"""عقود الفرز ومصفوفة الأدبيات | Screening + matrix contracts (PUBRIVA).

**الحقل يقول ما يعرفه ويسكت عمّا لا يعرفه.** فلا حقل هنا يحمل قيمةً
افتراضية تُقرأ حقيقة: `doi` يغيب حين لا يكون متحقَّقًا، و`reading_scope`
يُحسب من حالٍ مسجَّلة لا من نيّة، و«لا سبب» في الاستبعاد حالٌ لا يقبلها
العقد أصلًا.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from ..models.screening import (
    CELL_STATES,
    EXCLUSION_REASON_CODES,
    SOURCE_SCOPES,
)

# **الأنماط تُشتقّ من السجل لا تُكتب بجانبه.** مفردةٌ تُكتب مرّتين تفترق
# بأول إضافة، فيقبل العقد ما يرفضه القيد — أو العكس، وهو أسوأ.
_REASON_PATTERN = "^(" + "|".join(EXCLUSION_REASON_CODES) + ")$"
_STATE_PATTERN = "^(" + "|".join(CELL_STATES) + ")$"
_SCOPE_PATTERN = "^(" + "|".join(SOURCE_SCOPES) + ")$"


class ScreeningCardView(BaseModel):
    """دراسةٌ في شاشة الفرز — بما تُعرَف به، لا بمعرّفٍ داخلي."""

    source_id: uuid.UUID
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    venue: str | None = None
    # يغيب ما لم يكن المرجع متحقَّقًا — معرّفٌ غير مفحوصٍ معروضٌ يُقرأ إثباتًا.
    doi: str | None = None
    # من أين جاء هذا المرجع: `crossref` أو `openalex` أو رفعُ الباحث نفسه.
    registry: str | None = None
    verification_status: str
    retraction_status: str
    use_state: str
    exclusion_reason_code: str | None = None
    reason_ar: str | None = None
    decided_at: dt.datetime | None = None
    added_at: dt.datetime | None = None
    # أقصى مدًى صادقٍ للقراءة من هذا المرجع في هذا البحث.
    reading_scope: str
    has_abstract: bool = False


class ScreeningView(BaseModel):
    """شاشة الفرز كاملة — **وأعدادها محسوبة لا مُقدَّرة**."""

    project_id: uuid.UUID
    cards: list[ScreeningCardView] = Field(default_factory=list)
    saved_only: int = 0
    included: int = 0
    excluded: int = 0
    # مفردة الأسباب تأتي من الخادم: الواجهة تعرض أسماءها ولا تخترع رمزًا.
    reason_codes: list[str] = Field(default_factory=list)


class MatrixCellView(BaseModel):
    """خليةٌ واحدة — **قيمةٌ وحالٌ ومَدًى ومَن كتبها**، لا نصٌّ مجرَّد."""

    field_key: str
    value_ar: str | None = None
    cell_state: str
    source_scope: str
    extraction_method: str
    verification_status: str
    source_file_id: uuid.UUID | None = None
    evidence_quote: str | None = None
    evidence_locator: str | None = None


class MatrixRowView(BaseModel):
    source_id: uuid.UUID
    title: str
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    doi: str | None = None
    reading_scope: str
    cells: list[MatrixCellView] = Field(default_factory=list)


class MatrixView(BaseModel):
    project_id: uuid.UUID
    fields: list[str] = Field(default_factory=list)
    rows: list[MatrixRowView] = Field(default_factory=list)
    note_ar: str = (
        "المصفوفة للدراسات المدرجة وحدها. وكل خلية تحمل مدى ما قُرئ منه — "
        "وما لم يُذكر في المصدر يبقى «غير مذكور» ولا يُملأ."
    )


class MatrixCellRequest(BaseModel):
    """كتابةُ خلية — **والمدى يُصرَّح به ويُفحص، لا يُفترض**.

    ولا `value_ar` مع `missing`: الغياب غيابٌ، وقيمةٌ بجانبه تناقضٌ يرفضه
    القيد في القاعدة أيضًا — فيُردّ هنا برسالةٍ مفهومة بدل خطأ قاعدة.
    """

    cell_state: str = Field(pattern=_STATE_PATTERN)
    source_scope: str = Field(pattern=_SCOPE_PATTERN)
    value_ar: str | None = Field(default=None, max_length=4000)
    evidence_quote: str | None = Field(default=None, max_length=2000)
    evidence_locator: str | None = Field(default=None, max_length=200)
    source_file_id: uuid.UUID | None = None


class MatrixCellVerifyRequest(BaseModel):
    """حكمُ الباحث على خليةٍ مكتوبة — والأربعة من الترحيل 0016.

    و«لا أعرف» حالةٌ أولى: من راجع خليةً ولم يستطع الحكم عليها **لم
    يرفضها**، وخلطُ الاثنين يجعل التردّد يبدو بطلانًا.
    """

    verification_status: str = Field(pattern="^(approved|rejected|unknown)$")


__all__ = [
    "MatrixCellRequest",
    "MatrixCellVerifyRequest",
    "MatrixCellView",
    "MatrixRowView",
    "MatrixView",
    "ScreeningCardView",
    "ScreeningView",
]
