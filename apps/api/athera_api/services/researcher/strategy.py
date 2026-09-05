"""الاستراتيجيّةُ البحثيّة | Research strategy versions (§4، §7).

**والمعتمَدُ لا يُعدَّل.** تغييرُ استراتيجيّةٍ معتمَدة يُنشئ إصدارًا تاليًا
ويُحيل الأوّل `superseded`. واللقطاتُ تُخزَّن مع كلّ إصدار لأنّ الأهدافَ
تتبدّل، وقرارٌ اتُّخذ على حالٍ سابقة يُقرأ خطأً إن قيس بحالٍ لاحقة.

**والناقصُ يُقال دائمًا** (§7): كلُّ إصدارٍ يحمل قائمةَ ما لا تعرفه المنصّة
عن هذا الباحث. وتوصيةٌ تُخفي ما لا تعرفه أسوأ من صمت.

**ولا رقم.** لا نسبةَ جاهزية، ولا احتمالَ قَبول، ولا درجةَ نجاح — لا في
عمود، ولا في عقدٍ، ولا في تعليل.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.research import ResearcherProfile
from ...models.researcher_intelligence import ResearchStrategy
from .. import audit
from . import profile as profile_service

#: مفاتيحُ «الناقص» — تُترجَم عند حدّ الـHTTP، ولا تُصاغ نصًّا هنا.
MISSING_PROFILE_FIELD: Final = "profile.{field}"
MISSING_NO_CONFIRMED_GOAL: Final = "goals.none_confirmed"
MISSING_NO_GOALS: Final = "goals.none"
MISSING_NO_CONSTRAINTS: Final = "constraints.none"
MISSING_UNCONFIRMED_CONSTRAINT: Final = "constraints.unconfirmed"
MISSING_ORCID_UNVERIFIED: Final = "orcid.not_externally_verified"

#: الحقولُ التي يُقال عن غيابها «غيرُ معروف» — لا «لا قيد» ولا «لا مؤسّسة».
_EXPECTED_PROFILE_FIELDS: Final = (
    "institution_ar", "current_rank", "target_rank",
    "primary_field_ar", "preferred_manuscript_language",
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def assemble_missing_information(
    profile: ResearcherProfile, goals: list, constraints: list
) -> list[str]:
    """ما لا تعرفه المنصّةُ عن هذا الباحث — يُقال، ولا يُملأ بتخمين (§7)."""
    missing: list[str] = []

    for field in _EXPECTED_PROFILE_FIELDS:
        if not getattr(profile, field, None):
            missing.append(MISSING_PROFILE_FIELD.format(field=field))

    # **والصيغةُ الصحيحة ليست توثيقًا** — فرقٌ يُقال هنا صراحةً بدل أن
    # يُقرأ الرقمُ الصحيحُ سندًا.
    if profile.orcid_status != "externally_verified":
        missing.append(MISSING_ORCID_UNVERIFIED)

    if not goals:
        missing.append(MISSING_NO_GOALS)
    elif not any(goal.researcher_confirmed for goal in goals):
        missing.append(MISSING_NO_CONFIRMED_GOAL)

    if not constraints:
        # **غيابُ القيد «غيرُ معروف»، لا «لا قيد»** (§4).
        missing.append(MISSING_NO_CONSTRAINTS)
    elif not all(item.researcher_confirmed for item in constraints):
        missing.append(MISSING_UNCONFIRMED_CONSTRAINT)

    return missing


async def list_versions(
    session: AsyncSession, *, profile_id: uuid.UUID
) -> list[ResearchStrategy]:
    rows = (
        await session.execute(
            select(ResearchStrategy)
            .where(ResearchStrategy.profile_id == profile_id)
            .order_by(ResearchStrategy.strategy_version.desc())
        )
    ).scalars().all()
    return list(rows)


async def load(
    session: AsyncSession, *, profile_id: uuid.UUID, strategy_id: uuid.UUID
) -> ResearchStrategy:
    row = (
        await session.execute(
            select(ResearchStrategy).where(
                ResearchStrategy.id == strategy_id,
                ResearchStrategy.profile_id == profile_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("researcher.strategy_not_found")
    return row


async def create_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    profile: ResearcherProfile,
    actor_user_id: uuid.UUID,
    rationale_ar: str | None = None,
    rationale_en: str | None = None,
) -> ResearchStrategy:
    """يُنشئ الإصدارَ التالي من لقطةِ الملفّ والأهداف والقيود **الآن**.

    ولا يُعدَّل إصدارٌ قائم بحال: الرقمُ يزيد، واللقطةُ تُثبَّت، والمعتمَدُ
    السابق يُحال `superseded` — فيبقى مقروءًا على أيّ حالٍ اتُّخذ قرارُه.
    """
    goals = await profile_service.list_goals(session, profile_id=profile.id)
    constraints = await profile_service.list_constraints(session, profile_id=profile.id)

    highest = (
        await session.execute(
            select(func.max(ResearchStrategy.strategy_version)).where(
                ResearchStrategy.profile_id == profile.id
            )
        )
    ).scalar_one()
    next_version = (highest or 0) + 1

    strategy = ResearchStrategy(
        tenant_id=tenant_id,
        profile_id=profile.id,
        strategy_version=next_version,
        generated_at=_now(),
        status="draft",
        rationale_ar=rationale_ar,
        rationale_en=rationale_en,
        missing_information=assemble_missing_information(profile, goals, constraints),
        profile_snapshot=profile_service.snapshot(profile),
        goals_snapshot=[profile_service.goal_snapshot(goal) for goal in goals],
        constraints_snapshot=[
            profile_service.constraint_snapshot(item) for item in constraints
        ],
    )
    session.add(strategy)
    await session.flush()

    # **والمعتمَدُ السابق يُحال، ولا يُمحى ولا يُعدَّل.** والمُشغِّل في
    # القاعدة يسمح بهذا الانتقال وحده على صفٍّ معتمَد.
    previous = (
        await session.execute(
            select(ResearchStrategy).where(
                ResearchStrategy.profile_id == profile.id,
                ResearchStrategy.status == "approved",
            )
        )
    ).scalars().all()
    for old in previous:
        old.status = "superseded"
        old.superseded_by = strategy.id
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.strategy_version_created",
        object_type="research_strategy",
        object_id=strategy.id,
        actor_user_id=actor_user_id,
        state_after={"strategy_version": str(next_version), "status": "draft",
                     "superseded": str(len(previous))},
        reason="a change to an approved strategy creates the next version (§4)",
    )
    return strategy


async def approve(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    profile: ResearcherProfile,
    strategy_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> ResearchStrategy:
    """اعتمادٌ منسوبٌ إلى صاحبه ووقته — وبعده لا يُعدَّل الصفّ."""
    strategy = await load(session, profile_id=profile.id, strategy_id=strategy_id)
    if strategy.status not in ("draft", "needs_review"):
        raise AtheraError("researcher.strategy_not_approvable", status=strategy.status)

    strategy.status = "approved"
    strategy.approved_at = _now()
    strategy.approved_by = actor_user_id
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="researcher.strategy_approved",
        object_type="research_strategy",
        object_id=strategy.id,
        actor_user_id=actor_user_id,
        state_after={"strategy_version": str(strategy.strategy_version),
                     "status": "approved"},
        reason=reason or "researcher approved this strategy version (§4)",
    )
    return strategy
