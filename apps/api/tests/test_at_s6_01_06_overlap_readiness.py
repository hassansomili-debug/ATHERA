"""AT-S6-01…06 — مصفوفة التداخل ودرجة الجاهزية (§23.4–23.7، TC-05).

تعمل بلا قاعدة بيانات: منطق علمي خالص على بصمات الفرص.
"""
import pytest

from athera_api.services.thesis import overlap, readiness, vocab

F = overlap.OpportunityFingerprint

DEFAULT_POLICY = overlap.OverlapPolicy(
    policy_id="default",
    thresholds={"research_question": 0.6, "sample": 0.8, "variable": 0.6, "result": 0.5,
                "table_figure": 0.3, "text": 0.2, "published_output": 0.01},
    salami_min_dimensions=3,
    salami_critical_dimensions=frozenset({"published_output"}),
)


def _fingerprint(identifier: str, **overrides) -> overlap.OpportunityFingerprint:
    base = dict(
        research_question="أثر الثقة في الإعلان على نية الشراء لدى الشباب",
        sample_ids=frozenset({"s1"}), variable_ids=frozenset({"v1", "v2"}),
        result_ids=frozenset({"r1", "r2"}), table_figure_ids=frozenset({"t1"}),
        text="النتائج تشير إلى ارتباط موجب بين الثقة ونية الشراء",
        published_output_ids=frozenset(),
    )
    base.update(overrides)
    return F(opportunity_id=identifier, **base)


def test_spec_vocabulary_is_complete_and_bilingual():
    """AT-S6-01 — §23.4/23.5/23.7/23.6 و§24.1."""
    assert len(vocab.OPPORTUNITY_KINDS) == 10
    assert set(vocab.PAPER_KINDS) == {"extraction", "extension"}
    assert len(vocab.OVERLAP_DIMENSIONS) == 7
    assert len(vocab.READINESS_COMPONENTS) == 8
    assert len(vocab.READINESS_OUTCOMES) == 5
    assert len(vocab.CREDIT_ROLES) == 14
    assert readiness.total_weight() == 100

    for table in (vocab.OPPORTUNITY_KINDS, vocab.PAPER_KINDS, vocab.OVERLAP_DIMENSIONS,
                  vocab.READINESS_OUTCOMES, vocab.CREDIT_ROLES, vocab.RIGHTS_BASES):
        for arabic, english in table.values():
            assert arabic.strip() and english.strip()
            assert any("؀" <= ch <= "ۿ" for ch in arabic)


def test_ai_is_not_a_possible_authorship_party():
    """§24.2 — المنع بغياب القيمة، لا بفحص نصي."""
    assert set(vocab.AUTHORSHIP_PARTY_KINDS) == {"person", "organization"}


def test_missing_data_is_not_computed_never_zero():
    """AT-S6-02 — رقم مطمئن مبني على غياب بيانات أخطر من غياب الرقم."""
    known = _fingerprint("op-a")
    unknown = F(opportunity_id="op-b", research_question=None, sample_ids=None,
                variable_ids=None, result_ids=None, table_figure_ids=None,
                text=None, published_output_ids=None)
    result = overlap.compare(known, unknown, DEFAULT_POLICY)

    assert len(result.not_computed) == 7
    assert all(dimension.value is None for dimension in result.dimensions)
    assert all(dimension.status == overlap.NOT_COMPUTED for dimension in result.dimensions)
    assert not result.salami_alert


def test_duplicate_opportunities_raise_a_salami_alert():
    """AT-S6-03 / TC-05."""
    left, right = _fingerprint("op-1"), _fingerprint("op-2")
    result = overlap.compare(left, right, DEFAULT_POLICY)

    assert result.salami_alert
    assert result.blocks_separate_conversion
    question = next(d for d in result.dimensions if d.dimension == "research_question")
    assert question.value == 1.0 and question.exceeds_threshold


def test_genuinely_distinct_opportunities_do_not_alert():
    left = _fingerprint("op-1")
    right = _fingerprint(
        "op-3", research_question="دور الشفافية في بناء سمعة العلامة",
        sample_ids=frozenset({"s2"}), variable_ids=frozenset({"v7", "v8"}),
        result_ids=frozenset({"r9"}), table_figure_ids=frozenset({"t5"}),
        text="تناولت الورقة الشفافية المؤسسية وأثرها في السمعة",
    )
    result = overlap.compare(left, right, DEFAULT_POLICY)
    assert not result.salami_alert
    assert result.exceeded == []


def test_thresholds_come_from_policy_not_code():
    """AT-S6-04 — §23.7: القواعد تحددها سياسات التحرير/النزاهة."""
    left = _fingerprint("op-1")
    moderate = _fingerprint(
        "op-6", research_question="أثر الثقة في الإعلان على الولاء للعلامة",
        variable_ids=frozenset({"v1", "v5"}), result_ids=frozenset({"r7"}),
        table_figure_ids=frozenset({"t7"}),
        text="تناولت الورقة الثقة في الإعلان وأثرها في الولاء",
    )
    strict = overlap.OverlapPolicy(
        policy_id="strict", thresholds={k: 0.2 for k in vocab.OVERLAP_DIMENSIONS},
        salami_min_dimensions=2,
    )

    assert not overlap.compare(left, moderate, DEFAULT_POLICY).salami_alert
    assert overlap.compare(left, moderate, strict).salami_alert
    assert overlap.compare(left, moderate, strict).policy_id == "strict"


def test_a_critical_dimension_alerts_on_its_own():
    """نشر سابق مشترك يكفي وحده، دون بلوغ حد عدد الأبعاد."""
    left = _fingerprint(
        "op-4", research_question="قياس فاعلية الرسائل التوعوية الصحية في الإذاعة",
        sample_ids=frozenset({"s9"}), variable_ids=frozenset({"v9"}),
        result_ids=frozenset({"r9"}), table_figure_ids=frozenset({"t9"}),
        text="تناولت الدراسة الرسائل التوعوية الصحية وأساليب إنتاجها إذاعيًا",
        published_output_ids=frozenset({"pub-1"}),
    )
    right = _fingerprint(
        "op-5", research_question="اتجاهات الجمهور نحو رعاية العلامات للفعاليات الرياضية",
        sample_ids=frozenset({"s8"}), variable_ids=frozenset({"v8"}),
        result_ids=frozenset({"r8"}), table_figure_ids=frozenset({"t8"}),
        text="بحثت الورقة رعاية العلامات التجارية للفعاليات الرياضية واتجاهات المتلقين",
        published_output_ids=frozenset({"pub-1"}),
    )
    result = overlap.compare(left, right, DEFAULT_POLICY)
    assert result.exceeded == ["published_output"]
    assert result.salami_alert
    assert len(result.exceeded) < DEFAULT_POLICY.salami_min_dimensions


def test_matrix_covers_every_pair():
    fingerprints = [_fingerprint("op-1"), _fingerprint("op-2"),
                    _fingerprint("op-3", research_question="سؤال بعيد تمامًا عن الأول",
                                 sample_ids=frozenset({"s3"}),
                                 variable_ids=frozenset({"v9"}),
                                 result_ids=frozenset({"r9"}),
                                 table_figure_ids=frozenset({"t9"}),
                                 text="موضوع مختلف كليًا عن الأول")]
    results = overlap.matrix(fingerprints, DEFAULT_POLICY)
    assert len(results) == 3
    assert sum(1 for r in results if r.salami_alert) == 1


# ── AT-S6-05/06: درجة الجاهزية (§23.6) ──

FULL_RATIOS = {key: 0.85 for key in vocab.READINESS_COMPONENTS}


def test_score_carries_its_components_and_is_not_a_bare_number():
    result = readiness.compute(FULL_RATIOS, salami_alert=False)
    assert len(result.components) == 8
    assert result.outcome == "ready_to_convert"
    assert result.outcome_label_ar.strip() and result.outcome_label_en.strip()
    assert result.note_ar.strip() and result.note_en.strip()
    assert all(component.rationale_ar for component in result.components)


def test_salami_alert_precedes_every_calculation():
    """ورقة مكررة لا تُنقذها جودة منهجها."""
    perfect = {key: 1.0 for key in vocab.READINESS_COMPONENTS}
    assert readiness.compute(perfect, salami_alert=True).outcome == "do_not_publish_separately"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"novelty": 0.1}, "do_not_publish_separately"),
        ({"independent_question": 0.2}, "merge_with_another"),
        ({"independent_results": 0.2}, "needs_reanalysis"),
        ({"method_data_strength": 0.3}, "needs_reanalysis"),
        ({"topic_currency": 0.2}, "needs_theoretical_update"),
    ],
)
def test_each_outcome_is_reachable(overrides, expected):
    """AT-S6-05 — المخرجات الخمسة في §23.6."""
    ratios = {**FULL_RATIOS, **overrides}
    assert readiness.compute(ratios, salami_alert=False).outcome == expected


def test_uncomputed_components_are_declared_not_guessed():
    ratios = {**FULL_RATIOS, "independent_question": None, "journal_fit": None}
    result = readiness.compute(ratios, salami_alert=False)
    assert set(result.uncomputed) == {"independent_question", "journal_fit"}
    rationale = next(c.rationale_ar for c in result.components if c.key == "journal_fit")
    assert "لم تتوفر" in rationale


def test_invalid_inputs_are_refused():
    with pytest.raises(ValueError):
        readiness.compute({"novelty": 1.5}, salami_alert=False)
    with pytest.raises(ValueError):
        readiness.ReadinessScore(components=[], outcome="definitely_publish")
