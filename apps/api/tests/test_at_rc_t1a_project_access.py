"""عضويّةُ المستأجر ليست عضويّةَ بحث | Tenant membership is not project access (RC-T1A).

**العطبُ الذي يُغلق هنا، وقد كان قائمًا.**

قائمةُ «أبحاثي» كانت تُبنى بـ`tenant_id == principal.tenant_id` وحده،
وبوّابةُ فتح البحث كذلك. فكان أيُّ باحثٍ في المستأجر يرى عناوينَ أبحاث
زملائه ويفتحها بمعرّفها — أبحاثًا لا يملكها ولم يُدعَ إليها.

وهذا لا يستقيم مع فرق البحث: الفريقُ يُبنى على أنّ الوصولَ يُمنح صراحةً،
فإن كان ممنوحًا أصلًا لكلّ من في المستأجر فلا معنى لمنحه.

**والقاعدةُ الواحدة:** مالكٌ، أو عضوٌ **نشط** يحمل `view_project` صفًّا
صريحًا. ولا دورَ يُفسَّر، ولا انتماءَ مستأجرٍ يكفي.

## ولمَ يُجاب غيرُ المأذون بـ404

`403` تقول «موجودٌ ولستَ منه» — فتكشف وجودَ بحثٍ لمن لا شأن له به، ويصير
تعدادُ المعرّفات استدلالًا على ما في المستأجر. فالمعدومُ وغيرُ المأذون
يُجابان جوابًا واحدًا.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db

PROJECTS = "/api/v1/workspace/projects"
JOURNEY = "/api/v1/workspace/projects/{pid}/journey"


def _client(slot, locale: str = "ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


async def _owned_project(slot, *, title="بحثُ العزل") -> uuid.UUID:
    """بحثٌ يُنشأ **بالمسار الحقيقيّ** — فالملكيّةُ تُسجَّل كما تُسجَّل فعلًا."""
    async with _client(slot) as http:
        response = await http.post(PROJECTS, json={"title_ar": title})
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _second_user(tenant_id, *, email: str) -> dict:
    """باحثٌ ثانٍ في المستأجر نفسِه — زميلٌ لا شريك."""
    from sqlalchemy import select

    from athera_api.db import system_session, tenant_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    # **ودورُ المستأجر يُقرأ بسياقه.** `roles` محكومٌ بسياسة العزل، وجلسةٌ
    # بلا مستأجرٍ تُطابق صفرَ صفوف — وهو الفشلُ الآمن لا غيابُ الدور.
    # **و`users` جدولٌ عامّ بلا مستأجر**، و`memberships` و`roles` محكومان
    # بسياسة العزل. فيُكتب كلٌّ في سياقه: المستخدمُ بلا مستأجر، والانتماءُ
    # داخل مستأجره — وجلسةٌ بلا سياقٍ تُرفض كتابتُها، وهو الفشلُ الآمن.
    async with system_session() as session:
        user = User(email=email, password_hash=hash_password("Colleague-9f3b!"),
                    full_name_ar="زميلٌ في المركز", full_name_en="A colleague")
        session.add(user)
        await session.flush()
        user_id = user.id

    async with tenant_session(tenant_id) as scoped:
        role_id = (await scoped.execute(
            select(Role.id).where(Role.tenant_id == tenant_id,
                                  Role.key == "researcher"))).scalar_one()
        scoped.add(Membership(tenant_id=tenant_id, user_id=user_id, role_id=role_id))

    return {"tenant_id": tenant_id, "user_id": user_id, "email": email}


async def _titles(slot) -> list[str]:
    async with _client(slot) as http:
        response = await http.get(PROJECTS)
    assert response.status_code == 200, response.text
    return [row["title_ar"] for row in response.json()]


async def _invite_and_accept(owner, invitee, project_id, *, permissions):
    """دعوةٌ تُقبل بالمسار القائم — **ولا صفَّ عضويّةٍ يُدسّ بيد**."""
    from athera_api.db import tenant_session
    from athera_api.models.identity import User
    from athera_api.services import collaboration

    from sqlalchemy import select

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        email = (await session.execute(
            select(User.email).where(User.id == invitee["user_id"]))).scalar_one()
        issued = await collaboration.invite_member(
            session, tenant_id=owner["tenant_id"], project_id=project_id,
            inviter_user_id=owner["user_id"], display_name="زميل",
            email=email, role="co_author", permissions=list(permissions))
        token = issued.token

    async with tenant_session(invitee["tenant_id"], invitee["user_id"]) as session:
        member = await collaboration.accept_invitation(
            session, tenant_id=invitee["tenant_id"], token=token,
            accepting_user_id=invitee["user_id"])
    assert member is not None
    return member


# ═════════════════ أ · قبل العضويّة: لا يرى ولا يفتح ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_a_same_tenant_colleague_neither_sees_nor_opens_another_project(
        two_tenants):
    """**العطبُ بعينه** — زميلٌ في المستأجر ليس شريكًا في البحث."""
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ خاصٌّ بصاحبه")
    colleague = await _second_user(a["tenant_id"], email=f"c-{uuid.uuid4().hex[:8]}@x.test")

    # المالكُ يراه.
    assert "بحثٌ خاصٌّ بصاحبه" in await _titles(a)

    # والزميلُ لا يراه في قائمته.
    assert "بحثٌ خاصٌّ بصاحبه" not in await _titles(colleague)

    # ولا يفتحه بمعرّفه — **و404 لا 403**، فلا يُستدلّ على وجوده.
    async with _client(colleague) as http:
        opened = await http.get(JOURNEY.format(pid=project_id))
    assert opened.status_code == 404


# ═════════════════ ب · دورةُ الصلاحية كاملةً ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_access_follows_the_permission_through_its_whole_life(two_tenants):
    """**يُمنح فيرى، ويُنزع فيُحجب، ويُعاد فيعود** — والدورُ لا يتغيّر."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُشارَك")
    colleague = await _second_user(a["tenant_id"], email=f"m-{uuid.uuid4().hex[:8]}@x.test")

    await _invite_and_accept(a, colleague, project_id,
                             permissions=["view_project"])

    # ── مُنح: يرى ويفتح ──
    assert "بحثٌ يُشارَك" in await _titles(colleague)
    async with _client(colleague) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 200

    # ── نُزعت الصلاحية، والعضويّةُ باقية والدورُ كما هو ──
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        fresh = await collaboration.member_for(
            session, project_id=project_id, user_id=colleague["user_id"])
        await collaboration.set_permissions(
            session, tenant_id=a["tenant_id"], member=fresh,
            actor_user_id=a["user_id"], keys=[])
    assert "بحثٌ يُشارَك" not in await _titles(colleague)
    async with _client(colleague) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404

    # ── أُعيدت: يعود ──
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        fresh = await collaboration.member_for(
            session, project_id=project_id, user_id=colleague["user_id"])
        await collaboration.set_permissions(
            session, tenant_id=a["tenant_id"], member=fresh,
            actor_user_id=a["user_id"], keys=["view_project"])
    assert "بحثٌ يُشارَك" in await _titles(colleague)

    # ── أُوقف: يُحجب فورًا، بلا إعادة دخول ──
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        fresh = await collaboration.member_for(
            session, project_id=project_id, user_id=colleague["user_id"])
        await collaboration.set_access_state(
            session, tenant_id=a["tenant_id"], member=fresh,
            actor_user_id=a["user_id"], state="suspended")
    assert "بحثٌ يُشارَك" not in await _titles(colleague)
    async with _client(colleague) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404

    # ── أُزيل: يبقى محجوبًا ──
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        fresh = await collaboration.member_for(
            session, project_id=project_id, user_id=colleague["user_id"])
        await collaboration.set_access_state(
            session, tenant_id=a["tenant_id"], member=fresh,
            actor_user_id=a["user_id"], state="removed")
    assert "بحثٌ يُشارَك" not in await _titles(colleague)
    async with _client(colleague) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404

    # **والمالكُ لم يفقد بحثَه في شيءٍ من ذلك.**
    assert "بحثٌ يُشارَك" in await _titles(a)


@requires_db
@pytest.mark.asyncio
async def test_an_invitation_that_was_never_accepted_grants_nothing(two_tenants):
    """**والمدعوُّ ليس عضوًا** حتى يقبل."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.identity import User
    from athera_api.services import collaboration

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ دُعي إليه")
    invitee = await _second_user(a["tenant_id"], email=f"i-{uuid.uuid4().hex[:8]}@x.test")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        email = (await session.execute(
            select(User.email).where(User.id == invitee["user_id"]))).scalar_one()
        await collaboration.invite_member(
            session, tenant_id=a["tenant_id"], project_id=project_id,
            inviter_user_id=a["user_id"], display_name="مدعوّ",
            email=email, role="co_author", permissions=["view_project"])

    assert "بحثٌ دُعي إليه" not in await _titles(invitee)
    async with _client(invitee) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


# ═════════════════ ج · المستأجر الآخر ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_a_different_tenant_sees_nothing_of_this_project(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _owned_project(a, title="بحثٌ في مركزٍ آخر")

    assert "بحثٌ في مركزٍ آخر" not in await _titles(b)
    async with _client(b) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


# ═════════════════ د · ولا تكرار، ولا سلّةٌ تكشف ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_an_owner_who_is_also_a_member_appears_once(two_tenants):
    """**مجموعةٌ لا قائمة** — والمالكُ الذي له صفُّ عضويّةٍ يظهر مرّةً."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ لمالكٍ عضو")

    # `access_for` تُنشئ عضويّةَ المالك — فيصير مالكًا وعضوًا معًا.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await collaboration.access_for(
            session, tenant_id=a["tenant_id"], project_id=project_id,
            user_id=a["user_id"])

    titles = await _titles(a)
    assert titles.count("بحثٌ لمالكٍ عضو") == 1


@requires_db
@pytest.mark.asyncio
async def test_the_trash_listing_does_not_expose_a_colleagues_deleted_project(
        two_tenants):
    """**والسلّةُ كانت تكشف ما تكشفه القائمة.**"""
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ إلى السلّة")
    colleague = await _second_user(a["tenant_id"], email=f"t-{uuid.uuid4().hex[:8]}@x.test")

    async with _client(a) as http:
        trashed = await http.delete(f"{PROJECTS}/{project_id}")
    assert trashed.status_code in (200, 204), trashed.text

    async with _client(colleague) as http:
        theirs = await http.get(f"{PROJECTS}?trash=true")
    assert theirs.status_code == 200
    assert "بحثٌ إلى السلّة" not in [r["title_ar"] for r in theirs.json()]

    # والمالكُ يجدها في سلّته.
    async with _client(a) as http:
        mine = await http.get(f"{PROJECTS}?trash=true")
    assert "بحثٌ إلى السلّة" in [r["title_ar"] for r in mine.json()]
