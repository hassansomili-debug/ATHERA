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


# ═══════════ هـ · الموجّهاتُ المباشرة: لا بابَ خلفيًّا حول Workspace ═══════════
#
# **وهذا القسمُ وُلد من تصحيح.** قيل في المراجعة السابقة إنّ سطوحَ الملفات
# والبيانات «محميّةٌ خلف Workspace» — ولم تكن. كان `_project` في Workspace
# يُغلق، ويبقى أحد عشر موجّهًا آخر يقبل معرّفَ البحث مباشرةً بمساواة
# المستأجر وحدها: الخيطُ الذهبيّ، والتخطيط، والتوليف، وإدارةُ المشروع،
# والتحليل، والنشر، والصياغة، والأدبيّات، والمحادثة، والمكتبة، والمحفظة.
#
# فلا يُقال «محميّ خلف كذا» ويُصدَّق: **يُطرق البابُ نفسُه ويُرى ماذا يردّ**.

GOLDEN_VIEW = "/api/v1/projects/{pid}/thread/golden-view"
THREAD_ELEMENTS = "/api/v1/projects/{pid}/thread/elements"
PUB_CONTEXT = "/api/v1/planning/{pid}/publication-context"
DASHBOARD = "/api/v1/project-management/projects/{pid}/dashboard"
TASKS = "/api/v1/project-management/projects/{pid}/tasks"
THEMES = "/api/v1/synthesis/projects/{pid}/themes"
LEDGER = "/api/v1/literature/projects/{pid}/evidence-ledger"
DATASETS = "/api/v1/analysis/datasets"
MANUSCRIPTS = "/api/v1/publishing/manuscripts"
ASK = "/api/v1/ai/ask"
PORTFOLIO = "/api/v1/portfolio/projects"

ELEMENT_BODY = {"element_type": "problem", "label_ar": "مشكلةٌ دسّها غريب", "ordinal": 1}
TASK_BODY = {"title": "مهمّةٌ دسّها غريب", "stage": "idea"}


@requires_db
@pytest.mark.asyncio
async def test_e_a_non_member_is_refused_at_every_direct_project_router(two_tenants):
    """**كلُّ بابٍ يُطرق بمعرّفٍ صحيح، وكلُّها تردّ ٤٠٤.**

    ولا يُكتفى بالبوابة المشهورة: الزميلُ هنا يعرف المعرّفَ تمامًا كما
    يعرفه صاحبُ البحث، ويطرق عشرةَ أبوابٍ لا يمرّ واحدٌ منها بـWorkspace.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ لا يُطرق بابه")
    colleague = await _second_user(a["tenant_id"], email=f"d-{uuid.uuid4().hex[:8]}@x.test")

    async with _client(colleague) as http:
        for route in (JOURNEY, GOLDEN_VIEW, PUB_CONTEXT, DASHBOARD, TASKS,
                      THEMES, LEDGER):
            got = await http.get(route.format(pid=project_id))
            assert got.status_code == 404, f"{route} ردّ {got.status_code}: {got.text}"

        # والكتابةُ كذلك — ولا صفَّ يُترك خلفها.
        made = await http.post(THREAD_ELEMENTS.format(pid=project_id), json=ELEMENT_BODY)
        assert made.status_code == 404, made.text
        tasked = await http.post(TASKS.format(pid=project_id), json=TASK_BODY)
        assert tasked.status_code == 404, tasked.text

        # وطبقةُ البيانات: مجموعةٌ تُدسّ في بحثِ غيره.
        dataset = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "بياناتٌ دسّها غريب",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "a" * 64,
            "row_count": 10})
        assert dataset.status_code == 404, dataset.text

        # ومخطوطةٌ تُنشأ في بحثِ غيره.
        manuscript = await http.post(MANUSCRIPTS, json={
            "project_id": str(project_id), "title_ar": "مخطوطةٌ دسّها غريب",
            "language": "ar"})
        assert manuscript.status_code == 404, manuscript.text

        # والمحادثةُ لا تصير بابًا خلفيًّا لعنوان البحث وحاله.
        asked = await http.post(ASK, json={
            "question": "ما حال هذا البحث؟", "project_id": str(project_id)})
        assert asked.status_code == 404, asked.text

    # **ولا أثرَ بقي**: العنصرُ المرفوض لا صفَّ له في الخيط.
    async with _client(a) as http:
        woven = await http.get(GOLDEN_VIEW.format(pid=project_id))
    assert woven.status_code == 200, woven.text
    assert "مشكلةٌ دسّها غريب" not in woven.text


@requires_db
@pytest.mark.asyncio
async def test_e_the_portfolio_listing_is_a_second_door_to_the_same_list(two_tenants):
    """**شاشتان للقائمة نفسها، والحدُّ يُوضع في كلتيهما.**"""
    a = two_tenants["a"]
    await _owned_project(a, title="بحثٌ في المحفظة")
    colleague = await _second_user(a["tenant_id"], email=f"p-{uuid.uuid4().hex[:8]}@x.test")

    async with _client(a) as http:
        mine = await http.get(PORTFOLIO)
    assert mine.status_code == 200, mine.text
    assert "بحثٌ في المحفظة" in [r["working_title_ar"] for r in mine.json()]

    async with _client(colleague) as http:
        theirs = await http.get(PORTFOLIO)
    assert theirs.status_code == 200, theirs.text
    assert "بحثٌ في المحفظة" not in [r["working_title_ar"] for r in theirs.json()]


# ═══════════ و · الاطّلاعُ يقرأ ولا يكتب ═══════════


@requires_db
@pytest.mark.asyncio
async def test_f_view_project_reads_but_never_writes(two_tenants):
    """**`view_project` ليست إذنًا بالكتابة** — و٤٠٣ لا ٤٠٤ هنا.

    فالفرقُ مقصود: من لا مدخلَ له يُجاب بـ٤٠٤ فلا يُستدلّ على وجود البحث؛
    ومن يطّلع ولا يملك الفعل يعرف وجودَه سلفًا، فالصدقُ أنفع من إنكارٍ كاذب.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُقرأ ولا يُكتب")
    colleague = await _second_user(a["tenant_id"], email=f"v-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, colleague, project_id, permissions=["view_project"])

    async with _client(colleague) as http:
        # يقرأ.
        for route in (JOURNEY, GOLDEN_VIEW, DASHBOARD, THEMES):
            got = await http.get(route.format(pid=project_id))
            assert got.status_code == 200, f"{route} ردّ {got.status_code}: {got.text}"

        # ولا يكتب — في الخيط، ولا في المهامّ، ولا في البيانات.
        made = await http.post(THREAD_ELEMENTS.format(pid=project_id), json=ELEMENT_BODY)
        assert made.status_code == 403, made.text
        tasked = await http.post(TASKS.format(pid=project_id), json=TASK_BODY)
        assert tasked.status_code == 403, tasked.text
        dataset = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "بياناتٌ بلا إذن",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "b" * 64,
            "row_count": 10})
        assert dataset.status_code == 403, dataset.text


@requires_db
@pytest.mark.asyncio
async def test_f_edit_research_content_writes_but_is_not_data_management(two_tenants):
    """**والصلاحيّاتُ لا تتداخل**: من يحرّر المحتوى لا يملك البيانات بذلك.

    وهذا حدُّ الإحصائيّ في هذا النظام: `manage_data` صفٌّ قائمٌ بذاته،
    والمؤلّفُ المشارك يحرّر النصّ ولا يفتح مجموعةَ المشاركين.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُحرَّر")
    colleague = await _second_user(a["tenant_id"], email=f"e-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, colleague, project_id,
                             permissions=["view_project", "edit_research_content"])

    async with _client(colleague) as http:
        made = await http.post(THREAD_ELEMENTS.format(pid=project_id), json=ELEMENT_BODY)
        assert made.status_code == 201, made.text

        # ولا مهامّ: `manage_tasks` صفٌّ آخر لم يُمنح.
        tasked = await http.post(TASKS.format(pid=project_id), json=TASK_BODY)
        assert tasked.status_code == 403, tasked.text

        # **ولا بيانات** — وهذا هو الحدُّ الذي طُلب إثباتُه لا ادّعاؤه.
        dataset = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "بياناتُ مشاركين",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "c" * 64,
            "row_count": 10})
        assert dataset.status_code == 403, dataset.text


@requires_db
@pytest.mark.asyncio
async def test_f_manage_data_opens_the_dataset_and_its_dictionary_and_nothing_else(
        two_tenants):
    """**قاموسُ الأعمدة يحمل وسمَ البيانات الشخصية** — فلا يُقرأ بالاطّلاع.

    والمجموعةُ تُنشأ بـ`manage_data`، وتُقرأ نسخُها بالاطّلاع؛ أمّا الكتابةُ
    في القاموس فتطلب الصفَّ نفسه. وثالثةٌ تُثبت أنّ المنحةَ لم تتمدّد:
    صاحبُ البيانات لا يحرّر الخيط.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ ذو بيانات")
    statistician = await _second_user(a["tenant_id"], email=f"s-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, statistician, project_id,
                             permissions=["view_project", "manage_data"])

    async with _client(statistician) as http:
        made = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةُ المشاركين",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "d" * 64,
            "row_count": 40})
        assert made.status_code == 201, made.text
        version_id = made.json()["id"]

        wrote = await http.put(
            f"/api/v1/analysis/datasets/versions/{version_id}/dictionary",
            json=[{"column_name": "age", "description_ar": "العمر", "is_pii": False}])
        assert wrote.status_code == 200, wrote.text

        # ولا يحرّر الخيطَ العلميّ: `edit_research_content` لم يُمنح.
        element = await http.post(THREAD_ELEMENTS.format(pid=project_id), json=ELEMENT_BODY)
        assert element.status_code == 403, element.text

    # وزميلٌ لا عضويّةَ له لا يقرأ القاموس أصلًا — **ولا يعرف أنّه موجود**.
    outsider = await _second_user(a["tenant_id"], email=f"o-{uuid.uuid4().hex[:8]}@x.test")
    async with _client(outsider) as http:
        read = await http.get(f"/api/v1/analysis/datasets/versions/{version_id}/dictionary")
        assert read.status_code == 404, read.text
        listed = await http.get(DATASETS)
        assert listed.status_code == 200
        assert listed.json() == []


# ═══════════ ز · الملفُّ لا يتبع البحثَ، والبحثُ لا يفتح الملفّ ═══════════
#
# **وهذا ما طُلب إثباتُه لا ادّعاؤه.** قيل إنّ الملفات «محميّةٌ خلف
# Workspace»؛ والحقيقةُ أدقُّ من ذلك وأمتن: `files` لا تسأل عن البحث أصلًا،
# بل عن **مِنحةٍ صريحة على الملفّ نفسه** (`rbac.require_object_action`)،
# تُكتب عند الرفع لصاحبه. فالحدُّ هنا قائمٌ بآليّةٍ أخرى — لا بـWorkspace.
#
# والحدّان مستقلّان في الاتجاهين، وكلاهما يُختبر:
#   • زميلٌ لا عضويّةَ له لا ينزّل ملفًّا مربوطًا ببحثٍ ليس له.
#   • **وعضوٌ في البحث لا ينزّل ملفَّه بمجرّد عضويّته**: `view_project`
#     ليست منحةَ ملفّ، و`manage_data` ليست منحةَ ملفّ. والربطُ يقول
#     «هذا البحث يستعمل هذا الملفّ»، لا «كلُّ عضوٍ يقرؤه».
#
# وذاك تصميمٌ مقصود: ملفُّ المشاركين قد يحمل هويّاتٍ لا يجوز أن يراها كلُّ
# من دُعي إلى البحث. ويُقال هنا صريحًا حتى لا يُقرأ الصمتُ وعدًا.

DOWNLOAD = "/api/v1/files/{fid}/download"
LINK_FILE = "/api/v1/workspace/projects/{pid}/files"


async def _file_owned_by(slot, name="بياناتُ المشاركين.pdf") -> uuid.UUID:
    """ملفٌّ في مكتبة صاحبه، ومنحتُه مكتوبةٌ له كما يكتبها الرفعُ الحقيقيّ."""
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.identity import ObjectGrant

    tid, uid = slot["tenant_id"], slot["user_id"]
    async with tenant_session(tid, uid) as session:
        row = File(tenant_id=tid, storage_key=f"tenants/{tid}/{uuid.uuid4()}",
                   original_filename=name, content_type="application/pdf",
                   size_bytes=2048, checksum_sha256="0" * 64, classification="C2",
                   status="stored", uploaded_by=uid)
        session.add(row)
        await session.flush()
        session.add(ObjectGrant(tenant_id=tid, object_type="file", object_id=row.id,
                                user_id=uid, grant_level="owner", granted_by=uid))
        await session.flush()
        return row.id


@requires_db
@pytest.mark.asyncio
async def test_g_a_project_linked_file_is_not_readable_by_tenant_membership(two_tenants):
    """**الربطُ بالبحث لا يفتح الملفّ لأحد** — لا لزميل، ولا لعضو."""
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ له ملفّ")
    file_id = await _file_owned_by(a)

    # صاحبُه يربطه ببحثه وينزّله.
    async with _client(a) as http:
        linked = await http.post(LINK_FILE.format(pid=project_id),
                                 json={"asset_id": str(file_id)})
        assert linked.status_code == 201, linked.text
        mine = await http.get(DOWNLOAD.format(fid=file_id))
        assert mine.status_code == 200, mine.text

    # زميلٌ في المؤسسة، لا عضويّةَ له: لا بحثًا ولا ملفًّا.
    colleague = await _second_user(a["tenant_id"], email=f"f-{uuid.uuid4().hex[:8]}@x.test")
    async with _client(colleague) as http:
        assert (await http.get(DOWNLOAD.format(fid=file_id))).status_code == 403
        assert (await http.get(f"{PROJECTS}/{project_id}/files")).status_code == 404

    # **وعضوٌ في البحث بصلاحيّتي الاطّلاع وإدارة البيانات — ولا منحةَ ملفّ.**
    member = await _second_user(a["tenant_id"], email=f"g-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, member, project_id,
                             permissions=["view_project", "manage_data"])
    async with _client(member) as http:
        # يرى أنّ للبحث ملفًّا — وهذا حقُّ العضو.
        listed = await http.get(f"{PROJECTS}/{project_id}/files")
        assert listed.status_code == 200, listed.text
        # ولا ينزّله: المنحةُ على الملفّ صفٌّ آخر لم يُكتب له.
        assert (await http.get(DOWNLOAD.format(fid=file_id))).status_code == 403


# ═══════════ ح · والبوابةُ رحلةٌ واحدة ═══════════


@requires_db
@pytest.mark.asyncio
async def test_h_the_gate_costs_one_round_trip_for_a_member(two_tenants):
    """**عدُّ الرحلات هو زمنُ الاستجابة هنا.**

    فالتطبيق في سنغافورة والقاعدة في مومباي، وكلُّ عبارةٍ ~٦٠ms. وهذه
    البوابةُ تقع على كلّ مسارٍ يقبل معرّفَ بحث — ٩٣ مسارًا — فثلاثةُ
    استعلاماتٍ فيها تصير مئتَي جزءٍ من الثانية على كلّ شاشة.

    ويُقاس العدُّ ولا يُوعَد به: حارسٌ يقول «واحدة» ولا يعدّ يُصدَّق حتى
    يُضاف استعلامٌ رابع فلا يشتكي أحد.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُقاس فتحُه")
    colleague = await _second_user(a["tenant_id"], email=f"q-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, colleague, project_id,
                             permissions=["view_project", "edit_research_content"])

    statements: list[str] = []

    async with tenant_session(a["tenant_id"], colleague["user_id"]) as session:
        original = type(session).execute

        async def counting(self, statement, *args, **kwargs):
            statements.append(str(statement))
            return await original(self, statement, *args, **kwargs)

        type(session).execute = counting
        try:
            access = await collaboration.ensure_project_access(
                session, tenant_id=a["tenant_id"], project_id=project_id,
                user_id=colleague["user_id"],
                permission="edit_research_content")
        finally:
            type(session).execute = original

    assert access.project.id == project_id
    assert access.allows("edit_research_content")
    assert len(statements) == 1, (
        f"البوابة كلّفت {len(statements)} استعلامًا لا واحدًا:\n"
        + "\n".join(s[:160] for s in statements))
    # وعبارةٌ واحدة تحمل الحدود الثلاثة وصفوفَ الصلاحيات معًا.
    only = statements[0]
    for fragment in ("research_projects", "project_members",
                     "project_member_permissions", "array_agg"):
        assert fragment in only, fragment


@requires_db
@pytest.mark.asyncio
async def test_h_one_account_cannot_hold_two_memberships_in_one_project(two_tenants):
    """**والجوابُ واحدٌ لأنّ الصفَّ واحد** — بقيدٍ في القاعدة لا باتفاق.

    فالبوابةُ المدموجة تقرأ العضويّةَ بوصلةٍ خارجية، ولو أمكن صفّان
    لحسابٍ واحد في بحثٍ واحد لعاد جوابُها اختيارًا بين حالين: صفٌّ مُزالٌ
    وآخرُ نشط. فيُثبَت هنا أنّ ذلك **ممتنعٌ في القاعدة**:
    `uq_project_members_project_account` فريدٌ على (البحث، الحساب).

    و`user_id` يقبل الفراغ لمدعوٍّ بالبريد لم يقبل بعد، فالقيدُ جزئيّ
    (`WHERE user_id IS NOT NULL`) — ودعوتان بالبريد لا تصيران عضويّتين
    لحسابٍ إلا بعد القبول، وعندها يبيت القيد. ولذلك يبقى في البوابة فرعٌ
    يُعلن الخلل إن سقط القيدُ يومًا، ولا يُخمّن.

    ونموذجُ SQLAlchemy لا يعلن هذا القيد في `__table_args__` — يعيشُ في
    الترحيل 0028 وحده. فيُقرأ من الschema الحيّة لا من الشيفرة: قيدٌ
    يُفترض وجودُه ولا يُقرأ هو قيدٌ قد لا يكون هناك.
    """
    import datetime as dt

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import system_session, tenant_session
    from athera_api.models.portfolio import ProjectMember

    async with system_session() as session:
        definition = (await session.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'uq_project_members_project_account'"
        ))).scalar_one_or_none()
    assert definition is not None, "القيدُ الفريد غائبٌ عن القاعدة الحيّة"
    assert "UNIQUE" in definition
    assert "project_id" in definition and "user_id" in definition

    # **ويُثبَت أنه يبيت** — قيدٌ يوجد ولا يُجرَّب قيدٌ لم يُختبر.
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ بعضويّةٍ واحدة")
    colleague = await _second_user(a["tenant_id"], email=f"x-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, colleague, project_id, permissions=["view_project"])

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(ProjectMember(
                tenant_id=a["tenant_id"], project_id=project_id,
                user_id=colleague["user_id"], display_name="صفٌّ ثانٍ",
                invited_email=f"dup-{uuid.uuid4().hex[:8]}@x.test",
                role="acknowledged", access_state="removed",
                removed_at=dt.datetime.now(dt.UTC),
                consent_state="not_requested", is_author=False))


# ═══════ ط · صاحبُ البحث لا يُقصى عن بحثه (قرارُ مالك المنتج) ═══════
#
# **والعطبُ الذي يُغلق هنا كان قائمًا، وفُتح بهذه الدفعة نفسها.**
#
# حين صار صفُّ العضويّة مرجعَ التفويض، صار مديرُ الفريق قادرًا على إقصاء
# صاحب البحث عن بحثه: يوقف عضويّته، أو ينزع صفوفَها، فيصير البحثُ الذي
# أنشأه محجوبًا عنه — ولا مسارَ يعيده إليه. و`_refuse_if_last_team_manager`
# لم تكن تمنع ذلك: هي تحرس «آخرَ مديرٍ» لا «صاحبَ البحث»، فمتى وُجد مديرٌ
# ثانٍ سقط حرسُها.
#
# فالملكيّةُ المُثبَتة سلطةُ جذر: تُشتقّ من ملفّ الباحث أو من حدث الإنشاء في
# سجلٍّ يُضاف إليه ولا يُعدَّل — ولا تكتبهما شاشةُ الفريق. **والدورُ ليس
# ملكيّة**، ولا نقلَ للملكيّة في هذه الدفعة.

MEMBER_ACCESS = "/api/v1/projects/{pid}/members/{mid}/access"
MEMBER_PERMS = "/api/v1/projects/{pid}/members/{mid}/permissions"
MEMBER_ROLE = "/api/v1/projects/{pid}/members/{mid}/role"
LEAVE = "/api/v1/projects/{pid}/members/me/leave"

OWNER_IMMUTABLE = "team.owner_is_immutable"


async def _owner_membership_id(slot, project_id) -> uuid.UUID:
    """صفُّ عضويّةِ المالك — يُنشئه `access_for` عند أوّل مسار فريق.

    ولا يُدسّ بيد: يُبلَغ بالمسار الحقيقيّ كما يُبلَغ في الإنتاج، فيكون
    الهجومُ أدناه على ما يوجد فعلًا لا على حالةٍ مصنوعة.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        access = await collaboration.access_for(
            session, tenant_id=slot["tenant_id"], project_id=project_id,
            user_id=slot["user_id"])
        return access.member.id


async def _member_row_id(slot, project_id, user_id) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(slot["tenant_id"], slot["user_id"]) as session:
        member = await collaboration.member_for(
            session, project_id=project_id, user_id=user_id)
    assert member is not None
    return member.id


async def _owner_still_has_their_project(slot, project_id, title) -> None:
    """بعد كلّ محاولة: يرى ويفتح **ويفعل** — والثالثةُ هي بيتُ الحارس."""
    assert title in await _titles(slot)
    async with _client(slot) as http:
        opened = await http.get(JOURNEY.format(pid=project_id))
        assert opened.status_code == 200, opened.text
        # سلطةُ الجذر لا الاطّلاعَ وحده: كتابةٌ علمية تطلب
        # `edit_research_content`، وهي أوّلُ ما يُنزَع في الهجوم.
        wrote = await http.post(THREAD_ELEMENTS.format(pid=project_id), json={
            "element_type": "problem",
            "label_ar": f"سؤالٌ كتبه صاحبُ البحث {uuid.uuid4().hex[:6]}",
            "ordinal": 1})
        assert wrote.status_code == 201, wrote.text


@requires_db
@pytest.mark.asyncio
async def test_i_a_team_manager_cannot_suspend_or_remove_the_verified_owner(
        two_tenants):
    """**لا يُوقف مديرُ الفريق صاحبَ البحث ولا يُزيله** — و٤٠٩ لا صمت."""
    a = two_tenants["a"]
    title = "بحثٌ لا يُقصى صاحبُه"
    project_id = await _owned_project(a, title=title)
    manager = await _second_user(a["tenant_id"], email=f"mgr-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, manager, project_id,
                             permissions=["view_project", "manage_team"])

    owner_member_id = await _owner_membership_id(a, project_id)

    async with _client(manager) as http:
        for state in ("suspended", "removed"):
            attack = await http.patch(
                MEMBER_ACCESS.format(pid=project_id, mid=owner_member_id),
                json={"access_state": state})
            assert attack.status_code == 409, f"{state} → {attack.status_code}: {attack.text}"
            assert attack.json()["error"]["code"] == OWNER_IMMUTABLE
            await _owner_still_has_their_project(a, project_id, title)


@requires_db
@pytest.mark.asyncio
async def test_i_a_team_manager_cannot_strip_the_owners_permissions(two_tenants):
    """**والبابُ الثاني مسدودٌ مع الأول** — نزعُ الصفوف ليس طريقًا للإقصاء.

    فحمايةُ `access_state` وحدها كانت تترك هذا: يبقى المالكُ «نشطًا» وقد
    نُزعت صفوفُه كلُّها، فيُحجب بلا أن يُوقف.
    """
    a = two_tenants["a"]
    title = "بحثٌ لا تُنزع صفوفُ صاحبه"
    project_id = await _owned_project(a, title=title)
    manager = await _second_user(a["tenant_id"], email=f"str-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, manager, project_id,
                             permissions=["view_project", "manage_team"])
    owner_member_id = await _owner_membership_id(a, project_id)

    async with _client(manager) as http:
        for attempt in ([], ["view_project"], ["view_project", "manage_tasks"]):
            attack = await http.put(
                MEMBER_PERMS.format(pid=project_id, mid=owner_member_id),
                json={"permissions": attempt})
            assert attack.status_code == 409, f"{attempt} → {attack.status_code}: {attack.text}"
            assert attack.json()["error"]["code"] == OWNER_IMMUTABLE
            await _owner_still_has_their_project(a, project_id, title)


@requires_db
@pytest.mark.asyncio
async def test_i_a_team_manager_cannot_demote_the_owners_role(two_tenants):
    """**ولا يُنزَّل صاحبُ البحث بدورٍ يكتبه غيره.**"""
    a = two_tenants["a"]
    title = "بحثٌ لا يُنزَّل صاحبُه"
    project_id = await _owned_project(a, title=title)
    manager = await _second_user(a["tenant_id"], email=f"dem-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, manager, project_id,
                             permissions=["view_project", "manage_team"])
    owner_member_id = await _owner_membership_id(a, project_id)

    async with _client(manager) as http:
        for role in ("acknowledged", "student", "supervisor"):
            attack = await http.patch(
                MEMBER_ROLE.format(pid=project_id, mid=owner_member_id),
                json={"role": role})
            assert attack.status_code == 409, f"{role} → {attack.status_code}: {attack.text}"
            assert attack.json()["error"]["code"] == OWNER_IMMUTABLE
    await _owner_still_has_their_project(a, project_id, title)


@requires_db
@pytest.mark.asyncio
async def test_i_the_owner_cannot_leave_their_own_project(two_tenants):
    """**ولا يخرج صاحبُ البحث من بحثه** وهو صاحبُه — ولا نقلَ للملكيّة بعد.

    فبحثٌ خرج صاحبُه عنه لا يُستعاد إلّا بتدخّلٍ يدويّ في القاعدة: الملكيّةُ
    تبقى منسوبةً إليه في السجلّ، وصفُّه يقول إنه ذهب.
    """
    a = two_tenants["a"]
    title = "بحثٌ لا يتركه صاحبُه"
    project_id = await _owned_project(a, title=title)
    # ومديرٌ ثانٍ موجود، فلا يكون المانعُ «آخرَ مديرٍ» بل الملكيّة نفسها.
    manager = await _second_user(a["tenant_id"], email=f"lv-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, manager, project_id,
                             permissions=["view_project", "manage_team"])
    await _owner_membership_id(a, project_id)

    async with _client(a) as http:
        left = await http.post(LEAVE.format(pid=project_id))
    assert left.status_code == 409, left.text
    assert left.json()["error"]["code"] == OWNER_IMMUTABLE
    await _owner_still_has_their_project(a, project_id, title)


@requires_db
@pytest.mark.asyncio
async def test_i_the_pi_role_alone_grants_no_ownership_protection(two_tenants):
    """**الدورُ ليس ملكيّة** — ولا يُشتقّ منه حرسٌ ولا سلطةُ جذر.

    فعضوٌ دورُه `principal_investigator` وليس صاحبَ النسب يُوقَف كأيّ عضو،
    ولا يردّ المسارُ ٤٠٩. ولو كان الحرسُ مبنيًّا على المفردة لكان مديرُ
    الفريق يصنع لنفسه حصانةً بتغيير دوره — وهو ما يُمنع هنا.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ فيه باحثٌ رئيسٌ ليس صاحبَه")
    pretender = await _second_user(a["tenant_id"], email=f"pi-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, pretender, project_id,
                             permissions=["view_project", "manage_team"])
    pretender_member_id = await _member_row_id(a, project_id, pretender["user_id"])

    async with _client(a) as http:
        promoted = await http.patch(
            MEMBER_ROLE.format(pid=project_id, mid=pretender_member_id),
            json={"role": "principal_investigator"})
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "principal_investigator"

        # ومع المفردة نفسها: يُوقَف، فالنسبُ لا يُشتقّ من دور.
        suspended = await http.patch(
            MEMBER_ACCESS.format(pid=project_id, mid=pretender_member_id),
            json={"access_state": "suspended"})
        assert suspended.status_code == 200, suspended.text

    # وقد حُجب فعلًا — لا «رُفض الطلبُ صامتًا».
    async with _client(pretender) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_i_normal_team_administration_still_works(two_tenants):
    """**ولا يُكسَر تدبيرُ الفريق الحقيقيّ** — الحرسُ على المالك وحده.

    فمن يحمل `manage_team` يدير عضوًا عاديًّا كما كان: يغيّر دوره، ويضبط
    صلاحياته، ويوقفه، ويعيده. وحارسٌ يمنع ما لم يُطلب منعُه عطبٌ آخر.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُدار فريقُه")
    manager = await _second_user(a["tenant_id"], email=f"ok-{uuid.uuid4().hex[:8]}@x.test")
    ordinary = await _second_user(a["tenant_id"], email=f"c3-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, manager, project_id,
                             permissions=["view_project", "manage_team"])
    await _invite_and_accept(a, ordinary, project_id,
                             permissions=["view_project", "edit_research_content"])
    ordinary_member_id = await _member_row_id(a, project_id, ordinary["user_id"])

    async with _client(manager) as http:
        rolled = await http.patch(
            MEMBER_ROLE.format(pid=project_id, mid=ordinary_member_id),
            json={"role": "student"})
        assert rolled.status_code == 200, rolled.text

        permed = await http.put(
            MEMBER_PERMS.format(pid=project_id, mid=ordinary_member_id),
            json={"permissions": ["view_project"]})
        assert permed.status_code == 200, permed.text

    # ونزعُ التحرير وقع فعلًا: يقرأ ولا يكتب.
    async with _client(ordinary) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 200
        denied = await http.post(THREAD_ELEMENTS.format(pid=project_id),
                                 json=ELEMENT_BODY)
        assert denied.status_code == 403, denied.text

    async with _client(manager) as http:
        stopped = await http.patch(
            MEMBER_ACCESS.format(pid=project_id, mid=ordinary_member_id),
            json={"access_state": "suspended"})
        assert stopped.status_code == 200, stopped.text
    async with _client(ordinary) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404

    async with _client(manager) as http:
        restored = await http.patch(
            MEMBER_ACCESS.format(pid=project_id, mid=ordinary_member_id),
            json={"access_state": "active"})
        assert restored.status_code == 200, restored.text
    async with _client(ordinary) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 200

    # وعضوٌ عاديّ يخرج بنفسه — والخروجُ ممنوعٌ على المالك وحده.
    async with _client(ordinary) as http:
        gone = await http.post(LEAVE.format(pid=project_id))
        assert gone.status_code == 200, gone.text
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_i_a_bad_owner_membership_row_is_not_a_lockout_vector(two_tenants):
    """**وطبقتان لا واحدة.** فالحرسُ على العمليات يمنع الطلب، والتفويضُ
    يقرأ الملكيّة — ولو سقط الأولُ يومًا بقي الثاني.

    وهذه ليست حالةً نظريّة: صفوفُ ما قبل هذه الدفعة كُتبت بلا هذا الحرس،
    وقد يكون فيها مالكٌ مُوقَفٌ أو منزوعُ الصفوف. فيُصنع الحالُ هنا في
    القاعدة مباشرةً — لا عبر مسارٍ يرفضه الحرس — ويُثبَت أنّ صاحبَ البحث
    يبقى صاحبَه: يرى، ويفتح، ويكتب.
    """
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember
    from athera_api.services import collaboration

    a = two_tenants["a"]
    title = "بحثٌ صفُّ مالكه معطوب"
    project_id = await _owned_project(a, title=title)
    owner_member_id = await _owner_membership_id(a, project_id)

    # ١) صفوفُ الصلاحيات تُمحى، والحالُ «نشط».
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        member = await collaboration.member_for(
            session, project_id=project_id, user_id=a["user_id"])
        await collaboration._grant_permissions(  # noqa: SLF001 — تجهيزةُ حالٍ معطوب
            session, tenant_id=a["tenant_id"], member=member, keys=[],
            granted_by=a["user_id"])
        from sqlalchemy import delete

        from athera_api.models.collaboration import ProjectMemberPermission
        await session.execute(delete(ProjectMemberPermission).where(
            ProjectMemberPermission.member_id == owner_member_id))
    await _owner_still_has_their_project(a, project_id, title)

    # ٢) والحالُ يُضبط على «مُوقَف» في القاعدة مباشرةً.
    import datetime as dt

    from sqlalchemy import update
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await session.execute(update(ProjectMember)
                              .where(ProjectMember.id == owner_member_id)
                              .values(access_state="suspended",
                                      suspended_at=dt.datetime.now(dt.UTC)))
    await _owner_still_has_their_project(a, project_id, title)

    # ٣) و«مُزال» كذلك — والنسبُ في السجلّ لا يُمحى بحالِ صفّ.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await session.execute(update(ProjectMember)
                              .where(ProjectMember.id == owner_member_id)
                              .values(access_state="removed", suspended_at=None,
                                      removed_at=dt.datetime.now(dt.UTC)))
    await _owner_still_has_their_project(a, project_id, title)

    # **وغيرُ المالك لا ينال شيئًا من هذا التراخي.**
    outsider = await _second_user(a["tenant_id"], email=f"nz-{uuid.uuid4().hex[:8]}@x.test")
    async with _client(outsider) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


# ═══════════ ي · حدودٌ تُصحَّح: دورةُ الحياة، والمكتبة، والبيانات ═══════════
#
# **وثلاثةُ حدودٍ كانت موضوعةً في غير موضعها**، وكلُّها من نوعٍ واحد: صلاحيةٌ
# تُقرأ لفعلٍ لا تخصّه، فتتّسع سلطتُها إلى ما لم يُقصد.
#
#   ١. `edit_research_content` كان يفتح **أرشفةَ البحث وحذفه واسترجاعه**.
#      وهو صفُّ تحرير المحتوى العلميّ: فكان طالبٌ يُدعى ليحرّر فصلًا فيرمي
#      البحث كلَّه. ولا صفَّ في المفردة لدورة الحياة، ولا يُختلق في دفعةٍ
#      أمنية — فيُرفع الحدُّ إلى النسب المُثبَت حتى يوجد.
#
#   ٢. `manage_data` كان يفتح **ربطَ ملفات المكتبة بالبحث**. و`ProjectFile`
#      علاقةُ مكتبةٍ بمشروع لا مجموعةَ بياناتٍ خامًا: قد يكون المربوطُ ورقةً
#      مرجعية أو رسالةً. فالصفُّ الصحيح `manage_sources`.
#
#   ٣. `view_project` كان يفتح **قاموسَ أعمدة البيانات** — وفيه أسماءُ
#      الأعمدة ووسمُ ما يحمل بياناتٍ شخصية. ومن دُعي ليقرأ البحث لم يُدعَ
#      ليقرأ عمودَ الهويّات.

ARCHIVE = "/api/v1/workspace/projects/{pid}/archive"
RESTORE = "/api/v1/workspace/projects/{pid}/restore"
TRASH = "/api/v1/workspace/projects/{pid}"
PROJECT_FILES = "/api/v1/workspace/projects/{pid}/files"
DATASET_VERSIONS = "/api/v1/analysis/datasets/{did}/versions"
DICTIONARY = "/api/v1/analysis/datasets/versions/{vid}/dictionary"
PLANS = "/api/v1/analysis/plans"
EXPORTS = "/api/v1/analysis/exports"

OWNER_ONLY = "workspace.owner_only"


# ─────────── أ · دورةُ حياة البحث لصاحبه وحده ───────────


@requires_db
@pytest.mark.asyncio
async def test_j_project_lifecycle_is_owner_only(two_tenants):
    """**تحريرُ المحتوى لا يمنح سلطةَ رمي البحث** — و٤٠٣ لا ٤٠٤ للعضو."""
    a = two_tenants["a"]
    title = "بحثٌ لا يُرمى إلّا بيد صاحبه"
    project_id = await _owned_project(a, title=title)
    editor = await _second_user(a["tenant_id"], email=f"ed-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, editor, project_id,
                             permissions=["view_project", "edit_research_content"])

    async with _client(editor) as http:
        # **ويحرّر المحتوى فعلًا** — فالمنعُ على دورة الحياة لا على عمله.
        wrote = await http.post(THREAD_ELEMENTS.format(pid=project_id),
                                json=ELEMENT_BODY)
        assert wrote.status_code == 201, wrote.text

        # ولا يؤرشف ولا يرمي — و٤٠٣: هو عضوٌ يعرف البحث، فلا يُنكَر وجودُه.
        archived = await http.post(ARCHIVE.format(pid=project_id))
        assert archived.status_code == 403, archived.text
        assert archived.json()["error"]["code"] == OWNER_ONLY

        trashed = await http.delete(TRASH.format(pid=project_id))
        assert trashed.status_code == 403, trashed.text
        assert trashed.json()["error"]["code"] == OWNER_ONLY

    # والاطّلاعُ وحده كذلك — ولا فرق.
    viewer = await _second_user(a["tenant_id"], email=f"vw-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, viewer, project_id, permissions=["view_project"])
    async with _client(viewer) as http:
        assert (await http.post(ARCHIVE.format(pid=project_id))).status_code == 403
        assert (await http.delete(TRASH.format(pid=project_id))).status_code == 403

    # والبحثُ ما زال قائمًا: لا محاولةٍ منها وقعت.
    assert title in await _titles(a)

    # **وصاحبُه يفعل الثلاثةَ كلَّها.**
    async with _client(a) as http:
        assert (await http.post(ARCHIVE.format(pid=project_id))).status_code == 200
        assert (await http.delete(TRASH.format(pid=project_id))).status_code in (200, 204)
    assert title not in await _titles(a)

    # والاسترجاعُ لصاحبه وحده أيضًا — كالحذف الذي يعكسه.
    async with _client(editor) as http:
        refused = await http.post(RESTORE.format(pid=project_id))
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == OWNER_ONLY
    async with _client(a) as http:
        assert (await http.post(RESTORE.format(pid=project_id))).status_code == 200
    assert title in await _titles(a)


@requires_db
@pytest.mark.asyncio
async def test_j_a_same_tenant_outsider_still_gets_404_on_lifecycle(two_tenants):
    """**ولا يتحوّل الرفضُ الجديد إلى عدّادِ بحوث**: الغريبُ يبقى ٤٠٤."""
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ لا يُعَدّ وجودُه")
    outsider = await _second_user(a["tenant_id"], email=f"os-{uuid.uuid4().hex[:8]}@x.test")

    async with _client(outsider) as http:
        assert (await http.post(ARCHIVE.format(pid=project_id))).status_code == 404
        assert (await http.delete(TRASH.format(pid=project_id))).status_code == 404
        assert (await http.post(RESTORE.format(pid=project_id))).status_code == 404


# ─────────── ب · مكتبةُ البحث: إدارةُ مصادر ───────────


@requires_db
@pytest.mark.asyncio
async def test_j_project_files_need_manage_sources_not_manage_data(two_tenants):
    """**والملفُّ المربوطُ ليس مجموعةَ بيانات** — فصفُّه صفُّ المصادر."""
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ تُربط به مصادر")
    file_id = await _file_owned_by(a, name="ورقةٌ مرجعية.pdf")

    librarian = await _second_user(a["tenant_id"], email=f"lb-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, librarian, project_id,
                             permissions=["view_project", "manage_sources"])
    analyst = await _second_user(a["tenant_id"], email=f"an-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, analyst, project_id,
                             permissions=["view_project", "manage_data"])

    # ── مديرُ المصادر يربط ويُزيل ──
    async with _client(librarian) as http:
        linked = await http.post(PROJECT_FILES.format(pid=project_id),
                                 json={"asset_id": str(file_id)})
        assert linked.status_code == 201, linked.text
        unlinked = await http.delete(
            f"{PROJECT_FILES.format(pid=project_id)}/{file_id}?acknowledged=true")
        assert unlinked.status_code == 200, unlinked.text

        # **ولا مجموعةَ بياناتٍ له**: إدارةُ المصادر ليست إدارةَ بيانات.
        dataset = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةٌ بلا إذن",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "e" * 64,
            "row_count": 5})
        assert dataset.status_code == 403, dataset.text

    # ── ومديرُ البيانات لا يربط ملفَّ مكتبة ──
    async with _client(analyst) as http:
        refused = await http.post(PROJECT_FILES.format(pid=project_id),
                                  json={"asset_id": str(file_id)})
        assert refused.status_code == 403, refused.text

        # ويُنشئ مجموعةً — فالصفّان منفصلان في الاتجاهين.
        made = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةٌ بإذنها",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "f" * 64,
            "row_count": 5})
        assert made.status_code == 201, made.text


# ─────────── ج · تقدّمٌ آمن مقابل بيانٍ تفصيليّ ───────────


@requires_db
@pytest.mark.asyncio
async def test_j_view_project_sees_safe_progress_but_no_data_internals(two_tenants):
    """**«ثمّة مجموعةُ بيانات» تُقال، وأسماءُ أعمدتها لا تُقال.**

    فالرحلةُ تقرأ عدًّا لا تفصيلًا — وذاك هو الحدُّ بين حالِ تقدّمٍ يراه كلُّ
    من في الفريق، وبين واجهةِ إدارةِ بياناتٍ لا يفتحها إلّا من يملكها.
    """
    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ له بياناتٌ ووسومُها")

    async with _client(a) as http:
        made = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةُ المشاركين",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "a" * 64,
            "row_count": 120})
        assert made.status_code == 201, made.text
        version_id = made.json()["id"]
        dataset_id = (await http.get(DATASETS)).json()[0]["id"]

        wrote = await http.put(DICTIONARY.format(vid=version_id), json=[
            {"column_name": "national_id", "description_ar": "رقم الهوية",
             "is_pii": True},
            {"column_name": "score", "description_ar": "الدرجة", "is_pii": False}])
        assert wrote.status_code == 200, wrote.text

    viewer = await _second_user(a["tenant_id"], email=f"pj-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, viewer, project_id, permissions=["view_project"])

    async with _client(viewer) as http:
        # ── حالُ التقدّم الآمن: مسموح ──
        journey = await http.get(JOURNEY.format(pid=project_id))
        assert journey.status_code == 200, journey.text
        blob = journey.text
        # و«ثمّة بيانات» تُقال بعدٍّ، لا بعمودٍ ولا بوسمٍ ولا ببصمة.
        assert "national_id" not in blob, "الرحلةُ أفشت اسمَ عمود"
        assert "رقم الهوية" not in blob, "الرحلةُ أفشت وصفَ عمود"
        assert "a" * 64 not in blob, "الرحلةُ أفشت بصمةَ نسخة"

        # ── والبيانُ التفصيليّ: ممنوع ──
        assert (await http.get(DICTIONARY.format(vid=version_id))).status_code == 403
        assert (await http.get(
            DATASET_VERSIONS.format(did=dataset_id))).status_code == 403
        # وقوائمُ الطبقة تُرشَّح بالصلاحية، فتعود فارغةً لا ممتلئة.
        for route in (DATASETS, PLANS, EXPORTS):
            listed = await http.get(route)
            assert listed.status_code == 200, listed.text
            assert listed.json() == [], f"{route} كشف صفوفًا لمن لا يديرها"

    # ── ومديرُ البيانات يقرأ التفصيل ──
    analyst = await _second_user(a["tenant_id"], email=f"da-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, analyst, project_id,
                             permissions=["view_project", "manage_data"])
    async with _client(analyst) as http:
        read = await http.get(DICTIONARY.format(vid=version_id))
        assert read.status_code == 200, read.text
        body = read.json()
        assert body["pii_columns"] == 1
        assert {e["column_name"] for e in body["entries"]} == {"national_id", "score"}
        assert (await http.get(
            DATASET_VERSIONS.format(did=dataset_id))).status_code == 200
        assert len((await http.get(DATASETS)).json()) == 1

    # ── والغريبُ لا يعرف أنّ شيئًا من هذا موجود ──
    outsider = await _second_user(a["tenant_id"], email=f"ox-{uuid.uuid4().hex[:8]}@x.test")
    async with _client(outsider) as http:
        assert (await http.get(DICTIONARY.format(vid=version_id))).status_code == 404
        assert (await http.get(
            DATASET_VERSIONS.format(did=dataset_id))).status_code == 404
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404


# ═══════ ك · الاطّلاعُ أساسٌ لكلّ صلاحيةٍ أخرى — في القوائم كما في البوابة ═══════
#
# **بابانِ كانا يختلفان على بحثٍ واحد.**
#
# `_decide` — وهي قرارُ التفويض الوحيد — تشترط `view_project` أساسًا قبل أن
# تنظر في شيء. وكان مُرشِّحُ القوائم (`project_ids_with`) يكتفي بالصلاحية
# المطلوبة وحدها، فوقع التناقض:
#
#   عضوٌ نُزع منه `view_project` وبقي له `manage_data`:
#     • يختفي البحثُ من «أبحاثي»،
#     • وتردّ `ensure_project_access` عليه ٤٠٤،
#     • **ويبقى ظاهرًا في قوائم طبقة التحليل**.
#
# وقائمةٌ تعرض ما لا يُفتح ليست تسامحًا: هي تسريبُ وجودِ بحثٍ وعنوانِه
# ومعرّفِه لمن سُحب مدخلُه — **ونزعُ الاطّلاع إنّما يُفعل ليمنع هذا بعينه**.


async def _set_member_permissions(owner, member_user_id, project_id, keys):
    """تُضبط الصفوفُ بالمسار القائم — ولا تُدسّ بيد."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        member = await collaboration.member_for(
            session, project_id=project_id, user_id=member_user_id)
        await collaboration.set_permissions(
            session, tenant_id=owner["tenant_id"], member=member,
            actor_user_id=owner["user_id"], keys=list(keys))


async def _analysis_lists(slot) -> dict[str, list]:
    async with _client(slot) as http:
        out = {}
        for name, route in (("datasets", DATASETS), ("plans", PLANS),
                            ("exports", EXPORTS)):
            response = await http.get(route)
            assert response.status_code == 200, f"{route}: {response.text}"
            out[name] = response.json()
        return out


@requires_db
@pytest.mark.asyncio
async def test_k_revoking_view_project_empties_the_analysis_lists_at_once(
        two_tenants):
    """**نزعُ الاطّلاع يسري فورًا وفي كلّ باب** — بلا دخولٍ جديد.

    فالرمزُ في يد الباحث كما هو، ولا شيءَ يُبطله: الحكمُ يُقرأ من القاعدة
    في كلّ طلب. فلو بقيت القائمةُ تعرض بعد النزع لكان ذلك عطبَ تفويضٍ لا
    تأخّرَ ذاكرةٍ مؤقّتة.
    """
    a = two_tenants["a"]
    title = "بحثٌ لعضوٍ يُنزع اطّلاعُه"
    project_id = await _owned_project(a, title=title)
    member = await _second_user(a["tenant_id"], email=f"rv-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, member, project_id,
                             permissions=["view_project", "manage_data"])

    # ── وله مجموعةُ بياناتٍ وخطّةٌ وتصدير، فالقوائمُ ليست فارغةً أصلًا ──
    async with _client(member) as http:
        made = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةٌ تُرى ثم تُحجب",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "1" * 64,
            "row_count": 30})
        assert made.status_code == 201, made.text
        version_id = made.json()["id"]

        planned = await http.post(PLANS, json={
            "project_id": str(project_id), "version_label": "v1",
            "summary_ar": "خطّةٌ أوّلية",
            "tests": [{"test_key": "t1", "test_kind": "descriptive",
                       "variables": ["age"], "note_ar": "وصفٌ أوّليّ"}]})
        assert planned.status_code == 201, planned.text

        exported = await http.post(EXPORTS, json={
            "dataset_version_id": version_id, "tool": "spss",
            # و`sav` صيغةُ استيرادٍ لا تصدير — والأداةُ تُصدّر `csv`/`sps`.
            "export_format": "sps"})
        assert exported.status_code == 201, exported.text

    # ── مُنح: يُرى في «أبحاثي» وفي القوائم الثلاث ──
    assert title in await _titles(member)
    before = await _analysis_lists(member)
    assert len(before["datasets"]) == 1, before
    assert len(before["plans"]) == 1, before
    assert len(before["exports"]) == 1, before

    # ══ نُزع `view_project` وحده، و`manage_data` باقٍ ══
    await _set_member_permissions(a, member["user_id"], project_id,
                                  ["manage_data"])

    # لا «أبحاثي» —
    assert title not in await _titles(member)

    # **ولا قائمةَ من قوائم التحليل** — وهذا هو العطبُ الذي يُغلق.
    after = await _analysis_lists(member)
    assert after["datasets"] == [], "المجموعاتُ ظهرت لمن نُزع اطّلاعُه"
    assert after["plans"] == [], "الخططُ ظهرت لمن نُزع اطّلاعُه"
    assert after["exports"] == [], "التصديراتُ ظهرت لمن نُزع اطّلاعُه"

    # والوصولُ المباشر محجوبٌ كما كان — فالبابانِ اتّفقا.
    async with _client(member) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 404
        assert (await http.get(DICTIONARY.format(vid=version_id))).status_code == 404
        assert (await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "لا تُكتب",
            "classification": "C2", "raw_label": "خام",
            "raw_checksum": "2" * 64, "row_count": 1})).status_code == 404

    # ══ وأُعيد الاطّلاع: يعود كلُّ شيء ══
    await _set_member_permissions(a, member["user_id"], project_id,
                                  ["view_project", "manage_data"])
    assert title in await _titles(member)
    restored = await _analysis_lists(member)
    assert len(restored["datasets"]) == 1
    assert len(restored["plans"]) == 1
    assert len(restored["exports"]) == 1


@requires_db
@pytest.mark.asyncio
async def test_k_the_owner_is_listed_whatever_their_permission_rows_say(
        two_tenants):
    """**والمالكُ يُدرَج بنسبه لا بصفوفه** — فالنزعُ لا يطاله."""
    from athera_api.db import tenant_session
    from athera_api.models.collaboration import ProjectMemberPermission
    from sqlalchemy import delete

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ لمالكٍ بلا صفوف")
    async with _client(a) as http:
        made = await http.post(DATASETS, json={
            "project_id": str(project_id), "name_ar": "مجموعةُ المالك",
            "classification": "C2", "raw_label": "خام", "raw_checksum": "3" * 64,
            "row_count": 10})
        assert made.status_code == 201, made.text

    # صفُّ عضويّةٍ للمالك تُمحى صفوفُه في القاعدة مباشرةً — حالٌ لا يصنعها
    # مسارٌ (الحرسُ يمنعه)، لكنّها قد تكون في صفوفِ ما قبل الحراسة.
    owner_member_id = await _owner_membership_id(a, project_id)
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await session.execute(delete(ProjectMemberPermission).where(
            ProjectMemberPermission.member_id == owner_member_id))

    assert "بحثٌ لمالكٍ بلا صفوف" in await _titles(a)
    lists = await _analysis_lists(a)
    assert len(lists["datasets"]) == 1, "المالكُ فقد مجموعتَه بنزع صفوفٍ لا تعنيه"


@requires_db
@pytest.mark.asyncio
async def test_k_no_permission_grants_access_without_the_view_baseline(two_tenants):
    """**عقدٌ على المفردة كلّها** — لا صلاحيةَ تفتح بابًا بلا الاطّلاع.

    والاختبارُ أعلاه يثبت الحالةَ التي وقعت (`manage_data`). وهذا يثبت
    القاعدةَ على **كلّ** صلاحيةٍ في المفردة، بما فيها ما لا قائمةَ له اليوم:
    فقائمةٌ تُكتب غدًا على `manage_sources` أو `manage_submission` لا تُعيد
    العطبَ نفسه، **لأنّ أحدًا لن يتذكّر أن يكتب لها اختبارَه**.

    ويُقاس المُرشِّحُ مباشرةً لا عبر مسار: المسارُ قد لا يوجد بعد، والقاعدةُ
    تُحرس قبل أن يوجد.
    """
    from athera_api.db import tenant_session
    from athera_api.services import collaboration, team

    a = two_tenants["a"]
    project_id = await _owned_project(a, title="بحثٌ يُقاس عليه العقد")
    member = await _second_user(a["tenant_id"], email=f"ct-{uuid.uuid4().hex[:8]}@x.test")
    await _invite_and_accept(a, member, project_id, permissions=["view_project"])

    others = [k for k in team.PROJECT_PERMISSIONS if k != "view_project"]
    assert len(others) == 8, others

    async def ids_for(permission: str) -> set:
        async with tenant_session(a["tenant_id"], member["user_id"]) as session:
            return await collaboration.project_ids_with(
                session, tenant_id=a["tenant_id"], user_id=member["user_id"],
                permission=permission)

    for permission in others:
        # ١) الصلاحيةُ وحدها بلا اطّلاع: **لا مدخل**.
        await _set_member_permissions(a, member["user_id"], project_id,
                                      [permission])
        assert project_id not in await ids_for(permission), (
            f"«{permission}» وحدها فتحت القائمة بلا اطّلاع")
        assert project_id not in await ids_for("view_project")

        # ٢) والاثنتان معًا: يُدرَج.
        await _set_member_permissions(a, member["user_id"], project_id,
                                      ["view_project", permission])
        assert project_id in await ids_for(permission), (
            f"«{permission}» مع الاطّلاع لم تُدرِج البحث")

        # ٣) والاطّلاعُ وحده لا يُدرِج في قائمةِ صلاحيةٍ أخرى.
        await _set_member_permissions(a, member["user_id"], project_id,
                                      ["view_project"])
        assert project_id in await ids_for("view_project")
        assert project_id not in await ids_for(permission), (
            f"الاطّلاعُ وحده أدرج البحث في قائمة «{permission}»")


def test_k_the_member_filter_proves_all_three_in_one_statement():
    """**والرحلةُ واحدة**: العضويّةُ الحيّة والاطّلاعُ والمطلوبةُ في عبارة.

    فالقاعدةُ في إقليمٍ آخر، وسدُّ ثغرةٍ باستعلامٍ ثانٍ يشتري الأمانَ بزمنٍ
    لا يلزم دفعه. ويُقرأ ذلك من العبارة المولَّدة لا من الشيفرة.
    """
    import inspect
    import uuid as _uuid

    from sqlalchemy import and_, select
    from sqlalchemy.orm import aliased

    from athera_api.models.collaboration import ProjectMemberPermission
    from athera_api.models.portfolio import ProjectMember
    from athera_api.services import collaboration

    body = inspect.getsource(collaboration._member_project_ids)
    assert "aliased(" in body and body.count("aliased(") == 2
    assert "VIEW_PROJECT" in body
    assert body.count("session.execute") == 1, "رحلتان حيث تكفي واحدة"

    baseline = aliased(ProjectMemberPermission)
    wanted = aliased(ProjectMemberPermission)
    sql = str(
        select(ProjectMember.project_id)
        .join(baseline, and_(baseline.member_id == ProjectMember.id,
                             baseline.permission_key == "view_project"))
        .join(wanted, and_(wanted.member_id == ProjectMember.id,
                           wanted.permission_key == "manage_data"))
        .where(ProjectMember.tenant_id == _uuid.uuid4(),
               ProjectMember.user_id == _uuid.uuid4(),
               ProjectMember.access_state == "active")
        .compile(compile_kwargs={"literal_binds": True}))
    assert sql.count("SELECT") == 1
    assert sql.count("JOIN") == 2
    for fragment in ("'view_project'", "'manage_data'", "'active'"):
        assert fragment in sql, fragment
