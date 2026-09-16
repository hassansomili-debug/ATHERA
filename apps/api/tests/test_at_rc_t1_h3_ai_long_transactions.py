"""RC-T1-H3 — **لا معاملةَ قاعدةٍ تُمسَك عبر انتظارٍ خارجيّ**.

## العطب

`POST /api/v1/ai/ask` و`POST /api/v1/brain/ask` كانا يأخذان
`Depends(get_session)` — أي معاملةَ الطلب — ثمّ ينتظران:

  • نداءَ النموذج عبر `Orchestrator.run_agent(session, …)`
  • واكتشافَ المراجع من Crossref/OpenAlex (`ai.ask` وحده)

والمعاملةُ حيّةٌ طوالَ الانتظار، فالاتصالُ يبقى `idle in transaction`
دقائقَ إن لزم. وهو شكلُ الحادثة المسجَّلة في `fly.toml`: اتصالٌ عَلِق
٢٥٤ ثانية، «فيُمسَك قفلُ سلسلةِ التدقيق للمستأجر، وتقف كتاباتُه خلفه».

## ولمَ الدعوى مقيسةٌ على PostgreSQL نفسِها

الانتظارُ يُصنع بمزوّدٍ وهميٍّ محكوم — وهذا مسموح. أمّا **حدُّ المعاملة
فلا يُزيَّف**: يُلتقط معرّفُ الخادم الخلفيّ (`pg_backend_pid`) لكلّ اتصالٍ
يسحبه التطبيقُ من مجمّعه، ثمّ يُسأل `pg_stat_activity` **من اتصالٍ آخر**
عن حال تلك الخوادم أثناء حبس المزوّد. فما يُقاس هو ما تقوله القاعدة:

    state = 'idle in transaction'   →  معاملةٌ مفتوحةٌ بلا عمل
    xact_start IS NOT NULL          →  ومتى بدأت

**والشاهدُ هو حالُ القاعدة لا عدَّادُ مجمَّع.** ومحرّكُ الاختبارات
`NullPool` (`conftest` يستبدل `db.engine`)، فلا `checkedout()` فيه أصلًا —
وذاك أصلحُ: الاتصالُ المحبوسُ **هو** خادمٌ خلفيٌّ يُمسك معاملة، فتُعَدّ
الخوادمُ لا خاناتُ المجمَّع.

## ما تُثبته هذه الرقعة

  ١ أنّ عملَ القاعدة قد وقع فعلًا قبل الانتظار (فالقياسُ ليس على مسارٍ فارغ).
  ٢ وأنّ الانتظارَ الخارجيَّ يقع **بلا معاملةٍ مفتوحة**.
  ٣ ولا اتصالَ محبوسٌ بسبب الانتظار.
  ٤ وطلباتٌ بطيئةٌ متزامنةٌ لا تحبس اتصالًا لكلٍّ منها.
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

pytestmark = pytest.mark.asyncio

AI_ASK = "/api/v1/ai/ask"
BRAIN_ASK = "/api/v1/brain/ask"

#: سؤالٌ طويلٌ كافٍ ليمرّ تحقّقَ المخطَّط، وبلا نيّةِ بحثٍ في الأدبيات.
QUESTION = "أريد تصميمَ دراسةٍ عن أثر التعلّم المدمج في التحصيل الدراسيّ."


# ═══════════════════════ مزوّدٌ يُحبَس عند الطلب ═══════════════════════


class BarrierProvider:
    """مزوّدٌ بواجهة `ModelProvider` يقف عند حاجزٍ يفتحه الفحص.

    **والحبسُ هو المقصود**: هو ما يجعل «الانتظار الخارجيّ» قابلًا للقياس
    بلا شبكةٍ حقيقيّةٍ ولا زمنٍ مُقدَّر. وما لا يُزيَّف هو حدُّ المعاملة:
    القاعدةُ تُسأل عن حالها بنفسها.
    """

    name = "barrier"

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.seen: list = []

    async def generate_structured(self, request):
        from athera_api.providers.base import ModelResponse, ModelUsage

        self.calls += 1
        self.seen.append(request)
        self.entered.set()
        await self.release.wait()
        return ModelResponse(
            content="جوابٌ محكوم.", provider=self.name, model="barrier-1",
            structured={"answer_ar": "جوابٌ محكوم.", "citations": [],
                        "unsupported_claims": [], "evidence_gaps": []},
            usage=ModelUsage(input_tokens=10, output_tokens=10, latency_ms=1),
        )

    async def embed(self, texts, *, model=None):
        return [[0.0] * 4 for _ in texts]

    async def stream(self, request):
        yield "جوابٌ محكوم."

    async def tool_call(self, request):
        return await self.generate_structured(request)


class FailingProvider(BarrierProvider):
    """مزوّدٌ يرفع بعد الحبس — لفحص أنّ الإخفاق لا يُبقي معاملة."""

    name = "barrier-fail"

    async def generate_structured(self, request):
        self.calls += 1
        self.entered.set()
        await self.release.wait()
        raise RuntimeError("barrier provider refused on purpose")


def _allow_c2(monkeypatch):
    """يرفع سقفَ الإرسال إلى C2 **في الفحص وحده** — ولا يمسّ سياسةَ المنتج.

    ولمَ يلزم: `brain.ask` يستدعي `memory.search_verified` وتصنيفُ مخرَجها
    C2، والسقفُ العامّ C1 — فمزوّدٌ خارجيٌّ يُرَدّ بـ٤٠٣
    `provider.disabled_for_classification` **قبل أن تُنادى الشبكة**. وهذا
    سلوكُ منتجٍ صحيحٌ قائم، لا عطب؛ لكنّه يمنع قياسَ حدِّ المعاملة لأنّ
    الانتظارَ لا يقع أصلًا. فيُرفع السقفُ لهذا الفحص ليُقاس ما يُقاس.
    """
    from athera_api.config import get_settings

    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)


def _use_provider(monkeypatch, provider):
    """يُفعّل المزوّد بلا مفتاحٍ حقيقيّ ولا حزمةٍ مثبَّتة — نمطُ S5B نفسُه."""
    import importlib.util

    from athera_api.config import get_settings
    from athera_api.providers import gateway

    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only-not-a-real-key",
                        raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(gateway, "build_provider", lambda: provider)
    return provider


# ═════════════════ القياس: ما تقوله القاعدة، لا ما نظنّه ═════════════════


class BackendWatch:
    """يلتقط معرّفاتَ الخوادم الخلفيّة التي يسحبها التطبيقُ من مجمّعه.

    ولمَ لا يكفي `pg_stat_activity` وحده: قاعدةُ الفحص ليست ساكنةً بالضرورة.
    فتُعرف خوادمُ **هذا التطبيق** بأعيانها، ثمّ يُسأل عن حالها وحدَها.
    """

    #: **والمحرّكُ يُمرَّر ولا يُستورَد.** حارسُ الحزمة
    #: (`test_no_test_disposes_the_global_application_engine`) يمنع كلَّ ملفِّ
    #: اختبارٍ من `from …db import engine`، والمُحقّ فيه: التطبيقُ مربوطٌ
    #: بمحرّك الاختبارات، فاستيرادُ العامّ يراقب محرّكًا لا يعمل.
    def __init__(self, engine) -> None:
        self.pids: set[int] = set()
        self._engine = engine
        self._listener = None

    def __enter__(self):
        from sqlalchemy import event

        def _checkout(dbapi_connection, record, proxy):
            driver = getattr(dbapi_connection, "driver_connection", None)
            getter = getattr(driver, "get_server_pid", None)
            if getter is not None:
                self.pids.add(getter())

        self._listener = _checkout
        event.listen(self._engine.sync_engine, "checkout", _checkout)
        return self

    def __exit__(self, *exc):
        from sqlalchemy import event

        event.remove(self._engine.sync_engine, "checkout", self._listener)
        return False


async def _observer():
    """اتصالٌ مستقلٌّ يسأل `pg_stat_activity` — لا جلسةُ التطبيق."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    url = os.getenv("DATABASE_MIGRATION_URL") or os.getenv("DATABASE_URL", "")
    if not url:
        pytest.skip("no database URL is configured")
    engine = create_async_engine(url.replace("+psycopg", "+asyncpg"),
                                 poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def open_transactions(pids: set[int]) -> list[tuple]:
    """الخوادمُ من `pids` التي تُمسك معاملةً الآن — بقول القاعدة."""
    from sqlalchemy import text

    if not pids:
        return []
    engine, factory = await _observer()
    try:
        async with factory() as session:
            rows = (await session.execute(
                text(
                    "SELECT pid, state, xact_start IS NOT NULL AS in_xact,"
                    "       extract(epoch from (now() - xact_start)) AS held_s"
                    "  FROM pg_stat_activity"
                    " WHERE pid = ANY(:pids)"
                    "   AND xact_start IS NOT NULL"
                ),
                {"pids": list(pids)},
            )).all()
        return [tuple(r) for r in rows]
    finally:
        await engine.dispose()


def _client(slot, locale: str = "ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


@pytest.fixture(autouse=True)
def _clean_rate_limit():
    from athera_api.services import ai_rate_limit

    ai_rate_limit.reset()
    yield
    ai_rate_limit.reset()


async def _measure_during_external_wait(engine, slot, url: str, payload: dict,
                                        provider):
    """يُشغّل الطلبَ، ويقيس حالَ القاعدة **أثناء حبس المزوّد**.

    ويعيد: (شواهدُ المعاملات المفتوحة، جوابُ الطلب، الخوادمُ المسحوبة).
    """
    with BackendWatch(engine) as watch:
        async with _client(slot) as http:
            task = asyncio.create_task(http.post(url, json=payload))
            # **ولا انتظارٌ أعمى**: إن انتهى الطلبُ قبل أن يبلغ المزوّدَ
            # فالسببُ في جوابه، ويُقال في رسالة السقوط بدل أن يُخمَّن.
            reached = asyncio.create_task(provider.entered.wait())
            done, _ = await asyncio.wait({task, reached}, timeout=30,
                                         return_when=asyncio.FIRST_COMPLETED)
            if reached not in done:
                reached.cancel()
                if task in done:
                    answered = task.result()
                    raise AssertionError(
                        "لم يبلغ الطلبُ المزوّدَ — فالقياسُ لا يقيس شيئًا. "
                        f"HTTP {answered.status_code}: {answered.text[:400]}")
                task.cancel()
                raise AssertionError("لم يبلغ الطلبُ المزوّدَ ولم يُجب — مهلةٌ")

            # المزوّدُ محبوسٌ الآن: هذه هي اللحظةُ المقصودة بالقياس.
            evidence = await open_transactions(watch.pids)

            provider.release.set()
            response = await task
    return evidence, response, watch.pids


# ════════════════════ ١ · العطب يُعاد إنتاجه أو يُنفى ════════════════════


async def test_01_ai_ask_holds_no_transaction_across_the_model_wait(
    two_tenants, monkeypatch, test_engine,
):
    """**`ai.ask`: لا معاملةَ قاعدةٍ مفتوحةٌ أثناء انتظار النموذج.**

    وهذا الفحصُ يسقط على بنية `main` قبل الإصلاح: المسارُ يأخذ
    `Depends(get_session)` ويُمرّرها إلى `run_agent`، فتبقى المعاملةُ حيّةً
    حتى يعود المزوّد.
    """
    provider = _use_provider(monkeypatch, BarrierProvider())

    evidence, response, pids = await _measure_during_external_wait(
        test_engine, two_tenants["a"], AI_ASK, {"question": QUESTION}, provider)

    assert provider.calls == 1, "لم يُنادَ المزوّدُ مرّةً واحدة"
    assert pids, "لم يُسحب اتصالٌ واحد — فالمسارُ لم يعمل على القاعدة أصلًا"
    assert not evidence, (
        "معاملةٌ مفتوحةٌ أثناء انتظار النموذج — وهذا RC-T1-H3 بعينه: "
        f"{evidence}"
    )
    assert response.status_code == 200, response.text


async def test_02_brain_ask_holds_no_transaction_across_the_model_wait(
    two_tenants, monkeypatch, test_engine,
):
    """**`brain.ask`: لا معاملةَ قاعدةٍ مفتوحةٌ أثناء انتظار النموذج.**"""
    provider = _use_provider(monkeypatch, BarrierProvider())
    _allow_c2(monkeypatch)

    evidence, response, pids = await _measure_during_external_wait(
        test_engine, two_tenants["a"], BRAIN_ASK,
        {"agent_key": "research_manager", "question": QUESTION}, provider)

    assert provider.calls == 1, "لم يُنادَ المزوّدُ مرّةً واحدة"
    assert pids, "لم يُسحب اتصالٌ واحد — فالمسارُ لم يعمل على القاعدة أصلًا"
    assert not evidence, (
        "معاملةٌ مفتوحةٌ أثناء انتظار النموذج — وهذا RC-T1-H3 بعينه: "
        f"{evidence}"
    )
    assert response.status_code == 200, response.text


# ══════════ ٢ · الشبكةُ غيرُ النموذج: الفهارسُ الخارجيّة (الطور J) ══════════


LITERATURE_QUESTION = "ابحث لي في الأدبيات عن أثر التعلّم المدمج في التحصيل الدراسيّ."


class BarrierDiscovery:
    """بديلُ `reference_discovery.search` يقف عند حاجز.

    و**RC-T1-H3 ليس «لا انتظارَ نموذج» وحده**: كلُّ انتظارٍ خارجيٍّ يقع
    ومعاملةٌ حيّةٌ هو العطبُ نفسُه. و`ai.ask` كان ينتظر الفهارسَ
    (Crossref/OpenAlex) داخل معاملة الطلب قبل أن يبلغ النموذجَ أصلًا.
    """

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def __call__(self, question, **kwargs):
        from athera_api.discovery.contracts import DiscoveryResult

        self.calls += 1
        self.entered.set()
        await self.release.wait()
        return DiscoveryResult(ranked=(), provider_statuses=(), query=None,
                               external_link=None)


async def test_03_ai_ask_holds_no_transaction_across_the_reference_search(
    two_tenants, monkeypatch, test_engine,
):
    """**ولا معاملةَ أثناء نداء الفهارس** — لا النموذجِ وحده (الطور J)."""
    from athera_api.discovery import throttle
    from athera_api.services import reference_discovery

    throttle.reset()
    discovery = BarrierDiscovery()
    monkeypatch.setattr(reference_discovery, "search", discovery)
    # النموذجُ معطَّل: الدعوى هنا على انتظار الفهارس وحده.
    monkeypatch.setattr(__import__("athera_api.config", fromlist=["x"]).get_settings(),
                        "model_provider", "null", raising=False)

    evidence, response, pids = await _measure_during_external_wait(
        test_engine, two_tenants["a"], AI_ASK,
        {"question": LITERATURE_QUESTION}, discovery)

    assert discovery.calls == 1, "لم يُنادَ اكتشافُ المراجع"
    assert pids, "لم يُسحب اتصالٌ واحد — فالمسارُ لم يعمل على القاعدة"
    assert not evidence, (
        "معاملةٌ مفتوحةٌ أثناء نداء الفهارس الخارجيّة — RC-T1-H3: "
        f"{evidence}")
    assert response.status_code == 200, response.text


# ══════════════ ٣ · إخفاقُ المزوّد، والانقطاع، والتزامن ══════════════


async def test_04_a_provider_failure_leaves_no_open_transaction(
    two_tenants, monkeypatch, test_engine,
):
    """إخفاقُ المزوّد: لا معاملةٌ باقية، ولا نجاحٌ كاذب (الطور L)."""
    provider = _use_provider(monkeypatch, FailingProvider())
    _allow_c2(monkeypatch)

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            task = asyncio.create_task(
                http.post(BRAIN_ASK, json={"agent_key": "research_manager",
                                           "question": QUESTION}))
            await asyncio.wait_for(provider.entered.wait(), timeout=30)
            provider.release.set()
            response = await task
        after = await open_transactions(watch.pids)

    assert provider.calls == 1
    assert response.status_code >= 400, (
        f"إخفاقُ المزوّد رُدَّ نجاحًا: HTTP {response.status_code}")
    assert not after, f"معاملةٌ باقيةٌ بعد إخفاق المزوّد: {after}"


async def test_05_a_cancelled_request_leaves_no_open_transaction(
    two_tenants, monkeypatch, test_engine,
):
    """**انقطاعُ الطلب أثناء الانتظار لا يُبقي معاملة** (الطور N).

    وقبل الإصلاح كانت معاملةُ الطلب مفتوحةً عند نقطة الانتظار، فالإلغاءُ
    يقع وهي حيّة. وبعده لا معاملةَ أصلًا عند تلك النقطة — فلا شيءَ يبقى.
    """
    provider = _use_provider(monkeypatch, BarrierProvider())
    _allow_c2(monkeypatch)

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            task = asyncio.create_task(
                http.post(BRAIN_ASK, json={"agent_key": "research_manager",
                                           "question": QUESTION}))
            await asyncio.wait_for(provider.entered.wait(), timeout=30)
            during = await open_transactions(watch.pids)
            task.cancel()
            with pytest.raises((asyncio.CancelledError, Exception)):
                await task
        await asyncio.sleep(0)
        after = await open_transactions(watch.pids)

    assert not during, f"معاملةٌ مفتوحةٌ عند نقطة الانتظار: {during}"
    assert not after, f"معاملةٌ باقيةٌ بعد انقطاع الطلب: {after}"


async def test_06_concurrent_slow_requests_do_not_pin_a_transaction_each(
    two_tenants, monkeypatch, test_engine,
):
    """**خمسةُ انتظاراتٍ متزامنة، وصفرُ معاملاتٍ محبوسة** (الطور O).

    ولا إطارَ حملٍ هنا: عددٌ صغيرٌ محكوم. والدعوى أنّ عددَ المعاملات
    المفتوحة لا يساوي عددَ الطلبات المنتظرة — بل صفرٌ.
    """
    provider = _use_provider(monkeypatch, BarrierProvider())
    _allow_c2(monkeypatch)
    waves = 5
    arrived = asyncio.Semaphore(0)

    original = provider.generate_structured

    async def counting(request):
        arrived.release()
        return await original(request)

    provider.generate_structured = counting  # type: ignore[method-assign]

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            tasks = [
                asyncio.create_task(
                    http.post(BRAIN_ASK, json={"agent_key": "research_manager",
                                               "question": f"{QUESTION} ({n})"}))
                for n in range(waves)
            ]
            for _ in range(waves):
                await asyncio.wait_for(arrived.acquire(), timeout=30)

            # الخمسةُ كلُّها عند المزوّد الآن.
            evidence = await open_transactions(watch.pids)

            provider.release.set()
            responses = await asyncio.gather(*tasks)

    assert provider.calls == waves, f"وصل المزوّدَ {provider.calls} من {waves}"
    assert not evidence, (
        f"{len(evidence)} معاملةً محبوسةً و{waves} طلبًا تنتظر — "
        f"فالمجمَّعُ يُحبَس بطلبٍ لكلٍّ: {evidence}")
    assert all(r.status_code == 200 for r in responses), (
        [r.status_code for r in responses])


# ══════════════════ ٤ · إخفاقُ الإيداع النهائيّ (الطور M) ══════════════════


async def _plant_finalize_bomb(agent_key: str) -> None:
    """قيدٌ مؤجَّلٌ على `agent_runs` يرفع عند `COMMIT` لهذا الأجنت وحده.

    **ولا مُرقِّعٌ يزيّف `commit()`**: الحدُّ المفحوصُ هو الإيداعُ نفسُه،
    فالإخفاقُ يأتي من القاعدة — كما في RC-T1-H1.
    """
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "CREATE OR REPLACE FUNCTION athera_rc_t1_h3_finalize_bomb()"
                    " RETURNS trigger LANGUAGE plpgsql AS $fn$ BEGIN"
                    f"   IF NEW.agent_key = '{agent_key}' THEN"
                    "     RAISE EXCEPTION 'RC-T1-H3: planted finalize failure';"
                    "   END IF; RETURN NEW; END $fn$"))
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_rc_t1_h3_finalize_bomb_trg"
                    " ON agent_runs"))
                await session.execute(text(
                    "CREATE CONSTRAINT TRIGGER athera_rc_t1_h3_finalize_bomb_trg"
                    " AFTER INSERT ON agent_runs DEFERRABLE INITIALLY DEFERRED"
                    " FOR EACH ROW EXECUTE FUNCTION athera_rc_t1_h3_finalize_bomb()"))
    finally:
        await engine.dispose()


async def _remove_finalize_bomb() -> None:
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_rc_t1_h3_finalize_bomb_trg"
                    " ON agent_runs"))
                await session.execute(text(
                    "DROP FUNCTION IF EXISTS athera_rc_t1_h3_finalize_bomb()"))
    finally:
        await engine.dispose()


async def test_07_a_failed_finalize_commit_is_never_reported_as_success(
    two_tenants, monkeypatch, test_engine,
):
    """**النموذجُ نجح، وحفظُ الأثر أخفق ⇒ لا جوابَ نجاح** (الطور M، وRC-T1-H1).

    والفخُّ حقيقيّ: `ai.ask` يلتقط كلَّ استثناءٍ عامٍّ ويردّ ٢٠٠
    «تعذّر الوصول إلى مزوّد النموذج». فلو صعد إخفاقُ الإيداع خامًّا لصار
    **نجاحًا كاذبًا على كتابةٍ لم تُودَع**.

    **ولا يُدَّعى أنّ النموذجَ نُفِّذ مرّةً واحدةً بالضبط**: نداؤه وقع
    وكلفتُه أُنفقت، ولا معاملةَ قاعدةٍ تُرجِع ذلك.
    """
    provider = _use_provider(monkeypatch, BarrierProvider())
    provider.release.set()
    # **و`ai.ask` هو موضعُ الفخّ** لا `brain.ask`: هو الذي يلتقط كلَّ
    # استثناءٍ عامٍّ ويردّ ٢٠٠ `provider_error`. فيُفحص حيث يُخشى الكذب.
    await _plant_finalize_bomb("research_manager")
    try:
        async with _client(two_tenants["a"]) as http:
            response = await http.post(AI_ASK, json={"question": QUESTION})
    finally:
        await _remove_finalize_bomb()

    assert provider.calls == 1, "لم يُنادَ المزوّد — فالفحصُ لا يقيس الحالة"
    assert response.status_code >= 400, (
        "إخفاقُ إيداعِ الأثر رُدَّ نجاحًا — RC-T1-H1: "
        f"HTTP {response.status_code}: {response.text[:300]}")
    body = response.json()
    assert body.get("status") != "provider_error", (
        "إخفاقُ الإيداع تُرجم «تعذّر المزوّد» — وهو وصفٌ غيرُ صحيحٍ لما وقع")
    assert body.get("error", {}).get("code") == "db.commit_failed", body


async def test_08_no_agent_run_is_left_permanently_running(
    two_tenants, monkeypatch,
):
    """**ولا صفَّ `running` يبقى بعد إخفاق المزوّد** (الطور K).

    وهذا عطبٌ كان قائمًا في `main`: `ai.ask` يلتقط إخفاقَ المزوّد ويردّ ٢٠٠،
    و`TransactionalRoute` يُودِع — فيبقى `AgentRun` عند `running` بلا
    `finished_at` وبلا `error`، أبدًا، ولا مَن يُنهيه.

    والبنيةُ المنفصلة تمنعه بالتكوين: لا سجلَّ يُكتب قبل الشبكة، والأثرُ
    يُكتب مرّةً واحدةً بحالٍ **نهائيّة**.
    """
    from sqlalchemy import text

    tenant_id = two_tenants["a"]["tenant_id"]

    class Boom(BarrierProvider):
        async def generate_structured(self, request):
            self.calls += 1
            raise RuntimeError("provider refused on purpose")

    _use_provider(monkeypatch, Boom())
    async with _client(two_tenants["a"]) as http:
        response = await http.post(AI_ASK, json={"question": QUESTION})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "provider_error"

    engine, factory = await _observer()
    try:
        async with factory() as session:
            stranded = (await session.execute(text(
                "SELECT count(*) FROM agent_runs"
                " WHERE tenant_id = :t AND status = 'running'"),
                {"t": str(tenant_id)})).scalar_one()
            terminal = (await session.execute(text(
                "SELECT status, finished_at IS NOT NULL, error IS NOT NULL"
                "  FROM agent_runs WHERE tenant_id = :t"),
                {"t": str(tenant_id)})).all()
    finally:
        await engine.dispose()

    assert stranded == 0, f"{stranded} صفًّا عَلِق عند `running` بلا مُنهٍ"
    assert terminal, "لم يُكتب أثرٌ أصلًا — فالإخفاقُ لم يُسجَّل"
    for status, finished, has_error in terminal:
        assert status in {"failed", "blocked", "completed"}, status
        assert has_error or status == "completed", f"إخفاقٌ بلا سببٍ مكتوب: {status}"
        assert finished, f"حالٌ نهائيّةٌ بلا `finished_at`: {status}"


# ═════════════ ٥ · الأطوارُ مقيسةٌ زمنيًّا (الطور P) ═════════════


async def test_09_the_external_wait_is_outside_both_database_phases(
    two_tenants, monkeypatch,
):
    """**الانتظارُ الخارجيُّ أطولُ من طورَي القاعدة مجتمعَين** — قياسًا لا وصفًا.

    ولا يُقاس زمنُ النموذج (فهو محكومٌ هنا)، بل **موضعُه**: أنّ الحبسَ وقع
    في الطور الثاني وحده، وأنّ طورَي القاعدة قصيران بجانبه.
    """
    from athera_api.brain.orchestrator import Orchestrator, ToolCall
    from athera_api.db import tenant_session_maker

    provider = _use_provider(monkeypatch, BarrierProvider())
    _allow_c2(monkeypatch)
    slot = two_tenants["a"]
    timings: dict[str, float] = {}

    async def release_after_a_while():
        await provider.entered.wait()
        await asyncio.sleep(0.30)          # حبسٌ محكومٌ يمثّل زمنَ المزوّد
        provider.release.set()

    releaser = asyncio.create_task(release_after_a_while())
    await Orchestrator().run_agent_detached(
        tenant_session_maker(slot["tenant_id"], slot["user_id"]),
        tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
        agent_key="research_manager", question=QUESTION,
        tool_calls=[ToolCall(key="memory.search_verified", kwargs={"query": None})],
        timings=timings,
    )
    await releaser

    assert set(timings) == {"prepare_s", "external_s", "finalize_s"}, timings
    assert timings["external_s"] >= 0.30, timings
    # وطورا القاعدة معًا أقصرُ كثيرًا من الانتظار — فالمعاملةُ لم تحمله.
    assert timings["prepare_s"] + timings["finalize_s"] < timings["external_s"], (
        "طورا القاعدة ليسا قصيرَين بجانب الانتظار — فهما يحملانه: "
        f"{timings}")


# ═══════ ٦ · لا كائنَ ORM يعبُر الحدّ، ولا صلاحيةَ تتراجع (E و I) ═══════


def test_10_the_detached_path_takes_a_session_maker_never_a_session() -> None:
    """**دالّةٌ تُنشئ جلسةً، لا جلسةٌ تُمرَّر** — وهو الفرقُ كلُّه.

    وجلسةٌ مُمرَّرة تعني معاملةً حيّةً يملكها المستدعي، فتبقى مفتوحةً طوال
    عمله. فيُشترط في التوقيع أنّ أوّل معامل ليس `AsyncSession`.
    """
    import inspect

    from sqlalchemy.ext.asyncio import AsyncSession

    from athera_api.brain.orchestrator import Orchestrator

    signature = inspect.signature(Orchestrator.run_agent_detached)
    names = list(signature.parameters)
    assert names[1] == "session_maker", names
    annotation = signature.parameters["session_maker"].annotation
    assert annotation is not AsyncSession, annotation
    assert "session" not in [n for n in names[2:]], (
        f"معامِلُ جلسةٍ في المسار المنفصل: {names}")


def test_11_no_orm_object_crosses_the_detached_boundary() -> None:
    """ما يُحمَل عبر الحدّ قيمٌ عاديّة — **ولا صفُّ ORM** (الطور E).

    والصفُّ يموت بموت معاملته، والتحميلُ المتأخّر بعد إغلاقها يرفع؛ وأسوأ
    من الرفع أن يُقرأ بلا سياق مستأجر فتردّ RLS صفرَ صفوفٍ صامتة.

    فيُفحص أنّ `_ToolOutcome` بنيةُ قيمٍ لا كائنُ ORM، وأنّ حقولَها
    أوّليّاتٌ خالصة.
    """
    import dataclasses

    from sqlalchemy.orm import class_mapper

    from athera_api.brain.orchestrator import _ToolOutcome

    assert dataclasses.is_dataclass(_ToolOutcome)
    try:
        class_mapper(_ToolOutcome)
        mapped = True
    except Exception:  # noqa: BLE001
        mapped = False
    assert not mapped, "`_ToolOutcome` صارت كائنَ ORM — فهي لا تعبُر الحدّ"

    allowed = {"str", "int", "dict", "int | None", "dict | None"}
    for field in dataclasses.fields(_ToolOutcome):
        assert str(field.type) in allowed, (field.name, field.type)


async def test_12_project_authorization_is_unchanged_and_still_conceals(
    two_tenants, monkeypatch,
):
    """**معرّفُ بحثٍ في الجسم لا يصير مدخلًا موثوقًا** (الطور I).

    و`ai.ask` من مسارات `RC-T1-D3` (المعرّفُ يأتي في الجسم) — **ولا يُغلق
    ذلك الدَّين هنا**. والمطلوبُ أن تبقى الصلاحيةُ كما كانت بعد نقل
    القراءة إلى معاملةٍ قصيرة: بحثُ مستأجرٍ آخر يُكتَم بـ٤٠٤، ومعرّفٌ
    مختلَقٌ كذلك — فلا يُفرَّق بينهما.
    """
    from athera_api.db import tenant_session_maker
    from athera_api.models.portfolio import ResearchProject

    _use_provider(monkeypatch, BarrierProvider()).release.set()
    other = two_tenants["b"]

    # بحثٌ حقيقيٌّ في مستأجر (ب) — يُنشأ بجلسته لا بجلسة (أ).
    async with tenant_session_maker(other["tenant_id"], other["user_id"])() as session:
        project = ResearchProject(
            tenant_id=other["tenant_id"],
            working_title_ar="بحثُ مستأجرٍ آخر", status="planned")
        session.add(project)
        await session.flush()
        foreign_id = str(project.id)

    invented = str(uuid.uuid4())
    async with _client(two_tenants["a"]) as http:
        foreign = await http.post(AI_ASK, json={"question": QUESTION,
                                                "project_id": foreign_id})
        unknown = await http.post(AI_ASK, json={"question": QUESTION,
                                                "project_id": invented})

    assert foreign.status_code == 404, (
        f"بحثُ مستأجرٍ آخر لم يُكتَم: HTTP {foreign.status_code}")
    assert unknown.status_code == 404, unknown.status_code
    # **ولا يُفرَّق بين المكتوم والمختلَق** — وإلّا صار الرمزُ مؤشّرَ وجود.
    assert foreign.json()["error"]["code"] == unknown.json()["error"]["code"], (
        foreign.json()["error"]["code"], unknown.json()["error"]["code"])


async def test_13_a_guardrail_block_still_blocks_and_records_its_trace(
    two_tenants, monkeypatch,
):
    """**الحواجزُ تعمل كما كانت، وأثرُها يُكتب** (الطوران K و T).

    والحاجزُ يُختبر بمخرَجٍ يستشهد بـDOI ليس في مجموعة الأدلّة — فيُحجب،
    ويُكتب `guardrail_checks` و`IntegrityAlert`، ولا يصل الجوابُ العميلَ.
    """
    from sqlalchemy import text

    from athera_api.providers.base import ModelResponse, ModelUsage

    tenant_id = two_tenants["a"]["tenant_id"]

    class Fabricator(BarrierProvider):
        async def generate_structured(self, request):
            self.calls += 1
            return ModelResponse(
                content="x", provider=self.name, model="m",
                structured={
                    "answer_ar": "تؤكّد الدراسة ذلك (doi:10.9999/not-in-context).",
                    "citations": [{"memory_id": str(uuid.uuid4()),
                                   "locator": "p.1", "quote": "مختلق"}],
                    "unsupported_claims": [], "evidence_gaps": [],
                },
                usage=ModelUsage(input_tokens=1, output_tokens=1, latency_ms=1))

    _use_provider(monkeypatch, Fabricator())
    _allow_c2(monkeypatch)
    async with _client(two_tenants["a"]) as http:
        response = await http.post(BRAIN_ASK, json={"agent_key": "research_manager",
                                                    "question": QUESTION})

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "brain.output_blocked", response.text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            blocked = (await session.execute(text(
                "SELECT count(*) FROM agent_runs"
                " WHERE tenant_id = :t AND status = 'blocked'"),
                {"t": str(tenant_id)})).scalar_one()
            checks = (await session.execute(text(
                "SELECT count(*) FROM guardrail_checks WHERE tenant_id = :t"),
                {"t": str(tenant_id)})).scalar_one()
            alerts = (await session.execute(text(
                "SELECT count(*) FROM integrity_alerts"
                " WHERE tenant_id = :t AND alert_type = 'guardrail_block'"),
                {"t": str(tenant_id)})).scalar_one()
    finally:
        await engine.dispose()

    # **والأثرُ مُودَعٌ رغم أنّ الطلبَ انتهى بخطأ** — وهو المقصود: الحجبُ
    # واقعةٌ تُسجَّل، لا صمتٌ يُرجَع.
    assert blocked == 1, f"أثرُ الحجب لم يُودَع: blocked={blocked}"
    assert checks >= 1, f"لا فحوصَ حواجزَ مكتوبة: {checks}"
    assert alerts == 1, f"لا تنبيهَ نزاهةٍ مكتوب: {alerts}"


# ═══════════════ ٧ · حارسٌ معماريّ يمنع رجوعَ الدَّين (الطور R) ═══════════════
#
# **والحارسُ على الشجرة لا على النصّ**: `grep` على `run_agent` يتّهم تعليقًا
# يذكره، ويفوته استدعاءٌ مقسومٌ على سطرَين.

#: نداءاتٌ تخرج من العمليّة — مقروءةٌ من المستودع لا مُخمَّنة.
#:
#: `httpx` في `discovery/crossref.py` و`discovery/openalex.py` و
#: `services/literature/registry.py`؛ وحزمةُ المزوّد في
#: `providers/{openai,anthropic}_adapter.py`؛ وboto3 في `services/storage.py`.
KNOWN_EXTERNAL_CALLS = {
    "run_agent": "MODEL PROVIDER",
    "search": "EXTERNAL NETWORK",          # source_registry / reference_discovery
    "discover": "EXTERNAL NETWORK",
    "resolve_doi": "EXTERNAL NETWORK",
    "revalidate": "EXTERNAL NETWORK",
    "ingest_file": "STORAGE",
    "_load_bytes": "STORAGE",
}

#: ما بقي من `RC-T1-H3` **مُسمًّى ولا يُخفى**، وكلٌّ منه صنفُ العطب نفسُه.
#: انظر `docs/maintenance/RC-T1-H3-ai-long-transactions.md`.
#:
#: وزيادةُ هذه القائمة تُسقط الحزمة: **الدَّينُ لا يكبر صامتًا**.
KNOWN_REMAINING: set[tuple[str, str]] = set()
#
# **وكانت ستّةً، فخلت** (RC-T1-H3-B): كلُّها عُولجت بالنمط نفسِه — تحضيرٌ
# قصير، ثمّ الخارجُ بلا معاملة، ثمّ إنهاءٌ قصير. ولم يُحذف الحارس: بقاؤه
# فارغًا دعوى تُفحص، لا سطرٌ ميّت.
#
# **والدعوى الأصلبُ في موضعٍ آخر**: `test_19` في
# `test_at_rc_t1_h3b_remaining_external_waits.py` يمسح التطبيقَ بحلِّ
# الاستيراد — بلا مطابقةِ أسماءٍ مجرّدةٍ وبلا قائمةِ استثناءات — ويشترط
# صفرًا. وهذا الحارسُ يبقى رخيصًا وسريعًا بجانبه.

SESSION_DEPENDENCIES = {"get_session", "get_project_session"}


def _route_handlers():
    """معالجاتُ المسارات من الشجرة: (ملفّ، اسم، تبعيّاتُ جلسة، نداءاتٌ مُنتظَرة)."""
    import ast
    import pathlib

    routers = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"
    for path in sorted(routers.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                       and d.func.attr in {"get", "post", "put", "patch", "delete"}
                       for d in fn.decorator_list):
                continue
            managed = {
                d.args[0].id
                for d in [*fn.args.defaults,
                          *[k for k in fn.args.kw_defaults if k is not None]]
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                and d.func.id == "Depends" and d.args
                and isinstance(d.args[0], ast.Name)
                and d.args[0].id in SESSION_DEPENDENCIES
            }
            awaited = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                    func = node.value.func
                    name = (func.attr if isinstance(func, ast.Attribute)
                            else func.id if isinstance(func, ast.Name) else None)
                    if name:
                        awaited.add(name)
            yield path.name, fn.name, managed, awaited


def test_14_no_route_holds_a_request_transaction_across_a_model_call() -> None:
    """**الدعوى الصلبة: لا مسارَ يمسك معاملةَ الطلب عبر نداء نموذج.**

    ولا يُمنع `run_agent` من غير شيفرة الطلب: المنسّقُ والنصوصُ والفحوص
    تناديه بجلسةٍ تملكها، وذاك صحيح. الممنوعُ اقترانُه بجلسةٍ **يُديرها
    الطلب** في معالجِ مسار.
    """
    offenders = [
        f"{f}::{name}"
        for f, name, managed, awaited in _route_handlers()
        if managed and "run_agent" in awaited
    ]
    assert offenders == [], (
        "مسارٌ يمسك معاملةَ الطلب عبر نداء النموذج (RC-T1-H3):\n  "
        + "\n  ".join(offenders)
        + "\nوالنمطُ الصحيح: `run_agent_detached(tenant_session_maker(...), …)`")


def test_15_the_guard_would_notice_the_pattern_returning() -> None:
    """والحارسُ يعضّ: شجرةٌ مُحاكاةٌ تحمل النمطَ تُكشف.

    ولا يُحتسب حارسٌ لم يُجرَّب — فلو كان المسحُ يقرأ حقلًا خاطئًا لَمرّ
    الفحصُ أبدًا وهو لا يقيس شيئًا.
    """
    import ast
    import textwrap

    sample = textwrap.dedent("""
        @router.post('/ask')
        async def ask(session: AsyncSession = Depends(get_session)):
            return await Orchestrator().run_agent(session, question='x')
    """)
    fn = ast.parse(sample).body[0]
    managed = {
        d.args[0].id for d in fn.args.defaults
        if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
        and d.func.id == "Depends" and d.args
        and isinstance(d.args[0], ast.Name) and d.args[0].id in SESSION_DEPENDENCIES
    }
    awaited = {
        node.value.func.attr for node in ast.walk(fn)
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
    }
    assert managed == {"get_session"}, managed
    assert "run_agent" in awaited, awaited


def test_16_the_remaining_external_wait_routes_are_exactly_the_declared_ones() -> None:
    """**والدَّينُ الباقي لا يكبر صامتًا** — القائمةُ مطابقةٌ لا مُتضمَّنة.

    وهذه المسارات الستّة تمسك معاملةَ الطلب عبر نداءٍ خارجيّ، وهي صنفُ
    `RC-T1-H3` نفسُه — لكنّها **ليست نطاقَ هذه الدفعة**: إعادةُ تشكيلها
    ستّةَ مساراتِ منتجٍ في دفعةٍ تُغلق دعوى `ai.ask`/`brain.ask` يجعل
    الدفعةَ غيرَ قابلةٍ للمراجعة.

    فتُسمّى هنا بأعيانها: **مسارٌ جديدٌ يقع في النمط يُسقط الحزمة**،
    ومسارٌ يُعالَج يلزمه حذفُ اسمه من هنا. والمطابقةُ التامّة هي التي
    تمنع القائمةَ من أن تتعفّن في الاتّجاهين.
    """
    found = {
        (f, name)
        for f, name, managed, awaited in _route_handlers()
        if managed and (awaited & set(KNOWN_EXTERNAL_CALLS)) - {"run_agent"}
    }
    new = found - KNOWN_REMAINING
    fixed = KNOWN_REMAINING - found
    assert not new, (
        "مسارٌ جديدٌ يمسك معاملةَ الطلب عبر نداءٍ خارجيّ (RC-T1-H3):\n  "
        + "\n  ".join(f"{f}::{n}" for f, n in sorted(new)))
    assert not fixed, (
        "مساراتٌ عُولجت ولم تُحذف من `KNOWN_REMAINING`:\n  "
        + "\n  ".join(f"{f}::{n}" for f, n in sorted(fixed)))


def test_17_neither_ai_ask_nor_brain_ask_takes_a_request_managed_session() -> None:
    """والمسارانِ المقصودانِ بهذه الدفعة لا يأخذان جلسةً يُديرها الطلب."""
    handlers = {(f, name): managed for f, name, managed, _ in _route_handlers()}
    assert handlers.get(("ai.py", "ask")) == set(), handlers.get(("ai.py", "ask"))
    assert handlers.get(("brain.py", "ask")) == set(), handlers.get(("brain.py", "ask"))
