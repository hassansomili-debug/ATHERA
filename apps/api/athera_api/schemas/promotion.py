"""عقود محرك الترقية والمحفظة | Promotion and portfolio contracts (§35.2)."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field


class PolicyImportRequest(BaseModel):
    file_id: uuid.UUID
    policy_name_ar: str = Field(min_length=2, max_length=255)
    policy_name_en: str | None = None
    version_label: str = Field(min_length=1, max_length=32)
    effective_from: dt.date
    target_rank: str | None = None


class PolicyImportResponse(BaseModel):
    policy_id: uuid.UUID
    policy_version_id: uuid.UUID
    rules_proposed: int
    rules_rejected_unquoted: int
    note_ar: str = "كل قاعدة مستوردة غير متحققة حتى تعتمدها بنفسك."
    note_en: str = "Every imported rule stays unverified until you approve it."


class RuleResponse(BaseModel):
    id: uuid.UUID
    rule_type: str
    rule_key: str
    statement: str
    statement_ar: str
    statement_en: str | None
    params: dict
    source_locator: str | None
    source_quote: str | None
    is_blocking: bool
    verification_status: str


class RuleVerifyRequest(BaseModel):
    params: dict | None = None
    is_blocking: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)


class UnitContributionResponse(BaseModel):
    publication_id: str
    contribution: float
    explanation: str


class RuleEvaluationResponse(BaseModel):
    rule_id: str
    rule_type: str
    rule_key: str
    status: str
    required: Any = None
    actual: Any = None
    is_blocking: bool
    explanation: str
    explanation_ar: str
    explanation_en: str
    contributions: list[UnitContributionResponse] = []


class CaseResponse(BaseModel):
    """§27.2 — عدّادات لا نسبة. تفصيل القواعد جزء من الإجابة لا ملحق بها."""

    policy_version_id: uuid.UUID | None
    computed_at: dt.datetime
    units_total: float | None
    units_computable: bool
    rules_met: int
    rules_blocking: int
    rules_needing_verification: int
    is_ready: bool
    evaluations: list[RuleEvaluationResponse]
    note_ar: str = "لا تُعرض نسبة جاهزية واحدة: نسبة مرتفعة قد تخفي شرطًا حاجبًا."
    note_en: str = "No single readiness percentage is shown: a high score can hide a blocking gap."


class PlannedWorkRequest(BaseModel):
    title: str = Field(min_length=2, max_length=512)
    author_count: int = Field(default=1, ge=1, le=50)
    author_position: int = Field(default=1, ge=1, le=50)
    is_corresponding: bool = True
    indexes: list[str] = []
    journal_name: str | None = None
    is_thesis_derived: bool = False
    expected_on: dt.date | None = None


class ScenarioRequest(BaseModel):
    kind: str = Field(pattern="^(minimum|safe|ambitious|rejection_impact|indexing_change)$")
    planned_works: list[PlannedWorkRequest] = []


class ScenarioResponse(BaseModel):
    kind: str
    is_projection: bool = True
    assumptions: list[str]
    assumptions_ar: list[str]
    assumptions_en: list[str]
    baseline: CaseResponse
    projected: CaseResponse
    added_works: int


class ProjectCreateRequest(BaseModel):
    """§12.2 — حقول المشروع."""

    working_title_ar: str = Field(min_length=2)
    working_title_en: str | None = None
    program_id: uuid.UUID | None = None
    study_type: str | None = None
    expected_units: float | None = Field(default=None, ge=0, le=10)
    target_journal_name: str | None = None
    target_index_tier: str | None = None
    intended_author_count: int | None = Field(default=None, ge=1, le=50)
    intended_author_position: int | None = Field(default=None, ge=1, le=50)
    risks: list[str] | None = None
    target_date: dt.date | None = None
    is_thesis_derived: bool = False


class ProjectResponse(BaseModel):
    id: uuid.UUID
    working_title: str
    working_title_ar: str
    working_title_en: str | None
    program_id: uuid.UUID | None
    study_type: str | None
    status: str
    expected_units: float | None
    target_journal_name: str | None
    target_index_tier: str | None
    risks: list[str] | None
    target_date: dt.date | None
    current_gate: str | None
    is_thesis_derived: bool
