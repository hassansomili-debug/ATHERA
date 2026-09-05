"""عقود الخيط الذهبي والمنهجية | Golden thread contracts (§15، §16)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ElementCreateRequest(BaseModel):
    element_type: str = Field(
        pattern="^(phenomenon|problem|gap|question|objective|theory|construct|variable|"
                "method|instrument|analysis|result|discussion|recommendation|hypothesis)$"
    )
    label_ar: str = Field(min_length=2)
    label_en: str | None = None
    detail_ar: str | None = None
    ordinal: int = 1


class ElementResponse(BaseModel):
    id: uuid.UUID
    element_type: str
    label: str
    label_ar: str
    label_en: str | None
    ordinal: int


class LinkCreateRequest(BaseModel):
    source_element_id: uuid.UUID
    target_element_id: uuid.UUID
    link_type: str = Field(
        pattern="^(addresses|answers|maps_to|operationalizes|measures|analyzes|"
                "produces|supports|explains|derives_from)$"
    )
    note_ar: str | None = None


class FindingResponse(BaseModel):
    check_key: str
    kind: str
    is_blocking: bool
    detail: str
    detail_ar: str
    detail_en: str
    element_ids: list[str]
    excerpt: str | None


class ConsistencyResponse(BaseModel):
    """§15.3 — الدرجة لا تُعاد وحدها أبدًا.

    `findings` و`missing_elements` حقول إلزامية في العقد نفسه، فلا يستطيع
    أي عميل قراءة الرقم بمعزل عن سببه.

    **و`presented_score` هي التي تُعرض، لا `score`.** الأخيرة تبقى للبوابة
    ولقطة الاعتماد كما كانت — رقمٌ آليّ يقرؤه محرّك — والأولى `None` ما دامت
    العناصر الأساسية ناقصة، فلا يجد العارضُ صفرًا يعرضه عن نقصٍ لم يُفحص.

    **والأعداد مفصولةٌ بأسمائها.** `blocking_count` تجمع البنيويّ والمفقود
    معًا للبوابة، وجمعُهما في شاشةٍ يُنتج «تسعة عيوب حاجبة» فوق «لا توجد
    عيوب اتساق». فـ`missing_count` و`structural_count` و`linguistic_count`
    تُعاد منفصلة، وكلٌّ منها يُعرض باسمه.
    """

    score: int
    # `None` تعني «لا تُعرض درجة»، ولا تعني صفرًا — والفرق هو كل الفرق.
    presented_score: int | None = None
    is_computable: bool = True
    not_computed_reason: str | None = None
    not_computed_reason_ar: str | None = None
    not_computed_reason_en: str | None = None
    findings: list[FindingResponse]
    missing_elements: list[str]
    # عناصر مفقودة · عيوب بنيوية · تنبيهات منهجية — ثلاثة أعداد لا عدد واحد.
    missing_count: int = 0
    structural_count: int = 0
    linguistic_count: int = 0
    # لا مقارنة تُنتج تعارضًا في هذا الفحص، ويُقال لماذا بدل أن يُعرض صفرٌ صامت.
    conflict_count: int = 0
    conflict_note: str | None = None
    conflict_note_ar: str | None = None
    conflict_note_en: str | None = None
    blocking_count: int
    advisory_count: int
    can_pass_gate: bool
    is_final_verdict: bool = False
    note: str
    note_ar: str
    note_en: str


class RequirementResponse(BaseModel):
    key: str
    label: str
    label_ar: str
    label_en: str
    is_blocking: bool
    gate: str | None
    satisfied: bool


class MethodologyResponse(BaseModel):
    study_type: str
    requirements: list[RequirementResponse]
    missing_blocking: list[str]
    missing_advisory: list[str]
    is_complete: bool


class ProtocolCreateRequest(BaseModel):
    title_ar: str = Field(min_length=3)
    summary_ar: str | None = None
    summary_en: str | None = None
    version_label: str = "v1"


class GateSubmitRequest(BaseModel):
    gate: str = Field(pattern="^(G2|G3|G4|G5)$")
    reason: str | None = Field(default=None, max_length=1000)


class ProtocolResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version_label: str
    title_ar: str
    current_gate: str
    status: str
    approved_gate: str | None
    approved_at: dt.datetime | None
    consistency: ConsistencyResponse | None


class ThreadNodeView(BaseModel):
    """عقدةٌ في الخيط — واسمُ الجدول الذي قُرئت منه معها.

    و«نتيجة» في عناصر الخيط ليست «نتيجة» في مخرجات التحليل. ومن لا يعرف
    ذلك يقرأ توصيةً مسنودةً إلى نصٍّ كتبه بيده مسنودةً إلى تحليل.
    """

    id: str
    stage: str
    label: str
    origin: str
    detail: str | None = None


class ThreadStageView(BaseModel):
    key: str
    label: str
    label_ar: str
    label_en: str
    nodes: list[ThreadNodeView] = Field(default_factory=list)


class ThreadConnectionView(BaseModel):
    """وصلةٌ أو غيابُ وصلة — ومعها الصفّ الذي يشهد لها إن وُجد.

    والطرف الغائب يبقى `null`: ملؤه بأقرب عقدةٍ في مرحلته هو الخطّ المخترَع
    الذي تمنعه هذه الشاشة كلها.
    """

    stage_from: str
    stage_to: str
    state: str = Field(pattern="^(known|needs_review|missing|conflicting)$")
    detail: str
    detail_ar: str
    detail_en: str
    source_id: str | None = None
    source_label: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    basis: str | None = None


class ThreadReadNoteView(BaseModel):
    key: str
    detail: str
    detail_ar: str
    detail_en: str


class GoldenThreadView(BaseModel):
    """الخيط الذهبي كما يُعرض للباحث — **بلا درجة ولا حقلٍ تُكتب فيه**.

    و`ConsistencyResponse` تحمل درجةً لبوابة البروتوكول (§15.3)، وهي قرارٌ
    آخر لجهةٍ أخرى. ونقلُها إلى هنا يعيد ما مُنع في «ما نعرفه»: رقمٌ يخفي
    الفرق بين خيطٍ تنقصه وصلةٌ وخيطٍ ينقصه منهج.

    و`counts` أعدادٌ بحالاتها لا مجموعُ نقاط: «ثلاث وصلات ناقصة» تُقرأ
    فتُصحَّح، و«٧٤٪» تُقرأ فتُطمئن.
    """

    project_id: uuid.UUID
    title: str
    # **العنوان البديل يُعلَن بديلًا.** بحثٌ لم يُسمَّ بعد ليس بحثًا اسمُه
    # «مشروع بدون عنوان»، وبلا هذه الراية يُقرأ الأول الثانيَ.
    title_is_fallback: bool = False
    # تاريخ الإنشاء حقلٌ مستقلّ — ودمجُه في العنوان هو أصلُ العناوين المشوَّهة.
    created_at: dt.datetime | None = None
    stages: list[ThreadStageView] = Field(default_factory=list)
    connections: list[ThreadConnectionView] = Field(default_factory=list)
    read_notes: list[ThreadReadNoteView] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    note: str
    note_ar: str
    note_en: str


# ─────────────────── من كشفٍ إلى فعلٍ مقترح إلى معاينة ───────────────────


class SuggestedActionView(BaseModel):
    """فعلٌ **مقترح** على كشف — ولا شيء في هذا العقد يُنشئ التزامًا.

    `creates_obligation` ثابتةٌ `False` في العقد نفسه، فالعميل الذي يقرأ
    هذه الاستجابة يعرف من شكلها — لا من وثيقةٍ بجانبها — أنّ شيئًا لم
    يُكتب. والمساران اللذان يُصدرانها `GET`.
    """

    key: str
    finding_key: str
    category: str
    # بمفردات المستودع: known | missing | needs_review | conflicting.
    state: str
    action_kind: str
    title: str
    title_ar: str
    title_en: str
    detail: str
    detail_ar: str
    detail_en: str
    rule_id: str | None = None
    rule_status: str | None = None
    rule_is_enforceable: bool = False
    provenance: str | None = None
    excerpt: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    has_evidence: bool = False
    creates_obligation: bool = False


class UndeterminedFieldView(BaseModel):
    """حقلٌ في المهمّة لا يعرفه هذا المسار — يُسمَّى ولا يُملأ باختراع."""

    key: str
    label: str
    label_ar: str
    label_en: str


class TaskPreviewView(BaseModel):
    """المهمّة **لو** قَبِل الباحث — ولا صفَّ كُتب.

    `created` ثابتةٌ `False` و`is_preview` ثابتةٌ `True`: معاينةٌ تستطيع أن
    تقول «أُنشئت» ليست معاينة.
    """

    action_key: str
    title: str
    title_ar: str
    title_en: str
    detail: str
    detail_ar: str
    detail_en: str
    source: str
    source_ar: str
    source_en: str
    excerpt: str | None = None
    entity_ids: list[str] = Field(default_factory=list)
    undetermined_fields: list[UndeterminedFieldView] = Field(default_factory=list)
    is_preview: bool = True
    created: bool = False
    # يُقال بنصّه في الاستجابة، لا في حاشيةٍ على الشاشة وحدها.
    not_created_note: str
    not_created_note_ar: str
    not_created_note_en: str
    pending_contract_note: str
    pending_contract_note_ar: str
    pending_contract_note_en: str


class SuggestedActionsResponse(BaseModel):
    """قائمةُ الاقتراحات ومعها ما يقول إنّها اقتراحات."""

    project_id: uuid.UUID
    actions: list[SuggestedActionView] = Field(default_factory=list)
    advisory_note: str
    advisory_note_ar: str
    advisory_note_en: str
