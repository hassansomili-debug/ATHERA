"""حال دور قاعدة البيانات في زمن التشغيل | runtime database-role posture.

**الحادثة التي أوجدت هذا الملف.** كان عزل المستأجرين مفعَّلًا ومفروضًا على
كل جدول في القاعدة، ومع ذلك قرأ مستأجرٌ بيانات آخر في الإنتاج. السبب لم يكن
سياسةً ناقصة بل **دورًا** يحمل `rolbypassrls = true` في رابط زمن التشغيل:
سطرٌ في سرّ نشرٍ أبطل طبقة أمانٍ كاملة بلا خطأ ولا سجل ولا اختبار أحمر.

فالدرس: ضمانٌ يعتمد على قيمة إعدادٍ صامتة ليس ضمانًا. والقاعدة تعرف عن
نفسها ما لا يعرفه الكود — فتُسأل عند الجهوزية، ويُرفض الإقلاع الصحّي على دور
يتجاوز العزل أو يملك الخارقية.

**ولا يُنشر شيء من هذا للعامة:** اسم الدور يبقى في سجل الخادم، والمستخدم
يرى رمزًا واحدًا لا تفاصيل بنية.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text

# الرمز الداخلي — يُسجَّل ويُختبر، ولا يُفشي بنية قاعدة البيانات.
UNSAFE_REASON = "database_role_unsafe"

# `current_user` لا `session_user`: ما يهمّ هو الدور الفعّال الذي تُقيَّم به
# سياسات RLS، وهو ما قد يُبدَّل بـ`SET ROLE`.
_QUERY = text(
    "SELECT rolname, rolsuper, rolbypassrls "
    "FROM pg_roles WHERE rolname = current_user"
)


@dataclass(frozen=True, slots=True)
class RolePosture:
    """ما تقوله القاعدة عن الدور الذي يتصل بها الآن."""

    role: str
    is_superuser: bool
    bypasses_rls: bool

    @property
    def safe(self) -> bool:
        """آمنٌ يعني: سياسات RLS تنطبق على هذا الاتصال فعلًا."""
        return not (self.is_superuser or self.bypasses_rls)

    def detail(self) -> str:
        """وصفٌ للسجل الداخلي — لا للاستجابة."""
        flags = [name for name, on in (("rolsuper", self.is_superuser),
                                       ("rolbypassrls", self.bypasses_rls)) if on]
        return f"role={self.role} unsafe_flags={','.join(flags) or 'none'}"


async def read(conn) -> RolePosture:
    row = (await conn.execute(_QUERY)).one()
    return RolePosture(role=row.rolname, is_superuser=bool(row.rolsuper),
                       bypasses_rls=bool(row.rolbypassrls))


async def inspect(engine) -> RolePosture:
    """يفتح اتصالًا ويسأل — فيتحقق الاتصال والحال في نداء واحد."""
    async with engine.connect() as conn:
        return await read(conn)


__all__ = ["UNSAFE_REASON", "RolePosture", "inspect", "read"]
