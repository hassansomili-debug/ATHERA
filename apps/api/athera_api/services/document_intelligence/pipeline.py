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
from typing import Final

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.files import File
from ...models.research import DocumentChunk, ExtractionRun, FactCandidate
from ...models.thesis import Thesis
from ..extraction.base import quote_is_grounded
from ..parsing import NoTextLayer, UnsupportedDocument, parse
from ..thesis import processing
from ..thesis.processing import (  # noqa: F401 — يُعاد تصديرُه للمُنادين
    PROCESSING_NAMESPACE,
    run_id_for,
)
from . import section_ledger
from .contracts import STATUS_EXTRACTED, STATUS_NOT_FOUND, ExtractionBatch
from .deterministic import extract as deterministic_extract
from .fields import MODEL_FIELDS, Section, memory_category_for
from .selection import ChunkView, excluded_report, select_chunks_for
from .states import Status

# **حدُّ انتظارِ الأقفال في التنقيب التلقائيّ وحده.**
#
# `audit.record` يأخذ قفلًا استشاريًّا لسلسلة تدقيق المستأجر كلّه. ومعاملةٌ
# أخرى تمسكه تُعلّق هذا التنقيبَ **بلا حدّ**: التنقيبُ خلفيٌّ بعد استخراجٍ
# نجح، فلا أحدَ ينتظره ولا شيءَ يقطعه. فيُحَدّ انتظارُه هنا — وهنا وحده،
# ولا تُمسّ دلالاتُ التدقيق للمنصّة كلّها (ذاك عملُ P1).
AUTO_MINING_LOCK_TIMEOUT_MS = 5000

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


#: **ما يعنيه الرقم — معلنًا في المطالبة، لا متروكًا للتخمين.**
#:
#: كانت المطالبة تطلب `extraction_confidence` ولا تقول ما هو. ورقمٌ بلا
#: تعريفٍ يملؤه النموذجُ بما يظنّه: أهي ثقةٌ في **صحّة العلم**؟ في أهمّية
#: النتيجة؟ في جودة الرسالة؟ وكلُّ قراءةٍ من هذه تُنتج توزيعًا مختلفًا،
#: ثمّ تُقاس بعتباتٍ عُيِّرت على قراءةٍ واحدة — فيصير الحدُّ عشوائيًّا.
#:
#: والتعريفُ المكتوب هنا **لا يطلب رفعَ الأرقام**. يطلب أن تقيس شيئًا
#: واحدًا بعينه: هل هذه القيمة **مذكورةٌ صراحةً** في الاقتباس، ومُسنَدةٌ
#: إلى الحقل الصحيح؟ وما دون ذلك له مخارجُه المعلنة: التباسُ الإسناد
#: `ambiguous`، وغيابُ الدليل `not_found`. ولا قيمةَ افتراضية بحال.
CONFIDENCE_CONTRACT: Final = (
    "تعريف extraction_confidence — اقرأه قبل أن تُعطي رقمًا:\n"
    "هو ثقتُك في أنّ هذه القيمة **مذكورةٌ صراحةً في النصّ المقتبَس**، "
    "وأنّها **مُسنَدةٌ إلى هذا الحقل** لا إلى حقلٍ آخر. لا أكثر.\n"
    "وهو ليس: صحّةَ النتيجة علميًّا، ولا دلالتَها الإحصائية، ولا أهمّيةَ "
    "الاكتشاف، ولا جودةَ الرسالة، ولا ثقتَك في النظرية.\n"
    "فإن كان النصُّ يذكر القيمةَ صراحةً وإسنادُها إلى الحقل بيّن: "
    "أعطِ ثقةً عالية تناسب ذلك الوضوح.\n"
    "وإن كان الإسنادُ غيرَ بيّن أو يحتمل حقلين: status = ambiguous.\n"
    "وإن لم يرد في المقاطع: status = not_found.\n"
    "**ولا تخترع رقمًا افتراضيًّا، ولا تُغفل الحقل**: كلُّ حقلٍ حالتُه "
    "extracted يحمل extraction_confidence بين 0.0 و1.0."
)


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
        f"{CONFIDENCE_CONTRACT}\n\n"
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
    # **والتشغيلةُ تُستعاد بمعرّفها الثابت، ولا تُخلَق ثانيةً** (H2-B5).
    #
    # فمعرّفٌ عشوائيٌّ عند كلّ بداية يعني أنّ استئنافَ محاولةٍ مهجورةٍ يفتح
    # تشغيلةً ثانيةً للعمل الواحد: عددان في القاعدة، ومرشّحاتٌ تُنسب إلى
    # غير التي بدأتها. و`run_id_for` يعطي الهُويّةَ نفسَها ما دامت المحاولةُ
    # هي هي — فالإدراجُ محاولةٌ، والموجودُ يُعاد استعمالُه.
    run = None
    if run_id is not None:
        run = (
            await session.execute(select(ExtractionRun).where(
                ExtractionRun.id == run_id, ExtractionRun.tenant_id == tenant_id))
        ).scalar_one_or_none()
    if run is None:
        run = ExtractionRun(
            id=run_id,
            tenant_id=tenant_id, file_id=file_record.id, extractor="document_intelligence",
            status=Status.PARSING.value, chunks_parsed=0, candidates_proposed=0,
            candidates_rejected_unquoted=0, started_at=dt.datetime.now(dt.UTC),
        )
        session.add(run)
    await session.flush()

    # **حالُ الرسالة تُثبَّت مع كل انتقالٍ حقيقي** (ترحيل 0027). وهي عمودٌ
    # على `theses` لا اشتقاقٌ من `extraction_runs`: حالُ التشغيلة تصف
    # تشغيلة، وإعادةُ القراءة تُنشئ صفًّا جديدًا فتقفز الحال إلى الوراء.
    await processing.mark(session, tenant_id=tenant_id, file_id=file_record.id,
                          state=processing.PARSING)

    # ── التفكيك ──
    try:
        rows = await parse_into_chunks(session, tenant_id=tenant_id, record=file_record, data=data)
    except NoTextLayer as exc:
        # **مستندٌ ممسوح ضوئيًّا ليس ملفًّا فاسدًا.** الحال تُسمّى باسمها،
        # وطبقةُ النصّ تُعلَن غائبةً — فلا يُدّعى أنّ OCR جرى ولا يُعرض زرُّ
        # إعادةٍ يَعِد بنتيجةٍ لن تختلف.
        run.status = Status.PARSE_FAILED.value
        run.error = str(exc)[:500]
        run.finished_at = dt.datetime.now(dt.UTC)
        await processing.mark(
            session, tenant_id=tenant_id, file_id=file_record.id,
            state=processing.TEXT_LAYER_MISSING, failure_code="text_layer_missing",
            failure_detail=str(exc)[:500], text_layer=processing.TEXT_LAYER_ABSENT)
        return Prepared(run.id, file_record.id, Status.PARSE_FAILED, 0, 0, {}, (),
                        str(exc)[:200])
    except UnsupportedDocument as exc:
        run.status = Status.PARSE_FAILED.value
        run.error = str(exc)[:500]
        run.finished_at = dt.datetime.now(dt.UTC)
        await processing.mark(
            session, tenant_id=tenant_id, file_id=file_record.id,
            state=processing.FAILED, failure_code="unsupported_document",
            failure_detail=f"{type(exc).__name__}: {exc}"[:500])
        return Prepared(run.id, file_record.id, Status.PARSE_FAILED, 0, 0, {}, (),
                        str(exc)[:200])

    run.chunks_parsed = len(rows)
    run.status = Status.EXTRACTING.value if external_allowed else Status.PARSED.value
    # قُرئ نصٌّ فعلًا — فتُعلَن الطبقة موجودة. و«لم تُفحص» ليست «موجودة».
    await processing.mark(session, tenant_id=tenant_id, file_id=file_record.id,
                          state=processing.EXTRACTING,
                          text_layer=processing.TEXT_LAYER_PRESENT)
    views = _views(rows)
    excluded = excluded_report(views)

    # ── الحتمي أولًا ──
    #
    # **ولا يُدرَج مرّتين في التشغيلةِ الواحدة** (H2-B5). فاستئنافُ محاولةٍ
    # بعد سقوطٍ يُعيد تحضيرَها، والاستخراجُ الحتميُّ حتميٌّ فعلًا — يُنتج
    # القيمَ نفسَها — فيتضاعف المرشّحُ على الشاشة ويُطلب من الباحثِ أن
    # يقرّر في الأمر مرّتين.
    #
    # والهُويّةُ العمليّةُ للمرشّحِ الحتميّ: تشغيلتُه وحقلُه وموضعُه. وتُقرأ
    # الموجودةُ أوّلًا ثمّ يُدرَج الغائبُ وحده — **ولا يُمَسّ قرارُ إنسانٍ**:
    # ما قرّره الباحثُ يبقى كما هو، ولا يُحذف ولا يُكتب فوقه.
    existing_marks = {
        (row[0], row[1])
        for row in (await session.execute(
            select(FactCandidate.field_key, FactCandidate.locator)
            .where(FactCandidate.tenant_id == tenant_id,
                   FactCandidate.extraction_run_id == run.id)
        )).all()
    }

    candidates = 0
    for value in deterministic_extract(views, filename=file_record.original_filename):
        if (value.field_key, value.locator) in existing_marks:
            continue
        existing_marks.add((value.field_key, value.locator))
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
        # **ورفضُ الإرسال ليس فشلًا، ولا هو انتظار.** من قرّر ألّا يُرسل
        # رسالته انتهى الخطُّ عنده بمرشّحاتٍ محلّية يراجعها؛ ومن لم يقرّر
        # بعدُ ينتظر قراره. وحالان لا واحدة.
        await processing.mark(
            session, tenant_id=tenant_id, file_id=file_record.id,
            state=(processing.READY_FOR_REVIEW if consent_state == "declined"
                   else processing.AWAITING_CONSENT))

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
    await processing.mark(session, tenant_id=tenant_id, file_id=run.file_id,
                          state=processing.READY_FOR_REVIEW)
    if failed:
        # فشل قسم لا يُسقط ما نجح: الأقسام الأخرى تبقى، ويُبلَّغ عن الفاشل
        # باسمه (§29). فرسالةٌ استُخرج منها ستة أقسام من سبعة أنفع من لا شيء.
        run.error = ("partial: " + "; ".join(failed))[:500]
    return run


class _SectionAmbiguous(Exception):
    """عُبِر حدُّ المزوّدِ ثمّ انقطع — **ولا يُقال أخفق ولا لم يُنفَّذ**."""


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
    claim: processing.ProcessingClaim | None = None,
    subject_id: uuid.UUID | None = None,
    ledger_maker=None,
    checksum_sha256: str | None = None,
    provider_name: str = "unknown",
    model_name: str | None = None,
    capability: str | None = None,
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
    # **جلسةُ السِّجلِّ الداخليِّ تحمل سياقَ الفاعلِ التقنيِّ الثابت.**
    # `idempotency_records` وحدها محكومةٌ بالفاعل في هذا الخطّ؛ وما عداها
    # بالمستأجر. فإن لم يُمرَّر شيءٌ بقي السلوكُ كما كان حرفيًّا.
    ledger_maker = ledger_maker or session_maker
    subject_id = subject_id if subject_id is not None else actor_user_id

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

    # ── الأقسام: لكلٍّ جيلُ تنفيذٍ خاصٌّ به (RC-T1-H2-B5) ──
    #
    # الشكل لكلِّ قسم:
    #
    #   تحضيرٌ محلّيّ → بوّابةُ الجيل → تفويضُ المزوّد → **وسمُ العبور يُودَع**
    #   → نداءُ المزوّد → معاملةٌ واحدةٌ تحفظ المرشّحاتِ وتُثبّت تمامَ القسم.
    #
    # والوسمُ يُودَع في معاملةٍ تُغلق **قبل** النداء، فسقوطُ العمليّةِ أثناء
    # الانتظار يترك أثرًا يقول «قد نُفِّذ ولا نعلم» — فلا يُعاد النداءُ تحت
    # الجيل نفسِه.
    plans = plan_sections(prepared.views)
    failed: list[str] = []
    candidates = prepared.candidates
    attempted: set[str] = set()
    unresolved: list[str] = []

    # **والسِّجلُّ يخصّ جيلَ معالجة.** فبلا مطالبةٍ لا جيلَ يُفنَّد، ويبقى
    # المسلكُ القديمُ حرفيًّا — وهو ما تسلكه فحوصُ الوحدةِ للخطِّ نفسِه.
    ledgered = claim is not None

    for plan in plans:
        if not ledgered:
            try:
                result = await model_call(
                    question=plan.prompt,
                    schema=ExtractionBatch.model_json_schema(),
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
            continue

        fingerprint = section_ledger.section_fingerprint(
            run_id=prepared.run_id, section=plan.section.value,
            checksum_sha256=checksum_sha256, prompt=plan.prompt,
            chunks=section_ledger.chunk_identities(plan.chunks),
            field_keys=plan.field_keys, locale=locale,
            provider=provider_name, model=model_name, capability=capability)

        async with ledger_maker() as session:
            gate = await section_ledger.open_section(
                session, tenant_id=tenant_id, subject_id=subject_id,
                run_id=prepared.run_id, section=plan.section.value,
                fingerprint=fingerprint)

        if gate.outcome == "completed":
            # تمّ من قبلُ وأُودعت مرشّحاتُه: **صفرُ نداءٍ وصفرُ إدراج**.
            continue
        if gate.outcome == "unknown":
            # عُبِر الحدُّ ولم يُعرف الأثر: لا يُنادى المزوّدُ ثانيةً تحت
            # هذا الجيل. ومحاولةٌ جديدةٌ مقصودةٌ هي البابُ الوحيد.
            unresolved.append(plan.section.value)
            continue
        if gate.lease is None:
            # قائمٌ لعاملٍ آخر، أو تعارضُ معنًى علميّ — ولا نداءَ في الحالين.
            unresolved.append(plan.section.value)
            continue

        try:
            # **لا جلسة هنا.** ولو بقيت معاملة مفتوحة لعاد العطب نفسه.
            result = await model_call(
                question=plan.prompt,
                schema=ExtractionBatch.model_json_schema(),
                # §7 — محتوى بحثي غير منشور: C2، والبوابة تحكم الإرسال.
                classification="C2",
                locale=locale,
                section=plan.section.value,
                lease=gate.lease,
            )
            batch = ExtractionBatch.model_validate(result)
        except _SectionAmbiguous:
            # عُبِر الحدُّ ثمّ انقطع: أثرٌ لا يُعرف، ولا يُسمّى إخفاقَ مزوّد.
            unresolved.append(plan.section.value)
            continue
        except Exception as exc:  # noqa: BLE001 — قسم يسقط ولا يُسقط غيره
            failed.append(f"{plan.section.value}:{type(exc).__name__}")
            async with ledger_maker() as session:
                await section_ledger.fail_section_pre_external(
                    session, gate.lease, reason=f"pre_external:{type(exc).__name__}")
            continue

        # ══ معاملةٌ واحدة: السياجُ، والمرشّحاتُ، وتمامُ القسم ══
        #
        # **ولا يُثبَّت «تمّ» قبل أن تدوم المرشّحات.** لو سبقها لرأى
        # الاستئنافُ قسمًا تامًّا بلا أثرٍ فتخطّاه، فضاع عملٌ دُفع ثمنُه.
        async with ledger_maker() as session:
            if claim is not None:
                await processing.hold(session, claim, tenant_id=tenant_id)
            accepted, rejected, missing = await absorb(
                session, tenant_id=tenant_id, run_id=prepared.run_id,
                file_id=prepared.file_id, plan=plan, batch=batch,
            )
            await section_ledger.settle_section(
                session, gate.lease, accepted=accepted, rejected=rejected)
        candidates += accepted
        attempted |= missing

    async with session_maker() as session:
        run = await finalize(session, tenant_id=tenant_id,
                             run_id=prepared.run_id,
                             failed=failed + [f"{name}:external_result_unknown"
                                              for name in unresolved])
        status = Status(run.status)

    # ══ ولا يُقال «اكتمل» وقسمٌ لا يُعرف أثرُه (RC-T1-H2-B5) ══
    #
    # فقسمٌ عُبِر حدُّه ثمّ انقطع قد يكون نُفِّذ وقد لا — ولا سبيلَ إلى
    # الجزم. ورفعُ الحال إلى «جاهزة لمراجعتك» يقول للباحث إنّ القراءةَ تمّت،
    # وهي لم تتمّ. فتُقال الحقيقةُ بمفرداتِ الحالِ القائمة، ويبقى له أن
    # يبدأ محاولةً جديدةً مقصودة.
    if unresolved:
        status = Status.EXTRACTION_FAILED

    # ── التنقيب التلقائيّ — بعد أن يُحفظ الاستخراج، لا معه ──
    #
    # **وحدُّ الفشل مرسومٌ هنا بالبنية لا بالنيّة.** التنقيب يقع في معاملةٍ
    # **مستقلّة** تبدأ بعد أن استقرّ الاستخراجُ في القاعدة. فمهما تعثّر —
    # استثناءً كان أو خطأ قاعدة — لا يستطيع أن يتراجع عن الاستخراج ولا أن
    # يُعيد كتابة حاله. فالباحثُ الذي نجح استخراجُ رسالته يبقى سجلُّه
    # يقول ذلك، ومرشّحاتُه مكتوبةٌ مؤصَّلةٌ تنتظر مراجعته.
    if status is Status.AWAITING_REVIEW:
        await _mine_after_extraction(
            session_maker, tenant_id=tenant_id, actor_user_id=actor_user_id,
            file_id=prepared.file_id)

    return PipelineResult(prepared.run_id, status, prepared.chunks, candidates,
                          prepared.excluded,
                          failed + [f"{name}:external_result_unknown"
                                    for name in unresolved],
                          None, tuple(sorted(attempted)))


async def _mine_after_extraction(
    session_maker, *, tenant_id: uuid.UUID, actor_user_id: uuid.UUID,
    file_id: uuid.UUID,
) -> None:
    """يُنقّب فرصَ الرسالة تلقائيًّا — **ولا يُفشل استخراجًا نجح**.

    و`local_only` و`awaiting_consent` لا تبلغ هنا أصلًا: الشرطُ عند المُنادي
    `AWAITING_REVIEW` وحدها. فقرارُ الخصوصية **لا يُنقَّب له ولا يُعلَن
    فشلًا** — لا شيء يقع، ولا شيء يُدَّعى.

    والاستيرادُ داخل الدالّة عمدًا: `services.thesis.mining` يعتمد على
    كتالوج هذه الحزمة، فاستيرادُه في الأعلى حلقةٌ عند الإقلاع.
    """
    from ..thesis import mining, processing as thesis_processing  # noqa: PLC0415

    try:
        async with session_maker() as session:
            thesis = (
                await session.execute(
                    select(Thesis)
                    .where(Thesis.tenant_id == tenant_id, Thesis.file_id == file_id)
                    .with_for_update())
            ).scalar_one_or_none()
            if thesis is None:
                return
            # **ولا يُكتب على سجلٍّ أخفاه الباحث.** الأرشفةُ قرارٌ وقع بينما
            # كان الاستخراجُ يجري، ويُحترم.
            if thesis.archived_at is not None:
                return
            if thesis.processing_state in thesis_processing.IN_FLIGHT:
                return
            # **والحدُّ يُضبط هنا: بعد قفلِ الصفّ، وقبل التنقيب.**
            #
            # وترتيبُه مقصودٌ حرفًا بحرف. لو سبق `FOR UPDATE` لصار تنقيبٌ
            # آخر مشروعٌ على الصفّ نفسه «فشلًا» لمجرّد أنّه انتظر دورَه —
            # وتسلسلُ الصفّ يجب أن يبقى انتظارًا لا فشلًا. فالحدُّ يقع على
            # ما **بعد** القفل، وأوّلُه القفلُ الاستشاريّ لسلسلة التدقيق.
            #
            # و`set_config(..., true)` محلّيٌّ للمعاملة: ينتهي بانتهائها،
            # ولا يتسرّب إلى اتصالٍ يعود إلى التجمّع.
            await session.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": f"{AUTO_MINING_LOCK_TIMEOUT_MS}ms"},
            )
            await mining.run(session, tenant_id=tenant_id,
                             actor_user_id=actor_user_id, thesis=thesis)
    except Exception as error:  # noqa: BLE001 — الحدُّ نفسه هو المقصود
        # **يُسجَّل على محور التنقيب وحده.** ولا نصَّ مستندٍ ولا رسالةَ
        # استثناءٍ خام في العمود: نوعُ الخطأ يكفي لمعرفة أين يُنظر.
        await _record_mining_failure(
            session_maker, tenant_id=tenant_id, file_id=file_id,
            code=type(error).__name__[:64])


async def _record_mining_failure(
    session_maker, *, tenant_id: uuid.UUID, file_id: uuid.UUID, code: str,
) -> None:
    """يكتب `mining_state='failed'` — **ولا يمسّ حالَ الاستخراج**."""
    from ..thesis import mining  # noqa: PLC0415

    try:
        async with session_maker() as session:
            thesis = (
                await session.execute(
                    select(Thesis)
                    .where(Thesis.tenant_id == tenant_id, Thesis.file_id == file_id)
                    .with_for_update())
            ).scalar_one_or_none()
            if thesis is None:
                return
            thesis.mining_state = mining.FAILED
            thesis.mining_last_error = code
    except Exception:  # noqa: BLE001, S110 — تسجيلُ الفشل لا يُفشل شيئًا بدوره
        pass


async def ensure_thesis_for_file(
    session: AsyncSession, *, tenant_id: uuid.UUID, file_id: uuid.UUID,
) -> tuple[Thesis, bool]:
    """سجل الرسالة — يُنشأ مرة واحدة لكل ملف (§4، §5).

    ويُنشأ بلا عنوان ولا درجة: `NULL` تعني «لم يُستخرَج بعد» — واسم الملف
    عنوانًا أو درجةً مخمَّنة اختلاقٌ يمنعه §11.

    ## والتكرارُ يُمنع بالتسلسلِ في القاعدة، لا بالبحثِ وحده (RC-T1-H2-B5)

    **وكان التعليقُ يدّعي أنّ البحثَ قبل الإنشاء يكفي.** لا يكفي: طلبان
    متزامنان على الملفّ نفسِه يقرآن «لا شيء» معًا فيُدرجان صفَّين، و
    `theses.file_id` **بلا قيدِ تفرّد** — فُحص ذلك في القاعدة الحيّة. فرسالتان
    لملفٍّ واحد: بطاقتان في الشاشة، وحالان تتقدّمان على التوازي، ومرشّحاتٌ
    تنقسم بينهما.

    فيُقفَل صفُّ **الملفّ** أوّلًا (`SELECT … FOR UPDATE`). والملفُّ هو
    المرساةُ الصحيحة: هو المفتاحُ الذي نتفرّد عليه، وهو قائمٌ قبل الرسالة.
    فالثاني ينتظر الأوّلَ ثمّ يقرأ ما أودعه — فيجد رسالةً ويعيدها.
    """
    # **والقفلُ على صفٍّ قائمٍ لا على الرسالةِ المنشودة.** قفلُ صفٍّ غيرِ
    # موجودٍ لا يمنع إدراجَ غيره؛ وقفلُ الملفِّ يُسلسِل كلَّ من يقصده.
    anchored = (await session.execute(
        select(File.id).where(File.id == file_id, File.tenant_id == tenant_id)
        .with_for_update()
    )).scalar_one_or_none()
    if anchored is None:
        raise NotFound("file.not_found")

    existing = (
        await session.execute(select(Thesis).where(Thesis.file_id == file_id)
                              .order_by(Thesis.created_at.asc()))
    ).scalars().all()
    if len(existing) > 1:
        # **ولا تُخمَّن الصحيحةُ من بين مكرَّرتَين تاريخيّتَين.** ثالثةٌ لا
        # تُصنع، والطلبُ يُردّ بحقيقته ليُعالَج بيدٍ واعية.
        raise AtheraError("thesis.duplicate_for_file", status_code=409,
                          file_id=str(file_id), count=len(existing))
    if existing:
        return existing[0], False

    thesis = Thesis(tenant_id=tenant_id, file_id=file_id, title_ar=None, degree=None)
    session.add(thesis)
    await session.flush()
    return thesis, True


def content_fingerprint(data: bytes) -> str:
    """بصمة المحتوى — لمنع إعادة معالجة المطابق بلا داعٍ (§27)."""
    return hashlib.sha256(data).hexdigest()
