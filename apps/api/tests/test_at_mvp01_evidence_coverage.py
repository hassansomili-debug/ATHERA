"""تغطيةُ الدليل المؤهَّل للتنقيب | Mining-grade evidence coverage (MVP-0.1 P0).

**الحاجزُ الوظيفيّ الحقيقيّ، كما قرأته سجلّاتُ الإنتاج — لا كما خُمِّن.**

فحصٌ للقراءة وحدها على صفوف الإنتاج قال ما يلي عن رسالتين رُفعتا فعلًا:

  رسالة (١): ٣٧ مرشّحًا · **ثقةٌ فارغة: صفر** · مؤهَّلٌ آليًّا: صفر
              unsupported_field_key ٢٦ · below_support_threshold ١٠
  رسالة (٢): ١١ مرشّحًا · **ثقةٌ فارغة: صفر** · مؤهَّلٌ آليًّا: صفر
              unsupported_field_key ٦ · below_auto_threshold ٣

فالثقةُ كانت محفوظةً في كلّ صفّ. **وعقدُ الثقة عطبٌ كامن، لا سببَ هذين
السقوطين** — ذاك ما صحّحه PR #121 في وصفه. والسببُ الوظيفيُّ شيءٌ آخر:

  **لا يبلغ التنقيبَ دليلٌ علميٌّ كافٍ ليصير `AUTO_ELIGIBLE`.**

و`unsupported_field_key` ليست عطبًا في ذاتها: ذكاءُ المستندات يستخرج عمدًا
حقولًا كثيرةً تنفع المراجعة ولا تصلح دليلًا علميًّا للنشر، و`READ_KEYS`
أضيقُ عمدًا. **ولا يُوسَّع `READ_KEYS` بحقولٍ إدارية لتخضرّ الأعداد** —
وفحصٌ هنا يمنع ذلك صراحةً.

## فأين ينكسر الخطّ؟ قبل النموذج، لا بعده

‏`select_chunks_for` لا يُرسل إلى النموذج إلّا مقاطعَ فيها **دليلٌ نصّيّ**
من `cues_ar`/`cues_en`. فحقلٌ لا يُطابق دليلُه نصَّ الرسالة **لا يراه
النموذجُ أصلًا** — لا يُستخرج بثقةٍ ضعيفة، بل لا يُسأل عنه.

وقياسٌ على الرسالة الإنجليزية الحقيقية (٣٤٨ مقطعًا، ١٨٥ صفحة) قال:

  ‏`questions`   → **صفرُ مقاطع**. والدليلُ الإنجليزيّ الوحيد كان
                  «research questions» جمعًا، والرسالةُ تقول
                  «research question» مفردًا ثلاثَ مرّات، والجمعَ **صفرًا**.
  ‏`constructs`  → **صفرُ مقاطع**. ولا دليلَ على «construct» أصلًا،
                  والرسالةُ تقولها أربعَ عشرةَ مرّة.
  ‏`sample_size` → **صفرُ مقاطع**، و«participants» فيها خمسُ مرّات.

فالعلاجُ ليس خفضَ عتبة ولا توسيعَ `READ_KEYS`: هو أن يرى النموذجُ النصَّ
الذي فيه الدليل. **والمفردُ يلتقط الجمعَ ولا عكس** — وذلك أكثرُ ما في
هذا الإصلاح.
"""
from __future__ import annotations

import os
import pathlib

import pytest

# ═════════════════════ المستندُ الحقيقيّ — اختياريٌّ ومُعلَن ═════════════════════

FIXTURE_ENV = "ATHERA_REAL_THESIS_PDF"
DEFAULT_PATH = "/Users/hassansomili/Downloads/Developing_an_Effective_Integr.pdf"


def _document() -> pathlib.Path | None:
    path = pathlib.Path(os.environ.get(FIXTURE_ENV) or DEFAULT_PATH).expanduser()
    return path if path.is_file() else None


requires_real_document = pytest.mark.skipif(
    _document() is None,
    reason=f"set {FIXTURE_ENV} to a real dissertation PDF to run this regression",
)

#: الحقولُ العلمية — `READ_KEYS` بلا العنوانين. والعنوانُ يُسمّي ولا يُنشئ
#: دليلًا (أُصلح في #121)، فلا يُقاس به دليلٌ علميّ هنا.
SCIENTIFIC_KEYS = (
    "questions", "hypotheses", "constructs", "instruments",
    "primary_findings", "hypothesis_results", "qualitative_themes",
    "population", "sample_size", "sampling",
)


@pytest.fixture(scope="module")
def views():
    path = _document()
    if path is None:
        pytest.skip(f"set {FIXTURE_ENV} to a real dissertation PDF")
    from athera_api.services import parsing
    from athera_api.services.document_intelligence.selection import ChunkView

    chunks = parsing.parse(path.read_bytes(), "application/pdf", path.name)
    return [
        ChunkView(chunk_id=str(i), seq=c.seq, text=c.text, locator=c.locator,
                  section_path=c.section_path, page_number=c.page_number)
        for i, c in enumerate(chunks)
    ]


# ═══════════ ١ · عقدُ المعايرة: ما يعنيه الرقم يُقال، لا يُخمَّن ═══════════


def test_the_prompt_defines_what_extraction_confidence_means():
    """**رقمٌ بلا تعريفٍ يملؤه النموذجُ بما يظنّه.**

    كانت المطالبة تطلب `extraction_confidence` ولا تقول ما هو. فيقيس
    نموذجٌ صحّةَ العلم، وآخرُ أهمّيةَ النتيجة، وثالثٌ وضوحَ النصّ — ثلاثةُ
    توزيعاتٍ تُقاس بعتبةٍ واحدة عُيِّرت على واحدٍ منها.
    """
    from athera_api.services.document_intelligence.pipeline import CONFIDENCE_CONTRACT

    # التعريفُ الموجَب: القيمةُ مذكورةٌ صراحةً، ومُسنَدةٌ إلى هذا الحقل.
    assert "extraction_confidence" in CONFIDENCE_CONTRACT
    assert "مذكورةٌ صراحةً" in CONFIDENCE_CONTRACT
    assert "مُسنَدةٌ إلى هذا الحقل" in CONFIDENCE_CONTRACT


def test_the_contract_says_what_the_number_is_not():
    """**والنفيُ جزءٌ من التعريف** — وهو ما كان يُملأ بالظنّ.

    أربعةُ معانٍ تُلبَس بالثقة: صحّةُ النتيجة، ودلالتُها الإحصائية،
    وأهمّيةُ الاكتشاف، وجودةُ الرسالة. وكلُّها تُنفى صراحةً.
    """
    from athera_api.services.document_intelligence.pipeline import CONFIDENCE_CONTRACT

    for denied in ("صحّةَ النتيجة", "الإحصائية", "أهمّيةَ", "جودةَ الرسالة"):
        assert denied in CONFIDENCE_CONTRACT, f"لم يُنفَ المعنى: {denied}"


def test_the_contract_offers_exits_instead_of_inflation():
    """**ولا يُطلب من النموذج رفعُ الأرقام** — بل تُفتح له المخارجُ الصادقة.

    فالتباسُ الإسناد `ambiguous`، وغيابُ الدليل `not_found`، ولا قيمةَ
    افتراضية. وعقدٌ يطلب ثقةً عاليةً بلا مخرجٍ للشكّ يُنتج تضخيمًا.
    """
    from athera_api.services.document_intelligence.pipeline import CONFIDENCE_CONTRACT

    assert "ambiguous" in CONFIDENCE_CONTRACT
    assert "not_found" in CONFIDENCE_CONTRACT
    assert "لا تخترع رقمًا افتراضيًّا" in CONFIDENCE_CONTRACT
    # والمدى معلَن: ما بين الصفر والواحد، وكلُّ `extracted` يحمله.
    assert "0.0" in CONFIDENCE_CONTRACT and "1.0" in CONFIDENCE_CONTRACT


def test_every_built_prompt_carries_the_calibration_contract():
    """**والتعريفُ في كلّ مطالبةٍ تُرسل** — لا في التوثيق وحده.

    ويُفحص على المطالبات المبنيّة فعلًا من `plan_sections`، لا على نصٍّ
    يُعاد تركيبه في الاختبار.
    """
    from athera_api.services.document_intelligence.pipeline import (
        CONFIDENCE_CONTRACT,
        plan_sections,
    )
    from athera_api.services.document_intelligence.selection import ChunkView

    body = ("The research question guiding this study is stated below. "
            "The construct was measured across participants. "
            "The findings indicate a relationship. Themes emerged.")
    views = [ChunkView(chunk_id=str(i), seq=i, text=body, locator=f"p.{i}",
                       section_path=None, page_number=i) for i in range(1, 6)]

    plans = plan_sections(views)
    assert plans, "لم تُبنَ مطالبةٌ واحدة"
    for plan in plans:
        assert CONFIDENCE_CONTRACT in plan.prompt, (
            f"قسمٌ بلا عقدِ معايرة: {plan.section.value}")
        # **والمقاطعُ تبقى موسومةً بيانات لا تعليمات** — الحدُّ الذي لا يُمسّ.
        assert "<DOCUMENT" in plan.prompt


# ═══════════ ٢ · `READ_KEYS` تبقى ضيّقةً — ولا تُوسَّع لتخضرّ الأعداد ═══════════


def test_administrative_fields_are_never_mining_evidence():
    """**و`unsupported_field_key` ليست عطبًا يُداوى بتوسيع القائمة.**

    الخلفيّةُ والدرجةُ والجامعةُ واسمُ الطالب والتوصياتُ حقولُ مراجعةٍ
    مشروعة، وليست دليلًا علميًّا لفرصةِ نشر. وإدخالُها في `READ_KEYS`
    يجعل العدّادَ أخضرَ ويجعل الفرصةَ مبنيّةً على اسم جامعة.
    """
    from athera_api.services.thesis.canonical_facts import READ_KEYS

    for administrative in (
        "background", "degree", "university", "college", "department",
        "student_name", "supervisors", "recommendations", "year",
        "defense_date", "limitations", "future_research", "software",
        "page_count", "source_filename",
    ):
        assert administrative not in READ_KEYS, (
            f"حقلٌ إداريّ دخل أدلّةَ التنقيب: {administrative}")


def test_the_scientific_read_keys_are_exactly_the_declared_set():
    """**وما يُعَدّ دليلًا علميًّا مُعلَنٌ ومقفول** — فلا يتسرّب حقلٌ بصمت."""
    from athera_api.services.thesis.canonical_facts import READ_KEYS, TITLE_KEYS

    assert set(READ_KEYS) - set(TITLE_KEYS) == set(SCIENTIFIC_KEYS)


def test_the_field_thresholds_were_not_lowered():
    """**ولا عتبةَ تُخفَّض لتصير الأعداد خضراء.** الحلُّ تغطيةٌ لا تساهل."""
    from athera_api.services.thesis.fact_eligibility import (
        DEFAULT_AUTO_MIN,
        DEFAULT_SUPPORT_MIN,
        FIELD_THRESHOLDS,
    )

    assert (DEFAULT_AUTO_MIN, DEFAULT_SUPPORT_MIN) == (0.85, 0.70)
    assert FIELD_THRESHOLDS["questions"] == (0.90, 0.75)
    assert FIELD_THRESHOLDS["primary_findings"] == (0.92, 0.80)
    assert FIELD_THRESHOLDS["sample_size"] == (0.95, 0.85)
    assert FIELD_THRESHOLDS["hypothesis_results"] == (0.95, 0.85)


# ═══════════ ٣ · الدليلُ النصّيّ: المفردُ يلتقط الجمعَ ولا عكس ═══════════


def test_mining_relevant_cues_prefer_singular_stems():
    """**الجمعُ دليلًا يُفوّت المفرد، والمفردُ يلتقطهما.**

    ‏«research questions» تحوي «research question»، فالمفردُ أوسعُ تغطيةً.
    وكان العكسُ هو الحال، فخرجت أسئلةُ رسالةٍ حقيقية بصفرِ مقاطع.
    """
    from athera_api.services.document_intelligence.fields import BY_KEY

    expected = {
        "questions": "research question",
        "constructs": "construct",
        "qualitative_themes": "theme",
    }
    for key, stem in expected.items():
        cues = BY_KEY[key].cues_en
        assert stem in cues, f"{key}: لا دليلَ مفردًا ({stem}) — الجمعُ يفوّت المفرد"
        # ولا دليلَ جمعٍ يكرّر ما يلتقطه المفردُ أصلًا.
        assert stem + "s" not in cues, f"{key}: دليلُ جمعٍ زائدٌ فوق المفرد"


def test_sample_and_sampling_cues_cover_standard_method_vocabulary():
    """**ووصفُ العيّنة لا يُقال بعبارةٍ واحدة.**

    «participants» و«respondents» وصفٌ قياسيّ، والرسالةُ الحقيقية تقول
    الأولى ولا تقول «sample size» قطّ. و«sampling» مفردةً تلتقط
    «purposive sampling» وأخواتِها.
    """
    from athera_api.services.document_intelligence.fields import BY_KEY

    assert "participants" in BY_KEY["sample_size"].cues_en
    assert "sampling" in BY_KEY["sampling"].cues_en


# ═══════════ ٤ · الانحدارُ على الرسالة الحقيقية ═══════════


@requires_real_document
def test_the_real_dissertation_now_reaches_the_model_for_its_science(views):
    """**والمِحكُّ مقاطعُ تصل النموذجَ فعلًا، لا دليلٌ يبدو معقولًا.**

    وقبل هذا الإصلاح: `questions` صفر، و`constructs` صفر،
    و`sample_size` صفر — ثلاثةُ حقولٍ علمية لم يُسأل النموذجُ عنها قطّ.
    """
    from athera_api.services.document_intelligence.fields import BY_KEY
    from athera_api.services.document_intelligence.selection import select_chunks_for

    for key in ("questions", "constructs", "sample_size"):
        picked = select_chunks_for(BY_KEY[key], list(views))
        assert picked, f"{key}: لا يزال صفرَ مقاطع — لا يراه النموذجُ أصلًا"

    # **والغيابُ الصادقُ يبقى غيابًا.** الرسالةُ لا تذكر أسلوبَ معاينةٍ
    # البتّة، فصفرُ مقاطعَ لـ`sampling` هو الجوابُ الصحيح — ولا يُصطنع
    # لها دليلٌ ليمتلئ العدّاد.
    text = "\n".join(v.text for v in views).lower()
    assert "sampling" not in text
    assert not select_chunks_for(BY_KEY["sampling"], list(views))


@requires_real_document
def test_widening_the_cues_did_not_flood_the_provider(views):
    """**وتغطيةٌ أوسعُ ليست إغراقًا.**

    الحدُّ `limit=4` لكلِّ حقل قائمٌ، والمقاطعُ تُوحَّد بين حقول القسم.
    فيبقى ما يُرسَل جزءًا صغيرًا من المستند — والفحصُ يقيسه لا يفترضه.
    """
    from athera_api.services.document_intelligence.pipeline import plan_sections

    plans = plan_sections(views)
    sent = sum(len(p.chunks) for p in plans)
    assert sent <= len(views) // 3, (
        f"يُرسَل {sent} من {len(views)} مقطعًا — توسعةٌ أغرقت المزوّد")
    # ولكلِّ قسمٍ مقاطعُه المحدودة، لا المستندُ كلُّه.
    for plan in plans:
        assert len(plan.chunks) <= 4 * len(plan.field_keys)
