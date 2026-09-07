"""جسرُ المعرفة المعتمَدة | Reviewed knowledge feeds opportunity mining.

**العطبُ الذي تحرسه هذه الفحوص.** رسالةٌ تُرفع عبر الخطّ الحديث تُنتج
`FactCandidate`؛ يراجعها الباحثُ ويعتمدها فتصير ذاكرةً موثقة. وكان المنقّبُ
يقرأ `ThesisSection` و`ThesisResult` وحدهما — جدولان لا يكتبهما ذلك الخطّ.
فيُجاب الباحثُ بصفرٍ صامت مهما راجع واعتمد.

**ولا يُهنَّأ الجسرُ بأنّه لم ينكسر.** كلُّ فحصٍ هنا يقيس واقعةً: أنّ فرصةً
نشأت من معرفةٍ اعتمدها إنسان، وأنّ ما لم يُعتمد لم يدخل، وأنّ ذاكرةَ ملفٍّ
آخر لا تُغذّي هذه الرسالة، وأنّ عنوانًا كتبه الباحثُ بيده لا يُستبدل.
"""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from tests.conftest import requires_db

# ═════════ نصوصٌ تركيبية — لا محتوى بحثٍ حقيقيّ ═════════

TITLE = "أثر القيادة التحويلية على الرضا الوظيفي"
QUESTION_ONE = "ما أثر القيادة التحويلية على الرضا الوظيفي لدى المعلمين؟"
QUESTION_TWO = "ما الفروق في الرضا الوظيفي تبعًا لسنوات الخبرة؟"
FINDING = "توصلت الدراسة إلى وجود أثر دال للقيادة التحويلية على الرضا الوظيفي"
NULL_FINDING = "لم تكن الفروق في الرضا الوظيفي تبعًا للجنس دالة إحصائيًا"
CONSTRUCT_ONE = "القيادة التحويلية"
CONSTRUCT_TWO = "الرضا الوظيفي"
POPULATION = "معلمو المرحلة الثانوية بمدينة الرياض"
REJECTED_TEXT = "استنتاجٌ رفضه الباحث ولا يجوز أن يصل المنقّب"
UNVERIFIED_TEXT = "استخراجٌ لم يعرضه أحدٌ على الباحث بعد"


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    """**لا MinIO في CI، ولا يُدَّعى وجودُه.**

    وهذه الحزمة سقطت بها ثمانيَ مرّات: المزوّدُ الافتراضي `s3` يقصد
    `localhost:9000`، فتُرفض الوصلة ويُقرأ `EndpointConnectionError` عطبَ
    منتج — وهو عطبُ تجهيزة. والمزوّدُ الذاكريّ هو ما تستعمله الحزمُ القائمة
    (`test_at_thesis_center_stabilization.py`)، فيُستعمل هنا كما هو.
    """
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


def _client(tenant_id, user_id, locale="ar"):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": locale})


async def _file(session, tenant_id, user_id, filename):
    """ملفٌّ بمِنحته — كما يكتبهما الرفعُ معًا."""
    from athera_api.models.files import File
    from athera_api.models.identity import ObjectGrant
    from athera_api.services import storage

    record = File(
        tenant_id=tenant_id,
        storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/{filename}",
        original_filename=filename, content_type="application/pdf",
        size_bytes=2048, status="stored", uploaded_by=user_id)
    session.add(record)
    await session.flush()
    session.add(ObjectGrant(
        tenant_id=tenant_id, object_type="file", object_id=record.id,
        user_id=user_id, grant_level="owner", granted_by=user_id))
    storage.get_store().put(record.storage_key, b"%PDF-1.4 synthetic", "application/pdf")
    return record


async def _seed(tenant_id, user_id, *, title_ar=None, filename="رسالة.pdf"):
    """رسالةٌ حديثة: ملفٌّ وتشغيلةُ استخراج — بلا صفٍّ قديم واحد."""
    from athera_api.db import tenant_session
    from athera_api.models.research import ExtractionRun
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing

    async with tenant_session(tenant_id, user_id) as session:
        record = await _file(session, tenant_id, user_id, filename)
        thesis = Thesis(tenant_id=tenant_id, file_id=record.id, title_ar=title_ar,
                        degree=None, processing_state=processing.READY_FOR_REVIEW)
        session.add(thesis)
        run = ExtractionRun(tenant_id=tenant_id, file_id=record.id, extractor="model",
                            status="succeeded", started_at=dt.datetime.now(dt.UTC))
        session.add(run)
        await session.flush()
        return thesis.id, record.id, run.id


async def _chunk(session, tenant_id, file_id, text, seq=1):
    from athera_api.models.research import DocumentChunk

    chunk = DocumentChunk(
        tenant_id=tenant_id, file_id=file_id, seq=seq, text=text,
        locator=f"p.{seq}", page_number=seq, char_count=len(text))
    session.add(chunk)
    await session.flush()
    return chunk


async def _candidate(session, tenant_id, *, run_id, file_id, chunk, field_key,
                     value, category="project_decision", status="unverified"):
    """مرشّحٌ بالشكل الذي يكتبه خطُّ المستندات — `{"value": …}` وقيمتُه `Any`."""
    from athera_api.models.research import FactCandidate

    candidate = FactCandidate(
        tenant_id=tenant_id, extraction_run_id=run_id, file_id=file_id,
        chunk_id=chunk.id, memory_category=category, field_key=field_key,
        statement_ar=str(value),
        value={"value": value, "extraction_status": "extracted"},
        quote=chunk.text[:400], locator=chunk.locator, confidence=0.9, status=status)
    session.add(candidate)
    await session.flush()
    return candidate


async def _approve(session, tenant_id, user_id, candidate_id):
    """**المسارُ الحقيقيّ للاعتماد** — لا ذاكرةٌ تُزرع بيدٍ لتُرضي الفحص."""
    from athera_api.services import memory

    return await memory.approve_candidate(
        session, tenant_id=tenant_id, candidate_id=candidate_id,
        actor_user_id=user_id, reason="reviewed in the acceptance test")


async def _counts(tenant_id, user_id, thesis_id):
    """صفوفُ المعماريّة القديمة — **يجب أن تبقى صفرًا**."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    async with tenant_session(tenant_id, user_id) as session:
        sections = (await session.execute(
            select(func.count(ThesisSection.id))
            .where(ThesisSection.thesis_id == thesis_id))).scalar_one()
        results = (await session.execute(
            select(func.count(ThesisResult.id))
            .where(ThesisResult.thesis_id == thesis_id))).scalar_one()
    return sections, results


async def _reviewed_thesis(tid, uid, *, title_ar=None, with_null_finding=False):
    """رسالةٌ حديثة ومعرفةٌ اعتمدها الباحثُ فعلًا — الحالُ الذهبية."""
    from athera_api.db import tenant_session

    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=title_ar)
    async with tenant_session(tid, uid) as session:
        body = " ".join([TITLE, QUESTION_ONE, QUESTION_TWO, FINDING,
                         NULL_FINDING, CONSTRUCT_ONE, CONSTRUCT_TWO, POPULATION])
        chunk = await _chunk(session, tid, file_id, body)
        findings = [FINDING] + ([NULL_FINDING] if with_null_finding else [])
        made = []
        for key, value, category in (
            ("title_ar", TITLE, "researcher_fact"),
            ("questions", [QUESTION_ONE, QUESTION_TWO], "project_decision"),
            ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO], "project_decision"),
            ("primary_findings", findings, "verified_evidence"),
            ("population", POPULATION, "project_decision"),
        ):
            made.append(await _candidate(
                session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                field_key=key, value=value, category=category))
        for candidate in made:
            await _approve(session, tid, uid, candidate.id)
    return thesis_id, file_id, run_id


# ═════════ ١ · المسارُ الذهبيّ الحديث ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_modern_thesis_mines_from_reviewed_knowledge_and_writes_no_legacy_row(
        two_tenants):
    """**الواقعةُ التي لم تكن تقع.** رسالةٌ حديثة، معرفةٌ معتمَدة، فرصٌ تنشأ.

    ولا صفَّ `ThesisSection` ولا `ThesisResult` يُكتب: الجسرُ محوِّلُ قراءةٍ
    لا ناسخُ معرفةٍ بين معماريّتين.
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file_id, _run = await _reviewed_thesis(tid, uid)

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["opportunities_created"] > 0, "معرفةٌ اعتُمدت ولم تُنتج فرصة — الجسر لا يعمل"
    assert body["evidence_basis"] == "canonical"
    assert body["approved_facts_used"] > 0
    assert body["outcome"] == "opportunities_created"

    sections, results = await _counts(tid, uid, thesis_id)
    assert sections == 0, "الجسرُ نسخ معرفةً إلى الجدول القديم"
    assert results == 0, "الجسرُ نسخ معرفةً إلى الجدول القديم"


# ═════════ ٢ · الحقول: أُسندت إلى الحقيقة المعتمَدة ═════════


@requires_db
@pytest.mark.asyncio
async def test_the_opportunity_is_grounded_in_the_approved_facts(two_tenants):
    """السؤالُ سؤالٌ اعتُمد، والمراجعُ معرّفاتُ حقائقَ حقيقية."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research import FactCandidate
    from athera_api.models.thesis import PublicationOpportunity

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _reviewed_thesis(tid, uid)

    async with _client(tid, uid) as client:
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202

    async with tenant_session(tid, uid) as session:
        rows = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().all()
        approved_ids = {str(cid) for cid in (await session.execute(
            select(FactCandidate.id).where(
                FactCandidate.file_id == file_id,
                FactCandidate.status == "approved"))).scalars().all()}

    assert rows, "لا فرص"
    for row in rows:
        assert row.thesis_id == thesis_id
        for ref in (row.result_refs or []):
            assert ref in approved_ids, "مرجعُ نتيجةٍ لا يعود إلى حقيقةٍ معتمَدة"
        for ref in (row.sample_refs or []):
            assert ref in approved_ids, "مرجعُ عيّنةٍ لا يعود إلى حقيقةٍ معتمَدة"
            assert ref != str(thesis_id), "معرّفُ الرسالة انتحل هويّةَ عيّنة"

    questioned = [r for r in rows if r.research_question_ar]
    assert questioned, "لم تنشأ فرصةٌ من سؤال"
    assert all(r.research_question_ar in {QUESTION_ONE, QUESTION_TWO} for r in questioned)
    variables = {v for r in rows for v in (r.variable_refs or [])}
    assert variables <= {CONSTRUCT_ONE, CONSTRUCT_TWO}
    assert variables, "لم يصل بناءٌ معتمَد إلى الفرص"

    blob = " ".join(
        f"{r.working_title_ar} {r.research_question_ar or ''}" for r in rows)
    assert REJECTED_TEXT not in blob
    assert UNVERIFIED_TEXT not in blob


# ═════════ ٣ · ما لم يُعتمد لا يدخل ═════════


@requires_db
@pytest.mark.asyncio
async def test_only_approved_facts_reach_the_miner(two_tenants):
    """معتمَدٌ ومرفوضٌ وغيرُ مراجَع — ولا يمرّ إلّا الأول."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        body = " ".join([QUESTION_ONE, REJECTED_TEXT, UNVERIFIED_TEXT, FINDING])
        chunk = await _chunk(session, tid, file_id, body)
        good = await _candidate(session, tid, run_id=run_id, file_id=file_id,
                                chunk=chunk, field_key="questions", value=[QUESTION_ONE])
        await _approve(session, tid, uid, good.id)
        rejected = await _candidate(session, tid, run_id=run_id, file_id=file_id,
                                    chunk=chunk, field_key="questions",
                                    value=[REJECTED_TEXT])
        rejected.status = "rejected"
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="questions", value=[UNVERIFIED_TEXT])

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.facts.questions == (QUESTION_ONE,)
    assert REJECTED_TEXT not in evidence.facts.questions
    assert UNVERIFIED_TEXT not in evidence.facts.questions


@requires_db
@pytest.mark.asyncio
async def test_a_verified_memory_from_another_file_cannot_feed_this_thesis(two_tenants):
    """**الرابطةُ معرّفُ ملفّ، لا مشابهةُ نصّ.** ذاكرةُ ملفٍّ آخر لا تدخل."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _seed(tid, uid, filename="هذه.pdf")
    _other_thesis, other_file, other_run = await _seed(tid, uid, filename="أخرى.pdf")

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, other_file, QUESTION_ONE)
        candidate = await _candidate(session, tid, run_id=other_run, file_id=other_file,
                                     chunk=chunk, field_key="questions",
                                     value=[QUESTION_ONE])
        await _approve(session, tid, uid, candidate.id)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.approved_facts_used == 0, "ذاكرةُ ملفٍّ آخر عبرت إلى هذه الرسالة"
    assert evidence.has_evidence is False


# ═════════ ٤ · العنوان: يُملأ الفراغ ولا يُستبدل المكتوب ═════════


@requires_db
@pytest.mark.asyncio
async def test_an_approved_title_fills_an_empty_title(two_tenants):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _reviewed_thesis(tid, uid, title_ar=None)

    async with _client(tid, uid) as client:
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202

    async with tenant_session(tid, uid) as session:
        title = (await session.execute(
            select(Thesis.title_ar).where(Thesis.id == thesis_id))).scalar_one()
    assert title == TITLE


@requires_db
@pytest.mark.asyncio
async def test_a_title_the_researcher_wrote_is_never_silently_replaced(two_tenants):
    """**اعتمادُ حقيقةٍ ليس إذنًا بهدم ما أدخله الباحث.**"""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    mine = "عنوانٌ كتبه الباحث بيده"
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _reviewed_thesis(tid, uid, title_ar=mine)

    async with _client(tid, uid) as client:
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202

    async with tenant_session(tid, uid) as session:
        title = (await session.execute(
            select(Thesis.title_ar).where(Thesis.id == thesis_id))).scalar_one()
    assert title == mine, "عنوانُ الباحث استُبدل باستخراجٍ اعتُمد"


# ═════════ ٥ · الصفرُ الصامت انقسم إلى خبرين ═════════


@requires_db
@pytest.mark.asyncio
async def test_extracted_but_unreviewed_candidates_do_not_mine_and_say_so(two_tenants):
    """استخراجٌ بلا مراجعة لا يُنقّب — **ويُقال السببُ باسمه**."""
    from athera_api.db import tenant_session

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)
    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, " ".join([QUESTION_ONE, FINDING]))
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="questions", value=[QUESTION_ONE])

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["evidence_basis"] == "none"
    assert body["outcome"] == "no_reviewed_canonical_evidence"
    assert body["approved_facts_used"] == 0


# ═════════ ٦ · المسارُ القديم كما كان ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_thesis_with_only_legacy_evidence_still_mines_as_before(two_tenants):
    """**ولا يُكسر ما كان يعمل.** لا معرفةَ معتمَدة، وأقسامٌ قديمة قائمة."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file_id, _run = await _seed(tid, uid, title_ar=TITLE)

    async with tenant_session(tid, uid) as session:
        session.add(ThesisSection(
            tenant_id=tid, thesis_id=thesis_id, section_key="questions",
            content_ar=QUESTION_ONE, locator="p.1", quote=QUESTION_ONE[:200],
            verification_status="unverified"))
        session.add(ThesisResult(
            tenant_id=tid, thesis_id=thesis_id, label_ar=FINDING,
            variables=[CONSTRUCT_ONE, CONSTRUCT_TWO], is_published=False))

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] > 0, "المسارُ القديم انكسر"
    assert body["evidence_basis"] == "legacy"
    assert body["approved_facts_used"] == 0


# ═════════ ٧ · تطبيعُ القيمة — بلا قاعدة بيانات ═════════


def _fake(value, statement="عبارةٌ معتمَدة"):
    class _C:
        pass

    candidate = _C()
    candidate.value = value
    candidate.statement_ar = statement
    return candidate


def test_multi_valued_facts_are_read_as_items_and_prose_is_never_split():
    """**ولا يُشطر نثرٌ لتكثر المقترحات.** جملةٌ واحدة تبقى واحدة."""
    from athera_api.services.thesis import canonical_facts

    assert canonical_facts._texts(_fake({"value": ["أ", "ب"]})) == ["أ", "ب"]
    prose = "السؤال الأول. السؤال الثاني؛ والثالث"
    assert canonical_facts._texts(_fake({"value": prose})) == [prose]
    assert canonical_facts._texts(_fake({"value": 42})) == ["42"]
    assert canonical_facts._texts(_fake({"value": None}, "عبارة")) == ["عبارة"]
    assert canonical_facts._texts(_fake(None, "عبارة")) == ["عبارة"]
    assert canonical_facts._texts(_fake({"value": ["", "  "]}, "")) == []
    # عنصرٌ ليس نصًّا ولا رقمًا يُترك ولا يُخمَّن له تمثيل.
    assert canonical_facts._texts(_fake({"value": [{"x": 1}, "ب"]})) == ["ب"]


def test_a_null_result_is_only_counted_when_the_fact_says_so():
    """**الغيابُ ليس نفيًا** — ولا تُعدّ نتيجةٌ سالبةً بلا تصريح."""
    from athera_api.services.thesis import canonical_facts

    assert canonical_facts._NULL_RESULT_MARKERS.search(NULL_FINDING)
    assert canonical_facts._NULL_RESULT_MARKERS.search("no significant difference")
    assert not canonical_facts._NULL_RESULT_MARKERS.search(FINDING)
    assert not canonical_facts._NULL_RESULT_MARKERS.search("نتيجةٌ لم تُذكر دلالتها")
