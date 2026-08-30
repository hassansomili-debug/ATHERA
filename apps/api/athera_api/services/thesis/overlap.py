"""مصفوفة التداخل وتنبيه التجزئة | Overlap matrix and salami-slicing alert (§23.7).

الأبعاد السبعة تُحسب دائمًا؛ و**متى تصير تنبيهًا** يقرره صف سياسة لا ثابت
في الكود — §23.7 تنص أن القواعد «تحددها سياسات التحرير/النزاهة».

وقاعدة ثانية تحكم هذا الملف: بُعد لا تتوفر بياناته يُعلَن `not_computed`،
لا `0.0`. رقم مطمئن مبني على غياب بيانات أخطر من غياب الرقم.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .vocab import OVERLAP_DIMENSIONS

# نطاقات التشكيل والتطويل بترميز صريح لا بحروف حرفية.
# السبب: صنف حروف مكتوب حرفيًا يمكن أن يتلف عند النسخ فيبتلع الحروف العربية
# نفسها بدل تشكيلها — وهذا ما وقع فعلًا وكشفه اختبار التداخل في Sprint 6.
_ARABIC_DIACRITICS = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_NON_WORD = re.compile(r"[^\w؀-ۿ]+")

# كلمات وظيفية شائعة — وجودها المشترك ليس تشابهًا علميًا.
_STOPWORDS = frozenset({
    "في", "من", "على", "إلى", "عن", "أن", "إن", "التي", "الذي", "هذا", "هذه",
    "بين", "مع", "كما", "قد", "هل", "ما", "لا", "و", "أو", "ثم",
    "the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "are",
    "this", "that", "with", "by", "as", "at", "from", "between",
})


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    return text.lower()


def tokens(text: str) -> set[str]:
    parts = [p for p in _NON_WORD.split(normalize(text)) if p]
    return {p for p in parts if p not in _STOPWORDS and len(p) > 1}


def jaccard(left: set, right: set) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    return round(len(left & right) / len(union), 4) if union else 0.0


NOT_COMPUTED = "not_computed"


@dataclass(frozen=True, slots=True)
class OpportunityFingerprint:
    """بصمة فرصة — ما يكفي لقياس تداخلها بغيرها.

    كل حقل قابل لأن يكون `None`: غيابه يعني «لم يُحسب»، لا «لا تداخل».
    """

    opportunity_id: str
    research_question: str | None = None
    sample_ids: frozenset[str] | None = None
    variable_ids: frozenset[str] | None = None
    result_ids: frozenset[str] | None = None
    table_figure_ids: frozenset[str] | None = None
    text: str | None = None
    published_output_ids: frozenset[str] | None = None


@dataclass(slots=True)
class OverlapPolicy:
    """§23.7 — العتبات بيانات سياسة، لا ثوابت.

    `alert_threshold` لكل بُعد، و`salami_rule` يحدد كم بُعدًا يجب أن يتجاوز
    عتبته حتى يُطلق تنبيه التجزئة.
    """

    policy_id: str
    thresholds: dict[str, float]
    salami_min_dimensions: int
    salami_critical_dimensions: frozenset[str] = frozenset()
    label_ar: str = "سياسة تداخل"
    label_en: str = "Overlap policy"


@dataclass(slots=True)
class DimensionScore:
    dimension: str
    value: float | None
    status: str  # computed | not_computed
    exceeds_threshold: bool
    threshold: float | None
    label_ar: str
    label_en: str


@dataclass(slots=True)
class OverlapResult:
    left_id: str
    right_id: str
    dimensions: list[DimensionScore]
    policy_id: str
    salami_alert: bool
    exceeded: list[str] = field(default_factory=list)
    not_computed: list[str] = field(default_factory=list)

    @property
    def blocks_separate_conversion(self) -> bool:
        """TC-05 — التنبيه يمنع تحويل الفرصتين مستقلتين بلا دمج أو تبرير معتمد."""
        return self.salami_alert


def _pair(left, right) -> tuple[float | None, str]:
    """يحسب تشابه مجموعتين، ويميّز الغياب عن الصفر."""
    if left is None or right is None:
        return None, NOT_COMPUTED
    return jaccard(set(left), set(right)), "computed"


def compare(
    left: OpportunityFingerprint,
    right: OpportunityFingerprint,
    policy: OverlapPolicy,
) -> OverlapResult:
    raw: dict[str, tuple[float | None, str]] = {}

    if left.research_question is None or right.research_question is None:
        raw["research_question"] = (None, NOT_COMPUTED)
    else:
        raw["research_question"] = (
            jaccard(tokens(left.research_question), tokens(right.research_question)), "computed"
        )

    raw["sample"] = _pair(left.sample_ids, right.sample_ids)
    raw["variable"] = _pair(left.variable_ids, right.variable_ids)
    raw["result"] = _pair(left.result_ids, right.result_ids)
    raw["table_figure"] = _pair(left.table_figure_ids, right.table_figure_ids)
    raw["published_output"] = _pair(left.published_output_ids, right.published_output_ids)

    if left.text is None or right.text is None:
        raw["text"] = (None, NOT_COMPUTED)
    else:
        raw["text"] = (jaccard(tokens(left.text), tokens(right.text)), "computed")

    dimensions: list[DimensionScore] = []
    exceeded: list[str] = []
    not_computed: list[str] = []

    for key, (label_ar, label_en) in OVERLAP_DIMENSIONS.items():
        value, statuslabel = raw[key]
        threshold = policy.thresholds.get(key)
        over = (
            statuslabel == "computed"
            and threshold is not None
            and value is not None
            and value >= threshold
        )
        if statuslabel == NOT_COMPUTED:
            not_computed.append(key)
        if over:
            exceeded.append(key)
        dimensions.append(DimensionScore(
            dimension=key, value=value, status=statuslabel, exceeds_threshold=over,
            threshold=threshold, label_ar=label_ar, label_en=label_en,
        ))

    critical_hit = bool(policy.salami_critical_dimensions & set(exceeded))
    salami = critical_hit or len(exceeded) >= policy.salami_min_dimensions

    return OverlapResult(
        left_id=left.opportunity_id, right_id=right.opportunity_id,
        dimensions=dimensions, policy_id=policy.policy_id, salami_alert=salami,
        exceeded=exceeded, not_computed=not_computed,
    )


def matrix(
    fingerprints: list[OpportunityFingerprint], policy: OverlapPolicy
) -> list[OverlapResult]:
    """مصفوفة كل الأزواج — التداخل علاقة لا خاصية فرصة واحدة."""
    results: list[OverlapResult] = []
    for index, left in enumerate(fingerprints):
        for right in fingerprints[index + 1:]:
            results.append(compare(left, right, policy))
    return results
