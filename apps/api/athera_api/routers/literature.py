"""الأدبيات والأدلة | Literature and evidence API (§35.4، §14).

المصادر تُستورد من سجل خارجي حقيقي أو لا تُستورد. والادعاء بلا دليل يُعلَن
فجوة — لا يُولَّد له مرجع (TC-02).
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import Principal, get_principal, get_session
from ..discovery import DiscoveryProvider, ReferenceCandidate, default_providers, discover
from ..errors import AtheraError, NotFound
from ..models.literature import ACCESS_STATES, Author, Claim, ClaimEvidenceLink, Source, SourceAuthor
from ..schemas.discovery import (
    ExternalAccessLinkView,
    ProviderClaimView,
    ProviderStatusView,
    ReferenceCandidateView,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
)
from ..schemas.literature import (
    ClaimCreateRequest,
    ClaimResponse,
    ClaimStatusResponse,
    EvidenceLinkRequest,
    ExcerptCreateRequest,
    ExcerptResponse,
    LedgerEntry,
    LedgerResponse,
    SourceCandidate,
    SourceImportRequest,
    SourceResponse,
    SourceSearchRequest,
)
from ..services import audit
from ..services.literature import ledger, registry, verification

router = APIRouter(prefix="/api/v1", tags=["literature"])
settings = get_settings()


def _registries() -> list[registry.SourceRegistry]:
    """§33.2 — الترتيب: بيانات علمية رسمية أولًا.

    في بيئة بلا شبكة أو بلا إعداد يعود سجل حتمي فارغ: لا نتائج مخترعة، ولا
    فشل غامض.
    """
    if settings.app_env == "test":
        return [registry.OfflineRegistry()]
    return [registry.CrossrefRegistry(), registry.OpenAlexRegistry()]


def _discovery_providers() -> list[DiscoveryProvider]:
    """فهارس الاكتشاف — أو لا شيء، **وهي حالٌ ثالثة تُعلَن لا تُخفى**.

    البوابة هي بوابة `_registries` نفسها عمدًا: بيئة الاختبار لا تنادي
    أحدًا فتبقى CI حتمية بلا شبكة، وما عداها ينادي الفهرسين كما ينادي
    الاستيراد بـDOI اليوم. ولو رُبطت هنا ببوابةٍ أخرى لصار استيراد المرجع
    يعمل وبحثُه لا يعمل في النشر ذاته — وهو عيبٌ يقع على الباحث بلا سبب
    يفهمه.

    و«بلا فهارس» تُعاد إلى الواجهة حالًا مستقلّة: ليست «لا نتائج» ولا
    «تعذّر فهرس».
    """
    if settings.app_env == "test":
        return []
    # أدب الاستعمال يطلب جهة اتصال. الترويسة تحمل نطاق المنتج دائمًا،
    # ويُضاف بريدٌ إن ضُبط — فيُبلَّغ الفريق قبل أن يُحجب المرور لا بعده.
    return default_providers(mailto=(os.getenv("LITERATURE_CONTACT_EMAIL") or None))


def _claim_views(candidate: ReferenceCandidate) -> list[ProviderClaimView]:
    return [
        ProviderClaimView(
            provider=claim.provider, provider_id=claim.provider_id, doi=claim.doi,
            title=claim.title, authors=list(claim.authors), year=claim.year,
            venue=claim.venue, volume=claim.volume, issue=claim.issue, pages=claim.pages,
            abstract=claim.abstract, url=claim.url, open_access=claim.open_access,
            citation_count=claim.citation_count, type=claim.type,
            retraction_status=claim.retraction_status,
        )
        for claim in candidate.ordered_claims
    ]


def _pick(locale: str, ar: str, en: str | None) -> str:
    return (en or ar) if locale == "en" else ar


async def _source_response(session: AsyncSession, source: Source) -> SourceResponse:
    names = (
        await session.execute(
            select(Author.display_name)
            .join(SourceAuthor, SourceAuthor.author_id == Author.id)
            .where(SourceAuthor.source_id == source.id)
            .order_by(SourceAuthor.position)
        )
    ).scalars().all()
    return SourceResponse(
        id=source.id, doi=source.doi, title=source.title,
        publication_year=source.publication_year, journal_name=source.journal_name_raw,
        authors=list(names), theory=source.theory, method=source.method, sample=source.sample,
        findings=source.findings, limitations=source.limitations,
        retraction_status=source.retraction_status, retraction_detail=source.retraction_detail,
        access_state=source.access_state, last_verified_at=source.last_verified_at,
        registry=source.registry, verification_status=source.verification_status,
        can_carry_excerpt=ACCESS_STATES.get(source.access_state, False),
    )


@router.get("/sources", response_model=list[SourceResponse])
async def list_sources(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[SourceResponse]:
    rows = (
        await session.execute(select(Source).order_by(Source.created_at.desc()).limit(200))
    ).scalars().all()
    return [await _source_response(session, row) for row in rows]


@router.post("/sources/search", response_model=list[SourceCandidate])
async def search_sources(
    payload: SourceSearchRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[SourceCandidate]:
    """البحث يُسجَّل لأنه إفصاح خارجي.

    نص الاستعلام يغادر المستأجر إلى خدمة طرف ثالث — وقد يحمل عنوان بحث غير
    منشور أو فكرة قيد التطوير. تسجيله واجب تدقيق وخصوصية (§36.2)، لا شكلية.
    """
    results: list[SourceCandidate] = []
    used_registry: str | None = None
    failed: list[str] = []

    for source_registry in _registries():
        try:
            records = await source_registry.search(payload.query, limit=payload.limit)
        except Exception:  # noqa: BLE001 — سجل معطّل لا يوقف البقية، لكنه يُسجَّل
            failed.append(source_registry.name)
            continue
        results.extend(
            SourceCandidate(
                registry=record.registry, registry_id=record.registry_id, doi=record.doi,
                title=record.title, publication_year=record.publication_year,
                journal_name=record.journal_name, authors=record.authors,
                retraction_status=record.retraction_status, access_state=record.access_state,
            )
            for record in records
        )
        if results:
            used_registry = source_registry.name
            break

    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="evidence.registry_searched",
        object_type="source_registry",
        actor_user_id=principal.user_id,
        state_after={
            "query": payload.query[:200],
            "registry": used_registry,
            "results": len(results),
            "failed_registries": failed,
        },
        reason="query text disclosed to an external scholarly registry (§36.2)",
        request_id=principal.request_id,
    )
    return results[: payload.limit]


@router.post("/references/search", response_model=ReferenceSearchResponse)
async def discover_references(
    payload: ReferenceSearchRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ReferenceSearchResponse:
    """اكتشاف المراجع: عنوانٌ أو كلماتٌ مفتاحية أو DOI.

    يفترق عن `/sources/search` في ثلاثة، وكلّها مقصودة:

    **يُسأل الفهرسان معًا** ويُعرض ما قاله كلٌّ منهما منسوبًا إليه. أما
    المسار القديم فيتوقف عند أول فهرسٍ ردّ بشيء، فيرى الباحث نصف ما يعرفه
    العالم عن ورقته ولا يدري أنه نصف.

    **والتعذّر يُعلَن باسم صاحبه.** فهرسٌ لم يجب ليس فهرسًا قال «لا يوجد»؛
    والخلط بينهما يجعل الشاشة تكذب في أسوأ لحظة: حين تكون الشبكة معطوبة
    والباحث يظنّ موضوعه بكرًا فيبني عليه.

    **والنتيجة ليست مرجعًا مخزَّنًا.** لا تُكتب هنا صفوف: الحفظ فعلٌ مستقل
    يقع في المكتبة بمعرّفٍ شرعي، والإضافة إلى بحثٍ فعلٌ ثالث يبقى `saved_only`.

    ويبقى تسجيل الإفصاح كما هو في المسار القديم: نصّ الاستعلام يغادر
    المستأجر إلى طرفٍ ثالث، وقد يحمل عنوان بحثٍ غير منشور (§36.2).
    """
    providers = _discovery_providers()
    result = await discover(
        providers, payload.query, limit=payload.limit,
        year_from=payload.year_from, year_to=payload.year_to,
        work_type=payload.work_type, open_access_only=payload.open_access_only,
    )

    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="evidence.references_discovered",
        object_type="reference_discovery",
        actor_user_id=principal.user_id,
        state_after={
            "query": payload.query[:200],
            "providers": [status_.provider for status_ in result.provider_statuses],
            "failed_providers": [
                status_.provider for status_ in result.provider_statuses if not status_.ok
            ],
            "results": len(result.candidates),
            # الرابط الممنوع جمعه يُسجَّل أنه لم يُطلب — لا أنه طُلب فمُنع.
            "external_link_host": result.external_link.host if result.external_link else None,
        },
        reason="query text disclosed to external scholarly indexes (§36.2)",
        request_id=principal.request_id,
    )

    return ReferenceSearchResponse(
        candidates=[
            ReferenceCandidateView(
                doi=candidate.doi, title=candidate.title, authors=list(candidate.authors),
                year=candidate.year, venue=candidate.venue, volume=candidate.volume,
                issue=candidate.issue, pages=candidate.pages, abstract=candidate.abstract,
                url=candidate.url, open_access=candidate.open_access, type=candidate.type,
                retraction_status=candidate.retraction_status,
                providers=list(candidate.providers),
                citation_counts=candidate.citation_counts,
                match_basis=candidate.match_basis,
                claims=_claim_views(candidate),
                can_be_saved=bool(candidate.doi),
            )
            for candidate in result.candidates
        ],
        providers=[
            ProviderStatusView(provider=status_.provider, ok=status_.ok,
                               detail=status_.detail, results=status_.results)
            for status_ in result.provider_statuses
        ],
        providers_enabled=bool(providers),
        any_provider_failed=result.any_provider_failed,
        all_providers_failed=result.all_providers_failed,
        external_link=(
            ExternalAccessLinkView(url=result.external_link.url, host=result.external_link.host)
            if result.external_link else None
        ),
    )


@router.post("/sources/import", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def import_source(
    payload: SourceImportRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    """TC-02 — DOI لا يُحلّ يعيد خطأً واضحًا، ولا يُخزَّن مصدر مختلق."""
    try:
        record, registry_name = await verification.resolve_doi(_registries(), payload.doi)
    except registry.SourceNotFound as exc:
        raise AtheraError("evidence.doi_not_resolved", status_code=404, doi=payload.doi) from exc

    source = await verification.import_source(
        session, tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
        record=record, registry_name=registry_name,
    )
    return await _source_response(session, source)


@router.post("/sources/{source_id}/verify", response_model=SourceResponse)
async def revalidate_source(
    source_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> SourceResponse:
    source, _changed = await verification.revalidate(
        session, tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
        source_id=source_id, registries=_registries(),
    )
    return await _source_response(session, source)


@router.post("/evidence/excerpts", response_model=ExcerptResponse,
             status_code=status.HTTP_201_CREATED)
async def create_excerpt(
    payload: ExcerptCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ExcerptResponse:
    excerpt = await ledger.add_excerpt(
        session, tenant_id=principal.tenant_id, source_id=payload.source_id,
        quote=payload.quote, locator=payload.locator, actor_user_id=principal.user_id,
    )
    return ExcerptResponse(
        id=excerpt.id, source_id=excerpt.source_id, quote=excerpt.quote,
        locator=excerpt.locator, access_basis=excerpt.access_basis,
    )


@router.get("/claims", response_model=list[ClaimResponse])
async def list_claims(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    project_id: uuid.UUID | None = None,
) -> list[ClaimResponse]:
    query = select(Claim).order_by(Claim.created_at.desc()).limit(200)
    if project_id:
        query = query.where(Claim.project_id == project_id)
    rows = (await session.execute(query)).scalars().all()
    out: list[ClaimResponse] = []
    for claim in rows:
        state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim.id)
        out.append(_claim_response(claim, state, principal.locale))
    return out


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    payload: ClaimCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ClaimResponse:
    claim = Claim(
        tenant_id=principal.tenant_id, project_id=payload.project_id, text_ar=payload.text_ar,
        text_en=payload.text_en, claim_type=payload.claim_type, section=payload.section,
        status="draft",
    )
    session.add(claim)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="evidence.claim_created",
        object_type="claim", object_id=claim.id, actor_user_id=principal.user_id,
        state_after={"claim_type": payload.claim_type, "section": payload.section},
        reason="claim starts as draft with no evidence (§14.4)",
    )
    state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim.id)
    return _claim_response(claim, state, principal.locale)


def _claim_response(claim: Claim, state: ledger.ClaimStatus, locale: str) -> ClaimResponse:
    return ClaimResponse(
        id=claim.id, text=_pick(locale, claim.text_ar, claim.text_en),
        text_ar=claim.text_ar, text_en=claim.text_en, claim_type=claim.claim_type,
        section=claim.section, status=claim.status,
        verification_status=claim.verification_status,
        is_labelled_inference=claim.is_labelled_inference,
        evidence=ClaimStatusResponse(
            claim_id=state.claim_id, status=state.status, direct=state.direct,
            partial=state.partial, contextual=state.contextual, contradictory=state.contradictory,
            unresolved_contradictions=state.unresolved_contradictions,
            retracted_sources=state.retracted_sources, has_evidence_gap=state.has_evidence_gap,
            can_be_final=state.can_be_final,
        ),
    )


@router.post("/claims/{claim_id}/evidence", response_model=ClaimResponse)
async def attach_evidence(
    claim_id: uuid.UUID,
    payload: EvidenceLinkRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ClaimResponse:
    await ledger.link_evidence(
        session, tenant_id=principal.tenant_id, claim_id=claim_id, excerpt_id=payload.excerpt_id,
        support_level=payload.support_level, actor_user_id=principal.user_id,
        retraction_acknowledged=payload.retraction_acknowledged,
        acknowledgement_note=payload.acknowledgement_note,
    )
    claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one()
    state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim_id)
    return _claim_response(claim, state, principal.locale)


@router.post("/claims/{claim_id}/finalize", response_model=ClaimResponse)
async def finalize_claim(
    claim_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ClaimResponse:
    claim = await ledger.finalize_claim(
        session, tenant_id=principal.tenant_id, claim_id=claim_id,
        actor_user_id=principal.user_id,
    )
    state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim_id)
    return _claim_response(claim, state, principal.locale)


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ClaimResponse:
    claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise NotFound("evidence.claim_not_found")
    state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim_id)
    return _claim_response(claim, state, principal.locale)


@router.get("/projects/{project_id}/evidence-ledger", response_model=LedgerResponse)
async def evidence_ledger(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> LedgerResponse:
    claims = (
        await session.execute(select(Claim).where(Claim.project_id == project_id))
    ).scalars().all()

    entries: list[LedgerEntry] = []
    gaps = contradicted = 0
    for claim in claims:
        state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim.id)
        links = (
            await session.execute(
                select(ClaimEvidenceLink).where(ClaimEvidenceLink.claim_id == claim.id)
            )
        ).scalars().all()
        if state.has_evidence_gap:
            gaps += 1
        if state.unresolved_contradictions:
            contradicted += 1
        entries.append(LedgerEntry(
            claim=_pick(principal.locale, claim.text_ar, claim.text_en),
            claim_ar=claim.text_ar, claim_type=claim.claim_type, section=claim.section,
            evidence_ids=[link.excerpt_id for link in links],
            support_levels=[link.support_level for link in links],
            verification_status=claim.verification_status, status=state.status,
            has_evidence_gap=state.has_evidence_gap,
            unresolved_contradictions=state.unresolved_contradictions,
        ))

    return LedgerResponse(
        project_id=project_id, entries=entries, total_claims=len(claims),
        claims_with_gaps=gaps, claims_contradicted=contradicted,
    )
