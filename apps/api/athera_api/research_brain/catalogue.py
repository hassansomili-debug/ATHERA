"""سجل القواعد العلمية | The scientific rule catalogue (V1).

عشر قواعد، كلٌّ منها دالةٌ تُشغَّل وتُختبر — لا وصفٌ في وثيقة. وكلها
`DRAFT`: لم يراجعها مختصّ بعد، فلا واحدة منها تحجب اليوم (انظر
`ScientificRule.is_enforceable`).

**والمفردات كلها مستوردة أو منقولة بمرجعها.** أسماء الحالات هنا — `included`
و`saved_only` و`approved` و`known` و`model_output` — هي أسماؤها في القاعدة
والخدمات، لا مرادفاتٌ اختيرت هنا. واسمُ حالةٍ يُكتب من الذاكرة بدل أن يُقرأ
من مصدره هو أكثر عطبٍ تكرارًا في هذا المستودع، وقاعدةٌ تحرس النزاهة باسم
حالةٍ لا وجود له لا تُطلق أبدًا: تمرّ صامتةً وتبدو عاملة.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..services.analysis.vocab import TEST_KINDS
from ..services.golden_thread.language import find_causal_language
from ..services.golden_thread.methodology import REQUIREMENTS
from ..services.golden_thread.vocab import CAUSAL_DESIGNS
from .ontology import EntityKind, RelationKind
from .rules import (
    Assessment,
    RuleCategory,
    RuleFinding,
    RuleOutcome,
    ScientificRule,
    insufficient,
    not_applicable,
    passed,
    violated,
)
from .values import ValueState

# ── 1. اللغة السببية والتصميم ─────────────────────────────────────────────

RB_CAUSALITY_01 = "RB-CAUSALITY-01"


def _causal_language_requires_causal_design(a: Assessment) -> RuleOutcome:
    """التصميم الوصفي أو المقطعي لا يبرّر لغةً سببية.

    والكشف نفسه المستعمَل في §15.2 يُستدعى هنا ولا يُعاد كتابته: مجموعة
    أنماطٍ ثانية للسببية تفترق عن الأولى بعد شهرين، فيصير النصّ مخالفًا في
    شاشةٍ وسليمًا في أخرى.
    """
    text = a.narrative()
    if not text.strip():
        return not_applicable()

    design = a.graph.one_of_kind(EntityKind.DESIGN)
    study_type = getattr(design, "study_type", None) if design else None
    design_family = getattr(design, "design_family", None) if design else None
    temporal = getattr(design, "temporal_frame", "unknown") if design else "unknown"

    # يُفحص النص أولًا **كأن التصميم غير سببي**، فتُعرف الجمل موضعَ الحكم
    # قبل أن يُقرَّر هل هي مشروعة.
    hits = find_causal_language(text, design_family=None, study_type="")
    if not hits:
        return passed()

    if (study_type or "") in CAUSAL_DESIGNS or (design_family or "") in CAUSAL_DESIGNS:
        return not_applicable()

    findings = tuple(
        RuleFinding(
            RB_CAUSALITY_01,
            f"لغة سببية «{hit.matched}» في تصميم لا يسندها"
            + (f" (التصميم: {design_family})" if design_family else " (التصميم غير مسجَّل)")
            + ("، وإطارٌ زمني مقطعي لا يفصل السبب عن الأثر." if temporal == "cross_sectional"
               else "."),
            f"Causal wording '{hit.matched}' in a design that does not license it"
            + (f" (design: {design_family})" if design_family else " (design not recorded)")
            + ("; a cross-sectional frame cannot separate cause from effect."
               if temporal == "cross_sectional" else "."),
            entity_ids=(design.id,) if design else (),
            excerpt=hit.sentence,
        )
        for hit in hits
    )

    # تصميمٌ غير مسجَّل: الجمل تُعرض ولا يُحكم عليها. و«لا نعرف التصميم» ليست
    # براءة — وهي أيضًا ليست إدانة.
    if design is None or (study_type is None and design_family is None):
        return insufficient(*findings)
    return violated(*findings)


# ── 2. قيمة الدلالة ───────────────────────────────────────────────────────

RB_FABRICATION_01 = "RB-FABRICATION-01"


def _p_value_must_come_from_an_analysis_run(a: Assessment) -> RuleOutcome:
    """قيمة p لا تُكتب إلا وقد أنتجتها تشغيلة تحليل بعينها.

    والعطب الإنتاجي المسجَّل في `drafting/context.py` هو الشاهد: النموذج
    تلقّى `t = 3.738, df = 118` بلا p، فاشتقّ الدلالة بنفسه. والاشتقاق
    اختلاقٌ مهما بدا حسابيًّا سليمًا — الكتابة ليست محرّك تحليل.
    """
    findings_with_p = [
        f for f in a.graph.of_kind(EntityKind.FINDING)
        if getattr(f, "p_value").state is not ValueState.MISSING
    ]
    if not findings_with_p:
        return not_applicable()

    analysis_ids = {node.id for node in a.graph.of_kind(EntityKind.ANALYSIS)}
    violations: list[RuleFinding] = []
    unresolved: list[RuleFinding] = []

    for finding in findings_with_p:
        quantity = getattr(finding, "p_value")
        if quantity.state is ValueState.UNKNOWN:
            unresolved.append(RuleFinding(
                RB_FABRICATION_01,
                f"النتيجة «{finding.label_ar}» تحمل قيمة دلالة غير معروفة — "
                "ولا تُكتب رقمًا حتى تُنتَج.",
                f"Finding '{finding.label_ar}' carries an UNKNOWN p-value; "
                "it is not written as a number until it is produced.",
                entity_ids=(finding.id,),
            ))
            continue

        derived_from = set(a.graph.targets(RelationKind.FINDING_DERIVED_FROM_ANALYSIS, finding.id))
        if quantity.source_ref not in analysis_ids:
            violations.append(RuleFinding(
                RB_FABRICATION_01,
                f"قيمة p للنتيجة «{finding.label_ar}» منسوبة إلى "
                f"«{quantity.source_ref}» ولا تشغيلة بهذا المعرّف — نسبةٌ إلى ما لا وجود له.",
                f"The p-value of '{finding.label_ar}' is attributed to "
                f"'{quantity.source_ref}', which is not an analysis in this project.",
                entity_ids=(finding.id,),
            ))
        elif quantity.source_ref not in derived_from:
            # التشغيلة موجودة، لكن النتيجة لا تُشتقّ منها. وهذا عطبُ ربط لا
            # اختلاق — والتفريق بينهما يجعل الخلل يُطارَد في موضعه.
            violations.append(RuleFinding(
                RB_FABRICATION_01,
                f"قيمة p للنتيجة «{finding.label_ar}» تشير إلى تشغيلة "
                f"«{quantity.source_ref}» لا تُشتقّ منها النتيجة.",
                f"The p-value of '{finding.label_ar}' points at analysis "
                f"'{quantity.source_ref}', which the finding is not derived from.",
                entity_ids=(finding.id,),
            ))

    if violations:
        return violated(*violations)
    if unresolved:
        return insufficient(*unresolved)
    return passed()


# ── 3. حجم العيّنة ────────────────────────────────────────────────────────

RB_FABRICATION_02 = "RB-FABRICATION-02"


def _sample_size_must_never_be_invented(a: Assessment) -> RuleOutcome:
    """حجم العيّنة غير المسجَّل يُكتب «غير مسجَّل» — ولا يُملأ برقم.

    و«غير مسجَّل» جوابٌ صحيح يمرّ إلى المخطوطة كما هو. أما رقمٌ يظهر في
    النصّ بلا عيّنة تسنده فهو `unsupported_sample_number` نفسه الذي يمنعه
    فاحص المسودّات.
    """
    sample = a.graph.one_of_kind(EntityKind.SAMPLE)
    numbers = a.sample_numbers_in_text

    if sample is None:
        if not numbers:
            return not_applicable()
        return violated(RuleFinding(
            RB_FABRICATION_02,
            f"رقم عيّنة في النصّ ({', '.join(f'{n:g}' for n in numbers)}) ولا عيّنة مسجَّلة "
            "في البحث تسنده.",
            f"A sample number appears in the text ({', '.join(f'{n:g}' for n in numbers)}) "
            "with no sample recorded in the project behind it.",
        ))

    size = getattr(sample, "size")
    if size.state is ValueState.KNOWN:
        return passed()

    label_ar, label_en = size.label()
    if numbers:
        return violated(RuleFinding(
            RB_FABRICATION_02,
            f"حجم العيّنة {label_ar}، ومع ذلك يظهر في النصّ "
            f"({', '.join(f'{n:g}' for n in numbers)}). والرقم مخترَع لا مستخرَج.",
            f"The sample size is {label_en}, yet the text states "
            f"({', '.join(f'{n:g}' for n in numbers)}). That number is invented, not extracted.",
            entity_ids=(sample.id,),
        ))

    return insufficient(RuleFinding(
        RB_FABRICATION_02,
        f"حجم العيّنة {label_ar} — ويُكتب هكذا، ولا يُقدَّر ولا يُحسب من غيره.",
        f"The sample size is {label_en} — it is written as such, never estimated "
        "and never derived from something else.",
        entity_ids=(sample.id,),
    ))


# ── 4. الفروض والتصميم الكيفي ─────────────────────────────────────────────

RB_DESIGN_01 = "RB-DESIGN-01"


def _qualitative_study_must_not_carry_hypotheses(a: Assessment) -> RuleOutcome:
    """الدراسة الكيفية لا تُحمَّل فروضًا.

    والحكم **يُقرأ من جدول §16 القائم** لا يُكتب شرطًا هنا: `hypotheses`
    مطلبٌ في `QUANTITATIVE` وليس في `QUALITATIVE`. فإضافة تصميمٍ جديد إلى
    ذلك الجدول تصحّ هذه القاعدة تلقائيًّا، ولا تحتاج تعديلها — وهو المبدأ
    نفسه المسجَّل في رأس `methodology.py`: بيانات لا شيفرة شرطية.
    """
    hypotheses = a.graph.of_kind(EntityKind.HYPOTHESIS)
    if not hypotheses:
        return not_applicable()

    design = a.graph.one_of_kind(EntityKind.DESIGN)
    study_type = getattr(design, "study_type", None) if design else None
    if study_type is None:
        return insufficient(RuleFinding(
            RB_DESIGN_01,
            f"في البحث {len(hypotheses)} فرضًا ونوع الدراسة غير مسجَّل — "
            "فلا يُعرف أهي مشروعة فيه أم لا.",
            f"The project carries {len(hypotheses)} hypotheses with no recorded study type, "
            "so whether they belong cannot be judged.",
            entity_ids=tuple(h.id for h in hypotheses),
        ))

    requirements = REQUIREMENTS.get(study_type)
    if requirements is None:  # pragma: no cover - `Design` يرفض نوعًا خارج المفردة
        return insufficient(RuleFinding(
            RB_DESIGN_01, f"نوع دراسة غير معروف: {study_type}.",
            f"Unknown study type: {study_type}.",
        ))

    if "hypotheses" in {req.key for req in requirements}:
        return not_applicable()

    return violated(RuleFinding(
        RB_DESIGN_01,
        f"تصميم «{study_type}» لا يستلزم فروضًا في §16، وفي البحث "
        f"{len(hypotheses)} منها. والفرض المفروض على دراسةٍ كيفية يحوّل "
        "الاستكشاف إلى اختبارٍ لم يُصمَّم له.",
        f"Design '{study_type}' requires no hypotheses under §16, yet the project carries "
        f"{len(hypotheses)}. Forcing hypotheses onto a qualitative study turns exploration "
        "into a test it was never designed for.",
        entity_ids=tuple(h.id for h in hypotheses),
    ))


# ── 5. مطابقة الاختبار للتصميم والمتغيرات والافتراضات ─────────────────────

RB_DESIGN_02 = "RB-DESIGN-02"

_INTERVAL_OR_RATIO: Final = frozenset({"interval", "ratio"})
_NOMINAL: Final = frozenset({"nominal"})


@dataclass(frozen=True, slots=True)
class TestFitness:
    """ما يستلزمه اختبارٌ من مقاييس وافتراضات.

    والافتراضات تُسمّى ولا تُعدّ: «الافتراضات محقّقة» جملةٌ لا تُراجَع، أما
    «التجانس لم يُفحص» فعملٌ معلوم لمن يقرأه.
    """

    outcome_scales: frozenset[str]
    predictor_scales: frozenset[str]
    assumptions: tuple[str, ...]
    group_count: tuple[int, int] | None = None   # (الأدنى، الأعلى)
    study_types: frozenset[str] | None = None


# **ما لا نملك فيه حكمًا لا يُكتب هنا.** ثمانية من `TEST_KINDS` الخمسة عشر
# غائبة عمدًا (`sem` و`pls_sem` و`mediation` و`moderation` و`factor_analysis`
# و`reliability` و`validity` و`descriptive`): شروط ملاءمتها ليست جدولًا
# بسيطًا من مقاييس، وكتابة جدولٍ ناقص لها يجعل القاعدة تُصدر حكمًا لا تملكه.
# فتُرجِع القاعدة عنها `insufficient_information` باسمها.
TEST_FITNESS: Final[dict[str, TestFitness]] = {
    "t_test": TestFitness(
        outcome_scales=_INTERVAL_OR_RATIO, predictor_scales=_NOMINAL,
        assumptions=("normality", "homogeneity_of_variance", "independence"),
        group_count=(2, 2),
    ),
    "anova": TestFitness(
        outcome_scales=_INTERVAL_OR_RATIO, predictor_scales=_NOMINAL,
        assumptions=("normality", "homogeneity_of_variance", "independence"),
        group_count=(2, 99),
    ),
    "ancova": TestFitness(
        outcome_scales=_INTERVAL_OR_RATIO, predictor_scales=_NOMINAL,
        assumptions=("normality", "homogeneity_of_variance", "independence",
                     "homogeneity_of_regression_slopes"),
        group_count=(2, 99),
    ),
    "chi_square": TestFitness(
        outcome_scales=_NOMINAL, predictor_scales=_NOMINAL,
        assumptions=("expected_cell_counts", "independence"),
    ),
    "correlation": TestFitness(
        outcome_scales=_INTERVAL_OR_RATIO, predictor_scales=_INTERVAL_OR_RATIO,
        assumptions=("linearity", "normality"),
    ),
    "regression": TestFitness(
        outcome_scales=_INTERVAL_OR_RATIO,
        predictor_scales=frozenset({"nominal", "ordinal", "interval", "ratio"}),
        assumptions=("linearity", "independence_of_errors", "homoscedasticity",
                     "no_multicollinearity"),
    ),
    "thematic_coding": TestFitness(
        outcome_scales=frozenset(), predictor_scales=frozenset(),
        assumptions=(),
        study_types=frozenset({"qualitative", "mixed_methods"}),
    ),
}


def _scale_mismatch(analysis, fitness: TestFitness) -> list[str]:
    problems: list[str] = []
    outcome = getattr(analysis, "outcome_scale", None)
    predictor = getattr(analysis, "predictor_scale", None)
    if fitness.outcome_scales and outcome is not None and outcome not in fitness.outcome_scales:
        problems.append(f"مقياس المتغير التابع «{outcome}» لا يقبله هذا الاختبار")
    if (fitness.predictor_scales and predictor is not None
            and predictor not in fitness.predictor_scales):
        problems.append(f"مقياس المتغير المستقل «{predictor}» لا يقبله هذا الاختبار")
    if fitness.group_count is not None:
        count = getattr(analysis, "group_count", None)
        if count is not None:
            low, high = fitness.group_count
            if not low <= count <= high:
                problems.append(f"عدد المجموعات {count} خارج ما يقبله هذا الاختبار")
    return problems


def _statistical_test_must_match_design(a: Assessment) -> RuleOutcome:
    """الاختبار يطابق التصميم وأنواع المتغيرات والافتراضات — وإلا فالرقم بلا معنى.

    واختبارٌ لم تُفحص افتراضاته ليس ناجحًا ولا فاشلًا: هو **غير مفحوص**،
    وهذا ما تقوله القاعدة بدل أن تفترض أحدهما.
    """
    analyses = a.graph.of_kind(EntityKind.ANALYSIS)
    if not analyses:
        return not_applicable()

    design = a.graph.one_of_kind(EntityKind.DESIGN)
    study_type = getattr(design, "study_type", None) if design else None

    violations: list[RuleFinding] = []
    unresolved: list[RuleFinding] = []

    for analysis in analyses:
        test_kind = getattr(analysis, "test_kind", None)
        if test_kind is None:
            unresolved.append(RuleFinding(
                RB_DESIGN_02,
                f"التشغيلة «{analysis.label_ar}» بلا نوع اختبار مسجَّل.",
                f"Analysis '{analysis.label_ar}' records no test kind.",
                entity_ids=(analysis.id,)))
            continue

        fitness = TEST_FITNESS.get(test_kind)
        if fitness is None:
            unresolved.append(RuleFinding(
                RB_DESIGN_02,
                f"لا قاعدة ملاءمةٍ مسجَّلة للاختبار «{test_kind}» — ولا يُحكم بما لا يُعرف.",
                f"No recorded fitness rule for test '{test_kind}'; no verdict is issued "
                "on what is not known.",
                entity_ids=(analysis.id,)))
            continue

        problems = _scale_mismatch(analysis, fitness)
        if (fitness.study_types is not None and study_type is not None
                and study_type not in fitness.study_types):
            problems.append(f"الاختبار «{test_kind}» لا يُجرى على تصميم «{study_type}»")

        if problems:
            violations.append(RuleFinding(
                RB_DESIGN_02,
                f"الاختبار «{test_kind}» في «{analysis.label_ar}»: " + "؛ ".join(problems) + ".",
                f"Test '{test_kind}' in '{analysis.label_ar}' does not match the design "
                "or the variable types.",
                entity_ids=(analysis.id,)))
            continue

        recorded = getattr(analysis, "assumptions", {})
        failed = [name for name in fitness.assumptions if recorded.get(name) is False]
        unchecked = [name for name in fitness.assumptions if recorded.get(name) is None]
        if failed:
            violations.append(RuleFinding(
                RB_DESIGN_02,
                f"افتراضات «{test_kind}» فُحصت ولم تتحقّق: {'، '.join(failed)}.",
                f"Assumptions of '{test_kind}' were checked and failed: {', '.join(failed)}.",
                entity_ids=(analysis.id,)))
        elif unchecked:
            unresolved.append(RuleFinding(
                RB_DESIGN_02,
                f"افتراضات «{test_kind}» لم تُفحص: {'، '.join(unchecked)} — "
                "ولا يُقال إن الاختبار مناسب قبل فحصها.",
                f"Assumptions of '{test_kind}' were never checked: {', '.join(unchecked)}; "
                "the test is not called appropriate before they are.",
                entity_ids=(analysis.id,)))

    if violations:
        return violated(*violations)
    if unresolved:
        return insufficient(*unresolved)
    return passed()


# ── 6. تغيّر البيانات ─────────────────────────────────────────────────────

RB_LINEAGE_01 = "RB-LINEAGE-01"


def _dataset_change_invalidates_dependent_work(a: Assessment) -> RuleOutcome:
    """استبدال البيانات يُبطل ما بُني عليها — تحليلًا ونتيجةً وتوصية.

    و«تغيّرت» سؤالٌ يُجاب بمقارنة معرّفَي تجميد لا بحكمٍ تقديري:
    `analysis_runs.dataset_freeze_id` مقابل تجميد المجموعة الحالي. والتشغيلة
    القديمة لا تُحذف ولا تُصحَّح — تُوسَم بأنها جرت على بياناتٍ غير هذه.

    **والأثر يتعدّى التشغيلة.** نتيجةٌ اشتُقّت منها وتوصيةٌ بُنيت على النتيجة
    كلتاهما قديمة، ولو ذُكرت التشغيلة وحدها لبقيت التوصية في المخطوطة تبدو
    قائمة.
    """
    links = a.graph.links(RelationKind.ANALYSIS_USES_DATASET)
    if not links:
        return not_applicable()

    violations: list[RuleFinding] = []
    unresolved: list[RuleFinding] = []
    stale_analysis_ids: set[str] = set()

    for link in links:
        analysis = a.graph.by_id(link.source_id)
        dataset = a.graph.by_id(link.target_id)
        run_freeze = getattr(analysis, "dataset_freeze_id", None)
        current_freeze = getattr(dataset, "current_freeze_id", None)

        if run_freeze is None or current_freeze is None:
            # `data_not_frozen` نفسه: تحليلٌ على بياناتٍ غير مجمَّدة لا يُقال
            # عنه «قديم» ولا «حديث» — يُقال إنه غير قابل للإعادة أصلًا.
            unresolved.append(RuleFinding(
                RB_LINEAGE_01,
                f"التشغيلة «{analysis.label_ar}» أو مجموعة «{dataset.label_ar}» "
                "بلا معرّف تجميد — فلا يُعرف أهي على البيانات الحالية أم لا.",
                f"Analysis '{analysis.label_ar}' or dataset '{dataset.label_ar}' carries no "
                "freeze id, so whether it ran on the current data cannot be known.",
                entity_ids=(analysis.id, dataset.id)))
            continue

        if run_freeze != current_freeze:
            stale_analysis_ids.add(analysis.id)
            violations.append(RuleFinding(
                RB_LINEAGE_01,
                f"التشغيلة «{analysis.label_ar}» جرت على تجميد «{run_freeze}» "
                f"ومجموعة «{dataset.label_ar}» صارت عند «{current_freeze}» — "
                "نتيجتها لا تصف البيانات الحالية.",
                f"Analysis '{analysis.label_ar}' ran on freeze '{run_freeze}' while dataset "
                f"'{dataset.label_ar}' is now at '{current_freeze}'; its result no longer "
                "describes the current data.",
                entity_ids=(analysis.id, dataset.id)))

    for finding in a.graph.of_kind(EntityKind.FINDING):
        sources = set(a.graph.targets(RelationKind.FINDING_DERIVED_FROM_ANALYSIS, finding.id))
        if not sources & stale_analysis_ids:
            continue
        violations.append(RuleFinding(
            RB_LINEAGE_01,
            f"النتيجة «{finding.label_ar}» مشتقّة من تشغيلة على بياناتٍ استُبدلت.",
            f"Finding '{finding.label_ar}' derives from an analysis run on replaced data.",
            entity_ids=(finding.id,)))
        for rec_id in a.graph.sources(RelationKind.RECOMMENDATION_DERIVED_FROM_FINDING, finding.id):
            recommendation = a.graph.by_id(rec_id)
            violations.append(RuleFinding(
                RB_LINEAGE_01,
                f"التوصية «{recommendation.label_ar}» مبنيّة على نتيجةٍ سقط سندها.",
                f"Recommendation '{recommendation.label_ar}' rests on a finding whose "
                "support fell away.",
                entity_ids=(rec_id,)))

    if violations:
        return violated(*violations)
    if unresolved:
        return insufficient(*unresolved)
    return passed()


# ── 7. المصدر المحفوظ ليس دليلًا ──────────────────────────────────────────

RB_EVIDENCE_01 = "RB-EVIDENCE-01"


def _saved_only_source_cannot_support_a_claim(a: Assessment) -> RuleOutcome:
    """مصدرٌ في `saved_only` لا يسند ادّعاءً.

    و`saved_only` هي **القيمة الافتراضية** في `project_sources` (ترحيل
    0020): المصدر يبدأ محفوظًا لا مُدرَجًا، وإدراجه قرارٌ بشريٌّ منسوبٌ إلى
    قائله ووقته — وقيد `ck_project_source_decision_actor` يفرض ذلك.

    فحسابُ المحفوظ دليلًا يبني ورقةً على ما لم يقرّر أحدٌ أنه يُبنى عليه،
    ويجعل الافتراضي قرارًا لم يُتّخذ.
    """
    links = a.graph.links(RelationKind.SOURCE_SUPPORTS_CLAIM)
    if not links:
        return not_applicable()

    violations: list[RuleFinding] = []
    for link in links:
        source = a.graph.by_id(link.source_id)
        claim = a.graph.by_id(link.target_id)
        state = getattr(source, "use_state")
        if state == "included":
            continue
        if state == "saved_only":
            detail_ar = (f"المصدر «{source.label_ar}» في حالة `saved_only`: محفوظٌ للقراءة "
                         "ولم يقرّر الباحث إدراجه بعد — فلا يسند الادّعاء "
                         f"«{claim.label_ar}».")
            detail_en = (f"Source '{source.label_ar}' is `saved_only`: kept for reading, not yet "
                         f"decided upon — it does not support claim '{claim.label_ar}'.")
        else:
            detail_ar = (f"المصدر «{source.label_ar}» في حالة `excluded`: نُظر فيه واستُبعد، "
                         f"واستعماله سندًا للادّعاء «{claim.label_ar}» نقضٌ لقرارٍ مسجَّل.")
            detail_en = (f"Source '{source.label_ar}' is `excluded`: examined and rejected; using "
                         f"it behind claim '{claim.label_ar}' overturns a recorded decision.")
        violations.append(RuleFinding(
            RB_EVIDENCE_01, detail_ar, detail_en, entity_ids=(source.id, claim.id)))

    return violated(*violations) if violations else passed()


# ── 8. المرشّح ليس معرفة ──────────────────────────────────────────────────

RB_PROVENANCE_01 = "RB-PROVENANCE-01"


def _unapproved_candidate_cannot_become_known(a: Assessment) -> RuleOutcome:
    """المرشّح المستخرَج لا يصير `known` قبل اعتماد الباحث.

    و`known` في «ما نعرفه عن هذا البحث» تُمنح لوجود **ذاكرة موثقة**، لا
    لوجود مرشّح — والمسار الوحيد بينهما هو `approve_candidate` في §7.4.
    وحالتا `unverified` و`unknown` كلتاهما «لم يُحكم بعد»: الأولى لم تُقرأ،
    والثانية قُرئت ولم يستطع الباحث الحكم. ولا واحدة منهما اعتماد.
    """
    declared_known = [row for row in a.fields if row.state == "known"]
    if not declared_known:
        return not_applicable()

    violations: list[RuleFinding] = []
    for row in declared_known:
        if row.backing_memory_ids:
            continue
        if not row.backing_candidate_ids:
            violations.append(RuleFinding(
                RB_PROVENANCE_01,
                f"الحقل «{row.key}» معلَنٌ `known` ولا ذاكرة ولا مرشّح خلفه.",
                f"Field '{row.key}' is declared `known` with neither a memory nor a "
                "candidate behind it.",
            ))
            continue
        for candidate_id in row.backing_candidate_ids:
            candidate = a.candidate(candidate_id)
            status = candidate.status if candidate else "unverified"
            if status == "approved":
                # مرشّح معتمَد بلا ذاكرة ناتجة: الاعتماد جرى والترقية لم تكتمل.
                violations.append(RuleFinding(
                    RB_PROVENANCE_01,
                    f"الحقل «{row.key}» معلَنٌ `known` استنادًا إلى مرشّح معتمَد "
                    f"«{candidate_id}» لم تنتج عنه ذاكرة موثقة.",
                    f"Field '{row.key}' is declared `known` from approved candidate "
                    f"'{candidate_id}', but no verified memory came out of it.",
                ))
            else:
                violations.append(RuleFinding(
                    RB_PROVENANCE_01,
                    f"الحقل «{row.key}» معلَنٌ `known` استنادًا إلى مرشّح حالته "
                    f"«{status}» — ولم يعتمده الباحث.",
                    f"Field '{row.key}' is declared `known` from a candidate whose status is "
                    f"'{status}'; the researcher never approved it.",
                ))

    return violated(*violations) if violations else passed()


# ── 9. الادّعاء بلا دليل يبقى بلا دليل ────────────────────────────────────

RB_EVIDENCE_02 = "RB-EVIDENCE-02"


def _factual_claim_without_evidence_stays_unsupported(a: Assessment) -> RuleOutcome:
    """ادّعاءٌ يُعرض حقيقةً بلا دليل حالته `evidence_gap` — لا `supported`.

    والقاعدة **لا تحذف الادّعاء ولا تعيد صياغته**: تسمّي حالته. الحذف يخفي
    فكرةً قد تكون صحيحة وينتظر دليلها، وإعادة الصياغة تجعل النظام يكتب مكان
    الباحث. أما التسمية فتترك القرار له ولا تدع الادّعاء يمرّ مسنَدًا.

    و`interpretation` و`proposal` خارج القاعدة: التفسير والمقترح لا يُعرضان
    حقيقةَ مصدر أصلًا، ومطالبتهما بدليلٍ مباشر تعاقب الصدق في التوسيم.
    """
    claims = [c for c in a.graph.of_kind(EntityKind.CLAIM)
              if getattr(c, "origin") == "fact"]
    if not claims:
        return not_applicable()

    violations: list[RuleFinding] = []
    for claim in claims:
        evidence_ids = a.graph.targets(RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE, claim.id)
        included_sources = [
            sid for sid in a.graph.sources(RelationKind.SOURCE_SUPPORTS_CLAIM, claim.id)
            if getattr(a.graph.by_id(sid), "use_state") == "included"
        ]
        if evidence_ids or included_sources:
            continue
        violations.append(RuleFinding(
            RB_EVIDENCE_02,
            f"الادّعاء «{claim.label_ar}» معروضٌ حقيقةً بلا دليل — حالته "
            "`evidence_gap`، ولا يُكتب `supported`.",
            f"Claim '{claim.label_ar}' is presented as fact with no evidence; its state is "
            "`evidence_gap` and it is never written `supported`.",
            entity_ids=(claim.id,),
            excerpt=(getattr(claim, "text_ar", "") or claim.label_ar)[:200],
        ))

    return violated(*violations) if violations else passed()


# ── 10. اقتراح النموذج ليس حقيقة ──────────────────────────────────────────

RB_PROVENANCE_02 = "RB-PROVENANCE-02"


def _model_output_is_never_verified_knowledge(a: Assessment) -> RuleOutcome:
    """مخرَج النموذج لا يكون معرفةً موثقة بذاته.

    وهذه ليست سياسةً تُراجَع: قيد `ck_provenance_model_output_not_verified`
    يمنعها في القاعدة نفسها منذ ترحيل 0002. والقاعدة هنا تكشف الحالة **قبل**
    أن تصل إلى الجدول، فيُقال للباحث ما الخلل بدل أن يصله رفضُ قاعدة بيانات.
    """
    evidence = a.graph.of_kind(EntityKind.EVIDENCE)
    model_evidence = [e for e in evidence if getattr(e, "source_type") == "model_output"]
    if not model_evidence:
        return not_applicable()

    violations: list[RuleFinding] = []
    for item in model_evidence:
        if getattr(item, "verification_status") == "verified":
            violations.append(RuleFinding(
                RB_PROVENANCE_02,
                f"الدليل «{item.label_ar}» مخرَجُ نموذج وموسومٌ `verified` — "
                "والنموذج لا يوثّق نفسه.",
                f"Evidence '{item.label_ar}' is a model output marked `verified`; a model "
                "does not verify itself.",
                entity_ids=(item.id,)))

    model_ids = {e.id for e in model_evidence}
    for claim in a.graph.of_kind(EntityKind.CLAIM):
        if getattr(claim, "origin") != "fact":
            continue
        supporting = set(a.graph.targets(RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE, claim.id))
        if supporting and supporting <= model_ids:
            violations.append(RuleFinding(
                RB_PROVENANCE_02,
                f"الادّعاء «{claim.label_ar}» لا يسنده إلا مخرَج نموذج — "
                "واقتراح النموذج توصيةٌ تُراجَع لا واقعةٌ تُنقل.",
                f"Claim '{claim.label_ar}' rests on model output alone; a model's suggestion "
                "is a recommendation to review, not a fact to repeat.",
                entity_ids=(claim.id,)))

    return violated(*violations) if violations else passed()


# ── السجل ─────────────────────────────────────────────────────────────────

RULES: Final[tuple[ScientificRule, ...]] = (
    ScientificRule(
        id=RB_CAUSALITY_01,
        category=RuleCategory.CAUSALITY,
        severity="blocking",
        condition_ar="يظهر تركيبٌ سببي في نصّ بحثٍ تصميمه ليس تجريبيًّا ولا شبه تجريبي.",
        condition_en="Causal wording appears in a study whose design is neither "
                     "experimental nor quasi-experimental.",
        message_ar="التصميم الوصفي أو المقطعي يصف اقترانًا ولا يثبت سببًا؛ "
                   "واللغة السببية فيه تعد بما لم يُقَس.",
        message_en="A descriptive or cross-sectional design shows association, not cause; "
                   "causal wording promises what was never measured.",
        provenance="§15.2 (الكشف اللغوي التاسع) و`services/golden_thread/language.py`؛ "
                   "و`CAUSAL_DESIGNS` في `vocab.py` هي معيار المشروعية.",
        predicate=_causal_language_requires_causal_design,
        related_issue_keys=("causal_language_in_correlational_study",
                            "causal_language_beyond_design"),
    ),
    ScientificRule(
        id=RB_FABRICATION_01,
        category=RuleCategory.FABRICATION,
        severity="blocking",
        condition_ar="نتيجةٌ تحمل قيمة دلالة لا تعود إلى تشغيلة تحليل تُشتقّ منها.",
        condition_en="A finding carries a p-value that does not trace to an analysis "
                     "it derives from.",
        message_ar="قيمة p تُنتَج في التحليل وتُسجَّل مخرَجًا؛ ولا تُشتقّ في الكتابة "
                   "ولا تُقدَّر من إحصاءٍ آخر.",
        message_en="A p-value is produced by analysis and recorded as an output; it is never "
                   "derived while writing nor estimated from another statistic.",
        provenance="§19.2 القاعدة 2، وقيد `ClaimAnalysisLink`، والعطب المسجَّل في "
                   "`services/publishing/drafting/context.py` (t وdf بلا p).",
        predicate=_p_value_must_come_from_an_analysis_run,
        related_issue_keys=("statistic_without_analysis_output",
                            "significance_without_analysis_output"),
    ),
    ScientificRule(
        id=RB_FABRICATION_02,
        category=RuleCategory.FABRICATION,
        severity="blocking",
        condition_ar="رقمُ عيّنة يظهر بلا حجم عيّنة مسجَّل يسنده.",
        condition_en="A sample number appears with no recorded sample size behind it.",
        message_ar="حجم العيّنة غير المسجَّل يُكتب «غير مسجَّل»؛ والرقم المخترَع "
                   "يبني منهجيةً كاملة على ما لم يُعدّ.",
        message_en="An unrecorded sample size is written as MISSING; an invented number "
                   "builds a whole methodology on something never counted.",
        provenance="`unsupported_sample_number` في `drafting/checks.py`، و«ما لا ترد به "
                   "الأدلة يبقى None ولا يُخمَّن» في `services/planning/thread.py`.",
        predicate=_sample_size_must_never_be_invented,
        related_issue_keys=("unsupported_sample_number", "sample_size_mismatch"),
    ),
    ScientificRule(
        id=RB_DESIGN_01,
        category=RuleCategory.DESIGN_FIT,
        severity="blocking",
        condition_ar="فروضٌ مسجَّلة في بحثٍ لا يستلزم تصميمُه فروضًا وفق §16.",
        condition_en="Hypotheses are recorded in a study whose design does not require "
                     "them under §16.",
        message_ar="الدراسة الكيفية تستكشف ولا تختبر؛ وإلزامها بفروض يقلب سؤالها "
                   "إلى اختبارٍ لم تُصمَّم له.",
        message_en="A qualitative study explores rather than tests; forcing hypotheses on it "
                   "turns its question into a test it was never designed for.",
        provenance="§16.2 مقابل §16.1 — `REQUIREMENTS` في "
                   "`services/golden_thread/methodology.py` هي مصدر الحكم.",
        predicate=_qualitative_study_must_not_carry_hypotheses,
        related_issue_keys=("hypothesis_without_measurable_variables",),
    ),
    ScientificRule(
        id=RB_DESIGN_02,
        category=RuleCategory.DESIGN_FIT,
        severity="blocking",
        condition_ar="اختبارٌ إحصائي لا تطابقه مقاييسُ متغيراته أو تصميمُه أو افتراضاته.",
        condition_en="A statistical test does not match its variable scales, its design, "
                     "or its assumptions.",
        message_ar="الاختبار غير المطابق يُخرج رقمًا صحيح الحساب فاسد المعنى — "
                   "وهو أخطر من غياب الرقم لأنه يبدو نتيجة.",
        message_en="A mismatched test yields a number that computes correctly and means "
                   "nothing — worse than no number, because it looks like a result.",
        provenance="`TEST_KINDS` في `services/analysis/vocab.py`، ومقاييس "
                   "`variables.scale_type`، و§16.1 (خطة التحليل).",
        predicate=_statistical_test_must_match_design,
        related_issue_keys=(),
    ),
    ScientificRule(
        id=RB_LINEAGE_01,
        category=RuleCategory.LINEAGE,
        severity="blocking",
        condition_ar="تشغيلةُ تحليل جرت على تجميدٍ يخالف تجميد مجموعة البيانات الحالي.",
        condition_en="An analysis ran on a freeze that differs from the dataset's current one.",
        message_ar="استبدال البيانات يُبطل ما بُني عليها: التشغيلة والنتيجة والتوصية "
                   "تصير وصفًا لبياناتٍ لم تعد هي.",
        message_en="Replacing a dataset invalidates what was built on it: the run, the finding "
                   "and the recommendation now describe data that no longer exists.",
        provenance="§17.3 (التجميد)، و`analysis_runs.dataset_freeze_id`، وتنبيه "
                   "`data_not_frozen` في `services/inbox.py`.",
        predicate=_dataset_change_invalidates_dependent_work,
        related_issue_keys=("data_not_frozen", "result_without_analysis_run"),
    ),
    ScientificRule(
        id=RB_EVIDENCE_01,
        category=RuleCategory.EVIDENCE,
        severity="blocking",
        condition_ar="مصدرٌ حالته `saved_only` أو `excluded` يُستعمل سندًا لادّعاء.",
        condition_en="A source in `saved_only` or `excluded` is used to support a claim.",
        message_ar="المحفوظ ليس مُدرَجًا: الإدراج قرارُ الباحث المنسوب إليه، "
                   "وحسابُ المحفوظ دليلًا يفترض قرارًا لم يُتّخذ.",
        message_en="Saved is not included: inclusion is the researcher's attributed decision, "
                   "and counting a saved source as evidence assumes a decision never made.",
        provenance="ترحيل 0020 — `SOURCE_USE_STATES` وقيد "
                   "`ck_project_source_decision_actor`، وافتراضيّة `saved_only`.",
        predicate=_saved_only_source_cannot_support_a_claim,
        related_issue_keys=("claim_without_evidence",),
    ),
    ScientificRule(
        id=RB_PROVENANCE_01,
        category=RuleCategory.PROVENANCE,
        severity="blocking",
        condition_ar="حقلٌ معلَنٌ `known` وسندُه مرشّحٌ لم يعتمده الباحث.",
        condition_en="A field is declared `known` while its backing candidate was never "
                     "approved by the researcher.",
        message_ar="المرشّح المستخرَج ليس معرفة؛ والطريق الوحيد بينهما اعتمادُ "
                   "الباحث، و«لا أعرف» ليست اعتمادًا كما أن «لم يُراجَع» ليست رفضًا.",
        message_en="An extracted candidate is not knowledge; the only path between them is the "
                   "researcher's approval — and 'unknown' is not approval any more than "
                   "'unverified' is rejection.",
        provenance="§7.4 و`services/memory.py`، وترحيل 0016 (حالة «لا أعرف»)، "
                   "وحالات `known|needs_review|missing` في `services/workspace.py`.",
        predicate=_unapproved_candidate_cannot_become_known,
        related_issue_keys=(),
    ),
    ScientificRule(
        id=RB_EVIDENCE_02,
        category=RuleCategory.EVIDENCE,
        severity="blocking",
        condition_ar="ادّعاءٌ أصلُه `fact` ولا دليل ولا مصدرٌ مُدرَج يسنده.",
        condition_en="A claim whose origin is `fact` has neither evidence nor an included "
                     "source behind it.",
        message_ar="الادّعاء بلا دليل يبقى بلا دليل: يُسمّى `evidence_gap` ولا يُحذف "
                   "ولا يُعاد صوغه ولا يُكتب `supported`.",
        message_en="A claim with no evidence stays unsupported: it is named `evidence_gap`, "
                   "never deleted, never reworded, never written `supported`.",
        provenance="§19.2 القاعدة 1، و`claim_without_evidence` في "
                   "`services/publishing/manuscript.py`، وحالة `evidence_gap` في ترحيل 0008.",
        predicate=_factual_claim_without_evidence_stays_unsupported,
        related_issue_keys=("claim_without_evidence",
                            "factual_claim_without_verified_evidence"),
    ),
    ScientificRule(
        id=RB_PROVENANCE_02,
        category=RuleCategory.PROVENANCE,
        severity="blocking",
        condition_ar="مخرَجُ نموذج موسومٌ `verified`، أو ادّعاءُ حقيقةٍ لا يسنده غيره.",
        condition_en="A model output is marked `verified`, or a factual claim rests on "
                     "model output alone.",
        message_ar="توصية النموذج ليست واقعةً متحقَّقة: تُعرض اقتراحًا يراجعه الباحث، "
                   "ولا تُنقل إلى المخطوطة بوصفها معلومة.",
        message_en="A model's recommendation is not a verified fact: it is offered as a "
                   "suggestion for the researcher to review, not carried into the manuscript "
                   "as knowledge.",
        provenance="قيد `ck_provenance_model_output_not_verified` (ترحيل 0002)، "
                   "و§7.4، وحاجز `no_self_verification`.",
        predicate=_model_output_is_never_verified_knowledge,
        related_issue_keys=("unsupported_claim",),
    ),
)

BY_ID: Final[dict[str, ScientificRule]] = {rule.id: rule for rule in RULES}

# حارسٌ عند الاستيراد: مفتاحٌ في `TEST_FITNESS` خارج `TEST_KINDS` قاعدةٌ لا
# تُطلق أبدًا — والصمت هنا أسوأ من الانفجار. والنمط نفسه في
# `SectionPolicy.__post_init__` و`_assert_roles_exist`.
_unknown_tests = tuple(key for key in TEST_FITNESS if key not in TEST_KINDS)
if _unknown_tests:  # pragma: no cover - يقع عند الاستيراد أو لا يقع
    raise RuntimeError(f"TEST_FITNESS names tests that are not in TEST_KINDS: {_unknown_tests}")
