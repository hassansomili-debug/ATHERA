"""الرحلةُ على بحثٍ حقيقيّ | The unified journey, end to end (RC-0 §89–§101).

**ما يُثبَت هنا لا يُثبَت بغير قاعدةٍ حيّة:** أنّ المراحلَ التسع تُقرأ من
الجداول صاحبةِ الحقيقة، وأنّ الاكتمالَ يتبع حالَ المجال لا وجودَ الصفّ،
وأنّ بحثًا لمستأجرٍ لا يُرى من عند غيره.

وكلُّ تجهيزةٍ هنا تكتب **صفوفًا حقيقية** في الجداول الأصلية — لا تُلفّق
`literature_complete=true` ولا تُرقِّع خدمة. فما يُقاس هو ما سيقع للباحث.
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


async def _project(tid, uid, *, title="بحثٌ في أوّله"):
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid, uid) as session:
        row = ResearchProject(tenant_id=tid, working_title_ar=title,
                              status="planned", current_gate="G1")
        session.add(row)
        await session.flush()
        return row.id


async def _question(tid, uid, pid, label="ما أثر التدريب على الأداء؟"):
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import ThreadElement

    async with tenant_session(tid, uid) as session:
        session.add(ThreadElement(tenant_id=tid, project_id=pid,
                                  element_type="question", label_ar=label, ordinal=1))


async def _method(tid, uid, pid, *, study_type="quantitative"):
    from athera_api.db import tenant_session
    from athera_api.models.golden_thread import Method

    async with tenant_session(tid, uid) as session:
        session.add(Method(tenant_id=tid, project_id=pid, study_type=study_type,
                           design_family="correlational",
                           sampling_strategy="convenience", sample_size=120,
                           population_ar="مجتمع الدراسة"))


async def _source(tid, uid, pid, *, included: bool, title="دراسةٌ سابقة"):
    """مصدرٌ حقيقيّ مربوطٌ بالبحث — و«مُدرَج» قرارٌ له صاحبٌ ووقت."""
    from athera_api.db import tenant_session
    from athera_api.models.literature import Source
    from athera_api.models.portfolio import ProjectSource

    async with tenant_session(tid, uid) as session:
        src = Source(tenant_id=tid, title=title, publication_year=2023,
                     retraction_status="unknown")
        session.add(src)
        await session.flush()
        session.add(ProjectSource(
            tenant_id=tid, project_id=pid, source_id=src.id, added_by=uid,
            use_state="included" if included else "saved_only",
            decided_by=uid if included else None,
            decided_at=dt.datetime.now(dt.UTC) if included else None))
        await session.flush()
        return src.id


async def _matrix_cell(tid, uid, pid, source_id, *, field_key="findings"):
    """خليّةُ مصفوفةٍ بلغت `known` — أي **قُرئت** لا فُتحت."""
    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    async with tenant_session(tid, uid) as session:
        session.add(LiteratureMatrixCell(
            tenant_id=tid, project_id=pid, source_id=source_id,
            field_key=field_key, value_ar="نتيجةٌ مستخرَجة", cell_state="known",
            source_scope="full_text", extraction_method="researcher",
            # **وكلُّ خليّةٍ لها كاتبٌ مسجَّل** — والقيدُ في القاعدة يفرضه.
            updated_by=uid))


async def _manuscript(tid, uid, pid, *, with_text: bool, approved: bool = False):
    from athera_api.db import tenant_session
    from athera_api.models.publishing import (
        Manuscript,
        ManuscriptSection,
        ManuscriptVersion,
    )

    async with tenant_session(tid, uid) as session:
        ms = Manuscript(tenant_id=tid, project_id=pid,
                        title_ar="ورقةٌ من هذا البحث", status="draft",
                        language="ar")
        session.add(ms)
        await session.flush()
        version = ManuscriptVersion(tenant_id=tid, manuscript_id=ms.id,
                                    version_label="v1", created_by=uid,
                                    # **وكلُّ نسخةٍ تقول لمَ أُنشئت** — قيدٌ في القاعدة.
                                    change_reason_ar="النسخةُ الأولى")
        session.add(version)
        await session.flush()
        if with_text:
            session.add(ManuscriptSection(
                tenant_id=tid, version_id=version.id, section_key="introduction",
                text_ar="نصُّ المقدّمة المكتوب.", ordinal=1,
                review_status="approved" if approved else "draft",
                # **والاعتمادُ له صاحبٌ ووقت** — قيدٌ في القاعدة، لا تزيين.
                reviewed_by=uid if approved else None,
                reviewed_at=dt.datetime.now(dt.UTC) if approved else None))
            await session.flush()




def _gap(tid, pid, gap_type: str, text: str):
    """فجوةٌ بحثية بحقولها الإلزامية — **وكلُّها تقول من أين جاءت**.

    والقيدُ في القاعدة يفرض «كم مصدرًا نُظر فيه» و«ما حدودُ ما نعرف»: فجوةٌ
    بلا هذين دعوى بلا سند.
    """
    from athera_api.models.synthesis import GapCandidate

    return GapCandidate(
        tenant_id=tid, project_id=pid, gap_type=gap_type,
        description_ar=text, why_suggested_ar="لم تتناولها الدراساتُ المقروءة.",
        # **ومدى البحث يسمّي فهارسَه** — وإلا فالدعوى بلا حدّ (قيدٌ في القاعدة).
        sources_considered=2,
        search_scope={"indexes_searched": ["project_sources"]},
        source_scope_distribution={"full_text": 2},
        known_limitations_ar="قراءةٌ محدودةٌ بعددِ ما أُدرج.",
        strength="emerging_pattern", generation_method="deterministic",
        # **ووقتُ التوليد إلزاميّ**: كشفٌ بلا وقتٍ لا يُعرف أقديمٌ هو أم جديد.
        generated_at=dt.datetime.now(dt.UTC), status="generated")


# ═════════════════ أ · بحثٌ خاوٍ (§89) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_an_empty_project_opens_at_the_idea_with_no_percentage(two_tenants):
    """**٢٠٠، ومرحلةٌ حاليّة، وخطوةٌ مفهومة — ولا سؤالَ مخترَع.**"""
    a = two_tenants["a"]
    pid = await _project(a["tenant_id"], a["user_id"])

    async with _client(a) as http:
        response = await http.get(JOURNEY.format(pid=pid))

    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["stages"]) == 9
    assert body["current_stage"] == "idea"
    assert [row["is_current"] for row in body["stages"]].count(True) == 1
    # **ولا نسبةَ إنجاز بأيّ صيغة** (§23).
    for shape in ("%", "٪", "percent"):
        assert shape not in response.text
    # ولا شيءٌ يُدَّعى معروفًا.
    assert all(not row["known"] for row in body["known"])
    assert body["recommended"] is not None


@requires_db
@pytest.mark.asyncio
async def test_the_empty_project_names_what_is_missing_by_grade(two_tenants):
    """**§49 — ثلاثُ رتبٍ لا قائمةٌ حمراء واحدة.**"""
    a = two_tenants["a"]
    pid = await _project(a["tenant_id"], a["user_id"])
    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    grades = {row["key"]: row["severity"] for row in body["missing"]}
    assert grades["literature"] == "blocking"
    assert grades["instrument"] == "optional"
    assert grades["references"] == "recommended"


# ═════════════════ ب · الرحلةُ تتقدّم بتقدّم البحث (§90، §91) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_journey_advances_with_real_project_changes(two_tenants):
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    path = JOURNEY.format(pid=pid)

    async with _client(a) as http:
        empty = (await http.get(path)).json()
        await _question(tid, uid, pid)
        with_idea = (await http.get(path)).json()
        src = await _source(tid, uid, pid, included=True)
        with_source = (await http.get(path)).json()
        await _matrix_cell(tid, uid, pid, src)
        with_reading = (await http.get(path)).json()

    assert empty["current_stage"] == "idea"
    assert with_idea["current_stage"] == "references"
    assert with_source["current_stage"] == "literature"
    assert with_reading["current_stage"] == "synthesis"

    # **والبصمةُ تتغيّر مع الحال** (§90).
    prints = {b["context_fingerprint"] for b in
              (empty, with_idea, with_source, with_reading)}
    assert len(prints) == 4


@requires_db
@pytest.mark.asyncio
async def test_linked_sources_never_complete_the_literature_stage(two_tenants):
    """**§27، §91 — مصدرٌ مربوطٌ ليس دراسةً مقروءة.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _source(tid, uid, pid, included=True)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["references"]["status"] == "completed"
    assert stages["literature"]["status"] != "completed"


@requires_db
@pytest.mark.asyncio
async def test_a_saved_source_is_not_an_included_source(two_tenants):
    """**والإدراجُ قرارٌ** — لا تخزين."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _source(tid, uid, pid, included=False)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["references"]["status"] == "needs_action"


# ═════════════════ ج · الورقةُ والمنهج (§98، §100) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_a_manuscript_shell_is_not_a_written_paper(two_tenants):
    """**§98 — وجودُ المخطوطة ليس كتابةً لها.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    bare = await _project(tid, uid, title="مخطوطةٌ بلا نصّ")
    await _manuscript(tid, uid, bare, with_text=False)
    written = await _project(tid, uid, title="مخطوطةٌ مكتوبة")
    await _manuscript(tid, uid, written, with_text=True, approved=True)

    async with _client(a) as http:
        shell = (await http.get(JOURNEY.format(pid=bare))).json()
        full = (await http.get(JOURNEY.format(pid=written))).json()

    def paper(body):
        return next(r for r in body["stages"] if r["key"] == "paper")

    assert paper(shell)["status"] == "needs_action"
    assert paper(full)["status"] == "completed"


@requires_db
@pytest.mark.asyncio
async def test_an_unrecorded_method_stays_unknown(two_tenants):
    """**§100، §51 — ولا يُستنبط المنهجُ من شيء.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    method = next(row for row in body["known"] if row["key"] == "method")
    assert method["known"] is False and method["value"] == ""


@requires_db
@pytest.mark.asyncio
async def test_a_qualitative_project_is_not_blocked_on_instrument_or_data(two_tenants):
    """**§32، §34 — ولا حاجزَ كمّيٌّ كونيّ.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _method(tid, uid, pid, study_type="qualitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["instrument"]["status"] == "optional"
    assert stages["data"]["status"] == "optional"
    assert stages["design"]["status"] == "completed"


@requires_db
@pytest.mark.asyncio
async def test_a_quantitative_project_expects_instrument_and_data(two_tenants):
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _method(tid, uid, pid, study_type="quantitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["instrument"]["status"] != "optional"
    assert stages["data"]["status"] != "optional"


# ═════════════════ د · حتميّة، وعزل، وإذن (§87، §88، §101) ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_same_state_always_renders_the_same_journey(two_tenants):
    """**§101 — ولا ترتيبَ عشوائيّ.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    seen = set()
    async with _client(a) as http:
        for _ in range(5):
            body = (await http.get(JOURNEY.format(pid=pid))).json()
            seen.add((
                body["current_stage"],
                tuple((r["key"], r["status"], r["is_current"]) for r in body["stages"]),
                body["context_fingerprint"],
                body["recommended"]["action_key"] if body["recommended"] else None,
            ))
    assert len(seen) == 1


@requires_db
@pytest.mark.asyncio
async def test_another_tenant_never_sees_this_journey(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    pid = await _project(a["tenant_id"], a["user_id"])
    await _question(a["tenant_id"], a["user_id"], pid)

    async with _client(a) as http:
        mine = await http.get(JOURNEY.format(pid=pid))
    async with _client(b) as http:
        theirs = await http.get(JOURNEY.format(pid=pid))

    assert mine.status_code == 200
    assert theirs.status_code == 404, "بحثُ غيرك يُجاب بجوابٍ لا يفرّقه عن المعدوم"


@requires_db
@pytest.mark.asyncio
async def test_the_journey_refuses_the_anonymous_and_the_absent(two_tenants):
    import httpx

    from athera_api.main import app

    a = two_tenants["a"]
    pid = await _project(a["tenant_id"], a["user_id"])

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://test") as http:
        anonymous = await http.get(JOURNEY.format(pid=pid))
    async with _client(a) as http:
        malformed = await http.get(JOURNEY.format(pid="not-a-uuid"))
        absent = await http.get(JOURNEY.format(pid=uuid.uuid4()))

    assert anonymous.status_code == 401
    assert malformed.status_code == 422
    assert absent.status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_one_project_never_reads_another_projects_stages(two_tenants):
    """**ولا يستعير بحثٌ من بحث** — وRLS لا تحرس هذا: المالكُ واحد."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    rich = await _project(tid, uid, title="بحثٌ متقدّم")
    await _question(tid, uid, rich)
    await _source(tid, uid, rich, included=True)
    bare = await _project(tid, uid, title="بحثٌ خاوٍ")

    async with _client(a) as http:
        one = (await http.get(JOURNEY.format(pid=rich))).json()
        two = (await http.get(JOURNEY.format(pid=bare))).json()

    assert one["current_stage"] == "literature"
    assert two["current_stage"] == "idea"
    assert one["context_fingerprint"] != two["context_fingerprint"]


# ═════════════════ هـ · العقدُ المنشور واللغة (§126، §55) ═════════════════


def test_the_openapi_declares_the_stage_contract():
    from athera_api.main import app

    schemas = app.openapi()["components"]["schemas"]
    journey = set(schemas["ProjectJourneyView"]["properties"])
    assert {"stages", "current_stage", "known", "missing"} <= journey

    stage = set(schemas["StageView"]["properties"])
    assert {"key", "status", "is_current", "title", "reason", "summary", "route",
            "blocking_reasons"} <= stage


@requires_db
@pytest.mark.asyncio
async def test_the_journey_speaks_both_languages_completely(two_tenants):
    """**§55 — ولا تطبيقَ عربيٌّ وحده.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    path = JOURNEY.format(pid=pid)

    async with _client(a, locale="ar") as http:
        arabic = (await http.get(path)).json()
    async with _client(a, locale="en") as http:
        english = (await http.get(path)).json()

    for ar, en in zip(arabic["stages"], english["stages"], strict=True):
        assert ar["key"] == en["key"]
        assert ar["title"] and en["title"] and ar["title"] != en["title"]
        assert ar["reason"] and en["reason"]
    assert english["stages"][0]["title"] == "Idea"

# ══════════ ي · رحلةٌ موحَّدة لا تخالف نفسَها ══════════
#
# **العطبُ الذي تحرسه هذه الحزمة، ويراه الباحثُ بعينه:**
#
#     المرحلة الحالية : المراجع
#     والزرُّ يقول    : حدِّد المنهج
#
# وسببُه أنّ للقرار كان محرّكان: المراحلُ تقول أين هو، وسجلُّ قواعدَ آخر
# يرتّب «التالي» بأولوياتٍ مستقلّة. ومحرّكان لا يُصلَحان بموازنةٍ بينهما،
# بل بأن يبقى واحد — فصار الفعلُ الرئيس **نداءَ المرحلة الحاليّة** بالبناء.


def _primary(body) -> str:
    """مفتاحُ الفعل الرئيس — وهو مفتاحُ المرحلة نفسِه بعد التوحيد."""
    return body["recommended"]["action_key"]


@requires_db
@pytest.mark.asyncio
async def test_question_without_sources_points_at_references_not_the_method(two_tenants):
    """**أ · الحالةُ المسمّاة في المراجعة بعينها.**

    سؤالٌ موجود، ولا مصادر ⇒ المرحلة «المراجع»، والفعلُ «المراجع».
    **ولا `select_method`** — وهو ما كان يقوله الزرُّ قبل التوحيد.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    assert body["current_stage"] == "references"
    assert _primary(body) == "references"
    assert _primary(body) != "select_method"
    # وعنوانُ الفعل نداءٌ لا اسمُ مرحلة.
    assert body["recommended"]["title"] == "أضف مراجع للبحث"


@requires_db
@pytest.mark.asyncio
async def test_included_sources_without_literature_point_at_literature(two_tenants):
    """**ب · مصادرُ مُدرَجةٌ ولا قراءة ⇒ الدراساتُ السابقة.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _source(tid, uid, pid, included=True)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    assert body["current_stage"] == "literature"
    assert _primary(body) == "literature"


@requires_db
@pytest.mark.asyncio
async def test_literature_and_gap_without_method_point_at_the_design(two_tenants):
    """**ج · دراساتٌ وفجوةٌ ولا منهج ⇒ تصميمُ البحث.**"""
    from athera_api.db import tenant_session

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    src = await _source(tid, uid, pid, included=True)
    await _matrix_cell(tid, uid, pid, src)
    async with tenant_session(tid, uid) as session:
        session.add(_gap(tid, pid, "population_gap", "فجوةٌ في مجتمع الدراسة."))

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    assert body["current_stage"] == "design"
    assert _primary(body) == "design"


@requires_db
@pytest.mark.asyncio
async def test_the_primary_action_always_matches_the_current_stage(two_tenants):
    """**والتطابقُ بنيويّ لا اتفاقيّ** — يُفحص على كلّ حالٍ تُبنى هنا."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    path = JOURNEY.format(pid=pid)

    async with _client(a) as http:
        seen = [(await http.get(path)).json()]
        await _question(tid, uid, pid)
        seen.append((await http.get(path)).json())
        src = await _source(tid, uid, pid, included=True)
        seen.append((await http.get(path)).json())
        await _matrix_cell(tid, uid, pid, src)
        seen.append((await http.get(path)).json())
        await _method(tid, uid, pid, study_type="quantitative")
        seen.append((await http.get(path)).json())

    for body in seen:
        assert _primary(body) == body["current_stage"], (
            f"الفعلُ {_primary(body)} يخالف المرحلة {body['current_stage']}")
        # **والخطواتُ الأخرى لا تُعيد الحاليّة.**
        assert body["current_stage"] not in [
            row["action_key"] for row in body["actions"]]


# ══════════ ك · المنهجُ الكيفيّ لا يُحجب بأداةٍ كمّية ══════════


@requires_db
@pytest.mark.asyncio
async def test_a_qualitative_project_does_not_skip_analysis_to_reach_the_paper(
        two_tenants):
    """**د · والتناقضُ الذي كان: البياناتُ اختياريّة والتحليلُ متوقّفٌ لغيابها.**

    فكانت الرحلةُ تقفز من تصميم البحث إلى الورقة، كأنّ التحليلَ لا يلزم
    دراسةً كيفية. والعلاجُ صدقٌ عن قدرة المنصّة: التحليلُ **لم يبدأ** — لا
    متوقّفًا بحجّةِ أداةٍ كمّية، ولا مكتملًا، ولا اختياريًّا يُتخطّى.
    """
    from athera_api.db import tenant_session

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid, title="دراسةٌ كيفية")
    await _question(tid, uid, pid)
    src = await _source(tid, uid, pid, included=True)
    await _matrix_cell(tid, uid, pid, src)
    async with tenant_session(tid, uid) as session:
        session.add(_gap(tid, pid, "context_gap", "فجوةٌ سياقية."))
    await _method(tid, uid, pid, study_type="qualitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}

    # ولا أداةَ تُشترط، ولا مجموعةَ بياناتٍ كمّية.
    assert stages["instrument"]["status"] == "optional"
    assert stages["data"]["status"] == "optional"

    # **ولا يُحجب التحليلُ لغياب مجموعة بيانات.**
    assert stages["analysis"]["status"] == "not_started"
    assert stages["analysis"]["blocking_reasons"] == []
    # ولا يُدَّعى تمامُه.
    assert stages["analysis"]["status"] != "completed"
    # **ولا قفزَ إلى الورقة.**
    assert body["current_stage"] == "analysis"
    assert _primary(body) == "analysis"
    # ويُقال بصدقٍ إنّ المنصّةَ لا تُمثّل هذه المادّة بعد.
    assert "لا تُمثِّل المنصّةُ" in stages["analysis"]["reason"]


@requires_db
@pytest.mark.asyncio
async def test_the_quantitative_path_still_requires_data_before_analysis(two_tenants):
    """**هـ · والمسارُ الكمّيّ يبقى كما هو** — لا تحليلَ بلا بيانات."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid, title="دراسةٌ كمّية")
    await _question(tid, uid, pid)
    await _method(tid, uid, pid, study_type="quantitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["instrument"]["status"] == "not_started"
    assert stages["data"]["status"] == "not_started"
    assert stages["analysis"]["status"] == "blocked"
    assert stages["analysis"]["blocking_reasons"] == ["no_data_available"]


@requires_db
@pytest.mark.asyncio
async def test_the_same_state_gives_the_same_stage_and_the_same_primary(two_tenants):
    """**و · حتميّةٌ كاملة** — المرحلةُ والفعلُ معًا."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    seen = set()
    async with _client(a) as http:
        for _ in range(5):
            body = (await http.get(JOURNEY.format(pid=pid))).json()
            seen.add((body["current_stage"], _primary(body),
                      tuple(r["action_key"] for r in body["actions"])))
    assert len(seen) == 1


# ══════════ ل · ولا أثرَ مشغّلٍ مُتتبَّع ══════════


def test_no_generated_runner_artifact_is_tracked():
    """**ز · حالُ مشغّلٍ ليست مصدرًا يُراجَع.**

    وقد تسرّب `apps/api/test-results/.last-run.json` إلى طلبِ دمجٍ يحمل
    `"status": "failed"` من تشغيلٍ محلّيّ عابر — تُقرأ في المراجعة إخفاقًا
    قائمًا في الفرع.
    """
    import subprocess

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True).stdout.strip()
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True,
        check=True).stdout.splitlines()

    leaked = [path for path in tracked if "test-results/" in path]
    assert leaked == [], f"آثارُ مشغّلٍ متتبَّعة: {leaked}"

# ══════════ م · عقدُ الأفعال: وجهةٌ حقيقية، وحالٌ لا تُطوى ══════════


@requires_db
@pytest.mark.asyncio
async def test_the_references_action_points_at_the_sources_not_at_the_journey_page(
        two_tenants):
    """**والفعلُ يبلغ أداةً، لا يعيد الباحثَ إلى مكانه.**

    كان يقصد `/portfolio/{id}` — وهي صفحةُ الرحلة التي يقف عليها أصلًا،
    فينقر «أضف مراجع» فلا يتغيّر شيء. وأدواتُ المصادر في قسم «الدراسات
    السابقة» من الصفحة نفسِها، فيُقصد بعينه.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    assert body["current_stage"] == "references"
    route = body["recommended"]["route"]
    assert route == f"/portfolio/{pid}?section=literature"
    # **ولا يساوي صفحةَ الرحلة نفسَها.**
    assert route != f"/portfolio/{pid}"


@requires_db
@pytest.mark.asyncio
async def test_a_qualitative_analysis_offers_no_route_to_a_tool_that_cannot_run_it(
        two_tenants):
    """**وفرقٌ بين «هذا العملُ باقٍ» و«اضغط هنا لتفعله».**

    وتشغيلةُ التحليل في هذه المنصّة تلزمها نسخةُ مجموعةِ بيانات
    (`analysis_runs.dataset_version_id` غيرُ قابلٍ للإفراغ)، فأداةُ التحليل
    لا تقبل مادّةً كيفية. فلا وجهةَ تُعرض.
    """
    from athera_api.db import tenant_session
    from athera_api.models.synthesis import GapCandidate  # noqa: F401

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid, title="دراسةٌ كيفية")
    await _question(tid, uid, pid)
    src = await _source(tid, uid, pid, included=True)
    await _matrix_cell(tid, uid, pid, src)
    async with tenant_session(tid, uid) as session:
        session.add(_gap(tid, pid, "context_gap", "فجوةٌ سياقية."))
    await _method(tid, uid, pid, study_type="qualitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert body["current_stage"] == "analysis"
    # **ولا وجهةَ في المرحلة ولا في الفعل.**
    assert stages["analysis"]["route"] is None
    assert body["recommended"]["route"] is None
    # ويُقال السببُ بدل الوعد.
    assert "لا أداةَ هنا" in body["recommended"]["reason"]


@requires_db
@pytest.mark.asyncio
async def test_the_quantitative_analysis_keeps_its_real_route(two_tenants):
    """**والمسارُ الكمّيّ يبلغ أداتَه** — فما سقط هو الوعدُ الكاذب وحدَه."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)
    await _method(tid, uid, pid, study_type="quantitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["analysis"]["route"] == "/analysis"
    assert stages["data"]["route"] == "/analysis"


@requires_db
@pytest.mark.asyncio
async def test_an_optional_stage_stays_optional_in_the_actions(two_tenants):
    """**والاختياريُّ لا يُطوى في «موصًى به».**

    كان الفعلُ يُكتب `blocked if blocking else recommended`، فيصير
    «أضف بيانات» في بحثٍ كيفيّ موصًى بها — وهي نافعةٌ لا لازمة. وتغييرُ
    الرتبة تغييرُ معنًى: ما لا يلزم يبدو ناقصًا.
    """
    from athera_api.db import tenant_session

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid, title="دراسةٌ كيفية")
    await _question(tid, uid, pid)
    src = await _source(tid, uid, pid, included=True)
    await _matrix_cell(tid, uid, pid, src)
    async with tenant_session(tid, uid) as session:
        session.add(_gap(tid, pid, "context_gap", "فجوةٌ سياقية."))
    await _method(tid, uid, pid, study_type="qualitative")

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    actions = {row["action_key"]: row for row in body["actions"]}
    stages = {row["key"]: row for row in body["stages"]}

    for key in ("instrument", "data"):
        assert stages[key]["status"] == "optional"
        assert actions[key]["status"] == "optional", (
            f"الاختياريُّ {key} صار «{actions[key]['status']}» في الأفعال")

    # **والمكتملُ ليس فعلًا يُقترح.**
    for key, row in stages.items():
        if row["status"] == "completed":
            assert key not in actions
    # ولا تظهر حالٌ لم تُعلَن في المراحل.
    for row in actions.values():
        assert row["status"] in ("optional", "recommended", "blocked")


@requires_db
@pytest.mark.asyncio
async def test_a_blocked_stage_is_shown_with_its_reason_but_never_offered_as_a_step(
        two_tenants):
    """**والمتوقّفةُ تُعرض ولا تُقترح.**

    فسببُ إغلاقها مرحلةٌ قبلها، ودعوتُها «خطوةً أخرى» دعوةٌ إلى بابٍ مغلق.
    لكنّ حالَها وسببَها وما يلزم لرفعه يصل كلُّه في `stages` — فالمنعُ
    يُسمّى ولا يُخفى (§44).
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    pid = await _project(tid, uid)
    await _question(tid, uid, pid)

    async with _client(a) as http:
        body = (await http.get(JOURNEY.format(pid=pid))).json()

    stages = {row["key"]: row for row in body["stages"]}
    assert stages["literature"]["status"] == "blocked"
    assert stages["literature"]["blocking_reasons"] == ["no_sources_linked"]
    assert stages["literature"]["reason"].strip()

    # **ولا تُعرض فعلًا يُدعى إليه.**
    assert "literature" not in [row["action_key"] for row in body["actions"]]
