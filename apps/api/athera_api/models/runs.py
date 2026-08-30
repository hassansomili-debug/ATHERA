"""تشغيلات الأجنتات والأدوات والنماذج | Agent, tool and model runs (§29.1، §32)."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


class AgentRun(Base, TenantScoped, Timestamped):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # الأثر: تشغيلات متعددة قد تنتمي إلى طلب واحد (§38.5).
    trace_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True, index=True)
    parent_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ToolRun(Base, TenantScoped, Timestamped):
    __tablename__ = "tool_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    tool_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # read | denied — «denied» يوثّق محاولة استدعاء خارج الصلاحية.
    tool_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class ModelRun(Base, TenantScoped, Timestamped):
    """جدول مقترح خارج §29.1 — تستلزمه §29.2 التي تشير إلى model_run_id بلا تعريف.

    مسجَّل صراحةً في خطة Sprint 0 §3.1 بدل تمريره صامتًا.
    """

    __tablename__ = "model_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(96), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)  # generate_structured|embed|stream|tool_call
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    # §36.3 — أعلى تصنيف حساسية سُمح بإرساله فعلًا في هذا الاستدعاء.
    max_classification_sent: Mapped[str] = mapped_column(String(4), nullable=False, default="C0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(Base, TenantScoped, Timestamped):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
