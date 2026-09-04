"""AT-RB-04 — منصّة تقييم علمي: حالاتٌ ممثِّلة وحكمٌ متوقَّع لكل قاعدة.

**ليست اختبار وحدات.** كل حالةٍ هنا موقفٌ بحثيّ يقع فعلًا — مسحٌ مقطعي
يكتب سببية، مقابلاتٌ كيفية تُحمَّل فروضًا، مصدرٌ محفوظ يُحسب دليلًا، بياناتٌ
استُبدلت وبقيت نتائجها — والحكم المتوقَّع مكتوبٌ بجانبها. فإن تغيّر سلوك
قاعدةٍ لاحقًا ظهر التغيّر موقفًا مسمّى لا سطرًا في تتبّع.

**والحالات السالبة نصفُ المنصّة.** حارسٌ يُطلق على كل شيء لا يقلّ ضررًا عن
حارسٍ لا يُطلق: الأول يعلّم الباحث تجاهُله، والثاني لا يراه أصلًا. فلكل
قاعدةٍ هنا حالةٌ تخالفها، وحالةٌ لا تخالفها، وحالةٌ لا تنطبق عليها.
"""
from dataclasses import dataclass

import pytest

from athera_api.research_brain import ontology as o
from athera_api.research_brain import rules
from athera_api.research_brain.catalogue import RULES
from athera_api.research_brain.rules import Assessment, BrainFieldView, CandidateView, Verdict
from athera_api.research_brain.values import known

R = o.RelationKind
NA = Verdict.NOT_APPLICABLE
PASS = Verdict.PASS
VIOLATION = Verdict.VIOLATION
UNSURE = Verdict.INSUFFICIENT_INFORMATION


@dataclass(frozen=True, slots=True)
class EvalCase:
    """موقفٌ واحد وحكمه المتوقَّع.

    `expect` يذكر القواعد المعنيّة وحدها؛ وما لم يُذكر لا يُفحص هنا — كل
    قاعدة لها حالاتها. و`detail_contains` تفحص أن الرسالة تقول الشيء الصحيح
    لا أن حكمًا ما صدر: «مخالفة» بلا سببٍ صحيح تمرّ اختبارًا ولا تنفع باحثًا.
    """

    id: str
    description_ar: str
    assessment: Assessment
    expect: dict[str, Verdict]
    detail_contains: tuple[str, ...] = ()
    min_findings: int = 0


def _link(kind, source_id, target_id):
    return o.Relationship(kind=kind, source_id=source_id, target_id=target_id)


def _survey_design(**kw):
    defaults = dict(id="design", label_ar="مسح مقطعي", study_type="quantitative",
                    design_family="correlational", temporal_frame="cross_sectional")
    return o.Design(**{**defaults, **kw})


def _analysis(**kw):
    defaults = dict(id="an1", label_ar="اختبار ت", test_kind="t_test",
                    outcome_scale="interval", predictor_scale="nominal", group_count=2,
                    assumptions={"normality": True, "homogeneity_of_variance": True,
                                 "independence": True})
    return o.Analysis(**{**defaults, **kw})


CAUSAL = "يؤدي التدريب إلى تحسّن الأداء الوظيفي."
HEDGED = "لا تدّعي الدراسة أن التدريب يؤدي إلى تحسّن الأداء الوظيفي."


CASES: tuple[EvalCase, ...] = (
    # ── السببية ──
    EvalCase(
        "causal_overclaim_in_a_cross_sectional_survey",
        "مسحٌ مقطعي ارتباطي يكتب «يؤدي … إلى» — اقترانٌ يُعرض سببًا.",
        Assessment(graph=o.ResearchGraph(entities=[_survey_design()]),
                   sections={"discussion": CAUSAL}),
        {"RB-CAUSALITY-01": VIOLATION},
        detail_contains=("مقطعي",),
        min_findings=1,
    ),
    EvalCase(
        "hedged_wording_in_the_same_survey_is_not_punished",
        "الجملة نفسها منفيّة صراحةً — وهي اللغة العلمية المطلوبة لا مخالفة.",
        Assessment(graph=o.ResearchGraph(entities=[_survey_design()]),
                   sections={"discussion": HEDGED}),
        {"RB-CAUSALITY-01": PASS},
    ),
    EvalCase(
        "causal_wording_in_an_experimental_design_is_legitimate",
        "التصميم التجريبي يسند السببية — والكشف عليه خطأ لا اكتشاف.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(study_type="experimental", design_family="experimental",
                           temporal_frame="longitudinal")]),
            sections={"discussion": CAUSAL}),
        {"RB-CAUSALITY-01": NA},
    ),
    EvalCase(
        "causal_wording_with_no_recorded_design_is_not_judged",
        "لا تصميم مسجَّل: الجملة تُعرض ولا يُحكم عليها — ولا تُبتلع.",
        Assessment(sections={"discussion": CAUSAL}),
        {"RB-CAUSALITY-01": UNSURE},
        min_findings=1,
    ),

    # ── الفروض والتصميم الكيفي ──
    EvalCase(
        "qualitative_interviews_are_not_forced_to_carry_hypotheses",
        "دراسةٌ كيفية بمقابلات، ومعها فرضان — إلزامٌ يقلب الاستكشاف اختبارًا.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(study_type="qualitative", design_family="case_study",
                           temporal_frame="unknown"),
            o.Hypothesis(id="h1", label_ar="الفرض الأول"),
            o.Hypothesis(id="h2", label_ar="الفرض الثاني"),
        ])),
        {"RB-DESIGN-01": VIOLATION},
        detail_contains=("qualitative",),
        min_findings=1,
    ),
    EvalCase(
        "a_qualitative_study_with_no_hypotheses_is_untouched",
        "كيفيةٌ بلا فروض — لا موضع للقاعدة أصلًا.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(study_type="qualitative", design_family="case_study")])),
        {"RB-DESIGN-01": NA},
    ),
    EvalCase(
        "a_quantitative_study_may_carry_hypotheses",
        "الكمّية تستلزم الفروض في §16.1 — فوجودها مطلبٌ لا مخالفة.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(), o.Hypothesis(id="h1", label_ar="الفرض الأول")])),
        {"RB-DESIGN-01": NA},
    ),
    EvalCase(
        "hypotheses_with_an_unrecorded_study_type_are_not_judged",
        "فروضٌ ونوع الدراسة غير مسجَّل — فلا يُعرف أهي مشروعة.",
        Assessment(graph=o.ResearchGraph(entities=[
            o.Hypothesis(id="h1", label_ar="الفرض الأول")])),
        {"RB-DESIGN-01": UNSURE},
        min_findings=1,
    ),

    # ── المصدر المحفوظ ──
    EvalCase(
        "a_saved_only_source_is_denied_evidence_status",
        "مصدرٌ محفوظ للقراءة يُحسب سندًا — قرارُ إدراجٍ لم يتّخذه أحد.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Source(id="s1", label_ar="دراسة سابقة", use_state="saved_only"),
                      o.Claim(id="c1", label_ar="الادّعاء الأول", text_ar="نصّ الادّعاء")],
            relationships=[_link(R.SOURCE_SUPPORTS_CLAIM, "s1", "c1")])),
        {"RB-EVIDENCE-01": VIOLATION, "RB-EVIDENCE-02": VIOLATION},
        detail_contains=("saved_only", "evidence_gap"),
        min_findings=1,
    ),
    EvalCase(
        "an_excluded_source_is_denied_for_a_different_reason",
        "المستبعَد نُظر فيه ورُفض — واستعماله نقضٌ لقرارٍ مسجَّل لا غيابُ قرار.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Source(id="s1", label_ar="دراسة مستبعَدة", use_state="excluded"),
                      o.Claim(id="c1", label_ar="الادّعاء الأول")],
            relationships=[_link(R.SOURCE_SUPPORTS_CLAIM, "s1", "c1")])),
        {"RB-EVIDENCE-01": VIOLATION},
        detail_contains=("excluded",),
    ),
    EvalCase(
        "an_included_source_supports_its_claim",
        "المُدرَج قرارٌ منسوب إلى قائله — فهو سندٌ مشروع.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Source(id="s1", label_ar="دراسة مُدرَجة", use_state="included"),
                      o.Claim(id="c1", label_ar="الادّعاء الأول")],
            relationships=[_link(R.SOURCE_SUPPORTS_CLAIM, "s1", "c1")])),
        {"RB-EVIDENCE-01": PASS, "RB-EVIDENCE-02": PASS},
    ),
    EvalCase(
        "an_interpretation_is_not_asked_for_direct_evidence",
        "التفسير لا يُعرض حقيقةَ مصدر — ومطالبتُه بدليلٍ تعاقب صدق التوسيم.",
        Assessment(graph=o.ResearchGraph(entities=[
            o.Claim(id="c1", label_ar="قراءةٌ محتملة", origin="interpretation")])),
        {"RB-EVIDENCE-02": NA},
    ),

    # ── حجم العيّنة ──
    EvalCase(
        "a_missing_sample_size_is_declared_missing_never_filled",
        "لا حجم عيّنة مسجَّلًا ولا رقمَ في النصّ — يُقال «غير مسجَّلة» ويُكتب هكذا.",
        Assessment(graph=o.ResearchGraph(entities=[o.Sample(id="sm", label_ar="العيّنة")])),
        {"RB-FABRICATION-02": UNSURE},
        detail_contains=("غير مسجَّلة", "MISSING"),
        min_findings=1,
    ),
    EvalCase(
        "a_sample_number_with_nothing_behind_it_is_an_invention",
        "٣٨٤ في النصّ وحجم العيّنة غير مسجَّل — رقمٌ مخترَع لا مستخرَج.",
        Assessment(graph=o.ResearchGraph(entities=[o.Sample(id="sm", label_ar="العيّنة")]),
                   sample_numbers_in_text=(384,)),
        {"RB-FABRICATION-02": VIOLATION},
        detail_contains=("384",),
    ),
    EvalCase(
        "a_recorded_sample_size_passes",
        "حجمٌ مسجَّل ومعه معرّف ما أنتجه.",
        Assessment(graph=o.ResearchGraph(entities=[
            o.Sample(id="sm", label_ar="العيّنة", size=known(384, source_ref="RUN-1"))])),
        {"RB-FABRICATION-02": PASS},
    ),

    # ── قيمة الدلالة ──
    EvalCase(
        "a_p_value_traced_to_its_analysis_passes",
        "القيمة تعود إلى تشغيلةٍ تُشتقّ منها النتيجة.",
        Assessment(graph=o.ResearchGraph(
            entities=[_analysis(),
                      o.Finding(id="f1", label_ar="فرقٌ دال",
                                p_value=known(0.03, source_ref="an1"))],
            relationships=[_link(R.FINDING_DERIVED_FROM_ANALYSIS, "f1", "an1")])),
        {"RB-FABRICATION-01": PASS},
    ),
    EvalCase(
        "a_p_value_attributed_to_a_run_that_does_not_exist",
        "نسبةٌ إلى معرّفٍ لا تشغيلة له — اختلاقُ سند.",
        Assessment(graph=o.ResearchGraph(
            entities=[_analysis(),
                      o.Finding(id="f1", label_ar="فرقٌ دال",
                                p_value=known(0.03, source_ref="an9"))],
            relationships=[_link(R.FINDING_DERIVED_FROM_ANALYSIS, "f1", "an1")])),
        {"RB-FABRICATION-01": VIOLATION},
        detail_contains=("an9",),
    ),
    EvalCase(
        "a_p_value_pointing_at_an_unlinked_analysis",
        "التشغيلة موجودة والنتيجة لا تُشتقّ منها — عطبُ ربطٍ لا اختلاق.",
        Assessment(graph=o.ResearchGraph(
            entities=[_analysis(),
                      o.Finding(id="f1", label_ar="فرقٌ دال",
                                p_value=known(0.03, source_ref="an1"))])),
        {"RB-FABRICATION-01": VIOLATION},
    ),
    EvalCase(
        "a_finding_with_no_p_value_is_out_of_scope",
        "نتيجةٌ بلا قيمة دلالة — لا موضع للقاعدة.",
        Assessment(graph=o.ResearchGraph(entities=[o.Finding(id="f1", label_ar="وصفٌ عام")])),
        {"RB-FABRICATION-01": NA},
    ),

    # ── مطابقة الاختبار ──
    EvalCase(
        "a_t_test_on_a_nominal_outcome_is_a_mismatch",
        "اختبار ت على متغيّر تابع اسمي — رقمٌ يُحسب ولا يعني شيئًا.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(), _analysis(outcome_scale="nominal")])),
        {"RB-DESIGN-02": VIOLATION},
        detail_contains=("nominal",),
    ),
    EvalCase(
        "a_t_test_across_three_groups_is_a_mismatch",
        "اختبار ت لثلاث مجموعات — والاختبار مبنيّ على مقارنة اثنتين.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(), _analysis(group_count=3)])),
        {"RB-DESIGN-02": VIOLATION},
    ),
    EvalCase(
        "a_t_test_with_unchecked_assumptions_is_not_called_appropriate",
        "الافتراضات لم تُفحص — فالاختبار ليس ناجحًا ولا فاشلًا، هو غير مفحوص.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(), _analysis(assumptions={})])),
        {"RB-DESIGN-02": UNSURE},
        detail_contains=("normality",),
        min_findings=1,
    ),
    EvalCase(
        "a_t_test_with_a_failed_assumption_is_a_violation",
        "التجانس فُحص ولم يتحقّق — وهذا حكمٌ لا جهل.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(),
            _analysis(assumptions={"normality": True, "homogeneity_of_variance": False,
                                   "independence": True})])),
        {"RB-DESIGN-02": VIOLATION},
        detail_contains=("homogeneity_of_variance",),
    ),
    EvalCase(
        "a_fully_checked_t_test_passes",
        "المقاييس مطابقة والافتراضات مفحوصة ومتحقّقة.",
        Assessment(graph=o.ResearchGraph(entities=[_survey_design(), _analysis()])),
        {"RB-DESIGN-02": PASS},
    ),
    EvalCase(
        "thematic_coding_on_a_quantitative_design_is_a_mismatch",
        "الترميز الموضوعي لا يُجرى على تصميمٍ كمّي.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(),
            o.Analysis(id="an1", label_ar="ترميز موضوعي", test_kind="thematic_coding")])),
        {"RB-DESIGN-02": VIOLATION},
    ),
    EvalCase(
        "a_test_with_no_recorded_fitness_rule_gets_no_verdict",
        "لا قاعدة ملاءمةٍ مسجَّلة لنمذجة المعادلة البنائية — فلا يُحكم بما لا يُعرف.",
        Assessment(graph=o.ResearchGraph(entities=[
            _survey_design(), o.Analysis(id="an1", label_ar="نمذجة بنائية", test_kind="sem")])),
        {"RB-DESIGN-02": UNSURE},
        detail_contains=("sem",),
    ),

    # ── سلسلة البيانات ──
    EvalCase(
        "replacing_a_dataset_invalidates_analysis_finding_and_recommendation",
        "البيانات استُبدلت: التشغيلة والنتيجة والتوصية كلها تصف ما لم يعد قائمًا.",
        Assessment(graph=o.ResearchGraph(
            entities=[
                o.Dataset(id="ds", label_ar="بيانات الاستبانة", state="analysis_locked",
                          current_freeze_id="FRZ-b2"),
                _analysis(dataset_freeze_id="FRZ-a1"),
                o.Finding(id="f1", label_ar="فرقٌ بين المجموعتين"),
                o.Recommendation(id="rc", label_ar="توسيع البرنامج التدريبي"),
            ],
            relationships=[
                _link(R.ANALYSIS_USES_DATASET, "an1", "ds"),
                _link(R.FINDING_DERIVED_FROM_ANALYSIS, "f1", "an1"),
                _link(R.RECOMMENDATION_DERIVED_FROM_FINDING, "rc", "f1"),
            ])),
        {"RB-LINEAGE-01": VIOLATION},
        detail_contains=("FRZ-a1", "FRZ-b2", "التوصية"),
        min_findings=3,
    ),
    EvalCase(
        "an_analysis_on_the_current_freeze_passes",
        "التجميدان واحد — فالنتيجة تصف البيانات الحالية.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Dataset(id="ds", label_ar="بيانات", current_freeze_id="FRZ-b2"),
                      _analysis(dataset_freeze_id="FRZ-b2")],
            relationships=[_link(R.ANALYSIS_USES_DATASET, "an1", "ds")])),
        {"RB-LINEAGE-01": PASS},
    ),
    EvalCase(
        "an_analysis_on_unfrozen_data_is_neither_stale_nor_current",
        "لا معرّف تجميد — والتشغيلة غير قابلة للإعادة أصلًا.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Dataset(id="ds", label_ar="بيانات"), _analysis()],
            relationships=[_link(R.ANALYSIS_USES_DATASET, "an1", "ds")])),
        {"RB-LINEAGE-01": UNSURE},
        min_findings=1,
    ),

    # ── المرشّح والمعرفة ──
    EvalCase(
        "an_unreviewed_candidate_cannot_make_a_field_known",
        "حقلٌ معلَنٌ معروفًا وسندُه مرشّح لم يُراجَع.",
        Assessment(
            fields=(BrainFieldView(key="question", state="known",
                                   backing_candidate_ids=("cand1",)),),
            candidates=(CandidateView(id="cand1", status="unverified"),)),
        {"RB-PROVENANCE-01": VIOLATION},
        detail_contains=("unverified",),
    ),
    EvalCase(
        "i_do_not_know_is_not_approval",
        "الباحث راجع ولم يستطع الحكم — و«لا أعرف» امتناعٌ لا اعتماد.",
        Assessment(
            fields=(BrainFieldView(key="method", state="known",
                                   backing_candidate_ids=("cand1",)),),
            candidates=(CandidateView(id="cand1", status="unknown"),)),
        {"RB-PROVENANCE-01": VIOLATION},
        detail_contains=("unknown",),
    ),
    EvalCase(
        "a_verified_memory_makes_a_field_known",
        "الذاكرة الموثقة هي ما يمنح `known` — والمسار مرّ باعتماد الباحث.",
        Assessment(fields=(BrainFieldView(key="question", state="known",
                                          backing_memory_ids=("mem1",)),)),
        {"RB-PROVENANCE-01": PASS},
    ),
    EvalCase(
        "a_field_that_admits_it_is_missing_is_not_a_violation",
        "«غير متوفّر» جوابٌ صحيح — والقاعدة تلاحق الادّعاء لا الاعتراف.",
        Assessment(fields=(BrainFieldView(key="results", state="missing"),)),
        {"RB-PROVENANCE-01": NA},
    ),

    # ── مخرَج النموذج ──
    EvalCase(
        "a_model_output_marked_verified_is_a_violation",
        "النموذج لا يوثّق نفسه — والقيد يمنعها في القاعدة منذ ترحيل 0002.",
        Assessment(graph=o.ResearchGraph(entities=[
            o.Evidence(id="e1", label_ar="اقتراح النموذج", source_type="model_output",
                       verification_status="verified")])),
        {"RB-PROVENANCE-02": VIOLATION},
    ),
    EvalCase(
        "a_factual_claim_resting_on_model_output_alone",
        "ادّعاءٌ يُعرض حقيقةً ولا يسنده إلا اقتراح نموذج.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Claim(id="c1", label_ar="الادّعاء الأول"),
                      o.Evidence(id="e1", label_ar="اقتراح النموذج",
                                 source_type="model_output")],
            relationships=[_link(R.CLAIM_SUPPORTED_BY_EVIDENCE, "c1", "e1")])),
        {"RB-PROVENANCE-02": VIOLATION, "RB-EVIDENCE-02": PASS},
    ),
    EvalCase(
        "an_uploaded_document_is_not_a_model_output",
        "دليلٌ من ملفٍ مرفوع — خارج القاعدة تمامًا.",
        Assessment(graph=o.ResearchGraph(
            entities=[o.Claim(id="c1", label_ar="الادّعاء الأول"),
                      o.Evidence(id="e1", label_ar="مقتطف من المستند", source_type="upload",
                                 verification_status="verified")],
            relationships=[_link(R.CLAIM_SUPPORTED_BY_EVIDENCE, "c1", "e1")])),
        {"RB-PROVENANCE-02": NA, "RB-EVIDENCE-02": PASS},
    ),
)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_the_engine_reaches_the_expected_verdict(case: EvalCase):
    report = rules.evaluate(case.assessment, RULES)
    for rule_id, expected in case.expect.items():
        actual = report.verdict_of(rule_id)
        assert actual is expected, (
            f"{case.id}: {rule_id} → {actual.value if actual else None}، "
            f"والمتوقَّع {expected.value} ({case.description_ar})")


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_the_message_says_the_right_thing_not_merely_something(case: EvalCase):
    """حكمٌ صحيح برسالةٍ خاطئة لا ينفع باحثًا — فتُفحص الرسالة."""
    report = rules.evaluate(case.assessment, RULES)
    text = "\n".join(
        f"{f.detail_ar} {f.detail_en} {f.excerpt or ''}"
        for result in report.results for f in result.findings
    )
    for fragment in case.detail_contains:
        assert fragment in text, f"{case.id}: الرسالة لا تذكر «{fragment}»"
    if case.min_findings:
        total = sum(len(result.findings) for result in report.results
                    if result.rule.id in case.expect)
        assert total >= case.min_findings, case.id


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_no_case_blocks_while_every_rule_is_draft(case: EvalCase):
    """المنصّة كلها استشارية اليوم — ولو انقلبت هذه لبدأ المحرّك يوقف باحثين."""
    report = rules.evaluate(case.assessment, RULES)
    assert report.blocking == ()


def test_every_rule_is_exercised_by_at_least_one_violation_and_one_clean_case():
    """قاعدةٌ لم تُختبر في الحالتين لم تُختبر — إطلاقُها وصمتُها كلاهما سلوك."""
    violated_by = {rule_id for case in CASES
                   for rule_id, verdict in case.expect.items() if verdict is VIOLATION}
    cleared_by = {rule_id for case in CASES
                  for rule_id, verdict in case.expect.items()
                  if verdict in (PASS, NA)}
    registered = {rule.id for rule in RULES}
    assert registered - violated_by == set(), f"بلا حالة مخالفة: {registered - violated_by}"
    assert registered - cleared_by == set(), f"بلا حالة سليمة: {registered - cleared_by}"


def test_the_harness_covers_every_verdict():
    """الأحكام الأربعة كلها ممثَّلة — و`insufficient_information` أهمها."""
    seen = {verdict for case in CASES for verdict in case.expect.values()}
    assert seen == set(Verdict)


def test_case_ids_are_unique():
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids))
