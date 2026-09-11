"""ثقةُ الاستخراج شرطٌ، وحالُ التنقيب صادقة | MVP-0.1 P0.

**الواقعةُ التي تحرسها هذه الحزمة، بحرفها.**

رُفعت رسالتان في الإنتاج. قُرئتا. استُخرج منهما ثلاثٌ وعشرون حقلًا معروضةً
على الصفّ. وعرضت البطاقةُ بجوارها: «لم يبدأ استخراج الفرص بعد». ولم تتكوّن
فرصةُ نشرٍ واحدة.

والسببُ سلسلةٌ من حلقةٍ واحدة مكسورة:

  ‏١ ‏`ExtractedField.extraction_confidence` كان `default=None`. فمخرَجُ
    نموذجٍ أغفل الثقةَ يُقبل **بصمت** ويُعدّ استخراجًا ناجحًا.
  ‏٢ فيُحفظ العمودُ `fact_candidates.confidence` فارغًا.
  ‏٣ فتستبعده الأهليّةُ كلَّه بـ`no_extraction_confidence` — وهي محقّة:
    حقيقةٌ بلا ثقةٍ لا يجوز أن تُنقَّب.
  ‏٤ فيبلغ المنقّبَ **صفرُ** حقائقَ مؤهَّلة، فلا فرصة.
  ‏٥ ثمّ تُكتب الحالُ `not_started` — لأنّ مفردات 0031 الخمس لا تحوي ما
    يقول «جريتُ فلم أجد دليلًا مؤهَّلًا»، فوقع الاختيارُ على أكذبها.

فالعطبُ الأول في **العقد**، والثاني في **المفردات**. وكلُّ فحصٍ هنا يقيس
واقعةً في تلك السلسلة، ولا يهنّئ نفسه بأنّها لم تنكسر.

## وما لا تفعله هذه الحزمة

  • **لا تخترع ثقةً غائبة.** ولا `0.5` افتراضية، ولا ترقيةً تلقائية.
  • **ولا تُخفّض عتبة.** `FIELD_THRESHOLDS` كما هي.
  • **ولا تُجنّس الصفوفَ التاريخية.** مرشّحٌ محفوظٌ بثقةٍ فارغة يبقى
    مستبعَدًا مغلقًا — والفحصُ يطلب ذلك صراحةً.
  • **ولا تتحدّث إلى مزوّدٍ حيّ.** ولا تدّعي أنّها فعلت.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db

# **وتجهيزاتُ الرسالة الحديثة لا تُنسخ** — تُستورَد من حزمة جسر المعرفة.
# ونسخُها هنا يخلق مصدرًا ثانيًا للحقيقة عن شكل الصفوف التي يكتبها خطُّ
# المستندات، فيفترق المصدران وتمرّ الفحوصُ على شكلٍ لا يقع في الإنتاج.
from tests.test_at_thesis_canonical_bridge import (  # noqa: PLC2701
    CONSTRUCT_ONE,
    CONSTRUCT_TWO,
    FINDING,
    POPULATION,
    QUESTION_ONE,
    QUESTION_TWO,
    TITLE,
    _candidate,
    _card,
    _chunk,
    _client,
    _machine_thesis,
    _mined_at,
    _mining_state,
    _seed,
)

# ═════════════════════ تجهيزةُ الخزن: لا MinIO في CI ═════════════════════


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    """المزوّدُ الذاكريّ — والتجهيزةُ المنسوخة عن الحزم القائمة عمدًا.

    التجهيزاتُ التلقائية لا تعبُر بين الوحدات، فلا تُستورَد من حزمةٍ أخرى.
    """
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


# ═════════════════════ أدواتٌ صافية: أهليّةٌ بلا قاعدة ═════════════════════
#
# **وتُبنى كائناتُ الإنتاج نفسُها غيرَ محفوظة.** لا أشباهٌ تُصنع بيدٍ: شبهٌ
# يقبل ما ترفضه القاعدةُ يجعل الفحصَ يشهد لشكلٍ لا يقع.

CHUNK_TEXT = " ".join([
    TITLE, QUESTION_ONE, QUESTION_TWO, FINDING,
    CONSTRUCT_ONE, CONSTRUCT_TWO, POPULATION,
])


def _parts(tenant_id=None, file_id=None, run_status="awaiting_review",
           chunk_text=CHUNK_TEXT):
    """تشغيلةٌ ومقطعٌ متّسقان — الأصلُ الذي تُقاس عليه الحالات."""
    from athera_api.models.research import DocumentChunk, ExtractionRun

    tenant_id = tenant_id or uuid.uuid4()
    file_id = file_id or uuid.uuid4()
    run = ExtractionRun(id=uuid.uuid4(), tenant_id=tenant_id, file_id=file_id,
                        extractor="model", status=run_status)
    chunk = DocumentChunk(id=uuid.uuid4(), tenant_id=tenant_id, file_id=file_id,
                          seq=1, text=chunk_text, locator="p.1", page_number=1,
                          char_count=len(chunk_text))
    return tenant_id, file_id, run, chunk


def _fact(tenant_id, file_id, run, chunk, *, field_key, value, confidence,
          quote=None, status="unverified", extraction="extracted"):
    """مرشّحٌ بالشكل الذي يكتبه خطُّ المستندات — `extraction_status` في `value`."""
    from athera_api.models.research import FactCandidate

    return FactCandidate(
        id=uuid.uuid4(), tenant_id=tenant_id, extraction_run_id=run.id,
        file_id=file_id, chunk_id=chunk.id, memory_category="project_decision",
        field_key=field_key, statement_ar=str(value),
        value={"value": value, "extraction_status": extraction},
        quote=chunk.text[:200] if quote is None else quote,
        locator=chunk.locator, confidence=confidence, status=status)


def _verdict(candidate, tenant_id, file_id, run, chunk):
    """**المصنّفُ الإنتاجيّ نفسُه** — ولا نسخةَ منطقٍ في الاختبار."""
    from athera_api.services.thesis import fact_eligibility as policy
    from athera_api.services.thesis.canonical_facts import READ_KEYS, _texts

    return policy.classify(
        candidate, tenant_id=tenant_id, file_id=file_id, run=run, chunk=chunk,
        memory=None, known_fields=READ_KEYS, texts=_texts(candidate))


# ═════════════════ ١ · العقد: ما ادّعى أنّه استُخرج يحمل ثقته ═════════════════


def test_an_extracted_field_without_confidence_is_rejected_not_defaulted():
    """**برهانُ (١): مخرَجٌ أغفل الثقةَ يُرفض — ولا يُكمَّل بقيمة.**

    وهذه هي الحلقةُ الأولى في السلسلة. كانت `default=None` تقبله بصمت،
    فيمضي «ناجحًا» إلى القاعدة بثقةٍ فارغة.

    ولا تُختبر الرسالةُ حرفًا: يُختبر أنّ الرفضَ وقع وأنّ اسمَ الحقل فيه،
    فيُقرأ في السجلّ أيُّ حقلٍ خالف العقد.
    """
    from pydantic import ValidationError

    from athera_api.services.document_intelligence.contracts import (
        STATUS_EXTRACTED,
        ExtractedField,
    )

    with pytest.raises(ValidationError) as caught:
        ExtractedField(field_key="primary_findings", status=STATUS_EXTRACTED,
                       value=[FINDING], quote=FINDING)

    assert "extraction_confidence" in str(caught.value)
    assert "primary_findings" in str(caught.value), "الرفضُ لا يقول أيُّ حقلٍ خالف"


def test_a_whole_batch_is_rejected_when_one_extracted_field_omits_confidence():
    """والدفعةُ تُرفض بحقلٍ واحدٍ مخالف — **فلا يُحفظ نصفُ مخرَجٍ معطوب**.

    ويتولّى خطُّ المعالجة الرفضَ كما يتولّى أيَّ مخرَجٍ مخالفٍ للعقد:
    ‏`except Exception` في `pipeline.py` يسجّله فشلَ قسمٍ ولا يُسقط غيره.
    """
    from pydantic import ValidationError

    from athera_api.services.document_intelligence.contracts import ExtractionBatch

    payload = {"fields": [
        {"field_key": "title_ar", "status": "extracted", "value": TITLE,
         "quote": TITLE, "extraction_confidence": 0.94},
        # هذا وحده بلا ثقة.
        {"field_key": "questions", "status": "extracted",
         "value": [QUESTION_ONE], "quote": QUESTION_ONE},
    ]}
    with pytest.raises(ValidationError):
        ExtractionBatch.model_validate(payload)


def test_confidence_is_optional_only_for_fields_that_carry_no_value():
    """**والاشتراطُ على ما يدّعي أنّه استُخرج وحده.**

    ‏`not_found` وأختاها لا تحمل قيمةً أصلًا، فثقةُ استخراجٍ لم يقع لا
    معنى لها. واشتراطُها عليها كان سيُسقط أقسامًا سليمةً لا تجد الحقل.
    """
    from athera_api.services.document_intelligence.contracts import (
        STATUS_AMBIGUOUS,
        STATUS_NEEDS_REVIEW,
        STATUS_NOT_FOUND,
        ExtractedField,
    )

    for status in (STATUS_NOT_FOUND, STATUS_AMBIGUOUS, STATUS_NEEDS_REVIEW):
        field = ExtractedField(field_key="sample_size", status=status)
        assert field.extraction_confidence is None, "ثقةٌ اختُرعت لحقلٍ بلا قيمة"


def test_a_stated_zero_confidence_survives_as_exactly_zero():
    """**برهانُ (٢): `0.0` ثقةٌ قيلت، لا ثقةٌ غائبة.**

    وكان الشرطُ `if raw.get("confidence")` — صدقًا منطقيًّا لا حضورًا —
    فتصير الصفرُ `None`، فيُستبعد المرشّحُ بحجّة أنّ النموذج لم يقل ثقته،
    وقد قالها صراحةً: صفرًا. والفرقُ بينهما خبران: الأولى ثقةٌ ضعيفة
    تُصنَّف بعتبتها، والثانية عقدٌ مخالف.
    """
    from athera_api.services.document_intelligence.contracts import (
        STATUS_EXTRACTED,
        ExtractedField,
    )
    from athera_api.services.extraction.model import _confidence

    field = ExtractedField(field_key="sample_size", status=STATUS_EXTRACTED,
                           value="120", quote="120", extraction_confidence=0.0)
    assert field.extraction_confidence == 0.0
    assert field.extraction_confidence is not None

    # وفي المستخرِج الآخر كذلك — العطبُ كان فيه بحرفه.
    assert _confidence({"confidence": 0.0}) == 0.0
    assert _confidence({"confidence": 0.93}) == 0.93
    for absent in ({}, {"confidence": None}):
        with pytest.raises(KeyError):
            _confidence(absent)


def test_the_model_is_asked_for_confidence_as_a_required_field():
    """**وما لا يُشترَط في المخطَّط يُغفله النموذج.** فالعقدُ يُعلن مشترطًا.

    ويُفحص المدى أيضًا: ثقةٌ فوق الواحد أو تحت الصفر مخرَجٌ معطوب، ولا
    تُقصَّ إلى الحدّ فتصير رقمًا لم يقله أحد.
    """
    from athera_api.services.extraction.model import RESPONSE_SCHEMA, _confidence

    required = RESPONSE_SCHEMA["properties"]["facts"]["items"]["required"]
    assert "confidence" in required, "النموذجُ لا يُشترط عليه أن يقول ثقته"

    for outside in (1.5, -0.1):
        with pytest.raises(ValueError, match="out of range"):
            _confidence({"confidence": outside})


# ═════════════════ ٢ · الأهليّة: الاستبعادُ أصل، والأهليّةُ تُستحقّ ═════════════════


def test_a_grounded_high_confidence_fact_becomes_auto_eligible():
    """**برهانُ (٣): المؤصَّلُ العاليُ الثقة يصير `AUTO_ELIGIBLE` بلا اعتماد.**

    وهذه هي الحلقةُ التي كان انكسارُها يُفرغ المنقّب.
    """
    from athera_api.services.thesis import fact_eligibility as policy

    tenant_id, file_id, run, chunk = _parts()
    auto_min, _support = policy.thresholds_for("primary_findings")
    fact = _fact(tenant_id, file_id, run, chunk, field_key="primary_findings",
                 value=[FINDING], confidence=auto_min, quote=FINDING)

    verdict = _verdict(fact, tenant_id, file_id, run, chunk)
    assert verdict.classification == policy.AUTO_ELIGIBLE
    assert verdict.reason == "meets_field_threshold"
    assert verdict.eligible
    # **ولا يُدَّعى أنّ إنسانًا اعتمدها.**
    assert not verdict.from_human


def test_a_fact_below_the_field_threshold_keeps_its_safe_class():
    """**برهانُ (٤): ما دون العتبة يبقى في صنفه الآمن — ولا يُرفع.**

    ولا تُخفّض العتبةُ لأنّ المنقّبَ يشتهي دليلًا: `SUPPORT_ONLY` تُعين على
    السياق ولا تُنشئ فرصةً وحدها، وما دون سندِها يُستبعد.
    """
    from athera_api.services.thesis import fact_eligibility as policy

    tenant_id, file_id, run, chunk = _parts()
    auto_min, support_min = policy.thresholds_for("primary_findings")

    just_below = _fact(tenant_id, file_id, run, chunk, field_key="primary_findings",
                       value=[FINDING], confidence=auto_min - 0.01, quote=FINDING)
    verdict = _verdict(just_below, tenant_id, file_id, run, chunk)
    assert verdict.classification == policy.SUPPORT_ONLY
    assert verdict.reason == "below_auto_threshold"
    assert not verdict.eligible, "دليلٌ دون العتبة بلغ المنقّب"

    far_below = _fact(tenant_id, file_id, run, chunk, field_key="primary_findings",
                      value=[FINDING], confidence=support_min - 0.01, quote=FINDING)
    weak = _verdict(far_below, tenant_id, file_id, run, chunk)
    assert weak.classification == policy.EXCLUDED
    assert weak.reason == "below_support_threshold"


def test_high_confidence_never_buys_a_pass_on_grounding():
    """**برهانُ (٥): `0.99` مع اقتباسٍ غير مؤصَّل تُستبعد.**

    ‏`0.99` تقول «قرأتُ هذا النصَّ من المستند على الأرجح». ولا تشتري
    تجاوزًا لعطبٍ في التأصيل: اقتباسٌ لا يوجد في المقطع اختلاقٌ مهما
    عَلَت ثقتُه.
    """
    from athera_api.services.thesis import fact_eligibility as policy

    tenant_id, file_id, run, chunk = _parts()
    invented = _fact(
        tenant_id, file_id, run, chunk, field_key="primary_findings",
        value=["نتيجةٌ لا توجد في المقطع"], confidence=0.99,
        quote="اقتباسٌ لم يُكتب في هذا المستند قطّ ولا يوجد في مقطعه")

    verdict = _verdict(invented, tenant_id, file_id, run, chunk)
    assert verdict.classification == policy.EXCLUDED
    assert verdict.reason == "quote_not_grounded"


def test_a_candidate_with_a_null_confidence_stays_fail_closed():
    """**والصفوفُ التاريخية لا تُجنَّس.** ثقةٌ فارغة تبقى مستبعَدةً مغلقًا.

    وهذا مطلوبٌ صراحةً: إصلاحُ العقد يمنع صفوفًا جديدةً فارغة، ولا
    يُرقّي القديمةَ إلى الأهليّة. ثقةٌ لم تُقَل لا تُخترع بعد حين.
    """
    from athera_api.services.thesis import fact_eligibility as policy

    tenant_id, file_id, run, chunk = _parts()
    historical = _fact(tenant_id, file_id, run, chunk, field_key="primary_findings",
                       value=[FINDING], confidence=None, quote=FINDING)

    verdict = _verdict(historical, tenant_id, file_id, run, chunk)
    assert verdict.classification == policy.EXCLUDED
    assert verdict.reason == "no_extraction_confidence"


# ═════════════════ ٣ · التعارضُ المادّيّ يُحجب مفهومًا لا رسالة ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_a_material_conflict_keeps_the_concept_out_of_the_canonical_set(two_tenants):
    """**برهانُ (٦): حقيقتان متعارضتان ماديًّا لا تصير أيُّهما كنسيّة.**

    ولا تُعطَّل الرسالةُ كلُّها: المفهومُ المعنيّ وحده يُحجب، وتبقى بقيّةُ
    الحقائق مؤهَّلةً — وهو ما يفصله `facts_withheld_for_conflict`.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts
    from athera_api.services.thesis import fact_eligibility as policy

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _machine_thesis(tid, uid, title_ar=TITLE)

    # عيّنتان تُناقض إحداهما الأخرى ماديًّا — وكلتاهما عاليةُ الثقة.
    async with tenant_session(tid, uid) as session:
        body = "بلغ حجم العينة 120 مشاركًا. وبلغ حجم العينة 480 مشاركًا."
        chunk = await _chunk(session, tid, file_id, body, seq=2)
        for count in ("120", "480"):
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key="sample_size", value=count,
                             confidence=0.99, quote=body)

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert canonical.conflicts_detected == 1
    assert canonical.facts_withheld_for_conflict == 2
    assert canonical.reasons.get("material_conflict_for_concept") == 2
    assert canonical.counts.get(policy.REVIEW_REQUIRED, 0) >= 2
    # **ولا عيّنةَ في المجموعة الكنسيّة** — ولا واحدةٌ منهما «فازت».
    assert not canonical.facts.sample_ids
    # وبقيّةُ الحقائق باقيةٌ مؤهَّلة: حُجب مفهومٌ لا رسالة.
    assert canonical.eligible_facts_used > 0
    assert canonical.has_evidence


# ═════════════════ ٤ · من الأهليّة إلى الفرصة بلا اعتمادٍ لكلِّ واقعة ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_auto_eligible_facts_reach_the_miner_with_zero_per_fact_approvals(two_tenants):
    """**برهانا (٧) و(٨): المؤهَّلُ آليًّا يصير كنسيًّا ويبلغ المنقّب.**

    ولا `approve_candidate` واحدة، ولا `ResearcherMemory` واحدة: هذا
    بالضبط ما صار مؤهَّلًا بعد تحوّل السياسة — **الباحثُ يعتمد القراراتِ
    العلمية لا كلَّ استخراجٍ آليٍّ وسيط**.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.services.thesis import canonical_facts
    from athera_api.services.thesis import fact_eligibility as policy

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _machine_thesis(tid, uid, title_ar=TITLE)

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)
        approvals = (await session.execute(
            select(func.count(ResearcherMemory.id))
            .where(ResearcherMemory.source_file_id == file_id))).scalar_one()

    # ٧ · صُنّفت مؤهَّلةً آليًّا، ولا يدَ إنسانٍ في ذلك.
    assert approvals == 0, "اعتُمدت واقعةٌ بيد — فالفحصُ لا يقيس المسارَ الآليّ"
    assert canonical.counts.get(policy.AUTO_ELIGIBLE, 0) > 0
    assert canonical.approved_verified_used == 0
    assert canonical.eligible_facts_used > 0

    # ٨ · وبلغت المجموعةُ الكنسيّةُ المنقّبَ بمضمونها لا بعددها وحده.
    facts = canonical.facts
    assert facts.questions, "أسئلةُ الرسالة لم تبلغ المنقّب"
    assert facts.results, "نتائجُ الرسالة لم تبلغ المنقّب"
    assert facts.construct_refs, "بناءاتُ الرسالة لم تبلغ المنقّب"
    assert canonical.processing_scope == policy.SCOPE_ADVANCED


# ═════════════════════ ٥ · حصادُ التصنيف: بالصنف وبالسبب ═════════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_classification_tally_names_every_class_and_every_reason(two_tenants):
    """**والحصادُ يُقرأ بالصنف وبالسبب** — وبه يُعرف أين انكسرت السلسلة.

    ولا منطقَ تصنيفٍ ثانٍ هنا: الحصادُ يبنيه `canonical_facts.load` من
    `fact_eligibility.classify` نفسِه، ويُودَع في سجلّ التدقيق. ونسخُه في
    الاختبار كان سيشهد لمنطقٍ لا يُشغَّل.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts
    from athera_api.services.thesis import fact_eligibility as policy

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    # دفعةٌ مختلطة: مؤهَّلٌ عالٍ، ومعينٌ دون العتبة، ومستبعَدٌ ضعيف.
    thesis_id, file_id, _run = await _machine_thesis(
        tid, uid, title_ar=TITLE, confidence=0.97,
        extra=(("hypotheses", ["فرضيةٌ دون عتبة الترقية"], 0.80),
               ("instruments", ["أداةٌ ضعيفةُ الثقة"], 0.50)))

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    # الأصنافُ مفاتيحُ الحصاد، ومجموعُها كلُّ ما صُنِّف.
    assert set(canonical.counts) <= {
        policy.AUTO_ELIGIBLE, policy.SUPPORT_ONLY,
        policy.REVIEW_REQUIRED, policy.EXCLUDED}
    assert canonical.counts.get(policy.AUTO_ELIGIBLE, 0) >= 4
    assert canonical.counts.get(policy.SUPPORT_ONLY, 0) >= 1
    assert canonical.counts.get(policy.EXCLUDED, 0) >= 1

    # **والسببُ باسمه لكلِّ ما لم يُؤهَّل** — لا «مستبعَد» مجرَّدة.
    assert canonical.reasons.get("below_auto_threshold", 0) >= 1
    assert canonical.reasons.get("below_support_threshold", 0) >= 1
    # ولا سببَ يُسجَّل لمؤهَّل: الحصادُ يشرح المنعَ لا الإذن.
    assert sum(canonical.reasons.values()) == (
        sum(canonical.counts.values()) - canonical.counts.get(policy.AUTO_ELIGIBLE, 0))


@requires_db
@pytest.mark.asyncio
async def test_the_audit_record_carries_the_tally_by_class_and_reason(two_tenants):
    """والحصادُ يُودَع في التدقيق — **فيُقرأ بعد حين، لا في لحظته وحدها**.

    وبه يُشخَّص ما وقع لرسالةٍ بعينها في الإنتاج بلا تخمين: أيُّ صنفٍ
    كم، وأيُّ سببٍ كم.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.audit import AuditEvent
    from athera_api.services.thesis import fact_eligibility as policy

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _machine_thesis(tid, uid, title_ar=TITLE)

    async with _client(tid, uid) as client:
        assert (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202

    async with tenant_session(tid, uid) as session:
        rows = (await session.execute(
            select(AuditEvent.state_after)
            .where(AuditEvent.object_id == thesis_id,
                   AuditEvent.action == "thesis.opportunities_mined")
            .order_by(AuditEvent.occurred_at.desc()))).scalars().all()

    assert rows, "لا أثرَ تدقيقٍ لتنقيبٍ وقع"
    state = rows[0]
    assert state["classification_counts"].get(policy.AUTO_ELIGIBLE, 0) > 0
    assert "exclusion_reasons" in state
    assert state["eligible_facts_used"] > 0
    # والحالُ المحفوظة تُودَع في الأثر كما كُتبت — فيُقرأ بعد حينٍ ما وقع.
    from athera_api.services.thesis import mining

    assert state["mining_state"] == mining.COMPLETED
    assert state["processing_scope"] == policy.SCOPE_ADVANCED


# ═════════════════ ٦ · حالُ التنقيب تصف التنقيب — ولا تكذب ═════════════════


@requires_db
@pytest.mark.asyncio
async def test_mining_never_writes_not_started_after_it_has_run(two_tenants):
    """**ولا «لم يبدأ» بعد تشغيلٍ وقع** — في كلِّ مخرَجٍ ممكن.

    وهذه هي الكذبةُ بعينها: `mining.run` **هي** التشغيل، فبلوغُ سطرِ
    الحال يعني أنّ الحقائقَ حُمِّلت وصُنِّفت وجرى التنقيب. فيُفحص
    المخرَجان الحدّيان معًا: دليلٌ مؤهَّل، ولا دليلَ مؤهَّل.
    """
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    rich, _f1, _r1 = await _machine_thesis(tid, uid, title_ar=TITLE,
                                           filename="غنيّة.pdf")
    barren, _f2, _r2 = await _machine_thesis(tid, uid, title_ar=TITLE,
                                             confidence=0.40, filename="فقيرة.pdf")

    async with _client(tid, uid) as client:
        for thesis_id in (rich, barren):
            assert (await client.post(
                f"/api/v1/theses/{thesis_id}/mine-opportunities")).status_code == 202

    for thesis_id, label in ((rich, "دليلٌ مؤهَّل"), (barren, "لا دليلَ مؤهَّل")):
        state = await _mining_state(tid, uid, thesis_id)
        assert state != mining.NOT_STARTED, (
            f"كُتبت «لم يبدأ» بعد تنقيبٍ وقع ({label})")
        assert state in mining.STATES


@requires_db
@pytest.mark.asyncio
async def test_zero_eligible_evidence_is_told_as_itself_in_both_languages(two_tenants):
    """**والحالُ الصادقة تبلغ الباحثَ بلغتيه** — نصًّا متعاقَدًا عليه.

    ولا «لم يبدأ» (تَعِد بخطوةٍ قادمة)، ولا «اكتمل» (وما اكتمل شيء)،
    ولا «تعذّر التحليل» (والتحليلُ تمّ). بل: اكتمل التحليل، ولم يتوفّر
    دليلٌ مؤهَّل.
    """
    from athera_api.services.thesis import card_actions, mining, processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _machine_thesis(tid, uid, title_ar=TITLE,
                                              confidence=0.40)

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["eligible_facts_used"] == 0
    assert body["outcome"] == mining.OUTCOME_NO_ELIGIBLE_EVIDENCE
    assert body["mining_state"] == mining.NO_ELIGIBLE_EVIDENCE
    # ولا ختمَ فحصٍ على دليلٍ مؤهَّل — إذ لم يكن ثمّة واحد.
    assert await _mined_at(tid, uid, thesis_id) is None

    expected = {
        "ar": processing.AR_NO_ELIGIBLE_EVIDENCE,
        "en": processing.EN_NO_ELIGIBLE_EVIDENCE,
    }
    for locale, sentence in expected.items():
        card = await _card(tid, uid, thesis_id, locale=locale)
        assert card["mining_state"] == mining.NO_ELIGIBLE_EVIDENCE
        assert card["opportunities_outcome"] == processing.OUTCOME_NO_ELIGIBLE_EVIDENCE
        assert card["opportunities_outcome_label"] == sentence
        # وسطحُ البطاقة يقول الواقعةَ نفسَها، ويبدأ بالجملة المتعاقَد عليها.
        assert card["actions"]["mining_state"] == (
            card_actions.MINING_NO_ELIGIBLE_EVIDENCE)
        assert card["actions"]["mining_reason"].startswith(sentence)
        # **وبابُ الاستكمال يبقى مفتوحًا**: الاستبعادُ حالُ دليلٍ لا حالُ عالَم.
        assert card["actions"]["can_mine"] is True


def test_the_new_state_agrees_across_every_module_and_the_migration():
    """**ومفردةٌ واحدة في خمسة مواضع تتفرّق بصمت** — فتُقابل هنا.

    الحالُ المحفوظة، وسطحُ البطاقة، وأثرُ التنقيب، وسببُ العدد، وقيدُ
    القاعدة: خمسةُ نصوصٍ للواقعة الواحدة. واختلافُ حرفٍ في أحدها يجعل
    الشاشةَ تسقط إلى فرعٍ خاطئ بلا خطأٍ يُرفع.
    """
    import pathlib

    from athera_api.services.thesis import card_actions, mining, processing

    word = "no_eligible_evidence"
    assert mining.NO_ELIGIBLE_EVIDENCE == word
    assert mining.OUTCOME_NO_ELIGIBLE_EVIDENCE == word
    assert processing.MINED_NO_ELIGIBLE_EVIDENCE == word
    assert processing.OUTCOME_NO_ELIGIBLE_EVIDENCE == word
    assert card_actions.MINING_NO_ELIGIBLE_EVIDENCE == word

    assert mining.NO_ELIGIBLE_EVIDENCE in mining.STATES
    assert word in card_actions.MINING_STATES
    assert word in processing.OPPORTUNITY_OUTCOMES
    # **ولا مفردةَ تنقيبٍ في مجال الأقسام**: قسمٌ لا يُقال عنه غيرُ مؤهَّل.
    assert word not in processing.OUTCOMES

    # والعمودُ يتّسع لها في النموذج — `String(16)` كانت تقتطعها.
    from athera_api.models.thesis import Thesis

    assert Thesis.__table__.c.mining_state.type.length >= len(word)

    # وقيدُ القاعدة يعرفها (ترحيل 0032) — يُقرأ من الملفّ لا من القاعدة،
    # فيعضّ الفحصُ في بيئةٍ بلا PostgreSQL أيضًا.
    root = pathlib.Path(__file__).resolve().parents[3]
    body = (root / "infra" / "db" / "migrations" / "versions"
            / "0032_mining_state_no_eligible_evidence.py").read_text(encoding="utf-8")
    assert f'"{word}"' in body
    assert "STATES_0032" in body
    # والتراجعُ يُخفّض الصفوفَ ولا يُسقطها.
    downgrade = body[body.index("def downgrade()"):]
    assert "UPDATE theses SET mining_state = 'withheld'" in downgrade


def test_every_stored_mining_state_has_a_card_surface_and_both_languages():
    """**وحالٌ محفوظةٌ بلا سطحٍ تُعرض رمزًا آليًّا** في وجه الباحث.

    فتُقابل كلُّ مفردةٍ مخزَّنة بسطحٍ يقرؤه، وكلُّ سطحٍ بنصّيه.
    """
    from athera_api.services.thesis import card_actions, mining

    for state in mining.STATES:
        surface = card_actions.mining_state(
            processing_state="ready_for_review", thesis_mining_state=state,
            opportunities=0, sections=0, results=0)
        assert surface in card_actions.MINING_STATES, f"حالٌ بلا سطح: {state}"

    for surface in card_actions.MINING_STATES:
        arabic, english = card_actions.MINING_LABELS[surface]
        assert arabic.strip() and english.strip(), f"سطحٌ بلا نصّ: {surface}"
        assert arabic != english


# ═════════════════════ ٧ · المسارُ الذهبيّ كاملًا ═════════════════════


@requires_db
@pytest.mark.asyncio
async def test_the_golden_path_runs_from_eligible_evidence_to_a_real_opportunity(
        two_tenants):
    """**المسارُ الذهبيّ: دليلٌ مؤهَّل ← كنسيّ ← تنقيبٌ ← فرصةٌ واحدة على الأقلّ.**

    وبلا اعتمادٍ لكلِّ واقعة، وبلا قرارٍ بشريٍّ واحد. وهذا هو المِحكُّ الذي
    يقول إنّ المسار الحقيقيَّ صار يعمل — لا خضرةُ حزمةٍ حول أجزائه.

    **وما يُفحص واقعةٌ محفوظة**: صفُّ فرصةٍ في القاعدة، لا جسدُ استجابة.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.research import ResearcherMemory
    from athera_api.models.thesis import PublicationOpportunity
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, _run = await _machine_thesis(tid, uid, title_ar=TITLE)

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")
        body = response.json()

    assert response.status_code == 202
    assert body["opportunities_created"] >= 1, "لم تتكوّن فرصةٌ واحدة"
    assert body["evidence_basis"] == "canonical"
    assert body["eligible_facts_used"] > 0
    assert body["mining_state"] == mining.COMPLETED

    async with tenant_session(tid, uid) as session:
        stored = (await session.execute(
            select(func.count(PublicationOpportunity.id))
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalar_one()
        approvals = (await session.execute(
            select(func.count(ResearcherMemory.id))
            .where(ResearcherMemory.source_file_id == file_id))).scalar_one()

    assert stored >= 1, "الاستجابةُ ادّعت فرصةً ولا صفَّ لها"
    assert approvals == 0, "لزِم اعتمادٌ بشريّ — والمسارُ الذهبيّ بلا اعتماد"
    assert await _mined_at(tid, uid, thesis_id) is not None
    assert await _mining_state(tid, uid, thesis_id) == mining.COMPLETED

    # والبطاقةُ تقول «فرصٌ قائمة» — واقعةٌ لا تُؤوَّل.
    card = await _card(tid, uid, thesis_id)
    assert card["opportunities_found"] >= 1
    assert card["opportunities_outcome"] == "found"
    assert card["actions"]["can_view_opportunities"] is True


@requires_db
@pytest.mark.asyncio
async def test_the_extraction_pipeline_mines_automatically_with_no_second_request(
        two_tenants):
    """**والتنقيبُ يبدأ من نفسه** — فلا زرَّ يطلب من الباحث تشغيلَ آلة.

    والمسارُ هو مسارُ الإنتاج: `_mine_after_extraction` بعد أن يستقرّ
    الاستخراجُ في القاعدة. ولا نداءَ ثانٍ في هذا الفحص.
    """
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis
    from athera_api.services.thesis import mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _f, _r = await _machine_thesis(tid, uid, title_ar=TITLE)

    async with tenant_session(tid, uid) as session:
        thesis = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        outcome = await mining.run(session, tenant_id=tid, actor_user_id=uid,
                                   thesis=thesis)

    assert outcome.created >= 1
    assert outcome.mining_state == mining.COMPLETED
    assert outcome.evidence_basis == "canonical"
    assert outcome.blocked_reason is None

    async with tenant_session(tid, uid) as session:
        stored = (await session.execute(
            select(func.count(PublicationOpportunity.id))
            .where(PublicationOpportunity.thesis_id == thesis_id))).scalar_one()
    assert stored == outcome.created, "الأثرُ يدّعي عددًا لا يطابق المحفوظ"


@requires_db
@pytest.mark.asyncio
async def test_a_thesis_whose_confidence_was_never_stored_yields_no_opportunity(
        two_tenants):
    """**ومسارُ الفشل كما وقع في الإنتاج بحرفه** — ثقةٌ فارغة في كلِّ حقل.

    وهذه إعادةُ بناءِ الحال قبل الإصلاح: العقدُ يمنعها اليوم من أن تُكتب،
    فتُزرع هنا مباشرةً في القاعدة لتُفحص السلسلةُ كاملةً بعدها. والمخرَجُ
    المطلوب: صفرُ فرص، وحالٌ تقول ذلك، **ولا «لم يبدأ»**.
    """
    from athera_api.db import tenant_session
    from athera_api.services.thesis import canonical_facts, mining

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(tid, uid, title_ar=TITLE,
                                             filename="بلا-ثقة.pdf")

    async with tenant_session(tid, uid) as session:
        chunk = await _chunk(session, tid, file_id, CHUNK_TEXT)
        for key, value in (("title_ar", TITLE),
                           ("questions", [QUESTION_ONE, QUESTION_TWO]),
                           ("constructs", [CONSTRUCT_ONE, CONSTRUCT_TWO]),
                           ("primary_findings", [FINDING])):
            await _candidate(session, tid, run_id=run_id, file_id=file_id,
                             chunk=chunk, field_key=key, value=value,
                             confidence=None)

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    # **كلُّها مستبعَدةٌ بالسبب نفسِه** — وهو تشخيصُ الإنتاج حرفًا.
    assert canonical.eligible_facts_used == 0
    assert canonical.reasons.get("no_extraction_confidence") == 4
    assert canonical.has_canonical_footprint

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["outcome"] == mining.OUTCOME_NO_ELIGIBLE_EVIDENCE
    assert await _mining_state(tid, uid, thesis_id) == mining.NO_ELIGIBLE_EVIDENCE
    assert await _mining_state(tid, uid, thesis_id) != mining.NOT_STARTED
