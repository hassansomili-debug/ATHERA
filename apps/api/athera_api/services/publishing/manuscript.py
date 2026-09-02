"""جاهزية المخطوطة | Manuscript readiness (§19.2، §9 بوابة G9).

قاعدتا §19.2 الأوليان تُجمعان في بوابة واحدة:
  1. الادعاءات الجوهرية من أدلة متحققة فقط.
  2. نتائج البحث من تشغيلات تحليل فقط.

والبوابة تسمّي ما ينقص بالاسم: «القسم كذا يحمل ادعاءً بلا دليل» أشد فائدة
من «المخطوطة غير جاهزة».
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .vocab import (
    EVIDENCE_BEARING_SECTIONS,
    INTERNAL_MARKERS,
    MANUSCRIPT_SECTIONS,
    RESULT_BEARING_SECTIONS,
)

# أنماط النتائج الإحصائية — نفس عائلة أنماط حاجز Sprint 2، وموضعها هنا
# لأن الفحص على مستوى المستند لا على مستوى مخرَج أجنت.
_STATISTICS = [
    re.compile(r"\bp\s*[=<>]\s*0?\.\d+", re.IGNORECASE),
    re.compile(r"[βΒbB]\s*=\s*-?0?\.\d+"),
    re.compile(r"\bR\s*[²2]\s*=\s*0?\.\d+", re.IGNORECASE),
    re.compile(r"\bt\s*\(\s*\d+\s*\)\s*=\s*-?\d"),
    re.compile(r"\bF\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*-?\d"),
    re.compile(r"\b(?:M|SD|AVE|CR|HTMT)\s*=\s*-?\d+([.,]\d+)?"),
    re.compile(r"معامل\s+الانحدار\s*=\s*-?\d"),
    re.compile(r"مستوى\s+الدلالة\s*=\s*0?[.,]\d+"),
]


@dataclass(frozen=True, slots=True)
class SectionState:
    """حالة قسم كما تصل الفحص."""

    section_key: str
    text: str
    claim_ids: frozenset[str] = frozenset()
    supported_claim_ids: frozenset[str] = frozenset()
    analysis_run_ids: frozenset[str] = frozenset()
    is_required: bool = True


@dataclass(slots=True)
class ReadinessIssue:
    section_key: str
    issue_key: str
    detail_ar: str
    detail_en: str
    excerpt: str | None = None

    @property
    def is_blocking(self) -> bool:
        return True


@dataclass(slots=True)
class ManuscriptReadiness:
    issues: list[ReadinessIssue]
    missing_sections: list[str]
    sections_checked: int
    note_ar: str = field(
        default="الجاهزية تُقاس بغياب الادعاءات بلا سند، لا باكتمال النص.", init=False
    )
    note_en: str = field(
        default="Readiness is the absence of unsupported claims, not the completeness of prose.",
        init=False,
    )

    @property
    def can_pass_g9(self) -> bool:
        return not self.issues and not self.missing_sections


def _first_statistic(text: str) -> str | None:
    for pattern in _STATISTICS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def evaluate(
    sections: list[SectionState], *, required_sections: frozenset[str] | None = None
) -> ManuscriptReadiness:
    """§19.2 — يفحص القاعدتين ويسمّي ما ينقص."""
    present = {section.section_key for section in sections}
    unknown = present - set(MANUSCRIPT_SECTIONS)
    issues: list[ReadinessIssue] = []

    for key in sorted(unknown):
        issues.append(ReadinessIssue(
            section_key=key, issue_key="unknown_section",
            detail_ar=f"قسم غير معروف في بنية المخطوطة: «{key}».",
            detail_en=f"Unknown manuscript section: '{key}'.",
        ))

    required = required_sections if required_sections is not None else frozenset({
        "title", "abstract", "introduction", "method", "results", "discussion",
        "conclusion", "references",
    })
    missing = sorted(required - present)

    for section in sections:
        # علامةُ تحكّمٍ داخلية في نصّ يُقيَّم للنشر (S5E §11).
        #
        # الحارس عند التوليد لا يكفي: **نسخةٌ قديمة تحمل العلامة تمرّ إلى
        # البوابة بلا أن تمرّ بالتوليد مرة أخرى.** وقد وقع ذلك — ثلاثة أقسام
        # محفوظة في الإنتاج تحملها. ولا تُنظَّف صامتًا: تنظيفها يجعلنا
        # ندّعي أن النصّ خرج نظيفًا.
        for marker in INTERNAL_MARKERS:
            if marker in (section.text or ""):
                issues.append(ReadinessIssue(
                    section_key=section.section_key,
                    issue_key="internal_redaction_marker",
                    detail_ar=f"علامة تحكّم داخلية في نصّ «{section.section_key}»: "
                              f"«{marker}».",
                    detail_en=f"An internal control marker in '{section.section_key}': "
                              f"'{marker}'.",
                    excerpt=marker,
                ))
                break

        # §19.2 القاعدة 1 — ادعاء جوهري بلا دليل متحقق.
        if section.section_key in EVIDENCE_BEARING_SECTIONS:
            unsupported = section.claim_ids - section.supported_claim_ids
            for claim_id in sorted(unsupported):
                issues.append(ReadinessIssue(
                    section_key=section.section_key, issue_key="claim_without_evidence",
                    detail_ar=f"ادعاء بلا دليل متحقق في قسم «{section.section_key}»: {claim_id}.",
                    detail_en=f"Claim without verified evidence in '{section.section_key}': {claim_id}.",
                ))

        # §19.2 القاعدة 2 — رقم إحصائي بلا تشغيلة تحليل.
        if section.section_key in RESULT_BEARING_SECTIONS and not section.analysis_run_ids:
            statistic = _first_statistic(section.text)
            if statistic:
                issues.append(ReadinessIssue(
                    section_key=section.section_key, issue_key="result_without_analysis_run",
                    detail_ar=f"نتيجة إحصائية بلا تشغيلة تحليل في «{section.section_key}»: «{statistic}».",
                    detail_en=f"Statistical result with no analysis run in '{section.section_key}': '{statistic}'.",
                    excerpt=statistic,
                ))

    return ManuscriptReadiness(
        issues=issues, missing_sections=missing, sections_checked=len(sections)
    )
