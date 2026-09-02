"""مسارات صياغة أقسام المخطوطة | Manuscript section drafting (S5E-B).

**قسمٌ واحد في كل نداء، وترتيبٌ لا يُقفز فوقه:** حال الأدلة، ثم الإذن، ثم
النداء، ثم الحفظ والربط، ثم التحقّق الحتمي، ثم قرار الباحث.

وقسمٌ واحد فقط في هذه الشريحة: **المنهجية**. وما عداه يُرفض صراحةً لا يُقبل
صامتًا — فمرحلةٌ لم تُفعَّل بعد يجب أن تُقال لا أن تُخمَّن.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain.orchestrator import Orchestrator
from ..db import tenant_session
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.literature import Claim
from ..models.planning import ManuscriptOutline
from ..models.portfolio import ResearchProject
from ..models.publishing import (
    ClaimAnalysisLink,
    ClaimMemoryLink,
    Manuscript,
    ManuscriptSection,
    ManuscriptSectionClaim,
    ManuscriptVersion,
)
from ..models.research import ResearcherMemory
from ..models.thesis import PublicationOpportunity
from ..providers.gateway import active_model, provider_readiness
from ..schemas.drafting import (
    ClaimView,
    DraftIssueView,
    DraftingConsentDecision,
    DraftingContextResponse,
    EvidenceRef,
    ManuscriptFromOpportunityRequest,
    SectionReviewDecision,
    SectionView,
)
from ..services import audit, consent
from ..services.planning import context as research_context
from ..services.publishing import vocab
from ..services.publishing.drafting import checks as draft_checks
from ..services.publishing.drafting import context as draft_context
from ..services.publishing.drafting import generate
from ..services.publishing.drafting.contracts import SectionDraft
from .publishing import manuscript_for_tenant

logger = logging.getLogger("athera.drafting")

router = APIRouter(prefix="/api/v1/manuscripts", tags=["manuscript-drafting"])

# **الأقسام المفعَّلة في هذه المرحلة.** المنهجية أولًا: أدلتها موثقة، وتأصيلها
# قابل للفحص، ولا تحتاج سجلّ أدبيات، واختلاقها يُكشف بسهولة (§31).
ENABLED_SECTIONS: frozenset[str] = frozenset({"method"})

DRAFT_NOTICE_AR = (
    "مسودة بُنيت من معرفتك الموثقة — وليست نصًّا معتمدًا. اعتمادك وحده يجعلها كذلك."
)
DRAFT_NOTICE_EN = (
    "A draft built from your verified knowledge — not approved text. "
    "Only your approval makes it so."
)


def _t(locale: str, ar: str, en: str) -> str:
    return en if locale == "en" else ar


def _require_enabled(section_key: str) -> None:
    """المفردة القانونية وحدها، والمرحلة المفعَّلة وحدها.

    و`methods` لا تُقبل ولو بدت مرادفًا: مفردةٌ واحدة للأقسام، وقبول اسمٍ
    ثانٍ يعيد الانحراف الذي أُغلق في S5E-A.
    """
    if section_key not in vocab.MANUSCRIPT_SECTIONS:
        raise AtheraError("drafting.unknown_section", status_code=422,
                          section=section_key)
    if section_key not in ENABLED_SECTIONS:
        raise AtheraError("drafting.section_not_enabled", status_code=422,
                          section=section_key,
                          enabled=",".join(sorted(ENABLED_SECTIONS)))


def _maker(tenant_id: uuid.UUID, actor_id: uuid.UUID):
    def _make():
        return tenant_session(tenant_id, actor_id)
    return _make


async def _current_version(session: AsyncSession, principal: Principal,
                           manuscript_id: uuid.UUID) -> ManuscriptVersion:
    row = (
        await session.execute(
            select(ManuscriptVersion)
            .where(ManuscriptVersion.manuscript_id == manuscript_id,
                   ManuscriptVersion.tenant_id == principal.tenant_id)
            .order_by(ManuscriptVersion.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("publishing.manuscript_not_found")
    return row


async def _section(session: AsyncSession, principal: Principal, version_id: uuid.UUID,
                   section_key: str) -> ManuscriptSection | None:
    return (
        await session.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.version_id == version_id,
                ManuscriptSection.section_key == section_key,
                ManuscriptSection.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()


async def _build_context(session: AsyncSession, principal: Principal,
                         record: Manuscript, section_key: str,
                         prior_text: str | None = None) -> draft_context.DraftingContext:
    if record.opportunity_id is None:
        raise AtheraError("drafting.manuscript_not_bound", status_code=409)
    research = await research_context.build(
        session, tenant_id=principal.tenant_id, project_id=record.project_id,
        capability=consent.DRAFTING_CAPABILITY)
    return await draft_context.build(
        session, research=research, manuscript_id=record.id,
        opportunity_id=record.opportunity_id, outline_id=record.outline_id,
        section_key=section_key, language=record.language,
        capability=consent.DRAFTING_CAPABILITY, prior_text=prior_text)


# ══════════ 1. المخطوطة من الفرصة المختارة ══════════

@router.post("/from-opportunity", status_code=201)
async def manuscript_from_opportunity(
    payload: ManuscriptFromOpportunityRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """يُنشئ مخطوطةً مربوطةً بالمشروع والفرصة والهيكل — أو يعيد القائمة.

    **ولا تُنسخ الفرصة ولا الهيكل**: المخطوطة تشير إليهما بمفتاح أجنبي،
    فيبقى مصدر الحقيقة واحدًا ولا يفترق نسختان.
    """
    project = (
        await session.execute(
            select(ResearchProject).where(
                ResearchProject.id == payload.project_id,
                ResearchProject.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise NotFound("publishing.project_not_found")

    opportunity = (
        await session.execute(
            select(PublicationOpportunity).where(
                PublicationOpportunity.id == payload.opportunity_id,
                PublicationOpportunity.project_id == payload.project_id,
                PublicationOpportunity.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if opportunity is None:
        raise NotFound("planning.opportunity_not_found")
    # §16 من S5D — لا تُبنى ورقة إلا لفرصة اختارها الباحث.
    if opportunity.planning_status != "selected":
        raise AtheraError("planning.selection_required", status_code=409,
                          planning_status=opportunity.planning_status)

    existing = (
        await session.execute(
            select(Manuscript).where(
                Manuscript.tenant_id == principal.tenant_id,
                Manuscript.opportunity_id == payload.opportunity_id)
            .order_by(Manuscript.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        version = await _current_version(session, principal, existing.id)
        return {"manuscript_id": str(existing.id), "created": False,
                "version_label": version.version_label}

    outline = (
        await session.execute(
            select(ManuscriptOutline).where(
                ManuscriptOutline.tenant_id == principal.tenant_id,
                ManuscriptOutline.opportunity_id == payload.opportunity_id)
            .order_by(ManuscriptOutline.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    record = Manuscript(
        tenant_id=principal.tenant_id, project_id=payload.project_id,
        title_ar=payload.title_ar or opportunity.working_title_ar,
        title_en=opportunity.working_title_en, language=payload.language,
        status="draft", opportunity_id=opportunity.id,
        outline_id=outline.id if outline else None,
    )
    session.add(record)
    await session.flush()
    version = ManuscriptVersion(
        tenant_id=principal.tenant_id, manuscript_id=record.id, version_label="v1",
        created_by=principal.user_id, change_reason_ar="النسخة الأولى من الفرصة المختارة",
    )
    session.add(version)
    await session.flush()
    record.current_version_id = version.id

    await audit.record(
        session, tenant_id=principal.tenant_id, action="manuscript.created",
        object_type="manuscript", object_id=record.id, actor_user_id=principal.user_id,
        state_after={"opportunity_id": str(opportunity.id),
                     "outline_id": str(outline.id) if outline else None,
                     "language": payload.language, "version": "v1"},
        reason="manuscript opened for a researcher-selected opportunity",
        request_id=principal.request_id,
    )
    return {"manuscript_id": str(record.id), "created": True, "version_label": "v1"}


# ══════════ 2. حال أدلة القسم ══════════

@router.get("/{manuscript_id}/sections/{section_key}/drafting-context",
            response_model=DraftingContextResponse)
async def drafting_context_state(
    manuscript_id: uuid.UUID,
    section_key: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DraftingContextResponse:
    """ما سيُرسل بالضبط، وحال الإذن عليه — **قبل أي نداء**."""
    _require_enabled(section_key)
    record = await manuscript_for_tenant(session, principal, manuscript_id)
    context = await _build_context(session, principal, record, section_key)
    state = await consent.drafting_state(
        session, tenant_id=principal.tenant_id, manuscript_id=manuscript_id,
        context_fingerprint=context.fingerprint)

    if context.sufficient:
        message = _t(principal.locale,
                     f"{len(context.items)} معلومة موثقة تخصّ هذا القسم.",
                     f"{len(context.items)} verified facts relevant to this section.")
        steps: list[str] = []
    else:
        message = _t(principal.locale,
                     "لا توجد معرفة موثقة كافية لكتابة هذا القسم بعد.",
                     "There is not enough verified knowledge to draft this section yet.")
        steps = [
            _t(principal.locale, "اعتمد ما استخرجته أثيرا من منهجية دراستك",
               "Approve what ATHERA extracted about your methodology"),
            _t(principal.locale, "أضف وصف التصميم والعينة إن لم يكن في المادة",
               "Add the design and sample description if the material lacks it"),
        ]

    summary = context.summary()
    return DraftingContextResponse(
        manuscript_id=manuscript_id, section_key=section_key,
        sufficient=context.sufficient, evidence_count=len(context.items),
        roles=summary["roles"], missing_roles=list(context.missing_roles),
        thread_elements=summary["thread_elements"], fingerprint=context.fingerprint,
        consent_state=state, capability=consent.DRAFTING_CAPABILITY,
        provider=provider_readiness()[0], model=active_model(),
        evidence=[EvidenceRef(memory_id=i.memory_id, role=i.role,
                              statement_ar=i.statement, locator=i.locator, quote=i.quote)
                  for i in context.items],
        message=message, next_steps=steps,
    )


# ══════════ 3. الإذن — مستقلٌّ عن إذن التخطيط ══════════

@router.post("/{manuscript_id}/sections/{section_key}/drafting-consent",
             response_model=DraftingContextResponse)
async def drafting_consent(
    manuscript_id: uuid.UUID,
    section_key: str,
    payload: DraftingConsentDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DraftingContextResponse:
    """إذن إرسال أدلة هذا القسم لصياغته (§12).

    **وإذن التخطيط لا يُغني عنه:** ذاك أذن ببناء مقترحات يقرؤها الباحث،
    وهذا يأذن بصياغة نصّ ورقة يحمل اسمه. غرضان يقرّهما مرتين.
    """
    _require_enabled(section_key)
    record = await manuscript_for_tenant(session, principal, manuscript_id)
    context = await _build_context(session, principal, record, section_key)
    if payload.context_fingerprint != context.fingerprint:
        raise AtheraError("drafting.context_changed", status_code=409,
                          expected=context.fingerprint[:12])

    await consent.record_drafting_decision(
        session, tenant_id=principal.tenant_id, manuscript_id=manuscript_id,
        section_key=section_key, actor_user_id=principal.user_id,
        granted=payload.decision == "grant",
        provider=provider_readiness()[0], model=active_model(),
        context_fingerprint=context.fingerprint, evidence_count=len(context.items),
        revocation=payload.decision == "revoke", request_id=principal.request_id,
    )
    return await drafting_context_state(manuscript_id, section_key,
                                        principal=principal, session=session)


# ══════════ 4. الصياغة — بلا معاملة أثناء النداء ══════════

@router.post("/{manuscript_id}/sections/{section_key}/draft",
             response_model=SectionView)
async def draft_section(
    manuscript_id: uuid.UUID,
    section_key: str,
    principal: Principal = Depends(get_principal),
) -> SectionView:
    """يصوغ القسم — **حتميٌّ أولًا، ثم نداء بلا معاملة، ثم حفظ** (§14).

    **ولا تبعية `get_session` هنا، وذلك مقصود.** تلك تفتح معاملةً تبقى
    مفتوحة طوال الطلب، ونحن ننتظر مزوّدًا خارجيًّا داخله — وهي العلّة التي
    أصلحها S5C وأثبت الإنتاج كلفتها: اتصالٌ علِق 254 ثانية.
    """
    _require_enabled(section_key)
    tenant_id, actor_id = principal.tenant_id, principal.user_id
    maker = _maker(tenant_id, actor_id)

    # ── معاملة (1): اللقطة والإذن والحراسة — ثم تُغلق ──
    async with maker() as opening:
        record = await manuscript_for_tenant(opening, principal, manuscript_id)
        version = await _current_version(opening, principal, manuscript_id)
        current = await _section(opening, principal, version.id, section_key)

        # §26 — نصٌّ اعتمده الباحث لا يُستبدل بنداءٍ عادي.
        if current is not None and current.review_status == "approved":
            raise AtheraError("drafting.section_approved", status_code=409,
                              section=section_key)

        context = await _build_context(opening, principal, record, section_key)
        if not context.sufficient:
            raise AtheraError("drafting.insufficient_evidence", status_code=422,
                              missing=",".join(context.missing_roles),
                              evidence_count=len(context.items))
        grant = await consent.drafting_authorization(
            opening, tenant_id=tenant_id, manuscript_id=manuscript_id,
            context_fingerprint=context.fingerprint)
        if grant is None:
            raise AtheraError("drafting.consent_required", status_code=403,
                              capability=consent.DRAFTING_CAPABILITY,
                              fingerprint=context.fingerprint)
        project_id = record.project_id
        language = record.language

    # ── بلا معاملة: النداء الخارجي ──
    try:
        draft, agent_run_id = await Orchestrator().run_structured_detached(
            maker, tenant_id=tenant_id, actor_user_id=actor_id,
            agent_key="scientific_writer", contract=SectionDraft,
            instruction=generate.INSTRUCTION, payload=generate.build_prompt(context),
            # §6 — معرفة بحثية غير منشورة: C2. والقدرة تحكم، والإذن مقروء.
            input_classification="C2", output_locale=language, grant=grant,
        )
    except Exception as exc:  # noqa: BLE001 — الفشل يُروى ولا يُبتلع
        logger.exception("drafting: section %s failed for manuscript %s",
                         section_key, manuscript_id)
        raise AtheraError("drafting.generation_failed", status_code=502,
                          section=section_key, error=type(exc).__name__) from exc

    grounded, dropped = generate.ground(draft, context)

    # ── معاملة (أخيرة): نسخة جديدة، ثم الحفظ والربط والتدقيق ──
    async with maker() as fresh:
        record = await manuscript_for_tenant(fresh, principal, manuscript_id)
        version = await _current_version(fresh, principal, manuscript_id)
        current = await _section(fresh, principal, version.id, section_key)
        if current is not None:
            # §27 — كل صياغة جديدة نسخةٌ جديدة، بسببها، عبر النظام القائم.
            version = await _new_version(
                fresh, principal, record, version,
                reason=f"إعادة صياغة قسم «{section_key}»", replace=section_key)
            current = await _section(fresh, principal, version.id, section_key)
        if current is None:
            current = ManuscriptSection(
                tenant_id=tenant_id, version_id=version.id, section_key=section_key,
                ordinal=1)
            fresh.add(current)
            await fresh.flush()

        stats = await generate.persist(
            fresh, tenant_id=tenant_id, project_id=project_id, section=current,
            draft=draft, grounded=grounded, agent_run_id=agent_run_id,
            fingerprint=context.fingerprint, known_output_ids=frozenset())
        record.current_version_id = version.id

        await audit.record(
            fresh, tenant_id=tenant_id, action="manuscript.section_drafted",
            object_type="manuscript", object_id=manuscript_id, actor_user_id=actor_id,
            state_after={"section_key": section_key, "version": version.version_label,
                         "context_fingerprint": context.fingerprint,
                         "evidence_count": len(context.items),
                         "dropped_unknown_references": len(dropped),
                         "review_status": "needs_review", **stats},
            reason="model draft grounded in verified evidence; not approved",
            request_id=principal.request_id,
        )

    async with maker() as reading:
        return await read_section(manuscript_id, section_key, principal=principal,
                                  session=reading)


async def _new_version(session: AsyncSession, principal: Principal, record: Manuscript,
                       old: ManuscriptVersion, *, reason: str,
                       replace: str | None) -> ManuscriptVersion:
    """نسخة جديدة تخلف سابقتها — **وتحفظ اعتماد ما لم يتغيّر** (§17).

    والقسم المستبدَل يعود «بانتظار المراجعة»: اعتمادٌ يُنقل إلى نصٍّ آخر
    اعتمادٌ لم يقع.
    """
    label = f"v{int((old.version_label or 'v1').lstrip('v') or 1) + 1}"
    fresh = ManuscriptVersion(
        tenant_id=principal.tenant_id, manuscript_id=record.id, version_label=label,
        created_by=principal.user_id, change_reason_ar=reason, supersedes_id=old.id)
    session.add(fresh)
    await session.flush()

    rows = (await session.execute(
        select(ManuscriptSection).where(
            ManuscriptSection.version_id == old.id,
            ManuscriptSection.tenant_id == principal.tenant_id)
    )).scalars().all()
    for row in rows:
        if row.section_key == replace:
            continue
        session.add(ManuscriptSection(
            tenant_id=principal.tenant_id, version_id=fresh.id,
            section_key=row.section_key, text_ar=row.text_ar, text_en=row.text_en,
            claim_ids=row.claim_ids, analysis_run_ids=row.analysis_run_ids,
            ordinal=row.ordinal, review_status=row.review_status,
            reviewed_by=row.reviewed_by, reviewed_at=row.reviewed_at,
            drafting_context_fingerprint=row.drafting_context_fingerprint,
            generation_run_id=row.generation_run_id))
    await session.flush()
    return fresh


# ══════════ 5. قراءة القسم بادعاءاته وكشوفاته ══════════

@router.get("/{manuscript_id}/sections/{section_key}", response_model=SectionView)
async def read_section(
    manuscript_id: uuid.UUID,
    section_key: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SectionView:
    _require_enabled(section_key)
    record = await manuscript_for_tenant(session, principal, manuscript_id)
    version = await _current_version(session, principal, manuscript_id)
    section = await _section(session, principal, version.id, section_key)
    if section is None:
        raise NotFound("drafting.section_not_drafted")

    rows = (await session.execute(
        select(Claim, ManuscriptSectionClaim.ordinal)
        .join(ManuscriptSectionClaim, ManuscriptSectionClaim.claim_id == Claim.id)
        .where(ManuscriptSectionClaim.section_id == section.id,
               ManuscriptSectionClaim.tenant_id == principal.tenant_id,
               Claim.tenant_id == principal.tenant_id)
        .order_by(ManuscriptSectionClaim.ordinal)
    )).all()

    claims: list[ClaimView] = []
    for claim, _ordinal in rows:
        evidence = (await session.execute(
            select(ResearcherMemory)
            .join(ClaimMemoryLink, ClaimMemoryLink.memory_id == ResearcherMemory.id)
            .where(ClaimMemoryLink.claim_id == claim.id,
                   ClaimMemoryLink.tenant_id == principal.tenant_id,
                   ResearcherMemory.tenant_id == principal.tenant_id)
        )).scalars().all()
        outputs = (await session.execute(
            select(ClaimAnalysisLink.output_id).where(
                ClaimAnalysisLink.claim_id == claim.id,
                ClaimAnalysisLink.tenant_id == principal.tenant_id)
        )).scalars().all()
        claims.append(ClaimView(
            id=claim.id, text_ar=claim.text_ar, claim_type=claim.claim_type,
            status=claim.status, is_labelled_inference=claim.is_labelled_inference,
            evidence=[EvidenceRef(memory_id=m.id, role="evidence",
                                  statement_ar=m.statement_ar, locator=m.source_locator,
                                  quote=m.source_quote) for m in evidence],
            analysis_output_ids=list(outputs)))

    issues: list[DraftIssueView] = []
    if section.text_ar:
        context = await _build_context(session, principal, record, section_key)
        replay = SectionDraft(
            section_text_ar=section.text_ar, section_text_en=section.text_en,
            claims=[], missing_evidence=[], warnings_ar=[])
        for found in draft_checks.run(replay, context,
                                      known_memory_ids=context.memory_ids,
                                      known_output_ids=frozenset()):
            issues.append(DraftIssueView(
                issue_key=found.issue_key, section_key=found.section_key,
                severity="blocking" if found.is_blocking else "advisory",
                message_ar=found.detail_ar, message_en=found.detail_en,
                excerpt=found.excerpt, claim_index=found.claim_index))
        # وادعاءٌ بلا سند بنيوي كشفٌ حاجب — يُقرأ من الروابط لا من النصّ.
        for index, view in enumerate(claims):
            if view.status == "evidence_gap":
                issues.append(DraftIssueView(
                    issue_key="factual_claim_without_verified_evidence",
                    section_key=section_key, severity="blocking",
                    message_ar="ادعاء بلا دليل موثق يسنده.",
                    message_en="A claim with no verified evidence behind it.",
                    excerpt=view.text_ar[:200], claim_index=index))

    return SectionView(
        manuscript_id=manuscript_id, version_label=version.version_label,
        section_key=section_key, text_ar=section.text_ar, text_en=section.text_en,
        review_status=section.review_status, reviewed_at=section.reviewed_at,
        fingerprint=section.drafting_context_fingerprint, claims=claims, issues=issues,
        blocking=sum(1 for i in issues if i.severity == "blocking"),
        note=_t(principal.locale, DRAFT_NOTICE_AR, DRAFT_NOTICE_EN),
    )


# ══════════ 6. قرار الباحث ══════════

@router.post("/{manuscript_id}/sections/{section_key}/review",
             response_model=SectionView)
async def review_section(
    manuscript_id: uuid.UUID,
    section_key: str,
    payload: SectionReviewDecision,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SectionView:
    """اعتماد الباحث أو طلبه تعديلًا — **ولا يعتمد النموذج نفسه** (§25)."""
    _require_enabled(section_key)
    await manuscript_for_tenant(session, principal, manuscript_id)
    version = await _current_version(session, principal, manuscript_id)
    section = await _section(session, principal, version.id, section_key)
    if section is None:
        raise NotFound("drafting.section_not_drafted")

    before = section.review_status
    section.review_status = ("approved" if payload.decision == "approve"
                             else "revision_requested")
    section.reviewed_by = principal.user_id
    section.reviewed_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=principal.tenant_id,
        action=("manuscript.section_approved" if payload.decision == "approve"
                else "manuscript.section_revision_requested"),
        object_type="manuscript", object_id=manuscript_id,
        actor_user_id=principal.user_id,
        state_before={"review_status": before},
        state_after={"review_status": section.review_status,
                     "section_key": section_key, "version": version.version_label},
        reason=(payload.reason or "")[:1000] or "researcher review decision",
        request_id=principal.request_id,
    )
    return await read_section(manuscript_id, section_key, principal=principal,
                              session=session)
