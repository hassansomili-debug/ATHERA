"""طبقة التركيب | Synthesis layer: themes, contradictions, gaps (PUBRIVA).

**أخطر ما في المنتج أن يصير مولِّد فجواتٍ زائفة.** فقيمةُ هذه الطبقة أن
تُظهر عدم اليقين، لا أن تصنع يقينًا. وكل عمودٍ هنا مكتوبٌ لهذا الغرض
وحده: لا حقل يقول «توجد فجوة»، وكل حقلٍ يقول **ضمن أيّ مجموعةٍ نظرنا**.

## أربع حقائق لا تُطوى في واحدة

  تجميعٌ موضوعي   عناوينٌ تتشارك كلمات — ليس نتيجة
  موضوعٌ علمي     تركيبٌ مسنودٌ بمحتوى قُرئ — نتيجة مرشَّحة
  تعارضٌ محتمل    نتيجتان تختلفان في **بناءَين متقابلين**
  فجوةٌ محتملة    ما لم يظهر **في هذه المجموعة**، بحدودها معلنة

وطيُّ الأولى في الثانية هو العطب الذي يُنتج «فجوات» من عناوين. فالفرق
مكتوبٌ في القاعدة عمودًا (`basis`) لا في الشاشة وحدها، ويُشتقّ من سندٍ
مرتبطٍ بخلية مصفوفة — أو لا يُشتقّ.

## السند يُتتبَّع أو لا يكون

`theme_candidate_supports.matrix_cell_id` يشير إلى خليةٍ في مصفوفة
الأدبيات (ترحيل 0023)، والخلية تحمل مقتطفها ومَداها ومَن كتبها. فالمسار
كامل: موضوع ← مرجع ← خلية ← شاهد. وسندٌ يدّعي محتوًى بلا خليةٍ يشير إليها
يرفضه القيد `content_support_points_at_a_cell` — فلا «موضوع» بلا أثر.

## الفجوة تحمل مداها معها

`sources_considered` و`search_scope` و`source_scope_distribution` و
`known_limitations_ar` **كلّها إلزامية وغير فارغة**. ودعوى «لا توجد
دراسات» لا مكان لها في هذا المخطَّط أصلًا: أكبر ما يمكن قوله أن شيئًا لم
يظهر في مجموعةٍ عددها معلوم بحثت فهارس معلومة. وفجوةٌ بلا حدودٍ معلنة
دعوى، فالقيد يرفض `known_limitations_ar` الفارغة.

## والفرصة لا تُولَد من فجوةٍ لم تُعتمَد

وهذا مفروضٌ من القاعدة لا من الخدمة: `research_opportunities` ترتبط
بـ`gap_candidates` بمفتاحٍ **مركّب** يضمّ الحال، وعمودها `gap_status`
مقيَّدٌ بـ`approved`. فإدراجُ فرصةٍ فوق فجوةٍ مولَّدة يُرفض؛ و`ON UPDATE
RESTRICT` يمنع سحبَ الاعتماد من تحت فرصةٍ قائمة — فلا تبقى فرصةٌ معلّقةً
في الهواء ولا يُمحى قرارٌ بشريّ بأثرٍ جانبي.

## والعزل بين بحثين داخل المستأجر الواحد بنيويّ

RLS تحمي بين المستأجرين ولا تحمي بين بحثين في مستأجرٍ واحد — وهذا عطبٌ
وقع في هذا المنتج من قبل. فكل صفٍّ تابع يحمل `project_id` ويرتبط بأبيه
**بمفتاحٍ مركّب** `(parent_id, project_id)`: سندُ موضوعٍ لا يمكن أن يشير
إلى خليةٍ من بحثٍ آخر، لا لأن الخدمة تصفّي، بل لأن القاعدة ترفض.

Revision ID: 0024
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = (
    "theme_candidates",
    "theme_candidate_supports",
    "contradiction_candidates",
    "contradiction_sides",
    "gap_candidates",
    "gap_candidate_sources",
    "research_opportunities",
)

# **دورة الحياة مفرداتُ المنصّة نفسها.** `needs_review` من حالات الخلية
# (0023) و«دماغ البحث»، و`unknown` من ترحيل 0016: من راجع مرشَّحًا ولم
# يستطع الحكم **لم يرفضه**. ولا `UNSURE` ولا `MAYBE` — مفردةٌ ثانية تعني
# الشيء نفسه باسمٍ آخر هي أول طريقٍ إلى حالتين تفترقان.
SYNTHESIS_STATUSES = ("generated", "needs_review", "approved", "rejected", "unknown")

# **الفرق بين تجميعٍ موضوعي وموضوعٍ علمي عمودٌ لا حاشية.**
THEME_BASES = ("topic_cluster", "content_synthesis")

# كيف نشأ المرشَّح. `deterministic` تعني قواعد حتمية لا نموذجًا — ولا قيمة
# `model` هنا اليوم لأن لا مسار نموذجٍ يكتب في هذه الجداول بعد.
GENERATION_METHODS = ("deterministic", "researcher")

SUPPORT_ROLES = ("supporting", "contradicting")

# و«نُظر فيه» ثالثةٌ في الفجوة وحدها: مرجعٌ فُحص ولم يسند ولم يعارض هو
# **جزءٌ من مدى البحث** — وإسقاطه يجعل الفجوة تبدو أوسع مما نُظر فيه.
GAP_SOURCE_ROLES = ("supporting", "contradicting", "considered")

# **التعارض له معنًى في أربعةٍ فقط.** واختلافُ الصياغة ليس منها، واختلافُ
# البناءات ليس منها — دراستان عن شيئين مختلفين لا تتعارضان.
CONFLICT_KINDS = ("direction", "significance", "effect_presence", "conclusion")

EFFECT_DIRECTIONS = ("positive", "negative", "none", "mixed", "not_stated")

SIGNIFICANCE_STATES = ("significant", "not_significant", "not_stated")

# **مفردة الفجوات مغلقة.** ونصٌّ حرٌّ في نوع الفجوة يجعل التقرير غير قابلٍ
# للعدّ ولا للمقارنة، ويسمح باختراع نوعٍ يبرّر دعوى.
GAP_TYPES = (
    "context_gap",              # فجوة سياق
    "population_gap",           # فجوة مجتمع
    "method_gap",               # فجوة منهج
    "theory_gap",               # فجوة نظرية
    "measurement_gap",          # فجوة قياس
    "temporal_gap",             # فجوة زمنية
    "contradictory_evidence",   # أدلة متعارضة
    "understudied_relationship",  # علاقة قليلة الدرس
    "replication_need",         # حاجة إلى تكرار
)

# **قوّةٌ توصف ولا تُرقَّم.** «٧٣٪ ثقة» رقمٌ مخترَع يوهم قياسًا لم يقع؛
# والثلاثة هنا لها معانٍ معرَّفة في `services/synthesis/vocab.py`.
GAP_STRENGTHS = ("weak_signal", "emerging_pattern", "supported_candidate")

# مَدى القراءة — منقولٌ حرفيًّا عن 0023، ولا يُعرَّف من جديد.
SOURCE_SCOPES = ("metadata_only", "abstract_only", "full_text")


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _decision_constraints() -> tuple:
    """قرارُ إنسانٍ يُنسب إلى صاحبه ووقته — **رفضًا كما اعتمادًا**.

    والعقد طلب `approved_by/at`؛ والعمود هنا `decided_by/at` عمدًا: رفضٌ
    بلا صاحب مثل اعتمادٍ بلا صاحب، وسجلٌّ يعرف من اعتمد ولا يعرف من رفض
    يُقرأ بعد شهرٍ كأن الرفض وقع من تلقائه.
    """
    return (
        sa.CheckConstraint(_in("status", SYNTHESIS_STATUSES), name="status"),
        sa.CheckConstraint(
            "(status IN ('generated', 'needs_review')) = (decided_by IS NULL)",
            name="decision_has_an_author"),
        sa.CheckConstraint(
            "(decided_by IS NULL) = (decided_at IS NULL)",
            name="decision_has_a_time"),
    )


def _decision_columns() -> tuple:
    return (
        sa.Column("status", sa.String(16), nullable=False, server_default="generated"),
        sa.Column("decided_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("decided_at", TS, nullable=True),
    )


def _scoped_columns() -> tuple:
    return (
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
    )


def upgrade() -> None:
    # ── ٠. الخليةُ تُعرَف ببحثها ──
    #
    # قيدٌ فريدٌ على `(id, project_id)` لا يمنع شيئًا بذاته: غرضه أن يصير
    # مرجعًا لمفتاحٍ أجنبيٍّ مركّب، فيستحيل بنيويًّا أن يسند موضوعٌ في بحثٍ
    # إلى خليةٍ في بحثٍ آخر من المستأجر نفسه.
    op.create_unique_constraint(
        "uq_literature_matrix_cells_project_scoped", "literature_matrix_cells",
        ["id", "project_id"])

    # ══════════════════════ ١. الموضوعات ══════════════════════
    op.create_table(
        "theme_candidates",
        *_scoped_columns(),
        sa.Column("label_ar", sa.Text, nullable=False),
        sa.Column("description_ar", sa.Text, nullable=True),
        # **العمود الذي يمنع الخلط.** `topic_cluster` تجميعٌ من بياناتٍ
        # وصفية، و`content_synthesis` تركيبٌ من محتوًى قُرئ. والشاشة تعرض
        # الفرق لأن القاعدة تحمله.
        sa.Column("basis", sa.String(24), nullable=False),
        # توزيعُ مَدى القراءة عبر مراجع الموضوع: {"abstract_only": 4, ...}.
        # موضوعٌ كلّ سنده `metadata_only` ليس نتيجة، والرقم يقول ذلك بلا جدال.
        sa.Column("source_scope_summary", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("generation_method", sa.String(24), nullable=False,
                  server_default="deterministic"),
        sa.Column("generated_at", TS, server_default=sa.text("now()"), nullable=False),
        *_decision_columns(),
        sa.CheckConstraint(_in("basis", THEME_BASES), name="basis"),
        sa.CheckConstraint(_in("generation_method", GENERATION_METHODS),
                           name="generation_method"),
        sa.CheckConstraint("length(btrim(label_ar)) > 0", name="label_is_not_blank"),
        sa.CheckConstraint("jsonb_typeof(source_scope_summary) = 'object'",
                           name="scope_summary_is_an_object"),
        *_decision_constraints(),
        sa.UniqueConstraint("id", "project_id", name="uq_theme_candidates_scoped"),
    )
    op.create_index("ix_theme_candidates_project", "theme_candidates",
                    ["tenant_id", "project_id", "status"])

    op.create_table(
        "theme_candidate_supports",
        *_scoped_columns(),
        sa.Column("theme_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        # العمود الذي جاء منه السند، ومعرّف الخلية نفسها. والثاني هو ما
        # يجعل «اضغط على الموضوع لترى الشاهد» ممكنًا لا موعودًا.
        sa.Column("basis_field_key", sa.String(32), nullable=False),
        sa.Column("matrix_cell_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("evidence_scope", sa.String(16), nullable=False),
        sa.CheckConstraint(_in("role", SUPPORT_ROLES), name="role"),
        sa.CheckConstraint(_in("evidence_scope", SOURCE_SCOPES), name="evidence_scope"),
        # **سندُ محتوًى بلا خليةٍ يشير إليها دعوى.** والبياناتُ الوصفية
        # وحدها هي ما يجوز أن يُسنَد بلا خلية — وهي بالضبط ما لا يصنع
        # موضوعًا علميًّا، بل تجميعًا موضوعيًّا يُسمّى باسمه.
        sa.CheckConstraint(
            "evidence_scope = 'metadata_only' OR matrix_cell_id IS NOT NULL",
            name="content_support_points_at_a_cell"),
        sa.ForeignKeyConstraint(
            ["theme_id", "project_id"],
            ["theme_candidates.id", "theme_candidates.project_id"],
            ondelete="CASCADE", name="fk_theme_candidate_supports_theme"),
        # **الحارس البنيويّ ضد التسرّب بين بحثين.** بلا `ondelete`: حذفُ
        # خليةٍ تسند موضوعًا يُرفض، وحذفُ البحث كلّه يمرّ لأن الفحص يقع في
        # آخر العبارة وقد ذهب الطرفان معًا.
        sa.ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_theme_candidate_supports_cell"),
        sa.UniqueConstraint("theme_id", "source_id", "role", "basis_field_key",
                            name="uq_theme_support"),
    )
    op.create_index("ix_theme_candidate_supports_theme", "theme_candidate_supports",
                    ["tenant_id", "theme_id", "role"])

    # ══════════════════════ ٢. التعارضات ══════════════════════
    op.create_table(
        "contradiction_candidates",
        *_scoped_columns(),
        # البناءان المتقابلان. وبدونهما لا يُقال «تعارض»: دراستان عن
        # شيئين مختلفين لا تتعارضان مهما اختلفت نتيجتاهما.
        sa.Column("construct_a_ar", sa.Text, nullable=False),
        sa.Column("construct_b_ar", sa.Text, nullable=True),
        sa.Column("relationship_ar", sa.Text, nullable=False),
        sa.Column("conflict_kind", sa.String(32), nullable=False),
        # **السياق أنفع من كلمة «تتعارضان».** «إحداهما درست المستهلكين في
        # السعودية والأخرى موظفي شركات في الولايات المتحدة» تفسير محتمل
        # يعيد الباحث إلى التفكير؛ و«الدراستان متعارضتان» تغلق التفكير.
        sa.Column("context_explanation_ar", sa.Text, nullable=True),
        # الأبعاد التي اختلف فيها الطرفان: ["country", "population", ...].
        sa.Column("context_divergence", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("generation_method", sa.String(24), nullable=False,
                  server_default="deterministic"),
        sa.Column("generated_at", TS, server_default=sa.text("now()"), nullable=False),
        *_decision_columns(),
        sa.CheckConstraint(_in("conflict_kind", CONFLICT_KINDS), name="conflict_kind"),
        sa.CheckConstraint(_in("generation_method", GENERATION_METHODS),
                           name="generation_method"),
        sa.CheckConstraint("length(btrim(construct_a_ar)) > 0",
                           name="construct_is_not_blank"),
        sa.CheckConstraint("jsonb_typeof(context_divergence) = 'array'",
                           name="divergence_is_an_array"),
        *_decision_constraints(),
        sa.UniqueConstraint("id", "project_id",
                            name="uq_contradiction_candidates_scoped"),
    )
    op.create_index("ix_contradiction_candidates_project", "contradiction_candidates",
                    ["tenant_id", "project_id", "status"])

    op.create_table(
        "contradiction_sides",
        *_scoped_columns(),
        sa.Column("contradiction_id", PgUUID(as_uuid=True), nullable=False),
        # **الطرفان يُحفظان كلاهما.** تعارضٌ يُسجَّل بطرفٍ واحد يجعل الثاني
        # «خطأً» بالسكوت عنه — ولا تُسمّى دراسةٌ خاطئة في هذه المنصّة.
        sa.Column("side", sa.String(1), nullable=False),
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("matrix_cell_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("result_ar", sa.Text, nullable=False),
        sa.Column("direction", sa.String(16), nullable=False,
                  server_default="not_stated"),
        sa.Column("significance", sa.String(16), nullable=False,
                  server_default="not_stated"),
        # سياقُ هذا الطرف — وكلّه اختياري لأن غيابه غيابٌ يُعلَن ولا يُملأ.
        sa.Column("population_ar", sa.Text, nullable=True),
        sa.Column("country_ar", sa.Text, nullable=True),
        sa.Column("method_ar", sa.Text, nullable=True),
        sa.Column("measurement_ar", sa.Text, nullable=True),
        sa.Column("period_year", sa.Integer, nullable=True),
        sa.Column("evidence_scope", sa.String(16), nullable=False),
        sa.CheckConstraint("side IN ('a', 'b')", name="side"),
        sa.CheckConstraint(_in("direction", EFFECT_DIRECTIONS), name="direction"),
        sa.CheckConstraint(_in("significance", SIGNIFICANCE_STATES),
                           name="significance"),
        sa.CheckConstraint(_in("evidence_scope", SOURCE_SCOPES), name="evidence_scope"),
        # **طرفٌ لا يقول شيئًا ليس طرفًا في تعارض.** ولو قُبل لصار كلُّ
        # صمتٍ في ورقةٍ نصفَ تعارضٍ يُعلَن للباحث.
        sa.CheckConstraint(
            "direction <> 'not_stated' OR significance <> 'not_stated'",
            name="a_side_states_something"),
        sa.CheckConstraint("length(btrim(result_ar)) > 0", name="result_is_not_blank"),
        # ولا طرفَ من بياناتٍ وصفية: التعارض حكمٌ على نتيجتين مقروءتين،
        # لا على عنوانين.
        sa.CheckConstraint("evidence_scope <> 'metadata_only'",
                           name="a_side_is_read_not_guessed"),
        sa.ForeignKeyConstraint(
            ["contradiction_id", "project_id"],
            ["contradiction_candidates.id", "contradiction_candidates.project_id"],
            ondelete="CASCADE", name="fk_contradiction_sides_parent"),
        sa.ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_contradiction_sides_cell"),
        sa.UniqueConstraint("contradiction_id", "side", "source_id",
                            name="uq_contradiction_side"),
    )
    op.create_index("ix_contradiction_sides_parent", "contradiction_sides",
                    ["tenant_id", "contradiction_id", "side"])

    # ══════════════════════ ٣. الفجوات المحتملة ══════════════════════
    #
    # **`gap_candidates` لا `confirmed_gaps`.** الاسم عقدٌ مع القارئ:
    # لا صفّ في هذه القاعدة يقول «هذه فجوة مؤكَّدة»، ولا حال في دورة
    # الحياة تعني ذلك — `approved` تعني «قرّر باحثٌ متابعتها»، لا «ثبتت».
    op.create_table(
        "gap_candidates",
        *_scoped_columns(),
        sa.Column("gap_type", sa.String(32), nullable=False),
        sa.Column("description_ar", sa.Text, nullable=False),
        sa.Column("why_suggested_ar", sa.Text, nullable=False),
        # **العدد الذي يحدّ الدعوى.** «لم تظهر دراسة» بلا عددٍ نُظر فيه
        # جملةٌ لا يمكن الحكم عليها؛ ومعه تصير قابلة للمراجعة.
        sa.Column("sources_considered", sa.Integer, nullable=False),
        # ما بُحث فعلًا: الفهارس، والمجموعة، وحدود الاستعلام إن وُجدت.
        sa.Column("search_scope", JSONB, nullable=False),
        sa.Column("source_scope_distribution", JSONB, nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        # **حدودُ ما نعرفه تُكتب مع الدعوى لا بعدها.** وفجوةٌ بلا حدودٍ
        # معلنة دعوى — فالقيد يرفض الفراغ.
        sa.Column("known_limitations_ar", sa.Text, nullable=False),
        sa.Column("strength", sa.String(24), nullable=False),
        # فجوةُ «أدلة متعارضة» تشير إلى تعارضها بعينه — ولا تُخترع.
        sa.Column("contradiction_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("generation_method", sa.String(24), nullable=False,
                  server_default="deterministic"),
        sa.Column("generated_at", TS, server_default=sa.text("now()"), nullable=False),
        *_decision_columns(),
        sa.CheckConstraint(_in("gap_type", GAP_TYPES), name="gap_type"),
        sa.CheckConstraint(_in("strength", GAP_STRENGTHS), name="strength"),
        sa.CheckConstraint(_in("generation_method", GENERATION_METHODS),
                           name="generation_method"),
        sa.CheckConstraint("length(btrim(description_ar)) > 0",
                           name="description_is_not_blank"),
        sa.CheckConstraint("length(btrim(why_suggested_ar)) > 0",
                           name="why_is_not_blank"),
        sa.CheckConstraint("length(btrim(known_limitations_ar)) > 0",
                           name="limitations_are_not_blank"),
        # **فجوةٌ فوق صفر مراجع ليست ملاحظة، هي اختراع.**
        sa.CheckConstraint("sources_considered > 0", name="something_was_considered"),
        # ومدى البحث يقول أيّ فهارس بُحثت — وإلا فالدعوى بلا حدّ.
        sa.CheckConstraint("jsonb_exists(search_scope, 'indexes_searched')",
                           name="search_scope_names_its_indexes"),
        sa.CheckConstraint("jsonb_typeof(source_scope_distribution) = 'object'",
                           name="distribution_is_an_object"),
        # و«أدلة متعارضة» وحدها تحمل تعارضًا؛ وغيرها لا يحمل واحدًا.
        sa.CheckConstraint(
            "(gap_type = 'contradictory_evidence') OR contradiction_id IS NULL",
            name="only_contradictory_evidence_carries_a_contradiction"),
        sa.ForeignKeyConstraint(
            ["contradiction_id", "project_id"],
            ["contradiction_candidates.id", "contradiction_candidates.project_id"],
            ondelete="CASCADE", name="fk_gap_candidates_contradiction"),
        *_decision_constraints(),
        sa.UniqueConstraint("id", "project_id", name="uq_gap_candidates_scoped"),
        # مرجعُ المفتاح المركّب الذي يمنع فرصةً فوق فجوةٍ لم تُعتمَد.
        sa.UniqueConstraint("id", "status", name="uq_gap_candidates_status"),
    )
    op.create_index("ix_gap_candidates_project", "gap_candidates",
                    ["tenant_id", "project_id", "status"])

    op.create_table(
        "gap_candidate_sources",
        *_scoped_columns(),
        sa.Column("gap_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("source_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("matrix_cell_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("evidence_scope", sa.String(16), nullable=False),
        sa.CheckConstraint(_in("role", GAP_SOURCE_ROLES), name="role"),
        sa.CheckConstraint(_in("evidence_scope", SOURCE_SCOPES), name="evidence_scope"),
        sa.ForeignKeyConstraint(
            ["gap_id", "project_id"],
            ["gap_candidates.id", "gap_candidates.project_id"],
            ondelete="CASCADE", name="fk_gap_candidate_sources_gap"),
        sa.ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_gap_candidate_sources_cell"),
        sa.UniqueConstraint("gap_id", "source_id", "role", name="uq_gap_source"),
    )
    op.create_index("ix_gap_candidate_sources_gap", "gap_candidate_sources",
                    ["tenant_id", "gap_id", "role"])

    # ══════════════════════ ٤. الفرص البحثية ══════════════════════
    op.create_table(
        "research_opportunities",
        *_scoped_columns(),
        sa.Column("gap_candidate_id", PgUUID(as_uuid=True), nullable=False),
        # **الحال محفوظةٌ مع الرابط لا مقروءةً وقت العرض.** وهي نصف مفتاحٍ
        # أجنبيٍّ مركّب: القاعدة نفسها ترفض فرصةً فوق فجوةٍ غير معتمَدة.
        sa.Column("gap_status", sa.String(16), nullable=False,
                  server_default="approved"),
        sa.Column("phenomenon_ar", sa.Text, nullable=False),
        sa.Column("context_ar", sa.Text, nullable=True),
        sa.Column("population_ar", sa.Text, nullable=True),
        sa.Column("constructs_ar", sa.Text, nullable=True),
        sa.Column("possible_contribution_ar", sa.Text, nullable=False),
        sa.Column("methodological_opportunity_ar", sa.Text, nullable=True),
        sa.Column("evidence_basis_ar", sa.Text, nullable=False),
        # **«ما زال غير مؤكد» ركنٌ في البطاقة لا حاشية.** بطاقةُ فرصةٍ بلا
        # عدم يقينٍ معلن تُقرأ خطةً مثبتة، وهي أبعد ما تكون عن ذلك.
        sa.Column("uncertainties_ar", sa.Text, nullable=False),
        sa.Column("created_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        # البحث الذي أُنشئ من هذه الفرصة — إن أُنشئ، وبتأكيدٍ صريح.
        sa.Column("spawned_project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="SET NULL"),
                  nullable=True),
        sa.CheckConstraint("gap_status = 'approved'", name="gap_must_be_approved"),
        sa.CheckConstraint("length(btrim(phenomenon_ar)) > 0",
                           name="phenomenon_is_not_blank"),
        sa.CheckConstraint("length(btrim(evidence_basis_ar)) > 0",
                           name="evidence_basis_is_not_blank"),
        sa.CheckConstraint("length(btrim(uncertainties_ar)) > 0",
                           name="uncertainties_are_not_blank"),
        # `ON UPDATE RESTRICT` — لا يُسحب الاعتماد من تحت فرصةٍ قائمة.
        sa.ForeignKeyConstraint(
            ["gap_candidate_id", "gap_status"],
            ["gap_candidates.id", "gap_candidates.status"],
            onupdate="RESTRICT", ondelete="RESTRICT",
            name="fk_research_opportunities_gap"),
        sa.ForeignKeyConstraint(
            ["gap_candidate_id", "project_id"],
            ["gap_candidates.id", "gap_candidates.project_id"],
            name="fk_research_opportunities_gap_project"),
    )
    op.create_index("ix_research_opportunities_project", "research_opportunities",
                    ["tenant_id", "project_id", "created_at"])

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
    """التنازل يرفض ولا يمحو حكمًا قاله باحث.

    مرشَّحٌ اعتُمد أو رُفض أو وُقف عنده بـ«لا أعرف» قرارٌ بشريّ منسوبٌ إلى
    صاحبه؛ وإسقاط الجداول عليه إتلافُ ذلك القرار لإرضاء تنازل. وكذلك كل
    فرصةٍ بحثية: هي بطاقةُ عملٍ كتبها إنسان بيده، لا مخرَجًا يُعاد توليده.

    فيُطلب الحسم أولًا — كما في 0016 و0020 و0022 و0023.
    """
    bind = op.get_bind()

    decided = bind.execute(sa.text(
        "SELECT (SELECT count(*) FROM theme_candidates WHERE decided_by IS NOT NULL)"
        " + (SELECT count(*) FROM contradiction_candidates WHERE decided_by IS NOT NULL)"
        " + (SELECT count(*) FROM gap_candidates WHERE decided_by IS NOT NULL)"
    )).scalar_one()
    if decided:
        raise RuntimeError(
            f"downgrade refused: {decided} synthesis candidate(s) carry a human "
            "decision. Dropping these tables would destroy judgements attributed to "
            "the researchers who made them. | "
            f"التنازل مرفوض: {decided} مرشَّحًا يحمل قرارًا بشريًّا."
        )

    opportunities = bind.execute(sa.text(
        "SELECT count(*) FROM research_opportunities")).scalar_one()
    if opportunities:
        raise RuntimeError(
            f"downgrade refused: {opportunities} research opportunity card(s) exist. "
            "Each was written by a person after confirming an approved gap. | "
            f"التنازل مرفوض: {opportunities} بطاقة فرصةٍ بحثية كتبها إنسان."
        )

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index("ix_research_opportunities_project",
                  table_name="research_opportunities")
    op.drop_table("research_opportunities")
    op.drop_index("ix_gap_candidate_sources_gap", table_name="gap_candidate_sources")
    op.drop_table("gap_candidate_sources")
    op.drop_index("ix_gap_candidates_project", table_name="gap_candidates")
    op.drop_table("gap_candidates")
    op.drop_index("ix_contradiction_sides_parent", table_name="contradiction_sides")
    op.drop_table("contradiction_sides")
    op.drop_index("ix_contradiction_candidates_project",
                  table_name="contradiction_candidates")
    op.drop_table("contradiction_candidates")
    op.drop_index("ix_theme_candidate_supports_theme",
                  table_name="theme_candidate_supports")
    op.drop_table("theme_candidate_supports")
    op.drop_index("ix_theme_candidates_project", table_name="theme_candidates")
    op.drop_table("theme_candidates")

    op.drop_constraint("uq_literature_matrix_cells_project_scoped",
                       "literature_matrix_cells", type_="unique")
