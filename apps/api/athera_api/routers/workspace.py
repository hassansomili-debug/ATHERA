"""مساحة عمل البحث | Project workspace routes (PUBRIVA).

**البحث هو الشيء المركزي، لا الوحدة.** فما كان مبعثرًا في وحداتٍ متجاورة —
ملفات هنا ومراجع هناك ومخطوطة ثالثة — يُجمع تحت البحث الذي يخدمه.

ولا يُنشأ نظام مشاريع موازٍ: `research_projects` هو هو، وهذه الطرق تعرضه
بعلاقاته. وجدولا الربط الجديدان يصفان **العلاقة** لا الشيء.
"""
from __future__ import annotations

import datetime as dt
import uuid

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
from ..schemas.workspace import (
    BrainEntryView,
    ImpactView,
    LinkRequest,
    NextAction,
    ProjectCreateRequest,
    ProjectFileView,
    ProjectOverview,
    ProjectRenameRequest,
    ProjectSourceView,
    ProjectSummary,
    SourceUseRequest,
)
from ..services import audit, workspace

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
    return [ProjectSourceView(
        source_id=source.id, title=source.title, doi=source.doi,
        publication_year=source.publication_year, use_state=link.use_state,
        added_at=link.created_at, decided_at=link.decided_at)
        for link, source in rows]


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
    return ProjectSourceView(
        source_id=source.id, title=source.title, doi=source.doi,
        publication_year=source.publication_year, use_state=link.use_state,
        added_at=link.created_at, decided_at=link.decided_at)


@router.patch("/projects/{project_id}/sources/{source_id}",
              response_model=ProjectSourceView)
async def set_source_use(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SourceUseRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectSourceView:
    """قرّر حال المرجع في هذا البحث — **والقرار يُنسب إلى صاحبه**."""
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
    if payload.use_state == "excluded":
        impact = await workspace.source_impact(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            source_id=source_id)
        if impact.breaks_approved_work:
            raise AtheraError(
                "workspace.source_still_cited",
                status_code=status.HTTP_409_CONFLICT,
                summary=impact.summary_ar())

    link.use_state = payload.use_state
    link.reason_ar = payload.reason_ar
    # قرارٌ صريح يُنسب إلى قائله؛ و`saved_only` عودةٌ إلى الحياد فلا فاعل له.
    if payload.use_state == "saved_only":
        link.decided_by, link.decided_at = None, None
    else:
        link.decided_by = principal.user_id
        link.decided_at = dt.datetime.now(dt.UTC)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="workspace.source_use_set",
        object_type="project_source", object_id=link.id,
        actor_user_id=principal.user_id, state_before={"use_state": before},
        state_after={"use_state": payload.use_state},
        reason="including a source as evidence is a researcher decision, attributed")
    return ProjectSourceView(
        source_id=source.id, title=source.title, doi=source.doi,
        publication_year=source.publication_year, use_state=link.use_state,
        added_at=link.created_at, decided_at=link.decided_at)
