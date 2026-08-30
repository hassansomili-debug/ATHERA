"""سجل الأدوات | Tool registry (§7.1).

قاعدة السجل: **ما لا توجد له أداة لا يمكن أن يحدث.** لذلك لا تُسجَّل هنا
أداة تعدّل بيانات خامًا، ولا أداة تبتّ في اعتماد، ولا أداة تكتب ذاكرة
موثقة — تلك الثلاثة قرارات إنسان لا قدرات أجنت (§4، §17.2، §7.4).

كل أداة تعلن أثرها الجانبي صراحةً، ويرفض السجل تسجيل أداة كاتبة في
Sprint 2 (AT-S2-03).
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession

ToolHandler = Callable[..., Awaitable[Any]]

# مستويات الأثر الجانبي. Sprint 2 لا يسجّل إلا `read`.
SIDE_EFFECTS: Final = ("read", "write", "decide")

# أفعال محظورة على الأدوات مهما كان مستواها — حارس ضد توسعة لاحقة غافلة.
FORBIDDEN_CAPABILITIES: Final = frozenset({
    "mutate_raw_dataset",     # §17.2 — RAW غير قابل للتعديل
    "decide_approval",        # §9 — البوابة قرار إنسان
    "write_verified_memory",  # §7.4 — الترقية لا تمر بأجنت
    "submit_manuscript",      # §51.5 P14 — لا تقديم خارجي بلا فعل بشري
    "assign_authorship",      # §24.2 — التأليف قرار بشري
})


@dataclass(frozen=True, slots=True)
class ToolSpec:
    key: str
    name_ar: str
    name_en: str
    side_effect: str
    handler: ToolHandler
    # أعلى تصنيف بيانات تعيده هذه الأداة — يرفع تصنيف السياق كله.
    returns_classification: str = "C2"


class ToolRegistryError(RuntimeError):
    pass


_REGISTRY: dict[str, ToolSpec] = {}


def register(spec: ToolSpec) -> ToolSpec:
    if spec.side_effect not in SIDE_EFFECTS:
        raise ToolRegistryError(f"unknown side effect: {spec.side_effect}")
    if spec.side_effect != "read":
        # حارس صريح: أي أداة كاتبة تحتاج قرارًا معماريًا وسبرنتًا خاصًا بها.
        raise ToolRegistryError(
            f"tool '{spec.key}' declares side effect '{spec.side_effect}'; "
            "Sprint 2 registers read-only tools (see SPRINT2_PLAN §2)"
        )
    if spec.key in _REGISTRY:
        raise ToolRegistryError(f"duplicate tool key: {spec.key}")
    _REGISTRY[spec.key] = spec
    return spec


def get_tool(key: str) -> ToolSpec:
    if key not in _REGISTRY:
        raise ToolRegistryError(f"unknown tool: {key}")
    return _REGISTRY[key]


def all_tools() -> dict[str, ToolSpec]:
    return dict(_REGISTRY)


# ── الأدوات المتاحة في Sprint 2: قراءة فقط ──

async def _search_verified_memory(
    session: AsyncSession, *, tenant_id: uuid.UUID, query: str | None = None,
    category: str | None = None, limit: int = 20,
) -> list[dict]:
    """§7.3 — الذاكرة الموثقة وحدها. المرشّحات غير المتحققة لا تدخل السياق."""
    from ..services import memory as memory_service

    rows = await memory_service.verified_memories(
        session, tenant_id=tenant_id, category=category, query=query, limit=limit
    )
    return [
        {
            "id": str(row.id),
            "category": row.memory_category,
            "statement_ar": row.statement_ar,
            "statement_en": row.statement_en,
            "source_type": row.source_type,
            "source_locator": row.source_locator,
            "source_quote": row.source_quote,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        }
        for row in rows
    ]


async def _read_profile(session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    from sqlalchemy import select

    from ..models.research import ResearcherProfile

    profile = (
        await session.execute(
            select(ResearcherProfile).where(ResearcherProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if profile is None:
        return {}
    return {
        "institution_ar": profile.institution_ar,
        "institution_en": profile.institution_en,
        "current_rank": profile.current_rank,
        "target_rank": profile.target_rank,
        "primary_field_ar": profile.primary_field_ar,
        "orcid": profile.orcid,
        "g0_approved": profile.g0_approved_at is not None,
    }


async def _list_pending_facts(session: AsyncSession, *, tenant_id: uuid.UUID, limit: int = 50) -> list[dict]:
    """يعيد **عدّادًا ووصفًا** لا محتوى المرشّحات — حتى لا يتسرب غير المتحقق للسياق."""
    from sqlalchemy import func, select

    from ..models.research import FactCandidate

    count = (
        await session.execute(
            select(func.count()).select_from(FactCandidate).where(FactCandidate.status == "unverified")
        )
    ).scalar_one()
    return [{"pending_unverified_facts": count}]


register(ToolSpec(
    key="memory.search_verified",
    name_ar="بحث في الذاكرة الموثقة", name_en="Search verified memory",
    side_effect="read", handler=_search_verified_memory, returns_classification="C2",
))
register(ToolSpec(
    key="profile.read",
    name_ar="قراءة ملف الباحث", name_en="Read researcher profile",
    side_effect="read", handler=_read_profile, returns_classification="C2",
))
register(ToolSpec(
    key="facts.list_pending",
    name_ar="عدّ الحقائق المعلّقة", name_en="Count pending facts",
    side_effect="read", handler=_list_pending_facts, returns_classification="C1",
))
