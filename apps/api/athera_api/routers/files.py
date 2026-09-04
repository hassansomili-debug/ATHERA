"""الملفات | Files (§29.2، §36.2، §33.3).

الرفع لا يُعتمد إلا ببصمة مطابقة، وكل ملف يحمل سجل provenance كامل، وكل
تنزيل يُسجَّل — بلا استثناء.
"""
import datetime as dt
import hashlib
import uuid
from time import perf_counter

from fastapi import APIRouter, Depends, File as FormFile, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.audit import ProvenanceEvent
from ..models.files import File, FileAccessLog
from ..models.identity import ObjectGrant
from ..schemas.files import (
    FileCompleteRequest,
    FileDownloadResponse,
    FileInitRequest,
    FileInitResponse,
    FileResponse,
    LibraryFile,
)
from ..services import audit, rbac, storage, workspace

# مقطع الميجابايت: يوازن بين عدد الدورات وبصمة الذاكرة.
CHUNK_BYTES = 1024 * 1024

router = APIRouter(prefix="/api/v1/files", tags=["files"])
settings = get_settings()


# ── حدود صفحة المكتبة ──────────────────────────────────────────────────
#
# **قائمةٌ بلا حدّ ليست قائمة.** كان المسار يردّ كل ملفات المستأجر دفعةً
# واحدة، وكل ملفٍ يزيدها. فمكتبةٌ تكبر تُبطئ نفسها بنفسها حتى تسقط —
# وذلك ما شكاه صاحبها: «المكتبة ما تتحمل كتب».
DEFAULT_PAGE = 25
MAX_PAGE = 100


@router.get("", response_model=list[LibraryFile])
async def list_files(
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    after: uuid.UUID | None = Query(default=None),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[LibraryFile]:
    """ملفات الباحث — **وكانت المكتبة لا تستطيع أن تعرضها إطلاقًا.**

    المسار لم يكن موجودًا: `POST /files` يبدأ رفعًا، و`GET /files/{id}` يقرأ
    واحدًا بمعرّفه. فمن رفع ملفًا لم يجد له أثرًا في الواجهة — كان عليه أن
    يحفظ معرّفه بنفسه.

    **والحالة تُقال كما هي.** الرفع يُنتج `stored`، والقراءة والاستخراج
    يجريان في مسار الرسائل (S5C). فتُقرأ حال المعالجة من `extraction_runs`
    الحقيقية، ولا يُقال «حُلِّل» لملفٍ لم يُقرأ — والصمت أصدق من وعدٍ كاذب.

    **ثم صارت تعرضها ولا تُنهي.** الصياغة السابقة كانت تقرأ كل الملفات بلا
    حدّ، ثم تسأل القاعدة عن حال **كل ملف على حدة**: ثلاث عبارات لكل ملف
    عُولج. والـAPI في سنغافورة والقاعدة في مومباي، فكل عبارة رحلةٌ بنحو
    ستين مللي ثانية — أربعون ملفًا تعني مئةً وعشرين رحلة، سبع ثوانٍ من
    الشبكة وحدها، وتزيد طردًا مع كل كتابٍ يُضاف. فالباحث الذي يملأ مكتبته
    يعاقَب على ملئها.

    **فصارت عبارةً واحدة وصفحةً محدودة.** الصفحة تُقتطع أولًا ثم تُشتقّ
    حال ما فيها وحده — والاستعلامات الفرعية مرتبطةٌ بصفوف الصفحة لا بكل
    ملفات المستأجر.

    **والمؤشّر مفتاحي لا إزاحة.** `after` معرّف آخر ملفٍ رآه العميل، ويُحلّ
    داخل العبارة نفسها فلا يكلّف رحلةً ثانية. والترتيب `(created_at, id)`
    نازلًا: `created_at` وحده لا يفصل ملفَّين رُفعا في المعاملة نفسها، فيتكرّر
    ملفٌ في صفحتين أو يسقط بينهما. ومؤشّرٌ إلى ملفٍ حُذف بين صفحتين يعطي
    صفحةً فارغة — لا خطأً: الحذف واقعةٌ مشروعة، وإعادة الفتح تصلحها.
    """
    page = (
        select(File)
        .where(File.tenant_id == principal.tenant_id)
        .order_by(File.created_at.desc(), File.id.desc())
        .limit(limit)
    )
    if after is not None:
        anchor_created = (
            select(File.created_at)
            .where(File.id == after, File.tenant_id == principal.tenant_id)
            .scalar_subquery()
        )
        anchor_id = (
            select(File.id)
            .where(File.id == after, File.tenant_id == principal.tenant_id)
            .scalar_subquery()
        )
        page = page.where(
            tuple_(File.created_at, File.id) < tuple_(anchor_created, anchor_id))

    window = page.subquery("page")
    thesis_id, run_status, candidates, reviewed = workspace.file_processing_state_columns(
        principal.tenant_id, window.c.id)
    rows = (await session.execute(
        select(window.c.id, window.c.original_filename, window.c.content_type,
               window.c.size_bytes, window.c.classification, window.c.status,
               window.c.created_at, thesis_id, run_status, candidates, reviewed)
        .order_by(window.c.created_at.desc(), window.c.id.desc())
    )).all()

    library: list[LibraryFile] = []
    for row in rows:
        processing, seen, done, thesis = workspace.file_processing_state_of_row(
            row[7], row[8], row[9], row[10])
        library.append(LibraryFile(
            id=row[0], original_filename=row[1], content_type=row[2],
            size_bytes=row[3], classification=row[4], status=row[5],
            created_at=row[6], processing_status=processing,
            thesis_id=thesis, candidates=seen, reviewed=done))
    return library


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
    record = (await session.execute(select(File).where(File.id == file_id,
                                            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
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
    record = (await session.execute(select(File).where(File.id == file_id,
                                            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
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
    record = (await session.execute(select(File).where(File.id == file_id,
                                            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
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
    declared = upload.content_type or "application/octet-stream"
    filename = upload.filename or "file"

    # النوع والامتداد أولًا: رفض مبكر قبل بثّ بايت واحد.
    storage.validate_type(declared, filename)

    # ── المرور الأول: تجزئة وعدّ وبصمة، مقطعًا مقطعًا ──
    #
    # لا `await upload.read()` هنا: نصف جيجابايت في الذاكرة على آلة بنصف
    # جيجابايت هو نفاد ذاكرة لا بطء. وStarlette يفيض بالجسم إلى ملف مؤقت
    # على القرص بعد ميجابايت واحد، فما يبقى في الذاكرة مقطعٌ واحد فقط.
    #
    # والسقف يُفحص **أثناء** البثّ لا بعده: ملف يتجاوز الحد يُوقَف عند
    # تجاوزه لا بعد استقباله كاملًا.
    limit = storage.max_bytes_for(declared)
    digest = hashlib.sha256()
    size = 0
    head = b""
    while chunk := await upload.read(CHUNK_BYTES):
        if not head:
            head = chunk[:8]
        size += len(chunk)
        if size > limit:
            raise AtheraError("file.too_large", status_code=413,
                              size_bytes=size, max_bytes=limit)
        digest.update(chunk)

    storage.validate_size(declared, size)
    storage.validate_content(declared, head)

    file_id = uuid.uuid4()
    key = storage.build_storage_key(principal.tenant_id, file_id, filename,
                                    user_id=principal.user_id)
    checksum = digest.hexdigest()

    # ── المرور الثاني: بثّ إلى التخزين من بداية الملف المؤقت ──
    await upload.seek(0)
    started = perf_counter()
    storage.get_store().put_stream(key, upload.file, declared)
    elapsed_ms = int((perf_counter() - started) * 1000)

    try:
        record = File(
            id=file_id,
            tenant_id=principal.tenant_id,
            storage_key=key,
            original_filename=filename[:512],
            content_type=declared,
            size_bytes=size,
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
                "content_type": declared, "size_bytes": size,
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
    record = (await session.execute(select(File).where(File.id == file_id,
                                            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
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
