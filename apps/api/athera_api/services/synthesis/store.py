"""كتابةُ التركيب وقراءتُه | Persisting and reading the synthesis layer.

**إعادةُ التوليد لا تمحو حكمًا.** أخطرُ ما يمكن أن يفعله زرُّ «أعد التحليل»
أن يُسقط مرشَّحًا اعتمده الباحث أمس ثم يُنشئ مكانه مرشَّحًا يشبهه: يظنّ
الباحث أن اعتماده باقٍ وهو ذهب، أو يرى فجوةً «جديدة» وقد رفضها من قبل.
فالحذفُ هنا مقصورٌ على ما **لم يقل فيه إنسانٌ شيئًا** — والمعيار عمودٌ في
القاعدة (`decided_by IS NULL`) لا نيّةٌ في الشيفرة.

**والاستعلام مقيَّدٌ بالبحث دائمًا.** لا دالّة هنا تقرأ بمعرّف الصفّ وحده:
كلّها تشترط `tenant_id` **و**`project_id` معًا. وRLS تحمي بين المستأجرين
ولا تحمي بين بحثين في مستأجرٍ واحد — وهو عطبٌ وقع في هذا المنتج من قبل،
فلا يُترك حارسُه للمفتاح الأجنبي وحده.

**ولا سطر هنا يكتب `use_state`.** قرارُ إدراج مرجعٍ فعلُ باحثٍ في شاشة
الفرز؛ وطبقةُ تركيبٍ تقلب مرجعًا إلى «مُدرَج» لتقوّي فجوةً تصنع دليلها
بنفسها.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.synthesis import (
    ContradictionCandidate,
    ContradictionSide,
    GapCandidate,
    GapCandidateSource,
    ResearchOpportunity,
    ThemeCandidate,
    ThemeCandidateSupport,
)
from .contradictions import ContradictionProposal
from .gaps import GapProposal
from .themes import ThemeProposal


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════════ الموضوعات ═════════════════════

async def replace_generated_themes(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    proposals: tuple[ThemeProposal, ...], generated_at: dt.datetime | None = None,
) -> list[ThemeCandidate]:
    """يستبدل المقترَحات التي **لم يُحكم فيها**، ويترك ما حُكم فيه كما هو."""
    moment = generated_at or _now()
    undecided = (await session.execute(
        select(ThemeCandidate.id).where(
            ThemeCandidate.tenant_id == tenant_id,
            ThemeCandidate.project_id == project_id,
            ThemeCandidate.decided_by.is_(None))
    )).scalars().all()
    if undecided:
        # السند يذهب مع صاحبه — والمفتاح المركّب في القاعدة يفعلها أيضًا،
        # وهذا صريحٌ ليقرأه من يقرأ الخدمة بلا أن يفتح الترحيل.
        await session.execute(delete(ThemeCandidateSupport).where(
            ThemeCandidateSupport.tenant_id == tenant_id,
            ThemeCandidateSupport.project_id == project_id,
            ThemeCandidateSupport.theme_id.in_(undecided)))
        await session.execute(delete(ThemeCandidate).where(
            ThemeCandidate.tenant_id == tenant_id,
            ThemeCandidate.project_id == project_id,
            ThemeCandidate.id.in_(undecided)))

    created: list[ThemeCandidate] = []
    for proposal in proposals:
        row = ThemeCandidate(
            tenant_id=tenant_id, project_id=project_id,
            label_ar=proposal.label_ar, description_ar=proposal.description_ar,
            basis=proposal.basis,
            source_scope_summary=dict(proposal.source_scope_summary),
            generation_method="deterministic", generated_at=moment,
            status="generated")
        session.add(row)
        await session.flush()
        for support in proposal.supports:
            session.add(ThemeCandidateSupport(
                tenant_id=tenant_id, project_id=project_id, theme_id=row.id,
                source_id=support.source_id, role=support.role,
                basis_field_key=support.basis_field_key,
                matrix_cell_id=support.matrix_cell_id,
                evidence_scope=support.evidence_scope))
        created.append(row)
    await session.flush()
    return created


async def list_themes(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID) -> list[ThemeCandidate]:
    return list((await session.execute(
        select(ThemeCandidate)
        .where(ThemeCandidate.tenant_id == tenant_id,
               ThemeCandidate.project_id == project_id)
        .order_by(ThemeCandidate.basis, ThemeCandidate.label_ar)
    )).scalars().all())


async def theme_supports(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         theme_ids: list[uuid.UUID]) -> list[ThemeCandidateSupport]:
    if not theme_ids:
        return []
    return list((await session.execute(
        select(ThemeCandidateSupport)
        .where(ThemeCandidateSupport.tenant_id == tenant_id,
               ThemeCandidateSupport.project_id == project_id,
               ThemeCandidateSupport.theme_id.in_(theme_ids))
        .order_by(ThemeCandidateSupport.role, ThemeCandidateSupport.basis_field_key)
    )).scalars().all())


async def theme_of(session: AsyncSession, *, tenant_id: uuid.UUID,
                   project_id: uuid.UUID,
                   theme_id: uuid.UUID) -> ThemeCandidate | None:
    """**البحث شرطٌ في القراءة لا مرشِّحٌ بعدها.**"""
    return (await session.execute(
        select(ThemeCandidate).where(
            ThemeCandidate.tenant_id == tenant_id,
            ThemeCandidate.project_id == project_id,
            ThemeCandidate.id == theme_id)
    )).scalar_one_or_none()


# ═════════════════════ التعارضات ═════════════════════

async def replace_generated_contradictions(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    proposals: tuple[ContradictionProposal, ...],
    generated_at: dt.datetime | None = None,
) -> dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID]:
    """يكتب التعارضات ويعيد خريطةَ (طرفٌ، طرف) ← معرّف الصفّ.

    والخريطة تخدم فجوةَ «أدلة متعارضة»: ترتبط بتعارضها بعينه لا بتعارضٍ
    يُبحث عنه لاحقًا بالنصّ.
    """
    moment = generated_at or _now()
    undecided = (await session.execute(
        select(ContradictionCandidate.id).where(
            ContradictionCandidate.tenant_id == tenant_id,
            ContradictionCandidate.project_id == project_id,
            ContradictionCandidate.decided_by.is_(None))
    )).scalars().all()
    if undecided:
        await session.execute(delete(ContradictionSide).where(
            ContradictionSide.tenant_id == tenant_id,
            ContradictionSide.project_id == project_id,
            ContradictionSide.contradiction_id.in_(undecided)))
        await session.execute(delete(ContradictionCandidate).where(
            ContradictionCandidate.tenant_id == tenant_id,
            ContradictionCandidate.project_id == project_id,
            ContradictionCandidate.id.in_(undecided)))

    keys: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
    for proposal in proposals:
        row = ContradictionCandidate(
            tenant_id=tenant_id, project_id=project_id,
            construct_a_ar=proposal.construct_a_ar,
            construct_b_ar=proposal.construct_b_ar,
            relationship_ar=proposal.relationship_ar,
            conflict_kind=proposal.conflict_kind,
            context_explanation_ar=proposal.context_explanation_ar,
            context_divergence=list(proposal.context_divergence),
            generation_method="deterministic", generated_at=moment,
            status="generated")
        session.add(row)
        await session.flush()
        for letter, side in (("a", proposal.side_a), ("b", proposal.side_b)):
            session.add(ContradictionSide(
                tenant_id=tenant_id, project_id=project_id,
                contradiction_id=row.id, side=letter, source_id=side.source_id,
                matrix_cell_id=side.matrix_cell_id, result_ar=side.result_ar,
                direction=side.direction, significance=side.significance,
                population_ar=side.population_ar, country_ar=side.country_ar,
                method_ar=side.method_ar, measurement_ar=side.measurement_ar,
                period_year=side.period_year, evidence_scope=side.evidence_scope))
        keys[(proposal.side_a.source_id, proposal.side_b.source_id)] = row.id
    await session.flush()
    return keys


async def list_contradictions(session: AsyncSession, *, tenant_id: uuid.UUID,
                              project_id: uuid.UUID) -> list[ContradictionCandidate]:
    return list((await session.execute(
        select(ContradictionCandidate)
        .where(ContradictionCandidate.tenant_id == tenant_id,
               ContradictionCandidate.project_id == project_id)
        .order_by(ContradictionCandidate.construct_a_ar,
                  ContradictionCandidate.created_at)
    )).scalars().all())


async def contradiction_sides(session: AsyncSession, *, tenant_id: uuid.UUID,
                              project_id: uuid.UUID,
                              contradiction_ids: list[uuid.UUID]
                              ) -> list[ContradictionSide]:
    if not contradiction_ids:
        return []
    return list((await session.execute(
        select(ContradictionSide)
        .where(ContradictionSide.tenant_id == tenant_id,
               ContradictionSide.project_id == project_id,
               ContradictionSide.contradiction_id.in_(contradiction_ids))
        .order_by(ContradictionSide.contradiction_id, ContradictionSide.side)
    )).scalars().all())


# ═════════════════════ الفجوات ═════════════════════

async def replace_generated_gaps(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    proposals: tuple[GapProposal, ...],
    contradiction_ids: dict[tuple[uuid.UUID, uuid.UUID], uuid.UUID],
    generated_at: dt.datetime | None = None,
) -> list[GapCandidate]:
    moment = generated_at or _now()
    undecided = (await session.execute(
        select(GapCandidate.id).where(
            GapCandidate.tenant_id == tenant_id,
            GapCandidate.project_id == project_id,
            GapCandidate.decided_by.is_(None))
    )).scalars().all()
    if undecided:
        await session.execute(delete(GapCandidateSource).where(
            GapCandidateSource.tenant_id == tenant_id,
            GapCandidateSource.project_id == project_id,
            GapCandidateSource.gap_id.in_(undecided)))
        await session.execute(delete(GapCandidate).where(
            GapCandidate.tenant_id == tenant_id,
            GapCandidate.project_id == project_id,
            GapCandidate.id.in_(undecided)))

    created: list[GapCandidate] = []
    for proposal in proposals:
        row = GapCandidate(
            tenant_id=tenant_id, project_id=project_id,
            gap_type=proposal.gap_type, description_ar=proposal.description_ar,
            why_suggested_ar=proposal.why_suggested_ar,
            sources_considered=proposal.sources_considered,
            search_scope=dict(proposal.search_scope),
            source_scope_distribution=dict(proposal.source_scope_distribution),
            known_limitations_ar=proposal.known_limitations_ar,
            strength=proposal.strength,
            contradiction_id=(contradiction_ids.get(proposal.contradiction_key)
                              if proposal.contradiction_key else None),
            generation_method="deterministic", generated_at=moment,
            status="generated")
        session.add(row)
        await session.flush()
        for ref in proposal.sources:
            session.add(GapCandidateSource(
                tenant_id=tenant_id, project_id=project_id, gap_id=row.id,
                source_id=ref.source_id, role=ref.role,
                matrix_cell_id=ref.matrix_cell_id,
                evidence_scope=ref.evidence_scope))
        created.append(row)
    await session.flush()
    return created


async def list_gaps(session: AsyncSession, *, tenant_id: uuid.UUID,
                    project_id: uuid.UUID) -> list[GapCandidate]:
    return list((await session.execute(
        select(GapCandidate)
        .where(GapCandidate.tenant_id == tenant_id,
               GapCandidate.project_id == project_id)
        .order_by(GapCandidate.gap_type, GapCandidate.created_at)
    )).scalars().all())


async def gap_of(session: AsyncSession, *, tenant_id: uuid.UUID,
                 project_id: uuid.UUID, gap_id: uuid.UUID) -> GapCandidate | None:
    return (await session.execute(
        select(GapCandidate).where(
            GapCandidate.tenant_id == tenant_id,
            GapCandidate.project_id == project_id,
            GapCandidate.id == gap_id)
    )).scalar_one_or_none()


async def gap_sources(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID,
                      gap_ids: list[uuid.UUID]) -> list[GapCandidateSource]:
    if not gap_ids:
        return []
    return list((await session.execute(
        select(GapCandidateSource)
        .where(GapCandidateSource.tenant_id == tenant_id,
               GapCandidateSource.project_id == project_id,
               GapCandidateSource.gap_id.in_(gap_ids))
        .order_by(GapCandidateSource.gap_id, GapCandidateSource.role)
    )).scalars().all())


# ═════════════════════ الفرص ═════════════════════

async def list_opportunities(session: AsyncSession, *, tenant_id: uuid.UUID,
                             project_id: uuid.UUID) -> list[ResearchOpportunity]:
    return list((await session.execute(
        select(ResearchOpportunity)
        .where(ResearchOpportunity.tenant_id == tenant_id,
               ResearchOpportunity.project_id == project_id)
        .order_by(ResearchOpportunity.created_at.desc())
    )).scalars().all())


async def opportunity_of(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         opportunity_id: uuid.UUID) -> ResearchOpportunity | None:
    return (await session.execute(
        select(ResearchOpportunity).where(
            ResearchOpportunity.tenant_id == tenant_id,
            ResearchOpportunity.project_id == project_id,
            ResearchOpportunity.id == opportunity_id)
    )).scalar_one_or_none()


def apply_decision(row, *, status: str, actor_id: uuid.UUID,
                   when: dt.datetime | None = None) -> dict:
    """يُسجّل قرار الباحث — **وينسبه إليه رفضًا كما اعتمادًا**.

    ويعيد الحال قبله لسجلّ التدقيق: «تغيّرت الحال» بلا ما كانت عليه لا
    يُراجَع بعد شهر.
    """
    before = {"status": row.status,
              "decided_by": str(row.decided_by) if row.decided_by else None}
    row.status = status
    row.decided_by = actor_id
    row.decided_at = when or _now()
    return before


__all__ = [
    "apply_decision",
    "contradiction_sides",
    "gap_of",
    "gap_sources",
    "list_contradictions",
    "list_gaps",
    "list_opportunities",
    "list_themes",
    "opportunity_of",
    "replace_generated_contradictions",
    "replace_generated_gaps",
    "replace_generated_themes",
    "theme_of",
    "theme_supports",
]
