"""AT-S8-01…06 — سلسلة البيانات وقفل الخطة وإعادة الإنتاج (§17، §18.1، TC-07)."""
import datetime as dt

import pytest

from athera_api.services.analysis import lineage, plan, reproducibility, vocab

NOW = dt.datetime(2026, 8, 30, tzinfo=dt.UTC)


def _raw() -> lineage.DatasetVersion:
    return lineage.DatasetVersion(
        version_id="v1", dataset_id="d1", state="raw",
        label="بيانات الاستبانة الخام", checksum="abc", row_count=214,
    )


def test_cleaning_creates_a_version_and_never_touches_raw():
    """AT-S8-01 / TC-07 — أهم اختبار في هذا السبرنت."""
    raw = _raw()
    cleaned = lineage.derive(
        raw, new_state="cleaned", label="منظَّف v1", checksum="def",
        change_note_ar="حذف الاستجابات الناقصة", row_count=201, version_id="v2",
    )
    assert cleaned.version_id != raw.version_id
    assert cleaned.parent_version_id == raw.version_id
    # الأصل لم يتغير بأي شكل.
    assert raw.checksum == "abc" and raw.row_count == 214 and raw.state == "raw"
    assert raw.is_immutable


def test_the_four_states_and_their_transitions():
    """AT-S8-02 — §17.2."""
    assert set(vocab.DATASET_STATES) == {"raw", "cleaned", "analysis_locked", "derived"}
    assert "raw" not in vocab.ALLOWED_TRANSITIONS["cleaned"]
    assert vocab.ALLOWED_TRANSITIONS["raw"] == frozenset({"cleaned"})


def test_illegal_transitions_and_missing_lineage_are_refused():
    raw = _raw()
    with pytest.raises(lineage.LineageError):
        lineage.derive(raw, new_state="derived", label="x", checksum="y",
                       change_note_ar="قفز", version_id="v3")
    with pytest.raises(lineage.LineageError):
        lineage.DatasetVersion(version_id="v9", dataset_id="d1", state="cleaned",
                               label="x", checksum="y")
    with pytest.raises(lineage.LineageError):
        lineage.DatasetVersion(version_id="v10", dataset_id="d1", state="raw",
                               label="x", checksum="y", parent_version_id="v1")


def test_a_derived_version_must_say_why_it_differs():
    raw = _raw()
    with pytest.raises(lineage.LineageError):
        lineage.derive(raw, new_state="cleaned", label="x", checksum="y",
                       change_note_ar="   ", version_id="v4")


def test_freezing_produces_an_id_and_locks_the_version():
    """AT-S8-03 — §17.3 بوابة G6."""
    cleaned = lineage.derive(_raw(), new_state="cleaned", label="c", checksum="def",
                             change_note_ar="تنظيف", version_id="v2")
    frozen = lineage.freeze(cleaned, at=NOW)
    assert frozen.freeze_id and frozen.freeze_id.startswith("FRZ-")
    assert frozen.state == "analysis_locked"
    assert frozen.is_frozen and frozen.is_immutable

    with pytest.raises(lineage.LineageError):
        lineage.freeze(_raw(), at=NOW)
    with pytest.raises(lineage.LineageError):
        lineage.freeze(frozen, at=NOW)


def test_lineage_traces_back_to_raw():
    raw = _raw()
    cleaned = lineage.derive(raw, new_state="cleaned", label="c", checksum="def",
                             change_note_ar="تنظيف", version_id="v2")
    chain = lineage.LineageChain([raw, lineage.freeze(cleaned, at=NOW)])
    path = chain.path_to_raw("v2")
    assert [v.state for v in path] == ["analysis_locked", "raw"]


# ── AT-S8-05: قفل الخطة والانحراف المُعلَن ──

def _plan() -> plan.AnalysisPlan:
    return plan.AnalysisPlan(plan_id="p1", tests=[
        plan.PlannedTest(test_key="t_reliability", test_kind="reliability",
                         variables=("q1", "q2")),
        plan.PlannedTest(test_key="t_regression", test_kind="regression",
                         variables=("y", "x1")),
    ])


def test_a_run_requires_an_approved_plan():
    with pytest.raises(plan.PlanError):
        plan.classify_run(_plan(), ["t_reliability"])


def test_empty_plans_cannot_be_approved():
    with pytest.raises(plan.PlanError):
        plan.AnalysisPlan(plan_id="p2", tests=[]).approve(by="u", at=NOW)


def test_unplanned_tests_are_disclosed_not_blocked():
    """AT-S8-05 — §51.8: المنع المطلق يدفع للتحايل؛ الإعلان يجعل الاستكشاف مرئيًا."""
    approved = _plan()
    approved.approve(by="u1", at=NOW)

    clean = plan.classify_run(approved, ["t_reliability", "t_regression"])
    assert clean.exploratory_keys == [] and not clean.requires_disclosure

    drifted = plan.classify_run(approved, ["t_reliability", "t_fishing"])
    assert drifted.exploratory_keys == ["t_fishing"]
    assert drifted.requires_disclosure
    assert drifted.planned_not_run == ["t_regression"]
    assert all(c.reason_ar.strip() and c.reason_en.strip() for c in drifted.classifications)


def test_editing_a_plan_after_approval_is_detected():
    approved = _plan()
    approved.approve(by="u1", at=NOW)
    approved.tests.append(plan.PlannedTest(test_key="t_new", test_kind="anova",
                                           variables=("g", "y")))
    assert approved.has_drifted()
    with pytest.raises(plan.PlanError):
        plan.classify_run(approved, ["t_new"])


# ── AT-S8-04/06: بيان إعادة الإنتاج ──

def _full_manifest(seed: int = 42) -> reproducibility.RunManifest:
    return reproducibility.RunManifest(
        code_hash="h1", runtime="python-3.12", packages={"pandas": "2.2.0"},
        dataset_version_id="v2", dataset_freeze_id="FRZ-abc123", random_seed=seed,
    )


def test_incomplete_manifest_is_not_reproducible_and_names_gaps():
    status = reproducibility.assess(
        "run-1", reproducibility.RunManifest(code_hash="h1", runtime="python-3.12")
    )
    assert not status.reproducible
    assert set(status.missing) == {"packages", "dataset_version_id", "random_seed"}
    assert status.detail_ar.strip() and status.detail_en.strip()


def test_a_complete_manifest_on_unfrozen_data_is_still_refused():
    """§17.3 — البيان الكامل لا يكفي إن كانت البيانات متحركة."""
    manifest = _full_manifest()
    manifest.dataset_freeze_id = None
    status = reproducibility.assess("run-2", manifest)
    assert not status.reproducible
    assert "غير مجمَّدة" in status.detail_ar


def test_same_inputs_produce_the_same_fingerprint():
    """AT-S8-06 — إعادة الإنتاج تعني نفس البصمة."""
    first = reproducibility.assess("run-3", _full_manifest())
    second = reproducibility.assess("run-4", _full_manifest())
    assert first.reproducible and first.fingerprint == second.fingerprint

    different = reproducibility.assess("run-5", _full_manifest(seed=7))
    assert first.fingerprint != different.fingerprint


def test_incomplete_manifests_cannot_be_fingerprinted():
    with pytest.raises(reproducibility.ReproducibilityError):
        reproducibility.RunManifest(code_hash="h1").fingerprint()
