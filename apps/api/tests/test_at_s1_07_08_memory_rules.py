"""AT-S1-07/08 — فئات الذاكرة، ومسارات §7.4، والاستقلال عن المزود."""
import pytest

from athera_api.models.research import MEMORY_CATEGORIES, PROMOTION_PATHS


def test_all_eight_memory_categories_from_spec_are_present():
    """§7.3 — الفئات الثماني، بلا نقصان ولا اختراع فئة تاسعة."""
    expected = {
        "researcher_fact", "promotion_policy", "verified_evidence", "project_decision",
        "working_hypothesis", "journal_fact", "analysis_result", "temporary_context",
    }
    assert set(MEMORY_CATEGORIES) == expected


def test_every_category_declares_its_required_verification():
    for category, requirement in MEMORY_CATEGORIES.items():
        assert requirement, f"{category} has no declared verification requirement"


def test_only_four_promotion_paths_exist():
    """§7.4 — أربعة مسارات لا خامس لها."""
    assert set(PROMOTION_PATHS) == {"external_source", "upload", "analysis_run", "user_statement"}
    assert len(PROMOTION_PATHS) == 4


def test_model_output_is_not_a_promotion_path():
    """أهم سطر في هذا الملف: مخرج النموذج ليس مسارًا إلى الذاكرة الموثقة."""
    assert "model_output" not in PROMOTION_PATHS
    assert "model" not in PROMOTION_PATHS


@pytest.mark.asyncio
async def test_full_pipeline_runs_with_null_provider():
    """AT-S1-08 — خط الأنابيب كامل بلا أي مزود نموذج (§4 Provider Independent)."""
    from athera_api.config import get_settings
    from athera_api.services.extraction.rules import RuleBasedExtractor
    from athera_api.services.parsing import parse_text

    assert get_settings().model_provider == "null"

    document = (
        "السيرة الذاتية\n\n"
        "الرتبة الحالية: أستاذ مشارك في قسم الإعلان والاتصال التسويقي.\n\n"
        "المهارات\n\n"
        "يجيد الباحث استخدام SPSS وSmartPLS، وتدرّب على NVivo، ويستخدم PLS-SEM."
    ).encode("utf-8")

    chunks = parse_text(document)
    result = await RuleBasedExtractor().propose(chunks)
    found = {candidate.value.get("name") for candidate in result.candidates if candidate.value}
    assert {"SPSS", "SmartPLS", "NVivo"} <= found
    assert result.model_run_id is None
