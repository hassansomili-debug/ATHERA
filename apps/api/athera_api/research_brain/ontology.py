"""أنطولوجيا البحث | Research ontology (عقود، لا تخزين).

**عقودٌ لا جداول، ولا قاعدة رسوم.** كل ما هنا يمثَّل في PostgreSQL بجداول
وروابط عادية — والخيط الذهبي يفعل ذلك اليوم فعلًا في `thread_elements`
و`thread_links`. وإدخال قاعدة رسوم لأجل تسعة أنواع روابط يضيف قاعدة بيانات
ثانية تُشغَّل وتُنسَخ احتياطيًّا وتُؤمَّن، مقابل استعلامٍ لا يُكتب اليوم.

## المفردات ليست جديدة

`ELEMENT_TYPE_BY_ENTITY` أدناه يربط كل كيان هنا بنوع العنصر المقابل في
الخيط الذهبي القائم. وهذا الربط ليس زينة: منظومةٌ فيها مفردتان للشيء نفسه
تكتب بإحداهما وتقرأ بالأخرى، فتصير الحالة صحيحةً في نصف الشيفرة وخاطئةً في
نصفها الآخر — وهو أكثر عطبٍ تكرارًا في هذا المستودع. فما له اسمٌ في
`services/golden_thread/vocab.py` يُستورَد منه، ولا يُعاد تعريفه.

## الروابط لها طرفان معلومان

`RELATION_ENDPOINTS` يثبّت نوع الطرفين لكل رابط. فرابطُ
`CLAIM_SUPPORTED_BY_EVIDENCE` من ادّعاءٍ إلى دليل، ولا يمكن أن يكون من
ادّعاءٍ إلى ادّعاء. ولولا هذا التثبيت لصار الرسم قابلًا لأن يقول إن ادّعاءً
يسند نفسه — وهي بالضبط الدائرة التي يمنعها حاجز `no_self_verification`.
"""
from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..services.analysis.vocab import TEST_KINDS
from ..services.golden_thread.vocab import SAMPLING_STRATEGIES, STUDY_TYPES
from .values import Quantity, missing


class EntityKind(str, Enum):
    """الكيانات الاثنان والعشرون."""

    RESEARCHER = "researcher"
    PROJECT = "project"
    DOMAIN = "domain"
    PHENOMENON = "phenomenon"
    CONTEXT = "context"
    CONSTRUCT = "construct"
    THEORY = "theory"
    RESEARCH_QUESTION = "research_question"
    HYPOTHESIS = "hypothesis"
    DESIGN = "design"
    POPULATION = "population"
    SAMPLE = "sample"
    MEASURE = "measure"
    DATASET = "dataset"
    ANALYSIS = "analysis"
    FINDING = "finding"
    LIMITATION = "limitation"
    GAP = "gap"
    SOURCE = "source"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    RECOMMENDATION = "recommendation"


class RelationKind(str, Enum):
    """العلاقات التسع."""

    PROJECT_HAS_QUESTION = "PROJECT_HAS_QUESTION"
    QUESTION_USES_CONSTRUCT = "QUESTION_USES_CONSTRUCT"
    CONSTRUCT_OPERATIONALIZED_BY_MEASURE = "CONSTRUCT_OPERATIONALIZED_BY_MEASURE"
    CLAIM_SUPPORTED_BY_EVIDENCE = "CLAIM_SUPPORTED_BY_EVIDENCE"
    FINDING_DERIVED_FROM_ANALYSIS = "FINDING_DERIVED_FROM_ANALYSIS"
    ANALYSIS_USES_DATASET = "ANALYSIS_USES_DATASET"
    RECOMMENDATION_DERIVED_FROM_FINDING = "RECOMMENDATION_DERIVED_FROM_FINDING"
    PROJECT_USES_THEORY = "PROJECT_USES_THEORY"
    SOURCE_SUPPORTS_CLAIM = "SOURCE_SUPPORTS_CLAIM"


RELATION_ENDPOINTS: Final[dict[RelationKind, tuple[EntityKind, EntityKind]]] = {
    RelationKind.PROJECT_HAS_QUESTION: (EntityKind.PROJECT, EntityKind.RESEARCH_QUESTION),
    RelationKind.QUESTION_USES_CONSTRUCT: (EntityKind.RESEARCH_QUESTION, EntityKind.CONSTRUCT),
    RelationKind.CONSTRUCT_OPERATIONALIZED_BY_MEASURE: (EntityKind.CONSTRUCT, EntityKind.MEASURE),
    RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE: (EntityKind.CLAIM, EntityKind.EVIDENCE),
    RelationKind.FINDING_DERIVED_FROM_ANALYSIS: (EntityKind.FINDING, EntityKind.ANALYSIS),
    RelationKind.ANALYSIS_USES_DATASET: (EntityKind.ANALYSIS, EntityKind.DATASET),
    RelationKind.RECOMMENDATION_DERIVED_FROM_FINDING: (
        EntityKind.RECOMMENDATION, EntityKind.FINDING),
    RelationKind.PROJECT_USES_THEORY: (EntityKind.PROJECT, EntityKind.THEORY),
    RelationKind.SOURCE_SUPPORTS_CLAIM: (EntityKind.SOURCE, EntityKind.CLAIM),
}

# الكيان هنا ← نوع العنصر في الخيط الذهبي القائم (§15.1).
#
# ما لا مقابل له لا يُدرَج بالقوّة: `researcher` و`project` و`domain`
# و`dataset` و`source` و`claim` و`evidence` كيانات لها جداولها الخاصة
# (`researcher_profiles`، `research_projects`، `datasets`، `sources`،
# `claims`) ولا تسكن `thread_elements`. وحشرُها في نوعٍ قريبٍ منها يجعل
# فحوص الاتساق التسعة تعدّ ما ليس عنصرًا في الخيط.
ELEMENT_TYPE_BY_ENTITY: Final[dict[EntityKind, str]] = {
    EntityKind.PHENOMENON: "phenomenon",
    EntityKind.GAP: "gap",
    EntityKind.RESEARCH_QUESTION: "question",
    EntityKind.THEORY: "theory",
    EntityKind.CONSTRUCT: "construct",
    EntityKind.MEASURE: "instrument",
    EntityKind.DESIGN: "method",
    EntityKind.ANALYSIS: "analysis",
    EntityKind.FINDING: "result",
    EntityKind.RECOMMENDATION: "recommendation",
    EntityKind.HYPOTHESIS: "hypothesis",
}


class Entity(BaseModel):
    """أصل كل كيان: معرّفٌ ونوعٌ وتسميةٌ عربية.

    `label_ar` إلزامية و`label_en` اختيارية — لا العكس. المنصّة عربية أولًا،
    وعقدٌ يجعل الإنجليزية هي الإلزامية يجبر كل مسارٍ عربيّ على ترجمةٍ آليّة
    ليمرّ التحقق.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    label_ar: str = Field(min_length=1)
    label_en: str | None = None

    @property
    def kind(self) -> EntityKind:  # pragma: no cover - يُلغى في كل مشتق
        raise NotImplementedError


def _kind(value: EntityKind):
    """يثبّت نوع الكيان في الصنف نفسه، فلا يُمرَّر حقلًا يمكن أن يخالف الصنف."""
    return property(lambda self: value)


class Researcher(Entity):
    orcid: str | None = None
    kind = _kind(EntityKind.RESEARCHER)


class Domain(Entity):
    kind = _kind(EntityKind.DOMAIN)


class Project(Entity):
    domain_id: str | None = None
    kind = _kind(EntityKind.PROJECT)


class Phenomenon(Entity):
    detail_ar: str | None = None
    kind = _kind(EntityKind.PHENOMENON)


class Context(Entity):
    """السياق: أين وقعت الدراسة ومتى ولمن — وهو حدّ التعميم لا زينة."""

    setting_ar: str | None = None
    kind = _kind(EntityKind.CONTEXT)


class Construct(Entity):
    definition_ar: str | None = None
    # تعريفٌ إجرائي مسجَّل — الفحص الثالث في §15.2 يقرأه.
    has_operational_definition: bool = False
    kind = _kind(EntityKind.CONSTRUCT)


class Theory(Entity):
    source_id: str | None = None
    kind = _kind(EntityKind.THEORY)


class ResearchQuestion(Entity):
    kind = _kind(EntityKind.RESEARCH_QUESTION)


class Hypothesis(Entity):
    directional: bool = False
    kind = _kind(EntityKind.HYPOTHESIS)


# عائلات التصميم — **اتحادُ ما هو مستعمَل فعلًا في المستودع**، لا قائمةٌ
# اختيرت هنا.
#
# وعمود `methods.design_family` **بلا قيد في القاعدة**، فتفرّقت المفردة على
# أربعة مواضع متداخلة: تعليقُ العمود نفسه، وجدولُ الدلائل في
# `services/planning/thread.py` (ويكتب `survey`)، و`_DESIGNS` في
# `services/publishing/consistency.py` (وفيه `descriptive_survey`
# و`qualitative`)، و`_METHOD_TERMS` في `drafting/checks.py`. وهذا عيبٌ
# قائم يُسجَّل هنا ولا يُصلَح الليلة: توحيدُه يمسّ عمودًا في الإنتاج، وهذا
# الأساس لا يمسّ الإنتاج.
#
# والاتحاد أصدق من الاختيار: قائمةٌ تسقط `survey` ترفض قيمةً يكتبها كودٌ
# يعمل اليوم، فيصير الرفض عطبًا لا حراسة.
DESIGN_FAMILIES: Final[tuple[str, ...]] = (
    # تعليق عمود `methods.design_family` في `models/golden_thread.py`
    "correlational", "descriptive", "experimental", "quasi_experimental",
    "case_study", "ethnographic",
    # يكتبها `services/planning/thread.py` من دلائل النص
    "survey",
    # يقارن بها `services/publishing/consistency.py` نصّ المخطوطة
    "descriptive_survey", "qualitative",
)


class Design(Entity):
    """التصميم المنهجي.

    `study_type` من `STUDY_TYPES` القائمة، و`design_family` من الاتحاد
    أعلاه — ولا قيمة تُخترع هنا.

    `temporal_frame` **حقلٌ جديد لا وجود له في القاعدة اليوم**، ويجب أن
    يُقرأ كذلك. أُفرد لأن «مقطعي» ليس عائلةَ تصميم: دراسةٌ ارتباطية قد تكون
    مقطعية وقد تكون طولية، والخلط يجعل حقلًا واحدًا يحمل بُعدين. ومن ضمّه
    إلى `design_family` أضاف قيمةً عاشرة إلى مفردةٍ متفرّقة أصلًا — زيادةُ
    الفوضى لا إصلاحها.
    """

    study_type: str | None = None
    design_family: str | None = None
    temporal_frame: str = Field(default="unknown",
                                pattern="^(cross_sectional|longitudinal|unknown)$")
    kind = _kind(EntityKind.DESIGN)

    @model_validator(mode="after")
    def _study_type_from_the_existing_vocabulary(self) -> Design:
        if self.study_type is not None and self.study_type not in STUDY_TYPES:
            raise ValueError(f"unknown study type: {self.study_type}")
        if self.design_family is not None and self.design_family not in DESIGN_FAMILIES:
            raise ValueError(f"unknown design family: {self.design_family}")
        return self


class Population(Entity):
    kind = _kind(EntityKind.POPULATION)


class Sample(Entity):
    """العيّنة — وحجمها `Quantity` لا `int | None`.

    `int | None` تجعل «لم يُسجَّل» و«لا ينطبق» و«نُسي» جوابًا واحدًا،
    ويملؤها أوّل مسارٍ يحتاج رقمًا. و`Quantity` تجعل الغياب قابلًا للطباعة:
    «غير مسجَّلة» تُكتب في المخطوطة كما هي.
    """

    population_id: str | None = None
    sampling_strategy: str | None = None
    size: Quantity = Field(default_factory=missing)
    kind = _kind(EntityKind.SAMPLE)

    @model_validator(mode="after")
    def _sampling_strategy_from_the_existing_vocabulary(self) -> Sample:
        if self.sampling_strategy is not None and self.sampling_strategy not in SAMPLING_STRATEGIES:
            raise ValueError(f"unknown sampling strategy: {self.sampling_strategy}")
        return self

    @property
    def supports_generalization(self) -> bool:
        """هل يسمح أسلوب المعاينة بالتعميم؟ يُقرأ من الجدول القائم لا يُقدَّر."""
        return SAMPLING_STRATEGIES.get(self.sampling_strategy or "", False)


class Measure(Entity):
    """المقياس — و`scale_type` قيمه هي قيم `variables.scale_type` نفسها."""

    construct_id: str | None = None
    scale_type: str | None = Field(default=None, pattern="^(nominal|ordinal|interval|ratio)$")
    kind = _kind(EntityKind.MEASURE)


class Dataset(Entity):
    """مجموعة البيانات، و`current_freeze_id` إصدارها المجمَّد الحالي (§17.3).

    التجميد هو ما يجعل «تغيّرت البيانات» سؤالًا يُجاب عليه بمقارنة معرّفين،
    لا بحكمٍ تقديري.
    """

    state: str | None = Field(default=None,
                              pattern="^(raw|cleaned|analysis_locked|derived)$")
    current_freeze_id: str | None = None
    kind = _kind(EntityKind.DATASET)


class Analysis(Entity):
    """تشغيلة تحليل — بمعرّف تجميد البيانات التي جرت عليها.

    `dataset_freeze_id` هو نفسه عمود `analysis_runs.dataset_freeze_id`.
    وغيابه ليس تفصيلًا: `reproducibility.py` تُسقط وصف «قابلة للإعادة» عند
    غيابه، وهذا الحقل يحمل المعنى نفسه هنا.
    """

    test_kind: str | None = None
    dataset_freeze_id: str | None = None
    outcome_scale: str | None = Field(default=None,
                                      pattern="^(nominal|ordinal|interval|ratio)$")
    predictor_scale: str | None = Field(default=None,
                                        pattern="^(nominal|ordinal|interval|ratio)$")
    group_count: int | None = Field(default=None, ge=1)
    # الافتراضات المفحوصة: اسم الافتراض ← هل تحقّق؟ و`None` تعني «لم يُفحص»،
    # وهي حالةٌ ثالثة لا تُقرأ «تحقّق» ولا «لم يتحقّق».
    assumptions: dict[str, bool | None] = Field(default_factory=dict)
    kind = _kind(EntityKind.ANALYSIS)

    @model_validator(mode="after")
    def _test_kind_from_the_existing_vocabulary(self) -> Analysis:
        if self.test_kind is not None and self.test_kind not in TEST_KINDS:
            raise ValueError(f"unknown test kind: {self.test_kind}")
        return self


class Finding(Entity):
    """نتيجة — ولها قيمةٌ إحصائية بحالتها لا رقمٌ عارٍ."""

    statement_ar: str | None = None
    p_value: Quantity = Field(default_factory=missing)
    kind = _kind(EntityKind.FINDING)


class Limitation(Entity):
    kind = _kind(EntityKind.LIMITATION)


class Gap(Entity):
    kind = _kind(EntityKind.GAP)


class Source(Entity):
    """مصدر في مكتبة البحث.

    `use_state` قيمه الثلاث هي قيم `project_sources.use_state` حرفيًّا
    (ترحيل 0020)، و`saved_only` هي القيمة الافتراضية هناك — أي أن المصدر
    يبدأ محفوظًا لا مستعمَلًا، والقرار بإدراجه قرار الباحث.
    """

    use_state: str = Field(default="saved_only", pattern="^(included|saved_only|excluded)$")
    verification_status: str = Field(default="unverified",
                                     pattern="^(unverified|verified|rejected)$")
    kind = _kind(EntityKind.SOURCE)


class Claim(Entity):
    """ادّعاء في مخطوطة.

    `origin` يفرّق بين ما يُعرض حقيقةَ مصدر وما يُعرض تفسيرًا أو اقتراحًا —
    والقاعدة التي تلزم الدليل تنطبق على `fact` وحدها، كما في
    `factual_claim_without_verified_evidence`.
    """

    text_ar: str = ""
    origin: str = Field(default="fact", pattern="^(fact|interpretation|proposal)$")
    kind = _kind(EntityKind.CLAIM)


class Evidence(Entity):
    """دليل.

    `source_type` قيمه هي قيم `provenance_events.source_type`: مسارات
    الترقية الأربع، و`model_output` معها — وهي القيمة التي يمنع القيد
    `ck_provenance_model_output_not_verified` أن تُصير `verified` أبدًا.
    """

    source_type: str = Field(
        pattern="^(external_source|upload|analysis_run|user_statement|model_output)$")
    verification_status: str = Field(
        default="unverified", pattern="^(unverified|approved|rejected|verified)$")
    source_ref: str | None = None
    kind = _kind(EntityKind.EVIDENCE)


class Recommendation(Entity):
    kind = _kind(EntityKind.RECOMMENDATION)


class Relationship(BaseModel):
    """رابطٌ بطرفين معلومَي النوع.

    النوعان يُفحصان عند الإنشاء لا عند القراءة: رابطٌ مقلوب الاتجاه يُكتب
    مرةً ويُقرأ ألف مرة، وكل قراءةٍ بعده تبني على اتجاهٍ خاطئ.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: RelationKind
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)

    @property
    def endpoints(self) -> tuple[EntityKind, EntityKind]:
        return RELATION_ENDPOINTS[self.kind]


class ResearchGraph(BaseModel):
    """لقطةُ مشروعٍ واحد: كياناته وروابطه.

    **لقطةٌ لا مخزن.** لا تُحفظ ولا تُقرأ من قاعدة بيانات؛ تُبنى من الحالة
    القائمة وتُمرَّر إلى محرّك القواعد. وهذا ما يجعل كل قاعدة قابلة للاختبار
    بلا قاعدة بيانات — الدرس نفسه المسجَّل في رأس
    `services/golden_thread/vocab.py`.
    """

    model_config = ConfigDict(extra="forbid")

    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    @model_validator(mode="after")
    def _relationships_must_match_their_endpoints(self) -> ResearchGraph:
        by_id = {entity.id: entity for entity in self.entities}
        if len(by_id) != len(self.entities):
            raise ValueError("entity ids must be unique within one graph")
        for link in self.relationships:
            expected_source, expected_target = link.endpoints
            source = by_id.get(link.source_id)
            target = by_id.get(link.target_id)
            # طرفٌ معلَّق: الرابط يشير إلى كيان غير موجود في اللقطة. وهو
            # بالضبط ما منعه `ManuscriptSectionClaim` حين استبدل المفتاح
            # الأجنبي بمصفوفة المعرّفات — مصفوفةٌ تُجيب اليوم وتكذب غدًا.
            if source is None or target is None:
                missing_id = link.source_id if source is None else link.target_id
                raise ValueError(f"relationship endpoint not in graph: {missing_id}")
            if source.kind is not expected_source or target.kind is not expected_target:
                raise ValueError(
                    f"{link.kind.value} runs {expected_source.value} → {expected_target.value}, "
                    f"not {source.kind.value} → {target.kind.value}"
                )
        return self

    def of_kind(self, kind: EntityKind) -> list[Entity]:
        return [entity for entity in self.entities if entity.kind is kind]

    def one_of_kind(self, kind: EntityKind) -> Entity | None:
        found = self.of_kind(kind)
        return found[0] if found else None

    def by_id(self, entity_id: str) -> Entity | None:
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        return None

    def links(self, kind: RelationKind) -> list[Relationship]:
        return [link for link in self.relationships if link.kind is kind]

    def targets(self, kind: RelationKind, source_id: str) -> list[str]:
        return [link.target_id for link in self.links(kind) if link.source_id == source_id]

    def sources(self, kind: RelationKind, target_id: str) -> list[str]:
        return [link.source_id for link in self.links(kind) if link.target_id == target_id]
