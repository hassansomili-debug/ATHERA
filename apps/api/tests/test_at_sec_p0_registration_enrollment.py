"""P0 — التسجيل الذاتي لا ينضمّ إلى مستأجر قائم.

**ثغرة تفويض، لا تسريب عزل.** `POST /auth/register` عامٌّ بلا مصادقة، وكان
يقبل `tenant_slug` نصًّا حرًّا؛ فإن طابق مستأجرًا قائمًا أنشأ المستخدم عضوًا
فيه بدور باحث وأصدر له رمزًا.

وخطورتها أنها **تلتفّ على كل ما بُني**: سياسات RLS سليمة، وبوابات الملكية
سليمة، وحارس الدور سليم — والمهاجم لا يكسر واحدًا منها. يصير عضوًا شرعيًّا،
فتفتح له الطبقات أبوابها كما تفتحها لصاحب البيت.

ويكفي أن يعرف الاسم. و`athera` اسمٌ يُخمَّن من أول محاولة.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db


# نطاقٌ اصطناعي يقبله المدقّق: `.test` نطاقٌ محجوز يرفضه `EmailStr`، وحارس
# قاعدة الاختبار يمنع أصلًا أن تبلغ هذه الصفوف قاعدة إنتاج.
FIXTURE_DOMAIN = "fixtures.athera"


def _payload(email: str, **extra) -> dict:
    body = {
        "email": email,
        "password": "a-long-enough-password",
        "full_name_ar": "باحث اختبار",
        "preferred_locale": "ar",
    }
    body.update(extra)
    return body


async def _register(payload: dict):
    from athera_api.errors import AtheraError
    from athera_api.routers import auth
    from athera_api.schemas.auth import RegisterRequest

    try:
        return await auth.register(RegisterRequest(**payload), locale="ar"), None
    except AtheraError as exc:
        return None, exc


async def _counts(tenant_id=None) -> dict:
    """أعدادٌ عامة — والعضويات تُعدّ بسياق مستأجرها حين يُطلب.

    `users` و`tenants` لهما سياسة عامة؛ و`memberships` عليها عزلٌ مفروض،
    فعدّها بلا سياق يعطي صفرًا دائمًا — ومقارنةُ صفرٍ بصفر لا تثبت شيئًا.
    """
    from sqlalchemy import func, select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Tenant, User

    async with system_session() as session:
        totals = {
            "users": (await session.execute(
                select(func.count(User.id)))).scalar_one(),
            "tenants": (await session.execute(
                select(func.count(Tenant.id)))).scalar_one(),
        }
    if tenant_id is not None:
        async with tenant_session(tenant_id) as scoped:
            totals["memberships"] = (await scoped.execute(
                select(func.count(Membership.id)))).scalar_one()
    return totals


# ══════════ 1. السلوك المشروع لا ينكسر ══════════

@requires_db
@pytest.mark.asyncio
async def test_a_brand_new_workspace_still_registers_normally(db_ready):
    """المسار المقصود يبقى: اسمٌ جديد ⇒ مساحةٌ جديدة وعضويةُ باحث فيها."""
    from sqlalchemy import select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Tenant, User

    slug = f"fresh-{uuid.uuid4().hex[:10]}"
    tokens, error = await _register(_payload(f"{slug}@fixtures.athera", tenant_slug=slug))
    assert error is None, error
    assert tokens.access_token

    async with system_session() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == slug))).scalar_one()
        user = (await session.execute(
            select(User).where(User.email == f"{slug}@{FIXTURE_DOMAIN}"))).scalar_one()

    # **العضوية تُقرأ بسياق مستأجرها.** `memberships` عليها عزلٌ مفروض، وجلسةُ
    # النظام لا تضبط مستأجرًا — فتعود صفرًا. وهو الدرس نفسه الذي كشفه احتواء
    # حادثة P0 حين انكسر تسجيل الدخول.
    async with tenant_session(tenant.id, user.id) as scoped:
        membership = (await scoped.execute(
            select(Membership).where(Membership.user_id == user.id))).scalar_one()
    assert membership.tenant_id == tenant.id


# ══════════ 2. الاسم المأخوذ يفشل مغلقًا ══════════

@requires_db
@pytest.mark.asyncio
async def test_registering_into_an_existing_tenant_is_denied(two_tenants):
    """**الثغرة نفسها.** ويجب أن يفشل هذا الاختبار ضدّ الشيفرة القديمة."""
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import Tenant

    async with system_session() as session:
        victim = (await session.execute(
            select(Tenant.slug).where(
                Tenant.id == two_tenants["a"]["tenant_id"]))).scalar_one()

    before = await _counts(two_tenants["a"]["tenant_id"])
    email = f"attacker-{uuid.uuid4().hex[:8]}@fixtures.athera"
    tokens, error = await _register(_payload(email, tenant_slug=victim))

    assert tokens is None, "أُصدر رمزٌ لمستأجر ليس للمستدعي فيه شيء"
    assert error is not None and error.code == "auth.workspace_name_taken"
    assert error.status_code == 409
    # **ولا كتابة واحدة**: لا مستخدم، ولا عضوية، ولا دور، ولا مستأجر.
    assert await _counts(two_tenants["a"]["tenant_id"]) == before


@requires_db
@pytest.mark.asyncio
async def test_no_user_row_survives_a_denied_registration(two_tenants):
    """المعاملة تعود كاملةً — فلا حسابٌ يتيمٌ يبقى شاهدًا على محاولة."""
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import Tenant, User

    async with system_session() as session:
        victim = (await session.execute(
            select(Tenant.slug).where(
                Tenant.id == two_tenants["a"]["tenant_id"]))).scalar_one()

    email = f"ghost-{uuid.uuid4().hex[:8]}@fixtures.athera"
    _tokens, error = await _register(_payload(email, tenant_slug=victim))
    assert error is not None

    async with system_session() as session:
        assert (await session.execute(
            select(User).where(User.email == email))).scalar_one_or_none() is None


@requires_db
@pytest.mark.asyncio
async def test_no_membership_is_created_in_the_targeted_tenant(two_tenants):
    from sqlalchemy import func, select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Tenant

    tenant_id = two_tenants["a"]["tenant_id"]
    async with system_session() as session:
        victim = (await session.execute(
            select(Tenant.slug).where(Tenant.id == tenant_id))).scalar_one()
        before = (await session.execute(select(func.count(Membership.id)).where(
            Membership.tenant_id == tenant_id))).scalar_one()

    await _register(_payload(f"x-{uuid.uuid4().hex[:8]}@fixtures.athera",
                             tenant_slug=victim))

    async with system_session() as session:
        after = (await session.execute(select(func.count(Membership.id)).where(
            Membership.tenant_id == tenant_id))).scalar_one()
    assert after == before


@requires_db
@pytest.mark.asyncio
async def test_no_audit_event_is_written_inside_the_targeted_tenant(two_tenants):
    """رفضٌ لا يترك أثرًا في سجلّ مستأجرٍ آخر — والسجل مِلكُه لا ساحةٌ عامة."""
    from sqlalchemy import func, select

    from athera_api.db import system_session
    from athera_api.models.audit import AuditEvent
    from athera_api.models.identity import Tenant

    tenant_id = two_tenants["a"]["tenant_id"]
    async with system_session() as session:
        victim = (await session.execute(
            select(Tenant.slug).where(Tenant.id == tenant_id))).scalar_one()
        before = (await session.execute(select(func.count(AuditEvent.id)).where(
            AuditEvent.tenant_id == tenant_id))).scalar_one()

    await _register(_payload(f"y-{uuid.uuid4().hex[:8]}@fixtures.athera",
                             tenant_slug=victim))

    async with system_session() as session:
        after = (await session.execute(select(func.count(AuditEvent.id)).where(
            AuditEvent.tenant_id == tenant_id))).scalar_one()
    assert after == before


# ══════════ 3. والاسم المشتقّ من البريد كذلك ══════════

@requires_db
@pytest.mark.asyncio
async def test_an_email_derived_slug_cannot_join_an_existing_tenant(db_ready):
    """`ahmed@x.com` و`ahmed@y.com` يشتقّان الاسم نفسه.

    فلو استُثني المشتقّ من القاعدة لبقيت الثغرة مفتوحةً **بلا أن يكتب
    المهاجم حرفًا** — يكفي أن يسجّل ببريدٍ اسمُه اسمُ الضحية.
    """
    local = f"shared{uuid.uuid4().hex[:8]}"
    first, error = await _register(_payload(f"{local}@first.athera"))
    assert error is None and first is not None

    before = await _counts()
    second, error = await _register(_payload(f"{local}@second.athera"))
    assert second is None, "انضمّ إلى مساحة غيره باسمٍ مشتقّ من بريده"
    assert error is not None and error.code == "auth.workspace_name_taken"
    assert await _counts() == before


# ══════════ 4. السباق ══════════

@requires_db
@pytest.mark.asyncio
async def test_a_slug_race_never_turns_into_an_enrollment(db_ready):
    """طلبان متزامنان: أحدهما يفوز، والآخر يُرفض — ولا ينضمّ إلى ما أنشأه غيره.

    والخطر أن يُقرأ اصطدام قيد التفرّد «صار المستأجر موجودًا فلننضمّ إليه»،
    فتعود الثغرة من باب معالجة الأخطاء.
    """
    import asyncio

    from sqlalchemy import func, select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Tenant

    slug = f"race-{uuid.uuid4().hex[:10]}"
    results = await asyncio.gather(
        _register(_payload(f"a-{slug}@fixtures.athera", tenant_slug=slug)),
        _register(_payload(f"b-{slug}@fixtures.athera", tenant_slug=slug)),
        return_exceptions=True,
    )
    granted = [r for r in results if isinstance(r, tuple) and r[0] is not None]
    assert len(granted) <= 1, "منح السباق عضويتين في مساحة واحدة"

    async with system_session() as session:
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
        if tenant is not None:
            members = (await session.execute(select(func.count(Membership.id)).where(
                Membership.tenant_id == tenant.id))).scalar_one()
            assert members <= 1, "عضوان في مساحة أنشأها أحدهما"


# ══════════ 5. الحارس بنيويّ لا نصّي ══════════

def test_the_join_existing_tenant_branch_no_longer_exists():
    """الفرع يُحذف ولا يُخبّأ خلف شرط — شرطٌ يُنسى، وفرعٌ محذوف لا يعود."""
    import inspect

    from athera_api.routers import auth

    source = inspect.getsource(auth.register)
    assert "auth.workspace_name_taken" in source
    # لا فرعَ «إن لم يوجد المستأجر فأنشئه» — أي لا مسارَ «وإن وُجد فاستعمله».
    assert "if tenant is None:" not in source
    # والرفض قبل أي كتابة.
    assert source.index("workspace_name_taken") < source.index("user = User(")


def test_the_only_other_membership_path_is_admin_gated():
    """§5 — لا مسارَ عامٍّ ثانٍ يمنح عضوية في مستأجر قائم."""
    import inspect

    from athera_api.routers import tenants

    source = inspect.getsource(tenants.add_member)
    assert "require_roles(" in source
    assert 'if tenant_id != principal.tenant_id:' in source


def test_no_third_path_creates_a_membership():
    """جردٌ بنيوي: كل موضع يُنشئ عضوية يُعرف بالاسم ويُراجَع."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    creators = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if path.parent.name != "models" and re.search(r"(?<![A-Za-z])Membership\(",
                                                      path.read_text())
    )
    assert creators == ["routers/auth.py", "routers/tenants.py"], creators
