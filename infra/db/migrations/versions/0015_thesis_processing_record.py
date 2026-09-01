"""سجل رسالة قيد المعالجة | System-created thesis record (S5C).

سجلّ تنشئه المنصة عند رفع الرسالة، **قبل** أن تُقرأ. فلا عنوان يُعرف ولا
درجة، والحقلان يصيران قابلين للعدم.

و`NULL` هنا تعني «لم يُستخرَج بعد» — وهي الحقيقة. والبديل كان أسوأ: اسم
الملف عنوانًا للرسالة، أو درجة مخمَّنة بين ماجستير ودكتوراه. وكلاهما اختلاق
تمنعه قاعدة المنتج: المفقود يُعلَن مفقودًا ولا يُملأ.

والقيد يبقى قائمًا وأوسع لا أضيق: `NULL` أو إحدى القيمتين — فلا تتسرّب قيمة
ثالثة من باب الارتخاء.

**والعقد اليدوي لا يرتخي:** `ThesisCreateRequest` يظلّ يشترط العنوان والدرجة.
هذا الترحيل للسجل الذي ينشئه النظام لا للذي يملؤه المستخدم.
"""
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("theses", "title_ar", nullable=True)
    op.alter_column("theses", "degree", nullable=True)

    # الاسم الفعلي في القاعدة `ck_theses_ck_thesis_degree`: اتفاقية التسمية
    # في `Base.metadata` تسبق كل قيد بـ`ck_%(table_name)s_`، وترحيل 0010
    # مرّر لها اسمًا يبدأ بـ`ck_` أصلًا فتضاعفت البادئة.
    #
    # ولذلك يُكتب الاسم صريحًا هنا لا محسوبًا: `op.drop_constraint` يعيد
    # تطبيق الاتفاقية على ما يُمرَّر إليه، فيصير اسمٌ ثالث لا وجود له.
    op.execute("ALTER TABLE theses DROP CONSTRAINT ck_theses_ck_thesis_degree")
    op.execute(
        "ALTER TABLE theses ADD CONSTRAINT ck_theses_ck_thesis_degree "
        "CHECK (degree IS NULL OR degree IN ('masters','phd'))"
    )


def downgrade() -> None:
    """التنازل يعيد الإلزام — **ولا يخترع قيمة ليَنجح**.

    صفٌّ قيد المعالجة بلا عنوان أو درجة يمنع إعادة `NOT NULL`، وPostgreSQL
    يرفض الترحيل صراحةً. وذلك سلوك صحيح لا عيب: ملء العنوان باسم ملف أو
    الدرجة بتخمين لإرضاء تنازلٍ هو بالضبط ما بُني هذا الترحيل ليمنعه.

    فمن أراد التنازل يحسم تلك السجلات أولًا — بمراجعة بشرية أو بحذفها.
    """
    op.execute("ALTER TABLE theses DROP CONSTRAINT ck_theses_ck_thesis_degree")
    op.execute(
        "ALTER TABLE theses ADD CONSTRAINT ck_theses_ck_thesis_degree "
        "CHECK (degree IN ('masters','phd'))"
    )
    op.alter_column("theses", "degree", nullable=False)
    op.alter_column("theses", "title_ar", nullable=False)
