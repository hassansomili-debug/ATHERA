"""مَن يقرأ دعوةً | RC-T1C: closing a pre-existing ProjectInvitation leak.

**دَينٌ سابقٌ اكتُشف في أثناء RC-T1C — لا شيءٌ أحدثته هذه المرحلة.**

أنشأ الترحيلُ 0028 على `project_invitations` سياسةً واحدةً `FOR ALL`
حدُّها `tenant_id = app_current_tenant()`. فكلُّ مصادَقٍ في مستأجرٍ كان
يقرأ **كلَّ دعوات مستأجره**: مَن دُعي، وإلى أيّ بحث، وبأيّ دورٍ
وصلاحيات — ولو لم يكن من ذلك البحث بشيء.

والموجّهُ يشترط `manage_team`، لكنّ **حدَّ القاعدة كان أوسعَ من حدِّ
الموجّه**. وسياسةُ «الدعوةُ إليّ» التي أضافها 0035 أوّلًا لم تُضيّق شيئًا:
سياساتُ PostgreSQL المُتاحة تتجمّع بـ«أو»، فالعريضةُ تبقى تُشبع القراءة
وحدها. فلا بدّ من **إسقاطها** ووضعِ طقمٍ مُفصَّلٍ بالأفعال مكانها.

ويُقاس ذلك كلُّه **عند القاعدة** لا عند الموجّه: ما يُثبَت هنا يصمد أمام
موجّهٍ يُكتب غدًا.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _owned_project, _second_user  # noqa: E402
from tests.test_at_rc_t1c_project_bridge import _member  # noqa: E402

VIEW = "view_project"
INVITATIONS = "project_invitations"


async def _issue(owner, project_id, *, email, invited_user_id=None,
                 role="co_author", permissions=(VIEW,)):
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        issued = await collaboration.invite_member(
            session, tenant_id=owner["tenant_id"], project_id=project_id,
            inviter_user_id=owner["user_id"], email=email,
            display_name="مدعوٌّ للفحص", role=role,
            permissions=list(permissions), invited_user_id=invited_user_id)
        return issued.invitation.id, issued.token


async def _visible(slot) -> set[uuid.UUID]:
    """ما يراه هذا الفاعلُ من الدعوات — بجلسته الأصليّة."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.collaboration import ProjectInvitation

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        return set((await session.execute(
            select(ProjectInvitation.id))).scalars().all())


async def _email_of(slot) -> str:
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import User

    async with system_session() as session:
        return (await session.execute(
            select(User.email).where(User.id == slot["user_id"]))).scalar_one()


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def invites(two_tenants):
    owner = two_tenants["a"]
    outsider_tenant = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]

    project_id = await _owned_project(owner, title="بحثُ خصوصيّة الدعوات")
    other_project_id = await _owned_project(owner, title="بحثٌ ثانٍ")

    manager = await _second_user(owner["tenant_id"], email=f"mgr-{suffix}@example.test")
    plain = await _second_user(owner["tenant_id"], email=f"pln-{suffix}@example.test")
    pi = await _second_user(owner["tenant_id"], email=f"pi-{suffix}@example.test")
    stranger = await _second_user(owner["tenant_id"], email=f"str-{suffix}@example.test")
    recipient = outsider_tenant
    foreigner = await _second_user(outsider_tenant["tenant_id"],
                                   email=f"frn-{suffix}@example.test")

    manager_member = await _member(owner, manager, project_id,
                                   permissions=[VIEW, "manage_team"])
    await _member(owner, plain, project_id, permissions=[VIEW])
    # **دورٌ باسمه لا يُفوّض**: باحثٌ رئيسٌ بلا `manage_team` صريحة.
    await _member(owner, pi, project_id, permissions=[VIEW],
                  role="principal_investigator")

    invitation_id, token = await _issue(
        owner, project_id, email=await _email_of(recipient),
        invited_user_id=recipient["user_id"])

    return World(owner=owner, manager=manager, manager_member=manager_member,
                 plain=plain, pi=pi, stranger=stranger, recipient=recipient,
                 foreigner=foreigner, project_id=project_id,
                 other_project_id=other_project_id,
                 invitation_id=invitation_id, token=token, suffix=suffix)


# ═════════ ١–٣ · مَن يقرأ ومَن لا يقرأ ═════════


@requires_db
@pytest.mark.asyncio
async def test_01_the_exact_recipient_reads_their_own_invitation_across_tenants(invites):
    """**١ · المدعوُّ بعينه يقرأ دعوتَه — عبر المستأجرين، وقبل العضويّة.**"""
    assert invites.invitation_id in await _visible(invites.recipient)


@requires_db
@pytest.mark.asyncio
async def test_02_the_recipient_reads_no_other_invitation(invites):
    """**٢ · ولا يقرأ دعوةَ غيره.**"""
    second_id, _ = await _issue(
        invites.owner, invites.project_id,
        email=await _email_of(invites.foreigner),
        invited_user_id=invites.foreigner["user_id"])
    seen = await _visible(invites.recipient)
    assert invites.invitation_id in seen
    assert second_id not in seen, "المدعوُّ قرأ دعوةَ مرشَّحٍ آخر"


@requires_db
@pytest.mark.asyncio
async def test_03_a_same_tenant_stranger_reads_nothing(invites):
    """**٣ · والغريبُ في مستأجر البحث لا يقرأ شيئًا — وهذا هو الكشفُ المُغلَق.**

    فقبل 0035 كانت سياسةُ 0028 تُسلّمه كلَّ دعوات مستأجره.
    """
    assert await _visible(invites.stranger) == set()


@requires_db
@pytest.mark.asyncio
async def test_03b_a_cross_tenant_stranger_reads_nothing(invites):
    """وغريبٌ في مستأجرٍ آخر كذلك."""
    assert invites.invitation_id not in await _visible(invites.foreigner)


# ═════════ ٤–٨ · حدُّ المدير ═════════


@requires_db
@pytest.mark.asyncio
async def test_04_a_member_without_manage_team_reads_no_invitation(invites):
    """**٤ · وعضوٌ في البحث بلا `manage_team` لا يقرأ قائمةَ الدعوات.**

    فالعضويّةُ ليست إدارةَ فريق، والرؤيةُ ليست تفويضًا.
    """
    # **ويرى كلٌّ منهما دعوتَه هو** — فقد دُعي ليصير عضوًا. والمقصودُ
    # أنّه لا يرى دعوةَ غيره، لا أنّه أعمى عن نفسه.
    assert invites.invitation_id not in await _visible(invites.plain)


@requires_db
@pytest.mark.asyncio
async def test_05_an_authorized_manager_reads_the_project_invitations(invites):
    """**٥ · والمديرُ النشِطُ له الأساسُ و`manage_team` يقرأ.**"""
    assert invites.invitation_id in await _visible(invites.manager)


@requires_db
@pytest.mark.asyncio
async def test_05b_the_verified_owner_reads_them(invites):
    """وصاحبُ البحث كذلك — سلطةُ جذرٍ لا صفُّ صلاحية."""
    assert invites.invitation_id in await _visible(invites.owner)


@requires_db
@pytest.mark.asyncio
async def test_06_the_principal_investigator_role_alone_reads_nothing(invites):
    """**٦ · واسمُ الدور لا يُفوّض** — `principal_investigator` بلا `manage_team`."""
    assert invites.invitation_id not in await _visible(invites.pi)


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["suspended", "removed"])
async def test_07_08_a_suspended_or_removed_manager_reads_nothing(invites, state):
    """**٧ و٨ · والإيقافُ والإزالةُ يقطعان في الحال.**"""
    assert invites.invitation_id in await _visible(invites.manager)

    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(invites.owner["tenant_id"],
                              invites.owner["user_id"]) as session:
        fresh = await session.get(type(invites.manager_member),
                                  invites.manager_member.id)
        await collaboration.set_access_state(
            session, tenant_id=invites.owner["tenant_id"], member=fresh,
            actor_user_id=invites.owner["user_id"], state=state)

    assert invites.invitation_id not in await _visible(invites.manager), \
        f"مديرٌ {state} ما زال يقرأ دعوةَ البحث"


# ═════════ ٩–١٣ · مَن يكتب ماذا ═════════


@requires_db
@pytest.mark.asyncio
async def test_09_the_recipient_performs_their_own_transition(invites):
    """**٩ · والمدعوُّ يقبل أو يعتذر بنفسه.**"""
    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(invites.token)
    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        invitation = await collaboration.decline_invitation(
            session, tenant_id=invites.recipient["tenant_id"],
            token=invites.token, declining_user_id=invites.recipient["user_id"])
    assert invitation.state == "declined"


@requires_db
@pytest.mark.asyncio
async def test_10_the_recipient_cannot_rewrite_the_invitation_identity(invites):
    """**١٠ · ولا يُبدّل المدعوُّ هويّةَ الدعوة ليجعلها لبحثٍ آخر أو لغيره.**

    فسياسةُ تعديله حدُّها أنّها دعوتُه — و`WITH CHECK` تُعيد قياسَ ذلك على
    الصفّ الجديد، فنقلُها إلى حسابٍ آخر يُخرجها من حدِّه.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(invites.token)
    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text(f"UPDATE {INVITATIONS} SET invited_user_id = :u "
                     "WHERE id = :i"),
                {"u": str(invites.foreigner["user_id"]),
                 "i": str(invites.invitation_id)})

    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text(f"UPDATE {INVITATIONS} SET project_id = :p WHERE id = :i"),
                {"p": str(invites.other_project_id),
                 "i": str(invites.invitation_id)})


@requires_db
@pytest.mark.asyncio
async def test_11_the_recipient_cannot_revoke(invites):
    """**١١ · والنقضُ ليس بيد المدعوّ** — فلا يُخفي أحدٌ أنّه دُعي.

    وسياسةُ تعديله تُسلّمه الصفَّ، ولا تعرف **أيَّ حالٍ** كتب.
    و`revoke_invitation` في الخدمة **لا تسأل عن سلطةٍ أصلًا** — كان
    الموجّهُ وحده يمنع. فالمنعُ صار في مُشغِّلٍ على القاعدة: من ردّ على
    دعوته يقبل أو يعتذر، ولا ينقض.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(invites.token)
    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text(f"UPDATE {INVITATIONS} SET state = 'revoked', "
                     "    responded_at = now() WHERE id = :i"),
                {"i": str(invites.invitation_id)})
    assert "accept or decline" in str(caught.value), str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_12_a_manager_cannot_accept_for_the_candidate(invites):
    """**١٢ · ولا يقبل المديرُ عن مرشَّحه.**

    والرمزُ في يده — أصدره هو — فالحدُّ ليس الحَوْزَ بل الهويّة.
    """
    from athera_api.db import tenant_session
    from athera_api.errors import AtheraError
    from athera_api.services import collaboration

    async with tenant_session(invites.owner["tenant_id"],
                              invites.owner["user_id"]) as session:
        with pytest.raises(AtheraError):
            await collaboration.accept_invitation(
                session, tenant_id=invites.owner["tenant_id"],
                token=invites.token,
                accepting_user_id=invites.owner["user_id"])


@requires_db
@pytest.mark.asyncio
async def test_13_a_manager_can_revoke(invites):
    """**١٣ · والمديرُ ينقض** — فالتضييقُ لم يُعطّل ما يجب أن يعمل."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(invites.owner["tenant_id"],
                              invites.owner["user_id"]) as session:
        invitation = await collaboration.revoke_invitation(
            session, tenant_id=invites.owner["tenant_id"],
            project_id=invites.project_id, invitation_id=invites.invitation_id,
            actor_user_id=invites.owner["user_id"])
    assert invitation.state == "revoked"


# ═════════ دورةُ حياةِ الدعوة: حالٌ مطلقةٌ لا فرقٌ بين حالَين ═════════
#
# **والعطبُ الذي أُغلق هنا:** كان المُشغِّلُ يُجمّد بعضَ الأعمدة ثمّ يعود
# مبكّرًا متى بقيت الحالُ كما هي — فيمرّ كلُّ ما ليس في قائمة التجميد.
# فيمدّ المدعوُّ مهلةَ نفسِه، أو يكتب `member_id` والحالُ `invited`، ثمّ
# يعتذر فيحمل الصفُّ تلويثَه معه؛ لأنّ الفحصَ كان يقارن **ما تبدّل في
# الانتقال** لا **ما صار عليه الصفّ**.


async def _recipient_writes(invites, assignment: str, params: dict | None = None):
    """كتابةٌ خامّةٌ بجلسة المدعوّ — فما يمنع هو القاعدةُ لا الخدمة."""
    from sqlalchemy import text

    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(invites.token)
    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        await session.execute(
            text(f"UPDATE {INVITATIONS} SET {assignment} WHERE id = :i"),
            {**(params or {}), "i": str(invites.invitation_id)})


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,assignment",
    [
        ("expires_at", "expires_at = expires_at + interval '30 days'"),
        ("invited_display_name", "invited_display_name = 'اسمٌ آخر'"),
        ("proposed_role", "proposed_role = 'principal_investigator'"),
        ("proposed_permissions", "proposed_permissions = '[\"manage_team\"]'::jsonb"),
        ("token_hash", "token_hash = repeat('a', 64)"),
        ("invited_by", "invited_by = invited_user_id"),
        ("created_at", "created_at = now()"),
    ],
)
async def test_the_recipient_cannot_rewrite_the_offer_or_the_deadline(
    invites, label, assignment,
):
    """**ولا يمدّ المدعوُّ مهلةَ نفسِه، ولا يرفع عرضَه.**

    و`expires_at` منها: من يملك تعديلَ صفّه كان يمدّ أجلَه بلا حدّ. ولا
    حاجةَ في المنتج إلى تعديلها بعد الإصدار — دعوةٌ انتهت يُصدَر بدلُها
    صفٌّ جديد، وذاك ما يفعله `invite_member` بالحصاد.
    """
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as caught:
        await _recipient_writes(invites, assignment)
    assert "written once" in str(caught.value), (label, str(caught.value))


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,assignment",
    [
        ("member_id", "member_id = :m"),
        ("accepted_user_id", "accepted_user_id = :m"),
        ("responded_at", "responded_at = now()"),
    ],
)
async def test_a_live_invitation_carries_no_answer(invites, label, assignment):
    """**ودعوةٌ حيّةٌ لا تحمل جوابًا ولا عضويّة — وتُقاس الحالُ مطلقةً.**

    فلو اكتُفي بمقارنة ما تبدّل في الانتقال لَمرّ صفٌّ لُوِّث وهو `invited`
    ثمّ حمل تلويثَه إلى «معتذَرٌ عنه».
    """
    from sqlalchemy.exc import DBAPIError

    params = {"m": str(uuid.uuid4())} if ":m" in assignment else None
    with pytest.raises(DBAPIError) as caught:
        await _recipient_writes(invites, assignment, params)
    message = str(caught.value)
    assert ("carries no answer" in message or "written with its state" in message), (
        label, message)


@requires_db
@pytest.mark.asyncio
async def test_a_settled_invitation_that_was_not_accepted_carries_no_membership(
    invites,
):
    """**ولا معتذَرٌ عنها ولا منقوضةٌ ولا منتهيةٌ تحمل ارتباطَ عضويّة.**

    ويُقاس بمحاولةِ اعتذارٍ يحمل `member_id` في العبارة نفسِها — وهو
    الطريقُ الذي كان يفلت: انتقالٌ صحيحٌ يُهرّب معه حقلًا ملوَّثًا.
    """
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as caught:
        await _recipient_writes(
            invites,
            "state = 'declined', responded_at = now(), member_id = :m",
            {"m": str(uuid.uuid4())})
    assert "carries no membership" in str(caught.value), str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_an_accepted_invitation_must_point_at_its_own_membership(invites):
    """**والعضويّةُ المذكورةُ هي عضويّةُ هذا الحساب في هذا البحث.**

    ولا يكفي مفتاحٌ أجنبيٌّ يقول إنّها موجودة: عضويّةٌ صحيحةٌ في بحثٍ آخر
    أو لحسابٍ آخر تُرَدّ.
    """
    from sqlalchemy import select, text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    # عضويّةٌ حقيقيّةٌ لحسابٍ آخر في البحث نفسِه.
    async with tenant_session(invites.owner["tenant_id"],
                              invites.owner["user_id"]) as session:
        foreign_member = (await session.execute(
            select(ProjectMember.id).where(
                ProjectMember.project_id == invites.project_id,
                ProjectMember.user_id == invites.plain["user_id"]))).scalar_one()

    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(invites.token)
    async with invitation_session(token_hash, invites.recipient["tenant_id"],
                                 invites.recipient["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text(f"UPDATE {INVITATIONS} SET state='accepted', "
                     "  responded_at=now(), accepted_user_id=:a, member_id=:m "
                     "WHERE id=:i"),
                {"a": str(invites.recipient["user_id"]),
                 "m": str(foreign_member), "i": str(invites.invitation_id)})
    assert "same account, project and tenant" in str(caught.value)


# ═════════ ١٤ و١٥ · البنيةُ والانحدار ═════════


@requires_db
@pytest.mark.asyncio
async def test_14_no_hard_delete_path_exists(db_ready):
    """**١٤ · ولا حذفَ صلبًا للدعوات: لا سياسةَ ولا صلاحية.**

    فالنقضُ حالٌ تُكتب لا صفٌّ يُمحى — وأثرُ من دُعي يبقى.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        granted = (await session.execute(text(
            "SELECT has_table_privilege('athera_app', :t, 'DELETE')"),
            {"t": INVITATIONS})).scalar_one()
        commands = set((await session.execute(text(
            "SELECT p.polcmd FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
            "WHERE c.relname = :t"), {"t": INVITATIONS})).scalars().all())
    assert granted is False, "صلاحيةُ حذفٍ قائمةٌ على الدعوات"
    assert "d" not in commands and "*" not in commands, commands


@requires_db
@pytest.mark.asyncio
async def test_15_the_broad_policy_is_gone_and_the_narrow_set_is_in_place(db_ready):
    """**١٥ · وسياسةُ 0028 العريضةُ أُسقطت — لا أُضيف إليها.**

    ويُقاس الاسمُ والعدد: فإضافةٌ بجوارِ العريضة لا تُضيّق شيئًا، وذاك
    بالضبط ما وقع في أوّل محاولة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = dict((await session.execute(text(
            "SELECT p.polname, p.polcmd FROM pg_policy p "
            "JOIN pg_class c ON c.oid = p.polrelid WHERE c.relname = :t"),
            {"t": INVITATIONS})).all())

    assert "project_invitations_tenant_isolation" not in rows, (
        "سياسةُ 0028 العريضةُ ما زالت قائمة — فلا شيءَ ضُيّق")
    assert set(rows) == {
        "project_invitations_recipient_read",
        "project_invitations_manager_read",
        "project_invitations_manager_insert",
        "project_invitations_manager_update",
        "project_invitations_recipient_update",
    }, sorted(rows)
    # ولا سياسةَ شاملةَ الأفعال: كلٌّ بفعله.
    assert "*" not in set(rows.values())
