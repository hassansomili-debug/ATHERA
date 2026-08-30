"""الأدبيات وسجل الأدلة | Literature and evidence ledger (Sprint 4).

القيود هنا هي §14.5 محوّلة إلى قواعد لا تُخترق:
  • مقتطف من مصدر بلا نص متاح ⇒ مستحيل.
  • ربط بمصدر مسحوب بلا إقرار ⇒ مستحيل.
  • مصدر «متحقق» بلا سجل خارجي وتاريخ ⇒ مستحيل.

Revision ID: 0008
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

ACCESS_STATES = (
    "open_access_full_text", "user_uploaded_rights_confirmed", "licensed_institutional_access",
    "abstract_metadata_only", "restricted_no_processing_right",
)
TEXT_BEARING = ("open_access_full_text", "user_uploaded_rights_confirmed",
                "licensed_institutional_access")
SUPPORT_LEVELS = ("direct", "partial", "contextual", "contradictory")
CLAIM_TYPES = ("empirical", "theoretical", "contextual", "interpretive")
RETRACTION_STATES = ("none", "correction", "expression_of_concern", "retracted", "unknown")

TENANT_TABLES = [
    "journals", "journal_indexing_records", "authors", "sources", "source_versions",
    "source_authors", "evidence_excerpts", "claims", "claim_evidence_links",
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
        "journals",
        *_base(),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("name_ar", sa.String(512)),
        sa.Column("issn", sa.String(16)),
        sa.Column("eissn", sa.String(16)),
        sa.Column("publisher", sa.String(255)),
        sa.Column("country", sa.String(64)),
        sa.Column("is_open_access", sa.Boolean),
        sa.Column("external_ids", JSONB),
    )

    op.create_table(
        "journal_indexing_records",
        *_base(),
        sa.Column("journal_id", UUID, sa.ForeignKey("journals.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("index_name", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("coverage_from", sa.Date),
        sa.Column("coverage_to", sa.Date),
        sa.Column("evidence_source", sa.String(64), nullable=False),
        # §39 — «Journal index status بلا تاريخ تحقق: صفر».
        sa.Column("last_verified_at", TS, nullable=False),
    )

    op.create_table(
        "authors",
        *_base(),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("orcid", sa.String(32)),
        sa.Column("external_ids", JSONB),
    )

    op.create_table(
        "sources",
        *_base(),
        sa.Column("doi", sa.String(255)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("publication_year", sa.Integer),
        sa.Column("journal_id", UUID, sa.ForeignKey("journals.id", ondelete="SET NULL")),
        sa.Column("journal_name_raw", sa.String(512)),
        sa.Column("theory", sa.Text),
        sa.Column("method", sa.Text),
        sa.Column("sample", sa.Text),
        sa.Column("findings", sa.Text),
        sa.Column("limitations", sa.Text),
        sa.Column("retraction_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("retraction_detail", sa.Text),
        sa.Column("access_state", sa.String(40), nullable=False,
                  server_default="abstract_metadata_only"),
        sa.Column("last_verified_at", TS),
        sa.Column("registry", sa.String(32)),
        sa.Column("registry_id", sa.String(255)),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("raw_metadata", JSONB),
        sa.UniqueConstraint("tenant_id", "doi", name="uq_sources_doi"),
        sa.CheckConstraint(_in("access_state", ACCESS_STATES), name="ck_source_access_state"),
        sa.CheckConstraint(_in("retraction_status", RETRACTION_STATES), name="ck_source_retraction"),
        sa.CheckConstraint("verification_status IN ('unverified','verified','rejected')",
                           name="ck_source_status"),
        # §14.5 — «متحقق» يعني: سجل خارجي، ومعرّف فيه، وتاريخ تحقق. أو ملف
        # مرفوع بحقوق مؤكدة. لا ثالث لهما.
        sa.CheckConstraint(
            "(verification_status <> 'verified') OR "
            "((registry IS NOT NULL AND registry_id IS NOT NULL AND last_verified_at IS NOT NULL)"
            " OR (file_id IS NOT NULL AND access_state = 'user_uploaded_rights_confirmed'))",
            name="ck_source_verified_requires_registry_or_upload",
        ),
    )
    op.create_index("ix_sources_retraction", "sources", ["tenant_id", "retraction_status"])

    op.create_table(
        "source_versions",
        *_base(),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("checked_at", TS, nullable=False),
        sa.Column("registry", sa.String(32), nullable=False),
        sa.Column("retraction_status", sa.String(32), nullable=False),
        sa.Column("access_state", sa.String(40), nullable=False),
        sa.Column("snapshot", JSONB),
    )

    op.create_table(
        "source_authors",
        *_base(),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("author_id", UUID, sa.ForeignKey("authors.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("source_id", "position", name="uq_source_author_position"),
    )

    op.create_table(
        "evidence_excerpts",
        *_base(),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("locator", sa.Text, nullable=False),
        sa.Column("access_basis", sa.String(40), nullable=False),
        sa.Column("chunk_id", UUID, sa.ForeignKey("document_chunks.id", ondelete="SET NULL")),
        sa.Column("note_ar", sa.Text),
        sa.Column("note_en", sa.Text),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.CheckConstraint("length(quote) > 0", name="ck_excerpt_quote_required"),
        sa.CheckConstraint("length(locator) > 0", name="ck_excerpt_locator_required"),
        # §14.5 القاعدة 3 — المقتطف لا يوجد إلا حيث يوجد نص متاح قانونًا.
        sa.CheckConstraint(_in("access_basis", TEXT_BEARING), name="ck_excerpt_requires_text_access"),
    )

    op.create_table(
        "claims",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE")),
        sa.Column("text_ar", sa.Text, nullable=False),
        sa.Column("text_en", sa.Text),
        sa.Column("claim_type", sa.String(24), nullable=False),
        sa.Column("section", sa.String(64)),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="unverified"),
        sa.Column("reviewed_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", TS),
        sa.Column("is_labelled_inference", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint(_in("claim_type", CLAIM_TYPES), name="ck_claim_type"),
        sa.CheckConstraint(
            "status IN ('draft','supported','evidence_gap','contradicted','final')",
            name="ck_claim_status",
        ),
        # §14.5 القاعدة 1 — النسخة النهائية تحتاج مراجعًا وتاريخًا.
        sa.CheckConstraint(
            "(status <> 'final') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)",
            name="ck_claim_final_requires_reviewer",
        ),
    )
    op.create_index("ix_claims_project", "claims", ["tenant_id", "project_id", "status"])

    op.create_table(
        "claim_evidence_links",
        *_base(),
        sa.Column("claim_id", UUID, sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("excerpt_id", UUID, sa.ForeignKey("evidence_excerpts.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("support_level", sa.String(16), nullable=False),
        sa.Column("retraction_acknowledged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("acknowledgement_note", sa.Text),
        sa.Column("reviewed_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("resolution_note_ar", sa.Text),
        sa.Column("resolution_note_en", sa.Text),
        sa.UniqueConstraint("claim_id", "excerpt_id", name="uq_claim_evidence"),
        sa.CheckConstraint(_in("support_level", SUPPORT_LEVELS), name="ck_link_support_level"),
        # §14.5 القاعدة 2 — الإقرار بلا سياق مكتوب ليس إقرارًا.
        sa.CheckConstraint(
            "(NOT retraction_acknowledged) OR (acknowledgement_note IS NOT NULL)",
            name="ck_link_acknowledgement_needs_note",
        ),
    )

    # §14.5 القاعدة 2 على مستوى قاعدة البيانات: لا ربط بمسحوب بلا إقرار.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_retraction_acknowledgement() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            source_state text;
        BEGIN
            SELECT retraction_status INTO source_state FROM sources WHERE id = NEW.source_id;
            IF source_state IN ('retracted','expression_of_concern')
               AND (NOT NEW.retraction_acknowledged OR NEW.acknowledgement_note IS NULL) THEN
                RAISE EXCEPTION
                    'citing a % source requires an explicit acknowledgement and context (PRD 14.5)',
                    source_state
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_claim_evidence_retraction
            BEFORE INSERT OR UPDATE ON claim_evidence_links
            FOR EACH ROW EXECUTE FUNCTION enforce_retraction_acknowledgement();
        """
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
    op.execute("DROP TRIGGER IF EXISTS trg_claim_evidence_retraction ON claim_evidence_links")
    op.execute("DROP FUNCTION IF EXISTS enforce_retraction_acknowledgement()")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in ("claim_evidence_links", "claims", "evidence_excerpts", "source_authors",
                  "source_versions", "sources", "authors", "journal_indexing_records", "journals"):
        op.drop_table(table)
