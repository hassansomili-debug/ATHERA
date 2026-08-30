"""الامتدادات وأدوار قاعدة البيانات | Extensions and database roles.

يثبت هذا الترحيل ثلاثة أشياء لا يمكن إضافتها لاحقًا بلا ألم:
  1. pgvector (§31.3) — مع تراجع نظيف (AT-S0-13).
  2. دور تطبيق بلا BYPASSRLS (ADR-0002).
  3. دالة سياق المستأجر التي تعتمد عليها كل سياسات RLS.

Revision ID: 0001
"""
import os

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _app_password() -> str:
    """كلمة دور التطبيق من البيئة، ولا قيمة افتراضية في الإنتاج.

    كانت مكتوبة في هذا الملف — أي في المستودع. كلمة مرور في git تبقى في
    التاريخ حتى بعد تغييرها، فيصبح تدويرها لاحقًا إخفاءً لا إصلاحًا.

    القيمة الافتراضية تُقبل في `development` وحدها، ويفشل الترحيل بلا
    كلمة في أي بيئة أخرى — الفشل هنا أرخص من قاعدة إنتاج بكلمة معروفة.
    """
    password = os.getenv("ATHERA_DB_APP_PASSWORD", "")
    if password:
        return password
    if os.getenv("APP_ENV", "development") == "development":
        return "athera_app_pw"
    raise RuntimeError(
        "ATHERA_DB_APP_PASSWORD is required outside development: "
        "the application role must not carry a password that lives in the repository."
    )


def upgrade() -> None:
    # على المستضيفات المدارة (Supabase مثلًا) توضع الامتدادات في مخطط
    # `extensions` لا `public`؛ ووجودها مسبقًا هو الحالة الطبيعية هناك.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # لا حاجة إلى pgcrypto: gen_random_uuid() في نواة PostgreSQL منذ 13،
    # والمشروع يستهدف 16 (ADR-0001). كل تبعية امتداد تُسقَط تعني بيئات
    # استضافة أكثر تقبل تشغيل المنصة.

    # دور التطبيق: لا BYPASSRLS، ولا ملكية للجداول. إن وُجد لا نلمس كلمته.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'athera_app') THEN
                CREATE ROLE athera_app LOGIN PASSWORD '{_app_password()}' NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO athera_app")

    # سياق المستأجر: NULL عند غياب الضبط ⇒ السياسات لا تطابق شيئًا ⇒ فشل آمن.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_tenant() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_actor() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.actor_id', true), '')::uuid
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_current_actor()")
    op.execute("DROP FUNCTION IF EXISTS app_current_tenant()")
    op.execute("DROP EXTENSION IF EXISTS vector")
