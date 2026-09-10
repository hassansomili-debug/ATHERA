"""الخيطُ الذهبيّ بنداءِ نموذج | slice 3 — حيث يدخل النموذج، وحدودُه.

**وهنا يقع خطرُ الاختلاق فعلًا.** كلُّ ما سبق بناءٌ حتميّ؛ وهذه أوّلُ نقطةٍ
يعود منها نصٌّ لم نكتبه. فالحدودُ الثلاثة تُفحص هنا بأدقّ ما يمكن بلا قاعدة:

  ١ **لا نداءَ داخل معاملة** — فحصٌ على شجرة الشيفرة لا على قراءةِ عين.
  ٢ **لا نداءَ بلا إذن** — والدعوى التي تهمّ هي أنّ عددَ النداءات **صفر**.
  ٣ **مرجعٌ لا يُحلّ يُرفض عنصرُه** — ولا يُصلَح ولا يُستبدل.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import uuid

import pytest

from athera_api.schemas.thesis import ThreadElementDraft
from athera_api.services.thesis import journey
from tests.conftest import requires_db


# ══════════ ١. لا نداءَ خارجيّ داخل معاملةٍ مفتوحة ══════════


def _model_calls_inside_session_blocks(function) -> list[int]:
    """أسطرُ نداءِ النموذج الواقعة **داخل** `async with session_maker()`.

    وهذا هو الفحصُ الذي كان ينقص يومَ عُلّقت الحزمةُ خمسًا وخمسين دقيقة:
    قراءةُ العين تُخطئ في المسافات البادئة، وشجرةُ الشيفرة لا تُخطئ.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncWith):
            continue
        opens_session = any(
            isinstance(item.context_expr, ast.Call)
            and getattr(item.context_expr.func, "id", "") == "session_maker"
            for item in node.items)
        if not opens_session:
            continue
        for inner in ast.walk(node):
            if (isinstance(inner, ast.Call)
                    and getattr(inner.func, "attr", "") == "run_structured_detached"):
                offenders.append(inner.lineno)
    return offenders


def test_the_model_is_never_called_inside_an_open_transaction():
    """**درسُ تخاصم سلسلة التدقيق، مثبَّتًا حارسًا.**"""
    offenders = _model_calls_inside_session_blocks(journey.build_thread)
    assert not offenders, (
        f"نداءُ نموذجٍ داخل معاملةٍ مفتوحة عند الأسطر {offenders} — "
        "معاملةٌ تمتدّ عبر الشبكة تُعلّق الحزمة")


def test_the_guard_would_catch_a_call_inside_a_transaction():
    """**وحارسٌ لا يعضّ حارسٌ ميّت** — فيُجرَّب على شكلٍ مخالفٍ مصطنع."""
    bad = textwrap.dedent('''
        async def f(session_maker):
            async with session_maker() as session:
                return await Orchestrator().run_structured_detached(session_maker)
    ''')
    tree = ast.parse(bad)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith) and any(
                isinstance(i.context_expr, ast.Call)
                and getattr(i.context_expr.func, "id", "") == "session_maker"
                for i in node.items):
            found += [n.lineno for n in ast.walk(node)
                      if isinstance(n, ast.Call)
                      and getattr(n.func, "attr", "") == "run_structured_detached"]
    assert found, "الحارسُ لا يرى نداءً داخل معاملة — فهو بلا أثر"


def test_the_call_goes_through_the_orchestrator_and_gateway_only():
    source = inspect.getsource(journey.build_thread)
    assert "run_structured_detached" in source
    assert 'input_classification="C2"' in source, "التصنيفُ ليس C2"
    for banned in ("openai", "anthropic", "httpx", "requests."):
        assert banned not in source, f"نداءُ مزوّدٍ مباشر: {banned}"


def test_consent_is_checked_before_any_work_is_built():
    """**والرفضُ يقع قبل بناء أيّ حِمل** — لا payload يُبنى ثمّ يُرمى."""
    source = inspect.getsource(journey.build_thread)
    consent_at = source.index("raise JourneyBlocked((BLOCK_NO_CONSENT,))")
    call_at = source.index("run_structured_detached")
    assert consent_at < call_at, "الإذنُ يُفحص بعد النداء — وهذا يعني نداءً بلا إذن"


def test_the_thread_build_passes_the_source_scope():
    """**وحدُّ العزل يُمرَّر هنا أيضًا** — أدلّةُ هذه الرسالة وحدها."""
    source = inspect.getsource(journey.build_thread)
    assert "source_file_id=file_id" in source, (
        "بناءُ الخيط يقرأ أدلّةَ المستأجر كلِّه — تسرُّبٌ بين رسالتين")


# ══════════ ٢. سلطةُ الأقسام: السياسةُ وحدها ══════════


def test_the_policy_is_the_only_section_authority():
    from athera_api.services.publishing.drafting import policy

    allowed = journey.draftable_sections()
    assert set(allowed) <= policy.ENABLED_SECTIONS
    assert set(allowed) == set(policy.ENABLED_SECTIONS)


def test_literature_review_and_references_stay_blocked():
    """**ولا يُكتب قسمٌ تمنعه السياسةُ لغياب الأدبيات.**"""
    blocked = journey.blocked_sections()
    assert "literature_review" in blocked
    assert "references" in blocked
    assert "literature_review" not in journey.draftable_sections()
    assert "references" not in journey.draftable_sections()


def test_section_selection_is_a_pure_decision_over_data():
    enabled = {"introduction", "methods"}
    candidates = ("introduction", "literature_review", "methods", "references")
    assert journey.sections_allowed(candidates, enabled=enabled) == (
        "introduction", "methods")
    assert journey.sections_refused(candidates, enabled=enabled) == (
        "literature_review", "references")


def test_no_section_name_is_hard_coded_in_the_journey_module():
    """قائمةٌ ثانية تُنشئ سلطةً تفترق عن السياسة بأوّل تعديل."""
    import pathlib

    source = pathlib.Path(inspect.getfile(journey)).read_text(encoding="utf-8")
    body = source[source.index("def sections_allowed"):]
    for name in ("introduction", "methodology", "discussion", "conclusion"):
        assert f'"{name}"' not in body, f"اسمُ قسمٍ مكتوبٌ بيد: {name}"


# ══════════ ٣. الحدُّ الذي لا يلين، على مخرَج نموذجٍ حقيقيّ الشكل ══════════


def test_a_model_element_with_an_invented_reference_is_rejected():
    """**وهنا تكسب `reject_unresolvable` وجودَها.**"""
    real = str(uuid.uuid4())
    ghost = str(uuid.uuid4())
    elements = [
        ThreadElementDraft(element_type="construct", label_ar="مُسنَد",
                                   evidence_refs=[real]),
        ThreadElementDraft(element_type="construct", label_ar="مخترَع",
                                   evidence_refs=[ghost]),
        ThreadElementDraft(element_type="construct", label_ar="مختلَط",
                                   evidence_refs=[real, ghost]),
        ThreadElementDraft(element_type="construct", label_ar="بلا إسناد",
                                   evidence_refs=[]),
    ]
    kept, rejected = journey.reject_unresolvable(
        elements, {real}, refs_of=lambda element: element.evidence_refs)

    assert [element.label_ar for element in kept] == ["مُسنَد"]
    assert [element.label_ar for element in rejected] == [
        "مخترَع", "مختلَط", "بلا إسناد"]
    # **ولم يُمسّ المرفوض**: لا مرجعَ بديل كُتب فيه.
    assert rejected[0].evidence_refs == [ghost]


def test_rejection_happens_before_any_row_is_written():
    """الرفضُ يسبق الكتابة — فلا صفٌّ مخترَع يُودَع ثمّ يُحذف."""
    source = inspect.getsource(journey.build_thread)
    assert source.index("reject_unresolvable") < source.index("session.add(ThreadElement")


def test_rejected_elements_are_counted_not_narrated():
    """عددُ المرفوض معلومةٌ للتدقيق، **ومتنُه اختلاقٌ لا يُحفظ**."""
    source = inspect.getsource(journey.build_thread)
    assert '"rejected": len(rejected)' in source
    for leak in ("rejected[0]", "element.label_ar for element in rejected"):
        assert leak not in source, f"متنُ المرفوض يُكتب: {leak}"


# ══════════ ٤. ما يحتاج قاعدةً — مكتوبٌ ولم يُشغَّل هنا ══════════
#
# **DB TESTS = NOT RUN على جهاز التطوير**: لا PostgreSQL. تُشغَّل في CI.


@requires_db
@pytest.mark.asyncio
async def test_without_consent_zero_external_calls_are_made(two_tenants, monkeypatch):
    """**والدعوى التي تهمّ: العدد صفر** — لا مجرّد أنّ الخطأ صحيح.

    فحصٌ يفحص نصَّ الخطأ يمرّ ولو وقع نداءٌ ثمّ فشل. والمقصودُ ألّا يقع.
    """
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session

    calls: list[str] = []

    async def _forbidden(*args, **kwargs):
        calls.append(kwargs.get("agent_key", "?"))
        raise AssertionError("نداءٌ خارجيّ وقع بلا إذن")

    monkeypatch.setattr(Orchestrator, "run_structured_detached", _forbidden)

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    with pytest.raises(journey.JourneyBlocked) as blocked:
        await journey.build_thread(
            lambda: tenant_session(tid, uid), tenant_id=tid, actor_user_id=uid,
            file_id=uuid.uuid4(), project_id=uuid.uuid4())

    assert journey.BLOCK_NO_CONSENT in blocked.value.reasons
    assert calls == [], f"وقع {len(calls)} نداءً خارجيًّا بلا إذن"


@requires_db
@pytest.mark.asyncio
async def test_a_model_failure_leaves_no_partial_thread(two_tenants, monkeypatch):
    """**وسقوطُ النموذج لا يترك أثرًا نصفيًّا.**

    الخطوةُ الأولى قراءةٌ فقط، والثالثةُ لا تُفتح إن سقطت الثانية.
    """
    from sqlalchemy import func, select

    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import ThreadElement

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = uuid.uuid4()

    async def _explode(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr(Orchestrator, "run_structured_detached", _explode)

    with pytest.raises((RuntimeError, journey.JourneyBlocked)):
        await journey.build_thread(
            lambda: tenant_session(tid, uid), tenant_id=tid, actor_user_id=uid,
            file_id=uuid.uuid4(), project_id=project_id)

    async with tenant_session(tid, uid) as session:
        written = (await session.execute(
            select(func.count(ThreadElement.id))
            .where(ThreadElement.project_id == project_id))).scalar_one()

    assert written == 0, f"سقط النموذجُ وبقي {written} صفًّا — أثرٌ نصفيّ"
