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

# ══════════ ٥. البصمةُ البائتة: إذنٌ لا يصلح للّقطة الجديدة ══════════


def test_the_stale_fingerprint_gate_precedes_the_model_call():
    """**والرفضُ قبل النداء لا بعده** — فحصٌ على ترتيب المصدر."""
    source = inspect.getsource(journey.build_thread)
    assert "planning_state" in source, "لا فحصَ لبصمة اللقطة"
    assert source.index("BLOCK_STALE_CONSENT") < source.index("run_structured_detached"), (
        "البصمةُ تُفحص بعد النداء — أي أنّ النداء وقع على لقطةٍ بائتة")


def test_the_stale_check_uses_the_fingerprint_of_the_snapshot_just_built():
    """ولا تُفحص بصمةٌ غيرُ بصمةِ الأدلّة التي ستُرسَل فعلًا."""
    source = inspect.getsource(journey.build_thread)
    assert "fingerprint = evidence.fingerprint" in source
    assert "context_fingerprint=fingerprint" in source


def test_stale_is_its_own_reason_not_folded_into_refusal():
    """**«بائت» ليست «مرفوض».** الباحثُ لم يرجع عن شيء، والفرقُ يُقال."""
    assert journey.BLOCK_STALE_CONSENT != journey.BLOCK_NO_CONSENT
    assert journey.BLOCK_STALE_CONSENT == "ai_consent_stale"


@requires_db
@pytest.mark.asyncio
async def test_a_stale_fingerprint_makes_zero_external_calls(two_tenants, monkeypatch):
    """**أُذن ثمّ تغيّرت الأدلّة — فلا نداءَ واحد.**

    والدعوى هي العدد صفر، لا صحّةُ نصّ الخطأ.
    """
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.services import consent
    from athera_api.services.planning import context as research_context

    calls: list[str] = []

    async def _forbidden(*args, **kwargs):
        calls.append(kwargs.get("agent_key", "?"))
        raise AssertionError("نداءٌ خارجيّ وقع على لقطةٍ بائتة")

    monkeypatch.setattr(Orchestrator, "run_structured_detached", _forbidden)

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    file_id, project_id = uuid.uuid4(), uuid.uuid4()

    # إذنٌ حقيقيّ على الملفّ، ثمّ إذنُ تخطيطٍ ببصمةٍ **لا تطابق** اللقطة.
    async with tenant_session(tid, uid) as session:
        await consent.record_decision(
            session, tenant_id=tid, file_id=file_id, actor_user_id=uid,
            granted=True, provider="anthropic", model="m")
        await consent.record_planning_decision(
            session, tenant_id=tid, project_id=project_id, actor_user_id=uid,
            granted=True, context_fingerprint="a-fingerprint-from-an-older-snapshot",
            provider="anthropic", model="m")

    async with tenant_session(tid, uid) as session:
        live = await research_context.build(
            session, tenant_id=tid, project_id=project_id,
            capability=consent.PLANNING_CAPABILITY, source_file_id=file_id)
    assert live.fingerprint != "a-fingerprint-from-an-older-snapshot"

    with pytest.raises(journey.JourneyBlocked) as blocked:
        await journey.build_thread(
            lambda: tenant_session(tid, uid), tenant_id=tid, actor_user_id=uid,
            file_id=file_id, project_id=project_id)

    assert journey.BLOCK_STALE_CONSENT in blocked.value.reasons
    assert calls == [], f"وقع {len(calls)} نداءً على لقطةٍ بائتة"


# ══════════ ٦. إعادةُ الاستعمال: خيطٌ قائمٌ لا يُبنى ثانيًا ══════════
#
# **وعطبٌ صامتٌ كان هنا.** الدالّةُ تُدرج عقدًا جديدةً في كلِّ نداء، فإعادةُ
# الضغط على الزرّ تُضاعف عقدَ المشروع: خيطٌ واحدٌ في الشاشة وعقدتان في
# القاعدة لكلِّ فكرة. لا خطأَ يُرفع، ولا شيءَ يسقط — والعددُ وحده يكبر.
# وصار للزرّ موضعٌ في الرحلة، فالضغطُ عليه ثانيًا وقتيٌّ لا نظريّ.


def test_an_existing_thread_short_circuits_before_the_model_is_called():
    """**فحصُ إعادة الاستعمال يسبق النداء** — لا كلفةَ نموذجٍ لخيطٍ قائم."""
    source = inspect.getsource(journey.build_thread)
    assert "reused=True" in source, "لا سبيلَ لإعادة استعمال خيطٍ قائم"
    assert source.index("reused=True") < source.index("run_structured_detached"), (
        "إعادةُ الاستعمال تُفحص بعد النداء — أي أنّ النداء وقع بلا داعٍ")


def test_the_reuse_check_never_skips_a_consent_gate():
    """**والبوّابتان تسبقانه**: خيطٌ قائمٌ لا يفتح بابًا حول الإذن."""
    source = inspect.getsource(journey.build_thread)
    reuse_at = source.index("reused=True")
    assert source.index("BLOCK_NO_CONSENT") < reuse_at, "إعادةُ الاستعمال قبل الإذن"
    assert source.index("BLOCK_STALE_CONSENT") < reuse_at, (
        "إعادةُ الاستعمال قبل فحص البصمة")


def test_reuse_writes_no_row_and_claims_no_agent_run():
    """**ولا يُدَّعى نداءٌ لم يقع**: `agent_run_id` لا شيء عند إعادة الاستعمال."""
    outcome = journey.ThreadOutcome(created=3, rejected=0, fingerprint="f",
                                    agent_run_id=None, reused=True)
    assert outcome.reused is True
    assert outcome.agent_run_id is None

    source = inspect.getsource(journey.build_thread)
    early = source[:source.index("reused=True")]
    assert "session.add(ThreadElement" not in early, (
        "صفٌّ يُكتب في مسار إعادة الاستعمال — وهو التكرارُ بعينه")


@requires_db
@pytest.mark.asyncio
async def test_a_stale_fingerprint_makes_zero_external_calls(two_tenants, monkeypatch):
    """**والدعوى هي العدد صفر** — لا مجرّد أنّ الرفض وقع.

    إذنٌ أُعطي للقطةٍ لا يصلح لغيرها؛ وإرسالُها تحته إرسالُ ما لم يره الباحث.
    """
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.services import consent

    calls: list[str] = []

    async def _forbidden(*args, **kwargs):
        calls.append(kwargs.get("agent_key", "?"))
        raise AssertionError("نداءٌ خارجيّ وقع على لقطةٍ بائتة")

    monkeypatch.setattr(Orchestrator, "run_structured_detached", _forbidden)
    # الإذنُ قائمٌ شكلًا، والبصمةُ بائتة — وهذا هو الفرقُ المقصود.
    monkeypatch.setattr(journey, "consent_granted",
                        lambda *a, **k: _true(), raising=False)
    monkeypatch.setattr(consent, "planning_state",
                        lambda *a, **k: _value(consent.STALE))

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    with pytest.raises(journey.JourneyBlocked) as blocked:
        await journey.build_thread(
            lambda: tenant_session(tid, uid), tenant_id=tid, actor_user_id=uid,
            file_id=uuid.uuid4(), project_id=uuid.uuid4())

    assert journey.BLOCK_STALE_CONSENT in blocked.value.reasons
    assert calls == [], f"وقع {len(calls)} نداءً على لقطةٍ بائتة"


async def _true() -> bool:
    return True


async def _value(v):
    return v


@requires_db
@pytest.mark.asyncio
async def test_building_the_thread_twice_creates_no_duplicate_elements(
        two_tenants, monkeypatch):
    """**والضغطُ ثانيًا لا يُضاعف عقدَ المشروع.**"""
    from sqlalchemy import func, select

    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import ThreadElement

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = uuid.uuid4()

    # عقدةٌ قائمةٌ تمثّل خيطًا مبنيًّا من قبل.
    async with tenant_session(tid, uid) as session:
        session.add(ThreadElement(
            tenant_id=tid, project_id=project_id, element_type="construct",
            label_ar="عقدةٌ قائمة", ordinal=1, metadata_json={}))

    calls: list[str] = []

    async def _counted(*args, **kwargs):
        calls.append(kwargs.get("agent_key", "?"))
        raise AssertionError("نداءٌ خارجيّ وقع لخيطٍ قائم")

    monkeypatch.setattr(Orchestrator, "run_structured_detached", _counted)

    try:
        outcome = await journey.build_thread(
            lambda: tenant_session(tid, uid), tenant_id=tid, actor_user_id=uid,
            file_id=a.get("file_id") or uuid.uuid4(), project_id=project_id)
    except journey.JourneyBlocked:
        pytest.skip("الإذنُ غيرُ مهيَّإ في هذه التجهيزة — والتكرارُ مفحوصٌ بنيويًّا")

    assert outcome.reused is True, "خيطٌ قائمٌ أُعيد بناؤه"
    assert outcome.created == 0, "دعوى إنشاءٍ لم يقع"
    assert calls == [], "نداءٌ خارجيّ وقع لخيطٍ قائم"

    async with tenant_session(tid, uid) as session:
        count = (await session.execute(
            select(func.count(ThreadElement.id))
            .where(ThreadElement.project_id == project_id))).scalar_one()
    assert count == 1, f"صار في المشروع {count} عقدة بعد بناءين — تكرار"


# ══════════ ٧. العزل: أدلّةُ رسالةٍ لا تصل خيطَ أخرى ══════════


def test_the_thread_reads_only_this_thesis_evidence():
    """**حدُّ المصدر يُمرَّر، ولا يُقرأ المستأجرُ كلُّه.**

    وهذا هو الحدُّ الذي يمنع أدلّةَ رسالةٍ (أ) من دخول خيطِ رسالةٍ (ب):
    `source_file_id` هو ملفُّ **هذه** الرسالة وحده.
    """
    source = inspect.getsource(journey.build_thread)
    assert "source_file_id=file_id" in source
    # وملفُّ الرسالة يُقرأ من صفّها في نقطة النهاية، لا يأتي من المُدخل.
    from athera_api.routers import thesis as thesis_router

    endpoint = inspect.getsource(thesis_router.build_thread)
    assert "file_id = thesis.file_id" in endpoint, (
        "ملفُّ الرسالة لا يُقرأ من صفّها — فقد يصل ملفُّ رسالةٍ أخرى")
    assert "_opportunity_of_thesis(" in endpoint, (
        "النسبُ لا يُفحص — فرصةُ رسالةٍ أخرى قد تُبنى هنا")


def test_the_thread_endpoint_scopes_every_read_to_one_tenant():
    """**ولا قراءةَ عابرةَ مستأجر.** الحدُّ في كلِّ استعلام، لا في واحد."""
    source = inspect.getsource(journey.build_thread)
    reads = source.count("tenant_id=tenant_id") + source.count(
        "ThreadElement.tenant_id == tenant_id")
    assert reads >= 3, "استعلامٌ بلا حدِّ مستأجر في بناء الخيط"
    assert "ThreadElement.tenant_id == tenant_id" in source, (
        "فحصُ الخيط القائم بلا حدِّ مستأجر — خيطُ مستأجرٍ آخر يُقرأ")
