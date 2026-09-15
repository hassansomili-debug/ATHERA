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

from .errors import Unauthorized
from sqlalchemy.sql import text

from .config import get_settings
from .dbtarget import parse as parse_target

_settings = get_settings()


def _refuse_production_outside_production() -> None:
    """يمنع بيئةً غير إنتاجية من فتح محرّك على قاعدة إنتاج.

    **الحادثة التي أوجدت هذا الفحص:** `pytest` من جذر المستودع حمّل `.env`
    الذي يحمل اعتماد الإنتاج، فكتبت الاختبارات مئة وأربعة مستأجرين اصطناعيين
    في قاعدة حيّة. وحارس الاختبارات وحده لا يكفي: تشغيل الـAPI محليًّا بسياق
    صدفةٍ منسيّ يبلغ القاعدة نفسها.

    والقاعدة بسيطة: **قاعدة الإنتاج للإنتاج وحده.** فإن كان `APP_ENV` غير
    `production` والهدف مُدارًا، يُرفض الإقلاع — ويُذكر السبب بمضيفٍ واسم
    قاعدة، بلا رابط ولا كلمة. والإنتاج يمرّ لأن `APP_ENV=production` معلَن
    في `fly.toml`.
    """
    if _settings.app_env.strip().lower() == "production":
        return
    target = parse_target(_settings.database_url)
    if target is None or not target.looks_managed:
        return
    raise RuntimeError(
        f"refusing to start: APP_ENV={_settings.app_env!r} but DATABASE_URL points at "
        f"a managed database ({target.describe()}). A non-production process must not "
        "open a connection to the production database. Set APP_ENV=production for the "
        "real deployment, or point DATABASE_URL at a local database."
    )


_refuse_production_outside_production()


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
            # **ضبطان في عبارةٍ واحدة — لأن العبارة ثمنُها ذهابٌ وإياب.**
            #
            # قِيس من داخل آلة الإنتاج: عبارةٌ واحدة على اتصالٍ قائم تكلّف
            # ٣٣٠ ميلي ثانية (٣٢٩–٣٣١، بلا تشتّت يُذكر) — لأن الخادم في
            # سنغافورة والقاعدة في `ap-south-1`. ودورةُ الجلسة كاملةً ١٩٧٨
            # ميلي ثانية، وهي ستُّ عبارات: فحصُ الاتصال، وبدءُ المعاملة،
            # وضبطان، والاستعلام، والختم. فالحساب ينطبق تمامًا.
            #
            # فكلُّ عبارةٍ تُحذف تُوفّر ٣٣٠ ميلي ثانية على **كل** طلب مصادق.
            # والضبطان مستقلّان لا يعتمد أحدهما على الآخر، فيُرسلان معًا.
            #
            # و`true` باقية في الاثنين: الضبط محلّي بالمعاملة، فلا يتسرّب
            # سياق مستأجرٍ إلى الطلب التالي عبر اتصالٍ معاد استخدامه. وهذا
            # هو ما يحمي العزل، ولا يُمَسّ من أجل سرعة.
            if tenant_id is not None and actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true),"
                         "       set_config('app.actor_id', :aid, true)"),
                    {"tid": str(tenant_id), "aid": str(actor_id)},
                )
            elif tenant_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
            elif actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.actor_id', :aid, true)"),
                    {"aid": str(actor_id)},
                )
            yield session


# ── جسرُ البحث عبر المؤسسات: مُسنَدُ النطاق ──
#
# «أين يعيش هذا البحث **بالنسبة لهذا الفاعل**؟»
#
# ويُقرأ بحقوق المستدعي تحت سياساتِ «النفس» التي أضافها الترحيل 0035: صفُّ
# عضويّتِه هو، وصلاحيتُه هو. فلا يُخرج هذا الاستعلامُ صفًّا لا يخصّ صاحبَ
# الجلسة، ولو جرى بلا مستأجرٍ أصلًا.
#
# **وأساسُ `view_project` شرطٌ في الجسر نفسِه**: صلاحيةُ فعلٍ وحدها لا
# تنقل أحدًا إلى مستأجرٍ آخر. و`access_state = 'active'` كذلك — فالموقوفُ
# والمُزال لا يعبُران.
# **وتماسكُ الفاعل بمستأجره شرطٌ قبل كلّ شيء.**
#
# فالسياقُ في الإنتاج يأتي من رمزٍ واحدٍ موقَّع: الفاعلُ ومستأجرُه
# الأصليّ من `sub` و`tid` معًا، فلا يفترقان. لكنّ **البِنيةَ الأمنيّةَ
# نفسَها لا يصحّ أن تقبل زوجًا غيرَ متماسك** كأنّه تفويضٌ صحيح: من ينادي
# هذه الدالّةَ بفاعلٍ ومستأجرٍ لا ينتمي إليه يجب أن يُردّ، لا أن يُخدَم.
#
# و`memberships` هي علاقةُ الانتماء المؤسّسيّ المُعتمدة، وهي محكومةٌ
# بعزل المستأجر — فتُقرأ هنا **قبل** إعادة الربط، في سياق المستأجر
# الأصليّ، حيث يرى الفاعلُ انتماءَه هو.
#
# وهو شرطٌ **في الاستعلام نفسِه**: لا عبارةَ ثانية، ولا ذهابَ وإياب زائد.
# وتُقرأ الحقيقتان في **عبارةٍ واحدة**: أمتماسكٌ هذا السياق؟ وأين يعيش
# هذا البحثُ بالنسبة لصاحبه؟ فالفصلُ بينهما لازمٌ — «لا تماسك» تُرَدّ،
# و«لا عضويّة» تُترك للحارس — والذهابُ مرّتين ثمنُه ذهابٌ وإياب.
_PROJECT_SCOPE = text(
    "SELECT "
    "  EXISTS (SELECT 1 FROM memberships hm "
    "           WHERE hm.user_id = app_current_actor() "
    "             AND hm.tenant_id = app_current_tenant()) AS coherent, "
    "  (SELECT m.tenant_id FROM project_members m "
    "     JOIN project_member_permissions p "
    "       ON p.member_id = m.id AND p.permission_key = 'view_project' "
    "    WHERE m.project_id = :project_id "
    "      AND m.user_id = app_current_actor() "
    "      AND m.access_state = 'active' "
    "    LIMIT 1) AS project_tenant"
)


@asynccontextmanager
async def project_session(
    project_id: UUID, tenant_id: UUID | None, actor_id: UUID | None,
) -> AsyncIterator[AsyncSession]:
    """جلسةٌ تدخل مستأجرَ البحث **إن كان للفاعل فيه مدخلٌ مُثبت**.

    وهذه هي النقطةُ الوحيدةُ التي يُعاد فيها ربطُ المستأجر داخل طلب. ولا
    تُنسخ في موجّه: خمسةَ عشرَ موجّهًا تأخذ `project_id`، ونسخةٌ من هذا
    المنطق في كلٍّ منها تفترق بأوّل تعديل.

    ## وما لا يأتي من العميل

    **مستأجرُ البحث يُشتقّ من صفِّ عضويّةٍ محفوظ، لا من الطلب.** لا جسمٌ
    ولا مُعامِلُ استعلامٍ ولا ترويسة تختار مستأجرًا. والفاعلُ يبقى هو
    نفسَه قبل الربط وبعده — يتغيّر المستأجرُ وحده.

    ## ولا يُعاد الربطُ إلّا عند الحاجة

    فصاحبُ البحث وزميلُه في مستأجره يبقيان في سياقهما الأصليّ: لا استعلامَ
    زائدَ الأثر، ولا مسارَ ثانٍ يفترق عن الأوّل في سلوكه.

    ## والتفويضُ ليس هنا

    هذه الدالّةُ تفتح بابَ **السياق** لا بابَ الإذن. ومَن يدخل البحثَ
    فعلًا يقرّره `ensure_project_access` كما منذ RC-T1A: مالكٌ مُثبت، أو
    عضوٌ نشِطٌ يحمل `view_project`. فلو أعادت هذه الدالّةُ ربطًا لا يستحقّه
    أحدٌ لَما أفاده: الحارسُ خلفه لم يُمسّ.

    **وصاحبُ البحث لا يُشترط له صفُّ عضويّة**: لا مطابقةَ هنا فلا ربط،
    ويبقى في مستأجره — وهو مستأجرُ بحثه أصلًا.

    ## وزوجٌ غيرُ متماسكٍ لا يُخدَم

    ولا يكفي أن يكون الفاعلُ صحيحًا: يجب أن يكون **منتميًا إلى المستأجر
    الذي فُتحت به الجلسة**. فمن نادى هذه الدالّةَ بفاعلٍ ومستأجرٍ لا صلةَ
    بينهما رُدَّ — انظر `_PROJECT_SCOPE`.
    """
    async with SessionFactory() as session:
        async with session.begin():
            if tenant_id is not None and actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true),"
                         "       set_config('app.actor_id', :aid, true)"),
                    {"tid": str(tenant_id), "aid": str(actor_id)},
                )
            elif tenant_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(tenant_id)},
                )
            elif actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.actor_id', :aid, true)"),
                    {"aid": str(actor_id)},
                )

            # **ولا تُدمج هذه العبارةُ مع ضبطِ السياق.** ترتيبُ تقييم
            # عناصر قائمة `SELECT` غيرُ مضمونٍ في PostgreSQL، والمُسنَد
            # يقرأ `app_current_actor()` — فدمجُهما يجعل الصحّةَ رهنَ
            # ترتيبٍ لم يَعِد به أحد.
            coherent, scope = (await session.execute(
                _PROJECT_SCOPE, {"project_id": str(project_id)})).one()

            # **وزوجٌ غيرُ متماسكٍ يُرَدّ، ولا يُخدَم بسياقٍ مُمرَّر.**
            #
            # ولو اكتُفي بترك الربط لَما كفى: من ينادي هذه الدالّةَ بفاعلٍ
            # ومستأجرٍ لا صلةَ بينهما **قد يُمرّر مستأجرَ البحث نفسَه**،
            # فتبقى الجلسةُ فيه ويُجيزه الحارسُ بحقّ — لأنّ عضويّتَه في
            # البحث حقيقية. فالمنعُ يقع هنا، عند بناء السياق، لا بعده.
            #
            # وفي الإنتاج لا يقع هذا أصلًا: الفاعلُ ومستأجرُه من رمزٍ
            # واحدٍ موقَّع. لكنّ البِنيةَ لا تتّكل على مَن يناديها.
            if tenant_id is not None and actor_id is not None and not coherent:
                raise Unauthorized("auth.invalid_credentials")

            if scope is not None and scope != tenant_id:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(scope)},
                )
            # والمستأجرُ النافذُ يُحفظ على الجلسة نفسِها، فيقرؤه الحارسُ
            # بعدُ بلا استعلامٍ ثانٍ ولا تخمين.
            session.info["scoped_tenant_id"] = scope if scope is not None else tenant_id
            yield session


# ── جسرُ القبول: الدعوةُ تُبلَغ قبل العضويّة ──
#
# **والقبولُ يقع قبل أن يوجد عضو**، فلا مُسنَد عضويّةٍ يخدمه. وحدُّه
# سياسةُ «الدعوةُ إليّ» من الترحيل 0035: `invited_user_id =
# app_current_actor()` — فيرى المدعوُّ دعوتَه هو وحدها، عبر المستأجرين،
# ولا يرى دعوةَ غيره.
#
# ويُقرأ التماسكُ معه في العبارة نفسِها، كما في جسر البحث: فاعلٌ ومستأجرٌ
# لا صلةَ بينهما لا يُخدَم — ولا يجوز أن يكون بابُ القبول أضعفَ من باب
# الوصول العاديّ.
# **والمُسنَدُ هو مُسنَدُ السياسة نفسُه، حرفًا بحرف** (الترحيل 0035):
# الدعوةُ إليّ إمّا بربطٍ صريح إلى حسابي، أو ببريدٍ **هو بريدُ حسابي أنا**.
#
# وكان هذا الجسرُ يعرف الأوّلَ وحده، فانكسر المنتجُ في أكثر حالاته شيوعًا:
# شاشةُ الفريق تدعو **ببريد**، والبحثُ عن الحساب فيها مقيَّدٌ بمستأجر
# الداعي — فمدعوٌّ من مؤسسةٍ أخرى يُكتب صفُّه بـ`invited_user_id` فارغًا.
# فكان يقرأ دعوتَه (السياسةُ تُجيز فرعَ البريد) ثمّ **يُردّ ٥٠٠ عند
# القبول**: الجلسةُ بقيت في مستأجره، والعضويّةُ تُكتب في مستأجر البحث،
# فترفضها RLS. وقد ظهر ذلك في أوّل تشغيلةٍ بمتصفّحٍ حقيقيّ، ولم يظهر في
# اختبارٍ واحدٍ من اختباراتنا: كلُّها كانت تُمرّر الربطَ الصريح.
#
# **ولا يوسّع هذا الجسرُ شيئًا**: السياسةُ في القاعدة هي الحدُّ، وهي
# تُجيز الفرعين أصلًا؛ فمن لا دعوةَ له لا يرى صفًّا هنا ولا يُنقل.
# والبريدُ مربوطٌ بـ`u.id = app_current_actor()` — فلا يُنتحل بريدُ غيره.
_INVITATION_SCOPE = text(
    "SELECT "
    "  EXISTS (SELECT 1 FROM memberships hm "
    "           WHERE hm.user_id = app_current_actor() "
    "             AND hm.tenant_id = app_current_tenant()) AS coherent, "
    "  (SELECT i.tenant_id FROM project_invitations i "
    "    WHERE i.token_hash = :token_hash "
    "      AND (i.invited_user_id = app_current_actor() "
    "           OR (i.invited_user_id IS NULL AND EXISTS ("
    "                 SELECT 1 FROM users u "
    "                  WHERE u.id = app_current_actor() "
    "                    AND lower(u.email) = lower(i.invited_email)))) "
    "    LIMIT 1) AS invitation_tenant"
)


@asynccontextmanager
async def invitation_session(
    token_hash: str, tenant_id: UUID | None, actor_id: UUID | None,
) -> AsyncIterator[AsyncSession]:
    """جلسةٌ تدخل مستأجرَ الدعوة **إن كانت الدعوةُ لصاحب الجلسة**.

    ولا تُستعمل `project_session` هنا: تلك تشترط عضويّةً نشِطة، والقبولُ
    هو ما يُنشئ العضويّة. فبابٌ آخر، بحدٍّ آخر، **وبقوّةٍ واحدة**.

    ## وما تُثبته قبل أن تنقل شيئًا

      • أنّ الفاعلَ ينتمي إلى المستأجر الذي فُتحت به الجلسة؛
      • وأنّ الدعوةَ المعنيّة **موجَّهةٌ إليه بعينه** — لا إلى بريدٍ
        يُشبه بريدَه، ولا إلى اسمٍ يُشبه اسمَه.

    والرمزُ يُمرَّر **مجزَّأً**: لا رمزَ خامٌّ يعبُر هذه الطبقة، ولا
    يُكتب في سجلّ.

    وما تعجز عنه لا تُخفيه: من لا دعوةَ له يبقى في مستأجره، ويردّه
    `accept_invitation` بعدها — فالتفويضُ النهائيُّ ليس هنا.
    """
    async with SessionFactory() as session:
        async with session.begin():
            if tenant_id is not None and actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true),"
                         "       set_config('app.actor_id', :aid, true)"),
                    {"tid": str(tenant_id), "aid": str(actor_id)},
                )
            elif actor_id is not None:
                await session.execute(
                    text("SELECT set_config('app.actor_id', :aid, true)"),
                    {"aid": str(actor_id)},
                )

            coherent, scope = (await session.execute(
                _INVITATION_SCOPE, {"token_hash": token_hash})).one()

            if tenant_id is not None and actor_id is not None and not coherent:
                raise Unauthorized("auth.invalid_credentials")

            if scope is not None and scope != tenant_id:
                await session.execute(
                    text("SELECT set_config('app.tenant_id', :tid, true)"),
                    {"tid": str(scope)},
                )
            session.info["scoped_tenant_id"] = scope if scope is not None else tenant_id
            yield session


def scoped_tenant(session: AsyncSession, default: UUID | None = None) -> UUID | None:
    """المستأجرُ الذي تعمل به هذه الجلسةُ فعلًا.

    فبعد عبورِ الجسر لم يعد مستأجرُ الرمز هو مستأجرَ المعاملة، وحارسٌ
    يقرأ `principal.tenant_id` بعدها يسأل عن المستأجر الخطأ.
    """
    return session.info.get("scoped_tenant_id", default)


@asynccontextmanager
async def system_session() -> AsyncIterator[AsyncSession]:
    """جلسة بلا مستأجر — للتسجيل والمصادقة فقط قبل تحديد السياق.

    لا تمنح تجاوزًا لـRLS: دور التطبيق لا يملك BYPASSRLS. الجداول التي
    تُقرأ هنا (users, tenants) لها سياسات خاصة موصوفة في الترحيل 0002.
    """
    async with SessionFactory() as session:
        async with session.begin():
            yield session
