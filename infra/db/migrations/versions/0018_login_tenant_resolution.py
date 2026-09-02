"""حلّ سياق المستأجر قبل المصادقة | pre-authentication tenant resolution.

**عيبٌ كشفه احتواء حادثة العزل، لا تغييرُ منتج.**

كان رابط زمن التشغيل في الإنتاج يتصل بدورٍ يحمل `rolbypassrls = true`،
فكانت سياسات RLS معطَّلة فعليًّا على كل استعلام. ولمّا صُحّح الرابط إلى
`athera_app` — وهو الدور المقصود بلا تجاوز — سقط تسجيل الدخول كليًّا.

والسبب أن مسار الهوية يقرأ ويكتب جداول **مملوكة لمستأجر** قبل أن يُعرف
المستأجر: `memberships` و`roles` عند الدخول، و`refresh_tokens` عند التجديد،
وسجل التدقيق بعدهما. وسياستها `tenant_id = app_current_tenant()`، والسياق
وقتها فارغ — فتعود صفر صفوف، ويُقرأ ذلك «بيانات دخول غير صحيحة».

أي أن التجاوز لم يكن يُخفي تسريبًا فحسب؛ كان يُخفي أن التطبيق لا يعمل أصلًا
بدوره المقصود. ولم يظهر ذلك في الاختبارات لأنها تفتح جلساتها بسياق مستأجر
مباشرةً ولا تمرّ بـ`/auth/login` عبر HTTP.

**والعلاج ليس إرخاء سياسة.** سياسةٌ تسمح بالقراءة حين يكون السياق فارغًا
تفشل مفتوحةً: كل مسارٍ نُسي فيه ضبط المستأجر يصير يرى كل شيء — وهو أخطر من
العلّة نفسها. فالمكتوب هنا استثناءان **ضيّقان ومسمّيان**، كلٌّ يجيب عن سؤال
واحد ويعيد **معرّف مستأجر واحد** لا صفًّا ولا محتوى:

    app_login_tenant(user, slug)   → مستأجر هذا المستخدم
    app_refresh_token_tenant(hash) → مستأجر هذا الرمز

ثم يثبّت التطبيق السياق بما عاد، وتجري بقية المعاملة تحت RLS كاملةً. وهو
المبدأ نفسه الذي أقرّه الترحيل 0014 لإقلاع المستأجر: السياق الصحيح يُضبط
حالما يُعرف، ولا يُلتف على العزل.

Revision ID: 0018
"""
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

# `SET search_path` شرطٌ في كل دالة SECURITY DEFINER: بدونه يستطيع مستدعٍ
# ذو صلاحية إنشاء مخطط أن يحقن جدولًا يسبق `public` في المسار.
LOGIN_TENANT = """
CREATE OR REPLACE FUNCTION app_login_tenant(p_user_id uuid, p_tenant_slug text DEFAULT NULL)
RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT m.tenant_id
    FROM memberships m
    JOIN tenants t ON t.id = m.tenant_id
    WHERE m.user_id = p_user_id
      AND (p_tenant_slug IS NULL OR t.slug = p_tenant_slug)
    ORDER BY m.created_at ASC
    LIMIT 1
$$;
"""

REFRESH_TENANT = """
CREATE OR REPLACE FUNCTION app_refresh_token_tenant(p_token_hash text)
RETURNS uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT tenant_id FROM refresh_tokens WHERE token_hash = p_token_hash LIMIT 1
$$;
"""

SIGNATURES = (
    "app_login_tenant(uuid, text)",
    "app_refresh_token_tenant(text)",
)


def upgrade() -> None:
    for body in (LOGIN_TENANT, REFRESH_TENANT):
        op.execute(body)
    for signature in SIGNATURES:
        # لا تُنفَّذ من العامة — دور التطبيق وحده، وهو مصادِقٌ قبلها.
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO athera_app")


def downgrade() -> None:
    for signature in SIGNATURES:
        op.execute(f"DROP FUNCTION IF EXISTS {signature}")
