"""ملف الباحث والذاكرة الموثقة | Profile, fact review and verified memory (§35.1، §10).

هذا الموجّه يجسّد أهم قاعدة في المنتج: ما يخرج من مستند لا يصبح حقيقة إلا
بقرار إنسان. قائمة المراجعة هنا هي بوابة G0 عمليًا.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
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
from ..services.extraction.rules import RuleBasedExtractor

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


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
    session: AsyncSession = Depends(get_session),
) -> ImportResponse:
    """§35.1 — ملف مرفوع → مقاطع بموضع → مرشّحات غير متحققة."""
    extractor = RuleBasedExtractor()
    if payload.extractor == "model":
        from ..providers.gateway import ModelGateway  # noqa: PLC0415
        from ..services.extraction.model import ModelExtractor  # noqa: PLC0415

        extractor = ModelExtractor(
            ModelGateway(), session, principal.tenant_id, classification="C2"
        )

    await _get_or_create_profile(session, principal.tenant_id, principal.user_id)
    run, candidates = await ingestion.ingest_file(
        session,
        tenant_id=principal.tenant_id,
        file_id=payload.file_id,
        actor_user_id=principal.user_id,
        extractor=extractor,
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
