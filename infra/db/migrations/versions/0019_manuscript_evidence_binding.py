"""ربط المخطوطة بأدلتها | Structural evidence binding for manuscripts (S5E-A).

**توسيعٌ لا معماريةٌ موازية — وهذه المرة أضيق مما اقترحتُ أولًا.**

`manuscripts` و`manuscript_versions` و`manuscript_sections` قائمة منذ 0011،
وتمثّل بالفعل: وعاء المسودة، وتاريخ المراجعات بسببٍ مكتوب وسلسلة `supersedes`،
ومحتوى الأقسام بقيدٍ على مفاتيحها الثمانية عشر. فلا `manuscript_drafts` يُخترع،
ولا تاريخُ مراجعاتٍ ثانٍ يُبنى بجانب `manuscript_versions`.

وما ينقص **علاقات إسناد**، لا كيانات:

    manuscript_section ──┐
                         ├─→ claim ──┬─→ researcher_memory   (حقيقة الباحث)
                         │           └─→ analysis_output     (رقمٌ من تشغيلة)
                         └── (القسم يعرف ادعاءاته بمفتاح أجنبي لا بمصفوفة)

**ولماذا `analysis_outputs` لا `analysis_runs`؟**

`manuscript_sections.analysis_run_ids` مصفوفةٌ تثبت أن «تشغيلةً ما موجودة في
هذا القسم» — ولا تثبت أن **هذا الرقم بعينه** خرج من **ذلك المخرَج بعينه**.
والفرق ليس شكليًّا: قسمٌ فيه تشغيلة انحدار لا يجعل متوسطًا مكتوبًا فيه مسنَدًا.
فالرابط إلى المخرَج، والتشغيلة تُشتقّ منه عبر `analysis_outputs.run_id` — مصدر
حقيقة واحد لا عمودان يفترقان.

**ولا `run_id` مكرَّر هنا** — للسبب نفسه الذي منع نسخ الإسناد في 0017.

**والمفردات واحدة.** `outline.py` كان يُصدر `methods` و`literature`، والمفردات
القانونية في `services/publishing/vocab.py` تقول `method` و`literature_review`.
و`manuscript_sections.section_key` عليه قيدٌ بالمفاتيح القانونية — فأول تحويل
لهيكل S5D إلى أقسام مخطوطة كانت القاعدة سترفضه. وهو صنف الانحراف نفسه الذي
أنتج عوائق S5D الثلاثة: معرّفٌ يُكتب بجانب سجلّه بدل أن يُشتقّ منه. فيُحوَّل
المحفوظ هنا، ويُشتقّ المولَّد في الشيفرة، ويحرس الاثنين اختبارٌ في CI.

Revision ID: 0019
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# حالات مراجعة القسم (§18) — قرار الباحث في نصٍّ ولّده نموذج.
# ولا تُخلط بـ`manuscripts.status` التي تصف دورة حياة الورقة كلها.
SECTION_REVIEW_STATUSES = ("draft", "needs_review", "approved", "revision_requested")

# مستوى السند — **من مفردات `claim_evidence_links` القائمة**، لا مفردات ثانية.
SUPPORT_LEVELS = ("direct", "partial", "contextual", "contradictory")

# مفاتيح أقسام المخطوطة القانونية — نسخةٌ حرفية من
# `athera_api/services/publishing/vocab.py::MANUSCRIPT_SECTIONS`.
#
# والترحيل لا يستورد من التطبيق عمدًا (فالترحيلات تعمل على شيفرة قد تتقدّم
# عليها)، لكن الانحراف بينهما لا يُترك للحظّ: اختبارٌ في الحزمة يقارن الاثنين.
MANUSCRIPT_SECTIONS = (
    "title", "abstract", "keywords", "introduction", "problem_gap",
    "literature_review", "theory", "hypotheses_questions", "method", "results",
    "discussion", "contributions", "implications", "limitations",
    "future_research", "conclusion", "declarations", "references",
)

# المفاتيح القديمة التي أصدرها هيكل S5D → مقابلها القانوني.
OUTLINE_KEY_RENAMES = {"methods": "method", "literature": "literature_review"}

NEW_TABLES = ("manuscript_section_claims", "claim_memory_links", "claim_analysis_links")


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


def _rename_outline_keys(bind, mapping: dict[str, str]) -> int:
    """يعيد تسمية مفاتيح الأقسام داخل `manuscript_outlines.sections`.

    والترتيب محفوظ: `WITH ORDINALITY` ثم `ORDER BY` — فمصفوفة الأقسام ترتيبها
    معنى، ولا يُترك لعشوائية التجميع.
    """
    if not mapping:
        return 0
    cases = " ".join(
        f"WHEN elem->>'key' = '{old}' THEN jsonb_set(elem, '{{key}}', '\"{new}\"') "
        for old, new in mapping.items()
    )
    predicate = " OR ".join(
        f"""sections @> '[{{"key": "{old}"}}]'::jsonb""" for old in mapping
    )
    result = bind.execute(sa.text(
        f"""
        UPDATE manuscript_outlines SET sections = (
            SELECT jsonb_agg(CASE {cases} ELSE elem END ORDER BY ord)
            FROM jsonb_array_elements(sections) WITH ORDINALITY AS t(elem, ord)
        )
        WHERE {predicate}
        """
    ))
    return result.rowcount


def _outline_keys(bind) -> set[str]:
    rows = bind.execute(sa.text(
        "SELECT DISTINCT elem->>'key' FROM manuscript_outlines, "
        "jsonb_array_elements(sections) AS elem"
    )).scalars().all()
    return {key for key in rows if key}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. المخطوطة تعرف الفرصة والهيكل اللذين وُلدت عنهما ──
    #
    # عمودان لا جدول: السؤال «من أي فرصة ومن أي هيكل؟» يجيب عنه مفتاحان
    # أجنبيان على الكيان القائم. وكلاهما قابل للعدم — مخطوطات ما قبل S5E
    # لا فرصة لها ولا هيكل، ولا تُخترع لها قيمة.
    op.add_column("manuscripts", sa.Column(
        "opportunity_id", PgUUID(as_uuid=True),
        sa.ForeignKey("publication_opportunities.id", ondelete="SET NULL"), nullable=True))
    op.add_column("manuscripts", sa.Column(
        "outline_id", PgUUID(as_uuid=True),
        sa.ForeignKey("manuscript_outlines.id", ondelete="SET NULL"), nullable=True))

    # ── 2. القسم يحمل حال مراجعته وبصمة سياق صياغته ──
    #
    # والبصمة على القسم لا على المخطوطة: الموافقة تُعطى لصياغة **قسم** من
    # أدلةٍ بعينها، وأدلةٌ تُضاف بعدها لا تُرسل تحتها.
    op.add_column("manuscript_sections", sa.Column(
        "review_status", sa.String(20), nullable=False, server_default="draft"))
    op.add_column("manuscript_sections", sa.Column(
        "reviewed_by", PgUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("manuscript_sections", sa.Column("reviewed_at", TS, nullable=True))
    op.add_column("manuscript_sections", sa.Column(
        "drafting_context_fingerprint", sa.String(64), nullable=True))
    op.add_column("manuscript_sections", sa.Column(
        "generation_run_id", PgUUID(as_uuid=True),
        sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True))

    op.create_check_constraint(
        "review_status", "manuscript_sections",
        _in("review_status", SECTION_REVIEW_STATUSES))
    # قرارٌ بشري بلا فاعل ووقت لا يكون — كما `planning_actor` في 0017.
    op.create_check_constraint(
        "review_actor", "manuscript_sections",
        "review_status IN ('draft','needs_review') OR "
        "(reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)")

    # ── 3. القسم ← الادعاء، بمفتاح أجنبي ──
    #
    # `manuscript_sections.claim_ids` مصفوفةُ JSON تبقى للتوافق، ولا تكون
    # مرجعًا: مصفوفة تُجيب اليوم وتكذب غدًا حين يُحذف ادعاء فيبقى معرّفه
    # معلّقًا بلا أن ينبّه أحد.
    op.create_table(
        "manuscript_section_claims", *_base(),
        sa.Column("section_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("claim_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("section_id", "claim_id", name="uq_section_claim"),
    )
    op.create_index("ix_section_claims_section", "manuscript_section_claims",
                    ["tenant_id", "section_id"])

    # ── 4. الادعاء ← ذاكرة الباحث الموثقة ──
    #
    # `claim_evidence_links` القائم يشترط `excerpt_id` و`source_id` — أي
    # مقتطفًا من **مصدر أدبيات خارجي**، وكلاهما غير قابل للعدم. فلا يستطيع
    # اليوم أن يقول: «هذا الادعاء تسنده معرفة الباحث الموثقة». وذلك بالضبط
    # ما تحتاجه S5E، والسجل الخارجي مغلق أصلًا حتى S5F.
    #
    # و`RESTRICT` على الذاكرة عمدًا: دليلٌ يسند ادعاءً في مخطوطة لا يختفي
    # صامتًا — كما في `planning_run_evidence`.
    op.create_table(
        "claim_memory_links", *_base(),
        sa.Column("claim_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("researcher_memories.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("support_level", sa.String(16), nullable=False),
        sa.CheckConstraint(_in("support_level", SUPPORT_LEVELS),
                           name="ck_claim_memory_links_support_level"),
        sa.UniqueConstraint("claim_id", "memory_id", name="uq_claim_memory"),
    )
    op.create_index("ix_claim_memory_claim", "claim_memory_links",
                    ["tenant_id", "claim_id"])

    # ── 5. الادعاء ← المخرَج التحليلي بعينه ──
    #
    # **إلى `analysis_outputs` لا `analysis_runs`.** وجودُ تشغيلةٍ في القسم
    # لا يجعل رقمًا مكتوبًا فيه مسنَدًا؛ السند أن يكون **هذا الرقم** في
    # **هذا المخرَج**. و`statistic_excerpt` يحفظ الصيغة كما وردت في الادعاء،
    # فيبقى التطابق قابلًا للفحص بعد شهور.
    #
    # ولا عمود `run_id` هنا: التشغيلة تُشتقّ من `analysis_outputs.run_id`.
    op.create_table(
        "claim_analysis_links", *_base(),
        sa.Column("claim_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("claims.id", ondelete="CASCADE"), nullable=False),
        sa.Column("output_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("analysis_outputs.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("statistic_excerpt", sa.Text, nullable=False),
        sa.UniqueConstraint("claim_id", "output_id", name="uq_claim_analysis"),
    )
    op.create_index("ix_claim_analysis_claim", "claim_analysis_links",
                    ["tenant_id", "claim_id"])

    # ── 6. العزل: مفعَّل ومفروض على كل جدول جديد ──
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = app_current_tenant()) "
            "WITH CHECK (tenant_id = app_current_tenant())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO athera_app")

    # ── 7. توحيد مفردات الأقسام في الهياكل المحفوظة ──
    #
    # **قبل:** لا مفتاح خارج (القانوني ∪ القديم المعروف) — فمفتاحٌ ثالث يعني
    # انحرافًا لا نعرفه، ولا يُخمَّن له مقابل.
    before = _outline_keys(bind)
    unexpected = before - set(MANUSCRIPT_SECTIONS) - set(OUTLINE_KEY_RENAMES)
    if unexpected:
        raise RuntimeError(
            "migration refused: stored outlines carry unknown section key(s) "
            f"{sorted(unexpected)}. They map to no canonical section and will not be "
            "guessed. Resolve them deliberately first. | "
            f"الترحيل مرفوض: هياكل محفوظة تحمل مفاتيح أقسام غير معروفة "
            f"{sorted(unexpected)} — ولا يُخمَّن لها مقابل."
        )
    renamed = _rename_outline_keys(bind, OUTLINE_KEY_RENAMES)
    print(f"[0019] outlines with renamed section keys: {renamed}")

    # **بعد:** كل مفتاح قسم محفوظ ينتمي إلى المفردات القانونية — وإلا فشل.
    after = _outline_keys(bind)
    leftover = after - set(MANUSCRIPT_SECTIONS)
    if leftover:
        raise RuntimeError(
            f"migration failed its own postcondition: outline section key(s) {sorted(leftover)} "
            "are still outside MANUSCRIPT_SECTIONS after the rename."
        )


def downgrade() -> None:
    """التنازل يرفض ولا يمحو قرار مراجعةٍ بشريًّا.

    قسمٌ اعتمده الباحث أو طلب مراجعته حكمٌ قاله على نصٍّ قرأه. وحذف العمود
    الذي يحمله يمحو الحكم بلا أثر — فيُرفض ويُقال العدد وما يجب فعله، كما
    فعل 0016 مع «لا أعرف» و0017 مع قرار التخطيط.

    وروابط الإسناد تُحذف: هي مخرجات قابلة لإعادة البناء من الأدلة نفسها،
    لا أحكامًا بشرية.
    """
    bind = op.get_bind()

    # **كل الفحوص أولًا، ثم التعديل** — الدرس المسجَّل في 0017: رفضٌ في منتصف
    # التنازل يترك القاعدة نصف مُنزَّلة، وذلك أسوأ من تنازل يتمّ.
    decided = bind.execute(sa.text(
        "SELECT count(*) FROM manuscript_sections "
        "WHERE review_status IN ('approved','revision_requested')"
    )).scalar_one()
    if decided:
        raise RuntimeError(
            f"downgrade refused: {decided} manuscript section(s) carry a human review "
            "decision (approved or revision_requested). Dropping review_status would "
            "destroy it. Resolve or export them first, then retry. | "
            f"التنازل مرفوض: {decided} قسم مخطوطة يحمل قرار مراجعة بشريًّا "
            "(معتمَد أو مطلوب تعديله). حذف العمود يمحو القرار."
        )

    reviewed_claims = bind.execute(sa.text(
        "SELECT count(*) FROM claims c "
        "WHERE c.reviewed_by IS NOT NULL AND EXISTS ("
        "  SELECT 1 FROM manuscript_section_claims l WHERE l.claim_id = c.id)"
    )).scalar_one()
    if reviewed_claims:
        raise RuntimeError(
            f"downgrade refused: {reviewed_claims} manuscript claim(s) carry a researcher "
            "review. Dropping the section binding would orphan that judgement. | "
            f"التنازل مرفوض: {reviewed_claims} ادعاء في مخطوطة يحمل مراجعة باحث."
        )

    # عكسٌ حتمي: كل مفتاح قانوني كان له مقابل قديم يعود إليه، ولا غيره.
    _rename_outline_keys(bind, {new: old for old, new in OUTLINE_KEY_RENAMES.items()})

    for table in NEW_TABLES:
        op.drop_table(table)

    for short in ("review_actor", "review_status"):
        # حذفٌ بـSQL صريح — واجهة alembic تعيد تطبيق اصطلاح التسمية على اسمٍ
        # طُبّق عليه أصلًا، فلا يطابق ما أُنشئ (الدرس المسجَّل في 0017).
        op.execute(f"ALTER TABLE manuscript_sections DROP CONSTRAINT "
                   f"ck_manuscript_sections_{short}")

    for column in ("generation_run_id", "drafting_context_fingerprint",
                   "reviewed_at", "reviewed_by", "review_status"):
        op.drop_column("manuscript_sections", column)
    for column in ("outline_id", "opportunity_id"):
        op.drop_column("manuscripts", column)
