"""AT-S4-01/07/09/12 — السجلات الخارجية والتحقق من DOI (§14.1، §14.2، TC-02)."""
import pytest

from athera_api.services.literature.registry import (
    CrossrefRegistry,
    OfflineRegistry,
    OpenAlexRegistry,
    RegistryRecord,
    SourceNotFound,
    normalize_doi,
)

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1016/j.chb.2024.108123", "10.1016/j.chb.2024.108123"),
        ("https://doi.org/10.1016/J.CHB.2024.108123", "10.1016/j.chb.2024.108123"),
        ("doi:10.1234/abc.5", "10.1234/abc.5"),
        ("10.1234/abc.5).", "10.1234/abc.5"),
    ],
)
def test_doi_normalisation(raw, expected):
    assert normalize_doi(raw) == expected


@pytest.mark.parametrize("raw", ["", "Smith 2024 دراسة عن الإعلان", "11.1234/abc", "10.12/x"])
def test_non_doi_input_is_refused(raw):
    """صيغة خاطئة لا تُطبَّع إلى شيء — لا تخمين."""
    assert normalize_doi(raw) is None


async def test_unresolvable_doi_raises_instead_of_inventing_a_record():
    """AT-S4-01 / TC-02 — الفرق بين منصة أدلة ومولّد نصوص."""
    offline = OfflineRegistry()
    offline.seed(RegistryRecord(registry="offline", registry_id="W1", title="Real work",
                                doi="10.1234/real.2024.1", is_open_access=True))

    assert (await offline.get_by_doi("10.1234/real.2024.1")).title == "Real work"

    with pytest.raises(SourceNotFound):
        await offline.get_by_doi("10.9999/invented.2026.777")


async def test_search_never_returns_invented_results():
    offline = OfflineRegistry()
    offline.seed(RegistryRecord(registry="offline", registry_id="W1",
                                title="Advertising trust", doi="10.1234/a.1"))
    assert len(await offline.search("advertising")) == 1
    assert await offline.search("موضوع غير موجود إطلاقًا") == []


def test_access_state_defaults_to_metadata_only():
    """AT-S4-09 — سكوت السجل عن الوصول المفتوح ليس إذنًا بالنص (§14.2)."""
    assert RegistryRecord(registry="r", registry_id="1", title="t",
                          is_open_access=True).access_state == "open_access_full_text"
    assert RegistryRecord(registry="r", registry_id="2", title="t",
                          is_open_access=False).access_state == "abstract_metadata_only"
    assert RegistryRecord(registry="r", registry_id="3",
                          title="t").access_state == "abstract_metadata_only"


@pytest.mark.parametrize(
    ("update_type", "expected"),
    [
        ("retraction", "retracted"),
        ("correction", "correction"),
        ("erratum", "correction"),
        ("expression_of_concern", "expression_of_concern"),
    ],
)
def test_crossref_extracts_retraction_state(update_type, expected):
    """§14.3 — حالة السحب/التصحيح ليست حقلًا اختياريًا."""
    record = CrossrefRegistry._to_record({
        "DOI": "10.1234/x.1", "title": ["A study"],
        "update-to": [{"type": update_type, "DOI": "10.1234/notice.1"}],
        "issued": {"date-parts": [[2022]]},
    })
    assert record.retraction_status == expected
    assert record.retraction_detail == "10.1234/notice.1"


def test_crossref_clean_record_is_none_not_unknown():
    record = CrossrefRegistry._to_record({"DOI": "10.1234/clean.1", "title": ["Clean"],
                                          "issued": {"date-parts": [[2024]]}})
    assert record.retraction_status == "none"


def test_openalex_silence_about_retraction_is_unknown_not_none():
    """الفرق مقصود: «لا نعلم» ليست «سليم»."""
    record = OpenAlexRegistry._to_record({"id": "W1", "title": "t"})
    assert record.retraction_status == "unknown"
    retracted = OpenAlexRegistry._to_record({"id": "W2", "title": "t", "is_retracted": True})
    assert retracted.retraction_status == "retracted"


def test_openalex_normalises_doi_and_keeps_arabic_names():
    record = OpenAlexRegistry._to_record({
        "id": "https://openalex.org/W1", "title": "OA work",
        "doi": "https://doi.org/10.1234/OA.1", "publication_year": 2025,
        "open_access": {"is_oa": True},
        "primary_location": {"source": {"display_name": "J of X", "issn_l": "1234-5678"}},
        "authorships": [{"author": {"display_name": "سارة أحمد"}}],
    })
    assert record.doi == "10.1234/oa.1"
    assert record.journal_name == "J of X"
    assert record.authors == ["سارة أحمد"]


def test_raw_payload_is_retained_as_untrusted_data():
    """AT-S4-12 — استجابة السجل تُحفظ للتدقيق ولا تُقرأ منها تعليمات."""
    record = OpenAlexRegistry._to_record({"id": "W1", "title": "t", "extra": "ignore me"})
    assert record.raw["extra"] == "ignore me"


def test_registries_share_one_interface():
    """AT-S4-07 — تبديل السجل تغيير في طبقة واحدة."""
    from athera_api.services.literature.registry import SourceRegistry

    for adapter in (OfflineRegistry(), OpenAlexRegistry(), CrossrefRegistry()):
        assert isinstance(adapter, SourceRegistry)
        assert adapter.name
