"""عقدُ الموافقة — الطرفُ المُتعاقِد من نشرٍ متدحرج | the CONTRACT half.

**توسعةٌ ثمّ نشرٌ ثمّ تعاقد.**

الترحيل 0028 توسعةٌ محضة: يضيف الأعمدة والجداول ولا يفرض قيدًا يعجز عنه
الخادمُ القائم. وذلك ضروريّ لأنّ بين ترحيل القاعدة ونشر الموجة نافذةً
يخدم فيها **الخادمُ القديم مخطَّطًا جديدًا**؛ وهو يكتب `consent_recorded_at`
وحده ولا يعرف `consent_method` (`routers/team.py:156`،
`services/thesis/rights.py:190`). فقيدٌ يقرن العمودين في 0028 كان يُسقط كلّ
تسجيل موافقةٍ بـ٥٠٠ في تلك النافذة.

وهذا الملفّ هو الطرفُ الثاني: يُطبَّق **بعد** أن تصير الموجةُ الأولى هي
الكاتبة، فيرمّم ما كُتب في النافذة ثمّ يفرض العقد.

**وقاعدةٌ علميّة تحكم الترميم:** موافقةٌ كُتبت في النافذة لا يُعرف كاتبُها
من الحدث الأصلي. فلا تُوصف «ذاتية» بحال — تلك دعوى أنّ العضو نفسه أقرّ،
ولا دليل عليها. وتبقى `legacy_unverified`: تُقال مجهولةَ الإسناد كما هي،
ولا يُختلق لها `consent_recorded_by` ولا سندٌ مكتوب.
"""
from __future__ import annotations

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

#: القيودُ المؤجَّلة من 0028 — تُفرض هنا بعد الترميم.
DEFERRED = (
    ("project_members", "consent_has_a_method",
     "(consent_recorded_at IS NULL) = (consent_method IS NULL)"),
    ("project_members", "consent_has_a_time",
     "(consent_state IN ('granted', 'declined')) "
     "= (consent_recorded_at IS NOT NULL)"),
    ("authorship_agreements", "consent_has_a_method",
     "(consent_recorded_at IS NULL) = (consent_method IS NULL)"),
)


def upgrade() -> None:
    # ═════════ أ. ترميمُ صفوف النافذة — وحدَها ═════════
    #
    # الشرطُ ضيّقٌ عمدًا: `consent_method IS NULL` مع وقتٍ مكتوب. فما
    # أسندته الموجةُ الأولى (`self` أو `administrative`) لا يُمَسّ، وما لا
    # موافقة فيه لا يُخترع له واحدة.
    op.execute(
        "UPDATE project_members "
        "SET consent_method = 'legacy_unverified', consent_state = 'granted' "
        "WHERE consent_recorded_at IS NOT NULL AND consent_method IS NULL"
    )
    op.execute(
        "UPDATE authorship_agreements "
        "SET consent_method = 'legacy_unverified' "
        "WHERE consent_recorded_at IS NOT NULL AND consent_method IS NULL"
    )
    # **والحالُ الأخرى**: صفٌّ يقول «مُنحت» أو «رُفضت» بلا وقت يخالف
    # `consent_has_a_time`. ولا يُخترع له وقت — يُعاد إلى ما قبل الطلب،
    # فذاك ما تقوله القاعدةُ عنه صدقًا: لا موافقة مسجَّلة.
    op.execute(
        "UPDATE project_members SET consent_state = 'not_requested' "
        "WHERE consent_state IN ('granted', 'declined') "
        "AND consent_recorded_at IS NULL"
    )

    # ═════════ ب. البرهانُ قبل الفرض ═════════
    #
    # **ولا يُفرض قيدٌ على أمل.** لو بقي صفٌّ مخالف لسقط `ALTER TABLE`
    # برسالةٍ تذكر القيد ولا تذكر الصفّ، فيُقرأ الترحيلُ معطوبًا وهو سليم.
    # فيُعدّ المخالفون أوّلًا، ويُقال عددُهم في الخطأ.
    for table, name, expression in DEFERRED:
        op.execute(
            f"DO $$ DECLARE offenders bigint; BEGIN "
            f"SELECT count(*) INTO offenders FROM {table} "
            f"WHERE NOT ({expression}); "
            f"IF offenders > 0 THEN RAISE EXCEPTION "
            f"'ck_{table}_{name}: % row(s) still violate the contract "
            f"after the legacy repair', offenders; END IF; END $$;"
        )

    # ═════════ ج. العقد ═════════
    #
    # وبـSQL صريحٍ بالاسم الكامل: واجهةُ alembic تعيد تطبيق اصطلاح التسمية
    # على اسمٍ طُبّق عليه أصلًا، فتطلب اسمًا لا وجود له (وقع في 0017).
    for table, name, expression in DEFERRED:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_{name} "
            f"CHECK ({expression})"
        )


def downgrade() -> None:
    # **ولا يُعاد الترميم إلى ما كان.** رفعُ القيد يُعيد الشكل، ولا يُعيد
    # `consent_method` إلى العدم: قيمةُ `legacy_unverified` وصفٌ صادقٌ لما
    # في الصفّ، ومحوُها يجعل الصفّ يدّعي أنّه لم يُراجَع قطّ.
    for table, name, _ in DEFERRED:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT ck_{table}_{name}")
