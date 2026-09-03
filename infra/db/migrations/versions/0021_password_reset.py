"""استعادة كلمة المرور | Password recovery (PUBRIVA).

**تغييرُ الكلمة لا يفيد من نسيها.** و`/auth/change-password` يشترط الكلمة
الحالية — وهو الصواب — لكنه يترك من فقدها بلا باب. فإمّا مسارُ استعادة
مصمَّم، وإمّا بابٌ خلفيّ إداريّ يُلغي معنى الكلمة نفسها. فيُبنى الأول.

**والرمز لا يُخزَّن.** يُخزَّن تجزئته وحدها، فمن قرأ الجدول لا يملك ما
يُعيد به ضبط كلمة أحد. وهو المبدأ نفسه في `refresh_tokens`.

**والجدول عابرٌ للمستأجرين** كما `users` نفسه. والسبب بنيويّ لا تساهُل:
«نسيتُ كلمتي» يقع **قبل** أي مصادقة، فلا سياق مستأجرٍ حينها يُفلتر به —
ولو رُبط الرمز بمستأجر لتعذّر البحث عنه أصلًا، ولانكسر المسار لمن ينتمي
إلى أكثر من مساحة. فيتبع سياسة الجداول العابرة كما قرّرها الترحيل 0003.

Revision ID: 0021
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

# **مستأجرو المستخدم، بلا سياقٍ مسبق.**
#
# إبطالُ الجلسات بعد إعادة الضبط يحتاج معرفة مستأجري المستخدم — و`memberships`
# مملوك لمستأجر ومحميّ بـRLS. والاستعادة تقع **بلا مصادقة ولا سياق**، فقراءة
# العضويات حينها تعود فارغة، فلا يُبطَل شيء — ويبقى من نسخ رمزًا قادرًا على
# إصدار وصولٍ بعد إعادة الضبط.
#
# وهو العيب نفسه الذي عالجه الترحيل 0018 لمسار الدخول: دالّة ضيّقة
# `SECURITY DEFINER` تُجيب عن سؤالٍ واحد، ثم يُثبَّت السياق وتجري البقية تحت
# RLS كاملةً. ولا يُلتف على العزل — يُسأل عنه بابٌ مُعلَن.
USER_TENANTS = """
CREATE OR REPLACE FUNCTION app_user_tenants(p_user_id uuid)
RETURNS SETOF uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT DISTINCT tenant_id FROM memberships WHERE user_id = p_user_id
$$;
"""


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # **تجزئة الرمز وحدها.** ولا عمود للرمز الخام — فلا يوجد موضعٌ يمكن
        # أن يُكتب فيه سهوًا.
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("consumed_at", TS, nullable=True),
        # يُبطَل دون استهلاك حين يُطلب رمزٌ جديد، أو بعد إعادة ضبطٍ ناجحة.
        sa.Column("invalidated_at", TS, nullable=True),
        # **صلاحية قصيرة تُفرض في القاعدة لا في الشيفرة وحدها.**
        sa.CheckConstraint("expires_at > created_at",
                           name="ck_password_reset_expiry_after_creation"),
        # ولا يكون الرمز مستهلَكًا ومُبطَلًا معًا: حالان متنافيتان.
        sa.CheckConstraint("consumed_at IS NULL OR invalidated_at IS NULL",
                           name="ck_password_reset_single_terminal_state"),
    )
    # البحث يقع بالتجزئة وحدها — والفهرس الفريد أعلاه يكفيه.
    op.create_index("ix_password_reset_user_live", "password_reset_tokens",
                    ["user_id", "expires_at"])

    # جدولٌ عابر: يُقرأ ويُكتب بلا سياق مستأجر، كما `users` و`tenants`
    # (سياسة الترحيل 0003 للجداول العابرة).
    op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY global_readwrite ON password_reset_tokens "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON password_reset_tokens TO athera_app"
    )

    op.execute(USER_TENANTS)
    # `public` يُنزع صراحةً: الدالّة تتجاوز RLS بحكم تعريفها، فلا تُترك
    # مفتوحةً لكل دور.
    op.execute("REVOKE ALL ON FUNCTION app_user_tenants(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_user_tenants(uuid) TO athera_app")


def downgrade() -> None:
    """التنازل يرفض إن كان في الجدول رمزٌ حيّ.

    فحذفُه حينئذٍ يُبطل استعادةً جاريةً بلا أن يعلم صاحبها، ويتركه أمام
    رابطٍ يقول «انتهت صلاحيته» وهو لم تنتهِ.
    """
    live = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM password_reset_tokens "
        "WHERE consumed_at IS NULL AND invalidated_at IS NULL AND expires_at > now()"
    )).scalar_one()
    if live:
        raise RuntimeError(
            f"downgrade refused: {live} live password-reset token(s) would be destroyed, "
            "stranding a recovery already in progress. | "
            f"التنازل مرفوض: {live} رمز استعادة حيّ."
        )
    op.execute("DROP FUNCTION IF EXISTS app_user_tenants(uuid)")
    op.drop_index("ix_password_reset_user_live", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
