"""ما الذي يحتاج انتباهك الآن؟ | What needs your attention now (PUBRIVA).

**السؤال الذي تجيب عنه لوحةُ المشروع سؤالٌ عمليّ، لا سؤالُ عرض.** والباحث
يفتح اللوحة وفي ذهنه ساعةٌ فارغة — يريد أن يعرف أين يضعها. فتُجيبه بعملٍ
بعينه، لا بأرقامٍ عنه.

## ولا رقم هنا يدّعي قياسًا

  ما يُعرض        عددٌ يُراجَع: «ثلاث مهامّ متأخرة» — يفتحها فيراها
  ما لا يُعرض     نسبةٌ تُصدَّق: «٧٣٪ مكتمل» — لا يستطيع أحدٌ مراجعتها

و«٨٢٪ جاهزية بحثية» أخطرها: تقرأ كأنّ المنصّة فحصت الورقة علميًّا. ولم
يقع شيء من ذلك — عُدَّت بطاقاتٌ مغلقة وقُسمت على بطاقات. فلا دالّة في هذا
الملف تُرجع كسرًا، ولا حقلَ في مخرجها من نوعٍ عشريّ.

## والترتيب معنًى لا زينة

ما فات موعده أولًا، ثمّ ما ينتظر قرار الباحث نفسه — فهذان يوقفان غيرهما.
ثمّ نقصٌ علميّ يخصّ المرحلة التي أعلنها. ثمّ الاقتراح، وهو آخرها لأنه
أضعفها سندًا. وشاشةٌ تضع «التالي المقترح» فوق «ثلاث مهامّ متأخرة» تدفع
الباحث إلى الأمام وخلفه عملٌ لم يتمّ.
"""
from __future__ import annotations

from dataclasses import dataclass

from .stages import StageSuggestion
from .store import ScientificState, TaskCounts
from .vocab import (
    CONVENTIONAL_ORDER,
    MISSING_ITEM_EXPECTED_AT,
    MISSING_ITEM_LABELS,
    label,
    stage_label,
)


@dataclass(frozen=True, slots=True)
class MissingItem:
    """عنصرٌ علميّ غائبٌ عن مرحلةٍ بلغها المشروع — **غيابٌ يُعلَن لا يُملأ**."""

    key: str
    label_ar: str
    label_en: str
    expected_since_stage: str


@dataclass(frozen=True, slots=True)
class AttentionItem:
    """بندٌ يحتاج انتباهًا — باسمه وعدده والوجهة التي يُعالَج فيها.

    و`count` عددٌ صحيح أو لا شيء. **ولا كسر**: النوع نفسه يمنع أن يتسلّل
    «٠٫٧٣» إلى هذا العقد.
    """

    key: str
    label_ar: str
    label_en: str
    detail_ar: str
    detail_en: str
    count: int | None
    destination: str  # tasks · stage · milestones · overview


def _stage_index(stage: str) -> int:
    try:
        return CONVENTIONAL_ORDER.index(stage)
    except ValueError:
        return 0


def missing_scientific_items(current_stage: str,
                             state: ScientificState) -> list[MissingItem]:
    """ما ينقص المشروع علميًّا **عند المرحلة التي أعلنها صاحبه**.

    ولا يُسأل مشروعٌ في «الفكرة» عن مخطوطته: لم يبلغ بعد الموضع الذي
    يصير فيه غيابها نقصًا. والمرجع هو مرحلةُ الباحث المعتمَدة، لا مرحلةٌ
    استنتجتها المنصّة.
    """
    have = {
        "included_sources": state.included_sources,
        "approved_gap": state.approved_gaps,
        "approved_decision": state.approved_decisions,
        "dataset": state.datasets,
        "manuscript": state.manuscripts,
    }
    here = _stage_index(current_stage)
    items: list[MissingItem] = []
    for key, expected_at in MISSING_ITEM_EXPECTED_AT.items():
        if _stage_index(expected_at) > here:
            continue
        if have.get(key, 0) > 0:
            continue
        items.append(MissingItem(
            key=key,
            label_ar=label(MISSING_ITEM_LABELS, key, "ar"),
            label_en=label(MISSING_ITEM_LABELS, key, "en"),
            expected_since_stage=expected_at))
    return items


def attention_items(*, current_stage: str, is_confirmed: bool,
                    counts: TaskCounts, missing: list[MissingItem],
                    suggestion: StageSuggestion) -> list[AttentionItem]:
    """قائمةُ «ما يحتاج انتباهك الآن» مرتَّبةً بما يوقف العمل أولًا.

    **والقائمة الفارغة جوابٌ صريح**: «لا شيء عاجل الآن» تُقال بنصّها،
    ولا تُترك الشاشة بيضاء ليقرأها الباحث عطبًا في التحميل.
    """
    items: list[AttentionItem] = []

    if counts.overdue:
        items.append(AttentionItem(
            key="overdue_tasks", label_ar="المهام المتأخرة",
            label_en="Overdue tasks",
            detail_ar=f"{counts.overdue} مهمّة فات موعدها ولم تكتمل.",
            detail_en=f"{counts.overdue} task(s) are past their due date.",
            count=counts.overdue, destination="tasks"))

    if counts.awaiting_your_decision:
        items.append(AttentionItem(
            key="awaiting_your_decision", label_ar="تنتظر اعتمادك",
            label_en="Awaiting your decision",
            detail_ar=(f"{counts.awaiting_your_decision} مهمّة موقوفةٌ على قرارٍ "
                       "منك — ولا تتقدّم حتى تقرّر."),
            detail_en=(f"{counts.awaiting_your_decision} task(s) are held on a "
                       "decision only you can make."),
            count=counts.awaiting_your_decision, destination="tasks"))

    if counts.blocked:
        items.append(AttentionItem(
            key="blocked_tasks", label_ar="مهامّ متعثّرة", label_en="Blocked tasks",
            detail_ar=f"{counts.blocked} مهمّة أُعلن تعثّرها.",
            detail_en=f"{counts.blocked} task(s) are marked blocked.",
            count=counts.blocked, destination="tasks"))

    if not is_confirmed:
        items.append(AttentionItem(
            key="stage_unconfirmed", label_ar="لم تؤكِّد مرحلة البحث بعد",
            label_en="You have not confirmed the stage yet",
            detail_ar=(f"يُعرض البحث عند «{stage_label(current_stage)}» موضعَ "
                       "بدءٍ للعرض — ولم تقل المنصّة إنها مرحلته، ولم تقلها أنت."),
            detail_en=(f"The project is shown at “{stage_label(current_stage, 'en')}” "
                       "as a starting point only; neither you nor the platform has "
                       "claimed it."),
            count=None, destination="stage"))

    if missing:
        names = " · ".join(item.label_ar for item in missing)
        items.append(AttentionItem(
            key="missing_scientific_items", label_ar="العناصر العلمية المفقودة",
            label_en="Missing scientific items",
            detail_ar=(f"لا يسجّل البحث بعد: {names}. وهذا غيابُ تسجيلٍ في "
                       "المنصّة، لا حكمٌ على عملك خارجها."),
            detail_en=(f"Not yet recorded: "
                       f"{' · '.join(item.label_en for item in missing)}. This is "
                       "an absence of records here, not a judgement of your work."),
            count=len(missing), destination="overview"))

    if suggestion.is_offered:
        items.append(AttentionItem(
            key="suggested_next", label_ar="التالي المقترح",
            label_en="Suggested next",
            detail_ar=f"{stage_label(suggestion.stage or '')} — {suggestion.basis_ar}",
            detail_en=(f"{stage_label(suggestion.stage or '', 'en')} — "
                       f"{suggestion.basis_en}"),
            count=None, destination="stage"))

    return items


NOTHING_URGENT_AR = "لا شيء متأخّرٌ ولا موقوفٌ على قرارك الآن."
NOTHING_URGENT_EN = "Nothing is overdue or waiting on your decision right now."


__all__ = [
    "NOTHING_URGENT_AR",
    "NOTHING_URGENT_EN",
    "AttentionItem",
    "MissingItem",
    "attention_items",
    "missing_scientific_items",
]
