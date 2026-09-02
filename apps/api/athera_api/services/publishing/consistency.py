"""اتساق المخطوطة عبر أقسامها | Cross-section manuscript checks (S5E-D §15).

**قسمٌ سليمٌ وحده قد يناقض قسمًا سليمًا وحده.**

مدقّق الصياغة يفحص قسمًا بأدلته. وهذا يفحص ما لا يُرى إلا من فوق: عيّنةٌ
عددها في المنهجية غيرها في النتائج، أو خاتمةٌ تقرّر ما لم ترد في النتائج، أو
ملخّصٌ يأتي برقمٍ لا أصل له في الورقة. وكلٌّ من القسمين مرّ فحصه الخاص.

**وحتميٌّ كله.** لا يُسأل نموذجٌ «هل تتّسق هذه الورقة؟» — جوابه سيكون معقولًا
بلا سند. والسؤال القابل للحسم: هل يرد هذا الرقم في ذاك القسم؟ هل تُذكر هذه
النتيجة في قسم النتائج؟

ويعمل على **النسخة الحالية** كما هي، فلا يُخزَّن حكمٌ يقادم على نصٍّ تغيّر.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ..golden_thread import language
from .drafting import numbers
from .drafting.policy import POLICIES
from .vocab import INTERNAL_MARKERS

# عددُ مشاركين — رقمٌ صحيح بحجم معقول يسبقه أو يليه لفظُ عيّنة.
_SAMPLE_PHRASES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?:عينة|العينة|عيّنة|بلغ(?:ت)?\s+العينة|تكوّنت\s+العينة)"
               r"[^.،]{0,40}?(\d{2,6})"),
    re.compile(r"(\d{2,6})\s*(?:طالبًا|طالبة|مشاركًا|مشاركة|فردًا|مفحوصًا)"),
    re.compile(r"\bn\s*=\s*(\d{2,6})", re.IGNORECASE),
)

# ألفاظ التصميم — تُقابَل بين الأقسام لا تُفسَّر.
_DESIGNS: Final[dict[str, re.Pattern[str]]] = {
    "quasi_experimental": re.compile(r"شبه\s+التجريبي|quasi-?experimental", re.IGNORECASE),
    "experimental": re.compile(r"(?<!شبه\s)(?<!شبه)التجريبي\b|(?<!quasi-)\bexperimental\b",
                               re.IGNORECASE),
    "correlational": re.compile(r"الارتباطي|correlational", re.IGNORECASE),
    "descriptive_survey": re.compile(r"الوصفي\s+المسحي|المسحي|survey", re.IGNORECASE),
    "qualitative": re.compile(r"النوعي|الكيفي|qualitative", re.IGNORECASE),
}


@dataclass(slots=True)
class ManuscriptIssue:
    """كشفٌ على مستوى الورقة — بقسميه لا بقسمٍ واحد."""

    issue_key: str
    sections: tuple[str, ...]
    detail_ar: str
    detail_en: str
    excerpt: str | None = None
    is_blocking: bool = True


@dataclass(frozen=True, slots=True)
class SectionText:
    """قسمٌ كما يصل الفحص — نصًّا وحالًا، بلا ORM."""

    section_key: str
    text: str
    review_status: str = "draft"


def _sample_numbers(text: str) -> set[str]:
    body = numbers.normalise(text)
    found: set[str] = set()
    for pattern in _SAMPLE_PHRASES:
        found.update(pattern.findall(body))
    return found


def _designs(text: str) -> set[str]:
    body = numbers.normalise(text)
    return {name for name, pattern in _DESIGNS.items() if pattern.search(body)}


def _statistics(text: str) -> set[str]:
    return {hit.excerpt for hit in numbers.find(text) if hit.value is not None}


def evaluate(sections: list[SectionText]) -> list[ManuscriptIssue]:
    """يفحص النسخة الحالية كوحدة واحدة."""
    by_key = {s.section_key: s for s in sections}
    issues: list[ManuscriptIssue] = []

    def add(key, keys, ar, en, excerpt=None, blocking=True) -> None:
        issues.append(ManuscriptIssue(issue_key=key, sections=tuple(keys),
                                      detail_ar=ar, detail_en=en, excerpt=excerpt,
                                      is_blocking=blocking))

    # ── 1. عيّنةٌ عددها يختلف بين الأقسام ──
    #
    # ولا يُرجَّح أحدهما: أيّهما الصحيح سؤالٌ للباحث لا للمنصّة.
    counts: dict[str, set[str]] = {
        key: _sample_numbers(section.text)
        for key, section in by_key.items() if section.text
    }
    stated = {key: values for key, values in counts.items() if values}

    # **التقاطع لا التطابق.** ورقةٌ صحيحة تذكر الكلّ في المنهجية والكلَّ
    # والمجموعةَ في النتائج: «120 طالبًا … 60 لكل مجموعة». والمجموعتان
    # {120} و{120، 60} متسقتان تمامًا؛ واشتراطُ التطابق يجعل المدقّق يعاقب
    # الدقّة — وحارسٌ يعاقب الصدق يُعطَّل، ثم لا يحرس شيئًا.
    #
    # والتناقض أن يذكر قسمان عددين **لا يشتركان في شيء**.
    conflicting = sorted(
        (left, right) for left in stated for right in stated
        if left < right and not (stated[left] & stated[right])
    )
    if conflicting:
        left, right = conflicting[0]
        pairs = " · ".join(
            f"{key}={'،'.join(sorted(stated[key]))}" for key in (left, right))
        add("sample_size_mismatch", (left, right),
            f"حجم العينة يختلف بين الأقسام: {pairs}.",
            f"The stated sample size differs across sections: {pairs}.",
            excerpt=pairs)

    # ── 2. تصميمٌ يختلف بين الأقسام ──
    designs = {key: _designs(section.text)
               for key, section in by_key.items() if section.text}
    declared = {key: found for key, found in designs.items() if found}
    union = {d for found in declared.values() for d in found}
    if len(union) > 1:
        add("design_mismatch", sorted(declared),
            f"تصميم الدراسة يختلف بين الأقسام: {'، '.join(sorted(union))}.",
            f"The stated study design differs across sections: {', '.join(sorted(union))}.")

    # ── 3. الملخّص يأتي برقمٍ لا أصل له في الورقة ──
    #
    # §5 — الملخص **يعيد** ما سُنِد، ولا يولّد. ورقمٌ فيه لا يرد في قسمٍ آخر
    # واقعةٌ دخلت من أضعف باب: باب التلخيص.
    abstract = by_key.get("abstract")
    if abstract and abstract.text:
        elsewhere: set[str] = set()
        for key, section in by_key.items():
            if key != "abstract" and section.text:
                elsewhere |= _statistics(section.text)
        for value in sorted(_statistics(abstract.text) - elsewhere):
            add("abstract_introduces_new_statistic", ("abstract",),
                f"قيمة إحصائية في الملخّص لا ترد في أي قسم آخر: «{value}».",
                f"A statistic in the abstract that appears in no other section: "
                f"'{value}'.", excerpt=value)
            break

    # ── 4. الخاتمة تقرّر ما لم يرد في النتائج ──
    conclusion, results = by_key.get("conclusion"), by_key.get("results")
    if conclusion and conclusion.text and results is not None:
        orphan = sorted(_statistics(conclusion.text) - _statistics(results.text or ""))
        if orphan:
            add("conclusion_states_absent_result", ("conclusion", "results"),
                f"الخاتمة تذكر قيمة لا ترد في النتائج: «{orphan[0]}».",
                f"The conclusion states a value absent from the results: '{orphan[0]}'.",
                excerpt=orphan[0])

    # ── 5. لغة سببية في قسمٍ لا تسمح سياسته بها ──
    design_family = next(iter(union), None)
    for key, section in by_key.items():
        policy = POLICIES.get(key)
        if not section.text or policy is None or policy.allow_causal:
            continue
        hits = language.find_causal_language(
            section.text, design_family=design_family, study_type=design_family or "")
        if hits:
            add("causal_language_beyond_design", (key,),
                f"لغة سببية في «{key}» لا يسندها التصميم الموثق: «{hits[0].matched}».",
                f"Causal wording in '{key}' the verified design does not support: "
                f"'{hits[0].matched}'.", excerpt=hits[0].sentence)
            break

    # ── 6. تعميمٌ أوسع من العيّنة ──
    for key, section in by_key.items():
        if not section.text:
            continue
        hits = language.find_overgeneralization(section.text, sampling_strategy=None)
        if hits:
            add("generalization_beyond_sample", (key,),
                f"تعميم أوسع مما تسمح به العينة في «{key}»: «{hits[0].matched}».",
                f"A generalization beyond what the sample supports in '{key}': "
                f"'{hits[0].matched}'.", excerpt=hits[0].sentence)
            break

    # ── 7. علامةُ تحكّمٍ داخلية في أي قسم ──
    for key, section in by_key.items():
        marker = next((m for m in INTERNAL_MARKERS if m in (section.text or "")), None)
        if marker:
            add("internal_redaction_marker", (key,),
                f"علامة تحكّم داخلية في «{key}»: «{marker}».",
                f"An internal control marker in '{key}': '{marker}'.", excerpt=marker)
            break

    # ── 8. قسمٌ معتمَد بلا نصّ ──
    for key, section in by_key.items():
        if section.review_status == "approved" and not (section.text or "").strip():
            add("approved_section_is_empty", (key,),
                f"قسم «{key}» معتمَد بلا نصّ.",
                f"Section '{key}' is approved but has no text.")
            break

    return issues


__all__ = ["ManuscriptIssue", "SectionText", "evaluate"]
