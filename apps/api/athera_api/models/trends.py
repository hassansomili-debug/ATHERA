"""الذكاء الاستباقي | Proactive trend intelligence models (§51)."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..services.trends.vocab import (  # noqa: F401 — إعادة تصدير مقصودة
    DETECTION_PATTERNS,
    OPPORTUNITY_CRITERIA,
    READY_CONDITIONS,
    SIGNAL_SOURCE_TYPES,
    WATCHLIST_KINDS,
)
from .base import Base, TenantScoped, Timestamped, uuid_pk

__all__ = [
    "ResearchWatchlist", "ResearchTrend", "TrendSignalRow", "OpportunityCardRow",
    "OpportunityEvidence", "PaperPipelineRun", "SubmissionDelegationRow",
    "CompetitiveNoveltyCheck", "ResearchIntelligenceBrief",
    "DETECTION_PATTERNS", "WATCHLIST_KINDS", "OPPORTUNITY_CRITERIA",
    "SIGNAL_SOURCE_TYPES", "READY_CONDITIONS",
]


class ResearchWatchlist(Base, TenantScoped, Timestamped):
    """§51.2 — ملف مراقبة. بلا نطاق لا يراقب شيئًا."""

    __tablename__ = "research_watchlists"

    id: Mapped[uuid.UUID] = uuid_pk()
    watchlist_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=True
    )
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    theories: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    methods: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    journal_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    refresh_cron: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_refreshed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ResearchTrend(Base, TenantScoped, Timestamped):
    """§51.1 — «مُصادق عليه» يعني فحصًا مؤرَّخًا بسياسة معلومة، لا وسمًا."""

    __tablename__ = "research_trends"
    __table_args__ = (UniqueConstraint("tenant_id", "trend_key", name="uq_research_trend_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_key: Mapped[str] = mapped_column(String(128), nullable=False)
    label_ar: Mapped[str] = mapped_column(String(512), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(512), nullable=True)
    field_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discovered_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    evidence_weight: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False, default=0)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    span_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    validation_policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TrendSignalRow(Base, TenantScoped, Timestamped):
    """§51.11 — لا إشارة يتيمة. و§51.1 — مخرَج النموذج لا يُحتسب دليلًا."""

    __tablename__ = "trend_signals"

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_trends.id", ondelete="CASCADE"), nullable=False
    )
    watchlist_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_watchlists.id", ondelete="SET NULL"), nullable=True
    )
    pattern: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(24), nullable=False)
    source_id: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=1.0)
    counts_as_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detail_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class OpportunityCardRow(Base, TenantScoped, Timestamped):
    """§51.4 — لا عمود لنص مخطوطة: «لا تبدأ بالكتابة مباشرة»."""

    __tablename__ = "opportunity_cards"

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_trends.id", ondelete="CASCADE"), nullable=False
    )
    working_title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    central_question_ar: Mapped[str] = mapped_column(Text, nullable=False)
    trend_summary_ar: Mapped[str] = mapped_column(Text, nullable=False)
    gap_ar: Mapped[str] = mapped_column(Text, nullable=False)
    gap_confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    proposed_theory_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_method_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_data_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_is_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    novelty_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_journal_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    execution_risk_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overlap_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    fit_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    fit_criteria: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    blocking_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="SET NULL"), nullable=True
    )


class OpportunityEvidence(Base, TenantScoped, Timestamped):
    __tablename__ = "opportunity_evidence"
    __table_args__ = (UniqueConstraint("card_id", "signal_id", name="uq_opportunity_evidence"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("opportunity_cards.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trend_signals.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    relevance_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class SubmissionDelegationRow(Base, TenantScoped, Timestamped):
    """§51.5 P14 — تفويض قابل للسحب والتدقيق."""

    __tablename__ = "submission_delegations"

    id: Mapped[uuid.UUID] = uuid_pk()
    granted_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    granted_to: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    scope_ar: Mapped[str] = mapped_column(Text, nullable=False)
    granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revocation_reason_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class PaperPipelineRun(Base, TenantScoped, Timestamped):
    """§51.5/§51.6 — الحالة لا تُمنح إلا باستيفاء الشروط الاثني عشر."""

    __tablename__ = "paper_pipeline_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("opportunity_cards.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="SET NULL"), nullable=True
    )
    current_stage: Mapped[str] = mapped_column(String(4), nullable=False, default="P0")
    completed_stages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ready_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    unmet_conditions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_ready_for_submission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submission_authorized_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    submission_authorized_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submission_delegation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CompetitiveNoveltyCheck(Base, TenantScoped, Timestamped):
    __tablename__ = "competitive_novelty_checks"

    id: Mapped[uuid.UUID] = uuid_pk()
    card_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("opportunity_cards.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    similarity: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    decision_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class ResearchIntelligenceBrief(Base, TenantScoped, Timestamped):
    """§51.7 — التقارير بإيقاعاتها الأربعة."""

    __tablename__ = "research_intelligence_briefs"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    new_trends: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    score_changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    new_cards: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    alerts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
