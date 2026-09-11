"""عزلُ أدلّة الرسالة | Thesis evidence isolation (AI Journey V1، شريحة ١).

**العطب.** `planning.context.build` كان يقرأ كلَّ ذاكرةٍ موثقة في المستأجر:
`tenant_id` و`verification_status == "verified"` وحدهما. ورسالتان لباحثٍ
واحد في مستأجرٍ واحد تمرّان حارسَ المستأجر معًا — فرحلةُ الرسالة (أ) كانت
تُصاغ من أدلّة الرسالة (ب)، وتُنسب إليها.

**والعزلُ حدٌّ في الاستعلام لا تعليمةٌ في مُوجِّه.** «لا تستعمل أدلّة رسالةٍ
أخرى» جملةٌ تُطاع أو لا تُطاع ولا يُفحص أثرُها؛ والحدُّ يمنع الصفَّ من
الوصول أصلًا: **ما لم يُقرأ لا يُسرَّب**.

## ولماذا القاعدةُ دالّةٌ صافية

لا PostgreSQL على جهاز التطوير، ففحصٌ يحتاج قاعدةً لا يُشغَّل هنا. فالقاعدة
تُكتب دالّةً صافية على بياناتٍ عادية (`scoped_to_source`)، ويُبنى فوقها
حدُّ الاستعلام وحارسُ العمق. فما يُفحص هنا يُفحص فعلًا، وما يحتاج قاعدةً
يُقال إنّه لم يُشغَّل.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import uuid

import pytest

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

# ══════════════════ ١. القاعدة: دالّةٌ صافية تُفحص كما هي ══════════════════


def test_the_scope_rule_admits_only_the_thesis_own_file():
    from athera_api.services.planning import context as ctx

    mine, other = uuid.uuid4(), uuid.uuid4()
    assert ctx.scoped_to_source(mine, source_file_id=mine) is True
    assert ctx.scoped_to_source(other, source_file_id=mine) is False


def test_a_memory_with_no_source_file_is_refused_under_a_scope():
    """**و`None` لا يتسلّل.** ذاكرةٌ بلا مصدرِ ملفّ ليست دليلًا لهذه الرسالة،
    وقبولُها يفتح البابَ الذي يُغلق هنا."""
    from athera_api.services.planning import context as ctx

    assert ctx.scoped_to_source(None, source_file_id=uuid.uuid4()) is False


def test_unscoped_project_planning_is_untouched():
    """تخطيطُ مشروعٍ غيرِ مشتقٍّ من رسالة يبقى كما كان — ولا حدَّ عليه."""
    from athera_api.services.planning import context as ctx

    assert ctx.scoped_to_source(uuid.uuid4(), source_file_id=None) is True
    assert ctx.scoped_to_source(None, source_file_id=None) is True


def test_the_depth_guard_raises_and_never_filters_silently():
    """**التصفيةُ الصامتة أسوأ من السقوط.**

    الحدُّ الحقيقيّ في SQL؛ وهذا الحارسُ يكشف تعطُّلَه بدل أن يستره. فلو
    صُفّي الصفُّ الشاردُ بصمت لبقيت العزلةُ قائمةً بالصدفة لا بالتصميم.
    """
    from athera_api.services.planning import context as ctx

    mine, other = uuid.uuid4(), uuid.uuid4()

    class _Item:
        def __init__(self, source_file_id):
            self.memory_id = uuid.uuid4()
            self.source_file_id = source_file_id

    assert len(ctx.enforce_source_scope([_Item(mine)], source_file_id=mine)) == 1
    with pytest.raises(ctx.EvidenceIsolationError):
        ctx.enforce_source_scope([_Item(other)], source_file_id=mine)


# ══════════════ ٢. الحدُّ في الاستعلام — حارسٌ بنيويّ لا قراءةُ عين ══════════════


def test_the_isolation_lives_in_the_sql_not_in_a_prompt():
    """**حارسٌ على الموضع نفسه.** إن نُقل الحدُّ يومًا إلى مُوجِّه، سقط هذا."""
    from athera_api.services.planning import context as ctx

    tree = ast.parse(inspect.getsource(ctx.build))
    wheres = [ast.unparse(n) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "where"]
    assert any("ResearcherMemory.source_file_id" in w for w in wheres), (
        "حدُّ المصدر ليس في `.where()` — العزلُ لم يعد في طبقة الاستعلام")

    module_source = pathlib.Path(inspect.getfile(ctx)).read_text(encoding="utf-8")
    for instruction in ("do not use evidence", "only use evidence from",
                        "لا تستعمل أدلة"):
        assert instruction not in module_source.lower(), (
            f"تعليمةُ عزلٍ نصّية: {instruction} — والتعليمةُ ليست حدًّا")


def test_the_drafting_caller_actually_passes_the_scope():
    """**وحدٌّ لا يُمرَّر إليه شيء حدٌّ ميّت.**"""
    from athera_api.routers import manuscript_drafting

    source = pathlib.Path(inspect.getfile(manuscript_drafting)).read_text(encoding="utf-8")
    assert "_thesis_source_scope" in source
    assert "source_file_id=source_file_id" in source


def test_a_scoped_snapshot_has_its_own_fingerprint():
    """لقطةٌ مقيَّدةٌ برسالة ليست اللقطةَ المفتوحة، ولو تطابقت ذاكراتُها."""
    from athera_api.services.planning import context as ctx

    memories = [uuid.uuid4()]
    project = uuid.uuid4()
    open_fp = ctx.fingerprint_of(memories, capability="c", project_id=project)
    scoped_fp = ctx.fingerprint_of(memories, capability="c", project_id=project,
                                   source_file_id=uuid.uuid4())
    assert open_fp != scoped_fp


# ══════════════════ ٣. الجسر: الفرصة → المشروع ══════════════════


def test_conversion_binds_project_id_and_keeps_both_links():
    """**والرابطةُ كانت مقطوعة من جهتها.** `converted_project_id` وحده
    كان يُكتب، و`project_id` — التي يقرؤها التخطيط — تبقى فارغة."""
    from athera_api.routers import thesis as thesis_router

    source = inspect.getsource(thesis_router.convert_to_project)
    assert "opportunity.project_id = project.id" in source
    assert "opportunity.converted_project_id = project.id" in source
    # والرسالةُ تبقى مصدرَ الفرصة بعد التحويل.
    assert "opportunity.thesis_id = None" not in source
    # وإعادةُ التحويل تُعيد ما وقع، ولا تُنشئ مشروعًا ثانيًا.
    assert "if opportunity.converted_project_id is not None:" in source


# ══════════════════ ٤. ما يحتاج قاعدةً — مكتوبٌ ولم يُشغَّل هنا ══════════════════
#
# **DB TESTS = NOT RUN على جهاز التطوير**: لا PostgreSQL. تُشغَّل في CI.


@requires_db
@pytest.mark.asyncio
async def test_a_journey_never_sees_another_thesis_evidence(two_tenants):
    """**الدعوى المركزية.** رسالتان في مستأجرٍ واحد، ولكلٍّ دليلُها الموثق."""
    from sqlalchemy import func

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.services.planning import context as ctx

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = uuid.uuid4()

    async with tenant_session(tid, uid) as session:
        # **وملفّان حقيقيّان** — `source_file_id` مفتاحٌ أجنبيّ، ومعرّفٌ
        # مُختلَقٌ يرفضه `fk_researcher_memories_source_file_id`.
        file_a = await seed_file(session, tenant_id=tid, uploaded_by=uid,
                                 name="رسالة-أ.pdf")
        file_b = await seed_file(session, tenant_id=tid, uploaded_by=uid,
                                 name="رسالة-ب.pdf")
        for file_id, statement in ((file_a, "دليلُ الرسالة أ"),
                                   (file_b, "دليلُ الرسالة ب")):
            session.add(ResearcherMemory(
                tenant_id=tid, memory_category="project_decision",
                statement_ar=statement, value={"field_key": "sample_size"},
                source_type="upload", source_file_id=file_id,
                source_locator="§1 ¶1", source_quote=statement,
                # **و«موثق» يحمل مُحقِّقَه وتاريخَه** — القيد
                # `ck_memory_verified_requires_verifier` (الترحيل 0005، §7.4)
                # يرفض غير ذلك، وهو محقّ: توثيقٌ بلا مُوثِّقٍ دعوى بلا صاحب.
                # وكانت التجهيزةُ تكتب الحالَ وتترك العمودين فارغين، فلا
                # يسقط شيءٌ على جهازٍ بلا قاعدة ويسقط الإدراجُ في CI.
                verification_status="verified",
                verified_by=uid, verified_at=func.now(),
            ))

    async with tenant_session(tid, uid) as session:
        scoped_a = await ctx.build(
            session, tenant_id=tid, project_id=project,
            capability="publication_planning_external_c2", source_file_id=file_a)
        scoped_b = await ctx.build(
            session, tenant_id=tid, project_id=project,
            capability="publication_planning_external_c2", source_file_id=file_b)

    assert {i.source_file_id for i in scoped_a.items} == {file_a}
    assert {i.source_file_id for i in scoped_b.items} == {file_b}
    assert "دليلُ الرسالة ب" not in " ".join(i.statement for i in scoped_a.items)
    assert "دليلُ الرسالة أ" not in " ".join(i.statement for i in scoped_b.items)
    # ولقطتان مختلفتان لا تتشاركان بصمة.
    assert scoped_a.fingerprint != scoped_b.fingerprint


@requires_db
@pytest.mark.asyncio
async def test_cross_tenant_isolation_is_preserved(two_tenants):
    """**والحارسُ الأقدم يبقى.** إضافةُ حدٍّ لا تُضعف الحدَّ القائم."""
    from sqlalchemy import func

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.services.planning import context as ctx

    a, b = two_tenants["a"], two_tenants["b"]

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        # الملفُّ صفٌّ حقيقيّ في مستأجر (ب) — و(أ) يطلب معرّفَه بعدُ.
        shared_file = await seed_file(
            session, tenant_id=b["tenant_id"], uploaded_by=b["user_id"])
        session.add(ResearcherMemory(
            tenant_id=b["tenant_id"], memory_category="project_decision",
            statement_ar="دليلُ الجار", value={"field_key": "sample_size"},
            source_type="upload", source_file_id=shared_file,
            source_locator="§1 ¶1", source_quote="دليلُ الجار",
            # ومُحقِّقُ الجار من مستأجره — لا من (أ).
            verification_status="verified",
            verified_by=b["user_id"], verified_at=func.now(),
        ))

    # المستأجر (أ) يطلب المعرّف نفسه — ولا يرى شيئًا.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        context = await ctx.build(
            session, tenant_id=a["tenant_id"], project_id=uuid.uuid4(),
            capability="publication_planning_external_c2", source_file_id=shared_file)

    assert context.items == ()


@requires_db
@pytest.mark.asyncio
async def test_converting_twice_creates_no_second_project(two_tenants):
    """**ز · إعادةُ التحويل لا تُضاعف مشروعًا.**"""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    async with tenant_session(tid, uid) as session:
        # **ولا فرصةَ بلا مصدر** — `has_source` (0017) تشترط رسالةً أو
        # مشروعًا، وهذه كانت بلا كليهما. والفرصةُ هنا من رسالة.
        thesis = Thesis(tenant_id=tid, processing_state="ready_for_review")
        session.add(thesis)
        await session.flush()
        # و`ready_to_submit` تشترط ختمَي الحقوق والتأليف في المُنشئ (0010).
        opportunity = PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis.id,
            opportunity_kind="sub_model", paper_kind="extraction",
            working_title_ar="ورقةٌ اصطناعية", status="ready_to_submit",
            rights_approved_by=uid, rights_approved_at=func.now(),
            authorship_approved_by=uid, authorship_approved_at=func.now())
        session.add(opportunity)
        await session.flush()
        opportunity_id = opportunity.id

    async with _client(tid, uid) as client:
        first = await client.post(
            f"/api/v1/opportunities/{opportunity_id}/convert-to-project")
        second = await client.post(
            f"/api/v1/opportunities/{opportunity_id}/convert-to-project")

    assert first.status_code == 200 and second.status_code == 200

    async with tenant_session(tid, uid) as session:
        projects = (await session.execute(
            select(func.count(ResearchProject.id))
            .where(ResearchProject.tenant_id == tid))).scalar_one()
        row = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.id == opportunity_id))).scalar_one()

    assert projects == 1, "إعادةُ التحويل أنشأت مشروعًا ثانيًا"
    assert row.project_id is not None
    assert row.project_id == row.converted_project_id
