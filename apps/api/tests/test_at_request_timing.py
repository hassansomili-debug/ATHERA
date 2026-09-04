"""زمنُ الاستجابة يُقاس ولا يحمل شيئًا من الباحث.

**البطء كان يُشتكى منه ولا يُقاس.** «المنصّة بطيئة» جملةٌ لا تُصلَّح: لا
تقول أيّ مسار، ولا كم، ولا هل هو الشبكة أم الاستعلام. فكنّا نخمّن ثم
نُحسّن ما لم يكن بطيئًا.

وقياسٌ يحمل معرّفات الباحث يشتري التشخيص بثمنٍ لا يجوز دفعه.
"""
from __future__ import annotations

import pathlib

MAIN = (pathlib.Path(__file__).resolve().parents[1]
        / "athera_api" / "main.py").read_text(encoding="utf-8")


def test_every_response_carries_its_duration():
    """الزمن يُقاس حول تنفيذ الطلب كلّه — لا حول جزءٍ منه."""
    assert "time.perf_counter()" in MAIN, "لا قياس زمن"
    assert 'response.headers["Server-Timing"]' in MAIN, (
        "الزمن لا يصل إلى المتصفّح، فيبقى البطء مرئيًّا من السجلّ وحده")


def test_the_log_carries_the_route_template_not_the_filled_path():
    """**القالب لا المسار.**

    المسار المملوء يحمل معرّفات الباحث وملفّاته: `/api/v1/files/<uuid>`.
    والقالب يجيب عن السؤال نفسه — «أيّ نقطة بطيئة» — بلا أن يحمل شيئًا
    من ذلك.
    """
    assert 'request.scope.get("route")' in MAIN, "المسار يُسجَّل مملوءًا"
    assert 'getattr(route, "path", None)' in MAIN, "القالب لا يُقرأ من الموجّه"
    # ولا يُسجَّل المسار الخام بحالٍ.
    assert "request.url.path" not in MAIN, "المسار الخام يُسجَّل"
    assert "str(request.url)" not in MAIN, "الرابط كاملًا يُسجَّل"


def test_the_log_carries_no_body_no_query_no_headers():
    """لا أجسام، ولا استعلامات، ولا ترويسات — ولا نصّ مستند ولا موجّه نموذج."""
    # وسائطُ نداء التسجيل وحدها — لا الملفّ كلّه: الوسيط يقرأ ترويسة
    # `x-request-id` بحقّ، وقراءتُها ليست تسجيلًا لها.
    start = MAIN.index("_timing.log(")
    call = MAIN[start:MAIN.index("\n    )", start)]
    for forbidden in ("request.query_params", "request.headers", "request.body",
                      "request.cookies", "response.body", "request.url"):
        assert forbidden not in call, f"القياس يحمل {forbidden}"
    # ولا يُسجَّل إلا ما أُعلن: الطريقة والقالب والحال والزمن والمعرّف.
    assert "request.method" in call and "template" in call and "duration_ms" in call


def test_slow_requests_are_announced_not_buried():
    """**بطءٌ في سطرٍ عادي بين آلاف لا يُرى.** فما تجاوز الحدّ يُعلَن تحذيرًا."""
    assert "SLOW_REQUEST_MS" in MAIN, "لا حدّ للبطء"
    assert "logging.WARNING if duration_ms >= SLOW_REQUEST_MS else logging.INFO" in MAIN, (
        "البطء يُسجَّل كغيره")
