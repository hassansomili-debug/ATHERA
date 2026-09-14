"""الاستقطابُ عبر المؤسسات — وعزلُ البحث باقٍ | RC-T1B recruitment security.

**الحدُّ الذي يُكسَر هنا، وما يمنعه من أن يصير ثقبًا.**

كلُّ صفٍّ قبل الترحيل 0034 يُقرأ داخل مستأجرٍ واحد. وقرارُ المنتج يستوجب
أن يكتشف باحثٌ في مؤسسةٍ فرصةَ تعاونٍ أعلنها بحثٌ في مؤسسةٍ أخرى وأن
يتقدّم إليها. فالحدُّ يُكسَر في القاعدة وبأضيق ما يكفي، **وهذه الحزمةُ
هي ما يُثبت أنّ «أضيق ما يكفي» ليس دعوى**.

## ثلاثةُ أسئلةٍ رفعتها مراجعةٌ أمنية، وهذه أجوبتُها المُقاسة

  ١ **هل يبلغ الغريبُ الأعمدةَ الخاصّة؟** كان الجوابُ «العرضُ الآمن هو
    الطريقُ المُعتمد» — أي اتفاقًا في التطبيق. فانفصل النسبُ عن الإعلان:
    `recruitment_opportunities` تحمل المستأجرَ والبحثَ والمنشئ ولا
    سياسةَ عابرةً للمستأجرين عليها، و`recruitment_opportunity_listings`
    **لا تحمل تلك الأعمدة أصلًا**. فيُقاس هنا الأمرانِ معًا: أنّ
    الاكتشافَ يعمل، وأنّ العمودَ الخاصَّ لا يُبلَغ من أيّ جدول.
  ٢ **هل سلطةُ التعديل أوسعُ من صاحبها؟** كانت سياسةُ «صاحبُه يعدّله»
    تسمح له أن يُرشّح نفسَه: `WITH CHECK` ترى الجديدَ ولا ترى القديم.
    فالمصفوفةُ في مُشغِّلٍ على القاعدة، وتُقاس بندًا بندًا.
  ٣ **هل يُقبل تقدُّمٌ على بابٍ أُغلق؟** كان يُقبل. فشرطُ القبول صار
    نفسَ شرطِ الاكتشاف، ويُقاس على الحالات الخمس.

## ولا شيءَ هنا يُصطنع

لا `mock` لسياسةٍ، ولا جلسةَ تجاوز، ولا صفَّ يُدسّ بيدٍ حيث يمرّ المنتجُ
بمسار. البحثُ يُنشأ من نقطةِ الـAPI الحقيقية، والدعوةُ تُصدر بخدمتها،
والفرصةُ والتطبيقُ يُكتبان بجلسةِ صاحبهما — فما يُرفض هنا ترفضه
PostgreSQL نفسُها، وما يُقبل قبلته.

**ولا `BYPASSRLS` في هذه الحزمة** — ويُثبَت ذلك فحصًا صريحًا، لأنّ حزمةً
تجري بدورٍ متجاوزٍ تُثبت العزلَ على قاعدةٍ لا تُرشّح.
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

OWNERS = "recruitment_opportunities"
LISTINGS = "recruitment_opportunity_listings"
APPLICATIONS = "recruitment_applications"
PUBLIC_VIEW = "recruitment_opportunities_public"

#: ما لا يجوز أن يبلغه غريبٌ من أيّ جدولٍ في هذا النطاق.
PRIVATE_COLUMNS = ("tenant_id", "project_id", "created_by")


def _hours(n: int) -> dt.timedelta:
    return dt.timedelta(hours=n)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═════════════════ التجهيز ═════════════════


async def _make_opportunity(
    slot, project_id, *, status="open", starts_at=..., ends_at=...,
    deleted_at=None, title="مساعدةٌ في التحليل الإحصائي", created_by=None,
) -> uuid.UUID:
    """فرصةٌ تُكتب **بجلسة مديرها** — فالإدراجُ نفسُه برهانُ سلطته.

    وصفّان لا صفّ: النسبُ أوّلًا (تفويضُه `project_id` وحده)، ثمّ
    الإعلانُ (تفويضُه يقرأ أباه). **ولو انعكس الترتيبُ لاحتاج إعلانٌ إلى
    نسبٍ لم يُكتب بعد.**
    """
    from athera_api.db import tenant_session
    from athera_api.models.recruitment import (
        RecruitmentOpportunity,
        RecruitmentOpportunityListing,
    )

    if starts_at is ...:
        starts_at = _now() - _hours(24) if status != "draft" else None
    if ends_at is ...:
        ends_at = _now() + _hours(24 * 30) if starts_at is not None else None

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        owner = RecruitmentOpportunity(
            tenant_id=slot["tenant_id"], project_id=project_id,
            created_by=(created_by or slot)["user_id"])
        session.add(owner)
        await session.flush()
        session.add(RecruitmentOpportunityListing(
            opportunity_id=owner.id,
            title=title, description="مراجعةُ مخرجاتِ نموذجٍ خطّيّ وتوثيقُها.",
            contributions="تشغيلُ التحليل وكتابةُ قسم النتائج.",
            requirements="خبرةٌ بـR أو Python.",
            specialization="القياس والإحصاء", openings_count=1,
            collaboration_type="data_analysis", status=status,
            starts_at=starts_at, ends_at=ends_at, deleted_at=deleted_at,
            public_label="مركزُ أبحاثٍ جامعيّ"))
        await session.flush()
        return owner.id


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


async def _apply_raw(slot, opportunity_id, *, applicant=None, **overrides) -> None:
    """إدراجٌ خامٌّ **بلا `RETURNING`** — ليُقاس `WITH CHECK` وحده.

    **ولمَ لا يكفي مسارُ الـORM هنا.** SQLAlchemy تُلحق `RETURNING` بكلّ
    إدراجٍ فيه قيمةٌ تُولَّد في الخادم (`created_at`/`updated_at`)، و
    PostgreSQL تُخضع `RETURNING` لسياسات **القراءة**. فصفٌّ باسم غيرِ
    الفاعل كان يُرفض بسياسة القراءة قبل أن يُسأل عنه `WITH CHECK` —
    ‏**وقد اكتُشف هذا بعضّ الحارس**: أُبطل شرطُ الفاعل في سياسة الإدراج
    فبقي الفحصُ ناجحًا، أي أنّه كان يُثبت بندًا غير الذي يُسمّيه.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    values = {
        "i": str(uuid.uuid4()), "o": str(opportunity_id),
        "u": str((applicant or slot)["user_id"]), "t": str(slot["tenant_id"]),
        "s": overrides.get("status", "pending"),
        "m": "إدراجٌ خامّ",
    }
    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        await session.execute(
            text(f"INSERT INTO {APPLICATIONS} "
                 "(id, opportunity_id, applicant_user_id, applicant_tenant_id, "
                 " status, message, created_at, updated_at) "
                 "VALUES (:i, :o, :u, :t, :s, :m, now(), now())"),
            values)


async def _update_application(slot, application_id, **columns) -> None:
    """تعديلٌ خامٌّ بأعمدةٍ بعينها — فتُقاس المصفوفةُ عمودًا عمودًا.

    ولا `RETURNING` هنا كذلك: المقصودُ المُشغِّلُ والسياسة، لا ما يعود.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    assignments = ", ".join(f"{name} = :{name}" for name in columns)
    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        await session.execute(
            text(f"UPDATE {APPLICATIONS} SET {assignments} WHERE id = :row_id"),
            {**columns, "row_id": str(application_id)})


async def _issue_invitation(owner, project_id, *, email) -> uuid.UUID:
    """دعوةٌ حقيقيةٌ تُصدر بخدمتها القائمة — **ولا تُقبل**.

    فحالُ «مدعوّ» تشترط دعوةً موجودة، لا عضويّةً مُنشأة: الدعوةُ تُقبل
    بيد صاحبها، وذاك ما يصنع العضويّة — في RC-T1C.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        issued = await collaboration.invite_member(
            session, tenant_id=owner["tenant_id"], project_id=project_id,
            inviter_user_id=owner["user_id"], display_name="مرشَّح",
            email=email, role="co_author", permissions=["view_project"])
        return issued.invitation.id


async def _visible_listing_ids(slot) -> set[uuid.UUID]:
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentOpportunityListing

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        rows = (await session.execute(
            select(RecruitmentOpportunityListing.opportunity_id))).scalars().all()
    return set(rows)


async def _visible_owner_ids(slot) -> set[uuid.UUID]:
    """ما تراه الجلسةُ من **جدول النسب** — وهو ما يجب أن يبقى مغلقًا."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentOpportunity

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        rows = (await session.execute(
            select(RecruitmentOpportunity.id))).scalars().all()
    return set(rows)


async def _discoverable_ids(slot) -> set[uuid.UUID]:
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


async def _application_row(slot, application_id) -> dict | None:
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        row = (await session.execute(
            text(f"SELECT status, decided_by, decided_at, withdrawn_at, "
                 f"       invitation_id, opportunity_id, applicant_user_id, "
                 f"       applicant_tenant_id, message "
                 f"FROM {APPLICATIONS} WHERE id = :i"),
            {"i": str(application_id)})).mappings().first()
    return dict(row) if row else None


async def _manages(slot, project_id) -> bool:
    from sqlalchemy import text

    from athera_api.db import tenant_session

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        return (await session.execute(
            text("SELECT app_manages_project(:p)"), {"p": str(project_id)})).scalar_one()


class World:
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
    # غريبٌ في مستأجر المتقدّمين لا يتقدّم إلى شيء — فيُقاس عليه الحدُّ
    # العابرُ للمستأجرين وحده، بلا تقدُّمٍ يخلطه.
    outsider = await _second_user(applicant["tenant_id"],
                                  email=f"out-{suffix}@example.test")

    manager_member = await _invite_and_accept(
        owner, manager, project_id, permissions=["view_project", "manage_team"])
    # **ودورٌ باسمه لا يُفوّض**: عضوٌ بلا `manage_team` صريحة.
    plain_member = await _invite_and_accept(
        owner, plain, project_id, permissions=["view_project"])
    await _invite_and_accept(
        owner, other_manager, other_project_id,
        permissions=["view_project", "manage_team"])

    return World(
        owner=owner, applicant=applicant, applicant2=applicant2,
        outsider=outsider,
        manager=manager, manager_member=manager_member,
        plain=plain, plain_member=plain_member,
        stranger=stranger, other_manager=other_manager,
        project_id=project_id, other_project_id=other_project_id,
        suffix=suffix,
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


# ═══════ ١ و٢ · الاكتشافُ يعبُر، والأعمدةُ الخاصّةُ لا تُبلَغ ═══════


@requires_db
@pytest.mark.asyncio
async def test_01_an_open_opportunity_crosses_the_tenant_boundary(world):
    """**١ · باحثٌ في «أ» يرى إعلانًا كتبه بحثٌ في «ب».**

    وهو الحدُّ المقصودُ كسرُه. ولو سقط هذا الفحص فالمنتجُ لم يُبنَ.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    assert opportunity_id in await _visible_listing_ids(world.applicant)
    assert opportunity_id in await _discoverable_ids(world.applicant)


@requires_db
@pytest.mark.asyncio
async def test_02_no_private_column_is_reachable_across_the_tenant_boundary(world):
    """**٢ · ولا يبلغ الغريبُ معرّفَ بحثٍ ولا مستأجرٍ ولا منشئ — من أيّ جدول.**

    **وهذا ما لم يكن مغلقًا.** كانت الفرصةُ جدولًا واحدًا عليه سياسةُ
    اكتشافٍ عابرة، وRLS تحكم الصفوفَ لا الأعمدة — فاستعلامٌ مباشرٌ على
    الجدول الأصل كان يُعطي `project_id` و`tenant_id` و`created_by`.

    ويُقاس الآن ثلاثةَ أوجه:

      أ **جدولُ النسب لا يُرى**: صفرُ صفوفٍ لغريبٍ، فلا عمودَ يُقرأ منه.
      ب **وجدولُ الإعلان لا يحملها أصلًا**: يُطلب العمودُ فتسقط العبارة —
        وهو أقوى من قائمةٍ تُقرأ، لأنّ القائمةَ تتوسّع والعمودَ المعدومَ
        لا يعود.
      ج **والوصلةُ المصنوعةُ بيدٍ لا تُجدي**: من يعرف معرّفَ فرصةٍ ويصل
        جدولَ النسب بها لا يزيد على صفر.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from athera_api.db import tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    assert opportunity_id in await _visible_listing_ids(world.applicant)

    # أ · النسبُ مغلقٌ تمامًا.
    assert await _visible_owner_ids(world.applicant) == set()

    async with tenant_session(world.applicant["tenant_id"],
                              world.applicant["user_id"]) as session:
        count = (await session.execute(
            text(f"SELECT count(*) FROM {OWNERS} WHERE id = :i"),
            {"i": str(opportunity_id)})).scalar_one()
        assert count == 0, "جدولُ النسب مقروءٌ من مستأجرٍ آخر"

        # ج · ووصلةٌ مصنوعةٌ بيدٍ لا تُخرج شيئًا.
        leaked = (await session.execute(text(
            f"SELECT count(*) FROM {LISTINGS} l "
            f"JOIN {OWNERS} o ON o.id = l.opportunity_id"))).scalar_one()
        assert leaked == 0, "الوصلةُ أخرجت نسبًا لغريب"

    # ب · والإعلانُ لا يحمل عمودًا خاصًّا يُطلَب.
    #
    # **وجلسةٌ لكلّ عمود**: عبارةٌ ترفضها القاعدة تُجهض المعاملةَ، فكلُّ ما
    # بعدها يُجيب بخطأ الإجهاض لا بخطأ الرفض — فيُقاس بندٌ غيرُ المقصود.
    for column in PRIVATE_COLUMNS:
        async with tenant_session(world.applicant["tenant_id"],
                                  world.applicant["user_id"]) as fresh:
            with pytest.raises(ProgrammingError) as caught:
                await fresh.execute(text(f"SELECT {column} FROM {LISTINGS}"))
            assert "does not exist" in str(caught.value), \
                f"العمودُ {column} موجودٌ في جدول الإعلان"



@requires_db
@pytest.mark.asyncio
async def test_02b_the_manager_still_reaches_the_private_metadata(world):
    """وما أُغلق عن الغريب لم يُغلق عن أهله — وإلّا لم يكن إصلاحًا.

    فصاحبُ البحث والعضوُ المفوَّضُ يقرآن النسبَ، والغريبُ في المستأجر
    نفسِه لا يقرؤه.
    """
    from sqlalchemy import text

    from athera_api.db import tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    for slot, label in ((world.owner, "المالك"), (world.manager, "المدير")):
        async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
            row = (await session.execute(text(
                f"SELECT tenant_id, project_id, created_by FROM {OWNERS} "
                "WHERE id = :i"), {"i": str(opportunity_id)})).mappings().one()
        assert row["project_id"] == world.project_id, label
        assert row["tenant_id"] == world.owner["tenant_id"], label
        assert row["created_by"] == world.owner["user_id"], label

    # والغريبُ في المستأجر نفسِه: لا شيء — لا قراءةً ولا إدارة.
    assert await _visible_owner_ids(world.stranger) == set()
    assert await _manages(world.stranger, world.project_id) is False
    assert await _visible_owner_ids(world.plain) == set(), \
        "عضوٌ بلا تفويضِ فريقٍ يقرأ نسبَ الفرص"
    # وغريبٌ في مستأجرٍ آخر كذلك — والحدّان مختلفان فيُقاسان معًا.
    assert await _manages(world.outsider, world.project_id) is False
    assert await _visible_owner_ids(world.outsider) == set()


@requires_db
@pytest.mark.asyncio
async def test_03_only_the_open_window_is_discoverable(world):
    """**٣ · المسوّدةُ والمجدولةُ والمغلقةُ والمحذوفةُ لا تُكتشف.**

    وأربعُ حالاتٍ لا اثنتان: **والنافذةُ المنتهيةُ خامسة**. فإعلانٌ حالُه
    `open` وقد انقضى أجلُه كان سيبقى مُكتشَفًا لو قِيس الحالُ وحده —
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

    seen_base = await _visible_listing_ids(world.applicant)
    seen_view = await _discoverable_ids(world.applicant)

    assert live in seen_base and live in seen_view
    for label, opportunity_id in hidden.items():
        assert opportunity_id not in seen_base, f"حالٌ خاصّةٌ ظهرت في الجدول: {label}"
        assert opportunity_id not in seen_view, f"حالٌ خاصّةٌ ظهرت في الإسقاط: {label}"

    # وصاحبُها يراها كلَّها — فالإخفاءُ عن الغريب لا إخفاءٌ عن أهلها.
    assert set(hidden.values()) | {live} <= await _visible_listing_ids(world.owner)


# ═══════ ٤ و٥ · التقدّمُ فعلٌ شخصيّ ═══════


@requires_db
@pytest.mark.asyncio
async def test_04_a_researcher_applies_across_the_tenant_boundary(world):
    """**٤ (و٢٠ من المصفوفة) · تقدُّمٌ صحيحٌ عبر الحدّ ينجح.**"""
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    assert application_id in await _visible_application_ids(world.applicant)
    row = await _application_row(world.applicant, application_id)
    assert row["status"] == "pending"
    assert row["decided_by"] is None and row["decided_at"] is None


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


@requires_db
@pytest.mark.asyncio
async def test_05c_an_application_is_born_pending(world):
    """ولا يُولد التطبيقُ مُرشَّحًا ولا محسومًا.

    **ولمَ مُشغِّلٌ لا سياسة:** `WITH CHECK` ترى الصفَّ الجديد، فتقدر على
    هذا — لكنّ المُشغِّلَ يحمل المصفوفةَ كلَّها في موضعٍ واحد، فلا تُقرأ
    قاعدةُ النشأة في مكانٍ وقاعدةُ الانتقال في آخر.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    for forged in ("shortlisted", "invited", "declined", "withdrawn"):
        with pytest.raises(DBAPIError) as caught:
            await _apply_raw(world.applicant, opportunity_id, status=forged)
        assert "born pending" in str(caught.value) or "check" in str(caught.value).lower(), \
            f"حالُ نشأةٍ مزوَّرةٌ مرّت: {forged}"


# ═══════ ٦–٨ · خصوصيّةُ المتقدّمين ═══════


@requires_db
@pytest.mark.asyncio
async def test_06_07_08_an_applicant_sees_only_their_own(world):
    """**٦ و٧ و٨ (و٢٤ من المصفوفة) · كلٌّ يرى تقدُّمَه، ولا يرى غيرَه.**

    و«غيرُه» ثلاثةٌ: زميلٌ في مستأجره تقدّم لنفس الفرصة، وغريبٌ في مستأجر
    الفرصة، وغريبٌ عبر المستأجرين.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    mine = await _apply(world.applicant, opportunity_id)
    theirs = await _apply(world.applicant2, opportunity_id)

    assert await _visible_application_ids(world.applicant) == {mine}
    assert await _visible_application_ids(world.applicant2) == {theirs}
    # غريبٌ في مستأجر الفرصة.
    assert await _visible_application_ids(world.stranger) == set()
    # وعضوٌ في البحث بلا تفويضِ فريق.
    assert await _visible_application_ids(world.plain) == set()
    # وغريبٌ عابرٌ للمستأجرين لم يتقدّم — وهو حدٌّ ثالثٌ لا يُستنتج من
    # الأوّلين: لا عضويّةَ له ولا مستأجرَ مشترك.
    assert await _visible_application_ids(world.outsider) == set()


# ═══════ ٩–١٤ · مَن يرى المتقدّمين ═══════


@requires_db
@pytest.mark.asyncio
async def test_09_the_verified_owner_sees_the_applications(world):
    """**٩ (و٢٥ من المصفوفة) · صاحبُ البحث يرى من تقدّم إلى فرصته.**"""
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
    with pytest.raises(DBAPIError):
        await _make_opportunity(world.plain, world.project_id, title="بلا تفويض")


@requires_db
@pytest.mark.asyncio
async def test_11b_manage_team_without_the_view_baseline_is_denied(world):
    """**و`manage_team` بلا أساسِ `view_project` لا تُفوّض.**

    وهذا مرآةُ ما قرّره RC-T1A في `project_ids_with`: صلاحيةٌ مُفصَّلةٌ
    بلا أساسِ الرؤية صفٌّ غيرُ مكتمل، لا سلطةٌ أعلى من الرؤية.
    """
    from sqlalchemy.exc import DBAPIError

    partial = await _second_user(world.owner["tenant_id"],
                                 email=f"half-{world.suffix}@example.test")
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
    """**١٢ و١٣ (و٢٣ من المصفوفة) · الإيقافُ والإزالةُ يقطعان في الحال.**

    ولا يُنتظر انتهاءُ رمزٍ ولا تحديثُ ذاكرة: الشرطُ
    `access_state = 'active'` يُقرأ في كلّ استعلام.
    """
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    private_id = await _make_opportunity(
        world.owner, world.project_id, status="draft",
        starts_at=None, ends_at=None, title="مسوّدةُ الفريق")
    application_id = await _apply(world.applicant, opportunity_id)

    assert await _visible_application_ids(world.manager) == {application_id}
    assert private_id in await _visible_listing_ids(world.manager)
    assert opportunity_id in await _visible_owner_ids(world.manager)

    await _set_access(world, world.manager_member, state)

    assert await _manages(world.manager, world.project_id) is False
    assert await _visible_application_ids(world.manager) == set()
    assert await _visible_owner_ids(world.manager) == set()
    # **ويعود باحثًا كأيّ باحث**: المفتوحُ يُكتشف، والمسوّدةُ لا.
    seen = await _visible_listing_ids(world.manager)
    assert opportunity_id in seen
    assert private_id not in seen, "المُوقَفُ ما زال يرى ما لا يُكتشف"


@requires_db
@pytest.mark.asyncio
async def test_14_a_manager_of_another_project_is_denied(world):
    """**١٤ · وتفويضُ الفريق مقيَّدٌ ببحثه.**"""
    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    assert await _manages(world.other_manager, world.other_project_id) is True
    assert await _manages(world.other_manager, world.project_id) is False
    assert await _visible_application_ids(world.other_manager) == set()
    assert await _visible_owner_ids(world.other_manager) == set()


# ═══════ ١٥–١٧ · السياقُ الناقصُ والمشوَّهُ يفشل آمنًا ═══════


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
    assert await _visible_owner_ids(mixed) == set()

    reversed_mix = {"tenant_id": world.owner["tenant_id"],
                    "user_id": world.applicant["user_id"]}
    assert await _manages(reversed_mix, world.project_id) is False
    assert await _visible_owner_ids(reversed_mix) == set()


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
        RecruitmentOpportunityListing,
    )

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    async with tenant_session(world.owner["tenant_id"]) as session:
        assert (await session.execute(text("SELECT app_current_actor()"))).scalar_one() is None
        for entity in (RecruitmentOpportunity.id,
                       RecruitmentOpportunityListing.opportunity_id,
                       RecruitmentApplication.id):
            assert (await session.execute(select(entity))).scalars().all() == []
        assert (await session.execute(
            text(f"SELECT count(*) FROM {PUBLIC_VIEW}"))).scalar_one() == 0

    # ولا كتابةَ نسبٍ بلا فاعل.
    async with tenant_session(world.owner["tenant_id"]) as session:
        session.add(RecruitmentOpportunity(
            tenant_id=world.owner["tenant_id"], project_id=world.project_id,
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


# ═══════ ١٨ و١٩ · المجمَّعُ لا ينقل سياقًا بين معاملتين ═══════


@requires_db
@pytest.mark.asyncio
async def test_18_19_a_reused_pooled_connection_carries_no_previous_context(
    two_tenants,
):
    """**١٨ و١٩ (و٢٦ من المصفوفة) · الاتصالُ نفسُه لا يحمل فاعلًا ولا مستأجرًا.**

    و`set_config(..., true)` محليّةٌ بالمعاملة — لكنّ الدعوى تُثبَت على
    اتصالٍ **مُعادٍ بعينه**: يُثبَّت `pg_backend_pid()` متطابقًا في
    المعاملات الثلاث، وإلّا لأثبت الفحصُ نظافةَ اتصالٍ جديدٍ لا نظافةَ
    إعادةِ استعمال.
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


# ═══════ ٢٠ · لا تطبيقانِ قائمان ═══════


@requires_db
@pytest.mark.asyncio
async def test_20_a_second_active_application_is_refused_by_the_database(world):
    """**٢٠ (و٢٢ من المصفوفة) · والمنعُ في القاعدة لا في الواجهة.**

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

    await _update_application(world.applicant, first,
                              status="withdrawn", withdrawn_at=_now())
    again = await _apply(world.applicant, opportunity_id)
    assert again != first


@requires_db
@pytest.mark.asyncio
async def test_20b_a_withdrawn_row_must_carry_its_time(world):
    """والحالةُ وزمنُها لا يفترقان — وإلّا صار «متى انسحب؟» بلا جواب."""
    from sqlalchemy.exc import IntegrityError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    with pytest.raises(IntegrityError) as caught:
        await _update_application(world.applicant, application_id, status="withdrawn")
    assert "withdrawal_has_a_time" in str(caught.value)


# ═══════ ٢١ · الإسقاطُ لا يحمل ما لا يُعرض ═══════


@requires_db
@pytest.mark.asyncio
async def test_21_the_discovery_projection_names_what_it_shows(world):
    """**٢١ · والإسقاطُ يُسمّي ما يُعرض، ولا يحمل حالًا ولا حذفًا ولا تعديلًا.**

    وهو الآن **راحةٌ لا حدّ**: الحدُّ صار في المخطَّط. ويبقى لأنّه يُسمّي
    المعروضَ صريحًا، ويُقاس بعمودٍ **يُطلَب فيسقط** لا بقائمةٍ تُقرأ.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from athera_api.db import system_session, tenant_session

    await _make_opportunity(world.owner, world.project_id)

    async with system_session() as session:
        columns = set((await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :v"), {"v": PUBLIC_VIEW})).scalars().all())

    forbidden = set(PRIVATE_COLUMNS) | {"status", "deleted_at", "updated_at"}
    assert not (columns & forbidden), f"أعمدةٌ خاصّةٌ في الإسقاط: {columns & forbidden}"
    assert {"id", "title", "description", "openings_count",
            "collaboration_type", "starts_at", "ends_at"} <= columns

    for column in sorted(forbidden):
        async with tenant_session(world.applicant["tenant_id"],
                                  world.applicant["user_id"]) as session:
            with pytest.raises(ProgrammingError):
                await session.execute(text(f"SELECT {column} FROM {PUBLIC_VIEW}"))


@requires_db
@pytest.mark.asyncio
async def test_21b_the_view_is_evaluated_with_the_readers_own_policies(world):
    """والعرضُ `security_invoker` و`security_barrier` — ويُقاس من القاعدة.

    فلو غاب `security_invoker` لقُيّم العرضُ بحقوق مالكه، وقد **قِيس
    بالعضّ** أنّ ذلك يفتح الإسقاطَ لجلسةٍ بلا فاعل. والخيارُ يُتجاهل
    صامتًا على إصدارٍ أقدم من ١٥.
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


# ═══════ ٢٢ · ولا تجاوزَ للعزل في هذا المسار ═══════


@requires_db
@pytest.mark.asyncio
async def test_22_the_whole_path_runs_without_bypassrls(world):
    """**٢٢ (و٢٧ من المصفوفة) · والدورُ الذي أثبت كلَّ ما سبق لا يتجاوز.**"""
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
    هذه الحزمة**: ما يُثبت عن العزل يُثبت بالدور الذي يعمل به الإنتاج.
    """
    for path in (API / "models" / "recruitment.py", MIGRATION):
        source = path.read_text(encoding="utf-8").upper()
        assert "BYPASSRLS" not in source, f"تجاوزٌ مذكورٌ في {path.name}"

    own = pathlib.Path(__file__).read_text(encoding="utf-8")
    for forbidden in ("ATHERA_TEST_BYPASSRLS", "bypassing_rls"):
        hits = [line for line in own.splitlines()
                if forbidden in line and "forbidden" not in line]
        assert hits == [], f"الحزمةُ تلمس {forbidden}: {hits}"


# ════════════ سلطةُ التعديل: مصفوفةُ الانتقالات ════════════
#
# **وهذا ما لا تقدر عليه RLS**: `WITH CHECK` ترى الصفَّ الجديد ولا ترى
# القديم. فسياسةٌ تقول «صاحبُه يعدّله» كانت تسمح له بكلّ ما دونه.


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("forbidden_state", ["shortlisted", "declined", "invited"])
async def test_a1_an_applicant_never_awards_themselves_a_decision(world, forbidden_state):
    """**٣ و٤ و٥ من المصفوفة · ولا يُرشّح أحدٌ نفسَه ولا يرفضها عن نفسه.**

    فالترشيحُ والاعتذارُ والدعوةُ **أحكامٌ على المتقدّم لا أفعالٌ له**.
    وقبل المُشغِّلِ كانت سياسةُ «صاحبُه يعدّله» تكفي لكتابتها كلِّها.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    with pytest.raises(DBAPIError) as caught:
        await _update_application(world.applicant, application_id,
                                  status=forbidden_state)
    message = str(caught.value)
    assert "self-awarded" in message or "invited_needs_an_invitation" in message, message

    assert (await _application_row(world.applicant, application_id))["status"] == "pending"


@requires_db
@pytest.mark.asyncio
async def test_a2_an_applicant_writes_no_decision_columns(world):
    """**٨ من المصفوفة · ولا يكتب صاحبُ التطبيق حسمًا ولا كاتبَه.**"""
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    for columns in ({"decided_by": str(world.applicant["user_id"])},
                    {"decided_at": _now()},
                    {"decided_by": str(world.owner["user_id"]), "decided_at": _now()}):
        with pytest.raises(DBAPIError) as caught:
            await _update_application(world.applicant, application_id, **columns)
        assert "writes no decision" in str(caught.value), str(caught.value)

    row = await _application_row(world.applicant, application_id)
    assert row["decided_by"] is None and row["decided_at"] is None


@requires_db
@pytest.mark.asyncio
async def test_a3_the_identity_of_an_application_is_immutable(world):
    """**٦ و٧ من المصفوفة · ولا تُنقل تقدُّمًا ولا تُبدّل هويّةَ صاحبه.**

    وأخطرُها نقلُ `opportunity_id`: تقدُّمٌ قُبل على بابٍ مفتوحٍ يُنقل إلى
    فرصةٍ أخرى **فيتجاوز شرطَ القبول كلَّه** — ويصير المتقدّمُ مرشَّحًا في
    بحثٍ لم يتقدّم إليه.
    """
    from sqlalchemy.exc import DBAPIError

    first = await _make_opportunity(world.owner, world.project_id, title="الأولى")
    second = await _make_opportunity(world.owner, world.project_id, title="الثانية")
    application_id = await _apply(world.applicant, first)

    attempts = (
        ("opportunity_id", {"opportunity_id": str(second)}),
        ("applicant_user_id", {"applicant_user_id": str(world.applicant2["user_id"])}),
        ("applicant_tenant_id", {"applicant_tenant_id": str(world.owner["tenant_id"])}),
        ("created_at", {"created_at": _now()}),
    )
    for label, columns in attempts:
        with pytest.raises(DBAPIError) as caught:
            await _update_application(world.applicant, application_id, **columns)
        assert "identity" in str(caught.value), f"{label}: {caught.value}"

    # ونصُّ صاحبه لا يُعدَّل بعد الإرسال — لا بيده ولا بيد مديرٍ قرأه.
    for slot in (world.applicant, world.owner):
        with pytest.raises(DBAPIError) as caught:
            await _update_application(slot, application_id, message="نصٌّ آخر")
        assert "not edited after submission" in str(caught.value)

    row = await _application_row(world.applicant, application_id)
    assert row["opportunity_id"] == first
    assert row["applicant_user_id"] == world.applicant["user_id"]
    assert row["applicant_tenant_id"] == world.applicant["tenant_id"]


@requires_db
@pytest.mark.asyncio
async def test_a4_the_applicant_may_withdraw_and_only_withdraw(world):
    """وما مُنع ليس كلَّ شيء: الانسحابُ فعلُ صاحبه، ويقع.

    وحارسٌ يمنع كلَّ تعديلٍ لم يكن حارسًا بل تعطيلًا — فيُقاس الطرفُ
    الآخر: الانسحابُ ينجح، ويُرفض من حالٍ غيرِ قائمة.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    await _update_application(world.applicant, application_id,
                              status="withdrawn", withdrawn_at=_now())
    row = await _application_row(world.applicant, application_id)
    assert row["status"] == "withdrawn" and row["withdrawn_at"] is not None

    # **ولا يُعاد كتابةُ وقتِ انسحابٍ وقع** — أثرٌ يُقرأ في نزاعٍ على أسبقيّة.
    with pytest.raises(DBAPIError) as caught:
        await _update_application(world.applicant, application_id,
                                  withdrawn_at=_now() - _hours(72))
    assert "written once" in str(caught.value)

    # ومن «مُرشَّح» ينسحب كذلك — فالترشيحُ ليس قيدًا على صاحبه.
    shortlisted_op = await _make_opportunity(
        world.owner, world.project_id, title="للانسحاب بعد الترشيح")
    shortlisted_app = await _apply(world.applicant, shortlisted_op)
    await _update_application(world.owner, shortlisted_app, status="shortlisted",
                              decided_at=_now(),
                              decided_by=str(world.owner["user_id"]))
    await _update_application(world.applicant, shortlisted_app,
                              status="withdrawn", withdrawn_at=_now())
    assert (await _application_row(
        world.applicant, shortlisted_app))["status"] == "withdrawn"

    # ولا انسحابَ من حالٍ ليست قائمة: يُعتذر عن متقدّمٍ ثمّ يحاول الانسحاب.
    second = await _make_opportunity(world.owner, world.project_id, title="ثانية")
    other = await _apply(world.applicant, second)
    await _update_application(world.owner, other, status="declined",
                              decided_at=_now(),
                              decided_by=str(world.owner["user_id"]))
    with pytest.raises(DBAPIError) as caught:
        await _update_application(world.applicant, other,
                                  status="withdrawn", withdrawn_at=_now())
    assert "only a live application" in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_a5_the_manager_transition_matrix_is_exactly_what_was_written(world):
    """ومصفوفةُ المدير تُقاس **مسموحًا ومرفوضًا** لا مسموحًا وحده.

    `pending → shortlisted | declined` و`shortlisted → declined | invited`،
    ولا غيرُها. وحارسٌ يُثبت المسموحَ وحده يمرّ على مصفوفةٍ مفتوحة.
    """
    from sqlalchemy.exc import DBAPIError

    from athera_api.models.recruitment import MANAGER_TRANSITIONS

    # ── المسموح: كلُّ زوجٍ في المصفوفة يقع فعلًا ──
    #
    # **ويُقاس عددُها أيضًا**: هذا الفحصُ يمرّ على ما في المصفوفة، فزوجٌ
    # يُزاد سهوًا يصير «مسموحًا» هنا بلا أن ينبّه أحد. والعددُ ثلاثةٌ
    # مكتوبةٌ في التكليف، و`test_a9c` يقابل الأزواجَ بأعيانها.
    assert len(MANAGER_TRANSITIONS) == 3, MANAGER_TRANSITIONS

    for before, after in MANAGER_TRANSITIONS:
        opportunity_id = await _make_opportunity(
            world.owner, world.project_id, title=f"{before}->{after}")
        application_id = await _apply(world.applicant, opportunity_id)
        if before != "pending":
            await _update_application(
                world.owner, application_id, status=before,
                decided_at=_now(), decided_by=str(world.owner["user_id"]))
        await _update_application(
            world.owner, application_id, status=after, decided_at=_now(),
            decided_by=str(world.owner["user_id"]))
        row = await _application_row(world.owner, application_id)
        assert row["status"] == after, (before, after)
        assert row["decided_by"] == world.owner["user_id"]

    # ── والمرفوض: ما ليس في المصفوفة ──
    #
    # و«مدعوّ» لها فحصٌ قائمٌ بذاته أدناه: هي المفردةُ الوحيدةُ المحجوزة،
    # فلا تُخلط بانتقالٍ مرفوضٍ لسببٍ آخر.
    refused = (
        ("declined", "shortlisted"),  # ولا يُنقض اعتذارٌ صدر
        ("declined", "pending"),
        ("shortlisted", "pending"),
    )
    for before, after in refused:
        opportunity_id = await _make_opportunity(
            world.owner, world.project_id, title=f"x{before}->{after}")
        application_id = await _apply(world.applicant, opportunity_id)
        if before != "pending":
            await _update_application(
                world.owner, application_id, status=before,
                decided_at=_now(), decided_by=str(world.owner["user_id"]))
        with pytest.raises(DBAPIError) as caught:
            await _update_application(
                world.owner, application_id, status=after, decided_at=_now(),
                decided_by=str(world.owner["user_id"]))
        assert "no such transition" in str(caught.value), (before, after, caught.value)


@requires_db
@pytest.mark.asyncio
async def test_a6_a_decision_names_the_acting_session(world):
    """ومن حسم يُنسب إليه ما حسم — **بفاعل الجلسة لا بما كُتب في الطلب**.

    فمديرٌ يكتب `decided_by` باسم زميله يصنع أثرًا يُقرأ في نزاعٍ بعد
    سنة، ويقول إنّ غيرَه قرّر.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    with pytest.raises(DBAPIError) as caught:
        await _update_application(
            world.owner, application_id, status="shortlisted",
            decided_at=_now(), decided_by=str(world.manager["user_id"]))
    assert "names its author" in str(caught.value)

    # وحسمٌ بلا وقتٍ مرفوضٌ كذلك.
    with pytest.raises(DBAPIError) as caught:
        await _update_application(
            world.owner, application_id, status="shortlisted",
            decided_by=str(world.owner["user_id"]))
    assert "a decision has a time" in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_a7_the_manager_never_withdraws_on_the_applicants_behalf(world):
    """**١٢ من المصفوفة · والانسحابُ فعلُ صاحبه لا حكمٌ عليه.**

    فمديرٌ يكتب «انسحب» يمحو تقدُّمَ باحثٍ ويُسجّله انصرافًا منه.
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    with pytest.raises(DBAPIError) as caught:
        await _update_application(world.owner, application_id,
                                  status="withdrawn", withdrawn_at=_now())
    assert "applicant's own act" in str(caught.value)
    assert (await _application_row(world.owner, application_id))["status"] == "pending"


@requires_db
@pytest.mark.asyncio
async def test_a8_the_manager_never_rewrites_applicant_identity(world):
    """**٩ و١٠ و١١ من المصفوفة · ولا ينتحل المديرُ متقدّمًا ولا ينقل تقدُّمَه.**

    وهذا أخطرُ من نظيره عند المتقدّم: المديرُ يملك سلطةَ تعديلٍ حقيقيةً
    على الصفّ، فلا يمنعه إلّا المُشغِّل.
    """
    from sqlalchemy.exc import DBAPIError

    first = await _make_opportunity(world.owner, world.project_id, title="الأولى")
    second = await _make_opportunity(world.owner, world.project_id, title="الثانية")
    application_id = await _apply(world.applicant, first)

    attempts = (
        {"applicant_user_id": str(world.applicant2["user_id"])},
        {"applicant_tenant_id": str(world.owner["tenant_id"])},
        {"opportunity_id": str(second)},
    )
    for columns in attempts:
        with pytest.raises(DBAPIError) as caught:
            await _update_application(world.owner, application_id, **columns)
        assert "identity" in str(caught.value), (columns, caught.value)

    row = await _application_row(world.owner, application_id)
    assert row["applicant_user_id"] == world.applicant["user_id"]
    assert row["opportunity_id"] == first


# ════════ «مدعوّ» محجوزةٌ لـRC-T1C — ولا طريقَ إليها ════════
#
# **والقرارُ قرارُ منتجٍ لا نقصُ تنفيذ.** فالدعوةُ الصحيحة دعوةٌ **لصاحب
# هذا التطبيق بعينه**، و`ProjectInvitation` اليوم محلّيّةُ المستأجر:
# إصدارُها يبحث عن الحساب داخل مستأجر البحث. وفرصُ البحث عابرةٌ
# للمستأجرين قصدًا — فباحثٌ في مؤسسةٍ يتقدّم إلى بحثٍ في أخرى.
#
# فالربطُ الصحيح تصميمُ خدمةٍ في RC-T1C، **ولا يُوسَّع سلوكُ الدعوات
# المحلّيّ خِلسةً داخل دفعةٍ أمنية**.


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("before", ["pending", "shortlisted"])
@pytest.mark.parametrize(
    "invitation",
    ["none", "forged", "same_project", "other_project", "other_candidate"])
async def test_a9_invited_has_no_transition_in_this_stage(world, before, invitation):
    """**ولا انتقالَ إلى «مدعوّ» في RC-T1B — ولا تُجدي دعوةٌ صحيحة.**

    ‏**والمانعُ هو المصفوفةُ لا صحّةُ الدعوة.** وهذا هو مقصودُ الفحص:
    فلو كان المانعُ «دعوتُك غير صالحة» لظنّ من يأتي بعدُ أنّ دعوةً صالحةً
    تكفي — وهي لا تكفي، لأنّ **صلاحيةَ الدعوة ليست هي المطلوب**: المطلوبُ
    أن تكون الدعوةُ لصاحب هذا التطبيق بعينه، وذاك ما لا يُثبته المخطَّطُ
    اليوم.

    فتُقاس عشرُ حالاتٍ (حالانِ قبل × خمسُ دعوات)، ومنها **دعوةٌ حقيقيةٌ
    حيّةٌ في بحثِ الفرصة نفسِه** — والرفضُ واحدٌ في الجميع: «لا انتقالَ
    كهذا».
    """
    from sqlalchemy.exc import DBAPIError

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)
    if before == "shortlisted":
        await _update_application(
            world.owner, application_id, status="shortlisted",
            decided_at=_now(), decided_by=str(world.owner["user_id"]))

    columns = {"status": "invited", "decided_at": _now(),
               "decided_by": str(world.owner["user_id"])}
    tag = uuid.uuid4().hex[:8]
    if invitation == "forged":
        columns["invitation_id"] = str(uuid.uuid4())
    elif invitation == "same_project":
        # **دعوةٌ حقيقيةٌ حيّةٌ في البحث نفسِه** — وهي الحالةُ الحاسمة.
        columns["invitation_id"] = str(await _issue_invitation(
            world.owner, world.project_id, email=f"ok-{tag}@example.test"))
    elif invitation == "other_project":
        columns["invitation_id"] = str(await _issue_invitation(
            world.owner, world.other_project_id, email=f"of-{tag}@example.test"))
    elif invitation == "other_candidate":
        # دعوةٌ صحيحةٌ في البحث نفسِه **لكنّها لمرشَّحٍ آخر** — وهو العطبُ
        # الذي رفعته المراجعة: تطبيقُ «أ» يُوسَم مدعوًّا بدعوةِ «ب».
        columns["invitation_id"] = str(await _issue_invitation(
            world.owner, world.project_id, email=f"other-{tag}@example.test"))

    with pytest.raises(DBAPIError) as caught:
        await _update_application(world.owner, application_id, **columns)
    message = str(caught.value)
    assert "no such transition" in message, (
        f"«مدعوّ» بلغت الصفَّ بدعوةٍ من نوع {invitation!r} من حال {before!r}: "
        f"{message}")

    row = await _application_row(world.owner, application_id)
    assert row["status"] == before
    assert row["invitation_id"] is None


@requires_db
@pytest.mark.asyncio
async def test_a9b_no_row_in_this_stage_can_hold_the_reserved_state(world):
    """ولا مولودَ «مدعوًّا» أيضًا — فالبابُ مسدودٌ من طرفيه.

    فالانتقالُ ممنوعٌ بالمصفوفة، **والنشأةُ ممنوعةٌ بالمُشغِّل**: الصفُّ
    يُولد في الانتظار ومعه صفرُ دعواتٍ وصفرُ حسم. فلا مدخلَ ثالثًا.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import system_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    with pytest.raises(DBAPIError):
        await _apply_raw(world.applicant, opportunity_id, status="invited")

    # ولا صفَّ في القاعدة كلِّها يحمل المفردةَ المحجوزة.
    async with system_session() as session:
        held = (await session.execute(text(
            f"SELECT count(*) FROM {APPLICATIONS} WHERE status = 'invited' "
            "   OR invitation_id IS NOT NULL"))).scalar_one()
    assert held == 0, f"{held} صفًّا بلغ المفردةَ المحجوزة"


def test_a9c_the_reserved_state_is_no_transition_target_anywhere():
    """والمفردةُ باقيةٌ في المخطَّط، **ولا هدفَ لها في أيّ مصفوفة**.

    ويُقاس على الترحيل والنموذج ونصِّ المُشغِّل الثلاثةِ: فمصفوفةٌ تُعدَّل
    في موضعٍ وتُنسى في آخر تفتح البابَ من حيث لا يُنظر.

    و`APPLICANT_TRANSITIONS` تحمل `invited → withdrawn` اشتقاقًا من حالات
    «القائم» — **وذاك غيرُ قابلٍ للبلوغ** لأنّ لا صفَّ يصل «مدعوّ» أصلًا،
    ويبقى كي لا يُعدَّل شيءٌ يوم تُفتح.
    """
    import importlib.util

    from athera_api.models import recruitment

    spec = importlib.util.spec_from_file_location("m0034", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for label, matrix in (("النموذج", recruitment.MANAGER_TRANSITIONS),
                          ("الترحيل", module.MANAGER_TRANSITIONS)):
        assert matrix == (("pending", "shortlisted"), ("pending", "declined"),
                          ("shortlisted", "declined")), f"مصفوفةُ {label}"
        assert not any(after == "invited" for _, after in matrix), \
            f"«مدعوّ» هدفٌ في مصفوفة {label}"

    # ونصُّ المُشغِّل هو ما يعمل — فيُسأل هو أيضًا.
    guard = module.APPLICATION_GUARD_FN
    assert "('shortlisted','invited')" not in guard
    assert "('pending','invited')" not in guard
    for before, after in module.MANAGER_TRANSITIONS:
        assert f"('{before}','{after}')" in guard, (before, after)

    # والمفردةُ باقيةٌ في المخطَّط كي لا يُهاجَر مرّتين.
    assert "invited" in recruitment.APPLICATION_STATES
    assert "RC-T1C" in (API / "models" / "recruitment.py").read_text(encoding="utf-8")


@requires_db
@pytest.mark.asyncio
async def test_a10_recruitment_creates_no_member_no_authorship_no_credit(world):
    """**ولا عضويّةَ ولا تأليفَ ولا أدوارَ CRediT من الاستقطاب — ولا بدعوة.**

    فالمسارُ المُقرَّر: يُرشَّح المتقدّم، ثمّ تُصدر `ProjectInvitation`
    له بعينه في RC-T1C، ثمّ **يقبلها هو**، وحينها تُنشأ العضويّة. وهذه
    الدفعةُ لا تبلغ الخطوةَ الثانية.

    ويُقاس ما يقع فعلًا: إصدارُ دعوةٍ حقيقيةٍ **لا يُنشئ عضوًا**، ومحاولةُ
    الترشيح ثمّ «مدعوّ» لا تُنشئ عضوًا، ولا تُغيّر تأليفًا ولا أدوارًا —
    ولا شيءَ من ذلك يُقاس على النصّ، بل على الصفوف قبل وبعد.
    """
    from sqlalchemy import select
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember

    async def team() -> list[tuple]:
        async with tenant_session(world.owner["tenant_id"],
                                  world.owner["user_id"]) as session:
            rows = (await session.execute(
                select(ProjectMember.id, ProjectMember.user_id,
                       ProjectMember.access_state, ProjectMember.is_author,
                       ProjectMember.author_position, ProjectMember.credit_roles)
                .where(ProjectMember.project_id == world.project_id)
                .order_by(ProjectMember.id))).all()
        return [tuple(r) for r in rows]

    before = await team()
    assert before, "التجهيزةُ بلا فريقٍ — فالمقارنةُ لا تُثبت شيئًا"

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)
    await _update_application(world.owner, application_id, status="shortlisted",
                              decided_at=_now(),
                              decided_by=str(world.owner["user_id"]))

    # **ودعوةٌ حقيقيةٌ تُصدر ولا تُقبل** — فلا عضوَ منها.
    invitation_id = await _issue_invitation(
        world.owner, world.project_id, email=f"chosen-{world.suffix}@example.test")
    assert invitation_id
    assert await team() == before, "إصدارُ دعوةٍ أنشأ عضويّة"

    # والمحاولةُ تُرفض، والفريقُ كما كان.
    with pytest.raises(DBAPIError):
        await _update_application(world.owner, application_id, status="invited",
                                  decided_at=_now(),
                                  decided_by=str(world.owner["user_id"]),
                                  invitation_id=str(invitation_id))
    assert await team() == before, "محاولةُ «مدعوّ» غيّرت الفريق"

    # ولا تأليفَ ولا أدوارَ CRediT تحرّكت — والمقارنةُ تحملهما عمودًا عمودًا.
    row = await _application_row(world.owner, application_id)
    assert row["status"] == "shortlisted"
    assert row["invitation_id"] is None


# ════════════ نسبُ الفرصة: يُكتب مرّةً ولا يُنقل ════════════


@requires_db
@pytest.mark.asyncio
async def test_b1_an_opportunity_is_credited_to_the_session_that_wrote_it(world):
    """**١٣ من المصفوفة · ولا تُنسب فرصةٌ إلى غير كاتبها.**"""
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as caught:
        await _make_opportunity(world.owner, world.project_id,
                                created_by=world.manager, title="نسبٌ مزوَّر")
    assert "row-level security" in str(caught.value).lower()


@requires_db
@pytest.mark.asyncio
async def test_b2_the_provenance_of_an_opportunity_has_no_edit_path(world):
    """**١٤ من المصفوفة · والمستأجرُ والبحثُ والمنشئ ثوابتُ — بلا حارس.**

    فلا سياسةَ تعديلٍ على جدول النسب **ولا صلاحيةَ تعديل**، كما فعل 0003
    بسجلّ التدقيق. وثباتُها **غيابُ طريقٍ لا حارسٌ يُفحَص** — وهو أقوى:
    حارسٌ يُنسى تعديلُه، وطريقٌ معدومٌ لا يُسلَك.

    والمديرُ يعدّل **الإعلانَ** بحرّية: نصَّه وحالَه ونافذتَه.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import system_session, tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)

    async with system_session() as session:
        for privilege in ("UPDATE", "DELETE"):
            granted = (await session.execute(text(
                f"SELECT has_table_privilege('athera_app', :t, '{privilege}')"),
                {"t": OWNERS})).scalar_one()
            assert granted is False, f"صلاحيةُ {privilege} قائمةٌ على جدول النسب"

    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text(f"UPDATE {OWNERS} SET project_id = :p WHERE id = :i"),
                {"p": str(world.other_project_id), "i": str(opportunity_id)})
        assert "permission denied" in str(caught.value).lower()

    # وما بقي مسموحًا: تعديلُ الإعلان.
    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        await session.execute(
            text(f"UPDATE {LISTINGS} SET status = 'closed' WHERE opportunity_id = :i"),
            {"i": str(opportunity_id)})
    assert opportunity_id not in await _discoverable_ids(world.applicant)


@requires_db
@pytest.mark.asyncio
async def test_b3_a_listing_belongs_to_the_opportunity_it_was_written_for(world):
    """ولا يُنقل إعلانٌ إلى فرصةٍ أخرى — فنصٌّ مُعلَنٌ يُنقل إلى بحثٍ لم يكتبه."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session

    first = await _make_opportunity(world.owner, world.project_id, title="الأولى")
    second = await _make_opportunity(world.owner, world.project_id, title="الثانية")

    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        with pytest.raises(DBAPIError) as caught:
            await session.execute(
                text(f"UPDATE {LISTINGS} SET opportunity_id = :b "
                     "WHERE opportunity_id = :a"),
                {"a": str(first), "b": str(second)})
    assert "belongs to the opportunity" in str(caught.value)


# ════════════ بابٌ مفتوحٌ الآن — شرطُ القبول ════════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,kwargs",
    [
        ("draft", dict(status="draft", starts_at=None, ends_at=None)),
        ("scheduled", dict(status="scheduled")),
        ("closed", dict(status="closed")),
        ("deleted", dict(status="deleted")),
        ("expired", dict(status="open")),
    ],
)
async def test_c1_no_application_reaches_a_door_that_is_not_open(world, label, kwargs):
    """**١٥–١٩ من المصفوفة · ومعرّفٌ عُرف وقتَ الفتح لا يصير مفتاحًا بعده.**

    **وهذا لم يكن مغلقًا.** كانت سياسةُ الإدراج تُثبت هويّةَ المتقدّم
    ومؤسستَه، **ولا تسأل عن الباب**. فمن حفظ معرّفَ فرصةٍ مفتوحةٍ كان
    يتقدّم إليها بعد إغلاقها بشهر — ولا فرقَ عنده بين مسوّدةٍ لم تُنشر
    وبابٍ انقضى.

    وشرطُ القبول **نفسُ نصِّ شرطِ الاكتشاف**: ما لا يُرى لا يُتقدَّم إليه.
    """
    from sqlalchemy.exc import DBAPIError

    if label == "scheduled":
        kwargs = dict(kwargs, starts_at=_now() + _hours(48),
                      ends_at=_now() + _hours(96))
    elif label == "deleted":
        kwargs = dict(kwargs, deleted_at=_now())
    elif label == "expired":
        kwargs = dict(kwargs, starts_at=_now() - _hours(96),
                      ends_at=_now() - _hours(1))

    opportunity_id = await _make_opportunity(
        world.owner, world.project_id, title=f"باب {label}", **kwargs)

    with pytest.raises(DBAPIError) as caught:
        await _apply(world.applicant, opportunity_id)
    assert "row-level security" in str(caught.value).lower(), str(caught.value)

    # والمسارُ الخامُّ كذلك — فلا `RETURNING` يُثبت بندًا غيرَ المقصود.
    with pytest.raises(DBAPIError):
        await _apply_raw(world.applicant, opportunity_id)

    assert await _visible_application_ids(world.applicant) == set()


@requires_db
@pytest.mark.asyncio
async def test_c2_a_door_that_closes_mid_flight_refuses_the_next_applicant(world):
    """والشرطُ يُقرأ عند الكتابة لا عند العرض — فإغلاقٌ يعمل في الحال.

    فلو قِيس مرّةً وحُفظ لصار «كانت مفتوحةً حين نظرتُ» عذرًا مقبولًا.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    first = await _apply(world.applicant, opportunity_id)
    assert first

    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        await session.execute(
            text(f"UPDATE {LISTINGS} SET status = 'closed' WHERE opportunity_id = :i"),
            {"i": str(opportunity_id)})

    with pytest.raises(DBAPIError):
        await _apply(world.applicant2, opportunity_id)
    assert await _visible_application_ids(world.applicant2) == set()

    # ومن تقدّم قبل الإغلاق يبقى تقدُّمُه، وينسحب إن شاء.
    assert await _visible_application_ids(world.applicant) == {first}
    await _update_application(world.applicant, first,
                              status="withdrawn", withdrawn_at=_now())


# ═══════ حرّاسُ البنية: ما لا تلتقطه فحوصُ السلوك ═══════


@requires_db
@pytest.mark.asyncio
async def test_no_policy_on_the_new_tables_is_broadly_true(db_ready):
    """**ولا `USING (true)` على سطحِ الاستقطاب، ولا سياسةَ حذفٍ لأحد.**

    فسياسةٌ شاملةٌ تُغني عن كلّ ما سبق في سطرٍ واحد، ولا يظهر أثرُها في
    فحصٍ سلوكيٍّ إلّا حين يُسأل السؤالُ الذي لم يُسأل.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT c.relname, p.polname, p.polcmd, "
            "       coalesce(pg_get_expr(p.polqual, p.polrelid), '') AS q, "
            "       coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '') AS w "
            "FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid "
            "WHERE c.relname IN (:o, :l, :a)"),
            {"o": OWNERS, "l": LISTINGS, "a": APPLICATIONS})).all()

    covered = {row[0] for row in rows}
    assert covered == {OWNERS, LISTINGS, APPLICATIONS}, f"جدولٌ بلا سياسة: {covered}"
    for table, name, cmd, using, check in rows:
        for expression in (using, check):
            assert expression.strip().lower() not in ("true", "(true)"), \
                f"سياسةٌ شاملة: {table}.{name}"
        assert cmd != "d", f"سياسةُ حذفٍ مكتوبة: {name}"
        assert cmd != "*", f"سياسةٌ شاملةُ الأفعال تشمل الحذفَ ضمنًا: {name}"


@requires_db
@pytest.mark.asyncio
async def test_a_hard_delete_is_unreachable_from_the_application_role(db_ready):
    """والحذفُ الصلبُ ممنوعٌ بطبقتين: لا سياسةَ له، **ولا صلاحيةَ** له."""
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        for table in (OWNERS, LISTINGS, APPLICATIONS):
            granted = (await session.execute(text(
                "SELECT has_table_privilege('athera_app', :t, 'DELETE')"),
                {"t": table})).scalar_one()
            assert granted is False, f"صلاحيةُ حذفٍ قائمةٌ على {table}"
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
    طبقتان تُقاسان كلٌّ على حدة: لا صلاحيةَ حذفٍ لدور التطبيق (أُثبِت
    بالمحاولة: `permission denied` لا انتهاكَ مفتاح)، والمفتاحُ `RESTRICT`
    لو مُنحت يومًا.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from athera_api.db import system_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    await _apply(world.applicant, opportunity_id)

    async with system_session() as session:
        with pytest.raises(ProgrammingError) as caught:
            await session.execute(
                text(f"DELETE FROM {OWNERS} WHERE id = :i"),
                {"i": str(opportunity_id)})
    assert "permission denied" in str(caught.value).lower()

    async with system_session() as session:
        rules = set((await session.execute(text(
            "SELECT confdeltype FROM pg_constraint "
            "WHERE conrelid = cast(:a AS regclass) AND contype = 'f' "
            "  AND confrelid = cast(:o AS regclass)"),
            {"a": APPLICATIONS, "o": OWNERS})).scalars().all())
    # و`confdeltype` عمودُ `"char"` — يعود بايتًا.
    assert rules <= {"r", b"r"}, f"مفتاحُ الفرصة ليس RESTRICT بل {rules}"


@requires_db
@pytest.mark.asyncio
async def test_the_authorization_predicates_are_not_security_definer(db_ready):
    """ودوالُّ التفويض **بحقوق مستدعيها** — وذاك شرطُ صحّتها لا تفصيل.

    **وقد جُرّبت `app_manages_project` بـ`SECURITY DEFINER` فلم يتغيّر
    سلوكٌ واحد** — والسببُ أنّ الجداولَ التي تقرؤها عليها `FORCE ROW LEVEL
    SECURITY`، فمالكُها خاضعٌ لسياساتها. فالسببُ ليس ثقبًا قائمًا بل
    **ألّا يتعلّق هذا الضمانُ بجداولَ أخرى**: يكفي أن يسقط `FORCE` عن
    أحدها، أو أن يصير المالكُ دورًا متجاوزًا، ليصير `DEFINER` ثقبًا بحجم
    الدالّة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    names = ("app_manages_project", "app_manages_opportunity",
             "app_opportunity_admits")
    async with system_session() as session:
        for name in names:
            row = (await session.execute(text(
                "SELECT p.prosecdef, p.provolatile, p.proconfig, "
                f"       has_function_privilege('public', '{name}(uuid)', 'EXECUTE'), "
                f"       has_function_privilege('athera_app', '{name}(uuid)', 'EXECUTE') "
                "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
                "WHERE n.nspname = 'public' AND p.proname = :name"),
                {"name": name})).one()
            assert row[0] is False, f"{name} SECURITY DEFINER"
            # و`provolatile` عمودُ `"char"` — يعود بايتًا.
            assert row[1] in ("s", b"s"), f"{name} ليست STABLE: {row[1]!r}"
            assert any("search_path=" in c for c in (row[2] or [])), \
                f"{name} بلا مسارِ بحثٍ مثبَّت"
            assert row[3] is False, f"تنفيذٌ عامٌّ لـ{name}"
            assert row[4] is True, f"دورُ التطبيق لا ينفّذ {name}"


@requires_db
@pytest.mark.asyncio
async def test_the_mutation_guards_are_actually_attached(db_ready):
    """والمُشغِّلُ المكتوبُ غيرُ المُشغِّلِ المربوط — فيُسأل الفهرس.

    فدالّةٌ تُنشأ ولا يُربط بها مُشغِّلٌ حبرٌ على ورق، ومصفوفةُ الانتقالات
    كلُّها تصير تعليقًا.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    expected = {
        (f"trg_{LISTINGS}_guard", LISTINGS),
        (f"trg_{APPLICATIONS}_guard", APPLICATIONS),
    }
    async with system_session() as session:
        rows = set((await session.execute(text(
            "SELECT t.tgname, c.relname FROM pg_trigger t "
            "JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE NOT t.tgisinternal AND c.relname IN (:l, :a)"),
            {"l": LISTINGS, "a": APPLICATIONS})).all())
        assert {(a, b) for a, b in rows} == expected, f"مُشغِّلاتٌ ناقصة: {rows}"

        # ويُربط على الإدراج **والتعديل** معًا في التطبيقات: حالُ النشأة
        # تُقاس عند الإدراج، والمصفوفةُ عند التعديل.
        timing = (await session.execute(text(
            "SELECT t.tgtype::int FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname = :n"), {"n": f"trg_{APPLICATIONS}_guard"})).scalar_one()
        assert timing & 4, "لا يعمل عند الإدراج"   # TRIGGER_TYPE_INSERT
        assert timing & 16, "لا يعمل عند التعديل"  # TRIGGER_TYPE_UPDATE
        assert timing & 2, "ليس BEFORE"            # TRIGGER_TYPE_BEFORE


@requires_db
@pytest.mark.asyncio
async def test_no_constraint_name_on_the_new_tables_was_silently_truncated(db_ready):
    """والاسمُ المقصوصُ لا يُعلن عن نفسه — فيُطابق ما يُنتظر بأعيانه.

    وهو الفخُّ الذي وثّقه 0032: `%(constraint_name)s` يُبادئ الاسمَ باسم
    الجدول، فاسمٌ كُتب كاملًا يُبادأ مرّتين ويُقصّ فوق ٦٣ محرفًا.
    **وقد وقع هذا فعلًا في أوّل كتابةٍ لهذا الترحيل.**
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    expected = {
        "ck_recruitment_opportunity_listings_status_is_known",
        "ck_recruitment_opportunity_listings_window_is_ordered",
        "ck_recruitment_opportunity_listings_openings_are_positive",
        "ck_recruitment_opportunity_listings_open_needs_a_start",
        "ck_recruitment_applications_status_is_known",
        "ck_recruitment_applications_withdrawal_has_a_time",
        "ck_recruitment_applications_invited_needs_an_invitation",
    }
    async with system_session() as session:
        names = set((await session.execute(text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid::regclass::text IN (:o, :l, :a) AND contype = 'c'"),
            {"o": OWNERS, "l": LISTINGS, "a": APPLICATIONS})).scalars().all())

    assert names == expected, f"قيودٌ بأسماءٍ غيرِ متوقّعة: {names ^ expected}"
    assert all(len(name) <= 63 for name in names)


@requires_db
@pytest.mark.asyncio
async def test_the_window_and_the_openings_are_enforced_by_the_database(world):
    """`starts_at < ends_at`، و«مفتوح» يستوجب بدايةً، والشواغرُ موجبة."""
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

    from sqlalchemy import text

    from athera_api.db import tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        with pytest.raises(IntegrityError) as caught:
            await session.execute(
                text(f"UPDATE {LISTINGS} SET openings_count = 0 "
                     "WHERE opportunity_id = :i"), {"i": str(opportunity_id)})
    assert "openings_are_positive" in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_an_unknown_state_is_refused_on_both_tables(world):
    """والمفرداتُ مغلقةٌ في القاعدة لا في التوثيق."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session

    opportunity_id = await _make_opportunity(world.owner, world.project_id)
    application_id = await _apply(world.applicant, opportunity_id)

    async with tenant_session(world.owner["tenant_id"],
                              world.owner["user_id"]) as session:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(f"UPDATE {LISTINGS} SET status = 'paused' "
                     "WHERE opportunity_id = :i"), {"i": str(opportunity_id)})

    with pytest.raises(IntegrityError):
        await _update_application(world.owner, application_id, status="hired")


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
    assert module.MANAGER_TRANSITIONS == recruitment.MANAGER_TRANSITIONS
    assert tuple(module.PROJECT_CREATED_ACTIONS) == \
        tuple(collaboration.PROJECT_CREATED_ACTIONS)
    assert recruitment.MANAGE_RECRUITMENT == "manage_team"
    assert recruitment.MANAGE_RECRUITMENT in module.MANAGES_PROJECT_FN
    assert collaboration.VIEW_PROJECT in module.MANAGES_PROJECT_FN
    # ومصفوفةُ المدير مكتوبةٌ في المُشغِّل لا مُستنبطة.
    for before, after in recruitment.MANAGER_TRANSITIONS:
        assert f"('{before}','{after}')" in module.APPLICATION_GUARD_FN


def test_the_discovery_predicate_is_written_once():
    """وشرطُ الاكتشافِ نصٌّ واحد يخدم السياسةَ والقبولَ والعرض.

    وثلاثُ نسخٍ منه تفترق، وحينها يعرض العرضُ ما لا تسمح به السياسة، أو
    يُقبل تقدُّمٌ على بابٍ لا يُرى — ولا يظهر ذلك في فحصٍ واحد.
    """
    source = MIGRATION.read_text(encoding="utf-8")
    assert source.count("DISCOVERABLE = (") == 1
    assert source.count("{DISCOVERABLE}") == 3, \
        "شرطُ الاكتشاف يُقرأ في ثلاثة مواضع: السياسة، ودالّةُ القبول، والعرض"
    for fragment in ("status = 'open'", "deleted_at IS NULL",
                     "starts_at <= now()", "ends_at > now()"):
        assert fragment in source, f"شرطٌ ناقصٌ في الاكتشاف: {fragment}"


def test_this_stage_adds_no_router_and_no_web_surface():
    """و«فرصُ البحث» لم تبدأ — وهي دعوى تُثبَت لا تُقال.

    **ويُقاس هذا النطاقُ باسمه لا بكلمةٍ عامّة**: `opportunities` و
    `publication-opportunities` صفحتان قائمتان منذ التوليف والرسائل، ولا
    شأنَ لهما بالاستقطاب — وحارسٌ يمنع الكلمةَ يسقط على شيءٍ لم أكتبه.
    """
    routers = API / "routers"
    offenders = [p.name for p in routers.glob("*.py") if "recruitment" in p.name]
    assert offenders == [], f"موجّهٌ في مرحلةٍ لا موجّهَ فيها: {offenders}"

    main = (API / "main.py").read_text(encoding="utf-8")
    assert "recruitment" not in main, "الاستقطابُ مُركَّبٌ في التطبيق"

    web = REPO / "apps" / "web" / "src"
    if web.exists():
        touched = [
            str(path.relative_to(web))
            for path in web.rglob("*.ts*")
            if "recruitment" in path.read_text(encoding="utf-8", errors="ignore").lower()
        ]
        assert touched == [], f"الويبُ يلمس الاستقطاب: {touched}"


def test_nothing_here_creates_membership_authorship_or_credit():
    """**ولا عضويّةَ تُنشأ ولا تأليفَ ولا أدوارَ CRediT من هذا النطاق.**"""
    model = (API / "models" / "recruitment.py").read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")

    for source, label in ((model, "النموذج"), (migration, "الترحيل")):
        for phrase in ("ProjectMember(", "INSERT INTO project_members",
                       "credit_roles", "is_author", "author_position"):
            assert phrase not in source, f"{label} يلمس العضويّة/التأليف: {phrase}"


@requires_db
@pytest.mark.asyncio
async def test_no_employment_vocabulary_entered_the_domain(db_ready):
    """وهذا تعاونٌ بحثيّ لا توظيف — ولا مفرداتَ أجرٍ ولا عقدِ عمل.

    **ويُقاس على المخطَّط لا على النثر.** فرأسُ الوحدة يذكر هذه المفردات
    **منفيّةً** («لا راتبَ ولا عقدَ عمل»)، وحارسٌ يقرأ النصَّ يسقط على
    الجملة التي تمنعها ويطالب بحذف التوثيق.
    """
    from sqlalchemy import text

    from athera_api.db import system_session
    from athera_api.models import recruitment

    forbidden = ("salary", "wage", "payroll", "employee", "employment",
                 "hiring", "hire", "compensation", "payment")

    async with system_session() as session:
        columns = set((await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name IN (:o, :l, :a)"),
            {"o": OWNERS, "l": LISTINGS, "a": APPLICATIONS})).scalars().all())

    for column in columns:
        for word in forbidden:
            assert word not in column.lower(), f"عمودٌ بمفردةِ توظيف: {column}"

    vocabularies = (recruitment.OPPORTUNITY_STATES
                    + recruitment.APPLICATION_STATES
                    + recruitment.ACTIVE_APPLICATION_STATES)
    for value in vocabularies:
        for word in forbidden:
            assert word not in value.lower(), f"حالٌ بمفردةِ توظيف: {value}"


def test_the_closed_boundary_is_recorded_as_a_control_not_as_debt():
    """**والحدُّ المُغلَق يُكتب ضابطًا لا دَينًا مؤجَّلًا.**

    فقد كان مسجَّلًا في «مخاطر مقبولة ومعلنة» بندًا خامسًا، وكان ذلك
    وصفًا صحيحًا لتصميمٍ ناقص. وقد أُغلق في المخطَّط، فانتقل إلى جدول
    الضوابط — **ووصفُ حدٍّ مُغلَقٍ كدَينٍ يُضلّل من يقرأ بعد سنة**.
    """
    document = (REPO / "docs" / "threat-model.md").read_text(encoding="utf-8")
    controls, risks = document.split("## مخاطر مقبولة ومعلنة")

    assert "RC-T1B" in controls, "الضابطُ غيرُ مسجَّلٍ في جدول التهديدات"
    assert LISTINGS in controls and OWNERS in controls
    assert "RC-T1B" not in risks, "حدٌّ مُغلَقٌ ما زال مكتوبًا دَينًا مؤجَّلًا"
    assert PUBLIC_VIEW not in risks


# ═══════ ١٤ من التكليف · RC-T1A لم تُمسّ ═══════


@requires_db
@pytest.mark.asyncio
async def test_rc_t1a_project_access_is_unchanged_by_this_stage(world):
    """**وعضويّةُ المستأجر لم تعُد عضويّةَ بحثٍ — ولا تزال.**

    فسطحٌ جديدٌ يقرأ الأبحاثَ والعضويّاتِ قد يُغري بتوسيع ما يراه
    المستأجر. فيُعاد سؤالُ RC-T1A هنا: الغريبُ لا يرى، والعضوُ يرى،
    والمالكُ مالك.
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
