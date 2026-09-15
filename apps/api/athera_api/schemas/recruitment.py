"""عقودُ الاستقطاب | RC-T1C recruitment API contracts.

**ولمَ خمسةُ نماذجٍ لا نموذجٌ واحد.**

جدولُ الإعلان والتطبيق يحمل ما يراه المدير وما يراه الغريب معًا. فنموذجٌ
واحدٌ يخدم الاثنين يجعل إضافةَ عمودٍ غدًا **تسريبًا صامتًا**: يُضاف
`project_id` إلى النموذج ليحتاجه المدير، فيخرج إلى الاكتشاف العالميّ ولا
ينبّه أحد.

فالفصلُ بنيويّ: `PublicOpportunity` **لا تملك الحقلَ أصلًا**، ولا تُبنى
إلّا من الأعمدة المُعلَنة. وحارسٌ ساكنٌ يقرأ حقولَها فيسقط إن دخلها اسمٌ
ممنوع — انظر `tests/test_at_rc_t1c_recruitment_api.py`.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

#: الحقولُ التي لا يجوز أن تُوجد في أيّ عقدٍ عامّ — يُقرأ في الحارس.
FORBIDDEN_PUBLIC_FIELDS: frozenset[str] = frozenset({
    "tenant_id", "project_id", "created_by", "profile_id",
    "applicant_user_id", "applicant_tenant_id",
})


class PublicOpportunity(BaseModel):
    """ما يراه باحثٌ في مؤسسةٍ أخرى — ولا شيءَ غيرُه.

    **ولا نسبَ فيه**: لا مستأجرَ ولا بحثًا ولا منشئًا ولا عنوانَ بحثٍ
    خاصّ. والانتماءُ يُعلَن بـ`public_label` إن كتبه صاحبُه.
    """

    opportunity_id: uuid.UUID
    title: str
    description: str
    contributions: str | None = None
    requirements: str | None = None
    specialization: str | None = None
    openings_count: int
    collaboration_type: str
    public_label: str | None = None
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None
    #: حالٌ مشتقّةٌ من الزمن لا مخزَّنة — انظر `services.recruitment.effective_status`.
    effective_status: str


class ManagerOpportunity(PublicOpportunity):
    """وما يراه مديرُ البحث: يزيد الحالَ المخزَّنة وعددَ المتقدّمين."""

    stored_status: str
    deleted_at: dt.datetime | None = None
    applications_count: int = 0
    created_at: dt.datetime


class OpportunityCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10)
    contributions: str | None = None
    requirements: str | None = None
    specialization: str | None = Field(default=None, max_length=120)
    openings_count: int = Field(default=1, ge=1, le=100)
    #: وسمُ تعاونٍ لا دورُ عضوية. و«مساعد بحث» افتراضُه.
    collaboration_type: str = Field(default="research_assistant", max_length=40)
    public_label: str | None = Field(default=None, max_length=160)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None


class OpportunityPatchRequest(BaseModel):
    """وما يُعدَّل — والخدمةُ تقرّر أيُّها جوهريٌّ بعد أوّل تقدُّم."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10)
    contributions: str | None = None
    requirements: str | None = None
    specialization: str | None = Field(default=None, max_length=120)
    openings_count: int | None = Field(default=None, ge=1, le=100)
    collaboration_type: str | None = Field(default=None, max_length=40)
    public_label: str | None = Field(default=None, max_length=160)
    starts_at: dt.datetime | None = None
    ends_at: dt.datetime | None = None


class ApplicationCreateRequest(BaseModel):
    """**ولا هويّةَ في الطلب.**

    فالمتقدّمُ هو صاحبُ الرمز الموقَّع، ولا حقلَ هنا يقبل حسابًا ولا
    مؤسسة — وحارسٌ ساكنٌ يُثبت ذلك.
    """

    message: str | None = Field(default=None, max_length=4000)


class LinkedInvitation(BaseModel):
    """حالُ الدعوة المرتبطة — **صادقةً لا متفائلة**.

    فحالُ التطبيق تبقى «مدعوّ» تاريخًا، والدعوةُ قد تكون انقضت أو نُقضت
    أو قُبلت. فتُعرض صلاحيتُها محسوبةً لا مستنتَجةً من حال التطبيق.
    """

    invitation_id: uuid.UUID
    state: str
    usable: bool
    expires_at: dt.datetime
    membership_created: bool


class MyApplication(BaseModel):
    """ما يراه صاحبُ التقدّم عن تقدُّمه هو."""

    application_id: uuid.UUID
    opportunity_id: uuid.UUID
    title: str
    status: str
    message: str | None = None
    submitted_at: dt.datetime
    decided_at: dt.datetime | None = None
    invitation: LinkedInvitation | None = None


class ManagerApplication(BaseModel):
    """وما يراه مديرُ الفرصة — ما يلزم للاختيار، لا أكثر.

    **ولا مؤسسةَ المتقدّم ولا معرّفُ حسابه**: الاختيارُ يقع على التطبيق،
    والخدمةُ تشتقّ الحسابَ في الخادم.
    """

    application_id: uuid.UUID
    display_name: str
    status: str
    message: str | None = None
    submitted_at: dt.datetime
    decided_at: dt.datetime | None = None
    invitation: LinkedInvitation | None = None


class InviteRequest(BaseModel):
    """**ولا هويّةَ هنا كذلك**: المديرُ يختار دورًا وصلاحيات، لا شخصًا."""

    role: str = Field(max_length=32)
    permissions: list[str] = Field(min_length=1)
    ttl_hours: int | None = Field(default=None, ge=1, le=24 * 60)


class RecruitmentInvitationResponse(BaseModel):
    """جوابُ التحويل — ويحمل الرمزَ **مرّةً واحدة**.

    ولا سبيلَ لتسليم الرموز في هذه النسخة (لا بريدَ ولا إشعار)، فيُعاد
    إلى المدير الذي أصدره ليُسلّمه بنفسه — وهو سلوكُ دعوات الفريق القائم.
    **ولا يُخزَّن خامًّا ولا يُكتب في سجلّ ولا يعود من أيّ قراءة.**
    """

    application_id: uuid.UUID
    application_status: str
    invitation_id: uuid.UUID
    invitation_state: str
    role: str
    permissions: list[str]
    expires_at: dt.datetime
    token: str


__all__ = [
    "FORBIDDEN_PUBLIC_FIELDS",
    "ApplicationCreateRequest",
    "InviteRequest",
    "LinkedInvitation",
    "ManagerApplication",
    "ManagerOpportunity",
    "MyApplication",
    "OpportunityCreateRequest",
    "OpportunityPatchRequest",
    "PublicOpportunity",
    "RecruitmentInvitationResponse",
]
