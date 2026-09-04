"""ترتيب المرشَّحين | Explainable deterministic ranking.

الباحث أمام مئة نتيجة لا يقرأ مئة؛ يقرأ العشر الأولى. فترتيبُها **قرارٌ
علميّ** لا زينة عرض، وهذا الملفّ يخضع لثلاثة قيود لا يُتنازل عنها:

**١ — لا نسبة ملفَّقة.** «٩٧٪ صلة» رقمٌ لا مرجع له ولا وحدة قياس، ويقرؤه
الباحث حكمًا كميًّا على ورقةٍ لم تُقرأ. فالمخرَج هنا **أسبابٌ بلغته**:
«يطابق عبارة البحث بدرجة قوية»، «لا يذكر: الجامعات». والدرجة الرقمية
داخلية للترتيب وحده، ولا تعبر إلى العقد ولا إلى الشاشة.

**٢ — لا انحدار إلى الترتيب بالسنة.** أثرُ الحداثة محدودٌ بسقفٍ صغير عمدًا
(٣٠ نقطة) بينما الصلة اللفظية تصل إلى ٨٩٠. فورقةٌ تأسيسية من ٢٠٠٥ يكثر
الاستشهاد بها تسبق ورقةً من هذا العام لا تمتّ للسؤال بصلة — وهو ما يقع في
الحقيقة، وما يخالفه الترتيب الزمني في كل مرّة.

**٣ — الاستشهاد إشارة منسوبة لا حقيقة مدموجة.** يؤخذ **أعلى ما قاله فهرس**
باسم قائله، ولا يُجمع عدّادان ولا يُوسَّطان: المجموع يعدّ الاستشهاد الواحد
مرّتين، والمتوسّط رقمٌ لا يقوله أحد ولا يُتحقَّق منه في أي فهرس. وأثره
لوغاريتمي بسقف، فلا يصير البحث ترتيبًا بالشهرة.

والحساب كله بأعداد صحيحة: المقارنة بين درجتين لا تنكسر بفروق الفاصلة
العائمة، والاختبار يُثبت خصائص الترتيب لا أرقامه.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from .contracts import ReferenceCandidate
from .normalize import first_author_key, normalized_title, tokens
from .query import STOPWORDS, ParsedQuery

# ── الأوزان (نقاط صحيحة) ──────────────────────────────────────────────
# النسبة بين السقوف هي القرار الحقيقي، لا قيمة كل رقم على حدة: الصلة
# اللفظية تتجاوز ٨٠٠ نقطة، والحداثة ٣٠، والاستشهاد ٩٠. فلا تحكم إشارةٌ
# مساعدة في ترتيبٍ ما دامت الصلة تقول غير قولها.
W_PHRASE = 170
W_SIMILARITY = 200
W_TITLE_COVERAGE = 120
W_ABSTRACT_COVERAGE = 60
W_AUTHOR = 90
W_AUTHOR_CAP = 120
W_MISSING_PENALTY = 200
# «لا شيء ممّا سألتَ عنه غائب» خاصيّةٌ تستحقّ وزنًا مستقلًّا عن التغطية
# الجزئية: ورقةٌ تذكر سياقك في ملخّصها وتذكر متغيّراتك تسبق ورقةً تطابق
# نصف سؤالك في عنوانها وتُسقط نصفه — وهذا ما يفعله الباحث حين يقرأ بنفسه.
W_FULL_COVERAGE = 90
W_CITATION_CAP = 90
W_AGREEMENT = 10
W_EXACT_TITLE = 400

# السحب ليس «إشارة سلبية» تُوازن بغيرها: عقوبتُه أكبر من كل الإشارات
# المساعدة مجتمعة، فلا ترفعها شهرةٌ ولا حداثة إلى صدارة تُقرأ دليلًا.
W_RETRACTED = -250
W_CONCERN = -80
W_CORRECTION = -20

TIER_DOI = 2
TIER_EXACT_TITLE = 1
TIER_RELEVANCE = 0

# عتبات إصدار الأسباب. مُعلَنة هنا لأن السبب المعروض على الباحث عقدٌ معه:
# «مرتبط مباشرة بالمتغيرات الرئيسية» تعني عنوانًا يذكر ≥ ٧٥٪ من مصطلحاته
# **ولا يُسقط منها شيئًا** — لا أكثر ولا أقل، ويستطيع أن يتحقق بعينه.
_DIRECT_COVERAGE = 0.75
_RELATED_COVERAGE = 0.5
_WEAK_COVERAGE = 0.6
_HIGHLY_CITED = 100
_RECENT_YEARS = 5
# أقصر تتابعٍ يُعدّ شبهًا سطحيًّا. لفظةٌ واحدة مشتركة صدفةٌ لا شبه.
_MIN_RUN = 2

REASON_MATCH = "match"
REASON_CAUTION = "caution"


@dataclass(frozen=True, slots=True)
class RankReason:
    """سببٌ يُقرأ بلغة الباحث. `code` مفتاح ترجمة، والحقول ما يُعبّأ فيه.

    ولا حقل للنسبة هنا **بنيةً**: ما لا يوجد في العقد لا تعرضه شاشة.
    """

    code: str
    kind: str = REASON_MATCH
    terms: tuple[str, ...] = ()
    # الاستشهاد لا يُذكر بلا قائله: «١٣٤ في OpenAlex» جملةٌ يمكن التحقق منها،
    # و«١٣٤ استشهادًا» دعوى منصّة على فهرسٍ لم يقلها.
    provider: str | None = None
    count: int | None = None
    year: int | None = None


@dataclass(frozen=True, slots=True)
class Ranking:
    """نتيجة الترتيب لمرشَّحٍ واحد: مرتبته، وأسبابه، وما طوبق وما غاب."""

    score: int
    tier: int
    reasons: tuple[RankReason, ...]
    matched_terms: tuple[str, ...]
    missing_terms: tuple[str, ...]
    # الإشارات الخام تُحفظ للاختبار والتشخيص، ولا تُصدَّر في عقد الشبكة.
    signals: dict[str, int]


@dataclass(frozen=True, slots=True)
class RankedReference:
    """مرشَّحٌ ومعه ترتيبه. البطاقة تُعرض من الأول، والتفسير من الثاني."""

    candidate: ReferenceCandidate
    ranking: Ranking


def _content_tokens(text: str | None) -> tuple[list[str], set[str]]:
    """ألفاظ نصٍّ بترتيبها ومجموعتها، بلا ألفاظ الربط."""
    ordered = [word for word in tokens(text or "") if word not in STOPWORDS]
    return ordered, set(ordered)


def _longest_run(haystack: list[str], needle: list[str]) -> int:
    """أطول تتابعٍ من ألفاظ العبارة يرد متتاليًا في العنوان.

    **هذا المقياس هو كاشف الإيجابية الكاذبة.** «أثر وسائل التواصل في تفاعل
    الطلبة» و«أثر وسائل التواصل في تفاعل السوق» يشتركان في تتابعٍ طويل جدًّا،
    فيبدوان للعين ولمقاييس التشابه ورقةً واحدة — والفارق كله لفظةٌ واحدة
    غائبة. فحين يطول التتابع **وتغيب لفظةٌ من سؤال الباحث** يُقال له ذلك
    تحذيرًا صريحًا، لا يُسكت عنه ولا يُترجم «تطابقًا قويًّا».
    """
    if not needle or not haystack:
        return 0
    best = 0
    previous = [0] * (len(needle) + 1)
    for word in haystack:
        current = [0] * (len(needle) + 1)
        for index, target in enumerate(needle, start=1):
            if word == target:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


def _dice(left: set[str], right: set[str]) -> float:
    """تشابه المجموعتين. **يعاقب العنوانَ الزائد كما يعاقب الناقص**.

    وهذا مقصود: عنوانٌ يبتلع كلمات البحث داخل موضوعٍ أوسع بكثير ليس تطابقًا،
    والمقياس الذي يقيس التغطية وحدها يمنحه العلامة الكاملة ظلمًا.
    """
    if not left or not right:
        return 0.0
    return (2 * len(left & right)) / (len(left) + len(right))


def _citation_points(candidate: ReferenceCandidate) -> tuple[int, str | None, int | None]:
    """أثر الاستشهاد: **أعلى ما قاله فهرسٌ واحد، منسوبًا إليه**.

    ولا يُجمع عدّادان (فيُعدّ الاستشهاد المفهرس مرّتين) ولا يُوسَّطان (فيُخترع
    رقمٌ لا يقوله أحد). والأثر لوغاريتمي بسقف: الفرق بين ١٠ و١٠٠ يُقال،
    والفرق بين ٥٠٠٠ و١٠٠٠٠ لا يقلب ترتيبًا بُني على الصلة.
    """
    counts = candidate.citation_counts
    if not counts:
        return 0, None, None
    provider, count = max(counts.items(), key=lambda item: (item[1], item[0]))
    if count <= 0:
        return 0, provider, count
    points = min(W_CITATION_CAP, int(round(26 * math.log10(1 + count))))
    return points, provider, count


def _recency_points(year: int | None, now_year: int) -> int:
    """الحداثة إشارةٌ صغيرة بسقفٍ صغير — لأنها ليست صلة.

    ورقةٌ من هذا العام عن موضوعٍ آخر لا تنفع الباحث، وسقفُ ٣٠ نقطة يمنعها
    من أن تسبق ورقةً تجيب سؤاله. رفعُ هذا السقف يحوّل الشاشة إلى ترتيبٍ
    زمني بأسماء أخرى.
    """
    if year is None:
        return 0
    age = now_year - year
    if age < 0:
        return 0
    if age <= _RECENT_YEARS:
        return 30
    if age <= 10:
        return 18
    if age <= 20:
        return 8
    return 0


def _type_points(work_type: str | None) -> int:
    """نوع العمل إشارةٌ أصغر من الحداثة، ولا تُقصي نوعًا.

    المسوّدة المنشورة قد تكون أحدث ما في الميدان، فلا تُحجب — لكن المقال
    المحكَّم يُقدَّم عند تساوي الصلة، وهذا ما يفعله الباحث بنفسه.
    """
    if work_type in ("journal-article", "review", "book"):
        return 12
    if work_type in ("conference-paper", "book-chapter", "thesis", "report"):
        return 6
    return 0


def _retraction_points(status: str) -> int:
    if status == "retracted":
        return W_RETRACTED
    if status == "expression_of_concern":
        return W_CONCERN
    if status == "correction":
        return W_CORRECTION
    return 0


def _author_points(candidate: ReferenceCandidate, parsed: ParsedQuery) -> tuple[int, tuple[str, ...]]:
    """مطابقة المؤلّف على اسم العائلة وحده — كما في التوحيد، وللسبب نفسه.

    الفهارس تكتب الاسم بترتيبين ودرجتَي اختصار، فمقارنة الاسم كاملًا تُسقط
    مطابقةً صحيحة. ولفظةٌ واحدة لا تكفي هويّةً، لذلك هي إشارةٌ لا مرتبة.
    """
    if not parsed.authors:
        return 0, ()
    wanted = {
        key for key in (first_author_key([name]) for name in parsed.authors) if key
    }
    have = {
        key for key in (first_author_key([name]) for name in candidate.authors) if key
    }
    hits = tuple(sorted(wanted & have))
    return min(W_AUTHOR_CAP, W_AUTHOR * len(hits)), hits


def _build_reasons(
    *,
    candidate: ReferenceCandidate,
    parsed: ParsedQuery,
    exact_doi: bool,
    exact_title: bool,
    phrase_hit: bool,
    surface_only: bool,
    broader_topic: bool,
    title_coverage: float,
    total_coverage: float,
    abstract_only: tuple[str, ...],
    missing: tuple[str, ...],
    author_hits: tuple[str, ...],
    citation_provider: str | None,
    citation_count: int | None,
    now_year: int,
) -> tuple[RankReason, ...]:
    """يترجم الإشارات إلى جملٍ يقرؤها الباحث — كلٌّ منها قابلة للتحقق.

    والسبب لا يُصاغ من الدرجة بل من الإشارة التي أنتجته: «يطابق عبارة
    البحث» تعني أن ألفاظ العبارة وردت متتاليةً في العنوان، لا أن الدرجة
    عالية. فلو انفصل السبب عن سببه لصار تفسيرًا مُختلقًا لترتيبٍ مجهول.
    """
    reasons: list[RankReason] = []

    if exact_doi:
        reasons.append(RankReason(code="exact_doi"))
    if exact_title:
        reasons.append(RankReason(code="exact_title"))

    # المطابقة القويّة والشبه السطحي **لا يجتمعان**: الأولى تعني أن عبارة
    # الباحث كلها وردت متتاليةً، والثاني أنها وردت ناقصةً لفظةً تغيّر
    # الموضوع. ولو قيلا معًا لناقض السببان بعضهما في بطاقةٍ واحدة.
    if phrase_hit and not exact_title:
        reasons.append(RankReason(code="strong_phrase"))
    elif surface_only:
        reasons.append(RankReason(code="surface_similarity", kind=REASON_CAUTION,
                                  terms=missing[:2]))

    if parsed.keywords:
        # «مباشرة» تشترط ألّا يغيب شيء: عنوانٌ يذكر ثلاثة من أربعة ويُسقط
        # الرابع ليس مرتبطًا مباشرةً، بل هو بابُ الإيجابية الكاذبة نفسه.
        if title_coverage >= _DIRECT_COVERAGE and not missing and len(parsed.keywords) >= 2:
            reasons.append(RankReason(code="direct_variables"))
        elif not missing and abstract_only:
            # كل ما سأل عنه حاضرٌ فيه، وبعضه في الملخّص لا العنوان: هذه هي
            # المطابقة السياقية التي يفوّتها البحث بالعنوان وحده.
            reasons.append(RankReason(code="context_match", terms=abstract_only[:3]))
        elif abstract_only:
            reasons.append(RankReason(code="abstract_terms", terms=abstract_only[:3]))

        if broader_topic:
            # يذكر مصطلحاتك كلها، لكن عنوانه يحمل من المصطلحات الأخرى أكثر
            # ممّا سألت عنه — فموضوعه أوسع، وربما آخر. يُقال ولا يُحجب.
            reasons.append(RankReason(code="broader_topic", kind=REASON_CAUTION))

        if 0.0 < total_coverage < _WEAK_COVERAGE and not phrase_hit and not surface_only:
            reasons.append(RankReason(code="shared_terms_only", kind=REASON_CAUTION))

    if author_hits:
        reasons.append(RankReason(code="author_match", terms=author_hits))

    year = candidate.year
    if (
        year is not None and (now_year - year) <= _RECENT_YEARS
        and total_coverage >= _RELATED_COVERAGE and not surface_only
    ):
        # «حديثة ومرتبطة» لا تُقال وحدها أبدًا: مشروطةٌ بصلةٍ قائمة وبانتفاء
        # الشبه السطحي، وإلا صار السبب إعلانًا عن تاريخ نشرٍ لا عن فائدة —
        # ووصفُ ورقةٍ بالحداثة بعد تحذيرٍ من شبهها السطحي تناقضٌ يُربك القارئ.
        reasons.append(RankReason(code="recent_related", year=year))

    if citation_count is not None and citation_count >= _HIGHLY_CITED and citation_provider:
        reasons.append(RankReason(
            code="highly_cited", provider=citation_provider, count=citation_count,
        ))

    if missing:
        reasons.append(RankReason(code="missing_terms", kind=REASON_CAUTION, terms=missing[:3]))

    status = candidate.retraction_status
    if status == "retracted":
        reasons.append(RankReason(code="retracted", kind=REASON_CAUTION))
    elif status == "expression_of_concern":
        reasons.append(RankReason(code="concern", kind=REASON_CAUTION))

    return tuple(reasons)


def rank_one(
    candidate: ReferenceCandidate, parsed: ParsedQuery, *, now_year: int,
) -> Ranking:
    """درجةٌ ومرتبةٌ وأسباب لمرشَّحٍ واحد — حتميّة على المدخل نفسه."""
    keywords = parsed.keywords
    title_ordered, title_set = _content_tokens(candidate.title)
    _abstract_ordered, abstract_set = _content_tokens(candidate.abstract)

    matched_title = tuple(word for word in keywords if word in title_set)
    abstract_only = tuple(
        word for word in keywords if word not in title_set and word in abstract_set
    )
    missing = tuple(
        word for word in keywords if word not in title_set and word not in abstract_set
    )
    total = len(keywords)
    title_coverage = len(matched_title) / total if total else 0.0
    total_coverage = (len(matched_title) + len(abstract_only)) / total if total else 0.0

    exact_doi = bool(parsed.doi and candidate.doi and parsed.doi == candidate.doi)
    # المقارنة على العنوان المسوَّى: فرقُ الحرف الكبير والشرطة ليس فرق ورقة.
    query_title = parsed.phrase or parsed.title_hint or parsed.text or parsed.raw
    exact_title = bool(
        candidate.title and normalized_title(query_title) == normalized_title(candidate.title)
    )

    phrase_ordered, _ = _content_tokens(query_title)
    run = _longest_run(title_ordered, phrase_ordered)
    phrase_hit = len(phrase_ordered) >= _MIN_RUN and run == len(phrase_ordered)
    # شبهٌ سطحي: تتابعٌ طويل يبلغ نصف عبارة الباحث فأكثر، ومع ذلك تغيب
    # لفظةٌ من سؤاله لا في العنوان ولا في الملخّص. هذا هو الشكل الذي تأخذه
    # الإيجابية الكاذبة في الواقع، ولا يكشفه تشابهُ المجموعات وحده.
    surface_only = bool(
        not phrase_hit and missing
        and run >= _MIN_RUN and run * 2 >= len(phrase_ordered)
    )
    # عنوانٌ يحمل من المصطلحات الأخرى أكثر ممّا سأل عنه الباحث كلَّه:
    # مصطلحاته حاضرة، لكنها ليست موضوع الورقة بل جزءٌ من موضوعٍ أوسع.
    broader_topic = bool(total and not missing and len(title_set - set(keywords)) > total)

    similarity = _dice(set(keywords), title_set)
    citation_points, citation_provider, citation_count = _citation_points(candidate)
    author_points, author_hits = _author_points(candidate, parsed)

    signals = {
        "phrase": W_PHRASE if phrase_hit else 0,
        "similarity": int(round(similarity * W_SIMILARITY)),
        "title_coverage": int(round(title_coverage * W_TITLE_COVERAGE)),
        "abstract_coverage": int(round(
            (len(abstract_only) / total if total else 0.0) * W_ABSTRACT_COVERAGE
        )),
        "author": author_points,
        "full_coverage": W_FULL_COVERAGE if (total >= 3 and not missing) else 0,
        "missing": -int(round(
            (len(missing) / total if total else 0.0) * W_MISSING_PENALTY
        )),
        "citations": citation_points,
        "recency": _recency_points(candidate.year, now_year),
        "work_type": _type_points(candidate.work_type),
        "agreement": W_AGREEMENT if len(candidate.providers) > 1 else 0,
        "retraction": _retraction_points(candidate.retraction_status),
        "exact_title": W_EXACT_TITLE if exact_title else 0,
    }

    tier = TIER_DOI if exact_doi else (TIER_EXACT_TITLE if exact_title else TIER_RELEVANCE)
    return Ranking(
        score=sum(signals.values()),
        tier=tier,
        reasons=_build_reasons(
            candidate=candidate, parsed=parsed, exact_doi=exact_doi,
            exact_title=exact_title, phrase_hit=phrase_hit,
            surface_only=surface_only, broader_topic=broader_topic,
            title_coverage=title_coverage, total_coverage=total_coverage,
            abstract_only=abstract_only, missing=missing, author_hits=author_hits,
            citation_provider=citation_provider, citation_count=citation_count,
            now_year=now_year,
        ),
        matched_terms=matched_title + abstract_only,
        missing_terms=missing,
        signals=signals,
    )


def rank_candidates(
    candidates: tuple[ReferenceCandidate, ...] | list[ReferenceCandidate],
    parsed: ParsedQuery,
    *,
    now_year: int | None = None,
) -> tuple[RankedReference, ...]:
    """يرتّب المرشَّحين ترتيبًا حتميًّا: المرتبة، ثم الدرجة، ثم فاصلٌ ثابت.

    الفاصل الأخير (العنوان المسوَّى ثم الـDOI) ليس تحسينًا للترتيب بل
    ضمانةٌ له: بلا فاصلٍ ثابت يتبدّل ترتيب المتساويين بترتيب وصول الفهارس،
    فيرى الباحث شاشتين مختلفتين للبحث نفسه ويظنّ أن شيئًا تغيّر.
    """
    year_now = now_year if now_year is not None else datetime.now(UTC).year
    ranked = [
        RankedReference(candidate=candidate, ranking=rank_one(candidate, parsed, now_year=year_now))
        for candidate in candidates
    ]
    ranked.sort(key=lambda item: (
        -item.ranking.tier,
        -item.ranking.score,
        normalized_title(item.candidate.title),
        item.candidate.doi or "",
    ))
    return tuple(ranked)
