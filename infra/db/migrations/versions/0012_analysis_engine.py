"""محرك التحليل | Analysis engine (Sprint 8).

ثلاثة قيود تحمل السبرنت:
  • RAW لا يُعدَّل — trigger يعيد استخدام `forbid_row_mutation()` من ترحيل 0003
    (TC-07، §17.2، §39).
  • التشغيلة لا تعمل إلا على نسخة مجمَّدة (§17.3).
  • مخرَج بلا تشغيلة مستحيل (§39).

Revision ID: 0012
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)

STATES = ("raw", "cleaned", "analysis_locked", "derived")
TEST_KINDS = ("descriptive", "reliability", "validity", "correlation", "regression",
              "anova", "ancova", "t_test", "chi_square", "sem", "pls_sem",
              "mediation", "moderation", "factor_analysis", "thematic_coding")
ORIGINS = ("planned", "exploratory")
TOOLS = ("spss", "smartpls", "nvivo", "python", "r")
OUTPUT_KINDS = ("table", "figure", "statistic", "model")

TENANT_TABLES = [
    "datasets", "dataset_versions", "data_dictionaries", "analysis_plans",
    "planned_tests", "analysis_runs", "analysis_outputs", "interpretations", "tool_exports",
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
        "datasets", *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255)),
        sa.Column("description_ar", sa.Text),
        sa.Column("classification", sa.String(4), nullable=False, server_default="C3"),
        sa.CheckConstraint("classification IN ('C0','C1','C2','C3','C4')",
                           name="ck_dataset_classification"),
    )

    op.create_table(
        "dataset_versions", *_base(),
        sa.Column("dataset_id", UUID, sa.ForeignKey("datasets.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("parent_version_id", UUID,
                  sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT")),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("row_count", sa.Integer),
        sa.Column("change_note_ar", sa.Text),
        sa.Column("frozen_at", TS),
        sa.Column("freeze_id", sa.String(32)),
        sa.Column("frozen_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.UniqueConstraint("freeze_id", name="uq_dataset_freeze_id"),
        sa.CheckConstraint(_in("state", STATES), name="ck_dataset_version_state"),
        # §17.2 — الخام بلا أصل، وكل ما عداه يعرف أصله.
        sa.CheckConstraint(
            "(state = 'raw' AND parent_version_id IS NULL) OR "
            "(state <> 'raw' AND parent_version_id IS NOT NULL)",
            name="ck_dataset_version_lineage",
        ),
        # نسخة مشتقة بلا سبب تغيير تُخفي ما فُعل بالبيانات.
        sa.CheckConstraint(
            "state = 'raw' OR change_note_ar IS NOT NULL",
            name="ck_dataset_version_change_note",
        ),
        # §17.3 — التجميد له معرّف وفاعل وتاريخ، أو ليس تجميدًا.
        sa.CheckConstraint(
            "(frozen_at IS NULL AND freeze_id IS NULL AND frozen_by IS NULL) OR "
            "(frozen_at IS NOT NULL AND freeze_id IS NOT NULL AND frozen_by IS NOT NULL)",
            name="ck_dataset_freeze_complete",
        ),
    )
    op.create_index("ix_dataset_versions_dataset", "dataset_versions",
                    ["tenant_id", "dataset_id", "state"])

    # TC-07 / §39 — RAW غير قابل للتعديل. الدالة موجودة من ترحيل 0003.
    op.execute(
        """
        CREATE TRIGGER trg_raw_dataset_version_immutable
            BEFORE UPDATE OR DELETE ON dataset_versions
            FOR EACH ROW WHEN (OLD.state = 'raw')
            EXECUTE FUNCTION forbid_row_mutation();
        """
    )
    # نسخة مجمَّدة لا تُعدَّل أيضًا: التجميد يعني ثباتًا لا وسمًا.
    #
    # الشرط على OLD وحده — وهو الصحيح دلاليًا لا مجرد المتاح تقنيًا:
    # تجميد نسخة غير مجمَّدة له OLD.frozen_at IS NULL فلا يُفعّل المشغّل،
    # وما إن تُجمَّد حتى يمتنع تعديلها وحذفها معًا. (وشرط على NEW مرفوض
    # أصلًا في مشغّل DELETE — لا صف جديد هناك.)
    op.execute(
        """
        CREATE TRIGGER trg_frozen_dataset_version_immutable
            BEFORE UPDATE OR DELETE ON dataset_versions
            FOR EACH ROW WHEN (OLD.frozen_at IS NOT NULL)
            EXECUTE FUNCTION forbid_row_mutation();
        """
    )

    op.create_table(
        "data_dictionaries", *_base(),
        sa.Column("dataset_version_id", UUID,
                  sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_name", sa.String(128), nullable=False),
        sa.Column("label_ar", sa.String(255)),
        sa.Column("variable_id", UUID, sa.ForeignKey("variables.id", ondelete="SET NULL")),
        sa.Column("scale_type", sa.String(24)),
        sa.Column("value_labels", JSONB),
        sa.Column("is_pii", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("dataset_version_id", "column_name", name="uq_data_dictionary_column"),
    )

    op.create_table(
        "analysis_plans", *_base(),
        sa.Column("project_id", UUID, sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("version_label", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("summary_ar", sa.Text),
        sa.Column("lock_hash", sa.String(64)),
        sa.Column("approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("approved_at", TS),
        sa.UniqueConstraint("project_id", "version_label", name="uq_analysis_plan_version"),
        # §9 G7 — الاعتماد يقفل ويسجّل فاعله وتاريخه معًا.
        sa.CheckConstraint(
            "(lock_hash IS NULL AND approved_by IS NULL AND approved_at IS NULL) OR "
            "(lock_hash IS NOT NULL AND approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_analysis_plan_lock_complete",
        ),
    )

    op.create_table(
        "planned_tests", *_base(),
        sa.Column("plan_id", UUID, sa.ForeignKey("analysis_plans.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("test_key", sa.String(64), nullable=False),
        sa.Column("test_kind", sa.String(32), nullable=False),
        sa.Column("variables", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("hypothesis_id", UUID, sa.ForeignKey("thread_elements.id", ondelete="SET NULL")),
        sa.Column("note_ar", sa.Text),
        sa.UniqueConstraint("plan_id", "test_key", name="uq_planned_test_key"),
        sa.CheckConstraint(_in("test_kind", TEST_KINDS), name="ck_planned_test_kind"),
    )

    op.create_table(
        "analysis_runs", *_base(),
        sa.Column("plan_id", UUID, sa.ForeignKey("analysis_plans.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("dataset_version_id", UUID,
                  sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dataset_freeze_id", sa.String(32), nullable=False),
        sa.Column("tool", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64)),
        sa.Column("runtime", sa.String(64)),
        sa.Column("packages", JSONB),
        sa.Column("random_seed", sa.Integer),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("is_reproducible", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("missing_manifest_fields", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("executed_test_keys", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("exploratory_test_keys", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("requires_disclosure", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("network_egress", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("started_at", TS, nullable=False),
        sa.Column("finished_at", TS),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("error", sa.Text),
        sa.CheckConstraint(_in("tool", TOOLS), name="ck_analysis_run_tool"),
        sa.CheckConstraint("status IN ('running','completed','failed')",
                           name="ck_analysis_run_status"),
        # §31.6 — لا إنترنت صادر أثناء تشغيل التحليل، بلا استثناء.
        sa.CheckConstraint("NOT network_egress", name="ck_analysis_run_no_network"),
        # §18.1 — «قابل لإعادة الإنتاج» يعني بيانًا كاملًا وبصمة.
        sa.CheckConstraint(
            "(NOT is_reproducible) OR "
            "(code_hash IS NOT NULL AND runtime IS NOT NULL AND packages IS NOT NULL "
            " AND random_seed IS NOT NULL AND fingerprint IS NOT NULL "
            " AND missing_manifest_fields = '[]'::jsonb)",
            name="ck_analysis_run_reproducible_requires_manifest",
        ),
        # §51.8 — وجود اختبار استكشافي يستوجب الإفصاح.
        sa.CheckConstraint(
            "exploratory_test_keys = '[]'::jsonb OR requires_disclosure",
            name="ck_analysis_run_exploratory_requires_disclosure",
        ),
    )
    op.create_index("ix_analysis_runs_plan", "analysis_runs", ["tenant_id", "plan_id", "status"])

    # §17.3 — التشغيلة لا تعمل إلا على نسخة مجمَّدة فعلًا.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_frozen_dataset_for_run() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            actual_freeze text;
        BEGIN
            SELECT freeze_id INTO actual_freeze
            FROM dataset_versions WHERE id = NEW.dataset_version_id;
            IF actual_freeze IS NULL THEN
                RAISE EXCEPTION
                    'analysis requires a frozen dataset version (PRD 17.3)'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF actual_freeze <> NEW.dataset_freeze_id THEN
                RAISE EXCEPTION
                    'freeze id mismatch: run cites %, version has % (PRD 17.3)',
                    NEW.dataset_freeze_id, actual_freeze
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_analysis_run_requires_freeze
            BEFORE INSERT OR UPDATE ON analysis_runs
            FOR EACH ROW EXECUTE FUNCTION enforce_frozen_dataset_for_run();
        """
    )

    op.create_table(
        "analysis_outputs", *_base(),
        # §39 — «النتائج غير المرتبطة بتحليل: صفر». غير قابل للإفراغ.
        sa.Column("run_id", UUID, sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("output_kind", sa.String(16), nullable=False),
        sa.Column("test_key", sa.String(64)),
        sa.Column("label_ar", sa.String(255), nullable=False),
        sa.Column("label_en", sa.String(255)),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.CheckConstraint(_in("output_kind", OUTPUT_KINDS), name="ck_analysis_output_kind"),
    )

    op.create_table(
        "interpretations", *_base(),
        sa.Column("output_id", UUID, sa.ForeignKey("analysis_outputs.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("result_ar", sa.Text, nullable=False),
        sa.Column("result_en", sa.Text),
        sa.Column("statistical_ar", sa.Text),
        sa.Column("statistical_en", sa.Text),
        sa.Column("theoretical_ar", sa.Text),
        sa.Column("theoretical_en", sa.Text),
        sa.Column("managerial_ar", sa.Text),
        sa.Column("managerial_en", sa.Text),
        sa.Column("approved_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("approved_at", TS),
        sa.UniqueConstraint("output_id", name="uq_interpretation_output"),
        # §18.3 — سلسلة السند: لا نظري بلا إحصائي، ولا إداري بلا نظري.
        sa.CheckConstraint(
            "theoretical_ar IS NULL OR statistical_ar IS NOT NULL",
            name="ck_interpretation_theoretical_needs_statistical",
        ),
        sa.CheckConstraint(
            "managerial_ar IS NULL OR theoretical_ar IS NOT NULL",
            name="ck_interpretation_managerial_needs_theoretical",
        ),
        # §9 G8 — اعتماد التفسير له فاعل وتاريخ.
        sa.CheckConstraint(
            "(approved_by IS NULL AND approved_at IS NULL) OR "
            "(approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_interpretation_approval_complete",
        ),
    )

    op.create_table(
        "tool_exports", *_base(),
        sa.Column("run_id", UUID, sa.ForeignKey("analysis_runs.id", ondelete="CASCADE")),
        sa.Column("dataset_version_id", UUID,
                  sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tool", sa.String(16), nullable=False),
        sa.Column("export_format", sa.String(16), nullable=False),
        sa.Column("file_id", UUID, sa.ForeignKey("files.id", ondelete="SET NULL")),
        sa.Column("limitations_ar", sa.Text, nullable=False),
        sa.Column("limitations_en", sa.Text, nullable=False),
        sa.CheckConstraint(_in("tool", TOOLS), name="ck_tool_export_tool"),
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
    # RAW لا يُعدَّل ولا يُحذف حتى بصلاحية التطبيق.
    op.execute("REVOKE DELETE ON dataset_versions FROM athera_app")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_analysis_run_requires_freeze ON analysis_runs")
    op.execute("DROP FUNCTION IF EXISTS enforce_frozen_dataset_for_run()")
    op.execute("DROP TRIGGER IF EXISTS trg_frozen_dataset_version_immutable ON dataset_versions")
    op.execute("DROP TRIGGER IF EXISTS trg_raw_dataset_version_immutable ON dataset_versions")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    for table in ("tool_exports", "interpretations", "analysis_outputs", "analysis_runs",
                  "planned_tests", "analysis_plans", "data_dictionaries",
                  "dataset_versions", "datasets"):
        op.drop_table(table)
