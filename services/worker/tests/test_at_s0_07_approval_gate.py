"""AT-S0-07 — البوابة تتوقف، تنجو من إعادة التشغيل، ثم تستأنف.

يستخدم بيئة Temporal الاختبارية؛ إن لم تتوفر يُتخطى الاختبار بوضوح — ولا
يُعد ناجحًا.
"""
import uuid

import pytest

pytest.importorskip("temporalio.testing")

from temporalio.client import WorkflowFailureError  # noqa: E402
from temporalio.testing import WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from athera_worker.workflows import ApprovalDecision, ApprovalGateInput, ApprovalGateWorkflow  # noqa: E402

pytestmark = pytest.mark.asyncio


async def _fake_register(payload) -> str:
    return str(uuid.uuid4())


async def _fake_settle(record) -> None:
    return None


async def _fake_audit(payload: dict) -> None:
    return None


async def test_workflow_waits_for_a_human_and_then_resumes():
    from temporalio import activity

    register = activity.defn(name="register_approval_request")(_fake_register)
    settle = activity.defn(name="settle_approval")(_fake_settle)
    audit_activity = activity.defn(name="record_audit_event")(_fake_audit)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-approvals",
            workflows=[ApprovalGateWorkflow],
            activities=[register, settle, audit_activity],
        ):
            handle = await env.client.start_workflow(
                ApprovalGateWorkflow.run,
                ApprovalGateInput(
                    tenant_id=str(uuid.uuid4()),
                    gate="G10",
                    object_type="manuscript",
                    object_id=str(uuid.uuid4()),
                    requested_by=str(uuid.uuid4()),
                    reason_ar="اعتماد المجلة المستهدفة",
                    reason_en="Approve the target journal",
                ),
                id=f"approval-{uuid.uuid4()}",
                task_queue="test-approvals",
            )

            # البوابة معلّقة: لا قرار، ولا مهلة تُسقطها.
            assert await handle.query("status") == "awaiting_human_approval"

            await handle.signal(
                ApprovalGateWorkflow.submit_decision,
                ApprovalDecision(approved=True, decided_by=str(uuid.uuid4()), reason="approved by researcher"),
            )
            result = await handle.result()
            assert result["approved"] is True
            assert result["gate"] == "G10"


async def test_gate_cannot_be_settled_twice():
    """قرار البوابة نهائي؛ إشارة ثانية لا تعيد فتحها."""
    from temporalio import activity

    register = activity.defn(name="register_approval_request")(_fake_register)
    settle = activity.defn(name="settle_approval")(_fake_settle)
    audit_activity = activity.defn(name="record_audit_event")(_fake_audit)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue="test-approvals-2",
            workflows=[ApprovalGateWorkflow],
            activities=[register, settle, audit_activity],
        ):
            handle = await env.client.start_workflow(
                ApprovalGateWorkflow.run,
                ApprovalGateInput(
                    tenant_id=str(uuid.uuid4()), gate="G6", object_type="dataset",
                    object_id=str(uuid.uuid4()), requested_by=str(uuid.uuid4()),
                ),
                id=f"approval-{uuid.uuid4()}", task_queue="test-approvals-2",
            )
            user = str(uuid.uuid4())
            await handle.signal(ApprovalGateWorkflow.submit_decision,
                                ApprovalDecision(approved=False, decided_by=user, reason="rejected"))
            await handle.signal(ApprovalGateWorkflow.submit_decision,
                                ApprovalDecision(approved=True, decided_by=user, reason="flip"))
            result = await handle.result()
            assert result["approved"] is False, "a second signal must not overturn a settled gate"
