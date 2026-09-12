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


# ═════════ الاكتشافُ طبقة، والاكتمالُ طبقةٌ أخرى ═════════
#
# **سؤالان لا سؤال، وخلطُهما هو ما ردّ الباحثَ بصفر.**
#
#   ‏«اقرأ رسالتي وقل لي أيَّ الأوراق يمكن أن تُشتقّ منها؟»
#   ‏«هل لهذه الورقة من الأدلّة ما يكفي للصياغة الآمنة؟»
#
# والثاني قرارٌ **لاحق**. وكان شرطُ الثاني — بناءٌ وعيّنةٌ معًا — مفروضًا
# على الأول، فرسالةٌ فيها نتيجةٌ قويّةٌ مؤصَّلة بلا وصفِ عيّنةٍ مستخرَج
# تخرج بصفرِ أفكار. وغيابُ السياق لا يمحو الفكرة؛ يجعلها **ناقصةً معلنةً**.
#
# فالمستوى يُقال في البيانات، ولا يُترك للقارئ يستنتجه.

#: **فكرةٌ مؤصَّلة، وسياقُها ناقص** — تُعرض ولا يُدَّعى أنّها جاهزة.
LEVEL_IDEA_ONLY: Final = "idea_only"
#: **مؤصَّلةٌ ومعها سياقُ التطوير**: بناءٌ وعيّنة.
LEVEL_CONTEXT_COMPLETE: Final = "context_complete"
DISCOVERY_LEVELS: Final = (LEVEL_IDEA_ONLY, LEVEL_CONTEXT_COMPLETE)

#: المرتكزُ العلميّ الذي قامت عليه الفكرة — **واحدٌ منها لازم**.
#:
#: **و«نتيجة» لا «نتيجةٌ رئيسة».** كانت القيمة `primary_finding`، و`results`
#: الكنسيّة تُغذّيها ثلاثةُ حقول: `primary_findings` و`hypothesis_results`
#: و`qualitative_themes`. فثيمةٌ كيفيةٌ كانت تُوسَم «نتيجةً رئيسة» — وسمٌ
#: يقرؤه الباحثُ خبرًا عن نوع دليله، وهو خطأ في اثنتين من ثلاث.
BASIS_RESULT: Final = "result"
BASIS_QUESTION: Final = "research_question"
#: **والفرضيةُ مرتكزٌ قائمٌ بذاته** — لا تُقلب نتيجةً ولا تُعاد صياغتها سؤالًا.
BASIS_HYPOTHESIS: Final = "hypothesis"
BASIS_INSTRUMENT: Final = "instrument"
BASIS_QUALITATIVE: Final = "qualitative_theme"
BASIS_NULL_RESULT: Final = "null_or_unexpected_result"
DISCOVERY_BASES: Final = (
    BASIS_RESULT, BASIS_QUESTION, BASIS_HYPOTHESIS, BASIS_INSTRUMENT,
    BASIS_QUALITATIVE, BASIS_NULL_RESULT,
)

#: ما ينقص **من سياق التطوير** — لا من المرتكز.
#:
#: والمرتكزُ يُقال في `basis` لا هنا: فكرةٌ قامت على سؤالٍ ليست «ناقصةَ
#: سؤال». وهذه القائمةُ تصف ما يلزم لتطويرها بأمان، وهو ما عرّفته الطبقةُ
#: الثانية: بناءٌ وعيّنة.
MISSING_CONSTRUCTS: Final = "constructs"
MISSING_SAMPLE: Final = "sample"
MISSING_CONTEXT_KINDS: Final = (MISSING_CONSTRUCTS, MISSING_SAMPLE)


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
    #: **هل العنوانُ دليلٌ علميّ أم تسميةٌ للسياق؟**
    #:
    #: والعنوانُ لا يُنشئ مقترحًا في الحالين — انظر `_marker_haystack`. وهذه
    #: الرايةُ للتدقيق والوضوح: عنوانُ سياقٍ مصدرُه حقيقةٌ `SUPPORT_ONLY`
    #: يُسمّي مقترحًا قام على دليلٍ آخر، ولا يُقرأ شاهدًا على شيء.
    title_is_scientific_evidence: bool = False
    questions: tuple[str, ...] = ()
    hypotheses: tuple[str, ...] = ()
    #: ‏**(معرّف الحقيقة، النصّ)** للأسئلة والفرضيات — تتبُّعُ المصدر.
    #:
    #: و`questions` أعلاه نصوصٌ وحدها، فكانت الفكرةُ القائمةُ على سؤالٍ
    #: **لا تعرف أيَّ `FactCandidate` سوّغها** — بينما النتائجُ تحفظ
    #: معرّفاتِها منذ البداية. وفقدُ المعرّف فقدُ سلسلةِ الإسناد: لا اقتباسَ
    #: يُعاد إليه، ولا موضعَ يُفتح للباحث.
    #:
    #: **ولا يُحشر معرّفُ سؤالٍ في `result_refs`**: ذاك عمودُ نتائج، وخلطُه
    #: يجعل فكرةً بلا نتيجةٍ تبدو كأنّ لها واحدة.
    question_refs: tuple[tuple[str, str], ...] = ()
    hypothesis_refs: tuple[tuple[str, str], ...] = ()
    results: tuple[tuple[str, str], ...] = ()      # (result_id, label)
    instruments: tuple[tuple[str, str], ...] = ()  # (instrument_id, label)
    variables: tuple[str, ...] = ()
    #: **معرّفاتُ حقائقِ البُنى الحقيقية** — لا نصوصُها.
    #:
    #: و`variables` أعلاه نصوصٌ تُعرض ويُعدّ بها؛ وهذه مراجعُ تُحفظ في
    #: `PublicationOpportunity.variable_refs` فتُردّ إلى `FactCandidate`
    #: قائم. والمساران القديمان يكتبان النصَّ هناك — عيبُ إسنادٍ سابقٌ
    #: لهذا التغيير، ولم يُوسَّع إليه المدى.
    construct_refs: tuple[str, ...] = ()
    sample_ids: tuple[str, ...] = ()
    qualitative_phases: tuple[str, ...] = ()
    null_result_ids: tuple[str, ...] = ()
    published_result_ids: tuple[str, ...] = ()
    #: **أمراجعُ هذه الوقائع `FactCandidate` كنسيّة؟**
    #:
    #: والمسارُ القديم (`ThesisSection`/`ThesisResult`) يُمرّر معرّفاتِ صفوفه
    #: هو، وهي ليست حقائقَ مرشّحة: لا اقتباسَ لها ولا موضعَ ولا مقطع. ففكرةُ
    #: اكتشافٍ مبنيّةٌ عليها **لا تستطيع أن تُثبت إسنادها** — وإثباتُ الإسناد
    #: شرطُ الاكتشاف لا زينتُه.
    #:
    #: **وفيه عيبٌ آخر أقدم:** المسارُ القديم يكتب `sample_ids={thesis_id}`،
    #: أي يجعل معرّفَ الرسالة عيّنةً لها. فلو جرى الاكتشافُ عليه لقال
    #: «سياقُ العيّنة مكتمل» عن عيّنةٍ لا وجود لها. ولا يُصلَح ذاك هنا —
    #: يُحاط: الاكتشافُ للكنسيّ وحده، والقديمُ يبقى كما كان بلا زيادة.
    evidence_is_canonical: bool = True


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
    #: **معرّفاتُ الحقائق التي سوّغت هذه الفكرة** — أيًّا كان حقلُها.
    #:
    #: و`result_refs` عمودُ نتائجَ بعينها، فلا يُحشر فيه معرّفُ سؤال. وهذا
    #: عامٌّ: به تُردّ كلُّ فكرةٍ إلى `FactCandidate` قائم، ومنه إلى مقطعه
    #: واقتباسِه وموضعه.
    source_fact_refs: list[str] = field(default_factory=list)
    #: مستوى الاكتشاف ومرتكزُه وما ينقص من سياقه — تُقال، ولا تُستنتج.
    discovery_level: str = LEVEL_CONTEXT_COMPLETE
    discovery_basis: str = BASIS_RESULT
    missing_context: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.opportunity_kind not in OPPORTUNITY_KINDS:
            raise ValueError(f"unknown opportunity kind: {self.opportunity_kind}")
        if self.paper_kind not in PAPER_KINDS:
            raise ValueError(f"unknown paper kind: {self.paper_kind}")
        if self.discovery_level not in DISCOVERY_LEVELS:
            raise ValueError(f"unknown discovery level: {self.discovery_level}")
        if self.discovery_basis not in DISCOVERY_BASES:
            raise ValueError(f"unknown discovery basis: {self.discovery_basis}")
        for gap in self.missing_context:
            if gap not in MISSING_CONTEXT_KINDS:
                raise ValueError(f"unknown missing-context kind: {gap}")
        # **ولا فكرةَ بلا مصدر.** فكرةٌ لا تعرف ما سوّغها لا تُثبت إسنادها،
        # ولا يستطيع الباحثُ أن يسألها: «من أين جئتِ؟»
        if not self.source_fact_refs:
            raise ValueError(
                f"an opportunity draft must name the facts that justify it "
                f"(kind={self.opportunity_kind!r})")
        # واتّساقُ المستوى مع ما ينقص — فلا «مكتملة» ومعها نقص.
        complete = not self.missing_context
        if complete != (self.discovery_level == LEVEL_CONTEXT_COMPLETE):
            raise ValueError(
                f"discovery level {self.discovery_level!r} contradicts "
                f"missing_context {self.missing_context!r}")


_SCALE_MARKERS = re.compile(r"(مقياس|استبانة جديدة|أداة مطورة|scale|instrument development)",
                            re.IGNORECASE)
_ANTECEDENT_MARKERS = re.compile(r"(محددات|مسببات|العوامل المؤثرة|antecedents|determinants)",
                                 re.IGNORECASE)
_CONSEQUENCE_MARKERS = re.compile(r"(آثار|نتائج مترتبة|تبعات|consequences|outcomes)",
                                  re.IGNORECASE)
_COMPARATIVE_MARKERS = re.compile(r"(مقارنة|الفروق بين|comparative|differences between)",
                                  re.IGNORECASE)


def context_gaps(facts: ThesisFacts) -> list[str]:
    """ما ينقص من **سياق التطوير** — بناءٌ وعيّنة، لا المرتكز.

    وهو شرطُ الطبقة الثانية بعينه، مقروءًا نقصًا بدل أن يكون بوّابةً صامتة.
    """
    gaps: list[str] = []
    if not facts.construct_refs:
        gaps.append(MISSING_CONSTRUCTS)
    if not facts.sample_ids:
        gaps.append(MISSING_SAMPLE)
    return gaps


def _level_for(gaps: list[str]) -> str:
    return LEVEL_CONTEXT_COMPLETE if not gaps else LEVEL_IDEA_ONLY


def mine(facts: ThesisFacts) -> list[OpportunityDraft]:
    """يقترح فرصًا مؤصَّلة في عناصر الرسالة. القائمة الفارغة نتيجة صحيحة."""
    drafts: list[OpportunityDraft] = []
    unpublished = [rid for rid, _ in facts.results if rid not in facts.published_result_ids]
    # **ونقصُ السياق يُقاس مرّةً على الرسالة**، ثمّ يُنسَب إلى كلّ مقترح:
    # فهو وصفُ ما استُخرج من الرسالة، لا وصفُ المقترح وحده.
    gaps = context_gaps(facts)
    level = _level_for(gaps)
    questions_by_text = {text: fid for fid, text in facts.question_refs}

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
            # مصدرُه السؤالُ **ونتيجتُه** — ومعرّفُ السؤال من `question_refs`
            # لا من `result_refs`.
            source_fact_refs=(
                ([questions_by_text[question]] if question in questions_by_text else [])
                + list(related)),
            discovery_level=level, discovery_basis=BASIS_QUESTION,
            missing_context=list(gaps),
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
                source_fact_refs=[instrument_id],
                discovery_level=level, discovery_basis=BASIS_INSTRUMENT,
                missing_context=list(gaps),
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
            source_fact_refs=[phase],
            discovery_level=level, discovery_basis=BASIS_QUALITATIVE,
            missing_context=list(gaps),
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
            source_fact_refs=list(facts.null_result_ids),
            discovery_level=level, discovery_basis=BASIS_NULL_RESULT,
            missing_context=list(gaps),
        ))

    # ٩ب — **مقترحٌ محافظٌ واحد حين لا يقوم شكلٌ متخصّص.**
    #
    # رسالةٌ لها نتيجةٌ مستخرَجةٌ مؤهَّلة وعنوانٌ يُسمّيها وبناءٌ أو عيّنة
    # تُعرّفها: عندها ما يكفي لمقترحٍ واحدٍ مؤصَّل، وردُّ صاحبها بصفر خبرٌ
    # كاذب عن رسالةٍ فيها عمل. ويقع **بعد** الأشكال المتخصّصة فلا يزاحمها،
    # و**لا يقع إن قام منها شيء** — فواحدٌ لا اثنان.
    #
    # ولا يقوم على عنوانٍ وحده أبدًا: النتيجةُ شرطٌ فيه. وهو البابُ نفسه
    # الذي أُغلق في `_marker_haystack`، فلا يُفتح من الجهة الأخرى.
    #
    # 5/6/7/9 — محددات، نتائج مترتبة، مقارنة، تحليل ثانوي.
    #
    # **وهذه الأربعة وحدها عنوانُها العامل مشتقٌّ من عنوان الرسالة**، فتُعلَّق
    # حين لا عنوان — ولا يُخترع لها واحد. انظر `_titled_drafts`.
    #
    # **والعنوانُ شرطٌ لتسميتها لا سببٌ لوجودها**: سببُها إشارةٌ في سؤالٍ أو
    # فرضية، أو عيّنةٌ ومتغيّراتٌ ثلاثة. فبعنوانٍ وحده لا يقوم منها شيء.
    drafts += _titled_drafts(facts, unpublished)
    if not drafts:
        drafts += _fallback_drafts(facts, unpublished)
    return drafts


def _fallback_drafts(facts: ThesisFacts, unpublished: list[str]) -> list[OpportunityDraft]:
    """مقترحٌ **واحد** مؤصَّل حين لا يقوم شكلٌ متخصّص — ولا يُشترط عنوان.

    **والعنوانُ تسميةٌ لا أساسٌ علميّ.** اشتراطُه هنا كان يردّ الرسالةَ التي
    بُني هذا المسار لأجلها: أسئلةٌ وبُنًى وعيّنة، بلا عنوانٍ مستخرَج بعد.
    فيُطلب الأساسُ العلميُّ وحده، ويُستعمل العنوانُ سياقًا إن وُجد.

    وطبقتان، **ولا تقعان معًا**:

      ‏(أ) استخلاصٌ مؤصَّل — نتيجةٌ غيرُ منشورة، وبناءٌ، وعيّنة.
      ‏(ب) امتدادٌ مؤصَّل — سؤالٌ، وبناءٌ، وعيّنة. **بلا نتيجة**، ويُقال
          ذلك في تسويغه صراحةً فلا يُقرأ ادّعاءَ نتيجةٍ لا وجود لها.

    ولا واحدةَ منهما تقوم بعنوانٍ وحده: كلتاهما تشترط أساسًا علميًّا
    (نتيجةً أو سؤالًا) **ومعه** بناءٌ وعيّنة. فالبابُ الذي أُغلق في
    `_marker_haystack` يبقى مغلقًا من هذه الجهة أيضًا.
    """
    constructs = list(facts.construct_refs)
    samples = list(facts.sample_ids)
    gaps = context_gaps(facts)

    # ── والسياقُ الناقص لم يعد يمحو الفكرة ──
    #
    # **كان هذا السطرُ `return []`.** بناءٌ وعيّنةٌ معًا شرطًا للوجود، لا
    # للاكتمال. فرسالةٌ فيها نتيجةٌ قويّةٌ مؤصَّلةٌ مؤهَّلةٌ آليًّا، ولم
    # يُستخرَج منها وصفُ عيّنة، كانت تُردّ بصفرِ أفكار — والباحثُ سأل
    # «أيَّ الأوراق يمكن أن تُشتقّ من رسالتي؟» لا «أيُّها جاهزٌ للصياغة؟».
    #
    # فالشرطُ باقٍ **بمعناه في موضعه**: هو ما يفصل `context_complete` عن
    # `idea_only`، لا ما يفصل الوجودَ عن العدم.
    if gaps:
        # **وللكنسيّ وحده**: القديمُ لا يحمل إسنادًا يُثبَت، وعيّنتُه
        # مصطنَعة. فيبقى على ما كان — صفرٌ صادقٌ عنه، لا فكرةٌ لا تُسنَد.
        if not facts.evidence_is_canonical:
            return []
        return _preliminary_draft(facts, unpublished, gaps)

    # ── (أ) استخلاصٌ مؤصَّل: نتيجةٌ قائمة هي الأساس ──
    if unpublished:
        context = f": {facts.title[:60]}" if facts.title else " من نتائج الرسالة"
        return [OpportunityDraft(
            opportunity_kind="sub_model", paper_kind="extraction",
            working_title_ar=f"نموذج فرعي قابل للنشر{context}",
            # **ولا سؤالَ يُنسب إليها ما لم يُختَر سؤالٌ حقيقيّ بعينه.**
            research_question_ar=None,
            rationale_ar="مشتقّة من أدلّة قائمة في الرسالة: نتيجةٌ مستخرَجة "
                         "ومعها بناءٌ وعيّنة. ولا سؤالَ جديدًا ولا نتيجةً مضافة.",
            rationale_en="Derived from evidence already in the thesis: an extracted "
                         "result together with a construct and a sample. It adds no "
                         "new question and no new result.",
            result_refs=list(unpublished),
            variable_refs=constructs,
            sample_refs=samples,
            source_fact_refs=list(unpublished),
            discovery_level=LEVEL_CONTEXT_COMPLETE, discovery_basis=BASIS_RESULT,
            missing_context=[],
        )]

    # ── (ب) امتدادٌ مؤصَّل: سؤالٌ مستخرَجٌ هو الأساس، ولا نتيجةَ تُدَّعى ──
    if not facts.question_refs:
        return _hypothesis_draft(facts, gaps=[])
    question_id, question = facts.question_refs[0]
    return [OpportunityDraft(
        opportunity_kind="extension", paper_kind="extension",
        working_title_ar=f"امتداد بحثي للسؤال: {question[:80]}",
        research_question_ar=question,
        # **وصدقُ هذا التسويغ هو ما يجعل فرصةً بلا نتيجةٍ مدافَعًا عنها.**
        rationale_ar="فرصةُ امتدادٍ **مبدئية**، مؤصَّلة في سؤالٍ مستخرَج من "
                     "الرسالة ومعه بُنًى وعيّنة. **ولا تدّعي أنّ الرسالة "
                     "تحمل نتيجةً لهذا الامتداد**؛ وقد يلزمها تحقّقٌ من "
                     "الأدب المنشور أو تحليلٌ إضافي.",
        rationale_en="A preliminary extension opportunity, grounded in a question "
                     "extracted from the thesis together with its constructs and "
                     "sample. It does not claim the thesis already contains a result "
                     "for this extension; literature validation or further analysis "
                     "may be required.",
        # **ولا نتيجةَ تُدَّعى**: العمودُ فارغٌ صدقًا، والمصدرُ هو السؤال.
        result_refs=[],
        variable_refs=constructs,
        sample_refs=samples,
        source_fact_refs=[question_id],
        discovery_level=LEVEL_CONTEXT_COMPLETE, discovery_basis=BASIS_QUESTION,
        missing_context=[],
    )]


def _hypothesis_draft(
    facts: ThesisFacts, gaps: list[str],
) -> list[OpportunityDraft]:
    """**الفرضيةُ مرتكزٌ علميٌّ قائمٌ بذاته** — حين لا نتيجةَ ولا سؤال.

    وكان العقدُ المُعلَن يعدّها مرتكزًا صالحًا، والتنفيذُ لا يعرف إلّا
    النتيجةَ والسؤال. فرسالةٌ فرضياتُها مستخرَجةٌ مؤهَّلةٌ مؤصَّلة — ولا
    سؤالَ صريحٌ فيها ولا نتيجةٌ بلغت العتبة — تخرج بصفرِ أفكار بينما
    الوثيقةُ تقول إنّها لا تخرج. فالتنفيذُ يلحق بالعقد.

    **ولا تُقلب الفرضيةُ نتيجةً**: `result_refs` يبقى فارغًا، والتسويغُ
    ينفي ادّعاءَ نتيجةٍ صراحةً. **ولا تُعاد صياغتُها سؤالًا**: نصُّها كما
    استُخرج، ومرتكزُها `hypothesis` لا `research_question` — فالوسمُ خبرٌ
    عن نوع الدليل، ومَن قرأ «سؤال» ظنّ أنّ الرسالة سألته.
    """
    if not facts.hypothesis_refs:
        return []
    hypothesis_id, hypothesis = facts.hypothesis_refs[0]
    level = _level_for(gaps)
    incomplete = (
        " **وسياقُها غيرُ مكتمل**: يلزم تأكيدُ العيّنة أو البُنى." if gaps else "")
    incomplete_en = (
        " Its context is incomplete: the sample or constructs need confirmation."
        if gaps else "")
    return [OpportunityDraft(
        opportunity_kind="extension", paper_kind="extension",
        working_title_ar=f"فكرة امتداد مبدئية من فرضية: {hypothesis[:70]}",
        # **ولا تُكتب الفرضيةُ في خانة السؤال**: الرسالةُ لم تسألها سؤالًا.
        research_question_ar=None,
        rationale_ar="فكرةُ ورقةٍ **مبدئية**، مؤصَّلةٌ في **فرضيةٍ** مستخرَجة "
                     "من الرسالة. **ولا تدّعي أنّ الرسالة تحمل نتيجةً مؤهَّلةً "
                     "لهذه الفرضية** — ولا نتيجةَ مؤهَّلةً استُخرجت أصلًا، ولا "
                     "سؤالَ بحثيٍّ صريح." + incomplete,
        rationale_en="A preliminary paper idea, grounded in a hypothesis extracted "
                     "from the thesis. It does not claim the thesis holds an eligible "
                     "result for this hypothesis — no eligible result was extracted "
                     "at all, and no explicit research question either." + incomplete_en,
        # **ولا نتيجةَ تُدَّعى.**
        result_refs=[],
        variable_refs=list(facts.construct_refs),
        sample_refs=list(facts.sample_ids),
        source_fact_refs=[hypothesis_id],
        discovery_level=level, discovery_basis=BASIS_HYPOTHESIS,
        missing_context=list(gaps),
    )]


def _preliminary_draft(
    facts: ThesisFacts, unpublished: list[str], gaps: list[str],
) -> list[OpportunityDraft]:
    """**فكرةٌ واحدةٌ محافظة حين يقوم المرتكزُ وينقص السياق.**

    وواحدةٌ لا أكثر: بابُ الاكتشاف ليس بابَ توليدٍ تخميني. وتقع بعد كلّ
    شكلٍ متخصّص ولا تقع إن قام منها شيء — فلا تُكرَّر فكرةٌ قائمة.

    ومفرداتُها `extension` لا `sub_model`: الثانيةُ تَعِد بنموذجٍ فرعيٍّ
    مكتمل، وهذه مبدئيّةٌ بإقرارها. والنقصُ يُقال في `missing_context`
    ويُكتب في بيانات الفرصة، فلا يُقرأ اكتمالًا.
    """
    if unpublished:
        # ‏(ج١) نتيجةٌ مؤهَّلةٌ قائمة — والسياقُ وحده ناقص.
        anchor = facts.title[:60] if facts.title else "نتيجةٍ مستخرَجة"
        return [OpportunityDraft(
            opportunity_kind="extension", paper_kind="extension",
            working_title_ar=f"فكرة ورقة مبدئية من {anchor}",
            research_question_ar=None,
            rationale_ar="فكرةُ ورقةٍ **مبدئية**، مؤصَّلةٌ في نتيجةٍ مستخرَجة "
                         "من الرسالة. **وسياقُها غيرُ مكتمل**: يلزم تأكيدُ "
                         "العيّنة أو البُنى قبل التطوير، ولم يُفترض منها شيء.",
            rationale_en="A preliminary paper idea, grounded in a finding extracted "
                         "from the thesis. Its context is incomplete: the sample or "
                         "constructs need confirmation before development, and "
                         "nothing about them has been assumed.",
            result_refs=list(unpublished),
            variable_refs=list(facts.construct_refs),
            sample_refs=list(facts.sample_ids),
            source_fact_refs=list(unpublished),
            discovery_level=LEVEL_IDEA_ONLY, discovery_basis=BASIS_RESULT,
            missing_context=list(gaps),
        )]

    # ‏(ج٢) سؤالٌ مؤهَّلٌ قائم، ولا نتيجةَ — ويُقال ذلك صراحةً.
    if not facts.question_refs:
        # ‏(ج٣) ولا سؤالَ كذلك — فالفرضيةُ مرتكزٌ ثالث.
        return _hypothesis_draft(facts, gaps)
    question_id, question = facts.question_refs[0]
    return [OpportunityDraft(
        opportunity_kind="extension", paper_kind="extension",
        working_title_ar=f"فكرة امتداد مبدئية للسؤال: {question[:70]}",
        research_question_ar=question,
        rationale_ar="فكرةُ امتدادٍ **مبدئية**، مؤصَّلةٌ في سؤالٍ مستخرَج من "
                     "الرسالة. **ولا تدّعي أنّ الرسالة تحمل نتيجةً لهذا "
                     "السؤال** — ولا نتيجةَ مؤهَّلةً استُخرجت أصلًا. "
                     "**وسياقُها غيرُ مكتمل**: يلزم تأكيدُ العيّنة أو البُنى.",
        rationale_en="A preliminary extension idea, grounded in a question extracted "
                     "from the thesis. It does not claim the thesis holds a result "
                     "for this question — no eligible result was extracted at all. "
                     "Its context is incomplete: the sample or constructs need "
                     "confirmation.",
        result_refs=[],
        variable_refs=list(facts.construct_refs),
        sample_refs=list(facts.sample_ids),
        source_fact_refs=[question_id],
        discovery_level=LEVEL_IDEA_ONLY, discovery_basis=BASIS_QUESTION,
        missing_context=list(gaps),
    )]


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
    """الإشاراتُ تُقرأ من **الدليل العلميّ وحده** — لا من العنوان.

    **وكان العنوانُ داخلًا فيه، فكان يُنشئ فرصةً بنفسه.** رسالةٌ عنوانُها
    «أثر كذا في كذا» تحمل إشارةَ «المحدّدات» في عنوانها؛ فإن لم يكن معها
    سؤالٌ ولا فرضية ولا نتيجة، خرج منها مقترحٌ كاملٌ مصدرُه اسمُها. وذاك
    اكتشافُ فرصةٍ من لا شيء.

    والعنوانُ يبقى تسميةً للمقترح — يُقتبس في `working_title_ar` — ولا يبقى
    سببًا لوجوده. `" ".join` على `None` يسقط بـ`TypeError`، فيُصفّى الغائب.
    """
    return " ".join(part for part in (*facts.questions, *facts.hypotheses) if part)


def _secondary_analysis_fits(facts: ThesisFacts) -> bool:
    return bool(facts.sample_ids) and len(facts.variables) >= 3


def _titled_drafts(facts: ThesisFacts, unpublished: list[str]) -> list[OpportunityDraft]:
    if not facts.title:
        return []
    haystack = _marker_haystack(facts)
    gaps = context_gaps(facts)
    level = _level_for(gaps)
    # **ومرتكزُ هذه الأربعة إشارةٌ في سؤالٍ أو فرضية، أو بُنًى وعيّنة** —
    # لا العنوان. فمصدرُها ما قام عليه فعلًا: نتائجُها إن وُجدت، وإلّا
    # أسئلتُها وفرضياتُها. ولا تقوم على عنوانٍ وحده (انظر `_marker_haystack`).
    anchors = list(unpublished) or [fid for fid, _ in facts.question_refs] \
        or [fid for fid, _ in facts.hypothesis_refs]
    basis = BASIS_RESULT if unpublished else BASIS_QUESTION
    drafts = [
        OpportunityDraft(
            opportunity_kind=kind, paper_kind="extraction",
            working_title_ar=f"{label}: {facts.title[:60]}",
            research_question_ar=None,
            rationale_ar="ورد في الرسالة ما يشير إلى هذا المسار صراحةً.",
            rationale_en="The thesis explicitly signals this line of enquiry.",
            result_refs=list(unpublished), variable_refs=list(facts.variables),
            sample_refs=list(facts.sample_ids),
            source_fact_refs=list(anchors),
            discovery_level=level, discovery_basis=basis,
            missing_context=list(gaps),
        )
        for pattern, kind, label in _TITLED_KINDS
        if pattern.search(haystack) and anchors
    ]
    if _secondary_analysis_fits(facts) and anchors:
        drafts.append(OpportunityDraft(
            opportunity_kind="secondary_analysis", paper_kind="extension",
            working_title_ar=f"تحليل ثانوي على بيانات: {facts.title[:60]}",
            research_question_ar=None,
            rationale_ar="تسمح البيانات بسؤال جديد لم تختبره الرسالة.",
            rationale_en="The data supports a new question the thesis did not test.",
            variable_refs=list(facts.variables), sample_refs=list(facts.sample_ids),
            source_fact_refs=list(anchors),
            discovery_level=level, discovery_basis=basis,
            missing_context=list(gaps),
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
