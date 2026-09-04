"""فهم الاستعلام | Query intelligence.

**نيّة الباحث لا تُعاد كتابتها في الخفاء.** الاستعلام يُقرأ ليُفهم — DOI،
أو عبارةٌ بين قوسين، أو اسم مؤلّف، أو سنة، أو كلماتٌ مفتاحية — ثم يُقال
للباحث ما فُهم منه، ويبقى نصّه كما كتبه ظاهرًا وقابلًا للمقارنة.

والتوسيع اقتراحٌ لا تنفيذ: `suggestions` قائمة مصطلحاتٍ تُعرض ليقبلها
الباحث أو يرفضها، ولا يدخل منها شيءٌ في الطلب حتى يقبله. والسبب عمليّ لا
تجميلي: «التعلّم العميق» ليس مرادفًا لـ«التعلّم الآلي» وإن جاورَه في
الأدبيات — ومن وسّع البحث نيابةً عن الباحث غيّر سؤاله البحثي ثم أراه
نتائج سؤالٍ آخر على أنها نتائج سؤاله.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import extract_doi_anywhere, tokens

# ألفاظٌ تربط ولا تدلّ على موضوع. إسقاطها من الكلمات المفتاحية يمنع أن
# يُحسب تطابقُ «في» و«of» تطابقًا في المضمون — وهو أكثر ما يصنع الإيجابيات
# الكاذبة في المطابقة اللفظية.
STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "in", "on", "for", "and", "or", "to", "with", "by",
    "at", "from", "as", "is", "are", "was", "were", "be", "been", "that", "this",
    "these", "those", "its", "it", "into", "between", "among", "using", "used",
    "use", "study", "studies", "research", "paper", "article", "case", "based",
    "toward", "towards", "about", "over", "under", "via", "not", "new",
    "في", "من", "علي", "الي", "عن", "مع", "بين", "او", "و", "ال",
    "هذا", "هذه", "ذلك", "التي", "الذي", "دراسه", "بحث", "بحوث",
    "ورقه", "مقال", "حول", "نحو", "عبر", "لدي", "ضمن", "باستخدام", "استخدام",
})

# مُعامِلات ميدانية بلغتين. الباحث لا يُلزَم بها — غيابها يجعل النصّ كله
# كلماتٍ مفتاحية، ووجودها يجعل ما بعدها موجَّهًا إلى حقلٍ بعينه.
_FIELD_ALIASES: dict[str, str] = {
    "doi": "doi", "معرف": "doi", "معرّف": "doi",
    "author": "author", "authors": "author", "المؤلف": "author",
    "المؤلّف": "author", "مؤلف": "author", "مؤلّف": "author",
    "year": "year", "سنة": "year", "سنه": "year", "السنة": "year", "العام": "year",
    "title": "title", "عنوان": "title", "العنوان": "title",
}

_FIELD_TOKEN = re.compile(
    r"(?P<field>[A-Za-zء-ي]+)\s*:\s*(?P<value>\"[^\"]+\"|«[^»]+»|\S+)"
)
_PHRASE = re.compile(r"\"([^\"]{2,200})\"|«([^»]{2,200})»")
_YEAR_RANGE = re.compile(r"^(?P<from>\d{4})\s*[-–]\s*(?P<to>\d{4})$")
_YEAR = re.compile(r"^\d{4}$")

# سقفٌ على عدد الكلمات المفتاحية: استعلامٌ من فقرةٍ كاملة يجعل «التغطية»
# مستحيلةً على كل ورقة، فتتساوى النتائج كلها عند الصفر ويضيع الترتيب.
_MAX_KEYWORDS = 24


@dataclass(frozen=True, slots=True)
class SuggestedTerm:
    """مصطلحٌ مقترح — **معروضٌ لا مُطبَّق**.

    `accepted` تبقى `False` هنا دائمًا: القبول حدثٌ يقع في الواجهة ويعود
    إلى الخادم في `accepted_terms`. ولو حُسبت هنا لصار الاقتراح تنفيذًا.
    """

    term: str
    source_term: str
    # لماذا اقتُرح: توسيع اختصار، أو المقابل بلغةٍ أخرى.
    kind: str

    @property
    def accepted(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class ParsedQuery:
    """ما فُهم من نصّ الباحث — ومعه نصّه كما كتبه، بلا استبدال."""

    raw: str
    doi: str | None = None
    phrase: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    title_hint: str | None = None
    keywords: tuple[str, ...] = ()
    # نصّ الباحث بعد نزع بادئات المُعامِلات وعلامات الاقتباس وحدها. يُقارَن
    # به العنوان مقارنةَ تطابقٍ وعبارة — و`raw` لا يصلح لذلك لأن «author:»
    # لفظةٌ من صياغتنا لا من سؤاله، فلا تُحسب عليه في التشابه.
    text: str = ""
    # النصّ الذي يُرسَل إلى الفهارس فعلًا. يفترق عن `raw` في شيءٍ واحد:
    # نزع بادئات المُعامِلات (`author:`) وإضافة ما قبِله الباحث صراحةً.
    # ويُعاد إلى الشاشة ليُقارَن بـ`raw` — فلا يقع تبديلٌ لا يراه صاحبه.
    sent: str = ""
    accepted_terms: tuple[str, ...] = ()
    suggestions: tuple[SuggestedTerm, ...] = ()

    @property
    def is_identifier_lookup(self) -> bool:
        """استعلامٌ بمعرّفٍ شرعي: يُحلّ بالمعرّف، ولا يُبحث بالألفاظ."""
        return self.doi is not None

    @property
    def was_expanded(self) -> bool:
        return bool(self.accepted_terms)


# مُعجمٌ صغير ومغلق: توسيعُ اختصارٍ شائع، أو مقابلٌ بلغةٍ ثانية للمصطلح
# نفسه. **ولا يُدرَج فيه قريبٌ في المعنى**: «التعلّم العميق» ليس توسيعًا
# لـ«التعلّم الآلي» بل بناءٌ آخر، واقتراحُه بوصفه مرادفًا يجعل الباحث
# يظنّ أنه وسّع بحثه وقد بدّل موضوعه.
_LEXICON: dict[str, tuple[tuple[str, str], ...]] = {
    "ai": (("artificial intelligence", "acronym"),),
    "ml": (("machine learning", "acronym"),),
    "nlp": (("natural language processing", "acronym"),),
    "sme": (("small and medium enterprises", "acronym"),),
    "smes": (("small and medium enterprises", "acronym"),),
    "tam": (("technology acceptance model", "acronym"),),
    "esg": (("environmental social and governance", "acronym"),),
    "mooc": (("massive open online course", "acronym"),),
    "moocs": (("massive open online courses", "acronym"),),
    "الذكاء الاصطناعي": (("artificial intelligence", "translation"),),
    "التحول الرقمي": (("digital transformation", "translation"),),
    "التحوّل الرقمي": (("digital transformation", "translation"),),
    "التعليم العالي": (("higher education", "translation"),),
    "الاقتصاد الدائري": (("circular economy", "translation"),),
    "الصحة النفسية": (("mental health", "translation"),),
    "سلاسل الإمداد": (("supply chain", "translation"),),
}


def clean_terms(raw: object) -> tuple[str, ...]:
    """مصطلحاتٌ قبِلها الباحث، مُنقّاةً وبسقف. المدخل من الشبكة فلا يُصدَّق."""
    if not isinstance(raw, (list, tuple)):
        return ()
    kept: list[str] = []
    lowered: set[str] = set()
    for item in raw:
        term = str(item or "").strip()
        if not term or len(term) > 120 or term.lower() in lowered:
            continue
        lowered.add(term.lower())
        kept.append(term)
    return tuple(kept[:8])


def suggest_terms(text: str, keywords: tuple[str, ...]) -> tuple[SuggestedTerm, ...]:
    """اقتراحاتٌ حتميّة من مُعجمٍ مغلق — لا توليد ولا تخمين.

    الحتميّة شرط: البحث نفسه يجب أن يعطي الاقتراحات نفسها في كل تشغيلة،
    وإلا صار ما يراه الباحث اليوم غير ما يراه غدًا بلا سببٍ يفهمه.
    """
    lowered = (text or "").strip().lower()
    found: list[SuggestedTerm] = []
    seen: set[str] = set()

    def _add(term: str, source: str, kind: str) -> None:
        key = term.strip().lower()
        # ما هو مكتوبٌ في الاستعلام أصلًا لا يُقترح: اقتراح ما عند الباحث
        # ضجيجٌ يُعلّم الباحث تجاهل الاقتراحات كلها.
        if not key or key in seen or key in lowered:
            return
        seen.add(key)
        found.append(SuggestedTerm(term=term.strip(), source_term=source, kind=kind))

    for phrase, expansions in _LEXICON.items():
        if " " in phrase and phrase in lowered:
            for term, kind in expansions:
                _add(term, phrase, kind)
    for word in keywords:
        for term, kind in _LEXICON.get(word, ()):
            _add(term, word, kind)
    return tuple(found[:5])


def parse_query(text: str, *, accepted_terms: object = ()) -> ParsedQuery:
    """يقرأ نصّ الباحث ويقول ما فهمه — ولا يبدّل ما لم يُقبَل صراحةً."""
    raw = (text or "").strip()
    accepted = clean_terms(accepted_terms)

    doi = extract_doi_anywhere(raw)

    authors: list[str] = []
    year: int | None = None
    year_from: int | None = None
    year_to: int | None = None
    title_hint: str | None = None
    remainder = raw
    # نصّان يفترقان عمدًا: `remainder` ما يُرسَل إلى الفهرس (واسم المؤلّف
    # جزءٌ منه، فالفهرس يبحث به)، و`topic` موضوع البحث وحده. ولو حُسب اسم
    # المؤلّف مصطلحًا موضوعيًّا لظهر «لا يذكر: أوكافور» تحت كل ورقةٍ له.
    topic = raw

    for match in _FIELD_TOKEN.finditer(raw):
        field_name = _FIELD_ALIASES.get(match.group("field").strip().lower())
        if field_name is None:
            continue
        value = match.group("value").strip().strip('"«»')
        if not value:
            continue
        if field_name == "author":
            authors.append(value)
        elif field_name == "title":
            title_hint = value
        elif field_name == "year":
            span = _YEAR_RANGE.match(value)
            if span:
                year_from, year_to = int(span.group("from")), int(span.group("to"))
            elif _YEAR.match(value):
                year = int(value)
        # البادئة تُنزع من النصّ المُرسَل وتبقى قيمتها: `author:` كلمةٌ لا
        # يعرفها الفهرس، أما الاسم فيعرفه. وهذا نزع صياغةٍ لا تبديل نيّة.
        remainder = remainder.replace(match.group(0), value, 1)
        # المؤلّف والسنة قيدان لا موضوع: يُنزعان من نصّ الموضوع كاملَين،
        # وإلا صارت السنة «مصطلحًا غائبًا» وصار اسم المؤلّف شرطَ عنوان.
        topic = topic.replace(match.group(0), "" if field_name in ("author", "year") else value, 1)

    phrase_match = _PHRASE.search(remainder)
    phrase = None
    if phrase_match:
        phrase = (phrase_match.group(1) or phrase_match.group(2) or "").strip() or None

    keyword_source = " ".join(part for part in (topic, title_hint or "") if part)
    keywords: list[str] = []
    # استعلامٌ بمعرّفٍ شرعي لا كلمات مفتاحية له: أجزاء الـDOI («tlt»، «j»)
    # ألفاظٌ من صياغة الناشر لا من سؤال الباحث، وحسابُها صلةً يجعل ورقةً
    # أخرى في الدوريّة نفسها «مطابِقة» لمعرّفٍ لا يخصّها.
    for word in () if doi else tokens(keyword_source):
        if word in STOPWORDS or len(word) < 2 or word.isdigit():
            continue
        if word not in keywords:
            keywords.append(word)
        if len(keywords) >= _MAX_KEYWORDS:
            break

    text = " ".join(topic.replace('"', " ").replace("«", " ").replace("»", " ").split())
    outgoing = " ".join(remainder.replace('"', " ").replace("«", " ").replace("»", " ").split())
    sent = " ".join(part for part in (outgoing, *accepted) if part).strip()
    return ParsedQuery(
        raw=raw,
        doi=doi,
        phrase=phrase,
        authors=tuple(authors),
        year=year,
        year_from=year_from,
        year_to=year_to,
        title_hint=title_hint,
        keywords=tuple(keywords),
        text=text,
        sent=sent or raw,
        accepted_terms=accepted,
        suggestions=suggest_terms(raw, tuple(keywords)),
    )
