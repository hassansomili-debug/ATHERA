"""عنوانُ البحث كما يُعرض | Project title presentation.

**هذا تنفيذٌ محلّي لعقدٍ مشترك يعرّفه المسار «ب».** وحتى يصل العقد المشترك،
تُطبَّق قواعدُه هنا حرفيًّا كي لا تختلف شاشتان في اسم البحث الواحد؛ ومتى وصل
حُذف هذا الملف واستُدعي مكانَه. والطلبُ مكتوب في
`docs/integration/track-f-requests.md`.

القاعدتان:

  ١ **عنوانٌ فارغ يُسمّى «مشروع بدون عنوان»** ولا يُترك فراغًا ولا يُملأ
    بشيءٍ آخر. وسطرٌ بلا عنوان في قائمةٍ يُقرأ عطبًا في الشاشة، والباحث
    يبحث عن بحثه فلا يجده.

  ٢ **وتاريخُ الإنشاء يُعرض حقلًا مستقلًّا لا داخل العنوان.** ودمجُه في
    العنوان هو أصلُ العطب الذي جاء منه `«قبول 2026-09-09T17:12…»`: طابعٌ
    زمنيّ كُتب عنوانًا، فصار اسمَ البحث في كل شاشة.

**وما لا يُفعل هنا مقصودٌ كما يُفعل.** لا يُحذف عنوانٌ مخزَّن لأنّه *يشبه*
طابعًا زمنيًّا: كاشفٌ كهذا يخفي عنوانًا مشروعًا كتبه باحثٌ فيه تاريخ، وإخفاءُ
عنوانٍ صحيح أسوأ من عرضِ عنوانٍ رديء — الأول يُفقد البحث، والثاني يُصحَّح
بتحريره. فالعناوينُ المشوَّهة الموجودة اليوم بياناتُ اختبارٍ تُنظَّف من
مصدرها، لا تُخفى من عارضها.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# العنوان البديل — نصُّ العقد المشترك حرفيًّا.
UNTITLED_AR = "مشروع بدون عنوان"
UNTITLED_EN = "Untitled project"


@dataclass(frozen=True, slots=True)
class PresentedTitle:
    """العنوان معروضًا، ومعه ما يقول إنّه بديل — لا يُخلط الأمران.

    `is_fallback` تجعل الشاشة قادرةً على تمييز «بحثٌ لم يُسمَّ بعد» من بحثٍ
    اسمُه هكذا؛ ولولاها لعُرض البديل عنوانًا حقيقيًّا.
    """

    title: str
    is_fallback: bool
    created_at: dt.datetime | None = None


def present(working_title_ar: str | None,
            working_title_en: str | None = None,
            *,
            locale: str = "ar",
            created_at: dt.datetime | None = None) -> PresentedTitle:
    """يعيد العنوان المعروض — والفراغ وحده هو ما يستدعي البديل."""
    preferred = working_title_en if locale == "en" else working_title_ar
    # الإنجليزية تسقط إلى العربية قبل أن تسقط إلى البديل: عنوانٌ عربيّ
    # مخزَّن أصدقُ من «Untitled» على بحثٍ له اسم.
    candidate = (preferred or "").strip() or (working_title_ar or "").strip()
    if candidate:
        return PresentedTitle(title=candidate, is_fallback=False, created_at=created_at)
    return PresentedTitle(
        title=UNTITLED_EN if locale == "en" else UNTITLED_AR,
        is_fallback=True,
        created_at=created_at,
    )
