"""عنوانُ المشروع كما يُعرض | The project-title presentation contract (PUBRIVA).

**عيبٌ حقيقيّ وقع**: عُرضت للباحث بحوثٌ عناوينها من هذا النوع —

    قبول 2026-09-09T17:12:41.883012+00:00

وهذه ليست عنوانًا. هي نصُّ حدثٍ في سجلّ التدقيق ووقتُه، لُصقا معًا وعُرضا
في موضع العنوان. فيقرأ الباحث قائمة بحوثه ولا يعرف أيّها بحثه.

## القاعدة

  **لا يُصنَع عنوانٌ من شيء.** لا من نصِّ تدقيق، ولا من طابعٍ زمني، ولا من
  أول جملةٍ في ملفّ، ولا من اسم ملفٍّ مرفوع.

فإن لم يكن للبحث عنوانُ عملٍ ذو معنًى، قيل ذلك صراحةً — «مشروع بدون
عنوان» — وعُرض تاريخ الإنشاء **في حقلٍ منفصل**، وأُتيحت إعادة التسمية.
وثلاثتها معًا: الإعلان بلا سبيلٍ إلى التصحيح يترك الباحث حيث هو.

## لماذا هذا الملف عقدٌ مشترك

الوحدات الأخرى تعرض عناوين البحوث أيضًا (المحفظة، الفريق، الخيط الذهبي،
سلّة المهملات). ولو نُسخت القاعدة في كل شاشة لعادت الشاشةُ الخامسة تعرض
`قبول 2026-…` بعد أن أُصلحت أربع. فالقاعدة هنا، ونظيرتها الحرفية في
`apps/web/src/lib/projectTitle.ts`، ويقابل بينهما اختبار.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Final

# **العنوان الذي يُعرض حين لا عنوان.** جملةٌ واحدة، بلا رقمٍ فيها — ورقمٌ
# في عنوانٍ بديل هو أول خطوةٍ نحو تلفيقٍ يبدو معلومة.
PLACEHOLDER_AR: Final = "مشروع بدون عنوان"
PLACEHOLDER_EN: Final = "Untitled project"

# طابعٌ زمنيّ بصيغة ISO — `2026-09-09T17:12:41` وما شابهها. **لا يكتب باحثٌ
# هذا في عنوان ورقة**، فوجودُه شاهدُ تلفيقٍ لا اختيارِ صاحبه.
_ISO_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")

# نصٌّ لا يحمل حرفًا واحدًا — أرقامٌ وتواريخُ وعلاماتُ ترقيم وحدها.
_HAS_A_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ProjectTitle:
    """العنوان المعروض وحاله — **وحالُه تُعلَن ولا تُخمَّن من شكل النصّ**.

    و`created_at` حقلٌ مستقلّ عمدًا: من ضمّه إلى العنوان أنتج العيب الذي
    كُتب هذا الملف لأجله. ومن قرأ هذا العقد لا يستطيع ضمَّه بغير قصد.
    """

    display_ar: str
    display_en: str
    is_placeholder: bool
    # سببُ البديل — للسجلّ وللشاشة، فلا يُقال «بدون عنوان» بلا تفسير.
    reason: str | None
    created_at: dt.datetime | None
    can_rename: bool = True


def _is_manufactured(value: str) -> str | None:
    """هل هذا النصّ عنوانٌ كتبه إنسان، أم أثرٌ لُصق في موضع العنوان؟

    ثلاثُ حالاتٍ ترفض، ولا رابعة — والتضييق مقصود: **رفضُ عنوانٍ صحيح أسوأ
    من قبول عنوانٍ رديء**. باحثٌ سمّى بحثه «دراسة ٢٠٢٤» يجب أن يرى اسمه
    كما كتبه، لا «مشروع بدون عنوان» يمحو اختياره.
    """
    if not value:
        return "blank"
    if _ISO_TIMESTAMP.search(value):
        # `قبول 2026-09-09T17:12:41.883012+00:00` — بعينه.
        return "audit_timestamp"
    if not _HAS_A_LETTER.search(value):
        # `2026-09-09` أو `12:41` أو `— —` — لا حرف فيه.
        return "no_letters"
    return None


def project_title(working_title_ar: str | None, *,
                  created_at: dt.datetime | None = None,
                  working_title_en: str | None = None) -> ProjectTitle:
    """العقد: نصٌّ يُعرض كما كتبه صاحبه، أو بديلٌ يقول إنه بديل.

    **ولا حالة ثالثة.** لا تركيبَ عنوانٍ من التاريخ، ولا من أول كلماتٍ في
    وصف، ولا من اسم مجلّة مستهدَفة. ومن أراد عنوانًا للبحث فليكتبه.
    """
    trimmed = (working_title_ar or "").strip()
    reason = _is_manufactured(trimmed)
    if reason is not None:
        return ProjectTitle(display_ar=PLACEHOLDER_AR, display_en=PLACEHOLDER_EN,
                            is_placeholder=True, reason=reason,
                            created_at=created_at, can_rename=True)

    english = (working_title_en or "").strip()
    if _is_manufactured(english) is not None:
        english = trimmed

    return ProjectTitle(display_ar=trimmed, display_en=english or trimmed,
                        is_placeholder=False, reason=None,
                        created_at=created_at, can_rename=True)


__all__ = ["PLACEHOLDER_AR", "PLACEHOLDER_EN", "ProjectTitle", "project_title"]
