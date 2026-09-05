"""ذكاءُ الباحث | Researcher intelligence routes (§11).

**ولا يختم موجّهٌ معاملةً لا يملكها** (ADR-0003). `tenant_session` تفتحها
وتختمها عند الخروج، ومن ختم في الوسط ثمّ قرأ بالجلسة نفسها سقط طلبُه بـ٥٠٠.
ولا `session.commit()` في هذا الملفّ — ويحرسه `test_no_router_owns_its_transaction`.

**ولا مسارَ هنا يكتب في الملفّ الفعّال نيابةً عن الباحث.** التأكيدُ وحده
يفعل، وهو نداءٌ صريحٌ منه.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..models.researcher_intelligence import (
    STATES_OUTSIDE_THE_ACTIVE_PROFILE,
    ResearcherConstraint,
    ResearcherGoal,
    ResearcherProfileCandidate,
)
from ..schemas.researcher import (
    CandidateDecision,
    ConstraintCreate,
    ConstraintPatch,
    ConstraintResponse,
    GoalCreate,
    GoalPatch,
    GoalResponse,
    ProfileCandidateCreate,
    ProfileCandidateResponse,
    ResearcherProfilePatch,
    ResearcherProfileResponse,
    StrategyApproval,
    StrategyCreate,
    StrategyResponse,
)
from ..services.researcher import profile as profile_service
from ..services.researcher import strategy as strategy_service

router = APIRouter(prefix="/api/v1/researcher", tags=["researcher"])


# ═══════════════════ العرض ═══════════════════


def _profile_view(profile) -> ResearcherProfileResponse:
    return ResearcherProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        institution_ar=profile.institution_ar,
        institution_en=profile.institution_en,
        college_ar=profile.college_ar,
        college_en=profile.college_en,
        department_ar=profile.department_ar,
        department_en=profile.department_en,
        current_rank=profile.current_rank,
        target_rank=profile.target_rank,
        primary_field_ar=profile.primary_field_ar,
        primary_field_en=profile.primary_field_en,
        country=profile.country,
        keywords=profile.keywords,
        preferred_research_languages=profile.preferred_research_languages,
        preferred_working_language=profile.preferred_working_language,
        preferred_manuscript_language=profile.preferred_manuscript_language,
        ai_response_language=profile.ai_response_language,
        orcid=profile.orcid,
        orcid_status=profile.orcid_status,
        orcid_verified_at=profile.orcid_verified_at,
        orcid_source=profile.orcid_source,
        field_provenance=profile.field_provenance,
    )


def _candidate_view(row: ResearcherProfileCandidate) -> ProfileCandidateResponse:
    return ProfileCandidateResponse(
        id=row.id,
        field_name=row.field_name,
        candidate_value=row.candidate_value,
        source_type=row.source_type,
        source_id=row.source_id,
        provenance=row.provenance,
        extraction_method=row.extraction_method,
        profile_state=row.profile_state,
        status=row.status,
        # **أهو في الملفّ الفعّال؟** يُقال صراحةً: المستخرَجُ والمقترَحُ لا
        # يكونان فيه أبدًا، والمؤكَّدُ وحده يكون (§2).
        in_active_profile=(
            row.profile_state not in STATES_OUTSIDE_THE_ACTIVE_PROFILE
            and row.status == "confirmed"
        ),
        created_at=row.created_at,
        decided_at=row.decided_at,
        decided_by=row.decided_by,
        decision_reason=row.decision_reason,
    )


def _goal_view(row: ResearcherGoal) -> GoalResponse:
    return GoalResponse(
        id=row.id, goal_type=row.goal_type, target=row.target, priority=row.priority,
        timeframe=row.timeframe, status=row.status,
        researcher_confirmed=row.researcher_confirmed, notes=row.notes,
        created_at=row.created_at,
    )


def _constraint_view(row: ResearcherConstraint) -> ConstraintResponse:
    return ConstraintResponse(
        id=row.id, constraint_type=row.constraint_type, value=row.value,
        notes=row.notes, researcher_confirmed=row.researcher_confirmed,
        created_at=row.created_at,
    )


def _strategy_view(row, *, with_snapshots: bool) -> StrategyResponse:
    return StrategyResponse(
        id=row.id,
        strategy_version=row.strategy_version,
        status=row.status,
        generated_at=row.generated_at,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
        superseded_by=row.superseded_by,
        rationale_ar=row.rationale_ar,
        rationale_en=row.rationale_en,
        missing_information=list(row.missing_information or []),
        profile_snapshot=row.profile_snapshot if with_snapshots else None,
        goals_snapshot=row.goals_snapshot if with_snapshots else None,
        constraints_snapshot=row.constraints_snapshot if with_snapshots else None,
    )


async def _profile_of(session: AsyncSession, principal: Principal):
    return await profile_service.get_or_create(
        session, tenant_id=principal.tenant_id, user_id=principal.user_id
    )


# ═══════════════════ الملفّ ═══════════════════


@router.get("/profile", response_model=ResearcherProfileResponse)
async def read_profile(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ResearcherProfileResponse:
    return _profile_view(await _profile_of(session, principal))


@router.patch("/profile", response_model=ResearcherProfileResponse)
async def update_profile(
    payload: ResearcherProfilePatch,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ResearcherProfileResponse:
    profile = await _profile_of(session, principal)
    updated = await profile_service.update_profile(
        session,
        profile=profile,
        changes=payload.model_dump(exclude_unset=True),
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
    )
    return _profile_view(updated)


# ═══════════════════ المرشَّحات ═══════════════════


@router.get("/profile/candidates", response_model=list[ProfileCandidateResponse])
async def list_candidates(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    candidate_status: str | None = Query(
        default=None, pattern="^(proposed|confirmed|rejected|needs_review)$"
    ),
) -> list[ProfileCandidateResponse]:
    profile = await _profile_of(session, principal)
    rows = await profile_service.list_candidates(
        session, profile_id=profile.id, status=candidate_status
    )
    return [_candidate_view(row) for row in rows]


@router.post(
    "/profile/candidates",
    response_model=ProfileCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def propose_candidate(
    payload: ProfileCandidateCreate,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProfileCandidateResponse:
    """إدخالٌ يدويّ (§3، الخيار الأوّل) — **ويبقى خارج الملفّ حتى يُؤكَّد.**"""
    profile = await _profile_of(session, principal)
    candidate = await profile_service.propose_manual_candidate(
        session,
        tenant_id=principal.tenant_id,
        profile=profile,
        field_name=payload.field_name,
        candidate_value=payload.candidate_value,
        provenance=payload.provenance,
        actor_user_id=principal.user_id,
    )
    return _candidate_view(candidate)


@router.post(
    "/profile/candidates/{candidate_id}/confirm", response_model=ProfileCandidateResponse
)
async def confirm_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProfileCandidateResponse:
    profile = await _profile_of(session, principal)
    candidate = await profile_service.confirm_candidate(
        session,
        tenant_id=principal.tenant_id,
        profile=profile,
        candidate_id=candidate_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
    )
    return _candidate_view(candidate)


@router.post(
    "/profile/candidates/{candidate_id}/reject", response_model=ProfileCandidateResponse
)
async def reject_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProfileCandidateResponse:
    profile = await _profile_of(session, principal)
    candidate = await profile_service.reject_candidate(
        session,
        tenant_id=principal.tenant_id,
        profile=profile,
        candidate_id=candidate_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
    )
    return _candidate_view(candidate)


# ═══════════════════ الأهداف ═══════════════════


@router.get("/goals", response_model=list[GoalResponse])
async def list_goals(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[GoalResponse]:
    profile = await _profile_of(session, principal)
    rows = await profile_service.list_goals(session, profile_id=profile.id)
    return [_goal_view(row) for row in rows]


@router.post("/goals", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: GoalCreate,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GoalResponse:
    profile = await _profile_of(session, principal)
    goal = ResearcherGoal(
        tenant_id=principal.tenant_id,
        profile_id=profile.id,
        goal_type=payload.goal_type,
        target=payload.target,
        priority=payload.priority,
        timeframe=payload.timeframe,
        notes=payload.notes,
        researcher_confirmed=payload.researcher_confirmed,
        status="active",
    )
    session.add(goal)
    await session.flush()
    return _goal_view(goal)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
async def patch_goal(
    goal_id: uuid.UUID,
    payload: GoalPatch,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GoalResponse:
    profile = await _profile_of(session, principal)
    goal = await profile_service.load_goal(session, profile_id=profile.id, goal_id=goal_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await session.flush()
    return _goal_view(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    profile = await _profile_of(session, principal)
    goal = await profile_service.load_goal(session, profile_id=profile.id, goal_id=goal_id)
    await session.delete(goal)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ═══════════════════ القيود ═══════════════════


@router.get("/constraints", response_model=list[ConstraintResponse])
async def list_constraints(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ConstraintResponse]:
    profile = await _profile_of(session, principal)
    rows = await profile_service.list_constraints(session, profile_id=profile.id)
    return [_constraint_view(row) for row in rows]


@router.post(
    "/constraints", response_model=ConstraintResponse, status_code=status.HTTP_201_CREATED
)
async def create_constraint(
    payload: ConstraintCreate,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ConstraintResponse:
    profile = await _profile_of(session, principal)
    row = ResearcherConstraint(
        tenant_id=principal.tenant_id,
        profile_id=profile.id,
        constraint_type=payload.constraint_type,
        value=payload.value,
        notes=payload.notes,
        researcher_confirmed=payload.researcher_confirmed,
    )
    session.add(row)
    await session.flush()
    return _constraint_view(row)


@router.patch("/constraints/{constraint_id}", response_model=ConstraintResponse)
async def patch_constraint(
    constraint_id: uuid.UUID,
    payload: ConstraintPatch,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ConstraintResponse:
    profile = await _profile_of(session, principal)
    row = await profile_service.load_constraint(
        session, profile_id=profile.id, constraint_id=constraint_id
    )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await session.flush()
    return _constraint_view(row)


@router.delete("/constraints/{constraint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_constraint(
    constraint_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    profile = await _profile_of(session, principal)
    row = await profile_service.load_constraint(
        session, profile_id=profile.id, constraint_id=constraint_id
    )
    await session.delete(row)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ═══════════════════ الاستراتيجيّة ═══════════════════


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[StrategyResponse]:
    profile = await _profile_of(session, principal)
    rows = await strategy_service.list_versions(session, profile_id=profile.id)
    return [_strategy_view(row, with_snapshots=False) for row in rows]


@router.post(
    "/strategies", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED
)
async def create_strategy(
    payload: StrategyCreate,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    """**والتغييرُ يُنشئ إصدارًا** — ولا يُعدَّل إصدارٌ معتمَدٌ أبدًا (§11)."""
    profile = await _profile_of(session, principal)
    row = await strategy_service.create_version(
        session,
        tenant_id=principal.tenant_id,
        profile=profile,
        actor_user_id=principal.user_id,
        rationale_ar=payload.rationale_ar,
        rationale_en=payload.rationale_en,
    )
    return _strategy_view(row, with_snapshots=True)


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def read_strategy(
    strategy_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    profile = await _profile_of(session, principal)
    row = await strategy_service.load(
        session, profile_id=profile.id, strategy_id=strategy_id
    )
    return _strategy_view(row, with_snapshots=True)


@router.post("/strategies/{strategy_id}/approve", response_model=StrategyResponse)
async def approve_strategy(
    strategy_id: uuid.UUID,
    payload: StrategyApproval,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> StrategyResponse:
    profile = await _profile_of(session, principal)
    row = await strategy_service.approve(
        session,
        tenant_id=principal.tenant_id,
        profile=profile,
        strategy_id=strategy_id,
        actor_user_id=principal.user_id,
        reason=payload.reason,
    )
    return _strategy_view(row, with_snapshots=True)
