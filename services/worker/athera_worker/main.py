"""تشغيل الـworker | Temporal worker entrypoint."""
import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import record_audit_event, register_approval_request, settle_approval
from .monitoring import TrendMonitorWorkflow, harvest_signals
from .workflows import ApprovalGateWorkflow


async def main() -> None:
    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    worker = Worker(
        client,
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "athera-approvals"),
        workflows=[ApprovalGateWorkflow, TrendMonitorWorkflow],
        activities=[register_approval_request, settle_approval, record_audit_event,
                    harvest_signals],
    )
    print("ATHERA worker ready — بوابات الاعتماد البشري والرصد المجدول جاهزان")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
