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
