"""ما يمكن، وما يُستحسن — ولا يُخلطان | The journey orchestrator rules (Wave 2-A §23–§26).

**الفصلُ هو موضوعُ هذه الرقعة.** بوّابةٌ حتمية تقول «لا تحليلَ بلا بيانات»
واقعةٌ تُقرأ من الصفوف، وتوصيةٌ تقول «ابدأ بالوصفيّ» رأيٌ في الترتيب.
ودمجُهما يُنتج أحدَ عطبين: رأيٌ يصير حاجزًا يوقف باحثًا يعرف ما يفعل، أو
واقعةٌ تصير اقتراحًا يُتجاوَز فيُطلَب تحليلٌ لبياناتٍ غير موجودة.

ويُفحص هنا أيضًا ما يسهل أن يُنسى: أنّ **بحثًا خاويًا لا يُسقط الحساب**،
وأنّ **الفعلَ الممنوع يقول لمَ**.
"""
from __future__ import annotations

import pytest

from athera_api.research_brain import journey as j
from athera_api.research_brain import ontology as o
from athera_api.research_brain.values import known, missing


def graph(*entities: o.Entity) -> o.ResearchGraph:
    return o.ResearchGraph(entities=list(entities))


PROJECT = o.Project(id="project:1", label_ar="بحث")
QUESTION = o.ResearchQuestion(id="rq:1", label_ar="ما أثر التدريب؟")
DESIGN = o.Design(id="dz:1", label_ar="شبه تجريبيّ")
#: **عيّنةٌ حجمُها مسجَّل** — لا كيانُ عيّنةٍ فارغ. والفرقُ مقصود:
#: الجسرُ يُنشئ كيانَ عيّنةٍ لكلّ منهج، وحجمُه قد يكون غيرَ مسجَّل.
SAMPLE = o.Sample(id="sm:1", label_ar="عيّنة",
                  size=known(120.0, source_ref="method:1"))
#: وعيّنةٌ بلا حجمٍ مسجَّل — وهي ما يُنتجه منهجٌ لم يُذكر فيه العدد.
SAMPLE_UNSIZED = o.Sample(id="sm:1", label_ar="عيّنة", size=missing())
SOURCE = o.Source(id="src:1", label_ar="مصدر")
DATASET = o.Dataset(id="ds:1", label_ar="بيانات")
ANALYSIS = o.Analysis(id="an:1", label_ar="تحليل")
FINDING = o.Finding(id="fn:1", label_ar="نتيجة")


def facts(*entities: o.Entity, **kw) -> j.JourneyFacts:
    return j.read_facts(graph(PROJECT, *entities), **kw)


# ═════════════════ أ · بحثٌ خاوٍ لا يُسقط شيئًا (§57، §90) ═════════════════


def test_an_empty_project_does_not_crash_and_names_what_is_unknown():
    """**لا انهيار، ولا سؤالُ بحثٍ مخترَع.**

    وهذا هو الفحصُ الذي يمنع أشدَّ الأعطاب إغراءً: مسارٌ يملأ الفراغَ
    بقيمةٍ معقولةٍ ليُخرج جوابًا جميلًا.
    """
    decision = j.decide(j.read_facts(o.ResearchGraph()))

    assert decision.recommended is not None
    assert decision.recommended.action_key == "define_research_question"
    # ولا نصَّ يزعم أنّ ثمّة سؤالًا.
    assert "لا سؤالَ" in decision.recommended.reason_ar


def test_an_empty_project_blocks_analysis_and_says_why():
    """**والمنعُ يُسمّى** — لا زرَّ مطفأٍ بلا سبب."""
    decision = j.decide(j.read_facts(o.ResearchGraph()))
    gate = decision.capability("run_analysis")

    assert gate is not None and gate.allowed is False
    assert gate.blocking_reasons == (j.NO_DATASET,)


# ═════════════════ ب · البوّابات حتمية (§24) ═════════════════


@pytest.mark.parametrize("key, missing_entity, present, code", [
    ("run_analysis", DATASET, (), j.NO_DATASET),
    ("record_finding", ANALYSIS, (DATASET,), j.NO_ANALYSIS),
    ("support_claim", SOURCE, (), j.NO_SOURCE),
    ("draft_results", FINDING, (DATASET, ANALYSIS), j.NO_FINDING),
])
def test_each_gate_opens_only_when_its_requirement_exists(key, missing_entity,
                                                          present, code):
    closed = j.decide(facts(*present)).capability(key)
    assert closed.allowed is False and code in closed.blocking_reasons

    opened = j.decide(facts(*present, missing_entity)).capability(key)
    assert opened.allowed is True and opened.blocking_reasons == ()


def test_a_gate_is_the_same_answer_every_time():
    """**حتميّةٌ لا احتماليّة**: المُدخلُ نفسُه يُعطي الجوابَ نفسه."""
    seen = {j.decide(facts(DATASET)).capability("run_analysis").allowed
            for _ in range(10)}
    assert seen == {True}


# ═════════════════ ج · الترتيب حتميّ ولا يتبع ترتيبَ الإعلان ═════════════════


def test_the_order_is_by_priority_not_by_declaration():
    ordered = j.decide(j.read_facts(o.ResearchGraph()))
    priorities = [a.priority for a in ordered.actions]
    assert priorities == sorted(priorities)


def test_the_same_facts_give_the_same_actions_in_the_same_order():
    first = [a.action_key for a in j.decide(facts(QUESTION, DESIGN)).actions]
    second = [a.action_key for a in j.decide(facts(QUESTION, DESIGN)).actions]
    assert first == second


# ═════════════════ د · الرحلةُ تتقدّم بتقدّم البحث ═════════════════


@pytest.mark.parametrize("entities, expected", [
    ((), "define_research_question"),
    ((QUESTION,), "select_method"),
    ((QUESTION, DESIGN), "define_sample"),
    # **وكيانُ عيّنةٍ بلا حجمٍ لا يُسكت القاعدة** — وهو ما يُنتجه
    # الجسرُ فعلًا لكلّ منهجٍ مسجَّل.
    ((QUESTION, DESIGN, SAMPLE_UNSIZED), "define_sample"),
    ((QUESTION, DESIGN, SAMPLE), "link_sources"),
    ((QUESTION, DESIGN, SAMPLE, SOURCE, DATASET), "run_analysis"),
    ((QUESTION, DESIGN, SAMPLE, SOURCE, DATASET, ANALYSIS), "record_findings"),
    ((QUESTION, DESIGN, SAMPLE, SOURCE, DATASET, ANALYSIS, FINDING),
     "start_manuscript"),
])
def test_the_next_step_follows_the_state_of_the_research(entities, expected):
    """**الخطوةُ التالية تُشتقّ من الحال** — لا من صفحةٍ فتحها الباحث (§50)."""
    assert j.decide(facts(*entities)).recommended.action_key == expected


def test_a_completed_step_stops_being_suggested():
    assert "define_research_question" not in [
        a.action_key for a in j.decide(facts(QUESTION)).actions]


# ═════════════════ هـ · التعارضُ يُعرض ولا يُحسم (§17، §58) ═════════════════


def test_a_recorded_conflict_becomes_the_first_suggestion():
    decision = j.decide(facts(QUESTION, DESIGN, contradictions=["claim:7", "claim:8"]))

    assert decision.recommended.action_key == "resolve_contradiction"
    assert decision.recommended.evidence_refs == ("claim:7", "claim:8")


def test_the_conflict_action_does_not_pick_a_side():
    """**ولا ترجيحَ**: تُعرض الحالُ ويُدلّ على موضعها، والحسمُ للباحث."""
    action = j.decide(facts(contradictions=["claim:7"])).recommended
    for verdict in ("احذف", "استبعد", "الصحيح", "الأرجح", "تجاهل"):
        assert verdict not in action.reason_ar, f"ترجيحٌ في نصّ التعارض: {verdict}"


# ═════════════════ و · العقدُ نفسُه يمنع الطريقَ المسدود ═════════════════


def test_a_blocked_action_cannot_exist_without_a_named_reason():
    """**بنيويًّا لا اتفاقًا.** الكائنُ لا يُبنى أصلًا بلا سبب.

    وهو الدرسُ المدفوع ثمنُه في رحلة الرسالة: زرٌّ مطفأٌ لا يقول لمَ.
    """
    with pytest.raises(ValueError, match="بلا سببٍ مسمّى"):
        j.NextAction(
            action_key="x", category=j.ActionCategory.DATA,
            status=j.ActionStatus.BLOCKED,
            title_ar="ع", title_en="x", reason_ar="ع", reason_en="x")


def test_reasons_may_not_be_attached_to_an_unblocked_action():
    with pytest.raises(ValueError, match="أسبابُ منعٍ"):
        j.NextAction(
            action_key="x", category=j.ActionCategory.DATA,
            status=j.ActionStatus.RECOMMENDED,
            title_ar="ع", title_en="x", reason_ar="ع", reason_en="x",
            blocking_reasons=("dataset_missing",))


def test_a_capability_may_not_deny_without_a_reason():
    with pytest.raises(ValueError, match="منعٌ بلا سبب"):
        j.Capability(key="run_analysis", allowed=False)


# ═════════════════ ز · ولا نسبةَ إنجاز ولا مفردةَ رسائل ═════════════════


def test_no_action_carries_a_completion_percentage():
    """**ولا «٧٣٪ مكتمل»** (§45) — الحالاتُ المسمّاة هي الحقيقة."""
    for action in j.decide(facts(QUESTION, DESIGN)).actions:
        assert "%" not in action.reason_ar and "٪" not in action.reason_ar
        assert "%" not in action.reason_en


def test_every_action_explains_itself_in_both_languages():
    """**وكلُّ فعلٍ يقول لمَ** (§26) — بالعربية والإنجليزية معًا."""
    for action in j.decide(facts(QUESTION, DESIGN, DATASET,
                                 needs_review=["method"])).actions:
        assert action.reason_ar.strip() and action.reason_en.strip()
        assert action.title_ar.strip() and action.title_en.strip()


def test_no_thesis_vocabulary_reaches_the_researcher():
    """**ولا مفردةَ مركزِ رسائلَ في وجه الباحث** — الحدُّ `project_id` وحده (§75)."""
    forbidden = ("thesis", "mining", "رسالة", "تنقيب", "auto_eligible")
    for action in j.decide(facts(QUESTION, DESIGN, DATASET, ANALYSIS, FINDING,
                                 needs_review=["x"], contradictions=["c"])).actions:
        blob = " ".join([action.action_key, action.title_ar, action.title_en,
                         action.reason_ar, action.reason_en, action.route or ""])
        for word in forbidden:
            assert word not in blob.lower(), f"مفردةُ رسائلَ ظهرت: {word}"


def test_the_registry_has_no_duplicate_keys():
    """**سجلٌّ لا شجرةُ شروط** (§49) — ومفتاحان متكرران يجعلان قاعدةً لا تُطلق."""
    keys = [rule.key for rule in j.RULES]
    assert len(keys) == len(set(keys))
    assert set(j.BY_KEY) == set(keys)
