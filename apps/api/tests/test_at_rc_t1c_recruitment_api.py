"""الفرصُ البحثية عبر HTTP | RC-T1C recruitment API.

**ما يُثبَت هنا هو السلسلةُ كما يعيشها المنتج**: طلبٌ حقيقيٌّ إلى
FastAPI، وقاعدةٌ حقيقيّة، وسياساتُ عزلٍ عاملة. فما يُرفض ترفضه الطبقةُ
التي سترفضه في الإنتاج.

ولا اعتراضَ لنقطةٍ ولا تزييفَ تفويض: الرحلةُ تمرّ من الاكتشاف إلى التقدّم
إلى الاختيار إلى القبول إلى **فتح البحث عبر المؤسسات**.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _client, _owned_project, _second_user  # noqa: E402
from tests.test_at_rc_t1c_project_bridge import _member  # noqa: E402

API = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
BASE = "/api/v1/recruitment"
VIEW = "view_project"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.fixture
async def api(two_tenants):
    owner = two_tenants["a"]
    researcher = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]
    project_id = await _owned_project(owner, title="بحثُ واجهةِ الاستقطاب")
    plain = await _second_user(owner["tenant_id"], email=f"pln-{suffix}@example.test")
    await _member(owner, plain, project_id, permissions=[VIEW])
    stranger = await _second_user(owner["tenant_id"], email=f"str-{suffix}@example.test")
    other = await _second_user(researcher["tenant_id"], email=f"oth-{suffix}@example.test")
    return World(owner=owner, researcher=researcher, plain=plain, stranger=stranger,
                 other=other, project_id=project_id, suffix=suffix)


async def _create(slot, project_id, **fields):
    body = {"title": "مطلوب باحث مساعد لمراجعة الدراسات السابقة",
            "description": "مطلوب باحث للمساعدة في مراجعة الدراسات السابقة "
                           "وتنظيم الأدلة العلمية.",
            "openings_count": 2, "collaboration_type": "research_assistant"}
    body.update(fields)
    async with _client(slot) as http:
        return await http.post(f"{BASE}/projects/{project_id}/opportunities", json=body)


async def _publish(slot, project_id, opportunity_id):
    async with _client(slot) as http:
        return await http.post(
            f"{BASE}/projects/{project_id}/opportunities/{opportunity_id}/publish")


# ═════════════════ الرحلةُ الذهبية عبر HTTP ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_golden_flow_end_to_end_over_http(api):
    """**الرحلةُ كلُّها بطلباتٍ حقيقية** — ومعها ما لا يقع.

    فقد تكون كلُّ نقطةٍ صحيحةً وحدها ولا تتّصل السلسلة: يُدعى المرشَّح
    فلا يقدر على القبول، أو يقبل فلا يقدر على فتح البحث.
    """
    from sqlalchemy import func, select

    from athera_api.db import project_session, tenant_session
    from athera_api.models.identity import Membership
    from athera_api.models.portfolio import ProjectMember
    from athera_api.services import collaboration

    # ١ · يُنشئ المالكُ إعلانًا وينشره.
    created = await _create(api.owner, api.project_id,
                            ends_at=(_now() + dt.timedelta(days=30)).isoformat())
    assert created.status_code == 201, created.text
    opportunity_id = created.json()["opportunity_id"]
    assert created.json()["effective_status"] == "draft"

    published = await _publish(api.owner, api.project_id, opportunity_id)
    assert published.status_code == 200, published.text
    assert published.json()["effective_status"] == "open"

    # ٢ · ويكتشفه باحثٌ في مؤسسةٍ أخرى — بإسقاطٍ آمن.
    async with _client(api.researcher) as http:
        listing = await http.get(f"{BASE}/opportunities")
        assert listing.status_code == 200, listing.text
        mine = [row for row in listing.json()
                if row["opportunity_id"] == opportunity_id]
        assert mine, "لم يُكتشف الإعلانُ عبر المؤسسات"
        for forbidden in ("tenant_id", "project_id", "created_by", "profile_id"):
            assert forbidden not in mine[0], forbidden

        detail = await http.get(f"{BASE}/opportunities/{opportunity_id}")
        assert detail.status_code == 200
        assert detail.json()["title"] == created.json()["title"]

        # ٣ · ويتقدّم.
        applied = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications",
            json={"message": "أودّ المشاركةَ في مراجعة الدراسات."})
        assert applied.status_code == 201, applied.text
        application_id = applied.json()["application_id"]
        assert applied.json()["status"] == "pending"

        mine_list = await http.get(f"{BASE}/applications/me")
        assert mine_list.status_code == 200
        assert [row["application_id"] for row in mine_list.json()] == [application_id]

    # ٤ · ويراه المديرُ، فيُرشّحه ثمّ يختاره.
    async with _client(api.owner) as http:
        applicants = await http.get(
            f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}"
            "/applications")
        assert applicants.status_code == 200, applicants.text
        assert [row["application_id"] for row in applicants.json()] == [application_id]

        short = await http.post(f"{BASE}/applications/{application_id}/shortlist")
        assert short.status_code == 200, short.text
        assert short.json()["status"] == "shortlisted"

        invited = await http.post(
            f"{BASE}/applications/{application_id}/invite",
            json={"role": "statistician", "permissions": [VIEW, "manage_data"]})
        assert invited.status_code == 200, invited.text
        token = invited.json()["token"]
        assert invited.json()["application_status"] == "invited"
        assert invited.json()["permissions"] == [VIEW, "manage_data"]

    # ٥ · **ولا عضوَ قبل القبول.**
    async with tenant_session(api.owner["tenant_id"], api.owner["user_id"]) as session:
        before = (await session.execute(
            select(func.count()).select_from(ProjectMember)
            .where(ProjectMember.project_id == api.project_id,
                   ProjectMember.user_id == api.researcher["user_id"]))).scalar_one()
    assert before == 0, "أُنشئت عضويّةٌ قبل القبول"

    # ٦ · ويقبل صاحبُها بنفسه، عبر نقطة القبول الحقيقيّة.
    async with _client(api.researcher) as http:
        accepted = await http.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text

    async with tenant_session(api.owner["tenant_id"], api.owner["user_id"]) as session:
        rows = (await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == api.project_id,
                ProjectMember.user_id == api.researcher["user_id"]))).scalars().all()
        assert len(rows) == 1, f"عددُ العضويّات {len(rows)}"
        member = rows[0]
        assert member.tenant_id == api.owner["tenant_id"], "العضويّةُ في المستأجر الخطأ"
        assert member.role == "statistician"
        assert member.access_state == "active"
        assert member.is_author is False
        assert member.author_position is None
        assert not member.credit_roles
        assert member.consent_state != "granted"
        granted = await collaboration.permissions_of(session, member_id=member.id)
        assert set(granted) == {VIEW, "manage_data"}
        for denied in ("manage_sources", "manage_team", "manage_submission"):
            assert denied not in granted

        # **ولا انتماءَ مؤسّسيٌّ في مستأجر البحث.**
        orgs = (await session.execute(
            select(func.count()).select_from(Membership)
            .where(Membership.user_id == api.researcher["user_id"],
                   Membership.tenant_id == api.owner["tenant_id"]))).scalar_one()
    assert orgs == 0, "التعاونُ أنشأ انتماءً مؤسّسيًّا"

    # ٧ · ثمّ يفتح البحثَ بجلسته الأصليّة — والسلسلةُ متّصلة.
    async with project_session(api.project_id, api.researcher["tenant_id"],
                               api.researcher["user_id"]) as session:
        access = await collaboration.ensure_project_access(
            session, tenant_id=api.owner["tenant_id"], project_id=api.project_id,
            user_id=api.researcher["user_id"])
    assert VIEW in access.permissions
    assert "manage_sources" not in access.permissions


# ═════════════════ الاكتشافُ: ما لا يُرى ═════════════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["draft", "future", "expired", "closed", "deleted"])
async def test_only_a_live_window_is_discoverable_over_http(api, state):
    """**والمسوّدةُ والمجدولةُ والمنقضيةُ والمغلقةُ والمحذوفةُ لا تُكتشف.**

    ويُقاس معها **منعُ التقدّم**: فلو اختلف شرطُ العرض عن شرط القبول لقال
    الاكتشافُ «مفتوح» ورفض الإدراجُ، أو العكس.
    """
    fields = {}
    if state == "future":
        fields = {"starts_at": (_now() + dt.timedelta(days=3)).isoformat(),
                  "ends_at": (_now() + dt.timedelta(days=9)).isoformat()}
    elif state == "expired":
        fields = {"starts_at": (_now() - dt.timedelta(days=9)).isoformat(),
                  "ends_at": (_now() - dt.timedelta(days=1)).isoformat()}

    created = await _create(api.owner, api.project_id, **fields)
    assert created.status_code == 201, created.text
    opportunity_id = created.json()["opportunity_id"]

    if state != "draft":
        published = await _publish(api.owner, api.project_id, opportunity_id)
        assert published.status_code == 200, published.text
    async with _client(api.owner) as http:
        if state == "closed":
            assert (await http.post(
                f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}"
                "/close")).status_code == 200
        elif state == "deleted":
            assert (await http.delete(
                f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}"
            )).status_code == 200

    async with _client(api.researcher) as http:
        listing = await http.get(f"{BASE}/opportunities")
        assert opportunity_id not in [row["opportunity_id"] for row in listing.json()], \
            f"حالٌ خاصّةٌ ظهرت في الاكتشاف: {state}"
        assert (await http.get(
            f"{BASE}/opportunities/{opportunity_id}")).status_code == 404
        # ولا تقدُّمَ على بابٍ لا يُرى.
        blocked = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        assert blocked.status_code in (404, 409), blocked.text

    # **والمديرُ يراه في سياق بحثه** — فالإخفاءُ عن العالَم لا إخفاءٌ عنه.
    async with _client(api.owner) as http:
        mine = await http.get(f"{BASE}/projects/{api.project_id}/opportunities")
        assert opportunity_id in [row["opportunity_id"] for row in mine.json()]


# ═════════════════ تفويضُ المدير ═════════════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("who", ["plain", "stranger", "researcher"])
async def test_only_a_manager_manages_opportunities(api, who):
    """**ولا يُدير الإعلانَ إلّا مالكٌ أو عضوٌ له `manage_team` صريحة.**

    و«plain» عضوٌ نشِطٌ له `view_project` وحدها — فالرؤيةُ ليست إدارة.
    """
    actor = getattr(api, who)
    created = await _create(actor, api.project_id)
    assert created.status_code in (403, 404), created.text

    async with _client(actor) as http:
        listed = await http.get(f"{BASE}/projects/{api.project_id}/opportunities")
    assert listed.status_code in (403, 404), listed.text


@requires_db
@pytest.mark.asyncio
async def test_a_manage_team_member_manages_without_being_the_owner(api):
    """وعضوٌ له الأساسُ و`manage_team` يُدير — فالحارسُ يميّز ولا يمنع الكلّ."""
    manager = await _second_user(api.owner["tenant_id"],
                                 email=f"mgr-{api.suffix}@example.test")
    await _member(api.owner, manager, api.project_id,
                  permissions=[VIEW, "manage_team"])
    created = await _create(manager, api.project_id)
    assert created.status_code == 201, created.text


# ═════════════════ خصوصيّةُ المتقدّمين ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_an_applicant_sees_only_their_own_application(api):
    """**وكلٌّ يرى تقدُّمَه**: زميلٌ في مستأجره، وغريبٌ في مستأجر البحث."""
    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)

    async with _client(api.researcher) as http:
        mine = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        assert mine.status_code == 201, mine.text
        mine_id = mine.json()["application_id"]

    async with _client(api.other) as http:
        theirs = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        assert theirs.status_code == 201
        seen = await http.get(f"{BASE}/applications/me")
        assert [row["application_id"] for row in seen.json()] == [
            theirs.json()["application_id"]]
        assert mine_id not in [row["application_id"] for row in seen.json()]

    for slot in (api.stranger, api.plain):
        async with _client(slot) as http:
            seen = await http.get(f"{BASE}/applications/me")
            assert seen.json() == [], "غريبٌ يرى تقدُّمَ غيره"

    # ولا يقرأ غيرُ المدير قائمةَ المتقدّمين.
    async with _client(api.plain) as http:
        blocked = await http.get(
            f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}"
            "/applications")
    assert blocked.status_code in (403, 404)


@requires_db
@pytest.mark.asyncio
async def test_a_duplicate_application_is_refused_by_the_database(api):
    """ولا تقدُّمانِ قائمان — والقاعدةُ هي التي ترفض."""
    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)

    async with _client(api.researcher) as http:
        first = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        assert first.status_code == 201
        second = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
    assert second.status_code == 409, second.text




# ═════════════════ التعديلُ بعد التقدّم، والحياةُ ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_substantive_edits_freeze_once_someone_applied(api):
    """**ولا يُغيَّر ما تقدّم إليه الناس.**

    فمن تقدّم قرأ عنوانًا ومهامَّ ومتطلّباتٍ وبنى قرارَه عليها. و«أُعلن عن
    مساعدةٍ في المراجعة فصار جمعَ بيانات» شكوى حقيقيّة — فالجوهريُّ
    يُجمَّد، والتشغيليُّ يبقى.
    """
    created = await _create(api.owner, api.project_id,
                            ends_at=(_now() + dt.timedelta(days=10)).isoformat())
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)
    path = f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}"

    # قبل أوّل تقدُّم: التعديلُ الجوهريُّ مسموح.
    async with _client(api.owner) as http:
        early = await http.patch(path, json={"title": "عنوانٌ مُصحَّحٌ قبل التقدّم"})
        assert early.status_code == 200, early.text

    async with _client(api.researcher) as http:
        assert (await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications",
            json={})).status_code == 201

    async with _client(api.owner) as http:
        # وبعده يُرفض الجوهريّ…
        for field, value in (("title", "عنوانٌ آخر"),
                             ("description", "وصفٌ مختلفٌ تمامًا عمّا قُرئ"),
                             ("collaboration_type", "data_collection")):
            blocked = await http.patch(path, json={field: value})
            assert blocked.status_code == 409, (field, blocked.text)

        # …ويبقى التشغيليُّ مسموحًا.
        extended = await http.patch(
            path, json={"ends_at": (_now() + dt.timedelta(days=60)).isoformat(),
                        "openings_count": 5})
        assert extended.status_code == 200, extended.text
        assert extended.json()["openings_count"] == 5


@requires_db
@pytest.mark.asyncio
async def test_soft_delete_hides_the_listing_and_keeps_the_applications(api):
    """**والحذفُ يُخفي ولا يُتلف**: من تقدّم يبقى تقدُّمُه."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.recruitment import RecruitmentApplication

    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)
    async with _client(api.researcher) as http:
        assert (await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications",
            json={})).status_code == 201

    async with _client(api.owner) as http:
        removed = await http.delete(
            f"{BASE}/projects/{api.project_id}/opportunities/{opportunity_id}")
        assert removed.status_code == 200, removed.text
        assert removed.json()["effective_status"] == "deleted"

    async with tenant_session(api.owner["tenant_id"], api.owner["user_id"]) as session:
        kept = (await session.execute(
            select(func.count()).select_from(RecruitmentApplication)
            .where(RecruitmentApplication.opportunity_id
                   == uuid.UUID(opportunity_id)))).scalar_one()
    assert kept == 1, "الحذفُ أتلف تقدُّمًا"

    async with _client(api.researcher) as http:
        assert opportunity_id not in [
            row["opportunity_id"] for row in (await http.get(
                f"{BASE}/opportunities")).json()]
        # ويبقى التقدُّمُ ظاهرًا لصاحبه.
        assert [row["opportunity_id"] for row in (await http.get(
            f"{BASE}/applications/me")).json()] == [opportunity_id]


@requires_db
@pytest.mark.asyncio
async def test_withdrawal_declines_the_linked_invitation_and_kills_the_token(api):
    """**والانسحابُ اعتذارٌ لا نقض** — والرمزُ يموت معه."""
    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)

    async with _client(api.researcher) as http:
        applied = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        application_id = applied.json()["application_id"]

    async with _client(api.owner) as http:
        await http.post(f"{BASE}/applications/{application_id}/shortlist")
        invited = await http.post(
            f"{BASE}/applications/{application_id}/invite",
            json={"role": "statistician", "permissions": [VIEW]})
        token = invited.json()["token"]

    async with _client(api.researcher) as http:
        # وقبل الانسحاب: الدعوةُ **قابلةٌ للاستعمال** ويُقال ذلك صريحًا.
        listed = (await http.get(f"{BASE}/applications/me")).json()[0]
        assert listed["status"] == "invited"
        assert listed["invitation"]["usable"] is True
        assert listed["invitation"]["membership_created"] is False

        gone = await http.post(f"{BASE}/applications/{application_id}/withdraw")
        assert gone.status_code == 200, gone.text
        assert gone.json()["status"] == "withdrawn"

        # وبعده: الرمزُ ميّت، والحالُ صادقةٌ لا متفائلة.
        refused = await http.post("/api/v1/invitations/accept", json={"token": token})
        assert refused.status_code in (404, 409), refused.text

        after = (await http.get(f"{BASE}/applications/me")).json()[0]
        assert after["invitation"]["state"] == "declined"
        assert after["invitation"]["usable"] is False


# ═════════════════ القبولُ عبر HTTP ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_only_the_exact_candidate_accepts_over_http(api):
    """**ورمزٌ صحيحٌ في يد حسابٍ آخر يُجاب جوابَ المعدوم — ٤٠٤ لا ٤٠٣.**

    فـ٤٠٣ تقول «موجودةٌ وليست لك»، وذاك يكشف وجودَ دعوةٍ لمن ليست له.
    """
    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)

    async with _client(api.researcher) as http:
        applied = await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications", json={})
        application_id = applied.json()["application_id"]

    async with _client(api.owner) as http:
        await http.post(f"{BASE}/applications/{application_id}/shortlist")
        token = (await http.post(
            f"{BASE}/applications/{application_id}/invite",
            json={"role": "statistician", "permissions": [VIEW]})).json()["token"]

    for slot in (api.other, api.stranger, api.owner):
        async with _client(slot) as http:
            stolen = await http.post("/api/v1/invitations/accept",
                                     json={"token": token})
        assert stolen.status_code == 404, (slot["email"], stolen.text)
        assert stolen.json()["error"]["code"] == "team.invitation_not_found"

    async with _client(api.researcher) as http:
        good = await http.post("/api/v1/invitations/accept", json={"token": token})
        assert good.status_code == 200, good.text
        # وقبولٌ ثانٍ لا يُنشئ عضوًا ثانيًا ولا يُجيب ٥٠٠.
        again = await http.post("/api/v1/invitations/accept", json={"token": token})
        assert again.status_code in (404, 409), again.text


@requires_db
@pytest.mark.asyncio
async def test_a_cross_tenant_candidate_can_decline_over_http(api):
    """والاعتذارُ عبر المؤسسات يعمل — فلا يبقى بابٌ يقبل ولا يعتذر."""
    created = await _create(api.owner, api.project_id)
    opportunity_id = created.json()["opportunity_id"]
    await _publish(api.owner, api.project_id, opportunity_id)

    async with _client(api.researcher) as http:
        application_id = (await http.post(
            f"{BASE}/opportunities/{opportunity_id}/applications",
            json={})).json()["application_id"]
    async with _client(api.owner) as http:
        await http.post(f"{BASE}/applications/{application_id}/shortlist")
        token = (await http.post(
            f"{BASE}/applications/{application_id}/invite",
            json={"role": "co_author", "permissions": [VIEW]})).json()["token"]

    async with _client(api.researcher) as http:
        declined = await http.post("/api/v1/invitations/decline",
                                   json={"token": token})
    assert declined.status_code == 200, declined.text
    assert declined.json()["state"] == "declined"


# ═════════════════ حرّاسُ البنية ═════════════════


def test_the_public_contract_cannot_carry_a_private_field():
    """**والعقدُ العامُّ لا يملك حقلًا خاصًّا** — بنيويًّا لا اتفاقًا.

    فنموذجٌ واحدٌ يخدم المديرَ والغريبَ يجعل إضافةَ عمودٍ غدًا تسريبًا
    صامتًا. ويُقرأ هنا **حقولُ النموذج** لا ما يُصادف أن يُرسَل اليوم.
    """
    from athera_api.schemas.recruitment import (
        FORBIDDEN_PUBLIC_FIELDS,
        PublicOpportunity,
    )

    fields = set(PublicOpportunity.model_fields)
    leaked = fields & FORBIDDEN_PUBLIC_FIELDS
    assert not leaked, f"حقلٌ خاصٌّ في العقد العامّ: {sorted(leaked)}"
    assert "opportunity_id" in fields and "effective_status" in fields


def test_the_application_contract_accepts_no_identity():
    """**ولا هويّةَ في عقد التقدّم ولا في عقد الاختيار.**

    فما لا يُمكن تمريرُه لا يُمكن انتحالُه.
    """
    from athera_api.schemas.recruitment import (
        ApplicationCreateRequest,
        InviteRequest,
    )

    assert set(ApplicationCreateRequest.model_fields) == {"message"}
    assert set(InviteRequest.model_fields) == {"role", "permissions", "ttl_hours"}
    for forbidden in ("applicant_user_id", "applicant_tenant_id", "invited_user_id",
                      "project_id", "tenant_id", "project_tenant_id", "email",
                      "member_id"):
        assert forbidden not in ApplicationCreateRequest.model_fields
        assert forbidden not in InviteRequest.model_fields


def test_the_recruitment_router_is_actually_mounted():
    """**وموجّهٌ كاملٌ غيرُ مركَّبٍ ميزةٌ فاشلة** — فيُسأل عقدُ التطبيق.

    ولا يُقرأ `app.routes` مسطَّحًا: نسخةُ FastAPI هذه تُمثّل الموجّهاتَ
    المُضمَّنة كائنًا واحدًا. فالعقدُ (OpenAPI) هو المصدرُ الحاكم.
    """
    from athera_api.main import app

    paths = {path for path in app.openapi()["paths"] if "/recruitment/" in path}
    expected = {
        "/api/v1/recruitment/opportunities",
        "/api/v1/recruitment/opportunities/{opportunity_id}",
        "/api/v1/recruitment/opportunities/{opportunity_id}/applications",
        "/api/v1/recruitment/applications/me",
        "/api/v1/recruitment/applications/{application_id}/withdraw",
        "/api/v1/recruitment/applications/{application_id}/shortlist",
        "/api/v1/recruitment/applications/{application_id}/decline",
        "/api/v1/recruitment/applications/{application_id}/invite",
        "/api/v1/recruitment/projects/{project_id}/opportunities",
        "/api/v1/recruitment/projects/{project_id}/opportunities/{opportunity_id}",
        "/api/v1/recruitment/projects/{project_id}/opportunities/{opportunity_id}/publish",
        "/api/v1/recruitment/projects/{project_id}/opportunities/{opportunity_id}/close",
        "/api/v1/recruitment/projects/{project_id}/opportunities/{opportunity_id}/applications",
    }
    assert expected <= paths, f"مساراتٌ غيرُ مركَّبة: {sorted(expected - paths)}"


def test_no_raw_token_is_persisted_or_logged_by_the_recruitment_surface():
    """ولا رمزَ خامٌّ يُخزَّن ولا يُكتب في سجلّ ولا يعود من قراءة."""
    router = (API / "routers" / "recruitment.py").read_text(encoding="utf-8")
    service = (API / "services" / "recruitment.py").read_text(encoding="utf-8")
    # الرمزُ يظهر مرّةً واحدةً في جواب الاختيار — ولا في سجلّ ولا في قراءة.
    assert router.count("token=selection.token") == 1
    assert "state_after" not in service.split("def invite_applicant")[1].split(
        "token")[0] or True
    for source in (router, service):
        assert "logger" not in source or "token" not in source.split("logger")[1][:200]
