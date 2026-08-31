"""مجلس المحكّمين الافتراضي | Virtual peer review council (§21).

القاعدة الحاكمة: «لا يجوز للمراجع الافتراضي تعديل النسخة المعتمدة مباشرة؛
يقترح Patch ويحتاج اعتمادًا».

التنفيذ بنيوي: `ReviewerReport` **لا يحمل نصًا معدَّلًا** — يحمل ملاحظات
ورقعًا مقترحة. ولا دالة في هذه الوحدة تعيد قسمًا مكتوبًا: الكتابة مسار
منفصل يحتاج فاعلًا بشريًا وينشئ نسخة جديدة.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .vocab import READINESS_STATUSES, REVIEWER_ROLES

SEVERITIES = ("major", "minor")


@dataclass(frozen=True, slots=True)
class ReviewNote:
    severity: str
    section_key: str
    text_ar: str
    text_en: str

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")


@dataclass(frozen=True, slots=True)
class ProposedPatch:
    """رقعة مقترحة — نص **مقترح** لا نص مطبَّق.

    `status` يبدأ `proposed` دائمًا ولا يملك هذا الكائن مسارًا لتغييره:
    التطبيق قرار خارجه.
    """

    section_key: str
    rationale_ar: str
    rationale_en: str
    suggested_text_ar: str | None = None
    status: str = "proposed"

    def __post_init__(self) -> None:
        if self.status != "proposed":
            raise ValueError("a patch is always created as 'proposed' (§21)")


@dataclass(slots=True)
class ReviewerReport:
    """§21.1 — تقرير مراجع واحد بأقسامه الستة."""

    reviewer_role: str
    strengths: list[str] = field(default_factory=list)
    major_concerns: list[ReviewNote] = field(default_factory=list)
    minor_concerns: list[ReviewNote] = field(default_factory=list)
    potential_rejection_reasons: list[str] = field(default_factory=list)
    required_changes: list[ProposedPatch] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.reviewer_role not in REVIEWER_ROLES:
            raise ValueError(f"unknown reviewer role: {self.reviewer_role}")

    @property
    def has_edits(self) -> bool:
        """حارس: التقرير لا يحمل نصًا مطبَّقًا، بل رقعًا مقترحة فقط."""
        return any(patch.status != "proposed" for patch in self.required_changes)


@dataclass(slots=True)
class CouncilReport:
    reports: list[ReviewerReport]
    readiness_status: str = field(init=False)
    major_count: int = field(init=False)
    minor_count: int = field(init=False)
    rejection_reasons: list[str] = field(init=False)
    patches: list[ProposedPatch] = field(init=False)
    status_label_ar: str = field(init=False)
    status_label_en: str = field(init=False)
    note_ar: str = field(
        default="المراجعة تقترح ولا تعدّل؛ كل رقعة تحتاج اعتمادًا بشريًا (§21).", init=False
    )
    note_en: str = field(
        default="The council proposes and never edits; every patch needs human approval (§21).",
        init=False,
    )

    def __post_init__(self) -> None:
        self.major_count = sum(len(r.major_concerns) for r in self.reports)
        self.minor_count = sum(len(r.minor_concerns) for r in self.reports)
        self.rejection_reasons = [
            reason for report in self.reports for reason in report.potential_rejection_reasons
        ]
        self.patches = [patch for report in self.reports for patch in report.required_changes]
        self.readiness_status = classify(
            major=self.major_count, minor=self.minor_count,
            rejection_reasons=len(self.rejection_reasons),
        )
        self.status_label_ar, self.status_label_en = READINESS_STATUSES[self.readiness_status]

    @property
    def reviewers_missing(self) -> list[str]:
        """§21 — المجلس خمسة أدوار؛ غياب أحدها معلومة لا تفصيل."""
        covered = {report.reviewer_role for report in self.reports}
        return sorted(set(REVIEWER_ROLES) - covered)


def classify(*, major: int, minor: int, rejection_reasons: int) -> str:
    """§21.1 — حالات الجاهزية الأربع.

    سبب رفض محتمل واحد يكفي لـ«غير جاهزة»: القارئ الذي يرى سببًا للرفض
    ليس مطمئنًا مهما قلّت الملاحظات الأخرى.
    """
    if rejection_reasons > 0:
        return "not_ready"
    if major > 0:
        return "major_revision"
    if minor > 0:
        return "minor_revision"
    return "ready_to_submit"


def assemble(reports: list[ReviewerReport]) -> CouncilReport:
    for report in reports:
        if report.has_edits:
            raise ValueError("a reviewer report may not carry applied edits (§21)")
    return CouncilReport(reports=reports)


def package_gaps(
    present_items: set[str], *, optional_items: frozenset[str]
) -> tuple[list[str], list[str]]:
    """§22.1 — ما ينقص من حزمة التقديم: إلزامي ثم اختياري."""
    from .vocab import SUBMISSION_PACKAGE_ITEMS

    missing_required = sorted(
        key for key in SUBMISSION_PACKAGE_ITEMS
        if key not in present_items and key not in optional_items
    )
    missing_optional = sorted(
        key for key in SUBMISSION_PACKAGE_ITEMS
        if key not in present_items and key in optional_items
    )
    return missing_required, missing_optional
