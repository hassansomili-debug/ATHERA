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


class ThesisCardActions(BaseModel):
    """ما تعرضه البطاقة — **والشاشة لا تجتهد، بل تعرض ما يقوله الخادم**.

    كان كلُّ شرطٍ منها مكتوبًا في JSX على حدة، فافترقت الشاشة عن الخادم:
    زرُّ «تفكيك الرسالة» يُعرض دائمًا وإن ردّت النقطة `thesis.no_file`، وزرُّ
    «استخراج الفرص» مشروطٌ بـ`parsed_at` الذي لا يضعه إلّا مسارٌ قديم.
    """

    #: الفعل الأول على البطاقة: review · process · reprocess · attach_file · None
    primary: str | None = None
    #: عملٌ يجري الآن — فلا فعلَ يُعرض، ويُعرض ما يجري.
    in_progress: bool = False

    can_review: bool = False
    can_process: bool = False
    can_reprocess: bool = False
    #: **المسار القديم باقٍ في الواجهة البرمجية ومسحوبٌ من البطاقة.**
    can_parse: bool = False
    can_attach_file: bool = False
    can_mine: bool = False
    can_remove: bool = True
    can_trash_file: bool = False

    #: available · in_flight · no_evidence
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
    """**ما يقوم على الرسالة، قبل الإزالة لا بعدها.**"""

    thesis_id: uuid.UUID
    removable: bool
    dependencies: list[RemovalDependency]
    blocking: list[RemovalDependency]
    explanation: str
    #: نقلُ ملفّ المكتبة إلى السلّة فعلٌ آخر — ومعرّفُه هنا ليُطلب صراحةً.
    source_file_id: uuid.UUID | None = None
    note_ar: str = (
        "الإزالة تُسقط سجلّ مركز الرسائل ولا تمسّ ملفّ المكتبة، "
        "ولا يُمحى كائنُ التخزين نهائيًّا في أيّ حال."
    )
    note_en: str = (
        "Removal drops the Thesis Center record and does not touch the library file; "
        "no stored object is ever permanently deleted."
    )


class RemovalResponse(BaseModel):
    thesis_id: uuid.UUID
    removed: bool
    #: ما أُسقط معها من مخرجات الآلة — يُقال بالعدد لا يُترك يُخمَّن.
    dropped: dict[str, int]
    audit_preserved: bool = True
    note_ar: str = "سجلّ التدقيق يبقى كاملًا بعد الإزالة."
    note_en: str = "The audit history stays complete after removal."


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
    #: **ما اقترحه المنقّب ووُجد مثلُه قائمًا فلم يُكتب ثانيةً.** بدونه تُقرأ
    #: التشغيلة الثانية «٠ فرص» فيُظنّ أنّ المنقّب لم يجد شيئًا — وهو وجد
    #: ما كان موجودًا. والتنقيب مُعادٌ بلا أثر، لا مُلغًى.
    opportunities_already_present: int = 0
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
