"""خط أنابيب الاستيعاب | Ingestion pipeline (§41.2، §33.1).

ملف مخزَّن → مقاطع بموضع → مرشّحات حقائق. كل خطوة تُسجَّل، ولا خطوة تنتج
معلومة «موثقة».
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.research import DocumentChunk, ExtractionRun, FactCandidate
from . import audit
from .extraction.base import ExtractionResult, Extractor
from .extraction.rules import RuleBasedExtractor
from .parsing import UnsupportedDocument, parse


async def _load_bytes(record: File) -> bytes:
    import boto3  # noqa: PLC0415

    from ..config import get_settings

    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    response = client.get_object(Bucket=settings.s3_bucket, Key=record.storage_key)
    return response["Body"].read()


async def ingest_file(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    file_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    extractor: Extractor | None = None,
    raw_bytes: bytes | None = None,
) -> tuple[ExtractionRun, list[FactCandidate]]:
    record = (await session.execute(
        select(File).where(File.id == file_id, File.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    if record.status != "stored":
        raise AtheraError("ingestion.file_not_ready", status_code=409, status=record.status)

    extractor = extractor or RuleBasedExtractor()
    run = ExtractionRun(
        tenant_id=tenant_id,
        file_id=file_id,
        extractor=extractor.name,
        status="running",
        started_at=dt.datetime.now(dt.UTC),
    )
    session.add(run)
    await session.flush()

    try:
        data = raw_bytes if raw_bytes is not None else await _load_bytes(record)
        chunks = parse(data, record.content_type, record.original_filename)
    except UnsupportedDocument as exc:
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = dt.datetime.now(dt.UTC)
        await audit.record(
            session, tenant_id=tenant_id, action="ingestion.failed", object_type="file",
            object_id=file_id, actor_user_id=actor_user_id, reason=str(exc),
        )
        raise AtheraError("ingestion.unsupported_document", status_code=422, detail=str(exc)) from exc

    stored: dict[int, DocumentChunk] = {}
    for parsed in chunks:
        chunk = DocumentChunk(
            tenant_id=tenant_id,
            file_id=file_id,
            seq=parsed.seq,
            text=parsed.text,
            locator=parsed.locator,
            page_number=parsed.page_number,
            section_path=parsed.section_path,
            paragraph_index=parsed.paragraph_index,
            char_count=parsed.char_count,
            is_untrusted=True,  # §33.3 — بلا استثناء ولا وضع "موثوق".
        )
        session.add(chunk)
        stored[parsed.seq] = chunk
    await session.flush()

    result: ExtractionResult = await extractor.propose(chunks)

    candidates: list[FactCandidate] = []
    for candidate in result.candidates:
        chunk = stored.get(candidate.chunk_seq)
        if chunk is None:  # pragma: no cover — الحاجز يمنعه أصلًا
            continue
        row = FactCandidate(
            tenant_id=tenant_id,
            extraction_run_id=run.id,
            file_id=file_id,
            chunk_id=chunk.id,
            memory_category=candidate.memory_category,
            field_key=candidate.field_key,
            statement_ar=candidate.statement_ar,
            statement_en=candidate.statement_en,
            value=candidate.value,
            quote=candidate.quote,
            locator=chunk.locator,
            confidence=candidate.confidence,
            status="unverified",  # §10.2 — لا شيء يبدأ معتمدًا.
        )
        session.add(row)
        candidates.append(row)

    run.status = "completed"
    run.chunks_parsed = len(chunks)
    run.candidates_proposed = len(candidates)
    run.candidates_rejected_unquoted = len(result.rejected_unquoted)
    run.model_run_id = uuid.UUID(result.model_run_id) if result.model_run_id else None
    run.finished_at = dt.datetime.now(dt.UTC)
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="ingestion.completed",
        object_type="file",
        object_id=file_id,
        actor_user_id=actor_user_id,
        state_after={
            "extractor": extractor.name,
            "chunks": len(chunks),
            "candidates": len(candidates),
            "rejected_unquoted": len(result.rejected_unquoted),
        },
        reason="facts extracted as unverified candidates pending human review (§10.2)",
    )
    if result.rejected_unquoted:
        # اقتباس غير مؤصَّل مؤشر اختلاق — يُرفع كتنبيه نزاهة لا يُبتلع صامتًا.
        from ..models.audit import IntegrityAlert

        session.add(
            IntegrityAlert(
                tenant_id=tenant_id,
                alert_type="ungrounded_extraction",
                severity="warning",
                name_ar="مرشّحات حقائق باقتباسات غير موجودة في المصدر",
                name_en="Fact candidates with quotes absent from the source",
                detail_ar=f"رُفض {len(result.rejected_unquoted)} مرشّحًا آليًا قبل المراجعة.",
                detail_en=f"{len(result.rejected_unquoted)} candidates auto-rejected before review.",
                object_type="file",
                object_id=file_id,
            )
        )
    return run, candidates
