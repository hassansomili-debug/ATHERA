"""محرك الترقية ومحفظة الأبحاث | Promotion engine and research portfolio (Sprint 3).

Revision ID: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

RULE_TYPES = (
    "service_duration", "minimum_units", "sole_author_works", "authorship_credit",
    "minimum_refereed_journals", "outlet_diversity", "production_points",
    "indexing_requirement", "date_window", "thesis_derived_limit",
    "first_or_corresponding_author", "teaching_service_requirement",
)

TENANT_TABLES = [
    "promotion_policies", "promotion_policy_versions", "promotion_rules",
    "researcher_publications", "promotion_cases", "promotion_evidence", "promotion_scenarios",
    "research_programs", "research_projects", "project_members", "project_decisions",
]


def _base(*, timestamps: bool = True) -> list[sa.Column]:
    cols = [
        sa.Column("id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False, index=True),
    ]
    if timestamps:
        cols += [
            sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        ]
    return cols


def _in(column: str, values) -> str:
    return f"{column} IN ({','.join(chr(39) + v + chr(39) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "promotion_policies",
        *_base(),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("target_rank", sa.String(64)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "promotion_policy_versions",
        *_base(),
        sa.Column("policy_id", UUID, sa.ForeignKey("promotion_policies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_label", sa.String(32), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("source_document_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("verified_at", TS),
        sa.UniqueConstraint("policy_id", "version_label", name="uq_policy_version_label"),
        sa.CheckConstraint("verification_status IN ('unverified','verified','rejected')",
                           name="ck_policy_version_status"),
        sa.CheckConstraint("(effective_to IS NULL) OR (effective_to >= effective_from)",
                           name="ck_policy_version_window"),
        # §11.2 — نسخة موثقة بلا مصدر رسمي غير مقبولة.
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR "
            "(source_document_id IS NOT NULL AND verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_policy_version_verified_requires_source",
        ),
    )

    op.create_table(
        "promotion_rules",
        *_base(),
        sa.Column("policy_version_id", UUID,
                  sa.ForeignKey("promotion_policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(48), nullable=False),
        sa.Column("rule_key", sa.String(64), nullable=False),
        sa.Column("statement_ar", sa.Text, nullable=False),
        sa.Column("statement_en", sa.Text),
        sa.Column("params", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_locator", sa.Text),
        sa.Column("source_quote", sa.Text),
        sa.Column("is_blocking", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("verified_at", TS),
        sa.CheckConstraint(_in("rule_type", RULE_TYPES), name="ck_promotion_rule_type"),
        sa.CheckConstraint("verification_status IN ('unverified','verified','rejected')",
                           name="ck_promotion_rule_status"),
        # §8 (Promotion Auditor) — لا قاعدة موثقة بلا موضع ومُحقِّق وتاريخ.
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR "
            "(source_locator IS NOT NULL AND verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_promotion_rule_verified_requires_source",
        ),
    )
    op.create_index("ix_promotion_rules_version", "promotion_rules",
                    ["tenant_id", "policy_version_id", "verification_status"])

    op.create_table(
        "researcher_publications",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("journal_name", sa.String(512)),
        sa.Column("journal_id", UUID),
        sa.Column("doi", sa.String(255)),
        sa.Column("published_on", sa.Date),
        sa.Column("author_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("author_position", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_corresponding", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_refereed", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("is_thesis_derived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("indexes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("indexing_verified_at", TS),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("verified_at", TS),
        sa.CheckConstraint("author_position <= author_count", name="ck_publication_position"),
        sa.CheckConstraint("author_count >= 1", name="ck_publication_author_count"),
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_publication_verified_requires_verifier",
        ),
        # §20.1 — ادعاء فهرسة بلا تاريخ تحقق غير مقبول.
        sa.CheckConstraint(
            "(indexes = '[]'::jsonb) OR (indexing_verified_at IS NOT NULL)",
            name="ck_publication_indexes_require_timestamp",
        ),
    )

    op.create_table(
        "promotion_cases",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("policy_version_id", UUID,
                  sa.ForeignKey("promotion_policy_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("computed_at", TS, nullable=False),
        sa.Column("rules_met", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rules_blocking", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rules_needing_verification", sa.Integer, nullable=False, server_default="0"),
        sa.Column("units_total", sa.Numeric(8, 3)),
        sa.Column("units_computable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("result", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        # «صفر» و«غير معلوم» ليسا الشيء نفسه: غير قابل للحساب ⇒ لا رقم.
        sa.CheckConstraint("(units_computable) OR (units_total IS NULL)",
                           name="ck_case_units_null_when_incomputable"),
    )

    op.create_table(
        "promotion_evidence",
        *_base(),
        sa.Column("case_id", UUID, sa.ForeignKey("promotion_cases.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("rule_id", UUID, sa.ForeignKey("promotion_rules.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("publication_id", UUID,
                  sa.ForeignKey("researcher_publications.id", ondelete="SET NULL")),
        sa.Column("contribution", sa.Numeric(8, 3)),
        sa.Column("explanation_ar", sa.Text, nullable=False),
        sa.Column("explanation_en", sa.Text, nullable=False),
    )

    op.create_table(
        "promotion_scenarios",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("policy_version_id", UUID,
                  sa.ForeignKey("promotion_policy_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("scenario_kind", sa.String(32), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("assumptions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("projection", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_projection", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "scenario_kind IN ('minimum','safe','ambitious','rejection_impact','indexing_change')",
            name="ck_scenario_kind",
        ),
        # §11.6 — الإسقاط لا يتحول إلى إنجاز بتعديل عمود.
        sa.CheckConstraint("is_projection", name="ck_scenario_always_projection"),
    )

    op.create_table(
        "research_programs",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL")),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("description_ar", sa.Text),
        sa.Column("description_en", sa.Text),
    )

    op.create_table(
        "research_projects",
        *_base(),
        sa.Column("program_id", UUID, sa.ForeignKey("research_programs.id", ondelete="SET NULL")),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="SET NULL")),
        sa.Column("working_title_ar", sa.Text, nullable=False),
        sa.Column("working_title_en", sa.Text),
        sa.Column("study_type", sa.String(48)),
        sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
        sa.Column("expected_units", sa.Numeric(6, 3)),
        sa.Column("target_journal_name", sa.String(512)),
        sa.Column("target_index_tier", sa.String(32)),
        sa.Column("intended_author_count", sa.Integer),
        sa.Column("intended_author_position", sa.Integer),
        sa.Column("risks", JSONB),
        sa.Column("target_date", sa.Date),
        sa.Column("current_gate", sa.String(8)),
        sa.Column("gate_approved_at", TS),
        sa.Column("is_thesis_derived", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "project_members",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="co_author"),
        sa.Column("credit_roles", JSONB),
        sa.Column("consent_recorded_at", TS),
    )

    op.create_table(
        "project_decisions",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("decision_kind", sa.String(48), nullable=False),
        sa.Column("statement_ar", sa.Text, nullable=False),
        sa.Column("statement_en", sa.Text),
        sa.Column("gate", sa.String(8)),
        sa.Column("approval_id", UUID, sa.ForeignKey("approvals.id", ondelete="SET NULL")),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", TS),
        sa.Column("supersedes_id", UUID),
        # §7.3 Project Decision — قرار محسوم بلا فاعل وتاريخ غير مقبول.
        sa.CheckConstraint(
            "(decided_at IS NULL) OR (decided_by IS NOT NULL)",
            name="ck_project_decision_actor",
        ),
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


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in ("project_decisions", "project_members", "research_projects", "research_programs",
                  "promotion_scenarios", "promotion_evidence", "promotion_cases",
                  "researcher_publications", "promotion_rules", "promotion_policy_versions",
                  "promotion_policies"):
        op.drop_table(table)
