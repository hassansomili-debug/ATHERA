"""صندوق القرارات | Decision inbox (§9، §25، §38.5).

هذا الموجّه هو الوجه البشري للقيد السادس: بوابات الاعتماد لا يتجاوزها أجنت.
منطق البوابة نفسه في سير Temporal الدائم؛ وما هنا هو ما يراه الإنسان وما
يوقّع به — ولا شيء غير الإنسان يستطيع استدعاء `POST /decide`.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.audit import Approval, IntegrityAlert
from ..models.runs import Notification
from ..schemas.inbox import (
    AlertResolveRequest,
    ApprovalDecisionRequest,
    ApprovalResponse,
    InboxSummaryResponse,
    IntegrityAlertResponse,
    NotificationResponse,
)
from ..services import audit, inbox

router = APIRouter(prefix="/api/v1", tags=["inbox"])


def _pick(locale: str, arabic: str | None, english: str | None) -> str | None:
    return (english or arabic) if locale == "en" else (arabic or english)


def _approval(row: Approval, locale: str) -> ApprovalResponse:
    return ApprovalResponse(
        id=row.id, gate=row.gate, gate_label=inbox.gate_label(row.gate, locale),
        object_type=row.object_type, object_id=row.object_id, status=row.status,
        requested_by=row.requested_by, requested_at=row.created_at,
        decided_by=row.decided_by, decided_at=row.decided_at, reason=row.reason,
        workflow_id=row.workflow_id,
    )


@router.get("/approvals", response_model=list[ApprovalResponse])
async def list_approvals(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalResponse]:
    """§9 — الافتراض «المعلّقة» لأن الصندوق غرضه ما ينتظر قرارًا."""
    query = select(Approval).order_by(Approval.created_at.desc())
    if status != "all":
        query = query.where(Approval.status == status)
    rows = (await session.execute(query)).scalars().all()
    return [_approval(row, principal.locale) for row in rows]


@router.get("/approvals/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    row = (
        await session.execute(select(Approval).where(Approval.id == approval_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("inbox.approval_not_found")
    return _approval(row, principal.locale)


@router.post("/approvals/{approval_id}/decide", response_model=ApprovalResponse)
async def decide_approval(
    approval_id: uuid.UUID,
    payload: ApprovalDecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ApprovalResponse:
    """يسجّل قرار الإنسان ويرسل الإشارة إلى سير العمل المنتظر.

    الترتيب مقصود: تُكتب الحقيقة في قاعدتنا **قبل** إخطار Temporal. لو
    انعكس، لصار سير العمل قد مضى قدمًا بقرار لا أثر له في سجلنا.

    ولا مهلة تُسقط القرار: البوابة تنتظر إلى أجل غير مسمى (§9).
    """
    row = (
        await session.execute(select(Approval).where(Approval.id == approval_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("inbox.approval_not_found")
    try:
        inbox.check_decidable(row.status)
    except inbox.InboxError as exc:
        raise AtheraError("inbox.already_decided", status_code=422,
                          detail=str(exc)) from exc
    if row.requested_by == principal.user_id:
        # §28 — لا يبتّ الطالب في طلبه. الفصل بين الطلب والقرار هو ما يجعل
        # البوابة بوابةً لا خطوة إجرائية.
        raise AtheraError("inbox.self_approval_forbidden", status_code=403)

    row.status = "approved" if payload.approved else "rejected"
    row.decided_by = principal.user_id
    row.decided_at = dt.datetime.now(dt.UTC)
    row.reason = payload.reason

    await audit.record(
        session, tenant_id=principal.tenant_id, action="approval.decided",
        object_type=row.object_type, object_id=row.object_id,
        actor_user_id=principal.user_id, approval_id=row.id,
        state_after={"gate": row.gate, "approved": payload.approved},
        reason=payload.reason,
    )

    if row.workflow_id:
        from ..services import workflows

        # الإخطار لا يُبطل القرار إن تعذّر: القرار مكتوب، والسير يُستأنف لاحقًا.
        await workflows.signal_approval_decision(
            workflow_id=row.workflow_id, approved=payload.approved,
            decided_by=str(principal.user_id), reason=payload.reason,
        )
    return _approval(row, principal.locale)


@router.get("/integrity-alerts", response_model=list[IntegrityAlertResponse])
async def list_alerts(
    open_only: bool = Query(default=True),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[IntegrityAlertResponse]:
    query = select(IntegrityAlert).order_by(IntegrityAlert.created_at.desc())
    if open_only:
        query = query.where(IntegrityAlert.resolved_at.is_(None))
    rows = (await session.execute(query)).scalars().all()
    return [
        IntegrityAlertResponse(
            id=row.id, alert_type=row.alert_type, severity=row.severity,
            name=_pick(principal.locale, row.name_ar, row.name_en) or row.alert_type,
            detail=_pick(principal.locale, row.detail_ar, row.detail_en),
            object_type=row.object_type, object_id=row.object_id,
            resolved_at=row.resolved_at, raised_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/integrity-alerts/{alert_id}/resolve",
             response_model=IntegrityAlertResponse)
async def resolve_alert(
    alert_id: uuid.UUID,
    payload: AlertResolveRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> IntegrityAlertResponse:
    """§25 — التنبيه يُغلق بتبرير مكتوب، ولا يُحذف.

    لا مسار حذف هنا عمدًا: تنبيه نزاهة يختفي بلا أثر هو أسوأ ما يمكن أن
    يفعله سجل نزاهة.
    """
    row = (
        await session.execute(select(IntegrityAlert).where(IntegrityAlert.id == alert_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("inbox.alert_not_found")
    if row.resolved_at is not None:
        raise AtheraError("inbox.alert_already_resolved", status_code=422)

    row.resolved_at = dt.datetime.now(dt.UTC)
    row.detail_ar = f"{row.detail_ar or ''}\n[إغلاق] {payload.resolution_ar}".strip()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="integrity_alert.resolved",
        object_type="integrity_alert", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"alert_type": row.alert_type, "severity": row.severity},
        reason=payload.resolution_ar,
    )
    return IntegrityAlertResponse(
        id=row.id, alert_type=row.alert_type, severity=row.severity,
        name=_pick(principal.locale, row.name_ar, row.name_en) or row.alert_type,
        detail=_pick(principal.locale, row.detail_ar, row.detail_en),
        object_type=row.object_type, object_id=row.object_id,
        resolved_at=row.resolved_at, raised_at=row.created_at,
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[NotificationResponse]:
    rows = (
        await session.execute(
            select(Notification)
            .where(Notification.user_id == principal.user_id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    return [
        NotificationResponse(
            id=row.id, kind=row.kind,
            title=_pick(principal.locale, row.title_ar, row.title_en) or row.kind,
            body=_pick(principal.locale, row.body_ar, row.body_en),
            read_at=row.read_at, created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/notifications/{notification_id}/read",
             response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> NotificationResponse:
    row = (
        await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == principal.user_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("inbox.notification_not_found")
    if row.read_at is None:
        row.read_at = dt.datetime.now(dt.UTC)
    return NotificationResponse(
        id=row.id, kind=row.kind,
        title=_pick(principal.locale, row.title_ar, row.title_en) or row.kind,
        body=_pick(principal.locale, row.body_ar, row.body_en),
        read_at=row.read_at, created_at=row.created_at,
    )


@router.get("/inbox/summary", response_model=InboxSummaryResponse)
async def inbox_summary(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> InboxSummaryResponse:
    pending = (
        await session.execute(
            select(func.count()).select_from(Approval).where(Approval.status == "pending")
        )
    ).scalar_one()
    alerts = (
        await session.execute(
            select(IntegrityAlert.severity).where(IntegrityAlert.resolved_at.is_(None))
        )
    ).scalars().all()
    unread = (
        await session.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == principal.user_id,
                Notification.read_at.is_(None),
            )
        )
    ).scalar_one()
    return InboxSummaryResponse(
        pending_approvals=int(pending), open_alerts=len(alerts),
        blocking_alerts=sum(1 for severity in alerts if inbox.is_blocking(severity)),
        unread_notifications=int(unread),
    )
