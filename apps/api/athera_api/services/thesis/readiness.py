"""درجة جاهزية النشر | Publication Readiness Score (§23.6).

المكونات الثمانية بأوزانها كما نصّت الوثيقة، ومجموع الأوزان 100.

ونفس قاعدة §15.3 و§11: **الدرجة لا تُعاد مجردة**. المخرَج فئة من خمس مع
مكوناته، لأن «72 من 100» لا تخبر الباحث بما يجب فعله، بينما «تحتاج إعادة
تحليل» تخبره.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .vocab import READINESS_COMPONENTS, READINESS_OUTCOMES


@dataclass(frozen=True, slots=True)
class ComponentScore:
    key: str
    weight: int
    # نسبة من 0 إلى 1 — أو None حين لا تتوفر بيانات تقييمه.
    ratio: float | None
    rationale_ar: str
    rationale_en: str

    @property
    def points(self) -> float:
        return 0.0 if self.ratio is None else round(self.weight * self.ratio, 2)


@dataclass(slots=True)
class ReadinessScore:
    components: list[ComponentScore]
    outcome: str
    score: float = field(init=False)
    uncomputed: list[str] = field(init=False)
    outcome_label_ar: str = field(init=False)
    outcome_label_en: str = field(init=False)
    note_ar: str = field(
        default="الدرجة مؤشر؛ القرار هو المخرَج المصنَّف ومكوناته لا الرقم وحده.", init=False
    )
    note_en: str = field(
        default="The score is indicative; the decision is the classified outcome, not the number.",
        init=False,
    )

    def __post_init__(self) -> None:
        if self.outcome not in READINESS_OUTCOMES:
            raise ValueError(f"unknown readiness outcome: {self.outcome}")
        self.score = round(sum(c.points for c in self.components), 2)
        self.uncomputed = [c.key for c in self.components if c.ratio is None]
        self.outcome_label_ar, self.outcome_label_en = READINESS_OUTCOMES[self.outcome]


def total_weight() -> int:
    return sum(weight for weight, _, _ in READINESS_COMPONENTS.values())


def classify(components: list[ComponentScore], *, salami_alert: bool) -> str:
    """§23.6 — المخرجات الخمسة.

    الترتيب مقصود: التداخل الحاد يسبق أي حساب نقاط، لأن ورقة مكررة لا
    تُنقذها جودة منهجها.
    """
    by_key = {c.key: c for c in components}

    def ratio(key: str) -> float | None:
        component = by_key.get(key)
        return component.ratio if component else None

    if salami_alert:
        return "do_not_publish_separately"

    novelty = ratio("novelty")
    question = ratio("independent_question")
    results = ratio("independent_results")
    method = ratio("method_data_strength")

    if novelty is not None and novelty < 0.3:
        return "do_not_publish_separately"
    if question is not None and question < 0.4:
        return "merge_with_another"
    if results is not None and results < 0.4:
        return "needs_reanalysis"
    if method is not None and method < 0.5:
        return "needs_reanalysis"

    currency = ratio("topic_currency")
    if currency is not None and currency < 0.4:
        return "needs_theoretical_update"

    return "ready_to_convert"


def compute(ratios: dict[str, float | None], *, salami_alert: bool,
            rationales: dict[str, tuple[str, str]] | None = None) -> ReadinessScore:
    """يبني الدرجة من نسب المكونات. مكون بلا بيانات يبقى `None` ويُعلَن."""
    rationales = rationales or {}
    components: list[ComponentScore] = []
    for key, (weight, label_ar, label_en) in READINESS_COMPONENTS.items():
        ratio = ratios.get(key)
        if ratio is not None and not 0.0 <= ratio <= 1.0:
            raise ValueError(f"component ratio out of range: {key}={ratio}")
        default_ar = f"{label_ar}: لم تتوفر بيانات كافية للتقييم." if ratio is None else label_ar
        default_en = f"{label_en}: insufficient data to assess." if ratio is None else label_en
        rationale_ar, rationale_en = rationales.get(key, (default_ar, default_en))
        components.append(ComponentScore(
            key=key, weight=weight, ratio=ratio,
            rationale_ar=rationale_ar, rationale_en=rationale_en,
        ))

    return ReadinessScore(
        components=components,
        outcome=classify(components, salami_alert=salami_alert),
    )
