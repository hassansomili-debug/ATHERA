"""العقلُ على بحثٍ حقيقيّ: العقد، والعزل، والتقادم | Brain V1 end to end (Wave 2-A §88–§93).

**ثلاثةُ أشياء تُثبَت هنا على قاعدةٍ حيّة، ولا تُثبت بغيرها:**

١) **الحقلُ المُعلَن يصل.** الدرسُ من الإنتاج وثمنُه معروف: حقلٌ يُحسب ولا
   يُعلنه النموذجُ يُطرح صامتًا — `extra="ignore"` هي الافتراض — فتقرأ
   الشاشةُ `undefined` أبدًا. فيُقرأ هنا **العقدُ المنشور** (`app.openapi()`)
   والجوابُ الحقيقيّ عبر الموجّه، لا رقعةٌ في متصفّح تُلفّق الجواب فتتجاوز
   النموذجَ الذي كان هو موضعَ العطب.

٢) **بحثٌ لا يستعير من بحث، ولا مستأجرٌ من مستأجر.** وRLS لا تحرس الأولى:
   المستأجرُ يملك بحثيه معًا.

٣) **والقولُ القديم يَبْلى.** توصيةٌ قيلت تحت بصمةٍ ثمّ تغيّر البحث لا
   تبقى معروضةً على أنّها جارية.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from tests.conftest import requires_db

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


async def _bare_project(tenant_id, user_id, *, title="بحثٌ في أوّله"):
    """**بحثٌ خاوٍ فعلًا** — لا سؤال، ولا منهج، ولا مصدر، ولا بيانات (§90)."""
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tenant_id, user_id) as session:
        project = ResearchProject(tenant_id=tenant_id, working_title_ar=title,
                                  status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        return project.id


async def _add_question(tenant_id, user_id, project_id, label="ما أثر التدريب؟"):
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import ThreadElement

    async with tenant_session(tenant_id, user_id) as session:
        session.add(ThreadElement(tenant_id=tenant_id, project_id=project_id,
                                  element_type="question", label_ar=label, ordinal=1))


async def _add_method(tenant_id, user_id, project_id, *, family="correlational",
                      sample_size=None):
    """منهجٌ مسجَّل — **وحجمُ العيّنة اختياريّ عمدًا**.

    فالجسرُ يُنشئ كيانَ عيّنةٍ لكلّ منهج، وحجمُه `missing()` إن لم يُذكر.
    والتفريقُ بينهما هو ما يجعل «حدِّد حجم العيّنة» قاعدةً تُطلق.
    """
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import Method

    async with tenant_session(tenant_id, user_id) as session:
        session.add(Method(tenant_id=tenant_id, project_id=project_id,
                           study_type="quantitative", design_family=family,
                           sampling_strategy="convenience", sample_size=sample_size,
                           population_ar="مجتمع الدراسة"))


# ═════════════════ أ · العقدُ المنشور يُعلن ما تحتاجه الشاشة (§55، §56) ═════════════════


def test_the_openapi_document_declares_every_field_the_screen_reads():
    """**وما لا يظهر في العقد المنشور لا يعرفه من يبني عليه.**"""
    from athera_api.main import app

    schema = app.openapi()["components"]["schemas"]["ProjectJourneyView"]
    properties = set(schema["properties"])
    required = {"project_id", "context_fingerprint", "recommended", "actions",
                "capabilities", "limitations", "note"}
    assert required <= properties, f"حقولٌ غائبةٌ عن العقد: {sorted(required - properties)}"


def test_the_route_is_mounted_and_is_not_the_thesis_journey():
    """**ورحلةُ المشروع غيرُ رحلة الرسالة** — مساران لا واحد (§75)."""
    from athera_api.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/v1/workspace/projects/{project_id}/journey" in paths
    # ولا يُمسّ مسارُ الرسالة المؤجَّل.
    assert "/api/v1/theses/{thesis_id}/journey" in paths


def test_the_response_model_does_not_silently_swallow_a_field():
    """**العطبُ الذي بلغ الإنتاج، مفحوصًا عند حدّه.**"""
    from athera_api.schemas.research_brain import ProjectJourneyView

    assert ProjectJourneyView.model_config.get("extra", "ignore") == "ignore"
    for field in ("context_fingerprint", "capabilities", "actions"):
        assert field in ProjectJourneyView.model_fields


# ═════════════════ ب · بحثٌ خاوٍ يعمل ولا يخترع (§57، §90) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_an_empty_project_answers_without_inventing_a_research_question(two_tenants):
    """**لا ٥٠٠، ولا سؤالُ بحثٍ مخترَع، وخطوةٌ تالية مشروعة.**"""
    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])

    async with _client(a) as http:
        response = await http.get(JOURNEY.format(pid=project_id))

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["recommended"]["action_key"] == "define_research_question"
    assert len(body["context_fingerprint"]) == 64
    # **ولا نسبةَ إنجاز** ولا ادّعاءَ معرفةٍ غير موجودة.
    assert "%" not in response.text and "٪" not in response.text
    assert body["known_count"] == 0

    # وبوّابةُ التحليل مغلقةٌ بسببها المسمّى.
    gates = {row["key"]: row for row in body["capabilities"]}
    assert gates["run_analysis"]["allowed"] is False
    assert gates["run_analysis"]["blocking_reasons"] == ["dataset_missing"]


@requires_db
@pytest.mark.asyncio
async def test_the_empty_project_records_exactly_one_snapshot_row_when_reread(two_tenants):
    """**وفتحُ الصفحة مرّتين ليس تغيّرين في البحث.**

    ولولا هذا لَصار الجدولُ سجلَّ زياراتٍ لا تاريخَ بحث — ولَبدا كلُّ
    فتحٍ للشاشة حدثًا يُبطل ما قبله.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research_brain import ResearchContextSnapshot

    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])

    async with _client(a) as http:
        first = await http.get(JOURNEY.format(pid=project_id))
        second = await http.get(JOURNEY.format(pid=project_id))

    assert first.json()["context_fingerprint"] == second.json()["context_fingerprint"]

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        rows = (await session.execute(
            select(func.count(ResearchContextSnapshot.id)).where(
                ResearchContextSnapshot.project_id == project_id))).scalar_one()
    assert rows == 1, "قراءةٌ ثانيةٌ بلا تغييرٍ أنتجت صفًّا ثانيًا"


# ═════════════════ ج · بحثٌ ينمو فتتغيّر الخطوة (§91) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_next_step_changes_as_the_project_develops(two_tenants):
    """السؤالُ يُضاف فتتغيّر الخطوة، والمنهجُ يُضاف فتتغيّر ثانيةً."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _bare_project(tid, uid)
    path = JOURNEY.format(pid=project_id)

    async with _client(a) as http:
        empty = (await http.get(path)).json()
        await _add_question(tid, uid, project_id)
        with_question = (await http.get(path)).json()
        await _add_method(tid, uid, project_id)
        with_method = (await http.get(path)).json()
        await _add_method(tid, uid, project_id, sample_size=120)
        with_sample = (await http.get(path)).json()

    assert empty["recommended"]["action_key"] == "define_research_question"
    assert with_question["recommended"]["action_key"] == "select_method"
    # منهجٌ بلا حجمِ عيّنة — فالخطوةُ التالية أن يُسجَّل الحجم.
    assert with_method["recommended"]["action_key"] == "define_sample"
    # ثمّ سُجِّل، فانتقلت الرحلةُ إلى ما بعده.
    assert with_sample["recommended"]["action_key"] == "link_sources"

    # **وكلُّ خطوةٍ تحمل سببَها** — لا «الذكاء الاصطناعي يقترح».
    for body in (empty, with_question, with_method, with_sample):
        assert body["recommended"]["reason"].strip()


@requires_db
@pytest.mark.asyncio
async def test_a_material_change_produces_a_new_fingerprint(two_tenants):
    """**§92 — تغيّرٌ ذو معنى يُنتج بصمةً أخرى.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _bare_project(tid, uid)
    path = JOURNEY.format(pid=project_id)

    async with _client(a) as http:
        before = (await http.get(path)).json()["context_fingerprint"]
        await _add_question(tid, uid, project_id)
        after = (await http.get(path)).json()["context_fingerprint"]

    assert before != after, "تغيّر البحثُ ولم تتغيّر البصمة"


# ═════════════════ د · والقولُ القديم يَبْلى (§41، §92) ═════════════════


# ═════════════════ هـ · العزل والإذن (§36، §37، §89) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_another_tenant_cannot_read_this_journey(two_tenants):
    """**بحثُ غيرك يُجاب بجوابٍ لا يفرّقه عن المعدوم** — لا 403 يُثبت وجوده."""
    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])
    path = JOURNEY.format(pid=project_id)

    async with _client(a) as http:
        mine = await http.get(path)
    async with _client(b) as http:
        theirs = await http.get(path)

    assert mine.status_code == 200
    assert theirs.status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_the_journey_refuses_the_anonymous_and_the_malformed(two_tenants):
    import httpx

    from athera_api.main import app

    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as http:
        anonymous = await http.get(JOURNEY.format(pid=project_id))
    async with _client(a) as http:
        malformed = await http.get(JOURNEY.format(pid="not-a-uuid"))
        absent = await http.get(JOURNEY.format(pid=uuid.uuid4()))

    assert anonymous.status_code == 401
    assert malformed.status_code == 422
    assert absent.status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_two_projects_of_one_tenant_never_share_a_fingerprint(two_tenants):
    """**ولا يستعير بحثٌ من بحث** — وRLS لا تحرس هذا: المالكُ واحد."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    first = await _bare_project(tid, uid, title="البحث الأول")
    second = await _bare_project(tid, uid, title="البحث الثاني")

    async with _client(a) as http:
        one = (await http.get(JOURNEY.format(pid=first))).json()
        two = (await http.get(JOURNEY.format(pid=second))).json()

    assert one["context_fingerprint"] != two["context_fingerprint"]
    assert one["project_id"] != two["project_id"]


@requires_db
@pytest.mark.asyncio
async def test_the_snapshot_row_is_stamped_with_the_reading_tenant(two_tenants):
    """**وكلُّ صفٍّ يحمل مستأجرَه** — شرطُ أن تعمل سياسةُ العزل أصلًا."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research_brain import ResearchContextSnapshot

    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])
    async with _client(a) as http:
        await http.get(JOURNEY.format(pid=project_id))

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = (await session.execute(
            select(ResearchContextSnapshot).where(
                ResearchContextSnapshot.project_id == project_id))).scalar_one()

    assert row.tenant_id == a["tenant_id"]
    assert row.fingerprint_schema.startswith("pubriva.")
    assert row.first_seen_at is not None and row.last_seen_at is not None


# ═════════════════ و · الترجمة تصل، ولا يُعرض اسمُ خدمة ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_journey_speaks_the_readers_language(two_tenants):
    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])
    path = JOURNEY.format(pid=project_id)

    async with _client(a, locale="ar") as http:
        arabic = (await http.get(path)).json()
    async with _client(a, locale="en") as http:
        english = (await http.get(path)).json()

    assert arabic["recommended"]["title"] != english["recommended"]["title"]
    assert english["recommended"]["title"] == "Define the research question"
    # **ولا اسمَ وحدةٍ ولا دالّةٍ في وجه الباحث** (§25).
    for blob in (arabic["recommended"]["reason"], english["recommended"]["reason"]):
        for leak in ("research_assessment", "orchestrator", "JourneyFacts", "def "):
            assert leak not in blob


# ═════════════════ ز · التعارضُ يُعرض ولا يُحسم (§58، §93) ═════════════════


async def _project_with_unresolved_conflict(tenant_id, user_id):
    """بحثٌ فيه دليلٌ **مناقضٌ غير معالَج** — كما يسجّله §14.4 فعلًا.

    ولا يُستنبط التعارضُ من نصّ: مصدرُه عمودٌ مسجَّل —
    `claim_evidence_links.support_level = 'contradictory'` بلا ملاحظة معالجة.
    """
    from athera_api.db import tenant_session
    from athera_api.models.literature import (
        Claim,
        ClaimEvidenceLink,
        EvidenceExcerpt,
        Source,
    )
    from athera_api.models.portfolio import ProjectSource

    project_id = await _bare_project(tenant_id, user_id, title="بحثٌ فيه تعارض")
    async with tenant_session(tenant_id, user_id) as session:
        source = Source(tenant_id=tenant_id, title="دراسةٌ تقول خلافَ ذلك",
                        publication_year=2022, retraction_status="unknown")
        claim = Claim(tenant_id=tenant_id, project_id=project_id,
                      text_ar="التدريبُ يرفع الأداء.", claim_type="empirical",
                      status="draft")
        session.add_all([source, claim])
        await session.flush()

        excerpt = EvidenceExcerpt(
            tenant_id=tenant_id, source_id=source.id,
            quote="لم يُلحَظ أثرٌ دالٌّ للتدريب على الأداء.",
            locator="ص12", access_basis="open_access_full_text",
            created_by=user_id)
        session.add_all([
            excerpt,
            # **و«مُدرَج» قرارٌ له صاحبٌ ووقت** — والقيدُ في القاعدة يفرضه،
            # فلا يصير مصدرٌ دليلًا في بحثٍ بلا أن يقرّره أحد.
            ProjectSource(tenant_id=tenant_id, project_id=project_id,
                          source_id=source.id, use_state="included",
                          added_by=user_id, decided_by=user_id,
                          decided_at=dt.datetime.now(dt.UTC)),
        ])
        await session.flush()
        session.add(ClaimEvidenceLink(
            tenant_id=tenant_id, claim_id=claim.id, excerpt_id=excerpt.id,
            source_id=source.id, support_level="contradictory",
            reviewed_by=user_id,
            # **ولا ملاحظةَ معالجة** — وهذا بالضبط ما يجعله تعارضًا قائمًا.
            resolution_note_ar=None))
    return project_id


@requires_db
@pytest.mark.asyncio
async def test_a_conflicted_project_reports_the_conflict_and_does_not_settle_it(two_tenants):
    """**التعارضُ يُعلَن ويُقدَّم، ولا يُختار طرفٌ ولا يُسقط دليل.**"""
    a = two_tenants["a"]
    project_id = await _project_with_unresolved_conflict(a["tenant_id"], a["user_id"])

    async with _client(a) as http:
        response = await http.get(JOURNEY.format(pid=project_id))

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["conflict_count"] >= 1, "تعارضٌ مسجَّل لم يصل الجواب"
    assert body["recommended"]["action_key"] == "resolve_contradiction"
    # **ويُقدَّم على غيره** — فلا يُبنى على أدلةٍ متنازَعٍ فيها.
    assert body["actions"][0]["action_key"] == "resolve_contradiction"
    # **ولا ترجيحَ في النصّ.**
    for verdict in ("احذف", "استبعد", "الأرجح", "تجاهل"):
        assert verdict not in body["recommended"]["reason"]


@requires_db
@pytest.mark.asyncio
async def test_the_conflict_is_part_of_the_fingerprint(two_tenants):
    """**وظهورُ التعارضِ تغيّرٌ في حال البحث** — لا تفصيلَ معروضًا فقط."""
    a = two_tenants["a"]
    plain = await _bare_project(a["tenant_id"], a["user_id"], title="بلا تعارض")
    conflicted = await _project_with_unresolved_conflict(a["tenant_id"], a["user_id"])

    async with _client(a) as http:
        first = (await http.get(JOURNEY.format(pid=plain))).json()
        second = (await http.get(JOURNEY.format(pid=conflicted))).json()

    assert first["conflict_count"] == 0
    assert second["conflict_count"] >= 1
    assert first["context_fingerprint"] != second["context_fingerprint"]


# ═════════════════ ح · العزل في القاعدة نفسها (§36، §88) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_row_level_security_hides_another_tenants_brain_rows(two_tenants):
    """**العزلُ يُفحص في القاعدة لا في الخدمة.**

    فخدمةٌ تُقيّد استعلاماتِها صحيحةٌ اليوم وقد يُكتب غدًا استعلامٌ ينسى
    الشرط. وسياسةُ الصفوف تحرس ما ينساه الكاتب — فتُقاس هنا بجلسةِ
    المستأجر الآخر بعينها.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research_brain import ResearchContextSnapshot

    a, b = two_tenants["a"], two_tenants["b"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])
    async with _client(a) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 200

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        mine = (await session.execute(
            select(func.count(ResearchContextSnapshot.id)))).scalar_one()

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        theirs = (await session.execute(
            select(func.count(ResearchContextSnapshot.id))
            .where(ResearchContextSnapshot.project_id == project_id))).scalar_one()

    assert mine >= 1
    assert theirs == 0, "لقطةُ مستأجرٍ ظهرت لمستأجرٍ آخر"

# ══════════ ط · لا توصيةَ تعيش لتَبْلى — والحُجّةُ التي أسقطت الجدول ══════════
#
# كان هنا جدولُ توصياتٍ ووسمُ تقادم. وأُسقطا في مراجعةٍ معمارية لأنّ
# التوصيةَ **تُحسب من الحال الراهنة في كلّ طلب**، فلا تعيش لتَبْلى أصلًا.
#
# والحجّةُ لا تُترك قولًا في رسالة الالتزام: تُفحص هنا. فإن كُتب يومًا
# مسارٌ يعرض توصيةً محفوظة، سقطت هذه الفحوصُ وعاد السؤالُ إلى طاولته.


def test_the_journey_rules_cannot_reach_a_database_at_all():
    """**حتميّةٌ بنيويّة تُقرأ من الشجر النحويّ لا من النيّة.**

    ودالّةٌ خالصة لا تقرأ قاعدةً تُعطي الجوابَ نفسه للحال نفسها، فحفظُ
    جوابها نسخةٌ ثانية من شيءٍ يُشتقّ. وهذا هو الأساسُ الذي بُني عليه
    إسقاطُ الجدول — فيُحرس.
    """
    import ast
    import pathlib

    source = pathlib.Path(
        "athera_api/research_brain/journey.py").read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    for module in imported:
        for banned in ("sqlalchemy", "models", "services", "db"):
            assert banned not in module, (
                f"قواعدُ الرحلة استوردت `{module}` — ولم تعد دالّةً خالصة، "
                "فيسقط ما بُني عليه إسقاطُ جدول التوصيات")


@requires_db
@pytest.mark.asyncio
async def test_what_the_screen_shows_is_always_computed_from_the_current_state(two_tenants):
    """**ما يُعرض محسوبٌ من الراهن دائمًا — لا مقروءٌ من صفٍّ محفوظ.**

    ويُقاس بأدقّ ما يمكن: تُقارَن بصمةُ الجواب ببصمةٍ تُحسب **الآن** من
    حال البحث. فلو جاء الجوابُ من صفٍّ محفوظ لَانفصلت الاثنتان عند أوّل
    تغيير — وهو بعينه «قولٌ قديم يُعرض جاريًا».
    """
    from athera_api.db import tenant_session
    from athera_api.services.research_assessment import build_project_assessment
    from athera_api.services.research_assessment.orchestrator import fingerprint_of

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _bare_project(tid, uid)
    path = JOURNEY.format(pid=project_id)

    async def live_fingerprint() -> str:
        async with tenant_session(tid, uid) as session:
            snap = await build_project_assessment(
                session, tenant_id=tid, project_id=project_id)
            return fingerprint_of(snap)

    async with _client(a) as http:
        before = (await http.get(path)).json()
        assert before["context_fingerprint"] == await live_fingerprint()

        await _add_question(tid, uid, project_id)

        after = (await http.get(path)).json()
        assert after["context_fingerprint"] == await live_fingerprint(), (
            "البصمةُ المعروضة لا تطابق حالَ البحث الآن — أي أنّ شيئًا حُفظ ثمّ عُرض")

    # **والخطوةُ تبدّلت مع الحال** — ولا أثرَ للقديمة في الجواب.
    assert before["recommended"]["action_key"] != after["recommended"]["action_key"]
    assert "define_research_question" not in [
        row["action_key"] for row in after["actions"]]


@requires_db
@pytest.mark.asyncio
async def test_only_the_snapshot_table_is_written_by_a_journey_read(two_tenants):
    """**والمكتوبُ صفٌّ واحد: بصمةٌ رُصدت.**

    ولا جدولَ ثانيًا للعقل في القاعدة — فحصٌ يمنع عودةَ ما أُسقط بلا
    مراجعةٍ جديدة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    a = two_tenants["a"]
    project_id = await _bare_project(a["tenant_id"], a["user_id"])
    async with _client(a) as http:
        assert (await http.get(JOURNEY.format(pid=project_id))).status_code == 200

    async with system_session() as session:
        tables = set((await session.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "AND tablename LIKE 'research\\_%'"))).scalars())

    assert "research_context_snapshots" in tables
    assert "research_recommendations" not in tables, (
        "عاد جدولُ التوصيات — والحجّةُ التي أسقطته لم تتغيّر")


@requires_db
@pytest.mark.asyncio
async def test_the_snapshot_history_is_what_makes_change_detectable(two_tenants):
    """**وتاريخُ البصمات هو القدرةُ التي حُفظ الجدولُ من أجلها.**

    لقطتان لحالين، وأوقاتُ أولِ رؤيةٍ لكلٍّ منهما — وبها يُعرف **متى**
    تغيّر البحث. وهذا ما لا يُستعاد بإعادة الحساب، فيُحفظ.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research_brain import ResearchContextSnapshot

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project_id = await _bare_project(tid, uid)
    path = JOURNEY.format(pid=project_id)

    async with _client(a) as http:
        first = (await http.get(path)).json()["context_fingerprint"]
        await _add_question(tid, uid, project_id)
        second = (await http.get(path)).json()["context_fingerprint"]

    async with tenant_session(tid, uid) as session:
        rows = (await session.execute(
            select(ResearchContextSnapshot)
            .where(ResearchContextSnapshot.project_id == project_id)
            .order_by(ResearchContextSnapshot.first_seen_at))).scalars().all()

    assert [row.context_fingerprint for row in rows] == [first, second], (
        "تاريخُ الحالين لم يُحفظ — وهو وحده ما يقول متى تغيّر البحث")
    assert rows[0].first_seen_at <= rows[1].first_seen_at
