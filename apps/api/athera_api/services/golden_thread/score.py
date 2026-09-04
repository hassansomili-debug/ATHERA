"""درجة الخيط الذهبي | Golden Thread Score (§15.3).

§15.3 تنص: «درجة من 100 مع شرح العناصر المفقودة، **مع منع استخدام الدرجة
وحدها كحكم نهائي**».

التنفيذ يجعل المنع بنيويًا لا اتفاقيًا: `GoldenThreadScore` لا يُبنى بلا
قائمة نتائجه، ولا يوجد مسار يعيد رقمًا مجردًا. ودرجة 100 مع كشف حاجب
مستحيلة بحكم الحساب.

**والصفر ليس حكمًا.** الحساب يخصم عن كل عنصرٍ مفقود، فخيطٌ في أوّله تنقصه
العناصر التسعة يهبط إلى صفر — فيقرأ الباحث «بحثُك في أقصى درجات التناقض»
والحقيقةُ «لا نملك ما يكفي للحكم». والفرق بين الحالين ليس فرق درجةٍ بل
فرقُ نوع: الاتساق صفةُ علاقاتٍ **بين عناصر موجودة**، ولا علاقة تُفحص بين
عنصرٍ وغياب. فصفرٌ عن نقصٍ ليس قياسًا رديئًا، بل قياسٌ لم يقع أصلًا.

فـ`is_computable` تفصل الحالين بنيويًا، و`presented_score` تعيد `None` ما
دامت العناصر الأساسية ناقصة — فلا يجد العارضُ رقمًا يعرضه. والدرجة نفسها
تبقى محسوبةً **لبوابة البروتوكول** كما كانت: لا `can_pass_gate` تتغيّر ولا
لقطةُ الاعتماد، فالبوابة قرارٌ آليّ لا قراءةُ باحث.

**والمفقود ليس عيبًا.** `blocking_count` تجمع العيوبَ البنيوية والمفقوداتِ
معًا لأنّ كليهما يغلق البوابة — وهو صحيحٌ للبوابة وكاذبٌ للقراءة: «تسعة
عيوب حاجبة» فوق «لا توجد عيوب اتساق» تناقضٌ في عين الباحث مهما استقام في
الحساب. فالأعداد تُفصَل بأسمائها — `missing_count` و`structural_count`
و`linguistic_count` — ويبقى `blocking_count` للبوابة وحدها.
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

# ما يُقال حين لا يُحسب الاتساق — نصٌّ واحد، فلا تختلف الشاشتان في السبب.
NOT_COMPUTED_AR = "لم يُحسب الاتساق بعد لعدم اكتمال العناصر الأساسية."
NOT_COMPUTED_EN = (
    "Consistency has not been computed yet: the core elements are incomplete."
)


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

    # ── الأعداد بأسمائها: المفقود ليس عيبًا، والعيب ليس تنبيهًا ──

    @property
    def missing_count(self) -> int:
        """عناصر مفقودة — غيابُ ما يُفحص، لا نتيجةُ فحص."""
        return len(self.missing_elements)

    @property
    def structural_count(self) -> int:
        """عيوبٌ بنيوية في **علاقاتٍ بين عناصر موجودة** — هذه وحدها «عيوب اتساق»."""
        return sum(1 for finding in self.findings if finding.is_blocking)

    @property
    def linguistic_count(self) -> int:
        """تنبيهاتٌ منهجية لغوية — اقتراحُ مراجعةٍ يقرّه الباحث، لا حكم."""
        return len(self.findings) - self.structural_count

    @property
    def is_computable(self) -> bool:
        """هل هناك ما يكفي للحكم على الاتساق أصلًا؟

        الاتساق صفةُ علاقاتٍ بين عناصر موجودة. وما دام عنصرٌ أساسيّ غائبًا
        فالسلسلة مقطوعة عنده، وكلُّ رقمٍ يُعرض عنها يقيس **النقص** ويُقرأ
        **تناقضًا** — وهما ليسا الشيء نفسه.
        """
        return not self.missing_elements

    @property
    def presented_score(self) -> int | None:
        """الدرجة كما تُعرض — و`None` تعني «لا تُعرض»، لا «صفر».

        والفصلُ هنا بنيويّ لا اتفاقي: العارضُ الذي يطلب `presented_score`
        لا يجد رقمًا يعرضه حين لا يُحسب، فلا يبقى للصفر بابٌ يدخل منه.
        """
        return self.score if self.is_computable else None

    @property
    def not_computed_reason_ar(self) -> str | None:
        return None if self.is_computable else NOT_COMPUTED_AR

    @property
    def not_computed_reason_en(self) -> str | None:
        return None if self.is_computable else NOT_COMPUTED_EN


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
