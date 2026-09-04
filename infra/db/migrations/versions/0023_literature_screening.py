"""الفرز ومصفوفة الأدبيات | Literature screening + matrix (PUBRIVA).

**ثلاثة معانٍ لا تُطوى في واحد.** نتيجةُ بحثٍ في فهرسٍ خارجي ليست مرجعًا
مخزَّنًا، والمرجعُ المخزَّن ليس دليلًا مُدرَجًا. والترحيل 0020 حفظ الثالث
منها في `project_sources.use_state`؛ وهذا الترحيل **يمدّ ذلك الصفَّ ولا
ينشئ حقيقةً موازية له**: لا جدول قراراتٍ ثانٍ، ولا عمود «مفروز» يفترق عن
`use_state` بأول تعديل.

**والاستبعاد حكمٌ يلزمه سبب.** «استُبعد» بلا سببٍ مسجَّل لا يُراجَع بعد
شهر ولا يُكتب في قسم المنهجية: يقرأ الباحث اسم الدراسة ولا يذكر لماذا
تركها، فيعيد قراءتها أو — وهو الأسوأ — يذكر لها سببًا من ذاكرته الآن.
فالسببُ رمزٌ من قائمةٍ مغلقة، والقيد في القاعدة يرفض الاستبعاد بدونه.

**ولا يُستنتج استبعادٌ آليًّا أبدًا.** لا في هذا الترحيل ولا فيما بُني
عليه: القرار فعلُ إنسانٍ يُنسب إليه بالاسم والوقت — وهو قيد 0020 نفسه،
باقٍ كما هو.

**والخلية تحمل حالها ومَداها.** خليةٌ في مصفوفة الأدبيات ليست نصًّا: هي
نصٌّ **ومن أين قُرئ**. فمقياسٌ لم يُذكر في الملخّص حاله `missing` ولا
يُخترع له اسم؛ ومَدى القراءة `metadata_only` أو `abstract_only` أو
`full_text` يُكتب مع كل خلية، فتقول الشاشة «تم التحليل من الملخص فقط» بدل
أن توهم الباحث أنه قرأ ورقةً كاملة.

وأربعة قيودٍ في القاعدة تحرس ذلك، لأن انضباط المطوّر وحده لا يحرسه:
  ١) `missing` لا تحمل قيمة ولا شاهدًا — الغياب غيابٌ لا فراغٌ يُملأ.
  ٢) `metadata_only` لا تحمل اقتباسًا — بيانات وصفية ليست نصًّا (§14.5).
  ٣) `abstract_only` لا تحمل مُحدِّدَ صفحة — **ولا تُخترع أرقام صفحات**.
  ٤) ما استخرجه نموذج لا يُكتب معتمَدًا بلا مُعتمِدٍ بشريّ يُسمّى.

Revision ID: 0023
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = ("literature_matrix_cells",)

# **أسباب الاستبعاد: قائمةٌ مغلقة، ونصٌّ حرٌّ لواحدٍ منها.** القائمة المغلقة
# تُعدّ وتُقارن ويُكتب منها قسم المنهجية؛ والنصّ الحرّ وحده لا يُعدّ ولا
# يُقارن — فيبقى مكانه `سبب آخر` مصحوبًا بملاحظةٍ إجبارية.
EXCLUSION_REASON_CODES = (
    "topic_not_relevant",      # موضوع غير ذي صلة
    "population_mismatch",     # مجتمع غير مناسب
    "method_mismatch",         # منهج غير مناسب
    "not_original_study",      # ليست دراسة أصلية
    "outside_time_window",     # خارج الفترة الزمنية
    "insufficient_data",       # لا تتوفر بيانات كافية
    "duplicate",               # مكرر
    "other",                   # سبب آخر — يلزمه نصّ
    # **قرارٌ سبق اشتراطَ السبب.** صفٌّ استُبعد قبل هذا الترحيل لا سبب له،
    # ولا يجوز أن يُخترع له واحد. فيُسمّى ما هو: «لم يُسجَّل سببه». والـAPI
    # لا يقبله مُدخَلًا أبدًا — فلا يصير بابًا خلفيًّا لاستبعادٍ بلا سبب.
    "unrecorded_legacy",
)

# حال الخلية — **مفردات المنصّة نفسها** كما في «دماغ البحث» و`BrainEntryView`،
# لا مفرداتٌ ثانية تعني الشيء نفسه بأسماء أخرى.
CELL_STATES = ("known", "needs_review", "missing", "conflicting")

# **مدى ما قُرئ.** الفرق بين الثلاثة هو الفرق بين قراءةٍ وادّعاء قراءة.
SOURCE_SCOPES = ("metadata_only", "abstract_only", "full_text")

# كيف وصلت القيمة إلى الخلية. و`model` تبقى مرشَّحة حتى يعتمدها إنسان.
EXTRACTION_METHODS = ("researcher", "metadata", "model")

# §7.4 مع «لا أعرف» من الترحيل 0016 — امتناعٌ عن الحكم ليس حكمًا بالبطلان.
VERIFICATION_STATES = ("unverified", "approved", "rejected", "unknown")

# أعمدة المصفوفة. تُكتب هنا مرّة ويشتقّها النموذج والخدمة منها — فلا يفترق
# موضعان بحرفٍ فيصير القيد يرفض عمودًا تعرضه الشاشة.
MATRIX_FIELDS = (
    "reference", "year", "problem", "objective", "theory", "design", "method",
    "population", "sample", "context", "constructs", "measures", "analysis",
    "findings", "limitations", "gaps",
)


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # ── ١. الاستبعاد يلزمه سبب — على الصفّ القائم لا على صفٍّ جديد ──
    #
    # العمود على `project_sources` نفسه عمدًا: حالُ الاستعمال هناك، فالسبب
    # الذي يفسّرها يقع في الصفّ نفسه. وجدولُ أسبابٍ منفصل يسمح بصفٍّ
    # مستبعَدٍ بلا سبب وسببٍ بلا صفّ، ثم يحتاج حارسًا يمنع الحالين.
    op.add_column("project_sources",
                  sa.Column("exclusion_reason_code", sa.String(32), nullable=True))

    # **ما استُبعد قبل اليوم يُسمّى ما هو.** لا يُخترع له سبب، ولا يُترك
    # فارغًا فيرفضه القيد بعد سطرين. و`unrecorded_legacy` تقول الحقيقة:
    # قرارٌ وقع قبل أن تُطلب الأسباب.
    op.execute(
        "UPDATE project_sources SET exclusion_reason_code = 'unrecorded_legacy' "
        "WHERE use_state = 'excluded' AND exclusion_reason_code IS NULL"
    )

    op.create_check_constraint(
        "exclusion_reason_code", "project_sources",
        f"exclusion_reason_code IS NULL OR "
        f"{_in('exclusion_reason_code', EXCLUSION_REASON_CODES)}",
    )
    # **الاستبعاد بلا سبب مرفوض من القاعدة.** ومن ألغى الاستبعاد يمحو سببه
    # معه: سببٌ باقٍ بجانب حالٍ لم تعد قائمة يُقرأ يومًا حكمًا لم يُقل.
    op.create_check_constraint(
        "exclusion_needs_reason", "project_sources",
        "(use_state = 'excluded') = (exclusion_reason_code IS NOT NULL)",
    )
    # و«سبب آخر» بلا نصّ ليس سببًا — هو خانةٌ فارغة تُعدّ سببًا في التقرير.
    op.create_check_constraint(
        "other_reason_needs_note", "project_sources",
        "exclusion_reason_code <> 'other' OR "
        "(reason_ar IS NOT NULL AND length(btrim(reason_ar)) > 0)",
    )
    # شاشة «الدراسات المستبعدة» تقرأ سببًا سببًا؛ وفهرسٌ جزئيّ يكفيها لأنها
    # الأقلّ عددًا عادةً، ولا يثقل كل كتابةٍ على الجدول.
    op.create_index("ix_project_sources_excluded", "project_sources",
                    ["tenant_id", "project_id", "exclusion_reason_code"],
                    postgresql_where=sa.text("use_state = 'excluded'"))

    # ── ٢. خلايا مصفوفة الأدبيات ──
    op.create_table(
        "literature_matrix_cells",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        # **`RESTRICT` على المرجع** كما في `project_sources`: إزالته من بحثٍ
        # شيء، وإتلافه من المكتبة شيء آخر لا يقع بأثرٍ جانبي للأول.
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("field_key", sa.String(32), nullable=False),
        # القيمة تغيب حين تغيب المعلومة — و`NULL` هنا «لم يُذكر»، لا نصًّا
        # فارغًا يُعرض خانةً بيضاء تُقرأ «لا شيء يستحق».
        sa.Column("value_ar", sa.Text, nullable=True),
        sa.Column("cell_state", sa.String(16), nullable=False),
        sa.Column("source_scope", sa.String(16), nullable=False),
        sa.Column("extraction_method", sa.String(16), nullable=False),
        # الملف الذي قُرئ منه إن وُجد. `SET NULL` لأن ذهاب الملف من المكتبة
        # لا يُبطل ما قرأه الباحث منه — يُبطل إمكان العودة إليه فقط.
        sa.Column("source_file_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_quote", sa.Text, nullable=True),
        sa.Column("evidence_locator", sa.Text, nullable=True),
        sa.Column("verification_status", sa.String(16), nullable=False,
                  server_default="unverified"),
        sa.Column("verified_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("verified_at", TS, nullable=True),
        sa.Column("updated_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.CheckConstraint(_in("field_key", MATRIX_FIELDS), name="field_key"),
        sa.CheckConstraint(_in("cell_state", CELL_STATES), name="cell_state"),
        sa.CheckConstraint(_in("source_scope", SOURCE_SCOPES), name="source_scope"),
        sa.CheckConstraint(_in("extraction_method", EXTRACTION_METHODS),
                           name="extraction_method"),
        sa.CheckConstraint(_in("verification_status", VERIFICATION_STATES),
                           name="verification_status"),
        # **الغياب غيابٌ لا فراغٌ يُملأ.** خليةٌ حالها `missing` تحمل قيمةً
        # هي أسوأ ما في مصفوفة أدبيات: مقياسٌ لم يُذكر في الورقة يظهر في
        # عمود «المقاييس»، ثم يُكتب في قسم المنهجية أنه استُعمل.
        sa.CheckConstraint(
            "cell_state <> 'missing' OR "
            "(value_ar IS NULL AND evidence_quote IS NULL AND evidence_locator IS NULL)",
            name="missing_carries_nothing"),
        # وخليةٌ ليست `missing` بلا قيمة حالٌ لا معنى لها — «معلوم» بلا معلوم.
        sa.CheckConstraint(
            "cell_state = 'missing' OR "
            "(value_ar IS NOT NULL AND length(btrim(value_ar)) > 0)",
            name="stated_cell_has_a_value"),
        # §14.5 — لا نصّ فلا مقتطف. بياناتٌ وصفية لا يُقتبس منها شيء، ومن
        # اقتبس من عنوانٍ وسنةٍ فقد اخترع.
        sa.CheckConstraint(
            "source_scope <> 'metadata_only' OR evidence_quote IS NULL",
            name="metadata_only_has_no_quote"),
        # **ولا تُخترع أرقام صفحات.** الملخّص لا صفحات له؛ فمُحدِّدُ خليةٍ
        # قُرئت من ملخّصٍ إمّا غائب وإمّا الكلمة الصريحة `abstract`.
        sa.CheckConstraint(
            "source_scope <> 'abstract_only' OR evidence_locator IS NULL "
            "OR evidence_locator = 'abstract'",
            name="abstract_has_no_page_number"),
        sa.CheckConstraint(
            "source_scope <> 'metadata_only' OR evidence_locator IS NULL",
            name="metadata_only_has_no_locator"),
        # مراجعةٌ بلا مراجِعٍ ووقت لا تكون — قاعدة كل قرارٍ بشري في المنظومة.
        sa.CheckConstraint(
            "verification_status = 'unverified' OR "
            "(verified_by IS NOT NULL AND verified_at IS NOT NULL)",
            name="verification_actor"),
        # **ما استخرجه نموذج يبقى مرشَّحًا.** لا يصير معرفةً إلا بفعلٍ بشريٍّ
        # لاحقٍ يُنسب إلى صاحبه — والقيد يمنع أن يُكتب معتمَدًا بلا مُعتمِد.
        sa.CheckConstraint(
            "extraction_method <> 'model' OR verification_status = 'unverified' "
            "OR verified_by IS NOT NULL",
            name="model_value_is_not_self_approved"),
        # خليةٌ واحدة لكل (بحث، مرجع، عمود). وبدونها تتراكم نسخٌ تفترق، ولا
        # يعرف أحدٌ أيّها المعروض.
        sa.UniqueConstraint("project_id", "source_id", "field_key",
                            name="uq_matrix_cell"),
    )
    # قراءةُ الشاشة الواحدة: مصفوفةُ بحثٍ بعينه صفًّا صفًّا.
    op.create_index("ix_literature_matrix_cells_project", "literature_matrix_cells",
                    ["tenant_id", "project_id", "source_id"])

    # ── ٣. العزل: مفعَّل **ومفروض**، ومنحُ الدور صريح (ADR-0002) ──
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
    """التنازل يرفض ولا يمحو سبب استبعادٍ ولا خليةً راجعها الباحث.

    سببُ الاستبعاد حكمٌ قاله باحثٌ بعد نظر، وإسقاطُ العمود يمحوه بلا أثر —
    فتبقى الدراسة مستبعَدة ولا يعرف أحدٌ لماذا، وهو بالضبط العطب الذي
    أُنشئ هذا الترحيل ليمنعه.

    وخلايا المصفوفة المراجَعة معرفةٌ حكم فيها إنسان؛ وإسقاط الجدول عليها
    إتلافُ مراجعةٍ لإرضاء تنازل. فيُطلب القرار أولًا — كما في 0020 و0022.
    """
    bind = op.get_bind()

    excluded = bind.execute(sa.text(
        "SELECT count(*) FROM project_sources WHERE exclusion_reason_code IS NOT NULL"
    )).scalar_one()
    if excluded:
        raise RuntimeError(
            f"downgrade refused: {excluded} source link(s) carry a recorded exclusion "
            "reason; dropping the column would leave studies excluded for reasons no "
            "one can read. Re-open or decide them deliberately first. | "
            f"التنازل مرفوض: {excluded} مرجعًا يحمل سبب استبعادٍ مسجَّلًا."
        )

    reviewed = bind.execute(sa.text(
        "SELECT count(*) FROM literature_matrix_cells "
        "WHERE verification_status <> 'unverified'"
    )).scalar_one()
    if reviewed:
        raise RuntimeError(
            f"downgrade refused: {reviewed} matrix cell(s) carry a human review. "
            "Dropping the table would destroy it. | "
            f"التنازل مرفوض: {reviewed} خليةً راجعها الباحث."
        )

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_index("ix_literature_matrix_cells_project",
                  table_name="literature_matrix_cells")
    op.drop_table("literature_matrix_cells")

    op.drop_index("ix_project_sources_excluded", table_name="project_sources")
    for constraint in ("other_reason_needs_note", "exclusion_needs_reason",
                       "exclusion_reason_code"):
        op.execute("ALTER TABLE project_sources DROP CONSTRAINT "
                   f"ck_project_sources_{constraint}")
    op.drop_column("project_sources", "exclusion_reason_code")
