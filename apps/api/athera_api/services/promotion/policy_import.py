"""استيراد اللائحة | Policy import (§11.1، §41.3).

يعيد استخدام حاجز التأصيل نفسه من Sprint 1: كل قاعدة مقترحة تحمل اقتباسًا
حرفيًا من نص اللائحة وموضعه، ويُتحقق من وجوده. قاعدة بلا نص داعم لا تصل
إلى شاشة الاعتماد.

وكل قاعدة تُستورد **غير متحققة**. هذا ليس تحفظًا زائدًا: §8 تلزم Promotion
Auditor بألا يفترض قاعدة غير موثقة، و§11.4 تضع كل متطلب غير مثبت في حالة
Needs Institutional Verification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..extraction.base import quote_is_grounded
from ..parsing import ParsedChunk

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

_NUMBER_WORDS = {
    "واحد": 1, "واحدة": 1, "سنة": 1, "سنتين": 2, "اثنين": 2, "اثنتين": 2,
    "ثلاث": 3, "ثلاثة": 3, "أربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5,
    "ست": 6, "ستة": 6, "سبع": 7, "سبعة": 7, "ثمان": 8, "ثمانية": 8,
    "تسع": 9, "تسعة": 9, "عشر": 10, "عشرة": 10,
}

_INDEX_TOKENS = ("SSCI", "AHCI", "SCIE", "ESCI", "SCOPUS", "WEB OF SCIENCE", "ISI")


@dataclass(slots=True)
class RuleCandidate:
    rule_type: str
    rule_key: str
    statement_ar: str
    statement_en: str
    params: dict
    quote: str
    chunk_seq: int
    confidence: float


def _number_near(text: str, match: re.Match[str]) -> int | None:
    """يستخرج عددًا رقميًا أو لفظيًا قريبًا من الموضع."""
    window = text[max(0, match.start() - 60): match.end() + 60].translate(_AR_DIGITS)
    digits = re.search(r"\b(\d{1,3})\b", window)
    if digits:
        return int(digits.group(1))
    for word, value in _NUMBER_WORDS.items():
        if word in window:
            return value
    return None


def _window(text: str, match: re.Match[str], padding: int = 80) -> str:
    return text[max(0, match.start() - padding): match.end() + padding].strip()


def extract_rule_candidates(chunks: list[ParsedChunk]) -> tuple[list[RuleCandidate], list[RuleCandidate]]:
    """يعيد (المؤصَّلة، المرفوضة لعدم التأصيل)."""
    candidates: list[RuleCandidate] = []
    seen: set[str] = set()

    for chunk in chunks:
        text = chunk.text

        for match in re.finditer(r"(?:مدة|قضاء|أمضى|إمضاء)[^.\n]{0,40}(?:الرتبة|الخدمة)", text):
            years = _number_near(text, match)
            if years is None or "service_duration" in seen:
                continue
            seen.add("service_duration")
            candidates.append(RuleCandidate(
                rule_type="service_duration", rule_key="service_duration",
                statement_ar=f"مدة الخدمة المطلوبة في الرتبة: {years} سنوات.",
                statement_en=f"Required service duration in rank: {years} year(s).",
                params={"min_years": years}, quote=_window(text, match),
                chunk_seq=chunk.seq, confidence=0.6,
            ))

        for match in re.finditer(r"(?:وحدة|وحدات)\s*(?:بحثية)?", text):
            units = _number_near(text, match)
            if units is None or "minimum_units" in seen:
                continue
            seen.add("minimum_units")
            candidates.append(RuleCandidate(
                rule_type="minimum_units", rule_key="minimum_units",
                statement_ar=f"الحد الأدنى من الوحدات البحثية: {units}.",
                statement_en=f"Minimum research units: {units}.",
                params={"min_units": float(units)}, quote=_window(text, match),
                chunk_seq=chunk.seq, confidence=0.5,
            ))

        for match in re.finditer(r"(?:منفرد|بمفرده|المنفردة)", text):
            count = _number_near(text, match)
            if count is None or "sole_author_works" in seen:
                continue
            seen.add("sole_author_works")
            candidates.append(RuleCandidate(
                rule_type="sole_author_works", rule_key="sole_author_works",
                statement_ar=f"الحد الأدنى من الأعمال المنفردة: {count}.",
                statement_en=f"Minimum sole-authored works: {count}.",
                params={"min_count": count}, quote=_window(text, match),
                chunk_seq=chunk.seq, confidence=0.5,
            ))

        for token in _INDEX_TOKENS:
            for match in re.finditer(re.escape(token), text, re.IGNORECASE):
                key = f"indexing:{token.upper()}"
                if key in seen:
                    continue
                seen.add(key)
                count = _number_near(text, match) or 1
                candidates.append(RuleCandidate(
                    rule_type="indexing_requirement", rule_key=f"indexing_{token.lower().replace(' ', '_')}",
                    statement_ar=f"شرط فهرسة يذكر {token}؛ العدد المقترح {count}.",
                    statement_en=f"Indexing requirement mentioning {token}; suggested count {count}.",
                    # count_esci لا يُخمَّن: يبقى غائبًا ليقرره معتمد اللائحة.
                    params={"indexes": [token.upper()], "min_count": count},
                    quote=_window(text, match), chunk_seq=chunk.seq, confidence=0.4,
                ))

    by_seq = {chunk.seq: chunk for chunk in chunks}
    grounded, rejected = [], []
    for candidate in candidates:
        chunk = by_seq.get(candidate.chunk_seq)
        if chunk is not None and quote_is_grounded(candidate.quote, chunk.text):
            grounded.append(candidate)
        else:
            rejected.append(candidate)
    return grounded, rejected
