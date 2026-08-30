"""المخطوطة والمجلات والمراجعة | Manuscripts, journals and review (§19، §20، §21، §22)."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..services.publishing.vocab import (  # noqa: F401 — إعادة تصدير مقصودة
    MANUSCRIPT_SECTIONS,
    READINESS_STATUSES,
    REVIEWER_ROLES,
    SUBMISSION_PACKAGE_ITEMS,
    TRUST_TIERS,
)
from .base import Base, TenantScoped, Timestamped, uuid_pk

__all__ = [
    "Manuscript", "ManuscriptVersion", "ManuscriptSection", "JournalProfile",
    "JournalPolicyCheck", "JournalMatchRow", "ReviewRound", "ReviewerReportRow",
    "ReviewPatch", "SubmissionPackage",
    "MANUSCRIPT_SECTIONS", "TRUST_TIERS", "REVIEWER_ROLES", "READINESS_STATUSES",
    "SUBMISSION_PACKAGE_ITEMS",
]


class Manuscript(Base, TenantScoped, Timestamped):
    """§19 — المخطوطة. بوابة G9 لها لقطة جاهزية، فالاعتماد يقع على حالة معروفة."""

    __tablename__ = "manuscripts"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="ar")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    g9_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    g9_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    g9_readiness_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ManuscriptVersion(Base, TenantScoped, Timestamped):
    """§19.2 — لا تغيير لعنصر معتمد دون نسخة جديدة بسبب مكتوب."""

    __tablename__ = "manuscript_versions"
    __table_args__ = (UniqueConstraint("manuscript_id", "version_label",
                                       name="uq_manuscript_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    change_reason_ar: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ManuscriptSection(Base, TenantScoped, Timestamped):
    __tablename__ = "manuscript_sections"
    __table_args__ = (UniqueConstraint("version_id", "section_key",
                                       name="uq_manuscript_section"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_key: Mapped[str] = mapped_column(String(32), nullable=False)
    text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # §19.2 — الادعاءات والتشغيلات مرتبطة بالقسم، فتُفحص بوابة G9 عليها.
    claim_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    analysis_run_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class JournalProfile(Base, TenantScoped, Timestamped):
    """§20.1 — ملف المجلة. طبقة الثقة بلا تاريخ حساب ادعاء بلا زمن."""

    __tablename__ = "journal_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="CASCADE"), nullable=False
    )
    trust_tier: Mapped[str | None] = mapped_column(String(1), nullable=True)
    tier_computed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scope_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recent_article_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    accepted_methods: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    apc_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    oa_model: Mapped[str | None] = mapped_column(String(24), nullable=True)
    ai_policy_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    median_review_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class JournalPolicyCheck(Base, TenantScoped, Timestamped):
    """§20.3 / TC-04 — سجل إعادة التحقق عند النقاط الأربع."""

    __tablename__ = "journal_policy_checks"

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="CASCADE"), nullable=False
    )
    verification_point: Mapped[str] = mapped_column(String(24), nullable=False)
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    indexing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)


class JournalMatchRow(Base, TenantScoped, Timestamped):
    """§20.4 — لا حقل لاحتمال قبول هنا، وهذه هي الضمانة."""

    __tablename__ = "journal_matches"
    __table_args__ = (UniqueConstraint("manuscript_id", "journal_id", name="uq_journal_match"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="RESTRICT"), nullable=False
    )
    fit_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trust_tier: Mapped[str] = mapped_column(String(1), nullable=False)
    blockers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    uncomputed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    indexing_verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    g10_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    g10_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewRound(Base, TenantScoped, Timestamped):
    __tablename__ = "review_rounds"
    __table_args__ = (UniqueConstraint("manuscript_id", "round_number", name="uq_review_round"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(24), nullable=False)
    major_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewers_missing: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ReviewerReportRow(Base, TenantScoped, Timestamped):
    __tablename__ = "reviewer_reports"
    __table_args__ = (UniqueConstraint("round_id", "reviewer_role", name="uq_reviewer_report"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    round_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_role: Mapped[str] = mapped_column(String(24), nullable=False)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    major_concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    minor_concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rejection_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ReviewPatch(Base, TenantScoped, Timestamped):
    """§21 — الرقعة تبدأ مقترحة، وتطبيقها يستلزم فاعلًا و**نسخة جديدة**."""

    __tablename__ = "review_patches"

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("reviewer_reports.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale_ar: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_in_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )


class SubmissionPackage(Base, TenantScoped, Timestamped):
    """§22.1 — «مكتملة» تعني فعلًا لا عنصر إلزاميًا ناقصًا."""

    __tablename__ = "submission_packages"

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    journal_match_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journal_matches.id", ondelete="SET NULL"), nullable=True
    )
    items_present: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_optional: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assembled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
