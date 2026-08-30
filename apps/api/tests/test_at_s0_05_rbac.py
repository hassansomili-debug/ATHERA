"""AT-S0-05 — مصفوفة الصلاحيات والفصل بين التحرير والاعتماد (§28، §9)."""
import uuid

import pytest

from athera_api.db import tenant_session
from athera_api.errors import Forbidden
from athera_api.models.identity import ObjectGrant
from athera_api.services import rbac

pytestmark = pytest.mark.asyncio


async def _grant(tenant_id, user_id, object_id, level):
    async with tenant_session(tenant_id, user_id) as session:
        session.add(
            ObjectGrant(
                tenant_id=tenant_id, object_type="file", object_id=object_id,
                user_id=user_id, grant_level=level, granted_by=user_id,
            )
        )


def test_editor_grant_does_not_include_approve():
    """الفصل الحاسم: من يحرّر لا يعتمد. لو انكسر هذا انهارت بوابات §9."""
    from athera_api.services.rbac import _GRANT_ACTIONS

    assert "approve" not in _GRANT_ACTIONS["editor"]
    assert "approve" not in _GRANT_ACTIONS["owner"]
    assert "approve" in _GRANT_ACTIONS["approver"]
    assert "write" not in _GRANT_ACTIONS["approver"]


def test_all_nine_roles_from_spec_are_present():
    assert len(rbac.ROLE_KEYS) == 9
    assert set(rbac.ADMIN_ROLE_KEYS) <= set(rbac.ROLE_KEYS)


async def test_editor_cannot_approve(two_tenants):
    a = two_tenants["a"]
    object_id = uuid.uuid4()
    await _grant(a["tenant_id"], a["user_id"], object_id, "editor")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        actions = await rbac.object_actions(session, a["tenant_id"], a["user_id"], "file", object_id)
        assert "write" in actions and "approve" not in actions
        with pytest.raises(Forbidden):
            await rbac.require_object_action(
                session, a["tenant_id"], a["user_id"], "file", object_id, "approve"
            )


async def test_viewer_cannot_write(two_tenants):
    a = two_tenants["a"]
    object_id = uuid.uuid4()
    await _grant(a["tenant_id"], a["user_id"], object_id, "viewer")
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(Forbidden):
            await rbac.require_object_action(
                session, a["tenant_id"], a["user_id"], "file", object_id, "write"
            )


async def test_no_grant_means_no_access(two_tenants):
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        actions = await rbac.object_actions(
            session, a["tenant_id"], a["user_id"], "file", uuid.uuid4()
        )
    assert actions == frozenset()
