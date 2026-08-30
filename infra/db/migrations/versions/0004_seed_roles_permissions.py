"""بذر الأدوار والصلاحيات | Seed the nine roles and permission catalog (§28).

الأدوار بيانات لا ثوابت في الكود، وكل اسم بلغتين لأن الواجهة ثنائية اللغة
من الأساس (§26.4).

Revision ID: 0004
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

PERMISSIONS = [
    ("tenant.manage", "إدارة المستأجر", "Manage tenant"),
    ("member.invite", "دعوة الأعضاء", "Invite members"),
    ("member.manage", "إدارة العضويات", "Manage memberships"),
    ("audit.read", "قراءة سجل التدقيق", "Read audit log"),
    ("file.upload", "رفع الملفات", "Upload files"),
    ("file.read", "قراءة الملفات", "Read files"),
    ("file.delete", "حذف الملفات", "Delete files"),
    ("approval.decide", "البت في بوابات الاعتماد", "Decide approval gates"),
    ("project.create", "إنشاء مشروع بحثي", "Create research project"),
    ("project.read", "قراءة المشاريع", "Read projects"),
    ("project.write", "تعديل المشاريع", "Edit projects"),
    ("promotion.read", "قراءة ملف الترقية", "Read promotion case"),
    ("promotion.manage", "إدارة سياسات الترقية", "Manage promotion policies"),
    ("thesis.read", "قراءة الرسائل", "Read theses"),
    ("thesis.mine", "استخراج فرص النشر", "Mine publication opportunities"),
    ("integrity.read", "قراءة تنبيهات النزاهة", "Read integrity alerts"),
]

# الدور → صلاحياته. system_admin يأخذ كل شيء.
ROLE_MATRIX = {
    "researcher": ["file.upload", "file.read", "project.create", "project.read", "project.write",
                   "promotion.read", "thesis.read", "thesis.mine", "approval.decide",
                   "integrity.read"],
    "co_author": ["file.read", "project.read", "project.write"],
    "supervisor": ["file.read", "file.upload", "project.read", "thesis.read", "thesis.mine",
                   "integrity.read"],
    "student": ["file.upload", "file.read", "project.read", "thesis.read"],
    "internal_reviewer": ["project.read", "file.read", "integrity.read"],
    "research_admin": ["member.invite", "member.manage", "audit.read", "project.read",
                       "promotion.read", "integrity.read"],
    "college_admin": ["member.invite", "member.manage", "audit.read", "project.read",
                      "promotion.read", "promotion.manage", "integrity.read"],
    "institution_admin": ["tenant.manage", "member.invite", "member.manage", "audit.read",
                          "promotion.manage", "promotion.read", "project.read", "integrity.read"],
    "system_admin": [key for key, _, _ in PERMISSIONS],
}

ROLE_NAMES = {
    "researcher": ("باحث", "Researcher"),
    "co_author": ("مؤلف مشارك", "Co-author"),
    "supervisor": ("مشرف", "Supervisor"),
    "student": ("طالب دراسات عليا", "Graduate student"),
    "internal_reviewer": ("محكّم داخلي", "Internal reviewer"),
    "research_admin": ("مدير بحثي", "Research admin"),
    "college_admin": ("مدير كلية", "College admin"),
    "institution_admin": ("مدير مؤسسة", "Institution admin"),
    "system_admin": ("مدير النظام", "System admin"),
}

ADMIN_ROLES = {"research_admin", "college_admin", "institution_admin", "system_admin"}


def upgrade() -> None:
    for key, name_ar, name_en in PERMISSIONS:
        op.execute(
            f"""
            INSERT INTO permissions (key, name_ar, name_en)
            VALUES ('{key}', '{name_ar}', '{name_en}')
            ON CONFLICT (key) DO NOTHING
            """
        )

    # دالة تزرع الأدوار لكل مستأجر جديد — يستدعيها trigger عند إنشاء المستأجر،
    # حتى لا يعتمد اكتمال الأدوار على مسار تطبيقي قد يُنسى.
    role_values = ",".join(
        f"('{key}', '{ROLE_NAMES[key][0]}', '{ROLE_NAMES[key][1]}', "
        f"{'true' if key in ADMIN_ROLES else 'false'})"
        for key in ROLE_MATRIX
    )
    matrix_values = ",".join(
        f"('{role}', '{perm}')" for role, perms in ROLE_MATRIX.items() for perm in perms
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION seed_tenant_roles() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO roles (tenant_id, key, name_ar, name_en, is_admin)
            SELECT NEW.id, r.key, r.name_ar, r.name_en, r.is_admin
            FROM (VALUES {role_values}) AS r(key, name_ar, name_en, is_admin)
            ON CONFLICT (tenant_id, key) DO NOTHING;

            INSERT INTO role_permissions (tenant_id, role_id, permission_id)
            SELECT NEW.id, ro.id, p.id
            FROM (VALUES {matrix_values}) AS m(role_key, perm_key)
            JOIN roles ro ON ro.tenant_id = NEW.id AND ro.key = m.role_key
            JOIN permissions p ON p.key = m.perm_key
            ON CONFLICT DO NOTHING;

            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_seed_tenant_roles
            AFTER INSERT ON tenants
            FOR EACH ROW EXECUTE FUNCTION seed_tenant_roles();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_seed_tenant_roles ON tenants")
    op.execute("DROP FUNCTION IF EXISTS seed_tenant_roles()")
    op.execute("DELETE FROM permissions")
