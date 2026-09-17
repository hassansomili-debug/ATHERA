"""RC-T1-H2-A — سجلُّ التكرار: إعادةُ الطلب لا تُكرّر الطفرة.

## الدعوى

`RC-T1-H1` أغلق النجاحَ الكاذب: جوابُ الطفرة الناجح يعني أنّ الإيداع وقع.
ولم يُغلق **الجوابَ الغامض**: أنّ الإيداعَ وقع لا يعني أنّ العميلَ عَلِم.
فينقطع الاتصال، ويُعيد العميلُ الطلبَ نفسَه، **فتقع الطفرةُ مرّتين**.

وقد قِيس ذلك على PostgreSQL حقيقيّة قبل هذه الدفعة: طلبانِ متطابقانِ إلى
`POST /api/v1/workspace/projects` ⇒ `rows=2` و`distinct_ids=2`. بحثان من
نيّةٍ واحدة.

**ولا يُدَّعى «مرّةً واحدةً بالضبط».** ما يُبنى هو **تحمُّلُ إعادةٍ آمنة**،
وهو أضعفُ وأصدق.

## ولمَ جدولٌ لا ذاكرةُ عمليّة

الصحّةُ هنا **قيدُ فرادةٍ في القاعدة**، لا قفلٌ في العمليّة: الخوادمُ عدّة،
وذاكرةُ أحدها لا تعرف طلبًا وصل غيرَه. والقيدُ هو الحَكَم.

## نطاقُ الفرادة — أربعةٌ لا واحد

    (tenant_id, actor_user_id, operation, key_digest)

  • **المستأجر** — مفتاحُ مستأجرٍ لا يصطدم بمفتاح آخر.
  • **الفاعل** — وهذا هو الحدُّ الأمنيّ: الصفُّ يحمل **جسمَ جوابٍ قابلًا
    للإعادة**، فلولا الفاعل لأمكن لمفتاحٍ مُخمَّنٍ أن يُخرج جوابَ مستخدمٍ
    آخر داخل المستأجر نفسِه.
  • **العمليّة** — قالبُ المسار وفعلُه. فالمفتاحُ نفسُه على مسارٍ آخر
    عمليّةٌ أخرى، لا تعارض.
  • **بصمةُ المفتاح** — `sha256` لا المفتاحَ الخام: الخامُ لا يضيف شيئًا،
    ويجعل الجدولَ مخزنًا لنصوصٍ يرسلها العميل.

## والسياسةُ بحدَّين: مستأجرٌ **وفاعل**

وجداولُ المستأجر في هذا المستودع تُعزَل بالمستأجر وحده، وذاك يكفيها لأنّها
بياناتُ بحثٍ يشترك فيها الفريق. **وهذا الجدول يختلف**: صفُّه جوابٌ يُعاد
حرفيًّا لمن يحمل المفتاح. فتُشترط هويّةُ الفاعل أيضًا.

و`app_current_actor()` تُعيد `NULL` بلا ضبط، وكلُّ مقارنةٍ بـ`NULL` تُعطي
`NULL` — فجلسةٌ بلا فاعلٍ **لا ترى صفًّا ولا تكتبه**. الفشلُ آمنٌ بالبناء.

## وما لا يُعتمد عليه

لا `SECURITY DEFINER`، ولا `BYPASSRLS`، ولا دورٌ فائق. و`athera_app` بلا
تجاوزٍ، وحارسُ الإصدار يُعيد التحقّق من ذلك في كلّ نشر.

## والحالاتُ ثلاثٌ، ولا رابعةَ تُضاف لأنّها تبدو مفيدة

    in_progress  — حَجزٌ قائمٌ ونتيجةٌ غيرُ معروفة
    completed    — جوابٌ مخزونٌ يُعاد
    failed       — نهائيّةٌ، والمفتاحُ يبقى قابلًا لإعادةِ محاولةٍ صادقة

**وفي الطور A لا يُودَع `in_progress` أبدًا**: الحجزُ والطفرةُ والجوابُ في
معاملةٍ واحدة، فإمّا `completed` أو لا صفَّ البتّة. والحقلانِ
`lease_expires_at` و`in_progress` موجودانِ لأنّ الطور B — المسارات ذاتُ
الانتظار الخارجيّ — سيحتاجهما، ولا يُضاف عمودٌ في ترحيلٍ ثانٍ لما نعرفه الآن.

Revision ID: 0037
Revises: 0036
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

TABLE = "idempotency_records"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # **والمفاتيحُ الأجنبيّةُ كعُرف المستودع**: مئةٌ وعشرون من مئةٍ
        # وواحدٍ من جداول المستأجر تحملها، و`audit_events` تحمل الاثنين.
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT",
                                name="fk_idempotency_records_tenant_id"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT",
                                name="fk_idempotency_records_actor_user_id"),
        # قالبُ المسار وفعلُه: "POST /api/v1/workspace/projects"
        sa.Column("operation", sa.String(length=200), nullable=False),
        # sha256 بالست عشريّ الصغير — ولا يُخزَّن المفتاحُ الخام.
        sa.Column("key_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.CHAR(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.SmallInteger(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # للطور B وحده — ولا معنى له ما دامت الحالُ ليست `in_progress`.
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('in_progress', 'completed', 'failed')",
            name="ck_idempotency_state"),
    )

    # ══ القيدُ الذي تقوم عليه الصحّة كلُّها ══
    #
    # وهو الحَكَم عند التزامن: الطلبُ الثاني يقف على مُدخَل الفهرس غير
    # المُودَع حتى يُحسم الأوّل، ثمّ يُعيد جوابَه أو يمضي إن رجع الأوّل.
    op.create_index("uq_idempotency_scope", TABLE,
                    ["tenant_id", "actor_user_id", "operation", "key_digest"],
                    unique=True)
    # للتنظيف المحدود، ولا أكثر.
    op.create_index("ix_idempotency_expires", TABLE, ["expires_at"])
    op.create_index("ix_idempotency_records_tenant_id", TABLE, ["tenant_id"])

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    # FORCE يجعل السياسة تنطبق حتى على مالك الجدول — لا باب خلفي.
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_actor_isolation ON {TABLE}
          USING (tenant_id = app_current_tenant()
                 AND actor_user_id = app_current_actor())
          WITH CHECK (tenant_id = app_current_tenant()
                      AND actor_user_id = app_current_actor())
        """
    )


def downgrade() -> None:
    """الهبوطُ بلا فقدِ بيانات مجال.

    وسجلُّ التكرار عابرٌ بالبناء — لا يحمل بحثًا ولا مخطوطةً ولا تحليلًا،
    بل أجوبةً مخزونةً تنتهي صلاحيّتُها خلال يوم. فحذفُه يُرجع المخطَّط إلى
    ٠٠٣٦ تمامًا، ولا شيءَ من المجال يضيع معه. وهذا بعينه ما يجعل إضافته
    آمنة.
    """
    op.execute(f"DROP POLICY IF EXISTS tenant_actor_isolation ON {TABLE}")
    op.drop_index("ix_idempotency_records_tenant_id", table_name=TABLE)
    op.drop_index("ix_idempotency_expires", table_name=TABLE)
    op.drop_index("uq_idempotency_scope", table_name=TABLE)
    op.drop_table(TABLE)
