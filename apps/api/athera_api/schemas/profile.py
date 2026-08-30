"""عقود ملف الباحث والذاكرة | Profile, facts and memory contracts (§35.1)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    institution: str | None
    institution_ar: str | None
    institution_en: str | None
    current_rank: str | None
    target_rank: str | None
    primary_field: str | None
    keywords: list[str] | None
    orcid: str | None
    g0_approved_at: dt.datetime | None
    verified_memory_count: int


class ProfilePatch(BaseModel):
    institution_ar: str | None = None
    institution_en: str | None = None
    college_ar: str | None = None
    college_en: str | None = None
    department_ar: str | None = None
    department_en: str | None = None
    current_rank: str | None = None
    target_rank: str | None = None
    primary_field_ar: str | None = None
    primary_field_en: str | None = None
    keywords: list[str] | None = None
    orcid: str | None = Field(default=None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    excluded_topics: list[str] | None = None
    future_interests: list[str] | None = None


class ImportRequest(BaseModel):
    file_id: uuid.UUID
    extractor: str = Field(default="rules", pattern="^(rules|model)$")


class ImportResponse(BaseModel):
    extraction_run_id: uuid.UUID
    chunks_parsed: int
    candidates_proposed: int
    candidates_rejected_unquoted: int
    extractor: str
    note_ar: str = "كل ما استُخرج مرشّحات غير متحققة تنتظر اعتمادك."
    note_en: str = "Everything extracted is an unverified candidate awaiting your approval."


class FactCandidateResponse(BaseModel):
    """§10.2 — Fact · Source File · Page/Section · Confidence · Status."""

    id: uuid.UUID
    memory_category: str
    field_key: str | None
    statement: str
    statement_ar: str
    statement_en: str | None
    quote: str
    locator: str
    file_id: uuid.UUID
    confidence: float | None
    status: str
    decided_at: dt.datetime | None
    decision_reason: str | None


class DecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class MemoryResponse(BaseModel):
    id: uuid.UUID
    memory_category: str
    statement: str
    statement_ar: str
    statement_en: str | None
    value: dict | None
    source_type: str
    source_locator: str | None
    source_quote: str | None
    verification_status: str
    verified_at: dt.datetime | None
