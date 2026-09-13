"""حقولُ «ما نعرفه عن هذا البحث» — مفردةٌ واحدة | The nine knowledge fields.

**بيانٌ خالص، ولا استيرادَ فيه إلا من المكتبة القياسية.** وهذا شرطُ موضعه:
تسعُ حقولٍ بأسمائها ودورها، تقرؤها الشاشةُ والجسرُ والتقرير.

## ولمَ انتقلت من `services/workspace.py`

كانت تسكن هناك، فكان كلُّ من أراد أسماءَ الحقول التسعة **يرث معه مركزَ
الرسائل**: `workspace` تستورد `models.thesis` لتعدّ فرصَ النشر وحالَ معالجة
الملفات، و`models.thesis` تستورد `services.thesis.vocab`.

    research_assessment.view → services.workspace → models.thesis

وأمسك هذه السلسلةَ عقدُ الاستيراد في `pyproject.toml` (§79): أساسُ العقل
لا يقوم على وحدةٍ مؤجَّلة. **والاتجاهُ الصحيح معكوس** — الوحدةُ المجالية
تعتمد على مفردات العقل، لا العكس. فـ`workspace` تستورد من هنا الآن.

**ولم يتغيّر اسمٌ ولا قيمة:** `workspace.BRAIN_FIELDS` يبقى موجودًا ويُعيد
تصدير ما هنا، فكلُّ نداءٍ وكلُّ فحصٍ قائم يعمل كما كان.
"""
from __future__ import annotations

from typing import Final

#: الحقلُ: مفتاحُه، واسمُه بلغتين، والأدوارُ التي تُسنده في مفردات الأدلة.
#:
#: **و«ناقص» حالٌ مشروعة** لا عيب: بحثٌ في أوله لا يعرف نتائجه، وقولُ
#: المنصّة إنّه يعرفها كذبٌ يُبنى عليه.
BRAIN_FIELDS: Final[tuple[tuple[str, str, str, tuple[str, ...]], ...]] = (
    ("problem", "مشكلة البحث", "Research problem", ("problem",)),
    ("question", "سؤال البحث", "Research question", ("question",)),
    ("objective", "الأهداف", "Objectives", ("objective",)),
    ("theory", "الإطار النظري", "Theory", ("theory",)),
    ("method", "المنهج وأداة القياس", "Method and instrument", ("methodology",)),
    ("sample", "العيّنة", "Sample", ("sample",)),
    ("data", "التحليل", "Analysis", ("analysis",)),
    ("results", "النتائج", "Results", ("result",)),
    ("limitations", "حدود الدراسة", "Limitations", ("limitation",)),
)

__all__ = ["BRAIN_FIELDS"]
