"""عقود صندوق القرارات | Decision inbox contracts (§9، §25، §38.5)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    """طلب اعتماد معلّق أو محسوم. لا حقل «ينتهي في»: البوابة لا تسقط بالوقت."""

    id: uuid.UUID
    gate: str
    gate_label: str
    object_type: str
    object_id: uuid.UUID
    status: str
    requested_by: uuid.UUID
    requested_at: dt.datetime
    decided_by: uuid.UUID | None
    decided_at: dt.datetime | None
    reason: str | None
    workflow_id: str | None


class ApprovalDecisionRequest(BaseModel):
    """§9 — القرار فعل إنسان له سبب. الرفض يحتاج سببًا كما الاعتماد."""

    approved: bool
    reason: str = Field(min_length=3, max_length=2000)


class IntegrityAlertResponse(BaseModel):
    id: uuid.UUID
    alert_type: str
    severity: str
    name: str
    detail: str | None
    object_type: str | None
    object_id: uuid.UUID | None
    resolved_at: dt.datetime | None
    raised_at: dt.datetime


class AlertResolveRequest(BaseModel):
    """§25 — التنبيه يُغلق بقرار مبرَّر، لا بإخفائه."""

    resolution_ar: str = Field(min_length=3, max_length=2000)


class NotificationResponse(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str | None
    read_at: dt.datetime | None
    created_at: dt.datetime


class InboxSummaryResponse(BaseModel):
    """العدّادات التي تحملها القائمة الجانبية.

    الاعتمادات المعلّقة والتنبيهات غير المُغلقة **لا تُجمع في رقم واحد**:
    الأول انتظار قرار، والثاني إخفاق مرصود. جمعهما يخفي أيّهما يحتاج تدخلًا.
    """

    pending_approvals: int
    open_alerts: int
    blocking_alerts: int
    unread_notifications: int
