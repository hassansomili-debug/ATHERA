"""سجل الادعاء-الدليل | Claim-to-Evidence Ledger (§14.4، §14.5، §43 TC-02).

القواعد الثلاث في §14.5 مطبَّقة هنا كقرارات لا كنصائح:

  1. المرجع غير المتحقق لا يدخل النسخة النهائية.
  2. لا استشهاد ببحث مسحوب دون تحذير وسياق واضح.
  3. لا تُستخدم Metadata-only كمصدر لتفاصيل لم تُتحقق من النص.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.literature import (
    SUPPORT_LEVELS,
    TEXT_BEARING_STATES,
    Claim,
    ClaimEvidenceLink,
    EvidenceExcerpt,
    Source,
)
from .. import audit

SUPPORTING_LEVELS = ("direct", "partial")


class LedgerError(AtheraError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code, status_code=422, **context)


@dataclass(slots=True)
class ClaimStatus:
    """حالة ادعاء كما يراها السجل — لا رقم واحد يخفي مشكلة."""

    claim_id: uuid.UUID
    status: str
    direct: int
    partial: int
    contextual: int
    contradictory: int
    unresolved_contradictions: int
    retracted_sources: int
    has_evidence_gap: bool

    @property
    def can_be_final(self) -> bool:
        return (
            (self.direct + self.partial) > 0
            and self.unresolved_contradictions == 0
            and not self.has_evidence_gap
        )


async def add_excerpt(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
    quote: str,
    locator: str,
    actor_user_id: uuid.UUID,
    chunk_id: uuid.UUID | None = None,
) -> EvidenceExcerpt:
    """§14.5 القاعدة 3 — لا مقتطف من مصدر لم يُتَح نصه."""
    source = (await session.execute(select(Source).where(Source.id == source_id))).scalar_one_or_none()
    if source is None:
        raise NotFound("evidence.source_not_found")
    if source.access_state not in TEXT_BEARING_STATES:
        raise LedgerError(
            "evidence.no_text_access", source_id=str(source_id), access_state=source.access_state
        )
    if source.verification_status != "verified":
        # §14.5 القاعدة 1 — المصدر غير المتحقق لا يُبنى عليه دليل.
        raise LedgerError("evidence.source_not_verified", source_id=str(source_id))

    excerpt = EvidenceExcerpt(
        tenant_id=tenant_id, source_id=source_id, quote=quote, locator=locator,
        access_basis=source.access_state, chunk_id=chunk_id, created_by=actor_user_id,
    )
    session.add(excerpt)
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id, action="evidence.excerpt_added",
        object_type="evidence_excerpt", object_id=excerpt.id, actor_user_id=actor_user_id,
        state_after={"source_id": str(source_id), "access_basis": source.access_state},
        source_refs=[{"source_id": str(source_id), "locator": locator}],
    )
    return excerpt


async def link_evidence(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    excerpt_id: uuid.UUID,
    support_level: str,
    actor_user_id: uuid.UUID,
    retraction_acknowledged: bool = False,
    acknowledgement_note: str | None = None,
) -> ClaimEvidenceLink:
    if support_level not in SUPPORT_LEVELS:
        raise LedgerError("evidence.unknown_support_level", support_level=support_level)

    claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise NotFound("evidence.claim_not_found")
    excerpt = (
        await session.execute(select(EvidenceExcerpt).where(EvidenceExcerpt.id == excerpt_id))
    ).scalar_one_or_none()
    if excerpt is None:
        raise NotFound("evidence.excerpt_not_found")
    source = (await session.execute(select(Source).where(Source.id == excerpt.source_id))).scalar_one()

    # §14.5 القاعدة 2 — المسحوب يحتاج إقرارًا صريحًا، لا منعًا مطلقًا.
    if source.retraction_status in ("retracted", "expression_of_concern"):
        if not retraction_acknowledged or not (acknowledgement_note or "").strip():
            raise LedgerError(
                "evidence.retraction_needs_acknowledgement",
                source_id=str(source.id), retraction_status=source.retraction_status,
            )

    link = ClaimEvidenceLink(
        tenant_id=tenant_id, claim_id=claim_id, excerpt_id=excerpt_id, source_id=source.id,
        support_level=support_level, retraction_acknowledged=retraction_acknowledged,
        acknowledgement_note=acknowledgement_note, reviewed_by=actor_user_id,
    )
    session.add(link)
    await session.flush()

    await audit.record(
        session, tenant_id=tenant_id, action="evidence.linked_to_claim",
        object_type="claim", object_id=claim_id, actor_user_id=actor_user_id,
        state_after={
            "support_level": support_level, "source_id": str(source.id),
            "retraction_status": source.retraction_status,
            "retraction_acknowledged": retraction_acknowledged,
        },
        source_refs=[{"source_id": str(source.id), "locator": excerpt.locator}],
    )
    return link


async def claim_status(
    session: AsyncSession, *, tenant_id: uuid.UUID, claim_id: uuid.UUID
) -> ClaimStatus:
    """يحسب حالة الادعاء من أدلته — ويُظهر المناقض بدل إخفائه (§14.4)."""
    rows = (
        await session.execute(
            select(ClaimEvidenceLink, Source)
            .join(Source, Source.id == ClaimEvidenceLink.source_id)
            .where(ClaimEvidenceLink.claim_id == claim_id)
        )
    ).all()

    counts = {level: 0 for level in SUPPORT_LEVELS}
    unresolved = 0
    retracted = 0
    for link, source in rows:
        counts[link.support_level] = counts.get(link.support_level, 0) + 1
        if link.support_level == "contradictory" and not (link.resolution_note_ar or "").strip():
            unresolved += 1
        if source.retraction_status in ("retracted", "expression_of_concern"):
            retracted += 1

    supporting = counts["direct"] + counts["partial"]
    has_gap = supporting == 0

    if has_gap:
        status = "evidence_gap"
    elif unresolved:
        status = "contradicted"
    else:
        status = "supported"

    return ClaimStatus(
        claim_id=claim_id, status=status,
        direct=counts["direct"], partial=counts["partial"],
        contextual=counts["contextual"], contradictory=counts["contradictory"],
        unresolved_contradictions=unresolved, retracted_sources=retracted,
        has_evidence_gap=has_gap,
    )


async def finalize_claim(
    session: AsyncSession, *, tenant_id: uuid.UUID, claim_id: uuid.UUID, actor_user_id: uuid.UUID
) -> Claim:
    """§14.5 القاعدة 1 — الإغلاق ممنوع بلا دليل داعم أو مع مناقض غير معالج.

    TC-02: البديل عن المرجع المختلق هو **إعلان فجوة**، لا توليد مرجع.
    """
    claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one_or_none()
    if claim is None:
        raise NotFound("evidence.claim_not_found")

    status = await claim_status(session, tenant_id=tenant_id, claim_id=claim_id)
    if not status.can_be_final:
        claim.status = status.status
        await audit.record(
            session, tenant_id=tenant_id, action="evidence.claim_finalization_refused",
            object_type="claim", object_id=claim_id, actor_user_id=actor_user_id,
            state_after={
                "status": status.status, "direct": status.direct, "partial": status.partial,
                "unresolved_contradictions": status.unresolved_contradictions,
            },
            reason="claim cannot be final without supporting evidence (§14.5, TC-02)",
        )
        raise LedgerError(
            "evidence.claim_has_gap" if status.has_evidence_gap else "evidence.claim_contradicted",
            claim_id=str(claim_id),
        )

    claim.status = "final"
    claim.verification_status = "verified"
    claim.reviewed_by = actor_user_id
    claim.reviewed_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=tenant_id, action="evidence.claim_finalized",
        object_type="claim", object_id=claim_id, actor_user_id=actor_user_id,
        state_after={"direct": status.direct, "partial": status.partial,
                     "contextual": status.contextual, "retracted_sources": status.retracted_sources},
        reason="researcher confirmed the claim is supported by verified evidence",
    )
    return claim
