"""لوحة الإدارة — مخطّطاتُ الجواب | Admin Console V1 response schemas (Stage 9).

**كلُّ حقلٍ هنا بياناتُ تشغيلٍ لا محتوى بحث.** لا نصَّ ورقة، ولا نصَّ رسالةٍ
مستخرَجًا، ولا حمولةَ أداة، ولا مطالبةَ نموذجٍ ولا جوابَه، ولا نصَّ خطأٍ حرًّا.
ويحرس ذلك فحصٌ بنيويٌّ يقرأ هذه المخطّطات (`test_at_stage9_admin_console`):
لا اسمَ حقلٍ يشبه سرًّا أو حمولة.

**والنطاقُ مستأجرٌ واحد.** لا حقلَ يحمل بياناتِ مستأجرٍ آخر، ولا مخطّطَ لسياقٍ
عابرٍ للمستأجرين — ذاك تصميمٌ مؤمَّنٌ منفصلٌ في المرحلة ١٠.
"""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

# ═════════════════════════════ النظرة العامّة ═════════════════════════════


class AdminScope(BaseModel):
    """مساحةُ العمل الحاليّة — وحدَها. والمستأجرُ من الرمز لا من الطلب."""

    tenant_id: uuid.UUID
    tenant_name: str
    current_admin_roles: list[str]


class UserCounts(BaseModel):
    #: أشخاصٌ متمايزون لهم عضويّةٌ هنا — لا عددُ العضويّات (شخصٌ بثلاثة أدوار واحد).
    member_count: int
    #: منهم من حسابُه مفعَّل — والتفعيلُ صفةُ الحساب على المنصّة كلّها.
    active_identity_count: int
    #: منهم من سجّل الدخولَ إلى PUBRIVA خلال المدّة — **إلى أيّ مساحة عمل**:
    #: `last_login_at` صفةُ الحساب لا العضويّة. فلا يُسمّى «نشِطًا شهريًّا».
    signed_in_7d: int
    signed_in_30d: int


class ProjectCounts(BaseModel):
    #: غيرُ المحذوفة (`deleted_at` فارغ).
    total: int
    #: غيرُ المحذوفة وغيرُ المؤرشفة.
    active: int
    archived: int
    #: في سلّة المهملات (`deleted_at` مضبوط) — لا تدخل `total`.
    trashed: int


class FileCounts(BaseModel):
    #: غيرُ المرميّة في السلّة.
    total: int
    #: مجموعُ `size_bytes` لغير المرميّة — والعمودُ غيرُ فارغٍ في المخطّط.
    total_bytes: int
    trashed: int
    #: رفعٌ موقَّعٌ مسبقًا لم يُختَم بعد.
    pending: int


class ThesisCounts(BaseModel):
    total: int
    #: عددٌ لكلّ حالِ معالجةٍ قائمةٍ فعلًا في القيد `ck_theses_processing_state`.
    by_processing_state: dict[str, int]
    #: جاريةٌ منذ أطولَ من `STALE_AFTER` (حكمُ البيات نفسُه في B5).
    stalled: int


class ModelUsage(BaseModel):
    """تشغيلاتُ النموذج في المدّة — **من `model_runs` حرفًا**.

    والتكلفةُ **المسجَّلة** وحدَها: `cost_usd` الفارغُ يعني «لم تُسجَّل»، لا «صفر».
    فيُعرض دائمًا عددُ ما سُجّلت تكلفتُه وما لم تُسجَّل.
    """

    window_days: int
    model_runs: int
    succeeded: int
    failed: int
    #: نتيجةٌ لا تُعرف (B4) — لا نجاحٌ ولا فشل.
    ambiguous: int
    other_status: int
    input_tokens: int
    output_tokens: int
    recorded_cost_usd: Decimal
    runs_with_cost: int
    runs_without_cost: int


class OperationCounts(BaseModel):
    window_days: int
    failed_agent_runs: int
    blocked_agent_runs: int
    failed_model_runs: int
    ambiguous_model_runs: int
    failed_tool_runs: int
    denied_tool_runs: int
    #: رسائلُ حالُها `failed` أو `text_layer_missing` الآن — لا في المدّة.
    thesis_processing_failures: int


class AuditSummary(BaseModel):
    """آخرُ ما في سلسلة التدقيق — **بلا تحقّقٍ كاملٍ مع كلّ تحميل**."""

    latest_seq: int | None
    latest_at: dt.datetime | None


class AdminOverview(BaseModel):
    scope: AdminScope
    users: UserCounts
    projects: ProjectCounts
    files: FileCounts
    theses: ThesisCounts
    ai: ModelUsage
    operations: OperationCounts
    audit: AuditSummary


# ═════════════════════════════════ المستخدمون ═════════════════════════════════


class AdminUserRow(BaseModel):
    user_id: uuid.UUID
    display_name: str
    email: str
    preferred_locale: str
    is_active: bool
    last_login_at: dt.datetime | None
    #: أدوارُه في هذه المساحة وحدَها — بلا تكرارٍ ولا ترتيبٍ عشوائيّ.
    roles: list[str]
    member_since: dt.datetime
    #: بحوثٌ يملكها في هذه المساحة (غيرُ محذوفة).
    project_count: int
    #: ملفّاتٌ رفعها في هذه المساحة (غيرُ مرميّة).
    file_count: int
    #: تشغيلاتُ نموذجٍ **منسوبةٌ إليه** خلال ٣٠ يومًا — عبر `agent_runs.requested_by`.
    attributed_model_runs_30d: int


class AdminUserPage(BaseModel):
    items: list[AdminUserRow]
    next_cursor: str | None


class AdminProjectSummary(BaseModel):
    project_id: uuid.UUID
    title: str
    lifecycle: str
    created_at: dt.datetime


class AdminUserDetail(BaseModel):
    user: AdminUserRow
    #: أقدمُ عضويّةٍ وأحدثُها في هذه المساحة.
    first_membership_at: dt.datetime
    latest_membership_at: dt.datetime
    projects: list[AdminProjectSummary] = Field(default_factory=list)
    projects_truncated: bool
    file_bytes: int
    thesis_count: int
    ai_30d: ModelUsage
    latest_model_activity_at: dt.datetime | None
    #: تشغيلاتُ وكلاءَ طلبها خلال ٣٠ يومًا.
    agent_runs_30d: int


# ═════════════════════════════════ البحوث ═════════════════════════════════


class AdminProjectRow(BaseModel):
    project_id: uuid.UUID
    #: العنوانُ العاملُ وحدَه — **لا ملخّص ولا نصّ**.
    title: str
    status: str
    #: `active` | `archived` | `trashed` — من الطوابع، لا من `status`.
    lifecycle: str
    current_gate: str | None
    owner_user_id: uuid.UUID | None
    owner_name: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    collaborators: int
    files: int
    manuscripts: int


class AdminProjectPage(BaseModel):
    items: list[AdminProjectRow]
    next_cursor: str | None


# ═════════════════════════════ استخدام النموذج ═════════════════════════════


class UsageBucket(BaseModel):
    key: str
    model_runs: int
    failed: int
    input_tokens: int
    output_tokens: int
    recorded_cost_usd: Decimal
    runs_with_cost: int


class LatencySummary(BaseModel):
    #: تشغيلاتٌ سجّلت زمنها — والمتوسّطُ والوسيطُ عليها وحدَها.
    runs_with_latency: int
    average_ms: int | None
    median_ms: int | None


class AdminUsage(BaseModel):
    window_days: int
    summary: ModelUsage
    agent_runs: int
    tool_runs: int
    latency: LatencySummary
    by_day: list[UsageBucket]
    by_provider: list[UsageBucket]
    by_model: list[UsageBucket]
    by_status: list[UsageBucket]
    by_operation: list[UsageBucket]


# ═════════════════════════════════ العمليات ═════════════════════════════════


class OpAgentRun(BaseModel):
    run_id: uuid.UUID
    trace_id: uuid.UUID | None
    agent_key: str
    status: str
    gate: str | None
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    requested_by: uuid.UUID | None
    requested_by_name: str | None
    #: **حضورُ خطأٍ لا نصُّه** — `error` نصٌّ حرٌّ قد يحمل ما لا يُعرض.
    error_present: bool


class OpModelRun(BaseModel):
    run_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    provider: str
    model: str
    operation: str | None
    status: str
    latency_ms: int | None
    created_at: dt.datetime
    error_present: bool


class OpToolRun(BaseModel):
    run_id: uuid.UUID
    agent_run_id: uuid.UUID | None
    tool_key: str
    tool_kind: str | None
    status: str
    duration_ms: int | None
    created_at: dt.datetime
    error_present: bool


class OpThesis(BaseModel):
    thesis_id: uuid.UUID
    processing_state: str
    #: من مفرداتٍ مغلقةٍ في القاعدة (`ck_theses_failure_code_vocabulary`) — فهي آمنة.
    failure_code: str | None
    processing_state_changed_at: dt.datetime | None
    processing_attempts: int
    stalled: bool


class AdminOperations(BaseModel):
    view: str
    limit: int
    agent_runs: list[OpAgentRun]
    model_runs: list[OpModelRun]
    tool_runs: list[OpToolRun]
    theses: list[OpThesis]
