"""حدّ معدّل بسيط لأثيرا AI (§22).

**ليس نظامًا فرعيًا جديدًا.** نافذة منزلقة في ذاكرة العملية، بمفتاح
(مستأجر، مستخدم). تكفي لمنع حلقة عميل مندفعة ولاستدعاء متكرر بلا قصد،
وهما ما يحرق حصة مزوّد فعلًا.

وحدّها معلن: عملية واحدة تعني عدّادًا لكل عملية. مع آلة واحدة اليوم هذا
دقيق؛ ومع أكثر من آلة يصير الحدّ لكل آلة لا لكل مستأجر — وذلك يحتاج عدّادًا
مشتركًا (Redis) حين يأتي التوسّع، لا اليوم.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from typing import Final

from ..errors import AtheraError

WINDOW_SECONDS: Final = 60
MAX_CALLS_PER_WINDOW: Final = 12

_calls: dict[tuple[uuid.UUID, uuid.UUID], deque[float]] = defaultdict(deque)


def check(tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    now = time.monotonic()
    window = _calls[(tenant_id, user_id)]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    if len(window) >= MAX_CALLS_PER_WINDOW:
        raise AtheraError(
            "ai.rate_limited", status_code=429,
            retry_after_seconds=int(WINDOW_SECONDS - (now - window[0])) + 1,
        )
    window.append(now)


def reset() -> None:
    """للاختبار وحده."""
    _calls.clear()
