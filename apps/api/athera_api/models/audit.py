"""التدقيق والـProvenance | Audit and provenance (§37، §29.2، ADR-0004).

سجلّان بسؤالين مختلفين:
  audit_events      → من فعل ماذا ومتى ولماذا
  provenance_events → من أين جاءت هذه المعلومة
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BilingualName, TenantScoped, Timestamped, uuid_pk


class AuditEvent(Base, TenantScoped):
    """append-only. صلاحيات UPDATE/DELETE منزوعة من دور التطبيق (ترحيل 0002)."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "chain_seq", name="uq_audit_events_chain_seq"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="user")  # user|agent|system

    action: Mapped[str] = mapped_column(String(96), nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    # §37 — الحالة قبل وبعد وسبب التغيير، لا مجرد "حدث تغيير".
    state_before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    source_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # سلسلة التجزئة: تكشف العبث ولا تمنع من يملك DBA — مخاطرة معلنة في ADR-0004.
    chain_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ProvenanceEvent(Base, TenantScoped, Timestamped):
    """الحقول التسعة الإلزامية في §29.2 — مفروضة بقيد قاعدة بيانات لا بمراجعة كود."""

    __tablename__ = "provenance_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)

    # upload | external_source | analysis_run | user_statement | model_output
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    # الصفحة/القسم/الفقرة — بلا locator لا يوجد أثر قابل للتحقق.
    source_locator: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # unverified | approved | rejected | verified  (§7.4)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Approval(Base, TenantScoped, Timestamped):
    """بوابات §9 — الاعتماد كائن مستقل له تاريخ وفاعل وسبب."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = uuid_pk()
    gate: Mapped[str] = mapped_column(String(8), nullable=False)  # G0..G12, GT1
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    requested_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # بصمة السياق الذي أُذن له (S5D §7) — قابلة للعدم: بوابات §9 وموافقات
    # S5C لا تستعملها. ووجودها يجعل الإذن مرتبطًا بأدلةٍ بعينها لا مفتوحًا.
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IntegrityAlert(Base, TenantScoped, Timestamped, BilingualName):
    """§25 — تنبيهات النزاهة، بلغتين لأنها تُعرض للباحث مباشرة."""

    __tablename__ = "integrity_alerts"

    id: Mapped[uuid.UUID] = uuid_pk()
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="warning")
    detail_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
