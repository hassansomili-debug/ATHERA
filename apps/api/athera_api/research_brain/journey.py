"""أين يقف الباحث، وما الخطوة التالية، ولماذا | The project journey orchestrator (Wave 2-A §23–§26, §49).

**سؤالان لا سؤال واحد، ولا يُخلطان:**

    ما الذي **يمكن** فعله الآن؟      حتميّ — يُقرأ من حال البحث
    ما الذي **يُستحسن** فعله تاليًا؟  استشاريّ — رأيٌ في الترتيب

والفرقُ ليس تنميقًا. «لا يمكن تشغيل تحليلٍ بلا بيانات» واقعةٌ يقرؤها أيُّ
قارئٍ من الصفوف نفسها فيخرج بالجواب نفسه. و«ابدأ بالإحصاء الوصفي» رأيٌ في
الترتيب يصحّ ويُخالَف. فجعلُهما نوعًا واحدًا يُنتج أحدَ عطبين: إمّا أن يصير
الرأيُ حاجزًا يوقف باحثًا يعرف ما يفعل، وإمّا أن تصير الواقعةُ اقتراحًا
يُتجاوَز فيُطلَب تحليلٌ لبياناتٍ غير موجودة.

**ولا حالةَ خاصّةً برسالة هنا.** الحدُّ `project_id` وحده (§75): بحثٌ نشأ
من فكرة، أو من رسالة، أو من مجموعة بيانات، أو من ورقةٍ مرفوعة — كلُّها
تُقرأ بالقواعد نفسها. ولا `thesis_id` ولا `mining_state` ولا مفردةً من
مفردات مركز الرسائل في هذا الملف، وعقدُ الاستيراد في `pyproject.toml`
يحرس ذلك بنيويًّا لا اتفاقًا.

## ولا نسبةَ إنجاز

لا «٧٣٪ مكتمل» (§45). النسبةُ تُخترع مقامًا لا وجود له: كم خطوةً في بحثٍ
كيفيّ استكشافيّ؟ فتُسمّى الحالُ بأسمائها — «لا سؤال بحث»، «المنهج محدَّد»،
«لا تحليل بعد» — وهي أصدقُ وأنفعُ معًا.

## والقاعدة تُعلن سببها

كلُّ فعلٍ مقترح يحمل `reason_ar`/`reason_en` و`evidence_refs`: **لمَ** قيل،
و**ممّ** قُرئ (§26). و«الذكاء الاصطناعي يقترح كذا» ليس سببًا — ولا نموذجَ
يُستدعى في هذا الملف أصلًا.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Final, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .ontology import EntityKind, ResearchGraph


class ActionStatus(str, Enum):
    """حالُ الفعل المقترح — خمسٌ، ولكلٍّ معنًى لا يشاركه غيرُه."""

    #: يُستحسن الآن — ومتطلّباته متوفّرة.
    RECOMMENDED = "recommended"
    #: ممكنٌ الآن، ولا يُقدَّم على غيره.
    AVAILABLE = "available"
    #: **لا يمكن** — ومعه سببُ المنع بالاسم.
    BLOCKED = "blocked"
    #: نافعٌ ولا يلزم.
    OPTIONAL = "optional"
    #: وقع فعلًا.
    COMPLETED = "completed"


class ActionCategory(str, Enum):
    FOUNDATION = "foundation"
    EVIDENCE = "evidence"
    DATA = "data"
    INTEGRITY = "integrity"
    WRITING = "writing"


class NextAction(BaseModel):
    """فعلٌ واحد بحاله وسببه وسنده.

    **ولا اسمَ خدمةٍ داخليّ في وجه الباحث** (§25): `action_key` رمزٌ ثابت
    للآلة، والعنوانُ نصٌّ للإنسان، ولا يُعرض اسمُ وحدةٍ ولا دالّة.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action_key: str = Field(min_length=1)
    category: ActionCategory
    status: ActionStatus

    title_ar: str = Field(min_length=1)
    title_en: str = Field(min_length=1)
    reason_ar: str = Field(min_length=1)
    reason_en: str = Field(min_length=1)

    #: مسارُ الواجهة بلا لغة — تُضيفها الواجهةُ من موضعها.
    route: str | None = None

    #: ما يمنع هذا الفعل الآن — رموزٌ ثابتة، وتُملأ مع `BLOCKED` وحدها.
    blocking_reasons: tuple[str, ...] = ()
    #: ما يلزم توفّره ليصير الفعل ممكنًا.
    requirements: tuple[str, ...] = ()
    #: معرّفاتُ الكيانات التي قُرئت فصدر هذا الحكم — **سندُ القول**.
    evidence_refs: tuple[str, ...] = ()

    #: رتبةُ العرض. أصغرُ أولًا، ولا تُقرأ رقمًا مطلقًا.
    priority: int = 100

    def model_post_init(self, _context: object) -> None:
        """**والمنعُ يُسمّى.** فعلٌ ممنوعٌ بلا سببٍ مكتوب طريقٌ مسدود.

        وهو العطبُ عينه الذي أُصلح في رحلة الرسالة: زرٌّ مطفأٌ لا يقول لمَ.
        فيصير الشرطُ بنيويًّا هنا — لا يُبنى الكائنُ أصلًا بلا سبب.
        """
        if self.status is ActionStatus.BLOCKED and not self.blocking_reasons:
            raise ValueError(
                f"{self.action_key}: فعلٌ ممنوع بلا سببٍ مسمّى — والمنعُ يُسمّى")
        if self.status is not ActionStatus.BLOCKED and self.blocking_reasons:
            raise ValueError(
                f"{self.action_key}: أسبابُ منعٍ على فعلٍ غيرِ ممنوع")


@dataclass(frozen=True, slots=True)
class JourneyFacts:
    """وقائعُ البحث كما تُقرأ من اللقطة — **عدٌّ لا تفسير**.

    تُشتقّ من `ResearchGraph` وحدها، فتُختبر كلُّ قاعدةٍ بلا قاعدة بيانات
    ولا جلسة — وهو الحدُّ الذي تقوم عليه هذه الحزمة كلُّها.
    """

    counts: dict[str, int] = field(default_factory=dict)
    ids: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: حقولُ «ما نعرفه» التي تنتظر مراجعةً.
    needs_review: tuple[str, ...] = ()
    #: تعارضاتٌ **مسجَّلة** في البيانات — لا مستنبَطة (§17).
    contradictions: tuple[str, ...] = ()
    #: أقسامُ المخطوطة التي فيها نصّ.
    written_sections: tuple[str, ...] = ()
    #: **حجمُ العيّنة مسجَّلٌ فعلًا** — لا مجرّدُ وجودِ كيانِ عيّنة.
    #:
    #: والفرقُ ليس تدقيقًا: الجسرُ يُنشئ كيانَ `Sample` لكلّ منهجٍ مسجَّل
    #: **ولو كان الحجمُ غيرَ مسجَّل** (يضع `missing()` في موضعه). فقاعدةٌ
    #: تسأل «أثمّة عيّنة؟» تُجاب بنعم دائمًا بمجرّد وجود منهج، فلا تُطلق
    #: أبدًا — وهو عطبُ حارسٍ ميت: موجودٌ في السجلّ، لا يحرس شيئًا.
    sample_size_recorded: bool = False

    def has(self, kind: EntityKind) -> bool:
        return self.counts.get(kind.value, 0) > 0

    def count(self, kind: EntityKind) -> int:
        return self.counts.get(kind.value, 0)

    def refs(self, *kinds: EntityKind) -> tuple[str, ...]:
        """سندُ الحكم: معرّفاتُ ما قُرئ — مرتَّبةً فلا يتغيّر الجوابُ بترتيب."""
        out: list[str] = []
        for kind in kinds:
            out.extend(self.ids.get(kind.value, ()))
        return tuple(sorted(out))


def read_facts(graph: ResearchGraph, *,
               needs_review: Iterable[str] = (),
               contradictions: Iterable[str] = (),
               written_sections: Iterable[str] = ()) -> JourneyFacts:
    """يقرأ الرسمَ عدًّا — ولا يحكم."""
    counts: dict[str, int] = {}
    ids: dict[str, list[str]] = {}
    sized = False
    for entity in graph.entities:
        key = entity.kind.value
        counts[key] = counts.get(key, 0) + 1
        ids.setdefault(key, []).append(entity.id)
        size = getattr(entity, "size", None)
        if size is not None and getattr(size, "is_known", False):
            sized = True
    return JourneyFacts(
        sample_size_recorded=sized,
        counts=counts,
        ids={k: tuple(sorted(v)) for k, v in ids.items()},
        needs_review=tuple(sorted(needs_review)),
        contradictions=tuple(sorted(contradictions)),
        written_sections=tuple(sorted(written_sections)),
    )


# ═══════════════ البوّابات الحتمية — ما **يمكن** فعله ═══════════════

class Capability(BaseModel):
    """بوّابةٌ حتمية: **يمكن** أو **لا يمكن**، ومعها السبب.

    ولا نموذجَ يُسأل عنها (§24). «هل تكفي هذه البيانات لتحليل؟» سؤالٌ
    جوابُه في الصفوف، ونموذجٌ يُجيب عنه يُجيب أحيانًا بنعم وأحيانًا بلا
    على المُدخل نفسه — فيصير حاجزًا لا يُبنى عليه منع.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    allowed: bool
    blocking_reasons: tuple[str, ...] = ()

    def model_post_init(self, _context: object) -> None:
        if not self.allowed and not self.blocking_reasons:
            raise ValueError(f"{self.key}: منعٌ بلا سبب")
        if self.allowed and self.blocking_reasons:
            raise ValueError(f"{self.key}: سببُ منعٍ مع إذن")


#: رموزُ المنع — ثابتةٌ للآلة، وتُترجَم في طبقة العرض (§81).
NO_QUESTION: Final = "research_question_missing"
NO_METHOD: Final = "method_not_selected"
NO_DATASET: Final = "dataset_missing"
NO_ANALYSIS: Final = "analysis_not_run"
NO_FINDING: Final = "no_findings_recorded"
NO_SOURCE: Final = "no_sources_linked"


def capabilities(facts: JourneyFacts) -> tuple[Capability, ...]:
    """البوّاباتُ الأربع — وكلُّها تُقرأ من الوقائع وحدها."""

    def gate(key: str, *reasons: tuple[bool, str]) -> Capability:
        blocking = tuple(code for failed, code in reasons if failed)
        return Capability(key=key, allowed=not blocking, blocking_reasons=blocking)

    return (
        # تحليلٌ بلا بياناتٍ لا يقع — مهما اقترح مقترح.
        gate("run_analysis", (not facts.has(EntityKind.DATASET), NO_DATASET)),
        # نتيجةٌ بلا تشغيلةٍ أنتجتها اختلاق — وهي `RB-FABRICATION-01` نفسها.
        gate("record_finding", (not facts.has(EntityKind.ANALYSIS), NO_ANALYSIS)),
        # ادّعاءٌ بلا مصدرٍ مربوطٍ بالبحث لا يُسنَد.
        gate("support_claim", (not facts.has(EntityKind.SOURCE), NO_SOURCE)),
        # وقسمُ النتائج لا يُصاغ قبل أن توجد نتيجة.
        gate("draft_results", (not facts.has(EntityKind.FINDING), NO_FINDING)),
    )


# ═══════════════ سجلُّ القواعد — ما **يُستحسن** تاليًا ═══════════════

@dataclass(frozen=True, slots=True)
class JourneyRule:
    """قاعدةٌ واحدة: مفتاحٌ، وشرطٌ، وفعلٌ يُقترح.

    **سجلٌّ لا شجرةُ `if`** (§49). القاعدةُ كائنٌ يُعدّ ويُختبر ويُعطَّل
    وحدَه؛ وشجرةُ شروطٍ متفرّقةٌ على صفحات لا يُعرف منها ما القواعدُ ولا
    أيُّها أطلق.
    """

    key: str
    category: ActionCategory
    priority: int
    evaluate: Callable[[JourneyFacts], NextAction | None]


def _action(key: str, category: ActionCategory, priority: int, *,
            status: ActionStatus, ar: str, en: str, why_ar: str, why_en: str,
            route: str | None = None, refs: tuple[str, ...] = (),
            requirements: tuple[str, ...] = (),
            blocking: tuple[str, ...] = ()) -> NextAction:
    return NextAction(
        action_key=key, category=category, status=status, priority=priority,
        title_ar=ar, title_en=en, reason_ar=why_ar, reason_en=why_en,
        route=route, evidence_refs=refs, requirements=requirements,
        blocking_reasons=blocking)


def _define_question(f: JourneyFacts) -> NextAction | None:
    if f.has(EntityKind.RESEARCH_QUESTION):
        return None
    return _action(
        "define_research_question", ActionCategory.FOUNDATION, 10,
        status=ActionStatus.RECOMMENDED,
        ar="حدِّد سؤال البحث", en="Define the research question",
        why_ar="لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد، وعليه يُبنى ما بعده.",
        why_en="No research question is recorded yet, and the rest builds on it.",
        route="/portfolio/{project_id}/thread")


def _select_method(f: JourneyFacts) -> NextAction | None:
    if not f.has(EntityKind.RESEARCH_QUESTION) or f.has(EntityKind.DESIGN):
        return None
    return _action(
        "select_method", ActionCategory.FOUNDATION, 20,
        status=ActionStatus.RECOMMENDED,
        ar="اختر المنهج", en="Select the method",
        why_ar="السؤالُ مسجَّل ولا تصميمَ منهجيًّا بعده.",
        why_en="A research question exists but no design is recorded.",
        route="/portfolio/{project_id}/thread",
        refs=f.refs(EntityKind.RESEARCH_QUESTION))


def _define_sample(f: JourneyFacts) -> NextAction | None:
    """**والسؤالُ عن حجمٍ مسجَّل لا عن كيانٍ موجود.**

    كيانُ العيّنة يُنشأ مع كلّ منهج، وحجمُه قد يكون `missing()`. فلو سُئل
    عن وجود الكيان لَما أطلقت هذه القاعدةُ أبدًا.
    """
    if not f.has(EntityKind.DESIGN) or f.sample_size_recorded:
        return None
    return _action(
        "define_sample", ActionCategory.FOUNDATION, 30,
        status=ActionStatus.RECOMMENDED,
        ar="حدِّد حجم العيّنة", en="Record the sample size",
        why_ar="التصميمُ محدَّد وحجمُ العيّنة غيرُ مسجَّل.",
        why_en="A design is selected but the sample size is not recorded.",
        route="/portfolio/{project_id}/thread",
        refs=f.refs(EntityKind.DESIGN))


def _link_sources(f: JourneyFacts) -> NextAction | None:
    if f.has(EntityKind.SOURCE):
        return None
    return _action(
        "link_sources", ActionCategory.EVIDENCE, 40,
        status=ActionStatus.RECOMMENDED,
        ar="اربط مصادر بالبحث", en="Link sources to the project",
        why_ar="لا مصدرَ مربوطٌ بهذا البحث، ولا يُسنَد ادّعاءٌ بلا مصدر.",
        why_en="No source is linked to this project, and no claim can be supported without one.",
        route="/library")


def _add_dataset(f: JourneyFacts) -> NextAction | None:
    if not f.has(EntityKind.DESIGN) or f.has(EntityKind.DATASET):
        return None
    return _action(
        "add_dataset", ActionCategory.DATA, 50,
        status=ActionStatus.OPTIONAL,
        ar="أضف مجموعة بيانات", en="Add a dataset",
        why_ar=("التصميمُ محدَّد ولا بياناتٍ بعد. وليست كلُّ الدراسات "
                "تحتاجها، فهذه دعوةٌ لا شرط."),
        why_en=("A design exists and no dataset yet. Not every study needs one, "
                "so this is an invitation, not a requirement."),
        route="/analysis", refs=f.refs(EntityKind.DESIGN))


def _run_analysis(f: JourneyFacts) -> NextAction | None:
    if not f.has(EntityKind.DATASET) or f.has(EntityKind.ANALYSIS):
        return None
    return _action(
        "run_analysis", ActionCategory.DATA, 60,
        status=ActionStatus.RECOMMENDED,
        ar="شغِّل تحليلًا", en="Run an analysis",
        why_ar="البياناتُ متوفّرة ولا تشغيلةَ تحليلٍ عليها بعد.",
        why_en="A dataset is available and no analysis run exists on it yet.",
        route="/analysis", refs=f.refs(EntityKind.DATASET))


def _record_findings(f: JourneyFacts) -> NextAction | None:
    if not f.has(EntityKind.ANALYSIS) or f.has(EntityKind.FINDING):
        return None
    return _action(
        "record_findings", ActionCategory.DATA, 70,
        status=ActionStatus.RECOMMENDED,
        ar="سجِّل النتائج", en="Record the findings",
        why_ar="التحليلُ جرى ولم تُسجَّل نتيجةٌ تُشتقّ منه.",
        why_en="An analysis ran and no finding is derived from it yet.",
        route="/analysis", refs=f.refs(EntityKind.ANALYSIS))


def _resolve_conflicts(f: JourneyFacts) -> NextAction | None:
    """**والتعارضُ يُعرض ولا يُحسم عن الباحث** (§17، §58).

    ولا تختار هذه القاعدةُ طرفًا ولا تُسقط دليلًا: تقول إنّ ثمّة تعارضًا
    مسجَّلًا، وتدلّ على موضعه. والحسمُ حكمٌ علميّ صاحبُه الباحث.
    """
    if not f.contradictions:
        return None
    return _action(
        "resolve_contradiction", ActionCategory.INTEGRITY, 5,
        status=ActionStatus.RECOMMENDED,
        ar="عالِج تعارضًا في الأدلة", en="Resolve an evidence conflict",
        why_ar=(f"ثمّة {len(f.contradictions)} تعارضًا مسجَّلًا بين دليلٍ "
                "وادّعاء، بلا ملاحظةِ معالجة."),
        why_en=(f"{len(f.contradictions)} recorded conflict(s) between evidence "
                "and a claim, with no resolution note."),
        route="/portfolio/{project_id}/contradictions",
        refs=tuple(f.contradictions))


def _review_fields(f: JourneyFacts) -> NextAction | None:
    if not f.needs_review:
        return None
    return _action(
        "review_extracted_fields", ActionCategory.INTEGRITY, 80,
        status=ActionStatus.OPTIONAL,
        ar="راجِع معلوماتٍ مستخرَجة", en="Review extracted information",
        why_ar=(f"{len(f.needs_review)} حقلًا مستخرَجًا ينتظر تأكيدَك. "
                "والمستخرَجُ غيرُ المؤكَّد لا يصير معرفةً موثقة."),
        why_en=(f"{len(f.needs_review)} extracted field(s) await your confirmation. "
                "Unconfirmed extraction does not become verified knowledge."),
        route="/facts", refs=tuple(f.needs_review))


def _start_writing(f: JourneyFacts) -> NextAction | None:
    if not f.has(EntityKind.FINDING) or f.written_sections:
        return None
    return _action(
        "start_manuscript", ActionCategory.WRITING, 90,
        status=ActionStatus.RECOMMENDED,
        ar="ابدأ كتابة الورقة", en="Start writing the paper",
        why_ar="ثمّة نتائجُ مسجَّلة ولا قسمَ مكتوبٌ بعد.",
        why_en="Findings are recorded and no section is written yet.",
        route="/manuscripts", refs=f.refs(EntityKind.FINDING))


#: **سجلُّ القواعد.** والترتيبُ هنا ترتيبُ الإعلان لا ترتيبُ العرض —
#: العرضُ بـ`priority` ثمّ بالمفتاح، فلا يتغيّر بإعادة ترتيب هذه القائمة.
RULES: Final[tuple[JourneyRule, ...]] = (
    JourneyRule("resolve_contradiction", ActionCategory.INTEGRITY, 5, _resolve_conflicts),
    JourneyRule("define_research_question", ActionCategory.FOUNDATION, 10, _define_question),
    JourneyRule("select_method", ActionCategory.FOUNDATION, 20, _select_method),
    JourneyRule("define_sample", ActionCategory.FOUNDATION, 30, _define_sample),
    JourneyRule("link_sources", ActionCategory.EVIDENCE, 40, _link_sources),
    JourneyRule("add_dataset", ActionCategory.DATA, 50, _add_dataset),
    JourneyRule("run_analysis", ActionCategory.DATA, 60, _run_analysis),
    JourneyRule("record_findings", ActionCategory.DATA, 70, _record_findings),
    JourneyRule("review_extracted_fields", ActionCategory.INTEGRITY, 80, _review_fields),
    JourneyRule("start_manuscript", ActionCategory.WRITING, 90, _start_writing),
)

BY_KEY: Final[dict[str, JourneyRule]] = {rule.key: rule for rule in RULES}


@dataclass(frozen=True, slots=True)
class JourneyDecision:
    """جوابُ المنسّق: ما يمكن، وما يُستحسن — مفصولين."""

    capabilities: tuple[Capability, ...]
    actions: tuple[NextAction, ...]

    @property
    def recommended(self) -> NextAction | None:
        """الخطوةُ التالية المقترحة — واحدةٌ لا عشر (§84)."""
        for action in self.actions:
            if action.status is ActionStatus.RECOMMENDED:
                return action
        return None

    def capability(self, key: str) -> Capability | None:
        for row in self.capabilities:
            if row.key == key:
                return row
        return None


def decide(facts: JourneyFacts,
           rules: tuple[JourneyRule, ...] = RULES) -> JourneyDecision:
    """يُشغّل السجلَّ ويرتّب — **حتميًّا**.

    ولا عشوائيةَ في الترتيب: `priority` ثمّ المفتاح. فالجوابُ عن وقائعَ
    واحدة هو هو في كلّ مرة، وهذا شرطُ أن تُختبر الشاشةُ أصلًا.
    """
    produced = [action for rule in rules if (action := rule.evaluate(facts))]
    produced.sort(key=lambda a: (a.priority, a.action_key))
    return JourneyDecision(capabilities=capabilities(facts), actions=tuple(produced))


__all__ = [
    "ActionCategory", "ActionStatus", "BY_KEY", "Capability", "JourneyDecision",
    "JourneyFacts", "JourneyRule", "NextAction", "RULES",
    "NO_ANALYSIS", "NO_DATASET", "NO_FINDING", "NO_METHOD", "NO_QUESTION", "NO_SOURCE",
    "capabilities", "decide", "read_facts",
]
