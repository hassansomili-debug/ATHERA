"""المخطوطة والمجلات والمراجعة | Manuscripts, journals and review (Sprint 7).

قيدان يحملان وزن السبرنت:
  • `review_patches` تبدأ `proposed` دائمًا، وتطبيقها يستلزم فاعلًا وتاريخًا
    و**نسخة جديدة** — §21 تمنع تعديل النسخة المعتمدة مباشرة.
  • `journal_matches` بلا حقل لاحتمال قبول، وطبقة الثقة لا تُثبَّت بلا تاريخ
    تحقق (§20.3، §39).

Revision ID: 0011
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

SECTIONS = ("title", "abstract", "keywords", "introduction", "problem_gap",
            "literature_review", "theory", "hypotheses_questions", "method", "results",
            "discussion", "contributions", "implications", "limitations",
            "future_research", "conclusion", "declarations", "references")
TIERS = ("A", "B", "C", "D", "X")
REVIEWERS = ("theoretical", "methodological", "statistical", "editorial", "integrity")
READINESS = ("not_ready", "major_revision", "minor_revision", "ready_to_submit")
PATCH_STATUSES = ("proposed", "applied", "rejected")

TENANT_TABLES = [
    "manuscripts", "manuscript_versions", "manuscript_sections", "journal_profiles",
    "journal_policy_checks", "journal_matches", "review_rounds", "reviewer_reports",
    "review_patches", "submission_packages",
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
        "manuscripts", *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title_ar", sa.Text, nullable=False),
        sa.Column("title_en", sa.Text),
        sa.Column("language", sa.String(5), nullable=False, server_default="ar"),
        sa.Column("current_version_id", UUID),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("g9_approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("g9_approved_at", TS),
        sa.Column("g9_readiness_snapshot", JSONB),
        sa.CheckConstraint("language IN ('ar','en')", name="ck_manuscript_language"),
        sa.CheckConstraint("status IN ('draft','in_review','ready_for_journal','submitted')",
                           name="ck_manuscript_status"),
        # §9 — G9 اعتماد له فاعل وتاريخ ولقطة جاهزية.
        sa.CheckConstraint(
            "g9_approved_at IS NULL OR "
            "(g9_approved_by IS NOT NULL AND g9_readiness_snapshot IS NOT NULL)",
            name="ck_manuscript_g9_requires_actor_and_snapshot",
        ),
    )

    op.create_table(
        "manuscript_versions", *_base(),
        sa.Column("manuscript_id", UUID, sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_label", sa.String(32), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("change_reason_ar", sa.Text, nullable=False),
        sa.Column("supersedes_id", UUID),
        sa.UniqueConstraint("manuscript_id", "version_label", name="uq_manuscript_version"),
    )

    op.create_table(
        "manuscript_sections", *_base(),
        sa.Column("version_id", UUID,
                  sa.ForeignKey("manuscript_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_key", sa.String(32), nullable=False),
        sa.Column("text_ar", sa.Text),
        sa.Column("text_en", sa.Text),
        sa.Column("claim_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("analysis_run_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("version_id", "section_key", name="uq_manuscript_section"),
        sa.CheckConstraint(_in("section_key", SECTIONS), name="ck_manuscript_section_key"),
    )

    op.create_table(
        "journal_profiles", *_base(),
        sa.Column("journal_id", UUID, sa.ForeignKey("journals.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("trust_tier", sa.String(1)),
        sa.Column("tier_computed_at", TS),
        sa.Column("scope_keywords", JSONB),
        sa.Column("recent_article_keywords", JSONB),
        sa.Column("accepted_methods", JSONB),
        sa.Column("apc_usd", sa.Numeric(10, 2)),
        sa.Column("oa_model", sa.String(24)),
        sa.Column("ai_policy_ar", sa.Text),
        sa.Column("submission_requirements", JSONB),
        sa.Column("median_review_days", sa.Integer),
        sa.Column("is_discontinued", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_suspicious", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint("trust_tier IS NULL OR " + _in("trust_tier", TIERS),
                           name="ck_journal_trust_tier"),
        # §20.1/§39 — طبقة بلا تاريخ حساب ادعاء بلا زمن.
        sa.CheckConstraint(
            "trust_tier IS NULL OR tier_computed_at IS NOT NULL",
            name="ck_journal_tier_requires_timestamp",
        ),
    )

    op.create_table(
        "journal_policy_checks", *_base(),
        sa.Column("journal_id", UUID, sa.ForeignKey("journals.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("verification_point", sa.String(24), nullable=False),
        sa.Column("checked_at", TS, nullable=False),
        sa.Column("checked_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("indexing_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.CheckConstraint(
            "verification_point IN ('shortlisting','submission','acceptance','publication')",
            name="ck_journal_check_point",
        ),
        sa.CheckConstraint("outcome IN ('confirmed','changed','needs_reverification')",
                           name="ck_journal_check_outcome"),
    )

    op.create_table(
        "journal_matches", *_base(),
        sa.Column("manuscript_id", UUID, sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("journal_id", UUID, sa.ForeignKey("journals.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("fit_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("criteria", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("trust_tier", sa.String(1), nullable=False),
        sa.Column("blockers", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("uncomputed", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("indexing_verified_at", TS),
        sa.Column("g10_approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("g10_approved_at", TS),
        sa.UniqueConstraint("manuscript_id", "journal_id", name="uq_journal_match"),
        sa.CheckConstraint(_in("trust_tier", TIERS), name="ck_match_trust_tier"),
        # TC-04 / §20.3 — لا اعتماد G10 بلا إعادة تحقق من الفهرسة.
        sa.CheckConstraint(
            "g10_approved_at IS NULL OR "
            "(g10_approved_by IS NOT NULL AND indexing_verified_at IS NOT NULL)",
            name="ck_match_g10_requires_fresh_indexing",
        ),
    )

    op.create_table(
        "review_rounds", *_base(),
        sa.Column("manuscript_id", UUID, sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_id", UUID,
                  sa.ForeignKey("manuscript_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("round_number", sa.Integer, nullable=False),
        sa.Column("readiness_status", sa.String(24), nullable=False),
        sa.Column("major_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("minor_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reviewers_missing", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.UniqueConstraint("manuscript_id", "round_number", name="uq_review_round"),
        sa.CheckConstraint(_in("readiness_status", READINESS), name="ck_review_readiness"),
    )

    op.create_table(
        "reviewer_reports", *_base(),
        sa.Column("round_id", UUID, sa.ForeignKey("review_rounds.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("reviewer_role", sa.String(24), nullable=False),
        sa.Column("strengths", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("major_concerns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("minor_concerns", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rejection_reasons", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("agent_run_id", UUID),
        sa.UniqueConstraint("round_id", "reviewer_role", name="uq_reviewer_report"),
        sa.CheckConstraint(_in("reviewer_role", REVIEWERS), name="ck_reviewer_role"),
    )

    op.create_table(
        "review_patches", *_base(),
        sa.Column("report_id", UUID, sa.ForeignKey("reviewer_reports.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("section_key", sa.String(32), nullable=False),
        sa.Column("rationale_ar", sa.Text, nullable=False),
        sa.Column("rationale_en", sa.Text),
        sa.Column("suggested_text_ar", sa.Text),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", TS),
        sa.Column("applied_in_version_id", UUID,
                  sa.ForeignKey("manuscript_versions.id", ondelete="SET NULL")),
        sa.CheckConstraint(_in("section_key", SECTIONS), name="ck_patch_section_key"),
        sa.CheckConstraint(_in("status", PATCH_STATUSES), name="ck_patch_status"),
        # §21 — الرقعة لا تُطبَّق إلا بفاعل بشري، وفي نسخة جديدة لا في المعتمدة.
        sa.CheckConstraint(
            "status <> 'applied' OR "
            "(decided_by IS NOT NULL AND decided_at IS NOT NULL "
            " AND applied_in_version_id IS NOT NULL)",
            name="ck_patch_applied_requires_actor_and_new_version",
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_patch_rejected_requires_actor",
        ),
    )

    op.create_table(
        "submission_packages", *_base(),
        sa.Column("manuscript_id", UUID, sa.ForeignKey("manuscripts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("journal_match_id", UUID,
                  sa.ForeignKey("journal_matches.id", ondelete="SET NULL")),
        sa.Column("items_present", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_required", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("missing_optional", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("assembled_at", TS, nullable=False),
        sa.Column("is_complete", sa.Boolean, nullable=False, server_default=sa.false()),
        # §22.1 — «مكتملة» تعني فعلًا لا عنصر إلزاميًا ناقصًا.
        sa.CheckConstraint(
            "(NOT is_complete) OR missing_required = '[]'::jsonb",
            name="ck_package_complete_means_nothing_missing",
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
    for table in ("submission_packages", "review_patches", "reviewer_reports", "review_rounds",
                  "journal_matches", "journal_policy_checks", "journal_profiles",
                  "manuscript_sections", "manuscript_versions", "manuscripts"):
        op.drop_table(table)
