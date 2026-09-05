"""دورةُ حياة البيانات الاصطناعية | the synthetic-data lifecycle contract.

**الشكُّ يعني «حقيقي».** كلُّ فحصٍ هنا يحمي جهةً واحدة: ألّا يُصنَّف صفُّ
باحثٍ حقيقيّ اصطناعيًّا. والخطأ في الجهة الأخرى يترك صفًّا زائدًا في قاعدة،
والخطأ في هذه يمحو عمل إنسان.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from athera_api.synthetic import (
    SYNTHETIC_EMAIL_DOMAIN,
    SYNTHETIC_PREFIXES,
    classify,
    is_synthetic_email,
    synthetic_email,
)

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"


@pytest.mark.parametrize("email", [
    "pubriva-accept-1a2b3c@example.com",
    "pubriva-smoke-9ea1b0b5@example.com",
    # **الطابعُ الزمنيّ بشُرَطه** — وهو ما تكتبه رحلةُ القبول فعلًا، وهو
    # الذي أسقط أوّلَ صياغةٍ لهذا المصنّف فعدّ اثنين وثلاثين حسابًا حقيقيّة.
    "pubriva-accept-2026-09-04t17-12-33-451z@example.com",
    "pubriva-accept-2026-09-04T17:12:33.451Z@example.com",
])
def test_a_marked_account_is_recognised(email: str):
    assert is_synthetic_email(email)
    assert classify(email) == "synthetic"


@pytest.mark.parametrize("email", [
    "pubriva-accept-1a2b3c@pubriva.com",     # بادئةٌ مسجّلة ونطاقٌ حقيقيّ
    "hmsomili@gmail.com",
    "research.lab@university.edu.sa",
])
def test_a_real_account_is_never_called_synthetic(email: str):
    """**هذا هو الفحص الذي يمنع محوَ عمل إنسان.**

    والبادئةُ وحدها لا تكفي: من سجّل على نطاقٍ حقيقيّ فهو حقيقيّ ولو وافق
    اسمُه بادئةً مسجّلة.
    """
    assert not is_synthetic_email(email)
    assert classify(email) == "real"


@pytest.mark.parametrize("email", [
    "ahmed@example.com",           # نطاقٌ محجوز وبادئةٌ غير مسجّلة
    "accept-1a2b3c@example.com",   # بادئةٌ مشابهة غير مسجّلة
    "pubriva-perf-9@example.com",  # أثرُ قياسِ أداءٍ قديم
])
def test_an_unknown_marker_is_flagged_not_silently_called_real(email: str):
    """**ما لا يُعرف مصدرُه يُقال، لا يُبتلع.**

    `example.com` نطاقٌ محجوزٌ للتوثيق لا يستقبل بريدًا، فحسابٌ عليه ليس
    باحثًا حقيقيًّا. وعدُّه «حقيقيًّا» يُخفيه من التقرير إلى الأبد؛ وعدُّه
    «اصطناعيًّا» يساويه بما نعرف من أنشأه. فله اسمٌ ثالث يُعرَض على المالك.

    **وليس هذا إذنًا بحذف**: لا شيء في هذا الملفّ يحذف، ولا صنفَ فيه يعني
    «احذفني».
    """
    assert classify(email) == "review_candidate"
    assert not is_synthetic_email(email), "مجهولُ المصدر ليس معروفَ المصدر"


def test_the_legacy_incident_is_known_but_kept_apart():
    """أثرُ 2026-08-31 يُعرَف ولا يُخلط: له أداتُه وقرارُ مالكه."""
    assert classify("test-a-1a2b3c4d@example.test") == "legacy_incident"
    assert not is_synthetic_email("test-a-1a2b3c4d@example.test")


def test_a_marker_is_built_from_the_registry_not_written_beside_it():
    assert synthetic_email("pubriva-smoke", "abc123") == \
        f"pubriva-smoke-abc123@{SYNTHETIC_EMAIL_DOMAIN}"
    with pytest.raises(ValueError):
        synthetic_email("some-unregistered-prefix", "abc123")


def test_every_registered_prefix_says_who_creates_it():
    """بادئةٌ بلا سببٍ مكتوب تصير لغزًا بعد شهر، فلا يجرؤ أحدٌ على تنظيفها."""
    for prefix, reason in SYNTHETIC_PREFIXES.items():
        assert re.fullmatch(r"[a-z-]+", prefix), f"{prefix}: بادئةٌ غير قياسيّة"
        assert len(reason) > 20, f"{prefix}: بلا سببٍ مفهوم"


def test_the_browser_journey_uses_the_registered_marker():
    """**السجلُّ واحد أو ليس سجلًّا.**

    رحلةُ القبول تُنشئ الحساب على الإنتاج، فلو كتبت بادئةً من عندها لافترقت
    عن السجلّ يومًا، ونجا صفٌّ من كل تنظيفٍ لأنّ أداته تبحث عن بادئةٍ لم تعد
    تُكتب. فيُطلب أن يبقى ما تكتبه موافقًا لما هنا.
    **وكلُّ رقعةٍ تُسجّل حسابًا، لا رحلةُ القبول وحدها.** كان الفحص يقرأ
    ملفًّا واحدًا باسمه، فرقعةٌ ثانية تبني بريدًا من عندها تمرّ بلا سؤال —
    وهي بعينها الحال التي وُجد الفحص لأجلها. فتُقرأ الرقعات كلُّها.
    """
    specs = sorted((WEB / "tests").glob("*.spec.ts")) if (WEB / "tests").exists() else []
    if not specs:                               # pragma: no cover
        pytest.skip("رقعاتُ المتصفّح غير موجودة في هذه الشجرة")

    found_any = False
    for spec in specs:
        text = spec.read_text(encoding="utf-8")
        for prefix, domain in re.findall(r"`([a-z-]+)-\$\{[^}]+\}@([a-z.]+)`", text):
            found_any = True
            assert prefix in SYNTHETIC_PREFIXES, (
                f"{spec.name} تكتب بادئة {prefix!r} غير مسجّلة في "
                "athera_api.synthetic — فلن يتعرّف عليها أيُّ تقرير تنظيف")
            assert domain == SYNTHETIC_EMAIL_DOMAIN, (
                f"{spec.name} تسجّل على {domain!r} لا {SYNTHETIC_EMAIL_DOMAIN!r}")

    assert found_any, "لم يُعثر على بريدٍ مُركَّب في أيّ رقعة — تغيّرت الصيغة"
