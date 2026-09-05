"""الموجةُ الأولى على مخطَّط التوسعة | NEW API + 0028, over real HTTP.

**هذه هي نافذةُ النشر بعينها.**

الترتيبُ في الإنتاج: يُرحَّل المخطَّط إلى `0028`، ثمّ **يُنشر خادمُ الموجة
الأولى وهو ما زال عليه**، ثمّ يُطبَّق `0029`. فبين النشر والعقد يخدم
الخادمُ الجديد مخطَّطًا لم يُفرض عليه العقد بعد.

ولا يُثبت ذلك شيءٌ ممّا سبق:
  · فحصُ الخادم القديم يستعمل SQL خامًّا، لا شيفرةَ الموجة.
  · ورحلةُ مرشَّح الإصدار تعمل على رأس السلسلة `0029`.

فالسؤالُ الباقي: أتقرأ نماذجُ الموجة وتكتب على `0028` بلا انفصامٍ بين
النموذج والمخطَّط؟ وهو سؤالٌ لا يُجاب إلّا بتشغيل شيفرتها على تلك القاعدة
بعينها، عبر HTTP، بهويّةٍ حقيقية.

**والقاعدةُ تُنتقى بمتغيّر البيئة لا بالصدفة.** يُشغَّل هذا الملفّ في
خطوةٍ مستقلّة يُوجَّه فيها `DATABASE_URL` إلى قاعدة النافذة؛ ولولا ذلك
لجرى صامتًا على قاعدة الاختبارات عند `0029` — فيخضرّ ولا يفحص النافذة.
ولذلك يُطلب `ATHERA_EXPECT_SCHEMA` صراحةً: بغيابه يُتخطّى الملفّ، وبحضوره
**يُؤكَّد أنّ رأس القاعدة هو المطلوب** ويسقط إن خالفه.
"""
from __future__ import annotations

import os
import uuid

import pytest

from tests.conftest import requires_db

EXPECTED_SCHEMA = os.environ.get("ATHERA_EXPECT_SCHEMA", "")

pytestmark = pytest.mark.skipif(
    not EXPECTED_SCHEMA,
    reason="نافذةُ النشر: يُضبط ATHERA_EXPECT_SCHEMA في خطوتها المستقلّة")


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


@requires_db
@pytest.mark.asyncio
async def test_the_database_is_the_window_and_not_the_head(db_ready):
    """**البابُ الأوّل: أنّ القاعدة هي المقصودة.**

    ولو جرى الملفُّ على `0029` لأخضرَّ ولم يفحص النافذة — وهو أسوأ من
    السقوط: تُقرأ خضرةٌ عن حالٍ لم تُجرَّب.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        head = (await session.execute(text(
            "SELECT version_num FROM alembic_version"))).scalar_one()
    assert head == EXPECTED_SCHEMA, (
        f"قاعدةُ هذا الفحص عند {head}، والمطلوب {EXPECTED_SCHEMA} — "
        "وُجّه DATABASE_URL إلى غير قاعدة النافذة")


@requires_db
@pytest.mark.asyncio
async def test_wave_one_reads_its_own_tables_on_the_expanded_schema(two_tenants):
    """**ولا انفصامَ بين النموذج والمخطَّط.**

    نماذجُ الموجة تختار أعمدةً أضافها 0027 و0028؛ فلو نقص عمودٌ واحد
    لسقطت القراءةُ بـ`UndefinedColumn` عند أوّل طلب — وهو ما يقع لو نُشر
    الخادمُ على مخطَّطٍ أقدم.
    """
    a = two_tenants["a"]
    async with _client(a["tenant_id"], a["user_id"]) as client:
        for path in ("/api/v1/theses", "/api/v1/workspace/projects"):
            answer = await client.get(path)
            assert answer.status_code < 500, (
                f"{path} انهار على مخطَّط النافذة: {answer.text[:180]}")


@requires_db
@pytest.mark.asyncio
async def test_wave_one_records_self_consent_over_http_on_the_window(two_tenants):
    """**المسارُ الأوّل الحسّاس للنشر: موافقةُ العضو عن نفسه.**

    وهو المسارُ الذي كان العقدُ سيقتله لو فُرض في 0028. يُشغَّل هنا
    بشيفرة الموجة كاملةً — موجّهٌ ومصادقةٌ وجلسةُ مستأجرٍ وصلاحية — لا
    بعبارةِ SQL.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember, ResearchProject

    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        project = ResearchProject(
            tenant_id=a["tenant_id"], working_title_ar="مشروعُ نافذة النشر",
            status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        project_id = project.id

        # **عضويةُ الفريق ليست تأليفًا** (§24). فالبذرةُ تُعلن التأليف
        # صراحةً — ولا تُزوّر موافقة: تبقى `not_requested` حتى تكتبها
        # النقطةُ نفسها.
        session.add(ProjectMember(
            tenant_id=a["tenant_id"], project_id=project_id,
            user_id=a["user_id"], display_name="الباحثُ نفسه",
            role="co_author", access_state="active",
            is_author=True, author_position=1,
            consent_state="not_requested"))
        await session.flush()

    async with _client(a["tenant_id"], a["user_id"]) as client:
        answer = await client.post(
            f"/api/v1/projects/{project_id}/members/me/consent",
            json={"granted": True})
    assert answer.status_code == 200, answer.text[:300]

    # **ويُقرأ من القاعدة لا من الاستجابة.** الاستجابةُ تقول ما يدّعيه
    # المعالج؛ والصفُّ يقول ما وقع.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        stored = (await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        )).scalar_one()
        assert stored.consent_recorded_at is not None, "لم يُكتب وقتُ الموافقة"
        assert stored.consent_method == "self", (
            f"طريقةُ الموافقة {stored.consent_method!r} لا 'self'")
        assert stored.consent_recorded_by == a["user_id"], "الموافقةُ بلا صاحبها"
        assert stored.consent_state == "granted"


@requires_db
@pytest.mark.asyncio
async def test_wave_one_reads_the_member_back_over_http_on_the_window(two_tenants):
    """**وتُقرأ بعد الكتابة**: دورةٌ كاملة على مخطَّط النافذة."""
    from athera_api.db import tenant_session
    from athera_api.models.collaboration import ProjectMemberPermission
    from athera_api.models.portfolio import ProjectMember, ResearchProject

    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        project = ResearchProject(
            tenant_id=a["tenant_id"], working_title_ar="مشروعُ القراءة",
            status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        project_id = project.id

        member = ProjectMember(
            tenant_id=a["tenant_id"], project_id=project_id,
            user_id=a["user_id"], display_name="عضوٌ يُقرأ",
            role="co_author", access_state="active")
        session.add(member)
        await session.flush()

        # **والعضويةُ لا تمنح صلاحية.** فتُمنح واحدةٌ بعينها — وهي التي
        # تطلبها النقطة — لا حزمةٌ تُرضي الفحص وتُخفي العقد.
        session.add(ProjectMemberPermission(
            tenant_id=a["tenant_id"], project_id=project_id,
            member_id=member.id, permission_key="view_project",
            granted_by=a["user_id"]))
        await session.flush()

    async with _client(a["tenant_id"], a["user_id"]) as client:
        listing = await client.get(f"/api/v1/projects/{project_id}/members")
        assert listing.status_code == 200, listing.text[:300]
        assert listing.json(), "قائمةُ الأعضاء فارغةٌ على مخطَّط النافذة"


@requires_db
@pytest.mark.asyncio
async def test_the_window_leaks_nothing_across_tenants(two_tenants):
    """**والعزلُ قائمٌ على النافذة كما على الرأس** — RLS لا تنتظر العقد."""
    a, b = two_tenants["a"], two_tenants["b"]
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        project = ResearchProject(
            tenant_id=a["tenant_id"], working_title_ar="مشروعٌ خاصّ",
            status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        project_id = project.id

    async with _client(b["tenant_id"], b["user_id"]) as stranger:
        answer = await stranger.get(f"/api/v1/projects/{project_id}/members")
        assert answer.status_code in {403, 404}, (
            f"جارٌ قرأ أعضاءَ مشروعِ غيره على النافذة: {answer.status_code}")
