"""مفرداتُ إدارة المشروع بلغتيها | Project-management vocabulary (PUBRIVA).

**كل مفردةٍ تصل الباحث تُعرَّف هنا مرّة**، ويقابلها اختبارٌ بقائمة النموذج
عنصرًا بعنصر. والخطأ المتكرر في هذا المستودع مفردةٌ تُكتب في الشاشة بجانب
سجلّها في القاعدة — فتنقص واحدة، وتُعرض للباحث كلمةٌ إنجليزية خام في واجهةٍ
عربية، أو أسوأ: يسقط الطلب بـ٥٠٠ على قيمةٍ تبدو سليمة.

**ولا مفردةَ هنا تحمل حكمًا علميًّا.** «التحليل» اسمُ مرحلةٍ في خطّة عمل،
لا شهادةٌ بأن تحليلًا صحيحًا وقع.
"""
from __future__ import annotations

from typing import Final

from ...models.project_management import (
    MILESTONES,
    STAGES,
    TASK_PRIORITIES,
    TASK_SOURCES,
    TASK_STATUSES,
)

# ═══════════════════════════ المراحل ═══════════════════════════

STAGE_LABELS: Final[dict[str, dict[str, str]]] = {
    "idea": {"ar": "الفكرة", "en": "Idea"},
    "literature_discovery": {"ar": "استكشاف الأدبيات",
                             "en": "Literature discovery"},
    "gap_problem": {"ar": "الفجوة والمشكلة البحثية",
                    "en": "Gap and research problem"},
    "design_methodology": {"ar": "التصميم والمنهجية",
                           "en": "Design and methodology"},
    "data_preparation_collection": {"ar": "تهيئة البيانات وجمعها",
                                    "en": "Data preparation and collection"},
    "analysis": {"ar": "التحليل", "en": "Analysis"},
    "scientific_writing": {"ar": "الكتابة العلمية", "en": "Scientific writing"},
    "scientific_review": {"ar": "المراجعة العلمية", "en": "Scientific review"},
    "journal_selection": {"ar": "اختيار المجلة", "en": "Journal selection"},
    "submission": {"ar": "التقديم", "en": "Submission"},
    "peer_review_revision": {"ar": "التحكيم والتعديل",
                             "en": "Peer review and revision"},
    "published": {"ar": "منشور", "en": "Published"},
}

# **الترتيب المعتاد عُرفٌ يُعلَن، لا قانون.** وهو مصدرُ الاقتراح الأضعف —
# ويُسمّى باسمه في كل مرّة تُعرض فيها الاقتراح، فلا يُقرأ دليلًا.
CONVENTIONAL_ORDER: Final[tuple[str, ...]] = STAGES

# ═══════════════════════════ المَعالم ═══════════════════════════

MILESTONE_LABELS: Final[dict[str, dict[str, str]]] = {
    "idea_approved": {"ar": "اعتماد الفكرة", "en": "Idea approved"},
    "literature_review_completed": {"ar": "اكتمال مراجعة الأدبيات",
                                    "en": "Literature review completed"},
    "gap_approved": {"ar": "اعتماد الفجوة", "en": "Gap approved"},
    "methodology_approved": {"ar": "اعتماد المنهجية",
                             "en": "Methodology approved"},
    "data_ready": {"ar": "جاهزية البيانات", "en": "Data ready"},
    "analysis_completed": {"ar": "اكتمال التحليل", "en": "Analysis completed"},
    "manuscript_ready": {"ar": "جاهزية المخطوطة", "en": "Manuscript ready"},
    "journal_selected": {"ar": "اختيار المجلة", "en": "Journal selected"},
    "submitted": {"ar": "تمّ التقديم", "en": "Submitted"},
    "review_response_completed": {"ar": "اكتمال الردّ على التحكيم",
                                  "en": "Review response completed"},
    "published": {"ar": "النشر", "en": "Published"},
}

# **المَعْلَم الذي يُنهي كل مرحلة** — ومنه وحده يُشتقّ اقتراحٌ له سند.
#
# ومرحلتان بلا مَعْلَمٍ يحدّهما عمدًا: «الكتابة العلمية» تنتهي بحكم الباحث
# على مسودّته لا بمَعْلَمٍ في القائمة، و«منشور» آخرُ المسار. وملءُ الفراغ
# بمَعْلَمٍ مخترَع كان سيعطي اقتراحًا يبدو مسنودًا وهو ليس كذلك.
STAGE_EXIT_MILESTONE: Final[dict[str, str | None]] = {
    "idea": "idea_approved",
    "literature_discovery": "literature_review_completed",
    "gap_problem": "gap_approved",
    "design_methodology": "methodology_approved",
    "data_preparation_collection": "data_ready",
    "analysis": "analysis_completed",
    "scientific_writing": None,
    "scientific_review": "manuscript_ready",
    "journal_selection": "journal_selected",
    "submission": "submitted",
    "peer_review_revision": "review_response_completed",
    "published": None,
}

# ═══════════════════════════ المهامّ ═══════════════════════════

TASK_STATUS_LABELS: Final[dict[str, dict[str, str]]] = {
    "not_started": {"ar": "لم تبدأ", "en": "Not started"},
    "in_progress": {"ar": "قيد العمل", "en": "In progress"},
    "awaiting_review": {"ar": "بانتظار المراجعة", "en": "Awaiting review"},
    "needs_decision": {"ar": "تنتظر قرارك", "en": "Needs your decision"},
    "blocked": {"ar": "متعثّرة", "en": "Blocked"},
    "completed": {"ar": "مكتملة", "en": "Completed"},
}

TASK_PRIORITY_LABELS: Final[dict[str, dict[str, str]]] = {
    "low": {"ar": "منخفضة", "en": "Low"},
    "normal": {"ar": "معتادة", "en": "Normal"},
    "high": {"ar": "عالية", "en": "High"},
}

TASK_SOURCE_LABELS: Final[dict[str, dict[str, str]]] = {
    "researcher_created": {"ar": "أنشأها الباحث", "en": "Created by the researcher"},
    "team_created": {"ar": "أنشأها الفريق", "en": "Created by the team"},
    # **الاسم يقول إنّ إنسانًا قبِلها.** و«اقتراح دماغ البحث» وحدها تُقرأ
    # كأنّ المنصّة كلّفت أحدًا — ولم يقع ذلك ولا يمكن أن يقع.
    "research_brain_suggestion": {"ar": "اقتراحٌ من دماغ البحث قبِلتَه",
                                  "en": "A Research Brain suggestion you accepted"},
    "system_workflow": {"ar": "مسارٌ آليّ قبِلتَه",
                        "en": "A system workflow you accepted"},
}

# ═════════════════ ما تعرضه لوحة المشروع — بلا نسبة ═════════════════
#
# **هذه هي القائمة كاملةً، ولا سابعَ فيها اسمُه «نسبة الإنجاز».** وكلُّ
# سطرٍ منها عددٌ أو حال — والعدد واقعةٌ تُراجَع، والنسبة دعوى تُصدَّق.
ATTENTION_KEYS: Final[tuple[str, ...]] = (
    "current_stage",       # المرحلة الحالية
    "suggested_next",      # التالي المقترح
    "open_tasks",          # المهام المفتوحة
    "overdue_tasks",       # المهام المتأخرة
    "awaiting_your_decision",  # تنتظر اعتمادك
    "missing_scientific_items",  # العناصر العلمية المفقودة
)

ATTENTION_LABELS: Final[dict[str, dict[str, str]]] = {
    "current_stage": {"ar": "المرحلة الحالية", "en": "Current stage"},
    "suggested_next": {"ar": "التالي المقترح", "en": "Suggested next"},
    "open_tasks": {"ar": "المهام المفتوحة", "en": "Open tasks"},
    "overdue_tasks": {"ar": "المهام المتأخرة", "en": "Overdue tasks"},
    "awaiting_your_decision": {"ar": "تنتظر اعتمادك", "en": "Awaiting your decision"},
    "missing_scientific_items": {"ar": "العناصر العلمية المفقودة",
                                 "en": "Missing scientific items"},
}

# العناصرُ العلمية التي يُسأل عنها المشروع — **غيابُها يُعلَن ولا يُملأ**.
#
# **وكلُّ عنصرٍ هنا يُعدّ من جدولٍ قائم.** ولا يُدرَج في القائمة ما لا
# تستطيع القاعدة عدَّه: «سؤالٌ بحثيّ مسجَّل» يبدو حقًّا في محلّه، ولا جدول
# يحمله اليوم — وإدراجُه يعني إمّا سطرًا يقول «مفقود» أبدًا، أو استنتاجَه
# من نصٍّ آخر. وكلاهما كذب.
MISSING_ITEM_LABELS: Final[dict[str, dict[str, str]]] = {
    "included_sources": {"ar": "مراجع مُدرَجة في المجموعة",
                         "en": "Sources included in the corpus"},
    "approved_gap": {"ar": "فجوةٌ معتمَدة", "en": "An approved gap"},
    "approved_decision": {"ar": "قرارٌ بحثيٌّ معتمَد",
                          "en": "An approved research decision"},
    "dataset": {"ar": "مجموعة بيانات", "en": "A dataset"},
    "manuscript": {"ar": "مخطوطة", "en": "A manuscript"},
}

# **المرحلةُ التي يصير عندها العنصرُ متوقَّعًا.** ومشروعٌ في «الفكرة» بلا
# مخطوطة ليس ناقصًا — هو في أوّله. وقولُ «مخطوطة مفقودة» لكل بحثٍ جديد
# ضجيجٌ يُدرَّب الباحث على تجاهله، فيتجاهل معه ما يهمّ.
MISSING_ITEM_EXPECTED_AT: Final[dict[str, str]] = {
    "included_sources": "literature_discovery",
    "approved_gap": "gap_problem",
    "approved_decision": "design_methodology",
    "dataset": "data_preparation_collection",
    "manuscript": "scientific_writing",
}


def label(table: dict[str, dict[str, str]], key: str, locale: str = "ar") -> str:
    """التسمية بلغتها — **والمفتاح الخام لا يصل الباحث أبدًا**.

    وسقوطُه إلى العربية عند غياب الإنجليزية مقصود: العربية لغةُ المنتج
    الأولى، وواجهةٌ عربيةٌ فيها مفتاحٌ إنجليزيّ خام عطبٌ ظاهر.
    """
    entry = table.get(key)
    if entry is None:
        return key
    return entry.get(locale) or entry["ar"]


def stage_label(key: str, locale: str = "ar") -> str:
    return label(STAGE_LABELS, key, locale)


def milestone_label(key: str, locale: str = "ar") -> str:
    return label(MILESTONE_LABELS, key, locale)


def vocabulary(locale: str = "ar") -> dict[str, list[dict[str, str]]]:
    """المفرداتُ كلّها للشاشة — فلا تُعيد الواجهة كتابة قائمةٍ ثانية."""
    return {
        "stages": [{"key": k, "label": stage_label(k, locale)} for k in STAGES],
        "milestones": [{"key": k, "label": milestone_label(k, locale)}
                       for k in MILESTONES],
        "task_statuses": [{"key": k, "label": label(TASK_STATUS_LABELS, k, locale)}
                          for k in TASK_STATUSES],
        "task_priorities": [{"key": k, "label": label(TASK_PRIORITY_LABELS, k, locale)}
                            for k in TASK_PRIORITIES],
        "task_sources": [{"key": k, "label": label(TASK_SOURCE_LABELS, k, locale)}
                         for k in TASK_SOURCES],
    }


__all__ = [
    "ATTENTION_KEYS",
    "ATTENTION_LABELS",
    "CONVENTIONAL_ORDER",
    "MILESTONE_LABELS",
    "MISSING_ITEM_EXPECTED_AT",
    "MISSING_ITEM_LABELS",
    "STAGE_EXIT_MILESTONE",
    "STAGE_LABELS",
    "TASK_PRIORITY_LABELS",
    "TASK_SOURCE_LABELS",
    "TASK_STATUS_LABELS",
    "label",
    "milestone_label",
    "stage_label",
    "vocabulary",
]
