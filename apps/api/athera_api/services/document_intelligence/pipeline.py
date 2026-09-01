"""خطّ أنابيب ذكاء المستندات | The S5C processing pipeline.

    مخزَّن → تفكيك → مقاطع بمواضعها → حتمي أولًا → نموذج على الأدنى اللازم
    → مرشّحات → مراجعة إنسان

**لا مكدّس موازٍ:** التفكيك من `services/parsing.py`، والمقاطع في
`document_chunks`، والتشغيلة في `extraction_runs`، والمرشّحات في
`fact_candidates`. كلها قائمة قبل S5C.

**والنموذج يُستدعى عبر المنسّق وحده** — لا اتصال مباشر من خدمة بحثية بمزوّد.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.files import File
from ...models.research import DocumentChunk, ExtractionRun, FactCandidate
from ...models.thesis import Thesis
from ..extraction.base import quote_is_grounded
from ..parsing import UnsupportedDocument, parse
from .contracts import STATUS_EXTRACTED, STATUS_NOT_FOUND, ExtractionBatch
from .deterministic import extract as deterministic_extract
from .fields import MODEL_FIELDS, Section, memory_category_for
from .selection import ChunkView, excluded_report, select_chunks_for
from .states import Status

# حزمة حقول واحدة لكل قسم — استدعاء لكل حقل يضاعف الكلفة بلا فائدة.
_BATCH_SECTIONS = (
    Section.METADATA, Section.PROBLEM, Section.QUESTIONS,
    Section.THEORY, Section.METHODOLOGY, Section.FINDINGS, Section.LIMITS,
)


@dataclass(slots=True)
class PipelineResult:
    run_id: uuid.UUID
    status: Status
    chunks: int
    candidates: int
    excluded: dict[str, int]
    failed_sections: list[str]
    error: str | None = None
    # حقول فُحصت فلم تُوجد — تُعلَن مفقودة ولا تُخزَّن صفوفًا بلا اقتباس.
    not_found: tuple[str, ...] = ()


def _views(rows: list[DocumentChunk]) -> list[ChunkView]:
    return [
        ChunkView(str(r.id), r.seq, r.text, r.locator, r.page_number, r.section_path)
        for r in rows
    ]


async def parse_into_chunks(
    session: AsyncSession, *, tenant_id: uuid.UUID, record: File, data: bytes,
) -> list[DocumentChunk]:
    """تفكيك ثم حفظ المقاطع بمواضعها. مقطع بلا موضع لا يُحفظ (§29.2).

    **وإعادة القراءة لا تعيد التفكيك.** الملف في التخزين لا يُعدَّل — مفتاحه
    ثابت وبصمته محفوظة — فمقاطعه لا تتغير. وإعادة إدراجها تخالف
    `uq_document_chunks_seq` أصلًا، والأهمّ أنها تُنشئ مواضع جديدة لنفس
    النصّ فتُبطل إسناد المرشّحات القديمة إلى مقاطعها.
    """
    existing = list((
        await session.execute(
            select(DocumentChunk).where(DocumentChunk.file_id == record.id)
            .order_by(DocumentChunk.seq)
        )
    ).scalars().all())
    if existing:
        return existing

    parsed = parse(data, record.content_type, record.original_filename)
    rows: list[DocumentChunk] = []
    for chunk in parsed:
        if not chunk.locator:
            continue
        row = DocumentChunk(
            tenant_id=tenant_id, file_id=record.id, seq=len(rows), text=chunk.text,
            locator=chunk.locator, page_number=chunk.page_number,
            section_path=chunk.section_path, paragraph_index=None,
            char_count=len(chunk.text),
            # §33.3 — محتوى الملفات بيانات لا تعليمات، منذ لحظة الحفظ.
            is_untrusted=True,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


def build_prompt(section: Section, chunks: list[ChunkView], specs) -> str:
    """المطالبة: الحقول المطلوبة ثم المقاطع **موسومةً كبيانات**.

    الوسم صريح: ما بين `<DOCUMENT>` مادةٌ مُستخرَجة من ملف رفعه المستخدم،
    وليس تعليمات. وهذا هو حدّ الحقن في موضعه العملي — لا في التوثيق وحده.
    """
    wanted = "\n".join(
        f"- {s.key} ({s.label_en}){' [قد يتكرر]' if s.multi else ''}" for s in specs
    )
    body = "\n\n".join(
        f"[{c.locator}] {c.text[:1800]}" for c in chunks
    )
    return (
        f"استخرج الحقول التالية من مقاطع الرسالة أدناه، ولا شيء غيرها:\n{wanted}\n\n"
        "لكل حقل أعِد: field_key، وstatus، وvalue، وquote (اقتباس حرفي من المقاطع)، "
        "وextraction_confidence.\n"
        "إن لم يرد الحقل في المقاطع فـstatus = not_found وvalue = null. "
        "وإن ورد ملتبسًا فـstatus = ambiguous. **لا تخمّن ولا تكمل من معرفتك العامة.**\n\n"
        f"<DOCUMENT section=\"{section.value}\">\n{body}\n</DOCUMENT>"
    )


async def run_extraction(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    file_record: File,
    data: bytes,
    orchestrator,
    locale: str = "ar",
    run_id: uuid.UUID | None = None,
    external_allowed: bool = True,
    consent_state: str = "granted",
) -> PipelineResult:
    """التشغيلة كاملة — وكل فشل يُسمّى بسببه ولا يُبتلع.

    وفشل قسم لا يُسقط ما نجح: الأقسام الستة الأخرى تبقى، ويُبلَّغ عن الفاشل
    باسمه (§29). فرسالةٌ استُخرج منها ستة أقسام من سبعة أنفع من لا شيء.

    و`run_id` يسمح بمتابعة تشغيلة **أُنشئت وحُفظت قبل هذه المعاملة**. وذلك
    لا ترفٌ: انهيارٌ هنا يُرجِع المعاملة كلها، ومنها الصفّ الذي كان سيروي
    الانهيار — فيبقى الملف عند «لم تبدأ القراءة» وقد بدأت وسقطت.
    """
    run = None
    if run_id is not None:
        run = (
            await session.execute(select(ExtractionRun).where(ExtractionRun.id == run_id))
        ).scalar_one_or_none()
    if run is None:
        run = ExtractionRun(
            tenant_id=tenant_id, file_id=file_record.id, extractor="document_intelligence",
            status=Status.PARSING.value, chunks_parsed=0, candidates_proposed=0,
            candidates_rejected_unquoted=0, started_at=dt.datetime.now(dt.UTC),
        )
        session.add(run)
    await session.flush()

    # ── التفكيك ──
    try:
        rows = await parse_into_chunks(session, tenant_id=tenant_id, record=file_record, data=data)
    except UnsupportedDocument as exc:
        run.status = Status.PARSE_FAILED.value
        run.error = str(exc)[:500]
        run.finished_at = dt.datetime.now(dt.UTC)
        return PipelineResult(run.id, Status.PARSE_FAILED, 0, 0, {}, [], str(exc)[:200])

    run.chunks_parsed = len(rows)
    run.status = Status.EXTRACTING.value if external_allowed else Status.PARSED.value
    views = _views(rows)
    excluded = excluded_report(views)

    # ── الحتمي أولًا ──
    candidates = 0
    for value in deterministic_extract(views, filename=file_record.original_filename):
        session.add(FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run.id, file_id=file_record.id,
            chunk_id=uuid.UUID(value.chunk_id) if value.chunk_id else rows[0].id,
            memory_category="researcher_fact", field_key=value.field_key,
            statement_ar=str(value.value),
            value={"value": value.value, "extraction_status": STATUS_EXTRACTED},
            quote=value.quote, locator=value.locator,
            # `unverified` لا `extracted`: العمود حالة **قرار الإنسان** لا
            # نتيجة القراءة. وخلطهما كان يجعل كل مرشّح يبدو «مقرَّرًا» فيرفض
            # مسار الترقية اعتماده بحجّة أنه حُسم — وهو لم يُعرض بعد.
            confidence=1.0, status="unverified",
        ))
        candidates += 1

    # ── بلا إذن: يقف الخط عند المحلي، ولا يُعدّ ذلك فشلًا ──
    #
    # الاستخراج الحتمي تمّ، والمقاطع محفوظة بمواضعها، والمراجعة ممكنة على ما
    # استُخرج. وما لم يقع هو **الإرسال الخارجي وحده** — فيُقال باسمه.
    if not external_allowed:
        run.candidates_proposed = candidates
        run.status = (Status.LOCAL_ONLY.value if consent_state == "declined"
                      else Status.AWAITING_CONSENT.value)
        run.finished_at = dt.datetime.now(dt.UTC)
        return PipelineResult(run.id, Status(run.status), len(rows), candidates,
                              excluded, [], None, ())

    # ── النموذج، قسمًا قسمًا، على المقاطع المختارة وحدها ──
    failed: list[str] = []
    # حقول فُحصت ولم تُوجد — تُعدّ ولا تُخزَّن صفوفًا بلا اقتباس.
    attempted: set[str] = set()
    for section in _BATCH_SECTIONS:
        specs = [f for f in MODEL_FIELDS if f.section is section]
        if not specs:
            continue
        picked: dict[str, ChunkView] = {}
        for spec in specs:
            for chunk in select_chunks_for(spec, views):
                picked[chunk.chunk_id] = chunk
        if not picked:
            continue

        spec_by_key = {f.key: f for f in specs}
        chunk_list = sorted(picked.values(), key=lambda c: c.seq)
        try:
            result = await orchestrator(
                question=build_prompt(section, chunk_list, specs),
                schema=ExtractionBatch.model_json_schema(),
                # §7 — محتوى بحثي غير منشور: C2، والبوابة تحكم الإرسال.
                classification="C2",
                locale=locale,
            )
            batch = ExtractionBatch.model_validate(result)
        except Exception as exc:  # noqa: BLE001 — قسم يسقط ولا يُسقط غيره
            failed.append(f"{section.value}:{type(exc).__name__}")
            continue

        for field in batch.fields:
            if field.status == STATUS_NOT_FOUND:
                # **الغياب لا يُسجَّل صفًّا.** `fact_candidates` يشترط اقتباسًا
                # بقيد في القاعدة (`ck_candidate_quote_required`)، والمفقود لا
                # اقتباس له — فصفٌّ باقتباس فارغ يخالف القيد، وصفٌّ باقتباس
                # مستعار من مقطع لا يحوي الحقل هو اختلاق الموضع بعينه.
                #
                # والغياب يبقى مرئيًّا في المراجعة بلا صفّ: الشاشة تعرض فهرس
                # الحقول كاملًا، وما لا مرشّح له يُعلَن «لم يُستخرَج».
                attempted.add(field.field_key)
                continue

            # ── حاجز الاختلاق ──
            #
            # قيمة باقتباس لا يوجد في أي مقطع مُرسَل **تُرفض**. ولا مقطع
            # احتياطي يُسنَد إليه: إسناد اقتباسٍ مختلَق إلى أول مقطع يجعل
            # الاختلاق يمرّ **وقد اكتسب موضعًا**، وهو أسوأ من مروره عاريًا —
            # لأن الباحث سيرى مصدرًا يبدو صحيحًا فيثق به.
            #
            # والفحص هو `quote_is_grounded` نفسه الذي يستعمله الاعتماد في
            # §7.4. واختلافهما كان سيجعل مرشّحًا يُقبل هنا ويُرفض عند
            # الاعتماد — طريقٌ مسدود أمام الباحث بلا سبب مفهوم.
            quote = (field.quote or "").strip()
            source = next((c for c in chunk_list if quote_is_grounded(quote, c.text)), None)
            if source is None:
                run.candidates_rejected_unquoted += 1
                continue

            session.add(FactCandidate(
                tenant_id=tenant_id, extraction_run_id=run.id, file_id=file_record.id,
                chunk_id=uuid.UUID(source.chunk_id),
                memory_category=memory_category_for(spec_by_key[field.field_key])
                if field.field_key in spec_by_key else "researcher_fact",
                field_key=field.field_key,
                statement_ar=str(field.value) if field.value is not None else "",
                value={"value": field.value, "extraction_status": field.status},
                quote=quote[:2000], locator=source.locator,
                confidence=field.extraction_confidence, status="unverified",
            ))
            candidates += 1

    run.candidates_proposed = candidates
    run.finished_at = dt.datetime.now(dt.UTC)
    if failed and candidates == 0:
        run.status = Status.EXTRACTION_FAILED.value
        run.error = "; ".join(failed)[:500]
        return PipelineResult(run.id, Status.EXTRACTION_FAILED, len(rows), 0, excluded, failed,
                              run.error, tuple(sorted(attempted)))

    run.status = Status.AWAITING_REVIEW.value
    if failed:
        run.error = "partial: " + "; ".join(failed)[:400]
    return PipelineResult(run.id, Status.AWAITING_REVIEW, len(rows), candidates, excluded,
                          failed, run.error, tuple(sorted(attempted)))


async def ensure_thesis_for_file(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID,
) -> tuple[Thesis, bool]:
    """سجل الرسالة — يُنشأ مرة واحدة لكل ملف (§4، §5).

    **والتكرار يُمنع بالبحث لا بقيد جديد:** `theses.file_id` قائم، فالاستعلام
    عنه قبل الإنشاء يجعل إعادة المحاولة آمنة بلا ترحيل إضافي.

    ويُنشأ بلا عنوان ولا درجة: `NULL` تعني «لم يُستخرَج بعد» — واسم الملف
    عنوانًا أو درجةً مخمَّنة اختلاقٌ يمنعه §11.
    """
    existing = (
        await session.execute(select(Thesis).where(Thesis.file_id == file_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    thesis = Thesis(tenant_id=tenant_id, file_id=file_id, title_ar=None, degree=None)
    session.add(thesis)
    await session.flush()
    return thesis, True


def content_fingerprint(data: bytes) -> str:
    """بصمة المحتوى — لمنع إعادة معالجة المطابق بلا داعٍ (§27)."""
    return hashlib.sha256(data).hexdigest()
