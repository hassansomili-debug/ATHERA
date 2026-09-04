"""الرفع الموقّع ينزل في المجلَّد | My Library V2.1 — the signed upload path.

**كان للمكتبة بابا رفعٍ يفترقان في أمرٍ واحد يهمّ صاحبها.** الرفعُ المباشر
(`POST /files/upload`) يقبل `folder_id` فينزل الملف حيث يقف الباحث؛ والرفعُ
الموقّع (`POST /files` ثم `/complete`) لا يعرف الحقل أصلًا، فينزل في الجذر
مهما كان المجلَّد المفتوح. ولا رسالةَ ولا سبب — والباحث لا يعرف أيّ بابٍ
استعمله عميلُه، ولا يجب أن يعرف.

وهذا الملف يثبت أربعة:

١) **الموضع يعبر المسار كلَّه**: نيّةٌ تحمل `folder_id`، وردٌّ يعلنه،
   وصفٌّ يُكتب به من أول لحظة، وختمٌ يُبقيه — أو ينقله بقولٍ أخير صريح.
٢) **الوجهة تُحرَس قبل أن يُصدر رابطٌ موقّع**: مجلَّدٌ لا وجود له أو
   لمستأجرٍ آخر ⇐ 404، ومجلَّدٌ يُرى ولا يُملك ⇐ 403، ومعرّفٌ غير صالح
   ⇐ 422. **ولا 500 في واحدةٍ منها.**
٣) **مفتاح التخزين لا يذكر المجلَّد**: المفتاح نفسه حرفًا بحرف سواء نزل
   الملف في الجذر أو في «كتب المنهج» — فنقلُ ملفٍ بين رفَّين يبقى تغييرَ
   عمود، لا نسخَ كائنٍ يكسر كل رابطٍ موقّع وكلّ سجلّ إسناد.
٤) **الختم لا يكتب إلا وقائع الرفع**: البصمة والحال ووقت الاكتمال
   والموضع — ولا شيء غيرها.
"""
from __future__ import annotations

import inspect
import re
import uuid

import pytest

from tests.conftest import requires_db

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ═════════════════ اختبارات خالصة: ما يُقرأ بلا قاعدة ═════════════════

def test_both_upload_paths_take_the_folder_the_researcher_stands_in():
    """بابان إلى مكتبةٍ واحدة — **ولا يفترقان في أين ينزل الملف**.

    والفرق كان صامتًا: من رفع بعميلٍ يستعمل الرابط الموقّع وجد ملفه في
    الجذر، ومن رفع من الشاشة وجده في مجلَّده. وهما فعلٌ واحد عند صاحب
    المكتبة، فاختلافُ نتيجتهما عطبٌ لا خيار.
    """
    from athera_api.routers.files import upload_file
    from athera_api.schemas.files import FileCompleteRequest, FileInitRequest, FileInitResponse

    assert "folder_id" in inspect.signature(upload_file).parameters, (
        "الرفع المباشر فقد `folder_id`")
    for model in (FileInitRequest, FileCompleteRequest, FileInitResponse):
        assert "folder_id" in model.model_fields, (
            f"{model.__name__} لا يحمل الموضع — فينقطع في هذه الحلقة")


def test_the_signed_response_tells_the_client_where_the_file_will_land():
    """ردُّ النيّة يُعلن الموضع، فلا يخمّن العميل ما قرّره الخادم.

    ولو أضمره الخادم لعرض العميل «الرفع إلى: مكتبتي» بينما الصفّ يقول
    غير ذلك — وعدٌ في الشاشة يخالف ما في القاعدة.
    """
    from athera_api.routers import files as router

    source = inspect.getsource(router.init_upload)
    assert "folder_id=payload.folder_id" in source, (
        "النيّة لا تُعيد الموضع الذي أعلنته")


def test_the_storage_key_can_not_encode_a_folder_because_it_never_sees_one():
    """**المفتاح عنوانُ كائن، لا مسارٌ في نظام ملفات.**

    فلو حُشر فيه مسارُ المجلَّد لصار نقلُ ملفٍ بين رفَّين نسخًا في المخزن،
    ولانكسر معه كلُّ رابطٍ موقّع صدر من قبل وكلُّ سجلّ `provenance` يذكر
    الموضع القديم. والحارس يقرأ التوقيع نفسه: الدالّة لا تقبل مجلَّدًا
    أصلًا، فلا سبيل إلى تسريبه إليها.
    """
    from athera_api.services import storage

    parameters = set(inspect.signature(storage.build_storage_key).parameters)
    assert "folder_id" not in parameters and "folder" not in parameters, (
        f"`build_storage_key` صار يقبل مجلَّدًا: {sorted(parameters)}")

    tenant, file_id = uuid.uuid4(), uuid.uuid4()
    # المفتاح نفسه حرفًا بحرف مهما تكرّر البناء — ولا مدخل للمجلَّد فيه.
    assert (storage.build_storage_key(tenant, file_id, "المنهج.pdf")
            == storage.build_storage_key(tenant, file_id, "المنهج.pdf"))


def test_no_upload_path_passes_anything_folder_shaped_into_the_key():
    """والحارس الثاني: **لا موضع استدعاءٍ يمرّر مجلَّدًا إلى بناء المفتاح**.

    فحصُ التوقيع وحده يمرّ لو حُشر المجلَّد في اسم الملف — وهو أسهل طريقٍ
    إلى العطب نفسه من بابٍ خلفي.
    """
    from athera_api.routers import files as router

    source = inspect.getsource(router)
    calls = re.findall(r"build_storage_key\((.*?)\)", source, flags=re.S)
    assert calls, "لم يُعثر على أي استدعاء لبناء المفتاح"
    for call in calls:
        assert "folder" not in call, f"مجلَّدٌ يتسرّب إلى مفتاح التخزين: {call!r}"


def test_completing_an_upload_writes_the_upload_facts_and_nothing_else():
    """الختمُ يكتب البصمة والحال ووقت الاكتمال والموضع — **لا أكثر**.

    ولو كتب يومًا في رابط بحثٍ أو حال مرشّحٍ أو مفتاح تخزين، لفقد الباحث
    سند ورقته في آخر خطوةٍ من رفعٍ نجح. والمسار يُقرأ نصًّا بلا شرحه، فلا
    يُخدع الفحص بتوثيقٍ صادق يذكر ما لا يُمسّ.
    """
    from athera_api.routers import files as router

    source = inspect.getsource(router.complete_upload).replace(
        router.complete_upload.__doc__, "")
    assigned = set(re.findall(r"record\.([a-z_0-9]+)\s*=", source))
    assert assigned == {"checksum_sha256", "status", "completed_at", "folder_id"}, (
        f"ختمُ الرفع يكتب حقولًا لا تخصّه: {sorted(assigned)}")
    # والمفتاح **يُقرأ ولا يُكتب**: سجلّ الإسناد يذكره موضعًا للأصل، وذلك
    # كلُّ ما للختم به. فمن قرأ حقلًا لم يغيّره.
    assert "source_locator=record.storage_key" in source, (
        "سجلّ الإسناد لا يذكر مفتاح التخزين موضعًا للأصل")
    assert "record.storage_key =" not in source, (
        "الختم يكتب في مفتاح التخزين — والمفتاح يُبنى مرّة عند النيّة ويبقى")


def test_the_folder_guard_is_one_definition_that_every_door_reads():
    """**أربعةُ أبوابٍ إلى الحقل نفسه، وفحصٌ واحد.**

    ولو كتب كل بابٍ فحصه لافترقت الأربعة بأول تعديل: يُشدَّد بابٌ وتبقى
    ثلاثةٌ مفتوحة، ولا يظهر ذلك في أي اختبارٍ يقيس بابًا واحدًا.
    """
    from athera_api.routers import files as router

    for endpoint in (router.init_upload, router.complete_upload,
                     router.upload_file, router.move_file):
        assert "_writable_folder" in inspect.getsource(endpoint), (
            f"{endpoint.__name__} لا يمرّ بالفحص الموحَّد للوجهة")


def test_the_folder_guard_answers_with_a_code_not_with_a_five_hundred():
    """رمزٌ يقول ما وقع — لا «حدث خطأ غير متوقع».

    و404 و403 يفترقان عمدًا: الأول «لا وجود له عندك» (والعزل يمنع رؤية
    مجلَّد غيرك أصلًا فلا يفشي التخمينُ خبرًا)، والثاني «تراه ولا تملكه».
    وجمعُهما في رمزٍ واحد يترك الباحث لا يعرف أيّ الأمرين وقع.
    """
    from athera_api.services import library

    # والتعريف في الخدمة لا في الموجّه: الفعل الجماعيّ في موجّهٍ ثانٍ يقرأ
    # الحارس نفسه، ونسختان منه تفترقان بأول تعديل.
    source = inspect.getsource(library.assert_writable)
    assert "get_folder" in source, "لا فحص لوجود المجلَّد"
    assert "require_object_action" in source, "لا فحص للمنحة على المجلَّد"
    assert "except" not in source, "الفحص يبتلع استثناءً فيصير الرفض صامتًا"


def test_a_silent_body_at_complete_keeps_the_place_the_intent_announced():
    """**السكوت يُبقي، ولا يسحب الملف إلى الجذر.**

    وكلُّ عميلٍ كُتب قبل هذا التغيير يختم بلا `folder_id`. فلو عومل الغياب
    معاملة «الجذر» لنقض الختمُ ما وعدت به النيّة في آخر خطوة — وهو بعينه
    العطب الذي يعالجه هذا التغيير، يُعاد إدخاله من باب التوافق.
    """
    from athera_api.schemas.files import FileCompleteRequest

    silent = FileCompleteRequest(checksum_sha256="0" * 64)
    assert silent.folder_named is False
    assert silent.folder_id is None

    known = uuid.uuid4()
    named = FileCompleteRequest(checksum_sha256="0" * 64, folder_id=known)
    assert named.folder_named is True and named.folder_id == known

    # و`null` صريحةٌ قولٌ أخير: «إلى الجذر» — تُفرَّق عن الغياب.
    to_root = FileCompleteRequest.model_validate(
        {"checksum_sha256": "0" * 64, "folder_id": None})
    assert to_root.folder_named is True and to_root.folder_id is None


# ══════════════════════ اختبارات تمسّ القاعدة ══════════════════════

pytest_asyncio = pytest.importorskip("pytest_asyncio")


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    """تخزين معزول لكل اختبار — بلا شبكة وبلا اعتماد إنتاج.

    والرابط الموقّع يحتاج مخزنًا يوقّع؛ و`UnconfiguredStore` يردّ 503 فتصير
    الاختبارات تقيس غياب الإعداد لا سلوك المجلَّد.
    """
    from athera_api.config import get_settings
    from athera_api.services import storage

    settings = get_settings()
    monkeypatch.setattr(settings, "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield storage.get_store()
    storage.reset_store_cache()


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


@pytest_asyncio.fixture
async def clients(two_tenants):
    made = {slot: _client(two_tenants[slot]["tenant_id"], two_tenants[slot]["user_id"])
            for slot in ("a", "b")}
    yield made
    for http in made.values():
        await http.aclose()
    from athera_api.db import engine
    await engine.dispose()


async def _make_folder(http, name: str, parent: str | None = None) -> dict:
    response = await http.post("/api/v1/files/folders",
                               json={"name": name, "parent_folder_id": parent})
    assert response.status_code == 201, response.text
    return response.json()


def _intent(folder: str | None = None, name: str = "أثر البرنامج.pdf") -> dict:
    body = {"filename": name, "content_type": "application/pdf",
            "size_bytes": 4096, "classification": "C2"}
    if folder is not None:
        body["folder_id"] = folder
    return body


async def _row(tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.files import File

    async with tenant_session(tenant_id, user_id) as session:
        return (await session.execute(
            select(File).where(File.id == file_id))).scalar_one()


@requires_db
@pytest.mark.asyncio
async def test_a_signed_upload_lands_in_the_folder_it_named(clients, two_tenants):
    """**من نيّةٍ إلى صفّ: الموضع يعبر الحلقات الأربع كلها.**

    ويُقاس في كل حلقة على حدة — الردّ، والصفّ المعلَّق قبل الختم، والصفّ
    بعده، والقائمة التي يقرؤها الباحث. فحلقةٌ تكسر وحدها تُنتج ملفًّا في
    غير موضعه، وهو ما لا يظهر في اختبارٍ يقيس الطرفين فقط.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    shelf = await _make_folder(a, "كتب المنهج")

    started = await a.post("/api/v1/files", json=_intent(shelf["id"]))
    assert started.status_code == 201, started.text
    body = started.json()
    assert body["folder_id"] == shelf["id"], "ردُّ النيّة لا يعلن الموضع"

    file_id = uuid.UUID(body["file_id"])
    pending = await _row(tid, uid, file_id)
    assert pending.status == "pending"
    assert pending.folder_id == uuid.UUID(shelf["id"]), (
        "الصفّ المعلَّق نزل في الجذر — والموضع يُكتب من أول لحظة")

    done = await a.post(f"/api/v1/files/{file_id}/complete",
                        json={"checksum_sha256": "a" * 64})
    assert done.status_code == 200, done.text
    assert done.json()["folder_id"] == shelf["id"], (
        "الختمُ سحب الملف إلى الجذر — والسكوت يُبقي لا يُلغي")

    inside = (await a.get(f"/api/v1/files?folder={shelf['id']}")).json()
    assert [row["id"] for row in inside] == [str(file_id)]
    at_root = (await a.get("/api/v1/files?folder=root")).json()
    assert all(row["id"] != str(file_id) for row in at_root)


@requires_db
@pytest.mark.asyncio
async def test_the_signed_key_names_no_folder_at_all(clients, two_tenants):
    """المفتاح لا يذكر المجلَّد — لا معرّفًا ولا اسمًا.

    ولو ذكره لكان كلُّ نقلٍ بين مجلَّدين نسخًا في المخزن، ولانكسر كلُّ
    رابطٍ موقّع صدر قبله وكلُّ سجلّ إسنادٍ يشير إلى الموضع القديم.
    """
    a = clients["a"]
    shelf = await _make_folder(a, "رفٌّ ذو اسمٍ مميّز")

    at_root = (await a.post("/api/v1/files", json=_intent())).json()
    in_shelf = (await a.post("/api/v1/files", json=_intent(shelf["id"]))).json()

    for key in (at_root["storage_key"], in_shelf["storage_key"]):
        assert shelf["id"] not in key, "معرّف المجلَّد في مفتاح التخزين"
        assert "رفٌّ" not in key and "folders" not in key, "مسارُ مجلَّدٍ في المفتاح"

    # والشكل واحد: المستأجر ثم الملف — يفترقان في معرّف الملف لا في المجلَّد.
    def shape(key: str, file_id: str) -> str:
        return key.replace(file_id, "<file>")

    assert (shape(at_root["storage_key"], at_root["file_id"])
            == shape(in_shelf["storage_key"], in_shelf["file_id"])), (
        "المجلَّد غيّر شكل المفتاح")


@requires_db
@pytest.mark.asyncio
async def test_a_folder_that_is_not_yours_is_refused_before_a_single_byte(
        clients, two_tenants):
    """**الرفض قبل الرابط، لا بعد أن يبثّ الباحث كتابه.**

    ورفضٌ عند الختم بعد رفعٍ استغرق دقائق هو وعدٌ يُقطع بعد أن دُفع ثمنه.
    والرموز تُقال: 404 لما لا يُرى، و403 لما يُرى ولا يُملك، و422 لمعرّفٍ
    ليس معرّفًا — **ولا واحدة منها 500**.
    """
    a, b = clients["a"], clients["b"]
    mine = await _make_folder(a, "مجلَّدي أنا")

    stranger = await b.post("/api/v1/files", json=_intent(mine["id"]))
    assert stranger.status_code == 404, stranger.text
    assert stranger.json()["error"]["code"] == "library.folder_not_found"

    ghost = await a.post("/api/v1/files", json=_intent(str(uuid.uuid4())))
    assert ghost.status_code == 404

    malformed = await a.post("/api/v1/files", json=_intent("not-a-uuid"))
    assert malformed.status_code == 422, malformed.text

    # ولا صفَّ يتيمًا خلّفه أيٌّ من الثلاثة: الرفض قبل الكتابة.
    everything = (await b.get("/api/v1/files")).json()
    assert all(row["folder_id"] != mine["id"] for row in everything)


@requires_db
@pytest.mark.asyncio
async def test_a_colleague_who_sees_the_folder_still_may_not_upload_into_it(
        clients, two_tenants):
    """العزل لا يفصل داخل المستأجر — **والمنحة هي التي تفصل**.

    وباحثان في مساحةٍ واحدة يريان المكتبة نفسها؛ فمن لا يملك المجلَّد لا
    يضع فيه شيئًا، لا بالنقل ولا بالرفع.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    a = clients["a"]
    tid = two_tenants["a"]["tenant_id"]
    folder = await _make_folder(a, "مجلَّد صاحب المكتبة")

    async with tenant_session(tid) as session:
        user = User(email=f"colleague-{uuid.uuid4().hex[:8]}@example.test",
                    password_hash=hash_password("correct-horse-battery-staple"),
                    full_name_ar="زميل", full_name_en="Colleague")
        session.add(user)
        await session.flush()
        role = (await session.execute(
            select(Role).where(Role.tenant_id == tid, Role.key == "researcher")
        )).scalar_one()
        session.add(Membership(tenant_id=tid, user_id=user.id, role_id=role.id))
        await session.flush()
        other = user.id

    colleague = _client(tid, other)
    try:
        refused = await colleague.post("/api/v1/files", json=_intent(folder["id"]))
        assert refused.status_code == 403, refused.text
    finally:
        await colleague.aclose()


@requires_db
@pytest.mark.asyncio
async def test_a_folder_holding_a_pending_upload_is_not_deleted_from_under_it(
        clients, two_tenants):
    """**رفعٌ يجري لا يُسحب المجلَّد من تحته.**

    والصفّ يُكتب عند النيّة لا عند الختم، فيَعُدّه حارسُ «لا يُحذف مجلَّدٌ
    وفيه شيء». ولولا ذلك لأمكن أن يُحذف المجلَّد بينما الباحث يبثّ كتابه،
    فيُختم الرفع في مجلَّدٍ صار في السلّة — ملفٌّ حيّ في وعاءٍ محذوف، لا
    يظهر في أي شاشة.
    """
    a = clients["a"]
    shelf = await _make_folder(a, "رفٌّ فيه رفعٌ يجري")
    started = (await a.post("/api/v1/files", json=_intent(shelf["id"]))).json()

    refused = await a.post(f"/api/v1/files/folders/{shelf['id']}/trash")
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "library.folder_not_empty"
    assert refused.json()["error"]["context"]["files"] == "1"

    done = await a.post(f"/api/v1/files/{started['file_id']}/complete",
                        json={"checksum_sha256": "b" * 64})
    assert done.status_code == 200
    assert done.json()["folder_id"] == shelf["id"]


@requires_db
@pytest.mark.asyncio
async def test_the_last_word_at_complete_is_checked_exactly_like_the_first(
        clients, two_tenants):
    """الباحث غيّر وجهته بين النيّة والختم — **فيُفحص الثاني كما فُحص الأول**.

    و`null` صريحةٌ تعني الجذر، والغياب يُبقي. والثلاثة تُقاس هنا حالًا
    بحال، فلا يمرّ إلى القاعدة موضعٌ لم يُفحص.
    """
    a, b = clients["a"], clients["b"]
    first = await _make_folder(a, "الرفّ الأول")
    second = await _make_folder(a, "الرفّ الثاني")
    theirs = await _make_folder(b, "رفُّ مستأجرٍ آخر")

    started = (await a.post("/api/v1/files", json=_intent(first["id"]))).json()
    file_id = started["file_id"]

    stolen = await a.post(f"/api/v1/files/{file_id}/complete",
                          json={"checksum_sha256": "c" * 64, "folder_id": theirs["id"]})
    assert stolen.status_code == 404, stolen.text

    moved = await a.post(f"/api/v1/files/{file_id}/complete",
                         json={"checksum_sha256": "c" * 64, "folder_id": second["id"]})
    assert moved.status_code == 200, moved.text
    assert moved.json()["folder_id"] == second["id"]

    # و«إلى الجذر» تُقال بـ`null` صريحة — والغياب لا يقولها.
    to_root = await a.post(f"/api/v1/files/{file_id}/complete",
                           json={"checksum_sha256": "c" * 64, "folder_id": None})
    assert to_root.status_code == 200
    assert to_root.json()["folder_id"] is None


@requires_db
@pytest.mark.asyncio
async def test_both_doors_put_the_file_in_the_same_place(clients, two_tenants):
    """بابان، ومكتبةٌ واحدة، **وموضعٌ واحد**.

    والمقارنة هي المقصودة: ملفٌّ يرفعه الباحث من الشاشة وملفٌّ يرفعه عميلٌ
    موقّع، كلاهما من داخل المجلَّد نفسه — فيجب أن يُقرآ في القائمة نفسها.
    """
    import io

    a = clients["a"]
    shelf = await _make_folder(a, "رفُّ المقارنة")

    direct = await a.post(
        "/api/v1/files/upload",
        files={"upload": ("مباشر.pdf", io.BytesIO(b"%PDF-1.7\n" + b"x" * 400),
                          "application/pdf")},
        data={"classification": "C2", "folder_id": shelf["id"]})
    assert direct.status_code == 201, direct.text

    started = (await a.post("/api/v1/files", json=_intent(shelf["id"], "موقّع.pdf"))).json()
    assert (await a.post(f"/api/v1/files/{started['file_id']}/complete",
                         json={"checksum_sha256": "d" * 64})).status_code == 200

    inside = {row["id"] for row in (await a.get(f"/api/v1/files?folder={shelf['id']}")).json()}
    assert {direct.json()["id"], started["file_id"]} <= inside, (
        "بابا الرفع لم يضعا الملفين في المجلَّد نفسه")
