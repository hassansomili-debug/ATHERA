"""المرحلة: اقتراحٌ يُشتقّ، واعتمادٌ يُكتب | Stage suggestion vs confirmation.

**المنصّة تقترح ولا تدّعي.** والفرق بنيويّ لا لفظيّ:

  ما تدّعيه المنصّة   لا شيء — `current_stage` لا يتغيّر إلا بفعل إنسان
  ما تقترحه          يُحسَب في هذا الملف وقت القراءة، ولا يُخزَّن أصلًا

وامتناعُ التخزين مقصود: قيمةٌ محفوظة في عمودٍ تُقرأ بعد شهرٍ حالًا، لا
اقتراحًا. ومن قرأ `suggested_stage` من صفٍّ في القاعدة لن يعرف أنّ أحدًا لم
يوافق عليه. فالاقتراح يُشتقّ في كل مرّة، ويحمل سنده معه، أو لا يخرج.

## سندان لا ثالث لهما — وكلاهما يُسمّى

  `milestone_completed`  مَعْلَمٌ **اعتمده الباحث بيده** انتهى بهذه المرحلة
  `conventional_order`   الترتيب المعتاد — **عُرفٌ يُعلَن، لا دليل**

والثاني أضعف، ويُقال ضعفُه في نصّ السند نفسه لا في حاشية. ومرحلتان بلا
مَعْلَمٍ يحدّهما تُقترح تاليتهما بالعرف وحده، وتُخبَر بذلك.

## ولا اقتراحَ فوق ما لم يقع

مرحلةٌ لها مَعْلَمٌ لم يُعتمد **لا اقتراح لها**، ويُقال السبب: «لم يُعتمد
بعد مَعْلَم كذا». وهذا هو موضع الامتناع الذي يفرّق بين منصّةٍ تُعين ومنصّةٍ
تدفع الباحث إلى الأمام بلا سند.

## والمسار ليس خطًّا

باحثٌ في «التحليل» عاد إلى «التصميم والمنهجية» لأن التحليل كشف عيبًا —
هذا هو الصواب العلميّ. فلا دالّة هنا ترفض عودةً، ولا تعدّها تراجعًا: تُحسب
مرحلتُه الجديدة كما تُحسب أيّ مرحلة، ومَعْلَمُها المعتمَد سابقًا لا يزال
معتمدًا، والاقتراح يُشتقّ من حاله الآن.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ...models.project_management import STAGES
from .vocab import CONVENTIONAL_ORDER, STAGE_EXIT_MILESTONE, milestone_label, stage_label


@dataclass(frozen=True, slots=True)
class StageSuggestion:
    """اقتراحٌ يحمل سنده — **أو امتناعٌ يحمل سببه**.

    ولا حالة ثالثة: مرحلةٌ مقترَحة بلا سند لا تخرج من هذا الملف، لأن
    الحقلين يُملآن معًا أو يبقيان فارغين معًا.
    """

    stage: str | None
    basis_kind: str          # milestone_completed · conventional_order · none
    basis_ar: str
    basis_en: str

    @property
    def is_offered(self) -> bool:
        return self.stage is not None


def _next_in_order(stage: str) -> str | None:
    try:
        index = CONVENTIONAL_ORDER.index(stage)
    except ValueError:
        return None
    if index + 1 >= len(CONVENTIONAL_ORDER):
        return None
    return CONVENTIONAL_ORDER[index + 1]


def suggest_next_stage(current_stage: str,
                       completed_milestones: Iterable[str]) -> StageSuggestion:
    """ما التالي — **إن كان له سند**.

    والمُدخَل `completed_milestones` مَعالمُ اعتمدها بشرٌ بأسمائهم (القيد
    في `project_milestones` يمنع إتمامًا بلا صاحب). فالاقتراح مبنيٌّ على
    قرارٍ إنسانيّ سابق، لا على أثرِ زيارةِ صفحة ولا على ملفٍّ رُفع.
    """
    completed = set(completed_milestones)

    if current_stage not in STAGES:
        return StageSuggestion(
            None, "none",
            "مرحلةٌ غير معروفة — لا يُقترح فوق ما لا يُفهم.",
            "Unknown stage — nothing is suggested on top of what is not understood.")

    following = _next_in_order(current_stage)
    if following is None:
        return StageSuggestion(
            None, "none",
            f"«{stage_label(current_stage)}» آخرُ المسار — ولا مرحلة بعدها تُقترح.",
            f"“{stage_label(current_stage, 'en')}” is the end of the path; "
            "no further stage is suggested.")

    exit_milestone = STAGE_EXIT_MILESTONE.get(current_stage)

    if exit_milestone is None:
        # **عُرفٌ يُعلَن بوصفه عُرفًا.** ولو قيل «التالي: المراجعة العلمية»
        # بلا هذه الجملة لقُرئ حكمًا، وهو ليس حكمًا.
        return StageSuggestion(
            following, "conventional_order",
            f"الترتيب المعتاد للمراحل يضع «{stage_label(following)}» بعد "
            f"«{stage_label(current_stage)}». وهذا عُرفٌ لا دليل، والانتقال قرارك.",
            f"The conventional order places “{stage_label(following, 'en')}” after "
            f"“{stage_label(current_stage, 'en')}”. That is a convention, not "
            "evidence; the move is your decision.")

    if exit_milestone in completed:
        return StageSuggestion(
            following, "milestone_completed",
            f"اعتمدتَ مَعْلَم «{milestone_label(exit_milestone)}» الذي تنتهي به "
            f"«{stage_label(current_stage)}» — فالمقترَح التالي "
            f"«{stage_label(following)}». والاعتماد قرارك أنت.",
            f"You approved the milestone “{milestone_label(exit_milestone, 'en')}” "
            f"that ends “{stage_label(current_stage, 'en')}”, so the suggested next "
            f"stage is “{stage_label(following, 'en')}”. Confirming it is your call.")

    # **الامتناع.** ولا يُقترح شيءٌ فوق مَعْلَمٍ لم يقع.
    return StageSuggestion(
        None, "none",
        f"لم يُعتمد بعد مَعْلَم «{milestone_label(exit_milestone)}» الذي تنتهي به "
        f"«{stage_label(current_stage)}» — ولا يُقترح انتقالٌ فوق مَعْلَمٍ لم يقع.",
        f"The milestone “{milestone_label(exit_milestone, 'en')}” that ends "
        f"“{stage_label(current_stage, 'en')}” has not been approved, so no move "
        "is suggested on top of something that has not happened.")


__all__ = ["StageSuggestion", "suggest_next_stage"]
