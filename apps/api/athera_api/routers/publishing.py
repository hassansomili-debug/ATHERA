"""المخطوطة والمجلات والمراجعة | Publishing API (§19، §20، §21، §22).

ثلاث قواعد يفرضها هذا الموجّه:
  • G9 لا تُفتح بمخطوطة تحمل ادعاءً بلا سند أو رقمًا بلا تشغيلة (§19.2).
  • G10 لا تُعتمد بفهرسة لم يُعَد التحقق منها (§20.3، TC-04).
  • تطبيق رقعة مراجعة **ينشئ نسخة جديدة** ولا يعدّل المعتمدة (§21).
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.literature import Journal, JournalIndexingRecord
from ..models.publishing import (
    JournalMatchRow,
    JournalPolicyCheck,
    JournalProfile,
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
    ReviewerReportRow,
    ReviewPatch,
    ReviewRound,
    SubmissionPackage,
)
from ..schemas.publishing import (
    CriterionResponse,
    IndexingVerifyRequest,
    IndexingVerifyResponse,
    InternalReviewRequest,
    JournalMatchRequest,
    JournalMatchResponse,
    ManuscriptCreateRequest,
    ManuscriptReadinessResponse,
    ManuscriptResponse,
    PackageItemResponse,
    PatchApplyRequest,
    PatchResponse,
    ReadinessIssueResponse,
    ReviewRoundResponse,
    SectionUpsertRequest,
    SubmissionPackageResponse,
)
from ..services import audit
from ..services.publishing import journals, manuscript, review, vocab

router = APIRouter(prefix="/api/v1", tags=["publishing"])

# §20.2 — سياسة الطبقات الافتراضية. أسماء الفهارس بيانات لا كود.
DEFAULT_TIER_POLICY = journals.TierPolicy(
    policy_id="default",
    tier_a_indexes=frozenset({"SSCI", "AHCI", "SCIE"}),
    tier_b_indexes=frozenset({"ESCI"}),
    tier_c_indexes=frozenset({"SCOPUS"}),
    verification_max_age_days=90,
)


def _pick(locale: str, arabic: str, english: str | None) -> str:
    return (english or arabic) if locale == "en" else arabic


async def _current_version(session: AsyncSession, manuscript_id: uuid.UUID) -> ManuscriptVersion | None:
    return (
        await session.execute(
            select(ManuscriptVersion)
            .where(ManuscriptVersion.manuscript_id == manuscript_id)
            .order_by(ManuscriptVersion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


@router.post("/manuscripts", response_model=ManuscriptResponse,
             status_code=status.HTTP_201_CREATED)
async def create_manuscript(
    payload: ManuscriptCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ManuscriptResponse:
    record = Manuscript(
        tenant_id=principal.tenant_id, project_id=payload.project_id,
        title_ar=payload.title_ar, title_en=payload.title_en, language=payload.language,
        status="draft",
    )
    session.add(record)
    await session.flush()

    version = ManuscriptVersion(
        tenant_id=principal.tenant_id, manuscript_id=record.id, version_label="v1",
        created_by=principal.user_id, change_reason_ar="النسخة الأولى",
    )
    session.add(version)
    await session.flush()
    record.current_version_id = version.id

    await audit.record(
        session, tenant_id=principal.tenant_id, action="manuscript.created",
        object_type="manuscript", object_id=record.id, actor_user_id=principal.user_id,
        state_after={"language": payload.language, "version": "v1"},
    )
    return ManuscriptResponse(
        id=record.id, project_id=record.project_id,
        title=_pick(principal.locale, record.title_ar, record.title_en),
        title_ar=record.title_ar, language=record.language, status=record.status,
        current_version_label=version.version_label, g9_approved_at=None,
    )


@router.post("/manuscripts/{manuscript_id}/sections", status_code=status.HTTP_201_CREATED)
async def upsert_section(
    manuscript_id: uuid.UUID,
    payload: SectionUpsertRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.section_key not in vocab.MANUSCRIPT_SECTIONS:
        raise AtheraError("publishing.unknown_section", status_code=422,
                          section=payload.section_key)
    version = await _current_version(session, manuscript_id)
    if version is None:
        raise NotFound("publishing.manuscript_not_found")

    existing = (
        await session.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.version_id == version.id,
                ManuscriptSection.section_key == payload.section_key,
            )
        )
    ).scalar_one_or_none()

    section = existing or ManuscriptSection(
        tenant_id=principal.tenant_id, version_id=version.id, section_key=payload.section_key
    )
    section.text_ar = payload.text_ar
    section.text_en = payload.text_en
    section.claim_ids = payload.claim_ids
    section.analysis_run_ids = payload.analysis_run_ids
    if existing is None:
        session.add(section)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="manuscript.section_saved",
        object_type="manuscript_section", object_id=section.id, actor_user_id=principal.user_id,
        state_after={"section": payload.section_key, "claims": len(payload.claim_ids),
                     "runs": len(payload.analysis_run_ids)},
    )
    return {"id": str(section.id), "section_key": section.section_key}


async def _readiness(
    session: AsyncSession, manuscript_id: uuid.UUID, supported: dict[str, set[str]] | None = None
) -> manuscript.ManuscriptReadiness:
    version = await _current_version(session, manuscript_id)
    if version is None:
        raise NotFound("publishing.manuscript_not_found")
    rows = (
        await session.execute(
            select(ManuscriptSection).where(ManuscriptSection.version_id == version.id)
        )
    ).scalars().all()
    supported = supported or {}
    return manuscript.evaluate([
        manuscript.SectionState(
            section_key=row.section_key, text=row.text_ar or "",
            claim_ids=frozenset(row.claim_ids or []),
            supported_claim_ids=frozenset(supported.get(row.section_key, set())),
            analysis_run_ids=frozenset(row.analysis_run_ids or []),
        )
        for row in rows
    ])


@router.get("/manuscripts", response_model=list[ManuscriptResponse])
async def list_manuscripts(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ManuscriptResponse]:
    rows = (
        await session.execute(select(Manuscript).order_by(Manuscript.created_at.desc()))
    ).scalars().all()
    return [
        ManuscriptResponse(
            id=r.id, project_id=r.project_id, title=r.title_en or r.title_ar,
            title_ar=r.title_ar, language=r.language, status=r.status,
            current_version_label=r.current_version_label, g9_approved_at=r.g9_approved_at,
        )
        for r in rows
    ]


@router.get("/manuscripts/{manuscript_id}/readiness",
            response_model=ManuscriptReadinessResponse)
async def readiness(
    manuscript_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ManuscriptReadinessResponse:
    """§19.2 — يسمّي ما ينقص بالاسم لا يرفض رفضًا مبهمًا."""
    result = await _readiness(session, manuscript_id)
    return ManuscriptReadinessResponse(
        manuscript_id=manuscript_id, can_pass_g9=result.can_pass_g9,
        issues=[
            ReadinessIssueResponse(
                section_key=i.section_key, issue_key=i.issue_key,
                detail=_pick(principal.locale, i.detail_ar, i.detail_en),
                detail_ar=i.detail_ar, detail_en=i.detail_en, excerpt=i.excerpt,
            )
            for i in result.issues
        ],
        missing_sections=result.missing_sections, sections_checked=result.sections_checked,
        note=_pick(principal.locale, result.note_ar, result.note_en),
        note_ar=result.note_ar, note_en=result.note_en,
    )


@router.post("/manuscripts/{manuscript_id}/approve-g9", response_model=ManuscriptResponse)
async def approve_g9(
    manuscript_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ManuscriptResponse:
    record = (
        await session.execute(select(Manuscript).where(Manuscript.id == manuscript_id))
    ).scalar_one_or_none()
    if record is None:
        raise NotFound("publishing.manuscript_not_found")

    result = await _readiness(session, manuscript_id)
    snapshot = {
        "can_pass_g9": result.can_pass_g9,
        "issues": [i.issue_key for i in result.issues],
        "missing_sections": result.missing_sections,
    }
    if not result.can_pass_g9:
        record.g9_readiness_snapshot = snapshot
        await audit.record(
            session, tenant_id=principal.tenant_id, action="manuscript.g9_refused",
            object_type="manuscript", object_id=manuscript_id, actor_user_id=principal.user_id,
            state_after=snapshot,
            reason="unsupported claims or results without an analysis run (§19.2)",
        )
        raise AtheraError("publishing.g9_blocked", status_code=422,
                          issues=str(len(result.issues)))

    record.g9_approved_by = principal.user_id
    record.g9_approved_at = dt.datetime.now(dt.UTC)
    record.g9_readiness_snapshot = snapshot
    record.status = "ready_for_journal"

    await audit.record(
        session, tenant_id=principal.tenant_id, action="manuscript.g9_approved",
        object_type="manuscript", object_id=manuscript_id, actor_user_id=principal.user_id,
        state_after=snapshot, reason="researcher approved the manuscript at gate G9",
    )
    version = await _current_version(session, manuscript_id)
    return ManuscriptResponse(
        id=record.id, project_id=record.project_id,
        title=_pick(principal.locale, record.title_ar, record.title_en),
        title_ar=record.title_ar, language=record.language, status=record.status,
        current_version_label=version.version_label if version else None,
        g9_approved_at=record.g9_approved_at,
    )


async def _journal_facts(session: AsyncSession, journal: Journal) -> journals.JournalFacts:
    records = (
        await session.execute(
            select(JournalIndexingRecord).where(JournalIndexingRecord.journal_id == journal.id)
        )
    ).scalars().all()
    profile = (
        await session.execute(
            select(JournalProfile).where(JournalProfile.journal_id == journal.id)
        )
    ).scalar_one_or_none()
    return journals.JournalFacts(
        journal_id=str(journal.id), name=journal.name,
        indexing=tuple(
            journals.IndexingRecord(index_name=r.index_name, status=r.status,
                                    last_verified_at=r.last_verified_at)
            for r in records
        ),
        publisher=journal.publisher, is_peer_reviewed=True,
        is_discontinued=bool(profile and profile.is_discontinued),
        is_suspicious=bool(profile and profile.is_suspicious),
        scope_keywords=frozenset((profile.scope_keywords if profile else None) or []),
        recent_article_keywords=frozenset(
            (profile.recent_article_keywords if profile else None) or []
        ),
        accepted_methods=frozenset((profile.accepted_methods if profile else None) or []),
        apc_usd=float(profile.apc_usd) if profile and profile.apc_usd is not None else None,
        oa_model=profile.oa_model if profile else None,
        median_review_days=profile.median_review_days if profile else None,
    )


@router.post("/journals/match", response_model=list[JournalMatchResponse])
async def match_journals(
    payload: JournalMatchRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[JournalMatchResponse]:
    now = dt.datetime.now(dt.UTC)
    profile = journals.ManuscriptProfile(
        keywords=frozenset(payload.keywords), method_keys=frozenset(payload.method_keys),
        target_journal_tier=payload.target_journal_tier, max_apc_usd=payload.max_apc_usd,
        requires_open_access=payload.requires_open_access,
    )
    candidates = (await session.execute(select(Journal).limit(50))).scalars().all()

    responses: list[JournalMatchResponse] = []
    for journal in candidates:
        facts = await _journal_facts(session, journal)
        result = journals.match(profile, facts, DEFAULT_TIER_POLICY, as_of=now)

        existing = (
            await session.execute(
                select(JournalMatchRow).where(
                    JournalMatchRow.manuscript_id == payload.manuscript_id,
                    JournalMatchRow.journal_id == journal.id,
                )
            )
        ).scalar_one_or_none()
        row = existing or JournalMatchRow(
            tenant_id=principal.tenant_id, manuscript_id=payload.manuscript_id,
            journal_id=journal.id, fit_score=0, trust_tier="X",
        )
        row.fit_score = result.fit_score
        row.trust_tier = result.tier.tier
        row.criteria = {c.key: c.points for c in result.criteria}
        row.blockers = result.blockers
        row.uncomputed = result.uncomputed
        if existing is None:
            session.add(row)

        responses.append(JournalMatchResponse(
            journal_id=journal.id, journal_name=journal.name, trust_tier=result.tier.tier,
            trust_tier_label=_pick(principal.locale, result.tier.label_ar, result.tier.label_en),
            meets_strict_wos=result.tier.meets_strict_wos, fit_score=result.fit_score,
            criteria=[
                CriterionResponse(
                    key=c.key, weight=c.weight, ratio=c.ratio, points=c.points,
                    label=_pick(principal.locale, c.label_ar, c.label_en),
                    detail=_pick(principal.locale, c.detail_ar, c.detail_en),
                )
                for c in result.criteria
            ],
            blockers=result.blockers, uncomputed=result.uncomputed,
            stale_indexes=result.tier.stale_indexes,
            note=_pick(principal.locale, result.note_ar, result.note_en),
            note_ar=result.note_ar, note_en=result.note_en,
        ))

    await audit.record(
        session, tenant_id=principal.tenant_id, action="publishing.journals_matched",
        object_type="manuscript", object_id=payload.manuscript_id,
        actor_user_id=principal.user_id,
        state_after={"candidates": len(candidates)},
        reason="fit scoring only; acceptance is never estimated (§20.4)",
    )
    responses.sort(key=lambda r: r.fit_score, reverse=True)
    return responses


@router.post("/journals/{journal_id}/verify-indexing", response_model=IndexingVerifyResponse)
async def verify_indexing(
    journal_id: uuid.UUID,
    payload: IndexingVerifyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> IndexingVerifyResponse:
    """§20.3 / TC-04 — إعادة التحقق عند النقاط الأربع."""
    now = dt.datetime.now(dt.UTC)
    records = (
        await session.execute(
            select(JournalIndexingRecord).where(JournalIndexingRecord.journal_id == journal_id)
        )
    ).scalars().all()
    latest = max((r.last_verified_at for r in records), default=None)
    needs = journals.requires_reverification(
        latest, DEFAULT_TIER_POLICY, at_point=payload.verification_point, as_of=now
    )
    outcome = "needs_reverification" if needs else "confirmed"

    session.add(JournalPolicyCheck(
        tenant_id=principal.tenant_id, journal_id=journal_id,
        verification_point=payload.verification_point, checked_at=now,
        checked_by=principal.user_id,
        indexing_snapshot={r.index_name: r.status for r in records},
        outcome=outcome,
    ))
    await audit.record(
        session, tenant_id=principal.tenant_id, action="publishing.indexing_checked",
        object_type="journal", object_id=journal_id, actor_user_id=principal.user_id,
        state_after={"point": payload.verification_point, "outcome": outcome},
    )
    return IndexingVerifyResponse(
        journal_id=journal_id, verification_point=payload.verification_point,
        requires_reverification=needs, outcome=outcome, checked_at=now,
        note_ar=("حالة الفهرسة تحتاج إعادة تحقق قبل اعتماد المجلة."
                 if needs else "حالة الفهرسة متحقق منها حديثًا."),
        note_en=("Indexing needs re-verification before the journal is approved."
                 if needs else "Indexing was verified recently."),
    )


@router.post("/manuscripts/{manuscript_id}/internal-review", response_model=ReviewRoundResponse,
             status_code=status.HTTP_201_CREATED)
async def internal_review(
    manuscript_id: uuid.UUID,
    payload: InternalReviewRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ReviewRoundResponse:
    """§21 — المجلس يقترح رقعًا؛ لا سطر هنا يكتب في قسم معتمد."""
    reports = [
        review.ReviewerReport(
            reviewer_role=r.reviewer_role, strengths=list(r.strengths),
            major_concerns=[
                review.ReviewNote(severity=n.severity, section_key=n.section_key,
                                  text_ar=n.text_ar, text_en=n.text_en)
                for n in r.major_concerns
            ],
            minor_concerns=[
                review.ReviewNote(severity=n.severity, section_key=n.section_key,
                                  text_ar=n.text_ar, text_en=n.text_en)
                for n in r.minor_concerns
            ],
            potential_rejection_reasons=list(r.potential_rejection_reasons),
            required_changes=[
                review.ProposedPatch(section_key=p.section_key, rationale_ar=p.rationale_ar,
                                     rationale_en=p.rationale_en,
                                     suggested_text_ar=p.suggested_text_ar)
                for p in r.required_changes
            ],
        )
        for r in payload.reports
    ]
    council = review.assemble(reports)

    previous = (
        await session.execute(
            select(ReviewRound).where(ReviewRound.manuscript_id == manuscript_id)
        )
    ).scalars().all()
    round_row = ReviewRound(
        tenant_id=principal.tenant_id, manuscript_id=manuscript_id,
        version_id=payload.version_id, round_number=len(previous) + 1,
        readiness_status=council.readiness_status, major_count=council.major_count,
        minor_count=council.minor_count, reviewers_missing=council.reviewers_missing,
    )
    session.add(round_row)
    await session.flush()

    patch_rows: list[ReviewPatch] = []
    for report in reports:
        report_row = ReviewerReportRow(
            tenant_id=principal.tenant_id, round_id=round_row.id,
            reviewer_role=report.reviewer_role, strengths=report.strengths,
            major_concerns=[{"section": n.section_key, "text_ar": n.text_ar}
                            for n in report.major_concerns],
            minor_concerns=[{"section": n.section_key, "text_ar": n.text_ar}
                            for n in report.minor_concerns],
            rejection_reasons=report.potential_rejection_reasons,
        )
        session.add(report_row)
        await session.flush()
        for patch in report.required_changes:
            row = ReviewPatch(
                tenant_id=principal.tenant_id, report_id=report_row.id,
                section_key=patch.section_key, rationale_ar=patch.rationale_ar,
                rationale_en=patch.rationale_en, suggested_text_ar=patch.suggested_text_ar,
                status="proposed",
            )
            session.add(row)
            patch_rows.append(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="publishing.internal_review_completed",
        object_type="manuscript", object_id=manuscript_id, actor_user_id=principal.user_id,
        state_after={"status": council.readiness_status, "patches": len(patch_rows),
                     "reviewers_missing": council.reviewers_missing},
        reason="council proposed patches; none applied without human approval (§21)",
    )
    return ReviewRoundResponse(
        id=round_row.id, round_number=round_row.round_number,
        readiness_status=council.readiness_status,
        readiness_label=_pick(principal.locale, council.status_label_ar,
                              council.status_label_en),
        major_count=council.major_count, minor_count=council.minor_count,
        reviewers_missing=council.reviewers_missing,
        patches=[
            PatchResponse(id=r.id, section_key=r.section_key, rationale_ar=r.rationale_ar,
                          suggested_text_ar=r.suggested_text_ar, status=r.status)
            for r in patch_rows
        ],
        note_ar=council.note_ar, note_en=council.note_en,
    )


@router.post("/review-patches/{patch_id}/apply", response_model=PatchResponse)
async def apply_patch(
    patch_id: uuid.UUID,
    payload: PatchApplyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PatchResponse:
    """§21 — التطبيق **ينشئ نسخة جديدة** ولا يمس النسخة المعتمدة."""
    patch = (
        await session.execute(select(ReviewPatch).where(ReviewPatch.id == patch_id))
    ).scalar_one_or_none()
    if patch is None:
        raise NotFound("publishing.patch_not_found")
    if patch.status != "proposed":
        raise AtheraError("publishing.patch_already_decided", status_code=422,
                          status_value=patch.status)

    report = (
        await session.execute(
            select(ReviewerReportRow).where(ReviewerReportRow.id == patch.report_id)
        )
    ).scalar_one()
    round_row = (
        await session.execute(select(ReviewRound).where(ReviewRound.id == report.round_id))
    ).scalar_one()

    old_version = (
        await session.execute(
            select(ManuscriptVersion).where(ManuscriptVersion.id == round_row.version_id)
        )
    ).scalar_one()
    new_version = ManuscriptVersion(
        tenant_id=principal.tenant_id, manuscript_id=round_row.manuscript_id,
        version_label=payload.new_version_label, created_by=principal.user_id,
        change_reason_ar=payload.change_reason_ar, supersedes_id=old_version.id,
    )
    session.add(new_version)
    await session.flush()

    # تُنسخ الأقسام إلى النسخة الجديدة، ويُطبَّق النص المقترح على قسمه وحده.
    sections = (
        await session.execute(
            select(ManuscriptSection).where(ManuscriptSection.version_id == old_version.id)
        )
    ).scalars().all()
    for section in sections:
        session.add(ManuscriptSection(
            tenant_id=principal.tenant_id, version_id=new_version.id,
            section_key=section.section_key,
            text_ar=(patch.suggested_text_ar
                     if section.section_key == patch.section_key and patch.suggested_text_ar
                     else section.text_ar),
            text_en=section.text_en, claim_ids=section.claim_ids,
            analysis_run_ids=section.analysis_run_ids, ordinal=section.ordinal,
        ))

    patch.status = "applied"
    patch.decided_by = principal.user_id
    patch.decided_at = dt.datetime.now(dt.UTC)
    patch.applied_in_version_id = new_version.id

    manuscript_row = (
        await session.execute(
            select(Manuscript).where(Manuscript.id == round_row.manuscript_id)
        )
    ).scalar_one()
    manuscript_row.current_version_id = new_version.id
    # النسخة الجديدة تُلغي اعتماد G9 السابق: الاعتماد كان على نص آخر.
    manuscript_row.g9_approved_at = None
    manuscript_row.g9_approved_by = None
    manuscript_row.status = "draft"

    await audit.record(
        session, tenant_id=principal.tenant_id, action="publishing.patch_applied",
        object_type="review_patch", object_id=patch.id, actor_user_id=principal.user_id,
        state_before={"status": "proposed", "version": old_version.version_label},
        state_after={"status": "applied", "version": new_version.version_label},
        reason=payload.change_reason_ar,
    )
    return PatchResponse(id=patch.id, section_key=patch.section_key,
                         rationale_ar=patch.rationale_ar,
                         suggested_text_ar=patch.suggested_text_ar, status=patch.status)


@router.get("/manuscripts/{manuscript_id}/submission-package",
            response_model=SubmissionPackageResponse)
async def submission_package(
    manuscript_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SubmissionPackageResponse:
    """§22.1 — يبني الحزمة مما هو موجود فعلًا ويسمّي الناقص."""
    version = await _current_version(session, manuscript_id)
    if version is None:
        raise NotFound("publishing.manuscript_not_found")
    sections = {
        row.section_key
        for row in (
            await session.execute(
                select(ManuscriptSection).where(ManuscriptSection.version_id == version.id)
            )
        ).scalars().all()
        if (row.text_ar or "").strip()
    }

    present: set[str] = set()
    if sections:
        present.add("main_manuscript")
        present.add("blinded_manuscript")
    if "title" in sections:
        present.add("title_page")
    if "declarations" in sections:
        present |= {"funding", "conflict_of_interest", "ai_disclosure",
                    "data_availability_statement", "credit_contributions"}
    if "results" in sections:
        present.add("figures_tables")

    missing_required, missing_optional = review.package_gaps(
        present, optional_items=vocab.OPTIONAL_PACKAGE_ITEMS
    )
    now = dt.datetime.now(dt.UTC)
    session.add(SubmissionPackage(
        tenant_id=principal.tenant_id, manuscript_id=manuscript_id,
        items_present=sorted(present), missing_required=missing_required,
        missing_optional=missing_optional, assembled_at=now,
        is_complete=not missing_required,
    ))
    await audit.record(
        session, tenant_id=principal.tenant_id, action="publishing.package_assembled",
        object_type="manuscript", object_id=manuscript_id, actor_user_id=principal.user_id,
        state_after={"present": len(present), "missing_required": missing_required},
    )
    return SubmissionPackageResponse(
        manuscript_id=manuscript_id,
        items=[
            PackageItemResponse(
                key=key, label=_pick(principal.locale, label_ar, label_en),
                present=key in present, is_optional=key in vocab.OPTIONAL_PACKAGE_ITEMS,
            )
            for key, (label_ar, label_en) in vocab.SUBMISSION_PACKAGE_ITEMS.items()
        ],
        missing_required=missing_required, missing_optional=missing_optional,
        is_complete=not missing_required,
    )
