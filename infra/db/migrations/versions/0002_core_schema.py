"""الجداول الأساسية | Core Sprint 0 schema (§29.1).

يُولَّد من نماذج SQLAlchemy، ويُكتب صراحةً هنا حتى يبقى الترحيل مقروءًا
ومراجَعًا — لا ناتج أداة صامت.

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)


def _base_cols(*, tenant: bool = True, timestamps: bool = True) -> list[sa.Column]:
    cols = [sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()"))]
    if tenant:
        cols.append(
            sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                      nullable=False, index=True)
        )
    if timestamps:
        cols += [
            sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        ]
    return cols


def upgrade() -> None:
    op.create_table(
        "tenants",
        *_base_cols(tenant=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("default_locale", sa.String(5), nullable=False, server_default="ar"),
        sa.Column("isolation_mode", sa.String(16), nullable=False, server_default="shared"),
        sa.CheckConstraint("default_locale IN ('ar','en')", name="ck_tenants_locale"),
    )

    op.create_table(
        "users",
        *_base_cols(tenant=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name_ar", sa.String(255), nullable=False),
        sa.Column("full_name_en", sa.String(255)),
        sa.Column("preferred_locale", sa.String(5), nullable=False, server_default="ar"),
        sa.Column("orcid", sa.String(32)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", TS),
        sa.CheckConstraint("preferred_locale IN ('ar','en')", name="ck_users_locale"),
    )

    op.create_table(
        "organizations",
        *_base_cols(),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("ror_id", sa.String(64)),
        sa.Column("parent_id", UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL")),
    )

    op.create_table(
        "roles",
        *_base_cols(),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("tenant_id", "key", name="uq_roles_tenant_key"),
    )

    op.create_table(
        "permissions",
        *_base_cols(tenant=False),
        sa.Column("key", sa.String(96), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
    )

    op.create_table(
        "role_permissions",
        *_base_cols(timestamps=False),
        sa.Column("role_id", UUID, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", UUID, sa.ForeignKey("permissions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
    )

    op.create_table(
        "memberships",
        *_base_cols(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", UUID, sa.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_memberships"),
    )

    op.create_table(
        "object_grants",
        *_base_cols(),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", UUID, nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grant_level", sa.String(16), nullable=False),
        sa.Column("restricted_fields", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("granted_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint("grant_level IN ('owner','viewer','editor','approver')",
                           name="ck_object_grants_level"),
        sa.UniqueConstraint("tenant_id", "object_type", "object_id", "user_id", "grant_level",
                            name="uq_object_grants"),
    )

    op.create_table(
        "refresh_tokens",
        *_base_cols(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("revoked_at", TS),
        sa.Column("rotated_to", UUID),
    )

    op.create_table(
        "mfa_factors",
        *_base_cols(tenant=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("factor_type", sa.String(16), nullable=False, server_default="totp"),
        sa.Column("secret_encrypted", sa.Text, nullable=False),
        sa.Column("confirmed_at", TS),
    )

    op.create_table(
        "files",
        *_base_cols(),
        sa.Column("storage_key", sa.Text, nullable=False, unique=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("classification", sa.String(4), nullable=False, server_default="C2"),
        sa.Column("is_untrusted_content", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("uploaded_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("completed_at", TS),
        sa.CheckConstraint("classification IN ('C0','C1','C2','C3','C4')", name="ck_files_classification"),
    )

    op.create_table(
        "file_access_logs",
        *_base_cols(timestamps=False),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("accessed_at", TS, nullable=False),
        sa.Column("ip_address", sa.String(64)),
    )

    # ── التدقيق: append-only بسلسلة تجزئة (§37، ADR-0004) ──
    op.create_table(
        "audit_events",
        *_base_cols(timestamps=False),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("actor_user_id", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("actor_kind", sa.String(16), nullable=False, server_default="user"),
        sa.Column("action", sa.String(96), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", UUID),
        sa.Column("state_before", JSONB),
        sa.Column("state_after", JSONB),
        sa.Column("reason", sa.Text),
        sa.Column("agent_run_id", UUID),
        sa.Column("model_run_id", UUID),
        sa.Column("approval_id", UUID),
        sa.Column("source_refs", JSONB),
        sa.Column("request_id", sa.String(64)),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("chain_seq", sa.Integer, nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("tenant_id", "chain_seq", name="uq_audit_events_chain_seq"),
    )
    op.create_index("ix_audit_events_object", "audit_events", ["tenant_id", "object_type", "object_id"])

    op.create_table(
        "provenance_events",
        *_base_cols(),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", UUID, nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", UUID),
        sa.Column("source_locator", sa.Text),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("verified_at", TS),
        sa.Column("model_run_id", UUID),
        sa.Column("confidence", sa.String(16)),
        sa.CheckConstraint(
            "verification_status IN ('unverified','approved','rejected','verified')",
            name="ck_provenance_status",
        ),
        # §7.4 — لا ترقية إلى verified بلا مُحقِّق وتاريخ. مفروضة في قاعدة البيانات.
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR "
            "(verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_provenance_verified_requires_verifier",
        ),
        # مخرجات النموذج لا تكون مصدرًا موثقًا بذاتها (§7.4).
        sa.CheckConstraint(
            "(source_type <> 'model_output') OR (verification_status <> 'verified')",
            name="ck_provenance_model_output_not_verified",
        ),
    )
    op.create_index("ix_provenance_object", "provenance_events", ["tenant_id", "object_type", "object_id"])

    op.create_table(
        "approvals",
        *_base_cols(),
        sa.Column("gate", sa.String(8), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", UUID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", TS),
        sa.Column("reason", sa.Text),
        sa.Column("workflow_id", sa.String(255)),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_approvals_status"),
        # لا اعتماد بلا مُقرِّر وتاريخ — البوابة إما محسومة بفاعل معروف أو معلّقة.
        sa.CheckConstraint(
            "(status = 'pending') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_approvals_decided_requires_actor",
        ),
    )

    op.create_table(
        "integrity_alerts",
        *_base_cols(),
        sa.Column("alert_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("detail_ar", sa.Text),
        sa.Column("detail_en", sa.Text),
        sa.Column("object_type", sa.String(64)),
        sa.Column("object_id", UUID),
        sa.Column("resolved_at", TS),
    )

    op.create_table(
        "agent_runs",
        *_base_cols(),
        sa.Column("agent_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS),
        sa.Column("input_summary", JSONB),
        sa.Column("output_summary", JSONB),
        sa.Column("error", sa.Text),
    )

    op.create_table(
        "tool_runs",
        *_base_cols(),
        sa.Column("agent_run_id", UUID, sa.ForeignKey("agent_runs.id", ondelete="SET NULL")),
        sa.Column("tool_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("request_payload", JSONB),
        sa.Column("response_payload", JSONB),
    )

    op.create_table(
        "model_runs",
        *_base_cols(),
        sa.Column("agent_run_id", UUID, sa.ForeignKey("agent_runs.id", ondelete="SET NULL")),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(96), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("max_classification_sent", sa.String(4), nullable=False, server_default="C0"),
        sa.Column("error", sa.Text),
    )

    op.create_table(
        "notifications",
        *_base_cols(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("title_ar", sa.String(255), nullable=False),
        sa.Column("title_en", sa.String(255)),
        sa.Column("body_ar", sa.Text),
        sa.Column("body_en", sa.Text),
        sa.Column("read_at", TS),
    )


def downgrade() -> None:
    for table in (
        "notifications", "model_runs", "tool_runs", "agent_runs", "integrity_alerts",
        "approvals", "provenance_events", "audit_events", "file_access_logs", "files",
        "mfa_factors", "refresh_tokens", "object_grants", "memberships", "role_permissions",
        "permissions", "roles", "organizations", "users", "tenants",
    ):
        op.drop_table(table)
