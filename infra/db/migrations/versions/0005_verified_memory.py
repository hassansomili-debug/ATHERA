"""الذاكرة الموثقة | Verified memory schema (Sprint 1).

القيود هنا ليست تجميلًا: قيد `ck_memory_verified_requires_verifier` وقيد
`ck_memory_source_path` هما ما يجعلان قاعدة §7.4 غير قابلة للالتفاف من أي
كود مستقبلي — بما في ذلك الأجنتات في السبرنتات القادمة.

Revision ID: 0005
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

MEMORY_CATEGORIES = (
    "researcher_fact", "promotion_policy", "verified_evidence", "project_decision",
    "working_hypothesis", "journal_fact", "analysis_result", "temporary_context",
)
PROMOTION_PATHS = ("external_source", "upload", "analysis_run", "user_statement")

TENANT_TABLES = [
    "researcher_profiles", "researcher_skills", "researcher_memories",
    "document_chunks", "extraction_runs", "fact_candidates",
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


def _in_list(column: str, values: tuple[str, ...]) -> str:
    joined = ",".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.create_table(
        "researcher_profiles",
        *_base(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", UUID, sa.ForeignKey("organizations.id", ondelete="SET NULL")),
        sa.Column("institution_ar", sa.String(255)),
        sa.Column("institution_en", sa.String(255)),
        sa.Column("college_ar", sa.String(255)),
        sa.Column("college_en", sa.String(255)),
        sa.Column("department_ar", sa.String(255)),
        sa.Column("department_en", sa.String(255)),
        sa.Column("current_rank", sa.String(64)),
        sa.Column("target_rank", sa.String(64)),
        sa.Column("rank_started_on", sa.Date),
        sa.Column("primary_field_ar", sa.String(255)),
        sa.Column("primary_field_en", sa.String(255)),
        sa.Column("related_fields", JSONB),
        sa.Column("keywords", JSONB),
        sa.Column("orcid", sa.String(32)),
        sa.Column("scholar_ids", JSONB),
        sa.Column("writing_preferences", JSONB),
        sa.Column("excluded_topics", JSONB),
        sa.Column("future_interests", JSONB),
        sa.Column("g0_approved_at", TS),
        sa.Column("g0_approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_researcher_profiles_user"),
    )

    op.create_table(
        "researcher_memories",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE")),
        sa.Column("memory_category", sa.String(32), nullable=False),
        sa.Column("statement_ar", sa.Text, nullable=False),
        sa.Column("statement_en", sa.Text),
        sa.Column("value", JSONB),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("source_locator", sa.Text),
        sa.Column("source_quote", sa.Text),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("verified_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("verified_at", TS),
        sa.Column("expires_at", TS),
        sa.Column("superseded_by", UUID),
        sa.CheckConstraint(_in_list("memory_category", MEMORY_CATEGORIES), name="ck_memory_category"),
        # §7.4 — المسارات الأربعة، لا خامس لها.
        sa.CheckConstraint(_in_list("source_type", PROMOTION_PATHS), name="ck_memory_source_path"),
        sa.CheckConstraint(
            "verification_status IN ('unverified','approved','rejected','verified')",
            name="ck_memory_status",
        ),
        # لا «موثق» بلا مُحقِّق وتاريخ (§7.4، TC-01).
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR "
            "(verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_memory_verified_requires_verifier",
        ),
        # ذاكرة من ملف يجب أن تحمل موضعًا واقتباسًا — وإلا فهي ادعاء بلا أثر.
        sa.CheckConstraint(
            "(source_type <> 'upload') OR "
            "(source_file_id IS NOT NULL AND source_locator IS NOT NULL AND source_quote IS NOT NULL)",
            name="ck_memory_upload_requires_locator",
        ),
        # temporary_context وحدها تملك صلاحية منتهية (§7.3).
        sa.CheckConstraint(
            "(expires_at IS NULL) OR (memory_category = 'temporary_context')",
            name="ck_memory_expiry_only_temporary",
        ),
    )
    op.create_index("ix_memory_category", "researcher_memories",
                    ["tenant_id", "memory_category", "verification_status"])

    op.create_table(
        "researcher_skills",
        *_base(),
        sa.Column("profile_id", UUID, sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("skill_kind", sa.String(24), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("evidence_level", sa.String(24), nullable=False, server_default="claimed"),
        sa.Column("memory_id", UUID, sa.ForeignKey("researcher_memories.id", ondelete="SET NULL")),
        sa.CheckConstraint(
            "skill_kind IN ('theory','method','software','language','design')",
            name="ck_skill_kind",
        ),
    )

    op.create_table(
        "document_chunks",
        *_base(),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("locator", sa.Text, nullable=False),
        sa.Column("page_number", sa.Integer),
        sa.Column("section_path", sa.Text),
        sa.Column("paragraph_index", sa.Integer),
        sa.Column("char_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_untrusted", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("embedding_model", sa.String(96)),
        sa.UniqueConstraint("file_id", "seq", name="uq_document_chunks_seq"),
        sa.CheckConstraint("length(text) > 0", name="ck_document_chunks_text_not_empty"),
        sa.CheckConstraint("length(locator) > 0", name="ck_document_chunks_locator_required"),
    )
    # §33.1 — عمود المتجه يُضاف بـSQL خام لأن نوع vector من الامتداد لا من SQLAlchemy.
    op.execute("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)")
    # فهرس ثلاثي الحروف لتسريع البحث النصي العربي. هو **تحسين أداء لا قيد
    # صحة**: غيابه يبطئ البحث ولا يغيّر نتيجة. لذلك يُتخطى بتحذير صريح على
    # استضافة تقيّد الامتدادات، بدل أن يمنع تشغيل المنصة كلها.
    op.execute(
        """
        DO $$
        BEGIN
            CREATE EXTENSION IF NOT EXISTS pg_trgm;
            CREATE INDEX IF NOT EXISTS ix_document_chunks_text_trgm
                ON document_chunks USING gin (text gin_trgm_ops);
        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING
                'pg_trgm unavailable: trigram index skipped. Arabic text search will '
                'fall back to a sequential scan. Detail: %', SQLERRM;
        END
        $$;
        """
    )

    op.create_table(
        "extraction_runs",
        *_base(),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extractor", sa.String(32), nullable=False),
        sa.Column("model_run_id", UUID, sa.ForeignKey("model_runs.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("chunks_parsed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("candidates_proposed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("candidates_rejected_unquoted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS),
        sa.Column("error", sa.Text),
    )

    op.create_table(
        "fact_candidates",
        *_base(),
        sa.Column("extraction_run_id", UUID,
                  sa.ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", UUID, sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("memory_category", sa.String(32), nullable=False),
        sa.Column("field_key", sa.String(64)),
        sa.Column("statement_ar", sa.Text, nullable=False),
        sa.Column("statement_en", sa.Text),
        sa.Column("value", JSONB),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("locator", sa.Text, nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", TS),
        sa.Column("decision_reason", sa.Text),
        sa.Column("resulting_memory_id", UUID,
                  sa.ForeignKey("researcher_memories.id", ondelete="SET NULL")),
        sa.CheckConstraint(_in_list("memory_category", MEMORY_CATEGORIES),
                           name="ck_candidate_category"),
        sa.CheckConstraint("status IN ('unverified','approved','rejected')",
                           name="ck_candidate_status"),
        sa.CheckConstraint("length(quote) > 0", name="ck_candidate_quote_required"),
        # قرار بلا فاعل وتاريخ غير مقبول — الرفض قرار أيضًا.
        sa.CheckConstraint(
            "(status = 'unverified') OR (decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_candidate_decided_requires_actor",
        ),
        # الاعتماد وحده ينتج ذاكرة؛ الرفض لا ينتج شيئًا.
        sa.CheckConstraint(
            "(status = 'approved') OR (resulting_memory_id IS NULL)",
            name="ck_candidate_memory_only_when_approved",
        ),
    )
    op.create_index("ix_fact_candidates_status", "fact_candidates", ["tenant_id", "status"])

    # RLS على كل جدول جديد — نفس قاعدة ADR-0002، بلا استثناء.
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
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON "
        + ", ".join(TENANT_TABLES)
        + " TO athera_app"
    )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_text_trgm")
    for table in ("fact_candidates", "extraction_runs", "document_chunks",
                  "researcher_skills", "researcher_memories", "researcher_profiles"):
        op.drop_table(table)
