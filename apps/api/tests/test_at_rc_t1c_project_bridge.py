"""جسرُ البحث عبر المؤسسات | RC-T1C: the cross-tenant project bridge.

**ما يُثبَت هنا، ولمَ قبل كلِّ شيءٍ آخر.**

أتاح RC-T1B أن يتقدّم باحثٌ في مؤسسةٍ إلى فرصةٍ في أخرى. وبقي نصفُ
القصّة: إذا قُبل، كيف يعمل على البحث نفسِه؟ وكلُّ طلبٍ يُفتح بمستأجر
الباحث الأصليّ، وجداولُ البحث محكومةٌ بـ`tenant_id = app_current_tenant()`
— فلا يرى البحثَ ولا عضويّتَه فيه ولا دعوتَه إليه.

فالجسرُ أوّلًا: سياساتُ «النفس» الثلاث (الترحيل 0035) تُري الفاعلَ صفَّه
هو، و`project_session` تُعيد ربطَ المعاملة بمستأجر البحث **إن كان له فيه
مدخلٌ مُثبت** — والتفويضُ يبقى عند `ensure_project_access` كما كان.

## ولمَ لا دالّةَ `SECURITY DEFINER`

قِيس الفرقُ فسقط المقترح: `athera_owner` مالكُ الدوالِّ القائمة، وهو
`rolsuper` و`rolbypassrls`. فدالّةٌ بحقوقه تقرأ عبر المستأجرين كلِّهم.
ويُقاس ذلك هنا صريحًا كي لا يُعاد اقتراحُه.
"""
from __future__ import annotations

import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _owned_project, _second_user  # noqa: E402

API = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
REPO = pathlib.Path(__file__).resolve().parents[3]

VIEW = "view_project"


async def _context(project_id, *, tenant_id, actor_id) -> tuple:
    """أين انتهت المعاملةُ فعلًا — مستأجرًا وفاعلًا."""
    from sqlalchemy import text

    from athera_api.db import project_session

    async with project_session(project_id, tenant_id, actor_id) as session:
        return (await session.execute(
            text("SELECT app_current_tenant(), app_current_actor()"))).one()


async def _external_member(owner, guest, project_id, *, permissions):
    """متعاونٌ من مستأجرٍ آخر — **وصفُّه يُكتب في مستأجر البحث**.

    فلو وُسم بمستأجر الضيف لَما رآه صاحبُ البحث في فريقه، ولَما طابقته
    استعلاماتُ RC-T1A التي ترشّح بـ`ProjectMember.tenant_id`.
    """
    from athera_api.db import tenant_session
    from athera_api.models.identity import User
    from athera_api.services import collaboration

    from sqlalchemy import select

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        email = (await session.execute(
            select(User.email).where(User.id == guest["user_id"]))).scalar_one()
        issued = await collaboration.invite_member(
            session, tenant_id=owner["tenant_id"], project_id=project_id,
            inviter_user_id=owner["user_id"], display_name="متعاونٌ خارجيّ",
            email=email, role="statistician", permissions=list(permissions))
        token = issued.token

    # **والقبولُ يقع في مستأجر البحث بفاعلِ الضيف** — وهو ما يجب أن يفعله
    # مسارُ القبول المُصحَّح: المستأجرُ مستأجرُ الدعوة، والفاعلُ من قَبِل.
    async with tenant_session(owner["tenant_id"], guest["user_id"]) as session:
        member = await collaboration.accept_invitation(
            session, tenant_id=owner["tenant_id"], token=token,
            accepting_user_id=guest["user_id"])
    return member


async def _set_permissions(owner, member, permissions):
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        fresh = await session.get(type(member), member.id)
        await collaboration.set_permissions(
            session, tenant_id=owner["tenant_id"], member=fresh,
            actor_user_id=owner["user_id"], keys=list(permissions))


async def _set_access(owner, member, state):
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        fresh = await session.get(type(member), member.id)
        await collaboration.set_access_state(
            session, tenant_id=owner["tenant_id"], member=fresh,
            actor_user_id=owner["user_id"], state=state)


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def bridge(two_tenants):
    """بحثٌ في «أ»، ومتعاونٌ نشِطٌ من «ب»، وغريبان."""
    owner = two_tenants["a"]
    guest = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]

    project_id = await _owned_project(owner, title="بحثٌ يتشارك عبر المؤسسات")
    colleague = await _second_user(owner["tenant_id"], email=f"col-{suffix}@example.test")
    outsider = await _second_user(guest["tenant_id"], email=f"out-{suffix}@example.test")

    member = await _external_member(owner, guest, project_id,
                                    permissions=[VIEW, "manage_data"])
    return World(owner=owner, guest=guest, member=member, colleague=colleague,
                 outsider=outsider, project_id=project_id, suffix=suffix)


# ═════════ ١–٣ · مَن يعبُر ومَن يبقى ═════════


@requires_db
@pytest.mark.asyncio
async def test_01_the_owner_stays_in_their_own_tenant(bridge):
    """**١ · صاحبُ البحث لا يعبُر جسرًا — بحثُه في مستأجره أصلًا.**

    ولا صفَّ عضويّةٍ يُشترط له: الجسرُ لا يجد مطابقةً فلا يُعيد ربطًا،
    ويبقى السياقُ كما فتحه الرمزُ الموقَّع. **وسلطتُه لا تُمَسّ.**
    """
    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.owner["tenant_id"],
        actor_id=bridge.owner["user_id"])
    assert tenant == bridge.owner["tenant_id"]
    assert actor == bridge.owner["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_02_a_same_tenant_member_stays_put(bridge):
    """**٢ · وزميلٌ في المستأجر نفسِه كذلك: لا ربطَ ولا استعلامَ ذا أثر.**"""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(bridge.owner["tenant_id"],
                              bridge.owner["user_id"]) as session:
        member = await collaboration.ensure_owner_membership(
            session, tenant_id=bridge.owner["tenant_id"],
            project_id=bridge.project_id, actor_user_id=bridge.owner["user_id"])
    assert member is not None

    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.owner["tenant_id"],
        actor_id=bridge.owner["user_id"])
    assert tenant == bridge.owner["tenant_id"]
    assert actor == bridge.owner["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_03_an_active_external_member_crosses(bridge):
    """**٣ · والمتعاونُ النشِطُ من مستأجرٍ آخر يعبُر — وهو الحدُّ المقصود.**"""
    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert tenant == bridge.owner["tenant_id"], "لم يعبُر المتعاونُ إلى مستأجر البحث"
    assert actor == bridge.guest["user_id"]


# ═════════ ٤–٨ · مَن لا يعبُر ═════════


@requires_db
@pytest.mark.asyncio
async def test_04_a_cross_tenant_outsider_cannot_hop(bridge):
    """**٤ · ومعرّفُ بحثٍ يُخمَّن لا ينقل أحدًا.**

    فلو كان التخمينُ يكفي لصار كلُّ بحثٍ في المنصّة مفتوحًا لمن يجرّب
    معرّفات.
    """
    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.outsider["tenant_id"],
        actor_id=bridge.outsider["user_id"])
    assert tenant == bridge.outsider["tenant_id"], "غريبٌ عبَر إلى مستأجر البحث"
    assert actor == bridge.outsider["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_04b_a_forged_project_id_moves_nobody(bridge):
    """ومعرّفٌ لا وجودَ له لا يُحرّك سياقًا."""
    tenant, _ = await _context(
        uuid.uuid4(), tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert tenant == bridge.guest["tenant_id"]


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["suspended", "removed"])
async def test_05_06_a_suspended_or_removed_member_cannot_cross(bridge, state):
    """**٥ و٦ · والإيقافُ والإزالةُ يُغلقان الجسرَ في الحال.**

    ولا يُنتظر انتهاءُ رمزٍ ولا تحديثُ ذاكرة: `access_state = 'active'`
    شرطٌ في مُسنَد الجسر نفسِه، يُقرأ في كلّ طلب.
    """
    before, _ = await _context(
        bridge.project_id, tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert before == bridge.owner["tenant_id"]

    await _set_access(bridge.owner, bridge.member, state)

    after, actor = await _context(
        bridge.project_id, tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert after == bridge.guest["tenant_id"], f"عضوٌ {state} ما زال يعبُر"
    assert actor == bridge.guest["user_id"]


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["manage_sources", "manage_data", "manage_team",
                                    "manage_tasks"])
async def test_07_08_an_action_permission_alone_opens_no_bridge(bridge, action):
    """**٧ و٨ · وصلاحيةُ فعلٍ بلا أساسِ `view_project` لا تنقل أحدًا.**

    وهذا أدقُّ ما في الجسر: `manage_sources` وحدها تبدو سلطةً أعلى من
    الرؤية، وهي ليست كذلك — صفٌّ غيرُ مكتملٍ لا سلطةَ فوق الأساس.
    """
    await _set_permissions(bridge.owner, bridge.member, [action])

    tenant, _ = await _context(
        bridge.project_id, tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert tenant == bridge.guest["tenant_id"], f"{action} وحدها فتحت الجسر"

    # وبالأساس معها يعبُر — فالحارسُ يميّز ولا يمنع كلَّ شيء.
    await _set_permissions(bridge.owner, bridge.member, [VIEW, action])
    tenant, _ = await _context(
        bridge.project_id, tenant_id=bridge.guest["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert tenant == bridge.owner["tenant_id"]


# ═════════ ٩–١١ · الفاعلُ والمصدر ═════════


@requires_db
@pytest.mark.asyncio
async def test_09_the_actor_never_changes_across_the_hop(bridge):
    """**٩ · يتغيّر المستأجرُ وحده — والفاعلُ هو هو قبلَ الجسر وبعده.**

    فلو تغيّر الفاعلُ لصار كلُّ أثرٍ يُكتب بعد العبور منسوبًا إلى غير
    صاحبه، ولانهار تدقيقُ «من فعل ماذا» في اللحظة التي يبدأ فيها التعاون.
    """
    from sqlalchemy import text

    from athera_api.db import project_session

    async with project_session(bridge.project_id, bridge.guest["tenant_id"],
                               bridge.guest["user_id"]) as session:
        # يُقاس داخل المعاملة نفسِها بعد الربط.
        tenant, actor = (await session.execute(
            text("SELECT app_current_tenant(), app_current_actor()"))).one()
    assert tenant == bridge.owner["tenant_id"]
    assert actor == bridge.guest["user_id"], "تبدّل الفاعلُ عند العبور"


@requires_db
@pytest.mark.asyncio
async def test_10_11_the_project_tenant_comes_only_from_a_persisted_row(bridge):
    """**١٠ و١١ · مستأجرُ البحث يُشتقّ من صفٍّ محفوظ، ولا حقلَ يختاره.**

    ويُقاس بمزجٍ مصنوع: فاعلٌ صحيحٌ مع مستأجرٍ أصليٍّ **ليس مستأجرَه**.
    فلو كان المستأجرُ المُمرَّر يُصدَّق لَعبَر بأيّ قيمةٍ تُكتب.
    """
    # ١. فاعلُ الضيف مع مستأجرٍ أصليٍّ مختلَق — يعبُر لأنّ صفَّه يقول ذلك،
    #    والمستأجرُ المُمرَّر لا يُستعمَل إلّا كنقطة بداية.
    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.outsider["tenant_id"],
        actor_id=bridge.guest["user_id"])
    assert tenant == bridge.owner["tenant_id"]
    assert actor == bridge.guest["user_id"]

    # ٢. وفاعلُ الغريب مع مستأجر البحث نفسِه — **لا يعبُر ولا يبقى فيه
    #    بحقّ**: لا صفَّ له، فلا شيءَ يُشتقّ. والحارسُ خلفه يُخفي البحث.
    tenant, actor = await _context(
        bridge.project_id, tenant_id=bridge.outsider["tenant_id"],
        actor_id=bridge.outsider["user_id"])
    assert tenant == bridge.outsider["tenant_id"]

    # ٣. ولا مُعامِلَ في التوقيع يحمل مستأجرَ بحثٍ أصلًا.
    import inspect

    from athera_api.db import project_session

    names = set(inspect.signature(project_session.__wrapped__).parameters)
    assert names == {"project_id", "tenant_id", "actor_id"}, names
    assert "project_tenant_id" not in names


# ═════════ ١٢ · المجمَّع ═════════


@requires_db
@pytest.mark.asyncio
async def test_12_a_reused_connection_carries_no_actor_or_tenant(bridge):
    """**١٢ · والاتصالُ المُعاد لا يحمل فاعلًا ولا مستأجرًا ولا مستأجرَ بحث.**

    وإعادةُ ربط المستأجر داخل الطلب تجعل هذا السؤالَ أحدَّ: لو تسرّب
    مستأجرُ بحثٍ إلى معاملةٍ تالية لقرأ باحثٌ بحثَ مؤسسةٍ أخرى بلا أيّ
    عضويّة.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from athera_api.config import get_settings
    from athera_api.db import _connect_args

    engine = create_async_engine(
        get_settings().database_url, pool_size=1, max_overflow=0,
        connect_args=_connect_args())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            pid_one = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true), "
                     "       set_config('app.actor_id', :u, true)"),
                {"t": str(bridge.owner["tenant_id"]), "u": str(bridge.guest["user_id"])})
            await session.commit()
        async with factory() as session:
            pid_two = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            leaked = (await session.execute(
                text("SELECT app_current_tenant(), app_current_actor()"))).one()
            await session.commit()
    finally:
        await engine.dispose()

    assert pid_one == pid_two, "لم يُعَد الاتصالُ نفسُه — فالفحصُ لا يُثبت إعادةَ استعمال"
    assert leaked == (None, None), f"سياقٌ عبَر المعاملة: {leaked}"


# ═════════ ١٣ و١٤ · ولا تجاوزَ ولا مُعرِّفٌ متميّز ═════════


@requires_db
@pytest.mark.asyncio
async def test_13_the_runtime_role_does_not_bypass_rls(bridge):
    """**١٣ · والدورُ الذي يعمل به الإنتاج لا يتجاوز العزل.**"""
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(bridge.guest["tenant_id"],
                              bridge.guest["user_id"]) as session:
        row = (await session.execute(text(
            "SELECT current_user, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"))).one()
    assert row[1] is False, f"{row[0]} متميّز"
    assert row[2] is False, f"{row[0]} يتجاوز RLS"


@requires_db
@pytest.mark.asyncio
async def test_14_no_privileged_definer_backs_the_bridge(bridge):
    """**١٤ · ولا دالّةَ `SECURITY DEFINER` تحت هذا الجسر — ولمَ ذلك يهمّ.**

    فمالكُ الدوالِّ القائمة `athera_owner`، وهو `rolsuper` و`rolbypassrls`.
    ويُقاس أثرُ ذلك هنا بمسبارَين متطابقَين إلّا في كلمة: الأوّلُ بحقوق
    المُعرِّف والثاني بحقوق المستدعي، كلاهما بلا سياق مستأجر.

    **وهذا الفحصُ يُبطل حجّةً بعينها**: أنّ `FORCE ROW LEVEL SECURITY`
    تُخضع المالكَ فتجعل `SECURITY DEFINER` آمنة. لا تفعل — والفرقُ يُقاس.
    وتعليلٌ بهذا المعنى مكتوبٌ في الترحيل 0034، وهو خطأٌ مُصحَّحٌ في 0035.
    """
    from sqlalchemy import text

    from athera_api.db import system_session, tenant_session

    # أ · الجسرُ نفسُه: لا دالّةَ فيه.
    source = (API / "db.py").read_text(encoding="utf-8")
    bridge_src = source[source.index("async def project_session"):
                        source.index("def scoped_tenant")]
    assert "SECURITY DEFINER" not in bridge_src.upper()
    assert "app_project_scope" not in bridge_src

    # ب · ولا دالّةَ بهذا الاسم في القاعدة.
    async with system_session() as session:
        found = (await session.execute(text(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = 'app_project_scope'"))).scalar_one()
    assert found == 0, "دالّةُ نطاقٍ متميّزةٌ أُنشئت رغم القرار"

    # ج · والبرهانُ على أنّ المالكَ يتجاوز — فلا يُقترح المسارُ ثانيةً.
    async with system_session() as session:
        owner_row = (await session.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname = (SELECT pg_get_userbyid(relowner) FROM pg_class "
            "                  WHERE relname = 'project_members')"))).one()
    assert owner_row[0] or owner_row[1], (
        "مالكُ الجداول لم يعد متميّزًا — فتُراجَع حجّةُ هذا الفحص، "
        "ولا تُقبل `SECURITY DEFINER` بلا قياسٍ جديد")

    # د · وسياساتُ «النفس» لا تُري الفاعلَ إلّا صفَّه.
    async with tenant_session(bridge.guest["tenant_id"],
                              bridge.guest["user_id"]) as session:
        mine = (await session.execute(text(
            "SELECT count(*) FROM project_members"))).scalar_one()
        not_mine = (await session.execute(text(
            "SELECT count(*) FROM project_members WHERE user_id <> app_current_actor() "
            "  AND tenant_id <> app_current_tenant()"))).scalar_one()
    assert mine >= 1, "الفاعلُ لا يرى عضويّتَه"
    assert not_mine == 0, "سياسةُ النفس أظهرت عضويّةَ غيره"


def test_14b_the_bridge_predicate_requires_the_baseline_and_active_state():
    """ومُسنَدُ الجسر يُقرأ حرفيًّا: أساسٌ، وحالٌ نشِطة، وفاعلٌ من الجلسة."""
    source = (API / "db.py").read_text(encoding="utf-8")
    predicate = source[source.index("_PROJECT_SCOPE = text("):
                       source.index("@asynccontextmanager\nasync def project_session")]
    for fragment in ("permission_key = 'view_project'",
                     "m.access_state = 'active'",
                     "m.user_id = app_current_actor()"):
        assert fragment in predicate, f"شرطٌ ناقصٌ في الجسر: {fragment}"
    # ولا مستأجرَ يأتي من خارج الصفّ.
    assert ":tenant" not in predicate and "project_tenant" not in predicate


@requires_db
@pytest.mark.asyncio
async def test_14c_the_bridge_costs_a_counted_number_of_round_trips(bridge):
    """وكلفةُ الجسر **تُعَدّ ولا تُقدَّر** — عبارةً عبارة.

    و«عددُ الاستعلامات هو زمنُ الاستجابة» في هذه الطبولوجيا: الخادمُ في
    سنغافورة والقاعدةُ في مومباي، ومذكرةُ الأداء تُسجّل عبارةً واحدةً على
    اتصالٍ قائم بنحو ٣٣٠ ميلي ثانية. فزيادةُ عبارةٍ ليست تفصيلًا.

    ويُثبَّت العددُ هنا حارسًا: من يزيد استعلامًا في الجسر يراه في فحصٍ
    يسقط، لا في شكوى مستخدمٍ بعد النشر.

    **ولا تُدمج العبارتان في واحدة**: ترتيبُ تقييم عناصر `SELECT` غيرُ
    مضمونٍ في PostgreSQL، والمُسنَدُ يقرأ `app_current_actor()` — فالدمجُ
    يجعل الصحّةَ رهنَ ترتيبٍ لم يَعِد به أحد.
    """
    from sqlalchemy import event

    from athera_api import db as dbmod

    counted = {"n": 0}

    def _count(conn, cursor, statement, params, context, executemany):
        counted["n"] += 1

    sync_engine = dbmod.engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _count)
    try:
        counted["n"] = 0
        async with dbmod.tenant_session(bridge.owner["tenant_id"],
                                        bridge.owner["user_id"]):
            pass
        baseline = counted["n"]

        counted["n"] = 0
        async with dbmod.project_session(bridge.project_id,
                                         bridge.owner["tenant_id"],
                                         bridge.owner["user_id"]):
            pass
        same_tenant = counted["n"]

        counted["n"] = 0
        async with dbmod.project_session(bridge.project_id,
                                         bridge.guest["tenant_id"],
                                         bridge.guest["user_id"]):
            pass
        cross_tenant = counted["n"]
    finally:
        event.remove(sync_engine, "before_cursor_execute", _count)

    assert baseline == 1, f"جلسةُ المستأجر لم تعُد عبارةً واحدة: {baseline}"
    # ضبطُ السياق + مُسنَدُ النطاق.
    assert same_tenant == 2, f"نفسُ المستأجر: {same_tenant} عبارة"
    # ويُضاف إليهما إعادةُ الربط وحدها.
    assert cross_tenant == 3, f"عبر المستأجرين: {cross_tenant} عبارة"


# ═════════ ١٥ و١٦ · ما لا يُمَسّ ═════════


@requires_db
@pytest.mark.asyncio
async def test_15_rc_t1a_project_access_is_unchanged(bridge):
    """**١٥ · وعضويّةُ المستأجر لم تعُد عضويّةَ بحث — ولا تزال.**

    فسياسةُ «النفس» تُري الفاعلَ صفَّه عبر المستأجرين، وقد تُغري بظنّ أنّ
    الرؤيةَ صارت تفويضًا. فيُعاد سؤالُ RC-T1A: الغريبُ في المستأجر لا
    يرى، والمالكُ مالك.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    tenant_id = bridge.owner["tenant_id"]

    async with tenant_session(tenant_id, bridge.colleague["user_id"]) as session:
        visible = await collaboration.visible_project_ids(
            session, tenant_id=tenant_id, user_id=bridge.colleague["user_id"])
        assert bridge.project_id not in visible, "زميلٌ في المستأجر يرى بحثًا"
        assert await collaboration.may_view_project(
            session, tenant_id=tenant_id, project_id=bridge.project_id,
            user_id=bridge.colleague["user_id"]) is False

    async with tenant_session(tenant_id, bridge.owner["user_id"]) as session:
        assert await collaboration.is_verified_owner(
            session, project_id=bridge.project_id,
            user_id=bridge.owner["user_id"]) is True


@requires_db
@pytest.mark.asyncio
async def test_16_the_external_member_row_lives_in_the_project_tenant(bridge):
    """**١٦ · وصفُّ المتعاون يُكتب في مستأجر البحث لا في مستأجره هو.**

    ولو وُسم بمستأجر الضيف لَما رآه صاحبُ البحث في فريقه — وهو أوّلُ ما
    ينكسر بصمت.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    async with tenant_session(bridge.owner["tenant_id"],
                              bridge.owner["user_id"]) as session:
        row = (await session.execute(
            select(ProjectMember.tenant_id, ProjectMember.user_id,
                   ProjectMember.access_state)
            .where(ProjectMember.project_id == bridge.project_id,
                   ProjectMember.user_id == bridge.guest["user_id"]))).one()
    assert row[0] == bridge.owner["tenant_id"], "صفُّ المتعاون في المستأجر الخطأ"
    assert row[2] == "active"
