"""إدارة المشروع البحثي | Research project management (PUBRIVA).

**الفرق بين لوح مهامّ ومشروعٍ علميّ مكتوبٌ في هذا المخطَّط، لا في الشاشة.**

ولا عمود في هذه الجداول يحمل نسبة: لا `progress_percent` ولا
`readiness_score` ولا `completion_ratio`. والسبب ليس ذوقًا: «٨٢٪ جاهزية
بحثية» تُقرأ حكمًا فحصت فيه المنصّة ورقةً علميًّا، ولم يقع من ذلك شيء —
عُدَّت بطاقاتٌ مغلقة وقُسمت على بطاقات. ورقمٌ لا يستطيع الباحث مراجعته
يُصدَّق، والعدد يُفتَح ويُرى.

## أربع حقائق لا يطويها عمودٌ واحد

  المرحلة الحالية   `project_plans.current_stage`
  اعتمادُ الباحث    `stage_confirmed_by` / `stage_confirmed_at` — وفراغُهما
                    يعني «لم يقل أحدٌ شيئًا بعد»، لا «هو في الفكرة يقينًا»
  تاريخ المراحل     `project_stage_events` — و`confirmed_by` فيه **غيرُ
                    قابلٍ للفراغ**: لا صفَّ في هذا السجلّ تكتبه المنصّة عن
                    نفسها، فلا تستطيع أن تدّعي مرحلةً ولو أراد كاتبٌ ذلك
  المقترَح التالي   **لا عمود له أصلًا** — يُشتقّ وقت القراءة من مَعالمَ
                    اعتمدها بشر، فيستحيل بنيويًّا أن يُقرأ حالًا مخزَّنة

وطيُّ الرابعة في الأولى هو العطب الذي يجعل المنصّة تدّعي علمًا: تكتب
«التحليل» في `current_stage` لأن ملف بياناتٍ رُفع، فيقرأ الباحث بعد شهر
أنه في التحليل ولم يقل ذلك أحد.

## ودورة الحياة ليست خطًّا — ولا قيد هنا يفرضها خطًّا

باحثٌ يعود إلى المنهجية بعد التحليل يفعل الصواب: التحليل كشف عيبًا في
التصميم. فلا قيد ترتيبٍ في `project_stage_events`، و`from_stage` قد يقع
بعد `to_stage` في القائمة، والسجلّ يقبله ويحفظه كما هو.

## واقتراحٌ لا يصير تكليفًا بلا إنسان — والقاعدة تفرضه

`ck_project_tasks_a_suggestion_becomes_a_task_only_when_accepted` يرفض أيّ
صفٍّ `suggested_by_system` بلا `accepted_by` و`accepted_at`. فلو كُتب يومًا
مسارٌ ثانٍ يُدخل مهامًّا مقترَحة في قوائم الباحثين رفضته القاعدة قبل أن
يصل الإنتاج. والفرق جوهريّ: مهمّةٌ في القائمة تُقرأ التزامًا، ومنصّةٌ
تُدخل التزاماتٍ لم يقبلها أحد تخلط ما اقترحته بما قرّره الباحث.

## والإتمام فعلُ إنسانٍ لا أثرُ زيارةِ صفحة

`ck_project_milestones_completion_has_an_author_and_a_time` يمنع
`completed_at` بلا `completed_by`. ولو اكتُشف الإتمام من مرور الباحث على
شاشةٍ لصار «اكتملت مراجعة الأدبيات» مكتوبًا في سجلٍّ لأن أحدًا فتح صفحة
المراجع — ثمّ بُني عليه اقتراحُ الانتقال إلى المرحلة التالية.

## والعزل بين بحثين في المستأجر الواحد بنيويّ

RLS تحمي بين المستأجرين ولا تحمي بين بحثين في مستأجرٍ واحد — وهذا عطبٌ
وقع في هذا المنتج من قبل. فإسنادُ المهمّة يرتبط بعضو الفريق **بمفتاحٍ
مركّب** `(assignee_member_id, project_id)`: مهمّةٌ في بحثٍ لا يمكن أن
تُسنَد إلى عضوٍ في بحثٍ آخر، لا لأن الخدمة تصفّي، بل لأن القاعدة ترفض.

وبلا `ondelete` على ذلك المفتاح عمدًا: إزالةُ عضوٍ ما زالت له مهامّ
تُرفض — فتُعاد إسنادها أولًا — بينما حذفُ البحث كلّه يمرّ، لأن الفحص يقع
في آخر العبارة وقد ذهب الطرفان معًا.

Revision ID: 0026
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = (
    "project_plans",
    "project_stage_events",
    "project_tasks",
    "project_milestones",
)

# ══════════════════════════ المفردات ══════════════════════════
#
# **مكتوبةٌ هنا ومقابَلةٌ بقائمة النموذج اختبارًا**، عنصرًا بعنصر. والخطأ
# المتكرر في هذا المستودع مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

STAGES = (
    "idea",
    "literature_discovery",
    "gap_problem",
    "design_methodology",
    "data_preparation_collection",
    "analysis",
    "scientific_writing",
    "scientific_review",
    "journal_selection",
    "submission",
    "peer_review_revision",
    "published",
)

# **ستٌّ لا عشرون.** وكل حالٍ إضافية معنًى ثانٍ لشيءٍ له اسم، ثمّ تقريران
# لا يتفقان — ومن يعدّ «المتأخرة» يختار بعضها وينسى بعضها.
TASK_STATUSES = ("not_started", "in_progress", "awaiting_review",
                 "needs_decision", "blocked", "completed")

TASK_SOURCES = ("researcher_created", "team_created",
                "research_brain_suggestion", "system_workflow")

# المصدران اللذان لا يصيران تكليفًا بلا قبولٍ من إنسان.
SYSTEM_TASK_SOURCES = ("research_brain_suggestion", "system_workflow")

TASK_PRIORITIES = ("low", "normal", "high")

MILESTONES = (
    "idea_approved",
    "literature_review_completed",
    "gap_approved",
    "methodology_approved",
    "data_ready",
    "analysis_completed",
    "manuscript_ready",
    "journal_selected",
    "submitted",
    "review_response_completed",
    "published",
)


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _scoped_columns() -> tuple:
    """الأعمدة التي يحملها كل جدولٍ تابعٍ لبحث — **و`project_id` منها**.

    وهو ليس تكرارًا لـ`tenant_id`: العزل بين المستأجرين تتكفّل به RLS،
    والعزل بين بحثين في المستأجر الواحد لا يتكفّل به شيء إلا هذا العمود
    وما يُبنى عليه من مفاتيح مركّبة.
    """
    return (
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    # ── ٠. عضوُ الفريق يُعرَف ببحثه ──
    #
    # قيدٌ فريدٌ على `(id, project_id)` لا يمنع شيئًا بذاته — `id` مفتاحٌ
    # أوّليّ أصلًا. غرضه أن يصير **مرجعًا لمفتاحٍ أجنبيٍّ مركّب**، فيستحيل
    # بنيويًّا أن تُسنَد مهمّةٌ في بحثٍ إلى عضوٍ في بحثٍ آخر من المستأجر
    # نفسه. وهو الحارس الذي لا تملكه RLS.
    op.create_unique_constraint(
        "uq_project_members_project_scoped", "project_members",
        ["id", "project_id"])

    # ══════════════════ ١. خطّة البحث ومرحلته ══════════════════
    op.create_table(
        "project_plans",
        *_scoped_columns(),
        # تاريخُ البدء هنا، وتاريخُ الهدف في `research_projects.target_date`
        # القائم — **ولا يُنسخ**: عمودان لتاريخٍ واحد يفترقان بأول تعديل،
        # ثمّ تعرض شاشتان موعدين مختلفين ولا يُعرف أيّهما الخطّة.
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("current_stage", sa.String(48), nullable=False,
                  server_default="idea"),
        sa.Column("stage_confirmed_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("stage_confirmed_at", TS, nullable=True),
        sa.Column("stage_note_ar", sa.Text, nullable=True),
        sa.CheckConstraint(_in("current_stage", STAGES), name="current_stage"),
        # **الاعتماد له صاحبٌ ووقت، أو ليس اعتمادًا.**
        sa.CheckConstraint(
            "(stage_confirmed_by IS NULL) = (stage_confirmed_at IS NULL)",
            name="confirmation_has_an_author_and_a_time"),
        # صفٌّ واحد لكل بحث — وصفّان يعنيان مرحلتين لبحثٍ واحد.
        sa.UniqueConstraint("project_id", name="uq_project_plans_project"),
    )

    # ══════════════════ ٢. تاريخ المراحل ══════════════════
    #
    # **`confirmed_by NOT NULL` هو العمود الذي يمنع المنصّة من ادّعاء
    # مرحلة.** ولو قُبل الفراغ لصار بالإمكان أن يُكتب في هذا السجلّ سطرٌ
    # بلا صاحب، فيُقرأ بعد شهرٍ كأنّ المشروع بلغ مرحلةً بشهادة النظام.
    op.create_table(
        "project_stage_events",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        # لا `from_stage` عند أول اعتماد: لم يكن قبله شيءٌ ليُنسب إليه.
        sa.Column("from_stage", sa.String(48), nullable=True),
        sa.Column("to_stage", sa.String(48), nullable=False),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("confirmed_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note_ar", sa.Text, nullable=True),
        # **ما كانت المنصّة تقترحه لحظة الاعتماد.** يُحفظ ليُقرأ بعد شهر:
        # هل تبع الباحث الاقتراح أم خالفه؟ فتصير جودة الاقتراح قابلةً
        # للمراجعة بدل أن تُصدَّق. وفراغه يعني «لم يكن هناك اقتراح».
        sa.Column("system_suggested_stage", sa.String(48), nullable=True),
        sa.CheckConstraint(_in("to_stage", STAGES), name="to_stage"),
        sa.CheckConstraint(
            "from_stage IS NULL OR " + _in("from_stage", STAGES), name="from_stage"),
        sa.CheckConstraint(
            "system_suggested_stage IS NULL OR "
            + _in("system_suggested_stage", STAGES), name="system_suggested_stage"),
        # **ولا قيدَ ترتيبٍ هنا عمدًا.** العودة إلى مرحلةٍ سابقة حالٌ صحيحة.
    )
    op.create_index("ix_project_stage_events_project", "project_stage_events",
                    ["tenant_id", "project_id", "occurred_at"])

    # ══════════════════ ٣. المهامّ ══════════════════
    op.create_table(
        "project_tasks",
        *_scoped_columns(),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("stage", sa.String(48), nullable=False),
        sa.Column("status", sa.String(24), nullable=False,
                  server_default="not_started"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("assignee_member_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("created_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False,
                  server_default="researcher_created"),
        sa.Column("suggested_by_system", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        # **قبولُ الاقتراح يُنسب إلى صاحبه ووقته** — وبدونهما لا صفّ.
        sa.Column("accepted_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("accepted_at", TS, nullable=True),
        sa.Column("due_at", TS, nullable=True),
        sa.Column("started_at", TS, nullable=True),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("requires_decision", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("decision_gate", sa.String(16), nullable=True),
        sa.Column("related_entity_type", sa.String(48), nullable=True),
        sa.Column("related_entity_id", PgUUID(as_uuid=True), nullable=True),

        sa.CheckConstraint(_in("status", TASK_STATUSES), name="status"),
        sa.CheckConstraint(_in("source", TASK_SOURCES), name="source"),
        sa.CheckConstraint(_in("priority", TASK_PRIORITIES), name="priority"),
        sa.CheckConstraint(_in("stage", STAGES), name="stage"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="title_is_not_blank"),
        # **الإتمام له وقت.** و«مكتملة» بلا وقتٍ تُسقط كلَّ حسابٍ للتأخّر،
        # وتجعل «متى أُنجزت؟» سؤالًا بلا جواب في مراجعةٍ بعد سنة.
        sa.CheckConstraint("(status = 'completed') = (completed_at IS NOT NULL)",
                           name="completion_has_a_time"),
        # **الرايةُ تُشتقّ من المصدر لا تُكتب بجانبه.** ولو افترقا لَعُدّت
        # مهمّةٌ اقترحتها آلةٌ من صنع الباحث، أو العكس.
        sa.CheckConstraint(
            "suggested_by_system = (" + _in("source", SYSTEM_TASK_SOURCES) + ")",
            name="suggestion_flag_follows_its_source"),
        # **الحارس الذي يمنع الاقتراح من أن يصير تكليفًا.**
        sa.CheckConstraint(
            "NOT suggested_by_system"
            " OR (accepted_by IS NOT NULL AND accepted_at IS NOT NULL)",
            name="a_suggestion_becomes_a_task_only_when_accepted"),
        sa.CheckConstraint("(accepted_by IS NULL) = (accepted_at IS NULL)",
                           name="acceptance_has_an_author_and_a_time"),
        # بوابةُ قرارٍ بلا «تحتاج قرارًا» تسقط من قائمة «تنتظر اعتمادك».
        sa.CheckConstraint("decision_gate IS NULL OR requires_decision",
                           name="a_gate_means_a_decision_is_required"),
        sa.CheckConstraint("status <> 'needs_decision' OR requires_decision",
                           name="needing_a_decision_means_requiring_one"),
        sa.CheckConstraint(
            "(related_entity_type IS NULL) = (related_entity_id IS NULL)",
            name="a_relation_names_its_kind"),
        # **العزل بين بحثين — بنيويًّا.** بلا `ondelete`: إزالةُ عضوٍ له
        # مهامّ تُرفض حتى تُعاد إسنادها، وحذفُ البحث كلّه يمرّ لأن الفحص
        # يقع في آخر العبارة وقد ذهب الطرفان معًا.
        sa.ForeignKeyConstraint(
            ["assignee_member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            name="fk_project_tasks_assignee"),
    )
    op.create_index("ix_project_tasks_project", "project_tasks",
                    ["tenant_id", "project_id", "status"])
    # فهرسُ «ما تأخّر»: القراءة التي تفتحها اللوحة في كل مرّة.
    op.create_index("ix_project_tasks_due", "project_tasks",
                    ["tenant_id", "project_id", "due_at"])

    # ══════════════════ ٤. المَعالم ══════════════════
    op.create_table(
        "project_milestones",
        *_scoped_columns(),
        sa.Column("milestone_key", sa.String(48), nullable=False),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("completed_at", TS, nullable=True),
        sa.Column("completed_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("evidence_note_ar", sa.Text, nullable=True),
        sa.CheckConstraint(_in("milestone_key", MILESTONES), name="milestone_key"),
        # **الإتمام فعلُ إنسانٍ لا أثرُ زيارةِ صفحة.**
        sa.CheckConstraint("(completed_at IS NULL) = (completed_by IS NULL)",
                           name="completion_has_an_author_and_a_time"),
        sa.UniqueConstraint("project_id", "milestone_key",
                            name="uq_project_milestone"),
    )
    op.create_index("ix_project_milestones_project", "project_milestones",
                    ["tenant_id", "project_id", "completed_at"])

    # ── ٥. العزل: مفعَّل **ومفروض**، ومنحُ الدور صريح (ADR-0002) ──
    #
    # `FORCE` ليست تكرارًا لـ`ENABLE`: بدونها يتجاوز مالكُ الجدول سياساته،
    # فتصير الحماية معتمدةً على أيّ دورٍ فتح الاتصال.
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
    """التنازل يرفض ولا يمحو ما قاله باحثٌ بيده.

    واعتمادُ مرحلةٍ أو مَعْلَمٍ قرارٌ بشريّ منسوبٌ إلى صاحبه ووقته؛ وإسقاط
    الجداول عليه إتلافُ ذلك القرار لإرضاء تنازل. فيُطلب الحسم أولًا — كما
    في 0016 و0020 و0022 و0023 و0025.

    والمهامّ تُسقَط بلا سؤال: مهمّةٌ عملٌ يُنظَّم، لا حكمٌ علميّ. والفرق
    هو نفسه الذي يقوم عليه هذا الترحيل كلّه.
    """
    bind = op.get_bind()

    decisions = bind.execute(sa.text(
        "SELECT (SELECT count(*) FROM project_stage_events)"
        " + (SELECT count(*) FROM project_milestones WHERE completed_by IS NOT NULL)"
    )).scalar_one()
    if decisions:
        raise RuntimeError(
            f"downgrade refused: {decisions} stage confirmation(s) and completed "
            "milestone(s) carry a human decision attributed to the researcher who "
            "made it. Dropping these tables would destroy that record. | "
            f"التنازل مرفوض: {decisions} اعتمادًا بشريًّا في المراحل والمَعالم."
        )

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index("ix_project_milestones_project", table_name="project_milestones")
    op.drop_table("project_milestones")
    op.drop_index("ix_project_tasks_due", table_name="project_tasks")
    op.drop_index("ix_project_tasks_project", table_name="project_tasks")
    # **قبل قيد أعضاء الفريق**: المفتاح المركّب يشير إليه، وإسقاطُ المشار
    # إليه قبل المشير يفشل.
    op.drop_table("project_tasks")
    op.drop_index("ix_project_stage_events_project", table_name="project_stage_events")
    op.drop_table("project_stage_events")
    op.drop_table("project_plans")

    op.drop_constraint("uq_project_members_project_scoped", "project_members",
                       type_="unique")
