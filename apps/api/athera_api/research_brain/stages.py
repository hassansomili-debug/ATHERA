"""رحلةُ البحث تسعَ مراحل | The nine-stage research journey (RC-0).

**الغرض: أن تبدو المنصّةُ منتجًا واحدًا**، لا مجموعةَ وحداتٍ يعرف الباحثُ
أسماءَها الداخلية. فيُسأل عن كلّ بحثٍ خمسةُ أسئلة — أين أنت، وماذا أُنجز،
وما الناقص، وما التالي، ولماذا — وتُشتقّ الأجوبةُ من حال البحث المسجَّلة
وحدَها.

## والاكتمالُ يعني شيئًا

أخطرُ ما يُكتب في ملفٍّ كهذا أن يُعدّ **وجودُ صفٍّ** إنجازًا:

    مصدرٌ مربوط    ≠  الدراساتُ السابقة قُرئت
    مجموعةُ بيانات  ≠  التحليلُ تمّ
    مخطوطةٌ قائمة   ≠  الورقةُ كُتبت
    منهجٌ مسجَّل    ≠  التصميمُ مكتمل

ومنظومةٌ تفعل ذلك تُخبر الباحثَ أنّه أنجز ما لم يبدأه، فيبني عليه. فكلُّ
مرحلةٍ هنا تُعلن **ما الذي يجعلها مكتملة** بمفردات مجالها، ولا تكتفي بعدٍّ.

## ولا نسبةَ إنجاز

لا «٧٣٪». والبحثُ ليس له مقامٌ كونيّ: كم مرحلةً في دراسةٍ كيفيةٍ
استكشافية؟ فتُسمّى الحالُ بأسمائها، وهي أصدقُ وأنفعُ معًا.

## والمنهجُ لا يُفترَض

الأداةُ والبياناتُ ليستا شرطًا على كلّ بحث. ودراسةٌ كيفيةٌ لا تلزمها أداةُ
قياس، ومراجعةٌ منهجية لا يلزمها استبيان. فما لم يُسجَّل المنهجُ تبقى
هاتان **اختياريّتين** — ولا يُستنبط المنهجُ من وجود بيانات (§51): وجودُ
ملفٍّ لا يجعل البحثَ كمّيًّا.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Final

from pydantic import BaseModel, ConfigDict, Field


class StageKey(str, Enum):
    """المراحلُ التسع — وهي سقفُ ما يُعرض في المسار الرئيس.

    وأربعَ عشرةَ مرحلةً دقيقةً في شريطٍ واحد تُخفي الرحلةَ بدل أن تُظهرها.
    فالتفصيلُ يسكن في وحدته، والمسارُ الرئيس تسعةٌ لا أكثر.
    """

    IDEA = "idea"
    REFERENCES = "references"
    LITERATURE = "literature"
    SYNTHESIS = "synthesis"
    DESIGN = "design"
    INSTRUMENT = "instrument"
    DATA = "data"
    ANALYSIS = "analysis"
    PAPER = "paper"


#: ترتيبُ العرض — ثابتٌ لا يتبع ترتيبَ الإعلان ولا قاموسًا.
ORDER: Final[tuple[StageKey, ...]] = (
    StageKey.IDEA, StageKey.REFERENCES, StageKey.LITERATURE, StageKey.SYNTHESIS,
    StageKey.DESIGN, StageKey.INSTRUMENT, StageKey.DATA, StageKey.ANALYSIS,
    StageKey.PAPER,
)


class StageStatus(str, Enum):
    """حالُ المرحلة — خمسٌ، ولكلٍّ معنًى لا يشاركه غيرُه.

    **و«الحاليّة» ليست منها.** كانت سادسةً تُكتب مكان الحال الحقيقية، فكان
    أوّلُ ما لم يكتمل يُعرض «حاليًّا» وتضيع معرفةُ **هل بُدئ أم لا**:
    مخطوطةٌ كُتبت ولم تُعتمد ومخطوطةٌ لم توجد أصلًا تصيران سواءً في الجواب.
    فالموضعُ من الرحلة علمٌ آخر — `Stage.is_current` — والحالُ تبقى صادقة.
    """

    #: تمّت بمعنى مجالها — لا بوجود صفّ.
    COMPLETED = "completed"
    #: بُدئت ولم تتمّ.
    NEEDS_ACTION = "needs_action"
    #: لم تُبدأ بعد.
    NOT_STARTED = "not_started"
    #: لا يمكن المضيّ فيها، ومعها سببٌ مسمًّى.
    BLOCKED = "blocked"
    #: نافعةٌ ولا تلزم هذا البحث.
    OPTIONAL = "optional"


#: الطريقُ إلى الوحدة الأصلية — بلا لغة؛ تُركّبها الواجهةُ من موضعها.
#:
#: **ولا تُبنى الوحدةُ داخل الرحلة**: الرحلةُ تدلّ، والعملُ يقع في أداته.
ROUTE: Final[dict[StageKey, str]] = {
    StageKey.IDEA: "/portfolio/{project_id}/thread",
    # **وقسمُ المصادر لا صفحةُ الرحلة نفسُها.** كان يقصد
    # `/portfolio/{project_id}` — وهي الصفحةُ التي يقف عليها الباحثُ أصلًا،
    # فينقر «أضف مراجع» فيعود إلى مكانه. وأدواتُ المصادر قائمةٌ في قسم
    # «الدراسات السابقة» من الصفحة نفسِها، فيُقصد بعينه.
    StageKey.REFERENCES: "/portfolio/{project_id}?section=literature",
    StageKey.LITERATURE: "/portfolio/{project_id}/matrix",
    StageKey.SYNTHESIS: "/portfolio/{project_id}/gaps",
    StageKey.DESIGN: "/portfolio/{project_id}/thread",
    StageKey.INSTRUMENT: "/portfolio/{project_id}/thread",
    StageKey.DATA: "/analysis",
    StageKey.ANALYSIS: "/analysis",
    StageKey.PAPER: "/manuscripts",
}

#: عناوينُ المراحل — بلغتين، ومن مفردات الباحث لا من مفردات الجداول.
TITLES: Final[dict[StageKey, tuple[str, str]]] = {
    StageKey.IDEA: ("الفكرة", "Idea"),
    StageKey.REFERENCES: ("المراجع", "References"),
    StageKey.LITERATURE: ("الدراسات السابقة", "Literature"),
    StageKey.SYNTHESIS: ("التركيب والفجوة", "Synthesis & gap"),
    StageKey.DESIGN: ("تصميم البحث", "Research design"),
    StageKey.INSTRUMENT: ("أداة الدراسة", "Instrument"),
    StageKey.DATA: ("البيانات", "Data"),
    StageKey.ANALYSIS: ("التحليل", "Analysis"),
    StageKey.PAPER: ("الورقة", "Paper"),
}

#: **نداءُ الفعل لكلّ مرحلة** — فعلٌ يُطلب لا اسمُ مرحلةٍ يُعاد.
#:
#: والباحثُ يُقال له «أضف مراجع» لا «المراجع»: الاسمُ يصف موضعًا، والنداءُ
#: يقول ما يفعل. وهو ما يظهر في الفعل الرئيس تحت «الخطوة التالية».
CTA: Final[dict[StageKey, tuple[str, str]]] = {
    StageKey.IDEA: ("حدِّد سؤال البحث", "Define the research question"),
    StageKey.REFERENCES: ("أضف مراجع للبحث", "Add references"),
    StageKey.LITERATURE: ("راجِع الدراسات السابقة", "Review the literature"),
    StageKey.SYNTHESIS: ("استخرج الفجوة البحثية", "Identify the research gap"),
    StageKey.DESIGN: ("ابدأ تصميم البحث", "Start the research design"),
    StageKey.INSTRUMENT: ("أنشئ أداة الدراسة", "Create the instrument"),
    StageKey.DATA: ("أضف بيانات البحث", "Add your research data"),
    StageKey.ANALYSIS: ("ابدأ التحليل", "Start the analysis"),
    StageKey.PAPER: ("ابدأ كتابة الورقة", "Start writing the paper"),
}

#: رموزُ المنع — ثابتةٌ للآلة، وتُترجَم في طبقة العرض (§69).
NEEDS_QUESTION: Final = "research_question_missing"
NEEDS_SOURCES: Final = "no_sources_linked"
NEEDS_LITERATURE: Final = "no_literature_read"
NEEDS_DESIGN: Final = "method_not_selected"
NEEDS_DATA: Final = "no_data_available"
NEEDS_ANALYSIS_OUTPUT: Final = "no_analysis_output"


@dataclass(frozen=True, slots=True)
class StageFacts:
    """وقائعُ البحث التي تُشتقّ منها المراحل — **عدٌّ لا تفسير**.

    تُقرأ من الوحدات صاحبةِ الحقيقة في `services/`، وتصل هنا أرقامًا
    وحالات. فتُختبر كلُّ مرحلةٍ بلا قاعدة بيانات — وهو الحدُّ الذي تقوم
    عليه هذه الحزمة كلُّها.
    """

    # ── الفكرة ──
    questions: int = 0
    objectives: int = 0

    # ── المراجع ──
    sources_linked: int = 0
    #: **قرارٌ لا تخزين**: «مُدرَج» حكمٌ له صاحبٌ ووقت، و«محفوظ» ليس كذلك.
    sources_included: int = 0
    sources_full_text: int = 0

    # ── الدراسات السابقة ──
    matrix_sources: int = 0
    #: خلايا بلغت حالَ `known` — أي قُرئت فعلًا لا فُتحت.
    matrix_cells_known: int = 0

    # ── التركيب والفجوة ──
    themes: int = 0
    contradictions: int = 0
    gaps: int = 0

    # ── تصميم البحث ──
    has_method_row: bool = False
    study_type: str | None = None
    design_family: str | None = None
    theories: int = 0
    constructs: int = 0
    variables: int = 0

    # ── أداة الدراسة ──
    instruments: int = 0
    #: **أداةٌ بلا بنودٍ قشرة** — والبندُ هو ما يقيس (§95).
    instrument_items: int = 0

    # ── البيانات ──
    datasets: int = 0

    # ── التحليل ──
    analysis_runs: int = 0
    analysis_outputs: int = 0
    #: نتيجةٌ مسجَّلة — ولا تُعدّ إلا إن أنتجتها تشغيلة (§36).
    findings: int = 0

    # ── الورقة ──
    manuscripts: int = 0
    sections_with_text: int = 0
    sections_approved: int = 0

    # ── ما يعترض ──
    unresolved_conflicts: tuple[str, ...] = field(default_factory=tuple)

    @property
    def method_recorded(self) -> bool:
        """**المنهجُ مسجَّلٌ فعلًا** — لا صفُّ منهجٍ فارغ."""
        return self.has_method_row and bool(self.study_type)

    @property
    def measurement_expected(self) -> bool:
        """أيُنتظَر لهذا البحث أداةُ قياس؟

        **ولا يُخمَّن**: ما لم يُسجَّل المنهجُ فالجوابُ لا — فتبقى الأداةُ
        اختياريّة. وإدراجُها شرطًا على بحثٍ لا يُعرف منهجُه يوقف دراسةً
        كيفيةً بحجّةٍ لا تخصّها.
        """
        return self.study_type in ("quantitative", "experimental", "mixed_methods")


class Stage(BaseModel):
    """مرحلةٌ واحدة بحالها وسببها وملخّصها.

    **ولا رمزَ داخليّ في وجه الباحث** (§18): `key` للآلة، والعنوانُ
    والسببُ نصٌّ للإنسان، ولا يُعرض اسمُ جدولٍ ولا عمود.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: StageKey
    status: StageStatus

    title_ar: str = Field(min_length=1)
    title_en: str = Field(min_length=1)
    #: لماذا هذه الحال — ويُملأ دائمًا، فلا حالَ بلا تفسير.
    reason_ar: str = Field(min_length=1)
    reason_en: str = Field(min_length=1)
    #: ملخّصٌ قصيرٌ صادق — «٣ مصادر مرتبطة». ولا مقاييسُ داخلية (§47).
    summary_ar: str = ""
    summary_en: str = ""

    #: **هنا يقف الباحثُ الآن** — علمٌ مستقلّ عن الحال لا بديلٌ عنها.
    is_current: bool = False
    #: نداءُ الفعل — «أضف مراجع» لا «المراجع».
    cta_ar: str = Field(min_length=1)
    cta_en: str = Field(min_length=1)

    route: str | None = None
    #: رموزُ ما يمنع — تُترجَم في طبقة العرض، ومع `BLOCKED` وحدها.
    blocking_reasons: tuple[str, ...] = ()

    def model_post_init(self, _context: object) -> None:
        """**والمنعُ يُسمّى.** مرحلةٌ متوقّفة بلا سببٍ مكتوب طريقٌ مسدود."""
        if self.status is StageStatus.BLOCKED and not self.blocking_reasons:
            raise ValueError(f"{self.key.value}: مرحلةٌ متوقّفة بلا سببٍ مسمّى")
        if self.status is not StageStatus.BLOCKED and self.blocking_reasons:
            raise ValueError(f"{self.key.value}: أسبابُ منعٍ على مرحلةٍ غيرِ متوقّفة")


@dataclass(frozen=True, slots=True)
class _Verdict:
    """حكمُ مرحلةٍ قبل أن يُعرف موضعُها من الرحلة."""

    status: StageStatus
    why_ar: str
    why_en: str
    summary_ar: str = ""
    summary_en: str = ""
    blocking: tuple[str, ...] = ()
    #: **ولا وجهةَ حين لا تستطيع المنصّةُ تنفيذ العمل بعد.**
    #:
    #: فرقٌ بين «هذا العملُ باقٍ عليك» و«اضغط هنا لتفعله»: الثانيةُ وعدٌ
    #: بمسارٍ قائم. ومرحلةٌ صادقةٌ في نصّها تقول «لا نُمثّل هذه المادّة
    #: بعد» ثمّ تعرض زرًّا يفتح أداةً لا تقبلها تنقض نصَّها بزرّها.
    routable: bool = True


def _idea(f: StageFacts) -> _Verdict:
    if f.questions == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لا سؤالَ بحثٍ مسجَّلٌ لهذا المشروع بعد.",
            "No research question is recorded for this project yet.")
    return _Verdict(
        StageStatus.COMPLETED,
        f"سؤالُ البحث مسجَّل ({f.questions}).",
        f"The research question is recorded ({f.questions}).",
        f"{f.questions} سؤال بحث" + (f" · {f.objectives} هدف" if f.objectives else ""),
        f"{f.questions} research question(s)"
        + (f" · {f.objectives} objective(s)" if f.objectives else ""))


def _references(f: StageFacts) -> _Verdict:
    """**والمرجعُ المحفوظ ليس مرجعًا مُدرَجًا.**

    «مُدرَج» قرارٌ له صاحبٌ ووقت في `project_sources`، و«محفوظ فقط» تخزينٌ
    لم يقرّره أحد. فاكتمالُ المرحلة يعلّق على الأول لا على العدّ.
    """
    if f.sources_linked == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لا مصدرَ مربوطٌ بهذا البحث.",
            "No source is linked to this project.")
    summary_ar = f"{f.sources_linked} مصدر مرتبط"
    summary_en = f"{f.sources_linked} source(s) linked"
    if f.sources_full_text:
        summary_ar += f" · {f.sources_full_text} بنصّ كامل"
        summary_en += f" · {f.sources_full_text} with full text"
    if f.sources_included == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "المصادرُ محفوظةٌ ولم يُقرَّر إدراجُ أيٍّ منها في هذا البحث.",
            "Sources are saved but none has been decided as included in this project.",
            summary_ar, summary_en)
    return _Verdict(
        StageStatus.COMPLETED,
        f"{f.sources_included} مصدرًا مُدرَجًا بقرارٍ مسجَّل.",
        f"{f.sources_included} source(s) included by a recorded decision.",
        summary_ar + f" · {f.sources_included} مُدرَج",
        summary_en + f" · {f.sources_included} included")


def _literature(f: StageFacts) -> _Verdict:
    """**ووجودُ المصادر لا يجعل الدراساتِ مقروءة** (§27).

    الاكتمالُ هنا خلايا بلغت `known` — أي استُخرجت وقُرئت — لا ملفّاتٌ
    رُفعت.
    """
    if f.sources_linked == 0:
        return _Verdict(
            StageStatus.BLOCKED,
            "لا مصادرَ في هذا البحث تُقرأ.",
            "There are no sources in this project to read.",
            blocking=(NEEDS_SOURCES,))
    if f.matrix_cells_known == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لم تُستخرَج بعد معلوماتٌ من الدراسات المرتبطة.",
            "No information has been extracted from the linked studies yet.",
            f"{f.sources_linked} مصدر بانتظار القراءة",
            f"{f.sources_linked} source(s) awaiting reading")
    return _Verdict(
        StageStatus.COMPLETED,
        f"استُخرجت معلوماتٌ مقروءةٌ من {f.matrix_sources} دراسة.",
        f"Information has been extracted from {f.matrix_sources} stud(ies).",
        f"{f.matrix_sources} دراسة مقروءة · {f.matrix_cells_known} معلومة",
        f"{f.matrix_sources} stud(ies) read · {f.matrix_cells_known} field(s)")


def _synthesis(f: StageFacts) -> _Verdict:
    """**ولا تكتمل بوجود دراساتٍ مقروءة** (§29) — بل بمخرَجِ تركيب."""
    if f.matrix_cells_known == 0:
        return _Verdict(
            StageStatus.BLOCKED,
            "لا معلوماتٍ مستخرَجةً من الدراسات يُبنى عليها تركيب.",
            "There is no extracted study information to synthesise.",
            blocking=(NEEDS_LITERATURE,))
    found = f.themes + f.contradictions + f.gaps
    if found == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لم تُستخرَج بعد محاورُ ولا تعارضاتٌ ولا فجوات.",
            "No themes, contradictions, or gaps have been derived yet.")
    summary_ar = f"{f.themes} محور · {f.contradictions} تعارض · {f.gaps} فجوة"
    summary_en = (f"{f.themes} theme(s) · {f.contradictions} contradiction(s) "
                  f"· {f.gaps} gap(s)")
    if f.gaps == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "ثمّة نتائجُ تركيبٍ ولم تُحدَّد فجوةٌ بحثية بعد.",
            "Synthesis output exists but no research gap has been identified yet.",
            summary_ar, summary_en)
    return _Verdict(
        StageStatus.COMPLETED,
        f"حُدِّدت {f.gaps} فجوةٌ بحثية.",
        f"{f.gaps} research gap(s) identified.",
        summary_ar, summary_en)


def _design(f: StageFacts) -> _Verdict:
    """**وصفُّ منهجٍ فارغ ليس تصميمًا** — النوعُ هو ما يُبنى عليه."""
    if f.questions == 0:
        return _Verdict(
            StageStatus.BLOCKED,
            "لا سؤالَ بحثٍ يُصمَّم له.",
            "There is no research question to design for.",
            blocking=(NEEDS_QUESTION,))
    if not f.method_recorded:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لم يُسجَّل المنهجُ لهذا البحث بعد.",
            "No method has been recorded for this project yet.")
    parts_ar = [f"المنهج: {f.study_type}"]
    parts_en = [f"Method: {f.study_type}"]
    if f.theories:
        parts_ar.append(f"{f.theories} إطار نظري")
        parts_en.append(f"{f.theories} theoretical framework(s)")
    if f.constructs:
        parts_ar.append(f"{f.constructs} بناء")
        parts_en.append(f"{f.constructs} construct(s)")
    return _Verdict(
        StageStatus.COMPLETED,
        "المنهجُ مسجَّل، والسؤالُ مرتبطٌ به.",
        "The method is recorded and linked to the research question.",
        " · ".join(parts_ar), " · ".join(parts_en))


def _instrument(f: StageFacts) -> _Verdict:
    """**والأداةُ ليست شرطًا على كلّ بحث** (§33).

    فما لم يُسجَّل منهجٌ يستدعي قياسًا تبقى اختياريّة — ولا يُستنبط المنهج.
    """
    if f.instruments == 0:
        if not f.measurement_expected:
            return _Verdict(
                StageStatus.OPTIONAL,
                ("لا أداةَ مسجَّلة. وليست كلُّ البحوث تحتاج أداةَ قياس، "
                 "ولم يُسجَّل منهجٌ يقتضيها."),
                ("No instrument is recorded. Not every study needs a measurement "
                 "instrument, and no method requiring one is recorded."))
        return _Verdict(
            StageStatus.NOT_STARTED,
            "المنهجُ المسجَّل يقتضي أداةَ قياس، ولا أداةَ بعد.",
            "The recorded method calls for a measurement instrument, and none exists yet.")
    if f.instrument_items == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "الأداةُ مُنشأةٌ بلا بنود — والبندُ هو ما يقيس.",
            "The instrument exists but has no items, and items are what measure.",
            f"{f.instruments} أداة بلا بنود", f"{f.instruments} instrument(s), no items")
    return _Verdict(
        StageStatus.COMPLETED,
        f"الأداةُ مُنشأةٌ وفيها {f.instrument_items} بندًا.",
        f"The instrument exists with {f.instrument_items} item(s).",
        f"{f.instruments} أداة · {f.instrument_items} بند",
        f"{f.instruments} instrument(s) · {f.instrument_items} item(s)")


def _data(f: StageFacts) -> _Verdict:
    """**ولا يُفترض أنّ كلّ بحثٍ له مجموعةُ بيانات** (§34)."""
    if f.datasets == 0:
        if not f.measurement_expected:
            return _Verdict(
                StageStatus.OPTIONAL,
                ("لا بياناتٍ مسجَّلة. ولم يُسجَّل منهجٌ يقتضي مجموعةَ بياناتٍ "
                 "بعينها."),
                ("No data is recorded, and no method requiring a dataset has been "
                 "recorded."))
        return _Verdict(
            StageStatus.NOT_STARTED,
            "المنهجُ المسجَّل يقتضي بيانات، ولا بياناتٍ بعد.",
            "The recorded method calls for data, and none exists yet.")
    return _Verdict(
        StageStatus.COMPLETED,
        f"ثمّة {f.datasets} مجموعةَ بياناتٍ مسجَّلة.",
        f"{f.datasets} dataset(s) recorded.",
        f"{f.datasets} مجموعة بيانات", f"{f.datasets} dataset(s)")


def _analysis(f: StageFacts) -> _Verdict:
    """**والنتيجةُ لا تُعدّ إلا إن أنتجتها تشغيلة** (§36).

    وهذا أخطرُ ثابتٍ في هذا الملفّ: منظومةٌ تعرض «نتائج» بلا مخرَجِ تحليلٍ
    يُشتقّ منه تُعلّم الباحثَ أن يبني ورقةً على رقمٍ لا أصلَ له.

    ## والحجبُ على «مجموعة بيانات» يخصّ المسارَ الكمّيّ وحدَه

    كان هذا يحجب كلَّ تحليلٍ بلا `datasets`، فوقع تناقضٌ في بحثٍ كيفيّ:
    مرحلةُ البيانات **اختياريّة** ومرحلةُ التحليل **متوقّفةٌ لغياب
    البيانات** — والاثنتان معًا لا تستقيمان. وأسوأُ أثرِه أنّ الرحلةَ كانت
    تقفز من تصميم البحث إلى الورقة، كأنّ التحليلَ لا يلزم دراسةً كيفية.

    **والعلاجُ صدقٌ عن القدرة لا نموذجٌ جديد**: المنصّةُ اليوم تُمثّل مادّةَ
    البحث `Dataset` في المسار الكمّيّ، ولا تُمثّل المقابلاتِ والوثائقَ بعد.
    فالتحليلُ في بحثٍ كيفيّ **لم يبدأ** — لا متوقّفًا بحجّةِ أداةٍ كمّية،
    ولا مكتملًا، ولا اختياريًّا يُتخطّى.
    """
    if f.datasets == 0:
        if f.measurement_expected:
            # المسارُ الكمّيّ: لا تحليلَ بلا بياناتٍ فعلًا.
            return _Verdict(
                StageStatus.BLOCKED,
                "لا بياناتٍ صالحةً للتحليل.",
                "No usable data is available to analyse.",
                blocking=(NEEDS_DATA,))
        if f.analysis_runs == 0:
            # **ولا وجهةَ لهذا الفعل.** تشغيلةُ التحليل في هذه المنصّة
            # تلزمها نسخةُ مجموعةِ بيانات (`analysis_runs.dataset_version_id`
            # غيرُ قابلٍ للإفراغ)، فأداةُ التحليل لا تقبل مادّةً كيفية. وزرٌّ
            # يقول «ابدأ التحليل» ويفتحها يَعِد بما لا يقع.
            return _Verdict(
                StageStatus.NOT_STARTED,
                ("لم يبدأ التحليلُ بعد. ولا تُمثِّل المنصّةُ اليوم مادّةَ "
                 "البحث الكيفيّ — كالمقابلات والوثائق — كما تُمثّل مجموعاتِ "
                 "البيانات، فلا أداةَ هنا تُنفّذ هذا العمل بعد."),
                ("Analysis has not started. PUBRIVA does not yet model qualitative "
                 "material — interviews, documents — the way it models datasets, so "
                 "no tool here can carry out this work yet."),
                routable=False)
    if f.analysis_runs == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "البياناتُ متوفّرة ولم تجرِ تشغيلةُ تحليلٍ بعد.",
            "Data is available and no analysis run exists yet.")
    summary_ar = f"{f.analysis_runs} تشغيلة · {f.analysis_outputs} مخرَج"
    summary_en = f"{f.analysis_runs} run(s) · {f.analysis_outputs} output(s)"
    if f.analysis_outputs == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "جرت تشغيلةُ تحليلٍ ولم يُسجَّل لها مخرَج.",
            "An analysis ran and produced no recorded output.",
            summary_ar, summary_en)
    if f.findings == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "ثمّة مخرجاتُ تحليلٍ ولم تُسجَّل نتيجةٌ تُشتقّ منها.",
            "Analysis outputs exist and no finding is derived from them yet.",
            summary_ar, summary_en)
    return _Verdict(
        StageStatus.COMPLETED,
        f"{f.findings} نتيجةً مسجَّلةً مُسنَدةً إلى مخرجات التحليل.",
        f"{f.findings} finding(s) recorded and supported by analysis output.",
        summary_ar + f" · {f.findings} نتيجة",
        summary_en + f" · {f.findings} finding(s)")


def _paper(f: StageFacts) -> _Verdict:
    """**ووجودُ المخطوطة ليس كتابةً لها** (§37)."""
    if f.manuscripts == 0:
        return _Verdict(
            StageStatus.NOT_STARTED,
            "لا مخطوطةَ لهذا البحث بعد.",
            "No manuscript exists for this project yet.")
    if f.sections_with_text == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "المخطوطةُ مُنشأةٌ ولم يُكتب فيها قسمٌ بعد.",
            "The manuscript exists and no section has been written yet.",
            f"{f.manuscripts} مخطوطة بلا نصّ",
            f"{f.manuscripts} manuscript(s), nothing written")
    summary_ar = f"{f.sections_with_text} قسمًا مكتوبًا"
    summary_en = f"{f.sections_with_text} section(s) written"
    if f.sections_approved:
        summary_ar += f" · {f.sections_approved} معتمَدًا"
        summary_en += f" · {f.sections_approved} approved"
    if f.sections_approved == 0:
        return _Verdict(
            StageStatus.NEEDS_ACTION,
            "ثمّة أقسامٌ مكتوبةٌ ولم يُعتمد منها شيء.",
            "Sections are written and none has been approved yet.",
            summary_ar, summary_en)
    return _Verdict(
        StageStatus.COMPLETED,
        f"{f.sections_approved} قسمًا معتمَدًا في المخطوطة.",
        f"{f.sections_approved} approved manuscript section(s).",
        summary_ar, summary_en)


_JUDGES: Final[dict[StageKey, Callable[[StageFacts], _Verdict]]] = {
    StageKey.IDEA: _idea,
    StageKey.REFERENCES: _references,
    StageKey.LITERATURE: _literature,
    StageKey.SYNTHESIS: _synthesis,
    StageKey.DESIGN: _design,
    StageKey.INSTRUMENT: _instrument,
    StageKey.DATA: _data,
    StageKey.ANALYSIS: _analysis,
    StageKey.PAPER: _paper,
}


@dataclass(frozen=True, slots=True)
class JourneyStages:
    """المراحلُ التسع، ومَن منها الحاليّة."""

    stages: tuple[Stage, ...]
    current: StageKey | None

    @property
    def primary(self) -> Stage | None:
        """**الفعلُ الرئيس — من المرحلة الحاليّة، ولا مصدرَ ثانٍ له.**

        وكان هذا موضعَ تناقضٍ حقيقيّ: تقول الشاشةُ «المرحلة: المراجع»
        ويقول زرُّها «حدِّد المنهج» — لأنّ سجلَّ قواعدَ آخر كان يرتّب
        الأفعال بأولوياتٍ مستقلّةٍ عن ترتيب المراحل. ورحلةٌ موحَّدة لا
        تخالف نفسَها.

        فصار الفعلُ الرئيس **هو نداءَ المرحلة الحاليّة** بالبناء: لا يمكن
        أن يفترقا لأنّهما شيءٌ واحد.
        """
        for row in self.stages:
            if row.is_current:
                return row
        return None

    @property
    def secondary(self) -> tuple[Stage, ...]:
        """خطواتٌ أخرى مفتوحة — **بترتيب المراحل نفسِه**، بلا الحاليّة.

        والاختياريّةُ منها تُعرض ولا تُقدَّم، والمتوقّفةُ لا تُعرض فعلًا
        يُدعى إليه.
        """
        return tuple(
            row for row in self.stages
            if not row.is_current
            and row.status in (StageStatus.NEEDS_ACTION, StageStatus.NOT_STARTED,
                               StageStatus.OPTIONAL))

    def by_key(self, key: StageKey) -> Stage:
        for row in self.stages:
            if row.key is key:
                return row
        raise KeyError(key)  # pragma: no cover - المفاتيحُ تسعةٌ مغلقة

    @property
    def completed(self) -> tuple[Stage, ...]:
        return tuple(s for s in self.stages if s.status is StageStatus.COMPLETED)


def derive(facts: StageFacts, *, project_id: str) -> JourneyStages:
    """يشتقّ المراحلَ التسع من الوقائع — **حتميًّا وبترتيبٍ ثابت**.

    و«الحاليّة» أوّلُ مرحلةٍ غيرِ مكتملةٍ وغيرِ اختياريّة (§46). والبحثُ
    ليس خطًّا مستقيمًا دائمًا، لكنّ الباحثَ يحتاج موضعًا واحدًا يبدأ منه —
    وما سواه يبقى معروضًا ومفتوحًا.

    **والمتوقّفةُ تبقى متوقّفة** ولو كانت أوّلَ ما لم يكتمل: تسميتُها
    «الحاليّة» تدعو الباحثَ إلى بابٍ مغلق، وسببُ إغلاقه مرحلةٌ قبلها.
    """
    judged: list[Stage] = []
    current: StageKey | None = None

    for key in ORDER:
        verdict = _JUDGES[key](facts)
        status = verdict.status
        # **والموضعُ أوّلُ ما يمكن العملُ فيه** — لا أوّلُ ما لم يكتمل.
        #
        # فالمتوقّفةُ سببُ إغلاقها مرحلةٌ قبلها، ودعوةُ الباحث إليها دعوةٌ
        # إلى بابٍ مغلق. وتُتخطّى في اختيار الموضع وتبقى معروضةً بحالها.
        here = current is None and status in (StageStatus.NEEDS_ACTION,
                                              StageStatus.NOT_STARTED)
        if here:
            current = key
        judged.append(Stage(
            key=key, status=status, is_current=here,
            title_ar=TITLES[key][0], title_en=TITLES[key][1],
            cta_ar=CTA[key][0], cta_en=CTA[key][1],
            reason_ar=verdict.why_ar, reason_en=verdict.why_en,
            summary_ar=verdict.summary_ar, summary_en=verdict.summary_en,
            route=(ROUTE[key].replace("{project_id}", project_id)
                   if verdict.routable else None),
            blocking_reasons=verdict.blocking))

    return JourneyStages(stages=tuple(judged), current=current)




# ═══════════════ ما يعرفه PUBRIVA، وما ينقص ═══════════════

BLOCKING: Final = "blocking"
RECOMMENDED: Final = "recommended"
OPTIONAL_GAP: Final = "optional"


@dataclass(frozen=True, slots=True)
class KnownFact:
    """واقعةٌ عن البحث — **أو إعلانُ أنّها غيرُ مسجَّلة**.

    و«غير مسجَّل» جوابٌ صحيحٌ يُعرض كما هو (§51). ومنظومةٌ تملأ الفراغَ
    باستنباطٍ معقول — «ثمّة بيانات، إذن البحث كمّي» — تُخبر الباحثَ عن
    بحثه ما لم يقله، ثمّ يبني عليه.
    """

    key: str
    label_ar: str
    label_en: str
    value_ar: str = ""
    value_en: str = ""

    @property
    def known(self) -> bool:
        return bool(self.value_ar)


@dataclass(frozen=True, slots=True)
class MissingItem:
    """ناقصٌ واحد برتبته — **ولا تُكدَّس الرتبُ في قائمةٍ حمراء** (§49).

    فقائمةٌ واحدة تخلط ما يمنع بما يُستحسن تُعلّم الباحثَ تجاهُلَ القائمة
    كلِّها — فيسقط التنبيهُ الصحيح مع الزائد.
    """

    key: str
    label_ar: str
    label_en: str
    severity: str


def known_facts(f: StageFacts) -> tuple[KnownFact, ...]:
    """ما تعرفه المنصّةُ عن هذا البحث — وقائعُ الباحث لا مقاييسُ النظام (§48)."""

    def count(n: int, ar: str, en: str) -> tuple[str, str]:
        return (f"{n} {ar}", f"{n} {en}") if n else ("", "")

    return (
        KnownFact("question", "سؤال البحث", "Research question",
                  *count(f.questions, "سؤال مسجَّل", "recorded")),
        KnownFact("method", "المنهج", "Method",
                  f.study_type or "", f.study_type or ""),
        KnownFact("sources", "المصادر", "Sources",
                  *count(f.sources_linked, "مصدر مرتبط", "linked")),
        KnownFact("instrument", "أداة الدراسة", "Instrument",
                  *count(f.instruments, "أداة", "instrument(s)")),
        KnownFact("data", "البيانات", "Data",
                  *count(f.datasets, "مجموعة بيانات", "dataset(s)")),
        KnownFact("analysis", "التحليل", "Analysis",
                  *count(f.analysis_outputs, "مخرَج تحليل", "analysis output(s)")),
        KnownFact("manuscript", "المخطوطة", "Manuscript",
                  *count(f.manuscripts, "مخطوطة", "manuscript(s)")),
    )


def missing_items(f: StageFacts, derived: JourneyStages) -> tuple[MissingItem, ...]:
    """ما ينقص، مصنَّفًا ثلاثًا.

    **والرتبةُ تُقرأ من حال المرحلة نفسها** لا من قائمةٍ ثانية تُكتب بجانبها:
    ما أوقف مرحلةً `blocking`، وما كانت مرحلتُه اختياريّةً `optional`، وما
    عداه `recommended`. فلا تفترق رتبةُ الناقص عن حال مرحلته.
    """
    out: list[MissingItem] = []
    for stage in derived.stages:
        if stage.status is StageStatus.COMPLETED:
            continue
        severity = (BLOCKING if stage.status is StageStatus.BLOCKED
                    else OPTIONAL_GAP if stage.status is StageStatus.OPTIONAL
                    else RECOMMENDED)
        out.append(MissingItem(
            key=stage.key.value, label_ar=stage.title_ar, label_en=stage.title_en,
            severity=severity))
    return tuple(out)


__all__ = [
    "BLOCKING", "JourneyStages", "KnownFact", "MissingItem", "NEEDS_ANALYSIS_OUTPUT", "NEEDS_DATA", "NEEDS_DESIGN",
    "NEEDS_LITERATURE", "NEEDS_QUESTION", "NEEDS_SOURCES", "ORDER", "ROUTE",
    "CTA", "OPTIONAL_GAP", "RECOMMENDED", "Stage", "StageFacts", "StageKey",
    "StageStatus",
    "TITLES", "derive", "known_facts", "missing_items",
]
