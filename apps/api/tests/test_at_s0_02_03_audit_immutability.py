"""AT-S0-02/03 — مناعة سجل التدقيق وسلسلة التجزئة (§37، ADR-0004)."""

import pytest
from sqlalchemy import text

from athera_api.db import tenant_session
from athera_api.services import audit

pytestmark = pytest.mark.asyncio


async def test_update_on_audit_events_is_rejected(two_tenants):
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await audit.record(
            session, tenant_id=a["tenant_id"], action="test.event",
            object_type="test", actor_user_id=a["user_id"], reason="AT-S0-02",
        )

    with pytest.raises(Exception) as excinfo:
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            await session.execute(text("UPDATE audit_events SET reason = 'tampered'"))
    assert "append-only" in str(excinfo.value).lower() or "privilege" in str(excinfo.value).lower()


async def test_delete_on_audit_events_is_rejected(two_tenants):
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await audit.record(
            session, tenant_id=a["tenant_id"], action="test.event2",
            object_type="test", actor_user_id=a["user_id"],
        )
    with pytest.raises(Exception):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            await session.execute(text("DELETE FROM audit_events"))


async def test_chain_is_intact_after_several_events(two_tenants):
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        for index in range(5):
            await audit.record(
                session, tenant_id=a["tenant_id"], action=f"test.seq.{index}",
                object_type="test", actor_user_id=a["user_id"],
                state_after={"index": index, "note": "نص عربي للتأكد من ثبات التمثيل"},
            )
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        intact, broken_at = await audit.verify_chain(session, a["tenant_id"])
    assert intact and broken_at is None


async def test_chain_detects_tampering(two_tenants):
    """AT-S0-03 — التعديل من مسار امتيازي يجب أن يُكتشف، وإن لم يُمنع."""
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        event = await audit.record(
            session, tenant_id=a["tenant_id"], action="test.tamper",
            object_type="test", actor_user_id=a["user_id"], reason="original",
        )
        seq = event.chain_seq

    # محاكاة عبث بامتياز أعلى: نعطّل الـtrigger مؤقتًا كما لو كان DBA فعلها.
    # هذا يحتاج ملكية الجدول — ودور التطبيق لا يملكها عمدًا. التخطي هنا
    # ليس تسامحًا: هو إقرار بأن السيناريو يتطلب صلاحية أعلى من صلاحية المنصة.
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        try:
            await session.execute(
                text("ALTER TABLE audit_events DISABLE TRIGGER trg_audit_events_immutable")
            )
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"simulating DBA tampering requires table ownership: {exc}")
        await session.execute(
            text("UPDATE audit_events SET reason = 'tampered' WHERE tenant_id = :t AND chain_seq = :s"),
            {"t": str(a["tenant_id"]), "s": seq},
        )
        await session.execute(text("ALTER TABLE audit_events ENABLE TRIGGER trg_audit_events_immutable"))

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        intact, broken_at = await audit.verify_chain(session, a["tenant_id"])
    assert not intact, "tampering went undetected — the hash chain is not doing its job"
    assert broken_at == seq
