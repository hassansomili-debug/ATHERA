"""الذاكرة الموثقة | Verified memory (§7.3، §43 TC-01).

لا يعرض هذا الموجّه إلا ما حالته `verified`. المرشّحات غير المتحققة لها
مسارها الخاص في `/profile/facts` — الخلط بينهما هو بالضبط ما يمنعه TC-01.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..models.research import MEMORY_CATEGORIES
from ..schemas.profile import MemoryResponse
from ..services import memory as memory_service

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("", response_model=list[MemoryResponse])
async def list_memory(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, le=300),
) -> list[MemoryResponse]:
    rows = await memory_service.verified_memories(
        session, tenant_id=principal.tenant_id, category=category, query=q, limit=limit
    )
    return [
        MemoryResponse(
            id=row.id,
            memory_category=row.memory_category,
            statement=(row.statement_en or row.statement_ar)
            if principal.locale == "en"
            else row.statement_ar,
            statement_ar=row.statement_ar,
            statement_en=row.statement_en,
            value=row.value,
            source_type=row.source_type,
            source_locator=row.source_locator,
            source_quote=row.source_quote,
            verification_status=row.verification_status,
            verified_at=row.verified_at,
        )
        for row in rows
    ]


@router.get("/categories", response_model=dict[str, str])
async def list_categories(principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """§7.3 — الفئات الثماني ومستوى التحقق المطلوب لكل واحدة."""
    return dict(MEMORY_CATEGORIES)
