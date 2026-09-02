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
from ..vocab import INTERNAL_MARKERS
from .policy import POLICIES
from . import numbers

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
# كسرٌ عشري بأي فاصلة — عربية أو لاتينية أو نقطة. يُنزع كاملًا قبل البحث عن
# أرقام العيّنة: جزؤه الكسري ليس عددَ مشاركين، والكلّ إمّا قيمة إحصائية
# يفحصها فحصها الخاص، أو ليس حجمَ عيّنة بحال.
_DECIMAL = re.compile(r"\d+\s*[.,٫٬]\s*\d+")
_SAMPLE_NUMBER = re.compile(r"(?<![\d.,])(\d{2,6})(?![\d.,])")
_YEARS = re.compile(r"^(?:1[89]|20)\d{2}$")

# صيغ استشهاد — لا مرجع يُختلق والسجل مغلق (§23).
# صيغ تفسيرية لا موضع لها في «النتائج» (§2) — التفسير للمناقشة.
#
# والنتائج وصفٌ لما لوحظ. وجملةٌ تفسّر «لماذا» تُقحم في القسم الوصفي ادّعاءً
# لا يسنده قياس، ويقرؤه المحكِّم نتيجةً.
_INTERPRETATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(?:يُعزى|تُعزى|يمكن\s+تفسير|ويُفسَّر|مما\s+يدلّ?\s+على|"
               r"مما\s+يشير\s+إلى|ويرجع\s+ذلك)"),
    # الفاعل قد يتوسّط: «وتتفق **هذه النتيجة** مع ما توصّلت إليه…».
    re.compile(r"(?:يتفق|تتفق|يختلف|تختلف)\s+(?:\S+\s+){0,3}مع\s+(?:ما\s+)?"
               r"(?:توصّل|دراس|نتائج|الأدب)"),
    re.compile(r"(?:نوصي|يُوصى|وتوصي\s+الدراسة|ويُقترح)"),
    re.compile(r"\b(?:this\s+(?:suggests|implies|indicates\s+that)|"
               r"consistent\s+with\s+(?:previous|prior)|we\s+recommend)\b",
               re.IGNORECASE),
)

_CITATION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    # الفاصلة العربية `،` كالفاصلة اللاتينية — و«(الزهراني، 2019)» استشهاد.
    re.compile(r"\(\s*[^()]{2,60}?[,،]\s*(?:19|20)\d{2}[a-z]?\s*\)"),
    re.compile(r"\b(?:doi|DOI)\s*:\s*10\.\d{4,9}/"),
    re.compile(r"\b[A-Z][a-z]+\s+(?:et\s+al\.|and\s+[A-Z][a-z]+)\s*\(\s*(?:19|20)\d{2}\s*\)"),
    re.compile(r"(?:وآخرون|وزملاؤه)\s*\(\s*(?:19|20)\d{2}\s*\)"),
)


# أقسامٌ يصف نصّها إجراءً منهجيًّا — وفيها وحدها تُفحص مفردات المنهج.
_METHOD_BEARING_SECTIONS: Final[frozenset[str]] = frozenset({"method"})

# أقسامٌ وصفية: تقول ما لوحظ ولا تفسّره (§2) — **من السجلّ لا بجانبه**.
_DESCRIPTIVE_SECTIONS: Final[frozenset[str]] = frozenset(
    key for key, policy in POLICIES.items() if policy.descriptive_only)


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


def outputs_carrying(hit, context) -> list:
    """المخرجات المؤهَّلة التي تحمل هذه القيمة **بنوعها وأبعادها** (المستوى أ).

    وهذا سؤال «هل يجوز أن يظهر هذا الرقم في القسم؟» — يُجاب من المخرجات
    المتاحة كلها، لا من ادعاءٍ بعينه. وكان الخلط بين هذا السؤال وسؤال
    الإسناد يجعل رقمًا حقيقيًّا يُرفض لأن النموذج علّق معرّف مخرَجه على
    ادعاءٍ آخر.
    """
    if hit.value is None:
        return []
    carrying = []
    for output in context.outputs:
        if any(numbers.fact_supports(hit, fact)
               for fact in numbers.facts(output.payload)):
            carrying.append(output)
    return carrying


def _grounded_statistics(draft, context, known_output_ids: frozenset[str]) -> set[str]:
    """القيم التي يسندها مخرَجٌ بعينه **ومربوطةٌ بادعاء** (المستوى ب).

    ولا يكفي أن يذكر النموذج معرّف مخرَج: يُتحقّق أن المعرّف أُرسل إليه، وأن
    المخرَج يحمل هذه القيمة بنوعها وأبعادها. فالمعرّف إشارةٌ لا سلطة.
    """
    grounded: set[str] = set()
    for claim in draft.claims:
        outputs = [context.output(o) for o in claim.analysis_output_ids
                   if o in known_output_ids]
        available = [o for o in outputs if o is not None]
        if not available:
            continue
        for hit in numbers.find(claim.text_ar):
            if any(numbers.fact_supports(hit, fact)
                   for output in available for fact in numbers.facts(output.payload)):
                grounded.add(hit.excerpt)
    return grounded


def _evidence_blob(context) -> str:
    """كل ما أُرسل من أدلة — نصًّا واحدًا للمقابلة."""
    parts: list[str] = []
    for item in context.items:
        parts.extend(filter(None, (item.statement, item.quote)))
    parts.extend(context.thread_labels)
    return "\n".join(parts)


def _sample_numbers(text: str) -> set[str]:
    r"""أرقامٌ تصف عيّنة — **بعد التوحيد وبعد نزع القيم الإحصائية**.

    وعطبان كشفهما الإنتاج:

    الأول أن `\d` في بايثون يطابق الأرقام العربية الهندية، والفاصلة العشرية
    العربية `٫` ليست في نظرة الخلف — فكان `٣٫٠٨` يُقرأ رقمين، ويُبلَّغ عن
    «٠٨» رقمَ عيّنةٍ مخترَعًا. فيُوحَّد النصّ أولًا.

    والثاني أن القيم الإحصائية تُفحص بفحصها الخاص، فمرورها هنا يجعل كل
    قيمة تُبلَّغ مرتين بوصفين مختلفين — أحدهما خاطئ.
    """
    body = numbers.normalise(text)
    for hit in numbers.find(body):
        body = body.replace(hit.excerpt, " ")
    # ثم كل كسرٍ عشري بقي — بأي فاصلة. فأول علاج نزع القيم المعروفة وحدها،
    # وبقيت `0,003` تُقرأ «003» لأن الفاصلة اللاتينية ليست في نظرة الخلف.
    body = _DECIMAL.sub(" ", body)
    return {m for m in _SAMPLE_NUMBER.findall(body) if not _YEARS.match(m)}


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

    # ── 2. رقمٌ إحصائي بلا مخرَج تحليل بعينه ──
    #
    # وجودُ تشغيلة في القسم ليس سندًا (§20): السند أن تكون **هذه القيمة** في
    # **ذلك المخرَج**. ولا تقريب: `0.047` و`0.05` ليستا واحدة.
    grounded_values = _grounded_statistics(draft, context, known_output_ids)
    for hit in numbers.find(text):
        if hit.excerpt in grounded_values:
            continue
        if hit.is_bare_significance:
            # §17 — ادّعاء الدلالة مأذونٌ **بوجود قيمة p مسجَّلة**، ولا يُشتقّ
            # من (ت) ودرجات حريتها. فالكتابة ليست محرّك تحليل: ما يلزم من
            # إحصاءٍ يُنتَج في «البيانات والتحليل» ويُسجَّل مخرَجًا.
            if context.statistics.significance_claim_allowed:
                continue
            add("significance_without_analysis_output",
                f"ادّعاء دلالة إحصائية بلا قيمة دلالة مسجَّلة: «{hit.excerpt}». "
                "والقيمة تُنتَج في التحليل وتُسجَّل مخرَجًا، ولا تُشتقّ هنا.",
                f"A statistical-significance claim with no recorded p-value: "
                f"'{hit.excerpt}'. That value is produced by analysis and recorded "
                "as an output; it is not derived here.",
                excerpt=hit.excerpt)
            break

        # **فشلان لا واحد.** «لا مخرَج يحمل هذا الرقم» غير «الرقم حقيقي لكن
        # لا إسناد بنيويًّا له». والخلط بينهما يجعل عطبًا في الربط يُقرأ
        # اختلاقًا، فيُطارَد في المكان الخطأ.
        carrying = outputs_carrying(hit, context)
        if not carrying:
            add("statistic_without_analysis_output",
                f"قيمة إحصائية ({hit.kind}) بلا مخرَج تحليل يسندها: «{hit.excerpt}».",
                f"A statistic ({hit.kind}) with no analysis output behind it: "
                f"'{hit.excerpt}'.",
                excerpt=hit.excerpt)
        elif len(carrying) > 1:
            # §9 — لا يُختار أحدهما اعتباطًا: إسنادٌ غير محدَّد ليس إسنادًا.
            add("statistic_output_ambiguous",
                f"أكثر من مخرَج تحليل يحمل «{hit.excerpt}» — والإسناد الصحيح "
                "غير محدَّد.",
                f"More than one analysis output carries '{hit.excerpt}'; the correct "
                "provenance cannot be determined.",
                excerpt=hit.excerpt)
        else:
            add("statistic_without_claim_binding",
                f"قيمة إحصائية حقيقية بلا رابط بنيوي إلى مخرَجها: «{hit.excerpt}».",
                f"A real statistic with no structural link to the output that produced "
                f"it: '{hit.excerpt}'.",
                excerpt=hit.excerpt)
        break

    # وأنماط `manuscript.evaluate()` القائمة تبقى حزامًا ثانيًا — لما يفوته
    # المستخرِج. ومقتطفاتها تختلف طولًا عن مقتطفاته (`t(118) = 4` مقابل
    # `t(118) = 4.21`)، فالمقابلة بالتداخل لا بالتطابق الحرفي؛ وإلا عُدّت
    # قيمةٌ مسنَدة غيرَ مسنَدة لأن الحزامين يقتطعانها بطولين مختلفين.
    def _already_grounded(found: str) -> bool:
        return any(found in value or value in found for value in grounded_values)

    for pattern in _STATISTICS:
        match = pattern.search(text)
        if match and not _already_grounded(match.group(0)):
            add("statistic_without_analysis_output",
                f"قيمة إحصائية في المسودة بلا مخرَج تحليل يسندها: «{match.group(0)}».",
                f"A statistic appears with no analysis output behind it: '{match.group(0)}'.",
                excerpt=match.group(0))
            break

    # ── 2ب. تفسيرٌ في قسمٍ وصفي ──
    if section in _DESCRIPTIVE_SECTIONS:
        for pattern in _INTERPRETATION_PATTERNS:
            found = pattern.search(text)
            if found:
                add("interpretation_in_results",
                    f"تفسير في قسم وصفي — موضعه المناقشة: «{found.group(0)}».",
                    f"Interpretation inside a descriptive section; it belongs in the "
                    f"discussion: '{found.group(0)}'.",
                    excerpt=found.group(0))
                break
        # §2 — ادعاءات النتائج وقائع، لا مقترحات.
        for index, claim in enumerate(draft.claims):
            if claim.origin == "proposal":
                add("proposal_in_results",
                    "اقتراح معروضٌ نتيجةً — والنتائج وصفٌ لما لوحظ.",
                    "A proposal presented as a result; Results describes what was observed.",
                    excerpt=claim.text_ar[:200], index=index)
                break

    # ── 2ج. قيمةٌ تخالف المخرَج الذي رُبطت به ──
    for index, claim in enumerate(draft.claims):
        for output_id in claim.analysis_output_ids:
            if output_id not in known_output_ids:
                continue
            output = context.output(output_id)
            if output is None:
                continue
            mismatched = [h for h in numbers.find(claim.text_ar)
                          if not h.is_bare_significance
                          and not numbers.supports(h, output.payload)]
            if mismatched:
                add("statistic_value_mismatch",
                    f"قيمة لا ترد في المخرَج المرتبط بها: «{mismatched[0].excerpt}».",
                    f"A value that does not appear in the analysis output it is linked "
                    f"to: '{mismatched[0].excerpt}'.",
                    excerpt=mismatched[0].excerpt, index=index)
                break

    # ── 2د. علامةُ حجبٍ داخلية تسرّبت إلى النصّ ──
    for marker in INTERNAL_MARKERS:
        if marker in text:
            add("internal_redaction_marker_leak",
                f"علامة داخلية ظهرت في نصّ المخطوطة: «{marker}».",
                f"An internal redaction marker leaked into manuscript prose: '{marker}'.",
                excerpt=marker)
            break

    # ── 3. تفصيل منهجي لا أثر له في الأدلة ──
    #
    # **والمقابلة بالمصطلح المطابق لا بالنمط.** أول صياغة قابلت وجودَ النمط
    # في الأدلة، فكان «المنهج الوصفي» يمرّ لأن الأدلة تذكر «شبه التجريبي»
    # — وكلاهما يطابق نمط التصاميم نفسه. أي أن الحارس كان يتحقق من أن
    # الأدلة تذكر **تصميمًا ما**، لا التصميم المكتوب.
    #
    # **وفي أقسام المنهج وحدها.** الحارس وُضع ليمنع قسم المنهجية من اختراع
    # أداةٍ أو أسلوب معاينة. وتطبيقه على المناقشة والخاتمة يُنتج ضجيجًا من
    # مشتركات اللفظ: «في حدود الأدلة **المتاحة**» تُقرأ عيّنةً متاحة،
    # و«**مقياس** لحجم الأثر» تُقرأ أداةَ دراسة. وقد وقع الاثنان في الإنتاج.
    #
    # وحارسٌ يكثر ضجيجه يُتجاهَل، ثم لا يحرس شيئًا.
    for kind, patterns in (_METHOD_TERMS.items()
                           if section in _METHOD_BEARING_SECTIONS else ()):
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
    #
    # **وكل عدد في مخرَج تحليل مؤهَّل يُستثنى** — لا القيم المرتبطة بادعاء
    # وحدها. فدرجات الحرية في `t(118) = 3.738` عددٌ حقيقي خرج من التحليل،
    # وقد يكتبها الباحث أو النموذج خارج صيغة الاختبار: «د.ح = 118». وحصرُ
    # الاستثناء في المقتطفات المرتبطة يجعل رقمًا حقيقيًّا يُبلَّغ عنه رقمَ
    # عيّنة مخترَعًا — وهو ما وقع فعلًا فحُجبت مسودة صحيحة.
    #
    # ويُستعمل `all_values` لا `facts`: مفتاحٌ لا نعرف نوعه (`n_control`)
    # يبقى عددًا حقيقيًّا خرج من التحليل.
    #
    # ولا يُرخي هذا الإسناد: الادعاءات الإحصائية تظل تُفحص بنوعها وقيمتها
    # وأبعادها ورابطها. وهذا الفحص وحده — حارسُ **أرقام العيّنة** — هو الذي
    # يكفّ عن عدّ مخرجات التحليل اختلاقًا.
    grounded_digits = {d for value in grounded_values
                       for d in _sample_numbers(numbers.normalise(value))}
    output_digits: set[str] = set()
    for output in context.outputs:
        for value in numbers.all_values(output.payload):
            output_digits |= _sample_numbers(value)
    invented_numbers = sorted(
        _sample_numbers(text) - _sample_numbers(evidence)
        - grounded_digits - output_digits)
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


# كشوفاتٌ لا يجوز أن يصير نصّها مخطوطة — ولو تحت «بانتظار المراجعة» (§25).
#
# فبقية الكشوفات تحذيرات على نصٍّ قائم يراه الباحث ويقرّر فيه؛ وهذه اختلاق:
# رقمٌ لا مصدر له، أو قيمةٌ تخالف مصدرها، أو إسنادٌ إلى دليل لم يُرسل، أو
# مرجعٌ لا وجود له. وتركها تُحفظ يجعل الاختلاق نصًّا يُقرأ.
FABRICATION_ISSUES: Final[frozenset[str]] = frozenset({
    "statistic_without_analysis_output",
    "significance_without_analysis_output",
    "statistic_value_mismatch",
    "statistic_output_ambiguous",
    "statistic_without_claim_binding",
    "claim_references_unknown_evidence",
    "fabricated_citation",
    "unsupported_sample_number",
    # ليست اختلاقًا علميًّا، لكنها نصٌّ ليس نصَّ الباحث ولا نصَّ النموذج —
    # وتنظيفها صامتًا يخفي أن المخرَج لم يمرّ كما هو.
    "internal_redaction_marker_leak",
})


def fabrications(issues: list[DraftIssue]) -> list[DraftIssue]:
    return [i for i in issues if i.issue_key in FABRICATION_ISSUES]


__all__ = ["FABRICATION_ISSUES", "INTERNAL_MARKERS", "DraftIssue", "fabrications",
           "outputs_carrying", "run"]
