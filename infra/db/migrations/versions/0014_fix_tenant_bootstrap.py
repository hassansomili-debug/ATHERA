"""إصلاح إقلاع المستأجر | Fix tenant bootstrap under RLS.

**عيب وجده أول تشغيل على قاعدة حقيقية.**

`trg_seed_tenant_roles` (ترحيل 0004) يزرع الأدوار التسعة عند إنشاء مستأجر.
لكن `roles` و`role_permissions` عليهما RLS بـ`WITH CHECK (tenant_id =
app_current_tenant())` من ترحيل 0003 — وعند إنشاء المستأجر لا سياق بعد،
فـ`app_current_tenant()` تساوي NULL ويُرفض الإدراج.

الأثر: **تسجيل مستخدم جديد يفشل كليًا** — لا الأدوار تُزرع، ولا العضوية
ولا حدث التدقيق يمكن كتابتهما بعدها، لأنها كلها خاضعة للسياق نفسه.

الإصلاح: المشغّل يثبّت سياق المستأجر الجديد لبقية المعاملة قبل الزرع.
هذا ليس التفافًا على العزل بل إتمامه: المعاملة التي تنشئ المستأجر هي
معاملته، فالسياق الصحيح فيها هو هو. و`set_config(..., true)` محلي
بالمعاملة فلا يتسرب إلى طلب لاحق عبر اتصال معاد استخدامه.

Revision ID: 0014
"""
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

ROLE_VALUES_SQL = """
            INSERT INTO roles (tenant_id, key, name_ar, name_en, is_admin)
            SELECT NEW.id, r.key, r.name_ar, r.name_en, r.is_admin
            FROM (VALUES
                ('researcher', 'باحث', 'Researcher', false),
                ('co_author', 'مؤلف مشارك', 'Co-author', false),
                ('supervisor', 'مشرف', 'Supervisor', false),
                ('student', 'طالب دراسات عليا', 'Graduate student', false),
                ('internal_reviewer', 'محكّم داخلي', 'Internal reviewer', false),
                ('research_admin', 'مدير بحثي', 'Research admin', true),
                ('college_admin', 'مدير كلية', 'College admin', true),
                ('institution_admin', 'مدير مؤسسة', 'Institution admin', true),
                ('system_admin', 'مدير النظام', 'System admin', true)
            ) AS r(key, name_ar, name_en, is_admin)
            ON CONFLICT (tenant_id, key) DO NOTHING;
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION seed_tenant_roles() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            -- يثبّت سياق المستأجر الجديد لبقية المعاملة، فتمر سياسات RLS على
            -- الأدوار والصلاحيات والعضوية وسجل التدقيق. محلي بالمعاملة.
            PERFORM set_config('app.tenant_id', NEW.id::text, true);
            {ROLE_VALUES_SQL}
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT NEW.id, ro.id, p.id
            FROM roles ro
            JOIN LATERAL (
                SELECT unnest(CASE ro.key
                    WHEN 'researcher' THEN ARRAY['file.upload','file.read','project.create',
                        'project.read','project.write','promotion.read','thesis.read',
                        'thesis.mine','approval.decide','integrity.read']
                    WHEN 'co_author' THEN ARRAY['file.read','project.read','project.write']
                    WHEN 'supervisor' THEN ARRAY['file.read','file.upload','project.read',
                        'thesis.read','thesis.mine','integrity.read']
                    WHEN 'student' THEN ARRAY['file.upload','file.read','project.read',
                        'thesis.read']
                    WHEN 'internal_reviewer' THEN ARRAY['project.read','file.read',
                        'integrity.read']
                    WHEN 'research_admin' THEN ARRAY['member.invite','member.manage',
                        'audit.read','project.read','promotion.read','integrity.read']
                    WHEN 'college_admin' THEN ARRAY['member.invite','member.manage',
                        'audit.read','project.read','promotion.read','promotion.manage',
                        'integrity.read']
                    WHEN 'institution_admin' THEN ARRAY['tenant.manage','member.invite',
                        'member.manage','audit.read','promotion.manage','promotion.read',
                        'project.read','integrity.read']
                    WHEN 'system_admin' THEN ARRAY[]::text[]
                    ELSE ARRAY[]::text[]
                END) AS perm_key
            ) AS m ON true
            JOIN permissions p ON p.key = m.perm_key
            WHERE ro.tenant_id = NEW.id
            ON CONFLICT DO NOTHING;

            -- مدير النظام يأخذ كل الصلاحيات المعرَّفة.
            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT NEW.id, ro.id, p.id
            FROM roles ro CROSS JOIN permissions p
            WHERE ro.tenant_id = NEW.id AND ro.key = 'system_admin'
            ON CONFLICT DO NOTHING;

            RETURN NEW;
        END
        $$;
        """
    )


def downgrade() -> None:
    # يعيد النسخة السابقة بلا ضبط السياق — وهي المعطوبة تحت RLS، لكنها
    # الحالة التي كان عليها الترحيل 0004 فعلًا.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION seed_tenant_roles() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            {ROLE_VALUES_SQL}
            RETURN NEW;
        END
        $$;
        """
    )
