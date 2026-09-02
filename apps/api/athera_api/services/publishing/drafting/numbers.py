"""استخراج القيم الإحصائية ومطابقتها | Statistical token extraction (S5E-C §19، §20).

**الغرض ضيّق:** أن نعرف متى تحمل جملةٌ قيمةً إحصائية تستحق النشر، وأن نقابل
تلك القيمة بمخرَج تحليل حقيقي. لا محرّك لغة رياضية، ولا فهم للمعادلات.

**ولا تقريب.** `0.047` و`0.05` ليستا القيمة نفسها، ومن يقرّب بينهما يجعل رقمًا
لم يُحسب يبدو محسوبًا. فالمطابقة على القيمة كما خزّنها التحليل، والتنسيق —
إن لزم — يُشتقّ من المخزَّن لا من النموذج.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# الأرقام العربية الهندية → اللاتينية. والمنتج ثنائي اللغة، والباحث يكتب
# بالنظامين، فمقابلةٌ تعرف واحدًا منهما تفوّت نصف الحالات.
_ARABIC_INDIC: Final = str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789..")


def normalise(text: str) -> str:
    """يوحّد الأرقام والفواصل العشرية — بلا تغيير القيمة."""
    return text.translate(_ARABIC_INDIC)


# الرموز الإحصائية التي تستحق سندًا بنيويًّا (§4).
#
# وكلٌّ بمفتاحه فيُقال للباحث **أي** قيمة بلا سند لا «ثمة قيمة».
STATISTIC_TOKENS: Final[dict[str, re.Pattern[str]]] = {
    "p_value": re.compile(r"\bp\s*[=<>≤≥]\s*(-?0?\.\d+)", re.IGNORECASE),
    "t_statistic": re.compile(r"\bt\s*\(\s*\d+(?:\.\d+)?\s*\)\s*=\s*(-?\d+(?:\.\d+)?)"),
    "f_statistic": re.compile(r"\bF\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*(-?\d+(?:\.\d+)?)"),
    "beta": re.compile(r"[βΒ]\s*=\s*(-?\d*\.?\d+)"),
    "r_squared": re.compile(r"\bR\s*[²2]\s*=\s*(-?\d*\.?\d+)", re.IGNORECASE),
    "correlation": re.compile(r"\br\s*=\s*(-?0?\.\d+)"),
    "eta_squared": re.compile(
        r"(?:مربع\s+إيتا|η\s*[²2]|eta[\s-]*squared)\s*[=:]?\s*(-?\d*\.?\d+)",
        re.IGNORECASE),
    "cohen_d": re.compile(r"\b(?:cohen'?s\s+)?d\s*=\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE),
    "mean": re.compile(r"\b(?:M|المتوسط(?:\s+الحسابي)?)\s*[=:]\s*(-?\d+(?:\.\d+)?)"),
    "std_dev": re.compile(r"\b(?:SD|الانحراف\s+المعياري)\s*[=:]\s*(-?\d+(?:\.\d+)?)"),
    "confidence_interval": re.compile(
        r"\b(?:CI|فترة\s+الثقة)\s*[^\d\-]{0,12}(-?\d+(?:\.\d+)?)"),
    "composite_reliability": re.compile(r"\b(?:AVE|CR|HTMT)\s*=\s*(-?\d+(?:\.\d+)?)"),
    "percentage": re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|في\s+المئة|بالمئة)"),
}

# صيغ الدلالة بلا رقم — ادّعاءٌ إحصائي كامل ولو خلا من قيمة.
#
# «فروق دالة إحصائيًّا» تقرّر نتيجة اختبار فرضية. واشتراطُ رقمٍ ظاهر يجعل
# حذف الرقم وسيلةً لتمرير الادعاء نفسه.
# والصيغة تبتلع لاحقتها ومستواها: «دالة إحصائيًّا عند مستوى 0.05» ادّعاءٌ
# واحد، وحجبُ نصفه يترك نصفًا يقرأه القارئ ادّعاءً كاملًا.
_SIGNIFICANCE_TAIL = r"(?:\s*عند\s+مستوى(?:\s+الدلالة)?\s*[\d.]+)?"
SIGNIFICANCE_CLAIMS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"دالّ?(?:ة|ًا|ا)?\s+إحصائي[\u064B-\u0652ًٌٍَُِّْ]*(?:ية|ة|ا)?[\u064B-\u0652]*"
    + _SIGNIFICANCE_TAIL),
    re.compile(r"ذات\s+دلالة\s+إحصائية" + _SIGNIFICANCE_TAIL),
    re.compile(r"\bstatistically\s+significant\b", re.IGNORECASE),
    re.compile(r"\bsignificant\s+difference\b", re.IGNORECASE),
)


@dataclass(frozen=True, slots=True)
class StatisticHit:
    """قيمة إحصائية وُجدت في نصّ — بنوعها ومقتطفها وقيمتها."""

    kind: str
    excerpt: str
    value: str | None

    @property
    def is_bare_significance(self) -> bool:
        return self.value is None


def find(text: str) -> list[StatisticHit]:
    """كل قيمة إحصائية في النصّ، ثم ادّعاءات الدلالة بلا رقم."""
    body = normalise(text)
    hits: list[StatisticHit] = []
    for kind, pattern in STATISTIC_TOKENS.items():
        for match in pattern.finditer(body):
            hits.append(StatisticHit(kind=kind, excerpt=match.group(0).strip(),
                                     value=match.group(1)))
    for pattern in SIGNIFICANCE_CLAIMS:
        match = pattern.search(body)
        if match:
            hits.append(StatisticHit(kind="significance", excerpt=match.group(0),
                                     value=None))
            break
    return hits


def _values_in(payload) -> set[str]:
    """كل قيمة عددية في حمولة المخرَج — نصًّا كما خُزّنت، بلا تقريب."""
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for item in node.values():
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            found.add(_canonical(str(node)))
        elif isinstance(node, str):
            # يقبل `.05` كما يقبل `0.05` — والتمثيل ليس القيمة.
            for token in re.findall(r"-?\d*\.?\d+", normalise(node)):
                found.add(_canonical(token))

    walk(payload)
    return found


def _canonical(value: str) -> str:
    """`.05` و`0.05` و`0.050` قيمة واحدة — و`0.047` ليست منها."""
    try:
        return f"{float(value):.10g}"
    except ValueError:
        return value


def supports(hit: StatisticHit, payload) -> bool:
    """هل تحمل حمولة المخرَج هذه القيمة **بعينها**؟

    ولا تقريب: القيمة تُقارَن بقيمتها لا بأقرب منها. ومن قرّب بينهما جعل
    رقمًا لم يُحسب يبدو محسوبًا.
    """
    if hit.value is None:
        # ادّعاء دلالة بلا رقم: يسنده وجود مخرَج لاختبارٍ يقرّر الدلالة —
        # وذلك يُفحص خارج هذه الدالة بمفتاح الاختبار، لا بالأرقام.
        return True
    return _canonical(hit.value) in _values_in(payload)


def redact(text: str) -> tuple[str, list[str]]:
    """يحجب القيم الإحصائية من نصٍّ **قبل إرساله** (§21).

    ذاكرةٌ موثقة قد تحمل رقمًا لم يدخل محرّك التحليل بعد. وإرسالها كما هي
    دعوةٌ للنموذج أن يعيد رقمًا سيرفضه المدقّق بعد قليل — فيبدو الحارس
    تعسّفًا، ويُغرى المستخدم بتعطيله.

    فيُحجب الرقم ويُقال إنه غير متاح، ويبقى المعنى الذي يسنده الدليل.
    """
    body = normalise(text)
    removed: list[str] = []

    def _mask(label: str):
        def _replace(match: re.Match[str]) -> str:
            removed.append(match.group(0).strip())
            return label

        return _replace

    for pattern in STATISTIC_TOKENS.values():
        body = pattern.sub(_mask("[قيمة إحصائية غير متاحة بنيويًّا]"), body)
    # **وادّعاء الدلالة يُحجب كذلك.** «فروق دالة إحصائيًّا» يقرّر نتيجة اختبار
    # فرضية ولو خلا من رقم؛ وإرساله كما هو دعوةٌ لإعادته، ثم يرفضه المدقّق.
    # ويبقى ما يسنده الدليل: وجود فرق، واتجاهه.
    for pattern in SIGNIFICANCE_CLAIMS:
        body = pattern.sub(_mask("[دلالة إحصائية غير مسنَدة بمخرَج تحليل]"), body)
    return body, removed


__all__ = ["SIGNIFICANCE_CLAIMS", "STATISTIC_TOKENS", "StatisticHit", "find",
           "normalise", "redact", "supports"]
