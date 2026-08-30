"""أثر العقل البحثي | Brain orchestration trace (Sprint 2).

Revision ID: 0006
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("trace_id", UUID))
    op.add_column("agent_runs", sa.Column("parent_agent_run_id", UUID,
                                          sa.ForeignKey("agent_runs.id", ondelete="SET NULL")))
    op.add_column("agent_runs", sa.Column("requested_by", UUID,
                                          sa.ForeignKey("users.id", ondelete="RESTRICT")))
    op.add_column("agent_runs", sa.Column("gate", sa.String(8)))
    op.add_column("agent_runs", sa.Column("blocked_reason", sa.String(255)))
    op.create_index("ix_agent_runs_trace", "agent_runs", ["tenant_id", "trace_id"])
    op.create_check_constraint(
        "ck_agent_runs_status", "agent_runs",
        "status IN ('running','completed','failed','blocked')",
    )

    op.add_column("tool_runs", sa.Column("tool_kind", sa.String(16)))
    op.add_column("tool_runs", sa.Column("error", sa.Text))
    op.create_check_constraint(
        "ck_tool_runs_status", "tool_runs", "status IN ('ok','error','denied')",
    )

    op.create_table(
        "guardrail_checks",
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("agent_run_id", UUID, sa.ForeignKey("agent_runs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("guard_key", sa.String(64), nullable=False),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("detail_ar", sa.Text),
        sa.Column("detail_en", sa.Text),
        sa.Column("excerpt", sa.Text),
        sa.CheckConstraint("result IN ('passed','blocked')", name="ck_guardrail_result"),
        # حجب بلا تفصيل بلغتين غير مقبول: المستخدم يستحق سبب الحجب بلغته.
        sa.CheckConstraint(
            "(result <> 'blocked') OR (detail_ar IS NOT NULL AND detail_en IS NOT NULL)",
            name="ck_guardrail_block_requires_detail",
        ),
    )
    op.create_index("ix_guardrail_checks_run", "guardrail_checks", ["tenant_id", "agent_run_id"])

    op.execute("ALTER TABLE guardrail_checks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE guardrail_checks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON guardrail_checks
          USING (tenant_id = app_current_tenant())
          WITH CHECK (tenant_id = app_current_tenant())
        """
    )
    op.execute("GRANT SELECT, INSERT ON guardrail_checks TO athera_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON guardrail_checks")
    op.drop_table("guardrail_checks")
    # SQL صريح لا `drop_constraint`: اصطلاح التسمية `ck_%(table_name)s_%(...)s`
    # يُطبَّق عند الحذف ولا يُطبَّق عند `create_check_constraint`، فيُنتج اسمًا
    # مضاعفًا (`ck_tool_runs_ck_tool_runs_status`) لا وجود له، فينكسر التراجع.
    op.execute("ALTER TABLE tool_runs DROP CONSTRAINT IF EXISTS ck_tool_runs_status")
    op.drop_column("tool_runs", "error")
    op.drop_column("tool_runs", "tool_kind")
    op.execute("ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS ck_agent_runs_status")
    op.drop_index("ix_agent_runs_trace", table_name="agent_runs")
    for column in ("blocked_reason", "gate", "requested_by", "parent_agent_run_id", "trace_id"):
        op.drop_column("agent_runs", column)
