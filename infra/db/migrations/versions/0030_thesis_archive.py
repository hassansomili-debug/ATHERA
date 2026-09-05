"""أرشفةُ الرسالة لا حذفُها | Thesis soft archive (Wave 1.1).

**الإزالة صارت أرشفةً، والحذفُ الفيزيائيّ رُفع من المنتج.**

كان مركز الرسائل بلا مخرج: لا سبيل إلى إزالة رسالةٍ أصلًا. وأوّلُ علاجٍ
كتب `DELETE FROM theses` على رسالةٍ لا تبعات علميّة لها — وذلك خطأ. الصفُّ
أصلُ سلسلةٍ: منه الأقسام والنتائج ومرشّحاتُ الوقائع والفرص واتفاقاتُ
التأليف واعتماداتُ الحقوق، و`ON DELETE CASCADE` قائمٌ على خمسة جداول.
و«لا تبعات **اليوم**» ليست «لن تكون»، والحذفُ لا يُستعاد.

فلا يُحذف شيء. تُوسَم الرسالة بوقت الأرشفة ومَن أرشفها، وتخرج من القائمة
الافتراضية، **ويبقى كلُّ ما تحتها كما هو** — والاسترجاع يمحو الوسم فتعود
كما كانت حرفًا بحرف.

## توسعةٌ محضة — والخادمُ القائم يبقى صحيحًا عليها

بين ترحيل القاعدة ونشر الموجة نافذةٌ يخدم فيها **الخادمُ القديم مخطَّطًا
جديدًا** (الدرس المكتوب في 0028/0029). فالعمودان:

  • **يقبلان `NULL`** ولا `server_default` يكتب فيهما شيئًا،
  • ولا قيدَ يقرنهما بعمودٍ يعرفه الخادمُ القديم،
  • ولا يدخلان في أيّ قيدٍ قائم.

فالخادمُ القائم (مخطَّط 0029، واجهة v88) يُدرج صفوفَ رسائل بلا ذكرهما
فيأخذان `NULL` — ومعناها «غير مؤرشَفة»، وهي الحال الصحيحة لكلّ ما يكتبه.
ويقرأ بقوائم أعمدةٍ صريحة يولّدها SQLAlchemy من نماذجه، فعمودٌ لا يعرفه
لا يصل إليه أصلًا. ولا سطر في تلك الواجهة يُسقط رسالةً ولا يقرأ أرشيفًا،
فلا سلوكَ فيها يتغيّر.

**والقيدُ الوحيد المضاف يصف الوسم نفسه** ولا يمسّ عمودًا قديمًا: أرشفةٌ
بلا وقتٍ أو بلا فاعلٍ ليست أرشفة — والصفوفُ القائمة كلُّها `NULL` في
العمودين، فتحقّقه جميعًا.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

#: **وسمٌ كاملٌ أو غائب.** «أُرشفت ولا يُعرف متى» و«أُرشفت ولا يُعرف بيد مَن»
#: كلاهما سجلٌّ لا يُحاسَب عليه أحد؛ والعمودان يقعان معًا أو لا يقع أيّهما.
ARCHIVE_IS_NAMED = (
    "ck_theses_archive_is_named",
    "(archived_at IS NULL) = (archived_by IS NULL)",
)


def upgrade() -> None:
    op.add_column("theses", sa.Column("archived_at", TS, nullable=True))
    op.add_column("theses", sa.Column("archived_by", PgUUID(as_uuid=True), nullable=True))
    # **ومفتاحٌ أجنبيّ باسمٍ صريح**: اصطلاحُ التسمية يُطبَّق على ما تولّده
    # الواجهة، ومفتاحٌ مضمَّنٌ في `add_column` يخرج باسمٍ لا يعرفه التنازل.
    op.execute(
        "ALTER TABLE theses ADD CONSTRAINT fk_theses_archived_by "
        "FOREIGN KEY (archived_by) REFERENCES users (id) ON DELETE RESTRICT"
    )

    name, expression = ARCHIVE_IS_NAMED
    op.execute(f"ALTER TABLE theses ADD CONSTRAINT {name} CHECK ({expression})")

    # ── فهرسُ القائمة الافتراضية ──
    #
    # القائمة صارت تُصفّي `archived_at IS NULL`، وهو شرطٌ يصدق على الغالبية
    # العظمى من الصفوف. وفهرسٌ جزئيّ بهذا الشرط يبقى صغيرًا ويحمل ترتيبَ
    # الصفحة نفسه `(created_at, id)` نازلًا — فلا تكلّف التصفيةُ الجديدة
    # مسحًا. والقاعدة في مومباي والخادم في سنغافورة: **عددُ العبارات
    # وكلفتُها هما زمنُ الاستجابة.**
    #
    # **وSQL صريحٌ لا `op.create_index`**: الترتيب النازل جزءٌ من الفهرس،
    # و`sa.text("created_at DESC")` داخل قائمة أعمدة يُصيَّر تعبيرًا لا
    # عمودًا مرتَّبًا في بعض الإصدارات (الدرس نفسه في 0027).
    op.execute(
        "CREATE INDEX ix_theses_tenant_live_page ON theses "
        "(tenant_id, created_at DESC, id DESC) WHERE archived_at IS NULL"
    )


def downgrade() -> None:
    """**التنازل يُخرج الرسائل من الأرشيف، ولا يُتلف صفًّا واحدًا.**

    وذهابُ العمود يعيد كلَّ مؤرشَفةٍ إلى القائمة — وذاك ثمنُ التنازل
    المعلَن: قرارُ الباحث بالأرشفة يضيع، ولا يضيع شيءٌ من عمله العلميّ.
    """
    op.execute("DROP INDEX IF EXISTS ix_theses_tenant_live_page")
    op.execute(f"ALTER TABLE theses DROP CONSTRAINT IF EXISTS {ARCHIVE_IS_NAMED[0]}")
    op.execute("ALTER TABLE theses DROP CONSTRAINT IF EXISTS fk_theses_archived_by")
    op.drop_column("theses", "archived_by")
    op.drop_column("theses", "archived_at")
