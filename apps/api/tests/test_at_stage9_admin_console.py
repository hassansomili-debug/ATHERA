"""المرحلة ٩ — لوحة الإدارة V1 | Admin Console V1.

## ما يُقاس

- **الحارس**: الأدوارُ الإداريّةُ الأربعةُ تدخل (بسياسة MFA المركزيّة)، والخمسةُ
  الأخرى تُردّ — في كلّ مسار.
- **مستأجرٌ واحد**: مديرُ A لا يرى من B شيئًا — لا صفًّا ولا عددًا ولا تكلفة.
- **`users` جدولٌ عامٌّ بسياسة `global_readwrite`** — فالمرساةُ العضويّة: مستخدمٌ
  لا ينتمي إلّا إلى B لا يظهر لمدير A بمعرّفه ولا ببريده ولا في العدّ.
- **الدقّة**: أعدادٌ ومجاميعُ تطابق صفوفًا مزروعةً بعينها، والتكلفةُ الفارغةُ
  «لم تُسجَّل» لا «صفر».
- **الخصوصيّة**: نصٌّ بحثيٌّ مزروعٌ في الحمولات والأخطاء لا يظهر في أيّ جواب.
- **البنية**: لا حقلَ يشبه سرًّا، ولا طفرة، ولا جلسةَ نظام، ولا N+1.
"""
from __future__ import annotations

import ast
import datetime as dt
import inspect
import json
import pathlib
import re
import uuid
from decimal import Decimal

import pytest

from tests.conftest import requires_db

pytestmark = pytest.mark.asyncio

API = pathlib.Path(__file__).resolve().parents[1]
ADMIN = ("research_admin", "college_admin", "institution_admin", "system_admin")
NON_ADMIN = ("researcher", "student", "co_author", "supervisor", "internal_reviewer")
ENDPOINTS = ("/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/projects",
             "/api/v1/admin/usage", "/api/v1/admin/operations")

#: نصٌّ بحثيٌّ يُزرع في كلّ حمولةٍ وخطأ — ولا يجوز أن يظهر في جوابٍ إداريّ.
RESEARCH_SECRET = "BAYESIAN-HIPPOCAMPUS-COHORT-7731"


# ═════════════════════════════ التجهيز ═════════════════════════════


def _client(slot, *, roles=("system_admin",), mfa=True, locale="ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                               roles=list(roles), mfa_satisfied=mfa)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


async def _member(tenant_id, *, roles=("researcher",), name="عضو", email=None,
                  active=True, last_login_days_ago: int | None = None,
                  since: dt.datetime | None = None) -> dict:
    """حسابٌ بعضويّةٍ لكلّ دور — **والحسابُ في جلسةٍ بلا مستأجر، والعضويّةُ في سياقه**."""
    from sqlalchemy import select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    email = email or f"s9-{uuid.uuid4().hex[:10]}@example.test"
    async with system_session() as session:
        user = User(email=email, password_hash=hash_password("Stage9-Passw0rd!"),
                    full_name_ar=name, full_name_en=f"{name} EN", is_active=active,
                    last_login_at=(dt.datetime.now(dt.UTC)
                                   - dt.timedelta(days=last_login_days_ago))
                    if last_login_days_ago is not None else None)
        session.add(user)
        await session.flush()
        user_id = user.id
    async with tenant_session(tenant_id) as scoped:
        for key in roles:
            role_id = (await scoped.execute(select(Role.id).where(
                Role.tenant_id == tenant_id, Role.key == key))).scalar_one()
            member = Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id)
            if since is not None:
                member.created_at = since
            scoped.add(member)
    return {"tenant_id": tenant_id, "user_id": user_id, "email": email}


async def _project(tenant_id, owner_id, *, title="بحثٌ للفحص", archived=False,
                   trashed=False) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.services import audit

    now = dt.datetime.now(dt.UTC)
    async with tenant_session(tenant_id, owner_id) as session:
        project = ResearchProject(
            tenant_id=tenant_id, working_title_ar=title, status="planned",
            archived_at=now if archived else None,
            deleted_at=now if trashed else None, deleted_by=owner_id if trashed else None)
        session.add(project)
        await session.flush()
        await audit.record(session, tenant_id=tenant_id, action="workspace.project_created",
                           object_type="research_project", object_id=project.id,
                           actor_user_id=owner_id, reason="stage 9 fixture")
        return project.id


async def _file(tenant_id, owner_id, *, size=1000, trashed=False) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.files import File

    async with tenant_session(tenant_id, owner_id) as session:
        row = File(tenant_id=tenant_id, storage_key=f"t/{uuid.uuid4()}",
                   original_filename=f"{RESEARCH_SECRET}.pdf", content_type="application/pdf",
                   size_bytes=size, classification="C2", is_untrusted_content=True,
                   status="stored", uploaded_by=owner_id,
                   trashed_at=dt.datetime.now(dt.UTC) if trashed else None,
                   trashed_by=owner_id if trashed else None)
        session.add(row)
        await session.flush()
        return row.id


async def _runs(tenant_id, requester, specs: list[dict], *, days_ago: int = 0) -> None:
    """تشغيلُ وكيلٍ واحد، وتحته تشغيلاتُ نموذجٍ وأداةٍ — **وفيها النصُّ البحثيّ**."""
    from athera_api.db import tenant_session
    from athera_api.models.runs import AgentRun, ModelRun, ToolRun

    stamp = dt.datetime.now(dt.UTC) - dt.timedelta(days=days_ago)
    async with tenant_session(tenant_id, requester) as session:
        agent = AgentRun(tenant_id=tenant_id, agent_key="stage9.fixture", status="failed",
                         started_at=stamp, finished_at=stamp, requested_by=requester,
                         trace_id=uuid.uuid4(),
                         input_summary={"text": RESEARCH_SECRET},
                         output_summary={"text": RESEARCH_SECRET},
                         error=f"boom {RESEARCH_SECRET}", created_at=stamp)
        session.add(agent)
        await session.flush()
        for spec in specs:
            session.add(ModelRun(
                tenant_id=tenant_id, agent_run_id=agent.id, provider=spec.get("provider", "fake"),
                model=spec.get("model", "m-1"), operation=spec.get("operation", "planning"),
                input_tokens=spec["input"], output_tokens=spec["output"],
                cost_usd=spec.get("cost"), latency_ms=spec.get("latency"),
                status=spec.get("status", "ok"),
                error=f"model said {RESEARCH_SECRET}" if spec.get("status") == "error" else None,
                created_at=stamp))
        session.add(ToolRun(tenant_id=tenant_id, agent_run_id=agent.id, tool_key="search",
                            status="error", duration_ms=12, tool_kind="read",
                            request_payload={"q": RESEARCH_SECRET},
                            response_payload={"hits": [RESEARCH_SECRET]},
                            error=f"tool {RESEARCH_SECRET}", created_at=stamp))


async def _get(slot, url, **kw):
    async with _client(slot, **kw) as http:
        return await http.get(url)


# ═════════════════════════════ ١ · البنية ═════════════════════════════


def _admin_routes():
    from athera_api.main import app

    return {p: ops for p, ops in app.openapi()["paths"].items() if p.startswith("/api/v1/admin")}


def test_01_every_admin_route_is_read_only() -> None:
    """**ولا طفرة في المرحلة ٩** — لا تعطيلَ حسابٍ ولا منحَ دورٍ ولا حذف."""
    routes = _admin_routes()
    assert set(routes) == {
        "/api/v1/admin/overview", "/api/v1/admin/users", "/api/v1/admin/users/{user_id}",
        "/api/v1/admin/projects", "/api/v1/admin/usage", "/api/v1/admin/operations"}
    for path, ops in routes.items():
        assert set(ops) == {"get"}, f"طفرةٌ في لوحة الإدارة: {path} {sorted(ops)}"


def test_02_the_guard_is_the_canonical_admin_set_through_require_roles() -> None:
    from athera_api.routers import admin
    from athera_api.services import rbac

    src = inspect.getsource(admin)
    assert "require_roles(*sorted(rbac.ADMIN_ROLE_KEYS))" in src, \
        "الحارسُ لا يُشتقّ من المصدر القانونيّ"
    assert set(ADMIN) == set(rbac.ADMIN_ROLE_KEYS)
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if isinstance(fn, ast.AsyncFunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "get"
                for d in fn.decorator_list):
            text = ast.unparse(fn)
            assert "Depends(admin_guard)" in text, f"{fn.name}: بلا الحارس الإداريّ"
            assert "tenant_id" not in {a.arg for a in fn.args.args}, \
                f"{fn.name}: يقبل مستأجرًا من الطلب"


def test_03_no_privileged_session_or_credential_in_the_console() -> None:
    """لا `system_session` ولا `BYPASSRLS` ولا مفتاحُ خدمةٍ ولا اتصالُ مالك."""
    for module in ("routers/admin.py", "services/admin_console.py", "schemas/admin.py"):
        code = (API / "athera_api" / module).read_text(encoding="utf-8")
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        code = re.sub(r"#[^\n]*", "", code)
        for forbidden in ("system_session", "BYPASSRLS", "service_role", "migration_url",
                          "database_migration", "owner_url", "bypass"):
            assert forbidden.lower() not in code.lower(), f"{module}: {forbidden}"


_SECRETISH = re.compile(
    r"(password|secret|(^|_)token(_hash)?$|refresh_token|access_token|api_key|"
    r"authorization|credential|database_url|request_payload|response_payload|"
    r"input_summary|output_summary|prompt|^error$|failure_detail|mining_last_error)")


def test_04_no_admin_schema_field_looks_like_a_secret_or_payload() -> None:
    """**`input_tokens` مقياسٌ لا سرّ** — فلا يُتّهم؛ و`token` وحدَه يُتّهم."""
    from pydantic import BaseModel

    from athera_api.schemas import admin as S

    offenders = []
    for name, obj in vars(S).items():
        if inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel:
            for field in obj.model_fields:
                if _SECRETISH.search(field):
                    offenders.append(f"{name}.{field}")
    assert offenders == [], offenders
    assert not _SECRETISH.search("input_tokens") and not _SECRETISH.search("output_tokens")
    assert _SECRETISH.search("password_hash") and _SECRETISH.search("token_hash")


def test_05_no_account_state_or_impersonation_route_exists_anywhere_new() -> None:
    from athera_api.main import app

    for path in app.openapi()["paths"]:
        low = path.lower()
        assert not re.search(r"impersonat|/active$|deactivat|disable|suspend-account", low), path


# ═════════════════════════════ ٢ · الحارس ═════════════════════════════


@requires_db
@pytest.mark.parametrize("role", NON_ADMIN)
async def test_06_non_admin_roles_are_refused_everywhere(two_tenants, role):
    slot = two_tenants["a"]
    async with _client(slot, roles=(role,)) as http:
        for url in (*ENDPOINTS, f"/api/v1/admin/users/{slot['user_id']}"):
            answer = await http.get(url)
            assert answer.status_code == 403, f"{role} قرأ {url}: {answer.status_code}"
            assert "items" not in answer.text and "member_count" not in answer.text


@requires_db
@pytest.mark.parametrize("role", ADMIN)
async def test_07_every_admin_role_enters_with_mfa(two_tenants, role):
    slot = two_tenants["a"]
    for url in ENDPOINTS:
        answer = await _get(slot, url, roles=(role,))
        assert answer.status_code == 200, f"{role} {url}: {answer.text[:200]}"


@requires_db
async def test_08_admin_without_mfa_follows_the_central_policy(two_tenants, monkeypatch):
    from athera_api.config import get_settings

    slot = two_tenants["a"]
    monkeypatch.setattr(get_settings(), "mfa_required_for_admin_roles", True, raising=False)
    refused = await _get(slot, "/api/v1/admin/overview", roles=("system_admin",), mfa=False)
    assert refused.status_code == 401 and \
        refused.json()["error"]["code"] == "auth.mfa_required", refused.text

    monkeypatch.setattr(get_settings(), "mfa_required_for_admin_roles", False, raising=False)
    allowed = await _get(slot, "/api/v1/admin/overview", roles=("system_admin",), mfa=False)
    assert allowed.status_code == 200, allowed.text


# ═════════════════════════════ ٣ · الدقّة ═════════════════════════════


@requires_db
async def test_09_overview_counts_are_exact_and_tenant_bound(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    # شخصٌ بدورين ⇒ **شخصٌ واحد**. وآخرُ معطَّل، وثالثٌ دخل قبل ٤٠ يومًا.
    twice = await _member(a["tenant_id"], roles=("researcher", "supervisor"),
                          last_login_days_ago=2)
    await _member(a["tenant_id"], active=False, last_login_days_ago=40)
    await _member(b["tenant_id"], roles=("researcher", "co_author"), last_login_days_ago=1)

    await _project(a["tenant_id"], a["user_id"])
    await _project(a["tenant_id"], a["user_id"], archived=True)
    await _project(a["tenant_id"], twice["user_id"], trashed=True)
    await _project(b["tenant_id"], b["user_id"])

    await _file(a["tenant_id"], a["user_id"], size=1500)
    await _file(a["tenant_id"], twice["user_id"], size=2500)
    await _file(a["tenant_id"], a["user_id"], size=9999, trashed=True)
    await _file(b["tenant_id"], b["user_id"], size=777_777)

    await _runs(a["tenant_id"], a["user_id"], [
        {"input": 100, "output": 30, "cost": Decimal("0.12")},
        {"input": 200, "output": 50, "cost": None},
        {"input": 50, "output": 10, "cost": Decimal("0.04"), "status": "error"},
        {"input": 7, "output": 3, "cost": None, "status": "ambiguous"},
    ])
    await _runs(a["tenant_id"], a["user_id"], [{"input": 9999, "output": 9999,
                                                 "cost": Decimal("9")}], days_ago=40)
    await _runs(b["tenant_id"], b["user_id"], [{"input": 5555, "output": 5555,
                                                 "cost": Decimal("5")}])

    got = (await _get(a, "/api/v1/admin/overview")).json()
    assert got["scope"]["tenant_id"] == str(a["tenant_id"])
    assert got["scope"]["current_admin_roles"] == ["system_admin"]
    assert got["users"] == {"member_count": 3, "active_identity_count": 2,
                            "signed_in_7d": 1, "signed_in_30d": 1}, got["users"]
    assert got["projects"] == {"total": 2, "active": 1, "archived": 1, "trashed": 1}
    assert got["files"] == {"total": 2, "total_bytes": 4000, "trashed": 1, "pending": 0}
    ai = got["ai"]
    assert (ai["model_runs"], ai["succeeded"], ai["failed"], ai["ambiguous"]) == (4, 2, 1, 1)
    assert (ai["input_tokens"], ai["output_tokens"]) == (357, 93), "أرقامُ مستأجرٍ آخر أو خارج النافذة"
    assert Decimal(str(ai["recorded_cost_usd"])) == Decimal("0.16")
    assert (ai["runs_with_cost"], ai["runs_without_cost"]) == (2, 2)
    assert got["operations"]["failed_agent_runs"] == 1  # الأربعين يومًا خارج النافذة
    assert got["operations"]["failed_tool_runs"] == 1
    assert got["audit"]["latest_seq"] is not None


@requires_db
async def test_10_usage_matches_seeded_runs_and_null_cost_is_not_zero(two_tenants):
    """المثالُ بعينه: ١٠٠/٣٠/٠٫١٢ · ٢٠٠/٥٠/— · ٥٠/١٠/٠٫٠٤ فاشل.

    والحالُ «فاشل» في المصدر `error` (الموجِّهُ يكتب `ok`/`error`، والمنسّقُ
    `ambiguous`) — فيُزرع بمفردات المصدر لا بمفرداتٍ مفترضة.
    """
    a = two_tenants["a"]
    await _runs(a["tenant_id"], a["user_id"], [
        {"input": 100, "output": 30, "cost": Decimal("0.12"), "latency": 100, "provider": "p1"},
        {"input": 200, "output": 50, "cost": None, "latency": 300, "provider": "p1"},
        {"input": 50, "output": 10, "cost": Decimal("0.04"), "status": "error",
         "provider": "p2", "model": "m-2"},
    ])
    got = (await _get(a, "/api/v1/admin/usage?window=30d")).json()
    s = got["summary"]
    assert (s["input_tokens"], s["output_tokens"]) == (350, 90)
    assert Decimal(str(s["recorded_cost_usd"])) == Decimal("0.16")
    assert (s["runs_with_cost"], s["runs_without_cost"], s["failed"]) == (2, 1, 1)
    assert got["latency"] == {"runs_with_latency": 2, "average_ms": 200, "median_ms": 200}
    providers = {b["key"]: b for b in got["by_provider"]}
    assert providers["p1"]["model_runs"] == 2 and providers["p2"]["failed"] == 1
    assert {b["key"] for b in got["by_status"]} == {"ok", "error"}
    assert len(got["by_day"]) == 1

    # **ولا تكلفةَ مسجّلةً أصلًا** ⇒ «صفرُ دولار» على **صفر** تشغيلاتٍ بتكلفة.
    b = two_tenants["b"]
    await _runs(b["tenant_id"], b["user_id"], [{"input": 1, "output": 1, "cost": None}])
    only_null = (await _get(b, "/api/v1/admin/usage")).json()["summary"]
    assert only_null["runs_with_cost"] == 0 and only_null["runs_without_cost"] == 1


@requires_db
async def test_11_usage_windows_are_bounded_by_database_time(two_tenants):
    a = two_tenants["a"]
    await _runs(a["tenant_id"], a["user_id"], [{"input": 1, "output": 1}], days_ago=5)
    await _runs(a["tenant_id"], a["user_id"], [{"input": 10, "output": 10}], days_ago=20)
    await _runs(a["tenant_id"], a["user_id"], [{"input": 100, "output": 100}], days_ago=60)
    await _runs(a["tenant_id"], a["user_id"], [{"input": 1000, "output": 1000}], days_ago=200)
    tokens = {}
    for window in ("7d", "30d", "90d"):
        tokens[window] = (await _get(a, f"/api/v1/admin/usage?window={window}")
                          ).json()["summary"]["input_tokens"]
    assert tokens == {"7d": 1, "30d": 11, "90d": 111}, tokens
    bad = await _get(a, "/api/v1/admin/usage?window=365d")
    assert bad.status_code == 422


# ═════════════════════════════ ٤ · المستخدمون ═════════════════════════════


@requires_db
async def test_12_a_user_with_several_roles_is_one_row(two_tenants):
    a = two_tenants["a"]
    many = await _member(a["tenant_id"], roles=("researcher", "supervisor", "co_author"))
    items = (await _get(a, "/api/v1/admin/users")).json()["items"]
    mine = [u for u in items if u["user_id"] == str(many["user_id"])]
    assert len(mine) == 1, f"صفوفٌ مكرّرة: {len(mine)}"
    assert mine[0]["roles"] == ["co_author", "researcher", "supervisor"]


@requires_db
async def test_13_search_role_and_active_filters_stay_inside_the_tenant(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    target = await _member(a["tenant_id"], name="نورة المطيري", roles=("supervisor",))
    idle = await _member(a["tenant_id"], name="حساب موقوف", active=False)
    stranger = await _member(b["tenant_id"], name="نورة المطيري")

    found = (await _get(a, "/api/v1/admin/users?search=%D9%86%D9%88%D8%B1%D8%A9")).json()["items"]
    assert [u["user_id"] for u in found] == [str(target["user_id"])], found
    by_email = (await _get(a, f"/api/v1/admin/users?search={target['email']}")).json()["items"]
    assert len(by_email) == 1
    sup = (await _get(a, "/api/v1/admin/users?role=supervisor")).json()["items"]
    assert [u["user_id"] for u in sup] == [str(target["user_id"])]
    off = (await _get(a, "/api/v1/admin/users?active=false")).json()["items"]
    assert [u["user_id"] for u in off] == [str(idle["user_id"])]
    assert str(stranger["user_id"]) not in json.dumps(found + by_email + sup + off)


@requires_db
async def test_14_the_global_users_table_cannot_be_reached_from_another_tenant(two_tenants):
    """**X في B وحدَه** — ومديرُ A يعرف معرّفَه وبريدَه بالضبط."""
    a, b = two_tenants["a"], two_tenants["b"]
    before = (await _get(a, "/api/v1/admin/overview")).json()["users"]["member_count"]
    x = await _member(b["tenant_id"], name="خارج المساحة")

    searched = (await _get(a, f"/api/v1/admin/users?search={x['email']}")).json()
    assert searched["items"] == [], "البحثُ كشف بريدًا خارج المساحة"
    detail = await _get(a, f"/api/v1/admin/users/{x['user_id']}")
    nowhere = await _get(a, f"/api/v1/admin/users/{uuid.uuid4()}")
    assert detail.status_code == nowhere.status_code == 404
    assert detail.json()["error"]["code"] == nowhere.json()["error"]["code"] == \
        "admin.user_not_found", "رمزان مختلفان يكشفان وجودَ الحساب"
    assert detail.json()["error"]["messages"] == nowhere.json()["error"]["messages"]
    after = (await _get(a, "/api/v1/admin/overview")).json()["users"]["member_count"]
    assert after == before, "عُدّ حسابٌ من مستأجرٍ آخر"
    # وتفصيلُ عضوٍ حقيقيٍّ يعمل — فالرفضُ ليس رفضًا للكلّ.
    assert (await _get(a, f"/api/v1/admin/users/{a['user_id']}")).status_code == 200


@requires_db
async def test_15_pagination_is_bounded_stable_and_opaque(two_tenants):
    a = two_tenants["a"]
    # **تعادلٌ مقصود**: ثلاثون عضويّةً بالطابع نفسِه، وحدُّ الصفحة داخلَه. فمؤشّرٌ
    # على الطابع وحدَه (بلا المعرّف) يُسقط ما بقي من التعادل أو يكرّره.
    tie = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    for i in range(30):
        await _member(a["tenant_id"], name=f"عضو {i:02d}", since=tie)
    first = (await _get(a, "/api/v1/admin/users?limit=20")).json()
    assert len(first["items"]) == 20 and first["next_cursor"]
    assert "SELECT" not in first["next_cursor"].upper()
    second = (await _get(a, f"/api/v1/admin/users?limit=20&cursor={first['next_cursor']}")).json()
    seen = [u["user_id"] for u in first["items"] + second["items"]]
    assert len(seen) == len(set(seen)) == 31, "تكرارٌ أو فقدٌ بين الصفحات"
    assert second["next_cursor"] is None
    again = (await _get(a, "/api/v1/admin/users?limit=20")).json()
    assert [u["user_id"] for u in again["items"]] == [u["user_id"] for u in first["items"]]
    assert (await _get(a, "/api/v1/admin/users?limit=101")).status_code == 422
    assert (await _get(a, "/api/v1/admin/users?cursor=not-a-cursor")).status_code == 422
    default = (await _get(a, "/api/v1/admin/users")).json()
    assert len(default["items"]) == 25


@requires_db
async def test_16_user_detail_is_tenant_scoped_metadata(two_tenants):
    a = two_tenants["a"]
    await _project(a["tenant_id"], a["user_id"], title="بحثٌ مملوك")
    await _file(a["tenant_id"], a["user_id"], size=4096)
    await _runs(a["tenant_id"], a["user_id"], [{"input": 11, "output": 4, "cost": None}])
    got = (await _get(a, f"/api/v1/admin/users/{a['user_id']}")).json()
    assert got["user"]["roles"] == ["researcher"]
    assert got["user"]["project_count"] == 1 and got["user"]["file_count"] == 1
    assert got["file_bytes"] == 4096
    assert got["ai_30d"]["input_tokens"] == 11 and got["ai_30d"]["runs_without_cost"] == 1
    assert [p["title"] for p in got["projects"]] == ["بحثٌ مملوك"]
    assert "password" not in json.dumps(got).lower()


# ═════════════════════════════ ٥ · البحوث ═════════════════════════════


@requires_db
async def test_17_projects_are_tenant_scoped_with_real_filters(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    live = await _project(a["tenant_id"], a["user_id"], title="بحثٌ حيّ")
    shelved = await _project(a["tenant_id"], a["user_id"], title="بحثٌ مؤرشف", archived=True)
    binned = await _project(a["tenant_id"], a["user_id"], title="بحثٌ في السلّة", trashed=True)
    theirs = await _project(b["tenant_id"], b["user_id"], title="بحثُ مستأجرٍ آخر")

    default = (await _get(a, "/api/v1/admin/projects")).json()["items"]
    ids = {p["project_id"] for p in default}
    assert ids == {str(live), str(shelved)}, "السلّةُ أو مستأجرٌ آخر في القائمة الافتراضيّة"
    assert str(theirs) not in json.dumps(default)
    trash = (await _get(a, "/api/v1/admin/projects?lifecycle=trashed")).json()["items"]
    assert [p["project_id"] for p in trash] == [str(binned)]
    owner = (await _get(a, f"/api/v1/admin/projects?owner_id={a['user_id']}")).json()["items"]
    assert {p["owner_user_id"] for p in owner} == {str(a["user_id"])}
    assert owner[0]["owner_name"], "مالكٌ عضوٌ بلا اسم"
    hit = (await _get(a, "/api/v1/admin/projects?search=%D9%85%D8%A4%D8%B1%D8%B4%D9%81")).json()
    assert [p["project_id"] for p in hit["items"]] == [str(shelved)]
    # ومستأجرٌ آخر لا يُستهدف ولو طُلب بالاسم أو بمعرّف مالكه.
    cross = (await _get(a, f"/api/v1/admin/projects?owner_id={b['user_id']}")).json()
    assert cross["items"] == []
    # **ومالكٌ ليس عضوًا هنا لا اسمَ له**: أنشأه حسابٌ من B (سجلُّ A يحمل معرّفه).
    # فالمعرّفُ من بيانات A، والاسمُ من الجدول العامّ — ولا يُقرأ إلّا عبر عضويّة.
    stranger = await _project(a["tenant_id"], b["user_id"], title="أنشأه غريب")
    rows = (await _get(a, "/api/v1/admin/projects")).json()["items"]
    row = next(p for p in rows if p["project_id"] == str(stranger))
    assert row["owner_user_id"] == str(b["user_id"]) and row["owner_name"] is None
    assert b["email"] not in json.dumps(rows)


@requires_db
async def test_18_a_tenant_id_in_the_query_changes_nothing(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    await _project(b["tenant_id"], b["user_id"], title="لا يُرى")
    ours = await _project(a["tenant_id"], a["user_id"], title="يُرى")
    for url in ENDPOINTS:
        injected = await _get(a, f"{url}?tenant_id={b['tenant_id']}")
        assert injected.status_code == 200
        assert str(b["tenant_id"]) not in injected.text, f"{url}: مستأجرٌ من الطلب"
    # **ولا يصير المستأجرُ المحقونُ سلطةً صامتة**: RLS وحدَها تُخفي بياناتِ B —
    # فمسارٌ يأخذ `tid` من الطلب يُجيب فارغًا لا مسرّبًا. فيُشترط أنّ بياناتِ A باقية.
    projects = (await _get(a, f"/api/v1/admin/projects?tenant_id={b['tenant_id']}")).json()
    assert [p["project_id"] for p in projects["items"]] == [str(ours)]
    overview = (await _get(a, f"/api/v1/admin/overview?tenant_id={b['tenant_id']}")).json()
    assert overview["scope"]["tenant_id"] == str(a["tenant_id"])
    assert overview["projects"]["total"] == 1
    users = (await _get(a, f"/api/v1/admin/users?tenant_id={b['tenant_id']}")).json()
    assert [u["user_id"] for u in users["items"]] == [str(a["user_id"])]


# ═════════════════════════════ ٦ · العمليات والخصوصيّة ═════════════════════════════


async def _thesis(tenant_id, owner_id, *, state="failed", code="parse_failed") -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    file_id = await _file(tenant_id, owner_id)
    async with tenant_session(tenant_id, owner_id) as session:
        row = Thesis(tenant_id=tenant_id, title_ar="رسالةٌ للفحص", file_id=file_id,
                     processing_state=state, failure_code=code,
                     failure_detail=f"detail {RESEARCH_SECRET}" if code else None,
                     text_layer_state="present" if state != "text_layer_missing" else "absent",
                     processing_state_changed_at=dt.datetime.now(dt.UTC))
        session.add(row)
        await session.flush()
        return row.id


@requires_db
async def test_19_operations_show_failures_as_metadata_only(two_tenants):
    a = two_tenants["a"]
    await _runs(a["tenant_id"], a["user_id"], [
        {"input": 1, "output": 1, "status": "error"},
        {"input": 1, "output": 1, "status": "ambiguous"},
        {"input": 1, "output": 1, "status": "ok"}])
    # وتشغيلٌ خارج النافذة (١٢٠ يومًا) — لا يبلغه ولا «الكلّ».
    await _runs(a["tenant_id"], a["user_id"], [{"input": 1, "output": 1, "status": "error"}],
                days_ago=120)
    thesis = await _thesis(a["tenant_id"], a["user_id"])
    everything = (await _get(a, "/api/v1/admin/operations?view=all")).json()
    assert len(everything["agent_runs"]) == 1, "«الكلّ» تجاوز نافذةَ التسعين يومًا"
    assert len(everything["model_runs"]) == 3 and len(everything["tool_runs"]) == 1
    ops = (await _get(a, "/api/v1/admin/operations")).json()
    assert ops["view"] == "failed" and ops["limit"] == 50
    assert {m["status"] for m in ops["model_runs"]} == {"error", "ambiguous"}
    assert ops["agent_runs"][0]["error_present"] is True
    assert ops["agent_runs"][0]["requested_by_name"]
    assert ops["tool_runs"][0]["status"] == "error"
    assert [t["thesis_id"] for t in ops["theses"]] == [str(thesis)]
    assert ops["theses"][0]["failure_code"] == "parse_failed"
    assert (await _get(a, "/api/v1/admin/operations?limit=201")).status_code == 422
    assert (await _get(a, "/api/v1/admin/operations?view=everything")).status_code == 422


@requires_db
async def test_20_no_research_payload_reaches_any_admin_response(two_tenants):
    """**نصٌّ بحثيٌّ مزروعٌ في كلِّ حمولةٍ وخطأٍ واسمِ ملفّ** — ولا يظهر في جوابٍ واحد."""
    a = two_tenants["a"]
    await _runs(a["tenant_id"], a["user_id"], [{"input": 1, "output": 1, "status": "error"}])
    await _thesis(a["tenant_id"], a["user_id"])
    await _file(a["tenant_id"], a["user_id"])
    urls = [*ENDPOINTS, f"/api/v1/admin/users/{a['user_id']}",
            "/api/v1/admin/operations?view=all", "/api/v1/admin/usage?window=90d"]
    for url in urls:
        body = (await _get(a, url)).text
        assert RESEARCH_SECRET not in body, f"نصٌّ بحثيٌّ في {url}"
        for field in ("request_payload", "response_payload", "input_summary",
                      "password_hash", "failure_detail"):
            assert field not in body, f"{field} في {url}"


# ═════════════════════════════ ٧ · الحدود والأداء ═════════════════════════════


@requires_db
async def test_21_list_endpoints_issue_a_constant_number_of_statements(two_tenants):
    """**لا N+1**: عددُ العبارات لا يكبر بعدد الصفوف."""
    from sqlalchemy import event

    from athera_api import db as dbmod

    a = two_tenants["a"]

    async def count(url):
        seen = {"n": 0}

        def _tick(*_a, **_k):
            seen["n"] += 1

        event.listen(dbmod.engine.sync_engine, "before_cursor_execute", _tick)
        try:
            ok = await _get(a, url)
        finally:
            event.remove(dbmod.engine.sync_engine, "before_cursor_execute", _tick)
        assert ok.status_code == 200, ok.text
        return seen["n"]

    # **والأساسُ صفحةٌ غيرُ فارغة**: الصفحةُ الفارغةُ تتخطّى العباراتِ الثانويّة
    # بحقّ، فمقارنتُها بصفحةٍ ملأى تقيس الفرعَ لا النموّ. فصفّان أوّلًا.
    seed = await _member(a["tenant_id"], name="أساس")
    await _project(a["tenant_id"], seed["user_id"], title="أساس")
    small_users, small_projects = await count("/api/v1/admin/users"), \
        await count("/api/v1/admin/projects")
    for i in range(50):
        m = await _member(a["tenant_id"], name=f"م{i}")
        await _project(a["tenant_id"], m["user_id"], title=f"ب{i}")
    await _runs(a["tenant_id"], a["user_id"], [{"input": 1, "output": 1}] * 120)

    big_users, big_projects = await count("/api/v1/admin/users"), \
        await count("/api/v1/admin/projects")
    assert big_users == small_users, f"المستخدمون: {small_users} → {big_users}"
    assert big_projects == small_projects, f"البحوث: {small_projects} → {big_projects}"
    assert big_users <= 12 and big_projects <= 12

    page = (await _get(a, "/api/v1/admin/users")).json()
    assert len(page["items"]) == 25
    usage = (await _get(a, "/api/v1/admin/usage")).json()
    assert usage["summary"]["model_runs"] == 120 and len(usage["by_day"]) <= 31


def test_22_every_admin_query_pins_the_principal_tenant() -> None:
    """**طبقتان لا طبقة**: RLS، وفوقها شرطُ `tenant_id == tid` صريحٌ في كلّ دالّة.

    وRLS وحدَها تُخفي حذفَ الشرط الصريح في الفحوص الحيّة — فحذفُه لا يُحمّر
    شيئًا وتسقط الطبقةُ الثانية صامتة. فيُقرأ المصدر: كلُّ نموذجٍ مستأجَرٍ تلمسه
    دالّةٌ هنا يُقيَّد فيها بـ`tid` المأخوذ من الرمز.
    """
    source = (API / "athera_api" / "services" / "admin_console.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    scoped = ("Membership", "Role", "ResearchProject", "File", "Thesis", "AgentRun",
              "ModelRun", "ToolRun", "ProjectMember", "ProjectFile", "Manuscript", "AuditEvent")
    # `_owner_expr` و`_lifecycle_expr` تعبيران يُركَّبان داخل استعلامٍ مقيَّدٍ أصلًا.
    exempt = {"_owner_expr", "_lifecycle_expr"}
    offenders = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name in exempt:
            continue
        body = ast.get_source_segment(source, fn) or ""
        for model in scoped:
            if re.search(rf"\b{model}\.(?!tenant_id)\w+", body) and \
                    f"{model}.tenant_id == tid" not in body:
                offenders.append(f"{fn.name}: {model}")
    assert offenders == [], f"نموذجٌ مستأجَرٌ بلا شرطِ المستأجر الصريح: {offenders}"
