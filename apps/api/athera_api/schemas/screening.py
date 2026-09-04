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
    DEFAULT_PAGE_SIZE,
    EXCLUSION_REASON_CODES,
    SOURCE_SCOPES,
)

# **حدُّ الدفعة يُقال في العقد لا يُكتشف بالتجربة.** ودفعةٌ بلا سقف تُرسَل
# بألف مرجع فتُقفل المعاملة على الجدول دقائق — والباحث يرى الشاشة معلّقة.
MAX_BATCH_SIZE = 100
# وتشغيلةُ الاستخراج أثقل: تقرأ نصوصًا وتكتب ثلاث عشرة خليةً لكل مرجع.
MAX_EXTRACTION_BATCH = 25

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
    # **دعوى الفهرس لا قراءةٌ وقعت.** الاسم يقول ذلك صراحةً، فلا يُقرأ يومًا
    # «النصّ الكامل متاح» — والفرق بينهما هو الفرق بين قراءةٍ وادّعاء قراءة.
    index_says_open_access: bool = False
    document_type: str | None = None
    # تنبيهٌ لا حكم: الاستبعاد للتكرار يبقى قرارَ الباحث بسببه المسجَّل.
    possible_duplicate: bool = False
    abstract_sources: int = 0
    # فهرسان أرسلا ملخّصين مختلفين — يُعرض اختلافًا ولا يُحسم بغلبة أحدهما.
    abstracts_disagree: bool = False


class ScreeningFacetsView(BaseModel):
    """خيارات التصفية الموجودة **في هذا البحث** — لا قائمةٌ عامّة تُعرض للكلّ."""

    registries: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None


class ScreeningView(BaseModel):
    """شاشة الفرز كاملة — **وأعدادها من القاعدة لا من الصفحة المعروضة**.

    و`saved_only` و`included` و`excluded` تُحسب بكل المرشّحات **إلا حال
    الفرز نفسها**: التبويب يسأل «كم مُدرَجة ضمن ما أراه الآن»، وعدٌّ فوق
    الصفحة يقول صفرًا في كل تبويبٍ سواه.

    و`total` عددُ ما تطابقه المرشّحات كلُّها ومنها الحال — وهو ما يُصفَّح.
    """

    project_id: uuid.UUID
    cards: list[ScreeningCardView] = Field(default_factory=list)
    saved_only: int = 0
    included: int = 0
    excluded: int = 0
    # مجموع الثلاثة — يُرسَل ولا يُحسب في الواجهة، فلا يفترق موضعان.
    all: int = 0
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    total: int = 0
    pages: int = 1
    # كم مرجعًا في هذا البحث يشترك مع غيره في معرّفٍ أو عنوان.
    duplicates: int = 0
    facets: ScreeningFacetsView = Field(default_factory=ScreeningFacetsView)
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
    # من أي ملخّصٍ قُرئت الخلية، ومن أرسل ذلك الملخّص.
    source_abstract_id: uuid.UUID | None = None
    abstract_provider: str | None = None
    # **الصفحة تُقال حين تُعرف وتُترك حين لا تُعرف** — ولا تُشتقّ من ترتيب مقطع.
    evidence_page: int | None = None
    evidence_section: str | None = None


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
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    # عدد الدراسات المدرجة كلِّها — لا عدد صفوف هذه الصفحة.
    total: int = 0
    pages: int = 1
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
    # **الصفحة والقسم من نصٍّ كامل وحده.** ولا يُرسَل رقمُ صفحةٍ مع ملخّص:
    # الملخّص لا صفحات له، والقيد في القاعدة يرفضه — ويُردّ هنا برسالةٍ
    # مفهومة قبل أن يصل إليه.
    evidence_page: int | None = Field(default=None, ge=1, le=100000)
    evidence_section: str | None = Field(default=None, max_length=500)


class MatrixCellVerifyRequest(BaseModel):
    """حكمُ الباحث على خليةٍ مكتوبة — والأربعة من الترحيل 0016.

    و«لا أعرف» حالةٌ أولى: من راجع خليةً ولم يستطع الحكم عليها **لم
    يرفضها**، وخلطُ الاثنين يجعل التردّد يبدو بطلانًا.
    """

    verification_status: str = Field(pattern="^(approved|rejected|unknown)$")


class BatchDecisionRequest(BaseModel):
    """قرارُ فرزٍ على مجموعةٍ — **يقع كلُّه أو لا يقع منه شيء**.

    وتسعةَ عشرَ من عشرين قرارًا وقعت وواحدٌ فشل أسوأ من عشرين فشلت: الباحث
    يعيد الأمر فيقع بعضه مرّتين، ولا يعرف أيُّها وقع. فالتحقّق يتمّ على
    الجميع أولًا، ثم تُكتب المعاملة كلُّها أو تُلغى كلُّها.

    **والاستبعاد في الدفعة يلزمه سببه كالفرد سواء** — والسبب واحدٌ للجميع
    لأن سببًا يُنسب إلى عشرين دراسةً بلا نظرٍ في كلٍّ منها ليس سببًا.
    """

    source_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_BATCH_SIZE)
    use_state: str = Field(pattern="^(included|saved_only|excluded)$")
    reason_code: str | None = Field(default=None, pattern=_REASON_PATTERN)
    reason_ar: str | None = Field(default=None, max_length=2000)


class BatchDecisionView(BaseModel):
    """ما وقع فعلًا — **عددٌ يقابل ما أُرسل، لا «تمّ»**."""

    project_id: uuid.UUID
    use_state: str
    applied: int
    source_ids: list[uuid.UUID] = Field(default_factory=list)
    note_ar: str = (
        "وقع القرار على المراجع كلّها معًا. ولو تعذّر واحد لما وقع منها شيء."
    )


class MatrixExtractionRequest(BaseModel):
    """اقرأ ما هو متاحٌ لهذه المراجع واكتب مرشّحاتها.

    ولا `use_state` هنا: المصفوفة للمدرَجة وحدها، ومرجعٌ «محفوظ فقط» لم
    يُقرَّر بعدُ أنه دليل — فتحليلُه يبني على ما لم يُحكم عليه.
    """

    source_ids: list[uuid.UUID] = Field(min_length=1,
                                        max_length=MAX_EXTRACTION_BATCH)


class SourceExtractionView(BaseModel):
    """حصيلةُ مرجعٍ واحد — **بما لم يُكتب كما بما كُتب**."""

    source_id: uuid.UUID
    scope: str
    filled: int = 0
    marked_missing: int = 0
    # خلايا كتبها الباحث أو حكم فيها — لا تُمسّ، ويُقال عددها.
    left_to_the_researcher: int = 0
    fields: list[str] = Field(default_factory=list)


class MatrixExtractionView(BaseModel):
    project_id: uuid.UUID
    results: list[SourceExtractionView] = Field(default_factory=list)
    note_ar: str = (
        "ما استُخرج آليًّا مقترحاتٌ تنتظر مراجعتك، لا معرفةً معتمدة. "
        "وما لم تذكره الدراسة بقي «غير مذكور» ولم يُملأ."
    )


class AbstractView(BaseModel):
    """ملخّصٌ منسوبٌ إلى من أرسله — **ولا يُطوى ملخّصان في واحد**."""

    id: uuid.UUID | None = None
    provider: str
    provider_identifier: str | None = None
    text: str
    retrieved_at: dt.datetime | None = None


class SourceAbstractsView(BaseModel):
    source_id: uuid.UUID
    abstracts: list[AbstractView] = Field(default_factory=list)
    # اختلافُ فهرسين يُعرض اختلافًا، ولا يُحسم بغلبة أحدهما بصمت.
    disagree: bool = False


__all__ = [
    "AbstractView",
    "BatchDecisionRequest",
    "BatchDecisionView",
    "MAX_BATCH_SIZE",
    "MAX_EXTRACTION_BATCH",
    "MatrixCellRequest",
    "MatrixExtractionRequest",
    "MatrixExtractionView",
    "ScreeningFacetsView",
    "SourceAbstractsView",
    "SourceExtractionView",
    "MatrixCellVerifyRequest",
    "MatrixCellView",
    "MatrixRowView",
    "MatrixView",
    "ScreeningCardView",
    "ScreeningView",
]
