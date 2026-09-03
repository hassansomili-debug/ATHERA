"""استعادة كلمة المرور | Password recovery (PUBRIVA).

**الرمز يُولَّد ويُسلَّم مرّة، ولا يُخزَّن.** تُخزَّن تجزئته وحدها، فمن
قرأ الجدول لا يملك ما يُعيد به ضبط كلمة أحد — وهو المبدأ نفسه في
`refresh_tokens`.

**ولا يُفشى وجود الحساب.** الجواب واحدٌ لبريدٍ موجود وبريدٍ ليس موجودًا:
فرقٌ في النصّ أو في زمن الاستجابة يُحوّل هذا المسار إلى أداة تعداد حسابات.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import time
from collections import defaultdict, deque
from typing import Final

from ..config import get_settings
from ..errors import AtheraError

#: صلاحيةٌ قصيرة: رابطٌ مسروق بعدها لا يفتح شيئًا.
TOKEN_TTL_MINUTES: Final = 20
#: طولٌ يجعل التخمين غير وارد.
TOKEN_BYTES: Final = 32


def new_token() -> tuple[str, str]:
    """(الرمز الخام، تجزئته). والخام يُسلَّم للبريد ثم يُنسى."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    """SHA-256 — كما `hash_refresh_token`.

    ولا Argon2 هنا: الرمز عشوائيٌّ بمئتين وستة وخمسين بتًّا، فلا معنى
    لإبطاء تخمينٍ لا يقع. والتجزئة السريعة تسمح بالبحث المباشر بالفهرس.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def expiry(now: dt.datetime) -> dt.datetime:
    return now + dt.timedelta(minutes=TOKEN_TTL_MINUTES)


def recovery_url(raw_token: str, locale: str) -> str:
    """الرابط — **والرمز في الجزء (fragment) لا في الاستعلام**.

    وما بعد `#` لا يُرسَل في طلب HTTP إطلاقًا: لا يبلغ خادم الواجهة، ولا
    يظهر في سجلات وصوله، ولا في ترويسة `Referer` عند الانتقال. والرمز في
    `?query` يُكتب في كل واحدٍ من هذه المواضع.
    """
    base = get_settings().web_base_url.rstrip("/")
    lang = locale if locale in ("ar", "en") else "ar"
    return f"{base}/{lang}/reset-password#token={raw_token}"


def message_body(raw_token: str, locale: str) -> tuple[str, str]:
    """(الموضوع، الجسم) بلغة الباحث."""
    url = recovery_url(raw_token, locale)
    if locale == "en":
        return (
            "Reset your PUBRIVA password",
            "We received a request to reset your PUBRIVA password.\n\n"
            f"Open this link within {TOKEN_TTL_MINUTES} minutes:\n{url}\n\n"
            "The link works once. If you did not request this, ignore this "
            "message — your password stays unchanged.\n",
        )
    return (
        "إعادة تعيين كلمة مرور بُبريفا",
        "وصلنا طلبٌ لإعادة تعيين كلمة مرور حسابك في بُبريفا.\n\n"
        f"افتح هذا الرابط خلال {TOKEN_TTL_MINUTES} دقيقة:\n{url}\n\n"
        "والرابط يعمل مرّة واحدة. وإن لم تطلب ذلك فأهمل هذه الرسالة — "
        "كلمتك تبقى كما هي.\n",
    )


# ══════════ حدّ المعدّل ══════════
#
# **بعدان لا واحد.** الحدّ بالبريد وحده يترك مهاجمًا يعدّ الحسابات ببريدٍ
# مختلف كل مرّة؛ والحدّ بالمصدر وحده يترك من يغيّر مصدره يقصف بريد ضحيةٍ
# بعينها. فيُحَدّ الاثنان.

WINDOW_SECONDS: Final = 900
MAX_PER_EMAIL: Final = 3
MAX_PER_CLIENT: Final = 10

_by_email: dict[str, deque[float]] = defaultdict(deque)
_by_client: dict[str, deque[float]] = defaultdict(deque)


def _hit(bucket: dict[str, deque[float]], key: str, limit: int) -> bool:
    now = time.monotonic()
    window = bucket[key]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    if len(window) >= limit:
        return False
    window.append(now)
    return True


def check_rate(email: str, client: str) -> None:
    # البريد يُجزَّأ قبل أن يصير مفتاحًا: لا عنوان بريدٍ في ذاكرة العملية.
    email_key = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    if not _hit(_by_email, email_key, MAX_PER_EMAIL) or not _hit(
        _by_client, client or "unknown", MAX_PER_CLIENT
    ):
        raise AtheraError("auth.reset_rate_limited", status_code=429)


def reset_rate_limits() -> None:
    """للاختبار وحده."""
    _by_email.clear()
    _by_client.clear()


__all__ = ["MAX_PER_CLIENT", "MAX_PER_EMAIL", "TOKEN_TTL_MINUTES", "check_rate",
           "expiry", "hash_token", "message_body", "new_token", "recovery_url",
           "reset_rate_limits"]
