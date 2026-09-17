"""الأدبيات والأدلة | Literature and evidence API (§35.4، §14).

المصادر تُستورد من سجل خارجي حقيقي أو لا تُستورد. والادعاء بلا دليل يُعلَن
فجوة — لا يُولَّد له مرجع (TC-02).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import tenant_session_maker
from ..deps import (
    Principal,
    get_principal,
    get_project_session,
    get_session,
    project_tenant,
)
from ..discovery import (
    DiscoveryProvider,
    ParsedQuery,
    RankedReference,
    ReferenceCandidate,
    discover,
)
from ..discovery import throttle
from ..errors import AtheraError, NotFound
from ..models.literature import ACCESS_STATES, Author, Claim, ClaimEvidenceLink, Source, SourceAuthor
from ..schemas.discovery import (
    ExternalAccessLinkView,
    ProviderClaimView,
    ProviderStatusView,
    QueryUnderstandingView,
    RankReasonView,
    ReferenceCandidateView,
    ReferenceSearchRequest,
    ReferenceSearchResponse,
    SuggestedTermView,
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
from ..services import audit, idempotency, collaboration, reference_discovery
from ..services.literature import ledger, registry, verification
from ..transaction import TransactionalRoute

router = APIRouter(prefix="/api/v1", tags=["literature"], route_class=TransactionalRoute)
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
    """فهارس الاكتشاف — **من المحوّل وحده، لا من نسخةٍ ثانية هنا**.

    كان القرار مكتوبًا في هذا الملف، ثمّ احتاجته المحادثة. ونسخُه كان
    يجعل الفهرسين مُفعَّلين في شاشة المراجع ومُطفأين في المحادثة بعد أوّل
    تعديل يمسّ واحدةً من النسختين — بلا سببٍ يفهمه الباحث.

    و«بلا فهارس» تبقى حالًا ثالثة تُعلَن لا تُخفى: ليست «لا نتائج» ولا
    «تعذّر فهرس».
    """
    return reference_discovery.enabled_providers()


def _claim_views(candidate: ReferenceCandidate) -> list[ProviderClaimView]:
    return [
        ProviderClaimView(
            provider=claim.provider, provider_id=claim.provider_id, doi=claim.doi,
            title=claim.title, authors=list(claim.authors), year=claim.year,
            venue=claim.venue, volume=claim.volume, issue=claim.issue, pages=claim.pages,
            abstract=claim.abstract, url=claim.url, open_access=claim.open_access,
            citation_count=claim.citation_count, type=claim.type,
            work_type=claim.work_type, retraction_status=claim.retraction_status,
        )
        for claim in candidate.ordered_claims
    ]


def _understanding(parsed: ParsedQuery | None) -> QueryUnderstandingView | None:
    """ما فُهم من السؤال يعود إلى صاحبه ليقارنه بما كتبه.

    وهذا هو الحدّ العملي بين «فهمُ الاستعلام» و«إعادةُ كتابته»: ما دام
    النصّان معروضين معًا، لا يقع تبديلٌ لا يراه الباحث.
    """
    if parsed is None:
        return None
    return QueryUnderstandingView(
        raw=parsed.raw, sent=parsed.sent, doi=parsed.doi, phrase=parsed.phrase,
        authors=list(parsed.authors), year=parsed.year, year_from=parsed.year_from,
        year_to=parsed.year_to, keywords=list(parsed.keywords),
        accepted_terms=list(parsed.accepted_terms),
        suggestions=[
            SuggestedTermView(term=one.term, source_term=one.source_term, kind=one.kind)
            for one in parsed.suggestions
        ],
    )


def _reason_views(ranked: RankedReference) -> list[RankReasonView]:
    """الأسباب وحدها تعبر السلك. الدرجة تبقى داخل الخادم عمدًا (لا نسبة)."""
    return [
        RankReasonView(code=reason.code, kind=reason.kind, terms=list(reason.terms),
                       provider=reason.provider, count=reason.count, year=reason.year)
        for reason in ranked.ranking.reasons
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
    request: Request,
    payload: SourceSearchRequest,
    principal: Principal = Depends(get_principal),
) -> list[SourceCandidate] | JSONResponse:
    """البحث يُسجَّل لأنه إفصاح خارجي.

    نص الاستعلام يغادر المستأجر إلى خدمة طرف ثالث — وقد يحمل عنوان بحث غير
    منشور أو فكرة قيد التطوير. تسجيله واجب تدقيق وخصوصية (§36.2)، لا شكلية.

    **ولا `Depends(get_session)`** (RC-T1-H3): التبعيّةُ تفتح معاملةَ الطلب
    **قبل** أن يعمل المتن، فتبقى حيّةً طوال نداء الفهارس — والاتصالُ
    `idle in transaction` حتى يعود الطرفُ الثالث. ولا قراءةَ قاعدةٍ يحتاجها
    هذا المسار قبل النداء أصلًا: الصلاحيةُ من الرمز، ولا نطاقَ بحثٍ ولا
    مشروع. فالشبكةُ أوّلًا بلا معاملة، ثمّ معاملةٌ قصيرةٌ للتدقيق.
    """
    # ══ تحضيرٌ يُودَع قبل الشبكة (RC-T1-H2-B2) ══
    #
    # وبلا ترويسةٍ يسلك المسارُ مسلكَه القديم حرفيًّا: لا حجزَ ولا إعادة.
    # والأثرُ الخارجيُّ هنا **قراءةٌ**، فإعادتُه عند انتهاء إجارةٍ آمنة —
    # ولا يُقاس على ذلك كتابةُ تخزينٍ ولا نداءُ نموذج.
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)
    guard = await idempotency.begin_leased(
        request, maker, tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id, body=payload.model_dump(mode="json"),
        ttl=idempotency.LEASE_NETWORK)
    if guard.answer is not None:
        return guard.answer

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

    # ── معاملةٌ قصيرةٌ **بعد** الشبكة: الإفصاحُ وقع فيُسجَّل ──
    #
    # **والإنهاءُ والتدقيقُ في معاملةٍ واحدة**: عاملٌ بائتٌ يرفع
    # `LeaseSuperseded` فتُرجَع المعاملةُ ولا يُودَع حدثُ إفصاحٍ لمن فقد
    # إجارتَه.
    answer = results[: payload.limit]
    async with maker() as session:
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
        await idempotency.settle_leased(
            session, guard, status=200, body=jsonable_encoder(answer))
    return answer


@router.post("/references/search", response_model=ReferenceSearchResponse)
async def discover_references(
    request: Request,
    payload: ReferenceSearchRequest,
    principal: Principal = Depends(get_principal),
) -> ReferenceSearchResponse | JSONResponse:
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

    **والترتيب بالصلة المُعلَّلة، لا بالسنة ولا بترتيب وصول الفهارس.** ومع كل
    نتيجة أسبابُ موضعها بلغة الباحث — ولا درجة رقمية في العقد أصلًا، لأن
    رقمًا يعبر السلك يُعرض يومًا نسبةً، وتلك كذبةٌ لا تُسترد.

    **والتوسيع لا يقع إلا بقبولٍ صريح.** الاقتراحات تُعاد في
    `query_understanding.suggestions`، ولا تدخل البحث حتى تعود في
    `accepted_terms` من الواجهة.

    ويبقى تسجيل الإفصاح كما هو في المسار القديم: نصّ الاستعلام يغادر
    المستأجر إلى طرفٍ ثالث، وقد يحمل عنوان بحثٍ غير منشور (§36.2).
    """
    # ══ الترتيب: مَن يُحكَم أوّلًا، الحدُّ أم المفتاح؟ (RC-T1-H2-B2) ══
    #
    # **الحدُّ يحمي الفهرسَين، فلا يُطبَّق على طلبٍ لا يبلغهما.**
    #
    # وكان الحدُّ أوّلًا لكلّ الطلبات، وهو عطبٌ في العقد: طلبٌ مُمفتَحٌ
    # **تَمَّ** كان يُردّ ٤٢٩ بدل أن يُعيد جوابَه المخزَّن — فيُعاقَب عميلٌ
    # يُعيد الطلبَ كما أُمر، على عملٍ لا يُنادي مزوّدًا أصلًا. وكان
    # التوأمُ المردودُ (`in_progress`) والتعارضُ يستهلكان حصّةَ بحثٍ
    # خارجيٍّ لم يقع.
    #
    # فالمفتاحُ — إن وُجد — يُحكَم أوّلًا: إعادةٌ أو رفضٌ أو تعارضٌ تُجاب
    # بلا حدٍّ وبلا مزوّد. ولا يبلغ الحدَّ إلا **إجارةٌ جديدة**، أي عملٌ
    # سيُنادي الفهرسَين حقًّا.
    #
    # **وبلا مفتاحٍ لا يُغيَّر شيء**: الحدُّ كما كان، ولا رحلةَ تحضيرٍ
    # زائدةً إلى قاعدةٍ في مدينةٍ أخرى.
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)
    guard = idempotency.LeaseGuard()
    if idempotency.is_keyed(request):
        guard = await idempotency.begin_leased(
            request, maker, tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id, body=payload.model_dump(mode="json"),
            ttl=idempotency.LEASE_NETWORK)
        if guard.answer is not None:
            return guard.answer

    # **الحدّ قبل النداء الخارجي لا بعده.** كل بحثٍ هنا نداءان إلى فهرسين
    # يمنحاننا الاستعمال بأدبٍ لا بعقد؛ وحلقةُ عميلٍ مندفعة تحرق ائتماننا
    # عندهما فيُحجب مرورنا عن كل المستأجرين لا عن صاحب الحلقة وحده.
    wait = throttle.check((principal.tenant_id, principal.user_id))
    if wait:
        # **إخفاقٌ معلومٌ قبل الخارج**: لم يُنادَ مزوّدٌ، ولا أثرَ غامضًا.
        # فتُسجَّل الإجارةُ `failed` (ودلالتُها القائمةُ تُفرغ السياج)،
        # فيبقى المفتاحُ قابلًا لمحاولةٍ صادقةٍ بعد انقضاء الحدّ — ولا
        # يُترك حجزٌ حيٌّ لعملٍ لن يقع.
        if guard.lease is not None:
            async with maker() as session:
                await idempotency.fail_leased(session, guard.lease,
                                              reason="rate_limited")
        raise AtheraError(
            "evidence.reference_search_rate_limited", status_code=429,
            retry_after_seconds=wait,
        )

    providers = _discovery_providers()
    result = await discover(
        providers, payload.query, limit=payload.limit,
        year_from=payload.year_from, year_to=payload.year_to,
        work_type=payload.work_type, open_access_only=payload.open_access_only,
        accepted_terms=payload.accepted_terms,
    )

    # ── معاملةٌ قصيرةٌ **بعد** نداء الفهرسَين (RC-T1-H3) ──
    # **ويُبنى الجوابُ قبل معاملة الإنهاء**: هو ما يُخزَّن ويُعاد
    # حرفيًّا عند الإعادة، فيجب أن يكون تامًّا قبل أن يُثبَّت.
    answer = ReferenceSearchResponse(
        candidates=[
            ReferenceCandidateView(
                doi=ranked.candidate.doi, title=ranked.candidate.title,
                authors=list(ranked.candidate.authors),
                year=ranked.candidate.year, venue=ranked.candidate.venue,
                volume=ranked.candidate.volume, issue=ranked.candidate.issue,
                pages=ranked.candidate.pages, abstract=ranked.candidate.abstract,
                url=ranked.candidate.url, open_access=ranked.candidate.open_access,
                type=ranked.candidate.type, work_type=ranked.candidate.work_type,
                retraction_status=ranked.candidate.retraction_status,
                providers=list(ranked.candidate.providers),
                citation_counts=ranked.candidate.citation_counts,
                match_basis=ranked.candidate.match_basis,
                claims=_claim_views(ranked.candidate),
                can_be_saved=bool(ranked.candidate.doi),
                reasons=_reason_views(ranked),
                matched_terms=list(ranked.ranking.matched_terms),
                missing_terms=list(ranked.ranking.missing_terms),
            )
            for ranked in result.ranked
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
        query_understanding=_understanding(result.query),
    )
    async with maker() as session:
        await audit.record(
            session,
            tenant_id=principal.tenant_id,
            action="evidence.references_discovered",
            object_type="reference_discovery",
            actor_user_id=principal.user_id,
            state_after={
                "query": payload.query[:200],
                # **ما غادر المستأجر هو `sent` لا `query`.** لو سُجّل نصّ الباحث
                # وحده لبقي المصطلح الذي قبِله خارج السجلّ، والإفصاح يُسجَّل بما
                # أُفصح به فعلًا لا بما قصده صاحبه (§36.2).
                "sent": (result.query.sent[:200] if result.query else payload.query[:200]),
                "accepted_terms": list(payload.accepted_terms),
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
        await idempotency.settle_leased(
            session, guard, status=200, body=jsonable_encoder(answer))
    return answer


@router.post("/sources/import", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def import_source(
    request: Request,
    payload: SourceImportRequest,
    principal: Principal = Depends(get_principal),
) -> SourceResponse | JSONResponse:
    """TC-02 — DOI لا يُحلّ يعيد خطأً واضحًا، ولا يُخزَّن مصدر مختلق.

    **وحلُّ المعرّف يقع بلا معاملة** (RC-T1-H3). وكان ترتيبُ المتن صحيحًا
    أصلًا — الشبكةُ قبل الكتابة — لكنّ `Depends(get_session)` تفتح المعاملةَ
    **قبل** أن يعمل المتن، فتبقى مفتوحةً طوال حلِّ المعرّف عند الفهرس.
    فلا تبعيّةَ جلسةٍ الآن: الشبكةُ أوّلًا، ثمّ معاملةٌ قصيرةٌ تكتب وتُودِع.

    **وإخفاقُ الإيداع بعد النداء لا يُردّ نجاحًا** (RC-T1-H1): الخطأُ يصعد
    من المعالج نفسِه. ونداءُ الفهرس لا يُرجَع — وذاك اتّساقُ الأثر
    الخارجيّ، مفتوحٌ مُعلَن (RC-T1-H2).
    """
    # ══ تحضيرٌ يُودَع قبل حلِّ المعرّف (RC-T1-H2-B2) ══
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)
    guard = await idempotency.begin_leased(
        request, maker, tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id, body=payload.model_dump(mode="json"),
        ttl=idempotency.LEASE_NETWORK)
    if guard.answer is not None:
        return guard.answer

    try:
        record, registry_name = await verification.resolve_doi(_registries(), payload.doi)
    except registry.SourceNotFound as exc:
        # إخفاقٌ **معلوم**: المعرّفُ لا يُحَلّ. فيُسجَّل `failed` ويبقى
        # المفتاحُ قابلًا لإعادةِ محاولةٍ صادقة — ولا يُختلق معنًى لغموض.
        if guard.lease is not None:
            async with maker() as session:
                await idempotency.fail_leased(session, guard.lease,
                                              reason="doi_not_resolved")
        raise AtheraError("evidence.doi_not_resolved", status_code=404, doi=payload.doi) from exc

    # ══ إنهاءٌ ذرّيّ: الطفرةُ والإتمامُ معًا أو لا شيء ══
    #
    # ولو فُقدت الإجارةُ رُفع `LeaseSuperseded` **داخل** الجلسة، فتُرجَع
    # المعاملةُ كلُّها: صفرُ مصادرَ، وصفرُ تدقيقٍ، وصفرُ إتمام.
    async with maker() as session:
        source = await verification.import_source(
            session, tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
            record=record, registry_name=registry_name,
        )
        answer = await _source_response(session, source)
        await idempotency.settle_leased(
            session, guard, status=status.HTTP_201_CREATED,
            body=jsonable_encoder(answer))
        return answer


@router.post("/sources/{source_id}/verify", response_model=SourceResponse)
async def revalidate_source(
    request: Request,
    source_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> SourceResponse | JSONResponse:
    """إعادةُ فحصِ مصدر — **بثلاثة أطوار، والشبكةُ بلا معاملة** (RC-T1-H3).

        (١) معاملةٌ قصيرة : المصدرُ يوجد وله DOI ⇒ يُحمَل DOI **نصًّا**
        (٢) بلا معاملة    : يُسأل الفهرس
        (٣) معاملةٌ قصيرة : يُعاد تحميلُ الصفّ، ثمّ يُثبَّت الفحص

    **ولا صفُّ ORM يعبُر الحدّ**: الصفُّ يموت بموت معاملته. وما يعبُر نصٌّ.

    **وفجوةُ الزمن تُحسب لا تُهمَل**: الحالُ تُقاس على القاعدة وقت الكتابة،
    ومصدرٌ حُذف أثناء الانتظار يردّ ٤٠٤، ومصدرٌ تغيّر معرّفُه يردّ ٤٠٩ —
    فلا يُكتب فحصُ ورقةٍ على ورقةٍ أخرى.
    """
    session_maker = tenant_session_maker(principal.tenant_id, principal.user_id)

    # ── (١) معاملةٌ قصيرة: التفويضُ والقراءةُ ثمّ الحجز ──
    #
    # **والمعرّفُ جزءٌ من معنى الطلب**: الجسمُ فارغٌ هنا، فلولا `source_id`
    # في البصمة لَصار مفتاحٌ واحدٌ يُعيد جوابَ مصدرٍ على مصدرٍ آخر.
    async with session_maker() as session:
        doi = await verification.revalidation_doi(session, source_id=source_id)
        guard = await idempotency.begin_leased_in(
            session, request, tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            body={"source_id": str(source_id)},
            ttl=idempotency.LEASE_NETWORK)
    if guard.answer is not None:
        return guard.answer

    # ── (٢) بلا معاملة: يُسأل الفهرس ──
    record, registry_name = await verification.resolve_doi(_registries(), doi)

    # ── (٣) معاملةٌ قصيرة: يُعاد التحميلُ ثمّ يُثبَّت الفحصُ والإتمام ──
    #
    # وحرّاسُ الفجوة تبقى كما هي: مصدرٌ حُذف ⇒ ٤٠٤، ومعرّفٌ تغيّر ⇒ ٤٠٩.
    # ولا يُطبَّق فحصُ معرّفٍ على حالِ مصدرٍ آخر.
    async with session_maker() as session:
        source, _changed = await verification.apply_revalidation(
            session, tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
            source_id=source_id, record=record, registry_name=registry_name,
            resolved_doi=doi,
        )
        answer = await _source_response(session, source)
        await idempotency.settle_leased(
            session, guard, status=200, body=jsonable_encoder(answer))
        return answer


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


EDIT = "edit_research_content"


async def _claim_gate(session: AsyncSession, principal: Principal, claim: Claim, *,
                      permission: str = collaboration.VIEW_PROJECT) -> None:
    """ادّعاءٌ منسوبٌ إلى بحثٍ **يُحرس بحراسة بحثه**.

    وكان يُقرأ ويُغلق بمعرّفه وحده: فمن عرف معرّفَ ادّعاءٍ في بحثِ زميله
    قرأ نصَّه وأدلّته، **وأغلقه نهائيًّا** (`finalize`) — وذاك قرارٌ علميّ
    لا رجعةَ فيه في سجلّ بحثٍ ليس له.

    و`project_id` يقبل الفراغ: ادّعاءٌ في مكتبة المستأجر لا ينتسب إلى بحث،
    فليس له حدُّ بحثٍ يُحرس به، ويبقى على عزل المستأجر وحده. ولا يُختلق
    له مالكٌ هنا — والحدُّ الناقص يُقال ولا يُسَدّ بتخمين.
    """
    if claim.project_id is None:
        return
    await collaboration.ensure_project_access(
        session, tenant_id=principal.tenant_id, project_id=claim.project_id,
        user_id=principal.user_id, permission=permission,
        not_found_code="evidence.claim_not_found")


async def _claim_or_404(session: AsyncSession, claim_id: uuid.UUID) -> Claim:
    claim = (await session.execute(
        select(Claim).where(Claim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise NotFound("evidence.claim_not_found")
    return claim


@router.get("/claims", response_model=list[ClaimResponse])
async def list_claims(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    project_id: uuid.UUID | None = None,
) -> list[ClaimResponse]:
    query = select(Claim).order_by(Claim.created_at.desc()).limit(200)
    if project_id:
        await collaboration.ensure_project_access(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            user_id=principal.user_id)
        query = query.where(Claim.project_id == project_id)
    else:
        # **قائمةٌ بلا مُرشِّح لا تعني قائمةَ المستأجر كلِّه.** فادّعاءات
        # بحوثِ الزملاء لا تُعرض هنا لمجرّد إغفال المُرشِّح — ويبقى ما لا
        # بحثَ له على عزل المستأجر.
        visible = await collaboration.visible_project_ids(
            session, tenant_id=principal.tenant_id, user_id=principal.user_id)
        query = query.where(or_(Claim.project_id.is_(None),
                                Claim.project_id.in_(visible)))
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
    if payload.project_id is not None:
        await collaboration.ensure_project_access(
            session, tenant_id=principal.tenant_id, project_id=payload.project_id,
            user_id=principal.user_id, permission=EDIT)
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
    await _claim_gate(session, principal,
                      await _claim_or_404(session, claim_id), permission=EDIT)
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
    await _claim_gate(session, principal,
                      await _claim_or_404(session, claim_id), permission=EDIT)
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
    claim = await _claim_or_404(session, claim_id)
    await _claim_gate(session, principal, claim)
    state = await ledger.claim_status(session, tenant_id=principal.tenant_id, claim_id=claim_id)
    return _claim_response(claim, state, principal.locale)


@router.get("/projects/{project_id}/evidence-ledger", response_model=LedgerResponse)
async def evidence_ledger(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> LedgerResponse:
    await collaboration.ensure_project_access(
        session, tenant_id=project_tenant(session, principal), project_id=project_id,
        user_id=principal.user_id)
    claims = (
        await session.execute(select(Claim).where(Claim.project_id == project_id))
    ).scalars().all()

    entries: list[LedgerEntry] = []
    gaps = contradicted = 0
    for claim in claims:
        state = await ledger.claim_status(session, tenant_id=project_tenant(session, principal), claim_id=claim.id)
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
