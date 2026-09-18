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


@pytest.fixture(autouse=True)
def _memory_storage(monkeypatch):
    """مخزنٌ في الذاكرة — فلا MinIO على هذه الآلة (ولا شأنَ له بـB4)."""
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory",
                        raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


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


# ═════════ ٤ · الحدُّ بعينه، لا أوّلُ المعالج ═════════


def test_14_the_boundary_hook_sits_between_authorize_and_invoke() -> None:
    """المُعلَّقُ **بعد** التفويض و**قبل** النداء — ولا شيءَ بينهما.

    ولو كان قبل التفويض لَوُسِم غامضًا ما رُدّ محليًّا: أداةٌ مُنعت، أو
    تصنيفٌ رُفض، أو تفويضُ مزوّدٍ سقط — ولم يُنادَ مزوّدٌ قطّ. فيُحرَم
    صاحبُه إعادةً مشروعة.
    """
    import ast
    import inspect
    import textwrap

    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.services.extraction.model import ModelExtractor

    # **والمستخرِجُ النموذجيُّ يخضع للقاعدة نفسِها**: له مسارُ نداءٍ خاصّ،
    # فلو فُحص المنسّقُ وحدَه بقي بابٌ ثالثٌ بلا حارس.
    targets = [Orchestrator.run_agent_detached,
               Orchestrator.run_structured_detached,
               ModelExtractor._call]  # noqa: SLF001 — مسارُ النداء بعينه
    for target in targets:
        name = target.__qualname__
        src = textwrap.dedent(inspect.getsource(target))
        fn = ast.parse(src).body[0]
        at: dict[str, int] = {}
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            label = ast.unparse(node.func)
            if label.endswith("_gateway.authorize"):
                at["authorize"] = node.lineno
            elif label.endswith("_gateway.invoke"):
                at["invoke"] = node.lineno
            elif label in {"before_provider_call",
                           "self._before_provider_call"}:
                at["hook"] = node.lineno
        assert {"authorize", "hook", "invoke"} <= set(at), f"{name}: {at}"
        assert at["authorize"] < at["hook"] < at["invoke"], f"{name}: {at}"
        # ══ ولا **جملةَ** بينهما، لا نداءً فقط ══
        #
        # وأوّلُ صيغةٍ لهذا الفحصِ عدّت النداءاتِ وحدَها، فمرّ عليها
        # `_ = self._gateway.provider_name` (وصولُ سمةٍ لا نداء). فيُقاس
        # **التجاور**: كتلةُ الوسمِ يتلوها نداءُ المزوّدِ مباشرةً، بلا جملةٍ
        # بينهما من أيّ نوع.
        adjacent = False
        for node in ast.walk(fn):
            body = getattr(node, "body", None)
            if not isinstance(body, list):
                continue
            for index, statement in enumerate(body):
                holds_hook = any(
                    isinstance(c, ast.Call)
                    and ast.unparse(c.func) in {"before_provider_call",
                                                 "self._before_provider_call"}
                    for c in ast.walk(statement))
                if not holds_hook or index + 1 >= len(body):
                    continue
                following = body[index + 1]
                if any(isinstance(c, ast.Call)
                       and ast.unparse(c.func).endswith("_gateway.invoke")
                       for c in ast.walk(following)):
                    adjacent = True
        assert adjacent, (
            f"{name}: كتلةُ الوسمِ لا يتلوها نداءُ المزوّد مباشرةً — "
            "بينهما عمل، فما بعد الوسمِ قد يُردّ ولم يُنادَ مزوّد")


@requires_db
async def test_15_the_schema_itself_forbids_an_ambiguous_agent_run(two_tenants):
    """**ويُقال الحدُّ صريحًا، ويُقرأ من القاعدة لا من الظنّ.**

    `agent_runs.status` مُقيَّدٌ بـ`CHECK` على أربع قيم، وليس فيها ما يقول
    «لا يُعرف». و«failed» دعوى أقوى من المعلوم، و«blocked» يقول إنّنا
    رفضنا ولم نرفض. فلا يُكتب صفُّ تشغيلةٍ كاذبٌ أصلًا: `model_runs` بلا
    قيدٍ فيقول `ambiguous` صراحةً، ووسمُ الجيل الدائم هو البرهانُ الباقي.

    **ولا هجرةَ 0038 لهذا.** ولو زال القيدُ يومًا فليُعَد النظرُ في
    التمثيل بدل أن يبقى الالتفافُ بلا سبب — وهذا الفحصُ يُنبّه حينها.
    """
    rows = await _rows(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c"
        " WHERE c.contype = 'c' AND c.conrelid = 'agent_runs'::regclass"
        "   AND pg_get_constraintdef(c.oid) LIKE '%status%'", {})
    assert rows, "لم يُعثر على قيدٍ على حالِ التشغيلة"
    definition = rows[0][0]
    assert "'ambiguous'" not in definition, (
        "صارت `ambiguous` مسموحةً في `agent_runs.status` — "
        f"فيُبسَّط التمثيل: {definition}")
    for allowed in ("running", "completed", "failed", "blocked"):
        assert f"'{allowed}'" in definition, (
            f"تغيّرت قيمُ الحال المسموحة، و{allowed!r} مفقودة: {definition}")

    # و`model_runs` بلا قيدٍ على الحال — فهو موضعُ القول الصريح.
    model_rows = await _rows(
        "SELECT count(*) FROM pg_constraint c"
        " WHERE c.contype = 'c' AND c.conrelid = 'model_runs'::regclass"
        "   AND pg_get_constraintdef(c.oid) LIKE '%status%'", {})
    assert model_rows == [(0,)],         f"صار على `model_runs.status` قيدٌ — يُراجَع تمثيلُ الغموض: {model_rows}"


@requires_db
async def test_16_a_post_boundary_timeout_is_ambiguous_not_failed(
    two_tenants, monkeypatch,
):
    """مهلةٌ **بعد** الحدّ: لا تشغيلةَ كاذبة، وسجلُّ نموذجٍ `ambiguous`.

        الجيلُ يبقى `in_progress` ومعه الوسم
        ولا `AgentRun` يقول «أخفق»
        و`ModelRun.status == "ambiguous"`
        ونداءُ المزوّدِ **واحد**
    """
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    maker = lambda: tenant_session(slot["tenant_id"], slot["user_id"])  # noqa: E731

    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    guard = idem.LeaseGuard(lease=lease, operation=OPERATION)
    boundary = idem.ModelBoundary(maker, guard, provider="fake",
                                  capability=idem_unproven())

    calls = {"n": 0}

    class _Timeout:
        name = "fake"
        model_idempotency_capability = idem_unproven()

        async def generate_structured(self, request):
            calls["n"] += 1
            raise TimeoutError("provider timed out mid-generation")

        async def stream(self, request):  # pragma: no cover — غيرُ مستعمل
            raise NotImplementedError

        async def embed(self, texts):  # pragma: no cover
            raise NotImplementedError

        async def moderate(self, text):  # pragma: no cover
            raise NotImplementedError

    orchestrator = Orchestrator()
    monkeypatch.setattr(orchestrator._gateway, "_provider", _Timeout())  # noqa: SLF001

    before_runs = await _rows(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})
    with pytest.raises(Exception):
        await orchestrator.run_agent_detached(
            maker, tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
            agent_key="research_manager", question="سؤالٌ بحثيٌّ كافي الطول.",
            tool_calls=[], before_provider_call=boundary)

    assert calls["n"] == 1, f"نُودي المزوّدُ {calls['n']} مرّةً"
    assert boundary.crossed is True, "لم يُسجَّل عبورُ الحدّ"

    # ── الجيلُ غامضٌ لا مُخفِق ──
    state, code, body, _f = await _record(slot["tenant_id"], key)
    assert state == "in_progress", state
    assert code is None
    assert idem.EXTERNAL_MARKER in (body or {}), body

    # ── ولا تشغيلةَ تقول «أخفق» ──
    after_runs = await _rows(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})
    assert after_runs == before_runs, \
        f"كُتب صفُّ تشغيلةٍ لأثرٍ لا يُعرف: {before_runs} → {after_runs}"
    failed = await _rows(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = :t AND status = 'failed'"
        "   AND error LIKE '%Timeout%'", {"t": str(slot["tenant_id"])})
    assert failed == [(0,)], f"تشغيلةٌ وُسمت «أخفق» لمهلةٍ غامضة: {failed}"

    # ── وسجلُّ النموذجِ يقول الحقّ ──
    model_runs = await _rows(
        "SELECT status FROM model_runs WHERE tenant_id = :t"
        " ORDER BY created_at DESC LIMIT 1", {"t": str(slot["tenant_id"])})
    assert model_runs and model_runs[0][0] == "ambiguous", \
        f"سجلُّ النموذجِ لا يقول «ambiguous»: {model_runs}"

    # ── وبعد انقضاء الإجارة: لا نداءَ ثانيًا ──
    await _expire_lease(slot["tenant_id"], key)
    after = await _claim(slot, key)
    assert isinstance(after, idem.ExternalUnknown), after
    assert calls["n"] == 1, "نُودي المزوّدُ ثانيةً"


@requires_db
async def test_17_a_pre_boundary_rejection_keeps_the_key_retryable(
    two_tenants, monkeypatch,
):
    """رفضٌ **قبل** الحدّ (تفويضُ التصنيف) ⇒ لا وسمَ، والمفتاحُ يُعاد.

    ويُقاس أنّ المزوّدَ لم يُنادَ قطّ — فالدعوى ليست «لا نعرف»، بل «لم يقع».
    """
    from athera_api.brain.orchestrator import Orchestrator
    from athera_api.db import tenant_session
    from athera_api.services import idempotency as idem

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    maker = lambda: tenant_session(slot["tenant_id"], slot["user_id"])  # noqa: E731

    lease = await _claim(slot, key)
    assert isinstance(lease, idem.Lease)
    guard = idem.LeaseGuard(lease=lease, operation=OPERATION)
    boundary = idem.ModelBoundary(maker, guard, provider="fake",
                                  capability=idem_unproven())

    calls = {"n": 0}
    orchestrator = Orchestrator()

    def _refuse(request, grant=None):
        raise AssertionError("classification refused before any provider call")

    monkeypatch.setattr(orchestrator._gateway, "authorize", _refuse)  # noqa: SLF001

    class _Counting:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            raise AssertionError("must never be reached")

    monkeypatch.setattr(orchestrator._gateway, "_provider", _Counting())  # noqa: SLF001

    with pytest.raises(Exception):
        await orchestrator.run_agent_detached(
            maker, tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
            agent_key="research_manager", question="سؤالٌ بحثيٌّ كافي الطول.",
            tool_calls=[], before_provider_call=boundary)

    assert calls["n"] == 0, "نُودي المزوّدُ رغم رفضٍ محليّ"
    assert boundary.crossed is False, "وُسم عبورُ حدٍّ لم يُعبَر"
    state, _c, body, _f = await _record(slot["tenant_id"], key)
    assert idem.EXTERNAL_MARKER not in (body or {}), \
        "وُسم غامضًا ما رُدّ قبل الحدّ — فيُحرَم صاحبُه إعادةً مشروعة"

    # ويُغلَق إخفاقًا معلومًا، فيُعاد المفتاحُ بأمان.
    await idem.close_pre_external(maker, guard, reason="pre_external:test")
    again = await _claim(slot, key)
    assert isinstance(again, idem.Lease), f"سُمِّم مفتاحٌ رُدّ قبل الحدّ: {again}"


# ═════════ ٥ · حارسُ المسالك الطرفيّة ═════════


def test_18_no_keyed_terminal_branch_forgets_its_generation() -> None:
    """**كلُّ مسلكٍ طرفيٍّ بعد الحجز ينتهي إلى حالٍ معلومة.**

    فمن حجز جيلًا ثمّ عاد أو رفع بلا إتمامٍ ولا إغلاقٍ ولا وسمٍ يترك صفًّا
    `in_progress` عالقًا: يُردّ صاحبُه ٤٠٩ إلى أن تنقضي الإجارةُ على عملٍ
    لم يُنفَّذ ولا يُعرف.

    ولا يُقاس بمطابقةِ نصّ: تُحدَّد الدالّاتُ التي **تحجز** (نداءٌ إلى
    `begin_leased_in` أو `begin_model`)، ثمّ يُشترط أن تذكر كلٌّ منها
    الثلاثيَّ الذي يُغلق الجيل — إتمامًا أو إغلاقًا قبل الحدِّ أو وسمَ
    حدٍّ عبَر. وغيابُ الثلاثةِ جميعًا هو النسيان.
    """
    import ast
    import pathlib

    # **ولا يكفي حضورُ أحدِها.** وأوّلُ صيغةٍ قبلت أيَّ واحدٍ من الأربعة،
    # فمرّ عليها حذفُ `close_pre_external` من `brain.ask` لأنّ
    # `ModelBoundary` باقٍ. فالشرطُ الآن: **الإتمامُ لازمٌ لكلّ حاجز**،
    # ومَن يستعمل مُعلَّقَ الحدّ يلزمه **إغلاقٌ قبل الحدّ** أيضًا.
    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    # **ووحدةُ الأوّليّات نفسُها مستثناة**: `begin_leased` تفوّض إلى
    # `begin_leased_in` ولا تملك مسلكًا طرفيًّا — والمقصودُ مُستهلكوها.
    primitives = {"idempotency.py"}
    forgetful: list[str] = []
    reserving: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name in primitives:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = {ast.unparse(n.func).split(".")[-1]
                     for n in ast.walk(fn) if isinstance(n, ast.Call)}
            if not calls & {"begin_leased_in", "begin_model"}:
                continue
            reserving.append(f"{path.name}::{fn.name}")
            if "settle_leased" not in calls:
                forgetful.append(f"{path.name}::{fn.name} (no settle)")
            if "ModelBoundary" in calls and "close_pre_external" not in calls:
                forgetful.append(f"{path.name}::{fn.name} (no pre-external close)")

    assert reserving, "لم يُعثر على دالّةٍ تحجز — فالحارسُ لا يحرس شيئًا"
    assert forgetful == [], (
        "دالّةٌ تحجز جيلًا ولا تُغلقه في أيّ مسلك: " + ", ".join(forgetful))


def test_19_the_terminal_guard_bites_a_forgotten_branch() -> None:
    """والحارسُ يعضّ نصًّا يحجز ولا يُغلق — وحارسٌ لا يعضّ ليس حارسًا."""
    import ast

    def _forgetful(source: str) -> list[str]:
        found = []
        for fn in ast.walk(ast.parse(source)):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = {ast.unparse(n.func).split(".")[-1]
                     for n in ast.walk(fn) if isinstance(n, ast.Call)}
            if not calls & {"begin_leased_in", "begin_model"}:
                continue
            if "settle_leased" not in calls:
                found.append(fn.name)
            elif "ModelBoundary" in calls and "close_pre_external" not in calls:
                found.append(fn.name)
        return found

    forgotten = (
        "async def handler(request, principal):\n"
        "    async with maker() as session:\n"
        "        guard = await idempotency.begin_leased_in(session, request)\n"
        "    if not ready:\n"
        "        return Disabled()\n"      # ← جيلٌ مُودَعٌ ولا إتمام
        "    return Ok()\n"
    )
    assert _forgetful(forgotten) == ["handler"], "الحارسُ لم يعضّ النسيان"

    closed = (
        "async def handler(request, principal):\n"
        "    async with maker() as session:\n"
        "        guard = await idempotency.begin_leased_in(session, request)\n"
        "        await idempotency.settle_leased(session, guard, status=200, body={})\n"
        "    return Ok()\n"
    )
    assert _forgetful(closed) == [], "الحارسُ اتّهم مسلكًا مُغلَقًا"


def test_20_every_authorized_b4_flow_passes_the_boundary_hook() -> None:
    """الستّةُ كلُّها تُمرّر مُعلَّقَ الحدّ — **ولا نداءَ نموذجٍ بلا وسم**.

    ومسارُ معالجةِ الرسالة (`document_intelligence`) مستثنًى صريحًا: موعدُه
    الطور B-5، ولا يُقحَم هنا.
    """
    import ast
    import pathlib

    ENTRIES = {"run_agent_detached", "run_structured_detached", "ModelExtractor"}
    OUT_OF_SCOPE = {"document_intelligence.py"}
    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    unhooked: list[str] = []
    seen = 0
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if ast.unparse(node.func).split(".")[-1] not in ENTRIES:
                continue
            seen += 1
            if path.name in OUT_OF_SCOPE:
                continue
            if "before_provider_call" not in {k.arg for k in node.keywords}:
                unhooked.append(f"{path.name}:{node.lineno}")
    assert seen >= 7, f"لم تُحصَ منافذُ النموذج ({seen}) — يُراجَع المسح"
    assert unhooked == [], f"نداءُ نموذجٍ بلا مُعلَّقِ حدّ: {unhooked}"

    # ولا يكفي أن تكون المنافذُ الثلاثةُ موسومة: للمنسّقِ صِنفان آخران
    # يصلان إلى المزوّدِ ولا يقبلان مُعلَّقًا — `run_agent` و`run_structured`.
    # فمسلكٌ من الستّةِ لو تحوّل إليهما عبَر الحدَّ بلا وسمٍ، وبقي هذا
    # الفحصُ أخضرَ. فيُمنع ذلك صراحةً — على الستّةِ وحدها، فـ B-5 حرٌّ بعد.
    HOOKLESS = {"run_agent", "run_structured"}
    AUTHORIZED = {
        "ai.py", "brain.py", "manuscript_drafting.py", "planning.py",
        "profile.py", "journey.py",
    }
    escapes: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name not in AUTHORIZED:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and \
                    ast.unparse(node.func).split(".")[-1] in HOOKLESS:
                escapes.append(f"{path.name}:{node.lineno}")
    assert escapes == [], \
        f"مسلكٌ مأذونٌ يصل إلى المزوّدِ بصنفٍ لا يقبل مُعلَّقَ الحدّ: {escapes}"


def _activate(monkeypatch, provider):
    """يُفعّل مزوّدًا وهميًّا **وجهوزيّتَه** — وإلّا سلك المسارُ فرعَ التعطيل.

    فـ`provider_readiness` تقرأ الإعدادَ ووجودَ الحزمة، لا `build_provider`.
    ويُعاد استعمالُ نهجِ `test_at_s5b_ai_activation` نفسِه بلا مفتاحٍ حقيقيّ.
    """
    import importlib.util

    from athera_api.config import get_settings
    from athera_api.providers import gateway as gateway_module

    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only-not-a-real-key",
                        raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(gateway_module, "build_provider", lambda: provider)
    return provider


# ═════════ ٦ · المسالكُ الطرفيّةُ في المنتج، لا في النصّ وحده ═════════


@requires_db
async def test_21_a_disabled_provider_settles_its_generation(two_tenants, monkeypatch):
    """مزوّدٌ غيرُ مضبوط **بعد** الحجز: الجوابُ يُثبَّت ولا يُترك الجيلُ عالقًا.

    وهذا مسلكٌ طرفيٌّ بين الحجزِ والنموذج، وكان يُترك `in_progress` بلا
    وسمٍ ولا إتمام — فيُردّ صاحبُه ٤٠٩ على عملٍ لم يُنفَّذ ولا غموضَ فيه.
    """
    from athera_api.routers import ai as ai_router
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    monkeypatch.setattr(ai_router, "provider_readiness",
                        lambda: ("null", False, "no provider configured"))

    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}
    async with _client(slot) as http:
        first = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "disabled", first.json()["status"]

        state, code, marker, _f = await _record(slot["tenant_id"], key)
        assert state == "completed", f"الجيلُ بقي عالقًا: {state}"
        assert code == 200

        replay = await http.post("/api/v1/ai/ask", json=body,
                                 headers={"Idempotency-Key": key})
    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json() == first.json(), "الإعادةُ ليست الجوابَ الأصل"


@requires_db
async def test_22_a_keyed_ai_ask_replays_without_a_second_model_call(
    two_tenants, monkeypatch,
):
    """`/ai/ask` المُمفتَح: نجاحٌ ثمّ إعادةٌ بصفرِ نداءٍ وصفرِ تشغيلةٍ ثانية."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    calls = {"n": 0}

    class _Fake:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            from athera_api.providers.base import ModelResponse, ModelUsage

            return ModelResponse(
                content="", provider="fake", model="m",
                usage=ModelUsage(input_tokens=1, output_tokens=1, cost_usd=0.0,
                                 latency_ms=1),
                structured={"answer_ar": "جوابٌ مقترَح", "answer_en": "A proposal",
                            "citations": [], "unsupported_claims": [],
                            "evidence_gaps": []})

    _activate(monkeypatch, _Fake())
    key = uuid.uuid4().hex
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    before_runs = await _rows(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})
    async with _client(slot) as http:
        first = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text
        after_first = calls["n"]
        runs_after_first = await _rows(
            "SELECT count(*) FROM agent_runs WHERE tenant_id = :t",
            {"t": str(slot["tenant_id"])})
        replay = await http.post("/api/v1/ai/ask", json=body,
                                 headers={"Idempotency-Key": key})
        conflict = await http.post("/api/v1/ai/ask",
                                   json={"question": "سؤالٌ آخرُ مختلفٌ تمامًا هنا."},
                                   headers={"Idempotency-Key": key})

    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json() == first.json()
    assert calls["n"] == after_first, "الإعادةُ نادت النموذج"
    assert await _rows("SELECT count(*) FROM agent_runs WHERE tenant_id = :t",
                       {"t": str(slot["tenant_id"])}) == runs_after_first, \
        "الإعادةُ أنشأت تشغيلةً ثانية"
    assert runs_after_first != before_runs, "لم تُسجَّل تشغيلةٌ للنجاح الأوّل"

    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["code"] == "idempotency.key_reused", conflict.text
    assert calls["n"] == after_first, "التعارضُ نادى النموذج"


@requires_db
async def test_23_a_keyed_ai_ask_timeout_is_ambiguous_and_never_recalled(
    two_tenants, monkeypatch,
):
    """`/ai/ask`: مهلةٌ بعد الحدّ ⇒ ٤٠٩ صادقة، وبعد الانقضاء لا نداءَ ثانيًا."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    slot = two_tenants["a"]
    calls = {"n": 0}

    class _Timeout:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            raise TimeoutError("provider timed out mid-generation")

    _activate(monkeypatch, _Timeout())
    key = uuid.uuid4().hex
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    async with _client(slot) as http:
        first = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
        assert first.status_code == 409, f"{first.status_code}: {first.text[:200]}"
        assert first.json()["error"]["code"] == "idempotency.external_result_unknown", \
            first.text
        assert calls["n"] == 1

        # قبل انقضاء الإجارة: «قائمٌ لغيرك» — ولا نداء.
        early = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
        assert early.status_code == 409, early.text
        assert early.json()["error"]["code"] == "idempotency.in_progress", early.text
        assert calls["n"] == 1

        await _expire_lease(slot["tenant_id"], key)
        after = await http.post("/api/v1/ai/ask", json=body,
                                headers={"Idempotency-Key": key})
    assert after.status_code == 409, after.text
    assert after.json()["error"]["code"] == "idempotency.external_result_unknown", \
        after.text
    assert calls["n"] == 1, f"نُودي النموذجُ {calls['n']} مرّةً لجيلٍ واحد"

    # ولا تشغيلةَ تقول «أخفق»، وسجلُّ النموذجِ يقول الحقّ.
    failed = await _rows(
        "SELECT count(*) FROM agent_runs WHERE tenant_id = :t AND status = 'failed'"
        "   AND error LIKE '%Timeout%'", {"t": str(slot["tenant_id"])})
    assert failed == [(0,)], f"تشغيلةٌ كاذبة: {failed}"
    ambiguous = await _rows(
        "SELECT count(*) FROM model_runs WHERE tenant_id = :t AND status = 'ambiguous'",
        {"t": str(slot["tenant_id"])})
    assert ambiguous == [(1,)], f"سجلُّ النموذجِ لا يقول «ambiguous»: {ambiguous}"


@requires_db
async def test_24_tenant_and_actor_isolation_on_ai_ask(two_tenants, monkeypatch):
    """مفتاحٌ واحدٌ عبر مستأجرَين وفاعلَين ⇒ أعمالٌ مستقلّة."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_rc_t1a_project_access import _second_user

    class _Fake:
        name = "fake"

        async def generate_structured(self, request):
            from athera_api.providers.base import ModelResponse, ModelUsage

            return ModelResponse(
                content="", provider="fake", model="m", usage=ModelUsage(),
                structured={"answer_ar": "جواب", "answer_en": "answer",
                            "citations": [], "unsupported_claims": [],
                            "evidence_gaps": []})

    _activate(monkeypatch, _Fake())
    key = uuid.uuid4().hex
    body = {"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."}

    async with _client(two_tenants["a"]) as http:
        mine = await http.post("/api/v1/ai/ask", json=body,
                               headers={"Idempotency-Key": key})
    async with _client(two_tenants["b"]) as http:
        theirs = await http.post("/api/v1/ai/ask", json=body,
                                 headers={"Idempotency-Key": key})
    assert mine.status_code == 200 and theirs.status_code == 200
    assert "Idempotency-Replayed" not in theirs.headers, "مفتاحٌ عبَر مستأجرًا"

    colleague = await _second_user(
        two_tenants["a"]["tenant_id"],
        email=f"h2b4-{uuid.uuid4().hex[:10]}@example.com")
    async with _client(colleague) as http:
        peer = await http.post("/api/v1/ai/ask", json=body,
                               headers={"Idempotency-Key": key})
    assert peer.status_code == 200, peer.text
    assert "Idempotency-Replayed" not in peer.headers, "مفتاحٌ عبَر فاعلًا"


@requires_db
async def test_25_the_raw_key_is_never_persisted_by_model_routes(
    two_tenants, monkeypatch,
):
    """الخامُ لا يُخزَّن: لا في الإجارة ولا التشغيلة ولا النموذج ولا التدقيق."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client

    class _Fake:
        name = "fake"

        async def generate_structured(self, request):
            from athera_api.providers.base import ModelResponse, ModelUsage

            return ModelResponse(
                content="", provider="fake", model="m", usage=ModelUsage(),
                structured={"answer_ar": "جواب", "answer_en": "answer",
                            "citations": [], "unsupported_claims": [],
                            "evidence_gaps": []})

    _activate(monkeypatch, _Fake())
    slot = two_tenants["a"]
    key = uuid.uuid4().hex
    async with _client(slot) as http:
        answered = await http.post(
            "/api/v1/ai/ask",
            json={"question": "سؤالٌ بحثيٌّ كافي الطول للفحص."},
            headers={"Idempotency-Key": key})
    assert answered.status_code == 200, answered.text

    like = f"%{key}%"
    for sql, label in (
        ("SELECT count(*) FROM idempotency_records WHERE tenant_id = :t"
         "   AND (key_digest = :raw OR response_body::text LIKE :like)", "الإجارة"),
        ("SELECT count(*) FROM agent_runs WHERE tenant_id = :t"
         "   AND (coalesce(error,'') LIKE :like"
         "        OR coalesce(input_summary::text,'') LIKE :like)", "التشغيلة"),
        ("SELECT count(*) FROM model_runs WHERE tenant_id = :t"
         "   AND coalesce(error,'') LIKE :like", "سجلّ النموذج"),
        ("SELECT count(*) FROM audit_events WHERE tenant_id = :t"
         "   AND (coalesce(state_after::text,'') LIKE :like"
         "        OR coalesce(reason,'') LIKE :like)", "التدقيق"),
    ):
        hits = await _rows(sql, {"t": str(slot["tenant_id"]), "raw": key,
                                 "like": like})
        assert hits == [(0,)], f"المفتاحُ الخامُ ظهر في {label}: {hits}"


# ═════════ ٧ · المسارات الأربعةُ الأخرى: أعدادُ المجال ═════════
#
# **والأعدادُ هي الدعوى.** «لا تكرار» تُقاس بعدِّ صفوفِ المجال قبل الإعادة
# وبعدها، لا بالثقة في مسلكٍ يبدو صحيحًا.


async def _count(sql: str, params: dict) -> int:
    rows = await _rows(sql, params)
    return int(rows[0][0]) if rows else 0


class _Structured:
    """مزوّدٌ يُعيد حِملًا بنيويًّا لأيّ عقد — ويَعُدّ نداءاته."""

    name = "fake"

    def __init__(self, payload: dict) -> None:
        self._payload = payload
        self.calls = 0

    async def generate_structured(self, request):
        from athera_api.providers.base import ModelResponse, ModelUsage

        self.calls += 1
        return ModelResponse(
            content="", provider="fake", model="m",
            usage=ModelUsage(input_tokens=1, output_tokens=1, cost_usd=0.0,
                             latency_ms=1),
            structured=self._payload)

    async def embed(self, texts, *, model=None):  # pragma: no cover
        return [[0.0] * 4 for _ in texts]

    async def stream(self, request):  # pragma: no cover
        yield ""


async def _grant_drafting(slot, manuscript_id, section_key: str = "method") -> None:
    """يمنح إذنَ الصياغة **على البصمة الحاضرة** — كما يفعل المنتج.

    فالإذنُ مربوطٌ بلقطةِ الدليل: إذنٌ على بصمةٍ أخرى ليس إذنًا.
    """
    from athera_api.db import tenant_session
    from athera_api.routers import manuscript_drafting as drafting
    from athera_api.services import consent
    from tests.test_at_s5e_b_methods_drafting import _principal

    principal = _principal(slot)
    tid, uid = slot["tenant_id"], slot["user_id"]
    async with tenant_session(tid, uid) as session:
        record = await drafting.manuscript_for_tenant_edit(
            session, principal, manuscript_id)
        context = await drafting._build_context(  # noqa: SLF001 — تجهيزةُ فحص
            session, principal, record, section_key)
        await consent.record_drafting_decision(
            session, tenant_id=tid, manuscript_id=manuscript_id,
            section_key=section_key, actor_user_id=uid, granted=True,
            provider="anthropic", model="m",
            context_fingerprint=context.fingerprint,
            evidence_count=len(context.items))


async def _grant_planning(slot, project_id) -> None:
    """يمنح إذنَ التخطيط على البصمة الحاضرة."""
    from athera_api.db import tenant_session
    from athera_api.services import consent
    from athera_api.services.planning import context as ctx
    from tests.test_at_s5e_b_methods_drafting import _principal

    tid, uid = slot["tenant_id"], slot["user_id"]
    async with tenant_session(tid, uid) as session:
        built = await ctx.build(session, tenant_id=tid, project_id=project_id,
                                capability=consent.PLANNING_CAPABILITY)
        await consent.record_planning_decision(
            session, tenant_id=tid, project_id=project_id, actor_user_id=uid,
            granted=True, provider="anthropic", model="m",
            context_fingerprint=built.fingerprint, evidence_count=len(built.items))
    assert _principal is not None  # الاستيرادُ يُثبّت وجودَ التجهيزة


@requires_db
async def test_26_manuscript_draft_replay_adds_no_domain_rows(
    two_tenants, monkeypatch,
):
    """`/…/draft`: إعادةٌ بصفرِ نداءٍ وصفرِ نسخةٍ وصفرِ قسمٍ وصفرِ تدقيق."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_s5e_b_methods_drafting import _seed_manuscript

    slot = two_tenants["a"]
    _project, manuscript_id, _sel = await _seed_manuscript(
        slot["tenant_id"], slot["user_id"])
    await _grant_drafting(slot, manuscript_id)
    # **وحمولةٌ تُرضي العقد**، من الحزمة القائمة لا من اختراع: حمولةٌ
    # مخالفةٌ للعقد تُرفَع **بعد** الحدّ، فيصير الفحصُ يقيس الغموضَ لا النجاح.
    from tests.test_at_s5e_b_methods_drafting import _draft_json

    draft_payload = _draft_json()
    draft_payload["claims"] = []
    provider = _activate(monkeypatch, _Structured(draft_payload))

    tid = str(slot["tenant_id"])
    key = uuid.uuid4().hex
    url = f"/api/v1/manuscripts/{manuscript_id}/sections/method/draft"

    async with _client(slot) as http:
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, f"{first.status_code}: {first.text[:300]}"
        after = provider.calls
        counts = {
            "versions": await _count(
                "SELECT count(*) FROM manuscript_versions WHERE tenant_id = :t", {"t": tid}),
            "sections": await _count(
                "SELECT count(*) FROM manuscript_sections WHERE tenant_id = :t", {"t": tid}),
            "audits": await _count(
                "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
                "   AND action = 'manuscript.section_drafted'", {"t": tid}),
            "runs": await _count(
                "SELECT count(*) FROM agent_runs WHERE tenant_id = :t", {"t": tid}),
        }
        replay = await http.post(url, headers={"Idempotency-Key": key})

    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json() == first.json(), "الإعادةُ ليست الجوابَ الأصل"
    assert provider.calls == after, "الإعادةُ نادت النموذج"
    for label, sql in (
        ("versions", "SELECT count(*) FROM manuscript_versions WHERE tenant_id = :t"),
        ("sections", "SELECT count(*) FROM manuscript_sections WHERE tenant_id = :t"),
        ("audits", "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
                   "   AND action = 'manuscript.section_drafted'"),
        ("runs", "SELECT count(*) FROM agent_runs WHERE tenant_id = :t"),
    ):
        assert await _count(sql, {"t": tid}) == counts[label], \
            f"الإعادةُ زادت {label}"


@requires_db
async def test_27_manuscript_draft_conflicts_when_the_snapshot_changes(
    two_tenants, monkeypatch,
):
    """بصمةُ سياقٍ أخرى بالمفتاح نفسِه ⇒ ٤٠٩ **قبل** أيّ نداءٍ ثانٍ."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_s5e_b_methods_drafting import _seed_manuscript

    slot = two_tenants["a"]
    _project, manuscript_id, _sel = await _seed_manuscript(
        slot["tenant_id"], slot["user_id"])
    await _grant_drafting(slot, manuscript_id)
    await _grant_drafting(slot, manuscript_id, "results")
    from tests.test_at_s5e_b_methods_drafting import _draft_json

    draft_payload = _draft_json()
    draft_payload["claims"] = []
    provider = _activate(monkeypatch, _Structured(draft_payload))
    key = uuid.uuid4().hex

    async with _client(slot) as http:
        first = await http.post(
            f"/api/v1/manuscripts/{manuscript_id}/sections/method/draft",
            headers={"Idempotency-Key": key})
        assert first.status_code == 200, first.text
        after = provider.calls
        # قسمٌ آخرُ بالمفتاح نفسِه ⇒ معنًى آخر ⇒ تعارض.
        other = await http.post(
            f"/api/v1/manuscripts/{manuscript_id}/sections/results/draft",
            headers={"Idempotency-Key": key})
    assert other.status_code == 409, f"{other.status_code}: {other.text[:200]}"
    assert other.json()["error"]["code"] == "idempotency.key_reused", other.text
    assert provider.calls == after, "التعارضُ نادى النموذج"


@requires_db
async def test_28_planning_creates_exactly_one_run_and_no_duplicates(
    two_tenants, monkeypatch,
):
    """`/publication-opportunities`: تشغيلةٌ واحدة، وإعادةٌ بصفرِ زيادة.

    **ولا `PlanningRun` قبل المزوّد للعملِ المُمفتَح** (الخيار أ): فحالُها
    مُقيَّدٌ بـ`CHECK` ولا يقول «لا يُعرف»، فتُفتح في معاملة النجاح وحدَها.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    slot = two_tenants["a"]
    project_id, _verified, _file = await _seed_project_with_memory(
        slot["tenant_id"], slot["user_id"])
    await _grant_planning(slot, project_id)
    provider = _activate(monkeypatch, _Structured({"opportunities": []}))
    tid = str(slot["tenant_id"])
    key = uuid.uuid4().hex
    url = f"/api/v1/projects/{project_id}/publication-opportunities"

    async with _client(slot) as http:
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, f"{first.status_code}: {first.text[:300]}"
        after = provider.calls
        runs = await _count(
            "SELECT count(*) FROM planning_runs WHERE tenant_id = :t", {"t": tid})
        opportunities = await _count(
            "SELECT count(*) FROM publication_opportunities WHERE tenant_id = :t",
            {"t": tid})
        audits = await _count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
            "   AND action = 'planning.opportunities_generated'", {"t": tid})
        replay = await http.post(url, headers={"Idempotency-Key": key})

    assert runs == 1, f"عددُ التشغيلات {runs} — والمطلوبُ واحدة"
    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert provider.calls == after, "الإعادةُ نادت النموذج"
    assert await _count("SELECT count(*) FROM planning_runs WHERE tenant_id = :t",
                        {"t": tid}) == runs, "الإعادةُ أنشأت تشغيلةً ثانية"
    assert await _count(
        "SELECT count(*) FROM publication_opportunities WHERE tenant_id = :t",
        {"t": tid}) == opportunities, "الإعادةُ أنشأت فرصًا مكرَّرة"
    assert await _count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
        "   AND action = 'planning.opportunities_generated'",
        {"t": tid}) == audits, "الإعادةُ دوّنت حدثًا ثانيًا"


@requires_db
async def test_29_a_planning_timeout_leaves_zero_planning_runs(
    two_tenants, monkeypatch,
):
    """مهلةٌ بعد الحدّ ⇒ **صفرُ تشغيلاتِ تخطيط**، ولا صفَّ «أخفق» كاذب.

    فالتشغيلةُ لا تُفتح قبل المزوّد للعملِ المُمفتَح، والغموضُ يحمله وسمُ
    الجيل الدائم.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    slot = two_tenants["a"]
    project_id, _verified, _file = await _seed_project_with_memory(
        slot["tenant_id"], slot["user_id"])

    class _Timeout:
        name = "fake"

        def __init__(self) -> None:
            self.calls = 0

        async def generate_structured(self, request):
            self.calls += 1
            raise TimeoutError("planning provider timed out")

    await _grant_planning(slot, project_id)
    provider = _activate(monkeypatch, _Timeout())
    tid = str(slot["tenant_id"])
    key = uuid.uuid4().hex
    url = f"/api/v1/projects/{project_id}/publication-opportunities"

    async with _client(slot) as http:
        answered = await http.post(url, headers={"Idempotency-Key": key})
        assert answered.status_code == 409, f"{answered.status_code}: {answered.text[:250]}"
        assert answered.json()["error"]["code"] == \
            "idempotency.external_result_unknown", answered.text
        assert provider.calls == 1

        assert await _count("SELECT count(*) FROM planning_runs WHERE tenant_id = :t",
                            {"t": tid}) == 0, "فُتحت تشغيلةُ تخطيطٍ لأثرٍ لا يُعرف"

        await _expire_lease(slot["tenant_id"], key)
        after = await http.post(url, headers={"Idempotency-Key": key})
    assert after.status_code == 409, after.text
    assert after.json()["error"]["code"] == "idempotency.external_result_unknown"
    assert provider.calls == 1, f"نُودي المزوّدُ {provider.calls} مرّةً"
    assert await _count("SELECT count(*) FROM planning_runs WHERE tenant_id = :t",
                        {"t": tid}) == 0
    # **ولا تشغيلةَ أجنتٍ شاردة**: لا `running` مُعلَّقةٌ إلى الأبد، ولا
    # «أخفق» كاذبةٌ — و`run_structured_detached` لا يفتح صفًّا قبل الشبكة.
    stranded = await _rows(
        "SELECT status, count(*) FROM agent_runs WHERE tenant_id = :t"
        " GROUP BY status", {"t": tid})
    assert stranded == [], f"صفوفُ تشغيلةٍ بعد مهلةٍ غامضة: {stranded}"
    ambiguous_models = await _count(
        "SELECT count(*) FROM model_runs WHERE tenant_id = :t"
        "   AND status = 'ambiguous'", {"t": tid})
    assert ambiguous_models == 1, \
        f"سجلُّ النموذجِ لا يقول «ambiguous» مرّةً واحدة: {ambiguous_models}"


def _local_storage_read(monkeypatch, data: bytes = b"") -> None:
    """يقرأ البايتات محلّيًّا بدل MinIO.

    **و`ingestion.load_object_bytes` تستورد `boto3` مباشرةً وتتجاهل
    `storage_provider`** — فلا يكفي ضبطُ المخزن في الذاكرة. وهو تفاوتٌ
    قائمٌ في طبقة التخزين، لا شأنَ له بالطور B-4، فلا يُصلَح هنا؛
    ويُزيَّف في الفحص كما تفعل حزمةُ H3-B.
    """
    from athera_api.services import ingestion

    document = data or (
        "مشكلة الدراسة: قياس أثر التعلّم المدمج.\n\n"
        "المنهج: تصميمٌ شبه تجريبيّ.\n\nالنتائج: فرقٌ لصالح التجريبيّة.\n"
    ).encode("utf-8")

    async def _read(_storage_key: str) -> bytes:
        return document

    monkeypatch.setattr(ingestion, "load_object_bytes", _read)


# ═════════ ٨ · استيرادُ المِلفّ: تفويضٌ وتجزئةٌ وأعدادٌ ═════════


@requires_db
async def test_30_profile_import_requires_current_file_authorization(
    two_tenants, monkeypatch,
):
    """**ومفتاحٌ قديمٌ لا يُستورد ملفَّ غيرك.**

    وكان المسارُ يستعلم بالمستأجر وحده، فزميلٌ بلا منحةٍ على الملفّ كان
    يستورده. فصار يُقرأ بالحارس المشترك الذي يفحص المنحة — **قبل** أيّ
    تحكيمِ مفتاح.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_rc_t1_h3b_remaining_external_waits import _make_file
    from tests.test_at_rc_t1a_project_access import _second_user

    _local_storage_read(monkeypatch)
    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    colleague = await _second_user(
        slot["tenant_id"], email=f"h2b4p-{uuid.uuid4().hex[:10]}@example.com")

    body = {"file_id": str(file_id), "extractor": "rules"}
    async with _client(colleague) as http:
        refused = await http.post("/api/v1/profile/import", json=body,
                                  headers={"Idempotency-Key": uuid.uuid4().hex})
    assert refused.status_code in (403, 404), \
        f"زميلٌ بلا منحةٍ استورد ملفَّ غيره: {refused.status_code}"

    # وصاحبُ الملفّ يستورده — فالرفضُ كان عن منحةٍ لا عن عطب.
    async with _client(slot) as http:
        allowed = await http.post("/api/v1/profile/import", json=body,
                                  headers={"Idempotency-Key": uuid.uuid4().hex})
    assert allowed.status_code == 202, allowed.text


@requires_db
async def test_31_profile_import_replay_adds_no_extraction_rows(
    two_tenants, monkeypatch,
):
    """إعادةٌ بصفرِ تشغيلةِ استخراجٍ وصفرِ مرشَّحٍ وصفرِ مِلفٍّ شخصيّ ثانٍ."""
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_rc_t1_h3b_remaining_external_waits import _make_file

    _local_storage_read(monkeypatch)
    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    tid = str(slot["tenant_id"])
    key = uuid.uuid4().hex
    body = {"file_id": str(file_id), "extractor": "rules"}

    async with _client(slot) as http:
        first = await http.post("/api/v1/profile/import", json=body,
                                headers={"Idempotency-Key": key})
        assert first.status_code == 202, first.text
        runs = await _count(
            "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t", {"t": tid})
        candidates = await _count(
            "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t", {"t": tid})
        profiles = await _count(
            "SELECT count(*) FROM researcher_profiles WHERE tenant_id = :t", {"t": tid})
        replay = await http.post("/api/v1/profile/import", json=body,
                                 headers={"Idempotency-Key": key})

    assert replay.status_code == 202, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json() == first.json(), "الإعادةُ ليست الجوابَ الأصل"
    assert runs == 1, f"عددُ تشغيلات الاستخراج {runs}"
    assert await _count(
        "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t",
        {"t": tid}) == runs, "الإعادةُ أنشأت تشغيلةَ استخراجٍ ثانية"
    assert await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t",
        {"t": tid}) == candidates, "الإعادةُ أنشأت مرشَّحاتٍ مكرَّرة"
    assert await _count(
        "SELECT count(*) FROM researcher_profiles WHERE tenant_id = :t",
        {"t": tid}) == profiles, "الإعادةُ أنشأت مِلفًّا شخصيًّا ثانيًا"


@requires_db
async def test_32_a_changed_source_checksum_conflicts(two_tenants, monkeypatch):
    """تجزئةٌ تغيّرت تحت المفتاح نفسِه ⇒ ٤٠٩، وصفرُ كتابةٍ ثانية.

    فالتجزئةُ **هُويّةُ المصدر**: محتوًى آخرُ طلبٌ آخرُ في معناه.
    """
    from sqlalchemy import text

    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_rc_t1_h3b_remaining_external_waits import _make_file

    _local_storage_read(monkeypatch)
    _local_storage_read(monkeypatch)
    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    tid = str(slot["tenant_id"])
    key = uuid.uuid4().hex
    body = {"file_id": str(file_id), "extractor": "rules"}

    async with _client(slot) as http:
        first = await http.post("/api/v1/profile/import", json=body,
                                headers={"Idempotency-Key": key})
        assert first.status_code == 202, first.text
        runs = await _count(
            "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t", {"t": tid})

        engine, factory = await _observer()
        try:
            async with factory() as session:
                await session.execute(
                    text("UPDATE files SET checksum_sha256 = :c WHERE id = :i"),
                    {"c": "9" * 64, "i": str(file_id)})
                await session.commit()
        finally:
            await engine.dispose()

        changed = await http.post("/api/v1/profile/import", json=body,
                                  headers={"Idempotency-Key": key})
    assert changed.status_code == 409, f"{changed.status_code}: {changed.text[:200]}"
    assert changed.json()["error"]["code"] == "idempotency.key_reused", changed.text
    assert await _count(
        "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t",
        {"t": tid}) == runs, "التعارضُ كتب استخراجًا"


# ═════════ ٩ · تركيبُ البصمة: لقطةٌ علميّةٌ لا زمنٌ ولا معرّفُ طلب ═════════


def test_33_each_model_route_fingerprints_its_scientific_snapshot() -> None:
    """**ما يحدّد مخرَجَ النموذج يدخل البصمة** — وإلّا أُعيد جوابُ لقطةٍ أخرى.

    ويُقاس بالبنية: يُقرأ قاموسُ `body=` المُمرَّر إلى الحجز في كلّ مسار،
    وتُطلَب مفاتيحُه اللازمة. فحذفُ بصمةِ السياق أو معرّفِ النسخة أو
    تجزئةِ المصدر يُسقِط هذا الفحصَ فورًا.

    **ولا زمنَ ولا معرّفَ طلبٍ ولا مفتاحٌ خامّ** في أيٍّ منها.
    """
    import ast
    import pathlib

    REQUIRED = {
        "ai.py": {"question", "project_id", "locale"},
        "brain.py": {"question", "agent_key", "locale"},
        "manuscript_drafting.py": {"manuscript_id", "section_key", "version_id",
                                    "context_fingerprint", "language"},
        "planning.py": {"project_id", "context_fingerprint", "locale"},
        "thesis.py": {"thesis_id", "opportunity_id", "project_id", "file_id"},
        "profile.py": {"file_id", "extractor", "checksum_sha256"},
    }
    FORBIDDEN = {"request_id", "timestamp", "now", "created_at",
                 "idempotency_key", "key"}

    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"
    seen: dict[str, set[str]] = {}
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if ast.unparse(node.func).split(".")[-1] not in {"begin_leased_in",
                                                              "begin_model"}:
                continue
            for kw in node.keywords:
                if kw.arg != "body" or not isinstance(kw.value, ast.Dict):
                    continue
                keys = {k.value for k in kw.value.keys
                        if isinstance(k, ast.Constant)}
                seen.setdefault(path.name, set()).update(keys)

    for name, required in REQUIRED.items():
        assert name in seen, f"لم يُعثر على بصمةِ حجزٍ في {name}"
        missing = required - seen[name]
        assert not missing, f"{name}: مفاتيحٌ لازمةٌ غائبةٌ من البصمة: {sorted(missing)}"
        leaked = seen[name] & FORBIDDEN
        assert not leaked, f"{name}: البصمةُ تحمل ما لا يُبصَم: {sorted(leaked)}"


# ═════════ ١٠ · خيطُ الرسالة، ومستأجرُ البحثِ النافذ ═════════


@requires_db
async def test_34_an_existing_thread_settles_without_a_model_call(
    two_tenants, monkeypatch,
):
    """خيطٌ قائمٌ: `reused=True` **بصفرِ نداءٍ**، والجيلُ يُتمّ ولا يُترك.

    وإعادةٌ بعده تُعيد الجوابَ نفسَه، **ولا عقدةَ ثانيةً تُدرَج**.
    """
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import ThreadElement
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client
    from tests.test_at_thesis_journey_build import _seed_thesis_and_opportunity

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, opportunity_id = await _seed_thesis_and_opportunity(tid, uid)

    # يُبنى مشروعٌ وعقدةٌ قائمة، فيسلك المسارُ الطريقَ السريع.
    #
    # ويُقرأ المشروعُ من صفّ الفرصة مباشرةً: حرّاسُ التفويض تُفحص في
    # المسار نفسِه، وتجهيزةُ الفحص لا تحتاج أن تمرّ بها.
    from sqlalchemy import select

    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.thesis import PublicationOpportunity

    async with tenant_session(tid, uid) as session:
        opportunity = (await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_id))).scalar_one()
        project_id = opportunity.project_id or opportunity.converted_project_id
        if project_id is None:
            # **والخيطُ يُعلَّق بمشروعٍ قائم** — فيُنشأ هنا بدل تخطّي الفحص.
            project = ResearchProject(tenant_id=tid,
                                      working_title_ar="مشروعُ خيطٍ للفحص")
            session.add(project)
            await session.flush()
            project_id = project.id
            opportunity.project_id = project_id
        # **ومنحةُ الملفّ تُدسّ كما يفعل الرفعُ الحقيقيّ**: تجهيزةُ
        # `seed_file` تُنشئ صفًّا بلا منحة، والمسارُ يشترط الكتابةَ عليه.
        from athera_api.models.identity import ObjectGrant
        from athera_api.models.thesis import Thesis

        thesis_row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        if thesis_row.file_id is not None:
            session.add(ObjectGrant(
                tenant_id=tid, object_type="file", object_id=thesis_row.file_id,
                user_id=uid, grant_level="owner", granted_by=uid))

        # و`element_type` مُقيَّدٌ بـ`CHECK` على قائمةٍ مُعلَنة — و«claim»
        # ليست منها. فتُستعمل قيمةٌ مشروعة.
        session.add(ThreadElement(
            tenant_id=tid, project_id=project_id, element_type="problem",
            label_ar="عقدةٌ قائمة", ordinal=1, metadata_json={"evidence_refs": []}))

    calls = {"n": 0}

    class _NeverCalled:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            raise AssertionError("must not be reached when a thread exists")

    _activate(monkeypatch, _NeverCalled())
    key = uuid.uuid4().hex
    url = f"/api/v1/theses/{thesis_id}/opportunities/{opportunity_id}/thread"

    async with _client(slot) as http:
        first = await http.post(url, headers={"Idempotency-Key": key})
        assert first.status_code == 200, f"{first.status_code}: {first.text[:250]}"
        assert first.json()["reused"] is True, first.json()
        assert calls["n"] == 0, "نُودي النموذجُ وخيطٌ قائم"

        state, code, _b, _f = await _record(tid, key)
        assert state == "completed", f"الجيلُ بقي عالقًا على المسلك السريع: {state}"

        elements = await _count(
            "SELECT count(*) FROM thread_elements WHERE tenant_id = :t",
            {"t": str(tid)})
        replay = await http.post(url, headers={"Idempotency-Key": key})

    assert replay.status_code == 200, replay.text
    assert replay.headers.get("Idempotency-Replayed") == "true"
    assert replay.json() == first.json()
    assert calls["n"] == 0
    assert await _count(
        "SELECT count(*) FROM thread_elements WHERE tenant_id = :t",
        {"t": str(tid)}) == elements, "الإعادةُ أدرجت عقدةً ثانية"
    assert code == 200


def test_35_planning_scopes_its_generation_to_the_project_tenant() -> None:
    """**مستأجرُ البحثِ النافذُ لا مستأجرُ الرمز** — ويُثبَّت مصدرُه بنيويًّا.

    فهذا المسارُ وحدَه يعمل على بحثٍ قد يكون مستأجرُه غيرَ مستأجرِ الرمز
    (جسرُ التعاون، والجلسةُ `project_session`). فحجزٌ بمستأجر الرمز يضع
    صفَّ الجيل في مستأجرٍ آخر: فتُعاد أجوبةٌ عبر الحدّ، أو لا تُعاد حيث
    يجب — وهو عطبُ عزلٍ لا عطبُ راحة.

    **ويُقاس مصدرُ القيمة لا اسمُها**: يُشترط أنّ `tenant_id` المُمرَّرَ
    إلى الحجز هو المُسنَدُ من `project_tenant(...)`، وأنّ
    `principal.tenant_id` لا يُمرَّر إليه.

    (والبرهانُ الزمنيُّ عبر جسرٍ حقيقيٍّ يبقى على تجهيزات التعاون القائمة
    في `test_at_rc_t1a_project_access` و`test_at_sec_p0_tenant_isolation`؛
    وهذا الحارسُ يُثبّت الموضعَ الذي يُخطئ فيه التعديل.)
    """
    import ast
    import inspect
    import textwrap

    from athera_api.routers import planning

    src = textwrap.dedent(inspect.getsource(planning.generate_opportunities_body))
    fn = ast.parse(src).body[0]

    # (أ) `tenant_id` يُسنَد من `project_tenant(...)` في هذا المتن.
    assigned_from_project_tenant = any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "tenant_id" for t in node.targets)
        and "project_tenant" in ast.unparse(node.value)
        for node in ast.walk(fn))
    assert assigned_from_project_tenant, \
        "`tenant_id` لم يُسنَد من `project_tenant(...)` في متن التوليد"

    # (ب) والحجزُ يُمرَّر ذاك المتغيّرَ، لا مستأجرَ الرمز.
    checked = 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if ast.unparse(node.func).split(".")[-1] not in {"begin_leased_in",
                                                          "begin_model"}:
            continue
        passed = {k.arg: ast.unparse(k.value) for k in node.keywords}
        assert passed.get("tenant_id") == "tenant_id", (
            "الحجزُ يُمرَّر مستأجرًا غيرَ مستأجر البحث النافذ: "
            f"{passed.get('tenant_id')!r}")
        assert passed.get("tenant_id") != "principal.tenant_id"
        checked += 1
    assert checked == 1, f"عددُ مواضعِ الحجز في المتن {checked}"

def test_36_every_generation_lifecycle_code_speaks_both_languages() -> None:
    """ورموزُ دورةِ الجيلِ كلُّها لها نصٌّ بالعربيّةِ والإنجليزيّة.

    و`translate` تُعيد المفتاحَ نفسَه إن غاب النصُّ — فرمزٌ بلا مدخلٍ يظهر
    للباحثِ حروفًا خامًّا مثل `ingestion.source_changed`. وقد وقع ذلك
    فعلًا في هذا الطور: رمزُ تبدُّلِ المصدرِ رُفع بلا نصّ، ورمزُ تبدُّلِ
    أدلّةِ التخطيطِ كان بلا نصٍّ ثمّ صار يُرفع في موضعٍ ثانٍ.

    والعائلةُ مُثبَّتة: فرمزٌ جديدٌ في دورةِ الجيلِ يُراجَع ولا يُشحن صامتًا.
    """
    from athera_api.i18n.catalog import CATALOG, translate

    FAMILY = (
        "idempotency.external_result_unknown",
        "idempotency.in_progress",
        "idempotency.key_invalid",
        "idempotency.key_reused",
        "idempotency.lease_superseded",
        "drafting.context_changed",
        "planning.context_changed",
        "ingestion.source_changed",
        "file.upload_not_pending",
    )
    missing = [code for code in FAMILY
               if set(CATALOG.get(code, {})) < {"ar", "en"}]
    assert missing == [], f"رمزٌ بلا نصٍّ في لغةٍ: {missing}"

    # ولا يكفي وجودُ المفتاح: النصُّ يجب أن يكون نصًّا لا صدى للرمز.
    echoes = [code for code in FAMILY
              for locale in ("ar", "en")
              if translate(code, locale).strip() in (code, "")]
    assert echoes == [], f"نصٌّ يُعيد الرمزَ نفسَه: {echoes}"

    # ورسالةُ الغموضِ لا تقول «أخفق» ولا «لم يُنفَّذ» ولا «نُعيد المحاولة».
    unknown_en = translate("idempotency.external_result_unknown", "en").lower()
    for forbidden in ("failed", "did not run", "was not executed",
                      "retrying automatically"):
        assert forbidden not in unknown_en, forbidden
