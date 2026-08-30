"""بوابة الاعتماد البشري كسير عمل دائم | Human approval gate as a durable workflow.

هذا ليس مثالًا تعليميًا: بوابات §9 كلها (G0…G12، GT1) ستُبنى على هذا النمط
بالضبط — سير عمل يتوقف بلا أجل، ينتظر قرار إنسان، وينجو من إعادة تشغيل
الـworker وترقية النشر. إن لم يثبت هذا في Sprint 0، انهارت البوابات لاحقًا.

AT-S0-07 يختبر هذا السلوك تحديدًا.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        ApprovalRecord,
        record_audit_event,
        register_approval_request,
        settle_approval,
    )


@dataclasses.dataclass(slots=True)
class ApprovalGateInput:
    tenant_id: str
    gate: str            # G0..G12, GT1
    object_type: str
    object_id: str
    requested_by: str
    reason_ar: str | None = None
    reason_en: str | None = None


@dataclasses.dataclass(slots=True)
class ApprovalDecision:
    approved: bool
    decided_by: str
    reason: str | None = None


@workflow.defn(name="ApprovalGateWorkflow")
class ApprovalGateWorkflow:
    """يتوقف عند البوابة إلى أجل غير مسمى — لا مهلة تُسقط القرار البشري تلقائيًا."""

    def __init__(self) -> None:
        self._decision: ApprovalDecision | None = None
        self._approval_id: str | None = None

    @workflow.run
    async def run(self, payload: ApprovalGateInput) -> dict:
        retry = RetryPolicy(maximum_attempts=5)

        self._approval_id = await workflow.execute_activity(
            register_approval_request,
            payload,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # الانتظار بلا مهلة: البوابة البشرية لا تُتجاوز بانقضاء وقت (§9، §4).
        await workflow.wait_condition(lambda: self._decision is not None)
        decision = self._decision
        assert decision is not None

        await workflow.execute_activity(
            settle_approval,
            ApprovalRecord(
                approval_id=self._approval_id,
                tenant_id=payload.tenant_id,
                approved=decision.approved,
                decided_by=decision.decided_by,
                reason=decision.reason,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        await workflow.execute_activity(
            record_audit_event,
            {
                "tenant_id": payload.tenant_id,
                "action": "approval.decided",
                "object_type": payload.object_type,
                "object_id": payload.object_id,
                "actor_user_id": decision.decided_by,
                "reason": decision.reason,
                "approval_id": self._approval_id,
                "state_after": {"gate": payload.gate, "approved": decision.approved},
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )
        return {"approval_id": self._approval_id, "approved": decision.approved, "gate": payload.gate}

    @workflow.signal(name="submit_decision")
    async def submit_decision(self, decision: ApprovalDecision) -> None:
        """الإشارة الوحيدة القادرة على تحريك البوابة — ولا يرسلها إلا إنسان."""
        if self._decision is None:
            self._decision = decision

    @workflow.query(name="status")
    def status(self) -> str:
        if self._decision is None:
            return "awaiting_human_approval"
        return "approved" if self._decision.approved else "rejected"
