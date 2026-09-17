"""RC-T1-H2-B2 — **إجارةٌ على مساراتِ القراءةِ الخارجيّة** | leased external reads.

## ما يُغلق هنا

الطور A أغلق الجوابَ الغامضَ للطفرات **الذرّيّة في القاعدة**: طلبٌ واحدٌ،
معاملةٌ واحدة، و`ON CONFLICT` حَكَمٌ. والطور B-1 بنى أوّليّاتِ الإجارة
والسياج وأثبتها على PostgreSQL. وهذه الدفعةُ **تستعملها على أربعة مسارات**
انتظارُها خارجيّ، فلا تكفيها ذرّيّةُ معاملةٍ واحدة:

    POST /sources/search             قراءةٌ خارجيّة + تدقيقُ إفصاح
    POST /references/search          قراءةٌ خارجيّة + تدقيقُ إفصاح
    POST /sources/import             قراءةٌ خارجيّة + طفرةُ مجال
    POST /sources/{source_id}/verify قراءةٌ خارجيّة + طفرةُ مجال

## وما لا يُدَّعى، صريحًا

**لا «مرّةً واحدةً بالضبط».** الفهرسُ الخارجيُّ يُسأل مرّتين إن أُعيد
الطلبُ بعد انتهاء الإجارة، ولا سلطةَ لنا على أثرٍ خارج قاعدتنا. وما
يُضمَن: **أنّ طفرتَنا وإتمامَنا يقعان معًا أو لا يقعان**، وأنّ عاملًا فقد
إجارتَه **لا يُودِع شيئًا**.

**ولا إعادةٌ لمن لا مفتاحَ له.** الترويسةُ اختياريّة، ومن أغفلها يسلك
المسلكَ القديم حرفيًّا — وهذا مقيسٌ هنا لا مُفترَض (§٤).

## والقياسُ على قاعدةٍ حقيقيّة

لا مُحاكاةَ إيداعٍ ولا قفلَ ذاكرة: الحَكَمُ `uq_idempotency_scope`
و`lease_expires_at` على PostgreSQL. والحبسُ الخارجيُّ بـ`Barrier` — وهو
**الاعتمادُ** المُزيَّف، لا حدُّ المعاملة.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.test_at_rc_t1_h3b_remaining_external_waits import (
    Barrier,
    _make_source,
)
from tests.test_at_rc_t1_h3_ai_long_transactions import _client, _observer

pytestmark = pytest.mark.asyncio

SOURCES_SEARCH = "/api/v1/sources/search"
REFERENCES_SEARCH = "/api/v1/references/search"
SOURCES_IMPORT = "/api/v1/sources/import"

HEADER = "Idempotency-Key"


def _key() -> str:
    """مفتاحٌ صالحُ الشكل — ٣٢ محرفًا ست عشريًّا."""
    return uuid.uuid4().hex


# ═══════════════════════ تجهيزاتٌ محليّة ═══════════════════════


@pytest.fixture(autouse=True)
def _reset_throttle():
    from athera_api.discovery import throttle

    throttle.reset()
    yield
    throttle.reset()


async def _scalar(sql: str, params: dict):
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return (await session.execute(text(sql), params)).scalar_one()
    finally:
        await engine.dispose()


async def _rows(sql: str, params: dict) -> list[tuple]:
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return [tuple(r) for r in (await session.execute(text(sql), params)).all()]
    finally:
        await engine.dispose()


async def _records(tenant_id, operation: str | None = None) -> int:
    if operation is None:
        return await _scalar(
            "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
            {"t": str(tenant_id)})
    return await _scalar(
        "SELECT count(*) FROM idempotency_records "
        "WHERE tenant_id = :t AND operation = :o",
        {"t": str(tenant_id), "o": operation})


async def _record(tenant_id, key: str) -> tuple:
    """(الحال، الرمز، الجسم، انتهاءُ الإجارة، العمليّة) لمفتاحٍ واحد."""
    from athera_api.services.idempotency import digest_key

    return (await _rows(
        "SELECT state, response_status, response_body, lease_expires_at, operation"
        "  FROM idempotency_records"
        " WHERE tenant_id = :t AND key_digest = :d",
        {"t": str(tenant_id), "d": digest_key(key)}))[0]


async def _sources(tenant_id, doi: str) -> int:
    return await _scalar(
        "SELECT count(*) FROM sources WHERE tenant_id = :t AND doi = :d",
        {"t": str(tenant_id), "d": doi})


async def _audit_rows(tenant_id, action: str) -> int:
    return await _scalar(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t AND action = :a",
        {"t": str(tenant_id), "a": action})


def _barrier_registry(barrier):
    from athera_api.services.literature import registry

    class BarrierRegistry(registry.SourceRegistry):
        name = "barrier"

        def __init__(self, b):
            self._b = b

        async def search(self, query, *, limit=20):
            return await self._b(query, limit=limit)

        async def get_by_doi(self, doi):
            return await self._b(doi)

    return BarrierRegistry(barrier)


def _record_for(doi: str):
    from athera_api.services.literature import registry

    return registry.RegistryRecord(
        registry="barrier", registry_id=f"b-{uuid.uuid4().hex[:6]}", doi=doi,
        title="ورقةٌ للفحص", publication_year=2024, journal_name=None, issn=None,
        is_open_access=False, authors=[], retraction_status="none",
        retraction_detail=None, raw={})


def _empty_discovery():
    from athera_api.discovery.contracts import DiscoveryResult

    return DiscoveryResult(ranked=(), provider_statuses=(), external_link=None,
                           query=None)


async def _hold(slot, url, payload, barrier, *, key, method="post"):
    """يُطلق طلبًا يحبسه الحاجزُ عند الاعتماد الخارجيّ — ويعيد مهمّتَه.

    فتُملَك الإجارةُ فعلًا **أثناء** ما يجري الفحصُ طلبًا ثانيًا. وهذا هو
    الفرقُ عن مُحاكاةِ صفٍّ يُدسّ باليد: الحالُ حالُ عاملٍ حقيقيّ.
    """
    http = _client(slot)
    await http.__aenter__()
    send = getattr(http, method)
    task = asyncio.create_task(
        send(url, json=payload, headers={HEADER: key}) if payload is not None
        else send(url, headers={HEADER: key}))
    reached = asyncio.create_task(barrier.entered.wait())
    done, _ = await asyncio.wait({task, reached}, timeout=30,
                                 return_when=asyncio.FIRST_COMPLETED)
    if reached not in done:
        reached.cancel()
        if task in done:
            answered = task.result()
            await http.__aexit__(None, None, None)
            raise AssertionError(
                "لم يبلغ الطلبُ الاعتمادَ الخارجيّ — فلا إجارةَ محبوسة. "
                f"HTTP {answered.status_code}: {answered.text[:400]}")
        task.cancel()
        await http.__aexit__(None, None, None)
        raise AssertionError("لم يبلغ الطلبُ الاعتمادَ ولم يُجب — مهلةٌ")
    return http, task


# ═════════ ١ · بلا مفتاح: السلوكُ القديم **حرفيًّا** ═════════


async def test_01_a_request_without_a_key_behaves_exactly_as_before(
    two_tenants, monkeypatch,
):
    """أربعةُ مساراتٍ بلا ترويسة: تُجيب كما كانت، **وصفرُ صفوفِ إجارة**.

    وهذا شرطُ المهمّة الحرفيّ: «للطلبات بلا `Idempotency-Key` حافظ على
    السلوك الحاليّ بالضبط». فلو حُجز صفٌّ لمن لم يطلب لَصار المسارُ يكتب
    ما لم يُؤمَر به.
    """
    from athera_api.routers import literature
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    before = await _records(slot["tenant_id"])

    monkeypatch.setattr(literature, "_registries",
                        lambda: [_barrier_registry(_instant([]))])
    monkeypatch.setattr(literature, "discover", _instant(_empty_discovery()))
    doi = f"10.1234/h2b2-nokey-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))

    async with _client(slot) as http:
        one = await http.post(SOURCES_SEARCH, json={"query": "بحثٌ", "limit": 5})
        two = await http.post(REFERENCES_SEARCH, json={"query": "بحثٌ", "limit": 5})
        three = await http.post(SOURCES_IMPORT, json={"doi": doi})
        source_id = three.json()["id"]
        four = await http.post(f"/api/v1/sources/{source_id}/verify")

    assert one.status_code == 200, one.text
    assert two.status_code == 200, two.text
    assert three.status_code == 201, three.text
    assert four.status_code == 200, four.text
    for answered in (one, two, three, four):
        assert "Idempotency-Replayed" not in answered.headers, \
            "طلبٌ بلا مفتاحٍ وُسم إعادةً"

    assert await _records(slot["tenant_id"]) == before, \
        "طلبٌ بلا مفتاحٍ كتب صفَّ إجارة — والسلوكُ القديم لم يُحفَظ"


def _instant(result):
    """اعتمادٌ خارجيٌّ يعود فورًا — لا حبس. يعيد نفسَ القيمة كلَّ مرّة."""
    barrier = Barrier(result=lambda: result)
    barrier.release.set()
    return barrier


# ═════════ ٢ · الإعادة: الجوابُ **حرفيًّا** من الصفّ ═════════


@pytest.mark.parametrize(
    ("label", "url", "payload", "expect"),
    [("search", SOURCES_SEARCH, {"query": "بحثٌ مُعاد", "limit": 5}, 200),
     ("references", REFERENCES_SEARCH, {"query": "بحثٌ مُعاد", "limit": 5}, 200),
     ("import", SOURCES_IMPORT, None, 201)],
)
async def test_02_a_completed_key_replays_the_stored_answer(
    two_tenants, monkeypatch, label, url, payload, expect,
):
    """المفتاحُ نفسُه مرّتين ⇒ جوابٌ واحدٌ بعينه، **ولا نداءَ خارجيٍّ ثانٍ**.

    والإعادةُ تُعلَن بترويسة `Idempotency-Replayed` — فيَعلم العميلُ أنّ
    ما أخذه جوابٌ مخزَّن لا عملٌ جديد.

    **والتساوي في المعنى لا في البايتات، وهذا مقيسٌ لا مُتساهَلٌ فيه:**
    `response_body` عمودُ `JSONB`، و`JSONB` لا يحفظ ترتيبَ المفاتيح — فقِيس
    أنّ الجسمَ المُعادَ يخرج بترتيبٍ آخر ومحتوًى واحد. وهذا **عقدُ الطور A
    المنشورُ نفسُه** (`first.json() == second.json()` هناك). وحفظُ البايتات
    حرفيًّا يقتضي عمودًا نصّيًّا — أي هجرةً جديدة، وهي غيرُ مأذونٍ بها في
    هذه الدفعة. فيُقال الحدُّ ولا يُدَّعى ما ليس واقعًا.
    """
    from athera_api.routers import literature
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-replay-{label}-{uuid.uuid4().hex[:8]}"
    if payload is None:
        payload = {"doi": doi}

    calls = _instant([])
    monkeypatch.setattr(literature, "_registries", lambda: [_barrier_registry(calls)])
    monkeypatch.setattr(literature, "discover", _instant(_empty_discovery()))
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))
    external = {"search": calls, "references": literature.discover,
                "import": verification.resolve_doi}[label]

    key = _key()
    async with _client(slot) as http:
        one = await http.post(url, json=payload, headers={HEADER: key})
        after_first = external.calls
        two = await http.post(url, json=payload, headers={HEADER: key})

    assert one.status_code == expect, one.text
    assert two.status_code == expect, two.text
    assert two.json() == one.json(), "الإعادةُ لم تُعِد الجوابَ نفسَه"
    assert sorted(two.text) == sorted(one.text), "الإعادةُ غيّرت المحتوى لا الترتيبَ"
    assert two.headers.get("Idempotency-Replayed") == "true", \
        "الإعادةُ لم تُعلَن بالترويسة"
    assert external.calls == after_first, \
        "الإعادةُ نادت الاعتمادَ الخارجيَّ مرّةً ثانية"


async def test_03_a_replayed_import_creates_no_second_source(
    two_tenants, monkeypatch,
):
    """الإعادةُ لا تُنشئ مصدرًا ثانيًا — **وهذا العطبُ المقيسُ أصلًا**."""
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-once-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))

    key = _key()
    async with _client(slot) as http:
        one = await http.post(SOURCES_IMPORT, json={"doi": doi},
                              headers={HEADER: key})
        two = await http.post(SOURCES_IMPORT, json={"doi": doi},
                              headers={HEADER: key})

    assert one.status_code == 201 and two.status_code == 201
    assert one.json()["id"] == two.json()["id"], "مُعرّفان لنيّةٍ واحدة"
    assert await _sources(slot["tenant_id"], doi) == 1, \
        "الإعادةُ أنشأت مصدرًا ثانيًا"


# ═════════ ٣ · التزامن: إجارةٌ حيّةٌ تُردّ بـ٤٠٩ ═════════


@pytest.mark.parametrize(
    ("label", "url", "payload"),
    [("search", SOURCES_SEARCH, {"query": "تزامنٌ", "limit": 5}),
     ("import", SOURCES_IMPORT, None)],
)
async def test_04_a_live_lease_refuses_the_twin_with_in_progress(
    two_tenants, monkeypatch, label, url, payload,
):
    """طلبان بمفتاحٍ واحدٍ معًا: الأوّلُ يعمل، والثاني **يُردّ ٤٠٩** فورًا.

    ولا يُترك الثاني يُنادي الفهرسَ موازيًا — فذاك أثرٌ خارجيٌّ مزدوجٌ
    لنيّةٍ واحدة، وهو ما جاءت الإجارةُ تمنعه.
    """
    from athera_api.routers import literature
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-race-{label}-{uuid.uuid4().hex[:8]}"
    if payload is None:
        payload = {"doi": doi}

    held = Barrier(result=lambda: ([] if label == "search"
                                   else (_record_for(doi), "barrier")))
    if label == "search":
        monkeypatch.setattr(literature, "_registries",
                            lambda: [_barrier_registry(held)])
    else:
        monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, url, payload, held, key=key)
    try:
        # الإجارةُ محبوسةٌ الآن عند الاعتماد الخارجيّ — فيصل التوأم.
        #
        # **وبمهلةٍ مقصودة:** التوأمُ الذي لا يُردّ يمضي إلى الاعتمادِ
        # المحبوسِ فيتجمّد إلى الأبد، فيصير الانحدارُ تعليقًا لا إخفاقًا —
        # وقد قِيس ذلك: إلغاءُ الرفضِ جمّد الفحصَ ولم يُفشِله. والمهلةُ
        # تجعل الانحدارَ يُقرأ سطرًا واحدًا.
        async with _client(slot) as other:
            try:
                twin = await asyncio.wait_for(
                    other.post(url, json=payload, headers={HEADER: key}),
                    timeout=10)
            except TimeoutError:
                raise AssertionError(
                    "التوأمُ لم يُردّ ومضى إلى الاعتمادِ الخارجيّ — فالإجارةُ "
                    "الحيّةُ لا تمنع أثرًا خارجيًّا مزدوجًا") from None
        assert twin.status_code == 409, \
            f"التوأمُ لم يُردّ أثناء إجارةٍ حيّة: {twin.status_code} {twin.text[:300]}"
        assert twin.json()["error"]["code"] == "idempotency.in_progress", twin.text
        assert held.calls == 1, \
            f"الاعتمادُ الخارجيُّ نُودي {held.calls} مرّةً لنيّةٍ واحدة"
    finally:
        held.release.set()
        answered = await first
        await http.__aexit__(None, None, None)
    assert answered.status_code in (200, 201), answered.text


async def test_05_the_refused_twin_writes_nothing(two_tenants, monkeypatch):
    """التوأمُ المردودُ **لا يكتب**: لا مصدرَ، ولا تدقيقًا، ولا صفًّا ثانيًا."""
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-nowrite-{uuid.uuid4().hex[:8]}"
    held = Barrier(result=lambda: (_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, SOURCES_IMPORT, {"doi": doi}, held, key=key)
    try:
        records_before = await _records(slot["tenant_id"])
        async with _client(slot) as other:
            twin = await other.post(SOURCES_IMPORT, json={"doi": doi},
                                    headers={HEADER: key})
        assert twin.status_code == 409, twin.text
        assert await _records(slot["tenant_id"]) == records_before, \
            "التوأمُ المردودُ كتب صفَّ إجارةٍ ثانيًا"
        assert await _sources(slot["tenant_id"], doi) == 0, \
            "التوأمُ المردودُ أنشأ مصدرًا قبل أن يُنهي الأوّل"
    finally:
        held.release.set()
        await first
        await http.__aexit__(None, None, None)
    assert await _sources(slot["tenant_id"], doi) == 1, "الأوّلُ لم يُنشئ مصدرَه"


# ═════════ ٤ · التعارض: مفتاحٌ أُعيد بجسمٍ آخر ═════════


async def test_06_the_same_key_with_a_different_body_is_a_conflict(
    two_tenants, monkeypatch,
):
    """مفتاحٌ واحدٌ ونيّتان ⇒ ٤٠٩ `key_reused` — **ولا يُنفَّذ الثاني**."""
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    first_doi = f"10.1234/h2b2-conflict-a-{uuid.uuid4().hex[:8]}"
    second_doi = f"10.1234/h2b2-conflict-b-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(
        verification, "resolve_doi",
        _instant((_record_for(first_doi), "barrier")))

    key = _key()
    async with _client(slot) as http:
        one = await http.post(SOURCES_IMPORT, json={"doi": first_doi},
                              headers={HEADER: key})
        two = await http.post(SOURCES_IMPORT, json={"doi": second_doi},
                              headers={HEADER: key})

    assert one.status_code == 201, one.text
    assert two.status_code == 409, two.text
    assert two.json()["error"]["code"] == "idempotency.key_reused", two.text
    assert await _sources(slot["tenant_id"], second_doi) == 0, \
        "التعارضُ نُفِّذ بدل أن يُردّ"


async def test_07_the_conflict_audit_survives_the_refusal(
    two_tenants, monkeypatch,
):
    """حدثُ التعارضِ **يُودَع** — والرفعُ كان يمحوه مع الرجوع (الطور A).

    وهذا هو الدرسُ المقيسُ هناك: `audit.record` تأخذ قفلًا **مدى
    المعاملة**، فمعاملةٌ ثانيةٌ للتدقيق تتجمّد. فيُكتب الحدثُ في المعاملةِ
    الحيّة ويُعاد الرفضُ **قيمةً** لا رفعًا.
    """
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    first_doi = f"10.1234/h2b2-audit-a-{uuid.uuid4().hex[:8]}"
    second_doi = f"10.1234/h2b2-audit-b-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(first_doi), "barrier")))

    before = await _audit_rows(slot["tenant_id"], "idempotency.conflict")
    key = _key()
    async with _client(slot) as http:
        await http.post(SOURCES_IMPORT, json={"doi": first_doi},
                        headers={HEADER: key})
        two = await http.post(SOURCES_IMPORT, json={"doi": second_doi},
                              headers={HEADER: key})
    assert two.status_code == 409, two.text
    after = await _audit_rows(slot["tenant_id"], "idempotency.conflict")
    assert after == before + 1, \
        f"حدثُ التعارضِ لم يُودَع (قبل={before} بعد={after})"


# ═════════ ٥ · السياج: عاملٌ بائتٌ لا يُودِع شيئًا ═════════


async def test_08_a_superseded_worker_commits_absolutely_nothing(
    two_tenants, monkeypatch,
):
    """الاستيلاءُ بعد انتهاء الإجارة ⇒ البائتُ يُردّ ٤٠٩ **بصفرِ طفرات**.

    وهذا شرطُ المهمّة الحرفيّ: «صفرُ مصادر، وصفرُ تدقيق/مجال، وصفرُ إتمام».
    ويُقاس بأن تُنتهى إجارةُ الأوّلِ **على ساعة القاعدة** فيستولي الثاني،
    ثمّ يُفَكّ الأوّلُ فيجد سياجَه قد تغيّر.
    """
    from sqlalchemy import text

    from athera_api.services.idempotency import digest_key
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-fence-{uuid.uuid4().hex[:8]}"
    held = Barrier(result=lambda: (_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, SOURCES_IMPORT, {"doi": doi}, held, key=key)
    try:
        # تُنتهى إجارةُ الأوّلِ **بساعةِ القاعدة** لا بانتظارٍ حقيقيّ.
        engine, factory = await _observer()
        try:
            async with factory() as session:
                await session.execute(
                    text("UPDATE idempotency_records "
                         "   SET lease_expires_at = now() - interval '1 second'"
                         " WHERE tenant_id = :t AND key_digest = :d"),
                    {"t": str(slot["tenant_id"]), "d": digest_key(key)})
                await session.commit()
        finally:
            await engine.dispose()

        # يستولي الثاني — والاستيلاءُ يزيد السياجَ حتمًا (الطور B-1).
        monkeypatch.setattr(verification, "resolve_doi",
                            _instant((_record_for(doi), "barrier")))
        async with _client(slot) as taker:
            took = await taker.post(SOURCES_IMPORT, json={"doi": doi},
                                    headers={HEADER: key})
        assert took.status_code == 201, f"الاستيلاءُ لم ينجح: {took.text[:300]}"
        sources_after_takeover = await _sources(slot["tenant_id"], doi)
        audit_after_takeover = await _audit_rows(slot["tenant_id"],
                                                 "evidence.source_imported")
    finally:
        held.release.set()
        stale = await first
        await http.__aexit__(None, None, None)

    assert stale.status_code == 409, \
        f"البائتُ لم يُردّ: {stale.status_code} {stale.text[:300]}"
    assert stale.json()["error"]["code"] == "idempotency.lease_superseded", stale.text
    assert await _sources(slot["tenant_id"], doi) == sources_after_takeover, \
        "البائتُ أودع مصدرًا بعد أن فقد إجارتَه"
    assert await _audit_rows(slot["tenant_id"], "evidence.source_imported") \
        == audit_after_takeover, "البائتُ أودع حدثَ تدقيقٍ بعد أن فقد إجارتَه"
    state, status_code, _body, _expires, _op = await _record(slot["tenant_id"], key)
    assert state == "completed", f"الحالُ ليس مُتمًّا: {state}"
    assert status_code == 201, "الإتمامُ المخزَّنُ ليس جوابَ المُستولي"


async def test_09_the_stale_worker_does_not_overwrite_the_winners_answer(
    two_tenants, monkeypatch,
):
    """الصفُّ المخزَّنُ يبقى **جوابَ المُستولي** لا جوابَ البائت.

    فلو كتب البائتُ فوقَه لَأعاد المسارُ لاحقًا جوابًا لطفرةٍ رُجِعت —
    وذاك أسوأُ من الغموض: يقينٌ كاذب.
    """
    from sqlalchemy import text

    from athera_api.services.idempotency import digest_key
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-nooverwrite-{uuid.uuid4().hex[:8]}"
    held = Barrier(result=lambda: (_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, SOURCES_IMPORT, {"doi": doi}, held, key=key)
    try:
        engine, factory = await _observer()
        try:
            async with factory() as session:
                await session.execute(
                    text("UPDATE idempotency_records "
                         "   SET lease_expires_at = now() - interval '1 second'"
                         " WHERE tenant_id = :t AND key_digest = :d"),
                    {"t": str(slot["tenant_id"]), "d": digest_key(key)})
                await session.commit()
        finally:
            await engine.dispose()
        monkeypatch.setattr(verification, "resolve_doi",
                            _instant((_record_for(doi), "barrier")))
        async with _client(slot) as taker:
            took = await taker.post(SOURCES_IMPORT, json={"doi": doi},
                                    headers={HEADER: key})
        assert took.status_code == 201, took.text
        winner_id = took.json()["id"]
    finally:
        held.release.set()
        await first
        await http.__aexit__(None, None, None)

    async with _client(slot) as http2:
        replay = await http2.post(SOURCES_IMPORT, json={"doi": doi},
                                  headers={HEADER: key})
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == winner_id, \
        "الإعادةُ أعادت جوابَ البائت لا جوابَ المُستولي"


# ═════════ ٦ · العزل: المفتاحُ لا يعبُر مستأجرًا ولا مسارًا ═════════


async def test_10_the_same_key_in_another_tenant_is_a_separate_intent(
    two_tenants, monkeypatch,
):
    """مفتاحٌ واحدٌ ومستأجران ⇒ عملان مستقلّان، ولا إعادةَ عبر الحدّ."""
    from athera_api.services.literature import verification

    doi_a = f"10.1234/h2b2-tenant-a-{uuid.uuid4().hex[:8]}"
    doi_b = f"10.1234/h2b2-tenant-b-{uuid.uuid4().hex[:8]}"
    key = _key()

    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi_a), "barrier")))
    async with _client(two_tenants["a"]) as http:
        one = await http.post(SOURCES_IMPORT, json={"doi": doi_a},
                              headers={HEADER: key})
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi_b), "barrier")))
    async with _client(two_tenants["b"]) as http:
        two = await http.post(SOURCES_IMPORT, json={"doi": doi_b},
                              headers={HEADER: key})

    assert one.status_code == 201, one.text
    assert two.status_code == 201, two.text
    assert "Idempotency-Replayed" not in two.headers, \
        "مفتاحُ مستأجرٍ أعاد جوابًا لمستأجرٍ آخر"
    assert await _sources(two_tenants["b"]["tenant_id"], doi_b) == 1


async def test_11_the_same_key_on_two_routes_is_two_operations(
    two_tenants, monkeypatch,
):
    """المفتاحُ مقيَّدٌ بالعمليّة: بحثٌ واستيرادٌ بمفتاحٍ واحدٍ لا يتعارضان."""
    from athera_api.routers import literature
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-tworoutes-{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(literature, "_registries",
                        lambda: [_barrier_registry(_instant([]))])
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))

    key = _key()
    async with _client(slot) as http:
        one = await http.post(SOURCES_SEARCH, json={"query": "بحثٌ", "limit": 5},
                              headers={HEADER: key})
        two = await http.post(SOURCES_IMPORT, json={"doi": doi},
                              headers={HEADER: key})
    assert one.status_code == 200, one.text
    assert two.status_code == 201, two.text
    assert "Idempotency-Replayed" not in two.headers, \
        "مفتاحُ مسارٍ أعاد جوابَ مسارٍ آخر"


async def test_12_the_operation_name_is_the_route_template_not_the_url(
    two_tenants, monkeypatch,
):
    """`/sources/{source_id}/verify` **عمليّةٌ واحدة** لكلّ المصادر.

    وكان هذا مكسورًا: `scope["route_path"]` مفتاحٌ لا يضعه أحدٌ — لا
    Starlette ولا هذا المستودع — فكان الاسمُ يسقط إلى العنوان المُستبدَل،
    فيصير لكلّ مصدرٍ فضاءُ مفاتيحَ خاصٌّ به. ولو بقي كذلك لَما كُشف مفتاحٌ
    أُعيد على مصدرٍ آخر.
    """
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-op-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(slot, doi=doi)
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))

    key = _key()
    async with _client(slot) as http:
        answered = await http.post(f"/api/v1/sources/{source_id}/verify",
                                   headers={HEADER: key})
    assert answered.status_code == 200, answered.text

    _state, _code, _body, _expires, operation = await _record(slot["tenant_id"], key)
    assert operation == "POST /api/v1/sources/{source_id}/verify", \
        f"اسمُ العمليّة يحمل معرّفًا بدل القالب: {operation!r}"
    assert str(source_id) not in operation, \
        "معرّفُ المصدرِ دخل اسمَ العمليّة — ففضاءُ المفاتيح انقسم"


async def test_13_the_same_key_on_two_different_sources_is_a_conflict(
    two_tenants, monkeypatch,
):
    """مفتاحٌ واحدٌ على مصدرَين ⇒ ٤٠٩ — **لأنّ المعرّفَ في البصمة**.

    والجسمُ فارغٌ في هذا المسار، فلو لم يدخل `source_id` البصمةَ لَأعاد
    المفتاحُ جوابَ المصدرِ الأوّلِ على الثاني: فحصٌ يُنسَب لورقةٍ لم تُفحَص.
    """
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi_one = f"10.1234/h2b2-src1-{uuid.uuid4().hex[:8]}"
    doi_two = f"10.1234/h2b2-src2-{uuid.uuid4().hex[:8]}"
    one_id = await _make_source(slot, doi=doi_one)
    two_id = await _make_source(slot, doi=doi_two)

    key = _key()
    async with _client(slot) as http:
        monkeypatch.setattr(verification, "resolve_doi",
                            _instant((_record_for(doi_one), "barrier")))
        first = await http.post(f"/api/v1/sources/{one_id}/verify",
                                headers={HEADER: key})
        monkeypatch.setattr(verification, "resolve_doi",
                            _instant((_record_for(doi_two), "barrier")))
        second = await http.post(f"/api/v1/sources/{two_id}/verify",
                                 headers={HEADER: key})

    assert first.status_code == 200, first.text
    assert second.status_code == 409, \
        f"مفتاحٌ أُعيد على مصدرٍ آخر ولم يُكشَف: {second.status_code}"
    assert second.json()["error"]["code"] == "idempotency.key_reused", second.text


# ═════════ ٧ · الإخفاقُ المعلومُ يبقى صادقًا ═════════


async def test_14_an_unresolvable_doi_fails_the_key_and_stays_retryable(
    two_tenants, monkeypatch,
):
    """معرّفٌ لا يُحَلّ ⇒ ٤٠٤ كما كان، والصفُّ `failed` **لا `completed`**.

    ولا يُخزَّن ٤٠٤ جوابًا يُعاد: الإخفاقُ الخارجيُّ قد يكون عارضًا،
    فيبقى المفتاحُ قابلًا لمحاولةٍ صادقةٍ بعده.
    """
    from athera_api.services.literature import registry, verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-missing-{uuid.uuid4().hex[:8]}"

    async def _missing(*_a, **_k):
        raise registry.SourceNotFound(doi)

    monkeypatch.setattr(verification, "resolve_doi", _missing)

    key = _key()
    async with _client(slot) as http:
        answered = await http.post(SOURCES_IMPORT, json={"doi": doi},
                                   headers={HEADER: key})
    assert answered.status_code == 404, answered.text
    assert answered.json()["error"]["code"] == "evidence.doi_not_resolved", answered.text

    state, code, _body, _expires, _op = await _record(slot["tenant_id"], key)
    assert state == "failed", f"الحالُ بعد إخفاقٍ معلومٍ: {state}"
    assert code is None, "٤٠٤ خُزِّن جوابًا يُعاد"
    assert await _sources(slot["tenant_id"], doi) == 0, "مصدرٌ مختلقٌ خُزِّن"

    # ومحاولةٌ ثانيةٌ بالمفتاح نفسِه **تُنفَّذ** ولا تُردّ إعادةً.
    monkeypatch.setattr(verification, "resolve_doi",
                        _instant((_record_for(doi), "barrier")))
    async with _client(slot) as http:
        retried = await http.post(SOURCES_IMPORT, json={"doi": doi},
                                  headers={HEADER: key})
    assert retried.status_code == 201, \
        f"المفتاحُ سُمِّم بإخفاقٍ عارض: {retried.status_code} {retried.text[:300]}"
    assert await _sources(slot["tenant_id"], doi) == 1


async def test_15_a_rate_limited_request_never_burns_its_key(
    two_tenants, monkeypatch,
):
    """٤٢٩ **قبل** الحجز: من رُدّ بالحدِّ لا يُحجَز مفتاحُه.

    فلو حُجز لَصار العميلُ المؤدَّبُ — يُعيد بالمفتاح نفسِه كما أُمر —
    يُردّ ٤٠٩ إلى الأبد على طلبٍ لم يُنفَّذ أصلًا.
    """
    from athera_api.discovery import throttle
    from athera_api.routers import literature

    slot = two_tenants["a"]
    monkeypatch.setattr(literature, "discover", _instant(_empty_discovery()))

    key = _key()
    async with _client(slot) as http:
        # يُستنفَد الحدُّ بطلباتٍ **بلا مفتاح** حتى يُردّ ٤٢٩.
        limited = None
        for _ in range(40):
            answered = await http.post(REFERENCES_SEARCH,
                                       json={"query": "حدٌّ", "limit": 5})
            if answered.status_code == 429:
                limited = answered
                break
        assert limited is not None, "لم يُبلَغ حدُّ المعدّل — فالفحصُ لا يقيس شيئًا"

        keyed = await http.post(REFERENCES_SEARCH, json={"query": "حدٌّ", "limit": 5},
                                headers={HEADER: key})
    assert keyed.status_code == 429, \
        f"الحدُّ لم يُطبَّق على الطلبِ المُمفتَح: {keyed.status_code}"

    rows = await _rows(
        "SELECT state FROM idempotency_records "
        "WHERE tenant_id = :t AND key_digest = :d",
        {"t": str(slot["tenant_id"]),
         "d": __import__("athera_api.services.idempotency",
                         fromlist=["digest_key"]).digest_key(key)})
    assert rows == [], f"٤٢٩ حجز مفتاحًا: {rows}"
    throttle.reset()


async def test_16_a_malformed_key_is_refused_before_any_work(
    two_tenants, monkeypatch,
):
    """مفتاحٌ مشوَّهُ الشكل ⇒ ٤٠٠، **ولا نداءَ خارجيًّا ولا صفًّا**."""
    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-badkey-{uuid.uuid4().hex[:8]}"
    external = _instant((_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", external)

    before = await _records(slot["tenant_id"])
    async with _client(slot) as http:
        # ويُختار مشوَّهٌ **ASCII**: غيرُ ASCII ترفضه httpx قبل الإرسال،
        # فلا يبلغ المُدقِّقَ أصلًا — فيكون الفحصُ يقيس العميلَ لا الخادم.
        answered = await http.post(SOURCES_IMPORT, json={"doi": doi},
                                   headers={HEADER: "not a valid key!!"})
    assert answered.status_code == 400, answered.text
    assert answered.json()["error"]["code"] == "idempotency.key_invalid", answered.text
    assert external.calls == 0, "نُودي الفهرسُ بمفتاحٍ مشوَّه"
    assert await _records(slot["tenant_id"]) == before, "مفتاحٌ مشوَّهٌ كتب صفًّا"


# ═════════ ٨ · حرّاسُ الفجوةِ لم تُمَسّ ═════════


async def test_17_a_source_deleted_during_the_wait_still_fails_truthfully(
    two_tenants, monkeypatch,
):
    """مصدرٌ حُذف أثناء الانتظار ⇒ إخفاقٌ صادقٌ، **والإجارةُ لا تُخفيه**.

    وهذا حارسُ `RC-T1-H3-B`: الحالُ تُقاس على القاعدة وقت الكتابة لا وقت
    القراءة. والإجارةُ أُضيفت فوقَه ولا تُبدِله.
    """
    from sqlalchemy import text

    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-deleted-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(slot, doi=doi)
    held = Barrier(result=lambda: (_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, f"/api/v1/sources/{source_id}/verify", None,
                              held, key=key)
    try:
        engine, factory = await _observer()
        try:
            async with factory() as session:
                await session.execute(
                    text("DELETE FROM sources WHERE id = :i"), {"i": str(source_id)})
                await session.commit()
        finally:
            await engine.dispose()
    finally:
        held.release.set()
        answered = await first
        await http.__aexit__(None, None, None)

    assert answered.status_code >= 400, \
        f"مصدرٌ حُذف أثناء الانتظارِ أُجيب نجاحًا: {answered.status_code}"
    state, code, _body, _expires, _op = await _record(slot["tenant_id"], key)
    assert state != "completed", \
        f"إخفاقٌ خُزِّن إتمامًا يُعاد: state={state} status={code}"


async def test_18_a_doi_changed_during_the_wait_still_conflicts(
    two_tenants, monkeypatch,
):
    """معرّفٌ تغيّر أثناء الانتظار ⇒ تعارضٌ، ولا يُكتب فحصُ ورقةٍ على أخرى."""
    from sqlalchemy import text

    from athera_api.services.literature import verification

    slot = two_tenants["a"]
    doi = f"10.1234/h2b2-changed-{uuid.uuid4().hex[:8]}"
    other = f"10.1234/h2b2-changed-other-{uuid.uuid4().hex[:8]}"
    source_id = await _make_source(slot, doi=doi)
    held = Barrier(result=lambda: (_record_for(doi), "barrier"))
    monkeypatch.setattr(verification, "resolve_doi", held)

    key = _key()
    http, first = await _hold(slot, f"/api/v1/sources/{source_id}/verify", None,
                              held, key=key)
    try:
        engine, factory = await _observer()
        try:
            async with factory() as session:
                await session.execute(
                    text("UPDATE sources SET doi = :d WHERE id = :i"),
                    {"d": other, "i": str(source_id)})
                await session.commit()
        finally:
            await engine.dispose()
    finally:
        held.release.set()
        answered = await first
        await http.__aexit__(None, None, None)

    assert answered.status_code >= 400, \
        f"معرّفٌ تغيّر أثناء الانتظارِ أُجيب نجاحًا: {answered.status_code}"
    state, _code, _body, _expires, _op = await _record(slot["tenant_id"], key)
    assert state != "completed", "تعارضُ الفجوةِ خُزِّن إتمامًا يُعاد"


# ═════════ ٩ · الشكل: التبنّي مقيسٌ لا مُدَّعى ═════════


def test_19_all_four_routes_actually_take_a_lease() -> None:
    """الأربعةُ تُنادي `begin_leased*` و`settle_leased` — **بنيويًّا**.

    ولا يكفي وجودُ النصّ في الملفّ: يُطلب أن يكون النداءُ **داخل** المعالج
    بعينه. وحضورُ سلسلةٍ ليس دعوى (درسٌ تكرّر في هذه السلسلة ثلاث مرّات).
    """
    import ast
    import pathlib

    src = pathlib.Path("athera_api/routers/literature.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    wanted = {"search_sources", "discover_references", "import_source",
              "revalidate_source"}
    seen: dict[str, set[str]] = {}
    for fn in tree.body:
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name in wanted:
            calls = set()
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
            seen[fn.name] = calls

    assert set(seen) == wanted, f"معالجٌ مفقود: {wanted - set(seen)}"
    for name, calls in seen.items():
        assert calls & {"begin_leased", "begin_leased_in"}, \
            f"{name} لا يأخذ إجارةً"
        assert "settle_leased" in calls, f"{name} لا يُنهي تحت السياج"


def test_20_the_operation_helper_reads_the_key_fastapi_actually_sets() -> None:
    """`_operation_of` تقرأ `scope["route"]` — **لا مفتاحًا لا يضعه أحد**.

    وهذا العطبُ كان حيًّا في الطور A أيضًا. ومساراتُه الأربعةُ بلا معاملٍ
    في المسار، فالتصحيحُ لا يُغيّر اسمَ عمليّةٍ لمفتاحٍ قائم — لكنّه كان
    ليكسر هذا الطورَ لولا أن كُشف.
    """
    import ast
    import inspect

    from athera_api.services import idempotency

    src = inspect.getsource(idempotency._operation_of)
    subscripts = {
        node.slice.value
        for node in ast.walk(ast.parse(src.lstrip()))
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
    }
    constants = {
        node.value for node in ast.walk(ast.parse(src.lstrip()))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "route_path" not in (subscripts | constants), \
        "لا يزال يُقرأ `route_path` — وهو مفتاحٌ لا يضعه أحد"
    assert "route" in (subscripts | constants), \
        "لا يُقرأ `scope['route']` — فالقالبُ لا يُبلَغ"
