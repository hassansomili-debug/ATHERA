"""محرّك القواعد العلمية | Scientific rules engine (عقود ومحرّك).

**قواعد حتمية لا نموذج.** كل قاعدة هنا دالةٌ تقرأ لقطةً وتُرجع حكمًا، ولا
تسأل مزوّدًا ولا تحتمل جوابين لمدخلٍ واحد. وهذا شرطٌ لا تفضيل: قاعدةٌ تحرس
النزاهة ويحكم فيها نموذجٌ احتمالي تصير حارسًا يُصدّق أحيانًا ويُكذّب أحيانًا
على المُدخل نفسه — ولا يُبنى على ذلك منع.

## الحكم أربعة لا اثنان

    pass                       فُحصت وسلمت
    violation                  فُحصت وخولفت
    not_applicable             لا تنطبق على هذه الحالة أصلًا
    insufficient_information   لم يمكن الفحص — والمعطيات ناقصة

والرابعة هي التي تصنع الفرق. قاعدةٌ لا تجد ما تفحصه فترجع `pass` تكذب:
تقول «فُحص وسلم» عمّا لم يُفحص. ومنظومةٌ كلها تفعل ذلك تُخرج تقريرًا خاليًا
من المخالفات عن ورقةٍ لم يُقرأ منها شيء. فالجهل يُعلَن باسمه.

## ولا قاعدة تحجب اليوم

`status` تبدأ `DRAFT` لكل قاعدة، و`EvaluationReport.blocking` لا تعدّ إلا
ما كانت قاعدته `APPROVED`. فالنتيجة اليوم: كل ما يخرج من هذا المحرّك
**استشاري**، ولا سطر منه يوقف باحثًا.

وهذا مقصود لا نقصان. القاعدة العلمية تصير حاجزًا حين يراجعها مختصّ ويوقّع
عليها، لا حين يكتبها من كتب الشيفرة. ومحرّكٌ يحجب بقواعد كتبها مبرمج بلا
مراجعة يوقف بحثًا صحيحًا باسم النزاهة — وهو ضررٌ من جنس الضرر الذي يمنعه.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Final

from pydantic import BaseModel, ConfigDict, Field

from ..services.inbox import ALERT_SEVERITIES, is_blocking
from ..services.publishing.vocab import MANUSCRIPT_SECTIONS
from .ontology import ResearchGraph


class RuleStatus(str, Enum):
    """رتبة القاعدة — و`DRAFT` وحدها ما يستطيع كاتبُ الشيفرة أن يمنحه."""

    DRAFT = "DRAFT"
    EXPERT_REVIEWED = "EXPERT_REVIEWED"
    APPROVED = "APPROVED"
    DEPRECATED = "DEPRECATED"


class RuleCategory(str, Enum):
    CAUSALITY = "causality"
    FABRICATION = "fabrication"
    DESIGN_FIT = "design_fit"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    LINEAGE = "lineage"


class Verdict(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class BrainFieldView(BaseModel):
    """حقلٌ من حقول «ما نعرفه عن هذا البحث» بحالته وسنده.

    الحالات الأربع منقولة عن التعليق الذي يحكم الحقل في
    `services/workspace.py` — ولا تُعرَّف هنا من جديد. و`known` هناك تُمنح
    لوجود **ذاكرة موثقة**، لا لوجود مرشّح.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    state: str = Field(pattern="^(known|needs_review|missing|conflicting)$")
    backing_memory_ids: tuple[str, ...] = ()
    backing_candidate_ids: tuple[str, ...] = ()


class CandidateView(BaseModel):
    """مرشّح حقيقة مستخرَج — بحالته الأربع كما في ترحيل 0016."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    status: str = Field(pattern="^(unverified|approved|rejected|unknown)$")


class Assessment(BaseModel):
    """لقطةُ ما يُحكَم عليه — كاملةً ومغلقة.

    **لا جلسة ولا كائن ORM هنا.** الدرس مسجَّل في `drafting/context.py`
    و`planning/context.py`: بنيةٌ تعبر حدّ المعاملة وهي تحمل كائنًا حيًّا
    تقرأ لاحقًا من قاعدةٍ أُغلقت. وهنا يضاف سببٌ ثانٍ: لقطةٌ خالصة تجعل كل
    قاعدة قابلة للاختبار بلا قاعدة بيانات، فيصير الإثبات ممكنًا لا موعودًا.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    graph: ResearchGraph = Field(default_factory=ResearchGraph)
    # نصّ المخطوطة: مفتاحه اسم القسم من `MANUSCRIPT_SECTIONS`.
    sections: dict[str, str] = Field(default_factory=dict)
    fields: tuple[BrainFieldView, ...] = ()
    candidates: tuple[CandidateView, ...] = ()
    # أرقام العيّنة الواردة في النصّ — تُستخرَج بمحلّل الأرقام القائم لا هنا.
    sample_numbers_in_text: tuple[float, ...] = ()

    def narrative(self) -> str:
        """كل نصّ المخطوطة موصولًا — بترتيب `MANUSCRIPT_SECTIONS` لا بترتيب القاموس.

        ترتيب القاموس ترتيبُ الإدخال، فيتغيّر النصّ الموصول بتغيّر ترتيب
        الكتابة وحده — ويصير مخرَجٌ حتميّ غيرَ حتميّ بلا سبب.
        """
        return "\n".join(
            self.sections[key] for key in MANUSCRIPT_SECTIONS if self.sections.get(key)
        )

    def candidate(self, candidate_id: str) -> CandidateView | None:
        for row in self.candidates:
            if row.id == candidate_id:
                return row
        return None


@dataclass(frozen=True, slots=True)
class RuleFinding:
    """مخالفةٌ واحدة بموضعها — لا رسالة عامة.

    `entity_ids` تُذكر لأن «هناك مشكلة في مكانٍ ما» ليست نتيجة قابلة
    للتصحيح؛ والمستودع يفعل هذا في `Finding.element_ids`
    و`GuardViolation.excerpt` معًا.
    """

    rule_id: str
    detail_ar: str
    detail_en: str
    entity_ids: tuple[str, ...] = ()
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class RuleOutcome:
    verdict: Verdict
    findings: tuple[RuleFinding, ...] = ()


def passed() -> RuleOutcome:
    return RuleOutcome(Verdict.PASS)


def not_applicable() -> RuleOutcome:
    return RuleOutcome(Verdict.NOT_APPLICABLE)


def violated(*findings: RuleFinding) -> RuleOutcome:
    if not findings:  # pragma: no cover - حارس ضد مخالفةٍ بلا موضع
        raise ValueError("a violation must name what it found")
    return RuleOutcome(Verdict.VIOLATION, findings)


def insufficient(*findings: RuleFinding) -> RuleOutcome:
    """«لم أستطع الفحص» — ومعها ما لُوحظ إن لُوحظ شيء.

    والملاحظات تُحمل ولا تُطرح: قاعدةٌ رأت لغةً سببية ولم تعرف التصميم
    يجب أن تقول ما رأته، وإلا ضاع ما رأته لأن الحكم لم يكتمل.
    """
    return RuleOutcome(Verdict.INSUFFICIENT_INFORMATION, findings)


Predicate = Callable[[Assessment], RuleOutcome]


@dataclass(frozen=True, slots=True)
class ScientificRule:
    """قاعدة علمية واحدة: ما تقوله، ومن أين جاءت، ومن راجعها.

    `provenance` إلزامية وغير فارغة. قاعدةٌ بلا مصدر لا تُناقَش ولا تُراجَع
    ولا تسقط حين يتبيّن خطؤها: تصير عرفًا في الشيفرة يتوارثه من بعدنا بلا
    أن يعرف أحدٌ لمَ هو هناك.

    `related_issue_keys` تربط القاعدة بمفاتيح الفحوص القائمة في المستودع —
    فيُعرف عند التفعيل أين يقع الازدواج، ولا يخرج للباحث تنبيهان لعطبٍ واحد.
    """

    id: str
    category: RuleCategory
    severity: str
    condition_ar: str
    condition_en: str
    message_ar: str
    message_en: str
    provenance: str
    predicate: Predicate
    related_issue_keys: tuple[str, ...] = ()
    version: int = 1
    status: RuleStatus = RuleStatus.DRAFT

    def __post_init__(self) -> None:
        if self.severity not in ALERT_SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")
        if not self.provenance.strip():
            raise ValueError(f"rule {self.id} has no provenance")
        if not any("؀" <= ch <= "ۿ" for ch in self.message_ar):
            raise ValueError(f"rule {self.id} has no Arabic message")
        if not self.message_en.strip():
            raise ValueError(f"rule {self.id} has no English message")

    @property
    def is_enforceable(self) -> bool:
        """هل يجوز أن تحجب هذه القاعدة؟ `APPROVED` وحدها.

        و`EXPERT_REVIEWED` **لا تحجب**: مراجعة المختصّ تقول «القاعدة صحيحة
        علميًّا»، والاعتماد يقول «وقد قرّرنا أن نوقف عليها العمل». وهما
        قراران لجهتين، ودمجهما يجعل رأيًا علميًّا يوقف باحثًا قبل أن يقرّر
        أحدٌ ذلك.
        """
        return self.status is RuleStatus.APPROVED

    @property
    def blocks(self) -> bool:
        return self.is_enforceable and is_blocking(self.severity)


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule: ScientificRule
    outcome: RuleOutcome

    @property
    def findings(self) -> tuple[RuleFinding, ...]:
        return self.outcome.findings


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    results: tuple[RuleResult, ...] = field(default_factory=tuple)

    @property
    def violations(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.outcome.verdict is Verdict.VIOLATION)

    @property
    def unevaluated(self) -> tuple[RuleResult, ...]:
        """ما لم يُفحص — يُعرض بقدر ما يُعرض المخالَف.

        تقريرٌ يذكر المخالفات ويصمت عمّا عجز عنه يقرأه الباحث «سليم»، وهو
        أخطر من تقريرٍ يذكر مخالفةً زائدة.
        """
        return tuple(
            r for r in self.results if r.outcome.verdict is Verdict.INSUFFICIENT_INFORMATION
        )

    @property
    def blocking(self) -> tuple[RuleResult, ...]:
        """المخالفات الحاجبة — **فارغةٌ ما دامت كل قاعدة `DRAFT`**."""
        return tuple(r for r in self.violations if r.rule.blocks)

    @property
    def advisory(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.violations if not r.rule.blocks)

    def by_rule(self, rule_id: str) -> RuleResult | None:
        for result in self.results:
            if result.rule.id == rule_id:
                return result
        return None

    def verdict_of(self, rule_id: str) -> Verdict | None:
        result = self.by_rule(rule_id)
        return result.outcome.verdict if result else None


def evaluate(assessment: Assessment, rules: tuple[ScientificRule, ...]) -> EvaluationReport:
    """يشغّل كل القواعد ويعيد كل الأحكام — ولا يتوقف عند أول مخالفة.

    الترتيب بالمعرّف لا بترتيب الكتابة، فيخرج التقرير نفسه لكل تشغيلة —
    وهو ما يجعل مقارنة تقريرين ممكنة أصلًا.

    **ولا `try` حول المُسنِد.** استثناءٌ في قاعدة حتمية عطبٌ في القاعدة،
    وابتلاعُه يجعلها تُعدّ «سليمة» في كل تشغيلة بعده — فيموت الحارس صامتًا
    ويبقى اسمه في التقرير.
    """
    deprecated = tuple(r for r in rules if r.status is RuleStatus.DEPRECATED)
    if deprecated:  # قاعدة مهجورة لا تُشغَّل ولا تُحذف من السجل — تُترك بتاريخها.
        rules = tuple(r for r in rules if r.status is not RuleStatus.DEPRECATED)
    return EvaluationReport(
        results=tuple(
            RuleResult(rule=rule, outcome=rule.predicate(assessment))
            for rule in sorted(rules, key=lambda r: r.id)
        )
    )


ENFORCEABLE_STATUSES: Final = frozenset({RuleStatus.APPROVED})
