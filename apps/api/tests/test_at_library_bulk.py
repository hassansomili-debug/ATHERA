"""أفعالٌ على المختار | My Library V2.1 — bulk actions.

**من رفع ثلاثين ورقةً في الجذر لا ينظّمها بثلاثين ضغطة.** والمجلَّدات صارت
موجودة، لكنّ الطريق إليها بقي ملفًا ملفًا: افتح لوحته، اختر الوجهة، أكّد،
ثم أعِد ذلك تسعةً وعشرين مرّة. وذلك ليس بطئًا في الشاشة — هو أن التنظيم لا
يقع أصلًا.

وأربعةٌ تُثبَت هنا:

١) **ثلاثة أفعالٍ لا رابع: نقلٌ، وحذفٌ إلى سلّة، وربطٌ ببحث.** ولا إتلاف
   دائم — لا في مسارٍ ولا في أثرٍ جانبي — والإتلاف قرارٌ لم يُبنَ بعد.
٢) **الضمانُ لا يُستثنى منه الجماعيّ**: نقلُ عشرين ملفًا يغيّر
   `folder_id` في كل صفّ **ولا شيء غيره** — لا مفتاح تخزين، ولا رابط بحث،
   ولا اعتماد مرشّح، ولا سجلّ إسناد.
٣) **الدفعة كلها أو لا شيء منها**: ملفٌّ واحدٌ لا يملكه الباحث يردّ
   الجميع، ولا تبقى تسعةَ عشرَ منقولةً بلا أن يُقال.
٤) **الكلفة لا تنمو بالاختيار**: عدُّ ما يسنده المختار عبارةٌ واحدة مهما
   كثر، لا عبارةٌ لكل ملف.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import inspect
import re
import uuid

import pytest

from tests.conftest import requires_db

pytest_asyncio = pytest.importorskip("pytest_asyncio")


@pytest_asyncio.fixture
async def clients_free():
    """عميلٌ بلا اعتماد — لقياس **أيّ مسارٍ التقط الطلب**، لا ما يردّه.

    ولا يمسّ قاعدةً: المصادقة تردّ قبلها.
    """
    import httpx

    from athera_api.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as http:
        yield http


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ اختبارات خالصة: ما يُقرأ بلا قاعدة ═════════════════

def test_the_bulk_router_offers_three_actions_and_no_destruction():
    """**الإتلاف الدائم مؤجَّل — ولا يدخل من باب الأفعال الجماعية.**

    وذلك أسوأ مواضعه: قرارٌ لم تُحلّ شروطه (رسم التبعيات، وتحذيرٌ صادق،
    وأثرُ الروابط، وحفظ الإسناد، وتنظيف التخزين، وسلوكُ التعويض عند الفشل،
    والتدقيق) يقع على عشرين ملفًا بضغطةٍ واحدة. فيُقرأ الموجّه نصًّا.
    """
    from athera_api.routers import library_bulk

    paths = {route.path for route in library_bulk.router.routes}
    assert paths == {"/bulk/move", "/bulk/trash", "/bulk/link"}, (
        f"الموجّه الجماعيّ يعرض فعلًا غير الثلاثة: {sorted(paths)}")

    source = inspect.getsource(library_bulk)
    for forbidden in ("session.delete", "purge", "hard_delete", ".delete(key",
                      "storage.get_store"):
        assert forbidden not in source, (
            f"الموجّه الجماعيّ يذكر {forbidden!r} — والإتلاف قرارٌ ثانٍ مؤجَّل")


def test_moving_a_selection_writes_nothing_but_the_folder_of_each_row():
    """**الضمانُ نفسه، مضروبًا في عشرين.**

    وما يصدق على ملفٍ واحد يصدق على المختار كله؛ ولا يُستثنى الجماعيّ من
    ضمانٍ يقوم عليه المفرد — فالخطأ فيه يمسّ عشرين ملفًا لا واحدًا.
    """
    from athera_api.routers import library_bulk

    source = inspect.getsource(library_bulk.bulk_move).replace(
        library_bulk.bulk_move.__doc__, "")
    assigned = set(re.findall(r"record\.([a-z_]+)\s*=", source))
    assert assigned == {"folder_id"}, (
        f"النقل الجماعيّ يكتب حقولًا غير `folder_id`: {sorted(assigned)}")
    for forbidden in ("storage_key", "FactCandidate", "ProvenanceEvent",
                      "checksum", "trashed_at"):
        assert forbidden not in source, (
            f"النقل الجماعيّ يذكر {forbidden!r} — والمجلَّد تنظيمٌ لا حالُ دليل")


def test_the_bulk_paths_are_registered_before_the_id_shaped_ones():
    """`‎/files/bulk/move` يلتقطه `‎/files/{file_id}/move` لو سُجّل بعده.

    فيحاول الخادم قراءة «bulk» معرّفًا فيفشل، ويردّ 422 على فعلٍ صحيح —
    والترتيب هو كل الفرق، ولا يظهر في اختبار وحدةٍ يستدعي الدالّة مباشرةً.
    """
    from athera_api.main import app

    # وترتيبُ `openapi` هو ترتيب التسجيل نفسه — والإصدارات الحديثة من
    # FastAPI تؤجّل ضمَّ الموجّهات، فلا يُقرأ الترتيب من `app.routes`.
    paths = list(app.openapi()["paths"])
    order = {path: index for index, path in enumerate(paths)}
    assert order["/api/v1/files/bulk/move"] < order["/api/v1/files/{file_id}/move"], (
        "مسارُ المعرّف يسبق المسار الجماعيّ فيلتقط «bulk» معرّفًا")
    # وكذلك المجلَّدات، للسبب نفسه — والعلّة واحدة.
    assert order["/api/v1/files/folders"] < order["/api/v1/files/{file_id}"]


@pytest.mark.asyncio
async def test_the_bulk_paths_really_match_their_own_endpoint(clients_free):
    """**والترتيب يُقاس بالسلوك لا بالقائمة وحدها.**

    فلو التقط `‎/{file_id}/move` الطلبَ لفشل تحويل «bulk» إلى معرّف وردّ
    422. والردّ هنا 401 — أي أن الطلب بلغ المسار الجماعيّ ووقف عند
    المصادقة، وهو ما لا تقيسه قائمةُ مسارات. ولا قاعدةَ تُمسّ: الرفض قبلها.
    """
    for path in ("/api/v1/files/bulk/move", "/api/v1/files/bulk/trash",
                 "/api/v1/files/bulk/link"):
        response = await clients_free.post(path, json={"file_ids": []})
        assert response.status_code == 401, (
            f"{path} لم يبلغ مسارَه: {response.status_code} {response.text[:120]}")


def test_the_guards_are_the_same_definitions_the_single_actions_read():
    """حارسان لفعلٍ واحد يفترقان بأول تعديل — ويُنسى أخطرهما.

    فيُشدَّد المفرد ويبقى الجماعيّ يقبل ما لا يقبله، وهو الذي يمرّ على
    عشرين ملفًا.
    """
    from athera_api.routers import files, library_bulk

    assert "library.owned_file" in inspect.getsource(files._owned_file)
    assert "library.owned_file" in inspect.getsource(library_bulk._selection)
    assert "library.assert_writable" in inspect.getsource(files._writable_folder)
    assert "library.assert_writable" in inspect.getsource(library_bulk.bulk_move)


def test_a_selection_is_bounded_and_deduplicated_before_anything_is_written():
    """**دفعةٌ بلا سقف معاملةٌ لا يُعرف طولها**، تقفل صفوفًا وتُبطئ كل قارئ.

    والتكرار يُطرح: معرّفٌ مذكور مرّتين ليس ملفَّين، وعدُّه مرّتين يجعل
    «نُقل ٢١ ملفًا» رقمًا لا يطابق ما في المكتبة.
    """
    from athera_api.routers.library_bulk import MAX_BATCH, _selection

    source = inspect.getsource(_selection)
    assert "dict.fromkeys" in source, "التكرار لا يُطرح من الاختيار"
    assert "MAX_BATCH" in source, "الاختيار بلا سقف"
    assert MAX_BATCH <= 100, "سقفُ الدفعة أكبر من سقف صفحة القراءة"


def test_the_bulk_error_codes_all_have_translations_in_both_locales():
    """مفتاحٌ تقنيّ يصل الباحث ليس رسالة — واللغتان شرطٌ لا تحسين."""
    from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES
    from athera_api.routers import library_bulk

    codes = set(re.findall(r'(?:AtheraError|NotFound)\(\s*"([a-z_.]+)"',
                           inspect.getsource(library_bulk)))
    assert codes, "لم يُعثر على أي رمز خطأ في الموجّه الجماعيّ"
    for code in sorted(codes):
        assert code in CATALOG, f"رمز بلا ترجمة: {code}"
        for locale in SUPPORTED_LOCALES:
            assert CATALOG[code].get(locale), f"{code} ناقصٌ بلغة {locale}"


def test_the_outcome_is_counted_not_merely_confirmed():
    """**«تم» تُقرأ «وقع لعشرين».**

    فمن اختار عشرين وكان ثمانيةٌ منها مربوطًا من قبل يبحث عن أثرٍ لم يقع
    لثمانيةٍ ولا يجده. فيُقال بعدده: اخترتَ كذا، تغيّر كذا، وكان كذا كذلك.
    """
    from athera_api.schemas.library import BulkOutcome

    assert set(BulkOutcome.model_fields) == {
        "selected", "changed", "already", "project_links"}


# ══════════════════════ اختبارات تمسّ القاعدة ══════════════════════


@contextlib.contextmanager
def counting_statements():
    """يعدّ عبارات القاعدة الحقيقية — و`set_config` ليست منها."""
    from sqlalchemy.ext.asyncio import AsyncSession

    seen: list[str] = []
    original = AsyncSession.execute

    async def spy(self, statement, *args, **kwargs):
        rendered = str(statement)
        if "set_config" not in rendered:
            seen.append(rendered)
        return await original(self, statement, *args, **kwargs)

    AsyncSession.execute = spy
    try:
        yield seen
    finally:
        AsyncSession.execute = original


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


async def _seed_file(tenant_id: uuid.UUID, user_id: uuid.UUID, name: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.identity import ObjectGrant

    async with tenant_session(tenant_id, user_id) as session:
        row = File(tenant_id=tenant_id, storage_key=f"tenants/{tenant_id}/{uuid.uuid4()}",
                   original_filename=name, content_type="application/pdf",
                   size_bytes=2048, checksum_sha256="0" * 64, classification="C2",
                   status="stored", uploaded_by=user_id, completed_at=_now())
        session.add(row)
        await session.flush()
        session.add(ObjectGrant(tenant_id=tenant_id, object_type="file",
                                object_id=row.id, user_id=user_id,
                                grant_level="owner", granted_by=user_id))
        await session.flush()
        return row.id


async def _project(tenant_id: uuid.UUID, title: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tenant_id) as session:
        row = ResearchProject(tenant_id=tenant_id, working_title_ar=title,
                              status="planned", current_gate="G1")
        session.add(row)
        await session.flush()
        return row.id


async def _make_folder(http, name: str) -> dict:
    response = await http.post("/api/v1/files/folders", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


@requires_db
@pytest.mark.asyncio
async def test_a_selection_moves_together_and_keeps_every_key_and_link(
        clients, two_tenants):
    """**الاختبار الذي يقوم عليه الفعل الجماعيّ كله.**

    ملفاتٌ عليها: روابطُ بحثٍ قائمة، ومرشّحٌ اعتمده الباحث، وسجلّاتُ إسناد
    تذكر مفاتيح تخزينها. تُنقل دفعةً إلى مجلَّد ثم تعود إلى الجذر —
    ويُقارَن كلُّ ذلك قبلَ النقل وبعده **قيمةً بقيمة**.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.audit import ProvenanceEvent
    from athera_api.models.files import File
    from athera_api.models.portfolio import ProjectFile
    from athera_api.models.research import DocumentChunk, ExtractionRun, FactCandidate
    from athera_api.models.thesis import Thesis

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    made = [await _seed_file(tid, uid, f"ورقة {index}.pdf") for index in range(4)]
    project = await _project(tid, "بحثٌ يعتمد على الملفات")

    async with tenant_session(tid, uid) as session:
        for file_id in made:
            session.add(ProjectFile(tenant_id=tid, project_id=project, file_id=file_id,
                                    state=ProjectFile.ACTIVE, added_by=uid))
            session.add(Thesis(tenant_id=tid, file_id=file_id, title_ar="رسالة"))
            run = ExtractionRun(tenant_id=tid, file_id=file_id, extractor="rules",
                                status="completed", started_at=_now())
            session.add(run)
            await session.flush()
            chunk = DocumentChunk(tenant_id=tid, file_id=file_id, seq=1,
                                  text="نصٌّ مقتبس", locator="p.1 ¶1", page_number=1,
                                  paragraph_index=1, char_count=11)
            session.add(chunk)
            await session.flush()
            session.add(FactCandidate(
                tenant_id=tid, extraction_run_id=run.id, file_id=file_id,
                chunk_id=chunk.id, memory_category="researcher_fact",
                field_key="sample", statement_ar="عبارة", quote="نصٌّ مقتبس",
                locator=chunk.locator, confidence=0.9, status="approved",
                decided_by=uid, decided_at=_now()))
            stored = (await session.execute(
                select(File).where(File.id == file_id))).scalar_one()
            session.add(ProvenanceEvent(
                tenant_id=tid, object_type="file", object_id=file_id,
                source_type="upload", source_id=file_id,
                source_locator=stored.storage_key, created_by=uid,
                verification_status="unverified"))
        await session.flush()

    async def snapshot() -> dict:
        async with tenant_session(tid, uid) as session:
            out = {}
            for file_id in made:
                row = (await session.execute(
                    select(File).where(File.id == file_id))).scalar_one()
                link = (await session.execute(select(ProjectFile).where(
                    ProjectFile.file_id == file_id))).scalar_one()
                candidate = (await session.execute(select(FactCandidate).where(
                    FactCandidate.file_id == file_id))).scalar_one()
                event = (await session.execute(select(ProvenanceEvent).where(
                    ProvenanceEvent.object_id == file_id))).scalar_one()
                out[file_id] = {
                    "storage_key": row.storage_key, "checksum": row.checksum_sha256,
                    "status": row.status, "trashed_at": row.trashed_at,
                    "link_state": link.state, "link_project": link.project_id,
                    "candidate_status": candidate.status,
                    "candidate_decided_by": candidate.decided_by,
                    "provenance_locator": event.source_locator,
                }
            return out

    before = await snapshot()
    shelf = await _make_folder(a, "رفُّ الدفعة")

    for target in (shelf["id"], None):
        moved = await a.post("/api/v1/files/bulk/move",
                             json={"file_ids": [str(f) for f in made],
                                   "folder_id": target})
        assert moved.status_code == 200, moved.text
        assert moved.json()["selected"] == len(made)
        assert moved.json()["changed"] == len(made)
        assert before == await snapshot(), (
            "النقل الجماعيّ غيّر شيئًا غير المجلَّد — والمجلَّد تنظيمٌ لا حالُ دليل")

    # وموضعُ كل ملفٍ تغيّر فعلًا: الضمانُ ليس «لم يقع شيء».
    inside = await a.post("/api/v1/files/bulk/move",
                          json={"file_ids": [str(f) for f in made],
                                "folder_id": shelf["id"]})
    assert inside.status_code == 200
    listed = {row["id"] for row in
              (await a.get(f"/api/v1/files?folder={shelf['id']}&limit=100")).json()}
    assert listed == {str(f) for f in made}


@requires_db
@pytest.mark.asyncio
async def test_one_file_that_is_not_yours_refuses_the_whole_batch(clients, two_tenants):
    """**النجاح الجزئيّ أسوأ الخيارين.**

    سبعةَ عشرَ ملفًّا انتقلت وثلاثةٌ لم تنتقل، ولا شيء في الشاشة يقول
    أيُّها — فيبحث الباحث عن ملفاته في رفَّين ويظنّ ما وجده كلَّ ما اختاره.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.files import File

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    theirs = await _seed_file(two_tenants["b"]["tenant_id"],
                              two_tenants["b"]["user_id"], "ملفُّ الآخر.pdf")
    mine = [await _seed_file(tid, uid, f"ملفّي {index}.pdf") for index in range(3)]
    shelf = await _make_folder(a, "رفٌّ لن يمتلئ")

    refused = await a.post(
        "/api/v1/files/bulk/move",
        json={"file_ids": [str(f) for f in mine] + [str(theirs)],
              "folder_id": shelf["id"]})
    assert refused.status_code == 404, refused.text

    # **ولم ينتقل واحدٌ منها**: المعاملة رُدّت كلها.
    async with tenant_session(tid, uid) as session:
        rows = (await session.execute(
            select(File.folder_id).where(File.id.in_(mine)))).scalars().all()
    assert all(folder is None for folder in rows), (
        "بعضُ الدفعة انتقل رغم رفضها — والنجاح الجزئيّ لا يُقال للباحث")


@requires_db
@pytest.mark.asyncio
async def test_deleting_a_selection_warns_with_a_number_and_destroys_nothing(
        clients, two_tenants):
    """التحذير الجماعيّ أخطر من المفرد: ضغطةٌ واحدة تُخفي عشرين ملفًا.

    فيُقال عددُ ما يسنده المختار **قبل** أن يقع، والحذفُ نقلٌ إلى سلّة:
    الروابط باقية، والاستعادة ترجع كلَّ ملفٍ إلى موضعه.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    made = [await _seed_file(tid, uid, f"يسند بحثًا {index}.pdf") for index in range(3)]
    project = await _project(tid, "بحثٌ قائم")
    async with tenant_session(tid, uid) as session:
        for file_id in made[:2]:
            session.add(ProjectFile(tenant_id=tid, project_id=project, file_id=file_id,
                                    state=ProjectFile.ACTIVE, added_by=uid))
        await session.flush()

    body = {"file_ids": [str(f) for f in made]}
    refused = await a.post("/api/v1/files/bulk/trash", json=body)
    assert refused.status_code == 409, refused.text
    error = refused.json()["error"]
    assert error["code"] == "library.selection_linked_to_projects"
    assert error["context"]["projects"] == "2"
    assert error["context"]["files"] == "3"

    done = await a.post("/api/v1/files/bulk/trash", json={**body, "confirm": True})
    assert done.status_code == 200, done.text
    assert done.json() == {"selected": 3, "changed": 3, "already": 0, "project_links": 2}

    # الروابط باقية بعد الحذف — الحذف إخفاءٌ لا قطعُ سند.
    async with tenant_session(tid, uid) as session:
        links = (await session.execute(select(ProjectFile).where(
            ProjectFile.file_id.in_(made)))).scalars().all()
    assert len(links) == 2
    assert all(link.state == ProjectFile.ACTIVE for link in links)

    in_trash = {row["id"] for row in (await a.get("/api/v1/files?trash=true")).json()}
    assert {str(f) for f in made} <= in_trash
    for file_id in made:
        assert (await a.post(f"/api/v1/files/{file_id}/restore")).status_code == 200


@requires_db
@pytest.mark.asyncio
async def test_linking_a_selection_counts_what_was_already_linked(clients, two_tenants):
    """«رُبط عشرون» وفيها ثمانيةٌ لم يقع لها شيء رقمٌ لا يصدق.

    والربط لا ينقل ملفًّا من رفّه: بحثٌ يستعمل ملفًّا لا يغيّر موضعه في
    مكتبة صاحبه.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.portfolio import ProjectFile

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    made = [await _seed_file(tid, uid, f"مرجع {index}.pdf") for index in range(4)]
    project = await _project(tid, "بحثٌ يُربط به")
    shelf = await _make_folder(a, "رفُّ المراجع")
    assert (await a.post("/api/v1/files/bulk/move",
                         json={"file_ids": [str(f) for f in made],
                               "folder_id": shelf["id"]})).status_code == 200

    body = {"file_ids": [str(f) for f in made], "project_id": str(project)}
    first = await a.post("/api/v1/files/bulk/link", json=body)
    assert first.status_code == 200, first.text
    assert first.json()["changed"] == 4 and first.json()["already"] == 0

    # ثانيةً: لا شيء يقع، ويُقال ذلك بعدده — ولا صفَّ ربطٍ مكرَّر.
    again = await a.post("/api/v1/files/bulk/link", json=body)
    assert again.status_code == 200
    assert again.json()["changed"] == 0 and again.json()["already"] == 4

    async with tenant_session(tid, uid) as session:
        links = (await session.execute(select(ProjectFile).where(
            ProjectFile.project_id == project))).scalars().all()
        assert len(links) == 4, "الربط الثاني أنشأ صفوفًا مكرَّرة"
        placed = (await session.execute(select(File.folder_id).where(
            File.id.in_(made)))).scalars().all()
    assert all(folder == uuid.UUID(shelf["id"]) for folder in placed), (
        "الربط ببحثٍ نقل الملفات من رفّها")


@requires_db
@pytest.mark.asyncio
async def test_an_empty_or_oversized_selection_is_refused_by_its_own_name(clients):
    """رفضٌ يقول ما وقع — لا «حدث خطأ غير متوقع»."""
    a = clients["a"]
    empty = await a.post("/api/v1/files/bulk/move",
                         json={"file_ids": [], "folder_id": None})
    assert empty.status_code == 422, empty.text

    too_many = await a.post(
        "/api/v1/files/bulk/move",
        json={"file_ids": [str(uuid.uuid4()) for _ in range(101)], "folder_id": None})
    assert too_many.status_code == 422
    assert too_many.json()["error"]["code"] == "library.selection_too_large"


@requires_db
@pytest.mark.asyncio
async def test_the_warning_costs_one_statement_however_many_are_selected(
        clients, two_tenants):
    """عدُّ ما يسنده المختار عبارةٌ واحدة، لا عبارةٌ لكل ملف.

    وعدُّ كلٍّ على حدة يُعيد `1 + N` في فعلٍ يُفترض أنه وفّرها — وهو العطب
    الذي عولج في صفحة المكتبة، يُعاد من بابٍ جديد.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    few = [await _seed_file(tid, uid, f"قليل {index}.pdf") for index in range(2)]
    many = [await _seed_file(tid, uid, f"كثير {index}.pdf") for index in range(12)]
    shelf = await _make_folder(a, "رفُّ القياس")

    with counting_statements() as small:
        assert (await a.post("/api/v1/files/bulk/move",
                             json={"file_ids": [str(f) for f in few],
                                   "folder_id": shelf["id"]})).status_code == 200
    with counting_statements() as large:
        assert (await a.post("/api/v1/files/bulk/move",
                             json={"file_ids": [str(f) for f in many],
                                   "folder_id": shelf["id"]})).status_code == 200

    # الفحصُ لكل ملفٍ حقٌّ لا يُتنازل عنه — لكن نموّه يجب أن يكون خطّيًّا
    # في الفحص وحده، لا في الوجهة ولا في عدّ ما يسنده المختار.
    per_file = (len(large) - len(small)) / (len(many) - len(few))
    assert per_file <= 2.0, (
        f"كل ملفٍ في الدفعة كلّف {per_file:.1f} عبارة — والفحص وحده يكفيه")
