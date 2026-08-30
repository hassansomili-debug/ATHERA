"""حاجز الاختلاق | The anti-fabrication barrier (§4 No Fabrication، §10.2).

كل مرشّح حقيقة يجب أن يحمل اقتباسًا **موجودًا حرفيًا** في المقطع الذي يدّعي
أنه مصدره. هذا ليس تحققًا شكليًا: هو ما يمنع أي مستخرِج — قاعديًا كان أم
نموذجًا لغويًا — من أن يخترع معلومة وينسبها إلى ملف الباحث.

مرشّح لا يجتاز هذا الحاجز لا يصل إلى قائمة المراجعة أصلًا، ويُحصى في
`extraction_runs.candidates_rejected_unquoted` كمؤشر مباشر على محاولة اختلاق.
"""
from __future__ import annotations

import abc
import re
import unicodedata
from dataclasses import dataclass

from ..parsing import ParsedChunk

# نطاقات التشكيل والتطويل بترميز صريح لا بحروف حرفية.
# السبب: صنف حروف مكتوب حرفيًا يمكن أن يتلف عند النسخ فيبتلع الحروف العربية
# نفسها بدل تشكيلها — وهذا ما وقع فعلًا وكشفه اختبار التداخل في Sprint 6.
_ARABIC_DIACRITICS = re.compile("[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")


def normalize_for_match(text: str) -> str:
    """تطبيع للمطابقة فقط — النص المخزّن يبقى كما ورد في المصدر."""
    text = unicodedata.normalize("NFKC", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"[\s ]+", " ", text)
    return text.strip().lower()


@dataclass(slots=True)
class Candidate:
    """مرشّح حقيقة — لا حقيقة. الفرق هو كل شيء في هذا المنتج."""

    memory_category: str
    statement_ar: str
    quote: str
    chunk_seq: int
    statement_en: str | None = None
    field_key: str | None = None
    value: dict | None = None
    confidence: float | None = None


@dataclass(slots=True)
class ExtractionResult:
    candidates: list[Candidate]
    rejected_unquoted: list[Candidate]
    extractor: str
    model_run_id: str | None = None


def quote_is_grounded(quote: str, chunk_text: str) -> bool:
    """هل الاقتباس موجود فعلًا في المقطع؟"""
    if not quote or not quote.strip():
        return False
    return normalize_for_match(quote) in normalize_for_match(chunk_text)


def enforce_grounding(
    candidates: list[Candidate], chunks: dict[int, ParsedChunk]
) -> tuple[list[Candidate], list[Candidate]]:
    """يفصل المرشّحات المؤصَّلة عن المختلقة. لا استثناءات ولا وضع «متساهل»."""
    grounded: list[Candidate] = []
    rejected: list[Candidate] = []
    for candidate in candidates:
        chunk = chunks.get(candidate.chunk_seq)
        if chunk is not None and quote_is_grounded(candidate.quote, chunk.text):
            grounded.append(candidate)
        else:
            rejected.append(candidate)
    return grounded, rejected


class Extractor(abc.ABC):
    """واجهة المستخرِج — قاعدية أو نموذجية، والنتيجة تمر بالحاجز نفسه."""

    name: str = "abstract"

    @abc.abstractmethod
    async def propose(self, chunks: list[ParsedChunk]) -> ExtractionResult: ...
