"""حالُ معالجة الرسالة عمودًا أوّليًّا | First-class thesis processing state (Wave 1-C).

**العطب عطبُ صدق.** كانت حالُ الرسالة تُشتقّ وقت العرض من
`extraction_runs.status` — وهي حالُ **تشغيلة** على **ملفّ**، لا حالُ رسالة.
فينكسر ثلاثةٌ:

  • رسالةٌ رُفعت ولم تُجدوَل تشغيلة لها تُعرض بلا حالٍ إطلاقًا: `NULL` تُقرأ
    «لا أدري» لا «لم يبدأ».
  • إعادةُ القراءة تُنشئ صفَّ تشغيلةٍ جديدًا فتقفز الحال إلى الوراء، بلا أن
    يقع على الرسالة شيء.
  • والفشل كان يصل إلى الشاشة **صفرًا**: «٠ أقسام · ٠ فرص» جملةٌ واحدة
    تُقال في ستّ حالاتٍ معناها مختلف — لم يبدأ التحليل، ويجري، ولا طبقة
    نصّ، وبانتظار إذن، وسقط، وتمّ فلم يجد. **والفشل ليس فراغًا، وما لم يبدأ
    ليس نتيجةً صفرية.**

## القيود تحمل العقد، لا الخدمة وحدها

`failure_is_named` هو أهمّها: صفٌّ في `failed` أو `text_layer_missing` **لا
يُكتب** بلا رمزِ سبب، وصفٌّ ناجح لا يحمل رمز سقوطٍ قديم. فيستحيل بنيويًّا
أن يصل إلى الشاشة فشلٌ بلا سبب — وهو بعينه العطب الذي وُصف بـ«صفرٌ صامت».

## و`text_layer_missing` حالٌ قائمة بذاتها لا نوعٌ من `failed`

المستند سليم، والقارئ سليم، والذي لا يوجد **طبقةُ نصّ**. وخلطُها بالفشل
يجعل الشاشة تعرض «أعد المحاولة» على مستندٍ ممسوحٍ ضوئيًّا — وعدٌ يخذل، لأن
إعادة القراءة تُنتج النتيجة نفسها حرفًا بحرف.

## وعقدُ OCR يبقى مكتوبًا وإن لم يُنفَّذ

`ocr_state` يقبل خمسًا وافتراضُه `unavailable`، و`ocr_only_when_no_text_layer`
يمنع ادّعاء مسحٍ ضوئيّ على مستندٍ له طبقة نصّ أصلًا. ولا مسار في هذا
المستودع يكتب فيه غير الافتراض — والعمود قائمٌ ليقول ذلك، لا ليتظاهر بغيره.

## إضافةٌ محضة

`theses` جدولٌ قائم، وRLS مفعَّلةٌ ومفروضةٌ عليه منذ ترحيل 0003 وسياستُه
قائمة؛ فلا يُعاد تعريف شيء منها هنا. وكلُّ ما يقع إضافةُ أعمدةٍ بقيمٍ
افتراضية وقيودٍ عليها وفهرسٍ للصفحة.

Revision ID: 0027
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
# **مؤقّتًا فوق 0025.** المسار C يعمل على فرعٍ معزول، و0026 يملكه مسارٌ آخر.
# ويعيد المُكامِل توجيه هذا السطر إلى "0026" حين تصل سلسلتُه — وذلك متوقَّع،
# ولا يُنسَّق من هنا.
down_revision = "0025"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# **تسعُ حالاتٍ مغلقة.** والمفردة نفسها حرفًا بحرف في
# `athera_api/services/thesis/processing.py`، وفحصٌ يقارنهما فلا تفترقان.
PROCESSING_STATES = (
    "uploaded",             # حُفظ الملف ولم يُطلب شيء بعد
    "queued",               # طُلبت المعالجة ولم تبدأ
    "parsing",              # جارٍ قراءة المستند
    "extracting",           # جارٍ استخراج بنية الرسالة
    "awaiting_consent",     # القراءة المحلية تمّت، والإذن الخارجي معلّق
    "ready_for_review",     # مرشّحاتٌ تنتظر مراجعة الباحث
    "completed",            # اكتملت المراجعة
    "failed",               # سقطت المعالجة — ولها رمز سبب
    "text_layer_missing",   # لا طبقة نصّ، ولا OCR بعد
)

FAILURE_STATES = ("failed", "text_layer_missing")

# رموزُ الفشل — **تقنيّة وآمنة**: صنفُ العطب لا مقتطفٌ من مستند الباحث.
FAILURE_CODES = (
    "text_layer_missing", "unsupported_document", "file_missing",
    "storage_unavailable", "parse_failed", "extraction_failed", "unknown",
)

TEXT_LAYER_STATES = ("not_checked", "present", "absent")

OCR_STATES = ("unavailable", "not_attempted", "queued", "completed", "failed")


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


# **الأسماء تُكتب كاملةً وSQL صريح — في الإنشاء والإسقاط معًا.**
#
# اصطلاحُ التسمية في `Base.metadata` يُطبَّق عند `op.drop_constraint` ولا
# يُطبَّق عند `op.create_check_constraint`؛ فمن أنشأ باسمٍ مجرَّد ثمّ أسقط
# به أنشأ `processing_state` وحاول إسقاط `ck_theses_processing_state` —
# اسمٌ لا وجود له. **وينكسر التنازل يوم يُحتاج إليه لا يوم يُكتب**، وفحص
# `test_no_migration_drops_a_constraint_through_the_naming_convention`
# يمنع هذا الصنف من العطب. وترحيل 0015 يحمل الندبة نفسها موصوفة.
CHECKS: tuple[tuple[str, str], ...] = (
    ("ck_theses_processing_state", _in("processing_state", PROCESSING_STATES)),
    ("ck_theses_text_layer_state", _in("text_layer_state", TEXT_LAYER_STATES)),
    ("ck_theses_ocr_state", _in("ocr_state", OCR_STATES)),
    ("ck_theses_failure_code_vocabulary",
     f"failure_code IS NULL OR {_in('failure_code', FAILURE_CODES)}"),
    # **القيدُ الذي يمنع «الصفر الصامت».** فشلٌ بلا سببٍ مكتوب لا يُخزَّن
    # أصلًا، فلا يصل إلى الشاشة صفرٌ لا يُعرف معناه. والعكس مفروضٌ كذلك:
    # صفٌّ يقول «جاهزة للمراجعة» ويحمل رمز سقوطٍ قديم يُقرأ متناقضًا.
    ("ck_theses_failure_is_named",
     f"({_in('processing_state', FAILURE_STATES)}) = (failure_code IS NOT NULL)"),
    # **ولا تفصيلَ فشلٍ بلا فشل**: نصٌّ تقنيّ معلَّق على صفٍّ ناجح أثرٌ يضلّل.
    ("ck_theses_failure_detail_needs_a_failure",
     "failure_detail IS NULL OR failure_code IS NOT NULL"),
    # **و`text_layer_missing` تقول ما تعنيه.** حالٌ تدّعي غياب طبقة النصّ
    # بينما العمود يقول إنها موجودة تناقضٌ يُرفض في القاعدة لا في المراجعة.
    ("ck_theses_missing_text_layer_says_so",
     "processing_state <> 'text_layer_missing' OR text_layer_state = 'absent'"),
    # **وعقدُ OCR لا يُستعمل ليدّعي قراءةً لم تقع.** المسحُ الضوئيّ لا معنى
    # له إلا حيث لا طبقة نصّ؛ فقيمةٌ غير الافتراض على مستندٍ نصُّه مقروء
    # ادّعاءٌ يُرفض بنيويًّا.
    ("ck_theses_ocr_only_when_no_text_layer",
     "ocr_state = 'unavailable' OR text_layer_state = 'absent'"),
)


def upgrade() -> None:
    op.add_column("theses", sa.Column(
        "processing_state", sa.String(24), nullable=False, server_default="uploaded"))
    op.add_column("theses", sa.Column(
        "processing_state_changed_at", TS, nullable=True))
    op.add_column("theses", sa.Column(
        "processing_attempts", sa.Integer, nullable=False, server_default="0"))
    op.add_column("theses", sa.Column("failure_code", sa.String(32), nullable=True))
    op.add_column("theses", sa.Column("failure_detail", sa.Text, nullable=True))
    op.add_column("theses", sa.Column(
        "text_layer_state", sa.String(16), nullable=False, server_default="not_checked"))
    op.add_column("theses", sa.Column(
        "ocr_state", sa.String(16), nullable=False, server_default="unavailable"))
    op.add_column("theses", sa.Column("opportunities_mined_at", TS, nullable=True))

    # ── القيود: SQL صريحٌ بأسماءٍ كاملة (انظر `CHECKS` أعلاه) ──
    for name, expression in CHECKS:
        op.execute(f"ALTER TABLE theses ADD CONSTRAINT {name} CHECK ({expression})")

    # ── الفهرس: صفحةُ القائمة بعبارةٍ واحدة ──
    #
    # الترتيب `(created_at, id)` نازلًا هو مؤشّر الصفحة، و`processing_state`
    # شرطُ التصفية. والـAPI في سنغافورة والقاعدة في مومباي، فكلُّ عبارةٍ
    # رحلةٌ بنحو ٣٣٠ مللي ثانية: **عددُ العبارات هو زمنُ الاستجابة.**
    #
    # **وSQL صريحٌ هنا لا `op.create_index`**: الترتيب النازل جزءٌ من الفهرس
    # لا زينة، و`sa.text("created_at DESC")` داخل قائمة أعمدةٍ يُصيَّر
    # تعبيرًا لا عمودًا مرتَّبًا في بعض الإصدارات. والعبارة تقول ما تعنيه.
    op.execute(
        "CREATE INDEX ix_theses_tenant_state_page ON theses "
        "(tenant_id, processing_state, created_at DESC, id DESC)")
    # وفهرسٌ للصفحة بلا تصفية — وهو الطلب الشائع.
    op.execute(
        "CREATE INDEX ix_theses_tenant_page ON theses "
        "(tenant_id, created_at DESC, id DESC)")


def downgrade() -> None:
    """التنازل يُسقط ما أضافه هذا الترحيل وحده — **ولا يمسّ صفًّا**.

    وهذه أعمدةُ حالٍ تشغيلية يُعاد اشتقاقها بإعادة المعالجة، لا قراراتٌ
    بشرية؛ فلا موجب لرفض التنازل كما في 0025. غير أن سببَ فشلٍ مكتوبًا
    يضيع بذهاب العمود — وذاك ثمنُ التنازل المعلَن، لا أثرٌ جانبيّ صامت.
    """
    op.execute("DROP INDEX IF EXISTS ix_theses_tenant_page")
    op.execute("DROP INDEX IF EXISTS ix_theses_tenant_state_page")

    for name, _expression in CHECKS:
        op.execute(f"ALTER TABLE theses DROP CONSTRAINT IF EXISTS {name}")

    for column in ("opportunities_mined_at", "ocr_state", "text_layer_state",
                   "failure_detail", "failure_code", "processing_attempts",
                   "processing_state_changed_at", "processing_state"):
        op.drop_column("theses", column)
