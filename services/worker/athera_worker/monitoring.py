"""الرصد المجدول | Scheduled trend monitoring (§51.11).

«تشغيل مراقبة مجدولة في الخلفية دون إبقاء جلسة مفتوحة» — هذا سيرها.

ثلاثة قيود تُفرض هنا بالبنية لا بالتعليق:
  • الرصد **يجمع إشارات** ولا يُنشئ بطاقات فرص. البطاقة تحتاج سؤالًا وفجوة،
    وهما قرار بحثي لا ناتج جدولة.
  • كل إشارة تُكتب بمصدرها ومعرّفها وتاريخها، أو لا تُكتب (§51.11).
  • النشرة تُنتَج حتى لو كانت فارغة، فيبقى الصمت مفهومًا: الرصد عمل ولم يجد.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy


@dataclasses.dataclass(slots=True)
class MonitorInput:
    tenant_id: str
    watchlist_id: str
    user_id: str
    cadence: str = "weekly"


@dataclasses.dataclass(slots=True)
class HarvestResult:
    """ما جمعته دورة رصد واحدة. الأصفار قيمة صالحة تُنقل كما هي."""

    signals_recorded: int = 0
    signals_rejected: int = 0
    trends_touched: int = 0


async def _persist_signal(session, tenant_id, watchlist_id, candidate: dict) -> None:
    """يكتب الإشارة، وينشئ الاتجاه إن لم يكن موجودًا.

    لا يُعاد تصديق الاتجاه هنا: التصديق يقع عند مسار الإشارة في الـAPI بسياسة
    المؤسسة، وتكراره بسياسة افتراضية في الخلفية كان سيعطي حكمين مختلفين
    للبيانات نفسها.
    """
    from sqlalchemy import select

    from athera_api.models.trends import ResearchTrend, TrendSignalRow
    from athera_api.services.trends.vocab import SIGNAL_SOURCE_TYPES

    trend = (
        await session.execute(
            select(ResearchTrend).where(ResearchTrend.trend_key == candidate["trend_key"])
        )
    ).scalar_one_or_none()
    if trend is None:
        trend = ResearchTrend(
            tenant_id=tenant_id, trend_key=candidate["trend_key"],
            label_ar=candidate["trend_label_ar"], discovered_at=dt.datetime.now(dt.UTC),
            status="candidate",
        )
        session.add(trend)
        await session.flush()

    duplicate = (
        await session.execute(
            select(TrendSignalRow).where(
                TrendSignalRow.trend_id == trend.id,
                TrendSignalRow.source_id == candidate["source_id"],
            )
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        # نفس المصدر مرصود مرتين لا يضاعف الدليل — وإلا صار تكرار التشغيل
        # وحده كافيًا لتصديق اتجاه.
        return

    session.add(TrendSignalRow(
        tenant_id=tenant_id, trend_id=trend.id, watchlist_id=watchlist_id,
        pattern=candidate["pattern"], source_type=candidate["source_type"],
        source_id=candidate["source_id"], observed_at=candidate["observed_at"],
        weight=candidate.get("weight", 1.0),
        counts_as_evidence=SIGNAL_SOURCE_TYPES[candidate["source_type"]],
        detail_ar=candidate.get("detail_ar"),
    ))


@activity.defn
async def harvest_signals(payload: MonitorInput) -> HarvestResult:
    """يقرأ ملف المراقبة ويستدعي السجلات المهيّأة ثم يكتب الإشارات الصالحة.

    الإشارة التي تفشل التحقق تُعدّ مرفوضة **ويُبلَّغ عنها**، ولا تُكتب ولا
    تُصلَّح. تصحيحها هنا يعني اختراع مصدر أو تاريخ لم يأتِ من السجل.
    """
    import uuid

    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.trends import ResearchWatchlist
    from athera_api.services.trends import signals as signal_rules

    tenant_id = uuid.UUID(payload.tenant_id)
    result = HarvestResult()

    async with tenant_session(tenant_id, uuid.UUID(payload.user_id)) as session:
        watchlist = (
            await session.execute(
                select(ResearchWatchlist).where(
                    ResearchWatchlist.id == uuid.UUID(payload.watchlist_id)
                )
            )
        ).scalar_one_or_none()
        if watchlist is None or not watchlist.is_active:
            return result

        # السجل يُحقن من الإعداد: نفس طبقة Sprint 4 القابلة للتبديل، وبلا
        # شبكة في الاختبار. لا استدعاء شبكة مكتوب هنا مباشرةً.
        from athera_api.services.literature.registry_factory import get_registry
        from athera_api.services.trends import harvest as harvester

        terms = [
            *(watchlist.keywords or []),
            *(watchlist.theories or []),
            *(watchlist.methods or []),
        ]
        outcome = await harvester.harvest(get_registry(), terms=terms)
        result.signals_rejected = outcome.rejected

        seen_trends: set[str] = set()
        for candidate in outcome.candidates:
            try:
                signal_rules.TrendSignal(
                    signal_id="pending", trend_key=candidate["trend_key"],
                    source_type=candidate["source_type"], source_id=candidate["source_id"],
                    observed_at=candidate["observed_at"], pattern=candidate["pattern"],
                    weight=float(candidate.get("weight", 1.0)),
                )
            except signal_rules.SignalError:
                # مرشّح مرّ من الحصاد وسقط عند العقد: يُعدّ مرفوضًا ولا يُصلَّح.
                result.signals_rejected += 1
                continue
            await _persist_signal(session, tenant_id, watchlist.id, candidate)
            seen_trends.add(candidate["trend_key"])
            result.signals_recorded += 1
        result.trends_touched = len(seen_trends)

        watchlist.last_refreshed_at = dt.datetime.now(dt.UTC)
    return result


@workflow.defn(name="TrendMonitorWorkflow")
class TrendMonitorWorkflow:
    """دورة رصد واحدة. التكرار مسؤولية Temporal Schedule لا حلقة داخلية.

    الحلقة الداخلية كانت ستجعل السير يعمل إلى الأبد، فيصعب إيقافه أو تغيير
    وتيرته — والجدول كائن مستقل يُعدَّل ويُوقَف بلا لمس الكود.
    """

    @workflow.run
    async def run(self, payload: MonitorInput) -> dict:
        harvest = await workflow.execute_activity(
            harvest_signals,
            payload,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        return {
            "watchlist_id": payload.watchlist_id,
            "signals_recorded": harvest.signals_recorded,
            "signals_rejected": harvest.signals_rejected,
            # لا حقل «فرص مكتشفة»: الرصد لا يصنع فرصًا (§51.4).
        }
