"""خنق محاولات الدخول | Login attempt throttling.

**لماذا الآن؟** كان التحقق بخطوتين هو الحاجز الثاني أمام كلمة مرور مسروقة
أو مخمَّنة على الحسابات الإدارية. ورفعُه عن الدخول الاعتيادي — وهو القرار
المتّخذ — يجعل كلمة المرور الحاجز الوحيد. وحاجزٌ واحد بلا حدّ محاولات يعني
أن التخمين الآلي مسألة وقت لا مسألة قدرة.

**وليس نظامًا فرعيًا جديدًا:** نفس شكل `ai_rate_limit` — نافذة منزلقة في
ذاكرة العملية. وحدُّه معلن: عدّادٌ لكل عملية، فمع أكثر من آلة يصير الحدّ لكل
آلة. اليوم آلة واحدة (`min_machines_running = 1`)، فالحدّ دقيق. والتوسّع
يحتاج عدّادًا مشتركًا، ويُسجَّل دَينًا لا يُدَّعى حلُّه.

**والمفتاح بريدٌ لا مستخدم:** المحاولة تفشل قبل أن يُعرف المستخدم، والخنق
يجب أن يعمل على بريد لا وجود له أيضًا — وإلا صار الفرق في السلوك بين بريد
موجود وآخر غير موجود طريقةً لعدّ الحسابات.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Final

from ..errors import AtheraError

WINDOW_SECONDS: Final = 300
MAX_FAILURES_PER_WINDOW: Final = 8

_failures: dict[str, deque[float]] = defaultdict(deque)


def _prune(key: str, now: float) -> deque[float]:
    window = _failures[key]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    return window


def check(email: str) -> None:
    """يُستدعى **قبل** فحص كلمة المرور — ولا يفشي أي شيء عن الحساب."""
    now = time.monotonic()
    window = _prune(email.strip().lower(), now)
    if len(window) >= MAX_FAILURES_PER_WINDOW:
        raise AtheraError(
            "auth.too_many_attempts", status_code=429,
            retry_after_seconds=int(WINDOW_SECONDS - (now - window[0])) + 1,
        )


def record_failure(email: str) -> None:
    _prune(email.strip().lower(), time.monotonic()).append(time.monotonic())


def record_success(email: str) -> None:
    """دخولٌ ناجح يمسح العدّاد — فلا يُعاقب صاحب الحساب بمحاولاته هو."""
    _failures.pop(email.strip().lower(), None)


def reset() -> None:
    """للاختبار وحده."""
    _failures.clear()
