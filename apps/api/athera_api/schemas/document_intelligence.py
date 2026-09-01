"""عقود ذكاء المستندات | Document intelligence contracts (S5C)."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, Field


class ExtractionStateResponse(BaseModel):
    """حالة المعالجة كما هي — لا «جارٍ» تُعرض على تشغيلة ماتت.

    الحالة تُقرأ من `extraction_runs.status` وحدها، فما تراه الشاشة هو ما
    في القاعدة لا ما تظنّه الواجهة.
    """

    thesis_id: uuid.UUID
    file_id: uuid.UUID | None
    status: str
    chunks: int
    candidates: int
    error: str | None = None
    message: str


class CandidateResponse(BaseModel):
    id: uuid.UUID
    field_key: str
    label: str
    value: Any = None
    # حالة قرار الإنسان — أربع، وهي المرجع لا مشتقّة من حقل آخر (ترحيل 0016).
    status: str = Field(pattern="^(unverified|approved|rejected|unknown)$")
    # حالة القراءة: extracted | not_found | ambiguous | needs_review.
    extraction_status: str | None = None
    # ثقة **الاستخراج** لا صحّة العلم (§16) — تُعرض بهذا المعنى في الواجهة.
    extraction_confidence: float | None = None
    quote: str | None = None
    locator: str | None = None
    decided_at: dt.datetime | None = None
    edited_by_human: bool = False
    # يظهر حين تختلف قراءة جديدة عن قيمة اعتمدها الباحث (§28).
    conflict_with: Any = None


class SectionGroup(BaseModel):
    key: str
    label: str
    fields: list[CandidateResponse]


class ReviewResponse(BaseModel):
    thesis_id: uuid.UUID
    sections: list[SectionGroup]
    total: int
    # الفئات الأربع مفصولة (§10): «لا أعرف» لا تُعدّ رفضًا ولا انتظارًا.
    approved: int
    rejected: int
    unknown: int
    pending: int
    note: str


class CandidateDecision(BaseModel):
    """قرار الباحث على مرشّح واحد.

    `approve` مع `value` يعني **تعديلًا ثم اعتمادًا**: ما يكتبه الباحث يعلو
    ما اقترحه النموذج، ويُحفظ قيمةً لا تعليقًا.
    """

    decision: str = Field(pattern="^(approve|reject|unknown)$")
    """`approve` مع `value` = تعديل ثم اعتماد."""
    value: Any = None
    reason: str | None = Field(default=None, max_length=1000)
