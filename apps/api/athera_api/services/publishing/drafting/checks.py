"""تحقّق حتمي من مسودة قسم | Deterministic section verification (S5E-B §21).

**الحتمي أولًا، ولا نموذج يحكم على نموذج.** سؤال «هل هذه الجملة صحيحة؟» لا
يُوكل إلى نموذجٍ ثانٍ: جوابه سيكون معقولًا بالقدر نفسه وبلا سند أكثر. والسؤال
القابل للحسم هو الآخر: **هل يوجد دليل موثق يقول هذا؟**

فالفحوص هنا تقابل نصّ المسودة بالأدلة المُرسَلة، لا بمعرفةٍ عامة. وما لا يجد
له سندًا يُعلَن كشفًا حاجبًا يراه الباحث — ولا يُعاد كتابة المسودة صامتًا حتى
تمرّ (§22).

**والصدق لا يُعاقَب.** الدرس المسجَّل في حواجز Sprint 2 مطبَّق: جملةٌ تقول
«لم تُذكر إجراءات الصدق في المادة الموثقة» ليست مخالفة بل هي المطلوب.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ...golden_thread import language
from ..manuscript import _STATISTICS

# مفردات منهجية لا يجوز ادّعاؤها بلا سند — وكلٌّ بصنفه فيُقال للباحث **أي**
# تفصيل اختُلق لا «ثمة اختلاق».
_METHOD_TERMS: Final[dict[str, tuple[re.Pattern[str], ...]]] = {
    "design": (
        re.compile(r"(?:شبه\s+التجريبي|التجريبي|الوصفي|الارتباطي|المسحي|الإثنوغرافي)"),
        re.compile(r"\b(?:quasi-experimental|experimental|descriptive|correlational|survey)\b",
                   re.IGNORECASE),
    ),
    "sampling": (
        re.compile(r"(?:العشوائية\s+\S+|الطبقية|العنقودية|القصدية|المتاحة|كرة\s+الثلج)"),
        re.compile(r"\b(?:stratified|cluster|purposive|convenience|snowball)\b", re.IGNORECASE),
    ),
    "instrument": (
        re.compile(r"(?:استبانة|مقياس|اختبار\s+تحصيلي|بطاقة\s+ملاحظة|مقابلة\s+\S+)"),
        re.compile(r"\b(?:questionnaire|scale|inventory|rubric|interview\s+protocol)\b",
                   re.IGNORECASE),
    ),
    "reliability": (
        re.compile(r"(?:ألفا\s+كرونباخ|كرونباخ|معامل\s+الثبات|إعادة\s+الاختبار)"),
        re.compile(r"\b(?:cronbach|test-?retest|composite\s+reliability)\b", re.IGNORECASE),
    ),
    "software": (
        re.compile(r"\b(?:SPSS|AMOS|SmartPLS|Stata|NVivo|MAXQDA|Mplus|JASP|R\b)",
                   re.IGNORECASE),
    ),
    "ethics": (
        re.compile(r"(?:موافقة\s+أخلاقية|لجنة\s+الأخلاقيات|الموافقة\s+المستنيرة)"),
        re.compile(r"\b(?:ethics\s+(?:approval|committee)|informed\s+consent|IRB)\b",
                   re.IGNORECASE),
    ),
}

# أرقامٌ ذات معنى منهجي — حجم عينة أو عدد أدوات. والسنوات تُستثنى: تاريخٌ
# مذكور في اقتباس ليس ادّعاء عيّنة.
_SAMPLE_NUMBER = re.compile(r"(?<![\d.])(\d{2,6})(?![\d.])")
_YEARS = re.compile(r"^(?:1[89]|20)\d{2}$")

# صيغ استشهاد — لا مرجع يُختلق والسجل مغلق (§23).
_CITATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # الفاصلة العربية `،` كالفاصلة اللاتينية — و«(الزهراني، 2019)» استشهاد.
    re.compile(r"\(\s*[^()]{2,60}?[,،]\s*(?:19|20)\d{2}[a-z]?\s*\)"),
    re.compile(r"\b(?:doi|DOI)\s*:\s*10\.\d{4,9}/"),
    re.compile(r"\b[A-Z][a-z]+\s+(?:et\s+al\.|and\s+[A-Z][a-z]+)\s*\(\s*(?:19|20)\d{2}\s*\)"),
    re.compile(r"(?:وآخرون|وزملاؤه)\s*\(\s*(?:19|20)\d{2}\s*\)"),
)


@dataclass(slots=True)
class DraftIssue:
    """كشفٌ واحد — بموضعه وسببه ومقتطفه، فيراه الباحث ولا يُخفى."""

    issue_key: str
    section_key: str
    detail_ar: str
    detail_en: str
    excerpt: str | None = None
    claim_index: int | None = None
    is_blocking: bool = True


def _evidence_blob(context) -> str:
    """كل ما أُرسل من أدلة — نصًّا واحدًا للمقابلة."""
    parts: list[str] = []
    for item in context.items:
        parts.extend(filter(None, (item.statement, item.quote)))
    parts.extend(context.thread_labels)
    return "\n".join(parts)


def _sample_numbers(text: str) -> set[str]:
    return {m for m in _SAMPLE_NUMBER.findall(text) if not _YEARS.match(m)}


def run(draft, context, *, known_memory_ids: frozenset[str],
        known_output_ids: frozenset[str]) -> list[DraftIssue]:
    """يقابل المسودة بالأدلة المُرسَلة — ولا شيء غيرها."""
    section = context.section_key
    issues: list[DraftIssue] = []
    evidence = _evidence_blob(context)
    text = draft.section_text_ar or ""

    def add(key: str, ar: str, en: str, *, excerpt=None, index=None, blocking=True) -> None:
        issues.append(DraftIssue(issue_key=key, section_key=section, detail_ar=ar,
                                 detail_en=en, excerpt=excerpt, claim_index=index,
                                 is_blocking=blocking))

    # ── 1. ادعاءٌ يُعرض حقيقةً بلا سند ──
    for index, claim in enumerate(draft.claims):
        valid_memories = [m for m in claim.memory_ids if m in known_memory_ids]
        valid_outputs = [o for o in claim.analysis_output_ids if o in known_output_ids]
        invented = ([m for m in claim.memory_ids if m not in known_memory_ids]
                    + [o for o in claim.analysis_output_ids if o not in known_output_ids])
        if invented:
            # §16 — معرّفٌ خارج السياق المُرسَل: اختلاقُ سند، لا خطأ مطبعي.
            add("claim_references_unknown_evidence",
                f"ادعاء يشير إلى دليل لم يُرسل إليه: {invented[0]}.",
                f"A claim references evidence that was never sent to it: {invented[0]}.",
                excerpt=claim.text_ar[:200], index=index)
        if claim.origin == "fact" and not valid_memories and not valid_outputs:
            add("factual_claim_without_verified_evidence",
                "ادعاء معروضٌ حقيقةَ مصدر بلا دليل موثق يسنده.",
                "A claim is presented as fact with no verified evidence behind it.",
                excerpt=claim.text_ar[:200], index=index)

    # ── 2. رقمٌ إحصائي بلا مخرَج تحليل ──
    #
    # وجودُ تشغيلة في القسم ليس سندًا (§20): السند أن يكون الرقم في مخرَج
    # بعينه. والمنهجية لا يُتوقّع أن تحمل نتيجة أصلًا.
    for pattern in _STATISTICS:
        match = pattern.search(text)
        if match:
            add("statistic_without_analysis_output",
                f"قيمة إحصائية في المسودة بلا مخرَج تحليل يسندها: «{match.group(0)}».",
                f"A statistic appears with no analysis output behind it: '{match.group(0)}'.",
                excerpt=match.group(0))
            break

    # ── 3. تفصيل منهجي لا أثر له في الأدلة ──
    #
    # **والمقابلة بالمصطلح المطابق لا بالنمط.** أول صياغة قابلت وجودَ النمط
    # في الأدلة، فكان «المنهج الوصفي» يمرّ لأن الأدلة تذكر «شبه التجريبي»
    # — وكلاهما يطابق نمط التصاميم نفسه. أي أن الحارس كان يتحقق من أن
    # الأدلة تذكر **تصميمًا ما**، لا التصميم المكتوب.
    for kind, patterns in _METHOD_TERMS.items():
        flagged = False
        for pattern in patterns:
            for found in pattern.finditer(text):
                term = found.group(0)
                if term.lower() in evidence.lower():
                    continue
                add(f"unsupported_{kind}",
                    f"تفصيل منهجي لا تسنده المادة الموثقة ({kind}): «{term}».",
                    f"A method detail unsupported by the verified material ({kind}): "
                    f"'{term}'.",
                    excerpt=term)
                flagged = True
                break
            if flagged:
                break

    # ── 4. رقمٌ يصف العينة ولا يرد في الأدلة ──
    invented_numbers = sorted(_sample_numbers(text) - _sample_numbers(evidence))
    if invented_numbers:
        add("unsupported_sample_number",
            f"رقم لا يرد في المادة الموثقة: «{invented_numbers[0]}».",
            f"A number that appears nowhere in the verified material: '{invented_numbers[0]}'.",
            excerpt=invented_numbers[0])

    # ── 5. استشهادٌ مختلَق — والسجل مغلق حتى S5F ──
    for pattern in _CITATION_PATTERNS:
        found = pattern.search(text)
        if found and not pattern.search(evidence):
            add("fabricated_citation",
                f"استشهاد لا أصل له في المادة الموثقة: «{found.group(0)}».",
                f"A citation with no basis in the verified material: '{found.group(0)}'.",
                excerpt=found.group(0))
            break

    # ── 6. لغة سببية فوق ما يسمح به التصميم ──
    design = _design_family(evidence)
    for hit in language.find_causal_language(text, design_family=design, study_type=design or ""):
        add("causal_language_beyond_design",
            f"لغة سببية لا يسندها التصميم الموثق: «{hit.matched}».",
            f"Causal wording the verified design does not support: '{hit.matched}'.",
            excerpt=hit.sentence)
        break

    return issues


def _design_family(evidence: str) -> str | None:
    """عائلة التصميم **من الأدلة** — وما لا يُذكر فيها لا يُفترض."""
    from ...planning.thread import _DESIGN_HINTS, _hint

    return _hint(evidence, _DESIGN_HINTS)


__all__ = ["DraftIssue", "run"]
