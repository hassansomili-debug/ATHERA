"""الصلاحيات | RBAC and object-level grants (§28).

طبقتان: دور على مستوى المستأجر، ومنحة على مستوى الكائن. والفصل الحاسم:
`editor` لا يمنح `approve` — من يحرّر لا يعتمد (شرط سلامة بوابات §9).
"""
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import Forbidden
from ..models.identity import Membership, ObjectGrant, Permission, Role, RolePermission

# الأدوار التسعة (§28) — بيانات مرجعية تُزرع في الترحيل، لا ثوابت في منطق الأعمال.
ROLE_KEYS: Final = (
    "researcher", "co_author", "supervisor", "student", "internal_reviewer",
    "research_admin", "college_admin", "institution_admin", "system_admin",
)

ADMIN_ROLE_KEYS: Final = frozenset({"research_admin", "college_admin", "institution_admin", "system_admin"})

GRANT_LEVELS: Final = ("owner", "viewer", "editor", "approver")

# ما تسمح به كل منحة. لاحظ أن editor لا يرث approve.
_GRANT_ACTIONS: Final[dict[str, frozenset[str]]] = {
    "owner": frozenset({"read", "write", "share", "delete"}),
    "editor": frozenset({"read", "write"}),
    "viewer": frozenset({"read"}),
    "approver": frozenset({"read", "approve"}),
}


async def user_role_keys(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[str]:
    rows = (
        await session.execute(
            select(Role.key)
            .join(Membership, Membership.role_id == Role.id)
            .where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        )
    ).scalars().all()
    return list(rows)


async def has_permission(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                         permission_key: str) -> bool:
    row = (
        await session.execute(
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Membership, Membership.role_id == RolePermission.role_id)
            .where(
                Membership.tenant_id == tenant_id,
                Membership.user_id == user_id,
                Permission.key == permission_key,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def object_actions(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                         object_type: str, object_id: uuid.UUID) -> frozenset[str]:
    levels = (
        await session.execute(
            select(ObjectGrant.grant_level).where(
                ObjectGrant.tenant_id == tenant_id,
                ObjectGrant.user_id == user_id,
                ObjectGrant.object_type == object_type,
                ObjectGrant.object_id == object_id,
            )
        )
    ).scalars().all()
    actions: set[str] = set()
    for level in levels:
        actions |= _GRANT_ACTIONS.get(level, frozenset())
    return frozenset(actions)


async def require_object_action(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                                object_type: str, object_id: uuid.UUID, action: str) -> None:
    allowed = await object_actions(session, tenant_id, user_id, object_type, object_id)
    if action not in allowed:
        raise Forbidden("authz.approver_required" if action == "approve" else "authz.forbidden",
                        object_type=object_type, action=action)


async def restricted_fields_for(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
                                object_type: str, object_id: uuid.UUID) -> set[str]:
    """الحقول المقيّدة (§28) — تُحجب عند التسلسل لا بعد إرسالها."""
    rows = (
        await session.execute(
            select(ObjectGrant.restricted_fields).where(
                ObjectGrant.tenant_id == tenant_id,
                ObjectGrant.user_id == user_id,
                ObjectGrant.object_type == object_type,
                ObjectGrant.object_id == object_id,
            )
        )
    ).scalars().all()
    fields: set[str] = set()
    for row in rows:
        fields |= set((row or {}).get("hidden", []))
    return fields
