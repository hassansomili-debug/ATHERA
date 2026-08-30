"""AT-S7-01…06 — طبقات الثقة ومطابقة المجلات (§20، TC-04)."""
import dataclasses
import datetime as dt

import pytest

from athera_api.services.publishing import journals, vocab

NOW = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)

POLICY = journals.TierPolicy(
    policy_id="default",
    tier_a_indexes=frozenset({"SSCI", "AHCI", "SCIE"}),
    tier_b_indexes=frozenset({"ESCI"}),
    tier_c_indexes=frozenset({"SCOPUS"}),
    verification_max_age_days=90,
)


def record(name: str, status: str = "active", days_ago: int = 10) -> journals.IndexingRecord:
    return journals.IndexingRecord(
        index_name=name, status=status, last_verified_at=NOW - dt.timedelta(days=days_ago)
    )


def test_spec_vocabulary_is_complete():
    """AT-S7-01 — §19.1، §20.2، §20.4، §21، §22.1."""
    assert len(vocab.MANUSCRIPT_SECTIONS) == 18
    assert set(vocab.TRUST_TIERS) == {"A", "B", "C", "D", "X"}
    assert len(vocab.MATCH_CRITERIA) == 9
    assert sum(weight for weight, _, _ in vocab.MATCH_CRITERIA.values()) == 100
    assert len(vocab.VERIFICATION_POINTS) == 4
    assert len(vocab.REVIEWER_ROLES) == 5
    assert len(vocab.REPORT_SECTIONS) == 6
    assert len(vocab.READINESS_STATUSES) == 4
    assert len(vocab.SUBMISSION_PACKAGE_ITEMS) == 13


def test_no_acceptance_probability_field_exists_anywhere():
    """AT-S7-02 — §20.4. الضمانة بغياب الحقل لا بفحص نصي."""
    facts = journals.JournalFacts(journal_id="j1", name="J", indexing=(record("SSCI"),))
    result = journals.match(journals.ManuscriptProfile(), facts, POLICY, as_of=NOW)

    banned = {"acceptance_probability", "accept_probability", "acceptance_chance",
              "acceptance_rate", "probability"}
    # `dataclasses.fields` لا `vars`: الأخيرة تنهار مع `slots=True` — وكانت
    # تمر على مفسّر أقدم يُسقط slots، فتُخفي أن الفحص لا يفحص شيئًا.
    fields = {f.name for f in dataclasses.fields(result)} | {c.key for c in result.criteria}
    assert not (banned & fields)
    assert not (banned & set(vocab.MATCH_CRITERIA))


def test_esci_does_not_reach_tier_a_but_the_rule_is_data_driven():
    """AT-S7-03 — §20.2/§20.3، بآلية عامة لا استثناء مكتوب في الكود."""
    esci = journals.JournalFacts(journal_id="j2", name="ESCI J", indexing=(record("ESCI"),))
    assessment = journals.assess_tier(esci, POLICY, as_of=NOW)
    assert assessment.tier == "B"
    assert not assessment.meets_strict_wos

    ssci = journals.JournalFacts(journal_id="j3", name="SSCI J", indexing=(record("SSCI"),))
    assert journals.assess_tier(ssci, POLICY, as_of=NOW).meets_strict_wos

    # مؤسسة أخرى تعرّف الصرامة بشكل مختلف — بلا تعديل كود.
    lenient = journals.TierPolicy(
        policy_id="lenient", tier_a_indexes=frozenset({"SSCI", "ESCI"}),
        tier_b_indexes=frozenset(), tier_c_indexes=frozenset({"SCOPUS"}),
        verification_max_age_days=90,
    )
    assert journals.assess_tier(esci, lenient, as_of=NOW).tier == "A"


def test_stale_indexing_falls_back_to_needs_reverification():
    """AT-S7-04 — مجلة كانت في SSCI قبل عامين ليست بالضرورة فيها اليوم."""
    stale = journals.JournalFacts(
        journal_id="j4", name="Stale", indexing=(record("SSCI", days_ago=400),)
    )
    assessment = journals.assess_tier(stale, POLICY, as_of=NOW)
    assert assessment.tier != "A"
    assert "SSCI" in assessment.stale_indexes
    assert assessment.indexes[0].status == journals.NEEDS_REVERIFICATION
    assert not assessment.indexes[0].counts


def test_discontinued_and_peer_reviewed_tiers():
    dead = journals.JournalFacts(journal_id="j5", name="Dead", indexing=(record("SSCI"),),
                                 is_discontinued=True)
    assert journals.assess_tier(dead, POLICY, as_of=NOW).tier == "X"

    peer = journals.JournalFacts(journal_id="j6", name="Peer", is_peer_reviewed=True)
    assert journals.assess_tier(peer, POLICY, as_of=NOW).tier == "D"


@pytest.mark.parametrize("point", vocab.VERIFICATION_POINTS)
def test_missing_verification_always_requires_recheck(point):
    """AT-S7-05 / TC-04 — «لا نعلم» ليست «سليمة»."""
    assert journals.requires_reverification(None, POLICY, at_point=point, as_of=NOW) is True


def test_verification_freshness_window():
    fresh = NOW - dt.timedelta(days=10)
    stale = NOW - dt.timedelta(days=200)
    assert journals.requires_reverification(fresh, POLICY, at_point="submission",
                                            as_of=NOW) is False
    assert journals.requires_reverification(stale, POLICY, at_point="acceptance",
                                            as_of=NOW) is True


def test_unknown_verification_point_is_refused():
    with pytest.raises(ValueError):
        journals.requires_reverification(NOW, POLICY, at_point="whenever", as_of=NOW)


def test_match_carries_its_criteria_and_blockers():
    """AT-S7-06 — الدرجة لا تُعاد مجردة."""
    facts = journals.JournalFacts(
        journal_id="j1", name="Journal of Advertising", indexing=(record("SSCI"),),
        scope_keywords=frozenset({"advertising", "trust"}),
        recent_article_keywords=frozenset({"advertising"}),
        accepted_methods=frozenset({"survey"}), apc_usd=0, oa_model="hybrid",
        median_review_days=90,
    )
    profile = journals.ManuscriptProfile(
        keywords=frozenset({"advertising", "trust"}),
        method_keys=frozenset({"survey"}), required_tier="A",
    )
    result = journals.match(profile, facts, POLICY, as_of=NOW)

    assert len(result.criteria) == 9
    assert all(c.detail_ar.strip() and c.detail_en.strip() for c in result.criteria)
    assert result.note_ar.strip() and result.note_en.strip()
    assert result.blockers == []
    assert result.fit_score >= 80


def test_uncomputed_criteria_are_declared_and_score_zero():
    sparse = journals.JournalFacts(journal_id="j7", name="Sparse", indexing=(record("SCOPUS"),))
    result = journals.match(
        journals.ManuscriptProfile(keywords=frozenset({"advertising"})), sparse, POLICY, as_of=NOW
    )
    assert len(result.uncomputed) >= 4
    assert all(c.points == 0.0 for c in result.criteria if c.ratio is None)


def test_blockers_name_the_reason():
    esci = journals.JournalFacts(journal_id="j2", name="ESCI J", indexing=(record("ESCI"),))
    below = journals.match(
        journals.ManuscriptProfile(keywords=frozenset({"x"}), required_tier="A"),
        esci, POLICY, as_of=NOW,
    )
    assert "tier_below_promotion_requirement" in below.blockers

    stale = journals.JournalFacts(journal_id="j4", name="Stale",
                                  indexing=(record("SSCI", days_ago=400),))
    assert "indexing_needs_reverification" in journals.match(
        journals.ManuscriptProfile(), stale, POLICY, as_of=NOW
    ).blockers
