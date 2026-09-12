"""انحدارٌ على رسالةٍ حقيقية | Regression on a real dissertation (MVP-0.1 P0).

**ولماذا مستندٌ حقيقيّ ولا يكفي التركيبيّ.**

النصوصُ التركيبية في بقيّة الحزم قصيرةٌ نظيفةٌ عربية، مكتوبةٌ لتُرضي
المُدخل. والمستندُ الذي أوقف المنتجَ في الإنتاج كان غيرَ ذلك: مئةٌ وخمسةٌ
وثمانون صفحةً بالإنجليزية، عنوانُها بأحرفٍ كبيرة، وفواصلُ صفحاتها ورؤوسُها
تدخل في النصّ، ومقاطعُها تُقطَّع حيث لا يقطّع كاتبُها.

فيُشغَّل هنا الخطُّ الحقيقيُّ على مستندٍ حقيقيّ: `parsing.parse` الفعليّ،
ومقاطعُه كما خرجت، واقتباساتٌ **مأخوذةٌ حرفًا من تلك المقاطع**، وتأصيلٌ
يُفحص بـ`quote_is_grounded` نفسِه، ثمّ أهليّةٌ بالمصنّف الإنتاجيّ.

## حدُّ هذا الفحص، مُعلَنًا

**حقولُ النموذج هنا مُعادةُ البناء — تجهيزةُ اختبارٍ مضبوطة (CONTROLLED
TEST FIXTURE).** لم يُستدعَ مزوّدٌ حيّ، ولا يُدَّعى أنّ نموذجًا أنتج هذه
الحقول. المأخوذُ من المستند حقيقيٌّ كلُّه: نصُّه، ومقاطعُه، وموضعُ كلِّ
اقتباس، وتأصيلُه. والمُعادُ بناؤه: **الحقلُ الذي يقابل الاقتباس وثقتُه** —
أي ما كان النموذجُ سيقوله عنه.

وهذا فصلٌ مقصود: ما يُفحص هو أنّ السلسلةَ بعد النموذج تعمل على مادّةٍ
حقيقية — العقد، والتأصيل، والأهليّة، والتنقيب — لا أنّ النموذج يقول صوابًا.
وذاك سؤالٌ آخر لا يُجاب بحزمةِ قبول.

## ولا تعتمد هذه الحزمةُ على مزوّدٍ حيّ ولا على شبكة

والمستندُ نفسُه خارجُ المستودع: رسالةُ دكتوراه لطرفٍ ثالث، ونسخُها في
مستودعٍ عامٍّ ليس لنا. فتُقرأ من مسارٍ يُعلَن في البيئة، وتُتخطّى الحزمةُ
بسببٍ صريح عند غيابه — على منهاج `ATHERA_LARGE_FILE_MB` القائم في
`test_at_large_file_upload.py`. **ولا تُعدّ متخطّاةً ناجحة.**
"""
from __future__ import annotations

import os
import pathlib

import pytest

from tests.conftest import requires_db
from tests.test_at_thesis_canonical_bridge import (  # noqa: PLC2701
    _candidate,
    _client,
    _mining_state,
    _seed,
)

#: مسارُ المستند — يُعلَن في البيئة، ولا يُخمَّن في المستودع.
FIXTURE_ENV = "ATHERA_REAL_THESIS_PDF"

#: والمسارُ الذي جرى عليه الانحدارُ في التطوير، افتراضًا حين لا يُعلَن شيء.
DEFAULT_PATH = "/Users/hassansomili/Downloads/Developing_an_Effective_Integr.pdf"


def _document() -> pathlib.Path | None:
    raw = os.environ.get(FIXTURE_ENV) or DEFAULT_PATH
    path = pathlib.Path(raw).expanduser()
    return path if path.is_file() else None


requires_real_document = pytest.mark.skipif(
    _document() is None,
    reason=f"set {FIXTURE_ENV} to a real dissertation PDF to run this regression",
)


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    from athera_api.config import get_settings
    from athera_api.services import storage

    monkeypatch.setattr(get_settings(), "storage_provider", "memory", raising=False)
    storage.reset_store_cache()
    yield
    storage.reset_store_cache()


@pytest.fixture(scope="module")
def parsed():
    """المستندُ كما يقرؤه الإنتاج — `parsing.parse` بلا وسيط."""
    path = _document()
    if path is None:
        pytest.skip(f"set {FIXTURE_ENV} to a real dissertation PDF")
    from athera_api.services import parsing

    data = path.read_bytes()
    return data, parsing.parse(data, "application/pdf", path.name)


# ═════════════════════ ١ · القراءةُ الحقيقية تقع فعلًا ═════════════════════


@requires_real_document
def test_the_real_document_parses_into_grounded_chunks(parsed):
    """**والقراءةُ حقيقية**: مقاطعُ ذاتُ مواضعَ من مستندٍ بمئةٍ وخمسٍ وثمانين صفحة.

    ولا OCR ولا طبقةَ نصٍّ مُختلَقة: ما يُقرأ هو طبقةُ نصِّ المستند.
    """
    data, chunks = parsed

    assert len(data) > 1_000_000, "المستندُ أصغرُ من أن يكون رسالةً كاملة"
    assert len(chunks) > 100, f"مقاطعُ قليلةٌ لرسالةٍ كاملة: {len(chunks)}"

    pages = [c.page_number for c in chunks if c.page_number]
    assert max(pages) >= 150, f"آخرُ صفحةٍ مقروءة {max(pages)} — القراءةُ ناقصة"
    # وموضعٌ لكلِّ مقطع: بلا موضعٍ لا تأصيل، وبلا تأصيلٍ لا أهليّة.
    assert all((c.locator or "").strip() for c in chunks), "مقطعٌ بلا موضع"
    assert all(c.text.strip() for c in chunks), "مقطعٌ فارغ"
    assert sum(len(c.text) for c in chunks) > 100_000


# ═════════════════════ ٢ · التأصيلُ يعضّ على النصّ الحقيقيّ ═════════════════════


@requires_real_document
def test_quotes_lifted_verbatim_are_grounded_and_invented_ones_are_not(parsed):
    """**والتأصيلُ يُقاس على نصٍّ حقيقيّ، لا على سلسلةٍ نظيفةٍ مكتوبةٍ لتنجح.**

    ونصُّ هذا المستند فيه ما يُعجز المطابقةَ الساذجة: أحرفٌ كبيرة،
    ومسافاتٌ مزدوجة، وعلاماتُ اقتباسٍ مُنمَّقة (`’`)، وأسطرٌ مقطوعة.
    """
    from athera_api.services.extraction.base import quote_is_grounded

    _data, chunks = parsed
    long_enough = [c for c in chunks if len(c.text) > 300]
    assert len(long_enough) > 20, "لا مقاطعَ طويلةً تكفي للقياس"

    for chunk in long_enough[:25]:
        verbatim = chunk.text[40:200]
        assert quote_is_grounded(verbatim, chunk.text), (
            f"اقتباسٌ مأخوذٌ حرفًا لم يُؤصَّل — {chunk.locator}")

    # **وما لم يُكتب في المستند لا يُؤصَّل** — ولو كان معقولًا في ذاته.
    invented = ("The study found a statistically significant effect of "
                "integrated marketing communication on brand recall.")
    assert not any(quote_is_grounded(invented, c.text) for c in chunks), (
        "اقتباسٌ مُختلَقٌ عُدّ مؤصَّلًا")


# ═════════════════════ ٣ · السلسلةُ كاملةً على مادّةٍ حقيقية ═════════════════════
#
# **تجهيزةُ اختبارٍ مضبوطة (CONTROLLED TEST FIXTURE).**
#
# الاقتباسُ والموضعُ من المستند الحقيقيّ. والحقلُ والثقةُ مُعادا البناء —
# لم يقلهما نموذج، ولا يُدَّعى ذلك.

#: حقولٌ تقابل مقاطعَ حقيقيةً في المستند، وثقاتُها **فوق عتبة كلِّ حقل**
#: (`FIELD_THRESHOLDS`) — ولم تُخفَّض عتبةٌ واحدة لأجل هذه الحزمة.
RECONSTRUCTED_FIELDS = (
    ("title_en", 0.94),
    ("questions", 0.93),
    ("constructs", 0.93),
    ("primary_findings", 0.95),
    ("population", 0.94),
)


def _pick_chunks(chunks, count):
    """أطولُ المقاطع — أكثرُها نصًّا يُقتبَس منه حرفًا."""
    ordered = sorted(chunks, key=lambda c: len(c.text), reverse=True)
    return ordered[:count]


@requires_db
@requires_real_document
@pytest.mark.asyncio
async def test_the_real_document_yields_auto_eligible_evidence_and_an_opportunity(
        two_tenants, parsed):
    """**المِحكُّ الأخير: مستندٌ حقيقيّ ← دليلٌ مؤهَّل ← فرصةُ نشرٍ واحدة على الأقلّ.**

    وبلا اعتمادٍ بشريٍّ لكلِّ واقعة، وبلا عتبةٍ خُفِّضت، وبلا اقتباسٍ
    مُختلَق: كلُّ اقتباسٍ هنا مأخوذٌ حرفًا من مقطعٍ حقيقيّ ويجتاز التأصيل.

    **وحقولُ النموذج مُعادةُ البناء** — CONTROLLED TEST FIXTURE، كما تُعلن
    حاشيةُ القسم أعلاه.
    """
    from athera_api.db import tenant_session
    from athera_api.models.research import DocumentChunk
    from athera_api.services.thesis import canonical_facts
    from athera_api.services.thesis import fact_eligibility as policy
    from athera_api.services.thesis import mining

    _data, chunks = parsed
    chosen = _pick_chunks(chunks, len(RECONSTRUCTED_FIELDS))

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(
        tid, uid, filename="Developing_an_Effective_Integr.pdf")

    async with tenant_session(tid, uid) as session:
        # ── المقاطعُ الحقيقية تُحفظ كما قرأها المحلِّل ──
        for source in chosen:
            row = DocumentChunk(
                tenant_id=tid, file_id=file_id, seq=source.seq, text=source.text,
                locator=source.locator, page_number=source.page_number,
                char_count=len(source.text))
            session.add(row)
            await session.flush()

            field_key, confidence = RECONSTRUCTED_FIELDS[chosen.index(source)]
            # **والاقتباسُ حرفٌ من هذا المقطع** — لا إعادةُ صياغة.
            verbatim = source.text[:300].strip()
            await _candidate(
                session, tid, run_id=run_id, file_id=file_id, chunk=row,
                field_key=field_key, value=[verbatim] if field_key != "title_en"
                else verbatim,
                confidence=confidence, quote=verbatim)

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    # ولا اقتباسَ سقط في التأصيل: المأخوذُ حرفًا يُؤصَّل كلُّه.
    assert canonical.reasons.get("quote_not_grounded", 0) == 0, (
        f"اقتباسٌ حرفيٌّ رُفض تأصيلًا: {canonical.reasons}")
    assert canonical.reasons.get("no_extraction_confidence", 0) == 0
    assert canonical.counts.get(policy.AUTO_ELIGIBLE, 0) >= 1, (
        f"لا دليلَ مؤهَّلًا من مستندٍ حقيقيّ: {canonical.counts} · {canonical.reasons}")
    assert canonical.eligible_facts_used >= 1
    assert canonical.approved_verified_used == 0, "لزِم اعتمادٌ بشريّ"

    async with _client(tid, uid) as client:
        response = await client.post(f"/api/v1/theses/{thesis_id}/mine-opportunities")
        body = response.json()

    assert response.status_code == 202
    assert body["evidence_basis"] == "canonical"
    assert body["eligible_facts_used"] >= 1
    assert body["opportunities_created"] >= 1, (
        f"مستندٌ حقيقيّ بدليلٍ مؤهَّل ولا فرصة: {body}")
    assert await _mining_state(tid, uid, thesis_id) == mining.COMPLETED


@requires_db
@requires_real_document
@pytest.mark.asyncio
async def test_the_same_real_document_with_no_confidence_stays_fail_closed(
        two_tenants, parsed):
    """**وعلى المادّة الحقيقية نفسِها: ثقةٌ غائبة تُوقف السلسلةَ كما أوقفتها.**

    فالفرقُ بين الفحص الذي قبله وهذا هو **الثقةُ وحدها** — لا المستند ولا
    المقاطعُ ولا الاقتباسات. وبه يُقرأ أثرُ الإصلاح معزولًا عن كلِّ ما عداه.
    """
    from athera_api.db import tenant_session
    from athera_api.models.research import DocumentChunk
    from athera_api.services.thesis import canonical_facts, mining

    _data, chunks = parsed
    chosen = _pick_chunks(chunks, len(RECONSTRUCTED_FIELDS))

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, file_id, run_id = await _seed(
        tid, uid, filename="Developing_an_Effective_Integr_no_confidence.pdf")

    async with tenant_session(tid, uid) as session:
        for index, source in enumerate(chosen):
            row = DocumentChunk(
                tenant_id=tid, file_id=file_id, seq=source.seq, text=source.text,
                locator=source.locator, page_number=source.page_number,
                char_count=len(source.text))
            session.add(row)
            await session.flush()
            field_key, _confidence = RECONSTRUCTED_FIELDS[index]
            verbatim = source.text[:300].strip()
            await _candidate(
                session, tid, run_id=run_id, file_id=file_id, chunk=row,
                field_key=field_key,
                value=[verbatim] if field_key != "title_en" else verbatim,
                # **الفرقُ الوحيد** — وهو ما كان يقع في الإنتاج.
                confidence=None, quote=verbatim)

    async with tenant_session(tid, uid) as session:
        canonical = await canonical_facts.load(
            session, tenant_id=tid, thesis_id=thesis_id, file_id=file_id)

    assert canonical.eligible_facts_used == 0
    assert canonical.reasons.get("no_extraction_confidence") == len(chosen)

    async with _client(tid, uid) as client:
        body = (await client.post(
            f"/api/v1/theses/{thesis_id}/mine-opportunities")).json()

    assert body["opportunities_created"] == 0
    assert body["outcome"] == mining.OUTCOME_NO_ELIGIBLE_EVIDENCE
    # **ولا «لم يبدأ» عن تنقيبٍ جرى على مستندٍ بمئةٍ وخمسٍ وثمانين صفحة.**
    state = await _mining_state(tid, uid, thesis_id)
    assert state == mining.NO_ELIGIBLE_EVIDENCE
    assert state != mining.NOT_STARTED
