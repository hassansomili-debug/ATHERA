"""حدُّ معدّلٍ للاكتشاف | Discovery search rate limit.

**كل بحثٍ هنا نداءان خارجيان.** Crossref وOpenAlex يمنحاننا الاستعمال بأدبٍ
لا بعقد: هويّةٌ في الترويسة، وجهةُ اتصال، ومرورٌ معقول. وحلقةُ عميلٍ مندفعة
— أو حقلُ بحثٍ يُرسل مع كل حرف — تحرق هذا الائتمان في دقائق، فيُحجب مرورنا
عن **كل** المستأجرين لا عن صاحب الحلقة وحده.

فالحدّ هنا حمايةٌ لبقيّة الباحثين من واحدٍ منهم، لا تقنينٌ للخدمة. ولذلك
سقفه سخيّ: باحثٌ يكتب استعلامًا ويعدّله ويعيد بحثه لا يبلغه أبدًا.

**و٤٢٩ تُعلَن بمهلة انتظار.** «حاول لاحقًا» بلا رقمٍ تجعل العميل يعيد
المحاولة فورًا فيطيل حبسه بنفسه؛ والرقم يجعل الانتظار قابلًا للبرمجة.

ونافذةٌ منزلقة في ذاكرة العملية تكفي لهذا الغرض بالضبط: مع أكثر من آلة
يصير الحدّ لكل آلة لا لكل مستأجر — وهو ما يزال يمنع الحلقة المندفعة، وهي
الغاية. والعدّاد المشترك يأتي مع التوسّع لا قبله.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable, Hashable

WINDOW_SECONDS = 60.0
# ثلاثون بحثًا في الدقيقة: أكثر مما يفعله باحثٌ يفكّر، وأقلّ بكثير ممّا
# تفعله حلقةٌ معطوبة في ثانية.
MAX_SEARCHES_PER_WINDOW = 30

_windows: dict[Hashable, deque[float]] = defaultdict(deque)


def check(key: Hashable, *, clock: Callable[[], float] = time.monotonic) -> int:
    """يعيد `0` إن كان المرور مسموحًا، أو ثوانيَ الانتظار إن تجاوز الحدّ.

    والقيمة المعادة عدد ثوانٍ لا استثناء: هذه الوحدة نقيّة لا تعرف HTTP،
    والراوتر هو من يترجمها إلى ٤٢٩ برسالةٍ مترجمة.
    """
    now = clock()
    window = _windows[key]
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()
    if len(window) >= MAX_SEARCHES_PER_WINDOW:
        return int(WINDOW_SECONDS - (now - window[0])) + 1
    window.append(now)
    return 0


def reset() -> None:
    """للاختبار وحده — لا يُنادى في مسارٍ حيّ."""
    _windows.clear()
