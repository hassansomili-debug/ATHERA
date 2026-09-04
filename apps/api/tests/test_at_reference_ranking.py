"""ترتيب المراجع | Explainable ranking — ثماني حالاتٍ تُثبَت خصائصها.

**تُختبر الخصائص لا الأرقام.** «الورقة التأسيسية تسبق الحديثة غير المرتبطة»
خاصيّةٌ تبقى صحيحةً بعد كل معايرةٍ للأوزان؛ أما `score == 613` فيسقط عند
أول تعديل ويُتّهم به عملٌ سليم، فيتعلّم الفريق أن يعدّل الاختبار ليمرّ —
وعندها لا يحرس شيئًا.

والحمولات ملفّاتٌ مسجَّلة بأشكال Crossref وOpenAlex كما تردّان، وبلا شبكة
عن قصد: اختبارٌ ينادي فهرسًا حيًّا يفشل يوم تنقطع الشبكة فيتّهم شفرةً
سليمة، ولا يفشل يوم تنكسر المطابقة إن صادف أن الفهرس ردّ شيئًا يشبه.

و`_NOW` مثبَّتة: ترتيبٌ يقرأ ساعة الجهاز يتغيّر جوابه في رأس السنة.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from athera_api.discovery import (
    DiscoveryProvider,
    ProviderClaim,
    ProviderUnavailable,
    deduplicate,
    discover,
    parse_query,
    rank_candidates,
)
from athera_api.discovery import crossref as crossref_provider
from athera_api.discovery import openalex as openalex_provider

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"

# سنةٌ مثبَّتة للاختبار وحدها. إشارة الحداثة تُقاس منها، فلا يتبدّل جوابٌ
# لأن التقويم تقدّم يومًا.
_NOW = 2026

# ── الحالات الثماني، ومعرّف كل واحدة في الفهرس المسجَّل ──────────────────
EXACT_TITLE = "10.1000/exact.2019"            # ١ تطابق عنوانٍ حرفي
EXACT_DOI = "10.1109/tlt.2021.3055555"        # ٢ تطابق معرّف
SAME_TERMS_OTHER_CONSTRUCT = "10.1000/energy.2021"   # ٣ المصطلحات نفسها، بناءٌ آخر
WRONG_FIELD = "10.1000/fraud.2022"            # ٤ الصياغة نفسها، ميدانٌ آخر
RIGHT_FIELD = "10.1000/medical.2018"
NEWER_LESS_RELEVANT = "10.1000/vocational.2025"      # ٥ أحدث وأقلّ صلة
NEWEST_IRRELEVANT = "10.1000/proctoring.2024"
FOUNDATIONAL = "10.1000/tam.2006"             # ٦ أقدم وتأسيسية
CONTEXT_SPECIFIC = "10.1000/saudi.2020"       # ٧ مطابقةٌ سياقية
FALSE_POSITIVE = "10.1000/stock.2021"         # ٨ شبهٌ سطحي كاذب
TRUE_POSITIVE = "10.1000/student.2020"
RETRACTED = "10.1000/retracted.2018"

QUERY_EDUCATION = "digital transformation in higher education"
QUERY_DIAGNOSIS = "machine learning for medical diagnosis"
QUERY_CONTEXT = "digital transformation higher education Saudi universities"
QUERY_ENGAGEMENT = "the impact of social media on student engagement"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _corpus() -> list[ProviderClaim]:
    """الحمولات المسجَّلة من الفهرسين، بلا شبكة."""
    claims = [
        crossref_provider.to_claim(item)
        for item in _load("ranking_crossref.json")["message"]["items"]
    ]
    claims += [
        openalex_provider.to_claim(item)
        for item in _load("ranking_openalex.json")["results"]
    ]
    return claims


def _order(query: str) -> list[str]:
    """معرّفات النتائج بترتيبها لهذا الاستعلام."""
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(query), now_year=_NOW)
    return [item.candidate.doi or item.candidate.title for item in ranked]


def _reasons(query: str, doi: str) -> set[str]:
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(query), now_year=_NOW)
    for item in ranked:
        if item.candidate.doi == doi:
            return {reason.code for reason in item.ranking.reasons}
    raise AssertionError(f"{doi} did not appear in the ranking at all")


def _rank_of(query: str, doi: str) -> int:
    return _order(query).index(doi)


class _StubProvider(DiscoveryProvider):
    """فهرسٌ يعيد حمولةً مسجَّلة. `honours_limit` يفرّق حالتين حقيقيتين.

    الفهرس الحقيقي يقصّ عنده بـ`rows`؛ لكن العدد المطلوب يُملأ من الفهرسين
    معًا فيجاوز السقف بعد التوحيد، وهناك يقع قصُّ الخادم — وهو الموضع الذي
    يجب أن يقع فيه **بعد** الترتيب لا قبله.
    """

    def __init__(self, name: str, claims: list[ProviderClaim],
                 *, honours_limit: bool = True) -> None:
        self.name = name
        self._claims = claims
        self._honours_limit = honours_limit

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        return self._claims[:limit] if self._honours_limit else list(self._claims)

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        return next((claim for claim in self._claims if claim.doi == doi), None)


class _DownProvider(DiscoveryProvider):
    def __init__(self, name: str) -> None:
        self.name = name

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        raise ProviderUnavailable(self.name, "ConnectTimeout")

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        raise ProviderUnavailable(self.name, "ConnectTimeout")


# ─────────────────── الحالات الثماني ───────────────────

def test_case_1_an_exact_title_leads_and_says_so():
    """التطابق الحرفي يتصدّر، **ويقول لماذا** — لا يُترك للباحث أن يخمّن."""
    assert _order(QUERY_EDUCATION)[0] == EXACT_TITLE
    assert "exact_title" in _reasons(QUERY_EDUCATION, EXACT_TITLE)


def test_case_2_an_exact_doi_outranks_every_word_match():
    """المعرّف حكمٌ لا إشارة: يتصدّر ولو لم يشترك في لفظةٍ من الاستعلام.

    ولذلك المرتبة قبل الدرجة في الترتيب — درجةُ ورقةٍ مشهورة قد تفوق درجة
    الورقة المطلوبة بمعرّفها، ولا يجوز أن تسبقها.
    """
    ranked = rank_candidates(
        deduplicate(_corpus()), parse_query(EXACT_DOI), now_year=_NOW,
    )
    assert ranked[0].candidate.doi == EXACT_DOI
    assert "exact_doi" in {reason.code for reason in ranked[0].ranking.reasons}
    # وفوقه في الدرجة أوراقٌ أخرى — فالصدارة جاءت من المرتبة لا من الدرجة.
    assert any(item.ranking.score > ranked[0].ranking.score for item in ranked[1:])


def test_case_3_same_terms_in_another_construct_falls_behind_and_is_flagged():
    """كل مصطلحات البحث في عنوانه، وموضوعه آخر: يُدرَج ويُقيَّد لا يُحذف.

    الحذف ادّعاءُ فهمٍ للمعنى لا تملكه مطابقةٌ لفظية؛ والصمت يجعل الباحث
    يفتح ورقةً عن عدّادات الطاقة وهو يبحث في التعليم.
    """
    order = _order(QUERY_EDUCATION)
    assert order.index(SAME_TERMS_OTHER_CONSTRUCT) > order.index(EXACT_TITLE)
    assert order.index(SAME_TERMS_OTHER_CONSTRUCT) > order.index(FOUNDATIONAL)
    assert "broader_topic" in _reasons(QUERY_EDUCATION, SAME_TERMS_OTHER_CONSTRUCT)


def test_case_4_the_same_wording_in_the_wrong_field_loses_to_the_right_one():
    """«تعلّم آلي لتشخيص الاحتيال» و«لتشخيص طبّي»: لفظتان مشتركتان وميدانان.

    والخاسرة هنا أحدث وأكثر استشهادًا — ومع ذلك تتأخّر، لأن اللفظة الغائبة
    («طبّي») هي كل الفرق، والدرجة تقولها بعقوبةٍ لا بتجاهل.
    """
    order = _order(QUERY_DIAGNOSIS)
    assert order.index(RIGHT_FIELD) < order.index(WRONG_FIELD)
    assert "medical" in _reasons_terms(QUERY_DIAGNOSIS, WRONG_FIELD, "missing_terms")


def test_case_5_newer_but_less_relevant_stays_below_older_and_relevant():
    """الأحدث ليس الأفضل. ورقة ٢٠٢٥ تشترك في لفظتين تتأخّر عن ٢٠٠٦ و٢٠١٩."""
    order = _order(QUERY_EDUCATION)
    assert order.index(NEWER_LESS_RELEVANT) > order.index(FOUNDATIONAL)
    assert order.index(NEWER_LESS_RELEVANT) > order.index(EXACT_TITLE)
    # وأحدثُ ما في القائمة (٢٠٢٤) بلا صلةٍ في عنوانه، فيقع خلف الأقلّ حداثة.
    assert order.index(NEWEST_IRRELEVANT) > order.index(NEWER_LESS_RELEVANT)
    assert order.index(NEWEST_IRRELEVANT) > order.index(CONTEXT_SPECIFIC)


def test_case_6_an_older_foundational_paper_outranks_a_newer_unrelated_one():
    """**الحارس الأول ضدّ الانحدار إلى الترتيب بالسنة.**

    لو صار الترتيب زمنيًّا لتصدّرت ٢٠٢٤ و٢٠٢٥؛ وهما آخر ما في القائمة.
    والاستشهاد يُذكر منسوبًا إلى فهرسه: ٢٤٠٠ في OpenAlex، لا رقمًا بلا قائل.
    """
    order = _order(QUERY_EDUCATION)
    assert order.index(FOUNDATIONAL) < order.index(NEWEST_IRRELEVANT)
    assert order.index(FOUNDATIONAL) < order.index(NEWER_LESS_RELEVANT)

    ranked = rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    cited = next(
        reason for item in ranked if item.candidate.doi == FOUNDATIONAL
        for reason in item.ranking.reasons if reason.code == "highly_cited"
    )
    assert (cited.provider, cited.count) == ("openalex", 2400)


def test_case_7_a_context_specific_match_beats_a_generic_one_missing_the_context():
    """الباحث سأل عن الجامعات السعودية، فالورقة التي تذكرها تسبق التي لا تذكرها.

    وسياقها في الملخّص لا في العنوان — ولو قيست الصلة بالعنوان وحده لضاعت.
    """
    order = _order(QUERY_CONTEXT)
    assert order.index(CONTEXT_SPECIFIC) < order.index(EXACT_TITLE)
    assert "context_match" in _reasons(QUERY_CONTEXT, CONTEXT_SPECIFIC)
    # والعامّة تُقال ناقصةً بالاسم: «لا تذكر: السعودية».
    assert "saudi" in _reasons_terms(QUERY_CONTEXT, EXACT_TITLE, "missing_terms")


def test_case_8_a_false_positive_title_is_pushed_down_and_named_a_false_positive():
    """«أثر وسائل التواصل في تفاعل السوق» ليس «…في تفاعل الطلبة».

    التتابع المشترك طويل جدًّا، فتُخطئه العين ويُخطئه تشابه المجموعات؛
    واللفظة الغائبة وحدها هي الفرق. فيُقال شبهًا سطحيًّا لا تطابقًا قويًّا.
    """
    order = _order(QUERY_ENGAGEMENT)
    assert order.index(TRUE_POSITIVE) < order.index(FALSE_POSITIVE)
    reasons = _reasons(QUERY_ENGAGEMENT, FALSE_POSITIVE)
    assert "surface_similarity" in reasons
    # ولا يجتمع مع سبب المطابقة القويّة: السببان يتناقضان في بطاقةٍ واحدة.
    assert "strong_phrase" not in reasons
    assert "direct_variables" not in reasons
    assert "strong_phrase" in _reasons(QUERY_ENGAGEMENT, TRUE_POSITIVE)


def _reasons_terms(query: str, doi: str, code: str) -> list[str]:
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(query), now_year=_NOW)
    for item in ranked:
        if item.candidate.doi == doi:
            for reason in item.ranking.reasons:
                if reason.code == code:
                    return list(reason.terms)
    return []


# ─────────────────── خصائصُ عامّة في الترتيب ───────────────────

def test_the_ranking_is_never_a_sort_by_year():
    """خاصيّةٌ صريحة: ترتيب النتائج ليس ترتيب سنواتها تنازليًّا."""
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    years = [item.candidate.year for item in ranked if item.candidate.year]
    assert years != sorted(years, reverse=True)


def test_the_ranking_is_never_a_sort_by_citations_either():
    """ولا ترتيبَ شهرة: أكثر الأوراق استشهادًا ليست الأولى."""
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    counts = [max(item.candidate.citation_counts.values(), default=0) for item in ranked]
    assert counts != sorted(counts, reverse=True)


def test_citation_counts_stay_attributed_and_are_never_merged_by_ranking():
    """الترتيب يقرأ العدّادات ولا يمسّها: تبقى قاموسًا منسوبًا لا رقمًا واحدًا."""
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    foundational = next(item for item in ranked if item.candidate.doi == FOUNDATIONAL)
    assert foundational.candidate.citation_counts == {"crossref": 2100, "openalex": 2400}
    # لا مجموع (٤٥٠٠) ولا متوسّط (٢٢٥٠): رقمان لا يقولهما فهرس.
    assert not hasattr(foundational.candidate, "citation_count")


def test_a_retracted_paper_never_leads_and_is_flagged_even_when_relevant():
    """الورقة المسحوبة مرتبطةٌ ومستشهَدٌ بها كثيرًا — ولا تتصدّر.

    ولا تُحذف أيضًا: الباحث قد يكون مستشهدًا بها فعلًا، وإخفاؤها يمنعه من
    اكتشاف ذلك. فتُعرض متأخّرةً ومعها تحذيرُها.
    """
    order = _order(QUERY_EDUCATION)
    assert order[0] != RETRACTED
    assert order.index(RETRACTED) > order.index(EXACT_TITLE)
    assert order.index(RETRACTED) > order.index(FOUNDATIONAL)
    assert "retracted" in _reasons(QUERY_EDUCATION, RETRACTED)


def test_retraction_is_read_from_structured_data_not_from_the_title_string():
    """السحب يُقرأ من `update-to` و`is_retracted`، لا من كلمةٍ في العنوان."""
    pretender = ProviderClaim(
        provider="crossref", provider_id="10.1000/pretend.2020",
        doi="10.1000/pretend.2020",
        title="Retraction and reproducibility in digital transformation research",
        year=2020,
    )
    candidate = deduplicate([pretender])[0]
    # عنوانٌ يحمل لفظة «Retraction» عن موضوع السحب — لا ورقةٌ مسحوبة.
    assert candidate.retraction_status == "unknown"
    ranked = rank_candidates([candidate], parse_query(QUERY_EDUCATION), now_year=_NOW)
    assert "retracted" not in {reason.code for reason in ranked[0].ranking.reasons}


def test_the_same_search_twice_gives_the_same_order():
    """الحتميّة شرطُ ثقة: شاشتان مختلفتان للبحث نفسه تُقرأان تغيّرًا لم يقع."""
    assert _order(QUERY_EDUCATION) == _order(QUERY_EDUCATION)
    reversed_corpus = list(reversed(_corpus()))
    first = [
        item.candidate.doi for item in
        rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    ]
    second = [
        item.candidate.doi for item in
        rank_candidates(deduplicate(reversed_corpus), parse_query(QUERY_EDUCATION), now_year=_NOW)
    ]
    # ترتيب وصول الفهارس لا يغيّر ترتيب العرض.
    assert first == second


def test_no_reason_ever_carries_a_relevance_percentage():
    """**لا نسبة في العقد أصلًا.** ما لا يوجد لا تعرضه شاشة."""
    from athera_api.discovery.ranking import RankReason

    fields = set(RankReason.__dataclass_fields__)
    assert fields.isdisjoint({"percent", "percentage", "relevance", "score", "confidence"})


def test_every_result_carries_at_least_one_reason_or_a_named_gap():
    """لا نتيجة بلا تفسير: إمّا سببُ ترجيح، وإمّا مصطلحٌ غائب يُسمّى."""
    ranked = rank_candidates(deduplicate(_corpus()), parse_query(QUERY_EDUCATION), now_year=_NOW)
    for item in ranked:
        assert item.ranking.reasons, item.candidate.title


def test_ranking_happens_before_the_limit_cuts():
    """القصّ يقع على المرتَّب: أفضلُ ما وُجد، لا أفضلُ ما وصل أوّلًا."""
    provider = _StubProvider("crossref", _corpus(), honours_limit=False)
    result = asyncio.run(discover([provider], QUERY_EDUCATION, limit=2, now_year=_NOW))
    # الورقة التأسيسية آخرُ ما ورد من الفهرس، ومع ذلك تبقى بعد القصّ.
    assert [candidate.doi for candidate in result.candidates] == [
        EXACT_TITLE, FOUNDATIONAL,
    ]


def test_the_service_returns_ranked_results_with_their_reasons():
    provider = _StubProvider("crossref", _corpus())
    result = asyncio.run(discover([provider], QUERY_EDUCATION, now_year=_NOW))
    assert result.ranked[0].candidate.doi == EXACT_TITLE
    assert result.ranked[0].ranking.reasons
    assert result.query is not None
    assert result.query.raw == QUERY_EDUCATION


def test_a_failed_provider_still_leaves_the_survivor_ranked_and_explained():
    """فهرسٌ سقط لا يُلغي ترتيب الباقي، ولا يُقرأ سقوطه «لا نتائج»."""
    result = asyncio.run(discover(
        [_StubProvider("crossref", _corpus()), _DownProvider("openalex")],
        QUERY_EDUCATION, now_year=_NOW,
    ))
    assert result.any_provider_failed is True
    assert result.all_providers_failed is False
    assert result.ranked[0].candidate.doi == EXACT_TITLE
    assert result.ranked[0].ranking.reasons


# ─────────────────── العقد على السلك ───────────────────

def test_an_unauthenticated_search_is_401_never_a_generic_500():
    """التعذّر يُصنَّف: ٤٠١ يقول «سجّل الدخول»، و٥٠٠ لا يقول شيئًا."""
    pytest.importorskip("fastapi")
    httpx = pytest.importorskip("httpx")

    from athera_api.main import app

    async def _call() -> int:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post(
                "/api/v1/references/search", json={"query": "digital transformation"},
            )
            return response.status_code

    assert asyncio.run(_call()) == 401


def test_the_request_contract_bounds_what_a_client_may_accept():
    """المدخل من الشبكة محدود في العقد نفسه، فيُردّ ٤٢٢ لا يُبتلع."""
    pytest.importorskip("pydantic")
    from pydantic import ValidationError

    from athera_api.schemas.discovery import ReferenceSearchRequest

    with pytest.raises(ValidationError):
        ReferenceSearchRequest(query="digital", accepted_terms=[str(n) for n in range(20)])
    with pytest.raises(ValidationError):
        ReferenceSearchRequest(query="x")
    # والحال الطبيعية: قائمةٌ فارغة — الاقتراح معروضٌ لا مُطبَّق.
    assert ReferenceSearchRequest(query="digital transformation").accepted_terms == []


def test_the_wire_contract_carries_reasons_and_never_a_score():
    """الدرجة لا تعبر السلك: رقمٌ داخلي يصل الواجهة يُعرض يومًا نسبةً."""
    pytest.importorskip("pydantic")
    from athera_api.schemas.discovery import RankReasonView, ReferenceCandidateView

    fields = set(ReferenceCandidateView.model_fields)
    assert {"reasons", "matched_terms", "missing_terms"} <= fields
    assert fields.isdisjoint({"score", "relevance", "relevance_percent", "rank"})
    assert set(RankReasonView.model_fields).isdisjoint(
        {"score", "percent", "percentage", "confidence"}
    )
