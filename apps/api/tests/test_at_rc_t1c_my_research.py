"""«أبحاثي» عبر المؤسسات، ومدخلُ المتعاون الحقيقيّ | RC-T1C Phase 4.

**العطبُ الذي يغلقه هذا الملفّ عطبُ منتجٍ لا عطبُ حدّ**: كان الباحثُ
يَقبل الدعوةَ إلى بحثٍ في مؤسسةٍ أخرى — بكلّ ما بُني في المراحل السابقة —
ثمّ لا يجد البحثَ في أيّ شاشةٍ يفتحها. فالقبولُ صحيحٌ في القاعدة وغيرُ
مرئيٍّ في المنتج، وذاك أسوأُ من رفضٍ صريح.

ويُثبَت هنا أربعةُ أشياء:

  ١) القائمةُ تعرض بحثَ المؤسسة الأخرى — **بالجسر القانونيّ وحده**.
  ٢) وما دون العضويّة الحيّةِ الحاملةِ للاطّلاع لا يُعرض: دعوةٌ معلّقة،
     ولا اطّلاعَ له، وموقوفٌ، ومُزال، وغريبٌ في مؤسسةٍ ثالثة.
  ٣) ولا انتماءَ تنظيميًّا يُكتب في أيّ لحظة.
  ٤) والمتعاونُ المقبولُ **يستعمل البحثَ فعلًا** — لا بطاقةً في قائمةٍ
     خلفها ٤٠٤ في كلّ باب.

ولا اعتراضَ لنقطةٍ ولا تزييفَ تفويض: طلباتٌ حقيقيةٌ إلى FastAPI، وقاعدةٌ
حقيقيّة، وسياساتُ عزلٍ عاملة.
"""
from __future__ import annotations

import ast
import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _client, _owned_project, _second_user  # noqa: E402
from tests.test_at_rc_t1c_project_bridge import (  # noqa: E402
    _external_member,
    _member,
    _set_access,
    _set_permissions,
)
from tests.test_at_rc_t1c_recruitment_api import _third_tenant  # noqa: E402

PORTFOLIO = "/api/v1/portfolio/projects"
WORKSPACE = "/api/v1/workspace/projects"
TEAM = "/api/v1/projects"
TASKS = "/api/v1/project-management/projects"
VIEW = "view_project"
DATA = "manage_data"
SOURCES = "manage_sources"
TEAM_PERMISSION = "manage_team"


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


async def _titles(slot) -> dict[str, dict]:
    """«أبحاثي» كما تردّها الواجهةُ فعلًا — مفهرسةً بالمعرّف."""
    async with _client(slot) as http:
        response = await http.get(PORTFOLIO)
    assert response.status_code == 200, response.text
    return {row["id"]: row for row in response.json()}


@pytest.fixture
async def world(two_tenants):
    """ثلاثُ مؤسسات: «أ» فيها البحث، و«ب» متعاونٌ مقبول، و«ج» غريب."""
    owner = two_tenants["a"]
    guest = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]
    project_id = await _owned_project(owner, title="بحثُ «أبحاثي» عبر المؤسسات")
    # متعاونٌ من مؤسسةٍ أخرى: دورُه `statistician`، وصلاحيّاته صريحة —
    # الاطّلاعُ والبيانات، ولا مصادرَ ولا فريقَ ولا تقديم.
    member = await _external_member(owner, guest, project_id,
                                    permissions=[VIEW, DATA])
    outsider = await _third_tenant(suffix)
    colleague = await _second_user(owner["tenant_id"], email=f"clg-{suffix}@example.test")
    return World(owner=owner, guest=guest, outsider=outsider, colleague=colleague,
                 project_id=project_id, member=member, suffix=suffix)


# ═══════════════════ ١ · حقيقةُ «أبحاثي» ═══════════════════


@requires_db
@pytest.mark.asyncio
async def test_01_the_owner_still_sees_their_own_project_as_owner(world):
    """صاحبُ البحث يبقى صاحبَه — **والوسمُ يقول ذلك، فتُعرض أزرارُه**."""
    rows = await _titles(world.owner)
    card = rows[str(world.project_id)]
    assert card["is_owner"] is True
    assert card["relationship"] == "owner"


@requires_db
@pytest.mark.asyncio
async def test_02_a_same_tenant_member_is_labelled_a_collaborator(world):
    """وزميلٌ في المؤسسة نفسِها متعاونٌ لا مالك — **والفرقُ يُعلَن**.

    فالقائمةُ كانت كلَّها أبحاثَ صاحبها؛ ولو بقيت بلا وسمٍ لَعُرضت على
    العضو أزرارُ أرشفةِ بحثِ غيره وحذفِه.
    """
    await _member(world.owner, world.colleague, world.project_id,
                  permissions=[VIEW], role="co_author")
    card = (await _titles(world.colleague))[str(world.project_id)]
    assert card["is_owner"] is False
    assert card["relationship"] == "collaborator"
    assert card["member_role"] == "co_author"


@requires_db
@pytest.mark.asyncio
async def test_03_an_accepted_cross_tenant_member_sees_the_original_project(world):
    """**البحثُ الأصليُّ نفسُه يظهر لمتعاونٍ في مؤسسةٍ أخرى.**

    لا نسخةٌ، ولا بحثٌ ظلّ، ولا شاشةٌ ثانية اسمها «أبحاثٌ مشتركة»: هو في
    القائمة نفسِها، بمعرّفه وعنوانه.
    """
    owner_card = (await _titles(world.owner))[str(world.project_id)]
    rows = await _titles(world.guest)
    assert str(world.project_id) in rows, "لم يظهر البحثُ للمتعاون المقبول"
    card = rows[str(world.project_id)]
    assert card["working_title"] == owner_card["working_title"]
    assert card["is_owner"] is False
    assert card["relationship"] == "collaborator"
    assert card["member_role"] == "statistician"
    # ولا مستأجرَ في الجواب ولا معرّفَ مؤسسة: الشاشةُ تحتاج ما يملكه
    # الطالبُ فعلَه، لا موضعَ البحث تنظيميًّا.
    for forbidden in ("tenant_id", "organization_id", "profile_id"):
        assert forbidden not in card, forbidden


@requires_db
@pytest.mark.asyncio
async def test_04_an_outsider_in_a_third_tenant_sees_nothing(world):
    """وغريبٌ في مؤسسةٍ ثالثة لا يرى البحثَ — **والجسرُ يعرف الفاعل وحده**."""
    assert str(world.project_id) not in await _titles(world.outsider)


@requires_db
@pytest.mark.asyncio
async def test_05_an_explicit_view_project_row_is_required(world):
    """**والصلاحيةُ صفٌّ يُقرأ**: عضوٌ نُزع اطّلاعُه يختفي من القائمة.

    ولو كفى «عضوٌ نشِط» لَبقي البحثُ في قائمة من سُحب مدخلُه — وقائمةٌ
    تعرض ما لا يُفتح تسريبُ عنوانٍ لا تسامح.
    """
    await _set_permissions(world.owner, world.member, [DATA])
    assert str(world.project_id) not in await _titles(world.guest)

    await _set_permissions(world.owner, world.member, [VIEW, DATA])
    assert str(world.project_id) in await _titles(world.guest)


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["suspended", "removed"])
async def test_06_07_a_suspended_or_removed_member_loses_the_card(world, state):
    """موقوفٌ ومُزالٌ ليسا عضوين عاملين — **والقائمةُ تقول الحقَّ فورًا**."""
    await _set_access(world.owner, world.member, state)
    assert str(world.project_id) not in await _titles(world.guest)


@requires_db
@pytest.mark.asyncio
async def test_08_restoring_a_suspended_member_returns_the_card(world):
    """والإيقافُ ليس حكمًا أبديًّا: الاستعادةُ تُعيد البحثَ في الطلب التالي.

    **ولا كذبةَ ذاكرةٍ هنا**: لا خروجٌ ولا تجديدُ رمزٍ ولا انتظارُ مهلة —
    الطلبُ التالي يقرأ الصفَّ كما هو.
    """
    await _set_access(world.owner, world.member, "suspended")
    assert str(world.project_id) not in await _titles(world.guest)
    await _set_access(world.owner, world.member, "active")
    assert str(world.project_id) in await _titles(world.guest)


@requires_db
@pytest.mark.asyncio
async def test_09_a_pending_invitation_lists_nothing(world):
    """ودعوةٌ لم تُقبل ليست عضويّة — **فلا بطاقةَ قبل القبول**."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        await collaboration.invite_member(
            session, tenant_id=world.owner["tenant_id"], project_id=world.project_id,
            inviter_user_id=world.owner["user_id"], display_name="مدعوٌّ لم يقبل",
            email=world.outsider["email"], role="co_author",
            permissions=[VIEW], invited_user_id=world.outsider["user_id"])

    assert str(world.project_id) not in await _titles(world.outsider)


@requires_db
@pytest.mark.asyncio
async def test_10_no_organization_membership_is_ever_created(world):
    """**ومنحُ التعاون ليس انتماءً إلى مؤسسة** — ولا صفَّ انتماءٍ يُكتب.

    ولو كُتب لَصار المتعاونُ عضوًا في كلّ ما في تلك المؤسسة: أبحاثِ
    زملائها، ومكتبتِها، وسجلِّها. والقائمةُ تُحلّ بالجسر، لا بترقيةِ
    الضيف إلى موظَّف.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.identity import Membership

    assert str(world.project_id) in await _titles(world.guest)
    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        count = (await session.execute(
            select(func.count()).select_from(Membership)
            .where(Membership.tenant_id == world.owner["tenant_id"],
                   Membership.user_id == world.guest["user_id"]))).scalar_one()
    assert count == 0, "كُتب انتماءٌ تنظيميّ لأجل قائمة"


@requires_db
@pytest.mark.asyncio
async def test_11_an_owner_who_is_also_a_member_appears_once(world):
    """صفٌّ واحدٌ لكلّ بحث — **والملكيّةُ تسبق العضويّة في الوسم**."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        await collaboration.ensure_owner_membership(
            session, tenant_id=world.owner["tenant_id"], project_id=world.project_id,
            actor_user_id=world.owner["user_id"])

    async with _client(world.owner) as http:
        rows = (await http.get(PORTFOLIO)).json()
    mine = [row for row in rows if row["id"] == str(world.project_id)]
    assert len(mine) == 1, mine
    assert mine[0]["relationship"] == "owner"


@requires_db
@pytest.mark.asyncio
async def test_12_research_projects_has_no_actor_wide_read_policy(world):
    """**ولم يُفتح الجدولُ للفاعل عبر المستأجرين** — لا هنا ولا في 0035.

    فالحلُّ الرخيصُ كان سياسةَ `app_current_actor()` على
    `research_projects` نفسِه، أو دالّةَ `SECURITY DEFINER` تقرأ بلا عزل.
    وكلاهما يفتح الجدولَ أوسعَ من الحاجة: القائمةُ تحتاج **بحثًا بعينه
    لمن له فيه صفٌّ**، لا قراءةً عامّةً للفاعل.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT policyname, coalesce(qual, '') || ' ' || coalesce(with_check, '') "
            "  FROM pg_policies WHERE tablename = 'research_projects'"))).all()
    assert rows, "لا سياسةَ على research_projects أصلًا"
    for name, body in rows:
        assert "app_current_actor" not in body, (name, body)
        assert "true" != body.strip().lower(), (name, body)


# ═══════════════ ٢ · مدخلُ المتعاون الحقيقيّ ═══════════════


@requires_db
@pytest.mark.asyncio
async def test_13_the_access_endpoint_reports_server_derived_capability(world):
    """ما يملكه الطالبُ يُقرأ من الخادم — **ولا يُشتقّ من دورٍ في الشاشة**.

    فالدورُ `statistician` وحده لا يقول شيئًا: الصلاحياتُ صفوفٌ صريحة،
    وواجهةٌ تشتقّها من الدور تعرض زرًّا لا يعمل أو تُخفي زرًّا يعمل.
    """
    async with _client(world.guest) as http:
        response = await http.get(f"{TEAM}/{world.project_id}/access")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_owner"] is False
    assert body["relationship"] == "collaborator"
    assert body["role"] == "statistician"
    assert body["access_state"] == "active"
    assert sorted(body["permissions"]) == [DATA, VIEW]
    assert body["can_manage_data"] is True
    assert body["can_manage_sources"] is False
    assert body["can_manage_team"] is False
    assert body["can_manage_submission"] is False


@requires_db
@pytest.mark.asyncio
async def test_14_the_access_endpoint_creates_no_membership_row(world):
    """**وفتحُ صفحةٍ لا يكتب صفًّا.** فالقراءةُ قراءة، والعضويّةُ لا تُختلق."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    async def members() -> int:
        async with tenant_session(world.owner["tenant_id"],
                                  world.owner["user_id"]) as session:
            return (await session.execute(
                select(func.count()).select_from(ProjectMember)
                .where(ProjectMember.project_id == world.project_id))).scalar_one()

    before = await members()
    async with _client(world.owner) as http:
        assert (await http.get(f"{TEAM}/{world.project_id}/access")).status_code == 200
    assert await members() == before


@requires_db
@pytest.mark.asyncio
async def test_15_an_outsider_is_concealed_by_the_access_endpoint(world):
    """وغريبٌ يُردّ ٤٠٤ لا ٤٠٣ — **فوجودُ بحثِ غيرك معلومةٌ لا تُفشى**."""
    async with _client(world.outsider) as http:
        response = await http.get(f"{TEAM}/{world.project_id}/access")
    assert response.status_code == 404, response.text


@requires_db
@pytest.mark.asyncio
async def test_16_the_external_collaborator_can_actually_use_the_project(world):
    """**البطاقةُ ليست وعدًا فارغًا**: الأبوابُ تُفتح فعلًا.

    وهذا هو الفحصُ الذي يفصل «قائمةً جميلة» عن منتجٍ يعمل: بحثٌ ظاهرٌ في
    «أبحاثي» وخلفه ٤٠٤ في النظرة العامّة والرحلة والفريق والمهام أسوأُ من
    بحثٍ لا يظهر.
    """
    async with _client(world.guest) as http:
        for path in (f"{WORKSPACE}/{world.project_id}/overview",
                     f"{WORKSPACE}/{world.project_id}/journey",
                     f"{WORKSPACE}/{world.project_id}/sources",
                     f"{TEAM}/{world.project_id}/members",
                     f"{TEAM}/{world.project_id}/member-events",
                     f"{TASKS}/{world.project_id}/tasks"):
            response = await http.get(path)
            assert response.status_code == 200, f"{path} → {response.status_code} {response.text[:200]}"


@requires_db
@pytest.mark.asyncio
async def test_17_the_same_project_not_a_copy(world):
    """والبحثُ الذي يُفتح هو البحثُ نفسُه — **معرّفًا وعنوانًا وحالةً**."""
    async with _client(world.owner) as http:
        owner_view = (await http.get(f"{WORKSPACE}/{world.project_id}/overview")).json()
    async with _client(world.guest) as http:
        guest_view = (await http.get(f"{WORKSPACE}/{world.project_id}/overview")).json()
    assert guest_view["project"]["id"] == owner_view["project"]["id"]
    assert guest_view["project"]["title_ar"] == owner_view["project"]["title_ar"]
    assert guest_view["project"]["status"] == owner_view["project"]["status"]


@requires_db
@pytest.mark.asyncio
async def test_18_permissions_decide_not_the_role(world):
    """**الدورُ ليس صلاحية** — ويُثبَت ذلك بمنحٍ واحدٍ بلا تغييرِ دور.

    قبلَه: لا مصادرَ ولا فريقَ ولا مهامّ. وبعده: المصادرُ وحدها — والدورُ
    كما كان `statistician`.
    """
    from athera_api.db import tenant_session
    from athera_api.models.literature import Source

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        source = Source(tenant_id=world.owner["tenant_id"],
                        title="دراسةٌ سابقةٌ للربط", retraction_status="unknown")
        session.add(source)
        await session.flush()
        source_id = source.id

    link = f"{WORKSPACE}/{world.project_id}/sources"
    async with _client(world.guest) as http:
        denied = await http.post(link, json={"asset_id": str(source_id)})
        assert denied.status_code == 403, denied.text

        no_team = await http.post(
            f"{TEAM}/{world.project_id}/members",
            json={"display_name": "من يُدسّ", "role": "co_author"})
        assert no_team.status_code == 403, no_team.text

        no_tasks = await http.post(
            f"{TASKS}/{world.project_id}/tasks",
            json={"title": "مهمّةٌ لا تُنشأ", "stage": "idea"})
        assert no_tasks.status_code == 403, no_tasks.text

    # ومنحٌ واحدٌ صريح — **بلا تغييرِ دور**.
    await _set_permissions(world.owner, world.member, [VIEW, DATA, SOURCES])

    async with _client(world.guest) as http:
        allowed = await http.post(link, json={"asset_id": str(source_id)})
        assert allowed.status_code == 201, allowed.text
        access = (await http.get(f"{TEAM}/{world.project_id}/access")).json()
    assert access["role"] == "statistician", "تغيّر الدورُ مع الصلاحية"
    assert access["can_manage_sources"] is True
    assert access["can_manage_team"] is False


@requires_db
@pytest.mark.asyncio
async def test_19_suspension_bites_on_the_very_next_request(world):
    """**ولا كذبةَ ذاكرة**: الإيقافُ يُقفل البابَ في الطلب التالي مباشرة.

    ولا خروجٌ ولا تجديدُ رمزٍ ولا مهلةُ ذاكرة: الرمزُ نفسُه، والصفُّ
    تغيّر، والجوابُ تغيّر معه.
    """
    overview = f"{WORKSPACE}/{world.project_id}/overview"
    async with _client(world.guest) as http:
        assert (await http.get(overview)).status_code == 200
        await _set_access(world.owner, world.member, "suspended")
        assert (await http.get(overview)).status_code == 404
        await _set_access(world.owner, world.member, "active")
        assert (await http.get(overview)).status_code == 200


@requires_db
@pytest.mark.asyncio
async def test_20_membership_grants_neither_authorship_nor_credit(world):
    """والقبولُ في فريقٍ **ليس تأليفًا ولا مساهمةَ CRediT** — ولا يُستنتج."""
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        row = await session.get(ProjectMember, world.member.id)
        assert row is not None
        assert row.is_author is False
        assert not (row.credit_roles or [])


# ═══════════ ٣ · قياسُ الثمن (N+1 معلومٌ لا مخفيّ) ═══════════


@requires_db
@pytest.mark.asyncio
async def test_21_the_cross_tenant_listing_costs_one_bridge_per_foreign_project(world):
    """الثمنُ يُقاس ويُعلَن — **ولا يُشترى بحدّ العزل**.

    فأبحاثُ مستأجرِ الباحث كلُّها في عبارتين (ملكيّةٌ) وعبارةٍ (عضويّة)
    وعبارةِ قراءة. وكلُّ بحثٍ **خارج** مستأجره يزيد جسرًا قانونيًّا
    كاملًا: ضبطُ سياقٍ، ثمّ إثباتُ العضويّة، ثمّ ربطٌ، ثمّ قراءة.

    والرقمُ مثبَّتٌ هنا كي لا يزحف صامتًا: من يجعل القائمةَ أغلى يرى
    ذلك في اختبارٍ يفشل، لا في زمنِ استجابةٍ في الإنتاج.
    """
    from sqlalchemy import event

    from athera_api import db as dbmod
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    counted: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        counted.append(statement)

    sync_engine = dbmod.engine.sync_engine
    event.listen(sync_engine, "before_cursor_execute", _count)
    try:
        async with tenant_session(world.guest["tenant_id"],
                                 world.guest["user_id"]) as session:
            counted.clear()
            entries = await collaboration.my_research(
                session, tenant_id=world.guest["tenant_id"],
                user_id=world.guest["user_id"])
    finally:
        event.remove(sync_engine, "before_cursor_execute", _count)

    assert [str(e.project.id) for e in entries] == [str(world.project_id)]
    # ٣ في المستأجر (ملكيّةٌ بعبارتين، وعضويّةٌ بعبارة) + ٤ للجسر الواحد.
    # ولا عبارةَ قراءةٍ محليّة: لا بحثَ في مستأجر الضيف أصلًا.
    assert len(counted) == 7, [s.split("\n")[0][:80] for s in counted]


# ═══════════ ٤ · تدقيقُ مسارات البحث (بنيويّ) ═══════════

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"
METHODS = {"get", "post", "put", "patch", "delete"}

# **الاستثناءُ الوحيدُ المُعلَن**، وسببُه بنيويٌّ لا ذوقيّ: هذا المسار لا
# يأخذ جلسةً تبعيةً لأنّ تبعيةً واحدةً تُبقي معاملةً مفتوحةً طوال انتظارِ
# مزوّدٍ خارجي (علّة S5C: اتصالٌ `idle in transaction` عبر انتظارٍ شبكي).
# فيبني الجسرَ نفسَه في جسمه عبر `_maker` → `project_session`، ويُفحص
# ذلك أدناه بالنصّ لا بالثقة.
IN_BODY_BRIDGE = {("planning.py", "generate_opportunities")}


def _route_templates(node) -> list[str]:
    """قوالبُ المسار من المُزخرِفات — **ونصوصًا حرفيّةً فقط**.

    فالمحلّلُ الساكن لا يفهم `A + "/b"`، وقد سُكِّت حارسٌ من قبل بهذا
    بالضبط: صار وسيطُ المُزخرِف `BinOp` فانهار الفاحصُ بصمت وعدّ الصفرَ
    نجاحًا. فما ليس نصًّا حرفيًّا **يُرفع عطبًا** هنا ولا يُتجاوَز.
    """
    out: list[str] = []
    for dec in node.decorator_list:
        if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                and dec.func.attr in METHODS and dec.args):
            continue
        first = dec.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append(first.value)
        elif isinstance(first, ast.JoinedStr):
            raise AssertionError(f"قالبُ مسارٍ مبنيٌّ بـf-string في {node.name}")
        else:
            try:
                value = ast.literal_eval(first)
            except Exception as exc:  # noqa: BLE001
                raise AssertionError(
                    f"قالبُ مسارٍ غيرُ حرفيّ في {node.name}: "
                    f"{ast.dump(first)[:120]}") from exc
            assert isinstance(value, str), node.name
            out.append(value)
    return out


def _session_dependencies(node) -> set[str]:
    names: set[str] = set()
    defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
    for default in defaults:
        if (isinstance(default, ast.Call)
                and getattr(default.func, "id", None) == "Depends"
                and default.args):
            target = default.args[0]
            name = getattr(target, "id", None) or getattr(target, "attr", None)
            if name and "session" in name:
                names.add(name)
    return names


def _project_routes() -> list[tuple[str, str, tuple[str, ...], set[str], str]]:
    """جردٌ آليٌّ لكلّ مسارٍ يأخذ معرّفَ بحثٍ **في قالب مساره**."""
    found = []
    for path in sorted(ROUTERS.glob("*.py")):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            templates = _route_templates(node)
            if not any("{project_id}" in t for t in templates):
                continue
            found.append((path.name, node.name, tuple(templates),
                          _session_dependencies(node),
                          ast.get_source_segment(source, node) or ""))
    return found


@requires_db
def test_22_every_project_scoped_route_enters_through_the_canonical_bridge():
    """**ولا مسارَ بحثٍ يدخل من جلسة البيت ثمّ يفوّض.**

    فالترتيبُ هو المسألة: من فتح جلسةً بمستأجر رمزه ثمّ سأل
    `ensure_project_access` عن بحثٍ في مؤسسةٍ أخرى قرأ صفرَ صفوف — فيردّ
    ٤٠٤ على بحثٍ الطالبُ عضوٌ فيه بحقّ. وهو العطبُ الذي وقع في مساراتِ
    قرار المدير، وكُشف بطلبٍ حقيقيّ لا بمراجعة.

    والحارسُ يفشل بأوّل مسارٍ جديدٍ يُكتب على `get_session` — فلا يُكتشف
    هذا مرّةً أخرى بعد الشحن.
    """
    offenders = []
    for file_name, func_name, _templates, deps, body in _project_routes():
        if (file_name, func_name) in IN_BODY_BRIDGE:
            # والاستثناءُ يُفحص لا يُصدَّق: لا تبعيةَ جلسةٍ أصلًا، والجسرُ
            # القانونيُّ مبنيٌّ في الجسم.
            assert not deps, (file_name, func_name, deps)
            assert "_maker(project_id" in body, (file_name, func_name)
            maker = (ROUTERS / file_name).read_text()
            assert "return project_session(project_id, tenant_id, actor_id)" in maker
            continue
        if deps != {"get_project_session"}:
            offenders.append((file_name, func_name, sorted(deps)))
    assert not offenders, offenders


@requires_db
def test_23_the_project_route_inventory_is_pinned():
    """والعددُ مثبَّت: **مسارٌ جديد يُراجَع، لا يُضاف بصمت**."""
    routes = _project_routes()
    assert len(routes) == 96, len(routes)
    bridged = [r for r in routes if r[3] == {"get_project_session"}]
    assert len(bridged) == 95, len(bridged)
    assert len(IN_BODY_BRIDGE) == 1


@requires_db
def test_24_no_project_route_reads_the_token_tenant_after_the_bridge():
    """**ومن قرأ مستأجرَ رمزه بعد العبور سأل عن المستأجر الخطأ.**

    والخطأُ هنا أسوأُ من ٤٠٤: كتابةٌ في مستأجرٍ لا يراه أحد — صفٌّ
    يُخزَّن ويُعدّ نجاحًا ولا يظهر في أيّ شاشة.
    """
    offenders = []
    for file_name, func_name, _templates, deps, body in _project_routes():
        if deps != {"get_project_session"}:
            continue
        if "principal.tenant_id" in body:
            offenders.append((file_name, func_name))
    assert not offenders, offenders
