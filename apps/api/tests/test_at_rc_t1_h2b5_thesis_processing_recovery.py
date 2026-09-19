"""RC-T1-H2-B5 — **استئنافُ معالجةِ الرسالة، وسياجُ عاملِها**.

## العطب

مهامُّ `BackgroundTasks` تعيش داخل عملية الـAPI. فإعادةُ نشرٍ أو سقوطُ آلةٍ
أثناء العمل تترك الصفَّ عند `queued` أو `parsing` أو `extracting`، ولا
يستأنفه أحد — و`claim_for_processing` كان يرفض كلَّ حالٍ جاريةٍ **إلى الأبد**.
فالرسالةُ تعلق، والبطاقةُ تقول «جارٍ» ولا شيء يجري.

## والدعوى المأذونة — وحدَها

    مهمّةٌ ضاعت أو انقطعت يمكن استئنافُها بطلبٍ مأذونٍ لاحق، بلا تكرارِ
    الاستخراجِ المنطقيّ، وبلا أن يكتب عاملٌ بائتٌ بعد الاستعادة، وبلا نداءٍ
    أعمى لمزوّدٍ غيرِ مُثبَتِ المنعة داخل جيلِ المعالجةِ نفسِه.

ويجوز أيضًا أن يُقال:

    إعادةُ معالجةٍ مقصودةٌ جديدةٌ جيلٌ آخر، ويجوز فيها نداءُ النموذجِ مجدّدًا.

**ولا يُدَّعى**: تنفيذٌ مرّةً واحدةً بالضبط، ولا طابورٌ دائم، ولا استئنافٌ
تلقائيٌّ بعد سقوط العمليّة، ولا أنّ `BackgroundTasks` تنجو من موتِ العمليّة.
"""
from __future__ import annotations

import io
import uuid

import pytest

from tests.conftest import requires_db

pytestmark = pytest.mark.asyncio

UPLOAD = "/api/v1/theses/upload"

#: مستندٌ يُفكَّك فعلًا: فقراتٌ أطولُ من الحدّ الأدنى للمقطع.
DOCUMENT = (
    "مشكلة الدراسة: قياس أثر التعلّم المدمج في التحصيل الدراسيّ لدى طلبة "
    "المرحلة الثانوية في المدارس الحكومية.\n\n"
    "المنهج: تصميمٌ شبه تجريبيّ على مجموعتين متكافئتين، واستبانةٌ موزّعةٌ "
    "على عيّنةٍ عشوائيةٍ من المعلّمين.\n\n"
    "النتائج: فرقٌ دالٌّ إحصائيًّا لصالح المجموعة التجريبيّة في الاختبار "
    "البعديّ، وحُلّلت البيانات باستخدام SPSS.\n"
).encode("utf-8")


async def _rows(sql: str, params: dict | None = None):
    """قراءةٌ من **اتصالٍ مستقلٍّ** — فالعزلُ يحجب عن جلسةٍ بلا سياق."""
    from sqlalchemy import text

    from tests.test_at_rc_t1_h3_ai_long_transactions import _observer

    engine, factory = await _observer()
    try:
        async with factory() as session:
            return [tuple(r) for r in
                    (await session.execute(text(sql), params or {})).all()]
    finally:
        await engine.dispose()


async def _count(sql: str, params: dict | None = None) -> int:
    return int((await _rows(sql, params))[0][0])


def _client(slot):
    from tests.test_at_rc_t1_h3_ai_long_transactions import _client as make

    return make(slot)


async def _upload(slot, *, key: str | None = None, data: bytes = DOCUMENT,
                  name: str = "thesis.txt"):
    """يرفع رسالةً عبر المسار الحقيقيّ — بمفتاحٍ أو بلا."""
    headers = {"Idempotency-Key": key} if key else {}
    async with _client(slot) as http:
        return await http.post(
            UPLOAD, files={"upload": (name, io.BytesIO(data), "text/plain")},
            headers=headers)


async def _thesis_row(tenant_id, thesis_id):
    rows = await _rows(
        "SELECT processing_state, processing_attempts, processing_state_changed_at,"
        "       file_id, failure_code, failure_detail"
        "  FROM theses WHERE id = :t AND tenant_id = :ten",
        {"t": str(thesis_id), "ten": str(tenant_id)})
    return rows[0] if rows else None


async def _make_stale(tenant_id, thesis_id, *, seconds: int | None = None) -> None:
    """يُقدّم الطابعَ إلى الوراء **بساعة القاعدة** — كعاملٍ مات منذ ساعة."""
    from sqlalchemy import text

    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h3_ai_long_transactions import _observer

    back = seconds or int(processing.STALE_AFTER.total_seconds()) + 60
    engine, factory = await _observer()
    try:
        async with factory() as session:
            await session.execute(
                text("UPDATE theses SET processing_state_changed_at ="
                     "        now() - make_interval(secs => :back)"
                     " WHERE id = :t AND tenant_id = :ten"),
                {"back": back, "t": str(thesis_id), "ten": str(tenant_id)})
            await session.commit()
    finally:
        await engine.dispose()


def _memory_storage(monkeypatch):
    from athera_api.services import storage

    monkeypatch.setattr(storage.get_settings(), "storage_provider", "memory",
                        raising=False)
    storage.reset_store_cache()


@pytest.fixture(autouse=True)
def _storage(monkeypatch):
    _memory_storage(monkeypatch)
    yield


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    """**لا مهمّةَ تعمل من تلقائها في هذه الحزمة.**

    فالمقصودُ هنا حالُ الجيلِ وسياجُه، لا ما يفعله العامل. فتُلتقَط الجدولةُ
    ولا تُنفَّذ — ثمّ يُنادى العاملُ صراحةً حيث يُقصَد ذلك.
    """
    from fastapi import BackgroundTasks

    scheduled: list[tuple] = []

    def _add(self, func, *args, **kwargs):
        scheduled.append((func, args, kwargs))

    monkeypatch.setattr(BackgroundTasks, "add_task", _add)
    yield scheduled


# ═════════════════ ١ · الجيلُ: بدايةٌ، واستعادةٌ، وحدُّ الهجران ═════════════════


@requires_db
async def test_01_a_keyed_upload_creates_exactly_one_of_everything(
    two_tenants, _no_background,
):
    """(أ) رفعٌ مُمفتَح: كائنٌ واحد، وملفٌّ واحد، ومنحةٌ واحدة، ورسالةٌ واحدة."""
    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    key = uuid.uuid4().hex

    answer = await _upload(slot, key=key)
    assert answer.status_code == 202, f"{answer.status_code}: {answer.text[:250]}"
    body = answer.json()
    thesis_id, file_id = body["thesis_id"], body["file_id"]

    assert await _count("SELECT count(*) FROM files WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1
    assert await _count(
        "SELECT count(*) FROM object_grants WHERE tenant_id = :t"
        "   AND object_type = 'file' AND object_id = :f",
        {"t": str(tid), "f": file_id}) == 1
    assert await _count("SELECT count(*) FROM theses WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1

    state, attempts, changed, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    assert state == "queued", state
    assert attempts == 1, f"عددُ المحاولات {attempts}"
    assert changed is not None, "لا طابعَ للجيل — فلا سياج"
    assert len(_no_background) == 1, "لم يُجدوَل عاملٌ واحد"


@requires_db
async def test_02_the_same_key_and_bytes_adds_nothing(two_tenants, _no_background):
    """(ب) إعادةٌ بالمفتاح والبايتات نفسِها: صفرُ ملفٍّ وصفرُ رسالةٍ وصفرُ محاولة."""
    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    key = uuid.uuid4().hex

    first = await _upload(slot, key=key)
    assert first.status_code == 202, first.text
    thesis_id = first.json()["thesis_id"]
    _s, attempts, _c, _f, _fc, _fd = await _thesis_row(tid, thesis_id)

    again = await _upload(slot, key=key)
    assert again.status_code == 202, f"{again.status_code}: {again.text[:250]}"
    assert again.json() == first.json(), "الإعادةُ ليست الجوابَ الأصل"

    assert await _count("SELECT count(*) FROM files WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1, "ملفٌّ ثانٍ"
    assert await _count("SELECT count(*) FROM theses WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1, "رسالةٌ ثانية"
    _s2, attempts2, _c2, _f2, _fc2, _fd2 = await _thesis_row(tid, thesis_id)
    assert attempts2 == attempts, "الإعادةُ بدأت محاولةً جديدة"


@requires_db
async def test_03_the_same_key_with_other_bytes_conflicts(two_tenants, _no_background):
    """(ج) المفتاحُ نفسُه ببايتاتٍ أخرى: صِدامٌ، وصفرُ طفرةٍ ثانية."""
    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    key = uuid.uuid4().hex

    first = await _upload(slot, key=key)
    assert first.status_code == 202, first.text

    other = await _upload(slot, key=key, data=DOCUMENT + "\n\nفقرةٌ مستجدّةٌ كافية الطول للفحص.\n".encode("utf-8"))
    assert other.status_code == 409, f"{other.status_code}: {other.text[:250]}"
    assert other.json()["error"]["code"] == "idempotency.key_reused", other.text

    assert await _count("SELECT count(*) FROM files WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1, "كُتب ملفٌّ ثانٍ على صِدام"
    assert await _count("SELECT count(*) FROM theses WHERE tenant_id = :t",
                        {"t": str(tid)}) == 1, "كُتبت رسالةٌ ثانيةٌ على صِدام"


@requires_db
async def test_04_a_lost_dispatch_becomes_stale_and_is_recovered(
    two_tenants, _no_background,
):
    """(هـ) أُودع العملُ ولم تُطلَق المهمّة: تُهجَر، ثمّ تُستعاد **بجيلها**."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    thesis_id = uuid.UUID(answer.json()["thesis_id"])

    # المهمّةُ لم تعمل قطّ — والحالُ `queued`.
    async with tenant_session(tid, slot["user_id"]) as session:
        assert not await processing.is_stale(
            session, tenant_id=tid, thesis_id=thesis_id), "هُجرت قبل أوانها"

    await _make_stale(tid, thesis_id)

    async with tenant_session(tid, slot["user_id"]) as session:
        assert await processing.is_stale(session, tenant_id=tid, thesis_id=thesis_id)
        before = (await _thesis_row(tid, thesis_id))[1]
        claim = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)

    assert claim.recovered is True, "لم تُعَدّ استعادةً"
    assert claim.attempt == before, "الاستعادةُ زادت رقمَ المحاولة"
    state, attempts, changed, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    assert attempts == before, f"المحاولةُ صارت {attempts}"
    assert claim.fence == changed, "السياجُ لا يطابق الطابعَ المُودَع"


@requires_db
async def test_05_a_live_attempt_is_never_recovered(two_tenants, _no_background):
    """محاولةٌ حيّة: `thesis.processing_in_flight` — ولا تُستعاد."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    thesis_id = uuid.UUID(answer.json()["thesis_id"])

    async with tenant_session(tid, slot["user_id"]) as session:
        with pytest.raises(processing.ProcessingConflict) as conflict:
            await processing.claim_generation(
                session, tenant_id=tid, thesis_id=thesis_id)
    assert conflict.value.code == "thesis.processing_in_flight"


@requires_db
async def test_06_a_duplicate_background_task_does_no_work(
    two_tenants, _no_background, monkeypatch,
):
    """(٩) مهمّتان بالمطالبة نفسِها: واحدةٌ تفوز، والأخرى **صفرُ أثر**."""
    from athera_api.routers import document_intelligence as di
    from athera_api.services.thesis import processing

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    await _upload(slot, key=uuid.uuid4().hex)
    claim = _no_background[0][1][2]
    assert isinstance(claim, processing.ProcessingClaim)

    calls = {"n": 0}

    class _Never:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            raise AssertionError("نُودي النموذجُ لعاملٍ خاسر")

    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate
    _activate(monkeypatch, _Never())

    # الأوّلُ يعمل ويُحوّل السياج.
    await di._process(tid, uid, claim, "ar")
    runs_after_first = await _count(
        "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t", {"t": str(tid)})
    candidates_after_first = await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t", {"t": str(tid)})
    audits_after_first = await _count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t", {"t": str(tid)})

    # والثاني يحمل السياجَ القديم نفسَه — فيعود بلا أثر.
    await di._process(tid, uid, claim, "ar")

    assert await _count(
        "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t",
        {"t": str(tid)}) == runs_after_first, "العاملُ الخاسرُ أنشأ تشغيلة"
    assert await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t",
        {"t": str(tid)}) == candidates_after_first, "الخاسرُ أدرج مرشّحات"
    assert await _count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = :t",
        {"t": str(tid)}) == audits_after_first, "الخاسرُ كتب تدقيقًا"


@requires_db
async def test_07_a_stale_worker_cannot_write_after_takeover(
    two_tenants, _no_background,
):
    """(١٣) عاملٌ قديمٌ عاد بعد الاستعادة: **صفرُ كتابةٍ، وصفرُ حالٍ مكتوبة**."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    thesis_id = uuid.UUID(answer.json()["thesis_id"])
    old_claim = _no_background[0][1][2]

    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, slot["user_id"]) as session:
        new_claim = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert new_claim.fence != old_claim.fence, "السياجُ لم يتبدّل بالاستعادة"

    # والقديمُ يحاول أن يكتب — بالسياج البائت.
    async with tenant_session(tid, slot["user_id"]) as session:
        with pytest.raises(processing.ProcessingSuperseded):
            await processing.hold(session, old_claim, tenant_id=tid)
    async with tenant_session(tid, slot["user_id"]) as session:
        with pytest.raises(processing.ProcessingSuperseded):
            await processing.advance(session, old_claim, tenant_id=tid,
                                     state=processing.EXTRACTING)

    state, _a, changed, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    assert changed == new_claim.fence, "كتب البائتُ فوق سياجِ من استلم"
    assert state == processing.QUEUED, f"الحالُ تبدّلت بيدِ بائت: {state}"


@requires_db
async def test_08_concurrent_thesis_creation_yields_exactly_one(two_tenants):
    """(٦) طلبان متزامنان على ملفٍّ واحد: **رسالةٌ واحدةٌ**، ولا ٥٠٠."""
    import asyncio

    from athera_api.db import tenant_session
    from athera_api.services.document_intelligence import pipeline
    from tests.test_at_rc_t1_h3b_remaining_external_waits import _make_file

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    file_id = await _make_file(slot)

    async def _create():
        async with tenant_session(tid, uid) as session:
            thesis, created = await pipeline.ensure_thesis_for_file(
                session, tenant_id=tid, file_id=file_id)
            return thesis.id, created

    first, second = await asyncio.gather(_create(), _create())
    assert first[0] == second[0], "معرّفان مختلفان لملفٍّ واحد"
    assert [first[1], second[1]].count(True) == 1, "أُنشئت رسالتان"
    assert await _count(
        "SELECT count(*) FROM theses WHERE file_id = :f", {"f": str(file_id)}) == 1


# ═════════════════ ٢ · الأقسام: جيلُ تنفيذٍ لكلِّ قسمٍ على حدة ═════════════════


def _grant(slot, file_id):
    """إذنُ المعالجةِ الخارجيّة — فبدونه لا يُنادى نموذج."""
    from athera_api.db import tenant_session
    from athera_api.services import consent

    async def _run():
        async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
            await consent.record_decision(
                session, tenant_id=slot["tenant_id"], file_id=file_id,
                actor_user_id=slot["user_id"], granted=True,
                provider="anthropic", model="m")
    return _run()


def _batch():
    """حِملُ استخراجٍ صالحٌ بلا وقائع — فالمقصودُ عددُ النداءات لا محتواها."""
    return {"facts": []}


async def _ready_thesis(slot):
    """رسالةٌ مرفوعةٌ مأذونٌ لها، ومطالبةُ جيلها."""
    answer = await _upload(slot, key=uuid.uuid4().hex)
    body = answer.json()
    await _grant(slot, uuid.UUID(body["file_id"]))
    return uuid.UUID(body["thesis_id"]), uuid.UUID(body["file_id"])


class _DiesAfter:
    """مزوّدٌ ينجح مرّاتٍ ثمّ **تموت العمليّة** — لا يُخفق، بل يُقتَل.

    و`CancelledError` ليست `Exception`، فلا يلتقطها مسارُ الفشل: تخرج من
    العاملِ كما تخرج عند قتلِ العمليّة، وتُترك الحالُ **جارية** لا طرفيّة.
    وهذا هو ما يُحاكَى: إعادةُ نشرٍ أثناء العمل.
    """

    name = "fake"

    def __init__(self, succeed: int) -> None:
        self.succeed = succeed
        self.calls = 0

    async def generate_structured(self, request):
        import asyncio

        from athera_api.providers.base import ModelResponse, ModelUsage

        self.calls += 1
        if self.calls > self.succeed:
            raise asyncio.CancelledError("process died")
        return ModelResponse(
            content="", provider="fake", model="m",
            usage=ModelUsage(input_tokens=1, output_tokens=1, cost_usd=0.0,
                             latency_ms=1),
            structured=_batch())

    async def embed(self, texts, *, model=None):  # pragma: no cover
        return [[0.0] * 4 for _ in texts]

    async def stream(self, request):  # pragma: no cover
        yield ""


async def _ledger_rows(tid):
    return await _rows(
        "SELECT state, response_status FROM idempotency_records"
        "  WHERE tenant_id = :t AND operation = 'INTERNAL thesis.document.section'"
        "  ORDER BY created_at", {"t": str(tid)})


@requires_db
async def test_09_a_completed_section_is_never_called_again(
    two_tenants, _no_background, monkeypatch,
):
    """(١٥) قسمٌ تمّ ثمّ ماتت العمليّة: الاستئنافُ **لا ينادِيه ثانيةً**.

    ولا يُدرج مرشّحاتِه مرّتين — فـ«تمّ» أُودعت مع الأثر لا قبله.
    """
    import asyncio

    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, _file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    dying = _DiesAfter(succeed=1)
    _activate(monkeypatch, dying)
    with pytest.raises(asyncio.CancelledError):
        await di._process(tid, uid, claim, "ar")

    ledger = await _ledger_rows(tid)
    completed = [r for r in ledger if r[0] == "completed"]
    assert len(completed) == 1, f"لم يُثبَّت قسمٌ واحدٌ تامًّا: {ledger}"
    candidates = await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t", {"t": str(tid)})

    state, _a, _c, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    assert state in processing.IN_FLIGHT, f"ماتت العمليّةُ فصارت الحالُ {state}"

    # تُهجَر ثمّ تُستعاد **بالجيل نفسِه**.
    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, uid) as session:
        again = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert again.recovered is True, "لم تُعَدّ استعادةً"
    assert again.attempt == claim.attempt, "الاستعادةُ غيّرت الجيل"

    resumed = _DiesAfter(succeed=99)
    _activate(monkeypatch, resumed)
    await di._process(tid, uid, again, "ar")

    # **والدعوى دقيقة**: المستأنِفُ نادى الأقسامَ التي لا جيلَ لها وحدها.
    # فلكلِّ قسمٍ مخطَّطٍ صفٌّ في السِّجلّ بعد أن يمرّ عليه عاملٌ — فالفرقُ
    # بين ما كان وما صار هو عددُ ما نُودي، لا أكثر ولا أقلّ.
    after = await _ledger_rows(tid)
    assert resumed.calls == len(after) - len(ledger), (
        f"نُودي {resumed.calls} قسمًا، والجديدُ منها {len(after) - len(ledger)} — "
        "أي أُعيد نداءُ قسمٍ له جيلٌ سابق")
    assert len([r for r in after if r[0] == "completed"]) > len(completed)
    assert await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t",
        {"t": str(tid)}) >= candidates, "نقصت المرشّحاتُ بالاستئناف"
    assert await _count(
        "SELECT count(*) FROM extraction_runs WHERE tenant_id = :t",
        {"t": str(tid)}) == 1, "أُنشئت تشغيلةٌ ثانيةٌ للمحاولة نفسِها"


@requires_db
async def test_10_an_external_attempted_section_is_never_recalled(
    two_tenants, _no_background, monkeypatch,
):
    """(١٧/١٩) وُسم العبورُ ثمّ ماتت العمليّة: **صفرُ نداءٍ ثانٍ لذلك القسم**."""
    import asyncio

    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.idempotency import EXTERNAL_MARKER
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, _file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    # أوّلُ نداءٍ يُقتَل **بعد** أن وُسم عبورُ حدِّه.
    dying = _DiesAfter(succeed=0)
    _activate(monkeypatch, dying)
    with pytest.raises(asyncio.CancelledError):
        await di._process(tid, uid, claim, "ar")
    assert dying.calls == 1, dying.calls

    marked = await _rows(
        "SELECT response_body FROM idempotency_records WHERE tenant_id = :t"
        "   AND operation = 'INTERNAL thesis.document.section'", {"t": str(tid)})
    assert any(isinstance(r[0], dict) and EXTERNAL_MARKER in r[0] for r in marked), \
        f"لم يُدوَّن عبورُ الحدّ: {marked}"

    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, uid) as session:
        again = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert again.attempt == claim.attempt, "صار جيلًا جديدًا بلا قرارِ باحث"

    resumed = _DiesAfter(succeed=99)
    _activate(monkeypatch, resumed)
    await di._process(tid, uid, again, "ar")

    # **والقسمُ الموسومُ لم يُنادَ ثانيةً**، والبقيّةُ جاز لها مرّةً واحدة.
    after = await _ledger_rows(tid)
    assert resumed.calls == len(after) - len(marked), (
        f"نُودي {resumed.calls} قسمًا، والجديدُ منها {len(after) - len(marked)} — "
        "أي أُعيد نداءُ القسمِ الموسوم")
    still_unknown = [r for r in after if r[0] == "in_progress"]
    assert still_unknown, "زال الوسمُ عن القسم المجهول"

    state, _a, _c, _f, failure_code, failure_detail = await _thesis_row(tid, thesis_id)
    assert state == processing.FAILED, f"ادُّعي اكتمالٌ وقسمٌ مجهولُ الأثر: {state}"
    assert failure_code == "extraction_failed", failure_code
    assert "unknown" in (failure_detail or "").lower(), failure_detail
    for lie in ("provider failed", "did not run", "was not executed"):
        assert lie not in (failure_detail or "").lower(), failure_detail


@requires_db
async def test_11_a_new_deliberate_attempt_may_call_the_model_again(
    two_tenants, _no_background, monkeypatch,
):
    """(٢٠) إعادةٌ مقصودةٌ بعد غموض: جيلٌ جديد، وتشغيلةٌ جديدة، ونداءٌ مأذون."""
    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.document_intelligence import pipeline
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    calls = {"n": 0}

    class _Timeout:
        name = "fake"

        async def generate_structured(self, request):
            calls["n"] += 1
            raise TimeoutError("provider timed out")

    _activate(monkeypatch, _Timeout())
    await di._process(tid, uid, claim, "ar")
    ambiguous_calls = calls["n"]

    # والباحثُ يقرّر إعادةً جديدة — والحالُ طرفيّةٌ تقبلها.
    async with tenant_session(tid, uid) as session:
        fresh = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert fresh.recovered is False, "عُدَّت استعادةً وهي إعادةٌ مقصودة"
    assert fresh.attempt == claim.attempt + 1, "رقمُ المحاولةِ لم يزد"
    assert pipeline.run_id_for(tid, file_id, fresh.attempt) != \
        pipeline.run_id_for(tid, file_id, claim.attempt), "التشغيلةُ لم تتغيّر"

    await di._process(tid, uid, fresh, "ar")
    assert calls["n"] > ambiguous_calls, "الجيلُ الجديدُ لم يُؤذَن له بالنداء"


# ═════════════════ ٣ · التفويض، والفاعلُ التقنيّ، والإذن ═════════════════


@requires_db
async def test_12_recovery_is_not_an_authorization_bypass(two_tenants, _no_background):
    """(٢٢) سُحب الوصولُ قبل الاستعادة: **لا إعادةَ ولا جدولةَ ولا كشف**."""
    from athera_api.db import tenant_session
    from athera_api.models.identity import ObjectGrant
    from sqlalchemy import delete

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    key = uuid.uuid4().hex
    answer = await _upload(slot, key=key)
    body = answer.json()
    file_id = uuid.UUID(body["file_id"])
    await _make_stale(tid, uuid.UUID(body["thesis_id"]))

    # تُسحب المنحةُ عن الملفّ — كما يقع حين يُنزع الوصول.
    async with tenant_session(tid, slot["user_id"]) as session:
        await session.execute(delete(ObjectGrant).where(
            ObjectGrant.tenant_id == tid, ObjectGrant.object_type == "file",
            ObjectGrant.object_id == file_id))

    scheduled_before = len(_no_background)
    replay = await _upload(slot, key=key)

    assert replay.status_code in (403, 404), \
        f"{replay.status_code}: {replay.text[:220]}"
    assert len(_no_background) == scheduled_before, "جُدوِل عاملٌ بلا حقّ"


@requires_db
async def test_13_a_cross_actor_recovery_shares_one_section_generation(
    two_tenants, _no_background, monkeypatch,
):
    """(٢١) يستعيدها مستخدمٌ آخرُ مأذون: **الجيلُ نفسُه، وصفرُ نداءٍ مكرّر**.

    فلو نُسب جيلُ القسمِ إلى «من ضغط الاستعادة» لصار لكلِّ مستعيدٍ جيلُه،
    فيُنادى المزوّدُ مرّةً لكلِّ واحد. والفاعلُ التقنيُّ `File.uploaded_by`
    يمنع ذلك — وهو سياقُ RLS وحدَه لا تفويض.
    """
    import asyncio

    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate
    from tests.test_at_rc_t1a_project_access import _second_user

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    dying = _DiesAfter(succeed=1)
    _activate(monkeypatch, dying)
    with pytest.raises(asyncio.CancelledError):
        await di._process(tid, uid, claim, "ar")
    before = await _ledger_rows(tid)

    # زميلٌ آخرُ في المستأجر نفسِه يستعيد — والفاعلُ التقنيُّ لا يتغيّر.
    colleague = await _second_user(
        tid, email=f"recoverer-{uuid.uuid4().hex[:8]}@fixtures.athera")
    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, colleague["user_id"]) as session:
        again = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)

    resumed = _DiesAfter(succeed=99)
    _activate(monkeypatch, resumed)
    # ويعمل العاملُ **باسم الزميل** — والسِّجلُّ يبقى منسوبًا إلى الرافع.
    await di._process(tid, colleague["user_id"], again, "ar")

    after = await _ledger_rows(tid)
    assert resumed.calls == len(after) - len(before), (
        f"نادى المستعيدُ الآخرُ {resumed.calls} قسمًا والجديدُ "
        f"{len(after) - len(before)} — أي أنشأ جيلًا موازيًا")
    subjects = await _rows(
        "SELECT DISTINCT actor_user_id FROM idempotency_records"
        "  WHERE tenant_id = :t AND operation = 'INTERNAL thesis.document.section'",
        {"t": str(tid)})
    assert len(subjects) == 1, f"جيلُ القسمِ انقسم بين فاعلَين: {subjects}"
    assert str(subjects[0][0]) == str(uid), "الفاعلُ التقنيُّ ليس رافعَ الملفّ"


@requires_db
async def test_14_a_repeated_consent_grant_starts_no_second_attempt(
    two_tenants, _no_background,
):
    """(٢٣) منحٌ مكرَّر: **لا محاولةَ ثانيةً لمجرّد إعادةِ الطلب**."""
    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    body = answer.json()
    thesis_id = body["thesis_id"]

    grant_url = f"/api/v1/theses/{thesis_id}/consent"
    async with _client(slot) as http:
        first = await http.post(grant_url, json={"decision": "grant"})
        assert first.status_code == 200, first.text
        _s, attempts_after_first, _c, _f, _fc, _fd = await _thesis_row(
            tid, uuid.UUID(thesis_id))
        scheduled = len(_no_background)

        second = await http.post(grant_url, json={"decision": "grant"})
        assert second.status_code == 200, second.text

    _s2, attempts_after_second, _c2, _f2, _fc2, _fd2 = await _thesis_row(
        tid, uuid.UUID(thesis_id))
    assert attempts_after_second == attempts_after_first, (
        f"منحٌ مكرَّرٌ بدأ محاولةً جديدة: {attempts_after_first} ← "
        f"{attempts_after_second}")
    assert len(_no_background) == scheduled, "جُدوِل عاملٌ ثانٍ لمنحٍ مكرَّر"


@requires_db
async def test_15_a_consent_grant_that_lost_its_dispatch_is_recoverable(
    two_tenants, _no_background,
):
    """(٢٤) منحٌ ضاعت جدولتُه: الجيلُ يُهجَر، ثمّ يُستعاد بالرقم نفسِه."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    thesis_id = uuid.UUID(answer.json()["thesis_id"])

    async with _client(slot) as http:
        granted = await http.post(f"/api/v1/theses/{thesis_id}/consent",
                                  json={"decision": "grant"})
        assert granted.status_code == 200, granted.text

    _s, attempts, _c, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, slot["user_id"]) as session:
        claim = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert claim.recovered is True
    assert claim.attempt == attempts, "الاستعادةُ زادت رقمَ المحاولة"


@requires_db
async def test_16_recovery_past_the_ledger_horizon_starts_a_new_generation(
    two_tenants, _no_background,
):
    """(٢٥) محاولةٌ أقدمُ من أفقِ السِّجلّ: **لا استعادةٌ صامتة**.

    فسِجلُّها لم يعد يُثبت ما تمّ، فاستعادتُها تعني نداءً أعمى. فيبدأ جيلٌ
    **جديدٌ مقصود** — رقمٌ جديدٌ ومفاتيحُ أقسامٍ جديدة — أو تُردّ بصدق.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session
    from athera_api.services.document_intelligence import pipeline
    from athera_api.services.idempotency import TTL
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h3_ai_long_transactions import _observer

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    answer = await _upload(slot, key=uuid.uuid4().hex)
    body = answer.json()
    thesis_id, file_id = uuid.UUID(body["thesis_id"]), uuid.UUID(body["file_id"])
    claim = _no_background[0][1][2]

    # تشغيلةٌ للمحاولة، بُدئت قبل الأفق — كمحاولةٍ هُجرت منذ أيّام.
    run_id = pipeline.run_id_for(tid, file_id, claim.attempt)
    from athera_api.models.research import ExtractionRun
    from athera_api.services.document_intelligence.states import Status
    async with tenant_session(tid, uid) as session:
        session.add(ExtractionRun(
            id=run_id, tenant_id=tid, file_id=file_id,
            extractor="document_intelligence", status=Status.PARSING.value,
            chunks_parsed=0, candidates_proposed=0,
            candidates_rejected_unquoted=0,
            started_at=__import__("datetime").datetime.now(
                __import__("datetime").UTC)))

    # **واسمٌ آخرُ عمدًا**: `session` يخصّ نطاقَ `tenant_session` الذي أُغلق،
    # وإعادةُ استعماله تُخفي عمرَ الجلسة — وهو ما يرصده حارسُ دورة الحياة.
    engine, factory = await _observer()
    try:
        async with factory() as observer:
            await observer.execute(
                text("UPDATE extraction_runs SET started_at ="
                     "        now() - make_interval(secs => :back)"
                     " WHERE id = :r"),
                {"back": int(TTL.total_seconds()) + 3600, "r": str(run_id)})
            await observer.commit()
    finally:
        await engine.dispose()

    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, uid) as session:
        fresh = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)

    assert fresh.recovered is False, "استُعيدت محاولةٌ تجاوزت أفقَ سِجلِّها"
    assert fresh.attempt == claim.attempt + 1, (
        f"لم يبدأ جيلٌ جديد: {claim.attempt} ← {fresh.attempt}")
    assert pipeline.run_id_for(tid, file_id, fresh.attempt) != run_id


@requires_db
async def test_17_no_raw_idempotency_key_is_ever_persisted(two_tenants, _no_background):
    """(٢٧) المفتاحُ الخامُّ لا يُخزَّن — لا في جدولٍ ولا في تدقيقٍ ولا في صفٍّ."""
    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    key = f"b5raw{uuid.uuid4().hex}"
    answer = await _upload(slot, key=key)
    assert answer.status_code == 202, answer.text

    for table, column in (
        ("idempotency_records", "key_digest"),
        ("audit_events", "state_after::text"),
        ("theses", "failure_detail"),
        ("extraction_runs", "error"),
    ):
        hits = await _count(
            f"SELECT count(*) FROM {table} WHERE tenant_id = :t"
            f"   AND coalesce({column}, '') LIKE :k",
            {"t": str(tid), "k": f"%{key}%"})
        assert hits == 0, f"المفتاحُ الخامُّ ظهر في {table}.{column}"


# ═════════════════ ٤ · التحضيرُ المحلّيّ، والتوأم، والتنقيب ═════════════════


@requires_db
async def test_18_a_crash_after_local_prepare_duplicates_nothing(
    two_tenants, _no_background, monkeypatch,
):
    """(١٤) سقوطٌ بعد التحضير: تشغيلةٌ ثابتة، ومقاطعُ كما هي، وحتميٌّ لا يُكرَّر."""
    import asyncio

    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    # يموت عند أوّل قسم — أي بعد أن تمّ التحضيرُ المحلّيُّ وأُودع.
    _activate(monkeypatch, _DiesAfter(succeed=0))
    with pytest.raises(asyncio.CancelledError):
        await di._process(tid, uid, claim, "ar")

    chunks = await _count(
        "SELECT count(*) FROM document_chunks WHERE file_id = :f", {"f": str(file_id)})
    deterministic = await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t", {"t": str(tid)})
    runs = await _rows(
        "SELECT id FROM extraction_runs WHERE tenant_id = :t", {"t": str(tid)})
    assert chunks > 0, "لم يُفكَّك المستندُ أصلًا — فالفحصُ فارغ"
    assert len(runs) == 1, runs

    await _make_stale(tid, thesis_id)
    async with tenant_session(tid, uid) as session:
        again = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    _activate(monkeypatch, _DiesAfter(succeed=0))
    with pytest.raises(asyncio.CancelledError):
        await di._process(tid, uid, again, "ar")

    assert await _count(
        "SELECT count(*) FROM document_chunks WHERE file_id = :f",
        {"f": str(file_id)}) == chunks, "تضاعفت المقاطعُ بالاستئناف"
    assert await _count(
        "SELECT count(*) FROM fact_candidates WHERE tenant_id = :t",
        {"t": str(tid)}) == deterministic, "تضاعف المرشّحُ الحتميُّ بالاستئناف"
    assert await _rows(
        "SELECT id FROM extraction_runs WHERE tenant_id = :t",
        {"t": str(tid)}) == runs, "أُنشئت تشغيلةٌ ثانيةٌ للمحاولة نفسِها"


@requires_db
async def test_19_a_pre_provider_refusal_leaves_no_marker(
    two_tenants, _no_background, monkeypatch,
):
    """(١٨) رفضٌ **قبل** الحدّ: لا وسمَ عبور، والقسمُ يبقى قابلًا لإعادةٍ صادقة."""
    from athera_api.config import get_settings
    from athera_api.routers import document_intelligence as di
    from athera_api.services.idempotency import EXTERNAL_MARKER
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _Structured, _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    _thesis_id, _file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]

    calls = {"n": 0}

    class _Counted(_Structured):
        async def generate_structured(self, request):
            calls["n"] += 1
            return await super().generate_structured(request)

    _activate(monkeypatch, _Counted(_batch()))
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    # **والرفضُ يقع في البوّابة بعينها** — بعد التحضيرِ المحلّيِّ وقبل النداء.
    # ولا يُخفَّض السقفُ لذلك: إذنُ الباحثِ يرفع سقفَ قدرته فيتجاوزه، فيُمنع
    # الطلبُ من موضعِ المنع نفسِه.
    from athera_api.errors import AtheraError
    from athera_api.providers.gateway import ModelGateway

    def _refuse(self, request, grant=None):
        raise AtheraError("provider.disabled_for_classification", status_code=403,
                          classification=request.classification, ceiling="C0")

    monkeypatch.setattr(ModelGateway, "authorize", _refuse)
    await di._process(tid, uid, claim, "ar")

    assert calls["n"] == 0, "نُودي النموذجُ رغم الرفضِ قبل الحدّ"
    rows = await _rows(
        "SELECT state, response_body FROM idempotency_records WHERE tenant_id = :t"
        "   AND operation = 'INTERNAL thesis.document.section'", {"t": str(tid)})
    for state, body in rows:
        assert not (isinstance(body, dict) and EXTERNAL_MARKER in body), \
            "وُسم عبورُ حدٍّ ولا نداءَ وقع"
        assert state != "completed", "أُثبت تمامُ قسمٍ لم يُنفَّذ"


@requires_db
async def test_20_a_live_process_file_twin_starts_one_attempt(
    two_tenants, _no_background,
):
    """(٧) توأمٌ حيٌّ على `process-file`: **محاولةٌ واحدة**، والثاني يُردّ."""
    from tests.test_at_rc_t1_h3b_remaining_external_waits import _make_file

    slot = two_tenants["a"]
    tid = slot["tenant_id"]
    file_id = await _make_file(slot)
    url = f"/api/v1/theses/process-file/{file_id}"

    async with _client(slot) as http:
        first = await http.post(url)
        assert first.status_code == 202, f"{first.status_code}: {first.text[:220]}"
        twin = await http.post(url)

    assert twin.status_code == 409, f"{twin.status_code}: {twin.text[:220]}"
    thesis_id = uuid.UUID(first.json()["thesis_id"])
    _s, attempts, _c, _f, _fc, _fd = await _thesis_row(tid, thesis_id)
    assert attempts == 1, f"بدأ توأمٌ حيٌّ محاولةً ثانية: {attempts}"
    assert await _count("SELECT count(*) FROM theses WHERE file_id = :f",
                        {"f": str(file_id)}) == 1


@requires_db
async def test_21_recovery_does_not_duplicate_mining_opportunities(
    two_tenants, _no_background, monkeypatch,
):
    """(٢٦) الاستئنافُ لا يُضاعف الفرص — والتنقيبُ يبقى في معاملته."""
    from athera_api.config import get_settings
    from athera_api.db import tenant_session
    from athera_api.routers import document_intelligence as di
    from athera_api.services.thesis import processing
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _Structured, _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    thesis_id, _file_id = await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)

    _activate(monkeypatch, _Structured(_batch()))
    await di._process(tid, uid, claim, "ar")
    opportunities = await _count(
        "SELECT count(*) FROM publication_opportunities WHERE tenant_id = :t",
        {"t": str(tid)})

    # إعادةٌ مقصودةٌ بعد الاكتمال — والفرصُ لا تتضاعف.
    async with tenant_session(tid, uid) as session:
        again = await processing.claim_generation(
            session, tenant_id=tid, thesis_id=thesis_id)
    await di._process(tid, uid, again, "ar")

    assert await _count(
        "SELECT count(*) FROM publication_opportunities WHERE tenant_id = :t",
        {"t": str(tid)}) == opportunities, "تضاعفت فرصُ النشر"


def test_22_no_transaction_spans_an_external_wait() -> None:
    """(٢٨) ماسحُ H3 نظيف — ولا معاملةَ تمتدّ على تخزينٍ أو نموذج."""
    import sys

    sys.path.insert(0, "tests")
    from external_wait_audit import audit

    offenders = list(audit().offenders())
    assert offenders == [], f"معاملةٌ تمتدّ على انتظارٍ خارجيّ: {offenders}"


def test_23_the_worker_converts_its_claim_before_anything_else() -> None:
    """**ولا يُصدَّق الرمزُ الممرَّرُ بلا فحص** — وأوّلُ فعلٍ هو التحويل.

    والسياجُ على كلِّ كتابةٍ يمنع الخاسرَ أن يكتب، وذاك صحيح. لكنّ العقدَ
    أضيقُ من ذلك: **أوّلُ فعلٍ في القاعدة** تحويلُ المطالبة. فبدونه يمضي
    الخاسرُ في قراءةٍ وجلبٍ من التخزين وتفكيكٍ قبل أن يُردّ — عملٌ مدفوعٌ
    لا أثرَ له، وقد يكون نداءً خارجيًّا.

    فيُقاس بالبنية: `start_worker` تُنادى، وقبل أيّ نداءٍ للخطّ أو للتخزين،
    والانسحابُ عند `None` صريح.
    """
    import ast
    import inspect
    import textwrap

    from athera_api.routers import document_intelligence as router_module

    source = textwrap.dedent(inspect.getsource(router_module._process))
    tree = ast.parse(source)

    starts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call)
              and ast.unparse(n.func).endswith("start_worker")]
    assert starts, "العاملُ لا يُحوّل مطالبتَه أصلًا"

    LATER = ("run_extraction", "get_store", "run_in_threadpool", "_model_reader",
             "authorization_for")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if any(name.endswith(later) for later in LATER):
            assert node.lineno > min(starts), (
                f"`{name}` يقع قبل تحويلِ المطالبة — فالخاسرُ يعمل قبل أن يُردّ")

    # والانسحابُ صريحٌ عند الخسارة، لا مجرّدُ اتّكالٍ على السياج.
    assert "if started is None" in source, "لا انسحابَ صريحٌ للعاملِ الخاسر"


@requires_db
async def test_24_a_section_is_not_settled_unless_its_candidates_are_durable(
    two_tenants, _no_background, monkeypatch,
):
    """**«تمّ» تُودَع مع الأثر أو لا تُودَع** — وهذا شرطُ الصحّةِ كلِّه.

    فلو سبقت «تمّ» حفظَ المرشّحات لرأى الاستئنافُ قسمًا تامًّا **بلا أثر**،
    فيتخطّاه — فيضيع عملٌ دُفع ثمنُه، بصمت. فيُكسر الحفظُ عمدًا، ويُشترط
    ألّا يبقى للقسم إثباتُ تمام.
    """
    from athera_api.config import get_settings
    from athera_api.routers import document_intelligence as di
    from athera_api.services.document_intelligence import pipeline
    from tests.test_at_rc_t1_h2b4_model_ambiguity import _Structured, _activate

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    await _ready_thesis(slot)
    claim = _no_background[0][1][2]
    monkeypatch.setattr(get_settings(), "model_external_send_max_classification",
                        "C2", raising=False)
    _activate(monkeypatch, _Structured(_batch()))

    async def _broken_absorb(*args, **kwargs):
        raise RuntimeError("candidate write failed")

    monkeypatch.setattr(pipeline, "absorb", _broken_absorb)
    await di._process(tid, uid, claim, "ar")

    settled = [r for r in await _ledger_rows(tid) if r[0] == "completed"]
    assert settled == [], (
        "أُثبت تمامُ قسمٍ ومرشّحاتُه لم تُودَع — فاستئنافٌ سيتخطّاه ويضيع عملُه")


@requires_db
async def test_25_the_same_section_with_other_science_conflicts(two_tenants):
    """بصمةُ القسمِ معنًى علميّ — فمُدخلٌ آخرُ تحت الجيل نفسِه **صِدام**.

    ولولا الملفُّ والمطالبةُ في البصمة لصار الجيلُ يقبل أيَّ مُدخلٍ ويُعيد
    عليه «تمّ» — أي إثباتُ تمامٍ لعملٍ لم يقع على هذه الأدلّة.
    """
    from athera_api.db import tenant_session
    from athera_api.services.document_intelligence import section_ledger

    slot = two_tenants["a"]
    tid, uid = slot["tenant_id"], slot["user_id"]
    run_id = uuid.uuid4()

    def _fp(prompt: str, checksum: str):
        return section_ledger.section_fingerprint(
            run_id=run_id, section="problem", checksum_sha256=checksum,
            prompt=prompt, chunks=(("c1", "h1"),), field_keys=("x",),
            locale="ar", provider="openai", model="m", capability="cap")

    async with tenant_session(tid, uid) as session:
        gate = await section_ledger.open_section(
            session, tenant_id=tid, subject_id=uid, run_id=run_id,
            section="problem", fingerprint=_fp("prompt-one", "a" * 64))
        assert gate.outcome == "granted", gate.outcome
        await section_ledger.settle_section(session, gate.lease,
                                            accepted=1, rejected=0)

    async with tenant_session(tid, uid) as session:
        same = await section_ledger.open_section(
            session, tenant_id=tid, subject_id=uid, run_id=run_id,
            section="problem", fingerprint=_fp("prompt-one", "a" * 64))
    assert same.outcome == "completed", f"لم يُعرَف القسمُ التامّ: {same.outcome}"

    async with tenant_session(tid, uid) as session:
        other = await section_ledger.open_section(
            session, tenant_id=tid, subject_id=uid, run_id=run_id,
            section="problem", fingerprint=_fp("prompt-two", "b" * 64))
    assert other.outcome == "conflict", (
        f"مُدخلٌ علميٌّ آخرُ قُبل تحت الجيل نفسِه: {other.outcome}")
    assert not other.may_call_provider, "أُذن بنداءِ مزوّدٍ على صِدام"
