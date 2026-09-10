"""رحلةُ الرسالة إلى ورقة | The thesis-to-paper journey (AI Journey V1).

**الحالُ تُشتقّ من صفوفٍ قائمة، ولا نسبةَ تُخترع.** «٦٠٪ مكتمل» رقمٌ بلا
قياسٍ خلفه، والباحثُ يقرؤه وعدًا. فالرحلةُ حالٌ مسمّاة، كلُّ واحدةٍ منها
واقعةٌ في القاعدة يمكن الإشارة إليها.

## ولماذا القلبُ دالّاتٌ صافية

لا PostgreSQL على جهاز التطوير، ففحصٌ يحتاج قاعدةً لا يُشغَّل. فالقرارُ
كلُّه — اشتقاقُ الحال، والبوّابات، ورفضُ المراجع غير القابلة للحلّ — يقع في
دالّاتٍ صافية على بياناتٍ عادية (`JourneyFacts`)، والطبقةُ غير الصافية
تقرأ الصفوفَ وتبني تلك البيانات. فما يُفحص هنا يُفحص فعلًا.

## والحدُّ الذي لا يلين

نموذجٌ يعيد مرجعَ دليلٍ لا يردّ إلى صفٍّ حقيقيّ: **يُرفض ذلك العنصر**. لا
يُصلَح، ولا يُستبدل بمرجعٍ معقول، ولا يمرّ بتحذير. وهو الفرقُ بين مساعدٍ
بحثيّ وآلةِ اختلاق — وأكثرُ القواعد عرضةً للانحناء حين يُراد لعرضٍ أن ينجح.
"""
from __future__ import annotations

import dataclasses
import uuid
from typing import Final

# ═════════════════ ١. الحالاتُ السبع عشرة ═════════════════

UPLOADED: Final = "uploaded"
EXTRACTING: Final = "extracting"
ANALYSED: Final = "analysed"
OPPORTUNITIES_READY: Final = "opportunities_ready"
RESEARCHER_DECISION_REQUIRED: Final = "researcher_decision_required"
RIGHTS_REQUIRED: Final = "rights_required"
OVERLAP_REVIEW_REQUIRED: Final = "overlap_review_required"
PROJECT_CREATED: Final = "project_created"
THREAD_READY: Final = "thread_ready"
OUTLINE_READY: Final = "outline_ready"
MANUSCRIPT_CREATED: Final = "manuscript_created"
DRAFTING: Final = "drafting"
DRAFT_READY: Final = "draft_ready"
LITERATURE_PENDING: Final = "literature_pending"
READY_FOR_PAPER_STUDIO: Final = "ready_for_paper_studio"
AWAITING_AI_CONSENT: Final = "awaiting_ai_consent"
FAILED: Final = "failed"

STATES: Final[tuple[str, ...]] = (
    UPLOADED, EXTRACTING, ANALYSED, OPPORTUNITIES_READY,
    RESEARCHER_DECISION_REQUIRED, RIGHTS_REQUIRED, OVERLAP_REVIEW_REQUIRED,
    PROJECT_CREATED, THREAD_READY, OUTLINE_READY, MANUSCRIPT_CREATED,
    DRAFTING, DRAFT_READY, LITERATURE_PENDING, READY_FOR_PAPER_STUDIO,
    AWAITING_AI_CONSENT, FAILED,
)

#: أسبابُ التوقّف — رموزٌ تقرؤها الآلةُ وتترجمها الشاشة.
BLOCK_NO_CONSENT: Final = "ai_consent_required"
BLOCK_NO_SELECTION: Final = "researcher_selection_required"
BLOCK_OVERLAP: Final = "overlap_unresolved"
BLOCK_RIGHTS: Final = "rights_gate_not_passed"
BLOCK_NO_OPPORTUNITY: Final = "no_opportunity_yet"
BLOCK_EXTRACTION_FAILED: Final = "extraction_failed"


@dataclasses.dataclass(frozen=True, slots=True)
class JourneyFacts:
    """وقائعُ الرحلة — **بياناتٌ عادية، لا ORM ولا جلسة**.

    تعبر حدَّ المعاملة، فتُفحص كما هي بلا قاعدة بيانات.
    """

    processing_state: str
    extraction_failed: bool = False
    opportunities: int = 0
    selected_opportunity: bool = False
    overlap_unresolved: int = 0
    rights_passed: bool = False
    ai_consent_granted: bool = False
    project_exists: bool = False
    thread_ready: bool = False
    outline_exists: bool = False
    manuscript_exists: bool = False
    sections_drafted: int = 0
    sections_expected: int = 0
    literature_pending: bool = False


# ═════════════════ ٢. اشتقاقُ الحال — دالّةٌ صافية ═════════════════

_IN_FLIGHT: Final[frozenset[str]] = frozenset({"queued", "parsing", "extracting"})
_ANALYSED: Final[frozenset[str]] = frozenset({"ready_for_review", "completed"})


def derive_state(facts: JourneyFacts) -> str:
    """الحالُ الواحدة التي تصف الرحلةَ الآن — **وكلُّها واقعةٌ في القاعدة**.

    والترتيبُ من الأبعد إلى الأقرب: ما بلغته الرحلةُ فعلًا يسبق ما ينتظرها.
    """
    if facts.extraction_failed:
        return FAILED
    if facts.manuscript_exists:
        if facts.literature_pending:
            return LITERATURE_PENDING
        if facts.sections_expected and facts.sections_drafted >= facts.sections_expected:
            return READY_FOR_PAPER_STUDIO
        if facts.sections_drafted:
            return DRAFTING
        return MANUSCRIPT_CREATED
    if facts.outline_exists:
        return OUTLINE_READY
    if facts.thread_ready:
        return THREAD_READY
    if facts.project_exists:
        return PROJECT_CREATED

    # ── ما قبل المشروع: بوّاباتٌ تُقرأ بترتيبها ──
    if facts.selected_opportunity:
        if facts.overlap_unresolved:
            return OVERLAP_REVIEW_REQUIRED
        if not facts.rights_passed:
            return RIGHTS_REQUIRED
        # **والإذنُ لا يُمنح تلقائيًّا.** بلا إذنٍ تقف الرحلةُ هنا وتُسمّي
        # ما ينقصها، ولا يُستدعى نموذجٌ أصلًا.
        if not facts.ai_consent_granted:
            return AWAITING_AI_CONSENT
        return OPPORTUNITIES_READY
    if facts.opportunities:
        return RESEARCHER_DECISION_REQUIRED
    if facts.processing_state in _ANALYSED:
        return ANALYSED
    if facts.processing_state in _IN_FLIGHT:
        return EXTRACTING
    return UPLOADED


def blocking_reasons(facts: JourneyFacts) -> tuple[str, ...]:
    """ما يمنع التقدّم الآن — **رموزٌ لا نثر**، وقد تجتمع."""
    reasons: list[str] = []
    if facts.extraction_failed:
        reasons.append(BLOCK_EXTRACTION_FAILED)
    if not facts.opportunities:
        reasons.append(BLOCK_NO_OPPORTUNITY)
    elif not facts.selected_opportunity:
        reasons.append(BLOCK_NO_SELECTION)
    if facts.selected_opportunity and facts.overlap_unresolved:
        reasons.append(BLOCK_OVERLAP)
    if facts.selected_opportunity and not facts.rights_passed:
        reasons.append(BLOCK_RIGHTS)
    if facts.selected_opportunity and not facts.ai_consent_granted:
        reasons.append(BLOCK_NO_CONSENT)
    return tuple(reasons)


def can_build_paper(facts: JourneyFacts) -> bool:
    """**البوّاباتُ كلُّها، ولا واحدةَ تُتخطّى.**"""
    return not blocking_reasons(facts)


# ═════════════════ ٣. الحدُّ الذي لا يلين: مرجعٌ لا يُحلّ يُرفض ═════════════════


def reference_resolves(ref: object, known_ids: frozenset[str]) -> bool:
    """أيردّ هذا المرجعُ إلى صفٍّ حقيقيّ؟ — دالّةٌ صافية على نصوص."""
    return isinstance(ref, str) and bool(ref) and ref in known_ids


def reject_unresolvable(elements, known_ids, *, refs_of):
    """يفصل ما يُحلّ عمّا لا يُحلّ — **ولا يُصلح شيئًا ولا يستبدله**.

    يعيد `(kept, rejected)`. والمرفوضُ يُطرح ويُسجَّل عددًا؛ ولا يُعاد
    بناؤه بمرجعٍ «معقول»، فذاك اختلاقٌ بخطوةٍ إضافية.

    **وعنصرٌ بلا مرجعٍ واحد يُرفض أيضًا**: دعوى بلا إسنادٍ ليست دليلًا،
    وقبولُها يجعل الفراغَ بابًا.
    """
    known = frozenset(known_ids)
    kept, rejected = [], []
    for element in elements:
        refs = list(refs_of(element))
        if refs and all(reference_resolves(r, known) for r in refs):
            kept.append(element)
        else:
            rejected.append(element)
    return kept, rejected


# ═════════════════ ٤. الطبقةُ غير الصافية: قراءةُ الوقائع ═════════════════


async def load_facts(session, *, tenant_id: uuid.UUID, thesis) -> JourneyFacts:
    """يقرأ صفوفَ الرحلة ويبني `JourneyFacts` — **قراءةٌ فقط**.

    ولا نداءَ نموذجٍ هنا ولا معاملةٌ تمتدّ عبره: القراءةُ تُغلق قبل أن
    يبدأ أيُّ عملٍ خارجيّ. (درسُ تخاصم سلسلة التدقيق.)
    """
    from sqlalchemy import func, select

    from ...models.planning import ManuscriptOutline
    from ...models.publishing import Manuscript
    from ...models.thesis import OpportunityOverlapScore, PublicationOpportunity
    from . import processing

    opportunities = (await session.execute(
        select(PublicationOpportunity)
        .where(PublicationOpportunity.tenant_id == tenant_id,
               PublicationOpportunity.thesis_id == thesis.id)
    )).scalars().all()

    selected = [o for o in opportunities
                if o.status in {"ready_to_submit", "converted"} or o.project_id]
    project_ids = [o.project_id for o in selected if o.project_id]

    unresolved = 0
    if selected:
        unresolved = (await session.execute(
            select(func.count(OpportunityOverlapScore.id)).where(
                OpportunityOverlapScore.salami_alert.is_(True),
                OpportunityOverlapScore.resolution.is_(None),
                OpportunityOverlapScore.left_opportunity_id.in_([o.id for o in selected]),
            )
        )).scalar_one()

    outline_exists = manuscript_exists = False
    if project_ids:
        outline_exists = bool((await session.execute(
            select(func.count(ManuscriptOutline.id))
            .where(ManuscriptOutline.tenant_id == tenant_id,
                   ManuscriptOutline.project_id.in_(project_ids))
        )).scalar_one())
        manuscript_exists = bool((await session.execute(
            select(func.count(Manuscript.id))
            .where(Manuscript.tenant_id == tenant_id,
                   Manuscript.project_id.in_(project_ids))
        )).scalar_one())

    return JourneyFacts(
        processing_state=thesis.processing_state,
        extraction_failed=thesis.processing_state == processing.FAILED,
        opportunities=len(opportunities),
        selected_opportunity=bool(selected),
        overlap_unresolved=int(unresolved),
        # **البوّابتان تُقرآن من صفوفهما، ولا تُفترض واحدةٌ منهما.**
        rights_passed=any(o.status in {"ready_to_submit", "converted"} for o in selected),
        project_exists=bool(project_ids),
        outline_exists=outline_exists,
        manuscript_exists=manuscript_exists,
    )
