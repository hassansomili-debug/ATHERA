"""قراءة سجل التدقيق | Audit read API (§37).

للقراءة فقط: لا يوجد PATCH ولا DELETE في هذا الموجّه، وقاعدة البيانات
تمنعهما أصلًا حتى لو أُضيفا سهوًا (ترحيل 0002).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_session, require_roles
from ..models.audit import AuditEvent
from ..schemas.audit import AuditEventResponse, ChainVerificationResponse
from ..services import audit

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])

_admin = require_roles("research_admin", "college_admin", "institution_admin", "system_admin")


@router.get("/events", response_model=list[AuditEventResponse])
async def list_events(
    principal: Principal = Depends(_admin),
    session: AsyncSession = Depends(get_session),
    object_type: str | None = Query(default=None),
    object_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[AuditEventResponse]:
    query = select(AuditEvent).order_by(AuditEvent.chain_seq.desc()).limit(limit)
    if object_type:
        query = query.where(AuditEvent.object_type == object_type)
    if object_id:
        query = query.where(AuditEvent.object_id == object_id)
    rows = (await session.execute(query)).scalars().all()
    return [AuditEventResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/chain/verify", response_model=ChainVerificationResponse)
async def verify_chain(
    principal: Principal = Depends(_admin),
    session: AsyncSession = Depends(get_session),
) -> ChainVerificationResponse:
    intact, broken_at = await audit.verify_chain(session, principal.tenant_id)
    total = await audit.count_for_tenant(session, principal.tenant_id)
    return ChainVerificationResponse(intact=intact, broken_at_seq=broken_at, events_checked=total)
