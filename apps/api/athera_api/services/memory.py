"""ترقية الذاكرة | Memory promotion (§7.4، §10.2، §43 TC-01).

المسار الوحيد الذي يحوّل مرشّح حقيقة إلى ذاكرة موثقة. لا يوجد باب آخر:
لا في الموجّهات، ولا في الأجنتات لاحقًا.

قاعدة §7.4 حرفيًا: لا يجوز تحويل مخرجات النموذج إلى Verified Memory
تلقائيًا. يلزم أحد الآتي — مصدر خارجي موثق، ملف مرفوع مع locator واضح،
نتيجة تشغيل تحليل فعلية، أو تأكيد صريح من الباحث.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, NotFound
from ..models.audit import ProvenanceEvent
from ..models.research import (
    MEMORY_CATEGORIES,
    PROMOTION_PATHS,
    DocumentChunk,
    FactCandidate,
    ResearcherMemory,
    ResearcherProfile,
    ResearcherSkill,
)
from . import audit
from .extraction.base import quote_is_grounded


class MemoryPromotionError(AtheraError):
    def __init__(self, code: str = "memory.promotion_denied", **context: object) -> None:
        super().__init__(code, status_code=422, **context)


# الحالات التي يجوز اتخاذ قرار جديد عليها (S5C §6).
#
# `unverified` لم تُراجَع بعد، و`unknown` راجعها الباحث ولم يستطع الحكم —
# فعودته إليها بحكمٍ صريح تقدُّمٌ لا تراجع. أما `approved` و`rejected` فحكمٌ
# قيل، ولا يُقلَب بنداءٍ ثانٍ صامت.
REVISABLE: Final = frozenset({"unverified", "unknown"})


def _require_revisable(candidate: FactCandidate) -> None:
    if candidate.status not in REVISABLE:
        raise MemoryPromotionError("memory.already_decided", status=candidate.status)


async def approve_candidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    candidate_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> ResearcherMemory:
    """اعتماد مرشّح → ذاكرة موثقة + provenance + تدقيق، في معاملة واحدة."""
    candidate = (
        await session.execute(select(FactCandidate).where(
            FactCandidate.id == candidate_id, FactCandidate.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFound("memory.candidate_not_found")
    _require_revisable(candidate)

    # إعادة التحقق من التأصيل عند الاعتماد، لا عند الاستخراج فقط: المقطع قد
    # يكون تغيّر، والاعتماد هو اللحظة التي تكتسب فيها المعلومة صفة رسمية.
    chunk = (
        await session.execute(select(DocumentChunk).where(
            DocumentChunk.id == candidate.chunk_id,
            DocumentChunk.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if chunk is None or not quote_is_grounded(candidate.quote, chunk.text):
        raise MemoryPromotionError("memory.quote_not_grounded", candidate_id=str(candidate_id))

    if candidate.memory_category not in MEMORY_CATEGORIES:
        raise MemoryPromotionError("memory.unknown_category", category=candidate.memory_category)

    # المسار: ملف مرفوع مع locator واضح + تأكيد صريح من الباحث (§7.4).
    source_type = "upload"
    if source_type not in PROMOTION_PATHS:  # pragma: no cover — حارس ضد تعديل لاحق
        raise MemoryPromotionError("memory.invalid_source_path", source_type=source_type)

    previous_status = candidate.status
    now = dt.datetime.now(dt.UTC)
    profile = (
        await session.execute(
            select(ResearcherProfile).where(ResearcherProfile.tenant_id == tenant_id)
        )
    ).scalars().first()

    memory = ResearcherMemory(
        tenant_id=tenant_id,
        profile_id=profile.id if profile else None,
        memory_category=candidate.memory_category,
        statement_ar=candidate.statement_ar,
        statement_en=candidate.statement_en,
        value=candidate.value,
        source_type=source_type,
        source_file_id=candidate.file_id,
        source_locator=candidate.locator,
        source_quote=candidate.quote,
        verification_status="verified",
        verified_by=actor_user_id,
        verified_at=now,
    )
    session.add(memory)
    await session.flush()

    candidate.status = "approved"
    candidate.decided_by = actor_user_id
    candidate.decided_at = now
    candidate.decision_reason = reason
    candidate.resulting_memory_id = memory.id

    # مهارة مشتقة: البرمجيات والمناهج تُغذّي ملف الباحث (§10.1) بمصدرها.
    if profile and candidate.field_key in {"software", "method"} and candidate.value:
        session.add(
            ResearcherSkill(
                tenant_id=tenant_id,
                profile_id=profile.id,
                skill_kind=candidate.value.get("skill_kind", "software"),
                name_ar=candidate.value.get("name", candidate.statement_ar)[:255],
                name_en=candidate.value.get("name"),
                evidence_level="document_verified",
                memory_id=memory.id,
            )
        )

    session.add(
        ProvenanceEvent(
            tenant_id=tenant_id,
            object_type="researcher_memory",
            object_id=memory.id,
            source_type=source_type,
            source_id=candidate.file_id,
            source_locator=candidate.locator,
            created_by=actor_user_id,
            verification_status="verified",
            verified_by=actor_user_id,
            verified_at=now,
            confidence=str(candidate.confidence) if candidate.confidence is not None else None,
        )
    )
    await audit.record(
        session,
        tenant_id=tenant_id,
        action="memory.fact_approved",
        object_type="researcher_memory",
        object_id=memory.id,
        actor_user_id=actor_user_id,
        state_before={"candidate_status": previous_status},
        state_after={
            "candidate_status": "approved",
            "memory_category": candidate.memory_category,
            "locator": candidate.locator,
        },
        reason=reason or "researcher approved extracted fact (G0)",
        source_refs=[{"file_id": str(candidate.file_id), "locator": candidate.locator}],
    )
    return memory


async def reject_candidate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    candidate_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> FactCandidate:
    """الرفض لا ينتج ذاكرة، لكنه يبقى مسجّلًا — الرفض معلومة أيضًا."""
    candidate = (
        await session.execute(select(FactCandidate).where(
            FactCandidate.id == candidate_id, FactCandidate.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFound("memory.candidate_not_found")
    _require_revisable(candidate)

    before = candidate.status
    candidate.status = "rejected"
    candidate.decided_by = actor_user_id
    candidate.decided_at = dt.datetime.now(dt.UTC)
    candidate.decision_reason = reason

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="memory.fact_rejected",
        object_type="fact_candidate",
        object_id=candidate.id,
        actor_user_id=actor_user_id,
        # الحالة السابقة كما كانت: «لا أعرف» ثم «مرفوض» مسارٌ مختلف عن
        # «غير مراجَع» ثم «مرفوض»، والسجل يحفظ الفرق.
        state_before={"status": before},
        state_after={"status": "rejected"},
        reason=reason,
    )
    return candidate


async def mark_candidate_unknown(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    candidate_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> FactCandidate:
    """«لا أعرف» قرارٌ ثالث — لا اعتماد ولا رفض (S5C §13).

    **ولماذا لا يكفي الرفض؟** لأن الرفض يقول «هذا خطأ»، و«لا أعرف» تقول
    «لا أستطيع الحكم». وخلطهما يفسد الإشارة: إعادة قراءة لاحقة تحتاج أن
    تميّز ما حكم عليه الباحث بالبطلان عمّا تركه معلّقًا.

    **والحالة أولى في العمود لا مشتقّة من `value`.** ترحيل 0016 وسّع
    `ck_candidate_status` ليقبل `unknown`، فلا يحتاج عميلٌ أن يستنتجها من
    `rejected` + علامة في JSON. والعمود هو المرجع.

    ولا ذاكرة تُنتَج منه — مثل الرفض تمامًا، ولنفس السبب: `verified` لا
    يُبلَغ إلا بتأكيد صريح عبر أحد مسارات §7.4. والقاعدة تحرسه أيضًا:
    `ck_candidate_memory_only_when_approved` يمنع `resulting_memory_id` على
    غير المعتمَد.

    **ولا نهاية له:** الباحث قد يعود فيحسم. `REVISABLE` تسمح بذلك صراحةً،
    ولا تسمح بقلب حكمٍ قيل.
    """
    candidate = (
        await session.execute(select(FactCandidate).where(
            FactCandidate.id == candidate_id, FactCandidate.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if candidate is None:
        raise NotFound("memory.candidate_not_found")
    _require_revisable(candidate)

    before = candidate.status
    candidate.status = "unknown"
    candidate.decided_by = actor_user_id
    candidate.decided_at = dt.datetime.now(dt.UTC)
    candidate.decision_reason = reason

    await audit.record(
        session,
        tenant_id=tenant_id,
        action="memory.fact_marked_unknown",
        object_type="fact_candidate",
        object_id=candidate.id,
        actor_user_id=actor_user_id,
        state_before={"status": before},
        state_after={"status": "unknown"},
        reason=reason,
    )
    return candidate


async def verified_memories(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    category: str | None = None,
    query: str | None = None,
    limit: int = 100,
) -> list[ResearcherMemory]:
    """الذاكرة الموثقة فقط. غير الموثق لا يُعرض هنا إطلاقًا (TC-01)."""
    statement = (
        select(ResearcherMemory)
        .where(ResearcherMemory.verification_status == "verified")
        .order_by(ResearcherMemory.created_at.desc())
        .limit(limit)
    )
    if category:
        statement = statement.where(ResearcherMemory.memory_category == category)
    if query:
        # بحث نصي بسيط: PostgreSQL بلا قاموس تجذير عربي، فلا ندّعي أكثر مما نملك.
        pattern = f"%{query}%"
        statement = statement.where(ResearcherMemory.statement_ar.ilike(pattern))
    return list((await session.execute(statement)).scalars().all())
