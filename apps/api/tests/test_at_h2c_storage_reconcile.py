"""H2-C — **تنظيفُ الأجيال ومصالحةُ الكائنات المهجورة** | Stage 8.

## ما يُقاس هنا

  ١ **التنظيفُ العامّ** يبلغ الآن المساراتِ المُجارة (B2…B5) كما يبلغ الطور A،
    ويُزيل المنتهيَ المحسوم — **ولا يمسّ `in_progress` أبدًا**.
  ٢ **المُصالِح** يحذف كائنَ جيلٍ مهجورٍ **حين يُثبَت هجرُه وحده**: لا صفَّ
    يشير إليه، وإجارتُه منقضيةٌ منذ مهلةٍ كافية، وسياجُه سياجُ الصيانة.

والمقياسُ الذي لا يُساوَم عليه:

    صفُّ File قائم  +  كائنُه محذوف   ⇒   لا يقع أبدًا

**والكائناتُ اليتيمةُ تُصنع بالمسار الحقيقيّ** — رفعٌ مُمفتَحٌ يسقط داخل
معاملة الإنهاء بعد نجاح التخزين — لا بإدراجٍ يدويٍّ يُحاكي ما لم يقع.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import threading
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1_h2b3_file_storage import (
    HEADER,
    UPLOAD,
    CountingStore,
    _audits,
    _client,
    _derived,
    _expire_lease,
    _files,
    _generation,
    _key,
    _observer,
    _record,
    _retire_generation,
    _rows,
    _scalar,
    _upload_kwargs,
)

pytestmark = pytest.mark.asyncio


class ReconcileStore(CountingStore):
    """المخزنُ العادّ نفسُه — ومعه السردُ وإخفاقاتٌ عند الطلب."""

    def __init__(self) -> None:
        super().__init__()
        self.list_calls: list[str] = []
        self.list_fail: BaseException | None = None
        self.delete_fail: BaseException | None = None
        #: حبسٌ **بعد** الكتابة — عاملٌ كتب ثمّ توقّف قبل الإنهاء.
        self.pause_after_put: threading.Event | None = None
        self.paused: threading.Event | None = None
        self.on_list = None

    def put_stream(self, key: str, fileobj, content_type: str) -> None:
        super().put_stream(key, fileobj, content_type)
        if self.pause_after_put is not None:
            gate, self.pause_after_put = self.pause_after_put, None
            if self.paused is not None:
                self.paused.set()
            gate.wait(timeout=60)

    def list_prefix(self, prefix: str, *, limit: int) -> list[str]:
        self.list_calls.append(prefix)
        if self.on_list is not None:
            self.on_list()
        if self.list_fail is not None:
            raise self.list_fail
        return sorted(k for k in self.objects if k.startswith(prefix))[:max(1, limit)]

    def delete(self, key: str) -> None:
        if self.delete_fail is not None:
            raise self.delete_fail
        super().delete(key)


@pytest.fixture
def store(monkeypatch) -> ReconcileStore:
    from athera_api.services import storage

    made = ReconcileStore()
    monkeypatch.setattr(storage, "get_store", lambda: made)
    return made


async def _sql(statement: str, params: dict) -> None:
    from sqlalchemy import text

    engine, factory = await _observer()
    try:
        async with factory() as session:
            await session.execute(text(statement), params)
            await session.commit()
    finally:
        await engine.dispose()


async def _abandon(slot, store, monkeypatch, *, key: str | None = None) -> tuple[str, str]:
    """جيلٌ مهجورٌ حقيقيّ: تخزينٌ نجح، ثمّ ماتت معاملةُ الإنهاء.

    ثمّ يُشاخ السياجُ ساعتين بساعة القاعدة — أبعدَ من مهلة المُصالِح.
    """
    from athera_api.routers import files as files_router

    key = key or _key()
    real = files_router.audit.record
    fired = {"n": 0}

    async def _explode(*a, **k):
        if fired["n"] == 0:
            fired["n"] += 1
            raise RuntimeError("process died mid-finalize")
        return await real(*a, **k)

    monkeypatch.setattr(files_router.audit, "record", _explode)
    async with _client(slot) as http:
        fell = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    monkeypatch.setattr(files_router.audit, "record", real)
    assert fell.status_code >= 500, fell.status_code
    record_id = str(await _generation(slot["tenant_id"], key))
    await _sql("UPDATE idempotency_records SET lease_expires_at = now() - interval '2 hours'"
               " WHERE id = :i", {"i": record_id})
    return key, record_id


async def _reconcile(slot, store, *, apply: bool = True, **kw):
    from athera_api.services import storage_reconcile

    return await storage_reconcile.reconcile(
        tenant_id=slot["tenant_id"], actor_id=slot["user_id"], apply=apply,
        store=store, **kw)


async def _state(record_id: str):
    rows = await _rows("SELECT state, lease_expires_at FROM idempotency_records WHERE id = :i",
                       {"i": record_id})
    return rows[0] if rows else None


def _prefix(slot, record_id: str) -> str:
    from athera_api.services import storage

    return storage.stable_file_prefix(slot["tenant_id"], slot["user_id"],
                                      uuid.UUID(_derived(record_id)))


async def _fresh_leased_generation(slot) -> None:
    """جيلٌ **مُجارٌ** جديدٌ يفوز بإجارته — وهو ما يُطلق التنظيفَ الآن."""
    async with _client(slot) as http:
        ok = await http.post(UPLOAD, **_upload_kwargs(filename="trigger.txt"),
                             headers={HEADER: _key()})
    assert ok.status_code == 201, ok.text


# ═════════ ١ · التنظيفُ العامُّ يبلغ المساراتِ المُجارة ═════════


@requires_db
async def test_01_an_expired_completed_generation_is_housekept_by_a_leased_flow(
    two_tenants, store,
):
    """**وكان الطورُ A وحدَه يبلغ التنظيف.** والرفعُ مُجارٌ (B3)."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        done = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert done.status_code == 201
    await _retire_generation(slot["tenant_id"], key)

    await _fresh_leased_generation(slot)
    assert await _record(slot["tenant_id"], key) == (), \
        "جيلٌ منتهٍ محسومٌ بقي — والمسارُ المُجار لا ينظّف"
    # والصفُّ المحسومُ لا يعني الملفّ: الملفُّ باقٍ.
    assert await _files(slot["tenant_id"], done.json()["id"]) == 1


@requires_db
async def test_02_an_expired_failed_generation_is_housekept(two_tenants, store):
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        done = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    record_id = str(await _generation(slot["tenant_id"], key))
    # حالٌ `failed` تُصنع بعبارةٍ صريحة — ولا مسارَ كتابةِ تخزينٍ ينتجها
    # (انظر `test_15`)، فالمقصودُ هنا حكمُ التنظيف على الحال لا منشؤها.
    await _sql("UPDATE idempotency_records SET state='failed', response_status=NULL,"
               " response_body=NULL, lease_expires_at=NULL,"
               " expires_at = now() - interval '1 second' WHERE id = :i",
               {"i": record_id})
    assert done.status_code == 201

    await _fresh_leased_generation(slot)
    assert await _state(record_id) is None, "جيلٌ منتهٍ فاشلٌ بقي بعد التنظيف"


@requires_db
async def test_03_an_ambiguous_in_progress_generation_is_never_housekept(
    two_tenants, store, monkeypatch,
):
    """**مرساةُ المصالحة لا تُمحى بتنظيفٍ عامّ** — ولو انقضى بقاؤها."""
    slot = two_tenants["a"]
    _key_, record_id = await _abandon(slot, store, monkeypatch)
    await _sql("UPDATE idempotency_records SET expires_at = now() - interval '1 day'"
               " WHERE id = :i", {"i": record_id})

    await _fresh_leased_generation(slot)
    assert (await _state(record_id))[0] == "in_progress", \
        "التنظيفُ العامُّ محا جيلًا غامضًا — وهو مرساةُ كائنٍ في المخزن"


# ═════════ ٢ · المُصالِح: متى لا يحذف ═════════


@requires_db
async def test_04_a_candidate_inside_the_safe_age_is_not_touched(
    two_tenants, store, monkeypatch,
):
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    # انقضت الإجارةُ منذ ثانيةٍ فقط — لا منذ ساعة.
    await _sql("UPDATE idempotency_records SET lease_expires_at = now() - interval '1 second'"
               " WHERE id = :i", {"i": record_id})

    outcomes = await _reconcile(slot, store)
    assert outcomes == [], f"مرشّحٌ داخل المهلة: {outcomes}"
    assert store.delete_calls == [] and store.list_calls == []
    assert len(store.objects) == 1


@requires_db
async def test_05_a_generation_whose_file_row_exists_is_never_deleted(
    two_tenants, store,
):
    """**صفُّ File قائم ⇒ لا حذف.** ويرجع السياجُ فلا يُحبَس مفتاحٌ سليم."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        done = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert done.status_code == 201
    record_id = str(await _generation(slot["tenant_id"], key))
    # جيلٌ غامضٌ **وله** صفُّ ملفّ — ما لا ينتجه المسار، ويجب أن يصمد له المُصالِح.
    await _sql("UPDATE idempotency_records SET state='in_progress', response_status=NULL,"
               " response_body=NULL, completed_at=NULL,"
               " lease_expires_at = now() - interval '2 hours' WHERE id = :i",
               {"i": record_id})
    before = await _state(record_id)

    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["skipped_domain_row"], outcomes
    assert store.delete_calls == [], "حُذف كائنٌ له صفُّ File"
    assert len(store.objects) == 1
    assert await _files(slot["tenant_id"], done.json()["id"]) == 1
    assert await _state(record_id) == before, "السياجُ بقي بعد الرفض — مفتاحٌ سليمٌ محبوس"


# ═════════ ٣ · البادئةُ التامّةُ وحدودُ النطاق ═════════


@requires_db
async def test_06_only_the_exact_file_prefix_is_listed_and_deleted(
    two_tenants, store, monkeypatch,
):
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    prefix = _prefix(slot, record_id)
    orphan = next(iter(store.objects))
    assert orphan.startswith(prefix)
    # جارٌ في مجلّد الفاعل نفسِه، وملفٌّ آخرُ للمستخدم.
    sibling = prefix.replace(_derived(record_id), str(uuid.uuid4())) + "sibling.txt"
    store.objects[sibling] = (b"x", "text/plain")

    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["reconciled"], outcomes
    # كلُّ سردٍ بالبادئة التامّة وحدَها — والسردُ الثاني تحقّقٌ من النظافة
    # قبل طيِّ الجيل، لا مسحٌ لشيءٍ آخر.
    assert set(store.list_calls) == {prefix}, f"سُرد ما لم يُطلب: {store.list_calls}"
    assert len(store.list_calls) == 2, store.list_calls
    assert store.delete_calls == [orphan], store.delete_calls
    assert sibling in store.objects, "مُسّ ملفٌّ جار"


@requires_db
async def test_07_a_neighbour_sharing_the_id_text_is_untouched(
    two_tenants, store, monkeypatch,
):
    """**والشرطةُ الختاميّةُ هي الحدّ** — لا طولُ المعرّف."""
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    prefix = _prefix(slot, record_id)
    lookalike = prefix.rstrip("/") + "0/not-mine.txt"
    store.objects[lookalike] = (b"x", "text/plain")

    await _reconcile(slot, store)
    assert lookalike in store.objects, "حُذف كائنٌ يشارك المعرّفَ نصًّا لا هُويّة"


@requires_db
async def test_08_another_tenants_orphan_is_untouched(two_tenants, store, monkeypatch):
    a, b = two_tenants["a"], two_tenants["b"]
    _ka, rec_a = await _abandon(a, store, monkeypatch)
    _kb, rec_b = await _abandon(b, store, monkeypatch)
    theirs = next(k for k in store.objects if k.startswith(_prefix(b, rec_b)))

    outcomes = await _reconcile(a, store)
    assert [o.record_id for o in outcomes] == [rec_a], outcomes
    assert theirs in store.objects, "صُولح كائنُ مستأجرٍ آخر"
    assert (await _state(rec_b))[0] == "in_progress"


@requires_db
async def test_09_another_actors_orphan_is_untouched_under_rls(
    two_tenants, store, monkeypatch,
):
    from tests.test_at_rc_t1a_project_access import _second_user

    a = two_tenants["a"]
    colleague = await _second_user(a["tenant_id"],
                                   email=f"h2c-{uuid.uuid4().hex[:10]}@example.com")
    _ka, rec_a = await _abandon(a, store, monkeypatch)
    _kc, rec_c = await _abandon(colleague, store, monkeypatch)
    theirs = next(k for k in store.objects if k.startswith(_prefix(colleague, rec_c)))

    outcomes = await _reconcile(a, store)
    assert [o.record_id for o in outcomes] == [rec_a], \
        f"رأى المُصالِحُ جيلَ فاعلٍ آخر: {outcomes}"
    assert theirs in store.objects
    assert (await _state(rec_c))[0] == "in_progress"


# ═════════ ٤ · الإخفاقُ يترك المرساة، والتكرارُ آمن ═════════


@requires_db
async def test_10_a_list_failure_keeps_the_anchor_and_a_later_run_finishes(
    two_tenants, store, monkeypatch,
):
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    store.list_fail = ConnectionError("s3 unreachable")

    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["list_failed"], outcomes
    assert (await _state(record_id))[0] == "in_progress", "سقطت المرساةُ مع السرد"
    assert len(store.objects) == 1

    # سياجُ الصيانة يحجب الجولةَ التالية حتى ينقضي — ثمّ تُتمّ.
    assert await _reconcile(slot, store) == []
    store.list_fail = None
    await _sql("UPDATE idempotency_records SET lease_expires_at = now() - interval '2 hours'"
               " WHERE id = :i", {"i": record_id})
    again = await _reconcile(slot, store)
    assert [o.status for o in again] == ["reconciled"], again
    assert store.objects == {}


@requires_db
async def test_11_a_delete_failure_keeps_the_anchor(two_tenants, store, monkeypatch):
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    store.delete_fail = TimeoutError("delete timed out")

    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["delete_failed"], outcomes
    assert (await _state(record_id))[0] == "in_progress"
    assert len(store.objects) == 1, "عُدّ الكائنُ محذوفًا ولم يُحذف"
    assert await _audits(slot["tenant_id"], "storage.orphan_reconciled") == 0


@requires_db
async def test_12_a_reconciled_orphan_then_a_rerun_and_a_retry_stay_consistent(
    two_tenants, store, monkeypatch,
):
    """تشغيلةٌ ثانيةٌ لا تفعل شيئًا — وإعادةُ العميل بالمفتاح نفسِه تُتمّ صحيحًا."""
    slot = two_tenants["a"]
    key, record_id = await _abandon(slot, store, monkeypatch)
    file_id = _derived(record_id)

    first = await _reconcile(slot, store)
    assert [o.status for o in first] == ["reconciled"], first
    assert store.objects == {}
    assert (await _state(record_id))[0] == "failed", "الجيلُ لم يُسجَّل إخفاقًا معلومًا"
    assert await _files(slot["tenant_id"], file_id) == 0
    assert await _audits(slot["tenant_id"], "storage.orphan_reconciled", file_id) == 1

    assert await _reconcile(slot, store) == [], "تشغيلةٌ ثانيةٌ وجدت ما تفعله"
    assert await _audits(slot["tenant_id"], "storage.orphan_reconciled", file_id) == 1

    # **والإعادةُ بعد المصالحة**: يستولي العميلُ على الجيل الفاشل نفسِه
    # (المعرّفُ ثابت) فيكتب ويُنهي — ملفٌّ وكائنٌ معًا.
    async with _client(slot) as http:
        retried = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert retried.status_code == 201, retried.text
    assert retried.json()["id"] == file_id
    assert len(store.objects) == 1
    assert await _files(slot["tenant_id"], file_id) == 1


# ═════════ ٥ · البائتُ بعد الصيانة — المقياسُ الذي لا يُساوَم عليه ═════════


@requires_db
async def test_13_a_stale_worker_cannot_finalize_a_file_onto_a_deleted_object(
    two_tenants, store,
):
    """عاملٌ كتب الكائنَ ثمّ توقّف؛ صالحته الصيانةُ وحذفته؛ ثمّ استيقظ.

    **فلا يُودَع له صفُّ File** — سياجُ الصيانة أبطل سياجه، فرجعت معاملةُ
    إنهائه كلُّها. ولولا ذلك لَصار: صفٌّ قائمٌ يشير إلى كائنٍ محذوف.
    """
    slot = two_tenants["a"]
    key = _key()
    store.pause_after_put = threading.Event()
    store.paused = threading.Event()
    gate = store.pause_after_put

    http = _client(slot)
    await http.__aenter__()
    worker = asyncio.create_task(
        http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key}))
    try:
        deadline = asyncio.get_running_loop().time() + 30
        while not store.paused.is_set():
            assert asyncio.get_running_loop().time() < deadline, "لم يبلغ العاملُ المخزن"
            await asyncio.sleep(0.01)
        record_id = str(await _generation(slot["tenant_id"], key))
        await _sql("UPDATE idempotency_records SET lease_expires_at = now() - interval '2 hours'"
                   " WHERE id = :i", {"i": record_id})
        outcomes = await _reconcile(slot, store)
        assert [o.status for o in outcomes] == ["reconciled"], outcomes
        assert store.objects == {}
    finally:
        gate.set()
        answered = await worker
        await http.__aexit__(None, None, None)

    assert answered.status_code == 409, \
        f"البائتُ أُجيب نجاحًا بعد الصيانة: {answered.status_code} {answered.text[:200]}"
    assert answered.json()["error"]["code"] == "idempotency.lease_superseded"
    file_id = _derived(record_id)
    assert await _files(slot["tenant_id"], file_id) == 0, \
        "صفُّ File قائمٌ وكائنُه محذوف — أسوأُ ما يمكن أن تنتجه صيانة"
    assert store.objects == {}


@requires_db
async def test_14_a_lease_losing_its_margin_mid_run_deletes_nothing(
    two_tenants, store, monkeypatch,
):
    """**قبل كلِّ حذفٍ يُسأل السياج.** أجلٌ بلا هامشٍ كافٍ ⇒ لا حذف."""
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)

    loop = asyncio.get_running_loop()

    def _shrink():
        # بين السرد والحذف: يتقلّص أجلُ الصيانة دون هامش الحذف.
        #
        # **وعلى الحلقة القائمة لا على حلقةٍ تُبنى** (حارسُ الحزمة يمنعها):
        # السردُ يجري في خيطٍ جانبيّ والحلقةُ حرّةٌ تنتظره، فيُرسَل إليها.
        asyncio.run_coroutine_threadsafe(_sql(
            "UPDATE idempotency_records SET lease_expires_at = now() + interval '1 minute'"
            " WHERE id = :i", {"i": record_id}), loop).result(timeout=30)

    store.on_list = _shrink
    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["contended"], outcomes
    assert store.delete_calls == [], "حُذف والأجلُ بلا هامش"
    assert len(store.objects) == 1


# ═════════ ٦ · بنية ═════════


def test_15_no_storage_write_route_ever_marks_its_generation_failed() -> None:
    """**وعليه يقوم أمانُ التنظيف العامّ.** التنظيفُ يمحو `failed`؛ فلو سجّل
    مسارُ كتابةِ تخزينٍ `failed` بعد كتابته لَمُحيت مرساةُ كائنٍ حقيقيّ.
    """
    import inspect

    from athera_api.routers import files

    source = inspect.getsource(files.store_uploaded_file)
    for forbidden in ("fail_leased", "close_pre_external"):
        assert forbidden not in source, f"مسارُ الكتابة يسجّل `failed`: {forbidden}"


def test_16_the_reconciler_holds_no_transaction_across_storage_io() -> None:
    """ولا نداءَ مخزنٍ داخل `async with maker()` — RC-T1-H3 على الصيانة أيضًا."""
    import ast
    import inspect
    import textwrap

    from athera_api.services import storage_reconcile

    tree = ast.parse(textwrap.dedent(inspect.getsource(storage_reconcile)))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncWith):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr in {
                        "list_prefix", "delete", "put", "put_stream"}:
                    offenders.append(inner.attr)
    assert offenders == [], f"نداءُ مخزنٍ داخل معاملة: {offenders}"


def test_17_the_reconciler_never_reaches_a_model_provider() -> None:
    import inspect

    from athera_api.services import storage_reconcile

    source = inspect.getsource(storage_reconcile)
    for forbidden in ("providers", "gateway", "run_structured", "ModelBoundary"):
        assert f"import {forbidden}" not in source and f".{forbidden} import" not in source, \
            forbidden
    assert storage_reconcile.STORAGE_WRITE_OPERATIONS == {
        "POST /api/v1/files/upload", "POST /api/v1/theses/upload"}


def test_18_the_reconciler_is_dry_run_by_default() -> None:
    import inspect

    from athera_api.services import storage_reconcile

    assert inspect.signature(storage_reconcile.reconcile).parameters["apply"].default is False
    assert dt.timedelta(hours=1) <= storage_reconcile.RECONCILE_GRACE


@requires_db
async def test_19_a_dry_run_reports_without_touching_anything(
    two_tenants, store, monkeypatch,
):
    slot = two_tenants["a"]
    _k, record_id = await _abandon(slot, store, monkeypatch)
    before = await _state(record_id)

    outcomes = await _reconcile(slot, store, apply=False)
    assert [o.status for o in outcomes] == ["would_reconcile"], outcomes
    assert outcomes[0].objects == 1
    # **والتقريرُ بصماتٌ لا أسماء**: لا يظهر اسمُ الملفّ ولا مفتاحُه.
    assert all(len(d) == 16 for d in outcomes[0].key_digests)
    assert "paper.txt" not in repr(outcomes)
    assert store.delete_calls == []
    assert await _state(record_id) == before, "التجربةُ الجافّةُ كتبت سياجًا"
    assert await _scalar("SELECT count(*) FROM audit_events WHERE action = :a AND tenant_id = :t",
                         {"a": "storage.orphan_reconciled", "t": str(slot["tenant_id"])}) == 0


@requires_db
async def test_20_the_theses_upload_family_is_reconciled_too(
    two_tenants, store, monkeypatch,
):
    """رفعُ الرسالة يكتب الكائنَ بالطريق نفسِه — فيُصالَح كذلك."""
    from athera_api.routers import files as files_router

    slot = two_tenants["a"]
    key = _key()
    real = files_router.audit.record
    fired = {"n": 0}

    async def _explode(*a, **k):
        if fired["n"] == 0:
            fired["n"] += 1
            raise RuntimeError("process died mid-finalize")
        return await real(*a, **k)

    monkeypatch.setattr(files_router.audit, "record", _explode)
    async with _client(slot) as http:
        fell = await http.post("/api/v1/theses/upload",
                               files={"upload": ("thesis.txt", b"# thesis\n\nbody " * 40,
                                                 "text/plain")},
                               headers={HEADER: key})
    monkeypatch.setattr(files_router.audit, "record", real)
    assert fell.status_code >= 500, fell.text
    record_id = str(await _generation(slot["tenant_id"], key))
    op = (await _record(slot["tenant_id"], key))[4]
    assert op == "POST /api/v1/theses/upload", op
    await _expire_lease(slot["tenant_id"], key)
    await _sql("UPDATE idempotency_records SET lease_expires_at = now() - interval '2 hours'"
               " WHERE id = :i", {"i": record_id})

    outcomes = await _reconcile(slot, store)
    assert [o.status for o in outcomes] == ["reconciled"], outcomes
    assert store.objects == {}
