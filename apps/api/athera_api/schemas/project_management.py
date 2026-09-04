"""عقودُ إدارة المشروع البحثي | Project-management contracts (PUBRIVA).

**العقد هو حيث تُكذَب الكذبة أو تُمنع.** فحقلٌ اسمُه `progress_percent`
يجعل كلَّ شاشةٍ تقرؤه تعرض نسبةً لا سند لها، ولن يسأل أحدٌ بعد ذلك من أين
جاءت. فلا حقلَ عشريًّا في هذا الملف كلِّه، ولا اسمَ حقلٍ فيه `percent` ولا
`score` ولا `readiness` — ويقابل ذلك اختبارٌ يمرّ على كل حقول هذه العقود.

**والمرحلةُ أربعة حقولٍ لا حقلٌ واحد**: ما هي الآن، وهل أكّدها إنسان، وما
المقترَح بعدها، وبأيّ سند. وطيُّها في `stage: "analysis"` يجعل القارئ يظنّ
أن المنصّة تعرف.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field, model_validator

from ..models.project_management import (
    MILESTONES,
    STAGES,
    TASK_PRIORITIES,
    TASK_STATUSES,
)

# الأنماط تُشتقّ من سجلّ النموذج ولا تُكتب بجانبه: قائمتان تفترقان بأول
# إضافة، فيقبل العقد قيمةً يرفضها القيد — أو يرفض قيمةً تعرضها الشاشة.
STAGE_PATTERN = "^(" + "|".join(STAGES) + ")$"
STATUS_PATTERN = "^(" + "|".join(TASK_STATUSES) + ")$"
PRIORITY_PATTERN = "^(" + "|".join(TASK_PRIORITIES) + ")$"
MILESTONE_PATTERN = "^(" + "|".join(MILESTONES) + ")$"


# ═══════════════════════════ عنوان المشروع ═══════════════════════════

class ProjectTitleView(BaseModel):
    """**العقد المشترك لعرض عنوان مشروع** — تستهلكه بقيّة الوحدات.

    و`created_at` حقلٌ مستقلّ عن العنوان عمدًا، وهو نصفُ العلاج: من ضمّ
    التاريخ إلى العنوان أنتج `قبول 2026-09-09T17:12…` الذي عُرض للباحث.
    ومن قرأ هذا العقد لا يستطيع ضمَّه بغير قصد.
    """

    display_ar: str
    display_en: str
    # هل هذا عنوانُ صاحبه، أم بديلٌ يقول إنه بديل؟
    is_placeholder: bool = False
    # سببُ البديل: blank · audit_timestamp · no_letters
    placeholder_reason: str | None = None
    created_at: dt.datetime | None = None
    can_rename: bool = True


# ═══════════════════════════ المرحلة ═══════════════════════════

class StageSuggestionView(BaseModel):
    """**اقتراحٌ يحمل سنده، أو امتناعٌ يحمل سببه.**

    و`is_offered` صريحةٌ ولا تُستنتج من `stage is None`: شاشةٌ تنسى الفحص
    تعرض «التالي المقترح: —» وهو أسوأ من ألّا تعرض شيئًا.
    """

    is_offered: bool
    stage: str | None = None
    stage_label: str | None = None
    # milestone_completed · conventional_order · none
    basis_kind: str
    basis: str


class ProjectStageView(BaseModel):
    """أربعُ حقائق لا تُطوى في واحدة."""

    current_stage: str
    current_stage_label: str
    # **مشروعٌ لم يؤكِّد صاحبُه مرحلته ليس في «الفكرة» يقينًا.**
    is_researcher_confirmed: bool
    confirmed_by: uuid.UUID | None = None
    confirmed_at: dt.datetime | None = None
    confirmation_note_ar: str | None = None
    suggestion: StageSuggestionView
    # جملةٌ تُعرض حرفيًّا فوق المرحلة، فلا تُقرأ حكمًا من المنصّة.
    disclaimer: str


class StageEventView(BaseModel):
    """صفٌّ في تاريخ المراحل — **وله صاحبٌ دائمًا**."""

    id: uuid.UUID
    from_stage: str | None = None
    from_stage_label: str | None = None
    to_stage: str
    to_stage_label: str
    occurred_at: dt.datetime
    confirmed_by: uuid.UUID
    note_ar: str | None = None
    # ما كانت المنصّة تقترحه لحظتها — وفراغه يعني «لم يكن هناك اقتراح».
    system_suggested_stage: str | None = None
    followed_the_suggestion: bool | None = None
    # هل كانت هذه عودةً إلى مرحلةٍ سابقة؟ **حقيقةٌ تُعرض ولا تُوصف تراجعًا**.
    is_return_to_earlier_stage: bool = False


class StageHistoryView(BaseModel):
    project_id: uuid.UUID
    events: list[StageEventView] = Field(default_factory=list)
    note: str


class StageConfirmRequest(BaseModel):
    """اعتمادُ مرحلة — **فعلُ إنسانٍ صريح، ولا افتراضي فيه**."""

    stage: str = Field(pattern=STAGE_PATTERN)
    note_ar: str | None = Field(default=None, max_length=2000)


# ═══════════════════════════ المهامّ ═══════════════════════════

class TaskView(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None = None
    stage: str
    stage_label: str
    status: str
    status_label: str
    priority: str
    priority_label: str
    assignee_member_id: uuid.UUID | None = None
    assignee_name: str | None = None
    created_by: uuid.UUID
    source: str
    source_label: str
    suggested_by_system: bool = False
    accepted_by: uuid.UUID | None = None
    accepted_at: dt.datetime | None = None
    due_at: dt.datetime | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    # **يُحسَب عند القراءة ولا يُخزَّن.** عمودٌ محفوظ يكذب عند منتصف الليل.
    is_overdue: bool = False
    requires_decision: bool = False
    decision_gate: str | None = None
    related_entity_type: str | None = None
    related_entity_id: uuid.UUID | None = None
    created_at: dt.datetime
    updated_at: dt.datetime


class TaskCountsView(BaseModel):
    """**أعدادٌ فقط.** ولا حقل هنا من نوع `float` — والنوع نفسه هو الحارس."""

    open: int = 0
    overdue: int = 0
    awaiting_your_decision: int = 0
    awaiting_review: int = 0
    blocked: int = 0
    completed: int = 0
    total: int = 0


class TasksView(BaseModel):
    project_id: uuid.UUID
    tasks: list[TaskView] = Field(default_factory=list)
    counts: TaskCountsView
    note: str


class TaskCreateRequest(BaseModel):
    """إنشاء مهمّة.

    و`accept_suggestion` هي البوابة: مهمّةٌ مصدرها اقتراحٌ آليّ **لا تُنشأ**
    إلا بها. والقاعدة نفسها ترفض غير ذلك (`accepted_by NOT NULL`)، فالعقد
    هنا يجعل الرفض رسالةً مفهومة بدل انتهاكِ قيدٍ يصل الباحث خطأً عامًّا.
    """

    title: str = Field(min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    stage: str = Field(pattern=STAGE_PATTERN)
    priority: str = Field(default="normal", pattern=PRIORITY_PATTERN)
    assignee_member_id: uuid.UUID | None = None
    due_at: dt.datetime | None = None
    requires_decision: bool = False
    decision_gate: str | None = Field(default=None, max_length=16)
    related_entity_type: str | None = Field(default=None, max_length=48)
    related_entity_id: uuid.UUID | None = None
    # researcher_created · team_created · research_brain_suggestion · system_workflow
    source: str = Field(
        default="researcher_created",
        pattern="^(researcher_created|team_created|research_brain_suggestion"
                "|system_workflow)$")
    accept_suggestion: bool = False

    @model_validator(mode="after")
    def _a_suggestion_needs_an_explicit_acceptance(self) -> TaskCreateRequest:
        """**اقتراحٌ لا يصير تكليفًا بلا إنسانٍ يقبله** — والرفض هنا ٤٢٢."""
        if self.source in ("research_brain_suggestion", "system_workflow") \
                and not self.accept_suggestion:
            raise ValueError(
                "a system suggestion becomes a task only when a researcher "
                "explicitly accepts it | الاقتراح لا يصير مهمّة إلا بقبولٍ صريح")
        if self.decision_gate is not None and not self.requires_decision:
            raise ValueError(
                "a decision gate means a decision is required | "
                "بوابةُ قرارٍ بلا «تحتاج قرارًا» تضيع من قائمة ما ينتظر اعتمادك")
        return self


class TaskUpdateRequest(BaseModel):
    """تعديلُ مهمّة — **وكلُّ حقلٍ اختياريّ، وما لم يُرسل لا يُمسّ**.

    وعقدٌ يستبدل الصفَّ كلَّه يمحو ما لم ترسله الشاشة: تعديلُ الموعد وحده
    يمسح المُسنَد إليه لأن النموذج في المتصفّح لم يكن يحمله.
    """

    title: str | None = Field(default=None, min_length=2, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    stage: str | None = Field(default=None, pattern=STAGE_PATTERN)
    status: str | None = Field(default=None, pattern=STATUS_PATTERN)
    priority: str | None = Field(default=None, pattern=PRIORITY_PATTERN)
    assignee_member_id: uuid.UUID | None = None
    clear_assignee: bool = False
    due_at: dt.datetime | None = None
    clear_due_at: bool = False
    requires_decision: bool | None = None
    decision_gate: str | None = Field(default=None, max_length=16)


class TaskSuggestionView(BaseModel):
    """اقتراحٌ معروضٌ للقراءة — **ولا صفّ له في القاعدة**."""

    key: str
    title_ar: str
    why_ar: str
    stage: str
    stage_label: str
    priority: str
    source: str = "research_brain_suggestion"


class TaskSuggestionsView(BaseModel):
    project_id: uuid.UUID
    suggestions: list[TaskSuggestionView] = Field(default_factory=list)
    # **تُقال بنصّها في الاستجابة**، فلا تعتمد الشاشة على أن أحدًا سيكتبها.
    note: str


# ═══════════════════════════ المَعالم ═══════════════════════════

class MilestoneView(BaseModel):
    key: str
    label: str
    target_date: dt.date | None = None
    completed_at: dt.datetime | None = None
    # **الإتمام له صاحب** — ولا يُستنتج من زيارةِ صفحة.
    completed_by: uuid.UUID | None = None
    evidence_note_ar: str | None = None
    is_completed: bool = False


class MilestonesView(BaseModel):
    project_id: uuid.UUID
    milestones: list[MilestoneView] = Field(default_factory=list)
    note: str


class MilestoneUpdateRequest(BaseModel):
    target_date: dt.date | None = None
    clear_target_date: bool = False
    # `True` يُتمّ المَعْلَم منسوبًا إلى صاحب الطلب، و`False` يسحب الإتمام.
    completed: bool | None = None
    evidence_note_ar: str | None = Field(default=None, max_length=2000)


# ═══════════════════════════ اللوحة ═══════════════════════════

class AttentionItemView(BaseModel):
    key: str
    label: str
    detail: str
    # عددٌ صحيح أو لا شيء. **ولا كسر** — والنوع هو الحارس.
    count: int | None = None
    destination: str


class MissingItemView(BaseModel):
    key: str
    label: str
    expected_since_stage: str
    expected_since_stage_label: str


class ActivityView(BaseModel):
    kind: str
    occurred_at: dt.datetime
    subject: str
    actor_user_id: uuid.UUID | None = None


class TimelineView(BaseModel):
    """الخطُّ الزمني — تواريخُ الخطّة ومَعالمُها وتاريخُ مراحلها."""

    start_date: dt.date | None = None
    target_completion_date: dt.date | None = None
    milestones: list[MilestoneView] = Field(default_factory=list)
    stage_events: list[StageEventView] = Field(default_factory=list)


class ProjectDashboardView(BaseModel):
    """لوحةُ المشروع — **تجيب عن سؤالٍ عمليّ، لا تعرض أرقام زينة**.

    ولا حقل هنا اسمه `progress` ولا `readiness` ولا `completion_percent`:
    لا عقد علميّ يحوّل بطاقاتٍ مغلقة إلى جاهزية ورقةٍ للنشر.
    """

    project_id: uuid.UUID
    title: ProjectTitleView
    stage: ProjectStageView
    start_date: dt.date | None = None
    target_completion_date: dt.date | None = None
    counts: TaskCountsView
    team_members: int = 0
    missing_scientific_items: list[MissingItemView] = Field(default_factory=list)
    recent_activity: list[ActivityView] = Field(default_factory=list)
    # «ما الذي يحتاج انتباهك الآن؟» — مرتَّبًا بما يوقف العمل أولًا.
    needs_your_attention: list[AttentionItemView] = Field(default_factory=list)
    # **الفراغ جوابٌ صريح**، لا شاشةٌ بيضاء تُقرأ عطبًا في التحميل.
    nothing_urgent_note: str


class PlanUpdateRequest(BaseModel):
    """تواريخُ الخطّة.

    و`target_completion_date` تُكتب في `research_projects.target_date`
    القائم، ولا يُنشأ لها عمودٌ ثانٍ: تاريخان لشيءٍ واحد يفترقان بأول
    تعديل، فتعرض شاشتان موعدين مختلفين ولا يُعرف أيّهما الخطّة.
    """

    start_date: dt.date | None = None
    clear_start_date: bool = False
    target_completion_date: dt.date | None = None
    clear_target_completion_date: bool = False


# ═══════════════════ سلّة المهملات والإتلاف الدائم ═══════════════════

class DependencyCountView(BaseModel):
    kind: str
    count: int
    label: str


class DeletionPreviewView(BaseModel):
    """**ما يترتّب على الإتلاف — قبل الزرّ لا بعده.**

    و`is_blocked` ليست عطبًا: هي حكمُ امتناعٍ مدروس. وسياسةُ الاحتفاظ في
    هذا النظام غير معرَّفةٍ تعريفًا قابلًا للتنفيذ، فلا يُتلَف ما لا تُعرف
    مشروعيّة إتلافه. والسبب والشرط مكتوبان في الاستجابة نفسها.
    """

    project_id: uuid.UUID
    title: ProjectTitleView
    is_in_trash: bool
    dependencies: list[DependencyCountView] = Field(default_factory=list)
    total_dependent_rows: int = 0
    is_blocked: bool = True
    blocked_reason: str
    message: str
    unblock_requirement: str
    policy_sources: list[str] = Field(default_factory=list)


class TrashedProjectView(BaseModel):
    """بحثٌ في السلّة — **وعنوانه يمرّ بالعقد المشترك، لا بالحقل الخام**."""

    project_id: uuid.UUID
    title: ProjectTitleView
    created_at: dt.datetime
    deleted_at: dt.datetime | None = None
    deleted_by: uuid.UUID | None = None


class TrashView(BaseModel):
    projects: list[TrashedProjectView] = Field(default_factory=list)
    note: str


# ═══════════════════════════ المفردات ═══════════════════════════

class VocabularyEntry(BaseModel):
    key: str
    label: str


class VocabularyView(BaseModel):
    stages: list[VocabularyEntry] = Field(default_factory=list)
    milestones: list[VocabularyEntry] = Field(default_factory=list)
    task_statuses: list[VocabularyEntry] = Field(default_factory=list)
    task_priorities: list[VocabularyEntry] = Field(default_factory=list)
    task_sources: list[VocabularyEntry] = Field(default_factory=list)


__all__ = [
    "MILESTONE_PATTERN",
    "PRIORITY_PATTERN",
    "STAGE_PATTERN",
    "STATUS_PATTERN",
    "ActivityView",
    "AttentionItemView",
    "DeletionPreviewView",
    "DependencyCountView",
    "MilestoneUpdateRequest",
    "MilestoneView",
    "MilestonesView",
    "MissingItemView",
    "PlanUpdateRequest",
    "ProjectDashboardView",
    "ProjectStageView",
    "ProjectTitleView",
    "StageConfirmRequest",
    "StageEventView",
    "StageHistoryView",
    "StageSuggestionView",
    "TaskCountsView",
    "TaskCreateRequest",
    "TaskSuggestionView",
    "TaskSuggestionsView",
    "TaskUpdateRequest",
    "TaskView",
    "TasksView",
    "TimelineView",
    "TrashView",
    "TrashedProjectView",
    "VocabularyEntry",
    "VocabularyView",
]
