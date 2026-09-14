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
