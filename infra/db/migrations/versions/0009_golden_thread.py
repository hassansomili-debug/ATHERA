"""الخيط الذهبي والمنهجية والبروتوكول | Golden thread, methodology, protocol (Sprint 5).

Revision ID: 0009
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

ELEMENT_TYPES = (
    "phenomenon", "problem", "gap", "question", "objective", "theory", "construct",
    "variable", "method", "instrument", "analysis", "result", "discussion",
    "recommendation", "hypothesis",
)
LINK_TYPES = ("addresses", "answers", "maps_to", "operationalizes", "measures",
              "analyzes", "produces", "supports", "explains", "derives_from")
STUDY_TYPES = ("quantitative", "qualitative", "mixed_methods", "experimental", "review")
SAMPLING = ("simple_random", "stratified_random", "systematic_random", "cluster_random",
            "census", "convenience", "purposive", "snowball", "quota")
VARIABLE_ROLES = ("independent", "dependent", "mediator", "moderator", "control")

TENANT_TABLES = [
    "theories", "thread_elements", "thread_links", "constructs", "variables",
    "methods", "instruments", "instrument_items", "protocols",
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
        "theories",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("rationale_ar", sa.Text),
        sa.Column("rationale_en", sa.Text),
        sa.Column("alternatives", JSONB),
        sa.Column("limitations_ar", sa.Text),
        sa.Column("source_id", UUID, sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("gate", sa.String(8)),
    )

    op.create_table(
        "thread_elements",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("element_type", sa.String(24), nullable=False),
        sa.Column("label_ar", sa.Text, nullable=False),
        sa.Column("label_en", sa.Text),
        sa.Column("detail_ar", sa.Text),
        sa.Column("detail_en", sa.Text),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="1"),
        sa.Column("theory_id", UUID, sa.ForeignKey("theories.id", ondelete="SET NULL")),
        sa.Column("metadata_json", JSONB),
        sa.Column("approved_at", TS),
        sa.CheckConstraint(_in("element_type", ELEMENT_TYPES), name="ck_thread_element_type"),
    )
    op.create_index("ix_thread_elements_project", "thread_elements",
                    ["tenant_id", "project_id", "element_type"])

    op.create_table(
        "thread_links",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_element_id", UUID,
                  sa.ForeignKey("thread_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_element_id", UUID,
                  sa.ForeignKey("thread_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("link_type", sa.String(24), nullable=False),
        sa.Column("note_ar", sa.Text),
        sa.UniqueConstraint("source_element_id", "target_element_id", "link_type",
                            name="uq_thread_link"),
        sa.CheckConstraint(_in("link_type", LINK_TYPES), name="ck_thread_link_type"),
        # عنصر لا يرتبط بنفسه — رابط ذاتي يفسد كل فحوص الوصول.
        sa.CheckConstraint("source_element_id <> target_element_id", name="ck_thread_link_no_self"),
    )

    op.create_table(
        "constructs",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("conceptual_definition_ar", sa.Text),
        sa.Column("theory_id", UUID, sa.ForeignKey("theories.id", ondelete="SET NULL")),
        sa.Column("measurement_model", sa.String(16)),
        sa.CheckConstraint(
            "measurement_model IS NULL OR measurement_model IN ('reflective','formative')",
            name="ck_construct_measurement_model",
        ),
    )

    op.create_table(
        "variables",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("construct_id", UUID, sa.ForeignKey("constructs.id", ondelete="SET NULL")),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("operational_definition_ar", sa.Text),
        sa.Column("scale_type", sa.String(24)),
        sa.Column("appears_in_title", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint(_in("role", VARIABLE_ROLES), name="ck_variable_role"),
        # §16.1 — متغير مرتبط بمُنشأ بلا تعريف إجرائي لا يُقاس، فلا يُقبل.
        sa.CheckConstraint(
            "(construct_id IS NULL) OR (operational_definition_ar IS NOT NULL)",
            name="ck_variable_construct_needs_operational_definition",
        ),
    )

    op.create_table(
        "methods",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("study_type", sa.String(24), nullable=False),
        sa.Column("design_label_ar", sa.String(255)),
        sa.Column("design_family", sa.String(32)),
        sa.Column("sampling_strategy", sa.String(32)),
        sa.Column("population_ar", sa.Text),
        sa.Column("sample_size", sa.Integer),
        sa.Column("sample_size_justification_ar", sa.Text),
        sa.Column("analysis_plan_ar", sa.Text),
        sa.Column("details", JSONB),
        sa.Column("gate", sa.String(8)),
        sa.CheckConstraint(_in("study_type", STUDY_TYPES), name="ck_method_study_type"),
        sa.CheckConstraint(
            "sampling_strategy IS NULL OR " + _in("sampling_strategy", SAMPLING),
            name="ck_method_sampling",
        ),
    )

    op.create_table(
        "instruments",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("instrument_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.Text),
        sa.Column("is_translated", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("back_translation_done", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("pilot_done", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("reliability", JSONB),
        sa.Column("validity", JSONB),
        sa.Column("gate", sa.String(8)),
        # §16.1 — أداة مترجمة بلا ترجمة عكسية ادعاء غير مكتمل.
        sa.CheckConstraint(
            "(NOT is_translated) OR (back_translation_done IS NOT NULL)",
            name="ck_instrument_translation",
        ),
    )

    op.create_table(
        "instrument_items",
        *_base(),
        sa.Column("instrument_id", UUID, sa.ForeignKey("instruments.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("variable_id", UUID, sa.ForeignKey("variables.id", ondelete="SET NULL")),
        sa.Column("item_text_ar", sa.Text, nullable=False),
        sa.Column("item_code", sa.String(32)),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="1"),
    )

    op.create_table(
        "protocols",
        *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_label", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("title_ar", sa.Text, nullable=False),
        sa.Column("summary_ar", sa.Text),
        sa.Column("summary_en", sa.Text),
        sa.Column("current_gate", sa.String(8), nullable=False, server_default="G2"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("approved_gate", sa.String(8)),
        sa.Column("approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("approved_at", TS),
        sa.Column("consistency_snapshot", JSONB),
        sa.CheckConstraint("status IN ('draft','submitted','approved','superseded')",
                           name="ck_protocol_status"),
        # §9 — الاعتماد كائن له فاعل وتاريخ وبوابة، أو ليس اعتمادًا.
        sa.CheckConstraint(
            "(status <> 'approved') OR "
            "(approved_by IS NOT NULL AND approved_at IS NOT NULL AND approved_gate IS NOT NULL)",
            name="ck_protocol_approved_requires_actor",
        ),
        # الاعتماد يقع على حالة اتساق معروفة، لا على المجهول.
        sa.CheckConstraint(
            "(status <> 'approved') OR (consistency_snapshot IS NOT NULL)",
            name="ck_protocol_approved_requires_snapshot",
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
    for table in ("protocols", "instrument_items", "instruments", "methods", "variables",
                  "constructs", "thread_links", "thread_elements", "theories"):
        op.drop_table(table)
