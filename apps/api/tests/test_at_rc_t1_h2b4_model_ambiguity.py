"""RC-T1-H2-B4 — **أثرُ النموذجِ الغامض** | ambiguous model effects.

## القاعدةُ الحاكمة

**مهلةٌ أو انقطاعٌ بعد إرسال طلبٍ إلى نموذجٍ لا يُثبت أنّ النموذجَ لم
ينفّذ.** فقد ولّد وحُوسِبنا ثمنَه ثمّ انقطع السلك. فلا يُعاد النداءُ
عميانًا، **ولا يُدَّعى «مرّةً واحدةً بالضبط»**.

## وثلاثةُ مواضعَ تفترق

    قبل الحدّ           ⇒ لا مزوّدَ نُودي  ⇒ يُستولى عليه ويُنفَّذ
    عبَر الحدَّ ولا يُعرف ⇒ قد نفّذ        ⇒ لا يُعاد النداء، ويُقال: لا يُعرف
    تَمَّ                ⇒ جوابٌ عندنا     ⇒ يُعاد بلا مزوّد

## ولمَ لا يكفي التقاطُ الاستثناء

العمليّةُ قد تموت وهي واقفةٌ **داخل** نداء المزوّد: لا استثناءَ، ولا
`finally`. فالتدوينُ يُودَع **قبل** النداء.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1_h3_ai_long_transactions import _observer

pytestmark = pytest.mark.asyncio


# ═════════ ١ · قدرةُ المزوّد: غيرُ مُثبَتةٍ لكِلَيهما ═════════


def test_01_both_adapters_declare_provider_idempotency_unproven() -> None:
    """**والافتراضُ عدمُ الإثبات** — ولا يُرقَّى محوّلٌ بالسكوت.

    وقد فُحص المصدرُ المُثبَّت لا الوثائقُ وحدها: `responses.create` و
    `messages.create` لا تقبلان `idempotency_key`، و`with_options` ترفضه،
    و`_idempotency_header` يبقى `None` فلا يُرسَل شيءٌ على السلك.
    """
    from athera_api.providers.anthropic_adapter import AnthropicAdapter
    from athera_api.providers.base import SERVER_DEDUPLICATED, UNPROVEN, ModelProvider
    from athera_api.providers.openai_adapter import OpenAIAdapter

    assert ModelProvider.model_idempotency_capability == UNPROVEN, \
        "الافتراضُ في الواجهة ليس «غيرَ مُثبَت»"
    assert OpenAIAdapter.model_idempotency_capability == UNPROVEN
    assert AnthropicAdapter.model_idempotency_capability == UNPROVEN
    assert SERVER_DEDUPLICATED != UNPROVEN


def test_02_the_installed_sdks_offer_no_idempotency_mechanism() -> None:
    """لا مِيكانيزمَ أصلًا في الإصدارَين المُثبَّتَين — فلا دعوى تُبنى عليه.

    وهذا أقوى من غياب التوثيق: لو وُجد ضمانٌ عند الخادم لَما استطاع هذا
    الـSDK أن يُعبّر عنه.
    """
    import inspect

    from anthropic.resources.messages import AsyncMessages
    from openai.resources.responses import AsyncResponses

    for method, label in ((AsyncResponses.create, "openai responses.create"),
                          (AsyncMessages.create, "anthropic messages.create")):
        params = set(inspect.signature(method).parameters)
        assert "idempotency_key" not in params, \
            f"{label} صار يقبل `idempotency_key` — تُراجَع دعوى الإثبات"

    # و`_idempotency_header` يبقى `None` فلا تُرسَل ترويسةٌ أصلًا.
    import anthropic._base_client as ab
    import openai._base_client as ob

    for mod, label in ((ob, "openai"), (ab, "anthropic")):
        src = inspect.getsource(mod)
        assert "self._idempotency_header = None" in src, \
            f"{label}: تغيّر تهيئةُ ترويسةِ الإزالة — يُعاد التصنيف"


# ═════════ ٢ · لا إعاداتٍ خفيّةً في SDK ═════════


def _capture_client(monkeypatch, module_name: str, class_name: str) -> dict:
    """يعترض إنشاءَ عميلِ الـSDK ويُسجّل وسائطَه — بلا نداءٍ حقيقيّ."""
    import sys
    import types

    seen: dict = {}

    class _Fake:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    module = types.ModuleType(module_name)
    setattr(module, class_name, _Fake)
    monkeypatch.setitem(sys.modules, module_name, module)
    return seen


def test_03_the_openai_client_is_built_with_no_sdk_retries(monkeypatch) -> None:
    """`max_retries=0` — **ولا يُتَّكل على افتراضِ الـSDK**.

    و`DEFAULT_MAX_RETRIES = 2` في هذا الإصدار، فنداءٌ واحدٌ من البوّابة
    يصير ثلاثَ محاولاتِ HTTP، وكلُّ محاولةٍ قد تولّد وتُحاسَب.
    """
    from athera_api.providers.openai_adapter import OpenAIAdapter

    seen = _capture_client(monkeypatch, "openai", "AsyncOpenAI")
    OpenAIAdapter(api_key="sk-test")._get_client()
    assert seen.get("max_retries") == 0, f"وسائطُ العميل: {seen}"


def test_04_the_anthropic_client_is_built_with_no_sdk_retries(monkeypatch) -> None:
    """`max_retries=0` كذلك — والافتراضُ هنا ٢ أيضًا."""
    from athera_api.providers.anthropic_adapter import AnthropicAdapter

    seen = _capture_client(monkeypatch, "anthropic", "AsyncAnthropic")
    AnthropicAdapter(api_key="sk-test", default_model="claude-x")._get_client()
    assert seen.get("max_retries") == 0, f"وسائطُ العميل: {seen}"


def test_05_the_sdk_default_is_still_two_so_the_override_matters() -> None:
    """يُثبَت أنّ الافتراضَ غيرُ صفرٍ — وإلّا كان التصريحُ زينةً.

    فلو صار الافتراضُ صفرًا يومًا بقي التصريحُ صحيحًا؛ ولو صار خمسةً
    بقي محميًّا. والمقصودُ ألّا يُقرأ هذا الفحصُ كأنّه يحرس شيئًا لا
    يحرسه.
    """
    from anthropic._constants import DEFAULT_MAX_RETRIES as A
    from openai._constants import DEFAULT_MAX_RETRIES as O

    assert O > 0 and A > 0, (
        f"افتراضُ الـSDK صار صفرًا (openai={O} anthropic={A}) — "
        "فيُراجَع نصُّ الدعوى لا الشِّفرة")


async def test_06_one_timeout_is_one_attempt_not_three(monkeypatch) -> None:
    """مهلةٌ واحدةٌ ⇒ **محاولةُ نقلٍ واحدة** لا ثلاث.

    ويُقاس عند النقل لا عند المحوّل: العدُّ عند المحوّل يمرّ ولو أعاد
    الـSDK ثلاثًا في الداخل.
    """
    import httpx
    from openai import AsyncOpenAI

    attempts = {"n": 0}

    def _boom(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        raise httpx.ConnectTimeout("simulated provider timeout")

    client = AsyncOpenAI(
        api_key="sk-test", max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_boom)))
    with pytest.raises(Exception):
        await client.responses.create(model="m", input="hi")
    assert attempts["n"] == 1, \
        f"محاولاتُ النقل {attempts['n']} — الـSDK أعاد خفيةً"

    # والضدُّ يُقاس: بالافتراضِ تصير ثلاثًا، فالتصريحُ هو الذي يمنع.
    attempts["n"] = 0
    lenient = AsyncOpenAI(
        api_key="sk-test",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(_boom)))
    with pytest.raises(Exception):
        await lenient.responses.create(model="m", input="hi")
    assert attempts["n"] > 1, (
        "الافتراضُ لم يُعِد — فالفحصُ لا يُثبت أنّ التصريحَ نافع "
        f"(محاولات={attempts['n']})")


# ═════════ ٣ · الحدُّ الخارجيُّ على قاعدةٍ حقيقيّة ═════════


OPERATION = "POST /api/v1/ai/ask"
FINGERPRINT = "f" * 64


async def _rows(sql: str, params: dict) -> list[tuple]:
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return [tuple(r) for r in (await session.execute(text(sql), params)).all()]
    finally:
        await engine.dispose()


async def _record(tenant_id, key: str) -> tuple:
    from athera_api.services.idempotency import digest_key

    rows = await _rows(
        "SELECT state, response_status, response_body, lease_expires_at"
        "  FROM idempotency_records WHERE tenant_id = :t AND key_digest = :d",
        {"t": str(tenant_id), "d": digest_key(key)})
    return rows[0] if rows else ()


async def _expire_lease(tenant_id, key: str) -> None:
    """تُنتهى الإجارةُ **بساعة القاعدة** — كموتِ عمليّةٍ تركت جيلَها."""
    from sqlalchemy import text

    from athera_api.services.idempotency import digest_key

    engine, factory = await _observer()
    try:
        async with factory() as session:
            await session.execute(
                text("UPDATE idempotency_records"
                     "   SET lease_expires_at = now() - interval '1 second'"
                     " WHERE tenant_id = :t AND key_digest = :d"),
                {"t": str(tenant_id), "d": digest_key(key)})
            await session.commit()
    finally:
        await engine.dispose()


async def _claim(slot, key: str, *, fingerprint: str = FINGERPRINT,
                 operation: str = OPERATION):
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        return await idem.acquire_lease(
            session, tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
            operation=operation, key=key, fingerprint=fingerprint,
            ttl=idem.LEASE_MODEL)


async def _mark(slot, lease, *, capability: str) -> None:
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        stale = await idem.mark_external_attempt(
            session, lease, provider="fake", capability=capability)
    assert stale is None, "لم يُدوَّن عبورُ الحدّ"


@requires_db
async def test_07_a_pre_external_abandoned_generation_may_be_taken_over(two_tenants):
    """عملٌ مهجورٌ **قبل** الحدّ: لا مزوّدَ نُودي ⇒ يُستولى عليه ويُنفَّذ."""
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    first = await _claim(slot, key)
    assert isinstance(first, idem.Lease), first

    # موتٌ قبل الحدّ: لا وسمَ كُتب.
    state, code, body, _f = await _record(slot["tenant_id"], key)
    assert state == "in_progress" and body is None, (state, body)

    await _expire_lease(slot["tenant_id"], key)
    second = await _claim(slot, key)
    assert isinstance(second, idem.Lease), \
        f"لم يُستولَ على عملٍ لم يبلغ المزوّد: {second}"
    assert second.record_id == first.record_id, "الجيلُ تغيّر بلا داعٍ"
    assert second.fence > first.fence, "السياجُ لم يتزايد"


@requires_db
async def test_08_an_external_attempted_generation_is_never_re_called(two_tenants):
    """عبَر الحدَّ ثمّ انتهت إجارتُه ⇒ **لا استيلاءَ ولا نداءَ** بل «لا يُعرف»."""
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    await _mark(slot, lease, capability=idem_unproven())

    # ── قبل انتهاء الإجارة: «قائمٌ لغيرك» ──
    live = await _claim(slot, key)
    assert isinstance(live, idem.InProgress), f"قبل الانتهاء: {live}"

    # ── وبعد انتهائها: أثرٌ لا يُعرف — ولا إجارةٌ تُمنَح ──
    await _expire_lease(slot["tenant_id"], key)
    after = await _claim(slot, key)
    assert isinstance(after, idem.ExternalUnknown), \
        f"استُولي على عملٍ عبَر الحدّ — وقد يكون النموذجُ نفّذ: {after}"
    assert after.provider == "fake"

    # ولا يصير الوسمُ جوابًا يُعاد.
    state, code, body, _f = await _record(slot["tenant_id"], key)
    assert state == "in_progress", state
    assert code is None, "وسمُ العبور صار جوابًا يُعاد"
    assert idem.EXTERNAL_MARKER in (body or {}), body


def idem_unproven() -> str:
    from athera_api.providers.base import UNPROVEN

    return UNPROVEN


@requires_db
async def test_09_a_completed_generation_replays_and_clears_the_marker(two_tenants):
    """الإتمامُ يكتب الجوابَ فوق الوسم ⇒ إعادةٌ من عندنا بلا مزوّد."""
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    await _mark(slot, lease, capability=idem_unproven())

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        stale = await idem.finalize_leased(session, lease, status=200,
                                           body={"answer": "ok"})
    assert stale is None

    state, code, body, fence = await _record(slot["tenant_id"], key)
    assert state == "completed" and code == 200, (state, code)
    assert idem.EXTERNAL_MARKER not in (body or {}), "بقي الوسمُ بعد الإتمام"
    assert fence is None

    replay = await _claim(slot, key)
    assert isinstance(replay, idem.Replay), replay
    assert replay.body == {"answer": "ok"}


@requires_db
async def test_10_a_known_pre_external_failure_stays_retryable(two_tenants):
    """إخفاقٌ **معلومٌ قبل** الحدّ (تفويضٌ، تصنيفٌ، مدخلٌ) يبقى قابلًا للإعادة."""
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        await idem.fail_leased(session, lease, reason="classification_refused")

    again = await _claim(slot, key)
    assert isinstance(again, idem.Lease), \
        f"مفتاحٌ سُمِّم بإخفاقٍ معلومٍ قبل الحدّ: {again}"


@requires_db
async def test_11_a_stale_worker_cannot_mark_the_external_boundary(two_tenants):
    """البائتُ لا يُدوّن على جيلٍ صار لغيره — فالوسمُ مُسَيَّج."""
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    stale_lease = await _claim(slot, key)
    assert isinstance(stale_lease, idem.Lease)

    await _expire_lease(slot["tenant_id"], key)
    winner = await _claim(slot, key)
    assert isinstance(winner, idem.Lease)
    assert winner.fence > stale_lease.fence

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        result = await idem.mark_external_attempt(
            session, stale_lease, provider="fake", capability=idem_unproven())
    assert isinstance(result, idem.Stale), \
        "البائتُ دوّن عبورَ حدٍّ على جيلِ غيره"


@requires_db
async def test_12_a_changed_fingerprint_conflicts_even_when_ambiguous(two_tenants):
    """جسمٌ آخرُ بالمفتاح نفسِه ⇒ تعارضٌ — ولا يُعاد جوابُ سياقٍ آخر."""
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    await _mark(slot, lease, capability=idem_unproven())
    await _expire_lease(slot["tenant_id"], key)

    with pytest.raises(idem.KeyReused):
        await _claim(slot, key, fingerprint="d" * 64)


@requires_db
async def test_13_the_marker_is_scoped_to_its_own_generation(two_tenants):
    """الوسمُ لا يعبُر جيلًا: مفتاحٌ آخرُ وعمليّةٌ أخرى لا يُصيبهما غموضُ غيرهما."""
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    marked = uuid.uuid4().hex
    lease = await _claim(slot, marked)
    assert isinstance(lease, idem.Lease)
    await _mark(slot, lease, capability=idem_unproven())
    await _expire_lease(slot["tenant_id"], marked)
    assert isinstance(await _claim(slot, marked), idem.ExternalUnknown)

    other_key = await _claim(slot, uuid.uuid4().hex)
    assert isinstance(other_key, idem.Lease), "غموضُ مفتاحٍ عبَر إلى مفتاحٍ آخر"
    other_route = await _claim(slot, marked, operation="POST /api/v1/brain/ask")
    assert isinstance(other_route, idem.Lease), "غموضُ عمليّةٍ عبَر إلى عمليّةٍ أخرى"
