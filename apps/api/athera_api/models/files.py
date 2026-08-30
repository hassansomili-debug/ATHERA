"""الملفات | Files (§29.1، §33.3، §36).

كل ملف مرفوع يُوسم `untrusted` منذ لحظة الرفع — تمهيدًا لدفاع حقن الأوامر
في §33.3: محتوى الملفات بيانات، لا تعليمات.
"""

import datetime as dt
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


class File(Base, TenantScoped, Timestamped):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = uuid_pk()
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # C0 عام … C4 بيانات مشاركين — تحدد التشفير والاحتفاظ وحق الإرسال لنموذج خارجي.
    classification: Mapped[str] = mapped_column(String(4), nullable=False, default="C2")
    is_untrusted_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FileAccessLog(Base, TenantScoped):
    """§36.2 — سجل من اطّلع على الملف. كل تنزيل يُسجَّل، بلا استثناء."""

    __tablename__ = "file_access_logs"

    id: Mapped[uuid.UUID] = uuid_pk()
    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # download|view|presign
    accessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
