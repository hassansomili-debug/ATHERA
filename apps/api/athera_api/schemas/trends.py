"""عقود الذكاء الاستباقي | Trend intelligence contracts (§51)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class WatchlistCreateRequest(BaseModel):
    watchlist_kind: str = Field(
        pattern="^(personal|project|construct|journal|supervised_thesis|competitive)$"
    )
    name_ar: str = Field(min_length=2)
    name_en: str | None = None
    project_id: uuid.UUID | None = None
    keywords: list[str] = []
    theories: list[str] = []
    methods: list[str] = []
    journal_ids: list[str] = []
    refresh_cron: str | None = None


class WatchlistResponse(BaseModel):
    id: uuid.UUID
    watchlist_kind: str
    kind_label: str
    name: str
    keywords: list[str]
    is_active: bool
    last_refreshed_at: dt.datetime | None


class SignalCreateRequest(BaseModel):
    """§51.11 — لا إشارة يتيمة: المصدر والمعرّف والتاريخ إلزامية."""

    trend_key: str = Field(min_length=2, max_length=128)
    trend_label_ar: str = Field(min_length=2)
    pattern: str
    source_type: str
    source_id: str = Field(min_length=1, max_length=512)
    source_url: str | None = None
    observed_at: dt.datetime
    weight: float = Field(default=1.0, gt=0, le=1)
    watchlist_id: uuid.UUID | None = None
    detail_ar: str | None = None


class ConditionResponse(BaseModel):
    key: str
    satisfied: bool
    actual: float
    required: float
    detail: str


class TrendStrengthResponse(BaseModel):
    """§51.3 — قوة الاتجاه وحدها. لا حقل هنا يقيس قابلية النشر."""

    trend_id: uuid.UUID
    trend_key: str
    status: str
    evidence_weight: float
    signal_count: int
    distinct_sources: int
    span_days: int
    ignored_signals: int
    conditions: list[ConditionResponse]
    unmet_conditions: list[str]
    is_validated: bool
    note_ar: str
    note_en: str


class TimelinePointResponse(BaseModel):
    period: str
    signal_count: int
    weight: float


class OpportunityFitRequest(BaseModel):
    novelty: float | None = None
    momentum: float | None = None
    research_gap: float | None = None
    researcher_fit: float | None = None
    data_feasibility: float | None = None
    journal_fit: float | None = None
    publication_potential: float | None = None
    execution_risk: float | None = None


class FitCriterionResponse(BaseModel):
    key: str
    weight: int
    ratio: float | None
    points: float
    label: str
    rationale: str


class OpportunityFitResponse(BaseModel):
    """§51.3 — ملاءمة الفرصة وحدها. ودرجة مرتفعة مع معيار حاسم صفري لا تكفي."""

    fit_score: float
    criteria: list[FitCriterionResponse]
    uncomputed: list[str]
    blocking_reasons: list[str]
    is_actionable: bool
    note_ar: str
    note_en: str


class CardCreateRequest(BaseModel):
    """§51.4 — لا حقل نص مخطوطة: البطاقة لا تبدأ بالكتابة."""

    trend_id: uuid.UUID
    working_title_ar: str = Field(min_length=3)
    central_question_ar: str = Field(min_length=5)
    trend_summary_ar: str = Field(min_length=5)
    gap_ar: str = Field(min_length=5)
    gap_confidence: float = Field(ge=0, le=1)
    evidence_signal_ids: list[uuid.UUID] = Field(min_length=1)
    proposed_theory_ar: str | None = None
    proposed_method_ar: str | None = None
    required_data_ar: str | None = None
    data_is_available: bool | None = None
    candidate_journal_ids: list[str] = []
    execution_risk_ar: str | None = None
    estimated_months: int | None = None
    fit: OpportunityFitRequest | None = None


class CardResponse(BaseModel):
    id: uuid.UUID
    trend_id: uuid.UUID
    working_title_ar: str
    central_question_ar: str
    gap_ar: str
    gap_confidence: float
    fit_score: float | None
    blocking_reasons: list[str]
    is_actionable: bool
    approved_at: dt.datetime | None
    converted_project_id: uuid.UUID | None
    evidence_count: int


class StageResponse(BaseModel):
    stage: str
    label: str
    completed: bool


class PipelineResponse(BaseModel):
    """§51.5/§51.6 — الهدف Ready for Submission لا النشر."""

    card_id: uuid.UUID
    current_stage: str
    stages: list[StageResponse]
    ready_conditions: dict[str, bool]
    unmet_conditions: list[str]
    unmet_labels: list[str]
    is_ready_for_submission: bool
    note_ar: str = "الحالة الرسمية Ready for Submission؛ لا ضمان قبول ولا «جاهزة للنشر»."
    note_en: str = "The official status is Ready for Submission; acceptance is never guaranteed."


class PipelineUpdateRequest(BaseModel):
    completed_stages: list[str] = []
    ready_conditions: dict[str, bool] = {}


class SubmissionAuthorizeRequest(BaseModel):
    human_act: bool = False
    delegation_id: uuid.UUID | None = None


class SubmissionDecisionResponse(BaseModel):
    allowed: bool
    basis: str
    unmet_conditions: list[str]
    reason: str
    reason_ar: str
    reason_en: str

class BriefItemInput(BaseModel):
    """§51.9 — لا بند بلا مرجع يسنده."""

    item_key: str = Field(min_length=1, max_length=128)
    title_ar: str = Field(min_length=2)
    evidence_ref: str = Field(min_length=1, max_length=512)
    detail_ar: str | None = None


class BriefCreateRequest(BaseModel):
    cadence: str
    period_start: dt.datetime
    period_end: dt.datetime
    new_trends: list[BriefItemInput] = []
    score_changes: list[BriefItemInput] = []
    new_cards: list[BriefItemInput] = []
    alerts: list[BriefItemInput] = []


class BriefResponse(BaseModel):
    id: uuid.UUID
    cadence: str
    cadence_label: str
    period_start: dt.datetime
    period_end: dt.datetime
    new_trends: list[BriefItemInput]
    score_changes: list[BriefItemInput]
    new_cards: list[BriefItemInput]
    alerts: list[BriefItemInput]
    is_empty: bool
    summary: str
    seen_at: dt.datetime | None
    acknowledged_at: dt.datetime | None


class NoveltyCheckRequest(BaseModel):
    """§51.10 — التشابه رقم، و«منشور أم لا» هو ما يحوّله إلى حكم."""

    similarity: float = Field(ge=0.0, le=1.0)
    published_source_id: uuid.UUID | None = None
    note_ar: str | None = None


class NoveltyCheckResponse(BaseModel):
    id: uuid.UUID
    card_id: uuid.UUID
    similarity: float
    is_blocking: bool
    needs_review: bool
    reason: str
    decision: str | None
    checked_at: dt.datetime


class NoveltyDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(distinct|overlapping|abandon)$")
    note_ar: str = Field(min_length=3, max_length=2000)
