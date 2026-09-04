"""مساحة عمل البحث | Project workspace routes (PUBRIVA).

**البحث هو الشيء المركزي، لا الوحدة.** فما كان مبعثرًا في وحداتٍ متجاورة —
ملفات هنا ومراجع هناك ومخطوطة ثالثة — يُجمع تحت البحث الذي يخدمه.

ولا يُنشأ نظام مشاريع موازٍ: `research_projects` هو هو، وهذه الطرق تعرضه
بعلاقاته. وجدولا الربط الجديدان يصفان **العلاقة** لا الشيء.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.literature import Source
from ..models.portfolio import ProjectFile, ProjectSource, ResearchProject
from ..models.publishing import Manuscript
from ..models.research import FactCandidate, ResearcherMemory
from ..models.screening import (
    DEFAULT_PAGE_SIZE,
    EXCLUSION_REASON_CODES,
    MATRIX_FIELDS,
    MAX_PAGE_SIZE,
    LiteratureMatrixCell,
)
from ..schemas.screening import (
    AbstractView,
    BatchDecisionRequest,
    BatchDecisionView,
    MatrixCellRequest,
    MatrixCellVerifyRequest,
    MatrixCellView,
    MatrixExtractionRequest,
    MatrixExtractionView,
    MatrixRowView,
    MatrixView,
    ScreeningCardView,
    ScreeningFacetsView,
    ScreeningView,
    SourceAbstractsView,
    SourceExtractionView,
)
from ..schemas.workspace import (
    AssessmentItemView,
    BrainEntryView,
    ImpactView,
    LinkRequest,
    NextAction,
    ProjectAssessmentView,
    ProjectCreateRequest,
    ProjectFileView,
    ProjectOverview,
    ProjectRenameRequest,
    ProjectSourceView,
    ProjectSummary,
    SourceUseRequest,
)
from ..services import (
    audit,
    matrix_extraction,
    research_assessment,
    screening,
    workspace,
)

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


async def _project(session: AsyncSession, principal: Principal,
                   project_id: uuid.UUID) -> ResearchProject:
    row = await workspace.live_project(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    if row is None:
        raise NotFound("workspace.project_not_found")
    return row


async def _summary(session: AsyncSession, principal: Principal,
                   row: ResearchProject) -> ProjectSummary:
    """ملخّصٌ بأعدادٍ محسوبة، لا بحقولٍ مخزَّنة تتقادم بصمت."""
    tid = principal.tenant_id
    files = (await session.execute(
        select(func.count(ProjectFile.id)).where(
            ProjectFile.tenant_id == tid, ProjectFile.project_id == row.id,
            ProjectFile.state == ProjectFile.ACTIVE)
    )).scalar_one()
    sources = (await session.execute(
        select(func.count(ProjectSource.id)).where(
            ProjectSource.tenant_id == tid, ProjectSource.project_id == row.id,
            ProjectSource.use_state != "excluded")
    )).scalar_one()
    # المعرفة الموثقة **لهذا البحث** لا للمستأجر كله: العدد يُعرض على بطاقة
    # بحثٍ بعينه، ورقمٌ يعمّ المستأجر يقرأه الباحث حصيلةَ هذا البحث فيصدّقه.
    facts = (await session.execute(
        select(func.count(func.distinct(ResearcherMemory.id)))
        .join(FactCandidate,
              FactCandidate.resulting_memory_id == ResearcherMemory.id)
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(ResearcherMemory.tenant_id == tid,
               ResearcherMemory.verification_status == "verified",
               FactCandidate.tenant_id == tid,
               ProjectFile.tenant_id == tid,
               ProjectFile.project_id == row.id,
               ProjectFile.state == ProjectFile.ACTIVE)
    )).scalar_one()
    manuscripts = (await session.execute(
        select(func.count(Manuscript.id)).where(
            Manuscript.tenant_id == tid, Manuscript.project_id == row.id)
    )).scalar_one()
    return ProjectSummary(
        id=row.id, title_ar=row.working_title_ar, status=row.status,
        created_at=row.created_at, archived_at=row.archived_at,
        deleted_at=row.deleted_at, files=files, sources=sources,
        verified_facts=facts, manuscripts=manuscripts)


# ─────────────────────────────── البحوث ───────────────────────────────

@router.get("/projects", response_model=list[ProjectSummary])
async def list_projects(
    trash: bool = Query(default=False, description="اعرض ما في السلّة بدله"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSummary]:
    """بحوث الباحث — **وما في السلّة لا يظهر مع القائم**."""
    stmt = select(ResearchProject).where(ResearchProject.tenant_id == principal.tenant_id)
    stmt = (stmt.where(ResearchProject.deleted_at.is_not(None))
            if trash else stmt.where(ResearchProject.deleted_at.is_(None)))
    rows = (await session.execute(
        stmt.order_by(ResearchProject.created_at.desc()))).scalars().all()
    return [await _summary(session, principal, row) for row in rows]


@router.post("/projects", response_model=ProjectSummary,
             status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSummary:
    """ابدأ بحثًا — **بعنوانٍ وحده**.

    والمسار القديم `/portfolio/projects` يشترط ملفًّا تعريفيًّا للباحث
    ويرفض بدونه، ويطلب نوع الدراسة والمجلة المستهدفة. وهذا يصحّ لمن يخطّط
    محفظةً كاملة، ولا يصحّ لمن معه فكرةٌ الآن: **الاستمارةُ قبل الفكرة
    توقف الباحث عند الباب**. فيُنشأ البحث بأقلّ ما يلزم، وتُملأ بقيّته حين
    تُعرف — والحقول نفسها والجدول نفسه، لا نظام مشاريع ثانٍ.
    """
    project = ResearchProject(
        tenant_id=principal.tenant_id, working_title_ar=payload.title_ar,
        status="planned", current_gate="G1")
    session.add(project)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.project_created",
        object_type="research_project", object_id=project.id,
        actor_user_id=principal.user_id,
        state_after={"title": payload.title_ar[:120],
                     "starting_from": payload.starting_from},
        reason="a project starts from an idea; the rest of the form is filled when known")
    return await _summary(session, principal, project)


@router.patch("/projects/{project_id}", response_model=ProjectSummary)
async def rename_project(
    project_id: uuid.UUID,
    payload: ProjectRenameRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSummary:
    project = await _project(session, principal, project_id)
    before = project.working_title_ar
    project.working_title_ar = payload.title_ar
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.project_renamed",
        object_type="research_project", object_id=project.id,
        actor_user_id=principal.user_id, state_before={"title": before[:120]},
        state_after={"title": payload.title_ar[:120]},
        reason="the working title changes as the research matures")
    return await _summary(session, principal, project)


@router.post("/projects/{project_id}/archive", response_model=ProjectSummary)
async def archive_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSummary:
    """أرشِف — **البحث المؤجَّل ليس محذوفًا**."""
    project = await _project(session, principal, project_id)
    project.archived_at = project.archived_at or dt.datetime.now(dt.UTC)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.project_archived",
        object_type="research_project", object_id=project.id,
        actor_user_id=principal.user_id,
        state_after={"archived_at": project.archived_at.isoformat()},
        reason="paused research stays reachable; archiving is not deletion")
    return await _summary(session, principal, project)


@router.delete("/projects/{project_id}", response_model=ImpactView)
async def trash_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ImpactView:
    """انقل إلى السلّة — **ولا يُتلَف شيء**.

    فالحذفُ الظاهر تأجيلٌ لا إتلاف: صفوف البحث كلها باقية، والاستعادة
    ترجعه كما كان. وسنواتُ عملٍ لا تُعاد كتابتها بضغطةٍ واحدة.
    """
    project = await _project(session, principal, project_id)
    project.deleted_at = dt.datetime.now(dt.UTC)
    project.deleted_by = principal.user_id
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.project_trashed",
        object_type="research_project", object_id=project.id,
        actor_user_id=principal.user_id,
        state_after={"deleted_at": project.deleted_at.isoformat()},
        reason="deletion is deferred, never destructive; the project is restorable")
    return ImpactView(is_safe=True, breaks_approved_work=False,
                      summary="نُقل البحث إلى السلّة، ويمكن استعادته كما كان.")


@router.post("/projects/{project_id}/restore", response_model=ProjectSummary)
async def restore_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSummary:
    row = (await session.execute(
        select(ResearchProject).where(
            ResearchProject.id == project_id,
            ResearchProject.tenant_id == principal.tenant_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound("workspace.project_not_found")
    row.deleted_at, row.deleted_by = None, None
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.project_restored",
        object_type="research_project", object_id=row.id,
        actor_user_id=principal.user_id, state_after={"deleted_at": None},
        reason="restoring returns the project with every relation intact")
    return await _summary(session, principal, row)


# ────────────────────────────── الملخّص العام ──────────────────────────────

@router.get("/projects/{project_id}/overview", response_model=ProjectOverview)
async def project_overview(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectOverview:
    """حالُ البحث — **بحالاتٍ صادقة لا بنسبةٍ واحدة**.

    ونسبةُ «جاهزية ٪» تُخفي الفرق بين بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج.
    فتُذكر العناصر بأسمائها وحالاتها، ويُقترح **فعلٌ واحد** هو الأولى.
    """
    project = await _project(session, principal, project_id)
    brain = await workspace.research_brain(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    action = await workspace.next_action(
        session, tenant_id=principal.tenant_id, project_id=project_id)

    blockers = [e.label_ar for e in brain
                if e.state == "missing" and e.key in {"problem", "question", "method"}]
    return ProjectOverview(
        project=await _summary(session, principal, project),
        brain=[BrainEntryView(key=e.key, label=e.label_ar, state=e.state,
                              value=e.value_ar, sources=e.sources) for e in brain],
        recommended_next=NextAction(key=action[0], label=action[1]) if action else None,
        blockers=blockers,
        note=("لا تُعرض نسبةُ جاهزية: الحالات أعلاه هي الحقيقة، وما كان "
              "«ناقصًا» في بحثٍ في أوله ليس خطأً."))


@router.get("/projects/{project_id}/assessment", response_model=ProjectAssessmentView)
async def project_assessment(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectAssessmentView:
    """تقييمُ العقل البحثي لهذا البحث — **مشورةٌ تُقرأ لا بوابةٌ تُغلق**.

    والقواعد العشر تُشغَّل على لقطةٍ تُبنى من صفوف **هذا البحث** وحدها. وكلها
    مسوّدة حتى يراجعها مختصّ، فـ`blocking` فارغة ولا سطر منها يوقف باحثًا:
    محرّكٌ يحجب بقواعد كتبها مبرمج بلا مراجعة يوقف بحثًا صحيحًا باسم النزاهة.

    و«لم نجد شيئًا» لا تُعرض سلامةً: ما عجزت القاعدة عن فحصه يظهر في «ما
    يحتاج مراجعة» بنصّه، وما تعذّرت قراءته من البحث يظهر في «ما ينقص».
    """
    await _project(session, principal, project_id)
    snapshot = await research_assessment.build_project_assessment(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    if snapshot is None:  # pragma: no cover - `_project` سبق أن أثبت وجوده
        raise NotFound("workspace.project_not_found")

    _report, view = research_assessment.assess(snapshot)

    def _items(rows) -> list[AssessmentItemView]:
        return [AssessmentItemView(
            key=row.key,
            detail=row.detail_ar if principal.locale == "ar" else row.detail_en,
            rule_id=row.rule_id, entity_ids=list(row.entity_ids), excerpt=row.excerpt)
            for row in rows]

    arabic = principal.locale == "ar"
    return ProjectAssessmentView(
        project_id=project_id, title=snapshot.title_ar,
        known=_items(view.known), missing=_items(view.missing),
        needs_review=_items(view.needs_review), conflicts=_items(view.conflicts),
        methodological_alerts=_items(view.methodological_alerts),
        read_notes=_items(view.read_notes),
        is_advisory_only=view.is_advisory_only, blocking_count=view.blocking_count,
        advisory_note=(research_assessment.ADVISORY_NOTE_AR if arabic
                       else research_assessment.ADVISORY_NOTE_EN),
        note=(research_assessment.NO_SCORE_NOTE_AR if arabic
              else research_assessment.NO_SCORE_NOTE_EN))


# ─────────────────────────────── ملفات البحث ───────────────────────────────

@router.get("/projects/{project_id}/files", response_model=list[ProjectFileView])
async def project_files(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectFileView]:
    await _project(session, principal, project_id)
    rows = (await session.execute(
        select(ProjectFile, File)
        .join(File, File.id == ProjectFile.file_id)
        .where(ProjectFile.tenant_id == principal.tenant_id,
               ProjectFile.project_id == project_id)
        .order_by(ProjectFile.created_at.desc())
    )).all()

    out: list[ProjectFileView] = []
    for link, file in rows:
        processing, candidates, reviewed, thesis_id = await workspace.file_processing_state(
            session, tenant_id=principal.tenant_id, file_id=file.id)
        out.append(ProjectFileView(
            file_id=file.id, filename=file.original_filename,
            content_type=file.content_type, size_bytes=file.size_bytes,
            added_at=link.created_at, state=link.state,
            processing_status=processing, thesis_id=thesis_id,
            candidates=candidates, reviewed=reviewed))
    return out


@router.post("/projects/{project_id}/files", response_model=ProjectFileView,
             status_code=status.HTTP_201_CREATED)
async def link_file(
    project_id: uuid.UUID,
    payload: LinkRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectFileView:
    """اربط ملفًّا من المكتبة بهذا البحث — **بلا نسخ**."""
    await _project(session, principal, project_id)
    file = (await session.execute(
        select(File).where(File.id == payload.asset_id,
                           File.tenant_id == principal.tenant_id)
    )).scalar_one_or_none()
    if file is None:
        raise NotFound("workspace.file_not_found")

    existing = (await session.execute(
        select(ProjectFile).where(
            ProjectFile.tenant_id == principal.tenant_id,
            ProjectFile.project_id == project_id,
            ProjectFile.file_id == file.id)
    )).scalar_one_or_none()
    if existing is not None:
        existing.state = ProjectFile.ACTIVE
        link = existing
    else:
        link = ProjectFile(tenant_id=principal.tenant_id, project_id=project_id,
                           file_id=file.id, state=ProjectFile.ACTIVE,
                           added_by=principal.user_id)
        session.add(link)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.file_linked",
        object_type="project_file", object_id=link.id, actor_user_id=principal.user_id,
        state_after={"project_id": str(project_id), "file_id": str(file.id)},
        reason="a library file is linked to a project, never copied into it")
    return ProjectFileView(
        file_id=file.id, filename=file.original_filename,
        content_type=file.content_type, size_bytes=file.size_bytes,
        added_at=link.created_at, state=link.state)


@router.get("/projects/{project_id}/files/{file_id}/impact", response_model=ImpactView)
async def file_removal_impact(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ImpactView:
    """ماذا يترتب على إزالته — **قبل أن تقع، لا بعد**."""
    await _project(session, principal, project_id)
    impact = await workspace.file_impact(
        session, tenant_id=principal.tenant_id, project_id=project_id, file_id=file_id)
    return ImpactView(
        is_safe=impact.is_safe, breaks_approved_work=impact.breaks_approved_work,
        summary=impact.summary_ar(),
        consequences=[{"kind": c.kind, "count": c.count, "label": c.label_ar,
                       "breaks_approved_work": c.breaks_approved_work}
                      for c in impact.consequences])


@router.delete("/projects/{project_id}/files/{file_id}", response_model=ImpactView)
async def unlink_file(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    acknowledged: bool = Query(default=False,
                               description="أقرّ الباحث بما يترتب على الإزالة"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ImpactView:
    """أزِل الملف من البحث — **ولا يُحذف من المكتبة**.

    وإن كان يسند عملًا معتمَدًا لم تقع الإزالة حتى يُقرّ الباحث بما يترتب:
    فالتحذير الذي يُعرض بعد الفعل ليس تحذيرًا.
    """
    await _project(session, principal, project_id)
    link = (await session.execute(
        select(ProjectFile).where(
            ProjectFile.tenant_id == principal.tenant_id,
            ProjectFile.project_id == project_id, ProjectFile.file_id == file_id)
    )).scalar_one_or_none()
    if link is None:
        raise NotFound("workspace.file_not_linked")

    impact = await workspace.file_impact(
        session, tenant_id=principal.tenant_id, project_id=project_id, file_id=file_id)
    view = ImpactView(
        is_safe=impact.is_safe, breaks_approved_work=impact.breaks_approved_work,
        summary=impact.summary_ar(),
        consequences=[{"kind": c.kind, "count": c.count, "label": c.label_ar,
                       "breaks_approved_work": c.breaks_approved_work}
                      for c in impact.consequences])
    if impact.breaks_approved_work and not acknowledged:
        raise AtheraError("workspace.removal_needs_acknowledgement",
                          status_code=status.HTTP_409_CONFLICT,
                          summary=view.summary)

    link.state = ProjectFile.ARCHIVED
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.file_unlinked",
        object_type="project_file", object_id=link.id, actor_user_id=principal.user_id,
        state_after={"state": ProjectFile.ARCHIVED, "acknowledged": acknowledged,
                     "consequences": len(impact.consequences)},
        reason="removing a file from a project never deletes it from the library")
    return view


# ────────────────────────────── مراجع البحث ──────────────────────────────

def _cell_view(cell: LiteratureMatrixCell) -> MatrixCellView:
    """خليةٌ مخزَّنة كما تُعرض — **بحالها ومَداها معًا، لا بقيمتها وحدها**.

    والبناء في الخدمة لا هنا: صفُّ المصفوفة والجوابُ المفرد يعرضان الخلية
    نفسها، ونسختان تفترقان بأول عمودٍ يُضاف — فيظهر في الشاشة عمودٌ ولا
    يظهر بعد الحفظ.
    """
    return MatrixCellView(**asdict(screening.cell_view(cell)))


def _source_view(link: ProjectSource, source: Source) -> ProjectSourceView:
    """صفُّ مرجعٍ في بحث — **بحاله وسببه معًا**.

    وكانت الحال تُعاد وحدها، فيقرأ الباحث «مستبعَدة» ولا يعرف لماذا. وهو
    الموضع نفسه في كل شاشة تعرض هذا الصفّ، فيُكتب مرّة هنا.
    """
    return ProjectSourceView(
        source_id=source.id, title=source.title, doi=source.doi,
        publication_year=source.publication_year, use_state=link.use_state,
        added_at=link.created_at, decided_at=link.decided_at,
        exclusion_reason_code=link.exclusion_reason_code,
        reason_ar=link.reason_ar)

@router.get("/projects/{project_id}/sources", response_model=list[ProjectSourceView])
async def project_sources(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSourceView]:
    await _project(session, principal, project_id)
    rows = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == principal.tenant_id,
               ProjectSource.project_id == project_id)
        .order_by(ProjectSource.created_at.desc())
    )).all()
    return [_source_view(link, source) for link, source in rows]


@router.post("/projects/{project_id}/sources", response_model=ProjectSourceView,
             status_code=status.HTTP_201_CREATED)
async def link_source(
    project_id: uuid.UUID,
    payload: LinkRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSourceView:
    """أضِف مرجعًا — **محفوظًا فقط حتى يقرأه الباحث**.

    فالاستيراد ليس حكمًا بالصلاحية دليلًا، وجعلُ كل مستورَدٍ «مُدرَجًا»
    يبني ورقةً على ما لم يقرأه أحد.
    """
    await _project(session, principal, project_id)
    source = (await session.execute(
        select(Source).where(Source.id == payload.asset_id,
                             Source.tenant_id == principal.tenant_id)
    )).scalar_one_or_none()
    if source is None:
        raise NotFound("workspace.source_not_found")

    link = (await session.execute(
        select(ProjectSource).where(
            ProjectSource.tenant_id == principal.tenant_id,
            ProjectSource.project_id == project_id,
            ProjectSource.source_id == source.id)
    )).scalar_one_or_none()
    if link is None:
        link = ProjectSource(tenant_id=principal.tenant_id, project_id=project_id,
                             source_id=source.id, use_state="saved_only",
                             added_by=principal.user_id)
        session.add(link)
        await session.flush()
        await audit.record(
            session, tenant_id=principal.tenant_id, action="workspace.source_linked",
            object_type="project_source", object_id=link.id,
            actor_user_id=principal.user_id,
            state_after={"project_id": str(project_id), "use_state": "saved_only"},
            reason="importing a source is not a judgement that it is evidence")
    return _source_view(link, source)


@router.patch("/projects/{project_id}/sources/{source_id}",
              response_model=ProjectSourceView)
async def set_source_use(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SourceUseRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSourceView:
    """قرّر حال المرجع في هذا البحث — **والقرار يُنسب إلى صاحبه**.

    وهذا هو المسار الوحيد لقرار الفرز: شاشةُ الفرز وقائمةُ مراجع البحث
    تنادِيانه كلتاهما، فلا تنشأ حقيقتان لحالٍ واحدة.

    **والاستبعاد لا يقع بلا سبب.** حكمٌ بلا سببٍ مسجَّل لا يُراجَع بعد شهر
    ولا يُكتب في قسم المنهجية؛ فيُردّ الطلب بلا رمزٍ من القائمة المغلقة،
    و«سبب آخر» يلزمه نصّه.

    **ولا يُستنتج استبعادٌ آليًّا.** لا شيء في هذا المسار يقرأ حالًا ويحكم:
    الحال تأتي من الطلب، والفاعل من الرمز، والوقت من الساعة.
    """
    await _project(session, principal, project_id)
    row = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == principal.tenant_id,
               ProjectSource.project_id == project_id,
               ProjectSource.source_id == source_id)
    )).first()
    if row is None:
        raise NotFound("workspace.source_not_linked")
    link, source = row

    before = link.use_state
    before_reason = link.exclusion_reason_code
    if payload.use_state == "excluded":
        if not screening.reason_is_acceptable(payload.reason_code, payload.reason_ar):
            # 422 لا 400: الطلب مفهوم وصياغته صحيحة، وما ينقصه شرطٌ في
            # المعنى — فيُقال ذلك برمزٍ له ترجمتان، لا بـ500 من قيد القاعدة.
            raise AtheraError("workspace.exclusion_needs_reason",
                              status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
        impact = await workspace.source_impact(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            source_id=source_id)
        if impact.breaks_approved_work:
            raise AtheraError(
                "workspace.source_still_cited",
                status_code=status.HTTP_409_CONFLICT,
                summary=impact.summary_ar())

    # **كاتبٌ واحد للحال يخدم الفرد والدفعة.** ودالّتان تكتبانها تفترقان
    # بأول شرطٍ يُضاف، فتسمح الدفعة بما يمنعه الفرد — وهي التي تقع على
    # عشرين مرجعًا مرّة.
    screening.apply_decision(
        link=link, use_state=payload.use_state,
        reason_code=payload.reason_code, reason_ar=payload.reason_ar,
        actor_user_id=principal.user_id, now=dt.datetime.now(dt.UTC))
    await session.flush()
    # **الأثر يحمل الرمز ولا يحمل نصًّا من المستند.** رمزُ السبب مفردةٌ
    # مغلقة تُعدّ وتُقارن؛ أما ملاحظة الباحث فقد تقتبس من الورقة، ومحتوى
    # المستندات لا يدخل سجلّ التدقيق (§37).
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.source_use_set",
        object_type="project_source", object_id=link.id,
        actor_user_id=principal.user_id,
        state_before={"use_state": before, "reason_code": before_reason},
        state_after={"use_state": payload.use_state,
                     "reason_code": link.exclusion_reason_code,
                     "has_note": bool(payload.reason_ar)},
        reason="including a source as evidence is a researcher decision, attributed")
    return _source_view(link, source)


# ─────────────────── الفرز · الدراسات المدرجة والمستبعدة ───────────────────

@router.get("/projects/{project_id}/screening", response_model=ScreeningView)
async def screening_workspace(
    project_id: uuid.UUID,
    use_state: str | None = Query(
        default=None, pattern="^(included|saved_only|excluded)$",
        description="اقصر العرض على حالٍ واحدة"),
    page: int = Query(default=1, ge=1, description="رقم الصفحة"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE,
                           description="عدد البطاقات في الصفحة"),
    year_from: int | None = Query(default=None, ge=1000, le=2200,
                                  description="من سنة النشر"),
    year_to: int | None = Query(default=None, ge=1000, le=2200,
                                description="إلى سنة النشر"),
    registry: str | None = Query(default=None, max_length=32,
                                 description="الفهرس الذي جاء منه المرجع"),
    document_type: str | None = Query(default=None, max_length=64,
                                      description="نوع الوثيقة كما أعلنه الفهرس"),
    open_access: bool | None = Query(
        default=None, description="ما أعلن الفهرس أنه مفتوح الوصول — دعوى حقوق"),
    has_abstract: bool | None = Query(default=None, description="ما له ملخّص"),
    has_full_text: bool | None = Query(
        default=None, description="ما في يدك نصّه الكامل في هذا البحث"),
    possible_duplicate: bool | None = Query(
        default=None, description="ما يشترك مع مرجعٍ آخر في هذا البحث"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ScreeningView:
    """شاشة الفرز — **بطاقةٌ تُعرَف بها الدراسة، لا سطرٌ بمعرّف**.

    كل بطاقة تحمل العنوان والمؤلفين والسنة والوعاء ومن أين جاء المرجع
    وحالَه الآن. و`doi` يظهر متحقَّقًا أو لا يظهر: معرّفٌ لم يُحلّ في فهرسٍ
    معروضًا بجانب دراسةٍ يُقرأ إثباتًا فيُنسخ في قائمة المراجع بلا فحص.

    و`reading_scope` يقول **ما يمكن قراءته فعلًا** من هذا المرجع في هذا
    البحث — وعليه تُبنى المصفوفة لاحقًا، فلا يدّعي الباحث نصًّا ليس في يده.

    **والبحث الجادّ فيه ألفُ مرجعٍ لا عشرون.** فلا تُحمَّل كلُّها: المرشّحات
    تُلحق بالعبارة في القاعدة **قبل أي حدّ**، ثم تُقتطع الصفحة. وتصفيةٌ تقع
    بعد الاقتطاع كذبة — تعرض ثلاثة من عشرين جُلبت وتقول «ثلاث دراسات».

    **والعدّادات من القاعدة كذلك**، وبكل المرشّحات إلا حال الفرز نفسها:
    التبويب يسأل «كم مُدرَجة ضمن ما أراه الآن»، لا «كم في هذه الصفحة».
    """
    await _project(session, principal, project_id)
    filters = screening.ScreeningFilters(
        use_state=use_state, year_from=year_from, year_to=year_to,
        registry=registry, document_type=document_type, open_access=open_access,
        has_abstract=has_abstract, has_full_text=has_full_text,
        possible_duplicate=possible_duplicate)
    result = await screening.screening_page(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        filters=filters, page=page, page_size=page_size)
    facets = await screening.screening_facets(
        session, tenant_id=principal.tenant_id, project_id=project_id)

    return ScreeningView(
        project_id=project_id,
        # `asdict` لا `vars`: البطاقة `slots` فلا `__dict__` لها — و`vars`
        # عليها ترمي في وقت التشغيل، وهو عطبٌ لا يظهر إلا على الشاشة.
        cards=[ScreeningCardView(**asdict(card)) for card in result.cards],
        saved_only=result.tallies.saved_only,
        included=result.tallies.included,
        excluded=result.tallies.excluded,
        all=result.tallies.all,
        page=result.page, page_size=result.page_size,
        total=result.total, pages=result.pages,
        duplicates=result.duplicates,
        facets=ScreeningFacetsView(**asdict(facets)),
        reason_codes=list(EXCLUSION_REASON_CODES),
    )


@router.post("/projects/{project_id}/screening/batch",
             response_model=BatchDecisionView)
async def batch_decide(
    project_id: uuid.UUID,
    payload: BatchDecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BatchDecisionView:
    """قرارُ فرزٍ على مجموعة — **يقع كلُّه أو لا يقع منه شيء**.

    وتسعةَ عشرَ قرارًا وقعت وواحدٌ فشل أسوأ من عشرين فشلت: الباحث يرى رسالة
    خطأ فيعيد الأمر، فيقع بعضه مرّتين ولا يعرف أيُّها وقع أصلًا. فالفحص
    يجري على المجموعة كاملةً أولًا — كلُّ مرجعٍ مربوطٌ بهذا البحث، والسبب
    مقبول، ولا واحدٌ منها مستشهَدٌ به في عملٍ معتمَد — ثم تُكتب.

    **وأيّ رفضٍ يرفع استثناءً، والمعاملة تُلغى كلُّها معه**: لا شيء يُكتب
    على دفعات، ولا `flush` قبل اكتمال الفحص.

    **والاستبعاد في الدفعة يلزمه سببه** كالفرد سواء — والقيد في القاعدة
    يرفض غير ذلك، فيُقال هنا برمزٍ له ترجمتان لا بخطأ قاعدة.
    """
    await _project(session, principal, project_id)
    # التكرار في الطلب يُطوى: مرجعٌ ذُكر مرّتين قرارٌ واحد، والعدّ المُعاد
    # يجعل «طُبّق على ٢١» وهي عشرون.
    wanted = list(dict.fromkeys(payload.source_ids))

    if payload.use_state == "excluded" and not screening.reason_is_acceptable(
            payload.reason_code, payload.reason_ar):
        raise AtheraError("workspace.exclusion_needs_reason",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    rows = (await session.execute(
        select(ProjectSource).where(
            ProjectSource.tenant_id == principal.tenant_id,
            ProjectSource.project_id == project_id,
            ProjectSource.source_id.in_(wanted))
    )).scalars().all()
    links = {link.source_id: link for link in rows}
    # **مرجعٌ من بحثٍ آخر يُردّ، ولا يُتخطّى بصمت.** والتخطّي يجعل الباحث
    # يقرأ «طُبّق على ٢٠» وقد طُبّق على ثمانية عشر.
    missing = [source_id for source_id in wanted if source_id not in links]
    if missing:
        raise NotFound("workspace.source_not_linked",
                       source_id=str(missing[0]), missing=len(missing))

    # فحصُ الاستشهاد قبل أي كتابة: مرجعٌ مستشهَدٌ به في عملٍ معتمَد لا يُستبعد
    # بأثرٍ جانبي لدفعة.
    if payload.use_state == "excluded":
        for source_id in wanted:
            impact = await workspace.source_impact(
                session, tenant_id=principal.tenant_id, project_id=project_id,
                source_id=source_id)
            if impact.breaks_approved_work:
                raise AtheraError(
                    "workspace.source_still_cited",
                    status_code=status.HTTP_409_CONFLICT,
                    source_id=str(source_id), summary=impact.summary_ar())

    now = dt.datetime.now(dt.UTC)
    for source_id in wanted:
        link = links[source_id]
        before = screening.apply_decision(
            link=link, use_state=payload.use_state,
            reason_code=payload.reason_code, reason_ar=payload.reason_ar,
            actor_user_id=principal.user_id, now=now)
        await audit.record(
            session, tenant_id=principal.tenant_id,
            action="workspace.source_use_set",
            object_type="project_source", object_id=link.id,
            actor_user_id=principal.user_id, state_before=before,
            state_after={"use_state": payload.use_state,
                         "reason_code": link.exclusion_reason_code,
                         "has_note": bool(payload.reason_ar),
                         "batch_of": len(wanted)},
            reason="a batch decision is one judgement applied to named sources")
    await session.flush()
    return BatchDecisionView(project_id=project_id, use_state=payload.use_state,
                             applied=len(wanted), source_ids=wanted)


@router.get("/projects/{project_id}/sources/{source_id}/abstracts",
            response_model=SourceAbstractsView)
async def source_abstracts(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SourceAbstractsView:
    """ملخّصات هذا المرجع — **كلُّها منسوبةً، ولا يُطوى اثنان في واحد**.

    وفهرسان يرسلان نصّين مختلفين للورقة نفسها حالٌ واقعة؛ وأن يغلب أحدهما
    الآخر بصمت يجعل الباحث يقرأ نصف الحقيقة ويظنّه كلّها. فيُعرضان معًا
    باسم مرسِل كلٍّ ووقته، ويحكم هو.
    """
    await _project(session, principal, project_id)
    row = (await session.execute(
        select(Source)
        .join(ProjectSource, ProjectSource.source_id == Source.id)
        .where(Source.tenant_id == principal.tenant_id,
               ProjectSource.tenant_id == principal.tenant_id,
               ProjectSource.project_id == project_id,
               ProjectSource.source_id == source_id)
    )).scalar_one_or_none()
    if row is None:
        raise NotFound("workspace.source_not_linked")
    stored = (await screening.stored_abstracts_by_source(
        session, tenant_id=principal.tenant_id, source_ids=[source_id])
    ).get(source_id, [])
    records = screening.abstracts_of(row, stored)
    return SourceAbstractsView(
        source_id=source_id,
        abstracts=[AbstractView(id=record.stored_id, provider=record.provider,
                                provider_identifier=record.provider_identifier,
                                text=record.text,
                                retrieved_at=record.retrieved_at)
                   for record in records],
        disagree=len({record.content_hash for record in records}) > 1,
    )


# ────────────────────────── مصفوفة الأدبيات ──────────────────────────

@router.get("/projects/{project_id}/matrix", response_model=MatrixView)
async def literature_matrix(
    project_id: uuid.UUID,
    page: int = Query(default=1, ge=1, description="رقم الصفحة"),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE,
                           description="عدد الدراسات في الصفحة"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MatrixView:
    """مصفوفة الأدبيات — **للدراسات المدرجة وحدها**.

    ومرجعٌ «محفوظ فقط» لم يُقرَّر بعدُ أنه دليل؛ ووضعُه في المصفوفة يجعل
    الباحث يبني تحليله على ما لم يحكم عليه. أما المستبعَد فقراره أن يُترك.

    وكل خلية تحمل مَداها: خانةٌ فارغة تُقرأ «لا شيء يستحق الذكر»، و
    `missing` تُقرأ «لم يُذكر في المصدر» — والثانية وحدها فجوةٌ تُعالَج.
    """
    await _project(session, principal, project_id)
    rows = await screening.matrix_rows(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        page=page, page_size=page_size)
    # العدد من القاعدة لا من طول الصفحة: ستةَ عشرَ عمودًا في ألف صفٍّ ستةَ
    # عشرَ ألف خلية، والمتصفّح يتوقّف قبل أن يُنهي رسمها.
    total = await screening.included_source_count(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    size = max(1, min(page_size, MAX_PAGE_SIZE))
    return MatrixView(
        project_id=project_id,
        fields=list(MATRIX_FIELDS),
        rows=[MatrixRowView(
            source_id=row.source_id, title=row.title, authors=row.authors,
            publication_year=row.publication_year, doi=row.doi,
            reading_scope=row.reading_scope,
            cells=[MatrixCellView(**asdict(cell)) for cell in row.cells])
            for row in rows],
        page=max(1, page), page_size=size, total=total,
        pages=max(1, -(-total // size)),
    )


async def _included_link(session: AsyncSession, principal: Principal,
                         project_id: uuid.UUID, source_id: uuid.UUID) -> ProjectSource:
    """المرجع المُدرَج وحده تُكتب له خلية — والباقي يُردّ بسببه مفهومًا."""
    link = (await session.execute(
        select(ProjectSource).where(
            ProjectSource.tenant_id == principal.tenant_id,
            ProjectSource.project_id == project_id,
            ProjectSource.source_id == source_id)
    )).scalar_one_or_none()
    if link is None:
        raise NotFound("workspace.source_not_linked")
    if link.use_state != "included":
        raise AtheraError("workspace.matrix_needs_included_source",
                          status_code=status.HTTP_409_CONFLICT)
    return link


@router.post("/projects/{project_id}/matrix/extract",
             response_model=MatrixExtractionView)
async def extract_matrix(
    project_id: uuid.UUID,
    payload: MatrixExtractionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MatrixExtractionView:
    """اقرأ ما هو متاحٌ لهذه المراجع واكتب مرشّحاتها — **مرشّحاتٍ لا معرفة**.

    **والمدرَجة وحدها تُقرأ.** مرجعٌ «محفوظ فقط» لم يقرّر الباحث بعدُ أنه
    دليل؛ وتحليلُه يبني المصفوفة على ما لم يُحكم عليه، ثم يُكتب منها.

    **والمدى قيدٌ لا ترجيح.** بياناتٌ وصفية لا يُقرأ منها منهجٌ ولا عيّنة —
    فتشغيلةٌ على مرجعٍ لا ملخّص له ولا نصّ لا تكتب خليةً واحدة، ويُقال ذلك
    في الجواب: `filled = 0` و`scope = metadata_only`، لا نجاحٌ صامت.

    **ولا تُدهس يدُ إنسان.** خليةٌ كتبها الباحث أو حكم فيها لا تُمسّ،
    ويُقال عددها في `left_to_the_researcher`.

    وكلُّ ما يُكتب `needs_review` و`unverified` وطريقته `model` — وقيدُ
    القاعدة `model_value_is_not_self_approved` يمنع أن يُكتب معتمَدًا بلا
    مُعتمِدٍ بشريّ يُسمّى. والاعتماد يمرّ بمسار المراجعة القائم نفسه، ولا
    نظامَ اعتمادٍ ثانٍ يُبنى بجانبه.
    """
    await _project(session, principal, project_id)
    wanted = list(dict.fromkeys(payload.source_ids))
    # الفحص على المجموعة كاملةً قبل أي كتابة — كالدفعة سواء.
    for source_id in wanted:
        await _included_link(session, principal, project_id, source_id)

    sources = {
        row.id: row
        for row in (await session.execute(
            select(Source).where(Source.tenant_id == principal.tenant_id,
                                 Source.id.in_(wanted))
        )).scalars().all()
    }
    absent = [source_id for source_id in wanted if source_id not in sources]
    if absent:
        raise NotFound("workspace.source_not_found", source_id=str(absent[0]))

    files = await screening.readable_project_file_ids(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    stored = await screening.stored_abstracts_by_source(
        session, tenant_id=principal.tenant_id, source_ids=wanted)

    results: list[SourceExtractionView] = []
    for source_id in wanted:
        source = sources[source_id]
        rows = stored.get(source_id, [])
        scope = screening.reading_scope(
            source, project_file_ids=files, stored_abstracts=rows)
        outcome = await matrix_extraction.extract_for_source(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            source=source, scope=scope, actor_user_id=principal.user_id,
            stored_abstracts=rows)
        results.append(SourceExtractionView(**asdict(outcome)))
        # **الأثر يحمل العدد والمدى ولا يحمل نصًّا من المستند** (§37).
        await audit.record(
            session, tenant_id=principal.tenant_id,
            action="literature_matrix.extraction_run",
            object_type="project_source", object_id=source_id,
            actor_user_id=principal.user_id,
            state_after={"scope": outcome.scope, "filled": outcome.filled,
                         "marked_missing": outcome.marked_missing,
                         "left_to_the_researcher": outcome.left_to_the_researcher},
            reason="an automatic reading proposes candidates; only a human approves")
    return MatrixExtractionView(project_id=project_id, results=results)


@router.put("/projects/{project_id}/matrix/{source_id}/{field_key}",
            response_model=MatrixCellView)
async def set_matrix_cell(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    field_key: str,
    payload: MatrixCellRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MatrixCellView:
    """اكتب خليةً — **ولا تُخمَّن خلية أبدًا**.

    أربعةٌ تُفحص قبل الكتابة، وكلّها ترفض ادّعاءً أكبر مما قُرئ:

    **المدى لا يتجاوز المتاح.** مرجعٌ لا نصّ له في يد الباحث لا تُكتب عنه
    خليةٌ مَداها `full_text`؛ ومرجعٌ بلا ملخّصٍ مُرسَل لا يُقرأ منه ملخّص.
    والمتاح يُحسب من حقّ الوصول ومن وجود ملفٍّ مرتبطٍ بهذا البحث — لا من
    نيّة الكاتب.

    **والغياب غياب.** `missing` لا تحمل قيمةً ولا شاهدًا: مقياسٌ لم يُذكر في
    الورقة يظهر في عمود «المقاييس» ثم يُكتب في المنهجية أنه استُعمل.

    **ولا مقتطف بلا نصّ** (§14.5): بياناتٌ وصفية لا يُقتبس منها شيء.

    **ولا تُخترع أرقام صفحات.** خليةٌ قُرئت من ملخّصٍ إمّا بلا مُحدِّد وإمّا
    بالكلمة الصريحة «الملخّص» — ولا صفحة لملخّص.
    """
    await _project(session, principal, project_id)
    if field_key not in MATRIX_FIELDS:
        raise NotFound("workspace.matrix_field_unknown", field=field_key)
    await _included_link(session, principal, project_id, source_id)

    source = (await session.execute(
        select(Source).where(Source.id == source_id,
                             Source.tenant_id == principal.tenant_id)
    )).scalar_one_or_none()
    if source is None:
        raise NotFound("workspace.source_not_found")

    files = await screening.project_file_ids(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    scope = screening.reading_scope(source, project_file_ids=files)
    if not scope.permits(payload.source_scope):
        raise AtheraError("workspace.scope_not_available",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                          available=scope.scope, requested=payload.source_scope)

    missing = payload.cell_state == "missing"
    if missing and (payload.value_ar or payload.evidence_quote
                    or payload.evidence_locator):
        raise AtheraError("workspace.missing_cell_carries_value",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if not missing and not (payload.value_ar or "").strip():
        raise AtheraError("workspace.stated_cell_needs_value",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if payload.evidence_quote and payload.source_scope == screening.METADATA_ONLY:
        raise AtheraError("workspace.quote_without_text",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if not screening.locator_is_honest(payload.source_scope, payload.evidence_locator):
        raise AtheraError("workspace.invented_locator",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    # **ولا صفحة ولا قسم من غير نصٍّ كامل.** ملخّصٌ لا صفحات له، وبياناتٌ
    # وصفية لا أقسام لها؛ ومن كتب رقمًا هنا أرسل القارئ إلى صفحةٍ لا تحمل
    # ما نُسب إليها. والقيد في القاعدة يرفضه أيضًا — ويُقال هنا أولًا.
    if ((payload.evidence_page is not None or payload.evidence_section)
            and payload.source_scope != screening.FULL_TEXT):
        raise AtheraError("workspace.page_without_full_text",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                          scope=payload.source_scope)
    if payload.source_file_id is not None and not await screening.file_is_in_project(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            file_id=payload.source_file_id):
        raise NotFound("workspace.file_not_linked")

    cell = (await session.execute(
        select(LiteratureMatrixCell).where(
            LiteratureMatrixCell.tenant_id == principal.tenant_id,
            LiteratureMatrixCell.project_id == project_id,
            LiteratureMatrixCell.source_id == source_id,
            LiteratureMatrixCell.field_key == field_key)
    )).scalar_one_or_none()
    before = None if cell is None else {
        "cell_state": cell.cell_state, "source_scope": cell.source_scope,
        "verification_status": cell.verification_status}
    if cell is None:
        cell = LiteratureMatrixCell(
            tenant_id=principal.tenant_id, project_id=project_id,
            source_id=source_id, field_key=field_key,
            updated_by=principal.user_id)
        session.add(cell)

    cell.value_ar = None if missing else payload.value_ar
    cell.cell_state = payload.cell_state
    cell.source_scope = payload.source_scope
    # **ما يكتبه الباحث بيده منسوبٌ إليه.** ولا استخراج آليّ في هذا المسار:
    # `model` تُكتب من مسارٍ مستقلٍّ لم يُفتح بعد، وتبقى `unverified` حتى
    # يعتمدها إنسان — والقيد في القاعدة يمنع غير ذلك.
    cell.extraction_method = "researcher"
    cell.source_file_id = payload.source_file_id
    cell.evidence_quote = None if missing else payload.evidence_quote
    cell.evidence_locator = None if missing else payload.evidence_locator
    cell.evidence_page = None if missing else payload.evidence_page
    cell.evidence_section = None if missing else payload.evidence_section
    # **ما يكتبه الباحث بيده لا يُنسب إلى ملخّصٍ استخرجه غيره.** فالنسبة
    # تزول مع الكتابة: خليةٌ صحّحها إنسان لم تعد قراءةَ ذلك الملخّص.
    cell.source_abstract_id = None
    # **الكتابة تُبطل المراجعة السابقة.** خليةٌ عُدّلت بعد اعتمادها تبقى
    # «معتمَدة» وهي غير التي اعتُمدت — وهو ختمٌ على نصٍّ لم يُقرأ.
    cell.verification_status = "unverified"
    cell.verified_by, cell.verified_at = None, None
    cell.updated_by = principal.user_id
    await session.flush()

    # **ولا محتوى مستندٍ في السجلّ** (§37): الحال والمدى والعمود تُسجَّل،
    # وقيمةُ الخلية واقتباسها لا يُنسخان إلى سجلّ التدقيق.
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="literature_matrix.cell_recorded",
        object_type="literature_matrix_cell", object_id=cell.id,
        actor_user_id=principal.user_id, state_before=before,
        state_after={"field_key": field_key, "cell_state": cell.cell_state,
                     "source_scope": cell.source_scope,
                     "extraction_method": cell.extraction_method,
                     "has_quote": bool(cell.evidence_quote)},
        reason="a matrix cell records what was read and how far it was read")
    return _cell_view(cell)


@router.post("/projects/{project_id}/matrix/{source_id}/{field_key}/verify",
             response_model=MatrixCellView)
async def verify_matrix_cell(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    field_key: str,
    payload: MatrixCellVerifyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MatrixCellView:
    """احكم على خليةٍ مكتوبة — **والحكم فعلٌ ثانٍ مستقلّ عن الكتابة**.

    فما يُكتب يبقى مرشَّحًا حتى يراجعه إنسان، ولا تُرقَّى قيمةٌ إلى معرفةٍ
    موثقة بأثرٍ جانبي لحفظها. و«لا أعرف» حالةٌ أولى (الترحيل 0016): من راجع
    ولم يستطع الحكم **لم يرفض**.
    """
    await _project(session, principal, project_id)
    if field_key not in MATRIX_FIELDS:
        raise NotFound("workspace.matrix_field_unknown", field=field_key)
    cell = (await session.execute(
        select(LiteratureMatrixCell).where(
            LiteratureMatrixCell.tenant_id == principal.tenant_id,
            LiteratureMatrixCell.project_id == project_id,
            LiteratureMatrixCell.source_id == source_id,
            LiteratureMatrixCell.field_key == field_key)
    )).scalar_one_or_none()
    if cell is None:
        raise NotFound("workspace.matrix_cell_not_found")

    before = cell.verification_status
    cell.verification_status = payload.verification_status
    cell.verified_by = principal.user_id
    cell.verified_at = dt.datetime.now(dt.UTC)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="literature_matrix.cell_reviewed",
        object_type="literature_matrix_cell", object_id=cell.id,
        actor_user_id=principal.user_id,
        state_before={"verification_status": before},
        state_after={"field_key": field_key,
                     "verification_status": cell.verification_status},
        reason="an extracted value becomes knowledge only by a named human review")
    return _cell_view(cell)
