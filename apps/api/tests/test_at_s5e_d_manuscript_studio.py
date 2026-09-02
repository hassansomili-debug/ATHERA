"""S5E-D — مصنع المخطوطات: السجلّ والاتساق عبر الأقسام.

**السؤال هنا مختلف عمّا سبق.** S5E-B وS5E-C يسألان: هل هذا القسم مسنَد؟
وهذا يسأل: هل هذه **الورقة** متسقة؟

وقسمٌ سليمٌ وحده قد يناقض قسمًا سليمًا وحده: عيّنةٌ عددها في المنهجية غيرها
في النتائج، أو خاتمةٌ تقرّر ما لم يرد، أو ملخّصٌ يأتي برقمٍ لا أصل له. وكلٌّ
منهما مرّ فحصه الخاص — ولا يراهما إلا فحصٌ من فوق.
"""
from __future__ import annotations

import pytest

from athera_api.services.publishing import consistency
from athera_api.services.publishing.drafting import policy

S = consistency.SectionText


def _keys(issues):
    return {i.issue_key for i in issues}


# ══════════ 1. السجلّ مصدر الحقيقة الوحيد ══════════

def test_every_policy_key_is_canonical():
    from athera_api.services.publishing.vocab import MANUSCRIPT_SECTIONS

    assert set(policy.POLICIES) <= set(MANUSCRIPT_SECTIONS)


def test_a_policy_cannot_be_written_with_an_unknown_key():
    """الصنف يُغلق عند الاستيراد لا عند الاستعمال."""
    with pytest.raises(ValueError, match="MANUSCRIPT_SECTIONS"):
        policy.SectionPolicy(key="methods")


def test_a_policy_cannot_redact_statistics_it_forbids():
    """حجبُ ما لا يجوز أصلًا تناقضٌ صامت — يُرفض عند التعريف."""
    with pytest.raises(ValueError, match="meaningless"):
        policy.SectionPolicy(key="title", statistics="forbidden", redact_statistics=True)


@pytest.mark.parametrize("module_attr", [
    ("athera_api.services.publishing.drafting.context", "REDACT_STATISTICS_IN"),
    ("athera_api.services.publishing.drafting.context", "ROLES_BY_SECTION"),
    ("athera_api.services.publishing.drafting.context", "THREAD_TYPES_BY_SECTION"),
    ("athera_api.services.publishing.drafting.context", "REQUIRED_ANY_BY_SECTION"),
])
def test_no_module_restates_the_section_rules(module_attr):
    """كل خريطة قسمٍ في الشيفرة **مشتقّة** من السجلّ لا مكتوبة بجانبه."""
    import importlib

    name, attr = module_attr
    module = importlib.import_module(name)
    value = getattr(module, attr)
    for key in value:
        assert key in policy.POLICIES, f"{attr} يذكر قسمًا بلا سياسة: {key}"


def test_the_checker_reads_descriptive_sections_from_the_registry():
    from athera_api.services.publishing.drafting import checks

    assert checks._DESCRIPTIVE_SECTIONS == frozenset(
        k for k, p in policy.POLICIES.items() if p.descriptive_only)


def test_pending_literature_sections_are_disabled_not_faked():
    """§3 — قسمٌ يحتاج بحثًا مغلقًا يبقى معلّقًا معلَنًا، لا نثرًا بلا مصادر."""
    for key in ("literature_review", "references"):
        spec = policy.POLICIES[key]
        assert spec.enabled is False
        assert spec.literature == "blocked"
        assert spec.purpose_note_ar, "معطَّلٌ بلا سبب مكتوب"


def test_the_scientific_policies_of_method_and_results_did_not_regress():
    """§8، §9 — تعميم المعمارية لا يُرخي ما أُثبت."""
    results = policy.POLICIES["results"]
    assert results.statistics == "grounded"
    assert results.redact_statistics is True
    assert results.descriptive_only is True
    assert results.allow_inference is False and results.allow_proposal is False

    method = policy.POLICIES["method"]
    assert method.statistics == "forbidden"
    assert method.required_any == ("methodology", "sample")


def test_interpretive_sections_declare_their_freedom_explicitly():
    """§10، §12، §13 — الاستنتاج مأذونٌ حيث يُعلَن، لا حيث يُسكت عنه."""
    assert policy.POLICIES["discussion"].allow_inference is True
    assert policy.POLICIES["limitations"].allow_inference is True
    assert policy.POLICIES["implications"].allow_proposal is True
    # والنتائج والمنهجية لا تأذنان بشيء من ذلك.
    assert policy.POLICIES["results"].allow_proposal is False
    assert policy.POLICIES["conclusion"].allow_proposal is False


def test_no_section_allows_citations_before_the_literature_stage():
    """§25 — لا مرجع يُبنى من ذاكرة نموذج، في أي قسم."""
    assert all(not p.allow_citations for p in policy.POLICIES.values())


# ══════════ 2. الاتساق عبر الأقسام ══════════

def test_a_sample_size_that_differs_between_sections_is_caught():
    issues = consistency.evaluate([
        S("method", "بلغت عينة الدراسة 120 طالبًا"),
        S("results", "شارك 240 طالبًا في الاختبار البعدي"),
    ])
    assert "sample_size_mismatch" in _keys(issues)


def test_the_same_sample_size_across_sections_passes():
    """الحارس الذي يعاقب الاتساق أسوأ من الذي يفوّت تناقضًا."""
    issues = consistency.evaluate([
        S("method", "بلغت عينة الدراسة 120 طالبًا"),
        S("results", "من أصل 120 طالبًا شاركوا في الدراسة"),
    ])
    assert "sample_size_mismatch" not in _keys(issues)


def test_a_design_that_differs_between_sections_is_caught():
    issues = consistency.evaluate([
        S("method", "استخدمت الدراسة المنهج شبه التجريبي"),
        S("discussion", "وبما أن الدراسة اتّبعت المنهج الارتباطي"),
    ])
    assert "design_mismatch" in _keys(issues)


def test_an_abstract_statistic_absent_from_the_paper_is_caught():
    """§5 — الملخّص يعيد ما سُنِد، ولا يأتي بجديد من أضعف باب."""
    issues = consistency.evaluate([
        S("results", "بلغت قيمة t(118) = 3.738"),
        S("abstract", "وبلغ مربع إيتا 0.42"),
    ])
    assert "abstract_introduces_new_statistic" in _keys(issues)


def test_an_abstract_reusing_a_grounded_result_passes():
    issues = consistency.evaluate([
        S("results", "بلغت قيمة t(118) = 3.738 ومربع إيتا 0.106"),
        S("abstract", "أظهرت النتائج فرقًا بلغ مربع إيتا 0.106"),
    ])
    assert "abstract_introduces_new_statistic" not in _keys(issues)


def test_a_conclusion_stating_an_absent_result_is_caught():
    """§11 — الخاتمة تُغلق ما فُتح، ولا تفتح رقمًا جديدًا."""
    issues = consistency.evaluate([
        S("results", "بلغت قيمة t(118) = 3.738"),
        S("conclusion", "وخلصت الدراسة إلى أن مربع إيتا 0.55"),
    ])
    assert "conclusion_states_absent_result" in _keys(issues)


def test_causal_language_in_a_section_that_forbids_it_is_caught():
    issues = consistency.evaluate([
        S("method", "استخدمت الدراسة المنهج الارتباطي"),
        S("conclusion", "يؤدي التعلّم النشط إلى تحسّن التفكير الناقد"),
    ])
    assert "causal_language_beyond_design" in _keys(issues)


def test_an_internal_marker_anywhere_in_the_manuscript_is_caught():
    issues = consistency.evaluate([S("results", "أظهرت النتائج فروقًا [غير متاح]")])
    assert "internal_redaction_marker" in _keys(issues)


def test_an_approved_section_with_no_text_is_caught():
    issues = consistency.evaluate([S("method", "   ", review_status="approved")])
    assert "approved_section_is_empty" in _keys(issues)


def test_a_coherent_manuscript_raises_nothing():
    """ورقةٌ متسقة تمرّ صامتة — وإلا صار المدقّق ضجيجًا يُتجاهَل."""
    issues = consistency.evaluate([
        S("method", "استخدمت الدراسة المنهج شبه التجريبي وبلغت العينة 120 طالبًا",
          "approved"),
        S("results", "من أصل 120 طالبًا بلغت قيمة t(118) = 3.738", "approved"),
        S("abstract", "أظهرت النتائج فرقًا بلغت قيمته t(118) = 3.738"),
    ])
    assert _keys(issues) == set(), [i.issue_key for i in issues]


# ══════════ 3. الجاهزية تشمل الورقة كوحدة ══════════

def test_readiness_includes_cross_section_findings():
    """§26 — بوابة G9 لا تكتفي بسلامة الأقسام فرادى."""
    import inspect

    from athera_api.routers import publishing

    source = inspect.getsource(publishing._readiness)
    assert "consistency.evaluate" in source
    # والإسناد البنيوي هو المرجع لا `claim_ids` الموروثة.
    assert "ManuscriptSectionClaim" in source


def test_readiness_reads_supported_claims_from_the_relational_links():
    import inspect

    from athera_api.routers import publishing

    source = inspect.getsource(publishing._readiness)
    assert 'status == "supported"' in source
