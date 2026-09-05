"""حالُ معالجة الرسالة | The persisted thesis processing state (Wave 1-C).

**العطب الذي يعالجه هذا الملفّ عطبُ صدقٍ لا عطبُ حساب.** كانت الشاشة تقرأ
حالَ آخر تشغيلة استخراج على ملفٍّ (`extraction_runs.status`) وتعرضها حالًا
للرسالة. وثلاثةُ أشياء تنكسر بذلك:

  • **رسالةٌ بلا تشغيلة لا حال لها** — فتُعرض بلا شيء، ولا يعرف الباحث
    أرُفعت للتوّ أم وقف عنها النظام. و`NULL` هنا لم تكن «لم يُستخرَج بعد»
    بل «لا أدري».
  • **حالُ التشغيلة تصف تشغيلة لا رسالة.** إعادةُ القراءة تُنشئ صفًّا
    جديدًا، فتقفز الحال إلى الوراء بلا أن يقع شيء على الرسالة نفسها.
  • **والفشل كان يُعرض صفرًا.** «٠ أقسام · ٠ فرص» جملةٌ تُقال في ستّ حالاتٍ
    مختلفة معناها مختلف: لم يبدأ التحليل، ويجري، ولا طبقة نصّ، وبانتظار
    إذن، وسقط، وتمّ فلم يجد. **والفشل ليس فراغًا، وما لم يبدأ ليس نتيجةً
    صفرية.**

فالحال تُحفَظ في `theses.processing_state` عمودًا أوّليًّا، وتُنقل بانتقالٍ
مسمّى، وتحمل معها سببَ فشلها إن سقطت.

## ولا OCR في هذه المرحلة — **ويُقال ذلك ولا يُتظاهَر بغيره**

`text_layer_missing` حالٌ قائمة بذاتها لا نوعٌ من `failed`: المستند سليم،
والقارئ سليم، والذي لا يوجد هو **طبقةُ نصّ** فيه. وإعادةُ المحاولة عليها
لا تغيّر شيئًا، فتُردّ صراحةً بدل أن تُعرض زرًّا يَعِد ولا يفعل.

و`ocr_state` عمودٌ محفوظٌ افتراضُه `unavailable` — عقدٌ لمرحلةٍ قادمة يُقرأ
اليوم فيقول «لم يقع OCR»، ولا يوجد في هذا المستودع مسارٌ واحد يكتب فيه
غير ذلك.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.thesis import Thesis

# ═════════════════════ ١. مفردةُ الحال ═════════════════════
#
# **تسعُ حالاتٍ مغلقة، والقاعدة تحرسها بقيد.** ونصٌّ حرّ هنا يعني حالًا
# عاشرة تظهر يومًا في الشاشة بلا ترجمة ولا معنى.

UPLOADED: Final = "uploaded"                      # حُفظ الملف، ولم يُطلب شيء بعد
QUEUED: Final = "queued"                          # طُلبت المعالجة ولم تبدأ
PARSING: Final = "parsing"                        # جارٍ قراءة المستند
EXTRACTING: Final = "extracting"                  # جارٍ استخراج بنية الرسالة
AWAITING_CONSENT: Final = "awaiting_consent"      # القراءة المحلية تمّت، والإذن معلّق
READY_FOR_REVIEW: Final = "ready_for_review"      # مرشّحاتٌ تنتظر مراجعتك
COMPLETED: Final = "completed"                    # اكتملت المراجعة
FAILED: Final = "failed"                          # سقطت المعالجة، وللسقوط سبب
TEXT_LAYER_MISSING: Final = "text_layer_missing"  # لا طبقة نصّ — ولا OCR بعد

PROCESSING_STATES: Final[tuple[str, ...]] = (
    UPLOADED, QUEUED, PARSING, EXTRACTING, AWAITING_CONSENT,
    READY_FOR_REVIEW, COMPLETED, FAILED, TEXT_LAYER_MISSING,
)

#: حالاتٌ يجري فيها عملٌ الآن — **وطلبُ معالجةٍ ثانية عليها يُردّ**، فلا
#: تشغيلتان على ملفٍّ واحد تكتبان مرشّحاتٍ مضاعفة.
IN_FLIGHT: Final[tuple[str, ...]] = (QUEUED, PARSING, EXTRACTING)

#: حالاتُ الفشل — وهي **حالان لا واحدة**، ومعالجتهما مختلفة.
FAILURE_STATES: Final[tuple[str, ...]] = (FAILED, TEXT_LAYER_MISSING)

#: من هذه الحالات تُقبل إعادة المحاولة. و`text_layer_missing` ليست منها
#: عمدًا: إعادةُ قراءةِ مستندٍ ممسوحٍ ضوئيًّا تُنتج النتيجة نفسها حرفيًّا،
#: وزرٌّ يَعِد بذلك يخذل. فيُقال إن OCR غير متاح، ولا يُعرض الزرّ.
RETRYABLE: Final[tuple[str, ...]] = (
    UPLOADED, AWAITING_CONSENT, READY_FOR_REVIEW, COMPLETED, FAILED,
)


# ═════════════════════ ٢. مفردةُ سبب الفشل ═════════════════════
#
# **رمزٌ تقنيّ آمن، لا رسالة استثناء.** رسالةُ الاستثناء قد تحمل مقتطفًا من
# مستند الباحث؛ والرمز لا يحمل إلا صنف العطب. والعربية تُشتقّ من الرمز في
# موضعٍ واحد، فلا تفترق ترجمةٌ عن حالٍ بأول تعديل.

FAILURE_CODES: Final[tuple[str, ...]] = (
    "text_layer_missing",     # مستندٌ ممسوح ضوئيًّا بلا طبقة نصّ
    "unsupported_document",   # نوعٌ لا يقرؤه المفكِّك
    "file_missing",           # صفُّ الملف أو كائنه غير موجود
    "storage_unavailable",    # تعذّر جلب الملف من المخزن
    "parse_failed",           # سقط التفكيك لسببٍ آخر
    "extraction_failed",      # قُرئ المستند ولم يُستخرَج منه
    "unknown",                # لم يُصنَّف — ويُقال ذلك ولا يُخمَّن
)

FAILURE_LABELS: Final[dict[str, tuple[str, str]]] = {
    "text_layer_missing": (
        "المستند ممسوح ضوئيًّا بلا طبقة نصّ، ولا تتوفّر قراءة ضوئية (OCR) بعد.",
        "The document is scanned with no text layer, and OCR is not available yet.",
    ),
    "unsupported_document": (
        "نوع الملف لا يمكن قراءته.",
        "This file type cannot be read.",
    ),
    "file_missing": (
        "لم يُعثر على الملف المرتبط بهذه الرسالة.",
        "The file attached to this thesis was not found.",
    ),
    "storage_unavailable": (
        "تعذّر جلب الملف من المخزن.",
        "The file could not be fetched from storage.",
    ),
    "parse_failed": (
        "تعذّرت قراءة المستند.",
        "The document could not be read.",
    ),
    "extraction_failed": (
        "قُرئ المستند ولم يكتمل استخراج بنيته.",
        "The document was read but its structure could not be extracted.",
    ),
    "unknown": (
        "توقّفت المعالجة لسببٍ غير مصنَّف — والسجلّ التقني يحمل تفصيله.",
        "Processing stopped for an unclassified reason; the technical log carries the detail.",
    ),
}


# ═════════════════════ ٣. عقدُ OCR المؤجَّل ═════════════════════
#
# **لا OCR في هذا السبرنت، والعمود يبقى ليقول ذلك صراحةً.** والافتراض
# `unavailable`: لا «لم يُحاوَل» ولا «معلَّق» — فكلاهما يوحي بمسارٍ قائم.

OCR_UNAVAILABLE: Final = "unavailable"
OCR_STATES: Final[tuple[str, ...]] = (
    OCR_UNAVAILABLE, "not_attempted", "queued", "completed", "failed",
)

TEXT_LAYER_NOT_CHECKED: Final = "not_checked"
TEXT_LAYER_PRESENT: Final = "present"
TEXT_LAYER_ABSENT: Final = "absent"
TEXT_LAYER_STATES: Final[tuple[str, ...]] = (
    TEXT_LAYER_NOT_CHECKED, TEXT_LAYER_PRESENT, TEXT_LAYER_ABSENT,
)


# ═════════════════════ ٤. النصّ المعروض للحال ═════════════════════
#
# **ولا نسبةٌ مئوية في هذا الملفّ ولا في الشاشة.** خطُّ الأنابيب لا يقيس
# تقدّمًا — لا يعرف كم قسمًا في المستند قبل أن يقرأه — ورقمٌ يُعرض بلا
# قياسٍ خلفه اختلاقٌ صغير يتكرّر ألف مرّة. فالحال تُقال بالكلمة.

STATE_LABELS: Final[dict[str, tuple[str, str]]] = {
    UPLOADED: ("رُفع الملف", "File uploaded"),
    QUEUED: ("في انتظار الدور", "Queued"),
    PARSING: ("جارٍ قراءة المستند", "Reading the document"),
    EXTRACTING: ("جارٍ استخراج بنية الرسالة", "Extracting the thesis structure"),
    AWAITING_CONSENT: ("بانتظار إذنك", "Awaiting your approval"),
    READY_FOR_REVIEW: ("جاهزة لمراجعتك", "Ready for review"),
    COMPLETED: ("اكتمل التحليل", "Analysis complete"),
    FAILED: ("تعذّر التحليل", "Analysis failed"),
    TEXT_LAYER_MISSING: ("لا توجد طبقة نصّ في المستند", "The document has no text layer"),
}


# ═════════════════════ ٥. سببُ الرقم، لا الرقم وحده ═════════════════════
#
# **«٠ أقسام · ٠ فرص» ليست معلومة.** ستُّ حالاتٍ تُنتجها ومعناها مختلف،
# والباحث يحتاج أيّها وقع. فيُرافق كلَّ عددٍ سببُه.

OUTCOME_NOT_STARTED: Final = "not_started"
OUTCOME_RUNNING: Final = "running"
OUTCOME_NO_TEXT_LAYER: Final = "no_text_layer"
OUTCOME_AWAITING_CONSENT: Final = "awaiting_consent"
OUTCOME_FAILED: Final = "failed"
OUTCOME_COMPLETED_EMPTY: Final = "completed_empty"
OUTCOME_FOUND: Final = "found"

OUTCOMES: Final[tuple[str, ...]] = (
    OUTCOME_NOT_STARTED, OUTCOME_RUNNING, OUTCOME_NO_TEXT_LAYER,
    OUTCOME_AWAITING_CONSENT, OUTCOME_FAILED, OUTCOME_COMPLETED_EMPTY, OUTCOME_FOUND,
)

SECTION_OUTCOME_LABELS: Final[dict[str, tuple[str, str]]] = {
    OUTCOME_NOT_STARTED: ("لم يبدأ التحليل بعد", "Analysis has not started"),
    OUTCOME_RUNNING: ("التحليل جارٍ الآن", "Analysis is running"),
    OUTCOME_NO_TEXT_LAYER: ("لا طبقة نصّ تُقرأ في المستند", "No readable text layer"),
    OUTCOME_AWAITING_CONSENT: ("بانتظار إذنك قبل المتابعة", "Awaiting your approval"),
    OUTCOME_FAILED: ("تعذّر التحليل — والسبب مذكور", "Analysis failed; the reason is stated"),
    OUTCOME_COMPLETED_EMPTY: (
        "اكتمل التحليل ولم يُعثر على قسمٍ قابل للاستخراج",
        "Analysis completed and found no extractable section",
    ),
    OUTCOME_FOUND: ("أقسام مستخرجة", "Sections extracted"),
}

OPPORTUNITY_OUTCOME_LABELS: Final[dict[str, tuple[str, str]]] = {
    OUTCOME_NOT_STARTED: ("لم يبدأ استخراج الفرص بعد", "Opportunity mining has not started"),
    OUTCOME_RUNNING: ("التحليل جارٍ الآن", "Analysis is running"),
    OUTCOME_NO_TEXT_LAYER: ("لا طبقة نصّ تُقرأ في المستند", "No readable text layer"),
    OUTCOME_AWAITING_CONSENT: ("بانتظار إذنك قبل المتابعة", "Awaiting your approval"),
    OUTCOME_FAILED: ("تعذّر التحليل — والسبب مذكور", "Analysis failed; the reason is stated"),
    OUTCOME_COMPLETED_EMPTY: (
        "اكتمل الفحص ولم يُعثر على فرصةٍ مرشَّحة",
        "The scan completed and found no candidate opportunity",
    ),
    OUTCOME_FOUND: ("فرص مرشَّحة", "Candidate opportunities"),
}


def section_outcome(state: str, sections: int) -> str:
    """لماذا عددُ الأقسام هو ما هو — **لا الرقم وحده**."""
    if state == TEXT_LAYER_MISSING:
        return OUTCOME_NO_TEXT_LAYER
    if state == FAILED:
        return OUTCOME_FAILED
    if sections:
        return OUTCOME_FOUND
    if state == AWAITING_CONSENT:
        return OUTCOME_AWAITING_CONSENT
    if state in IN_FLIGHT:
        return OUTCOME_RUNNING
    if state == UPLOADED:
        return OUTCOME_NOT_STARTED
    return OUTCOME_COMPLETED_EMPTY


def opportunity_outcome(state: str, found: int, mined_at: dt.datetime | None) -> str:
    """لماذا عددُ الفرص هو ما هو.

    **و«لم يُنقَّب بعد» ليست نتيجةً صفرية.** ولذلك يُحفظ
    `opportunities_mined_at`: بدونه لا سبيل إلى التمييز بين تنقيبٍ لم يقع
    وتنقيبٍ وقع فلم يجد — وهما خبران مختلفان تمامًا للباحث.
    """
    if found:
        return OUTCOME_FOUND
    if mined_at is not None:
        return OUTCOME_COMPLETED_EMPTY
    if state == TEXT_LAYER_MISSING:
        return OUTCOME_NO_TEXT_LAYER
    if state == FAILED:
        return OUTCOME_FAILED
    if state == AWAITING_CONSENT:
        return OUTCOME_AWAITING_CONSENT
    if state in IN_FLIGHT:
        return OUTCOME_RUNNING
    return OUTCOME_NOT_STARTED


# ═════════════════════ ٦. هويّةُ البطاقة ═════════════════════

def display_title(title_ar: str | None, title_en: str | None,
                  filename: str | None, locale: str) -> tuple[str | None, bool]:
    """ما يُكتب على البطاقة، **ومعه هل هو عنوانٌ مستخرَج أم اسمُ ملفّ**.

    **العطب: رصّةُ بطاقاتٍ متطابقة تقول «لم يُستخرَج العنوان بعد».** خمسُ
    رسائل مرفوعة تصير خمسَ بطاقاتٍ لا يفرّق بينها شيء، فلا يعرف الباحث
    أيَّها ملفُّه.

    **ولا يُحلّ ذلك بجعل اسم الملفّ عنوانًا.** `theses.title_ar` يبقى
    `NULL` كما هو (ترحيل 0015)، ولا يُكتب فيه اسم ملفّ أبدًا. الذي يُضاف
    هو **حقلُ عرضٍ ثانٍ** ومعه رايةٌ صريحة `title_is_extracted`: فالشاشة
    تعرف أنّها تعرض اسم ملفّ وتقوله، والعقد لا يدّعي استخراجًا لم يقع.
    """
    extracted = (title_en or title_ar) if locale == "en" else title_ar
    if extracted:
        return extracted, True
    name = (filename or "").strip()
    return (name or None), False


# ═════════════════════ ٧. الانتقال — كتابةٌ واحدة مسمّاة ═════════════════════

class ProcessingConflict(Exception):
    """طلبُ معالجةٍ مرفوض — بسببه ورمزه، لا بصمت."""

    def __init__(self, code: str, *, state: str | None) -> None:
        self.code = code
        self.state = state
        super().__init__(code)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def mark(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    thesis_id: uuid.UUID | None = None,
    file_id: uuid.UUID | None = None,
    state: str,
    failure_code: str | None = None,
    failure_detail: str | None = None,
    text_layer: str | None = None,
) -> None:
    """يثبّت حالَ رسالةٍ — **بعبارةٍ واحدة، وبلا قراءةٍ قبلها**.

    والرسالة تُبلَغ بمعرّفها أو بمعرّف ملفّها: خطُّ الأنابيب يعرف الملفّ
    ولا يحمل معرّف الرسالة، وقراءتُه أوّلًا رحلةٌ ثانية إلى مومباي بلا داعٍ.

    **والفشل يحمل سببه أو لا يُكتب.** القاعدة تفرض ذلك بقيد
    `failure_is_named`؛ والفحص هنا يجعل الرسالة مفهومةً قبل أن تصل إليه.
    """
    if state not in PROCESSING_STATES:
        raise ValueError(f"unknown processing state: {state}")
    if state in FAILURE_STATES and failure_code is None:
        raise ValueError(f"state {state} must carry a failure code")
    if state not in FAILURE_STATES and failure_code is not None:
        raise ValueError(f"state {state} must not carry a failure code")
    if failure_code is not None and failure_code not in FAILURE_CODES:
        raise ValueError(f"unknown failure code: {failure_code}")

    values: dict[str, object] = {
        "processing_state": state,
        "processing_state_changed_at": _now(),
        # النجاح يمحو سببَ فشلٍ سابق: صفٌّ يقول «جاهزة» ويحمل رمز سقوطٍ
        # قديم يُقرأ متناقضًا، والقيد يرفضه أصلًا.
        "failure_code": failure_code,
        "failure_detail": (failure_detail or None) if failure_code else None,
    }
    if text_layer is not None:
        if text_layer not in TEXT_LAYER_STATES:
            raise ValueError(f"unknown text layer state: {text_layer}")
        values["text_layer_state"] = text_layer

    # `synchronize_session=False`: الصفّ قد يكون محمَّلًا في الجلسة، ومزامنته
    # تكلّف عبارةً إضافية — رحلةً كاملة إلى مومباي — لتحديث نسخةٍ في الذاكرة
    # لا تُقرأ بعد هذه الكتابة. والقيمة المعتمَدة هي ما في القاعدة.
    statement = (update(Thesis).where(Thesis.tenant_id == tenant_id)
                 .values(**values)
                 .execution_options(synchronize_session=False))
    if thesis_id is not None:
        statement = statement.where(Thesis.id == thesis_id)
    elif file_id is not None:
        statement = statement.where(Thesis.file_id == file_id)
    else:  # pragma: no cover — خطأ برمجيّ لا حالُ تشغيل
        raise ValueError("mark() needs either thesis_id or file_id")
    await session.execute(statement)


async def claim_for_processing(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
) -> str:
    """يحجز الرسالة للمعالجة — **أو يقول لماذا لا**.

    **والحجز شرطٌ في عبارة الكتابة نفسها، لا فحصٌ قبلها.** فحصٌ ثمّ كتابةٌ
    نافذتان: طلبان متزامنان يقرآن «ساقطة» معًا فيجدولان تشغيلتين على الملفّ
    نفسه، فتتضاعف المرشّحات ويُحاسب الباحث على ضغطةٍ مكرّرة. و
    `UPDATE … WHERE processing_state IN (…)` يجعل القاعدة هي الحَكَم: الأوّل
    يصيب صفًّا، والثاني يصيب صفرًا فيُردّ.

    يعيد الحال السابقة عند النجاح، ويرفع `ProcessingConflict` عند الرفض.
    """
    current = (
        await session.execute(
            select(Thesis.processing_state)
            .where(Thesis.id == thesis_id, Thesis.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if current is None:
        raise ProcessingConflict("thesis.not_found", state=None)
    if current == TEXT_LAYER_MISSING:
        raise ProcessingConflict("thesis.retry_needs_ocr", state=current)
    if current in IN_FLIGHT:
        raise ProcessingConflict("thesis.processing_in_flight", state=current)

    claimed = await session.execute(
        update(Thesis)
        .where(Thesis.id == thesis_id, Thesis.tenant_id == tenant_id,
               Thesis.processing_state.in_(RETRYABLE))
        .values(processing_state=QUEUED, processing_state_changed_at=_now(),
                processing_attempts=Thesis.processing_attempts + 1,
                failure_code=None, failure_detail=None)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        # سبقنا إليها طلبٌ آخر بين القراءة والكتابة — والقاعدة حسمت.
        raise ProcessingConflict("thesis.processing_in_flight", state=current)
    return current


#: الحالاتُ التي يجوز للمسار القديم أن يرفعها إلى «جاهزة لمراجعتك».
#:
#: **وما عداها لا يُمسّ.** `awaiting_consent` بوابةُ إذنٍ مستقلّة لا تُقفز
#: بأثرٍ جانبيّ لعمليةٍ أخرى (DIC2)، و`ready_for_review` و`completed` أبعدُ
#: من التفكيك فلا يُرجَعان إليه، والحالاتُ الجارية ليست له أصلًا.
LEGACY_PARSE_MAY_SETTLE: Final[tuple[str, ...]] = (
    UPLOADED, FAILED, TEXT_LAYER_MISSING,
)


async def settle_after_legacy_parse(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
) -> None:
    """يثبّت حالَ رسالةٍ بعد تفكيكٍ قديمٍ نجح — **بعبارةٍ شرطيّةٍ واحدة**.

    ## العطب: المسار القديم كان يكتب حالًا بائتة فوق حالٍ أحدث

    `POST /theses/{id}/parse` يقرأ `processing_state` في أوّل الطلب، ثمّ
    يجلب الملفّ من المخزن ويفكّكه — وذاك عملٌ طويل — ثمّ يكتب:

        settled = READY_FOR_REVIEW if <القيمة المقروءة> in (…) else <القيمة المقروءة>
        mark(state=settled)                    # UPDATE بلا شرطٍ على الحال

    فإن تقدّم الخطُّ الحديث في تلك النافذة — من `extracting` إلى
    `ready_for_review` — كتب التفكيكُ فوقه `extracting` مرّةً أخرى.
    **والبطاقة تتراجع من المراجعة إلى «جارٍ الاستخراج» بلا أن يقع شيء**،
    وتبقى كذلك: لا مهمّة تعمل لترفعها، فتُعرض حالٌ جاريةٌ إلى الأبد.

    ## والعلاج: القاعدة هي التي تقرأ الحال، وقت الكتابة

    عبارةٌ واحدة بـ`CASE`، فلا فجوةَ بين القراءة والقرار:

      • الحالُ ترتفع إلى `ready_for_review` **إن كانت وقتئذٍ** من
        `LEGACY_PARSE_MAY_SETTLE` — وما عداها يبقى كما هو حرفيًّا.
      • و`text_layer_state` تصير `present` دائمًا: تفكيكٌ نجح **واقعةٌ
        أثبتها هذا الطلب** مهما تكن حالُ الرسالة.
      • ورمزُ الفشل يُمحى: صفٌّ يقول «تعذّرت القراءة» وقد قُرئ للتوّ يُقرأ
        كذبًا، وقيدُ `failure_is_named` يرفضه أصلًا.

    **والعبارةُ واحدةٌ لا اثنتان لسببٍ يخصّ القاعدة**: قيد
    `missing_text_layer_says_so` يشترط أن تلازم `text_layer_missing`
    قيمةَ `text_layer_state='absent'`. فكتابةُ `present` في عبارةٍ ثمّ رفعُ
    الحال في أخرى تمرّ بلحظةٍ يرفضها القيد. وهنا يقعان معًا على الصفّ نفسه.
    """
    advances = ", ".join(f"'{state}'" for state in LEGACY_PARSE_MAY_SETTLE)
    await session.execute(
        text(
            f"UPDATE theses SET "
            f"  processing_state = CASE WHEN processing_state IN ({advances}) "
            f"                          THEN :settled ELSE processing_state END, "
            f"  processing_state_changed_at = CASE WHEN processing_state IN ({advances}) "
            f"                          THEN :now ELSE processing_state_changed_at END, "
            f"  failure_code = NULL, "
            f"  failure_detail = NULL, "
            f"  text_layer_state = :present "
            f"WHERE id = :thesis_id AND tenant_id = :tenant_id"
        ),
        {"settled": READY_FOR_REVIEW, "now": _now(), "present": TEXT_LAYER_PRESENT,
         "thesis_id": thesis_id, "tenant_id": tenant_id},
    )
