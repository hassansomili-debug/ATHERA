"""طبقة قاعدة البيانات وعزل المستأجرين | Database layer and tenant isolation.

ADR-0002: العزل خاصية قاعدة بيانات لا انضباط مطوّرين. كل جلسة تضبط
`app.tenant_id` داخل المعاملة، وسياسات RLS تتولى الباقي. نسيان الضبط يعني
صفر نتائج (فشل آمن) لا تسريبًا.

Isolation is a database property, not developer discipline. Every session sets
`app.tenant_id` inside the transaction; forgetting it yields zero rows (fail-safe).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from .config import get_settings

_settings = get_settings()

def _connect_args() -> dict:
    """يعطّل ذاكرة العبارات المهيّأة خلف مجمّع بوضع المعاملة.

    مجمّعات مثل PgBouncer/Supabase (المنفذ 6543) تعيد استخدام اتصالات
    الخادم بين المعاملات، بينما يخزّن asyncpg العبارات المهيّأة على الاتصال
    ويسمّيها بأسماء متسلسلة. النتيجة `DuplicatePreparedStatementError`
    تظهر تحت الحمل فقط — أي في الإنتاج لا في الاختبار.

    الكشف من نصّ الرابط: منفذ المجمّع أو مضيف `pooler`. ولو أخطأ الكشف
    فالثمن أداء أقل قليلًا على اتصال مباشر، لا عطب تحت الحمل.

    ويبقى `SET LOCAL` سليمًا في وضع المعاملة: `tenant_session` تفتح معاملة
    صريحة، فالضبط والاستعلام في المعاملة نفسها ولا يتسرب السياق.
    """
    url = _settings.database_url
    if not url.startswith("postgresql+asyncpg"):
        return {}
    behind_pooler = ":6543" in url or "pooler." in url
    if not behind_pooler:
        return {}
    return {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


engine = create_async_engine(
    _settings.database_url,
    pool_pre_ping=True,
    echo=False,
    connect_args=_connect_args(),
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def tenant_session(tenant_id: UUID | None, actor_id: UUID | None = None) -> AsyncIterator[AsyncSession]:
    """جلسة مقيّدة بمستأجر | a session scoped to one tenant.

    `SET LOCAL` يعني أن القيمة تموت مع المعاملة ولا تتسرب إلى الطلب التالي
    عبر اتصال معاد استخدامه من الـpool.
    """
    async with SessionFactory() as session:
        async with session.begin():
            if tenant_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
            if actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.actor_id', :aid, true)"),
                    {"aid": str(actor_id)},
                )
            yield session


@asynccontextmanager
async def system_session() -> AsyncIterator[AsyncSession]:
    """جلسة بلا مستأجر — للتسجيل والمصادقة فقط قبل تحديد السياق.

    لا تمنح تجاوزًا لـRLS: دور التطبيق لا يملك BYPASSRLS. الجداول التي
    تُقرأ هنا (users, tenants) لها سياسات خاصة موصوفة في الترحيل 0002.
    """
    async with SessionFactory() as session:
        async with session.begin():
            yield session
