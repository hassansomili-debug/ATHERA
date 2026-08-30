"""AT-S5-10/11 — متطلبات التصميم والبروتوكول (§16، §9)."""
import pytest

from athera_api.services.golden_thread import methodology


def test_all_five_study_types_from_spec_have_requirements():
    """§16.1–16.5 — الأنواع الخمسة."""
    assert set(methodology.REQUIREMENTS) == {
        "quantitative", "qualitative", "mixed_methods", "experimental", "review",
    }


@pytest.mark.parametrize("study_type", sorted(methodology.REQUIREMENTS))
def test_every_requirement_is_bilingual_and_gated(study_type):
    for requirement in methodology.REQUIREMENTS[study_type]:
        assert requirement.label_ar.strip() and requirement.label_en.strip()
        assert any("؀" <= ch <= "ۿ" for ch in requirement.label_ar)
        assert requirement.gate is None or requirement.gate.startswith("G")


def test_quantitative_requirements_match_the_spec():
    """§16.1 — العناصر المذكورة في الوثيقة حاضرة."""
    keys = {r.key for r in methodology.REQUIREMENTS["quantitative"]}
    assert {"variables", "conceptual_model", "hypotheses", "operational_definitions",
            "population", "sample_size_justification", "instrument",
            "reliability_validity", "analysis_plan"} <= keys


def test_qualitative_requirements_match_the_spec():
    """§16.2."""
    keys = {r.key for r in methodology.REQUIREMENTS["qualitative"]}
    assert {"design_type", "participant_selection", "interview_guide", "saturation",
            "codebook", "analysis_approach", "reflexivity"} <= keys


def test_review_requires_a_protocol_before_anything_else():
    """§16.5 — بروتوكول المراجعة شرط بوابة G2."""
    protocol = next(r for r in methodology.REQUIREMENTS["review"] if r.key == "protocol")
    assert protocol.is_blocking and protocol.gate == "G2"


def test_missing_blocking_requirements_are_reported():
    """AT-S5-10 — الناقص يُعلَن، لا يُفترض مكتملًا."""
    gaps = methodology.evaluate("quantitative", set())
    assert not gaps.is_complete
    assert "analysis_plan" in {r.key for r in gaps.missing_blocking}

    satisfied = {r.key for r in methodology.REQUIREMENTS["quantitative"] if r.is_blocking}
    complete = methodology.evaluate("quantitative", satisfied)
    assert complete.is_complete
    # الإرشادي الناقص لا يمنع الاكتمال لكنه يبقى معروضًا.
    assert complete.missing_advisory


def test_advisory_requirements_never_block():
    for study_type, requirements in methodology.REQUIREMENTS.items():
        advisory = {r.key for r in requirements if not r.is_blocking}
        gaps = methodology.evaluate(
            study_type, {r.key for r in requirements if r.is_blocking}
        )
        assert gaps.is_complete
        assert {r.key for r in gaps.missing_advisory} == advisory


def test_unknown_study_type_is_refused_not_defaulted():
    with pytest.raises(ValueError):
        methodology.evaluate("astrology", set())


def test_adding_a_design_is_data_not_logic():
    """§3 نفسه: تصميم جديد إضافةُ بيانات لا تعديل منطق."""
    import inspect

    source = inspect.getsource(methodology.evaluate)
    for study_type in methodology.REQUIREMENTS:
        assert study_type not in source, (
            f"'{study_type}' is hard-coded in the evaluator instead of read from the table"
        )
