"""مسارات تخطيط النشر | Publication planning routes (S5D §37).

**تمتدّ على مسارات المشروع القائمة** — لا مساحة عناوين ثانية للفرص.

والترتيب هو الحارس: حال الأدلة، ثم الإذن، ثم التوليد، ثم اختيار الباحث، ثم
الخيط، ثم الهيكل. ولا خطوة تقفز فوق سابقتها.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.orchestrator import Orchestrator
from ..db import project_session
from ..deps import (
    Principal,
    get_principal,
    get_project_session,
    project_tenant,
)
from ..errors import AtheraError, NotFound
from ..models.planning import (
    ManuscriptOutline,
    OpportunityEvidenceLink,
    PlanningRun,
)
from ..models.portfolio import ResearchProject
from ..models.thesis import PublicationOpportunity
from ..providers.gateway import active_model, provider_idempotency_capability, provider_readiness
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
from ..services import audit, collaboration, consent, idempotency
from ..services.planning import context as ctx
from ..services.planning import generate, outline, thread
from ..services.planning.contracts import OpportunityBatch
from ..services.thesis import selection
from ..transaction import TransactionalRoute

logger = logging.getLogger("athera.planning")

router = APIRouter(prefix="/api/v1/projects", tags=["planning"], route_class=TransactionalRoute)

PROPOSAL_NOTICE_AR = (
    "هذه مقترحات بُنيت من معرفتك الموثقة — وليست حقائق معتمدة ولا ادعاء جدة."
)
PROPOSAL_NOTICE_EN = (
    "These are proposals built from your verified knowledge — not approved facts, "
    "and not a novelty claim."
)


def _t(locale: str, ar: str, en: str) -> str:
    return en if locale == "en" else ar


EDIT = "edit_research_content"


async def _project(session: AsyncSession, principal: Principal,
                   project_id: uuid.UUID, *,
                   permission: str = collaboration.VIEW_PROJECT) -> ResearchProject:
    """**البوابة القانونية الوحيدة** — بالمستأجر والعضويّة والصلاحية معًا.

    كان هذا الفحص يقرأ المشروع بمعرّفه وحده ويتّكل على RLS في حراسة
    المستأجر. والاتّكال صحيح ما دامت RLS تنطبق — وفي الإنتاج لم تنطبق:
    رابط زمن التشغيل كان يتصل بدورٍ يحمل `rolbypassrls`، فسقطت الطبقة
    الوحيدة، ولم يكن خلفها شيء. فقرأ مستأجرٌ فرصَ آخر وخيطه وهيكله، وردّ
    قراره بـ200. فأُضيفت الفلترة الصريحة، والطبقتان تبقيان معًا.

    **ثم تبيّن أنّ الطبقتين معًا تحرسان الحدَّ الخطأ.** فكلتاهما تسأل
    «أمِن مستأجري هذا البحث؟» — ولا تسأل واحدةٌ منهما «أهو بحثي؟». وفي
    مؤسسةٍ فيها ألفُ باحث كان كلُّ واحدٍ منهم يقرأ فرصَ نشر الألف الباقين
    ويقرّر فيها. فمساواةُ المستأجر شرطُ عزلٍ لا تفويضَ مشروع، والتفويضُ
    صفُّ عضويّةٍ نشط يحمل الصلاحية — وهو ما تقرؤه البوابة المشتركة الآن.

    و404 لا 403: وجودُ بحثٍ ليس لك معلومةٌ لا تُفشى.
    """
    return (await collaboration.ensure_project_access(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
        user_id=principal.user_id, permission=permission,
        not_found_code="planning.project_not_found")).project


async def _opportunity(session: AsyncSession, principal: Principal,
                       project_id: uuid.UUID,
                       opportunity_id: uuid.UUID) -> PublicationOpportunity:
    """فرصةٌ بمعرّفها **ومشروعها ومستأجرها** — ولا واحدة تُقرأ بدونها."""
    row = (
        await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == opportunity_id,
                PublicationOpportunity.project_id == project_id,
                PublicationOpportunity.tenant_id == project_tenant(session, principal),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("planning.opportunity_not_found")
    return row


async def _build_context(session: AsyncSession, principal: Principal,
                         project_id: uuid.UUID) -> ctx.ResearchContext:
    return await ctx.build(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
        capability=consent.PLANNING_CAPABILITY,
    )


@router.get("/{project_id}/publication-context", response_model=ContextState)
async def publication_context(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ContextState:
    """حال الأدلة — **قبل أي نداء، ومهما كان الإذن**."""
    await _project(session, principal, project_id)
    context = await _build_context(session, principal, project_id)
    state = await consent.planning_state(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
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
    session: AsyncSession = Depends(get_project_session),
) -> ContextState:
    """إذن إرسال المعرفة الموثقة لبناء فرص النشر (§6، §7).

    **وموافقة S5C لا تُغني عنه:** تلك أذنت بقراءة مستند، وهذه تأذن بإرسال
    حقائق موثقة لبناء مقترحات. غرضان يقرّهما الباحث مرتين.

    والبصمة تُحفظ مع القرار: أدلةٌ تُضاف بعده لا تُرسل تحته.
    """
    await _project(session, principal, project_id, permission=EDIT)
    context = await _build_context(session, principal, project_id)
    if payload.context_fingerprint != context.fingerprint:
        # الباحث وافق على شاشةٍ عرضت أدلةً غير التي بين أيدينا الآن.
        raise AtheraError("planning.context_changed", status_code=409,
                          expected=context.fingerprint[:12])

    await consent.record_planning_decision(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
        actor_user_id=principal.user_id, granted=payload.decision == "grant",
        provider=provider_readiness()[0], model=active_model(),
        context_fingerprint=context.fingerprint, evidence_count=len(context.items),
        revocation=payload.decision == "revoke",
        request_id=principal.request_id,
    )
    return await publication_context(project_id, principal=principal, session=session)


@router.post("/{project_id}/publication-opportunities", response_model=OpportunityList)
async def generate_opportunities(
    request: Request,
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> OpportunityList | JSONResponse:
    """المعالجُ المُزخرَف — يفوّض إلى المتن (RC-T1-H2-B4)."""
    return await generate_opportunities_body(project_id, principal=principal,
                                             request=request)


async def generate_opportunities_body(
    project_id: uuid.UUID,
    *,
    principal: Principal,
    request: Request | None = None,
) -> OpportunityList | JSONResponse:
    """يولّد الفرص — **حتميٌّ أولًا، ثم نداء بلا معاملة، ثم حفظ** (§33).

    و`request=None` تعني **بلا مفتاح**: المسلكُ القديم حرفيًّا، وتُفتَح
    التشغيلةُ في التحضير كما كانت. ولا شواهدَ FastAPI في هذا التوقيع.

    وبوابة الكفاية تسبق كل شيء: أدلةٌ لا تكفي تعني **صفر نداء** — لا مقترحات
    تُخترع من فراغ ولا رموز تُنفَق على سؤال لا جواب له.

    **ولا تبعية `get_session` هنا — وذلك مقصود.**

    تلك التبعية تفتح معاملةً تبقى مفتوحة طوال الطلب، ونحن ننتظر مزوّدًا
    خارجيًّا داخله. فتعود العلّة التي أصلحها S5C: اتصالٌ `idle in
    transaction` عبر انتظارٍ شبكي. فتُدار الجلسات هنا صراحةً: قصيرةٌ قبل
    النداء، وقصيرةٌ بعده، ولا شيء مفتوح أثناءه.
    """
    #
    # **والجلساتُ هنا جلساتُ بحثٍ لا جلساتُ مستأجر.** فمتعاونٌ من مؤسسةٍ
    # أخرى يحمل `edit_research_content` في هذا البحث لا مدخلَ له بجلسةِ
    # بيته: يُقرأ صفرُ صفوفٍ فيُردّ ٤٠٤ على بحثٍ هو عضوٌ فيه. و`_maker`
    # يبني الجسرَ القانونيَّ نفسَه في كلّ معاملةٍ من الثلاث.
    actor_id = principal.user_id
    maker = _maker(project_id, principal.tenant_id, actor_id)

    # ── معاملة (1): اللقطة والإذن والتشغيلة — ثم تُغلق ──
    async with maker() as opening:
        # والمستأجرُ النافذُ يُقرأ من الجلسة بعد العبور، لا من الرمز. وهو
        # واحدٌ في المعاملات الثلاث: البحثُ واحدٌ، والجسرُ يُشتقّ من صفِّ
        # عضويّةٍ محفوظ لا من زمنٍ ولا من طلب.
        tenant_id = project_tenant(opening, principal)
        await _project(opening, principal, project_id, permission=EDIT)
        context = await _build_context(opening, principal, project_id)
        if not context.sufficient:
            raise AtheraError("planning.insufficient_evidence", status_code=422,
                              missing=list(context.missing_roles),
                              evidence_count=len(context.items))
        grant = await consent.planning_authorization(
            opening, tenant_id=tenant_id, project_id=project_id,
            context_fingerprint=context.fingerprint)
        if grant is None:
            raise AtheraError("planning.consent_required", status_code=403,
                              capability=consent.PLANNING_CAPABILITY,
                              fingerprint=context.fingerprint)
        # ══ الحجزُ بالمستأجر **النافذ** لا بمستأجر الرمز (H2-B4) ══
        #
        # **وهذا المسارُ يعمل على بحثٍ قد يكون مستأجرُه غيرَ مستأجرِ
        # الرمز** (جسرُ التعاون). فحجزٌ بـ`principal.tenant_id` يضع صفَّ
        # الجيل في مستأجرٍ آخر: فتُعاد أجوبةٌ عبر الحدّ، أو لا تُعاد حيث
        # يجب. فيُستعمل `tenant_id` النافذُ المقروءُ أعلاه.
        #
        # والبصمةُ تحمل **بصمةَ السياق العلميّ**، فتغيُّرُ الدليل يجعل
        # الطلبَ طلبًا آخر.
        keyed = request is not None and idempotency.is_keyed(request)
        guard = idempotency.LeaseGuard()
        if keyed:
            guard = await idempotency.begin_leased_in(
                opening, request,
                tenant_id=tenant_id, actor_user_id=actor_id,
                body={
                    "project_id": str(project_id),
                    "context_fingerprint": context.fingerprint,
                    "locale": principal.locale,
                    "capability": grant.capability,
                },
                ttl=idempotency.LEASE_MODEL)

        # ══ ولا `PlanningRun` قبل المزوّد للعملِ المُمفتَح (الخيار أ) ══
        #
        # `planning_runs.status` مُقيَّدٌ بـ`CHECK` على أربعٍ ليس فيها ما
        # يقول «لا يُعرف». فصفٌّ يُفتح قبل النداء يبقى `running` إلى الأبد
        # عند سقوطٍ، أو يُكذَّب بـ`failed` عند غموض. فيُؤجَّل فتحُه إلى
        # معاملة النجاح: **سقوطٌ قبل الحدّ ⇒ صفرُ تشغيلات**، وغموضٌ ⇒
        # صفرُ تشغيلات، ووسمُ الجيل الدائمُ هو البرهان.
        #
        # وبلا مفتاحٍ يبقى السلوكُ القديم — والرصدُ القائمُ لا يُنقَص.
        # **والشرطُ «بلا مفتاح» لا «بلا إجارة».** وكانا يُخلطان: فإعادةٌ
        # أو تعارضٌ أو غموضٌ تُعيد `guard.lease = None` أيضًا — فكان
        # `open_run` يعمل على مسلكِ الإعادة فيُودِع تشغيلةً شاردة. وقد
        # قِيس: عدُّ التشغيلات صار ٢ بعد إعادةٍ لم تُنفّذ شيئًا.
        run_id = None
        if not keyed:
            run_id = await generate.open_run(
                opening, tenant_id=tenant_id, project_id=project_id,
                context=context, capability=grant.capability)
    if guard.answer is not None:
        return guard.answer

    locale = principal.locale
    thesis_id = None

    # ── بلا معاملة: النداء الخارجي ──
    boundary = idempotency.ModelBoundary(
        maker, guard, provider=provider_readiness()[0],
        capability=provider_idempotency_capability())
    try:
        batch, agent_run_id = await Orchestrator().run_structured_detached(
            maker, tenant_id=tenant_id, actor_user_id=actor_id,
            agent_key="publication_planner", contract=OpportunityBatch,
            instruction=generate.INSTRUCTION,
            payload=generate.build_prompt(context),
            # §6 — معرفة بحثية غير منشورة: C2. والبوابة تحكم، والإذن مقروء.
            input_classification="C2", output_locale=locale, grant=grant,
            before_provider_call=(boundary if guard.lease is not None else None),
        )
    except Exception as exc:  # noqa: BLE001 — الفشل يُروى في معاملة مستقلة
        logger.exception("planning: run %s failed for project %s", run_id, project_id)
        if guard.lease is not None:
            # **ولا `mark_failed` لأثرٍ لا يُعرف.** وما رُدّ قبل الحدِّ
            # يُغلَق إخفاقًا معلومًا فيبقى المفتاحُ قابلًا للإعادة.
            if not boundary.crossed:
                await idempotency.close_pre_external(
                    maker, guard, reason=f"pre_external:{type(exc).__name__}")
                raise
            from ..errors import athera_error_handler  # noqa: PLC0415

            return await athera_error_handler(
                request, idempotency.ExternalResultUnknown())
        # بلا مفتاحٍ ⇒ التشغيلةُ فُتحت في التحضير، فالمعرّفُ موجود.
        assert run_id is not None  # noqa: S101
        async with maker() as fresh:
            await generate.mark_failed(fresh, tenant_id=tenant_id, run_id=run_id,
                                       error=f"{type(exc).__name__}: {exc}")
        raise

    # ── معاملة (أخيرة): الحفظ والتدقيق ──
    grounded, rejected = generate.ground(batch, context)
    async with maker() as fresh:
        # وإعادةُ التفويضِ وفحصُ اللقطة قبل الإيداع: النموذجُ انتظر.
        if guard.lease is not None:
            await _project(fresh, principal, project_id, permission=EDIT)
            live = await _build_context(fresh, principal, project_id)
            if live.fingerprint != context.fingerprint:
                raise AtheraError("planning.context_changed", status_code=409,
                                  expected_fingerprint=context.fingerprint,
                                  current_fingerprint=live.fingerprint)
            run_id = await generate.open_run(
                fresh, tenant_id=tenant_id, project_id=project_id,
                context=context, capability=grant.capability)
        # وقد فُتحت التشغيلةُ إمّا في التحضير (بلا مفتاح) أو هنا (بمفتاح).
        assert run_id is not None  # noqa: S101
        result = await generate.persist(
            fresh, tenant_id=tenant_id, project_id=project_id, run_id=run_id,
            thesis_id=thesis_id, grounded=grounded, context=context,
            rejected_ungrounded=rejected,
        )
        run = (await fresh.execute(
            select(PlanningRun).where(PlanningRun.id == run_id,
                                      PlanningRun.tenant_id == tenant_id))).scalar_one()
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
        if guard.lease is not None:
            # **الجوابُ والإتمامُ في معاملةِ الطفرة نفسِها.**
            answer = await list_opportunities(project_id, principal=principal,
                                              session=fresh)
            await idempotency.settle_leased(
                fresh, guard, status=200, body=jsonable_encoder(answer))
            return answer
    async with maker() as reading:
        return await list_opportunities(project_id, principal=principal, session=reading)


def _maker(project_id: uuid.UUID, tenant_id: uuid.UUID, actor_id: uuid.UUID):
    """مصنعُ جلساتٍ **مربوطةٍ بمستأجر البحث** — لا بمستأجر الرمز.

    وهو الاستثناءُ الوحيدُ المُعلَن في تدقيق مسارات البحث: هذا المسار لا
    يأخذ `get_project_session` تبعيةً لأنّ تبعيةً واحدةً تُبقي معاملةً
    مفتوحةً طوال انتظارِ مزوّدٍ خارجي (علّة S5C). فيُبنى الجسرُ نفسُه
    هنا صراحةً، في كلّ معاملةٍ قصيرة — والحدُّ هو الحدُّ نفسُه:
    `project_session` تُثبت عضويّةَ الفاعل في البحث قبل أن تربط.
    """
    def _make():
        return project_session(project_id, tenant_id, actor_id)
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
    session: AsyncSession = Depends(get_project_session),
) -> OpportunityList:
    await _project(session, principal, project_id)
    rows = (
        await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.project_id == project_id,
                   PublicationOpportunity.tenant_id == project_tenant(session, principal))
            .order_by(PublicationOpportunity.evidence_readiness_score.desc().nullslast(),
                      PublicationOpportunity.created_at.desc())
        )
    ).scalars().all()
    # **عدٌّ مقيَّد بفرص هذه القائمة لا بالجدول كله.** كان الاستعلام يجمع كل
    # روابط الأدلة في القاعدة ثم يقرأ منها ما يخصّه — وبلا RLS يعني ذلك
    # قراءة عدّادات مستأجرين آخرين.
    counts: dict[uuid.UUID, int] = {}
    if rows:
        counts = dict((
            await session.execute(
                select(OpportunityEvidenceLink.opportunity_id,
                       func.count(OpportunityEvidenceLink.id))
                .where(OpportunityEvidenceLink.tenant_id == project_tenant(session, principal),
                       OpportunityEvidenceLink.opportunity_id.in_([r.id for r in rows]))
                .group_by(OpportunityEvidenceLink.opportunity_id)
            )
        ).all())
    run = (
        await session.execute(
            select(PlanningRun).where(PlanningRun.project_id == project_id,
                                      PlanningRun.tenant_id == project_tenant(session, principal))
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
    session: AsyncSession = Depends(get_project_session),
) -> OpportunityView:
    """اختيار الباحث أو استبعاده (§18) — **ولا يختار النموذج**.

    ويُكتب في `planning_status` وحده: `status` دورةُ إنتاج ورقة، ولا يمسّها
    قرارُ تخطيط.
    """
    # الملكية تُثبَت **قبل أي تعديل** — لا كتابة تسبق التفويض.
    await _project(session, principal, project_id, permission=EDIT)
    row = await _opportunity(session, principal, project_id, opportunity_id)

    # **والكتابةُ في `services/thesis/selection.py` وحدها.** فرصةُ الرسالة
    # تُختار من موجّه الرسائل ولا مشروعَ لها بعد، فلو بقيت الكتابةُ هنا
    # لصار للقرار الواحد كاتبان يفترقان.
    await selection.decide(
        session, tenant_id=project_tenant(session, principal), opportunity=row,
        actor_user_id=principal.user_id, decision=payload.decision,
        reason=payload.reason, request_id=principal.request_id)
    return _view(row, principal.locale)


async def _selected(session: AsyncSession, principal: Principal,
                    project_id: uuid.UUID,
                    opportunity_id: uuid.UUID) -> PublicationOpportunity:
    """الخيط والهيكل لا يُبنيان إلا لفرصة **اختارها الباحث** (§16، §27).

    والملكية تُفحص أولًا: حالةُ فرصةِ مستأجرٍ آخر ليست جوابًا يُعطى.
    """
    row = await _opportunity(session, principal, project_id, opportunity_id)
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
    session: AsyncSession = Depends(get_project_session),
) -> ThreadView:
    """يبني الخيط الذهبي من الأدلة ويشغّل المدقّق القائم (§22، §24).

    **حتميٌّ بالكامل — لا نداء نموذج.** بنية الخيط معروفة، والذي يحتاج
    اجتهادًا هو ربطها بالأدلة، وذلك عملٌ يقيني: أي دليل يصير أي عنصر.
    """
    await _project(session, principal, project_id, permission=EDIT)
    opportunity = await _selected(session, principal, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    await thread.assemble(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
        opportunity=opportunity, context=context, actor_user_id=principal.user_id)
    await session.flush()

    await audit.record(
        session, tenant_id=project_tenant(session, principal), action="planning.thread_generated",
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
    session: AsyncSession = Depends(get_project_session),
) -> ThreadView:
    await _project(session, principal, project_id)
    opportunity = await _selected(session, principal, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    graph = await thread.to_graph(session, tenant_id=project_tenant(session, principal),
                                  project_id=project_id,
                                  opportunity=opportunity, context=context)
    findings = thread.validate(graph)
    # البنيوي يحجب، واللغوي اقتراح مراجعة — والتمييز من المدقّق نفسه لا مني.
    issues = [
        ThreadIssue(check=f.check_key,
                    severity=("blocking" if f.is_blocking else "advisory"),
                    message_ar=f.detail_ar, message_en=f.detail_en)
        for f in findings
    ]
    mapped = await thread.evidence_map(session, tenant_id=project_tenant(session, principal),
                                       project_id=project_id,
                                       opportunity_id=opportunity_id)
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
    session: AsyncSession = Depends(get_project_session),
) -> OutlineView:
    """هيكل الورقة — **بعد الاختيار والخيط والتدقيق** (§27).

    وهيكلٌ لا نثر: غرضٌ وأسئلة وأدلة متاحة وناقصة وحدود ادّعاء. وكتابة
    الورقة مرحلةٌ أخرى لا تبدأ هنا.
    """
    await _project(session, principal, project_id, permission=EDIT)
    opportunity = await _selected(session, principal, project_id, opportunity_id)
    context = await _build_context(session, principal, project_id)

    view = await read_thread(project_id, opportunity_id, principal=principal,
                             session=session)
    if not view.elements:
        raise AtheraError("planning.thread_required", status_code=409)

    sections = outline.build(context, opportunity)
    row = ManuscriptOutline(
        tenant_id=project_tenant(session, principal), opportunity_id=opportunity_id,
        project_id=project_id, sections=sections,
        article_type=opportunity.paper_kind,
        generation_run_id=opportunity.generation_run_id, status="draft",
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=project_tenant(session, principal), action="planning.outline_generated",
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
    session: AsyncSession = Depends(get_project_session),
) -> OutlineView:
    await _project(session, principal, project_id)
    row = (
        await session.execute(
            select(ManuscriptOutline).where(
                ManuscriptOutline.opportunity_id == opportunity_id,
                ManuscriptOutline.project_id == project_id,
                ManuscriptOutline.tenant_id == project_tenant(session, principal),
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
