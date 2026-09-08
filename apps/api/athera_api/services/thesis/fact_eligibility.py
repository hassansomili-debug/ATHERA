"""أهليّةُ الحقيقة للتنقيب | Which canonical facts are safe to mine.

**تحوّلٌ في السياسة، لا تخفيفٌ للحراسة.** كان الشرطُ أن يعتمد الباحثُ كلَّ
حقيقةٍ بيده قبل أن تصل المنقّب. والمبدأ الآن: **الباحثُ يعتمد القراراتِ
العلمية، لا كلَّ استخراجٍ آليٍّ وسيط.** فسقط `status == "approved"` شرطًا،
وسقطت معه الحمايةُ التي كان يوفّرها.

**فالتصنيفُ هنا هو ما يحمل تلك الحماية وحده.** لم يعد بين تخمينِ آلةٍ
وفرصةِ نشرٍ محفوظةٍ إلّا هذا الملفّ. ولذلك: الاستبعادُ هو الأصل، والأهليّةُ
استثناءٌ يُستحقّ بشروطٍ كلُّها لازمة.

## أربعُ حالاتٍ تشغيليّة — لا أحكامٌ على صحّةٍ علمية

  `AUTO_ELIGIBLE`    تصلح مدخلًا للمنقّب.
  `SUPPORT_ONLY`     تُعين على السياق والترتيب، **ولا تُنشئ فرصةً وحدها**.
  `REVIEW_REQUIRED`  تعارضٌ مادّيّ أو رايةُ مراجعة — يُحجب **المفهومُ
                     المعنيّ وحده**، ولا تُعطَّل الرسالة كلُّها.
  `EXCLUDED`         لا تدخل شيئًا.

## محوران لا محور

**وقرارُ خصوصيّةٍ لا يُعرض فشلَ استخراج.** حالُ التشغيل (`processing_scope`)
شيء، وجودةُ الدليل شيءٌ آخر. فباحثٌ رفض إرسالَ رسالته إلى مزوّدٍ خارجي
تمّت قراءتُه المحلّية، ولم يقع استخراجٌ متقدّم — **قرارُه محترمًا**، لا
عطبًا يُقال له. ولا تصير بياناتُ الوصف المحلّية دليلًا علميًّا يُنقَّب.

## الثقةُ ثقةُ استخراجٍ لا ثقةُ علم

`0.99` تقول «قرأتُ هذا النصَّ من المستند على الأرجح». لا تشتري تجاوزًا
لعطبٍ في التأصيل ولا لرايةِ مراجعة ولا لشكلٍ فاسد:

  ‏`0.99` مع `ambiguous`     → `REVIEW_REQUIRED`
  ‏`0.99` مع `needs_review`  → `REVIEW_REQUIRED`
  ‏`0.99` مع اقتباسٍ غير مؤصَّل → `EXCLUDED`
  ‏`0.99` مع قيمةٍ فاسدة الشكل → `EXCLUDED`

**ولا تُرفع حقيقةٌ ضعيفة لأنّ المنقّبَ يشتهي دليلًا.**
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from typing import Final

from ...models.research import DocumentChunk, ExtractionRun, FactCandidate, ResearcherMemory
from ..document_intelligence.fields import FIELD_CATALOGUE
from ..extraction.base import quote_is_grounded

# ═════════ الحالاتُ الأربع ═════════

AUTO_ELIGIBLE: Final = "auto_eligible"
SUPPORT_ONLY: Final = "support_only"
REVIEW_REQUIRED: Final = "review_required"
EXCLUDED: Final = "excluded"

# ═════════ محورُ التشغيل — منفصلٌ عن محور الجودة ═════════
#
# **ولا حالَ تُخترع هنا.** كان `"succeeded"` مكتوبًا في هذه المجموعة ولا
# كاتبَ له في التطبيق كلّه: لا مسارَ في خطّ المعالجة يُنتجه. فكانت
# التجهيزاتُ تزرعه، فتمرّ الفحوصُ خضراءَ على حالٍ لا تقع في الإنتاج — وهو
# أسوأُ من فحصٍ ساقط: فحصٌ يطمئن على ما لم يُفحص.
#
# فالمجموعةُ الآن ما يكتبه `document_intelligence/pipeline.py` فعلًا.

ADVANCED_EVIDENCE_RUNS: Final[frozenset[str]] = frozenset({"awaiting_review", "verified"})

#: **ليست فشلًا.** القراءةُ المحلّية تمّت، ولم يقع استخراجٌ متقدّم — إمّا
#: لأنّ الباحث رفض الإرسال الخارجي، أو لأنّه لم يقرّر بعد.
LOCAL_SCOPE_RUNS: Final[frozenset[str]] = frozenset({"local_only", "awaiting_consent"})

FAILED_RUNS: Final[frozenset[str]] = frozenset({"parse_failed", "extract_failed"})
IN_FLIGHT_RUNS: Final[frozenset[str]] = frozenset({"parsing", "parsed", "extracting"})

SCOPE_ADVANCED: Final = "advanced_extraction"
SCOPE_LOCAL_ONLY: Final = "local_deterministic_only"
SCOPE_AWAITING_CONSENT: Final = "awaiting_consent"
SCOPE_FAILED: Final = "extraction_failed"
SCOPE_IN_FLIGHT: Final = "extraction_in_flight"
SCOPE_UNKNOWN: Final = "unknown"


def processing_scope(run_status: str | None) -> str:
    """حالُ التشغيل بلغتها — **ولا يُترجَم رفضُ إذنٍ إلى فشل**."""
    if run_status in ADVANCED_EVIDENCE_RUNS:
        return SCOPE_ADVANCED
    if run_status == "local_only":
        return SCOPE_LOCAL_ONLY
    if run_status == "awaiting_consent":
        return SCOPE_AWAITING_CONSENT
    if run_status in FAILED_RUNS:
        return SCOPE_FAILED
    if run_status in IN_FLIGHT_RUNS:
        return SCOPE_IN_FLIGHT
    return SCOPE_UNKNOWN


# ═════════ مفردٌ ومتعدّد — من الكتالوج، لا من قائمةٍ ثانية ═════════
#
# **والمصدرُ واحد.** `FieldSpec.multi` قائمٌ في
# `document_intelligence/fields.py`، وكتابةُ قائمةٍ ثانية هنا تنحرف عنه.

SINGLETON_FIELDS: Final[frozenset[str]] = frozenset(
    spec.key for spec in FIELD_CATALOGUE if not spec.multi)
MULTI_FIELDS: Final[frozenset[str]] = frozenset(
    spec.key for spec in FIELD_CATALOGUE if spec.multi)

# ═════════ حالُ الاستخراج — تُقرأ من داخل `value` ═════════

EXTRACTION_OK: Final = "extracted"
EXTRACTION_REVIEW: Final[frozenset[str]] = frozenset({"ambiguous", "needs_review"})
EXTRACTION_ABSENT: Final = "not_found"


def extraction_status(candidate: FactCandidate) -> str | None:
    payload = candidate.value if isinstance(candidate.value, dict) else None
    status = payload.get("extraction_status") if payload else None
    return status if isinstance(status, str) else None


# ═════════ قرارُ الإنسان ═════════

STATUS_REJECTED: Final = "rejected"
STATUS_UNKNOWN: Final = "unknown"
STATUS_APPROVED: Final = "approved"
AUTOMATABLE_STATUSES: Final[frozenset[str]] = frozenset({"unverified", STATUS_APPROVED})

# ═════════ العتبات — خريطةٌ واحدة، لا أرقامٌ متناثرة ═════════
#
# **افتراضاتٌ تشغيليّة تُعايَر، لا ثوابتُ طبيعة.**

DEFAULT_AUTO_MIN: Final = 0.85
DEFAULT_SUPPORT_MIN: Final = 0.70

FIELD_THRESHOLDS: Final[dict[str, tuple[float, float]]] = {
    "title_ar": (0.90, 0.75),
    "questions": (0.90, 0.75),
    "hypotheses": (0.90, 0.75),
    "constructs": (0.90, 0.75),
    "instruments": (0.90, 0.75),
    "sampling": (0.90, 0.75),
    "population": (0.92, 0.80),
    "qualitative_themes": (0.88, 0.75),
    "primary_findings": (0.92, 0.80),
    # **رقمٌ واحد خاطئ يُعيد تشكيل كلّ استدلال بُني عليه.**
    "sample_size": (0.95, 0.85),
    "hypothesis_results": (0.95, 0.85),
}


def thresholds_for(field_key: str | None) -> tuple[float, float]:
    return FIELD_THRESHOLDS.get(field_key or "", (DEFAULT_AUTO_MIN, DEFAULT_SUPPORT_MIN))


# ═════════ صلاحيةُ الشكل — محافِظةٌ، ومركزُها هنا لا في المشغّل ═════════

_ARABIC_DIGITS: Final = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_INTEGER: Final[re.Pattern[str]] = re.compile(r"\d+")
_LETTER: Final[re.Pattern[str]] = re.compile(r"[^\W\d_]", re.UNICODE)
_DOCUMENT_SUFFIX: Final[re.Pattern[str]] = re.compile(
    r"\.(pdf|docx?|txt|rtf|odt|pptx?)\s*$", re.IGNORECASE)
_PAGE_COUNT_LABEL: Final[re.Pattern[str]] = re.compile(
    r"^\s*(عدد\s+الصفحات|page\s*count|pages)\b", re.IGNORECASE)


def sample_counts(texts: list[str]) -> set[int]:
    """كلُّ عددٍ صحيحٍ موجبٍ في النصّ — بالأرقام العربية والهندية معًا."""
    found: set[int] = set()
    for text in texts:
        for token in _INTEGER.findall(text.translate(_ARABIC_DIGITS)):
            value = int(token)
            if value > 0:
                found.add(value)
    return found


def structurally_valid(field_key: str | None, texts: list[str]) -> tuple[bool, str]:
    """**الشكلُ يسبق الثقة.** وقيمةٌ فاسدةٌ لا تُنقذها 0.99.

    والفحصُ محافِظ: يقبل ما يُقطع بصلاحه، ويرفض ما يُقطع بفساده،
    **ويسقط مغلقًا عند الشكّ** — ولا حكمَ دلاليًّا في شيءٍ منه.
    """
    if not texts:
        return False, "empty_or_malformed_value"

    if field_key == "sample_size":
        counts = sample_counts(texts)
        if not counts:
            # صفرٌ أو سالبٌ أو بلا عددٍ أصلًا — لا حجمَ عيّنةٍ فيه.
            return False, "sample_size_has_no_positive_count"
        if len(counts) > 1:
            # **ولا يُخمَّن أيُّ الرقمين نهائيّ.** «310 دُعوا، 297 استجابوا»
            # عددان متنافسان، واختيارُ أحدهما اختلاقُ واقعةٍ لم تُقل.
            return False, "sample_size_has_competing_counts"
        return True, ""

    if field_key == "title_ar":
        title = texts[0].strip()
        if not title:
            return False, "title_empty"
        if not _LETTER.search(title):
            # رقمٌ محض ليس عنوانًا.
            return False, "title_has_no_textual_content"
        if _DOCUMENT_SUFFIX.search(title):
            # اسمُ الملفّ ليس عنوانَ الرسالة.
            return False, "title_looks_like_a_filename"
        if _PAGE_COUNT_LABEL.match(title):
            return False, "title_looks_like_page_metadata"
        return True, ""

    return True, ""


def usable_texts(candidate: FactCandidate) -> list[str]:
    """قيمُ الحقيقةِ نصًّا — **وتسقط مغلقةً على بنيةٍ لا يعرفها العقد**.

    والشكلُ المخزون `{"value": …}` و`value` نوعُه `Any`. فتُقبل السلاسلُ
    والأعدادُ وقوائمُها، ويُرفض ما عداها.

    **ونصُّ العبارة لا يُنقذ قيمةً فاسدة.** كان الرجوعُ إلى `statement_ar`
    يقع كلّما خلت القراءةُ من نتيجة — ومنها حين تكون القيمةُ حاضرةً لكنّها
    قائمةُ قواميس. و`statement_ar` مكتوبٌ `str(value)`، فيصير
    `"[{'name': …}]"` نصًّا غيرَ فارغ **فيمرّ**. فيدخل قاموسٌ مُسلسَلٌ إلى
    مراجع المتغيّرات في فرصةِ نشرٍ محفوظة.

    فيُفصل الحالان: قيمةٌ **غائبة** يُصان معها نصُّ العبارة، وقيمةٌ
    **حاضرةٌ فاسدة** تسقط مغلقةً ولا تُترجَم.

    وعنصرٌ واحد غيرُ قياسيّ يُسقط القائمةَ كلَّها: قائمةٌ مختلطة لا يُقطع
    فيها بما قُصد، **وما لا يُقطع فيه لا يُنشر**.
    """
    payload = candidate.value if isinstance(candidate.value, dict) else None
    present = payload is not None and "value" in payload
    raw = payload.get("value") if payload else None

    if present and raw is not None:
        out: list[str] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str | int | float) and not isinstance(item, bool):
                    text = str(item).strip()
                    if text:
                        out.append(text)
                else:
                    return []
        elif isinstance(raw, str | int | float) and not isinstance(raw, bool):
            text = str(raw).strip()
            if text:
                out.append(text)
        else:
            return []
        return out

    statement = (candidate.statement_ar or "").strip()
    return [statement] if statement else []


# ═════════ التعارضُ المادّيّ ═════════

CONFLICT_SENSITIVE_FIELDS: Final[frozenset[str]] = frozenset({"sample_size"})


def conflict_key(field_key: str, text: str) -> str:
    if field_key == "sample_size":
        counts = sample_counts([text])
        if len(counts) == 1:
            return str(next(iter(counts)))
    return " ".join(text.split())


# ═════════ الحكم ═════════


@dataclasses.dataclass(frozen=True, slots=True)
class Verdict:
    fact_id: uuid.UUID
    field_key: str | None
    classification: str
    reason: str

    @property
    def eligible(self) -> bool:
        return self.classification == AUTO_ELIGIBLE

    @property
    def from_human(self) -> bool:
        return self.reason == "approved_and_verified_by_researcher"


def classify(
    candidate: FactCandidate,
    *,
    tenant_id: uuid.UUID,
    file_id: uuid.UUID,
    run: ExtractionRun | None,
    chunk: DocumentChunk | None,
    memory: ResearcherMemory | None,
    known_fields: frozenset[str],
    texts: list[str],
) -> Verdict:
    """**الاستبعادُ أصل، والأهليّةُ تُستحقّ.** وكلُّ شرطٍ هنا لازم."""
    def verdict(classification: str, reason: str) -> Verdict:
        return Verdict(candidate.id, candidate.field_key, classification, reason)

    # ── المِلكيّةُ والنسب: لا تُشترى بثقة ──
    #
    # **ولا يُتّكل على RLS.** هي تمنع العبورَ بين المستأجرين، ولا تُثبت أنّ
    # المقطعَ والتشغيلة يخصّان **هذا الملفّ** داخل المستأجر الواحد. فمرشّحٌ
    # على الملفّ (أ) يشير إلى مقطعٍ في الملفّ (ب) يمرّ من RLS سالمًا، ويحمل
    # اقتباسًا مؤصَّلًا في مستندٍ آخر. فتُفحص السلسلةُ كلُّها صراحةً.
    if candidate.tenant_id != tenant_id:
        return verdict(EXCLUDED, "wrong_tenant")
    if candidate.file_id != file_id:
        return verdict(EXCLUDED, "wrong_file")

    if (candidate.field_key or "") not in known_fields:
        return verdict(EXCLUDED, "unsupported_field_key")

    if run is None:
        return verdict(EXCLUDED, "extraction_run_missing")
    if run.id != candidate.extraction_run_id:
        return verdict(EXCLUDED, "extraction_run_mismatch")
    if run.tenant_id != tenant_id or run.file_id != file_id:
        return verdict(EXCLUDED, "extraction_run_belongs_to_another_file")

    if run.status in FAILED_RUNS:
        return verdict(EXCLUDED, "extraction_run_failed")
    if run.status in IN_FLIGHT_RUNS:
        return verdict(EXCLUDED, "extraction_run_incomplete")
    if run.status not in ADVANCED_EVIDENCE_RUNS:
        # `local_only` و`awaiting_consent` وأيُّ حالٍ غير معروفة — تُستبعد
        # بسببها المعلن، **ولا تُسمّى فشلًا**، ولا تُقبل بالسكوت.
        return verdict(EXCLUDED, f"no_advanced_extraction:{processing_scope(run.status)}")

    # ── قرارُ الإنسان يسبق كلَّ حسابٍ آليّ ──
    if candidate.status == STATUS_REJECTED:
        return verdict(EXCLUDED, "rejected_by_researcher")
    if candidate.status == STATUS_UNKNOWN:
        return verdict(REVIEW_REQUIRED, "researcher_marked_unknown")
    if candidate.status not in AUTOMATABLE_STATUSES:
        return verdict(EXCLUDED, f"status_not_automatable:{candidate.status}")

    # ── التأصيل: عطبُ نزاهةٍ لا تشتريه ثقة، ولو بلغت 0.99 ──
    if chunk is None:
        return verdict(EXCLUDED, "chunk_missing")
    if chunk.id != candidate.chunk_id:
        return verdict(EXCLUDED, "chunk_mismatch")
    if chunk.tenant_id != tenant_id or chunk.file_id != file_id:
        return verdict(EXCLUDED, "chunk_belongs_to_another_file")
    if not (candidate.quote or "").strip() or not (candidate.locator or "").strip():
        return verdict(EXCLUDED, "missing_provenance")
    if not quote_is_grounded(candidate.quote, chunk.text):
        return verdict(EXCLUDED, "quote_not_grounded")

    # ── رايةُ الاستخراج ──
    status = extraction_status(candidate)
    if status is None:
        return verdict(EXCLUDED, "extraction_status_absent")
    if status == EXTRACTION_ABSENT:
        return verdict(EXCLUDED, "extraction_reported_not_found")
    if status in EXTRACTION_REVIEW:
        return verdict(REVIEW_REQUIRED, f"extraction_{status}")
    if status != EXTRACTION_OK:
        return verdict(EXCLUDED, f"unknown_extraction_status:{status}")

    # ── الشكلُ يسبق الثقة ──
    valid, why = structurally_valid(candidate.field_key, texts)
    if not valid:
        return verdict(EXCLUDED, why)

    # ── الاعتمادُ البشريّ: يُثبَت كاملًا أو يسقط مغلقًا ──
    #
    # **ولا نزولَ من هنا إلى العتبة.** كان الفرعُ يعود بالأهليّة عند تمام
    # الشروط، ويسقط إلى حساب الثقة عند نقصانها — فمرشّحٌ «معتمَد» بذاكرةٍ
    # مفقودةٍ أو غيرِ موثقةٍ أو من ملفٍّ آخر كان يُصنَّف مؤهَّلًا **بثقة
    # الآلة**، وذاك يقلب قاعدةَ الأسبقيّة رأسًا على عقب: يصير الاعتمادُ
    # المكسور أقوى من الاعتماد المفقود.
    if candidate.status == STATUS_APPROVED:
        if (candidate.resulting_memory_id is None
                or memory is None
                or memory.id != candidate.resulting_memory_id
                or memory.tenant_id != tenant_id
                or memory.source_file_id != file_id
                or memory.verification_status != "verified"):
            return verdict(EXCLUDED, "approved_memory_integrity_failed")
        return verdict(AUTO_ELIGIBLE, "approved_and_verified_by_researcher")

    # ── العتبة، أخيرًا ──
    if candidate.confidence is None:
        return verdict(EXCLUDED, "no_extraction_confidence")
    auto_min, support_min = thresholds_for(candidate.field_key)
    confidence = float(candidate.confidence)
    if confidence >= auto_min:
        return verdict(AUTO_ELIGIBLE, "meets_field_threshold")
    if confidence >= support_min:
        return verdict(SUPPORT_ONLY, "below_auto_threshold")
    return verdict(EXCLUDED, "below_support_threshold")
