"""تهيئة الاختبارات | Test fixtures.

الاختبارات التي تلمس قاعدة البيانات تتطلب PostgreSQL حيًّا (make dev).
تُتخطى بوضوح عند غيابه بدل أن تفشل بضجيج — لكنها **لا تُعد ناجحة**.
"""
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

# ── `pytest_asyncio` تبعيةٌ قاطعة، و SQLAlchemy وحدها الاختيارية ──
#
# **وكان الاستيرادان مقرونين في `try` واحدة** — وهما سؤالان مختلفان. فبيئةٌ
# فيها المكوّنُ ولا SQLAlchemy فيها كانت تُسقط `pytest_asyncio = None`،
# فيصير المكوّنُ الحاضرُ غائبًا، وأيُّ مُزخرِفٍ يسأله بعدها يرفع
# `NameError: name 'pytest_asyncio' is not defined`.
#
# والمكوّنُ لازمٌ على كلِّ حال: `asyncio_mode = "auto"` في `pyproject.toml`
# لا معنى له بدونه، وهو مُعلَنٌ في `dev`. فيُستورَد صريحًا في الرأس.
import pytest_asyncio  # noqa: E402 — بعد الحارس عمدًا: لا شيء قبل فحص الهدف

# تبعيات قاعدة البيانات اختيارية عند الجمع: الاختبارات الخالصة — منطق علمي
# لا يمس قاعدة بيانات — يجب أن تعمل في بيئة بلا SQLAlchemy مثبَّت. وغيابها
# يُسقط تجهيزات قاعدة البيانات وحدها، ولا يُسقط بقية الحزمة.
#
# **والمُشغِّل من التبعيات، لا SQLAlchemy وحدها.** تجهيزةُ الربط تبني
# محرّكًا عند بدء الجلسة، و`create_async_engine` على رابط `+asyncpg` تطلب
# `asyncpg` عندها لا عند الاتصال. فبيئةٌ فيها SQLAlchemy بلا مُشغِّل كانت
# ستُسقط الحزمةَ كلَّها — بما فيها الاختباراتُ الخالصة التي لا تلمس قاعدة.
try:
    import asyncpg  # noqa: F401 — يُسأل عن وجوده لا عن استعماله
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlalchemy.pool import NullPool

    DB_DEPS_AVAILABLE = True
except ImportError:  # pragma: no cover - بيئة تطوير بلا تبعيات قاعدة البيانات
    text = None
    AsyncSession = async_sessionmaker = create_async_engine = None
    NullPool = None
    DB_DEPS_AVAILABLE = False

DB_AVAILABLE = DB_DEPS_AVAILABLE and os.getenv("ATHERA_TEST_DB", "1") == "1"

requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="requires a live PostgreSQL (run `make dev` then `make migrate`)"
)


# ── ولا حلقةَ أحداثٍ تُبنى باليد هنا ──
#
# **كانت `event_loop` تجهيزةً ميّتة تبدو حيّة.** أزال pytest-asyncio تلك
# التجهيزةَ في 1.0 (أُنذر بها في 0.23)، والمدى `>=0.24` بلا سقفٍ سمح
# للرئيسيّ الجديد بالدخول في CI. فبقيت الدالّةُ في الملفّ ولا أحدَ يسألها:
# تُجمع تجهيزةً عادية، ولا تُصبح حلقةَ الاختبارات.
#
# فجرى كلُّ اختبارٍ لا-متزامنٍ على حلقةٍ خاصّةٍ به (`function` هو الافتراض)،
# والمحرّكُ في `athera_api.db` واحدٌ عامٌّ بمجمَّعٍ يحتفظ باتصالات asyncpg
# مربوطةً بالحلقة التي أنشأتها. فاتصالٌ يُنشأ في حلقةِ اختبارٍ ويُعاد
# استعمالُه أو يُغلق في حلقةِ آخر — وهو نصُّ العطب:
# «got Future attached to a different loop».
#
# والنطاقُ يُعلَن الآن في `pyproject.toml` (`asyncio_default_*_loop_scope`)
# بالواجهة المدعومة، فتشترك التجهيزاتُ والاختبارات في حلقةٍ واحدة.

# ═════════════ محرّكُ الاختبارات: مملوكٌ للحزمة، لا المحرّكُ العامّ ═════════════
#
# **والمحرّكُ العامّ ملكُ التطبيق لا ملكُ الاختبارات.** `athera_api.db` ينشئ
# `AsyncEngine` واحدًا عند الاستيراد بمجمَّعٍ حقيقيّ
# (`AsyncAdaptedQueuePool`)، يحتفظ باتصالات asyncpg حيّةً بين الاختبارات.
# وكلُّ اتصالٍ مربوطٌ بحلقة الأحداث التي أنشأته، فكانت الحزمةُ تتصرّف
# بمِلكٍ ليس لها: تتخلّص من مجمَّعه قبل كلِّ اختبار (`engine.dispose()`) كي
# لا يعبُر اتصالٌ بين حلقتين — عِلاجُ عَرَضٍ يُخفي السبب ويُبطئ الحزمة.
#
# فللاختبارات محرّكُها: **`NullPool`، فلا اتصالَ يعيش بين اختبارين أصلًا**،
# ولا شيءَ يعبُر بين الحلقات ولو تغيّر النطاقُ يومًا. ويُهيَّأ مرّةً،
# ويُتخلَّص منه مرّةً عند نهاية الجلسة — لا قبل كلِّ اختبار.
#
# **ولا يُنسخ ضبطُ الإنتاج نسخًا.** `pool_pre_ping` لا معنى له بلا مجمَّع.
# و`connect_args` تُقرأ من `db._connect_args()` نفسِها لا من نسخةٍ ثانية:
# هي تعطّل ذاكرةَ العبارات المهيّأة **خلف مجمّع معاملات** (منفذ 6543 أو
# مضيف `pooler`)، وهدفُ الاختبار محلّيٌّ يفرضه `db_safety`، فتعيد `{}`
# من نفسها. فيبقى السلوكُ صحيحًا في الحالتين بمصدرٍ واحد.


if DB_DEPS_AVAILABLE:

    @pytest_asyncio.fixture(scope="session")
    async def test_engine():
        """محرّكُ الحزمة — بلا مجمَّع، ويُتخلَّص منه مرّةً واحدة."""
        from athera_api.config import get_settings
        from athera_api.db import _connect_args

        engine = create_async_engine(
            get_settings().database_url,
            poolclass=NullPool,
            echo=False,
            connect_args=_connect_args(),
        )
        try:
            yield engine
        finally:
            await engine.dispose()

    @pytest_asyncio.fixture(scope="session", autouse=True)
    async def _bind_application_to_test_engine(test_engine):
        """**والتطبيقُ كلُّه على محرّك الاختبار، لا نصفُه.**

        فحصٌ يُحوّل `db_ready` وحدها يترك كلَّ ما يمرّ على الـAPI على
        المحرّك العامّ: `get_session` تنادي `tenant_session`، وهي —
        و`system_session` معها — تقرأ `SessionFactory` **من فضاء الوحدة
        عند النداء**. فربطُ ذلك الاسم يُحوّل كلَّ مسارٍ دفعةً واحدة: كلّ
        موجّه، وكلّ تجهيزة، وكلّ خدمة.
        ‏
        وهو النمطُ القائم في الحزمة نفسها: `bypassing_rls` في فحوص P0
        تُبدّل `SessionFactory` وتُعيدها. فيُتبع هنا ولا يُخترع غيرُه.
        ‏
        و`autouse` بنطاق الجلسة: يقع الربطُ مرّةً قبل أوّل اختبار، ويُفكّ
        مرّةً بعد آخره — فلا يبقى اختبارٌ واحدٌ خارج الربط سهوًا.
        """
        from athera_api import db

        original_engine = db.engine
        original_factory = db.SessionFactory
        db.engine = test_engine
        db.SessionFactory = async_sessionmaker(
            test_engine, expire_on_commit=False, class_=AsyncSession)
        try:
            yield
        finally:
            db.engine = original_engine
            db.SessionFactory = original_factory
            # محرّكُ التطبيق لم يُستعمل في هذه التشغيلة، والتخلّصُ منه
            # إغلاقٌ لما لم يُفتح — يُقال صراحةً ولا يُترك معلَّقًا.
            await original_engine.dispose()


if not DB_DEPS_AVAILABLE:
    # تجهيزات وهمية تُسقط أي اختبار يطلب قاعدة بيانات بسبب واضح.
    @pytest.fixture
    def test_engine():
        pytest.skip("database dependencies are not installed")

    @pytest.fixture
    def db_ready():
        pytest.skip("database dependencies are not installed")

    @pytest.fixture
    def two_tenants():
        pytest.skip("database dependencies are not installed")


@(pytest_asyncio.fixture if DB_DEPS_AVAILABLE else pytest.fixture)
async def db_ready(test_engine) -> bool:
    """يتحقق من الاتصال، **ويميّز** تعذّر الوصول عن أي خطأ آخر.

    ابتلاع كل استثناء في «PostgreSQL غير متاحة» يخفي عيوبًا حقيقية خلف تخطٍّ
    مطمئن — وهو ما وقع فعلًا: اختبارات كانت تُتخطى بينما القاعدة تعمل.

    **ولا `dispose()` هنا بعد اليوم.** كان يُتخلَّص من مجمَّع المحرّك العامّ
    قبل كلِّ اختبار كي لا يعبُر اتصالٌ بين حلقتين — وذلك عِلاجُ عَرَض:
    الحزمةُ تتصرّف بمِلك التطبيق، وتدفع ثمنَ اتصالٍ جديدٍ في كلِّ اختبار،
    ويبقى السببُ قائمًا. والمحرّكُ الآن للاختبارات وبلا مجمَّع، فلا اتصالَ
    يعيش بين اختبارين أصلًا.

    **وقائمةُ «غير متاح» تضيق ولا تتّسع** (البند ١١): ما ليس تعذُّرَ وصولٍ
    صريحًا يُرفع خطأً ولا يُبتلع في تخطٍّ مطمئن. وأخطاءُ الحلقات
    (`attached to a different loop`) عطبٌ حقيقيّ — تُرفع، ولا تُخفى.
    """
    try:
        async with test_engine.connect() as conn:
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


async def seed_file(session, *, tenant_id, uploaded_by, name="رسالة.pdf"):
    """صفُّ ملفٍّ حقيقيّ، ويُعاد معرّفُه | a real `files` row; returns its id.

    **ومعرّفٌ مُختلَقٌ ليس صفًّا.** كانت تجهيزاتٌ تمرّر `uuid.uuid4()` حيث
    ينتظر العمودُ مفتاحًا أجنبيًّا (`fk_researcher_memories_source_file_id`،
    `fk_theses_file_id`)، فتمرّ على جهازٍ بلا قاعدة ويرفضها الإدراجُ في CI.
    فمن يحتاج ملفًّا يطلب ملفًّا.
    """
    from athera_api.models.files import File

    row = File(tenant_id=tenant_id, storage_key=f"tenants/{tenant_id}/{uuid.uuid4()}",
               original_filename=name, content_type="application/pdf",
               size_bytes=2048, classification="C2", status="stored",
               uploaded_by=uploaded_by)
    session.add(row)
    await session.flush()
    return row.id
