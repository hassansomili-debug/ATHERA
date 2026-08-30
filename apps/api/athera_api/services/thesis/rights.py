"""بوابة الحقوق والتأليف GT1 | Rights and authorship gate (§23.9، §24، TC-06).

القاعدة الحرفية من §23.9: «لا يسمح النظام بوضع المشروع في Ready to Submit
إذا لم تُعتمد الحقوق والتأليف».

وTC-06 يضيف تمييزًا مهمًا: **التحليل الداخلي مسموح** بلا حقوق. المنع على
التقدم لا على الفهم — الباحث يستطيع أن يعرف إن كانت الفرصة تستحق قبل أن
يسعى إلى الموافقات.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...errors import AtheraError, NotFound
from ...models.thesis import (
    AuthorshipAgreement,
    AuthorshipParty,
    PublicationOpportunity,
    Thesis,
    ThesisOwner,
)
from .. import audit
from .vocab import AUTHORSHIP_PARTY_KINDS, CREDIT_ROLES, RIGHTS_BASES

# الحالات التي يسمح فيها بالتحليل بلا حقوق (TC-06).
ANALYSIS_ONLY_STATUSES = ("discovered", "analysed", "rights_pending")


class RightsGateError(AtheraError):
    def __init__(self, code: str, **context: object) -> None:
        super().__init__(code, status_code=422, **context)


@dataclass(slots=True)
class GateStatus:
    """حالة بوابة GT1 — تفصيل لا نعم/لا."""

    opportunity_id: uuid.UUID
    rights_basis: str | None
    rights_approved: bool
    owner_consent_recorded: bool
    authors_total: int
    authors_consented: int
    authorship_approved: bool
    blockers: list[str] = field(default_factory=list)

    @property
    def can_be_ready_to_submit(self) -> bool:
        return self.rights_approved and self.authorship_approved and not self.blockers


async def gate_status(
    session: AsyncSession, *, tenant_id: uuid.UUID, opportunity_id: uuid.UUID
) -> GateStatus:
    opportunity = (
        await session.execute(
            select(PublicationOpportunity).where(PublicationOpportunity.id == opportunity_id)
        )
    ).scalar_one_or_none()
    if opportunity is None:
        raise NotFound("thesis.opportunity_not_found")

    thesis = (
        await session.execute(select(Thesis).where(Thesis.id == opportunity.thesis_id))
    ).scalar_one()
    owners = (
        await session.execute(select(ThesisOwner).where(ThesisOwner.thesis_id == thesis.id))
    ).scalars().all()
    agreements = (
        await session.execute(
            select(AuthorshipAgreement)
            .where(AuthorshipAgreement.opportunity_id == opportunity_id)
        )
    ).scalars().all()

    blockers: list[str] = []
    if thesis.rights_basis is None:
        blockers.append("rights_basis_missing")
    elif thesis.rights_basis not in RIGHTS_BASES:
        blockers.append("rights_basis_unknown")

    owner_consent = bool(owners) and all(o.consent_recorded_at is not None for o in owners)
    # §23.2 — المشرف يحتاج موافقة صاحب الرسالة صراحةً.
    if thesis.rights_basis == "supervisor_with_consent" and not owner_consent:
        blockers.append("owner_consent_missing")

    if not agreements:
        blockers.append("no_authors_declared")
    consented = sum(1 for a in agreements if a.consent_status == "granted")
    if agreements and consented != len(agreements):
        blockers.append("author_consent_incomplete")

    positions = sorted(a.author_position for a in agreements)
    if positions and positions != list(range(1, len(positions) + 1)):
        blockers.append("author_order_invalid")
    if agreements and not any(a.is_corresponding for a in agreements):
        blockers.append("corresponding_author_missing")

    return GateStatus(
        opportunity_id=opportunity_id,
        rights_basis=thesis.rights_basis,
        rights_approved=opportunity.rights_approved_at is not None,
        owner_consent_recorded=owner_consent,
        authors_total=len(agreements),
        authors_consented=consented,
        authorship_approved=opportunity.authorship_approved_at is not None,
        blockers=blockers,
    )


async def add_author(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    party_kind: str,
    display_name: str,
    author_position: int,
    actor_user_id: uuid.UUID,
    is_corresponding: bool = False,
    user_id: uuid.UUID | None = None,
    credit_roles: list[str] | None = None,
) -> AuthorshipAgreement:
    """§24.2 — التأليف قرار بشري مسجَّل، ولا يُسند لغير إنسان أو جهة."""
    if party_kind not in AUTHORSHIP_PARTY_KINDS:
        raise RightsGateError("thesis.invalid_party_kind", party_kind=party_kind)
    for role in credit_roles or []:
        if role not in CREDIT_ROLES:
            raise RightsGateError("thesis.unknown_credit_role", role=role)

    party = AuthorshipParty(
        tenant_id=tenant_id, party_kind=party_kind, display_name=display_name, user_id=user_id
    )
    session.add(party)
    await session.flush()

    agreement = AuthorshipAgreement(
        tenant_id=tenant_id, opportunity_id=opportunity_id, party_id=party.id,
        author_position=author_position, is_corresponding=is_corresponding,
        consent_status="pending",
    )
    session.add(agreement)
    await session.flush()

    if credit_roles:
        from ...models.thesis import CreditRoleAssignment  # noqa: PLC0415

        for role in credit_roles:
            session.add(CreditRoleAssignment(
                tenant_id=tenant_id, agreement_id=agreement.id, credit_role=role,
                assigned_by=actor_user_id,
            ))

    await audit.record(
        session, tenant_id=tenant_id, action="authorship.author_added",
        object_type="publication_opportunity", object_id=opportunity_id,
        actor_user_id=actor_user_id,
        state_after={
            "party_kind": party_kind, "position": author_position,
            "credit_roles": credit_roles or [], "consent": "pending",
        },
        reason="authorship recorded by a human decision (§24.2)",
    )
    return agreement


async def record_consent(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    agreement_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    consent_file_id: uuid.UUID | None = None,
) -> AuthorshipAgreement:
    agreement = (
        await session.execute(
            select(AuthorshipAgreement).where(AuthorshipAgreement.id == agreement_id)
        )
    ).scalar_one_or_none()
    if agreement is None:
        raise NotFound("thesis.agreement_not_found")

    agreement.consent_status = "granted"
    agreement.consent_file_id = consent_file_id
    agreement.consent_recorded_at = dt.datetime.now(dt.UTC)

    await audit.record(
        session, tenant_id=tenant_id, action="authorship.consent_recorded",
        object_type="authorship_agreement", object_id=agreement.id,
        actor_user_id=actor_user_id,
        state_before={"consent_status": "pending"},
        state_after={"consent_status": "granted", "has_file": consent_file_id is not None},
    )
    return agreement


async def approve_gate(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    reason: str | None = None,
) -> PublicationOpportunity:
    """بوابة GT1 — الاعتماد الوحيد الذي يسمح بالتقدم إلى Ready to Submit."""
    status = await gate_status(session, tenant_id=tenant_id, opportunity_id=opportunity_id)
    opportunity = (
        await session.execute(
            select(PublicationOpportunity).where(PublicationOpportunity.id == opportunity_id)
        )
    ).scalar_one()

    if status.blockers:
        await audit.record(
            session, tenant_id=tenant_id, action="authorship.gate_refused",
            object_type="publication_opportunity", object_id=opportunity_id,
            actor_user_id=actor_user_id, state_after={"blockers": status.blockers},
            reason="rights or authorship prerequisites are incomplete (§23.9, TC-06)",
        )
        raise RightsGateError("thesis.gate_blocked", blockers=",".join(status.blockers))

    now = dt.datetime.now(dt.UTC)
    opportunity.rights_approved_by = actor_user_id
    opportunity.rights_approved_at = now
    opportunity.authorship_approved_by = actor_user_id
    opportunity.authorship_approved_at = now
    opportunity.status = "ready_to_submit"

    await audit.record(
        session, tenant_id=tenant_id, action="authorship.gate_approved",
        object_type="publication_opportunity", object_id=opportunity_id,
        actor_user_id=actor_user_id,
        state_after={
            "gate": "GT1", "rights_basis": status.rights_basis,
            "authors": status.authors_total, "status": "ready_to_submit",
        },
        reason=reason or "researcher approved rights and authorship (GT1)",
    )
    return opportunity
