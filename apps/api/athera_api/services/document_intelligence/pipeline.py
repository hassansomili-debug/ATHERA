"""خطّ أنابيب ذكاء المستندات | The S5C processing pipeline.

    مخزَّن → تفكيك → مقاطع بمواضعها → حتمي أولًا → نموذج على الأدنى اللازم
    → مرشّحات → مراجعة إنسان

**لا مكدّس موازٍ:** التفكيك من `services/parsing.py`، والمقاطع في
`document_chunks`، والتشغيلة في `extraction_runs`، والمرشّحات في
`fact_candidates`. كلها قائمة قبل S5C.

**والنموذج يُستدعى عبر المنسّق وحده** — لا اتصال مباشر من خدمة بحثية بمزوّد.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.files import File
from ...models.research import DocumentChunk, ExtractionRun, FactCandidate
from ...models.thesis import Thesis
from ..extraction.base import quote_is_grounded
from ..parsing import UnsupportedDocument, parse
from .contracts import STATUS_EXTRACTED, STATUS_NOT_FOUND, ExtractionBatch
from .deterministic import extract as deterministic_extract
from .fields import MODEL_FIELDS, Section, memory_category_for
from .selection import ChunkView, excluded_report, select_chunks_for
from .states import Status

# حزمة حقول واحدة لكل قسم — استدعاء لكل حقل يضاعف الكلفة بلا فائدة.
_BATCH_SECTIONS = (
    Section.METADATA, Section.PROBLEM, Section.QUESTIONS,
    Section.THEORY, Section.METHODOLOGY, Section.FINDINGS, Section.LIMITS,
)


@dataclass(slots=True)
class PipelineResult:
    run_id: uuid.UUID
    status: Status
    chunks: int
    candidates: int
    excluded: dict[str, int]
    failed_sections: list[str]
    error: str | None = None
    # حقول فُحصت فلم تُوجد — تُعلَن مفقودة ولا تُخزَّن صفوفًا بلا اقتباس.
    not_found: tuple[str, ...] = ()


def _views(rows: list[DocumentChunk]) -> list[ChunkView]:
    return [
        ChunkView(str(r.id), r.seq, r.text, r.locator, r.page_number, r.section_path)
        for r in rows
    ]


async def parse_into_chunks(
    session: AsyncSession, *, tenant_id: uuid.UUID, record: File, data: bytes,
) -> list[DocumentChunk]:
    """تفكيك ثم حفظ المقاطع بمواضعها. مقطع بلا موضع لا يُحفظ (§29.2).

    **وإعادة القراءة لا تعيد التفكيك.** الملف في التخزين لا يُعدَّل — مفتاحه
    ثابت وبصمته محفوظة — فمقاطعه لا تتغير. وإعادة إدراجها تخالف
    `uq_document_chunks_seq` أصلًا، والأهمّ أنها تُنشئ مواضع جديدة لنفس
    النصّ فتُبطل إسناد المرشّحات القديمة إلى مقاطعها.
    """
    existing = list((
        await session.execute(
            select(DocumentChunk).where(DocumentChunk.file_id == record.id)
            .order_by(DocumentChunk.seq)
        )
    ).scalars().all())
    if existing:
        return existing

    parsed = parse(data, record.content_type, record.original_filename)
    rows: list[DocumentChunk] = []
    for chunk in parsed:
        if not chunk.locator:
            continue
        row = DocumentChunk(
            tenant_id=tenant_id, file_id=record.id, seq=len(rows), text=chunk.text,
            locator=chunk.locator, page_number=chunk.page_number,
            section_path=chunk.section_path, paragraph_index=None,
            char_count=len(chunk.text),
            # §33.3 — محتوى الملفات بيانات لا تعليمات، منذ لحظة الحفظ.
            is_untrusted=True,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


def build_prompt(section: Section, chunks: list[ChunkView], specs) -> str:
    """المطالبة: الحقول المطلوبة ثم المقاطع **موسومةً كبيانات**.

    الوسم صريح: ما بين `<DOCUMENT>` مادةٌ مُستخرَجة من ملف رفعه المستخدم،
    وليس تعليمات. وهذا هو حدّ الحقن في موضعه العملي — لا في التوثيق وحده.
    """
    wanted = "\n".join(
        f"- {s.key} ({s.label_en}){' [قد يتكرر]' if s.multi else ''}" for s in specs
    )
    body = "\n\n".join(
        f"[{c.locator}] {c.text[:1800]}" for c in chunks
    )
    return (
        f"استخرج الحقول التالية من مقاطع الرسالة أدناه، ولا شيء غيرها:\n{wanted}\n\n"
        "لكل حقل أعِد: field_key، وstatus، وvalue، وquote (اقتباس حرفي من المقاطع)، "
        "وextraction_confidence.\n"
        "إن لم يرد الحقل في المقاطع فـstatus = not_found وvalue = null. "
        "وإن ورد ملتبسًا فـstatus = ambiguous. **لا تخمّن ولا تكمل من معرفتك العامة.**\n\n"
        f"<DOCUMENT section=\"{section.value}\">\n{body}\n</DOCUMENT>"
    )


@dataclass(frozen=True, slots=True)
class SectionPlan:
    """قسمٌ جاهز للإرسال — **بيانات في الذاكرة لا كائنات ORM**.

    يعبر حدود المعاملات، ولذلك لا يحمل صفًّا ولا جلسة: نصوص المقاطع
    ومعرّفاتها ومواضعها وحدها. فلا `DetachedInstanceError` ولا استعلام
    كسول يفتح معاملةً من حيث لا نحتسب.
    """

    section: Section
    prompt: str
    chunks: tuple[ChunkView, ...]
    field_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Prepared:
    """حصيلة العمل المحلي — يُودَع قبل أن يبدأ أي انتظار خارجي."""

    run_id: uuid.UUID
    file_id: uuid.UUID
    status: Status
    chunks: int
    candidates: int
    excluded: dict
    views: tuple[ChunkView, ...]
    error: str | None = None


async def prepare(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    file_record: File,
    data: bytes,
    run_id: uuid.UUID | None = None,
    external_allowed: bool = True,
    consent_state: str = "granted",
) -> Prepared:
    """كل ما لا يحتاج شبكة — في معاملة واحدة قصيرة تُودَع فورًا.

    التفكيك، والمقاطع بمواضعها، والاستخراج الحتمي. وبعدها تُغلق المعاملة
    فلا يبقى اتصالٌ مفتوح أثناء انتظار المزوّد.
    """
    run = None
    if run_id is not None:
        run = (
            await session.execute(select(ExtractionRun).where(
                ExtractionRun.id == run_id, ExtractionRun.tenant_id == tenant_id))
        ).scalar_one_or_none()
    if run is None:
        run = ExtractionRun(
            tenant_id=tenant_id, file_id=file_record.id, extractor="document_intelligence",
            status=Status.PARSING.value, chunks_parsed=0, candidates_proposed=0,
            candidates_rejected_unquoted=0, started_at=dt.datetime.now(dt.UTC),
        )
        session.add(run)
    await session.flush()

    # ── التفكيك ──
    try:
        rows = await parse_into_chunks(session, tenant_id=tenant_id, record=file_record, data=data)
    except UnsupportedDocument as exc:
        run.status = Status.PARSE_FAILED.value
        run.error = str(exc)[:500]
        run.finished_at = dt.datetime.now(dt.UTC)
        return Prepared(run.id, file_record.id, Status.PARSE_FAILED, 0, 0, {}, (),
                        str(exc)[:200])

    run.chunks_parsed = len(rows)
    run.status = Status.EXTRACTING.value if external_allowed else Status.PARSED.value
    views = _views(rows)
    excluded = excluded_report(views)

    # ── الحتمي أولًا ──
    candidates = 0
    for value in deterministic_extract(views, filename=file_record.original_filename):
        session.add(FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run.id, file_id=file_record.id,
            chunk_id=uuid.UUID(value.chunk_id) if value.chunk_id else rows[0].id,
            memory_category="researcher_fact", field_key=value.field_key,
            statement_ar=str(value.value),
            value={"value": value.value, "extraction_status": STATUS_EXTRACTED},
            quote=value.quote, locator=value.locator,
            # `unverified` لا `extracted`: العمود حالة **قرار الإنسان** لا
            # نتيجة القراءة. وخلطهما كان يجعل كل مرشّح يبدو «مقرَّرًا» فيرفض
            # مسار الترقية اعتماده بحجّة أنه حُسم — وهو لم يُعرض بعد.
            confidence=1.0, status="unverified",
        ))
        candidates += 1

    # ── بلا إذن: يقف الخط عند المحلي، ولا يُعدّ ذلك فشلًا ──
    #
    # الاستخراج الحتمي تمّ، والمقاطع محفوظة بمواضعها، والمراجعة ممكنة على ما
    # استُخرج. وما لم يقع هو **الإرسال الخارجي وحده** — فيُقال باسمه.
    if not external_allowed:
        run.candidates_proposed = candidates
        run.status = (Status.LOCAL_ONLY.value if consent_state == "declined"
                      else Status.AWAITING_CONSENT.value)
        run.finished_at = dt.datetime.now(dt.UTC)

    return Prepared(run.id, file_record.id, Status(run.status), len(rows), candidates,
                    excluded, tuple(views))


def plan_sections(views) -> list[SectionPlan]:
    """اختيار المقاطع وبناء المطالبات — **دالة خالصة، بلا قاعدة ولا شبكة**."""
    plans: list[SectionPlan] = []
    for section in _BATCH_SECTIONS:
        specs = [f for f in MODEL_FIELDS if f.section is section]
        if not specs:
            continue
        picked: dict[str, ChunkView] = {}
        for spec in specs:
            for chunk in select_chunks_for(spec, list(views)):
                picked[chunk.chunk_id] = chunk
        if not picked:
            continue
        chunk_list = tuple(sorted(picked.values(), key=lambda c: c.seq))
        plans.append(SectionPlan(
            section=section,
            prompt=build_prompt(section, list(chunk_list), specs),
            chunks=chunk_list,
            field_keys=tuple(f.key for f in specs),
        ))
    return plans


async def absorb(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    file_id: uuid.UUID,
    plan: SectionPlan,
    batch: ExtractionBatch,
) -> tuple[int, int, set[str]]:
    """يحفظ مرشّحات قسم واحد — معاملة قصيرة بعد أن انتهت الشبكة.

    ويعيد: كم قُبل، وكم رُفض لعدم التأصيل، وأي حقول فُحصت فلم تُوجد.
    """
    spec_by_key = {k: f for k in plan.field_keys
                   for f in MODEL_FIELDS if f.key == k}
    run = (
        await session.execute(select(ExtractionRun).where(
            ExtractionRun.id == run_id, ExtractionRun.tenant_id == tenant_id))
    ).scalar_one()

    accepted = rejected = 0
    attempted: set[str] = set()
    for field in batch.fields:
        if field.status == STATUS_NOT_FOUND:
            # **الغياب لا يُسجَّل صفًّا.** `fact_candidates` يشترط اقتباسًا
            # بقيد في القاعدة (`ck_candidate_quote_required`)، والمفقود لا
            # اقتباس له — فصفٌّ باقتباس فارغ يخالف القيد، وصفٌّ باقتباس
            # مستعار من مقطع لا يحوي الحقل هو اختلاق الموضع بعينه.
            #
            # والغياب يبقى مرئيًّا في المراجعة بلا صفّ: الشاشة تعرض فهرس
            # الحقول كاملًا، وما لا مرشّح له يُعلَن «لم يُستخرَج».
            attempted.add(field.field_key)
            continue

        # ── حاجز الاختلاق ──
        #
        # قيمة باقتباس لا يوجد في أي مقطع مُرسَل **تُرفض**. ولا مقطع
        # احتياطي يُسنَد إليه: إسناد اقتباسٍ مختلَق إلى أول مقطع يجعل
        # الاختلاق يمرّ **وقد اكتسب موضعًا**، وهو أسوأ من مروره عاريًا —
        # لأن الباحث سيرى مصدرًا يبدو صحيحًا فيثق به.
        #
        # والفحص هو `quote_is_grounded` نفسه الذي يستعمله الاعتماد في
        # §7.4. واختلافهما كان سيجعل مرشّحًا يُقبل هنا ويُرفض عند
        # الاعتماد — طريقٌ مسدود أمام الباحث بلا سبب مفهوم.
        quote = (field.quote or "").strip()
        source = next((c for c in plan.chunks if quote_is_grounded(quote, c.text)), None)
        if source is None:
            run.candidates_rejected_unquoted += 1
            rejected += 1
            continue

        session.add(FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run_id, file_id=file_id,
            chunk_id=uuid.UUID(source.chunk_id),
            memory_category=memory_category_for(spec_by_key[field.field_key])
            if field.field_key in spec_by_key else "researcher_fact",
            field_key=field.field_key,
            statement_ar=str(field.value) if field.value is not None else "",
            value={"value": field.value, "extraction_status": field.status},
            quote=quote[:2000], locator=source.locator,
            confidence=field.extraction_confidence, status="unverified",
        ))
        accepted += 1

    run.candidates_proposed += accepted
    return accepted, rejected, attempted


async def finalize(
    session: AsyncSession, *, tenant_id: uuid.UUID, run_id: uuid.UUID,
    failed: list[str],
) -> ExtractionRun:
    """إغلاق التشغيلة — معاملة قصيرة أخيرة."""
    run = (
        await session.execute(select(ExtractionRun).where(
            ExtractionRun.id == run_id, ExtractionRun.tenant_id == tenant_id))
    ).scalar_one()
    run.status = Status.AWAITING_REVIEW.value
    run.finished_at = dt.datetime.now(dt.UTC)
    if failed:
        # فشل قسم لا يُسقط ما نجح: الأقسام الأخرى تبقى، ويُبلَّغ عن الفاشل
        # باسمه (§29). فرسالةٌ استُخرج منها ستة أقسام من سبعة أنفع من لا شيء.
        run.error = ("partial: " + "; ".join(failed))[:500]
    return run


async def run_extraction(
    session_maker,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    file_id: uuid.UUID,
    data: bytes,
    model_call,
    locale: str = "ar",
    run_id: uuid.UUID | None = None,
    external_allowed: bool = True,
    consent_state: str = "granted",
) -> PipelineResult:
    """التشغيلة كاملة — **ولا معاملة مفتوحة أثناء أي نداء خارجي**.

    الشكل: معاملة قصيرة للعمل المحلي، ثم لكل قسم نداءٌ **بلا معاملة** يليه
    معاملة قصيرة تحفظ نتيجته، ثم معاملة أخيرة تُغلق التشغيلة.

    وكان هذا كله معاملةً واحدة تمتدّ من التفكيك إلى آخر قسم — فتبقى مفتوحة
    دقائق أثناء سبعة نداءات خارجية، ويظهر الاتصال `idle in transaction`،
    ويُمسَك قفل سلسلة التدقيق للمستأجر فتقف كتاباته خلفه. رُصد ذلك في
    الإنتاج: اتصالٌ علِق 254 ثانية، وكتابةٌ استغرقت 120 ثانية ثم تمّت في 6.2
    حين أُفرج عنه.

    و`session_maker` دالةٌ تُنشئ جلسةً جديدة عند كل نداء — لا جلسةٌ تُمرَّر:
    الجلسة الممرَّرة تعني معاملةً حيّة، وهي ما نتجنّب.
    """
    async with session_maker() as session:
        record = (
            await session.execute(select(File).where(
                File.id == file_id, File.tenant_id == tenant_id))
        ).scalar_one()
        prepared = await prepare(
            session, tenant_id=tenant_id, actor_user_id=actor_user_id,
            file_record=record, data=data, run_id=run_id,
            external_allowed=external_allowed, consent_state=consent_state,
        )

    if prepared.status is Status.PARSE_FAILED:
        return PipelineResult(prepared.run_id, Status.PARSE_FAILED, 0, 0, {}, [],
                              prepared.error, ())
    if not external_allowed:
        return PipelineResult(prepared.run_id, prepared.status, prepared.chunks,
                              prepared.candidates, prepared.excluded, [], None, ())

    # ── الأقسام: نداءٌ بلا معاملة، ثم حفظٌ في معاملة قصيرة ──
    plans = plan_sections(prepared.views)
    failed: list[str] = []
    candidates = prepared.candidates
    attempted: set[str] = set()
    for plan in plans:
        try:
            # **لا جلسة هنا.** ولو بقيت معاملة مفتوحة لعاد العطب نفسه.
            result = await model_call(
                question=plan.prompt,
                schema=ExtractionBatch.model_json_schema(),
                # §7 — محتوى بحثي غير منشور: C2، والبوابة تحكم الإرسال.
                classification="C2",
                locale=locale,
            )
            batch = ExtractionBatch.model_validate(result)
        except Exception as exc:  # noqa: BLE001 — قسم يسقط ولا يُسقط غيره
            failed.append(f"{plan.section.value}:{type(exc).__name__}")
            continue

        async with session_maker() as session:
            accepted, _rejected, missing = await absorb(
                session, tenant_id=tenant_id, run_id=prepared.run_id,
                file_id=prepared.file_id, plan=plan, batch=batch,
            )
        candidates += accepted
        attempted |= missing

    async with session_maker() as session:
        run = await finalize(session, tenant_id=tenant_id,
                             run_id=prepared.run_id, failed=failed)
        status = Status(run.status)

    return PipelineResult(prepared.run_id, status, prepared.chunks, candidates,
                          prepared.excluded, failed, None, tuple(sorted(attempted)))


async def ensure_thesis_for_file(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID,
) -> tuple[Thesis, bool]:
    """سجل الرسالة — يُنشأ مرة واحدة لكل ملف (§4، §5).

    **والتكرار يُمنع بالبحث لا بقيد جديد:** `theses.file_id` قائم، فالاستعلام
    عنه قبل الإنشاء يجعل إعادة المحاولة آمنة بلا ترحيل إضافي.

    ويُنشأ بلا عنوان ولا درجة: `NULL` تعني «لم يُستخرَج بعد» — واسم الملف
    عنوانًا أو درجةً مخمَّنة اختلاقٌ يمنعه §11.
    """
    existing = (
        await session.execute(select(Thesis).where(Thesis.file_id == file_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    thesis = Thesis(tenant_id=tenant_id, file_id=file_id, title_ar=None, degree=None)
    session.add(thesis)
    await session.flush()
    return thesis, True


def content_fingerprint(data: bytes) -> str:
    """بصمة المحتوى — لمنع إعادة معالجة المطابق بلا داعٍ (§27)."""
    return hashlib.sha256(data).hexdigest()
