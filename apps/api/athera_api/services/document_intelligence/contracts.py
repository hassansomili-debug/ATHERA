"""عقد الاستخراج | The extraction output contract (§15، §16).

النموذج يعيد **بنية** لا نثرًا. والنثر الحرّ يجعل النظام يقرأ اقتراحًا على
أنه قيمة، ويفقد الموضع الذي جاءت منه.
"""
from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, Field

# الحالات الأربع في §15 — و`extracted` وحدها تحمل قيمة.
STATUS_EXTRACTED: Final = "extracted"
STATUS_NOT_FOUND: Final = "not_found"
STATUS_AMBIGUOUS: Final = "ambiguous"
STATUS_NEEDS_REVIEW: Final = "needs_review"
CANDIDATE_STATUSES: Final = (
    STATUS_EXTRACTED, STATUS_NOT_FOUND, STATUS_AMBIGUOUS, STATUS_NEEDS_REVIEW,
)


class ExtractedField(BaseModel):
    """حقل واحد كما رآه النموذج في المصدر."""

    field_key: str
    status: str = Field(pattern="^(extracted|not_found|ambiguous|needs_review)$")
    # `None` حين لا توجد قيمة — لا سلسلة فارغة ولا «غير معروف» كنصّ.
    value: Any = None
    # اقتباس حرفي من المقطع. حاجز الاختلاق يرفض ما لا يوجد فيه (§4).
    quote: str | None = None
    # ثقة **الاستخراج** لا صحّة العلم (§16).
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class ExtractionBatch(BaseModel):
    fields: list[ExtractedField] = Field(default_factory=list)
