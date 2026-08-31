"""محفظة الأبحاث | Research portfolio API (§12)."""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import NotFound
from ..models.portfolio import ResearchProject
from ..models.research import ResearcherProfile
from ..schemas.portfolio import ProjectCreateRequest, ProjectResponse
from ..services import audit

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])

# §12.3 — الخطة المرجعية **اقتراح لا قيد**: تُعرض كإرشاد ولا يفرضها أي تحقق.
REFERENCE_PLAN = {
    "projects": 8,
    "sole_authored": 6,
    "primary_target_indexes": ["SSCI", "AHCI", "SCIE"],
    "backup_wos_paper": 1,
    "planned_units": 7,
    "is_binding": False,
    "note_ar": "خطة مقترحة قابلة لإعادة الترتيب، وليست قاعدة ثابتة (§12.3).",
    "note_en": "A suggested, re-orderable plan — not a fixed rule (§12.3).",
}


def _to_response(row: ResearchProject, locale: str) -> ProjectResponse:
    title = (row.working_title_en or row.working_title_ar) if locale == "en" else row.working_title_ar
    return ProjectResponse(
        id=row.id, working_title=title, working_title_ar=row.working_title_ar,
        working_title_en=row.working_title_en, program_id=row.program_id,
        study_type=row.study_type, status=row.status,
        expected_units=float(row.expected_units) if row.expected_units is not None else None,
        target_journal_name=row.target_journal_name, target_index_tier=row.target_index_tier,
        risks=row.risks, target_date=row.target_date, current_gate=row.current_gate,
        is_thesis_derived=row.is_thesis_derived,
    )


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectResponse]:
    rows = (
        await session.execute(select(ResearchProject).order_by(ResearchProject.created_at.desc()))
    ).scalars().all()
    return [_to_response(row, principal.locale) for row in rows]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    profile = (
        await session.execute(
            select(ResearcherProfile).where(ResearcherProfile.user_id == principal.user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise NotFound("portfolio.profile_required")

    project = ResearchProject(
        tenant_id=principal.tenant_id, profile_id=profile.id, program_id=payload.program_id,
        working_title_ar=payload.working_title_ar, working_title_en=payload.working_title_en,
        study_type=payload.study_type, status="planned", expected_units=payload.expected_units,
        target_journal_name=payload.target_journal_name, target_index_tier=payload.target_index_tier,
        intended_author_count=payload.intended_author_count,
        intended_author_position=payload.intended_author_position,
        risks=payload.risks, target_date=payload.target_date,
        current_gate="G1", is_thesis_derived=payload.is_thesis_derived,
    )
    session.add(project)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="portfolio.project_created",
        object_type="research_project", object_id=project.id, actor_user_id=principal.user_id,
        state_after={"title": payload.working_title_ar[:120], "gate": "G1"},
        reason="project starts at G1 and needs approval before it advances (§9)",
    )
    return _to_response(project, principal.locale)


@router.get("/reference-plan", response_model=dict)
async def reference_plan(principal: Principal = Depends(get_principal)) -> dict:
    """§12.3 — تُعرض للإرشاد. `is_binding=false` جزء من الإجابة لا حاشية."""
    return REFERENCE_PLAN
