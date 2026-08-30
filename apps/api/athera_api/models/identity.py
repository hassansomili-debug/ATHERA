"""الهوية والمستأجرون والصلاحيات | Identity, tenancy and RBAC (§28، ADR-0002)."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BilingualName, TenantScoped, Timestamped, uuid_pk


class Tenant(Base, Timestamped, BilingualName):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    default_locale: Mapped[str] = mapped_column(String(5), nullable=False, default="ar")
    # مسار العزل الفعلي لعملاء Enterprise (§46) — نفس الكود، اتصال مختلف.
    isolation_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="shared")


class Organization(Base, TenantScoped, Timestamped, BilingualName):
    """المؤسسة/الكلية/القسم داخل مستأجر | institution, college or department."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_pk()
    ror_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )


class User(Base, Timestamped):
    """المستخدم عابر للمستأجرين؛ الانتماء يُعبَّر عنه بالعضوية."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_locale: Mapped[str] = mapped_column(String(5), nullable=False, default="ar")
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(Base, TenantScoped, Timestamped, BilingualName):
    """الأدوار التسعة (§28) كبيانات لا كثوابت في الكود."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_roles_tenant_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permission(Base, Timestamped, BilingualName):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = uuid_pk()
    key: Mapped[str] = mapped_column(String(96), unique=True, nullable=False)


class RolePermission(Base, TenantScoped):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    role_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )


class Membership(Base, TenantScoped, Timestamped):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_memberships"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )


class ObjectGrant(Base, TenantScoped, Timestamped):
    """الطبقة الثانية من §28: Owner/Viewer/Editor/Approver + حقول مقيّدة لكل كائن.

    جدول مقترح خارج قائمة §29.1 — مسجَّل صراحةً في خطة Sprint 0 §3.1.
    """

    __tablename__ = "object_grants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_type", "object_id", "user_id", "grant_level",
                         name="uq_object_grants"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # owner | viewer | editor | approver
    grant_level: Mapped[str] = mapped_column(String(16), nullable=False)
    restricted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class RefreshToken(Base, TenantScoped, Timestamped):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rotated_to: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class MfaFactor(Base, Timestamped):
    __tablename__ = "mfa_factors"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    factor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="totp")
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
