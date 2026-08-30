"""جسر Temporal | Temporal bridge (§9).

يفصل هذا الملف قرار الإنسان عن توفّر Temporal. القرار يُكتب في قاعدتنا
دائمًا؛ وإخطار سير العمل محاولة **إضافية**. لو ربطنا الأمرين، لصار تعطّل
Temporal قادرًا على منع إنسان من اعتماد شيء — وهو عكس ما تعنيه البوابة.

والاتجاه المعاكس ممنوع بالبنية: لا شيء هنا يستطيع **اتخاذ** قرار، بل نقله
فقط. الإشارة تحمل هوية إنسان بعينه.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class SignalOutcome:
    """نتيجة الإخطار — تُعرض ولا تُبتلع صامتة."""

    __slots__ = ("delivered", "reason")

    def __init__(self, delivered: bool, reason: str | None = None) -> None:
        self.delivered = delivered
        self.reason = reason


async def signal_approval_decision(
    *, workflow_id: str, approved: bool, decided_by: str, reason: str | None,
) -> SignalOutcome:
    """يرسل إشارة `submit_decision` إلى سير البوابة المنتظر.

    عدم التوفّر ليس خطأً في الطلب: القرار محفوظ، والسير يستأنف عند إعادة
    التشغيل بقراءة حالة الاعتماد. لذلك تُسجَّل الحالة ولا تُرمى استثناءً.
    """
    if os.getenv("TEMPORAL_ENABLED", "0") != "1":
        return SignalOutcome(False, "temporal is not enabled in this environment")

    try:
        from temporalio.client import Client
    except ImportError:
        logger.warning("temporalio is not installed; approval %s recorded without signal",
                       workflow_id)
        return SignalOutcome(False, "temporalio is not installed")

    try:
        client = await Client.connect(
            os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
        )
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal("submit_decision", {
            "approved": approved, "decided_by": decided_by, "reason": reason,
        })
        return SignalOutcome(True)
    except Exception as exc:  # noqa: BLE001 — الفشل يُسجَّل ولا يُسقط القرار
        logger.warning("could not signal workflow %s: %s", workflow_id, exc)
        return SignalOutcome(False, str(exc))
