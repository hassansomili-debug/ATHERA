"""اكتشاف المراجع | Reference discovery — تسويةٌ وتوحيدٌ ونسبة.

**بلا شبكة، عن قصد.** الحمولات ملفّات مسجَّلة بأشكال Crossref وOpenAlex
كما تردّان. اختبارٌ ينادي فهرسًا حيًّا يفشل يوم يتغيّر الفهرس أو تنقطع
الشبكة، فيتّهم شفرةً سليمة — ولا يفشل يوم تنكسر التسوية إن صادف أن الفهرس
ردّ شيئًا يشبه المطلوب.
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
)
from athera_api.discovery import crossref as crossref_provider
from athera_api.discovery import openalex as openalex_provider

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _crossref_claims() -> list[ProviderClaim]:
    items = _load("crossref_search.json")["message"]["items"]
    return [crossref_provider.to_claim(item) for item in items]


def _openalex_claims() -> list[ProviderClaim]:
    return [openalex_provider.to_claim(item) for item in _load("openalex_search.json")["results"]]


class _StubProvider(DiscoveryProvider):
    """مزوّدٌ يعيد حمولةً مسجَّلة. يحصي نداءاته ليُثبَت **أنه لم يُنادَ**."""

    def __init__(self, name: str, claims: list[ProviderClaim]) -> None:
        self.name = name
        self._claims = claims
        self.calls = 0

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        self.calls += 1
        return self._claims[:limit]

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        self.calls += 1
        return next((claim for claim in self._claims if claim.doi == doi), None)


class _DownProvider(DiscoveryProvider):
    """فهرسٌ لا يجيب. تعذّرُه حالٌ تُعلَن، لا صمتٌ يُقرأ «لا نتائج»."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        raise ProviderUnavailable(self.name, "ConnectTimeout")

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        raise ProviderUnavailable(self.name, "ConnectTimeout")


# ─────────────────────────── التسوية ───────────────────────────

def test_crossref_claim_carries_only_what_the_index_said():
    claim = _crossref_claims()[0]
    assert claim.provider == "crossref"
    # الـDOI يُسوَّى حالةً، فمقارنته بين فهرسين لا تنكسر بحرفٍ كبير.
    assert claim.doi == "10.1016/j.jbusres.2020.06.008"
    assert claim.provider_id == claim.doi
    assert claim.title == "Digital transformation in Saudi higher education"
    assert claim.authors == ("Nora Al-Qassim", "Peter Vance")
    assert claim.year == 2020
    assert claim.venue == "Journal of Business Research"
    assert (claim.volume, claim.issue, claim.pages) == ("117", "3", "245-259")
    assert claim.citation_count == 120
    assert claim.type == "journal-article"


def test_crossref_abstract_is_stripped_of_jats_and_never_invented():
    claims = _crossref_claims()
    assert claims[0].abstract == (
        "This study examines how public universities adopt digital platforms."
    )
    # العنصر الثاني لم يُرسل ناشرُه ملخّصًا — فيبقى غيابه غيابًا.
    assert claims[1].abstract is None


def test_crossref_open_access_is_unknown_not_closed():
    # Crossref لا يعلن الوصول المفتوح، و`False` هنا ستكون دعوى إغلاقٍ كاذبة.
    assert all(claim.open_access is None for claim in _crossref_claims())


def test_crossref_retraction_is_read_and_absence_is_not_a_denial():
    claims = _crossref_claims()
    assert claims[1].retraction_status == "retracted"
    # غياب `update-to` ليس شهادةً بأن الورقة سليمة.
    assert claims[0].retraction_status == "unknown"


def test_crossref_reads_a_consortium_name_without_dropping_the_author():
    assert _crossref_claims()[2].authors == ("Adaptive Assessment Working Group",)


def test_openalex_abstract_is_reassembled_from_the_index_it_sent():
    claim = _openalex_claims()[0]
    assert claim.abstract == (
        "This study examines how public universities adopt digital platforms."
    )
    # وعملٌ بلا فهرسٍ مقلوب لا يُؤلَّف له ملخّص.
    assert _openalex_claims()[2].abstract is None


def test_openalex_claim_carries_open_access_ids_and_pages():
    claim = _openalex_claims()[0]
    assert claim.provider_id == "W3012345678"
    assert claim.open_access is True
    assert claim.citation_count == 134
    assert claim.pages == "245-259"
    assert "pmid:32834111" in claim.alternate_ids
    # `is_retracted: false` نفيٌ صريح من الفهرس، فيُنقل نفيًا.
    assert claim.retraction_status == "none"


def test_openalex_unknown_open_access_stays_unknown():
    assert _openalex_claims()[2].open_access is None


# ─────────────────────────── التوحيد ───────────────────────────

def test_same_doi_across_two_indexes_is_one_candidate():
    merged = deduplicate([_crossref_claims()[0], _openalex_claims()[0]])
    assert len(merged) == 1
    assert merged[0].match_basis == "doi"
    assert merged[0].providers == ("crossref", "openalex")


def test_citation_counts_stay_attributed_and_are_never_summed():
    candidate = deduplicate([_crossref_claims()[0], _openalex_claims()[0]])[0]
    counts = candidate.citation_counts
    assert counts == {"crossref": 120, "openalex": 134}
    # لا مجموع ولا متوسّط: ٢٥٤ و١٢٧ رقمان لا يقولهما فهرس.
    assert not hasattr(candidate, "citation_count")


def test_a_different_doi_keeps_the_papers_apart_despite_one_title():
    """نسخة المؤتمر ونسخة الدوريّة عنوانهما واحد وسنتهما واحدة.

    ولو دُمجتا لاستشهد الباحث بواحدة وقد قرأ عن الأخرى، ولا شيء يقول له.
    """
    conference = _openalex_claims()[1]
    journal = _crossref_claims()[0]
    assert journal.title.lower() == conference.title.lower()
    assert journal.year == conference.year
    merged = deduplicate([journal, conference])
    assert len(merged) == 2


def test_title_year_author_merges_only_when_neither_side_has_a_doi():
    left, right = _openalex_claims()[2], _openalex_claims()[3]
    assert left.doi is None and right.doi is None
    merged = deduplicate([left, right])
    assert len(merged) == 1
    assert merged[0].match_basis == "title_year_author"


def test_a_bare_record_is_never_absorbed_into_an_identified_one():
    """مجهولُ الـDOI لا يُلحق بحزمةٍ معروفة على حُسن الظنّ."""
    identified = _crossref_claims()[0]
    bare = ProviderClaim(
        provider="openalex", provider_id="W7777",
        title=identified.title, year=identified.year, authors=identified.authors,
    )
    assert len(deduplicate([identified, bare])) == 2


def test_a_short_shared_title_is_not_an_identity():
    """«Correction» عنوانٌ لآلاف الأوراق، فلا يصلح دليلَ تطابق."""
    first = ProviderClaim(provider="openalex", provider_id="W1", title="Correction",
                          year=2019, authors=("Lina Farah",))
    second = ProviderClaim(provider="openalex", provider_id="W2", title="Correction",
                           year=2019, authors=("Lina Farah",))
    assert len(deduplicate([first, second])) == 2


def test_a_shared_alternate_id_joins_what_the_indexes_call_one_work():
    left = ProviderClaim(provider="crossref", provider_id="c1", title="Cohort study of X",
                         year=2015, alternate_ids=frozenset({"pmid:26000000"}))
    right = ProviderClaim(provider="openalex", provider_id="W9", title="Cohort Study of X",
                          year=2015, alternate_ids=frozenset({"pmid:26000000"}))
    merged = deduplicate([left, right])
    assert len(merged) == 1
    assert merged[0].match_basis == "provider_id"


# ─────────────────────────── التنسيق ───────────────────────────

def test_a_failing_index_is_named_and_never_read_as_no_results():
    up = _StubProvider("crossref", _crossref_claims())
    down = _DownProvider("openalex")
    result = asyncio.run(discover([up, down], "digital transformation"))
    statuses = {status.provider: status for status in result.provider_statuses}
    assert statuses["openalex"].ok is False
    assert statuses["openalex"].detail == "ConnectTimeout"
    assert statuses["crossref"].ok is True
    assert result.any_provider_failed is True
    # ونتائج الفهرس الحيّ لا تسقط بسقوط جاره.
    assert len(result.candidates) == 3


def test_every_index_down_is_a_declared_failure_not_an_empty_shelf():
    result = asyncio.run(discover([_DownProvider("crossref"), _DownProvider("openalex")], "x"))
    assert result.candidates == ()
    assert result.all_providers_failed is True


def test_both_indexes_are_asked_even_when_the_first_answered():
    crossref = _StubProvider("crossref", _crossref_claims())
    openalex = _StubProvider("openalex", _openalex_claims())
    asyncio.run(discover([crossref, openalex], "digital transformation"))
    assert (crossref.calls, openalex.calls) == (1, 1)


def test_a_researchgate_url_is_never_fetched_and_carries_no_metadata():
    crossref = _StubProvider("crossref", _crossref_claims())
    openalex = _StubProvider("openalex", _openalex_claims())
    result = asyncio.run(discover(
        [crossref, openalex], "https://www.researchgate.net/publication/4412_Digital",
    ))
    # لا نداء أصلًا — والامتناع يسبق الطلب لا يعقبه.
    assert (crossref.calls, openalex.calls) == (0, 0)
    assert result.candidates == ()
    assert result.external_link is not None
    assert result.external_link.host == "www.researchgate.net"
    assert result.external_link.verified is False


def test_an_academia_url_that_carries_a_real_doi_is_resolved_by_the_doi_alone():
    crossref = _StubProvider("crossref", _crossref_claims())
    result = asyncio.run(discover(
        [crossref], "https://www.academia.edu/1234/10.1016/j.jbusres.2020.06.008",
    ))
    assert result.external_link is not None
    assert result.external_link.verified is False
    # البيانات جاءت من الفهرس بالمعرّف الشرعي، لا من صفحة المنصّة.
    assert len(result.candidates) == 1
    assert result.candidates[0].doi == "10.1016/j.jbusres.2020.06.008"
    assert result.candidates[0].providers == ("crossref",)


def test_a_doi_query_is_resolved_by_identifier_not_by_words():
    crossref = _StubProvider("crossref", _crossref_claims())
    result = asyncio.run(discover([crossref], "10.1371/journal.pone.0011111"))
    assert len(result.candidates) == 1
    assert result.candidates[0].retraction_status == "retracted"


def test_an_unresolvable_doi_returns_nothing_and_invents_nothing():
    crossref = _StubProvider("crossref", _crossref_claims())
    result = asyncio.run(discover([crossref], "10.9999/does.not.exist"))
    assert result.candidates == ()
    assert result.all_providers_failed is False


@pytest.mark.parametrize(
    ("kwargs", "expected_dois"),
    [
        ({"year_from": 2021}, {"10.1109/tlt.2021.3055555"}),
        ({"year_to": 2018}, {"10.1371/journal.pone.0011111"}),
        ({"work_type": "journal-article"}, {
            "10.1016/j.jbusres.2020.06.008",
            "10.1371/journal.pone.0011111",
            "10.1109/tlt.2021.3055555",
        }),
    ],
)
def test_the_easy_filters_narrow_without_rewriting_the_records(kwargs, expected_dois):
    crossref = _StubProvider("crossref", _crossref_claims())
    result = asyncio.run(discover([crossref], "education", **kwargs))
    assert {candidate.doi for candidate in result.candidates} == expected_dois


def test_two_indexes_naming_one_kind_differently_land_in_one_basket():
    """Crossref يقول `journal-article` وOpenAlex يقول `article` عن الشيء نفسه.

    ولو صُفّي على الحرف لاختفت نصف النتائج بحسب أيّ فهرسٍ ردّ أوّلًا —
    ونصّ كل فهرس يبقى مقروءًا في ادعائه كما قاله.
    """
    crossref, openalex = _crossref_claims()[0], _openalex_claims()[0]
    assert (crossref.type, openalex.type) == ("journal-article", "article")
    assert crossref.work_type == openalex.work_type == "journal-article"
    assert _openalex_claims()[1].work_type == "conference-paper"


def test_filtering_by_kind_uses_the_shared_basket_not_the_index_wording():
    openalex = _StubProvider("openalex", _openalex_claims())
    result = asyncio.run(discover([openalex], "education", work_type="conference-paper"))
    assert {candidate.doi for candidate in result.candidates} == {"10.5555/conf.2020.4412"}


def test_the_wire_contract_keeps_a_candidate_from_posing_as_a_stored_reference():
    """**النوع نفسه يمنع الخلط.** مرشَّحٌ يحمل `id` أو `use_state` يوشك أن
    يُمرَّر حيث يُنتظر مرجعٌ مخزَّن، فيصير الاستيراد أثرًا جانبيًّا لبحث.
    """
    pytest.importorskip("pydantic")
    from athera_api.schemas.discovery import ReferenceCandidateView, ReferenceSearchResponse

    fields = set(ReferenceCandidateView.model_fields)
    assert fields.isdisjoint({"id", "source_id", "use_state", "decided_at"})
    # والنسبة جزءٌ من العقد لا زينةٌ في الشاشة.
    assert {"providers", "citation_counts", "claims", "match_basis"} <= fields
    assert "citation_count" not in fields

    envelope = set(ReferenceSearchResponse.model_fields)
    assert {"providers", "providers_enabled", "all_providers_failed"} <= envelope


def test_open_access_only_excludes_what_no_index_declared_open():
    """«مفتوح الوصول» حقٌّ يُعلَن، والمجهول لا يُدرَج تحته."""
    crossref = _StubProvider("crossref", _crossref_claims())
    openalex = _StubProvider("openalex", _openalex_claims())
    result = asyncio.run(discover([crossref, openalex], "education", open_access_only=True))
    assert {candidate.doi for candidate in result.candidates} == {
        "10.1016/j.jbusres.2020.06.008"
    }
