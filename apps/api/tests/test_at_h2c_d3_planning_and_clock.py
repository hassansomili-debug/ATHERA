"""H2-C + D3 — **هيكلُ الورقة بمفتاح، وكتالوجُ التخطيط، وساعةُ القاعدة** | Stage 8.

## ثلاثُ دعاوى

  ١ **الهيكلُ يتحمّل الإعادة** (H2-C): كان كلُّ نداءٍ يُنشئ صفَّ هيكلٍ جديدًا؛
    والآن النيّةُ الواحدةُ بمفتاحها ⇒ هيكلٌ واحد، والإعادةُ تُعيد معرّفَه.
  ٢ **كلُّ رمزِ خطأٍ في التخطيط له نصٌّ بلغتين** (D3): والقائمةُ تُشتقّ من
    المصدر في كلّ تشغيلة، لا من قائمةٍ منسوخةٍ تتخلّف.
  ٣ **ساعةُ حكمِ المعالجة ساعةُ القاعدة** (D3): لا `_now()` ولا
    `datetime.now` ولا معاملٌ مُمرَّرٌ يُكتب في `processing_state_changed_at`.
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

pytestmark = pytest.mark.asyncio

API = pathlib.Path(__file__).resolve().parents[1]
PKG = API / "athera_api"


# ═════════ الإعداد: أدلّةٌ ← إذنٌ ← توليدٌ ← اختيارٌ ← خيطٌ ═════════


def _two_opportunities() -> dict:
    from tests.test_at_s5d_publication_planning import _batch_json

    first = _batch_json()["opportunities"][0]
    second = dict(first, working_title_ar="أثر التعلّم التعاونيّ في الدافعيّة",
                  research_question_ar="ما أثر التعلّم التعاونيّ في الدافعيّة؟")
    return {"opportunities": [first, second]}


async def _ready_for_outline(slot, monkeypatch, http) -> tuple[uuid.UUID, list[str]]:
    """بحثٌ بفرصتين، الأولى مختارةٌ وخيطُها مبنيّ — **عبر المسارات الحقيقيّة**."""
    from tests.test_at_rc_t1_h2b4_model_ambiguity import (
        _activate, _grant_planning, _Structured)
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    project_id, _m, _f = await _seed_project_with_memory(slot["tenant_id"], slot["user_id"])
    await _grant_planning(slot, project_id)
    _activate(monkeypatch, _Structured(_two_opportunities()))

    base = f"/api/v1/projects/{project_id}/publication-opportunities"
    made = await http.post(base)
    assert made.status_code == 200, made.text
    ids = [o["id"] for o in made.json()["opportunities"]]
    assert len(ids) == 2, made.text
    chose = await http.post(f"{base}/{ids[0]}/decide", json={"decision": "select"})
    assert chose.status_code == 200, chose.text
    thread = await http.post(f"{base}/{ids[0]}/thread")
    assert thread.status_code == 200, thread.text
    return project_id, ids


def _outline_url(project_id, opportunity_id) -> str:
    return (f"/api/v1/projects/{project_id}/publication-opportunities/"
            f"{opportunity_id}/outline")


async def _outlines(tid, opportunity_id) -> int:
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _count

    return await _count(
        "SELECT count(*) FROM manuscript_outlines WHERE tenant_id = :t"
        "   AND opportunity_id = :o", {"t": str(tid), "o": str(opportunity_id)})


async def _outline_audits(tid, opportunity_id) -> int:
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _count

    return await _count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
        "   AND action = 'planning.outline_generated' AND object_id = :o",
        {"t": str(tid), "o": str(opportunity_id)})


# ═════════ ١ · الهيكلُ يتحمّل الإعادة ═════════


@requires_db
async def test_01_one_key_one_outline_and_the_replay_returns_its_id(
    two_tenants, monkeypatch,
):
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    async with _client(slot) as http:
        project_id, ids = await _ready_for_outline(slot, monkeypatch, http)
        url = _outline_url(project_id, ids[0])
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text
        replay = await http.post(url, headers={"Idempotency-Key": key})

    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json()["id"] == first.json()["id"], "الإعادةُ أنشأت هيكلًا آخر"
    assert await _outlines(slot["tenant_id"], ids[0]) == 1, "هيكلان لنيّةٍ واحدة"
    assert await _outline_audits(slot["tenant_id"], ids[0]) == 1, \
        "الإعادةُ كتبت حدثَ تدقيقٍ ثانيًا"


@requires_db
async def test_02_the_same_key_on_another_opportunity_is_refused(
    two_tenants, monkeypatch,
):
    """مسارُ الفرصة في الـURL لا في الجسم — **فيدخل البصمةَ صراحةً**."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    async with _client(slot) as http:
        project_id, ids = await _ready_for_outline(slot, monkeypatch, http)
        base = f"/api/v1/projects/{project_id}/publication-opportunities"
        first = await http.post(_outline_url(project_id, ids[0]),
                                headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text
        # الثانيةُ تُختار ويُبنى خيطُها — فتصحّ طلبًا، ويبقى المفتاحُ مفتاحَ الأولى.
        assert (await http.post(f"{base}/{ids[1]}/decide",
                                json={"decision": "select"})).status_code == 200
        assert (await http.post(f"{base}/{ids[1]}/thread")).status_code == 200
        other = await http.post(_outline_url(project_id, ids[1]),
                                headers={"Idempotency-Key": key})

    assert other.status_code == 409, f"{other.status_code}: {other.text[:200]}"
    assert other.json()["error"]["code"] == "idempotency.key_reused", other.text
    assert await _outlines(slot["tenant_id"], ids[1]) == 0, "بُني هيكلٌ على مفتاحٍ مُعاد"


@requires_db
async def test_03_the_same_key_after_the_context_changed_is_refused(
    two_tenants, monkeypatch,
):
    """بصمةُ السياق في البصمة: هيكلٌ بُني على سياقٍ آخر لا يُعاد."""
    from athera_api.routers import planning
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    async with _client(slot) as http:
        project_id, ids = await _ready_for_outline(slot, monkeypatch, http)
        url = _outline_url(project_id, ids[0])
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text

        real = planning._build_context  # noqa: SLF001

        async def _changed(*a, **k):
            built = await real(*a, **k)
            return dataclasses.replace(built, fingerprint=built.fingerprint + "-changed")

        monkeypatch.setattr(planning, "_build_context", _changed)
        again = await http.post(url, headers={"Idempotency-Key": key})

    assert again.status_code == 409, f"{again.status_code}: {again.text[:200]}"
    assert again.json()["error"]["code"] == "idempotency.key_reused"
    assert await _outlines(slot["tenant_id"], ids[0]) == 1


@requires_db
async def test_04_authorization_and_domain_state_are_checked_before_any_replay(
    two_tenants, monkeypatch,
):
    """**لا يُعاد جوابٌ مخزونٌ لمن لا يحقّ له الطلب الآن.**

    مستأجرٌ آخر بالمفتاح والمسار نفسَيهما يُردّ ٤٠٤ لا الهيكلَ المخزون؛
    والفرصةُ نفسُها بعد استبعادها تُردّ «اختر أوّلًا» لا إعادة.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    a, b = two_tenants["a"], two_tenants["b"]
    key = uuid.uuid4().hex
    async with _client(a) as http:
        project_id, ids = await _ready_for_outline(a, monkeypatch, http)
        url = _outline_url(project_id, ids[0])
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text

    async with _client(b) as stranger:
        foreign = await stranger.post(url, headers={"Idempotency-Key": key})
    assert foreign.status_code == 404, f"{foreign.status_code}: {foreign.text[:200]}"
    assert "sections" not in foreign.text

    async with _client(a) as http:
        base = f"/api/v1/projects/{project_id}/publication-opportunities"
        dropped = await http.post(f"{base}/{ids[0]}/decide", json={"decision": "exclude"})
        assert dropped.status_code == 200, dropped.text
        stale = await http.post(url, headers={"Idempotency-Key": key})
    assert stale.status_code == 409, stale.text
    assert stale.json()["error"]["code"] == "planning.selection_required", stale.text
    assert stale.headers.get("Idempotency-Replayed") is None


@requires_db
async def test_05_a_new_deliberate_build_after_success_makes_a_new_outline(
    two_tenants, monkeypatch,
):
    """**والهيكلُ لا يصير واحدًا إلى الأبد.** مفتاحٌ جديدٌ نيّةٌ جديدة."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    async with _client(slot) as http:
        project_id, ids = await _ready_for_outline(slot, monkeypatch, http)
        url = _outline_url(project_id, ids[0])
        first = await http.post(url, headers={"Idempotency-Key": uuid.uuid4().hex})
        second = await http.post(url, headers={"Idempotency-Key": uuid.uuid4().hex})
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert await _outlines(slot["tenant_id"], ids[0]) == 2


@requires_db
async def test_06_an_unkeyed_build_keeps_its_old_behaviour(two_tenants, monkeypatch):
    """**وبلا ترويسةٍ يسلك المسارُ مسلكَه القديم حرفيًّا** — صفٌّ لكلّ نداء.

    وهذا مقصودٌ ومُعلَن: المتصفّحُ يُرسل مفتاحًا دائمًا (المرحلة ٦)، والعميلُ
    الذي لا يُرسله يختار السلوكَ القديم بنفسه.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    async with _client(slot) as http:
        project_id, ids = await _ready_for_outline(slot, monkeypatch, http)
        url = _outline_url(project_id, ids[0])
        one = await http.post(url)
        two = await http.post(url)
    assert one.status_code == two.status_code == 200
    assert one.json()["id"] != two.json()["id"]
    assert "Idempotency-Replayed" not in two.headers


# ═════════ ٢ · كتالوجُ التخطيط — مُشتقٌّ من المصدر ═════════


def _raised_planning_codes() -> dict[str, list[str]]:
    """كلُّ رمزٍ `planning.*` يُرفع في مسار التخطيط وخدماته — بالشجرة لا بالنصّ."""
    raised: dict[str, list[str]] = {}
    files = [PKG / "routers" / "planning.py",
             *sorted((PKG / "services" / "planning").rglob("*.py"))]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str) \
                    and first.value.startswith("planning."):
                raised.setdefault(first.value, []).append(f"{path.name}:{node.lineno}")
    return raised


def test_07_every_raised_planning_code_is_bilingual() -> None:
    """الرموزُ المرفوعة ⊆ مفاتيحِ الكتالوج بنصٍّ غيرِ فارغ في اللغتين.

    **ولا قائمةَ منسوخة.** المرفوعُ يُقرأ من المصدر في كلّ تشغيلة؛ فرمزٌ
    جديدٌ يُرفع بلا نصٍّ يُحمِّر هذا الفحصَ من غير أن يتذكّره أحد.
    """
    from athera_api.i18n.catalog import CATALOG, translate

    raised = _raised_planning_codes()
    assert len(raised) >= 7, f"القراءةُ لم تجد ما يكفي: {sorted(raised)}"
    missing = {}
    for code, where in sorted(raised.items()):
        entry = CATALOG.get(code) or {}
        if not entry.get("ar", "").strip() or not entry.get("en", "").strip():
            missing[code] = where
            continue
        # و`translate` لا تُعيد الرمزَ نفسَه — أي أنّ الباحث يقرأ جملةً لا رمزًا.
        assert translate(code, "ar") != code and translate(code, "en") != code
    assert missing == {}, f"رموزُ تخطيطٍ بلا نصٍّ بلغتين: {missing}"


def test_08_the_planning_messages_say_what_the_researcher_can_do() -> None:
    """ولا رسالةَ تقول «خطأ» وحدها: كلٌّ منها تسمّي الخطوةَ التالية أو السبب."""
    from athera_api.i18n.catalog import CATALOG

    for code in ("planning.consent_required", "planning.insufficient_evidence",
                 "planning.selection_required", "planning.thread_required"):
        en = CATALOG[code]["en"].lower()
        assert any(w in en for w in ("first", "grant", "approve", "select", "build")), \
            (code, en)
        assert "error" not in en, (code, en)


# ═════════ ٣ · ساعةُ القاعدة لحكم المعالجة ═════════


_CLOCKS = {"_now", "now", "utcnow"}


def _process_clock(node: ast.AST) -> bool:
    """أهذا التعبيرُ ساعةَ العمليّة؟ `datetime.now(...)` أو `_now()` أو ما يشبهها."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call):
            func = inner.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            owner = func.value if isinstance(func, ast.Attribute) else None
            # `func.now()` ساعةُ القاعدة — والوحيدةُ المسموحة.
            if isinstance(owner, ast.Name) and owner.id == "func":
                continue
            if name in _CLOCKS:
                return True
    return False


def test_09_no_processing_fence_is_written_with_the_process_clock() -> None:
    """كلُّ كتابةٍ لـ`processing_state_changed_at` في التشغيل بساعةِ القاعدة.

    ثلاثةُ أشكالٍ تُفحص: وسيطٌ مسمّى (`.values(processing_state_changed_at=…)`)،
    ومفتاحُ قاموس (`{"processing_state_changed_at": …}`)، ونصُّ SQL خامٌّ
    (`processing_state_changed_at = … :param`) — **وكان الثالثُ متنكّرًا**:
    `THEN :now` يبدو ساعةَ القاعدة وهو معاملٌ يحمل ساعةَ العمليّة.
    """
    offenders: list[str] = []
    for path in sorted(PKG.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "processing_state_changed_at" not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "processing_state_changed_at":
                if _process_clock(node.value):
                    offenders.append(f"{path.name}:{node.value.lineno} keyword")
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values, strict=True):
                    if isinstance(k, ast.Constant) and k.value == "processing_state_changed_at" \
                            and _process_clock(v):
                        offenders.append(f"{path.name}:{v.lineno} dict")
            if isinstance(node, ast.JoinedStr) or (
                    isinstance(node, ast.Constant) and isinstance(node.value, str)):
                text = (node.value if isinstance(node, ast.Constant)
                        else "".join(p.value for p in node.values
                                     if isinstance(p, ast.Constant)))
                # **تعبيرُ إسنادِ هذا العمود وحدَه** — لا العبارةُ كلُّها: معاملُ
                # `:settled` لعمودٍ آخر في العبارة نفسِها مشروع.
                for assigned in re.findall(
                        r"processing_state_changed_at\s*=\s*(CASE.*?END|[^,]+)",
                        text, flags=re.S):
                    if re.search(r":[A-Za-z_]\w*", assigned):
                        offenders.append(f"{path.name}:{node.lineno} raw-sql bind")
    assert offenders == [], f"سياجُ المعالجة بساعة العمليّة: {offenders}"


def test_10_the_retired_claim_helper_is_gone_and_nothing_calls_it() -> None:
    from athera_api.services.thesis import processing

    assert not hasattr(processing, "claim_for_processing"), \
        "عادت `claim_for_processing` — بلا مُنادٍ في التشغيل، وبساعة العمليّة"
    callers = [str(p.relative_to(PKG)) for p in PKG.rglob("*.py")
               if "claim_for_processing(" in p.read_text(encoding="utf-8")]
    assert callers == [], callers


@requires_db
async def test_11_mark_writes_the_database_transaction_clock(two_tenants) -> None:
    """**وبرهانٌ حيّ لا بنيويٌّ وحده**: `now()` في القاعدة ثابتةٌ طوالَ المعاملة.

    فما يكتبه `mark()` يساوي `SELECT now()` في المعاملة نفسِها **حرفًا** —
    وساعةُ العمليّة لا تساويه أبدًا (تختلف بالميكروثانية على الأقلّ).
    """
    from sqlalchemy import select, text

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing
    from tests.test_at_thesis_intelligence_v2 import _seed_thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file = await _seed_thesis(tid, uid)
    async with tenant_session(tid, uid) as session:
        db_now = (await session.execute(text("SELECT now()"))).scalar_one()
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.QUEUED)
        written = (await session.execute(
            select(Thesis.processing_state_changed_at).where(Thesis.id == thesis_id)
        )).scalar_one()
    assert written == db_now, f"ساعةُ العمليّة كُتبت: {written} ≠ {db_now}"


@requires_db
async def test_12_the_legacy_settle_writes_the_database_clock_too(two_tenants) -> None:
    from sqlalchemy import select, text

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing
    from tests.test_at_thesis_intelligence_v2 import _seed_thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file = await _seed_thesis(tid, uid)
    async with tenant_session(tid, uid) as session:
        db_now = (await session.execute(text("SELECT now()"))).scalar_one()
        await processing.settle_after_legacy_parse(
            session, tenant_id=tid, thesis_id=thesis_id)
        written = (await session.execute(
            select(Thesis.processing_state_changed_at).where(Thesis.id == thesis_id)
        )).scalar_one()
    assert written == db_now, f"التسويةُ القديمةُ كتبت ساعةَ العمليّة: {written}"
