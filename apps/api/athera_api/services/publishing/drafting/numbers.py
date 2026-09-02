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
    "p_value": re.compile(r"\bp\s*[=<>≤≥]\s*(-?0?[.,]\d+)", re.IGNORECASE),
    # وتلتقط درجات الحرية كذلك: `t(118)=3.738` ليست `t(117)=3.738`، والبُعد
    # جزءٌ من هوية القيمة لا زينة حولها.
    "t_statistic": re.compile(
        r"\bt\s*\(\s*(?P<df>\d+(?:[.,]\d+)?)\s*\)\s*=\s*(-?\d+(?:[.,]\d+)?)"),
    "f_statistic": re.compile(
        r"\bF\s*\(\s*(?P<df1>\d+)\s*,\s*(?P<df2>\d+)\s*\)\s*=\s*(-?\d+(?:[.,]\d+)?)"),
    "beta": re.compile(r"[βΒ]\s*=\s*(-?\d*[.,]?\d+)"),
    "r_squared": re.compile(r"\bR\s*[²2]\s*=\s*(-?\d*[.,]?\d+)", re.IGNORECASE),
    "correlation": re.compile(r"\br\s*=\s*(-?0?[.,]\d+)"),
    "eta_squared": re.compile(
        r"(?:مربع\s+إيتا|η\s*[²2]|eta[\s-]*squared)\s*[=:]?\s*(-?\d*[.,]?\d+)",
        re.IGNORECASE),
    "cohen_d": re.compile(r"\b(?:cohen'?s\s+)?d\s*=\s*(-?\d+(?:[.,]\d+)?)", re.IGNORECASE),
    "mean": re.compile(r"\b(?:M|المتوسط(?:\s+الحسابي)?)\s*[=:]\s*(-?\d+(?:[.,]\d+)?)"),
    "std_dev": re.compile(r"\b(?:SD|الانحراف\s+المعياري)\s*[=:]\s*(-?\d+(?:[.,]\d+)?)"),
    "confidence_interval": re.compile(
        r"\b(?:CI|فترة\s+الثقة)\s*[^\d\-]{0,12}(-?\d+(?:[.,]\d+)?)"),
    "composite_reliability": re.compile(r"\b(?:AVE|CR|HTMT)\s*=\s*(-?\d+(?:[.,]\d+)?)"),
    "percentage": re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|في\s+المئة|بالمئة)"),
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
    """قيمة إحصائية وُجدت في نصّ — بنوعها ومقتطفها وقيمتها وأبعادها.

    و`dims` ليست زينة: `t(118)=3.738` و`t(117)=3.738` نتيجتان مختلفتان،
    ومطابقةٌ تنظر إلى العدد وحده تخلط بينهما.
    """

    kind: str
    excerpt: str
    value: str | None
    dims: tuple[tuple[str, str], ...] = ()
    start: int = -1
    end: int = -1

    @property
    def is_bare_significance(self) -> bool:
        return self.value is None

    @property
    def identity(self) -> tuple:
        """هوية القيمة: نوعُها وقيمتُها وأبعادُها — لا رقمها وحده."""
        return (self.kind, _canonical(self.value or ""),
                tuple(sorted((k, _canonical(v)) for k, v in self.dims)))


def find(text: str) -> list[StatisticHit]:
    """كل قيمة إحصائية في النصّ، ثم ادّعاءات الدلالة بلا رقم."""
    body = normalise(text)
    hits: list[StatisticHit] = []
    for kind, pattern in STATISTIC_TOKENS.items():
        for match in pattern.finditer(body):
            groups = match.groupdict()
            # المجموعة الأخيرة غير المسمّاة هي القيمة؛ والمسمّاة أبعادها.
            value = match.group(match.lastindex) if match.lastindex else None
            dims = tuple((name, found) for name, found in groups.items() if found)
            hits.append(StatisticHit(kind=kind, excerpt=match.group(0).strip(),
                                     value=value, dims=dims,
                                     start=match.start(), end=match.end()))
    for pattern in SIGNIFICANCE_CLAIMS:
        match = pattern.search(body)
        if match:
            hits.append(StatisticHit(kind="significance", excerpt=match.group(0),
                                     value=None, start=match.start(), end=match.end()))
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
    """`.05` و`0.05` و`0.050` و`0,05` قيمة واحدة — و`0.047` ليست منها.

    والفاصلة اللاتينية تُقبل فاصلةً عشرية **بين رقمين**: الباحث يكتب بلوحة
    عربية أو لاتينية، ومطابقةٌ تعرف تمثيلًا واحدًا تفوّت نصف الحالات. ولا
    تُترجم في النصّ كله — فـ`F(1, 118)` فاصلتها فاصلُ أبعاد لا كسر.
    """
    try:
        return f"{float(value.replace(',', '.')):.10g}"
    except ValueError:
        return value


def all_values(payload) -> set[str]:
    """كل عدد في حمولة مخرَج — بصيغته الموحَّدة.

    **أوسع من `facts()` عمدًا.** تلك تعرف الأنواع المسمّاة؛ وهذه تقول: أي
    عدد **موجود فعلًا** في مخرَج تحليل مؤهَّل. ويحتاجها حارسُ أرقام العيّنة
    وحده: مفتاحٌ لا نعرف نوعه (`n_control` مثلًا) يبقى عددًا حقيقيًّا خرج من
    التحليل، ولا يجوز أن يُبلَّغ عنه رقمَ عيّنة مخترَعًا.
    """
    return _values_in(payload)


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

    # **والعلامة محايدة تجاه النموذج.** «[دلالة إحصائية محجوبة]» تُخبره أن
    # ثمة نتيجة دلالة، فيعيد بناءها من عنده — وهو ما وقع في أول نداء إنتاجي.
    # فالعلامة تقول «غير متاح» ولا تصف ما حُجب. والباحث يرى التفصيل في
    # `redacted_statistics`، وهو صاحب البيانات.
    for pattern in STATISTIC_TOKENS.values():
        body = pattern.sub(_mask("[غير متاح]"), body)
    # **وادّعاء الدلالة يُحجب كذلك.** «فروق دالة إحصائيًّا» يقرّر نتيجة اختبار
    # فرضية ولو خلا من رقم؛ وإرساله كما هو دعوةٌ لإعادته، ثم يرفضه المدقّق.
    # ويبقى ما يسنده الدليل: وجود فرق، واتجاهه.
    for pattern in SIGNIFICANCE_CLAIMS:
        body = pattern.sub(_mask("[غير متاح]"), body)
    return body, removed





# ══════════ حقائق المخرَج: النوع والقيمة والأبعاد ══════════
#
# **المطابقة بالنوع لا بالعدد.** حمولةٌ تحمل `n_control = 60` و`p = 0.106`
# لا تجعل «مربع إيتا = 0.106» مسنَدًا: تطابقُ الكسر العشري صدفةٌ لا سند.
#
# ومفاتيح الحمولة يكتبها الباحث بأسماء متعدّدة للمعنى الواحد، فتُقابَل
# بمرادفاتها المعروفة — وما لا يُعرف اسمه لا يُخمَّن له نوع.
_KEY_KINDS: Final[dict[str, str]] = {
    "p": "p_value", "p_value": "p_value", "pvalue": "p_value", "sig": "p_value",
    "significance": "p_value",
    "t": "t_statistic", "t_value": "t_statistic", "t_statistic": "t_statistic",
    "f": "f_statistic", "f_value": "f_statistic", "f_statistic": "f_statistic",
    "beta": "beta", "b": "beta",
    "r_squared": "r_squared", "r2": "r_squared", "rsquared": "r_squared",
    "r": "correlation", "correlation": "correlation",
    "eta_squared": "eta_squared", "eta2": "eta_squared",
    "partial_eta_squared": "eta_squared", "eta_sq": "eta_squared",
    "d": "cohen_d", "cohens_d": "cohen_d", "cohen_d": "cohen_d",
    "mean": "mean", "m": "mean", "average": "mean",
    "sd": "std_dev", "std": "std_dev", "std_dev": "std_dev",
    "standard_deviation": "std_dev",
    "percent": "percentage", "percentage": "percentage", "pct": "percentage",
    "ave": "composite_reliability", "cr": "composite_reliability",
    "htmt": "composite_reliability",
    "ci_lower": "confidence_interval", "ci_upper": "confidence_interval",
    "ci": "confidence_interval",
}

# مفاتيح تحمل أبعادًا لا نتائج — تُقيّد المطابقة ولا تُطابَق وحدها.
_DIMENSION_KEYS: Final[dict[str, str]] = {
    "df": "df", "degrees_of_freedom": "df", "df1": "df1", "df2": "df2",
}

# لكل نوع، أي أبعاد يجب أن تتفق إن وُجدت في الطرفين.
_REQUIRED_DIMS: Final[dict[str, tuple[str, ...]]] = {
    "t_statistic": ("df",),
    "f_statistic": ("df1", "df2"),
}


# لواحق تصف **أي مجموعة** لا نوع الإحصاء: `mean_control` متوسطٌ كذلك.
_GROUP_SUFFIXES: Final[tuple[str, ...]] = (
    "_control", "_treatment", "_experimental", "_pre", "_post", "_group",
    "_1", "_2", "_a", "_b",
)


def _base_key(key: str) -> str:
    for suffix in _GROUP_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return key


@dataclass(frozen=True, slots=True)
class StatisticFact:
    """واقعة إحصائية كما خزّنها التحليل."""

    kind: str
    value: str
    dims: tuple[tuple[str, str], ...] = ()


def facts(payload) -> list[StatisticFact]:
    """يستخرج الوقائع الإحصائية المعروفة من حمولة مخرَج.

    ويجمع الأبعاد على مستوى الكائن الذي وردت فيه: `{"t": 3.738, "df": 118}`
    واقعةٌ واحدة بدرجات حريتها، لا رقمان منفصلان.
    """
    found: list[StatisticFact] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            dims = tuple(
                (_DIMENSION_KEYS[k.lower()], _canonical(str(v)))
                for k, v in node.items()
                if k.lower() in _DIMENSION_KEYS and isinstance(v, (int, float, str))
                and not isinstance(v, bool)
            )
            for key, value in node.items():
                lowered = key.lower()
                if isinstance(value, (dict, list)):
                    walk(value)
                    continue
                if isinstance(value, bool) or value is None:
                    continue
                kind = _KEY_KINDS.get(lowered) or _KEY_KINDS.get(_base_key(lowered))
                if kind is None:
                    continue
                found.append(StatisticFact(kind=kind, value=_canonical(str(value)),
                                           dims=dims))
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def fact_supports(hit: StatisticHit, fact: StatisticFact) -> bool:
    """هل تسند هذه الواقعة ذلك المقتطف؟ نوعًا وقيمةً وبُعدًا.

    والأبعاد تُقارَن **حين تتوفّر في الطرفين**: مخرَجٌ لا يسجّل درجات الحرية
    لا يُرفض لأجل ما لم يسجّله؛ لكنه إن سجّلها ولم تتفق، فهي نتيجة أخرى.
    """
    if hit.kind != fact.kind or hit.value is None:
        return False
    if _canonical(hit.value) != fact.value:
        return False
    stated = dict(hit.dims)
    stored = dict(fact.dims)
    for dim in _REQUIRED_DIMS.get(hit.kind, ()):
        if dim in stated and dim in stored and _canonical(stated[dim]) != stored[dim]:
            return False
    return True


__all__ = ["SIGNIFICANCE_CLAIMS", "STATISTIC_TOKENS", "StatisticFact", "StatisticHit",
           "all_values", "fact_supports", "facts", "find", "normalise", "redact",
           "supports"]
