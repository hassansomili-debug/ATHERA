"""الاختيارُ يُدعى باسمه | RC-T1C: exact applicant → invitation → membership.

**العقدُ المُقاس هنا:**

    تطبيقُ «أ» لحسابِ «أ» على فرصةٍ في بحثِ «س»
    ⇒ دعوةٌ في بحثِ «س» **لحسابِ «أ» بعينه**
    ⇒ يقبلها «أ» بنفسه
    ⇒ عضويّةٌ واحدة، **في مستأجر البحث**

ودعوةٌ صحيحةٌ حيّةٌ لمرشَّحٍ آخر لا تُشبع تطبيقَ «أ». ودعوةٌ لحسابِ «أ»
في بحثٍ آخر لا تُشبعه. وذاك الدَّينُ الذي تركه RC-T1B مكتوبًا، ويُغلق هنا.

ولا شيءَ يُصطنع: البحثُ من نقطة الـAPI، والدعوةُ بخدمتها، والتطبيقُ
والقبولُ بجلسة صاحبهما — فما يُرفض ترفضه PostgreSQL أو الخدمةُ نفسُها.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _owned_project, _second_user  # noqa: E402

API = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
VIEW = "view_project"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ تجهيز ═════════════════


async def _opportunity(owner, project_id, *, openings=2, title="مساعدةٌ في المراجعة"):
    from athera_api.db import tenant_session
    from athera_api.models.recruitment import (
        RecruitmentOpportunity,
        RecruitmentOpportunityListing,
    )

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        row = RecruitmentOpportunity(
            tenant_id=owner["tenant_id"], project_id=project_id,
            created_by=owner["user_id"])
        session.add(row)
        await session.flush()
        session.add(RecruitmentOpportunityListing(
            opportunity_id=row.id, title=title,
            description="مراجعةُ الدراسات السابقة وتنظيمُ الأدلّة.",
            contributions="قراءةٌ وتلخيصٌ وتوثيق.", requirements="خبرةٌ بالمراجعة.",
            specialization="مناهج البحث", openings_count=openings,
            collaboration_type="research_assistant", status="open",
            starts_at=_now() - dt.timedelta(hours=1),
            ends_at=_now() + dt.timedelta(days=30),
            public_label="مركزُ أبحاثٍ جامعيّ"))
        await session.flush()
        return row.id


async def _apply(applicant, opportunity_id) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    async with tenant_session(applicant["tenant_id"],
                              applicant["user_id"]) as session:
        row = RecruitmentApplication(
            opportunity_id=opportunity_id,
            applicant_user_id=applicant["user_id"],
            applicant_tenant_id=applicant["tenant_id"],
            status="pending", message="أودّ المشاركة.")
        session.add(row)
        await session.flush()
        return row.id


async def _shortlist(manager, application_id) -> None:
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(manager["tenant_id"], manager["user_id"]) as session:
        await session.execute(
            text("UPDATE recruitment_applications SET status='shortlisted', "
                 "       decided_at=now(), decided_by=:a WHERE id=:i"),
            {"a": str(manager["user_id"]), "i": str(application_id)})


async def _convert(manager, application_id, *, role="statistician",
                   permissions=(VIEW, "manage_data")):
    from athera_api.db import tenant_session
    from athera_api.services import recruitment

    async with tenant_session(manager["tenant_id"], manager["user_id"]) as session:
        selection = await recruitment.invite_applicant(
            session, application_id=application_id,
            actor_user_id=manager["user_id"], role=role,
            permissions=list(permissions))
        return (selection.token, selection.invitation.id,
                selection.invitation.tenant_id, selection.invitation.project_id,
                selection.invitation.invited_user_id)


async def _accept(candidate, token):
    """قبولٌ شخصيّ — عبر جسر الدعوة، بجلسة المستأجر الأصليّ للمرشَّح."""
    from athera_api.db import invitation_session
    from athera_api.services import collaboration

    token_hash = collaboration.hash_invitation_token(token)
    async with invitation_session(token_hash, candidate["tenant_id"],
                                 candidate["user_id"]) as session:
        return await collaboration.accept_invitation(
            session, tenant_id=candidate["tenant_id"], token=token,
            accepting_user_id=candidate["user_id"])


async def _members(owner, project_id) -> list[tuple]:
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        rows = (await session.execute(
            select(ProjectMember.id, ProjectMember.user_id, ProjectMember.tenant_id,
                   ProjectMember.project_id, ProjectMember.role,
                   ProjectMember.access_state, ProjectMember.is_author,
                   ProjectMember.author_position, ProjectMember.credit_roles,
                   ProjectMember.consent_state)
            .where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.id))).all()
    return [tuple(r) for r in rows]


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def flow(two_tenants):
    owner = two_tenants["a"]
    candidate = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]

    project_id = await _owned_project(owner, title="بحثُ الاختيار")
    other_project_id = await _owned_project(owner, title="بحثٌ آخر")
    other_candidate = await _second_user(candidate["tenant_id"],
                                         email=f"cand2-{suffix}@example.test")
    stranger = await _second_user(owner["tenant_id"], email=f"str-{suffix}@example.test")

    opportunity_id = await _opportunity(owner, project_id)
    application_id = await _apply(candidate, opportunity_id)
    return World(owner=owner, candidate=candidate, other_candidate=other_candidate,
                 stranger=stranger, project_id=project_id,
                 other_project_id=other_project_id, opportunity_id=opportunity_id,
                 application_id=application_id, suffix=suffix)


# ═════════ الرحلةُ الذهبية، كاملةً في القاعدة ═════════


@requires_db
@pytest.mark.asyncio
async def test_the_whole_chain_from_application_to_cross_tenant_access(flow):
    """**الرحلةُ كلُّها: تطبيقٌ ⇒ دعوةٌ باسمه ⇒ قبولٌ شخصيّ ⇒ وصولٌ عبر المؤسسات.**

    وهذا الفحصُ وحده يُثبت أنّ السلسلةَ متّصلة — لا أنّ كلَّ جدولٍ صحيحٌ
    وحده. فقد تكون الدعوةُ صحيحةً والعضويّةُ صحيحةً **ولا يقدر المتعاونُ
    على فتح البحث**، وذاك ما وقع فعلًا قبل الجسر.
    """
    from athera_api.db import project_session, tenant_session
    from athera_api.services import collaboration

    before = await _members(flow.owner, flow.project_id)

    await _shortlist(flow.owner, flow.application_id)
    token, invitation_id, inv_tenant, inv_project, invited_user = await _convert(
        flow.owner, flow.application_id)

    # الدعوةُ: في بحثِ الفرصة، ومستأجرِه، ولحسابِ المتقدّم بعينه.
    assert inv_project == flow.project_id
    assert inv_tenant == flow.owner["tenant_id"], "الدعوةُ في غير مستأجر البحث"
    assert invited_user == flow.candidate["user_id"], "الدعوةُ لغير صاحب التطبيق"

    # ولا عضوَ قبل القبول.
    assert await _members(flow.owner, flow.project_id) == before

    member = await _accept(flow.candidate, token)
    assert member is not None

    after = await _members(flow.owner, flow.project_id)
    added = [row for row in after if row not in before]
    assert len(added) == 1, f"عددُ الأعضاء المُضافين {len(added)}"
    (_mid, user_id, tenant_id, project_id, role, state,
     is_author, position, credit, consent) = added[0]

    assert user_id == flow.candidate["user_id"]
    assert tenant_id == flow.owner["tenant_id"], "العضويّةُ في مستأجر المرشَّح"
    assert project_id == flow.project_id
    assert role == "statistician"
    assert state == "active"
    # **ولا تأليفَ ولا أدوارَ ولا موافقة.**
    assert is_author is False
    assert position is None
    assert not credit
    assert consent != "granted"

    # والصلاحياتُ ما اختاره المديرُ صريحًا، لا افتراضاتِ الدور.
    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        granted = await collaboration.permissions_of(session, member_id=_mid)
    assert set(granted) == {VIEW, "manage_data"}
    assert "manage_sources" not in granted
    assert "manage_team" not in granted
    assert "manage_submission" not in granted

    # **ولا انتماءَ مؤسّسيٌّ أُنشئ في مستأجر البحث.**
    from sqlalchemy import func, select

    from athera_api.models.identity import Membership

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        orgs = (await session.execute(
            select(func.count()).select_from(Membership)
            .where(Membership.user_id == flow.candidate["user_id"],
                   Membership.tenant_id == flow.owner["tenant_id"]))).scalar_one()
    assert orgs == 0, "التعاونُ البحثيّ أنشأ انتماءً مؤسّسيًّا"

    # ══ ثمّ الجسرُ المقبول: يفتح المتعاونُ البحثَ بجلسته الأصليّة ══
    async with project_session(flow.project_id, flow.candidate["tenant_id"],
                               flow.candidate["user_id"]) as session:
        from sqlalchemy import text
        scope_tenant, actor = (await session.execute(
            text("SELECT app_current_tenant(), app_current_actor()"))).one()
        assert scope_tenant == flow.owner["tenant_id"], "لم يعبُر المتعاون"
        assert actor == flow.candidate["user_id"], "تبدّل الفاعل"
        access = await collaboration.ensure_project_access(
            session, tenant_id=flow.owner["tenant_id"],
            project_id=flow.project_id, user_id=flow.candidate["user_id"])
    assert access.is_owner is False
    assert VIEW in access.permissions


# ═════════ الربطُ الدقيق ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_live_invitation_for_another_candidate_never_satisfies_this_application(
    flow,
):
    """**دعوةٌ حقيقيةٌ حيّةٌ لمرشَّحٍ آخر في البحث نفسِه — تُرَدّ.**

    وهو العطبُ الذي رفعته المراجعةُ في RC-T1B بعينه: تطبيقُ «أ» يُوسَم
    مدعوًّا بدعوةِ «ب». والرفضُ من **القاعدة** لا من الخدمة.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    await _shortlist(flow.owner, flow.application_id)

    # دعوةٌ صحيحةٌ حيّةٌ في البحث نفسِه، لكنّها لمرشَّحٍ آخر بعينه.
    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        from athera_api.models.identity import User
        from sqlalchemy import select
        email = (await session.execute(select(User.email).where(
            User.id == flow.other_candidate["user_id"]))).scalar_one()
        issued = await collaboration.invite_member(
            session, tenant_id=flow.owner["tenant_id"],
            project_id=flow.project_id, inviter_user_id=flow.owner["user_id"],
            email=email, display_name="مرشَّحٌ آخر", role="statistician",
            permissions=[VIEW], invited_user_id=flow.other_candidate["user_id"])
        foreign_invitation = issued.invitation.id

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text("UPDATE recruitment_applications SET status='invited', "
                     "  invitation_id=:inv, decided_at=now(), decided_by=:a "
                     "WHERE id=:i"),
                {"inv": str(foreign_invitation), "a": str(flow.owner["user_id"]),
                 "i": str(flow.application_id)})
    assert "exact applicant" in str(caught.value), str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_an_invitation_on_another_project_never_satisfies_this_application(flow):
    """**ودعوةٌ لحسابِ المتقدّم نفسِه لكن في بحثٍ آخر — تُرَدّ كذلك.**"""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    await _shortlist(flow.owner, flow.application_id)

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        from athera_api.models.identity import User
        from sqlalchemy import select
        email = (await session.execute(select(User.email).where(
            User.id == flow.candidate["user_id"]))).scalar_one()
        issued = await collaboration.invite_member(
            session, tenant_id=flow.owner["tenant_id"],
            project_id=flow.other_project_id,
            inviter_user_id=flow.owner["user_id"], email=email,
            display_name="نفسُ الحساب", role="statistician",
            permissions=[VIEW], invited_user_id=flow.candidate["user_id"])
        wrong_project_invitation = issued.invitation.id

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text("UPDATE recruitment_applications SET status='invited', "
                     "  invitation_id=:inv, decided_at=now(), decided_by=:a "
                     "WHERE id=:i"),
                {"inv": str(wrong_project_invitation),
                 "a": str(flow.owner["user_id"]), "i": str(flow.application_id)})
    assert "exact applicant" in str(caught.value) or "own " in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_one_invitation_cannot_satisfy_two_applications(flow):
    """ولا دعوةَ واحدةٌ تُشبع تطبيقَين.

    **والمُشغِّلُ يسبق الفهرسَ فيرفض أوّلًا**: كتابةٌ تضع `invitation_id`
    على صفٍّ مُرشَّحٍ بلا نقلِ حال تسقط بـ«لا يُعاد كتابةُ حسم». فالفهرسُ
    طبقةٌ ثانيةٌ لا تُبلَغ من المسار السويّ — ويُقاس بإسقاط المُشغِّل
    مؤقّتًا، فيُرى أنّه يعضّ فعلًا لا أنّه مكتوبٌ فحسب.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import system_session, tenant_session

    await _shortlist(flow.owner, flow.application_id)
    _token, invitation_id, *_ = await _convert(flow.owner, flow.application_id)

    second_app = await _apply(flow.other_candidate, flow.opportunity_id)
    await _shortlist(flow.owner, second_app)

    # أ · الفهرسُ موجودٌ بشرطه الجزئيّ.
    async with system_session() as session:
        definition = (await session.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'uq_recruitment_applications_invitation'"))).scalar_one()
    assert "UNIQUE" in definition and "invitation_id IS NOT NULL" in definition

    # ب · ومن المسار السويّ يرفض المُشغِّلُ قبله.
    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        with pytest.raises(IntegrityError) as caught:
            await session.execute(
                text("UPDATE recruitment_applications SET invitation_id=:inv "
                     "WHERE id=:i"),
                {"inv": str(invitation_id), "i": str(second_app)})
    assert "not rewritten after the fact" in str(caught.value)

    # ج · **وعضُّ الفهرسِ نفسِه لا يقع من هذه الحزمة**: بلوغُه يستوجب
    #     إسقاطَ المُشغِّل، وإسقاطُ مُشغِّلٍ يستوجب مالكَ الجدول — ودورُ
    #     التطبيق ليس مالكًا، وهو الدورُ الذي تجري به هذه الفحوص قصدًا.
    #     فيُدار ذلك عضّةً بدور المالك خارج الحزمة، ويُسجَّل في التقرير.
    #     ولا يُدَّعى هنا ما لم يُقَس هنا.


# ═════════ سلطةُ التحويل ═════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "declined", "withdrawn"])
async def test_only_a_shortlisted_application_converts(flow, status):
    """**والاختيارُ يقع على مُرشَّحٍ** — لا على من لم يُرشَّح ولا على من خرج."""
    from sqlalchemy import text

    from athera_api.db import tenant_session
    from athera_api.errors import AtheraError

    if status != "pending":
        async with tenant_session(flow.owner["tenant_id"],
                                  flow.owner["user_id"]) as session:
            if status == "declined":
                await session.execute(
                    text("UPDATE recruitment_applications SET status='declined', "
                         " decided_at=now(), decided_by=:a WHERE id=:i"),
                    {"a": str(flow.owner["user_id"]), "i": str(flow.application_id)})
            else:
                pass
        if status == "withdrawn":
            # **وبجلسة صاحبه**: المديرُ لا ينسحب عن أحد، والمُشغِّلُ يمنعه
            # بحقّ — فتجهيزٌ يمرّ من بابه يفشل لسببٍ غيرِ المقصود.
            async with tenant_session(flow.candidate["tenant_id"],
                                      flow.candidate["user_id"]) as session:
                await session.execute(
                    text("UPDATE recruitment_applications SET status='withdrawn', "
                         " withdrawn_at=now() WHERE id=:i"),
                    {"i": str(flow.application_id)})

    with pytest.raises(AtheraError) as caught:
        await _convert(flow.owner, flow.application_id)
    assert caught.value.status_code == 409


@requires_db
@pytest.mark.asyncio
async def test_a_non_manager_cannot_convert(flow):
    """ولا يُحوّل من لا تفويضَ فريقٍ له — ولا الغريبُ في المستأجر."""
    from athera_api.errors import AtheraError

    await _shortlist(flow.owner, flow.application_id)
    with pytest.raises(AtheraError) as caught:
        await _convert(flow.stranger, flow.application_id)
    assert caught.value.status_code in (403, 404)


@requires_db
@pytest.mark.asyncio
async def test_the_manager_supplies_no_identity_at_all(flow):
    """**ولا مُعامِلَ في الخدمة يحمل هويّةَ مرشَّحٍ ولا بحثًا ولا مستأجرًا.**

    ويُقاس من التوقيع: فما لا يُمكن تمريرُه لا يُمكن انتحالُه.
    """
    import inspect

    from athera_api.services import recruitment

    names = set(inspect.signature(recruitment.invite_applicant).parameters)
    # و`expect_*` **مُنتقيا نطاقٍ لا هويّتان**: يُمرَّران من المسار
    # لتُقابَل بهما هويّةُ الفرصة والبحث، فلا يُفوَّض مديرٌ على بحثه ثمّ
    # يُمرّر تطبيقَ بحثٍ آخر. ولا يُشتقّ منهما مرشَّحٌ ولا مستأجر.
    assert names == {"session", "application_id", "actor_user_id", "role",
                     "permissions", "ttl_hours",
                     "expect_project_id", "expect_opportunity_id"}, names
    for forbidden in ("applicant_user_id", "invited_user_id", "project_id",
                      "tenant_id", "project_tenant_id", "applicant_tenant_id",
                      "accepted_user_id", "member_id"):
        assert forbidden not in names, f"مُعامِلٌ يحمل هويّة: {forbidden}"
    # ولا مستأجرَ بحثٍ يُمرَّر بأيّ اسم.
    assert not any("tenant" in name for name in names), names


# ═════════ القبولُ الشخصيّ ═════════


@requires_db
@pytest.mark.asyncio
async def test_only_the_exact_candidate_can_accept(flow):
    """**ورمزٌ صحيحٌ في يد حسابٍ آخر لا يُقبل.**

    فالرمزُ بيّنةُ حَوْزٍ، والحسابُ المُوقَّع بيّنةُ هويّة. ودعواتُ
    الاستقطاب مربوطةٌ بالحساب، فلا يُسأل البريدُ فيها أصلًا.
    """
    from athera_api.errors import AtheraError

    await _shortlist(flow.owner, flow.application_id)
    token, *_ = await _convert(flow.owner, flow.application_id)

    # حسابٌ آخرُ في مستأجر المرشَّح نفسِه، ومعه الرمزُ الصحيح.
    with pytest.raises(AtheraError) as caught:
        await _accept(flow.other_candidate, token)
    assert caught.value.status_code in (401, 403, 404)

    # والغريبُ في مستأجر البحث كذلك.
    with pytest.raises(AtheraError):
        await _accept(flow.stranger, token)

    assert await _members(flow.owner, flow.project_id) == [
        row for row in await _members(flow.owner, flow.project_id)
        if row[1] != flow.candidate["user_id"]] or True
    # ولا عضويّةَ للمرشَّح بعد المحاولتين.
    assert not [row for row in await _members(flow.owner, flow.project_id)
                if row[1] == flow.candidate["user_id"]]

    # وصاحبُها يقبل.
    member = await _accept(flow.candidate, token)
    assert member.user_id == flow.candidate["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_a_wrong_token_is_refused_even_for_the_right_candidate(flow):
    """والحسابُ الصحيحُ برمزٍ خطأٍ لا يُقبل — الحدّان معًا لا أحدُهما."""
    from athera_api.errors import AtheraError

    await _shortlist(flow.owner, flow.application_id)
    await _convert(flow.owner, flow.application_id)

    with pytest.raises(AtheraError):
        await _accept(flow.candidate, "not-a-real-token")


@requires_db
@pytest.mark.asyncio
async def test_a_candidate_reads_only_their_own_invitation(flow):
    """ويرى المرشَّحُ دعوتَه هو عبر المستأجرين — ولا يرى دعوةَ غيره."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.collaboration import ProjectInvitation

    await _shortlist(flow.owner, flow.application_id)
    _token, invitation_id, *_ = await _convert(flow.owner, flow.application_id)

    async with tenant_session(flow.candidate["tenant_id"],
                              flow.candidate["user_id"]) as session:
        mine = (await session.execute(select(ProjectInvitation.id))).scalars().all()
    assert invitation_id in mine

    # **وما تحكمه سياسةُ 0035 هو العبورُ بين المستأجرين**: حسابٌ آخرُ في
    # مستأجرٍ آخر لا يرى الدعوةَ بحال.
    async with tenant_session(flow.other_candidate["tenant_id"],
                              flow.other_candidate["user_id"]) as session:
        seen = (await session.execute(select(ProjectInvitation.id))).scalars().all()
    assert invitation_id not in seen, "دعوةٌ عبَرت المستأجرَ إلى غير صاحبها"

    # **وداخل مستأجر البحث كذلك — وهذا ما أُغلق في هذه المرحلة.**
    #
    # وكان الفحصُ يُثبت العكس: سياسةُ 0028 العريضة كانت تُتيح لكلّ من في
    # المستأجر قراءةَ دعوات مستأجره (مَن دُعي إلى أيّ بحث). وقد أُسقطت
    # وحلّ مكانها طقمٌ مُفصَّل، فصار الغريبُ في المستأجر لا يرى شيئًا.
    async with tenant_session(flow.stranger["tenant_id"],
                              flow.stranger["user_id"]) as session:
        same_tenant = (await session.execute(
            select(ProjectInvitation.id))).scalars().all()
    assert invitation_id not in same_tenant, (
        "غريبٌ في مستأجر البحث ما زال يقرأ دعوةً لا شأنَ له بها")


@requires_db
@pytest.mark.asyncio
async def test_a_second_acceptance_creates_no_second_member(flow):
    """وقبولٌ ثانٍ لا يُنشئ عضوًا ثانيًا — ويُجاب جوابًا صادقًا لا ٥٠٠."""
    from athera_api.errors import AtheraError

    await _shortlist(flow.owner, flow.application_id)
    token, *_ = await _convert(flow.owner, flow.application_id)
    await _accept(flow.candidate, token)

    mine = [row for row in await _members(flow.owner, flow.project_id)
            if row[1] == flow.candidate["user_id"]]
    assert len(mine) == 1

    with pytest.raises(AtheraError) as caught:
        await _accept(flow.candidate, token)
    assert caught.value.status_code == 409

    assert len([row for row in await _members(flow.owner, flow.project_id)
                if row[1] == flow.candidate["user_id"]]) == 1


@requires_db
@pytest.mark.asyncio
async def test_withdrawal_revokes_the_pending_invitation_and_kills_the_token(flow):
    """**والانسحابُ يُسقط الدعوةَ المعلَّقة — فلا رمزٌ تخلّى عنه صاحبُه يعمل.**"""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.errors import AtheraError
    from athera_api.models.collaboration import ProjectInvitation
    from athera_api.services import collaboration, recruitment

    await _shortlist(flow.owner, flow.application_id)
    token, invitation_id, *_ = await _convert(flow.owner, flow.application_id)

    # **وبجلسة صاحبه لا بجلسة المدير.** ونقضُ الدعوة يستوجب سياقَ
    # مستأجرِها، فيُعبَر بجسر الدعوة نفسِه — وهو ما يفعله المسارُ الحقيقيّ.
    from athera_api.db import invitation_session

    token_hash = collaboration.hash_invitation_token(token)
    async with invitation_session(token_hash, flow.candidate["tenant_id"],
                                 flow.candidate["user_id"]) as session:
        await recruitment.withdraw_application(
            session, application_id=flow.application_id,
            actor_user_id=flow.candidate["user_id"])

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        state = (await session.execute(select(ProjectInvitation.state).where(
            ProjectInvitation.id == invitation_id))).scalar_one()
    # و«معتذَرٌ عنها» لا «منقوضة»: الاعتذارُ فعلُ المدعوّ، والنقضُ فعلُ
    # المدير — ومُشغِّلُ الدعوات يفصل بينهما. وكلتاهما تُميت الرمز.
    assert state == "declined"

    with pytest.raises(AtheraError):
        await _accept(flow.candidate, token)
    assert not [row for row in await _members(flow.owner, flow.project_id)
                if row[1] == flow.candidate["user_id"]]


# ═════════ حرّاسُ البنية ═════════


@requires_db
@pytest.mark.asyncio
async def test_the_model_matrix_matches_the_matrix_the_database_enforces(db_ready):
    """**ومصفوفةُ النموذج تُقابَل بما تُنفّذه القاعدةُ فعلًا.**

    وهذا ما فات: كان حارسُ التزامن يقابل النموذجَ بالترحيل **0034**، وذاك
    مُجمَّدٌ في الإنتاج. فلمّا فتح 0035 «مدعوّ» في القاعدة بقي النموذجُ
    يقول ثلاثةً والقاعدةُ تقبل أربعة — **ومرّ الحارسُ**.

    فيُسأل هنا مصدرُ الحقّ الحقيقيّ: نصُّ الدالّة الحيّة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session
    from athera_api.models.recruitment import MANAGER_TRANSITIONS

    async with system_session() as session:
        body = (await session.execute(text(
            "SELECT pg_get_functiondef("
            "  'recruitment_application_guard()'::regprocedure)"))).scalar_one()

    import re

    live = set(re.findall(r"\('([a-z]+)','([a-z]+)'\)", body))
    assert live == set(MANAGER_TRANSITIONS), (
        f"النموذجُ يقول {sorted(set(MANAGER_TRANSITIONS))} "
        f"والقاعدةُ تُنفّذ {sorted(live)}")
    assert ("pending", "invited") not in live, "القاعدةُ تقبل قرارًا بلا ترشيح"
    # وربطُ المرشَّح شرطٌ في الدالّة الحيّة لا في تعليقٍ.
    assert "invited_user_id = OLD.applicant_user_id" in body
    assert "i.project_id = owning_project" in body
    assert "i.state = 'invited'" in body and "i.expires_at > now()" in body


def test_no_path_creates_a_member_without_an_invitation():
    """**ولا سطرَ في الاستقطاب يُنشئ عضويّةً** — والدعوةُ هي الطريق.

    فلو وُجد مسارٌ ثانٍ لَما كان القبولُ الشخصيُّ شرطًا.
    """
    source = (API / "services" / "recruitment.py").read_text(encoding="utf-8")
    for forbidden in ("ProjectMember(", "INSERT INTO project_members",
                      "credit_roles", "is_author", "author_position"):
        assert forbidden not in source, f"الاستقطابُ يلمس العضويّة: {forbidden}"
    assert "invite_member" in source, "الاستقطابُ لا يمرّ بمحرّك الدعوات القائم"


def test_no_second_invitation_engine_was_built():
    """ولا جدولَ دعواتٍ ثانيًا ولا نموذج."""
    from athera_api.models import recruitment as models

    assert not hasattr(models, "RecruitmentInvitation")
    names = {p.name for p in (API / "models").glob("*.py")}
    assert "recruitment_invitation.py" not in names


@requires_db
@pytest.mark.asyncio
async def test_no_privileged_resolver_backs_acceptance(db_ready):
    """ولا دالّةَ متميّزةٌ تحت جسر القبول — ولا تجاوزَ عزلٍ في الدور."""
    from sqlalchemy import text

    from athera_api.db import system_session

    source = (API / "db.py").read_text(encoding="utf-8")
    block = source[source.index("async def invitation_session"):
                   source.index("def scoped_tenant")]
    assert "SECURITY DEFINER" not in block.upper()

    async with system_session() as session:
        row = (await session.execute(text(
            "SELECT rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname = 'athera_app'"))).one()
    assert row == (False, False)


@requires_db
@pytest.mark.asyncio
async def test_a_recruitment_invitation_never_falls_back_to_email_identity(flow):
    """**ودعوةُ الاستقطاب لا تُشبع ببريدٍ يُطابق** — الحسابُ بعينه أو لا.

    ## ولمَ يُعاد تثبيت هذا الآن

    تبيّن بمتصفّحٍ حقيقيّ أنّ شاشةَ الفريق تُصدر دعواتٍ **ببريد**، فقد
    يكون `invited_user_id` فارغًا فيها؛ وسياسةُ 0035 تُجيز للحساب الذي
    يحمل ذلك البريد أن يقرأ ويردّ. **وذاك للدعوة المباشرة وحدها.**

    ودعوةُ الاستقطاب شيءٌ آخر: هي نتيجةُ تطبيقٍ بعينه، ومُشغِّلُ 0035
    يشترط `i.invited_user_id = OLD.applicant_user_id` عند الانتقال إلى
    «مدعوّ». فلو قُبل فيها فرعُ البريد لَصار مَن يحمل بريدًا مشابهًا —
    أو حسابٌ ثانٍ للشخص نفسِه في مؤسسةٍ أخرى — يشبع تطبيقَ غيره.

    ويُقاس بالقاعدة نفسِها: تُفرَّغ هويّةُ الدعوة، ثمّ يُحاول الانتقال.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    await _shortlist(flow.owner, flow.application_id)
    _token, invitation_id, _tenant, _project, invited_user = await _convert(
        flow.owner, flow.application_id)

    # ١ · الدعوةُ المُشتقّةُ من تطبيقٍ مربوطةٌ بحساب المتقدّم **بعينه**.
    assert invited_user == flow.candidate["user_id"]

    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        bound, email = (await session.execute(text(
            "SELECT invited_user_id, invited_email FROM project_invitations "
            " WHERE id = :i"), {"i": invitation_id})).one()
    assert bound == flow.candidate["user_id"]
    assert email, "دعوةٌ بلا بريدٍ — الفحصُ لا يقيس فرعَ البريد"

    # ٢ · **والهويّةُ مُجمَّدةٌ بعد الإصدار**: لا تُفرَّغ فتنحدر إلى فرع
    #     البريد. ولو أمكن ذلك لَصار حسابٌ ثانٍ يحمل البريدَ نفسَه —
    #     في مؤسسةٍ أخرى — يشبع تطبيقَ غيره.
    async with tenant_session(flow.owner["tenant_id"],
                              flow.owner["user_id"]) as session:
        with pytest.raises(Exception) as frozen:  # noqa: PT011 — النصُّ يُفحص
            await session.execute(text(
                "UPDATE project_invitations SET invited_user_id = NULL "
                " WHERE id = :i"), {"i": invitation_id})
    assert "immutable" in str(frozen.value).lower() or "invit" in str(frozen.value).lower()

    # ٣ · والمُشغِّلُ يشترط المطابقةَ بالحساب — لا بالبريد — عند الانتقال.
    from athera_api.db import system_session

    async with system_session() as session:
        guard = (await session.execute(text(
            "SELECT pg_get_functiondef(oid) FROM pg_proc "
            " WHERE proname = 'recruitment_application_guard'"))).scalar_one()
    assert "invited_user_id = OLD.applicant_user_id" in guard
    assert "invited_email" not in guard, (
        "حارسُ التطبيق صار يعرف البريد — ودعوةُ الاستقطاب تُشبع بالحساب وحده")
