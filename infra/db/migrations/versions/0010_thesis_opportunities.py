"""الرسائل وفرص النشر والتأليف | Theses, opportunities and authorship (Sprint 6).

قيدان يحملان وزن السبرنت:
  • ready_to_submit يستلزم اعتماد الحقوق والتأليف (§23.9، TC-06).
  • party_kind من قيمتين فقط — «AI لا يكون مؤلفًا» (§24.2) مفروضة بغياب
    القيمة لا بفحص نصي.

Revision ID: 0010
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

OPPORTUNITY_KINDS = ("independent_question", "sub_model", "qualitative_phase",
                     "scale_development", "antecedents", "consequences", "comparative",
                     "null_unexpected", "secondary_analysis", "extension")
PAPER_KINDS = ("extraction", "extension")
READINESS_OUTCOMES = ("ready_to_convert", "needs_reanalysis", "needs_theoretical_update",
                      "merge_with_another", "do_not_publish_separately")
CREDIT_ROLES = ("conceptualization", "data_curation", "formal_analysis", "funding_acquisition",
                "investigation", "methodology", "project_administration", "resources",
                "software", "supervision", "validation", "visualization",
                "writing_original_draft", "writing_review_editing")
RIGHTS_BASES = ("thesis_owner", "supervisor_with_consent", "institution_policy")
OPP_STATUSES = ("discovered", "analysed", "rights_pending", "ready_to_submit",
                "converted", "rejected")

TENANT_TABLES = [
    "theses", "thesis_owners", "thesis_supervisors", "thesis_sections", "thesis_results",
    "overlap_policies", "publication_opportunities", "opportunity_overlap_scores",
    "authorship_parties", "authorship_agreements", "credit_role_assignments",
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
        "theses", *_base(),
        sa.Column("title_ar", sa.Text, nullable=False),
        sa.Column("title_en", sa.Text),
        sa.Column("degree", sa.String(24), nullable=False),
        sa.Column("defended_on", sa.Date),
        sa.Column("data_collected_on", sa.Date),
        sa.Column("institution_ar", sa.String(255)),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("rights_basis", sa.String(32)),
        sa.Column("parsed_at", TS),
        sa.Column("existing_publications", JSONB),
        sa.CheckConstraint("degree IN ('masters','phd')", name="ck_thesis_degree"),
        sa.CheckConstraint("rights_basis IS NULL OR " + _in("rights_basis", RIGHTS_BASES),
                           name="ck_thesis_rights_basis"),
    )

    op.create_table(
        "thesis_owners", *_base(),
        sa.Column("thesis_id", UUID, sa.ForeignKey("theses.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("orcid", sa.String(32)),
        sa.Column("consent_file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("consent_recorded_at", TS),
    )

    op.create_table(
        "thesis_supervisors", *_base(),
        sa.Column("thesis_id", UUID, sa.ForeignKey("theses.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("is_main", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "thesis_sections", *_base(),
        sa.Column("thesis_id", UUID, sa.ForeignKey("theses.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("section_key", sa.String(32), nullable=False),
        sa.Column("content_ar", sa.Text),
        sa.Column("locator", sa.Text),
        sa.Column("quote", sa.Text),
        sa.Column("verification_status", sa.String(16), nullable=False,
                  server_default="unverified"),
        sa.UniqueConstraint("thesis_id", "section_key", name="uq_thesis_section"),
        # نفس حاجز Sprint 1: قسم موثق يحتاج موضعًا واقتباسًا.
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR (locator IS NOT NULL AND quote IS NOT NULL)",
            name="ck_thesis_section_verified_needs_locator",
        ),
    )

    op.create_table(
        "thesis_results", *_base(),
        sa.Column("thesis_id", UUID, sa.ForeignKey("theses.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("label_ar", sa.Text, nullable=False),
        sa.Column("result_code", sa.String(32)),
        sa.Column("variables", JSONB),
        sa.Column("table_figure_refs", JSONB),
        sa.Column("locator", sa.Text),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "overlap_policies", *_base(),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("thresholds", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("salami_min_dimensions", sa.Integer, nullable=False, server_default="3"),
        sa.Column("critical_dimensions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source_note_ar", sa.Text),
        sa.CheckConstraint("salami_min_dimensions >= 1", name="ck_overlap_policy_min_dims"),
    )

    op.create_table(
        "publication_opportunities", *_base(),
        sa.Column("thesis_id", UUID, sa.ForeignKey("theses.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("opportunity_kind", sa.String(32), nullable=False),
        sa.Column("paper_kind", sa.String(16), nullable=False),
        sa.Column("working_title_ar", sa.Text, nullable=False),
        sa.Column("working_title_en", sa.Text),
        sa.Column("research_question_ar", sa.Text),
        sa.Column("sample_refs", JSONB),
        sa.Column("variable_refs", JSONB),
        sa.Column("result_refs", JSONB),
        sa.Column("table_figure_refs", JSONB),
        sa.Column("published_output_refs", JSONB),
        sa.Column("draft_text_ar", sa.Text),
        sa.Column("readiness_score", sa.Numeric(5, 2)),
        sa.Column("readiness_outcome", sa.String(32)),
        sa.Column("readiness_components", JSONB),
        sa.Column("salami_alert", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("data_age_years", sa.Numeric(5, 2)),
        sa.Column("literature_age_years", sa.Numeric(5, 2)),
        sa.Column("rights_approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("rights_approved_at", TS),
        sa.Column("authorship_approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("authorship_approved_at", TS),
        sa.Column("status", sa.String(24), nullable=False, server_default="discovered"),
        sa.Column("converted_project_id", UUID,
                  sa.ForeignKey("research_projects.id", ondelete="SET NULL")),
        sa.CheckConstraint(_in("opportunity_kind", OPPORTUNITY_KINDS), name="ck_opportunity_kind"),
        sa.CheckConstraint(_in("paper_kind", PAPER_KINDS), name="ck_opportunity_paper_kind"),
        sa.CheckConstraint(_in("status", OPP_STATUSES), name="ck_opportunity_status"),
        sa.CheckConstraint(
            "readiness_outcome IS NULL OR " + _in("readiness_outcome", READINESS_OUTCOMES),
            name="ck_opportunity_readiness_outcome",
        ),
        # §23.9 / TC-06 — القيد الذي يحمل السبرنت: لا تقدّم بلا اعتماد الحقوق والتأليف.
        sa.CheckConstraint(
            "status <> 'ready_to_submit' OR "
            "(rights_approved_at IS NOT NULL AND rights_approved_by IS NOT NULL "
            " AND authorship_approved_at IS NOT NULL AND authorship_approved_by IS NOT NULL)",
            name="ck_opportunity_ready_requires_rights_and_authorship",
        ),
        # التحويل إلى مشروع يقع بعد التقدم، لا قبله.
        sa.CheckConstraint(
            "converted_project_id IS NULL OR status = 'converted'",
            name="ck_opportunity_converted_status",
        ),
    )
    op.create_index("ix_opportunities_thesis", "publication_opportunities",
                    ["tenant_id", "thesis_id", "status"])

    op.create_table(
        "opportunity_overlap_scores", *_base(),
        sa.Column("left_opportunity_id", UUID,
                  sa.ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("right_opportunity_id", UUID,
                  sa.ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("policy_id", UUID, sa.ForeignKey("overlap_policies.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("dimensions", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("exceeded", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("not_computed", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("salami_alert", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("resolution", sa.String(24)),
        sa.Column("resolution_note_ar", sa.Text),
        sa.Column("resolved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("resolved_at", TS),
        sa.UniqueConstraint("left_opportunity_id", "right_opportunity_id", "policy_id",
                            name="uq_overlap_pair"),
        sa.CheckConstraint("left_opportunity_id <> right_opportunity_id",
                           name="ck_overlap_distinct_pair"),
        sa.CheckConstraint(
            "resolution IS NULL OR resolution IN ('merged','justified','separated','rejected')",
            name="ck_overlap_resolution",
        ),
        # TC-05 — حسم التنبيه قرار بشري بسبب مكتوب.
        sa.CheckConstraint(
            "resolution IS NULL OR "
            "(resolved_by IS NOT NULL AND resolved_at IS NOT NULL "
            " AND resolution_note_ar IS NOT NULL)",
            name="ck_overlap_resolution_requires_actor_and_note",
        ),
    )

    op.create_table(
        "authorship_parties", *_base(),
        sa.Column("party_kind", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("orcid", sa.String(32)),
        sa.Column("affiliation_ar", sa.String(255)),
        # §24.2 — لا قيمة تمثل نموذجًا أو أجنتًا. المنع بغياب القيمة.
        sa.CheckConstraint("party_kind IN ('person','organization')",
                           name="ck_authorship_party_kind_human_or_org"),
    )

    op.create_table(
        "authorship_agreements", *_base(),
        sa.Column("opportunity_id", UUID,
                  sa.ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("party_id", UUID, sa.ForeignKey("authorship_parties.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("author_position", sa.Integer, nullable=False),
        sa.Column("is_corresponding", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("consent_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("consent_file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("consent_recorded_at", TS),
        sa.Column("order_change_log", JSONB),
        sa.UniqueConstraint("opportunity_id", "party_id", name="uq_authorship_agreement"),
        sa.UniqueConstraint("opportunity_id", "author_position", name="uq_authorship_position"),
        sa.CheckConstraint("author_position >= 1", name="ck_authorship_position"),
        sa.CheckConstraint("consent_status IN ('pending','granted','declined')",
                           name="ck_authorship_consent_status"),
        # موافقة ممنوحة بلا تاريخ ليست موافقة.
        sa.CheckConstraint(
            "consent_status <> 'granted' OR consent_recorded_at IS NOT NULL",
            name="ck_authorship_consent_needs_timestamp",
        ),
    )

    op.create_table(
        "credit_role_assignments", *_base(),
        sa.Column("agreement_id", UUID,
                  sa.ForeignKey("authorship_agreements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credit_role", sa.String(32), nullable=False),
        sa.Column("assigned_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("note_ar", sa.Text),
        sa.UniqueConstraint("agreement_id", "credit_role", name="uq_credit_role_assignment"),
        sa.CheckConstraint(_in("credit_role", CREDIT_ROLES), name="ck_credit_role"),
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
    for table in ("credit_role_assignments", "authorship_agreements", "authorship_parties",
                  "opportunity_overlap_scores", "publication_opportunities", "overlap_policies",
                  "thesis_results", "thesis_sections", "thesis_supervisors", "thesis_owners",
                  "theses"):
        op.drop_table(table)
