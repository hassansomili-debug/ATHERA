"""مسارات تخطيط النشر | Publication planning routes (S5D §37).

**تمتدّ على مسارات المشروع القائمة** — لا مساحة عناوين ثانية للفرص.

والترتيب هو الحارس: حال الأدلة، ثم الإذن، ثم التوليد، ثم اختيار الباحث، ثم
الخيط، ثم الهيكل. ولا خطوة تقفز فوق سابقتها.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.orchestrator import Orchestrator
from ..db import tenant_session
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.planning import (
    ManuscriptOutline,
    OpportunityEvidenceLink,
    PlanningRun,
)
from ..models.portfolio import ResearchProject
from ..models.thesis import PublicationOpportunity
from ..providers.gateway import active_model, provider_readiness
from ..schemas.planning import (
    ContextState,
    EvidenceMapEntry,
    EvidenceRef,
    OpportunityList,
    OpportunityView,
    OutlineView,
    PlanningConsentDecision,
    PlanningDecision,
    ThreadIssue,
    ThreadView,
)
from ..services import audit, consent
from ..services.planning import context as ctx
from ..services.planning import generate, outline, thread
from ..services.planning.contracts import OpportunityBatch

logger = logging.getLogger("athera.planning")

router = APIRouter(prefix="/api/v1/projects", tags=["planning"])

PROPOSAL_NOTICE_AR = (
    "هذه مقترحات بُنيت من معرفتك الموثقة — وليست حقائق معتمدة ولا ادعاء جدة."
)
PROPOSAL_NOTICE_EN = (
    "These are proposals built from your verified knowledge — not approved facts, "
    "and not a novelty claim."
)


def _t(locale: str, ar: str, en: str) -> str:
    return en if locale == "en" else ar


async def _project(session: AsyncSession, principal: Principal,
                   project_id: uuid.UUID) -> ResearchProject:
    """المشروع — وRLS يحرس المستأجر قبل أي فحص هنا.

    فمشروع مستأجر آخر لا يُرى أصلًا، ولا يُردّ بـ403 يفشي وجوده.
    """
    project = (
        await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise NotFound("planning.project_not_found")
    return project


async def _build_context(session: AsyncSession, principal: Principal,
                         project_id: uuid.UUID) -> ctx.ResearchContext:
    return await ctx.build(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        capability=consent.PLANNING_CAPABILITY,
    )


@router.get("/{project_id}/publication-context", response_model=ContextState)
async def publication_context(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ContextState:
    """حال الأدلة — **قبل أي نداء، ومهما كان الإذن**."""
    await _project(session, principal, project_id)
    context = await _build_context(session, principal, project_id)
    state = await consent.planning_state(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        context_fingerprint=context.fingerprint)

    if context.sufficient:
        message = _t(principal.locale,
                     f"{len(context.items)} معلومة موثقة جاهزة لبناء فرص النشر.",
                     f"{len(context.items)} verified facts ready for publication planning.")
        steps: list[str] = []
    else:
        message = _t(principal.locale,
                     "لا توجد معرفة موثقة كافية لبناء فرصة نشر بعد.",
                     "There is not enough verified knowledge to build a publication "
                     "opportunity yet.")
        steps = [
            _t(principal.locale, "راجع ما استخرجته أثيرا واعتمد ما تراه صحيحًا",
               "Review what ATHERA extracted and approve what is correct"),
            _t(principal.locale, "ارفع مادة بحثية إضافية",
               "Upload additional research material"),
            _t(principal.locale, "أضف بياناتك أو نتائجك",
               "Add your data or results"),
        ]

    return ContextState(
        project_id=project_id, sufficient=context.sufficient,
        evidence_count=len(context.items), roles=context.summary()["roles"],
        missing_roles=list(context.missing_roles), fingerprint=context.fingerprint,
        consent_state=state, capability=consent.PLANNING_CAPABILITY,
        provider=provider_readiness()[0], model=active_model(),
        message=message, next_steps=steps,
    )


@router.post("/{project_id}/publication-consent", response_model=ContextState)
async def planning_consent(
    project_id: uuid.UUID,
    payload: PlanningConsentDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ContextState:
    """إذن إرسال المعرفة الموثقة لبناء فرص النشر (§6، §7).

    **وموافقة S5C لا تُغني عنه:** تلك أذنت بقراءة مستند، وهذه تأذن بإرسال
    حقائق موثقة لبناء مقترحات. غرضان يقرّهما الباحث مرتين.

    والبصمة تُحفظ مع القرار: أدلةٌ تُضاف بعده لا تُرسل تحته.
    """
    await _project(session, principal, project_id)
    context = await _build_context(session, principal, project_id)
    if payload.context_fingerprint != context.fingerprint:
        # الباحث وافق على شاشةٍ عرضت أدلةً غير التي بين أيدينا الآن.
        raise AtheraError("planning.context_changed", status_code=409,
                          expected=context.fingerprint[:12])

    await consent.record_planning_decision(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        actor_user_id=principal.user_id, granted=payload.decision == "grant",
        provider=provider_readiness()[0], model=active_model(),
        context_fingerprint=context.fingerprint, evidence_count=len(context.items),
        revocation=payload.decision == "revoke",
        request_id=principal.request_id,
    )
    return await publication_context(project_id, principal=principal, session=session)


@router.post("/{project_id}/publication-opportunities", response_model=OpportunityList)
async def generate_opportunities(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityList:
    """يولّد الفرص — **حتميٌّ أولًا، ثم نداء بلا معاملة، ثم حفظ** (§33).

    وبوابة الكفاية تسبق كل شيء: أدلةٌ لا تكفي تعني **صفر نداء** — لا مقترحات
    تُخترع من فراغ ولا رموز تُنفَق على سؤال لا جواب له.
    """
    project = await _project(session, principal, project_id)
    thesis_id = project.id and None
    tenant_id, actor_id, locale = principal.tenant_id, principal.user_id, principal.locale

    # ── معاملة (1): اللقطة والإذن والتشغيلة ──
    context = await _build_context(session, principal, project_id)
    if not context.sufficient:
        raise AtheraError("planning.insufficient_evidence", status_code=422,
                          missing=list(context.missing_roles),
                          evidence_count=len(context.items))
    grant = await consent.planning_authorization(
        session, tenant_id=tenant_id, project_id=project_id,
        context_fingerprint=context.fingerprint)
    if grant is None:
        raise AtheraError("planning.consent_required", status_code=403,
                          capability=consent.PLANNING_CAPABILITY,
                          fingerprint=context.fingerprint)
    run_id = await generate.open_run(session, tenant_id=tenant_id, project_id=project_id,
                                     context=context, capability=grant.capability)
    await session.commit()

    # ── بلا معاملة: النداء الخارجي ──
    maker = _maker(tenant_id, actor_id)
    try:
        batch, agent_run_id = await Orchestrator().run_structured_detached(
            maker, tenant_id=tenant_id, actor_user_id=actor_id,
            agent_key="publication_planner", contract=OpportunityBatch,
            instruction=generate.INSTRUCTION,
            payload=generate.build_prompt(context),
            # §6 — معرفة بحثية غير منشورة: C2. والبوابة تحكم، والإذن مقروء.
            input_classification="C2", output_locale=locale, grant=grant,
        )
    except Exception as exc:  # noqa: BLE001 — الفشل يُروى في معاملة مستقلة
        logger.exception("planning: run %s failed for project %s", run_id, project_id)
        async with maker() as fresh:
            await generate.mark_failed(fresh, run_id=run_id,
                                       error=f"{type(exc).__name__}: {exc}")
        raise

    # ── معاملة (أخيرة): الحفظ والتدقيق ──
    grounded, rejected = generate.ground(batch, context)
    async with maker() as fresh:
        result = await generate.persist(
            fresh, tenant_id=tenant_id, project_id=project_id, run_id=run_id,
            thesis_id=thesis_id, grounded=grounded, context=context,
            rejected_ungrounded=rejected,
        )
        run = (await fresh.execute(
            select(PlanningRun).where(PlanningRun.id == run_id))).scalar_one()
        run.agent_run_id = agent_run_id
        await audit.record(
            fresh, tenant_id=tenant_id, action="planning.opportunities_generated",
            object_type="research_project", object_id=project_id, actor_user_id=actor_id,
            state_after={
                "run_id": str(run_id), "proposed": result.proposed,
                "rejected_ungrounded": rejected,
                "evidence_count": len(context.items),
                "context_fingerprint": context.fingerprint,
                "capability": grant.capability,
                # §14 — يُسجَّل أن السجل مغلق، فلا يُقرأ الصمت ادّعاءً.
                "literature_validation": "pending",
            },
            reason="model proposals generated from verified evidence; nothing verified",
            request_id=principal.request_id,
        )
    return await list_opportunities(project_id, principal=principal, session=session)


def _maker(tenant_id: uuid.UUID, actor_id: uuid.UUID):
    def _make():
        return tenant_session(tenant_id, actor_id)
    return _make


def _view(row: PublicationOpportunity, locale: str, evidence_count: int = 0
          ) -> OpportunityView:
    proposal = (row.readiness_components or {}).get("proposal", {})
    return OpportunityView(
        id=row.id, working_title_ar=row.working_title_ar,
        working_title_en=row.working_title_en,
        research_question_ar=row.research_question_ar,
        opportunity_kind=row.opportunity_kind, paper_kind=row.paper_kind,
        status=row.status, planning_status=row.planning_status,
        evidence_readiness_score=(float(row.evidence_readiness_score)
                                  if row.evidence_readiness_score is not None else None),
        literature_validation_status=row.literature_validation_status,
        journal_validation_status=row.journal_validation_status,
        salami_alert=row.salami_alert,
        proposed_contribution_ar=proposal.get("contribution_ar"),
        claim_boundaries_ar=proposal.get("claim_boundaries_ar"),
        limitations_ar=proposal.get("limitations_ar"),
        missing_requirements=proposal.get("missing_requirements") or [],
        evidence_count=evidence_count,
        proposal_notice=_t(locale, PROPOSAL_NOTICE_AR, PROPOSAL_NOTICE_EN),
    )


@router.get("/{project_id}/publication-opportunities", response_model=OpportunityList)
async def list_opportunities(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityList:
    await _project(session, principal, project_id)
    rows = (
        await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.project_id == project_id)
            .order_by(PublicationOpportunity.evidence_readiness_score.desc().nullslast(),
                      PublicationOpportunity.created_at.desc())
        )
    ).scalars().all()
    counts = dict((
        await session.execute(
            select(OpportunityEvidenceLink.opportunity_id,
                   func.count(OpportunityEvidenceLink.id))
            .group_by(OpportunityEvidenceLink.opportunity_id)
        )
    ).all())
    run = (
        await session.execute(
            select(PlanningRun).where(PlanningRun.project_id == project_id)
            .order_by(PlanningRun.started_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    return OpportunityList(
        project_id=project_id,
        opportunities=[_view(r, principal.locale, counts.get(r.id, 0)) for r in rows],
        generated_at=run.finished_at if run else None,
        run_id=run.id if run else None,
        note=_t(principal.locale, PROPOSAL_NOTICE_AR, PROPOSAL_NOTICE_EN),
    )


@router.post("/{project_id}/publication-opportunities/{opportunity_id}/decide",
             response_model=OpportunityView)
async def decide_opportunity(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    payload: PlanningDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityView:
    """اختيار الباحث أو استبعاده (§18) — **ولا يختار النموذج**.

    ويُكتب في `planning_status` وحده: `status` دورةُ إنتاج ورقة، ولا يمسّها
    قرارُ تخطيط.
    """
    await _project(session, principal, project_id)
    row = (
        await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_id,
                PublicationOpportunity.project_id == project_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("planning.opportunity_not_found")

    before = row.planning_status
    row.planning_status = "selected" if payload.decision == "select" else "excluded"
    row.planning_decided_by = principal.user_id
    row.planning_decided_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=principal.tenant_id,
        action=("planning.opportunity_selected" if payload.decision == "select"
                else "planning.opportunity_excluded"),
        object_type="publication_opportunity", object_id=row.id,
        actor_user_id=principal.user_id,
        state_before={"planning_status": before},
        state_after={"planning_status": row.planning_status,
                     # يُسجَّل أن دورة النشر لم تُمسّ.
                     "publication_status_unchanged": row.status},
        reason=(payload.reason or "")[:1000] or "researcher planning decision",
        request_id=principal.request_id,
    )
    return _view(row, principal.locale)


async def _selected(session: AsyncSession, project_id: uuid.UUID,
                    opportunity_id: uuid.UUID) -> PublicationOpportunity:
    """الخيط والهيكل لا يُبنيان إلا لفرصة **اختارها الباحث** (§16، §27)."""
    row = (
        await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_id,
                PublicationOpportunity.project_id == project_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("planning.opportunity_not_found")
    if row.planning_status != "selected":
        raise AtheraError("planning.selection_required", status_code=409,
                          planning_status=row.planning_status)
    return row


def _entry(element_type: str, claim: str, origin: str, refs) -> EvidenceMapEntry:
    return EvidenceMapEntry(element_type=element_type, claim_ar=claim,
                            origin=origin, evidence=refs)


@router.post("/{project_id}/publication-opportunities/{opportunity_id}/thread",
             response_model=ThreadView)
async def build_thread(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThreadView:
    """يبني الخيط الذهبي من الأدلة ويشغّل المدقّق القائم (§22، §24).

    **حتميٌّ بالكامل — لا نداء نموذج.** بنية الخيط معروفة، والذي يحتاج
    اجتهادًا هو ربطها بالأدلة، وذلك عملٌ يقيني: أي دليل يصير أي عنصر.
    """
    await _project(session, principal, project_id)
    opportunity = await _selected(session, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    await thread.assemble(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        opportunity=opportunity, context=context, actor_user_id=principal.user_id)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="planning.thread_generated",
        object_type="publication_opportunity", object_id=opportunity_id,
        actor_user_id=principal.user_id,
        state_after={"evidence_count": len(context.items),
                     "context_fingerprint": context.fingerprint},
        reason="golden thread assembled from verified evidence",
        request_id=principal.request_id,
    )
    return await read_thread(project_id, opportunity_id, principal=principal,
                             session=session)


@router.get("/{project_id}/publication-opportunities/{opportunity_id}/thread",
            response_model=ThreadView)
async def read_thread(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThreadView:
    await _project(session, principal, project_id)
    opportunity = await _selected(session, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    graph = await thread.to_graph(session, project_id=project_id,
                                  opportunity=opportunity, context=context)
    findings = thread.validate(graph)
    # البنيوي يحجب، واللغوي اقتراح مراجعة — والتمييز من المدقّق نفسه لا مني.
    issues = [
        ThreadIssue(check=f.check_key,
                    severity=("blocking" if f.is_blocking else "advisory"),
                    message_ar=f.detail_ar, message_en=f.detail_en)
        for f in findings
    ]
    mapped = await thread.evidence_map(session, opportunity_id=opportunity_id)
    entries = [
        EvidenceMapEntry(
            element_id=uuid.UUID(m["element_id"]), element_type=m["element_type"],
            claim_ar=m["claim_ar"], origin=m["origin"],
            evidence=[EvidenceRef(memory_id=uuid.UUID(e["memory_id"]), role="evidence",
                                  statement_ar=e["statement_ar"], locator=e["locator"],
                                  quote=e["quote"],
                                  source_file_id=(uuid.UUID(e["source_file_id"])
                                                  if e["source_file_id"] else None))
                      for e in m["evidence"]],
        )
        for m in mapped
    ]
    return ThreadView(
        opportunity_id=opportunity_id, elements=entries, issues=issues,
        blocking=sum(1 for i in issues if i.severity == "blocking"),
        advisory=sum(1 for i in issues if i.severity == "advisory"),
        note=_t(principal.locale,
                "العناصر بلا دليل مقترحات — والفجوة مرشحة حتى يُتحقق من الأدبيات.",
                "Elements without evidence are proposals — the gap stays a candidate "
                "until literature validation."),
    )


@router.post("/{project_id}/publication-opportunities/{opportunity_id}/outline",
             response_model=OutlineView)
async def build_outline(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OutlineView:
    """هيكل الورقة — **بعد الاختيار والخيط والتدقيق** (§27).

    وهيكلٌ لا نثر: غرضٌ وأسئلة وأدلة متاحة وناقصة وحدود ادّعاء. وكتابة
    الورقة مرحلةٌ أخرى لا تبدأ هنا.
    """
    await _project(session, principal, project_id)
    opportunity = await _selected(session, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    view = await read_thread(project_id, opportunity_id, principal=principal,
                             session=session)
    if not view.elements:
        raise AtheraError("planning.thread_required", status_code=409)

    sections = outline.build(context, opportunity)
    row = ManuscriptOutline(
        tenant_id=principal.tenant_id, opportunity_id=opportunity_id,
        project_id=project_id, sections=sections,
        article_type=opportunity.paper_kind,
        generation_run_id=opportunity.generation_run_id, status="draft",
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="planning.outline_generated",
        object_type="publication_opportunity", object_id=opportunity_id,
        actor_user_id=principal.user_id,
        state_after={"sections": len(sections), "outline_id": str(row.id),
                     "thread_blocking_issues": view.blocking},
        reason="structural outline generated; no manuscript prose",
        request_id=principal.request_id,
    )
    return OutlineView(
        id=row.id, opportunity_id=opportunity_id, article_type=row.article_type,
        sections=sections, status=row.status,
        note=_t(principal.locale,
                "هيكلٌ لا نصّ — والمقارنة بالدراسات السابقة بانتظار البحث العلمي.",
                "A structure, not prose — comparison with prior studies is pending "
                "literature search."),
    )


@router.get("/{project_id}/publication-opportunities/{opportunity_id}/outline",
            response_model=OutlineView)
async def read_outline(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OutlineView:
    await _project(session, principal, project_id)
    row = (
        await session.execute(
            select(ManuscriptOutline).where(
                ManuscriptOutline.opportunity_id == opportunity_id,
                ManuscriptOutline.project_id == project_id,
            ).order_by(ManuscriptOutline.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("planning.outline_not_found")
    return OutlineView(
        id=row.id, opportunity_id=opportunity_id, article_type=row.article_type,
        sections=row.sections, status=row.status,
        note=_t(principal.locale,
                "هيكلٌ لا نصّ — والمقارنة بالدراسات السابقة بانتظار البحث العلمي.",
                "A structure, not prose — comparison with prior studies is pending "
                "literature search."),
    )
