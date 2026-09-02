"""مساحة عمل البحث | PUBRIVA project workspace.

يثبت هذا الملف أربعة أشياء لا يُشحن بدونها:
١) عزل المستأجر على جدولَي الربط الجديدين — RLS مفروضة لا مُعلنة فقط.
٢) الافتراض `saved_only` للمصادر — الاستيراد ليس حكمًا بالصلاحية دليلًا.
٣) الإزالة تُخبر بما يترتب **قبل** أن تقع، وترفض حتى يُقرّ الباحث.
٤) ما في السلّة لا يظهر قائمًا — في أي شاشة.
"""
import datetime as dt
import pathlib
import uuid

import pytest

from tests.conftest import requires_db


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ─────────────────────── اختبارات خالصة بلا قاعدة ───────────────────────

def test_brain_roles_all_exist_in_the_field_vocabulary():
    """كل دورٍ يذكره «دماغ البحث» موجودٌ فعلًا في مفردات الحقول.

    وإلا فالعنصر يظهر «ناقصًا» أبدًا مهما وثّق الباحث — لأن الاسم المكتوب
    بجانب السجل لا يقابل شيئًا فيه. وهو الخطأ المتكرر نفسه، فيُمسك هنا.
    """
    from athera_api.services.planning.context import ROLE_BY_FIELD
    from athera_api.services.workspace import BRAIN_FIELDS

    known = set(ROLE_BY_FIELD.values())
    for key, label_ar, _label_en, roles in BRAIN_FIELDS:
        assert roles, f"{key} names no role at all"
        assert label_ar.strip(), f"{key} has no Arabic label"
        for role in roles:
            assert role in known, (
                f"«{key}» يشير إلى الدور {role!r} وليس له وجود في ROLE_BY_FIELD — "
                "فالعنصر ميت لا يمكن أن يُعرف أبدًا")


def test_brain_keys_are_unique():
    from athera_api.services.workspace import BRAIN_FIELDS

    keys = [key for key, _a, _e, _r in BRAIN_FIELDS]
    assert len(keys) == len(set(keys))


def test_impact_is_measured_inside_the_project_not_across_the_tenant():
    """`project_id` وسيطٌ يجب أن يُستعمل — لا أن يُستقبل ويُهمل.

    وأول صياغة عدّت الادعاءات والأقسام في المستأجر كله، فكان ملفٌّ يُمنع من
    الإزالة بحجّة ورقةٍ في بحثٍ آخر. **وحارسٌ يعاقب على ما لم يقع يُعطَّل ثم
    لا يحرس شيئًا.**
    """
    import inspect

    from athera_api.services import workspace

    source = inspect.getsource(workspace.file_impact)
    assert "Claim.project_id == project_id" in source
    assert "Manuscript.project_id == project_id" in source


def test_impact_summary_says_nothing_depends_when_nothing_does():
    from athera_api.services.workspace import Consequence, Impact

    empty = Impact()
    assert empty.is_safe and not empty.breaks_approved_work
    assert "لا يعتمد" in empty.summary_ar()

    loaded = Impact(consequences=[
        Consequence("approved_sections", 2, "قسمًا معتمَدًا", "approved sections",
                    breaks_approved_work=True)])
    assert not loaded.is_safe and loaded.breaks_approved_work
    assert "2 قسمًا معتمَدًا" in loaded.summary_ar()


def test_every_link_state_the_code_writes_is_permitted_by_the_migration():
    """**عيبٌ كشفه الإنتاج**: الموجّه كتب `"removed"` والقيد لا يعرفها.

    فكانت كل إزالةِ ملفٍّ من بحثٍ تُنتج 500 على الخادم الحيّ — والاختبارات
    المحلية لم تمسّها لأنها لم تُنفِّذ المسار على قاعدة. وهو الخطأ المتكرر:
    مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

    فيُقابَل ما يكتبه الشيفرة بما يسمح به الترحيل — نصًّا بنصّ.
    """
    import inspect
    import re

    from athera_api.models.portfolio import ProjectFile
    from athera_api.routers import workspace as router
    from athera_api.services import workspace as service

    migration = (pathlib.Path(__file__).resolve().parents[3] / "infra" / "db"
                 / "migrations" / "versions" / "0020_project_workspace.py"
                 ).read_text(encoding="utf-8")
    allowed = set(re.search(r"LINK_STATES = \(([^)]*)\)", migration).group(1)
                  .replace('"', "").replace("'", "").replace(" ", "").strip(",").split(","))

    assert set(ProjectFile.STATES) == allowed, (
        f"مفردات النموذج {set(ProjectFile.STATES)} تخالف قيد الترحيل {allowed}")

    # ولا يُكتب سلسلةُ حالٍ حرفية في الموجّه أو الخدمة — تُشتقّ من النموذج.
    for module in (router, service):
        source = inspect.getsource(module)
        for literal in re.findall(r'(?:link|existing)\.state = "([^"]+)"', source):
            assert literal in allowed, (
                f"{module.__name__} يكتب الحال {literal!r} ولا يقبلها القيد")


def test_project_creation_asks_for_a_title_and_nothing_more():
    """الاستمارةُ قبل الفكرة توقف الباحث عند الباب."""
    from athera_api.schemas.workspace import ProjectCreateRequest

    payload = ProjectCreateRequest(title_ar="أثر برنامج في التفكير الناقد")
    assert payload.starting_from == "idea"

    with pytest.raises(ValueError):
        ProjectCreateRequest(title_ar="أ")


def test_source_use_states_are_the_three_named_ones():
    from athera_api.schemas.workspace import SourceUseRequest

    for state in ("included", "saved_only", "excluded"):
        assert SourceUseRequest(use_state=state).use_state == state
    with pytest.raises(ValueError):
        SourceUseRequest(use_state="maybe")


def test_workspace_error_codes_all_have_translations():
    """رسالةٌ بلا ترجمة تصل الباحث مفتاحًا تقنيًّا — وهو ليس رسالة."""
    import inspect

    from athera_api.i18n.catalog import CATALOG
    from athera_api.routers import workspace as router

    source = inspect.getsource(router)
    referenced = {
        line.split('"')[1]
        for line in source.splitlines()
        if '"workspace.' in line and "raise" in line or '("workspace.' in line
    }
    referenced = {code for code in referenced if code.startswith("workspace.")}
    assert referenced, "no workspace error codes were found to check"
    missing = sorted(code for code in referenced if code not in CATALOG)
    assert not missing, f"error codes with no translation: {missing}"


# ──────────────────────── اختبارات تمسّ القاعدة ────────────────────────

async def _seed_file(tid: uuid.UUID, uid: uuid.UUID, name: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.files import File

    async with tenant_session(tid, uid) as session:
        file = File(
            tenant_id=tid, storage_key=f"t/{uuid.uuid4()}", original_filename=name,
            content_type="application/pdf", size_bytes=1024,
            checksum_sha256="0" * 64, classification="C2", status="stored",
            uploaded_by=uid)
        session.add(file)
        await session.flush()
        return file.id


async def _seed_project(tid: uuid.UUID, title: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid) as session:
        project = ResearchProject(
            tenant_id=tid, working_title_ar=title, status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        return project.id


@requires_db
@pytest.mark.asyncio
async def test_project_file_link_is_invisible_to_the_other_tenant(two_tenants):
    """جدول الربط الجديد يخضع لـRLS مثل غيره — لا استثناء لجدولٍ حديث."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile

    a, b = two_tenants["a"], two_tenants["b"]
    project_a = await _seed_project(a["tenant_id"], "بحث المستأجر أ")
    file_a = await _seed_file(a["tenant_id"], a["user_id"], "أ.pdf")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(ProjectFile(
            tenant_id=a["tenant_id"], project_id=project_a, file_id=file_a,
            state="active", added_by=a["user_id"]))

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        rows = (await session.execute(select(ProjectFile))).scalars().all()
        assert all(row.project_id != project_a for row in rows)
        direct = (await session.execute(
            select(ProjectFile).where(ProjectFile.project_id == project_a)
        )).scalars().all()
        assert direct == [], "ربط ملفات مستأجرٍ ظهر لمستأجر آخر"


@requires_db
@pytest.mark.asyncio
async def test_project_source_link_is_invisible_to_the_other_tenant(two_tenants):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.literature import Source
    from athera_api.models.portfolio import ProjectSource

    a, b = two_tenants["a"], two_tenants["b"]
    project_a = await _seed_project(a["tenant_id"], "بحث فيه مراجع")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        source = Source(tenant_id=a["tenant_id"], title="مرجع سرّي",
                        publication_year=2024, retraction_status="unknown")
        session.add(source)
        await session.flush()
        session.add(ProjectSource(
            tenant_id=a["tenant_id"], project_id=project_a, source_id=source.id,
            added_by=a["user_id"]))
        await session.flush()
        source_a = source.id

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        leaked = (await session.execute(
            select(ProjectSource).where(ProjectSource.source_id == source_a)
        )).scalars().all()
        assert leaked == []


@requires_db
@pytest.mark.asyncio
async def test_an_imported_source_is_saved_only_until_the_researcher_decides(two_tenants):
    """**الاستيراد ليس حكمًا بالصلاحية دليلًا.**

    وجعلُ كل مستورَدٍ «مُدرَجًا» افتراضًا يبني ورقةً على ما لم يقرأه أحد.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.literature import Source
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث المراجع الافتراضية")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        source = Source(tenant_id=a["tenant_id"], title="مرجع مستورَد",
                        retraction_status="unknown")
        session.add(source)
        await session.flush()
        # لا يُمرَّر `use_state` إطلاقًا — القاعدة هي التي تقرّر الافتراض.
        session.add(ProjectSource(
            tenant_id=a["tenant_id"], project_id=project, source_id=source.id,
            added_by=a["user_id"]))
        await session.flush()
        link = (await session.execute(
            select(ProjectSource).where(ProjectSource.source_id == source.id)
        )).scalar_one()
        assert link.use_state == "saved_only"
        assert link.decided_by is None and link.decided_at is None


@requires_db
@pytest.mark.asyncio
async def test_including_a_source_requires_a_named_decider(two_tenants):
    """قرارٌ صريح بلا فاعل يُرفض — القيد في القاعدة لا في الواجهة وحدها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.literature import Source
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث القرار المنسوب")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            source = Source(tenant_id=a["tenant_id"], title="مرجع بلا قرار",
                            retraction_status="unknown")
            session.add(source)
            await session.flush()
            session.add(ProjectSource(
                tenant_id=a["tenant_id"], project_id=project, source_id=source.id,
                use_state="included", added_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_trashed_project_is_gone_from_every_listing(two_tenants):
    """الحذف الذي يُخفي في شاشة ويُبقي في أخرى يجعل الحذف كذبًا."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.services.workspace import live_project

    a = two_tenants["a"]
    project_id = await _seed_project(a["tenant_id"], "بحثٌ سيُحذف")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        assert await live_project(
            session, tenant_id=a["tenant_id"], project_id=project_id) is not None
        row = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one()
        row.deleted_at, row.deleted_by = _now(), a["user_id"]

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        assert await live_project(
            session, tenant_id=a["tenant_id"], project_id=project_id) is None
        # ولا يُتلَف: الصف باقٍ كاملًا، والاستعادة ترجعه كما كان.
        still_there = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one()
        assert still_there.working_title_ar == "بحثٌ سيُحذف"
        assert still_there.deleted_by == a["user_id"]


@requires_db
@pytest.mark.asyncio
async def test_trashing_a_project_requires_naming_who_did_it(two_tenants):
    """`deleted_at` بلا `deleted_by` حذفٌ بلا صاحب — يرفضه القيد."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    a = two_tenants["a"]
    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(ResearchProject(
                tenant_id=a["tenant_id"], working_title_ar="حذفٌ بلا صاحب",
                status="planned", deleted_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_the_same_file_may_serve_two_projects(two_tenants):
    """ملفٌ واحد يخدم بحثين — وهو سبب اختيار جدول ربطٍ لا عمود."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile

    a = two_tenants["a"]
    one = await _seed_project(a["tenant_id"], "بحث أول")
    two = await _seed_project(a["tenant_id"], "بحث ثانٍ")
    file_id = await _seed_file(a["tenant_id"], a["user_id"], "بياناتٌ مشتركة.csv")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        for project_id in (one, two):
            session.add(ProjectFile(
                tenant_id=a["tenant_id"], project_id=project_id, file_id=file_id,
                state="active", added_by=a["user_id"]))
        await session.flush()
        count = (await session.execute(
            select(func.count(ProjectFile.id)).where(ProjectFile.file_id == file_id)
        )).scalar_one()
        assert count == 2, "الملف الواحد لم يُقبل في بحثين — فرضنا نسخًا"


@requires_db
@pytest.mark.asyncio
async def test_a_file_cannot_be_linked_to_one_project_twice(two_tenants):
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile

    a = two_tenants["a"]
    project_id = await _seed_project(a["tenant_id"], "بحثٌ لا يقبل التكرار")
    file_id = await _seed_file(a["tenant_id"], a["user_id"], "مكرَّر.pdf")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            for _ in range(2):
                session.add(ProjectFile(
                    tenant_id=a["tenant_id"], project_id=project_id, file_id=file_id,
                    state="active", added_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_removing_a_file_from_a_project_never_deletes_the_file(two_tenants):
    """`RESTRICT` عمدًا: الإزالة من بحثٍ ليست حذفًا من المكتبة."""
    from sqlalchemy import delete, select

    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.portfolio import ProjectFile

    a = two_tenants["a"]
    project_id = await _seed_project(a["tenant_id"], "بحثٌ يُزال منه ملف")
    file_id = await _seed_file(a["tenant_id"], a["user_id"], "باقٍ.pdf")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(ProjectFile(
            tenant_id=a["tenant_id"], project_id=project_id, file_id=file_id,
            state="active", added_by=a["user_id"]))

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await session.execute(
            delete(ProjectFile).where(ProjectFile.file_id == file_id))

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        survivor = (await session.execute(
            select(File).where(File.id == file_id))).scalar_one_or_none()
        assert survivor is not None, "إزالة الملف من بحثٍ حذفته من المكتبة"


@requires_db
@pytest.mark.asyncio
async def test_next_action_starts_by_asking_for_a_document(two_tenants):
    """بحثٌ بلا أدلة لا يُقال له «اكتب المناقشة» — نصيحةٌ لا تُنفَّذ."""
    from athera_api.db import tenant_session
    from athera_api.services.workspace import next_action

    a = two_tenants["a"]
    project_id = await _seed_project(a["tenant_id"], "بحثٌ في أوله")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        action = await next_action(
            session, tenant_id=a["tenant_id"], project_id=project_id)
    assert action is not None and action[0] == "add_document"


@requires_db
@pytest.mark.asyncio
async def test_research_brain_reports_missing_without_inventing_a_percentage(two_tenants):
    """بحثٌ في أوله لا يعرف نتائجه — وقولُ ذلك أصدق من شريطٍ يقول «٤٠٪»."""
    from athera_api.db import tenant_session
    from athera_api.services.workspace import BRAIN_FIELDS, research_brain

    a = two_tenants["a"]
    project_id = await _seed_project(a["tenant_id"], "بحثٌ فارغ")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        brain = await research_brain(
            session, tenant_id=a["tenant_id"], project_id=project_id)

    assert len(brain) == len(BRAIN_FIELDS)
    assert {entry.state for entry in brain} <= {"known", "needs_review",
                                                "missing", "conflicting"}
    assert all(entry.label_ar for entry in brain)


@requires_db
@pytest.mark.asyncio
async def test_one_project_never_shows_another_projects_knowledge(two_tenants):
    """**ولا يُبحث في بحثٍ آخر بصمت.**

    `researcher_memories` لا تحمل `project_id`، فقراءة ذاكرة المستأجر كلها
    تجعل دماغ بحثٍ يعرض معرفةً استُخرجت من بحثٍ غيره — والباحث لا يرى
    الفرق، فيبني على ما ليس من بحثه.
    """
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectFile
    from athera_api.models.research import (
        DocumentChunk,
        ExtractionRun,
        FactCandidate,
        ResearcherMemory,
    )
    from athera_api.services.workspace import research_brain

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    owner = await _seed_project(tid, "البحث صاحب المعرفة")
    stranger = await _seed_project(tid, "بحثٌ لا يملك شيئًا")
    file_id = await _seed_file(tid, uid, "أدلّة.pdf")

    async with tenant_session(tid, uid) as session:
        session.add(ProjectFile(tenant_id=tid, project_id=owner, file_id=file_id,
                                state="active", added_by=uid))
        memory = ResearcherMemory(
            tenant_id=tid, memory_category="verified_evidence",
            statement_ar="المنهج شبه تجريبي بمجموعتين",
            source_type="upload", source_file_id=file_id,
            source_locator="p.4", source_quote="المنهج شبه تجريبي بمجموعتين",
            verification_status="verified", verified_by=uid, verified_at=_now())
        session.add(memory)
        chunk = DocumentChunk(tenant_id=tid, file_id=file_id, seq=0,
                              text="المنهج شبه تجريبي بمجموعتين",
                              locator="p.4", char_count=29)
        session.add(chunk)
        run = ExtractionRun(tenant_id=tid, file_id=file_id, extractor="rules",
                            status="succeeded", started_at=_now())
        session.add(run)
        await session.flush()
        session.add(FactCandidate(
            tenant_id=tid, extraction_run_id=run.id, file_id=file_id,
            chunk_id=chunk.id, memory_category="verified_evidence",
            field_key="design",
            statement_ar="المنهج شبه تجريبي بمجموعتين",
            quote="المنهج شبه تجريبي بمجموعتين", locator="p.4",
            status="approved", decided_by=uid, decided_at=_now(),
            resulting_memory_id=memory.id))
        await session.flush()

    async with tenant_session(tid, uid) as session:
        mine = await research_brain(session, tenant_id=tid, project_id=owner)
        theirs = await research_brain(session, tenant_id=tid, project_id=stranger)

    method_mine = next(e for e in mine if e.key == "method")
    method_theirs = next(e for e in theirs if e.key == "method")
    assert method_mine.state == "known", "البحث المالك لا يرى معرفته"
    assert method_theirs.state == "missing", (
        "بحثٌ آخر رأى معرفةً ليست من ملفاته — البحث الصامت في بحثٍ غيره")
