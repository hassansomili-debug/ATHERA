"""المستأجرون والعضويات | Tenants and memberships (§28، ADR-0002)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session, require_roles
from ..errors import NotFound
from ..models.identity import Membership, Role, Tenant, User
from ..services import audit

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


class TenantResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    name_ar: str
    name_en: str | None
    default_locale: str
    isolation_mode: str


class MemberAddRequest(BaseModel):
    email: EmailStr
    role_key: str = Field(pattern="^(researcher|co_author|supervisor|student|internal_reviewer|research_admin|college_admin|institution_admin|system_admin)$")


class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    role_key: str
    role_name: str


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TenantResponse:
    # RLS تكفي وحدها لمنع القراءة العابرة؛ الفحص هنا لإعادة رسالة واضحة لا للأمان.
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if tenant is None or tenant.id != principal.tenant_id:
        raise NotFound("tenant.not_found")
    return TenantResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.display(principal.locale),
        name_ar=tenant.name_ar,
        name_en=tenant.name_en,
        default_locale=tenant.default_locale,
        isolation_mode=tenant.isolation_mode,
    )


@router.post("/{tenant_id}/members", response_model=MemberResponse,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    tenant_id: uuid.UUID,
    payload: MemberAddRequest,
    principal: Principal = Depends(require_roles("research_admin", "institution_admin", "system_admin")),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    if tenant_id != principal.tenant_id:
        raise NotFound("tenant.not_found")

    user = (
        await session.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise NotFound("auth.invalid_credentials")

    role = (
        await session.execute(
            select(Role).where(Role.tenant_id == tenant_id, Role.key == payload.role_key)
        )
    ).scalar_one_or_none()
    if role is None:
        raise NotFound("authz.forbidden")

    membership = Membership(tenant_id=tenant_id, user_id=user.id, role_id=role.id)
    session.add(membership)
    await session.flush()

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="membership.granted",
        object_type="membership",
        object_id=membership.id,
        actor_user_id=principal.user_id,
        state_after={"user_id": str(user.id), "role_key": role.key},
        reason="admin granted membership",
        request_id=principal.request_id,
    )
    return MemberResponse(
        membership_id=membership.id,
        user_id=user.id,
        email=user.email,
        role_key=role.key,
        role_name=role.display(principal.locale),
    )


@router.get("/{tenant_id}/members", response_model=list[MemberResponse])
async def list_members(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[MemberResponse]:
    if tenant_id != principal.tenant_id:
        raise NotFound("tenant.not_found")
    rows = (
        await session.execute(
            select(Membership, User, Role)
            .join(User, User.id == Membership.user_id)
            .join(Role, Role.id == Membership.role_id)
        )
    ).all()
    return [
        MemberResponse(
            membership_id=m.id,
            user_id=u.id,
            email=u.email,
            role_key=r.key,
            role_name=r.display(principal.locale),
        )
        for m, u, r in rows
    ]
