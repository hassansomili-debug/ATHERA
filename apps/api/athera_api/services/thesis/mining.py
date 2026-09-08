"""تنقيبُ الفرص: تطبيقٌ واحد، ومُناديان | One mining implementation, two callers.

**ولماذا خدمةٌ لا نسخةٌ ثانية.** التنقيب يقع الآن في مسارين: تلقائيًّا عند
اكتمال الاستخراج، ويدويًّا حين يُعيد الباحثُ المحاولة. ونسختان من منطقٍ
واحد تتباعدان — يُشدَّد أحدُهما ويبقى البابُ مفتوحًا من الآخر. وهذا بعينه
ما أنتج سرَّ `SUPABASE_PROJECT_REF` المكرَّر، وعميلَي Crossref اللذين
يختلفان في قيمة التراجع الافتراضية.

فالمنطقُ هنا، والمُناديان يستدعيانه.

## حدُّ الفشل — وهو أهمُّ ما في هذا الملفّ

**فشلُ التنقيب لا يُكتب أبدًا حالَ استخراجٍ فاشلة.** الاستخراجُ نجح:
المرشّحاتُ مكتوبةٌ ومؤصَّلة، والباحثُ يقدر على مراجعتها. وإعلانُ الرسالة
`extract_failed` لأنّ خطوةً تاليةً تعثّرت **يمحو عملًا وقع فعلًا** ويقود
الباحثَ إلى إعادة استخراجٍ لا داعي لها.

فللتنقيب حالُه (`theses.mining_state`، ترحيل 0031)، وللاستخراج حالُه، ولا
يكتب أحدُهما في خانة الآخر.

## الإعادةُ بلا أثر محفوظةٌ كما كانت

القفلُ `FOR UPDATE` على صفّ الرسالة **مسؤوليةُ المُنادي**: المسارُ اليدويّ
يقفل في `_thesis_or_404`، والتلقائيّ يقفل قبل الاستدعاء. ومفتاحُ الهويّة
`(opportunity_kind, paper_kind, working_title_ar)` يمنع الصفَّ المكرَّر،
فتشغيلتان متتاليتان أو متزامنتان لا تُنتجان فرصةً مرّتين.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid
from dataclasses import replace
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.thesis import PublicationOpportunity, Thesis, ThesisResult, ThesisSection
from .. import audit
from . import aging, canonical_facts, miner

# ═════════ حالُ التنقيب — مستقلّةٌ عن حال الاستخراج ═════════

NOT_STARTED: Final = "not_started"
RUNNING: Final = "running"
COMPLETED: Final = "completed"
WITHHELD: Final = "withheld"
FAILED: Final = "failed"

STATES: Final[tuple[str, ...]] = (NOT_STARTED, RUNNING, COMPLETED, WITHHELD, FAILED)

#: أساسُ الدليل الذي يُعدّ محاولةً حقيقية — وبه يُختم ويُسجَّل «نُقِّب».
REAL_ATTEMPT: Final[frozenset[str]] = frozenset({"canonical", "legacy"})

# ═════════ أسبابُ الأثر: تصف ما وقع، لا سياسةً سابقة ═════════

_MINING_REASONS: Final[dict[str, str]] = {
    "canonical": (
        "mined from eligible canonical facts for this thesis file; eligibility is "
        "either researcher-approved with a verified memory, or auto-eligible machine "
        "extraction that passed every provenance, grounding, shape and field-threshold "
        "gate"
    ),
    "legacy": (
        "mined from legacy ThesisSection/ThesisResult evidence, used only because no "
        "mining-relevant canonical footprint (a FactCandidate whose field_key is in "
        "READ_KEYS) owns this thesis"
    ),
    "canonical_withheld": (
        "a mining-relevant canonical footprint owns this thesis but nothing was "
        "eligible; legacy fallback was intentionally suppressed so that a deliberate "
        "withholding is never silently downgraded into a legacy mining run"
    ),
    "none": (
        "no mining-relevant canonical footprint and no usable legacy evidence, so no "
        "mining attempt was made and no completion is stamped"
    ),
}


@dataclasses.dataclass(frozen=True, slots=True)
class MiningOutcome:
    created: int
    already_present: int
    withheld_for_missing_title: int
    evidence_basis: str
    outcome: str
    mining_state: str
    kinds: list[str]
    aging: aging.AgingReport
    canonical: canonical_facts.CanonicalEvidence
    title_conflict: bool


async def run(
    session: AsyncSession, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID | None,
    thesis: Thesis,
) -> MiningOutcome:
    """يُنقّب فرصَ رسالةٍ **مقفولٍ صفُّها سلفًا**، ويكتب حالَ التنقيب.

    ولا يفحص صلاحيةً ولا مِلكيّة: ذاك عملُ المُنادي، ويقع قبل القفل.
    """
    thesis_id = thesis.id
    thesis.mining_state = RUNNING
    thesis.mining_last_error = None

    # ── مصدرٌ واحد، ولا يُخلط المصدران ──
    canonical = await canonical_facts.load(
        session, tenant_id=tenant_id, thesis_id=thesis_id, file_id=thesis.file_id)

    title_conflict = False
    if canonical.has_evidence:
        # **وما كتبه الباحثُ بيده لا يُستبدل باستخراجٍ اعتُمد.**
        if canonical.approved_title:
            if thesis.title_ar is None:
                thesis.title_ar = canonical.approved_title
            elif thesis.title_ar.strip() != canonical.approved_title.strip():
                title_conflict = True
        facts = replace(canonical.facts, title=thesis.title_ar)
        evidence_basis = "canonical"
    elif canonical.has_canonical_footprint:
        # **ولا هروبَ إلى القديم حين يُحجب الحديث.**
        facts = miner.ThesisFacts(thesis_id=str(thesis_id), title=thesis.title_ar)
        evidence_basis = "canonical_withheld"
    else:
        sections = (
            await session.execute(
                select(ThesisSection).where(ThesisSection.thesis_id == thesis_id))
        ).scalars().all()
        results = (
            await session.execute(
                select(ThesisResult).where(ThesisResult.thesis_id == thesis_id))
        ).scalars().all()
        facts = miner.ThesisFacts(
            thesis_id=str(thesis_id), title=thesis.title_ar,
            questions=tuple(s.content_ar or "" for s in sections
                            if s.section_key == "questions"),
            results=tuple((str(r.id), r.label_ar) for r in results),
            variables=tuple({v for r in results for v in (r.variables or [])}),
            sample_ids=tuple({str(thesis_id)}),
            published_result_ids=tuple(str(r.id) for r in results if r.is_published),
        )
        evidence_basis = "legacy" if (sections or results) else "none"

    drafts = miner.mine(facts)
    withheld = miner.withheld_for_missing_title(facts)

    report = aging.compute(
        as_of=dt.date.today(), data_collected_on=thesis.data_collected_on,
        latest_cited_year=(thesis.defended_on.year if thesis.defended_on else None),
        literature_update_threshold_years=3, data_age_review_threshold_years=5,
    )

    # **ما هو قائمٌ الآن على هذه الرسالة** — والعزل مكتوبٌ في الشرط.
    present = {
        (kind, paper, title)
        for kind, paper, title in (await session.execute(
            select(PublicationOpportunity.opportunity_kind,
                   PublicationOpportunity.paper_kind,
                   PublicationOpportunity.working_title_ar)
            .where(PublicationOpportunity.tenant_id == tenant_id,
                   PublicationOpportunity.thesis_id == thesis_id)
        )).all()
    }

    created = 0
    already = 0
    for draft in drafts:
        key = (draft.opportunity_kind, draft.paper_kind, draft.working_title_ar)
        if key in present:
            already += 1
            continue
        present.add(key)
        session.add(PublicationOpportunity(
            tenant_id=tenant_id, thesis_id=thesis_id,
            opportunity_kind=draft.opportunity_kind, paper_kind=draft.paper_kind,
            working_title_ar=draft.working_title_ar,
            research_question_ar=draft.research_question_ar,
            sample_refs=draft.sample_refs, variable_refs=draft.variable_refs,
            result_refs=draft.result_refs,
            published_output_refs=draft.published_output_refs,
            data_age_years=report.data_age_years,
            literature_age_years=report.literature_age_years,
            status="discovered",
        ))
        created += 1

    # **والختمُ لمحاولةٍ حقيقية على دليلٍ مؤهَّل وحدها.**
    if evidence_basis in REAL_ATTEMPT:
        thesis.opportunities_mined_at = dt.datetime.now(dt.UTC)

    if created:
        outcome = "opportunities_created"
    elif already:
        outcome = "already_present"
    elif canonical.facts_withheld_for_conflict:
        outcome = "evidence_withheld_for_conflict"
    elif evidence_basis in {"none", "canonical_withheld"}:
        outcome = "no_eligible_evidence"
    elif withheld:
        outcome = "withheld_for_missing_title"
    elif evidence_basis == "legacy":
        outcome = "legacy_evidence_but_no_opportunity"
    else:
        outcome = "eligible_evidence_but_no_opportunity"

    # **وحالُ التنقيب تصف التنقيب.** «حُجب» ليست «فشل»: الأولى قرارُ سياسةٍ
    # وقع كما يجب، والثانية عطبٌ يستدعي النظر.
    if evidence_basis in REAL_ATTEMPT:
        thesis.mining_state = COMPLETED
    elif canonical.has_canonical_footprint:
        thesis.mining_state = WITHHELD
    else:
        thesis.mining_state = NOT_STARTED

    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id,
        action=("thesis.opportunities_mined" if evidence_basis in REAL_ATTEMPT
                else "thesis.opportunity_scan_skipped_no_evidence"),
        object_type="thesis", object_id=thesis_id, actor_user_id=actor_user_id,
        state_after={
            "created": created, "already_present": already,
            "withheld_for_missing_title": withheld,
            "kinds": sorted({d.opportunity_kind for d in drafts}),
            "data_age_years": report.data_age_years,
            "literature_age_years": report.literature_age_years,
            "evidence_basis": evidence_basis,
            "eligible_facts_used": canonical.eligible_facts_used,
            "approved_facts_used": canonical.approved_verified_used,
            "processing_scope": canonical.processing_scope,
            "classification_counts": canonical.counts,
            "conflicts_detected": canonical.conflicts_detected,
            "facts_withheld_for_conflict": canonical.facts_withheld_for_conflict,
            "exclusion_reasons": canonical.reasons,
            "outcome": outcome,
            "mining_state": thesis.mining_state,
        },
        reason=_MINING_REASONS[evidence_basis],
    )

    if title_conflict:
        await audit.record(
            session, tenant_id=tenant_id,
            action="thesis.title_conflict_preserved",
            object_type="thesis", object_id=thesis_id, actor_user_id=actor_user_id,
            state_after={
                "existing_title_preserved": True,
                "approved_title_fact_id": str(canonical.approved_title_fact_id),
            },
            reason="an approved extracted title differs from the title already on the "
                   "thesis; the existing title is kept and never silently replaced",
        )

    return MiningOutcome(
        created=created, already_present=already, withheld_for_missing_title=withheld,
        evidence_basis=evidence_basis, outcome=outcome,
        mining_state=thesis.mining_state,
        kinds=sorted({d.opportunity_kind for d in drafts}),
        aging=report, canonical=canonical, title_conflict=title_conflict,
    )
