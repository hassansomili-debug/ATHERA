"""فريق المشروع وقراراته | Project team and decisions (§12، §24).

ما لا يفعله هذا الموجّه: لا يستنتج أدوار CRediT من نشاط أحد، ولا يسجّل
موافقة نيابةً عن مؤلف، ولا يعدّل قرارًا محسومًا.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.portfolio import ProjectDecision, ProjectMember, ResearchProject
from ..schemas.team import (
    DecisionCreateRequest,
    DecisionResponse,
    MemberCreateRequest,
    MemberResponse,
    VocabularyResponse,
)
from ..services import audit, team

router = APIRouter(prefix="/api/v1", tags=["team"])


def _pick(locale: str, arabic: str, english: str | None) -> str:
    return (english or arabic) if locale == "en" else arabic


def _vocab(mapping: dict[str, tuple[str, str]], locale: str) -> list[VocabularyResponse]:
    return [
        VocabularyResponse(key=key, label=_pick(locale, *value))
        for key, value in mapping.items()
    ]


@router.get("/vocab/credit-roles", response_model=list[VocabularyResponse])
async def credit_roles(principal: Principal = Depends(get_principal)):
    return _vocab(team.CREDIT_ROLES, principal.locale)


@router.get("/vocab/member-roles", response_model=list[VocabularyResponse])
async def member_roles(principal: Principal = Depends(get_principal)):
    return _vocab(team.MEMBER_ROLES, principal.locale)


@router.get("/vocab/decision-kinds", response_model=list[VocabularyResponse])
async def decision_kinds(principal: Principal = Depends(get_principal)):
    return _vocab(team.DECISION_KINDS, principal.locale)


async def _require_project(session: AsyncSession, project_id: uuid.UUID) -> ResearchProject:
    row = (
        await session.execute(select(ResearchProject).where(ResearchProject.id == project_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("team.project_not_found")
    return row


def _member(row: ProjectMember, locale: str) -> MemberResponse:
    credit = list(row.credit_roles or [])
    return MemberResponse(
        id=row.id, project_id=row.project_id, display_name=row.display_name,
        user_id=row.user_id, role=row.role,
        role_label=_pick(locale, *team.MEMBER_ROLES.get(row.role, (row.role, row.role))),
        credit_roles=credit,
        credit_labels=[
            _pick(locale, *team.CREDIT_ROLES[key]) for key in credit
            if key in team.CREDIT_ROLES
        ],
        consent_recorded_at=row.consent_recorded_at,
    )


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[MemberResponse]:
    await _require_project(session, project_id)
    rows = (
        await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at)
        )
    ).scalars().all()
    return [_member(row, principal.locale) for row in rows]


@router.post("/projects/{project_id}/members", response_model=MemberResponse,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    payload: MemberCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    await _require_project(session, project_id)
    if payload.role not in team.MEMBER_ROLES:
        raise AtheraError("team.unknown_member_role", status_code=422, role=payload.role)
    try:
        team.validate_author_name(payload.display_name)
        team.validate_credit_roles(payload.credit_roles)
    except team.TeamError as exc:
        raise AtheraError("team.invalid_member", status_code=422, detail=str(exc)) from exc

    row = ProjectMember(
        tenant_id=principal.tenant_id, project_id=project_id,
        user_id=payload.user_id, display_name=payload.display_name.strip(),
        role=payload.role, credit_roles=payload.credit_roles or None,
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="team.member_added",
        object_type="project_member", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"role": payload.role, "credit_roles": payload.credit_roles},
        reason="CRediT roles are recorded as declared, never inferred (§24)",
    )
    return _member(row, principal.locale)


@router.post("/projects/{project_id}/members/{member_id}/consent",
             response_model=MemberResponse)
async def record_consent(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """§24 — الموافقة تُسجَّل عن مؤلف بعينه، ولها وقت وفاعل.

    لا مسار يسجّل موافقة الجميع دفعة واحدة: «وافق الجميع» بضغطة واحدة هو
    بالضبط ما يجعل موافقة التأليف بلا معنى.
    """
    row = (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.id == member_id, ProjectMember.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("team.member_not_found")
    if row.consent_recorded_at is not None:
        raise AtheraError("team.consent_already_recorded", status_code=422)

    row.consent_recorded_at = dt.datetime.now(dt.UTC)
    await audit.record(
        session, tenant_id=principal.tenant_id, action="team.consent_recorded",
        object_type="project_member", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"display_name": row.display_name},
    )
    return _member(row, principal.locale)


def _decision(row: ProjectDecision, superseded: set[uuid.UUID], locale: str) -> DecisionResponse:
    kind = team.DECISION_KINDS.get(row.decision_kind,
                                   (row.decision_kind, row.decision_kind))
    return DecisionResponse(
        id=row.id, project_id=row.project_id, decision_kind=row.decision_kind,
        kind_label=_pick(locale, *kind),
        statement=_pick(locale, row.statement_ar, row.statement_en),
        gate=row.gate, approval_id=row.approval_id, decided_by=row.decided_by,
        decided_at=row.decided_at, supersedes_id=row.supersedes_id,
        is_superseded=row.id in superseded,
    )


@router.get("/projects/{project_id}/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DecisionResponse]:
    """يعيد السلسلة كاملة — المنسوخ والناسخ معًا.

    إخفاء القرار المنسوخ يجعل السجل يبدو كأن الرأي الحالي هو الرأي الوحيد.
    """
    await _require_project(session, project_id)
    rows = (
        await session.execute(
            select(ProjectDecision).where(ProjectDecision.project_id == project_id)
            .order_by(ProjectDecision.created_at)
        )
    ).scalars().all()
    superseded = {row.supersedes_id for row in rows if row.supersedes_id}
    return [_decision(row, superseded, principal.locale) for row in rows]


@router.post("/projects/{project_id}/decisions", response_model=DecisionResponse,
             status_code=status.HTTP_201_CREATED)
async def record_decision(
    project_id: uuid.UUID,
    payload: DecisionCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DecisionResponse:
    await _require_project(session, project_id)
    if payload.decision_kind not in team.DECISION_KINDS:
        raise AtheraError("team.unknown_decision_kind", status_code=422,
                          kind=payload.decision_kind)

    if payload.supersedes_id is not None:
        previous = (
            await session.execute(
                select(ProjectDecision).where(ProjectDecision.id == payload.supersedes_id)
            )
        ).scalar_one_or_none()
        if previous is None:
            raise NotFound("team.decision_not_found")
        if previous.project_id != project_id:
            raise AtheraError("team.decision_other_project", status_code=422)

    row = ProjectDecision(
        tenant_id=principal.tenant_id, project_id=project_id,
        decision_kind=payload.decision_kind, statement_ar=payload.statement_ar,
        statement_en=payload.statement_en, gate=payload.gate,
        supersedes_id=payload.supersedes_id,
        decided_by=principal.user_id, decided_at=dt.datetime.now(dt.UTC),
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="team.decision_recorded",
        object_type="project_decision", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"kind": payload.decision_kind,
                     "supersedes": str(payload.supersedes_id) if payload.supersedes_id else None},
    )
    return _decision(row, set(), principal.locale)
