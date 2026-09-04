"""نيّة السؤال | Routing what the researcher actually asked for (Wave1-D).

**الباحث الذي قال «ابحث لي في الأدبيات» طلب فعلًا، لا إذنًا لطلبه.**

وكان المسار يستقبل هذا السؤال فيردّ باعتذار: «البحث الخارجي غير مفعّل»،
أو يقترح على الباحث أن يذهب إلى شاشةٍ أخرى ليبحث بنفسه. وكلاهما خذلانٌ
لطلبٍ صريح: القدرةُ قائمة، والسؤال لا لبس فيه، وإعادةُ السؤال عن الإذن
بعد طلبٍ صريح استهلاكٌ لوقت الباحث بلا فائدة.

فالتصنيف هنا **حتميٌّ ومقروء**: قائمتا مفردات، وقاعدةُ تركيبٍ واحدة،
و`matched` تعيد الكلمات التي قرّرت — فيُراجَع القرار ولا يُصدَّق.

**ولماذا لا نموذج؟** لأنّ نيّةً يقرّرها نموذجٌ تتغيّر بين نداءين على النصّ
نفسه، ولأنّ فشلها الصامت يُنفق نداءً خارجيًّا على فهرسٍ بلا سبب. والقاعدة
الحتمية تُقرأ وتُختبر وتُصحَّح بسطر.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

# ═════════════════ تسويةُ النصّ العربي ═════════════════
#
# التشكيل والتطويل ووجوه الألف والياء تجعل «الأدبيات» و«الادبيات» كلمتين
# مختلفتين للحاسوب وكلمةً واحدة للباحث. والتسوية تُجرى على النصّ وعلى
# المفردات معًا، فلا تُكتب المفردات مرّتين.
_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")


def normalize(text: str) -> str:
    """يسوّي النصّ للمطابقة وحدها — ولا يُخزَّن ولا يُرسل إلى أحد."""
    lowered = _TASHKEEL.sub("", (text or "").lower())
    for source, target in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
                           ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        lowered = lowered.replace(source, target)
    return re.sub(r"\s+", " ", lowered).strip()


def _terms(*words: str) -> tuple[str, ...]:
    return tuple(normalize(word) for word in words)


# ── الأدبيات: ما الذي يُطلب؟ ──
LITERATURE_OBJECTS: Final = _terms(
    "أدبيات", "الأدبيات", "دراسات", "الدراسات", "مراجع", "المراجع",
    "أبحاث", "الأبحاث", "بحوث", "أوراق علمية", "ورقة علمية", "منشورات",
    "مقالات علمية", "أدبٌ علمي",
    # **المفرد الإنجليزي العامّ خارج القائمة عمدًا** — `study` و`article`
    # تردان في «my study design» و«this article I am writing»، وليستا طلبَ
    # بحثٍ في الأدبيات. والاعتذارُ في غير موضعه خذلانٌ، والبحثُ في غير
    # موضعه إنفاقُ نداءٍ خارجيّ بلا سبب.
    "papers", "paper", "literature", "references", "studies",
    "articles", "publications", "prior work", "related work",
)

# ── وبأيّ فعلٍ يُطلب؟ ──
LITERATURE_VERBS: Final = _terms(
    "ابحث", "ابحثي", "بحث عن", "ابحث عن", "اعثر", "أعثر", "جد", "أوجد",
    "هات", "أعطني", "اعطني", "دلني", "دلّني", "استعرض", "اجمع", "التمس",
    "أحدث", "احدث", "آخر", "الجديد", "راجع الأدبيات",
    "find", "search", "look for", "get me", "show me",
    "latest", "recent", "newest",
)

# ── وعباراتٌ تكفي وحدها: طلبُ أدبياتٍ صريحٌ فيها بلا فعلٍ منفصل ──
LITERATURE_PHRASES: Final = _terms(
    "الدراسات السابقة", "دراسات سابقة", "أحدث الأدبيات", "مراجعة الأدبيات",
    "previous studies", "prior studies", "existing literature",
    "literature review", "recent literature", "search the literature",
)

# ── ما لا يُجاب إلا من نصٍّ كامل ──
#
# القائمة **ضيّقة عمدًا**. فكلّ مدخلٍ فيها يجعل المنصّة تعتذر، والاعتذار
# في غير موضعه خذلانٌ كالاختلاق. فما بقي هنا هو ما لا يوجد في ملخّصٍ
# قطعًا: نصٌّ حرفيّ، وموضعٌ في الورقة، وتفصيلُ إجراءٍ أو جدول.
FULL_TEXT_MARKERS: Final = _terms(
    "اقتبس", "اقتباس", "نصًّا حرفيًّا", "حرفيًا", "حرفياً", "نص حرفي",
    "رقم الصفحة", "الصفحة رقم", "في أي صفحة", "الجدول رقم",
    "قسم المنهجية", "قسم النتائج", "تفاصيل التحليل الإحصائي",
    "الملحق", "من النص الكامل", "النص الكامل للدراسة",
    "quote", "verbatim", "page number", "which page", "table number",
    "methods section", "results section", "appendix", "full text of",
)

# ── سؤالٌ عن مكتبة الباحث ومصادره المحفوظة ──
LIBRARY_MARKERS: Final = _terms(
    "مكتبتي", "مكتبة البحث", "مصادري", "المصادر المحفوظة", "مراجعي المحفوظة",
    "ما حفظته", "my library", "saved sources", "my references", "my sources",
)

# ── سؤالٌ عن المشروع نفسه ──
PROJECT_MARKERS: Final = _terms(
    "مشروعي", "بحثي الحالي", "مشروع البحث", "هذا البحث", "خطة بحثي",
    "my project", "this project", "my research project",
)

GENERAL: Final = "general"
LITERATURE_SEARCH: Final = "literature_search"
LIBRARY: Final = "library"
PROJECT: Final = "project"
FILE: Final = "file"

KINDS: Final = (GENERAL, LITERATURE_SEARCH, LIBRARY, PROJECT, FILE)


@dataclass(frozen=True, slots=True)
class Intent:
    """نيّةٌ مقروءة — ومعها **الكلمات التي قرّرتها**، فتُراجَع لا تُصدَّق."""

    kind: str
    needs_full_text: bool = False
    matched: tuple[str, ...] = ()

    @property
    def wants_literature_search(self) -> bool:
        return self.kind == LITERATURE_SEARCH


def _hits(text: str, vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(word for word in vocabulary if word and word in text)


def wants_literature(question: str) -> tuple[bool, tuple[str, ...]]:
    """هل طلب الباحث بحثًا في الأدبيات صراحةً؟

    والقاعدة تركيبيّة لا كلمةٌ واحدة: «راجع منهجيتي» فيها فعلٌ بلا مفعول،
    و«الأدبيات» وحدها قد ترد في سؤالٍ نظري. فيُشترط **فعلٌ ومفعول معًا**،
    أو عبارةٌ صريحة تكفي وحدها.
    """
    text = normalize(question)
    phrases = _hits(text, LITERATURE_PHRASES)
    if phrases:
        return True, phrases
    objects = _hits(text, LITERATURE_OBJECTS)
    verbs = _hits(text, LITERATURE_VERBS)
    if objects and verbs:
        return True, objects + verbs
    return False, ()


def needs_full_text(question: str) -> tuple[bool, tuple[str, ...]]:
    """هل يستحيل الجواب من ملخّص؟ — والقائمة ضيّقة عمدًا."""
    text = normalize(question)
    hits = _hits(text, FULL_TEXT_MARKERS)
    return bool(hits), hits


def classify(question: str, *, has_attachment: bool = False,
             has_project: bool = False) -> Intent:
    """نيّةٌ واحدة، وعلَمُ «يحتاج نصًّا كاملًا» مستقلٌّ عنها.

    ولم يُجعل «يحتاج نصًّا كاملًا» نيّةً خامسة عمدًا: سؤالٌ يطلب دراساتٍ
    **ويطلب اقتباسًا منها** يستحقّ البحث *و*التحفّظ معًا. ولو كان نيّةً
    مانعة لسقط البحث الذي طُلب صراحةً.
    """
    text = normalize(question)
    full_text, full_hits = needs_full_text(question)

    if has_attachment:
        return Intent(FILE, needs_full_text=full_text, matched=full_hits)

    literature, lit_hits = wants_literature(question)
    if literature:
        return Intent(LITERATURE_SEARCH, needs_full_text=full_text,
                      matched=lit_hits + full_hits)

    library = _hits(text, LIBRARY_MARKERS)
    if library:
        return Intent(LIBRARY, needs_full_text=full_text, matched=library + full_hits)

    project = _hits(text, PROJECT_MARKERS)
    if project or has_project:
        return Intent(PROJECT, needs_full_text=full_text, matched=project + full_hits)

    return Intent(GENERAL, needs_full_text=full_text, matched=full_hits)
