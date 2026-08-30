"""أنشطة سير العمل | Workflow activities — كل أثر جانبي يقع هنا لا داخل الـworkflow."""
from __future__ import annotations

import dataclasses
import datetime as dt
import uuid

from temporalio import activity


@dataclasses.dataclass(slots=True)
class ApprovalRecord:
    approval_id: str
    tenant_id: str
    approved: bool
    decided_by: str
    reason: str | None = None


@activity.defn
async def register_approval_request(payload) -> str:
    """ينشئ صف approvals بحالة pending ويعيد معرّفه."""
    from athera_api.db import tenant_session
    from athera_api.models.audit import Approval
    from athera_api.services import audit

    tenant_id = uuid.UUID(payload.tenant_id)
    async with tenant_session(tenant_id, uuid.UUID(payload.requested_by)) as session:
        approval = Approval(
            tenant_id=tenant_id,
            gate=payload.gate,
            object_type=payload.object_type,
            object_id=uuid.UUID(payload.object_id),
            status="pending",
            requested_by=uuid.UUID(payload.requested_by),
            reason=payload.reason_ar or payload.reason_en,
            workflow_id=activity.info().workflow_id,
        )
        session.add(approval)
        await session.flush()
        await audit.record(
            session,
            tenant_id=tenant_id,
            action="approval.requested",
            object_type=payload.object_type,
            object_id=uuid.UUID(payload.object_id),
            actor_user_id=uuid.UUID(payload.requested_by),
            approval_id=approval.id,
            state_after={"gate": payload.gate, "status": "pending"},
        )
        return str(approval.id)


@activity.defn
async def settle_approval(record: ApprovalRecord) -> None:
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.audit import Approval

    tenant_id = uuid.UUID(record.tenant_id)
    async with tenant_session(tenant_id, uuid.UUID(record.decided_by)) as session:
        approval = (
            await session.execute(select(Approval).where(Approval.id == uuid.UUID(record.approval_id)))
        ).scalar_one()
        approval.status = "approved" if record.approved else "rejected"
        approval.decided_by = uuid.UUID(record.decided_by)
        approval.decided_at = dt.datetime.now(dt.UTC)
        approval.reason = record.reason


@activity.defn
async def record_audit_event(payload: dict) -> None:
    from athera_api.db import tenant_session
    from athera_api.services import audit

    tenant_id = uuid.UUID(payload["tenant_id"])
    actor = payload.get("actor_user_id")
    async with tenant_session(tenant_id, uuid.UUID(actor) if actor else None) as session:
        await audit.record(
            session,
            tenant_id=tenant_id,
            action=payload["action"],
            object_type=payload["object_type"],
            object_id=uuid.UUID(payload["object_id"]) if payload.get("object_id") else None,
            actor_user_id=uuid.UUID(actor) if actor else None,
            reason=payload.get("reason"),
            approval_id=uuid.UUID(payload["approval_id"]) if payload.get("approval_id") else None,
            state_after=payload.get("state_after"),
        )
