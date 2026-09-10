"""اختيارُ الباحث لفرصةِ رسالته | The researcher's selection of a thesis opportunity.

**الفجوةُ التي تُغلق هنا فجوةُ طريقٍ مسدود، لا فجوةُ منطق.**

عقدُ T1 (§12.1) ينتهي بأنّ «الباحثَ يختار الفرصة العلمية»، والرحلةُ تقف
عند `researcher_decision_required` حتى يقع ذلك الاختيار. ونقطةُ القرار
الوحيدة في المستودع كانت `routers/planning.py`، وهي تقرأ الفرصةَ بشرط
`project_id == project_id` — وفرصةُ الرسالة `project_id` فيها `NULL` حتى
تُحوَّل. **فالفعلُ المطلوبُ لم يكن له بابٌ يُطرق**، وكلُّ رسالةٍ تسلك
المسارَ الذهبيّ تقف عند الخطوة الثانية إلى الأبد.

**DB TESTS = NOT RUN على جهاز التطوير**: لا PostgreSQL. تُشغَّل في CI.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import uuid

import pytest

from athera_api.services.thesis import journey, selection

from tests.conftest import requires_db


# ══════════ ١. قرارٌ واحد، وكاتبٌ واحد ══════════


def test_the_two_decisions_are_the_only_ones():
    assert selection.DECISIONS == ("select", "exclude")


def test_selection_never_touches_the_publication_lifecycle():
    """**العمودان مُفرَدان عمدًا** — والاختيارُ لا يمسّ `status` بحال.

    ودمجُهما يجعل «مرفوضة» تحتمل معنيين: ورقةٌ أُوقف إنتاجُها، وفرصةٌ لم
    يخترها الباحث. وهما حكمان يقولهما شخصان في لحظتين.
    """
    source = inspect.getsource(selection.decide)
    tree = ast.parse(inspect.cleandoc(source))
    written = {
        target.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Attribute)
    }
    assert "status" not in written, "الاختيارُ كتب في دورة الإنتاج"
    assert "planning_status" in written


def test_both_routers_write_the_decision_through_one_authority():
    """**نسختان من كتابةٍ تفترقان بأوّل تعديل.**

    فرصةُ الرسالة تُختار من موجّه الرسائل، وفرصةُ المشروع من موجّه
    التخطيط — والكتابةُ واحدة.
    """
    from athera_api.routers import planning as planning_router
    from athera_api.routers import thesis as thesis_router

    for endpoint in (planning_router.decide_opportunity,
                     thesis_router.select_opportunity):
        source = inspect.getsource(endpoint)
        assert "selection.decide(" in source, (
            f"{endpoint.__name__} لا ينادي السلطةَ الواحدة")
        assert "planning_status =" not in source, (
            f"{endpoint.__name__} يكتب القرارَ بنفسه — نسخةٌ ثانية")


# ══════════ ٢. نقاطُ النهاية موجودة فعلًا ══════════


def test_the_journey_endpoints_the_product_needs_all_exist():
    """**دالّةٌ بلا نقطةِ نهايةٍ ميزةٌ غيرُ موجودة.**

    كانت `journey.build_thread` مكتوبةً ومفحوصةً ولا يناديها شيء، فالخيطُ
    الذهبيّ لا يُبنى في المنتج و`thread_ready` لا تقع أبدًا.
    """
    from athera_api.routers import thesis as thesis_router

    paths = {
        (tuple(sorted(getattr(route, "methods", []))), route.path)
        for route in thesis_router.router.routes
    }
    base = "/api/v1/theses/{thesis_id}"
    required = {
        (("GET",), f"{base}/journey"),
        (("POST",), f"{base}/opportunities/{{opportunity_id}}/select"),
        (("POST",), f"{base}/opportunities/{{opportunity_id}}/build-paper"),
        (("POST",), f"{base}/opportunities/{{opportunity_id}}/thread"),
    }
    assert required <= paths, f"نقاطٌ ناقصة: {sorted(required - paths)}"


# ══════════ ٣. كلُّ رمزٍ يُرفع له نصٌّ باللغتين ══════════


def test_every_error_code_this_surface_raises_has_bilingual_copy():
    """**رمزٌ يُرفع بلا مدخلٍ في الفهرس يصل الباحثَ رمزًا لا نصًّا.**

    وكانت `thesis.journey_blocked` كذلك: تُرفع عند كلِّ بوّابةٍ تردّ
    الباحثَ — وهي أكثرُ اللحظات حاجةً إلى جملةٍ مفهومة.

    وفحصُ اللغتين القائم يفحص **مداخلَ الفهرس** لا **ما يُرفع**، فرمزٌ لا
    مدخلَ له لا يمرّ به أصلًا. وهذا تثبيتٌ موجب من الجهة الأخرى.
    """
    from athera_api.i18n.catalog import CATALOG

    api = pathlib.Path(inspect.getfile(journey)).resolve().parents[2]
    surface = [api / "routers/thesis.py", *sorted((api / "services/thesis").glob("*.py"))]

    raised: dict[str, str] = {}
    for path in surface:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in {"AtheraError", "NotFound", "RightsGateError"}
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                raised.setdefault(node.args[0].value, path.name)

    assert raised, "لم يُعثر على رمزٍ واحد — تغيّر شكلُ الرفع وبطل الفحص"
    missing = {code: where for code, where in raised.items() if code not in CATALOG}
    assert missing == {}, f"رموزٌ تُرفع بلا نصٍّ باللغتين: {missing}"


# ══════════ ٤. ما يحتاج قاعدةً ══════════


async def _seed(tid, uid):
    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    async with tenant_session(tid, uid) as session:
        thesis = Thesis(tenant_id=tid, processing_state="ready_for_review")
        session.add(thesis)
        await session.flush()
        opportunity = PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis.id, opportunity_kind="sub_model",
            paper_kind="extraction", working_title_ar="ورقةٌ اصطناعية",
            status="discovered")
        session.add(opportunity)
        await session.flush()
        return thesis.id, opportunity.id


@requires_db
@pytest.mark.asyncio
async def test_selecting_advances_the_journey_to_the_rights_step(two_tenants):
    """**الدعوى: الرحلةُ تتحرّك.**

    قبل الاختيار تقول «اختر الفرصة»، وبعده تقول «الحقوق والتأليف» —
    وكانت تقول «اختر الفرصة» إلى الأبد لأنّ الاختيار كان يُقرأ من دورة
    الإنتاج، وتلك لا يحرّكها اختيارُ الباحث.
    """
    from sqlalchemy import select as sa_select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, opportunity_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            sa_select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        before = await journey.view(session, tenant_id=tid, thesis=thesis)

    assert before["state"] == journey.RESEARCHER_DECISION_REQUIRED
    assert journey.BLOCK_NO_SELECTION in before["blocking_reasons"]

    async with tenant_session(tid, uid) as session:
        opportunity = (await session.execute(
            sa_select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()
        await selection.decide(
            session, tenant_id=tid, opportunity=opportunity, actor_user_id=uid,
            decision=selection.SELECT, reason="أقربها إلى سؤالي")

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            sa_select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        after = await journey.view(session, tenant_id=tid, thesis=thesis)
        opportunity = (await session.execute(
            sa_select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()

    # **الخطوةُ الثانية صارت بالغة** — وكانت خطوةً ميّتة في الخريطة.
    assert after["state"] == journey.RIGHTS_REQUIRED
    assert journey.BLOCK_NO_SELECTION not in after["blocking_reasons"]
    assert journey.BLOCK_RIGHTS in after["blocking_reasons"]
    # **ودورةُ الإنتاج لم تُمسّ.**
    assert opportunity.status == "discovered"
    assert opportunity.planning_status == "selected"


@requires_db
@pytest.mark.asyncio
async def test_the_rights_gate_is_not_satisfied_by_selection_alone(two_tenants):
    """**بوّابتان لا واحدة.** كانتا تُقرآن من الشرط نفسه، فكانتا واحدة."""
    from sqlalchemy import select as sa_select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, opportunity_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        opportunity = (await session.execute(
            sa_select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()
        await selection.decide(
            session, tenant_id=tid, opportunity=opportunity, actor_user_id=uid,
            decision=selection.SELECT)
        # حالُ الإنتاج تتقدّم بلا ختمِ البوّابة — وهي الحالةُ التي كانت
        # تُقرأ حقوقًا مُجازة.
        opportunity.status = "ready_to_submit"

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            sa_select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        facts = await journey.load_facts(session, tenant_id=tid, thesis=thesis)

    assert facts.selected_opportunity is True
    assert facts.rights_passed is False, (
        "حالُ الإنتاج قُرئت اعتمادًا للحقوق — والاعتمادُ ختمُه في عموده")


@requires_db
@pytest.mark.asyncio
async def test_a_built_paper_can_actually_be_opened_in_the_studio(two_tenants):
    """**السلسلةُ لا تبدأ من وسطها.**

    `Manuscript → ManuscriptVersion → ManuscriptSection`. وكلُّ مدخلٍ إلى
    استوديو الورقة يمرّ على النسخة الحالية، فمخطوطةٌ بلا نسخة صفٌّ قائمٌ
    لا باب له: يقول الزرُّ «افتح استوديو الورقة» ويُجيب الاستوديو «غير
    موجودة».
    """
    from sqlalchemy import func, select as sa_select

    from athera_api.db import tenant_session
    from athera_api.models.publishing import Manuscript, ManuscriptVersion
    from athera_api.models.thesis import PublicationOpportunity, Thesis
    from athera_api.services import consent

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    file_id = uuid.uuid4()

    async with tenant_session(tid, uid) as session:
        thesis = Thesis(tenant_id=tid, processing_state="ready_for_review",
                        file_id=file_id)
        session.add(thesis)
        await session.flush()
        thesis_id = thesis.id
        opportunity = PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis_id, opportunity_kind="sub_model",
            paper_kind="extraction", working_title_ar="ورقةٌ اصطناعية",
            status="ready_to_submit", planning_status="selected")
        session.add(opportunity)
        await session.flush()
        opportunity_id = opportunity.id
        # البوّابتان: ختمُ GT1، ثمّ الإذنُ الصريح.
        opportunity.rights_approved_by = uid
        opportunity.rights_approved_at = func.now()
        opportunity.authorship_approved_by = uid
        opportunity.authorship_approved_at = func.now()
        await consent.record_decision(
            session, tenant_id=tid, file_id=file_id, actor_user_id=uid,
            granted=True, provider="anthropic", model="m")

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            sa_select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        opportunity = (await session.execute(
            sa_select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()
        outcome = await journey.build_paper(
            session, tenant_id=tid, actor_user_id=uid, thesis=thesis,
            opportunity=opportunity)

    async with tenant_session(tid, uid) as session:
        record = (await session.execute(
            sa_select(Manuscript)
            .where(Manuscript.id == outcome.manuscript_id))).scalar_one()
        versions = (await session.execute(
            sa_select(func.count(ManuscriptVersion.id))
            .where(ManuscriptVersion.manuscript_id == outcome.manuscript_id))
        ).scalar_one()

    assert versions == 1, "مخطوطةٌ بُنيت بلا نسخة — لا يفتحها الاستوديو"
    assert record.current_version_id is not None
