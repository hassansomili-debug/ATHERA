"""AT-S7-07…11 — جاهزية المخطوطة ومجلس المحكّمين (§19.2، §21، §22.1)."""
import pytest

from athera_api.services.publishing import manuscript, review, vocab

REQUIRED = ["title", "abstract", "introduction", "method", "results",
            "discussion", "conclusion", "references"]


def _sections(**overrides) -> list[manuscript.SectionState]:
    states = []
    for key in REQUIRED:
        if key in overrides:
            states.append(overrides[key])
        else:
            states.append(manuscript.SectionState(section_key=key, text="نص"))
    return states


def test_claim_without_evidence_blocks_g9_and_is_named():
    """AT-S7-07 — §19.2 القاعدة 1."""
    result = manuscript.evaluate(_sections(
        introduction=manuscript.SectionState(
            section_key="introduction", text="نص المقدمة",
            claim_ids=frozenset({"c1", "c2"}), supported_claim_ids=frozenset({"c1"}),
        )
    ))
    assert not result.can_pass_g9
    issue = next(i for i in result.issues if i.issue_key == "claim_without_evidence")
    assert issue.section_key == "introduction"
    assert "c2" in issue.detail_ar
    assert issue.detail_en.strip()


def test_supported_claims_pass():
    result = manuscript.evaluate(_sections(
        introduction=manuscript.SectionState(
            section_key="introduction", text="نص", claim_ids=frozenset({"c1"}),
            supported_claim_ids=frozenset({"c1"}),
        )
    ))
    assert result.can_pass_g9


@pytest.mark.parametrize(
    "text",
    [
        "أظهرت النتائج أن p = 0.03 وهو دال.",
        "معامل المسار β = 0.42.",
        "بلغت R² = 0.61.",
        "F(2, 197) = 8.1.",
        "The model reported AVE = 0.58.",
    ],
)
def test_statistics_without_an_analysis_run_block_g9(text):
    """AT-S7-08 — §19.2 القاعدة 2."""
    result = manuscript.evaluate(_sections(
        results=manuscript.SectionState(section_key="results", text=text)
    ))
    assert any(i.issue_key == "result_without_analysis_run" for i in result.issues)
    assert not result.can_pass_g9


def test_statistics_pass_when_linked_to_a_run():
    result = manuscript.evaluate(_sections(
        results=manuscript.SectionState(
            section_key="results", text="أظهرت النتائج أن p = 0.03.",
            analysis_run_ids=frozenset({"run-1"}),
        )
    ))
    assert result.can_pass_g9


def test_ordinary_numbers_are_not_flagged():
    """الحد الآخر: عدد المبحوثين والسنة ليسا ادعاء نتيجة."""
    result = manuscript.evaluate(_sections(
        results=manuscript.SectionState(section_key="results",
                                        text="شارك 214 مبحوثًا في عام 2026.")
    ))
    assert result.can_pass_g9


def test_missing_and_unknown_sections_are_named():
    incomplete = manuscript.evaluate([manuscript.SectionState(section_key="title", text="عنوان")])
    assert len(incomplete.missing_sections) >= 6
    assert not incomplete.can_pass_g9

    unknown = manuscript.evaluate(
        [*_sections(), manuscript.SectionState(section_key="acknowledgements", text="شكر")]
    )
    assert any(i.issue_key == "unknown_section" for i in unknown.issues)


# ── AT-S7-09/10: المراجعة تقترح ولا تعدّل (§21) ──

def test_a_patch_is_always_born_proposed():
    patch = review.ProposedPatch(section_key="method", rationale_ar="أضف حساب العينة",
                                 rationale_en="Add a sample size calculation")
    assert patch.status == "proposed"

    with pytest.raises(ValueError):
        review.ProposedPatch(section_key="method", rationale_ar="x", rationale_en="x",
                             status="applied")


def test_a_reviewer_report_may_not_carry_applied_edits():
    report = review.ReviewerReport(
        reviewer_role="methodological",
        major_concerns=[review.ReviewNote(severity="major", section_key="method",
                                          text_ar="حجم العينة غير مبرر",
                                          text_en="Sample size is unjustified")],
        required_changes=[review.ProposedPatch(section_key="method", rationale_ar="أضف",
                                               rationale_en="Add")],
    )
    assert not report.has_edits
    assert review.assemble([report]).patches


def test_the_review_module_exposes_no_writing_path():
    """§21 — لا دالة هنا تكتب في قسم؛ التطبيق مسار منفصل بفاعل بشري."""
    exported = [name for name in dir(review) if not name.startswith("_")]
    assert not [name for name in exported if name.startswith(("apply", "write", "edit"))]


def test_unknown_reviewer_role_and_severity_are_refused():
    with pytest.raises(ValueError):
        review.ReviewerReport(reviewer_role="astrologer")
    with pytest.raises(ValueError):
        review.ReviewNote(severity="catastrophic", section_key="method",
                          text_ar="x", text_en="x")


# ── AT-S7-11: حالات الجاهزية وحزمة التقديم ──

@pytest.mark.parametrize(
    ("major", "minor", "rejections", "expected"),
    [
        (0, 0, 1, "not_ready"),
        (5, 5, 1, "not_ready"),
        (1, 0, 0, "major_revision"),
        (0, 1, 0, "minor_revision"),
        (0, 0, 0, "ready_to_submit"),
    ],
)
def test_readiness_classification(major, minor, rejections, expected):
    """سبب رفض واحد يكفي لـ«غير جاهزة» مهما قلّت الملاحظات الأخرى."""
    assert review.classify(major=major, minor=minor, rejection_reasons=rejections) == expected


def test_council_reports_missing_reviewers():
    """§21 — المجلس خمسة أدوار؛ غياب أحدها معلومة."""
    council = review.assemble([review.ReviewerReport(reviewer_role="editorial")])
    assert len(council.reviewers_missing) == 4
    assert council.status_label_ar.strip() and council.status_label_en.strip()
    assert council.note_ar.strip() and council.note_en.strip()


def test_submission_package_gaps_separate_required_from_optional():
    """§22.1 — الاختياري لا يمنع الحزمة."""
    required, optional = review.package_gaps(set(), optional_items=vocab.OPTIONAL_PACKAGE_ITEMS)
    assert len(required) == len(vocab.SUBMISSION_PACKAGE_ITEMS) - len(vocab.OPTIONAL_PACKAGE_ITEMS)
    assert set(optional) == set(vocab.OPTIONAL_PACKAGE_ITEMS)

    complete, _ = review.package_gaps(set(vocab.SUBMISSION_PACKAGE_ITEMS),
                                      optional_items=vocab.OPTIONAL_PACKAGE_ITEMS)
    assert complete == []
