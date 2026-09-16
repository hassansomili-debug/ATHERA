"""ملف الباحث والذاكرة الموثقة | Profile, fact review and verified memory (§35.1، §10).

هذا الموجّه يجسّد أهم قاعدة في المنتج: ما يخرج من مستند لا يصبح حقيقة إلا
بقرار إنسان. قائمة المراجعة هنا هي بوابة G0 عمليًا.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import tenant_session_maker
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.research import FactCandidate, ResearcherMemory, ResearcherProfile
from ..schemas.profile import (
    DecisionRequest,
    FactCandidateResponse,
    ImportRequest,
    ImportResponse,
    MemoryResponse,
    ProfilePatch,
    ProfileResponse,
)
from ..services import audit, ingestion, memory
from ..services.extraction.base import Extractor
from ..services.extraction.rules import RuleBasedExtractor
from ..services.parsing import UnsupportedDocument, parse
from ..transaction import TransactionalRoute

router = APIRouter(prefix="/api/v1/profile", tags=["profile"], route_class=TransactionalRoute)


def _pick(locale: str, arabic: str | None, english: str | None) -> str | None:
    return (english or arabic) if locale == "en" else (arabic or english)


async def _get_or_create_profile(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> ResearcherProfile:
    profile = (
        await session.execute(
            select(ResearcherProfile).where(ResearcherProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = ResearcherProfile(tenant_id=tenant_id, user_id=user_id)
        session.add(profile)
        await session.flush()
    return profile


@router.get("", response_model=ProfileResponse)
async def get_profile(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    profile = await _get_or_create_profile(session, principal.tenant_id, principal.user_id)
    verified_count = (
        await session.execute(
            select(func.count())
            .select_from(ResearcherMemory)
            .where(ResearcherMemory.verification_status == "verified")
        )
    ).scalar_one()
    return ProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        institution=_pick(principal.locale, profile.institution_ar, profile.institution_en),
        institution_ar=profile.institution_ar,
        institution_en=profile.institution_en,
        current_rank=profile.current_rank,
        target_rank=profile.target_rank,
        primary_field=_pick(principal.locale, profile.primary_field_ar, profile.primary_field_en),
        keywords=profile.keywords,
        orcid=profile.orcid,
        g0_approved_at=profile.g0_approved_at,
        verified_memory_count=verified_count,
    )


@router.patch("", response_model=ProfileResponse)
async def patch_profile(
    payload: ProfilePatch,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    profile = await _get_or_create_profile(session, principal.tenant_id, principal.user_id)
    before = {
        field: getattr(profile, field)
        for field in payload.model_dump(exclude_unset=True)
    }
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="profile.updated",
        object_type="researcher_profile",
        object_id=profile.id,
        actor_user_id=principal.user_id,
        state_before=before,
        state_after=payload.model_dump(exclude_unset=True),
        # §7.4 — ما يكتبه الباحث بنفسه مسار مشروع: تأكيد صريح منه.
        reason="researcher self-declared profile field (user_statement path, §7.4)",
    )
    return await get_profile(principal, session)


@router.post("/import", response_model=ImportResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_document(
    payload: ImportRequest,
    principal: Principal = Depends(get_principal),
) -> ImportResponse:
    """§35.1 — ملف مرفوع → مقاطع بموضع → مرشّحات غير متحققة.

    **ولا معاملةَ قاعدةٍ عبر التخزين ولا عبر النموذج** (RC-T1-H3):

        (١) معاملةٌ قصيرة : الملفُّ موجودٌ وجاهز ⇒ يُحمَل **مفتاحُه** ونوعُه
        (٢) بلا معاملة    : تُقرأ البايتات من التخزين
        (٣) بلا معاملة    : يُفكَّك النصّ (حسابٌ محلّيّ)، ثمّ يُستدعى النموذج
                            إن كان المُستخرِجُ نموذجيًّا — ويُسجّل نداءَه
                            في معاملةٍ قصيرةٍ خاصّةٍ به
        (٤) معاملةٌ قصيرة : يُخزَّن الاستخراجُ كلُّه ويُودَع

    **والمُستخرِجُ النموذجيُّ كان عطبًا ثانيًا في هذا المسار**: كان يُبنى
    بجلسة الطلب فيُمرّرها إلى بوابة النموذج — أي نداءُ نموذجٍ داخل معاملةٍ
    حيّة. ولم يره الماسحُ الساكن لأنّ `Extractor` واجهةٌ تُمرَّر مُعامِلًا.
    فصار يُبنى بدالّةِ جلسةٍ لا بجلسة.

    **ورموزُ الإخفاق ومواضعُها كما كانت**: ملفٌّ غائب ٤٠٤، وملفٌّ غيرُ جاهز
    ٤٠٩ — ويُفحص ذلك في الطور (١) **قبل** أيّ قراءةٍ من التخزين، كما كان
    يقع قبل `_load_bytes`.
    """
    session_maker = tenant_session_maker(principal.tenant_id, principal.user_id)

    # ── الطورُ (١): **قراءاتٌ فقط** — ولا كتابةَ تسبق الانتظار ──
    #
    # **ولا يُنشأ المِلفُّ الشخصيُّ هنا.** كان `_get_or_create_profile` في
    # هذا الطور، وهو **كتابة**: فتُودَع قبل قراءة التخزين، فإن أخفق
    # الاستيراد بقي مِلفٌّ شخصيٌّ جديدٌ أثرًا لطلبٍ فاشل. وقبل RC-T1-H3-B
    # كان الإنشاءُ والاستخراجُ في معاملةِ الطلب نفسِها، فيرجعان معًا —
    # **وتقصيرُ المعاملات لا يجوز أن يُضعف تلك الذرّيّة.**
    #
    # فصار الإنشاءُ في معاملة الإنهاء مع الاستخراج: إمّا يقعان معًا أو
    # لا يقع أيٌّ منهما.
    async with session_maker() as session:
        record = (await session.execute(
            select(File).where(File.id == payload.file_id,
                               File.tenant_id == principal.tenant_id)
        )).scalar_one_or_none()
        if record is None:
            raise NotFound("file.not_found")
        if record.status != "stored":
            raise AtheraError("ingestion.file_not_ready", status_code=409,
                              status=record.status)
        # **قيمٌ لا صفّ**: المفتاحُ والنوعُ والاسم، ولا كائنَ ORM يعبُر.
        storage_key = record.storage_key
        content_type = record.content_type
        filename = record.original_filename

    # ── الطورُ (٢): التخزين، بلا معاملة ──
    data = await ingestion.load_object_bytes(storage_key)

    # ── الطورُ (٣): التفكيكُ ثمّ الاقتراح، بلا معاملةٍ مفتوحة ──
    extractor: Extractor = RuleBasedExtractor()
    if payload.extractor == "model":
        from ..providers.gateway import ModelGateway  # noqa: PLC0415
        from ..services.extraction.model import ModelExtractor  # noqa: PLC0415

        extractor = ModelExtractor(
            ModelGateway(), session_maker, principal.tenant_id, classification="C2"
        )
    try:
        chunks = parse(data, content_type, filename)
    except UnsupportedDocument as exc:
        # الرمزُ والموضعُ كما كانا في `ingest_file`، ويُسجَّل الإخفاق.
        async with session_maker() as session:
            await audit.record(
                session, tenant_id=principal.tenant_id, action="ingestion.failed",
                object_type="file", object_id=payload.file_id,
                actor_user_id=principal.user_id, reason=str(exc),
            )
        raise AtheraError("ingestion.unsupported_document", status_code=422,
                          detail=str(exc)) from exc
    proposal = await extractor.propose(chunks)

    # ── الطورُ (٤): الإنشاءُ والتخزينُ والإيداع — **في معاملةٍ واحدة** ──
    #
    # والترتيبُ داخلها لا يُغيّر الحصيلة: `ingest_file` تُعيد التحقّق من
    # الملفّ وحاله، فإن رفعت (٤٠٤ أو ٤٠٩) رجعت المعاملةُ كلُّها ومعها
    # المِلفُّ الشخصيّ. **فإخفاقُ الاستيراد لا يُخلّف مِلفًّا جديدًا.**
    #
    # ومِلفٌّ كان موجودًا قبل الطلب لا يُمَسّ: `_get_or_create_profile`
    # تقرؤه ولا تُنشئ بديلًا، ولا تحذف شيئًا عند الإخفاق.
    async with session_maker() as session:
        await _get_or_create_profile(session, principal.tenant_id, principal.user_id)
        run, candidates = await ingestion.ingest_file(
            session,
            tenant_id=principal.tenant_id,
            file_id=payload.file_id,
            actor_user_id=principal.user_id,
            extractor_name=extractor.name,
            raw_bytes=data,
            proposal=proposal,
        )
        return ImportResponse(
            extraction_run_id=run.id,
            chunks_parsed=run.chunks_parsed,
            candidates_proposed=run.candidates_proposed,
            candidates_rejected_unquoted=run.candidates_rejected_unquoted,
            extractor=run.extractor,
        )


@router.get("/facts", response_model=list[FactCandidateResponse])
async def list_facts(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    fact_status: str = Query(default="unverified", pattern="^(unverified|approved|rejected|all)$"),
    limit: int = Query(default=200, le=500),
) -> list[FactCandidateResponse]:
    statement = (
        select(FactCandidate).order_by(FactCandidate.created_at.desc()).limit(limit)
    )
    if fact_status != "all":
        statement = statement.where(FactCandidate.status == fact_status)
    rows = (await session.execute(statement)).scalars().all()
    return [
        FactCandidateResponse(
            id=row.id,
            memory_category=row.memory_category,
            field_key=row.field_key,
            statement=_pick(principal.locale, row.statement_ar, row.statement_en) or row.statement_ar,
            statement_ar=row.statement_ar,
            statement_en=row.statement_en,
            quote=row.quote,
            locator=row.locator,
            file_id=row.file_id,
            confidence=float(row.confidence) if row.confidence is not None else None,
            status=row.status,
            decided_at=row.decided_at,
            decision_reason=row.decision_reason,
        )
        for row in rows
    ]


@router.post("/facts/{candidate_id}/approve", response_model=MemoryResponse)
async def approve_fact(
    candidate_id: uuid.UUID,
    payload: DecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemoryResponse:
    record = await memory.approve_candidate(
        session,
        tenant_id=principal.tenant_id,
        candidate_id=candidate_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
    )
    return MemoryResponse(
        id=record.id,
        memory_category=record.memory_category,
        statement=_pick(principal.locale, record.statement_ar, record.statement_en)
        or record.statement_ar,
        statement_ar=record.statement_ar,
        statement_en=record.statement_en,
        value=record.value,
        source_type=record.source_type,
        source_locator=record.source_locator,
        source_quote=record.source_quote,
        verification_status=record.verification_status,
        verified_at=record.verified_at,
    )


@router.post("/facts/{candidate_id}/reject", response_model=FactCandidateResponse)
async def reject_fact(
    candidate_id: uuid.UUID,
    payload: DecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FactCandidateResponse:
    row = await memory.reject_candidate(
        session,
        tenant_id=principal.tenant_id,
        candidate_id=candidate_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
    )
    return FactCandidateResponse(
        id=row.id,
        memory_category=row.memory_category,
        field_key=row.field_key,
        statement=_pick(principal.locale, row.statement_ar, row.statement_en) or row.statement_ar,
        statement_ar=row.statement_ar,
        statement_en=row.statement_en,
        quote=row.quote,
        locator=row.locator,
        file_id=row.file_id,
        confidence=float(row.confidence) if row.confidence is not None else None,
        status=row.status,
        decided_at=row.decided_at,
        decision_reason=row.decision_reason,
    )
