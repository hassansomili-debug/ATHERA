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
  `SUPPORT_ONLY`     تُعين على السياق والترتيب، **ولا تُنشئ فرصةً وحدها**
                     ولا تُسند نتيجةً ولا متغيّرًا ولا عيّنة.
  `REVIEW_REQUIRED`  تعارضٌ مادّيّ أو رايةُ مراجعة — يُحجب **المفهومُ
                     المعنيّ وحده**، ولا تُعطَّل الرسالة كلُّها.
  `EXCLUDED`         لا تدخل شيئًا.

## محوران لا محور

**وقرارُ خصوصيّةٍ لا يُعرض فشلَ استخراج.** حالُ التشغيل (`processing_scope`)
شيء، وجودةُ الدليل شيءٌ آخر. فباحثٌ رفض إرسالَ رسالته إلى مزوّدٍ خارجي
تمّت قراءتُه المحلّية، ولم يقع استخراجٌ متقدّم — وذاك **قرارُه محترمًا**،
لا عطبًا يُقال له. فيُفصل المحوران في التقرير.

## الثقةُ ثقةُ استخراجٍ لا ثقةُ علم

`0.99` تقول «قرأتُ هذا النصَّ من المستند على الأرجح». لا تقول إنّ ما قُرئ
صحيحٌ علميًّا، ولا تشتري تجاوزًا لعطبٍ في التأصيل ولا لرايةِ مراجعة:

  ‏`0.99` مع `ambiguous`     → `REVIEW_REQUIRED`
  ‏`0.99` مع `needs_review`  → `REVIEW_REQUIRED`
  ‏`0.99` مع اقتباسٍ غير مؤصَّل → `EXCLUDED`

**ولا تُرفع حقيقةٌ ضعيفة لأنّ المنقّبَ يشتهي دليلًا.** ذلك الانقلابُ بعينه
هو ما وُضعت العتباتُ لمنعه.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from typing import Final

from ...models.research import DocumentChunk, FactCandidate, ResearcherMemory
from ..extraction.base import quote_is_grounded

# ═════════ الحالاتُ الأربع ═════════

AUTO_ELIGIBLE: Final = "auto_eligible"
SUPPORT_ONLY: Final = "support_only"
REVIEW_REQUIRED: Final = "review_required"
EXCLUDED: Final = "excluded"

# ═════════ محورُ التشغيل — منفصلٌ عن محور الجودة ═════════

#: استخراجٌ متقدّم وقع، فيجوز النظرُ في دليله.
ADVANCED_EVIDENCE_RUNS: Final[frozenset[str]] = frozenset(
    {"awaiting_review", "verified", "succeeded"})

#: **ليست فشلًا.** القراءةُ المحلّية تمّت، ولم يقع استخراجٌ متقدّم — إمّا
#: لأنّ الباحث رفض الإرسال الخارجي، أو لأنّه لم يقرّر بعد. ولا يُشتقّ من
#: هذا أنّ ثمّة دليلًا علميًّا يُنقَّب.
LOCAL_SCOPE_RUNS: Final[frozenset[str]] = frozenset(
    {"local_only", "awaiting_consent"})

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


# ═════════ حالُ الاستخراج — تُقرأ من داخل `value` ═════════
#
# **وليست عمودًا.** `FactCandidate.extraction_status` لا وجود له؛ القيمةُ
# داخل `value` JSON. وغيابُ المفتاح يُعامَل **قصدًا** لا افتراضًا: مرشّحٌ
# لا يقول كيف استُخرج لا يُفترض أنّه استُخرج بنجاح.

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
AUTOMATABLE_STATUSES: Final[frozenset[str]] = frozenset({"unverified", "approved"})

# ═════════ العتبات — خريطةٌ واحدة، لا أرقامٌ متناثرة ═════════
#
# **افتراضاتٌ تشغيليّة تُعايَر، لا ثوابتُ طبيعة.** وهي عتباتُ ثقةِ استخراج:
# كم يُرجَّح أنّ النصَّ قُرئ من المستند كما هو. والحقولُ التي يُبنى عليها
# ادّعاءٌ كمّيّ أو منهجيّ أشدُّ، لأنّ خطأها يُنتج ورقةً مؤصَّلةً في وهم.

DEFAULT_AUTO_MIN: Final = 0.85
DEFAULT_SUPPORT_MIN: Final = 0.70

FIELD_THRESHOLDS: Final[dict[str, tuple[float, float]]] = {
    # الحقل: (أدنى للأهليّة، أدنى للإسناد)
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


# ═════════ التعارضُ المادّيّ — ما يُكشف حتمًا وحده ═════════
#
# **ولا مقياسَ تشابهٍ دلاليّ في هذا الطلب.** «هويّةُ بناءٍ غير متوافقة»
# و«نتائجُ فروضٍ متناقضة» تحتاجان حكمًا دلاليًّا أو هويّةً مستقرّة للفرض،
# ولا يمثّل النموذجُ أيًّا منهما اليوم. وحدسٌ يخطئ هنا يَسِم دليلًا صحيحًا
# بالتعارض ويحجبه — فيُؤجَّلان صراحةً ويُذكران في الوثيقة.
#
# ويبقى ما يُقطع فيه: **حجمُ العيّنة**. رقمان مختلفان لمجتمعٍ واحد تناقضٌ
# لا تأويلَ له.

CONFLICT_SENSITIVE_FIELDS: Final[frozenset[str]] = frozenset({"sample_size"})
_FIRST_INTEGER: Final[re.Pattern[str]] = re.compile(r"\d[\d,٫٬]*")


def conflict_key(field_key: str, text: str) -> str:
    """صورةٌ مُطبَّعة تُقارَن — لا نصٌّ خام يختلف بفراغٍ فيُظنّ تعارضًا."""
    if field_key == "sample_size":
        found = _FIRST_INTEGER.search(text)
        if found:
            return re.sub(r"[,٫٬]", "", found.group())
    return " ".join(text.split())


# ═════════ الحكم ═════════


@dataclasses.dataclass(frozen=True, slots=True)
class Verdict:
    """حكمٌ على حقيقةٍ واحدة — ومعه سببُه، بلا نصّ مستند."""

    fact_id: uuid.UUID
    field_key: str | None
    classification: str
    reason: str

    @property
    def eligible(self) -> bool:
        return self.classification == AUTO_ELIGIBLE


def classify(
    candidate: FactCandidate,
    *,
    tenant_id: uuid.UUID,
    file_id: uuid.UUID,
    run_status: str | None,
    chunk: DocumentChunk | None,
    memory: ResearcherMemory | None,
    known_fields: frozenset[str],
    has_text: bool,
) -> Verdict:
    """**الاستبعادُ أصل، والأهليّةُ تُستحقّ.** وكلُّ شرطٍ هنا لازم.

    والترتيبُ مقصود: المِلكيّةُ أولًا فلا تشتريها ثقة، ثمّ التأصيل فلا
    تشتريه ثقة، ثمّ رايةُ المراجعة، ثمّ العتبة أخيرًا.
    """
    def verdict(classification: str, reason: str) -> Verdict:
        return Verdict(candidate.id, candidate.field_key, classification, reason)

    # ── المِلكيّة: لا تُشترى بثقة ولا بأيّ شيء ──
    if candidate.tenant_id != tenant_id:
        return verdict(EXCLUDED, "wrong_tenant")
    if candidate.file_id != file_id:
        return verdict(EXCLUDED, "wrong_file")

    if (candidate.field_key or "") not in known_fields:
        return verdict(EXCLUDED, "unsupported_field_key")

    # ── حالُ التشغيل: والرفضُ ليس فشلًا، وكلاهما ليس دليلًا متقدّمًا ──
    if run_status in FAILED_RUNS:
        return verdict(EXCLUDED, "extraction_run_failed")
    if run_status in IN_FLIGHT_RUNS:
        return verdict(EXCLUDED, "extraction_run_incomplete")
    if run_status not in ADVANCED_EVIDENCE_RUNS:
        # `local_only` و`awaiting_consent` — تُستبعد بسببها المعلن، لا بوصفها فشلًا.
        return verdict(EXCLUDED, f"no_advanced_extraction:{processing_scope(run_status)}")

    # ── قرارُ الإنسان يسبق كلَّ حسابٍ آليّ ──
    if candidate.status == STATUS_REJECTED:
        return verdict(EXCLUDED, "rejected_by_researcher")
    if candidate.status == STATUS_UNKNOWN:
        return verdict(REVIEW_REQUIRED, "researcher_marked_unknown")
    if candidate.status not in AUTOMATABLE_STATUSES:
        return verdict(EXCLUDED, f"status_not_automatable:{candidate.status}")

    # ── التأصيل: عطبٌ في النزاهة لا تشتريه ثقة، ولو بلغت 0.99 ──
    if chunk is None:
        return verdict(EXCLUDED, "chunk_missing")
    if not (candidate.quote or "").strip() or not (candidate.locator or "").strip():
        return verdict(EXCLUDED, "missing_provenance")
    if not quote_is_grounded(candidate.quote, chunk.text):
        return verdict(EXCLUDED, "quote_not_grounded")

    # ── رايةُ الاستخراج: تُقرأ من `value`، وغيابُها يُعامَل قصدًا ──
    status = extraction_status(candidate)
    if status is None:
        return verdict(EXCLUDED, "extraction_status_absent")
    if status == EXTRACTION_ABSENT:
        return verdict(EXCLUDED, "extraction_reported_not_found")
    if status in EXTRACTION_REVIEW:
        return verdict(REVIEW_REQUIRED, f"extraction_{status}")
    if status != EXTRACTION_OK:
        return verdict(EXCLUDED, f"unknown_extraction_status:{status}")

    if not has_text:
        return verdict(EXCLUDED, "empty_or_malformed_value")

    # ── الإنسانُ المعتمِد أعلى ثقةً من أيّ استخراجٍ لاحق ──
    if (candidate.status == "approved" and memory is not None
            and memory.verification_status == "verified"
            and memory.source_file_id == file_id
            and memory.tenant_id == tenant_id):
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
