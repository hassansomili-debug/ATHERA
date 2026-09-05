"""علامةُ البيانات الاصطناعية | the synthetic-data marker, in one place.

**البياناتُ الاصطناعية تُعرَف بالبناء لا بالتحقيق.**

سكربتُ `cleanup_test_artifacts.py` يتعرّف على أثر حادثةٍ بعينها بخمس إشاراتٍ
مجتمعة — وهو عملُ محقّقٍ بعد وقوع الأمر، ونجح لأنّ الحادثة معروفةُ الشكل
والنافذة. ولا يصلح ذلك قاعدةً دائمة: رحلةُ القبول تسجّل حسابًا على الإنتاج
في **كل** تشغيلةٍ على `main`، فيتراكم صفٌّ لا يميّزه شيء إلّا أن يُستنبط.

فالعلامةُ تُكتب عند الإنشاء، ومن سجلٍّ واحد. ولو كُتبت البادئة في رحلة
القبول، وثانيةً في سكربت الدخان، وثالثةً في أداة التنظيف — لافترقت الثلاث
يومًا، ولنجا صفٌّ من التنظيف لأنّ أداته تبحث عن بادئةٍ لم تعد تُكتب.

**ولا يُحذف من الإنتاج شيءٌ بهذا الملفّ.** هو تعريفٌ وقراءةٌ فحسب؛ والحذف
قرارُ المالك، وله مسارُه المُدقَّق.
"""
from __future__ import annotations

import re
from typing import Final

#: النطاق الوحيد المسموح لحسابٍ اصطناعيّ. و`.test` مرفوضٌ من مُحقِّق البريد
#: (نطاقٌ محجوز)، فالتسجيل عليه يُردّ ٤٢٢ — ولذلك `example.com`.
SYNTHETIC_EMAIL_DOMAIN: Final = "example.com"

#: بادئاتٌ معروفة، كلٌّ منها يقول **من** أنشأ الصفّ ولماذا.
SYNTHETIC_PREFIXES: Final[dict[str, str]] = {
    "pubriva-accept": "رحلةُ القبول بمتصفّحٍ حقيقي على الإنتاج (CI، كل تشغيلة main)",
    "pubriva-smoke": "دخانٌ يدويّ بعد النشر — يُشغَّل عمدًا وقليلًا",
    # **بيئةُ المرشَّح (rc-e2e) معزولةٌ تمامًا ولا تلمس الإنتاج**: قاعدتها
    # خدمةٌ في المهمّة تموت معها. والبادئة مسجّلة هنا لا لأنّ صفًّا سينجو
    # — بل لأنّ رقعةَ الرحلة تبني بريدًا، والحارس يطلب أن يكون مصدرُه هذا
    # السجلّ. فلو سُرّبت الرحلةُ يومًا إلى قاعدةٍ باقية، عُرف مَن كتب الصفّ.
    "pubriva-rc": "رحلةُ المرشَّح للإصدار بمتصفّح حقيقي (CI، قاعدةٌ معزولة تُهدَم)",
}

#: أثرُ حادثة 2026-08-31: `test-a-xxxxxxxx` على `@example.test`. يُعرَف ولا
#: يُنشأ: أداةُ التنظيف الخاصّة به قائمة، وذكرُه هنا كي لا يُحسب حقيقيًّا.
LEGACY_INCIDENT_TENANT_PATTERN: Final = re.compile(r"^test-[ab]-[0-9a-f]{8}$")
LEGACY_INCIDENT_EMAIL_DOMAIN: Final = "example.test"

def _split(email: str) -> tuple[str, str]:
    local, _, domain = email.strip().lower().partition("@")
    return local, domain


def synthetic_email(prefix: str, stamp: str) -> str:
    """يبني بريدًا اصطناعيًّا من السجلّ — ولا يُكتب حرفيًّا في موضعٍ آخر."""
    if prefix not in SYNTHETIC_PREFIXES:
        raise ValueError(f"بادئةٌ غير مسجّلة: {prefix!r}")
    return f"{prefix}-{stamp}@{SYNTHETIC_EMAIL_DOMAIN}"


def is_synthetic_email(email: str) -> bool:
    """هل هذا البريد اصطناعيٌّ **بعلامةٍ كُتبت عمدًا**؟

    **والمطابقةُ بالبادئة لا بشكلٍ كامل.** أوّلُ صياغةٍ هنا اشترطت خاتمةً من
    حروفٍ وأرقامٍ فقط، ورحلةُ القبول تختم بطابعٍ زمنيّ فيه شُرَط. فابتلعت
    البادئةُ الطمّاعة الطابعَ كلَّه، وصار `pubriva-accept-2026-09-04t17-12`
    بادئةً غير مسجّلة، فعُدَّ الحسابُ **حقيقيًّا**.

    وظهر ذلك في أوّل تشغيلةٍ على الإنتاج: اثنان وثلاثون حسابَ قبولٍ قائمة،
    والتقرير يقول «لا تراكم». وهو أسوأ اتّجاهٍ للخطأ: تقريرٌ يطمئن كذبًا.
    """
    local, domain = _split(email)
    return domain == SYNTHETIC_EMAIL_DOMAIN and any(
        local.startswith(prefix + "-") for prefix in SYNTHETIC_PREFIXES)


def is_legacy_incident_email(email: str) -> bool:
    """أثرُ الحادثة القديمة — يُعرَف، ولأداته الخاصّة، ولا يُخلط بالجديد."""
    return _split(email)[1] == LEGACY_INCIDENT_EMAIL_DOMAIN


def classify(email: str) -> str:
    """أربعُ حالات — و**لا واحدةَ منها إذنٌ بالحذف**.

    - `synthetic`: بادئةٌ مسجّلة على النطاق المحجوز. معروفُ المصدر.
    - `legacy_incident`: أثرُ 2026-08-31، وله أداتُه.
    - `review_candidate`: على النطاق المحجوز ببادئةٍ **غير** مسجّلة. لا
      يُقال عنه «حقيقي» فيختفي من التقرير، ولا «اصطناعي» فيُعامَل معاملةَ
      ما يُعرف مصدره. يُعرَض على المالك باسمه: هذا لا نعرف من أنشأه.
    - `real`: الافتراض، وما عداه استثناءٌ يُبرَّر.
    """
    if is_legacy_incident_email(email):
        return "legacy_incident"
    if is_synthetic_email(email):
        return "synthetic"
    if _split(email)[1] == SYNTHETIC_EMAIL_DOMAIN:
        return "review_candidate"
    return "real"
