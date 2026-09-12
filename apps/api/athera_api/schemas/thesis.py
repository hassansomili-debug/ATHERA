"""عقود الرسائل وفرص النشر | Thesis and opportunity contracts (§35.7، §23)."""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

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


class ThesisCardActions(BaseModel):
    """ما تعرضه البطاقة — **والشاشة لا تجتهد، بل تعرض ما يقوله الخادم**.

    كان كلُّ شرطٍ منها مكتوبًا في JSX على حدة، فافترقت الشاشة عن الخادم:
    زرُّ «تفكيك الرسالة» يُعرض دائمًا وإن ردّت النقطة `thesis.no_file`، وزرُّ
    «استخراج الفرص» مشروطٌ بـ`parsed_at` الذي لا يضعه إلّا مسارٌ قديم.
    """

    #: الفعل الأول على البطاقة: review · process · reprocess · attach_file · None
    primary: str | None = None
    #: عملٌ يجري الآن — فلا فعلَ يُعرض، ويُعرض ما يجري.
    is_running: bool = False

    can_review: bool = False
    can_process: bool = False
    can_reprocess: bool = False
    #: **المسار القديم باقٍ في الواجهة البرمجية ومسحوبٌ من البطاقة.**
    can_parse: bool = False
    can_attach_file: bool = False
    can_mine: bool = False
    #: فرصٌ قائمةٌ تُفتح — وجهةُ الرحلة، لا زرُّ تشغيلٍ يدويّ.
    can_view_opportunities: bool = False
    can_archive: bool = False
    can_restore: bool = False
    can_trash_file: bool = False
    is_archived: bool = False
    #: سببُ منعِ الأرشفة والسلّة أثناء عملٍ جارٍ — **والخادم يفرضه أيضًا**.
    lifecycle_blocked_reason: str | None = None

    #: available · in_flight · no_evidence · found · failed ·
    #: withheld · completed_empty · no_eligible_evidence
    mining_state: str
    #: لماذا التنقيب متاحٌ أو غير متاح — **بنصٍّ يصف الواقع لا وعدًا**.
    mining_reason: str
    parse_withdrawn_reason: str
    #: سببُ خلوّ البطاقة من فعلٍ الآن، إن خلت.
    blocked_reason: str | None = None


class ThesisResponse(BaseModel):
    """`None` تعني «لم يُستخرَج بعد»، لا «فارغ» ولا قيمة نائبة.

    والواجهة تترجمها إلى حالة مفهومة («جارٍ استخراج عنوان الرسالة»)؛ فالعقد
    يبقى واقعيًّا والتسمية تبقى مسؤولية العرض.

    ## وثلاثةُ عيوبٍ في الصدق يعالجها هذا العقد (Wave 1-C)

    **١ — هويّة الملفّ.** `title` وحده كان يترك خمسَ رسائل مرفوعة خمسَ
    بطاقاتٍ متطابقة تقول «لم يُستخرَج العنوان بعد». فيُضاف `source_filename`
    و`display_title` ومعهما **رايةٌ صريحة** `title_is_extracted`: البطاقة
    تعرف أنّها تعرض اسم ملفّ فتقوله، و`title_ar` في القاعدة يبقى `NULL`.

    **٢ — الحال محفوظةٌ لا مشتقّة.** `processing_state` عمودٌ على
    `theses` (ترحيل 0027)، لا حالُ آخر تشغيلةٍ على ملفّ. وإعادةُ التحميل
    تعيدها كما هي لأنّها مكتوبة، لا لأنّ تشغيلةً بقيت.

    **٣ — الرقمُ يُرافقه سببه.** «٠ أقسام · ٠ فرص» جملةٌ تُقال في ستّ
    حالاتٍ معناها مختلف. فلكلّ عددٍ حقلُ `outcome` يقول أيَّها وقع.
    """

    id: uuid.UUID
    title: str | None
    title_ar: str | None
    degree: str | None

    # ── هويّةُ البطاقة ──
    #
    # `source_filename` اسمُ الملفّ كما رفعه صاحبه، و`display_title` ما
    # يُكتب على البطاقة: العنوان المستخرَج إن وُجد، وإلّا اسمُ الملفّ.
    # و`title_is_extracted` هي التي تمنع قراءةَ الثاني على أنّه الأول.
    source_filename: str | None = None
    display_title: str | None = None
    title_is_extracted: bool = False

    # ── حالُ المعالجة المحفوظة ──
    processing_state: str
    processing_state_label: str
    processing_state_changed_at: dt.datetime | None = None
    processing_attempts: int = 0

    # ── الفشل: رمزٌ آمن ونصٌّ مفهوم — **ولا صفرٌ صامت** ──
    failure_code: str | None = None
    failure_message: str | None = None
    can_retry: bool = False
    # سببُ منع الإعادة حين تُمنع — «لا OCR بعد» لا زرٌّ مطفأ بلا تفسير.
    retry_blocked_reason: str | None = None

    # ── طبقةُ النصّ وOCR: يُقال ما وقع، ولا يُدّعى ما لم يقع ──
    text_layer_state: str = "not_checked"
    ocr_state: str = "unavailable"
    ocr_available: bool = False

    defended_on: dt.date | None
    data_collected_on: dt.date | None
    rights_basis: str | None
    parsed_at: dt.datetime | None

    sections_extracted: int
    # لماذا العدد هو ما هو: not_started · running · no_text_layer ·
    # no_eligible_evidence ·
    # awaiting_consent · failed · completed_empty · found
    sections_outcome: str
    sections_outcome_label: str

    opportunities_found: int
    opportunities_outcome: str
    opportunities_outcome_label: str
    opportunities_mined_at: dt.datetime | None = None

    # §23 — الفرص **مرشَّحات** لا أوراق، ولا تتقدّم بلا اعتماد الحقوق.
    # والراية تُرسَل مع كل صفّ فلا تُقرأ البطاقة وعدًا بالنشر.
    opportunities_are_candidates: bool = True

    # ── نتائجُ الرسالة: العدّ الثاني الذي يقرؤه المنقّب ──
    #
    # ولم يكن يُرسَل، فكانت الشاشة تحكم على إتاحة التنقيب من `parsed_at`
    # وحده — وهو ختمُ المسار القديم لا شاهدُ وجود دليل.
    results_extracted: int = 0

    # **معرّفُ ملفّ المصدر** — لتُفرَّق «أزل السجلّ» عن «انقل الملفّ إلى
    # السلّة»؛ فعلان لصاحبين، ولا يُنفَّذ أحدهما بأثرٍ جانبيّ للآخر.
    source_file_id: uuid.UUID | None = None

    #: **مؤرشَفة = مُخفاة لا محذوفة** (ترحيل 0030). و`None` تعني «في القائمة».
    archived_at: dt.datetime | None = None

    #: **حالُ التنقيب المحفوظة** (ترحيل 0031، ثمّ 0032): `not_started` ·
    #: `running` · `completed` · `withheld` · `no_eligible_evidence` ·
    #: `failed`. و`no_eligible_evidence` تقول «جرى التنقيبُ ولم يكن ثمّة
    #: دليلٌ مؤهَّل» — واقعةٌ كانت تُكتب `not_started` فتكذب على الباحث.
    #: تُقرأ من العمود مباشرةً، ولا
    #: تُشتقّ من `actions.mining_state` (ذاك سطحُ عرضٍ لا حالُ تخزين).
    #:
    #: و`mining_last_error` **لا يخرج في العقد**: رمزٌ تقنيّ داخليّ.
    mining_state: str = "not_started"

    # ── الأفعال: قرارٌ واحد يُحسب في الخادم ──
    actions: ThesisCardActions


# ── إزالةُ الرسالة: معاينةُ التبعات ثم القرار ──

class RemovalDependency(BaseModel):
    key: str
    label: str
    count: int
    #: هل تمنع هذه التبعة الإزالة — أثرُ حكمٍ بشريٍّ يمنع، ومخرجُ آلةٍ لا يمنع.
    blocking: bool


class RemovalPreviewResponse(BaseModel):
    """**ما سيُخفى مع الرسالة، قبل الأرشفة لا بعدها.**

    وكان هذا العقد يقول «removable» — أي «أيجوز حذفُها؟». والحذفُ ذهب من
    المنتج، فذهب السؤال معه: الأرشفة تُخفي ولا تحذف، والاسترجاع يعيد. وما
    بقي سؤالٌ آخر — **«أيستوجب إخفاؤها إقرارًا صريحًا؟»** — ويستوجبه حين
    يتدلّى منها عملٌ حسمه إنسان.
    """

    thesis_id: uuid.UUID
    #: هل يتدلّى منها عملٌ حسمه إنسان، فيُطلب إقرارٌ صريح قبل الإخفاء.
    needs_acknowledgement: bool
    dependencies: list[RemovalDependency]
    #: ما يستوجب الإقرار بعينه، بأسمائه وأعداده.
    blocking: list[RemovalDependency]
    explanation: str
    #: نقلُ ملفّ المكتبة إلى السلّة فعلٌ آخر — ومعرّفُه هنا ليُطلب صراحةً.
    source_file_id: uuid.UUID | None = None
    archived: bool = False
    note_ar: str = (
        "الأرشفة تُخفي سجلّ مركز الرسائل ولا تحذف صفًّا واحدًا، ولا تمسّ ملفّ "
        "المكتبة، ولا يُمحى كائنُ التخزين نهائيًّا في أيّ حال."
    )
    note_en: str = (
        "Archiving hides the Thesis Center record and deletes not one row; it does not "
        "touch the library file, and no stored object is ever permanently deleted."
    )


class ArchiveRequest(BaseModel):
    """الإقرارُ بعد أن يُقال ما يترتّب — لا قبله.

    والافتراضُ `False`: إقرارٌ صامتٌ افتراضيّ يجعل السؤال زينة. (وهي القاعدة
    نفسها في `library.TrashRequest`.)
    """

    acknowledge: bool = False


class ArchiveResponse(BaseModel):
    thesis_id: uuid.UUID
    archived: bool
    archived_at: dt.datetime | None = None
    #: ما خرج من القائمة معها — **باقيًا كما هو**، لا محذوفًا.
    hidden: dict[str, int] = Field(default_factory=dict)
    acknowledged: bool = False
    #: **صفرٌ يُصرَّح به**: لا صفَّ يُحذف في هذا المسار، ولا كائنَ تخزين.
    rows_deleted: int = 0
    note_ar: str = "لم يُحذف شيء؛ الاسترجاع يعيد السجلّ كما كان."
    note_en: str = "Nothing was deleted; restoring returns the record exactly as it was."


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
    #: **مقترحاتٌ عُلِّقت لأنّ عنوان الرسالة لم يُستخرَج بعد** — ولا يُخترع
    #: لها عنوان. و«لم يُقترح» ليست «لا يوجد»، فيُقال العدد ومعه سببه.
    withheld_for_missing_title: int = 0
    title_note: str | None = None
    #: **ما اقترحه المنقّب ووُجد مثلُه قائمًا فلم يُكتب ثانيةً.** بدونه تُقرأ
    #: التشغيلة الثانية «٠ فرص» فيُظنّ أنّ المنقّب لم يجد شيئًا — وهو وجد
    #: ما كان موجودًا. والتنقيب مُعادٌ بلا أثر، لا مُلغًى.
    opportunities_already_present: int = 0
    #: مصدرُ الدليل: `canonical` معرفةٌ اعتمدها الباحث · `legacy` عناصرُ
    #: الاستخراج القديمة · `none` لا هذا ولا ذاك. **إضافةٌ متوافقة**: القيمة
    #: الافتراضية تحفظ سلوكَ المستهلكين القدامى.
    evidence_basis: str = "none"
    #: عددُ الحقائق التي اعتمدها الباحثُ وتحقّقت ذاكرتُها ودخلت الفحص.
    approved_facts_used: int = 0
    #: كلُّ ما كان مؤهَّلًا للتنقيب — **آليًّا كان أو معتمَدًا**. والسياسةُ
    #: الآن: الباحثُ يعتمد القراراتِ العلمية لا كلَّ استخراجٍ وسيط.
    eligible_facts_used: int = 0
    #: **محورٌ مستقلّ عن جودة الدليل.** رفضُ الباحثِ الإرسالَ الخارجي حالُ
    #: تشغيلٍ محترمة، لا فشلُ استخراجٍ يُعرض له.
    processing_scope: str = "unknown"
    #: تعارضٌ مادّيّ بين حقيقتين مؤهَّلتين في مفهومٍ واحد.
    conflicts_detected: int = 0
    #: ما حُجب لأجل ذلك التعارض — ويُحجب المفهومُ وحده لا الرسالة.
    facts_withheld_for_conflict: int = 0
    #: **حصيلةٌ تُقرأ، لا صفرٌ يُؤوَّل.** و`no_eligible_evidence` تقول «لا
    #: دليلَ مؤهَّل»، و`eligible_evidence_but_no_opportunity` تقول «فُحص
    #: دليلٌ مؤهَّل ولم تنشأ فرصة» — وكانتا رقمًا واحدًا.
    #:
    #: و`legacy_evidence_but_no_opportunity` ثالثةٌ لا تُخلط بهما: المادةُ
    #: القديمة استخراجٌ آليّ **لم يراجعه أحد**، فلا تُوصف بالمراجعة.
    #:
    #: و`evidence_withheld_for_conflict` رابعةٌ: حُجب مفهومٌ لتعارضٍ مادّيّ.
    #:
    #: **ولا قيمةَ افتراضية تسمّي حالًا لا تُصدرها الشيفرة**: افتراضٌ كهذا
    #: كذبةٌ صغيرة تنتظر أن تُقرأ حقيقةً في العقد.
    outcome: str = "no_eligible_evidence"
    #: **حالُ التنقيب نفسه** — مستقلّةٌ عن حال الاستخراج (ترحيل 0031).
    #: `not_started` · `running` · `completed` · `withheld` ·
    #: `no_eligible_evidence` · `failed`.
    mining_state: str = "not_started"
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
    #: **قرارُ الباحث، لا دورةُ الإنتاج**: `proposed` · `selected` ·
    #: `excluded`. والعمودان مُفرَدان عمدًا (§18)، ويُعرضان مفرَدَين.
    planning_status: str = "proposed"
    rights_approved: bool
    authorship_approved: bool
    #: **عددُ المراجع الحقيقية** التي يقوم عليها المقترح — لا نسبةٌ ولا درجة.
    #: يُعدّ ما هو مكتوبٌ في الصفّ، فصفرٌ هنا يعني مقترحًا بلا إسناد.
    provenance_count: int = 0


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


class JourneyResponse(BaseModel):
    """حالُ رحلة الرسالة — **حالٌ مسمّاة، ولا نسبةَ مئوية**.

    «٦٠٪ مكتمل» رقمٌ بلا قياسٍ خلفه يقرؤه الباحثُ وعدًا. وكلُّ حالٍ هنا
    واقعةٌ في القاعدة يمكن الإشارة إلى صفّها.
    """

    thesis_id: uuid.UUID
    state: str
    #: رموزٌ تقرؤها الآلةُ وتترجمها الشاشة — لا نثرٌ مترجَم في العقد.
    blocking_reasons: list[str] = []
    can_build_paper: bool = False
    #: الخيطُ الذهبيّ: واقعتُه، والفعلُ المتاح عليها — **فتعرفه الشاشة**.
    thread_ready: bool = False
    can_build_thread: bool = False
    opportunities: int = 0
    #: المفرداتُ المعلَنة، فتعرف الشاشةُ ما قد يصلها.
    states: list[str] = []


class BuildPaperResponse(BaseModel):
    """حصيلةُ بناء ورقة — **وما أُنشئ وما أُعيد استعمالُه، مسمَّيَين**."""

    project_id: uuid.UUID
    outline_id: uuid.UUID
    manuscript_id: uuid.UUID
    thread_id: uuid.UUID | None = None
    created: list[str] = []
    reused: list[str] = []
    #: ما لم يُبنَ بعد ويملكه طَورٌ لاحق — يُعلَن ولا يُدَّعى اكتمالُه.
    pending: list[str] = []
    state: str


class ThreadElementDraft(BaseModel):
    """عقدةٌ يقترحها النموذج — **ولا تدخل القاعدة قبل أن تُحلَّ مراجعُها**."""

    element_type: str
    label_ar: str
    evidence_refs: list[str] = []


class ThreadDraft(BaseModel):
    elements: list[ThreadElementDraft] = []


class SelectOpportunityRequest(BaseModel):
    """قرارُ الباحث في فرصة — **ولا يُقبل قرارٌ ثالثٌ صامتًا**.

    و`decision` لا قيمةَ افتراضية لها: اختيارٌ ضمنيّ ليس اختيارًا، وطلبٌ
    بلا قرارٍ صريح خطأٌ في النداء لا رأيٌ يُخمَّن.
    """

    decision: Literal["select", "exclude"]
    #: سببُ الباحث كما كتبه — يُحفظ في سلسلة التدقيق ولا يُعرض حكمًا.
    reason: str | None = None


class ThreadBuildResponse(BaseModel):
    """حصيلةُ بناء الخيط الذهبيّ — **وما رُفض يُعدّ ولا يُخفى**."""

    project_id: uuid.UUID
    created: int
    #: عقدٌ ردّها النظام لأنّ مراجعَ أدلّتها لا تردّ إلى صفوفٍ حقيقية.
    #: **عددٌ لا متن**: متنُ المرفوض اختلاقٌ لا يُحفظ ولا يُعرض.
    rejected: int
    context_fingerprint: str
    #: لا مُعرِّفَ نداءٍ حين لا نداء — وإعادةُ الاستعمال لا تنادي نموذجًا.
    agent_run_id: uuid.UUID | None = None
    #: **أُعيد استعمالُ خيطٍ قائم؟** يُقال ولا يُعرض بناءً لم يقع.
    reused: bool = False
