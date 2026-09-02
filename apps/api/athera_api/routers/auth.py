"""المصادقة | Authentication routes (§36.1).

كل مسار هنا يكتب حدث تدقيق داخل نفس المعاملة — بلا استثناء (AT-S0-04).
"""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ..config import get_settings
from ..db import system_session, tenant_session
from ..deps import Principal, get_locale, get_principal
from ..errors import AtheraError, Unauthorized
from ..models.identity import Membership, MfaFactor, RefreshToken, Role, Tenant, User
from ..schemas.auth import (
    LoginRequest,
    MeResponse,
    MfaEnrollResponse,
    MfaVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from ..security import (
    hash_password,
    hash_refresh_token,
    issue_access_token,
    new_refresh_token,
    new_totp_secret,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from ..services import audit, rbac

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


async def _bind_tenant(session, tenant_id: uuid.UUID,
                       actor_id: uuid.UUID | None = None) -> None:
    """يثبّت سياق المستأجر لبقية المعاملة **حالما يُعرف**.

    مسار الهوية يبدأ بلا سياق — فالمستأجر نفسه هو ما نبحث عنه. لكن ما إن
    يُعرف حتى تصير كل قراءة وكتابة بعده مملوكةً له: العضوية والأدوار ورموز
    التجديد وسجل التدقيق. فيُضبط هنا، وتجري بقية المعاملة تحت RLS كاملةً
    بلا استثناء ولا إرخاء سياسة.

    وهو المبدأ الذي أقرّه الترحيل 0014 لإقلاع المستأجر — وينطبق على الدخول
    بحرفه. و`set_config(..., true)` محلّي بالمعاملة فلا يتسرّب إلى طلبٍ
    لاحق عبر اتصال معاد استخدامه من التجمّع.
    """
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
    if actor_id is not None:
        await session.execute(
            text("SELECT set_config('app.actor_id', :aid, true)"), {"aid": str(actor_id)})


async def _issue_pair(session, user: User, tenant_id: uuid.UUID, roles: list[str],
                      mfa_satisfied: bool) -> TokenPair:
    raw_refresh, refresh_hash = new_refresh_token()
    session.add(
        RefreshToken(
            tenant_id=tenant_id,
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=dt.datetime.now(dt.UTC)
            + dt.timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    return TokenPair(
        access_token=issue_access_token(user.id, tenant_id, roles, mfa_satisfied),
        refresh_token=raw_refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, locale: str = Depends(get_locale)) -> TokenPair:
    async with system_session() as session:
        existing = (
            await session.execute(select(User).where(User.email == payload.email.lower()))
        ).scalar_one_or_none()
        if existing is not None:
            raise AtheraError("auth.email_taken", status_code=409)

        # ══════════ التسجيل الذاتي يُنشئ مساحةً جديدة، ولا ينضمّ إلى قائمة ══════════
        #
        # **ثغرة تفويض أُغلقت هنا.** كان هذا المسار — وهو عام بلا مصادقة —
        # يقبل `tenant_slug` نصًّا حرًّا من المستدعي، فإن طابق مستأجرًا قائمًا
        # أنشأ المستخدم **عضوًا فيه بدور باحث** وأصدر له رمزًا. أي أن كل عمل
        # عزل المستأجرين — RLS وسياساتها وبوابات الملكية وحارس الدور —
        # يُلتفّ عليه بالباب الأمامي: المهاجم لا يكسر العزل، بل يصير عضوًا
        # شرعيًّا فيه. ويكفي أن يعرف الاسم؛ وأسماءٌ كثيرة تُخمَّن.
        #
        # والقاعدة الآن: **اسمٌ مأخوذ يعني رفضًا، لا انضمامًا.** والانضمام إلى
        # مساحة قائمة يحتاج مسارًا مأذونًا (`POST /tenants/{id}/members`،
        # وهو محصورٌ بأدوار الإدارة داخل مستأجرها).
        #
        # والقاعدة تسري على الاسم المشتقّ من البريد كما تسري على المكتوب:
        # `ahmed@x.com` و`ahmed@y.com` يشتقّان الاسم نفسه، فلو استُثني
        # المشتقّ لبقيت الثغرة مفتوحةً بلا أن يكتب المهاجم حرفًا.
        slug = payload.tenant_slug or payload.email.split("@")[0].lower()[:64]
        taken = (
            await session.execute(select(Tenant.id).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if taken is not None:
            # رفضٌ **قبل أي كتابة**: لا مستخدم، ولا دور، ولا عضوية، ولا رمز،
            # ولا حدث تدقيق داخل مستأجرٍ ليس للمستدعي فيه شيء.
            raise AtheraError("auth.workspace_name_taken", status_code=409)

        tenant = Tenant(
            slug=slug,
            name_ar=payload.tenant_name_ar or payload.full_name_ar,
            name_en=payload.tenant_name_en or payload.full_name_en,
            default_locale=payload.preferred_locale,
        )
        session.add(tenant)
        try:
            # **السباق يفشل مغلقًا.** طلبان متزامنان على الاسم نفسه: أحدهما
            # يفوز، والآخر يصطدم بقيد التفرّد. ولا يجوز أن يُقرأ الاصطدام
            # «صار المستأجر موجودًا، فلننضمّ إليه» — تلك هي الثغرة نفسها
            # تدخل من باب المعالجة.
            await session.flush()
        except IntegrityError as exc:
            raise AtheraError("auth.workspace_name_taken", status_code=409) from exc

        # سياق بقية المعاملة — وإلا سقطت كتابة الأدوار والعضوية والتدقيق
        # تحت RLS.
        await _bind_tenant(session, tenant.id)

        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password),
            full_name_ar=payload.full_name_ar,
            full_name_en=payload.full_name_en,
            preferred_locale=payload.preferred_locale,
        )
        session.add(user)
        await session.flush()

        # المستأجر جديدٌ يقينًا، فدورُه إمّا بذَره مشغّل الترحيل أو يُنشأ هنا.
        researcher_role = (
            await session.execute(
                select(Role).where(Role.tenant_id == tenant.id, Role.key == "researcher")
            )
        ).scalar_one_or_none()
        if researcher_role is None:
            researcher_role = Role(tenant_id=tenant.id, key="researcher",
                                   name_ar="باحث", name_en="Researcher")
            session.add(researcher_role)
            await session.flush()

        session.add(Membership(tenant_id=tenant.id, user_id=user.id, role_id=researcher_role.id))

        await audit.record(
            session,
            tenant_id=tenant.id,
            action="user.registered",
            object_type="user",
            object_id=user.id,
            actor_user_id=user.id,
            state_after={"email": user.email, "locale": user.preferred_locale},
            reason="self-registration",
        )
        return await _issue_pair(session, user, tenant.id, ["researcher"], mfa_satisfied=False)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, locale: str = Depends(get_locale)) -> TokenPair:
    async with system_session() as session:
        user = (
            await session.execute(select(User).where(User.email == payload.email.lower()))
        ).scalar_one_or_none()
        if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
            raise Unauthorized("auth.invalid_credentials")

        # **مستأجر هذا المستخدم — بدالة ضيّقة تعيد معرّفًا لا صفًّا** (0018).
        #
        # `memberships` و`roles` مملوكان لمستأجر وسياستهما صارمة، والسياق
        # هنا لم يُحدَّد بعد لأن المستأجر هو ما نبحث عنه. وقراءتهما مباشرةً
        # تعيد صفر صفوف تحت الدور الصحيح — وهو ما أوقف الدخول كليًّا حين
        # صُحّح رابط الإنتاج. فالسؤال الوحيد المستثنى هو «أي مستأجر؟».
        tenant_id = await session.scalar(
            text("SELECT app_login_tenant(:uid, :slug)"),
            {"uid": str(user.id), "slug": payload.tenant_slug or None},
        )
        if tenant_id is None:
            raise Unauthorized("auth.invalid_credentials")
        await _bind_tenant(session, tenant_id, user.id)

        # وما بعدها تحت RLS كاملةً — بفلترة صريحة أيضًا، طبقتين لا واحدة.
        rows = (
            await session.execute(
                select(Membership, Role)
                .join(Role, Role.id == Membership.role_id)
                .where(Membership.user_id == user.id,
                       Membership.tenant_id == tenant_id,
                       Role.tenant_id == tenant_id)
            )
        ).all()
        if not rows:
            raise Unauthorized("auth.invalid_credentials")

        roles = [row[1].key for row in rows]

        factor = (
            await session.execute(
                select(MfaFactor).where(MfaFactor.user_id == user.id,
                                        MfaFactor.confirmed_at.is_not(None))
            )
        ).scalar_one_or_none()

        needs_mfa = settings.mfa_required_for_admin_roles and bool(
            set(roles) & rbac.ADMIN_ROLE_KEYS
        )
        mfa_satisfied = False
        if factor is not None:
            if payload.totp_code and verify_totp(factor.secret_encrypted, payload.totp_code):
                mfa_satisfied = True
            elif needs_mfa:
                raise Unauthorized("auth.mfa_invalid_code")
        elif needs_mfa:
            raise Unauthorized("auth.mfa_required")

        user.last_login_at = dt.datetime.now(dt.UTC)
        await audit.record(
            session,
            tenant_id=tenant_id,
            action="user.logged_in",
            object_type="user",
            object_id=user.id,
            actor_user_id=user.id,
            state_after={"mfa_satisfied": mfa_satisfied, "roles": roles},
        )
        return await _issue_pair(session, user, tenant_id, roles, mfa_satisfied)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest) -> TokenPair:
    token_hash = hash_refresh_token(payload.refresh_token)
    async with system_session() as session:
        # `refresh_tokens` مملوك لمستأجر — ولا يُعرف مستأجره إلا منه (0018).
        owner_tenant = await session.scalar(
            text("SELECT app_refresh_token_tenant(:h)"), {"h": token_hash})
        if owner_tenant is None:
            raise Unauthorized("auth.token_expired")
        await _bind_tenant(session, owner_tenant)

        record = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash,
                                           RefreshToken.tenant_id == owner_tenant)
            )
        ).scalar_one_or_none()
        now = dt.datetime.now(dt.UTC)
        if record is None or record.revoked_at is not None or record.expires_at <= now:
            raise Unauthorized("auth.token_expired")

        user = (await session.execute(select(User).where(User.id == record.user_id))).scalar_one()
        roles = await rbac.user_role_keys(session, record.tenant_id, user.id)

        # تدوير إلزامي: الرمز المستهلك يُبطل فورًا.
        record.revoked_at = now
        pair = await _issue_pair(session, user, record.tenant_id, roles, mfa_satisfied=True)
        await audit.record(
            session,
            tenant_id=record.tenant_id,
            action="auth.token_refreshed",
            object_type="refresh_token",
            object_id=record.id,
            actor_user_id=user.id,
        )
        return pair


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, principal: Principal = Depends(get_principal)) -> None:
    token_hash = hash_refresh_token(payload.refresh_token)
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        record = (
            await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if record is not None:
            record.revoked_at = dt.datetime.now(dt.UTC)
        await audit.record(
            session,
            tenant_id=principal.tenant_id,
            action="user.logged_out",
            object_type="user",
            object_id=principal.user_id,
            actor_user_id=principal.user_id,
        )


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
async def mfa_enroll(principal: Principal = Depends(get_principal)) -> MfaEnrollResponse:
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        user = (await session.execute(select(User).where(User.id == principal.user_id))).scalar_one()
        secret = new_totp_secret()
        session.add(MfaFactor(user_id=user.id, factor_type="totp", secret_encrypted=secret))
        await audit.record(
            session,
            tenant_id=principal.tenant_id,
            action="mfa.enrolled",
            object_type="user",
            object_id=user.id,
            actor_user_id=user.id,
            reason="TOTP factor created, pending confirmation",
        )
        return MfaEnrollResponse(secret=secret, provisioning_uri=totp_provisioning_uri(secret, user.email))


@router.post("/mfa/verify", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_verify(payload: MfaVerifyRequest, principal: Principal = Depends(get_principal)) -> None:
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        factor = (
            await session.execute(
                select(MfaFactor)
                .where(MfaFactor.user_id == principal.user_id)
                .order_by(MfaFactor.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if factor is None or not verify_totp(factor.secret_encrypted, payload.code):
            raise Unauthorized("auth.mfa_invalid_code")
        factor.confirmed_at = dt.datetime.now(dt.UTC)
        await audit.record(
            session,
            tenant_id=principal.tenant_id,
            action="mfa.confirmed",
            object_type="user",
            object_id=principal.user_id,
            actor_user_id=principal.user_id,
        )


@router.get("/me", response_model=MeResponse)
async def me(principal: Principal = Depends(get_principal)) -> MeResponse:
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        user = (await session.execute(select(User).where(User.id == principal.user_id))).scalar_one()
        factor = (
            await session.execute(
                select(MfaFactor).where(MfaFactor.user_id == user.id,
                                        MfaFactor.confirmed_at.is_not(None))
            )
        ).scalar_one_or_none()
        full_name = (user.full_name_en or user.full_name_ar) if principal.locale == "en" else user.full_name_ar
        return MeResponse(
            user_id=user.id,
            tenant_id=principal.tenant_id,
            email=user.email,
            full_name=full_name,
            full_name_ar=user.full_name_ar,
            full_name_en=user.full_name_en,
            preferred_locale=user.preferred_locale,
            roles=principal.roles,
            mfa_enabled=factor is not None,
        )
