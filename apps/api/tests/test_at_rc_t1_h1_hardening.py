"""RC-T1-H1 — تقويةُ الحدّ: معاملةٌ واحدة، وبثٌّ، وخلفيّة، وإطار.

## ما يُقاس هنا وما لا يُقاس

الدعوى الأصليّة — «جوابُ النجاح يعني أنّ الإيداع وقع» — مفحوصةٌ في
`test_at_rc_t1_h1_transaction_integrity.py` بقيدٍ مؤجَّلٍ حقيقيّ. وهذا
الملفُّ يُغلق أربعةَ أسئلةٍ بنيويّةٍ تُسأل قبل الدمج:

  ب/ج · **طلبٌ واحد، معاملةٌ واحدةٌ على الأكثر.** وإيداعُ معاملتين
        بالتسلسل ليس ذرّيًّا: تنجح الأولى وتُخفق الثانية، فيصير الجوابُ
        إخفاقًا **والأولى مُودَعة**. فتُرفض الثانيةُ مغلقًا قبل أن يكتب
        المعالجُ شيئًا.
  و   · **الإطارُ مُثبَّتٌ بدقّة.** الحدُّ يتّكل على ترتيبٍ في
        `fastapi/routing.py`، والحدُّ الأدنى المفتوح كان يجعل الالتزامَ
        الواحدَ يُركِّب إطارًا آخر غدًا.
  ز   · **البثُّ يُودِع قبل أوّل بايت.** `files.stream_file` مسارُ `GET`
        **يكتب** (سجلُّ اطّلاعٍ وتدقيق)، ويردّ `StreamingResponse`.
  ح   · **مهمّةُ الخلفية لا تعمل على إيداعٍ أخفق.**

**وما لا يُقاس هنا — ولا يُدَّعى:** أنّ العميلَ **استلم** الجواب. الإيداعُ
قد ينجح ثمّ ينقطع الاتصالُ قبل الاستلام، فيُعيد العميلُ الطلبَ فتقع
الطفرةُ مرّتين. وذاك `RC-T1-H2` — دَينٌ مستقلٌّ مُعلَن، لا يحلّه هذا الطور.
"""
from __future__ import annotations

import io
import re
import uuid

from fastapi import APIRouter, Depends, FastAPI, Request

PDF = b"%PDF-1.7\n% athera hardening\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


# ══════════════════════════════════════════════════════════════════════
#  ب — كم معاملةً يملك طلبٌ واحد؟ من الشجرة المُركَّبة لا من الحدس
# ══════════════════════════════════════════════════════════════════════

def _api_routes():
    from fastapi.routing import APIRoute

    from athera_api.main import app

    found, seen = [], set()

    def walk(node) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        for route in getattr(node, "routes", ()) or ():
            if isinstance(route, APIRoute):
                found.append(route)
            walk(route)
            for attr in ("original_router", "router", "app"):
                child = getattr(route, attr, None)
                if child is not None:
                    walk(child)
        for attr in ("original_router", "router", "app"):
            child = getattr(node, attr, None)
            if child is not None:
                walk(child)

    walk(app)
    return {(r.path, tuple(sorted(r.methods))): r for r in found}


def _session_dependants(dependant, out, uncached):
    from athera_api import deps

    session_deps = {deps.get_session, deps.get_project_session}
    call = getattr(dependant, "call", None)
    if call in session_deps:
        cached = getattr(dependant, "use_cache", True)
        out.append((call.__name__, cached))
        if not cached:
            uncached.append(call.__name__)
    for sub in getattr(dependant, "dependencies", ()) or ():
        _session_dependants(sub, out, uncached)


def test_01_no_current_route_can_own_more_than_one_request_transaction() -> None:
    """**مقيسٌ على المسارات كلِّها**، بتبعيّاتها المتداخلة و`use_cache`.

    فالوحدانيّةُ المُنفَّذة في `register_request_session` لا تكسر مسارًا
    قائمًا — وهذا هو الفحصُ الذي يُثبته قبل أن يُنفَّذ.

    وتخزينُ FastAPI المؤقّت لكلِّ طلب يعني أنّ نداءً واحدًا متكرّرًا
    بـ`use_cache=True` جلسةٌ واحدة؛ و`use_cache=False` يُنتج نسخةً ثانية —
    فيُعَدُّ صريحًا.
    """
    worst, offenders, uncached_routes = 0, [], []
    for (path, methods), route in _api_routes().items():
        found, uncached = [], []
        _session_dependants(route.dependant, found, uncached)
        distinct = len({name for name, cached in found if cached})
        distinct += sum(1 for _, cached in found if not cached)
        worst = max(worst, distinct)
        if distinct > 1:
            offenders.append(f"{methods} {path} -> {found}")
        if uncached:
            uncached_routes.append(f"{methods} {path} -> {uncached}")

    assert not offenders, (
        "مساراتٌ تملك أكثر من معاملةٍ واحدة — وإيداعُها بالتسلسل ليس ذرّيًّا:\n"
        + "\n".join(offenders))
    assert not uncached_routes, (
        "تبعيّةُ جلسةٍ بـ`use_cache=False` تُنتج معاملةً ثانية:\n"
        + "\n".join(uncached_routes))
    assert worst == 1, f"الأقصى المقيس {worst} — والمنتظر ١"


def test_02_the_session_count_scanner_would_notice_two_sessions() -> None:
    """**حارسٌ لا يسقط أبدًا ليس حارسًا** — فتُحاكى شجرةٌ بجلستين."""
    from athera_api import deps

    class FakeDependant:
        def __init__(self, call=None, dependencies=(), use_cache=True):
            self.call = call
            self.dependencies = list(dependencies)
            self.use_cache = use_cache

    tree = FakeDependant(dependencies=[
        FakeDependant(call=deps.get_session),
        FakeDependant(call=deps.get_project_session),
    ])
    found, uncached = [], []
    _session_dependants(tree, found, uncached)
    distinct = len({n for n, c in found if c}) + sum(1 for _, c in found if not c)
    assert distinct == 2, "الماسحُ لا يرى جلستين متمايزتين"

    repeated = FakeDependant(dependencies=[
        FakeDependant(call=deps.get_session),
        FakeDependant(call=deps.get_session, use_cache=False),
    ])
    found, uncached = [], []
    _session_dependants(repeated, found, uncached)
    assert uncached == ["get_session"], "الماسحُ لا يرى `use_cache=False`"


# ══════════════════════════════════════════════════════════════════════
#  ج — الوحدانيّة تُنفَّذ مغلقةً، قبل أن يكتب المعالجُ شيئًا
# ══════════════════════════════════════════════════════════════════════

def _probe_app(slot, *, second_session: bool, background: bool = False,
               state: dict | None = None):
    """تطبيقٌ صغير بصنف المسار **الحقيقيّ** وتبعيّاتِ جلسةٍ حقيقيّة.

    ولا يُضاف مسارٌ كهذا إلى التطبيق الحقيقيّ: المقيسُ هو الآلة، والآلةُ
    هي `TransactionalRoute` و`register_request_session` بأعيانهما.
    """
    from starlette.background import BackgroundTask

    from athera_api.db import tenant_session
    from athera_api.errors import AtheraError, athera_error_handler
    from athera_api.models.portfolio import ResearchProject
    from athera_api.transaction import TransactionalRoute, register_request_session

    marks = state if state is not None else {}
    app = FastAPI()
    app.add_exception_handler(AtheraError, athera_error_handler)
    router = APIRouter(route_class=TransactionalRoute)

    async def session_one(request: Request):
        async with tenant_session(slot["tenant_id"], slot["user_id"],
                                  owns_commit=False) as session:
            register_request_session(request, session)
            yield session

    async def session_two(request: Request):
        async with tenant_session(slot["tenant_id"], slot["user_id"],
                                  owns_commit=False) as session:
            register_request_session(request, session)
            yield session

    def _ran() -> None:
        marks["background_ran"] = True

    if second_session:
        @router.post("/probe")
        async def probe(title: str, first=Depends(session_one),
                        second=Depends(session_two)):  # noqa: ANN001
            marks["handler_ran"] = True
            first.add(ResearchProject(
                tenant_id=slot["tenant_id"], working_title_ar=title,
                status="planned", current_gate="G1"))
            second.add(ResearchProject(
                tenant_id=slot["tenant_id"], working_title_ar=f"{title}-second",
                status="planned", current_gate="G1"))
            return {"ok": True}
    else:
        @router.post("/probe")
        async def probe(title: str, first=Depends(session_one)):  # noqa: ANN001
            marks["handler_ran"] = True
            first.add(ResearchProject(
                tenant_id=slot["tenant_id"], working_title_ar=title,
                status="planned", current_gate="G1"))
            from fastapi.responses import JSONResponse
            if background:
                return JSONResponse({"ok": True},
                                    background=BackgroundTask(_ran))
            return JSONResponse({"ok": True})

    app.include_router(router)
    return app, marks


def _probe_client(app):
    import httpx

    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://probe")


async def test_03_a_single_session_request_registers_exactly_one(two_tenants):
    """الحالُ الطبيعيّة: معاملةٌ واحدةٌ تُسجَّل، والطفرةُ تقع."""
    import tests.test_at_rc_t1_h1_transaction_integrity as base

    title = f"h1-single-{uuid.uuid4().hex[:8]}"
    app, marks = _probe_app(two_tenants["a"], second_session=False)
    async with _probe_client(app) as http:
        response = await http.post("/probe", params={"title": title})
    assert response.status_code == 200, response.text
    assert marks.get("handler_ran") is True
    assert await base._project_rows(title) == 1


async def test_04_registering_the_same_session_twice_is_harmless() -> None:
    """الكائنُ نفسُه مرّتين لا يضرّ — فالدالّةُ صالحةٌ لإعادة النداء."""
    from athera_api.transaction import register_request_session, request_session

    class FakeState:
        pass

    class FakeRequest:
        def __init__(self):
            self.state = FakeState()
            self.headers: dict[str, str] = {}
            self.scope: dict[str, object] = {}
            self.method = "POST"

        @property
        def url(self):  # pragma: no cover - لا يُقرأ في المسار السليم
            raise AssertionError("لا يُقرأ العنوان في المسار السليم")

    sentinel = object()
    request = FakeRequest()
    register_request_session(request, sentinel)  # type: ignore[arg-type]
    register_request_session(request, sentinel)  # type: ignore[arg-type]
    assert request_session(request) is sentinel  # type: ignore[arg-type]


async def test_05_a_second_distinct_session_fails_closed(two_tenants):
    """**معاملةٌ ثانيةٌ تُرفض** — ولا يعمل المعالجُ، ولا يُودَع صفٌّ من أيّهما."""
    import tests.test_at_rc_t1_h1_transaction_integrity as base

    title = f"h1-double-{uuid.uuid4().hex[:8]}"
    app, marks = _probe_app(two_tenants["a"], second_session=True)
    async with _probe_client(app) as http:
        response = await http.post("/probe", params={"title": title})

    assert response.status_code == 500, response.text
    assert response.json()["error"]["code"] == "db.multiple_request_transactions"
    # **والرفضُ قبل الكتابة**: التبعيّةُ ترفع قبل `yield`، فلا يعمل المعالج.
    assert marks.get("handler_ran") is not True, (
        "عمل المعالجُ بعد رفض المعاملة الثانية — فالرفضُ جاء متأخّرًا")
    assert await base._project_rows(title) == 0
    assert await base._project_rows(f"{title}-second") == 0


# ══════════════════════════════════════════════════════════════════════
#  و — الإطارُ مُثبَّتٌ بدقّة، ولا تُرقّى بأثرٍ جانبيّ
# ══════════════════════════════════════════════════════════════════════

#: الإطارُ الذي جُرِّب عليه حدُّ المعاملة. وترقيتُه تستوجب إعادةَ تشغيل
#: فحوص الإيداع-قبل-الجواب وفكِّ التبعيّات والبثّ وRC E2E.
VALIDATED_FASTAPI = "0.141.1"


def test_06_fastapi_is_pinned_exactly_to_the_validated_version() -> None:
    """**الالتزامُ الواحد يُركِّب الإطارَ نفسَه دائمًا.**

    ولا ملفَّ قفلٍ في المستودع، وصورةُ Docker تُعيد الحلَّ في كلّ بناء
    (`pip install -e`). فحدٌّ أدنى مفتوح يعني أنّ عقدَ الصحّة رهنَ ما
    حلّه pip يومَ البناء.
    """
    import pathlib

    pyproject = (pathlib.Path(__file__).resolve().parents[1] / "pyproject.toml")
    declared = re.search(r'"fastapi==([0-9.]+)"', pyproject.read_text(encoding="utf-8"))
    assert declared, "fastapi غيرُ مُثبَّتٍ بدقّة في pyproject.toml"
    assert declared.group(1) == VALIDATED_FASTAPI, (
        f"التثبيتُ {declared.group(1)} والمُجرَّبُ {VALIDATED_FASTAPI} — "
        "ترقيةُ الإطار تستوجب إعادةَ تشغيل فحوص حدِّ المعاملة")


def test_07_the_installed_framework_matches_the_pin() -> None:
    """والمُركَّبُ هو المُثبَّت — وإلّا فالفحوصُ تقيس إطارًا غيرَ المنشور."""
    import fastapi

    assert fastapi.__version__ == VALIDATED_FASTAPI, (
        f"المُركَّب {fastapi.__version__} والمُثبَّت {VALIDATED_FASTAPI}")


def test_08_the_commit_boundary_assumption_is_still_true_in_this_framework() -> None:
    """والافتراضُ يُقرأ من الحزمة: الجوابُ يُرسَل **داخل** حزمةِ التبعيّات.

    فلو خرج الإرسالُ من متنها في إطارٍ أحدث صار الغلافُ زائدًا لا خاطئًا —
    ووجب إعادةُ النظر. **والدعوى السلوكيّةُ هي المرجع** لا هذا الفحص:
    `test_at_rc_t1_h1_transaction_integrity.py::test_02`.
    """
    import inspect

    from fastapi import routing

    lines = inspect.getsource(routing.request_response).splitlines()

    def at(needle: str) -> tuple[int, int]:
        for index, line in enumerate(lines):
            if needle in line:
                return index, len(line) - len(line.lstrip())
        raise AssertionError(f"بنيةُ FastAPI تغيّرت: لم يُعثر {needle!r}")

    stack_at, stack_indent = at("async with AsyncExitStack() as request_stack:")
    send_at, send_indent = at("await response(scope, receive, send)")
    assert send_at > stack_at
    assert send_indent > stack_indent, (
        "الإرسالُ خرج من متن حزمة التبعيّات — يُراجَع حدُّ المعاملة")


# ══════════════════════════════════════════════════════════════════════
#  ز — البثُّ يُودِع قبل أوّل بايت
# ══════════════════════════════════════════════════════════════════════

async def _access_log_rows(file_id: uuid.UUID) -> int:
    from sqlalchemy import text

    import tests.test_at_rc_t1_h1_transaction_integrity as base

    engine, factory = await base._owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                return (await session.execute(text(
                    "SELECT count(*) FROM file_access_logs WHERE file_id = :f"),
                    {"f": str(file_id)})).scalar_one()
    finally:
        await engine.dispose()


async def _plant_bomb_on(table: str, name: str) -> None:
    from sqlalchemy import text

    import tests.test_at_rc_t1_h1_transaction_integrity as base

    engine, factory = await base._owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    f"CREATE OR REPLACE FUNCTION {name}() RETURNS trigger"
                    " LANGUAGE plpgsql AS $fn$ BEGIN"
                    "   RAISE EXCEPTION 'RC-T1-H1 hardening: planted commit failure';"
                    " END $fn$"))
                await session.execute(text(
                    f"DROP TRIGGER IF EXISTS {name}_trg ON {table}"))
                await session.execute(text(
                    f"CREATE CONSTRAINT TRIGGER {name}_trg AFTER INSERT ON {table}"
                    " DEFERRABLE INITIALLY DEFERRED"
                    f" FOR EACH ROW EXECUTE FUNCTION {name}()"))
    finally:
        await engine.dispose()


async def _remove_bomb_on(table: str, name: str) -> None:
    from sqlalchemy import text

    import tests.test_at_rc_t1_h1_transaction_integrity as base

    engine, factory = await base._owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    f"DROP TRIGGER IF EXISTS {name}_trg ON {table}"))
                await session.execute(text(f"DROP FUNCTION IF EXISTS {name}()"))
    finally:
        await engine.dispose()


async def test_09_the_streaming_route_commits_before_the_body_starts(two_tenants):
    """**`GET …/content` مسارٌ يكتب** — سجلُّ اطّلاعٍ وتدقيق، ثمّ يبثّ.

    والدعوى حادّة: يُزرع قيدٌ مؤجَّل على `file_access_logs`، فإن كان
    الإيداعُ **قبل** بدء الجسم وصل العميلَ خطأٌ **بلا بايتٍ واحد**؛ ولو
    كان بعده لَأخذ ٢٠٠ والملفَّ كاملًا ثمّ أخفق الإيداعُ صامتًا.
    """
    import tests.test_at_rc_t1_h1_transaction_integrity as base

    async with base._client(two_tenants["a"]) as http:
        uploaded = await http.post(
            "/api/v1/files/upload",
            files={"upload": ("hardening.pdf", io.BytesIO(PDF), "application/pdf")})
        assert uploaded.status_code == 201, uploaded.text
        file_id = uuid.UUID(uploaded.json()["id"])

        # ── الضابط: تنزيلٌ سليمٌ يعيد البايتات نفسَها ويُسجّل اطّلاعًا ──
        before = await _access_log_rows(file_id)
        good = await http.get(f"/api/v1/files/{file_id}/content")
        assert good.status_code == 200
        assert good.content == PDF
        assert await _access_log_rows(file_id) == before + 1, (
            "لم يُودَع سجلُّ الاطّلاع — فالفحصُ التالي لا يقيس شيئًا")

        # ── والقيدُ المؤجَّل: لا جسمَ ولا نجاح ──
        await _plant_bomb_on("file_access_logs", "athera_h1_access_bomb")
        try:
            blocked = await http.get(f"/api/v1/files/{file_id}/content")
        finally:
            await _remove_bomb_on("file_access_logs", "athera_h1_access_bomb")

    assert blocked.status_code >= 400, (
        "البثُّ ردَّ نجاحًا وإيداعُ سجلِّ الاطّلاع أخفق — "
        f"فالإيداعُ يقع بعد بدء الجسم: HTTP {blocked.status_code}")
    assert blocked.content != PDF, "أُرسل الملفُّ كاملًا رغم إخفاق الإيداع"
    assert await _access_log_rows(file_id) == before + 1, "بقي سجلٌّ من معاملةٍ أخفقت"


def test_10_the_stream_body_does_not_read_from_the_committed_session() -> None:
    """ومُكرِّرُ البثّ لا يتّكل على المعاملة التي أُودعت توًّا.

    فالمجرى يأتي من التخزين (`storage.get_store().get_stream`) لا من
    القاعدة — فلا قراءةَ بعد الإيداع، ولا معاملةٌ جديدةٌ تُفتح بلا سياق
    RLS في أثناء الإرسال.
    """
    import inspect

    from athera_api.routers import files

    source = inspect.getsource(files.stream_file)
    assert "storage.get_store().get_stream" in source
    # **ومن `return StreamingResponse(` لا من التعليق النوعيّ**: الأوّلُ
    # في النصّ هو `-> StreamingResponse:` في الترويسة، فالقطعُ عليه يشمل
    # المتنَ كلَّه ويجعل الدعوى فارغة.
    stream_call = source.index("return StreamingResponse(")
    after = source[stream_call:]
    assert "session.execute" not in after, "استعلامٌ على الجلسة بعد بناء جواب البثّ"
    assert "await session" not in after


# ══════════════════════════════════════════════════════════════════════
#  ح — مهمّةُ الخلفية بعد إيداعٍ ناجح، ولا تعمل على إيداعٍ أخفق
# ══════════════════════════════════════════════════════════════════════

async def test_11_a_background_task_runs_after_a_successful_commit(two_tenants):
    """الترتيبُ: إيداعٌ ← جوابٌ ← خلفيّة. فالمهمّةُ ترى ما أُودع."""
    import tests.test_at_rc_t1_h1_transaction_integrity as base

    title = f"h1-bg-ok-{uuid.uuid4().hex[:8]}"
    app, marks = _probe_app(two_tenants["a"], second_session=False, background=True)
    async with _probe_client(app) as http:
        response = await http.post("/probe", params={"title": title})
    assert response.status_code == 200, response.text
    assert marks.get("background_ran") is True, "لم تعمل مهمّةُ الخلفية"
    assert await base._project_rows(title) == 1


async def test_12_a_background_task_is_suppressed_when_the_commit_fails(two_tenants):
    """**وإيداعٌ يُخفق يُلغي المهمّة** — فلا عملٌ على طفرةٍ لم تقع.

    والسببُ بنيويّ: الإيداعُ يقع قبل `await response(...)`، ومهامُّ
    الخلفية تعمل **داخل** إرسال الجواب. فرفعُ الإخفاق يمنع الإرسالَ
    ومعه المهمّة.
    """
    import tests.test_at_rc_t1_h1_transaction_integrity as base

    title = f"h1-bg-fail-{uuid.uuid4().hex[:8]}"
    app, marks = _probe_app(two_tenants["a"], second_session=False, background=True)
    await _plant_bomb_on("research_projects", "athera_h1_bg_bomb")
    try:
        async with _probe_client(app) as http:
            response = await http.post("/probe", params={"title": title})
    finally:
        await _remove_bomb_on("research_projects", "athera_h1_bg_bomb")

    assert response.status_code >= 400, response.text
    assert marks.get("background_ran") is not True, (
        "عملت مهمّةُ الخلفية على طفرةٍ أخفق إيداعُها")
    assert await base._project_rows(title) == 0
