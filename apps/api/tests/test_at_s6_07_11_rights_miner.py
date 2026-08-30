"""AT-S6-07…11 — بوابة الحقوق والتأليف، والمنقّب، والأعمار (§23، §24، TC-06)."""
import datetime as dt

import pytest

from athera_api.services.thesis import aging, miner, vocab


# ── AT-S6-11: المنقّب حتمي ومؤصَّل ──

FACTS = miner.ThesisFacts(
    thesis_id="t1",
    title="محددات الثقة في الإعلان الرقمي وآثارها على نية الشراء: دراسة مقارنة",
    questions=("ما مستوى الثقة في الإعلان الرقمي؟", "ما علاقة الثقة بنية الشراء؟"),
    hypotheses=("توجد علاقة موجبة",),
    results=(("r1", "نتيجة أولى"), ("r2", "نتيجة ثانية"), ("r3", "نتيجة منشورة")),
    instruments=(("i1", "مقياس الثقة في الإعلان المطوَّر"),),
    variables=("v1", "v2", "v3"),
    sample_ids=("s1",),
    qualitative_phases=("مقابلات شبه منظمة مع خبراء",),
    null_result_ids=("r2",),
    published_result_ids=("r3",),
)


def test_miner_only_proposes_known_kinds():
    drafts = miner.mine(FACTS)
    assert drafts
    for draft in drafts:
        assert draft.opportunity_kind in vocab.OPPORTUNITY_KINDS
        assert draft.paper_kind in vocab.PAPER_KINDS


def test_every_draft_is_grounded_in_thesis_elements():
    """فرصة بلا مراجع إلى ما اشتُقت منه ليست اكتشافًا بل تخمينًا."""
    for draft in miner.mine(FACTS):
        assert draft.result_refs or draft.variable_refs or draft.sample_refs
        assert draft.rationale_ar.strip() and draft.rationale_en.strip()


def test_published_results_are_excluded_but_recorded_for_overlap():
    """§23.8 — ما نُشر من الرسالة لا يُقترح ثانيةً، لكنه يبقى في بصمة التداخل."""
    drafts = miner.mine(FACTS)
    assert all("r3" not in draft.result_refs for draft in drafts)
    assert any("r3" in draft.published_output_refs for draft in drafts)


def test_extraction_and_extension_are_both_produced():
    """AT-S6-11 — §23.5: الاستخلاص يعيد استخدام نتائج قائمة، والامتداد يضيف."""
    kinds = {draft.paper_kind for draft in miner.mine(FACTS)}
    assert kinds == {"extraction", "extension"}

    scale = next(d for d in miner.mine(FACTS) if d.opportunity_kind == "scale_development")
    assert scale.paper_kind == "extension"
    question = next(d for d in miner.mine(FACTS) if d.opportunity_kind == "independent_question")
    assert question.paper_kind == "extraction"


def test_a_thesis_without_elements_yields_nothing():
    """القائمة الفارغة نتيجة صحيحة؛ التخمين ليس كذلك."""
    assert miner.mine(miner.ThesisFacts(thesis_id="t2", title="عنوان بلا تفاصيل")) == []


def test_unknown_opportunity_kind_is_refused():
    with pytest.raises(ValueError):
        miner.OpportunityDraft(
            opportunity_kind="magic", paper_kind="extraction", working_title_ar="x",
            research_question_ar=None, rationale_ar="x", rationale_en="x",
        )


# ── AT-S6-10: أعمار البيانات والأدبيات (§23.8) ──

TODAY = dt.date(2026, 8, 30)


def test_old_thesis_triggers_update_recommendations():
    report = aging.compute(
        as_of=TODAY, data_collected_on=dt.date(2019, 3, 1), latest_cited_year=2018,
        literature_update_threshold_years=3, data_age_review_threshold_years=5,
    )
    assert report.data_age_years > 7
    assert report.literature_age_years > 7
    assert report.needs_literature_update is True
    assert report.needs_reanalysis_review is True


def test_recent_thesis_needs_no_update():
    report = aging.compute(
        as_of=TODAY, data_collected_on=dt.date(2025, 6, 1), latest_cited_year=2026,
        literature_update_threshold_years=3, data_age_review_threshold_years=5,
    )
    assert report.needs_literature_update is False
    assert report.needs_reanalysis_review is False


def test_missing_dates_yield_none_and_no_verdict():
    """«لا نعلم» ليست «حديثة» — نفس تمييز §11.4 في محرك الترقية."""
    report = aging.compute(
        as_of=TODAY, data_collected_on=None, latest_cited_year=None,
        literature_update_threshold_years=3, data_age_review_threshold_years=5,
    )
    assert report.data_age_years is None and report.literature_age_years is None
    assert report.needs_literature_update is None and report.needs_reanalysis_review is None
    assert "لا يُفترض" in report.note_ar
    assert report.note_en.strip()


def test_thresholds_are_parameters_not_constants():
    """عتبة التحديث تختلف بين مجلة وأخرى — فهي معامل لا ثابت."""
    lenient = aging.compute(
        as_of=TODAY, data_collected_on=dt.date(2023, 1, 1), latest_cited_year=2023,
        literature_update_threshold_years=10, data_age_review_threshold_years=10,
    )
    strict = aging.compute(
        as_of=TODAY, data_collected_on=dt.date(2023, 1, 1), latest_cited_year=2023,
        literature_update_threshold_years=1, data_age_review_threshold_years=1,
    )
    assert lenient.needs_literature_update is False
    assert strict.needs_literature_update is True


# ── AT-S6-07/08/09: بوابة GT1 (§23.9، §24.2، TC-06) ──

def test_gate_status_reports_blockers_not_a_boolean():
    """التفصيل يخبر الباحث بما ينقصه؛ «لا» وحدها لا تفعل."""
    from athera_api.services.thesis.rights import GateStatus

    status = GateStatus(
        opportunity_id=__import__("uuid").uuid4(), rights_basis=None, rights_approved=False,
        owner_consent_recorded=False, authors_total=0, authors_consented=0,
        authorship_approved=False, blockers=["rights_basis_missing", "no_authors_declared"],
    )
    assert not status.can_be_ready_to_submit
    assert "rights_basis_missing" in status.blockers


def test_analysis_is_permitted_before_rights_are_settled():
    """AT-S6-08 / TC-06 — المنع على التقدم لا على الفهم."""
    from athera_api.services.thesis.rights import ANALYSIS_ONLY_STATUSES

    assert "discovered" in ANALYSIS_ONLY_STATUSES
    assert "analysed" in ANALYSIS_ONLY_STATUSES
    assert "ready_to_submit" not in ANALYSIS_ONLY_STATUSES


def test_credit_roles_are_the_fourteen_standard_ones():
    """AT-S6-09 — §24.1."""
    assert len(vocab.CREDIT_ROLES) == 14
    assert "writing_original_draft" in vocab.CREDIT_ROLES
    assert "writing_review_editing" in vocab.CREDIT_ROLES
    assert "supervision" in vocab.CREDIT_ROLES


def test_no_party_kind_can_represent_a_model():
    """§24.2 — «AI لا يكون مؤلفًا» مفروضة بغياب القيمة."""
    forbidden = {"ai", "model", "agent", "system", "llm", "software_agent"}
    assert not (forbidden & set(vocab.AUTHORSHIP_PARTY_KINDS))
    assert set(vocab.AUTHORSHIP_PARTY_KINDS) == {"person", "organization"}


def test_rights_bases_match_the_three_in_the_spec():
    """§23.2 — من يحق له استخدام الوحدة."""
    assert set(vocab.RIGHTS_BASES) == {
        "thesis_owner", "supervisor_with_consent", "institution_policy",
    }
