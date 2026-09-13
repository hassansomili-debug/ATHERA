"""ما الذي **يمكن** فعله الآن | The deterministic capability gates (Wave 2-A §24, §41).

**وهذه الرقعةُ تحرس سؤالًا واحدًا**، وكانت تحرس اثنين.

«لا يمكن تشغيل تحليلٍ بلا بيانات» واقعةٌ يقرؤها أيُّ قارئٍ من الصفوف نفسها
فيخرج بالجواب نفسه. وهي ما بقي في `journey.py`.

## وما سقط، ولماذا

كان فيه سجلُّ قواعدَ يرتّب «الخطوة التالية» بأولوياتٍ مستقلّةٍ عن ترتيب
المراحل في `stages.py`، فوقع تناقضٌ يراه الباحث:

    المرحلة الحالية : المراجع
    والزرُّ يقول    : حدِّد المنهج

ورحلةٌ موحَّدة لا تخالف نفسَها؛ ومحرّكان للقرار لا يُصلَحان بموازنةِ
أولوياتٍ بينهما بل بأن يبقى واحد. فصار الفعلُ الرئيس نداءَ المرحلة
الحاليّة بالبناء، وتُفحص تلك المرحلةُ في `test_at_rc0_stages.py`.

**والبوّاباتُ بقيت** لأنّها سؤالٌ مختلفٌ في نوعه لا في ترتيبه: تحجب، ولا
تنافس المراحلَ على «أين أنت».
"""
from __future__ import annotations

import pytest

from athera_api.research_brain import journey as j
from athera_api.research_brain import ontology as o

PROJECT = o.Project(id="project:1", label_ar="بحث")
QUESTION = o.ResearchQuestion(id="rq:1", label_ar="ما أثر التدريب؟")
SOURCE = o.Source(id="src:1", label_ar="مصدر")
DATASET = o.Dataset(id="ds:1", label_ar="بيانات")
ANALYSIS = o.Analysis(id="an:1", label_ar="تحليل")
FINDING = o.Finding(id="fn:1", label_ar="نتيجة")


def facts(*entities: o.Entity, **kw) -> j.JourneyFacts:
    return j.read_facts(o.ResearchGraph(entities=[PROJECT, *entities]), **kw)


def gate(key: str, *entities: o.Entity) -> j.Capability:
    found = next(row for row in j.capabilities(facts(*entities)) if row.key == key)
    return found


# ═════════════════ أ · البوّاباتُ الأربع، ولكلٍّ شرطُها ═════════════════


@pytest.mark.parametrize("key, requirement, present, code", [
    ("run_analysis", DATASET, (), j.NO_DATASET),
    ("record_finding", ANALYSIS, (DATASET,), j.NO_ANALYSIS),
    ("support_claim", SOURCE, (), j.NO_SOURCE),
    ("draft_results", FINDING, (DATASET, ANALYSIS), j.NO_FINDING),
])
def test_each_gate_opens_only_when_its_requirement_exists(key, requirement, present,
                                                          code):
    closed = gate(key, *present)
    assert closed.allowed is False and code in closed.blocking_reasons

    opened = gate(key, *present, requirement)
    assert opened.allowed is True and opened.blocking_reasons == ()


def test_an_empty_project_blocks_analysis_and_names_the_reason():
    """**والمنعُ يُسمّى** — لا ضابطٌ مطفأٌ صامت."""
    closed = gate("run_analysis")
    assert closed.allowed is False
    assert closed.blocking_reasons == (j.NO_DATASET,)


# ═════════════════ ب · حتميّةٌ لا احتماليّة ═════════════════


def test_a_gate_gives_the_same_answer_every_time():
    assert {gate("run_analysis", DATASET).allowed for _ in range(10)} == {True}


def test_the_gates_are_a_fixed_set_in_a_fixed_order():
    keys = [row.key for row in j.capabilities(facts())]
    assert keys == ["run_analysis", "record_finding", "support_claim", "draft_results"]


def test_the_rules_module_cannot_reach_a_database():
    """**دالّةٌ خالصة** — تُختبر بلا PostgreSQL، وذاك حدُّ الحزمة كلِّها."""
    import ast
    import pathlib

    source = pathlib.Path(
        "athera_api/research_brain/journey.py").read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    for module in imported:
        for banned in ("sqlalchemy", "models", "services", "db"):
            assert banned not in module, f"البوّاباتُ استوردت `{module}`"


# ═════════════════ ج · المنعُ بنيويّ، ولا سجلَّ توصياتٍ عائد ═════════════════


def test_a_capability_may_not_deny_without_a_reason():
    with pytest.raises(ValueError, match="منعٌ بلا سبب"):
        j.Capability(key="run_analysis", allowed=False)


def test_a_capability_may_not_allow_while_naming_a_blocker():
    with pytest.raises(ValueError, match="سببُ منعٍ مع إذن"):
        j.Capability(key="run_analysis", allowed=True,
                     blocking_reasons=("dataset_missing",))


def test_no_second_recommendation_engine_returns_to_this_module():
    """**حارسٌ ضدّ عودةِ التناقض.**

    فمحرّكٌ ثانٍ يرتّب «التالي» هنا يخالف ترتيبَ المراحل بعد أوّل تعديل،
    ويعود الباحثُ يقرأ مرحلةً ويضغط زرًّا يقول غيرَها.
    """
    for gone in ("decide", "RULES", "JourneyRule", "NextAction", "JourneyDecision"):
        assert not hasattr(j, gone), (
            f"عاد سجلُّ التوصيات إلى `journey.py`: {gone} — "
            "وصاحبُ القرار في الرحلة واحد، وهو `stages.py`")
