"""الأساس المشترك للنماذج | Shared model base."""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, MetaData, String, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TenantScoped:
    """كل جدول يحمل tenant_id — شرط تفعيل RLS (ADR-0002)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class Timestamped:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BilingualName:
    """الاسم بلغتين | bilingual display name (§26.4).

    الاسم العربي إلزامي لأن العربية لغة المنتج الافتراضية؛ الإنجليزي اختياري
    ويسقط إلى العربي عند غيابه.
    """

    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def display(self, locale: str) -> str:
        return (self.name_en or self.name_ar) if locale == "en" else self.name_ar
