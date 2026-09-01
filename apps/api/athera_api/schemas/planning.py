"""عقود تخطيط النشر | Publication planning contracts (S5D)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """دليل واحد بإسناده — والإسناد مقروء من الذاكرة لا منسوخ."""

    memory_id: uuid.UUID
    role: str
    statement_ar: str
    locator: str | None = None
    quote: str | None = None
    source_file_id: uuid.UUID | None = None


class ContextState(BaseModel):
    """حال الأدلة قبل أي نداء — وبوابة الكفاية معلنة فيه."""

    project_id: uuid.UUID
    sufficient: bool
    evidence_count: int
    roles: dict[str, int]
    missing_roles: list[str]
    fingerprint: str
    consent_state: str
    capability: str
    provider: str
    model: str | None = None
    message: str
    # ما يفعله الباحث إن لم تكفِ الأدلة (§10).
    next_steps: list[str] = Field(default_factory=list)


class PlanningConsentDecision(BaseModel):
    decision: str = Field(pattern="^(grant|decline|revoke)$")
    # البصمة التي يوافق عليها — فلا يُؤذن للقطة غير التي رآها.
    context_fingerprint: str = Field(min_length=64, max_length=64)


class OpportunityView(BaseModel):
    id: uuid.UUID
    working_title_ar: str
    working_title_en: str | None = None
    research_question_ar: str | None = None
    opportunity_kind: str
    paper_kind: str
    # دورة إنتاج الورقة — لا قرار الباحث.
    status: str
    # قرار الباحث — عمودٌ آخر لمعنى آخر.
    planning_status: str
    evidence_readiness_score: float | None = None
    literature_validation_status: str
    journal_validation_status: str
    salami_alert: bool
    proposed_contribution_ar: str | None = None
    claim_boundaries_ar: str | None = None
    limitations_ar: str | None = None
    missing_requirements: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    # يُعلَن في العقد نفسه: هذه مقترحات لا حقائق معتمدة.
    proposal_notice: str


class OpportunityList(BaseModel):
    project_id: uuid.UUID
    opportunities: list[OpportunityView]
    generated_at: dt.datetime | None = None
    run_id: uuid.UUID | None = None
    note: str


class PlanningDecision(BaseModel):
    decision: str = Field(pattern="^(select|exclude)$")
    reason: str | None = Field(default=None, max_length=1000)


class EvidenceMapEntry(BaseModel):
    element_id: uuid.UUID | None = None
    element_type: str
    claim_ar: str
    origin: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ThreadIssue(BaseModel):
    check: str
    severity: str
    message_ar: str
    message_en: str | None = None


class ThreadView(BaseModel):
    opportunity_id: uuid.UUID
    elements: list[EvidenceMapEntry]
    issues: list[ThreadIssue]
    blocking: int
    advisory: int
    note: str


class OutlineView(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    article_type: str | None = None
    sections: list[dict]
    status: str
    note: str
