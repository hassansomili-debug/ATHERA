"""التعاونُ على البيانات عبر المؤسسات | RC-T1C data collaboration (0036).

**العقدُ الذي تُثبته هذه الحزمة**: باحثٌ في مؤسسةٍ أخرى قُبل في بحثٍ
بدورِ `statistician` وبصلاحيّتَي `view_project` و`manage_data` **يعمل على
بيانات ذلك البحث فعلًا** — يقرأ مجموعاته، ويُنشئ مجموعةً، ويشتقّ نسخةً،
ويجمّدها، ويصف قاموسَها، ويشغّل خطّةً ويسجّل مخرَجًا ويصدّر.

وكان ذلك ممتنعًا بنيويًّا قبل 0036: مساراتُ التحليل لا تحمل معرّفَ البحث
في قوالبها، **ومنها ما لا يعرفه حتى يقرأ الكيان** — والقراءةُ في مستأجر
البيت ترى صفرَ صفوف. فصار `/projects/{id}/access` يقول للإحصائيّ إنّه
يحمل إدارةَ البيانات، ثمّ لا تُفتح له شاشةٌ واحدة.

وثلاثةُ حدودٍ تُقاس هنا، لا تُفترض:

  ١ **الصفُّ يُكتب في مستأجر البحث** — لا في مستأجر من كتبه. وصفٌّ
    يُخزَّن في المستأجر الخطأ لا يراه أحد، وذاك أخفى من ٤٠٤.
  ٢ **الصلاحيةُ صفّان معًا**: الاطّلاعُ أساسًا وإدارةُ البيانات معه.
    ولا دورَ يُقرأ، ولا انتماءٌ تنظيميّ يُنشأ.
  ٣ **ولا تسريبَ أفقيّ**: من يُدير بيانات بحثٍ في مؤسسةٍ لا يرى بحثًا
    آخرَ في المؤسسة نفسِها. وسياسةُ تحديد موضعٍ تكشف مجموعاتِ المستأجر
    كلَّها إخفاقٌ لا نجاحٌ ناقص.
"""
from __future__ import annotations

import contextlib
import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_rc_t1a_project_access import _client, _owned_project, _second_user  # noqa: E402
from tests.test_at_rc_t1c_project_bridge import (  # noqa: E402
    _external_member,
    _member,
    _set_access,
    _set_permissions,
)
from tests.test_at_rc_t1c_recruitment_api import _third_tenant  # noqa: E402

ANALYSIS = "/api/v1/analysis"
TEAM = "/api/v1/projects"
VIEW = "view_project"
DATA = "manage_data"
EDIT = "edit_research_content"
APPROVE = "approve_scientific_candidates"


class World:
    def __init__(self, **kw):
        self.__dict__.update(kw)


async def _dataset(slot, project_id, *, name="بياناتُ التعاون", checksum="a" * 64):
    """مجموعةٌ تُنشأ **بالمسار الحقيقيّ** — فتُسجَّل كما تُسجَّل فعلًا."""
    async with _client(slot) as http:
        return await http.post(f"{ANALYSIS}/datasets", json={
            "project_id": str(project_id), "name_ar": name,
            "classification": "C3", "raw_label": "الرفع الأول",
            "raw_checksum": checksum, "row_count": 50})


async def _plan(slot, project_id, *, label="v1"):
    async with _client(slot) as http:
        return await http.post(f"{ANALYSIS}/plans", json={
            "project_id": str(project_id), "version_label": label,
            "summary_ar": "خطّةٌ للتعاون",
            "tests": [{"test_key": "pearson_r", "test_kind": "correlation",
                       "note_ar": "علاقةٌ مُفترضة"}]})


@pytest.fixture
async def data(two_tenants):
    """بحثٌ في «أ»، وإحصائيٌّ من «ب» بإدارةِ بياناتٍ صريحة، وغرباء."""
    owner = two_tenants["a"]
    guest = two_tenants["b"]
    suffix = uuid.uuid4().hex[:8]
    project_id = await _owned_project(owner, title="بحثُ التعاون على البيانات")
    # **دورُه `statistician`، وصلاحيّاته صفّان صريحان** — ولا مصادرَ ولا فريق.
    member = await _external_member(owner, guest, project_id,
                                    permissions=[VIEW, DATA])
    outsider = await _third_tenant(suffix)
    colleague = await _second_user(owner["tenant_id"], email=f"dc-{suffix}@example.test")
    # وبحثٌ ثانٍ في المؤسسة نفسِها — **لا شأنَ للضيف به**.
    other_project = await _owned_project(owner, title="بحثٌ آخرُ في المؤسسة نفسِها")
    return World(owner=owner, guest=guest, outsider=outsider, colleague=colleague,
                 project_id=project_id, other_project=other_project,
                 member=member, suffix=suffix)


# ═══════════════ ١ · الرحلةُ الذهبية للبيانات ═══════════════


@requires_db
@pytest.mark.asyncio
async def test_01_the_external_statistician_creates_project_data(data):
    """**والصفُّ يُكتب في مستأجر البحث** — لا في مستأجر من كتبه.

    وهذا هو الحدُّ الذي لا يُرى إن لم يُقَس: لو حمل الصفُّ مستأجرَ الضيف
    لَردَّ المسارُ ٢٠١ ولَما رآه صاحبُ البحث أبدًا — نجاحٌ مُعلَنٌ وصفٌّ
    مفقود.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import Dataset, DatasetVersionRow
    from athera_api.models.audit import AuditEvent

    created = await _dataset(data.guest, data.project_id)
    assert created.status_code == 201, created.text
    version_id = uuid.UUID(created.json()["id"])
    dataset_id = uuid.UUID(created.json()["dataset_id"])

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        dataset = (await session.execute(
            select(Dataset).where(Dataset.id == dataset_id))).scalar_one()
        assert dataset.tenant_id == data.owner["tenant_id"], "المجموعةُ في المستأجر الخطأ"
        assert dataset.project_id == data.project_id

        raw = (await session.execute(
            select(DatasetVersionRow).where(
                DatasetVersionRow.id == version_id))).scalar_one()
        assert raw.tenant_id == data.owner["tenant_id"], "النسخةُ الخام في المستأجر الخطأ"
        assert raw.state == "raw"

        # **والسجلُّ في مستأجر البحث، والفاعلُ هو الضيفُ نفسُه.**
        event = (await session.execute(
            select(AuditEvent).where(
                AuditEvent.action == "analysis.dataset_created",
                AuditEvent.object_id == dataset_id))).scalar_one()
        assert event.tenant_id == data.owner["tenant_id"]
        assert event.actor_user_id == data.guest["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_02_the_whole_dataset_lifecycle_crosses_the_bridge(data):
    """السلسلةُ كلُّها: اشتقاقٌ وقاموسٌ وتجميد — **وكلُّ صفٍّ في مستأجر البحث**."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import DataDictionary, DatasetVersionRow

    created = await _dataset(data.guest, data.project_id)
    dataset_id = created.json()["dataset_id"]
    raw_version = created.json()["id"]

    async with _client(data.guest) as http:
        listed = await http.get(f"{ANALYSIS}/datasets/{dataset_id}/versions")
        assert listed.status_code == 200, listed.text
        assert [r["state"] for r in listed.json()] == ["raw"]

        derived = await http.post(f"{ANALYSIS}/datasets/{dataset_id}/versions", json={
            "parent_version_id": raw_version, "state": "cleaned",
            "label": "منقّاة", "checksum": "c" * 64,
            "change_note_ar": "حذف صفوف ناقصة", "row_count": 48})
        assert derived.status_code == 201, derived.text
        version_id = derived.json()["id"]

        wrote = await http.put(
            f"{ANALYSIS}/datasets/versions/{version_id}/dictionary",
            json=[{"column_name": "age", "label_ar": "العمر",
                   "scale_type": "ratio", "is_pii": False}])
        assert wrote.status_code == 200, wrote.text
        assert wrote.json()["described_columns"] == 1

        read = await http.get(f"{ANALYSIS}/datasets/versions/{version_id}/dictionary")
        assert read.status_code == 200, read.text
        assert read.json()["described_columns"] == 1

        frozen = await http.post(f"{ANALYSIS}/datasets/versions/{version_id}/freeze")
        assert frozen.status_code == 200, frozen.text

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        child = (await session.execute(
            select(DatasetVersionRow).where(
                DatasetVersionRow.id == uuid.UUID(version_id)))).scalar_one()
        assert child.tenant_id == data.owner["tenant_id"]
        assert child.frozen_at is not None
        entry = (await session.execute(
            select(DataDictionary).where(
                DataDictionary.dataset_version_id == uuid.UUID(version_id)))).scalar_one()
        assert entry.tenant_id == data.owner["tenant_id"]


@requires_db
@pytest.mark.asyncio
async def test_03_plan_run_output_and_export_all_resolve(data):
    """المفاتيحُ غيرُ المباشرة كلُّها تُحدَّد وتُعبَر: خطّةٌ وتشغيلةٌ ومخرَجٌ وتصدير."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import (
        AnalysisOutputRow,
        AnalysisPlanRow,
        AnalysisRun,
        PlannedTestRow,
        ToolExport,
    )

    created = await _dataset(data.guest, data.project_id)
    dataset_id = created.json()["dataset_id"]
    raw_version = created.json()["id"]

    async with _client(data.guest) as http:
        derived = await http.post(f"{ANALYSIS}/datasets/{dataset_id}/versions", json={
            "parent_version_id": raw_version, "state": "cleaned",
            "label": "منقّاة", "checksum": "d" * 64,
            "change_note_ar": "تنقية", "row_count": 48})
        version_id = derived.json()["id"]
        assert (await http.post(
            f"{ANALYSIS}/datasets/versions/{version_id}/freeze")).status_code == 200

    plan = await _plan(data.guest, data.project_id)
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]

    async with _client(data.guest) as http:
        # والخطّةُ تُقفل بصلاحيةِ الاعتماد لا بإدارة البيانات — فيُقفلها
        # صاحبُ البحث، وذاك حدٌّ محفوظٌ يُقاس في اختبارٍ آخر.
        pass
    async with _client(data.owner) as http:
        approved = await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")
        assert approved.status_code == 200, approved.text

    async with _client(data.guest) as http:
        run = await http.post(f"{ANALYSIS}/runs", json={
            "plan_id": plan_id, "dataset_version_id": version_id,
            "tool": "python", "executed_test_keys": ["pearson_r"],
            "code_hash": "e" * 64, "runtime": "3.12", "random_seed": 7})
        assert run.status_code == 201, run.text
        run_id = run.json()["id"]

        output = await http.post(f"{ANALYSIS}/runs/{run_id}/outputs", json={
            "output_kind": "statistic", "label_ar": "معامل الارتباط",
            "test_key": "pearson_r", "payload": {"r": 0.42}})
        assert output.status_code == 201, output.text

        export = await http.post(f"{ANALYSIS}/exports", json={
            "dataset_version_id": version_id, "run_id": run_id,
            "tool": "spss", "export_format": "csv"})
        assert export.status_code == 201, export.text

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        for model, ident in (
            (AnalysisPlanRow, uuid.UUID(plan_id)),
            (AnalysisRun, uuid.UUID(run_id)),
        ):
            row = (await session.execute(
                select(model).where(model.id == ident))).scalar_one()
            assert row.tenant_id == data.owner["tenant_id"], model.__name__
        for model in (PlannedTestRow, AnalysisOutputRow, ToolExport):
            rows = (await session.execute(select(model))).scalars().all()
            assert rows, model.__name__
            for row in rows:
                assert row.tenant_id == data.owner["tenant_id"], model.__name__


@requires_db
@pytest.mark.asyncio
async def test_04_the_global_lists_show_the_shared_project_and_nothing_else(data):
    """**القوائمُ العامّةُ تعبُر المؤسسات — ولا تعبُر إلى بحثٍ آخر.**

    وهذا أدقُّ فحصٍ في هذه الحزمة: سياسةُ تحديد موضعٍ تكشف مجموعاتِ
    المستأجر كلَّها **تُنجح هذا الاختبار وتُسقط الأمن**. فيُنشأ بحثٌ ثانٍ
    في المؤسسة نفسِها ويُنشأ له مجموعة، ويُشترط ألّا تظهر.
    """
    mine = await _dataset(data.guest, data.project_id, name="مجموعةُ البحث المشترك")
    assert mine.status_code == 201, mine.text
    theirs = await _dataset(data.owner, data.other_project, name="مجموعةُ بحثٍ آخر",
                            checksum="b" * 64)
    assert theirs.status_code == 201, theirs.text

    async with _client(data.guest) as http:
        listed = await http.get(f"{ANALYSIS}/datasets")
    assert listed.status_code == 200, listed.text
    projects = {row["project_id"] for row in listed.json()}
    assert projects == {str(data.project_id)}, projects
    names = {row["name"] for row in listed.json()}
    assert "مجموعةُ بحثٍ آخر" not in names

    async with _client(data.guest) as http:
        plans = await http.get(f"{ANALYSIS}/plans")
        exports = await http.get(f"{ANALYSIS}/exports")
    assert plans.status_code == 200 and exports.status_code == 200


# ═══════════════ ٢ · مصفوفةُ الصلاحيات ═══════════════


@requires_db
@pytest.mark.asyncio
async def test_05_view_project_alone_opens_no_data(data):
    """**الاطّلاعُ ليس إذنًا بالبيانات** — وهو حدُّ 0012 نفسُه، محفوظًا."""
    await _set_permissions(data.owner, data.member, [VIEW])
    created = await _dataset(data.guest, data.project_id)
    assert created.status_code in (403, 404), created.text

    async with _client(data.guest) as http:
        listed = await http.get(f"{ANALYSIS}/datasets")
    assert listed.status_code == 200
    assert listed.json() == [], listed.json()


@requires_db
@pytest.mark.asyncio
async def test_06_manage_data_without_the_baseline_opens_nothing(data):
    """وعضويّةٌ نُزع اطّلاعُها لا تُحدّد موضعًا ولا تعبُر — **الفشلُ مغلق**."""
    await _set_permissions(data.owner, data.member, [DATA])
    created = await _dataset(data.guest, data.project_id)
    assert created.status_code == 404, created.text

    async with _client(data.guest) as http:
        assert (await http.get(f"{ANALYSIS}/datasets")).json() == []


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["suspended", "removed"])
async def test_07_08_a_suspended_or_removed_member_loses_the_data(data, state):
    """موقوفٌ ومُزالٌ ليسا عضوين عاملين — **والبابُ يُقفل في الطلب التالي**."""
    created = await _dataset(data.guest, data.project_id)
    assert created.status_code == 201

    await _set_access(data.owner, data.member, state)
    async with _client(data.guest) as http:
        assert (await http.get(f"{ANALYSIS}/datasets")).json() == []
        blocked = await http.get(
            f"{ANALYSIS}/datasets/{created.json()['dataset_id']}/versions")
    assert blocked.status_code == 404, blocked.text


@requires_db
@pytest.mark.asyncio
async def test_09_revoking_manage_data_denies_immediately_and_regrant_returns(data):
    """**ولا كذبةَ ذاكرة، ولا دورٌ يتغيّر**: صفٌّ واحدٌ يُنزع فيُقفل الباب.

    والدورُ `statistician` قبلَ النزع وبعده وبعد الإعادة — فالدورُ ليس
    صلاحية، ويُقاس ذلك في طبقة البيانات كما يُقاس في المصادر.
    """
    created = await _dataset(data.guest, data.project_id)
    dataset_id = created.json()["dataset_id"]
    assert created.status_code == 201

    async with _client(data.guest) as http:
        assert (await http.get(
            f"{ANALYSIS}/datasets/{dataset_id}/versions")).status_code == 200
        role_before = (await http.get(f"{TEAM}/{data.project_id}/access")).json()["role"]

    await _set_permissions(data.owner, data.member, [VIEW])
    async with _client(data.guest) as http:
        denied = await http.get(f"{ANALYSIS}/datasets/{dataset_id}/versions")
        assert denied.status_code == 404, denied.text
        access = (await http.get(f"{TEAM}/{data.project_id}/access")).json()
        # والبحثُ باقٍ مرئيًّا، والرحلةُ تُفتح — الممنوعُ هو البيانات وحدها.
        assert access["can_manage_data"] is False
        assert access["role"] == role_before
        assert (await http.get(
            f"/api/v1/workspace/projects/{data.project_id}/overview")).status_code == 200

    await _set_permissions(data.owner, data.member, [VIEW, DATA])
    async with _client(data.guest) as http:
        again = await http.get(f"{ANALYSIS}/datasets/{dataset_id}/versions")
        assert again.status_code == 200, again.text
        assert (await http.get(
            f"{TEAM}/{data.project_id}/access")).json()["role"] == role_before


@requires_db
@pytest.mark.asyncio
async def test_10_removal_denies_access_but_preserves_what_was_created(data):
    """**والإزالةُ تُقفل البابَ ولا تُتلف العلم**: ما أُنشئ يبقى للبحث."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import Dataset

    created = await _dataset(data.guest, data.project_id)
    dataset_id = uuid.UUID(created.json()["dataset_id"])
    await _set_access(data.owner, data.member, "removed")

    async with _client(data.guest) as http:
        assert (await http.get(
            f"{ANALYSIS}/datasets/{dataset_id}/versions")).status_code == 404

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        row = (await session.execute(
            select(Dataset).where(Dataset.id == dataset_id))).scalar_one()
        assert row.project_id == data.project_id
        assert row.tenant_id == data.owner["tenant_id"]

    # وصاحبُ البحث يقرؤها كما كانت.
    async with _client(data.owner) as http:
        assert (await http.get(
            f"{ANALYSIS}/datasets/{dataset_id}/versions")).status_code == 200


@requires_db
@pytest.mark.asyncio
async def test_11_manage_data_never_becomes_manage_sources_or_manage_team(data):
    """**ولا يُحلّ بابُ البيانات بفتح بابٍ آخر.** المصادرُ والفريقُ ممنوعان."""
    async with _client(data.guest) as http:
        assert (await http.post(
            f"/api/v1/workspace/projects/{data.project_id}/sources",
            json={"asset_id": str(uuid.uuid4())})).status_code == 403
        assert (await http.post(
            f"{TEAM}/{data.project_id}/members",
            json={"display_name": "من يُدسّ", "role": "co_author"})).status_code == 403
        capability = (await http.get(f"{TEAM}/{data.project_id}/access")).json()
    assert capability["can_manage_data"] is True
    assert capability["can_manage_sources"] is False
    assert capability["can_manage_team"] is False
    assert capability["can_manage_submission"] is False


@requires_db
@pytest.mark.asyncio
async def test_12_scientific_permissions_are_not_widened_by_the_data_bridge(data):
    """**والجسرُ ينقل السياق ولا يُغيّر مَن يملك ماذا.**

    فالتفسيرُ تحريرُ محتوًى (`edit_research_content`)، والاعتمادُ اعتمادُ
    مرشَّحات (`approve_scientific_candidates`) — وإدارةُ البيانات لا
    تُغني عن واحدٍ منهما. ولو وُسِّعت لَصار الإحصائيُّ يُوافق على خطّةٍ
    ويكتب دلالةً إداريّةً باسم الفريق.
    """
    created = await _dataset(data.guest, data.project_id)
    dataset_id = created.json()["dataset_id"]
    raw_version = created.json()["id"]
    async with _client(data.guest) as http:
        derived = await http.post(f"{ANALYSIS}/datasets/{dataset_id}/versions", json={
            "parent_version_id": raw_version, "state": "cleaned", "label": "منقّاة",
            "checksum": "f" * 64, "change_note_ar": "تنقية", "row_count": 48})
        version_id = derived.json()["id"]
        await http.post(f"{ANALYSIS}/datasets/versions/{version_id}/freeze")

    plan = await _plan(data.guest, data.project_id)
    plan_id = plan.json()["id"]

    # **والاعتمادُ يُردّ على حامل إدارة البيانات وحدها.**
    async with _client(data.guest) as http:
        refused = await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")
    assert refused.status_code == 403, refused.text

    async with _client(data.owner) as http:
        assert (await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")).status_code == 200

    async with _client(data.guest) as http:
        run = await http.post(f"{ANALYSIS}/runs", json={
            "plan_id": plan_id, "dataset_version_id": version_id, "tool": "python",
            "executed_test_keys": ["pearson_r"], "code_hash": "0" * 64})
        run_id = run.json()["id"]
        output = await http.post(f"{ANALYSIS}/runs/{run_id}/outputs", json={
            "output_kind": "statistic", "label_ar": "معامل", "test_key": "pearson_r",
            "payload": {"r": 0.1}})
        output_id = output.json()["id"]

        # **والتفسيرُ يُردّ كذلك** — ولا يفتحه الجسر.
        interpreted = await http.post(f"{ANALYSIS}/outputs/{output_id}/interpret", json={
            "result_ar": "علاقةٌ ضعيفة", "statistical_ar": "r = 0.1"})
    assert interpreted.status_code == 403, interpreted.text


# ═══════════════ ٣ · الإخفاء والتسريب ═══════════════


@requires_db
@pytest.mark.asyncio
async def test_13_a_cross_tenant_outsider_is_told_nothing(data):
    """**ومعرّفٌ مُخمَّنٌ لا يُعلم أوجد أم لا** — جوابُ المعدوم في كلّ باب."""
    created = await _dataset(data.owner, data.project_id)
    dataset_id = created.json()["dataset_id"]
    version_id = created.json()["id"]
    plan = await _plan(data.owner, data.project_id)
    plan_id = plan.json()["id"]

    async with _client(data.outsider) as http:
        for path in (f"{ANALYSIS}/datasets/{dataset_id}/versions",
                     f"{ANALYSIS}/datasets/versions/{version_id}/dictionary"):
            response = await http.get(path)
            assert response.status_code == 404, f"{path} → {response.status_code}"
        for path, body in (
            (f"{ANALYSIS}/datasets/versions/{version_id}/freeze", None),
            (f"{ANALYSIS}/plans/{plan_id}/approve", None),
        ):
            response = await http.post(path, json=body)
            assert response.status_code == 404, f"{path} → {response.status_code}"
        # **ومجموعةٌ لبحثٍ لا يملكه: جوابُ المعدوم لا «ممنوع».**
        forged = await http.post(f"{ANALYSIS}/datasets", json={
            "project_id": str(data.project_id), "name_ar": "دسٌّ",
            "classification": "C3", "raw_label": "خام",
            "raw_checksum": "9" * 64, "row_count": 1})
        assert forged.status_code == 404, forged.text


@requires_db
@pytest.mark.asyncio
async def test_14_a_same_tenant_colleague_is_still_denied(data):
    """**ومساواةُ المستأجر ليست تفويضًا** — زميلٌ في المؤسسة ليس عضوًا في البحث."""
    created = await _dataset(data.owner, data.project_id)
    async with _client(data.colleague) as http:
        blocked = await http.get(
            f"{ANALYSIS}/datasets/{created.json()['dataset_id']}/versions")
        assert blocked.status_code == 404, blocked.text
        assert (await http.get(f"{ANALYSIS}/datasets")).json() == []


@requires_db
@pytest.mark.asyncio
async def test_15_a_same_tenant_member_without_manage_data_is_denied(data):
    """وعضوٌ حقيقيٌّ في المستأجر نفسِه بلا إدارةِ بيانات: ممنوعٌ أيضًا.

    فحدُّ 0012 على مستوى المسار كان هو هو قبل الجسر — والجسرُ لم يخفّفه.
    """
    await _member(data.owner, data.colleague, data.project_id,
                  permissions=[VIEW], role="co_author")
    created = await _dataset(data.owner, data.project_id)
    async with _client(data.colleague) as http:
        blocked = await http.get(
            f"{ANALYSIS}/datasets/{created.json()['dataset_id']}/versions")
    assert blocked.status_code == 403, blocked.text


@requires_db
@pytest.mark.asyncio
async def test_16_the_locator_policies_never_expose_a_neighbour_project(data):
    """**قياسٌ على مستوى القاعدة نفسِها، لا على مستوى المسار.**

    فلو كانت سياسةُ تحديد الموضع تكشف مجموعاتِ المستأجر كلَّها لَمرّت
    كلُّ فحوص المسارات — المُرشِّحُ في التطبيق يخفي الزائد — ولَبقي
    التسريبُ قائمًا لأوّل استعلامٍ يُكتب غدًا بلا مُرشِّح.

    فتُقرأ الجداولُ **بلا أيّ مُرشِّح** في جلسةِ بيتِ الضيف، ويُشترط أن
    يكون كلُّ صفٍّ يراه من البحث المشترك وحده.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import Dataset

    await _dataset(data.guest, data.project_id, name="مجموعةُ المشترك")
    await _dataset(data.owner, data.other_project, name="مجموعةُ الجار",
                   checksum="7" * 64)

    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as session:
        rows = (await session.execute(select(Dataset))).scalars().all()
    assert rows, "لم يُرَ شيءٌ أصلًا — الفحصُ لا يقيس"
    assert {row.project_id for row in rows} == {data.project_id}, (
        "سياسةُ تحديد الموضع كشفت بحثًا مجاورًا في المؤسسة نفسِها")

    # والغريبُ في مؤسسةٍ ثالثة لا يرى شيئًا.
    async with tenant_session(data.outsider["tenant_id"],
                              data.outsider["user_id"]) as session:
        assert (await session.execute(select(Dataset))).scalars().all() == []


@requires_db
@pytest.mark.asyncio
async def test_17_the_actor_never_changes_across_the_data_hop(data):
    """**الفاعلُ هو هو قبل العبور وبعده** — يتغيّر المستأجرُ وحده."""
    from sqlalchemy import text

    from athera_api.db import project_session, tenant_session

    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as home:
        before = (await home.execute(
            text("SELECT app_current_tenant(), app_current_actor()"))).one()
    async with project_session(data.project_id, data.guest["tenant_id"],
                               data.guest["user_id"]) as scoped:
        after = (await scoped.execute(
            text("SELECT app_current_tenant(), app_current_actor()"))).one()

    assert before[0] == data.guest["tenant_id"]
    assert after[0] == data.owner["tenant_id"], "لم يُعبَر إلى مستأجر البحث"
    assert before[1] == after[1] == data.guest["user_id"], "تبدّل الفاعل"


@requires_db
@pytest.mark.asyncio
async def test_18_no_organization_membership_is_created_by_data_work(data):
    """**وعملُ البيانات لا يُنشئ انتماءً تنظيميًّا** — ولا تأليفًا ولا CRediT."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.identity import Membership
    from athera_api.models.portfolio import ProjectMember

    assert (await _dataset(data.guest, data.project_id)).status_code == 201

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        count = (await session.execute(
            select(func.count()).select_from(Membership)
            .where(Membership.tenant_id == data.owner["tenant_id"],
                   Membership.user_id == data.guest["user_id"]))).scalar_one()
        assert count == 0
        row = await session.get(ProjectMember, data.member.id)
        assert row is not None and row.is_author is False
        assert not (row.credit_roles or [])


# ═══════════ ٤ · خلطُ البحوث في كيانٍ واحد ═══════════


@requires_db
@pytest.mark.asyncio
async def test_19_a_run_cannot_marry_a_plan_to_another_projects_data(data):
    """**خطّةُ بحثٍ لا تُشغَّل على بياناتِ بحثٍ آخر** — ولو أدارهما واحد.

    وكان كلٌّ يُفوَّض على حدة، فمن يُدير بحثين يخلط بيناتهما في تشغيلةٍ
    واحدة ويُسجَّل المخرَجُ تحت الخطّة كأنّه منها. وبعد جسر المؤسسات
    يصير ذلك خلطَ بياناتِ مؤسسةٍ في خطّةِ أخرى.
    """
    first = await _dataset(data.owner, data.project_id)
    async with _client(data.owner) as http:
        derived = await http.post(
            f"{ANALYSIS}/datasets/{first.json()['dataset_id']}/versions", json={
                "parent_version_id": first.json()["id"], "state": "cleaned",
                "label": "منقّاة", "checksum": "1" * 64,
                "change_note_ar": "تنقية", "row_count": 40})
        mine_version = derived.json()["id"]
        await http.post(f"{ANALYSIS}/datasets/versions/{mine_version}/freeze")

        neighbour = await http.post(f"{ANALYSIS}/datasets", json={
            "project_id": str(data.other_project), "name_ar": "بياناتُ الجار",
            "classification": "C3", "raw_label": "خام",
            "raw_checksum": "2" * 64, "row_count": 10})
        n_derived = await http.post(
            f"{ANALYSIS}/datasets/{neighbour.json()['dataset_id']}/versions", json={
                "parent_version_id": neighbour.json()["id"], "state": "cleaned",
                "label": "منقّاة", "checksum": "3" * 64,
                "change_note_ar": "تنقية", "row_count": 9})
        other_version = n_derived.json()["id"]
        await http.post(f"{ANALYSIS}/datasets/versions/{other_version}/freeze")

        plan = await _plan(data.owner, data.project_id)
        plan_id = plan.json()["id"]
        await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")

        # الخطّةُ من هذا البحث، والنسخةُ من جاره — **جوابُ المعدوم**.
        mixed = await http.post(f"{ANALYSIS}/runs", json={
            "plan_id": plan_id, "dataset_version_id": other_version,
            "tool": "python", "executed_test_keys": ["pearson_r"],
            "code_hash": "4" * 64})
        assert mixed.status_code == 404, mixed.text

        # والمطابقُ يمرّ.
        sound = await http.post(f"{ANALYSIS}/runs", json={
            "plan_id": plan_id, "dataset_version_id": mine_version,
            "tool": "python", "executed_test_keys": ["pearson_r"],
            "code_hash": "5" * 64})
        assert sound.status_code == 201, sound.text
        run_id = sound.json()["id"]

        # **وتصديرٌ يُرفق تشغيلةَ بحثٍ آخرَ يُردّ** — وكان يُقبل بلا تفويض.
        crossed = await http.post(f"{ANALYSIS}/exports", json={
            "dataset_version_id": other_version, "run_id": run_id,
            "tool": "spss", "export_format": "csv"})
        assert crossed.status_code == 404, crossed.text


# ═══════════ ٥ · حدُّ الملفّ الخام — دعوى تُثبَت ═══════════


@requires_db
def test_20_no_product_path_attaches_a_raw_data_file_yet() -> None:
    """**ولا مسارَ في المنتج يُرفق ملفَّ بياناتٍ بنسخةٍ** — دعوى بنيويّة.

    فالسؤال المطروح: هل يستطيع المتعاونُ الخارجيُّ إتمامَ رحلةِ ملفِّ
    البيانات؟ والجواب أنّ تلك الرحلةَ **غيرُ موجودةٍ لأحد** في هذا
    الإصدار — لا له ولا لصاحب البحث.

    فنسخةُ المجموعة في V1 **موصوفةٌ ومبصومة**: اسمٌ وبصمةُ تحقّقٍ
    (`checksum`) وعددُ صفوف. والعمودُ `file_id` قائمٌ في المخطَّط ولا
    يكتبه مسارٌ ولا يقرؤه، ولا حقلَ له في أيّ عقدِ طلب.

    وربطُ الملفات بالبحث بابٌ آخرُ بصلاحيةٍ أخرى (`manage_sources` في
    `workspace`) — ولم يُفتح لحاملِ إدارة البيانات، ولا يجوز أن يُفتح
    لحلِّ هذا: من يُدير بياناتٍ لا يصير بذلك مديرَ مكتبةٍ ومصادر.

    فلا شيءَ يُزعم هنا إتمامُه: **الحدُّ يُعلَن، ويُحرس بنيويًّا** —
    فأوّلُ مسارٍ يُرفق ملفًّا يكسر هذا الفحص، ويوجب حينها إثباتَ رحلته
    عبرَ المؤسسات وحدَّ تخزينه.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "athera_api"
    router = (root / "routers" / "analysis.py").read_text(encoding="utf-8")
    schemas = (root / "schemas" / "analysis.py").read_text(encoding="utf-8")

    assert "file_id" not in router, (
        "مسارُ تحليلٍ صار يمسّ `file_id` — فيجب إثباتُ رحلةِ الملفّ عبر "
        "المؤسسات وحدُّ تخزينها قبل الشحن")
    assert "file_id" not in schemas, "عقدُ طلبٍ صار يقبل معرّفَ ملفّ"

    # والعمودُ موجودٌ في المخطَّط — فالدعوى «لا مسار» لا «لا عمود».
    model = (root / "models" / "analysis.py").read_text(encoding="utf-8")
    assert "file_id" in model


@requires_db
@pytest.mark.asyncio
async def test_21_the_policy_itself_requires_both_permission_rows(data):
    """**قياسُ السياسة وحدها** — لا المُرشِّح الذي في التطبيق فوقها.

    وهذا فرقٌ يُخفي عطبًا: `_managed` تُرشِّح بمجموعةِ البحوث المُدارة في
    التطبيق، فلو ضعُفت السياسةُ في القاعدة لَبقيت القوائمُ نظيفةً
    ولَمرّت فحوصُ المسارات كلُّها — **ولَبقي التسريبُ قائمًا لأوّل
    استعلامٍ يُكتب غدًا بلا مُرشِّح**.

    فيُقاس هنا ما تراه القاعدةُ نفسُها: صفوفُ تحليلٍ في جلسةِ بيتِ عضوٍ
    نُزعت عنه إحدى الصلاحيَّتين. والمطلوبُ صفر.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import (
        AnalysisPlanRow,
        Dataset,
        DatasetVersionRow,
    )

    assert (await _dataset(data.guest, data.project_id)).status_code == 201
    assert (await _plan(data.guest, data.project_id)).status_code == 201

    async def rows_seen() -> tuple[int, int, int]:
        async with tenant_session(data.guest["tenant_id"],
                                  data.guest["user_id"]) as session:
            return (
                len((await session.execute(select(Dataset))).scalars().all()),
                len((await session.execute(
                    select(DatasetVersionRow))).scalars().all()),
                len((await session.execute(
                    select(AnalysisPlanRow))).scalars().all()),
            )

    # وبالصفَّين معًا: يرى.
    assert all(count > 0 for count in await rows_seen()), await rows_seen()

    # **وبالاطّلاع وحده: صفر** — فالسياسةُ تشترط إدارةَ البيانات.
    await _set_permissions(data.owner, data.member, [VIEW])
    assert await rows_seen() == (0, 0, 0), (
        "السياسةُ لم تشترط `manage_data` — عضوٌ بالاطّلاع وحده يرى البيانات")

    # **وبإدارةِ البيانات وحدها: صفر** — فالأساسُ شرطٌ لا تزيين.
    await _set_permissions(data.owner, data.member, [DATA])
    assert await rows_seen() == (0, 0, 0), (
        "السياسةُ لم تشترط أساسَ `view_project`")

    # وبالإيقاف: صفر، وإن حمل الصفَّين.
    await _set_permissions(data.owner, data.member, [VIEW, DATA])
    await _set_access(data.owner, data.member, "suspended")
    assert await rows_seen() == (0, 0, 0), "السياسةُ لم تشترط عضويّةً نشِطة"

    await _set_access(data.owner, data.member, "active")
    assert all(count > 0 for count in await rows_seen())


# ═══════════ ٦ · حدودُ الترحيل 0036 نفسِه ═══════════


@requires_db
@pytest.mark.asyncio
async def test_22_every_touched_table_keeps_its_force_and_its_write_boundary() -> None:
    """**ولا جدولَ يفقد حدَّه الأساسيّ، ولا كتابةَ تُفتح بسياسةِ فاعل.**

    وهذا أدقُّ ما في هذا الترحيل: سياساتُ 0012 على هذه الجداول `FOR ALL`
    بحدِّ المستأجر، وسياساتُ 0036 `FOR SELECT` وحدها. فالقراءةُ تصير
    «مستأجري **أو** بحثٌ أثبتُّ فيه إدارةَ بياناته»، **والكتابةُ تبقى
    مستأجري وحدها**.

    ودرسُ دعوات الفريق حاضر: السياساتُ المُتاحة تتجمّع بـ«أو». فسياسةُ
    `INSERT` أو `UPDATE` بمُسنَدِ فاعلٍ هنا تحوّل «تحديدَ موضعٍ آمنًا»
    إلى **كتابةٍ مباشرةٍ عبر المؤسسات** — وذاك نقضُ التصميم كلِّه، لا
    توسيعُ ميزة. فيُعدّ الأمرُ في كلّ سياسة.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    tables = ("datasets", "dataset_versions", "data_dictionaries", "analysis_plans",
              "planned_tests", "analysis_runs", "analysis_outputs",
              "interpretations", "tool_exports")

    async with system_session() as session:
        force = dict((await session.execute(text(
            "SELECT c.relname, c.relrowsecurity AND c.relforcerowsecurity "
            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'public' AND c.relname = ANY(:names)"),
            {"names": list(tables)})).all())
        policies = (await session.execute(text(
            "SELECT tablename, policyname, cmd, permissive "
            "  FROM pg_policies WHERE tablename = ANY(:names)"),
            {"names": list(tables)})).all()

    for table in tables:
        assert force.get(table) is True, f"{table} فقد ENABLE/FORCE RLS"

    # **ولا سياسةَ فاعلٍ تكتب.** كلُّ ما ليس بحدِّ المستأجر يجب أن يكون
    # `SELECT` — ويُقاس بالأمر لا بالاسم.
    for table, policy, cmd, permissive in policies:
        assert permissive == "PERMISSIVE", (table, policy)
        if policy.endswith("_data_collaborator_read"):
            assert cmd == "SELECT", (
                f"{table}.{policy} أمرُها {cmd} — سياسةُ الفاعل تكتب!")
        else:
            assert policy == "tenant_isolation", (table, policy)

    collaborator = {table for table, policy, _c, _p in policies
                    if policy.endswith("_data_collaborator_read")}
    # **وجدولان بلا سياسةٍ عابرة — قصدًا**: لا يُقرآن إلّا داخل نطاق البحث.
    assert collaborator == {
        "datasets", "analysis_plans", "dataset_versions", "tool_exports",
        "planned_tests", "analysis_runs", "analysis_outputs"}, collaborator
    assert "data_dictionaries" not in collaborator
    assert "interpretations" not in collaborator


@requires_db
@pytest.mark.asyncio
async def test_23_the_locator_function_has_invoker_rights_and_no_bypass() -> None:
    """**ولا `SECURITY DEFINER` ولا `BYPASSRLS`** — قِيس، لا قيل.

    فقد ثبت في 0034 و0035 أنّ مالكَ الترحيل `rolsuper/rolbypassrls`،
    فدالّةٌ بحقوقه تقرأ الجدولَ كلَّه بلا سياق. ودالّةُ هذا الترحيل
    بحقوق المستدعي: ما تقرؤه يخضع لسياساته — صفوفُ عضويّةِ الفاعل هو.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        row = (await session.execute(text(
            "SELECT prosecdef, provolatile, proconfig "
            "  FROM pg_proc WHERE proname = 'app_can_manage_project_data'"))).one()
        bypass = (await session.execute(text(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = 'athera_app'"))).scalar_one()
        definers = set((await session.execute(text(
            "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            " WHERE n.nspname = 'public' AND p.prosecdef "
            "   AND p.proname LIKE 'app\\_%'"))).scalars().all())
        analysis_policies = (await session.execute(text(
            "SELECT tablename, policyname, coalesce(qual, '') || ' ' "
            "       || coalesce(with_check, '') "
            "  FROM pg_policies WHERE tablename = ANY(:names)"),
            {"names": ["datasets", "dataset_versions", "data_dictionaries",
                       "analysis_plans", "planned_tests", "analysis_runs",
                       "analysis_outputs", "interpretations", "tool_exports"]})).all()

    secdef, volatile, config = row
    assert secdef is False, "دالّةُ تحديد الموضع بحقوق المالك — تقرأ بلا عزل"
    assert volatile in ("s", b"s"), "يجب أن تكون STABLE"
    assert config == ["search_path=public, pg_temp"], config
    assert bypass is False, "دورُ زمن التشغيل يتجاوز العزل"

    # **وثلاثُ دوالَّ بحقوق المالك قائمةٌ منذ 0018 و0021 — وتُسمّى.**
    #
    # وهي دوالُّ **ما قبل المصادقة**: أيُّ مستأجرٍ لهذا البريد عند
    # الدخول، وأيُّ مستأجرٍ لرمز التجديد. ولا سياقَ فاعلٍ يومَ تُنادى —
    # فلا سياسةَ تخدمها، ومن ثَمّ حقوقُ المالك. وليست من طبقة البيانات
    # بحال، ولا تُقرأ منها.
    #
    # **والحدُّ المقصود هنا: لا مُحدِّدَ موضعِ بياناتٍ بحقوق المالك** —
    # فيُثبَت أنّ سياساتِ التحليل لا تنادي واحدةً منها.
    assert definers == {"app_login_tenant", "app_refresh_token_tenant",
                        "app_user_tenants"}, (
        f"طقمُ دوالِّ حقوق المالك تغيّر: {sorted(definers)}")
    assert analysis_policies
    for table, policy, body in analysis_policies:
        for definer in definers:
            assert definer not in body, (
                f"{table}.{policy} تنادي دالّةً بحقوق المالك: {definer}")


@requires_db
@pytest.mark.asyncio
async def test_24_no_analysis_policy_uses_a_broad_predicate() -> None:
    """**ولا `USING (true)` ولا ما يعمل عمله.**

    ومُسنَدٌ يخلو من `app_current_tenant()` و`app_can_manage_project_data()`
    معًا مُسنَدٌ لا يعرف مَن يسأل — فيُرفض ولو كان نصُّه طويلًا.
    """
    from sqlalchemy import text

    from athera_api.db import system_session

    async with system_session() as session:
        rows = (await session.execute(text(
            "SELECT tablename, policyname, coalesce(qual, '') "
            "  FROM pg_policies WHERE tablename = ANY(:names)"),
            {"names": ["datasets", "dataset_versions", "data_dictionaries",
                       "analysis_plans", "planned_tests", "analysis_runs",
                       "analysis_outputs", "interpretations", "tool_exports"]})).all()

    assert rows
    for table, policy, qual in rows:
        body = qual.strip().lower()
        assert body not in ("true", "(true)"), f"{table}.{policy} مفتوحةٌ للكلّ"
        assert ("app_current_tenant" in body
                or "app_can_manage_project_data" in body), (table, policy, qual)


# ═══════ ٧ · الأبوان معًا: صفوفُ التاريخ المختلطة ═══════
#
# **والمسارُ الجديد يمنع الجديد، ولا يمسّ ما في القاعدة.** والمسارُ
# القديم كان يفوّض خطّةَ التشغيلة ونسختَها كلًّا على حدة، و`run_id` في
# التصدير كان يُقبل بلا تفويضٍ أصلًا. فما كان مستورًا بعزل المستأجر يصير
# بـ0036 مرئيًّا عبرَ المؤسسات **من جانبه المأذون** — فيُشترط في السياسة
# أن يكون الجذرُ واحدًا، لا أن يكون أحدُ الجذرين مأذونًا.


@contextlib.asynccontextmanager
async def _as_owner():
    """اتصالُ مالكِ المخطَّط — **لمحاكاةِ تاريخٍ، لا لفتحِ باب**.

    فالصفُّ المختلطُ الذي نُحاكيه كُتب قبل أن يوجد المُشغِّلُ الذي يمنعه،
    ولا سبيلَ إلى كتابته اليوم بجلسةِ تطبيقٍ — وهذا هو المقصود. فيُكتب
    بحقوق المالك ومُشغِّلاتُ الجذر مُعطَّلةٌ في نطاق هذه الكتلة وحدها،
    ثمّ تُعاد.

    **ودورُ زمن التشغيل لا يُمسّ**: هذه جلسةٌ تُفتح وتُغلق في الاختبار،
    ولا تدخل مصنعَ جلسات التطبيق.
    """
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    url = os.getenv("DATABASE_MIGRATION_URL", "")
    if not url:
        pytest.skip("DATABASE_MIGRATION_URL is not configured")
    engine = create_async_engine(url.replace("+psycopg", "+asyncpg"),
                                 poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            async with session.begin():
                for table in ("analysis_runs", "tool_exports"):
                    await session.execute(text(
                        f"ALTER TABLE {table} DISABLE TRIGGER USER"))
                # **ولا `finally` يُعيد التمكين**: تعديلُ الجدول في
                # PostgreSQL معامليّ، فسقوطُ الكتلة يُرجع المعاملةَ
                # ويُعيد المُشغِّلَ معها. و`finally` هنا كان يكتب عبارةً
                # في معاملةٍ مُجهَضة، **فيُخفي الخطأ الأصليَّ خلف خطئه**.
                yield session
                for table in ("analysis_runs", "tool_exports"):
                    await session.execute(text(
                        f"ALTER TABLE {table} ENABLE TRIGGER USER"))
    finally:
        await engine.dispose()


async def _mixed_run(owner, *, plan_project, data_project, suffix):
    """تشغيلةٌ خطّتُها في بحثٍ ونسختُها في آخر — **تُدسّ بصلاحية النظام**.

    ولا تُنشأ بمسارٍ: المسارُ يرفضها اليوم، والمُشغِّلُ في القاعدة يرفضها
    كذلك. فتُكتب بجلسةِ نظامٍ بلا مُشغِّل — لأنّ المقصودَ محاكاةُ صفٍّ
    **تُرك في القاعدة قبل هذه الدفعة**، لا اختبارُ بابٍ مفتوح.
    """
    from sqlalchemy import text

    async with _as_owner() as session:
        plan = (await session.execute(text(
            "INSERT INTO analysis_plans (id, tenant_id, project_id, version_label, "
            "  created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :p, :label, now(), now()) "
            "RETURNING id"),
            {"t": owner["tenant_id"], "p": plan_project,
             "label": f"mixed-{suffix}"})).scalar_one()
        dataset = (await session.execute(text(
            "INSERT INTO datasets (id, tenant_id, project_id, name_ar, "
            "  classification, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :p, :n, 'C3', now(), now()) "
            "RETURNING id"),
            {"t": owner["tenant_id"], "p": data_project,
             "n": f"mixed-data-{suffix}"})).scalar_one()
        version = (await session.execute(text(
            "INSERT INTO dataset_versions (id, tenant_id, dataset_id, state, "
            "  label, checksum, freeze_id, frozen_by, created_at, updated_at, "
            "  frozen_at) "
            # `raw` مجمَّدةٌ: القيدُ يشترط للحالِ غيرِ الخام أبًا وملاحظةَ
            # تغيير، والمقصودُ هنا أبسطُ صفٍّ مجمَّدٍ صحيحٍ في القاعدة.
            "VALUES (gen_random_uuid(), :t, :d, 'raw', 'v', :c, :f, :u, "
            "        now(), now(), now()) RETURNING id"),
            {"t": owner["tenant_id"], "d": dataset,
             "c": ("m" * 8 + suffix)[:64],
             "f": f"frz-{suffix}", "u": owner["user_id"]})).scalar_one()
        run = (await session.execute(text(
            "INSERT INTO analysis_runs (id, tenant_id, plan_id, dataset_version_id, "
            "  dataset_freeze_id, tool, started_at, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :pl, :v, :f, 'python', now(), "
            "        now(), now()) RETURNING id"),
            {"t": owner["tenant_id"], "pl": plan, "v": version,
             "f": f"frz-{suffix}"})).scalar_one()
        output = (await session.execute(text(
            "INSERT INTO analysis_outputs (id, tenant_id, run_id, output_kind, "
            "  label_ar, payload, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :r, 'statistic', 'مخرَجٌ مختلط', "
            "        '{}'::jsonb, now(), now()) RETURNING id"),
            {"t": owner["tenant_id"], "r": run})).scalar_one()
        export = (await session.execute(text(
            "INSERT INTO tool_exports (id, tenant_id, dataset_version_id, run_id, "
            "  tool, export_format, limitations_ar, limitations_en, "
            "  created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :v, :r, 'spss', 'csv', '—', '—', "
            "        now(), now()) RETURNING id"),
            {"t": owner["tenant_id"], "v": version, "r": run})).scalar_one()
    return {"plan": plan, "dataset": dataset, "version": version,
            "run": run, "output": output, "export": export,
            "freeze_id": f"frz-{suffix}"}


@requires_db
@pytest.mark.asyncio
async def test_25_a_historically_mixed_run_is_invisible_from_either_side(data):
    """**صفٌّ مختلطُ الجذر لا يُرى من الجانب المأذون** — ولا من الآخر.

    فالمتعاونُ مأذونٌ في البحث المشترك. ولو اكتفت السياسةُ بجذر الخطّة
    لَرأى تشغيلةً **نسختُها من بحثٍ آخرَ في المؤسسة نفسِها** — ومعها
    مخرَجُها: رقمٌ حُسب على بياناتِ بحثٍ لا يملكه، يُقرأ نتيجةً للبحث
    الذي يملكه.

    ويُقاس بلا أيّ مُرشِّح في التطبيق: ما تراه القاعدةُ نفسُها.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import (
        AnalysisOutputRow,
        AnalysisRun,
        ToolExport,
    )

    # الخطّةُ في البحث المشترك، والبيانات في بحثٍ آخرَ لصاحبِه نفسِه.
    mixed = await _mixed_run(data.owner, plan_project=data.project_id,
                             data_project=data.other_project,
                             suffix=data.suffix)

    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as session:
        runs = (await session.execute(select(AnalysisRun))).scalars().all()
        outputs = (await session.execute(select(AnalysisOutputRow))).scalars().all()
        exports = (await session.execute(select(ToolExport))).scalars().all()

    assert mixed["run"] not in {row.id for row in runs}, (
        "تشغيلةٌ مختلطةُ الجذر ظهرت للمتعاون من جانب خطّتها")
    assert mixed["output"] not in {row.id for row in outputs}, (
        "مخرَجُ تشغيلةٍ مختلطةٍ ظهر — رقمٌ من بحثٍ آخر تحت البحث المأذون")
    assert mixed["export"] not in {row.id for row in exports}, (
        "تصديرٌ مختلطٌ ظهر")

    # والعكسُ كذلك: لو كان الإذنُ على جانب البيانات لا الخطّة.
    reversed_mix = await _mixed_run(data.owner, plan_project=data.other_project,
                                    data_project=data.project_id,
                                    suffix=f"{data.suffix}b")
    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as session:
        runs = (await session.execute(select(AnalysisRun))).scalars().all()
        exports = (await session.execute(select(ToolExport))).scalars().all()
    assert reversed_mix["run"] not in {row.id for row in runs}, (
        "تشغيلةٌ مختلطةُ الجذر ظهرت من جانب بياناتها")
    assert reversed_mix["export"] not in {row.id for row in exports}


@requires_db
@pytest.mark.asyncio
async def test_26_a_sound_run_is_still_visible(data):
    """**والحارسُ لا يُعمي عن الصحيح**: تشغيلةٌ جذرُها واحدٌ تُرى.

    فحارسٌ يمنع الكلَّ يمرّ في كلّ فحصِ تسريبٍ ولا يخدم أحدًا.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import AnalysisOutputRow, AnalysisRun, ToolExport

    sound = await _mixed_run(data.owner, plan_project=data.project_id,
                             data_project=data.project_id,
                             suffix=f"{data.suffix}s")
    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as session:
        runs = {row.id for row in (await session.execute(
            select(AnalysisRun))).scalars().all()}
        outputs = {row.id for row in (await session.execute(
            select(AnalysisOutputRow))).scalars().all()}
        exports = {row.id for row in (await session.execute(
            select(ToolExport))).scalars().all()}
    assert sound["run"] in runs
    assert sound["output"] in outputs
    assert sound["export"] in exports


@requires_db
@pytest.mark.asyncio
async def test_27_a_foreign_run_on_an_authorised_export_is_concealed(data):
    """**ولا يُعرَض معرّفُ تشغيلةٍ غريبةٍ من خلال تصديرٍ مأذونٍ بنسخته.**

    فالتصديرُ نسختُه من البحث المشترك — مأذونٌ فيه — وتشغيلتُه من بحثٍ
    آخر. ولو اكتفت السياسةُ بجذر النسخة لَظهر الصفُّ وفيه `run_id` يدلّ
    على تشغيلةٍ لا يملكها الطالب.
    """
    from sqlalchemy import select, text

    from athera_api.db import tenant_session
    from athera_api.models.analysis import ToolExport

    mine = await _mixed_run(data.owner, plan_project=data.project_id,
                            data_project=data.project_id,
                            suffix=f"{data.suffix}m")
    theirs = await _mixed_run(data.owner, plan_project=data.other_project,
                              data_project=data.other_project,
                              suffix=f"{data.suffix}t")

    async with _as_owner() as session:
        crossed = (await session.execute(text(
            "INSERT INTO tool_exports (id, tenant_id, dataset_version_id, run_id, "
            "  tool, export_format, limitations_ar, limitations_en, "
            "  created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :v, :r, 'spss', 'csv', '—', '—', "
            "        now(), now()) RETURNING id"),
            {"t": data.owner["tenant_id"], "v": mine["version"],
             "r": theirs["run"]})).scalar_one()

    async with tenant_session(data.guest["tenant_id"], data.guest["user_id"]) as session:
        seen = {row.id for row in (await session.execute(
            select(ToolExport))).scalars().all()}
    assert crossed not in seen, "تصديرٌ يحمل تشغيلةً غريبةً ظهر للمتعاون"
    assert mine["export"] in seen, "والتصديرُ السليمُ اختفى — الحارسُ أعمى"


@requires_db
@pytest.mark.asyncio
async def test_28_the_database_refuses_a_new_mixed_run_or_export(data):
    """**والحدُّ في القاعدة لا في الموجّه**: مُشغِّلٌ يرفض الخلطَ الجديد.

    فشرطُ المسار صحيحٌ ولا يكفي: موجّهٌ يُكتب غدًا، أو هجرةُ بيانات، أو
    صفٌّ يُدسّ بجلسةٍ مشروعة — كلُّها تتجاوز شيفرةَ المسار.

    **وعلى هذا الجدول حارسٌ قائمٌ من قبل** يُطابق معرّفَ تجميدِ التشغيلة
    بمعرّف تجميدِ نسختها (PRD 17.3). فيُمرَّر المعرّفُ الصحيحُ هنا قصدًا:
    المقصودُ قياسُ حارسِ **الجذر** لا الاصطدامُ بحارسٍ آخرَ قبله.
    """
    import pytest as _pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    from athera_api.db import tenant_session
    from athera_api.models.analysis import AnalysisPlanRow, Dataset, DatasetVersionRow

    from sqlalchemy import select

    # جذرانِ سليمان في بحثين، بجلسةٍ مشروعةٍ في مستأجر صاحبِهما.
    first = await _mixed_run(data.owner, plan_project=data.project_id,
                             data_project=data.project_id,
                             suffix=f"{data.suffix}g1")
    second = await _mixed_run(data.owner, plan_project=data.other_project,
                              data_project=data.other_project,
                              suffix=f"{data.suffix}g2")

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        # تشغيلةٌ تخلط خطّةَ هذا بنسخةِ ذاك — **يرفضها المُشغِّل**.
        with _pytest.raises(DBAPIError) as mixed:
            await session.execute(text(
                "INSERT INTO analysis_runs (id, tenant_id, plan_id, "
                "  dataset_version_id, dataset_freeze_id, tool, started_at, "
                "  created_at, updated_at) "
                "VALUES (gen_random_uuid(), :t, :pl, :v, :f, 'python', now(), "
                "        now(), now())"),
                {"t": data.owner["tenant_id"], "pl": first["plan"],
                 "v": second["version"], "f": second["freeze_id"]})
        assert "mix two projects" in str(mixed.value)

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        # وتصديرٌ يُرفق تشغيلةً غريبة — يرفضها المُشغِّل.
        with _pytest.raises(DBAPIError) as foreign:
            await session.execute(text(
                "INSERT INTO tool_exports (id, tenant_id, dataset_version_id, "
                "  run_id, tool, export_format, limitations_ar, limitations_en, "
                "  created_at, updated_at) "
                "VALUES (gen_random_uuid(), :t, :v, :r, 'spss', 'csv', '—', '—', "
                "        now(), now())"),
                {"t": data.owner["tenant_id"], "v": first["version"],
                 "r": second["run"]})
        assert "foreign run" in str(foreign.value)

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        # **والسليمُ يمرّ** — فالحارسُ يفصل ولا يُقفل.
        await session.execute(text(
            "INSERT INTO analysis_runs (id, tenant_id, plan_id, "
            "  dataset_version_id, dataset_freeze_id, tool, started_at, "
            "  created_at, updated_at) "
            "VALUES (gen_random_uuid(), :t, :pl, :v, :f, 'python', now(), "
            "        now(), now())"),
            {"t": data.owner["tenant_id"], "pl": first["plan"],
             "v": first["version"], "f": first["freeze_id"]})
        # ويبقى الجذرانِ كما هما.
        assert (await session.execute(select(AnalysisPlanRow.project_id).where(
            AnalysisPlanRow.id == first["plan"]))).scalar_one() == data.project_id
        assert (await session.execute(
            select(Dataset.project_id).join(
                DatasetVersionRow, DatasetVersionRow.dataset_id == Dataset.id)
            .where(DatasetVersionRow.id == first["version"]))).scalar_one() \
            == data.project_id


# ═══════ ٨ · بوابةُ التاريخ في الترحيل نفسِه ═══════


@requires_db
def test_29_the_preflight_refuses_to_install_over_mixed_history() -> None:
    """**الترحيلُ يتوقّف إن كان في القاعدة صفٌّ مختلطُ الجذر** — ولا يُصلحه.

    وهذا أهمُّ فحصٍ في هذه الدفعة: المُشغِّلُ يمنع الجديد، والسياسةُ
    تُخفي المختلط — لكنّ **تثبيتَ 0036 على قاعدةٍ فيها تاريخٌ مختلطٌ
    قرارٌ لا يُتخذ صامتًا**. فالصفوفُ تبقى، ومن يصالحها إنسانٌ يعرف ما
    جرى: بياناتُ علمٍ لا تُصلَح بترحيل.

    ويُقاس بتشغيل دالّة الفحص القبليّ نفسِها على قاعدةٍ فيها صفٌّ مدسوسٌ
    — لا بقراءة نصِّها. ثمّ يُزال الصفُّ ويُعاد الفحصُ فيمرّ.
    """
    import importlib.util
    import os
    import pathlib
    import uuid as _uuid

    import pytest as _pytest
    from sqlalchemy import create_engine

    url = os.getenv("DATABASE_MIGRATION_URL", "")
    if not url:
        _pytest.skip("DATABASE_MIGRATION_URL is not configured")

    versions = (pathlib.Path(__file__).resolve().parents[3] / "infra" / "db"
                / "migrations" / "versions")
    spec = importlib.util.spec_from_file_location(
        "m0036", versions / "0036_cross_tenant_data_collaboration.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = create_engine(url)
    suffix = _uuid.uuid4().hex[:8]

    def reported(conn) -> set[str]:
        """معرّفاتُ التشغيلات التي يُبلّغ عنها الفحصُ القبليّ الآن."""
        return {row[0] for row in
                conn.exec_driver_sql(module.PREFLIGHT_RUNS).fetchall()}

    def refuse(conn) -> str:
        class _Bind:
            def exec_driver_sql(self, statement):
                return conn.exec_driver_sql(statement)

        class _Op:
            @staticmethod
            def get_bind():
                return _Bind()

        module.op = _Op  # type: ignore[attr-defined]
        try:
            module._preflight()
        except RuntimeError as refusal:
            return str(refusal)
        return ""

    planted: dict[str, str] = {}
    projects: list = []
    try:
        # **ويُقاس الفرقُ لا النظافةُ المطلقة.** فحزمةُ الاختبارات نفسُها
        # تدسّ صفوفًا مختلطةً قصدًا (فحوصُ الرؤية أعلاه)، وقاعدةُ التطوير
        # تحمل أثرَ تشغيلاتٍ سابقة. فحصٌ يشترط قاعدةً نظيفةً يمرّ اليوم
        # ويفشل غدًا لسببٍ لا علاقةَ له بما يحرسه.
        with engine.connect() as conn:
            before = reported(conn)

        with engine.begin() as conn:
            tenant = conn.exec_driver_sql(
                "SELECT id FROM tenants LIMIT 1").scalar_one()
            user = conn.exec_driver_sql(
                "SELECT id FROM users LIMIT 1").scalar_one()
            if user is None:
                _pytest.skip("the drill database has no user to attribute a freeze to")
            # **بحثان يُنشآن هنا** — ولا يُبحث عن بحثين موجودين: فحصٌ
            # يتخطّى نفسَه حين لا يجد بيئتَه لا يقيس شيئًا، وقد وقع ذلك.
            projects = [
                conn.exec_driver_sql(
                    "INSERT INTO research_projects (id, tenant_id, working_title_ar, "
                    "  created_at, updated_at) "
                    "VALUES (gen_random_uuid(), %(t)s, %(n)s, now(), now()) "
                    "RETURNING id",
                    {"t": tenant, "n": f"preflight-{suffix}-{index}"}).scalar_one()
                for index in (1, 2)]

            for table in ("analysis_runs", "tool_exports"):
                conn.exec_driver_sql(f"ALTER TABLE {table} DISABLE TRIGGER USER")

            plan = conn.exec_driver_sql(
                "INSERT INTO analysis_plans (id, tenant_id, project_id, "
                "  version_label, created_at, updated_at) "
                "VALUES (gen_random_uuid(), %(t)s, %(p)s, %(l)s, now(), now()) "
                "RETURNING id",
                {"t": tenant, "p": projects[0], "l": f"pf-{suffix}"}).scalar_one()
            dataset = conn.exec_driver_sql(
                "INSERT INTO datasets (id, tenant_id, project_id, name_ar, "
                "  classification, created_at, updated_at) "
                "VALUES (gen_random_uuid(), %(t)s, %(p)s, %(n)s, 'C3', now(), now()) "
                "RETURNING id",
                {"t": tenant, "p": projects[1], "n": f"pf-{suffix}"}).scalar_one()
            version = conn.exec_driver_sql(
                "INSERT INTO dataset_versions (id, tenant_id, dataset_id, state, "
                "  label, checksum, freeze_id, frozen_by, frozen_at, "
                "  created_at, updated_at) "
                "VALUES (gen_random_uuid(), %(t)s, %(d)s, 'raw', 'v', %(c)s, "
                "        %(f)s, %(u)s, now(), now(), now()) RETURNING id",
                {"t": tenant, "d": dataset, "c": ("p" * 8 + suffix)[:64],
                 "f": f"pf-{suffix}", "u": user}).scalar_one()
            run = conn.exec_driver_sql(
                "INSERT INTO analysis_runs (id, tenant_id, plan_id, "
                "  dataset_version_id, dataset_freeze_id, tool, started_at, "
                "  created_at, updated_at) "
                "VALUES (gen_random_uuid(), %(t)s, %(pl)s, %(v)s, %(f)s, "
                "        'python', now(), now(), now()) RETURNING id",
                {"t": tenant, "pl": plan, "v": version,
                 "f": f"pf-{suffix}"}).scalar_one()
            planted = {"run": str(run), "plan": str(plan),
                       "dataset": str(dataset), "version": str(version)}
            for table in ("analysis_runs", "tool_exports"):
                conn.exec_driver_sql(f"ALTER TABLE {table} ENABLE TRIGGER USER")

        # **والفحصُ القبليُّ يرفض** — ويقول العددَ والمعرّفاتِ والبحوثَ،
        # ولا يُفصح عن حمولةٍ ولا بصمةٍ ولا اسمِ مجموعة.
        with engine.connect() as conn:
            assert reported(conn) == before | {planted["run"]}, (
                "الفحصُ القبليُّ لم يرَ الصفَّ المدسوس")
            message = refuse(conn)

        assert "HOLD — historical mixed-project analysis rows" in message
        assert planted["run"] in message
        assert str(projects[0]) in message and str(projects[1]) in message
        # ولا حمولةَ ولا بصمةَ ولا اسمَ مجموعة.
        assert ("p" * 8 + suffix)[:64] not in message
        assert planted["dataset"] not in message

        # ── ثمّ يُزال الصفُّ المختلطُ وحدَه، فيعود البلاغُ إلى ما كان ──
        #
        # **ونسخةُ المجموعة لا تُحذف**: عليها حدُّ منتجٍ يمنع الحذف
        # (`forbid_row_mutation`) — وهو حدٌّ صحيحٌ لا يُفكّ لأجل تنظيف
        # اختبار. والفحصُ يُبلّغ عن التشغيلات والتصديرات، فحذفُ التشغيلة
        # يُنظِّف ما دُسّ؛ وما يبقى صفوفٌ سليمةُ الجذر كلٌّ في بحثه.
        with engine.begin() as conn:
            conn.exec_driver_sql("DELETE FROM analysis_runs WHERE id = %(r)s",
                                 {"r": planted["run"]})
        with engine.connect() as conn:
            assert reported(conn) == before, "بقي أثرُ الصفّ المدسوس"
    finally:
        engine.dispose()


# ═══════ ٩ · الصلاحياتُ العلمية مستقلّةٌ عبرَ المؤسسات ═══════
#
# **ولا يُشترى الاعتمادُ بإدارةِ بيانات.** فالمشرفُ يعتمد ولا يمسّ
# البيانات، والمؤلِّفُ المشاركُ يفسّر ولا يمسّها. وفي المستأجر الواحد
# هذا قائمٌ منذ RC-T1A؛ والمقصودُ هنا أن يبقى قائمًا عبرَ المؤسسات.


async def _external_with(owner, project_id, *, permissions, role, suffix):
    """متعاونٌ من مؤسسةٍ ثالثةٍ بصلاحيّاتٍ صريحة — ولا `manage_data` فيها."""
    from athera_api.db import tenant_session
    from athera_api.services import collaboration

    person = await _third_tenant(suffix)
    async with tenant_session(owner["tenant_id"], owner["user_id"]) as session:
        issued = await collaboration.invite_member(
            session, tenant_id=owner["tenant_id"], project_id=project_id,
            inviter_user_id=owner["user_id"], email=person["email"],
            display_name="متعاونٌ علميّ", role=role,
            permissions=list(permissions), invited_user_id=person["user_id"])
        token = issued.token
    async with _client(person) as http:
        accepted = await http.post("/api/v1/invitations/accept", json={"token": token})
        assert accepted.status_code == 200, accepted.text
    return person


async def _approvable_plan(owner, project_id):
    """خطّةٌ بوسمِ نسخةٍ فريد — **والقيدُ في القاعدة: خطّةٌ لكلّ وسم**."""
    plan = await _plan(owner, project_id, label=f"v-{uuid.uuid4().hex[:8]}")
    assert plan.status_code == 201, plan.text
    return plan.json()["id"]


async def _an_output(owner, project_id, suffix):
    """مخرَجٌ حقيقيٌّ بسلسلته: مجموعةٌ فنسخةٌ مجمّدةٌ فخطّةٌ معتمدةٌ فتشغيلة."""
    created = await _dataset(owner, project_id, checksum=("o" * 8 + suffix)[:64])
    dataset_id = created.json()["dataset_id"]
    async with _client(owner) as http:
        derived = await http.post(f"{ANALYSIS}/datasets/{dataset_id}/versions", json={
            "parent_version_id": created.json()["id"], "state": "cleaned",
            "label": "منقّاة", "checksum": ("q" * 8 + suffix)[:64],
            "change_note_ar": "تنقية", "row_count": 40})
        version_id = derived.json()["id"]
        await http.post(f"{ANALYSIS}/datasets/versions/{version_id}/freeze")
    plan_id = await _approvable_plan(owner, project_id)
    async with _client(owner) as http:
        await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")
        run = await http.post(f"{ANALYSIS}/runs", json={
            "plan_id": plan_id, "dataset_version_id": version_id, "tool": "python",
            "executed_test_keys": ["pearson_r"], "code_hash": ("r" * 64)})
        run_id = run.json()["id"]
        output = await http.post(f"{ANALYSIS}/runs/{run_id}/outputs", json={
            "output_kind": "statistic", "label_ar": "معامل", "test_key": "pearson_r",
            "payload": {"r": 0.3}})
    return output.json()["id"]


@requires_db
@pytest.mark.asyncio
async def test_30_an_external_supervisor_approves_without_manage_data(data):
    """**المشرفُ يعتمد ولا يملك بيانات** — والمسارُ المُعشَّشُ يجعل ذلك ممكنًا.

    ولولا الشكلُ الثاني لَلزمه `manage_data` ليُحدَّد موضعُ خطّته —
    صلاحيةٌ لا شأنَ لها بعمله، ومنحُها له يفتح له قاموسَ الأعمدة
    وبصماتِ البيانات. **والاستقلالُ هو الحدّ.**
    """
    supervisor = await _external_with(
        data.owner, data.project_id, permissions=[VIEW, APPROVE],
        role="supervisor", suffix=f"{data.suffix}sv")
    plan_id = await _approvable_plan(data.owner, data.project_id)

    async with _client(supervisor) as http:
        # ما يملكه: الاعتمادُ نعم، والبياناتُ لا.
        capability = (await http.get(f"{TEAM}/{data.project_id}/access")).json()
        assert capability["can_manage_data"] is False
        assert APPROVE in capability["permissions"]

        approved = await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{plan_id}/approve")
        assert approved.status_code == 200, approved.text
        assert approved.json()["is_locked"] is True

        # **ولا بياناتٍ له**: لا قائمةً ولا قراءةَ مجموعةٍ ولا إنشاء.
        assert (await http.get(f"{ANALYSIS}/datasets")).json() == []
        created = await _dataset(supervisor, data.project_id,
                                 checksum=("z" * 8 + data.suffix)[:64])
        assert created.status_code == 403, created.text


@requires_db
@pytest.mark.asyncio
async def test_31_an_external_coauthor_interprets_without_manage_data(data):
    """**والمؤلِّفُ المشاركُ يفسّر ولا يملك بيانات.**"""
    output_id = await _an_output(data.owner, data.project_id, f"{data.suffix}o")
    coauthor = await _external_with(
        data.owner, data.project_id, permissions=[VIEW, EDIT],
        role="co_author", suffix=f"{data.suffix}ca")

    async with _client(coauthor) as http:
        capability = (await http.get(f"{TEAM}/{data.project_id}/access")).json()
        assert capability["can_manage_data"] is False

        interpreted = await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/outputs/{output_id}/interpret",
            json={"result_ar": "علاقةٌ موجبةٌ ضعيفة",
                  "statistical_ar": "r = 0.3", "theoretical_ar": "يتّسق مع النظرية"})
        assert interpreted.status_code == 200, interpreted.text
        assert "statistical" in interpreted.json()["layers_present"]

        assert (await http.get(f"{ANALYSIS}/datasets")).json() == []
        blocked = await _dataset(coauthor, data.project_id,
                                 checksum=("y" * 8 + data.suffix)[:64])
        assert blocked.status_code == 403, blocked.text


@requires_db
@pytest.mark.asyncio
async def test_32_the_nested_routes_refuse_the_wrong_permission(data):
    """ومصفوفةُ المنع: **كلُّ فعلٍ بصلاحيّته، ولا واحدةٌ تُغني عن أخرى**."""
    plan_id = await _approvable_plan(data.owner, data.project_id)
    output_id = await _an_output(data.owner, data.project_id, f"{data.suffix}n")
    body = {"result_ar": "نصٌّ لا يُكتب", "statistical_ar": "r = 0"}

    # الإحصائيُّ: إدارةُ بياناتٍ بلا اعتمادٍ ولا تحرير.
    async with _client(data.guest) as http:
        assert (await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{plan_id}/approve")
        ).status_code == 403
        assert (await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/outputs/{output_id}/interpret",
            json=body)).status_code == 403

    # وباطّلاعٍ وحده: ممنوعٌ في البابين.
    view_only = await _external_with(
        data.owner, data.project_id, permissions=[VIEW],
        role="acknowledged", suffix=f"{data.suffix}vo")
    async with _client(view_only) as http:
        assert (await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{plan_id}/approve")
        ).status_code == 403
        assert (await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/outputs/{output_id}/interpret",
            json=body)).status_code == 403

    # **وبالصلاحية بلا أساس الاطّلاع: لا يُعبَر الجسرُ أصلًا** — ٤٠٤.
    no_baseline = await _external_with(
        data.owner, data.project_id, permissions=[APPROVE],
        role="supervisor", suffix=f"{data.suffix}nb")
    async with _client(no_baseline) as http:
        refused = await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{plan_id}/approve")
    assert refused.status_code == 404, refused.text

    # وغريبٌ من مؤسسةٍ ثالثة: جوابُ المعدوم.
    async with _client(data.outsider) as http:
        assert (await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{plan_id}/approve")
        ).status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_33_the_route_project_is_a_scope_selector_not_authority(data):
    """**وذكرُ البحث لا يمنح شيئًا**: خطّةُ بحثٍ آخرَ تُردّ جوابَ المعدوم.

    ولو اكتُفي بتفويض البحث المذكور لَاعتمد المشرفُ خطّةَ بحثٍ لا يملكه
    بذكر بحثٍ يملكه.
    """
    supervisor = await _external_with(
        data.owner, data.project_id, permissions=[VIEW, APPROVE],
        role="supervisor", suffix=f"{data.suffix}x")
    foreign_plan = await _approvable_plan(data.owner, data.other_project)

    async with _client(supervisor) as http:
        crossed = await http.post(
            f"{ANALYSIS}/projects/{data.project_id}/plans/{foreign_plan}/approve")
    assert crossed.status_code == 404, crossed.text

    # والخطّةُ لم تُعتمد.
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.analysis import AnalysisPlanRow

    async with tenant_session(data.owner["tenant_id"], data.owner["user_id"]) as session:
        row = (await session.execute(select(AnalysisPlanRow).where(
            AnalysisPlanRow.id == uuid.UUID(foreign_plan)))).scalar_one()
    assert row.approved_at is None


@requires_db
@pytest.mark.asyncio
async def test_34_the_legacy_routes_still_work_in_the_same_tenant(data):
    """**والشكلُ القديمُ لم يُمسّ**: صاحبُ البحث يعتمد ويفسّر بعنوانه القديم."""
    plan_id = await _approvable_plan(data.owner, data.project_id)
    output_id = await _an_output(data.owner, data.project_id, f"{data.suffix}L")

    async with _client(data.owner) as http:
        approved = await http.post(f"{ANALYSIS}/plans/{plan_id}/approve")
        assert approved.status_code == 200, approved.text
        interpreted = await http.post(
            f"{ANALYSIS}/outputs/{output_id}/interpret",
            json={"result_ar": "نتيجةٌ مفسَّرة", "statistical_ar": "r = 0.3"})
        assert interpreted.status_code == 200, interpreted.text
