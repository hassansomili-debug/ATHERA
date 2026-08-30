"""إشارات الاتجاه وتمييزه عن الضجيج | Trend signals and noise discrimination (§51.1).

§51.1 تشترط أربعة أشياء لتمييز الاتجاه الحقيقي: **حدًا أدنى من الأدلة،
والتكرار، والاستمرارية، وتنوع المصادر**. أربعة شروط لا شرط واحد.

خمس إشارات من مصدر واحد في يوم واحد ضجيج؛ وخمس من ثلاثة مصادر عبر ستة
أشهر اتجاه. الفرق يُحسب ولا يُخمَّن — وعتباته بيانات سياسة لا ثوابت.

وقاعدة قاطعة: إشارة مصدرها مخرَج نموذج **لا تُحتسب**. §51.1 تمنع الاعتماد
على ذاكرة النموذج وحدها، فالمنع بنيوي لا نصي.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .vocab import DETECTION_PATTERNS, SIGNAL_SOURCE_TYPES


class SignalError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class TrendSignal:
    """إشارة واحدة. §51.11: «لا توجد إشارة يتيمة بلا Provenance»."""

    signal_id: str
    trend_key: str
    source_type: str
    source_id: str
    observed_at: dt.datetime
    pattern: str
    weight: float = 1.0
    detail_ar: str | None = None

    def __post_init__(self) -> None:
        if self.source_type not in SIGNAL_SOURCE_TYPES:
            raise SignalError(f"unknown signal source: {self.source_type}")
        if not self.source_id.strip():
            raise SignalError("a signal without a source identifier is an orphan (§51.11)")
        if self.pattern not in DETECTION_PATTERNS:
            raise SignalError(f"unknown detection pattern: {self.pattern}")
        if not 0.0 < self.weight <= 1.0:
            raise SignalError("signal weight must be within (0, 1]")

    @property
    def counts_as_evidence(self) -> bool:
        """§51.1 — مخرَج النموذج يُسجَّل ولا يُحتسب دليلًا."""
        return SIGNAL_SOURCE_TYPES[self.source_type]


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    """§51.1 — العتبات الأربع كبيانات، لا ثوابت في الكود."""

    policy_id: str
    min_evidence_weight: float          # الحد الأدنى من الأدلة الموزونة
    min_signals: int                    # التكرار
    min_distinct_sources: int           # تنوع المصادر
    min_span_days: int                  # الاستمرارية
    decline_ratio: float = 0.4          # نسبة تراجع تعني انحسارًا


@dataclass(slots=True)
class ConditionCheck:
    key: str
    satisfied: bool
    actual: float
    required: float
    detail_ar: str
    detail_en: str


@dataclass(slots=True)
class TrendStrength:
    """§51.3 — درجة **قوة الاتجاه** وحدها.

    نوع مستقل تمامًا عن ملاءمة الفرصة: لا حقل يجمعهما ولا دالة تحوّل بينهما.
    موضوع رائج جدًا قد تكون فرصته صفرًا، وخلط الرقمين يخفي ذلك بالضبط.
    """

    trend_key: str
    status: str
    conditions: list[ConditionCheck]
    evidence_weight: float
    signal_count: int
    distinct_sources: int
    span_days: int
    ignored_signals: int = 0
    note_ar: str = field(
        default="قوة الاتجاه لا تعني قابلية النشر؛ لكل منهما درجته (§51.3).", init=False
    )
    note_en: str = field(
        default="Trend strength is not publishability; each has its own score (§51.3).",
        init=False,
    )

    @property
    def is_validated(self) -> bool:
        return self.status == "validated"

    @property
    def unmet_conditions(self) -> list[str]:
        return [c.key for c in self.conditions if not c.satisfied]


def validate(
    trend_key: str, signals: list[TrendSignal], policy: ValidationPolicy,
    *, as_of: dt.datetime, previous_weight: float | None = None,
) -> TrendStrength:
    """يفحص الشروط الأربعة معًا. استيفاء ثلاثة منها لا يكفي."""
    counted = [signal for signal in signals if signal.counts_as_evidence]
    ignored = len(signals) - len(counted)

    weight = round(sum(signal.weight for signal in counted), 3)
    sources = {signal.source_id for signal in counted}
    if counted:
        # الامتداد هو المسافة بين أقدم إشارة وأحدثها، لا بينها وبين اليوم.
        # قياسه حتى اليوم يجعل إشارة **واحدة** قديمة تستوفي شرط الاستمرار،
        # فينهار الشرط الرابع إلى «هل الإشارة قديمة» بدل «هل تكرّرت عبر الزمن».
        # و`as_of` تبقى السقف: إشارة مؤرَّخة في المستقبل لا تمدّ الامتداد.
        earliest = min(signal.observed_at for signal in counted)
        latest = min(max(signal.observed_at for signal in counted), as_of)
        span = max((latest - earliest).days, 0)
    else:
        span = 0

    conditions = [
        ConditionCheck(
            key="min_evidence_weight", satisfied=weight >= policy.min_evidence_weight,
            actual=weight, required=policy.min_evidence_weight,
            detail_ar=f"وزن الأدلة {weight} والمطلوب {policy.min_evidence_weight}.",
            detail_en=f"Evidence weight {weight}; {policy.min_evidence_weight} required.",
        ),
        ConditionCheck(
            key="min_signals", satisfied=len(counted) >= policy.min_signals,
            actual=float(len(counted)), required=float(policy.min_signals),
            detail_ar=f"عدد الإشارات المحتسبة {len(counted)} والمطلوب {policy.min_signals}.",
            detail_en=f"{len(counted)} counted signals; {policy.min_signals} required.",
        ),
        ConditionCheck(
            key="min_distinct_sources", satisfied=len(sources) >= policy.min_distinct_sources,
            actual=float(len(sources)), required=float(policy.min_distinct_sources),
            detail_ar=f"مصادر مختلفة {len(sources)} والمطلوب {policy.min_distinct_sources}.",
            detail_en=f"{len(sources)} distinct sources; {policy.min_distinct_sources} required.",
        ),
        ConditionCheck(
            key="min_span_days", satisfied=span >= policy.min_span_days,
            actual=float(span), required=float(policy.min_span_days),
            detail_ar=f"امتداد زمني {span} يومًا والمطلوب {policy.min_span_days}.",
            detail_en=f"Span of {span} days; {policy.min_span_days} required.",
        ),
    ]

    if all(condition.satisfied for condition in conditions):
        status = "validated"
        if previous_weight is not None and previous_weight > 0:
            if weight <= previous_weight * policy.decline_ratio:
                status = "declining"
    elif not counted:
        status = "candidate" if signals else "noise"
    else:
        status = "noise"

    return TrendStrength(
        trend_key=trend_key, status=status, conditions=conditions,
        evidence_weight=weight, signal_count=len(counted),
        distinct_sources=len(sources), span_days=span, ignored_signals=ignored,
    )


@dataclass(slots=True)
class TimelinePoint:
    period: str
    signal_count: int
    weight: float


def timeline(signals: list[TrendSignal]) -> list[TimelinePoint]:
    """§51.1 — خط زمني يوضح متى بدأ الاتجاه وسرعة نموه."""
    buckets: dict[str, list[TrendSignal]] = {}
    for signal in signals:
        if not signal.counts_as_evidence:
            continue
        key = signal.observed_at.strftime("%Y-%m")
        buckets.setdefault(key, []).append(signal)
    return [
        TimelinePoint(period=period, signal_count=len(items),
                      weight=round(sum(s.weight for s in items), 3))
        for period, items in sorted(buckets.items())
    ]
