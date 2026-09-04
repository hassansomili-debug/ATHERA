"""عقود الرسائل وفرص النشر | Thesis and opportunity contracts (§35.7، §23)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ThesisCreateRequest(BaseModel):
    title_ar: str = Field(min_length=3)
    title_en: str | None = None
    degree: str = Field(pattern="^(masters|phd)$")
    defended_on: dt.date | None = None
    data_collected_on: dt.date | None = None
    institution_ar: str | None = None
    file_id: uuid.UUID | None = None
    rights_basis: str | None = Field(
        default=None, pattern="^(thesis_owner|supervisor_with_consent|institution_policy)$"
    )
    owner_name: str | None = None
    supervisor_name: str | None = None


class ThesisResponse(BaseModel):
    """`None` تعني «لم يُستخرَج بعد»، لا «فارغ» ولا قيمة نائبة.

    والواجهة تترجمها إلى حالة مفهومة («جارٍ استخراج عنوان الرسالة»)؛ فالعقد
    يبقى واقعيًّا والتسمية تبقى مسؤولية العرض.
    """

    id: uuid.UUID
    title: str | None
    title_ar: str | None
    degree: str | None
    # حالة المعالجة — من آخر تشغيلة استخراج، لا من حالة الملف.
    processing_status: str | None = None
    defended_on: dt.date | None
    data_collected_on: dt.date | None
    rights_basis: str | None
    parsed_at: dt.datetime | None
    sections_extracted: int
    opportunities_found: int


class ParseResponse(BaseModel):
    thesis_id: uuid.UUID
    chunks_parsed: int
    sections_extracted: int
    results_extracted: int
    note_ar: str = "كل قسم مستخرج غير متحقق حتى تراجعه بنفسك."
    note_en: str = "Every extracted section stays unverified until you review it."


class AgingResponse(BaseModel):
    data_age_years: float | None
    literature_age_years: float | None
    needs_literature_update: bool | None
    needs_reanalysis_review: bool | None
    note: str
    note_ar: str
    note_en: str


class MineResponse(BaseModel):
    thesis_id: uuid.UUID
    opportunities_created: int
    kinds: list[str]
    aging: AgingResponse
    note_ar: str = "الفرص مقترحات مؤصَّلة في عناصر الرسالة، ولا تتقدم بلا اعتماد الحقوق."
    note_en: str = "Opportunities are grounded proposals; none advances without rights approval."


class OpportunityResponse(BaseModel):
    id: uuid.UUID
    thesis_id: uuid.UUID
    opportunity_kind: str
    opportunity_kind_label: str
    paper_kind: str
    paper_kind_label: str
    working_title: str
    working_title_ar: str
    research_question_ar: str | None
    readiness_score: float | None
    readiness_outcome: str | None
    readiness_outcome_label: str | None
    salami_alert: bool
    status: str
    rights_approved: bool
    authorship_approved: bool


class DimensionResponse(BaseModel):
    dimension: str
    label: str
    value: float | None
    status: str
    threshold: float | None
    exceeds_threshold: bool


class OverlapPairResponse(BaseModel):
    left_opportunity_id: uuid.UUID
    right_opportunity_id: uuid.UUID
    policy: str
    dimensions: list[DimensionResponse]
    exceeded: list[str]
    not_computed: list[str]
    salami_alert: bool


class OverlapMatrixResponse(BaseModel):
    thesis_id: uuid.UUID
    pairs: list[OverlapPairResponse]
    alerts: int
    note_ar: str = "التداخل مؤشر مراجعة لا حكم انتحال؛ القرار للباحث والمحرر."
    note_en: str = "Overlap is a review signal, not a plagiarism verdict; the decision is human."


class AuthorAddRequest(BaseModel):
    party_kind: str = Field(pattern="^(person|organization)$")
    display_name: str = Field(min_length=2, max_length=255)
    author_position: int = Field(ge=1, le=50)
    is_corresponding: bool = False
    credit_roles: list[str] = []


class ConsentRequest(BaseModel):
    """§24 — سندُ الموافقة حين لا يسجّلها صاحبُها بحسابه.

    ويُترك فارغًا حين يوافق الطرفُ بنفسه: حسابُه المصادَق هو السند. وحين
    يسجّلها غيرُه فلا بدّ من ورقةٍ يُشار إليها — وإلّا فهي دعوى بلا دليل.
    """

    evidence_ar: str | None = Field(default=None, max_length=2000)


class AuthorResponse(BaseModel):
    agreement_id: uuid.UUID
    party_id: uuid.UUID
    display_name: str
    author_position: int
    is_corresponding: bool
    consent_status: str
    credit_roles: list[str]


class GateStatusResponse(BaseModel):
    """§23.9 — تفصيل لا نعم/لا: الباحث يحتاج أن يعرف ما ينقصه."""

    opportunity_id: uuid.UUID
    rights_basis: str | None
    rights_approved: bool
    owner_consent_recorded: bool
    authors_total: int
    authors_consented: int
    authorship_approved: bool
    blockers: list[str]
    blocker_labels: list[str]
    can_be_ready_to_submit: bool


class PublicationMapResponse(BaseModel):
    thesis_id: uuid.UUID
    title: str
    opportunities: list[OpportunityResponse]
    overlap: OverlapMatrixResponse
    gate_summary: dict[str, int]
