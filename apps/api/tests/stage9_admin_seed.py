"""تجهيزُ رحلة المتصفّح للوحة الإدارة (المرحلة ٩) — **للفحوص وحدَها**.

## ولمَ عبر القاعدة

لا مسارَ في المنتج يمنح دورًا إداريًّا لحسابٍ جديد — وذاك مقصود: منحُ الأدوار
مُحالٌ إلى المرحلة ١٠. فالرحلةُ تُسجّل حسابًا حقيقيًّا من الواجهة، ثمّ يُمنح
هنا دورًا إداريًّا **وعاملَ تحقّقٍ بخطوتين مؤكَّدًا**، ثمّ يدخل من الواجهة
نفسِها بكلمته **ورمزِ TOTP حقيقيّ**. فسياسةُ MFA للأدوار الإداريّة تبقى كما هي —
لا تُطفأ لتسهيل الفحص.

## الأوامر

    python -m tests.stage9_admin_seed grant   <email> <role> <totp_secret>
    python -m tests.stage9_admin_seed member  <admin_email> <new_email> <role> <active>
    python -m tests.stage9_admin_seed activity <email> <secret_text>
    python -m tests.stage9_admin_seed project <email> <title>

وكلُّها تكتب **في مستأجر الحساب نفسِه** وبسياقه — لا جلسةَ نظامٍ إلّا لجدولَي
`users` و`mfa_factors` العامّين، كما يفعل `two_tenants` و`_second_user`.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
import uuid
from decimal import Decimal


async def _user_and_tenant(email: str) -> tuple[uuid.UUID, uuid.UUID]:
    """الحسابُ ومستأجرُه — **بالطريق نفسِه الذي يسلكه الدخول**.

    `memberships` محميّةٌ بـRLS، وجلسةٌ بلا مستأجرٍ تراها فارغة — وهو الصواب.
    فيُسأل `app_login_tenant` كما يسأله مسارُ الدخول، لا تُتجاوز السياسة.
    """
    from sqlalchemy import select, text

    from athera_api.db import system_session
    from athera_api.models.identity import User

    async with system_session() as session:
        user_id = (await session.execute(
            select(User.id).where(User.email == email.lower()))).scalar_one()
        tenant_id = await session.scalar(
            text("SELECT app_login_tenant(:uid, :slug)"), {"uid": str(user_id), "slug": None})
    if tenant_id is None:
        raise SystemExit(f"no tenant for {email}")
    return user_id, uuid.UUID(str(tenant_id))


async def grant(email: str, role: str, secret: str) -> None:
    from sqlalchemy import delete, select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import MfaFactor, Membership, Role

    user_id, tenant_id = await _user_and_tenant(email)
    async with tenant_session(tenant_id) as scoped:
        role_id = (await scoped.execute(select(Role.id).where(
            Role.tenant_id == tenant_id, Role.key == role))).scalar_one()
        scoped.add(Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id))
    async with system_session() as session:
        await session.execute(delete(MfaFactor).where(MfaFactor.user_id == user_id))
        session.add(MfaFactor(user_id=user_id, factor_type="totp", secret_encrypted=secret,
                              confirmed_at=dt.datetime.now(dt.UTC)))
    print(f"granted {role} + totp to {user_id} in {tenant_id}")


async def member(admin_email: str, new_email: str, role: str, active: str) -> None:
    from sqlalchemy import select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    _admin_id, tenant_id = await _user_and_tenant(admin_email)
    async with system_session() as session:
        user = User(email=new_email.lower(), password_hash=hash_password("Stage9-Member-Pw!"),
                    full_name_ar="عضو " + role, full_name_en="Member " + role,
                    is_active=active == "true")
        session.add(user)
        await session.flush()
        user_id = user.id
    async with tenant_session(tenant_id) as scoped:
        role_id = (await scoped.execute(select(Role.id).where(
            Role.tenant_id == tenant_id, Role.key == role))).scalar_one()
        scoped.add(Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id))
    print(f"member {user_id}")


async def activity(email: str, secret_text: str) -> None:
    """تشغيلاتٌ مزروعة: تكلفةٌ مسجّلةٌ وأخرى فارغة، وفشلٌ، وحمولةٌ بحثيّة."""
    from athera_api.db import tenant_session
    from athera_api.models.runs import AgentRun, ModelRun, ToolRun

    user_id, tenant_id = await _user_and_tenant(email)
    now = dt.datetime.now(dt.UTC)
    async with tenant_session(tenant_id, user_id) as session:
        agent = AgentRun(tenant_id=tenant_id, agent_key="stage9.browser", status="failed",
                         started_at=now, finished_at=now, requested_by=user_id,
                         trace_id=uuid.uuid4(), input_summary={"text": secret_text},
                         error=f"failure {secret_text}")
        session.add(agent)
        await session.flush()
        for inp, out, cost, status in ((100, 30, Decimal("0.12"), "ok"),
                                       (200, 50, None, "ok"),
                                       (50, 10, Decimal("0.04"), "error")):
            session.add(ModelRun(tenant_id=tenant_id, agent_run_id=agent.id, provider="fake",
                                 model="m-browser", operation="planning", input_tokens=inp,
                                 output_tokens=out, cost_usd=cost, status=status,
                                 latency_ms=120,
                                 error=f"model {secret_text}" if status == "error" else None))
        session.add(ToolRun(tenant_id=tenant_id, agent_run_id=agent.id, tool_key="search",
                            status="error", duration_ms=9, request_payload={"q": secret_text},
                            response_payload={"hits": [secret_text]}, error=secret_text))
    print("activity seeded")


async def project(email: str, title: str) -> None:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.services import audit

    user_id, tenant_id = await _user_and_tenant(email)
    async with tenant_session(tenant_id, user_id) as session:
        row = ResearchProject(tenant_id=tenant_id, working_title_ar=title, status="planned")
        session.add(row)
        await session.flush()
        await audit.record(session, tenant_id=tenant_id, action="workspace.project_created",
                           object_type="research_project", object_id=row.id,
                           actor_user_id=user_id, reason="stage 9 browser fixture")
    print(f"project {title}")


def main(argv: list[str]) -> None:
    command, *args = argv
    handlers = {"grant": grant, "member": member, "activity": activity, "project": project}
    asyncio.run(handlers[command](*args))


if __name__ == "__main__":
    main(sys.argv[1:])
