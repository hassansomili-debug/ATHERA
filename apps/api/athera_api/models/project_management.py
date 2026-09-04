"""إدارة المشروع البحثي | Research project management (PUBRIVA).

**هذا ليس لوح مهامّ.** الفرق ليس في الشكل بل فيما تدّعيه القاعدة:

  لوحُ مهامّ     يقيس الإنجاز بعدد البطاقات المغلقة، ويسمّي ذلك «تقدّمًا»
  مشروعٌ علميّ   لا يعرف «التقدّم» أصلًا — يعرف مرحلةً أكّدها باحث، ومَعالمَ
                 اعتُمدت بأسماء أصحابها، ومهامًّا مفتوحة، وقرارًا ينتظر

**ولا عمود في هذا الملف يحمل نسبة.** «٧٣٪ مكتمل» رقمٌ لا عقد علميّ خلفه:
مهمّة أُغلقت ليست نتيجة صحيحة، ومرحلةٌ بلغها المشروع ليست جاهزيةً علمية.
وأولُ عمودٍ يُسمّى `readiness_score` يجعل الشاشة تكذب كذبةً مُقنعة.

## أربع حقائق لا تُطوى في واحدة

  المرحلة الحالية   `project_plans.current_stage` — وهي حالٌ لا تتغيّر إلا
                    بفعل إنسان
  تاريخ المراحل     `project_stage_events` — سجلٌّ يُلحَق ولا يُعدَّل، وكل
                    صفٍّ فيه له صاحبٌ **إلزامًا** (`confirmed_by NOT NULL`)
  المقترَح التالي   **لا عمود له** — يُشتقّ وقت القراءة من مَعالمَ اعتُمدت،
                    فيستحيل بنيويًّا أن يُقرأ حالًا مخزَّنة
  اعتمادُ الباحث    `stage_confirmed_by/at` — ومشروعٌ لم يؤكِّد صاحبُه
                    مرحلته يُعرض كذلك، لا كأنّه في «الفكرة» يقينًا

وطيُّ الثالثة في الأولى هو العطب الذي يجعل المنصّة تدّعي علمًا: تكتب
«التحليل» في `current_stage` لأن الباحث رفع ملف بيانات، فيقرأ بعد شهرٍ أنّه
في التحليل ولم يقل ذلك أحد.

## ودورة الحياة ليست خطًّا

باحثٌ يعود إلى المنهجية بعد التحليل يفعل الصواب — التحليل كشف عيبًا في
التصميم. فلا قيد في هذه الجداول يفرض ترتيبًا: `from_stage` قد يكون بعد
`to_stage` في القائمة، والسجلّ يقبله ويحفظه.

## واقتراحُ «دماغ البحث» ليس تكليفًا

`suggested_by_system` مع `accepted_by IS NULL` مرفوضٌ في القاعدة نفسها:
لا تصير الملاحظة مهمّةً في قائمة أحدٍ حتى يقبلها إنسان بيده.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# ═════════════════════════════ المفردات ═════════════════════════════
#
# **مكتوبةٌ مرّة، ومقابَلةٌ بالترحيل اختبارًا.** والخطأ المتكرر في هذا
# المستودع مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه — فتفترق الاثنتان
# بأول تعديل، وتُنتج ٥٠٠ في الإنتاج على قيمةٍ تبدو سليمة في الشيفرة.

STAGES: Final = (
    "idea",                         # الفكرة
    "literature_discovery",         # استكشاف الأدبيات
    "gap_problem",                  # الفجوة والمشكلة البحثية
    "design_methodology",           # التصميم والمنهجية
    "data_preparation_collection",  # تهيئة البيانات وجمعها
    "analysis",                     # التحليل
    "scientific_writing",           # الكتابة العلمية
    "scientific_review",            # المراجعة العلمية
    "journal_selection",            # اختيار المجلة
    "submission",                   # التقديم
    "peer_review_revision",         # التحكيم والتعديل
    "published",                    # منشور
)

# **ستٌّ لا عشرون.** كل حالٍ إضافية تعني معنًى ثانيًا لشيءٍ له اسم، ثم
# تقريرين لا يتفقان: «متوقفة» و«معلّقة» و«بانتظار» ثلاثةُ أسماءٍ لحالٍ
# واحدة، وأولُ من يعدّ «المهام المتأخرة» يختار اثنتين منها وينسى الثالثة.
TASK_STATUSES: Final = (
    "not_started",     # لم تبدأ
    "in_progress",     # قيد العمل
    "awaiting_review",  # بانتظار المراجعة
    "needs_decision",  # تحتاج قرارًا
    "blocked",         # متعثّرة
    "completed",       # مكتملة
)

# الحالات التي تُعدّ «مفتوحة» — وهي ما عدا المكتملة. تُشتقّ ولا تُكتب.
OPEN_TASK_STATUSES: Final = tuple(s for s in TASK_STATUSES if s != "completed")

TASK_SOURCES: Final = (
    "researcher_created",         # أنشأها الباحث
    "team_created",               # أنشأها عضو فريق
    "research_brain_suggestion",  # اقتراحُ دماغ البحث — بعد قبولٍ صريح
    "system_workflow",            # مسارٌ آلي — بعد قبولٍ صريح
)

# **المصدران اللذان لا يصيران تكليفًا بلا إنسان.** والعمود `suggested_by_system`
# مشتقٌّ من هذه المجموعة بقيدٍ في القاعدة، فلا يفترق الاثنان.
SYSTEM_TASK_SOURCES: Final = ("research_brain_suggestion", "system_workflow")

# **ثلاثٌ تكفي.** وسُلَّمٌ من خمسٍ يُنتج «متوسطة-عالية» ثم لا يفرّق أحدٌ
# بينها وبين «عالية» — والأولوية تُقرأ لتُرتَّب بها قائمة، لا لتُقاس.
TASK_PRIORITIES: Final = ("low", "normal", "high")

MILESTONES: Final = (
    "idea_approved",               # اعتماد الفكرة
    "literature_review_completed",  # اكتمال مراجعة الأدبيات
    "gap_approved",                # اعتماد الفجوة
    "methodology_approved",        # اعتماد المنهجية
    "data_ready",                  # جاهزية البيانات
    "analysis_completed",          # اكتمال التحليل
    "manuscript_ready",            # جاهزية المخطوطة
    "journal_selected",            # اختيار المجلة
    "submitted",                   # تمّ التقديم
    "review_response_completed",   # اكتمال الردّ على التحكيم
    "published",                   # النشر
)

# **سندُ الاقتراح نوعُه معلَن.** ومَعْلَمٌ اعتمده الباحث سندٌ غير «الترتيب
# المعتاد»؛ وخلطُهما يجعل عُرفًا يبدو دليلًا.
SUGGESTION_BASES: Final = ("milestone_completed", "conventional_order", "none")


class ProjectPlan(Base, TenantScoped, Timestamped):
    """حالُ المشروع الزمنية والمرحلية — **صفٌّ واحد لكل بحث**.

    ولا `progress_percent` هنا ولا في غيره: لا يوجد عقدٌ علميّ يحوّل «ثلاث
    مهامّ من خمس» إلى جاهزيةِ ورقةٍ للنشر، وكتابةُ الرقم تدّعي وجودَه.
    """

    __tablename__ = "project_plans"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_plans_project"),
        CheckConstraint(
            "current_stage IN (" + ", ".join(f"'{s}'" for s in STAGES) + ")",
            name="current_stage"),
        # **الاعتماد له صاحبٌ ووقت، أو ليس اعتمادًا.**
        CheckConstraint("(stage_confirmed_by IS NULL) = (stage_confirmed_at IS NULL)",
                        name="confirmation_has_an_author_and_a_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)

    # **تاريخ البدء هنا، وتاريخ الهدف في `research_projects.target_date`.**
    # ولا يُنسخ الثاني إلى هنا: عمودان لتاريخٍ واحد يفترقان بأول تعديل، ثم
    # تعرض شاشتان تاريخين مختلفين للشيء نفسه ولا يعرف الباحث أيّهما خطّته.
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    current_stage: Mapped[str] = mapped_column(String(48), nullable=False,
                                               default="idea", server_default="idea")
    stage_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    stage_confirmed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    stage_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def is_researcher_confirmed(self) -> bool:
        """**مشروعٌ لم يؤكِّد صاحبُه مرحلته ليس في «الفكرة» يقينًا.**

        هو مشروعٌ بلا مرحلةٍ مُعلَنة، والقيمة الافتراضية موضعُ بدءٍ للعرض
        لا دعوى. والفرق يظهر للباحث في الشاشة، لأنه محفوظٌ هنا.
        """
        return self.stage_confirmed_by is not None


class ProjectStageEvent(Base, TenantScoped):
    """تاريخُ المراحل — **يُلحَق ولا يُعدَّل، وكلُّ صفٍّ له صاحب**.

    و`confirmed_by` غير قابلٍ للفراغ عمدًا: لا صفَّ في هذا السجلّ يمكن أن
    تكتبه المنصّة عن نفسها. فإن أرادت يومًا أن «تسجّل مرحلةً استنتجتها» لم
    تجد لها موضعًا — وهذا هو الغرض.

    و**لا قيدَ ترتيب**: `from_stage` بعد `to_stage` حالٌ صحيحة تمامًا —
    باحثٌ عاد إلى المنهجية بعد التحليل لأن التحليل كشف عيبًا في التصميم.
    """

    __tablename__ = "project_stage_events"
    __table_args__ = (
        CheckConstraint(
            "to_stage IN (" + ", ".join(f"'{s}'" for s in STAGES) + ")",
            name="to_stage"),
        CheckConstraint(
            "from_stage IS NULL OR from_stage IN ("
            + ", ".join(f"'{s}'" for s in STAGES) + ")",
            name="from_stage"),
        CheckConstraint(
            "system_suggested_stage IS NULL OR system_suggested_stage IN ("
            + ", ".join(f"'{s}'" for s in STAGES) + ")",
            name="system_suggested_stage"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(48), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(48), nullable=False)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    confirmed_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    # **ما كانت المنصّة تقترحه لحظة الاعتماد** — يُحفظ ليُقرأ بعد شهر:
    # هل تبع الباحث الاقتراح أم خالفه؟ وهو ما يجعل جودة الاقتراح قابلةً
    # للمراجعة بدل أن تُصدَّق. وفراغه يعني «لم يكن هناك اقتراح».
    system_suggested_stage: Mapped[str | None] = mapped_column(String(48), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.UTC))


class ProjectTask(Base, TenantScoped, Timestamped):
    """مهمّةٌ في بحث — **وإتمامُها ليس صحّةً علمية**.

    فالمهمّة عملٌ يُنجَز، والصحّةُ حكمٌ على النتيجة. وشاشةٌ تقول «اكتمل
    التحليل» لأن بطاقةً أُغلقت تخلط الاثنين.
    """

    __tablename__ = "project_tasks"
    __table_args__ = (
        CheckConstraint("status IN (" + ", ".join(f"'{s}'" for s in TASK_STATUSES) + ")",
                        name="status"),
        CheckConstraint("source IN (" + ", ".join(f"'{s}'" for s in TASK_SOURCES) + ")",
                        name="source"),
        CheckConstraint(
            "priority IN (" + ", ".join(f"'{p}'" for p in TASK_PRIORITIES) + ")",
            name="priority"),
        CheckConstraint("stage IN (" + ", ".join(f"'{s}'" for s in STAGES) + ")",
                        name="stage"),
        CheckConstraint("length(btrim(title)) > 0", name="title_is_not_blank"),
        # **الإتمام له وقت.** و«مكتملة» بلا وقتٍ تُسقط كل حسابٍ للتأخّر.
        CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)",
                        name="completion_has_a_time"),
        # **`suggested_by_system` مشتقٌّ من المصدر لا مكتوبٌ بجانبه.**
        CheckConstraint(
            "suggested_by_system = (source IN ("
            + ", ".join(f"'{s}'" for s in SYSTEM_TASK_SOURCES) + "))",
            name="suggestion_flag_follows_its_source"),
        # **اقتراحٌ لا يصير تكليفًا بلا إنسان يقبله** — والقاعدة تفرضه، لا
        # الخدمة. فلو كُتب مسارٌ ثانٍ يُدخل مهامًّا مقترَحة رفضته القاعدة.
        CheckConstraint(
            "NOT suggested_by_system"
            " OR (accepted_by IS NOT NULL AND accepted_at IS NOT NULL)",
            name="a_suggestion_becomes_a_task_only_when_accepted"),
        CheckConstraint("(accepted_by IS NULL) = (accepted_at IS NULL)",
                        name="acceptance_has_an_author_and_a_time"),
        # بوابةُ قرارٍ بلا «تحتاج قرارًا» تضيع من القائمة التي تجمعها.
        CheckConstraint("decision_gate IS NULL OR requires_decision",
                        name="a_gate_means_a_decision_is_required"),
        CheckConstraint("status <> 'needs_decision' OR requires_decision",
                        name="needing_a_decision_means_requiring_one"),
        # الربطُ بكيانٍ آخر نوعٌ ومعرّف معًا، أو لا شيء.
        CheckConstraint(
            "(related_entity_type IS NULL) = (related_entity_id IS NULL)",
            name="a_relation_names_its_kind"),
        # **الحارس البنيويّ ضد التسرّب بين بحثين في المستأجر الواحد.** RLS
        # تحمي بين المستأجرين ولا تحمي بين بحثين — وهذا عطبٌ وقع هنا من قبل.
        # فالمُسنَد إليه يُقيَّد بمفتاحٍ مركّب يضمّ البحث: عضوٌ في بحثٍ آخر
        # ترفضه القاعدة، لا الخدمة.
        ForeignKeyConstraint(
            ["assignee_member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            name="fk_project_tasks_assignee"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False,
                                        default="not_started",
                                        server_default="not_started")
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal",
                                          server_default="normal")
    assignee_member_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False,
                                        default="researcher_created")
    suggested_by_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false")
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    accepted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True),
                                                       nullable=True)
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True),
                                                           nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True),
                                                             nullable=True)

    requires_decision: Mapped[bool] = mapped_column(Boolean, nullable=False,
                                                    default=False,
                                                    server_default="false")
    decision_gate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True),
                                                                nullable=True)

    def is_overdue(self, now: dt.datetime) -> bool:
        """**التأخّر يُحسَب ولا يُخزَّن.** عمودٌ محفوظ يتقادم بصمت كل ليلة."""
        if self.status == "completed" or self.due_at is None:
            return False
        return self.due_at < now


class ProjectMilestone(Base, TenantScoped, Timestamped):
    """مَعْلَمٌ في المشروع — **واعتمادُه فعلُ إنسانٍ لا أثرُ زيارةِ صفحة**.

    فلو اكتُشف الإتمام من مرورِ الباحث على شاشة، لصار «اكتملت مراجعة
    الأدبيات» مكتوبًا في سجلٍّ لأن أحدًا فتح صفحة المراجع. والقيد هنا
    يمنعه: لا `completed_at` بلا `completed_by`، ولا واحدٌ منهما وحده.
    """

    __tablename__ = "project_milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "milestone_key", name="uq_project_milestone"),
        CheckConstraint(
            "milestone_key IN (" + ", ".join(f"'{m}'" for m in MILESTONES) + ")",
            name="milestone_key"),
        CheckConstraint("(completed_at IS NULL) = (completed_by IS NULL)",
                        name="completion_has_an_author_and_a_time"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)
    milestone_key: Mapped[str] = mapped_column(String(48), nullable=False)
    target_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True),
                                                             nullable=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    evidence_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "MILESTONES",
    "OPEN_TASK_STATUSES",
    "STAGES",
    "SUGGESTION_BASES",
    "SYSTEM_TASK_SOURCES",
    "TASK_PRIORITIES",
    "TASK_SOURCES",
    "TASK_STATUSES",
    "ProjectMilestone",
    "ProjectPlan",
    "ProjectStageEvent",
    "ProjectTask",
]
