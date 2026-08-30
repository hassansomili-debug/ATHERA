"""العزل والمناعة | Row-Level Security and audit immutability.

هنا يتحول ADR-0002 وADR-0004 من نية إلى خاصية قاعدة بيانات:
  • RLS إجبارية على كل جدول يحمل tenant_id.
  • دور التطبيق بلا BYPASSRLS، وبلا UPDATE/DELETE على سجل التدقيق.
  • trigger يمنع تعديل السجل حتى من مسار امتلك الصلاحية سهوًا.

Revision ID: 0003
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# كل جدول يحمل tenant_id — تُفحص القائمة آليًا في AT-S0-01/02 عبر information_schema.
TENANT_TABLES = [
    "organizations", "roles", "role_permissions", "memberships", "object_grants",
    "refresh_tokens", "files", "file_access_logs", "audit_events", "provenance_events",
    "approvals", "integrity_alerts", "agent_runs", "tool_runs", "model_runs", "notifications",
]

# جداول عابرة للمستأجرين: تُقرأ قبل تحديد السياق (تسجيل الدخول) أو مرجعية عامة.
GLOBAL_TABLES = ["tenants", "users", "permissions", "mfa_factors"]


def upgrade() -> None:
    # ── 1. الصلاحيات الأساسية لدور التطبيق ──
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO athera_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO athera_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO athera_app"
    )

    # ── 2. RLS على كل جدول بمستأجر ──
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE يجعل السياسة تنطبق حتى على مالك الجدول — لا باب خلفي.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (tenant_id = app_current_tenant())
              WITH CHECK (tenant_id = app_current_tenant())
            """
        )

    # الجداول العابرة: تُقرأ وتُكتب بلا سياق مستأجر (التسجيل، الدخول، المراجع).
    for table in GLOBAL_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY global_readwrite ON {table} USING (true) WITH CHECK (true)")

    # ── 3. سجل التدقيق: append-only (§37) ──
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM athera_app")
    op.execute("REVOKE UPDATE, DELETE ON file_access_logs FROM athera_app")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE UPDATE, DELETE ON TABLES FROM athera_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO athera_app"
    )

    # حزام ثانٍ: حتى لو مُنحت الصلاحية سهوًا في ترحيل لاحق، الـtrigger يرفض.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only (PRD §37 / ADR-0004): % denied', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_immutable
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_file_access_logs_immutable
            BEFORE UPDATE OR DELETE ON file_access_logs
            FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();
        """
    )

    # ── 4. RAW datasets لاحقًا (§17.2) — الدالة جاهزة ليعاد استخدامها في Sprint 8 ──
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_row_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'this row is immutable by product policy: % denied', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_file_access_logs_immutable ON file_access_logs")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_immutable()")
    op.execute("DROP FUNCTION IF EXISTS forbid_row_mutation()")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in GLOBAL_TABLES:
        op.execute(f"DROP POLICY IF EXISTS global_readwrite ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
