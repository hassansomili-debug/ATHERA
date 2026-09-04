"""طبقة التركيب | Literature synthesis (PUBRIVA).

**هذه أخطر مسارٍ علميّ في المنتج، وهذا الملف حارسه.**

ومقياسُ النجاح هنا مقلوب: لا يُقاس بعدد ما تجده الطبقة، بل بعدد ما **ترفض
أن تقوله**. فمنصّةٌ تُخرج لكل باحثٍ خمس فجواتٍ جاهزة تصير مصنع دعاوى،
وتُكتب دعاواها في أوراق تُنشر.

فيُثبت هنا ثمانية:

١) **تجميعٌ موضوعي لا يُطوى في موضوعٍ علمي** — والفرق عمودٌ في القاعدة.
٢) **لا موضوع بلا أثرٍ يُتتبَّع**: موضوع ← مرجع ← خلية ← شاهد.
٣) **التعارض في أربعٍ لا خامس**، واختلافُ البناءات أو الصياغة ليس منها.
٤) **الاختبارات السلبية الخمس للفجوات** — وهي غرض المسار كلّه.
٥) **الدعوى محدودةٌ بما بُحث**، ولا جملة مطلقة تخرج من الطبقة.
٦) **الفرصة من فجوةٍ معتمَدة وبتأكيد**، ولا مرجع يُقلَب إلى «مُدرَج» صامتًا.
٧) **العزل بين مستأجرين وبين بحثين في المستأجر الواحد** — والثاني هو
   العطب الذي وقع في هذا المنتج من قبل.
٨) **الشاشة تفرّق بين التحميل والفراغ والفشل**، وتُسمّي كل زرٍّ متكرّر.
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
             / "0025_literature_synthesis.py")
SCREEN = WEB / "src" / "app" / "[locale]" / "portfolio" / "[projectId]"
PAGES = ("themes", "contradictions", "gaps", "research-opportunities")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _migration_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0024", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ═════════════ أدوات بناء لقطةٍ خالصة (بلا قاعدة بيانات) ═════════════

def _cell(source_id, field_key, value, *, scope="abstract_only", state="known",
          cell_id=None, quote=None):
    from athera_api.services.synthesis.corpus import CellSnapshot

    return CellSnapshot(
        cell_id=cell_id if cell_id is not None else uuid.uuid4(),
        source_id=source_id, field_key=field_key, value_ar=value,
        cell_state=state, source_scope=scope, extraction_method="researcher",
        verification_status="unverified", evidence_quote=quote)


def _study(title, *, year=2021, scope="abstract_only", **fields):
    from athera_api.services.synthesis.corpus import StudySnapshot

    source_id = uuid.uuid4()
    cells = tuple(
        _cell(source_id, key, value, scope=scope)
        if value is not None else
        _cell(source_id, key, None, scope=scope, state="missing")
        for key, value in fields.items()
    )
    return StudySnapshot(source_id=source_id, title=title, publication_year=year,
                         reading_scope=scope, cells=cells)


def _corpus(*studies, registries=("crossref",), saved_only=0, excluded=0):
    from athera_api.services.synthesis.corpus import CorpusSnapshot

    return CorpusSnapshot(
        project_id=uuid.uuid4(), studies=tuple(studies), registries=registries,
        saved_only_count=saved_only, excluded_count=excluded, taken_at=_now())


# ═════════════════════ ١. الترحيل ═════════════════════

def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته.

    و«الجدول تحليليّ» ليس استثناءً من ADR-0002: مرشَّحُ فجوةٍ يحمل عناوين
    دراسات باحثٍ وخطّ تفكيره، وهو من أخصّ ما في المنصّة.
    """
    text = _migration_text()
    module = _migration_module()
    # الجداول السبعة كلّها في حلقةٍ واحدة — فلا يُنسى واحدٌ منها عند الإضافة.
    assert len(module.NEW_TABLES) == 7
    assert "for table in NEW_TABLES:" in text
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text
    # ولا جدولَ في النموذج خارج القائمة التي تُفعَّل عليها السياسة.
    from athera_api.models import synthesis as model

    tables = {value.__tablename__ for value in vars(model).values()
              if hasattr(value, "__tablename__")}
    assert tables == set(module.NEW_TABLES)


def test_the_migration_indexes_the_reads_the_screens_actually_make():
    text = _migration_text()
    for index in ("ix_theme_candidates_project", "ix_theme_candidate_supports_theme",
                  "ix_contradiction_candidates_project", "ix_contradiction_sides_parent",
                  "ix_gap_candidates_project", "ix_gap_candidate_sources_gap",
                  "ix_research_opportunities_project"):
        assert index in text, f"قراءةٌ معروضة بلا فهرس: {index}"


def test_the_migration_is_additive_and_follows_the_matrix():
    """**رقمٌ واحد لا يحمله ترحيلان.**

    كُتب هذا الترحيل `0024` وكُتب ترحيل ذكاء المصفوفة `0024` كذلك — وهما
    فرعان متوازيان. ولو دُمج الاثنان لصار لألمبيك رأسان، ولتوقّف ترحيل
    الإنتاج كلّه. فذكاء المصفوفة يملك `0024`، والتركيب يليه `0025`.
    """
    module = _migration_module()
    assert module.revision == "0025"
    assert module.down_revision == "0024"
    text = _migration_text()
    # لا `drop_column` ولا `drop_table` في الصعود — الترحيل يُضيف ولا يهدم.
    upgrade = text.split("def upgrade()")[1].split("def downgrade()")[0]
    assert "op.drop_table" not in upgrade
    assert "op.drop_column" not in upgrade


def test_the_downgrade_refuses_to_erase_a_human_judgement():
    """مرشَّحٌ حُكم فيه قرارٌ بشريّ، وإسقاط الجدول عليه إتلافُه لإرضاء تنازل."""
    text = _migration_text()
    assert "def downgrade()" in text
    assert "downgrade refused" in text
    assert "decided_by IS NOT NULL" in text
    assert "FROM research_opportunities" in text
    assert 'op.drop_table("theme_candidates")' in text


def test_the_downgrade_drops_every_table_the_upgrade_created():
    """جدولٌ يُنشأ ولا يُسقَط يجعل التنازل ينفجر بعد أن بدأ."""
    module = _migration_module()
    text = _migration_text()
    downgrade = text.split("def downgrade()")[1]
    for table in module.NEW_TABLES:
        assert f'op.drop_table("{table}")' in downgrade, f"لم يُسقَط {table}"
    assert "uq_literature_matrix_cells_project_scoped" in downgrade


def test_the_downgrade_drops_every_index_the_upgrade_created():
    """فهرسٌ يُنشأ ولا يُسقَط يجعل تدريب head→base→head ينفجر في منتصفه."""
    text = _migration_text()
    upgrade, downgrade = text.split("def downgrade()")
    created = set(re.findall(r'op\.create_index\(\s*"([a-z_]+)"', upgrade))
    dropped = set(re.findall(r'op\.drop_index\(\s*"([a-z_]+)"', downgrade))
    assert created and created == dropped, (
        f"أُنشئ {sorted(created)} وأُسقط {sorted(dropped)}")


def test_the_downgrade_drops_the_tables_before_what_they_point_at():
    """**ترتيبُ الإسقاط ليس ذوقًا.** جدولٌ يُسقَط قبل تابعِه يفشل بمفتاحٍ أجنبي.

    والقيدُ الفريد على خلايا المصفوفة يُسقَط آخرَ شيء: ثلاثة مفاتيح أجنبية
    تشير إليه، ولا يذهب قبلها.
    """
    downgrade = _migration_text().split("def downgrade()")[1]
    order = re.findall(r'op\.drop_table\("([a-z_]+)"\)', downgrade)
    for child, parent in (("research_opportunities", "gap_candidates"),
                          ("gap_candidate_sources", "gap_candidates"),
                          ("gap_candidates", "contradiction_candidates"),
                          ("contradiction_sides", "contradiction_candidates"),
                          ("theme_candidate_supports", "theme_candidates")):
        assert order.index(child) < order.index(parent), (
            f"{child} يُسقَط بعد {parent}")
    tail = downgrade.rsplit('op.drop_table("theme_candidates")', 1)[1]
    assert "uq_literature_matrix_cells_project_scoped" in tail


def test_the_opportunity_link_does_not_restrict_a_whole_project_delete():
    """`ON DELETE RESTRICT` يفحص فورًا، فيصطدم حذفُ بحثٍ كاملًا بنفسه.

    والافتراضيّ يؤجّل الفحص إلى آخر العبارة: يمنع حذف فجوةٍ وحدها من تحت
    فرصتها، ويسمح بذهاب الاثنين معًا مع بحثهما.
    """
    text = _migration_text()
    block = text.split("fk_research_opportunities_gap\"")[0]
    clause = block.rsplit('["gap_candidates.id", "gap_candidates.status"]', 1)[1]
    assert 'onupdate="RESTRICT"' in clause
    assert 'ondelete="RESTRICT"' not in clause


def test_the_model_and_the_migration_agree_column_by_column():
    """عمودٌ في النموذج لا يقابله عمودٌ في الترحيل يسقط في الإنتاج وحده."""
    from athera_api.models import synthesis as model

    text = _migration_text()
    for table in (model.ThemeCandidate, model.ThemeCandidateSupport,
                  model.ContradictionCandidate, model.ContradictionSide,
                  model.GapCandidate, model.GapCandidateSource,
                  model.ResearchOpportunity):
        for column in table.__table__.columns:
            assert f'"{column.name}"' in text, (
                f"{table.__tablename__}.{column.name} في النموذج ولا وجود له "
                "في الترحيل 0024")


def test_every_vocabulary_the_code_writes_is_permitted_by_the_migration():
    """**الخطأ المتكرر في هذا المستودع**: مفردةٌ تُكتب بجانب سجلّها.

    وتُقابَل هنا مجموعةً بمجموعة لا وجودَ نصٍّ في ملفّ: قيمةٌ زائدة في القيد
    لا يعرفها النموذج عيبٌ كذلك.
    """
    from athera_api.models import synthesis as model

    migration = _migration_module()
    for label, mine, theirs in (
        ("دورة الحياة", model.SYNTHESIS_STATUSES, migration.SYNTHESIS_STATUSES),
        ("أساس الموضوع", model.THEME_BASES, migration.THEME_BASES),
        ("طرق التوليد", model.GENERATION_METHODS, migration.GENERATION_METHODS),
        ("أدوار السند", model.SUPPORT_ROLES, migration.SUPPORT_ROLES),
        ("أدوار مراجع الفجوة", model.GAP_SOURCE_ROLES, migration.GAP_SOURCE_ROLES),
        ("أنواع التعارض", model.CONFLICT_KINDS, migration.CONFLICT_KINDS),
        ("اتجاهات الأثر", model.EFFECT_DIRECTIONS, migration.EFFECT_DIRECTIONS),
        ("حالات الدلالة", model.SIGNIFICANCE_STATES, migration.SIGNIFICANCE_STATES),
        ("أنواع الفجوات", model.GAP_TYPES, migration.GAP_TYPES),
        ("درجات القوّة", model.GAP_STRENGTHS, migration.GAP_STRENGTHS),
        ("مدى القراءة", model.SOURCE_SCOPES, migration.SOURCE_SCOPES),
    ):
        assert tuple(mine) == tuple(theirs), (
            f"{label}: النموذج يقول {mine!r} والترحيل يقول {theirs!r}")


def test_the_reading_scope_vocabulary_is_the_one_0023_defined():
    """مفردةٌ ثانية لمدى القراءة تجعل خليةً تُقرأ في مكانٍ بمعنًى وفي آخر بآخر."""
    from athera_api.models.screening import SOURCE_SCOPES as SCREENING_SCOPES
    from athera_api.models.synthesis import SOURCE_SCOPES

    assert tuple(SOURCE_SCOPES) == tuple(SCREENING_SCOPES)


def test_the_database_itself_refuses_an_opportunity_over_an_unapproved_gap():
    """**الحارس في القاعدة لا في الخدمة وحدها.**

    ومفتاحٌ أجنبيٌّ مركّب يضمّ الحال يجعل «فرصةٌ فوق فجوةٍ مولَّدة» غير قابلة
    للكتابة أصلًا؛ و`ON UPDATE RESTRICT` يمنع سحب الاعتماد من تحتها.
    """
    text = _migration_text()
    assert 'sa.CheckConstraint("gap_status = \'approved\'"' in text
    assert '["gap_candidates.id", "gap_candidates.status"]' in text
    assert 'onupdate="RESTRICT"' in text
    assert 'sa.UniqueConstraint("id", "status", name="uq_gap_candidates_status")' in text


def test_the_migration_makes_same_tenant_cross_project_leakage_structural():
    """**RLS لا تحمي بين بحثين في مستأجرٍ واحد** — وهذا عطبٌ وقع هنا من قبل.

    فكل صفٍّ تابع يرتبط بأبيه بمفتاحٍ مركّب يضمّ `project_id`، فيستحيل
    بنيويًّا أن يسند موضوعٌ في بحثٍ إلى خليةٍ في بحثٍ آخر.
    """
    text = _migration_text()
    assert "uq_literature_matrix_cells_project_scoped" in text
    for name in ("fk_theme_candidate_supports_cell", "fk_contradiction_sides_cell",
                 "fk_gap_candidate_sources_cell"):
        assert name in text, f"سندٌ بلا حارسٍ بنيويّ للبحث: {name}"
    assert text.count(
        '["literature_matrix_cells.id", "literature_matrix_cells.project_id"]') == 3
    for name in ("fk_theme_candidate_supports_theme", "fk_contradiction_sides_parent",
                 "fk_gap_candidate_sources_gap"):
        assert name in text


def test_a_gap_row_cannot_exist_without_its_bounds():
    """فجوةٌ بلا عددٍ نُظر فيه ولا فهارس ولا حدودٍ معلنة **دعوى**."""
    text = _migration_text()
    assert '"sources_considered > 0"' in text
    assert "jsonb_exists(search_scope, 'indexes_searched')" in text
    assert '"length(btrim(known_limitations_ar)) > 0"' in text
    assert '"length(btrim(uncertainties_ar)) > 0"' in text


# ═════════════════════ ٢. المفردات ═════════════════════

def test_the_lifecycle_reuses_the_platform_words_and_invents_none():
    """**ولا `UNKNOWN`-جديدة ولا `UNSURE` ولا `MAYBE`.**

    `needs_review` مفردةُ حالة الخلية في 0023 و«دماغ البحث»، و`unknown`
    مفردةُ ترحيل 0016 — والثالثة هي التي تحفظ الفرق بين «رفضتُه» و«لم
    أستطع الحكم».
    """
    from athera_api.models.screening import CELL_STATES, VERIFICATION_STATES
    from athera_api.models.synthesis import DECIDABLE_STATUSES, SYNTHESIS_STATUSES

    assert "needs_review" in CELL_STATES and "needs_review" in SYNTHESIS_STATUSES
    assert "unknown" in VERIFICATION_STATES and "unknown" in SYNTHESIS_STATUSES
    for invented in ("unsure", "maybe", "uncertain", "possible", "likely"):
        assert invented not in SYNTHESIS_STATUSES
    # و`generated` حالُ نشأةٍ لا يقبلها الـAPI مُدخَلًا: قبولها محوُ مراجعة.
    assert "generated" in SYNTHESIS_STATUSES
    assert "generated" not in DECIDABLE_STATUSES
    assert set(DECIDABLE_STATUSES) == set(SYNTHESIS_STATUSES) - {"generated"}


def test_marking_needs_review_is_a_decision_and_carries_its_author():
    """**«يحتاج مراجعة» حكمُ باحثٍ نظر فتوقّف** — لا حالُ نشأةٍ ثانية.

    ولو عُدَّت بلا صاحبٍ لوقع عطبان: يُمحى أثر من وسمها، ثم تمحوها إعادةُ
    التوليد لأنها «لم يُحكم فيها». فالقيد في القاعدة يستثني `generated`
    وحدها، والعقد يقبل الأربع الباقية مُدخَلًا.
    """
    from athera_api.models.synthesis import AUTHORLESS_STATUSES, DECIDABLE_STATUSES

    assert AUTHORLESS_STATUSES == ("generated",)
    assert "needs_review" in DECIDABLE_STATUSES
    text = _migration_text()
    assert "\"(status = 'generated') = (decided_by IS NULL)\"" in text
    assert "(status IN ('generated', 'needs_review')) = (decided_by IS NULL)" not in text


def test_the_decision_contract_refuses_to_reset_a_candidate_to_generated():
    from pydantic import ValidationError

    from athera_api.schemas.synthesis import DecisionRequest

    assert DecisionRequest(status="unknown").status == "unknown"
    with pytest.raises(ValidationError):
        DecisionRequest(status="generated")
    with pytest.raises(ValidationError):
        DecisionRequest(status="maybe")


def test_strength_is_described_never_a_percentage():
    """**«٧٣٪ ثقة» رقمٌ لا يقابله قياس** — لا عيّنة ولا توزيع ولا خطأ معياري."""
    from athera_api.models.synthesis import GAP_STRENGTHS
    from athera_api.services.synthesis.vocab import STRENGTH_LABELS, STRENGTH_MEANING

    assert GAP_STRENGTHS == ("weak_signal", "emerging_pattern", "supported_candidate")
    for key in GAP_STRENGTHS:
        for table in (STRENGTH_LABELS, STRENGTH_MEANING):
            assert table[key]["ar"].strip(), f"{key} بلا نصّ عربي"
        # ولا رقمًا ولا نسبةً في أيّ معنًى معروض.
        assert "%" not in STRENGTH_MEANING[key]["ar"]
        assert "٪" not in STRENGTH_MEANING[key]["ar"]
        assert not re.search(r"\d", STRENGTH_MEANING[key]["ar"])


def test_a_strength_never_exceeds_the_ceiling_of_its_corpus():
    from athera_api.services.synthesis.vocab import strength_at_most

    assert strength_at_most("supported_candidate", "weak_signal") == "weak_signal"
    assert strength_at_most("weak_signal", "supported_candidate") == "weak_signal"
    assert strength_at_most("emerging_pattern", "emerging_pattern") == "emerging_pattern"


def test_every_researcher_facing_vocabulary_carries_both_locales():
    from athera_api.services.synthesis import vocab

    tables = (vocab.STATUS_LABELS, vocab.BASIS_LABELS, vocab.BASIS_MEANING,
              vocab.STRENGTH_LABELS, vocab.STRENGTH_MEANING, vocab.GAP_TYPE_LABELS,
              vocab.CONFLICT_LABELS, vocab.DIRECTION_LABELS,
              vocab.SIGNIFICANCE_LABELS, vocab.CONTEXT_DIMENSION_LABELS)
    for table in tables:
        for key, entry in table.items():
            assert entry.get("ar", "").strip(), f"{key} بلا عربية"
            assert entry.get("en", "").strip(), f"{key} بلا إنجليزية"


# ═════════════════════ ٣. الموضوعات ═════════════════════

def test_titles_alone_produce_a_topic_cluster_and_never_a_scientific_theme():
    """**العنوان ليس نتيجة.** عشرُ دراساتٍ تشترك في كلمة تُرتَّب، ولا تُستنتج."""
    from athera_api.models.synthesis import CONTENT_SYNTHESIS, TOPIC_CLUSTER
    from athera_api.services.synthesis import propose_themes

    corpus = _corpus(
        _study("التحول الرقمي في المصارف", findings=None),
        _study("التحول الرقمي في التعليم", findings=None),
    )
    proposals = propose_themes(corpus)
    assert proposals, "لم يُقترح تجميعٌ موضوعي رغم اشتراك العناوين"
    assert all(p.basis == TOPIC_CLUSTER for p in proposals)
    assert not any(p.basis == CONTENT_SYNTHESIS for p in proposals)
    for proposal in proposals:
        assert all(s.evidence_scope == "metadata_only" for s in proposal.supports)
        assert all(s.matrix_cell_id is None for s in proposal.supports)


def test_a_topic_cluster_says_in_its_own_words_that_it_is_not_a_finding():
    """الفرق يُكتب للباحث نصًّا، لا يُترك ليُستنتج من لونٍ في الشاشة."""
    from athera_api.services.synthesis import propose_themes
    from athera_api.services.synthesis.vocab import BASIS_MEANING

    corpus = _corpus(_study("التحول الرقمي في المصارف"),
                     _study("التحول الرقمي في التعليم"))
    assert "ليس" in BASIS_MEANING["topic_cluster"]["ar"] or (
        "not a finding" in BASIS_MEANING["topic_cluster"]["en"])
    for proposal in propose_themes(corpus):
        assert "لا نتيجة" in proposal.description_ar


def test_content_read_from_the_matrix_produces_a_theme_bound_to_its_cells():
    """**لا موضوع بلا أثر**: موضوع ← مرجع ← خلية ← شاهد."""
    from athera_api.models.synthesis import CONTENT_SYNTHESIS
    from athera_api.services.synthesis import propose_themes
    from athera_api.services.synthesis.themes import traceability_is_complete

    corpus = _corpus(
        _study("دراسة أولى", constructs="الرضا الوظيفي والالتزام التنظيمي"),
        _study("دراسة ثانية", constructs="الالتزام التنظيمي والرضا الوظيفي"),
    )
    content = [p for p in propose_themes(corpus) if p.basis == CONTENT_SYNTHESIS]
    assert content, "محتوًى مقروءٌ في دراستين ولم يُقترح موضوعٌ علمي"
    for proposal in content:
        assert len(proposal.source_ids) >= 2
        assert proposal.is_traceable
        assert traceability_is_complete(proposal)
        for support in proposal.supports:
            assert support.matrix_cell_id is not None
            assert support.evidence_scope != "metadata_only"
            assert support.basis_field_key in (
                "constructs", "problem", "objective", "theory", "findings")


def test_a_theme_label_is_readable_arabic_not_a_normalised_key():
    """موضوعٌ اسمه «احصاييا» يقرؤه الباحث عطبًا لا نتيجة."""
    from athera_api.services.synthesis import propose_themes

    corpus = _corpus(_study("أولى", constructs="الأداء الوظيفي"),
                     _study("ثانية", constructs="الأداء الوظيفي"))
    labels = [p.label_ar for p in propose_themes(corpus)]
    assert "الأداء" in labels, labels


def test_a_single_study_is_a_study_not_a_theme():
    from athera_api.services.synthesis import propose_themes

    assert propose_themes(_corpus(_study("وحيدة", constructs="الرضا"))) == ()


def test_the_same_matrix_produces_the_same_themes_in_the_same_order():
    """**مخرَجٌ يتبدّل بين تشغيلتين لا يُراجَع ولا يُقارَن.**"""
    from athera_api.services.synthesis import propose_themes

    corpus = _corpus(
        _study("أولى", constructs="الرضا الوظيفي", findings="علاقة إيجابية"),
        _study("ثانية", constructs="الرضا الوظيفي", findings="علاقة إيجابية"),
        _study("ثالثة", constructs="الالتزام التنظيمي"),
    )
    first = [(p.basis, p.label_ar) for p in propose_themes(corpus)]
    second = [(p.basis, p.label_ar) for p in propose_themes(corpus)]
    assert first == second and first


def test_a_content_theme_ranks_above_a_topic_cluster_and_never_hides_it():
    from athera_api.models.synthesis import CONTENT_SYNTHESIS, TOPIC_CLUSTER
    from athera_api.services.synthesis import propose_themes

    corpus = _corpus(
        _study("الحوكمة في المصارف", constructs="الرضا الوظيفي"),
        _study("الحوكمة في التعليم", constructs="الرضا الوظيفي"),
    )
    bases = [p.basis for p in propose_themes(corpus)]
    assert CONTENT_SYNTHESIS in bases and TOPIC_CLUSTER in bases
    assert bases.index(CONTENT_SYNTHESIS) < bases.index(TOPIC_CLUSTER)


# ═════════════════════ ٤. التعارضات ═════════════════════

def test_opposite_directions_on_the_same_constructs_are_a_contradiction():
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا", context="السعودية"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا", context="الولايات المتحدة"),
    )
    found = propose_contradictions(corpus)
    assert len(found) == 1
    assert found[0].conflict_kind == "direction"


def test_different_constructs_are_never_a_contradiction():
    """**دراستان عن شيئين مختلفين لا تتعارضان** مهما اختلفت نتيجتاهما."""
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا"),
        _study("ثانية", constructs="التدريب والرضا",
               findings="أثر سلبي دال إحصائيًا"),
    )
    assert propose_contradictions(corpus) == ()


def test_a_shared_word_alone_does_not_make_two_studies_comparable():
    """التقابل تطابقٌ لا تقاطع — وأكثرُ ورقتين في حقلٍ تشتركان في كلمة."""
    from athera_api.services.synthesis.contradictions import constructs_are_comparable

    assert constructs_are_comparable(frozenset({"تدريب", "اداء"}),
                                     frozenset({"اداء", "تدريب"})) is True
    assert constructs_are_comparable(frozenset({"تدريب", "اداء"}),
                                     frozenset({"تدريب", "رضا"})) is False
    assert constructs_are_comparable(frozenset(), frozenset()) is False


def test_different_wording_for_the_same_result_is_not_a_contradiction():
    """«علاقة إيجابية دالّة» و«ارتباط موجب ذو دلالة إحصائية» قولٌ واحد."""
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="ارتباط موجب دال إحصائيًا بين المتغيرين"),
    )
    assert propose_contradictions(corpus) == ()


def test_silence_is_never_half_of_a_contradiction():
    """«لم تُذكر الدلالة» ليست «غير دالّ» — وخلطهما يصنع تعارضًا من صمت."""
    from athera_api.services.synthesis import propose_contradictions
    from athera_api.services.synthesis import textual

    assert textual.significance_of(None) == "not_stated"
    assert textual.direction_of("درست العلاقة بين المتغيرين") == "not_stated"
    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="درست العلاقة بين المتغيرين في بيئة العمل"),
    )
    assert propose_contradictions(corpus) == ()


def test_a_metadata_only_row_can_never_be_a_side_of_a_contradiction():
    """التعارض حكمٌ على نتيجتين مقروءتين لا على عنوانين."""
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", scope="metadata_only", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا"),
        _study("ثانية", scope="metadata_only", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا"),
    )
    assert propose_contradictions(corpus) == ()


def test_effect_versus_no_effect_and_significant_versus_not_are_both_conflicts():
    from athera_api.services.synthesis.contradictions import (
        SideSnapshot,
        conflict_between,
    )

    def side(direction, significance):
        return SideSnapshot(source_id=uuid.uuid4(), title="د", result_ar="ن",
                            direction=direction, significance=significance,
                            evidence_scope="abstract_only")

    assert conflict_between(side("positive", "significant"),
                            side("negative", "significant")) == "direction"
    assert conflict_between(side("positive", "significant"),
                            side("none", "not_stated")) == "effect_presence"
    assert conflict_between(side("positive", "significant"),
                            side("positive", "not_significant")) == "significance"
    assert conflict_between(side("positive", "significant"),
                            side("positive", "significant")) is None
    # ولا يُقابَل صمتٌ بقولٍ فيُعدّ تعارضًا.
    assert conflict_between(side("positive", "significant"),
                            side("not_stated", "not_stated")) is None


def test_the_contradiction_surfaces_the_context_instead_of_saying_they_conflict():
    """«إحداهما درست المستهلكين في السعودية والأخرى موظفي شركات في الولايات
    المتحدة» أنفع من «الدراستان تتعارضان»."""
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا",
               context="عينة من المستهلكين في السعودية",
               population="المستهلكون"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا",
               context="موظفو شركات في الولايات المتحدة",
               population="موظفو الشركات"),
    )
    found = propose_contradictions(corpus)
    assert len(found) == 1
    item = found[0]
    assert "country" in item.context_divergence
    assert "population" in item.context_divergence
    assert "السعودية" in item.context_explanation_ar
    assert "الولايات المتحدة" in item.context_explanation_ar


def test_an_unrecorded_context_is_reported_as_unrecorded_not_as_agreement():
    """غيابُ التسجيل ليس غيابًا للاختلاف — ولا يُقال «الظروف واحدة»."""
    from athera_api.services.synthesis import propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا"),
    )
    item = propose_contradictions(corpus)[0]
    assert item.context_divergence == ()
    assert "لم يُسجَّل" in item.context_explanation_ar
    assert "ليس غيابًا للاختلاف" in item.context_explanation_ar


def test_no_study_is_ever_called_wrong():
    """**الحكم في نزاعٍ علميّ ليس للمنصّة.**"""
    from athera_api.services.synthesis import propose_contradictions
    from athera_api.services.synthesis.vocab import FORBIDDEN_VERDICT_WORDS

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا", context="السعودية"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا", context="مصر"),
    )
    for item in propose_contradictions(corpus):
        blob = " ".join([item.relationship_ar, item.context_explanation_ar])
        for word in FORBIDDEN_VERDICT_WORDS:
            assert word not in blob, f"وُصفت دراسةٌ بـ«{word}»: {blob}"


# ═════════ ٥. الاختبارات السلبية الخمس — غرضُ المسار كلّه ═════════

def test_negative_1_two_articles_are_not_enough_for_a_broad_gap():
    """**١) مقالتان فقط ← لا فجوةَ عامّة، والسبب يُعلَن لا يُسكت عنه.**"""
    from athera_api.services.synthesis import assess_gaps
    from athera_api.services.synthesis.gaps import BROAD_GAP_TYPES

    corpus = _corpus(
        _study("أولى", constructs="الرضا", findings="علاقة إيجابية دالة إحصائيًا",
               theory="نظرية التبادل الاجتماعي", context="السعودية"),
        _study("ثانية", constructs="الرضا", findings="علاقة إيجابية دالة إحصائيًا",
               theory="نظرية التبادل الاجتماعي", context="السعودية"),
    )
    result = assess_gaps(corpus)
    assert result.corpus_size == 2
    for proposal in result.proposals:
        assert proposal.gap_type not in BROAD_GAP_TYPES, (
            f"فجوةٌ عامّة على مقالتين: {proposal.gap_type}")
    # والعجز يُعلَن باسمه بمفردة محرّك القواعد.
    reasons = {item.gap_type: item for item in result.not_assessed}
    assert "theory_gap" in reasons
    assert reasons["theory_gap"].verdict == "insufficient_information"
    assert "2" in reasons["theory_gap"].reason_ar


def test_negative_2_no_theory_in_an_abstract_is_not_a_theory_gap():
    """**٢) غيابُ ذكر النظرية ليس غيابًا للنظرية.**

    وأكثر الملخّصات لا تذكر إطارها النظري أصلًا؛ فمن استنتج من صمتها فجوةً
    نظرية استنتج من عادةِ كتابةٍ حكمًا على حقل.
    """
    from athera_api.services.synthesis import assess_gaps

    corpus = _corpus(*[
        _study(f"دراسة {i}", scope="abstract_only", constructs="الرضا الوظيفي",
               findings="علاقة إيجابية دالة إحصائيًا", theory=None)
        for i in range(6)
    ])
    result = assess_gaps(corpus)
    assert not any(p.gap_type == "theory_gap" for p in result.proposals)
    reason = next(item for item in result.not_assessed
                  if item.gap_type == "theory_gap")
    assert reason.verdict == "insufficient_information"
    assert "ليس غيابًا للنظرية" in reason.reason_ar


def test_negative_3_no_saudi_sample_is_a_corpus_observation_not_a_global_claim():
    """**٣) لا عيّنة سعودية ← فجوةُ سياقٍ محتملة داخل المجموعة، لا دعوى عالمية.**"""
    from athera_api.services.synthesis import assess_gaps
    from athera_api.services.synthesis.vocab import FORBIDDEN_ABSOLUTE_CLAIMS

    corpus = _corpus(
        _study("أولى", context="موظفون في مصر", constructs="الرضا"),
        _study("ثانية", context="موظفون في الأردن", constructs="الرضا"),
        _study("ثالثة", context="موظفون في تركيا", constructs="الرضا"),
        registries=("crossref", "openalex"), saved_only=4,
    )
    result = assess_gaps(corpus, watched_contexts=("السعودية",))
    context_gaps = [p for p in result.proposals if p.gap_type == "context_gap"]
    assert len(context_gaps) == 1
    gap = context_gaps[0]
    assert gap.strength == "weak_signal", "غيابُ سياقٍ من قائمةٍ ليس أكثر من إشارة"
    # الدعوى نفسها خاليةٌ من كل صيغةٍ مطلقة. (ونصُّ الحدود يقتبس العبارة
    # ليمنعها صراحةً، فيُستثنى — وحارسٌ يعاقب على تحذيرٍ صادق يُعطَّل.)
    for phrase in FORBIDDEN_ABSOLUTE_CLAIMS:
        assert phrase not in gap.description_ar
        assert phrase not in gap.why_suggested_ar
    assert "مجموعة المراجع الحالية" in gap.description_ar
    assert "3 دراسةً مُدرَجة" in gap.description_ar
    assert "crossref" in gap.description_ar and "openalex" in gap.description_ar
    assert gap.sources_considered == 3
    assert gap.search_scope["search_was_systematic"] is False
    # والحدود تحذّر بالنصّ من كتابتها بصيغة الغياب المطلق.
    assert "لا توجد دراسات" in gap.known_limitations_ar
    assert "لم تظهر" in gap.known_limitations_ar


def test_negative_3b_an_unrecorded_context_column_blocks_the_judgement_entirely():
    """ومصفوفةٌ خاليةُ أعمدة السياق لا تقول «لا سياق سعودي»؛ تقول إنها خالية."""
    from athera_api.services.synthesis import assess_gaps

    corpus = _corpus(_study("أولى", constructs="الرضا"),
                     _study("ثانية", constructs="الرضا"))
    result = assess_gaps(corpus, watched_contexts=("السعودية",))
    assert not any(p.gap_type == "context_gap" for p in result.proposals)
    reason = next(i for i in result.not_assessed if i.gap_type == "context_gap")
    assert reason.verdict == "insufficient_information"
    assert "غيابُ التسجيل ليس غيابًا للسياق" in reason.reason_ar


def test_negative_4_disagreement_yields_contradictory_evidence_and_nothing_else():
    """**٤) دراستان تختلفان ← «أدلة متعارضة» وحدها، لا فجوةٌ من جنسٍ آخر.**"""
    from athera_api.services.synthesis import assess_gaps, propose_contradictions

    corpus = _corpus(
        _study("أولى", constructs="التدريب والأداء",
               findings="علاقة إيجابية دالة إحصائيًا", context="السعودية"),
        _study("ثانية", constructs="الأداء والتدريب",
               findings="أثر سلبي دال إحصائيًا", context="السعودية"),
    )
    found = propose_contradictions(corpus)
    assert len(found) == 1
    result = assess_gaps(corpus, contradictions=found)
    kinds = {p.gap_type for p in result.proposals}
    assert "contradictory_evidence" in kinds
    for forbidden in ("understudied_relationship", "replication_need", "theory_gap"):
        assert forbidden not in kinds, (
            f"اختلافُ نتيجتين وُلِّد منه {forbidden} تلقائيًّا")
    item = next(p for p in result.proposals
                if p.gap_type == "contradictory_evidence")
    assert item.contradiction_key is not None
    assert "ليس فجوةً بذاته" in item.known_limitations_ar
    assert item.strength == "weak_signal"


def test_negative_5_all_cross_sectional_is_concentration_not_proof():
    """**٥) كلّها مقطعية ← تركّزٌ في هذه المجموعة، لا برهانٌ على غياب الطولية.**"""
    from athera_api.services.synthesis import assess_gaps

    corpus = _corpus(*[
        _study(f"دراسة {i}", design="دراسة مقطعية", constructs="الرضا الوظيفي",
               context="السعودية")
        for i in range(5)
    ])
    result = assess_gaps(corpus)
    method = [p for p in result.proposals if p.gap_type == "method_gap"]
    assert len(method) == 1
    gap = method[0]
    assert "مقطعية" in gap.description_ar
    assert "في هذه المجموعة" in gap.known_limitations_ar
    assert "ليس دليلًا" in gap.known_limitations_ar
    assert gap.strength != "supported_candidate"
    assert "لم يُجرِ النظام بحثًا منهجيًّا" in gap.description_ar


# ═════════════════════ ٦. حدودُ الدعوى ═════════════════════

def _all_generated_text(result) -> str:
    parts: list[str] = []
    for proposal in result.proposals:
        parts += [proposal.description_ar, proposal.why_suggested_ar,
                  proposal.known_limitations_ar]
    parts += [item.reason_ar for item in result.not_assessed]
    return " ".join(parts)


def test_no_absolute_absence_claim_ever_leaves_this_layer():
    """**«لا توجد دراسات» دعوى عن العالم لم تُفحص.**

    والمسموح: «لم تظهر ضمن مجموعة المراجع الحالية»، ومعه العدد والفهارس.
    ويُستثنى موضعٌ واحد صريح: نصُّ الحدود يقتبس العبارة ليمنعها.
    """
    from athera_api.services.synthesis import assess_gaps, propose_contradictions
    from athera_api.services.synthesis.vocab import FORBIDDEN_ABSOLUTE_CLAIMS

    corpus = _corpus(*[
        _study(f"دراسة {i}", design="دراسة مقطعية", context="موظفون في مصر",
               constructs="الرضا الوظيفي", measures=f"مقياس {i}",
               findings="علاقة إيجابية دالة إحصائيًا", year=2001)
        for i in range(6)
    ], registries=("crossref",))
    result = assess_gaps(corpus, contradictions=propose_contradictions(corpus))
    assert result.proposals, "لم يُقترح شيء فلا شيء يُفحص"
    for proposal in result.proposals:
        for phrase in FORBIDDEN_ABSOLUTE_CLAIMS:
            assert phrase not in proposal.description_ar, (
                f"{proposal.gap_type}: دعوى مطلقة «{phrase}»")
            assert phrase not in proposal.why_suggested_ar, (
                f"{proposal.gap_type}: دعوى مطلقة «{phrase}»")


def test_every_gap_carries_its_bounds_with_it_not_on_another_page():
    from athera_api.services.synthesis import assess_gaps

    corpus = _corpus(*[
        _study(f"دراسة {i}", design="دراسة مقطعية", context="موظفون في مصر",
               constructs="الرضا") for i in range(5)
    ], registries=("crossref", "upload"), saved_only=7, excluded=2)
    for proposal in assess_gaps(corpus).proposals:
        assert proposal.sources_considered == 5
        assert proposal.search_scope["indexes_searched"] == ["crossref", "upload"]
        assert proposal.search_scope["search_was_systematic"] is False
        assert proposal.source_scope_distribution
        assert proposal.known_limitations_ar.strip()
        assert "مجموعة المراجع الحالية" in proposal.description_ar
        # والمحفوظ غير المفروز يُذكر: فجوةٌ فوق فرزٍ لم يكتمل ناقصة.
        assert "7 مرجعًا محفوظًا لم يُفرَز" in proposal.description_ar


def test_an_empty_corpus_produces_no_gap_at_all():
    """**فجوةٌ فوق صفر مراجع اختراع.**"""
    from athera_api.services.synthesis import assess_gaps

    result = assess_gaps(_corpus())
    assert result.proposals == ()
    assert result.not_assessed
    assert result.corpus_size == 0


def test_the_strength_ceiling_is_driven_by_what_was_actually_read():
    """مجموعةٌ كبيرةٌ لم يُقرأ منها شيء ليست أقوى من صغيرةٍ قُرئت."""
    from athera_api.services.synthesis.gaps import strength_ceiling

    unread = _corpus(*[_study(f"د{i}", scope="metadata_only") for i in range(20)])
    assert strength_ceiling(unread) == "weak_signal"

    abstracts = _corpus(*[_study(f"د{i}", constructs="الرضا") for i in range(6)])
    assert strength_ceiling(abstracts) == "emerging_pattern"

    read = _corpus(*[_study(f"د{i}", scope="full_text", constructs="الرضا")
                     for i in range(6)])
    assert strength_ceiling(read) == "supported_candidate"


def test_the_gap_names_are_the_nine_controlled_ones_and_no_free_text():
    from athera_api.models.synthesis import GAP_TYPES

    assert len(GAP_TYPES) == len(set(GAP_TYPES)) == 9
    for expected in ("context_gap", "population_gap", "method_gap", "theory_gap",
                     "measurement_gap", "temporal_gap", "contradictory_evidence",
                     "understudied_relationship", "replication_need"):
        assert expected in GAP_TYPES


def test_the_model_is_named_a_candidate_and_never_a_confirmed_gap():
    """الاسم عقدٌ مع القارئ: لا صفّ في هذه القاعدة يقول «فجوة مؤكَّدة»."""
    from athera_api.models import synthesis as model

    assert hasattr(model, "GapCandidate")
    assert not hasattr(model, "ConfirmedGap")
    assert model.GapCandidate.__tablename__ == "gap_candidates"
    # ولا جدولَ باسمٍ يدّعي التأكيد. (التعليق في الترحيل يذكر الاسم ليمنعه،
    # فيُفحص إنشاء الجدول لا ورودُ الكلمة — وحارسٌ يسقط على شرحٍ صادق يُعطَّل.)
    assert 'op.create_table(\n        "confirmed' not in _migration_text()
    assert "gap_candidates" in _migration_text()


# ═════════════════════ ٧. الفرص البحثية ═════════════════════

def test_only_an_approved_gap_may_become_an_opportunity():
    from athera_api.services.synthesis import gap_may_become_opportunity

    assert gap_may_become_opportunity("approved") is True
    for other in ("generated", "needs_review", "rejected", "unknown"):
        assert gap_may_become_opportunity(other) is False


def test_the_opportunity_card_answers_all_seven_questions():
    from athera_api.services.synthesis.gaps import GapProposal
    from athera_api.services.synthesis.opportunities import RelatedStudy, build_preview

    gap = GapProposal(
        gap_type="context_gap", description_ar="ما لوحظ",
        why_suggested_ar="لماذا قد يكون مهمًّا",
        known_limitations_ar="ما زال غير مؤكد",
        strength="weak_signal", sources_considered=5,
        search_scope={"indexes_searched": ["crossref"]},
        source_scope_distribution={"abstract_only": 5})
    preview = build_preview(
        gap_id=str(uuid.uuid4()), gap=gap,
        related=(RelatedStudy(source_id=str(uuid.uuid4()), title="دراسة",
                              role="supporting", evidence_scope="abstract_only"),))
    assert preview.what_we_noticed_ar == "ما لوحظ"
    assert preview.why_it_might_matter_ar
    assert preview.evidence_basis_ar
    assert preview.related_studies
    assert preview.still_uncertain_ar == "ما زال غير مؤكد"
    assert preview.gap_type_label_ar == "فجوة سياق"
    assert preview.next_step_ar
    # والخطوة التالية ليست «اكتب ورقة».
    assert "بحثٌ مستقلّ" in preview.next_step_ar


def test_the_preview_writes_nothing_and_the_card_needs_an_explicit_confirmation():
    """معاينةٌ تكتب صفًّا تجعل كل استطلاعٍ لفكرةٍ أثرًا دائمًا في البحث."""
    import inspect

    from athera_api.routers import synthesis as router
    from athera_api.services.synthesis import opportunities

    preview_src = inspect.getsource(opportunities.build_preview)
    assert "session" not in preview_src and "add(" not in preview_src

    created = inspect.getsource(router.create_opportunity)
    assert "if not payload.confirmed" in created
    assert "synthesis.confirmation_required" in created
    assert "gap_may_become_opportunity" in created


def test_uncertainties_are_mandatory_on_every_opportunity_card():
    """بطاقةٌ بلا عدم يقينٍ معلن تُقرأ خطةً مثبتة."""
    from pydantic import ValidationError

    from athera_api.schemas.synthesis import OpportunityCreateRequest

    base = dict(gap_candidate_id=uuid.uuid4(), confirmed=True,
                phenomenon_ar="ظاهرة", possible_contribution_ar="إسهام",
                evidence_basis_ar="أدلة", uncertainties_ar="ما زال غير مؤكد")
    assert OpportunityCreateRequest(**base).uncertainties_ar
    with pytest.raises(ValidationError):
        OpportunityCreateRequest(**{**base, "uncertainties_ar": ""})


def test_creating_a_project_shows_a_preview_and_says_what_it_will_not_do():
    from athera_api.services.synthesis import build_project_preview

    preview = build_project_preview(opportunity_id=str(uuid.uuid4()),
                                    title_ar="عنوان مبدئي", gap_type="method_gap")
    assert preview.requires_confirmation is True
    assert preview.will_create_ar and preview.will_not_create_ar and preview.unchanged_ar
    blob = " ".join(preview.will_not_create_ar + preview.unchanged_ar)
    assert "لن تُنقل مراجعك" in blob
    assert "لن تُدرَج" in blob


def test_no_line_in_the_synthesis_layer_ever_writes_a_source_use_state():
    """**ولا مرجعٌ يُقلَب إلى «مُدرَج» في الخفاء.**

    والإدراج أخطر قرارٍ في الفرز؛ ووقوعُه بأثرٍ جانبي لإنشاء فرصةٍ يجعل
    الطبقة تصنع دليلها بنفسها.
    """
    package = (REPO / "apps" / "api" / "athera_api" / "services" / "synthesis")
    files = list(package.glob("*.py"))
    files.append(REPO / "apps" / "api" / "athera_api" / "routers" / "synthesis.py")
    assert len(files) > 5
    for path in files:
        source = path.read_text(encoding="utf-8")
        writes = re.findall(r"\.use_state\s*=(?![=<>])", source)
        assert not writes, f"{path.name} يكتب حال الاستعمال"
        assert "ProjectSource(" not in source, f"{path.name} ينشئ ربطَ مرجعٍ ببحث"


def test_creating_a_project_copies_no_source_and_says_so_in_the_audit():
    import inspect

    from athera_api.routers import synthesis as router

    source = inspect.getsource(router.create_project_from_opportunity)
    assert "if not payload.confirmed" in source
    assert '"sources_copied": 0' in source
    assert "ProjectSource" not in source


# ═════════════════════ ٨. القرار والتوليد ═════════════════════

def test_regeneration_never_erases_a_decided_candidate():
    """**زرُّ «أعد التحليل» لا يُلغي مراجعة أسبوع بلا سؤال.**"""
    import inspect

    from athera_api.services.synthesis import store

    for fn in (store.replace_generated_themes,
               store.replace_generated_contradictions,
               store.replace_generated_gaps):
        source = inspect.getsource(fn)
        assert "decided_by.is_(None)" in source, (
            f"{fn.__name__} يحذف بلا شرط «لم يُحكم فيه»")


def test_every_store_read_is_bound_to_its_project_not_only_its_tenant():
    """**RLS لا تحمي بين بحثين في مستأجرٍ واحد.**"""
    import inspect

    from athera_api.services.synthesis import store

    for name in ("list_themes", "theme_of", "theme_supports", "list_contradictions",
                 "contradiction_sides", "list_gaps", "gap_of", "gap_sources",
                 "list_opportunities", "opportunity_of"):
        source = inspect.getsource(getattr(store, name))
        assert "tenant_id ==" in source, f"{name} بلا شرط المستأجر"
        assert "project_id ==" in source, f"{name} بلا شرط البحث"


def test_a_decision_is_attributed_to_its_author_for_a_rejection_too():
    from athera_api.services.synthesis.store import apply_decision

    class Row:
        status = "generated"
        decided_by = None
        decided_at = None

    row = Row()
    actor = uuid.uuid4()
    before = apply_decision(row, status="rejected", actor_id=actor)
    assert before["status"] == "generated"
    assert row.status == "rejected"
    assert row.decided_by == actor and row.decided_at is not None


def test_the_synthesis_error_codes_all_have_translations_in_both_locales():
    import inspect

    from athera_api.i18n.catalog import CATALOG, SUPPORTED_LOCALES
    from athera_api.routers import synthesis as router

    referenced = set(re.findall(
        r'(?:AtheraError|NotFound)\(\s*"(synthesis\.[a-z_]+)"',
        inspect.getsource(router)))
    assert referenced, "لم يُعثر على أي رمز خطأ لفحصه"
    for code in sorted(referenced):
        assert code in CATALOG, f"رمزٌ بلا ترجمة: {code}"
        for locale in SUPPORTED_LOCALES:
            assert CATALOG[code].get(locale, "").strip(), f"{code} ينقصه {locale}"


def test_the_layer_calls_no_model_provider():
    """**مخرَجٌ احتماليّ هنا لا يُراجَع ولا يُقارَن.**"""
    package = (REPO / "apps" / "api" / "athera_api" / "services" / "synthesis")
    for path in package.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("anthropic", "openai", "providers", "orchestrator",
                          "model_run"):
            assert forbidden not in source.lower(), (
                f"{path.name} يستدعي مزوّد نموذج: {forbidden}")


# ═════════════════════ ٩. الشاشات ═════════════════════

def _catalogs() -> tuple[dict, dict]:
    return (json.loads((WEB / "messages" / "ar.json").read_text(encoding="utf-8")),
            json.loads((WEB / "messages" / "en.json").read_text(encoding="utf-8")))


def test_the_four_researcher_facing_screens_exist():
    for page in PAGES:
        assert (SCREEN / page / "page.tsx").exists(), f"لا شاشة لـ{page}"


def test_each_screen_tells_loading_from_ready_from_empty_from_failed():
    """**طلبٌ فشل يُعرض «لا فجوات» يجعل الباحث يظنّ بحثه سليمًا.**"""
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        for suffix in ("loading", "failed", "empty"):
            marker = f'data-testid="{page}-{suffix}"'
            assert marker in text, f"حالُ عرضٍ غير مميَّزة: {marker}"
        assert 't("common.retry")' in text, f"{page}: فشلٌ بلا إعادة محاولة"
        assert 'role="alert"' in text, f"{page}: فشلٌ بلا إعلان"


def test_no_state_is_set_synchronously_inside_an_effect():
    """`react-hooks/set-state-in-effect` خطأٌ في CI لا تحذير."""
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        assert "void Promise.resolve().then" in text, f"{page}: حالةٌ داخل تأثير"


def test_every_repeated_control_names_its_target():
    """زرٌّ اسمه «اعتماد» بجانب «اعتماد» لا يُميَّز بالسمع إطلاقًا."""
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        assert "aria-label={`${" in text, f"{page}: زرٌّ متكرّر بلا اسمٍ يسمّي هدفه"


def test_the_screens_never_leak_internal_jargon_to_the_researcher():
    """`GapGraphNode` و`topic_cluster` أسماءٌ داخلية لا تُعرض لباحث."""
    from tests.tsscan import code_lines

    forbidden = ("GapGraphNode", "GapCandidate", "ThemeCandidate",
                 ">topic_cluster<", ">weak_signal<", ">generated<",
                 ">content_synthesis<")
    offenders: list[str] = []
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        for number, line in code_lines(text):
            for name in forbidden:
                if name in line:
                    offenders.append(f"{page}:{number} -> {name}")
    assert not offenders, "مفردةٌ داخلية تُعرض للباحث: " + "; ".join(offenders)


def test_every_message_key_these_screens_name_exists_in_both_locales():
    """**مفتاحٌ ناقص يُعرض مفتاحًا** — و`translator` لا يفشل، يعيد المسار."""
    ar, en = _catalogs()

    def has(catalog: dict, path: str) -> bool:
        node: object = catalog
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return isinstance(node, str)

    missing: list[str] = []
    for page in PAGES:
        text = (SCREEN / page / "page.tsx").read_text(encoding="utf-8")
        keys = set(re.findall(r't\(\s*"([a-zA-Z0-9_.]+)"\s*\)', text))
        for key in sorted(keys):
            for label, catalog in (("ar", ar), ("en", en)):
                if not has(catalog, key):
                    missing.append(f"{page}: {key} [{label}]")
    assert not missing, "مفاتيح تُنادى ولا وجود لها: " + "; ".join(missing)


def test_the_gaps_screen_shows_the_bounds_and_the_unassessed():
    """الحدُّ يُعرض مع الدعوى، وما تعذّر الحكم فيه يُعرض بقدر ما وُجد."""
    text = (SCREEN / "gaps" / "page.tsx").read_text(encoding="utf-8")
    for needle in ("sources_considered", "search_scope", "known_limitations_ar",
                   "not_assessed", "strength_meaning_ar"):
        assert needle in text, f"شاشة الفجوات لا تعرض {needle}"


def test_the_themes_screen_makes_the_cluster_versus_theme_difference_visible():
    text = (SCREEN / "themes" / "page.tsx").read_text(encoding="utf-8")
    assert "basis_label_ar" in text
    assert "basis_meaning_ar" in text
    assert "is_traceable" in text


def test_the_contradictions_screen_shows_both_sides_and_the_context():
    text = (SCREEN / "contradictions" / "page.tsx").read_text(encoding="utf-8")
    for needle in ("context_explanation_ar", "context_divergence_labels_ar",
                   "sides", "country_ar", "population_ar"):
        assert needle in text, f"شاشة التعارضات لا تعرض {needle}"


def test_the_opportunity_screen_requires_a_confirmation_before_a_project():
    text = (SCREEN / "research-opportunities" / "page.tsx").read_text(encoding="utf-8")
    assert "project-preview" in text or "projectPreview" in text
    assert "requires_confirmation" in text
    assert "will_not_create_ar" in text


def test_the_researcher_facing_names_are_the_four_arabic_ones():
    ar, en = _catalogs()
    assert ar["synthesis"]["themesTitle"] == "الموضوعات"
    assert ar["synthesis"]["contradictionsTitle"] == "التعارضات"
    assert ar["synthesis"]["gapsTitle"] == "الفجوات المحتملة"
    assert ar["synthesis"]["opportunitiesTitle"] == "الفرص البحثية"
    for key in ("themesTitle", "contradictionsTitle", "gapsTitle",
                "opportunitiesTitle"):
        assert en["synthesis"][key].strip()


def test_every_synthesis_vocabulary_has_a_researcher_facing_name_in_both_locales():
    from athera_api.models.synthesis import (
        CONFLICT_KINDS,
        GAP_STRENGTHS,
        GAP_TYPES,
        SYNTHESIS_STATUSES,
        THEME_BASES,
    )

    ar, en = _catalogs()
    expected = (
        [f"gapType_{key}" for key in GAP_TYPES]
        + [f"strength_{key}" for key in GAP_STRENGTHS]
        + [f"status_{key}" for key in SYNTHESIS_STATUSES]
        + [f"basis_{key}" for key in THEME_BASES]
        + [f"conflict_{key}" for key in CONFLICT_KINDS]
    )
    for key in expected:
        assert ar["synthesis"].get(key, "").strip(), f"لا اسم عربي لـ{key}"
        assert en["synthesis"].get(key, "").strip(), f"no English name for {key}"


def test_the_gaps_screen_never_promises_certainty_in_its_own_words():
    """نصُّ الشاشة نفسه لا يقول «فجوة مؤكَّدة» ولا «لا توجد دراسات»."""
    ar, _en = _catalogs()
    blob = json.dumps(ar["synthesis"], ensure_ascii=False)
    for phrase in ("فجوة مؤكدة", "فجوة مؤكَّدة", "لا توجد دراسات", "أول دراسة"):
        assert phrase not in blob, f"الشاشة تَعِد بيقين: «{phrase}»"


# ════════════════════ ١٠. اختبارات تمسّ القاعدة (CI) ════════════════════

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


async def _seed_theme(tid, uid, project_id, source_id, *, label="موضوع"):
    from athera_api.db import tenant_session
    from athera_api.models.synthesis import ThemeCandidate, ThemeCandidateSupport

    async with tenant_session(tid, uid) as session:
        theme = ThemeCandidate(
            tenant_id=tid, project_id=project_id, label_ar=label,
            basis="topic_cluster", source_scope_summary={"metadata_only": 1},
            generation_method="deterministic", generated_at=_now(),
            status="generated")
        session.add(theme)
        await session.flush()
        session.add(ThemeCandidateSupport(
            tenant_id=tid, project_id=project_id, theme_id=theme.id,
            source_id=source_id, role="supporting", basis_field_key="reference",
            evidence_scope="metadata_only"))
        await session.flush()
        return theme.id


async def _seed_gap(tid, uid, project_id, *, status="generated", decided_by=None):
    from athera_api.db import tenant_session
    from athera_api.models.synthesis import GapCandidate

    async with tenant_session(tid, uid) as session:
        gap = GapCandidate(
            tenant_id=tid, project_id=project_id, gap_type="context_gap",
            description_ar="لم يظهر سياقٌ ضمن مجموعة المراجع الحالية",
            why_suggested_ar="قُرئ عمود السياق",
            sources_considered=3, search_scope={"indexes_searched": ["crossref"]},
            source_scope_distribution={"abstract_only": 3},
            known_limitations_ar="ملاحظةٌ على قائمةٍ لا مسحٌ للحقل",
            strength="weak_signal", generation_method="deterministic",
            generated_at=_now(), status=status, decided_by=decided_by,
            decided_at=_now() if decided_by else None)
        session.add(gap)
        await session.flush()
        return gap.id


@requires_db
@pytest.mark.asyncio
async def test_a_tenant_never_reads_another_tenants_synthesis(two_tenants):
    """**العزل بين المستأجرين مفروضٌ من القاعدة** — لا من تصفيةٍ في الخدمة."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import (
        GapCandidate,
        ThemeCandidate,
        ThemeCandidateSupport,
    )

    a, b = two_tenants["a"], two_tenants["b"]
    project = await _seed_project(a["tenant_id"], "بحث المستأجر أ")
    source = await _seed_source(a["tenant_id"], "دراسة أ")
    theme_id = await _seed_theme(a["tenant_id"], a["user_id"], project, source)
    gap_id = await _seed_gap(a["tenant_id"], a["user_id"], project)

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        for model, row_id in ((ThemeCandidate, theme_id), (GapCandidate, gap_id)):
            found = (await session.execute(
                select(model).where(model.id == row_id))).scalar_one_or_none()
            assert found is None, f"{model.__tablename__} تسرّب بين مستأجرين"
        leaked = (await session.execute(
            select(ThemeCandidateSupport).where(
                ThemeCandidateSupport.theme_id == theme_id))).scalars().all()
        assert not leaked


@requires_db
@pytest.mark.asyncio
async def test_one_tenant_two_projects_never_see_each_others_synthesis(two_tenants):
    """**العطب الذي وقع في هذا المنتج من قبل.**

    RLS تمرّ صفّ المستأجر نفسه، فالحماية بين بحثين مسؤولية الاستعلام —
    وكلُّ قراءةٍ في `store` تشترط `project_id`. ويُثبت ذلك على الأربعة.
    """
    from athera_api.db import tenant_session
    from athera_api.services.synthesis import store

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    first = await _seed_project(tid, "بحث أول")
    second = await _seed_project(tid, "بحث ثانٍ")
    source = await _seed_source(tid, "دراسة مشتركة")

    theme_id = await _seed_theme(tid, uid, first, source, label="موضوع الأول")
    gap_id = await _seed_gap(tid, uid, first)

    async with tenant_session(tid, uid) as session:
        # يُقرأ من بحثه.
        assert await store.theme_of(session, tenant_id=tid, project_id=first,
                                    theme_id=theme_id) is not None
        assert await store.gap_of(session, tenant_id=tid, project_id=first,
                                  gap_id=gap_id) is not None
        # ولا يُقرأ من بحثٍ آخر للمستأجر نفسه.
        assert await store.theme_of(session, tenant_id=tid, project_id=second,
                                    theme_id=theme_id) is None
        assert await store.gap_of(session, tenant_id=tid, project_id=second,
                                  gap_id=gap_id) is None
        assert await store.list_themes(session, tenant_id=tid,
                                       project_id=second) == []
        assert await store.list_gaps(session, tenant_id=tid, project_id=second) == []
        assert await store.list_contradictions(session, tenant_id=tid,
                                               project_id=second) == []
        assert await store.list_opportunities(session, tenant_id=tid,
                                              project_id=second) == []
        assert await store.theme_supports(session, tenant_id=tid, project_id=second,
                                          theme_ids=[theme_id]) == []


@requires_db
@pytest.mark.asyncio
async def test_a_theme_cannot_borrow_a_matrix_cell_from_another_project(two_tenants):
    """**الحارس بنيويّ لا مسلكيّ**: المفتاح المركّب يرفض الاستعارة."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectSource
    from athera_api.models.screening import LiteratureMatrixCell
    from athera_api.models.synthesis import ThemeCandidate, ThemeCandidateSupport

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    first = await _seed_project(tid, "بحث الخلية")
    second = await _seed_project(tid, "بحث المستعير")
    source = await _seed_source(tid, "دراسة")

    async with tenant_session(tid, uid) as session:
        session.add(ProjectSource(
            tenant_id=tid, project_id=first, source_id=source,
            use_state="included", added_by=uid, decided_by=uid, decided_at=_now()))
        cell = LiteratureMatrixCell(
            tenant_id=tid, project_id=first, source_id=source,
            field_key="constructs", value_ar="الرضا الوظيفي", cell_state="known",
            source_scope="abstract_only", extraction_method="researcher",
            updated_by=uid)
        session.add(cell)
        await session.flush()
        cell_id = cell.id

    async with tenant_session(tid, uid) as session:
        theme = ThemeCandidate(
            tenant_id=tid, project_id=second, label_ar="موضوع مستعير",
            basis="content_synthesis", source_scope_summary={},
            generation_method="deterministic", generated_at=_now(),
            status="generated")
        session.add(theme)
        await session.flush()
        theme_id = theme.id

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ThemeCandidateSupport(
                tenant_id=tid, project_id=second, theme_id=theme_id,
                source_id=source, role="supporting", basis_field_key="constructs",
                matrix_cell_id=cell_id, evidence_scope="abstract_only"))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_an_opportunity_over_an_unapproved_gap(two_tenants):
    """ثلاثةُ حرّاس على الشيء نفسه — وهذا أعمقُها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import ResearchOpportunity

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث الفرصة")
    gap_id = await _seed_gap(tid, uid, project, status="generated")

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ResearchOpportunity(
                tenant_id=tid, project_id=project, gap_candidate_id=gap_id,
                gap_status="approved", phenomenon_ar="ظاهرة",
                possible_contribution_ar="إسهام", evidence_basis_ar="أدلة",
                uncertainties_ar="غير مؤكد", created_by=uid))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_an_approved_gap_cannot_be_un_approved_under_a_live_opportunity(
        two_tenants):
    """`ON UPDATE RESTRICT` — ولا تبقى فرصةٌ معلّقةً في الهواء."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import GapCandidate, ResearchOpportunity
    from sqlalchemy import select

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث الاعتماد")
    gap_id = await _seed_gap(tid, uid, project, status="approved", decided_by=uid)

    async with tenant_session(tid, uid) as session:
        session.add(ResearchOpportunity(
            tenant_id=tid, project_id=project, gap_candidate_id=gap_id,
            gap_status="approved", phenomenon_ar="ظاهرة",
            possible_contribution_ar="إسهام", evidence_basis_ar="أدلة",
            uncertainties_ar="غير مؤكد", created_by=uid))
        await session.flush()

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            row = (await session.execute(
                select(GapCandidate).where(GapCandidate.id == gap_id)
            )).scalar_one()
            row.status = "rejected"
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_decided_candidate_must_name_its_author(two_tenants):
    """قرارٌ بلا صاحبٍ ووقت لا يكون — رفضًا كما اعتمادًا."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import GapCandidate

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث القرار")

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(GapCandidate(
                tenant_id=tid, project_id=project, gap_type="context_gap",
                description_ar="وصف", why_suggested_ar="سبب",
                sources_considered=1,
                search_scope={"indexes_searched": ["crossref"]},
                source_scope_distribution={}, known_limitations_ar="حدود",
                strength="weak_signal", generation_method="deterministic",
                generated_at=_now(), status="approved"))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_gap_without_its_bounds_is_refused_by_the_database(two_tenants):
    """**فجوةٌ بلا حدودٍ معلنة دعوى** — والقاعدة ترفضها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import GapCandidate

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث الحدود")

    def _gap(**overrides):
        base = dict(
            tenant_id=tid, project_id=project, gap_type="context_gap",
            description_ar="وصف", why_suggested_ar="سبب", sources_considered=3,
            search_scope={"indexes_searched": ["crossref"]},
            source_scope_distribution={}, known_limitations_ar="حدود",
            strength="weak_signal", generation_method="deterministic",
            generated_at=_now(), status="generated")
        base.update(overrides)
        return GapCandidate(**base)

    for broken in ({"sources_considered": 0},
                   {"search_scope": {"note": "بلا فهارس"}},
                   {"known_limitations_ar": "   "}):
        with pytest.raises(IntegrityError):
            async with tenant_session(tid, uid) as session:
                session.add(_gap(**broken))
                await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_contradiction_side_that_states_nothing_is_refused(two_tenants):
    """صمتُ ورقةٍ ليس نصفَ تعارض."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import ContradictionCandidate, ContradictionSide

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث الصمت")
    source = await _seed_source(tid, "دراسة صامتة")

    async with tenant_session(tid, uid) as session:
        parent = ContradictionCandidate(
            tenant_id=tid, project_id=project, construct_a_ar="الرضا",
            relationship_ar="علاقة", conflict_kind="direction",
            context_divergence=[], generation_method="deterministic",
            generated_at=_now(), status="generated")
        session.add(parent)
        await session.flush()
        parent_id = parent.id

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ContradictionSide(
                tenant_id=tid, project_id=project, contradiction_id=parent_id,
                side="a", source_id=source, result_ar="نتيجة",
                direction="not_stated", significance="not_stated",
                evidence_scope="abstract_only"))
            await session.flush()


@requires_db
@pytest.mark.asyncio
async def test_a_content_theme_support_must_point_at_a_cell(two_tenants):
    """سندُ محتوًى بلا خليةٍ يشير إليها دعوى — والقيد يرفضها."""
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.synthesis import ThemeCandidate, ThemeCandidateSupport

    a = two_tenants["a"]
    tid, uid = a["tenant_id"], a["user_id"]
    project = await _seed_project(tid, "بحث السند")
    source = await _seed_source(tid, "دراسة")

    async with tenant_session(tid, uid) as session:
        theme = ThemeCandidate(
            tenant_id=tid, project_id=project, label_ar="موضوع",
            basis="content_synthesis", source_scope_summary={},
            generation_method="deterministic", generated_at=_now(),
            status="generated")
        session.add(theme)
        await session.flush()
        theme_id = theme.id

    with pytest.raises(IntegrityError):
        async with tenant_session(tid, uid) as session:
            session.add(ThemeCandidateSupport(
                tenant_id=tid, project_id=project, theme_id=theme_id,
                source_id=source, role="supporting", basis_field_key="constructs",
                matrix_cell_id=None, evidence_scope="abstract_only"))
            await session.flush()
