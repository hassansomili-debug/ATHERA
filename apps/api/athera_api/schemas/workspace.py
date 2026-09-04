"""عقود مساحة عمل البحث | Project workspace contracts (PUBRIVA)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from ..models.screening import EXCLUSION_REASON_CODES

# النمط يُشتقّ من السجل ولا يُكتب بجانبه: قائمتان تفترقان بأول إضافة، فيقبل
# العقد رمزًا يرفضه القيد — أو يرفض رمزًا تعرضه الشاشة، وهو أسوأ.
REASON_CODE_PATTERN = "^(" + "|".join(EXCLUSION_REASON_CODES) + ")$"


class ProjectCreateRequest(BaseModel):
    """إنشاء بحث — **بأقلّ ما يلزم**.

    والباحث يبدأ بفكرة لا باستمارة: العنوان وحده يكفي، وبقيّة الحقول تُملأ
    حين تُعرف. واشتراطُ منهجٍ ونوع دراسة قبل أن يبدأ يوقفه عند الباب.
    """

    title_ar: str = Field(min_length=3, max_length=500)
    # من أين يبدأ: فكرة · مستند · بيانات · مخطوطة قائمة · فارغ
    starting_from: str = Field(
        default="idea", pattern="^(idea|document|dataset|manuscript|empty)$")


class ProjectRenameRequest(BaseModel):
    title_ar: str = Field(min_length=3, max_length=500)


class ProjectSummary(BaseModel):
    id: uuid.UUID
    title_ar: str
    status: str
    created_at: dt.datetime
    archived_at: dt.datetime | None = None
    deleted_at: dt.datetime | None = None
    files: int = 0
    sources: int = 0
    verified_facts: int = 0
    manuscripts: int = 0


class BrainEntryView(BaseModel):
    key: str
    label: str
    state: str = Field(description="known | needs_review | missing | conflicting")
    value: str | None = None
    sources: int = 0


class NextAction(BaseModel):
    key: str
    label: str


class ProjectOverview(BaseModel):
    project: ProjectSummary
    brain: list[BrainEntryView]
    recommended_next: NextAction | None = None
    blockers: list[str] = Field(default_factory=list)
    note: str


class ProjectFileView(BaseModel):
    file_id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    added_at: dt.datetime
    state: str
    processing_status: str = "not_processed"
    thesis_id: uuid.UUID | None = None
    candidates: int = 0
    reviewed: int = 0


class ProjectSourceView(BaseModel):
    source_id: uuid.UUID
    title: str
    doi: str | None = None
    publication_year: int | None = None
    use_state: str = Field(description="included | saved_only | excluded")
    added_at: dt.datetime
    decided_at: dt.datetime | None = None
    # سببُ الاستبعاد يُعاد مع الصفّ: حالٌ بلا سببها تُعرض حكمًا بلا تعليل،
    # فيقرأ الباحث «مستبعَدة» ولا يعرف لماذا — وهو ما يمنعه الترحيل 0023.
    exclusion_reason_code: str | None = None
    reason_ar: str | None = None


class LinkRequest(BaseModel):
    """ربط أصلٍ من المكتبة العامة بهذا البحث — بلا نسخ."""

    asset_id: uuid.UUID


class SourceUseRequest(BaseModel):
    """قرارُ الفرز — **مسارٌ واحد لا مساران**.

    شاشةُ الفرز وقائمةُ مراجع البحث تكتبان هنا كلتاهما: حالُ الاستعمال حقٌّ
    واحد في `project_sources`، ومسارٌ ثانٍ يكتبها كان سيصنع حقيقتين تفترقان
    — واحدةٌ تشترط سبب الاستبعاد وأخرى لا تشترطه.

    **والاستبعاد وحده يلزمه سبب.** أما «مُدرَج» و«محفوظ فقط» فلا: اشتراطُ
    تبريرٍ لكل قرار يجعل الباحث يكتب أيّ شيء ليمضي، فيصير الحقل ضجيجًا
    يُلغي قيمة السبب حيث يلزم فعلًا.
    """

    use_state: str = Field(pattern="^(included|saved_only|excluded)$")
    # رمزٌ من قائمةٍ مغلقة — يُعدّ ويُقارن ويُكتب منه قسم المنهجية.
    reason_code: str | None = Field(default=None, pattern=REASON_CODE_PATTERN)
    # النصّ الحرّ يرافق «سبب آخر» ويكون اختياريًّا مع غيره.
    reason_ar: str | None = Field(default=None, max_length=1000)


class ImpactView(BaseModel):
    """ما يترتب على الإزالة — **قبل أن تقع**."""

    is_safe: bool
    breaks_approved_work: bool
    summary: str
    consequences: list[dict] = Field(default_factory=list)


__all__ = ["BrainEntryView", "ImpactView", "LinkRequest", "NextAction",
           "ProjectCreateRequest", "ProjectFileView", "ProjectOverview",
           "ProjectRenameRequest", "ProjectSourceView", "ProjectSummary",
           "SourceUseRequest"]
