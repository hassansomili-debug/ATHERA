"""تصنيف هدف قاعدة البيانات | classifying a database target.

**من أين جاء هذا الملف.** الفرق بين قاعدة تطوير وقاعدة إنتاج على جهاز
المطوّر كان **المجلد الذي انطلق منه الأمر**: `Settings` تقرأ `.env` من مجلد
العمل، فمن جذر المستودع يُحمَّل ملفٌ يحمل اعتماد الإنتاج، ومن `apps/api` لا
يوجد ملف فتُستعمل القيم المحلية. فوقعت تشغيلة `pytest` على الإنتاج وتركت فيه
مئة وأربعة مستأجرين اصطناعيين.

فالسؤال «هل هذا الهدف إنتاجي؟» يجب أن يُجاب في مكان واحد، ويُسأل من ثلاثة
مواضع: إقلاع التطبيق، وحارس الاختبارات، وأمر الترحيل الإنتاجي — كلٌّ يريد
الجواب لغرض مختلف، والاثنان الأولان يرفضان «نعم» والثالث يرفض «لا».

ولا يُعاد بناء الجواب في كل موضع: ثلاث نسخ تفترق بأول تعديل، وأول موضع
ينساه يصير ثغرة.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse
from typing import Final

# بصمات استضافة مُدارة — قاعدة الإنتاج على واحدة منها.
MANAGED_HOST_MARKERS: Final = ("supabase.com", "supabase.co", "supabase.in",
                               "pooler.", "rds.amazonaws.com", "neon.tech")

# مضيفات محلية معروفة — التطوير وخدمات docker وCI.
LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "::1", "",
                                "postgres", "db", "athera-postgres"})


@dataclass(frozen=True, slots=True)
class Target:
    """ما يُقال عن هدفٍ بلا إفشاء اعتماده."""

    host: str
    database: str
    username: str

    def describe(self) -> str:
        """للسجل والرسائل — مضيفٌ واسم قاعدة، ولا كلمة ولا مستخدم كامل."""
        return f"{self.host or '(no host)'}/{self.database or '(no db)'}"

    @property
    def managed_marker(self) -> str | None:
        return next((m for m in MANAGED_HOST_MARKERS if m in self.host), None)

    @property
    def is_local(self) -> bool:
        return self.host in LOCAL_HOSTS and self.managed_marker is None

    @property
    def looks_managed(self) -> bool:
        """مُدارٌ يعني: ليس قاعدةً محلية، ولو لم نتعرّف على مزوّده.

        والافتراض عند الجهل «مُدار» لا «محلي» — فيفشل مغلقًا.
        """
        return not self.is_local

    @property
    def carries_project_reference(self) -> bool:
        """`postgres.<project-ref>` هو شكل اسم المستخدم على مجمّع Supabase."""
        return "." in self.username


def parse(url: str) -> Target | None:
    """يفكّك رابط SQLAlchemy أو libpq. و`None` تعني «لم يُفهم»، لا «سليم»."""
    if not url or "://" not in url:
        return None
    scheme, _, rest = url.partition("://")
    parsed = urlparse(f"{scheme.split('+')[0]}://{rest}")
    return Target(
        host=(parsed.hostname or "").lower(),
        database=unquote((parsed.path or "").lstrip("/")).lower(),
        username=unquote(parsed.username or ""),
    )


__all__ = ["LOCAL_HOSTS", "MANAGED_HOST_MARKERS", "Target", "parse"]
