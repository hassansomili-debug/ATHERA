"""عقود المخطوطة والمجلات والمراجعة | Publishing contracts (§19، §20، §21، §22)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ManuscriptCreateRequest(BaseModel):
    project_id: uuid.UUID
    title_ar: str = Field(min_length=3)
    title_en: str | None = None
    language: str = Field(default="ar", pattern="^(ar|en)$")


class SectionUpsertRequest(BaseModel):
    section_key: str
    text_ar: str | None = None
    text_en: str | None = None
    claim_ids: list[str] = []
    supported_claim_ids: list[str] = []
    analysis_run_ids: list[str] = []


class ReadinessIssueResponse(BaseModel):
    section_key: str
    issue_key: str
    detail: str
    detail_ar: str
    detail_en: str
    excerpt: str | None


class ManuscriptReadinessResponse(BaseModel):
    """§19.2 — الجاهزية تُقاس بغياب الادعاءات بلا سند، لا باكتمال النص."""

    manuscript_id: uuid.UUID
    can_pass_g9: bool
    issues: list[ReadinessIssueResponse]
    missing_sections: list[str]
    sections_checked: int
    note: str
    note_ar: str
    note_en: str


class ManuscriptResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    title_ar: str
    language: str
    status: str
    current_version_label: str | None
    g9_approved_at: dt.datetime | None


class VersionCreateRequest(BaseModel):
    version_label: str = Field(min_length=1, max_length=32)
    change_reason_ar: str = Field(min_length=3)


class JournalMatchRequest(BaseModel):
    manuscript_id: uuid.UUID
    keywords: list[str] = []
    method_keys: list[str] = []
    required_tier: str | None = Field(default=None, pattern="^[ABCDX]$")
    max_apc_usd: float | None = None
    requires_open_access: bool = False


class CriterionResponse(BaseModel):
    key: str
    weight: int
    ratio: float | None
    points: float
    label: str
    detail: str


class JournalMatchResponse(BaseModel):
    """§20.4 — لا حقل لاحتمال قبول: الضمانة بغياب المكان لا بفحص نصي."""

    journal_id: uuid.UUID
    journal_name: str
    trust_tier: str
    trust_tier_label: str
    meets_strict_wos: bool
    fit_score: float
    criteria: list[CriterionResponse]
    blockers: list[str]
    uncomputed: list[str]
    stale_indexes: list[str]
    note: str
    note_ar: str
    note_en: str


class IndexingVerifyRequest(BaseModel):
    verification_point: str = Field(pattern="^(shortlisting|submission|acceptance|publication)$")


class IndexingVerifyResponse(BaseModel):
    journal_id: uuid.UUID
    verification_point: str
    requires_reverification: bool
    outcome: str
    checked_at: dt.datetime
    note_ar: str
    note_en: str


class ReviewNoteInput(BaseModel):
    severity: str = Field(pattern="^(major|minor)$")
    section_key: str
    text_ar: str
    text_en: str


class PatchInput(BaseModel):
    section_key: str
    rationale_ar: str
    rationale_en: str
    suggested_text_ar: str | None = None


class ReviewerReportInput(BaseModel):
    reviewer_role: str = Field(
        pattern="^(theoretical|methodological|statistical|editorial|integrity)$"
    )
    strengths: list[str] = []
    major_concerns: list[ReviewNoteInput] = []
    minor_concerns: list[ReviewNoteInput] = []
    potential_rejection_reasons: list[str] = []
    required_changes: list[PatchInput] = []


class InternalReviewRequest(BaseModel):
    version_id: uuid.UUID
    reports: list[ReviewerReportInput] = Field(min_length=1)


class PatchResponse(BaseModel):
    id: uuid.UUID
    section_key: str
    rationale_ar: str
    suggested_text_ar: str | None
    status: str


class ReviewRoundResponse(BaseModel):
    """§21 — المجلس يقترح رقعًا ولا يعدّل نسخة معتمدة."""

    id: uuid.UUID
    round_number: int
    readiness_status: str
    readiness_label: str
    major_count: int
    minor_count: int
    reviewers_missing: list[str]
    patches: list[PatchResponse]
    note_ar: str
    note_en: str


class PatchApplyRequest(BaseModel):
    new_version_label: str = Field(min_length=1, max_length=32)
    change_reason_ar: str = Field(min_length=3)


class PackageItemResponse(BaseModel):
    key: str
    label: str
    present: bool
    is_optional: bool


class SubmissionPackageResponse(BaseModel):
    """§22.1 — «مكتملة» تعني فعلًا لا عنصر إلزاميًا ناقصًا."""

    manuscript_id: uuid.UUID
    items: list[PackageItemResponse]
    missing_required: list[str]
    missing_optional: list[str]
    is_complete: bool
