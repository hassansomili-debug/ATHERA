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
async def test_the_whole_identity_path_works_under_the_non_bypassing_role(db_ready):
    """تسجيل ثم دخول ثم تجديد — عبر HTTP، بدورٍ **لا يتجاوز RLS**.

    وهو ما لم يُختبر قط: كل الاختبارات تفتح جلساتها بسياق مستأجر جاهز، فلم
    يمرّ أحدها بالقراءة السابقة للمصادقة. فسقط الدخول كليًّا أول مرة عمل
    فيها الإنتاج بدوره المقصود — عطبٌ كان يخفيه التجاوز نفسه.

    والمسار الثلاثة مجتمعة مقصود: التسجيل يكتب `roles` و`memberships`
    وسجل التدقيق، والدخول يقرأ العضوية، والتجديد يقرأ `refresh_tokens` —
    وكلها مملوكة لمستأجر ويُلمس بعضها قبل أن يُعرف.

    ولا يصلح مستخدمو `two_tenants` هنا: عناوينهم على `.test`، وهو نطاق
    محجوز يرفضه العقد. فالتسجيل يصنع هوية حقيقية يقبلها المسار نفسه.
    """
    import httpx

    from athera_api.main import app

    slug = f"sec-{uuid.uuid4().hex[:10]}"
    email = f"{slug}@example.com"
    password = "correct-horse-battery-staple"  # noqa: S105 — قيمة اختبار

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        registered = await client.post("/api/v1/auth/register", json={
            "email": email, "password": password,
            "full_name_ar": "باحث أمني", "tenant_slug": slug})
        assert registered.status_code == 201, registered.text

        signed_in = await client.post("/api/v1/auth/login", json={
            "email": email, "password": password})
        assert signed_in.status_code == 200, signed_in.text
        tokens = signed_in.json()
        assert tokens["access_token"] and tokens["refresh_token"]

        refreshed = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]})
        assert refreshed.status_code == 200, refreshed.text

        # وطلبٌ مصادَق يمرّ بسياق مستأجر حقيقي.
        me = await client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {refreshed.json()['access_token']}"})
        assert me.status_code == 200, me.text
        assert me.json()["email"] == email
        assert "researcher" in me.json()["roles"]


@requires_db
@pytest.mark.asyncio
async def test_an_unknown_account_is_refused_the_same_way(db_ready):
    """يفشل مغلقًا — ولا يفرّق ردّه بين «لا مستخدم» و«لا عضوية»."""
    import httpx

    from athera_api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/auth/login", json={
            "email": f"nobody-{uuid.uuid4().hex[:8]}@example.com",
            "password": "correct-horse-battery-staple"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_credentials"


# ══════════ 4. حارس قاعدة الاختبار: لا تشغيلة على الإنتاج ══════════

# الرابط الحقيقي الذي جرت عليه التشغيلة في 2026-08-31 — بلا كلمة.
PRODUCTION_SHAPE = (
    "postgresql+asyncpg://postgres.ofyabufybofbxwkfalgs:REDACTED"
    "@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
)
CI_SHAPE = "postgresql+asyncpg://athera_app:pw@localhost:5432/athera"


def test_the_guard_refuses_the_exact_production_target_of_the_incident():
    from tests.db_safety import guard

    with pytest.raises(RuntimeError) as err:
        guard({"APP_ENV": "production", "DATABASE_URL": PRODUCTION_SHAPE})
    message = str(err.value)
    # أربع إشارات مستقلة — ولا واحدة تحمل الحكم وحدها.
    for signal in ("APP_ENV=production", "managed-database host",
                   "is not an allowed test host", "is never a test database",
                   "managed-project reference"):
        assert signal in message, signal


def test_the_guard_refuses_production_even_when_app_env_is_not_set():
    """المتغيّر قد يُنسى؛ والمضيف واسم القاعدة لا يُنسيان."""
    from tests.db_safety import guard

    with pytest.raises(RuntimeError):
        guard({"DATABASE_URL": PRODUCTION_SHAPE})


def test_the_guard_refuses_a_bypassrls_url_pointed_at_production():
    """دورٌ يتجاوز RLS موجَّهٌ إلى الإنتاج أسوأ من كل ما سبق."""
    from tests.db_safety import guard

    with pytest.raises(RuntimeError) as err:
        guard({"DATABASE_URL": CI_SHAPE, "ATHERA_TEST_BYPASSRLS_URL": PRODUCTION_SHAPE})
    assert "ATHERA_TEST_BYPASSRLS_URL" in str(err.value)


def test_the_guard_refuses_the_postgres_database_even_on_localhost():
    from tests.db_safety import guard

    with pytest.raises(RuntimeError) as err:
        guard({"DATABASE_URL": "postgresql+asyncpg://athera_app:pw@localhost:5432/postgres"})
    assert "is never a test database" in str(err.value)


def test_the_guard_refuses_what_it_cannot_parse():
    """يفشل مغلقًا: هدفٌ لا يُفهم لا يُفترض أنه بريء."""
    from tests.db_safety import guard

    with pytest.raises(RuntimeError):
        guard({"DATABASE_URL": "not a url at all"})


def test_the_guard_accepts_the_local_and_ci_targets():
    from tests.db_safety import guard

    guard({"DATABASE_URL": CI_SHAPE,
           "DATABASE_MIGRATION_URL":
               "postgresql+psycopg://athera_owner:pw@localhost:5432/athera",
           "MIGRATION_DRILL_URL":
               "postgresql+psycopg://athera_owner:pw@localhost:5432/athera_migration",
           "ATHERA_TEST_BYPASSRLS_URL":
               "postgresql+asyncpg://athera_test_bypass:pw@localhost:5432/athera"})


def test_the_guard_never_prints_a_credential():
    from tests.db_safety import guard

    secret = "sup3r-secret-password"  # noqa: S105 — قيمة اختبار لا سرّ
    url = f"postgresql+asyncpg://postgres.abc:{secret}@x.pooler.supabase.com:6543/postgres"
    with pytest.raises(RuntimeError) as err:
        guard({"DATABASE_URL": url})
    message = str(err.value)
    assert secret not in message
    assert url not in message
    assert "postgres.abc" not in message, "اسم المستخدم كاملًا في الرسالة"


def test_the_guard_has_no_environment_escape_hatch():
    """إضافة مضيفٍ تغييرٌ يُراجَع في المستودع — لا متغيّرَ يُصدَّر في عجلة."""
    import inspect

    from tests import db_safety

    source = inspect.getsource(db_safety)
    for hatch in ("ALLOW_PRODUCTION", "SKIP_DB_GUARD", "FORCE", "_UNSAFE"):
        assert hatch not in source, hatch


def test_the_guard_runs_before_any_fixture():
    """في `pytest_configure` — قبل الجمع، فلا تجهيزة تكتب قبل السؤال."""
    import inspect

    from tests import conftest

    assert hasattr(conftest, "pytest_configure")
    source = inspect.getsource(conftest.pytest_configure)
    assert "_guard_test_database()" in source
    assert "UsageError" in source, "الفشل يجب أن يوقف التشغيلة لا اختبارًا"


def test_the_guard_reads_the_url_the_application_actually_uses():
    """ثقب الحادثة نفسه: `.env` من جذر المستودع لا يظهر في البيئة."""
    import inspect

    from tests import db_safety

    source = inspect.getsource(db_safety.guard)
    assert "get_settings().database_url" in source


# ══════════ 5. الاستثناءان الضيّقان — مراجعة أمنية (0018) ══════════

_DEFINERS = ("app_login_tenant", "app_refresh_token_tenant")


@requires_db
@pytest.mark.asyncio
async def test_the_definer_functions_contain_no_dynamic_sql(db_ready):
    """لا `EXECUTE` ولا تركيب نصّ — فلا اسم جدولٍ يأتي من المستدعي."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for name in _DEFINERS:
            body = (await session.execute(text(
                "SELECT prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname='public' AND p.proname = :n"), {"n": name})).scalar_one()
            upper = body.upper()
            for forbidden in ("EXECUTE", "FORMAT(", "QUOTE_IDENT", "||", "SET ROLE"):
                assert forbidden not in upper, f"{name}: {forbidden}"


@requires_db
@pytest.mark.asyncio
async def test_the_definer_functions_are_narrow_and_pinned(db_ready):
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for name in _DEFINERS:
            row = (await session.execute(text(
                "SELECT p.prosecdef, p.provolatile::text, "
                "       pg_get_function_result(p.oid), "
                "       p.proconfig, pg_get_function_arguments(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname='public' AND p.proname = :n"), {"n": name})).one()
            assert row[0] is True, f"{name} is not SECURITY DEFINER"
            assert row[1] == "s", f"{name} is not STABLE"
            # **معرّف واحد** — لا صفّ، ولا SETOF، ولا محتوى.
            assert row[2] == "uuid", f"{name} returns {row[2]}"
            assert any(c.startswith("search_path=") for c in (row[3] or [])), name
            assert "record" not in row[4].lower()


@requires_db
@pytest.mark.asyncio
async def test_only_the_application_role_may_execute_the_definers(db_ready):
    """العامة لا تنفّذ، ولا دورَ غير مقصودٍ يملك التنفيذ."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for signature in ("app_login_tenant(uuid, text)",
                          "app_refresh_token_tenant(text)"):
            assert (await session.execute(text(
                "SELECT has_function_privilege('public', :s, 'EXECUTE')"),
                {"s": signature})).scalar_one() is False, signature
            assert (await session.execute(text(
                "SELECT has_function_privilege('athera_app', :s, 'EXECUTE')"),
                {"s": signature})).scalar_one() is True, signature

            # ولا دور مسجَّل دخول آخر — عدا الخارقين والمالك ودور الاختبار.
            others = (await session.execute(text(
                "SELECT rolname FROM pg_roles WHERE rolcanlogin "
                "  AND NOT rolsuper AND NOT rolbypassrls "
                "  AND rolname NOT IN ('athera_app') "
                "  AND rolname NOT LIKE 'pg\\_%' "
                "  AND has_function_privilege(rolname, :s, 'EXECUTE')"),
                {"s": signature})).scalars().all()
            assert others == [], f"{signature} is executable by {others}"


@requires_db
@pytest.mark.asyncio
async def test_an_unknown_identity_resolves_to_no_tenant(db_ready):
    """يفشل مغلقًا: لا مستأجر افتراضي، ولا أول صفٍّ في الجدول."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        assert (await session.execute(text(
            "SELECT app_login_tenant(:u)"),
            {"u": str(uuid.uuid4())})).scalar_one() is None
        assert (await session.execute(text(
            "SELECT app_refresh_token_tenant(:h)"),
            {"h": uuid.uuid4().hex})).scalar_one() is None


@requires_db
@pytest.mark.asyncio
async def test_a_slug_the_user_does_not_belong_to_resolves_to_nothing(two_tenants):
    """اسم مستأجرٍ ليس للمستخدم فيه عضوية لا يفتح شيئًا."""
    from sqlalchemy import select, text

    from athera_api.db import system_session
    from athera_api.models.identity import Tenant

    a, b = two_tenants["a"], two_tenants["b"]
    async with system_session() as session:
        slug_b = (await session.execute(
            select(Tenant.slug).where(Tenant.id == b["tenant_id"]))).scalar_one()
        resolved = (await session.execute(
            text("SELECT app_login_tenant(:u, :s)"),
            {"u": str(a["user_id"]), "s": slug_b})).scalar_one()
    assert resolved is None, "حُلّ مستأجرٌ لا عضوية للمستخدم فيه"


@requires_db
@pytest.mark.asyncio
async def test_multiple_memberships_never_resolve_to_a_foreign_tenant(two_tenants):
    """الالتباس يُحسم بمستأجرٍ **للمستخدم فيه عضوية** — لا بأيّ مستأجر."""
    from sqlalchemy import select, text

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Role

    a, b = two_tenants["a"], two_tenants["b"]

    # عضوية ثانية حقيقية للمستخدم أ في مستأجر ب.
    async with tenant_session(b["tenant_id"]) as session:
        role_b = (await session.execute(
            select(Role).where(Role.tenant_id == b["tenant_id"],
                               Role.key == "researcher"))).scalar_one()
        session.add(Membership(tenant_id=b["tenant_id"], user_id=a["user_id"],
                               role_id=role_b.id))

    async with system_session() as session:
        resolved = (await session.execute(
            text("SELECT app_login_tenant(:u)"), {"u": str(a["user_id"])})).scalar_one()
    assert resolved in {a["tenant_id"], b["tenant_id"]}

    # وهي عضوية قائمة فعلًا — لا اختيار عشوائي من الجدول.
    #
    # **والتحقق بسياق المستأجر**: `memberships` مملوك، وقراءته بلا سياق تعيد
    # صفرًا — وهو الفشل الآمن نفسه الذي أوقف الدخول، فلا يُقرأ هنا نفيًا.
    async with tenant_session(resolved) as session:
        member = (await session.execute(text(
            "SELECT count(*) FROM memberships WHERE user_id = :u AND tenant_id = :t"),
            {"u": str(a["user_id"]), "t": str(resolved)})).scalar_one()
    assert member >= 1


def test_login_binds_the_tenant_context_before_any_rls_query():
    """ترتيب لا تفصيل: السياق يُثبَّت ثم تُقرأ الجداول المملوكة."""
    import inspect

    from athera_api.routers import auth

    source = inspect.getsource(auth.login)
    bind = source.index("_bind_tenant(")
    membership = source.index("select(Membership, Role)")
    assert bind < membership, "قراءة العضوية تسبق تثبيت السياق"

    refresh = inspect.getsource(auth.refresh)
    assert refresh.index("_bind_tenant(") < refresh.index("select(RefreshToken)")


def test_no_rls_policy_was_relaxed_to_repair_authentication():
    """الإصلاح استثناءٌ مسمّى — لا سياسةٌ تسمح عند غياب السياق."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3] / "infra" / "db" / "migrations"
    body = (root / "versions" / "0018_login_tenant_resolution.py").read_text()
    upper = body.upper()
    for weakening in ("CREATE POLICY", "ALTER POLICY", "DROP POLICY",
                      "DISABLE ROW LEVEL SECURITY", "NO FORCE ROW LEVEL SECURITY",
                      "GRANT BYPASSRLS", "ALTER ROLE"):
        assert weakening not in upper, weakening
    # ونمط الفشل المفتوح بعينه: «اسمح حين لا سياق» — وهو ما كان سيجعل كل
    # مسارٍ نُسي فيه الضبط يرى كل شيء.
    assert "APP_CURRENT_TENANT() IS NULL" not in upper
    assert "REVOKE ALL ON FUNCTION" in body
    assert "GRANT EXECUTE ON FUNCTION" in body


# ══════════ 6. فصل التطوير عن الإنتاج — الطبقة الثانية ══════════

def test_the_target_classifier_reads_the_production_shape():
    from athera_api.dbtarget import parse

    target = parse(PRODUCTION_SHAPE)
    assert target is not None
    assert target.looks_managed and not target.is_local
    assert target.managed_marker == "supabase.com"
    assert target.carries_project_reference
    assert target.describe() == "aws-0-ap-south-1.pooler.supabase.com/postgres"


def test_the_target_classifier_reads_a_local_shape():
    from athera_api.dbtarget import parse

    target = parse(CI_SHAPE)
    assert target is not None
    assert target.is_local and not target.looks_managed
    assert target.managed_marker is None
    assert not target.carries_project_reference


def test_an_unrecognised_host_is_treated_as_managed_not_local():
    """يفشل مغلقًا: مضيفٌ لا نعرفه يُعامَل بعيدًا لا محليًّا."""
    from athera_api.dbtarget import parse

    target = parse("postgresql+asyncpg://u:p@db.example.org:5432/athera")
    assert target is not None
    assert target.looks_managed


def test_the_classifier_describe_carries_no_credential():
    from athera_api.dbtarget import parse

    secret = "sup3r-secret-password"  # noqa: S105 — قيمة اختبار لا سرّ
    target = parse(f"postgresql://postgres.abc:{secret}@x.pooler.supabase.com:6543/postgres")
    assert target is not None
    described = target.describe()
    assert secret not in described
    assert "postgres.abc" not in described


def test_the_startup_guard_refuses_a_managed_target_outside_production():
    """تشغيل الـAPI محليًّا بسياق صدفةٍ منسيّ لا يبلغ قاعدة الإنتاج.

    حارس الاختبارات يحمي `pytest` وحده؛ وهذا يحمي كل عملية تفتح محرّكًا.
    """
    import inspect

    from athera_api import db

    source = inspect.getsource(db._refuse_production_outside_production)
    assert 'app_env.strip().lower() == "production"' in source
    assert "looks_managed" in source
    assert "raise RuntimeError" in source

    # ويُستدعى عند الاستيراد — لا يبقى دالةً لا ينادي عليها أحد.
    module = inspect.getsource(db)
    assert "\n_refuse_production_outside_production()\n" in module


def test_the_startup_guard_is_reached_before_the_engine_is_created():
    """الترتيب هو الحارس: الرفض قبل `create_async_engine` لا بعده."""
    import inspect

    from athera_api import db

    source = inspect.getsource(db)
    assert (source.index("\n_refuse_production_outside_production()\n")
            < source.index("engine = create_async_engine"))


def test_the_test_guard_and_the_startup_guard_share_one_classifier():
    """جوابٌ واحد في موضع واحد — لا نسختان تفترقان بأول تعديل."""
    import inspect

    from athera_api import dbtarget
    from tests import db_safety

    assert db_safety.ALLOWED_HOSTS is dbtarget.LOCAL_HOSTS
    assert db_safety.MANAGED_HOST_MARKERS is dbtarget.MANAGED_HOST_MARKERS
    assert "parse_target" in inspect.getsource(db_safety.parse)


# ══════════ 7. أمر ترحيل الإنتاج — نيّة موجبة وهدف مُتحقَّق منه ══════════

def _migrate_script() -> str:
    import pathlib

    return (pathlib.Path(__file__).resolve().parents[3]
            / "scripts" / "migrate_production.py").read_text()


def test_the_production_migration_command_demands_a_typed_reference():
    source = _migrate_script()
    assert '"--confirm", required=True' in source
    assert "args.confirm != reference" in source


def test_the_production_migration_command_refuses_a_local_target():
    """أمر الإنتاج لا يُشغَّل سهوًا على قاعدة تطوير."""
    source = _migrate_script()
    assert "if not target.looks_managed:" in source
    assert "use `make migrate` for local development" in source


def test_the_production_migration_command_refuses_the_runtime_role():
    """اعتماد الترحيل لا يصير `DATABASE_URL` — ولا العكس."""
    source = _migrate_script()
    assert 'RUNTIME_ROLE = "athera_app"' in source
    assert "== RUNTIME_ROLE" in source


def test_the_migration_credential_file_is_never_loaded_implicitly():
    """`Settings` تقرأ `.env` وحده — فملف الترحيل لا يُحمَّل بأي أمر عادي."""
    import inspect

    from athera_api.config import Settings

    assert Settings.model_config["env_file"] == ".env"
    assert ".env.production" not in inspect.getsource(Settings)

    source = _migrate_script()
    assert '.env.production.migration' in source


def test_the_repository_template_documents_the_separation():
    import pathlib

    template = (pathlib.Path(__file__).resolve().parents[3] / ".env.example").read_text()
    assert "APP_ENV=development" in template
    assert "make migrate-prod" in template

    # ولا هدف إنتاجي في القالب — يُفحص كل رابط لا يُبحث عن كلمة، فذكرُ
    # مزوّدٍ في شرحٍ ليس اعتمادًا.
    from athera_api.dbtarget import parse

    for line in template.splitlines():
        if line.strip().startswith("#") or "://" not in line:
            continue
        target = parse(line.partition("=")[2].strip())
        if target is None or not target.host:
            continue
        assert target.is_local, f"the template points at {target.describe()}"


# ══════════ 8. S5E — العزل من أول يوم لا بعد تسريب ══════════

async def _seed_manuscript_for(tid, uid):
    """مخطوطة بنسخة وقسم — للمستأجر المالك."""
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.publishing import Manuscript, ManuscriptSection, ManuscriptVersion

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="مشروع مخطوطة")
        session.add(project)
        await session.flush()
        row = Manuscript(tenant_id=tid, project_id=project.id,
                         title_ar="سرٌّ لا يخرج من مستأجره", language="ar", status="draft")
        session.add(row)
        await session.flush()
        version = ManuscriptVersion(
            tenant_id=tid, manuscript_id=row.id, version_label=f"v{uuid.uuid4().hex[:6]}",
            created_by=uid, change_reason_ar="إنشاء أولي")
        session.add(version)
        await session.flush()
        session.add(ManuscriptSection(
            tenant_id=tid, version_id=version.id, section_key="method",
            text_ar="استخدمت الدراسة المنهج شبه التجريبي بتصميم المجموعتين"))
        return row.id


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_read_tenant_a_manuscript_without_rls(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.routers import publishing

    a, b = two_tenants["a"], two_tenants["b"]
    manuscript_a = await _seed_manuscript_for(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound) as err:
                await publishing.readiness(manuscript_a, principal=_principal(b),
                                           session=session)
            assert err.value.code == "publishing.manuscript_not_found"


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_list_tenant_a_manuscripts_without_rls(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.routers import publishing

    a, b = two_tenants["a"], two_tenants["b"]
    manuscript_a = await _seed_manuscript_for(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            rows = await publishing.list_manuscripts(principal=_principal(b), session=session)
    assert manuscript_a not in {row.id for row in rows}


@requires_db
@pytest.mark.asyncio
async def test_tenant_b_cannot_write_a_section_into_tenant_a_manuscript(two_tenants):
    """الكتابة العابرة — والرفض **قبل** أي تعديل لا بعده."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.errors import NotFound
    from athera_api.models.publishing import ManuscriptSection, ManuscriptVersion
    from athera_api.routers import publishing
    from athera_api.schemas.publishing import SectionUpsertRequest

    a, b = two_tenants["a"], two_tenants["b"]
    manuscript_a = await _seed_manuscript_for(a["tenant_id"], a["user_id"])

    async def _sections() -> int:
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            return (await session.execute(
                select(func.count(ManuscriptSection.id))
                .join(ManuscriptVersion, ManuscriptVersion.id == ManuscriptSection.version_id)
                .where(ManuscriptVersion.manuscript_id == manuscript_a))).scalar_one()

    before = await _sections()
    async with bypassing_rls():
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            with pytest.raises(NotFound):
                await publishing.upsert_section(
                    manuscript_a,
                    SectionUpsertRequest(section_key="results", text_ar="نتيجة مدسوسة"),
                    principal=_principal(b), session=session)
    assert await _sections() == before, "قسمٌ كُتب في مخطوطة مستأجر آخر"


@requires_db
@pytest.mark.asyncio
async def test_the_owning_tenant_still_reads_its_manuscript_without_rls(two_tenants):
    """الضابط الموجب: الفلترة تمنع الغريب ولا تمنع صاحب الحق."""
    from athera_api.db import tenant_session
    from athera_api.routers import publishing

    a = two_tenants["a"]
    manuscript_a = await _seed_manuscript_for(a["tenant_id"], a["user_id"])

    async with bypassing_rls():
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            result = await publishing.readiness(manuscript_a, principal=_principal(a),
                                                session=session)
            assert result.sections_checked >= 1
            rows = await publishing.list_manuscripts(principal=_principal(a), session=session)
    assert manuscript_a in {row.id for row in rows}


def test_every_manuscript_lookup_constrains_the_tenant():
    """فحصٌ بنيوي — يعمل في كل بيئة، ويلتقط الانحدار عند كتابته."""
    import ast
    import pathlib
    import re

    source = (pathlib.Path(__file__).resolve().parents[1]
              / "athera_api" / "routers" / "publishing.py")
    offenders = []
    for node in ast.walk(ast.parse(source.read_text())):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "where"):
            continue
        clause = ast.unparse(node)
        if "tenant_id" in clause or "Manuscript" not in clause:
            continue
        if re.search(r"\.(id|_id)\s*==", clause):
            offenders.append(f"{node.lineno}: {clause[:90]}")
    assert offenders == [], offenders


def test_the_manuscript_gate_checks_both_id_and_tenant():
    import inspect

    from athera_api.routers import publishing

    source = inspect.getsource(publishing.manuscript_for_tenant)
    assert "Manuscript.id == manuscript_id" in source
    assert "Manuscript.tenant_id == principal.tenant_id" in source


# ══════════ 8. المكتبة تعرض ملفات الباحث — وملفاته وحده ══════════

def test_the_library_listing_is_scoped_to_the_tenant():
    """**مسارٌ لم يكن موجودًا**، فكانت المكتبة لا تعرض ملفًا رفعه صاحبها.

    ويُضاف بالبوابتين معًا من أول سطر: RLS، وفلترةٌ صريحة بالمستأجر — درسُ
    حادثة P0 يُطبَّق قبل التسريب لا بعده.

    وقد انتقل حسابُ حال المعالجة إلى `services/workspace.file_processing_state`
    ليقرأه المكتبة ومساحة العمل معًا. فيُتتبَّع الشرط إلى موضعه الجديد **ولا
    يُحذف**: قائمةُ الملفات تبقى مفلترة بمستأجرها، والحسابُ المشترك يفلتر
    بمستأجره في كل استعلام فيه.
    """
    import inspect

    from athera_api.routers import files
    from athera_api.services import workspace

    listing = inspect.getsource(files.list_files)
    assert "File.tenant_id == principal.tenant_id" in listing

    shared = inspect.getsource(workspace.file_processing_state)
    for scoped in ("Thesis.tenant_id == tenant_id",
                   "ExtractionRun.tenant_id == tenant_id",
                   "FactCandidate.tenant_id == tenant_id"):
        assert scoped in shared, scoped


def test_no_caller_recomputes_the_processing_state_beside_the_shared_one():
    """حسابان لحالٍ واحدة يفترقان بأول تعديل — والباحث يرى شاشتين تتناقضان.

    وهذا وجهٌ آخر من الدرس المتكرر: ما يُكتب بجانب سجلّه بدل أن يُشتقّ منه.
    فيُمنع أن يستعلم أي مسار عن `ExtractionRun` ليخترع الحال لنفسه.
    """
    import inspect

    from athera_api.routers import files
    from athera_api.routers import workspace as workspace_router

    for func in (files.list_files, workspace_router.project_files):
        source = inspect.getsource(func)
        assert "ExtractionRun" not in source, (
            f"{func.__name__} يحسب حال المعالجة بنفسه بدل أن يشتقّها")
        assert "file_processing_state" in source


def test_the_library_never_claims_a_file_was_analysed():
    """الحالة تُقرأ من تشغيلة استخراج حقيقية، ولا تُخترع متفائلة."""
    import inspect

    from athera_api.services import workspace

    source = inspect.getsource(workspace.file_processing_state)
    assert '"not_processed"' in source
    assert "run.status" in source
    # ولا حالة ثابتة تُكتب بجانب الواقع.
    assert '"analyzed"' not in source and '"processed" if' not in source
