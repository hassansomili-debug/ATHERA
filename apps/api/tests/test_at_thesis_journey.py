"""رحلةُ الرسالة إلى ورقة | Thesis AI journey (V1) — القلبُ الصافي وحرّاسُه.

**والحارسُ الأول كُتب قبل ما يحرسه.** الشريحةُ الأولى أغلقت تسرُّبَ الأدلّة
بين رسالتين بحدٍّ في `WHERE`. وأخطرُ ما يعيده ليس تعديلًا في ذلك الحدّ، بل
**نداءٌ جديد ينسى تمريره**: لا يسقط شيء، ولا يُرفع خطأ، وتعود الرحلةُ تُصاغ
من أدلّة رسالةٍ أخرى بصمت. فالصمتُ هو نمطُ الفشل الذي يُحرَس هنا.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import uuid

import pytest

from athera_api.services.thesis import journey

# ══════════ ١. الحارس: لا نداءَ تخطيطٍ بلا حدِّ المصدر ══════════

_SCOPED_CALLERS = ("manuscript_drafting.py", "journey.py")


def _api_root() -> pathlib.Path:
    return pathlib.Path(inspect.getfile(journey)).resolve().parents[3]


def _planning_build_calls(tree: ast.AST) -> list[ast.Call]:
    """كلُّ نداءٍ إلى `…context.build(` أو `research_context.build(`."""
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "build":
            owner = getattr(func.value, "id", "")
            if owner in {"research_context", "context", "planning_context"}:
                calls.append(node)
    return calls


def test_every_thesis_journey_call_into_planning_passes_the_source_scope():
    """**نداءٌ بلا حدٍّ يُعيد التسرُّب الذي أُغلق — فيسقط هذا الفحص.**"""
    offenders: list[str] = []
    checked = 0
    for path in sorted((_api_root() / "athera_api").rglob("*.py")):
        if path.name == "context.py":
            continue  # موضعُ التعريف نفسه، لا نداءٌ إليه
        source = path.read_text(encoding="utf-8")
        if "context.build(" not in source:
            continue
        for call in _planning_build_calls(ast.parse(source)):
            checked += 1
            keywords = {k.arg for k in call.keywords}
            if "source_file_id" not in keywords:
                offenders.append(f"{path.name}:{call.lineno}")

    assert checked, "الحارسُ لم يجد نداءً واحدًا — تغيّر الشكلُ فصار بلا أثر"
    assert not offenders, (
        "نداءُ تخطيطٍ بلا حدِّ المصدر — تسرُّبُ أدلّةٍ بين رسالتين: "
        f"{offenders}")


def test_the_guard_would_catch_an_unscoped_call():
    """**وحارسٌ لا يعضّ حارسٌ ميّت** — فيُجرَّب على شكلٍ مخالفٍ مصطنع."""
    unscoped = ast.parse(
        "async def f():\n"
        "    return await research_context.build(session, tenant_id=t, project_id=p,\n"
        "                                        capability='c')\n"
    )
    calls = _planning_build_calls(unscoped)
    assert len(calls) == 1
    assert "source_file_id" not in {k.arg for k in calls[0].keywords}


# ══════════ ٢. الحالُ تُشتقّ من صفوف، ولا نسبةَ تُخترع ══════════


def test_the_sixteen_states_are_declared():
    assert len(journey.STATES) == 16
    assert len(set(journey.STATES)) == 16


def test_every_declared_state_is_actually_reachable():
    """**والدعوى: لا مفردةَ ميّتة.**

    كانت `draft_ready` معلَنةً في `STATES` ومرسومةً في خريطة الشاشة، ولا
    فرعَ في `derive_state` يعيدها. ونجت لأنّ الفحص القائم يقارن مجموعتين
    — الخادم والشاشة — وكلتاهما تحملها؛ فمفردةٌ ميّتة في الطرفين تمرّ.

    فهذا فحصُ **بلوغ** لا تطابق: يمشي على فضاء الوقائع كلِّه ويجمع ما
    تعيده الدالّةُ فعلًا، ثمّ يشترط أنّه `STATES` بلا زيادةٍ ولا نقصان.
    """
    import itertools

    F = journey.JourneyFacts
    reached = set()
    space = itertools.product(
        ("uploaded", "parsing", "ready_for_review", processing_failed()),
        (False, True),   # extraction_failed
        (0, 1),          # opportunities
        (False, True),   # selected_opportunity
        (0, 1),          # overlap_unresolved
        (False, True),   # rights_passed
        (False, True),   # ai_consent_granted
        (False, True),   # project_exists
        (False, True),   # thread_ready
        (False, True),   # outline_exists
        (False, True),   # manuscript_exists
        (0, 1, 3),       # sections_drafted
        (0, 3),          # sections_expected
        (False, True),   # literature_pending
    )
    for row in space:
        reached.add(journey.derive_state(F(*row)))

    declared = set(journey.STATES)
    assert declared - reached == set(), (
        f"مفرداتٌ معلَنةٌ لا تعيدها الدالّةُ أبدًا: {sorted(declared - reached)}")
    assert reached - declared == set(), (
        f"حالٌ تُعاد ولم تُعلَن: {sorted(reached - declared)}")


def processing_failed() -> str:
    from athera_api.services.thesis import processing

    return processing.FAILED


def test_no_percentage_is_ever_produced():
    """**«٦٠٪ مكتمل» رقمٌ بلا قياسٍ خلفه.** فلا نسبةَ في الوحدة أصلًا."""
    source = pathlib.Path(inspect.getfile(journey)).read_text(encoding="utf-8")
    for token in ("percent", "progress_ratio", "completion_pct", "/ len(STATES)"):
        assert token not in source, f"نسبةٌ مختلَقة: {token}"


def test_state_is_derived_from_real_rows_across_the_journey():
    F = journey.JourneyFacts
    assert journey.derive_state(F(processing_state="uploaded")) == journey.UPLOADED
    assert journey.derive_state(F(processing_state="parsing")) == journey.EXTRACTING
    assert journey.derive_state(F(processing_state="ready_for_review")) == journey.ANALYSED
    assert journey.derive_state(
        F(processing_state="ready_for_review", opportunities=2)
    ) == journey.RESEARCHER_DECISION_REQUIRED
    assert journey.derive_state(
        F(processing_state="ready_for_review", extraction_failed=True)) == journey.FAILED


def test_the_gates_are_read_in_order_and_none_is_skipped():
    """التداخلُ قبل الحقوق، والحقوقُ قبل الإذن — **ولا بوّابةَ تُقفز**."""
    F = journey.JourneyFacts
    base = dict(processing_state="ready_for_review", opportunities=1,
                selected_opportunity=True)

    assert journey.derive_state(F(**base, overlap_unresolved=1)) == (
        journey.OVERLAP_REVIEW_REQUIRED)
    assert journey.derive_state(F(**base)) == journey.RIGHTS_REQUIRED
    assert journey.derive_state(F(**base, rights_passed=True)) == (
        journey.AWAITING_AI_CONSENT)
    assert journey.derive_state(
        F(**base, rights_passed=True, ai_consent_granted=True)
    ) == journey.OPPORTUNITIES_READY


def test_consent_is_never_assumed():
    """**ولا يُمنح الإذنُ تلقائيًّا.** بلا إذنٍ تقف الرحلةُ وتُسمّي ما ينقصها."""
    F = journey.JourneyFacts
    facts = F(processing_state="ready_for_review", opportunities=1,
              selected_opportunity=True, rights_passed=True)
    assert journey.derive_state(facts) == journey.AWAITING_AI_CONSENT
    assert journey.BLOCK_NO_CONSENT in journey.blocking_reasons(facts)
    assert journey.can_build_paper(facts) is False


def test_build_is_refused_until_every_gate_passes():
    F = journey.JourneyFacts
    ready = F(processing_state="ready_for_review", opportunities=1,
              selected_opportunity=True, rights_passed=True, ai_consent_granted=True)
    assert journey.can_build_paper(ready) is True

    for broken in (
        dataclasses_replace(ready, overlap_unresolved=1),
        dataclasses_replace(ready, rights_passed=False),
        dataclasses_replace(ready, ai_consent_granted=False),
        dataclasses_replace(ready, opportunities=0, selected_opportunity=False),
    ):
        assert journey.can_build_paper(broken) is False


def dataclasses_replace(obj, **kw):
    import dataclasses

    return dataclasses.replace(obj, **kw)


def test_downstream_states_reflect_real_artefacts():
    F = journey.JourneyFacts
    done = dict(processing_state="ready_for_review", opportunities=1,
                selected_opportunity=True, rights_passed=True, ai_consent_granted=True)
    assert journey.derive_state(F(**done, project_exists=True)) == journey.PROJECT_CREATED
    assert journey.derive_state(
        F(**done, project_exists=True, thread_ready=True)) == journey.THREAD_READY
    assert journey.derive_state(
        F(**done, project_exists=True, outline_exists=True)) == journey.OUTLINE_READY
    assert journey.derive_state(
        F(**done, project_exists=True, manuscript_exists=True)) == journey.MANUSCRIPT_CREATED
    assert journey.derive_state(
        F(**done, manuscript_exists=True, sections_drafted=1, sections_expected=3)
    ) == journey.DRAFTING
    assert journey.derive_state(
        F(**done, manuscript_exists=True, sections_drafted=3, sections_expected=3)
    ) == journey.READY_FOR_PAPER_STUDIO
    # **وتحديثُ الأدبيات خطوةٌ بعد البناء لا قبله** (§14): مخطوطةٌ تمّت
    # أقسامُها ولم يُراجَع سجلُّ أدبياتها تقف هنا — أمّا مخطوطةٌ لم يُكتب
    # فيها حرفٌ بعدُ فحالُها أنّها أُنشئت، ولو كانت الأدبياتُ معلّقة.
    assert journey.derive_state(
        F(**done, manuscript_exists=True, sections_drafted=3, sections_expected=3,
          literature_pending=True)
    ) == journey.LITERATURE_PENDING
    assert journey.derive_state(
        F(**done, manuscript_exists=True, literature_pending=True)
    ) == journey.MANUSCRIPT_CREATED


# ══════════ ٣. الحدُّ الذي لا يلين: مرجعٌ لا يُحلّ يُرفض ══════════


def test_an_unresolvable_reference_is_rejected_never_repaired():
    """**الفرقُ بين مساعدٍ بحثيّ وآلةِ اختلاق.**

    عنصرٌ يحمل مرجعًا لا يردّ إلى صفٍّ حقيقيّ يُطرح كما هو — لا يُصلَح،
    ولا يُستبدل بمرجعٍ «معقول»، ولا يمرّ بتحذير.
    """
    real, ghost = str(uuid.uuid4()), str(uuid.uuid4())
    elements = [{"text": "مُسنَد", "refs": [real]},
                {"text": "مخترَع", "refs": [ghost]},
                {"text": "مختلَط", "refs": [real, ghost]}]

    kept, rejected = journey.reject_unresolvable(
        elements, {real}, refs_of=lambda e: e["refs"])

    assert [e["text"] for e in kept] == ["مُسنَد"]
    assert [e["text"] for e in rejected] == ["مخترَع", "مختلَط"]
    # **ولم يُمسّ المرفوض**: لا مرجعَ بديل كُتب فيه.
    assert rejected[0]["refs"] == [ghost]


def test_an_element_with_no_reference_at_all_is_rejected():
    """دعوى بلا إسنادٍ ليست دليلًا — وقبولُ الفراغ يجعله بابًا."""
    kept, rejected = journey.reject_unresolvable(
        [{"refs": []}], {str(uuid.uuid4())}, refs_of=lambda e: e["refs"])
    assert kept == []
    assert len(rejected) == 1


@pytest.mark.parametrize("ref", [None, "", 42, uuid.uuid4()])
def test_only_a_real_string_id_can_resolve(ref):
    assert journey.reference_resolves(ref, frozenset({"x"})) is False


# ══════════ ٦. الخيطُ الذهبيّ بوّابةً صافية ══════════
#
# **وفعلٌ لا تعرفه الشاشةُ فعلٌ لا يقع.** كانت `build_thread` مكتوبةً
# ومفحوصةً، ولها نقطةُ نهاية — ولا شيءَ في الرحلة ينادِيها. فحالُ
# `thread_ready` واقعةٌ لا تقع إلّا لمن قرأ الشيفرة أو نادى الـAPI بيده.
# فصارت البوّابةُ دالّةً صافيةً يقولها الخادمُ للشاشة.


def _ready_facts(**overrides):
    F = journey.JourneyFacts
    base = dict(processing_state="ready_for_review", opportunities=1,
                selected_opportunity=True, rights_passed=True,
                ai_consent_granted=True)
    return F(**{**base, **overrides})


def test_the_thread_needs_a_project_before_it_can_be_built():
    """**ولا خيطَ قبل مشروع** — الخيطُ يُعلَّق بمشروعٍ قائم لا يُخترع له صاحب."""
    assert journey.can_build_thread(_ready_facts()) is False
    assert journey.can_build_thread(_ready_facts(project_exists=True)) is True


def test_an_existing_thread_is_not_offered_for_building_again():
    """خيطٌ قائمٌ لا يُعرض زرًّا يُضغط — **يُعلَن أنّه قائم**."""
    facts = _ready_facts(project_exists=True, thread_ready=True)
    assert journey.can_build_thread(facts) is False


def test_the_thread_gate_never_skips_a_paper_gate():
    """**بوّاباتُ الورقة كلُّها تسبق الخيط** — ولا واحدةَ تُقفز إليه."""
    for broken in (
        dataclasses_replace(_ready_facts(project_exists=True), ai_consent_granted=False),
        dataclasses_replace(_ready_facts(project_exists=True), rights_passed=False),
        dataclasses_replace(_ready_facts(project_exists=True), overlap_unresolved=1),
        dataclasses_replace(_ready_facts(project_exists=True),
                            selected_opportunity=False, opportunities=0),
    ):
        assert journey.can_build_thread(broken) is False, (
            "الخيطُ يُبنى وبوّابةٌ لم تُفتح")


def test_the_consent_gate_is_declared_once_and_reused_by_both_actions():
    """**ولا بوّابةَ تُكتب مرّتين.** `can_build_thread` تسأل `blocking_reasons`."""
    source = inspect.getsource(journey.can_build_thread)
    assert "blocking_reasons(facts)" in source
    assert "ai_consent_granted" not in source, "بوّابةُ الإذن أُعيدت كتابتُها"


# ══════════ ٧. صدقُ الحال: الصياغةُ تُقاس بصفوفٍ محفوظة ══════════


def test_the_state_moves_with_persisted_sections_only():
    """**من «مخطوطة» إلى «صياغة» إلى «الأدبيات» — بصفوفٍ لا بنيّة.**

    وهذه هي السلسلةُ التي كانت مقطوعةً في المنتج: `sections_drafted` لا
    تزيد أبدًا لأنّ لا سبيلَ في الواجهة إلى نقطةِ الصياغة.
    """
    built = dict(processing_state="ready_for_review", opportunities=1,
                 selected_opportunity=True, rights_passed=True,
                 ai_consent_granted=True, project_exists=True,
                 thread_ready=True, outline_exists=True, manuscript_exists=True,
                 sections_expected=10)
    F = journey.JourneyFacts

    assert journey.derive_state(F(**built, sections_drafted=0)) == (
        journey.MANUSCRIPT_CREATED)
    # **وصفٌّ واحدٌ محفوظ يحرّك الحال** — لا نصفَ خطوةٍ ولا نسبة.
    assert journey.derive_state(F(**built, sections_drafted=1)) == journey.DRAFTING
    assert journey.derive_state(F(**built, sections_drafted=9)) == journey.DRAFTING


def test_a_finished_draft_still_waits_on_real_literature_validation():
    """**ولا تُقال جاهزيةٌ والأدبياتُ لم تُراجَع** (§14).

    والافتراضُ في العمود «معلّق» لا «مؤكَّد»، فورقةٌ تمّت أقسامُها تقف عند
    «تحديث الأدبيات» حتى يقع سجلٌّ حقيقيّ — ولا تُعلَن جاهزةً للاستوديو.
    """
    built = dict(processing_state="ready_for_review", opportunities=1,
                 selected_opportunity=True, rights_passed=True,
                 ai_consent_granted=True, project_exists=True,
                 thread_ready=True, outline_exists=True, manuscript_exists=True,
                 sections_expected=10, sections_drafted=10)
    F = journey.JourneyFacts

    assert journey.derive_state(F(**built, literature_pending=True)) == (
        journey.LITERATURE_PENDING)
    assert journey.derive_state(F(**built, literature_pending=False)) == (
        journey.READY_FOR_PAPER_STUDIO)


def test_the_literature_column_defaults_to_pending_not_confirmed():
    """**الافتراضُ لا يُقرَّ به ما لم يقع.** والعمودُ هو مصدرُ تلك الحال."""
    from athera_api.models.thesis import PublicationOpportunity

    column = PublicationOpportunity.__table__.c["literature_validation_status"]
    assert column.default.arg == "pending", (
        "افتراضُ الأدبيات ليس «معلّقًا» — فورقةٌ تُعلَن جاهزةً بلا مراجعة")
    assert column.nullable is False


def test_the_journey_view_exposes_the_thread_facts_the_screen_reads():
    """**وحقلٌ تقرؤه الشاشةُ ولا يُصدره الخادمُ عمودٌ فارغ.**"""
    from athera_api.schemas.thesis import JourneyResponse

    for field in ("thread_ready", "can_build_thread"):
        assert field in JourneyResponse.model_fields, f"حقلٌ مفقود: {field}"

    source = inspect.getsource(journey.view)
    assert '"thread_ready": facts.thread_ready' in source
    assert '"can_build_thread": can_build_thread(facts)' in source
