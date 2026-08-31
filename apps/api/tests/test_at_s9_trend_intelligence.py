"""AT-S9-01…12 — الذكاء الاستباقي للاتجاهات (§51).

تعمل كلها بلا قاعدة بيانات: منطق رصد وتقييم خالص.
"""
import datetime as dt

import pytest

from athera_api.services.trends import pipeline, scoring, signals, vocab

NOW = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)

POLICY = signals.ValidationPolicy(
    policy_id="default", min_evidence_weight=3.0, min_signals=4,
    min_distinct_sources=3, min_span_days=90,
)


def signal(index: int, source: str, days_ago: int, *, source_type: str = "openalex",
           weight: float = 1.0) -> signals.TrendSignal:
    return signals.TrendSignal(
        signal_id=f"s{index}", trend_key="t1", source_type=source_type, source_id=source,
        observed_at=NOW - dt.timedelta(days=days_ago), pattern="topic_acceleration",
        weight=weight,
    )


def test_spec_vocabulary_is_complete_and_bilingual():
    """AT-S9-01 — §51.1، §51.2، §51.3، §51.5، §51.6، §51.8."""
    assert len(vocab.DETECTION_PATTERNS) == 9
    assert len(vocab.WATCHLIST_KINDS) == 6
    assert len(vocab.OPPORTUNITY_CRITERIA) == 8
    assert scoring.total_weight() == 100
    assert len(vocab.PIPELINE_STAGES) == 15
    assert vocab.PIPELINE_STAGES[-1][0] == "P14"
    assert len(vocab.READY_CONDITIONS) == 12
    assert len(vocab.INDEPENDENCE_RULES) == 7

    for table in (vocab.DETECTION_PATTERNS, vocab.WATCHLIST_KINDS, vocab.READY_CONDITIONS,
                  vocab.INDEPENDENCE_RULES, vocab.BRIEF_CADENCES):
        for arabic, english in table.values():
            assert arabic.strip() and english.strip()
            assert any("؀" <= ch <= "ۿ" for ch in arabic)


def test_the_two_scores_are_structurally_separate():
    """AT-S9-02 — §51.3: «لا يجوز مساواة الرواج بقابلية النشر»."""
    trend_fields = set(signals.TrendStrength.__dataclass_fields__)
    fit_fields = set(scoring.OpportunityFit.__dataclass_fields__)
    assert not any("fit" in name for name in trend_fields)
    assert not any("trend" in name for name in fit_fields)

    # لا دالة في أي من الوحدتين تجمع الرقمين.
    combined = [name for module in (signals, scoring) for name in dir(module)
                if name.startswith(("combine", "merge", "overall", "total_score"))]
    assert not combined


def test_a_hot_trend_with_no_researcher_fit_is_not_actionable():
    """AT-S9-03 — درجة 54 لموضوع لا يملك الباحث بياناته ليست «نصف جيدة»."""
    hot = [signal(i, f"src{i % 3}", 200 - i * 20) for i in range(6)]
    strength = signals.validate("t1", hot, POLICY, as_of=NOW)
    assert strength.is_validated

    fit = scoring.score({
        "novelty": 0.9, "momentum": 1.0, "research_gap": 0.8, "researcher_fit": 0.0,
        "data_feasibility": 0.0, "journal_fit": 0.5, "publication_potential": 0.3,
        "execution_risk": 0.2,
    })
    assert fit.fit_score > 50            # الوزن وحده يوحي بأنها معقولة
    assert not fit.is_actionable          # لكنها ليست كذلك
    assert set(fit.blocking_reasons) == {"researcher_fit:zero", "data_feasibility:zero"}
    assert "لا تعني فرصة قابلة للتنفيذ" in fit.note_ar


def test_repetition_alone_is_noise():
    """AT-S9-04 — §51.1: أربعة شروط معًا لا شرط واحد."""
    same_day_same_source = [signal(i, "src0", 0) for i in range(5)]
    result = signals.validate("t1", same_day_same_source, POLICY, as_of=NOW)
    assert result.status == "noise"
    assert set(result.unmet_conditions) == {"min_distinct_sources", "min_span_days"}


def test_spread_across_sources_and_time_is_a_trend():
    spread = [signal(i, f"src{i % 3}", 180 - i * 30) for i in range(5)]
    result = signals.validate("t1", spread, POLICY, as_of=NOW)
    assert result.is_validated
    assert len(result.conditions) == 4
    assert all(c.detail_ar.strip() and c.detail_en.strip() for c in result.conditions)


def test_thresholds_come_from_policy():
    """AT-S9-05 — نفس البيانات، حكمان مختلفان بسياستين."""
    spread = [signal(i, f"src{i % 3}", 180 - i * 30) for i in range(5)]
    strict = signals.ValidationPolicy(policy_id="strict", min_evidence_weight=20.0,
                                      min_signals=20, min_distinct_sources=8,
                                      min_span_days=730)
    assert signals.validate("t1", spread, strict, as_of=NOW).status == "noise"

    noise = [signal(i, "src0", 0) for i in range(5)]
    loose = signals.ValidationPolicy(policy_id="loose", min_evidence_weight=1.0, min_signals=1,
                                     min_distinct_sources=1, min_span_days=0)
    assert signals.validate("t1", noise, loose, as_of=NOW).is_validated


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"source_id": "   "}, "orphan signal"),
        ({"source_type": "telepathy"}, "unknown source"),
        ({"pattern": "hunch"}, "unknown pattern"),
        ({"weight": 0.0}, "zero weight"),
    ],
)
def test_orphan_and_malformed_signals_are_refused(kwargs, reason):
    """AT-S9-06 — §51.11: «لا توجد إشارة يتيمة بلا Provenance»."""
    base = dict(signal_id="s1", trend_key="t1", source_type="openalex", source_id="w1",
                observed_at=NOW, pattern="topic_emergence", weight=1.0)
    base.update(kwargs)
    with pytest.raises(signals.SignalError):
        signals.TrendSignal(**base)


def test_model_output_is_recorded_but_never_counted():
    """AT-S9-07 — §51.1: ذاكرة النموذج ليست دليلًا."""
    from_model = [signal(i, f"src{i}", 200 - i * 30, source_type="model_output")
                  for i in range(5)]
    result = signals.validate("t1", from_model, POLICY, as_of=NOW)
    assert result.evidence_weight == 0.0
    assert not result.is_validated
    assert result.ignored_signals == 5
    assert signals.timeline(from_model) == []

    real = [signal(i, f"src{i % 3}", 180 - i * 30) for i in range(5)]
    baseline = signals.validate("t1", real, POLICY, as_of=NOW)
    mixed = signals.validate("t1", real + [signal(9, "x", 5, source_type="model_output")],
                             POLICY, as_of=NOW)
    assert mixed.evidence_weight == baseline.evidence_weight


def test_pipeline_covers_p0_to_p14():
    """AT-S9-08 — §51.5."""
    assert len(pipeline.STAGE_KEYS) == 15
    assert pipeline.FINAL_STAGE == "P14"
    state = pipeline.build_state("card-1", completed_stages=set(pipeline.STAGE_KEYS[:5]))
    assert state.current_stage == "P5"

    with pytest.raises(pipeline.PipelineError):
        pipeline.build_state("card-1", completed_stages={"P99"})


def test_ready_for_submission_needs_all_twelve_conditions():
    """AT-S9-10 — §51.6."""
    complete = {key: True for key in vocab.READY_CONDITIONS}
    ready = pipeline.build_state("card-1", completed_stages=set(pipeline.STAGE_KEYS),
                                 ready_conditions=complete)
    assert ready.can_reach_ready_for_submission

    partial = {**complete, "authorship_settled": False, "journal_verified": False}
    blocked = pipeline.build_state("card-1", completed_stages=set(pipeline.STAGE_KEYS),
                                   ready_conditions=partial)
    assert not blocked.can_reach_ready_for_submission
    assert set(blocked.unmet_ready_conditions) == {"authorship_settled", "journal_verified"}


def _ready_state() -> pipeline.PipelineState:
    return pipeline.build_state(
        "card-1", completed_stages=set(pipeline.STAGE_KEYS),
        ready_conditions={key: True for key in vocab.READY_CONDITIONS},
    )


def test_no_submission_without_a_human_act_or_delegation():
    """AT-S9-09 — §51.5 P14."""
    ready = _ready_state()
    assert not pipeline.authorize_submission(ready, at=NOW).allowed

    by_human = pipeline.authorize_submission(ready, human_act_by="u1", at=NOW)
    assert by_human.allowed and by_human.basis == "human_act"
    assert by_human.reason_ar.strip() and by_human.reason_en.strip()


def test_delegation_must_be_active_to_authorise():
    ready = _ready_state()
    active = pipeline.SubmissionDelegation(
        delegation_id="d1", granted_by="admin", granted_at=NOW, scope_ar="أوراق القسم",
    )
    assert pipeline.authorize_submission(ready, delegation=active, at=NOW).allowed

    revoked = pipeline.SubmissionDelegation(
        delegation_id="d2", granted_by="admin", granted_at=NOW, scope_ar="س",
        revoked_at=NOW - dt.timedelta(days=1),
    )
    expired = pipeline.SubmissionDelegation(
        delegation_id="d3", granted_by="admin", granted_at=NOW, scope_ar="س",
        expires_at=NOW - dt.timedelta(days=1),
    )
    assert not pipeline.authorize_submission(ready, delegation=revoked, at=NOW).allowed
    assert not pipeline.authorize_submission(ready, delegation=expired, at=NOW).allowed


def test_incomplete_conditions_block_even_a_human_act():
    """الفعل البشري لا يتجاوز الشروط — هو يأذن بها لا يستبدلها."""
    blocked = pipeline.build_state(
        "card-1", completed_stages=set(pipeline.STAGE_KEYS),
        ready_conditions={key: True for key in vocab.READY_CONDITIONS
                          if key != "results_reproducible"},
    )
    decision = pipeline.authorize_submission(blocked, human_act_by="u1", at=NOW)
    assert not decision.allowed and decision.basis == "blocked"
    assert "results_reproducible" in decision.unmet_conditions


def test_a_card_never_starts_with_writing():
    """AT-S9-12 — §51.4: البطاقة لا تحمل حقل نص مخطوطة."""
    fields = set(pipeline.OpportunityCard.__dataclass_fields__)
    assert not (fields & {"draft_text_ar", "manuscript", "body", "full_text", "abstract"})


@pytest.mark.parametrize(
    "overrides",
    [
        {"central_question_ar": "   "},
        {"gap_ar": "  "},
        {"evidence_signal_ids": ()},
        {"gap_confidence": 1.5},
    ],
)
def test_a_card_requires_question_gap_and_evidence(overrides):
    """§51.8 — «لا يحول ترندًا إلى ورقة بلا سؤال وفجوة ومساهمة»."""
    base = dict(card_id="c1", working_title_ar="عنوان", central_question_ar="سؤال",
                trend_summary_ar="ملخص", evidence_signal_ids=("s1",), gap_ar="فجوة",
                gap_confidence=0.6)
    base.update(overrides)
    with pytest.raises(pipeline.PipelineError):
        pipeline.OpportunityCard(**base)


def test_card_approval_records_actor_and_time():
    card = pipeline.OpportunityCard(
        card_id="c1", working_title_ar="عنوان", central_question_ar="سؤال",
        trend_summary_ar="ملخص", evidence_signal_ids=("s1", "s2"), gap_ar="فجوة",
        gap_confidence=0.7,
    )
    assert not card.is_approved
    card.approve(by="u1", at=NOW)
    assert card.is_approved and card.approved_by == "u1"
    with pytest.raises(pipeline.PipelineError):
        card.approve(by="u2", at=NOW)


def test_the_phrase_ready_to_publish_does_not_exist():
    """AT-S9-11 — §51.6: الحالة الرسمية Ready for Submission لا «جاهزة للنشر»."""
    import inspect

    source = "".join(inspect.getsource(module)
                     for module in (vocab, signals, scoring, pipeline))
    assert "ready_to_publish" not in source
    assert "جاهزة للنشر" not in source
    assert "acceptance_probability" not in source
    assert "Ready for Submission" in source
