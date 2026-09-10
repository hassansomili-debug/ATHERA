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

# ═════════════════ ١. الحالاتُ السّتَّ عشرة ═════════════════
#
# **ولا مفردةَ لا تُصدَر.** كانت `draft_ready` معلَنةً في المفردات ومرسومةً
# في الشاشة، و`derive_state` لا تعيدها في أيّ فرع — مفردةٌ ميّتة نجت لأنّ
# الفحص كان يقارن مجموعتين متطابقتين كلتاهما تحملها. فتقاعدت، وحلّ محلَّ
# ذلك الفحصِ فحصُ **بلوغ**: كلُّ حالٍ في `STATES` تعيدها الدالّةُ فعلًا.

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
LITERATURE_PENDING: Final = "literature_pending"
READY_FOR_PAPER_STUDIO: Final = "ready_for_paper_studio"
AWAITING_AI_CONSENT: Final = "awaiting_ai_consent"
FAILED: Final = "failed"

STATES: Final[tuple[str, ...]] = (
    UPLOADED, EXTRACTING, ANALYSED, OPPORTUNITIES_READY,
    RESEARCHER_DECISION_REQUIRED, RIGHTS_REQUIRED, OVERLAP_REVIEW_REQUIRED,
    PROJECT_CREATED, THREAD_READY, OUTLINE_READY, MANUSCRIPT_CREATED,
    DRAFTING, LITERATURE_PENDING, READY_FOR_PAPER_STUDIO,
    AWAITING_AI_CONSENT, FAILED,
)

#: أسبابُ التوقّف — رموزٌ تقرؤها الآلةُ وتترجمها الشاشة.
BLOCK_NO_CONSENT: Final = "ai_consent_required"
#: **أُذن ثمّ تغيّرت الأدلّة.** وليست رفضًا — الباحثُ لم يرجع عن شيء — لكنّها
#: ليست إذنًا للّقطة الجديدة. وإرسالُها تحت إذنٍ سابقٍ إرسالُ ما لم يره
#: صاحبُ القرار.
BLOCK_STALE_CONSENT: Final = "ai_consent_stale"
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
        # **وترتيبُ الخطوات هو ترتيبُ الفحص**: بناءُ الورقة (٤) قبل تحديث
        # الأدبيات (٥) قبل الاستوديو (٦). وكان `literature_pending` يُفحص
        # أوّلًا، فمخطوطةٌ لم يُكتب فيها حرفٌ بعدُ تُعرض عند «تحديث
        # الأدبيات» — خطوةٌ تُقفز وخطوةٌ تُعلَن قبل أوانها.
        drafted_out = bool(facts.sections_expected) and (
            facts.sections_drafted >= facts.sections_expected)
        if drafted_out:
            # **والأدبياتُ حدٌّ حقيقيّ لا زينة**: مسوّدةٌ تمّت أقسامُها لا
            # تُعلَن جاهزةً للاستوديو وسجلُّ الأدبيات لم يُراجَع بعد (§14).
            return LITERATURE_PENDING if facts.literature_pending else READY_FOR_PAPER_STUDIO
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


#: **قرارُ الباحث محلُّه `planning_status`** — وهو عمودٌ أُفرد عمدًا عن
#: `status` (انظر `models/thesis.py`): الأوّل «أهذه هي الورقة التي أريدها؟»
#: والثاني دورةُ إنتاج ورقة. وقراءةُ الاختيار من الثاني تخلطهما.
SELECTED: Final = "selected"

#: واعتمادُ الحقوق والتأليف (GT1) يستلزم الاختيار ولا يُناقضه: لا يعتمد
#: باحثٌ تأليفَ ورقةٍ لم يخترها. فتُقبل شهادتُه على الاختيار للصفوف التي
#: سبقت إفرادَ العمود — **ولا تُقرأ منها الحقوقُ**، تلك تُقرأ من ختمها.
_ADVANCED: Final[frozenset[str]] = frozenset({"ready_to_submit", "converted"})


def _is_selected(opportunity) -> bool:
    return (opportunity.planning_status == SELECTED
            or opportunity.status in _ADVANCED)


def _rights_passed(opportunity) -> bool:
    """**ختمُ البوّابة نفسه، لا حالٌ تُشبهه.**

    `rights.approve_gate` هي الباب الوحيد، وهي تكتب الختمين معًا. فتُقرأ
    الحقوقُ منهما — وكانت تُقرأ من `status in {ready_to_submit, converted}`،
    وهو الشرطُ الذي يُقرأ منه الاختيارُ أيضًا. فصارت البوّابتان شرطًا
    واحدًا: `rights_required` لا تقع أبدًا، وخطوةُ «الحقوق والتأليف» لا
    تكون الخطوةَ الحاليّة في أيّ لحظة من الرحلة.
    """
    return (opportunity.rights_approved_at is not None
            and opportunity.authorship_approved_at is not None)


async def load_facts(session, *, tenant_id: uuid.UUID, thesis) -> JourneyFacts:
    """يقرأ صفوفَ الرحلة ويبني `JourneyFacts` — **قراءةٌ فقط**.

    ولا نداءَ نموذجٍ هنا ولا معاملةٌ تمتدّ عبره: القراءةُ تُغلق قبل أن
    يبدأ أيُّ عملٍ خارجيّ. (درسُ تخاصم سلسلة التدقيق.)

    **وكلُّ حقلٍ في `JourneyFacts` يُملأ من صفّه.** حقلٌ يبقى على قيمته
    الافتراضية يجعل كلَّ حالٍ تقوم عليه غيرَ بالغة: بقيت `thread_ready`
    و`sections_drafted` و`sections_expected` و`literature_pending` فارغةً،
    فتجمّدت الرحلةُ عند «أُنشئت المخطوطة» مهما كُتب فيها، وثلاثٌ من ستِّ
    خطواتٍ لم تكن لتُضاء أبدًا.
    """
    from sqlalchemy import func, select

    from ...models.golden_thread import ThreadElement
    from ...models.planning import ManuscriptOutline
    from ...models.publishing import Manuscript, ManuscriptSection, ManuscriptVersion
    from ...models.thesis import OpportunityOverlapScore, PublicationOpportunity
    from ..publishing.drafting import policy
    from . import processing

    opportunities = (await session.execute(
        select(PublicationOpportunity)
        .where(PublicationOpportunity.tenant_id == tenant_id,
               PublicationOpportunity.thesis_id == thesis.id)
    )).scalars().all()

    selected = [o for o in opportunities if _is_selected(o)]
    project_ids = [o.project_id or o.converted_project_id for o in selected
                   if (o.project_id or o.converted_project_id)]

    unresolved = 0
    if selected:
        unresolved = (await session.execute(
            select(func.count(OpportunityOverlapScore.id)).where(
                OpportunityOverlapScore.salami_alert.is_(True),
                OpportunityOverlapScore.resolution.is_(None),
                OpportunityOverlapScore.left_opportunity_id.in_([o.id for o in selected]),
            )
        )).scalar_one()

    thread_ready = outline_exists = False
    manuscript = None
    if project_ids:
        thread_ready = bool((await session.execute(
            select(func.count(ThreadElement.id))
            .where(ThreadElement.tenant_id == tenant_id,
                   ThreadElement.project_id.in_(project_ids))
        )).scalar_one())
        outline_exists = bool((await session.execute(
            select(func.count(ManuscriptOutline.id))
            .where(ManuscriptOutline.tenant_id == tenant_id,
                   ManuscriptOutline.project_id.in_(project_ids))
        )).scalar_one())
        manuscript = (await session.execute(
            select(Manuscript)
            .where(Manuscript.tenant_id == tenant_id,
                   Manuscript.project_id.in_(project_ids))
            .order_by(Manuscript.created_at.desc()).limit(1)
        )).scalar_one_or_none()

    # ── ما كُتب فعلًا في المخطوطة، وما تنتظره ──
    #
    # **وسلطةُ الأقسام واحدة**: `drafting/policy.py` تقول ما هو مفعَّل،
    # فيُسأل منها العددُ المنتظَر ولا يُكتب رقمٌ بجانبها ينحرف عنها.
    sections_drafted = sections_expected = 0
    if manuscript is not None:
        sections_expected = len(policy.ENABLED_SECTIONS)
        version_id = manuscript.current_version_id
        if version_id is None:
            version_id = (await session.execute(
                select(ManuscriptVersion.id)
                .where(ManuscriptVersion.tenant_id == tenant_id,
                       ManuscriptVersion.manuscript_id == manuscript.id)
                .order_by(ManuscriptVersion.created_at.desc()).limit(1)
            )).scalar_one_or_none()
        if version_id is not None:
            sections_drafted = int((await session.execute(
                select(func.count(ManuscriptSection.id))
                .where(ManuscriptSection.tenant_id == tenant_id,
                       ManuscriptSection.version_id == version_id,
                       ManuscriptSection.section_key.in_(policy.ENABLED_SECTIONS))
            )).scalar_one())

    # ── الأدبيات: حالٌ في الصفّ، لا استنتاجٌ من السياسة ──
    #
    # سياسةُ الأقسام تقول إنّ المقدّمة والإطار والمناقشة تحتاج أدبيات، وذلك
    # ثابتٌ لكلّ ورقة. فلو قامت الحالُ عليه لكانت «تحديثُ الأدبيات» قائمةً
    # أبدًا وابتلعت ما بعدها. والصفُّ هو `literature_validation_status`
    # على الفرصة المختارة — وهو ما يتحرّك حين يُفتح سجلّ الأدبيات (S5F).
    literature_pending = any(
        o.literature_validation_status == "pending" for o in selected)

    return JourneyFacts(
        processing_state=thesis.processing_state,
        extraction_failed=thesis.processing_state == processing.FAILED,
        opportunities=len(opportunities),
        selected_opportunity=bool(selected),
        overlap_unresolved=int(unresolved),
        # **البوّابتان تُقرآن من صفَّيهما، ولا تُفترض واحدةٌ منهما.**
        rights_passed=any(_rights_passed(o) for o in selected),
        project_exists=bool(project_ids),
        thread_ready=thread_ready,
        outline_exists=outline_exists,
        manuscript_exists=manuscript is not None,
        sections_drafted=sections_drafted,
        sections_expected=sections_expected,
        literature_pending=literature_pending,
    )


# ═════════════════ ٥. الأثرُ القائم: قرارُ إعادة الاستعمال ═════════════════

#: الأربعةُ التي تُبنى مرّةً وتُعاد بعدها.
ARTIFACTS: Final[tuple[str, ...]] = ("project", "thread", "outline", "manuscript")

#: ما تبنيه هذه الشريحةُ حتميًّا. و«الخيط» ليس منها: بناؤه يقوم على أدلّةٍ
#: ونداءِ نموذج، وذاك عملُ الشريحة التالية. فيُرصد قائمًا ويُعلَن منتظَرًا،
#: **ولا يُخترع صفٌّ ليُقال إنّه اكتمل**.
DETERMINISTIC_ARTIFACTS: Final[tuple[str, ...]] = ("project", "outline", "manuscript")


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactSet:
    """ما هو قائمٌ الآن لهذه الفرصة — **معرّفاتٌ لا صفوف**."""

    project_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    outline_id: uuid.UUID | None = None
    manuscript_id: uuid.UUID | None = None

    def identifier(self, name: str) -> uuid.UUID | None:
        return getattr(self, f"{name}_id")


def to_create(existing: ArtifactSet) -> tuple[str, ...]:
    """ما ينقص فيجب إنشاؤه — **وما وُجد يُعاد استعمالُه**.

    قرارٌ على بياناتٍ عادية، فيُفحص بلا قاعدة بيانات. وإعادةُ التشغيل على
    أثرٍ كامل تُعيد `()`: لا صفَّ ثانيًا لأيٍّ من الأربعة.
    """
    return tuple(name for name in ARTIFACTS if existing.identifier(name) is None)


def to_reuse(existing: ArtifactSet) -> tuple[str, ...]:
    return tuple(name for name in ARTIFACTS if existing.identifier(name) is not None)


def reuses_everything(existing: ArtifactSet) -> bool:
    """إعادةُ تشغيلٍ لا تُنشئ شيئًا — وهي دعوى التكرار الآمن."""
    return not to_create(existing)


class JourneyBlocked(Exception):
    """بوّابةٌ لم تُجتَز — **ومعها أسبابُها رموزًا لا نثرًا**."""

    def __init__(self, reasons):
        self.reasons = tuple(reasons)
        super().__init__(",".join(self.reasons))


@dataclasses.dataclass(frozen=True, slots=True)
class BuildOutcome:
    """حصيلةُ بناءِ ورقة — وما أُنشئ وما أُعيد استعمالُه، مسمَّيَين."""

    project_id: uuid.UUID
    outline_id: uuid.UUID
    manuscript_id: uuid.UUID
    thread_id: uuid.UUID | None
    created: tuple[str, ...]
    reused: tuple[str, ...]
    pending: tuple[str, ...]
    state: str


# ═════════════════ ٦. الطبقةُ غير الصافية: قراءةُ الأثر وبناؤه ═════════════════


async def consent_granted(session, *, tenant_id: uuid.UUID, file_id) -> bool:
    """**ولا يُمنح الإذنُ تلقائيًّا.** يُقرأ من صفّه، ولا يُفترض."""
    from .. import consent

    if file_id is None:
        return False
    return await consent.state(session, tenant_id=tenant_id, file_id=file_id) == consent.GRANTED


async def load_artifacts(session, *, tenant_id: uuid.UUID, opportunity) -> ArtifactSet:
    """يرصد ما هو قائمٌ لهذه الفرصة — **قراءةٌ فقط، ولا إنشاء**."""
    from sqlalchemy import select

    from ...models.golden_thread import ThreadElement
    from ...models.planning import ManuscriptOutline
    from ...models.publishing import Manuscript

    project_id = opportunity.project_id or opportunity.converted_project_id
    if project_id is None:
        return ArtifactSet()

    thread_id = (await session.execute(
        select(ThreadElement.id)
        .where(ThreadElement.tenant_id == tenant_id,
               ThreadElement.project_id == project_id).limit(1)
    )).scalar_one_or_none()
    outline_id = (await session.execute(
        select(ManuscriptOutline.id)
        .where(ManuscriptOutline.tenant_id == tenant_id,
               ManuscriptOutline.opportunity_id == opportunity.id).limit(1)
    )).scalar_one_or_none()
    manuscript_id = (await session.execute(
        select(Manuscript.id)
        .where(Manuscript.tenant_id == tenant_id,
               Manuscript.opportunity_id == opportunity.id).limit(1)
    )).scalar_one_or_none()
    return ArtifactSet(project_id=project_id, thread_id=thread_id,
                       outline_id=outline_id, manuscript_id=manuscript_id)


async def view(session, *, tenant_id: uuid.UUID, thesis) -> dict:
    """حالُ الرحلة كما تُعرض — **مشتقّةٌ من صفوف، بلا نسبة**."""
    facts = await load_facts(session, tenant_id=tenant_id, thesis=thesis)
    facts = dataclasses.replace(
        facts,
        ai_consent_granted=await consent_granted(
            session, tenant_id=tenant_id, file_id=thesis.file_id),
    )
    return {
        "thesis_id": thesis.id,
        "state": derive_state(facts),
        "blocking_reasons": list(blocking_reasons(facts)),
        "can_build_paper": can_build_paper(facts),
        "opportunities": facts.opportunities,
        "states": list(STATES),
    }


async def build_paper(session, *, tenant_id: uuid.UUID, actor_user_id,
                      thesis, opportunity) -> BuildOutcome:
    """يبني ورقةً من فرصةٍ مختارة — **ويُعيد استعمالَ كلِّ ما هو قائم**.

    ولا نداءَ نموذجٍ هنا إطلاقًا: ما تبنيه هذه الشريحةُ حتميّ (مشروعٌ
    وهيكلٌ ومخطوطة). **فلا شبكةَ داخل معاملة** — والدرسُ محفوظ من تخاصم
    سلسلة التدقيق. وصياغةُ النصّ وبناءُ الخيط يقعان في الشريحة التالية،
    بسلطة سياسةِ الأقسام وبإذنٍ صريح.

    والبوّاباتُ تُقرأ من القلب الصافي ولا تُعاد كتابتُها هنا.
    """
    from ...models.planning import ManuscriptOutline
    from ...models.portfolio import ResearchProject
    from ...models.publishing import Manuscript, ManuscriptVersion
    from .. import audit

    # ── ١ · المِلكيّة والنسب: الفرصةُ لهذه الرسالة ولهذا المستأجر ──
    if opportunity.tenant_id != tenant_id or opportunity.thesis_id != thesis.id:
        raise JourneyBlocked(("opportunity_not_of_this_thesis",))

    # ── ٢ · البوّابات، بترتيبها، من القلب الصافي ──
    facts = await load_facts(session, tenant_id=tenant_id, thesis=thesis)
    facts = dataclasses.replace(
        facts,
        ai_consent_granted=await consent_granted(
            session, tenant_id=tenant_id, file_id=thesis.file_id),
    )
    reasons = blocking_reasons(facts)
    if reasons:
        raise JourneyBlocked(reasons)

    # ── ٣ · ما هو قائمٌ يُعاد استعمالُه، ولا يُنشأ ثانيًا ──
    existing = await load_artifacts(session, tenant_id=tenant_id, opportunity=opportunity)
    created: list[str] = []

    project_id = existing.project_id
    if project_id is None:
        project = ResearchProject(
            tenant_id=tenant_id, working_title_ar=opportunity.working_title_ar,
            working_title_en=opportunity.working_title_en, status="planned",
            current_gate="G1", is_thesis_derived=True)
        session.add(project)
        await session.flush()
        project_id = project.id
        # **والرابطتان تُكتبان معًا** — كما في التحويل اليدويّ.
        opportunity.project_id = project_id
        opportunity.converted_project_id = project_id
        # وهذا **هو** التحويل، فيُقال في دورة الإنتاج كما يقوله المسار
        # اليدويّ. وتركُه عند `ready_to_submit` يُبقي الفرصةَ تقول إنّها
        # تنتظر تحويلًا وقد صار لها مشروعٌ ومخطوطة.
        opportunity.status = "converted"
        created.append("project")

    outline_id = existing.outline_id
    if outline_id is None:
        outline = ManuscriptOutline(
            tenant_id=tenant_id, opportunity_id=opportunity.id, project_id=project_id,
            # **ولا قسمَ يُكتب هنا.** سياسةُ الأقسام هي السلطةُ الوحيدة،
            # وتملأ الهيكلَ في الشريحة التالية. وقائمةٌ تُخترع هنا تُنشئ
            # سلطةً ثانية تفترق عنها.
            sections=[])
        session.add(outline)
        await session.flush()
        outline_id = outline.id
        created.append("outline")

    manuscript_id = existing.manuscript_id
    if manuscript_id is None:
        manuscript = Manuscript(
            tenant_id=tenant_id, project_id=project_id,
            title_ar=opportunity.working_title_ar,
            title_en=opportunity.working_title_en,
            language="ar", status="draft",
            opportunity_id=opportunity.id, outline_id=outline_id)
        session.add(manuscript)
        await session.flush()

        # ── ونسخةٌ أولى معها، وإلّا فمخطوطةٌ لا يفتحها الاستوديو ──
        #
        # **`Manuscript → ManuscriptVersion → ManuscriptSection` سلسلةٌ لا
        # تبدأ من وسطها.** كلُّ مدخل في استوديو الورقة — العرضُ العامّ،
        # وقراءةُ قسم، وصياغتُه، واعتمادُه — يمرّ على `_current_version`،
        # وهي ترفع `publishing.manuscript_not_found` حين لا نسخةَ هناك.
        # فمخطوطةٌ بلا نسخة صفٌّ قائمٌ لا باب له: تُبنى الورقةُ، ويقول
        # الزرُّ «افتح استوديو الورقة»، ويُجيب الاستوديو «غير موجودة».
        # و`manuscript_from_opportunity` تكتبهما معًا منذ S5E — فيُكتبان
        # معًا هنا كذلك، ولا يُترك الطريقان يفترقان.
        version = ManuscriptVersion(
            tenant_id=tenant_id, manuscript_id=manuscript.id, version_label="v1",
            created_by=actor_user_id,
            change_reason_ar="النسخة الأولى من الفرصة التي اختارها الباحث")
        session.add(version)
        await session.flush()
        manuscript.current_version_id = version.id

        manuscript_id = manuscript.id
        created.append("manuscript")

    final = ArtifactSet(project_id=project_id, thread_id=existing.thread_id,
                        outline_id=outline_id, manuscript_id=manuscript_id)
    pending = tuple(name for name in to_create(final)
                    if name not in DETERMINISTIC_ARTIFACTS)

    await audit.record(
        session, tenant_id=tenant_id, action="thesis.paper_built",
        object_type="publication_opportunity", object_id=opportunity.id,
        actor_user_id=actor_user_id,
        state_after={"project_id": str(project_id), "outline_id": str(outline_id),
                     "manuscript_id": str(manuscript_id),
                     "created": created, "pending": list(pending)},
        reason="a paper was built from a researcher-selected opportunity after every "
               "gate passed; existing artefacts were reused, none duplicated",
    )

    after = dataclasses.replace(
        facts, project_exists=True, outline_exists=True, manuscript_exists=True,
        thread_ready=existing.thread_id is not None)
    return BuildOutcome(
        project_id=project_id, outline_id=outline_id, manuscript_id=manuscript_id,
        thread_id=existing.thread_id, created=tuple(created),
        reused=to_reuse(existing), pending=pending, state=derive_state(after))

# ═════════════════ ٧. سلطةُ الأقسام: السياسةُ وحدها ═════════════════
#
# **ولا قائمةَ أقسامٍ ثانية في هذا الملفّ.** `drafting/policy.py` هي
# السلطة؛ وما يُكتب هنا دالّةٌ تسأل تلك السلطةَ ولا تحلّ محلَّها. فحين
# تُفتح `literature_review` يومًا بسياستها، تُفتح من موضعٍ واحد.


def sections_allowed(candidates, *, enabled) -> tuple[str, ...]:
    """ما يجوز صياغتُه — **بترتيب المُدخل، ومن المسموح وحده**."""
    permitted = frozenset(enabled)
    return tuple(key for key in candidates if key in permitted)


def sections_refused(candidates, *, enabled) -> tuple[str, ...]:
    """ما تمنعه السياسة — **يُقال ولا يُخفى**، فالباحثُ يعرف ما لم يُكتب."""
    permitted = frozenset(enabled)
    return tuple(key for key in candidates if key not in permitted)


def draftable_sections() -> tuple[str, ...]:
    """الأقسامُ المسموحة الآن، من السياسة مباشرةً وبترتيبها."""
    from ..publishing.drafting import policy

    return sections_allowed(policy.ordered_sections(), enabled=policy.ENABLED_SECTIONS)


def blocked_sections() -> tuple[str, ...]:
    from ..publishing.drafting import policy

    return sections_refused(policy.ordered_sections(), enabled=policy.ENABLED_SECTIONS)


# ═════════════════ ٨. الخيطُ الذهبيّ: نداءُ نموذجٍ بحدوده ═════════════════
#
# **وعقدُ المخرَج في وحدة العقود لا هنا.** رأسُ هذه الوحدة يبقى بلا
# تبعيّة — لا pydantic ولا SQLAlchemy — فيُستورَد قلبُها الصافي ويُفحص
# بلا قاعدةٍ ولا حزم. واستيرادُ عقدٍ في الرأس يقطع ذلك الفحصَ كلَّه.


@dataclasses.dataclass(frozen=True, slots=True)
class ThreadOutcome:
    created: int
    rejected: int
    fingerprint: str
    agent_run_id: uuid.UUID


_THREAD_INSTRUCTION: Final = (
    "استخرج عقد الخيط الذهبي من الأدلة الموثقة المرفقة وحدها. "
    "ولكل عقدة `evidence_refs` من معرّفات الأدلة المرفقة — "
    "ولا تُنشئ عقدة بلا مرجع، ولا تخترع معرّفًا لم يرد في المدخل."
)


async def build_thread(session_maker, *, tenant_id: uuid.UUID, actor_user_id,
                       file_id, project_id: uuid.UUID) -> ThreadOutcome:
    """يبني عقدَ الخيط من الأدلّة الموثقة — **بثلاث خطواتٍ لا تتداخل**.

    ‏(١) معاملةٌ قصيرة تقرأ الإذنَ والأدلّة ثمّ **تُغلق**.
    ‏(٢) النداءُ الخارجيّ **بلا أيّ معاملة مفتوحة** — ودرسُ تخاصم سلسلة
        التدقيق هو السبب: معاملةٌ تمتدّ عبر نداءٍ شبكيّ تُعلّق الحزمةَ كلَّها.
    ‏(٣) معاملةٌ قصيرة ترفض ما لا يُحلّ وتكتب ما بقي.

    **وسقوطُ النموذج لا يترك أثرًا نصفيًّا**: الخطوةُ الأولى قراءةٌ فقط،
    والثالثةُ لا تُفتح أصلًا إن سقطت الثانية. فلا صفَّ يُكتب لمخطوطةٍ
    نصفِ مبنيّة.

    **والإذنُ لا يُمنح تلقائيًّا**: بلا إذنٍ لا يقع نداءٌ واحد.
    """
    import json

    from ...brain.orchestrator import Orchestrator
    from ...models.golden_thread import ThreadElement
    from ...schemas.thesis import ThreadDraft
    from .. import audit, consent
    from ..planning import context as research_context

    # ── (١) معاملةٌ قصيرة: الإذنُ والأدلّة، ثمّ تُغلق ──
    async with session_maker() as session:
        if not await consent_granted(session, tenant_id=tenant_id, file_id=file_id):
            # **ولا نداءَ واحدًا بلا إذن.** يُرفع قبل أن يُبنى أيُّ حِمل.
            raise JourneyBlocked((BLOCK_NO_CONSENT,))
        grant = await consent.authorization_for(
            session, tenant_id=tenant_id, file_id=file_id)
        # **وحدُّ المصدر يُمرَّر**: أدلّةُ هذه الرسالة وحدها تصل النموذج.
        evidence = await research_context.build(
            session, tenant_id=tenant_id, project_id=project_id,
            capability=consent.PLANNING_CAPABILITY, source_file_id=file_id)
        fingerprint = evidence.fingerprint

        # ── والبصمةُ تُفحص قبل النداء، لا بعده ──
        #
        # **إذنٌ أُعطي للقطةٍ لا يصلح لغيرها.** أُضيفت ذاكرةٌ موثقة أو تبدّل
        # نصُّها، فصارت الأدلّةُ غيرَ التي رآها الباحثُ حين أذن. وإرسالُها
        # تحت ذلك الإذن إرسالُ ما لم يره — ولو كان الإذنُ قائمًا شكلًا.
        #
        # ويقع الفحصُ **داخل هذه المعاملة القصيرة**، فالرفضُ يسبق النداء
        # ولا يقع نداءٌ واحد على لقطةٍ بائتة.
        planning = await consent.planning_state(
            session, tenant_id=tenant_id, project_id=project_id,
            context_fingerprint=fingerprint)
        if planning == consent.STALE:
            raise JourneyBlocked((BLOCK_STALE_CONSENT,))

        known = frozenset(str(item.memory_id) for item in evidence.items)
        payload = json.dumps(
            [dict(item.as_model_view(), id=str(item.memory_id)) for item in evidence.items],
            ensure_ascii=False)

    # ── (٢) بلا معاملة: النداءُ الخارجيّ عبر البوّابة وحدها ──
    draft, agent_run_id = await Orchestrator().run_structured_detached(
        session_maker, tenant_id=tenant_id, actor_user_id=actor_user_id,
        agent_key="golden_thread_agent", contract=ThreadDraft,
        instruction=_THREAD_INSTRUCTION, payload=payload,
        # §6 — معرفةٌ بحثية غير منشورة: C2. والقدرةُ تحكم، والإذنُ مقروء.
        input_classification="C2", output_locale="ar", grant=grant,
    )

    # ── (٣) معاملةٌ قصيرة: الرفضُ أوّلًا، ثمّ الكتابة ──
    kept, rejected = reject_unresolvable(
        draft.elements, known, refs_of=lambda element: element.evidence_refs)

    async with session_maker() as session:
        for ordinal, element in enumerate(kept, start=1):
            session.add(ThreadElement(
                tenant_id=tenant_id, project_id=project_id,
                element_type=element.element_type[:24],
                label_ar=element.label_ar, ordinal=ordinal,
                metadata_json={"evidence_refs": list(element.evidence_refs),
                               "agent_run_id": str(agent_run_id)}))
        await audit.record(
            session, tenant_id=tenant_id, action="thesis.thread_built",
            object_type="research_project", object_id=project_id,
            actor_user_id=actor_user_id,
            state_after={"created": len(kept), "rejected": len(rejected),
                         "context_fingerprint": fingerprint,
                         "agent_run_id": str(agent_run_id)},
            # **والمرفوضُ يُعدّ ولا يُروى نصًّا**: عددُه معلومةٌ للتدقيق،
            # ومتنُه اختلاقٌ لا يُحفظ.
            reason="thread elements whose evidence references did not resolve to real "
                   "rows were rejected outright, never repaired or substituted",
        )

    return ThreadOutcome(created=len(kept), rejected=len(rejected),
                         fingerprint=fingerprint, agent_run_id=agent_run_id)
