"""حالُ التنقيب حقيقةٌ مستقلّة | Mining has its own truthful state (P0-T1).

**العطب الذي يمنعه هذا الترحيل قبل أن يقع.**

التنقيب صار يبدأ تلقائيًّا عند اكتمال الاستخراج. ولا موضعَ في المخطَّط
يصف حالَه: `theses.opportunities_mined_at` ختمٌ زمنيّ يقول «وقع فحصٌ» ولا
يقول «يجري الآن» ولا «حُجب» ولا «فشل».

وبلا هذا العمود يبقى مخرجٌ واحد لتسجيل فشلِ تنقيب: كتابتُه في حالِ
الاستخراج — `extract_failed`. **وذلك يمحو عملًا نجح فعلًا.** الاستخراجُ
تمّ، والمرشّحاتُ مكتوبةٌ ومؤصَّلة، والباحثُ يقدر على مراجعتها. فإعلانُ
الرسالةِ «فشل استخراجُها» لأنّ خطوةً تاليةً تعثّرت كذبٌ على الباحث في
سجلّه، ويقود إلى إعادة استخراجٍ لا داعي لها.

فحدُّ الفشل مرسومٌ في المخطَّط: للاستخراج حالُه، وللتنقيب حالُه، ولا يكتب
أحدُهما في خانة الآخر.

## توسعةٌ محضة — والخادمُ القائم يبقى صحيحًا عليها

  • `mining_state` غيرُ فارغٍ بقيمةٍ افتراضية في القاعدة: صفوفٌ يكتبها
    خادمٌ لا يعرف العمود تأخذ `not_started` — وهي حالُها الصحيحة.
  • `mining_last_error` يقبل `NULL`، ولا `server_default` له.
  • ولا قيدَ يقرن أيًّا منهما بعمودٍ يعرفه الخادمُ القديم.

فالخادمُ المنشور (مخطَّط 0030) يُدرج ويقرأ بقوائم أعمدةٍ صريحة يولّدها
SQLAlchemy من نماذجه، فعمودٌ لا يعرفه لا يصل إليه أصلًا.

**ولا نصَّ مستندٍ في `mining_last_error`** — رمزُ سببٍ قصير، لا محتوى رسالة.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

#: الحالاتُ الخمس — وكلُّها تصف التنقيب وحده.
STATES = ("not_started", "running", "completed", "withheld", "failed")
CHECK = "ck_theses_mining_state_is_known"


def upgrade() -> None:
    op.add_column(
        "theses",
        sa.Column("mining_state", sa.String(16), nullable=False,
                  server_default="not_started"),
    )
    op.add_column("theses", sa.Column("mining_last_error", sa.String(64), nullable=True))
    op.create_check_constraint(
        CHECK, "theses",
        "mining_state IN (" + ", ".join(f"'{state}'" for state in STATES) + ")",
    )


def downgrade() -> None:
    # **وحذفُ قيد `check` بـSQL صريح.** اصطلاح التسمية
    # `ck_%(table_name)s_%(constraint_name)s` يُطبَّق عند `op.drop_constraint`
    # ولا يُطبَّق عند الإنشاء، فيُطلب اسمٌ مضاعفٌ لا وجود له وينكسر التراجع
    # — في اللحظة التي يُحتاج إليه فيها بالضبط.
    op.execute(f"ALTER TABLE theses DROP CONSTRAINT IF EXISTS {CHECK}")
    op.drop_column("theses", "mining_last_error")
    op.drop_column("theses", "mining_state")
