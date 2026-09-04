"""تسويةُ النصّ العربي وتصنيف النتائج | Arabic normalisation + result reading.

**هذا الملف يقرأ ولا يفسّر.** كل ما فيه دوالُّ حتمية على نصٍّ **كتبه الباحث
بيده في خلية المصفوفة** — لا على ملخّصٍ ولا على نصّ نموذج. ومخرَجها
تصنيفٌ صريح أو `not_stated`: لا تخمين، ولا قيمةٌ افتراضية تُقرأ حكمًا.

**والصمت لا يُصنَّف.** «لم تُذكر الدلالة» ليست «غير دالّ إحصائيًّا»، وخلطهما
يصنع تعارضًا من صمتِ ورقة. فالتصنيف الافتراضي `not_stated` دائمًا، ولا
تُشتقّ منه مقارنة.

**والنفي يُقرأ قبل المثبَت.** «غير دالّة إحصائيًّا» تحوي «دالّة»؛ ولو فُحص
المثبَت أولًا لصار كل نفيٍ إثباتًا — وهو عطبٌ يقلب نتيجة ورقةٍ رأسًا على عقب.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Final

# التشكيل والتطويل — يُنزعان قبل أي مقارنة، وإلا صارت «الأداء» و«الأداءُ»
# كلمتين، فانقسم موضوعٌ واحد إلى موضوعين.
_DIACRITICS: Final = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")

# صور الألف والياء والتاء المربوطة — تُوحَّد لأن الكاتبين يكتبونها مختلفة.
_LETTER_FOLD: Final = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ة": "ه",
    "ؤ": "و",
})

# **الفاصلة العربية حرفٌ في نطاق العربية.** ولو كُتب صفُّ المحارف
# `[^\w؀-ۿ]` — أي «احتفظ بكل ما في نطاق العربية» — لبقيت «،» و«؛» و«؟»
# ملتصقةً بالكلمات، فصارت «التدريب،» كلمةً غير «التدريب»، ولم يتقابل بناءان
# متطابقان أبدًا. فالمعيار `\w` وحده، وهو يعرف الحروف العربية.
_NON_WORD: Final = re.compile(r"[\W_]+", re.UNICODE)

# الكلمة كما كُتبت — تُستعمل للعرض وحده. والمسوّاة تُقارن ولا تُعرض: لا
# يُكتب للباحث «احصاييا» في اسم موضوع.
_WORD: Final = re.compile(r"[^\W_]+", re.UNICODE)

# **كلماتٌ لا تميّز شيئًا.** موضوعٌ اسمه «على» أو «الدراسة» ليس موضوعًا؛
# وبدون هذه القائمة يصير أكثر «الموضوعات» حروف جرّ.
#
# وتُسوّى هذه القائمة وكلُّ قائمةٍ بعدها **بالدالّة نفسها** التي تُسوّى بها
# النصوص المقروءة. وكتابةُ المفردة يدًا بصورتها المسوّاة عطبٌ صامت: «إحصائيًا»
# تصير «احصاييا» بعد توحيد الهمزات، فلا تطابق «احصائيا» المكتوبة يدًا، فيُقرأ
# كلُّ نصٍّ دالٍّ إحصائيًّا «غير مذكور» — ولا شيء يشتكي.
_RAW_STOPWORDS: Final = frozenset({
    "في", "من", "على", "الى", "عن", "مع", "بين", "هذا", "هذه", "ذلك", "التي",
    "الذي", "ما", "لا", "ان", "او", "ثم", "قد", "كان", "كانت", "هو", "هي",
    "الدراسه", "دراسه", "دراسات", "بحث", "البحث", "نتائج", "النتائج", "اثر",
    "الاثر", "تاثير", "التاثير", "علاقه", "العلاقه", "دور", "الدور", "واقع",
    "مستوى", "درجه", "الى", "لدى", "عند", "بعض", "كل", "غير", "بعد", "قبل",
    "the", "a", "an", "of", "in", "on", "and", "or", "to", "for", "with",
    "study", "studies", "research", "effect", "impact", "role", "between",
    "among", "level", "degree", "this", "that", "is", "are", "was", "were",
    # **ألفاظُ وصفِ النتيجة ليست موضوعات.** «إحصائيًّا» و«دالّة» و«إيجابية»
    # تتكرّر في كل خلية نتائج، فتتصدّر قائمة «الموضوعات» بلا أن تعني شيئًا —
    # ويقرأ الباحث موضوعًا اسمه «دالة» فيفقد الثقة في القائمة كلّها.
    "احصائيا", "احصائية", "داله", "دال", "دلاله", "معنويه",
    "ايجابيه", "ايجابي", "سلبيه", "سلبي", "موجب", "سالب", "ارتباط",
    "significant", "significance", "positive", "negative", "correlation",
    "association", "relationship",
})

# أقلّ طولٍ لكلمةٍ تصلح مفتاحًا. وما دونه حروفٌ لا تميّز.
MIN_TERM_LENGTH: Final = 3


def normalize(text: str | None) -> str:
    """نصٌّ مسوّى للمقارنة — ولا يُعرض للباحث أبدًا (يفقد تشكيله وهمزاته)."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text)
    folded = _DIACRITICS.sub("", folded)
    folded = folded.translate(_LETTER_FOLD)
    return _NON_WORD.sub(" ", folded.casefold()).strip()


def _fold_all(words) -> tuple[str, ...]:
    """يسوّي قائمةَ مفرداتٍ بالدالّة نفسها — **فلا موضعان يفترقان بحرف**."""
    return tuple(sorted({normalize(word) for word in words} - {""}))


def _lex(*words: str) -> tuple[str, ...]:
    return _fold_all(words)


STOPWORDS: Final = frozenset(_fold_all(_RAW_STOPWORDS))


# سوابقُ التعريف وما يتّصل بها. و**«والأداء» و«الأداء» و«أداء» كلمةٌ واحدة**:
# بدون هذه القائمة لا يتقابل بناءان مكتوبان بترتيبٍ مختلف أبدًا — «التدريب
# والأداء» و«الأداء والتدريب» يخرجان مجموعتين مختلفتين، فلا يُكتشف تعارضٌ
# حقيقيّ ولا يُجمع موضوعٌ واحد.
#
# ولا تُنزع الواو وحدها: «وظيفي» ليست «ظيفي». فالنزع مشروطٌ بلحاق «ال».
_ARTICLE_PREFIXES: Final = ("وال", "بال", "كال", "فال", "ال")


# **جذورٌ تبدأ بـ«وال» ولا واوَ عطفٍ فيها.**
#
# الشرطُ الموضعي يحمي أوّل اللفظ، ولا يحمي وسطه: «دور والدين في التحصيل»
# تُنتج «دين». والعائلة صغيرة ومغلقة — كلُّ ما اشتُقّ من «والد» — فتُستثنى
# بسابقةٍ واحدة لا بقائمة صيغ.
#
# وهذه معالجةٌ صرفيةٌ محافظة لا مُحلِّل صرفيّ: ما لم يُذكر هنا يبقى على
# القاعدة العامة، وذلك حدٌّ معلومٌ لا عيبٌ مستور.
_WAW_IS_RADICAL: Final = ("والد",)


def _strip_article(token: str, *, leading: bool = False) -> str:
    """ينزع سابقة التعريف، والواوَ العاطفة معها — **بشرط موضعها**.

    و«وال» وحدها مشروطةٌ بألّا يكون الرمز أوّلَ اللفظ: الواو العاطفة لا
    تبدأ عبارة، فما بدأ بها فواوُه من أصل الكلمة. ولولا هذا الشرط لصارت
    «والدين» ← «دين»، فيُقرأ بناءٌ عن الوالدين بناءً عن التديّن — وهما
    موضوعان لا يجمعهما شيء، ولا شيء في الشاشة يشتكي.

    وبقيّةُ السوابق («ال» و«بال» و«كال» و«فال») لا يقع فيها هذا اللبس،
    فتُنزع حيث وقعت.
    """
    if token.startswith(_WAW_IS_RADICAL):
        return token
    for prefix in _ARTICLE_PREFIXES:
        if prefix == "وال" and leading:
            continue
        if (token.startswith(prefix)
                and len(token) - len(prefix) >= MIN_TERM_LENGTH):
            return token[len(prefix):]
    return token


def term_forms(text: str | None) -> dict[str, str]:
    """المفتاح المسوّى ← **الكلمة كما كتبها الباحث**.

    والحاجة إليها أن المسوّاة لا تُعرض: «إحصائيًّا» تصير «احصاييا» بعد توحيد
    الهمزات، وموضوعٌ اسمه «احصاييا» يقرؤه الباحث عطبًا لا نتيجة. فتُحفظ
    الصورة الأصلية للعرض، وتبقى المسوّاة للمقارنة وحدها.
    """
    out: dict[str, str] = {}
    if not text:
        return out
    cleaned = _DIACRITICS.sub("", unicodedata.normalize("NFKC", text))
    for position, raw in enumerate(_WORD.findall(cleaned)):
        token = _strip_article(normalize(raw), leading=position == 0)
        if len(token) >= MIN_TERM_LENGTH and token not in STOPWORDS:
            out.setdefault(token, raw)
    return out


def terms(text: str | None) -> frozenset[str]:
    """المفاتيح المميِّزة في نصّ خلية — **مجموعةٌ لا ترتيب**.

    والترتيب لا يعني شيئًا هنا: «الرضا والأداء» و«الأداء والرضا» بناءان
    متطابقان، ومقارنتهما نصًّا تُنتج تعارضًا من ترتيب كلمتين.

    وتُشتقّ من `term_forms` ولا تُحسب مرّةً ثانية: حسابان للشيء نفسه
    يفترقان بأول تعديل، فيُقارَن مفتاحٌ لا وجود له في قائمة العرض.
    """
    return frozenset(term_forms(text))


# ── قراءة النتيجة: الاتجاه والدلالة والخلاصة ──
#
# **والنفي أولًا.** كل قائمةٍ من هذه تُفحص قبل مثبَتها.

_NO_EFFECT: Final = _lex(
    "لا اثر", "لا يوجد اثر", "عدم وجود اثر", "لا توجد علاقه", "لا علاقه",
    "عدم وجود علاقه", "لم يظهر اثر", "لا فروق", "عدم وجود فروق",
    "no effect", "no relationship", "no association", "no significant relationship",
)
_NEGATIVE: Final = _lex(
    "اثر سلبي", "علاقه سلبيه", "ارتباط سالب", "علاقه عكسيه", "اثر عكسي",
    "ينخفض", "انخفاض", "يقلل", "تقلل", "سلبا",
    "negative effect", "negative relationship", "inverse", "decrease", "reduces",
)
_POSITIVE: Final = _lex(
    "اثر ايجابي", "علاقه ايجابيه", "ارتباط موجب", "علاقه طرديه", "اثر طردي",
    "يزيد", "زياده", "يحسن", "تحسن", "ايجابا",
    "positive effect", "positive relationship", "increase", "improves", "enhances",
)
_MIXED: Final = _lex("اثر مختلط", "نتائج مختلطه", "متباين", "mixed effect", "mixed results")

# **ولا قيمة `p` في هذه القوائم.** التسوية تُسقط `<` و`>` فتصير «p < 0.05»
# و«p > 0.05» نصًّا واحدًا — فيُقرأ الدالُّ غيرَ دالّ. والصمت أسلم من قلب
# نتيجةٍ رأسًا على عقب: من كتب دلالته بقيمة `p` وحدها تبقى دلالته «غير مذكورة»،
# وهي حالٌ صادقة لا حكمٌ مقلوب.
_NOT_SIGNIFICANT: Final = _lex(
    "غير داله", "غير دال", "ليست داله", "ليس دالا", "لم تكن داله",
    "not significant", "non significant", "nonsignificant", "insignificant",
)
_SIGNIFICANT: Final = _lex(
    "داله احصائيا", "دال احصائيا", "دالا احصائيا", "ذات دلاله", "بدلاله احصائيه",
    "statistically significant", "significant at",
)

_REFUTES: Final = _lex(
    "لا تدعم الفرضيه", "لم تدعم الفرضيه", "ترفض الفرضيه", "لا تؤيد",
    "does not support", "fails to support", "rejects the hypothesis",
)
_SUPPORTS: Final = _lex(
    "تدعم الفرضيه", "تؤيد الفرضيه", "تتفق مع", "supports the hypothesis",
    "consistent with", "supports",
)


def _has_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def direction_of(text: str | None) -> str:
    """اتجاهُ الأثر كما **صرّح به النصّ** — و`not_stated` عند الصمت."""
    hay = normalize(text)
    if not hay:
        return "not_stated"
    if _has_any(hay, _MIXED):
        return "mixed"
    if _has_any(hay, _NO_EFFECT):
        return "none"
    if _has_any(hay, _NEGATIVE):
        return "negative"
    if _has_any(hay, _POSITIVE):
        return "positive"
    return "not_stated"


def significance_of(text: str | None) -> str:
    """الدلالة كما صُرّح بها — **والنفي يُقرأ قبل المثبَت**."""
    hay = normalize(text)
    if not hay:
        return "not_stated"
    if _has_any(hay, _NOT_SIGNIFICANT):
        return "not_significant"
    if _has_any(hay, _SIGNIFICANT):
        return "significant"
    return "not_stated"


def stance_of(text: str | None) -> str:
    """خلاصةُ الورقة تجاه فرضيتها — `supports` أو `refutes` أو `not_stated`."""
    hay = normalize(text)
    if not hay:
        return "not_stated"
    if _has_any(hay, _REFUTES):
        return "refutes"
    if _has_any(hay, _SUPPORTS):
        return "supports"
    return "not_stated"


# ── البلدان: تُقرأ إن ذُكرت، ولا تُستنتج ──
#
# **وغيابُ الذكر ليس غيابًا للبلد.** ورقةٌ لم تذكر بلدها في الخلية لا يُقال
# إنها «ليست سعودية»؛ يُقال إن بلدها **غير مسجَّل في المصفوفة**.
_RAW_COUNTRY_TERMS: Final[dict[str, tuple[str, ...]]] = {
    "السعودية": ("السعوديه", "المملكه العربيه السعوديه", "الرياض", "جده",
                 "saudi", "saudi arabia", "ksa"),
    "الإمارات": ("الامارات", "دبي", "ابوظبي", "uae", "emirates"),
    "مصر": ("مصر", "القاهره", "egypt"),
    "الأردن": ("الاردن", "عمان الاردن", "jordan"),
    "الكويت": ("الكويت", "kuwait"),
    "قطر": ("قطر", "qatar"),
    "الولايات المتحدة": ("الولايات المتحده", "امريكا", "united states", "usa", "u s "),
    "المملكة المتحدة": ("المملكه المتحده", "بريطانيا", "united kingdom", "uk ", "britain"),
    "الصين": ("الصين", "china"),
    "ماليزيا": ("ماليزيا", "malaysia"),
    "تركيا": ("تركيا", "turkey", "turkiye"),
}


COUNTRY_TERMS: Final[dict[str, tuple[str, ...]]] = {
    name: _fold_all(words) for name, words in _RAW_COUNTRY_TERMS.items()
}


def country_in(*texts: str | None) -> str | None:
    """أوّلُ بلدٍ **مذكور** في هذه النصوص — و`None` تعني «غير مسجَّل»."""
    hay = " ".join(normalize(t) for t in texts if t)
    if not hay:
        return None
    for country in sorted(COUNTRY_TERMS):
        if _has_any(hay, COUNTRY_TERMS[country]):
            return country
    return None


# ── أسرة التصميم: تُقرأ من نصّ الخلية إن صُرّح بها ──
_RAW_DESIGN_FAMILIES: Final[dict[str, tuple[str, ...]]] = {
    "مقطعية": ("مقطعيه", "مقطعي", "cross sectional", "cross-sectional"),
    "طولية": ("طوليه", "طولي", "تتبعيه", "longitudinal", "panel study", "cohort"),
    "تجريبية": ("تجريبيه", "تجريبي", "شبه تجريبيه", "experimental", "quasi experimental"),
    "نوعية": ("نوعيه", "كيفيه", "مقابلات", "qualitative", "interviews", "ethnograph"),
    "مراجعة": ("مراجعه منهجيه", "تحليل بعدي", "systematic review", "meta analysis"),
}


DESIGN_FAMILIES: Final[dict[str, tuple[str, ...]]] = {
    name: _fold_all(words) for name, words in _RAW_DESIGN_FAMILIES.items()
}


def design_family(*texts: str | None) -> str | None:
    """أسرةُ التصميم **المصرَّح بها** — و`None` تعني أنها غير مسجَّلة."""
    hay = " ".join(normalize(t) for t in texts if t)
    if not hay:
        return None
    for family in sorted(DESIGN_FAMILIES):
        if _has_any(hay, DESIGN_FAMILIES[family]):
            return family
    return None


__all__ = [
    "COUNTRY_TERMS",
    "DESIGN_FAMILIES",
    "MIN_TERM_LENGTH",
    "STOPWORDS",
    "country_in",
    "design_family",
    "direction_of",
    "normalize",
    "significance_of",
    "stance_of",
    "term_forms",
    "terms",
]
