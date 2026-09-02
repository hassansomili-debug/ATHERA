"""تهيئة الاختبارات | Test fixtures.

الاختبارات التي تلمس قاعدة البيانات تتطلب PostgreSQL حيًّا (make dev).
تُتخطى بوضوح عند غيابه بدل أن تفشل بضجيج — لكنها **لا تُعد ناجحة**.
"""
import asyncio
import os
import uuid

import pytest

from tests.db_safety import guard as _guard_test_database


def pytest_configure(config):
    """**قبل أي تجهيزة وقبل أي جمع** — أين تشير قاعدة هذه التشغيلة؟

    الحزمة تكتب صفوفًا حقيقية: مستأجرين ومستخدمين وملفات وأحداث تدقيق. وقد
    جرت مرةً على قاعدة الإنتاج فتركت فيها ١٠٤ مستأجر اختبار. فالسؤال يُسأل
    هنا، والجواب يفشل مغلقًا: تشغيلةٌ لا تثبت أن هدفها قاعدة اختبار تُرفض
    كاملةً — لا تُتخطّى تجهيزةٌ وتمضي البقية.
    """
    try:
        _guard_test_database()
    except RuntimeError as exc:
        raise pytest.UsageError(str(exc)) from exc

# تبعيات قاعدة البيانات اختيارية عند الجمع: الاختبارات الخالصة — منطق علمي
# لا يمس قاعدة بيانات — يجب أن تعمل في بيئة بلا SQLAlchemy مثبَّت. وغيابها
# يُسقط تجهيزات قاعدة البيانات وحدها، ولا يُسقط بقية الحزمة.
try:
    import pytest_asyncio
    from sqlalchemy import text

    DB_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - بيئة تطوير بلا تبعيات قاعدة البيانات
    pytest_asyncio = None
    text = None
    DB_DEPS_AVAILABLE = False

DB_AVAILABLE = DB_DEPS_AVAILABLE and os.getenv("ATHERA_TEST_DB", "1") == "1"

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="requires a live PostgreSQL (run `make dev` then `make migrate`)"
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


if not DB_DEPS_AVAILABLE:
    # تجهيزات وهمية تُسقط أي اختبار يطلب قاعدة بيانات بسبب واضح.
    @pytest.fixture
    def db_ready():
        pytest.skip("database dependencies are not installed")

    @pytest.fixture
    def two_tenants():
        pytest.skip("database dependencies are not installed")


@(pytest_asyncio.fixture if DB_DEPS_AVAILABLE else pytest.fixture)
async def db_ready() -> bool:
    """يتحقق من الاتصال، **ويميّز** تعذّر الوصول عن أي خطأ آخر.

    ابتلاع كل استثناء في «PostgreSQL غير متاحة» يخفي عيوبًا حقيقية خلف تخطٍّ
    مطمئن — وهو ما وقع فعلًا: اختبارات كانت تُتخطى بينما القاعدة تعمل.

    كما يُعاد تهيئة تجمّع الاتصالات لكل اختبار: التجمّع يرتبط بحلقة أحداث،
    ومشاركته بين حلقات مختلفة تُنتج فشلًا متقطعًا لا علاقة له بالمنطق.
    """
    from athera_api.db import engine

    await engine.dispose()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        unreachable = any(
            marker in message
            # «Connect call failed» هي صيغة asyncpg على macOS بلا Docker —
            # وكانت تفوت القائمة فتفشل الحزمة بضجيج بدل أن تُتخطى بوضوح.
            for marker in ("could not connect", "connection refused",
                           "connect call failed", "does not exist",
                           "no such file", "timeout")
        )
        if unreachable:
            pytest.skip(f"PostgreSQL is not reachable: {exc}")
        raise


@(pytest_asyncio.fixture if DB_DEPS_AVAILABLE else pytest.fixture)
async def two_tenants(db_ready):
    """مستأجران حقيقيان لاختبار العزل | two real tenants for isolation tests."""
    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Role, Tenant, User
    from athera_api.security import hash_password
    from sqlalchemy import select

    created = {}
    async with system_session() as session:
        for label in ("a", "b"):
            slug = f"test-{label}-{uuid.uuid4().hex[:8]}"
            tenant = Tenant(slug=slug, name_ar=f"مستأجر {label}", name_en=f"Tenant {label}")
            session.add(tenant)
            await session.flush()

            user = User(
                email=f"{slug}@example.test",
                password_hash=hash_password("correct-horse-battery-staple"),
                full_name_ar=f"باحث {label}",
                full_name_en=f"Researcher {label}",
            )
            session.add(user)
            await session.flush()

            role = (
                await session.execute(
                    select(Role).where(Role.tenant_id == tenant.id, Role.key == "researcher")
                )
            ).scalar_one()
            session.add(Membership(tenant_id=tenant.id, user_id=user.id, role_id=role.id))
            created[label] = {"tenant_id": tenant.id, "user_id": user.id, "email": user.email}
    return created
