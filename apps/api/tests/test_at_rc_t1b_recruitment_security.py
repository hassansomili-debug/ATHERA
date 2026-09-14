"""الاستقطابُ عبر المؤسسات — وعزلُ البحث باقٍ | RC-T1B recruitment security.

**الحدُّ الذي يُكسَر هنا، وما يمنعه من أن يصير ثقبًا.**

كلُّ صفٍّ قبل هذا الترحيل يُقرأ داخل مستأجرٍ واحد. وقرارُ المنتج يستوجب أن
يكتشف باحثٌ في مؤسسةٍ فرصةَ تعاونٍ أعلنها بحثٌ في مؤسسةٍ أخرى وأن يتقدّم
إليها. فالحدُّ يُكسَر في القاعدة وبأضيق ما يكفي، **وهذه الحزمةُ هي ما
يُثبت أنّ «أضيق ما يكفي» ليس دعوى**.

## ولا شيءَ هنا يُصطنع

لا `mock` لسياسةٍ، ولا جلسةَ تجاوز، ولا صفَّ يُدسّ بيدٍ حيث يمرّ المنتجُ
بمسار. البحثُ يُنشأ من نقطةِ الـAPI الحقيقية، والدعوةُ تُصدر وتُقبل
بخدمتها، والفرصةُ والتطبيقُ يُكتبان بجلسةِ صاحبهما — فما يُرفض هنا ترفضه
PostgreSQL نفسُها، وما يُقبل قبلته.

**ولا `BYPASSRLS` في هذه الحزمة** — ويُثبَت ذلك فحصًا صريحًا، لأنّ حزمةً
تجري بدورٍ متجاوزٍ تُثبت العزلَ على قاعدةٍ لا تُرشّح.

## ومصفوفةُ التهديد مرقَّمةٌ كما وردت

أقسامُ الملفّ تحمل أرقامَ البنود من ١ إلى ٢٢، فما سقط منها يُعرف باسمه لا
بالعدّ.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import uuid

import pytest

from tests.conftest import requires_db

# **وتجهيزاتُ RC-T1A تُستورَد ولا تُنسخ.** «بحثٌ له نسبُ ملكيّةٍ حقيقيّ»
# تعريفٌ واحد؛ ونسخةٌ ثانية منه هنا كانت ستُفلت من كلّ تعديلٍ يقع هناك،
# فتُثبت هذه الحزمةُ الإدارةَ على بحثٍ لم يُنشأ كما تُنشأ الأبحاث.
from tests.test_at_rc_t1a_project_access import (  # noqa: E402
    _invite_and_accept,
    _owned_project,
    _second_user,
)

API = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
REPO = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS = REPO / "infra" / "db" / "migrations" / "versions"
MIGRATION = MIGRATIONS / "0034_recruitment_security_foundation.py"

OPPORTUNITIES = "recruitment_opportunities"
APPLICATIONS = "recruitment_applications"
PUBLIC_VIEW = "recruitment_opportunities_public"


def _hours(n: int) -> dt.timedelta:
    return dt.timedelta(hours=n)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ التجهيز: عالَمٌ صغير بمستأجرَين ═════════════════


async def _make_opportunity(
    slot, project_id, *, status="open", starts_at=..., ends_at=...,
    deleted_at=None, title="مساعدةٌ في التحليل الإحصائي",
) -> uuid.UUID:
    """فرصةٌ تُكتب **بجلسة مديرها** — فالإدراجُ نفسُه برهانُ سلطته."""
    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentOpportunity

    if starts_at is ...:
        starts_at = _now() - _hours(24) if status != "draft" else None
    if ends_at is ...:
        ends_at = _now() + _hours(24 * 30) if starts_at is not None else None

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        row = RecruitmentOpportunity(
            tenant_id=slot["tenant_id"], project_id=project_id,
            title=title, description="مراجعةُ مخرجاتِ نموذجٍ خطّيّ وتوثيقُها.",
            contributions="تشغيلُ التحليل وكتابةُ قسم النتائج.",
            requirements="خبرةٌ بـR أو Python.",
            specialization="القياس والإحصاء", openings_count=1,
            collaboration_type="data_analysis", status=status,
            starts_at=starts_at, ends_at=ends_at, deleted_at=deleted_at,
            public_label="مركزُ أبحاثٍ جامعيّ", created_by=slot["user_id"])
        session.add(row)
        await session.flush()
        return row.id


async def _apply(slot, opportunity_id, *, applicant=None) -> uuid.UUID:
    """تقدُّمٌ يُكتب بجلسة المتقدّم — و`applicant` يسمح بمحاولة التزوير."""
    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        row = RecruitmentApplication(
            opportunity_id=opportunity_id,
            applicant_user_id=(applicant or slot)["user_id"],
            applicant_tenant_id=slot["tenant_id"],
            status="pending", message="أودّ المشاركةَ في هذا التحليل.")
        session.add(row)
        await session.flush()
        return row.id


async def _apply_raw(slot, opportunity_id, *, applicant) -> None:
    """إدراجٌ خامٌّ **بلا `RETURNING`** — ليُقاس `WITH CHECK` وحده.

    **ولمَ لا يكفي مسارُ الـORM هنا.** SQLAlchemy تُلحق `RETURNING` بكلّ
    إدراجٍ فيه قيمةٌ تُولَّد في الخادم (`created_at`/`updated_at`)، و
    PostgreSQL تُخضع `RETURNING` لسياسات **القراءة**. فصفٌّ باسم غيرِ
    الفاعل كان يُرفض بسياسة القراءة قبل أن يُسأل عنه `WITH CHECK` —
    ‏**وقد اكتُشف هذا بعضّ الحارس**: أُبطل شرطُ الفاعل في سياسة الإدراج
    فبقي الفحصُ ناجحًا، أي أنّه كان يُثبت بندًا غير الذي يُسمّيه.

    فيُكتب الصفُّ خامًّا بكلّ أعمدته: لا `RETURNING`، ولا سياسةَ قراءةٍ
    تُستدعى — و`WITH CHECK` هي الطبقةُ الوحيدةُ الباقية.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        await session.execute(
            text(f"INSERT INTO {APPLICATIONS} "
                 "(id, opportunity_id, applicant_user_id, applicant_tenant_id, "
                 " status, message, created_at, updated_at) "
                 "VALUES (:i, :o, :u, :t, 'pending', :m, now(), now())"),
            {"i": str(uuid.uuid4()), "o": str(opportunity_id),
             "u": str(applicant["user_id"]), "t": str(slot["tenant_id"]),
             "m": "إدراجٌ خامّ"})


async def _visible_opportunity_ids(slot) -> set[uuid.UUID]:
    """ما تراه جلسةُ هذا الفاعل من الجدول الأصل — لا ما تعرضه الشاشة."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentOpportunity

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        rows = (await session.execute(
            select(RecruitmentOpportunity.id))).scalars().all()
    return set(rows)


async def _discoverable_ids(slot) -> set[uuid.UUID]:
    """ما يعرضه الإسقاطُ الآمن."""
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        rows = (await session.execute(
            text(f"SELECT id FROM {PUBLIC_VIEW}"))).scalars().all()
    return {uuid.UUID(str(r)) for r in rows}


async def _visible_application_ids(slot) -> set[uuid.UUID]:
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        rows = (await session.execute(
            select(RecruitmentApplication.id))).scalars().all()
    return set(rows)


async def _manages(slot, project_id) -> bool:
    """جوابُ القاعدة نفسِها عن سؤال الإدارة، بجلسة هذا الفاعل."""
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        return (await session.execute(
            text("SELECT app_manages_project(:p)"), {"p": str(project_id)})).scalar_one()


class World:
    """مستأجران، بحثٌ في الثاني، وفرصةٌ مفتوحةٌ يتقدّم إليها من في الأوّل."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def world(two_tenants):
    """العالَمُ الأصغرُ الذي تكفي به المصفوفةُ كلُّها.

    ‏**والمستأجرُ «ب» صاحبُ البحث، و«أ» موطنُ المتقدّمين** — فالاكتشافُ
    والتقدّمُ يجريان من خارج المستأجر لا داخله، وهو الحدُّ المقصود.
    """
    owner = two_tenants["b"]
    applicant = two_tenants["a"]

    suffix = uuid.uuid4().hex[:8]
    project_id = await _owned_project(owner, title="بحثُ الاستقطاب")
    other_project_id = await _owned_project(owner, title="بحثٌ آخرُ للمستأجر نفسه")

    manager = await _second_user(owner["tenant_id"], email=f"mgr-{suffix}@example.test")
    plain = await _second_user(owner["tenant_id"], email=f"plain-{suffix}@example.test")
    stranger = await _second_user(owner["tenant_id"], email=f"str-{suffix}@example.test")
    other_manager = await _second_user(owner["tenant_id"],
                                       email=f"omgr-{suffix}@example.test")
    applicant2 = await _second_user(applicant["tenant_id"],
                                    email=f"app2-{suffix}@example.test")

    manager_member = await _invite_and_accept(
        owner, manager, project_id, permissions=["view_project", "manage_team"])
    # **ودورٌ باسمه لا يُفوّض**: باحثٌ رئيسٌ بلا `manage_team` صريحة.
    plain_member = await _invite_and_accept(
        owner, plain, project_id, permissions=["view_project"])
    await _invite_and_accept(
        owner, other_manager, other_project_id,
        permissions=["view_project", "manage_team"])

    return World(
        owner=owner, applicant=applicant, applicant2=applicant2,
        manager=manager, manager_member=manager_member,
        plain=plain, plain_member=plain_member,
        stranger=stranger, other_manager=other_manager,
        project_id=project_id, other_project_id=other_project_id,
    )


async def _set_role(world, member, role: str) -> None:
    """يُغيَّر اسمُ الدور وحده — والصلاحياتُ لا تُمسّ."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        fresh = await session.get(type(member), member.id)
        await collaboration.change_role(
            session, tenant_id=world.owner["tenant_id"], member=fresh,
            actor_user_id=world.owner["user_id"], role=role)


async def _set_access(world, member, state: str) -> None:
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(world.owner["tenant_id"], world.owner["user_id"]) as session:
        fresh = await session.get(type(member), member.id)
        await collaboration.set_access_state(
            session, tenant_id=world.owner["tenant_id"], member=fresh,
            actor_user_id=world.owner["user_id"], state=state)


# ═════════ ١–٣ · الاكتشافُ عالميّ، والحالاتُ الخاصّةُ لا تُكتشف ═════════


@requires_db
@pytest.mark.asyncio
async def test_01_an_open_opportunity_crosses_the_tenant_boundary(world):
    """**١ · باحثٌ في «أ» يرى فرصةً أعلنها بحثٌ في «ب».**

    وهو الحدُّ المقصودُ كسرُه. ولو سقط هذا الفحص فالمنتجُ لم يُبنَ.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    assert opportunity_id in await _visible_opportunity_ids(world.applicant)
    assert opportunity_id in await _discoverable_ids(world.applicant)


@requires_db
@pytest.mark.asyncio
async def test_02_03_only_the_open_window_is_discoverable(world):
    """**٢ و٣ · المسوّدةُ والمجدولةُ والمغلقةُ والمحذوفةُ لا تُكتشف.**

    وأربعُ حالاتٍ لا اثنتان: **والنافذةُ المنتهيةُ خامسة**. ففرصةٌ حالُها
    `open` وقد انقضى أجلُها كانت ستبقى مُكتشَفةً لو قِيس الحالُ وحده —
    وباحثٌ يتقدّم إلى بابٍ أُغلق منذ شهر.
    """
    hidden = {
        "draft": await _make_opportunity(
            world.owner, world.project_id, status="draft",
            starts_at=None, ends_at=None, title="مسوّدة"),
        "scheduled": await _make_opportunity(
            world.owner, world.project_id, status="scheduled",
            starts_at=_now() + _hours(48), ends_at=_now() + _hours(96),
            title="مجدولة"),
        "closed": await _make_opportunity(
            world.owner, world.project_id, status="closed", title="مغلقة"),
        "deleted": await _make_opportunity(
            world.owner, world.project_id, status="deleted",
            deleted_at=_now(), title="محذوفة"),
        "expired_window": await _make_opportunity(
            world.owner, world.project_id, status="open",
            starts_at=_now() - _hours(96), ends_at=_now() - _hours(1),
            title="انقضت"),
    }
    live = await _make_opportunity(world.owner, world.project_id, title="مفتوحة")

    seen_base = await _visible_opportunity_ids(world.applicant)
    seen_view = await _discoverable_ids(world.applicant)

    assert live in seen_base and live in seen_view
    for label, opportunity_id in hidden.items():
        assert opportunity_id not in seen_base, f"حالٌ خاصّةٌ ظهرت في الجدول: {label}"
        assert opportunity_id not in seen_view, f"حالٌ خاصّةٌ ظهرت في الإسقاط: {label}"

    # وصاحبُها يراها كلَّها — فالإخفاءُ عن الغريب لا إخفاءٌ عن أهلها.
    mine = await _visible_opportunity_ids(world.owner)
    assert set(hidden.values()) | {live} <= mine


# ═════════════════ ٤ و٥ · التقدّمُ فعلٌ شخصيّ ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_04_a_researcher_applies_across_the_tenant_boundary(world):
    """**٤ · متقدّمٌ في «أ» يكتب تطبيقًا على فرصةٍ في «ب».**"""
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    assert application_id in await _visible_application_ids(world.applicant)


@requires_db
@pytest.mark.asyncio
async def test_05_no_one_applies_in_another_researchers_name(world):
    """**٥ · ولا تطبيقَ يُكتب باسم غيرِ صاحبه.**

    فتطبيقٌ يكتبه غيرُ صاحبه إقرارٌ منسوبٌ إلى من لم يُقرّ — والمنعُ في
    السياسة لا في الواجهة: `WITH CHECK` تقيس المعرّفَ بفاعل الجلسة.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    # والمسارُ الخامّ يقيس `WITH CHECK` وحدها — انظر `_apply_raw`.
    with pytest.raises(DBAPIError) as caught:
        await _apply_raw(world.applicant, opportunity_id, applicant=world.applicant2)
    assert "row-level security" in str(caught.value).lower()

    # ومسارُ المنتج (الـORM) يُرفض كذلك — بطبقتين لا بواحدة.
    with pytest.raises(DBAPIError):
        await _apply(world.applicant, opportunity_id, applicant=world.applicant2)

    assert await _visible_application_ids(world.applicant2) == set()


@requires_db
@pytest.mark.asyncio
async def test_05b_a_manager_cannot_manufacture_an_application(world):
    """**٥ (تكملة) · ولا المديرُ يصنع متقدّمًا.**

    فالمديرُ يُرشّح ويعتذر، ولا يُنشئ تقدُّمًا عن أحد — ولا سياسةَ إدراجٍ
    له أصلًا.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    with pytest.raises(DBAPIError) as caught:
        await _apply_raw(world.owner, opportunity_id, applicant=world.applicant)
    assert "row-level security" in str(caught.value).lower()

    with pytest.raises(DBAPIError):
        await _apply(world.owner, opportunity_id, applicant=world.applicant)


# ═════════════════ ٦–٨ · خصوصيّةُ المتقدّمين ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_06_07_08_an_applicant_sees_only_their_own(world):
    """**٦ و٧ و٨ · كلٌّ يرى تقدُّمَه، ولا يرى تقدُّمَ غيره.**

    و«غيرُه» ثلاثةٌ: زميلٌ في مستأجره تقدّم لنفس الفرصة، وغريبٌ في مستأجر
    الفرصة، وغريبٌ عبر المستأجرين.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    mine = await _apply(world.applicant, opportunity_id)
    theirs = await _apply(world.applicant2, opportunity_id)

    assert await _visible_application_ids(world.applicant) == {mine}
    assert await _visible_application_ids(world.applicant2) == {theirs}
    # وغريبٌ في مستأجر الفرصة: لا عضويّةَ له ولا صلاحية.
    assert await _visible_application_ids(world.stranger) == set()


# ═════════════════ ٩–١٤ · مَن يرى المتقدّمين ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_09_the_verified_owner_sees_the_applications(world):
    """**٩ · صاحبُ البحث يرى من تقدّم إلى فرصته.**"""
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    assert await _visible_application_ids(world.owner) == {application_id}


@requires_db
@pytest.mark.asyncio
async def test_10_an_active_manage_team_member_sees_them(world):
    """**١٠ · وعضوٌ نشِطٌ له `manage_team` صريحةً كذلك.**"""
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    assert await _manages(world.manager, world.project_id) is True
    assert await _visible_application_ids(world.manager) == {application_id}
    # ويُدير الفرصَ كتابةً أيضًا: يكتب فرصةً على البحث نفسه.
    assert await _make_opportunity(world.manager, world.project_id,
                                   title="فرصةٌ كتبها المدير")


@requires_db
@pytest.mark.asyncio
async def test_11_a_member_without_manage_team_is_denied(world):
    """**١١ · وعضويّةٌ بلا `manage_team` لا ترى شيئًا — ولو كان الدورُ رئيسًا.**

    و`principal_investigator` **اسمُ دورٍ لا تفويض**. فيُغيَّر الاسمُ إلى
    أقواه وتبقى الصلاحياتُ كما هي: لو انفتح شيءٌ هنا لكان الدورُ يُترجم
    إلى سلطة — وهو بالضبط ما منعه القرارُ.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    await _set_role(world, world.plain_member, "principal_investigator")

    assert await _manages(world.plain, world.project_id) is False
    assert await _visible_application_ids(world.plain) == set()
    # ولا يكتب فرصةً على بحثٍ هو عضوٌ فيه بلا تفويضِ فريق.
    with pytest.raises(DBAPIError):
        await _make_opportunity(world.plain, world.project_id, title="بلا تفويض")


@requires_db
@pytest.mark.asyncio
async def test_11b_manage_team_without_the_view_baseline_is_denied(world):
    """**و`manage_team` بلا أساسِ `view_project` لا تُفوّض.**

    وهذا مرآةُ ما قرّره RC-T1A في `project_ids_with`: صلاحيةٌ مُفصَّلةٌ
    بلا أساسِ الرؤية صفٌّ غيرُ مكتمل، لا سلطةٌ أعلى من الرؤية. ولو سقط
    الأساسُ هنا وحده لصار للاستقطاب نموذجُ تفويضٍ ثانٍ يخالف نموذجَ
    المنصّة — فيُقاس صريحًا.
    """
    from sqlalchemy.exc import DBAPIError

    suffix = uuid.uuid4().hex[:8]
    partial = await _second_user(world.owner["tenant_id"],
                                 email=f"half-{suffix}@example.test")
    await _invite_and_accept(world.owner, partial, world.project_id,
                             permissions=["manage_team"])

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    assert await _manages(partial, world.project_id) is False
    assert await _visible_application_ids(partial) == set()
    with pytest.raises(DBAPIError):
        await _make_opportunity(partial, world.project_id, title="بلا أساس")


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["suspended", "removed"])
async def test_12_13_a_suspended_or_removed_manager_loses_access_at_once(world, state):
    """**١٢ و١٣ · والإيقافُ والإزالةُ يقطعان الوصولَ في الحال.**

    ولا يُنتظر انتهاءُ رمزٍ ولا تحديثُ ذاكرة: الشرطُ `access_state = 'active'`
    يُقرأ في كلّ استعلام.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    private_id = await _make_opportunity(
        world.owner, world.project_id, status="draft",
        starts_at=None, ends_at=None, title="مسوّدةُ الفريق")
    application_id = await _apply(world.applicant, opportunity_id)

    # وقبل الإيقاف: يرى المتقدّمين، ويرى مسوّدةَ فريقه.
    assert await _visible_application_ids(world.manager) == {application_id}
    assert private_id in await _visible_opportunity_ids(world.manager)

    await _set_access(world, world.manager_member, state)

    assert await _manages(world.manager, world.project_id) is False
    assert await _visible_application_ids(world.manager) == set()
    # **وبعده يعود باحثًا كأيّ باحث**: المفتوحُ يُكتشف، والمسوّدةُ لا.
    seen = await _visible_opportunity_ids(world.manager)
    assert opportunity_id in seen
    assert private_id not in seen, "المُوقَفُ ما زال يرى ما لا يُكتشف"


@requires_db
@pytest.mark.asyncio
async def test_14_a_manager_of_another_project_is_denied(world):
    """**١٤ · وتفويضُ الفريق مقيَّدٌ ببحثه.**

    فمديرُ فريقٍ في بحثٍ آخر — في المستأجر نفسه — لا يرى متقدّمي هذا.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    assert await _manages(world.other_manager, world.other_project_id) is True
    assert await _manages(world.other_manager, world.project_id) is False
    assert await _visible_application_ids(world.other_manager) == set()


# ═════════════ ١٥–١٧ · السياقُ الناقصُ والمشوَّهُ يفشل آمنًا ═════════════


@requires_db
@pytest.mark.asyncio
async def test_15_an_actor_tenant_mismatch_is_not_authorization(world):
    """**١٥ · وفاعلٌ من مستأجرٍ في سياق مستأجرٍ آخر لا يُفوَّض.**

    والمزجُ هذا لا يُنتجه عميل — الفاعلُ والمستأجرُ يُقرآن من رمزٍ واحدٍ
    موقَّع. لكنّ السياسةَ لا تتّكل على ذلك: تُقاس هنا بمزجٍ مصنوعٍ صريح.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    mixed = {"tenant_id": world.applicant["tenant_id"], "user_id": world.owner["user_id"]}
    assert await _manages(mixed, world.project_id) is False
    assert await _visible_application_ids(mixed) == set()

    reversed_mix = {"tenant_id": world.owner["tenant_id"],
                    "user_id": world.applicant["user_id"]}
    assert await _manages(reversed_mix, world.project_id) is False


@requires_db
@pytest.mark.asyncio
async def test_16_a_session_without_an_actor_sees_no_recruitment(world):
    """**١٦ · وجلسةٌ بلا فاعل: لا تكتشف، ولا ترى تطبيقًا، ولا تكتب.**

    و`app_current_actor()` تُعيد `NULL`، وكلُّ مقارنةٍ بـ`NULL` تُعطي
    `NULL` — فالسياسةُ لا تطابق. **فالفشلُ آمنٌ بالبناء لا بالاتفاق.**
    """
    from sqlalchemy import select, text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import (
        RecruitmentApplication,
        RecruitmentOpportunity,
    )

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    async with tenant_session(world.owner["tenant_id"]) as session:
        assert (await session.execute(text("SELECT app_current_actor()"))).scalar_one() is None
        assert (await session.execute(
            select(RecruitmentOpportunity.id))).scalars().all() == []
        assert (await session.execute(
            select(RecruitmentApplication.id))).scalars().all() == []
        assert (await session.execute(
            text(f"SELECT count(*) FROM {PUBLIC_VIEW}"))).scalar_one() == 0

    # ولا كتابةَ فرصةٍ بلا فاعل.
    async with tenant_session(world.owner["tenant_id"]) as session:
        session.add(RecruitmentOpportunity(
            tenant_id=world.owner["tenant_id"], project_id=world.project_id,
            title="بلا فاعل", description="—", openings_count=1,
            collaboration_type="data_analysis", status="open",
            starts_at=_now() - _hours(1), ends_at=_now() + _hours(1),
            created_by=world.owner["user_id"]))
        with pytest.raises(DBAPIError):
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_17_a_malformed_actor_aborts_instead_of_answering(world):
    """**١٧ · وفاعلٌ مشوَّه: تُلغى المعاملةُ ولا تُعاد صفوف.**

    فالبديلُ الوحيدُ الخطير أن يُعامَل المشوَّهُ كغائب: `::uuid` تسقط،
    فتسقط العبارةُ كلُّها — ولا صفٌّ يخرج على شكٍّ.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import system_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    async with system_session() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true), "
                 "       set_config('app.actor_id', 'not-a-uuid', true)"),
            {"t": str(world.applicant["tenant_id"])})
        with pytest.raises(DBAPIError) as caught:
            await session.execute(text(f"SELECT count(*) FROM {APPLICATIONS}"))
    assert "uuid" in str(caught.value).lower()


# ═════════════ ١٨ و١٩ · المجمَّعُ لا ينقل سياقًا بين معاملتين ═════════════


@requires_db
@pytest.mark.asyncio
async def test_18_19_a_reused_pooled_connection_carries_no_previous_context(
    two_tenants,
):
    """**١٨ و١٩ · الاتصالُ نفسُه يُعاد استعمالُه، ولا يحمل فاعلًا ولا مستأجرًا.**

    و`set_config(..., true)` محليّةٌ بالمعاملة — لكنّ الدعوى تُثبَت على
    اتصالٍ **مُعادٍ بعينه**: يُثبَّت `pg_backend_pid()` متطابقًا في
    المعاملات الثلاث، وإلّا لأثبت الفحصُ نظافةَ اتصالٍ جديدٍ لا نظافةَ
    إعادةِ استعمال.

    ومجمَّعٌ بسعةٍ واحدة وبلا فائض: لا اتصالَ ثانيًا يُختار مصادفةً.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from athera_api.config import get_settings
    from athera_api.db import _connect_args

    a, b = two_tenants["a"], two_tenants["b"]
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
                {"t": str(a["tenant_id"]), "u": str(a["user_id"])})
            assert (await session.execute(
                text("SELECT app_current_actor()"))).scalar_one() == a["user_id"]
            await session.commit()

        # ── المعاملةُ الثانية على الاتصال نفسِه، وبلا ضبطٍ إطلاقًا ──
        async with factory() as session:
            pid_two = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            leaked = (await session.execute(
                text("SELECT app_current_tenant(), app_current_actor()"))).one()
            await session.commit()

        # ── والثالثةُ بمستأجرٍ وفاعلٍ آخرين ──
        async with factory() as session:
            pid_three = (await session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true), "
                     "       set_config('app.actor_id', :u, true)"),
                {"t": str(b["tenant_id"]), "u": str(b["user_id"])})
            now = (await session.execute(
                text("SELECT app_current_tenant(), app_current_actor()"))).one()
            await session.commit()
    finally:
        await engine.dispose()

    assert pid_one == pid_two == pid_three, (
        f"لم يُعَد الاتصالُ نفسُه ({pid_one}/{pid_two}/{pid_three}) — "
        "والفحصُ يُثبت إعادةَ الاستعمال لا نظافةَ اتصالٍ جديد")
    assert leaked == (None, None), f"سياقٌ عبَر المعاملة: {leaked}"
    assert now == (b["tenant_id"], b["user_id"])


# ═════════════════ ٢٠ · لا تطبيقانِ قائمان ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_20_a_second_active_application_is_refused_by_the_database(world):
    """**٢٠ · والمنعُ في القاعدة لا في الواجهة.**

    ويُحدَّد «القائم» صراحةً: `pending` و`shortlisted` و`invited`. فمن
    انسحب له أن يعود — ويُثبَت الطرفان: الثاني يُرفض، والعودةُ بعد
    الانسحاب تُقبل.
    """
    from sqlalchemy.exc import IntegrityError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    first = await _apply(world.applicant, opportunity_id)

    with pytest.raises(IntegrityError) as caught:
        await _apply(world.applicant, opportunity_id)
    assert "uq_recruitment_applications_active" in str(caught.value)

    # وبعد الانسحاب يعود — فالمنعُ على القائم وحده.
    from sqlalchemy import update

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        await session.execute(
            update(RecruitmentApplication)
            .where(RecruitmentApplication.id == first)
            .values(status="withdrawn", withdrawn_at=_now()))

    again = await _apply(world.applicant, opportunity_id)
    assert again != first


@requires_db
@pytest.mark.asyncio
async def test_20b_a_withdrawn_row_must_carry_its_time(world):
    """والحالةُ وزمنُها لا يفترقان — وإلّا صار «متى انسحب؟» بلا جواب."""
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        with pytest.raises(IntegrityError) as caught:
            await session.execute(
                update(RecruitmentApplication)
                .where(RecruitmentApplication.id == application_id)
                .values(status="withdrawn"))
    assert "withdrawal_has_a_time" in str(caught.value)


# ═════════════════ ٢١ · الإسقاطُ لا يحمل ما لا يُعرض ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_21_the_discovery_projection_carries_no_private_column(world):
    """**٢١ · ولا معرّفَ بحثٍ ولا مستأجرٍ ولا منشئٍ في الاكتشاف.**

    فمعرّفُ البحث مفتاحٌ إلى كلّ ما يتعلّق به، ومعرّفُ المستأجر يكشف
    المؤسسةَ لمن لم يُعلنها صاحبُها. والانتماءُ يُعلَن بـ`public_label`
    **إن كتبه صاحبُه**.

    ويُقاس بعمودٍ **يُطلَب فيسقط**، لا بقائمةٍ تُقرأ: قائمةٌ صحيحةٌ اليوم
    قد تتوسّع غدًا بعمودٍ جديد.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import system_session, tenant_session

    await _make_opportunity(world.owner, world.project_id)

    async with system_session() as session:
        columns = set((await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :v"), {"v": PUBLIC_VIEW})).scalars().all())

    forbidden = {"project_id", "tenant_id", "created_by", "status",
                 "deleted_at", "updated_at"}
    assert not (columns & forbidden), f"أعمدةٌ خاصّةٌ في الإسقاط: {columns & forbidden}"
    assert {"id", "title", "description", "openings_count",
            "collaboration_type", "starts_at", "ends_at"} <= columns

    for column in sorted(forbidden):
        async with tenant_session(world.applicant["tenant_id"],
                                  world.applicant["user_id"]) as session:
            with pytest.raises(DBAPIError):
                await session.execute(text(f"SELECT {column} FROM {PUBLIC_VIEW}"))


@requires_db
@pytest.mark.asyncio
async def test_21b_the_view_is_evaluated_with_the_readers_own_policies(world):
    """والعرضُ `security_invoker` و`security_barrier` — ويُقاس من القاعدة.

    **ولمَ هذا الفحصُ قائمٌ بذاته:** لو غاب `security_invoker` لقُيّم
    العرضُ بحقوق مالكه، فصار الإسقاطُ الآمنُ بابًا يُقرأ منه ما تمنعه
    سياسةُ القارئ. والخيارُ يُتجاهل صامتًا على إصدارٍ أقدم من ١٥.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        options = (await session.execute(text(
            "SELECT reloptions FROM pg_class WHERE relname = :v"),
            {"v": PUBLIC_VIEW})).scalar_one()
        version = (await session.execute(text(
            "SELECT current_setting('server_version_num')::int"))).scalar_one()

    assert version >= 150000, "الإسقاطُ الآمن يشترط PostgreSQL 15+"
    assert "security_invoker=true" in options
    assert "security_barrier=true" in options


# ═════════════════ ٢٢ · ولا تجاوزَ للعزل في هذا المسار ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_22_the_whole_path_runs_without_bypassrls(world):
    """**٢٢ · والدورُ الذي أثبت كلَّ ما سبق لا يتجاوز العزل.**

    فحزمةٌ تجري بدورٍ متجاوزٍ تُثبت العزلَ على قاعدةٍ لا تُرشّح — ويُسأل
    هنا عن الدور نفسِه الذي جرت به الفحوص.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        row = (await session.execute(text(
            "SELECT current_user, rolsuper, rolbypassrls "
            "FROM pg_roles WHERE rolname = current_user"))).one()

    assert row[1] is False, f"الدورُ {row[0]} مُتميّز"
    assert row[2] is False, f"الدورُ {row[0]} يتجاوز RLS"


def test_22b_no_line_of_the_recruitment_foundation_asks_for_bypassrls():
    """**ولا سطرَ يطلب التجاوزَ مكتوبٌ أصلًا** — لا في النموذج ولا الترحيل.

    ورابطُ دورِ التجاوز قائمٌ في تجهيزات المستودع لأسبابه، **ولا تلمسه
    هذه الحزمة**: ما يُثبت عن العزل يُثبت بالدور الذي يعمل به الإنتاج،
    وإلّا أُثبِت على قاعدةٍ لا تُرشّح.
    """
    for path in (API / "models" / "recruitment.py", MIGRATION):
        source = path.read_text(encoding="utf-8").upper()
        assert "BYPASSRLS" not in source, f"تجاوزٌ مذكورٌ في {path.name}"

    own = pathlib.Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("ATHERA_TEST_BYPASSRLS", "bypassing_rls"):
        # ويُقاس على الشيفرة لا على النصّ: السلاسلُ المذكورة هنا هي
        # المطلوبةُ غيابُها، فتُستثنى أسطرُ هذا الفحص نفسِه.
        hits = [line for line in own.splitlines()
                if forbidden in line and "forbidden" not in line]
        assert hits == [], f"الحزمةُ تلمس {forbidden}: {hits}"


# ═════════════ حرّاسُ البنية: ما لا تلتقطه فحوصُ السلوك ═════════════


@requires_db
@pytest.mark.asyncio
async def test_no_policy_on_the_new_tables_is_broadly_true(db_ready):
    """**ولا `USING (true)` على سطحِ الاستقطاب.**

    فسياسةٌ شاملةٌ تُغني عن كلّ ما سبق في سطرٍ واحد، ولا يظهر أثرُها في
    فحصٍ سلوكيٍّ إلّا حين يُسأل السؤالُ الذي لم يُسأل.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT p.polname, p.polcmd, "
            "       coalesce(pg_get_expr(p.polqual, p.polrelid), '') AS q, "
            "       coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '') AS w "
            "FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
            "WHERE c.relname IN (:o, :a)"),
            {"o": OPPORTUNITIES, "a": APPLICATIONS})).all()

    assert rows, "لا سياسةَ على جدولٍ مُفعَّلِ العزل — وذلك منعٌ كامل لا انفتاح"
    for name, cmd, using, check in rows:
        for expression in (using, check):
            assert expression.strip().lower() not in ("true", "(true)"), \
                f"سياسةٌ شاملة: {name}"
        # **ولا فعلَ حذفٍ لأحد** — دورةُ الحياة حذفٌ ناعم.
        assert cmd != "d", f"سياسةُ حذفٍ مكتوبة: {name}"
        assert cmd != "*", f"سياسةٌ شاملةُ الأفعال تشمل الحذفَ ضمنًا: {name}"


@requires_db
@pytest.mark.asyncio
async def test_a_hard_delete_is_unreachable_from_the_application_role(db_ready):
    """والحذفُ الصلبُ ممنوعٌ بطبقتين: لا سياسةَ له، **ولا صلاحيةَ** له.

    فمنحٌ شاملٌ في ترحيلٍ لاحق — وهو نمطٌ قائم في 0003 — كان سيفتح الحذفَ
    صامتًا لو اتُّكل على السياسة وحدها.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for table in (OPPORTUNITIES, APPLICATIONS):
            granted = (await session.execute(text(
                "SELECT has_table_privilege('athera_app', :t, 'DELETE')"),
                {"t": table})).scalar_one()
            assert granted is False, f"صلاحيةُ حذفٍ قائمةٌ على {table}"
        # ولا كتابةَ عبر الإسقاط.
        for privilege in ("INSERT", "UPDATE", "DELETE"):
            granted = (await session.execute(text(
                f"SELECT has_table_privilege('athera_app', :v, '{privilege}')"),
                {"v": PUBLIC_VIEW})).scalar_one()
            assert granted is False, f"{privilege} على الإسقاط"


@requires_db
@pytest.mark.asyncio
async def test_an_application_pins_the_opportunity_it_belongs_to(world):
    """وتسلسلُ الحذفِ كان سيمحو تقدُّمَ باحثٍ في مستأجرٍ آخر بلا أثر.

    فهو يجري **بحقوق مالك الجدول**: لا RLS تراه ولا سياسةَ تمنعه. ولذلك
    طبقتان تُقاسان كلٌّ على حدة:

      ١. دورُ التطبيق لا يملك `DELETE` أصلًا — فالمحاولةُ تُرفض قبل أن
         تبلغ المفتاحَ الأجنبيّ. **وقد أُثبِت هذا بالمحاولة**: الرفضُ جاء
         `permission denied`، لا انتهاكَ مفتاح.
      ٢. ولو مُنحت الصلاحيةُ يومًا — ومنحٌ شاملٌ في ترحيلٍ لاحق نمطٌ قائم
         في 0003 — لبقي المفتاحُ `RESTRICT` يمنع. ويُقرأ من الفهرس لأنّ
         الطبقةَ الأولى تحجب اختبارَه سلوكيًّا.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from athera_api.db import system_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    async with system_session() as session:
        with pytest.raises(ProgrammingError) as caught:
            await session.execute(
                text(f"DELETE FROM {OPPORTUNITIES} WHERE id = :i"),
                {"i": str(opportunity_id)})
    assert "permission denied" in str(caught.value).lower()

    async with system_session() as session:
        rule = (await session.execute(text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid = cast(:a AS regclass) AND contype = 'f' "
            "  AND confrelid = cast(:o AS regclass)"),
            {"a": APPLICATIONS, "o": OPPORTUNITIES})).scalar_one()
    # و`confdeltype` عمودُ `"char"` كسابقه — يعود بايتًا.
    assert rule in ("r", b"r"), f"مفتاحُ الفرصة ليس RESTRICT بل {rule!r}"


@requires_db
@pytest.mark.asyncio
async def test_the_manager_predicate_is_not_security_definer(db_ready):
    """ودالّةُ الإدارة **بحقوق مستدعيها** — وذاك شرطُ صحّتها لا تفصيل.

    فـ`SECURITY DEFINER` كانت ستجعلها تقرأ الأبحاثَ والعضويّاتِ عبر
    المستأجرين، فتُجيب «نعم» لمن ليس في المستأجر أصلًا: ثقبٌ بحجم
    الدالّة، في قلب كلّ سياسةٍ تناديها.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        row = (await session.execute(text(
            "SELECT p.prosecdef, p.provolatile, p.proconfig, "
            "       has_function_privilege('public', 'app_manages_project(uuid)', 'EXECUTE'), "
            "       has_function_privilege('athera_app', 'app_manages_project(uuid)', 'EXECUTE') "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'public' AND p.proname = 'app_manages_project'"))).one()

    assert row[0] is False, "دالّةُ الإدارة SECURITY DEFINER"
    # و`provolatile` عمودُ `"char"` — يعود بايتًا، فيُقاس كما هو.
    assert row[1] in ("s", b"s"), f"دالّةُ الإدارة ليست STABLE بل {row[1]!r}"
    assert any("search_path=" in c for c in (row[2] or [])), "مسارُ البحث غيرُ مثبَّت"
    assert row[3] is False, "تنفيذٌ عامّ لدالّة الإدارة"
    assert row[4] is True


@requires_db
@pytest.mark.asyncio
async def test_no_constraint_name_on_the_new_tables_was_silently_truncated(db_ready):
    """والاسمُ المقصوصُ لا يُعلن عن نفسه — فيُقاس طولُه ويُطابق ما يُنتظر.

    وهو الفخُّ الذي وثّقه الترحيل 0032: `%(constraint_name)s` يُبادئ الاسمَ
    باسم الجدول، فاسمٌ كُتب كاملًا يُبادأ مرّتين ويُقصّ فوق ٦٣ محرفًا.
    **وقد وقع هذا فعلًا في أوّل كتابةٍ لهذا الترحيل.**
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    expected = {
        "ck_recruitment_opportunities_status_is_known",
        "ck_recruitment_opportunities_window_is_ordered",
        "ck_recruitment_opportunities_openings_are_positive",
        "ck_recruitment_opportunities_open_needs_a_start",
        "ck_recruitment_applications_status_is_known",
        "ck_recruitment_applications_withdrawal_has_a_time",
    }
    async with system_session() as session:
        names = set((await session.execute(text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid::regclass::text IN (:o, :a) AND contype = 'c'"),
            {"o": OPPORTUNITIES, "a": APPLICATIONS})).scalars().all())

    assert names == expected, f"قيودٌ بأسماءٍ غيرِ متوقّعة: {names ^ expected}"
    assert all(len(name) <= 63 for name in names)


@requires_db
@pytest.mark.asyncio
async def test_the_window_and_the_openings_are_enforced_by_the_database(world):
    """`starts_at < ends_at`، و«مفتوحة» تستوجب بدايةً، والشواغرُ موجبة."""
    from sqlalchemy.exc import IntegrityError

    cases = (
        ("window_is_ordered", dict(starts_at=_now() + _hours(48),
                                   ends_at=_now() + _hours(1))),
        ("open_needs_a_start", dict(status="open", starts_at=None, ends_at=None)),
    )
    for expected, kwargs in cases:
        with pytest.raises(IntegrityError) as caught:
            await _make_opportunity(world.owner, world.project_id, **kwargs)
        assert expected in str(caught.value), f"قيدٌ لم يعضّ: {expected}"

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentOpportunity

    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        session.add(RecruitmentOpportunity(
            tenant_id=world.owner["tenant_id"], project_id=world.project_id,
            title="بلا شواغر", description="—", openings_count=0,
            collaboration_type="data_analysis", status="open",
            starts_at=_now() - _hours(1), ends_at=_now() + _hours(1),
            created_by=world.owner["user_id"]))
        with pytest.raises(IntegrityError) as caught:
            await session.flush()
    assert "openings_are_positive" in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_an_unknown_state_is_refused_on_both_tables(world):
    """والمفرداتُ مغلقةٌ في القاعدة لا في التوثيق."""
    from sqlalchemy import text, update
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    async with tenant_session(world.owner["tenant_id"],
                             world.owner["user_id"]) as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(f"UPDATE {OPPORTUNITIES} SET status = 'paused' WHERE id = :i"),
                {"i": str(opportunity_id)})

    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                update(RecruitmentApplication)
                .where(RecruitmentApplication.id == application_id)
                .values(status="hired"))


def test_the_vocabularies_of_the_model_and_the_migration_are_one():
    """ومفرداتٌ في موضعين تفترقان بأوّل تعديل — فتُقابَلان صريحًا.

    و**أفعالُ إنشاء البحث** أخطرُها: لو زيد فعلٌ في `collaboration.py` ولم
    يُزد في الدالّة لفقد مالكٌ سلطتَه على بحثه بلا أيّ خطأ ظاهر.
    """
    import importlib.util

    from athera_api.models import recruitment
    from athera_api.services import collaboration

    spec = importlib.util.spec_from_file_location("m0034", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.OPPORTUNITY_STATES == recruitment.OPPORTUNITY_STATES
    assert module.APPLICATION_STATES == recruitment.APPLICATION_STATES
    assert module.ACTIVE_APPLICATION_STATES == recruitment.ACTIVE_APPLICATION_STATES
    assert tuple(module.PROJECT_CREATED_ACTIONS) == \
        tuple(collaboration.PROJECT_CREATED_ACTIONS)
    # والصلاحيةُ المُديرة اسمٌ واحدٌ في الثلاثة.
    assert recruitment.MANAGE_RECRUITMENT == "manage_team"
    assert recruitment.MANAGE_RECRUITMENT in module.MANAGES_PROJECT_FN
    assert collaboration.VIEW_PROJECT in module.MANAGES_PROJECT_FN


def test_the_discovery_predicate_is_written_once():
    """وشرطُ الاكتشافِ نصٌّ واحد يخدم السياسةَ والعرض.

    فنسختانِ منه تفترقان، وحينها يعرض العرضُ ما لا تسمح به السياسة أو
    العكس — ولا يظهر ذلك في فحصٍ واحد.
    """
    source = MIGRATION.read_text(encoding="utf-8")
    assert source.count("DISCOVERABLE = (") == 1
    assert source.count("{DISCOVERABLE}") == 2
    for fragment in ("status = 'open'", "deleted_at IS NULL",
                     "starts_at <= now()", "ends_at > now()"):
        assert fragment in source, f"شرطٌ ناقصٌ في الاكتشاف: {fragment}"


def test_this_stage_adds_no_router_and_no_web_surface():
    """و«فرصُ البحث» لم تبدأ — وهي دعوى تُثبَت لا تُقال.

    فأساسٌ أمنيٌّ يُدسّ معه موجّهٌ أو صفحةٌ يخرج من نطاقه، ويصير ما لم
    يُراجَع منشورًا.

    **ويُقاس هذا النطاقُ باسمه لا بكلمةٍ عامّة**: `opportunities` و
    `publication-opportunities` صفحتان قائمتان منذ التوليف والرسائل، ولا
    شأنَ لهما بالاستقطاب — وحارسٌ يمنع الكلمةَ يسقط على شيءٍ لم أكتبه.
    """
    routers = API / "routers"
    offenders = [p.name for p in routers.glob("*.py") if "recruitment" in p.name]
    assert offenders == [], f"موجّهٌ في مرحلةٍ لا موجّهَ فيها: {offenders}"

    main = (API / "main.py").read_text(encoding="utf-8")
    assert "recruitment" not in main, "الاستقطابُ مُركَّبٌ في التطبيق"

    # ولا سطرَ في الويب يعرف هذا النطاق.
    web = REPO / "apps" / "web" / "src"
    if web.exists():
        touched = [
            str(path.relative_to(web))
            for path in web.rglob("*.ts*")
            if "recruitment" in path.read_text(encoding="utf-8", errors="ignore").lower()
        ]
        assert touched == [], f"الويبُ يلمس الاستقطاب: {touched}"


def test_nothing_here_creates_membership_authorship_or_credit():
    """**والقبولُ لا يُنشئ عضويّةً ولا تأليفًا ولا أدوارَ CRediT.**

    فالمختارُ يُدعى بـ`ProjectInvitation` القائمة، والدعوةُ تُقبل بيد
    صاحبها. والعضويّةُ ليست تأليفًا.
    """
    model = (API / "models" / "recruitment.py").read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    for source, label in ((model, "النموذج"), (migration, "الترحيل")):
        for forbidden in ("ProjectMember(", "project_members (",
                          "credit_roles", "is_author", "author_position"):
            assert forbidden not in source, f"{label} يلمس العضويّة/التأليف: {forbidden}"


@requires_db
@pytest.mark.asyncio
async def test_no_employment_vocabulary_entered_the_domain(db_ready):
    """وهذا تعاونٌ بحثيّ لا توظيف — ولا مفرداتَ أجرٍ ولا عقدِ عمل.

    **ويُقاس على المخطَّط لا على النثر.** فرأسُ الوحدة يذكر هذه المفردات
    **منفيّةً** («لا راتبَ ولا عقدَ عمل»)، وحارسٌ يقرأ النصَّ يسقط على
    الجملة التي تمنعها ويطالب بحذف التوثيق. فيُسأل الجدولُ نفسُه: أعمدةٌ
    ومفرداتٌ مغلقة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session
    from athera_api.models import recruitment

    forbidden = ("salary", "wage", "payroll", "employee", "employment",
                 "hiring", "hire", "contract", "compensation", "payment")

    async with system_session() as session:
        columns = set((await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name IN (:o, :a)"),
            {"o": OPPORTUNITIES, "a": APPLICATIONS})).scalars().all())

    for column in columns:
        for word in forbidden:
            assert word not in column.lower(), f"عمودٌ بمفردةِ توظيف: {column}"

    vocabularies = (recruitment.OPPORTUNITY_STATES
                    + recruitment.APPLICATION_STATES
                    + recruitment.ACTIVE_APPLICATION_STATES)
    for value in vocabularies:
        for word in forbidden:
            assert word not in value.lower(), f"حالٌ بمفردةِ توظيف: {value}"

    # و«مساعدُ بحث» وسمُ تعاونٍ: أدوارُ العضويّة تبقى مفرداتِ المستودع
    # القائمة، ولا يُخترع منها دورٌ وظيفيّ في هذا النطاق.
    assert not hasattr(recruitment, "COLLABORATION_ROLES")


def test_the_declared_boundary_is_written_down_not_remembered():
    """**والحدُّ المُعلَن يُقرأ من المستند** — فلو حُذف سقط هذا الفحص وطالب به.

    فسطحٌ يعبُر المستأجرين قصدًا، وعزلُه بحدِّ الصفوف لا الأعمدة، حدٌّ
    يجب أن يعرفه من يكتب أوّلَ موجّهِ اكتشافٍ في RC-T1C. وذاكرةُ من كتبه
    ليست مكانَ حفظه.
    """
    document = (REPO / "docs" / "threat-model.md").read_text(encoding="utf-8")
    assert "RC-T1B" in document
    assert PUBLIC_VIEW in document
    assert "security_invoker" in document
    for claim in ("project_id", "tenant_id", "created_by"):
        assert claim in document, f"عمودٌ خاصٌّ لم يُسمَّ في الحدّ المُعلَن: {claim}"


# ═════════════ ١٤ من التكليف · RC-T1A لم تُمسّ ═════════════


@requires_db
@pytest.mark.asyncio
async def test_rc_t1a_project_access_is_unchanged_by_this_stage(world):
    """**وعضويّةُ المستأجر لم تعُد عضويّةَ بحثٍ — ولا تزال.**

    فسطحٌ جديدٌ يقرأ الأبحاثَ والعضويّاتِ قد يُغري بتوسيع ما يراه
    المستأجر. فيُعاد سؤالُ RC-T1A هنا: الغريبُ لا يرى، والعضوُ يرى،
    والمالكُ يرى.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    tenant_id = world.owner["tenant_id"]

    async with tenant_session(tenant_id, world.stranger["user_id"]) as session:
        visible = await collaboration.visible_project_ids(
            session, tenant_id=tenant_id, user_id=world.stranger["user_id"])
        assert world.project_id not in visible, "غريبٌ في المستأجر يرى بحثًا"
        assert await collaboration.may_view_project(
            session, tenant_id=tenant_id, project_id=world.project_id,
            user_id=world.stranger["user_id"]) is False

    async with tenant_session(tenant_id, world.plain["user_id"]) as session:
        visible = await collaboration.visible_project_ids(
            session, tenant_id=tenant_id, user_id=world.plain["user_id"])
        assert world.project_id in visible
        assert world.other_project_id not in visible, \
            "عضوٌ في بحثٍ يرى بحثًا آخرَ لم يُدعَ إليه"

    async with tenant_session(tenant_id, world.owner["user_id"]) as session:
        assert await collaboration.is_verified_owner(
            session, project_id=world.project_id,
            user_id=world.owner["user_id"]) is True
        access = await collaboration.ensure_project_access(
            session, tenant_id=tenant_id, project_id=world.project_id,
            user_id=world.owner["user_id"])
        assert access.is_owner is True

    # ولا يرى المتقدّمُ من مستأجرٍ آخر بحثًا، ولو تقدّم إلى فرصته.
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)
    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        assert await collaboration.may_view_project(
            session, tenant_id=world.applicant["tenant_id"],
            project_id=world.project_id,
            user_id=world.applicant["user_id"]) is False
