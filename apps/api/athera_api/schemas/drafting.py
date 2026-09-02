"""عقود صياغة أقسام المخطوطة | Manuscript drafting contracts (S5E-B)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ManuscriptFromOpportunityRequest(BaseModel):
    project_id: uuid.UUID
    opportunity_id: uuid.UUID
    title_ar: str | None = Field(default=None, min_length=3, max_length=500)
    language: str = Field(default="ar", pattern="^(ar|en)$")


class EvidenceRef(BaseModel):
    memory_id: uuid.UUID
    role: str
    statement_ar: str
    locator: str | None = None
    quote: str | None = None


class DraftingContextResponse(BaseModel):
    manuscript_id: uuid.UUID
    section_key: str
    sufficient: bool
    evidence_count: int
    roles: dict[str, int]
    missing_roles: list[str]
    thread_elements: int
    fingerprint: str
    consent_state: str
    capability: str
    provider: str
    model: str | None
    evidence: list[EvidenceRef]
    message: str
    next_steps: list[str] = Field(default_factory=list)


class DraftingConsentDecision(BaseModel):
    decision: str = Field(pattern="^(grant|decline|revoke)$")
    context_fingerprint: str = Field(min_length=64, max_length=64)


class ClaimView(BaseModel):
    id: uuid.UUID
    text_ar: str
    claim_type: str
    status: str
    is_labelled_inference: bool
    evidence: list[EvidenceRef] = Field(default_factory=list)
    analysis_output_ids: list[uuid.UUID] = Field(default_factory=list)


class DraftIssueView(BaseModel):
    issue_key: str
    section_key: str
    severity: str
    message_ar: str
    message_en: str
    excerpt: str | None = None
    claim_index: int | None = None


class SectionView(BaseModel):
    manuscript_id: uuid.UUID
    version_label: str
    section_key: str
    text_ar: str | None
    text_en: str | None
    review_status: str
    reviewed_at: dt.datetime | None
    fingerprint: str | None
    claims: list[ClaimView] = Field(default_factory=list)
    issues: list[DraftIssueView] = Field(default_factory=list)
    blocking: int = 0
    missing_evidence: list[str] = Field(default_factory=list)
    note: str


class SectionReviewDecision(BaseModel):
    decision: str = Field(pattern="^(approve|request_revision)$")
    reason: str | None = Field(default=None, max_length=1000)


__all__ = ["ClaimView", "DraftIssueView", "DraftingConsentDecision",
           "DraftingContextResponse", "EvidenceRef",
           "ManuscriptFromOpportunityRequest", "SectionReviewDecision", "SectionView"]
