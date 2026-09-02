"""الرسائل وفرص النشر | Thesis-to-papers API (§35.7، §23، §24).

المسار كله محكوم بقاعدتين:
  • الفرصة تُحلَّل بلا حقوق، ولا **تتقدم** بلا اعتمادها (TC-06).
  • تنبيه التجزئة يمنع تحويل فرصتين مستقلتين بلا حسم بشري (TC-05).
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.portfolio import ResearchProject
from ..models.research import ExtractionRun, ResearcherProfile
from ..models.thesis import (
    AuthorshipParty,
    CreditRoleAssignment,
    OpportunityOverlapScore,
    OverlapPolicyRow,
    PublicationOpportunity,
    Thesis,
    ThesisOwner,
    ThesisResult,
    ThesisSection,
    ThesisSupervisor,
)
from ..schemas.thesis import (
    AgingResponse,
    AuthorAddRequest,
    AuthorResponse,
    DimensionResponse,
    GateStatusResponse,
    MineResponse,
    OpportunityResponse,
    OverlapMatrixResponse,
    OverlapPairResponse,
    ParseResponse,
    PublicationMapResponse,
    ThesisCreateRequest,
    ThesisResponse,
)
from ..services import audit
from ..services.parsing import UnsupportedDocument, parse
from ..services.thesis import aging, miner, overlap, rights, vocab

router = APIRouter(prefix="/api/v1", tags=["thesis"])

# رسائل الحواجز بلغتين — المستخدم يستحق أن يعرف ما ينقصه بلغته.
BLOCKER_LABELS = {
    "rights_basis_missing": ("لم يُحدَّد أساس حق استخدام الرسالة.",
                             "The rights basis for using the thesis is not set."),
    "rights_basis_unknown": ("أساس حق الاستخدام غير معروف.", "Unknown rights basis."),
    "owner_consent_missing": ("موافقة صاحب الرسالة غير مسجّلة.",
                              "The thesis owner's consent is not recorded."),
    "no_authors_declared": ("لم يُعلَن أي مؤلف بعد.", "No authors have been declared."),
    "author_consent_incomplete": ("موافقات المؤلفين غير مكتملة.",
                                  "Author consents are incomplete."),
    "author_order_invalid": ("ترتيب المؤلفين غير متسلسل.", "Author order is not sequential."),
    "corresponding_author_missing": ("لم يُحدَّد المؤلف المراسل.",
                                     "No corresponding author is designated."),
}

DEFAULT_THRESHOLDS = {
    "research_question": 0.6, "sample": 0.8, "variable": 0.6, "result": 0.5,
    "table_figure": 0.3, "text": 0.2, "published_output": 0.01,
}


def _pick(locale: str, arabic: str | None, english: str | None) -> str | None:
    """`None` تمرّ كما هي — لا تُستبدل بنصّ يوحي بقيمة.

    سجلٌّ قيد المعالجة بلا عنوان بعد؛ وإرجاع سلسلة فارغة أو شرطة يجعله يبدو
    كرسالة بلا عنوان بدل رسالة لم تُقرأ بعد.
    """
    return (english or arabic) if locale == "en" else arabic


async def _default_policy(session: AsyncSession, tenant_id: uuid.UUID) -> tuple[uuid.UUID, overlap.OverlapPolicy]:
    """§23.7 — العتبات من صف سياسة. تُنشأ سياسة افتراضية مرة واحدة وتبقى قابلة للتعديل."""
    row = (
        await session.execute(select(OverlapPolicyRow).where(OverlapPolicyRow.is_default.is_(True)))
    ).scalar_one_or_none()
    if row is None:
        row = OverlapPolicyRow(
            tenant_id=tenant_id, name_ar="سياسة التداخل الافتراضية",
            name_en="Default overlap policy", thresholds=DEFAULT_THRESHOLDS,
            salami_min_dimensions=3, critical_dimensions=["published_output"], is_default=True,
            source_note_ar="قيم مبدئية قابلة للتعديل وفق سياسة المجلة أو المؤسسة (§23.7).",
        )
        session.add(row)
        await session.flush()
    return row.id, overlap.OverlapPolicy(
        policy_id=str(row.id), thresholds=dict(row.thresholds),
        salami_min_dimensions=row.salami_min_dimensions,
        salami_critical_dimensions=frozenset(row.critical_dimensions or []),
        label_ar=row.name_ar, label_en=row.name_en or row.name_ar,
    )


def _fingerprint(row: PublicationOpportunity) -> overlap.OpportunityFingerprint:
    """الغياب يبقى غيابًا: حقل فارغ يعني «لم يُحسب» لا «صفر»."""
    def _set(value):
        return frozenset(value) if value is not None else None

    return overlap.OpportunityFingerprint(
        opportunity_id=str(row.id),
        research_question=row.research_question_ar,
        sample_ids=_set(row.sample_refs), variable_ids=_set(row.variable_refs),
        result_ids=_set(row.result_refs), table_figure_ids=_set(row.table_figure_refs),
        text=row.draft_text_ar, published_output_ids=_set(row.published_output_refs),
    )


def _opportunity_response(row: PublicationOpportunity, locale: str) -> OpportunityResponse:
    kind_ar, kind_en = vocab.OPPORTUNITY_KINDS[row.opportunity_kind]
    paper_ar, paper_en = vocab.PAPER_KINDS[row.paper_kind]
    outcome_label = None
    if row.readiness_outcome:
        out_ar, out_en = vocab.READINESS_OUTCOMES[row.readiness_outcome]
        outcome_label = _pick(locale, out_ar, out_en)
    return OpportunityResponse(
        id=row.id, thesis_id=row.thesis_id, opportunity_kind=row.opportunity_kind,
        opportunity_kind_label=_pick(locale, kind_ar, kind_en),
        paper_kind=row.paper_kind, paper_kind_label=_pick(locale, paper_ar, paper_en),
        working_title=_pick(locale, row.working_title_ar, row.working_title_en),
        working_title_ar=row.working_title_ar,
        research_question_ar=row.research_question_ar,
        readiness_score=float(row.readiness_score) if row.readiness_score is not None else None,
        readiness_outcome=row.readiness_outcome, readiness_outcome_label=outcome_label,
        salami_alert=row.salami_alert, status=row.status,
        rights_approved=row.rights_approved_at is not None,
        authorship_approved=row.authorship_approved_at is not None,
    )


@router.post("/theses", response_model=ThesisResponse, status_code=status.HTTP_201_CREATED)
async def create_thesis(
    payload: ThesisCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThesisResponse:
    thesis = Thesis(
        tenant_id=principal.tenant_id, title_ar=payload.title_ar, title_en=payload.title_en,
        degree=payload.degree, defended_on=payload.defended_on,
        data_collected_on=payload.data_collected_on, institution_ar=payload.institution_ar,
        file_id=payload.file_id, rights_basis=payload.rights_basis,
    )
    session.add(thesis)
    await session.flush()

    if payload.owner_name:
        session.add(ThesisOwner(tenant_id=principal.tenant_id, thesis_id=thesis.id,
                                display_name=payload.owner_name))
    if payload.supervisor_name:
        session.add(ThesisSupervisor(tenant_id=principal.tenant_id, thesis_id=thesis.id,
                                     display_name=payload.supervisor_name, is_main=True))

    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.created",
        object_type="thesis", object_id=thesis.id, actor_user_id=principal.user_id,
        state_after={"degree": payload.degree, "rights_basis": payload.rights_basis},
        reason="thesis registered; rights basis is a claim, not an approval (§23.2)",
    )
    return ThesisResponse(
        id=thesis.id, title=_pick(principal.locale, thesis.title_ar, thesis.title_en),
        title_ar=thesis.title_ar, degree=thesis.degree, defended_on=thesis.defended_on,
        data_collected_on=thesis.data_collected_on, rights_basis=thesis.rights_basis,
        parsed_at=None, sections_extracted=0, opportunities_found=0,
    )


@router.post("/theses/{thesis_id}/parse", response_model=ParseResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def parse_thesis(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ParseResponse:
    """§23.3 — التفكيك يعيد استخدام مفكِّك Sprint 1 وحاجزه: كل قسم بموضعه."""
    thesis = (await session.execute(select(Thesis).where(
        Thesis.id == thesis_id, Thesis.tenant_id == principal.tenant_id
    ))).scalar_one_or_none()
    if thesis is None:
        raise NotFound("thesis.not_found")
    if thesis.file_id is None:
        raise AtheraError("thesis.no_file", status_code=422)

    record = (await session.execute(select(File).where(
        File.id == thesis.file_id, File.tenant_id == principal.tenant_id
    ))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")

    from ..services.ingestion import _load_bytes  # noqa: PLC0415

    try:
        chunks = parse(await _load_bytes(record), record.content_type, record.original_filename)
    except UnsupportedDocument as exc:
        raise AtheraError("ingestion.unsupported_document", status_code=422,
                          detail=str(exc)) from exc

    # قسم بلا موضع لا يُخزَّن: نفس قاعدة §29.2.
    sections = 0
    for chunk in chunks:
        if not chunk.section_path:
            continue
        key = "results" if "نتائج" in chunk.section_path else "research_problem"
        exists = (
            await session.execute(
                select(ThesisSection).where(
                    ThesisSection.thesis_id == thesis_id, ThesisSection.section_key == key
                )
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(ThesisSection(
            tenant_id=principal.tenant_id, thesis_id=thesis_id, section_key=key,
            content_ar=chunk.text[:4000], locator=chunk.locator, quote=chunk.text[:400],
            verification_status="unverified",
        ))
        sections += 1

    thesis.parsed_at = dt.datetime.now(dt.UTC)
    results = (
        await session.execute(select(ThesisResult).where(ThesisResult.thesis_id == thesis_id))
    ).scalars().all()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.parsed",
        object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
        state_after={"chunks": len(chunks), "sections": sections},
        reason="thesis sections extracted as unverified candidates (§23.3)",
    )
    return ParseResponse(thesis_id=thesis_id, chunks_parsed=len(chunks),
                         sections_extracted=sections, results_extracted=len(results))


@router.post("/theses/{thesis_id}/mine-opportunities", response_model=MineResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def mine_opportunities(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MineResponse:
    """§23.4 + §23.8 — التنقيب يسبقه حساب الأعمار وإعلانها."""
    thesis = (await session.execute(select(Thesis).where(
        Thesis.id == thesis_id, Thesis.tenant_id == principal.tenant_id
    ))).scalar_one_or_none()
    if thesis is None:
        raise NotFound("thesis.not_found")

    sections = (
        await session.execute(select(ThesisSection).where(ThesisSection.thesis_id == thesis_id))
    ).scalars().all()
    results = (
        await session.execute(select(ThesisResult).where(ThesisResult.thesis_id == thesis_id))
    ).scalars().all()

    facts = miner.ThesisFacts(
        thesis_id=str(thesis_id), title=thesis.title_ar,
        questions=tuple(s.content_ar or "" for s in sections if s.section_key == "questions"),
        results=tuple((str(r.id), r.label_ar) for r in results),
        variables=tuple({v for r in results for v in (r.variables or [])}),
        sample_ids=tuple({str(thesis_id)}),
        published_result_ids=tuple(str(r.id) for r in results if r.is_published),
    )
    drafts = miner.mine(facts)

    report = aging.compute(
        as_of=dt.date.today(), data_collected_on=thesis.data_collected_on,
        latest_cited_year=(thesis.defended_on.year if thesis.defended_on else None),
        literature_update_threshold_years=3, data_age_review_threshold_years=5,
    )

    created = 0
    for draft in drafts:
        session.add(PublicationOpportunity(
            tenant_id=principal.tenant_id, thesis_id=thesis_id,
            opportunity_kind=draft.opportunity_kind, paper_kind=draft.paper_kind,
            working_title_ar=draft.working_title_ar,
            research_question_ar=draft.research_question_ar,
            sample_refs=draft.sample_refs, variable_refs=draft.variable_refs,
            result_refs=draft.result_refs, published_output_refs=draft.published_output_refs,
            data_age_years=report.data_age_years,
            literature_age_years=report.literature_age_years,
            status="discovered",
        ))
        created += 1
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.opportunities_mined",
        object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
        state_after={
            "created": created, "kinds": sorted({d.opportunity_kind for d in drafts}),
            "data_age_years": report.data_age_years,
            "literature_age_years": report.literature_age_years,
        },
        reason="opportunities proposed from extracted thesis elements only (§23.4)",
    )
    return MineResponse(
        thesis_id=thesis_id, opportunities_created=created,
        kinds=sorted({d.opportunity_kind for d in drafts}),
        aging=AgingResponse(
            data_age_years=report.data_age_years,
            literature_age_years=report.literature_age_years,
            needs_literature_update=report.needs_literature_update,
            needs_reanalysis_review=report.needs_reanalysis_review,
            note=_pick(principal.locale, report.note_ar, report.note_en),
            note_ar=report.note_ar, note_en=report.note_en,
        ),
    )


async def _overlap_matrix(
    session: AsyncSession, principal: Principal, thesis_id: uuid.UUID
) -> OverlapMatrixResponse:
    rows = (
        await session.execute(
            select(PublicationOpportunity).where(PublicationOpportunity.thesis_id == thesis_id)
        )
    ).scalars().all()
    policy_id, policy = await _default_policy(session, principal.tenant_id)
    results = overlap.matrix([_fingerprint(row) for row in rows], policy)

    by_id = {str(row.id): row for row in rows}
    pairs: list[OverlapPairResponse] = []
    for result in results:
        pairs.append(OverlapPairResponse(
            left_opportunity_id=uuid.UUID(result.left_id),
            right_opportunity_id=uuid.UUID(result.right_id),
            policy=policy.label_ar if principal.locale == "ar" else policy.label_en,
            dimensions=[
                DimensionResponse(
                    dimension=d.dimension,
                    label=_pick(principal.locale, d.label_ar, d.label_en),
                    value=d.value, status=d.status, threshold=d.threshold,
                    exceeds_threshold=d.exceeds_threshold,
                )
                for d in result.dimensions
            ],
            exceeded=result.exceeded, not_computed=result.not_computed,
            salami_alert=result.salami_alert,
        ))
        # التنبيه يُثبَّت على الفرصتين حتى لا يضيع بين استعلامين.
        if result.salami_alert:
            for identifier in (result.left_id, result.right_id):
                by_id[identifier].salami_alert = True

        existing = (
            await session.execute(
                select(OpportunityOverlapScore).where(
                    OpportunityOverlapScore.left_opportunity_id == uuid.UUID(result.left_id),
                    OpportunityOverlapScore.right_opportunity_id == uuid.UUID(result.right_id),
                    OpportunityOverlapScore.policy_id == policy_id,
                )
            )
        ).scalar_one_or_none()
        payload = {
            "dimensions": {d.dimension: d.value for d in result.dimensions},
            "exceeded": result.exceeded, "not_computed": result.not_computed,
            "salami_alert": result.salami_alert,
        }
        if existing is None:
            session.add(OpportunityOverlapScore(
                tenant_id=principal.tenant_id,
                left_opportunity_id=uuid.UUID(result.left_id),
                right_opportunity_id=uuid.UUID(result.right_id),
                policy_id=policy_id, **payload,
            ))
        else:
            for key, value in payload.items():
                setattr(existing, key, value)

    return OverlapMatrixResponse(
        thesis_id=thesis_id, pairs=pairs,
        alerts=sum(1 for pair in pairs if pair.salami_alert),
    )


@router.post("/theses/{thesis_id}/overlap", response_model=OverlapMatrixResponse)
async def compute_overlap(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OverlapMatrixResponse:
    """§23.7 / TC-05 — المصفوفة تُحسب وتُخزَّن بسياستها."""
    matrix_response = await _overlap_matrix(session, principal, thesis_id)
    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.overlap_computed",
        object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
        state_after={"pairs": len(matrix_response.pairs), "alerts": matrix_response.alerts},
        reason="overlap is a review signal; resolution is a human decision (§23.7)",
    )
    return matrix_response


@router.get("/theses/{thesis_id}/publication-map", response_model=PublicationMapResponse)
async def publication_map(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PublicationMapResponse:
    thesis = (await session.execute(select(Thesis).where(
        Thesis.id == thesis_id, Thesis.tenant_id == principal.tenant_id
    ))).scalar_one_or_none()
    if thesis is None:
        raise NotFound("thesis.not_found")

    rows = (
        await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id)
            .order_by(PublicationOpportunity.created_at)
        )
    ).scalars().all()

    summary = {"total": len(rows), "ready_to_submit": 0, "rights_pending": 0, "alerts": 0}
    for row in rows:
        if row.status == "ready_to_submit":
            summary["ready_to_submit"] += 1
        elif row.rights_approved_at is None:
            summary["rights_pending"] += 1
        if row.salami_alert:
            summary["alerts"] += 1

    return PublicationMapResponse(
        thesis_id=thesis_id,
        title=_pick(principal.locale, thesis.title_ar, thesis.title_en),
        opportunities=[_opportunity_response(row, principal.locale) for row in rows],
        overlap=await _overlap_matrix(session, principal, thesis_id),
        gate_summary=summary,
    )


@router.post("/opportunities/{opportunity_id}/authors", response_model=AuthorResponse,
             status_code=status.HTTP_201_CREATED)
async def add_author(
    opportunity_id: uuid.UUID,
    payload: AuthorAddRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> AuthorResponse:
    agreement = await rights.add_author(
        session, tenant_id=principal.tenant_id, opportunity_id=opportunity_id,
        party_kind=payload.party_kind, display_name=payload.display_name,
        author_position=payload.author_position, actor_user_id=principal.user_id,
        is_corresponding=payload.is_corresponding, credit_roles=payload.credit_roles,
    )
    return AuthorResponse(
        agreement_id=agreement.id, party_id=agreement.party_id,
        display_name=payload.display_name, author_position=agreement.author_position,
        is_corresponding=agreement.is_corresponding, consent_status=agreement.consent_status,
        credit_roles=payload.credit_roles,
    )


@router.post("/opportunities/{opportunity_id}/authors/{agreement_id}/consent",
             response_model=AuthorResponse)
async def record_consent(
    opportunity_id: uuid.UUID,
    agreement_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> AuthorResponse:
    agreement = await rights.record_consent(
        session, tenant_id=principal.tenant_id, agreement_id=agreement_id,
        actor_user_id=principal.user_id,
    )
    party = (
        await session.execute(select(AuthorshipParty).where(
            AuthorshipParty.id == agreement.party_id,
            AuthorshipParty.tenant_id == principal.tenant_id))
    ).scalar_one()
    roles = (
        await session.execute(
            select(CreditRoleAssignment.credit_role)
            .where(CreditRoleAssignment.agreement_id == agreement.id)
        )
    ).scalars().all()
    return AuthorResponse(
        agreement_id=agreement.id, party_id=party.id, display_name=party.display_name,
        author_position=agreement.author_position, is_corresponding=agreement.is_corresponding,
        consent_status=agreement.consent_status, credit_roles=list(roles),
    )


@router.get("/opportunities/{opportunity_id}/gate", response_model=GateStatusResponse)
async def gate_status(
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GateStatusResponse:
    state = await rights.gate_status(
        session, tenant_id=principal.tenant_id, opportunity_id=opportunity_id
    )
    return GateStatusResponse(
        opportunity_id=state.opportunity_id, rights_basis=state.rights_basis,
        rights_approved=state.rights_approved,
        owner_consent_recorded=state.owner_consent_recorded,
        authors_total=state.authors_total, authors_consented=state.authors_consented,
        authorship_approved=state.authorship_approved, blockers=state.blockers,
        blocker_labels=[
            _pick(principal.locale, *BLOCKER_LABELS.get(key, (key, key)))
            for key in state.blockers
        ],
        can_be_ready_to_submit=state.can_be_ready_to_submit,
    )


@router.post("/opportunities/{opportunity_id}/authorship-approval",
             response_model=OpportunityResponse)
async def approve_authorship(
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityResponse:
    """§23.9 / TC-06 — بوابة GT1: الباب الوحيد إلى Ready to Submit."""
    opportunity = await rights.approve_gate(
        session, tenant_id=principal.tenant_id, opportunity_id=opportunity_id,
        actor_user_id=principal.user_id,
    )
    return _opportunity_response(opportunity, principal.locale)


@router.post("/opportunities/{opportunity_id}/convert-to-project",
             response_model=OpportunityResponse)
async def convert_to_project(
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityResponse:
    """التحويل يشترط اجتياز GT1 وحسم أي تنبيه تجزئة (TC-05 + TC-06)."""
    opportunity = (
        await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_id,
                PublicationOpportunity.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if opportunity is None:
        raise NotFound("thesis.opportunity_not_found")
    if opportunity.status != "ready_to_submit":
        raise AtheraError("thesis.not_ready_to_convert", status_code=422,
                          status_value=opportunity.status)

    unresolved = (
        await session.execute(
            select(OpportunityOverlapScore).where(
                OpportunityOverlapScore.salami_alert.is_(True),
                OpportunityOverlapScore.resolution.is_(None),
                OpportunityOverlapScore.left_opportunity_id == opportunity_id,
            )
        )
    ).scalars().all()
    if unresolved:
        raise AtheraError("thesis.overlap_unresolved", status_code=422,
                          pairs=str(len(unresolved)))

    profile = (
        await session.execute(
            select(ResearcherProfile).where(ResearcherProfile.user_id == principal.user_id)
        )
    ).scalar_one_or_none()

    project = ResearchProject(
        tenant_id=principal.tenant_id, profile_id=profile.id if profile else None,
        working_title_ar=opportunity.working_title_ar,
        working_title_en=opportunity.working_title_en, status="planned",
        current_gate="G1", is_thesis_derived=True,
    )
    session.add(project)
    await session.flush()

    opportunity.converted_project_id = project.id
    opportunity.status = "converted"

    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.opportunity_converted",
        object_type="publication_opportunity", object_id=opportunity_id,
        actor_user_id=principal.user_id,
        state_after={"project_id": str(project.id), "is_thesis_derived": True},
        reason="converted after GT1 approval and overlap resolution (§23.9, TC-05/06)",
    )
    return _opportunity_response(opportunity, principal.locale)


@router.get("/theses", response_model=list[ThesisResponse])
async def list_theses(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ThesisResponse]:
    rows = (
        await session.execute(select(Thesis).order_by(Thesis.created_at.desc()))
    ).scalars().all()

    # حالة أحدث تشغيلة قراءة لكل ملف — تُقرأ دفعةً واحدة لا استعلامًا لكل صفّ.
    file_ids = [t.file_id for t in rows if t.file_id is not None]
    processing: dict[uuid.UUID, str] = {}
    if file_ids:
        runs = (
            await session.execute(
                select(ExtractionRun).where(ExtractionRun.file_id.in_(file_ids))
                .order_by(ExtractionRun.started_at.asc())
            )
        ).scalars().all()
        for run in runs:
            processing[run.file_id] = run.status  # الأحدث يغلب لأن الترتيب تصاعدي

    out: list[ThesisResponse] = []
    for thesis in rows:
        sections = (
            await session.execute(
                select(ThesisSection).where(ThesisSection.thesis_id == thesis.id)
            )
        ).scalars().all()
        opportunities = (
            await session.execute(
                select(PublicationOpportunity)
                .where(PublicationOpportunity.thesis_id == thesis.id)
            )
        ).scalars().all()
        out.append(ThesisResponse(
            id=thesis.id, title=_pick(principal.locale, thesis.title_ar, thesis.title_en),
            title_ar=thesis.title_ar, degree=thesis.degree, defended_on=thesis.defended_on,
            data_collected_on=thesis.data_collected_on, rights_basis=thesis.rights_basis,
            parsed_at=thesis.parsed_at, sections_extracted=len(sections),
            opportunities_found=len(opportunities),
            processing_status=processing.get(thesis.file_id) if thesis.file_id else None,
        ))
    return out
