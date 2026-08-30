"""الذكاء الاستباقي | Proactive trend intelligence API (§51).

أربع قواعد يفرضها هذا الموجّه:
  • لا إشارة يتيمة، ومخرَج النموذج يُسجَّل ولا يُحتسب (§51.1، §51.11).
  • الاتجاه يُصادق عليه بأربعة شروط معًا، وعتباتها سياسة (§51.1).
  • درجتان منفصلتان: قوة الاتجاه ≠ ملاءمة الفرصة (§51.3).
  • لا تقديم خارجي إلا بفعل بشري أو تفويض ساري (§51.5 P14).
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.trends import (
    CompetitiveNoveltyCheck,
    OpportunityCardRow,
    OpportunityEvidence,
    PaperPipelineRun,
    ResearchIntelligenceBrief,
    ResearchTrend,
    ResearchWatchlist,
    SubmissionDelegationRow,
    TrendSignalRow,
)
from ..schemas.trends import (
    BriefCreateRequest,
    BriefItemInput,
    BriefResponse,
    CardCreateRequest,
    CardResponse,
    ConditionResponse,
    FitCriterionResponse,
    NoveltyCheckRequest,
    NoveltyCheckResponse,
    NoveltyDecisionRequest,
    OpportunityFitRequest,
    OpportunityFitResponse,
    PipelineResponse,
    PipelineUpdateRequest,
    SignalCreateRequest,
    StageResponse,
    SubmissionAuthorizeRequest,
    SubmissionDecisionResponse,
    TimelinePointResponse,
    TrendStrengthResponse,
    WatchlistCreateRequest,
    WatchlistResponse,
)
from ..services import audit
from ..services.trends import brief, pipeline, scoring, signals, vocab

router = APIRouter(prefix="/api/v1", tags=["trends"])

# §51.1 — العتبات الأربع كبيانات سياسة، قابلة للتعديل لكل مؤسسة.
DEFAULT_VALIDATION_POLICY = signals.ValidationPolicy(
    policy_id="default", min_evidence_weight=3.0, min_signals=4,
    min_distinct_sources=3, min_span_days=90,
)


def _pick(locale: str, arabic: str, english: str | None) -> str:
    return (english or arabic) if locale == "en" else arabic


@router.post("/watchlists", response_model=WatchlistResponse,
             status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    payload: WatchlistCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> WatchlistResponse:
    if not (payload.keywords or payload.theories or payload.methods or payload.journal_ids):
        raise AtheraError("trends.watchlist_needs_scope", status_code=422)

    row = ResearchWatchlist(
        tenant_id=principal.tenant_id, watchlist_kind=payload.watchlist_kind,
        name_ar=payload.name_ar, name_en=payload.name_en, owner_user_id=principal.user_id,
        project_id=payload.project_id, keywords=payload.keywords, theories=payload.theories,
        methods=payload.methods, journal_ids=payload.journal_ids,
        refresh_cron=payload.refresh_cron,
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.watchlist_created",
        object_type="research_watchlist", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"kind": payload.watchlist_kind, "keywords": len(payload.keywords)},
    )
    label_ar, label_en = vocab.WATCHLIST_KINDS[payload.watchlist_kind]
    return WatchlistResponse(
        id=row.id, watchlist_kind=row.watchlist_kind,
        kind_label=_pick(principal.locale, label_ar, label_en),
        name=_pick(principal.locale, row.name_ar, row.name_en),
        keywords=row.keywords, is_active=row.is_active, last_refreshed_at=None,
    )


@router.post("/trends/signals", response_model=TrendStrengthResponse,
             status_code=status.HTTP_201_CREATED)
async def record_signal(
    payload: SignalCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TrendStrengthResponse:
    """يسجّل إشارة ثم يعيد تقييم قوة الاتجاه — لا يفصلهما."""
    try:
        signals.TrendSignal(
            signal_id="pending", trend_key=payload.trend_key,
            source_type=payload.source_type, source_id=payload.source_id,
            observed_at=payload.observed_at, pattern=payload.pattern, weight=payload.weight,
        )
    except signals.SignalError as exc:
        raise AtheraError("trends.invalid_signal", status_code=422, detail=str(exc)) from exc

    trend = (
        await session.execute(
            select(ResearchTrend).where(ResearchTrend.trend_key == payload.trend_key)
        )
    ).scalar_one_or_none()
    if trend is None:
        trend = ResearchTrend(
            tenant_id=principal.tenant_id, trend_key=payload.trend_key,
            label_ar=payload.trend_label_ar, discovered_at=dt.datetime.now(dt.UTC),
            status="candidate",
        )
        session.add(trend)
        await session.flush()

    counts = vocab.SIGNAL_SOURCE_TYPES[payload.source_type]
    session.add(TrendSignalRow(
        tenant_id=principal.tenant_id, trend_id=trend.id, watchlist_id=payload.watchlist_id,
        pattern=payload.pattern, source_type=payload.source_type,
        source_id=payload.source_id, source_url=payload.source_url,
        observed_at=payload.observed_at, weight=payload.weight,
        counts_as_evidence=counts, detail_ar=payload.detail_ar,
    ))
    await session.flush()

    rows = (
        await session.execute(
            select(TrendSignalRow).where(TrendSignalRow.trend_id == trend.id)
        )
    ).scalars().all()
    strength = signals.validate(
        trend.trend_key,
        [
            signals.TrendSignal(
                signal_id=str(r.id), trend_key=trend.trend_key, source_type=r.source_type,
                source_id=r.source_id, observed_at=r.observed_at, pattern=r.pattern,
                weight=float(r.weight),
            )
            for r in rows
        ],
        DEFAULT_VALIDATION_POLICY, as_of=dt.datetime.now(dt.UTC),
    )

    now = dt.datetime.now(dt.UTC)
    trend.status = strength.status
    trend.evidence_weight = strength.evidence_weight
    trend.signal_count = strength.signal_count
    trend.distinct_sources = strength.distinct_sources
    trend.span_days = strength.span_days
    trend.validation_policy_id = DEFAULT_VALIDATION_POLICY.policy_id
    trend.validation_snapshot = {
        c.key: {"satisfied": c.satisfied, "actual": c.actual, "required": c.required,
                "detail_ar": c.detail_ar, "detail_en": c.detail_en}
        for c in strength.conditions
    }
    trend.last_validated_at = now

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.signal_recorded",
        object_type="research_trend", object_id=trend.id, actor_user_id=principal.user_id,
        state_after={
            "source_type": payload.source_type, "counts_as_evidence": counts,
            "status": strength.status, "ignored": strength.ignored_signals,
        },
        reason="model output is recorded but never counted as evidence (§51.1)",
        source_refs=[{"source_type": payload.source_type, "source_id": payload.source_id}],
    )
    return TrendStrengthResponse(
        trend_id=trend.id, trend_key=trend.trend_key, status=strength.status,
        evidence_weight=strength.evidence_weight, signal_count=strength.signal_count,
        distinct_sources=strength.distinct_sources, span_days=strength.span_days,
        ignored_signals=strength.ignored_signals,
        conditions=[
            ConditionResponse(key=c.key, satisfied=c.satisfied, actual=c.actual,
                              required=c.required,
                              detail=_pick(principal.locale, c.detail_ar, c.detail_en))
            for c in strength.conditions
        ],
        unmet_conditions=strength.unmet_conditions, is_validated=strength.is_validated,
        note_ar=strength.note_ar, note_en=strength.note_en,
    )


@router.get("/trends", response_model=list[TrendStrengthResponse])
async def list_trends(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[TrendStrengthResponse]:
    """يعيد آخر تصديق محفوظ لكل اتجاه — لا يعيد الحساب هنا.

    القراءة لا تغيّر حالة تصديق؛ إعادة الحساب تقع عند وصول إشارة جديدة وحدها،
    وإلا صار عرضُ الشاشة فعلًا يعدّل السجل.
    """
    rows = (
        await session.execute(
            select(ResearchTrend).order_by(ResearchTrend.discovered_at.desc())
        )
    ).scalars().all()
    out: list[TrendStrengthResponse] = []
    for row in rows:
        snapshot = row.validation_snapshot or {}
        conditions = [
            ConditionResponse(
                key=key, satisfied=bool(value.get("satisfied")),
                actual=float(value.get("actual", 0)), required=float(value.get("required", 0)),
                detail=_pick(principal.locale, value.get("detail_ar", key),
                             value.get("detail_en")),
            )
            for key, value in snapshot.items()
        ]
        unmet = [c.key for c in conditions if not c.satisfied]
        out.append(TrendStrengthResponse(
            trend_id=row.id, trend_key=row.trend_key, status=row.status,
            evidence_weight=float(row.evidence_weight or 0), signal_count=row.signal_count or 0,
            distinct_sources=row.distinct_sources or 0, span_days=row.span_days or 0,
            ignored_signals=[], conditions=conditions, unmet_conditions=unmet,
            is_validated=row.status == "validated",
            note_ar="آخر تصديق محفوظ؛ لا يُعاد الحساب عند القراءة.",
            note_en="Last stored validation; reading does not recompute it.",
        ))
    return out


@router.get("/trends/{trend_id}/timeline", response_model=list[TimelinePointResponse])
async def trend_timeline(
    trend_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[TimelinePointResponse]:
    """§51.1 — خط زمني يبنيه الدليل المحتسب وحده."""
    rows = (
        await session.execute(select(TrendSignalRow).where(TrendSignalRow.trend_id == trend_id))
    ).scalars().all()
    points = signals.timeline([
        signals.TrendSignal(
            signal_id=str(r.id), trend_key="t", source_type=r.source_type,
            source_id=r.source_id, observed_at=r.observed_at, pattern=r.pattern,
            weight=float(r.weight),
        )
        for r in rows
    ])
    return [
        TimelinePointResponse(period=p.period, signal_count=p.signal_count, weight=p.weight)
        for p in points
    ]


def _fit(payload: OpportunityFitRequest, locale: str) -> tuple[scoring.OpportunityFit,
                                                               OpportunityFitResponse]:
    result = scoring.score(payload.model_dump())
    response = OpportunityFitResponse(
        fit_score=result.fit_score,
        criteria=[
            FitCriterionResponse(
                key=c.key, weight=c.weight, ratio=c.ratio, points=c.points,
                label=_pick(locale, c.label_ar, c.label_en),
                rationale=_pick(locale, c.rationale_ar, c.rationale_en),
            )
            for c in result.criteria
        ],
        uncomputed=result.uncomputed, blocking_reasons=result.blocking_reasons,
        is_actionable=result.is_actionable, note_ar=result.note_ar, note_en=result.note_en,
    )
    return result, response


@router.get("/opportunity-cards", response_model=list[CardResponse])
async def list_cards(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[CardResponse]:
    rows = (
        await session.execute(
            select(OpportunityCardRow).order_by(OpportunityCardRow.created_at.desc())
        )
    ).scalars().all()
    out: list[CardResponse] = []
    for row in rows:
        evidence = (
            await session.execute(
                select(OpportunityEvidence).where(OpportunityEvidence.card_id == row.id)
            )
        ).scalars().all()
        out.append(CardResponse(
            id=row.id, trend_id=row.trend_id, working_title_ar=row.working_title_ar,
            central_question_ar=row.central_question_ar, gap_ar=row.gap_ar,
            gap_confidence=float(row.gap_confidence),
            fit_score=float(row.fit_score) if row.fit_score is not None else None,
            blocking_reasons=list(row.blocking_reasons or []),
            # فرصة بلا درجة محسوبة ليست قابلة للتنفيذ؛ غياب الدرجة ليس نجاحًا.
            is_actionable=row.fit_score is not None and not row.blocking_reasons,
            approved_at=row.approved_at, converted_project_id=row.converted_project_id,
            evidence_count=len(evidence),
        ))
    return out


@router.post("/opportunity-cards/score", response_model=OpportunityFitResponse)
async def score_opportunity(
    payload: OpportunityFitRequest,
    principal: Principal = Depends(get_principal),
) -> OpportunityFitResponse:
    """§51.3 — درجة مستقلة تمامًا عن قوة الاتجاه."""
    try:
        _, response = _fit(payload, principal.locale)
    except scoring.ScoringError as exc:
        raise AtheraError("trends.invalid_fit", status_code=422, detail=str(exc)) from exc
    return response


@router.post("/opportunity-cards", response_model=CardResponse,
             status_code=status.HTTP_201_CREATED)
async def create_card(
    payload: CardCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> CardResponse:
    """§51.4 — البطاقة تحمل سؤالًا وفجوة وأدلة، ولا تحمل نصًا."""
    try:
        pipeline.OpportunityCard(
            card_id="pending", working_title_ar=payload.working_title_ar,
            central_question_ar=payload.central_question_ar,
            trend_summary_ar=payload.trend_summary_ar,
            evidence_signal_ids=tuple(str(s) for s in payload.evidence_signal_ids),
            gap_ar=payload.gap_ar, gap_confidence=payload.gap_confidence,
        )
    except pipeline.PipelineError as exc:
        raise AtheraError("trends.invalid_card", status_code=422, detail=str(exc)) from exc

    fit_result = None
    if payload.fit is not None:
        fit_result, _ = _fit(payload.fit, principal.locale)

    row = OpportunityCardRow(
        tenant_id=principal.tenant_id, trend_id=payload.trend_id,
        working_title_ar=payload.working_title_ar,
        central_question_ar=payload.central_question_ar,
        trend_summary_ar=payload.trend_summary_ar, gap_ar=payload.gap_ar,
        gap_confidence=payload.gap_confidence,
        proposed_theory_ar=payload.proposed_theory_ar,
        proposed_method_ar=payload.proposed_method_ar,
        required_data_ar=payload.required_data_ar,
        data_is_available=payload.data_is_available,
        candidate_journal_ids=payload.candidate_journal_ids,
        execution_risk_ar=payload.execution_risk_ar,
        estimated_months=payload.estimated_months,
        fit_score=fit_result.fit_score if fit_result else None,
        fit_criteria={c.key: c.points for c in fit_result.criteria} if fit_result else None,
        blocking_reasons=fit_result.blocking_reasons if fit_result else [],
    )
    session.add(row)
    await session.flush()

    for signal_id in payload.evidence_signal_ids:
        session.add(OpportunityEvidence(
            tenant_id=principal.tenant_id, card_id=row.id, signal_id=signal_id
        ))
    session.add(PaperPipelineRun(
        tenant_id=principal.tenant_id, card_id=row.id, current_stage="P0",
        completed_stages=[], ready_conditions={},
        unmet_conditions=sorted(vocab.READY_CONDITIONS),
    ))
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.card_created",
        object_type="opportunity_card", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"evidence": len(payload.evidence_signal_ids),
                     "fit_score": float(row.fit_score) if row.fit_score else None,
                     "blocking": row.blocking_reasons},
        reason="a card cites the signals that justify it and starts unapproved (§51.4)",
    )
    return CardResponse(
        id=row.id, trend_id=row.trend_id, working_title_ar=row.working_title_ar,
        central_question_ar=row.central_question_ar, gap_ar=row.gap_ar,
        gap_confidence=float(row.gap_confidence),
        fit_score=float(row.fit_score) if row.fit_score is not None else None,
        blocking_reasons=row.blocking_reasons,
        is_actionable=fit_result.is_actionable if fit_result else False,
        approved_at=None, converted_project_id=None,
        evidence_count=len(payload.evidence_signal_ids),
    )


@router.post("/opportunity-cards/{card_id}/approve", response_model=CardResponse)
async def approve_card(
    card_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> CardResponse:
    """§51.11 — لا تحويل إلى مشروع إلا بعد اعتماد المستخدم."""
    row = (
        await session.execute(
            select(OpportunityCardRow).where(OpportunityCardRow.id == card_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("trends.card_not_found")
    if row.approved_at is not None:
        raise AtheraError("trends.card_already_approved", status_code=422)

    row.approved_by = principal.user_id
    row.approved_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.card_approved",
        object_type="opportunity_card", object_id=card_id, actor_user_id=principal.user_id,
        state_after={"approved": True},
        reason="researcher approved the proactive opportunity card (§51.11)",
    )
    evidence = (
        await session.execute(
            select(OpportunityEvidence).where(OpportunityEvidence.card_id == card_id)
        )
    ).scalars().all()
    return CardResponse(
        id=row.id, trend_id=row.trend_id, working_title_ar=row.working_title_ar,
        central_question_ar=row.central_question_ar, gap_ar=row.gap_ar,
        gap_confidence=float(row.gap_confidence),
        fit_score=float(row.fit_score) if row.fit_score is not None else None,
        blocking_reasons=row.blocking_reasons, is_actionable=not row.blocking_reasons,
        approved_at=row.approved_at, converted_project_id=row.converted_project_id,
        evidence_count=len(evidence),
    )


async def _pipeline_row(session: AsyncSession, card_id: uuid.UUID) -> PaperPipelineRun:
    row = (
        await session.execute(
            select(PaperPipelineRun).where(PaperPipelineRun.card_id == card_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("trends.pipeline_not_found")
    return row


def _pipeline_response(row: PaperPipelineRun, locale: str) -> PipelineResponse:
    state = pipeline.build_state(
        str(row.card_id), completed_stages=set(row.completed_stages or []),
        ready_conditions=dict(row.ready_conditions or {}),
    )
    unmet = state.unmet_ready_conditions
    return PipelineResponse(
        card_id=row.card_id, current_stage=state.current_stage,
        stages=[
            StageResponse(stage=s.stage,
                          label=_pick(locale, s.label_ar, s.label_en),
                          completed=s.completed)
            for s in state.stages
        ],
        ready_conditions=dict(row.ready_conditions or {}), unmet_conditions=unmet,
        unmet_labels=[
            _pick(locale, *vocab.READY_CONDITIONS[key]) for key in unmet
        ],
        is_ready_for_submission=state.can_reach_ready_for_submission,
    )


@router.get("/opportunity-cards/{card_id}/pipeline", response_model=PipelineResponse)
async def get_pipeline(
    card_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PipelineResponse:
    return _pipeline_response(await _pipeline_row(session, card_id), principal.locale)


@router.post("/opportunity-cards/{card_id}/pipeline", response_model=PipelineResponse)
async def update_pipeline(
    card_id: uuid.UUID,
    payload: PipelineUpdateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PipelineResponse:
    row = await _pipeline_row(session, card_id)
    unknown_conditions = set(payload.ready_conditions) - set(vocab.READY_CONDITIONS)
    if unknown_conditions:
        raise AtheraError("trends.unknown_condition", status_code=422,
                          keys=",".join(sorted(unknown_conditions)))
    try:
        state = pipeline.build_state(
            str(card_id), completed_stages=set(payload.completed_stages),
            ready_conditions=payload.ready_conditions,
        )
    except pipeline.PipelineError as exc:
        raise AtheraError("trends.invalid_stage", status_code=422, detail=str(exc)) from exc

    row.completed_stages = payload.completed_stages
    row.ready_conditions = payload.ready_conditions
    row.unmet_conditions = state.unmet_ready_conditions
    row.current_stage = state.current_stage
    row.is_ready_for_submission = state.can_reach_ready_for_submission

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.pipeline_advanced",
        object_type="paper_pipeline_run", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"stage": row.current_stage, "unmet": row.unmet_conditions,
                     "ready": row.is_ready_for_submission},
    )
    return _pipeline_response(row, principal.locale)


@router.post("/opportunity-cards/{card_id}/authorize-submission",
             response_model=SubmissionDecisionResponse)
async def authorize_submission(
    card_id: uuid.UUID,
    payload: SubmissionAuthorizeRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SubmissionDecisionResponse:
    """§51.5 P14 — الباب الوحيد إلى تقديم خارجي."""
    row = await _pipeline_row(session, card_id)
    now = dt.datetime.now(dt.UTC)
    state = pipeline.build_state(
        str(card_id), completed_stages=set(row.completed_stages or []),
        ready_conditions=dict(row.ready_conditions or {}),
    )

    delegation = None
    if payload.delegation_id is not None:
        record = (
            await session.execute(
                select(SubmissionDelegationRow).where(
                    SubmissionDelegationRow.id == payload.delegation_id
                )
            )
        ).scalar_one_or_none()
        if record is None:
            raise NotFound("trends.delegation_not_found")
        delegation = pipeline.SubmissionDelegation(
            delegation_id=str(record.id), granted_by=str(record.granted_by),
            granted_at=record.granted_at, scope_ar=record.scope_ar,
            expires_at=record.expires_at, revoked_at=record.revoked_at,
        )

    decision = pipeline.authorize_submission(
        state, human_act_by=str(principal.user_id) if payload.human_act else None,
        delegation=delegation, at=now,
    )
    if decision.allowed:
        row.submission_authorized_at = now
        if decision.basis == "human_act":
            row.submission_authorized_by = principal.user_id
        else:
            row.submission_delegation_id = payload.delegation_id

    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="trends.submission_authorized" if decision.allowed
        else "trends.submission_refused",
        object_type="paper_pipeline_run", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"allowed": decision.allowed, "basis": decision.basis,
                     "unmet": decision.unmet_conditions},
        reason=decision.reason_ar,
    )
    return SubmissionDecisionResponse(
        allowed=decision.allowed, basis=decision.basis,
        unmet_conditions=decision.unmet_conditions,
        reason=_pick(principal.locale, decision.reason_ar, decision.reason_en),
        reason_ar=decision.reason_ar, reason_en=decision.reason_en,
    )


# ---------------------------------------------------------------------------
# §51.9 — النشرة الاستخباراتية
# ---------------------------------------------------------------------------


def _items(rows: list | None) -> list[BriefItemInput]:
    return [BriefItemInput(**row) for row in (rows or [])]


def _brief_response(row: ResearchIntelligenceBrief, locale: str) -> BriefResponse:
    model = brief.Brief(
        cadence=row.cadence, period_start=row.period_start, period_end=row.period_end,
        new_trends=tuple(brief.BriefItem(**item) for item in (row.new_trends or [])),
        score_changes=tuple(brief.BriefItem(**item) for item in (row.score_changes or [])),
        new_cards=tuple(brief.BriefItem(**item) for item in (row.new_cards or [])),
        alerts=tuple(brief.BriefItem(**item) for item in (row.alerts or [])),
    )
    cadence_ar, cadence_en = vocab.BRIEF_CADENCES[row.cadence]
    return BriefResponse(
        id=row.id, cadence=row.cadence,
        cadence_label=_pick(locale, cadence_ar, cadence_en),
        period_start=row.period_start, period_end=row.period_end,
        new_trends=_items(row.new_trends), score_changes=_items(row.score_changes),
        new_cards=_items(row.new_cards), alerts=_items(row.alerts),
        is_empty=model.is_empty,
        summary=_pick(locale, model.summary_ar, model.summary_en),
        seen_at=row.seen_at, acknowledged_at=row.acknowledged_at,
    )


@router.get("/briefs", response_model=list[BriefResponse])
async def list_briefs(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[BriefResponse]:
    rows = (
        await session.execute(
            select(ResearchIntelligenceBrief)
            .where(ResearchIntelligenceBrief.user_id == principal.user_id)
            .order_by(ResearchIntelligenceBrief.period_end.desc())
            .limit(50)
        )
    ).scalars().all()
    return [_brief_response(row, principal.locale) for row in rows]


@router.post("/briefs", response_model=BriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(
    payload: BriefCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BriefResponse:
    """§51.9 — نشرة تُحفظ حتى لو كانت فارغة.

    حذف النشرة الفارغة يجعل الصمت غامضًا: لا يعود المستخدم يعرف أالرصد عمل
    ولم يجد، أم لم يعمل أصلًا.
    """
    try:
        brief.Brief(
            cadence=payload.cadence, period_start=payload.period_start,
            period_end=payload.period_end,
            new_trends=tuple(brief.BriefItem(**item.model_dump())
                             for item in payload.new_trends),
            score_changes=tuple(brief.BriefItem(**item.model_dump())
                                for item in payload.score_changes),
            new_cards=tuple(brief.BriefItem(**item.model_dump())
                            for item in payload.new_cards),
            alerts=tuple(brief.BriefItem(**item.model_dump()) for item in payload.alerts),
        )
    except brief.BriefError as exc:
        raise AtheraError("trends.invalid_brief", status_code=422, detail=str(exc)) from exc

    row = ResearchIntelligenceBrief(
        tenant_id=principal.tenant_id, user_id=principal.user_id, cadence=payload.cadence,
        period_start=payload.period_start, period_end=payload.period_end,
        new_trends=[item.model_dump() for item in payload.new_trends],
        score_changes=[item.model_dump() for item in payload.score_changes],
        new_cards=[item.model_dump() for item in payload.new_cards],
        alerts=[item.model_dump() for item in payload.alerts],
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.brief_created",
        object_type="research_intelligence_brief", object_id=row.id,
        actor_user_id=principal.user_id,
        state_after={"cadence": payload.cadence,
                     "items": len(payload.new_trends) + len(payload.new_cards)},
    )
    return _brief_response(row, principal.locale)


@router.post("/briefs/{brief_id}/acknowledge", response_model=BriefResponse)
async def acknowledge_brief(
    brief_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BriefResponse:
    row = (
        await session.execute(
            select(ResearchIntelligenceBrief).where(
                ResearchIntelligenceBrief.id == brief_id,
                ResearchIntelligenceBrief.user_id == principal.user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("trends.brief_not_found")
    now = dt.datetime.now(dt.UTC)
    if row.seen_at is None:
        row.seen_at = now
    row.acknowledged_at = now
    return _brief_response(row, principal.locale)


# ---------------------------------------------------------------------------
# §51.10 — فحص الجدة التنافسية
# ---------------------------------------------------------------------------


def _novelty_response(row: CompetitiveNoveltyCheck, locale: str) -> NoveltyCheckResponse:
    verdict = brief.assess_novelty(
        float(row.similarity),
        published_source_id=str(row.source_id) if row.source_id else None,
    )
    return NoveltyCheckResponse(
        id=row.id, card_id=row.card_id, similarity=float(row.similarity),
        is_blocking=verdict.is_blocking, needs_review=verdict.needs_review,
        reason=_pick(locale, verdict.reason_ar, verdict.reason_en),
        decision=row.decision, checked_at=row.checked_at,
    )


@router.get("/opportunity-cards/{card_id}/novelty",
            response_model=list[NoveltyCheckResponse])
async def list_novelty_checks(
    card_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[NoveltyCheckResponse]:
    rows = (
        await session.execute(
            select(CompetitiveNoveltyCheck)
            .where(CompetitiveNoveltyCheck.card_id == card_id)
            .order_by(CompetitiveNoveltyCheck.checked_at.desc())
        )
    ).scalars().all()
    return [_novelty_response(row, principal.locale) for row in rows]


@router.post("/opportunity-cards/{card_id}/novelty",
             response_model=NoveltyCheckResponse, status_code=status.HTTP_201_CREATED)
async def record_novelty_check(
    card_id: uuid.UUID,
    payload: NoveltyCheckRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> NoveltyCheckResponse:
    """§51.10 — التشابه يُسجَّل ولا يُبتّ آليًّا.

    الحقل `decision` يبقى فارغًا هنا عمدًا: الحكم بأن فكرتين «مختلفتان» أو
    «متداخلتان» قرار بحثي، لا نتيجة عتبة رقمية.
    """
    card = (
        await session.execute(
            select(OpportunityCardRow).where(OpportunityCardRow.id == card_id)
        )
    ).scalar_one_or_none()
    if card is None:
        raise NotFound("trends.card_not_found")

    row = CompetitiveNoveltyCheck(
        tenant_id=principal.tenant_id, card_id=card_id,
        source_id=payload.published_source_id, similarity=payload.similarity,
        checked_at=dt.datetime.now(dt.UTC), decision_note_ar=payload.note_ar,
    )
    session.add(row)
    await session.flush()

    verdict = brief.assess_novelty(
        payload.similarity,
        published_source_id=str(payload.published_source_id)
        if payload.published_source_id else None,
    )
    if verdict.is_blocking:
        reasons = set(card.blocking_reasons or [])
        reasons.add("competitive_novelty:published_overlap")
        card.blocking_reasons = sorted(reasons)

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.novelty_checked",
        object_type="opportunity_card", object_id=card_id, actor_user_id=principal.user_id,
        state_after={"similarity": payload.similarity, "blocking": verdict.is_blocking},
        reason=verdict.reason_ar,
    )
    return _novelty_response(row, principal.locale)


@router.post("/novelty-checks/{check_id}/decide", response_model=NoveltyCheckResponse)
async def decide_novelty(
    check_id: uuid.UUID,
    payload: NoveltyDecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> NoveltyCheckResponse:
    """الحسم البشري وحده يرفع الحجب — أو يُسقط البطاقة."""
    row = (
        await session.execute(
            select(CompetitiveNoveltyCheck).where(CompetitiveNoveltyCheck.id == check_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("trends.novelty_check_not_found")
    if row.decision is not None:
        raise AtheraError("trends.novelty_already_decided", status_code=422)

    row.decision = payload.decision
    row.decision_note_ar = payload.note_ar
    row.decided_by = principal.user_id

    card = (
        await session.execute(
            select(OpportunityCardRow).where(OpportunityCardRow.id == row.card_id)
        )
    ).scalar_one_or_none()
    if card is not None and payload.decision == "distinct":
        card.blocking_reasons = [
            reason for reason in (card.blocking_reasons or [])
            if reason != "competitive_novelty:published_overlap"
        ]

    await audit.record(
        session, tenant_id=principal.tenant_id, action="trends.novelty_decided",
        object_type="competitive_novelty_check", object_id=row.id,
        actor_user_id=principal.user_id,
        state_after={"decision": payload.decision},
        reason=payload.note_ar,
    )
    return _novelty_response(row, principal.locale)
