"""الخيط الذهبي المعروض | The displayed golden thread.

الدعوى المفحوصة واحدة: **لا خطّ بلا صفّ**. وكل اختبار هنا يبني صفوفًا
بعينها ثم يسأل عن الوصلة التي تخرج منها — لا عن عددٍ ولا عن درجة.
"""
from __future__ import annotations

import inspect
import re

from athera_api.services.golden_thread import weave as w


def _snapshot(**kwargs) -> w.ThreadSnapshot:
    return w.ThreadSnapshot(**kwargs)


def _between(result: w.WovenThread, stage_from: str, stage_to: str):
    return [c for c in result.connections
            if c.stage_from == stage_from and c.stage_to == stage_to]


# ── الدعوى الأولى: لا خطّ بلا صفّ ──

def test_an_empty_project_draws_no_connection_at_all():
    """بحثٌ فارغ يخرج بلا وصلة — ولا وصلةَ «مفترَضة» بين مرحلتين فارغتين."""
    result = w.weave(_snapshot())
    assert result.connections == ()
    assert result.nodes == ()


def test_every_known_connection_names_the_stored_row_that_proves_it():
    """`known` بلا `basis` وعدٌ لا شاهد — فلا تُقبل واحدة."""
    result = w.weave(_snapshot(
        elements=[w.ElementRow("e1", "problem", "مشكلة"),
                  w.ElementRow("e2", "objective", "هدف")],
        links=[w.LinkRow("e1", "e2", "addresses")]))
    known = [c for c in result.connections if c.state == w.KNOWN]
    assert known, "لم تُشتقّ وصلةٌ من رابطٍ مخزَّن"
    for connection in known:
        assert connection.basis, f"وصلة معلومة بلا صفّ يشهد لها: {connection}"
        assert connection.source_id and connection.target_id


def test_a_connection_that_is_not_known_leaves_the_absent_end_empty():
    """الطرف الغائب يبقى فارغًا ولا يُملأ بأقرب عقدةٍ في مرحلته."""
    result = w.weave(_snapshot(
        elements=[w.ElementRow("e1", "problem", "مشكلة"),
                  w.ElementRow("e2", "objective", "هدف")]))
    gaps = [c for c in result.connections if c.state != w.KNOWN]
    assert gaps
    for connection in gaps:
        assert (connection.source_id is None) != (connection.target_id is None)
        assert connection.basis is None


def test_a_stored_link_is_read_from_either_end():
    """الرابط يُسجَّل بأيّ ترتيب، وقراءتُه باتجاهٍ واحد تُخفي رابطًا موجودًا."""
    reversed_link = w.weave(_snapshot(
        elements=[w.ElementRow("e1", "problem", "مشكلة"),
                  w.ElementRow("e2", "objective", "هدف")],
        links=[w.LinkRow("e2", "e1", "addresses")]))
    assert [c.state for c in _between(reversed_link, "problem", "objective")] == [w.KNOWN]


# ── الأمثلة الثلاثة المطلوبة ──

def test_an_objective_whose_question_reaches_no_construct_is_missing_not_invented():
    """هدفٌ يذكر «النية السلوكية» ولا بناء مسجَّلًا لها ← ناقص.

    ولا يُخترع بناءٌ باسمٍ ورد في نصّ الهدف: مطابقةُ النصّ تأويل، والفراغ
    هو الصدق.
    """
    result = w.weave(_snapshot(
        elements=[w.ElementRow("q1", "question", "ما أثر السهولة في النية السلوكية؟")]))
    gaps = _between(result, "question", "construct")
    assert [c.state for c in gaps] == [w.MISSING]
    assert gaps[0].target_id is None
    assert "لا مفتاح مباشر" in gaps[0].detail_ar


def test_a_construct_the_instruments_do_not_measure_while_they_measure_others_conflicts():
    """سؤالٌ عن الرضا وأدواتٌ لا تقيس إلا الولاء ← تعارض.

    وصفّان مخزَّنان يقولان قولين: البحث يعلن أنه يدرس الرضا، وبنود أدواته
    مربوطةٌ بمتغيّر الولاء وحده.
    """
    result = w.weave(_snapshot(
        elements=[w.ElementRow("q1", "question", "سؤال الرضا", theory_id="t1")],
        theories=[w.TheoryRow("t1", "نظرية")],
        constructs=[w.ConstructRow("c1", "الرضا", "t1"), w.ConstructRow("c2", "الولاء", "t1")],
        variables=[w.VariableRow("v1", "رضا", "c1", True, True),
                   w.VariableRow("v2", "ولاء", "c2", True, False)],
        instruments=[w.InstrumentRow("i1", "استبانة", ("v2",))]))
    by_construct = {c.source_id: c.state for c in _between(result, "construct", "method")}
    assert by_construct["c1"] == w.CONFLICTING
    assert by_construct["c2"] == w.KNOWN


def test_the_same_construct_needs_review_when_its_variables_have_no_operational_definition():
    """و«لا يُقاس» ليست تعارضًا حين لا يُعلم أصلًا أيُقاس أم لا."""
    result = w.weave(_snapshot(
        theories=[w.TheoryRow("t1", "نظرية")],
        constructs=[w.ConstructRow("c1", "الرضا", "t1"), w.ConstructRow("c2", "الولاء", "t1")],
        variables=[w.VariableRow("v1", "رضا", "c1", False, True),
                   w.VariableRow("v2", "ولاء", "c2", True, False)],
        instruments=[w.InstrumentRow("i1", "استبانة", ("v2",))]))
    by_construct = {c.source_id: c.state for c in _between(result, "construct", "method")}
    assert by_construct["c1"] == w.NEEDS_REVIEW


def test_a_construct_is_only_missing_measurement_when_nothing_is_measured():
    """ولا تعارضَ حين لا أداة تقيس شيئًا: ذاك غيابُ تسجيلٍ لا تناقض."""
    result = w.weave(_snapshot(
        constructs=[w.ConstructRow("c1", "الرضا", None)],
        variables=[w.VariableRow("v1", "رضا", "c1", True, False)]))
    assert [c.state for c in _between(result, "construct", "method")] == [w.MISSING]


def test_a_recommendation_without_a_stored_result_needs_review_not_missing():
    """توصيةٌ لا تُتعقّب إلى نتيجة ← تحتاج مراجعة.

    و«ناقص» تقول «اربطها»، وهي كذبٌ هنا: نصفُ ما قد يسندها — مخرَج تحليل —
    لا عمود في المنصّة يربطه بتوصية.
    """
    result = w.weave(_snapshot(elements=[w.ElementRow("r1", "recommendation", "توصية")]))
    gaps = _between(result, "finding", "recommendation")
    assert [c.state for c in gaps] == [w.NEEDS_REVIEW]
    assert "لا مفتاح في المنصّة" in gaps[0].detail_ar


def test_a_managerial_implication_is_traced_to_its_output_by_a_stored_column():
    """الدلالة الإدارية **متعقَّبة إلى نتيجة بعمود** — فتُرسم، ولا تُخمَّن.

    `interpretations.output_id` مفتاحٌ إلى `analysis_outputs`، و§18.3 تفرض
    بقيدٍ ألّا تُكتب دلالةٌ إدارية بلا تفسيرٍ نظريّ قبلها. فهذا هو الطريق
    الوحيد الذي تُتعقّب فيه توصيةٌ إلى نتيجةٍ بمفتاح اليوم.
    """
    result = w.weave(_snapshot(
        runs=[w.RunRow("run1", "تشغيلة", "plan1")],
        outputs=[w.OutputRow("o1", "مخرَج", "run1")],
        implications=[w.ImplicationRow("i1", "يُوصى بتوسيع البرنامج", "o1")]))
    traced = [c for c in _between(result, "finding", "recommendation")]
    assert [c.state for c in traced] == [w.KNOWN]
    assert traced[0].basis == "interpretations.output_id"
    assert traced[0].source_id == "o1"


def test_the_two_kinds_of_recommendation_are_never_merged():
    """توصيةُ الخيط ودلالةُ النتيجة صفّان في جدولين — ولكلٍّ حالُه.

    ودمجُهما يجعل توصيةً كتبها الباحث بيده تُقرأ مسنودةً إلى تحليل.
    """
    result = w.weave(_snapshot(
        elements=[w.ElementRow("r1", "recommendation", "توصية كتبها الباحث")],
        runs=[w.RunRow("run1", "تشغيلة", "plan1")],
        outputs=[w.OutputRow("o1", "مخرَج", "run1")],
        implications=[w.ImplicationRow("i1", "دلالة إدارية", "o1")]))
    states = {c.target_id: c.state for c in _between(result, "finding", "recommendation")}
    assert states == {"i1": w.KNOWN, "r1": w.NEEDS_REVIEW}
    origins = {n.id: n.origin for n in result.stage_nodes("recommendation")}
    assert origins == {"i1": "interpretations", "r1": "thread_elements"}


def test_a_recommendation_linked_to_a_result_element_is_known_and_names_the_link():
    result = w.weave(_snapshot(
        elements=[w.ElementRow("f1", "result", "نتيجة"),
                  w.ElementRow("r1", "recommendation", "توصية")],
        links=[w.LinkRow("f1", "r1", "supports")]))
    known = _between(result, "finding", "recommendation")
    assert [c.state for c in known] == [w.KNOWN]
    assert known[0].basis == "thread_links.supports"


# ── سلسلة التحليل: مفاتيح مخزَّنة لا أسماءٌ متقاربة ──

def test_an_analysis_output_is_always_bound_to_its_run_by_a_non_nullable_column():
    result = w.weave(_snapshot(
        runs=[w.RunRow("run1", "تشغيلة", "plan1")],
        outputs=[w.OutputRow("o1", "مخرَج", "run1")]))
    bound = _between(result, "analysis", "finding")
    assert [c.state for c in bound] == [w.KNOWN]
    assert bound[0].basis == "analysis_outputs.run_id"


def test_a_result_written_as_a_thread_element_has_no_run_column_so_it_needs_review():
    """و«نتيجتان» ليستا من جنسٍ واحد: هذه لا عمود لها يشير إلى تشغيلة."""
    result = w.weave(_snapshot(elements=[w.ElementRow("f1", "result", "نتيجة")]))
    assert [c.state for c in _between(result, "analysis", "finding")] == [w.NEEDS_REVIEW]


def test_a_run_reaches_its_variables_through_the_data_dictionary_key():
    result = w.weave(_snapshot(
        variables=[w.VariableRow("v1", "رضا", None, True, False)],
        runs=[w.RunRow("run1", "تشغيلة", "plan1", dictionary_variable_ids=("v1",))]))
    hits = [c for c in _between(result, "method", "analysis") if c.state == w.KNOWN]
    assert [c.basis for c in hits] == ["data_dictionaries.variable_id"]


def test_a_run_reaches_its_hypothesis_through_the_planned_test_key():
    result = w.weave(_snapshot(
        elements=[w.ElementRow("h1", "hypothesis", "فرض")],
        planned_tests=[w.PlannedTestRow("pt1", "t_test", "plan1", "h1")],
        runs=[w.RunRow("run1", "تشغيلة", "plan1")]))
    hits = [c for c in _between(result, "question", "analysis") if c.state == w.KNOWN]
    assert [c.basis for c in hits] == ["planned_tests.hypothesis_id"]


def test_a_planned_test_bound_to_no_hypothesis_leaves_the_run_without_a_question():
    result = w.weave(_snapshot(
        planned_tests=[w.PlannedTestRow("pt1", "t_test", "plan1", None)],
        runs=[w.RunRow("run1", "تشغيلة", "plan1")]))
    assert [c.state for c in _between(result, "question", "analysis")] == [w.MISSING]


# ── الصدق فيما لا يُسجَّل ──

def test_what_the_platform_cannot_store_is_declared_beside_the_drawing():
    """الرابطان اللذان لا يُبنيان من بياناتٍ حقيقية يُعلَنان بنصّهما."""
    keys = {note.key for note in w.weave(_snapshot()).read_notes}
    assert "recommendation_to_output_not_stored" in keys
    assert "question_to_construct_not_stored" in keys


def test_an_absent_method_and_absent_instruments_are_said_not_implied():
    notes = {n.key for n in w.weave(_snapshot()).read_notes}
    assert {"method_not_recorded", "instruments_not_recorded"} <= notes
    with_both = w.weave(_snapshot(
        method=w.MethodRow("m1", "تصميم"), instruments=[w.InstrumentRow("i1", "أداة")]))
    assert not ({"method_not_recorded", "instruments_not_recorded"}
                & {n.key for n in with_both.read_notes})


# ── المفردة والمنع ──

def test_the_connection_states_are_the_platform_states_not_a_second_vocabulary():
    """`known | needs_review | missing | conflicting` — كما في بقيّة المستودع."""
    assert {w.KNOWN, w.NEEDS_REVIEW, w.MISSING, w.CONFLICTING} == {
        "known", "needs_review", "missing", "conflicting"}


def test_nothing_in_the_woven_thread_emits_a_score_or_a_percentage():
    """درجة الخيط تُحسب لبوابة البروتوكول، ولا تُنقل إلى شاشة الباحث.

    ورقمٌ واحد يخفي الفرق بين خيطٍ تنقصه وصلةٌ وخيطٍ ينقصه منهج — وهو
    القرار نفسه المتّخذ في «ما نعرفه»، ولا يُنقض من بابٍ ثانٍ.
    """
    forbidden = re.compile(r"percent|readiness|score|ratio|جاهزية|درجة", re.IGNORECASE)
    for name in w.WovenThread.__annotations__:
        assert not forbidden.search(name), f"الخيط المعروض يحمل حقل درجة: {name}"
    for name in w.Connection.__annotations__:
        assert not forbidden.search(name), f"الوصلة تحمل حقل درجة: {name}"
    source = inspect.getsource(w)
    assert "%" not in source, "حُسبت نسبة في نسج الخيط"
    assert "score" not in source.replace("score.py", ""), "استُدعيت الدرجة في نسج الخيط"


def test_the_stages_are_the_nine_named_ones_in_order():
    assert w.STAGE_KEYS == ("problem", "objective", "question", "theory", "construct",
                            "method", "analysis", "finding", "recommendation")


def test_every_node_declares_the_table_it_was_read_from():
    """عقدتان بالاسم نفسه من جدولين مختلفين ليستا الشيء نفسه."""
    result = w.weave(_snapshot(
        elements=[w.ElementRow("f1", "result", "نتيجة")],
        runs=[w.RunRow("run1", "تشغيلة", "plan1")],
        outputs=[w.OutputRow("o1", "مخرَج", "run1")]))
    origins = {node.id: node.origin for node in result.nodes}
    assert origins["f1"] == "thread_elements"
    assert origins["o1"] == "analysis_outputs"


def test_elements_outside_the_nine_stages_are_not_forced_into_the_nearest_one():
    """`gap` و`discussion` لا مرحلة لهما هنا، فلا تُحشران في أقربها."""
    result = w.weave(_snapshot(
        elements=[w.ElementRow("g1", "gap", "فجوة"),
                  w.ElementRow("d1", "discussion", "مناقشة")]))
    assert result.nodes == ()
    assert result.connections == ()


# ── العقد كما يخرج إلى المتصفّح ──

def test_the_view_contract_has_no_field_a_score_could_be_written_into():
    """العقد نفسه يمنع الدرجة، لا الاتفاق على ألّا تُكتب.

    و`ConsistencyResponse` تحمل `score` لبوابة البروتوكول؛ وشاشة الباحث
    عقدُها آخر بلا ذلك الحقل، فلا يُنقل الرقم بسطرٍ واحد بعد سنة.
    """
    from athera_api.schemas.golden_thread import GoldenThreadView, ThreadConnectionView

    forbidden = re.compile(r"percent|readiness|score|ratio|جاهزية", re.IGNORECASE)
    for model in (GoldenThreadView, ThreadConnectionView):
        for name in model.model_fields:
            assert not forbidden.search(name), f"{model.__name__} يحمل حقل درجة: {name}"


def test_the_connection_state_pattern_is_the_platform_vocabulary():
    from athera_api.schemas.golden_thread import ThreadConnectionView

    pattern = ThreadConnectionView.model_fields["state"].metadata[0].pattern
    for state in (w.KNOWN, w.NEEDS_REVIEW, w.MISSING, w.CONFLICTING):
        assert state in pattern


def test_the_golden_view_is_read_only_and_registered():
    """قراءةٌ بـ`GET` وحدها: شاشةٌ تعرض الخيط لا تكتب فيه."""
    from athera_api.main import app

    path = "/api/v1/projects/{project_id}/thread/golden-view"
    assert set(app.openapi()["paths"][path]) == {"get"}


# ── سجل القواعد: الرتبة تصل مع التنبيه ──

def test_every_scientific_rule_reaches_the_screen_with_its_status_and_provenance():
    """تنبيهٌ بلا رتبةٍ يُقرأ حكمًا معتمَدًا، وكلّها اليوم مسوّدة."""
    from athera_api.research_brain.catalogue import RULES
    from athera_api.schemas.brain import ScientificRuleResponse

    assert {"status", "provenance", "is_enforceable"} <= set(
        ScientificRuleResponse.model_fields)
    for rule in RULES:
        assert rule.status.value == "DRAFT"
        assert not rule.is_enforceable
        assert rule.provenance.strip()


def test_the_rule_registry_is_read_only_and_registered():
    from athera_api.main import app

    assert set(app.openapi()["paths"]["/api/v1/brain/rules"]) == {"get"}
