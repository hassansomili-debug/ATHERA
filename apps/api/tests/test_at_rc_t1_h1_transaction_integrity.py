"""RC-T1-H1 — **جوابُ النجاح يعني أنّ الإيداع وقع** | commit-before-response.

## العطب

تبعيّاتُ الجلسة ذاتُ `yield` تُودِع معاملتَها في فكِّ حزمةِ الطلب، و
FastAPI يفكّها **بعد** أن يُرسل الجوابَ إلى العميل
(`fastapi/routing.py`): `response = await f(request)` ثمّ
`await response(scope, receive, send)` ثمّ تُفكّ `request_stack`.

فكلُّ مسارٍ يكتب عبر `Depends(get_session)` يقول «تمّ» ثمّ يُودِع. وإن
أخفق الإيداعُ بعد ذلك فلا سبيلَ إلى إبلاغ العميل: **قد قيل له تمّ**.

## ولمَ إخفاقُ إيداعٍ حقيقيٌّ لا مُحاكاة

الحدُّ المفحوصُ هو حدُّ المعاملة نفسُه؛ فلو زُيّف `commit()` بمُرقِّعٍ
لَفُحص المُرقِّعُ لا الحد. فيُزرع **قيدٌ مؤجَّل** في القاعدة:
`CONSTRAINT TRIGGER … DEFERRABLE INITIALLY DEFERRED` يرفع خطأً عند
`COMMIT` وحده. فالإدخالُ ينجح، والمعالجُ يبني جوابَ نجاح، ثمّ **تُخفق
القاعدةُ عند الإيداع** — وهي بعينها الحالُ التي لا يجوز أن يراها العميلُ
نجاحًا.

**والقيدُ جراحيّ**: يرفع على عنوانٍ واحدٍ بعينه، فلا يمسّ صفًّا آخر ولا
فحصًا آخر يعمل في الحزمة نفسها.

## ما تُثبته هذه الرقعة

  ١ جوابُ الطفرة الناجح لا يُرسَل إلّا بعد إيداعٍ ناجح.
  ٢ وإخفاقُ الإيداع يصل العميلَ خطأً مُصنَّفًا لا نجاحًا.
  ٣ ولا يبقى صفٌّ جزئيّ: الرجوعُ كامل.
"""
from __future__ import annotations

import os
import uuid

import pytest

#: عنوانٌ يُفجِّر الإيداعَ — والقيدُ لا يرفع على غيره.
BOMB_TITLE = f"rc-t1-h1-commit-bomb-{uuid.uuid4().hex[:10]}"
SAFE_TITLE = f"rc-t1-h1-control-{uuid.uuid4().hex[:10]}"

PROJECTS = "/api/v1/workspace/projects"

PLANT = """
CREATE OR REPLACE FUNCTION athera_rc_t1_h1_commit_bomb() RETURNS trigger
  LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.working_title_ar = :title THEN
    RAISE EXCEPTION 'RC-T1-H1 regression: commit-time failure planted by the test';
  END IF;
  RETURN NULL;
END $fn$;
"""


async def _owner_session():
    """اتصالُ مالكِ المخطَّط — لزرعِ قيدٍ مؤجَّل وإزالته.

    ولا يُمَسُّ دورُ زمن التشغيل: هذه جلسةٌ تُفتح وتُغلق في الاختبار، ولا
    تدخل مصنعَ جلسات التطبيق.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    url = os.getenv("DATABASE_MIGRATION_URL", "")
    if not url:
        pytest.skip("DATABASE_MIGRATION_URL is not configured")
    engine = create_async_engine(url.replace("+psycopg", "+asyncpg"), poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _plant_commit_bomb(title: str) -> None:
    from sqlalchemy import text

    engine, factory = await _owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "CREATE OR REPLACE FUNCTION athera_rc_t1_h1_commit_bomb()"
                    " RETURNS trigger LANGUAGE plpgsql AS $fn$"
                    " BEGIN"
                    f"   IF NEW.working_title_ar = '{title}' THEN"
                    "     RAISE EXCEPTION 'RC-T1-H1 regression: planted commit-time failure';"
                    "   END IF;"
                    "   RETURN NULL;"
                    " END $fn$"))
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_rc_t1_h1_commit_bomb_trg"
                    " ON research_projects"))
                # **مؤجَّلٌ ابتداءً**: لا يرفع عند الإدخال، بل عند الإيداع.
                await session.execute(text(
                    "CREATE CONSTRAINT TRIGGER athera_rc_t1_h1_commit_bomb_trg"
                    " AFTER INSERT ON research_projects"
                    " DEFERRABLE INITIALLY DEFERRED"
                    " FOR EACH ROW EXECUTE FUNCTION athera_rc_t1_h1_commit_bomb()"))
    finally:
        await engine.dispose()


async def _remove_commit_bomb() -> None:
    from sqlalchemy import text

    engine, factory = await _owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                await session.execute(text(
                    "DROP TRIGGER IF EXISTS athera_rc_t1_h1_commit_bomb_trg"
                    " ON research_projects"))
                await session.execute(text(
                    "DROP FUNCTION IF EXISTS athera_rc_t1_h1_commit_bomb()"))
    finally:
        await engine.dispose()


def _client(slot, locale: str = "ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                               roles=["researcher"], mfa_satisfied=True)
    # **ويُقاس ما وصل العميلَ، لا ما رفعه الخادمُ بعده.**
    #
    # فإخفاقُ الإيداع في البنية القائمة يقع **بعد** إرسال الجواب، فيصعد
    # استثناءً في مكدّس ASGI؛ و`raise_app_exceptions=True` (الافتراض)
    # يرفعه في وجه الفحص فيُخفي الحقيقةَ المقيسة: **أنّ العميل قد أخذ
    # ٢٠١ بالفعل**. فيُطفأ الرفعُ ليُقرأ الجوابُ كما قرأه العميل.
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


async def _project_rows(title: str) -> int:
    """عددُ الصفوف بهذا العنوان — بحقوق المالك، فلا تُخفيه RLS."""
    from sqlalchemy import text

    engine, factory = await _owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                return (await session.execute(text(
                    "SELECT count(*) FROM research_projects"
                    " WHERE working_title_ar = :t"), {"t": title})).scalar_one()
    finally:
        await engine.dispose()


async def test_01_a_control_mutation_still_succeeds(two_tenants):
    """**الحارسُ يقيس شيئًا**: المسارُ نفسُه ينجح بلا قيدٍ مزروع."""
    async with _client(two_tenants["a"]) as http:
        response = await http.post(PROJECTS, json={"title_ar": SAFE_TITLE})
    assert response.status_code == 201, response.text
    assert await _project_rows(SAFE_TITLE) == 1


async def test_02_a_failed_commit_is_never_reported_as_success(two_tenants):
    """**RC-T1-H1 بعينه**: إيداعٌ يُخفق لا يجوز أن يبلغ العميلَ نجاحًا.

    ويسقط هذا الفحصُ على البنية القائمة: الجوابُ ٢٠١ يُرسَل قبل أن
    تُخفق القاعدةُ عند الإيداع.
    """
    await _plant_commit_bomb(BOMB_TITLE)
    try:
        async with _client(two_tenants["a"]) as http:
            response = await http.post(PROJECTS, json={"title_ar": BOMB_TITLE})
    finally:
        await _remove_commit_bomb()

    assert response.status_code >= 400, (
        "المسارُ ردَّ نجاحًا على طفرةٍ أخفق إيداعُها — "
        f"وهذا RC-T1-H1: HTTP {response.status_code} والقاعدةُ رفضت الإيداع. "
        f"body={response.text[:200]}")
    assert response.status_code < 600


async def test_03_a_failed_commit_leaves_no_partial_row(two_tenants):
    """والرجوعُ كامل: لا صفَّ يبقى من طفرةٍ أخفق إيداعُها."""
    title = f"{BOMB_TITLE}-rollback"
    await _plant_commit_bomb(title)
    try:
        async with _client(two_tenants["a"]) as http:
            await http.post(PROJECTS, json={"title_ar": title})
    finally:
        await _remove_commit_bomb()

    assert await _project_rows(title) == 0, "صفٌّ بقي من معاملةٍ أخفق إيداعُها"


# ════════════════════════════════════════════════════════════════════════
#  الإنفاذُ المعماريّ — لا قائمةَ مراجعةٍ بشرية
# ════════════════════════════════════════════════════════════════════════

def test_04_every_api_route_owns_its_commit_through_the_route_class() -> None:
    """**موجّهٌ جديد بلا `TransactionalRoute` يُسقط الحزمة.**

    فالصحّةُ هنا خاصّيّةُ بنيةٍ لا عُرفُ مراجعة: لو أُضيف موجّهٌ غدًا
    بـ`APIRouter(...)` عاديّة لَعادت مساراتُه تُودِع بعد الجواب — بلا أن
    يُخطئ أحدٌ سطرًا. فيُفحص التطبيقُ المُركَّبُ نفسُه لا نصُّ الملفّات.
    """
    from fastapi.routing import APIRoute

    from athera_api.main import app
    from athera_api.transaction import TransactionalRoute

    found: list[APIRoute] = []
    seen: set[int] = set()

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
    assert found, "لم يُكتشف مسارٌ واحد — الماسحُ لا يحرس شيئًا"
    plain = sorted(
        f"{sorted(r.methods)} {r.path}"
        for r in found if not isinstance(r, TransactionalRoute))
    assert not plain, (
        "مساراتٌ لا تملك حدَّ معاملةٍ قبل الجواب (RC-T1-H1):\n" + "\n".join(plain))


def test_05_the_route_class_guard_would_notice_a_plain_router() -> None:
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.** فيُحاكى موجّهٌ عاديّ."""
    from fastapi import APIRouter, FastAPI
    from fastapi.routing import APIRoute

    from athera_api.transaction import TransactionalRoute

    plain = APIRouter(prefix="/forgotten")

    @plain.post("/x")
    async def _x() -> dict:  # pragma: no cover - لا يُستدعى
        return {}

    probe = FastAPI()
    probe.include_router(plain)
    routes = [r for r in plain.routes if isinstance(r, APIRoute)]
    assert routes, "الموجّهُ المُحاكى بلا مسار"
    assert not any(isinstance(r, TransactionalRoute) for r in routes), (
        "الحارسُ لا يفرّق موجّهًا عاديًّا عن المحكوم")


def test_06_the_session_dependencies_do_not_own_the_commit() -> None:
    """ملكيّةُ الإيداع تُقرأ من الشيفرة: التبعيّةُ تُمرّر `owns_commit=False`.

    ويُفحص مع الفحص المعماريّ أعلاه لا بدلًا منه: ذاك يُثبت أنّ الغلافَ
    مُثبَّتٌ، وهذا يُثبت أنّ التبعيّةَ تخلّت عن الإيداع فعلًا — ولو بقيت
    تُودِع لَوقع إيداعٌ مزدوجٌ أو إيداعٌ بعد الجواب.
    """
    import inspect

    from athera_api import deps

    for name in ("get_session", "get_project_session"):
        src = inspect.getsource(getattr(deps, name))
        assert "owns_commit=False" in src, f"{name} ما زالت تملك الإيداع"
        assert "register_request_session" in src, f"{name} لا تُسجّل جلستَها"


# ════════════════════════════════════════════════════════════════════════
#  ذرّيّةُ التدقيق، وإعادةُ المحاولة
# ════════════════════════════════════════════════════════════════════════

async def _audit_rows(action: str) -> int:
    from sqlalchemy import text

    engine, factory = await _owner_session()
    try:
        async with factory() as session:
            async with session.begin():
                return (await session.execute(text(
                    "SELECT count(*) FROM audit_events WHERE action = :a"),
                    {"a": action})).scalar_one()
    finally:
        await engine.dispose()


async def test_07_audit_rolls_back_with_the_mutation_it_describes(two_tenants):
    """**والتدقيقُ لا ينجو من رجوعٍ**: سطرٌ يصف طفرةً لم تقع كذبةٌ محفوظة."""
    title = f"{BOMB_TITLE}-audit"
    before = await _audit_rows("workspace.project_created")
    await _plant_commit_bomb(title)
    try:
        async with _client(two_tenants["a"]) as http:
            response = await http.post(PROJECTS, json={"title_ar": title})
    finally:
        await _remove_commit_bomb()

    assert response.status_code >= 400
    after = await _audit_rows("workspace.project_created")
    assert after == before, (
        "بقي سطرُ تدقيقٍ لطفرةٍ أخفق إيداعُها — والتدقيقُ في المعاملة نفسها")


async def test_08_a_retry_after_a_failed_commit_writes_exactly_one_row(two_tenants):
    """وإعادةُ المحاولة بعد إخفاقٍ تكتب صفًّا واحدًا لا صفرًا ولا اثنين."""
    title = f"rc-t1-h1-retry-{uuid.uuid4().hex[:8]}"
    await _plant_commit_bomb(title)
    try:
        async with _client(two_tenants["a"]) as http:
            first = await http.post(PROJECTS, json={"title_ar": title})
    finally:
        await _remove_commit_bomb()
    assert first.status_code >= 400
    assert await _project_rows(title) == 0

    async with _client(two_tenants["a"]) as http:
        second = await http.post(PROJECTS, json={"title_ar": title})
    assert second.status_code == 201, second.text
    assert await _project_rows(title) == 1


# ════════════════════════════════════════════════════════════════════════
#  سياقُ المستأجر والفاعل لا يتسرّب عبر اتصالٍ معادِ الاستعمال
# ════════════════════════════════════════════════════════════════════════

async def test_09_tenant_context_does_not_leak_to_a_later_session(two_tenants):
    """**`SET LOCAL` يموت مع المعاملة** — ولو انتقلت ملكيّةُ الإيداع.

    وهذا هو الخطرُ الذي يستحقّ فحصًا بعد إعادة بناء حدِّ المعاملة: لو
    ضُبط السياقُ بلا `true` أو أُودع خارج المعاملة لَبقي على الاتصال،
    فرأى الطلبُ التالي — أو مهمّةُ خلفيةٍ — صفوفَ مستأجرٍ آخر.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    title = f"rc-t1-h1-leak-{uuid.uuid4().hex[:8]}"
    async with _client(two_tenants["a"]) as http:
        created = await http.post(PROJECTS, json={"title_ar": title})
    assert created.status_code == 201, created.text

    # جلسةٌ بلا مستأجرٍ ولا فاعل — على المجمَّع نفسِه.
    async with tenant_session(None, None) as session:
        tenant = (await session.execute(
            text("SELECT current_setting('app.tenant_id', true)"))).scalar_one()
        actor = (await session.execute(
            text("SELECT current_setting('app.actor_id', true)"))).scalar_one()
        visible = (await session.execute(
            text("SELECT count(*) FROM research_projects"
                 " WHERE working_title_ar = :t"), {"t": title})).scalar_one()

    assert tenant in (None, ""), f"سياقُ المستأجر تسرّب: {tenant!r}"
    assert actor in (None, ""), f"سياقُ الفاعل تسرّب: {actor!r}"
    assert visible == 0, "صفُّ مستأجرٍ ظهر لجلسةٍ بلا سياق — RLS انتقضت"


async def test_10_a_failed_commit_also_leaves_no_context_behind(two_tenants):
    """وإخفاقُ الإيداع لا يُبقي سياقًا على الاتصال الراجع إلى المجمَّع."""
    from sqlalchemy import text

    from athera_api.db import tenant_session

    title = f"{BOMB_TITLE}-ctx"
    await _plant_commit_bomb(title)
    try:
        async with _client(two_tenants["a"]) as http:
            await http.post(PROJECTS, json={"title_ar": title})
    finally:
        await _remove_commit_bomb()

    async with tenant_session(None, None) as session:
        tenant = (await session.execute(
            text("SELECT current_setting('app.tenant_id', true)"))).scalar_one()
    assert tenant in (None, ""), f"سياقٌ بقي بعد إيداعٍ أخفق: {tenant!r}"
