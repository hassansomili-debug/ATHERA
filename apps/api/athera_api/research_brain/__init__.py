"""العقل البحثي — الأساس | Research Brain foundation (V1).

**أساسٌ لا ميزة.** ما هنا عقودٌ وقواعد حتمية تُختبر؛ ولا مسار API، ولا
ترحيل، ولا شاشة، ولا كتابة في قاعدة بيانات. وقراءةُ هذه الحزمة على أنها
الميزة خطأٌ يكلّف: انظر `docs/research-brain-foundation.md` وفيه ما **لم**
يُبنَ بعد، مذكورًا بالاسم.

**ولمَ لا تسكن `athera_api/brain/`:** تلك حزمة تشغيل النماذج — منسّقٌ
وأجنتات وأدوات وحواجز نصّية على مخرَج المزوّد. وهذه استدلالٌ حتميّ على حالة
البحث لا يستدعي مزوّدًا ولا يقرأ نصّ نموذج. وضمّهما في حزمةٍ واحدة يجعل
حاجزًا احتماليًّا وقاعدةً حتمية يبدوان من نوعٍ واحد، وهما ليسا كذلك: الأول
يُراجَع، والثانية تُثبت.
"""
from .canon import (
    CANON,
    CopyrightStatus,
    IngestionPermission,
    LicenseStatus,
    MethodologySource,
    SourceType,
    VerificationStatus,
    ingestible,
    ingestion_reason,
    may_ingest,
)
from .catalogue import BY_ID, RULES, TEST_FITNESS
from .ontology import (
    DESIGN_FAMILIES,
    ELEMENT_TYPE_BY_ENTITY,
    RELATION_ENDPOINTS,
    Analysis,
    Claim,
    Context,
    Construct,
    Dataset,
    Design,
    Domain,
    Entity,
    EntityKind,
    Evidence,
    Finding,
    Gap,
    Hypothesis,
    Limitation,
    Measure,
    Phenomenon,
    Population,
    Project,
    RelationKind,
    Relationship,
    Researcher,
    ResearchGraph,
    ResearchQuestion,
    Recommendation,
    Sample,
    Source,
    Theory,
)
from .rules import (
    Assessment,
    BrainFieldView,
    CandidateView,
    EvaluationReport,
    RuleCategory,
    RuleFinding,
    RuleOutcome,
    RuleResult,
    RuleStatus,
    ScientificRule,
    Verdict,
    evaluate,
)
from .values import Quantity, ValueState, known, missing, unknown

__all__ = [
    # المراجع المنهجية
    "CANON", "MethodologySource", "IngestionPermission", "LicenseStatus",
    "CopyrightStatus", "SourceType", "VerificationStatus",
    "may_ingest", "ingestion_reason", "ingestible",
    # الأنطولوجيا
    "EntityKind", "RelationKind", "RELATION_ENDPOINTS", "ELEMENT_TYPE_BY_ENTITY",
    "DESIGN_FAMILIES", "Entity", "Relationship", "ResearchGraph",
    "Researcher", "Project", "Domain", "Phenomenon", "Context", "Construct", "Theory",
    "ResearchQuestion", "Hypothesis", "Design", "Population", "Sample", "Measure",
    "Dataset", "Analysis", "Finding", "Limitation", "Gap", "Source", "Claim",
    "Evidence", "Recommendation",
    # القيم وحالاتها
    "Quantity", "ValueState", "known", "missing", "unknown",
    # محرّك القواعد
    "Assessment", "BrainFieldView", "CandidateView", "EvaluationReport", "RuleCategory",
    "RuleFinding", "RuleOutcome", "RuleResult", "RuleStatus", "ScientificRule",
    "Verdict", "evaluate", "RULES", "BY_ID", "TEST_FITNESS",
]
