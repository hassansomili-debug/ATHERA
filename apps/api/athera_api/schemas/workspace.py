"""عقود مساحة عمل البحث | Project workspace contracts (PUBRIVA)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


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


class LinkRequest(BaseModel):
    """ربط أصلٍ من المكتبة العامة بهذا البحث — بلا نسخ."""

    asset_id: uuid.UUID


class SourceUseRequest(BaseModel):
    use_state: str = Field(pattern="^(included|saved_only|excluded)$")
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
