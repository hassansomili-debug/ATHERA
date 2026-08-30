"""محفظة الأبحاث | Research portfolio (§12).

الهدف من §12.1: إدارة عدة أوراق متوازية تخدم خطًا علميًا واحدًا، بدل
أبحاث متفرقة. لذلك المشروع ينتمي إلى `research_program` — والبرنامج هو
«الخط العلمي» الذي يمنع تشتت المحفظة.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BilingualName, TenantScoped, Timestamped, uuid_pk


class ResearchProgram(Base, TenantScoped, Timestamped, BilingualName):
    """الخط العلمي الذي تخدمه عدة أوراق (§12.1)."""

    __tablename__ = "research_programs"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True
    )
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchProject(Base, TenantScoped, Timestamped):
    """§12.2 — حقول المشروع كما وردت في الوثيقة، بلا نقصان."""

    __tablename__ = "research_projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_programs.id", ondelete="SET NULL"), nullable=True
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True
    )

    working_title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    working_title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    study_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")

    # الوحدة المتوقعة إسقاط لا إنجاز — تبقى منفصلة عن الوحدات المحسوبة فعليًا.
    expected_units: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    target_journal_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_index_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intended_author_count: Mapped[int | None] = mapped_column(nullable=True)
    intended_author_position: Mapped[int | None] = mapped_column(nullable=True)

    risks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    current_gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gate_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_thesis_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProjectMember(Base, TenantScoped, Timestamped):
    __tablename__ = "project_members"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="co_author")
    # §24 — أدوار CRediT تُسجَّل ولا تُستنتج.
    credit_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    consent_recorded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectDecision(Base, TenantScoped, Timestamped):
    """§7.3 Project Decision — قرار له اعتماد بشري وتاريخ ونسخة."""

    __tablename__ = "project_decisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    decision_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    statement_ar: Mapped[str] = mapped_column(Text, nullable=False)
    statement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
