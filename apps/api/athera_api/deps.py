"""تبعيات الطلب | Request dependencies — سلسلة المسار الإلزامي (§38.6.8).

الترتيب ليس تفصيلًا: المصادقة ← سياق المستأجر (يفعّل RLS) ← الصلاحيات ←
السياسة ← المعالج. أي التفاف على هذه السلسلة يعني فقدان العزل أو التدقيق.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .db import scoped_tenant, tenant_session
from .errors import Forbidden, Unauthorized
from .i18n.catalog import negotiate_locale
from .services import rbac
from .transaction import register_request_session


@dataclass(slots=True)
class Principal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    roles: list[str]
    mfa_satisfied: bool
    locale: str
    request_id: str | None = None
    ip_address: str | None = None


def get_locale(accept_language: str | None = Header(default=None, alias="Accept-Language")) -> str:
    return negotiate_locale(accept_language)


async def get_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    locale: str = Depends(get_locale),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("auth.invalid_credentials")
    token = authorization.split(" ", 1)[1].strip()
    try:
        from .security import decode_access_token

        claims = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("auth.token_expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("auth.invalid_credentials") from exc

    return Principal(
        user_id=uuid.UUID(claims["sub"]),
        tenant_id=uuid.UUID(claims["tid"]),
        roles=list(claims.get("roles", [])),
        mfa_satisfied=bool(claims.get("mfa", False)),
        locale=locale,
        request_id=request.headers.get("x-request-id"),
        ip_address=request.client.host if request.client else None,
    )


async def get_session(
    request: Request, principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    """الجلسة تُفتح دائمًا بسياق المستأجر المستخرج من الرمز — لا من جسم الطلب.

    هذا ما يُبطل هجوم تزوير tenant_id في AT-S0-01: القيمة تأتي من رمز موقّع،
    وحتى لو تسللت قيمة أخرى فإن RLS لا تعرف إلا ما ضُبط هنا.

    **والإيداعُ ليس لهذه التبعيّة** (RC-T1-H1): لو بقي لها لوقع في فكِّ
    حزمةِ الطلب — أي بعد أن يأخذ العميلُ «تمّ». فتُسجَّل الجلسةُ على
    الطلب، ويُودِعها `TransactionalRoute` قبل إرسال الجواب. والرجوعُ
    والإغلاقُ يبقيان هنا.
    """
    async with tenant_session(
        principal.tenant_id, principal.user_id, owns_commit=False,
    ) as session:
        register_request_session(request, session)
        yield session


async def get_project_session(
    project_id: uuid.UUID, request: Request,
    principal: Principal = Depends(get_principal),
) -> AsyncIterator[AsyncSession]:
    """جلسةُ بحثٍ — **تعبُر إلى مستأجره إن كان للفاعل فيه مدخلٌ مُثبت**.

    وهي التجهيزةُ الوحيدةُ التي يُعاد بها ربطُ المستأجر داخل طلب، فلا
    يُنسخ `set_config` في موجّه. و`project_id` يُقرأ من **مسار** الطلب،
    و`principal` من رمزٍ موقَّع — ولا مستأجرَ بحثٍ يأتي من جسمٍ ولا ترويسة.

    والتفويضُ ليس هنا: هذه تفتح بابَ السياق، و`ensure_project_access` تقف
    خلفها. ومَن قرأ `principal.tenant_id` بعد العبور سأل عن المستأجر
    الخطأ — فيُقرأ `scoped_tenant(session)`.
    """
    from .db import project_session

    # **والإيداعُ للطلب لا للتبعيّة** — انظر `get_session` وRC-T1-H1.
    async with project_session(project_id, principal.tenant_id,
                               principal.user_id, owns_commit=False) as session:
        register_request_session(request, session)
        yield session


def project_tenant(session: AsyncSession, principal: Principal) -> uuid.UUID:
    """مستأجرُ البحثِ النافذُ على هذه الجلسة — **لا مستأجرُ الرمز**.

    فبعد عبور `get_project_session` لم يعد `principal.tenant_id` هو
    مستأجرَ المعاملة: متعاونٌ من مؤسسةٍ أخرى يعمل في مستأجر البحث.
    ومسارٌ يقرأ مستأجرَ رمزه بعد العبور يسأل عن المستأجر الخطأ — **فيقرأ
    صفرَ صفوفٍ إن قرأ، ويكتب في المستأجر الخطأ إن كتب**، وهذا الثاني
    أسوأُ من عطبٍ ظاهر: صفٌّ يُخزَّن حيث لا يراه أحد.

    وفي المسار المحليّ — صاحبُ البحث وزميلُه في مؤسسته — لا ربطَ يقع
    أصلًا، فتُعيد هذه الدالّةُ مستأجرَ الرمز نفسَه. فالسلوكُ القائم لا
    يتغيّر، والمسارُ الواحد يخدم الحالتين بلا فرعٍ يُكتب له.
    """
    scoped = scoped_tenant(session)
    return scoped if scoped is not None else principal.tenant_id


def require_roles(*role_keys: str):
    async def _guard(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(role_keys) & set(principal.roles):
            raise Forbidden(role_required=",".join(role_keys))
        # §36.1 — MFA للأدوار الإدارية، وقابليته للإطفاء إعدادٌ لا استثناء.
        #
        # كان الفحص هنا مفروضًا بصرف النظر عن `mfa_required_for_admin_roles`،
        # بينما يحترمه مسار الدخول. النتيجة تناقض: دخول ينجح ثم كل مسار إداري
        # يُرفض بـ«التحقق بخطوتين مطلوب» بلا سبيل إلى تحقيقه. الموضعان يقرآن
        # الإعداد نفسه الآن، فيتفق ما يُسمح به عند الباب وما يُسمح به بعده.
        from .config import get_settings  # noqa: PLC0415 — يتجنّب استيرادًا دائريًا

        if (
            get_settings().mfa_required_for_admin_roles
            and set(principal.roles) & rbac.ADMIN_ROLE_KEYS
            and not principal.mfa_satisfied
        ):
            raise Unauthorized("auth.mfa_required")
        return principal

    return _guard
