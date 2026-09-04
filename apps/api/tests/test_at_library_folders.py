"""مجلدات المكتبة | My Library V2 — folders.

يثبت هذا الملف خمسة أشياء لا تُشحن الميزة بدونها:

١) **العزل مفروض على الجدول الجديد**: مستأجرٌ لا يرى مجلَّد غيره ولا ينشئ
   تحته ولا ينقل إليه ولا يعيد تسميته ولا يحذفه ولا يستعيده — والمنع من
   القاعدة لا من الواجهة.
٢) **المنحة تحرس داخل المستأجر الواحد**: من يرى المجلَّد لا يملك تغييره
   بلا منحة عليه.
٣) **الدورة مرفوضة**: مجلَّدٌ تحت نفسه أو تحت واحدٍ من ذرّيته يُردّ 409،
   والشجرة تبقى كما كانت.
٤) **النقلُ تنظيمٌ لا حالُ دليل**: ملفٌّ بمرشّحٍ معتمَد ورابطِ بحثٍ وسجلّ
   إسنادٍ يعبر مجلَّدين ويحتفظ بكلّ ذلك — ومفتاحُ تخزينه لا يتغيّر حرفًا.
٥) **الكلفة لا تنمو**: قائمةُ مجلَّدٍ عبارتان أو ثلاث مهما بلغ عدد
   المجلَّدات، وصفحةُ الملفات عبارةٌ واحدة كما كانت قبل المجلَّدات.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db
from tests.tsscan import code_lines

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0022_library_folders.py")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ اختبارات خالصة: ما يُقرأ بلا قاعدة ═════════════════

def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته.

    والفرق ليس نظريًّا: من يفتح الاتصال بدور المالك يقرأ كل المستأجرين
    وسياسةٌ معلَنة قائمة. فـ`FORCE` هي ما يجعل العزل خاصية قاعدة لا
    خاصية دورٍ صادف أنه المستعمل — وهي قاعدة ADR-0002، لا استثناء
    لجدولٍ «تنظيميّ».
    """
    text = MIGRATION.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text


def test_the_migration_indexes_the_reads_the_screens_actually_make():
    """فهرسٌ للقراءة المعروضة، لا فهارس على التخمين.

    الشاشة تقرأ أبناء مجلَّدٍ بعينه، وصفحةَ ملفاتٍ داخل مجلَّد مرتَّبةً
    بالترقيم المفتاحيّ. فهذان يُفهرسان — وغيابهما يجعل كل فتح مجلَّدٍ مسحًا
    كاملًا للجدول، وهو بالضبط العطب الذي عولج في `GET /files`.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'ix_library_folders_parent' in text
    assert '"tenant_id", "parent_folder_id", "trashed_at"' in text
    assert 'ix_files_folder_page' in text
    assert '"tenant_id", "folder_id", "created_at", "id"' in text


def test_the_migration_has_a_real_downgrade_that_refuses_to_resurrect_the_trash():
    """تنازلٌ يمحو `trashed_at` يُعيد كل محذوفٍ حيًّا بلا أن يُقال لصاحبه.

    وهو العيب نفسه الذي منعه الترحيل 0020 في بحوث السلّة. فالتنازل حقيقيّ
    — يُسقط الأعمدة والجدول فعلًا — ويرفض ما دام في السلّة شيءٌ ينتظر
    قرارًا.
    """
    text = MIGRATION.read_text(encoding="utf-8")
    assert "def downgrade()" in text
    assert "downgrade refused" in text
    assert "trashed_at IS NOT NULL" in text
    assert 'op.drop_table("library_folders")' in text
    for column in ("trashed_by", "trashed_at", "folder_id"):
        assert f'"{column}"' in text


def test_the_model_and_the_migration_agree_column_by_column():
    """عمودٌ في النموذج لا يقابله عمودٌ في الترحيل يسقط في الإنتاج وحده.

    وهو الخطأ المتكرر في هذا المستودع: مفردةٌ تُكتب بجانب سجلّها بدل أن
    تُشتقّ منه.
    """
    from athera_api.models.library import LibraryFolder

    text = MIGRATION.read_text(encoding="utf-8")
    for column in LibraryFolder.__table__.columns:
        assert f'"{column.name}"' in text, (
            f"العمود {column.name!r} في النموذج ولا وجود له في الترحيل 0022")


def test_the_folder_error_codes_all_have_translations_in_both_locales():
    """مفتاحٌ تقنيّ يصل الباحث ليس رسالة — واللغتان شرطٌ لا تحسين."""
    import inspect

    from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES
    from athera_api.routers import files as files_router
    from athera_api.routers import folders as folders_router
    from athera_api.services import library as library_service

    # **ما يُرمى وحده، لا كل ما كُتب.** أفعالُ التدقيق تحمل البادئة نفسها
    # (`library.file_moved`)، وهي ليست رسائل تُعرض — وحارسٌ يعاقب عليها
    # يُعطَّل ثم لا يحرس شيئًا.
    referenced: set[str] = set()
    for module in (folders_router, files_router, library_service):
        referenced |= set(re.findall(
            r'(?:AtheraError|NotFound)\(\s*"(library\.[a-z_]+)"',
            inspect.getsource(module)))
    assert referenced, "لم يُعثر على أي رمز خطأ للمجلَّدات لفحصه"
    for code in sorted(referenced):
        assert code in CATALOG, f"رمز بلا ترجمة: {code}"
        for locale in SUPPORTED_LOCALES:
            assert CATALOG[code].get(locale), f"{code} ناقصٌ بلغة {locale}"


def test_moving_a_file_writes_nothing_but_its_folder():
    """**الحارس الذي يمنع أسوأ ما قد يقع.**

    نقلُ ملفٍّ بين مجلَّدين تنظيم. فلو كتب المسار — اليوم أو بعد سنة — في
    رابط بحثٍ أو حال مرشّحٍ أو مفتاح تخزين، لفقد الباحث سند ورقته لأنه
    رتّب مكتبته. والمسار يُقرأ نصًّا: لا إسناد إلا إلى `folder_id`.
    """
    import inspect

    from athera_api.routers import files as router

    # **الشرح يُنزع قبل الفحص.** التوثيق هنا يذكر بالاسم ما لا يُمسّ —
    # ومعاقبته على ذلك هي بعينها العلّة التي أسقطت حارسَين من قبل.
    source = inspect.getsource(router.move_file).replace(router.move_file.__doc__, "")
    assigned = set(re.findall(r"record\.([a-z_]+)\s*=", source))
    assert assigned == {"folder_id"}, (
        f"نقلُ الملف يكتب حقولًا غير `folder_id`: {sorted(assigned - {'folder_id'})}")
    for forbidden in ("storage_key", "ProjectFile", "FactCandidate", "ProvenanceEvent",
                      "use_state", "delete"):
        assert forbidden not in source, (
            f"مسار النقل يذكر {forbidden!r} — والنقل تنظيمٌ لا حالُ دليل")


def test_the_cycle_check_is_locked_before_it_is_checked():
    """الفحصُ ثم الكتابة بلا قفلٍ يمرّ عليه نقلان متزامنان فيصنعان حلقة.

    والحلقة تقطع فرعًا كاملًا عن الجذر: ملفاتٌ سليمة في القاعدة لا تظهر
    في أي شاشة. فيُقرأ ترتيب المسار نصًّا — القفل أولًا.
    """
    import inspect

    from athera_api.routers import folders as router

    source = inspect.getsource(router.move_folder)
    assert source.index("lock_tree") < source.index("assert_placement")
    assert source.index("assert_placement") < source.index("parent_folder_id =")


def test_no_listing_walks_down_the_tree():
    """تحميلُ الذرّية في قائمة يعيد عطب «المكتبة ما تتحمل كتب» من بابٍ آخر.

    والنزول الوحيد المسموح هو قياسُ ارتفاع الشجرة عند **النقل** — فعلٌ
    مفرد على ضغطة زرّ، لا قراءةٌ تُعرض.
    """
    import inspect

    from athera_api.routers import folders as router
    from athera_api.services import library as service

    for endpoint in (router.list_folders, router.list_all_folders):
        source = inspect.getsource(endpoint)
        assert "subtree_height" not in source, "قائمةٌ تنزل في الشجرة"
    # والنزول موضعه واحد: فحصُ العمق في `assert_placement`، ولا يُستدعى
    # إلا من مسار النقل.
    assert "subtree_height" in inspect.getsource(service.assert_placement)
    assert "assert_placement" in inspect.getsource(router.move_folder)


def test_the_files_page_still_costs_one_statement_shaped_query():
    """المجلَّد شرطٌ في العبارة، لا مرشِّحٌ بعدها ولا استعلامٌ ثانٍ.

    وأيّ صياغةٍ تقرأ المجلَّد أولًا ثم الملفات ثانيًا تُضيف رحلةً عبر
    البحر لكل فتح مجلَّد — وهو الثمن نفسه الذي دُفع مرّة وعولج.
    """
    import inspect

    from athera_api.routers import files as router

    source = inspect.getsource(router.list_files)
    assert "File.folder_id ==" in source
    assert "File.folder_id.is_(None)" in source
    assert source.count("await session.execute") == 1


def test_the_absent_folder_parameter_still_means_every_file():
    """قوائمُ الاختيار في شاشاتٍ أخرى تقرأ المكتبة بلا `folder`.

    ولو دلّ الغياب على الجذر لاختفت من تلك القوائم كلُّ ورقةٍ نظّمها
    الباحث في مجلَّد — نقصٌ صامت أسوأ من بطء.
    """
    from athera_api.routers.files import ROOT, _folder_scope

    assert _folder_scope(None) == (False, None)
    assert _folder_scope(ROOT) == (True, None)
    known = uuid.uuid4()
    assert _folder_scope(str(known)) == (True, known)


# ═════════════════ الواجهة: لا زرّ بلا اسم، ولا نصّ بلا لغتين ═════════════

def _messages(locale: str) -> dict:
    return json.loads((WEB / "messages" / f"{locale}.json").read_text(encoding="utf-8"))


def test_every_library_string_exists_in_both_languages():
    """العربية لغة المنتج، والإنجليزية ثانيتها — ونقصُ إحداهما نصٌّ مفقود."""
    ar, en = _messages("ar")["library"], _messages("en")["library"]

    def flat(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flat(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    assert set(flat(ar)) == set(flat(en)), (
        "مفاتيح المكتبة تفترق بين اللغتين: "
        f"{sorted(set(flat(ar)) ^ set(flat(en)))}")


def test_the_library_page_names_the_target_of_every_control():
    """**زرٌّ بلا اسمٍ يذكر هدفه لا يُستعمل بقارئ شاشة.**

    «نقل» في صفٍّ فيه عشرون ملفًا لا يقول أيّ ملف. فكل تسمية تحمل اسم
    الملف أو المجلَّد الذي تعمل عليه — والفحص يقرأ الشيفرة بلا تعليقاتها،
    فلا يُخدع بشرحٍ صادق.
    """
    page = (WEB / "src" / "app" / "[locale]" / "library" / "page.tsx")
    source = "\n".join(line for _n, line in code_lines(page.read_text(encoding="utf-8")))

    # كل تسمية للمجلَّدات والملفات تُركَّب من ترجمةٍ **واسمِ هدفها**.
    labels = re.findall(r"aria-label=\{`([^`]+)`\}", source)
    assert labels, "لا توجد تسميات وصفية في صفحة المكتبة"
    unnamed = [label for label in labels
               if ": ${" not in label and "${" not in label.split("}")[-1]]
    assert not unnamed, f"تسمياتٌ لا تذكر هدفها: {unnamed}"


def test_the_library_page_renders_no_control_without_a_route_behind_it():
    """**لا زرّ يفعل لا شيء.** وكل فعلٍ معروض له مسارٌ في الخادم.

    وعدٌ لا يُنجَز أسوأ من غياب الزرّ: الباحث يضغط، فلا يقع شيء، ولا رسالة.
    """
    page = (WEB / "src" / "app" / "[locale]" / "library" / "page.tsx")
    source = "\n".join(line for _n, line in code_lines(page.read_text(encoding="utf-8")))
    lib = (WEB / "src" / "lib" / "library.ts").read_text(encoding="utf-8")

    from athera_api.main import app

    known = set(app.openapi()["paths"])
    used = set(re.findall(r'"(/api/v1/[a-z0-9/_-]+)', source + lib))
    for path in used:
        # المسارات المعلَّمة تُطابق بقالبها لا بحرفها.
        if path in known:
            continue
        assert any(path.startswith(prefix.split("{")[0]) for prefix in known), (
            f"الشاشة تنادي مسارًا لا وجود له في الخادم: {path}")


# ══════════════════════ اختبارات تمسّ القاعدة ══════════════════════

pytest_asyncio = pytest.importorskip("pytest_asyncio")


@contextlib.contextmanager
def counting_statements():
    """يعدّ عبارات القاعدة الحقيقية — و`set_config` ليست منها.

    ضبطُ سياق المستأجر عبارتان في كل جلسة مهما كان المسار؛ عدُّهما يخلط
    ثمنًا ثابتًا بثمنٍ ينمو، وما يُقاس هنا هو الثاني.
    """
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


async def _second_user(tenant_id: uuid.UUID) -> uuid.UUID:
    """باحثٌ ثانٍ **في المستأجر نفسه** — فالعزل لا يفصل بينه وبين الأول.

    وهنا يُقاس ما لا تقيسه RLS: من يرى المجلَّد هل يملك تغييره؟
    """
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    async with system_session() as session:
        user = User(email=f"second-{uuid.uuid4().hex[:8]}@example.test",
                    password_hash=hash_password("correct-horse-battery-staple"),
                    full_name_ar="باحثٌ ثانٍ", full_name_en="Second researcher")
        session.add(user)
        await session.flush()
        role = (await session.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.key == "researcher")
        )).scalar_one()
        session.add(Membership(tenant_id=tenant_id, user_id=user.id, role_id=role.id))
        await session.flush()
        return user.id


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
    """ملفٌّ بمنحة ملكيةٍ عليه — كما ينشئه الرفع الحقيقي، لا صفًّا يتيمًا."""
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


async def _make_folder(http, name: str, parent: str | None = None) -> dict:
    response = await http.post("/api/v1/files/folders",
                               json={"name": name, "parent_folder_id": parent})
    assert response.status_code == 201, response.text
    return response.json()


# ── ١. العزل: مستأجرٌ لا يمسّ مجلَّد غيره بأي فعل ──

@requires_db
@pytest.mark.asyncio
async def test_the_other_tenant_can_do_nothing_at_all_to_this_folder(clients, two_tenants):
    """**ستّة أفعالٍ تُجرَّب واحدًا واحدًا، لا فعلٌ واحد يُقاس عليه البقية.**

    فحارسٌ يُفحص في مسارٍ ويُنسى في خمسة ليس حارسًا. والقراءة أولها: ما لا
    يُرى لا يُنقل إليه ولا يُعاد تسميته.
    """
    a, b = clients["a"], clients["b"]
    folder = await _make_folder(a, "كتب المنهج")
    mine = await _make_folder(b, "مجلَّد المستأجر الآخر")

    listing = (await b.get("/api/v1/files/folders")).json()
    assert all(row["id"] != folder["id"] for row in listing["folders"]), (
        "مجلَّد مستأجرٍ ظهر في قائمة مستأجرٍ آخر")
    assert (await b.get(f"/api/v1/files/folders?parent={folder['id']}")).status_code == 404

    # إنشاءٌ تحته، وإعادة تسمية، ونقلٌ إليه، ونقلُ مجلَّده هو إليه، وحذف،
    # واستعادة — كلها تُردّ، ولا يُفرَّق في الرسالة بين «غير موجود»
    # و«لغيرك»: التخمين لا يعطي خبرًا.
    attempts = [
        await b.post("/api/v1/files/folders",
                     json={"name": "اقتحام", "parent_folder_id": folder["id"]}),
        await b.patch(f"/api/v1/files/folders/{folder['id']}", json={"name": "اسمي أنا"}),
        await b.post(f"/api/v1/files/folders/{mine['id']}/move",
                     json={"parent_folder_id": folder["id"]}),
        await b.post(f"/api/v1/files/folders/{folder['id']}/move",
                     json={"parent_folder_id": None}),
        await b.post(f"/api/v1/files/folders/{folder['id']}/trash"),
        await b.post(f"/api/v1/files/folders/{folder['id']}/restore"),
    ]
    assert all(response.status_code in (403, 404) for response in attempts), (
        [(r.request.url.path, r.status_code) for r in attempts])

    # وبعد كل ذلك: المجلَّد كما كان، اسمًا وموضعًا وحالًا.
    after = (await a.get("/api/v1/files/folders")).json()["folders"]
    still = next(row for row in after if row["id"] == folder["id"])
    assert still["name"] == "كتب المنهج"
    assert still["parent_folder_id"] is None and still["trashed_at"] is None


@requires_db
@pytest.mark.asyncio
async def test_the_other_tenant_cannot_see_the_folder_row_even_in_the_database(
        clients, two_tenants):
    """العزل يُقاس تحت الـAPI أيضًا: السياسة تمنع الصفّ لا الموجّه وحده."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.library import LibraryFolder

    a, b = clients["a"], two_tenants["b"]
    folder = await _make_folder(a, "مجلَّدٌ سرّي")

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        leaked = (await session.execute(select(LibraryFolder).where(
            LibraryFolder.id == uuid.UUID(folder["id"])))).scalars().all()
        assert leaked == [], "صفّ مجلَّدٍ ظهر لمستأجرٍ آخر رغم RLS"


@requires_db
@pytest.mark.asyncio
async def test_a_colleague_in_the_same_tenant_cannot_change_a_folder_he_can_see(
        clients, two_tenants):
    """**العزل لا يفصل داخل المستأجر — والمنحة هي التي تفصل.**

    وباحثان في مساحةٍ واحدة يريان المكتبة نفسها؛ فالسؤال ليس «أيرى؟» بل
    «أيملك أن يغيّر؟». والجواب: لا، إلا بمنحةٍ على الكائن — وهي طبقة §28
    نفسها التي تحرس الملفات.
    """
    a = clients["a"]
    folder = await _make_folder(a, "مجلَّد صاحب المكتبة")
    other = await _second_user(two_tenants["a"]["tenant_id"])
    colleague = _client(two_tenants["a"]["tenant_id"], other)
    try:
        attempts = [
            await colleague.patch(f"/api/v1/files/folders/{folder['id']}",
                                  json={"name": "غيّرتُه"}),
            await colleague.post(f"/api/v1/files/folders/{folder['id']}/move",
                                 json={"parent_folder_id": None}),
            await colleague.post(f"/api/v1/files/folders/{folder['id']}/trash"),
            await colleague.post(f"/api/v1/files/folders/{folder['id']}/restore"),
            await colleague.post("/api/v1/files/folders",
                                 json={"name": "تحت مجلَّدك",
                                       "parent_folder_id": folder["id"]}),
        ]
        assert all(response.status_code == 403 for response in attempts), (
            [(r.request.url.path, r.status_code) for r in attempts])
    finally:
        await colleague.aclose()


# ── ٢. الدورة: مجلَّدٌ لا يبتلع نفسه ──

@requires_db
@pytest.mark.asyncio
async def test_a_folder_cannot_move_into_itself_or_into_its_own_descendant(clients):
    """الحلقةُ تقطع فرعًا عن الجذر فتختفي ملفاتُه من كل شاشة وهي سليمة.

    فتُرفض بـ409 مفهومة، **ولا تتغيّر الشجرة**: الرفض قبل الكتابة لا بعدها.
    """
    a = clients["a"]
    root = await _make_folder(a, "مكتبة المنهج")
    child = await _make_folder(a, "الكمي", parent=root["id"])
    grandchild = await _make_folder(a, "الانحدار", parent=child["id"])

    into_self = await a.post(f"/api/v1/files/folders/{root['id']}/move",
                             json={"parent_folder_id": root["id"]})
    into_child = await a.post(f"/api/v1/files/folders/{root['id']}/move",
                              json={"parent_folder_id": child["id"]})
    into_grandchild = await a.post(f"/api/v1/files/folders/{root['id']}/move",
                                   json={"parent_folder_id": grandchild["id"]})
    for response in (into_self, into_child, into_grandchild):
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "library.folder_cycle"

    listing = (await a.get(f"/api/v1/files/folders?parent={child['id']}")).json()
    assert [row["id"] for row in listing["folders"]] == [grandchild["id"]]
    assert [crumb["name"] for crumb in listing["breadcrumb"]] == ["مكتبة المنهج", "الكمي"]


@requires_db
@pytest.mark.asyncio
async def test_a_legitimate_move_keeps_the_breadcrumb_true(clients):
    """النقلُ المشروع يقع، وفتاتُ الطريق يقول الموضع الجديد لا القديم."""
    a = clients["a"]
    books = await _make_folder(a, "كتب المنهج")
    quantitative = await _make_folder(a, "المنهج الكمي")

    moved = await a.post(f"/api/v1/files/folders/{quantitative['id']}/move",
                         json={"parent_folder_id": books["id"]})
    assert moved.status_code == 200, moved.text

    listing = (await a.get(f"/api/v1/files/folders?parent={quantitative['id']}")).json()
    assert [crumb["name"] for crumb in listing["breadcrumb"]] == [
        "كتب المنهج", "المنهج الكمي"]

    # ثم يعود إلى الجذر: `null` قيمةٌ مقصودة لا حقلٌ منسيّ.
    back = await a.post(f"/api/v1/files/folders/{quantitative['id']}/move",
                        json={"parent_folder_id": None})
    assert back.status_code == 200
    assert back.json()["parent_folder_id"] is None


# ── ٣. الملف: نقلٌ لا يمسّ دليلًا ──

@requires_db
@pytest.mark.asyncio
async def test_moving_a_file_preserves_its_project_link_and_its_approved_evidence(
        clients, two_tenants):
    """**الاختبار الذي تقوم عليه الميزة كلها.**

    ملفٌّ عليه: رابطُ بحثٍ قائم، ومرشّحٌ اعتمده الباحث بفاعلٍ وتاريخ، وسجلّ
    إسنادٍ يذكر مفتاح تخزينه. يُنقل إلى مجلَّد ثم إلى مجلَّدٍ ثانٍ ثم يعود
    إلى الجذر — ويُقارَن كلُّ ذلك قبلَ النقل وبعده **قيمةً بقيمة**.

    فإن نقص شيء فقد الباحث سند ورقته لأنه رتّب مكتبته، وذلك أسوأ ما قد
    تفعله ميزةُ تنظيم.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.audit import ProvenanceEvent
    from athera_api.models.files import File
    from athera_api.models.portfolio import ProjectFile, ResearchProject
    from athera_api.models.research import DocumentChunk, ExtractionRun, FactCandidate
    from athera_api.models.thesis import Thesis

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    file_id = await _seed_file(tid, uid, "أثر البرنامج في التفكير الناقد.pdf")

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="بحثٌ يعتمد على الملف",
                                  status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        session.add(ProjectFile(tenant_id=tid, project_id=project.id, file_id=file_id,
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
            tenant_id=tid, extraction_run_id=run.id, file_id=file_id, chunk_id=chunk.id,
            memory_category="researcher_fact", field_key="sample", statement_ar="عبارة",
            quote="نصٌّ مقتبس", locator=chunk.locator, confidence=0.9,
            status="approved", decided_by=uid, decided_at=_now()))
        stored = (await session.execute(
            select(File).where(File.id == file_id))).scalar_one()
        session.add(ProvenanceEvent(
            tenant_id=tid, object_type="file", object_id=file_id, source_type="upload",
            source_id=file_id, source_locator=stored.storage_key, created_by=uid,
            verification_status="unverified"))
        await session.flush()
        before_key = stored.storage_key

    async def snapshot() -> dict:
        async with tenant_session(tid, uid) as session:
            row = (await session.execute(
                select(File).where(File.id == file_id))).scalar_one()
            link = (await session.execute(select(ProjectFile).where(
                ProjectFile.file_id == file_id))).scalar_one()
            candidate = (await session.execute(select(FactCandidate).where(
                FactCandidate.file_id == file_id))).scalar_one()
            event = (await session.execute(select(ProvenanceEvent).where(
                ProvenanceEvent.object_id == file_id))).scalar_one()
            return {
                "storage_key": row.storage_key,
                "checksum": row.checksum_sha256,
                "status": row.status,
                "link_id": link.id, "link_state": link.state,
                "link_project": link.project_id, "link_added_by": link.added_by,
                "candidate_status": candidate.status,
                "candidate_decided_by": candidate.decided_by,
                "candidate_memory": candidate.resulting_memory_id,
                "provenance_locator": event.source_locator,
                "provenance_source": event.source_type,
                "folder_id": row.folder_id,
            }

    before = await snapshot()
    books = await _make_folder(a, "كتب المنهج")
    quantitative = await _make_folder(a, "المنهج الكمي", parent=books["id"])

    for target in (books["id"], quantitative["id"], None):
        moved = await a.post(f"/api/v1/files/{file_id}/move",
                             json={"folder_id": target})
        assert moved.status_code == 200, moved.text
        after = await snapshot()
        assert after["folder_id"] == (uuid.UUID(target) if target else None)
        for key, value in before.items():
            if key == "folder_id":
                continue
            assert after[key] == value, (
                f"نقلُ الملف غيّر {key!r}: {value!r} ← {after[key]!r} — "
                "والمجلَّد تنظيمٌ لا حالُ دليل")

    # **ومفتاح التخزين لم يتحرّك حرفًا.** لو نُقل الكائن مع المجلَّد لانكسر
    # كل رابطٍ موقّع وكل سجلّ إسنادٍ يشير إليه.
    assert (await snapshot())["storage_key"] == before_key


@requires_db
@pytest.mark.asyncio
async def test_a_file_moves_between_folders_and_the_listing_follows_it(clients, two_tenants):
    """القائمة تقول أين الملف الآن — لا أين كان."""
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    file_id = await _seed_file(tid, uid, "كتابٌ يتنقّل.pdf")
    folder = await _make_folder(a, "رفٌّ جديد")

    at_root = (await a.get("/api/v1/files?folder=root")).json()
    assert any(row["id"] == str(file_id) for row in at_root)

    assert (await a.post(f"/api/v1/files/{file_id}/move",
                         json={"folder_id": folder["id"]})).status_code == 200

    at_root = (await a.get("/api/v1/files?folder=root")).json()
    assert all(row["id"] != str(file_id) for row in at_root)
    inside = (await a.get(f"/api/v1/files?folder={folder['id']}")).json()
    assert [row["id"] for row in inside] == [str(file_id)]
    assert inside[0]["folder_id"] == folder["id"]

    # وبلا `folder` تبقى المكتبة كلها مقروءة — كما تقرؤها قوائم الاختيار.
    everything = (await a.get("/api/v1/files")).json()
    assert any(row["id"] == str(file_id) for row in everything)


@requires_db
@pytest.mark.asyncio
async def test_pagination_survives_inside_a_folder(clients, two_tenants):
    """الترقيم المفتاحيّ داخل مجلَّد: كل ملفٍ مرّة، بلا تكرارٍ ولا سقوط."""
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    folder = await _make_folder(a, "رفٌّ ممتلئ")
    made = [await _seed_file(tid, uid, f"كتاب {index}.pdf") for index in range(7)]
    for file_id in made:
        assert (await a.post(f"/api/v1/files/{file_id}/move",
                             json={"folder_id": folder["id"]})).status_code == 200

    seen: list[str] = []
    after = None
    while True:
        query = f"/api/v1/files?folder={folder['id']}&limit=3"
        if after:
            query += f"&after={after}"
        page = (await a.get(query)).json()
        if not page:
            break
        seen.extend(row["id"] for row in page)
        after = page[-1]["id"]
        if len(page) < 3:
            break

    assert len(seen) == len(set(seen)) == len(made)
    assert set(seen) == {str(file_id) for file_id in made}


# ── ٤. السلّة: حذفٌ يُستعاد، وتحذيرٌ بعدده ──

@requires_db
@pytest.mark.asyncio
async def test_deleting_a_linked_file_warns_with_a_number_before_it_happens(
        clients, two_tenants):
    """**التحذير الذي لا يُذكر فيه عدد ليس تحذيرًا.**

    والحذف نقلٌ إلى سلّة: الرابط باقٍ، والكائن باقٍ، والاستعادة ترجع
    الملف — ويُقال ذلك قبل الفعل لا بعده.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile, ResearchProject

    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    file_id = await _seed_file(tid, uid, "ملفٌّ يسند بحثين.pdf")

    async with tenant_session(tid, uid) as session:
        for title in ("بحثٌ أول", "بحثٌ ثانٍ"):
            project = ResearchProject(tenant_id=tid, working_title_ar=title,
                                      status="planned", current_gate="G1")
            session.add(project)
            await session.flush()
            session.add(ProjectFile(tenant_id=tid, project_id=project.id,
                                    file_id=file_id, state=ProjectFile.ACTIVE,
                                    added_by=uid))
        await session.flush()

    refused = await a.post(f"/api/v1/files/{file_id}/trash", json={"confirm": False})
    assert refused.status_code == 409
    body = refused.json()["error"]
    assert body["code"] == "library.file_linked_to_projects"
    assert body["context"]["projects"] == "2"

    confirmed = await a.post(f"/api/v1/files/{file_id}/trash", json={"confirm": True})
    assert confirmed.status_code == 200
    assert confirmed.json()["project_links"] == 2

    # الروابط باقية بعد الحذف — الحذف إخفاءٌ لا قطعُ سند.
    async with tenant_session(tid, uid) as session:
        links = (await session.execute(select(ProjectFile).where(
            ProjectFile.file_id == file_id))).scalars().all()
        assert len(links) == 2
        assert all(link.state == ProjectFile.ACTIVE for link in links)

    assert all(row["id"] != str(file_id)
               for row in (await a.get("/api/v1/files")).json())
    assert any(row["id"] == str(file_id)
               for row in (await a.get("/api/v1/files?trash=true")).json())

    restored = await a.post(f"/api/v1/files/{file_id}/restore")
    assert restored.status_code == 200
    assert any(row["id"] == str(file_id)
               for row in (await a.get("/api/v1/files?folder=root")).json())


@requires_db
@pytest.mark.asyncio
async def test_a_folder_that_still_holds_something_is_not_deleted_silently(
        clients, two_tenants):
    """يُقال كم فيه، ولا يُجرّ ما تحته ولا يُترك معلَّقًا.

    فجرُّ المحتوى يُخفي عشرات الملفات بضغطةٍ واحدة، وتركُه يُنتج ملفاتٍ
    في القاعدة لا تظهر في أي شاشة — وكلاهما ضياعٌ صامت.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    shelf = await _make_folder(a, "رفٌّ فيه كتاب")
    file_id = await _seed_file(tid, uid, "كتابٌ داخل الرفّ.pdf")
    await a.post(f"/api/v1/files/{file_id}/move", json={"folder_id": shelf["id"]})

    refused = await a.post(f"/api/v1/files/folders/{shelf['id']}/trash")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "library.folder_not_empty"
    assert refused.json()["error"]["context"]["files"] == "1"

    # يُفرَّغ ثم يُحذف — وحينئذٍ يُستعاد كما كان.
    await a.post(f"/api/v1/files/{file_id}/move", json={"folder_id": None})
    trashed = await a.post(f"/api/v1/files/folders/{shelf['id']}/trash")
    assert trashed.status_code == 200
    assert trashed.json()["trashed_at"] is not None

    live = (await a.get("/api/v1/files/folders")).json()["folders"]
    assert all(row["id"] != shelf["id"] for row in live)
    in_trash = (await a.get("/api/v1/files/folders?trash=true")).json()["folders"]
    assert any(row["id"] == shelf["id"] for row in in_trash)

    restored = await a.post(f"/api/v1/files/folders/{shelf['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["trashed_at"] is None
    live = (await a.get("/api/v1/files/folders")).json()["folders"]
    assert any(row["id"] == shelf["id"] for row in live)


@requires_db
@pytest.mark.asyncio
async def test_a_file_is_not_restored_into_a_folder_that_is_itself_in_the_trash(
        clients, two_tenants):
    """استعادةٌ صامتة إلى الجذر تنقل الملف من حيث تركه صاحبه بلا أن يُقال له.

    فيُوقَف الفعل برسالةٍ تقول ما يلزم: استعِد المجلَّد أولًا.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    shelf = await _make_folder(a, "رفٌّ سيُحذف")
    file_id = await _seed_file(tid, uid, "كتابٌ سيُحذف معه.pdf")
    await a.post(f"/api/v1/files/{file_id}/move", json={"folder_id": shelf["id"]})

    assert (await a.post(f"/api/v1/files/{file_id}/trash",
                         json={"confirm": True})).status_code == 200
    assert (await a.post(f"/api/v1/files/folders/{shelf['id']}/trash")).status_code == 200

    refused = await a.post(f"/api/v1/files/{file_id}/restore")
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "library.parent_in_trash"

    assert (await a.post(f"/api/v1/files/folders/{shelf['id']}/restore")).status_code == 200
    assert (await a.post(f"/api/v1/files/{file_id}/restore")).status_code == 200


# ── ٥. الكلفة: لا تنمو مع عدد المجلَّدات ──

@requires_db
@pytest.mark.asyncio
async def test_listing_a_folder_costs_the_same_however_many_folders_there_are(
        clients, two_tenants):
    """**العدد هو الزمن.** والقاعدة وراء بحر، فكل عبارةٍ رحلة.

    فيُقاس عدد العبارات لا عدد الصفوف: قائمةُ مجلَّدٍ فيه ثلاثة أبناء
    وقائمتُه وفيه عشرون يجب أن تكلّفا الشيء نفسه.
    """
    a = clients["a"]
    parent = await _make_folder(a, "رفٌّ كبير")

    for index in range(3):
        await _make_folder(a, f"قسم {index}", parent=parent["id"])
    with counting_statements() as few:
        assert (await a.get(f"/api/v1/files/folders?parent={parent['id']}")
                ).status_code == 200

    for index in range(3, 20):
        await _make_folder(a, f"قسم {index}", parent=parent["id"])
    with counting_statements() as many:
        listing = (await a.get(f"/api/v1/files/folders?parent={parent['id']}")).json()

    assert len(listing["folders"]) == 20
    assert len(few) == len(many), (
        f"كلفة القائمة نمت مع عدد المجلَّدات: {len(few)} ← {len(many)} عبارة")
    assert len(many) <= 3, f"قائمةُ مجلَّدٍ كلّفت {len(many)} عبارات"


@requires_db
@pytest.mark.asyncio
async def test_a_page_of_files_inside_a_folder_is_still_one_statement(clients, two_tenants):
    """صفحةُ الملفات عبارةٌ واحدة كما كانت قبل المجلَّدات — لا عبارة ونصف."""
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    folder = await _make_folder(a, "رفُّ القياس")
    for index in range(6):
        file_id = await _seed_file(tid, uid, f"مقياس {index}.pdf")
        await a.post(f"/api/v1/files/{file_id}/move", json={"folder_id": folder["id"]})

    with counting_statements() as seen:
        page = (await a.get(f"/api/v1/files?folder={folder['id']}&limit=5")).json()

    assert len(page) == 5
    assert len(seen) == 1, (
        "صفحةُ ملفاتٍ داخل مجلَّد كلّفت أكثر من عبارة: " + "; ".join(seen))
