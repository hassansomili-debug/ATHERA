"""المشروع وعاءٌ حقيقي | The project as a real research container (PUBRIVA).

**ما ثبت بالفحص قبل كتابة سطر.** تسعة عشر جدولًا تعرف مشروعها اليوم —
الخطط والادعاءات والمجموعات والمخطوطات والفرص وعناصر الخيط وغيرها. وتسعة
لا تعرفه، ومنها **الملفات والمصادر**: أي أن الباحث يرفع ملفًا فلا يعرف
النظام لأي بحثٍ رفعه، ويستورد مصدرًا فلا ينتمي إلى شيء.

فلا يمكن بناء مساحة عمل حول المشروع وهما خارجه.

**ورابطٌ لا عمود.** الملف والمصدر أصلان في مكتبة الباحث العامة، وقد يخدم
الواحد منهما أكثر من بحث: ورقةٌ يستشهد بها مشروعان، وبياناتٌ تُقرأ في
سياقين. فعمودٌ واحد يفرض نسخًا — ونسخةٌ ثانية للأصل نفسه تفترق عنه بأول
تعديل، ولا يعرف أحدٌ أيّهما الصحيح.

**والاستعمال حالٌ في الرابط لا في الأصل.** مصدرٌ «مُدرَج» في مشروع قد يكون
«محفوظًا فقط» في آخر و«مستبعَدًا» في ثالث — وهو مصدرٌ واحد. فحالُ الاستعمال
تخصّ العلاقة لا الشيء.

**والحذف يُؤجَّل لا يقع.** بحثٌ يُحذف بضغطة لا يُستعاد، وسنواتُ عملٍ لا
تُعاد كتابتها. فالحذف الظاهر نقلٌ إلى سلّة، والحذف الحقيقي قرارٌ ثانٍ.

Revision ID: 0020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# حال الأصل داخل مشروعٍ بعينه — لا حال الأصل نفسه.
LINK_STATES = ("active", "archived")

# **حال استعمال المصدر في هذا البحث.**
#
#   included    — دليلٌ يجوز أن يُبنى عليه
#   saved_only  — محفوظٌ للقراءة، ولا يُبنى عليه بعد
#   excluded    — نُظر فيه واستُبعد، ويبقى القرار مرئيًّا
#
# والافتراض `saved_only`: استيرادُ مصدرٍ ليس حكمًا بصلاحيته دليلًا. وجعلُ
# كل ما يُخزَّن دليلًا افتراضًا يبني ورقةً على ما لم يقرأه أحد.
SOURCE_USE_STATES = ("included", "saved_only", "excluded")

NEW_TABLES = ("project_files", "project_sources")


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _base() -> list:
    return [
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # ── 1. الملف ينتمي إلى بحثٍ (أو أكثر) ──
    op.create_table(
        "project_files", *_base(),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        # **`RESTRICT` على الملف.** إزالته من مشروع شيء، وحذفه من المكتبة
        # شيء آخر — ولا يقع الثاني بأثرٍ جانبي للأول.
        sa.Column("file_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("added_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note_ar", sa.Text),
        sa.CheckConstraint(_in("state", LINK_STATES), name="ck_project_file_state"),
        sa.UniqueConstraint("project_id", "file_id", name="uq_project_file"),
    )
    op.create_index("ix_project_files_project", "project_files",
                    ["tenant_id", "project_id", "state"])

    # ── 2. المصدر ينتمي إلى بحثٍ **بحال استعماله فيه** ──
    op.create_table(
        "project_sources", *_base(),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("use_state", sa.String(16), nullable=False,
                  server_default="saved_only"),
        sa.Column("added_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("decided_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", TS),
        sa.Column("reason_ar", sa.Text),
        sa.CheckConstraint(_in("use_state", SOURCE_USE_STATES),
                           name="ck_project_source_use_state"),
        # قرارٌ بلا فاعل ووقت لا يكون — كما في كل قرار بشري في المنظومة.
        sa.CheckConstraint(
            "use_state = 'saved_only' OR "
            "(decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_project_source_decision_actor",
        ),
        sa.UniqueConstraint("project_id", "source_id", name="uq_project_source"),
    )
    op.create_index("ix_project_sources_project", "project_sources",
                    ["tenant_id", "project_id", "use_state"])

    # ── 3. سلّة المهملات: الحذف الظاهر تأجيلٌ لا إتلاف ──
    op.add_column("research_projects", sa.Column("archived_at", TS, nullable=True))
    op.add_column("research_projects", sa.Column("deleted_at", TS, nullable=True))
    op.add_column("research_projects", sa.Column(
        "deleted_by", PgUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    op.create_check_constraint(
        "trash_actor", "research_projects",
        "deleted_at IS NULL OR deleted_by IS NOT NULL")
    op.create_index("ix_research_projects_live", "research_projects",
                    ["tenant_id", "deleted_at"])

    # ── 4. العزل: مفعَّل ومفروض على كل جدول جديد ──
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = app_current_tenant()) "
            "WITH CHECK (tenant_id = app_current_tenant())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO athera_app")


def downgrade() -> None:
    """التنازل يرفض ولا يمحو قرار استبعادٍ ولا بحثًا في السلّة.

    استبعادُ مصدرٍ من بحث حكمٌ قاله الباحث بعد نظر، وحذف الجدول يمحوه بلا
    أثر. وبحثٌ في السلّة ينتظر قراره: حذفُ العمود يجعله يعود حيًّا فجأة أو
    يضيع — وكلاهما أسوأ من تنازلٍ يُرفض.
    """
    bind = op.get_bind()

    decided = bind.execute(sa.text(
        "SELECT count(*) FROM project_sources WHERE use_state <> 'saved_only'"
    )).scalar_one()
    if decided:
        raise RuntimeError(
            f"downgrade refused: {decided} source link(s) carry a human decision "
            "(included or excluded). Dropping the table would destroy it. | "
            f"التنازل مرفوض: {decided} مصدرًا يحمل قرار إدراج أو استبعاد."
        )

    trashed = bind.execute(sa.text(
        "SELECT count(*) FROM research_projects WHERE deleted_at IS NOT NULL"
    )).scalar_one()
    if trashed:
        raise RuntimeError(
            f"downgrade refused: {trashed} project(s) sit in the trash awaiting a "
            "decision. Restore or delete them deliberately first. | "
            f"التنازل مرفوض: {trashed} بحثًا في السلّة ينتظر قرارًا."
        )

    for table in NEW_TABLES:
        op.drop_table(table)
    op.drop_index("ix_research_projects_live", table_name="research_projects")
    op.execute("ALTER TABLE research_projects DROP CONSTRAINT "
               "ck_research_projects_trash_actor")
    for column in ("deleted_by", "deleted_at", "archived_at"):
        op.drop_column("research_projects", column)
