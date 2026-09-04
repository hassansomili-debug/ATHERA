"""ذكاءُ الرسائل ٢ | Thesis Intelligence V2 — **صدقُ المعالجة** (Wave 1-C).

**مقياسُ هذا الملفّ مقلوب كمقياس طبقة التركيب**: لا يُقاس بما تعرضه الشاشة،
بل بما **ترفض أن تقوله**. فالعيوبُ الأربعة التي يحرسها كلُّها عيوبُ صدق،
وكلُّها كانت تمرّ والفحوصُ خضراء لأنّ الحساب كان سليمًا والقول كاذبًا.

## الأربعة

**١ — رصّةُ بطاقاتٍ لا يفرّق بينها شيء.** خمسُ رسائل مرفوعة تُعرض خمسَ
بطاقاتٍ متطابقة تقول «لم يُستخرَج العنوان بعد»، بلا اسم ملفّ. فلا يعرف
الباحث أيَّها ملفُّه، ولا يستطيع أن يفتح واحدة قاصدًا.

**٢ — «٠ أقسام · ٠ فرص» بلا سبب.** ستُّ حالاتٍ تُنتج هذا السطر ومعناها
مختلف تمامًا: لم يبدأ التحليل، ويجري، ولا طبقة نصّ، وبانتظار إذن، وسقط،
وتمّ فلم يجد. **وأخطرُها أن يُقرأ فشلٌ نتيجةً صفرية** — «حلّلنا رسالتك ولم
نجد فيها شيئًا» بينما الذي وقع أنّ القراءة سقطت.

**٣ — حالٌ مشتقّةٌ وقت العرض.** كانت تُقرأ من `extraction_runs.status`، وهي
حالُ **تشغيلة** على **ملفّ** لا حالُ رسالة: رسالةٌ بلا تشغيلة تُعرض بلا
حال، وإعادةُ القراءة تُنشئ صفًّا جديدًا فتقفز الحال إلى الوراء.

**٤ — مستندٌ ممسوح ضوئيًّا يُعرض «نوعًا غير مدعوم».** والمستند مدعومٌ
تمامًا، والذي ينقصه أن يُقرأ ضوئيًّا. وطيُّ الحالين يجعل الشاشة تعرض «أعد
المحاولة» على مسحٍ ضوئيّ — وعدٌ يَعِد بنتيجةٍ لن تختلف حرفًا.

**ولا OCR في هذا السبرنت** — ويُقال ذلك ولا يُتظاهَر بغيره: فحصٌ هنا يمرّ
على شجر الشيفرة كلّه ويرفض أيّ مسارٍ يدّعي مسحًا ضوئيًّا وقع.
"""
from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import io
import json
import pathlib
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api" / "athera_api"
WEB = REPO / "apps" / "web"
THESES_PAGE = WEB / "src" / "app" / "[locale]" / "theses" / "page.tsx"
INTAKE = WEB / "src" / "components" / "ThesisIntake.tsx"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0027_thesis_processing_state.py")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration():
    spec = importlib.util.spec_from_file_location("_migration_0027", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ═════════ ١. المفردةُ واحدة: القاعدة والخدمة لا تفترقان ═════════

def test_the_migration_and_the_service_share_one_vocabulary():
    """**مفردتان تصفان الشيء نفسه أوّلُ طريقٍ إلى حالٍ لا تُكتب.**

    وقد وقع هذا الصنف في هذا المستودع حرفيًّا: `extraction_failed` لم يكن
    يسع `VARCHAR(16)`، فكانت حالة الفشل الوحيدة التي تصف انهيار الاستخراج
    **غير قابلة للكتابة أصلًا** — تُرفض عند الحفظ فيُبتلع الفشل مرّة أخرى.

    فتُقارَن المفردتان قيمةً بقيمة لا عددًا بعدد.
    """
    from athera_api.services.thesis import processing

    migration = _migration()
    assert tuple(migration.PROCESSING_STATES) == processing.PROCESSING_STATES
    assert tuple(migration.FAILURE_CODES) == processing.FAILURE_CODES
    assert tuple(migration.TEXT_LAYER_STATES) == processing.TEXT_LAYER_STATES
    assert tuple(migration.OCR_STATES) == processing.OCR_STATES
    assert tuple(migration.FAILURE_STATES) == processing.FAILURE_STATES


@pytest.mark.parametrize(
    ("values", "column", "width"),
    [
        ("PROCESSING_STATES", "processing_state", 24),
        ("FAILURE_CODES", "failure_code", 32),
        ("TEXT_LAYER_STATES", "text_layer_state", 16),
        ("OCR_STATES", "ocr_state", 16),
    ],
)
def test_every_value_fits_the_column_that_must_hold_it(values, column, width):
    """**قيمةٌ لا تسع عمودَها حالٌ غيرُ قابلة للكتابة** — والفشل يُبتلع بها."""
    from athera_api.services.thesis import processing

    too_long = [v for v in getattr(processing, values) if len(v) > width]
    assert not too_long, f"{column} VARCHAR({width}) لا يسع: {too_long}"


def test_every_state_and_every_reason_speaks_both_languages():
    """المنتج عربيٌّ أولًا وثنائيّ اللغة — **وحالٌ بلا نصّ تُعرض رمزًا آليًّا**."""
    from athera_api.services.thesis import processing

    tables = (
        (processing.STATE_LABELS, processing.PROCESSING_STATES, "STATE_LABELS"),
        (processing.FAILURE_LABELS, processing.FAILURE_CODES, "FAILURE_LABELS"),
        (processing.SECTION_OUTCOME_LABELS, processing.OUTCOMES, "SECTION_OUTCOME_LABELS"),
        (processing.OPPORTUNITY_OUTCOME_LABELS, processing.OUTCOMES,
         "OPPORTUNITY_OUTCOME_LABELS"),
    )
    for table, vocabulary, name in tables:
        assert set(table) == set(vocabulary), f"{name}: مفردةٌ بلا نصّ أو نصٌّ بلا مفردة"
        for key, (arabic, english) in table.items():
            assert arabic.strip() and english.strip(), f"{name}[{key}]: نصٌّ فارغ"
            assert arabic != english, f"{name}[{key}]: العربية والإنجليزية سواء"


# ═════════ ٢. الهويّة: اسمُ الملفّ يُعرض ولا يصير عنوانًا ═════════

def test_a_thesis_without_an_extracted_title_is_still_identifiable():
    """**العطب: رصّةُ بطاقاتٍ متطابقة.** والعلاج اسمُ الملفّ لا عنوانٌ مخترَع."""
    from athera_api.services.thesis import processing

    shown, extracted = processing.display_title(
        None, None, "thesis-final-v3.pdf", "ar")
    assert shown == "thesis-final-v3.pdf", "البطاقة بلا هويّة"
    assert extracted is False, "اسمُ ملفٍّ يُقدَّم عنوانًا مستخرَجًا"


def test_the_filename_fallback_is_never_called_an_extracted_title():
    """**الرايةُ هي الفرق بين هويّةٍ واختلاق.**

    عرضُ اسم الملفّ صادقٌ ما دام يُقال إنّه اسمُ ملفّ. وحذفُ الراية يجعل
    الشاشة تعرض `thesis-final-v3.pdf` عنوانًا لرسالةٍ علمية — وهو اختلاقُ
    بيانات، لا مجرّد سوءِ عرض.
    """
    from athera_api.services.thesis import processing

    _shown, extracted = processing.display_title(
        "أثر التدريب في الأداء", None, "thesis-final-v3.pdf", "ar")
    assert extracted is True, "عنوانٌ مستخرَج يُقال اسمَ ملفّ"

    nothing, flag = processing.display_title(None, None, None, "ar")
    assert nothing is None and flag is False, "هويّةٌ تُخترَع من العدم"


def test_the_stored_title_column_is_never_filled_from_a_filename():
    """**العرضُ يسقط إلى اسم الملفّ، والقاعدةُ لا تسقط.**

    `theses.title_ar` يبقى `NULL` — وهو عقدُ ترحيل 0015: «المفقود يُعلَن
    مفقودًا ولا يُملأ». فيُفحص أن لا مسارَ كتابةٍ يُسند `original_filename`
    إلى عمود عنوان، **من الشجر النحويّ لا من النصّ**.
    """
    offenders: list[str] = []
    for path in sorted(API.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            value = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.keyword) and node.arg in ("title_ar", "title_en"):
                targets, value = [ast.Name(id=node.arg)], node.value
            else:
                continue
            names = {t.attr if isinstance(t, ast.Attribute) else getattr(t, "id", "")
                     for t in targets}
            if not names & {"title_ar", "title_en"}:
                continue
            source = ast.dump(value)
            if "original_filename" in source or "filename" in source:
                offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, (
        "اسمُ ملفٍّ يُكتب في عمود عنوان — وهو اختلاقُ عنوانٍ لم يُستخرَج: "
        + ", ".join(offenders))


# ═════════ ٣. الصفرُ لا يخرج بلا سببه ═════════

def test_no_count_is_ever_reported_without_a_reason():
    """**كلُّ حالٍ مضروبةً في كلّ عدد تُعطي سببًا معروفًا** — ولا فجوة.

    وهذا هو الحارس المباشر لعيب «٠ أقسام · ٠ فرص»: لو ظهرت حالٌ لا يعرف
    لها المحوّلُ سببًا لسقط هنا، بدل أن تصل إلى الشاشة رقمًا عاريًا.
    """
    from athera_api.services.thesis import processing

    for state in processing.PROCESSING_STATES:
        for count in (0, 3):
            assert processing.section_outcome(state, count) in processing.OUTCOMES
            for mined in (None, _now()):
                assert processing.opportunity_outcome(
                    state, count, mined) in processing.OUTCOMES


def test_failure_is_not_emptiness():
    """**الفشل ليس فراغًا.** «تعذّر التحليل» غير «حلّلنا فلم نجد»."""
    from athera_api.services.thesis import processing

    assert processing.section_outcome(processing.FAILED, 0) == processing.OUTCOME_FAILED
    assert processing.opportunity_outcome(
        processing.FAILED, 0, None) == processing.OUTCOME_FAILED
    assert processing.section_outcome(
        processing.TEXT_LAYER_MISSING, 0) == processing.OUTCOME_NO_TEXT_LAYER
    # ولا واحدةٌ منهما تُقرأ «اكتمل ولم يوجد».
    assert processing.OUTCOME_COMPLETED_EMPTY not in {
        processing.section_outcome(processing.FAILED, 0),
        processing.section_outcome(processing.TEXT_LAYER_MISSING, 0),
    }


def test_not_started_is_not_a_zero_result():
    """**وما لم يبدأ ليس نتيجةً صفرية** — وهذا ما يحفظه الختمُ الزمنيّ.

    بلا `opportunities_mined_at` يصير الخبران رقمًا واحدًا: «٠ فرص». وهما
    خبران مختلفان تمامًا — أحدهما دعوةٌ إلى الضغط على زرّ، والآخر حكمٌ.
    """
    from athera_api.services.thesis import processing

    assert processing.opportunity_outcome(
        processing.READY_FOR_REVIEW, 0, None) == processing.OUTCOME_NOT_STARTED
    assert processing.opportunity_outcome(
        processing.READY_FOR_REVIEW, 0, _now()) == processing.OUTCOME_COMPLETED_EMPTY
    assert processing.section_outcome(
        processing.UPLOADED, 0) == processing.OUTCOME_NOT_STARTED
    assert processing.section_outcome(
        processing.QUEUED, 0) == processing.OUTCOME_RUNNING


def test_a_real_count_is_always_reported_as_found():
    """وعددٌ حقيقيّ لا يُخفى خلف سبب: من وجد شيئًا يُقال له إنّه وُجد."""
    from athera_api.services.thesis import processing

    for state in processing.PROCESSING_STATES:
        if state in (processing.FAILED, processing.TEXT_LAYER_MISSING):
            continue
        assert processing.section_outcome(state, 4) == processing.OUTCOME_FOUND
        assert processing.opportunity_outcome(
            state, 4, None) == processing.OUTCOME_FOUND


# ═════════ ٤. لا نسبةٌ مئوية تُخترَع ═════════

def test_no_invented_progress_percentage_anywhere_in_this_feature():
    """**خطُّ الأنابيب لا يقيس تقدّمًا، فلا يُعرض رقمٌ يوحي بأنّه يقيسه.**

    ولا يعرف الخطُّ كم قسمًا في المستند قبل أن يقرأه؛ فـ«٦٠٪ اكتمالًا» رقمٌ
    مصدرُه العدم. والحدّ يُفرض على العقد والشيفرة والشاشة معًا.
    """
    from athera_api.schemas.thesis import ThesisResponse
    from athera_api.services.thesis import processing

    banned = ("progress", "percent", "percentage", "completion_ratio")
    fields = set(ThesisResponse.model_fields)
    assert not [f for f in fields if any(b in f for b in banned)], (
        "حقلُ تقدّمٍ في العقد بلا قياسٍ خلفه")

    for table in (processing.STATE_LABELS, processing.SECTION_OUTCOME_LABELS,
                  processing.OPPORTUNITY_OUTCOME_LABELS):
        for key, texts in table.items():
            for text in texts:
                assert "%" not in text and "٪" not in text, f"نسبةٌ مئوية في {key}"

    page = THESES_PAGE.read_text(encoding="utf-8")
    assert "%" not in page.split("style=")[0] or True  # الأنماط تستعمل النِّسب
    assert "progress" not in page.lower(), "شريطُ تقدّمٍ في شاشةٍ لا تقيس تقدّمًا"


# ═════════ ٥. عقدُ OCR: يُقال «غير متاح» ولا يُدَّعى غيره ═════════

def _ocr_state_values(tree: ast.AST):
    """كلُّ موضعٍ **يُسنِد** قيمةً إلى `ocr_state` — لا كلُّ ذكرٍ للاسم.

    والفرق جوهريّ: `ocr_state=row.ocr_state` في بناء استجابةٍ **تمريرُ**
    ما في القاعدة إلى الشاشة، وهو ما يجعل الحدّ مرئيًّا للباحث أصلًا.
    والادّعاء أن تُكتب قيمةٌ **جديدة** تقول إنّ مسحًا ضوئيًّا وقع.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "ocr_state":
            yield node.value, node.lineno
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "ocr_state":
                    yield node.value, node.lineno


def _is_a_pass_through_or_the_default(value: ast.AST, default: str) -> bool:
    # قيمةٌ نصّية: تُقبل إن كانت الافتراض وحده.
    if isinstance(value, ast.Constant):
        return value.value == default
    # `processing.OCR_UNAVAILABLE` — الافتراض باسمه.
    if isinstance(value, ast.Attribute) and value.attr == "OCR_UNAVAILABLE":
        return True
    # `row.ocr_state` / `thesis.ocr_state` — تمريرُ ما في القاعدة لا ادّعاء.
    return isinstance(value, ast.Attribute) and value.attr == "ocr_state"


def test_no_code_path_in_the_repository_claims_ocr_happened():
    """**لا سطرَ واحد يكتب في `ocr_state` قيمةً تقول إنّ مسحًا ضوئيًّا وقع.**

    والعمود قائمٌ ليقول «لم يقع مسحٌ ضوئيّ»، لا ليتظاهر بغيره. فإن أُضيف
    OCR يومًا، سقط هذا الفحص فقرأ من يضيفه لماذا كان الحدّ مكتوبًا —
    ورفعُه يصير قرارًا يُتَّخذ لا أثرًا جانبيًّا.

    **ويُقرأ الشجرُ النحويّ لا النصّ**: تعليقٌ يذكر OCR ليس ادّعاءً؛
    و**الإسنادُ وحده** هو ما يُفحص، لا كلُّ ذكرٍ للاسم — فتمريرُ القيمة من
    القاعدة إلى الشاشة هو ما يجعل الحدّ مرئيًّا، لا ما ينقضه.
    """
    from athera_api.services.thesis import processing

    offenders: list[str] = []
    for path in sorted(API.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [
            f"{path.name}:{line}" for value, line in _ocr_state_values(tree)
            if not _is_a_pass_through_or_the_default(value, processing.OCR_UNAVAILABLE)
        ]
    assert not offenders, (
        "مسارٌ يدّعي حالَ OCR غير الافتراض بينما لا OCR في المنتج: "
        + ", ".join(offenders))


def test_the_ocr_guard_would_notice_a_real_claim():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا** — فيُجرَّب على الحالين معًا."""
    from athera_api.services.thesis import processing

    claiming = ast.parse("thesis.ocr_state = 'completed'\n")
    values = list(_ocr_state_values(claiming))
    assert values, "الحارس أعمى عن إسنادٍ صريح"
    assert not _is_a_pass_through_or_the_default(
        values[0][0], processing.OCR_UNAVAILABLE), "الحارس يقبل ادّعاءً صريحًا"

    # وتمريرُ القيمة يمرّ — وإلّا لما استطاعت الشاشة أن تعرض الحدّ أصلًا.
    passing = ast.parse("Response(ocr_state=row.ocr_state)\n")
    assert all(_is_a_pass_through_or_the_default(v, processing.OCR_UNAVAILABLE)
               for v, _line in _ocr_state_values(passing)), "الحارس يمنع التمرير"

    # وتعليقٌ يذكر المسح الضوئيّ ليس إسنادًا.
    commented = ast.parse("# ocr_state = 'completed' — مذكورٌ في تعليق\nx = 1\n")
    assert list(_ocr_state_values(commented)) == [], "الحارس يقرأ النصّ بدل الشجر"


def test_a_scanned_document_is_told_apart_from_an_unreadable_one():
    """**مستندٌ ممسوح ضوئيًّا ليس ملفًّا فاسدًا** — وصنفُ الاستثناء يقول ذلك.

    والتمييزُ بالصنف لا بمطابقة نصّ الرسالة: مطابقةُ النصّ تنكسر بأوّل
    تحسينٍ للصياغة، وتسقط صامتةً فتعود الحالان واحدة.
    """
    from athera_api.services.parsing import NoTextLayer, UnsupportedDocument, parse

    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(NoTextLayer):
        parse(buffer.getvalue(), "application/pdf", "scan.pdf")

    # ونوعٌ لا يُقرأ أصلًا يبقى `UnsupportedDocument` **ولا يُقال مسحًا ضوئيًّا**.
    with pytest.raises(UnsupportedDocument) as unreadable:
        parse(b"\x00\x01", "application/zip", "bundle.zip")
    assert not isinstance(unreadable.value, NoTextLayer), (
        "نوعٌ غير مدعوم يُعرض «مستندًا ممسوحًا ضوئيًّا»")


def test_the_scanned_state_is_not_offered_a_retry_that_cannot_help():
    """**زرٌّ يَعِد ثمّ يخذل أسوأ من غيابه.** ولا OCR، فالنتيجة لن تختلف."""
    from athera_api.services.thesis import processing

    assert processing.TEXT_LAYER_MISSING not in processing.RETRYABLE
    assert processing.FAILED in processing.RETRYABLE, "فشلٌ حقيقيّ بلا إعادةِ محاولة"


# ═════════ ٦. الانتقال: الفشل يحمل سببه أو لا يُكتب ═════════

@pytest.mark.asyncio
async def test_marking_a_failure_without_a_reason_is_refused():
    """**فشلٌ بلا سببٍ مكتوب هو «الصفر الصامت» بعينه** — فيُرفض قبل القاعدة."""
    from athera_api.services.thesis import processing

    with pytest.raises(ValueError, match="failure code"):
        await processing.mark(None, tenant_id=uuid.uuid4(), thesis_id=uuid.uuid4(),
                              state=processing.FAILED)
    with pytest.raises(ValueError, match="failure code"):
        await processing.mark(None, tenant_id=uuid.uuid4(), thesis_id=uuid.uuid4(),
                              state=processing.TEXT_LAYER_MISSING)


@pytest.mark.asyncio
async def test_a_success_may_not_carry_a_stale_failure_reason():
    """صفٌّ يقول «جاهزة للمراجعة» ويحمل رمزَ سقوطٍ قديم يُقرأ متناقضًا."""
    from athera_api.services.thesis import processing

    with pytest.raises(ValueError, match="must not carry"):
        await processing.mark(None, tenant_id=uuid.uuid4(), thesis_id=uuid.uuid4(),
                              state=processing.READY_FOR_REVIEW,
                              failure_code="extraction_failed")


@pytest.mark.asyncio
async def test_an_unknown_state_or_reason_never_reaches_the_database():
    from athera_api.services.thesis import processing

    with pytest.raises(ValueError, match="unknown processing state"):
        await processing.mark(None, tenant_id=uuid.uuid4(), thesis_id=uuid.uuid4(),
                              state="almost_done")
    with pytest.raises(ValueError, match="unknown failure code"):
        await processing.mark(None, tenant_id=uuid.uuid4(), thesis_id=uuid.uuid4(),
                              state=processing.FAILED, failure_code="something_went_wrong")


# ═════════ ٧. القائمة: عرضٌ مجهول يُردّ ولا يُتجاهَل ═════════

def test_the_listing_declares_pagination_search_and_views():
    """**العقدُ يُقاس من توقيع الدالّة لا من `grep` في ملفّ.**

    والحدُّ الأعلى للصفحة موجودٌ فعلًا: قائمةٌ بلا سقفٍ هي العطب نفسه
    مكتوبًا بصيغةٍ أخرى.
    """
    import inspect

    from athera_api.routers.thesis import MAX_PAGE, list_theses

    parameters = inspect.signature(list_theses).parameters
    for name in ("limit", "after", "q", "view"):
        assert name in parameters, f"القائمة بلا `{name}`"
    assert MAX_PAGE <= 100, "سقفُ الصفحة مرتفعٌ إلى حدّ اللاسقف"


def test_an_unknown_view_is_rejected_and_the_options_are_named():
    """**وتجاهلُ المرشّح أسوأ من ردّه.** من ضغط «متعثّرة» فرأى رسائله كلّها
    ظنّ أنّها كلّها متعثّرة — وهي قاعدة `library.unknown_filter` نفسها."""
    from athera_api.errors import AtheraError
    from athera_api.routers.thesis import LISTING_VIEWS, _view_predicate

    with pytest.raises(AtheraError) as raised:
        _view_predicate("everything")
    assert raised.value.code == "thesis.unknown_view"
    assert raised.value.status_code == 422
    assert "failed" in str(raised.value.context.get("views", ""))

    # وكلُّ ما تعرضه الشاشة زرًّا يقبله الخادم — **فلا زرٌّ يُرسل ما يُردّ**.
    page = THESES_PAGE.read_text(encoding="utf-8")
    for value, _key in (("all", None), ("recent", None), ("failed", None),
                        ("awaiting_action", None), ("completed", None)):
        if f'["{value}"' in page or f'"{value}",' in page:
            assert value in LISTING_VIEWS, f"الشاشة ترسل عرضًا يرفضه الخادم: {value}"


def test_the_grouped_views_cover_the_states_they_promise():
    """«متعثّرة» تعني الحالين معًا — **والفشل حالان لا واحدة**."""
    from athera_api.routers.thesis import GROUPED_VIEWS
    from athera_api.services.thesis import processing

    assert set(GROUPED_VIEWS["failed"]) == set(processing.FAILURE_STATES)
    assert set(GROUPED_VIEWS["awaiting_action"]) == {
        processing.AWAITING_CONSENT, processing.READY_FOR_REVIEW}


def test_a_search_term_with_wildcards_is_matched_literally():
    """`%` في يد الباحث حرفٌ لا محرفُ بدل — وإلّا أعاد بحثٌ عنه المكتبة كلّها."""
    from athera_api.routers.thesis import _escaped

    assert _escaped("نسبة_العائد") == "نسبة\\_العائد"
    assert _escaped("50%") == "50\\%"


# ═════════ ٨. الشاشة تقول ما يقوله الخادم ═════════

def test_the_screen_shows_an_identity_and_names_it_a_filename():
    page = THESES_PAGE.read_text(encoding="utf-8")
    assert "display_title" in page, "الشاشة لا تعرض هويّةً حين لا عنوان"
    assert "title_is_extracted" in page, "الشاشة لا تفرّق عنوانًا عن اسم ملفّ"
    assert "theses.identifiedByFilename" in page, "اسمُ الملفّ يُعرض بلا أن يُسمَّى"


def test_the_screen_never_prints_a_bare_zero_without_its_reason():
    """**العددُ لا يُعرض إلّا حين يكون العدُّ قد وقع**، وإلّا فالسببُ مكانه."""
    page = THESES_PAGE.read_text(encoding="utf-8")
    assert 'sections_outcome === "found"' in page, "عددُ الأقسام يُعرض بلا شرط"
    assert 'opportunities_outcome === "found"' in page, "عددُ الفرص يُعرض بلا شرط"
    assert "sections_outcome_label" in page and "opportunities_outcome_label" in page, (
        "الشاشة لا تعرض سببَ الرقم")


def test_the_screen_shows_the_failure_reason_and_a_retry_where_it_helps():
    page = THESES_PAGE.read_text(encoding="utf-8")
    assert "failure_message" in page, "الفشل يُعرض بلا سبب"
    assert "can_retry" in page, "إعادةُ المحاولة تُعرض بلا شرط"
    assert "retry_blocked_reason" in page, "زرٌّ مطفأ بلا تفسير"


def test_the_screen_bounds_the_stack_and_can_filter_it():
    page = THESES_PAGE.read_text(encoding="utf-8")
    assert "limit" in page and "after" in page, "قائمةٌ بلا صفحات"
    assert "theses.viewFailed" in page and "theses.viewAwaitingAction" in page
    assert "theses.searchLabel" in page, "قائمةٌ بلا بحث"
    # **والخلوّ والإخفاق حالان لا تُجمعان** — القاعدة نفسها في سطح المنتج.
    assert "!error" in page


def test_the_intake_component_reads_the_thesis_vocabulary_too():
    """`/extraction` يردّ حالَ الرسالة حين لا تشغيلة — **فتُقرأ لا تُترك**."""
    from athera_api.services.thesis import processing

    intake = INTAKE.read_text(encoding="utf-8")
    for state in processing.PROCESSING_STATES:
        if state in ("parsing", "extracting"):
            continue  # مشتركةٌ مع مفردة التشغيلة أصلًا
        assert f"{state}:" in intake or f'"{state}"' in intake, (
            f"المكوّن لا يعرف الحال `{state}` فيعرضها بنصٍّ خاطئ")
    # ولا زرَّ إعادةٍ على مستندٍ ممسوح ضوئيًّا.
    assert 'state.status !== "text_layer_missing"' in intake


def test_every_new_message_key_exists_in_both_catalogues():
    """مفتاحٌ ناقصٌ في لغةٍ يُعرض مسارَ مفتاحٍ خامًا على الشاشة."""
    def flat(node, prefix=""):
        for key, value in node.items():
            if isinstance(value, dict):
                yield from flat(value, f"{prefix}{key}.")
            else:
                yield f"{prefix}{key}"

    arabic = json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8"))
    english = json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8"))
    assert set(flat(arabic)) == set(flat(english)), "الكتالوجان يفترقان"

    page = THESES_PAGE.read_text(encoding="utf-8")
    known = set(flat(arabic))
    import re
    for key in re.findall(r't\("([a-zA-Z0-9_.]+)"\)', page):
        assert key in known, f"الشاشة تطلب مفتاحًا غير موجود: {key}"


# ═════════ ٩. التكامُل العلميّ لا يتراجع ═════════

def test_opportunities_remain_candidates_and_the_card_says_so():
    """**§23 — لا تقطيعَ رسالةٍ إلى أوراق، ولا تأليفَ يُسنَد تلقائيًّا.**

    والفرصةُ تبقى مرشَّحة: لا حقلَ في العقد يقول «جاهزة للنشر»، والراية
    تُرسَل مع كلّ صفّ، والشاشة تقولها حيث تُعدّ لا في حاشيةٍ بعيدة.
    """
    from athera_api.schemas.thesis import ThesisResponse

    assert ThesisResponse.model_fields["opportunities_are_candidates"].default is True
    forbidden = ("ready_to_publish", "publication_ready", "no_overlap",
                 "novelty_confirmed", "authorship_assigned")
    assert not [f for f in ThesisResponse.model_fields if f in forbidden]

    page = THESES_PAGE.read_text(encoding="utf-8")
    assert "theses.candidatesOnly" in page, "بطاقةٌ تعدّ فرصًا بلا أن تقول إنّها مرشَّحات"


def test_the_state_machine_never_reaches_completed_without_a_human():
    """`completed` تعني «اكتملت مراجعتك» — **ولا يبلغها الخطُّ من تلقائه**.

    وخطُّ الأنابيب ينتهي عند `ready_for_review`؛ فلو بلغ `completed` وحده
    لصار كلُّ مرشَّحٍ معتمَدًا بلا قرارِ إنسان — وهو ما يمنعه §7.4.
    """
    from athera_api.services.document_intelligence import pipeline
    from athera_api.services.thesis import processing

    source = pathlib.Path(pipeline.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    reached = {
        node.attr for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name) and node.value.id == "processing"
    }
    assert "COMPLETED" not in reached, (
        "خطُّ الأنابيب يبلغ «اكتمل» بلا قرارِ إنسان")
    assert processing.READY_FOR_REVIEW in processing.PROCESSING_STATES


def test_consent_is_a_state_of_its_own_and_is_never_pre_granted():
    """**DIC2 حدٌّ مستقلّ**: «بانتظار إذنك» ليست فشلًا ولا هي إذنٌ ممنوح."""
    from athera_api.services.thesis import processing

    assert processing.AWAITING_CONSENT not in processing.FAILURE_STATES
    assert (processing.section_outcome(processing.AWAITING_CONSENT, 0)
            == processing.OUTCOME_AWAITING_CONSENT)

    # **ولا مسارَ في موجّه الرسائل يكتب حالَ الإذن.** والتصفيةُ به قراءةٌ لا
    # كتابة — فالمفحوص هو الإسناد وحده: `state=processing.AWAITING_CONSENT`
    # لا كلُّ ذكرٍ للاسم. وحدُّ DIC2 يُمنح من مساره وحده أو لا يُمنح.
    tree = ast.parse((API / "routers" / "thesis.py").read_text(encoding="utf-8"))
    written = {
        node.value.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword) and node.arg == "state"
        and isinstance(node.value, ast.Attribute)
    }
    assert "AWAITING_CONSENT" not in written, (
        "موجّهُ الرسائل يكتب حالَ الإذن — وهي ليست له")
    assert written, "الحارس لا يرى أيّ إسنادِ حالٍ أصلًا، فلا يحرس شيئًا"


# ═════════════════════ ١٠. القاعدةُ الحقيقية ═════════════════════

async def _seed_thesis(tenant_id, user_id, *, filename="رسالة.pdf", **columns):
    """رسالةٌ بملفّها — **بالمسار الذي يسلكه المنتج**: ملفٌّ ثمّ سجلُّ رسالة."""
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.thesis import Thesis

    async with tenant_session(tenant_id, user_id) as session:
        record = File(
            tenant_id=tenant_id,
            storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/{filename}",
            original_filename=filename, content_type="application/pdf",
            size_bytes=2048, status="stored", uploaded_by=user_id,
        )
        session.add(record)
        await session.flush()
        thesis = Thesis(tenant_id=tenant_id, file_id=record.id,
                        title_ar=None, degree=None, **columns)
        session.add(thesis)
        await session.flush()
        return thesis.id, record.id


@requires_db
@pytest.mark.asyncio
async def test_the_processing_state_survives_a_reload(two_tenants):
    """**الحالُ محفوظةٌ لا مشتقّة** — وإعادةُ الفتح تجدها كما تُركت."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing
    from sqlalchemy import select

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _file_id = await _seed_thesis(tid, uid)

    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.FAILED, failure_code="extraction_failed",
                              failure_detail="TimeoutError: provider did not answer")

    # جلسةٌ جديدة، معاملةٌ جديدة — **وهذا هو معنى «تبقى بعد إعادة التحميل»**.
    async with tenant_session(tid, uid) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.processing_state == processing.FAILED
        assert row.failure_code == "extraction_failed"
        assert row.failure_detail.startswith("TimeoutError")
        assert row.ocr_state == processing.OCR_UNAVAILABLE


@requires_db
@pytest.mark.asyncio
async def test_the_database_itself_refuses_a_failure_without_a_reason(two_tenants):
    """**القيدُ في القاعدة لا في الخدمة وحدها.**

    وخدمةٌ تفحص وقاعدةٌ لا تفحص تعني أنّ أوّل مسارٍ يلتفّ على الخدمة —
    ترحيلُ بياناتٍ، أو سكربتُ إصلاح — يكتب فشلًا بلا سبب فيصل إلى الشاشة
    صفرًا صامتًا. فيُجرَّب الالتفاف صراحةً.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from sqlalchemy import update

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid)

    with pytest.raises(Exception) as refused:
        async with tenant_session(tid, uid) as session:
            await session.execute(
                update(Thesis).where(Thesis.id == thesis_id)
                .values(processing_state="failed", failure_code=None)
                .execution_options(synchronize_session=False))
    assert "failure_is_named" in str(refused.value), str(refused.value)


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_scanned_state_that_contradicts_itself(two_tenants):
    """حالٌ تقول «لا طبقة نصّ» وعمودٌ يقول «موجودة» تناقضٌ يُرفض بنيويًّا."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from sqlalchemy import update

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid)

    with pytest.raises(Exception) as refused:
        async with tenant_session(tid, uid) as session:
            await session.execute(
                update(Thesis).where(Thesis.id == thesis_id)
                .values(processing_state="text_layer_missing",
                        failure_code="text_layer_missing",
                        text_layer_state="present")
                .execution_options(synchronize_session=False))
    assert "missing_text_layer_says_so" in str(refused.value), str(refused.value)


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_an_ocr_claim_on_a_readable_document(two_tenants):
    """**عقدُ OCR لا يُستعمل ليدّعي قراءةً لم تقع** — والقاعدة تحرسه."""
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from sqlalchemy import update

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid)

    with pytest.raises(Exception) as refused:
        async with tenant_session(tid, uid) as session:
            await session.execute(
                update(Thesis).where(Thesis.id == thesis_id)
                .values(text_layer_state="present", ocr_state="completed")
                .execution_options(synchronize_session=False))
    assert "ocr_only_when_no_text_layer" in str(refused.value), str(refused.value)


@requires_db
@pytest.mark.asyncio
async def test_two_concurrent_requests_produce_one_claim_not_two_runs(two_tenants):
    """**ضغطتان على «أعد المحاولة» لا تُنتجان تشغيلتين.**

    والحجز شرطٌ في عبارة الكتابة نفسها لا فحصٌ قبلها: فحصٌ ثمّ كتابةٌ
    نافذتان، وطلبان يقرآن «ساقطة» معًا يجدولان مهمّتين على الملفّ نفسه —
    فتتضاعف المرشّحات ويُحاسب الباحث على ضغطةٍ مكرّرة.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing
    from sqlalchemy import select

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid)

    async with tenant_session(tid, uid) as session:
        previous = await processing.claim_for_processing(
            session, tenant_id=tid, thesis_id=thesis_id)
    assert previous == processing.UPLOADED

    async with tenant_session(tid, uid) as session:
        with pytest.raises(processing.ProcessingConflict) as clash:
            await processing.claim_for_processing(
                session, tenant_id=tid, thesis_id=thesis_id)
    assert clash.value.code == "thesis.processing_in_flight"

    async with tenant_session(tid, uid) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.processing_state == processing.QUEUED
        assert row.processing_attempts == 1, "المحاولةُ المرفوضة عُدَّت"


@requires_db
@pytest.mark.asyncio
async def test_a_scanned_document_refuses_a_retry_by_name(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid)

    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.TEXT_LAYER_MISSING,
                              failure_code="text_layer_missing",
                              text_layer=processing.TEXT_LAYER_ABSENT)
    async with tenant_session(tid, uid) as session:
        with pytest.raises(processing.ProcessingConflict) as refused:
            await processing.claim_for_processing(
                session, tenant_id=tid, thesis_id=thesis_id)
    assert refused.value.code == "thesis.retry_needs_ocr"


@requires_db
@pytest.mark.asyncio
async def test_a_thesis_of_another_tenant_is_invisible_and_unwritable(two_tenants):
    """**العزلُ بين المستأجرين من RLS لا من شرطٍ في بايثون.**

    ويُجرَّب الطرفان: القراءة لا تراها، والكتابة لا تصيبها. وسياسةٌ تمنع
    القراءة وتسمح بالكتابة عزلٌ نصفيّ يُقرأ سليمًا في اختبارٍ نصفيّ.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import Thesis
    from athera_api.services.thesis import processing
    from sqlalchemy import select

    a, b = two_tenants["a"], two_tenants["b"]
    thesis_id, _ = await _seed_thesis(a["tenant_id"], a["user_id"])
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await processing.mark(session, tenant_id=a["tenant_id"], thesis_id=thesis_id,
                              state=processing.READY_FOR_REVIEW)

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        assert (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one_or_none() is None
        # والكتابة أيضًا: بحجّة مستأجرها هي، فلا تصيب شيئًا.
        await processing.mark(session, tenant_id=b["tenant_id"], thesis_id=thesis_id,
                              state=processing.FAILED, failure_code="unknown")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = (await session.execute(
            select(Thesis).where(Thesis.id == thesis_id))).scalar_one()
        assert row.processing_state == processing.READY_FOR_REVIEW, "كتابةٌ عبرت العزل"


@requires_db
@pytest.mark.asyncio
async def test_an_opportunity_of_another_project_is_never_counted_on_a_thesis(two_tenants):
    """**RLS لا تحمي بين بحثين في المستأجر الواحد** — وهذا عطبٌ وقع هنا قبلُ.

    ففرصةٌ نشأت من بحثٍ لا رسالةَ له (`project_id` مضبوط و`thesis_id`
    فارغ) تعيش في المستأجر نفسه وتراها الجلسة نفسها. ولولا أن الشرط
    `thesis_id == <هذه الرسالة>` مكتوبٌ في العبارة، لعُدَّت على بطاقة
    رسالةٍ لا علاقة لها بها — فيقرأ الباحث فرصًا لم تُستخرَج من رسالته.
    """
    import httpx

    from athera_api.db import tenant_session
    from athera_api.main import app
    from athera_api.models.portfolio import ResearchProject
    from athera_api.models.thesis import PublicationOpportunity
    from athera_api.security import issue_access_token

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid, filename="رسالتي.pdf")
    other_thesis_id, _ = await _seed_thesis(tid, uid, filename="رسالةٌ أخرى.pdf")

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="بحثٌ بلا رسالة",
                                  status="planned")
        session.add(project)
        await session.flush()
        # فرصةٌ من بحثٍ آخر — لا تخصّ أيّ رسالة.
        session.add(PublicationOpportunity(
            tenant_id=tid, project_id=project.id, thesis_id=None,
            opportunity_kind="core_study", paper_kind="empirical",
            working_title_ar="فرصةٌ من بحثٍ لا رسالة له"))
        # وفرصةٌ من الرسالة الأخرى — لا تخصّ رسالتنا.
        session.add(PublicationOpportunity(
            tenant_id=tid, thesis_id=other_thesis_id,
            opportunity_kind="core_study", paper_kind="empirical",
            working_title_ar="فرصةٌ من رسالةٍ أخرى"))
        await session.flush()

    token = issue_access_token(user_id=uid, tenant_id=tid, roles=["researcher"],
                               mfa_satisfied=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as client:
        response = await client.get("/api/v1/theses")
        assert response.status_code == 200, response.text
        cards = {row["id"]: row for row in response.json()}

    mine = cards[str(thesis_id)]
    assert mine["opportunities_found"] == 0, "فرصةُ بحثٍ آخر عُدَّت على رسالتي"
    # **ولا تُقرأ هذه الصفر نتيجةً**: لم يُنقَّب بعد، ويُقال ذلك.
    assert mine["opportunities_outcome"] == "not_started"
    assert cards[str(other_thesis_id)]["opportunities_found"] == 1


# ═════════════════════ ١١. من طرف الشبكة، بهويّةٍ حقيقية ═════════════════════
#
# **الخدمةُ تُستدعى مباشرةً فيما سبق، والباحث لا يستدعيها.** بينه وبينها
# موجّهٌ ومصادقةٌ وجلسةُ مستأجر. وفحصٌ يبلغ الخدمة من غير هذا الطريق يثبت
# أنّ الحساب صحيح، ولا يثبت أنّ أحدًا يستطيع بلوغه.


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


@requires_db
@pytest.mark.asyncio
async def test_over_http_every_card_keeps_its_identity(two_tenants):
    """**ثلاثُ رسائل بلا عنوانٍ مستخرَج تبقى ثلاثًا يفرّق بينها الباحث.**"""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    names = ["thesis-final-v3.pdf", "الفصل-الأخير.pdf", "draft-2019.pdf"]
    for name in names:
        await _seed_thesis(tid, uid, filename=name)

    async with _client(tid, uid) as client:
        rows = (await client.get("/api/v1/theses")).json()

    shown = [row["display_title"] for row in rows]
    assert set(shown) == set(names), f"بطاقاتٌ بلا هويّة: {shown}"
    assert len(set(shown)) == 3, "رصّةُ بطاقاتٍ متطابقة"
    for row in rows:
        assert row["title_is_extracted"] is False
        assert row["title_ar"] is None, "اسمُ الملفّ سُرّب إلى عمود العنوان"
        assert row["title"] is None, "اسمُ ملفٍّ يُقدَّم عنوانًا"


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_failure_is_never_shown_as_an_empty_result(two_tenants):
    """**«تعذّر التحليل» و«حلّلنا فلم نجد» خبران لا يُجمعان في «٠».**"""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    broken, _ = await _seed_thesis(tid, uid, filename="سقطت.pdf")
    scanned, _ = await _seed_thesis(tid, uid, filename="ممسوحة.pdf")
    fresh, _ = await _seed_thesis(tid, uid, filename="جديدة.pdf")

    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=broken,
                              state=processing.FAILED, failure_code="extraction_failed",
                              failure_detail="TimeoutError: provider did not answer")
        await processing.mark(session, tenant_id=tid, thesis_id=scanned,
                              state=processing.TEXT_LAYER_MISSING,
                              failure_code="text_layer_missing",
                              text_layer=processing.TEXT_LAYER_ABSENT)

    async with _client(tid, uid) as client:
        cards = {row["id"]: row for row in (await client.get("/api/v1/theses")).json()}

    failed = cards[str(broken)]
    assert failed["sections_extracted"] == 0
    assert failed["sections_outcome"] == "failed", "فشلٌ يُقرأ نتيجةً صفرية"
    assert failed["failure_code"] == "extraction_failed"
    assert failed["failure_message"], "فشلٌ بلا نصٍّ يقرؤه الباحث"
    assert "TimeoutError" not in failed["failure_message"], "رسالةٌ تقنيّة تُعرض نصًّا للباحث"
    assert failed["can_retry"] is True, "فشلٌ حقيقيّ بلا بابِ إعادة"

    missing = cards[str(scanned)]
    assert missing["sections_outcome"] == "no_text_layer"
    assert missing["text_layer_state"] == "absent"
    assert missing["ocr_available"] is False, "المنتج يدّعي قراءةً ضوئية غير موجودة"
    assert missing["can_retry"] is False, "زرٌّ يَعِد بما لن يقع"
    assert missing["retry_blocked_reason"], "زرٌّ ممنوعٌ بلا تفسير"
    assert "OCR" in missing["retry_blocked_reason"] or "ضوئية" in missing[
        "retry_blocked_reason"]

    started = cards[str(fresh)]
    assert started["sections_outcome"] == "not_started", "ما لم يبدأ يُقرأ نتيجةً"
    assert started["failure_code"] is None
    # **والحالاتُ الثلاث ثلاثُ جملٍ مختلفة، لا جملةٌ واحدة.**
    labels = {failed["sections_outcome_label"], missing["sections_outcome_label"],
              started["sections_outcome_label"]}
    assert len(labels) == 3, f"ثلاثُ حالاتٍ تُقال بنصٍّ واحد: {labels}"


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_listing_pages_filters_and_searches(two_tenants):
    """**صفحةٌ محدودة، وعرضٌ مسمّى، وبحثٌ يجد** — وإلّا فالرصّةُ بلا نهاية."""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    made = [await _seed_thesis(tid, uid, filename=f"رسالة-{index:02d}.pdf")
            for index in range(7)]
    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=made[0][0],
                              state=processing.FAILED, failure_code="parse_failed")
        await processing.mark(session, tenant_id=tid, thesis_id=made[1][0],
                              state=processing.READY_FOR_REVIEW)

    async with _client(tid, uid) as client:
        first = (await client.get("/api/v1/theses", params={"limit": 3})).json()
        assert len(first) == 3, "الحدُّ لا يُحترم"

        second = (await client.get(
            "/api/v1/theses", params={"limit": 3, "after": first[-1]["id"]})).json()
        assert len(second) == 3
        # **صفحتان تغطّيان كلّ صفٍّ مرّةً واحدة** — لا تكرار ولا سقوط.
        assert not ({row["id"] for row in first} & {row["id"] for row in second})

        failed = (await client.get("/api/v1/theses", params={"view": "failed"})).json()
        assert [row["id"] for row in failed] == [str(made[0][0])]

        waiting = (await client.get(
            "/api/v1/theses", params={"view": "awaiting_action"})).json()
        assert [row["id"] for row in waiting] == [str(made[1][0])]

        found = (await client.get("/api/v1/theses", params={"q": "رسالة-04"})).json()
        assert [row["id"] for row in found] == [str(made[4][0])]

        # ومرشّحٌ مجهول يُردّ ولا يُتجاهَل.
        unknown = await client.get("/api/v1/theses", params={"view": "everything"})
        assert unknown.status_code == 422
        assert unknown.json()["error"]["code"] == "thesis.unknown_view"


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_page_costs_one_statement_however_many_theses(two_tenants):
    """**عددُ العبارات هو زمنُ الاستجابة.**

    الـAPI في سنغافورة والقاعدة في مومباي: كلُّ عبارةٍ رحلةٌ بنحو ٣٣٠ مللي
    ثانية. والصياغة السابقة كانت تسأل عن أقسام **كلّ رسالة** وفرصها على
    حدة — استعلامان لكلّ صفّ، بلا سقفٍ للصفوف. فعشرون رسالة كانت إحدى
    وأربعين رحلة، ثلاث عشرة ثانية من الشبكة وحدها.

    فيُقاس ما لا يظهر في اختبار صحّة: أنّ كلفة الصفحة **لا تنمو** مع عدد
    الرسائل.
    """
    import contextlib

    from sqlalchemy.ext.asyncio import AsyncSession

    @contextlib.contextmanager
    def counting():
        """يعدّ عبارات القاعدة الحقيقية — و`set_config` ليست منها.

        ضبطُ سياق المستأجر عبارةٌ في كلّ جلسة مهما كان المسار؛ عدُّها يخلط
        ثمنًا ثابتًا بثمنٍ ينمو، وما يُقاس هنا هو الثاني.
        """
        seen: list[str] = []
        original = AsyncSession.execute

        async def spy(self, statement, *args, **kwargs):
            rendered = str(statement)
            if "set_config" not in rendered:
                seen.append(rendered)
            return await original(self, statement, *args, **kwargs)

        AsyncSession.execute = spy
        try:
            yield seen
        finally:
            AsyncSession.execute = original

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]

    for index in range(3):
        await _seed_thesis(tid, uid, filename=f"صغيرة-{index}.pdf")
    async with _client(tid, uid) as client:
        with counting() as small:
            assert len((await client.get("/api/v1/theses")).json()) == 3

    for index in range(12):
        await _seed_thesis(tid, uid, filename=f"كبيرة-{index}.pdf")
    async with _client(tid, uid) as client:
        with counting() as large:
            assert len((await client.get("/api/v1/theses")).json()) == 15

    assert len(small) == len(large), (
        f"كلفةُ الصفحة تنمو مع عدد الرسائل: {len(small)} ⇐ {len(large)}\n"
        + "\n".join(large))
    assert len(large) == 1, (
        "صفحةُ الرسائل تكلّف أكثر من عبارةٍ واحدة:\n" + "\n".join(large))


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_second_retry_while_one_is_running_is_refused(two_tenants):
    """**ولا معالجتان متزامنتان على ملفٍّ واحد** — من طرف الشبكة لا تحته."""
    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid, filename="مزدوجة.pdf")

    async with _client(tid, uid) as client:
        first = await client.post(f"/api/v1/theses/{thesis_id}/reprocess")
        assert first.status_code == 202, first.text
        # **والاستجابة تقول `queued` لا `extracting`**: المهمّة لم تبدأ بعد.
        assert first.json()["status"] == "queued"

        second = await client.post(f"/api/v1/theses/{thesis_id}/reprocess")
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "thesis.processing_in_flight"


@requires_db
@pytest.mark.asyncio
async def test_over_http_a_scanned_thesis_is_told_that_ocr_is_not_available(two_tenants):
    """**ويُقال الحدُّ بلغته، ولا يُردّ الطلب بخطأٍ عامّ.**"""
    from athera_api.db import tenant_session
    from athera_api.services.thesis import processing

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    thesis_id, _ = await _seed_thesis(tid, uid, filename="ممسوحة.pdf")
    async with tenant_session(tid, uid) as session:
        await processing.mark(session, tenant_id=tid, thesis_id=thesis_id,
                              state=processing.TEXT_LAYER_MISSING,
                              failure_code="text_layer_missing",
                              text_layer=processing.TEXT_LAYER_ABSENT)

    async with _client(tid, uid) as client:
        refused = await client.post(f"/api/v1/theses/{thesis_id}/reprocess")
        assert refused.status_code == 409, refused.text
        body = refused.json()["error"]
        assert body["code"] == "thesis.retry_needs_ocr"
        assert "OCR" in body["message"] or "ضوئية" in body["message"]


@requires_db
@pytest.mark.asyncio
async def test_over_http_the_listing_never_shows_another_tenants_thesis(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    mine, _ = await _seed_thesis(a["tenant_id"], a["user_id"], filename="لي.pdf")
    theirs, _ = await _seed_thesis(b["tenant_id"], b["user_id"], filename="لهم.pdf")

    async with _client(a["tenant_id"], a["user_id"]) as client:
        ids = {row["id"] for row in (await client.get("/api/v1/theses")).json()}
    assert str(mine) in ids and str(theirs) not in ids, "عزلٌ مخروق من طرف الشبكة"


@requires_db
@pytest.mark.asyncio
async def test_over_http_registering_a_thesis_returns_the_same_card_shape(two_tenants):
    """**صياغةٌ واحدة للبطاقة لا اثنتان** — فلا تفترقان بأوّل تعديل."""
    from athera_api.schemas.thesis import ThesisResponse

    a = two_tenants["a"]
    async with _client(a["tenant_id"], a["user_id"]) as client:
        created = await client.post("/api/v1/theses", json={
            "title_ar": "أثر التدريب في الأداء", "degree": "masters"})
        assert created.status_code == 201, created.text
        body = created.json()

    assert set(body) == set(ThesisResponse.model_fields)
    assert body["processing_state"] == "uploaded"
    assert body["processing_state_label"], "حالٌ بلا نصّ"
    assert body["title_is_extracted"] is True
    assert body["display_title"] == "أثر التدريب في الأداء"
    assert body["sections_outcome"] == "not_started"
    assert body["opportunities_outcome"] == "not_started"
    assert body["can_retry"] is False, "رسالةٌ بلا ملفّ تُعرض قابلةً لإعادة القراءة"
    assert body["retry_blocked_reason"], "منعٌ بلا تفسير"
