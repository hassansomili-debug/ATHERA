"""بناءُ الورقة من فرصة | build-paper — التكرارُ الآمن وحدودُه (شريحة ٢ب).

**الدعوى الجوهرية**: إعادةُ الطلب لا تُنشئ صفًّا ثانيًا. مشروعٌ وهيكلٌ
ومخطوطةٌ مرّةً واحدة، ومهما تكرّر النداء تُعاد المعرّفاتُ نفسُها.

وقرارُ إعادة الاستعمال — «أهذا الأثرُ قائمٌ سلفًا؟» — قرارٌ على بياناتٍ
عادية، فيُفحص هنا بلا قاعدة. وما يحتاج قاعدةً مكتوبٌ ويُقال إنّه لم يُشغَّل.
"""
from __future__ import annotations

import inspect
import pathlib
import uuid

import pytest

from athera_api.services.thesis import journey
from tests.conftest import requires_db, seed_file


def _client(tenant_id, user_id, locale="ar"):
    """عميلٌ برمز وصولٍ حقيقيّ — لا جلسةٌ مزروعة."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


# ══════════ ١. قرارُ إعادة الاستعمال — صافٍ، ويُفحص بلا قاعدة ══════════


def test_nothing_exists_means_every_artifact_must_be_created():
    assert journey.to_create(journey.ArtifactSet()) == (
        "project", "thread", "outline", "manuscript")


def test_a_rerun_on_a_complete_artifact_set_creates_nothing():
    """**دعوى التكرار الآمن.**"""
    a, b, c, d = (uuid.uuid4() for _ in range(4))
    full = journey.ArtifactSet(project_id=a, thread_id=b, outline_id=c, manuscript_id=d)
    assert journey.to_create(full) == ()
    assert journey.reuses_everything(full) is True
    assert journey.to_reuse(full) == ("project", "thread", "outline", "manuscript")


def test_a_partial_set_creates_only_what_is_missing():
    a, c = uuid.uuid4(), uuid.uuid4()
    partial = journey.ArtifactSet(project_id=a, outline_id=c)
    assert journey.to_create(partial) == ("thread", "manuscript")
    assert journey.to_reuse(partial) == ("project", "outline")
    assert journey.reuses_everything(partial) is False


def test_the_thread_is_declared_pending_not_pretended_complete():
    """**ولا يُخترع صفٌّ ليُقال إنّ الخيط اكتمل.**

    بناءُ الخيط يقوم على أدلّةٍ ونداءِ نموذج، وذاك طَورٌ لاحق. فيُرصد قائمًا
    إن وُجد، ويُعلَن منتظَرًا إن لم يوجد — ولا يُدَّعى اكتمالُه.
    """
    assert "thread" not in journey.DETERMINISTIC_ARTIFACTS
    assert set(journey.DETERMINISTIC_ARTIFACTS) == {"project", "outline", "manuscript"}


# ══════════ ٢. حدودُ البناء: لا شبكة، ولا سلطةَ أقسامٍ ثانية ══════════


def test_building_a_paper_makes_no_network_call():
    """**بناءُ الورقة حتميّ**، فلا نداءَ نموذجٍ فيه أصلًا.

    وكان هذا الفحصُ يمسح الوحدةَ كلَّها؛ وقد صارت تنادي النموذجَ عمدًا في
    `build_thread`. فيُضيَّق إلى ما يصدق: **هذه الدالّةُ** بلا شبكة.
    """
    source = inspect.getsource(journey.build_paper)
    for symbol in ("Orchestrator", "run_structured_detached", "httpx",
                   "openai", "anthropic"):
        assert symbol not in source, f"نداءٌ خارجيّ في بناءٍ حتميّ: {symbol}"


def test_no_provider_sdk_is_ever_imported_directly():
    """**والبوّابةُ وحدها تنادي المزوّد.** لا SDK في هذه الوحدة بحال."""
    source = pathlib.Path(inspect.getfile(journey)).read_text(encoding="utf-8")
    for banned in ("import openai", "import anthropic", "from openai",
                   "from anthropic", "httpx."):
        assert banned not in source, f"نداءُ مزوّدٍ مباشر: {banned}"


def test_the_outline_carries_no_invented_sections():
    """**سياسةُ الأقسام هي السلطةُ الوحيدة** — ولا قائمةَ تُكتب هنا."""
    source = inspect.getsource(journey.build_paper)
    assert "sections=[]" in source
    for invented in ("introduction", "methodology", "discussion", "literature_review",
                     "references"):
        assert f'"{invented}"' not in source, f"قسمٌ مكتوبٌ بيد: {invented}"


def test_the_router_does_not_re_implement_the_gates():
    """**والموجّه رقيق.** نسختان من بوّابةٍ تفترقان بأوّل تعديل."""
    from athera_api.routers import thesis as thesis_router

    source = inspect.getsource(thesis_router.build_paper)
    assert "journey.build_paper(" in source
    for leaked in ("overlap_unresolved", "rights_passed", "ai_consent_granted"):
        assert leaked not in source, f"منطقُ بوّابةٍ سُرّب إلى الموجّه: {leaked}"


def test_blocked_reasons_travel_as_codes():
    blocked = journey.JourneyBlocked((journey.BLOCK_OVERLAP, journey.BLOCK_RIGHTS))
    assert blocked.reasons == (journey.BLOCK_OVERLAP, journey.BLOCK_RIGHTS)


# ══════════ ٣. ما يحتاج قاعدةً — مكتوبٌ ولم يُشغَّل هنا ══════════
#
# **DB TESTS = NOT RUN على جهاز التطوير**: لا PostgreSQL. تُشغَّل في CI.


async def _seed_thesis_and_opportunity(tid, uid, *, status="ready_to_submit",
                                       with_consent=True):
    """فرصةٌ في حالٍ **متّسقةٍ مع القاعدة**، لا حالٌ تُكتب وحدها.

    **و`ready_to_submit` ليست مجرّد نصٍّ في عمود.** القيد
    `ck_opportunity_ready_requires_rights_and_authorship` (الترحيل 0010،
    §23.9/TC-06) يشترط ختمَي الحقوق والتأليف معها، وهو القيدُ الذي يحمل
    بوّابةَ السبرنت. وكانت التجهيزةُ تكتب الحالَ وتترك الأختامَ فارغةً،
    فيسقط الإدراجُ نفسُه في CI قبل أن يبدأ الفحصُ شيئًا.

    فيُختمان **في المُنشئ** لا بعد `flush`: القيدُ يُفحص عند الإدراج، فختمٌ
    يُكتب بعده يصل متأخّرًا.
    """
    from sqlalchemy import func

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis
    from athera_api.services import consent

    # ما تشترطه القاعدةُ لهذه الحال — ولا شيءَ لغيرها.
    gates = {}
    if status == "ready_to_submit":
        gates = dict(rights_approved_by=uid, rights_approved_at=func.now(),
                     authorship_approved_by=uid, authorship_approved_at=func.now())

    async with tenant_session(tid, uid) as session:
        # **ورسالةٌ بلا ملفٍّ لا إذنَ لها.** `build_paper` تقرأ الإذنَ عن
        # `thesis.file_id`، فرسالةٌ بلا ملفّ تُردّ بـ`ai_consent_required`
        # أبدًا — لا لأنّ البوّابةَ تعمل، بل لأنّ التجهيزةَ ناقصة.
        file_id = await seed_file(session, tenant_id=tid, uploaded_by=uid)
        thesis = Thesis(tenant_id=tid, processing_state="ready_for_review",
                        file_id=file_id)
        session.add(thesis)
        await session.flush()
        opportunity = PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis.id, opportunity_kind="sub_model",
            paper_kind="extraction", working_title_ar="ورقةٌ اصطناعية",
            status=status, **gates)
        session.add(opportunity)
        await session.flush()

        # والإذنُ صريحٌ ومسجَّل — لا يُمنح تلقائيًّا، لا في الشيفرة ولا هنا.
        if with_consent:
            await consent.record_decision(
                session, tenant_id=tid, file_id=file_id, actor_user_id=uid,
                granted=True, provider="anthropic", model="m")
        return thesis.id, opportunity.id


@requires_db
@pytest.mark.asyncio
async def test_building_a_paper_twice_creates_no_duplicate_artifacts(two_tenants):
    """مشروعٌ وهيكلٌ ومخطوطةٌ **مرّةً واحدة**، مهما تكرّر النداء."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.planning import ManuscriptOutline
    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.publishing import Manuscript
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, opportunity_id = await _seed_thesis_and_opportunity(tid, uid)

    outcomes = []
    for _ in range(2):
        async with tenant_session(tid, uid) as session:
            thesis = (await session.execute(
                select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
            opportunity = (await session.execute(
                select(PublicationOpportunity)
                .where(PublicationOpportunity.id == opportunity_id))).scalar_one()
            outcomes.append(await journey.build_paper(
                session, tenant_id=tid, actor_user_id=uid, thesis=thesis,
                opportunity=opportunity))

    first, second = outcomes
    assert first.project_id == second.project_id
    assert first.outline_id == second.outline_id
    assert first.manuscript_id == second.manuscript_id
    # **والثانيةُ لم تُنشئ شيئًا.**
    assert second.created == ()
    assert set(second.reused) >= {"project", "outline", "manuscript"}

    async with tenant_session(tid, uid) as session:
        projects = (await session.execute(
            select(func.count(ResearchProject.id))
            .where(ResearchProject.tenant_id == tid))).scalar_one()
        outlines = (await session.execute(
            select(func.count(ManuscriptOutline.id))
            .where(ManuscriptOutline.opportunity_id == opportunity_id))).scalar_one()
        manuscripts = (await session.execute(
            select(func.count(Manuscript.id))
            .where(Manuscript.opportunity_id == opportunity_id))).scalar_one()

    assert (projects, outlines, manuscripts) == (1, 1, 1), (
        f"تكرّر أثر: مشاريع={projects} هياكل={outlines} مخطوطات={manuscripts}")


@requires_db
@pytest.mark.asyncio
async def test_an_opportunity_of_another_thesis_is_refused(two_tenants):
    """الفرصةُ يجب أن تكون **لهذه الرسالة** — والنسبُ يُفحص لا يُفترض."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    _, stranger_id = await _seed_thesis_and_opportunity(tid, uid)

    async with tenant_session(tid, uid) as session:
        mine = Thesis(tenant_id=tid, processing_state="ready_for_review")
        session.add(mine)
        await session.flush()
        mine_id = mine.id

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            select(Thesis).where(Thesis.id == mine_id))).scalar_one()
        stranger = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.id == stranger_id))).scalar_one()
        with pytest.raises(journey.JourneyBlocked) as blocked:
            await journey.build_paper(
                session, tenant_id=tid, actor_user_id=uid, thesis=thesis,
                opportunity=stranger)

    assert "opportunity_not_of_this_thesis" in blocked.value.reasons


@requires_db
@pytest.mark.asyncio
async def test_building_without_consent_is_refused(two_tenants):
    """**ولا يُمنح الإذنُ تلقائيًّا** — والبناءُ يقف ويُسمّي ما ينقصه."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    # **والإذنُ غائبٌ صراحةً، لا لأنّ التجهيزةَ ناقصة.**
    #
    # كانت الرسالةُ تُبنى بلا ملفٍّ أصلًا، فيُردّ البناءُ بـ«لا إذن» —
    # ويمرّ الفحصُ لسببٍ غير الذي يدّعيه: لا ملفَّ يُسأل عنه، لا قرارَ
    # رفضٍ يُقرأ. فالملفُّ قائمٌ الآن، والإذنُ وحده هو الغائب.
    thesis_id, opportunity_id = await _seed_thesis_and_opportunity(
        tid, uid, with_consent=False)

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        opportunity = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()
        with pytest.raises(journey.JourneyBlocked) as blocked:
            await journey.build_paper(
                session, tenant_id=tid, actor_user_id=uid, thesis=thesis,
                opportunity=opportunity)

    # رسالةٌ لها ملفٌّ ولا إذنَ عليه — فالبوّابةُ تقف وتُسمّي ما ينقص.
    assert journey.BLOCK_NO_CONSENT in blocked.value.reasons


@requires_db
@pytest.mark.asyncio
async def test_the_journey_endpoint_reports_state_without_a_percentage(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    async with tenant_session(tid, uid) as session:
        thesis = Thesis(tenant_id=tid, processing_state="uploaded")
        session.add(thesis)
        await session.flush()
        thesis_id = thesis.id

    async with _client(tid, uid) as client:
        response = await client.get(f"/api/v1/theses/{thesis_id}/journey")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == journey.UPLOADED
    assert body["can_build_paper"] is False
    assert journey.BLOCK_NO_OPPORTUNITY in body["blocking_reasons"]
    # **والمفرداتُ تُقرأ من الخدمة لا تُعدّ بالرقم.**
    #
    # كان الفحصُ `== 17`، وكانت الحالاتُ سبعَ عشرة يومَ كُتب. ثمّ تقاعدت
    # `draft_ready` — مفردةٌ معلَنةٌ لا تعيدها `derive_state` في أيّ فرع —
    # فصارت ستَّ عشرة، وبقي الرقمُ المكتوبُ بيدٍ يشير إلى ماضٍ. ورقمٌ
    # يُكتب بجانب سلطةٍ يفترق عنها بأوّل تعديل.
    assert body["states"] == list(journey.STATES)
    # **ولا نسبةَ في العقد.**
    assert not any("percent" in key for key in body)
