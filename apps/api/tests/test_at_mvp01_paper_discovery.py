"""اكتشافُ فكرةِ الورقة | Discovering a paper idea (MVP-0.1 P0, item 6+7).

**سؤالان لا سؤال — وخلطُهما هو ما ردّ الباحثَ بصفر.**

  ‏«اقرأ رسالتي وقل لي أيَّ الأوراق يمكن أن تُشتقّ منها؟»
  ‏«هل لهذه الورقة من الأدلّة ما يكفي للصياغة الآمنة؟»

والثاني قرارٌ **لاحق**. وكان شرطُه — بناءٌ وعيّنةٌ معًا — مفروضًا على
الأول في `_fallback_drafts`:

    if not constructs or not samples:
        return []

فرسالةٌ فيها نتيجةٌ قويّةٌ مؤصَّلةٌ مؤهَّلةٌ آليًّا، ولم يُستخرَج منها وصفُ
عيّنة، كانت تخرج بصفرِ أفكار. **وغيابُ السياق لا يمحو الفكرة؛ يجعلها
ناقصةً معلنة.**

## الطبقتان، كما تُقاسان هنا

  ‏(أ) **فكرةٌ قابلةٌ للاكتشاف** — مرتكزٌ علميٌّ واحدٌ على الأقلّ:
      ‏`AUTO_ELIGIBLE`، مؤصَّلٌ في `FactCandidate` حقيقيّ، له اقتباسٌ
      وموضع، ومن هذا المستأجر وهذا الملفّ. والعنوانُ وحده لا يكفي أبدًا،
      ولا البياناتُ الوصفية، ولا بناءٌ وحده، ولا عيّنةٌ وحدها.

  ‏(ب) **مكتملةُ السياق** — المرتكزُ ومعه بناءٌ وعيّنة. وهنا يبقى الشرطُ
      الصارم كما كان، في طبقته الصحيحة.

## وما لا يقع هنا

  • **لا تُوصف فكرةٌ اكتُشفت بأنّها «جاهزة للنشر».** الحالُ تبقى
    `discovered`/`proposed`، ولا `evidence_readiness_score` يُصطنع.
  • **ولا يُختلق ما نقص**: لا عيّنةٌ من معرّف الرسالة، ولا بُنًى من
    العنوان، ولا مجتمعٌ لأنّ الموضوع يوحي به.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db
from tests.test_at_thesis_canonical_bridge import (  # noqa: PLC2701
    CONSTRUCT_ONE,
    CONSTRUCT_TWO,
    FINDING,
    POPULATION,
    QUESTION_ONE,
    TITLE,
    _candidate,
    _chunk,
    _client,
    _mining_state,
    _seed,
)


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


#: نصٌّ يحمل كلَّ ما تحتاجه الحالات — والاقتباسُ يُؤخذ منه حرفًا.
BODY = " ".join([TITLE, QUESTION_ONE, FINDING, CONSTRUCT_ONE, CONSTRUCT_TWO, POPULATION])

#: **حقولٌ إدارية كثيرة** — كما في الإنتاج: ٢٦ منها خرجت
#: بـ`unsupported_field_key`. وهي مشروعةٌ للمراجعة، وليست دليلًا علميًّا.
ADMINISTRATIVE = (
    ("background", "خلفية الدراسة وسياقها العام"),
    ("degree", "دكتوراه"),
    ("university", "جامعة الملك سعود"),
    ("college", "كلية إدارة الأعمال"),
    ("department", "قسم التسويق"),
    ("year", "1446"),
    ("recommendations", "توصيات الدراسة للممارسين"),
    ("objectives", "أهداف الدراسة"),
    ("limitations", "حدود الدراسة"),
)


async def _build(tid, uid, *, scientific, administrative=True, filename=None,
                 title_conf=0.95):
    """رسالةٌ بشكل الإنتاج: عنوانٌ، وحقولٌ إدارية، ثمّ ما يُطلب علميًّا.

    و`scientific` متتاليةُ `(field_key, value, confidence)` — وهي وحدها
    ما يفرّق بين الحالات.
    """
    from athera_api.db import tenant_session

    thesis_id, file_id, run_id = await _seed(
        tid, uid, filename=filename or f"{uuid.uuid4().hex[:8]}.pdf")
    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, BODY)
        await _candidate(session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
                         field_key="title_ar", value=TITLE,
                         category="researcher_fact", confidence=title_conf, quote=TITLE)
        if administrative:
            for key, value in ADMINISTRATIVE:
                await _candidate(session, tid, run_id=run_id, file_id=file_id,
                                 chunk=chunk, field_key=key, value=value,
                                 confidence=0.97, quote=BODY[:120])
        for key, value, confidence in scientific:
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key=key, value=value,
                             confidence=confidence, quote=BODY[:200])
    return thesis_id, file_id, run_id


async def _opportunities(tid, uid, thesis_id):
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity

    async with tenant_session(tid, uid) as session:
        return (await session.execute(
            select(PublicationOpportunity)
            .where(PublicationOpportunity.thesis_id == thesis_id)
            .order_by(PublicationOpportunity.created_at))).scalars().all()


def _discovery(opportunity):
    from athera_api.services.thesis.mining import DISCOVERY_NAMESPACE

    return (opportunity.readiness_components or {}).get(DISCOVERY_NAMESPACE) or {}


async def _mine(tid, uid, thesis_id):
    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")
    assert response.status_code == 202
    return response.json()


# ═════════ الحالة ١ · شكلُ الإنتاج بعينه: نتيجةٌ قويّة، ولا عيّنة ولا بُنًى ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_strong_finding_without_context_still_yields_one_idea(two_tenants):
    """**وهذه هي الحالةُ التي كانت تُردّ بصفر.**

    عنوانٌ، وتسعةُ حقولٍ إدارية، ونتيجةٌ واحدةٌ مؤصَّلةٌ مؤهَّلةٌ آليًّا.
    ولا عيّنة، ولا بُنًى. والمطلوب: **فكرةٌ واحدة**، ناقصةُ السياق معلنةً.
    """
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(
        tid, uid, scientific=(("primary_findings", [FINDING], 0.95),))

    body = await _mine(tid, uid, thesis_id)
    assert body["evidence_basis"] == "canonical"
    assert body["opportunities_created"] == 1, f"صفرٌ كما قبل الإصلاح: {body}"

    # **والحقولُ الإدارية لم تدخل الدليل** — ولا واحدٌ منها.
    reasons = body["exclusion_reasons"] if "exclusion_reasons" in body else {}
    opportunities = await _opportunities(tid, uid, thesis_id)
    assert len(opportunities) == 1
    discovery = _discovery(opportunities[0])

    assert discovery["level"] == mining.miner.LEVEL_IDEA_ONLY
    assert discovery["basis"] == mining.miner.BASIS_RESULT
    assert discovery["context_complete"] is False
    assert set(discovery["missing_context"]) == {"constructs", "sample"}
    assert discovery["source_fact_refs"], "فكرةٌ بلا حقيقةٍ مصدر"

    # **ولا عيّنةَ اختُلقت ولا بُنًى** — الأعمدةُ فارغةٌ صدقًا.
    assert (opportunities[0].sample_refs or []) == []
    assert (opportunities[0].variable_refs or []) == []
    assert str(thesis_id) not in (opportunities[0].sample_refs or []), (
        "مُعرّفُ الرسالة كُتب عيّنةً لها")

    # **ولا تُدَّعى جاهزيةُ نشر.**
    assert opportunities[0].status == "discovered"
    assert opportunities[0].planning_status == "proposed"
    assert opportunities[0].evidence_readiness_score is None

    # **وحالُ التنقيب «اكتمل»**: فرصةٌ قامت فعلًا. ونقصُ السياق لا يجعلها
    # «حُجبت» — وذاك خلطُ السؤالين من جديد.
    assert body["mining_state"] == mining.COMPLETED
    assert await _mining_state(tid, uid, thesis_id) == mining.COMPLETED
    assert reasons.get("no_extraction_confidence", 0) == 0


# ═════════ الحالة ٢ · سؤالٌ قويّ بلا نتيجة ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_strong_question_without_a_result_says_it_claims_no_result(two_tenants):
    """**ولا نتيجةَ تُدَّعى حين لا نتيجة.** والتسويغُ يقولها صراحةً."""
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(
        tid, uid, scientific=(("questions", [QUESTION_ONE], 0.94),))

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 1

    opportunity = (await _opportunities(tid, uid, thesis_id))[0]
    discovery = _discovery(opportunity)
    assert discovery["basis"] == mining.miner.BASIS_QUESTION
    assert discovery["level"] == mining.miner.LEVEL_IDEA_ONLY
    assert discovery["context_complete"] is False

    # **ولا نتيجةَ في الأعمدة ولا في المعنى.**
    assert (opportunity.result_refs or []) == []
    assert opportunity.opportunity_kind == "extension"
    assert opportunity.research_question_ar == QUESTION_ONE

    # ومعرّفُ السؤال في مصدره، **لا في `result_refs`**.
    assert len(discovery["source_fact_refs"]) == 1
    assert discovery["source_fact_refs"][0] not in (opportunity.result_refs or [])


def test_the_preliminary_question_rationale_denies_a_result_in_both_languages():
    """**والنفيُ في نصِّ التسويغ نفسِه** — يقرؤه الباحثُ لا المطوِّرُ وحده."""
    from athera_api.services.thesis import miner

    facts = miner.ThesisFacts(
        thesis_id=str(uuid.uuid4()),
        question_refs=(("q-1", QUESTION_ONE),), questions=(QUESTION_ONE,))
    drafts = miner.mine(facts)
    assert len(drafts) == 1
    assert "لا تدّعي" in drafts[0].rationale_ar
    assert "does not claim" in drafts[0].rationale_en
    assert drafts[0].result_refs == []


# ═════════ الحالة ٣ · سياقٌ مكتمل — والمكتملُ لا يُضاعَف بمبدئيّة ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_complete_context_outranks_the_preliminary_fallback(two_tenants):
    """**والأقوى يسبق، ولا تُكرَّر فكرةٌ قائمة.**"""
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(tid, uid, scientific=(
        ("primary_findings", [FINDING], 0.95),
        ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO], 0.93),
        ("population", [POPULATION], 0.94),
    ))

    body = await _mine(tid, uid, thesis_id)
    opportunities = await _opportunities(tid, uid, thesis_id)

    assert body["opportunities_created"] == len(opportunities)
    # **ولا فكرةَ مبدئيةٌ تُضاف فوق المكتملة.**
    preliminary = [o for o in opportunities
                   if _discovery(o).get("level") == mining.miner.LEVEL_IDEA_ONLY]
    assert not preliminary, f"كُرِّرت فكرةٌ مبدئية فوق مكتملة: {len(preliminary)}"

    for opportunity in opportunities:
        discovery = _discovery(opportunity)
        assert discovery["level"] == mining.miner.LEVEL_CONTEXT_COMPLETE
        assert discovery["missing_context"] == []
        assert discovery["context_complete"] is True
        assert discovery["source_fact_refs"]


# ═════════ الحالات ٤–٦ · ما لا يُنشئ فكرةً أبدًا ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_title_and_administrative_fields_alone_create_nothing(two_tenants):
    """**الحالة ٤+٥ ممزوجتان: عنوانٌ وبياناتٌ وصفية — وصفرُ أفكار.**

    وهذه هي الدعوى التي لا تُساوَم: العنوانُ يُسمّي ولا يُنشئ، والحقولُ
    الإدارية تنفع المراجعةَ ولا تصلح دليلًا علميًّا.
    """
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(tid, uid, scientific=())

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 0
    assert body["eligible_facts_used"] == 0, "حقلٌ إداريٌّ عُدَّ دليلًا علميًّا"
    assert await _opportunities(tid, uid, thesis_id) == []
    assert body["outcome"] == mining.OUTCOME_NO_ELIGIBLE_EVIDENCE
    assert await _mining_state(tid, uid, thesis_id) == mining.NO_ELIGIBLE_EVIDENCE


@requires_db
@pytest.mark.asyncio
async def test_low_confidence_science_creates_nothing(two_tenants):
    """**الحالة ٥ · دليلٌ علميٌّ دون العتبة — ولا تُخفَّض العتبةُ له.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(tid, uid, scientific=(
        ("primary_findings", [FINDING], 0.55),
        ("questions", [QUESTION_ONE], 0.40),
    ))

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 0
    assert body["eligible_facts_used"] == 0
    assert await _opportunities(tid, uid, thesis_id) == []


@requires_db
@pytest.mark.asyncio
async def test_an_ungrounded_high_confidence_result_creates_nothing(two_tenants):
    """**الحالة ٦ · `0.99` مع اقتباسٍ غير مؤصَّل — والتأصيلُ لا يُشترى.**"""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, filename="مختلَق.pdf")
    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, BODY)
        await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="primary_findings", value=["نتيجةٌ لا توجد في المقطع"],
            confidence=0.99, quote="اقتباسٌ لم يُكتب في هذا المستند قطّ")

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)
    assert canonical.reasons.get("quote_not_grounded") == 1

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 0
    assert await _opportunities(tid, uid, thesis_id) == []


# ═════════ الإسناد: كلُّ فكرةٍ تُردّ إلى مقطعها ═════════


@requires_db
@pytest.mark.asyncio
async def test_every_idea_traces_back_to_a_grounded_fact_candidate(two_tenants):
    """**سلسلةُ الإسناد كاملةً**: فكرة ← حقيقة ← مقطع ← اقتباسٌ مؤصَّل.

    ولا جملةٌ منسوخةٌ بلا مصدر. ويُفحص المستأجرُ والملفُّ أيضًا: مصدرٌ من
    ملفٍّ آخر إسنادٌ كاذبٌ وإن بدا صحيحَ الشكل.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research import DocumentChunk, FactCandidate
    from athera_api.services.extraction.base import quote_is_grounded

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _r = await _build(
        tid, uid, scientific=(("primary_findings", [FINDING], 0.95),))
    await _mine(tid, uid, thesis_id)

    opportunities = await _opportunities(tid, uid, thesis_id)
    assert opportunities

    checked = 0
    for opportunity in opportunities:
        refs = _discovery(opportunity)["source_fact_refs"]
        assert refs, "فرصةٌ بلا حقيقةٍ مصدر"
        async with tenant_session(tid, uid) as session:
            for ref in refs:
                fact = (await session.execute(
                    select(FactCandidate)
                    .where(FactCandidate.id == uuid.UUID(ref)))).scalar_one()
                chunk = (await session.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.id == fact.chunk_id))).scalar_one()

                assert fact.tenant_id == tid, "مصدرٌ من مستأجرٍ آخر"
                assert fact.file_id == file_id, "مصدرٌ من ملفٍّ آخر"
                assert (fact.quote or "").strip(), "حقيقةٌ بلا اقتباس"
                assert (fact.locator or "").strip(), "حقيقةٌ بلا موضع"
                assert quote_is_grounded(fact.quote, chunk.text), "اقتباسٌ غيرُ مؤصَّل"
                assert fact.confidence is not None
                checked += 1
    assert checked >= 1


@requires_db
@pytest.mark.asyncio
async def test_discovery_needs_no_decision_and_no_manual_mining(two_tenants):
    """**ولا `/decide`، ولا صفحةُ مراجعة، ولا زرُّ تنقيبٍ يدويّ.**

    والمسارُ هنا هو المسارُ التلقائيّ نفسُه: `mining.run` كما يستدعيه
    خطُّ المعالجة بعد أن يستقرّ الاستخراج — بلا نداءِ واجهةٍ واحد.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _r = await _build(
        tid, uid, scientific=(("primary_findings", [FINDING], 0.95),))

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        outcome = await mining.run(session, tenant_id=tid, actor_user_id=uid,
                                   thesis=thesis)

    assert outcome.created == 1
    assert outcome.mining_state == mining.COMPLETED

    async with tenant_session(tid, uid) as session:
        approvals = (await session.execute(
            select(func.count(ResearcherMemory.id))
            .where(ResearcherMemory.source_file_id == file_id))).scalar_one()
    assert approvals == 0, "لزِم اعتمادٌ بشريّ لاكتشاف فكرة"


# ═════════ لا يُدَّعى نضجٌ لم يقع ═════════


def test_a_discovered_idea_is_never_labelled_with_development_readiness():
    """**ولا تُستعار مفرداتُ الجاهزية لوصف اكتشاف.**

    ‏`readiness.classify` مفرداتُه أحكامُ تطوير — `ready_to_convert`
    وأخواتُها. ومجالُ الاكتشاف منفصلٌ عنها اسمًا ومعنًى، فلا يتسرّب حكمٌ
    من هذا إلى ذاك.
    """
    from athera_api.services.thesis import miner
    from athera_api.services.thesis.mining import DISCOVERY_NAMESPACE
    from athera_api.services.thesis.vocab import READINESS_OUTCOMES

    assert DISCOVERY_NAMESPACE == "thesis_discovery"
    assert set(miner.DISCOVERY_LEVELS).isdisjoint(READINESS_OUTCOMES)
    assert "ready_to_convert" not in miner.DISCOVERY_LEVELS
    assert "ready_to_convert" not in miner.DISCOVERY_BASES


def test_a_draft_must_name_the_facts_that_justify_it():
    """**ولا فكرةَ بلا مصدر** — والعقدُ يمنع بناءَها أصلًا، لا يُصلحها بعدُ."""
    from athera_api.services.thesis import miner

    with pytest.raises(ValueError, match="must name the facts"):
        miner.OpportunityDraft(
            opportunity_kind="extension", paper_kind="extension",
            working_title_ar="فكرةٌ بلا مصدر", research_question_ar=None,
            rationale_ar="—", rationale_en="—")


def test_a_level_can_never_contradict_its_missing_context():
    """**ولا «مكتملة» ومعها نقص** — والتناقضُ يُرفض عند البناء."""
    from athera_api.services.thesis import miner

    with pytest.raises(ValueError, match="contradicts"):
        miner.OpportunityDraft(
            opportunity_kind="extension", paper_kind="extension",
            working_title_ar="متناقضة", research_question_ar=None,
            rationale_ar="—", rationale_en="—", source_fact_refs=["f1"],
            discovery_level=miner.LEVEL_CONTEXT_COMPLETE,
            missing_context=[miner.MISSING_SAMPLE])


def test_the_legacy_path_gains_no_discovery_ideas():
    """**والقديمُ يبقى كما كان.** مراجعُه ليست حقائقَ مرشّحة، وعيّنتُه
    مصطنَعة (`sample_ids={thesis_id}`) — ففكرةٌ منه لا تُثبت إسنادَها.
    """
    from athera_api.services.thesis import miner

    legacy = miner.ThesisFacts(
        thesis_id=str(uuid.uuid4()), results=(("r1", FINDING),),
        evidence_is_canonical=False)
    assert miner.mine(legacy) == []

    canonical = miner.ThesisFacts(
        thesis_id=str(uuid.uuid4()), results=(("r1", FINDING),))
    assert len(miner.mine(canonical)) == 1


# ═════════ الفرضيةُ مرتكزٌ ثالث — والعقدُ المُعلَن يلزم التنفيذَ ═════════
#
# **وثيقةُ هذا العمل تعدّ `hypotheses` مرتكزًا صالحًا للاكتشاف**، والتنفيذُ
# كان يعرف النتيجةَ والسؤالَ وحدهما. فرسالةٌ فرضياتُها مستخرَجةٌ مؤهَّلة،
# ولا سؤالَ صريحٌ فيها ولا نتيجةٌ بلغت العتبة، تخرج بصفرِ أفكار بينما
# الوثيقةُ تقول غيرَ ذلك. فيُقاس هنا أنّ التنفيذَ لحق بالعقد.


@requires_db
@pytest.mark.asyncio
async def test_a_hypothesis_alone_with_incomplete_context_yields_one_idea(two_tenants):
    """**(أ) فرضيةٌ وحدها وسياقٌ ناقص ← فكرةٌ واحدةٌ مبدئية.**"""
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    hypothesis = "توجد علاقة دالة بين القيادة التحويلية والرضا الوظيفي"
    thesis_id, _f, _r = await _build(
        tid, uid, scientific=(("hypotheses", [hypothesis], 0.94),))

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 1, f"فرضيةٌ مؤهَّلةٌ لم تُنتج فكرة: {body}"

    opportunity = (await _opportunities(tid, uid, thesis_id))[0]
    discovery = _discovery(opportunity)
    assert discovery["basis"] == mining.miner.BASIS_HYPOTHESIS == "hypothesis"
    assert discovery["level"] == mining.miner.LEVEL_IDEA_ONLY
    assert set(discovery["missing_context"]) == {"constructs", "sample"}
    assert opportunity.opportunity_kind == "extension"
    assert opportunity.paper_kind == "extension"

    # **ولا تُقلب الفرضيةُ نتيجةً، ولا تُعاد صياغتُها سؤالًا.**
    assert (opportunity.result_refs or []) == []
    assert opportunity.research_question_ar is None
    assert discovery["basis"] != mining.miner.BASIS_QUESTION
    assert discovery["basis"] != mining.miner.BASIS_RESULT

    # ومعرّفُ الفرضية هو المصدر.
    assert len(discovery["source_fact_refs"]) == 1
    assert discovery["source_fact_refs"][0] not in (opportunity.result_refs or [])


def test_the_hypothesis_rationale_denies_a_result_in_both_languages():
    """**والنفيُ في نصّ التسويغ** — يقرؤه الباحثُ لا المطوِّرُ وحده."""
    from athera_api.services.thesis import miner

    facts = miner.ThesisFacts(
        thesis_id=str(uuid.uuid4()),
        hypotheses=("فرضية",), hypothesis_refs=(("h-1", "فرضية"),))
    drafts = miner.mine(facts)
    assert len(drafts) == 1
    assert "فرضيةٍ" in drafts[0].rationale_ar
    assert "لا تدّعي" in drafts[0].rationale_ar
    assert "hypothesis" in drafts[0].rationale_en
    assert "does not claim" in drafts[0].rationale_en
    assert drafts[0].result_refs == []
    assert drafts[0].research_question_ar is None


@requires_db
@pytest.mark.asyncio
async def test_a_hypothesis_with_complete_context_is_context_complete(two_tenants):
    """**(ب) فرضيةٌ ومعها بناءٌ وعيّنة ← مكتملةُ السياق.**"""
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    hypothesis = "توجد علاقة دالة بين القيادة التحويلية والرضا الوظيفي"
    thesis_id, _f, _r = await _build(tid, uid, scientific=(
        ("hypotheses", [hypothesis], 0.94),
        ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO], 0.93),
        ("population", [POPULATION], 0.94),
    ))

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] >= 1

    opportunities = await _opportunities(tid, uid, thesis_id)
    discoveries = [_discovery(o) for o in opportunities]
    assert any(d["basis"] == mining.miner.BASIS_HYPOTHESIS for d in discoveries)
    for discovery in discoveries:
        assert discovery["level"] == mining.miner.LEVEL_CONTEXT_COMPLETE
        assert discovery["missing_context"] == []
        assert discovery["context_complete"] is True


@requires_db
@pytest.mark.asyncio
async def test_a_low_confidence_hypothesis_creates_nothing(two_tenants):
    """**(ج) فرضيةٌ دون العتبة ← صفر.** ولا تُخفَّض العتبةُ لمرتكزٍ جديد."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(
        tid, uid, scientific=(("hypotheses", ["فرضيةٌ ضعيفةُ الثقة"], 0.50),))

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 0
    assert body["eligible_facts_used"] == 0
    assert await _opportunities(tid, uid, thesis_id) == []


@requires_db
@pytest.mark.asyncio
async def test_an_ungrounded_high_confidence_hypothesis_creates_nothing(two_tenants):
    """**(د) `0.99` مع فرضيةٍ غير مؤصَّلة ← صفر.** والتأصيلُ لا يُشترى."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, filename="فرضيةٌ-مختلَقة.pdf")
    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, BODY)
        await _candidate(
            session, tid, run_id=run_id, file_id=file_id, chunk=chunk,
            field_key="hypotheses", value=["فرضيةٌ لا توجد في المقطع"],
            confidence=0.99, quote="اقتباسٌ لم يُكتب في هذا المستند قطّ")

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)
    assert canonical.reasons.get("quote_not_grounded") == 1

    body = await _mine(tid, uid, thesis_id)
    assert body["opportunities_created"] == 0
    assert await _opportunities(tid, uid, thesis_id) == []


def test_the_result_basis_does_not_mislabel_a_theme_or_a_hypothesis_result():
    """**و«نتيجة» لا «نتيجةٌ رئيسة».**

    ‏`results` الكنسيّة تُغذّيها ثلاثةُ حقول — `primary_findings` و
    `hypothesis_results` و`qualitative_themes` — فوسمُها جميعًا
    `primary_finding` خبرٌ خاطئٌ في اثنتين من ثلاث.
    """
    from athera_api.services.thesis import miner
    from athera_api.services.thesis.canonical_facts import RESULT_KEYS

    assert miner.BASIS_RESULT == "result"
    assert len(RESULT_KEYS) == 3
    assert "primary_finding" not in miner.DISCOVERY_BASES


# ═════════ الإسنادُ الكنسيّ لا يُدَّعى لمرجعٍ قديم ═════════


@requires_db
@pytest.mark.asyncio
async def test_a_canonical_opportunity_exposes_resolvable_fact_provenance(two_tenants):
    """**(١) الكنسيّةُ تحمل المجالَ، وكلُّ مرجعٍ فيه يُردّ إلى حقيقةٍ قائمة.**"""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research import FactCandidate
    from athera_api.services.thesis.mining import DISCOVERY_NAMESPACE

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _r = await _build(
        tid, uid, scientific=(("primary_findings", [FINDING], 0.95),))
    await _mine(tid, uid, thesis_id)

    for opportunity in await _opportunities(tid, uid, thesis_id):
        assert DISCOVERY_NAMESPACE in (opportunity.readiness_components or {})
        refs = _discovery(opportunity)["source_fact_refs"]
        assert refs
        async with tenant_session(tid, uid) as session:
            for ref in refs:
                fact = (await session.execute(
                    select(FactCandidate)
                    .where(FactCandidate.id == uuid.UUID(ref)))).scalar_one_or_none()
                assert fact is not None, f"مرجعٌ لا يُردّ إلى حقيقة: {ref}"
                assert fact.file_id == file_id


@requires_db
@pytest.mark.asyncio
async def test_a_legacy_opportunity_never_claims_canonical_fact_provenance(two_tenants):
    """**(٢) والقديمةُ لا تحمل المجالَ أصلًا.**

    فالمسارُ القديم يُمرّر معرّفاتِ `ThesisSection`/`ThesisResult`، وهي
    ليست حقائقَ مرشّحة. ولو كُتبت `source_fact_refs` لصارت وعدًا لا يُفحص:
    مرجعٌ يُقرأ إسنادًا كنسيًّا ولا يُردّ إلى شيء.

    **والأشكالُ المتخصّصة تسبق المقترحَ المبدئيّ وتعمل على القديم أيضًا** —
    فحظرُ المبدئيّ وحده لم يكن يكفي، وهذا الفحصُ يعضّ على الفرق.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.research import FactCandidate
    from athera_api.models.thesis import ThesisResult, ThesisSection
    from athera_api.services.thesis.mining import DISCOVERY_NAMESPACE

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file_id, _run = await _seed(tid, uid, title_ar=TITLE,
                                            filename="قديمة.pdf")
    async with tenant_session(tid, uid) as session:
        session.add(ThesisSection(tenant_id=tid, thesis_id=thesis_id,
                                  section_key="questions", content_ar=QUESTION_ONE))
        session.add(ThesisResult(tenant_id=tid, thesis_id=thesis_id,
                                 label_ar=FINDING,
                                 variables=[CONSTRUCT_ONE, CONSTRUCT_TWO],
                                 is_published=False))

    body = await _mine(tid, uid, thesis_id)
    assert body["evidence_basis"] == "legacy"

    opportunities = await _opportunities(tid, uid, thesis_id)
    assert opportunities, "المسارُ القديم لم يُنتج شيئًا — فالفحصُ لا يقيس شيئًا"

    async with tenant_session(tid, uid) as session:
        for opportunity in opportunities:
            components = opportunity.readiness_components or {}
            assert DISCOVERY_NAMESPACE not in components, (
                "فرصةٌ قديمة كُتب لها إسنادٌ كنسيّ")
            # وأيُّ مرجعٍ فيها ليس `FactCandidate` — وهذا سببُ المنع.
            for ref in (opportunity.result_refs or []):
                fact = (await session.execute(
                    select(FactCandidate)
                    .where(FactCandidate.id == uuid.UUID(ref)))).scalar_one_or_none()
                assert fact is None, "مرجعٌ قديمٌ صادف حقيقةً — التجهيزةُ ملتبسة"


@requires_db
@pytest.mark.asyncio
async def test_the_canonical_fresh_upload_path_is_unchanged(two_tenants):
    """**(٣) ومسارُ الرفع الكنسيّ كما كان** — لم يُمسّ بهذا الحدّ."""
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _build(tid, uid, scientific=(
        ("primary_findings", [FINDING], 0.95),
        ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO], 0.93),
        ("population", [POPULATION], 0.94),
    ))

    body = await _mine(tid, uid, thesis_id)
    assert body["evidence_basis"] == "canonical"
    assert body["opportunities_created"] >= 1
    assert body["mining_state"] == mining.COMPLETED
    for opportunity in await _opportunities(tid, uid, thesis_id):
        assert _discovery(opportunity)["context_complete"] is True

