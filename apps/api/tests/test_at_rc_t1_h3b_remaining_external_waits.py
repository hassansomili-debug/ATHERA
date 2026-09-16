"""RC-T1-H3-B — **ولا مسارَ يمسك معاملةً عبر انتظارٍ خارجيّ** | the rest of H3.

## ما أغلقه H3-A، وما بقي لهذا الطور

`RC-T1-H3-A` أغلق مسارَي الذكاء (`ai.ask`، `brain.ask`). وبقيت ستّةٌ من
**الصنف نفسِه** تمسك معاملةَ الطلب عبر شبكةٍ أو تخزين:

    /sources/search              source_registry.search      شبكة
    /references/search           discover                    شبكة
    /sources/import              verification.resolve_doi    شبكة
    /sources/{id}/verify         verification.revalidate     شبكة
    /profile/import              ingestion.ingest_file       تخزين
    /theses/{id}/parse           _load_bytes                 تخزين

**وسابعٌ وجده القارئُ لا الماسح**، داخل `/profile/import` نفسِه:
`ModelExtractor` كان يُبنى بجلسة الطلب فيُمرّرها إلى بوابة النموذج — أي
نداءُ نموذجٍ داخل معاملةٍ حيّة. ولم يره المسحُ الساكن لأنّ `Extractor`
واجهةٌ تُمرَّر مُعامِلًا. فأُغلق معها، وبُذرت الواجهةُ في الحارس.

## والقياسُ على PostgreSQL نفسِها

الانتظارُ يُصنع بحاجزٍ محكومٍ حول الاعتماد الخارجيّ الحقيقيّ — وهذا مسموح.
أمّا حدُّ المعاملة **فلا يُزيَّف**: يُلتقط `pg_backend_pid` لكلّ اتصالٍ
يسحبه التطبيقُ من مجمّعه، ثمّ يُسأل `pg_stat_activity` **من اتصالٍ آخر**:

    state = 'idle in transaction'   →  معاملةٌ مفتوحةٌ بلا عمل
    xact_start IS NOT NULL          →  ومتى بدأت

## والدعوى النهائية

> **صفرُ مسارات** تمسك معاملةَ قاعدةٍ عبر زمنٍ خارجيٍّ غيرِ محدود.

ويحرسها `test_19` بماسحٍ يحلّ الاستيراد (`external_wait_audit`) — لا
قائمةَ استثناءاتٍ ولا سماحَ لأحد. ومسارٌ جديدٌ يقع في النمط يُسقط الحزمة
ومعه سلسلةُ النداء كاملةً.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.test_at_rc_t1_h3_ai_long_transactions import (
    BackendWatch,
    _client,
    _observer,
    open_transactions,
)

pytestmark = pytest.mark.asyncio

SOURCES_SEARCH = "/api/v1/sources/search"
REFERENCES_SEARCH = "/api/v1/references/search"
SOURCES_IMPORT = "/api/v1/sources/import"
PROFILE_IMPORT = "/api/v1/profile/import"

#: مستندٌ نصّيٌّ **يُقرأ فعلًا** — و`text/plain` مسموحٌ للرفع
#: (`storage.DOCUMENT_TYPES`) و`parse_text` تفكّكه.
#:
#: ولمَ لا PDF مُصطنَع: `pypdf` ترفضه (`startxref not found`) فيخرج ٥٠٠ —
#: وهو السلوكُ نفسُه قبل الإصلاح وبعده (`ingest_file` تلتقط
#: `UnsupportedDocument` وحدها)، لكنّه يُخفي الدعوى المقيسة تحت ضجيج.
DOCUMENT = (
    "مشكلة الدراسة: قياس أثر التعلّم المدمج في التحصيل الدراسيّ.\n\n"
    "المنهج: تصميمٌ شبه تجريبيّ على مجموعتين متكافئتين.\n\n"
    "النتائج: فرقٌ لصالح المجموعة التجريبيّة في الاختبار البعديّ.\n"
).encode("utf-8")


# ═══════════════════════ حاجزٌ حول الاعتماد الخارجيّ ═══════════════════════


class Barrier:
    """يوقف نداءً خارجيًّا حتى يفتحه الفحص، ثمّ يعيد ما يُطلب منه.

    **والحبسُ هو المقصود**: هو ما يجعل «الانتظار الخارجيّ» قابلًا للقياس
    بلا شبكةٍ حقيقيّةٍ ولا زمنٍ مُقدَّر. وما لا يُزيَّف هو حدُّ المعاملة.
    """

    def __init__(self, result=None, error: BaseException | None = None) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0
        self.seen: list = []
        self._result = result
        self._error = error

    async def __call__(self, *args, **kwargs):
        self.calls += 1
        self.seen.append((args, kwargs))
        self.entered.set()
        await self.release.wait()
        if self._error is not None:
            raise self._error
        return self._result() if callable(self._result) else self._result


async def _measure(engine, slot, url, payload, barrier, *, method="post"):
    """يُشغّل الطلبَ ويقيس حالَ القاعدة **أثناء حبس الاعتماد الخارجيّ**."""
    with BackendWatch(engine) as watch:
        async with _client(slot) as http:
            send = getattr(http, method)
            task = asyncio.create_task(
                send(url, json=payload) if payload is not None else send(url))
            reached = asyncio.create_task(barrier.entered.wait())
            done, _ = await asyncio.wait({task, reached}, timeout=30,
                                         return_when=asyncio.FIRST_COMPLETED)
            if reached not in done:
                reached.cancel()
                if task in done:
                    answered = task.result()
                    raise AssertionError(
                        "لم يبلغ الطلبُ الاعتمادَ الخارجيّ — فالقياسُ لا يقيس "
                        f"شيئًا. HTTP {answered.status_code}: {answered.text[:400]}")
                task.cancel()
                raise AssertionError("لم يبلغ الطلبُ الاعتمادَ ولم يُجب — مهلةٌ")

            during = await open_transactions(watch.pids)
            barrier.release.set()
            response = await task
    return during, response, watch.pids


def _assert_detached(during, pids, response, *, expect=200):
    assert pids, "لم يُسحب اتصالٌ واحد — فالمسارُ لم يعمل على القاعدة أصلًا"
    assert not during, (
        "معاملةٌ مفتوحةٌ أثناء الانتظار الخارجيّ — RC-T1-H3: " f"{during}")
    if expect is not None:
        assert response.status_code == expect, response.text


# ═══════════════════════════ تجهيزاتُ الصفوف ═══════════════════════════


async def _make_source(slot, *, doi: str) -> uuid.UUID:
    from athera_api.db import tenant_session_maker
    from athera_api.models.literature import Source

    async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as session:
        row = Source(tenant_id=slot["tenant_id"], title="مصدرٌ للفحص", doi=doi,
                     retraction_status="none",
                     access_state="abstract_metadata_only")
        session.add(row)
        await session.flush()
        return row.id


async def _make_file(slot) -> uuid.UUID:
    """ملفٌّ **مرفوعٌ بالمسار الحقيقيّ** — فتُنشأ مِنحتُه مع صفّه.

    و`files` وحدَه لا يكفي: `require_object_action` تقرأ `ObjectGrant`،
    فصفٌّ يُدسّ مباشرةً يُردّ ٤٠٣. والرفعُ هو ما يمنح صاحبَه الكتابة —
    فيُستعمل المسارُ لا يُحاكى.
    """
    import io

    async with _client(slot) as http:
        uploaded = await http.post(
            "/api/v1/files/upload",
            files={"upload": ("h3b.txt", io.BytesIO(DOCUMENT), "text/plain")})
    assert uploaded.status_code == 201, uploaded.text
    return uuid.UUID(uploaded.json()["id"])


async def _make_thesis_with_file(slot) -> tuple[uuid.UUID, uuid.UUID]:
    from athera_api.db import tenant_session_maker
    from athera_api.models.thesis import Thesis

    file_id = await _make_file(slot)
    async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as session:
        thesis = Thesis(tenant_id=slot["tenant_id"], title_ar="رسالةٌ للفحص",
                        file_id=file_id)
        session.add(thesis)
        await session.flush()
        return thesis.id, file_id


@pytest.fixture(autouse=True)
def _memory_storage(monkeypatch):
    """تخزينٌ في الذاكرة — والدعوى حدُّ المعاملة لا مزوّدُ التخزين.

    وهو النمطُ القائم في `test_at_s5a_storage_upload.py`.
    """
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


@pytest.fixture(autouse=True)
def _reset_throttle():
    from athera_api.discovery import throttle

    throttle.reset()
    yield
    throttle.reset()


# ══════════ ١ · كلُّ مسارٍ من الستّة: صفرُ معاملاتٍ أثناء الانتظار ══════════


async def test_01_sources_search_holds_no_transaction_during_the_registry_call(
    two_tenants, monkeypatch, test_engine,
):
    """`/sources/search` — والتدقيقُ يُكتب **بعد** الشبكة في معاملةٍ قصيرة."""
    from athera_api.routers import literature
    from athera_api.services.literature import registry

    class BarrierRegistry(registry.SourceRegistry):
        name = "barrier"

        def __init__(self, barrier):
            self._barrier = barrier

        async def search(self, query, *, limit=20):
            return await self._barrier(query, limit=limit)

        async def get_by_doi(self, doi):
            return await self._barrier(doi)

    barrier = Barrier(result=lambda: [])
    monkeypatch.setattr(literature, "_registries", lambda: [BarrierRegistry(barrier)])

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], SOURCES_SEARCH,
        {"query": "الذكاء الاصطناعي في التعليم", "limit": 5}, barrier)

    assert barrier.calls == 1, "لم يُنادَ السجلُّ الخارجيّ"
    _assert_detached(during, pids, response)


async def test_02_references_search_holds_no_transaction_during_discovery(
    two_tenants, monkeypatch, test_engine,
):
    """`/references/search` — نداءُ الفهرسَين بلا معاملة."""
    from athera_api.discovery.contracts import DiscoveryResult
    from athera_api.routers import literature

    barrier = Barrier(result=lambda: DiscoveryResult(
        ranked=(), provider_statuses=(), external_link=None, query=None))
    monkeypatch.setattr(literature, "discover", barrier)

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], REFERENCES_SEARCH,
        {"query": "أثر التعلّم المدمج في التحصيل", "limit": 5}, barrier)

    assert barrier.calls == 1, "لم يُنادَ الاكتشاف"
    _assert_detached(during, pids, response)


async def test_03_sources_import_holds_no_transaction_during_doi_resolution(
    two_tenants, monkeypatch, test_engine,
):
    """`/sources/import` — حلُّ المعرّف بلا معاملة، ثمّ كتابةٌ قصيرة.

    والترتيبُ كان صحيحًا في المتن (الشبكةُ قبل الكتابة)، لكنّ
    `Depends(get_session)` تفتح المعاملةَ **قبل** أن يعمل المتن.
    """
    from athera_api.services.literature import registry, verification

    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-1", doi="10.1234/h3b-import",
        title="ورقةٌ للفحص", publication_year=2024, journal_name=None, issn=None,
        is_open_access=False, authors=[], retraction_status="none",
        retraction_detail=None, raw={},
    )
    barrier = Barrier(result=lambda: (record, "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", barrier)

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], SOURCES_IMPORT,
        {"doi": "10.1234/h3b-import"}, barrier)

    assert barrier.calls == 1, "لم يُنادَ حلُّ المعرّف"
    _assert_detached(during, pids, response, expect=201)


async def test_04_source_verify_holds_no_transaction_during_revalidation(
    two_tenants, monkeypatch, test_engine,
):
    """`/sources/{id}/verify` — ثلاثةُ أطوار، والشبكةُ في الأوسط بلا معاملة."""
    from athera_api.services.literature import registry, verification

    doi = f"10.1234/h3b-verify-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(two_tenants["a"], doi=doi)
    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-2", doi=doi, title="مصدرٌ للفحص",
        publication_year=2023, journal_name=None, issn=None, is_open_access=False,
        authors=[], retraction_status="none", retraction_detail=None, raw={},
    )
    barrier = Barrier(result=lambda: (record, "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", barrier)

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], f"/api/v1/sources/{source_id}/verify",
        None, barrier)

    assert barrier.calls == 1, "لم يُنادَ الفهرس"
    _assert_detached(during, pids, response)


async def test_05_profile_import_holds_no_transaction_during_storage_read(
    two_tenants, monkeypatch, test_engine,
):
    """`/profile/import` — قراءةُ التخزين بلا معاملة."""
    from athera_api.services import ingestion

    file_id = await _make_file(two_tenants["a"])
    barrier = Barrier(result=lambda: DOCUMENT)
    monkeypatch.setattr(ingestion, "load_object_bytes", barrier)

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], PROFILE_IMPORT,
        {"file_id": str(file_id), "extractor": "rules"}, barrier)

    assert barrier.calls == 1, "لم تُقرأ البايتات"
    _assert_detached(during, pids, response, expect=202)


async def test_06_thesis_parse_holds_no_transaction_during_storage_read(
    two_tenants, monkeypatch, test_engine,
):
    """`/theses/{id}/parse` — قراءةُ التخزين بلا معاملة."""
    from athera_api.services import ingestion

    thesis_id, _file_id = await _make_thesis_with_file(two_tenants["a"])
    barrier = Barrier(result=lambda: DOCUMENT)
    monkeypatch.setattr(ingestion, "load_object_bytes", barrier)

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], f"/api/v1/theses/{thesis_id}/parse",
        None, barrier)

    assert barrier.calls == 1, "لم تُقرأ البايتات"
    _assert_detached(during, pids, response, expect=202)


async def test_07_the_model_extractor_no_longer_holds_the_request_session(
    two_tenants, monkeypatch, test_engine,
):
    """**والمُستخرِجُ النموذجيُّ كان العطبَ السابع** — داخل `/profile/import`.

    وقياسُه على نداء النموذج نفسِه: يُحبَس المزوّد، ويُسأل `pg_stat_activity`.
    """
    import importlib.util

    from athera_api.config import get_settings
    from athera_api.providers import gateway
    from athera_api.providers.base import ModelResponse, ModelUsage
    from athera_api.services import ingestion

    file_id = await _make_file(two_tenants["a"])
    monkeypatch.setattr(ingestion, "load_object_bytes",
                        lambda key: _immediate(DOCUMENT))

    barrier = Barrier(result=lambda: ModelResponse(
        content="{}", provider="barrier", model="b",
        structured={"facts": []}, usage=ModelUsage(input_tokens=1, output_tokens=1,
                                                   latency_ms=1)))

    class BarrierProvider:
        name = "barrier"

        async def generate_structured(self, request):
            return await barrier(request)

        async def embed(self, texts, *, model=None):
            return [[0.0] * 4 for _ in texts]

        async def stream(self, request):
            yield ""

        async def tool_call(self, request):
            return await self.generate_structured(request)

    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only", raising=False)
    monkeypatch.setattr(settings, "model_external_send_max_classification", "C2",
                        raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(gateway, "build_provider", lambda: BarrierProvider())

    during, response, pids = await _measure(
        test_engine, two_tenants["a"], PROFILE_IMPORT,
        {"file_id": str(file_id), "extractor": "model"}, barrier)

    assert barrier.calls == 1, "لم يُنادَ النموذج"
    _assert_detached(during, pids, response, expect=202)


async def _immediate(value):
    return value


# ══════════════════ ٢ · دلالاتُ الإخفاق وفجوةُ الزمن ══════════════════


async def test_08_a_prepare_failure_never_reaches_the_external_call(
    two_tenants, monkeypatch,
):
    """**ملفٌّ غائبٌ يُردّ ٤٠٤ ولا يُقرأ التخزينُ أصلًا** (الطور H/١).

    والرمزُ والموضعُ كما كانا: الفحصُ في الطور الأوّل، قبل أيّ قراءة.
    """
    from athera_api.services import ingestion

    barrier = Barrier(result=lambda: DOCUMENT)
    monkeypatch.setattr(ingestion, "load_object_bytes", barrier)

    async with _client(two_tenants["a"]) as http:
        response = await http.post(PROFILE_IMPORT,
                                   json={"file_id": str(uuid.uuid4()),
                                         "extractor": "rules"})
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "file.not_found", response.text
    assert barrier.calls == 0, "قُرئ التخزينُ لملفٍّ لا وجود له"


async def test_09_an_external_failure_leaves_no_open_transaction(
    two_tenants, monkeypatch, test_engine,
):
    """إخفاقُ الشبكة: لا معاملةٌ باقية، ولا نجاحٌ كاذب (الطور H/٢)."""
    from athera_api.services.literature import verification

    barrier = Barrier(error=RuntimeError("registry refused on purpose"))
    monkeypatch.setattr(verification, "resolve_doi", barrier)

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            task = asyncio.create_task(
                http.post(SOURCES_IMPORT, json={"doi": "10.1234/h3b-fail"}))
            await asyncio.wait_for(barrier.entered.wait(), timeout=30)
            barrier.release.set()
            response = await task
        after = await open_transactions(watch.pids)

    assert barrier.calls == 1
    assert response.status_code >= 400, (
        f"إخفاقُ الشبكة رُدَّ نجاحًا: HTTP {response.status_code}")
    assert not after, f"معاملةٌ باقيةٌ بعد إخفاق الشبكة: {after}"


async def test_10_a_cancelled_request_leaves_no_open_transaction(
    two_tenants, monkeypatch, test_engine,
):
    """انقطاعُ الطلب أثناء الانتظار لا يُبقي معاملة (الطور H/٤)."""
    from athera_api.services import ingestion

    file_id = await _make_file(two_tenants["a"])
    barrier = Barrier(result=lambda: DOCUMENT)
    monkeypatch.setattr(ingestion, "load_object_bytes", barrier)

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            task = asyncio.create_task(
                http.post(PROFILE_IMPORT, json={"file_id": str(file_id),
                                                "extractor": "rules"}))
            await asyncio.wait_for(barrier.entered.wait(), timeout=30)
            during = await open_transactions(watch.pids)
            task.cancel()
            with pytest.raises(BaseException):  # noqa: B017, PT011
                await task
        await asyncio.sleep(0)
        after = await open_transactions(watch.pids)

    assert not during, f"معاملةٌ مفتوحةٌ عند نقطة الانتظار: {during}"
    assert not after, f"معاملةٌ باقيةٌ بعد الانقطاع: {after}"


async def test_11_a_failed_finalize_commit_is_never_reported_as_success(
    two_tenants, monkeypatch,
):
    """**الشبكةُ نجحت، وإيداعُ الكتابة أخفق ⇒ لا جوابَ نجاح** (الطور H/٥).

    والقيدُ مؤجَّلٌ حقيقيٌّ على `sources` — لا مُرقِّعٌ يزيّف `commit()`:
    الحدُّ المفحوصُ هو الإيداعُ نفسُه، كما في RC-T1-H1.

    **ونداءُ الفهرس لا يُرجَع** — ولا يُدَّعى ذلك.
    """
    from sqlalchemy import text

    from athera_api.services.literature import registry, verification

    doi = f"10.1234/h3b-bomb-{uuid.uuid4().hex[:8]}"
    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-3", doi=doi, title="عنوانٌ يُفجّر الإيداع",
        publication_year=2024, journal_name=None, issn=None, is_open_access=False,
        authors=[], retraction_status="none", retraction_detail=None, raw={},
    )
    barrier = Barrier(result=lambda: (record, "barrier"))
    barrier.release.set()
    monkeypatch.setattr(verification, "resolve_doi", barrier)

    engine, factory = await _observer()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "CREATE OR REPLACE FUNCTION athera_h3b_bomb() RETURNS trigger"
                    " LANGUAGE plpgsql AS $fn$ BEGIN"
                    "   IF NEW.title = 'عنوانٌ يُفجّر الإيداع' THEN"
                    "     RAISE EXCEPTION 'RC-T1-H3-B: planted commit failure';"
                    "   END IF; RETURN NEW; END $fn$"))
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_h3b_bomb_trg ON sources"))
                await session.execute(text(
                    "CREATE CONSTRAINT TRIGGER athera_h3b_bomb_trg AFTER INSERT"
                    " ON sources DEFERRABLE INITIALLY DEFERRED"
                    " FOR EACH ROW EXECUTE FUNCTION athera_h3b_bomb()"))
        async with _client(two_tenants["a"]) as http:
            response = await http.post(SOURCES_IMPORT, json={"doi": doi})
    finally:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_h3b_bomb_trg ON sources"))
                await session.execute(text(
                    "DROP FUNCTION IF EXISTS athera_h3b_bomb()"))
        await engine.dispose()

    assert barrier.calls == 1, "لم يُنادَ الفهرس — فالفحصُ لا يقيس الحالة"
    assert response.status_code >= 400, (
        "إخفاقُ الإيداع رُدَّ نجاحًا — RC-T1-H1: "
        f"HTTP {response.status_code}: {response.text[:300]}")


async def test_12_a_source_deleted_during_the_wait_fails_safely(
    two_tenants, monkeypatch,
):
    """**مصدرٌ حُذف أثناء الانتظار يُردّ ٤٠٤** — ولا يُكتب فوق فراغ (الطور G).

    وهذه فجوةُ الزمن التي أوجدها إغلاقُ المعاملة قبل الشبكة. فالإنهاءُ
    يُعيد تحميلَ الصفّ ولا يتّكل على قراءةٍ سابقة.
    """
    from sqlalchemy import delete

    from athera_api.db import tenant_session_maker
    from athera_api.models.literature import Source
    from athera_api.services.literature import registry, verification

    slot = two_tenants["a"]
    doi = f"10.1234/h3b-gone-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(slot, doi=doi)
    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-4", doi=doi, title="x",
        publication_year=2024, journal_name=None, issn=None, is_open_access=False,
        authors=[], retraction_status="none", retraction_detail=None, raw={},
    )

    async def vanish_then_resolve(*args, **kwargs):
        # يُحذف الصفُّ **في أثناء** الانتظار الخارجيّ — وهو ما تسمح به الفجوة.
        async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
            await s.execute(delete(Source).where(Source.id == source_id))
        return record, "barrier"

    monkeypatch.setattr(verification, "resolve_doi", vanish_then_resolve)

    async with _client(slot) as http:
        response = await http.post(f"/api/v1/sources/{source_id}/verify")
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "evidence.source_not_found", response.text


async def test_13_a_source_whose_doi_changed_during_the_wait_is_refused(
    two_tenants, monkeypatch,
):
    """**ولا يُكتب فحصُ ورقةٍ على ورقةٍ أخرى** — ٤٠٩ صريحة (الطور G).

    ولو ثُبِّت الفحصُ بلا هذا الحدّ لَكُتبت حالةُ سحبِ ورقةٍ على ورقةٍ
    مختلفة — وهو تلويثُ بيانات، لا مجرّدُ سباق.
    """
    from sqlalchemy import update

    from athera_api.db import tenant_session_maker
    from athera_api.models.literature import Source
    from athera_api.services.literature import registry, verification

    slot = two_tenants["a"]
    original = f"10.1234/h3b-was-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(slot, doi=original)
    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-5", doi=original, title="x",
        publication_year=2024, journal_name=None, issn=None, is_open_access=False,
        authors=[], retraction_status="retracted", retraction_detail="d", raw={},
    )

    async def change_then_resolve(*args, **kwargs):
        async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
            await s.execute(update(Source).where(Source.id == source_id)
                            .values(doi=f"10.9999/other-{uuid.uuid4().hex[:6]}"))
        return record, "barrier"

    monkeypatch.setattr(verification, "resolve_doi", change_then_resolve)

    async with _client(slot) as http:
        response = await http.post(f"/api/v1/sources/{source_id}/verify")
    assert response.status_code == 409, response.text
    body = response.json()["error"]
    assert body["code"] == "evidence.source_changed_during_verification", response.text
    # **ورسالةٌ تُقرأ، لا مفتاحٌ يُعرض.** كان الرمزُ يُرفع بلا مدخلٍ في
    # الكتالوج، فيرى الباحثُ المفتاحَ نفسَه — والفحصُ الذي يؤكّد الرمزَ
    # وحدَه لا يكشف ذلك.
    assert body["messages"]["ar"] != body["code"], body
    assert "تغيّر" in body["messages"]["ar"], body
    assert "changed" in body["messages"]["en"], body

    # **ولم تُكتب حالةُ السحب على الورقة الأخرى.**
    engine, factory = await _observer()
    try:
        from sqlalchemy import text

        async with factory() as session:
            status = (await session.execute(text(
                "SELECT retraction_status FROM sources WHERE id = :i"),
                {"i": str(source_id)})).scalar_one()
    finally:
        await engine.dispose()
    assert status == "none", f"كُتبت حالةُ سحبٍ على ورقةٍ أخرى: {status}"


async def test_14_a_thesis_deleted_during_the_wait_fails_safely(
    two_tenants, monkeypatch,
):
    """**والإذنُ يُعاد التحقّقُ منه بعد الانتظار** لأنّ ما بعده كتابة (الطور F).

    فالرسالةُ تُقرأ من جديد بالحارس نفسِه، ولا تُكتب أقسامٌ بصلاحيةٍ
    قُرِّرت قبل قراءة التخزين.
    """
    from sqlalchemy import delete

    from athera_api.db import tenant_session_maker
    from athera_api.models.thesis import Thesis
    from athera_api.services import ingestion

    slot = two_tenants["a"]
    thesis_id, _ = await _make_thesis_with_file(slot)

    async def vanish_then_read(_key):
        async with tenant_session_maker(slot["tenant_id"], slot["user_id"])() as s:
            await s.execute(delete(Thesis).where(Thesis.id == thesis_id))
        return DOCUMENT

    monkeypatch.setattr(ingestion, "load_object_bytes", vanish_then_read)

    async with _client(slot) as http:
        response = await http.post(f"/api/v1/theses/{thesis_id}/parse")
    # **والمحظورُ أن يُردّ نجاحٌ على رسالةٍ لا وجود لها.**
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] in (
        "thesis.not_found", "portfolio.thesis_not_found"), response.text


# ═════════════════ ٣ · العزلُ، وحملُ الحدّ، والتزامن ═════════════════


async def test_15_no_orm_object_can_cross_the_external_boundary() -> None:
    """ما يعبُر الحدَّ قيمٌ لا صفوفُ ORM (الطور E).

    و`load_object_bytes(storage_key: str)` توقيعٌ يفرض ذلك: مفتاحٌ نصّيّ لا
    صفُّ `File`. و`ModelExtractor` تقبل **دالّةَ جلسةٍ** لا جلسة.
    """
    import inspect

    from sqlalchemy.ext.asyncio import AsyncSession

    from athera_api.services.extraction.model import ModelExtractor
    from athera_api.services.ingestion import load_object_bytes

    signature = inspect.signature(load_object_bytes)
    assert list(signature.parameters) == ["storage_key"], signature
    annotation = signature.parameters["storage_key"].annotation
    assert annotation in (str, "str"), annotation

    extractor = inspect.signature(ModelExtractor.__init__)
    assert "session_or_maker" in extractor.parameters, extractor
    assert extractor.parameters["session_or_maker"].annotation is not AsyncSession


async def test_16_tenant_and_actor_context_do_not_leak_across_the_phases(
    two_tenants, monkeypatch,
):
    """**ولا يتسرّب سياقٌ بين المعاملات القصيرة** (الطور H).

    و`SET LOCAL` يموت مع كلّ معاملة ويُعاد ضبطُه مع التالية. فمستأجرٌ آخر
    لا يرى صفَّ هذا المسار، ولو تعدّدت معاملاته.
    """
    from sqlalchemy import text

    from athera_api.services.literature import registry, verification

    doi = f"10.1234/h3b-iso-{uuid.uuid4().hex[:8]}"
    record = registry.RegistryRecord(
        registry="barrier", registry_id="b-6", doi=doi, title="مصدرٌ معزول",
        publication_year=2024, journal_name=None, issn=None, is_open_access=False,
        authors=[], retraction_status="none", retraction_detail=None, raw={},
    )
    barrier = Barrier(result=lambda: (record, "barrier"))
    barrier.release.set()
    monkeypatch.setattr(verification, "resolve_doi", barrier)

    async with _client(two_tenants["a"]) as http:
        created = await http.post(SOURCES_IMPORT, json={"doi": doi})
    assert created.status_code == 201, created.text

    # مستأجرٌ آخر لا يراه.
    async with _client(two_tenants["b"]) as http:
        listed = await http.get("/api/v1/sources")
    assert listed.status_code == 200, listed.text
    assert all(item.get("doi") != doi for item in listed.json()), (
        "صفُّ مستأجرٍ ظهر لمستأجرٍ آخر")

    # ولا سياقَ باقٍ على أيّ اتصالٍ في المجمَّع.
    engine, factory = await _observer()
    try:
        async with factory() as session:
            leaked = (await session.execute(text(
                "SELECT count(*) FROM pg_settings"
                " WHERE name IN ('app.tenant_id','app.actor_id')"
                "   AND setting <> ''"))).scalar_one()
    finally:
        await engine.dispose()
    assert leaked == 0, "سياقُ مستأجرٍ أو فاعلٍ باقٍ على اتصالٍ راجع"


async def test_17_concurrent_network_waits_pin_no_transactions(
    two_tenants, monkeypatch, test_engine,
):
    """خمسةُ انتظاراتِ شبكةٍ متزامنة ⇒ **صفرُ معاملاتٍ محبوسة** (الطور M)."""
    from athera_api.discovery.contracts import DiscoveryResult
    from athera_api.routers import literature

    waves = 5
    arrived = asyncio.Semaphore(0)
    barrier = Barrier(result=lambda: DiscoveryResult(
        ranked=(), provider_statuses=(), external_link=None, query=None))

    async def counting(*args, **kwargs):
        arrived.release()
        return await barrier(*args, **kwargs)

    monkeypatch.setattr(literature, "discover", counting)

    with BackendWatch(test_engine) as watch:
        async with _client(two_tenants["a"]) as http:
            tasks = [asyncio.create_task(http.post(
                REFERENCES_SEARCH, json={"query": f"سؤالٌ رقم {n} عن التعلّم",
                                         "limit": 3}))
                     for n in range(waves)]
            for _ in range(waves):
                await asyncio.wait_for(arrived.acquire(), timeout=30)
            during = await open_transactions(watch.pids)
            barrier.release.set()
            responses = await asyncio.gather(*tasks)

    assert barrier.calls == waves, f"وصل الشبكةَ {barrier.calls} من {waves}"
    assert not during, (
        f"{len(during)} معاملةً محبوسةً و{waves} طلبًا تنتظر الشبكة: {during}")
    assert all(r.status_code == 200 for r in responses), (
        [r.status_code for r in responses])


async def test_18_concurrent_storage_waits_pin_no_transactions(
    two_tenants, monkeypatch, test_engine,
):
    """وأربعةُ انتظاراتِ تخزينٍ متزامنة ⇒ صفرُ معاملاتٍ محبوسة (الطور M)."""
    from athera_api.services import ingestion

    waves = 4
    slot = two_tenants["a"]
    files = [await _make_file(slot) for _ in range(waves)]
    arrived = asyncio.Semaphore(0)
    barrier = Barrier(result=lambda: DOCUMENT)

    async def counting(*args, **kwargs):
        arrived.release()
        return await barrier(*args, **kwargs)

    monkeypatch.setattr(ingestion, "load_object_bytes", counting)

    with BackendWatch(test_engine) as watch:
        async with _client(slot) as http:
            # **والمِلفُّ الشخصيُّ يُنشأ أوّلًا.** وإلّا تسابقت الطلباتُ
            # الأربعةُ على إنشائه، فتنتظر ثلاثةٌ قفلَ الفريد ولا تبلغ
            # الحاجزَ — فتسقط المهلةُ لسببٍ لا يقيسه الفحص.
            warm = await http.get("/api/v1/profile")
            assert warm.status_code == 200, warm.text

            tasks = [asyncio.create_task(http.post(
                PROFILE_IMPORT, json={"file_id": str(fid), "extractor": "rules"}))
                     for fid in files]
            for _ in range(waves):
                await asyncio.wait_for(arrived.acquire(), timeout=30)
            during = await open_transactions(watch.pids)
            barrier.release.set()
            await asyncio.gather(*tasks)

    assert barrier.calls == waves, f"وصل التخزينَ {barrier.calls} من {waves}"
    assert not during, (
        f"{len(during)} معاملةً محبوسةً و{waves} طلبًا تنتظر التخزين: {during}")


# ═══════════ ٤ · الدعوى النهائية: صفرٌ، ولا قائمةَ استثناءات ═══════════


def test_19_no_route_in_the_application_awaits_egress_under_a_transaction() -> None:
    """**الدعوى النهائيّة لـRC-T1-H3: صفرُ مسارات** (الطوران K و L).

    ولا قائمةَ استثناءاتٍ ولا سماحَ لأحد. ومسارٌ جديدٌ يقع في النمط يُسقط
    الحزمةَ ومعه سلسلةُ النداء كاملةً — من المسار إلى أوّليّة الشبكة.
    """
    from tests.external_wait_audit import audit

    result = audit()
    assert not result.missing_seeds, (
        "بذرةُ واجهةٍ فُقدت — أُعيد تشكيلُ الواجهة والحارسُ لم يُحدَّث:\n  "
        + "\n  ".join(result.missing_seeds))

    offenders = result.offenders()
    assert offenders == [], (
        "مسارٌ يمسك معاملةَ قاعدةٍ عبر انتظارٍ خارجيّ (RC-T1-H3):\n"
        + "\n".join(o.describe() for o in offenders)
        + "\n\nوالنمطُ الصحيح: تحضيرٌ قصير → الخارجُ بلا معاملة → إنهاءٌ قصير."
          "\nانظر docs/architecture/transactions.md §٦.")


def test_20_the_zero_offender_guard_would_notice_a_new_violation(tmp_path) -> None:
    """والحارسُ يعضّ — على شجرةٍ مُصطنَعةٍ تحمل النمط.

    ولا يُحتسب حارسٌ لم يُجرَّب: لو كان المسحُ يقرأ حقلًا خاطئًا لَمرّ أبدًا
    وهو لا يقيس شيئًا.
    """
    import pathlib
    import shutil

    from tests.external_wait_audit import audit

    real = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    staged = tmp_path / "athera_api"
    shutil.copytree(real, staged,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    probe = staged / "routers" / "zz_probe.py"
    probe.write_text(
        "from fastapi import APIRouter, Depends\n"
        "from sqlalchemy.ext.asyncio import AsyncSession\n"
        "from ..deps import Principal, get_principal, get_session\n"
        "from ..services.ingestion import load_object_bytes\n"
        "from ..transaction import TransactionalRoute\n"
        "router = APIRouter(route_class=TransactionalRoute)\n"
        "\n"
        "@router.post('/zz-probe')\n"
        "async def zz_probe(\n"
        "    principal: Principal = Depends(get_principal),\n"
        "    session: AsyncSession = Depends(get_session),\n"
        ") -> dict:\n"
        "    await load_object_bytes('k')\n"
        "    return {}\n",
        encoding="utf-8")

    offenders = audit(staged).offenders()
    assert [o.key for o in offenders] == [("zz_probe.py", "zz_probe")], (
        [o.key for o in offenders])
    assert offenders[0].kind == "STORAGE", offenders[0].kind
    assert "load_object_bytes" in offenders[0].describe()


def test_21_the_h3a_remaining_set_is_now_empty() -> None:
    """وقائمةُ H3-A المتبقّية صارت **فارغة** — ولم تُحذف، بل خلت.

    والحارسُ هناك بالمطابقة التامّة، فبقاؤه فارغًا دعوى: أنّ الستّةَ
    عُولجت، وأنّ لا سابعًا ظهر في مدى ذلك الماسح.
    """
    from tests.test_at_rc_t1_h3_ai_long_transactions import KNOWN_REMAINING

    assert KNOWN_REMAINING == set(), KNOWN_REMAINING


# ════════ ٥ · ذرّيّةُ الإخفاق: لا كتابةَ جزئيّةٌ على استيرادٍ فاشل ════════
#
# **وهذا عطبٌ أدخله RC-T1-H3-B نفسُه، وكشفته المراجعة.** كان
# `_get_or_create_profile` في طور التحضير — وهو **كتابة** — فتُودَع قبل
# قراءة التخزين. فإن أخفق الاستيراد بقي مِلفٌّ شخصيٌّ جديدٌ أثرًا لطلبٍ
# فاشل. وقبل هذا الطور كان الإنشاءُ والاستخراجُ في معاملةِ الطلب نفسِها
# فيرجعان معًا.
#
# **وتقصيرُ المعاملات لا يجوز أن يُضعف ذرّيّةً قائمة.**


async def _profile_count(tenant_id) -> int:
    """عددُ المِلفّات الشخصيّة — بحقوق المالك، فلا تُخفيها RLS."""
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return (await session.execute(text(
                "SELECT count(*) FROM researcher_profiles WHERE tenant_id = :t"),
                {"t": str(tenant_id)})).scalar_one()
    finally:
        await engine.dispose()


async def _extraction_counts(tenant_id) -> dict[str, int]:
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            out = {}
            for table in ("extraction_runs", "document_chunks", "fact_candidates"):
                out[table] = (await session.execute(text(
                    f"SELECT count(*) FROM {table} WHERE tenant_id = :t"),
                    {"t": str(tenant_id)})).scalar_one()
            return out
    finally:
        await engine.dispose()


async def test_22_a_storage_failure_leaves_no_new_researcher_profile(
    two_tenants, monkeypatch,
):
    """**إخفاقُ التخزين لا يُخلّف مِلفًّا شخصيًّا جديدًا** ولا صفَّ استخراج."""
    from athera_api.services import ingestion

    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    profiles_before = await _profile_count(slot["tenant_id"])
    rows_before = await _extraction_counts(slot["tenant_id"])
    assert profiles_before == 0, "المستأجرُ يملك مِلفًّا قبل الطلب — فالفحصُ لا يقيس"

    async def refuse(_key):
        raise RuntimeError("storage refused on purpose")

    monkeypatch.setattr(ingestion, "load_object_bytes", refuse)

    async with _client(slot) as http:
        response = await http.post(PROFILE_IMPORT,
                                   json={"file_id": str(file_id),
                                         "extractor": "rules"})

    assert response.status_code >= 400, (
        f"إخفاقُ التخزين رُدَّ نجاحًا: HTTP {response.status_code}")
    assert await _profile_count(slot["tenant_id"]) == profiles_before, (
        "بقي مِلفٌّ شخصيٌّ جديدٌ أثرًا لاستيرادٍ فاشل — كتابةٌ جزئيّة")
    assert await _extraction_counts(slot["tenant_id"]) == rows_before, (
        "بقيت صفوفُ استخراجٍ من استيرادٍ فاشل")


async def test_23_a_model_failure_leaves_no_new_researcher_profile(
    two_tenants, monkeypatch,
):
    """**وإخفاقُ النموذج كذلك** — والمُستخرِجُ النموذجيُّ يُنادى قبل الإنشاء."""
    import importlib.util

    from athera_api.config import get_settings
    from athera_api.providers import gateway
    from athera_api.services import ingestion

    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    profiles_before = await _profile_count(slot["tenant_id"])
    rows_before = await _extraction_counts(slot["tenant_id"])
    assert profiles_before == 0, "المستأجرُ يملك مِلفًّا قبل الطلب"

    async def read(_key):
        return DOCUMENT

    monkeypatch.setattr(ingestion, "load_object_bytes", read)

    class RefusingProvider:
        name = "refusing"

        async def generate_structured(self, request):
            raise RuntimeError("model refused on purpose")

        async def embed(self, texts, *, model=None):
            return [[0.0] * 4 for _ in texts]

        async def stream(self, request):
            yield ""

        async def tool_call(self, request):
            return await self.generate_structured(request)

    settings = get_settings()
    monkeypatch.setattr(settings, "model_provider", "openai", raising=False)
    monkeypatch.setattr(settings, "openai_api_key", "test-only", raising=False)
    monkeypatch.setattr(settings, "model_external_send_max_classification", "C2",
                        raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(gateway, "build_provider", lambda: RefusingProvider())

    async with _client(slot) as http:
        response = await http.post(PROFILE_IMPORT,
                                   json={"file_id": str(file_id),
                                         "extractor": "model"})

    assert response.status_code >= 400, (
        f"إخفاقُ النموذج رُدَّ نجاحًا: HTTP {response.status_code}")
    assert await _profile_count(slot["tenant_id"]) == profiles_before, (
        "بقي مِلفٌّ شخصيٌّ جديدٌ أثرًا لاستخراجٍ أخفق نموذجُه")
    assert await _extraction_counts(slot["tenant_id"]) == rows_before, (
        "بقيت صفوفُ استخراجٍ من استخراجٍ أخفق")


async def test_24_a_successful_import_creates_the_profile_and_the_extraction(
    two_tenants, monkeypatch,
):
    """**والنجاحُ يُنشئ الاثنين معًا** — فالذرّيّةُ ليست منعًا للنجاح."""
    from athera_api.services import ingestion

    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    assert await _profile_count(slot["tenant_id"]) == 0
    rows_before = await _extraction_counts(slot["tenant_id"])

    async def read(_key):
        return DOCUMENT

    monkeypatch.setattr(ingestion, "load_object_bytes", read)

    async with _client(slot) as http:
        response = await http.post(PROFILE_IMPORT,
                                   json={"file_id": str(file_id),
                                         "extractor": "rules"})

    assert response.status_code == 202, response.text
    assert await _profile_count(slot["tenant_id"]) == 1, "لم يُنشأ المِلفُّ الشخصيّ"
    rows_after = await _extraction_counts(slot["tenant_id"])
    assert rows_after["extraction_runs"] == rows_before["extraction_runs"] + 1, (
        rows_before, rows_after)
    assert rows_after["document_chunks"] > rows_before["document_chunks"], (
        rows_before, rows_after)


async def test_25_an_existing_profile_is_never_removed_by_a_failed_import(
    two_tenants, monkeypatch,
):
    """ومِلفٌّ كان قائمًا قبل الطلب لا يُحذف عند الإخفاق — ولا تعويضَ يُختلق."""
    from athera_api.services import ingestion

    slot = two_tenants["a"]
    file_id = await _make_file(slot)
    async with _client(slot) as http:
        warm = await http.get("/api/v1/profile")
        assert warm.status_code == 200, warm.text
    assert await _profile_count(slot["tenant_id"]) == 1

    async def refuse(_key):
        raise RuntimeError("storage refused on purpose")

    monkeypatch.setattr(ingestion, "load_object_bytes", refuse)
    async with _client(slot) as http:
        response = await http.post(PROFILE_IMPORT,
                                   json={"file_id": str(file_id),
                                         "extractor": "rules"})
    assert response.status_code >= 400, response.text
    assert await _profile_count(slot["tenant_id"]) == 1, (
        "حُذف مِلفٌّ كان قائمًا — والتعويضُ ليس مطلوبًا هنا أصلًا")


async def test_26_persistence_cannot_reach_outside_the_process_by_construction(
) -> None:
    """**والبنيةُ تمنع المسلك، لا الاتّفاق** — `ingest_file` تخزينٌ محضّ.

    وكانت `raw_bytes` و`proposal` اختياريّتَين و`extractor` كائنَ واجهة،
    فبقي فيها مسلكانِ يخرجان من العمليّة: قراءةُ تخزينٍ ونداءُ نموذج. وهي
    تُنادى **داخل معاملةٍ قصيرة** — فمستدعٍ ينسى أحدَ المُعطَيين غدًا
    يُمسك معاملةً عبر الشبكة. فصارت الثلاثةُ مطلوبة.
    """
    import inspect

    from athera_api.services.ingestion import ingest_file

    parameters = inspect.signature(ingest_file).parameters
    for name in ("extractor_name", "raw_bytes", "proposal"):
        assert name in parameters, (name, list(parameters))
        assert parameters[name].default is inspect.Parameter.empty, (
            f"`{name}` اختياريّةٌ — فالمسلكُ الخارجيُّ ما زال قائمًا")
    assert "extractor" not in parameters, (
        "كائنُ المُستخرِج ما زال يُمرَّر — والمسلكُ يعود من الباب الخلفيّ")

    source = inspect.getsource(ingest_file)
    assert ".propose(" not in source, "ما زالت تنادي مُستخرِجًا"
    assert "load_object_bytes" not in source and "_load_bytes" not in source, (
        "ما زالت تقرأ التخزين")


# ══════════ ٦ · الحارسُ يرى نمطَ مصنعِ الجلسات — وقد كان أعمى عنه ══════════
#
# **وهذه ثغرةٌ في الحارس نفسِه كشفتها المراجعة.** كان يطابق أسماءَ سياقٍ
# حرفيّةً، فلم يرَ النمطَ الذي أدخله هذا الطور:
#
#     session_maker = tenant_session_maker(...)
#     async with session_maker() as session:
#         await external_call()          ← مخالفةٌ لم تُكشف
#
# فصار يكتشف المصانعَ **من الشيفرة**: دالّةٌ تُعيد دالّةً تُعيد سياقَ جلسة.


def _staged_tree(tmp_path, probe_source: str, name: str = "zz_probe.py"):
    """شجرةٌ حقيقيّةٌ مُستنسخةٌ ومعها مسارٌ مُصطنَع — ثمّ تُمسح."""
    import pathlib
    import shutil

    from tests.external_wait_audit import audit

    real = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    staged = tmp_path / "athera_api"
    if not staged.exists():
        shutil.copytree(real, staged,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (staged / "routers" / name).write_text(probe_source, encoding="utf-8")
    return audit(staged).offenders()


_HEAD = (
    "from fastapi import APIRouter, Depends\n"
    "from sqlalchemy.ext.asyncio import AsyncSession\n"
    "from ..db import tenant_session, tenant_session_maker\n"
    "from ..deps import Principal, get_principal, get_session\n"
    "from ..services.ingestion import load_object_bytes\n"
    "from ..services.literature import verification\n"
    "from ..transaction import TransactionalRoute\n"
    "router = APIRouter(route_class=TransactionalRoute)\n\n"
)


def test_27_a_direct_tenant_session_context_offender_is_detected(tmp_path) -> None:
    """(ب) سياقٌ مباشرٌ يملكه المتن — `async with tenant_session(...)`."""
    offenders = _staged_tree(tmp_path, _HEAD + (
        "@router.post('/zz-direct')\n"
        "async def zz_direct(principal: Principal = Depends(get_principal)) -> dict:\n"
        "    async with tenant_session(principal.tenant_id, principal.user_id) as s:\n"
        "        await load_object_bytes('k')\n"
        "    return {}\n"), name="zz_direct.py")
    assert [o.key for o in offenders] == [("zz_direct.py", "zz_direct")], (
        [o.key for o in offenders])
    assert offenders[0].held_by == "handler body", offenders[0].held_by


def test_28_a_session_maker_alias_offender_is_detected(tmp_path) -> None:
    """(ج) **متغيّرُ مصنعٍ** — وهو ما كان الحارسُ أعمى عنه."""
    offenders = _staged_tree(tmp_path, _HEAD + (
        "@router.post('/zz-maker')\n"
        "async def zz_maker(principal: Principal = Depends(get_principal)) -> dict:\n"
        "    session_maker = tenant_session_maker(principal.tenant_id, principal.user_id)\n"
        "    async with session_maker() as session:\n"
        "        await load_object_bytes('k')\n"
        "    return {}\n"), name="zz_maker.py")
    assert [o.key for o in offenders] == [("zz_maker.py", "zz_maker")], (
        [o.key for o in offenders])
    assert offenders[0].kind == "STORAGE", offenders[0].kind


def test_29_a_renamed_maker_alias_is_detected(tmp_path) -> None:
    """(د) وبأيِّ اسم — فالمصنعُ يُعرَف بشكله لا باسم متغيّره."""
    offenders = _staged_tree(tmp_path, _HEAD + (
        "@router.post('/zz-renamed')\n"
        "async def zz_renamed(principal: Principal = Depends(get_principal)) -> dict:\n"
        "    whatever = tenant_session_maker(principal.tenant_id, principal.user_id)\n"
        "    async with whatever() as session:\n"
        "        await verification.resolve_doi([], '10.1/x')\n"
        "    return {}\n"), name="zz_renamed.py")
    assert [o.key for o in offenders] == [("zz_renamed.py", "zz_renamed")], (
        [o.key for o in offenders])
    assert offenders[0].kind == "NETWORK", offenders[0].kind


def test_30_a_direct_maker_expression_is_detected(tmp_path) -> None:
    """(هـ) ومصنعٌ يُنادى في موضعه — `async with tenant_session_maker(...)()`."""
    offenders = _staged_tree(tmp_path, _HEAD + (
        "@router.post('/zz-inline')\n"
        "async def zz_inline(principal: Principal = Depends(get_principal)) -> dict:\n"
        "    async with tenant_session_maker(\n"
        "            principal.tenant_id, principal.user_id)() as session:\n"
        "        await load_object_bytes('k')\n"
        "    return {}\n"), name="zz_inline.py")
    assert [o.key for o in offenders] == [("zz_inline.py", "zz_inline")], (
        [o.key for o in offenders])


def test_31_the_safe_detached_pattern_is_not_flagged(tmp_path) -> None:
    """**والنمطُ الصحيحُ لا يُتَّهم** — وهذه الدعوى الفارقة.

    فعمرُ متغيّرِ المصنع يمتدّ إلى آخر المعالج، أمّا **مدى المعاملة** فداخل
    `async with` وحدَه. ولو خلط الحارسُ بينهما لاتّهم كلَّ مسارٍ أصلحناه —
    فيصير عاجزًا عن التفريق بين العطب وعلاجه.
    """
    offenders = _staged_tree(tmp_path, _HEAD + (
        "from sqlalchemy import text\n\n"
        "@router.post('/zz-safe')\n"
        "async def zz_safe(principal: Principal = Depends(get_principal)) -> dict:\n"
        "    session_maker = tenant_session_maker(principal.tenant_id, principal.user_id)\n"
        "    async with session_maker() as session:\n"
        "        row = (await session.execute(text('SELECT 1'))).scalar_one()\n"
        "    payload = await load_object_bytes(str(row))\n"
        "    async with session_maker() as session:\n"
        "        await session.execute(text('SELECT 2'))\n"
        "    return {'bytes': len(payload)}\n"), name="zz_safe.py")
    assert offenders == [], (
        "اتُّهم النمطُ المنفصلُ الصحيح — فالحارسُ يخلط عمرَ المتغيّر بمدى "
        f"المعاملة: {[o.describe() for o in offenders]}")


def test_32_the_scanner_declares_what_it_discovered_and_what_it_lost() -> None:
    """وما يُكتشف يُقال، وما يُفقد يُقال — فلا حارسٌ يمرّ وهو أعمى.

    وواجهةٌ أو سياقٌ أُعيد تشكيلُه يُسقط الحارسَ صامتًا لو أُهمل.
    """
    from tests.external_wait_audit import audit

    result = audit()
    assert not result.missing_seeds, result.missing_seeds
    assert not result.missing_contexts, (
        "سياقُ جلسةٍ مُعلَنٌ لم يُعثر عليه في الشيفرة: "
        f"{result.missing_contexts}")
    assert "athera_api.db:tenant_session_maker" in result.maker_factories, (
        sorted(result.maker_factories))
    # **والمصانعُ تُكتشف لا تُعدّ**: ثلاثةٌ أُخرى في الموجّهات لم تُكتب هنا
    # بأسمائها، ويجدها المسحُ بشكلها.
    assert len(result.maker_factories) >= 4, sorted(result.maker_factories)
    assert result.session_contexts >= {"tenant_session", "project_session"}, (
        sorted(result.session_contexts))
