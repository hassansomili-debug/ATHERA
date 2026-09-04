"""اقتراحُ مهامّ — **معاينةٌ لا تكليف** | Task suggestions as preview only.

المسارُ كاملًا، ولا اختصار فيه:

    اقتراح ← معاينة ← يقبله الباحث ← تُنشأ المهمّة

**ولا سطر في هذا الملف يكتب في القاعدة.** وهذا ليس اصطلاحًا يُتّبع بل
خاصيّةٌ مفحوصة: اختبارٌ يعدّ عبارات الكتابة في هذا المسار ويشترط الصفر.
فلو أضاف أحدٌ يومًا `session.add` هنا سقط الفحص قبل أن يصل الإنتاج.

## لماذا هذا الحدّ بالذات

مهمّةٌ في قائمة الباحث تُقرأ التزامًا: شيءٌ عليه أن يفعله. ومنصّةٌ تُدخل
عشر مهامّ في قائمته من تلقاء نفسها تفعل شيئين معًا — تصنع عملًا لم يطلبه،
وتخلط ما اقترحته بما قرّره. ثم لا يعود يميّز بين ما ألزم به نفسه وما ألزمته
به آلة، فيثق بالقائمة كلّها أو يهملها كلّها.

## والاقتراح مبنيٌّ على واقعةٍ مقروءة، لا على تخمين

كلُّ اقتراحٍ هنا يقول **لماذا** بجملةٍ تشير إلى عددٍ في قاعدة البيانات:
«لا مرجع مُدرَجًا في المجموعة» — وهو صفرٌ يستطيع الباحث أن يفتحه ويراه.
ولا اقتراح بلا هذه الجملة.
"""
from __future__ import annotations

from dataclasses import dataclass

from .store import ScientificState, TaskCounts
from .vocab import CONVENTIONAL_ORDER, STAGE_EXIT_MILESTONE, milestone_label, stage_label


@dataclass(frozen=True, slots=True)
class TaskSuggestion:
    """اقتراحٌ معروضٌ للقراءة — **ولا وجود له في القاعدة حتى يُقبل**.

    ولا حقل `assignee` فيه عمدًا: الاقتراح لا يُسنَد إلى أحد. والإسناد فعلُ
    الباحث بعد القبول، وهو ما يجعل المهمّة التزامَ إنسانٍ على إنسان.
    """

    key: str
    title_ar: str
    why_ar: str
    stage: str
    priority: str = "normal"

    @property
    def source(self) -> str:
        return "research_brain_suggestion"


def _stage_index(stage: str) -> int:
    try:
        return CONVENTIONAL_ORDER.index(stage)
    except ValueError:
        return 0


def propose_tasks(*, current_stage: str, state: ScientificState,
                  counts: TaskCounts,
                  completed_milestones: set[str],
                  existing_titles: set[str]) -> list[TaskSuggestion]:
    """ما قد ينفع الآن — **وكلُّه معاينة**.

    و`existing_titles` تمنع تكرار ما قبِله الباحث فعلًا: اقتراحٌ يعود كل
    مرّة بعد قبوله يجعل القائمة ضجيجًا، ويعلّم الباحث تجاهلها.
    """
    here = _stage_index(current_stage)
    out: list[TaskSuggestion] = []

    def offer(key: str, title: str, why: str, stage: str, priority: str = "normal"):
        if title in existing_titles:
            return
        out.append(TaskSuggestion(key=key, title_ar=title, why_ar=why,
                                  stage=stage, priority=priority))

    if here >= _stage_index("literature_discovery") and state.included_sources == 0:
        offer("include_sources", "ضمّ مراجع إلى مجموعة هذا البحث",
              "لا مرجع واحدًا حالُه «مُدرَج» في هذا البحث — والعدد صفر في "
              "جدول مراجع المشروع.",
              "literature_discovery", "high")

    if here >= _stage_index("gap_problem") and state.approved_gaps == 0:
        offer("approve_gap", "راجع الفجوات المرشَّحة واعتمد ما تراه",
              "لا فجوةَ معتمَدة في هذا البحث. والمرشَّحات — إن وُجدت — تبقى "
              "مرشَّحاتٍ حتى تحكم فيها.",
              "gap_problem", "high")

    if here >= _stage_index("design_methodology") and state.approved_decisions == 0:
        offer("record_methodology_decision", "سجّل قرار المنهجية واعتمده",
              "لا قرارَ بحثيًّا معتمَدًا مسجَّلًا في هذا البحث — وقرارٌ لم "
              "يُسجَّل لا يُقرأ في قسم المنهجية بعد شهور.",
              "design_methodology")

    if here >= _stage_index("data_preparation_collection") and state.datasets == 0:
        offer("register_dataset", "سجّل مجموعة بيانات هذا البحث",
              "لا مجموعة بياناتٍ مسجَّلة في هذا البحث.",
              "data_preparation_collection")

    if here >= _stage_index("scientific_writing") and state.manuscripts == 0:
        offer("start_manuscript", "ابدأ مخطوطة هذا البحث",
              "لا مخطوطةَ مرتبطة بهذا البحث.",
              "scientific_writing")

    exit_milestone = STAGE_EXIT_MILESTONE.get(current_stage)
    if exit_milestone is not None and exit_milestone not in completed_milestones:
        offer(
            f"close_milestone_{exit_milestone}",
            f"احسم مَعْلَم «{milestone_label(exit_milestone)}»",
            f"«{stage_label(current_stage)}» تنتهي بهذا المَعْلَم، ولم يُعتمد "
            "بعد. واعتمادُه قرارك أنت — ولا تعتمده المنصّة عنك.",
            current_stage)

    if counts.overdue:
        offer("review_overdue", "راجع مواعيد المهامّ المتأخرة",
              f"{counts.overdue} مهمّة فات موعدها ولم تكتمل — وموعدٌ لم يعد "
              "واقعيًّا يُعدَّل، ولا يُترك ليصير ضجيجًا.",
              current_stage)

    return out


__all__ = ["TaskSuggestion", "propose_tasks"]
