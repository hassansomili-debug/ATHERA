"""أثيرا AI | The researcher-facing AI entry point (§32، §4، §8).

مسار واحد يخاطبه الباحث. لا اسم أجنت ولا أداة ولا مزوّد يظهر له — «أثيرا
AI» هي الهوية، والتتبّع الداخلي يبقى في `traces` لمن يريده.

وخمسة حدود مفروضة هنا لا موصوفة:
1. **الجهوزية تُقرأ لا تُفترض**: مزوّد بلا مفتاح يردّ `disabled` ولا يحاول.
2. **الملف يُذكر ولا يُقرأ**: مرحلة معالجة المستندات لم تبدأ، فلا يُرسل
   بايت واحد من محتواه إلى المزوّد.
3. **محتوى المستخدم بيانات**: يدخل في دور `user` وحده، ولا مسار يضعه في
   دور `system` — فلا يستطيع نصّ أن ينقض سياسة النزاهة.
4. **القدرات ثلاثٌ لا واحدة** (Wave1-D / D1): اكتشافُ المراجع، وسجلُّ
   الرصد المجدول، وبلوغُ النصّ الكامل — ثلاثةُ أشياء كانت مطويّةً في
   منطقٍ واحد اسمه `literature_online` مشتقٍّ من `LITERATURE_REGISTRY`
   وحده. فكانت المحادثة تقول للباحث «البحث الخارجي غير مفعّل» بينما
   Crossref وOpenAlex يعملان في كل بحثٍ في الشاشة المجاورة. وكانت تقول
   ذلك **للنموذج أيضًا**، فيمتنع عن قدرةٍ قائمة أو يملأ الفراغ باختلاق.
5. **الطلبُ الصريح يُنفَّذ لا يُعاد السؤال عنه** (D2): من قال «ابحث لي في
   الأدبيات» طلب فعلًا. فيُنادى الفهرسان، وتعود المراجع منسوبةً إلى
   قائليها — ولا يُقترح عليه أن يذهب ويبحث بنفسه في شاشةٍ أخرى.
"""
from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ..db import tenant_session_maker
from ..deps import Principal, get_principal
from ..discovery import throttle
from ..errors import AtheraError
from ..models.research import ExtractionRun, FactCandidate, ResearcherMemory
from ..brain.contracts import strip_markup
from ..brain.orchestrator import Orchestrator
from ..providers.gateway import (
    provider_idempotency_capability,
    provider_readiness,
)
from ..schemas.ai import (
    AiAskRequest,
    AiAskResponse,
    AiCapabilities,
    AiCapabilitiesResponse,
    AttachmentState,
    DiscoveredReferenceView,
    ExternalAccessLinkView,
    ProjectContextView,
    ProviderStatusLine,
)
from ..services import (
    ai_capabilities,
    ai_intent,
    ai_policy,
    ai_rate_limit,
    audit,
    collaboration,
    consent,
    idempotency,
    library,
    reference_discovery,
)
from ..transaction import TransactionalRoute

# الأجنت الذي ينفّذ نيّة S5B النصّية. الاسم داخلي ولا يظهر للباحث.
S5B_AGENT = "research_manager"

router = APIRouter(prefix="/api/v1/ai", tags=["athera-ai"], route_class=TransactionalRoute)


def _t(locale: str, ar: str, en: str) -> str:
    return en if locale == "en" else ar


def _capability_view(capabilities: ai_capabilities.Capabilities) -> AiCapabilities:
    return AiCapabilities(
        reference_discovery_available=capabilities.reference_discovery_available,
        reference_discovery_providers=list(capabilities.reference_discovery_providers),
        literature_registry_available=capabilities.literature_registry_available,
        full_text_retrieval_available=capabilities.full_text_retrieval_available,
    )


def _reference_view(found: reference_discovery.DiscoveredReference) -> DiscoveredReferenceView:
    """كلُّ حقلٍ كما قاله فهرسٌ، ونسبتُه معه — ولا حقل يُملأ استنتاجًا (D4)."""
    return DiscoveredReferenceView(
        title=found.title,
        authors=list(found.authors),
        year=found.year,
        venue=found.venue,
        doi=found.doi,
        url=found.url,
        providers=list(found.providers),
        # عدّادُ كلّ فهرسٍ باسمه — ولا مجموع ولا متوسّط.
        citation_counts=dict(found.citation_counts),
        open_access=found.open_access,
        retraction_status=found.retraction_status,
        scope=found.scope,
        # الحفظ في المكتبة يقع بمعرّفٍ شرعي وحده.
        can_be_saved=bool(found.doi),
    )


def _rendered(found: reference_discovery.DiscoveredReference) -> str:
    """مرجعٌ واحد نصًّا للنموذج — **بلا حقلٍ مفقودٍ يُملأ بفراغٍ يُقرأ قيمة**.

    الحقل الذي لم يقله فهرسٌ يُكتب «غير مذكور» صراحةً، فلا يقرأ النموذج
    مكانًا خاليًا فيملأه من عنده. وعدّادُ كل فهرسٍ باسمه، فلا يُدمج رقمان
    في رقمٍ لا يقوله أحد.
    """
    authors = "، ".join(found.authors) if found.authors else "غير مذكور"
    counts = ("، ".join(f"{name}: {value}"
                        for name, value in found.citation_counts.items())
              or "غير مذكور")
    return (
        f"العنوان: {found.title}\n"
        f"المؤلّفون: {authors}\n"
        f"السنة: {found.year if found.year is not None else 'غير مذكورة'}\n"
        f"وعاء النشر: {found.venue or 'غير مذكور'}\n"
        f"DOI: {found.doi or 'غير مذكور'}\n"
        f"الفهارس التي قالته: {'، '.join(found.providers)}\n"
        f"عدّاد الاستشهاد بحسب كل فهرس: {counts}\n"
        f"مدى ما وصلنا منه: {found.scope}"
    )


def _evidence_rows(
    references: list[reference_discovery.DiscoveredReference],
) -> list[dict]:
    """المراجع بوصفها سياقًا يعرفه المنسّق — **لا نصًّا مُلصقًا بالسؤال**.

    وبلا هذا يحجب حاجزُ النزاهة ما جلبناه بأنفسنا: كلُّ DOI ليس في مجموعة
    الأدلة يُعدّ مختلَقًا، فينتهي طلبُ «ابحث لي في الأدبيات» بـ٤٢٢ لأن
    النموذج ذكر معرّفًا أعطيناه إيّاه.

    والمُعرِّف هنا الـDOI نفسه لا معرّفٌ داخليّ: لا صفّ يُكتب، ولا يُوحى
    بأنّ في المكتبة دليلًا لم يُحفظ.
    """
    return [
        {
            "id": found.doi or f"{found.providers[0]}:{found.title[:48]}",
            "doi": found.doi,
            "statement_ar": _rendered(found),
            "source_locator": "، ".join(found.providers),
        }
        for found in references
    ]


def _context_digest(identity: list[dict]) -> str | None:
    """بصمةٌ حتميّةٌ للمعرفةِ المعتمَدةِ من المستند — **ولا نصَّ يُحفظ**.

    فجوابُ النموذجِ يُبنى على ما اعتمده الباحثُ من ملفِّه: حقولٌ وذاكرةٌ
    موثقةٌ بمواضعها. فلو لم تدخل بصمةَ الطلب لكان اعتمادُ حقلٍ جديدٍ أو
    سحبُ توثيقِ آخرَ **لا يُغيّر شيئًا** في نظر المفتاح، فيُعاد جوابٌ
    بُني على معرفةٍ لم تعد قائمة.

    والمحتوى يُختصَر إلى **مُلخَّصٍ لا يُعكَس**: معرّفُ الذاكرة، والحقل،
    وتجزئةُ نصِّها، والموضع، وحالُ التوثيق — مرتَّبةً ترتيبًا قانونيًّا
    فلا يُغيّر ترتيبُ الصفوفِ البصمةَ. ومتنُ بحثِ الباحثِ لا يُخزَّن في
    جدولِ المفاتيح ولا يُرسَل إلى غير موضعه.
    """
    if not identity:
        return None
    canonical = json.dumps(
        sorted(identity, key=lambda row: (row["memory_id"], row["field"])),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.get("/capabilities", response_model=AiCapabilitiesResponse)
async def capabilities(
    principal: Principal = Depends(get_principal),
) -> AiCapabilitiesResponse:
    """ما تستطيعه أثيرا AI الآن — **بلغة الباحث لا بلغة التشغيل** (D8).

    وكانت شاشة أثيرا AI تعرض بطاقات وضع التشغيل كما هي: اسمُ مزوّد النموذج،
    وحالُ تخزين S3، وسقفُ تصنيف البيانات C1. وهذه تشخيصُ بنيةٍ تحتية لمن
    ينشر الخادم، لا للباحث الذي جاء ليكتب ورقة — وعرضُها له يجعل الشاشة
    تبدو لوحةَ عملياتٍ لا سطحَ عمل.

    فما يعود هنا ثلاثُ قدراتٍ وحال، بلا اسم مزوّد ولا سبب تعطيلٍ داخليّ ولا
    رمز تصنيف. وأسماء الفهارس تُعرض لأنها **معلومةٌ علمية** يحتاجها الباحث
    ليعرف نطاق بحثه، لا تفصيلَ بنيةٍ تحتية.
    """
    _name, ready, _reason = provider_readiness()
    caps = ai_capabilities.current()
    return AiCapabilitiesResponse(
        assistant_available=ready,
        **_capability_view(caps).model_dump(),
    )


@router.post("/ask", response_model=AiAskResponse)
async def ask(
    request: Request,
    payload: AiAskRequest,
    principal: Principal = Depends(get_principal),
) -> AiAskResponse | JSONResponse:
    """أثيرا AI — **ولا معاملةَ قاعدةٍ تُمسَك عبر أيّ انتظارٍ خارجيّ** (RC-T1-H3).

    وهذا المسارُ كان ينتظر **مرّتين** ومعاملةُ الطلب حيّة: الفهارسَ الخارجيّة
    (Crossref/OpenAlex) ثمّ النموذج. فصار:

        (١) معاملةٌ قصيرة : وصولُ البحث، والملفُّ المختار، وحالُ الإذن
        (٢) بلا معاملة    : حدُّ المعدّل ثمّ نداءُ الفهارس
        (٣) معاملةٌ قصيرة : تدقيقُ الإفصاح
        (٤) بلا معاملة    : نداءُ النموذج (والمنسّقُ يملك معاملاتِ أثره)

    **والعقدُ العامّ لم يتغيّر**: نفسُ الجسم، ونفسُ الحالات، ونفسُ الحدود،
    ونفسُ سياسةِ التصنيف والإذن، ونفسُ التأصيل.
    """
    locale = principal.locale
    ai_rate_limit.check(principal.tenant_id, principal.user_id)

    provider, ready, reason = provider_readiness()

    # ── القدرات تُقرأ من مصادرها، ثلاثًا لا واحدة ──
    #
    # وكان هنا سطرٌ واحد يقول:
    #     literature_online = os.getenv("LITERATURE_REGISTRY", "offline") != "offline"
    # فيطوي اكتشافَ المراجع في سجلّ الرصد المجدول، ثم يعتذر عن بحثٍ يستطيع
    # إجراءه. والسجلّان مستقلّان تمامًا: الإنتاج يعمل بـ`offline` وفهارسُ
    # الاكتشاف تعمل فيه.
    caps = ai_capabilities.current()

    limitations: list[str] = []
    capabilities: list[str] = []
    actions: list[str] = []

    intent = ai_intent.classify(
        payload.question,
        has_attachment=payload.selected_file is not None,
        has_project=payload.project_id is not None,
    )
    references: list[reference_discovery.DiscoveredReference] = []
    provider_lines: list[ProviderStatusLine] = []
    external_link: ExternalAccessLinkView | None = None
    search_performed = False

    # ── سياقُ البحث الجاري: يُقرأ بمستأجره أو لا يُقرأ ──
    #
    # ومشروعُ مستأجرٍ آخر ٤٠٤ لا «سياقٌ فارغ»: الرد الفارغ يقول للمهاجم إنّ
    # المعرّف صحيح ولا يملكه، و٤٠٤ لا تقول شيئًا.
    project_view: ProjectContextView | None = None
    document_context: list[dict] = []
    pending_fields: list[str] = []
    attachment: AttachmentState | None = None
    context_identity: list[dict] = []
    chat_consent_state: str | None = None
    grant = None
    session_maker = tenant_session_maker(principal.tenant_id, principal.user_id)

    # ═════════ الطورُ (١): قراءاتُ التحضير في معاملةٍ قصيرة ═════════
    #
    # **ولا `Depends(get_session)` في هذا المسار** (RC-T1-H3): كانت معاملةُ
    # الطلب تبقى حيّةً عبر نداء الفهارس **وعبر نداء النموذج** معًا، فيبقى
    # الاتصالُ `idle in transaction` طوالَ الانتظارَين. فصار المسارُ يملك
    # معاملاتِه: قراءاتُ التحضير هنا، ثمّ الشبكةُ بلا معاملة.
    #
    # وما يُحمَل عبر الحدّ قيمٌ عاديّةٌ لا كائناتُ ORM: `ProjectContextView`
    # و`AttachmentState` نموذجانِ من Pydantic، و`document_context` قوائمُ
    # قواميسَ، و`grant` بنيةٌ مجمَّدة. فلا تحميلَ متأخّرٌ بعد إغلاق المعاملة.
    guard = idempotency.LeaseGuard()
    async with session_maker() as session:
        if payload.project_id is not None:
            # والمستأجرُ وحده لم يكن كافيًا: كان سؤالٌ بريء الشكل يعيد عنوانَ
            # بحثِ زميلك وحالَه وبوابتَه لمن يعرف المعرّف — والمحادثةُ أسهل
            # بابٍ يُطرَق. فالبوابةُ المشتركة هنا كما في كلّ مسارٍ يقبل معرّفًا.
            # والرمز المُعرَّف في الكتالوج، لا رمزٌ جديد يُترجَم إلى نفسه:
            # مفتاحٌ غائب يصل الباحث حرفيًّا — `project.not_found` على الشاشة.
            project = (await collaboration.ensure_project_access(
                session, tenant_id=principal.tenant_id,
                project_id=payload.project_id, user_id=principal.user_id)).project
            project_view = ProjectContextView(
                project_id=project.id,
                working_title=(project.working_title_en or project.working_title_ar)
                if locale == "en" else project.working_title_ar,
                status=project.status,
                current_gate=project.current_gate,
            )

        # ── الملف المختار: يُقرأ من **معرفته المعتمَدة** لا من محتواه الخام ──
        #
        # **ولا تصير المحادثة بابًا خلفيًّا.** إرسال مقاطع المستند إلى مزوّد
        # خارجي محكومٌ بإذن C2 في مسار معالجة المستندات؛ فلو قرأت المحادثة
        # المقاطع مباشرةً لالتفّت على ذلك الإذن بسؤالٍ بريء الشكل.
        #
        # فالمحادثة تقرأ ما **اعتمده الباحث بنفسه**: الذاكرة الموثقة المشتقّة من
        # هذا الملف بعينه. وهي معرفته لا محتوى مستنده، وقد مرّت بمراجعته.
        if payload.selected_file is not None:
            # ══ المنحةُ تُفحص، لا المستأجرُ وحده (RC-T1-H2-B4) ══
            #
            # **وكان استعلامًا بالمستأجر والمعرّف.** فزميلٌ في المستأجر
            # نفسِه يعرف معرّفَ ملفٍّ ليست له عليه منحةٌ كان يسأل عنه
            # فيصله ما اعتمده صاحبُه منه. والمحادثةُ أسهلُ بابٍ يُطرَق.
            #
            # فيُقرأ بالحارس المشترك — **قبل** قراءةِ المعرفةِ المعتمَدة
            # وقبل قراءةِ الإذن وقبل أيّ تحكيمِ مفتاح.
            record = await library.owned_file(
                session, tenant_id=principal.tenant_id,
                user_id=principal.user_id, file_id=payload.selected_file,
                action="read")

            rows = (await session.execute(
                select(FactCandidate, ResearcherMemory)
                .outerjoin(ResearcherMemory,
                           ResearcherMemory.id == FactCandidate.resulting_memory_id)
                .where(FactCandidate.tenant_id == principal.tenant_id,
                       FactCandidate.file_id == record.id)
            )).all()

            run = (await session.execute(
                select(ExtractionRun)
                .where(ExtractionRun.tenant_id == principal.tenant_id,
                       ExtractionRun.file_id == record.id)
                .order_by(ExtractionRun.created_at.desc()).limit(1)
            )).scalar_one_or_none()

            for candidate, memory in rows:
                if candidate.status == "approved" and memory is not None \
                        and memory.verification_status == "verified":
                    document_context.append({
                        "field": candidate.field_key,
                        "value": memory.statement_ar,
                        "locator": memory.source_locator,
                    })
                    # **هُويّةٌ لا نصّ**: ما يدخل بصمةَ الطلب مُلخَّصٌ
                    # حتميّ، فلا يُخزَّن متنُ بحثِ الباحث في جدولِ
                    # المفاتيح ولا في وسمِ الحدّ.
                    context_identity.append({
                        "memory_id": str(memory.id),
                        "field": candidate.field_key,
                        "statement": hashlib.sha256(
                            (memory.statement_ar or "").encode("utf-8")).hexdigest(),
                        "locator": memory.source_locator,
                        "verification": memory.verification_status,
                    })
                elif candidate.status == "unverified":
                    pending_fields.append(candidate.field_key)

            # **حالٌ تقرؤها الواجهة، لا نصٌّ تفسّره.** فتبني الزرّ الصحيح بدل
            # أن تترك الباحث ينفّذ التعليمة بنفسه.
            chat_consent_state = await consent.chat_state(
                session, tenant_id=principal.tenant_id, file_id=record.id)
            attachment = AttachmentState(
                file_id=record.id, filename=record.original_filename,
                processing_status=run.status if run is not None else "not_processed",
                consent_state=chat_consent_state,
                approved_facts=len(document_context),
                pending_review=len(set(pending_fields)),
                needs="none",
            )

            if not rows:
                # §10 — يُقال بصدق، ويُعطى الفعل التالي.
                limitations.append(_t(
                    locale,
                    "هذا الملف لم تُقرأ محتوياته بعد.",
                    "This file has not been read yet.",
                ))
                # §10 — ويُعطى الفعل التالي، لا يُترك الباحث أمام «لا أستطيع».
                actions.append(_t(
                    locale, "اطلب «معالجة المستند» من مكتبتك البحثية أولًا.",
                    "Ask for “Process document” in your research library first.",
                ))
                attachment = attachment.model_copy(update={"needs": "process"})
            elif not document_context:
                limitations.append(_t(
                    locale,
                    "قُرئ الملف ولم تعتمد بعد أيًّا من معلوماته، فلا أستطيع الإجابة منه.",
                    "The file was read but you have not approved any of its facts yet, "
                    "so I cannot answer from it.",
                ))
                attachment = attachment.model_copy(update={"needs": "review"})
            else:
                capabilities.append(_t(
                    locale,
                    f"أجيب من {len(document_context)} معلومة اعتمدتَها من هذا الملف.",
                    f"Answering from {len(document_context)} facts you approved from this file.",
                ))
            if pending_fields:
                limitations.append(_t(
                    locale,
                    f"و{len(set(pending_fields))} حقلًا مستخرَجًا ما زال بانتظار مراجعتك.",
                    f"And {len(set(pending_fields))} extracted fields still await your review.",
                ))


        # **والإذنُ يُقرأ هنا** لأنّه قراءةٌ محضة، وموضعُه في المنطق لم يتغيّر:
        # يُستعمل بعد بناء السياسة كما كان. والشرطُ `ready` يُبقي عددَ
        # القراءات كما هو — فمزوّدٌ مُعطَّل كان يرجع قبل أن يقرأه.
        if payload.selected_file is not None and ready and document_context:
            grant = await consent.chat_authorization(
                session, tenant_id=principal.tenant_id,
                file_id=payload.selected_file)

        # ══ الحجزُ **بعد** التفويض وفي معاملته (RC-T1-H2-B4) ══
        #
        # فوصولُ البحثِ والملفِّ والإذنُ كلُّها قُرئت أعلاه؛ فمن لا يملك
        # الحقَّ لا يبلغ هذا السطر. **والإعادةُ ليست تجاوزًا للتفويض**:
        # يُفحص الحقُّ الحاضرُ أوّلًا، ثمّ يُقال إن كان هناك جوابٌ مخزون.
        #
        # والبصمةُ معنى الطلب: السؤالُ، والملفُّ المختار، والبحثُ، واللغة.
        # ولا معرّفَ طلبٍ فيها ولا زمن.
        guard = await idempotency.begin_leased_in(
            session, request,
            tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
            body={
                "question": payload.question,
                "selected_file": (str(payload.selected_file)
                                  if payload.selected_file else None),
                # **ولقطةُ المستندِ معنًى في الطلب لا زينة.** جوابُ النموذج
                # يُبنى على ما اعتمده الباحثُ من هذا الملفّ، فتبدُّلُ
                # المعتمَدِ طلبٌ آخرُ في معناه — ولا يُعاد عليه جوابٌ قديم.
                "document_context_fingerprint": _context_digest(context_identity),
                # وحالُ إذنِ المحادثة كذلك: سُحب الإذنُ فتبدّلت البصمة،
                # فلا يُعاد محتوًى وُلّد تحت إذنٍ زال.
                "chat_consent_state": chat_consent_state,
                "project_id": (str(payload.project_id)
                               if payload.project_id else None),
                "locale": locale,
            },
            ttl=idempotency.LEASE_MODEL)
    if guard.answer is not None:
        # إعادةٌ، أو «قائمٌ لغيرك»، أو تعارضٌ، أو **أثرٌ لا يُعرف** —
        # وكلُّها بصفرِ نداءٍ للنموذج.
        return guard.answer
    # ═════════ الأدبيات: طلبٌ صريح يُنفَّذ، لا إذنٌ يُستأذن عليه ثانيةً ═════════
    #
    # **الباحث الذي قال «ابحث لي في الأدبيات» طلب فعلًا.** فلا يُسأل مرّة
    # ثانية، ولا يُقترح عليه أن يذهب إلى شاشةٍ أخرى ليبحث بنفسه.
    if intent.wants_literature_search and caps.reference_discovery_available:
        # **الحدّ قبل النداء الخارجي لا بعده.** الفهرسان يمنحاننا الاستعمال
        # بأدبٍ لا بعقد، وحلقةُ عميلٍ مندفعة تحرق ائتماننا عندهما فيُحجب
        # مرورنا عن كل المستأجرين لا عن صاحب الحلقة وحده.
        wait = throttle.check((principal.tenant_id, principal.user_id))
        if wait:
            # ولا يسقط السؤال كلّه لأجل الحدّ: يُجاب بلا بحث، ويُقال لماذا
            # ومتى — «حاول لاحقًا» بلا رقمٍ تجعل العميل يعيد فورًا فيطيل حبسه.
            limitations.append(_t(
                locale,
                f"تجاوزتَ حدّ البحث في الفهارس مؤقّتًا؛ أعد المحاولة بعد {wait} ثانية.",
                f"The reference-search rate limit was reached; try again in {wait} seconds.",
            ))
        else:
            result = await reference_discovery.search(payload.question)
            search_performed = True
            references = reference_discovery.references(result)
            provider_lines = [
                ProviderStatusLine(provider=status.provider, ok=status.ok,
                                   results=status.results, detail=status.detail)
                for status in result.provider_statuses
            ]
            if result.external_link is not None:
                # ResearchGate وAcademia: رابطٌ يُحفظ، لا قاعدةُ بياناتٍ تُقرأ.
                external_link = ExternalAccessLinkView(
                    url=result.external_link.url, host=result.external_link.host,
                    verified=result.external_link.verified)

            # **تعذّرُ فهرسٍ يُعلَن باسمه.** فهرسٌ لم يُجب ليس فهرسًا قال «لا
            # يوجد»، والخلط بينهما يجعل الشاشة تكذب في أسوأ لحظة: حين تكون
            # الشبكة معطوبة والباحث يظنّ موضوعه بكرًا فيبني عليه.
            failed = [status.provider for status in result.provider_statuses
                      if not status.ok]
            if failed:
                limitations.append(_t(
                    locale,
                    f"تعذّر بلوغ {'، و'.join(failed)} في هذه المحاولة، فما لديه لم يُعرض — "
                    "وهذا ليس نفيًا لوجود دراسات فيه.",
                    f"{', '.join(failed)} could not be reached on this attempt, so what it "
                    "holds was not shown — that is not evidence of absence.",
                ))

            # **معاملةٌ قصيرةٌ بعد الشبكة، لا معاملةٌ حملتها عبرها** (RC-T1-H3).
            #
            # وموضعُها بعد النداء مقصود: الإفصاحُ **وقع** — نصُّ الاستعلام
            # غادر المستأجرَ إلى طرفٍ ثالث. فيُسجَّل بمعاملةٍ تُودَع الآن،
            # ولا يُعلَّق على نجاحِ نموذجٍ لاحق: إخفاقُ النموذج كان يُرجِع
            # معاملةَ الطلب فيمحو سجلَّ إفصاحٍ حقيقيّ (§36.2).
            async with session_maker() as session:
                await audit.record(
                    session,
                    tenant_id=principal.tenant_id,
                    action="ai.references_discovered",
                    object_type="reference_discovery",
                    actor_user_id=principal.user_id,
                    state_after={
                        # نصّ الاستعلام يغادر المستأجر إلى طرفٍ ثالث، وقد يحمل
                        # عنوان بحثٍ غير منشور — فيُسجَّل الإفصاح (§36.2).
                        "sent": (result.query.sent[:200] if result.query
                                 else payload.question[:200]),
                        "providers": [s.provider for s in result.provider_statuses],
                        "failed_providers": failed,
                        "results": len(references),
                        "intent": intent.kind,
                    },
                    reason=("query text disclosed to external scholarly "
                            "indexes (§36.2)"),
                    request_id=principal.request_id,
                )
            capabilities.append("reference_discovery")

    # ── ما يُقال عن البحث: **مرّة واحدة، وبما وقع فعلًا** (D5، D6) ──
    #
    # ولا تُكدَّس ثلاثة تحذيراتٍ دفاعية: الواحد يُقرأ، والثلاثة تُقرأ اعتذارًا
    # عامًّا فتُتجاهل كلُّها — بما فيها الذي كان يهمّ.
    if search_performed:
        limitations.append(ai_policy.literature_scope_notice(
            locale, caps.reference_discovery_providers))
        if not references:
            actions.append(_t(
                locale,
                "جرّب مصطلحاتٍ أوسع أو مرادفاتٍ إنجليزية، فالفهرسان يفهرسان بلغة النشر.",
                "Try broader terms or English synonyms — the indexes index in the "
                "language of publication.",
            ))
    else:
        limitations.append(ai_policy.no_search_notice(
            locale, discovery_available=caps.reference_discovery_available))

    # ── سؤالٌ لا يُجاب إلا من نصٍّ كامل، ولا نصّ كامل هنا (D7) ──
    #
    # **والملخّصُ ليس الورقة.** واستخراجُ حجم عيّنةٍ أو إجراءٍ إحصائيّ منه
    # اختلاقٌ بلغةٍ واثقة — أخطر من الامتناع، لأنه يُكتب في ورقةٍ تُنشر.
    over_reach_refused = intent.needs_full_text and not document_context
    if over_reach_refused:
        limitations.append(ai_policy.full_text_limit_notice(locale))
        actions.append(_t(
            locale,
            "ارفع النصّ الكامل للدراسة إلى مكتبتك وعالِجه، ثم اسأل عنه.",
            "Upload the study’s full text to your library, process it, then ask about it.",
        ))

    # ── الجهوزية تُقرأ لا تُفترض ──
    #
    # **والبحثُ لا يحتاج نموذجًا.** فمزوّدٌ غير مضبوط يمنع التوليد ولا يمنع
    # اكتشافَ المراجع؛ وإخفاءُ ما وُجد فعلًا لأن النموذج مطفأ حجبُ عملٍ تمّ.
    if not ready:
        disabled = AiAskResponse(
            answer=_t(
                locale,
                "تنفيذ أثيرا AI غير مُفعَّل بعد: لم يُضبط مزوّد نموذج على الخادم. "
                "وما يعمل اليوم بلا نموذج: الاستخراج الحتمي، وفحوص الاتساق، ومطابقة المجلات.",
                "ATHERA AI execution is not activated yet: no model provider is configured on the server. "
                "What works today without a model: deterministic extraction, consistency checks, and journal matching.",
            ),
            status="disabled",
            evidence_state="search_results" if references else "none",
            limitations=limitations + [_t(locale, f"سبب التعطيل: {reason}", f"Reason: {reason}")],
            recommended_next_actions=actions + [_t(
                locale, "اضبط مزوّد النموذج ومفتاحه في أسرار الخادم.",
                "Configure the model provider and its key in the server secrets.",
            )],
            attachment=attachment,
            intent=intent.kind,
            search_performed=search_performed,
            capabilities=_capability_view(caps),
            references=[_reference_view(found) for found in references],
            provider_statuses=provider_lines,
            external_link=external_link,
            project=project_view,
        )
        # ══ وجيلٌ حُجز لا يُترك عالقًا (RC-T1-H2-B4) ══
        #
        # **وكان يُترك.** هذا مسلكٌ طرفيٌّ **بعد** الحجز وقبل النموذج:
        # مزوّدٌ غيرُ مضبوط. فكان الصفُّ يبقى `in_progress` بلا وسمٍ ولا
        # إتمام — فيُردّ صاحبُه ٤٠٩ إلى أن تنقضي الإجارةُ على عملٍ لم
        # يُنفَّذ أصلًا ولا غموضَ فيه.
        #
        # فيُثبَّت الجوابُ المُعطَّلُ نفسُه: إعادةٌ لاحقةٌ تُعيده حرفيًّا،
        # **وصفرُ نداءٍ للنموذج**.
        if guard.lease is not None:
            async with session_maker() as session:
                await idempotency.settle_leased(
                    session, guard, status=200, body=jsonable_encoder(disabled))
        return disabled

    # ── الاستدعاء عبر المنسّق: هو الطبقة المعمارية، والبوابة تحته ──
    #
    # **بلا أدوات في هذه المرحلة.** والقرار ليس تبسيطًا: أداة الذاكرة تصنيفها
    # C2، وسقف الإرسال الخارجي C1. فاستدعاؤها هنا كان يعني إمّا رفع السقف —
    # وهو إضعاف عام مرفوض — أو إرسال محتوى بحثي حسّاس. وS5B نصّي فقط: لا
    # ذاكرة موثقة، ولا ملفات، ولا بحث خارجي، ولا سياق مستأجر آخر.
    #
    # ونداء نموذج **واحد**: الموجّه لا يمسّ البوابة، والمنسّق وحده يستدعيها.
    notice = ai_policy.capability_notice(locale, capabilities=caps)
    policy = ai_policy.system_prompt(locale)
    if notice:
        policy = f"{policy}\n\n{notice}"
    if references:
        # **التعليمة في `system`، والبيانات في `user`.** نصُّ الفهرس محتوًى
        # غير موثوق (§33.3) ولا يدخل تعليمات النظام؛ والقيدُ عليه قولُنا نحن.
        policy = f"{policy}\n\n{ai_policy.search_results_instruction(locale)}"
    if over_reach_refused:
        # الحدّ يُبلَّغ النموذج نفسه، لا يُلحق بالرد بعد وقوع التجاوز:
        # منعُ الاختلاق عند مصدره أرخص من كشفه بعد أن يُكتب.
        policy = f"{policy}\n\n{ai_policy.full_text_limit_notice(locale)}"
    if project_view is not None:
        # **ولا يُرسل عنوان البحث ولا حالته إلى المزوّد.** عنوانُ بحثٍ غير
        # منشور معرفةٌ بحثية للباحث، وسقفُ الإرسال العام C1. فالسياق يُؤطَّر
        # بلا تعريف، ويبقى العنوان في الرد إلى صاحبه وحده.
        policy = f"{policy}\n\n" + _t(
            locale,
            "الباحث يعمل داخل بحثٍ قائم في المنصّة؛ أطّر جوابك بوصفه إسهامًا في "
            "بحثٍ جارٍ، ولا تفترض عنوانه ولا مرحلته.",
            "The researcher is working inside an existing project; frame your answer "
            "as a contribution to work in progress, and do not assume its title or stage.",
        )

    # **معرفة الملف المعتمَدة تُرسل بوصفها سياقًا، لا سؤالًا.**
    #
    # وتصنيفها C2: معرفة بحثية غير منشورة اعتمدها الباحث. فالسقف يُرفع
    # **لهذا النداء وحده** حين يوجد سياق مستند، ويبقى C1 فيما عداه — ولا
    # يُرفع السقف العام بحال.
    question = payload.question
    classification = "C1"
    if document_context:
        # §13 — **الإذن أولًا.** معرفةُ الباحث المعتمَدة تصنيفها C2، والسقف
        # العام C1. فلولا إذنٌ مسمّى لصارت المحادثة بابًا خلفيًّا: سؤالٌ
        # بريء الشكل يُخرج ما يمنع الإذنُ إخراجَه.
        #
        # **والقراءةُ وقعت في الطور (١)**، ولا تُعاد هنا: إعادتُها على جلسةٍ
        # أُغلقت معاملتُها تقرأ بلا سياق مستأجر — و`SET LOCAL` مات معها —
        # فتردّ RLS صفرَ صفوفٍ فيُقرأ ذلك «لا إذن». والقرارُ هنا على القيمة
        # التي قُرئت بسياقها، لا على قراءةٍ ثانيةٍ عمياء.
        if grant is None:
            document_context = []
            limitations.append(_t(
                locale,
                "الإجابة من هذا المستند تحتاج إذنك الصريح — يُرسَل ما اعتمدتَه "
                "منه وحده، لا نصّه.",
                "Answering from this document needs your explicit consent — only "
                "the facts you approved would be sent, not its text.",
            ))
            actions.append(_t(
                locale, "اسمح لأثيرا بالإجابة من هذا المستند.",
                "Allow ATHERA to answer from this document.",
            ))
            if attachment is not None:
                attachment = attachment.model_copy(update={"needs": "chat_consent"})

    if document_context:
        classification = "C2"
        facts = json.dumps(document_context, ensure_ascii=False)
        # `question` لا `payload.question`: ما أُضيف قبله (مراجعُ بحثٍ جرى)
        # يبقى، ولا يُمحى بإسنادٍ يبدأ من الصفر.
        question = (
            f"{question}\n\n"
            "أجب من هذه المعلومات المعتمَدة من مستند الباحث وحدها:\n"
            f"{facts}\n\n"
            "وما لا تجده فيها قل إنه غير موجود في المستند — ولا تُكمله من "
            "معرفتك. وميّز صراحةً بين ما ورد في المعلومات وبين أي اقتراح منك."
        )

    # ═════════ الطورُ (٣): النموذجُ **بلا معاملةٍ مفتوحة** ═════════
    #
    # والمنسّقُ يملك معاملاتِه: تحضيرٌ قصير، ثمّ الشبكةُ بلا معاملة، ثمّ أثرٌ
    # قصيرٌ بحالٍ نهائيّة. ولا صفَّ `running` يُترك معلَّقًا.
    # ══ الحدُّ يقف حيث هو، لا حيث يبدأ المعالج (RC-T1-H2-B4) ══
    #
    # **وكان التدوينُ هنا، وذاك مُبكّر.** فبعده في المنسّق عملٌ محليٌّ قد
    # يُردّ قبل أيّ نداءٍ: سياسةُ الأدوات، وتنفيذُها، وبناءُ الطلب، ثمّ
    # `gateway.authorize`. فوسمٌ يُكتب هنا يقول «عبَرنا» وقد رُدّ الطلبُ
    # على أداةٍ ممنوعةٍ أو تصنيفٍ مرفوض — فيُحرَم صاحبُه إعادةً مشروعة.
    #
    # فالمُعلَّقُ يُمرَّر، والمنسّقُ ينادِيه بعد التفويض وقبل `invoke`.
    boundary = idempotency.ModelBoundary(
        session_maker, guard, provider=provider,
        capability=provider_idempotency_capability())

    try:
        result = await Orchestrator().run_agent_detached(
            session_maker,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            agent_key=S5B_AGENT,
            question=question,
            tool_calls=[],
            input_classification=classification,
            grant=grant,
            extra_system=policy,
            output_locale=locale,
            evidence_context=_evidence_rows(references),
            before_provider_call=(boundary if guard.lease is not None
                                  else None),
        )
    except AtheraError:
        # **وإخفاقُ إيداعٍ لا يُترجَم إلى «تعذّر المزوّد»** (RC-T1-H1).
        #
        # وهذا الفرعُ كان قائمًا لأخطاء المنصّة المُصنَّفة، وصار يحمل معنًى
        # أثقل: `db.commit_failed` هو `AtheraError` أيضًا، فيمرّ من هنا خطأً
        # مُصنَّفًا. ولو سقط في الفرع العامّ أدناه لصار جوابُ الإخفاق ٢٠٠
        # «تعذّر الوصول إلى مزوّد النموذج» — أي **نجاحٌ كاذبٌ على كتابةٍ لم
        # تُودَع**، وهو بعينه ما أغلقه RC-T1-H1.
        raise
    except Exception as exc:  # noqa: BLE001 — يُترجم لا يُسرَّب
        async with session_maker() as session:
            await audit.record(
                session, tenant_id=principal.tenant_id,
                action="ai.provider_failed",
                object_type="ai_request", object_id=uuid.uuid4(),
                actor_user_id=principal.user_id,
                state_after={"provider": provider,
                             "error_type": type(exc).__name__,
                             # **ولا يُقال «لم يُنفَّذ» لمن عبَر الحدّ.**
                             "external_effect": ("unknown" if guard.lease is not None
                                                 else "not_attempted")},
                request_id=principal.request_id,
            )
        # ══ وطلبٌ مُمفتَحٌ عبَر الحدَّ لا يُقال له «لم يُولَّد شيء» ══
        #
        # **وكانت تُقال.** الجوابُ كان ٢٠٠ ونصُّه: «لم يُولَّد أي محتوى، ولم
        # يُحفظ شيء» — وهي **دعوى واقعٍ كاذبةٌ بعد مهلة**: النموذجُ قد ولّد
        # وحُوسِبنا ثمنَه، والذي انقطع هو السلكُ لا التوليد.
        #
        # فمن حجز جيلًا وعبَر الحدَّ يُردّ ٤٠٩ صادقة: قد يكون نُفِّذ، ولا
        # يُعاد تلقائيًّا بالمفتاح نفسِه. ومن لا مفتاحَ له يبقى جوابُه كما
        # كان — لكن بلا تلك الجملة: ما لا نعرفه لا نُخبر به.
        # **وما رُدّ قبل الحدِّ ليس غامضًا.** أداةٌ مُنعت، أو تصنيفٌ رُفض،
        # أو تفويضُ مزوّدٍ سقط محليًّا — كلُّها **قبل** أيّ نداء. فيُغلَق
        # المفتاحُ إخفاقًا معلومًا ويبقى قابلًا لإعادةٍ صادقة.
        if guard.lease is not None and not boundary.crossed:
            await idempotency.close_pre_external(
                session_maker, guard, reason=f"pre_external:{type(exc).__name__}")
        elif guard.lease is not None:
            from ..errors import athera_error_handler  # noqa: PLC0415

            return await athera_error_handler(
                request, idempotency.ExternalResultUnknown())
        return AiAskResponse(
            answer=_t(
                locale,
                "تعذّر الوصول إلى مزوّد النموذج الآن، ولا سبيل إلى تأكيد ما إذا "
                "كان الطلب قد نُفِّذ عنده. ولم يُحفظ شيء عندنا.",
                "The model provider could not be reached, and we cannot confirm "
                "whether it processed the request. Nothing was saved on our side.",
            ),
            status="provider_error",
            # **وما وُجد فعلًا لا يُخفى لأن النموذج تعذّر.** البحثُ جرى،
            # والمراجع عادت من فهارس؛ وحجبُها هنا يبدّد عملًا تمّ ويُلقي
            # الباحث في شاشةٍ فارغة بلا سبب.
            evidence_state="search_results" if references else "none",
            limitations=limitations,
            recommended_next_actions=actions + [
                _t(locale, "أعد المحاولة بعد قليل.", "Try again shortly.")],
            intent=intent.kind,
            search_performed=search_performed,
            capabilities=_capability_view(caps),
            references=[_reference_view(found) for found in references],
            provider_statuses=provider_lines,
            external_link=external_link,
            project=project_view,
        )

    answer = result.answer
    if answer is None:
        return AiAskResponse(
            answer=_t(locale, "لم تُنتَج إجابة.", "No answer was produced."),
            status="provider_error",
            evidence_state="search_results" if references else "none",
            limitations=limitations,
            intent=intent.kind,
            search_performed=search_performed,
            capabilities=_capability_view(caps),
            references=[_reference_view(found) for found in references],
            provider_statuses=provider_lines,
            external_link=external_link,
            project=project_view,
        )

    capabilities.append("model_reasoning")

    # ما لم يجد النموذج له سندًا يُعلَن حدًّا لا يُبتلع في النصّ.
    limitations.extend(answer.unsupported_claims)
    limitations.extend(answer.evidence_gaps)

    answer_body = AiAskResponse(
        answer=strip_markup(
            (answer.answer_en or answer.answer_ar) if locale == "en"
            else answer.answer_ar),
        status="ok",
        # بلا أدوات فلا استشهاد مسنود: اقتراح نموذج، لا دليل (§7.4).
        # §12 — إجابةٌ من معرفةٍ اعتمدها الباحث ليست اقتراح نموذج، وتُقال
        # كذلك. وما لا سند له يبقى `model_suggestion` مهما بدا واثقًا.
        #
        # **ونتيجةُ بحثٍ ليست دليلًا موثَّقًا** (D4): مرجعٌ وجده فهرسٌ لم
        # يقرأه أحد ولم يُعتمد في هذا البحث، فله حالُه الثالثة — لا يُرفع
        # إلى «مسنود» ولا يُخفض إلى «اقتراح نموذج».
        #
        # و`and not references` ليست تزيّدًا: المراجع المكتشَفة تدخل سياق
        # المنسّق ليعرفها الحاجز، فيستطيع النموذج أن يُخرج `citations`
        # تشير إليها. وبلا هذا الشرط تصير نتيجةُ بحثٍ «مسنودة بدليل موثّق»
        # على شاشة الباحث — وهي أخطر كذبةٍ يمكن أن تقولها هذه الطبقة.
        evidence_state=("verified" if (answer.citations or document_context)
                        and not references
                        else "search_results" if references
                        else "model_suggestion"),
        capabilities_used=capabilities,
        limitations=limitations,
        recommended_next_actions=actions + [
            _t(locale, "راجع الاقتراح واعتمد ما تريد إدخاله في مشروعك.",
               "Review the proposal and approve what you want to enter into your project."),
        ],
        attachment=attachment,
        model_run_id=result.model_run_id,
        intent=intent.kind,
        search_performed=search_performed,
        capabilities=_capability_view(caps),
        references=[_reference_view(found) for found in references],
        provider_statuses=provider_lines,
        external_link=external_link,
        project=project_view,
    )

    # ══ إنهاءٌ ذرّيّ: الجوابُ يُثبَّت في معاملةٍ قصيرة (RC-T1-H2-B4) ══
    #
    # **والبائتُ يُرجَع لا يُبلَّغ**: عاملٌ فقد إجارتَه يرفع
    # `LeaseSuperseded` داخل المعاملة فتُرجَع، فلا يُودَع إتمامٌ لجيلٍ
    # صار لغيره. وبلا مفتاحٍ لا شيءَ يُثبَّت — المسلكُ القديم حرفيًّا.
    if guard.lease is not None:
        async with session_maker() as session:
            await idempotency.settle_leased(
                session, guard, status=200, body=jsonable_encoder(answer_body))
    return answer_body
