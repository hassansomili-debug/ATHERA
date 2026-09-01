"""نماذج تخطيط النشر | Publication planning models (S5D).

**توسيعٌ لا معماريةٌ موازية.** الفرص في `publication_opportunities` منذ 0010،
والخيط في `thread_elements`. وهذه الجداول تربطهما بالمعرفة الموثقة.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


class PlanningRun(Base, TenantScoped, Timestamped):
    """تشغيلة تخطيط واحدة — والكيان الذي يُجيب عن سؤال «من أي دليل؟».

    §4 و§5 — تحمل **بصمة** لقطة الأدلة ومعرّفات ذاكراتها، لا محتواها. فتُقارَن
    الموافقة بسياقها: إذنٌ أُعطي على أدلةٍ بعينها لا يغطّي أدلةً أُضيفت بعده.
    """

    __tablename__ = "planning_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False
    )
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    memory_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    # running | insufficient_evidence | completed | failed
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="running")
    opportunities_proposed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class OpportunityEvidenceLink(Base, TenantScoped, Timestamped):
    """فرصة ← ذاكرة موثقة.

    **ولا نسخ للإسناد** (§21): الموضع والاقتباس والملف تملكها
    `researcher_memories`. ونسخها هنا يخلق مصدرَي حقيقة يفترقان بأول تعديل.
    فالسلسلة: فرصة → رابط → ذاكرة → إسناد.
    """

    __tablename__ = "opportunity_evidence_links"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "memory_id", "evidence_role",
                         name="uq_opportunity_evidence_link"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
        nullable=False
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_memories.id", ondelete="CASCADE"),
        nullable=False
    )
    evidence_role: Mapped[str] = mapped_column(String(24), nullable=False)


class ThreadElementEvidence(Base, TenantScoped, Timestamped):
    """عنصر خيط ← ذاكرة موثقة. وما لا رابط له **اقتراحٌ** لا حقيقة مصدر."""

    __tablename__ = "thread_element_evidence"
    __table_args__ = (
        UniqueConstraint("element_id", "memory_id", name="uq_thread_element_evidence"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    element_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("thread_elements.id", ondelete="CASCADE"),
        nullable=False
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_memories.id", ondelete="CASCADE"),
        nullable=False
    )


class ManuscriptOutline(Base, TenantScoped, Timestamped):
    """هيكل الورقة — أقسامٌ بأدلتها وحدودها. **ولا نثر** (§27)."""

    __tablename__ = "manuscript_outlines"

    id: Mapped[uuid.UUID] = uuid_pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
        nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False
    )
    sections: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    article_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("planning_runs.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")


__all__ = ["ManuscriptOutline", "OpportunityEvidenceLink", "PlanningRun",
           "ThreadElementEvidence"]
