"""درجة ملاءمة الفرصة | Opportunity fit score (§51.3).

النوع الثاني المستقل. §51.3 نصًّا: «لا يجوز مساواة الرواج بقابلية النشر».

لا يستورد هذا الملف `TrendStrength` ولا يعرف بوجوده: الفصل في الاستيراد
نفسه، فلا يمكن كتابة دالة تجمع الرقمين دون تعديل معماري ظاهر.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .vocab import OPPORTUNITY_CRITERIA


class ScoringError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CriterionRating:
    key: str
    weight: int
    ratio: float | None
    label_ar: str
    label_en: str
    rationale_ar: str
    rationale_en: str

    @property
    def points(self) -> float:
        return 0.0 if self.ratio is None else round(self.weight * self.ratio, 2)


@dataclass(slots=True)
class OpportunityFit:
    """درجة **ملاءمة الفرصة للباحث** — لا قوة الاتجاه."""

    criteria: list[CriterionRating]
    fit_score: float = field(init=False)
    uncomputed: list[str] = field(init=False)
    note_ar: str = field(
        default=("ملاءمة الفرصة لهذا الباحث؛ لا تقيس رواج الموضوع ولا تعد بقبول. "
                 "ودرجة مرتفعة مع معيار حاسم صفري لا تعني فرصة قابلة للتنفيذ."),
        init=False,
    )
    note_en: str = field(
        default=("Fit for this researcher; it measures neither topic popularity nor acceptance. "
                 "A high score with a zeroed gating criterion is still not actionable."),
        init=False,
    )

    def __post_init__(self) -> None:
        self.fit_score = round(sum(c.points for c in self.criteria), 2)
        self.uncomputed = [c.key for c in self.criteria if c.ratio is None]

    @property
    def blocking_reasons(self) -> list[str]:
        """معايير حاسمة تُسقط الفرصة مهما بلغت الدرجة.

        درجة 54 من 100 لموضوع لا يملك الباحث بياناته ليست «نصف جيدة» — هي
        غير قابلة للتنفيذ. الوزن وحده لا يعبّر عن ذلك: ملاءمة الباحث وقابلية
        الحصول على البيانات **شرطان حاسمان** لا معياران يُجمعان مع غيرهما.

        نفس درس §11 و§15.3: الرقم لا يقف وحده.
        """
        blocking = {"researcher_fit", "data_feasibility"}
        by_key = {c.key: c for c in self.criteria}
        reasons: list[str] = []
        for key in sorted(blocking):
            criterion = by_key.get(key)
            if criterion is None:
                continue
            if criterion.ratio is None:
                reasons.append(f"{key}:not_computed")
            elif criterion.ratio == 0.0:
                reasons.append(f"{key}:zero")
        return reasons

    @property
    def is_actionable(self) -> bool:
        """قابلة للتحويل إلى بطاقة فرصة — لا مجرد درجة مرتفعة."""
        return not self.blocking_reasons


def total_weight() -> int:
    return sum(weight for weight, _, _ in OPPORTUNITY_CRITERIA.values())


def score(
    ratios: dict[str, float | None],
    rationales: dict[str, tuple[str, str]] | None = None,
) -> OpportunityFit:
    rationales = rationales or {}
    unknown = set(ratios) - set(OPPORTUNITY_CRITERIA)
    if unknown:
        raise ScoringError(f"unknown opportunity criteria: {sorted(unknown)}")

    criteria: list[CriterionRating] = []
    for key, (weight, label_ar, label_en) in OPPORTUNITY_CRITERIA.items():
        ratio = ratios.get(key)
        if ratio is not None and not 0.0 <= ratio <= 1.0:
            raise ScoringError(f"criterion ratio out of range: {key}={ratio}")
        default_ar = (f"{label_ar}: لم تتوفر بيانات كافية." if ratio is None else label_ar)
        default_en = (f"{label_en}: insufficient data." if ratio is None else label_en)
        rationale_ar, rationale_en = rationales.get(key, (default_ar, default_en))
        criteria.append(CriterionRating(
            key=key, weight=weight, ratio=ratio, label_ar=label_ar, label_en=label_en,
            rationale_ar=rationale_ar, rationale_en=rationale_en,
        ))
    return OpportunityFit(criteria=criteria)
