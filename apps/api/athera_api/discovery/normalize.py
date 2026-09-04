"""تسوية القيم قبل المطابقة | Normalisation for matching.

التسوية هنا **لخدمة المقارنة وحدها**: لا يُعرض على الباحث نصٌّ مسوَّى، ولا
يُخزَّن. العنوان يُعرض كما ورد من الفهرس، ويُقارَن بصورته المسوّاة — فالفرق
بين «Al‑Qassim» و«al qassim» فرقُ كتابةٍ لا فرقُ ورقة.

وهنا **التعريف الوحيد للـDOI** في المنتج؛ سجلّ الأدبيات يعيد تصديره. وضعُه
في حزمةٍ نقيّة لا تلمس قاعدة بيانات مقصود: يبقى قابلًا للاختبار في بيئةٍ بلا
SQLAlchemy، وهو شرطٌ قائمٌ في هذه الحزمة.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")


def normalize_doi(value: str) -> str | None:
    """يقبل DOI خامًا أو داخل رابط، ويرفض ما ليس DOI."""
    if not value:
        return None
    candidate = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "https://dx.doi.org/"):
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):]
    candidate = candidate.rstrip(".,;)")
    return candidate if DOI_PATTERN.match(candidate) else None


_DIACRITICS = re.compile(r"[ً-ْٰـ]")
_NON_WORD = re.compile(r"[^0-9a-zء-ي]+")
_DOI_ANYWHERE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

# منصّات تمنع الجمع الآلي في شروطها. الحجب هنا **قرار امتثال لا تفضيل**:
# لا يُطلب منها شيء، ولا تُقرأ منها بيانات وصفية بأي حال (§33.3).
BLOCKED_HOSTS: frozenset[str] = frozenset({
    "researchgate.net", "www.researchgate.net",
    "academia.edu", "www.academia.edu",
})


# كل فهرسٍ يسمّي أنواع الأعمال بمفرداته: Crossref يقول `journal-article`
# وOpenAlex يقول `article` عن الشيء نفسه. ومرشِّحُ نوعٍ يقارن الحرفَ بالحرف
# يُخفي نصف النتائج بحسب من ردّ أولًا. فالتصنيف هنا **سلّةُ عرضٍ معلنة**،
# والنصّ الخام يبقى في ادعاء كل فهرس ليُقرأ كما قاله صاحبه.
_WORK_TYPES: dict[str, str] = {
    "journal-article": "journal-article",
    "article": "journal-article",
    "proceedings-article": "conference-paper",
    "proceedings": "conference-paper",
    "conference-paper": "conference-paper",
    "book-chapter": "book-chapter",
    "book-section": "book-chapter",
    "book": "book",
    "book-part": "book-chapter",
    "monograph": "book",
    "edited-book": "book",
    "posted-content": "preprint",
    "preprint": "preprint",
    "dissertation": "thesis",
    "thesis": "thesis",
    "dataset": "dataset",
    "report": "report",
    "review": "review",
    "peer-review": "review",
}

WORK_TYPES: frozenset[str] = frozenset(_WORK_TYPES.values()) | {"other"}


def canonical_work_type(raw: str | None) -> str | None:
    """سلّةُ النوع للعرض والتصفية. `None` تعني «لم يقل الفهرس نوعًا»."""
    if not raw:
        return None
    return _WORK_TYPES.get(raw.strip().lower(), "other")


def _fold(text: str) -> str:
    """طيُّ الاختلافات الإملائية التي لا تغيّر الورقة المقصودة."""
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = _DIACRITICS.sub("", folded)
    folded = folded.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    folded = folded.replace("ى", "ي").replace("ة", "ه")
    return folded.lower()


def normalized_title(title: str) -> str:
    """عنوانٌ مسوَّى للمقارنة الحرفية — لا للعرض ولا للتخزين."""
    return " ".join(part for part in _NON_WORD.split(_fold(title)) if part)


def first_author_key(authors: tuple[str, ...] | list[str]) -> str | None:
    """مفتاح المؤلّف الأول: آخر لفظةٍ من اسمه مسوّاةً — أي اسم العائلة غالبًا.

    الفهارس تكتب الاسم بترتيبين ودرجتَي اختصار («Jane Q. Smith» و«Smith, J»)،
    فالمقارنة على الاسم كاملًا تُفرّق ورقةً واحدة إلى ورقتين. ولفظةٌ واحدة
    وحدها لا تكفي دليلًا على التطابق — لذلك لا تُستعمل إلا مع العنوان والسنة.
    """
    for name in authors:
        parts = [part for part in _NON_WORD.split(_fold(name)) if part]
        if parts:
            return parts[-1]
    return None


def extract_doi_anywhere(text: str) -> str | None:
    """يلتقط DOI من نصٍّ حرّ أو من رابط. لا يخترع واحدًا إن لم يكن فيه."""
    if not text:
        return None
    direct = normalize_doi(text)
    if direct:
        return direct
    match = _DOI_ANYWHERE.search(text)
    return normalize_doi(match.group(0)) if match else None


def external_access_link(text: str) -> tuple[str, str] | None:
    """هل النصّ رابطٌ إلى منصّةٍ نمتنع عن جمعها؟ يعيد (الرابط، المضيف).

    الامتناع ليس صمتًا: الرابط يُعاد إلى الباحث ليحفظه «رابط وصول إضافي»،
    وتُطلب بياناته الوصفية من معرّفٍ شرعي — أو يُقال إنها لم تُتحقَّق.
    """
    candidate = (text or "").strip()
    if not candidate.lower().startswith(("http://", "https://")):
        return None
    host = (urlparse(candidate).hostname or "").lower()
    return (candidate, host) if host in BLOCKED_HOSTS else None
