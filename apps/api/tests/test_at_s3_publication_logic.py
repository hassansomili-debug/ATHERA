"""S3 — منطق النشر بعد سقوط الترقية الأكاديمية (ADR-0005، ADR-0006).

ثلاثة أبعاد بدّلت معناها ولم تبدّل وزنها: `publication_fit` بخمسة عشر،
و`publication_potential` بعشرة، و`target_journal_tier` هدفًا يعلنه الباحث
لا شرطًا تفرضه لائحة. وهذه الاختبارات تحرس الثلاثة معًا، وتحرس قبلها أن
مجموع كل مجموعة أوزان ما زال مئة — فإسقاط بُعد بلا إعادة توزيع يفسد كل
درجة يراها المستخدم.
"""
import datetime as dt

import pytest

from athera_api.services.publishing import journals, vocab as pub_vocab
from athera_api.services.trends import scoring, vocab as trend_vocab

NOW = dt.datetime(2026, 9, 1, tzinfo=dt.UTC)

# نفس سياسة الطبقات التي يستعملها اختبار المجلات — بيانات لا ثوابت كود.
POLICY = journals.TierPolicy(
    policy_id="default",
    tier_a_indexes=frozenset({"SSCI", "AHCI", "SCIE"}),
    tier_b_indexes=frozenset({"ESCI"}),
    tier_c_indexes=frozenset({"SCOPUS"}),
    verification_max_age_days=90,
)


def record(name: str) -> journals.IndexingRecord:
    return journals.IndexingRecord(
        index_name=name, status="active", last_verified_at=NOW - dt.timedelta(days=10)
    )


# ── الأوزان: المجموع مئة، والبُعد الأكاديمي لم يعد موجودًا ────────────

def test_journal_match_weights_still_total_one_hundred():
    assert sum(w for w, _, _ in pub_vocab.MATCH_CRITERIA.values()) == 100
    assert pub_vocab.MATCH_CRITERIA["publication_fit"][0] == 15
    assert "promotion_fit" not in pub_vocab.MATCH_CRITERIA


def test_opportunity_weights_still_total_one_hundred():
    assert scoring.total_weight() == 100
    assert trend_vocab.OPPORTUNITY_CRITERIA["publication_potential"][0] == 10
    assert "promotion_value" not in trend_vocab.OPPORTUNITY_CRITERIA


def test_both_dimensions_are_bilingual():
    for label_ar, label_en in (
        pub_vocab.MATCH_CRITERIA["publication_fit"][1:],
        trend_vocab.OPPORTUNITY_CRITERIA["publication_potential"][1:],
    ):
        assert any("؀" <= c <= "ۿ" for c in label_ar)
        assert label_en.strip() and not any("؀" <= c <= "ۿ" for c in label_en)


# ── هدف النشر: تفضيل الباحث، لا لائحة ────────────────────────────────

def test_eight_conceptual_targets_are_declared():
    assert set(pub_vocab.TARGET_JOURNAL_TIERS) == {
        "any_peer_reviewed", "scopus", "web_of_science", "q1", "q2",
        "open_access", "no_apc", "custom",
    }


@pytest.mark.parametrize(
    ("target", "index_name", "expected"),
    [
        ("web_of_science", "SSCI", 1.0),
        ("web_of_science", "SCOPUS", 0.0),
        ("scopus", "SCOPUS", 1.0),
        ("any_peer_reviewed", "SCOPUS", 1.0),
    ],
)
def test_target_tier_is_evaluated_against_the_journal(target, index_name, expected):
    facts = journals.JournalFacts(journal_id="j", name="J", indexing=(record(index_name),))
    tier = journals.assess_tier(facts, POLICY, as_of=NOW)
    ratio, ar, en = journals.publication_fit(target, tier, facts)
    assert ratio == expected
    assert ar.strip() and en.strip()


@pytest.mark.parametrize("target", ["q1", "q2"])
def test_quartile_targets_are_unknown_not_zero(target):
    """§20 — ما لا يُعرف يُعلن مجهولًا ولا يُقدَّر. لا بيانات أرباع في النموذج."""
    facts = journals.JournalFacts(journal_id="j", name="J", indexing=(record("SSCI"),))
    tier = journals.assess_tier(facts, POLICY, as_of=NOW)
    ratio, _, _ = journals.publication_fit(target, tier, facts)
    assert ratio is None


def test_no_target_means_unknown_not_failure():
    facts = journals.JournalFacts(journal_id="j", name="J", indexing=(record("SSCI"),))
    tier = journals.assess_tier(facts, POLICY, as_of=NOW)
    assert journals.publication_fit(None, tier, facts)[0] is None


def test_letter_tiers_still_work_for_backward_compatibility():
    facts = journals.JournalFacts(journal_id="j", name="J", indexing=(record("SSCI"),))
    tier = journals.assess_tier(facts, POLICY, as_of=NOW)
    assert journals.publication_fit("A", tier, facts)[0] == 1.0


def test_blocker_names_the_publication_target_not_a_regulation():
    esci = journals.JournalFacts(journal_id="j2", name="ESCI J", indexing=(record("ESCI"),))
    below = journals.match(
        journals.ManuscriptProfile(keywords=frozenset({"x"}), target_journal_tier="A"),
        esci, POLICY, as_of=NOW,
    )
    assert "below_publication_target" in below.blockers
    assert not any("promotion" in b for b in below.blockers)


def test_match_emits_publication_fit_and_never_promotion_fit():
    facts = journals.JournalFacts(journal_id="j", name="J", indexing=(record("SSCI"),))
    result = journals.match(
        journals.ManuscriptProfile(keywords=frozenset({"x"}), target_journal_tier="scopus"),
        facts, POLICY, as_of=NOW,
    )
    keys = {c.key for c in result.criteria}
    assert "publication_fit" in keys
    assert "promotion_fit" not in keys
    assert sum(c.weight for c in result.criteria) == 100


# ── الحدّ اللغوي: هدف لا وعد ─────────────────────────────────────────

def test_nothing_promises_acceptance():
    """لا يقدّر النظام احتمال قبول ولا يملك حقلًا له — قاعدة قائمة وتبقى."""
    surfaces = [
        *(f"{a} {b}" for a, b in pub_vocab.TARGET_JOURNAL_TIERS.values()),
        *(f"{lab_ar} {lab_en}" for _, lab_ar, lab_en in pub_vocab.MATCH_CRITERIA.values()),
        *(f"{lab_ar} {lab_en}" for _, lab_ar, lab_en in trend_vocab.OPPORTUNITY_CRITERIA.values()),
    ]
    for text in surfaces:
        lowered = text.lower()
        assert "acceptance probability" not in lowered
        assert "guarantee" not in lowered
        assert "احتمال القبول" not in text
