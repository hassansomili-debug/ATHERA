"""بحثُ المكتبة ومرشّحاتها | My Library V2.1 — search and filters.

**مكتبةٌ فيها مئة ورقة لا يُوجد فيها شيء بالتصفّح.** المجلَّدات نظّمت
الرفوف، لكنّ من يذكر كلمةً من اسم ملفه — أو من عنوان رسالته — كان عليه أن
يفتح الرفوف واحدًا واحدًا يقرأ الأسماء. والصفحة محدودة بخمسةٍ وعشرين،
فـ«حمّل المزيد» عشر مرات ليست بحثًا.

وثلاثة تُثبَت هنا:

١) **البحث نصّيّ لا دلاليّ، ويقول ما يفعل**: الاسم، وعنوان الرسالة حيث
   وُجدت — ولا تضمين ولا «قريبٌ من». ونطاقُه هو `folder` نفسه: مجلَّدٌ
   بعينه أو المكتبة كلها.
٢) **المرشّح لا يَعِد بما لا يعرفه الخادم**: سبعةٌ لا غير، أربعةٌ من
   `content_type` وثلاثٌ من حال المعالجة — وهي بعينها الحال المعروضة في
   البطاقة، فلا يقول المرشّح غير ما تقوله. ومرشّحٌ مجهول يُردّ بـ422 ولا
   يُتجاهل بصمت.
٣) **الكلفة لا تتغيّر**: صفحةٌ ببحثٍ ومرشّحٍ معًا **عبارةٌ واحدة** كما
   كانت بلا أيّهما. والشرط في `WHERE` لا مرشِّحٌ في بايثون بعد القراءة —
   وتصفيةٌ بعد القراءة تُنتج صفحةً ناقصةً ثم تقول إنها كلُّ ما يطابق.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import inspect
import json
import pathlib
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ اختبارات خالصة: ما يُقرأ بلا قاعدة ═════════════════

def test_the_filters_are_exactly_the_seven_the_server_can_answer():
    """**لا مرشّح لما لا يعرفه الخادم.**

    «مقروء» و«مهمّ» و«حديث» أوصافٌ لا أعمدة؛ وزرٌّ يَعِد بتصفيةٍ لا يقدر
    عليها الخادم يردّ قائمةً لا تطابق اسمه — وذلك أسوأ من غياب الزرّ.
    """
    from athera_api.routers.files import FILE_KIND_FILTERS, FILTERS
    from athera_api.services.workspace import LIBRARY_STATE_FILTERS

    assert set(FILTERS) == {"pdf", "docx", "datasets", "references",
                            "processed", "awaiting_consent", "not_processed"}
    assert set(FILTERS) == set(FILE_KIND_FILTERS) | set(LIBRARY_STATE_FILTERS)


def test_every_filter_has_a_condition_and_the_unknown_one_is_refused():
    """مرشّحٌ بلا شرطٍ يمرّ فيعرض المكتبة كلها باسمٍ لا يصفها.

    فالباحث يضغط «مراجع» فيرى كتبه وبياناته، ويظنّ أن هذه هي مراجعه —
    كذبٌ صامت. فيُردّ المجهول بـ422، وتُذكر معه الخيارات كلها.
    """
    from athera_api.errors import AtheraError
    from athera_api.routers.files import FILTERS, _filter_predicate

    tenant = uuid.uuid4()
    assert _filter_predicate(None, tenant) is None
    for kind in FILTERS:
        assert _filter_predicate(kind, tenant) is not None, f"مرشّح بلا شرط: {kind}"

    with pytest.raises(AtheraError) as raised:
        _filter_predicate("important", tenant)
    assert raised.value.status_code == 422
    assert raised.value.code == "library.unknown_filter"
    # والخيارات تُذكر في الرسالة: رفضٌ لا يقول البديل نصفُ رفض.
    for kind in FILTERS:
        assert kind in str(raised.value.context["filters"])


def test_the_kind_filters_read_the_type_tables_not_a_second_list():
    """مفردةٌ ثانية تفترق عن سجلّها بأول نوعٍ يُضاف.

    فيصير مرشّح «بيانات» يُخفي ملفًّا يقبله الرفع — نقصٌ صامت لا رسالةَ له،
    وهو الخطأ المتكرر في هذا المستودع: قائمةٌ تُكتب بجانب مصدرها.
    """
    from athera_api.routers import files as router
    from athera_api.services import storage

    source = inspect.getsource(router._kind_predicate)
    for reference in ("storage.PDF_TYPE", "storage.DOCX_TYPE",
                      "storage.DATASET_TYPES", "storage.REFERENCE_TYPES"):
        assert reference in source, f"المرشّح لا يقرأ {reference}"
    # وكلُّ نوعٍ مذكور نوعٌ يقبله الرفع فعلًا — لا اسمٌ مخترع.
    assert storage.PDF_TYPE in storage.ALLOWED_CONTENT_TYPES
    assert storage.DOCX_TYPE in storage.ALLOWED_CONTENT_TYPES
    assert storage.REFERENCE_TYPES <= storage.ALLOWED_CONTENT_TYPES


def test_the_state_filter_is_derived_from_the_very_columns_the_card_shows():
    """**حسابان لحالٍ واحدة يفترقان، فيرى الباحث تناقضًا في شاشةٍ واحدة.**

    بطاقةٌ تقول «مُعالَج» وملفُّها لا يظهر في مرشّح «مُعالَج» — والباحث
    يظنّ المرشّح معطوبًا أو البطاقة كاذبة، وكلاهما صحيح.
    """
    from athera_api.services import workspace

    source = inspect.getsource(workspace.file_state_predicate)
    assert "file_processing_state_columns" in source, (
        "شرطُ الحال لا يُشتقّ من أعمدة الحال المعروضة")
    assert workspace.file_state_predicate(uuid.uuid4(), "nonsense") is None


def test_the_search_escapes_the_two_characters_that_are_not_letters():
    """`%` و`_` في يد الباحث حرفان لا محرفا بدل.

    فمن بحث عن «نسبة_العائد» يقصد الاسم نفسه؛ وترك المحرفين بلا هروب يجعل
    بحثًا عن `%` وحده يطابق المكتبة كلها ثم يقول إن هذه نتائجُ بحثه.
    """
    from athera_api.services import workspace

    tenant = uuid.uuid4()
    assert workspace.file_text_predicate(tenant, "   ") is None, (
        "بحثٌ بفراغٍ محضٍ ليس بحثًا، ولا يجوز أن يُصفّي شيئًا")

    rendered = str(workspace.file_text_predicate(tenant, "نسبة_العائد%")
                   .compile(compile_kwargs={"literal_binds": True}))
    assert "\\_" in rendered and "\\%" in rendered, (
        "محرفا البدل يمرّان بلا هروب: " + rendered[:200])
    assert "ESCAPE" in rendered.upper()


def test_the_search_looks_at_the_name_and_at_the_title_where_there_is_one():
    """الباحث يذكر ما في المستند لا ما سمّى به ملفه.

    و«thesis-final-v3.pdf» لا يُبحث عنه باسمه بل بعنوانه. و«حيث وُجد» قيدٌ
    صادق: ملفٌّ لم يُقرأ لا عنوان له، فلا يُختلق له واحد.
    """
    from athera_api.services import workspace

    rendered = str(workspace.file_text_predicate(uuid.uuid4(), "المنهج")
                   .compile(compile_kwargs={"literal_binds": True}))
    assert "files.original_filename" in rendered
    assert "theses.title_ar" in rendered and "theses.title_en" in rendered
    # وشرطٌ واحد في العبارة نفسها: `EXISTS` مرتبط، لا عبارةٌ ثانية.
    assert "EXISTS" in rendered.upper()


def test_the_page_is_still_one_statement_with_a_search_and_a_filter_on_it():
    """**الحارس الذي دفع ثمنه الإنتاج مرّة.**

    كانت الصفحة `1 + 3N` عبارة فبلغت ثلاثين ثانية. والبحث والتصفية أسهلُ
    بابين لإعادة العطب: قائمةُ معرّفاتٍ تُقرأ أولًا ثم تُمرَّر، أو تصفيةٌ
    في بايثون بعد القراءة. فيُقرأ المسار نصًّا: عبارةٌ واحدة، والشرطان في
    `WHERE` لا بعده.
    """
    from athera_api.routers import files as router

    source = inspect.getsource(router.list_files)
    assert source.count("await session.execute") == 1, (
        "صفحة المكتبة صارت أكثر من عبارة")
    assert "page = page.where(matching)" in source, "البحث ليس شرطًا في العبارة"
    assert "page = page.where(chosen)" in source, "المرشّح ليس شرطًا في العبارة"
    # ولا تصفيةَ بعد القراءة: الحلقة تبني الردّ ولا تُسقط منه شيئًا.
    assert "continue" not in source and "if row" not in source, (
        "تصفيةٌ في بايثون بعد قراءة الصفحة تُنتج صفحةً ناقصة تدّعي الاكتمال")


def test_every_filter_and_search_string_exists_in_both_languages():
    """العربية لغة المنتج والإنجليزية ثانيتها — ونقصُ إحداهما نصٌّ مفقود.

    ولكل مرشّحٍ في الخادم اسمٌ في الشاشة: مرشّحٌ بلا اسمٍ زرٌّ بلا كلمة.
    """
    from athera_api.routers.files import FILTERS

    ar = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))
    en = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))
    for locale, messages in (("ar", ar), ("en", en)):
        names = messages["library"]["filters"]
        for kind in FILTERS:
            assert names.get(kind), f"المرشّح {kind} بلا اسمٍ بلغة {locale}"
        for key in ("all", "label", "searchLabel", "searchPlaceholder",
                    "searchClear", "searchScopeFolder", "searchScopeAll",
                    "noMatches"):
            assert messages["library"].get(key), f"نصّ البحث {key} ناقصٌ بلغة {locale}"


# ══════════════════════ اختبارات تمسّ القاعدة ══════════════════════

pytest_asyncio = pytest.importorskip("pytest_asyncio")


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


async def _seed_file(tenant_id: uuid.UUID, user_id: uuid.UUID, name: str,
                     content_type: str = "application/pdf") -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.identity import ObjectGrant

    async with tenant_session(tenant_id, user_id) as session:
        row = File(tenant_id=tenant_id, storage_key=f"tenants/{tenant_id}/{uuid.uuid4()}",
                   original_filename=name, content_type=content_type,
                   size_bytes=2048, checksum_sha256="0" * 64, classification="C2",
                   status="stored", uploaded_by=user_id, completed_at=_now())
        session.add(row)
        await session.flush()
        session.add(ObjectGrant(tenant_id=tenant_id, object_type="file",
                                object_id=row.id, user_id=user_id,
                                grant_level="owner", granted_by=user_id))
        await session.flush()
        return row.id


async def _give_state(tenant_id: uuid.UUID, user_id: uuid.UUID, file_id: uuid.UUID,
                      run_status: str, title: str | None = None) -> None:
    """رسالةٌ وتشغيلةٌ حقيقيتان — فالحال تُقرأ منهما لا تُكتب في عمود."""
    from athera_api.db import tenant_session
    from athera_api.models.research import ExtractionRun
    from athera_api.models.thesis import Thesis

    async with tenant_session(tenant_id, user_id) as session:
        session.add(Thesis(tenant_id=tenant_id, file_id=file_id,
                           title_ar=title or "رسالةٌ بلا عنوانٍ مميّز"))
        session.add(ExtractionRun(tenant_id=tenant_id, file_id=file_id,
                                  extractor="rules", status=run_status,
                                  started_at=_now()))
        await session.flush()


async def _make_folder(http, name: str) -> dict:
    response = await http.post("/api/v1/files/folders", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


@requires_db
@pytest.mark.asyncio
async def test_search_finds_a_file_by_its_name_and_by_its_title(clients, two_tenants):
    """اسمٌ يذكره الباحث، أو عنوانٌ في مستنده — والمكتبة تجد الاثنين.

    وملفٌّ سُمّي `thesis-final-v3.pdf` لا يُبحث عنه باسمه؛ فلولا العنوان
    لكان البحث يعرض ما سمّاه الباحث جيّدًا وحده، ويُخفي عنه بقيّة مكتبته.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    named = await _seed_file(tid, uid, "أثر البرنامج في التفكير الناقد.pdf")
    titled = await _seed_file(tid, uid, "thesis-final-v3.pdf")
    other = await _seed_file(tid, uid, "بيانات الاستبانة.csv", "text/csv")
    await _give_state(tid, uid, titled, "completed",
                      title="أثر التدريب في الدافعية الأكاديمية")

    by_name = (await a.get("/api/v1/files?q=التفكير الناقد")).json()
    assert [row["id"] for row in by_name] == [str(named)]

    by_title = (await a.get("/api/v1/files?q=الدافعية")).json()
    assert [row["id"] for row in by_title] == [str(titled)]

    # وبحثٌ يطابق الاثنين يعرضهما، ولا يعرض ما لا يطابق.
    both = {row["id"] for row in (await a.get("/api/v1/files?q=أثر")).json()}
    assert both == {str(named), str(titled)}
    assert str(other) not in both


@requires_db
@pytest.mark.asyncio
async def test_search_is_scoped_by_the_same_folder_parameter_as_the_listing(
        clients, two_tenants):
    """نطاقُ البحث هو `folder` نفسه — **لا معاملُ نطاقٍ ثالث يقول ما يقوله**.

    فالباحث إمّا يبحث في الرفّ الذي يقف فيه، وإمّا في مكتبته كلها؛
    والمعاملان لشيءٍ واحد يفترقان بأول تعديل.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    shelf = await _make_folder(a, "رفُّ المنهج")
    inside = await _seed_file(tid, uid, "منهج البحث الكمي.pdf")
    outside = await _seed_file(tid, uid, "منهج البحث النوعي.pdf")
    assert (await a.post(f"/api/v1/files/{inside}/move",
                         json={"folder_id": shelf["id"]})).status_code == 200

    here = {row["id"] for row in
            (await a.get(f"/api/v1/files?q=منهج&folder={shelf['id']}")).json()}
    assert here == {str(inside)}

    everywhere = {row["id"] for row in (await a.get("/api/v1/files?q=منهج")).json()}
    assert everywhere == {str(inside), str(outside)}


@requires_db
@pytest.mark.asyncio
async def test_a_wildcard_typed_by_a_researcher_is_a_letter_not_a_wildcard(
        clients, two_tenants):
    """من كتب `%` يبحث عن `%` — ولا يُقال له إن كل مكتبته نتيجةُ بحثه."""
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    percent = await _seed_file(tid, uid, "نسبة 100% من العينة.pdf")
    await _seed_file(tid, uid, "ورقةٌ لا رقم فيها.pdf")

    found = (await a.get("/api/v1/files?q=100%25")).json()
    assert [row["id"] for row in found] == [str(percent)]

    # و`%` وحده لا يطابق شيئًا اسمُه لا يحويه.
    only_percent = {row["id"] for row in (await a.get("/api/v1/files?q=%25")).json()}
    assert only_percent == {str(percent)}


@requires_db
@pytest.mark.asyncio
async def test_a_search_finds_nothing_of_another_tenants_library(clients, two_tenants):
    """العزل يسبق البحث: ما لا يُرى لا يُبحث فيه."""
    a, b = clients["a"], clients["b"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    mine = await _seed_file(tid, uid, "سرُّ المستأجر الأول.pdf")

    theirs = (await b.get("/api/v1/files?q=سرُّ")).json()
    assert all(row["id"] != str(mine) for row in theirs)
    assert (await a.get("/api/v1/files?q=سرُّ")).json()[0]["id"] == str(mine)


@requires_db
@pytest.mark.asyncio
async def test_each_kind_filter_returns_exactly_what_its_name_says(clients, two_tenants):
    """اسمُ المرشّح وعدٌ: من ضغط «بيانات» ينتظر بياناته كلها ولا شيء غيرها."""
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    made = {
        "pdf": await _seed_file(tid, uid, "ورقة.pdf", "application/pdf"),
        "docx": await _seed_file(tid, uid, "مسودة.docx", DOCX_TYPE),
        "datasets": await _seed_file(tid, uid, "استبانة.csv", "text/csv"),
        "references": await _seed_file(tid, uid, "مراجعي.ris", "text/plain"),
    }

    for kind, file_id in made.items():
        page = {row["id"] for row in (await a.get(f"/api/v1/files?kind={kind}")).json()}
        assert str(file_id) in page, f"مرشّح {kind} لا يعرض ما يخصّه"
        for other, other_id in made.items():
            if other != kind:
                assert str(other_id) not in page, (
                    f"مرشّح {kind} يعرض ملفَّ {other}")

    # والمراجع تُعرف بامتدادها أيضًا حين يصل النوع `text/plain` من المتصفح.
    assert str(made["references"]) in {
        row["id"] for row in (await a.get("/api/v1/files?kind=references")).json()}


@requires_db
@pytest.mark.asyncio
async def test_the_state_filter_agrees_with_the_state_the_card_shows(clients, two_tenants):
    """**التكافؤ نفسه، لا رمزَ نجاحٍ ولا «تقريبًا».**

    القائمة المصفّاة تُقارَن بالقائمة كاملةً مصفّاةً بالحال المعروضة — فإن
    افترقتا رأى الباحث بطاقةً تقول «مُعالَج» وملفًّا لا يظهر في مرشّح
    «مُعالَج»، وهو تناقضٌ في شاشةٍ واحدة.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    done = await _seed_file(tid, uid, "مُعالَج.pdf")
    waiting = await _seed_file(tid, uid, "بانتظار إذنٍ.pdf")
    untouched = await _seed_file(tid, uid, "لم يُقرأ بعد.pdf")
    await _give_state(tid, uid, done, "completed")
    await _give_state(tid, uid, waiting, "awaiting_consent")

    everything = (await a.get("/api/v1/files?limit=100")).json()
    for state in ("processed", "awaiting_consent", "not_processed"):
        shown = "completed" if state == "processed" else state
        expected = {row["id"] for row in everything
                    if row["processing_status"] == shown}
        got = {row["id"] for row in
               (await a.get(f"/api/v1/files?kind={state}&limit=100")).json()}
        assert got == expected, (
            f"مرشّح {state} يفترق عن الحال المعروضة: "
            f"زائد {sorted(got - expected)} / ناقص {sorted(expected - got)}")

    assert str(untouched) in {row["id"] for row in
                              (await a.get("/api/v1/files?kind=not_processed")).json()}


@requires_db
@pytest.mark.asyncio
async def test_an_unknown_filter_is_refused_and_not_quietly_ignored(clients):
    """تجاهلُه يعرض المكتبة كلها باسمٍ لا يصفها — كذبٌ صامت."""
    a = clients["a"]
    refused = await a.get("/api/v1/files?kind=important")
    assert refused.status_code == 422, refused.text
    assert refused.json()["error"]["code"] == "library.unknown_filter"


@requires_db
@pytest.mark.asyncio
async def test_a_searched_and_filtered_page_is_still_exactly_one_statement(
        clients, two_tenants):
    """**العدد هو الزمن، والقاعدة وراء بحر.**

    وصفحةٌ ببحثٍ ومرشّحٍ يجب أن تكلّف ما تكلّفه صفحةٌ بلا أيّهما — عبارةً
    واحدة. وأيّ صياغةٍ تقرأ المعرّفات أولًا ثم تُمرّرها تُعيد `1 + N` من
    بابٍ جديد.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    for index in range(8):
        file_id = await _seed_file(tid, uid, f"منهج {index}.pdf")
        if index % 2 == 0:
            await _give_state(tid, uid, file_id, "completed")

    with counting_statements() as plain:
        assert (await a.get("/api/v1/files?limit=5")).status_code == 200
    with counting_statements() as searched:
        assert (await a.get("/api/v1/files?q=منهج&limit=5")).status_code == 200
    with counting_statements() as both:
        page = (await a.get("/api/v1/files?q=منهج&kind=processed&limit=5")).json()

    assert len(plain) == 1
    assert len(searched) == 1, "البحث كلّف عبارةً ثانية: " + "; ".join(searched)
    assert len(both) == 1, "البحث والمرشّح كلّفا عبارةً ثانية: " + "; ".join(both)
    assert all(row["processing_status"] == "completed" for row in page)


@requires_db
@pytest.mark.asyncio
async def test_paging_a_filtered_search_covers_every_match_exactly_once(
        clients, two_tenants):
    """الترقيم المفتاحيّ يبقى مفتاحيًّا تحت الشرطين.

    ولو صُفّيت الصفحة بعد قراءتها لعادت أقصر من حدّها، فيظنّ العميل أنه بلغ
    النهاية ويُخفي «حمّل المزيد» — ونصفُ النتائج لا يراها أحد.
    """
    a = clients["a"]
    tid, uid = two_tenants["a"]["tenant_id"], two_tenants["a"]["user_id"]
    wanted = {str(await _seed_file(tid, uid, f"منهجٌ مطلوب {index}.pdf"))
              for index in range(7)}
    for index in range(5):
        await _seed_file(tid, uid, f"شيءٌ آخر {index}.csv", "text/csv")

    seen: list[str] = []
    after = None
    while True:
        query = "/api/v1/files?q=منهجٌ مطلوب&kind=pdf&limit=3"
        if after:
            query += f"&after={after}"
        page = (await a.get(query)).json()
        if not page:
            break
        seen.extend(row["id"] for row in page)
        after = page[-1]["id"]
        if len(page) < 3:
            break

    assert len(seen) == len(set(seen)) == len(wanted)
    assert set(seen) == wanted
