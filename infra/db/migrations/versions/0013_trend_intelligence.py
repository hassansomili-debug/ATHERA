"""الذكاء الاستباقي للاتجاهات | Proactive trend intelligence (§51).

أربعة قيود تحمل هذا القسم:
  • لا إشارة يتيمة: مصدر ومعرّف وتاريخ إلزامية (§51.11).
  • إشارة مصدرها مخرَج نموذج لا تُحتسب في وزن الأدلة (§51.1).
  • البطاقة لا تحمل نص مخطوطة — «لا تبدأ بالكتابة» بغياب العمود (§51.4).
  • لا تقديم خارجي إلا بفعل بشري أو تفويض ساري قابل للسحب (§51.5 P14).

Revision ID: 0013
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

PATTERNS = ("topic_emergence", "topic_acceleration", "declining_topic", "theory_shift",
            "method_shift", "geographic_gap", "contradictory_findings",
            "replication_opportunity", "data_opportunity")
WATCHLISTS = ("personal", "project", "construct", "journal", "supervised_thesis", "competitive")
SOURCE_TYPES = ("openalex", "crossref", "doaj", "licensed_index", "user_upload",
                "journal_site", "model_output")
TREND_STATUSES = ("candidate", "validated", "noise", "declining", "retired")
STAGES = tuple(f"P{i}" for i in range(15))
CADENCES = ("daily", "weekly", "monthly", "alert")

TENANT_TABLES = [
    "research_trends", "trend_signals", "research_watchlists", "opportunity_cards",
    "opportunity_evidence", "paper_pipeline_runs", "competitive_novelty_checks",
    "research_intelligence_briefs", "submission_delegations",
]


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    ]


def _in(column: str, values) -> str:
    return f"{column} IN ({','.join(chr(39) + v + chr(39) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "research_watchlists", *_base(),
        sa.Column("watchlist_kind", sa.String(24), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE")),
        sa.Column("keywords", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("theories", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("methods", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("journal_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("refresh_cron", sa.String(64)),
        sa.Column("last_refreshed_at", TS),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint(_in("watchlist_kind", WATCHLISTS), name="ck_watchlist_kind"),
        # §51.2 — مراقبة بلا نطاق لا تراقب شيئًا.
        sa.CheckConstraint(
            "keywords <> '[]'::jsonb OR theories <> '[]'::jsonb "
            "OR methods <> '[]'::jsonb OR journal_ids <> '[]'::jsonb",
            name="ck_watchlist_needs_scope",
        ),
    )

    op.create_table(
        "research_trends", *_base(),
        sa.Column("trend_key", sa.String(128), nullable=False),
        sa.Column("label_ar", sa.String(512), nullable=False),
        sa.Column("label_en", sa.String(512)),
        sa.Column("field_ar", sa.String(255)),
        sa.Column("discovered_at", TS, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="candidate"),
        sa.Column("evidence_weight", sa.Numeric(8, 3), nullable=False, server_default="0"),
        sa.Column("signal_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("distinct_sources", sa.Integer, nullable=False, server_default="0"),
        sa.Column("span_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("validation_policy_id", sa.String(64)),
        sa.Column("validation_snapshot", JSONB),
        sa.Column("last_validated_at", TS),
        sa.UniqueConstraint("tenant_id", "trend_key", name="uq_research_trend_key"),
        sa.CheckConstraint(_in("status", TREND_STATUSES), name="ck_trend_status"),
        # §51.1 — «مُصادق عليه» يعني فحصًا مؤرَّخًا بسياسة معلومة، لا وسمًا.
        sa.CheckConstraint(
            "status <> 'validated' OR "
            "(validation_snapshot IS NOT NULL AND last_validated_at IS NOT NULL "
            " AND validation_policy_id IS NOT NULL)",
            name="ck_trend_validated_requires_snapshot",
        ),
    )

    op.create_table(
        "trend_signals", *_base(),
        sa.Column("trend_id", UUID, sa.ForeignKey("research_trends.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("watchlist_id", UUID,
                  sa.ForeignKey("research_watchlists.id", ondelete="SET NULL")),
        sa.Column("pattern", sa.String(32), nullable=False),
        # §51.11 — «لا توجد إشارة يتيمة بلا Provenance».
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_id", sa.String(512), nullable=False),
        sa.Column("source_url", sa.Text),
        sa.Column("observed_at", TS, nullable=False),
        sa.Column("weight", sa.Numeric(4, 3), nullable=False, server_default="1.0"),
        sa.Column("counts_as_evidence", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("detail_ar", sa.Text),
        sa.Column("raw_payload", JSONB),
        sa.CheckConstraint(_in("pattern", PATTERNS), name="ck_signal_pattern"),
        sa.CheckConstraint(_in("source_type", SOURCE_TYPES), name="ck_signal_source_type"),
        sa.CheckConstraint("length(source_id) > 0", name="ck_signal_source_id_required"),
        sa.CheckConstraint("weight > 0 AND weight <= 1", name="ck_signal_weight_range"),
        # §51.1 — ذاكرة النموذج ليست دليلًا: لا يمكن وسمها كذلك.
        sa.CheckConstraint(
            "source_type <> 'model_output' OR NOT counts_as_evidence",
            name="ck_signal_model_output_not_evidence",
        ),
    )
    op.create_index("ix_trend_signals_trend", "trend_signals",
                    ["tenant_id", "trend_id", "observed_at"])

    op.create_table(
        "opportunity_cards", *_base(),
        sa.Column("trend_id", UUID, sa.ForeignKey("research_trends.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("working_title_ar", sa.Text, nullable=False),
        sa.Column("central_question_ar", sa.Text, nullable=False),
        sa.Column("trend_summary_ar", sa.Text, nullable=False),
        sa.Column("gap_ar", sa.Text, nullable=False),
        sa.Column("gap_confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("proposed_theory_ar", sa.Text),
        sa.Column("proposed_method_ar", sa.Text),
        sa.Column("required_data_ar", sa.Text),
        sa.Column("data_is_available", sa.Boolean),
        sa.Column("novelty_note_ar", sa.Text),
        sa.Column("candidate_journal_ids", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("execution_risk_ar", sa.Text),
        sa.Column("estimated_months", sa.Integer),
        sa.Column("overlap_note_ar", sa.Text),
        sa.Column("fit_score", sa.Numeric(5, 2)),
        sa.Column("fit_criteria", JSONB),
        sa.Column("blocking_reasons", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("approved_at", TS),
        sa.Column("converted_project_id", UUID,
                  sa.ForeignKey("research_projects.id", ondelete="SET NULL")),
        # §51.4 — لا عمود لنص مخطوطة: «لا تبدأ بالكتابة مباشرة».
        sa.CheckConstraint("length(central_question_ar) > 0", name="ck_card_needs_question"),
        sa.CheckConstraint("length(gap_ar) > 0", name="ck_card_needs_gap"),
        sa.CheckConstraint("gap_confidence >= 0 AND gap_confidence <= 1",
                           name="ck_card_gap_confidence_range"),
        # §51.11 — لا تحويل إلى مشروع إلا بعد اعتماد المستخدم.
        sa.CheckConstraint(
            "(approved_by IS NULL AND approved_at IS NULL) OR "
            "(approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_card_approval_complete",
        ),
        sa.CheckConstraint(
            "converted_project_id IS NULL OR approved_at IS NOT NULL",
            name="ck_card_conversion_requires_approval",
        ),
    )

    op.create_table(
        "opportunity_evidence", *_base(),
        sa.Column("card_id", UUID, sa.ForeignKey("opportunity_cards.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("signal_id", UUID, sa.ForeignKey("trend_signals.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("relevance_note_ar", sa.Text),
        sa.UniqueConstraint("card_id", "signal_id", name="uq_opportunity_evidence"),
    )

    op.create_table(
        "paper_pipeline_runs", *_base(),
        sa.Column("card_id", UUID, sa.ForeignKey("opportunity_cards.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="SET NULL")),
        sa.Column("current_stage", sa.String(4), nullable=False, server_default="P0"),
        sa.Column("completed_stages", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ready_conditions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("unmet_conditions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_ready_for_submission", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("submission_authorized_by", UUID,
                  sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("submission_authorized_at", TS),
        sa.Column("submission_delegation_id", UUID),
        sa.Column("last_error", sa.Text),
        sa.CheckConstraint(_in("current_stage", STAGES), name="ck_pipeline_stage"),
        # §51.6 — الحالة لا تُمنح إلا باستيفاء الشروط الاثني عشر كلها.
        sa.CheckConstraint(
            "(NOT is_ready_for_submission) OR unmet_conditions = '[]'::jsonb",
            name="ck_pipeline_ready_requires_all_conditions",
        ),
        # §51.5 P14 — التقديم يحتاج فعلًا بشريًا أو تفويضًا، وبعد بلوغ الحالة.
        sa.CheckConstraint(
            "submission_authorized_at IS NULL OR "
            "(is_ready_for_submission AND "
            " (submission_authorized_by IS NOT NULL OR submission_delegation_id IS NOT NULL))",
            name="ck_pipeline_submission_requires_human_or_delegation",
        ),
    )

    op.create_table(
        "submission_delegations", *_base(),
        sa.Column("granted_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("granted_to", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("scope_ar", sa.Text, nullable=False),
        sa.Column("granted_at", TS, nullable=False),
        sa.Column("expires_at", TS),
        sa.Column("revoked_at", TS),
        sa.Column("revoked_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("revocation_reason_ar", sa.Text),
        # §51.5 — «قابل للسحب والتدقيق»: السحب حدث له فاعل وسبب.
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revoked_by IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by IS NOT NULL "
            " AND revocation_reason_ar IS NOT NULL)",
            name="ck_delegation_revocation_complete",
        ),
        sa.CheckConstraint("expires_at IS NULL OR expires_at > granted_at",
                           name="ck_delegation_expiry_after_grant"),
    )
    op.create_foreign_key(
        "fk_pipeline_delegation", "paper_pipeline_runs", "submission_delegations",
        ["submission_delegation_id"], ["id"], ondelete="SET NULL",
    )

    op.create_table(
        "competitive_novelty_checks", *_base(),
        sa.Column("card_id", UUID, sa.ForeignKey("opportunity_cards.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("similarity", sa.Numeric(4, 3), nullable=False),
        sa.Column("checked_at", TS, nullable=False),
        sa.Column("decision", sa.String(24)),
        sa.Column("decision_note_ar", sa.Text),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.CheckConstraint("similarity >= 0 AND similarity <= 1",
                           name="ck_novelty_similarity_range"),
        sa.CheckConstraint(
            "decision IS NULL OR decision IN ('proceed','revise','merge','abandon')",
            name="ck_novelty_decision",
        ),
        # قرار السبق البحثي بشري ومُعلَّل.
        sa.CheckConstraint(
            "decision IS NULL OR (decided_by IS NOT NULL AND decision_note_ar IS NOT NULL)",
            name="ck_novelty_decision_requires_actor",
        ),
    )

    op.create_table(
        "research_intelligence_briefs", *_base(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cadence", sa.String(16), nullable=False),
        sa.Column("period_start", TS, nullable=False),
        sa.Column("period_end", TS, nullable=False),
        sa.Column("new_trends", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("score_changes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("new_cards", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("alerts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary_ar", sa.Text),
        sa.Column("summary_en", sa.Text),
        sa.Column("seen_at", TS),
        sa.Column("acknowledged_at", TS),
        sa.CheckConstraint(_in("cadence", CADENCES), name="ck_brief_cadence"),
        sa.CheckConstraint("period_end >= period_start", name="ck_brief_period"),
    )

    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
              USING (tenant_id = app_current_tenant())
              WITH CHECK (tenant_id = app_current_tenant())
            """
        )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON " + ", ".join(TENANT_TABLES) + " TO athera_app")
    # الإشارة سجل رصد: تُضاف ولا تُعدَّل ولا تُحذف.
    op.execute("REVOKE UPDATE, DELETE ON trend_signals FROM athera_app")


def downgrade() -> None:
    op.drop_constraint("fk_pipeline_delegation", "paper_pipeline_runs", type_="foreignkey")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in ("research_intelligence_briefs", "competitive_novelty_checks",
                  "submission_delegations", "paper_pipeline_runs", "opportunity_evidence",
                  "opportunity_cards", "trend_signals", "research_trends",
                  "research_watchlists"):
        op.drop_table(table)
