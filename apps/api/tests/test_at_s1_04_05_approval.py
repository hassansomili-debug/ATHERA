"""AT-S1-04/05 — الاعتماد ينتج ذاكرة موثقة، والرفض لا ينتج شيئًا.

يحتاج قاعدة بيانات حية: القيود التي نختبرها مفروضة في PostgreSQL لا في بايثون.
"""
import datetime as dt
import uuid

import pytest
from sqlalchemy import select, text

from athera_api.db import tenant_session
from athera_api.models.audit import AuditEvent, ProvenanceEvent
from athera_api.models.files import File
from athera_api.models.research import DocumentChunk, ExtractionRun, FactCandidate, ResearcherMemory
from athera_api.services import memory

pytestmark = pytest.mark.asyncio

CHUNK_TEXT = "يستخدم الباحث برنامج SPSS في التحليل الكمي لبيانات الاستبانة."


async def _seed_candidate(tenant_id, user_id, *, quote: str = "برنامج SPSS"):
    async with tenant_session(tenant_id, user_id) as session:
        file_row = File(
            tenant_id=tenant_id,
            storage_key=f"tenants/{tenant_id}/files/{uuid.uuid4()}/cv.pdf",
            original_filename="cv.pdf", content_type="application/pdf",
            size_bytes=100, status="stored", uploaded_by=user_id,
        )
        session.add(file_row)
        await session.flush()

        run = ExtractionRun(tenant_id=tenant_id, file_id=file_row.id, extractor="rules",
                            status="completed", started_at=dt.datetime.now(dt.UTC))
        chunk = DocumentChunk(tenant_id=tenant_id, file_id=file_row.id, seq=1, text=CHUNK_TEXT,
                              locator="p.1 ¶1", page_number=1, paragraph_index=1,
                              char_count=len(CHUNK_TEXT))
        session.add_all([run, chunk])
        await session.flush()

        candidate = FactCandidate(
            tenant_id=tenant_id, extraction_run_id=run.id, file_id=file_row.id, chunk_id=chunk.id,
            memory_category="researcher_fact", field_key="software",
            statement_ar="يستخدم الباحث SPSS", statement_en="The researcher uses SPSS",
            value={"skill_kind": "software", "name": "SPSS"},
            quote=quote, locator="p.1 ¶1", confidence=0.7, status="unverified",
        )
        session.add(candidate)
        await session.flush()
        return candidate.id


async def test_approval_creates_verified_memory_with_provenance_and_audit(two_tenants):
    a = two_tenants["a"]
    candidate_id = await _seed_candidate(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        record = await memory.approve_candidate(
            session, tenant_id=a["tenant_id"], candidate_id=candidate_id,
            actor_user_id=a["user_id"], reason="أكد الباحث صحة المعلومة",
        )
        memory_id = record.id

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        stored = (
            await session.execute(select(ResearcherMemory).where(ResearcherMemory.id == memory_id))
        ).scalar_one()
        assert stored.verification_status == "verified"
        assert stored.verified_by == a["user_id"] and stored.verified_at is not None
        assert stored.source_type == "upload"
        assert stored.source_locator and stored.source_quote

        provenance = (
            await session.execute(
                select(ProvenanceEvent).where(ProvenanceEvent.object_id == memory_id)
            )
        ).scalar_one()
        assert provenance.source_locator == "p.1 ¶1"

        event = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.object_id == memory_id)
            )
        ).scalar_one()
        assert event.action == "memory.fact_approved"

        candidate = (
            await session.execute(select(FactCandidate).where(FactCandidate.id == candidate_id))
        ).scalar_one()
        assert candidate.status == "approved" and candidate.resulting_memory_id == memory_id


async def test_rejection_creates_no_memory_but_keeps_the_record(two_tenants):
    a = two_tenants["a"]
    candidate_id = await _seed_candidate(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await memory.reject_candidate(
            session, tenant_id=a["tenant_id"], candidate_id=candidate_id,
            actor_user_id=a["user_id"], reason="هذه رتبة شخص آخر مذكور في السيرة",
        )

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        candidate = (
            await session.execute(select(FactCandidate).where(FactCandidate.id == candidate_id))
        ).scalar_one()
        assert candidate.status == "rejected"
        assert candidate.resulting_memory_id is None
        assert candidate.decision_reason
        count = (
            await session.execute(
                select(ResearcherMemory).where(ResearcherMemory.source_file_id == candidate.file_id)
            )
        ).scalars().all()
        assert count == []


async def test_cannot_approve_a_candidate_whose_quote_left_the_source(two_tenants):
    """إعادة التحقق عند الاعتماد: المصدر قد يكون تغيّر بين الاستخراج والقرار."""
    a = two_tenants["a"]
    candidate_id = await _seed_candidate(a["tenant_id"], a["user_id"], quote="برنامج AMOS")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(memory.MemoryPromotionError):
            await memory.approve_candidate(
                session, tenant_id=a["tenant_id"], candidate_id=candidate_id,
                actor_user_id=a["user_id"],
            )


async def test_double_decision_is_refused(two_tenants):
    a = two_tenants["a"]
    candidate_id = await _seed_candidate(a["tenant_id"], a["user_id"])
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        await memory.approve_candidate(
            session, tenant_id=a["tenant_id"], candidate_id=candidate_id,
            actor_user_id=a["user_id"],
        )
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(memory.MemoryPromotionError):
            await memory.reject_candidate(
                session, tenant_id=a["tenant_id"], candidate_id=candidate_id,
                actor_user_id=a["user_id"],
            )


async def test_database_refuses_verified_memory_from_a_model_path(two_tenants):
    """AT-S1-01 على مستوى قاعدة البيانات: لا التفاف حتى بـSQL مباشر."""
    a = two_tenants["a"]
    with pytest.raises(Exception):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO researcher_memories
                      (tenant_id, memory_category, statement_ar, source_type, verification_status)
                    VALUES (:t, 'researcher_fact', 'ادعاء بلا مصدر', 'model_output', 'verified')
                    """
                ),
                {"t": str(a["tenant_id"])},
            )


async def test_database_refuses_verified_without_verifier(two_tenants):
    a = two_tenants["a"]
    with pytest.raises(Exception):
        async with tenant_session(a["tenant_id"], a["user_id"]) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO researcher_memories
                      (tenant_id, memory_category, statement_ar, source_type, verification_status)
                    VALUES (:t, 'researcher_fact', 'ادعاء', 'user_statement', 'verified')
                    """
                ),
                {"t": str(a["tenant_id"])},
            )
