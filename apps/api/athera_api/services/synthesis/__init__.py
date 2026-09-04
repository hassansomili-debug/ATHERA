"""طبقة التركيب | The synthesis layer (PUBRIVA).

**قيمتها إظهار عدم اليقين لا صنع يقين.** وكل ما في هذه الحزمة حتميّ: لا
مزوّد نموذج، ولا نصّ مولَّد، ولا مخرَجٌ يختلف بين تشغيلتين على المُدخل
نفسه. والسبب أن مخرَجًا احتماليًّا في هذا الموضع لا يُراجَع ولا يُقارَن —
وباحثٌ يرى فجوةً تظهر وتختفي لا يعرف أيّهما يصدّق.

والتقسيم يقصد الفصل بين أربع حقائق لا تُطوى في واحدة:

    `corpus`         ما نُظر فيه، وحدودُه معه
    `themes`         تجميعٌ موضوعي **مفصولًا عن** موضوعٍ علميّ
    `contradictions` تعارضٌ على بناءَين متقابلين، بسياقه
    `gaps`           فجوةٌ محتملة، محدودةٌ بما بُحث، أو عجزٌ يُعلَن
    `opportunities`  بطاقةٌ من فجوةٍ اعتمدها إنسان — وبتأكيده
"""
from .corpus import CellSnapshot, CorpusSnapshot, StudySnapshot, load_corpus
from .gaps import GapAssessment, GapProposal, NotAssessed, assess_gaps
from .themes import ThemeProposal, ThemeSupport, propose_themes
from .contradictions import ContradictionProposal, SideSnapshot, propose_contradictions
from .opportunities import (
    OpportunityPreview,
    ProjectPreview,
    RelatedStudy,
    build_preview,
    build_project_preview,
    gap_may_become_opportunity,
)

__all__ = [
    "CellSnapshot",
    "ContradictionProposal",
    "CorpusSnapshot",
    "GapAssessment",
    "GapProposal",
    "NotAssessed",
    "OpportunityPreview",
    "ProjectPreview",
    "RelatedStudy",
    "SideSnapshot",
    "StudySnapshot",
    "ThemeProposal",
    "ThemeSupport",
    "assess_gaps",
    "build_preview",
    "build_project_preview",
    "gap_may_become_opportunity",
    "load_corpus",
    "propose_contradictions",
    "propose_themes",
]
