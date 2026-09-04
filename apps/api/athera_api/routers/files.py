"""الملفات | Files (§29.2، §36.2، §33.3).

الرفع لا يُعتمد إلا ببصمة مطابقة، وكل ملف يحمل سجل provenance كامل، وكل
تنزيل يُسجَّل — بلا استثناء.
"""
import datetime as dt
import hashlib
import uuid
from time import perf_counter

from fastapi import APIRouter, Depends, File as FormFile, Form, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import tenant_session
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.audit import ProvenanceEvent
from ..models.files import File, FileAccessLog
from ..models.identity import ObjectGrant
from ..models.library import FOLDER_OBJECT_TYPE, LibraryFolder
from ..models.portfolio import ProjectFile
from ..schemas.files import (
    FileCompleteRequest,
    FileDownloadResponse,
    FileInitRequest,
    FileInitResponse,
    FileResponse,
    LibraryFile,
)
from ..schemas.library import FileMoveRequest, FileTrashView, TrashRequest
from ..services import audit, library, rbac, storage, workspace
from .folders import router as folders_router

# مقطع الميجابايت: يوازن بين عدد الدورات وبصمة الذاكرة.
CHUNK_BYTES = 1024 * 1024

router = APIRouter(prefix="/api/v1/files", tags=["files"])

# **الضمّ هنا قبل كل شيء، لا في آخر الملف.** FastAPI يوفّق المسارات
# بترتيب تسجيلها، و`GET /{file_id}` يسبق ما يُسجَّل بعده — فلو ضُمّ موجّه
# المجلَّدات في الأسفل لالتقط `‎/api/v1/files/folders` مسارُ المعرّف أولًا،
# وفشل تحويل «folders» إلى UUID، فيردّ 422 على قائمةٍ صحيحة. والترتيب هو
# كل الفرق، ولا يظهر في أي اختبار وحدة يستدعي الدالّة مباشرةً.
router.include_router(folders_router)

settings = get_settings()


# ── حدود صفحة المكتبة ──────────────────────────────────────────────────
#
# **قائمةٌ بلا حدّ ليست قائمة.** كان المسار يردّ كل ملفات المستأجر دفعةً
# واحدة، وكل ملفٍ يزيدها. فمكتبةٌ تكبر تُبطئ نفسها بنفسها حتى تسقط —
# وذلك ما شكاه صاحبها: «المكتبة ما تتحمل كتب».
DEFAULT_PAGE = 25
MAX_PAGE = 100

# **الجذر يُطلب باسمه.** غيابُ `folder` يعني «كل الملفات» — وهو ما تحتاجه
# قوائم الاختيار في شاشات أخرى، وما كان يفعله المسار قبل المجلَّدات. أمّا
# `folder=root` فتعني جذر المكتبة وحده. ولو دلّ الغياب على الجذر لاختفت من
# قوائم الاختيار كلُّ ورقةٍ نظّمها الباحث في مجلَّد — نقصٌ صامت لا رسالةَ له.
ROOT = "root"


def _parsed_folder(folder_id: str | None) -> uuid.UUID | None:
    """معرّف مجلَّدٍ من نموذجٍ متعدّد الأجزاء — والفراغ جذرٌ لا خطأ.

    `FormData` في المتصفح لا يعرف `null`؛ حقلٌ لم يُملأ يصل نصًّا فارغًا.
    ولو عومل الفراغ خطأً لفشل كل رفعٍ من جذر المكتبة.
    """
    if not folder_id:
        return None
    try:
        return uuid.UUID(folder_id)
    except ValueError as exc:
        raise NotFound("library.folder_not_found") from exc


def _folder_scope(folder: str | None) -> tuple[bool, uuid.UUID | None]:
    """(أيُقيَّد بمجلَّد؟، أيّ مجلَّد) — و`None` مع `True` تعني الجذر."""
    if folder is None:
        return False, None
    if folder == ROOT:
        return True, None
    try:
        return True, uuid.UUID(folder)
    except ValueError as exc:
        raise NotFound("library.folder_not_found") from exc


@router.get("", response_model=list[LibraryFile])
async def list_files(
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    after: uuid.UUID | None = Query(default=None),
    folder: str | None = Query(default=None,
                               description="root للجذر، أو معرّف مجلَّد، أو لا شيء لكل الملفات"),
    trash: bool = Query(default=False),
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

    **والمجلَّد شرطٌ في العبارة نفسها، لا مرشِّحٌ بعدها.** `folder_id` عمودٌ
    مفهرس مع `(tenant_id, created_at, id)`، فالصفحة تُقتطع في القاعدة كما
    كانت: عبارةٌ واحدة لكل صفحة مهما بلغ عدد المجلَّدات وعمقُها. ولا يُقرأ
    مجلَّدٌ فرعيّ ولا تُحمَّل ذرّية — القائمة هي المجلَّد الحاليّ وحده.

    **وما في السلّة ليس في المكتبة.** والقائمتان لا تختلطان: `trash=true`
    تعرض المحذوف وحده، وهو الباب الذي تُستعاد منه الملفات.
    """
    scoped, folder_id = _folder_scope(folder)
    page = (
        select(File)
        .where(File.tenant_id == principal.tenant_id,
               File.trashed_at.is_not(None) if trash else File.trashed_at.is_(None))
        .order_by(File.created_at.desc(), File.id.desc())
        .limit(limit)
    )
    if scoped and not trash:
        page = (page.where(File.folder_id == folder_id) if folder_id is not None
                else page.where(File.folder_id.is_(None)))
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
               window.c.created_at, thesis_id, run_status, candidates, reviewed,
               window.c.folder_id, window.c.trashed_at)
        .order_by(window.c.created_at.desc(), window.c.id.desc())
    )).all()

    listing: list[LibraryFile] = []
    for row in rows:
        processing, seen, done, thesis = workspace.file_processing_state_of_row(
            row[7], row[8], row[9], row[10])
        listing.append(LibraryFile(
            id=row[0], original_filename=row[1], content_type=row[2],
            size_bytes=row[3], classification=row[4], status=row[5],
            created_at=row[6], processing_status=processing,
            thesis_id=thesis, candidates=seen, reviewed=done,
            folder_id=row[11], trashed_at=row[12]))
    return listing


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
    # **الملف ينزل حيث يقف الباحث.** والرفع إلى الجذر ثم نقلٌ ثانٍ يترك
    # نافذةً يظهر فيها الملف في غير موضعه، ويكلّف طلبًا زائدًا على كل رفع.
    folder_id: str | None = Form(default=None),
    principal: Principal = Depends(get_principal),
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
    # صيغةُ المعرّف تُفحص قبل بثّ بايت — وأمّا وجودُ المجلَّد والمنحةُ عليه
    # فداخل المعاملة أدناه، حيث تُقرأ القاعدة أصلًا.
    target_folder = _parsed_folder(folder_id)

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
    #
    # **وفي خيطٍ جانبي، لا في حلقة الأحداث.** `upload_fileobj` استدعاءٌ
    # متزامن يحجز الخيط حتى يفرغ الرفع كله. وكان يُستدعى مباشرةً هنا،
    # فيتوقّف الـAPI بأسره طوال بثّ الملف إلى التخزين: لا صفحةٌ تُحمَّل،
    # ولا استطلاعُ مكتبةٍ يُجاب، ولا حتى فحص الصحّة يردّ — وآلة Fly واحدة
    # بمعالجٍ مشترك. فكتابٌ بمئة ميجابايت لا يُبطئ رفعه وحده، بل **يُجمّد
    # المنتج كله** لمن يستعمله في تلك اللحظة. وهذا وجهٌ من «المكتبة ما
    # تتحمل كتب» لا يظهر في سجلّ أخطاء: لا خطأ، بل صمت.
    #
    # ولا يُغيَّر الترتيب: التخزين قبل القاعدة كما كان.
    await upload.seek(0)
    started = perf_counter()
    await run_in_threadpool(storage.get_store().put_stream, key, upload.file, declared)
    elapsed_ms = int((perf_counter() - started) * 1000)

    # ── القاعدة: معاملةٌ تُختم **قبل** أن يُبلَّغ نجاح ──
    #
    # **و«تم الحفظ» كانت تُقال قبل أن تُحفظ.** الجلسة كانت تبعيةً
    # (`Depends(get_session)`)، وFastAPI يُنهي التبعيات المولِّدة **بعد**
    # إرسال جسم الاستجابة: `response = await f(request)` ثم
    # `await response(scope, receive, send)` ثم يخرج المكدّس الذي يحمل
    # الجلسة. فالإيداع يقع بعد أن يقرأ المتصفح ٢٠١.
    #
    # وأثره ليس نظريًّا: الواجهة تقرأ المكتبة فور وصول ٢٠١، والقراءة طلبٌ
    # آخر على **اتصالٍ آخر** — فقد تسبق الإيداع فلا ترى الصفّ. فيرى الباحث
    # «تم الحفظ» ومكتبته خالية من ملفه، ثم يجده بعد تنقّلٍ كامل. وذلك عين
    # ما سقطت عليه رحلة القبول ثلاث مرات.
    #
    # فتُفتح المعاملة هنا وتُختم هنا — وهو النمط نفسه في `routers/auth.py`
    # لمن يحتاج ختمًا قبل الردّ — ولا يُعاد «تم» إلا وقد استقرّ الاثنان:
    # الكائن في التخزين، والصفّ في القاعدة.
    try:
        async with tenant_session(principal.tenant_id, principal.user_id) as session:
            if target_folder is not None:
                await library.get_folder(session, tenant_id=principal.tenant_id,
                                         folder_id=target_folder)
                await rbac.require_object_action(
                    session, principal.tenant_id, principal.user_id,
                    FOLDER_OBJECT_TYPE, target_folder, "write")
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
                folder_id=target_folder,
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
        # والإيداع داخل النطاق أعلاه، فسقوطُه يُمسك هنا أيضًا — لا بعد الردّ.
        await run_in_threadpool(storage.get_store().delete, key)
        raise

    # `expire_on_commit=False` يبقي الحقول محمَّلة بعد الإيداع، فلا قراءة
    # على جلسةٍ مغلقة.
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

    # **والتسليم بثٌّ لا تحميل.** كانت الصياغة `get(...)` ثم `iter([data])`:
    # الكائن كله في ذاكرة العملية قبل أن يُرسل منه بايت. فرسالةٌ ممسوحة
    # بنصف جيجابايت على آلةٍ بنصف جيجابايت ذاكرة ليست تنزيلًا بطيئًا — هي
    # نفاد ذاكرة يقتل العملية ويُسقط معها كل طلبٍ آخر جارٍ.
    #
    # و`get_object` نفسها استدعاءٌ متزامن، فتُنفَّذ في خيطٍ جانبي: فتحُ
    # المجرى لا يُجمّد حلقة الأحداث. وStarlette يستهلك المُكرِّر المتزامن
    # في خيطٍ جانبي أيضًا، فلا يعود شيءٌ من مسار التنزيل يحجز الحلقة.
    stream = await run_in_threadpool(storage.get_store().get_stream, record.storage_key)

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
        stream,
        media_type=record.content_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{storage.safe_filename(record.original_filename)}"',
            "Cache-Control": "private, no-store",
        },
    )


# ══════════════════════════════════════════════════════════════════════
# تنظيم المكتبة: نقلٌ إلى مجلَّد، وحذفٌ هو نقلٌ إلى سلّة
# ══════════════════════════════════════════════════════════════════════
async def _owned_file(session: AsyncSession, principal: Principal,
                      file_id: uuid.UUID, action: str) -> File:
    record = (await session.execute(select(File).where(
        File.id == file_id, File.tenant_id == principal.tenant_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, action)
    return record


async def _active_project_links(session: AsyncSession, principal: Principal,
                                file_id: uuid.UUID) -> int:
    return (await session.execute(
        select(func.count(ProjectFile.id)).where(
            ProjectFile.tenant_id == principal.tenant_id,
            ProjectFile.file_id == file_id,
            ProjectFile.state == ProjectFile.ACTIVE)
    )).scalar_one()


@router.post("/{file_id}/move", response_model=FileResponse)
async def move_file(
    file_id: uuid.UUID,
    payload: FileMoveRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """نقلُ ملفٍّ إلى مجلَّد — و`folder_id: null` تعيده إلى الجذر.

    **وهذا كلُّ ما يقع: عمودٌ واحد يتغيّر.**

    ولا يُمسّ `storage_key`. المفتاح يُبنى مرّة عند الرفع، وتشير إليه
    الروابط الموقّعة وسجلّ `provenance` موضعًا للأصل — فنقلُ الكائن في
    المخزن مع كل تغيير مجلَّد يكسر الاثنين، ولا يشتري شيئًا: المجلَّد صفٌّ
    في القاعدة لا مسارٌ في نظام ملفات.

    ولا يُمسّ ربطُ الملف ببحث، ولا حالُ استعمال مصدره، ولا اعتمادُ مرشّحٍ
    استُخرج منه، ولا استشهادٌ بُني عليه. **فالمجلَّد تنظيمٌ لا حالُ دليل**،
    ومن رتّب مكتبته لا يجوز أن يجد ورقته وقد فقدت سندها.
    """
    record = await _owned_file(session, principal, file_id, "write")
    if payload.folder_id is not None:
        await library.get_folder(session, tenant_id=principal.tenant_id,
                                 folder_id=payload.folder_id)
        await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                         FOLDER_OBJECT_TYPE, payload.folder_id, "write")

    before = record.folder_id
    record.folder_id = payload.folder_id
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.file_moved",
        object_type="file", object_id=file_id, actor_user_id=principal.user_id,
        state_before={"folder_id": str(before) if before else None},
        state_after={"folder_id": str(payload.folder_id) if payload.folder_id else None},
        reason="a folder change is organisation only: storage key, project links and "
               "evidence state are untouched",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return FileResponse.model_validate(record, from_attributes=True)


@router.post("/{file_id}/trash", response_model=FileTrashView)
async def trash_file(
    file_id: uuid.UUID,
    payload: TrashRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileTrashView:
    """«حذف» ملفٍّ = نقلُه إلى السلّة. **ولا يُتلَف شيء هنا.**

    الكائن باقٍ في المخزن، والصفّ باقٍ بكل حقوله، وربطُه ببحوثه باقٍ كما
    هو — والاستعادة ترجعه كما كان. والإتلاف الحقيقي قرارٌ ثانٍ مستقل لا
    يقع بأثرٍ جانبي لهذا المسار، ولا يُبنى إلا بعد أن يُقال للباحث ما
    ينكسر: `unlink ≠ delete` فلسفةُ المنصّة، لا رأيًا في هذه الشاشة.

    **ويُقال ما يترتّب قبل أن يقع، لا بعده.** ملفٌّ مرتبط ببحوث يختفي من
    مكتبة صاحبه، فيُردّ 409 بعدد البحوث التي تستعمله، ولا يمضي إلا بإقرارٍ
    صريح. والتحذير الصامت — أو الذي لا يُذكر فيه عدد — ليس تحذيرًا.
    """
    record = await _owned_file(session, principal, file_id, "delete")
    links = await _active_project_links(session, principal, file_id)
    if links and not payload.confirm:
        raise AtheraError("library.file_linked_to_projects", status_code=409,
                          projects=links)
    if record.trashed_at is None:
        record.trashed_at = dt.datetime.now(dt.UTC)
        record.trashed_by = principal.user_id
        await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.file_trashed",
        object_type="file", object_id=file_id, actor_user_id=principal.user_id,
        state_before={"trashed_at": None},
        state_after={"trashed_at": "now", "project_links": links},
        reason="deleting a file moves it to the trash; the object, the row and its "
               "project links all survive",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return FileTrashView(id=file_id, trashed_at=record.trashed_at, project_links=links)


@router.post("/{file_id}/restore", response_model=FileResponse)
async def restore_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """استعادةٌ من السلّة إلى **موضعها الأول**، لا إلى الجذر.

    ومجلَّدٌ في السلّة يوقف الاستعادة برسالةٍ تقول ما يلزم فعله. والبديل —
    إعادةٌ صامتة إلى الجذر — تنقل الملف من حيث تركه صاحبه بلا أن يُقال له،
    فيبحث عنه حيث كان فلا يجده، ويظنّ الاستعادة فشلت.
    """
    record = await _owned_file(session, principal, file_id, "write")
    if record.trashed_at is None:
        raise AtheraError("library.file_not_in_trash", status_code=409)
    if record.folder_id is not None:
        folder = (await session.execute(select(LibraryFolder).where(
            LibraryFolder.id == record.folder_id,
            LibraryFolder.tenant_id == principal.tenant_id))).scalar_one_or_none()
        if folder is None or folder.trashed_at is not None:
            raise AtheraError("library.parent_in_trash", status_code=409)

    record.trashed_at = None
    record.trashed_by = None
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.file_restored",
        object_type="file", object_id=file_id, actor_user_id=principal.user_id,
        state_before={"trashed_at": "set"}, state_after={"trashed_at": None},
        reason="the trash is a waiting room; restoring returns the file where it was",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return FileResponse.model_validate(record, from_attributes=True)
