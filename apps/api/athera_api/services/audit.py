"""كتابة سجل التدقيق | Audit writing (§37، §39، ADR-0004).

قاعدتان لا تُخترقان:
  1. الكتابة تقع داخل نفس المعاملة التي تعدّل الحالة — لا حدث يُفقد بعد commit.
  2. السلسلة لكل مستأجر: hash = sha256(prev_hash || canonical_json(payload)).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from ..models.audit import AuditEvent

GENESIS_HASH = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    """تمثيل حتمي — ترتيب المفاتيح وعدم تهريب الحروف العربية."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def event_payload(event: AuditEvent) -> dict[str, Any]:
    """الحقول الداخلة في التجزئة — أي تغيير لاحق عليها يكسر السلسلة."""
    return {
        "tenant_id": str(event.tenant_id),
        "occurred_at": event.occurred_at.isoformat(),
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "actor_kind": event.actor_kind,
        "action": event.action,
        "object_type": event.object_type,
        "object_id": str(event.object_id) if event.object_id else None,
        "state_before": event.state_before,
        "state_after": event.state_after,
        "reason": event.reason,
        "agent_run_id": str(event.agent_run_id) if event.agent_run_id else None,
        "model_run_id": str(event.model_run_id) if event.model_run_id else None,
        "approval_id": str(event.approval_id) if event.approval_id else None,
        "chain_seq": event.chain_seq,
    }


async def record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: str,
    object_type: str,
    object_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    actor_kind: str = "user",
    state_before: dict | None = None,
    state_after: dict | None = None,
    reason: str | None = None,
    agent_run_id: uuid.UUID | None = None,
    model_run_id: uuid.UUID | None = None,
    approval_id: uuid.UUID | None = None,
    source_refs: list | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    # تسلسل السلسلة لكل مستأجر يحتاج تسلسلًا بين الكاتبين. و`FOR UPDATE`
    # غير ممكن هنا: PostgreSQL يشترط صلاحية UPDATE على الجدول، وهي منزوعة
    # عمدًا لجعل السجل append-only (§37). القفل الاستشاري يحقق التسلسل نفسه
    # بصلاحية SELECT وحدها، وينتهي بانتهاء المعاملة.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext('athera_audit_chain'), hashtext(:tid))"),
        {"tid": str(tenant_id)},
    )
    last = (
        await session.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.chain_seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    prev_hash = last.hash if last else GENESIS_HASH
    seq = (last.chain_seq + 1) if last else 1

    event = AuditEvent(
        tenant_id=tenant_id,
        occurred_at=dt.datetime.now(dt.UTC),
        actor_user_id=actor_user_id,
        actor_kind=actor_kind,
        action=action,
        object_type=object_type,
        object_id=object_id,
        state_before=state_before,
        state_after=state_after,
        reason=reason,
        agent_run_id=agent_run_id,
        model_run_id=model_run_id,
        approval_id=approval_id,
        source_refs=source_refs,
        request_id=request_id,
        ip_address=ip_address,
        chain_seq=seq,
        prev_hash=prev_hash,
        hash="",
    )
    event.hash = compute_hash(prev_hash, event_payload(event))
    session.add(event)
    await session.flush()
    return event


async def verify_chain(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, int | None]:
    """التحقق من السلسلة | verify the chain.

    يعيد (سليمة؟، رقم أول سجل مكسور). AT-S0-03 يعتمد عليها.
    """
    events = (
        await session.execute(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.chain_seq.asc())
        )
    ).scalars().all()

    prev = GENESIS_HASH
    for event in events:
        if event.prev_hash != prev:
            return False, event.chain_seq
        if compute_hash(prev, event_payload(event)) != event.hash:
            return False, event.chain_seq
        prev = event.hash
    return True, None


async def count_for_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        )
    ).scalar_one()
