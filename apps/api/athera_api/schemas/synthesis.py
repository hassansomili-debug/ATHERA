"""عقود طبقة التركيب | Synthesis contracts (PUBRIVA).

**العقد يحمل الحدَّ مع الدعوى.** فلا حقل هنا يخرج فيه وصفُ فجوةٍ بلا
`sources_considered` و`search_scope` و`known_limitations_ar` بجانبه: واجهةٌ
تعرض الوصف وحده تُنتج جملةً مطلقة من عقدٍ محدود.

**والاسم يُعرض لا المفتاح.** كل مفردةٍ تخرج ومعها اسمها العربي ومعناها حيث
كان للمعنى أثر — فلا يقرأ الباحث `weak_signal` ولا `topic_cluster` ولا
`GapGraphNode`.

**والأنماط تُشتقّ من السجل.** مفردةٌ تُكتب مرّتين تفترق بأول إضافة، فيقبل
العقد ما يرفضه القيد — أو العكس، وهو أسوأ.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from ..models.synthesis import (
    CONFLICT_KINDS,
    DECIDABLE_STATUSES,
    EFFECT_DIRECTIONS,
    GAP_SOURCE_ROLES,
    GAP_STRENGTHS,
    GAP_TYPES,
    SIGNIFICANCE_STATES,
    SOURCE_SCOPES,
    SUPPORT_ROLES,
    SYNTHESIS_STATUSES,
    THEME_BASES,
)

_DECISION_PATTERN = "^(" + "|".join(DECIDABLE_STATUSES) + ")$"


class DecisionRequest(BaseModel):
    """حكمُ الباحث على مرشَّح — **و`generated` ليست منها**.

    قبولُها مُدخَلًا يعني «أعِد المرشَّح إلى ما قبل أن ينظر فيه أحد»، وهو
    محوُ مراجعةٍ وقعت. والأربع الباقية تشمل «لا أعرف» (ترحيل 0016): من راجع
    ولم يستطع الحكم **لم يرفض**.
    """

    status: str = Field(pattern=_DECISION_PATTERN)
    # سببٌ اختياري يكتبه الباحث لنفسه ولمن يراجع بعده.
    note_ar: str | None = Field(default=None, max_length=2000)


class VocabularyEntry(BaseModel):
    """مفردةٌ باسمها ومعناها — والمعنى ليس زينة."""

    key: str
    label_ar: str
    label_en: str
    meaning_ar: str | None = None


class EvidenceLink(BaseModel):
    """حلقةٌ في سلسلة الأثر: مرجع ← خلية ← شاهد.

    و`matrix_cell_id` هو ما يجعل «اضغط لترى الشاهد» ممكنًا؛ وغيابه يعني أن
    السند من بياناتٍ وصفية لا من محتوًى مقروء — وتلك حالٌ تُعلَن لا تُخفى.
    """

    source_id: uuid.UUID
    title: str
    role: str = Field(pattern="^(" + "|".join(sorted(
        set(SUPPORT_ROLES) | set(GAP_SOURCE_ROLES))) + ")$")
    basis_field_key: str | None = None
    matrix_cell_id: uuid.UUID | None = None
    evidence_scope: str = Field(pattern="^(" + "|".join(SOURCE_SCOPES) + ")$")
    evidence_quote: str | None = None
    evidence_locator: str | None = None
    cell_state: str | None = None
    cell_value_ar: str | None = None


# ═════════════════════ الموضوعات ═════════════════════

class ThemeView(BaseModel):
    """موضوعٌ مرشَّح — **وأساسه معروضٌ لا مضمر**."""

    id: uuid.UUID
    label_ar: str
    description_ar: str | None = None
    basis: str = Field(pattern="^(" + "|".join(THEME_BASES) + ")$")
    basis_label_ar: str
    # الجملة التي تمنع قراءة تجميعٍ من عناوين على أنه نتيجة.
    basis_meaning_ar: str
    status: str = Field(pattern="^(" + "|".join(SYNTHESIS_STATUSES) + ")$")
    status_label_ar: str
    source_scope_summary: dict[str, int] = Field(default_factory=dict)
    supporting_count: int = 0
    contradicting_count: int = 0
    # **هل يبلغ كل سندٍ محتوًى خليةً بعينها؟** موضوعٌ لا يبلغ لا يُبنى عليه.
    is_traceable: bool = False
    generated_at: dt.datetime | None = None
    decided_at: dt.datetime | None = None


class ThemeTraceView(BaseModel):
    """المسار كاملًا: موضوع ← مراجع ← خلايا ← شواهد."""

    theme: ThemeView
    supporting: list[EvidenceLink] = Field(default_factory=list)
    contradicting: list[EvidenceLink] = Field(default_factory=list)
    note_ar: str = (
        "كل سطرٍ هنا يشير إلى خليةٍ في مصفوفة الأدبيات. افتح الخلية لترى نصّها "
        "وشاهدها ومدى ما قُرئ منه — والموضوع لا يقوم إلا على ما تراه."
    )


class ThemesView(BaseModel):
    project_id: uuid.UUID
    themes: list[ThemeView] = Field(default_factory=list)
    corpus_size: int = 0
    # **تحذيرٌ يُعرض حين يكون كلّه تجميعًا موضوعيًّا.**
    note_ar: str = ""
    basis_vocabulary: list[VocabularyEntry] = Field(default_factory=list)


# ═════════════════════ التعارضات ═════════════════════

class ContradictionSideView(BaseModel):
    """طرفٌ واحد — بسياقه كما سُجِّل، وبـ«غير مذكور» حيث لم يُسجَّل."""

    side: str = Field(pattern="^(a|b)$")
    source_id: uuid.UUID
    title: str
    result_ar: str
    direction: str = Field(pattern="^(" + "|".join(EFFECT_DIRECTIONS) + ")$")
    direction_label_ar: str
    significance: str = Field(pattern="^(" + "|".join(SIGNIFICANCE_STATES) + ")$")
    significance_label_ar: str
    population_ar: str | None = None
    country_ar: str | None = None
    method_ar: str | None = None
    measurement_ar: str | None = None
    period_year: int | None = None
    evidence_scope: str = Field(pattern="^(" + "|".join(SOURCE_SCOPES) + ")$")
    matrix_cell_id: uuid.UUID | None = None


class ContradictionView(BaseModel):
    """تعارضٌ محتمل — **بطرفيه كليهما وبسياق اختلافهما**، ولا يُسمّى أحدهما خطأ."""

    id: uuid.UUID
    construct_a_ar: str
    construct_b_ar: str | None = None
    relationship_ar: str
    conflict_kind: str = Field(pattern="^(" + "|".join(CONFLICT_KINDS) + ")$")
    conflict_label_ar: str
    context_divergence: list[str] = Field(default_factory=list)
    context_divergence_labels_ar: list[str] = Field(default_factory=list)
    context_explanation_ar: str | None = None
    status: str
    status_label_ar: str
    sides: list[ContradictionSideView] = Field(default_factory=list)
    generated_at: dt.datetime | None = None
    decided_at: dt.datetime | None = None


class ContradictionsView(BaseModel):
    project_id: uuid.UUID
    contradictions: list[ContradictionView] = Field(default_factory=list)
    corpus_size: int = 0
    note_ar: str = (
        "التعارض هنا اختلافُ نتيجتين على البناءات نفسها — لا اختلافُ صياغة ولا "
        "اختلافُ موضوع. ولا تُوصف أيّ دراسة بالخطأ: قد تكون النتيجتان صحيحتين "
        "كلٌّ في سياقها، ولذلك يُعرض السياق قبل الحكم."
    )


# ═════════════════════ الفجوات ═════════════════════

class SearchScopeView(BaseModel):
    """**مدى ما بُحث — يخرج مع كل فجوة، لا في صفحةٍ منفصلة.**"""

    indexes_searched: list[str] = Field(default_factory=list)
    # تبقى `False`: المنصّة لا تُجري بحثًا منهجيًّا في الفهارس هنا، والادّعاء
    # بغير ذلك يجعل «لم تظهر دراسة» تُقرأ نتيجةَ مسحٍ شامل.
    search_was_systematic: bool = False
    corpus_size: int = 0
    content_read: int = 0
    full_text_read: int = 0
    saved_not_screened: int = 0
    excluded: int = 0
    taken_at: str | None = None


class GapView(BaseModel):
    """فجوةٌ **محتملة** — ولا حقل هنا يقول إنها مؤكَّدة."""

    id: uuid.UUID
    gap_type: str = Field(pattern="^(" + "|".join(GAP_TYPES) + ")$")
    gap_type_label_ar: str
    description_ar: str
    why_suggested_ar: str
    known_limitations_ar: str
    strength: str = Field(pattern="^(" + "|".join(GAP_STRENGTHS) + ")$")
    strength_label_ar: str
    strength_meaning_ar: str
    sources_considered: int
    search_scope: SearchScopeView
    source_scope_distribution: dict[str, int] = Field(default_factory=dict)
    supporting: list[EvidenceLink] = Field(default_factory=list)
    contradicting: list[EvidenceLink] = Field(default_factory=list)
    considered: list[EvidenceLink] = Field(default_factory=list)
    contradiction_id: uuid.UUID | None = None
    status: str
    status_label_ar: str
    generated_at: dt.datetime | None = None
    decided_at: dt.datetime | None = None
    # فرصةٌ لا تُنشأ إلا من معتمَدة — والواجهة تعرف ذلك من الخادم لا بتخمين.
    may_become_opportunity: bool = False


class NotAssessedView(BaseModel):
    """**ما تعذّر الحكم فيه — يُعرض بقدر ما يُعرض ما حُكم فيه.**

    و`verdict` مفردةُ محرّك القواعد نفسها: `insufficient_information`. وقائمةُ
    فجواتٍ تذكر ما وجدته وتصمت عمّا عجزت عنه يقرأها الباحث «لا شيء آخر».
    """

    gap_type: str
    gap_type_label_ar: str
    verdict: str = Field(pattern="^insufficient_information$")
    reason_ar: str


class GapsView(BaseModel):
    project_id: uuid.UUID
    gaps: list[GapView] = Field(default_factory=list)
    not_assessed: list[NotAssessedView] = Field(default_factory=list)
    corpus_size: int = 0
    search_scope: SearchScopeView | None = None
    strength_vocabulary: list[VocabularyEntry] = Field(default_factory=list)
    note_ar: str = (
        "هذه فجواتٌ **محتملة** ضمن مجموعة مراجعك الحالية وحدها. لم يُجرِ النظام "
        "بحثًا منهجيًّا في الفهارس، فما لم يظهر هنا قد يكون موجودًا خارج مجموعتك. "
        "ولا تُكتب أيّ ملاحظةٍ منها في ورقةٍ بصيغة «لا توجد دراسات»."
    )


# ═════════════════════ الفرص البحثية ═════════════════════

class RelatedStudyView(BaseModel):
    source_id: uuid.UUID
    title: str
    role: str
    evidence_scope: str


class OpportunityPreviewView(BaseModel):
    """معاينةٌ **لا تكتب شيئًا** — سبعةُ أسئلةٍ بأجوبتها قبل أن يقرّر الباحث."""

    gap_candidate_id: uuid.UUID
    gap_type: str
    gap_type_label_ar: str
    what_we_noticed_ar: str
    why_it_might_matter_ar: str
    evidence_basis_ar: str
    related_studies: list[RelatedStudyView] = Field(default_factory=list)
    still_uncertain_ar: str
    strength_label_ar: str
    strength_meaning_ar: str
    next_step_ar: str
    editable_fields: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class OpportunityCreateRequest(BaseModel):
    """إنشاءُ بطاقة — **بتأكيدٍ صريح، ومن فجوةٍ معتمَدة**.

    و`uncertainties_ar` إلزاميّ: بطاقةٌ بلا عدم يقينٍ معلن تُقرأ خطةً مثبتة،
    والقيد في القاعدة يرفضها أيضًا.
    """

    gap_candidate_id: uuid.UUID
    confirmed: bool = Field(description="تأكيدٌ صريح — ولا تُنشأ بطاقة بدونه")
    phenomenon_ar: str = Field(min_length=1, max_length=2000)
    context_ar: str | None = Field(default=None, max_length=2000)
    population_ar: str | None = Field(default=None, max_length=2000)
    constructs_ar: str | None = Field(default=None, max_length=2000)
    possible_contribution_ar: str = Field(min_length=1, max_length=4000)
    methodological_opportunity_ar: str | None = Field(default=None, max_length=4000)
    evidence_basis_ar: str = Field(min_length=1, max_length=4000)
    uncertainties_ar: str = Field(min_length=1, max_length=4000)


class OpportunityView(BaseModel):
    id: uuid.UUID
    gap_candidate_id: uuid.UUID
    gap_type: str
    gap_type_label_ar: str
    phenomenon_ar: str
    context_ar: str | None = None
    population_ar: str | None = None
    constructs_ar: str | None = None
    possible_contribution_ar: str
    methodological_opportunity_ar: str | None = None
    evidence_basis_ar: str
    uncertainties_ar: str
    created_at: dt.datetime | None = None
    spawned_project_id: uuid.UUID | None = None


class OpportunitiesView(BaseModel):
    project_id: uuid.UUID
    opportunities: list[OpportunityView] = Field(default_factory=list)
    note_ar: str = (
        "كل بطاقةٍ هنا كتبها باحثٌ بيده بعد أن اعتمد فجوةً محتملة. ولا تُولَّد "
        "بطاقةٌ تلقائيًّا، ولا تعني البطاقةُ أن الفجوة ثبتت."
    )


class ProjectPreviewView(BaseModel):
    """**ما سيقع بالضبط قبل أن يقع** — وما لن يقع، وما لن يتغيّر."""

    working_title_ar: str
    from_opportunity_id: uuid.UUID
    gap_type_label_ar: str
    will_create_ar: list[str] = Field(default_factory=list)
    will_not_create_ar: list[str] = Field(default_factory=list)
    unchanged_ar: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class ProjectFromOpportunityRequest(BaseModel):
    """«إنشاء مشروع بحثي» — **معاينةٌ ثم تأكيد، ولا يقع بضغطةٍ واحدة**."""

    confirmed: bool
    working_title_ar: str = Field(min_length=1, max_length=500)


__all__ = [
    "ContradictionSideView",
    "ContradictionView",
    "ContradictionsView",
    "DecisionRequest",
    "EvidenceLink",
    "GapView",
    "GapsView",
    "NotAssessedView",
    "OpportunitiesView",
    "OpportunityCreateRequest",
    "OpportunityPreviewView",
    "OpportunityView",
    "ProjectFromOpportunityRequest",
    "ProjectPreviewView",
    "RelatedStudyView",
    "SearchScopeView",
    "ThemeTraceView",
    "ThemeView",
    "ThemesView",
    "VocabularyEntry",
]
