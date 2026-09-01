"""اختيار المقاطع | Minimum-necessary chunk selection (§7، §8، §15).

**لا تُرسل الرسالة كاملة.** مئتا صفحة في مطالبة واحدة تعني كلفةً وفيضان
سياق واختلاقًا وتتبّعًا ضائعًا. ولكل حقل تُختار مقاطعه بدلائل نصّية، ثم
يُرسل ما اختير وحده.

**وحجبٌ قبل الاختيار:** ملاحق المشاركين ونماذج الموافقة ونصوص المقابلات قد
تحمل أسماءً وهواتف وبُرُدًا ومعرّفات. تُستبعد من كل إرسال خارجي — لا لأن
النموذج سيسيء استعمالها، بل لأن إرسال ما لا يلزم مخالفةٌ في ذاته (§36).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from .fields import FieldSpec

# أقسام تُستبعد من الإرسال الخارجي — عناوينها بالعربية والإنجليزية.
_SENSITIVE_SECTIONS: Final[tuple[str, ...]] = (
    "الملاحق", "ملحق", "نموذج الموافقة", "موافقة المشارك", "بيانات المشاركين",
    "نص المقابلة", "تفريغ المقابلات", "قائمة المحكمين", "السيرة الذاتية",
    "appendix", "appendices", "consent form", "informed consent",
    "interview transcript", "participant data", "respondent list", "curriculum vitae",
)

# أنماط تعريف شخصي — وجودها في مقطع يمنع إرساله مهما كان قسمه.
_PII_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"),                      # بريد
    re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)"),             # هاتف
    re.compile(r"\b\d{10,}\b"),                                     # هوية/سجل
)


@dataclass(frozen=True, slots=True)
class ChunkView:
    """ما يحتاجه الاختيار من المقطع — لا الصفّ كاملًا."""

    chunk_id: str
    seq: int
    text: str
    locator: str
    page_number: int | None
    section_path: str | None


def is_sensitive(chunk: ChunkView) -> tuple[bool, str | None]:
    """هل يُستبعد هذا المقطع من الإرسال الخارجي؟ ولماذا."""
    section = (chunk.section_path or "").lower()
    for marker in _SENSITIVE_SECTIONS:
        if marker.lower() in section:
            return True, f"sensitive_section:{marker}"
    for pattern in _PII_PATTERNS:
        if pattern.search(chunk.text):
            return True, "personal_identifier_detected"
    return False, None


def _score(chunk: ChunkView, spec: FieldSpec) -> int:
    haystack = f"{chunk.section_path or ''}\n{chunk.text}".lower()
    hits = sum(1 for cue in spec.cues_ar if cue.lower() in haystack)
    hits += sum(1 for cue in spec.cues_en if cue in haystack)
    if hits and chunk.section_path:
        hits += 1  # دليل في عنوان القسم أقوى من دليل في متن عابر
    return hits


def select_chunks_for(
    spec: FieldSpec, chunks: list[ChunkView], *, limit: int = 4, front_matter: int = 6,
) -> list[ChunkView]:
    """مقاطع هذا الحقل وحدها، مرتّبةً بقوة الدلالة.

    وبيانات الرسالة تسكن صفحاتها الأولى، فتُضاف مقاطع الصدر احتياطًا حين لا
    تكفي الدلائل — وهو استثناء مُعلن لا قاعدة عامة.
    """
    safe = [c for c in chunks if not is_sensitive(c)[0]]
    scored = [(c, _score(c, spec)) for c in safe]
    picked = [c for c, s in sorted(scored, key=lambda p: (-p[1], p[0].seq)) if s > 0][:limit]

    if not picked and spec.section.value == "metadata":
        picked = safe[:front_matter]
    return picked


def excluded_report(chunks: list[ChunkView]) -> dict[str, int]:
    """ماذا استُبعد ولماذا — يُسجَّل عددًا لا نصًّا."""
    report: dict[str, int] = {}
    for chunk in chunks:
        blocked, reason = is_sensitive(chunk)
        if blocked and reason:
            key = reason.split(":")[0]
            report[key] = report.get(key, 0) + 1
    return report
