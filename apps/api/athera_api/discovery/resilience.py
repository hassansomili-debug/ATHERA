"""صمود المزوّدين | Bounded retries for external indexes.

فهرسٌ يردّ ٥٠٣ مرّةً واحدة ليس فهرسًا معطوبًا، وإعلانُ تعذّره من أول
محاولة يحرم الباحث من نصف ما يعرفه العالم عن سؤاله لأجل ارتعاشةٍ في
الشبكة. وإعادةُ المحاولة بلا سقفٍ أسوأ: تُبقي الباحث أمام شاشةٍ لا تقول
شيئًا، وتضاعف مرورنا على فهرسٍ يشكو أصلًا من الحمل — فيُحجب عنّا.

فالقيود ثلاثة، وكلها معلنة هنا لا مبثوثة في كل مزوّد:

**١ عددُ محاولاتٍ محدود**، **٢ تراجعٌ تصاعدي بين المحاولات**، **٣ ميزانية
زمنٍ كلّية** تُنهي الأمر ولو بقيت محاولات. والثالثة هي التي تجعل السقف
حقيقيًّا: ثلاث محاولاتٍ بمهلة ثمانٍ لكل واحدة تعني أربعًا وعشرين ثانية من
الانتظار الصامت، وهي عمليًّا انقطاع.

**والتمييز بين ما يُعاد وما لا يُعاد جوهر الباب.** ٥٠٣ و٤٢٩ عوارض؛ و٤٠٠
و٤٠١ أحكامٌ لا تتبدّل بالتكرار، فإعادتها إسرافٌ في مرورٍ لن ينفع. و٤٠٤
ليست عطبًا أصلًا: هي جواب الفهرس «لا أعرف هذا» — وهو جوابٌ يُنقل لا يُعاد
السؤال عنه.

وهذه الطبقة **لا تعرف httpx**: تأخذ نداءً وتعيد قاموسًا. فتُختبر في CI
بلا شبكة، وهو شرطٌ قائمٌ في هذه الحزمة.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from .base import ProviderUnavailable

# عوارضُ حملٍ أو عطبٍ عابر: تُعاد المحاولة.
RETRYABLE_STATUS: frozenset[int] = frozenset({408, 425, 429, 500, 502, 503, 504})

# ثلاث محاولات: الأولى، ثم إعادتان. الرابعة لا تضيف احتمالًا يُذكر وتضيف
# انتظارًا يراه الباحث.
DEFAULT_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = 0.4
# سقف التراجع: بلا سقفٍ يبلغ الانتظار دقائق عند رقمٍ صغير من المحاولات.
MAX_BACKOFF_SECONDS = 2.0
# الميزانية الكلّية لهذا المزوّد في هذه التشغيلة، مهلًا وتراجعًا.
DEFAULT_BUDGET_SECONDS = 20.0

# ردٌّ فهرسيّ: (رمز الحالة، الحمولة). والحمولة `None` حين لا جسم في الرد.
Send = Callable[[], Awaitable[tuple[int, dict | None]]]


def backoff_delay(attempt: int, *, base: float = DEFAULT_BACKOFF_SECONDS) -> float:
    """تراجعٌ تصاعدي حتميّ بلا عشوائية.

    العشوائية تنفع حين تتزاحم آلاف العُقد على فهرسٍ واحد؛ وهنا مزوّدان في
    طلبٍ واحد لباحثٍ واحد، فثمنُها الوحيد أن يصير الاختبار غير حتميّ —
    وهو ثمنٌ لا يقابله نفع في هذا الحجم.
    """
    return min(MAX_BACKOFF_SECONDS, base * (2 ** max(0, attempt - 1)))


async def fetch_json(
    send: Send,
    *,
    provider: str,
    attempts: int = DEFAULT_ATTEMPTS,
    backoff: float = DEFAULT_BACKOFF_SECONDS,
    budget: float = DEFAULT_BUDGET_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict:
    """ينادي الفهرس بمحاولاتٍ محدودة، ويعلن التعذّر باسمه حين تنفد.

    و`{}` هنا تعني «أجاب الفهرس ولا يعرف» — وهي غير التعذّر تمامًا؛ الخلط
    بينهما هو ما يجعل الشاشة تقول «لا نتائج» والشبكة هي المعطوبة.
    """
    started = clock()
    last_detail = "Unknown"
    for attempt in range(1, max(1, attempts) + 1):
        try:
            status, payload = await send()
        except Exception as exc:  # noqa: BLE001 — كل تعذّرٍ يُترجم إلى نوعٍ مُعلَن
            last_detail = type(exc).__name__
        else:
            # ٤٠٤ جوابٌ لا عطب: الفهرس يقول «لا أعرف هذا المعرّف».
            if status == 404:
                return {}
            if 200 <= status < 300:
                return payload or {}
            last_detail = f"HTTP {status}"
            if status not in RETRYABLE_STATUS:
                # حكمٌ لا يتبدّل بالتكرار — فلا يُكرَّر.
                raise ProviderUnavailable(provider, last_detail)

        if attempt >= attempts:
            break
        delay = backoff_delay(attempt, base=backoff)
        if (clock() - started) + delay >= budget:
            # الميزانية نفدت: يُعلَن التعذّر الآن بدل أن يُنتظر ما لن يُنتظر.
            last_detail = f"{last_detail} (budget)"
            break
        await sleep(delay)
    raise ProviderUnavailable(provider, last_detail)
