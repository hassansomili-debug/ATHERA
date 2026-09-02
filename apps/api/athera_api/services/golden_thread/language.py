"""الفحوص اللغوية | Linguistic checks (§15.2).

كشفان من التسعة لغويان: اللغة السببية في دراسة ارتباطية، والتعميم الأكبر
من العينة.

الدرس المستفاد من حواجز Sprint 2 مطبَّق هنا مسبقًا: **حاجز يعاقب الصدق
أسوأ من حاجز يفوّت خطأ.** جملة تتحفظ («لا تدّعي الدراسة علاقة سببية»)
أو تنفي التعميم صراحةً هي اللغة العلمية المطلوبة — فتمر، ولا تُحسب مخالفة.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .vocab import CAUSAL_DESIGNS, SAMPLING_STRATEGIES

# صيغ سببية صريحة — عربية وإنجليزية.
_CAUSAL_PATTERNS = [
    # الفاعل يتوسّط الفعل وحرف الجرّ كثيرًا في العربية: «يؤدي التعلّم النشط
    # إلى…». والصيغة الملاصقة وحدها كانت تفوّت أكثر الجمل السببية شيوعًا،
    # وهي مبنى سببي صريح لا يقلّ عن «يؤدي إلى». والمدى محدود بثلاث كلمات كي
    # يبقى الكشف داخل التركيب الواحد لا عبر الجملة كلها.
    re.compile(r"يؤدي\s+(?:\S+\s+){0,3}إلى"),
    re.compile(r"تؤدي\s+(?:\S+\s+){0,3}إلى"),
    re.compile(r"(?:يسبب|تسبب|يتسبب)"),
    re.compile(r"ينتج\s+عن(?:ه|ها)?"),
    re.compile(r"(?:أثر|تأثير)\s+\S+\s+(?:على|في)\s+\S+"),
    re.compile(r"بسبب\s+\S+"),
    re.compile(r"\bcaus(?:e|es|ed|ing)\b", re.IGNORECASE),
    re.compile(r"\blead(?:s|ing)?\s+to\b", re.IGNORECASE),
    re.compile(r"\bresult(?:s|ed|ing)?\s+in\b", re.IGNORECASE),
    re.compile(r"\bdue\s+to\b", re.IGNORECASE),
    re.compile(r"\bthe\s+(?:effect|impact)\s+of\s+\S+\s+on\b", re.IGNORECASE),
]

# تحفّظ أو نفي — يُبطل الكشف في الجملة نفسها.
_HEDGE_PATTERNS = [
    re.compile(r"لا\s+(?:يمكن|تدّعي|ندّعي|يُستدل|تعني)"),
    re.compile(r"ليست?\s+علاقة\s+سببية"),
    re.compile(r"لا\s+تعني\s+السببية"),
    re.compile(r"ارتباط\s+لا\s+سببية"),
    re.compile(r"قد\s+(?:يشير|تشير|يرتبط|ترتبط)"),
    re.compile(r"\bdoes\s+not\s+(?:imply|establish|prove)\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+(?:be\s+)?(?:infer|inferred|establish|claim)\b", re.IGNORECASE),
    re.compile(r"\bcorrelation\s+does\s+not\b", re.IGNORECASE),
    re.compile(r"\bno\s+causal\b", re.IGNORECASE),
    re.compile(r"\bnot\s+causal\b", re.IGNORECASE),
]

# ألفاظ تعميم شامل.
_GENERALIZATION_PATTERNS = [
    # أُضيف «الطلاب» و«المعلمين» و«الطالبات»: المنصّة تخدم البحث التربوي
    # أولًا، وتعميمٌ على «جميع الطلاب» من عينة متاحة هو الحالة الشائعة فيه —
    # وكانت تمرّ لأن المفردات لم تشملها (§24: التوسيع عند الحاجة).
    re.compile(r"(?<!لا\s)(?:جميع|كل)\s+(?:ال)?(?:المستهلكين|الباحثين|الأفراد|"
               r"الجمهور|السكان|الناس|طلاب|الطلاب|الطالبات|المعلمين|المعلمات)"),
    re.compile(r"المجتمع\s+(?:السعودي|العربي|كامل|كله)"),
    re.compile(r"(?:دائمًا|دومًا|في\s+كل\s+الحالات)"),
    re.compile(r"\ball\s+(?:consumers|people|individuals|users|researchers)\b", re.IGNORECASE),
    re.compile(r"\b(?:always|never|universally)\b", re.IGNORECASE),
    re.compile(r"\bthe\s+entire\s+population\b", re.IGNORECASE),
]

_GENERALIZATION_HEDGES = [
    re.compile(r"لا\s+(?:يمكن|تُعمَّم|يمكن\s+تعميم)"),
    re.compile(r"(?:تقتصر|يقتصر)\s+على\s+العينة"),
    re.compile(r"ضمن\s+حدود\s+العينة"),
    re.compile(r"\bcannot\s+be\s+generali[sz]ed\b", re.IGNORECASE),
    re.compile(r"\blimited\s+to\s+the\s+sample\b", re.IGNORECASE),
    re.compile(r"\bnot\s+generali[sz]able\b", re.IGNORECASE),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+|\n+")


@dataclass(slots=True)
class LanguageHit:
    sentence: str
    matched: str


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]


def _hedged(sentence: str, hedges: list[re.Pattern[str]]) -> bool:
    return any(pattern.search(sentence) for pattern in hedges)


def find_causal_language(text: str, *, design_family: str | None, study_type: str) -> list[LanguageHit]:
    """§15.2 — لغة سببية في دراسة ارتباطية.

    لا يعمل على التصاميم التجريبية: السببية مشروعة فيها، والكشف عنها هناك
    خطأ لا اكتشاف.
    """
    if study_type in CAUSAL_DESIGNS or (design_family or "") in CAUSAL_DESIGNS:
        return []

    hits: list[LanguageHit] = []
    for sentence in _sentences(text):
        if _hedged(sentence, _HEDGE_PATTERNS):
            continue
        for pattern in _CAUSAL_PATTERNS:
            match = pattern.search(sentence)
            if match:
                hits.append(LanguageHit(sentence=sentence[:300], matched=match.group(0)))
                break
    return hits


def find_overgeneralization(text: str, *, sampling_strategy: str | None) -> list[LanguageHit]:
    """§15.2 — تعميم أكبر من العينة.

    يُفحص مقابل أسلوب المعاينة: «جميع المستهلكين» مع عينة ميسّرة كشفٌ،
    ومع عينة احتمالية ممثِّلة ليس كذلك.
    """
    if sampling_strategy and SAMPLING_STRATEGIES.get(sampling_strategy, False):
        return []

    hits: list[LanguageHit] = []
    for sentence in _sentences(text):
        if _hedged(sentence, _GENERALIZATION_HEDGES):
            continue
        for pattern in _GENERALIZATION_PATTERNS:
            match = pattern.search(sentence)
            if match:
                hits.append(LanguageHit(sentence=sentence[:300], matched=match.group(0)))
                break
    return hits


def mentions_theory(text: str, theory_name: str) -> bool:
    """هل ذُكرت النظرية في هذا النص؟ مطابقة متساهلة مع اسم النظرية."""
    if not theory_name.strip():
        return False
    needle = re.escape(theory_name.strip())
    return re.search(needle, text or "", re.IGNORECASE) is not None
