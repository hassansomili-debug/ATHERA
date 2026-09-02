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


# ══════════ 4. المدقّق لا يعاقب الدقّة ══════════

def test_a_total_and_a_per_group_count_are_not_a_mismatch():
    """**كشفٌ كاذب وجدته النسخة الإنتاجية.**

    ورقةٌ صحيحة تذكر الكلّ في المنهجية، والكلَّ والمجموعةَ في النتائج:
    «120 طالبًا … 60 لكل مجموعة». واشتراطُ التطابق يجعل المدقّق يعاقب
    الدقّة — وحارسٌ يعاقب الصدق يُعطَّل، ثم لا يحرس شيئًا.
    """
    issues = consistency.evaluate([
        S("method", "بلغت عينة الدراسة 120 طالبًا"),
        S("results", "من أصل 120 طالبًا، بواقع n=60 لكل مجموعة"),
    ])
    assert "sample_size_mismatch" not in _keys(issues), [i.excerpt for i in issues]


def test_two_sections_with_no_number_in_common_still_conflict():
    """والاستثناء لا يتّسع: عددان لا يشتركان في شيء تناقضٌ حقيقي."""
    issues = consistency.evaluate([
        S("method", "بلغت عينة الدراسة 120 طالبًا"),
        S("results", "شارك 240 طالبًا"),
    ])
    assert "sample_size_mismatch" in _keys(issues)


def test_a_third_section_agreeing_with_neither_is_caught():
    issues = consistency.evaluate([
        S("method", "بلغت عينة الدراسة 120 طالبًا"),
        S("results", "من أصل 120 طالبًا بواقع n=60 لكل مجموعة"),
        S("abstract", "شملت الدراسة 300 مشاركًا"),
    ])
    assert "sample_size_mismatch" in _keys(issues)


# ══════════ 5. قسمٌ مفعَّل بلا أدوار قسمٌ ميت ══════════

def test_every_enabled_section_can_actually_be_drafted():
    """**عطبان وجدهما الإنتاج.** «العنوان» و«النظرية» كانا مفعَّلين بلا أدوار
    أدلة — فسياقهما يعود بصفر دليل دائمًا، ولا يُكتبان أبدًا.

    وقسمٌ يُعرض للباحث «لم يبدأ» ولا يستطيع أن يبدأ أسوأ من قسمٍ معطَّل
    معلَن: الأول يَعِد، والثاني يقول الحقيقة.
    """
    for key in sorted(policy.ENABLED_SECTIONS):
        spec = policy.POLICIES[key]
        assert spec.roles, f"{key}: قسم مفعَّل بلا أدوار أدلة"
        for role in spec.required_any:
            assert role in spec.roles, f"{key}: يشترط دور {role} ولا يُرسل إليه"


def test_redaction_follows_the_evidence_not_a_hand_written_list():
    """**عطبٌ حجب الخاتمة في الإنتاج.**

    كان الحجب مقصورًا على «النتائج»، فوصلت الخاتمةَ ذاكرةٌ تقول «فروق دالة
    إحصائيًّا عند مستوى 0.05» بلا مخرَج يسندها — فأعادتها، فرُفضت. والقسم
    الذي **لا** يجوز أن يحمل إحصاءً أولى بالحجب من الذي يجوز.
    """
    for key, spec in policy.POLICIES.items():
        assert spec.redact_statistics == ("result" in spec.roles), key
    assert policy.POLICIES["conclusion"].redact_statistics is True
    assert policy.POLICIES["discussion"].redact_statistics is True
    assert policy.POLICIES["abstract"].redact_statistics is True
    # والمنهجية لا تصلها أدلة نتائج، فلا شيء يُحجب عنها.
    assert policy.POLICIES["method"].redact_statistics is False


# ══════════ 6. الحجب يُنظّف ولا يترك أثرًا يُنسخ ══════════

def test_redaction_removes_the_claim_instead_of_marking_its_place():
    """**عطبان في نداءٍ إنتاجي واحد.**

    كانت توضع مكان الادعاء علامةٌ محايدة `[غير متاح]`. فقالت للنموذج «هنا
    شيءٌ حُجب» — فأعاد بناءه من السياق، **ونسخ العلامة نفسها إلى نصّ
    المخطوطة**. فرُفضت المسودة بكشفين معًا.

    وعلامةٌ تقول «هنا شيءٌ حُجب» تُفشي ما وُضعت لتحجبه.
    """
    from athera_api.services.publishing.drafting import numbers
    from athera_api.services.publishing.vocab import INTERNAL_MARKERS

    body, removed = numbers.redact(
        "أظهرت النتائج وجود فروق دالة إحصائيًا عند مستوى 0.05 لصالح المجموعة")
    assert removed == ["دالة إحصائيًا عند مستوى 0.05"]
    for marker in INTERNAL_MARKERS:
        assert marker not in body, marker
    # ويبقى ما يسنده الدليل: وجود فرق، واتجاهه.
    assert "وجود فروق" in body and "لصالح المجموعة" in body
    assert "  " not in body, "فراغٌ مزدوج مكان المحذوف"


def test_an_empty_section_is_a_valid_answer():
    """**عطبٌ أسقط نداءً إنتاجيًّا.** كان العقد يشترط حرفًا واحدًا على الأقل،
    فلم يكن للنموذج سبيلٌ ليقول «لا يمكن كتابة هذا من الأدلة المتاحة».

    فإمّا أن يملأ الشكل بنثرٍ معقول، أو يسقط الطلب بخرق العقد — ووقع الثاني
    في أول نداء للمناقشة: دليلٌ واحد ومنعٌ محكم، فأعاد نواقصه بلا نصّ.
    """
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    draft = SectionDraft(missing_evidence=[
        {"topic_ar": "قيمة الدلالة الإحصائية", "why_ar": "لا مخرَج يحملها"}])
    assert draft.section_text_ar == ""
    assert len(draft.missing_evidence) == 1


def test_the_instruction_offers_the_empty_answer_explicitly():
    """لا يكفي أن يقبله العقد: يجب أن يُقال للنموذج إنه جواب."""
    from athera_api.services.publishing.drafting import generate

    assert "فارغًا" in generate.INSTRUCTION
    assert "دالّ إحصائيًّا" in generate.INSTRUCTION


# ══════════ 7. المخرجات تتبع سياسة الإحصاء لا سياسة الحجب ══════════

def test_a_section_that_forbids_statistics_receives_no_analysis_outputs():
    """**عطبٌ منع كتابة الخاتمة في الإنتاج، محاولةً بعد محاولة.**

    كانت المخرجات تُحمَّل حيثما يقع الحجب — وهما سؤالان مختلفان. فوصل
    «الخاتمةَ» مخرَجٌ يحمل `t = 3.738`، وسياستها تمنع الإحصاء أصلًا؛ فاستنتج
    النموذج الدلالة من قيمة (ت) بنفسه، ورفضها المدقّق في كل مرة.

    والقسم الذي لا يجوز أن يحمل إحصاءً لا تُرسل إليه أرقامٌ يستنتج منها.
    """
    import inspect

    from athera_api.services.publishing.drafting import context as ctx

    source = inspect.getsource(ctx.build)
    assert "spec.allows_statistics" in source
    assert "if section_key in REDACT_STATISTICS_IN:\n        outputs" not in source

    for key in ("conclusion", "limitations", "implications", "method"):
        assert policy.POLICIES[key].allows_statistics is False, key
    for key in ("results", "discussion", "abstract"):
        assert policy.POLICIES[key].allows_statistics is True, key


def test_redaction_and_output_loading_are_independent_questions():
    """يُحجب حيثما تصل أدلةُ نتائج، وتُرسل المخرجات حيثما يجوز الإحصاء."""
    conclusion = policy.POLICIES["conclusion"]
    assert conclusion.redact_statistics is True
    assert conclusion.allows_statistics is False

    limitations = policy.POLICIES["limitations"]
    assert limitations.redact_statistics is False
    assert limitations.allows_statistics is False


# ══════════ 8. مفردات المنهج تُفحص في المنهجية وحدها ══════════

def _section_context(section_key: str):
    import uuid

    from athera_api.services.planning.context import EvidenceItem
    from athera_api.services.publishing.drafting.context import DraftingContext

    item = EvidenceItem(uuid.uuid4(), "result", None, "أظهرت النتائج فروقًا",
                        "project_decision", None, "§النتائج ¶1", None)
    return DraftingContext(
        tenant_id=uuid.UUID(int=1), project_id=uuid.UUID(int=2),
        manuscript_id=uuid.UUID(int=3), opportunity_id=uuid.UUID(int=4),
        outline_id=None, section_key=section_key, language="ar", purpose_ar="",
        items=(item,), thread_labels=(), missing_roles=(), fingerprint="a" * 64)


def _issues(section_key: str, text: str):
    from athera_api.services.publishing.drafting import checks
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    context = _section_context(section_key)
    return {i.issue_key for i in checks.run(
        SectionDraft(section_text_ar=text), context,
        known_memory_ids=context.memory_ids, known_output_ids=frozenset())}


@pytest.mark.parametrize(("section", "text"), [
    ("conclusion", "لا يمكن في حدود الأدلة المتاحة الجزم بذلك"),
    ("discussion", "ويُعدّ مربع إيتا مقياسًا لحجم الأثر"),
])
def test_method_vocabulary_does_not_fire_outside_the_method_section(section, text):
    """**كشفان كاذبان وقعا في الإنتاج، وسببهما اشتراك اللفظ.**

    «في حدود الأدلة **المتاحة**» قُرئت عيّنةً متاحة، و«**مقياس** لحجم الأثر»
    قُرئ أداةَ دراسة. والحارس وُضع ليمنع قسم المنهجية من اختراع أداةٍ أو
    أسلوب معاينة — لا ليطارد المفردات في كل قسم.

    وحارسٌ يكثر ضجيجه يُتجاهَل، ثم لا يحرس شيئًا.
    """
    assert not {k for k in _issues(section, text) if k.startswith("unsupported_")}


def test_the_method_section_still_catches_an_invented_instrument():
    """والاستثناء لا يتّسع: المنهجية تبقى محروسة."""
    assert "unsupported_instrument" in _issues("method", "طُبّقت استبانة من إعداد الباحث")


# ══════════ 9. المناقشة تُكتب بلا قيمة دلالة ══════════
#
# **العائق الأخير في S5E-D.** المخرَج الحقيقي يحمل `t` و`df` وحجم الأثر
# والمتوسطات والانحرافات — **ولا يحمل قيمة p**. فكان النموذج يحسب الدلالة من
# (ت) ودرجات حريتها ويكتب «دالّ إحصائيًّا»، فيرفضه المدقّق في كل محاولة.
#
# والعطب لم يكن في الحارس: كان في أن أحدًا لم يُخبر النموذج **بما لا يملك**.

PRODUCTION_PAYLOAD = {
    "test": "independent_samples_t", "t": 3.738, "df": 118, "eta_squared": 0.106,
    "n_control": 60, "n_treatment": 60, "mean_control": 62.66, "mean_treatment": 68.11,
    "sd_control": 9.05, "sd_treatment": 6.75,
}


def _discussion_context(payload=None, section="discussion"):
    import uuid

    from athera_api.services.planning.context import EvidenceItem
    from athera_api.services.publishing.drafting.context import (
        AnalysisOutput,
        DraftingContext,
    )

    item = EvidenceItem(uuid.uuid4(), "result", None,
                        "أظهرت النتائج وجود فروق لصالح المجموعة التجريبية",
                        "project_decision", None, "§النتائج ¶18", None)
    outputs = ()
    if payload is not None:
        outputs = (AnalysisOutput(uuid.uuid4(), uuid.uuid4(), "posttest",
                                  "اختبار (ت)", payload),)
    return DraftingContext(
        tenant_id=uuid.UUID(int=1), project_id=uuid.UUID(int=2),
        manuscript_id=uuid.UUID(int=3), opportunity_id=uuid.UUID(int=4),
        outline_id=None, section_key=section, language="ar", purpose_ar="",
        items=(item,), thread_labels=(), missing_roles=(), fingerprint="a" * 64,
        outputs=outputs)


def _run_checks(context, text, claims=()):
    """يمرّ بالمسار الحقيقي: ربطٌ بنيوي ثم تحقّق — كما يفعل المسار."""
    from athera_api.services.publishing.drafting import checks, generate
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    draft = SectionDraft(section_text_ar=text, claims=list(claims))
    bound, _dropped = generate.ground(draft, context)
    generate.bind_statistics(draft, context, bound)
    verified = draft.model_copy(update={"claims": [
        b.claim.model_copy(update={"memory_ids": b.memory_ids,
                                   "analysis_output_ids": b.output_ids})
        for b in bound]})
    return {i.issue_key for i in checks.run(
        verified, context, known_memory_ids=context.memory_ids,
        known_output_ids=context.output_ids)}


def test_the_capability_summary_reports_exactly_what_production_has():
    """§4 — لا يُترك للنموذج أن يستنتج ما ينقص."""
    evidence = _discussion_context(PRODUCTION_PAYLOAD).statistics
    assert evidence.descriptive_available is True
    assert evidence.effect_size_available is True
    assert evidence.test_statistic_available is True
    assert evidence.p_value_available is False
    assert evidence.significance_claim_allowed is False


def test_the_capability_summary_reaches_the_provider():
    """يُقرأ لا يُستنتج: يُرسل في الطلب نفسه."""
    import json

    from athera_api.services.publishing.drafting import generate

    payload = json.loads(generate.build_prompt(_discussion_context(PRODUCTION_PAYLOAD)))
    assert payload["statistical_evidence"]["significance_claim_allowed"] is False
    assert payload["statistical_evidence"]["effect_size_available"] is True


def test_discussion_drafts_grounded_prose_without_a_p_value():
    """§15 — نقصُ قيمة الدلالة **لا يمنع** مناقشةً صادقة."""
    context = _discussion_context(PRODUCTION_PAYLOAD)
    prose = (
        "بلغ المتوسط الحسابي للمجموعة التجريبية 68.11 مقابل 62.66 للمجموعة "
        "الضابطة، وبلغت قيمة مربع إيتا 0.106. ولا تتوفر في الأدلة قيمة مستوى "
        "الدلالة، فلا يمكن الحكم على دلالة هذا الفرق إحصائيًّا."
    )
    assert _run_checks(context, prose) == set()


def test_an_unsupported_significance_claim_is_still_refused(  # §16
):
    from athera_api.services.publishing.drafting import checks

    context = _discussion_context(PRODUCTION_PAYLOAD)
    for phrasing in ("وجد فرق دال إحصائيًا بين المجموعتين",
                     "the difference was statistically significant",
                     "وكان الفرق دالًّا عند مستوى 0.05"):
        found = _run_checks(context, phrasing)
        assert found & {"significance_without_analysis_output",
                        "statistic_without_analysis_output"}, phrasing
    # ولا يصير نصًّا: الاختلاق لا يُحفظ ولو تحت «بانتظار المراجعة».
    assert "significance_without_analysis_output" in checks.FABRICATION_ISSUES


def test_significance_becomes_allowed_when_a_p_value_is_actually_recorded():
    """§17 — الإذن يأتي من قيمة مسجَّلة، لا من اشتقاق."""
    with_p = {**PRODUCTION_PAYLOAD, "p": 0.0003}
    context = _discussion_context(with_p)
    assert context.statistics.significance_claim_allowed is True
    assert _run_checks(context, "وجد فرق دال إحصائيًا بين المجموعتين") == set()


def test_the_platform_never_derives_the_missing_p_itself():
    """§2 — طبقة الكتابة ليست محرّك تحليل، ولا تحسب ما ينقص."""
    import inspect

    from athera_api.services.publishing.drafting import checks, context as ctx, numbers

    for module in (ctx, checks, numbers):
        source = inspect.getsource(module)
        for forbidden in ("scipy", "stats.t", "cdf(", "survival", "t_to_p",
                          "norm.sf", "math.erf"):
            assert forbidden not in source, f"{module.__name__}: {forbidden}"


def test_effect_size_thresholds_are_not_invented():
    """§7 — «صغير/متوسط/كبير» عتباتٌ اصطلاحية لا تسندها الأدلة."""
    from athera_api.services.publishing.drafting import generate

    assert "صغير" in generate.INSTRUCTION and "اذكر القيمة كما هي" in generate.INSTRUCTION


def test_the_discussion_rules_separate_direction_from_significance():
    """§8 — الاتجاه شيء، والدلالة شيء آخر يقرّره اختبار."""
    from athera_api.services.publishing.drafting import generate

    assert "الاتجاه" in generate.INSTRUCTION
    assert "قُبلت" in generate.INSTRUCTION
    rules = generate.SECTION_RULES["discussion"]
    assert "بانتظار البحث العلمي" in rules
    assert "لا يمنع المناقشة" in rules


def test_results_strictness_did_not_regress():
    """§9 — لا يُرخى شيءٌ من S5E-C لأجل المناقشة."""
    context = _discussion_context(PRODUCTION_PAYLOAD, section="results")
    assert "statistic_without_analysis_output" in _run_checks(
        context, "بلغت قيمة p = 0.05")
    assert "statistic_value_mismatch" not in _run_checks(
        context, "بلغت قيمة مربع إيتا 0.106")
