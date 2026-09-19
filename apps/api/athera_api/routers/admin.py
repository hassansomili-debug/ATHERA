"""لوحة الإدارة V1 | Admin Console V1 (Stage 9) — **قراءةٌ وحدَها**.

**حارسٌ واحد**، مشتقٌّ من `rbac.ADMIN_ROLE_KEYS` لا من قائمةٍ منسوخة، ويمرّ
بـ`require_roles` فيرث سياسةَ MFA المركزيّة كما هي — لا منطقَ MFA ثانٍ.

**والجلسةُ جلسةُ الطلب العاديّة** (`get_session`): سياقُ RLS من الرمز. فلا
`BYPASSRLS`، ولا مفتاحُ خدمة، ولا اتصالُ مالك، ولا `system_session`، ولا
مستأجرٌ من المتصفّح — **لا مُعاملَ `tenant_id` في أيّ مسارٍ هنا أصلًا**.

**ولا طفرة.** لا تعطيلَ حسابٍ ولا تفعيله، ولا انتحالَ هُويّة، ولا منحَ دور،
ولا حذف — كلُّها مُحالةٌ إلى المرحلة ١٠ بقرار، لا سهوًا.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_session, require_roles
from ..schemas import admin as S
from ..services import admin_console as console
from ..services import rbac

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

#: **الحارسُ القانونيّ الوحيد** — والأدوارُ من مصدرها في `rbac`.
admin_guard = require_roles(*sorted(rbac.ADMIN_ROLE_KEYS))


@router.get("/overview", response_model=S.AdminOverview)
async def overview(
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminOverview:
    return await console.overview(session, tid=principal.tenant_id, roles=principal.roles,
                                  locale=principal.locale)


@router.get("/users", response_model=S.AdminUserPage)
async def users(
    search: str | None = Query(default=None, max_length=200),
    role: str | None = Query(default=None, max_length=64),
    active: bool | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=512),
    limit: int | None = Query(default=None, ge=1, le=console.MAX_PAGE),
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminUserPage:
    return await console.list_users(
        session, tid=principal.tenant_id, locale=principal.locale, search=search,
        role=role, active=active, cursor=cursor, limit=limit)


@router.get("/users/{user_id}", response_model=S.AdminUserDetail)
async def user_detail(
    user_id: uuid.UUID,
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminUserDetail:
    return await console.user_detail(session, tid=principal.tenant_id,
                                     locale=principal.locale, user_id=user_id)


@router.get("/projects", response_model=S.AdminProjectPage)
async def projects(
    search: str | None = Query(default=None, max_length=200),
    lifecycle: str | None = Query(default=None, pattern="^(active|archived|trashed)$"),
    owner_id: uuid.UUID | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=512),
    limit: int | None = Query(default=None, ge=1, le=console.MAX_PAGE),
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminProjectPage:
    return await console.list_projects(
        session, tid=principal.tenant_id, locale=principal.locale, search=search,
        lifecycle=lifecycle, owner_id=owner_id, cursor=cursor, limit=limit)


@router.get("/usage", response_model=S.AdminUsage)
async def usage(
    window: str = Query(default="30d", pattern="^(7d|30d|90d)$"),
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminUsage:
    return await console.usage(session, tid=principal.tenant_id, window=window)


@router.get("/operations", response_model=S.AdminOperations)
async def operations(
    view: str = Query(default="failed", pattern="^(failed|in_progress|all)$"),
    limit: int | None = Query(default=None, ge=1, le=console.MAX_OPS),
    principal: Principal = Depends(admin_guard),
    session: AsyncSession = Depends(get_session),
) -> S.AdminOperations:
    return await console.operations(session, tid=principal.tenant_id,
                                    locale=principal.locale, view=view, limit=limit)
