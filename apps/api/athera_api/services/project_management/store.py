"""قراءاتُ إدارة المشروع | Project-management reads (PUBRIVA).

**عددُ العبارات هو زمن الاستجابة.** الخدمة في سنغافورة والقاعدة في مومباي،
وكل عبارةٍ تعبر بينهما تكلّف نحو ٣٣٠ مللي ثانية. فقائمةُ ثلاثين مهمّة
مكتوبةٌ بعبارةٍ لكل مهمّة تعني عشر ثوانٍ في الشاشة — ولا يظهر في الشيفرة شيء
معطوب، ولا في القاعدة استعلامٌ بطيء.

فقاعدةُ هذا الملف واحدة:

  **كل دالّةٍ هنا عددُ عباراتها ثابتٌ لا يتبع عدد الصفوف.**

ويحرسها اختبارٌ يعدّ العبارات عند صفٍّ واحد وعند أربعين، ويقارن العددين.
ولا يكفي أن يكون الاستعلام سريعًا: `N+1` سريعٌ في كل عبارةٍ منه.

**وكل قراءة مقيَّدةٌ بالبحث لا بالمستأجر وحده.** RLS تحمي بين مستأجرين
ولا تحمي بين بحثين في مستأجرٍ واحد — وهذا عطبٌ وقع في هذا المنتج من قبل،
فكلُّ `where` هنا يحمل `project_id` صراحةً.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import Integer, String, and_, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.analysis import Dataset
from ...models.audit import AuditEvent
from ...models.literature import Claim
from ...models.portfolio import (
    ProjectDecision,
    ProjectFile,
    ProjectMember,
    ProjectSource,
    ResearchProject,
)
from ...models.project_management import (
    MILESTONES,
    ProjectMilestone,
    ProjectPlan,
    ProjectStageEvent,
    ProjectTask,
)
from ...models.publishing import Manuscript
from ...models.research import FactCandidate, ResearcherMemory
from ...models.synthesis import (
    ContradictionCandidate,
    GapCandidate,
    ResearchOpportunity,
    ThemeCandidate,
)


# ═══════════════════════════ الخطّة والمرحلة ═══════════════════════════

async def plan_for(session: AsyncSession, *, tenant_id: uuid.UUID,
                   project_id: uuid.UUID) -> ProjectPlan | None:
    return (await session.execute(
        select(ProjectPlan).where(ProjectPlan.tenant_id == tenant_id,
                                  ProjectPlan.project_id == project_id)
    )).scalar_one_or_none()


async def ensure_plan(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID) -> ProjectPlan:
    """صفُّ الخطّة يُنشأ عند أول حاجةٍ إليه — **بلا اعتمادِ مرحلة**.

    و`current_stage` يبدأ عند «الفكرة» و`stage_confirmed_by` فارغٌ عمدًا:
    القيمة موضعُ بدءٍ للعرض، لا دعوى بأن الباحث قال إنه في الفكرة. والفرق
    يظهر في الشاشة لأنه محفوظٌ هنا.
    """
    found = await plan_for(session, tenant_id=tenant_id, project_id=project_id)
    if found is not None:
        return found
    plan = ProjectPlan(tenant_id=tenant_id, project_id=project_id,
                       current_stage="idea")
    session.add(plan)
    await session.flush()
    return plan


async def stage_history(session: AsyncSession, *, tenant_id: uuid.UUID,
                        project_id: uuid.UUID) -> list[ProjectStageEvent]:
    """التاريخُ كاملًا بترتيبه — عبارةٌ واحدة مهما طال."""
    return list((await session.execute(
        select(ProjectStageEvent)
        .where(ProjectStageEvent.tenant_id == tenant_id,
               ProjectStageEvent.project_id == project_id)
        .order_by(ProjectStageEvent.occurred_at.asc())
    )).scalars().all())


# ═══════════════════════════ المَعالم ═══════════════════════════

async def milestone_rows(session: AsyncSession, *, tenant_id: uuid.UUID,
                         project_id: uuid.UUID) -> dict[str, ProjectMilestone]:
    rows = (await session.execute(
        select(ProjectMilestone)
        .where(ProjectMilestone.tenant_id == tenant_id,
               ProjectMilestone.project_id == project_id)
    )).scalars().all()
    return {row.milestone_key: row for row in rows}


def completed_keys(rows: dict[str, ProjectMilestone]) -> set[str]:
    return {key for key, row in rows.items() if row.completed_at is not None}


# ═══════════════════════════ المهامّ ═══════════════════════════

@dataclass(frozen=True, slots=True)
class TaskRow:
    """مهمّةٌ واسمُ المُسنَد إليها — **مقروءان في عبارةٍ واحدة**.

    وقراءةُ اسم العضو بعبارةٍ لكل مهمّة هي `N+1` بعينه: ثلاثون مهمّة تعني
    ثلاثين رحلةً إلى مومباي، وعشر ثوانٍ في شاشةٍ تبدو بسيطة.
    """

    task: ProjectTask
    assignee_name: str | None


async def list_tasks(session: AsyncSession, *, tenant_id: uuid.UUID,
                     project_id: uuid.UUID,
                     status: str | None = None,
                     stage: str | None = None) -> list[TaskRow]:
    """قائمةُ مهامّ البحث — **عبارةٌ واحدة، ومعها أسماءُ المُسنَد إليهم**."""
    stmt = (
        select(ProjectTask, ProjectMember.display_name)
        .outerjoin(ProjectMember,
                   and_(ProjectMember.id == ProjectTask.assignee_member_id,
                        # **والمشروع في شرط الوصل أيضًا.** فلو تسرّب معرّف
                        # عضوٍ من بحثٍ آخر لَما جلب اسمه — وقد منعته القاعدة
                        # أصلًا بمفتاحٍ مركّب، وهذا حارسٌ ثانٍ في القراءة.
                        ProjectMember.project_id == ProjectTask.project_id,
                        ProjectMember.tenant_id == tenant_id))
        .where(ProjectTask.tenant_id == tenant_id,
               ProjectTask.project_id == project_id)
    )
    if status is not None:
        stmt = stmt.where(ProjectTask.status == status)
    if stage is not None:
        stmt = stmt.where(ProjectTask.stage == stage)
    # الترتيب: ما تأخّر أولًا، ثمّ ما له موعد، ثمّ الأحدث إنشاءً.
    stmt = stmt.order_by(ProjectTask.due_at.asc().nulls_last(),
                         ProjectTask.created_at.desc())
    return [TaskRow(task=task, assignee_name=name)
            for task, name in (await session.execute(stmt)).all()]


async def task_by_id(session: AsyncSession, *, tenant_id: uuid.UUID,
                     project_id: uuid.UUID,
                     task_id: uuid.UUID) -> ProjectTask | None:
    """**والبحث في الشرط، لا المستأجر وحده.**"""
    return (await session.execute(
        select(ProjectTask).where(ProjectTask.tenant_id == tenant_id,
                                  ProjectTask.project_id == project_id,
                                  ProjectTask.id == task_id)
    )).scalar_one_or_none()


@dataclass(frozen=True, slots=True)
class TaskCounts:
    """أعدادٌ لا نسب — **وكلُّ عددٍ منها واقعةٌ يستطيع الباحث مراجعتها**.

    ولا حقل `percent_complete` هنا ولا في أيّ عقدٍ يخرج من هذه الوحدة:
    «٧٣٪» تدّعي قياسًا لا عقد علميّ خلفه، والباحث يصدّقها لأنها رقم.
    """

    open: int = 0
    overdue: int = 0
    awaiting_your_decision: int = 0
    awaiting_review: int = 0
    blocked: int = 0
    completed: int = 0
    total: int = 0


async def task_counts(session: AsyncSession, *, tenant_id: uuid.UUID,
                      project_id: uuid.UUID, now: dt.datetime) -> TaskCounts:
    """**عبارةٌ واحدة لكل الأعداد** — لا عبارةً لكل حال.

    و«المتأخر» يُحسَب هنا ولا يُخزَّن: عمودٌ محفوظ يصير كاذبًا عند منتصف
    الليل، ولا شيء يوقظه.
    """
    scoped = and_(ProjectTask.tenant_id == tenant_id,
                  ProjectTask.project_id == project_id)
    open_ = ProjectTask.status != "completed"
    row = (await session.execute(
        select(
            func.count().filter(open_),
            func.count().filter(and_(open_, ProjectTask.due_at.is_not(None),
                                     ProjectTask.due_at < now)),
            func.count().filter(ProjectTask.status == "needs_decision"),
            func.count().filter(ProjectTask.status == "awaiting_review"),
            func.count().filter(ProjectTask.status == "blocked"),
            func.count().filter(ProjectTask.status == "completed"),
            func.count(),
        ).select_from(ProjectTask).where(scoped)
    )).one()
    return TaskCounts(open=row[0], overdue=row[1], awaiting_your_decision=row[2],
                      awaiting_review=row[3], blocked=row[4], completed=row[5],
                      total=row[6])


# ═══════════════════════ العناصر العلمية المفقودة ═══════════════════════

@dataclass(frozen=True, slots=True)
class ScientificState:
    """ما يملكه البحث علميًّا — **أعدادٌ مقروءة، لا حكمُ جاهزية**.

    و«العناصر المفقودة» تُشتقّ من الأصفار هنا: غيابٌ يُعلَن، لا نقصٌ
    يُترجَم إلى «٦٠٪ جاهز».
    """

    included_sources: int = 0
    approved_gaps: int = 0
    approved_decisions: int = 0
    datasets: int = 0
    manuscripts: int = 0
    claims: int = 0
    team_members: int = 0


async def scientific_state(session: AsyncSession, *, tenant_id: uuid.UUID,
                           project_id: uuid.UUID) -> ScientificState:
    """**عبارةٌ واحدة لسبعة جداول** — باستعلاماتٍ عدديّة متداخلة.

    وسبعُ عباراتٍ منفصلة تعني نحو ثانيتين ونصف على الشبكة نفسها، في لوحةٍ
    يُفترض أن تُجيب فورًا.
    """
    def count_of(model, *conditions):
        return (select(func.count())
                .select_from(model)
                .where(model.tenant_id == tenant_id, *conditions)
                .scalar_subquery())

    row = (await session.execute(select(
        count_of(ProjectSource, ProjectSource.project_id == project_id,
                 ProjectSource.use_state == "included"),
        count_of(GapCandidate, GapCandidate.project_id == project_id,
                 GapCandidate.status == "approved"),
        count_of(ProjectDecision, ProjectDecision.project_id == project_id,
                 ProjectDecision.decided_at.is_not(None)),
        count_of(Dataset, Dataset.project_id == project_id),
        count_of(Manuscript, Manuscript.project_id == project_id),
        count_of(Claim, Claim.project_id == project_id),
        count_of(ProjectMember, ProjectMember.project_id == project_id),
    ))).one()
    return ScientificState(included_sources=row[0], approved_gaps=row[1],
                           approved_decisions=row[2], datasets=row[3],
                           manuscripts=row[4], claims=row[5], team_members=row[6])


# ═══════════════════════════ آخرُ ما جرى ═══════════════════════════

@dataclass(frozen=True, slots=True)
class ActivityRow:
    kind: str
    occurred_at: dt.datetime
    subject: str
    actor_user_id: uuid.UUID | None


async def recent_activity(session: AsyncSession, *, tenant_id: uuid.UUID,
                          project_id: uuid.UUID, limit: int = 8) -> list[ActivityRow]:
    """آخرُ ما جرى في البحث — **عبارةٌ واحدة تجمع ثلاثة مصادر**.

    ولا يُعرض هنا شيءٌ لم يفعله إنسان: اعتمادُ مرحلة، وإتمامُ مَعْلَم،
    وتغييرُ مهمّة. ولا «زار الباحث الصفحة» — وهو أثرٌ لا معنى علميّ له
    وجمعُه سلوكُ مراقبةٍ لا إدارةَ مشروع.
    """
    # **الثابت النصّي يُصبّ صراحةً.** و`literal("x")` يُصيَّر مُعامِلًا
    # مربوطًا (`$1`)، وPostgreSQL في `UNION` لا يستنتج نوعه فيسقط الاستعلام
    # بـ«could not determine data type of parameter». والصبّ يجعله معلومًا.
    def kind(name: str):
        return cast(literal(name), String).label("kind")

    stages = select(
        kind("stage_confirmed"),
        ProjectStageEvent.occurred_at.label("at"),
        cast(ProjectStageEvent.to_stage, String).label("subject"),
        ProjectStageEvent.confirmed_by.label("actor"),
    ).where(ProjectStageEvent.tenant_id == tenant_id,
            ProjectStageEvent.project_id == project_id)

    milestones = select(
        kind("milestone_completed"),
        ProjectMilestone.completed_at,
        cast(ProjectMilestone.milestone_key, String),
        ProjectMilestone.completed_by,
    ).where(ProjectMilestone.tenant_id == tenant_id,
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.completed_at.is_not(None))

    tasks = select(
        kind("task_updated"),
        ProjectTask.updated_at,
        cast(ProjectTask.title, String),
        ProjectTask.created_by,
    ).where(ProjectTask.tenant_id == tenant_id,
            ProjectTask.project_id == project_id)

    union = stages.union_all(milestones, tasks).subquery()
    rows = (await session.execute(
        select(union).order_by(union.c.at.desc()).limit(limit))).all()
    return [ActivityRow(kind=row[0], occurred_at=row[1], subject=row[2],
                        actor_user_id=row[3]) for row in rows]


# ═══════════════════════ ما يترتّب على الإتلاف ═══════════════════════

@dataclass(frozen=True, slots=True)
class DependencyCount:
    kind: str
    count: int
    label_ar: str
    label_en: str


async def dependency_counts(session: AsyncSession, *, tenant_id: uuid.UUID,
                            project_id: uuid.UUID) -> list[DependencyCount]:
    """**ماذا يُتلَف لو أُتلف هذا البحث؟** — بعددٍ واسم، لا بتحذيرٍ عامّ.

    وعشرةُ أنواعٍ تُعدّ في **عبارةٍ واحدة**، لأن هذه المعاينة تُطلب قبل
    أخطر زرٍّ في المنتج، ولا يجوز أن تتأخّر فتُتخطّى.

    و«تبعيات التدقيق» في القائمة عمدًا: سجلُّ التدقيق يُلحَق ولا يُحذف
    (0003)، فأثرُ هذا البحث فيه باقٍ حتى لو ذهب البحث — وهذه واقعةٌ تُقال
    للباحث قبل أن يقرّر، لا بعده.
    """
    def count_of(model, *conditions):
        return (select(func.count())
                .select_from(model)
                .where(model.tenant_id == tenant_id, *conditions)
                .scalar_subquery())

    verified_knowledge = (
        select(func.count(func.distinct(ResearcherMemory.id)))
        .select_from(ResearcherMemory)
        .join(FactCandidate,
              FactCandidate.resulting_memory_id == ResearcherMemory.id)
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(ResearcherMemory.tenant_id == tenant_id,
               ResearcherMemory.verification_status == "verified",
               ProjectFile.tenant_id == tenant_id,
               ProjectFile.project_id == project_id)
        .scalar_subquery()
    )

    synthesis = (
        count_of(ThemeCandidate, ThemeCandidate.project_id == project_id)
        + count_of(ContradictionCandidate,
                   ContradictionCandidate.project_id == project_id)
        + count_of(GapCandidate, GapCandidate.project_id == project_id)
        + count_of(ResearchOpportunity, ResearchOpportunity.project_id == project_id)
    )

    audit_rows = (
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id,
               or_(AuditEvent.object_id == project_id,
                   and_(AuditEvent.object_type == "research_project",
                        AuditEvent.object_id == project_id)))
        .scalar_subquery()
    )

    row = (await session.execute(select(
        count_of(ProjectSource, ProjectSource.project_id == project_id),
        count_of(Claim, Claim.project_id == project_id),
        verified_knowledge,
        count_of(ProjectFile, ProjectFile.project_id == project_id),
        count_of(ProjectMember, ProjectMember.project_id == project_id),
        count_of(ProjectTask, ProjectTask.project_id == project_id),
        count_of(ProjectDecision, ProjectDecision.project_id == project_id),
        count_of(Manuscript, Manuscript.project_id == project_id),
        cast(synthesis, Integer),
        audit_rows,
    ))).one()

    named = (
        ("sources", "مرجعًا في مجموعة هذا البحث", "sources in this project's corpus"),
        ("claims", "ادعاءً علميًّا", "scientific claims"),
        ("approved_knowledge", "معرفةً موثَّقة معتمَدة", "approved verified knowledge"),
        ("files", "ملفًّا مرتبطًا", "linked files"),
        ("team", "عضوًا في الفريق", "team members"),
        ("tasks", "مهمّة", "tasks"),
        ("decisions", "قرارًا مسجَّلًا", "recorded decisions"),
        ("manuscript", "مخطوطة", "manuscripts"),
        ("synthesis_objects", "عنصرًا في طبقة التركيب",
         "synthesis-layer objects"),
        ("audit_dependencies", "حدثًا في سجلّ التدقيق يشير إلى هذا البحث",
         "audit-log events referring to this project"),
    )
    return [DependencyCount(kind=kind, count=int(value), label_ar=ar, label_en=en)
            for (kind, ar, en), value in zip(named, row, strict=True)]


# ═══════════════════════════ البحث نفسه ═══════════════════════════

async def project_in_trash(session: AsyncSession, *, tenant_id: uuid.UUID,
                           project_id: uuid.UUID) -> ResearchProject | None:
    """بحثٌ في السلّة — وهو وحده ما يجوز أن يُسأل عن إتلافه."""
    return (await session.execute(
        select(ResearchProject).where(ResearchProject.id == project_id,
                                      ResearchProject.tenant_id == tenant_id,
                                      ResearchProject.deleted_at.is_not(None))
    )).scalar_one_or_none()


async def member_in_project(session: AsyncSession, *, tenant_id: uuid.UUID,
                            project_id: uuid.UUID,
                            member_id: uuid.UUID) -> ProjectMember | None:
    """**عضوُ هذا البحث** — لا عضوَ المستأجر.

    والقاعدة ترفض غيره بمفتاحٍ مركّب؛ وهذا الفحص يجعل الردّ رسالةً مفهومة
    بدل انتهاكِ قيدٍ يصل الباحث خطأً عامًّا.
    """
    return (await session.execute(
        select(ProjectMember).where(ProjectMember.tenant_id == tenant_id,
                                    ProjectMember.project_id == project_id,
                                    ProjectMember.id == member_id)
    )).scalar_one_or_none()


ALL_MILESTONE_KEYS = MILESTONES

__all__ = [
    "ALL_MILESTONE_KEYS",
    "ActivityRow",
    "DependencyCount",
    "ScientificState",
    "TaskCounts",
    "TaskRow",
    "completed_keys",
    "dependency_counts",
    "ensure_plan",
    "list_tasks",
    "member_in_project",
    "milestone_rows",
    "plan_for",
    "project_in_trash",
    "recent_activity",
    "scientific_state",
    "stage_history",
    "task_by_id",
    "task_counts",
]
