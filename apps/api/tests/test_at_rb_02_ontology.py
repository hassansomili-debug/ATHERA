"""AT-RB-02 — الأنطولوجيا: مفرداتها مفردات المنظومة، وروابطها بطرفين معلومين.

نصف هذا الملف حراسةٌ ضد الانحراف: كل اسم حالةٍ يُقارَن **بمصدره في الترحيل
أو في مفردات الخدمات**، لا بما نتذكّره. واسمُ حالةٍ خاطئ لا يُسقط اختبارًا
ولا يرفع استثناءً — يمرّ صامتًا ويجعل قاعدةً تبدو عاملة ولا تُطلق أبدًا.
"""
import pathlib
import re

import pytest
from pydantic import ValidationError

from athera_api.research_brain import ontology
from athera_api.research_brain.values import ValueState, known, missing
from athera_api.services.analysis.vocab import TEST_KINDS
from athera_api.services.golden_thread.vocab import SAMPLING_STRATEGIES, STUDY_TYPES

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "infra" / "db" / "migrations" / "versions"
API_SRC = REPO_ROOT / "apps" / "api" / "athera_api"


def _literals(text: str, marker: str) -> set[str]:
    """يلتقط القيم المسرودة بعد علامةٍ في نصّ ترحيل — مصدر الحقيقة لا الذاكرة."""
    start = text.index(marker)
    chunk = text[start:text.index(")", start)]
    return set(re.findall(r"[\"']([a-z_]+)[\"']", chunk))


# ── الكيانات والعلاقات ────────────────────────────────────────────────────

def test_the_twenty_two_entities_are_all_present():
    """القائمة مكتوبة يدويًّا عمدًا حتى يفشل الاختبار إذا سقط كيانٌ بصمت."""
    expected = {
        "researcher", "project", "domain", "phenomenon", "context", "construct",
        "theory", "research_question", "hypothesis", "design", "population",
        "sample", "measure", "dataset", "analysis", "finding", "limitation",
        "gap", "source", "claim", "evidence", "recommendation",
    }
    assert {kind.value for kind in ontology.EntityKind} == expected
    assert len(expected) == 22


def test_the_nine_relationships_are_all_present():
    expected = {
        "PROJECT_HAS_QUESTION", "QUESTION_USES_CONSTRUCT",
        "CONSTRUCT_OPERATIONALIZED_BY_MEASURE", "CLAIM_SUPPORTED_BY_EVIDENCE",
        "FINDING_DERIVED_FROM_ANALYSIS", "ANALYSIS_USES_DATASET",
        "RECOMMENDATION_DERIVED_FROM_FINDING", "PROJECT_USES_THEORY",
        "SOURCE_SUPPORTS_CLAIM",
    }
    assert {kind.value for kind in ontology.RelationKind} == expected
    assert set(ontology.RELATION_ENDPOINTS) == set(ontology.RelationKind)


def test_every_entity_class_declares_its_kind():
    """صنفٌ بلا نوع يسقط في `Entity.kind` باستثناء — لا يمرّ بنوعٍ افتراضي.

    و`source_type` يُمرَّر لأن `Evidence` تشترطه: دليلٌ لا يُعرف من أين جاء
    لا يُبنى أصلًا، وهو الشرط عينه الذي تحرسه القاعدة العاشرة.
    """
    declared = set()
    for name in dir(ontology):
        value = getattr(ontology, name)
        if (isinstance(value, type) and issubclass(value, ontology.Entity)
                and value is not ontology.Entity):
            extra = {"source_type": "upload"} if value is ontology.Evidence else {}
            declared.add(value(id="i", label_ar="ت", **extra).kind)
    assert declared == set(ontology.EntityKind)


# ── الروابط تُفحص عند الإنشاء ─────────────────────────────────────────────

def test_a_reversed_relationship_is_refused():
    """رابطٌ مقلوب يُكتب مرةً ويُقرأ ألف مرة — فيُمنع عند الكتابة."""
    with pytest.raises(ValidationError):
        ontology.ResearchGraph(
            entities=[ontology.Claim(id="c", label_ar="ادّعاء"),
                      ontology.Evidence(id="e", label_ar="دليل", source_type="upload")],
            relationships=[ontology.Relationship(
                kind=ontology.RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE,
                source_id="e", target_id="c")],
        )


def test_a_claim_cannot_support_itself():
    """الدائرة التي يمنعها `no_self_verification` ممنوعةٌ بنيويًّا هنا."""
    with pytest.raises(ValidationError):
        ontology.ResearchGraph(
            entities=[ontology.Claim(id="c", label_ar="ادّعاء")],
            relationships=[ontology.Relationship(
                kind=ontology.RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE,
                source_id="c", target_id="c")],
        )


def test_a_dangling_endpoint_is_refused():
    """معرّفٌ معلّق: العطب نفسه الذي أزاله `ManuscriptSectionClaim` بالمفتاح الأجنبي."""
    with pytest.raises(ValidationError) as err:
        ontology.ResearchGraph(
            entities=[ontology.Claim(id="c", label_ar="ادّعاء")],
            relationships=[ontology.Relationship(
                kind=ontology.RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE,
                source_id="c", target_id="ghost")],
        )
    assert "ghost" in str(err.value)


def test_duplicate_entity_ids_are_refused():
    with pytest.raises(ValidationError):
        ontology.ResearchGraph(entities=[
            ontology.Claim(id="c", label_ar="أ"), ontology.Claim(id="c", label_ar="ب")])


# ── المفردات مقروءة من مصادرها ────────────────────────────────────────────

def test_element_mapping_uses_only_real_thread_element_types():
    """كل نوعٍ نربط به موجودٌ في `ELEMENT_TYPES` بترحيل 0009 — لا نوع مخترع."""
    text = (MIGRATIONS / "0009_golden_thread.py").read_text(encoding="utf-8")
    allowed = _literals(text, "ELEMENT_TYPES = (")
    assert "hypothesis" in allowed, "هذا الاختبار يقرأ القائمة الخطأ"
    assert set(ontology.ELEMENT_TYPE_BY_ENTITY.values()) <= allowed


def test_link_targets_of_the_mapping_are_entity_kinds():
    assert set(ontology.ELEMENT_TYPE_BY_ENTITY) <= set(ontology.EntityKind)


def test_source_use_states_match_migration_0020():
    """`SOURCE_USE_STATES` مقروءة من الترحيل نفسه لا من الذاكرة."""
    text = (MIGRATIONS / "0020_project_workspace.py").read_text(encoding="utf-8")
    states = _literals(text, "SOURCE_USE_STATES = (")
    assert states == {"included", "saved_only", "excluded"}
    for state in states:
        assert ontology.Source(id="s", label_ar="م", use_state=state).use_state == state
    with pytest.raises(ValidationError):
        ontology.Source(id="s", label_ar="م", use_state="approved")


def test_saved_only_is_the_default_use_state():
    """الافتراضي محفوظٌ لا مُدرَج — والإدراج قرار الباحث لا حالة ابتداء."""
    assert ontology.Source(id="s", label_ar="م").use_state == "saved_only"


def test_evidence_source_types_include_model_output_and_the_four_promotion_paths():
    text = (MIGRATIONS / "0005_verified_memory.py").read_text(encoding="utf-8")
    assert "ck_memory_source_path" in text
    for source_type in ("external_source", "upload", "analysis_run", "user_statement",
                        "model_output"):
        ontology.Evidence(id="e", label_ar="د", source_type=source_type)
    with pytest.raises(ValidationError):
        ontology.Evidence(id="e", label_ar="د", source_type="guess")


def test_study_types_and_sampling_come_from_the_existing_vocabulary():
    for study_type in STUDY_TYPES:
        ontology.Design(id="d", label_ar="ت", study_type=study_type)
    with pytest.raises(ValidationError):
        ontology.Design(id="d", label_ar="ت", study_type="cross_sectional")

    for strategy in SAMPLING_STRATEGIES:
        ontology.Sample(id="s", label_ar="ع", sampling_strategy=strategy)
    with pytest.raises(ValidationError):
        ontology.Sample(id="s", label_ar="ع", sampling_strategy="random-ish")


def test_cross_sectional_is_a_temporal_frame_not_a_design_family():
    """«مقطعي» بُعدٌ زمني: ارتباطيةٌ قد تكون مقطعية وقد تكون طولية."""
    assert "cross_sectional" not in ontology.DESIGN_FAMILIES
    design = ontology.Design(id="d", label_ar="ت", design_family="correlational",
                             temporal_frame="cross_sectional")
    assert design.temporal_frame == "cross_sectional"
    assert ontology.Design(id="d", label_ar="ت").temporal_frame == "unknown"


def test_design_families_cover_every_value_the_repo_writes_today():
    """`survey` و`descriptive_survey` يكتبهما كودٌ يعمل — فرفضهما عطبٌ لا حراسة."""
    hints = (API_SRC / "services" / "planning" / "thread.py").read_text(encoding="utf-8")
    written = set(re.findall(r':\s*"([a-z_]+)",?\s*$', hints, re.M))
    for value in {"survey", "quasi_experimental", "experimental", "descriptive",
                  "correlational"} & written:
        assert value in ontology.DESIGN_FAMILIES, value


def test_test_kinds_are_the_analysis_vocabulary():
    for kind in TEST_KINDS:
        ontology.Analysis(id="a", label_ar="ت", test_kind=kind)
    with pytest.raises(ValidationError):
        ontology.Analysis(id="a", label_ar="ت", test_kind="mann_whitney")


# ── القيم ─────────────────────────────────────────────────────────────────

def test_a_number_without_a_source_cannot_be_built():
    """الاختلاق خطأ تحقّقٍ عند الإنشاء، لا مخالفةً تُكتشف بعد الكتابة."""
    with pytest.raises(ValidationError):
        ontology.Sample(id="s", label_ar="ع",
                        size={"state": "known", "value": 384})
    with pytest.raises(ValidationError):
        ontology.Sample(id="s", label_ar="ع",
                        size={"state": "missing", "value": 384})


def test_missing_prints_as_missing_and_never_as_zero():
    sample = ontology.Sample(id="s", label_ar="ع")
    assert sample.size.state is ValueState.MISSING
    assert sample.size.value is None
    assert sample.size.label() == ("غير مسجَّلة", "MISSING")
    assert not sample.size.is_known


def test_known_carries_its_value_and_its_source():
    sample = ontology.Sample(id="s", label_ar="ع", size=known(384, source_ref="RUN-7"))
    assert sample.size.is_known and sample.size.value == 384
    assert sample.size.source_ref == "RUN-7"
    assert sample.size.label()[1] == "384"


def test_missing_and_unknown_are_two_different_answers():
    assert missing().state is not ValueState.UNKNOWN
    assert missing().label() != ontology.Sample(
        id="s", label_ar="ع", size={"state": "unknown"}).size.label()


def test_generalization_reads_the_sampling_table_not_a_guess():
    assert ontology.Sample(id="s", label_ar="ع",
                           sampling_strategy="convenience").supports_generalization is False
    assert ontology.Sample(id="s", label_ar="ع",
                           sampling_strategy="stratified_random").supports_generalization is True
    # أسلوبٌ غير مسجَّل لا يُعدّ ممثِّلًا — الغياب لا يمنح تعميمًا.
    assert ontology.Sample(id="s", label_ar="ع").supports_generalization is False
