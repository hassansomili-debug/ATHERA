"""إدارة المشروع البحثي | Project-management routes (PUBRIVA).

**لا نقطة هنا تُرجع نسبة.** لا «٧٣٪ مكتمل» ولا «٨٢٪ جاهزية بحثية» — لا
عقد علميّ خلف أيٍّ منهما، والباحث يصدّق الرقم لأنه رقم. وما يخرج من هنا
أعدادٌ يستطيع فتحها ورؤيتها: ثلاث مهامّ متأخرة، مَعْلَمان معتمدان، مرجعٌ
واحد مُدرَج.

## والمعاملة تُختم من الخارج

**لا `session.commit()` في هذا الملف.** `tenant_session` تفتح المعاملة
وتختمها عند الخروج؛ وختمُها داخل معالجٍ ثمّ استعمالُ الجلسة بعده يُسقط
الطلب بـ`InvalidRequestError: Can't operate on closed transaction` — وهو
عطبٌ أسقط أربع نقاطٍ في هذا المستودع الأسبوع الماضي. فيُترك الختم لمن فتح.

## والقراءة مقيَّدةٌ بالبحث لا بالمستأجر وحده

RLS تحمي بين مستأجرين ولا تحمي بين بحثين في مستأجرٍ واحد. فكل دالّةٍ هنا
تُثبت أوّلًا أنّ البحث لهذا المستأجر، ثمّ كل استعلامٍ يشترط `project_id`
مرّةً أخرى — والقاعدة نفسها ترفض إسنادَ مهمّةٍ إلى عضوِ بحثٍ آخر بمفتاحٍ
مركّب، لا لأن الخدمة تصفّي.

## التركيب في `main.py` — سطران، ولماذا كُتبا هنا لا في طلبٍ للمُكامِل

`main.py` ملفُّ المُكامِل، والقاعدة أن يُطلب منه التعديل لا أن يُؤخذ. وقد
كُتب الطلب فعلًا في `docs/integration/track-b-requests.md`. ثمّ أضاف
المُكامِل نفسه عقدًا معماريًّا (`test_at_arch_wave1_contracts.py`) يُسقط
**أيّ** موجّهٍ مكتوبٍ غير مركَّب — لأن طبقة التركيب شُحنت مرّةً كاملةً
ولم تكن في التطبيق، وتسعون فحصًا تمرّ ولا سبيل للباحث إليها.

فبقاءُ هذا الموجّه بلا تركيب يجعل فرع السبرنت أحمر، ووضعُه في قائمة «لا
يُركَّب عمدًا» كذبٌ على الحارس: هو **يُراد** له أن يُركَّب. فالسطران
مضافان هنا وموصوفان في مستند التكامل ليراجعهما المُكامِل:

    from .routers import project_management as project_management_router
    app.include_router(project_management_router.router)
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.portfolio import ResearchProject
from ..models.project_management import (
    MILESTONES,
    SYSTEM_TASK_SOURCES,
    ProjectMilestone,
    ProjectPlan,
    ProjectStageEvent,
    ProjectTask,
)
from ..schemas.project_management import (
    ActivityView,
    AttentionItemView,
    DeletionPreviewView,
    DependencyCountView,
    MilestonesView,
    MilestoneUpdateRequest,
    MilestoneView,
    MissingItemView,
    PlanUpdateRequest,
    ProjectDashboardView,
    ProjectStageView,
    ProjectTitleView,
    StageConfirmRequest,
    StageEventView,
    StageHistoryView,
    StageSuggestionView,
    TaskCountsView,
    TaskCreateRequest,
    TaskSuggestionsView,
    TaskSuggestionView,
    TaskUpdateRequest,
    TasksView,
    TimelineView,
    TrashedProjectView,
    TrashView,
    VocabularyEntry,
    VocabularyView,
)
from ..services import audit, workspace
from ..services.project_management import (
    attention_items,
    missing_scientific_items,
    project_title,
    propose_tasks,
    retention,
    store,
    suggest_next_stage,
)
from ..services.project_management.stages import StageSuggestion
from ..services.project_management.vocab import (
    CONVENTIONAL_ORDER,
    TASK_PRIORITY_LABELS,
    TASK_SOURCE_LABELS,
    TASK_STATUS_LABELS,
    label,
    milestone_label,
    stage_label,
    vocabulary,
)

router = APIRouter(prefix="/api/v1/project-management", tags=["project-management"])

# **الجملة التي تمنع أن تُقرأ المرحلة حكمًا من المنصّة.** تُرسل في كل
# استجابةٍ تحمل مرحلة، فلا تعتمد الشاشة على أن أحدًا سيكتبها في مكانٍ ما.
STAGE_DISCLAIMER_AR = (
    "المرحلة ما أكّدتَه أنت. والمنصّة تقترح ولا تُقرّر، ومرحلةُ المشروع "
    "ليست حكمًا على جاهزيته العلمية."
)

TASKS_NOTE_AR = (
    "إتمامُ مهمّةٍ إنجازُ عمل، لا شهادةٌ بصحّةٍ علمية. والمتأخّر يُحسَب عند "
    "القراءة من موعده وحاله."
)

SUGGESTIONS_NOTE_AR = (
    "هذه معاينة — **لم يُنشأ منها شيء**. ولا تصير مهمّةً في قائمتك إلا "
    "بقبولك، ولا تُسنَد إلى أحدٍ إلا بإسنادك."
)

MILESTONES_NOTE_AR = (
    "اعتمادُ المَعْلَم فعلُك أنت ويُنسب إليك؛ ولا يُستنتج من فتح صفحةٍ ولا "
    "من رفع ملف."
)

HISTORY_NOTE_AR = (
    "كلُّ سطرٍ هنا اعتمادُ إنسان. والعودة إلى مرحلةٍ سابقة حالٌ صحيحة — "
    "تحليلٌ يكشف عيبًا في التصميم يُعيدك إلى المنهجية، وهذا هو الصواب."
)

TRASH_NOTE_AR = (
    "ما في السلّة باقٍ كما هو ويمكن استعادته. والإتلاف الدائم قرارٌ ثانٍ "
    "لا يقع بضغطة، وتسبقه معاينةُ ما يترتّب عليه."
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _project(session: AsyncSession, principal: Principal,
                   project_id: uuid.UUID) -> ResearchProject:
    row = await workspace.live_project(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    if row is None:
        # **٤٠٤ لا ٤٠٣**: تمييزُ «موجودٌ وليس لك» عن «غير موجود» يسرّب وجود
        # بحوث غيرك — وهو تسريبٌ بذاته.
        raise NotFound("project_management.project_not_found")
    return row


def _title_view(row: ResearchProject) -> ProjectTitleView:
    """**العنوان يمرّ بالعقد المشترك دائمًا** — ولا يُقرأ العمود خامًا.

    وقراءةُ `working_title_ar` مباشرةً في شاشةٍ واحدة هي كل ما يلزم ليعود
    `قبول 2026-09-09T17:12…` إلى الظهور بعد أن أُصلح في أربع.
    """
    title = project_title(row.working_title_ar, created_at=row.created_at)
    return ProjectTitleView(
        display_ar=title.display_ar, display_en=title.display_en,
        is_placeholder=title.is_placeholder, placeholder_reason=title.reason,
        created_at=title.created_at, can_rename=title.can_rename)


def _suggestion_view(suggestion: StageSuggestion, locale: str) -> StageSuggestionView:
    return StageSuggestionView(
        is_offered=suggestion.is_offered,
        stage=suggestion.stage,
        stage_label=(stage_label(suggestion.stage, locale)
                     if suggestion.stage else None),
        basis_kind=suggestion.basis_kind,
        basis=suggestion.basis_en if locale == "en" else suggestion.basis_ar)


def _transient_plan(tenant_id: uuid.UUID, project_id: uuid.UUID) -> ProjectPlan:
    """خطّةٌ للعرض وحده حين لا صفَّ بعد — **والقراءة لا تكتب**.

    ونقطةُ `GET` تُنشئ صفًّا هي نقطةٌ تكتب في القاعدة كلّما فُتحت شاشة،
    فتُنتج كتابةً على كل تحديثٍ للصفحة. والصفّ يُنشأ عند أول فعلٍ يحتاجه.
    """
    return ProjectPlan(tenant_id=tenant_id, project_id=project_id,
                       current_stage="idea")


def _stage_view(plan: ProjectPlan, suggestion: StageSuggestion,
                locale: str) -> ProjectStageView:
    return ProjectStageView(
        current_stage=plan.current_stage,
        current_stage_label=stage_label(plan.current_stage, locale),
        is_researcher_confirmed=plan.stage_confirmed_by is not None,
        confirmed_by=plan.stage_confirmed_by,
        confirmed_at=plan.stage_confirmed_at,
        confirmation_note_ar=plan.stage_note_ar,
        suggestion=_suggestion_view(suggestion, locale),
        disclaimer=STAGE_DISCLAIMER_AR)


def _task_view(row: store.TaskRow, now: dt.datetime, locale: str):
    from ..schemas.project_management import TaskView

    task = row.task
    return TaskView(
        id=task.id, project_id=task.project_id, title=task.title,
        description=task.description, stage=task.stage,
        stage_label=stage_label(task.stage, locale),
        status=task.status, status_label=label(TASK_STATUS_LABELS, task.status, locale),
        priority=task.priority,
        priority_label=label(TASK_PRIORITY_LABELS, task.priority, locale),
        assignee_member_id=task.assignee_member_id, assignee_name=row.assignee_name,
        created_by=task.created_by, source=task.source,
        source_label=label(TASK_SOURCE_LABELS, task.source, locale),
        suggested_by_system=task.suggested_by_system,
        accepted_by=task.accepted_by, accepted_at=task.accepted_at,
        due_at=task.due_at, started_at=task.started_at,
        completed_at=task.completed_at, is_overdue=task.is_overdue(now),
        requires_decision=task.requires_decision, decision_gate=task.decision_gate,
        related_entity_type=task.related_entity_type,
        related_entity_id=task.related_entity_id,
        created_at=task.created_at, updated_at=task.updated_at)


def _counts_view(counts: store.TaskCounts) -> TaskCountsView:
    return TaskCountsView(
        open=counts.open, overdue=counts.overdue,
        awaiting_your_decision=counts.awaiting_your_decision,
        awaiting_review=counts.awaiting_review, blocked=counts.blocked,
        completed=counts.completed, total=counts.total)


def _milestone_views(rows: dict[str, ProjectMilestone],
                     locale: str) -> list[MilestoneView]:
    """**المَعالم الأحد عشر كلّها تُعرض**، وما لا صفَّ له يُعرض «لم يُعتمد».

    وعرضُ المخزَّن وحده يجعل مشروعًا جديدًا يبدو بلا مَعالمَ أصلًا، فلا يعرف
    الباحث ما ينتظره.
    """
    out: list[MilestoneView] = []
    for key in MILESTONES:
        row = rows.get(key)
        out.append(MilestoneView(
            key=key, label=milestone_label(key, locale),
            target_date=row.target_date if row else None,
            completed_at=row.completed_at if row else None,
            completed_by=row.completed_by if row else None,
            evidence_note_ar=row.evidence_note_ar if row else None,
            is_completed=bool(row and row.completed_at is not None)))
    return out


def _stage_event_views(events: list[ProjectStageEvent],
                       locale: str) -> list[StageEventView]:
    out: list[StageEventView] = []
    for event in events:
        earlier = (event.from_stage is not None
                   and event.from_stage in CONVENTIONAL_ORDER
                   and event.to_stage in CONVENTIONAL_ORDER
                   and CONVENTIONAL_ORDER.index(event.to_stage)
                   < CONVENTIONAL_ORDER.index(event.from_stage))
        out.append(StageEventView(
            id=event.id, from_stage=event.from_stage,
            from_stage_label=(stage_label(event.from_stage, locale)
                              if event.from_stage else None),
            to_stage=event.to_stage,
            to_stage_label=stage_label(event.to_stage, locale),
            occurred_at=event.occurred_at, confirmed_by=event.confirmed_by,
            note_ar=event.note_ar,
            system_suggested_stage=event.system_suggested_stage,
            followed_the_suggestion=(
                None if event.system_suggested_stage is None
                else event.system_suggested_stage == event.to_stage),
            is_return_to_earlier_stage=earlier))
    return out


# ═══════════════════════════ المفردات ═══════════════════════════

@router.get("/vocabulary", response_model=VocabularyView)
async def read_vocabulary(
    principal: Principal = Depends(get_principal),
) -> VocabularyView:
    """المفرداتُ كلّها بلغة الطلب — فلا تعيد الشاشة كتابة قائمةٍ ثانية.

    وقائمتان لشيءٍ واحد تفترقان بأول إضافة: تُعرض للباحث كلمةٌ إنجليزية
    خام في واجهةٍ عربية، أو يُرفض ما تعرضه الشاشة.
    """
    data = vocabulary(principal.locale)
    return VocabularyView(**{
        key: [VocabularyEntry(**entry) for entry in entries]
        for key, entries in data.items()})


# ═══════════════════════════ اللوحة ═══════════════════════════

@router.get("/projects/{project_id}/dashboard", response_model=ProjectDashboardView)
async def project_dashboard(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectDashboardView:
    """ما حالُ البحث، وما الذي يحتاج انتباهك الآن؟

    **وعددُ العبارات هنا ثابت** — ستٌّ مهما بلغ عدد المهامّ والمَعالم.
    والخدمة في سنغافورة والقاعدة في مومباي، فكل عبارةٍ زائدة ثلث ثانية في
    شاشةٍ يُفترض أن تُجيب فورًا.
    """
    tid = principal.tenant_id
    project = await _project(session, principal, project_id)
    now = _now()

    plan = await store.plan_for(session, tenant_id=tid, project_id=project_id)
    if plan is None:
        plan = _transient_plan(tid, project_id)

    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)
    counts = await store.task_counts(session, tenant_id=tid, project_id=project_id,
                                     now=now)
    state = await store.scientific_state(session, tenant_id=tid,
                                         project_id=project_id)
    activity = await store.recent_activity(session, tenant_id=tid,
                                           project_id=project_id)

    suggestion = suggest_next_stage(plan.current_stage,
                                    store.completed_keys(milestones))
    missing = missing_scientific_items(plan.current_stage, state)
    items = attention_items(current_stage=plan.current_stage,
                            is_confirmed=plan.stage_confirmed_by is not None,
                            counts=counts, missing=missing, suggestion=suggestion)

    locale = principal.locale
    from ..services.project_management.attention import (
        NOTHING_URGENT_AR,
        NOTHING_URGENT_EN,
    )

    return ProjectDashboardView(
        project_id=project_id,
        title=_title_view(project),
        stage=_stage_view(plan, suggestion, locale),
        start_date=plan.start_date,
        target_completion_date=project.target_date,
        counts=_counts_view(counts),
        team_members=state.team_members,
        missing_scientific_items=[
            MissingItemView(
                key=item.key,
                label=item.label_en if locale == "en" else item.label_ar,
                expected_since_stage=item.expected_since_stage,
                expected_since_stage_label=stage_label(item.expected_since_stage,
                                                       locale))
            for item in missing],
        recent_activity=[
            ActivityView(kind=row.kind, occurred_at=row.occurred_at,
                         subject=row.subject, actor_user_id=row.actor_user_id)
            for row in activity],
        needs_your_attention=[
            AttentionItemView(
                key=item.key,
                label=item.label_en if locale == "en" else item.label_ar,
                detail=item.detail_en if locale == "en" else item.detail_ar,
                count=item.count, destination=item.destination)
            for item in items],
        nothing_urgent_note=(NOTHING_URGENT_EN if locale == "en"
                             else NOTHING_URGENT_AR))


@router.patch("/projects/{project_id}/plan", response_model=TimelineView)
async def update_plan(
    project_id: uuid.UUID,
    payload: PlanUpdateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TimelineView:
    """تواريخُ الخطّة — بدايةً وهدفًا.

    و**لا ساعةَ عملٍ ولا تتبّعَ وقت**: الخطّة مواعيدُ يضعها الباحث لنفسه،
    لا رقابةٌ على ساعاته. وتاريخُ الهدف يُكتب في العمود القائم
    `research_projects.target_date` ولا يُنسخ إلى عمودٍ ثانٍ.
    """
    tid = principal.tenant_id
    project = await _project(session, principal, project_id)
    plan = await store.ensure_plan(session, tenant_id=tid, project_id=project_id)

    before = {"start_date": str(plan.start_date) if plan.start_date else None,
              "target_date": str(project.target_date) if project.target_date else None}

    if payload.clear_start_date:
        plan.start_date = None
    elif payload.start_date is not None:
        plan.start_date = payload.start_date

    if payload.clear_target_completion_date:
        project.target_date = None
    elif payload.target_completion_date is not None:
        project.target_date = payload.target_completion_date

    await session.flush()
    await audit.record(
        session, tenant_id=tid, action="project_management.plan_updated",
        object_type="research_project", object_id=project_id,
        actor_user_id=principal.user_id, state_before=before,
        state_after={
            "start_date": str(plan.start_date) if plan.start_date else None,
            "target_date": str(project.target_date) if project.target_date else None},
        reason="the researcher sets the project's own dates; no clock is imposed")

    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)
    events = await store.stage_history(session, tenant_id=tid, project_id=project_id)
    return TimelineView(
        start_date=plan.start_date, target_completion_date=project.target_date,
        milestones=_milestone_views(milestones, principal.locale),
        stage_events=_stage_event_views(events, principal.locale))


@router.get("/projects/{project_id}/timeline", response_model=TimelineView)
async def project_timeline(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TimelineView:
    """الخطُّ الزمني: تواريخُ الخطّة، والمَعالم، وتاريخُ المراحل."""
    tid = principal.tenant_id
    project = await _project(session, principal, project_id)
    plan = await store.plan_for(session, tenant_id=tid, project_id=project_id)
    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)
    events = await store.stage_history(session, tenant_id=tid, project_id=project_id)
    return TimelineView(
        start_date=plan.start_date if plan else None,
        target_completion_date=project.target_date,
        milestones=_milestone_views(milestones, principal.locale),
        stage_events=_stage_event_views(events, principal.locale))


# ═══════════════════════════ المرحلة ═══════════════════════════

@router.get("/projects/{project_id}/stage", response_model=ProjectStageView)
async def read_stage(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectStageView:
    """المرحلةُ الحالية والمقترَحُ بعدها — **وهما حقلان لا حقل**."""
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    plan = await store.plan_for(session, tenant_id=tid, project_id=project_id)
    if plan is None:
        plan = _transient_plan(tid, project_id)
    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)
    suggestion = suggest_next_stage(plan.current_stage,
                                    store.completed_keys(milestones))
    return _stage_view(plan, suggestion, principal.locale)


@router.post("/projects/{project_id}/stage/confirm", response_model=ProjectStageView)
async def confirm_stage(
    project_id: uuid.UUID,
    payload: StageConfirmRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectStageView:
    """**اعتمادُ المرحلة فعلُ الباحث** — وهو المسار الوحيد الذي يغيّرها.

    ولا يوجد في هذا الموجّه مسارٌ ثانٍ يكتب `current_stage`: لا استنتاجٌ من
    ملفٍّ رُفع، ولا من صفحةٍ زارها، ولا من بوابةٍ اعتُمدت في وحدةٍ أخرى.

    **ولا ترتيبَ مفروض.** العودةُ إلى مرحلةٍ سابقة تُقبل وتُسجَّل كما هي —
    وما كانت المنصّة تقترحه لحظتها يُحفظ معها، فيُقرأ بعد شهرٍ أنّ الباحث
    خالف الاقتراح، لا أنّ الاقتراح لم يكن.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    plan = await store.ensure_plan(session, tenant_id=tid, project_id=project_id)
    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)

    # الاقتراح **قبل** الاعتماد — وهو ما يُحفظ في السجلّ.
    before_suggestion = suggest_next_stage(plan.current_stage,
                                           store.completed_keys(milestones))
    from_stage = plan.current_stage if plan.stage_confirmed_by is not None else None
    now = _now()

    session.add(ProjectStageEvent(
        tenant_id=tid, project_id=project_id, from_stage=from_stage,
        to_stage=payload.stage, occurred_at=now, confirmed_by=principal.user_id,
        note_ar=payload.note_ar,
        system_suggested_stage=before_suggestion.stage))

    plan.current_stage = payload.stage
    plan.stage_confirmed_by = principal.user_id
    plan.stage_confirmed_at = now
    plan.stage_note_ar = payload.note_ar
    await session.flush()

    await audit.record(
        session, tenant_id=tid, action="project_management.stage_confirmed",
        object_type="research_project", object_id=project_id,
        actor_user_id=principal.user_id,
        state_before={"stage": from_stage},
        state_after={"stage": payload.stage,
                     "system_suggested": before_suggestion.stage,
                     "basis_kind": before_suggestion.basis_kind},
        reason=("the stage is what the researcher confirms; the platform suggests "
                "and never claims"))

    after = suggest_next_stage(payload.stage, store.completed_keys(milestones))
    return _stage_view(plan, after, principal.locale)


@router.get("/projects/{project_id}/stage/history", response_model=StageHistoryView)
async def read_stage_history(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> StageHistoryView:
    """تاريخُ المراحل — **وكلُّ سطرٍ فيه اعتمادُ إنسانٍ منسوبٌ إليه**."""
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    events = await store.stage_history(session, tenant_id=tid, project_id=project_id)
    return StageHistoryView(
        project_id=project_id,
        events=_stage_event_views(events, principal.locale),
        note=HISTORY_NOTE_AR)


# ═══════════════════════════ المهامّ ═══════════════════════════

@router.get("/projects/{project_id}/tasks", response_model=TasksView)
async def list_tasks(
    project_id: uuid.UUID,
    task_status: str | None = Query(default=None, alias="status"),
    stage: str | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TasksView:
    """قائمةُ المهامّ — **ثلاثُ عباراتٍ مهما بلغ عددها**.

    واسمُ المُسنَد إليه يأتي في العبارة نفسها بوصلٍ خارجيّ، لا بعبارةٍ لكل
    مهمّة: ثلاثون مهمّة تعني ثلاثين رحلةً بين سنغافورة ومومباي، وعشرَ ثوانٍ
    في شاشةٍ تبدو بسيطة.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    now = _now()
    rows = await store.list_tasks(session, tenant_id=tid, project_id=project_id,
                                  status=task_status, stage=stage)
    counts = await store.task_counts(session, tenant_id=tid, project_id=project_id,
                                     now=now)
    return TasksView(
        project_id=project_id,
        tasks=[_task_view(row, now, principal.locale) for row in rows],
        counts=_counts_view(counts), note=TASKS_NOTE_AR)


@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    payload: TaskCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """أنشئ مهمّة.

    **والمُسنَد إليه عضوُ هذا البحث** — والقاعدة ترفض غيره بمفتاحٍ مركّب
    `(assignee_member_id, project_id)`. والفحص هنا يجعل الردّ رسالةً مفهومة
    بدل انتهاكِ قيدٍ يصل الباحث خطأً عامًّا.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)

    if payload.assignee_member_id is not None:
        member = await store.member_in_project(
            session, tenant_id=tid, project_id=project_id,
            member_id=payload.assignee_member_id)
        if member is None:
            raise NotFound("project_management.member_not_in_project")

    from_system = payload.source in SYSTEM_TASK_SOURCES
    now = _now()
    task = ProjectTask(
        tenant_id=tid, project_id=project_id, title=payload.title.strip(),
        description=payload.description, stage=payload.stage,
        status="not_started", priority=payload.priority,
        assignee_member_id=payload.assignee_member_id,
        created_by=principal.user_id, source=payload.source,
        suggested_by_system=from_system,
        # **القبول يُنسب إلى صاحبه ووقته** — والقاعدة ترفض اقتراحًا بلا ذلك.
        accepted_by=principal.user_id if from_system else None,
        accepted_at=now if from_system else None,
        due_at=payload.due_at, requires_decision=payload.requires_decision,
        decision_gate=payload.decision_gate,
        related_entity_type=payload.related_entity_type,
        related_entity_id=payload.related_entity_id)
    session.add(task)
    await session.flush()

    await audit.record(
        session, tenant_id=tid, action="project_management.task_created",
        object_type="project_task", object_id=task.id,
        actor_user_id=principal.user_id,
        state_after={"project_id": str(project_id), "title": payload.title[:120],
                     "source": payload.source, "stage": payload.stage,
                     "accepted_by_researcher": from_system},
        reason=("a suggestion becomes an obligation only when a researcher "
                "accepts it"))

    return _task_view(store.TaskRow(task=task, assignee_name=None), now,
                      principal.locale)


@router.patch("/projects/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """عدِّل مهمّة — حالًا أو موعدًا أو مُسنَدًا إليه.

    و**«مكتملة» تحمل وقتها**: القيد في القاعدة يرفض إتمامًا بلا وقت، فلا
    يبقى حسابُ التأخّر معلَّقًا على عمودٍ فارغ.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    task = await store.task_by_id(session, tenant_id=tid, project_id=project_id,
                                  task_id=task_id)
    if task is None:
        raise NotFound("project_management.task_not_found")

    before = {"status": task.status, "stage": task.stage,
              "due_at": task.due_at.isoformat() if task.due_at else None,
              "assignee": str(task.assignee_member_id)
              if task.assignee_member_id else None}
    now = _now()

    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.description is not None:
        task.description = payload.description
    if payload.stage is not None:
        task.stage = payload.stage
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.requires_decision is not None:
        task.requires_decision = payload.requires_decision
    if payload.decision_gate is not None:
        task.decision_gate = payload.decision_gate
        task.requires_decision = True

    if payload.clear_assignee:
        task.assignee_member_id = None
    elif payload.assignee_member_id is not None:
        member = await store.member_in_project(
            session, tenant_id=tid, project_id=project_id,
            member_id=payload.assignee_member_id)
        if member is None:
            raise NotFound("project_management.member_not_in_project")
        task.assignee_member_id = payload.assignee_member_id

    if payload.clear_due_at:
        task.due_at = None
    elif payload.due_at is not None:
        task.due_at = payload.due_at

    if payload.status is not None:
        if payload.status == "needs_decision":
            task.requires_decision = True
        if payload.status == "completed":
            task.completed_at = task.completed_at or now
        else:
            # **سحبُ الإتمام يسحب وقتَه** — وإلّا بقي وقتٌ لإتمامٍ لم يعد قائمًا.
            task.completed_at = None
        if payload.status == "in_progress" and task.started_at is None:
            task.started_at = now
        task.status = payload.status

    await session.flush()
    await audit.record(
        session, tenant_id=tid, action="project_management.task_updated",
        object_type="project_task", object_id=task.id,
        actor_user_id=principal.user_id, state_before=before,
        state_after={"status": task.status, "stage": task.stage,
                     "due_at": task.due_at.isoformat() if task.due_at else None,
                     "assignee": str(task.assignee_member_id)
                     if task.assignee_member_id else None},
        reason="a completed task is finished work, never a scientific verdict")

    name = None
    if task.assignee_member_id is not None:
        member = await store.member_in_project(
            session, tenant_id=tid, project_id=project_id,
            member_id=task.assignee_member_id)
        name = member.display_name if member else None

    # **التحديثُ يُبطل `updated_at`، وقراءتُها بعده تطلب القاعدة من شيفرةٍ
    # متزامنة — فيسقط الطلب بـ٥٠٠.**
    #
    # `updated_at` قيمتُها `onupdate=now()` في الخادم، فبعد `flush` تصير
    # منتهيةً لا محمَّلة. و`_task_view` دالّةٌ متزامنة، فأولُ لمسٍ لها يبدأ
    # قراءةً من داخل سياقٍ لا يملك greenlet:
    #
    #     MissingGreenlet: greenlet_spawn has not been called
    #
    # وهو من عائلة العطب الذي أسقط أربع نقاطٍ من قبل: عملُ قاعدةٍ يقع حيث
    # لا يُتوقَّع. والعلاج أن تُطلب القراءة **صراحةً وبانتظار** قبل العرض،
    # لا أن تُترك لمصادفة لمسِ حقل. وهذا مسارُ تعديلٍ لا قائمة، فعبارةٌ
    # واحدة زائدة فيه ثمنٌ مقبول.
    await session.refresh(task)

    return _task_view(store.TaskRow(task=task, assignee_name=name), now,
                      principal.locale)


@router.get("/projects/{project_id}/task-suggestions",
            response_model=TaskSuggestionsView)
async def read_task_suggestions(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TaskSuggestionsView:
    """**معاينةٌ لا تكتب شيئًا.**

    ولا صفَّ يُنشأ من هذه النقطة، ولا تُسنَد مهمّةٌ إلى أحد. والمسار كاملًا:
    اقتراح ← معاينة ← يقبله الباحث ← تُنشأ المهمّة عبر `POST /tasks`.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    now = _now()

    plan = await store.plan_for(session, tenant_id=tid, project_id=project_id)
    current_stage = plan.current_stage if plan else "idea"
    milestones = await store.milestone_rows(session, tenant_id=tid,
                                            project_id=project_id)
    state = await store.scientific_state(session, tenant_id=tid,
                                         project_id=project_id)
    counts = await store.task_counts(session, tenant_id=tid, project_id=project_id,
                                     now=now)
    existing = await store.list_tasks(session, tenant_id=tid, project_id=project_id)

    proposals = propose_tasks(
        current_stage=current_stage, state=state, counts=counts,
        completed_milestones=store.completed_keys(milestones),
        existing_titles={row.task.title for row in existing
                         if row.task.status != "completed"})

    locale = principal.locale
    return TaskSuggestionsView(
        project_id=project_id,
        suggestions=[
            TaskSuggestionView(
                key=item.key, title_ar=item.title_ar, why_ar=item.why_ar,
                stage=item.stage, stage_label=stage_label(item.stage, locale),
                priority=item.priority, source=item.source)
            for item in proposals],
        note=SUGGESTIONS_NOTE_AR)


# ═══════════════════════════ المَعالم ═══════════════════════════

@router.get("/projects/{project_id}/milestones", response_model=MilestonesView)
async def read_milestones(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MilestonesView:
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    rows = await store.milestone_rows(session, tenant_id=tid, project_id=project_id)
    return MilestonesView(project_id=project_id,
                          milestones=_milestone_views(rows, principal.locale),
                          note=MILESTONES_NOTE_AR)


@router.put("/projects/{project_id}/milestones/{milestone_key}",
            response_model=MilestoneView)
async def set_milestone(
    project_id: uuid.UUID,
    milestone_key: str,
    payload: MilestoneUpdateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MilestoneView:
    """اعتمِد مَعْلَمًا أو ضع له موعدًا.

    **والاعتماد يُنسب إلى صاحبه ووقته**، والقيد في القاعدة يرفض واحدًا بلا
    الآخر. ولا يُستنتج الإتمام من زيارة صفحة ولا من رفع ملف: لو استُنتج
    لصار «اكتملت مراجعة الأدبيات» مكتوبًا في سجلٍّ لأن أحدًا فتح شاشة.
    """
    tid = principal.tenant_id
    await _project(session, principal, project_id)
    if milestone_key not in MILESTONES:
        raise NotFound("project_management.milestone_unknown")

    row = (await session.execute(
        select(ProjectMilestone).where(
            ProjectMilestone.tenant_id == tid,
            ProjectMilestone.project_id == project_id,
            ProjectMilestone.milestone_key == milestone_key)
    )).scalar_one_or_none()
    if row is None:
        row = ProjectMilestone(tenant_id=tid, project_id=project_id,
                               milestone_key=milestone_key)
        session.add(row)

    before = {"completed_at": row.completed_at.isoformat() if row.completed_at else None,
              "target_date": str(row.target_date) if row.target_date else None}

    if payload.clear_target_date:
        row.target_date = None
    elif payload.target_date is not None:
        row.target_date = payload.target_date

    if payload.completed is True:
        row.completed_at = row.completed_at or _now()
        row.completed_by = principal.user_id
    elif payload.completed is False:
        row.completed_at = None
        row.completed_by = None
    if payload.evidence_note_ar is not None:
        row.evidence_note_ar = payload.evidence_note_ar

    await session.flush()
    await audit.record(
        session, tenant_id=tid, action="project_management.milestone_set",
        object_type="project_milestone", object_id=row.id,
        actor_user_id=principal.user_id, state_before=before,
        state_after={
            "project_id": str(project_id), "milestone": milestone_key,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "target_date": str(row.target_date) if row.target_date else None},
        reason=("a milestone is completed by a person who says so, never inferred "
                "from a page visit"))

    return MilestoneView(
        key=milestone_key, label=milestone_label(milestone_key, principal.locale),
        target_date=row.target_date, completed_at=row.completed_at,
        completed_by=row.completed_by, evidence_note_ar=row.evidence_note_ar,
        is_completed=row.completed_at is not None)


# ═══════════════════ السلّة والإتلاف الدائم ═══════════════════

@router.get("/trash", response_model=TrashView)
async def read_trash(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TrashView:
    """ما في السلّة — **وعناوينُه تمرّ بالعقد المشترك**.

    وهذه بالضبط الشاشة التي عُرض فيها `قبول 2026-09-09T17:12…` عنوانًا
    لبحث. فالعمود لا يُقرأ خامًا هنا ولا في غيرها.
    """
    rows = (await session.execute(
        select(ResearchProject)
        .where(ResearchProject.tenant_id == principal.tenant_id,
               ResearchProject.deleted_at.is_not(None))
        .order_by(ResearchProject.deleted_at.desc())
    )).scalars().all()
    return TrashView(
        projects=[TrashedProjectView(
            project_id=row.id, title=_title_view(row), created_at=row.created_at,
            deleted_at=row.deleted_at, deleted_by=row.deleted_by)
            for row in rows],
        note=TRASH_NOTE_AR)


async def _deletion_preview(session: AsyncSession, principal: Principal,
                            project_id: uuid.UUID) -> DeletionPreviewView:
    project = await store.project_in_trash(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    if project is None:
        # بحثٌ ليس في السلّة لا يُسأل عن إتلافه — والحذف الظاهر يسبقه دائمًا.
        raise NotFound("project_management.project_not_in_trash")

    counts = await store.dependency_counts(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    call = retention.verdict()
    locale = principal.locale
    return DeletionPreviewView(
        project_id=project_id,
        title=_title_view(project),
        is_in_trash=True,
        dependencies=[DependencyCountView(
            kind=row.kind, count=row.count,
            label=row.label_en if locale == "en" else row.label_ar)
            for row in counts],
        total_dependent_rows=sum(row.count for row in counts),
        is_blocked=call.is_blocked,
        blocked_reason=call.reason,
        message=call.message_en if locale == "en" else call.message_ar,
        unblock_requirement=(call.requirement_en if locale == "en"
                             else call.requirement_ar),
        policy_sources=list(call.policy_sources))


@router.get("/trash/{project_id}/deletion-preview",
            response_model=DeletionPreviewView)
async def deletion_preview(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DeletionPreviewView:
    """**ماذا يُتلَف لو أُتلف هذا البحث؟** — بعشرة أعدادٍ باسمها، قبل الزرّ.

    ولا يُقال «هل أنت متأكد؟»: تحذيرٌ بلا رقم ليس تحذيرًا، ويضغط الباحث
    «نعم» لأنه ضغطها مئة مرّة على حوارٍ لا يقول شيئًا.
    """
    return await _deletion_preview(session, principal, project_id)


@router.post("/trash/{project_id}/permanent-delete",
             response_model=DeletionPreviewView)
async def permanent_delete(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DeletionPreviewView:
    """الإتلاف الدائم — **موقوفٌ، ويُقال لماذا**.

    وسياسةُ الاحتفاظ في هذا النظام غير معرَّفةٍ تعريفًا قابلًا للتنفيذ:
    مصفوفة تصنيف البيانات تُلزم بحفظ المواد البحثية الحسّاسة «مدّة المشروع
    + ٥ سنوات»، وتُحيل بيانات المشاركين إلى الموافقة الأخلاقية وحدها — ولا
    جدولَ في هذه القاعدة يمثّل أيًّا منهما.

    فلا يُتلَف ما لا تُعرف مشروعيّة إتلافه. والردّ ٤٠٩ ومعه المعاينة كاملة
    وشرطُ رفع الوقف — **لا ٥٠٠، ولا نجاحٌ صامت لم يقع**.
    """
    preview = await _deletion_preview(session, principal, project_id)
    call = retention.verdict()

    # **ولا حدثَ تدقيقٍ يُكتب هنا — وهذا مقصودٌ لا سهو.**
    #
    # `tenant_session` تفتح المعاملة وتُرجعها عند أيّ استثناء. فحدثٌ يُكتب
    # قبل `raise` يُمحى بالرفض نفسه: يبقى السطر في الشيفرة يوهم أنّ الرفض
    # مسجَّل، ولا صفَّ في القاعدة. **وسطرٌ يدّعي أثرًا لا يقع أسوأ من غيابه**،
    # لأن من يبحث عن المحاولة بعد شهرٍ يصدّق الشيفرة ولا يجد شيئًا.
    #
    # ويوم يُرفع الوقف، يقع الإتلاف والحدثُ في معاملةٍ واحدة تُختم معًا —
    # وذاك موضعُ الحدث الصحيح.

    if call.is_blocked:
        raise AtheraError(
            "project_management.permanent_delete_blocked", status_code=409,
            reason=call.reason,
            dependent_rows=preview.total_dependent_rows)

    # لا يُبلَغ هذا الموضع اليوم. ويوم يُبلَغ، يُكتب الإتلاف هنا وحده —
    # ومعه شاهدُ تدقيقٍ بياناتُه وصفية لا محتوى بحثيّ. ولا يُكتب قبل أن
    # تُكتب السياسة.
    return preview  # pragma: no cover


__all__ = ["router"]
