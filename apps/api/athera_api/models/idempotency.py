"""سجلُّ التكرار | Idempotency records (RC-T1-H2-A).

**بنيةٌ داخليّة، لا موردٌ للمستخدم.** ولا مسارَ يُدرج هذه الصفوف ولا يعرضها
ولا يحذفها: هي حَكَمُ إعادةِ المحاولة، ولو صارت موردًا لصار جسمُ الجواب
المخزون قابلًا للطلب مباشرةً — وذاك بابٌ لا يفتحه أحد.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import CHAR, DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, uuid_pk

#: حَجزٌ قائمٌ ونتيجةٌ غيرُ معروفة — **لا يُودَع في الطور A** (انظر 0037).
IN_PROGRESS = "in_progress"
#: جوابٌ مخزونٌ يُعاد حرفيًّا.
COMPLETED = "completed"
#: نهائيّةٌ، والمفتاحُ يبقى قابلًا لإعادةِ محاولةٍ صادقة.
FAILED = "failed"


class IdempotencyRecord(Base):
    """صفُّ تكرارٍ واحد — ونطاقُه أربعةٌ لا واحد.

    و`TenantScoped` لا تُستعمل هنا عمدًا: هي تُعلن `tenant_id` بفهرسٍ
    باسمٍ مشتقّ، وهذا الجدول يحمل **حدَّين** لا حدًّا — المستأجرَ والفاعل —
    ويُعلنهما صريحَين ليقرأهما من يقرأ السياسة.
    """

    __tablename__ = "idempotency_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False)
    #: الحدُّ الأمنيّ: الصفُّ يحمل جوابًا يُعاد، فلا يُقرأ إلّا لصاحبه.
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False)
    #: فعلٌ وقالبُ مسار: "POST /api/v1/workspace/projects".
    operation: Mapped[str] = mapped_column(String(200), nullable=False)
    #: `sha256` للمفتاح — **ولا يُخزَّن المفتاحُ الخام**.
    key_digest: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    response_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    expires_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    #: للطور B وحده — ولا معنى له ما دامت الحالُ ليست `in_progress`.
    lease_expires_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
