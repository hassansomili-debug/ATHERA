"""عقود فريق المشروع | Project team contracts (§12، §24)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class MemberCreateRequest(BaseModel):
    """يسجّل مساهمًا **باسمه المعروض وحده** — ولا يربطه بحساب.

    وكان الحقل `user_id` هنا يُقبل من جسم الطلب، فكان أيُّ مصادَقٍ يربط
    عضوًا بأيِّ حساب في المستأجر: يكتب معرِّف زميله، فيصير الزميل عضوًا في
    بحثٍ لم يوافق على دخوله، ويُنسب إليه ما يُنسب إلى الأعضاء.

    فالربطُ بالحساب صار طريقًا واحدًا: دعوةٌ يقبلها صاحبُ الحساب بنفسه.
    وهذا المسار يبقى لمن يُذكر في الشكر والتقدير أو لمساهمٍ لا حساب له.
    """

    display_name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="co_author")
    credit_roles: list[str] = []


class MemberResponse(BaseModel):
    """حالُ عضوٍ كما تعرضه الشاشة — **بأربعة تمييزاتٍ لا تُطوى في واحد**.

    الدورُ، والصلاحياتُ، وإقراراتُ CRediT، وحالُ التأليف والموافقة — كلٌّ
    منها حقلٌ مستقلّ. وشاشةٌ تعرض «عضو» وحدها تجعل القارئ يفترض الأربعة.
    """

    id: uuid.UUID
    project_id: uuid.UUID
    display_name: str
    user_id: uuid.UUID | None
    # **مربوطٌ بحساب أو لا.** واسمٌ معروض بلا حساب ليس شريكًا يتعاون.
    is_account_linked: bool
    invited_email: str | None
    role: str
    role_label: str
    access_state: str
    access_label: str
    permissions: list[str]
    permission_labels: list[str]
    credit_roles: list[str]
    credit_labels: list[str]
    # ── التأليف والموافقة: منفصلان عن العضوية وعن بعضهما ──
    is_author: bool
    author_position: int | None
    consent_state: str
    consent_label: str
    consent_method: str | None
    consent_method_label: str | None
    consent_recorded_at: dt.datetime | None
    consent_recorded_by: uuid.UUID | None
    # **الموافقةُ القديمة تُعلَن مجهولةَ المصدر ولا تُعرض كأنها ذاتية.**
    consent_needs_recollection: bool


class InvitationCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=2, max_length=255)
    role: str = Field(default="co_author")
    # اقتراحُ صلاحيات؛ وغيابُه يعني افتراضَ الدور — لا «كلَّ شيء».
    permissions: list[str] | None = None


class InvitationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    invited_email: str
    invited_display_name: str
    proposed_role: str
    proposed_role_label: str
    proposed_permissions: list[str]
    state: str
    state_label: str
    expires_at: dt.datetime
    responded_at: dt.datetime | None
    accepted_user_id: uuid.UUID | None
    member_id: uuid.UUID | None


class IssuedInvitationResponse(InvitationResponse):
    """يحمل الرمز **مرّةً واحدة**، في ردّ الإنشاء وحده.

    ولا يُعاد في أيّ قراءةٍ بعدها، ولا يُخزَّن خامًا، ولا يُكتب في سجلّ.
    """

    token: str


class InvitationTokenRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class MemberRoleRequest(BaseModel):
    role: str


class MemberPermissionsRequest(BaseModel):
    permissions: list[str]


class MemberCreditRequest(BaseModel):
    """§24 — قائمةٌ يكتبها إنسان. لا حقل «اقترح لي» ولا «استنتج»."""

    credit_roles: list[str]


class AuthorshipDeclarationRequest(BaseModel):
    is_author: bool
    author_position: int | None = None


class SelfConsentRequest(BaseModel):
    """موافقةُ المؤلف على تأليفه — **ولا تحمل معرِّف عضوٍ آخر**.

    ولو حملته لصار الطلب «سجّل موافقة فلان»، وهو بالضبط ما أُصلح.
    """

    granted: bool = True


class ProxyConsentRequest(BaseModel):
    """المسارُ الإداري — **يلزمه سندٌ مكتوب**، وإلّا فهو الفراغ نفسه."""

    evidence_ar: str = Field(min_length=12, max_length=2000)


class MemberAccessRequest(BaseModel):
    access_state: str


class MemberEventResponse(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID | None
    invitation_id: uuid.UUID | None
    event_kind: str
    actor_user_id: uuid.UUID
    subject_user_id: uuid.UUID | None
    state_before: dict | None
    state_after: dict | None
    note_ar: str | None
    occurred_at: dt.datetime


class PendingActionResponse(BaseModel):
    """بندٌ **يحتاج فعلًا الآن** — لا واقعةً وقعت.

    وخلطُه بالسجلّ التاريخي يجعل الفريق يقرأ قائمةً واحدة لا يعرف أيُّ
    سطرٍ فيها ينتظره وأيُّها انتهى.
    """

    kind: str
    kind_label: str
    subject_id: uuid.UUID
    statement: str
    # لمن هذا البند: هذا الحساب، أم الفريق؟
    is_mine: bool
    blocking_since: dt.datetime | None


class DecisionCreateRequest(BaseModel):
    decision_kind: str
    statement_ar: str = Field(min_length=3)
    statement_en: str | None = None
    gate: str | None = None
    supersedes_id: uuid.UUID | None = None


class DecisionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    decision_kind: str
    kind_label: str
    statement: str
    gate: str | None
    approval_id: uuid.UUID | None
    decided_by: uuid.UUID | None
    decided_at: dt.datetime | None
    supersedes_id: uuid.UUID | None
    is_superseded: bool
    # **مقروءٌ صراحةً لا محسوبٌ في الشاشة.** فقارئُ السجلّ يحتاج أن يعرف
    # أيُّ قرارٍ هو القائم اليوم، **وأنّ ما قبله بقي مكتوبًا** ولم يُمحَ.
    is_current: bool
    superseded_by_id: uuid.UUID | None


class VocabularyResponse(BaseModel):
    """المفردات التي تحتاجها الواجهة لتبني قوائمها بلا تكرارها في الشاشة."""

    key: str
    label: str
