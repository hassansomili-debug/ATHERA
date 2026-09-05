"""الملفُّ والمرشَّحاتُ والأهدافُ والقيود | Profile, candidates, goals, constraints.

**ولا يكتب مرشَّحٌ في الملفّ.** الكتابةُ فعلُ تأكيدٍ منفصلٌ يقع هنا، وله
صاحبٌ ووقتٌ يُسجَّلان في الصفّ وفي سجلّ التدقيق معًا.

**ولا تختم دالّةٌ هنا معاملتها.** `tenant_session` تفتحها وتختمها (ADR-0003).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.research import ResearcherProfile
from ...models.researcher_intelligence import (
    ResearcherConstraint,
    ResearcherGoal,
    ResearcherProfileCandidate,
)
from .. import audit
from . import orcid as orcid_service

#: الحقولُ التي يجوز أن يحملها مرشَّح — ومرشَّحٌ لحقلٍ خارجها يُرفض.
#:
#: القائمةُ مغلقةٌ عمدًا: مرشَّحٌ يسمّي عمودًا اعتباطيًّا كان سيصير مسارَ
#: كتابةٍ في الملفّ لا يمرّ بعينِ الباحث.
CONFIRMABLE_FIELDS: Final[tuple[str, ...]] = (
    "institution_ar", "institution_en",
    "college_ar", "college_en",
    "department_ar", "department_en",
    "current_rank", "target_rank",
    "primary_field_ar", "primary_field_en",
    "country",
    "orcid",
    "preferred_working_language",
    "preferred_manuscript_language",
    "ai_response_language",
)

#: الحالاتُ التي يجوز أن يُقرَّر منها مرشَّح. والمقرَّرُ لا يُقرَّر ثانيةً.
_DECIDABLE_FROM: Final = ("proposed", "needs_review")

#: لقطةُ الملفّ — الحقولُ التي تُخزَّن مع كلّ إصدارِ استراتيجيّة.
SNAPSHOT_FIELDS: Final[tuple[str, ...]] = (
    *CONFIRMABLE_FIELDS,
    "orcid_status",
    "preferred_research_languages",
    "related_fields",
    "keywords",
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def get_or_create(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> ResearcherProfile:
    """ملفٌّ واحدٌ للباحث — **ولا يُنشأ ملفٌّ ثانٍ** (§1)."""
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


def snapshot(profile: ResearcherProfile) -> dict[str, Any]:
    """لقطةٌ نصّيّةٌ من الملفّ — ولا رقمَ فيها يُقاس عليه."""
    return {field: getattr(profile, field, None) for field in SNAPSHOT_FIELDS}


# ═══════════════════ الملفُّ الفعّال ═══════════════════


async def update_profile(
    session: AsyncSession,
    *,
    profile: ResearcherProfile,
    changes: dict[str, Any],
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> ResearcherProfile:
    """ما يكتبه الباحثُ بيده يدخل الملفَّ فورًا — بحال `user_declared`.

    **وتبديلُ لغةٍ لا يمسّ لغةً أخرى** (§8): الحقولُ الأربعة أعمدةٌ مستقلّة،
    ولا سطرَ هنا يشتقّ واحدًا من آخر. ومَن بدّل لغةَ الشاشة لم يبدّل لغةَ
    مخطوطته، لأنّ لغةَ الشاشة ليست في هذا الجدول أصلًا.
    """
    before = {field: getattr(profile, field) for field in changes}

    if "orcid" in changes:
        normalised = orcid_service.normalise(changes["orcid"])
        if changes["orcid"] and normalised is None:
            raise AtheraError("researcher.orcid_malformed")
        if normalised is not None and not orcid_service.has_valid_format(normalised):
            raise AtheraError("researcher.orcid_checksum_failed")
        changes["orcid"] = normalised
        # **والصيغةُ الصحيحة ليست توثيقًا** (§6). أقصى ما يُقال عن رقمٍ
        # كتبه صاحبُه: أنّه قاله. ولا يرفعه شيءٌ هنا إلى `externally_verified`.
        changes["orcid_status"] = orcid_service.status_for_declared(normalised)
        changes["orcid_verified_at"] = None
        changes["orcid_source"] = None

    for field, value in changes.items():
        setattr(profile, field, value)

    _mark_provenance(
        profile,
        {field: "user_declared" for field in changes if field in CONFIRMABLE_FIELDS},
        actor_user_id=actor_user_id,
        candidate_id=None,
    )
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.profile_updated",
        object_type="researcher_profile",
        object_id=profile.id,
        actor_user_id=actor_user_id,
        state_before=_auditable(before),
        state_after=_auditable(changes),
        reason="researcher self-declared profile field (user_statement path, §7.4)",
    )
    return profile


def _auditable(values: dict[str, Any]) -> dict[str, Any]:
    """سجلُّ التدقيق يحمل ما تغيّر — ولا يحمل نصَّ سيرةٍ ولا رمزًا (§10)."""
    return {key: (None if value is None else str(value)) for key, value in values.items()}


def _mark_provenance(
    profile: ResearcherProfile,
    states: dict[str, str],
    *,
    actor_user_id: uuid.UUID,
    candidate_id: uuid.UUID | None,
) -> None:
    """يسجّل كيف صار كلُّ حقلٍ إلى ما هو عليه — ولا يُشتقّ منه حكم."""
    if not states:
        return
    provenance = dict(profile.field_provenance or {})
    stamp = _now().isoformat()
    for field, state in states.items():
        provenance[field] = {
            "state": state,
            "decided_by": str(actor_user_id),
            "decided_at": stamp,
            "candidate_id": str(candidate_id) if candidate_id else None,
        }
    profile.field_provenance = provenance


# ═══════════════════ المرشَّحات ═══════════════════


async def list_candidates(
    session: AsyncSession, *, profile_id: uuid.UUID, status: str | None = None
) -> list[ResearcherProfileCandidate]:
    statement = select(ResearcherProfileCandidate).where(
        ResearcherProfileCandidate.profile_id == profile_id
    )
    if status:
        statement = statement.where(ResearcherProfileCandidate.status == status)
    rows = (
        await session.execute(statement.order_by(ResearcherProfileCandidate.created_at.desc()))
    ).scalars().all()
    return list(rows)


async def propose_manual_candidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    profile: ResearcherProfile,
    field_name: str,
    candidate_value: str,
    provenance: str | None,
    actor_user_id: uuid.UUID,
) -> ResearcherProfileCandidate:
    """إدخالٌ يدويّ يُراجَع لاحقًا — الخيارُ الأوّل في رحلة §3.

    ويبقى **خارج الملفّ الفعّال** حتى يؤكّده صاحبُه، تمامًا كالمستخرَج من
    سيرةٍ ذاتية. والفرقُ الوحيد أنّ مصدرَه هو نفسُه.
    """
    if field_name not in CONFIRMABLE_FIELDS:
        raise AtheraError("researcher.candidate_field_unknown", field=field_name)

    candidate = ResearcherProfileCandidate(
        tenant_id=tenant_id,
        profile_id=profile.id,
        field_name=field_name,
        candidate_value=candidate_value,
        source_type="manual",
        source_id=None,
        provenance=provenance,
        extraction_method="researcher",
        profile_state="user_declared",
        status="proposed",
    )
    session.add(candidate)
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.candidate_proposed",
        object_type="researcher_profile_candidate",
        object_id=candidate.id,
        actor_user_id=actor_user_id,
        state_after={"field_name": field_name, "source_type": "manual",
                     "profile_state": "user_declared", "status": "proposed"},
        reason="researcher proposed a profile value for their own later review",
    )
    return candidate


async def _load_candidate(
    session: AsyncSession, *, profile_id: uuid.UUID, candidate_id: uuid.UUID
) -> ResearcherProfileCandidate:
    candidate = (
        await session.execute(
            select(ResearcherProfileCandidate).where(
                ResearcherProfileCandidate.id == candidate_id,
                ResearcherProfileCandidate.profile_id == profile_id,
            )
        )
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFound("researcher.candidate_not_found")
    return candidate


async def confirm_candidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    profile: ResearcherProfile,
    candidate_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> ResearcherProfileCandidate:
    """**التأكيدُ هو الفعلُ الوحيد الذي يُدخل قيمةً في الملفّ.**

    ولا يقع إلّا بطلبٍ من إنسانٍ مصادَق، ويُكتب اسمُه ووقتُه في الصفّ نفسه —
    لا في سجلٍّ جانبيّ وحده. والقاعدةُ ترفض غيرَ ذلك.
    """
    candidate = await _load_candidate(
        session, profile_id=profile.id, candidate_id=candidate_id
    )
    if candidate.status not in _DECIDABLE_FROM:
        raise AtheraError("researcher.candidate_already_decided",
                          status=candidate.status)
    if candidate.field_name not in CONFIRMABLE_FIELDS:
        raise AtheraError("researcher.candidate_field_unknown",
                          field=candidate.field_name)

    before = getattr(profile, candidate.field_name)

    candidate.status = "confirmed"
    candidate.profile_state = "confirmed"
    candidate.decided_by = actor_user_id
    candidate.decided_at = _now()
    candidate.decision_reason = reason

    if candidate.field_name == "orcid":
        normalised = orcid_service.normalise(candidate.candidate_value)
        if normalised is None or not orcid_service.has_valid_format(normalised):
            raise AtheraError("researcher.orcid_checksum_failed")
        profile.orcid = normalised
        # **وتأكيدُ الباحثِ ليس توثيقًا خارجيًّا.** أقرّ أنّ الرقمَ رقمُه،
        # ولم يقل سجلٌّ خارجيّ ذلك — فالحالُ `user_declared` لا غير (§6).
        profile.orcid_status = orcid_service.DECLARED_STATUS
        profile.orcid_verified_at = None
        profile.orcid_source = None
    else:
        setattr(profile, candidate.field_name, candidate.candidate_value)

    _mark_provenance(
        profile, {candidate.field_name: "confirmed"},
        actor_user_id=actor_user_id, candidate_id=candidate.id,
    )
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.candidate_confirmed",
        object_type="researcher_profile_candidate",
        object_id=candidate.id,
        actor_user_id=actor_user_id,
        state_before={"field": candidate.field_name,
                      "profile_value": None if before is None else str(before)},
        state_after={"field": candidate.field_name,
                     "profile_state": "confirmed",
                     "source_type": candidate.source_type},
        reason=reason or "researcher confirmed a profile candidate (§2)",
    )
    return candidate


async def reject_candidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    profile: ResearcherProfile,
    candidate_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> ResearcherProfileCandidate:
    """**والرفضُ لا يمسّ الملفَّ الفعّال بشيء.**

    و`profile_state` يبقى كما وُلد — مستخرَجًا أو مقترَحًا — فيبقى مقروءًا
    من أين جاء هذا الذي رُفض.
    """
    candidate = await _load_candidate(
        session, profile_id=profile.id, candidate_id=candidate_id
    )
    if candidate.status not in _DECIDABLE_FROM:
        raise AtheraError("researcher.candidate_already_decided",
                          status=candidate.status)

    candidate.status = "rejected"
    candidate.decided_by = actor_user_id
    candidate.decided_at = _now()
    candidate.decision_reason = reason
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.candidate_rejected",
        object_type="researcher_profile_candidate",
        object_id=candidate.id,
        actor_user_id=actor_user_id,
        state_after={"field": candidate.field_name, "status": "rejected",
                     "profile_state": candidate.profile_state},
        reason=reason or "researcher rejected a profile candidate (§2)",
    )
    return candidate


# ═══════════════════ الأهداف والقيود ═══════════════════


async def list_goals(
    session: AsyncSession, *, profile_id: uuid.UUID
) -> list[ResearcherGoal]:
    rows = (
        await session.execute(
            select(ResearcherGoal)
            .where(ResearcherGoal.profile_id == profile_id)
            .order_by(ResearcherGoal.created_at.asc())
        )
    ).scalars().all()
    return list(rows)


async def list_constraints(
    session: AsyncSession, *, profile_id: uuid.UUID
) -> list[ResearcherConstraint]:
    rows = (
        await session.execute(
            select(ResearcherConstraint)
            .where(ResearcherConstraint.profile_id == profile_id)
            .order_by(ResearcherConstraint.created_at.asc())
        )
    ).scalars().all()
    return list(rows)


async def load_goal(
    session: AsyncSession, *, profile_id: uuid.UUID, goal_id: uuid.UUID
) -> ResearcherGoal:
    row = (
        await session.execute(
            select(ResearcherGoal).where(
                ResearcherGoal.id == goal_id, ResearcherGoal.profile_id == profile_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("researcher.goal_not_found")
    return row


async def load_constraint(
    session: AsyncSession, *, profile_id: uuid.UUID, constraint_id: uuid.UUID
) -> ResearcherConstraint:
    row = (
        await session.execute(
            select(ResearcherConstraint).where(
                ResearcherConstraint.id == constraint_id,
                ResearcherConstraint.profile_id == profile_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("researcher.constraint_not_found")
    return row


def goal_snapshot(goal: ResearcherGoal) -> dict[str, Any]:
    return {
        "id": str(goal.id),
        "goal_type": goal.goal_type,
        "target": goal.target,
        "priority": goal.priority,
        "timeframe": goal.timeframe,
        "status": goal.status,
        "researcher_confirmed": goal.researcher_confirmed,
        "notes": goal.notes,
    }


def constraint_snapshot(constraint: ResearcherConstraint) -> dict[str, Any]:
    return {
        "id": str(constraint.id),
        "constraint_type": constraint.constraint_type,
        "value": constraint.value,
        "notes": constraint.notes,
        "researcher_confirmed": constraint.researcher_confirmed,
    }
