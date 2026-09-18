"""RC-T1-H2-B3 — **تحمُّلُ إعادةٍ لكتابات التخزين** | retry-safe storage writes.

## الدعوى، بحدّها

    نطاقُ مفتاحٍ واحد + طلبٌ واحدٌ في معناه
      ⇒ معرّفُ ملفٍّ واحد
      ⇒ مفتاحُ تخزينٍ واحد
      ⇒ محتوًى واحد
      ⇒ **مفتاحُ كائنٍ نهائيٌّ واحدٌ على الأكثر**

**ولا يُدَّعى «مرّةً واحدةً بالضبط».** كتابةٌ فعليّةٌ (PUT) قد تتكرّر بعد
إخفاقٍ غامضٍ أو بعد انتهاء إجارة — والمسموحُ تكرارُها **إلى المفتاح نفسِه
بالمحتوى نفسِه**. فالفحوصُ هنا تفرّق صراحةً بين:

    عددُ نداءات PUT      ← قد يكون ٢
    عددُ المفاتيح النهائيّة ← يجب أن يكون ١

وهذا هو «المصالحةُ بهدفٍ ثابت»، لا ذرّيّةٌ عند المزوّد.

## ولمَ الهُويّةُ تُشتقّ

كان `uuid.uuid4()` يُولَّد بعد التجزئة، ومنه مفتاحُ التخزين. فإعادةٌ بعد
غموضٍ تُولّد مفتاحًا ثانيًا — كائنان لنيّةٍ واحدة، أحدُهما بلا صفّ.
والهُويّةُ الآن مشتقّةٌ من نطاق المفتاح (مستأجرٌ وفاعلٌ وعمليّةٌ وبصمةُ
مفتاح)، فيبلغها المُستولي كما بلغها الأوّل — **بلا عمودٍ جديدٍ ولا هجرة**.
"""
from __future__ import annotations

import asyncio
import io
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1_h3_ai_long_transactions import _client, _observer

pytestmark = pytest.mark.asyncio

UPLOAD = "/api/v1/files/upload"
INIT = "/api/v1/files"
HEADER = "Idempotency-Key"

DOC = b"# a document\n\nbody text that is long enough to be real.\n"
#: **وبالطول نفسِه عمدًا.** لو اختلف الحجمُ لَكفى `size_bytes` وحدَه
#: للتمييز، فيمرّ الفحصُ ولو رُفعت التجزئةُ من البصمة — وقد قِيس ذلك:
#: حذفُ `checksum_sha256` من البصمة لم يُسقِط الفحصَ حتى سُوِّي الطولان.
OTHER = b"# a document\n\nbody text that is long enough to be REAL.\n"
assert len(DOC) == len(OTHER), "الطولان يجب أن يتساويا ليُعزَل أثرُ التجزئة"
assert DOC != OTHER


def _key() -> str:
    return uuid.uuid4().hex


# ═══════════════════ مخزنٌ يَعُدّ ويُخفق عند الطلب ═══════════════════


class CountingStore:
    """مخزنٌ في الذاكرة **يَعُدّ النداءات ويحفظ المفاتيح** — ويفرّق بينهما.

    فـ«نداءان» ليس «كائنان»: كتابتان إلى المفتاح نفسِه بالمحتوى نفسِه
    تتركان كائنًا واحدًا. وهذا الفرقُ هو دعوى الطور كلِّه، فيُقاس ولا يُفترض.
    """

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []
        self.fail_with: BaseException | None = None
        #: تحبس **النداءَ الأوّلَ وحدَه**. ولو حبست الجميعَ لَاحتُبس
        #: المُستولي أيضًا فتجمّد الفحصُ — وقد وقع ذلك حرفيًّا.
        self.gate: asyncio.Event | None = None
        self.entered: asyncio.Event | None = None
        self._gated = False

    # ── واجهةُ المخزن ──
    def put_stream(self, key: str, fileobj, content_type: str) -> None:
        self.put_calls.append(key)
        if self.gate is not None and not self._gated:
            self._gated = True
            if self.entered is not None:
                self.entered.set()
            # حبسٌ متزامنٌ في خيطٍ جانبيّ — و`run_in_threadpool` يُشغّلنا فيه.
            import time

            while not self.gate.is_set():
                time.sleep(0.01)
        elif self.entered is not None:
            self.entered.set()
        if self.fail_with is not None:
            raise self.fail_with
        self.objects[key] = (fileobj.read(), content_type)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.put_calls.append(key)
        self.objects[key] = (data, content_type)

    def get(self, key: str) -> bytes:
        return self.objects[key][0]

    def get_stream(self, key: str):
        return iter([self.objects[key][0]])

    def delete(self, key: str) -> None:
        self.delete_calls.append(key)
        self.objects.pop(key, None)

    def presign_put(self, key: str, content_type: str, *, expires_in: int) -> str:
        # توقيعٌ يختلف في كلّ مرّة — كما يفعل المزوّد الحقيقيّ.
        return f"https://example.invalid/{key}?sig={uuid.uuid4().hex}&exp={expires_in}"

    def presign_get(self, key: str, *, expires_in: int) -> str:
        return f"https://example.invalid/{key}?sig={uuid.uuid4().hex}"


@pytest.fixture
def store(monkeypatch) -> CountingStore:
    from athera_api.services import storage

    made = CountingStore()
    monkeypatch.setattr(storage, "get_store", lambda: made)
    return made


def _upload_kwargs(data: bytes = DOC, *, filename: str = "paper.txt",
                   classification: str = "C2"):
    return {
        "files": {"upload": (filename, io.BytesIO(data), "text/plain")},
        "data": {"classification": classification},
    }


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


async def _files(tenant_id, file_id=None) -> int:
    if file_id is None:
        return await _scalar("SELECT count(*) FROM files WHERE tenant_id = :t",
                             {"t": str(tenant_id)})
    return await _scalar(
        "SELECT count(*) FROM files WHERE tenant_id = :t AND id = :i",
        {"t": str(tenant_id), "i": str(file_id)})


async def _grants(tenant_id, object_id) -> int:
    return await _scalar(
        "SELECT count(*) FROM object_grants WHERE tenant_id = :t AND object_id = :o",
        {"t": str(tenant_id), "o": str(object_id)})


async def _provenance(tenant_id, object_id) -> int:
    return await _scalar(
        "SELECT count(*) FROM provenance_events WHERE tenant_id = :t AND object_id = :o",
        {"t": str(tenant_id), "o": str(object_id)})


async def _audits(tenant_id, action, object_id=None) -> int:
    if object_id is None:
        return await _scalar(
            "SELECT count(*) FROM audit_events WHERE tenant_id = :t AND action = :a",
            {"t": str(tenant_id), "a": action})
    return await _scalar(
        "SELECT count(*) FROM audit_events "
        "WHERE tenant_id = :t AND action = :a AND object_id = :o",
        {"t": str(tenant_id), "a": action, "o": str(object_id)})


async def _record(tenant_id, key: str) -> tuple:
    from athera_api.services.idempotency import digest_key

    rows = await _rows(
        "SELECT state, response_status, response_body, lease_expires_at, operation"
        "  FROM idempotency_records WHERE tenant_id = :t AND key_digest = :d",
        {"t": str(tenant_id), "d": digest_key(key)})
    return rows[0] if rows else ()


async def _expire_lease(tenant_id, key: str) -> None:
    """تُنتهى الإجارةُ **بساعة القاعدة** لا بانتظارٍ حقيقيّ."""
    from sqlalchemy import text

    from athera_api.services.idempotency import digest_key

    engine, factory = await _observer()
    try:
        async with factory() as session:
            await session.execute(
                text("UPDATE idempotency_records "
                     "   SET lease_expires_at = now() - interval '1 second'"
                     " WHERE tenant_id = :t AND key_digest = :d"),
                {"t": str(tenant_id), "d": digest_key(key)})
            await session.commit()
    finally:
        await engine.dispose()


# ═════════ ١ · بلا مفتاح: السلوكُ القديم حرفيًّا ═════════


@requires_db
async def test_01_an_unkeyed_upload_is_unchanged(two_tenants, store):
    """رفعٌ بلا ترويسة: ٢٠١، معرّفٌ عشوائيّ، **وصفرُ صفوفِ إجارة**."""
    slot = two_tenants["a"]
    before = await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})

    async with _client(slot) as http:
        one = await http.post(UPLOAD, **_upload_kwargs())
        two = await http.post(UPLOAD, **_upload_kwargs())

    assert one.status_code == 201, one.text
    assert two.status_code == 201, two.text
    assert one.json()["id"] != two.json()["id"], "رفعان بلا مفتاحٍ اندمجا"
    assert len(store.put_calls) == 2
    assert len(set(store.put_calls)) == 2, "بلا مفتاحٍ يجب أن يبقى المفتاحُ عشوائيًّا"
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])}) == before, "رفعٌ بلا مفتاحٍ حجز صفًّا"


# ═════════ ٢ · أوّلُ رفعٍ مُمفتَح ═════════


@requires_db
async def test_02_the_first_keyed_upload_writes_exactly_one_of_everything(
    two_tenants, store,
):
    """٢٠١ · ملفٌّ واحد · مفتاحٌ واحد · منحةٌ واحدة · إسنادٌ واحد · تدقيقٌ واحد."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        answered = await http.post(UPLOAD, **_upload_kwargs(),
                                   headers={HEADER: key})
    assert answered.status_code == 201, answered.text
    file_id = answered.json()["id"]

    assert len(store.put_calls) == 1, store.put_calls
    assert len(store.objects) == 1, "أكثرُ من مفتاحِ كائنٍ نهائيّ"
    assert await _files(slot["tenant_id"], file_id) == 1
    assert await _grants(slot["tenant_id"], file_id) == 1
    assert await _provenance(slot["tenant_id"], file_id) == 1
    assert await _audits(slot["tenant_id"], "file.uploaded", file_id) == 1

    state, status_code, _body, fence, operation = await _record(slot["tenant_id"], key)
    assert state == "completed", state
    assert status_code == 201
    assert fence is None, "بقيت إجارةٌ حيّةٌ بعد الإتمام"
    assert operation == "POST /api/v1/files/upload", operation


@requires_db
async def test_03_the_keyed_file_id_is_derived_not_random(two_tenants, store):
    """المعرّفُ **مشتقٌّ** من نطاق المفتاح — ويُحسب خارج المسار فيُطابق.

    فلو عاد `uuid4()` لَاختلف المحسوبُ عن المُعاد، ولَما أمكن لمُستولٍ أن
    يبلغ الهدفَ نفسَه.
    """
    from athera_api.services.idempotency import digest_key, stable_object_id

    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        answered = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert answered.status_code == 201, answered.text

    expected = stable_object_id(
        tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
        operation="POST /api/v1/files/upload", key_digest=digest_key(key))
    assert answered.json()["id"] == str(expected), "المعرّفُ ليس المشتقّ"

    # ونطاقان مختلفان لا يتصادمان.
    other = stable_object_id(
        tenant_id=slot["tenant_id"], actor_user_id=uuid.uuid4(),
        operation="POST /api/v1/files/upload", key_digest=digest_key(key))
    assert other != expected, "فاعلان أعطيا الهُويّةَ نفسَها"
    across = stable_object_id(
        tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
        operation="POST /api/v1/files", key_digest=digest_key(key))
    assert across != expected, "عمليّتان أعطتا الهُويّةَ نفسَها"


# ═════════ ٣ · الإعادة: صفرُ كتابةٍ ثانية ═════════


@requires_db
async def test_04_a_replayed_upload_writes_nothing_and_calls_no_put(
    two_tenants, store,
):
    """المفتاحُ نفسُه والبايتاتُ نفسُها ⇒ الجوابُ نفسُه، **وصفرُ PUT ثانٍ**."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        one = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
        assert one.status_code == 201, one.text
        two = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})

    assert two.status_code == 201, two.text
    assert two.json() == one.json(), "الإعادةُ ليست الجوابَ الأصل"
    assert two.json()["id"] == one.json()["id"]
    assert two.headers.get("Idempotency-Replayed") == "true"
    # **ومفتاحُ التخزين يُقاس من المخزن لا من الجواب**: `FileResponse` لا
    # يذكره أصلًا، والمقصودُ أنّ الهدفَ لم يتغيّر.
    stored_key = await _scalar(
        "SELECT storage_key FROM files WHERE id = :i", {"i": one.json()["id"]})
    assert store.put_calls == [stored_key], store.put_calls
    assert len(store.put_calls) == 1, f"الإعادةُ كتبت ثانيةً: {store.put_calls}"
    assert await _files(slot["tenant_id"], one.json()["id"]) == 1
    assert await _provenance(slot["tenant_id"], one.json()["id"]) == 1
    assert await _audits(slot["tenant_id"], "file.uploaded", one.json()["id"]) == 1


@requires_db
async def test_05_the_same_key_with_different_bytes_is_refused(two_tenants, store):
    """بايتاتٌ أخرى بالمفتاح نفسِه ⇒ ٤٠٩، **ولا كتابةَ ثانية**.

    والتجزئةُ في البصمة هي هُويّةُ المحتوى — ولا تُخزَّن البايتاتُ نفسُها.
    """
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        one = await http.post(UPLOAD, **_upload_kwargs(DOC), headers={HEADER: key})
        assert one.status_code == 201, one.text
        two = await http.post(UPLOAD, **_upload_kwargs(OTHER), headers={HEADER: key})

    assert two.status_code == 409, two.text
    assert two.json()["error"]["code"] == "idempotency.key_reused", two.text
    assert len(store.put_calls) == 1, f"التعارضُ كتب: {store.put_calls}"
    assert len(store.objects) == 1


@requires_db
async def test_06_the_same_key_with_different_metadata_is_refused(
    two_tenants, store,
):
    """وصفٌ آخر (اسمٌ أو تصنيف) بالمفتاح نفسِه ⇒ ٤٠٩ بلا كتابة."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        one = await http.post(UPLOAD, **_upload_kwargs(filename="a.txt"),
                              headers={HEADER: key})
        assert one.status_code == 201, one.text
        renamed = await http.post(UPLOAD, **_upload_kwargs(filename="b.txt"),
                                  headers={HEADER: key})
        reclassed = await http.post(UPLOAD, **_upload_kwargs(classification="C3"),
                                    headers={HEADER: key})

    assert renamed.status_code == 409, renamed.text
    assert reclassed.status_code == 409, reclassed.text
    assert len(store.put_calls) == 1, f"تعارضٌ كتب: {store.put_calls}"


# ═════════ ٤ · التزامن ═════════


@requires_db
async def test_07_a_concurrent_twin_is_refused_and_writes_nothing(
    two_tenants, store,
):
    """الإجارةُ الحيّةُ تمنع كتابةً ثانيةً موازيةً للنيّة نفسِها."""
    store.gate = asyncio.Event()
    store.entered = asyncio.Event()
    slot = two_tenants["a"]
    key = _key()

    http = _client(slot)
    await http.__aenter__()
    first = asyncio.create_task(
        http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key}))
    try:
        await asyncio.wait_for(store.entered.wait(), timeout=20)
        async with _client(slot) as other:
            twin = await asyncio.wait_for(
                other.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key}),
                timeout=20)
        assert twin.status_code == 409, f"{twin.status_code}: {twin.text[:300]}"
        assert twin.json()["error"]["code"] == "idempotency.in_progress", twin.text
        assert len(store.put_calls) == 1, f"التوأمُ كتب: {store.put_calls}"
    finally:
        store.gate.set()
        answered = await first
        await http.__aexit__(None, None, None)
    assert answered.status_code == 201, answered.text
    assert len(store.objects) == 1


# ═════════ ٥ · السقوطُ بعد التخزين وقبل القاعدة ═════════


@requires_db
async def test_08_a_crash_after_storage_before_finalize_keeps_the_object(
    two_tenants, store, monkeypatch,
):
    """**ولا يُحذف الكائنُ المُمفتَح.** والإعادةُ بعد الانتهاء تبلغ الهدفَ نفسَه.

        PUT = ٢   ·   مفاتيحُ نهائيّة = ١   ·   صفوفُ ملفّ = ١

    وهذا هو الفرقُ كلُّه: تكرارُ الكتابة مسموحٌ، وتكرارُ **الهدف** ممنوع.
    """
    from athera_api.routers import files as files_router

    slot = two_tenants["a"]
    key = _key()

    boom = {"n": 0}
    real_record = files_router.audit.record

    async def _explode(*a, **k):
        # سقوطٌ **داخل معاملة الإنهاء** بعد نجاح التخزين.
        if boom["n"] == 0:
            boom["n"] += 1
            raise RuntimeError("database died mid-finalize")
        return await real_record(*a, **k)

    monkeypatch.setattr(files_router.audit, "record", _explode)

    async with _client(slot) as http:
        fell = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert fell.status_code >= 500, fell.status_code

    assert len(store.put_calls) == 1
    assert store.delete_calls == [], \
        f"حُذف الكائنُ المُمفتَح — وقد يكون لمُستولٍ قائم: {store.delete_calls}"
    assert len(store.objects) == 1, "الكائنُ لم يبقَ هدفًا للمصالحة"
    assert await _files(slot["tenant_id"]) >= 0
    state, status_code, _b, fence, _op = await _record(slot["tenant_id"], key)
    assert state == "in_progress", f"الحالُ بعد سقوطٍ غامض: {state}"
    assert status_code is None
    assert fence is not None, "أُفرغت الإجارةُ بعد سقوطٍ قد يكون غامضًا"

    # ── قبل الانتهاء: يُردّ «قائمٌ لغيرك» ولا يُكتب ──
    async with _client(slot) as http:
        early = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert early.status_code == 409, early.text
    assert early.json()["error"]["code"] == "idempotency.in_progress", early.text
    assert len(store.put_calls) == 1, "أُعيدت الكتابةُ وإجارةٌ حيّة"

    # ── بعد الانتهاء: استيلاءٌ على **الهدف نفسِه** ──
    await _expire_lease(slot["tenant_id"], key)
    async with _client(slot) as http:
        took = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert took.status_code == 201, took.text

    assert len(store.put_calls) == 2, store.put_calls
    assert store.put_calls[0] == store.put_calls[1], \
        f"المُستولي ولّد مفتاحًا جديدًا: {store.put_calls}"
    assert len(store.objects) == 1, "كائنان لنيّةٍ واحدة"
    file_id = took.json()["id"]
    assert await _files(slot["tenant_id"], file_id) == 1
    assert await _grants(slot["tenant_id"], file_id) == 1
    assert await _provenance(slot["tenant_id"], file_id) == 1
    assert await _audits(slot["tenant_id"], "file.uploaded", file_id) == 1


@requires_db
async def test_09_an_ambiguous_storage_timeout_is_not_marked_known_failed(
    two_tenants, store,
):
    """مهلةٌ في الكتابة **لا تُثبت أنّ الكائنَ لم يُكتب**.

    فلا تُسجَّل `failed` — وهي تُفرغ السياجَ فتفتح الباب لمحاولةٍ فوريّة —
    بل تبقى الإجارةُ حيّةً إلى أجلها. ولا يُولَّد مفتاحٌ جديد.
    """
    slot = two_tenants["a"]
    key = _key()
    store.fail_with = TimeoutError("connection timed out mid-PUT")

    async with _client(slot) as http:
        fell = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert fell.status_code >= 500, fell.status_code

    state, _s, _b, fence, _op = await _record(slot["tenant_id"], key)
    assert state == "in_progress", \
        f"إخفاقٌ غامضٌ وُسم حالًا معلومة: {state} — والمهلةُ لا تُثبت عدمَ الكتابة"
    assert fence is not None, "أُفرغ السياجُ على غموض"
    assert store.delete_calls == [], "حُذف على غموض"

    # قبل الانتهاء: ٤٠٩
    async with _client(slot) as http:
        early = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert early.status_code == 409, early.text

    # بعد الانتهاء: الهدفُ نفسُه
    store.fail_with = None
    await _expire_lease(slot["tenant_id"], key)
    async with _client(slot) as http:
        took = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert took.status_code == 201, took.text
    assert len(set(store.put_calls)) == 1, \
        f"المُستولي غيّر الهدف: {set(store.put_calls)}"
    assert len(store.objects) == 1


@requires_db
async def test_10_a_stale_worker_cannot_finalize_nor_delete_the_winners_object(
    two_tenants, store,
):
    """البائتُ لا يُودِع صفًّا **ولا يمحو كائنَ المُستولي**."""
    store.gate = asyncio.Event()
    store.entered = asyncio.Event()
    slot = two_tenants["a"]
    key = _key()

    http = _client(slot)
    await http.__aenter__()
    stale = asyncio.create_task(
        http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key}))
    try:
        await asyncio.wait_for(store.entered.wait(), timeout=20)
        # تُنتهى إجارتُه ويستولي غيرُه ويُتمّ.
        await _expire_lease(slot["tenant_id"], key)
        store.entered = asyncio.Event()
        async with _client(slot) as winner:
            took = await asyncio.wait_for(
                winner.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key}),
                timeout=20)
        assert took.status_code == 201, took.text
        winner_id = took.json()["id"]
        objects_after_win = dict(store.objects)
    finally:
        store.gate.set()
        answered = await stale
        await http.__aexit__(None, None, None)

    assert answered.status_code == 409, \
        f"البائتُ أُجيب نجاحًا: {answered.status_code} {answered.text[:300]}"
    assert answered.json()["error"]["code"] == "idempotency.lease_superseded", \
        answered.text
    assert store.delete_calls == [], \
        f"البائتُ محا كائنًا: {store.delete_calls}"
    assert store.objects == objects_after_win, "تغيّر المخزنُ بعد فوز المُستولي"
    assert len(store.objects) == 1, "كائنان"
    assert await _files(slot["tenant_id"], winner_id) == 1
    assert await _provenance(slot["tenant_id"], winner_id) == 1, \
        "إسنادٌ مكرَّرٌ أو مفقود"
    assert await _audits(slot["tenant_id"], "file.uploaded", winner_id) == 1

    state, status_code, _b, _f, _op = await _record(slot["tenant_id"], key)
    assert state == "completed" and status_code == 201


@requires_db
async def test_11_an_unkeyed_upload_still_deletes_on_db_failure(
    two_tenants, store, monkeypatch,
):
    """**والسلوكُ القديم يبقى بلا مفتاح**: كائنٌ بلا صفٍّ يُحذف.

    فالمفتاحُ العشوائيُّ لا يشاركه أحد، فلا مُستولي يُخشى محوُ كائنه.
    """
    from athera_api.routers import files as files_router

    slot = two_tenants["a"]
    real_record = files_router.audit.record
    boom = {"n": 0}

    async def _explode(*a, **k):
        if boom["n"] == 0:
            boom["n"] += 1
            raise RuntimeError("database died mid-finalize")
        return await real_record(*a, **k)

    monkeypatch.setattr(files_router.audit, "record", _explode)
    async with _client(slot) as http:
        fell = await http.post(UPLOAD, **_upload_kwargs())
    assert fell.status_code >= 500
    assert len(store.delete_calls) == 1, \
        f"لم يُحذف الكائنُ اليتيمُ بلا مفتاح: {store.delete_calls}"
    assert store.objects == {}, "بقي كائنٌ بلا صفّ"


# ═════════ ٦ · العزل والسرّيّة ═════════


@requires_db
async def test_12_tenant_and_actor_isolation(two_tenants, store):
    """مفتاحٌ واحدٌ عبر مستأجرَين وعبر فاعلَين ⇒ أعمالٌ مستقلّة."""
    from tests.test_at_rc_t1a_project_access import _second_user

    key = _key()
    a, b = two_tenants["a"], two_tenants["b"]
    async with _client(a) as http:
        mine = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    async with _client(b) as http:
        theirs = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert mine.status_code == 201 and theirs.status_code == 201, theirs.text
    assert mine.json()["id"] != theirs.json()["id"], "مفتاحٌ عبَر مستأجرًا"
    assert "Idempotency-Replayed" not in theirs.headers

    colleague = await _second_user(
        a["tenant_id"], email=f"h2b3-{uuid.uuid4().hex[:10]}@example.com")
    async with _client(colleague) as http:
        other_actor = await http.post(UPLOAD, **_upload_kwargs(),
                                      headers={HEADER: key})
    assert other_actor.status_code == 201, other_actor.text
    assert other_actor.json()["id"] != mine.json()["id"], "مفتاحٌ عبَر فاعلًا"
    assert "Idempotency-Replayed" not in other_actor.headers
    assert len(set(store.put_calls)) == 3, store.put_calls


@requires_db
async def test_13_the_raw_key_is_never_persisted(two_tenants, store):
    """الخامُ لا يُخزَّن ولا يُدوَّن — لا في الإجارة ولا في التدقيق ولا في الصفّ."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        answered = await http.post(UPLOAD, **_upload_kwargs(), headers={HEADER: key})
    assert answered.status_code == 201, answered.text

    hits = await _scalar(
        "SELECT count(*) FROM idempotency_records"
        " WHERE tenant_id = :t AND (key_digest = :raw"
        "       OR response_body::text LIKE :like)",
        {"t": str(slot["tenant_id"]), "raw": key, "like": f"%{key}%"})
    assert hits == 0, "المفتاحُ الخامُ ظهر في صفّ الإجارة"

    audits = await _scalar(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
        "   AND (state_after::text LIKE :like OR coalesce(reason,'') LIKE :like)",
        {"t": str(slot["tenant_id"]), "like": f"%{key}%"})
    assert audits == 0, "المفتاحُ الخامُ ظهر في سجلّ التدقيق"

    files_hit = await _scalar(
        "SELECT count(*) FROM files WHERE tenant_id = :t AND storage_key LIKE :like",
        {"t": str(slot["tenant_id"]), "like": f"%{key}%"})
    assert files_hit == 0, "المفتاحُ الخامُ ظهر في مفتاح التخزين"


# ═════════ ٧ · النيّة الموقّعة: /files ═════════


def _init_body(filename: str = "signed.txt", size: int = 1024,
               classification: str = "C2") -> dict:
    return {"filename": filename, "content_type": "text/plain",
            "size_bytes": size, "classification": classification}


@requires_db
async def test_14_an_unkeyed_init_is_unchanged(two_tenants, store):
    """نيّةٌ بلا مفتاح: صفّان معلَّقان مستقلّان، وصفرُ صفوفِ إجارة."""
    slot = two_tenants["a"]
    before = await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})
    async with _client(slot) as http:
        one = await http.post(INIT, json=_init_body())
        two = await http.post(INIT, json=_init_body())
    assert one.status_code == 201, one.text
    assert two.status_code == 201, two.text
    assert one.json()["file_id"] != two.json()["file_id"]
    assert one.json()["upload_url"], "لا رابطَ موقّع"
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])}) == before


@requires_db
async def test_15_the_first_keyed_init_creates_one_pending_file(two_tenants, store):
    """صفٌّ معلَّقٌ واحد · هُويّةٌ ومفتاحٌ ثابتان · منحةٌ واحدة · حدثٌ واحد."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        answered = await http.post(INIT, json=_init_body(), headers={HEADER: key})
    assert answered.status_code == 201, answered.text
    file_id = answered.json()["file_id"]

    assert await _files(slot["tenant_id"], file_id) == 1
    assert await _grants(slot["tenant_id"], file_id) == 1
    assert await _audits(slot["tenant_id"], "file.upload_initiated", file_id) == 1
    assert await _scalar("SELECT status FROM files WHERE id = :i",
                         {"i": file_id}) == "pending"

    from athera_api.services.idempotency import digest_key, stable_object_id
    expected = stable_object_id(
        tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
        operation="POST /api/v1/files", key_digest=digest_key(key))
    assert file_id == str(expected), "معرّفُ النيّة ليس المشتقّ"


@requires_db
async def test_16_a_replayed_init_keeps_identity_and_mints_a_fresh_url(
    two_tenants, store,
):
    """الإعادةُ: **الهُويّةُ والمفتاحُ نفسُهما، والتوقيعُ جديد**.

    فالرابطُ قدرةٌ عابرة: إعادةٌ بعد انتهاء صلاحيّته يجب أن تُعطي رابطًا
    حيًّا لا جثّةَ توقيعٍ خُزّنت أمس.
    """
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        one = await http.post(INIT, json=_init_body(), headers={HEADER: key})
        assert one.status_code == 201, one.text
        two = await http.post(INIT, json=_init_body(), headers={HEADER: key})

    assert two.status_code == 201, two.text
    assert two.headers.get("Idempotency-Replayed") == "true"
    assert two.json()["file_id"] == one.json()["file_id"], "الهُويّةُ تغيّرت"
    assert two.json()["storage_key"] == one.json()["storage_key"], "المفتاحُ تغيّر"
    assert two.json()["upload_url"] != one.json()["upload_url"], \
        "أُعيد التوقيعُ المخزون نفسُه — وهو ينتهي فيصير جوابًا ميّتًا"
    assert two.json()["upload_url"], "إعادةٌ بلا رابط"

    fid = one.json()["file_id"]
    assert await _files(slot["tenant_id"], fid) == 1, "صفٌّ معلَّقٌ ثانٍ"
    assert await _grants(slot["tenant_id"], fid) == 1, "منحةٌ ثانية"
    assert await _audits(slot["tenant_id"], "file.upload_initiated", fid) == 1, \
        "حدثُ نيّةٍ ثانٍ"


@requires_db
async def test_17_no_signed_capability_is_ever_persisted(two_tenants, store):
    """**ولا توقيعَ في المخزون**: لا رابطٌ ولا `sig` ولا اعتمادٌ ولا خامٌّ."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        answered = await http.post(INIT, json=_init_body(), headers={HEADER: key})
    assert answered.status_code == 201, answered.text

    _state, _code, body, _fence, _op = await _record(slot["tenant_id"], key)
    assert body is not None
    flat = str(body).lower()
    for forbidden in ("upload_url", "http", "sig=", "signature", "x-amz",
                      "credential", "secret", "access_key", key.lower()):
        assert forbidden not in flat, \
            f"المخزونُ يحمل {forbidden!r} — وهو قدرةٌ أو سرّ: {body}"
    assert set(body) == {"file_id", "storage_key", "folder_id", "expires_in"}, body

    audits = await _scalar(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t"
        "   AND (state_after::text ILIKE '%upload_url%'"
        "        OR state_after::text ILIKE '%sig=%')",
        {"t": str(slot["tenant_id"])})
    assert audits == 0, "رابطٌ موقّعٌ في سجلّ التدقيق"


@requires_db
async def test_18_the_same_key_with_another_payload_is_refused(two_tenants, store):
    """جسمٌ آخر بالمفتاح نفسِه ⇒ ٤٠٩، ولا صفَّ معلَّقٍ ثانٍ."""
    slot = two_tenants["a"]
    key = _key()
    async with _client(slot) as http:
        one = await http.post(INIT, json=_init_body(), headers={HEADER: key})
        assert one.status_code == 201, one.text
        two = await http.post(INIT, json=_init_body(filename="other.txt"),
                              headers={HEADER: key})
    assert two.status_code == 409, two.text
    assert two.json()["error"]["code"] == "idempotency.key_reused", two.text
    assert await _scalar(
        "SELECT count(*) FROM files WHERE tenant_id = :t AND status = 'pending'"
        "   AND original_filename = 'other.txt'",
        {"t": str(slot["tenant_id"])}) == 0, "التعارضُ أنشأ صفًّا"


@requires_db
async def test_19_a_takeover_reuses_the_pending_row_it_finds(two_tenants, store):
    """**والصفُّ المعلَّقُ جزءٌ من المصالحة**: مُستولٍ يجده فيُعيد استعماله.

    ويُحاكى سقوطٌ بعد إيداع الصفّ وقبل الإتمام: يُدسّ الصفُّ بهُويّته
    الثابتة، ثمّ تُنتهى الإجارة، ثمّ يُعاد الطلب.
    """
    from sqlalchemy import text

    from athera_api.services.idempotency import digest_key, stable_object_id

    slot = two_tenants["a"]
    key = _key()
    stable = stable_object_id(
        tenant_id=slot["tenant_id"], actor_user_id=slot["user_id"],
        operation="POST /api/v1/files", key_digest=digest_key(key))

    # أوّلُ نداءٍ يُتمّ، ثمّ تُعاد حالُ الصفّ إلى ما قبل الإتمام.
    async with _client(slot) as http:
        first = await http.post(INIT, json=_init_body(), headers={HEADER: key})
    assert first.status_code == 201, first.text
    assert first.json()["file_id"] == str(stable)

    engine, factory = await _observer()
    try:
        async with factory() as session:
            await session.execute(
                text("UPDATE idempotency_records SET state='in_progress',"
                     "       response_status=NULL, response_body=NULL,"
                     "       completed_at=NULL,"
                     "       lease_expires_at = now() - interval '1 second'"
                     " WHERE tenant_id = :t AND key_digest = :d"),
                {"t": str(slot["tenant_id"]), "d": digest_key(key)})
            await session.commit()
    finally:
        await engine.dispose()

    async with _client(slot) as http:
        took = await http.post(INIT, json=_init_body(), headers={HEADER: key})
    assert took.status_code == 201, took.text
    assert took.json()["file_id"] == str(stable), "المُستولي ولّد هُويّةً جديدة"
    assert await _files(slot["tenant_id"], stable) == 1, "صفٌّ معلَّقٌ مكرَّر"
    assert await _grants(slot["tenant_id"], stable) == 1, "منحةٌ مكرَّرة"
    assert await _audits(slot["tenant_id"], "file.upload_initiated", stable) == 1, \
        "حدثُ نيّةٍ مكرَّر"


# ═════════ ٨ · الختم: /files/{id}/complete ═════════


@requires_db
async def test_20_a_keyed_complete_replays_without_duplicating_anything(
    two_tenants, store,
):
    """ختمٌ مُمفتَحٌ يُعاد: الجوابُ نفسُه، **ولا إسنادَ ولا حدثَ ختمٍ ثانٍ**."""
    slot = two_tenants["a"]
    async with _client(slot) as http:
        started = await http.post(INIT, json=_init_body())
        assert started.status_code == 201, started.text
        fid = started.json()["file_id"]
        key = _key()
        body = {"checksum_sha256": "a" * 64}
        one = await http.post(f"/api/v1/files/{fid}/complete", json=body,
                              headers={HEADER: key})
        assert one.status_code == 200, one.text
        two = await http.post(f"/api/v1/files/{fid}/complete", json=body,
                              headers={HEADER: key})

    assert two.status_code == 200, two.text
    assert two.json() == one.json(), "الإعادةُ ليست الجوابَ الأصل"
    assert two.headers.get("Idempotency-Replayed") == "true"
    assert await _provenance(slot["tenant_id"], fid) == 1, "إسنادٌ مكرَّر"
    assert await _audits(slot["tenant_id"], "file.upload_completed", fid) == 1, \
        "حدثُ ختمٍ مكرَّر"


@requires_db
async def test_21_a_complete_key_reused_on_another_file_is_refused(
    two_tenants, store,
):
    """المفتاحُ نفسُه على ملفٍّ آخر ⇒ ٤٠٩، ولا يُختم الثاني."""
    slot = two_tenants["a"]
    async with _client(slot) as http:
        a = (await http.post(INIT, json=_init_body())).json()["file_id"]
        b = (await http.post(INIT, json=_init_body(filename="b.txt"))).json()["file_id"]
        key = _key()
        body = {"checksum_sha256": "b" * 64}
        first = await http.post(f"/api/v1/files/{a}/complete", json=body,
                                headers={HEADER: key})
        assert first.status_code == 200, first.text
        second = await http.post(f"/api/v1/files/{b}/complete", json=body,
                                 headers={HEADER: key})
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "idempotency.key_reused", second.text
    assert await _scalar("SELECT status FROM files WHERE id = :i", {"i": b}) == "pending"
    assert await _provenance(slot["tenant_id"], b) == 0


@requires_db
async def test_22_a_complete_key_reused_with_another_checksum_is_refused(
    two_tenants, store,
):
    """تجزئةٌ أخرى بالمفتاح نفسِه ⇒ ٤٠٩ — فالمحتوى جزءٌ من المعنى."""
    slot = two_tenants["a"]
    async with _client(slot) as http:
        fid = (await http.post(INIT, json=_init_body())).json()["file_id"]
        key = _key()
        first = await http.post(f"/api/v1/files/{fid}/complete",
                                json={"checksum_sha256": "c" * 64},
                                headers={HEADER: key})
        assert first.status_code == 200, first.text
        second = await http.post(f"/api/v1/files/{fid}/complete",
                                 json={"checksum_sha256": "d" * 64},
                                 headers={HEADER: key})
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "idempotency.key_reused", second.text
    assert await _scalar("SELECT checksum_sha256 FROM files WHERE id = :i",
                         {"i": fid}) == "c" * 64, "كُتبت تجزئةُ التعارض"
    assert await _provenance(slot["tenant_id"], fid) == 1


@requires_db
async def test_23_complete_keeps_tenant_and_actor_isolation(two_tenants, store):
    """المفتاحُ لا يعبُر مستأجرًا ولا فاعلًا في مسار الختم."""
    from tests.test_at_rc_t1a_project_access import _second_user

    a = two_tenants["a"]
    key = _key()
    async with _client(a) as http:
        mine = (await http.post(INIT, json=_init_body())).json()["file_id"]
        first = await http.post(f"/api/v1/files/{mine}/complete",
                                json={"checksum_sha256": "e" * 64},
                                headers={HEADER: key})
    assert first.status_code == 200, first.text

    async with _client(two_tenants["b"]) as http:
        theirs = (await http.post(INIT, json=_init_body())).json()["file_id"]
        other = await http.post(f"/api/v1/files/{theirs}/complete",
                                json={"checksum_sha256": "e" * 64},
                                headers={HEADER: key})
    assert other.status_code == 200, other.text
    assert "Idempotency-Replayed" not in other.headers, "مفتاحٌ عبَر مستأجرًا"

    colleague = await _second_user(
        a["tenant_id"], email=f"h2b3c-{uuid.uuid4().hex[:10]}@example.com")
    async with _client(colleague) as http:
        theirs2 = (await http.post(INIT, json=_init_body())).json()["file_id"]
        peer = await http.post(f"/api/v1/files/{theirs2}/complete",
                               json={"checksum_sha256": "e" * 64},
                               headers={HEADER: key})
    assert peer.status_code == 200, peer.text
    assert "Idempotency-Replayed" not in peer.headers, "مفتاحٌ عبَر فاعلًا"


@requires_db
async def test_24_an_unkeyed_complete_is_unchanged(two_tenants, store):
    """ختمٌ بلا مفتاح: كما كان، وصفرُ صفوفِ إجارة."""
    slot = two_tenants["a"]
    before = await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])})
    async with _client(slot) as http:
        fid = (await http.post(INIT, json=_init_body())).json()["file_id"]
        answered = await http.post(f"/api/v1/files/{fid}/complete",
                                   json={"checksum_sha256": "f" * 64})
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "stored"
    assert await _scalar(
        "SELECT count(*) FROM idempotency_records WHERE tenant_id = :t",
        {"t": str(slot["tenant_id"])}) == before
