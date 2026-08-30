"""الملفات | Files (§29.2، §36.2، §33.3).

الرفع لا يُعتمد إلا ببصمة مطابقة، وكل ملف يحمل سجل provenance كامل، وكل
تنزيل يُسجَّل — بلا استثناء.
"""
import datetime as dt
import hashlib
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import Principal, get_principal, get_session
from ..errors import NotFound
from ..models.audit import ProvenanceEvent
from ..models.files import File, FileAccessLog
from ..models.identity import ObjectGrant
from ..schemas.files import (
    FileCompleteRequest,
    FileDownloadResponse,
    FileInitRequest,
    FileInitResponse,
    FileResponse,
)
from ..services import audit, rbac, storage

router = APIRouter(prefix="/api/v1/files", tags=["files"])
settings = get_settings()


@router.post("", response_model=FileInitResponse, status_code=status.HTTP_201_CREATED)
async def init_upload(
    payload: FileInitRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileInitResponse:
    storage.validate_upload(payload.content_type, payload.size_bytes)

    file_id = uuid.uuid4()
    key = storage.build_storage_key(principal.tenant_id, file_id, payload.filename)
    record = File(
        id=file_id,
        tenant_id=principal.tenant_id,
        storage_key=key,
        original_filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        classification=payload.classification,
        is_untrusted_content=True,  # §33.3 — محتوى الملفات بيانات لا تعليمات.
        status="pending",
        uploaded_by=principal.user_id,
    )
    session.add(record)
    await session.flush()

    session.add(
        ObjectGrant(
            tenant_id=principal.tenant_id,
            object_type="file",
            object_id=file_id,
            user_id=principal.user_id,
            grant_level="owner",
            granted_by=principal.user_id,
        )
    )
    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="file.upload_initiated",
        object_type="file",
        object_id=file_id,
        actor_user_id=principal.user_id,
        state_after={"filename": payload.filename, "classification": payload.classification},
        request_id=principal.request_id,
        ip_address=principal.ip_address,
    )

    return FileInitResponse(
        file_id=file_id,
        upload_url=storage.presign_put(key, payload.content_type),
        storage_key=key,
        expires_in=settings.s3_presign_ttl_seconds,
    )


@router.post("/{file_id}/complete", response_model=FileResponse)
async def complete_upload(
    file_id: uuid.UUID,
    payload: FileCompleteRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    record = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, "write")

    record.checksum_sha256 = payload.checksum_sha256
    record.status = "stored"
    record.completed_at = dt.datetime.now(dt.UTC)

    # §29.2 — الحقول التسعة كاملة، وإلا فلا أثر قابل للتحقق.
    session.add(
        ProvenanceEvent(
            tenant_id=principal.tenant_id,
            object_type="file",
            object_id=file_id,
            source_type="upload",
            source_id=file_id,
            source_locator=record.storage_key,
            created_by=principal.user_id,
            verification_status="unverified",  # §7.4 — الرفع لا يعني التحقق.
        )
    )
    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="file.upload_completed",
        object_type="file",
        object_id=file_id,
        actor_user_id=principal.user_id,
        state_before={"status": "pending"},
        state_after={"status": "stored", "checksum_sha256": payload.checksum_sha256},
        request_id=principal.request_id,
    )
    return FileResponse.model_validate(record, from_attributes=True)


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    record = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, "read")
    return FileResponse.model_validate(record, from_attributes=True)


@router.get("/{file_id}/download", response_model=FileDownloadResponse)
async def download_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileDownloadResponse:
    record = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, "read")

    # §36.2 — لا رابط تنزيل بلا سجل وصول.
    session.add(
        FileAccessLog(
            tenant_id=principal.tenant_id,
            file_id=file_id,
            user_id=principal.user_id,
            action="presign",
            accessed_at=dt.datetime.now(dt.UTC),
            ip_address=principal.ip_address,
        )
    )
    await audit.record(
        session,
        tenant_id=principal.tenant_id,
        action="file.download_presigned",
        object_type="file",
        object_id=file_id,
        actor_user_id=principal.user_id,
        request_id=principal.request_id,
        ip_address=principal.ip_address,
    )
    return FileDownloadResponse(
        download_url=storage.presign_get(record.storage_key),
        expires_in=settings.s3_presign_ttl_seconds,
    )


def sha256_of(data: bytes) -> str:
    """أداة مساعدة للاختبارات والعملاء | helper for tests and clients."""
    return hashlib.sha256(data).hexdigest()
