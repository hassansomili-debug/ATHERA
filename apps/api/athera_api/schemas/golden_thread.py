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
    """

    score: int
    findings: list[FindingResponse]
    missing_elements: list[str]
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
    stages: list[ThreadStageView] = Field(default_factory=list)
    connections: list[ThreadConnectionView] = Field(default_factory=list)
    read_notes: list[ThreadReadNoteView] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    note: str
    note_ar: str
    note_en: str
