"""P0 — عزل المستأجرين حين تسقط RLS | tenant isolation when RLS is bypassed.

**الملف الذي كان يجب أن يوجد قبل الحادثة.**

كل سياسات RLS كانت مفعَّلة ومفروضة، وكل اختبارات العزل كانت خضراء — ومع ذلك
قرأ مستأجرٌ في الإنتاج فرصَ آخر وخيطه وهيكله، وردّ قراره بـ200. لأن
الاختبارات كلها تعمل بدور `athera_app` الذي **لا** يتجاوز RLS، فكانت القاعدة
ترشّح نيابةً عن التطبيق وتخفي أن التطبيق لا يرشّح شيئًا. طبقةٌ واحدة تُختبر
بنفسها تبدو طبقتين.

فهذا الملف يعمل بدورٍ يحمل `BYPASSRLS` عمدًا — في قاعدة الاختبار وحدها —
ويسأل السؤال الذي لم يُسأل: **لو سقطت القاعدة، هل يمنع التطبيق؟**

ولا يُستبدل بذلك RLS ولا تُرخى: الطبقتان تبقيان، وكلٌّ تُختبر وحدها.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import os
import uuid

import pytest

from tests.conftest import requires_db

BYPASS_URL_ENV = "ATHERA_TEST_BYPASSRLS_URL"


# ══════════ 1. حارس حال الدور — بلا قاعدة ══════════

def test_a_superuser_role_is_never_ready():
    from athera_api.services.db_posture import RolePosture

    assert not RolePosture("postgres", True, False).safe
    assert not RolePosture("postgres", False, True).safe
    assert not RolePosture("postgres", True, True).safe


def test_the_intended_application_role_is_ready():
    from athera_api.services.db_posture import RolePosture

    assert RolePosture("athera_app", False, False).safe


def test_the_posture_detail_names_the_flag_and_carries_no_secret():
    """التشخيص للسجل الداخلي — وفيه سبب الرفض لا بيانات اتصال."""
    from athera_api.services.db_posture import RolePosture

    detail = RolePosture("postgres", False, True).detail()
    assert "rolbypassrls" in detail
    assert "rolsuper" not in detail
    for leak in ("password", "postgresql://", "@", ":6543"):
        assert leak not in detail, leak


@pytest.mark.asyncio
async def test_readiness_is_refused_on_a_role_that_bypasses_rls(monkeypatch):
    """الجهوزية تفشل مغلقةً — فتغيير سرٍّ إلى دورٍ متجاوز يُسقط النشر.

    وهذا هو الضمان الذي لم يكن موجودًا: الرابط تغيّر إلى دورٍ متجاوز، وقال
    `/readyz` «جاهز» طوال الوقت.
    """
    from athera_api.errors import AtheraError
    from athera_api.routers import health
    from athera_api.services import db_posture

    async def unsafe(_engine):
        return db_posture.RolePosture("postgres", False, True)

    monkeypatch.setattr(db_posture, "inspect", unsafe)
    with pytest.raises(AtheraError) as err:
        await health.readyz(locale="ar")
    assert err.value.status_code == 503
    assert err.value.code == "readiness.database_role_unsafe"


@pytest.mark.asyncio
async def test_readiness_is_refused_on_a_superuser_role(monkeypatch):
    from athera_api.errors import AtheraError
    from athera_api.routers import health
    from athera_api.services import db_posture

    async def unsafe(_engine):
        return db_posture.RolePosture("postgres", True, False)

    monkeypatch.setattr(db_posture, "inspect", unsafe)
    with pytest.raises(AtheraError) as err:
        await health.readyz(locale="ar")
    assert err.value.status_code == 503


@pytest.mark.asyncio
async def test_readiness_passes_on_the_safe_application_role(monkeypatch):
    from athera_api.routers import health
    from athera_api.services import db_posture

    async def safe(_engine):
        return db_posture.RolePosture("athera_app", False, False)

    monkeypatch.setattr(db_posture, "inspect", safe)
    assert (await health.readyz(locale="ar")).status == "ready"


def test_the_unsafe_reason_is_bilingual():
    from athera_api.i18n.catalog import CATALOG

    entry = CATALOG["readiness.database_role_unsafe"]
    assert entry["ar"] and entry["en"]


# ══════════ 2. الفلترة الصريحة موجودة في المصدر ══════════

def test_every_planning_lookup_constrains_the_tenant():
    """فحصٌ بنيوي: لا استعلام تخطيطٍ يقيّد بالمعرّف وحده.

    السلوكي يحتاج دورًا متجاوزًا؛ وهذا يعمل في كل بيئة، ويلتقط الانحدار
    عند كتابته لا عند استغلاله.
    """
    import ast
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    watched = {
        "routers/planning.py",
        "services/planning/thread.py",
    }
    offenders = []
    for rel in sorted(watched):
        tree = ast.parse((root / rel).read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "where"):
                continue
            clause = ast.unparse(node)
            if "tenant_id" in clause:
                continue
            if re.search(r"\.(id|_id)\s*==", clause):
                offenders.append(f"{rel}:{node.lineno} {clause[:90]}")
    assert offenders == [], offenders


def test_the_canonical_ownership_gate_checks_both_project_and_tenant():
    import inspect

    from athera_api.routers import planning

    source = inspect.getsource(planning._project)
    assert "ResearchProject.id == project_id" in source
    assert "ResearchProject.tenant_id == principal.tenant_id" in source

    opportunity = inspect.getsource(planning._opportunity)
    for required in ("PublicationOpportunity.id == opportunity_id",
                     "PublicationOpportunity.project_id == project_id",
                     "PublicationOpportunity.tenant_id == principal.tenant_id"):
        assert required in opportunity, required


def test_no_planning_route_reads_an_opportunity_outside_the_gate():
    """المسارات تمرّ بالبوابة — ولا استعلام موازٍ يلتف حولها."""
    import inspect

    from athera_api.routers import planning

    # كل مسارٍ يأخذ `project_id` من الطلب يمرّ ببوابة المشروع أولًا.
    for name in ("decide_opportunity", "read_outline", "list_opportunities",
                 "read_thread", "build_thread", "build_outline",
                 "publication_context", "planning_consent",
                 "generate_opportunities"):
        source = inspect.getsource(getattr(planning, name))
        assert "_project(session, principal" in source or "_project(opening" in source, name

    # وكل من يأخذ `opportunity_id` يمرّ ببوابة الفرصة — لا باستعلام موازٍ.
    for name in ("decide_opportunity", "_selected"):
        source = inspect.getsource(getattr(planning, name))
        assert "_opportunity(session, principal" in source, name

    # و`_selected` لا يقرأ الفرصة بنفسه: البوابة واحدة لا نسختان تفترقان.
    selected = inspect.getsource(planning._selected)
    assert "select(PublicationOpportunity)" not in selected


# ══════════ 3. تحت دورٍ يتجاوز RLS ══════════

@contextlib.asynccontextmanager
async def bypassing_rls():
    """يبدّل مصنع الجلسات إلى دورٍ يتجاوز RLS — في قاعدة الاختبار وحدها.

    **ولا تُستعمل هنا بيانات اعتماد إنتاجية بحال.** الدور يُنشأ في CI على
    قاعدة الاختبار، ويُتخطى الاختبار بوضوح حين لا يكون معرَّفًا.
    """
    url = os.getenv(BYPASS_URL_ENV, "")
    if not url:
        pytest.skip(f"{BYPASS_URL_ENV} is not configured (needs a BYPASSRLS test role)")

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from athera_api import db
    from athera_api.services import db_posture

    engine = create_async_engine(url, pool_pre_ping=True)
    original = db.SessionFactory
    try:
        async with engine.connect() as conn:
            posture = await db_posture.read(conn)
        # لو لم يكن الدور متجاوزًا فالاختبار لا يختبر شيئًا — ولا يمرّ صامتًا.
        assert posture.bypasses_rls or posture.is_superuser, (
            f"{BYPASS_URL_ENV} points at a role that does not bypass RLS: "
            f"{posture.detail()} — the suite would prove nothing")
        db.SessionFactory = async_sessionmaker(engine, expire_on_commit=False,
                                               class_=AsyncSession)
        yield
    finally:
        db.SessionFactory = original
        await engine.dispose()


async def _seed_tenant_a(tid, uid):
    """مشروع مستأجر أ كاملًا: أدلة موثقة، فرصة مختارة، خيط، هيكل."""
    from athera_api.db import tenant_session
    from athera_api.models.planning import ManuscriptOutline
    from athera_api.models.thesis import PublicationOpportunity
    from athera_api.services.planning import context as ctx
    from athera_api.services.planning import thread
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    project_id, _memory_id, _file_id = await _seed_project_with_memory(tid, uid)

    async with tenant_session(tid, uid) as session:
        opportunity = PublicationOpportunity(
            tenant_id=tid, project_id=project_id,
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar="سرٌّ لا يخرج من مستأجره",
            research_question_ar="ما أثر البرنامج في التفكير الناقد؟",
            status="discovered", planning_status="selected",
            # القيد `planning_actor` يشترط فاعلًا ووقتًا لكل قرار بشري.
            planning_decided_by=uid, planning_decided_at=_now(),
            readiness_components={"proposal": {"contribution_ar": "مساهمة مقترحة"}},
        )
        session.add(opportunity)
        await session.flush()
        context = await ctx.build(session, tenant_id=tid, project_id=project_id,
                                  capability="publication_planning_external_c2")
        await thread.assemble(session, tenant_id=tid, project_id=project_id,
                              opportunity=opportunity, context=context,
                              actor_user_id=uid)
        session.add(ManuscriptOutline(
            tenant_id=tid, opportunity_id=opportunity.id, project_id=project_id,
            sections=[{"key": "methods", "title_ar": "المنهجية"}], status="draft"))
        return project_id, opportunity.id


def _now():
    return dt.datetime.now(dt.UTC)


def _principal(tenant):
    from athera_api.deps import Principal

    return Principal(user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
                     roles=["researcher"], mfa_satisfied=True, locale="ar")


@requires_db
@pytest.mark.asyncio
async def test_the_bypass_role_really_reproduces_the_old_vulnerability(two_tenants):
    """يثبت أن الأداة صادقة: بشكل الاستعلام القديم يقع التسريب فعلًا.

    ولولا هذا لكانت بقية الملف قد تمرّ لأن الدور لا يتجاوز شيئًا — فيُقال
    إن الثغرة أُغلقت وهي لم تُختبر.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, opportunity_a = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            # **شكل الاستعلام قبل الإصلاح**: المعرّف وحده، والاتّكال على RLS.
            leaked = (await session.execute(
                select(PublicationOpportunity).where(
                    PublicationOpportunity.id == opportunity_a)
            )).scalar_one_or_none()
            assert leaked is not None, (
                "الدور لا يتجاوز RLS فعلًا — الملف كله لا يثبت شيئًا")
            assert leaked.project_id == project_a


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_list_tenant_a_opportunities_without_rls(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import planning

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, _ = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound) as err:
                await planning.list_opportunities(
                    project_a, principal=_principal(b), session=session)
            assert err.value.code == "planning.project_not_found"


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_thread_or_evidence_map(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import planning

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, opportunity_a = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound):
                await planning.read_thread(project_a, opportunity_a,
                                           principal=_principal(b), session=session)


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_outline(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import planning

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, opportunity_a = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound):
                await planning.read_outline(project_a, opportunity_a,
                                            principal=_principal(b), session=session)


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_planning_context(two_tenants):
    """الرفض عند حدّ ملكية المشروع — لا «سياق فارغ» يبدو نجاحًا."""
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import planning

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, _ = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound) as err:
                await planning.publication_context(
                    project_a, principal=_principal(b), session=session)
            assert err.value.code == "planning.project_not_found"


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_decide_tenant_a_opportunity(two_tenants):
    """الكتابة العابرة — وهي ما ردّ الإنتاج عليها بـ200.

    ويُتحقق بعدها أن **لا شيء تغيّر**: الرفض قبل أي تعديل لا بعده.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.models.thesis import PublicationOpportunity
    from athera_api.routers import planning
    from athera_api.schemas.planning import PlanningDecision

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, opportunity_a = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound):
                await planning.decide_opportunity(
                    project_a, opportunity_a,
                    PlanningDecision(decision="exclude", reason="اختطاف"),
                    principal=_principal(b), session=session)

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = (await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_a))).scalar_one()
        assert row.planning_status == "selected", "قرار مستأجر آخر غيّر الحالة"
        assert row.planning_decided_by == a["user_id"], "تبدّل صاحب القرار"


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_generate_against_tenant_a_project(two_tenants):
    """التوليد يُرفض عند الملكية — **قبل** أي نداء مزوّد أو تشغيلة."""
    from athera_api.errors import NotFound
    from athera_api.routers import planning

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, _ = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    calls: list = []
    original = planning.Orchestrator.run_structured_detached

    async def spy(*args, **kwargs):
        calls.append(kwargs)
        return await original(*args, **kwargs)

    planning.Orchestrator.run_structured_detached = spy
    try:
        async with bypassing_rls():
            with pytest.raises(NotFound):
                await planning.generate_opportunities(project_a, principal=_principal(b))
    finally:
        planning.Orchestrator.run_structured_detached = original
    assert calls == [], "استُدعي المزوّد على مشروع مستأجر آخر"


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_reuse_tenant_a_planning_consent(two_tenants):
    """الإذن مقيَّد بمستأجره — ولا يُقرأ لمن لم يُعطه."""
    from athera_api.db import tenant_session
    from athera_api.services import consent
    from athera_api.services.planning import context as ctx

    a, b = two_tenants["a"], two_tenants["b"]
    project_a, _ = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        context = await ctx.build(session, tenant_id=a["tenant_id"], project_id=project_a,
                                  capability=consent.PLANNING_CAPABILITY)
        await consent.record_planning_decision(
            session, tenant_id=a["tenant_id"], project_id=project_a,
            actor_user_id=a["user_id"], granted=True, provider="anthropic", model="m",
            context_fingerprint=context.fingerprint, evidence_count=len(context.items))

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            grant = await consent.planning_authorization(
                session, tenant_id=b["tenant_id"], project_id=project_a,
                context_fingerprint=context.fingerprint)
            assert grant is None
            assert await consent.planning_state(
                session, tenant_id=b["tenant_id"], project_id=project_a,
                context_fingerprint=context.fingerprint) == consent.ABSENT


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_files_or_candidates(two_tenants):
    """S5C أيضًا — العزل ليس خاصية مرحلةٍ واحدة."""
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import files as files_router
    from tests.test_at_s5d_publication_planning import _seed_project_with_memory

    a, b = two_tenants["a"], two_tenants["b"]
    _project, _memory, file_a = await _seed_project_with_memory(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound) as err:
                await files_router.get_file(file_a, principal=_principal(b),
                                            session=session)
            assert err.value.code == "file.not_found"


@requires_db
@pytest.mark.asyncio
async def test_the_owning_tenant_still_reads_everything_without_rls(two_tenants):
    """الضابط الموجب: الفلترة الصريحة تمنع الغريب ولا تمنع صاحب الحق."""
    from athera_api.db import tenant_session
    from athera_api.routers import planning

    a = two_tenants["a"]
    project_a, opportunity_a = await _seed_tenant_a(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            listing = await planning.list_opportunities(
                project_a, principal=_principal(a), session=session)
            assert [o.id for o in listing.opportunities] == [opportunity_a]

            view = await planning.read_thread(project_a, opportunity_a,
                                              principal=_principal(a), session=session)
            assert view.elements, "خريطة الأدلة فرغت لصاحبها"

            outline = await planning.read_outline(project_a, opportunity_a,
                                                  principal=_principal(a), session=session)
            assert outline.sections


@requires_db
@pytest.mark.asyncio
async def test_row_level_security_is_still_enabled_and_forced(db_ready):
    """الطبقة الأولى باقية — والفلترة الصريحة أُضيفت إليها لا بدلًا منها."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            """
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN information_schema.columns col
              ON col.table_name = c.relname AND col.column_name = 'tenant_id'
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND (c.relrowsecurity = false OR c.relforcerowsecurity = false)
            """
        ))).scalars().all()
    assert rows == [], f"RLS is not forced on: {rows}"


@requires_db
@pytest.mark.asyncio
async def test_the_login_tenant_resolver_is_narrow_and_not_public(db_ready):
    """الاستثناء المسمّى: يعيد معرّفًا واحدًا، ولا يُنفَّذ من العامة (0018)."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for name, returns in (("app_login_tenant", "uuid"),
                              ("app_refresh_token_tenant", "uuid")):
            row = (await session.execute(text(
                "SELECT p.prosecdef, pg_get_function_result(p.oid), p.proconfig "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.proname = :name"), {"name": name})).one()
            assert row[0] is True, f"{name} is not SECURITY DEFINER"
            assert row[1] == returns, f"{name} returns {row[1]}, not a bare identifier"
            assert any("search_path=" in c for c in (row[2] or [])), \
                f"{name} has no pinned search_path"

        # ولا تنفيذ عامّ.
        granted = (await session.execute(text(
            "SELECT has_function_privilege('public', 'app_login_tenant(uuid, text)', "
            "'EXECUTE')"))).scalar_one()
        assert granted is False, "app_login_tenant is executable by PUBLIC"


@requires_db
@pytest.mark.asyncio
async def test_login_works_under_the_non_bypassing_application_role(two_tenants):
    """الدخول عبر المسار الحقيقي بدورٍ **لا يتجاوز RLS** — وهو ما لم يُختبر قط.

    الاختبارات كانت تفتح جلساتها بسياق مستأجر جاهز، فلم يمرّ أحدها بالقراءة
    السابقة للمصادقة. فسقط الدخول كليًّا أول مرة عمل فيها الإنتاج بدوره
    المقصود — عطبٌ كان يخفيه التجاوز نفسه.
    """
    import httpx

    from athera_api.main import app
    from athera_api.schemas.auth import LoginRequest  # noqa: F401 — عقد الطلب

    a = two_tenants["a"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": a["email"], "password": "correct-horse-battery-staple"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] and body["refresh_token"]


@requires_db
@pytest.mark.asyncio
async def test_refresh_works_under_the_non_bypassing_application_role(two_tenants):
    """والتجديد كذلك: `refresh_tokens` جدولٌ مملوك لمستأجر يُقرأ قبل سياقه."""
    import httpx

    from athera_api.main import app

    a = two_tenants["a"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/v1/auth/login", json={
            "email": a["email"], "password": "correct-horse-battery-staple"})
        assert login.status_code == 200, login.text
        refreshed = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text


@requires_db
@pytest.mark.asyncio
async def test_registration_works_under_the_non_bypassing_application_role(db_ready):
    """والتسجيل: الأدوار والعضوية وسجل التدقيق كلها مملوكة لمستأجر."""
    import httpx

    from athera_api.main import app

    slug = f"sec-{uuid.uuid4().hex[:10]}"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/register", json={
            "email": f"{slug}@example.test",
            "password": "correct-horse-battery-staple",
            "full_name_ar": "باحث أمني", "tenant_slug": slug})
    assert response.status_code == 201, response.text
