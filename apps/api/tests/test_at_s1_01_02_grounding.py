"""AT-S1-01/02 — TC-01 وحاجز الاختلاق (§43 TC-01، §4 No Fabrication).

هذان الاختباران يحرسان أثمن ما في المنتج: أن لا شيء يصير «حقيقة» بلا نص
داعم في المصدر وقرار إنسان.
"""
import pytest

from athera_api.services.extraction.base import (
    Candidate,
    enforce_grounding,
    normalize_for_match,
    quote_is_grounded,
)
from athera_api.services.extraction.rules import RuleBasedExtractor
from athera_api.services.parsing import ParsedChunk

pytestmark = pytest.mark.asyncio


def _chunk(text: str, seq: int = 1) -> ParsedChunk:
    return ParsedChunk(seq=seq, text=text, locator=f"p.1 ¶{seq}", page_number=1,
                       section_path=None, paragraph_index=seq)


def test_quote_present_in_source_is_grounded():
    chunk = _chunk("الباحث أستاذ مشارك في جامعة الإمام محمد بن سعود الإسلامية.")
    assert quote_is_grounded("أستاذ مشارك", chunk.text)


def test_quote_absent_from_source_is_rejected():
    """AT-S1-02 — الاقتباس المخترع لا يمر، مهما بدا معقولًا."""
    chunk = _chunk("الباحث أستاذ مشارك في جامعة الإمام محمد بن سعود الإسلامية.")
    assert not quote_is_grounded("حاصل على جائزة الملك فيصل العالمية", chunk.text)


def test_grounding_tolerates_diacritics_and_hamza_variants():
    """التطبيع للمطابقة فقط — لا يفتح بابًا لاقتباس مختلف المعنى."""
    chunk = _chunk("الباحثُ أستاذٌ مشاركٌ في قسم الإعلان.")
    assert quote_is_grounded("استاذ مشارك", chunk.text)
    assert not quote_is_grounded("أستاذ دكتور", chunk.text)


def test_normalization_does_not_collapse_distinct_claims():
    assert normalize_for_match("SPSS") != normalize_for_match("SmartPLS")


def test_enforce_grounding_splits_real_from_fabricated():
    chunks = {1: _chunk("يستخدم الباحث برنامج SPSS في التحليل الكمي.")}
    candidates = [
        Candidate(memory_category="researcher_fact", statement_ar="يستخدم SPSS",
                  quote="برنامج SPSS", chunk_seq=1),
        Candidate(memory_category="researcher_fact", statement_ar="يستخدم AMOS",
                  quote="برنامج AMOS", chunk_seq=1),          # مختلق
        Candidate(memory_category="researcher_fact", statement_ar="حقيقة من مقطع غير موجود",
                  quote="أي نص", chunk_seq=99),               # مقطع وهمي
    ]
    grounded, rejected = enforce_grounding(candidates, chunks)
    assert len(grounded) == 1 and grounded[0].quote == "برنامج SPSS"
    assert len(rejected) == 2


async def test_rule_extractor_output_is_always_unverified_candidates():
    """AT-S1-01 — المستخرِج لا ينتج حقائق، بل مرشّحات. الفرق ليس لفظيًا."""
    chunks = [
        _chunk("السيرة الذاتية: أستاذ مشارك، ORCID: 0000-0002-1825-0097، يستخدم SPSS وSmartPLS."),
    ]
    result = await RuleBasedExtractor().propose(chunks)
    assert result.candidates, "expected the deterministic extractor to find something"
    assert result.rejected_unquoted == []
    for candidate in result.candidates:
        # كل مرشّح يحمل اقتباسًا موجودًا حرفيًا — الحاجز طُبّق داخل المستخرِج.
        assert quote_is_grounded(candidate.quote, chunks[0].text)
        assert candidate.confidence is None or candidate.confidence < 1.0


async def test_extractor_finds_nothing_in_unrelated_text_instead_of_guessing():
    """القائمة الفارغة نتيجة صحيحة — والتخمين ليس كذلك."""
    chunks = [_chunk("هذا نص عن الطقس ولا يحتوي أي معلومة أكاديمية عن الباحث إطلاقًا.")]
    result = await RuleBasedExtractor().propose(chunks)
    assert result.candidates == []


# ── اختبار انحدار: خطأ وُجد بالتشغيل الفعلي ──

async def test_latin_token_preceded_by_arabic_conjunction_is_matched():
    r"""واو العطف الملتصقة بمصطلح لاتيني كانت تُسقط الالتقاط.

    في «SPSS وSmartPLS» لا يوجد حدّ كلمة (`\b`) بين «و» و«S» لأن كليهما حرف
    كلمة في Unicode. هذه صيغة كتابة عادية في السير الذاتية العربية، وكانت
    تعني ضياع نصف المهارات بصمت.
    """
    chunk = _chunk("يجيد الباحث استخدام SPSS وSmartPLS، وتدرّب على NVivo في التحليل الكيفي.")
    result = await RuleBasedExtractor().propose([chunk])
    names = {candidate.value.get("name") for candidate in result.candidates if candidate.value}
    assert {"SPSS", "SmartPLS", "NVivo"} <= names


async def test_shorter_token_inside_a_longer_one_is_not_double_counted():
    """«SEM» داخل «PLS-SEM» كان يُلتقط مرتين فينتفخ ملف المهارات بضجيج."""
    chunk = _chunk("اعتمدت الدراسة على PLS-SEM في اختبار النموذج البنائي المقترح.")
    result = await RuleBasedExtractor().propose([chunk])
    names = {candidate.value.get("name") for candidate in result.candidates if candidate.value}
    assert "PLS-SEM" in names
    assert "SEM" not in names


# ── اختبار انحدار: التطبيع يجب أن يحفظ الحروف ──

@pytest.mark.parametrize("letter", list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي") + list("ةىأإآءؤئ"))
def test_normalisation_never_deletes_an_arabic_letter(letter):
    """صنف حروف التشكيل ابتلع الحروف العربية نفسها في وحدة أخرى.

    الاختبارات القديمة لم تكشفه لأنها قارنت نصين **بعد** التطبيع: حين يصير
    الطرفان فارغين تتساوى المقارنة وتمر. الحارس الصحيح يؤكد أن التطبيع
    **يحفظ** الحروف، لا أن نتيجتين متطابقتان.
    """
    assert normalize_for_match(letter).strip() != ""


def test_normalisation_strips_diacritics_but_keeps_words():
    assert normalize_for_match("الباحثُ أستاذٌ مشاركٌ") == "الباحث استاذ مشارك"
    assert normalize_for_match("الإعلانـــات") == "الاعلانات"


def test_normalisation_of_a_real_sentence_is_not_empty():
    sentence = "الباحث أستاذ مشارك في قسم الإعلان والاتصال التسويقي"
    normalized = normalize_for_match(sentence)
    assert len(normalized) > 30
    assert "استاذ مشارك" in normalized
