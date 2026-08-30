"""جداول الرصد | Monitoring schedules (§51.11).

الجدول كائن مستقل عن السير: يُنشأ ويُوقَف ويُغيَّر إيقاعه بلا لمس الكود،
ولا يبقى شيء «يعمل إلى الأبد» في حلقة داخلية يصعب إيقافها.

`--dry-run` يطبع ما سيُنشأ ولا ينشئ: جدول يبدأ يستدعي سجلات خارجية، وبدء
ذلك بالخطأ ليس شيئًا يُكتشف بعد ساعة.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
)

from .monitoring import MonitorInput, TrendMonitorWorkflow

# §51.2 — الإيقاعات المتاحة. القيمة فترة، والاسم ما يظهر للمستخدم.
CADENCES: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
}


def schedule_id(watchlist_id: str) -> str:
    return f"athera-watch-{watchlist_id}"


async def upsert_watchlist_schedule(
    client: Client, *, tenant_id: str, watchlist_id: str, user_id: str,
    cadence: str = "weekly",
) -> str:
    """ينشئ جدول رصد لملف مراقبة، أو يحدّث إيقاعه إن كان قائمًا."""
    if cadence not in CADENCES:
        raise ValueError(f"unknown cadence: {cadence}")

    sid = schedule_id(watchlist_id)
    action = ScheduleActionStartWorkflow(
        TrendMonitorWorkflow.run,
        MonitorInput(tenant_id=tenant_id, watchlist_id=watchlist_id,
                     user_id=user_id, cadence=cadence),
        id=f"{sid}-run",
        task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "athera-approvals"),
    )
    schedule = Schedule(
        action=action,
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=CADENCES[cadence])]),
        # التخطي لا التراكم: دورة رصد تأخرت لا يُعوَّض عنها بدورتين متلاحقتين
        # تكتبان الإشارة نفسها مرتين.
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
    )
    try:
        await client.create_schedule(sid, schedule)
    except Exception:  # noqa: BLE001 — قائم مسبقًا: يُحدَّث لا يُكرَّر
        handle = client.get_schedule_handle(sid)
        await handle.update(lambda _: schedule)
    return sid


async def pause_watchlist_schedule(client: Client, watchlist_id: str, *, note: str) -> None:
    """الإيقاف بسبب مكتوب — جدول متوقف بلا سبب يُعاد تشغيله بلا فهم."""
    handle = client.get_schedule_handle(schedule_id(watchlist_id))
    await handle.pause(note=note)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="ATHERA monitoring schedules")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--watchlist-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--cadence", default="weekly", choices=sorted(CADENCES))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"سيُنشأ الجدول {schedule_id(args.watchlist_id)} "
              f"بإيقاع {args.cadence} ({CADENCES[args.cadence]})")
        return

    client = await Client.connect(
        os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
    )
    sid = await upsert_watchlist_schedule(
        client, tenant_id=args.tenant_id, watchlist_id=args.watchlist_id,
        user_id=args.user_id, cadence=args.cadence,
    )
    print(f"الجدول جاهز: {sid}")


if __name__ == "__main__":
    asyncio.run(_main())
