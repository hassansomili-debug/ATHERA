"""فرز الأدبيات ومصفوفتها | Literature screening + matrix (PUBRIVA).

يثبت هذا الملف ستّة أشياء لا تُشحن الميزة بدونها:

١) **العزل مفروض على الجدول الجديد وعلى العمود الجديد**: مستأجرٌ لا يقرأ
   قرار فرز غيره ولا خليةَ مصفوفته، ولا يكتب فيهما — والمنع من القاعدة.
٢) **الاستبعاد لا يقع بلا سبب**: القيد في القاعدة يرفضه، والـAPI يرفضه
   برمزٍ له ترجمتان — لا بـ500 من قيدٍ انفجر.
٣) **لا حقيقة موازية**: حالُ الاستعمال تُكتب في `project_sources` وحده،
   ومن مسارٍ واحد.
٤) **لا خلية تُخمَّن**: «غير مذكور» لا تحمل قيمة، ولا مقتطف بلا نصّ، ولا
   رقم صفحةٍ لملخّص، ولا اعتماد لما استخرجه نموذج بلا مُعتمِدٍ يُسمّى.
٥) **المدى يُحسب من حالٍ مسجَّلة**: `full_text` تحتاج حقّ معالجة وملفًّا في
   هذا البحث، ولا تُمنح لنيّة الكاتب.
٦) **الشاشة تفرّق بين التحميل والفراغ والفشل**، ولا تعرض «لا مراجع» قبل
   الجواب — ولا تعرض فشلًا فراغًا.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0023_literature_screening.py")
SCREEN = WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _later_migrations_text() -> str:
    """ما كُتب بعد 0023 — لأن الجدول يُمدّ ولا يُعاد إنشاؤه."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MIGRATION.parent.glob("0*.py"))
        if path.name > MIGRATION.name
    )


# ═════════════════ اختبارات خالصة: ما يُقرأ بلا قاعدة ═════════════════

def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته.

    فمن يفتح الاتصال بدور المالك يقرأ كل المستأجرين وسياسةٌ معلَنة قائمة.
    و`FORCE` هي ما يجعل العزل خاصية قاعدة لا خاصية دورٍ صادف أنه المستعمل
    — قاعدة ADR-0002، بلا استثناء لجدولٍ «تحليليّ».
    """
    text = _migration_text()
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text


def test_the_migration_indexes_the_reads_the_screens_actually_make():
    """فهرسٌ للقراءة المعروضة لا فهارس على التخمين.

    شاشتان تقرآن: مصفوفةُ بحثٍ بعينه صفًّا صفًّا، وقائمةُ المستبعَدات
    بأسبابها. وغيابهما يجعل كل فتح مصفوفةٍ مسحًا كاملًا للجدول.
    """
    text = _migration_text()
    assert "ix_literature_matrix_cells_project" in text
    assert '"tenant_id", "project_id", "source_id"' in text
    assert "ix_project_sources_excluded" in text
    assert '"tenant_id", "project_id", "exclusion_reason_code"' in text


def test_the_migration_has_a_real_downgrade_that_refuses_to_erase_a_judgement():
    """تنازلٌ يُسقط العمود يمحو سبب استبعادٍ قاله باحثٌ بعد نظر.

    فتبقى الدراسة مستبعَدة ولا يعرف أحدٌ لماذا — وهو بالضبط العطب الذي
    أُنشئ الترحيل ليمنعه. فالتنازل حقيقيّ ويرفض ما دام هناك حكمٌ مسجَّل.
    """
    text = _migration_text()
    assert "def downgrade()" in text
    assert "downgrade refused" in text
    assert "exclusion_reason_code IS NOT NULL" in text
    assert "verification_status <> 'unverified'" in text
    assert 'op.drop_table("literature_matrix_cells")' in text
    assert 'op.drop_column("project_sources", "exclusion_reason_code")' in text


def test_the_model_and_the_migration_agree_column_by_column():
    """عمودٌ في النموذج لا يقابله عمودٌ في الترحيل يسقط في الإنتاج وحده.

    والجدول يُمدّ بترحيلاتٍ لاحقة، فتُقرأ **كلّها**: قصرُ الفحص على الترحيل
    الذي أنشأ الجدول يجعل كل عمودٍ يُضاف بعده يمرّ بلا مقابلة — وهو بالضبط
    العطب الذي أُنشئ هذا الفحص ليمنعه.
    """
    from athera_api.models.screening import LiteratureMatrixCell

    text = _migration_text() + _later_migrations_text()
    for column in LiteratureMatrixCell.__table__.columns:
        assert f'"{column.name}"' in text, (
            f"العمود {column.name!r} في النموذج ولا وجود له في أي ترحيل")


def _migration_module():
    """يُحمَّل الترحيل ملفًّا لأنه ليس حزمةً تُستورد — والمقابلة تحتاجه حيًّا."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0023", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_vocabulary_the_code_writes_is_permitted_by_the_migration():
    """**الخطأ المتكرر في هذا المستودع**: مفردةٌ تُكتب بجانب سجلّها.

    فكانت `"removed"` تُكتب بجانب حالات الربط والقيد لا يعرفها، فانفجرت كل
    إزالةِ ملفٍّ في الإنتاج. فتُقابَل هنا كل مفردةٍ يكتبها النموذج بالمفردة
    التي يفرضها القيد — **مجموعةً بمجموعة، لا وجودَ نصٍّ في ملفّ**: قيمةٌ
    زائدة في القيد لا يعرفها النموذج عيبٌ كذلك.
    """
    from athera_api.models import screening as model

    migration = _migration_module()
    for label, mine, theirs in (
        ("أسباب الاستبعاد", model.STORED_REASON_CODES,
         migration.EXCLUSION_REASON_CODES),
        ("حالات الخلية", model.CELL_STATES, migration.CELL_STATES),
        ("مَدى القراءة", model.SOURCE_SCOPES, migration.SOURCE_SCOPES),
        ("طرق الاستخراج", model.EXTRACTION_METHODS, migration.EXTRACTION_METHODS),
        ("حالات المراجعة", model.VERIFICATION_STATES, migration.VERIFICATION_STATES),
        ("أعمدة المصفوفة", model.MATRIX_FIELDS, migration.MATRIX_FIELDS),
    ):
        assert tuple(mine) == tuple(theirs), (
            f"{label}: النموذج يقول {mine!r} والترحيل يقول {theirs!r}")


def test_the_matrix_columns_are_the_sixteen_named_ones_in_order():
    from athera_api.models.screening import MATRIX_FIELDS

    assert MATRIX_FIELDS[0] == "reference"
    assert len(MATRIX_FIELDS) == len(set(MATRIX_FIELDS)) == 16
    for expected in ("problem", "objective", "theory", "design", "method",
                     "population", "sample", "context", "constructs",
                     "measures", "analysis", "findings", "limitations", "gaps"):
        assert expected in MATRIX_FIELDS


def test_the_legacy_reason_is_readable_but_never_writable():
    """**قرارٌ سبق اشتراطَ السبب يُسمّى ما هو، ولا يصير بابًا خلفيًّا.**

    فصفٌّ استُبعد قبل الترحيل لا سبب له ولا يُخترع له واحد؛ لكن قبولَ تلك
    القيمة مُدخَلًا يفتح استبعادًا بلا سبب — وهو ما أُنشئ الحقل ليمنعه.
    """
    from athera_api.models.screening import (
        EXCLUSION_REASON_CODES,
        LEGACY_REASON_CODE,
        STORED_REASON_CODES,
    )
    from athera_api.services.screening import reason_is_acceptable

    assert LEGACY_REASON_CODE in STORED_REASON_CODES
    assert LEGACY_REASON_CODE not in EXCLUSION_REASON_CODES
    assert reason_is_acceptable(LEGACY_REASON_CODE, "أيّ نصّ") is False
    assert f"'{LEGACY_REASON_CODE}'" in _migration_text()


def test_the_request_contract_rejects_the_legacy_reason_too():
    """العقد يُشتقّ من السجل، فلا يقبل ما لا تقبله الخدمة."""
    from pydantic import ValidationError

    from athera_api.schemas.workspace import SourceUseRequest

    payload = SourceUseRequest(use_state="excluded", reason_code="duplicate")
    assert payload.reason_code == "duplicate"
    with pytest.raises(ValidationError):
        SourceUseRequest(use_state="excluded", reason_code="unrecorded_legacy")
    with pytest.raises(ValidationError):
        SourceUseRequest(use_state="excluded", reason_code="لأنني قررت ذلك")


def test_other_is_not_a_reason_without_its_words():
    """«سبب آخر» بلا نصّ خانةٌ فارغة تُعدّ سببًا في التقرير."""
    from athera_api.services.screening import reason_is_acceptable

    assert reason_is_acceptable("other", None) is False
    assert reason_is_acceptable("other", "   ") is False
    assert reason_is_acceptable("other", "المجلة غير محكَّمة") is True
    assert reason_is_acceptable("duplicate", None) is True
    assert reason_is_acceptable(None, "نصّ") is False


def test_no_page_number_is_ever_invented_for_an_abstract():
    """**ولا تُخترع أرقام صفحات.** ملخّصٌ لا صفحات له، وبياناتٌ وصفية لا موضع."""
    from athera_api.services.screening import (
        ABSTRACT_ONLY,
        FULL_TEXT,
        METADATA_ONLY,
        locator_is_honest,
    )

    assert locator_is_honest(ABSTRACT_ONLY, "ص. ١٤") is False
    assert locator_is_honest(ABSTRACT_ONLY, "abstract") is True
    assert locator_is_honest(ABSTRACT_ONLY, None) is True
    assert locator_is_honest(METADATA_ONLY, "abstract") is False
    assert locator_is_honest(METADATA_ONLY, None) is True
    assert locator_is_honest(FULL_TEXT, "ص. ١٤") is True


def test_the_reading_scope_is_computed_from_recorded_facts_not_from_intent():
    """**`full_text` تعني أن النصّ في اليد.**

    ولا تكفي كلمة الفهرس «مفتوح الوصول»: من لم يرفع الورقة لم يقرأها،
    وشاشةٌ تسمح له بادّعاء قراءتها تكذب نيابةً عنه في مصفوفةٍ ستُكتب منها
    ورقة. فالشرطان معًا: حقّ معالجة، وملفٌّ مرتبطٌ بهذا البحث.
    """
    from athera_api.models.literature import Source
    from athera_api.services.screening import (
        ABSTRACT_ONLY,
        FULL_TEXT,
        METADATA_ONLY,
        reading_scope,
    )

    file_id = uuid.uuid4()

    bare = Source(title="دراسة بلا شيء", access_state="abstract_metadata_only",
                  raw_metadata=None)
    assert reading_scope(bare, project_file_ids=set()).scope == METADATA_ONLY

    with_abstract = Source(title="دراسة بملخّص",
                           access_state="abstract_metadata_only",
                           raw_metadata={"abstract": "<jats:p>خلاصة الدراسة.</jats:p>"})
    assert reading_scope(with_abstract, project_file_ids=set()).scope == ABSTRACT_ONLY

    # مفتوح الوصول **بلا ملف** لا يبلغ النصّ الكامل: الادّعاء ليس قراءة.
    open_no_file = Source(title="مفتوحة بلا ملف",
                          access_state="open_access_full_text",
                          raw_metadata={"abstract": "<jats:p>خلاصة.</jats:p>"})
    assert reading_scope(open_no_file, project_file_ids=set()).scope == ABSTRACT_ONLY

    # وملفٌّ بلا حقّ معالجة لا يبلغه أيضًا (§14.2).
    restricted = Source(title="ممنوعة المعالجة",
                        access_state="restricted_no_processing_right",
                        file_id=file_id, raw_metadata=None)
    assert reading_scope(restricted, project_file_ids={file_id}).scope == METADATA_ONLY

    readable = Source(title="مفتوحة وفي اليد",
                      access_state="open_access_full_text", file_id=file_id,
                      raw_metadata=None)
    assert reading_scope(readable, project_file_ids={file_id}).scope == FULL_TEXT

    # وملفٌّ في مكتبةٍ أخرى لا يخدم هذا البحث.
    assert reading_scope(readable, project_file_ids=set()).scope == METADATA_ONLY


def test_a_scope_never_permits_a_stronger_claim_than_it_holds():
    from athera_api.services.screening import (
        ABSTRACT_ONLY,
        FULL_TEXT,
        METADATA_ONLY,
        ReadingScope,
    )

    assert ReadingScope(ABSTRACT_ONLY).permits(METADATA_ONLY) is True
    assert ReadingScope(ABSTRACT_ONLY).permits(ABSTRACT_ONLY) is True
    assert ReadingScope(ABSTRACT_ONLY).permits(FULL_TEXT) is False
    assert ReadingScope(METADATA_ONLY).permits(ABSTRACT_ONLY) is False
    assert ReadingScope(FULL_TEXT).permits(FULL_TEXT) is True


def test_an_absent_abstract_stays_absent_and_is_never_generated():
    """غيابُ الملخّص يبقى غيابًا: لا يُستنتج من عنوان ولا يُولَّد."""
    from athera_api.models.literature import Source
    from athera_api.services.screening import abstract_of

    assert abstract_of(Source(title="بلا خام", raw_metadata=None)) is None
    assert abstract_of(Source(title="خام فارغ", raw_metadata={})) is None
    assert abstract_of(Source(title="عنوانٌ طويل جدًّا يصلح ملخّصًا لمن يخمّن",
                              raw_metadata={"title": "عنوان"})) is None
    # ونصُّ الناشر يُقرأ كما أرسله، منزوع الوسوم لا مُعاد صياغته.
    jats = Source(title="من Crossref",
                  raw_metadata={"abstract": "<jats:p>هدفت الدراسة إلى كذا.</jats:p>"})
    assert abstract_of(jats) == "هدفت الدراسة إلى كذا."
    inverted = Source(title="من OpenAlex",
                      raw_metadata={"abstract_inverted_index":
                                    {"هدفت": [0], "الدراسة": [1], "إلى": [2]}})
    assert abstract_of(inverted) == "هدفت الدراسة إلى"


def test_a_cell_that_was_never_filled_says_not_stated_not_nothing():
    """الخانة البيضاء تُقرأ «لا شيء يستحق»، و«غير مذكور» تُقرأ فجوة."""
    from athera_api.services.screening import METADATA_ONLY, empty_cell

    cell = empty_cell("measures", METADATA_ONLY)
    assert cell.cell_state == "missing"
    assert cell.value_ar is None
    assert cell.evidence_quote is None
    assert cell.verification_status == "unverified"


def test_only_two_columns_are_read_from_metadata_and_neither_is_invented():
    """**ولا يُملأ منهجٌ ولا عيّنةٌ ولا مقياسٌ من عنوانٍ وسنة.**

    ومن ملأها من البيانات الوصفية فقد اخترع. فالعمودان اللذان تُقرآن منها
    اثنان لا غير، وحالُهما `missing` حين تغيب البيانات نفسها.
    """
    from athera_api.models.literature import Source
    from athera_api.services.screening import METADATA_FIELDS, metadata_cell

    assert METADATA_FIELDS == ("reference", "year")
    for forbidden in ("method", "sample", "measures", "analysis", "findings"):
        assert forbidden not in METADATA_FIELDS

    known = metadata_cell("year", Source(title="دراسة", publication_year=2021), [])
    assert known.cell_state == "known" and known.value_ar == "2021"
    assert known.source_scope == "metadata_only"
    assert known.extraction_method == "metadata"
    # **ولا تُرقَّى بيانةٌ وصفية إلى معرفةٍ موثقة بمجرّد وجودها.**
    assert known.verification_status == "unverified"

    unknown = metadata_cell("year", Source(title="دراسة بلا سنة"), [])
    assert unknown.cell_state == "missing" and unknown.value_ar is None


def test_the_doi_is_shown_only_when_it_was_actually_verified():
    """معرّفٌ لم يُحلّ معروضًا بجانب دراسةٍ يُقرأ إثباتًا فيُنسخ بلا فحص."""
    from athera_api.models.literature import Source
    from athera_api.services.screening import ReadingScope, card_of
    from athera_api.models.portfolio import ProjectSource

    link = ProjectSource(use_state="saved_only", created_at=_now())
    unverified = Source(title="دراسة", doi="10.1000/x",
                        verification_status="unverified",
                        retraction_status="unknown", access_state="abstract_metadata_only")
    card = card_of(link, unverified, authors=[], scope=ReadingScope("metadata_only"))
    assert card.doi is None

    verified = Source(title="دراسة", doi="10.1000/x", verification_status="verified",
                      retraction_status="none", access_state="abstract_metadata_only")
    card = card_of(link, verified, authors=[], scope=ReadingScope("metadata_only"))
    assert card.doi == "10.1000/x"


def test_the_view_is_actually_buildable_from_the_service_record():
    """**عيبٌ لا يظهر إلا على الشاشة.**

    البطاقة والخلية `slots` فلا `__dict__` لهما، و`vars()` عليهما ترمي في
    وقت التشغيل. وكان الموجّه يبنيها بـ`vars` — فكانت كل فتحةٍ لشاشة الفرز
    تُنتج 500، ولا اختبارٌ يمسّها لأن أحدًا لم يبنِ العرض من السجلّ. فيُبنى
    هنا فعلًا.
    """
    from dataclasses import asdict

    from athera_api.schemas.screening import MatrixCellView as CellSchema
    from athera_api.schemas.screening import ScreeningCardView as CardSchema
    from athera_api.services.screening import METADATA_ONLY, ScreeningCard, empty_cell

    card = ScreeningCard(source_id=uuid.uuid4(), title="دراسة", added_at=_now(),
                         verification_status="verified", retraction_status="none")
    assert CardSchema(**asdict(card)).title == "دراسة"

    cell = empty_cell("measures", METADATA_ONLY)
    assert CellSchema(**asdict(cell)).cell_state == "missing"


def test_the_downgrade_drops_exactly_the_constraints_the_upgrade_created():
    """اسمٌ يُغيَّر في موضعٍ ويبقى في الآخر يجعل التنازل ينفجر بعد أن بدأ."""
    text = _migration_text()
    created = set(re.findall(r'op\.create_check_constraint\(\s*\n?\s*"([a-z_]+)"', text))
    dropped = set(re.findall(r'^\s+for constraint in \((.*?)\):', text, re.S | re.M))
    assert created, "لم يُعثر على قيدٍ أُنشئ في الترحيل"
    names = set(re.findall(r'"([a-z_]+)"', next(iter(dropped))))
    assert created == names, (
        f"الترحيل ينشئ {sorted(created)} ويُسقط {sorted(names)}")


def test_the_matrix_reads_included_sources_only():
    """مرجعٌ «محفوظ فقط» لم يُقرَّر بعدُ أنه دليل — ووضعه في المصفوفة يجعل
    الباحث يبني تحليله على ما لم يحكم عليه."""
    import inspect

    from athera_api.services import screening

    source = inspect.getsource(screening.matrix_rows)
    assert 'ProjectSource.use_state == "included"' in source


def test_the_decision_is_written_in_one_place_only():
    """**لا حقيقة موازية.** مسارٌ ثانٍ يكتب حال الاستعمال يصنع شاشتين
    تفترقان: واحدةٌ تشترط سبب الاستبعاد وأخرى لا تشترطه.

    وقد صار للفرز مساران في الـAPI — قرارٌ مفرد ودفعة على عشرين مرجعًا.
    فالكاتب واحدٌ لهما: `screening.apply_decision`. ولو كتب أحدهما الحال
    بنفسه لسمحت الدفعة يومًا بما يمنعه الفرد — وهي التي تقع على عشرين.
    """
    import inspect

    from athera_api.routers import workspace as router
    from athera_api.services import screening

    source = inspect.getsource(router)
    # الإسناد وحده يُعدّ: `==` مقارنةٌ تقرأ ولا تكتب.
    assert not re.findall(r"\.use_state\s*=(?![=<>])", source), (
        "المسار يكتب حال الاستعمال بنفسه — والكاتب واحدٌ في الخدمة")
    writes = re.findall(r"\.use_state\s*=(?![=<>])",
                        inspect.getsource(screening))
    assert len(writes) == 1, (
        f"حال الاستعمال تُكتب في {len(writes)} موضعًا — والموضع الواحد شرط")
    assert "exclusion_needs_reason" in source
    # والدفعة تشترط السبب كالفرد سواء — لا استثناء لأنها كثيرة.
    assert source.count("workspace.exclusion_needs_reason") == 2


def test_a_model_extracted_value_never_writes_itself_approved():
    """ما استخرجه نموذج يبقى مرشَّحًا حتى يعتمده إنسانٌ يُسمّى."""
    text = _migration_text()
    assert "model_value_is_not_self_approved" in text
    assert "extraction_method <> 'model' OR verification_status = 'unverified'" in text
    assert "OR verified_by IS NOT NULL" in text

    import inspect

    from athera_api.routers import workspace as router

    written = inspect.getsource(router.set_matrix_cell)
    assert 'cell.extraction_method = "researcher"' in written
    # والكتابة تُبطل المراجعة السابقة: خليةٌ عُدّلت بعد اعتمادها ليست التي اعتُمدت.
    assert 'cell.verification_status = "unverified"' in written


def test_the_screening_error_codes_all_have_translations_in_both_locales():
    """مفتاحٌ تقنيّ يصل الباحث ليس رسالة — واللغتان شرطٌ لا تحسين."""
    import inspect

    from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES
    from athera_api.routers import workspace as router

    referenced = set(re.findall(
        r'(?:AtheraError|NotFound)\(\s*"(workspace\.[a-z_]+)"',
        inspect.getsource(router)))
    assert referenced, "لم يُعثر على أي رمز خطأ لفحصه"
    for code in sorted(referenced):
        assert code in CATALOG, f"رمزٌ بلا ترجمة: {code}"
        for locale in SUPPORTED_LOCALES:
            assert CATALOG[code].get(locale, "").strip(), f"{code} ينقصه {locale}"


def _catalogs() -> tuple[dict, dict]:
    return (json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8")),
            json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8")))


def test_every_reason_code_has_a_researcher_facing_name_in_both_locales():
    """**والباحث لا يقرأ رمزًا تقنيًّا.**

    فرمزٌ بلا اسمٍ معروض يظهر في الشاشة `topic_not_relevant` — وهو ليس
    سببًا يقرؤه أحد. ويشمل الفحص الرمزَ القديم: يُعرض ولا يُكتب، فيجب أن
    يُقرأ.
    """
    from athera_api.models.screening import STORED_REASON_CODES

    ar, en = _catalogs()
    for code in STORED_REASON_CODES:
        key = f"reason_{code}"
        assert ar["screening"].get(key, "").strip(), f"لا اسم عربي للسبب {code}"
        assert en["screening"].get(key, "").strip(), f"no English name for {code}"


def test_every_matrix_vocabulary_has_a_name_in_both_locales():
    from athera_api.models.screening import (
        CELL_STATES,
        EXTRACTION_METHODS,
        MATRIX_FIELDS,
        SOURCE_SCOPES,
        VERIFICATION_STATES,
    )

    ar, en = _catalogs()
    expected = (
        [f"field_{field}" for field in MATRIX_FIELDS]
        + [f"method_{method}" for method in EXTRACTION_METHODS]
        + [f"verification_{state}" for state in VERIFICATION_STATES]
        + ["stateKnown", "stateNeedsReview", "stateMissing", "stateConflicting"]
        + ["scopeMetadata", "scopeAbstract", "scopeFullText"]
    )
    assert len(CELL_STATES) == 4 and len(SOURCE_SCOPES) == 3
    for key in expected:
        assert ar["matrix"].get(key, "").strip(), f"مفتاح المصفوفة {key} بلا اسم عربي"
        assert en["matrix"].get(key, "").strip(), f"matrix key {key} has no English name"


def test_every_message_key_these_screens_name_exists_in_both_locales():
    """**مفتاحٌ ناقص يُعرض مفتاحًا.**

    و`translator` يعيد المسار نفسه حين لا يجد قيمة — فتظهر في الشاشة
    `screening.tabQueue` بدل «الفرز»، ولا يفشل شيء. فيُفحص هنا: كل مفتاحٍ
    تسمّيه هذه الشاشات موجودٌ باللغتين.
    """
    ar, en = _catalogs()

    def has(catalog: dict, path: str) -> bool:
        node: object = catalog
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    missing: list[str] = []
    for page in (SCREEN / "screening" / "page.tsx", SCREEN / "matrix" / "page.tsx",
                 SCREEN / "page.tsx"):
        text = page.read_text(encoding="utf-8")
        keys = set(re.findall(r't\(\s*"([a-zA-Z0-9_.]+)"\s*\)', text))
        # والمفاتيح المخزَّنة في جداول الأسماء تُفحص كذلك — هي مفاتيح لا نصوص.
        keys |= set(re.findall(r'"([a-zA-Z]+\.[a-zA-Z0-9_]+)"', text))
        for key in sorted(keys):
            for label, catalog in (("ar", ar), ("en", en)):
                if not has(catalog, key):
                    missing.append(f"{page.name}: {key} [{label}]")
    assert not missing, "مفاتيح تُنادى ولا وجود لها: " + "; ".join(missing)


def test_the_abstract_only_label_says_so_to_the_researcher():
    """**«تم التحليل من الملخص فقط» ليست حاشية** — بها يعرف الباحث أنّ ما
    أمامه ليس قراءةَ ورقةٍ كاملة."""
    ar, _en = _catalogs()
    assert "الملخص فقط" in ar["matrix"]["scopeAbstract"]


def test_the_screens_never_leak_internal_jargon_to_the_researcher():
    """`ProviderClaim` و`AssessmentDTO` أسماءٌ داخلية لا تُعرض لباحث.

    ولا `metadata_only` ولا `saved_only`: كلُّ ما يُعرض يُقرأ من الكتالوج،
    فلا يظهر في شاشةٍ عربية مفتاحٌ إنجليزيّ.
    """
    from tests.tsscan import code_lines

    forbidden = ("ProviderClaim", "AssessmentDTO", "metadata_only\"", "saved_only\"")
    offenders: list[str] = []
    for path in (SCREEN / "screening" / "page.tsx", SCREEN / "matrix" / "page.tsx"):
        text = path.read_text(encoding="utf-8")
        for number, line in code_lines(text):
            # المفاتيح تُستعمل قيمًا في الشيفرة؛ الممنوع أن تُعرض نصًّا.
            if ">" in line and "<" in line:
                for name in forbidden:
                    if f">{name}<" in line:
                        offenders.append(f"{path.name}:{number} -> {name}")
    assert not offenders, "مفردةٌ داخلية تُعرض للباحث: " + "; ".join(offenders)


def test_the_screening_screen_tells_loading_from_empty_from_failed():
    """**طلبٌ فشل يُعرض «لا مراجع» يجعل الباحث يظنّ بحثه خاليًا.**

    فيذهب يستورد ما هو عنده — والشبكة وحدها كانت معطوبة. فلكل حالٍ موضعها
    ونصّها، والفشل يُعلَن ومعه طريق الخروج منه.
    """
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    for marker in ('data-testid="screening-loading"',
                   'data-testid="screening-failed"',
                   'data-testid="screening-empty"'):
        assert marker in text, f"حالُ عرضٍ غير مميَّزة: {marker}"
    assert 't("common.retry")' in text, "فشلٌ بلا إعادة محاولة طريقٌ مسدود"
    assert 'role="alert"' in text


def test_the_matrix_screen_tells_loading_from_empty_from_failed():
    text = (SCREEN / "matrix" / "page.tsx").read_text(encoding="utf-8")
    for marker in ('data-testid="matrix-loading"', 'data-testid="matrix-failed"',
                   'data-testid="matrix-empty"'):
        assert marker in text
    assert 't("common.retry")' in text


def test_every_repeated_control_names_its_target():
    """**زرٌّ اسمه «إدراج» بجانب «إدراج» لا يُميَّز بالسمع إطلاقًا.**

    وفي شاشة الفرز زرٌّ لكل دراسة، وفي المصفوفة زرٌّ لكل خانة. فكل زرٍّ
    متكرّر يحمل اسمًا مُعلَنًا يذكر هدفه — والعين ترى الاسم القصير كما كان.
    """
    for name, needles in (
        ("screening", ('aria-label={`${t(USE_LABEL[next])}: ${describe(card)}`}',)),
        ("matrix", ('aria-label={`${t("matrix.edit")}:', "describe(row)}`}")),
    ):
        text = (SCREEN / name / "page.tsx").read_text(encoding="utf-8")
        for needle in needles:
            assert needle in text, f"زرٌّ متكرّر بلا اسمٍ يسمّي هدفه في {name}"


def test_the_exclusion_button_never_fires_before_its_reason_is_complete():
    """زرٌّ مُفعَّل لا يفعل شيئًا يُعلّم الباحث ألّا يثق بالأزرار."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert "disabled={!reasonIsComplete(pending)" in text
    assert "function reasonIsComplete" in text


def test_the_matrix_screen_never_offers_a_scope_the_study_does_not_hold():
    """خيارٌ يُعرض ثم يردّه الخادم يُعلّم الباحث أن الشاشة تكذب."""
    text = (SCREEN / "matrix" / "page.tsx").read_text(encoding="utf-8")
    assert "SCOPES.indexOf(scope) <= SCOPES.indexOf(editing.row.reading_scope)" in text


def test_no_state_is_set_synchronously_inside_an_effect():
    """قاعدةٌ يفرضها المدقّق خطأً لا تحذيرًا — فتُفحص هنا قبل CI."""
    for name in ("screening", "matrix"):
        text = (SCREEN / name / "page.tsx").read_text(encoding="utf-8")
        assert "void Promise.resolve().then" in text, (
            f"{name}: التأثير يضبط حالةً متزامنةً")


# ════════════════════ اختبارات تمسّ القاعدة (CI) ════════════════════

async def _seed_project(tid: uuid.UUID, title: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar=title,
                                  status="planned", current_gate="G1")
        session.add(project)
        await session.flush()
        return project.id


async def _seed_source(tid: uuid.UUID, title: str) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.literature import Source

    async with tenant_session(tid) as session:
        source = Source(tenant_id=tid, title=title, retraction_status="unknown",
                        access_state="abstract_metadata_only")
        session.add(source)
        await session.flush()
        return source.id


async def _seed_included(tid: uuid.UUID, uid: uuid.UUID, project_id: uuid.UUID,
                         source_id: uuid.UUID) -> None:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    async with tenant_session(tid, uid) as session:
        session.add(ProjectSource(
            tenant_id=tid, project_id=project_id, source_id=source_id,
            use_state="included", added_by=uid, decided_by=uid, decided_at=_now()))
        await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_excluding_without_a_reason_is_refused_by_the_database(two_tenants):
    """**والحارس في القاعدة لا في الواجهة وحدها.**

    فمسارٌ يُكتب غدًا وينسى الفحص لا يستطيع أن يُنشئ استبعادًا بلا سبب.
    """
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الاستبعاد")
    source = await _seed_source(a["tenant_id"], "دراسة تُستبعَد")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(ProjectSource(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                use_state="excluded", added_by=a["user_id"],
                decided_by=a["user_id"], decided_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_reason_cannot_outlive_the_exclusion_that_explained_it(two_tenants):
    """رمزٌ باقٍ بجانب حالٍ لم تعد قائمة يُقرأ يومًا حكمًا لم يُقل."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث السبب اليتيم")
    source = await _seed_source(a["tenant_id"], "دراسة عادت مُدرَجة")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(ProjectSource(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                use_state="included", exclusion_reason_code="duplicate",
                added_by=a["user_id"], decided_by=a["user_id"], decided_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_other_without_words_is_refused_by_the_database(two_tenants):
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث السبب الآخر")
    source = await _seed_source(a["tenant_id"], "دراسة بسببٍ آخر")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(ProjectSource(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                use_state="excluded", exclusion_reason_code="other",
                reason_ar="   ", added_by=a["user_id"],
                decided_by=a["user_id"], decided_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_screening_decision_is_invisible_to_the_other_tenant(two_tenants):
    """**العزل خصمًا لا صديقًا**: المستأجر الآخر يقرأ صراحةً بالمعرّف فلا يجد."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a, b = two_tenants["a"], two_tenants["b"]
    project = await _seed_project(a["tenant_id"], "بحث سرّي")
    source = await _seed_source(a["tenant_id"], "دراسة استُبعدت")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(ProjectSource(
            tenant_id=a["tenant_id"], project_id=project, source_id=source,
            use_state="excluded", exclusion_reason_code="method_mismatch",
            added_by=a["user_id"], decided_by=a["user_id"], decided_at=_now()))
        await session.flush()

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        leaked = (await session.execute(
            select(ProjectSource).where(ProjectSource.project_id == project)
        )).scalars().all()
        assert leaked == [], "قرار فرزِ مستأجرٍ ظهر لمستأجر آخر"


@requires_db
@pytest.mark.asyncio
async def test_a_matrix_cell_is_invisible_and_unwritable_to_the_other_tenant(two_tenants):
    """قراءةً وكتابةً معًا: العزل الذي يمنع النظر ويسمح بالكتابة ليس عزلًا."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a, b = two_tenants["a"], two_tenants["b"]
    project = await _seed_project(a["tenant_id"], "بحث بمصفوفة")
    source = await _seed_source(a["tenant_id"], "دراسة مُدرَجة")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(LiteratureMatrixCell(
            tenant_id=a["tenant_id"], project_id=project, source_id=source,
            field_key="method", value_ar="شبه تجريبي", cell_state="known",
            source_scope="abstract_only", extraction_method="researcher",
            updated_by=a["user_id"]))
        await session.flush()

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        leaked = (await session.execute(
            select(LiteratureMatrixCell).where(
                LiteratureMatrixCell.project_id == project)
        )).scalars().all()
        assert leaked == [], "خليةُ مصفوفةِ مستأجرٍ ظهرت لمستأجر آخر"

    # **والكتابة تُردّ كذلك**: `WITH CHECK` يمنع صفًّا بمعرّف مستأجرٍ آخر.
    with pytest.raises(Exception):  # noqa: B017, PT011 — أيّ رفضٍ من القاعدة يكفي
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="sample", value_ar="٦٠ طالبًا", cell_state="known",
                source_scope="abstract_only", extraction_method="researcher",
                updated_by=b["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_missing_cell_can_never_carry_a_value(two_tenants):
    """**الغياب غيابٌ لا فراغٌ يُملأ.**

    ومقياسٌ لم يُذكر في الورقة يظهر في عمود «المقاييس» ثم يُكتب في المنهجية
    أنه استُعمل — وهذا أسوأ ما في مصفوفة أدبيات.
    """
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الغياب")
    source = await _seed_source(a["tenant_id"], "دراسة بلا مقياس")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="measures", value_ar="مقياس ليكرت الخماسي",
                cell_state="missing", source_scope="abstract_only",
                extraction_method="researcher", updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_metadata_alone_can_never_be_quoted(two_tenants):
    """§14.5 — لا نصّ فلا مقتطف. ومن اقتبس من عنوانٍ وسنةٍ فقد اخترع."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الاقتباس")
    source = await _seed_source(a["tenant_id"], "دراسة بلا نصّ")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="findings", value_ar="أثرٌ دال", cell_state="known",
                source_scope="metadata_only", extraction_method="metadata",
                evidence_quote="اقتباسٌ من لا شيء", updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_an_abstract_never_carries_a_page_number(two_tenants):
    """**ولا تُخترع أرقام صفحات.** ملخّصٌ لا صفحات له."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الصفحات")
    source = await _seed_source(a["tenant_id"], "دراسة بملخّص")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="sample", value_ar="٦٠ طالبًا", cell_state="known",
                source_scope="abstract_only", extraction_method="researcher",
                evidence_quote="بلغت العيّنة ٦٠ طالبًا", evidence_locator="ص. ١٤",
                updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_review_without_a_named_reviewer_is_refused(two_tenants):
    """مراجعةٌ بلا مراجِعٍ ووقت لا تكون — قاعدة كل قرارٍ بشري في المنظومة."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث المراجعة")
    source = await _seed_source(a["tenant_id"], "دراسة تُراجَع")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="theory", value_ar="نظرية الحِمل المعرفي",
                cell_state="known", source_scope="abstract_only",
                extraction_method="model", verification_status="approved",
                updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_one_cell_per_column_per_study(two_tenants):
    """نسختان لخانةٍ واحدة تفترقان، ولا يعرف أحدٌ أيّهما المعروض."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث التفرّد")
    source = await _seed_source(a["tenant_id"], "دراسة واحدة")
    await _seed_included(a["tenant_id"], a["user_id"], project, source)

    def cell(value: str) -> "LiteratureMatrixCell":
        return LiteratureMatrixCell(
            tenant_id=a["tenant_id"], project_id=project, source_id=source,
            field_key="design", value_ar=value, cell_state="known",
            source_scope="abstract_only", extraction_method="researcher",
            updated_by=a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(cell("شبه تجريبي"))
        await session.flush()

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(cell("وصفي"))
            await session.flush()
