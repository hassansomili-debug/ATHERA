"""AT-S0-01 — العزل بين المستأجرين | Tenant isolation (ADR-0002).

يفشل السبرنت إذا عاد أي صف من مستأجر آخر، بما في ذلك عند تزوير tenant_id.
"""
import uuid

import pytest
from sqlalchemy import select, text

from athera_api.db import tenant_session
from athera_api.models.files import File

pytestmark = pytest.mark.asyncio


async def _seed_file(tenant_id: uuid.UUID, user_id: uuid.UUID) -> uuid.UUID:
    async with tenant_session(tenant_id, user_id) as session:
        record = File(
            tenant_id=tenant_id,
            storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/x.pdf",
            original_filename="x.pdf",
            content_type="application/pdf",
            size_bytes=10,
            uploaded_by=user_id,
        )
        session.add(record)
        await session.flush()
        return record.id


async def test_cross_tenant_read_returns_nothing(two_tenants):
    a, b = two_tenants["a"], two_tenants["b"]
    file_a = await _seed_file(a["tenant_id"], a["user_id"])

    # المستأجر B يقرأ بمعرّف ملف يعرفه صراحةً — RLS تمنعه.
    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        found = (await session.execute(select(File).where(File.id == file_a))).scalar_one_or_none()
    assert found is None, "RLS failed: tenant B read a row owned by tenant A"


async def test_forged_tenant_id_in_where_clause_is_useless(two_tenants):
    """حتى لو زوّر المهاجم tenant_id في الاستعلام، السياق هو الحاكم."""
    a, b = two_tenants["a"], two_tenants["b"]
    file_a = await _seed_file(a["tenant_id"], a["user_id"])

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        rows = (
            await session.execute(
                select(File).where(File.id == file_a, File.tenant_id == a["tenant_id"])
            )
        ).scalars().all()
    assert rows == [], "RLS failed: forging tenant_id in the query bypassed isolation"


async def test_insert_into_another_tenant_is_rejected(two_tenants):
    """WITH CHECK يمنع الكتابة العابرة، لا القراءة فقط."""
    a, b = two_tenants["a"], two_tenants["b"]
    with pytest.raises(Exception):
        async with tenant_session(b["tenant_id"], b["user_id"]) as session:
            session.add(
                File(
                    tenant_id=a["tenant_id"],  # مستأجر آخر
                    storage_key=f"tenants/{a['tenant_id']}/files/{uuid.uuid4()}/evil.pdf",
                    original_filename="evil.pdf",
                    content_type="application/pdf",
                    size_bytes=1,
                    uploaded_by=b["user_id"],
                )
            )
            await session.flush()


async def test_missing_tenant_context_yields_zero_rows(two_tenants):
    """الفشل الآمن: بلا سياق لا توجد نتائج — لا تسريب."""
    a = two_tenants["a"]
    await _seed_file(a["tenant_id"], a["user_id"])
    async with tenant_session(None) as session:
        rows = (await session.execute(select(File))).scalars().all()
    assert rows == [], "missing tenant context leaked rows"


async def test_every_tenant_table_has_rls_enabled(db_ready):
    """AT-S0-01 الموسّع: جدول واحد بلا RLS يكفي لإسقاط العزل كله."""
    async with tenant_session(None) as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT c.relname
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    JOIN information_schema.columns col
                      ON col.table_name = c.relname AND col.column_name = 'tenant_id'
                    WHERE n.nspname = 'public' AND c.relkind = 'r'
                      AND (c.relrowsecurity = false OR c.relforcerowsecurity = false)
                    """
                )
            )
        ).scalars().all()
    assert rows == [], f"tables carrying tenant_id without FORCE RLS: {rows}"
