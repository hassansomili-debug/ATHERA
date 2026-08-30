"""عقود فريق المشروع | Project team contracts (§12، §24)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class MemberCreateRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=255)
    user_id: uuid.UUID | None = None
    role: str = Field(default="co_author")
    credit_roles: list[str] = []


class MemberResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    display_name: str
    user_id: uuid.UUID | None
    role: str
    role_label: str
    credit_roles: list[str]
    credit_labels: list[str]
    consent_recorded_at: dt.datetime | None


class DecisionCreateRequest(BaseModel):
    decision_kind: str
    statement_ar: str = Field(min_length=3)
    statement_en: str | None = None
    gate: str | None = None
    supersedes_id: uuid.UUID | None = None


class DecisionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    decision_kind: str
    kind_label: str
    statement: str
    gate: str | None
    approval_id: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_at: dt.datetime | None
    supersedes_id: uuid.UUID | None
    is_superseded: bool


class VocabularyResponse(BaseModel):
    """المفردات التي تحتاجها الواجهة لتبني قوائمها بلا تكرارها في الشاشة."""

    key: str
    label: str
