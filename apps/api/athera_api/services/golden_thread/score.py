"""درجة الخيط الذهبي | Golden Thread Score (§15.3).

§15.3 تنص: «درجة من 100 مع شرح العناصر المفقودة، **مع منع استخدام الدرجة
وحدها كحكم نهائي**».

التنفيذ يجعل المنع بنيويًا لا اتفاقيًا: `GoldenThreadScore` لا يُبنى بلا
قائمة نتائجه، ولا يوجد مسار يعيد رقمًا مجردًا. ودرجة 100 مع كشف حاجب
مستحيلة بحكم الحساب.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .checks import Finding, run_all
from .graph import ThreadGraph

# §15.1 — العناصر التي يجب أن يحملها خيط مكتمل.
REQUIRED_ELEMENTS: tuple[str, ...] = (
    "problem", "gap", "question", "objective", "theory", "variable",
    "method", "instrument", "analysis",
)

BLOCKING_PENALTY = 12
ADVISORY_PENALTY = 3


@dataclass(slots=True)
class GoldenThreadScore:
    """درجة لا تنفصل عن أسبابها.

    الحقول إلزامية بلا قيم افتراضية للنتائج: بناء درجة بلا شرح غير ممكن.
    """

    score: int
    findings: list[Finding]
    missing_elements: list[str]
    blocking_count: int
    advisory_count: int
    # §15.3 — الوسم يرافق كل استجابة، فلا تُقرأ الدرجة وحدها.
    is_final_verdict: bool = field(default=False, init=False)
    note_ar: str = field(
        default="الدرجة مؤشر إرشادي؛ لا تُستخدم وحدها حكمًا نهائيًا (§15.3).", init=False
    )
    note_en: str = field(
        default="The score is indicative; it must not be used alone as a final verdict (§15.3).",
        init=False,
    )

    def __post_init__(self) -> None:
        if self.blocking_count and self.score >= 100:
            # حارس ضد أي حساب مستقبلي يمنح الكمال مع عيب حاجب.
            raise ValueError("a perfect score with blocking findings is not representable")

    @property
    def can_pass_gate(self) -> bool:
        """البوابة تُفتح بغياب الكشوفات الحاجبة والعناصر المفقودة، لا بالدرجة."""
        return self.blocking_count == 0 and not self.missing_elements


def missing_required_elements(graph: ThreadGraph) -> list[str]:
    present = {element.element_type for element in graph.elements}
    if graph.variables:
        present.add("variable")
    if graph.instruments:
        present.add("instrument")
    if graph.method is not None:
        present.add("method")
    return [name for name in REQUIRED_ELEMENTS if name not in present]


def compute(graph: ThreadGraph) -> GoldenThreadScore:
    findings = run_all(graph)
    missing = missing_required_elements(graph)

    blocking = sum(1 for finding in findings if finding.is_blocking)
    advisory = len(findings) - blocking

    penalty = (
        blocking * BLOCKING_PENALTY
        + advisory * ADVISORY_PENALTY
        + len(missing) * BLOCKING_PENALTY
    )
    score = max(0, 100 - penalty)

    return GoldenThreadScore(
        score=score, findings=findings, missing_elements=missing,
        blocking_count=blocking + len(missing), advisory_count=advisory,
    )
