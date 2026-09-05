"""إدارة المشروع البحثي | Research project management (PUBRIVA).

**مشروعٌ علميّ لا لوحُ مهامّ.** والفرق يظهر فيما ترفض هذه الوحدة أن تقوله:
لا نسبةَ إنجاز، ولا «جاهزية بحثية»، ولا مرحلةٍ تدّعيها المنصّة عن الباحث،
ولا مهمّةٍ تدخل قائمته بلا قبولٍ منه.

  `vocab`        المفردات بلغتيها — مقابَلةٌ بقائمة النموذج اختبارًا
  `stages`       اقتراحُ المرحلة التالية — يُشتقّ ولا يُخزَّن، ويحمل سنده
  `titles`       عقدُ عرض عنوان المشروع — مشترَكٌ مع بقيّة الوحدات
  `attention`    «ما الذي يحتاج انتباهك الآن؟» — أعدادٌ لا نسب
  `suggestions`  اقتراحُ مهامّ — معاينةٌ لا تكتب في القاعدة شيئًا
  `retention`    الإتلاف الدائم: معاينةٌ ثمّ وقفٌ معلَن السبب
  `store`        القراءات — عددُ عباراتها ثابتٌ لا يتبع عدد الصفوف
"""
from . import retention, stages, store, suggestions, titles, vocab
from .attention import (
    NOTHING_URGENT_AR,
    NOTHING_URGENT_EN,
    AttentionItem,
    MissingItem,
    attention_items,
    missing_scientific_items,
)
from .stages import StageSuggestion, suggest_next_stage
from .suggestions import TaskSuggestion, propose_tasks
from .titles import PLACEHOLDER_AR, ProjectTitle, project_title

__all__ = [
    "NOTHING_URGENT_AR",
    "NOTHING_URGENT_EN",
    "PLACEHOLDER_AR",
    "AttentionItem",
    "MissingItem",
    "ProjectTitle",
    "StageSuggestion",
    "TaskSuggestion",
    "attention_items",
    "missing_scientific_items",
    "project_title",
    "propose_tasks",
    "retention",
    "stages",
    "store",
    "suggest_next_stage",
    "suggestions",
    "titles",
    "vocab",
]
