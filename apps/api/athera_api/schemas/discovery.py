"""عقود اكتشاف المراجع | Reference discovery contracts.

**المرشَّح ليس مرجعًا مخزَّنًا، والمرجع المخزَّن ليس دليلًا.** ثلاث حالات
لا يجوز طيّها في واحدة، والعقد هنا يحفظ الأولى منها: لا معرّف لمرشَّح في
قاعدتنا، ولا حال استعمال — لأنه لم يدخل المكتبة بعد.

وكل حقلٍ يبقى مصحوبًا بمن قاله في `claims`؛ فالقيمة المعروضة اختيارٌ
بأسبقيةٍ مُعلَنة، لا حقيقةٌ بلا مصدر.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReferenceSearchRequest(BaseModel):
    """عنوانٌ أو كلماتٌ مفتاحية أو DOI — والخادم يميّزها، لا الباحث."""

    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=20, ge=1, le=50)
    year_from: int | None = Field(default=None, ge=1400, le=2200)
    year_to: int | None = Field(default=None, ge=1400, le=2200)
    work_type: str | None = Field(default=None, max_length=64)
    open_access_only: bool = False


class ProviderClaimView(BaseModel):
    """ما قاله فهرسٌ واحد — منسوبًا إليه بالاسم."""

    provider: str
    provider_id: str
    doi: str | None = None
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    abstract: str | None = None
    url: str | None = None
    open_access: bool | None = None
    citation_count: int | None = None
    type: str | None = None
    retraction_status: str


class ReferenceCandidateView(BaseModel):
    """مرشَّح بحثٍ واحد. الحقول للعرض، و`claims` للنسبة."""

    doi: str | None = None
    title: str
    authors: list[str] = []
    year: int | None = None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    abstract: str | None = None
    url: str | None = None
    open_access: bool | None = None
    type: str | None = None
    retraction_status: str
    providers: list[str] = []
    # عدّاد كل فهرسٍ منسوبًا إليه — لا مجموع ولا متوسّط.
    citation_counts: dict[str, int] = {}
    # لماذا اجتمعت هذه الادعاءات في بطاقةٍ واحدة: doi | provider_id |
    # title_year_author | single. يجعل الدمج مُراجَعًا لا مسلَّمًا به.
    match_basis: str
    claims: list[ProviderClaimView] = []
    # الحفظ في المكتبة يمرّ بمعرّفٍ شرعيّ. وبلا DOI لا يُخزَّن مرجعٌ متحقَّق
    # ولا يُختلق له معرّف — فيُقال ذلك في العقد بدل أن يفشل الزرّ صامتًا.
    can_be_saved: bool = False


class ProviderStatusView(BaseModel):
    """حال فهرسٍ في هذه التشغيلة — يُعرض ليُقرأ الفشل فشلًا."""

    provider: str
    ok: bool
    detail: str | None = None
    results: int = 0


class ExternalAccessLinkView(BaseModel):
    """رابط وصول إضافي — يُحفظ ولا يُقرأ منه شيء.

    `verified` هنا `False` دائمًا وبنيةً: المنصّة لم تُسأل ولن تُسأل.
    """

    url: str
    host: str
    verified: bool = False
    note_ar: str = (
        "هذا رابط وصول إضافي فقط. لا تُجمع منه بيانات وصفية ولا يُعدّ متحقَّقًا؛ "
        "البيانات تأتي من معرّفٍ شرعي أو من فهرسٍ علمي."
    )
    note_en: str = (
        "This is an additional access link only. No metadata is collected from it and it "
        "is not treated as verified; metadata comes from a legitimate identifier or index."
    )


class ReferenceSearchResponse(BaseModel):
    """نتيجة الاكتشاف — ومعها من أجاب ومن تعذّر، لأن الفرق بينهما جوهري."""

    candidates: list[ReferenceCandidateView] = []
    providers: list[ProviderStatusView] = []
    # `False` تعني أن هذا النشر لم يُفعّل فيه فهرسٌ خارجي أصلًا — وهي حالٌ
    # ثالثة لا تُقرأ «لا نتائج» ولا «تعذّر الفهرس».
    providers_enabled: bool = True
    any_provider_failed: bool = False
    all_providers_failed: bool = False
    external_link: ExternalAccessLinkView | None = None
    note_ar: str = "نتيجة البحث ليست مرجعًا مخزَّنًا، والمرجع المخزَّن ليس دليلًا."
    note_en: str = (
        "A search result is not a stored reference, and a stored reference is not evidence."
    )
