"""ذكاء المصفوفة وسعة الفرز | Matrix intelligence + screening scale (PUBRIVA).

يثبت هذا الملف سبعة أشياء لا تُشحن الميزة بدونها:

١) **التصفية تقع قبل التصفيح، والعدّ في القاعدة**: صفحةٌ من ألف مرجع لا
   تُبنى بتحميل الألف، وعدّادُ التبويب لا يُقرأ من طول الصفحة المعروضة.
٢) **الدفعة تقع كلُّها أو لا تقع منها شيء**: تسعةَ عشرَ من عشرين أسوأ من
   صفرٍ من عشرين، لأن الباحث يعيد الأمر فيقع بعضه مرّتين.
٣) **المدى مشتقٌّ من الواقع**: `full_text` تحتاج ملفًّا **يُقرأ منه فعلًا**،
   لا ملفًّا مرفوعًا ولا كلمةَ فهرسٍ «مفتوح الوصول».
٤) **الملخّص منسوب، ولا يُطوى ملخّصان في واحد**: فهرسان يرسلان نصّين
   مختلفين صفّان، والاختلاف يُعرض اختلافًا.
٥) **الاستخراج لا يخترع**: لا يقرأ عنوانًا، ولا يكتب سببيةً لا تسندها
   الدراسة، ولا ينسب إلى الدراسة مجتمعًا من جملة «دلالات النتائج»، ولا
   يقول «لم تُستعمل نظرية» — يقول «غير مذكور».
٦) **ما استخرجته المنصّة مرشَّح**: `needs_review` و`unverified` و`model`،
   ولا يدهس خانةً كتبها إنسان أو حكم فيها.
٧) **العزل عزلُ مستأجرٍ وعزلُ بحث**: و`RLS` لا تمنع تسرّب بحثٍ إلى بحثٍ
   داخل المستأجر نفسه — فيُفحص الثاني كما يُفحص الأول.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

pytest_asyncio = pytest.importorskip("pytest_asyncio")

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
SCREEN = WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0024_matrix_intelligence.py")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _migration_module():
    """يُحمَّل الترحيل ملفًّا لأنه ليس حزمةً تُستورد — والمقابلة تحتاجه حيًّا."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0024", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalogs() -> tuple[dict, dict]:
    return (json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8")),
            json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8")))


# ═════════════════ الترحيل: العزل والفهارس والتنازل ═════════════════

def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته.

    و`FORCE` هي ما يجعل العزل خاصية قاعدة لا خاصية دورٍ صادف أنه المستعمل
    (ADR-0002) — بلا استثناء لجدولٍ «وصفيّ» يحمل ملخّصات.
    """
    text = _migration_text()
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text


def test_the_migration_indexes_the_reads_the_screen_actually_makes():
    """فهرسٌ لِما تُصفّى به الشاشة فعلًا — لا فهارس على التخمين.

    وترتيبُ الصفحة أولها: بدون فهرسٍ بترتيب القراءة نفسه يفرز الخادم جدول
    الروابط كلَّه ليعيد خمسةً وعشرين صفًّا.
    """
    text = _migration_text()
    for index in ("ix_project_sources_screening_page", "ix_sources_screening_year",
                  "ix_sources_screening_registry", "ix_sources_document_type",
                  "ix_sources_dedup_key", "ix_source_abstracts_source"):
        assert index in text, f"فهرسٌ ناقص: {index}"
    assert "created_at DESC" in text and "id DESC" in text


def test_the_dedup_key_is_written_once_and_read_twice():
    """**مفتاحٌ يُكتب مرّتين يفترق بأول إصلاح.**

    والفهرس في الترحيل والعبارة في الخدمة يجب أن يكونا النصّ نفسه؛ فلو
    افترقا لم يُستعمل الفهرس، ومسحت القاعدة جدول المراجع في كل فتحٍ
    للشاشة — بلا خطأ يظهر، وبلا أحدٍ يعرف لماذا بطؤت.
    """
    from sqlalchemy.dialects import postgresql

    from athera_api.services.screening import dedup_key_expr

    rendered = str(dedup_key_expr().compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    # اسمُ الجدول يسبق العمود في عبارة SQLAlchemy ولا يسبقه في `CREATE INDEX`
    # — وهو فرقُ صياغةٍ لا فرقُ تعبير، فيُسوّى قبل المقابلة.
    normalised = re.sub(r"\s+", " ", rendered.replace("sources.", "")).strip().lower()
    in_migration = re.sub(r"\s+", " ", _migration_module().DEDUP_KEY).strip().lower()
    assert normalised == in_migration, (
        "عبارة مفتاح التكرار في الخدمة لا تطابق فهرس الترحيل:\n"
        f"  الخدمة : {normalised}\n  الترحيل: {in_migration}")


def test_the_migration_refuses_a_downgrade_that_cuts_a_cell_from_its_abstract():
    """قيمةٌ استُخرجت من ملخّصٍ تُراجَع بمقابلتها به.

    وإسقاطُ الجدول يترك القيمة قائمةً ومصدرَها غير موجود — فتبقى «تحتاج
    مراجعة» أبدًا، لأن ما تُراجَع به ذهب.
    """
    text = _migration_text()
    assert "def downgrade()" in text
    assert "downgrade refused" in text
    assert "source_abstract_id IS NOT NULL" in text
    assert 'op.drop_table("source_abstracts")' in text


def test_the_new_columns_carry_constraints_that_refuse_an_invented_page():
    """**رقمُ الصفحة من نصٍّ كامل وحده** — والقيد في القاعدة لا في المسار.

    فمسارٌ يُكتب غدًا وينسى الفحص لا يستطيع أن يكتب صفحةً لملخّص.
    """
    text = _migration_text()
    assert "page_number_only_from_full_text" in text
    assert "evidence_page IS NULL OR (source_scope = 'full_text' AND evidence_page > 0)" in text
    assert "section_only_from_full_text" in text
    assert "abstract_cite_needs_abstract_scope" in text


def test_the_older_guarantees_are_untouched_by_this_migration():
    """**القيود الأربعة التي تحرس الصدق تبقى كما هي.**

    وترحيلٌ يمدّ جدولًا قد يُسقط قيدًا ليعيد بناءه، فيمرّ في التنفيذ ولا
    يبقى في القاعدة. فيُفحص هنا نصًّا: لا إسقاط لأيٍّ منها.
    """
    text = _migration_text()
    for guarded in ("abstract_has_no_page_number", "metadata_only_has_no_quote",
                    "model_value_is_not_self_approved", "verification_actor"):
        assert f"DROP CONSTRAINT ck_literature_matrix_cells_{guarded}" not in text
        assert f'drop_constraint("{guarded}"' not in text
    # وقيودُ 0023 نفسها ما زالت في ترحيلها.
    older = (MIGRATION.parent / "0023_literature_screening.py").read_text(encoding="utf-8")
    for guarded in ("abstract_has_no_page_number", "metadata_only_has_no_quote",
                    "model_value_is_not_self_approved", "verification_actor"):
        assert guarded in older


def test_the_abstract_model_and_the_migration_agree_column_by_column():
    from athera_api.models.screening import SourceAbstract

    text = _migration_text()
    for column in SourceAbstract.__table__.columns:
        assert f'"{column.name}"' in text, (
            f"العمود {column.name!r} في النموذج ولا وجود له في الترحيل 0024")


def test_the_provider_vocabulary_is_written_once():
    """مفردةٌ تُكتب بجانب سجلّها تفترق عنه — والقيد يرفض ما يكتبه النموذج.

    والمقابلة **مجموعةً بمجموعة** لا وجودَ نصٍّ في ملفّ: قيمةٌ زائدة في
    القيد لا يعرفها النموذج عيبٌ كذلك.
    """
    from athera_api.models.screening import ABSTRACT_PROVIDERS

    assert set(ABSTRACT_PROVIDERS) == set(_migration_module().ABSTRACT_PROVIDERS)


# ═════════════════ عقد التصفيح والعدّ ═════════════════

def test_the_counters_answer_the_question_the_tab_actually_asks():
    """**العدّاد يجيب: «كم مُدرَجة ضمن ما أراه الآن؟»**

    فتُسقَط حالُ الفرز وحدها من مرشّحات العدّ؛ ولو أُسقطت السنةُ والفهرس
    معها لأجاب العدّاد عن سؤالٍ لم يُسأل: «كم مُدرَجة في البحث كلِّه».
    """
    from athera_api.services.screening import ScreeningFilters

    filters = ScreeningFilters(use_state="included", year_from=2018,
                               registry="crossref", has_abstract=True)
    counting = filters.without_state
    assert counting.use_state is None
    assert counting.year_from == 2018
    assert counting.registry == "crossref"
    assert counting.has_abstract is True


def test_the_total_matches_the_tab_it_pages_and_the_sum_when_there_is_none():
    """`total` هو ما يُصفَّح: عددُ الحال المعروضة، أو مجموعُ الثلاث بلا حال."""
    from athera_api.services.screening import ScreeningTallies

    tallies = ScreeningTallies(saved_only=7, included=12, excluded=3)
    assert tallies.all == 22
    assert tallies.of(None) == 22
    assert tallies.of("included") == 12
    assert tallies.of("excluded") == 3


def test_a_page_is_bounded_no_matter_what_the_caller_asks():
    """ألفُ بطاقةٍ في جوابٍ واحد تُسقط الشاشة قبل أن تُسقط الخادم."""
    from athera_api.models.screening import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

    assert 0 < DEFAULT_PAGE_SIZE <= MAX_PAGE_SIZE <= 100
    router = (REPO / "apps" / "api" / "athera_api" / "routers"
              / "workspace.py").read_text(encoding="utf-8")
    assert "le=MAX_PAGE_SIZE" in router, "حدُّ الصفحة غير مفروضٍ في العقد"


def test_every_filter_is_applied_before_any_limit():
    """**تصفيةٌ بعد التصفيح كذبة.**

    تعرض الصفحة ثلاثة من خمسةٍ وعشرين جُلبت وتقول «ثلاث دراسات» وهي
    ثلاثمائة. فيُقرأ ترتيب البناء نصًّا: المرشّحات تُلحق بالعبارة، ثم
    `offset`/`limit` بعدها.
    """
    import inspect

    from athera_api.services import screening

    source = inspect.getsource(screening.screening_page)
    applied = source.index("apply_filters(stmt, filters")
    limited = source.index(".offset((page - 1) * page_size)")
    assert applied < limited, "الحدّ يسبق التصفية — والصفحة تكذب"


def _filtered_sql(**filters) -> str:
    """عبارةُ الصفحة كما ستصل القاعدة — تُقرأ نصًّا لأن العطب فيها لا يُرمى."""
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from athera_api.models.literature import Source
    from athera_api.models.portfolio import ProjectSource
    from athera_api.services import screening

    stmt = (select(ProjectSource.id)
            .join(Source, Source.id == ProjectSource.source_id)
            .where(ProjectSource.tenant_id == _uuid.uuid4()))
    stmt = screening.apply_filters(
        stmt, screening.ScreeningFilters(**filters), tenant_id=_uuid.uuid4(),
        duplicate_ids=frozenset(), readable_file_ids=frozenset())
    return re.sub(r"\s+", " ",
                  str(stmt.compile(dialect=postgresql.dialect())))


def test_a_null_never_becomes_a_third_state_that_hides_a_reference():
    """**`NULL` في SQL نفيٌ لا حالٌ ثالثة.**

    ومرجعٌ بلا بيانات فهرسٍ أصلًا كان يسقط من «له ملخّص» — وهو صواب —
    **ومن «بلا ملخّص» أيضًا**: يختفي من الوجهين، فيقرأ الباحث عددًا أنقص من
    مراجعه ولا يعرف أين ذهب الباقي.
    """
    for name, filters in (("الملخّص", {"has_abstract": False}),
                          ("النصّ الكامل", {"has_full_text": False})):
        sql = _filtered_sql(**filters)
        assert "NOT coalesce(" in sql, f"شرطُ {name} ليس آمنًا من NULL: {sql}"
    # وشرطُ الملف يفحص وجوده قبل أن يقابله بالمجموعة.
    assert "sources.file_id IS NOT NULL" in _filtered_sql(has_full_text=True)


def test_the_abstract_test_is_correlated_to_the_row_it_judges():
    """**بلا `correlate` يصير السؤال «هل في المستأجر ملخّصٌ واحد؟».**

    فيُضمّ جدولُ المراجع داخل `EXISTS` ضمًّا ديكارتيًّا، وتُقال كلُّ ورقةٍ
    ذاتَ ملخّص — والتصفية تعيد كل شيء ولا يبدو أنّ فيها عطبًا.
    """
    sql = _filtered_sql(has_abstract=True)
    inner = sql.split("EXISTS (", 1)[1].split(")", 1)[0]
    assert "sources" not in inner.split("WHERE")[0], (
        f"جدولُ المراجع مضمومٌ داخل EXISTS: {inner}")
    assert "source_abstracts.source_id = sources.id" in sql


def test_the_json_arrow_is_written_by_hand_not_left_to_a_subscript():
    """`raw_metadata['k']` فهرسةٌ لم تُقبل على jsonb قبل PostgreSQL 14.

    والفرق لا يظهر في التطوير ولا في الاختبار — يظهر يوم يُنشر على قاعدةٍ
    أقدم، وحينها يفشل كل فتحٍ للشاشة.
    """
    sql = _filtered_sql(has_abstract=True, document_type="journal-article")
    assert "raw_metadata ->" in sql
    assert "raw_metadata[" not in sql


def test_the_screening_page_never_loads_the_whole_project():
    """عددُ الذهاب والإياب ثابتٌ لا يتبع عدد المراجع — وإلا فهو عطب `1+N`.

    ستٌّ لمئة مرجعٍ وستٌّ لألف: المكرّرات، والملفات المقروءة، والعدّادات،
    والصفحة، ومؤلفوها، وملخّصاتها. وواحدةٌ تُضاف داخل حلقةٍ تجعل فتحَ
    الشاشة ألف رحلةٍ إلى قاعدةٍ في قارّةٍ أخرى.
    """
    import inspect

    from athera_api.services import screening

    source = inspect.getsource(screening.screening_page)
    assert source.count("await ") == 6, (
        f"عدد الذهاب والإياب تغيّر إلى {source.count('await ')} — راجع السبب")
    # ولا انتظارَ داخل حلقة: بناءُ البطاقات وحده يمرّ على الصفوف، وهو حساب.
    body = source.split("cards = [")[0]
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("for ", "while ")):
            pytest.fail(f"حلقةٌ قبل بناء البطاقات: {stripped}")
    assert ".limit(page_size)" in source


# ═════════════════ المدى مشتقٌّ من الواقع ═════════════════

def test_full_text_needs_a_file_that_was_actually_read():
    """**ملفٌّ مرفوع لم يُقطَّع منه سطرٌ ليس نصًّا في اليد** — هو وعدٌ به.

    وقد يكون رفعُه فشل، أو كان صورًا لا نصّ فيها. فالمجموعة التي تُبنى منها
    الرتبة تُقرأ من ملفاتٍ لها تقطيعٌ مقروء، لا من كل ملفٍّ مرتبط.
    """
    import inspect

    from athera_api.services import screening

    source = inspect.getsource(screening.readable_project_file_ids)
    assert "DocumentChunk" in source, "الملف المقروء لا يُشترط له تقطيع"
    assert "exists()" in source
    # ومن يبني المدى ينادي المقروءة لا كل مرتبط.
    for consumer in (screening.screening_page, screening.matrix_rows,
                     screening.screening_cards):
        assert "readable_project_file_ids" in inspect.getsource(consumer)


def test_an_open_access_claim_is_never_read_as_a_reading():
    """«مفتوح الوصول» حالُ حقوقٍ يعلنها فهرس — **لا نصٌّ في اليد**."""
    from athera_api.models.literature import Source
    from athera_api.services.screening import (
        ABSTRACT_ONLY,
        FULL_TEXT,
        OPEN_ACCESS_STATE,
        METADATA_ONLY,
        reading_scope,
    )

    file_id = uuid.uuid4()
    claimed = Source(title="مفتوحة بلا ملف", access_state=OPEN_ACCESS_STATE,
                     raw_metadata={"abstract": "<jats:p>خلاصة.</jats:p>"})
    assert reading_scope(claimed, project_file_ids=set()).scope == ABSTRACT_ONLY

    bare = Source(title="مفتوحة بلا ملف ولا ملخّص", access_state=OPEN_ACCESS_STATE,
                  raw_metadata=None)
    assert reading_scope(bare, project_file_ids=set()).scope == METADATA_ONLY

    in_hand = Source(title="مفتوحة وفي اليد", access_state=OPEN_ACCESS_STATE,
                     file_id=file_id, raw_metadata=None)
    assert reading_scope(in_hand, project_file_ids={file_id}).scope == FULL_TEXT


def test_the_card_says_the_index_claimed_it_not_that_the_text_is_available():
    """الاسم نفسه يمنع الخلط: `index_says_open_access` لا `has_full_text`."""
    from athera_api.services.screening import ScreeningCard

    assert "index_says_open_access" in ScreeningCard.__slots__
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert "index_says_open_access" in text
    ar, en = _catalogs()
    assert "دعوى" in ar["screening"]["openAccessClaim"]
    assert "not text in your hands" in en["screening"]["openAccessClaim"]


# ═════════════════ الملخّص مصدرٌ منسوب ═════════════════

def test_two_indexes_that_disagree_are_both_kept_and_the_disagreement_is_shown():
    """**ولا يغلب أحدهما الآخر بصمت.**

    فهرسان يرسلان ملخّصين مختلفين للورقة نفسها حالٌ واقعة؛ ومن طوى أحدهما
    جعل الباحث يقرأ نصف الحقيقة ويظنّه كلّها.
    """
    from athera_api.models.literature import Source
    from athera_api.models.screening import SourceAbstract
    from athera_api.services.screening import abstract_digest, abstracts_of

    source = Source(title="ورقةٌ اختلف فيها فهرسان", registry="openalex",
                    registry_id="W1", last_verified_at=_now(),
                    raw_metadata={"abstract_inverted_index":
                                  {"نصّ": [0], "OpenAlex": [1]}})
    stored = SourceAbstract(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), source_id=uuid.uuid4(),
        provider="crossref", provider_identifier="10.1/x",
        text="نصّ Crossref مختلف", content_hash=abstract_digest("نصّ Crossref مختلف"),
        retrieved_at=_now())

    records = abstracts_of(source, [stored])
    assert len(records) == 2
    assert {record.provider for record in records} == {"crossref", "openalex"}
    assert len({record.content_hash for record in records}) == 2


def test_the_same_abstract_from_the_same_index_is_not_counted_twice():
    """نصٌّ واحد قُرئ مرّتين ليس فهرسين اتّفقا."""
    from athera_api.models.literature import Source
    from athera_api.models.screening import SourceAbstract
    from athera_api.services.screening import abstract_digest, abstracts_of

    text = "هدفت الدراسة إلى كذا."
    source = Source(title="ورقة", registry="crossref", last_verified_at=_now(),
                    raw_metadata={"abstract": f"<jats:p>{text}</jats:p>"})
    stored = SourceAbstract(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), source_id=uuid.uuid4(),
        provider="crossref", text=text, content_hash=abstract_digest(text),
        retrieved_at=_now())
    records = abstracts_of(source, [stored])
    assert len(records) == 1
    assert records[0].stored_id == stored.id


def test_the_digest_ignores_whitespace_but_nothing_else():
    """سطرٌ إضافي ليس ملخّصًا ثانيًا — وحرفٌ مختلف ملخّصٌ ثانٍ."""
    from athera_api.services.screening import abstract_digest

    assert abstract_digest("نصّ  الملخّص\n") == abstract_digest("نصّ الملخّص")
    assert abstract_digest("نصّ الملخّص") != abstract_digest("نصّ الملخّصِ")


def test_an_abstract_with_no_arrival_time_is_never_stamped_with_now():
    """**وقتُ قراءتنا ليس وقت وصوله.** و`None` تقول «لا نعرف»، وهي صادقة."""
    from athera_api.models.literature import Source
    from athera_api.services.screening import derived_abstracts

    source = Source(title="بلا وقت", registry="crossref",
                    raw_metadata={"abstract": "<jats:p>نصّ.</jats:p>"})
    records = derived_abstracts(source)
    assert len(records) == 1
    assert records[0].retrieved_at is None


def test_an_unknown_registry_never_borrows_a_name_it_does_not_own():
    """نسبةٌ خاطئة أسوأ من نسبةٍ عامّة: تُقرأ إثباتًا ويُعاد إليها الطلب."""
    from athera_api.models.literature import Source
    from athera_api.models.screening import ABSTRACT_PROVIDERS
    from athera_api.services.screening import derived_abstracts

    source = Source(title="من فهرسٍ لا نعرفه", registry="scopus-clone",
                    last_verified_at=_now(),
                    raw_metadata={"abstract": "<jats:p>نصّ.</jats:p>"})
    assert derived_abstracts(source)[0].provider in ABSTRACT_PROVIDERS


# ═════════════════ الاستخراج: الحالات الخصمية ═════════════════

def _read(text: str):
    from athera_api.services import matrix_extraction as mx

    return {f.field_key: f.value_ar
            for f in mx.grounded(mx.findings_in(mx.ReadPassage(text=text)))}


def test_a_causal_title_over_a_cross_sectional_study_yields_no_causal_claim():
    """**«أثر كذا في كذا» عنوانٌ لدراسةٍ مقطعية لا تقيس أثرًا.**

    والعنوان دعوى المؤلف لا نتيجته؛ ومن قرأه استخرج سببيةً لم تُقس،
    والقارئ يراها في عمود «النتائج» فيصدّقها ثم يبني عليها.
    """
    from athera_api.services import matrix_extraction as mx

    title = "The Effect of Screen Time on Academic Achievement"
    abstract = ("A cross-sectional survey was administered to 425 undergraduate "
                "students. The results show that screen time was negatively "
                "associated with achievement.")
    found = _read(abstract)

    # لا شيء يُقرأ من العنوان أصلًا — ولذلك لا مدخل له في هذا المسار.
    assert "title" not in mx.ReadPassage(text=abstract).__slots__
    assert title.lower() not in " ".join(found.values()).lower()
    assert found["design"].lower() == "cross-sectional"
    # نتيجةٌ اقترانية تُنقل كما قيلت — ولا تُقلب سببًا.
    assert "effect" not in found.get("findings", "").lower()
    assert "associated" in found["findings"]


def test_a_causal_finding_from_a_non_causal_design_is_dropped_not_softened():
    """**والصدق أولى من الاكتمال.** تبقى الخانة «غير مذكور» يملؤها الباحث."""
    causal = ("A cross-sectional questionnaire study of 300 nurses. "
              "The results show that workload increases burnout among nurses.")
    assert "findings" not in _read(causal)

    # وتجربةٌ محكمة تقيس السببية، فنتيجتها تُنقل كما قيلت.
    trial = ("A randomized controlled trial with 120 patients. "
             "The results show that the intervention reduces anxiety.")
    assert "reduces anxiety" in _read(trial)["findings"]


def test_implications_for_a_country_never_become_the_population_studied():
    """**جملةُ الدلالات تصف من تنفعه النتيجة لا من دُرس.**

    ومن أخذ منها اسم البلد جعل دراسةً على طلابٍ أمريكيين تُقرأ سعودية —
    ثم تُكتب في قسمٍ عن السياق المحلّي.
    """
    abstract = ("We surveyed 425 undergraduate students at three public "
                "universities in the United States. Findings have important "
                "implications for Saudi Arabia.")
    found = _read(abstract)
    assert "Saudi" not in found.get("population", "")
    assert "Saudi" not in found.get("context", "")
    assert "students" in found["population"]
    assert "United States" in found["context"]


def test_a_number_the_abstract_states_is_the_sample_and_nothing_else_is():
    """«استطلعنا ٤٢٥ طالبًا» ← العيّنة ٤٢٥. **ورقمٌ بلا قرينة ليس عيّنة.**"""
    assert _read("We surveyed 425 university students.")["sample"] == "425"
    assert _read("عينة قوامها 380 معلمًا.")["sample"] == "380"
    # سنةٌ مذكورة ليست حجم عيّنة، ورقمٌ بلا قرينةٍ ليس شيئًا.
    assert "sample" not in _read("Data were drawn from the 2019 wave.")
    assert "sample" not in _read("The instrument had 12 items.")


def test_a_decimal_is_never_read_as_an_invented_sample_number():
    """**درسٌ دفعه الإنتاج مرّتين، ولا يُتعلَّم ثالثة.**

    `0.003` كانت تُقرأ «003» عيّنةً مخترَعة؛ ثم `0,003` بالفاصلة اللاتينية
    بعد أول علاج. فيُنزع كل كسرٍ بأي فاصلة قبل البحث عن أرقام العيّنة.
    """
    from athera_api.services.matrix_extraction import sample_size

    for sentence in ("Participants were surveyed (p = 0.003).",
                     "Participants were surveyed (p = 0,003).",
                     "شملت الدراسة مشاركين (الدلالة ٠٫٠٠٣)."):
        found = sample_size(sentence)
        assert found is None or found not in {"003", "0", "3"}, (
            f"كسرٌ عشري قُرئ عيّنة: {sentence} ← {found}")
    # والرقم الحقيقي ما زال يُقرأ ولو جاوره كسر.
    assert sample_size("Participants were 250 teachers (p = 0.003).") == "250"


def test_a_theory_absent_from_the_abstract_is_missing_not_absent_by_decree():
    """**«لم تذكر الورقة نظريةً» غير «لم تُستعمل نظرية».**

    الأولى وصفٌ لما قرأناه، والثانية دعوى عن الدراسة لم يقلها أحد — ومن
    كتبها في المصفوفة نفى عن الورقة سندًا نظريًّا قد يكون في متنها.
    """
    from athera_api.services import matrix_extraction as mx

    found = _read("A cross-sectional survey of 200 employees was conducted.")
    assert "theory" not in found
    assert "theory" in mx.EXAMINED_FIELDS, "النظرية تُفحص، فيُكتب غيابها صراحةً"

    source = pathlib.Path(
        REPO / "apps" / "api" / "athera_api" / "services"
        / "matrix_extraction.py").read_text(encoding="utf-8")
    assert "no theory" not in source.lower()
    assert 'cell.cell_state = "missing"' in source


def test_a_recommendation_for_future_work_is_not_this_study_s_design():
    """«يُوصى بدراساتٍ طولية» لا تجعل الدراسة المقطعية طولية.

    وهو أخطر ما كُشف في تجربة هذا المستخرِج: ينقلب التصميم، فيُرفع حارسُ
    السببية عن دراسةٍ تحتاجه.
    """
    abstract = ("A cross-sectional survey of 425 students was conducted. "
                "Future research should use longitudinal designs.")
    found = _read(abstract)
    assert found["design"].lower() == "cross-sectional"
    assert "longitudinal" in found["gaps"].lower()


def test_nothing_reaches_the_screen_without_its_words_in_the_text():
    """حاجزُ الاختلاق نفسه الذي يحرس مرشّحات الذاكرة الموثقة — لا حاجزٌ ثانٍ."""
    from athera_api.services import matrix_extraction as mx

    passage = mx.ReadPassage(text="A cross-sectional survey.")
    invented = mx.Finding("sample", "425", "we surveyed 425 students", passage)
    assert mx.grounded([invented]) == []
    real = mx.Finding("design", "cross-sectional", "A cross-sectional survey.", passage)
    assert mx.grounded([real]) == [real]


def test_a_compound_value_is_checked_word_by_word_not_as_one_string():
    """«استبانة · مقابلات» لفظان وُجد كلٌّ منهما، والفاصل من عندنا.

    وفحصُ العبارة كلّها نصًّا واحدًا كان يرمي كل قيمةٍ فيها لفظان — فتظهر
    الأعمدة فارغة ولا يُعرف لماذا.
    """
    found = _read("Data were collected through a questionnaire and interviews.")
    assert "questionnaire" in found["method"] and "interviews" in found["method"]


# ═════════════════ ما تكتبه المنصّة يبقى مرشَّحًا ═════════════════

def test_metadata_only_yields_no_reading_at_all():
    """**عنوانٌ وسنةٌ لا يُقرأ منهما منهجٌ ولا عيّنة** — ومن قرأ فقد اخترع."""
    from athera_api.services import matrix_extraction as mx
    from athera_api.services.screening import METADATA_FIELDS

    for field_key in METADATA_FIELDS:
        assert field_key not in mx.EXAMINED_FIELDS, (
            f"عمودٌ وصفيّ يُملأ من الاستخراج: {field_key}")

    import inspect
    source = inspect.getsource(mx._passages)
    assert "if scope.scope == sc.METADATA_ONLY:" in source
    assert "return []" in source


def test_everything_the_platform_writes_stays_a_candidate():
    """`needs_review` و`unverified` و`model` — والقيد في القاعدة يشملها."""
    import inspect

    from athera_api.services import matrix_extraction as mx

    source = inspect.getsource(mx.extract_for_source)
    assert 'cell.extraction_method = "model"' in source
    assert 'cell.verification_status = "unverified"' in source
    assert 'cell.cell_state = "needs_review"' in source
    assert "cell.verified_by, cell.verified_at = None, None" in source


def test_a_researcher_cell_is_never_overwritten_by_a_machine_reading():
    """تشغيلةٌ آلية تصحّح ما صحّحه إنسان تُعلّمه ألّا يصحّح."""
    from athera_api.models.screening import LiteratureMatrixCell
    from athera_api.services.matrix_extraction import _is_replaceable

    mine = LiteratureMatrixCell(extraction_method="researcher",
                                verification_status="unverified")
    approved = LiteratureMatrixCell(extraction_method="model",
                                    verification_status="approved")
    rejected = LiteratureMatrixCell(extraction_method="model",
                                    verification_status="rejected")
    fresh = LiteratureMatrixCell(extraction_method="model",
                                 verification_status="unverified")
    assert _is_replaceable(mine) is False
    assert _is_replaceable(approved) is False
    assert _is_replaceable(rejected) is False
    assert _is_replaceable(fresh) is True


def test_a_page_number_is_never_derived_from_a_chunk_index():
    """**المقطع السابع ليس الصفحة السابعة.**

    ومن كتب ذلك أرسل القارئ إلى صفحةٍ لا تحمل ما نُسب إليها. فرقمُ الصفحة
    من `page_number` الذي قرأه المُقطِّع، و`None` حين لا يُعرف.
    """
    import inspect

    from athera_api.services import matrix_extraction as mx

    source = inspect.getsource(mx._passages)
    assert "page=chunk.page_number" in source
    assert "chunk.seq" not in source.split("return [ReadPassage")[-1]

    from athera_api.services import screening as sc
    assert mx._locator_for(sc.ABSTRACT_ONLY, mx.ReadPassage(text="x")) == "abstract"
    assert mx._locator_for(sc.FULL_TEXT, mx.ReadPassage(text="x")) is None
    assert mx._locator_for(sc.FULL_TEXT,
                           mx.ReadPassage(text="x", page=14)) == "ص. 14"
    assert mx._locator_for(sc.METADATA_ONLY, mx.ReadPassage(text="x")) is None


def test_the_review_reuses_the_platform_pattern_and_builds_no_second_one():
    """اعتماد · تعديلٌ ثم اعتماد · رفض · غير مذكور — نمطُ المنصّة نفسه.

    ونظامُ اعتمادٍ ثانٍ يعني شاشتين تفترقان: واحدةٌ تنسب الحكم إلى قائله
    وأخرى لا.
    """
    text = (SCREEN / "matrix" / "page.tsx").read_text(encoding="utf-8")
    ar, en = _catalogs()
    # الأفعال الثلاثة الأولى تُبنى من قائمةٍ واحدة، والرابع والخامس صريحان.
    assert '(["approved", "rejected", "unknown"] as const)' in text
    assert "matrix.verdict_${verdict}" in text
    assert "matrix.verdict_edit_then_approve" in text
    assert "matrix.verdict_not_stated" in text
    for key in ("verdict_approved", "verdict_rejected", "verdict_unknown",
                "verdict_edit_then_approve", "verdict_not_stated"):
        assert ar["matrix"].get(key, "").strip(), f"فعلٌ بلا اسم عربي: {key}"
        assert en["matrix"].get(key, "").strip(), f"verdict with no name: {key}"
    # والاعتماد يمرّ بمسار التحقّق القائم، لا بحفظٍ يعتمد نفسه.
    assert "verifyMatrixCell" in text
    # و«تعديلٌ ثم اعتماد» كتابةٌ ثم حكم — لا حفظٌ يكتب نفسه معتمَدًا.
    assert 'verifyMatrixCell(locale, projectId, row.source_id, fieldKey, "approved")' in text


# ═════════════════ الشاشة: تصفيح وتصفية واختيار ═════════════════

def test_the_screening_screen_asks_for_one_page_and_says_where_it_is():
    """سهمان بلا عددٍ لا يقولان أين أنت من كم."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert "common.previous" in text and "common.next" in text
    assert "data?.pages" in text
    assert "page_size: PAGE_SIZE" in text


def test_the_screening_counters_come_from_the_server_not_from_the_page():
    """عدٌّ فوق الصفحة المعروضة يقول صفرًا في كل تبويبٍ سوى المفتوح."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert "return view.all;" in text or "view.all" in text
    assert "cards.length" not in text.split("function countOf")[-1]


def test_the_filters_are_sent_to_the_server_and_never_applied_in_the_browser():
    """ألفُ مرجعٍ لا تُحمَّل إلى المتصفّح لتُرمى تسعُ مئة منها."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    lib = (WEB / "src" / "lib" / "screening.ts").read_text(encoding="utf-8")
    for key in ("year_from", "registry", "document_type", "open_access",
                "has_abstract", "has_full_text", "possible_duplicate"):
        assert key in text, f"مرشّحٌ لا يُرسَل إلى الخادم: {key}"
    assert "URLSearchParams" in lib
    # ولا تصفيةٌ على البطاقات المعروضة سوى اختيار الباحث نفسه.
    assert "cards.filter" in text and text.count("cards.filter") == 1


def test_a_three_state_filter_never_collapses_unset_into_no():
    """«بلا تحديد» ليست «لا» — وطيُّهما يُخفي دراساتٍ لم يستبعدها أحد."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert 'type Tri = "" | "yes" | "no";' in text
    assert 'value === "" ? undefined : value === "yes"' in text


def test_the_batch_is_one_request_not_a_loop_of_twenty():
    """**حلقةٌ من عشرين طلبًا تترك بعضه واقعًا وبعضه لا.**

    والباحث لا يعرف أيُّها وقع، فيعيد الأمر فيقع بعضه مرّتين.
    """
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    lib = (WEB / "src" / "lib" / "screening.ts").read_text(encoding="utf-8")
    assert "decideSources" in text
    assert "screening/batch" in lib
    # ولا حلقةٌ تنادي القرار المفرد لكل مختار.
    assert "chosenCards.map((card) => card.source_id)" in text
    assert "chosen.map" not in text.split("const decideChosen")[-1].split("};")[0]


def test_the_batch_exclusion_still_asks_for_its_reason():
    """الاستبعاد الجماعي حكمٌ يلزمه سبب — ولا استثناء لأنه كثير."""
    text = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert 'if (next === "excluded") {\n      setPending({ cards: chosenCards' in text
    assert "reasonIsComplete(pending)" in text


def test_every_repeated_control_in_the_new_surfaces_names_its_target():
    """زرٌّ اسمه «اقرأ آليًّا» بجانب مئةٍ مثله لا يُميَّز بالسمع."""
    matrix = (SCREEN / "matrix" / "page.tsx").read_text(encoding="utf-8")
    screening = (SCREEN / "screening" / "page.tsx").read_text(encoding="utf-8")
    assert 'aria-label={`${t("matrix.extract")}: ${describe(row)}`}' in matrix
    assert 'aria-label={`${t("screening.selectLabel")}: ${describe(card)}`}' in screening


def test_the_new_screens_still_tell_loading_from_empty_from_failed():
    """طلبٌ فشل يُعرض «لا مراجع» يجعل الباحث يظنّ بحثه خاليًا."""
    for name, prefix in (("screening", "screening"), ("matrix", "matrix")):
        text = (SCREEN / name / "page.tsx").read_text(encoding="utf-8")
        for state in ("loading", "failed", "empty"):
            assert f'data-testid="{prefix}-{state}"' in text
        assert 't("common.retry")' in text


def test_the_automatic_reading_reports_numbers_not_the_word_done():
    """«تمّ» وحدها لا تقول شيئًا يُتصرَّف على أساسه."""
    text = (SCREEN / "matrix" / "page.tsx").read_text(encoding="utf-8")
    for key in ("matrix.extractedFilled", "matrix.extractedMissing",
                "matrix.extractedKept", "matrix.extractNothingToRead"):
        assert key in text, f"حصيلةٌ ناقصة في الجواب: {key}"


def test_every_new_message_key_exists_in_both_locales():
    """**مفتاحٌ ناقص يُعرض مفتاحًا** — و`translator` يعيد المسار بلا فشل."""
    ar, en = _catalogs()

    def has(catalog: dict, path: str) -> bool:
        node: object = catalog
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    missing: list[str] = []
    for page in (SCREEN / "screening" / "page.tsx", SCREEN / "matrix" / "page.tsx"):
        text = page.read_text(encoding="utf-8")
        keys = set(re.findall(r't\(\s*"([a-zA-Z0-9_.]+)"\s*\)', text))
        keys |= set(re.findall(r'"((?:screening|matrix|common)\.[a-zA-Z0-9_]+)"', text))
        for key in sorted(keys):
            for label, catalog in (("ar", ar), ("en", en)):
                if not has(catalog, key):
                    missing.append(f"{page.name}: {key} [{label}]")
    assert not missing, "مفاتيح تُنادى ولا وجود لها: " + "; ".join(missing)


def test_no_state_is_set_synchronously_inside_an_effect():
    """قاعدةٌ يفرضها المدقّق خطأً لا تحذيرًا — فتُفحص هنا قبل CI."""
    for name in ("screening", "matrix"):
        text = (SCREEN / name / "page.tsx").read_text(encoding="utf-8")
        assert "void Promise.resolve().then" in text


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


async def _seed_source(tid: uuid.UUID, title: str, **fields) -> uuid.UUID:
    from athera_api.db import tenant_session
    from athera_api.models.literature import Source

    async with tenant_session(tid) as session:
        source = Source(tenant_id=tid, title=title, retraction_status="unknown",
                        access_state=fields.pop("access_state",
                                                "abstract_metadata_only"),
                        **fields)
        session.add(source)
        await session.flush()
        return source.id


async def _link(tid: uuid.UUID, uid: uuid.UUID, project_id: uuid.UUID,
                source_id: uuid.UUID, use_state: str = "saved_only") -> None:
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    async with tenant_session(tid, uid) as session:
        session.add(ProjectSource(
            tenant_id=tid, project_id=project_id, source_id=source_id,
            use_state=use_state, added_by=uid,
            decided_by=uid if use_state != "saved_only" else None,
            decided_at=_now() if use_state != "saved_only" else None))
        await session.flush()


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
async def test_an_abstract_is_invisible_and_unwritable_to_the_other_tenant(two_tenants):
    """**العزل من القاعدة لا من الاستعلام.** ملخّصُ مستأجرٍ لا يقرؤه غيره."""
    from sqlalchemy import select
    from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

    from athera_api.db import tenant_session
    from athera_api.models.screening import SourceAbstract
    from athera_api.services.screening import abstract_digest

    a, b = two_tenants["a"], two_tenants["b"]
    source = await _seed_source(a["tenant_id"], "ورقةٌ لها ملخّص")
    text = "هدفت الدراسة إلى كذا."

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        session.add(SourceAbstract(
            tenant_id=a["tenant_id"], source_id=source, provider="crossref",
            text=text, content_hash=abstract_digest(text), retrieved_at=_now()))
        await session.flush()

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        rows = (await session.execute(select(SourceAbstract))).scalars().all()
        assert rows == [], "ملخّصُ مستأجرٍ ظهر لغيره"

    with pytest.raises((IntegrityError, ProgrammingError, DBAPIError)):
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            session.add(SourceAbstract(
                tenant_id=a["tenant_id"], source_id=source, provider="openalex",
                text="نصّ مدسوس", content_hash=abstract_digest("نصّ مدسوس"),
                retrieved_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_two_indexes_may_both_keep_their_abstract_but_one_may_not_repeat_itself(
        two_tenants):
    """الوحدانية على (المرجع، المرسِل، البصمة): اختلافٌ صفٌّ ثانٍ، وتكرارٌ لا."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import SourceAbstract
    from athera_api.services.screening import abstract_digest

    a = two_tenants["a"]
    source = await _seed_source(a["tenant_id"], "ورقةٌ اختلف فيها فهرسان")

    async def _add(provider: str, text: str) -> None:
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(SourceAbstract(
                tenant_id=a["tenant_id"], source_id=source, provider=provider,
                text=text, content_hash=abstract_digest(text),
                retrieved_at=_now()))
            await session.flush()

    await _add("crossref", "نصّ Crossref")
    await _add("openalex", "نصّ OpenAlex مختلف")
    await _add("crossref", "نصّ Crossref مُحدَّث")

    with pytest.raises(IntegrityError):
        await _add("crossref", "نصّ Crossref")


@requires_db
@pytest.mark.asyncio
async def test_an_empty_abstract_is_not_an_abstract(two_tenants):
    """صفٌّ فارغ يجعل «لا ملخّص» تبدو ملخّصًا."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import SourceAbstract

    a = two_tenants["a"]
    source = await _seed_source(a["tenant_id"], "ورقةٌ بلا ملخّص")
    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(SourceAbstract(
                tenant_id=a["tenant_id"], source_id=source, provider="crossref",
                text="   ", content_hash="0" * 64, retrieved_at=_now()))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_page_number_is_refused_for_anything_but_full_text(two_tenants):
    """**والحارس في القاعدة لا في المسار وحده.**"""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الصفحات")
    source = await _seed_source(a["tenant_id"], "دراسةٌ بملخّص")
    await _link(a["tenant_id"], a["user_id"], project, source, "included")

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="sample", value_ar="425", cell_state="needs_review",
                source_scope="abstract_only", extraction_method="model",
                evidence_page=14, updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_cell_that_cites_an_abstract_must_have_been_read_from_one(two_tenants):
    """خليةٌ تدّعي نصًّا كاملًا وتنسب نفسها إلى ملخّصٍ تنسب إلى غير مصدرها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell, SourceAbstract
    from athera_api.services.screening import abstract_digest

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث النسبة")
    source = await _seed_source(a["tenant_id"], "دراسة")
    await _link(a["tenant_id"], a["user_id"], project, source, "included")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = SourceAbstract(
            tenant_id=a["tenant_id"], source_id=source, provider="crossref",
            text="نصّ", content_hash=abstract_digest("نصّ"), retrieved_at=_now())
        session.add(row)
        await session.flush()
        abstract_id = row.id

    with pytest.raises(IntegrityError):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            session.add(LiteratureMatrixCell(
                tenant_id=a["tenant_id"], project_id=project, source_id=source,
                field_key="method", value_ar="استبانة", cell_state="needs_review",
                source_scope="full_text", extraction_method="model",
                source_abstract_id=abstract_id, updated_by=a["user_id"]))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_one_project_never_sees_another_project_s_sources(two_tenants):
    """**العزل عزلُ بحثٍ كذلك.** و`RLS` لا تمنع تسرّبًا داخل المستأجر نفسه.

    فبحثان لباحثٍ واحد: ما فُرز في الأول لا يُعدّ في الثاني، ولا تظهر
    دراساته في مصفوفته — والحصر بـ`project_id` هو ما يمنع ذلك.
    """
    from athera_api.db import tenant_session
    from athera_api.services import screening

    a = two_tenants["a"]
    first = await _seed_project(a["tenant_id"], "البحث الأول")
    second = await _seed_project(a["tenant_id"], "البحث الثاني")
    mine = await _seed_source(a["tenant_id"], "دراسةُ البحث الأول")
    theirs = await _seed_source(a["tenant_id"], "دراسةُ البحث الثاني")
    await _link(a["tenant_id"], a["user_id"], first, mine, "included")
    await _link(a["tenant_id"], a["user_id"], second, theirs, "included")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        page = await screening.screening_page(
            session, tenant_id=a["tenant_id"], project_id=first)
        assert [card.source_id for card in page.cards] == [mine]
        assert page.tallies.included == 1

        rows = await screening.matrix_rows(
            session, tenant_id=a["tenant_id"], project_id=first)
        assert [row.source_id for row in rows] == [mine]


@requires_db
@pytest.mark.asyncio
async def test_a_duplicate_is_a_duplicate_inside_one_project_only(two_tenants):
    """ورقةٌ في بحثين ليست مكرّرة — ومن قال ذلك جعل الباحث يستبعد دليله."""
    from athera_api.db import tenant_session
    from athera_api.services import screening

    a = two_tenants["a"]
    first = await _seed_project(a["tenant_id"], "بحثٌ فيه نسخة")
    second = await _seed_project(a["tenant_id"], "بحثٌ فيه النسخة نفسها")
    one = await _seed_source(a["tenant_id"], "العنوان نفسه")
    two = await _seed_source(a["tenant_id"], "العنوان نفسه!")
    await _link(a["tenant_id"], a["user_id"], first, one)
    await _link(a["tenant_id"], a["user_id"], second, two)

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        assert await screening.duplicate_source_ids(
            session, tenant_id=a["tenant_id"], project_id=first) == frozenset()

    # وحين يجتمعان في بحثٍ واحد يُنبَّه عليهما — تنبيهًا لا حكمًا.
    await _link(a["tenant_id"], a["user_id"], first, two)
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        found = await screening.duplicate_source_ids(
            session, tenant_id=a["tenant_id"], project_id=first)
        assert found == frozenset({one, two})


@requires_db
@pytest.mark.asyncio
async def test_filters_are_applied_before_paging_and_the_counters_follow_them(
        two_tenants):
    """التصفية قبل القطع، والعدّاد يتبعها — لا يتبع الصفحة."""
    from athera_api.db import tenant_session
    from athera_api.services import screening

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحثٌ فيه سنوات")
    for year in range(2010, 2040):
        source = await _seed_source(a["tenant_id"], f"دراسة {year}",
                                    publication_year=year)
        await _link(a["tenant_id"], a["user_id"], project, source,
                    "included" if year % 2 == 0 else "saved_only")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        page = await screening.screening_page(
            session, tenant_id=a["tenant_id"], project_id=project,
            filters=screening.ScreeningFilters(year_from=2030), page=1,
            page_size=5)
        assert len(page.cards) == 5, "الصفحة لم تُقتطع"
        assert page.total == 10, "العدد يتبع التصفية لا الصفحة"
        assert page.tallies.all == 10
        assert page.tallies.included == 5 and page.tallies.saved_only == 5
        assert page.pages == 2

        # والحالُ وحدها تُسقَط من العدّ: العدّادات تبقى على السنة نفسها.
        with_state = await screening.screening_page(
            session, tenant_id=a["tenant_id"], project_id=project,
            filters=screening.ScreeningFilters(year_from=2030,
                                               use_state="included"),
            page=1, page_size=5)
        assert with_state.total == 5
        assert with_state.tallies.saved_only == 5, (
            "العدّاد أسقط بقيّة المرشّحات مع الحال")

        # **ولا مرجعَ يسقط من الوجهين.** كلُّ هذه المراجع بلا بيانات فهرس،
        # فكلُّها «بلا ملخّص» و«بلا نصّ كامل» — ولا واحدٌ منها يختفي.
        without = await screening.screening_page(
            session, tenant_id=a["tenant_id"], project_id=project,
            filters=screening.ScreeningFilters(has_abstract=False),
            page=1, page_size=1)
        assert without.total == 30, "مرجعٌ بلا بيانات فهرسٍ سقط من «بلا ملخّص»"
        no_text = await screening.screening_page(
            session, tenant_id=a["tenant_id"], project_id=project,
            filters=screening.ScreeningFilters(has_full_text=False),
            page=1, page_size=1)
        assert no_text.total == 30, "مرجعٌ بلا ملفٍّ سقط من «بلا نصّ كامل»"


@requires_db
@pytest.mark.asyncio
async def test_a_batch_that_fails_on_one_source_applies_to_none(two_tenants):
    """**تسعةَ عشرَ من عشرين أسوأ من صفرٍ من عشرين.**

    فالباحث يرى الخطأ فيعيد الأمر، فيقع بعضه مرّتين ولا يعرف أيُّها وقع.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الدفعة")
    other = await _seed_project(a["tenant_id"], "بحثٌ آخر")
    mine = []
    for index in range(19):
        source = await _seed_source(a["tenant_id"], f"دراسة {index}")
        await _link(a["tenant_id"], a["user_id"], project, source)
        mine.append(source)
    stranger = await _seed_source(a["tenant_id"], "دراسةٌ من بحثٍ آخر")
    await _link(a["tenant_id"], a["user_id"], other, stranger)

    async with _client(a["tenant_id"], a["user_id"]) as http:
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/screening/batch",
            json={"source_ids": [str(sid) for sid in [*mine, stranger]],
                  "use_state": "included"})
    assert answer.status_code == 404, answer.text

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        states = (await session.execute(
            select(ProjectSource.use_state).where(
                ProjectSource.tenant_id == a["tenant_id"],
                ProjectSource.project_id == project)
        )).scalars().all()
    assert set(states) == {"saved_only"}, (
        "وقع بعضُ الدفعة وقد رُفض بعضها — والمعاملة لم تُلغَ")


@requires_db
@pytest.mark.asyncio
async def test_a_batch_exclusion_without_a_reason_changes_nothing(two_tenants):
    """الاستبعاد الجماعي حكمٌ يلزمه سبب — ولا استثناء لأنه كثير."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الاستبعاد الجماعي")
    ids = []
    for index in range(3):
        source = await _seed_source(a["tenant_id"], f"دراسة {index}")
        await _link(a["tenant_id"], a["user_id"], project, source)
        ids.append(str(source))

    async with _client(a["tenant_id"], a["user_id"]) as http:
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/screening/batch",
            json={"source_ids": ids, "use_state": "excluded"})
    assert answer.status_code == 422
    assert answer.json()["error"]["code"] == "workspace.exclusion_needs_reason"

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        states = (await session.execute(
            select(ProjectSource.use_state).where(
                ProjectSource.tenant_id == a["tenant_id"],
                ProjectSource.project_id == project)
        )).scalars().all()
    assert set(states) == {"saved_only"}


@requires_db
@pytest.mark.asyncio
async def test_a_whole_batch_applies_together_when_every_check_passes(two_tenants):
    """ويقع كلُّه حين تصحّ الشروط — والعدد يقابل ما أُرسل."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحثٌ يُدرَج كلُّه")
    ids = []
    for index in range(20):
        source = await _seed_source(a["tenant_id"], f"دراسة {index}")
        await _link(a["tenant_id"], a["user_id"], project, source)
        ids.append(str(source))

    async with _client(a["tenant_id"], a["user_id"]) as http:
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/screening/batch",
            json={"source_ids": ids, "use_state": "included"})
    assert answer.status_code == 200, answer.text
    assert answer.json()["applied"] == 20

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        states = (await session.execute(
            select(ProjectSource.use_state).where(
                ProjectSource.tenant_id == a["tenant_id"],
                ProjectSource.project_id == project)
        )).scalars().all()
    assert set(states) == {"included"} and len(states) == 20


@requires_db
@pytest.mark.asyncio
async def test_the_extraction_writes_candidates_and_records_what_it_read(two_tenants):
    """**ما يُكتب مرشَّح، ومصدرُه محفوظٌ منسوبًا.**

    والعيّنة تُقرأ من الملخّص، والنظرية تُكتب «غير مذكور» ولا يُنفى وجودها.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell, SourceAbstract

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحث الاستخراج")
    abstract = ("A cross-sectional survey was administered. We surveyed 425 "
                "undergraduate students in the United States. The results show "
                "that screen time was negatively associated with achievement.")
    source = await _seed_source(
        a["tenant_id"], "The Effect of Screen Time on Achievement",
        registry="crossref", registry_id="10.1/x", last_verified_at=_now(),
        raw_metadata={"abstract": f"<jats:p>{abstract}</jats:p>", "type": "journal-article"})
    await _link(a["tenant_id"], a["user_id"], project, source, "included")

    async with _client(a["tenant_id"], a["user_id"]) as http:
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/matrix/extract",
            json={"source_ids": [str(source)]})
    assert answer.status_code == 200, answer.text
    result = answer.json()["results"][0]
    assert result["scope"] == "abstract_only"
    assert result["filled"] > 0

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        cells = {
            cell.field_key: cell
            for cell in (await session.execute(
                select(LiteratureMatrixCell).where(
                    LiteratureMatrixCell.tenant_id == a["tenant_id"],
                    LiteratureMatrixCell.project_id == project)
            )).scalars().all()
        }
        stored = (await session.execute(select(SourceAbstract))).scalars().all()

    assert cells["sample"].value_ar == "425"
    assert cells["sample"].cell_state == "needs_review"
    assert cells["sample"].extraction_method == "model"
    assert cells["sample"].verification_status == "unverified"
    assert cells["sample"].verified_by is None
    # ملخّصٌ لا صفحات له — والمُحدِّد كلمةٌ صريحة.
    assert cells["sample"].evidence_locator == "abstract"
    assert cells["sample"].evidence_page is None
    assert cells["sample"].source_abstract_id is not None

    # **الغياب غيابٌ لا نفي.** والنظرية لم تُذكر، فحالُها «غير مذكور» بلا قيمة.
    assert cells["theory"].cell_state == "missing"
    assert cells["theory"].value_ar is None

    # ولا سببيةٌ من دراسةٍ مقطعية: «الأثر» في العنوان ولا يبلغ المصفوفة.
    assert "effect" not in (cells["findings"].value_ar or "").lower()
    assert "المجتمع" not in (cells["population"].value_ar or "")
    assert "Saudi" not in (cells["context"].value_ar or "")

    # والملخّص حُفظ منسوبًا إلى مرسِله بوقته ومعرّفه.
    assert len(stored) == 1
    assert stored[0].provider == "crossref"
    assert stored[0].provider_identifier == "10.1/x"


@requires_db
@pytest.mark.asyncio
async def test_the_extraction_refuses_a_source_that_is_only_saved(two_tenants):
    """**المدرَجة وحدها تُقرأ.** و«محفوظ فقط» لم يُقرَّر بعدُ أنه دليل."""
    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحثٌ فيه محفوظ فقط")
    source = await _seed_source(
        a["tenant_id"], "دراسةٌ محفوظة", last_verified_at=_now(),
        raw_metadata={"abstract": "<jats:p>A cross-sectional survey of 200 nurses.</jats:p>"})
    await _link(a["tenant_id"], a["user_id"], project, source, "saved_only")

    async with _client(a["tenant_id"], a["user_id"]) as http:
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/matrix/extract",
            json={"source_ids": [str(source)]})
    assert answer.status_code == 409
    assert answer.json()["error"]["code"] == "workspace.matrix_needs_included_source"


@requires_db
@pytest.mark.asyncio
async def test_the_extraction_never_overwrites_what_the_researcher_wrote(two_tenants):
    """خانةٌ كتبها الباحث أو حكم فيها لا تُمسّ — ويُقال عددها."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.screening import LiteratureMatrixCell

    a = two_tenants["a"]
    project = await _seed_project(a["tenant_id"], "بحثُ ما كتبه الباحث")
    source = await _seed_source(
        a["tenant_id"], "دراسة", last_verified_at=_now(),
        raw_metadata={"abstract": "<jats:p>A cross-sectional survey of 200 nurses.</jats:p>"})
    await _link(a["tenant_id"], a["user_id"], project, source, "included")

    async with _client(a["tenant_id"], a["user_id"]) as http:
        written = await http.put(
            f"/api/v1/workspace/projects/{project}/matrix/{source}/sample",
            json={"cell_state": "known", "source_scope": "abstract_only",
                  "value_ar": "٢٠٠ ممرضة — كتبتُها بيدي"})
        assert written.status_code == 200, written.text
        answer = await http.post(
            f"/api/v1/workspace/projects/{project}/matrix/extract",
            json={"source_ids": [str(source)]})
    assert answer.status_code == 200, answer.text
    assert answer.json()["results"][0]["left_to_the_researcher"] >= 1

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        cell = (await session.execute(
            select(LiteratureMatrixCell).where(
                LiteratureMatrixCell.tenant_id == a["tenant_id"],
                LiteratureMatrixCell.project_id == project,
                LiteratureMatrixCell.field_key == "sample")
        )).scalar_one()
    assert cell.extraction_method == "researcher"
    assert cell.value_ar == "٢٠٠ ممرضة — كتبتُها بيدي"


@requires_db
@pytest.mark.asyncio
async def test_the_matrix_of_one_project_never_reads_another_project_s_cell(
        two_tenants):
    """خليةٌ في بحثٍ لا تظهر في مصفوفة بحثٍ آخر ولو كان المرجع واحدًا."""
    from athera_api.db import tenant_session
    from athera_api.services import screening

    a = two_tenants["a"]
    first = await _seed_project(a["tenant_id"], "بحثٌ فيه خلية")
    second = await _seed_project(a["tenant_id"], "بحثٌ بلا خلية")
    source = await _seed_source(a["tenant_id"], "مرجعٌ في بحثين")
    await _link(a["tenant_id"], a["user_id"], first, source, "included")
    await _link(a["tenant_id"], a["user_id"], second, source, "included")

    async with _client(a["tenant_id"], a["user_id"]) as http:
        written = await http.put(
            f"/api/v1/workspace/projects/{first}/matrix/{source}/method",
            json={"cell_state": "known", "source_scope": "metadata_only",
                  "value_ar": "قيمةُ البحث الأول"})
        assert written.status_code == 200, written.text

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        rows = await screening.matrix_rows(
            session, tenant_id=a["tenant_id"], project_id=second)
    method = next(cell for cell in rows[0].cells if cell.field_key == "method")
    assert method.cell_state == "missing"
    assert method.value_ar is None
