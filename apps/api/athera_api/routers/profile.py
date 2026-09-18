"""ملف الباحث والذاكرة الموثقة | Profile, fact review and verified memory (§35.1، §10).

هذا الموجّه يجسّد أهم قاعدة في المنتج: ما يخرج من مستند لا يصبح حقيقة إلا
بقرار إنسان. قائمة المراجعة هنا هي بوابة G0 عمليًا.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import tenant_session_maker
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError
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
from ..providers.gateway import (
    provider_idempotency_capability,
    provider_readiness,
)
from ..services import audit, idempotency, ingestion, library, memory
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
    request: Request,
    payload: ImportRequest,
    principal: Principal = Depends(get_principal),
) -> ImportResponse | JSONResponse:
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
        # ══ تفويضُ الملفِّ الحاضر، لا مجرَّدُ استعلامٍ بالمستأجر (H2-B4) ══
        #
        # **وكان استعلامًا بالمستأجر وحده.** فزميلٌ في المستأجر نفسِه بلا
        # منحةٍ على الملفّ كان يستورد ملفَّ غيره — ويُعيده بمفتاحٍ قديم
        # حتى بعد سحب وصوله. فيُقرأ بالحارس المشترك (`library.owned_file`)
        # الذي يفحص المنحةَ، **قبل** أيّ تحكيمِ مفتاح.
        record = await library.owned_file(
            session, tenant_id=principal.tenant_id, user_id=principal.user_id,
            file_id=payload.file_id, action="read")
        if record.status != "stored":
            raise AtheraError("ingestion.file_not_ready", status_code=409,
                              status=record.status)
        # **قيمٌ لا صفّ**: المفتاحُ والنوعُ والاسم، ولا كائنَ ORM يعبُر.
        storage_key = record.storage_key
        content_type = record.content_type
        filename = record.original_filename
        checksum = record.checksum_sha256

        # ══ الحجزُ **بعد** التفويض ══
        #
        # والبصمةُ تحمل **هُويّةَ المصدر**: تجزئةُ الملفّ ونوعُه والمُستخرِج.
        # فمحتوًى تغيّر تحت المفتاح نفسِه طلبٌ آخرُ في معناه — يُردّ
        # بتعارضٍ ولا يُعاد عليه استخراجُ محتوًى آخر.
        guard = idempotency.LeaseGuard()
        if idempotency.is_keyed(request):
            guard = await idempotency.begin_leased_in(
                session, request,
                tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
                body={
                    "file_id": str(payload.file_id),
                    "extractor": payload.extractor,
                    "checksum_sha256": checksum,
                    "content_type": content_type,
                },
                ttl=idempotency.LEASE_MODEL)
    if guard.answer is not None:
        return guard.answer

    # ── الطورُ (٢): التخزين، بلا معاملة ──
    #
    # **وسقوطُ القراءةِ مسلكٌ طرفيٌّ عاديّ، لا أثرٌ غامض.** لا نموذجَ نُودي،
    # ولا وسمَ حدٍّ كُتب — فلو تُرك الجيلُ `in_progress` لانتظر الباحثُ
    # انقضاءَ الإجارة قبل إعادةٍ مشروعة، وعطبُ التخزينِ لحظيٌّ غالبًا.
    # فيُغلَق الجيلُ إغلاقَ ما قبل الحدّ، ويبقى الخطأُ الصادقُ كما هو.
    try:
        data = await ingestion.load_object_bytes(storage_key)
    except Exception as exc:
        if guard.lease is not None:
            await idempotency.close_pre_external(
                session_maker, guard, reason=f"pre_external:{type(exc).__name__}")
        raise

    # ── الطورُ (٣): التفكيكُ ثمّ الاقتراح، بلا معاملةٍ مفتوحة ──
    # **والقراءةُ من التخزين ليست أثرَ نموذج**: لا وسمَ حدٍّ حولها. فإن
    # أخفقت قبل النموذج بقي المفتاحُ قابلًا لإعادةٍ صادقة.
    boundary = idempotency.ModelBoundary(
        session_maker, guard, provider=provider_readiness()[0],
        capability=provider_idempotency_capability())
    extractor: Extractor = RuleBasedExtractor()
    if payload.extractor == "model":
        from ..providers.gateway import ModelGateway  # noqa: PLC0415
        from ..services.extraction.model import ModelExtractor  # noqa: PLC0415

        extractor = ModelExtractor(
            ModelGateway(), session_maker, principal.tenant_id, classification="C2",
            before_provider_call=(boundary if guard.lease is not None else None),
        )
    try:
        chunks = parse(data, content_type, filename)
    except UnsupportedDocument as exc:
        # الرمزُ والموضعُ كما كانا في `ingest_file`، ويُسجَّل الإخفاق.
        failure = AtheraError("ingestion.unsupported_document", status_code=422,
                              detail=str(exc))
        if guard.lease is None:
            async with session_maker() as session:
                await audit.record(
                    session, tenant_id=principal.tenant_id,
                    action="ingestion.failed", object_type="file",
                    object_id=payload.file_id,
                    actor_user_id=principal.user_id, reason=str(exc),
                )
            raise failure from exc

        # ══ نتيجةٌ **حتميّة**: هذه البايتاتُ لا تُفكَّك، واليومَ كغدٍ ══
        #
        # فلا معنى لترك الجيلِ `in_progress`: إعادةٌ بالمفتاح نفسِه ستقرأ
        # التخزينَ وتُفكِّك وتُخفق الإخفاقَ عينَه، وتكتب تدقيقًا ثانيًا
        # لحدثٍ واحد. فيُثبَّت الجوابُ نفسُه — **بتنسيقِ معالجِ الأخطاء
        # القائم، لا بشكلٍ موازٍ** — ويُكتب التدقيقُ مرّةً، في المعاملةِ
        # نفسِها: كلاهما أو لا شيء.
        import json as _json  # noqa: PLC0415

        from ..errors import athera_error_handler  # noqa: PLC0415

        response = await athera_error_handler(request, failure)
        async with session_maker() as session:
            await audit.record(
                session, tenant_id=principal.tenant_id,
                action="ingestion.failed", object_type="file",
                object_id=payload.file_id,
                actor_user_id=principal.user_id, reason=str(exc),
            )
            await idempotency.settle_leased(
                session, guard, status=response.status_code,
                body=_json.loads(bytes(response.body).decode("utf-8")))
        return response
    try:
        proposal = await extractor.propose(chunks)
    except Exception as exc:  # noqa: BLE001 — يُفرَّق: قبل الحدِّ أم بعده
        if guard.lease is not None and not boundary.crossed:
            # قراءةٌ أو تفكيكٌ أو تفويضُ مزوّدٍ — كلُّها قبل أيّ نداء.
            await idempotency.close_pre_external(
                session_maker, guard, reason=f"pre_external:{type(exc).__name__}")
            raise
        if guard.lease is not None:
            from ..errors import athera_error_handler  # noqa: PLC0415

            return await athera_error_handler(
                request, idempotency.ExternalResultUnknown())
        raise

    # ── الطورُ (٤): الإنشاءُ والتخزينُ والإيداع — **في معاملةٍ واحدة** ──
    #
    # والترتيبُ داخلها لا يُغيّر الحصيلة: `ingest_file` تُعيد التحقّق من
    # الملفّ وحاله، فإن رفعت (٤٠٤ أو ٤٠٩) رجعت المعاملةُ كلُّها ومعها
    # المِلفُّ الشخصيّ. **فإخفاقُ الاستيراد لا يُخلّف مِلفًّا جديدًا.**
    #
    # ومِلفٌّ كان موجودًا قبل الطلب لا يُمَسّ: `_get_or_create_profile`
    # تقرؤه ولا تُنشئ بديلًا، ولا تحذف شيئًا عند الإخفاق.
    async with session_maker() as session:
        # ── وإعادةُ التفويضِ وفحصُ هُويّةِ المصدر قبل الإيداع ──
        #
        # فالقراءةُ والنموذجُ انتظرا، وقد تُسحب المنحةُ أو يتغيّر الملفّ.
        fresh_file = await library.owned_file(
            session, tenant_id=principal.tenant_id, user_id=principal.user_id,
            file_id=payload.file_id, action="read")
        if fresh_file.status != "stored":
            raise AtheraError("ingestion.file_not_ready", status_code=409,
                              status=fresh_file.status)
        if guard.lease is not None and fresh_file.checksum_sha256 != checksum:
            raise AtheraError("ingestion.source_changed", status_code=409,
                              expected_checksum=checksum,
                              current_checksum=fresh_file.checksum_sha256)
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
        answer = ImportResponse(
            extraction_run_id=run.id,
            chunks_parsed=run.chunks_parsed,
            candidates_proposed=run.candidates_proposed,
            candidates_rejected_unquoted=run.candidates_rejected_unquoted,
            extractor=run.extractor,
        )
        # **الاستخراجُ والإتمامُ في المعاملة نفسِها**: كلُّها أو لا شيء.
        await idempotency.settle_leased(
            session, guard, status=status.HTTP_202_ACCEPTED,
            body=jsonable_encoder(answer))
        return answer


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
