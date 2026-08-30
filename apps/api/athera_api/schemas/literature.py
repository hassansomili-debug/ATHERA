"""عقود الأدبيات والأدلة | Literature and evidence contracts (§35.4)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class SourceSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=20, ge=1, le=50)


class SourceCandidate(BaseModel):
    """نتيجة بحث — ليست مصدرًا مخزَّنًا بعد."""

    registry: str
    registry_id: str
    doi: str | None
    title: str
    publication_year: int | None
    journal_name: str | None
    authors: list[str]
    retraction_status: str
    access_state: str


class SourceImportRequest(BaseModel):
    doi: str = Field(min_length=5, max_length=255)


class SourceResponse(BaseModel):
    """§14.3 — الحقول الثلاثة عشر."""

    id: uuid.UUID
    doi: str | None
    title: str
    publication_year: int | None
    journal_name: str | None
    authors: list[str] = []
    theory: str | None
    method: str | None
    sample: str | None
    findings: str | None
    limitations: str | None
    retraction_status: str
    retraction_detail: str | None
    access_state: str
    last_verified_at: dt.datetime | None
    registry: str | None
    verification_status: str
    can_carry_excerpt: bool


class ExcerptCreateRequest(BaseModel):
    source_id: uuid.UUID
    quote: str = Field(min_length=10, max_length=5000)
    locator: str = Field(min_length=1, max_length=255)


class ExcerptResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    quote: str
    locator: str
    access_basis: str


class ClaimCreateRequest(BaseModel):
    text_ar: str = Field(min_length=5)
    text_en: str | None = None
    claim_type: str = Field(pattern="^(empirical|theoretical|contextual|interpretive)$")
    section: str | None = None
    project_id: uuid.UUID | None = None


class EvidenceLinkRequest(BaseModel):
    excerpt_id: uuid.UUID
    support_level: str = Field(pattern="^(direct|partial|contextual|contradictory)$")
    retraction_acknowledged: bool = False
    acknowledgement_note: str | None = None


class ClaimStatusResponse(BaseModel):
    claim_id: uuid.UUID
    status: str
    direct: int
    partial: int
    contextual: int
    contradictory: int
    unresolved_contradictions: int
    retracted_sources: int
    has_evidence_gap: bool
    can_be_final: bool


class ClaimResponse(BaseModel):
    id: uuid.UUID
    text: str
    text_ar: str
    text_en: str | None
    claim_type: str
    section: str | None
    status: str
    verification_status: str
    is_labelled_inference: bool
    evidence: ClaimStatusResponse


class LedgerEntry(BaseModel):
    """§14.4 — الشكل المحدد في الوثيقة، بلغتين."""

    claim: str
    claim_ar: str
    claim_type: str
    section: str | None
    evidence_ids: list[uuid.UUID]
    support_levels: list[str]
    verification_status: str
    status: str
    has_evidence_gap: bool
    unresolved_contradictions: int


class LedgerResponse(BaseModel):
    project_id: uuid.UUID | None
    entries: list[LedgerEntry]
    total_claims: int
    claims_with_gaps: int
    claims_contradicted: int
    note_ar: str = "الادعاء بلا دليل يُعلَن فجوة؛ لا يُولَّد له مرجع."
    note_en: str = "A claim without evidence is declared a gap; no reference is generated for it."
