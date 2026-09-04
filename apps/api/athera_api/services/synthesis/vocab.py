"""مفردات طبقة التركيب | Synthesis vocabulary (PUBRIVA).

**كل مفردةٍ هنا لها معنًى مكتوب، لا اسمٌ يوحي بمعنى.** و«قوّةٌ» بلا تعريفٍ
معلن تُقرأ رقمًا في ذهن القارئ: يرى `SUPPORTED_CANDIDATE` فيفهم «ثبتت»،
وهي لا تعني ذلك. فالمعاني تُعرض للباحث مع الاسم دائمًا.

**ولا نِسَب مخترَعة.** «٧٣٪ ثقة» رقمٌ لا يقابله قياس: لا عيّنة، ولا توزيع،
ولا خطأ معياري — هو انطباعٌ لُبس ثوب رقم، وهو أخطر من انطباعٍ يقول إنه
انطباع. فالقوّة ثلاث درجاتٍ موصوفة، وحدودُ كل درجة مكتوبة في اسمها ومعناها.

**والدعوى محدودةٌ بما بُحث.** الجمل المطلقة عن غياب الدراسات ممنوعة في هذا
الملف نصًّا: `FORBIDDEN_ABSOLUTE_CLAIMS` قائمةٌ يمسحها اختبارٌ على كل نصٍّ
تُنتجه هذه الطبقة. وأكبر ما يجوز قوله أن شيئًا **لم يظهر في هذه المجموعة**،
مع عددها والفهارس التي جاءت منها.
"""
from __future__ import annotations

from typing import Final

from ...models.synthesis import (
    CONFLICT_KINDS,
    EFFECT_DIRECTIONS,
    GAP_STRENGTHS,
    GAP_TYPES,
    SIGNIFICANCE_STATES,
    SYNTHESIS_STATUSES,
    THEME_BASES,
)

# ── دورة الحياة كما يقرؤها الباحث ──
#
# ولا تُعرَض له `GENERATED` ولا `GapGraphNode`: أسماءُ الداخل تخصّ من يكتب
# الشيفرة، والباحث يقرأ ما يفهمه.
STATUS_LABELS: Final[dict[str, dict[str, str]]] = {
    "generated": {"ar": "مقترَح — لم يُراجَع بعد", "en": "Suggested — not reviewed yet"},
    "needs_review": {"ar": "يحتاج مراجعة", "en": "Needs review"},
    "approved": {"ar": "اعتمده الباحث", "en": "Approved by the researcher"},
    "rejected": {"ar": "رفضه الباحث", "en": "Rejected by the researcher"},
    # مفردة ترحيل 0016 — امتناعٌ عن الحكم ليس حكمًا بالبطلان.
    "unknown": {"ar": "راجعه ولم يستطع الحكم", "en": "Reviewed, could not decide"},
}

BASIS_LABELS: Final[dict[str, dict[str, str]]] = {
    "topic_cluster": {
        "ar": "تجميع موضوعي",
        "en": "Topic cluster",
    },
    "content_synthesis": {
        "ar": "موضوع علمي",
        "en": "Scientific theme",
    },
}

# **الفرق مكتوبٌ للباحث لا مضمرٌ في عمود.** ومن لم يقرأ هذا الفرق يقرأ
# تجميعًا من عناوين على أنه نتيجة.
BASIS_MEANING: Final[dict[str, dict[str, str]]] = {
    "topic_cluster": {
        "ar": ("عناوينُ دراساتٍ تشترك في كلمة. وهذا ترتيبٌ للقائمة، **وليس "
               "نتيجة**: لم يُقرأ من هذه الدراسات محتوًى يسند موضوعًا."),
        "en": ("Study titles sharing a word. This orders the list; it is not a "
               "finding — no content was read from these studies to support it."),
    },
    "content_synthesis": {
        "ar": ("تركيبٌ مسنودٌ بمحتوًى قُرئ من الدراسات نفسها: لكل دراسةٍ خليةٌ "
               "في مصفوفة الأدبيات يمكن فتحها ورؤية شاهدها."),
        "en": ("A synthesis supported by content actually read from the studies: "
               "each has a matrix cell you can open and inspect."),
    },
}

# ── قوّة الفجوة: ثلاث درجاتٍ موصوفة، ولا رقم ──
STRENGTH_LABELS: Final[dict[str, dict[str, str]]] = {
    "weak_signal": {"ar": "إشارة ضعيفة", "en": "Weak signal"},
    "emerging_pattern": {"ar": "نمط آخذ في الظهور", "en": "Emerging pattern"},
    "supported_candidate": {"ar": "مرشَّح مسنود", "en": "Supported candidate"},
}

STRENGTH_MEANING: Final[dict[str, dict[str, str]]] = {
    "weak_signal": {
        "ar": ("لوحظ في مجموعةٍ صغيرة أو من قراءةٍ لم تتجاوز الملخّصات. "
               "لا يُبنى عليه قرار، ويُذكر ليُفحص."),
        "en": ("Observed in a small set, or from reading no deeper than abstracts. "
               "Not a basis for a decision; noted so it can be checked."),
    },
    "emerging_pattern": {
        "ar": ("تكرّر في عدّة دراساتٍ قُرئ محتواها، وما زال محدودًا بهذه "
               "المجموعة وحدها."),
        "en": ("Recurs across several studies whose content was read; still bounded "
               "by this reference set alone."),
    },
    "supported_candidate": {
        "ar": ("تكرّر في مجموعةٍ معتبرة قُرئ أكثرها نصًّا كاملًا. ويبقى مرشَّحًا: "
               "يحتاج بحثًا مستقلًّا في الفهارس قبل أن يُكتب في ورقة."),
        "en": ("Recurs across a substantial set read mostly in full text. It stays a "
               "candidate: it needs an independent index search before it is written up."),
    },
}

# ترتيبُ القوّة — يُقارن ولا يُخمَّن، ولا تُمنح درجةٌ أعلى من سقف المجموعة.
STRENGTH_ORDER: Final = GAP_STRENGTHS

GAP_TYPE_LABELS: Final[dict[str, dict[str, str]]] = {
    "context_gap": {"ar": "فجوة سياق", "en": "Context gap"},
    "population_gap": {"ar": "فجوة مجتمع", "en": "Population gap"},
    "method_gap": {"ar": "فجوة منهج", "en": "Method gap"},
    "theory_gap": {"ar": "فجوة نظرية", "en": "Theory gap"},
    "measurement_gap": {"ar": "فجوة قياس", "en": "Measurement gap"},
    "temporal_gap": {"ar": "فجوة زمنية", "en": "Temporal gap"},
    "contradictory_evidence": {"ar": "أدلة متعارضة", "en": "Contradictory evidence"},
    "understudied_relationship": {"ar": "علاقة قليلة الدرس",
                                  "en": "Understudied relationship"},
    "replication_need": {"ar": "حاجة إلى تكرار", "en": "Replication need"},
}

CONFLICT_LABELS: Final[dict[str, dict[str, str]]] = {
    "direction": {"ar": "اتجاه الأثر مختلف", "en": "Opposite direction of effect"},
    "significance": {"ar": "الدلالة الإحصائية مختلفة",
                     "en": "Different statistical significance"},
    "effect_presence": {"ar": "أثرٌ مقابل لا أثر", "en": "Effect versus no effect"},
    "conclusion": {"ar": "خلاصتان مختلفتان", "en": "Differing conclusions"},
}

DIRECTION_LABELS: Final[dict[str, dict[str, str]]] = {
    "positive": {"ar": "أثر موجب", "en": "Positive"},
    "negative": {"ar": "أثر سالب", "en": "Negative"},
    "none": {"ar": "لا أثر", "en": "No effect"},
    "mixed": {"ar": "أثر مختلط", "en": "Mixed"},
    # **الصمت يُسمّى صمتًا.** «غير مذكور» ليست «لا أثر».
    "not_stated": {"ar": "غير مذكور", "en": "Not stated"},
}

SIGNIFICANCE_LABELS: Final[dict[str, dict[str, str]]] = {
    "significant": {"ar": "دالّ إحصائيًّا", "en": "Statistically significant"},
    "not_significant": {"ar": "غير دالّ إحصائيًّا", "en": "Not statistically significant"},
    "not_stated": {"ar": "غير مذكور", "en": "Not stated"},
}

# أبعاد السياق التي تُقارَن بين طرفَي التعارض — بأسمائها للباحث.
CONTEXT_DIMENSIONS: Final = ("country", "population", "method", "measurement", "period")

CONTEXT_DIMENSION_LABELS: Final[dict[str, dict[str, str]]] = {
    "country": {"ar": "البلد", "en": "Country"},
    "population": {"ar": "المجتمع", "en": "Population"},
    "method": {"ar": "المنهج", "en": "Method"},
    "measurement": {"ar": "القياس", "en": "Measurement"},
    "period": {"ar": "الفترة الزمنية", "en": "Period"},
}

# **جملٌ ممنوعة نصًّا.** كلٌّ منها دعوى عن العالم لم تُفحص، ويقرؤها الباحث
# حكمًا فيبني عليها ورقة. واختبارٌ يمسح كل نصٍّ تُنتجه هذه الطبقة بحثًا عنها.
FORBIDDEN_ABSOLUTE_CLAIMS: Final = (
    "لا توجد دراسات",
    "لا توجد دراسة",
    "لا يوجد بحث",
    "لم يدرس أحد",
    "أول دراسة",
    "الأولى من نوعها",
    "لم يسبق",
    "no studies exist",
    "no research exists",
    "first study",
    "never been studied",
)

# **ولا تُوصَف دراسةٌ بالخطأ.** التعارض حالُ معرفةٍ لا حكمٌ على باحث؛ ومن
# سمّى إحدى الدراستين خاطئة فقد فصل في نزاعٍ علميّ لم يُعرض عليه.
FORBIDDEN_VERDICT_WORDS: Final = (
    "خاطئة",
    "خطأ",
    "مغلوطة",
    "باطلة",
    "غير صحيحة",
    "أصحّ",
    "الأصحّ",
    "is wrong",
    "incorrect study",
)


def strength_at_most(strength: str, ceiling: str) -> str:
    """لا تُمنح درجةٌ أعلى من سقف المجموعة — **والسقف يُفرض هنا لا يُرجى**."""
    if STRENGTH_ORDER.index(strength) <= STRENGTH_ORDER.index(ceiling):
        return strength
    return ceiling


def label(table: dict[str, dict[str, str]], key: str, locale: str) -> str:
    """اسمُ المفردة باللغة المطلوبة — و**لا يُعرض المفتاح التقني أبدًا**."""
    entry = table.get(key)
    if entry is None:  # pragma: no cover - حارس ضد مفردةٍ لم تُترجَم
        raise KeyError(f"no bilingual label for {key!r}")
    return entry.get(locale) or entry["ar"]


__all__ = [
    "BASIS_LABELS",
    "BASIS_MEANING",
    "CONFLICT_KINDS",
    "CONFLICT_LABELS",
    "CONTEXT_DIMENSIONS",
    "CONTEXT_DIMENSION_LABELS",
    "DIRECTION_LABELS",
    "EFFECT_DIRECTIONS",
    "FORBIDDEN_ABSOLUTE_CLAIMS",
    "FORBIDDEN_VERDICT_WORDS",
    "GAP_STRENGTHS",
    "GAP_TYPES",
    "GAP_TYPE_LABELS",
    "SIGNIFICANCE_LABELS",
    "SIGNIFICANCE_STATES",
    "STATUS_LABELS",
    "STRENGTH_LABELS",
    "STRENGTH_MEANING",
    "STRENGTH_ORDER",
    "SYNTHESIS_STATUSES",
    "THEME_BASES",
    "label",
    "strength_at_most",
]
