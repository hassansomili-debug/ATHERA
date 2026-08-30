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

from .db import tenant_session
from .errors import Forbidden, Unauthorized
from .i18n.catalog import negotiate_locale
from .services import rbac


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


async def get_session(principal: Principal = Depends(get_principal)) -> AsyncIterator[AsyncSession]:
    """الجلسة تُفتح دائمًا بسياق المستأجر المستخرج من الرمز — لا من جسم الطلب.

    هذا ما يُبطل هجوم تزوير tenant_id في AT-S0-01: القيمة تأتي من رمز موقّع،
    وحتى لو تسللت قيمة أخرى فإن RLS لا تعرف إلا ما ضُبط هنا.
    """
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        yield session


def require_roles(*role_keys: str):
    async def _guard(principal: Principal = Depends(get_principal)) -> Principal:
        if not set(role_keys) & set(principal.roles):
            raise Forbidden(role_required=",".join(role_keys))
        if set(principal.roles) & rbac.ADMIN_ROLE_KEYS and not principal.mfa_satisfied:
            # §36.1 — MFA إلزامي للأدوار الإدارية.
            raise Unauthorized("auth.mfa_required")
        return principal

    return _guard
