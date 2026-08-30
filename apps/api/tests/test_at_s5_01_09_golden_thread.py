"""AT-S5-01…09 — اختبارات الاتساق التسعة والدرجة (§15).

كلها تعمل بلا قاعدة بيانات: الفحوص منطق علمي خالص على بنية الخيط.
"""
import pytest

from athera_api.services.golden_thread import checks, score
from athera_api.services.golden_thread.graph import (
    Element,
    InstrumentSpec,
    Link,
    MethodSpec,
    ThreadGraph,
    VariableSpec,
)

SPEC_CHECKS = {
    "objective_without_question",
    "question_without_analysis",
    "hypothesis_without_measurable_variables",
    "title_variable_missing_from_instrument",
    "result_without_question",
    "recommendation_without_result",
    "theory_unused_in_discussion",
    "generalization_beyond_sample",
    "causal_language_in_correlational_study",
}


def keys(findings) -> set[str]:
    return {f.check_key for f in findings}


def test_all_nine_checks_from_spec_exist():
    """AT-S5-01 — §15.2 كاملة، بلا نقصان ولا اختراع كشف عاشر."""
    assert set(checks.CHECKS) == SPEC_CHECKS
    assert len(checks.CHECKS) == 9


def test_structural_findings_block_and_linguistic_ones_advise():
    """§15.2 مع القرار المسجَّل: اللغوي اقتراح مراجعة لا حجب."""
    graph = ThreadGraph(
        elements=[Element("o1", "objective", "هدف")],
        results_text="الثقة تؤدي إلى الشراء لدى جميع المستهلكين.",
        method=MethodSpec(study_type="quantitative", design_family="correlational",
                          sampling_strategy="convenience"),
    )
    findings = checks.run_all(graph)
    assert all(f.is_blocking for f in findings if f.kind == checks.STRUCTURAL)
    assert all(not f.is_blocking for f in findings if f.kind == checks.LINGUISTIC)


def test_every_finding_is_bilingual():
    graph = ThreadGraph(
        elements=[Element("o1", "objective", "هدف"), Element("q1", "question", "سؤال"),
                  Element("h1", "hypothesis", "فرض"), Element("r1", "result", "نتيجة"),
                  Element("rec1", "recommendation", "توصية"), Element("t1", "theory", "نظرية")],
        variables=[VariableSpec("v1", "متغير", "independent", True, True)],
        instruments=[InstrumentSpec("i1", "أداة", ())],
        results_text="الثقة تؤدي إلى الشراء لدى جميع المستهلكين.",
        method=MethodSpec(study_type="quantitative", design_family="correlational",
                          sampling_strategy="convenience"),
    )
    findings = checks.run_all(graph)
    assert keys(findings) == SPEC_CHECKS, "a badly formed thread must trigger all nine checks"
    for finding in findings:
        assert finding.detail_ar.strip() and finding.detail_en.strip()
        assert any("؀" <= ch <= "ۿ" for ch in finding.detail_ar)


def test_structural_gaps_are_detected():
    """AT-S5-02 — هدف بلا سؤال · سؤال بلا تحليل · فرض بلا متغيرات."""
    graph = ThreadGraph(
        elements=[Element("q1", "question", "س"), Element("o1", "objective", "هـ"),
                  Element("h1", "hypothesis", "ف")],
        method=MethodSpec(study_type="quantitative"),
    )
    found = keys(checks.run_all(graph))
    assert "objective_without_question" in found
    assert "question_without_analysis" in found
    assert "hypothesis_without_measurable_variables" in found


def test_links_resolve_the_structural_gaps():
    graph = ThreadGraph(
        elements=[Element("q1", "question", "س"), Element("o1", "objective", "هـ"),
                  Element("a1", "analysis", "انحدار"), Element("h1", "hypothesis", "ف")],
        links=[Link("q1", "o1", "maps_to"), Link("q1", "a1", "analyzes"),
               Link("h1", "v1", "measures")],
        variables=[VariableSpec("v1", "الثقة", "independent", True, False)],
        method=MethodSpec(study_type="quantitative"),
    )
    found = keys(checks.run_all(graph))
    assert not ({"objective_without_question", "question_without_analysis",
                 "hypothesis_without_measurable_variables"} & found)


def test_title_variable_must_be_measured():
    """AT-S5-03 — متغير في العنوان لا تقيسه أداة."""
    unmeasured = ThreadGraph(
        variables=[VariableSpec("v1", "الولاء", "dependent", True, True)],
        instruments=[InstrumentSpec("i1", "استبانة", ())],
        method=MethodSpec(study_type="quantitative"),
    )
    assert "title_variable_missing_from_instrument" in keys(checks.run_all(unmeasured))

    measured = ThreadGraph(
        variables=[VariableSpec("v1", "الولاء", "dependent", True, True)],
        instruments=[InstrumentSpec("i1", "استبانة", ("v1",))],
        method=MethodSpec(study_type="quantitative"),
    )
    assert "title_variable_missing_from_instrument" not in keys(checks.run_all(measured))


def test_results_and_recommendations_need_grounding():
    """AT-S5-04."""
    ungrounded = ThreadGraph(
        elements=[Element("r1", "result", "ن"), Element("rec1", "recommendation", "ت")],
        method=MethodSpec(study_type="quantitative"),
    )
    found = keys(checks.run_all(ungrounded))
    assert "result_without_question" in found
    assert "recommendation_without_result" in found

    grounded = ThreadGraph(
        elements=[Element("q1", "question", "س"), Element("r1", "result", "ن"),
                  Element("rec1", "recommendation", "ت")],
        links=[Link("r1", "q1", "answers"), Link("r1", "rec1", "supports")],
        method=MethodSpec(study_type="quantitative"),
    )
    assert not ({"result_without_question", "recommendation_without_result"}
                & keys(checks.run_all(grounded)))


def test_adopted_theory_must_appear_in_the_discussion():
    """AT-S5-05 — نظرية زينة ليست نظرية."""
    unused = ThreadGraph(
        elements=[Element("t1", "theory", "نظرية السلوك المخطط")],
        discussion_text="ناقشت الدراسة النتائج في ضوء الأدبيات السابقة.",
        method=MethodSpec(study_type="quantitative"),
    )
    assert "theory_unused_in_discussion" in keys(checks.run_all(unused))

    used = ThreadGraph(
        elements=[Element("t1", "theory", "نظرية السلوك المخطط")],
        discussion_text="تتسق النتائج مع نظرية السلوك المخطط في تفسير النية.",
        method=MethodSpec(study_type="quantitative"),
    )
    assert "theory_unused_in_discussion" not in keys(checks.run_all(used))


CAUSAL_SENTENCE = "أظهرت النتائج أن الثقة تؤدي إلى زيادة نية الشراء لدى المستهلكين."


def test_causal_language_flagged_only_in_non_experimental_designs():
    """AT-S5-06 — السببية مشروعة في التجريبي؛ الكشف عنها هناك خطأ لا اكتشاف."""
    correlational = ThreadGraph(
        results_text=CAUSAL_SENTENCE,
        method=MethodSpec(study_type="quantitative", design_family="correlational"),
    )
    assert "causal_language_in_correlational_study" in keys(checks.run_all(correlational))

    for design in ("experimental", "quasi_experimental"):
        graph = ThreadGraph(
            results_text=CAUSAL_SENTENCE,
            method=MethodSpec(study_type="quantitative", design_family=design),
        )
        assert "causal_language_in_correlational_study" not in keys(checks.run_all(graph))


@pytest.mark.parametrize(
    "sentence",
    [
        "الارتباط الملاحظ لا يعني السببية بين المتغيرين.",
        "لا تدّعي الدراسة وجود علاقة سببية بين الثقة والنية.",
        "قد يشير الارتباط إلى علاقة تستحق اختبارًا تجريبيًا لاحقًا.",
        "Correlation does not imply causation in this design.",
        "A causal effect cannot be inferred from these data.",
    ],
)
def test_hedged_language_is_not_punished(sentence):
    """AT-S5-07 — حاجز يعاقب الصدق أسوأ من حاجز يفوّت خطأ."""
    graph = ThreadGraph(
        results_text=sentence,
        method=MethodSpec(study_type="quantitative", design_family="correlational"),
    )
    assert "causal_language_in_correlational_study" not in keys(checks.run_all(graph))


def test_generalisation_is_judged_against_the_sampling_strategy():
    """AT-S5-08 — «جميع المستهلكين» مشروعة مع عينة احتمالية."""
    claim = "تنطبق النتائج على جميع المستهلكين في المجتمع السعودي."

    convenience = ThreadGraph(
        discussion_text=claim,
        method=MethodSpec(study_type="quantitative", sampling_strategy="convenience"),
    )
    assert "generalization_beyond_sample" in keys(checks.run_all(convenience))

    probability = ThreadGraph(
        discussion_text=claim,
        method=MethodSpec(study_type="quantitative", sampling_strategy="stratified_random"),
    )
    assert "generalization_beyond_sample" not in keys(checks.run_all(probability))


@pytest.mark.parametrize(
    "sentence",
    [
        "لا يمكن تعميم النتائج خارج حدود العينة.",
        "تقتصر النتائج على العينة المدروسة فقط.",
        "These findings cannot be generalized beyond the sample.",
    ],
)
def test_explicit_limitation_statements_pass(sentence):
    graph = ThreadGraph(
        discussion_text=sentence,
        method=MethodSpec(study_type="quantitative", sampling_strategy="convenience"),
    )
    assert "generalization_beyond_sample" not in keys(checks.run_all(graph))


# ── AT-S5-09: الدرجة لا تنفصل عن أسبابها (§15.3) ──

def test_score_always_carries_its_findings():
    result = score.compute(ThreadGraph(method=MethodSpec(study_type="quantitative")))
    assert hasattr(result, "findings") and hasattr(result, "missing_elements")
    assert result.is_final_verdict is False
    assert result.note_ar.strip() and result.note_en.strip()


def test_perfect_score_with_a_blocking_finding_is_unrepresentable():
    """§15.3 — حارس بنيوي ضد أي حساب مستقبلي يمنح الكمال مع عيب حاجب."""
    with pytest.raises(ValueError):
        score.GoldenThreadScore(score=100, findings=[], missing_elements=[],
                                blocking_count=1, advisory_count=0)


def test_gate_opens_on_absence_of_blockers_not_on_a_number():
    empty = score.compute(ThreadGraph(method=MethodSpec(study_type="quantitative")))
    assert not empty.can_pass_gate
    assert len(empty.missing_elements) >= 8

    complete = score.compute(ThreadGraph(
        elements=[Element("p1", "problem", "م"), Element("g1", "gap", "ف"),
                  Element("q1", "question", "س"), Element("o1", "objective", "هـ"),
                  Element("t1", "theory", "نظرية السلوك المخطط"),
                  Element("a1", "analysis", "انحدار")],
        links=[Link("q1", "o1", "maps_to"), Link("q1", "a1", "analyzes")],
        variables=[VariableSpec("v1", "الثقة", "independent", True, True)],
        instruments=[InstrumentSpec("i1", "استبانة", ("v1",))],
        method=MethodSpec(study_type="quantitative", design_family="correlational",
                          sampling_strategy="stratified_random"),
        discussion_text="نوقشت النتائج وفق نظرية السلوك المخطط.",
        results_text="ظهر ارتباط موجب دال.",
    ))
    assert complete.can_pass_gate
    assert complete.blocking_count == 0
