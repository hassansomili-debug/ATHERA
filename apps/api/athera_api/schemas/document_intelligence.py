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
    # **ما يعرفه الكود يقينًا ليس مرشّحًا ينتظر تصديق الباحث.**
    #
    # اسمُ الملف وعددُ صفحاته يُقرآن من بيانات الملف الوصفية لا من متنه،
    # فاقتباسُهما ليس في نصّ المصدر بحكم التعريف. والاعتماد يشترط التأصيل
    # في النصّ — فطلبُهما من الباحث زرٌّ لا يمكن أن ينجح أبدًا: يضغطه فيردّ
    # الخادم `memory.quote_not_grounded` في كل مرّة. قِيس على الإنتاج: تسعةٌ
    # من عشرة مرشّحات تُعتمد، وواحدٌ — اسم الملف — يُرفض دائمًا.
    #
    # فالحقيقة الحتمية تُعرض بقيمتها ومصدرها، ولا يُطلب فيها قرار.
    decidable: bool = True


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


class ConsentDecision(BaseModel):
    """قرار الباحث في إرسال مستنده إلى مزوّد خارجي.

    ولا قيمة افتراضية: الموافقة تُقال صراحةً ولا تُستنتج من صمت.
    """

    decision: str = Field(pattern="^(grant|decline|revoke)$")


class ConsentState(BaseModel):
    """حالة الإذن كما هي — وما يترتب عليها.

    `provider` يُقرأ من وضعية المنصة لا من نصّ مترجَم: شاشةٌ تسمّي مزوّدًا
    غير المضبوط فعلًا تطلب موافقةً على غير ما سيقع.
    """

    file_id: uuid.UUID
    # granted | declined | absent
    state: str
    capability: str
    max_classification: str
    provider: str
    model: str | None = None
    decided_at: dt.datetime | None = None
    title: str
    body: str
    accept_label: str
    decline_label: str
    revoke_label: str
    # ما يُستبعَد محليًّا قبل أي إرسال — عددًا لا نصًّا.
    excluded_chunks: dict[str, int] = Field(default_factory=dict)
