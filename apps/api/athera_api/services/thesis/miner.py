"""منقّب فرص النشر | Publication opportunity miner (§23.4، §23.5).

يقترح فرصًا من **عناصر الرسالة المستخرجة فعلًا** — أسئلة، نتائج، مقاييس،
مراحل. لا يخترع فرصة من عنوان: كل فرصة تحمل مراجع إلى ما اشتُقت منه، وهي
نفسها بصمة التداخل لاحقًا (§23.7).

وهو حتمي بالكامل: يعمل بلا نموذج لغوي، بنفس منطق مستخرج Sprint 1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from .vocab import OPPORTUNITY_KINDS, PAPER_KINDS


@dataclass(frozen=True, slots=True)
class ThesisFacts:
    """ما استُخرج من الرسالة — مدخل المنقّب."""

    thesis_id: str
    #: **`None` = «لم يُستخرَج العنوان بعد»** — لا سلسلةٌ فارغة ولا اسمُ ملفّ.
    #:
    #: و`theses.title_ar` عمودٌ يقبل `NULL` (ترحيل 0015)، ورسالةٌ رُفعت ولم
    #: تُقرأ بعدُ لا عنوان لها. وكان هذا الحقل موصوفًا `str` فيُمرَّر `None`
    #: على أيّ حال — فيسقط `" ".join([...])` بـ`TypeError` ويُردّ الباحثُ
    #: بخمسمئة على مسارٍ صحيح تمامًا.
    title: str | None = None
    questions: tuple[str, ...] = ()
    hypotheses: tuple[str, ...] = ()
    results: tuple[tuple[str, str], ...] = ()      # (result_id, label)
    instruments: tuple[tuple[str, str], ...] = ()  # (instrument_id, label)
    variables: tuple[str, ...] = ()
    sample_ids: tuple[str, ...] = ()
    qualitative_phases: tuple[str, ...] = ()
    null_result_ids: tuple[str, ...] = ()
    published_result_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class OpportunityDraft:
    opportunity_kind: str
    paper_kind: str
    working_title_ar: str
    research_question_ar: str | None
    rationale_ar: str
    rationale_en: str
    result_refs: list[str] = field(default_factory=list)
    variable_refs: list[str] = field(default_factory=list)
    sample_refs: list[str] = field(default_factory=list)
    published_output_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.opportunity_kind not in OPPORTUNITY_KINDS:
            raise ValueError(f"unknown opportunity kind: {self.opportunity_kind}")
        if self.paper_kind not in PAPER_KINDS:
            raise ValueError(f"unknown paper kind: {self.paper_kind}")


_SCALE_MARKERS = re.compile(r"(مقياس|استبانة جديدة|أداة مطورة|scale|instrument development)",
                            re.IGNORECASE)
_ANTECEDENT_MARKERS = re.compile(r"(محددات|مسببات|العوامل المؤثرة|antecedents|determinants)",
                                 re.IGNORECASE)
_CONSEQUENCE_MARKERS = re.compile(r"(آثار|نتائج مترتبة|تبعات|consequences|outcomes)",
                                  re.IGNORECASE)
_COMPARATIVE_MARKERS = re.compile(r"(مقارنة|الفروق بين|comparative|differences between)",
                                  re.IGNORECASE)


def mine(facts: ThesisFacts) -> list[OpportunityDraft]:
    """يقترح فرصًا مؤصَّلة في عناصر الرسالة. القائمة الفارغة نتيجة صحيحة."""
    drafts: list[OpportunityDraft] = []
    unpublished = [rid for rid, _ in facts.results if rid not in facts.published_result_ids]

    # 1. سؤال مستقل — لكل سؤال بحثي له نتائج غير منشورة.
    for index, question in enumerate(facts.questions, start=1):
        related = unpublished[index - 1: index] or unpublished[:1]
        if not related:
            continue
        drafts.append(OpportunityDraft(
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar=f"ورقة من السؤال {index}: {question[:80]}",
            research_question_ar=question,
            rationale_ar="سؤال بحثي في الرسالة له نتائج لم تُنشر بعد.",
            rationale_en="A thesis research question with results not yet published.",
            result_refs=list(related), variable_refs=list(facts.variables),
            sample_refs=list(facts.sample_ids),
            published_output_refs=list(facts.published_result_ids),
        ))

    # 4. ورقة بناء مقياس — إن طُوِّرت أداة داخل الرسالة.
    for instrument_id, label in facts.instruments:
        if _SCALE_MARKERS.search(label):
            drafts.append(OpportunityDraft(
                opportunity_kind="scale_development", paper_kind="extension",
                working_title_ar=f"ورقة بناء مقياس: {label[:80]}",
                research_question_ar=None,
                rationale_ar="طُوِّرت أداة قياس داخل الرسالة وتصلح ورقة مستقلة.",
                rationale_en="A measurement instrument developed in the thesis merits its own paper.",
                variable_refs=list(facts.variables), sample_refs=list(facts.sample_ids),
                result_refs=[instrument_id],
            ))

    # 3. مرحلة كيفية مستقلة.
    for phase in facts.qualitative_phases:
        drafts.append(OpportunityDraft(
            opportunity_kind="qualitative_phase", paper_kind="extraction",
            working_title_ar=f"المرحلة الكيفية: {phase[:80]}",
            research_question_ar=None,
            rationale_ar="مرحلة كيفية لها سؤالها ومنهجها وتصلح ورقة قائمة بذاتها.",
            rationale_en="A qualitative phase with its own question and method can stand alone.",
            sample_refs=list(facts.sample_ids),
        ))

    # 8. نتائج سالبة أو غير متوقعة — قيمتها العلمية أن تُنشر لا أن تُهمل.
    if facts.null_result_ids:
        drafts.append(OpportunityDraft(
            opportunity_kind="null_unexpected", paper_kind="extraction",
            working_title_ar="ورقة النتائج السالبة أو غير المتوقعة",
            research_question_ar=None,
            rationale_ar="نتائج غير دالة أو مخالفة للتوقع، ونشرها يقلل انحياز النشر.",
            rationale_en="Null or unexpected results; publishing them reduces publication bias.",
            result_refs=list(facts.null_result_ids), sample_refs=list(facts.sample_ids),
        ))

    # 5/6/7/9 — محددات، نتائج مترتبة، مقارنة، تحليل ثانوي.
    #
    # **وهذه الأربعة وحدها عنوانُها العامل مشتقٌّ من عنوان الرسالة**، فتُعلَّق
    # حين لا عنوان — ولا يُخترع لها واحد. انظر `_titled_drafts`.
    drafts += _titled_drafts(facts, unpublished)
    return drafts


# ═════════ المقترحاتُ التي لا تقوم إلّا بعنوانٍ مستخرَج ═════════
#
# **ولا يُخترع عنوانٌ ليمرّ مقترح.** أربعةُ أنواعٍ عنوانُها العامل هو عنوان
# الرسالة مقصوصًا؛ ورسالةٌ لم يُستخرَج عنوانها بعد (`title_ar IS NULL`) لا
# اسم لها يُقتبس. فالخياران: أن يُخترع نصٌّ — وهو كذبٌ صغير يُكتب في قاعدة
# البيانات ويُقرأ عنوانَ ورقة — أو أن تُعلَّق هذه الأربعة ويُقال إنّها
# عُلِّقت. **والثاني هو الصادق**، وهو ما يقع.
#
# وما عداها يبقى عاملًا: «سؤال مستقل» عنوانُه من السؤال، و«بناء مقياس» من
# اسم الأداة، و«المرحلة الكيفية» من اسم المرحلة، و«النتائج السالبة» نصٌّ
# ثابت. فغيابُ العنوان لا يُعطّل التنقيب، ويُنقص منه ما لا يقوم بدونه.

_TITLED_KINDS: Final = (
    (_ANTECEDENT_MARKERS, "antecedents", "ورقة المحددات"),
    (_CONSEQUENCE_MARKERS, "consequences", "ورقة النتائج المترتبة"),
    (_COMPARATIVE_MARKERS, "comparative", "ورقة المقارنة"),
)


def _marker_haystack(facts: ThesisFacts) -> str:
    """**والغائبُ لا يُضمّ إلى النصّ.** `" ".join` على `None` يسقط بـ`TypeError`."""
    return " ".join(
        part for part in (facts.title, *facts.questions, *facts.hypotheses) if part)


def _secondary_analysis_fits(facts: ThesisFacts) -> bool:
    return bool(facts.sample_ids) and len(facts.variables) >= 3


def _titled_drafts(facts: ThesisFacts, unpublished: list[str]) -> list[OpportunityDraft]:
    if not facts.title:
        return []
    haystack = _marker_haystack(facts)
    drafts = [
        OpportunityDraft(
            opportunity_kind=kind, paper_kind="extraction",
            working_title_ar=f"{label}: {facts.title[:60]}",
            research_question_ar=None,
            rationale_ar="ورد في الرسالة ما يشير إلى هذا المسار صراحةً.",
            rationale_en="The thesis explicitly signals this line of enquiry.",
            result_refs=list(unpublished), variable_refs=list(facts.variables),
            sample_refs=list(facts.sample_ids),
        )
        for pattern, kind, label in _TITLED_KINDS if pattern.search(haystack)
    ]
    if _secondary_analysis_fits(facts):
        drafts.append(OpportunityDraft(
            opportunity_kind="secondary_analysis", paper_kind="extension",
            working_title_ar=f"تحليل ثانوي على بيانات: {facts.title[:60]}",
            research_question_ar=None,
            rationale_ar="تسمح البيانات بسؤال جديد لم تختبره الرسالة.",
            rationale_en="The data supports a new question the thesis did not test.",
            variable_refs=list(facts.variables), sample_refs=list(facts.sample_ids),
        ))
    return drafts


def withheld_for_missing_title(facts: ThesisFacts) -> int:
    """كم مقترحًا **عُلِّق** لأنّ العنوان لم يُستخرَج بعد.

    **و«لم يُقترح» ليست «لا يوجد».** تنقيبٌ يعود بأقلّ ممّا كان ليعود به،
    بلا أن يُقال لماذا، يُقرأ حكمًا على الرسالة لا نقصًا في مدخلاتها.
    """
    if facts.title:
        return 0
    haystack = _marker_haystack(facts)
    return (sum(1 for pattern, _kind, _label in _TITLED_KINDS if pattern.search(haystack))
            + (1 if _secondary_analysis_fits(facts) else 0))
