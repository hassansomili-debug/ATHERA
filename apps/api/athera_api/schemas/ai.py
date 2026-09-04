"""عقد أثيرا AI | The ATHERA AI response contract.

الرد **مهيكل عمدًا** لا نصًّا حرًّا: الواجهة تحتاج أن تفصل الاقتراح عن
الدليل عن الحدّ عن الخطوة التالية، والنص الحرّ يخلطها فيقرأ المستخدم
اقتراحًا على أنه نتيجة.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class AiAskRequest(BaseModel):
    question: str = Field(min_length=8, max_length=4000)
    # معرّف ملفٍ **يختاره الباحث بعينه**. ولا بحث تلقائي في ملفاته كلها:
    # المحادثة تقرأ ما أشار إليه، لا ما تستطيع الوصول إليه.
    attachment_file_id: uuid.UUID | None = None
    # الواجهة ترسله باسمه المختصر كذلك.
    file_id: uuid.UUID | None = None
    # **البحثُ الذي يعمل فيه الباحث الآن.** يُرسَل بمعرّفه ويُتحقَّق من
    # مستأجره في الخادم — فمشروعُ مستأجرٍ آخر ٤٠٤ لا سياق.
    project_id: uuid.UUID | None = None

    @property
    def selected_file(self) -> uuid.UUID | None:
        return self.attachment_file_id or self.file_id


class AttachmentState(BaseModel):
    """حال المستند المرفق — **بحقولٍ تقرؤها الواجهة، لا بنصٍّ تفسّره**.

    كانت الحدود تُقال بالعربية في `limitations` وحدها، فلم تستطع الواجهة أن
    تعرف **ماذا تعرض من زر**: أتطلب المعالجة؟ أم المراجعة؟ أم الإذن؟
    فتُترك الرسالة نصًّا يقرؤه الباحث ويُنفّذه بنفسه — أي بنداء API.

    و`needs` يقول الفعل التالي بكلمة واحدة، فتبنيه الواجهة زرًّا.
    """

    file_id: uuid.UUID
    filename: str
    # `not_processed` أو حالة تشغيلة الاستخراج الحقيقية.
    processing_status: str
    # `absent` | `granted` | `declined` — لقدرة السؤال عن المستند وحدها.
    consent_state: str
    approved_facts: int = 0
    pending_review: int = 0
    # الفعل التالي: `process` | `review` | `chat_consent` | `none`
    needs: str = "none"


class AiCapabilities(BaseModel):
    """**ثلاثُ قدراتٍ لا قدرةٌ واحدة** (Wave1-D / D1).

    كان في الطبقة منطقٌ واحد اسمه `literature_online` يُشتقّ من
    `LITERATURE_REGISTRY` وحده، فيُقال للباحث إنّ البحث الخارجي معطّل
    بينما اكتشافُ المراجع يعمل. وهما شيئان: الأول رصدٌ مجدول من سجلّ،
    والثاني نداءُ فهارس عند كل بحث.

    فالحقول ثلاثة، وكلٌّ مشتقّةٌ من مصدرها لا مكتوبةٌ بجانبه.
    """

    reference_discovery_available: bool
    reference_discovery_providers: list[str] = Field(default_factory=list)
    literature_registry_available: bool
    full_text_retrieval_available: bool


class AiCapabilitiesResponse(AiCapabilities):
    """قدراتُ الشاشة — **بلا اسم مزوّد ولا سبب تعطيلٍ داخليّ ولا رمز تصنيف**.

    `assistant_available` تقول «يستطيع أن يجيب» ولا تقول بماذا ولا لماذا لا:
    اسمُ المزوّد وسببُ تعطيله شأنُ من ينشر الخادم، ومكانه شاشةُ الإعدادات.
    """

    assistant_available: bool


class ProviderStatusLine(BaseModel):
    """حالُ فهرسٍ في هذه التشغيلة. **«لم يُجب» ليست «لا يوجد».**"""

    provider: str
    ok: bool
    results: int = 0
    detail: str | None = None


class DiscoveredReferenceView(BaseModel):
    """مرجعٌ مكتشَف — بما قاله الفهرس، منسوبًا إليه (D4).

    و`citation_counts` قاموسٌ لا رقم: عدّادُ كلّ فهرسٍ باسمه. جمعُهما يخترع
    رقمًا لا يقوله أحد، واختيارُ أحدهما بلا نسبةٍ يجعل ادعاءَ فهرسٍ حكمًا
    للمنصّة.
    """

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    providers: list[str] = Field(default_factory=list)
    citation_counts: dict[str, int] = Field(default_factory=dict)
    open_access: bool | None = None
    retraction_status: str = "unknown"
    # `metadata_only` | `abstract_only` — **ولا `full_text` من فهرسٍ أبدًا**.
    scope: str = "metadata_only"
    # المرجع يُحفظ في المكتبة بمعرّفٍ شرعي وحده، فتعرف الواجهة أيّ زرّ تعرض.
    can_be_saved: bool = False


class ExternalAccessLinkView(BaseModel):
    """رابطُ وصولٍ خارجيّ يحفظه الباحث — **لا قاعدةَ بياناتٍ تُقرأ** (D3).

    ResearchGate وAcademia.edu يمنعان الجمع الآلي، فلا يُطلبان ولا يُقرأان،
    ولا يُوصف منهما حقل. الرابط يبقى رابطًا، وحالته غير متحقَّقة.
    """

    url: str
    host: str
    verified: bool = False


class ProjectContextView(BaseModel):
    """سياقُ البحث الجاري — يظهر في شاشة أثيرا AI حين يوجد."""

    project_id: uuid.UUID
    working_title: str
    status: str
    current_gate: str | None = None


class AiAskResponse(BaseModel):
    """ما تعيده أثيرا AI — بحقولٍ تفصل ما لا يجوز خلطه."""

    answer: str
    status: str = Field(description="ok | provider_error | disabled")
    # `model_suggestion` = اقتراح نموذج لا دليل · `verified` = من طبقة الأدلة
    # `search_results` = نتائجُ بحثٍ في فهارس علمية — **وهي ليست دليلًا
    # موثَّقًا**: مرجعٌ وجده فهرسٌ لم يقرأه أحد ولم يُعتمد في هذا البحث.
    evidence_state: str = Field(
        description="model_suggestion | search_results | verified | none")
    capabilities_used: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    # للتتبّع الداخلي — لا يُعرض للباحث في المسار العادي.
    attachment: AttachmentState | None = None
    model_run_id: uuid.UUID | None = None

    # ── ما جرى في هذا الطلب، **حالًا تقرؤها الواجهة لا نصًّا تفسّره** ──
    intent: str = "general"
    search_performed: bool = False
    capabilities: AiCapabilities | None = None
    references: list[DiscoveredReferenceView] = Field(default_factory=list)
    provider_statuses: list[ProviderStatusLine] = Field(default_factory=list)
    external_link: ExternalAccessLinkView | None = None
    project: ProjectContextView | None = None
