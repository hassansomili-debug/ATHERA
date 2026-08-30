"""محرك الترقية | Promotion API (§35.2، §11).

كل قاعدة تُستورد غير متحققة، وكل حساب يُربط بنسخة سياسة بعينها، وكل
سيناريو يخرج موسومًا كإسقاط.
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
from ..models.promotion import (
    PromotionCase,
    PromotionEvidence,
    PromotionPolicy,
    PromotionPolicyVersion,
    PromotionRule,
    PromotionScenario,
    ResearcherPublication,
)
from ..models.research import ResearcherProfile
from ..schemas.promotion import (
    CaseResponse,
    PolicyImportRequest,
    PolicyImportResponse,
    RuleEvaluationResponse,
    RuleResponse,
    RuleVerifyRequest,
    ScenarioRequest,
    ScenarioResponse,
    UnitContributionResponse,
)
from ..services import audit
from ..services.parsing import UnsupportedDocument, parse
from ..services.promotion import calculator, scenarios
from ..services.promotion.facts import CaseFacts, PublicationFact
from ..services.promotion.policy_import import extract_rule_candidates

router = APIRouter(prefix="/api/v1/promotion", tags=["promotion"])


def _pick(locale: str, ar: str, en: str | None) -> str:
    return (en or ar) if locale == "en" else ar


async def _profile(session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> ResearcherProfile:
    profile = (
        await session.execute(select(ResearcherProfile).where(ResearcherProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        raise NotFound("promotion.profile_required")
    return profile


async def _active_version(session: AsyncSession) -> PromotionPolicyVersion:
    version = (
        await session.execute(
            select(PromotionPolicyVersion).order_by(PromotionPolicyVersion.effective_from.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("promotion.no_policy")
    return version


async def _build_facts(session: AsyncSession, profile: ResearcherProfile) -> CaseFacts:
    rows = (
        await session.execute(
            select(ResearcherPublication).where(ResearcherPublication.profile_id == profile.id)
        )
    ).scalars().all()
    return CaseFacts(
        as_of=dt.date.today(),
        rank_started_on=profile.rank_started_on,
        current_rank=profile.current_rank,
        target_rank=profile.target_rank,
        publications=tuple(
            PublicationFact(
                publication_id=str(row.id), title=row.title, published_on=row.published_on,
                author_count=row.author_count, author_position=row.author_position,
                is_corresponding=row.is_corresponding, is_refereed=row.is_refereed,
                is_thesis_derived=row.is_thesis_derived, indexes=tuple(row.indexes or ()),
                journal_name=row.journal_name, verification_status=row.verification_status,
            )
            for row in rows
        ),
    )


async def _rule_inputs(session: AsyncSession, version: PromotionPolicyVersion) -> list[calculator.RuleInput]:
    rows = (
        await session.execute(
            select(PromotionRule).where(PromotionRule.policy_version_id == version.id)
        )
    ).scalars().all()
    return [
        calculator.RuleInput(
            rule_id=str(row.id), rule_type=row.rule_type, rule_key=row.rule_key,
            statement_ar=row.statement_ar, statement_en=row.statement_en, params=row.params or {},
            verification_status=row.verification_status, is_blocking=row.is_blocking,
            effective_from=version.effective_from, effective_to=version.effective_to,
            source_locator=row.source_locator,
        )
        for row in rows
    ]


def _to_response(result: calculator.CaseResult, locale: str, version_id: uuid.UUID | None) -> CaseResponse:
    return CaseResponse(
        policy_version_id=version_id,
        computed_at=dt.datetime.now(dt.UTC),
        units_total=result.units_total,
        units_computable=result.units_computable,
        rules_met=result.rules_met,
        rules_blocking=result.rules_blocking,
        rules_needing_verification=result.rules_needing_verification,
        is_ready=result.is_ready,
        evaluations=[
            RuleEvaluationResponse(
                rule_id=e.rule_id, rule_type=e.rule_type, rule_key=e.rule_key, status=e.status,
                required=e.required, actual=e.actual, is_blocking=e.is_blocking,
                explanation=_pick(locale, e.explanation_ar, e.explanation_en),
                explanation_ar=e.explanation_ar, explanation_en=e.explanation_en,
                contributions=[
                    UnitContributionResponse(
                        publication_id=c.publication_id, contribution=c.contribution,
                        explanation=_pick(locale, c.explanation_ar, c.explanation_en),
                    )
                    for c in e.contributions
                ],
            )
            for e in result.evaluations
        ],
    )


@router.post("/policies/import", response_model=PolicyImportResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def import_policy(
    payload: PolicyImportRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PolicyImportResponse:
    record = (await session.execute(select(File).where(File.id == payload.file_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")

    from ..services.ingestion import _load_bytes  # noqa: PLC0415

    try:
        chunks = parse(await _load_bytes(record), record.content_type, record.original_filename)
    except UnsupportedDocument as exc:
        raise AtheraError("ingestion.unsupported_document", status_code=422, detail=str(exc)) from exc

    policy = PromotionPolicy(
        tenant_id=principal.tenant_id, name_ar=payload.policy_name_ar,
        name_en=payload.policy_name_en, target_rank=payload.target_rank,
    )
    session.add(policy)
    await session.flush()

    version = PromotionPolicyVersion(
        tenant_id=principal.tenant_id, policy_id=policy.id, version_label=payload.version_label,
        effective_from=payload.effective_from, source_document_id=payload.file_id,
        verification_status="unverified",
    )
    session.add(version)
    await session.flush()

    grounded, rejected = extract_rule_candidates(chunks)
    by_seq = {chunk.seq: chunk for chunk in chunks}
    for candidate in grounded:
        chunk = by_seq[candidate.chunk_seq]
        session.add(PromotionRule(
            tenant_id=principal.tenant_id, policy_version_id=version.id,
            rule_type=candidate.rule_type, rule_key=candidate.rule_key,
            statement_ar=candidate.statement_ar, statement_en=candidate.statement_en,
            params=candidate.params, source_locator=chunk.locator, source_quote=candidate.quote,
            verification_status="unverified",  # §11.4 — بلا استثناء.
        ))

    await audit.record(
        session, tenant_id=principal.tenant_id, action="promotion.policy_imported",
        object_type="promotion_policy_version", object_id=version.id,
        actor_user_id=principal.user_id,
        state_after={"rules_proposed": len(grounded), "rejected_unquoted": len(rejected)},
        reason="policy rules extracted as unverified candidates (§11.4)",
    )
    return PolicyImportResponse(
        policy_id=policy.id, policy_version_id=version.id,
        rules_proposed=len(grounded), rules_rejected_unquoted=len(rejected),
    )


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[RuleResponse]:
    rows = (await session.execute(select(PromotionRule))).scalars().all()
    return [
        RuleResponse(
            id=row.id, rule_type=row.rule_type, rule_key=row.rule_key,
            statement=_pick(principal.locale, row.statement_ar, row.statement_en),
            statement_ar=row.statement_ar, statement_en=row.statement_en, params=row.params or {},
            source_locator=row.source_locator, source_quote=row.source_quote,
            is_blocking=row.is_blocking, verification_status=row.verification_status,
        )
        for row in rows
    ]


@router.post("/rules/{rule_id}/verify", response_model=RuleResponse)
async def verify_rule(
    rule_id: uuid.UUID,
    payload: RuleVerifyRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> RuleResponse:
    """اعتماد بشري لكل قاعدة — الباب الوحيد إلى حالة `verified`."""
    rule = (await session.execute(select(PromotionRule).where(PromotionRule.id == rule_id))).scalar_one_or_none()
    if rule is None:
        raise NotFound("promotion.rule_not_found")
    if not rule.source_locator:
        raise AtheraError("promotion.rule_needs_source", status_code=422)

    before = {"verification_status": rule.verification_status, "params": rule.params}
    if payload.params is not None:
        rule.params = payload.params
    if payload.is_blocking is not None:
        rule.is_blocking = payload.is_blocking
    rule.verification_status = "verified"
    rule.verified_by = principal.user_id
    rule.verified_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=principal.tenant_id, action="promotion.rule_verified",
        object_type="promotion_rule", object_id=rule.id, actor_user_id=principal.user_id,
        state_before=before, state_after={"verification_status": "verified", "params": rule.params},
        reason=payload.reason or "researcher verified the extracted policy rule",
        source_refs=[{"locator": rule.source_locator}],
    )
    return RuleResponse(
        id=rule.id, rule_type=rule.rule_type, rule_key=rule.rule_key,
        statement=_pick(principal.locale, rule.statement_ar, rule.statement_en),
        statement_ar=rule.statement_ar, statement_en=rule.statement_en, params=rule.params or {},
        source_locator=rule.source_locator, source_quote=rule.source_quote,
        is_blocking=rule.is_blocking, verification_status=rule.verification_status,
    )


@router.get("/case", response_model=CaseResponse)
@router.post("/calculate", response_model=CaseResponse)
async def compute_case(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> CaseResponse:
    profile = await _profile(session, principal.tenant_id, principal.user_id)
    version = await _active_version(session)
    result = calculator.evaluate(await _rule_inputs(session, version), await _build_facts(session, profile))

    case = PromotionCase(
        tenant_id=principal.tenant_id, profile_id=profile.id, policy_version_id=version.id,
        computed_at=dt.datetime.now(dt.UTC), rules_met=result.rules_met,
        rules_blocking=result.rules_blocking,
        rules_needing_verification=result.rules_needing_verification,
        units_total=result.units_total, units_computable=result.units_computable,
        result={"evaluations": len(result.evaluations), "is_ready": result.is_ready},
    )
    session.add(case)
    await session.flush()

    # AT-S3-05 — كل مساهمة وحدة تُربط بقاعدتها ومنشورها.
    for evaluation in result.evaluations:
        for contribution in evaluation.contributions:
            publication_id = (
                uuid.UUID(contribution.publication_id)
                if not contribution.publication_id.startswith("planned-") else None
            )
            session.add(PromotionEvidence(
                tenant_id=principal.tenant_id, case_id=case.id,
                rule_id=uuid.UUID(evaluation.rule_id), publication_id=publication_id,
                contribution=contribution.contribution,
                explanation_ar=contribution.explanation_ar,
                explanation_en=contribution.explanation_en,
            ))

    await audit.record(
        session, tenant_id=principal.tenant_id, action="promotion.case_computed",
        object_type="promotion_case", object_id=case.id, actor_user_id=principal.user_id,
        state_after={
            "policy_version": str(version.id), "units": float(result.units_total or 0),
            "blocking": result.rules_blocking, "needs_verification": result.rules_needing_verification,
        },
    )
    return _to_response(result, principal.locale, version.id)


@router.post("/scenarios", response_model=ScenarioResponse)
async def run_scenario(
    payload: ScenarioRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ScenarioResponse:
    profile = await _profile(session, principal.tenant_id, principal.user_id)
    version = await _active_version(session)
    rules = await _rule_inputs(session, version)
    facts = await _build_facts(session, profile)

    result = scenarios.project(
        kind=payload.kind, rules=rules, facts=facts,
        planned_works=[
            scenarios.PlannedWork(
                title=work.title, author_count=work.author_count,
                author_position=work.author_position, is_corresponding=work.is_corresponding,
                indexes=tuple(work.indexes), journal_name=work.journal_name,
                is_thesis_derived=work.is_thesis_derived, expected_on=work.expected_on,
            )
            for work in payload.planned_works
        ],
    )

    # يُحفظ كإسقاط في جدوله الخاص — لا يمس promotion_cases إطلاقًا (AT-S3-06).
    session.add(PromotionScenario(
        tenant_id=principal.tenant_id, profile_id=profile.id, policy_version_id=version.id,
        scenario_kind=payload.kind, name_ar=f"سيناريو {payload.kind}", name_en=f"{payload.kind} scenario",
        assumptions={"ar": result.assumptions_ar, "en": result.assumptions_en},
        projection={
            "units": result.projected.units_total, "blocking": result.projected.rules_blocking,
            "added_works": result.added_works,
        },
        is_projection=True,
    ))
    await audit.record(
        session, tenant_id=principal.tenant_id, action="promotion.scenario_projected",
        object_type="promotion_scenario", object_id=profile.id, actor_user_id=principal.user_id,
        state_after={"kind": payload.kind, "added_works": result.added_works},
        reason="projection only; does not change the computed case",
    )

    return ScenarioResponse(
        kind=result.kind, is_projection=True,
        assumptions=result.assumptions_en if principal.locale == "en" else result.assumptions_ar,
        assumptions_ar=result.assumptions_ar, assumptions_en=result.assumptions_en,
        baseline=_to_response(result.baseline, principal.locale, version.id),
        projected=_to_response(result.projected, principal.locale, version.id),
        added_works=result.added_works,
    )
