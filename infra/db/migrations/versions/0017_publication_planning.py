"""تخطيط النشر من المعرفة الموثقة | Evidence-grounded publication planning (S5D).

**توسيعٌ لا معماريةٌ موازية.** `publication_opportunities` قائم منذ 0010
بجهوزيته وتداخله وبوابات حقوقه، و`thread_elements` قائم بخيطه الذهبي
ومدقّقه التسعي. وما ينقص جسرٌ بينهما وبين `researcher_memories`.

**والحدّ العام مشروعٌ لا معرّفٌ عائم.** `research_projects` كيانٌ حقيقي
مقيَّد بالمستأجر، وهو **أصلًا** أبو عناصر الخيط وروابطه. فربط الفرص به
يجعل السلسلة كلها تحت أبٍ واحد، بلا كيان جديد يُخترع:

    research_project
      ├── publication_opportunities.project_id   (جديد)
      ├── thread_elements.project_id             (قائم)
      └── planning_runs.project_id               (جديد)

و`thesis_id` يبقى ويصير قابلًا للعدم: الرسالة **مصدرٌ** لا حدُّ مجال. والصفوف
القائمة لا تُمسّ، ويحرسها قيدٌ يشترط أحد المصدرين على الأقل.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# حالة التخطيط — **منفصلة عن دورة حياة النشر**.
#
# `status` القائم يعني: اكتُشفت، حُلّلت، تنتظر الحقوق، جاهزة للتقديم، حُوّلت،
# رُفضت. وهي دورة **إنتاج ورقة**. وحالة التخطيط تعني شيئًا آخر تمامًا: هل
# اختار الباحث هذه الفرصة من بين ما اقترحته أثيرا؟ ودمجهما في عمود واحد
# يجعل «مرفوضة» تحتمل معنيين لا يجمعهما جامع.
PLANNING_STATUSES = ("proposed", "selected", "excluded", "superseded")

# حالات التحقق الخارجي — والسجل مغلق اليوم، فالافتراض «معلّق» لا «مؤكَّد».
LITERATURE_STATUSES = ("pending", "validated", "not_applicable")
JOURNAL_STATUSES = ("not_assessed", "pending", "assessed")

EVIDENCE_ROLES = (
    "problem", "question", "objective", "theory", "methodology",
    "sample", "variable", "analysis", "result", "limitation",
)


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # ── 1. الفرصة تعرف مشروعها، وحالة تخطيطها، وما لم يُتحقّق منه بعد ──
    op.add_column("publication_opportunities",
                  sa.Column("project_id", PgUUID(as_uuid=True),
                            sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                            nullable=True))
    op.alter_column("publication_opportunities", "thesis_id", nullable=True)

    op.add_column("publication_opportunities",
                  sa.Column("planning_status", sa.String(16), nullable=False,
                            server_default="proposed"))
    op.add_column("publication_opportunities",
                  sa.Column("planning_decided_by", PgUUID(as_uuid=True),
                            sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("publication_opportunities",
                  sa.Column("planning_decided_at", TS, nullable=True))

    # §14 — السجل مغلق، فلا ادّعاء جدّة ولا ملاءمة مجلة.
    op.add_column("publication_opportunities",
                  sa.Column("literature_validation_status", sa.String(24),
                            nullable=False, server_default="pending"))
    op.add_column("publication_opportunities",
                  sa.Column("journal_validation_status", sa.String(24),
                            nullable=False, server_default="not_assessed"))

    # §15 — درجة **جهوزية الأدلة**، مستقلة عن `readiness_score` القائم.
    # وسؤالها: «كم هذه الفرصة جاهزة للتطوير من الأدلة التي بين أيدينا؟»
    # لا: «كم احتمال أن تقبلها مجلة؟» — وهذا السؤال الثاني لا يُجاب هنا أبدًا.
    op.add_column("publication_opportunities",
                  sa.Column("evidence_readiness_score", sa.Numeric(5, 2), nullable=True))

    op.add_column("publication_opportunities",
                  sa.Column("generation_run_id", PgUUID(as_uuid=True), nullable=True))

    op.create_check_constraint(
        "planning_status", "publication_opportunities",
        _in("planning_status", PLANNING_STATUSES))
    op.create_check_constraint(
        "lit_status", "publication_opportunities",
        _in("literature_validation_status", LITERATURE_STATUSES))
    op.create_check_constraint(
        "journal_status", "publication_opportunities",
        _in("journal_validation_status", JOURNAL_STATUSES))
    # لا فرصة بلا مصدر: رسالةٌ أو مشروع، والقديم يبقى صالحًا بالأولى.
    op.create_check_constraint(
        "has_source", "publication_opportunities",
        "thesis_id IS NOT NULL OR project_id IS NOT NULL")
    # قرارٌ بشري بلا فاعل ووقت لا يكون.
    op.create_check_constraint(
        "planning_actor", "publication_opportunities",
        "planning_status IN ('proposed','superseded') OR "
        "(planning_decided_by IS NOT NULL AND planning_decided_at IS NOT NULL)")

    # ── 1ب. الموافقة تعرف سياقها، لا مستندها وحده ──
    #
    # §7 — موافقةٌ على «هذا المشروع إلى الأبد» تسمح بإرسال أدلةٍ أُضيفت بعدها
    # تحت إذنٍ لم يرها صاحبه. فالعمود يحمل بصمة اللقطة التي أُذن لها، ويُقارَن
    # بها عند كل إرسال. وقابلٌ للعدم: موافقات S5C لا تستعمله ولا تتأثر.
    op.add_column("approvals",
                  sa.Column("context_fingerprint", sa.String(64), nullable=True))

    # ── 2. تشغيلة التخطيط: الكيان الذي يثبّت لقطة الأدلة ──
    #
    # §4 و§5 — «ما الأدلة الموثقة التي وُلّدت منها هذه الفرص بالضبط؟» سؤالٌ
    # يحتاج صفًّا يُجيب عنه. والبصمة تُشتقّ من معرّفات الذاكرة ومحتواها،
    # فتُقارَن بموافقةٍ أُعطيت على سياق بعينه.
    op.create_table(
        "planning_runs",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        # بصمة لقطة الأدلة — لا محتواها.
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("memory_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence_summary", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("agent_run_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="running"),
        sa.Column("opportunities_proposed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("started_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", TS),
        sa.CheckConstraint(
            "status IN ('running','insufficient_evidence','completed','failed')",
            name="ck_planning_run_status"),
        sa.CheckConstraint("length(context_fingerprint) = 64",
                           name="ck_planning_run_fingerprint"),
    )
    op.create_index("ix_planning_runs_project", "planning_runs", ["project_id"])
    op.create_foreign_key("fk_opportunity_generation_run", "publication_opportunities",
                          "planning_runs", ["generation_run_id"], ["id"],
                          ondelete="SET NULL")

    # ── 3. روابط الأدلة: الفرصة → الذاكرة الموثقة ──
    #
    # §21 — **ولا نسخ للإسناد.** `researcher_memories` تملك `source_file_id`
    # و`source_locator` و`source_quote`، فتكرارها هنا يخلق مصدرَي حقيقة
    # يفترقان بأول تعديل. السلسلة: فرصة → رابط → ذاكرة → إسناد.
    op.create_table(
        "opportunity_evidence_links",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("opportunity_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("memory_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("researcher_memories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("evidence_role", sa.String(24), nullable=False),
        sa.CheckConstraint(_in("evidence_role", EVIDENCE_ROLES),
                           name="ck_opportunity_evidence_role"),
        sa.UniqueConstraint("opportunity_id", "memory_id", "evidence_role",
                            name="uq_opportunity_evidence_link"),
    )
    op.create_index("ix_opportunity_evidence_opportunity", "opportunity_evidence_links",
                    ["opportunity_id"])

    # ── 4. أدلة عناصر الخيط ──
    op.create_table(
        "thread_element_evidence",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("element_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("thread_elements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("researcher_memories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.UniqueConstraint("element_id", "memory_id", name="uq_thread_element_evidence"),
    )

    # ── 5. هيكل الورقة — أقسامٌ بأدلتها، لا نثر ──
    op.create_table(
        "manuscript_outlines",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("opportunity_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False),
        # الأقسام: غرضٌ وأسئلة وأدلة متاحة وناقصة وادعاءات مسموحة — لا نصّ ورقة.
        sa.Column("sections", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("article_type", sa.String(32)),
        sa.Column("generation_run_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("planning_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.CheckConstraint("status IN ('draft','reviewed','superseded')",
                           name="ck_outline_status"),
    )
    op.create_index("ix_manuscript_outlines_opportunity", "manuscript_outlines",
                    ["opportunity_id"])

    for table in ("planning_runs", "opportunity_evidence_links",
                  "thread_element_evidence", "manuscript_outlines"):
        _tenant_rls(table)


def _tenant_rls(table: str) -> None:
    """نفس سياسة العزل المطبَّقة على كل جدول مقيَّد بمستأجر منذ 0002."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (tenant_id = app_current_tenant()) "
        "WITH CHECK (tenant_id = app_current_tenant())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO athera_app")


def downgrade() -> None:
    """التنازل يرفض ولا يمحو قرار تخطيط (§32).

    فرصةٌ اختارها الباحث أو استبعدها حكمٌ قاله بعد مراجعة أدلة. وحذف العمود
    الذي يحمله يمحو الحكم بلا أثر — فيُرفض التنازل ويُقال العدد والسبب وما
    يجب فعله، كما فعل 0016 مع «لا أعرف».

    والتشغيلات والروابط والهياكل تُحذف: هي مخرجات نموذج قابلة لإعادة
    التوليد، لا أحكامًا بشرية.
    """
    bind = op.get_bind()
    decided = bind.execute(sa.text(
        "SELECT count(*) FROM publication_opportunities "
        "WHERE planning_status IN ('selected','excluded')"
    )).scalar_one()
    if decided:
        raise RuntimeError(
            f"downgrade refused: {decided} publication opportunity/opportunities carry a "
            "human planning decision (selected or excluded). Dropping planning_status "
            "would destroy it. Resolve them first — or export the decisions — then retry. | "
            f"التنازل مرفوض: {decided} فرصة نشر تحمل قرار تخطيط بشريًّا (مختارة أو "
            "مستبعَدة). حذف العمود يمحو القرار — احسمها أو صدّرها أولًا."
        )

    for table in ("manuscript_outlines", "thread_element_evidence",
                  "opportunity_evidence_links"):
        op.drop_table(table)
    op.drop_constraint("fk_opportunity_generation_run", "publication_opportunities",
                       type_="foreignkey")
    op.drop_table("planning_runs")

    # **الحذف بـSQL صريح.** حذفُ قيد check عبر واجهة alembic يعيد تطبيق
    # اصطلاح التسمية على اسمٍ طُبّق عليه أصلًا. والاسم الطويل يتجاوز
    # حدّ 63 محرفًا في PostgreSQL فيُبتَر ويُلحق به تجزئة عند الإنشاء — فلا
    # يطابقه ما يبنيه الاصطلاح عند الحذف، ويسقط التنازل حين يُحتاج إليه.
    for short in ("planning_actor", "has_source", "journal_status",
                  "lit_status", "planning_status"):
        op.execute("ALTER TABLE publication_opportunities "
                   f"DROP CONSTRAINT ck_publication_opportunities_{short}")

    op.drop_column("approvals", "context_fingerprint")

    for column in ("generation_run_id", "evidence_readiness_score",
                   "journal_validation_status", "literature_validation_status",
                   "planning_decided_at", "planning_decided_by", "planning_status",
                   "project_id"):
        op.drop_column("publication_opportunities", column)

    # `thesis_id` يعود إلزاميًّا — ولا يُخترع له قيمة.
    #
    # وصفٌّ بلا رسالة (فرصة S5D خالصة) يمنع العودة: يُقال ذلك ولا يُحذف الصفّ.
    orphans = bind.execute(sa.text(
        "SELECT count(*) FROM publication_opportunities WHERE thesis_id IS NULL"
    )).scalar_one()
    if orphans:
        raise RuntimeError(
            f"downgrade refused: {orphans} opportunity/opportunities have no thesis_id "
            "and would violate the restored NOT NULL. They are project-derived (S5D). "
            "Remove or re-source them deliberately first. | "
            f"التنازل مرفوض: {orphans} فرصة بلا رسالة مصدر."
        )
    op.alter_column("publication_opportunities", "thesis_id", nullable=False)
