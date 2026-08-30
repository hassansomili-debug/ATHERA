from .aging import AgingReport
from .miner import OpportunityDraft, ThesisFacts, mine
from .overlap import (
    NOT_COMPUTED,
    DimensionScore,
    OpportunityFingerprint,
    OverlapPolicy,
    OverlapResult,
    compare,
    matrix,
)
from .readiness import ComponentScore, ReadinessScore, classify, total_weight
from .vocab import (
    AUTHORSHIP_PARTY_KINDS,
    CREDIT_ROLES,
    OPPORTUNITY_KINDS,
    OVERLAP_DIMENSIONS,
    PAPER_KINDS,
    READINESS_COMPONENTS,
    READINESS_OUTCOMES,
    RIGHTS_BASES,
    THESIS_SECTIONS,
)

# ── تحميل كسول لما يعتمد على طبقة النماذج (PEP 562) ──
#
# `rights` تستورد نماذج SQLAlchemy، و`models.thesis` تستورد `vocab` من هذه
# الحزمة. استيراد `rights` مبكرًا هنا يغلق الدورة ويكسر الاستيراد كله.
# التحميل عند الطلب يفك الدورة دون تغيير الواجهة العامة للحزمة.
_LAZY = {
    "GateStatus": "rights",
    "RightsGateError": "rights",
    "add_author": "rights",
    "approve_gate": "rights",
    "gate_status": "rights",
    "record_consent": "rights",
    "ANALYSIS_ONLY_STATUSES": "rights",
}


def __getattr__(name: str):
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "OpportunityFingerprint", "OverlapPolicy", "OverlapResult", "DimensionScore",
    "compare", "matrix", "NOT_COMPUTED",
    "ReadinessScore", "ComponentScore", "classify", "total_weight",
    "ThesisFacts", "OpportunityDraft", "mine",
    "GateStatus", "RightsGateError", "gate_status", "add_author", "record_consent",
    "approve_gate", "ANALYSIS_ONLY_STATUSES",
    "AgingReport",
    "THESIS_SECTIONS", "OPPORTUNITY_KINDS", "PAPER_KINDS", "OVERLAP_DIMENSIONS",
    "READINESS_COMPONENTS", "READINESS_OUTCOMES", "CREDIT_ROLES",
    "AUTHORSHIP_PARTY_KINDS", "RIGHTS_BASES",
]
