"""مجلدات المكتبة | Library folders (PUBRIVA — My Library V2).

**المكتبة كانت قائمةً واحدة لا تنتهي.** كل ما رفعه الباحث في صفٍّ واحد،
مرتَّبًا بتاريخ الرفع وحده. ومن رفع ثلاثين كتابًا ومئة ورقة لا يجد كتاب
المنهج بينها إلا بأن يقرأ الأسماء واحدًا واحدًا — فالمكتبة تكبر فتزداد
عجزًا عن أداء وظيفتها الأولى: أن يجد الباحث ما وضعه فيها.

**والمجلَّد تنظيمٌ لا حالُ دليل.** هذا هو الحدّ الذي تقوم عليه هذه الإضافة
كلها: انتقالُ ملفٍّ من مجلَّد إلى مجلَّد يغيّر `folder_id` **ولا شيء غيره**.
لا يمسّ ربطَه ببحث، ولا حالَ استعمال مصدره، ولا اعتمادَ مرشّحٍ استُخرج منه،
ولا سلسلةَ الإسناد، ولا استشهادًا في ورقة. فمن نظّم مكتبته لا يجوز أن يجد
ورقته وقد فقدت سندها لأنه حرّك ملفًّا بين مجلَّدين.

**ولا يُنقل مفتاح التخزين أبدًا.** `storage_key` يُبنى مرّة عند الرفع
ويبقى؛ فالروابط الموقّعة تشير إليه، وسجلّ `provenance` يذكره موضعًا للأصل.
ونقلُ الكائن في المخزن مع كل تغيير مجلَّد يكسر الاثنين — وليس فيه فائدة
أصلًا: المجلَّد صفٌّ في القاعدة، لا مسارٌ في نظام ملفات.

**والحذف تأجيل.** «حذف» في الشاشة نقلٌ إلى سلّة (`trashed_at`)، والإتلاف
قرارٌ ثانٍ مستقل — وهي فلسفة المنصّة نفسها في الترحيل 0020 للبحوث.
والحاذفُ يُسمّى: `trashed_at` بلا `trashed_by` حذفٌ بلا صاحب، يرفضه القيد.

Revision ID: 0022
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = ("library_folders",)


def upgrade() -> None:
    # ── 1. المجلَّد: شجرةٌ في جدولٍ واحد ──
    op.create_table(
        "library_folders",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        # **الجذر هو `NULL`.** ولا صفَّ وهميّ اسمه «مكتبتي» يُنشأ لكل مستأجر:
        # صفٌّ كهذا يحتاج بذرةً في الترحيل وحارسًا يمنع حذفه وإعادةَ تسميته،
        # ثم يصير أول ما يُنسى في مستأجرٍ أُنشئ بعده. والغياب أصدق من صفٍّ
        # يدّعي ما ليس شيئًا.
        sa.Column("parent_folder_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("library_folders.id", ondelete="RESTRICT"),
                  nullable=True),
        # **المُنشئ يُسمّى كما يُسمّى رافعُ الملف** (`files.uploaded_by`):
        # نمطُ الملكية في المنصّة صفٌّ يذكر صاحبه ومنحةُ كائن في
        # `object_grants` — ولا يُخترع نموذج ملكيةٍ ثانٍ لأجل المجلَّدات.
        sa.Column("created_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("trashed_at", TS, nullable=True),
        sa.Column("trashed_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        # مجلَّدٌ بلا اسم لا يُميَّز عن غيره في قائمة — والفراغ ليس اسمًا.
        sa.CheckConstraint("length(btrim(name)) > 0",
                           name="ck_library_folders_name_not_empty"),
        # **أقصر دورة تُمنع في القاعدة.** فحصُ الدورات الأطول يقع في الكود
        # داخل معاملةٍ واحدة، وهذه تُمنع هنا فلا تعتمد على شيء.
        sa.CheckConstraint("parent_folder_id IS NULL OR parent_folder_id <> id",
                           name="ck_library_folders_not_own_parent"),
        sa.CheckConstraint("trashed_at IS NULL OR trashed_by IS NOT NULL",
                           name="ck_library_folders_trash_actor"),
    )
    # قراءةُ الشاشة الواحدة: أبناء مجلَّدٍ بعينه، القائمُ منهم وحده.
    op.create_index("ix_library_folders_parent", "library_folders",
                    ["tenant_id", "parent_folder_id", "trashed_at"])
    # وسلّة المهملات قائمةٌ ثانية، صغيرةٌ عادةً — فهرسٌ جزئيّ يكفيها.
    op.create_index("ix_library_folders_trashed", "library_folders",
                    ["tenant_id", "trashed_at"],
                    postgresql_where=sa.text("trashed_at IS NOT NULL"))

    # ── 2. الملف يعرف مجلَّده — والجذر `NULL` ──
    #
    # **عمودٌ لا جدول ربط.** والفرق مقصود: المصدر قد يخدم بحثين فحالُ
    # استعماله تخصّ العلاقة (الترحيل 0020)، أمّا موضعُ الملف في مكتبة صاحبه
    # فواحد — كما لا يكون الكتاب على رفَّين في آنٍ واحد. وجدولُ ربطٍ هنا
    # يسمح بحالٍ لا معنى لها ثم يحتاج حارسًا يمنعها.
    op.add_column("files", sa.Column("folder_id", PgUUID(as_uuid=True),
                                     sa.ForeignKey("library_folders.id",
                                                   ondelete="RESTRICT"),
                                     nullable=True))
    op.add_column("files", sa.Column("trashed_at", TS, nullable=True))
    op.add_column("files", sa.Column(
        "trashed_by", PgUUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True))
    op.create_check_constraint(
        "trash_actor", "files", "trashed_at IS NULL OR trashed_by IS NOT NULL")

    # **الفهرس يخدم الترقيم المفتاحيّ كما هو.** الصفحة تُقرأ
    # `WHERE tenant_id = ? AND folder_id [IS NULL | = ?] AND trashed_at IS NULL`
    # ثم `ORDER BY created_at DESC, id DESC`. وbtree يُمسح عكسًا بلا كلفة،
    # فالترتيب الصاعد في الفهرس يخدم النزول في الاستعلام.
    op.create_index("ix_files_folder_page", "files",
                    ["tenant_id", "folder_id", "created_at", "id"],
                    postgresql_where=sa.text("trashed_at IS NULL"))
    op.create_index("ix_files_trashed", "files", ["tenant_id", "trashed_at"],
                    postgresql_where=sa.text("trashed_at IS NOT NULL"))

    # ── 3. العزل: مفعَّل **ومفروض**، ومنحُ الدور صريح ──
    #
    # `FORCE` ليست تكرارًا لـ`ENABLE`: بدونها يتجاوز مالكُ الجدول سياساته،
    # فتصير الحماية معتمدةً على أيّ دورٍ فتح الاتصال. وهي قاعدة ADR-0002،
    # تُطبَّق على كل جدولٍ جديد بلا استثناء لجدولٍ «تنظيميّ».
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
    """التنازل يرفض ما دام في السلّة شيءٌ ينتظر قرارًا.

    إسقاطُ `trashed_at` يجعل كل ملفٍّ ومجلَّدٍ حذفه الباحث يعود حيًّا فجأة
    في مكتبته، بلا أن يُقال له شيء — وهو العيب نفسه الذي منعه الترحيل 0020
    في بحوث السلّة. فيُطلب القرار أولًا: استعادةٌ أو إتلافٌ مقصود.

    **وما يُفقد بالتنازل تنظيمٌ لا دليل.** شجرة المجلَّدات تذهب، وتعود
    الملفات إلى قائمةٍ واحدة كما كانت — ولا يمسّ ذلك ربطًا ببحث، ولا حالَ
    مصدر، ولا مرشّحًا معتمَدًا، ولا استشهادًا. لأن المجلَّد لم يكن يومًا
    حالَ دليل.
    """
    bind = op.get_bind()

    for table, label_ar in (("files", "ملفًّا"), ("library_folders", "مجلَّدًا")):
        waiting = bind.execute(sa.text(
            f"SELECT count(*) FROM {table} WHERE trashed_at IS NOT NULL"
        )).scalar_one()
        if waiting:
            raise RuntimeError(
                f"downgrade refused: {waiting} row(s) in {table} sit in the trash "
                "awaiting a decision; dropping the column would resurrect them "
                "silently. Restore or delete them deliberately first. | "
                f"التنازل مرفوض: {waiting} {label_ar} في السلّة ينتظر قرارًا."
            )

    op.drop_index("ix_files_trashed", table_name="files")
    op.drop_index("ix_files_folder_page", table_name="files")
    op.execute("ALTER TABLE files DROP CONSTRAINT ck_files_trash_actor")
    for column in ("trashed_by", "trashed_at", "folder_id"):
        op.drop_column("files", column)

    op.drop_index("ix_library_folders_trashed", table_name="library_folders")
    op.drop_index("ix_library_folders_parent", table_name="library_folders")
    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("library_folders")
