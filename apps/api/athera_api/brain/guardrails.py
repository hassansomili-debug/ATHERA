"""حواجز النزاهة | Integrity guardrails (§7.1، §8، §4).

فحوص حتمية على **مخرَج** الأجنت. لا تسأل النموذج إن كان ملتزمًا، بل تفحص
ما قاله فعلًا. مخرَج يخالف حاجزًا لا يصل إلى المستخدم إطلاقًا.

القاعدة: كل حاجز يترجم قيدًا نصيًا من §8 إلى فحص قابل للتشغيل.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# DOI و معرّفات الأدلة الداخلية.
_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.IGNORECASE)
_EVIDENCE_ID = re.compile(r"\bEV-[A-Za-z0-9_-]+\b")

# أنماط إحصائية: رقم بهذه الصيغ يعني ادعاء نتيجة، لا كلامًا عامًا.
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

# وعود القبول — القيد الحرفي لـJournal Matcher في §8، و§20.4.
#
# الصيغة الفعلية («تضمن القبول») أشيع من الاسمية («ضمان القبول»)، والنفي
# («لا تضمن»، «does not guarantee») هو بالضبط اللغة الصادقة التي نريدها أن
# تمر. لذا: تغطية الصيغ الفعلية مع استثناء صريح للنفي.
_ACCEPTANCE = [
    re.compile(r"(?<!لا )(?<!يمكن )(?:ضمان|تضمن|يضمن|نضمن|أضمن)\s*(?:لك\s+)?(?:ال)?قبول"),
    re.compile(r"(?<!لا )(?:سيتم|سوف)\s+قبول"),
    re.compile(r"(?<!غير )مضمون\s+(?:النشر|القبول)"),
    re.compile(r"احتمالية\s+القبول\s*[:=]?\s*\d"),
    re.compile(r"نسبة\s+القبول\s+المتوقعة"),
    re.compile(r"(?<!not )(?<!cannot )(?<!never )guarantee[sd]?\s+acceptance", re.IGNORECASE),
    re.compile(r"(?<!not )will\s+(?:certainly\s+)?be\s+accepted", re.IGNORECASE),
    re.compile(r"acceptance\s+probability\s*[:=]?\s*\d", re.IGNORECASE),
]

# ادعاء التحقق الذاتي — §7.4: الأجنت لا يرقّي معلومة إلى «موثقة».
_SELF_VERIFICATION = [
    re.compile(r"اعتبر\s*(?:ها|ه|هذه|هذا)?\s*متحقق"),
    re.compile(r"مُعتمد\s+تلقائيًا"),
    re.compile(r"تم\s+التحقق\s+تلقائيًا"),
    re.compile(r"verification_status\s*[=:]\s*[\"']?verified", re.IGNORECASE),
    # «marked this as verified» — كلمات بين الفعل و«as» هي الحالة الشائعة.
    re.compile(r"mark(?:ed|ing)?\s+(?:\w+\s+){0,3}as\s+verified", re.IGNORECASE),
    re.compile(r"treat\s+(?:\w+\s+){0,3}as\s+verified", re.IGNORECASE),
    re.compile(r"consider\s+(?:\w+\s+){0,3}(?:as\s+)?verified", re.IGNORECASE),
]

# إسناد التأليف — §24.2 وقيد Authorship Agent في §8.
_AUTHORSHIP = [
    re.compile(r"(?:أُسند|أسندت|مُنح|منحت)\s+(?:حق\s+)?التأليف"),
    re.compile(r"المؤلف\s+الأول\s+(?:هو|هي)\s+\S+"),
    re.compile(r"authorship\s+(?:is\s+)?(?:granted|assigned)", re.IGNORECASE),
    re.compile(r"first\s+author\s+(?:is|shall\s+be)\s+\S+", re.IGNORECASE),
]


@dataclass(slots=True)
class GuardContext:
    """ما يعرفه الحاجز عن التشغيلة — لا أكثر."""

    allowed_evidence_ids: frozenset[str] = frozenset()
    allowed_dois: frozenset[str] = frozenset()
    analysis_run_ids: frozenset[str] = frozenset()


@dataclass(slots=True)
class GuardViolation:
    guard_key: str
    detail_ar: str
    detail_en: str
    excerpt: str


def _first(patterns: list[re.Pattern[str]], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def citations_must_be_grounded(text: str, ctx: GuardContext) -> GuardViolation | None:
    """§4 No Fabrication — كل DOI أو معرّف دليل يجب أن يكون في مجموعة الأدلة."""
    for doi in _DOI.findall(text):
        if doi.rstrip(".,;)") not in {d.rstrip(".,;)") for d in ctx.allowed_dois}:
            return GuardViolation(
                "citations_must_be_grounded",
                f"استشهاد بـDOI غير موجود في مجموعة الأدلة المتحققة: {doi}",
                f"Cited a DOI absent from the verified evidence set: {doi}",
                doi,
            )
    for evidence_id in _EVIDENCE_ID.findall(text):
        if evidence_id not in ctx.allowed_evidence_ids:
            return GuardViolation(
                "citations_must_be_grounded",
                f"استشهاد بمعرّف دليل غير معروف: {evidence_id}",
                f"Cited an unknown evidence identifier: {evidence_id}",
                evidence_id,
            )
    return None


def numbers_require_analysis_run(text: str, ctx: GuardContext) -> GuardViolation | None:
    """§18.1 و§8 (Analysis Agent) — لا رقم إحصائي بلا تشغيلة تحليل فعلية."""
    if ctx.analysis_run_ids:
        return None
    found = _first(_STATISTICS, text)
    if found:
        return GuardViolation(
            "numbers_require_analysis_run",
            f"نتيجة إحصائية بلا تشغيلة تحليل مرتبطة: «{found}»",
            f"Statistical result with no linked analysis run: '{found}'",
            found,
        )
    return None


def no_acceptance_guarantee(text: str, ctx: GuardContext) -> GuardViolation | None:
    """§20.4 و§8 (Journal Matcher) — لا ضمان قبول ولا احتمال مختلق."""
    found = _first(_ACCEPTANCE, text)
    if found:
        return GuardViolation(
            "no_acceptance_guarantee",
            f"وعد أو احتمال قبول غير مسموح: «{found}»",
            f"Disallowed acceptance promise or probability: '{found}'",
            found,
        )
    return None


def no_self_verification(text: str, ctx: GuardContext) -> GuardViolation | None:
    """§7.4 — الأجنت لا يرقّي معلومة إلى ذاكرة موثقة، ولا يدّعي أنه فعل."""
    found = _first(_SELF_VERIFICATION, text)
    if found:
        return GuardViolation(
            "no_self_verification",
            f"ادعاء تحقق ذاتي يخالف قاعدة ترقية الذاكرة: «{found}»",
            f"Self-verification claim violating the memory promotion rule: '{found}'",
            found,
        )
    return None


def authorship_needs_human(text: str, ctx: GuardContext) -> GuardViolation | None:
    """§24.2 — التأليف قرار بشري موثق، لا مخرَج نموذج."""
    found = _first(_AUTHORSHIP, text)
    if found:
        return GuardViolation(
            "authorship_needs_human",
            f"إسناد تأليف بلا قرار بشري موثق: «{found}»",
            f"Authorship assigned without a recorded human decision: '{found}'",
            found,
        )
    return None


GUARDS: Final = {
    "citations_must_be_grounded": citations_must_be_grounded,
    "numbers_require_analysis_run": numbers_require_analysis_run,
    "no_acceptance_guarantee": no_acceptance_guarantee,
    "no_self_verification": no_self_verification,
    "authorship_needs_human": authorship_needs_human,
}


def run_guards(keys: frozenset[str], text: str, ctx: GuardContext) -> list[GuardViolation]:
    """يشغّل كل الحواجز ويعيد كل المخالفات — لا يتوقف عند الأولى.

    عرض المخالفات كلها دفعة واحدة أصدق من كشفها واحدة تلو الأخرى.
    """
    violations: list[GuardViolation] = []
    for key in sorted(keys):
        guard = GUARDS.get(key)
        if guard is None:
            continue
        violation = guard(text, ctx)
        if violation is not None:
            violations.append(violation)
    return violations
