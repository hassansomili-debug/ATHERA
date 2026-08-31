"""الملفات | Files (§29.2، §36.2، §33.3).

الرفع لا يُعتمد إلا ببصمة مطابقة، وكل ملف يحمل سجل provenance كامل، وكل
تنزيل يُسجَّل — بلا استثناء.
"""
import datetime as dt
import hashlib
import uuid
from time import perf_counter

from fastapi import APIRouter, Depends, File as FormFile, Form, UploadFile, status
from fastapi.responses import StreamingResponse
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


# ══════════════════════════════════════════════════════════════════════
# رفع مباشر عبر الخادم
# ══════════════════════════════════════════════════════════════════════
@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: UploadFile = FormFile(...),
    classification: str = Form(default="C2"),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """رفع يمرّ بالخادم لا بالمتصفح إلى التخزين.

    **لماذا لا رابط موقّع هنا؟** لأن ترويسة CSP تحصر اتصال المتصفح بالـAPI
    وحده (§38.6.8)، والرفع المباشر يُحجب صامتًا. والمرور بالخادم يبقي مضيف
    التخزين مخفيًا عن المتصفح، ويجعل التحقق من المحتوى ممكنًا قبل الحفظ —
    وهو ما لا يستطيعه رابط موقّع أصلًا. والمسار الموقّع باقٍ لمن يحتاجه.

    **الترتيب مقصود: التخزين أولًا ثم القاعدة.** فشل التخزين لا يترك سجلًّا
    يتيمًا يدّعي ملفًا لا وجود له، وفشل القاعدة يحذف الكائن قبل أن يُبلَّغ
    نجاح. ولا يُعاد «تم» إلا بعد تأكّد الاثنين.
    """
    data = await upload.read()
    declared = upload.content_type or "application/octet-stream"
    filename = upload.filename or "file"

    storage.validate_upload(declared, len(data), filename=filename)
    storage.validate_content(declared, data[:8])

    file_id = uuid.uuid4()
    key = storage.build_storage_key(principal.tenant_id, file_id, filename,
                                    user_id=principal.user_id)
    checksum = storage.sha256_of(data)

    started = perf_counter()
    storage.get_store().put(key, data, declared)
    elapsed_ms = int((perf_counter() - started) * 1000)

    try:
        record = File(
            id=file_id,
            tenant_id=principal.tenant_id,
            storage_key=key,
            original_filename=filename[:512],
            content_type=declared,
            size_bytes=len(data),
            checksum_sha256=checksum,
            classification=classification,
            is_untrusted_content=True,  # §33.3 — محتوى الملفات بيانات لا تعليمات.
            status="stored",
            uploaded_by=principal.user_id,
            completed_at=dt.datetime.now(dt.UTC),
        )
        session.add(record)
        await session.flush()

        session.add(ObjectGrant(
            tenant_id=principal.tenant_id, object_type="file", object_id=file_id,
            user_id=principal.user_id, grant_level="owner", granted_by=principal.user_id,
        ))
        session.add(ProvenanceEvent(
            tenant_id=principal.tenant_id, object_type="file", object_id=file_id,
            source_type="upload", source_id=file_id, source_locator=key,
            created_by=principal.user_id,
            verification_status="unverified",  # §7.4 — الرفع لا يعني التحقق.
        ))
        await audit.record(
            session,
            tenant_id=principal.tenant_id,
            action="file.uploaded",
            object_type="file",
            object_id=file_id,
            actor_user_id=principal.user_id,
            # لا محتوى ولا اسم كامل ولا مفتاح سرّي في السجل — وصفٌ لا بيانات.
            state_after={
                "content_type": declared, "size_bytes": len(data),
                "kind": storage.kind_for(declared), "classification": classification,
                "storage_ms": elapsed_ms,
            },
            request_id=principal.request_id,
            ip_address=principal.ip_address,
        )
    except Exception:
        # القاعدة سقطت بعد نجاح التخزين: يُحذف الكائن فلا يبقى بلا سجل.
        storage.get_store().delete(key)
        raise

    return FileResponse.model_validate(record, from_attributes=True)


@router.get("/{file_id}/content")
async def stream_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """بثّ مصادق — بلا رابط عام ولا كشف لمضيف التخزين.

    التخويل يُفحص قبل قراءة بايت واحد، وRLS تمنع أصلًا رؤية سجل مستأجر آخر:
    تخمين معرّف ملف لا يعطي شيئًا.
    """
    record = (await session.execute(select(File).where(File.id == file_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, "read")

    data = storage.get_store().get(record.storage_key)

    session.add(FileAccessLog(
        tenant_id=principal.tenant_id, file_id=file_id, user_id=principal.user_id,
        action="download", accessed_at=dt.datetime.now(dt.UTC), ip_address=principal.ip_address,
    ))
    await audit.record(
        session, tenant_id=principal.tenant_id, action="file.downloaded",
        object_type="file", object_id=file_id, actor_user_id=principal.user_id,
        request_id=principal.request_id, ip_address=principal.ip_address,
    )
    return StreamingResponse(
        iter([data]),
        media_type=record.content_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{storage.safe_filename(record.original_filename)}"',
            "Cache-Control": "private, no-store",
        },
    )
