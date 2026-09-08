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
#: عنوانٌ **لا يطابق أيَّ علامةٍ في المنقّب** — لا محددات ولا آثار ولا مقارنة.
#: فتُفحص حالُ «دليلٌ قائم ولا فرصة» بلا أن يصنعها العنوانُ من نفسه.
NEUTRAL_TITLE = "واقع ممارسات التدريس في المرحلة الابتدائية"
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


async def _seed(tenant_id, user_id, *, title_ar=None, filename="رسالة.pdf",
                run_status="awaiting_review"):
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
        # **حالٌ يكتبها خطُّ المعالجة فعلًا.** كان هنا `"succeeded"` ولا
        # كاتبَ له في التطبيق كلّه — فكانت الفحوصُ تمرّ خضراءَ على حالٍ لا
        # تقع في الإنتاج، وذاك أسوأُ من فحصٍ ساقط.
        run = ExtractionRun(tenant_id=tenant_id, file_id=record.id, extractor="model",
                            status=run_status,
                            started_at=dt.datetime.now(dt.UTC))
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
                     value, category="project_decision", status="unverified",
                     confidence=0.97, extraction="extracted", quote=None):
    """مرشّحٌ بالشكل الذي يكتبه خطُّ المستندات — `{"value": …}` وقيمتُه `Any`.

    و`extraction_status` **داخل `value`** لا عمودًا، كما يكتبه خطُّ المعالجة
    ويقرؤه `routers/document_intelligence.py`.
    """
    from athera_api.models.research import FactCandidate

    candidate = FactCandidate(
        tenant_id=tenant_id, extraction_run_id=run_id, file_id=file_id,
        chunk_id=chunk.id, memory_category=category, field_key=field_key,
        statement_ar=str(value),
        value={"value": value, "extraction_status": extraction},
        quote=chunk.text[:400] if quote is None else quote,
        locator=chunk.locator, confidence=confidence, status=status)
    session.add(candidate)
    await session.flush()
    return candidate


async def _machine_thesis(tid, uid, *, title_ar=None, confidence=0.97,
                          extra=(), filename="آليّة.pdf"):
    """رسالةٌ حديثة بحقائقَ **آليّةٍ لم يعتمدها أحد** — الحالُ الجديدة.

    ولا `approve_candidate`، ولا `ResearcherMemory`: هذا بالضبط ما صار
    مؤهَّلًا للتنقيب بعد تحوّل السياسة.
    """
    from athera_api.db import tenant_session

    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=title_ar,
                                             filename=filename)
    async with tenant_session(tid, uid) as session:
        body = " ".join([TITLE, QUESTION_ONE, QUESTION_TWO, FINDING,
                         CONSTRUCT_ONE, CONSTRUCT_TWO, POPULATION])
        chunk = await _chunk(session, tid, file_id, body)
        for key, value, category in (
            ("title_ar", TITLE, "researcher_fact"),
            ("questions", [QUESTION_ONE, QUESTION_TWO], "project_decision"),
            ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO], "project_decision"),
            ("primary_findings", [FINDING], "verified_evidence"),
        ):
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key=key, value=value,
                             category=category, confidence=confidence)
        for key, value, conf in extra:
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key=key, value=value,
                             confidence=conf)
    return thesis_id, file_id, run_id


async def _approve(session, tenant_id, user_id, candidate_id):
    """**المسارُ الحقيقيّ للاعتماد** — لا ذاكرةٌ تُزرع بيدٍ لتُرضي الفحص."""
    from athera_api.services import memory

    return await memory.approve_candidate(
        session, tenant_id=tenant_id, candidate_id=candidate_id,
        actor_user_id=user_id, reason="reviewed in the acceptance test")


async def _mark_unknown(session, tenant_id, user_id, candidate_id):
    """«لا أعرف» قرارٌ ثالث **له فاعل** — والقاعدة تفرضه كما تفرضه للرفض."""
    from athera_api.services import memory

    return await memory.mark_candidate_unknown(
        session, tenant_id=tenant_id, candidate_id=candidate_id,
        actor_user_id=user_id, reason="undecided in the acceptance test")


async def _reject(session, tenant_id, user_id, candidate_id):
    """**والرفضُ بمساره أيضًا** — لا بكتابة عمودٍ بيد."""
    from athera_api.services import memory

    return await memory.reject_candidate(
        session, tenant_id=tenant_id, candidate_id=candidate_id,
        actor_user_id=user_id, reason="rejected in the acceptance test")


async def _card(tenant_id, user_id, thesis_id, locale="ar"):
    """صفُّ البطاقة كما تقرؤه الشاشة — **هناك تظهر الكذبة إن ظهرت**."""
    async with _client(tenant_id, user_id, locale=locale) as client:
        rows = (await client.get("/api/v1/theses")).json()
    return next(row for row in rows if row["id"] == str(thesis_id))


async def _mined_at(tenant_id, user_id, thesis_id):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis

    async with tenant_session(tenant_id, user_id) as session:
        return (await session.execute(
            select(Thesis.opportunities_mined_at)
            .where(Thesis.id == thesis_id))).scalar_one()


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
async def test_human_decisions_outrank_every_automatic_rule(two_tenants):
    """**قرارُ الإنسان يسبق كلَّ حسابٍ آليّ** — ولو بلغت الثقةُ ذروتها.

    `rejected` تُستبعد، و`unknown` تُحال إلى المراجعة، وعاليةُ الثقة التي لم
    يمسَّها أحد تمرّ. وهذا هو تحوّلُ السياسة: الباحثُ يعتمد القراراتِ
    العلمية، لا كلَّ استخراجٍ وسيط.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts, fact_eligibility

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        body = " ".join([QUESTION_ONE, REJECTED_TEXT, UNVERIFIED_TEXT])
        chunk = await _chunk(session, tid, file_id, body)
        untouched = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[QUESTION_ONE], confidence=0.97)
        refused = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[REJECTED_TEXT], confidence=0.99)
        await _reject(session, tid, uid, refused.id)
        unsure = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[UNVERIFIED_TEXT], confidence=0.99)
        # **ولا يُكتب العمودُ بيد**: القيدُ
        # `ck_fact_candidates_ck_candidate_decided_requires_actor` يفرض فاعلًا،
        # وقرارٌ بلا صاحبٍ حالٌ لا تقع في المنتج.
        await _mark_unknown(session, tid, uid, unsure.id)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.facts.questions == (QUESTION_ONE,)
    assert REJECTED_TEXT not in evidence.facts.questions, "مرفوضٌ عبر بثقةٍ عالية"
    assert UNVERIFIED_TEXT not in evidence.facts.questions, "«غير محسوم» عبر"
    assert evidence.counts.get(fact_eligibility.REVIEW_REQUIRED, 0) >= 1
    assert "rejected_by_researcher" in evidence.reasons
    assert untouched.id and unsure.id  # الصفوفُ باقيةٌ، ولا تاريخَ يُحذف


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

    assert evidence.eligible_facts_used == 0, "ذاكرةُ ملفٍّ آخر عبرت إلى هذه الرسالة"
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
async def test_low_confidence_extraction_does_not_mine_and_says_why(two_tenants):
    """استخراجٌ دون العتبة لا يُنقّب — **ويُقال السببُ باسمه**.

    ولا يُختم `opportunities_mined_at`: البطاقةُ لا تدّعي فحصًا لم يقع على
    دليلٍ مؤهَّل، فتبقى «لم يبدأ استخراج الفرص بعد».
    """
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    # دون كلّ عتبةٍ في الخريطة — ولا تُرفع لأنّ المنقّبَ يشتهي دليلًا.
    thesis_id, _f, _r = await _machine_thesis(tid, uid, confidence=0.40)

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["eligible_facts_used"] == 0
    assert body["outcome"] == "no_eligible_evidence"
    assert await _mined_at(tid, uid, thesis_id) is None, "خُتمت رسالةٌ لم تُفحص"

    for locale, forbidden in (("ar", "اكتمل الفحص"), ("en", "scan completed")):
        card = await _card(tid, uid, thesis_id, locale=locale)
        assert card["opportunities_outcome"] != "completed_empty"
        assert forbidden not in (card["opportunities_outcome_label"] or "")


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


@requires_db
@pytest.mark.asyncio
async def test_legacy_evidence_that_yields_nothing_is_never_called_reviewed(two_tenants):
    """**المادةُ القديمة ليست معرفةً راجعها الباحث** — فلا تُوصف بذلك.

    صفوفُ `ThesisSection`/`ThesisResult` استخراجٌ آليّ، و`verification_status`
    فيها لا يُنقل عن `unverified` في أيّ مسار. فحصيلةٌ تقول
    «اعتُمدت المعرفةُ وفُحصت ولم تنشأ فرصة» ادّعاءُ مراجعةٍ لم تقع.

    والختمُ هنا **يُكتب**: دليلٌ قائمٌ فُحص فعلًا، وإن لم يُنتج شيئًا.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file_id, _run = await _seed(tid, uid, title_ar=NEUTRAL_TITLE)

    async with tenant_session(tid, uid) as session:
        # نتيجةٌ واحدة وبناءان اثنان: دليلٌ قائم، ولا سؤالَ ولا أداةَ ولا
        # ثلاثةُ متغيّرات — فلا يجد المنقّبُ ما يقترحه.
        session.add(ThesisResult(
            tenant_id=tid, thesis_id=thesis_id, label_ar=FINDING,
            variables=[CONSTRUCT_ONE, CONSTRUCT_TWO], is_published=False))

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["evidence_basis"] == "legacy"
    assert body["outcome"] == "legacy_evidence_but_no_opportunity"
    assert body["outcome"] != "eligible_evidence_but_no_opportunity", (
        "وُصفت مادةٌ قديمة بأنّها دليلٌ مؤهَّل حديث"
    )
    assert body["approved_facts_used"] == 0
    assert body["eligible_facts_used"] == 0
    assert await _mined_at(tid, uid, thesis_id) is not None, "فحصٌ وقع ولم يُختم"


@requires_db
@pytest.mark.asyncio
async def test_reviewed_evidence_that_yields_nothing_says_so_and_is_stamped(two_tenants):
    """اعتُمدت معرفةٌ، وفُحصت، ولم تنشأ فرصة — **خبرٌ ثالثٌ قائمٌ بذاته**.

    ويُختم: الفحصُ وقع على دليلٍ حقيقيّ. والبطاقةُ تقول «اكتمل الفحص ولم
    يُعثر على فرصة» — وهي هنا **صادقة**، بخلاف حال «لا دليل».
    """
    from athera_api.db import tenant_session

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=None)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id,
                             " ".join([NEUTRAL_TITLE, POPULATION]))
        for key, value, category in (
            ("title_ar", NEUTRAL_TITLE, "researcher_fact"),
            ("population", POPULATION, "project_decision"),
        ):
            candidate = await _candidate(
                session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                field_key=key, value=value, category=category)
            await _approve(session, tid, uid, candidate.id)

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["evidence_basis"] == "canonical"
    assert body["approved_facts_used"] > 0
    assert body["outcome"] == "eligible_evidence_but_no_opportunity"
    assert await _mined_at(tid, uid, thesis_id) is not None, "فحصٌ حقيقيّ لم يُختم"

    card = await _card(tid, uid, thesis_id)
    assert card["opportunities_outcome"] == "completed_empty"


# ═════════ ٧ · المسارُ الذهبيّ الجديد: بلا اعتمادٍ بشريّ أصلًا ═════════


@requires_db
@pytest.mark.asyncio
async def test_machine_facts_alone_produce_a_grounded_opportunity(two_tenants):
    """**البرهانُ المركزيّ لتحوّل السياسة.**

    رسالةٌ حديثة، حقائقُها `unverified` و`extraction_status=extracted` وعاليةُ
    الثقة ومؤصَّلةُ الاقتباس، وتشغيلتُها مسموحة — **ولا اعتمادَ بشريًّا
    واحدًا**، ولا صفَّ ذاكرةٍ موثقة، ولا صفًّا في الجدولين القديمين. ومع ذلك
    تنشأ فرصةُ نشرٍ مؤصَّلة.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import FactCandidate, ResearcherMemory
    from athera_api.models.thesis import PublicationOpportunity

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _machine_thesis(tid, uid)

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["opportunities_created"] > 0, "حقائقُ آليّةٌ مؤهَّلة لم تُنتج فرصة"
    assert body["evidence_basis"] == "canonical"
    assert body["eligible_facts_used"] > 0
    assert body["approved_facts_used"] == 0, "لا اعتمادَ بشريًّا في هذا المسار"
    assert body["processing_scope"] == "advanced_extraction"

    async with tenant_session(tid, uid) as session:
        memories = (await session.execute(
            select(func.count(ResearcherMemory.id)))).scalar_one()
        approved = (await session.execute(
            select(func.count(FactCandidate.id)).where(
                FactCandidate.file_id == file_id,
                FactCandidate.status == "approved"))).scalar_one()
        rows = (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalars().all()
        fact_ids = {str(cid) for cid in (await session.execute(
            select(FactCandidate.id).where(
                FactCandidate.file_id == file_id))).scalars().all()}

    assert memories == 0, "أُنشئت ذاكرةٌ موثقة — والمسار لا يحتاجها"
    assert approved == 0, "اعتُمدت حقيقةٌ — والمسار لا يحتاج اعتمادًا"
    sections, results = await _counts(tid, uid, thesis_id)
    assert sections == 0 and results == 0, "كُتب صفٌّ في المعماريّة القديمة"

    assert rows, "لا فرص"
    for row in rows:
        for ref in list(row.result_refs or []) + list(row.sample_refs or []):
            assert ref in fact_ids, "مرجعٌ لا يعود إلى حقيقةٍ حقيقية"
            assert ref != str(thesis_id), "معرّفُ الرسالة انتحل هويّةَ عيّنة"


@requires_db
@pytest.mark.asyncio
async def test_confidence_tiers_use_the_real_field_policy(two_tenants):
    """عاليةٌ تُؤهَّل، ومتوسّطةٌ تُعين ولا تُنشئ، ومنخفضةٌ تُستبعد."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts, fact_eligibility

    auto_min, support_min = fact_eligibility.thresholds_for("constructs")
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id,
                             " ".join([CONSTRUCT_ONE, CONSTRUCT_TWO, POPULATION]))
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="constructs", value=[CONSTRUCT_ONE],
                         confidence=auto_min + 0.02)
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="constructs", value=[CONSTRUCT_TWO],
                         confidence=(auto_min + support_min) / 2)
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="population", value=POPULATION,
                         confidence=support_min - 0.30)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.facts.variables == (CONSTRUCT_ONE,)
    assert CONSTRUCT_TWO not in evidence.facts.variables, "متوسّطةُ الثقة أسندت"
    assert evidence.facts.sample_ids == (), "منخفضةُ الثقة أسندت عيّنة"
    assert evidence.counts.get(fact_eligibility.SUPPORT_ONLY, 0) == 1
    assert evidence.counts.get(fact_eligibility.EXCLUDED, 0) >= 1


@requires_db
@pytest.mark.asyncio
async def test_high_confidence_never_buys_past_grounding_or_a_review_flag(two_tenants):
    """**الثقةُ ثقةُ استخراجٍ لا ثقةُ علم.** و`0.99` لا تشتري تجاوزًا."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts, fact_eligibility

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, QUESTION_ONE)
        # اقتباسٌ لا وجود له في المقطع — عطبُ تأصيلٍ لا تشتريه ثقة.
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="questions", value=[QUESTION_ONE],
                         confidence=0.99, quote="عبارةٌ لم ترد في المستند إطلاقًا")
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="hypotheses", value=["فرضٌ غامض"],
                         confidence=0.99, extraction="ambiguous")
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="constructs", value=[CONSTRUCT_ONE],
                         confidence=0.99, extraction="needs_review")

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0
    assert "quote_not_grounded" in evidence.reasons
    assert evidence.counts.get(fact_eligibility.REVIEW_REQUIRED, 0) == 2


@requires_db
@pytest.mark.asyncio
async def test_a_material_conflict_withholds_only_its_own_concept(two_tenants):
    """‏310 مقابل 297 — **يُحجب حجمُ العيّنة وحده**، وتمضي بقيّةُ الأدلّة."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _machine_thesis(
        tid, uid, extra=(("sample_size", "بلغ عدد أفراد العينة 310", 0.97),
                         ("sample_size", "بلغ عدد أفراد العينة 297", 0.97)))

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["conflicts_detected"] == 1
    assert body["facts_withheld_for_conflict"] == 2
    # **ولا تُعطَّل الرسالة**: الأسئلةُ والنتائجُ ما زالت تُنتج فرصًا.
    assert body["opportunities_created"] > 0, "تعارضٌ في مفهومٍ عطّل الرسالة كلَّها"
    assert body["eligible_facts_used"] > 0


@requires_db
@pytest.mark.asyncio
async def test_an_approved_correction_supersedes_a_machine_fact(two_tenants):
    """**الإنسانُ المعتمِد يبطل الآليَّ في المفهوم نفسه** — ولا يُحذف تاريخ."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import FactCandidate
    from athera_api.services.thesis import canonical_facts

    correction = "الالتزام التنظيمي"
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id,
                             " ".join([CONSTRUCT_ONE, correction]))
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="constructs", value=[CONSTRUCT_ONE],
                         confidence=0.99)
        human = await _candidate(session, tid, run_id=run_id, file_id=file_id,
                                 chunk=chunk, field_key="constructs",
                                 value=[correction], confidence=0.80)
        await _approve(session, tid, uid, human.id)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)
        remaining = (await session.execute(
            select(func.count(FactCandidate.id))
            .where(FactCandidate.file_id == file_id))).scalar_one()

    assert evidence.facts.variables == (correction,), evidence.facts.variables
    assert CONSTRUCT_ONE not in evidence.facts.variables, "الآليُّ غلب المعتمَد"
    assert evidence.approved_verified_used == 1
    assert "superseded_by_researcher_decision" in evidence.reasons
    assert remaining == 2, "حُذف تاريخ"


@requires_db
@pytest.mark.asyncio
async def test_confidence_never_overrides_ownership(two_tenants):
    """ملفٌّ آخر ومستأجرٌ آخر — **ولا تشتري الثقةُ مِلكيّة**."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a, b = two_tenants["a"], two_tenants["b"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _seed(tid, uid, filename="هذه.pdf")
    _other, other_file, other_run = await _seed(tid, uid, filename="أخرى.pdf")

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, other_file, QUESTION_ONE)
        await _candidate(session, tid, run_id=other_run, file_id=other_file,
                         chunk=chunk, field_key="questions", value=[QUESTION_ONE],
                         confidence=0.99)

    btid, buid = b["tenant_id"], b["user_id"]
    _bt, bfile, brun = await _seed(btid, buid, filename="مستأجر-آخر.pdf")
    async with tenant_session(btid, buid) as session:
        bchunk = await _chunk(session, btid, bfile, QUESTION_TWO)
        await _candidate(session, btid, run_id=brun, file_id=bfile, chunk=bchunk,
                         field_key="questions", value=[QUESTION_TWO], confidence=0.99)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0, "حقيقةٌ من ملفٍّ آخر عبرت"
    assert evidence.facts.questions == ()


@requires_db
@pytest.mark.asyncio
async def test_a_withheld_modern_thesis_never_escapes_into_legacy(two_tenants):
    """**الحجبُ المقصود لا يُنزَّل صامتًا.**

    رسالةٌ لها أثرٌ حديث ضعيفُ الثقة، ولها صفوفٌ قديمة صالحة للتنقيب. ولو
    سقط المسارُ إلى القديم لنُشر من بابٍ خلفيّ ما رُفض من الباب الأمامي.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _machine_thesis(tid, uid, title_ar=TITLE,
                                              confidence=0.40)

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

    assert body["evidence_basis"] == "canonical_withheld", body["evidence_basis"]
    assert body["opportunities_created"] == 0, "هرب المسارُ إلى الجداول القديمة"
    assert body["outcome"] == "no_eligible_evidence"
    assert await _mined_at(tid, uid, thesis_id) is None


# ═════════ ٨ · النسبُ كاملًا: مستأجرٌ وملفٌّ ومقطعٌ وتشغيلة ═════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("run_status", ["local_only", "awaiting_consent",
                                        "parsing", "parse_failed", "succeeded",
                                        "completed", ""])
async def test_only_real_advanced_run_states_are_eligible(two_tenants, run_status):
    """**ولا حالَ تُقبل بالسكوت.**

    و`succeeded` و`completed` بينها عمدًا: لا كاتبَ لهما في التطبيق، وقد
    كان الأولُ مكتوبًا في مجموعة الحالات المسموحة فمرّت الفحوصُ خضراءَ على
    حالٍ لا تقع في الإنتاج. فيُثبَت أنّ المجهولَ لا يصير مؤهَّلًا صامتًا.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, run_status=run_status)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, QUESTION_ONE)
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="questions", value=[QUESTION_ONE], confidence=0.99)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0, f"«{run_status}» صارت مؤهَّلة"
    assert any(reason.startswith(("no_advanced_extraction", "extraction_run_"))
               for reason in evidence.reasons), evidence.reasons


@requires_db
@pytest.mark.asyncio
async def test_a_chunk_from_another_file_cannot_ground_this_thesis(two_tenants):
    """**ولا يُتّكل على RLS.** هي تمنع المستأجرَ الآخر، لا الملفَّ الآخر.

    فمرشّحٌ على الملفّ (أ) يشير إلى مقطعٍ في الملفّ (ب) **داخل المستأجر
    نفسه**: يعبر RLS سالمًا، واقتباسُه مؤصَّلٌ في مستندٍ آخر. فيُفحص النسبُ
    صراحةً.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, filename="أ.pdf")
    _other, other_file, _other_run = await _seed(tid, uid, filename="ب.pdf")

    async with tenant_session(tid, uid) as session:
        # المقطعُ في الملفّ (ب) ويحمل النصَّ نفسه — فالتأصيلُ ينجح.
        foreign_chunk = await _chunk(session, tid, other_file, QUESTION_ONE)
        await _candidate(session, tid, run_id=run_id, file_id=file_id,
                         chunk=foreign_chunk, field_key="questions",
                         value=[QUESTION_ONE], confidence=0.99)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0, "مقطعُ ملفٍّ آخر أصّل هذه الرسالة"
    assert "chunk_belongs_to_another_file" in evidence.reasons


@requires_db
@pytest.mark.asyncio
async def test_a_run_from_another_file_cannot_authorise_this_thesis(two_tenants):
    """والتشغيلةُ كالمقطع: نسبُها يُفحص، ولا يكفي أنّها في المستأجر نفسه."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _seed(tid, uid, filename="أ.pdf")
    _other, _other_file, other_run = await _seed(tid, uid, filename="ب.pdf")

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, QUESTION_ONE)
        await _candidate(session, tid, run_id=other_run, file_id=file_id,
                         chunk=chunk, field_key="questions",
                         value=[QUESTION_ONE], confidence=0.99)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0, "تشغيلةُ ملفٍّ آخر أجازت هذه الرسالة"
    assert "extraction_run_belongs_to_another_file" in evidence.reasons


# ═════════ ٩ · الاعتمادُ المكسور يسقط مغلقًا ═════════


@requires_db
@pytest.mark.asyncio
@pytest.mark.parametrize("breakage", ["no_memory", "unverified", "wrong_file",
                                      "wrong_tenant"])
async def test_approved_with_a_broken_memory_never_falls_through_to_confidence(
        two_tenants, breakage):
    """**والاعتمادُ المكسور لا ينزل إلى حساب الثقة.**

    كان الفرعُ يعود بالأهليّة عند تمام الشروط ويسقط إلى العتبة عند نقصانها،
    فمرشّحٌ «معتمَد» بذاكرةٍ مفقودةٍ أو غيرِ موثقةٍ يُصنَّف مؤهَّلًا **بثقة
    الآلة** — فيصير الاعتمادُ المكسور أقوى من الاعتماد المفقود.
    """
    import datetime as _dt
    import uuid as _uuid

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.services.thesis import canonical_facts

    a, b = two_tenants["a"], two_tenants["b"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)
    _bt, bfile, _brun = await _seed(b["tenant_id"], b["user_id"], filename="ب.pdf")

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, QUESTION_ONE)
        candidate = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[QUESTION_ONE], confidence=0.99)

        if breakage == "no_memory":
            candidate.status = "approved"
            candidate.decided_by = uid
            candidate.decided_at = _dt.datetime.now(_dt.UTC)
            candidate.resulting_memory_id = None
        else:
            memory = ResearcherMemory(
                tenant_id=tid if breakage != "wrong_tenant" else b["tenant_id"],
                memory_category="project_decision", statement_ar=QUESTION_ONE,
                value={"value": QUESTION_ONE}, source_type="upload",
                source_file_id=file_id if breakage != "wrong_file" else bfile,
                source_locator=chunk.locator, source_quote=chunk.text[:200],
                verification_status=("verified" if breakage != "unverified"
                                     else "unverified"),
                verified_by=uid, verified_at=_dt.datetime.now(_dt.UTC))
            session.add(memory)
            await session.flush()
            candidate.status = "approved"
            candidate.decided_by = uid
            candidate.decided_at = _dt.datetime.now(_dt.UTC)
            candidate.resulting_memory_id = memory.id
            assert memory.id != _uuid.UUID(int=0)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.eligible_facts_used == 0, (
        f"اعتمادٌ مكسور ({breakage}) نزل إلى حساب الثقة ومرّ")
    assert "approved_memory_integrity_failed" in evidence.reasons, evidence.reasons


# ═════════ ١٠ · المفردُ يُحسم، والمتعدّدُ لا يُمحى بالمشاركة ═════════


@requires_db
@pytest.mark.asyncio
async def test_an_approved_item_does_not_erase_unrelated_items_of_a_multi_field(
        two_tenants):
    """**اعتمادُ سؤالٍ لا يقول شيئًا عن سؤالٍ آخر.**

    والإبطالُ على مستوى الحقل كان أوسعَ من الحقّ: يمحو دليلًا سليمًا لمجرّد
    أنّه يشارك المفتاح. ولا تُخترع هويّةُ عنصرٍ دلاليّة — **وعلاقةٌ مجهولة
    ليست علاقةَ إحلال**.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id,
                             " ".join([QUESTION_ONE, QUESTION_TWO]))
        machine = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[QUESTION_TWO], confidence=0.99)
        human = await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="questions", value=[QUESTION_ONE], confidence=0.80)
        await _approve(session, tid, uid, human.id)
        assert machine.id != human.id

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert QUESTION_ONE in evidence.facts.questions, "المعتمَدُ البشريّ سقط"
    assert QUESTION_TWO in evidence.facts.questions, (
        "سؤالٌ آليٌّ سليم مُحي لمجرّد مشاركته المفتاح")
    assert evidence.eligible_facts_used == 2


@requires_db
@pytest.mark.asyncio
async def test_an_approved_singleton_title_wins_the_whole_field(two_tenants):
    """والعنوانُ مفرد — **لا يحتمل قيمتين**، فاعتمادُه يحسمه كلَّه."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts, fact_eligibility

    chosen = "العنوانُ الذي اعتمده الباحث"
    assert "title_ar" in fact_eligibility.SINGLETON_FIELDS
    assert "questions" in fact_eligibility.MULTI_FIELDS

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, " ".join([TITLE, chosen]))
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="title_ar", value=TITLE,
                         category="researcher_fact", confidence=0.99)
        human = await _candidate(session, tid, run_id=run_id, file_id=file_id,
                                 chunk=chunk, field_key="title_ar", value=chosen,
                                 category="researcher_fact", confidence=0.80)
        await _approve(session, tid, uid, human.id)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.approved_title == chosen, "الآليُّ غلب المعتمَد في حقلٍ مفرد"
    assert "superseded_by_researcher_decision" in evidence.reasons


# ═════════ ١١ · الشكلُ يسبق الثقة ═════════


@requires_db
@pytest.mark.asyncio
async def test_malformed_values_are_refused_at_maximum_confidence(two_tenants):
    """**قيمةٌ فاسدةُ الشكل لا تُنقذها 0.99.**"""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid)

    async with tenant_session(tid, uid) as session:
        body = "بلغ عدد المدعوين 310 واستجاب منهم 297 مفردة. 2026 عدد الصفحات: 120"
        chunk = await _chunk(session, tid, file_id, body)
        # عددان متنافسان — **ولا يُخمَّن أيُّهما نهائيّ**.
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="sample_size",
                         value="بلغ عدد المدعوين 310 واستجاب منهم 297",
                         confidence=0.99)
        # عنوانٌ رقمٌ محض، وآخرُ اسمُ ملفّ، وثالثٌ بياناتُ صفحات.
        for title in ("2026", "رسالة.pdf", "عدد الصفحات: 120"):
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key="title_ar", value=title,
                             category="researcher_fact", confidence=0.99)
        # قاموسٌ ليس دليلًا لمجرّد أنّه غيرُ فارغ.
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="constructs", value=[{"name": CONSTRUCT_ONE}],
                         confidence=0.99)

    async with tenant_session(tid, uid) as session:
        evidence = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert evidence.facts.sample_ids == (), "عددان متنافسان أسندا عيّنة"
    assert "sample_size_has_competing_counts" in evidence.reasons
    assert evidence.approved_title is None, "عنوانٌ فاسد الشكل مرّ"
    assert evidence.facts.variables == (), "قاموسٌ صار دليلًا"


def test_the_sample_size_shape_rules_are_conservative():
    """يُقبل ما يُقطع بصلاحه، ويُرفض ما يُقطع بفساده — **بلا حكمٍ دلاليّ**."""
    from athera_api.services.thesis import fact_eligibility as policy

    for good in ("310", "310 participants", "بلغ حجم العينة 310 مفردات", "٣١٠"):
        ok, why = policy.structurally_valid("sample_size", [good])
        assert ok, f"{good!r} رُفض: {why}"

    for bad in ("0", "لا يوجد عدد", "310 invited, 297 responded", ""):
        ok, _why = policy.structurally_valid("sample_size", [bad] if bad else [])
        assert not ok, f"{bad!r} قُبل"


# ═════════ ١٢ · الأثرُ المالك هو الأثرُ ذو الصلة ═════════


@requires_db
@pytest.mark.asyncio
async def test_metadata_only_extraction_does_not_block_legacy_fallback(two_tenants):
    """**بياناتُ الوصف وحدها لا تحجب المسارَ القديم.**

    رسالةٌ قديمة رُفع ملفُّها فاستُخرج منه عددُ صفحاتٍ واسمُ ملفّ: لا شيء
    ممّا استُخرج يُنقَّب أصلًا، فحجبُها يمنع تنقيبًا مشروعًا بحجّة أثرٍ لا
    يمتّ إليه بصلة.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=TITLE)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, "رسالة.pdf 120")
        for key, value in (("page_count", 120), ("source_filename", "رسالة.pdf")):
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key=key, value=value,
                             category="researcher_fact", confidence=1.0)
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

    assert body["evidence_basis"] == "legacy", body["evidence_basis"]
    assert body["opportunities_created"] > 0, "حُجب تنقيبٌ مشروع بأثرٍ لا صلة له"


@requires_db
@pytest.mark.asyncio
async def test_a_mining_relevant_but_withheld_footprint_still_blocks_legacy(
        two_tenants):
    """وأثرٌ **ذو صلة** حُجب يبقى مالكًا — ولا هروبَ إلى القديم."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import ThesisResult, ThesisSection

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=TITLE)

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, QUESTION_ONE)
        # ذو صلةٍ بالتنقيب، لكنّه دون العتبة — حجبٌ مقصود.
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="questions", value=[QUESTION_ONE],
                         confidence=0.40)
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

    assert body["evidence_basis"] == "canonical_withheld", body["evidence_basis"]
    assert body["opportunities_created"] == 0, "هرب المسارُ إلى الجداول القديمة"
    assert body["outcome"] == "no_eligible_evidence"
