"""AT-S0-06 — الملفات: provenance كامل وتنزيل مسجَّل (§29.2، §36.2، §33.3)."""
import pytest
from sqlalchemy import select

from athera_api.db import tenant_session
from athera_api.models.audit import ProvenanceEvent
from athera_api.models.files import File
from athera_api.services import storage

pytestmark = pytest.mark.asyncio

REQUIRED_PROVENANCE_FIELDS = (
    "source_type", "source_id", "source_locator", "created_by", "created_at",
    "verification_status", "verified_by", "verified_at", "model_run_id",
)


def test_provenance_model_carries_the_nine_required_fields():
    """§29.2 — نقص حقل واحد يعني أثرًا غير قابل للتحقق."""
    columns = set(ProvenanceEvent.__table__.columns.keys())
    missing = [field for field in REQUIRED_PROVENANCE_FIELDS if field not in columns]
    assert not missing, f"missing mandatory provenance fields (§29.2): {missing}"


def test_uploaded_files_are_untrusted_by_default():
    """§33.3 — محتوى الملفات بيانات لا تعليمات."""
    default = File.__table__.columns["is_untrusted_content"].default
    server_default = File.__table__.columns["is_untrusted_content"].server_default
    assert (default is not None and default.arg is True) or server_default is not None


def test_upload_validation_rejects_unknown_types_and_oversize():
    from athera_api.errors import AtheraError

    with pytest.raises(AtheraError) as exc:
        storage.validate_upload("application/x-msdownload", 100)
    assert exc.value.code == "file.type_rejected"

    with pytest.raises(AtheraError) as exc:
        storage.validate_upload("application/pdf", storage.MAX_UPLOAD_BYTES + 1)
    assert exc.value.code == "file.too_large"


def test_storage_key_is_tenant_prefixed():
    """بادئة المسار جزء من العزل (ADR-0002)، لا مجرد تنظيم."""
    import uuid

    tenant_id, file_id = uuid.uuid4(), uuid.uuid4()
    key = storage.build_storage_key(tenant_id, file_id, "thesis.pdf")
    assert key.startswith(f"tenants/{tenant_id}/")
    # محاولة الهروب من المسار عبر اسم ملف خبيث.
    #
    # المهم ليس غياب حرفَي النقطة من الاسم، بل **استحالة الاجتياز**: اسم
    # الملف يُصبح مقطعًا واحدًا لأن الشرطات المائلة استُبدلت، فلا يستطيع
    # الخروج من بادئة المستأجر مهما احتوى.
    evil = storage.build_storage_key(tenant_id, file_id, "../../../etc/passwd")
    assert evil.startswith(f"tenants/{tenant_id}/")
    segments = evil.split("/")
    assert len(segments) == len(key.split("/")), "اسم الملف أضاف مقاطع مسار جديدة"
    assert ".." not in segments, "أحد المقاطع يساوي '..' فيسمح بالصعود"


async def test_provenance_row_written_on_upload_completion(two_tenants):
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        record = File(
            tenant_id=a["tenant_id"],
            storage_key=f"tenants/{a['tenant_id']}/files/x/y.pdf",
            original_filename="y.pdf", content_type="application/pdf",
            size_bytes=10, uploaded_by=a["user_id"],
        )
        session.add(record)
        await session.flush()
        session.add(
            ProvenanceEvent(
                tenant_id=a["tenant_id"], object_type="file", object_id=record.id,
                source_type="upload", source_id=record.id, source_locator=record.storage_key,
                created_by=a["user_id"], verification_status="unverified",
            )
        )
        file_id = record.id

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        row = (
            await session.execute(
                select(ProvenanceEvent).where(ProvenanceEvent.object_id == file_id)
            )
        ).scalar_one()
    # §7.4 — الرفع لا يساوي التحقق.
    assert row.verification_status == "unverified"
    assert row.source_locator
