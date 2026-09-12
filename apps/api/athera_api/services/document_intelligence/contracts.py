"""عقد الاستخراج | The extraction output contract (§15، §16).

النموذج يعيد **بنية** لا نثرًا. والنثر الحرّ يجعل النظام يقرأ اقتراحًا على
أنه قيمة، ويفقد الموضع الذي جاءت منه.
"""
from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, Field, model_validator

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
    #
    # **وحقلٌ `extracted` بلا ثقةٍ حقلٌ لا يصلح لشيء.** كان `default=None`،
    # فيُقبل مخرَجٌ أغفلها بصمت، ويُحفظ العمود `NULL`، ثمّ تستبعده الأهليّة
    # بـ`no_extraction_confidence`. فمخرَجٌ كامل الحقول ينتهي إلى **صفر**
    # دليلٍ مؤهَّل، ولا فرصةَ نشرٍ تتكوّن — وهو ما أوقف رسالتين في الإنتاج.
    #
    # والقيمةُ تبقى اختيارية لما لا يحمل قيمةً أصلًا (`not_found` وأختيها):
    # الاشتراطُ على ما يدّعي أنّه استُخرج وحده. ويُفحص ذلك في `_confidence_required`.
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _confidence_required_when_extracted(self) -> "ExtractedField":
        """**ما ادّعى النموذجُ أنّه استخرجه يحمل ثقتَه** — أو فالمخرَج معطوب.

        ولا تُخترع قيمةٌ افتراضية هنا ولا في أيّ موضع: `0.5` مصطنعةٌ تُدخل
        دليلًا إلى التنقيب بثقةٍ لم يقلها أحد. فيُرفع الخطأ، ويتولّى خطُّ
        المعالجة ما يتولّاه لأيّ مخرَجٍ مخالفٍ للعقد.
        """
        if self.status == STATUS_EXTRACTED and self.extraction_confidence is None:
            raise ValueError(
                f"extraction_confidence is required when status is "
                f"'{STATUS_EXTRACTED}' (field_key={self.field_key!r})")
        return self


class ExtractionBatch(BaseModel):
    fields: list[ExtractedField] = Field(default_factory=list)
