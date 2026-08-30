"""AT-S4-02…06 — سجل الادعاء-الدليل وقواعد المنع الثلاث (§14.4، §14.5).

يحتاج قاعدة بيانات حية: القيود مفروضة في PostgreSQL لا في بايثون.
"""
import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from athera_api.db import tenant_session
from athera_api.models.literature import (
    ACCESS_STATES,
    SUPPORT_LEVELS,
    TEXT_BEARING_STATES,
    Claim,
    EvidenceExcerpt,
    Source,
)
from athera_api.services.literature import ledger

pytestmark = pytest.mark.asyncio


def test_five_access_states_and_only_three_carry_text():
    """AT-S4-09 — §14.2 كاملة، و§14.5 مشفَّرة في الخريطة نفسها."""
    assert set(ACCESS_STATES) == {
        "open_access_full_text", "user_uploaded_rights_confirmed",
        "licensed_institutional_access", "abstract_metadata_only",
        "restricted_no_processing_right",
    }
    assert set(TEXT_BEARING_STATES) == {
        "open_access_full_text", "user_uploaded_rights_confirmed",
        "licensed_institutional_access",
    }
    assert ACCESS_STATES["abstract_metadata_only"] is False
    assert ACCESS_STATES["restricted_no_processing_right"] is False


def test_four_support_levels_including_contradictory():
    """AT-S4-06 — §14.4. الدليل المناقض قيمة أولى لا استثناء."""
    assert set(SUPPORT_LEVELS) == {"direct", "partial", "contextual", "contradictory"}
    for ar, en in SUPPORT_LEVELS.values():
        assert ar.strip() and en.strip()
        assert any("؀" <= ch <= "ۿ" for ch in ar)


async def _seed_source(tenant_id, user_id, *, access_state="open_access_full_text",
                       retraction_status="none", verified=True) -> uuid.UUID:
    async with tenant_session(tenant_id, user_id) as session:
        source = Source(
            tenant_id=tenant_id, doi=f"10.1234/test.{uuid.uuid4().hex[:8]}",
            title="دراسة تجريبية", publication_year=2024, access_state=access_state,
            retraction_status=retraction_status, registry="offline", registry_id="W1",
            last_verified_at=dt.datetime.now(dt.UTC),
            verification_status="verified" if verified else "unverified",
        )
        session.add(source)
        await session.flush()
        return source.id


async def _seed_claim(tenant_id, user_id, claim_type="empirical") -> uuid.UUID:
    async with tenant_session(tenant_id, user_id) as session:
        claim = Claim(tenant_id=tenant_id, text_ar="الثقة في الإعلان ترتبط بنية الشراء",
                      claim_type=claim_type, status="draft")
        session.add(claim)
        await session.flush()
        return claim.id


async def test_metadata_only_source_cannot_carry_an_excerpt(two_tenants):
    """AT-S4-02 — §14.5 القاعدة 3، أهم قيد في هذا السبرنت."""
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"],
                                   access_state="abstract_metadata_only")
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(ledger.LedgerError) as exc:
            await ledger.add_excerpt(
                session, tenant_id=a["tenant_id"], source_id=source_id,
                quote="نص لم يُقرأ فعلًا", locator="p.4", actor_user_id=a["user_id"],
            )
        assert exc.value.code == "evidence.no_text_access"


async def test_restricted_source_cannot_carry_an_excerpt(two_tenants):
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"],
                                   access_state="restricted_no_processing_right")
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(ledger.LedgerError):
            await ledger.add_excerpt(
                session, tenant_id=a["tenant_id"], source_id=source_id,
                quote="نص محمي", locator="p.1", actor_user_id=a["user_id"],
            )


async def test_unverified_source_cannot_carry_an_excerpt(two_tenants):
    """§14.5 القاعدة 1 — لا دليل على مصدر غير متحقق."""
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"], verified=False)
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(ledger.LedgerError) as exc:
            await ledger.add_excerpt(
                session, tenant_id=a["tenant_id"], source_id=source_id,
                quote="نص من مصدر غير متحقق", locator="p.2", actor_user_id=a["user_id"],
            )
        assert exc.value.code == "evidence.source_not_verified"


async def test_retracted_source_needs_explicit_acknowledgement(two_tenants):
    """AT-S4-03 — §14.5 القاعدة 2: المنع مشروط لا مطلق."""
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"], retraction_status="retracted")
    claim_id = await _seed_claim(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        excerpt = await ledger.add_excerpt(
            session, tenant_id=a["tenant_id"], source_id=source_id,
            quote="نتيجة من دراسة سُحبت لاحقًا", locator="p.7", actor_user_id=a["user_id"],
        )
        excerpt_id = excerpt.id

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(ledger.LedgerError) as exc:
            await ledger.link_evidence(
                session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=excerpt_id,
                support_level="direct", actor_user_id=a["user_id"],
            )
        assert exc.value.code == "evidence.retraction_needs_acknowledgement"

    # مع إقرار وسياق مكتوب: مسموح (§14.5).
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        link = await ledger.link_evidence(
            session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=excerpt_id,
            support_level="contextual", actor_user_id=a["user_id"],
            retraction_acknowledged=True,
            acknowledgement_note="يُستشهد به لتوثيق تاريخ الجدل لا لدعم نتيجة.",
        )
        assert link.retraction_acknowledged


async def test_claim_without_evidence_is_a_gap_not_a_generated_reference(two_tenants):
    """AT-S4-04 / TC-02 — البديل عن الاختلاق إعلانُ فجوة."""
    a = two_tenants["a"]
    claim_id = await _seed_claim(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        state = await ledger.claim_status(session, tenant_id=a["tenant_id"], claim_id=claim_id)
        assert state.has_evidence_gap and state.status == "evidence_gap"
        assert not state.can_be_final

        with pytest.raises(ledger.LedgerError) as exc:
            await ledger.finalize_claim(session, tenant_id=a["tenant_id"], claim_id=claim_id,
                                        actor_user_id=a["user_id"])
        assert exc.value.code == "evidence.claim_has_gap"

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        claim = (await session.execute(select(Claim).where(Claim.id == claim_id))).scalar_one()
        assert claim.status == "evidence_gap"
        assert claim.verification_status == "unverified"
        # لم يُنشأ أي مصدر أو مقتطف تعويضًا عن غياب الدليل.
        assert (await session.execute(select(EvidenceExcerpt))).scalars().all() == []


async def test_unresolved_contradiction_blocks_finalisation(two_tenants):
    """AT-S4-05 — الدليل المناقض يُعرض ويمنع الإغلاق حتى يُعالَج."""
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"])
    claim_id = await _seed_claim(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        supporting = await ledger.add_excerpt(
            session, tenant_id=a["tenant_id"], source_id=source_id,
            quote="النتيجة تدعم العلاقة المفترضة بين المتغيرين", locator="p.10",
            actor_user_id=a["user_id"],
        )
        against = await ledger.add_excerpt(
            session, tenant_id=a["tenant_id"], source_id=source_id,
            quote="لم تظهر الدراسة أي علاقة دالة بين المتغيرين", locator="p.14",
            actor_user_id=a["user_id"],
        )
        await ledger.link_evidence(
            session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=supporting.id,
            support_level="direct", actor_user_id=a["user_id"],
        )
        await ledger.link_evidence(
            session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=against.id,
            support_level="contradictory", actor_user_id=a["user_id"],
        )

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        state = await ledger.claim_status(session, tenant_id=a["tenant_id"], claim_id=claim_id)
        assert state.direct == 1 and state.contradictory == 1
        assert state.unresolved_contradictions == 1
        assert state.status == "contradicted" and not state.can_be_final

        with pytest.raises(ledger.LedgerError) as exc:
            await ledger.finalize_claim(session, tenant_id=a["tenant_id"], claim_id=claim_id,
                                        actor_user_id=a["user_id"])
        assert exc.value.code == "evidence.claim_contradicted"


async def test_supported_claim_can_be_finalised(two_tenants):
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"])
    claim_id = await _seed_claim(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        excerpt = await ledger.add_excerpt(
            session, tenant_id=a["tenant_id"], source_id=source_id,
            quote="أظهرت الدراسة ارتباطًا موجبًا بين الثقة ونية الشراء", locator="p.9",
            actor_user_id=a["user_id"],
        )
        await ledger.link_evidence(
            session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=excerpt.id,
            support_level="direct", actor_user_id=a["user_id"],
        )

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        claim = await ledger.finalize_claim(session, tenant_id=a["tenant_id"],
                                            claim_id=claim_id, actor_user_id=a["user_id"])
        assert claim.status == "final"
        assert claim.verification_status == "verified"
        assert claim.reviewed_by == a["user_id"] and claim.reviewed_at is not None


async def test_unknown_support_level_is_refused(two_tenants):
    a = two_tenants["a"]
    source_id = await _seed_source(a["tenant_id"], a["user_id"])
    claim_id = await _seed_claim(a["tenant_id"], a["user_id"])
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        excerpt = await ledger.add_excerpt(
            session, tenant_id=a["tenant_id"], source_id=source_id,
            quote="نص كافٍ للاقتطاف", locator="p.1", actor_user_id=a["user_id"],
        )
        with pytest.raises(ledger.LedgerError):
            await ledger.link_evidence(
                session, tenant_id=a["tenant_id"], claim_id=claim_id, excerpt_id=excerpt.id,
                support_level="probably_true", actor_user_id=a["user_id"],
            )
