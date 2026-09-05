"""الرسائل وفرص النشر | Thesis-to-papers API (§35.7، §23، §24).

المسار كله محكوم بقاعدتين:
  • الفرصة تُحلَّل بلا حقوق، ولا **تتقدم** بلا اعتمادها (TC-06).
  • تنبيه التجزئة يمنع تحويل فرصتين مستقلتين بلا حسم بشري (TC-05).
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.portfolio import ResearchProject
from ..models.research import ResearcherProfile
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
    ConsentRequest,
    DimensionResponse,
    GateStatusResponse,
    MineResponse,
    OpportunityResponse,
    OverlapMatrixResponse,
    OverlapPairResponse,
    ParseResponse,
    PublicationMapResponse,
    RemovalDependency,
    RemovalPreviewResponse,
    RemovalResponse,
    ThesisCardActions,
    ThesisCreateRequest,
    ThesisResponse,
)
from ..services import audit
from ..services.parsing import NoTextLayer, UnsupportedDocument, parse
from ..services.thesis import (
    aging,
    card_actions,
    miner,
    overlap,
    processing,
    removal,
    rights,
    vocab,
)

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
    # اسمُ الملفّ يُقرأ حين يوجد ملفّ وحده — رحلةٌ واحدة في مسارٍ نادر، ولا
    # تُقرأ في مسار التسجيل اليدوي الذي لا ملفّ فيه.
    filename = None
    if payload.file_id is not None:
        filename = (await session.execute(
            select(File.original_filename).where(
                File.id == payload.file_id, File.tenant_id == principal.tenant_id)
        )).scalar_one_or_none()
    return _card(thesis, principal.locale, source_filename=filename,
                 sections=0, opportunities=0, results=0)


async def _thesis_or_404(
    session: AsyncSession, principal: Principal, thesis_id: uuid.UUID, *,
    lock: bool = False,
) -> Thesis:
    statement = select(Thesis).where(
        Thesis.id == thesis_id, Thesis.tenant_id == principal.tenant_id)
    if lock:
        statement = statement.with_for_update()
    thesis = (await session.execute(statement)).scalar_one_or_none()
    if thesis is None:
        # **رسالةُ مستأجرٍ آخر غير موجودة، لا «ممنوعة»** — و٤٠٤ لا تُفشي
        # أنّ المعرّف قائمٌ عند غيرك.
        raise NotFound("thesis.not_found")
    return thesis


def _preview_response(
    view: removal.RemovalPreview, locale: str, *, source_file_id: uuid.UUID | None,
) -> RemovalPreviewResponse:
    def _row(dep: removal.Dependency) -> RemovalDependency:
        return RemovalDependency(key=dep.key, label=removal.label(dep.key, locale),
                                 count=dep.count, blocking=dep.blocking)

    return RemovalPreviewResponse(
        thesis_id=view.thesis_id,
        removable=view.removable,
        dependencies=[_row(dep) for dep in view.dependencies],
        blocking=[_row(dep) for dep in view.blocking],
        explanation=view.explanation(locale),
        source_file_id=source_file_id,
    )


@router.get("/theses/{thesis_id}/removal-preview", response_model=RemovalPreviewResponse)
async def removal_preview(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> RemovalPreviewResponse:
    """**ما يقوم على هذه الرسالة — قبل أن يُسأل «أمتأكّد؟»، لا بعده.**

    سؤالُ التأكيد بلا هذا الجواب زينةٌ: الباحث يُقرّ بما لا يعرفه. فيُحسب
    الأثرُ أوّلًا ويُعرض بأسمائه وأعداده، ثمّ يُسأل.
    """
    thesis = await _thesis_or_404(session, principal, thesis_id)
    view = await removal.preview(
        session, tenant_id=principal.tenant_id, thesis_id=thesis_id,
        file_id=thesis.file_id)
    return _preview_response(view, principal.locale, source_file_id=thesis.file_id)


@router.delete("/theses/{thesis_id}", response_model=RemovalResponse)
async def remove_thesis(
    thesis_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> RemovalResponse:
    """يُزيل سجلَّ الرسالة من مركز الرسائل — **أو يرفض ويقول لماذا**.

    **ولا حذفٌ متسلسلٌ صامت.** `ON DELETE CASCADE` قائمٌ في القاعدة على
    خمسة جداول، وفيها فرصُ النشر — ومنها تتدلّى اتفاقاتُ التأليف واعتماداتُ
    الحقوق والمشاريع المحوَّلة. فإسقاطُ صفٍّ واحد هنا يمحو سلسلةَ قراراتٍ
    بشريّة بلا أن يراها أحد. فتُحسب التبعات أوّلًا:

      • **ما تُعيده قراءةٌ ثانية لا يمنع** — أقسامٌ ونتائجُ كتبتها آلة.
      • **وما فيه حكمُ إنسانٍ يمنع** — ويُردّ الطلب بـ409 ومعه المعاينة.

    **والقفلُ ليس زخرفًا**: بين حساب التبعات وإسقاط الصفّ نافذةٌ قد تُكتب
    فيها فرصةٌ جديدة، فيقع الحذفُ على حالٍ لم تُفحص. فيُقفل صفُّ الرسالة
    قبل الحساب، وهو الصفُّ نفسه الذي يقفله التنقيب.

    **ولا يُمسّ ملفُّ المكتبة، ولا يُمحى كائنُ تخزينٍ نهائيًّا.** نقلُ
    الملفّ إلى السلّة فعلٌ آخر بنقطةٍ أخرى (`POST /files/{id}/trash`)،
    يطلبه الباحث وحده. **وسجلُّ التدقيق يبقى**: `audit_log.object_id` بلا
    مفتاحٍ أجنبيّ إلى `theses` قصدًا، فتاريخُ ما جرى يبقى مقروءًا بعد
    إسقاط الصفّ.
    """
    thesis = await _thesis_or_404(session, principal, thesis_id, lock=True)
    file_id = thesis.file_id
    view = await removal.preview(
        session, tenant_id=principal.tenant_id, thesis_id=thesis_id, file_id=file_id)

    if not view.removable:
        await audit.record(
            session, tenant_id=principal.tenant_id, action="thesis.removal_refused",
            object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
            state_after={"blocking": view.blocking_counts()},
            reason="removal refused: scientific work decided by a human rests on this "
                   "thesis; nothing is cascade-deleted silently",
        )
        raise AtheraError("thesis.removal_blocked", status_code=409,
                          **{k: v for k, v in view.blocking_counts().items()})

    dropped = {key: count for key, count in view.counts().items() if count}
    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.removed",
        object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
        state_before={"processing_state": thesis.processing_state,
                      "file_id": str(file_id) if file_id else None},
        state_after={"dropped": dropped, "library_file_touched": False},
        reason="the thesis carried no human decision; its record and the machine output "
               "under it are dropped, the library file is untouched and the audit stays",
    )
    # الشرطان معًا: المعرّف **والمستأجر**. و`tenant_session` تختم المعاملة —
    # ولا يختم الموجّه معاملةً لا يملكها.
    await session.execute(
        delete(Thesis).where(Thesis.id == thesis_id,
                             Thesis.tenant_id == principal.tenant_id))
    return RemovalResponse(thesis_id=thesis_id, removed=True, dropped=dropped)


async def _remember_failure(
    principal: Principal, thesis_id: uuid.UUID, *, state: str, code: str,
    detail: str, action: str, reason: str, text_layer: str | None = None,
) -> None:
    """يكتب سببَ الفشل **في معاملةٍ مستقلّة تنجو من رفض الطلب**.

    **وهذا ليس زخرفًا.** `tenant_session` تفتح معاملةَ الطلب وتُرجعها عند
    أيّ استثناء؛ فكتابةُ الحال في معاملة الطلب ثمّ رفعُ ٤٢٢ تمحو الكتابة
    وتُبقي الرسالة على حالها القديمة — والباحث يرى رسالة خطأٍ عابرة، ثم
    يُحدّث الصفحة فتقول له البطاقة «٠ أقسام» بلا سبب. **وهو العطب بعينه.**

    فتُفتح جلسةٌ ثانية قصيرة تكتب الحال والتدقيق وتُودِع، ثمّ يُرفع الخطأ.
    والموجّه لا يختم معاملةً لا يملكها: `tenant_session` هي التي تختم
    معاملتها هي، وهو النمط نفسه المستعمل في `_process` لتسجيل فشلٍ بعد
    سقوط معاملةٍ أخرى.

    **ولا تُنقل هنا رسالةُ استثناءٍ تحمل نصّ المستند**: الرمز صنفُ العطب،
    والتفصيل صنفُ الاستثناء ورسالته مقصوصة — وكلاهما تشغيليّ لا محتوًى.
    """
    from ..db import tenant_session  # noqa: PLC0415 — يتجنّب استيرادًا دائريًا

    async with tenant_session(principal.tenant_id, principal.user_id) as failure:
        await processing.mark(
            failure, tenant_id=principal.tenant_id, thesis_id=thesis_id,
            state=state, failure_code=code, failure_detail=detail[:500],
            text_layer=text_layer)
        await audit.record(
            failure, tenant_id=principal.tenant_id, action=action,
            object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
            state_after={"processing_state": state, "failure_code": code,
                         "ocr_state": processing.OCR_UNAVAILABLE},
            reason=reason,
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
    except NoTextLayer as exc:
        # **مستندٌ ممسوح ضوئيًّا يُسمَّى باسمه، ولا يُترك «نوعًا غير مدعوم».**
        await _remember_failure(
            principal, thesis_id, state=processing.TEXT_LAYER_MISSING,
            code="text_layer_missing", detail=str(exc),
            text_layer=processing.TEXT_LAYER_ABSENT,
            action="thesis.text_layer_missing",
            reason="scanned document detected; OCR is not available and none was performed")
        raise AtheraError("thesis.retry_needs_ocr", status_code=422,
                          detail=str(exc)) from exc
    except UnsupportedDocument as exc:
        await _remember_failure(
            principal, thesis_id, state=processing.FAILED,
            code="unsupported_document", detail=f"{type(exc).__name__}: {exc}",
            action="thesis.parse_failed",
            reason="the parser cannot read this file type; the reason is recorded, not swallowed")
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

    # **تفكيكٌ نجح يُثبت أنّ طبقة النصّ موجودة** — فتُكتب، ولا تبقى
    # «لم تُفحص». وإن كانت الرسالة موسومةً بفشلٍ سابق فقد بطل وسمُه: صفٌّ
    # يقول «تعذّرت القراءة» وقد قُرئ للتوّ تناقضٌ يُقرأ في الشاشة كذبًا.
    # وما عدا ذلك تبقى الحال كما هي — **ولا تُقفز بوابة الإذن من هنا**:
    # DIC2 حدٌّ مستقلّ لا يُمنَح بأثرٍ جانبي لعمليةٍ أخرى.
    settled = (processing.READY_FOR_REVIEW
               if thesis.processing_state in (*processing.FAILURE_STATES,
                                              processing.UPLOADED)
               else thesis.processing_state)
    await processing.mark(
        session, tenant_id=principal.tenant_id, thesis_id=thesis_id,
        state=settled, text_layer=processing.TEXT_LAYER_PRESENT)

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
    """§23.4 + §23.8 — التنقيب يسبقه حساب الأعمار وإعلانها.

    ## **والعطب الذي يُصلَح هنا: تنقيبٌ يُضاعف نفسه بكل ضغطة**

    كانت الحلقة `for draft in drafts: session.add(PublicationOpportunity(…))`
    بلا فحصِ وجود، ولا قيدَ تفرّدٍ في القاعدة يحرسها. والمنقّب حتميّ: يُعطى
    المدخلات نفسها فيُخرج المقترحات نفسها حرفًا بحرف. فضغطتان على الزرّ
    تكتبان الفرصة مرّتين، وثلاثٌ ثلاثًا — ثمّ تُقارَن الفرصةُ بنفسها في
    مصفوفة التداخل (§23.7) فيرتفع **تنبيهُ تجزئةٍ كاذب** على ورقةٍ واحدة
    مكرّرة، ويُطلب من الباحث حسمٌ بشريّ في تعارضٍ صنعته ضغطةٌ مكرّرة.

    **فالتنقيب صار مُعادًا بلا أثر (idempotent):**

      ١ صفُّ الرسالة يُقفل بـ`FOR UPDATE` **في القراءة نفسها** — بلا رحلةٍ
        إضافية. فطلبان متزامنان يتسلسلان: الثاني ينتظر ختمَ الأوّل، ثمّ
        يقرأ الفرص بلقطةٍ جديدة تشمل ما كتبه الأوّل فيتخطّاه. ولولا القفل
        لقرأ الاثنان «لا شيء» معًا وكتبا معًا.
      ٢ ومفتاحُ الهويّة `(opportunity_kind, paper_kind, working_title_ar)` —
        وهو ما يُنتجه المنقّب حتميًّا من عناصر الرسالة.
      ٣ والمقترحاتُ المكرّرة **داخل التشغيلة الواحدة** تُطوى أيضًا: سؤالان
        متطابقان في الرسالة كانا يُنتجان صفّين متطابقين.

    **ولا قيدَ تفرّدٍ في القاعدة يُضاف هنا** — الترقيم `0030` مملوكٌ لموجةٍ
    أخرى، وإضافةُ ترحيلٍ منافس تكسر الترتيب. والقفلُ يحرس ما كان القيدُ
    سيحرسه على هذا المسار؛ ويبقى القيد عملًا مؤجَّلًا مذكورًا في نصّ الطلب.
    """
    thesis = (await session.execute(select(Thesis).where(
        Thesis.id == thesis_id, Thesis.tenant_id == principal.tenant_id
    ).with_for_update())).scalar_one_or_none()
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

    # **ما هو قائمٌ الآن على هذه الرسالة** — والعزل مكتوبٌ في الشرط: RLS
    # تحمي بين المستأجرين ولا تحمي بين رسالتين في المستأجر الواحد.
    present = {
        (kind, paper, title)
        for kind, paper, title in (await session.execute(
            select(PublicationOpportunity.opportunity_kind,
                   PublicationOpportunity.paper_kind,
                   PublicationOpportunity.working_title_ar)
            .where(PublicationOpportunity.tenant_id == principal.tenant_id,
                   PublicationOpportunity.thesis_id == thesis_id)
        )).all()
    }

    created = 0
    already = 0
    for draft in drafts:
        key = (draft.opportunity_kind, draft.paper_kind, draft.working_title_ar)
        if key in present:
            already += 1
            continue
        present.add(key)
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

    # **«لم يُنقَّب بعد» ليست «نُقِّب فلم يُوجد».** بدون هذا الختم الزمنيّ
    # يصير الخبران رقمًا واحدًا: «٠ فرص» — وهو أقسى ما يُقال لباحثٍ لم
    # يبدأ التنقيب أصلًا. ويُكتب **وإن كان `created == 0`**: فحصٌ وقع
    # ولم يجد واقعةٌ يجب أن تُسجَّل، لا صمتٌ يُقرأ نتيجة.
    thesis.opportunities_mined_at = dt.datetime.now(dt.UTC)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="thesis.opportunities_mined",
        object_type="thesis", object_id=thesis_id, actor_user_id=principal.user_id,
        state_after={
            "created": created, "already_present": already,
            "kinds": sorted({d.opportunity_kind for d in drafts}),
            "data_age_years": report.data_age_years,
            "literature_age_years": report.literature_age_years,
        },
        reason="opportunities proposed from extracted thesis elements only (§23.4); "
               "a proposal that already exists is not written twice",
    )
    return MineResponse(
        thesis_id=thesis_id, opportunities_created=created,
        opportunities_already_present=already,
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
    payload: ConsentRequest | None = None,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> AuthorResponse:
    """§24 — الموافقةُ تُنسب إلى مَن سجّلها، ولا تُكتب عن أحدٍ صامتة.

    فإن كان الطالبُ هو الطرفَ نفسه (حسابٌ مربوط) فهي موافقتُه. وإن كان
    غيرَه فلا تُقبل إلّا بسندٍ مكتوب، وتُوسم `administrative` في السجلّ.
    """
    agreement = await rights.record_consent(
        session, tenant_id=principal.tenant_id, agreement_id=agreement_id,
        actor_user_id=principal.user_id,
        evidence_ar=payload.evidence_ar if payload else None,
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


# ═════════════════ قائمة الرسائل: صدقٌ، وهويّة، وحدٌّ ═════════════════
#
# **ثلاثةُ عيوبٍ كانت في هذه النقطة الواحدة.**
#
# ١ **رصّةُ بطاقاتٍ لا يفرّق بينها شيء.** خمسُ رسائل مرفوعة تُعرض خمسَ
#   بطاقاتٍ متطابقة تقول «لم يُستخرَج العنوان بعد» — بلا اسم ملفّ، فلا
#   يعرف الباحث أيَّها ملفُّه.
#
# ٢ **«٠ أقسام · ٠ فرص» بلا سبب.** ستُّ حالاتٍ تُنتج هذا السطر ومعناها
#   مختلف تمامًا، وأخطرُها أن يُقرأ فشلٌ نتيجةً صفرية: «حلّلنا رسالتك ولم
#   نجد فيها شيئًا» بينما الذي وقع أنّ القراءة سقطت.
#
# ٣ **استعلامان لكلّ رسالة، بلا سقف.** الصياغة السابقة تقرأ كلّ رسائل
#   المستأجر ثم تسأل القاعدة عن أقسام **كلّ رسالة** وفرصها على حدة. والـAPI
#   في سنغافورة والقاعدة في مومباي: كلُّ عبارةٍ رحلةٌ بنحو ٣٣٠ مللي ثانية.
#   عشرون رسالة ⇐ إحدى وأربعون رحلة ⇐ ثلاث عشرة ثانية من الشبكة وحدها،
#   تزيد طردًا مع كلّ رسالةٍ تُرفع. **فالباحث يُعاقَب على استعماله المنتج.**
#
# والعلاج للثالث هو علاج المكتبة نفسه (`routers/files.py`): صفحةٌ تُقتطع
# **في القاعدة** أولًا، ثم تُشتقّ أعدادُ ما فيها وحده باستعلاماتٍ فرعية
# مرتبطة — **عبارةٌ واحدة مهما بلغ عدد الرسائل**.

DEFAULT_PAGE = 25
MAX_PAGE = 100

#: عرضان مجمَّعان فوق الحالات المفردة — **ومفردةٌ واحدة لا معاملان**.
#: ومعاملان يقولان الشيء نفسه أوّلُ طريقٍ إلى تصفيتين تفترقان.
GROUPED_VIEWS: dict[str, tuple[str, ...]] = {
    # الفشل حالان لا واحدة: سقوطٌ، ومستندٌ بلا طبقة نصّ. والباحث يبحث
    # عن «ما لم ينجح» فيجدهما معًا.
    "failed": processing.FAILURE_STATES,
    "awaiting_action": (processing.AWAITING_CONSENT, processing.READY_FOR_REVIEW),
}

#: «الأحدث» ليست تصفية بل الترتيب الافتراضي — وتُقبل صراحةً لأنّ الشاشة
#: تعرضها زرًّا، وزرٌّ يُرسل قيمةً يرفضها الخادم عطبٌ في المنتج.
LISTING_VIEWS: tuple[str, ...] = (
    ("all", "recent") + tuple(GROUPED_VIEWS) + processing.PROCESSING_STATES
)


def _view_predicate(view: str | None):
    """شرطُ العرض في عبارة الصفحة نفسها — **ومجهولٌ يُردّ لا يُتجاهَل**.

    وتجاهلُه أسوأ من ردّه: من ضغط «متعثّرة» فرأى رسائله كلّها ظنّ أنّها
    كلّها متعثّرة. (وهي القاعدة نفسها المكتوبة في `library.unknown_filter`.)
    """
    if view is None or view in ("all", "recent"):
        return None
    if view in GROUPED_VIEWS:
        return Thesis.processing_state.in_(GROUPED_VIEWS[view])
    if view in processing.PROCESSING_STATES:
        return Thesis.processing_state == view
    raise AtheraError("thesis.unknown_view", status_code=422,
                      views=" · ".join(LISTING_VIEWS))


_LIKE_ESCAPE = "\\"


def _escaped(term: str) -> str:
    """`%` و`_` في يد الباحث حرفان لا محرفا بدل — وبحثٌ عن `%` لا يعيد كلَّ شيء."""
    out = term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
    return out.replace("%", f"{_LIKE_ESCAPE}%").replace("_", f"{_LIKE_ESCAPE}_")


def _search_predicate(tenant_id: uuid.UUID, term: str | None):
    """بحثٌ باسم الملفّ أو بالعنوان المستخرَج — **بشرطٍ واحد في العبارة**.

    والاسم يُبحث لأنّ الرسالة قبل قراءتها لا عنوان لها: من رفع
    `thesis-final-v3.pdf` ولمّا تُقرأ لا يجدها إلّا باسمها. و`EXISTS`
    مرتبطٌ بصفّ الرسالة، لا قائمةُ معرّفاتٍ تُقرأ في عبارةٍ سابقة.
    """
    needle = (term or "").strip()
    if not needle:
        return None
    pattern = f"%{_escaped(needle)}%"

    def like(column):
        return column.ilike(pattern, escape=_LIKE_ESCAPE)

    named = (
        select(File.id)
        .where(File.tenant_id == tenant_id, File.id == Thesis.file_id,
               like(File.original_filename))
        .exists()
    )
    return or_(like(Thesis.title_ar), like(Thesis.title_en), named)


_UNSET = object()


def _card(row, locale: str, *, source_filename=_UNSET, sections=_UNSET,
          opportunities=_UNSET, results=_UNSET) -> ThesisResponse:
    """بطاقةٌ واحدة — **والرقمُ فيها لا يخرج بلا سببه**.

    ولا نسبةٌ مئوية ولا «٧٣٪ اكتمالًا»: خطُّ الأنابيب لا يقيس تقدّمًا، ورقمٌ
    يُعرض بلا قياسٍ خلفه اختلاقٌ صغير يتكرّر في كلّ بطاقة.

    و`row` صفُّ الصفحة أو كائنُ `Thesis` نفسه؛ والأعدادُ تُمرَّر صراحةً حين
    لا يحملها الصفّ. **وصياغةٌ واحدة للبطاقة لا اثنتان** — فما يُعرض بعد
    التسجيل هو ما يُعرض في القائمة حرفًا بحرف، ولا تفترقان بأول تعديل.
    """
    state = row.processing_state
    sections = int(
        (row.sections_extracted if sections is _UNSET else sections) or 0)
    found = int(
        (row.opportunities_found if opportunities is _UNSET else opportunities) or 0)
    # **العدُّ الثاني الذي يقرؤه المنقّب.** بدونه تُقاس إتاحةُ التنقيب
    # بـ`parsed_at` — ختمِ مسارٍ قديم — لا بوجود دليلٍ يقرؤه المنقّب فعلًا.
    result_rows = int(
        (row.results_extracted if results is _UNSET else results) or 0)
    filename = row.source_filename if source_filename is _UNSET else source_filename

    shown, extracted = processing.display_title(
        row.title_ar, row.title_en, filename, locale)

    sections_why = processing.section_outcome(state, sections)
    opportunities_why = processing.opportunity_outcome(
        state, found, row.opportunities_mined_at)

    # **إعادةُ المحاولة تُعرض حيث تنفع وحدها**، ويُقال سببُ منعها حيث تُمنع.
    can_retry = row.file_id is not None and state in processing.RETRYABLE
    blocked = None
    if not can_retry:
        if state == processing.TEXT_LAYER_MISSING:
            blocked = _pick(locale, *processing.FAILURE_LABELS["text_layer_missing"])
        elif state in processing.IN_FLIGHT:
            blocked = _pick(locale, *processing.STATE_LABELS[state])
        elif row.file_id is None:
            blocked = _pick(locale, "لا ملفّ مرفق بهذه الرسالة.",
                            "No file is attached to this thesis.")

    return ThesisResponse(
        id=row.id,
        title=_pick(locale, row.title_ar, row.title_en),
        title_ar=row.title_ar,
        degree=row.degree,
        source_filename=filename,
        display_title=shown,
        title_is_extracted=extracted,
        processing_state=state,
        processing_state_label=_pick(locale, *processing.STATE_LABELS[state]),
        processing_state_changed_at=row.processing_state_changed_at,
        processing_attempts=int(row.processing_attempts or 0),
        failure_code=row.failure_code,
        failure_message=(_pick(locale, *processing.FAILURE_LABELS[row.failure_code])
                         if row.failure_code else None),
        can_retry=can_retry,
        retry_blocked_reason=blocked,
        text_layer_state=row.text_layer_state,
        ocr_state=row.ocr_state,
        # **ولا تُعلَن القراءة الضوئية متاحةً ما دامت غير متاحة.** والراية
        # تُشتقّ من العمود لا من ثابتٍ في الشاشة، فيوم يصير OCR حقيقةً
        # تتغيّر في موضعٍ واحد.
        ocr_available=row.ocr_state != processing.OCR_UNAVAILABLE,
        defended_on=row.defended_on,
        data_collected_on=row.data_collected_on,
        rights_basis=row.rights_basis,
        parsed_at=row.parsed_at,
        sections_extracted=sections,
        sections_outcome=sections_why,
        sections_outcome_label=_pick(
            locale, *processing.SECTION_OUTCOME_LABELS[sections_why]),
        opportunities_found=found,
        opportunities_outcome=opportunities_why,
        opportunities_outcome_label=_pick(
            locale, *processing.OPPORTUNITY_OUTCOME_LABELS[opportunities_why]),
        opportunities_mined_at=row.opportunities_mined_at,
        results_extracted=result_rows,
        source_file_id=row.file_id,
        # **آلةُ الحال في موضعٍ واحد** — والشاشة تعرض ما يقوله الخادم، ولا
        # تعيد بناء الشروط في JSX فتفترق عنه.
        actions=ThesisCardActions(**asdict(card_actions.compute(
            processing_state=state, file_id=row.file_id,
            sections=sections, results=result_rows, locale=locale))),
    )


@router.get("/theses", response_model=list[ThesisResponse])
async def list_theses(
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    after: uuid.UUID | None = Query(
        default=None, description="معرّف آخر رسالةٍ رآها العميل — مؤشّرٌ مفتاحيّ لا إزاحة"),
    q: str | None = Query(default=None, max_length=200,
                          description="بحثٌ في اسم الملفّ أو العنوان المستخرَج"),
    view: str | None = Query(default=None, description=" · ".join(LISTING_VIEWS)),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ThesisResponse]:
    """رسائل الباحث — **صفحةٌ محدودة بعبارةٍ واحدة، وكلُّ رقمٍ معه سببه**.

    **والمؤشّر مفتاحيّ لا إزاحة.** `after` معرّفُ آخر رسالةٍ رآها العميل،
    ويُحلّ داخل العبارة نفسها فلا يكلّف رحلةً ثانية. والترتيب
    `(created_at, id)` نازلًا: `created_at` وحده لا يفصل رسالتين رُفعتا في
    المعاملة نفسها، فتتكرّر واحدة في صفحتين أو تسقط بينهما.

    **والعدّ يقع في القاعدة على صفوف الصفحة وحدها.** الاستعلامات الفرعية
    مرتبطةٌ بـ`window.c.id` بعد الاقتطاع، لا بكلّ رسائل المستأجر — فكلفةُ
    الصفحة ثابتة مهما بلغ عددُ الرسائل.

    **والعزل مكتوبٌ في كلّ شرط.** RLS تحمي بين المستأجرين، **ولا تحمي بين
    بحثين في المستأجر الواحد** — وهو عطبٌ وقع في هذا المنتج من قبل. فعدُّ
    الفرص مشروطٌ بـ`thesis_id` **وبالمستأجر معًا**: فرصةٌ نشأت من بحثٍ آخر
    (`project_id` مضبوط و`thesis_id` فارغ) لا تُعدّ على أيّ رسالة، لا لأنّ
    بايثون تصفّيها بل لأنّ الشرط في `WHERE` أصلًا.
    """
    page = (
        select(
            Thesis.id, Thesis.title_ar, Thesis.title_en, Thesis.degree,
            Thesis.defended_on, Thesis.data_collected_on, Thesis.rights_basis,
            Thesis.parsed_at, Thesis.file_id, Thesis.created_at,
            Thesis.processing_state, Thesis.processing_state_changed_at,
            Thesis.processing_attempts, Thesis.failure_code,
            Thesis.text_layer_state, Thesis.ocr_state, Thesis.opportunities_mined_at,
        )
        .where(Thesis.tenant_id == principal.tenant_id)
        .order_by(Thesis.created_at.desc(), Thesis.id.desc())
        .limit(limit)
    )
    chosen = _view_predicate(view)
    if chosen is not None:
        page = page.where(chosen)
    matching = _search_predicate(principal.tenant_id, q)
    if matching is not None:
        page = page.where(matching)
    if after is not None:
        anchor_created = (
            select(Thesis.created_at)
            .where(Thesis.id == after, Thesis.tenant_id == principal.tenant_id)
            .scalar_subquery()
        )
        anchor_id = (
            select(Thesis.id)
            .where(Thesis.id == after, Thesis.tenant_id == principal.tenant_id)
            .scalar_subquery()
        )
        page = page.where(
            tuple_(Thesis.created_at, Thesis.id) < tuple_(anchor_created, anchor_id))

    window = page.subquery("page")

    # اسمُ الملفّ — **هويّةُ البطاقة حين لا عنوان بعد**.
    filename = (
        select(File.original_filename)
        .where(File.tenant_id == principal.tenant_id, File.id == window.c.file_id)
        .limit(1).scalar_subquery()
    )
    sections = (
        select(func.count(ThesisSection.id))
        .where(ThesisSection.tenant_id == principal.tenant_id,
               ThesisSection.thesis_id == window.c.id)
        .scalar_subquery()
    )
    opportunities = (
        select(func.count(PublicationOpportunity.id))
        .where(PublicationOpportunity.tenant_id == principal.tenant_id,
               PublicationOpportunity.thesis_id == window.c.id)
        .scalar_subquery()
    )
    # **العدُّ الثاني الذي يقرؤه المنقّب** — عمودٌ في العبارة نفسها، لا رحلةٌ
    # ثانية إلى مومباي: كلفةُ الصفحة تبقى كما هي، وتُصبح إتاحةُ التنقيب
    # مقيسةً بوجود دليلٍ لا بختمِ مسارٍ قديم.
    results = (
        select(func.count(ThesisResult.id))
        .where(ThesisResult.tenant_id == principal.tenant_id,
               ThesisResult.thesis_id == window.c.id)
        .scalar_subquery()
    )

    rows = (await session.execute(
        select(window, filename.label("source_filename"),
               sections.label("sections_extracted"),
               opportunities.label("opportunities_found"),
               results.label("results_extracted"))
        .order_by(window.c.created_at.desc(), window.c.id.desc())
    )).all()
    return [_card(row, principal.locale) for row in rows]

