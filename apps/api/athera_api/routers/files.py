"""الملفات | Files (§29.2، §36.2، §33.3).

الرفع لا يُعتمد إلا ببصمة مطابقة، وكل ملف يحمل سجل provenance كامل، وكل
تنزيل يُسجَّل — بلا استثناء.
"""
import datetime as dt
import hashlib
import uuid
from time import perf_counter

from fastapi import (
    APIRouter, Depends, File as FormFile, Form, Query, Request, UploadFile, status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import tenant_session_maker
from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.audit import ProvenanceEvent
from ..models.files import File, FileAccessLog
from ..models.identity import ObjectGrant
from ..models.library import LibraryFolder
from ..schemas.files import (
    FileCompleteRequest,
    FileDownloadResponse,
    FileInitRequest,
    FileInitResponse,
    FileResponse,
    LibraryFile,
)
from ..schemas.library import FileMoveRequest, FileTrashView, TrashRequest
from ..models.thesis import Thesis
from ..services import audit, idempotency, library, rbac, storage, workspace
from ..services.thesis import processing as thesis_processing
from ..transaction import TransactionalRoute
from .folders import router as folders_router
from .library_bulk import router as bulk_router

# مقطع الميجابايت: يوازن بين عدد الدورات وبصمة الذاكرة.
CHUNK_BYTES = 1024 * 1024

router = APIRouter(prefix="/api/v1/files", tags=["files"], route_class=TransactionalRoute)

# **الضمّ هنا قبل كل شيء، لا في آخر الملف.** FastAPI يوفّق المسارات
# بترتيب تسجيلها، و`GET /{file_id}` يسبق ما يُسجَّل بعده — فلو ضُمّ موجّه
# المجلَّدات في الأسفل لالتقط `‎/api/v1/files/folders` مسارُ المعرّف أولًا،
# وفشل تحويل «folders» إلى UUID، فيردّ 422 على قائمةٍ صحيحة. والترتيب هو
# كل الفرق، ولا يظهر في أي اختبار وحدة يستدعي الدالّة مباشرةً.
#
# والأفعالُ الجماعية كذلك: `‎/api/v1/files/bulk/move` يلتقطه
# `POST /{file_id}/move` لو سُجّل بعده، فيحاول قراءة «bulk» معرّفًا ويردّ
# 422 على فعلٍ صحيح.
router.include_router(folders_router)
router.include_router(bulk_router)

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


async def _writable_folder(session: AsyncSession, principal: Principal,
                           folder_id: uuid.UUID) -> None:
    """الوجهة قائمةٌ ومملوكة — والفحص نفسه يقرأه المفرد والجماعيّ.

    والتعريف في `services/library.py` لا هنا: الفعلُ الجماعيّ في موجّهٍ
    ثانٍ، ونسخةٌ ثانية من الحارس تفترق عن الأولى بأول تعديل — فيُشدَّد
    المفرد ويبقى الجماعيّ يقبل ما لا يقبله، وهو أخطرهما لأنه يمرّ على
    عشرين ملفًا لا على واحد.
    """
    await library.assert_writable(session, tenant_id=principal.tenant_id,
                                  user_id=principal.user_id, folder_id=folder_id)


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


# ── مرشّحات المكتبة: **حالٌ يعرفها الخادم، لا زينةٌ في الشاشة** ─────────
#
# سبعة خياراتٍ لا أكثر، وكلٌّ منها شرطٌ في العبارة نفسها. وأربعةٌ منها
# نوعُ ملفٍ يُقرأ من `content_type`، وثلاثةٌ حالُ معالجةٍ تُشتقّ من
# `extraction_runs` — وهي بعينها الحال المعروضة في البطاقة، لا حسابٌ ثانٍ.
#
# **ولا مرشّح لما لا يعرفه الخادم.** «مقروء» و«مهمّ» و«حديث» أوصافٌ لا
# أعمدة؛ وزرٌّ يَعِد بتصفيةٍ لا يقدر عليها الخادم يردّ قائمةً لا تطابق
# اسمه — وذلك أسوأ من غياب الزرّ.
FILE_KIND_FILTERS = ("pdf", "docx", "datasets", "references")
FILTERS = FILE_KIND_FILTERS + workspace.LIBRARY_STATE_FILTERS


def _kind_predicate(kind: str):
    """شرطُ نوع الملف — من جداول `storage` نفسها لا من قائمةٍ ثانية."""
    if kind == "pdf":
        return File.content_type == storage.PDF_TYPE
    if kind == "docx":
        return File.content_type == storage.DOCX_TYPE
    if kind == "datasets":
        return File.content_type.in_(sorted(storage.DATASET_TYPES))
    # المراجع: نوعُها الخاص، أو امتدادُها حين يصل النوع `text/plain` من
    # المتصفح — والاثنان ملفُ مراجعٍ عند صاحبه.
    return or_(
        File.content_type.in_(sorted(storage.REFERENCE_TYPES)),
        *[File.original_filename.ilike(f"%{suffix}")
          for suffix in storage.REFERENCE_SUFFIXES],
    )


def _filter_predicate(kind: str | None, tenant_id: uuid.UUID):
    """الشرط المقابل للمرشّح المطلوب — **ومرشّحٌ مجهول يُردّ لا يُتجاهل**.

    وتجاهلُه أسوأ: الباحث يضغط «مراجع» فيرى مكتبته كلها، ويظنّ أن هذه هي
    مراجعه. فيُقال إن الخيار غير معروف بـ422 وتُذكر الخيارات كلها.
    """
    if kind is None:
        return None
    if kind in FILE_KIND_FILTERS:
        return _kind_predicate(kind)
    state = workspace.file_state_predicate(tenant_id, kind)
    if state is None:
        raise AtheraError("library.unknown_filter", status_code=422,
                          filters=", ".join(FILTERS))
    return state


@router.get("", response_model=list[LibraryFile])
async def list_files(
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    after: uuid.UUID | None = Query(default=None),
    folder: str | None = Query(default=None,
                               description="root للجذر، أو معرّف مجلَّد، أو لا شيء لكل الملفات"),
    trash: bool = Query(default=False),
    q: str | None = Query(default=None, max_length=200,
                          description="بحثٌ نصّي في اسم الملف وعنوان رسالته"),
    kind: str | None = Query(default=None,
                             description=" · ".join(FILTERS)),
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

    **والبحث والتصفية شرطان في العبارة نفسها — لا مرشِّحان بعدها.**

    و`q` بحثٌ نصّيّ لا دلاليّ: اسمُ الملف، وعنوانُ رسالته حيث وُجدت. ونطاقُه
    هو `folder` نفسه — فبمعرّف مجلَّدٍ يبحث في هذا الرفّ وحده، وبغيابه في
    المكتبة كلها. ولا معامل «نطاق» ثالث يقول ما يقوله الأول.

    و`kind` واحدٌ من سبعةٍ **يعرفها الخادم**: أربعةُ أنواعٍ تُقرأ من
    `content_type`، وثلاثُ حالاتٍ تُشتقّ من `extraction_runs` — وهي بعينها
    الحال المعروضة في البطاقة، فلا يقول المرشّح غير ما تقوله.

    **والتصفية في القاعدة لا في بايثون.** ولو صُفّيت الصفحة بعد قراءتها
    لعادت ناقصةً بلا معنى: خمسةٌ وعشرون صفًّا يُقرأون فيبقى منهم ثلاثة، ثم
    يُقال للباحث إن هذه كلُّ ما يطابق — وهو كذب. والشرط في `WHERE` يُبقي
    الصفحة صفحةً وعددَ العبارات واحدًا كما كان.
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
    matching = workspace.file_text_predicate(principal.tenant_id, q) if q else None
    if matching is not None:
        page = page.where(matching)
    chosen = _filter_predicate(kind, principal.tenant_id)
    if chosen is not None:
        page = page.where(chosen)
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
    request: Request,
    payload: FileInitRequest,
    principal: Principal = Depends(get_principal),
) -> FileInitResponse | JSONResponse:
    """نيّةُ رفعٍ عبر رابطٍ موقّع — **والملف ينزل حيث يقف الباحث**.

    **وكان ينزل في الجذر دائمًا.** هذا المسار لم يكن يعرف `folder_id`
    أصلًا، بينما يعرفه الرفعُ المباشر؛ فمن رفع من داخل «كتب المنهج» بعميلٍ
    يستعمل الرابط الموقّع وجد ملفه في جذر المكتبة، ولا رسالةَ ولا سبب.
    وكان البديل الوحيد نقلًا ثانيًا بعد الختم: طلبٌ زائد على كل رفع، ونافذةٌ
    يظهر فيها الملف في غير موضعه، وسقوطٌ صامت لو فشل النقل بعد نجاح الرفع.

    **والفحص هنا لا عند الختم وحده.** الوجهة تُفحص **قبل** أن يُصدر الخادم
    رابطًا موقّعًا: فرفضٌ بعد أن يبثّ الباحث كتابه إلى المخزن هو الوعد
    يُقطع بعد أن دُفع ثمنه. والصفّ يُكتب بموضعه في المعاملة نفسها التي
    فُحص فيها المجلَّد.

    **ومن ذلك يلزم أثرٌ حسن:** المجلَّد الذي فيه رفعٌ معلَّق لا يُحذف —
    `trash_folder` يعدّ الملفات القائمة فيه ومنها المعلَّق، فيردّ
    `library.folder_not_empty`. فلا يُختم رفعٌ في مجلَّدٍ صار في السلّة
    بينما كان الباحث يبثّ.

    **ولا يمسّ المجلَّدُ مفتاحَ التخزين.** المفتاح يُبنى من المستأجر
    ومعرّف الملف، ولا يُحشر فيه مسارٌ: الموضع صفٌّ في القاعدة، والمفتاح
    عنوانُ كائنٍ يشير إليه كلُّ رابطٍ موقّع وكلُّ سجلّ إسناد.
    """
    storage.validate_upload(payload.content_type, payload.size_bytes)

    # ══ الهُويّةُ أوّلًا، والتوقيعُ خارج كلّ معاملة (RC-T1-H2-B3) ══
    #
    # **والرابطُ الموقّعُ قدرةٌ عابرة، لا جزءٌ من الجواب المخزون.** لو
    # خُزّن في `idempotency_records.response_body` لَأعادت إعادةٌ بعد يومٍ
    # رابطًا ميّتًا: توقيعُه انتهى، والعميلُ يراه جوابًا ناجحًا. فيُخزَّن
    # **ما يدوم** (الهُويّة والمفتاح والموضع والمدّة)، ويُوقَّع من جديدٍ
    # عند كلّ إعادة.
    #
    # و`presign_put` يعدّها الماسحُ عمليّةَ تخزين، فلا تمتدّ عليها معاملة:
    # تُحسب الهُويّةُ بدوالَّ نقيّة، ثمّ تُفتح المعاملةُ وتُغلق، ثمّ
    # يُوقَّع. ولا رحلةَ شبكةٍ في التوقيع أصلًا — لكنّ الترتيبَ يبقى
    # صادقًا مع القاعدة لا مع ما نظنّه عن المُنفِّذ.
    body = payload.model_dump(mode="json")
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)
    file_id = uuid.uuid4()
    key = storage.build_storage_key(principal.tenant_id, file_id, payload.filename)

    async with maker() as session:
        # ══ التفويضُ **قبل** تحكيمِ المفتاح (RC-T1-H2-B3) ══
        #
        # **وكان بعدَه وفي فرعِ العملِ الجديد وحدَه.** فمن سُحبت صلاحيّتُه
        # على المجلَّد كان يستعمل مفتاحًا قديمًا فيُسلك مسلكَ الإعادة —
        # ولا يُفحص شيء — فيُمنَح **قدرةَ كتابةٍ جديدة** إلى وجهةٍ لم يعد
        # يملكها. فلا يُتجاوَز فحصٌ لأنّ صفَّ حجزٍ موجود.
        if payload.folder_id is not None:
            await _writable_folder(session, principal, payload.folder_id)

        guard = idempotency.LeaseGuard()
        if idempotency.is_keyed(request):
            guard = await idempotency.begin_leased_in(
                session, request, tenant_id=principal.tenant_id,
                actor_user_id=principal.user_id, body=body,
                ttl=idempotency.LEASE_STORAGE, replay_as_value=True)
            if guard.answer is not None:
                return guard.answer
            if guard.stable_id is not None:
                # **والهُويّةُ بعد اكتساب الجيل لا قبله**: مرساتُها صفُّ
                # الإجارة، فلا تُعرَف إلّا بعد أن يُعرَف الجيل.
                file_id = guard.stable_id
                key = storage.build_storage_key(
                    principal.tenant_id, file_id, payload.filename)

        if guard.replay is not None:
            # ══ إعادةٌ تُجدّد قدرةً — **وللقدرةِ شرطٌ** ══
            #
            # الرابطُ الموقّعُ إذنُ كتابةٍ إلى مفتاحٍ بعينه. وكان يُجدَّد
            # بمجرّد وجود صفِّ حجزٍ مُتَمّ — **ولو كان الملفُّ قد خُتم
            # وصار `stored`**. فيُمنَح إذنُ كتابةٍ فوق كائنٍ نهائيّ:
            # فتتبدّل بايتاتُه، وتبقى `checksum_sha256` وحجمُه وإسنادُه
            # تصف ما كان. وذاك إفسادُ بيانات، لا إعادةُ جوابٍ.
            #
            # فيُعاد تحميلُ الصفّ **في هذه المعاملة**، ويُفحص التفويضُ
            # الحاضر، ويُشترط أنّه ما زال قابلًا للرفع. وإلّا فـ٤٠٩ صادقة
            # — ولا رابطَ، ولا مساسَ بالصفّ ولا بصفِّ الحجز.
            stored = guard.replay.body or {}
            file_id = uuid.UUID(str(stored["file_id"]))
            key = str(stored["storage_key"])
            folder_id = (uuid.UUID(str(stored["folder_id"]))
                         if stored.get("folder_id") else None)

            live = (await session.execute(
                select(File).where(File.id == file_id,
                                   File.tenant_id == principal.tenant_id)
            )).scalar_one_or_none()
            if live is None:
                raise NotFound("file.not_found")
            await rbac.require_object_action(
                session, principal.tenant_id, principal.user_id,
                "file", file_id, "write")
            if live.status != "pending" or live.trashed_at is not None:
                raise AtheraError("file.upload_not_pending", status_code=409,
                                  file_id=str(file_id), status=live.status)
            # والمفتاحُ يُقرأ من الصفّ الحاضر لا من المخزون وحدَه، فلا
            # يُوقَّع مفتاحٌ لا يملكه هذا الصفّ.
            key = live.storage_key
            folder_id = live.folder_id
        else:
            folder_id = payload.folder_id
            # **والصفُّ المعلَّق جزءٌ من المصالحة لا يتيمٌ يُتجاوَز.**
            # مُستولٍ بعد انتهاء إجارةٍ يجد صفَّه بهُويّته الثابتة فيُعيد
            # استعماله — ولا يُنشئ ثانيًا ولا منحةً ثانيةً ولا حدثًا ثانيًا.
            existing = (await session.execute(
                select(File).where(File.id == file_id,
                                   File.tenant_id == principal.tenant_id)
            )).scalar_one_or_none()
            if existing is None:
                session.add(File(
                    id=file_id,
                    tenant_id=principal.tenant_id,
                    storage_key=key,
                    original_filename=payload.filename,
                    content_type=payload.content_type,
                    size_bytes=payload.size_bytes,
                    classification=payload.classification,
                    is_untrusted_content=True,  # §33.3 — المحتوى بيانات لا تعليمات.
                    status="pending",
                    uploaded_by=principal.user_id,
                    folder_id=payload.folder_id,
                ))
                await session.flush()
                session.add(ObjectGrant(
                    tenant_id=principal.tenant_id, object_type="file",
                    object_id=file_id, user_id=principal.user_id,
                    grant_level="owner", granted_by=principal.user_id,
                ))
                await audit.record(
                    session,
                    tenant_id=principal.tenant_id,
                    action="file.upload_initiated",
                    object_type="file",
                    object_id=file_id,
                    actor_user_id=principal.user_id,
                    state_after={
                        "filename": payload.filename,
                        "classification": payload.classification,
                        "folder_id": str(payload.folder_id) if payload.folder_id else None,
                    },
                    request_id=principal.request_id,
                    ip_address=principal.ip_address,
                )
            # **ولا رابطَ ولا توقيعَ في المخزون** — الدائمُ وحده.
            await idempotency.settle_leased(
                session, guard, status=status.HTTP_201_CREATED,
                body={
                    "file_id": str(file_id), "storage_key": key,
                    "folder_id": str(folder_id) if folder_id else None,
                    "expires_in": settings.s3_presign_ttl_seconds,
                })

    # ── التوقيعُ بعد إغلاق المعاملة، ويُولَّد طازجًا في كلّ مرّة ──
    answer = FileInitResponse(
        file_id=file_id,
        upload_url=storage.presign_put(key, payload.content_type),
        storage_key=key,
        expires_in=settings.s3_presign_ttl_seconds,
        folder_id=folder_id,
    )
    if guard.replay is not None:
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=jsonable_encoder(answer),
            headers={idempotency.REPLAYED_HEADER: "true"})
    return answer


@router.post("/{file_id}/complete", response_model=FileResponse)
async def complete_upload(
    request: Request,
    file_id: uuid.UUID,
    payload: FileCompleteRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FileResponse | JSONResponse:
    """ختمُ الرفع الموقّع — **والموضع الذي أُعلن عند النيّة هو الذي يستقرّ**.

    **والسكوتُ يُبقي، لا يُلغي.** جسمٌ بلا `folder_id` — وهو كل عميلٍ كُتب
    قبل هذا التغيير — يترك الملف حيث أعلنت النيّة أنه سينزل. ولو عومل
    الغياب معاملة «الجذر» لسحب كلُّ عميلٍ قديم ملفَّه إلى الجذر عند الختم،
    فيصير المسار يعِد بموضعٍ ثم ينقضه في آخر خطوة.

    وذكرُ الحقل صراحةً قولٌ أخير: الباحث غيّر وجهته بين النيّة والختم،
    فيُفحص المجلَّد الجديد كما فُحص الأول — وجودًا ومستأجرًا ومنحة.

    **ولا يتغيّر `storage_key` هنا ولا هناك.** سجلّ الإسناد أدناه يذكره
    موضعًا للأصل، والمجلَّد لا يعدّل فيه حرفًا.
    """
    record = (await session.execute(select(File).where(File.id == file_id,
                                            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
    if record is None:
        raise NotFound("file.not_found")
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     "file", file_id, "write")

    # ══ الحجزُ **بعد** التفويض (RC-T1-H2-B3) ══
    #
    # فالحجزُ ليس بوّابةَ وصول: من لا يملك الكتابةَ يُردّ ٤٠٣ ولا يحجز
    # مفتاحًا، ولا يُفشي وجودَ ملفٍّ ليس له بأن يُردّ بتعارضِ مفاتيح.
    #
    # وهذا مسارٌ **ذرّيٌّ في القاعدة** لا انتظارَ خارجيًّا فيه: فلا إجارة،
    # بل حجزٌ في معاملة الطلب نفسِها كما في الطور A. والمعرّفُ والتجزئةُ
    # والموضعُ في البصمة — فمفتاحٌ أُعيد على ملفٍّ آخر أو بتجزئةٍ أخرى
    # تعارضٌ يُردّ، ولا يُكتب إسنادٌ ثانٍ ولا حدثُ ختمٍ ثانٍ.
    claim = await idempotency.begin(
        request, session,
        tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
        body={
            "file_id": str(file_id),
            "checksum_sha256": payload.checksum_sha256,
            "folder_named": payload.folder_named,
            "folder_id": str(payload.folder_id) if payload.folder_id else None,
        })
    if claim.answer is not None:
        return claim.answer

    if payload.folder_named and payload.folder_id is not None:
        await _writable_folder(session, principal, payload.folder_id)

    before_folder = record.folder_id
    if payload.folder_named:
        record.folder_id = payload.folder_id
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
        state_before={"status": "pending",
                      "folder_id": str(before_folder) if before_folder else None},
        state_after={"status": "stored", "checksum_sha256": payload.checksum_sha256,
                     "folder_id": str(record.folder_id) if record.folder_id else None},
        request_id=principal.request_id,
    )
    answer = FileResponse.model_validate(record, from_attributes=True)
    await claim.finish(session, status=200, body=jsonable_encoder(answer))
    return answer


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
    request: Request,
    upload: UploadFile = FormFile(...),
    classification: str = Form(default="C2"),
    # **الملف ينزل حيث يقف الباحث.** والرفع إلى الجذر ثم نقلٌ ثانٍ يترك
    # نافذةً يظهر فيها الملف في غير موضعه، ويكلّف طلبًا زائدًا على كل رفع.
    folder_id: str | None = Form(default=None),
    principal: Principal = Depends(get_principal),
) -> FileResponse | JSONResponse:
    """رفع يمرّ بالخادم لا بالمتصفح إلى التخزين.

    **لماذا لا رابط موقّع هنا؟** لأن ترويسة CSP تحصر اتصال المتصفح بالـAPI
    وحده (§38.6.8)، والرفع المباشر يُحجب صامتًا. والمرور بالخادم يبقي مضيف
    التخزين مخفيًا عن المتصفح، ويجعل التحقق من المحتوى ممكنًا قبل الحفظ —
    وهو ما لا يستطيعه رابط موقّع أصلًا. والمسار الموقّع باقٍ لمن يحتاجه.

    **الترتيب مقصود: التخزين أولًا ثم القاعدة.** فشل التخزين لا يترك سجلًّا
    يتيمًا يدّعي ملفًا لا وجود له، وفشل القاعدة يحذف الكائن قبل أن يُبلَّغ
    نجاح. ولا يُعاد «تم» إلا بعد تأكّد الاثنين.
    """
    return await store_uploaded_file(
        request=request, upload=upload, classification=classification,
        folder_id=folder_id, principal=principal)


async def store_uploaded_file(
    *,
    request: Request | None,
    upload: UploadFile,
    classification: str,
    folder_id: str | None,
    principal: Principal,
) -> FileResponse | JSONResponse:
    """متنُ الرفع — و`request=None` تعني **المسلكَ القديم حرفيًّا**.

    ولهذا موضعٌ واحد: `document_intelligence.upload_thesis` ينادي هذا
    المتنَ دالّةً لا عبر HTTP. ورفعُ الرسالة **خارج نطاق الطور B-3**
    (موعدُه B-5)، فلا يُقحَم فيه حجزٌ ولا هُويّةٌ مشتقّة: لو مُرِّر طلبُ
    الرسالة هنا لَصار مفتاحٌ يُرسَل إلى `/thesis/upload` يحجز باسم عمليّةٍ
    أخرى، ثمّ تُعاد `JSONResponse` إلى مُنادٍ ينتظر `FileResponse` فيسقط
    على `stored.id`. فالفصلُ صريحٌ هنا، لا مضمَرٌ في ترتيب المعاملات.
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

    checksum = digest.hexdigest()

    # ══ تحضيرٌ يُودَع قبل التخزين (RC-T1-H2-B3) ══
    #
    # **والهُويّةُ تُشتقّ ولا تُولَّد.** كان هنا `uuid.uuid4()`، ومنه مفتاحُ
    # التخزين. فإعادةٌ بعد إخفاقٍ **غامض** تُولّد معرّفًا جديدًا ومفتاحًا
    # جديدًا، فيصير لنيّةٍ واحدةٍ كائنان في المخزن أحدُهما بلا صفّ. والهُويّةُ
    # الآن مشتقّةٌ من نطاق المفتاح، فيبلغها المُستولي كما بلغها الأوّل.
    #
    # **وبلا مفتاحٍ لا يُغيَّر شيء**: `uuid4()` كما كان، ولا حجزَ ولا رحلةَ
    # تحضيرٍ إلى القاعدة.
    #
    # والبصمةُ من قيمٍ عاديّة، و`checksum_sha256` فيها **هُويّةُ المحتوى**:
    # فبايتاتٌ أخرى بالمفتاح نفسِه تعارضٌ يُردّ قبل أيّ كتابةٍ ثانية. ولا
    # تُخزَّن البايتاتُ نفسُها في مكان.
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)
    guard = idempotency.LeaseGuard()
    if request is not None and idempotency.is_keyed(request):
        # ══ التفويضُ **قبل** الكتابة، في معاملة التحضير نفسِها ══
        #
        # **وكان بعدها.** فحصُ الوجهة كان في معاملة الإنهاء وحدَها — أي
        # **بعد** بثِّ الملفّ إلى المخزن. فطلبٌ مُمفتَحٌ إلى مجلَّدٍ لا
        # يملكه صاحبُه كان يكتب الكائنَ أوّلًا ثمّ يُردّ ٤٠٣، **والكائنُ
        # المُمفتَحُ لا يُحذف** (وذاك صحيحٌ في الغموض) — فيبقى كائنٌ لا
        # يشير إليه صفٌّ ولا يملكه أحد. وليس ذلك غموضَ مزوّدٍ، بل فحصًا
        # وقع متأخّرًا.
        #
        # فيُفحص هنا: إن رُدّ فصفرُ نداءِ تخزين، وصفرُ حجزٍ مُودَع (المعاملةُ
        # ترجع)، وصفرُ كائن — ويبقى عقدُ ٤٠٣/٤٠٤ كما هو.
        async with maker() as session:
            if target_folder is not None:
                await _writable_folder(session, principal, target_folder)
            guard = await idempotency.begin_leased_in(
                session, request,
                tenant_id=principal.tenant_id, actor_user_id=principal.user_id,
                body={
                    "filename": filename,
                    "content_type": declared,
                    "classification": classification,
                    "folder_id": str(target_folder) if target_folder else None,
                    "size_bytes": size,
                    "checksum_sha256": checksum,
                },
                ttl=idempotency.LEASE_STORAGE)
        if guard.answer is not None:
            # إعادةٌ أو «قائمٌ لغيرك» أو تعارض — **وصفرُ كتابةٍ في المخزن**.
            return guard.answer

    file_id = guard.stable_id or uuid.uuid4()
    key = storage.build_storage_key(principal.tenant_id, file_id, filename,
                                    user_id=principal.user_id)

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
        async with maker() as session:
            # **ويُعاد الفحصُ هنا ولو فُحص في التحضير**: الصلاحيّةُ قد
            # تُسحب بينما الملفُّ يُبَثّ. فإن سُحبت رجعت معاملةُ الإنهاء —
            # ولا يُحذف الكائنُ المُمفتَح عميانًا (فقد يكون لمُستولٍ)،
            # وتنظيفُ المهجورِ حقًّا شأنُ الطور C.
            if target_folder is not None:
                await _writable_folder(session, principal, target_folder)
            # ══ يُنشأ الصفُّ أو **يُعاد استعماله** (RC-T1-H2-B3) ══
            #
            # فالهُويّةُ ثابتة، فقد يكون مُستولٍ سبقنا فأودع صفَّها. ولو
            # أُدرج عميانًا لَسقط على `pk_files` بخطأ ٥٠٠ **قبل** أن يبلغ
            # `settle_leased` — فيُحجب عن العميل الجوابُ الصادق (٤٠٩
            # «فُقدت الإجارة») خلف «خطأ غير متوقّع». وقد قِيس ذلك حرفيًّا.
            #
            # فيُقرأ أوّلًا: فإن وُجد أُعيد استعمالُه بلا منحةٍ ثانيةٍ ولا
            # إسنادٍ ثانٍ ولا حدثِ تدقيقٍ ثانٍ، ثمّ يُسأل السياجُ فيقول
            # كلمتَه — وهي الرجوعُ لمن فقد إجارتَه.
            existing = (await session.execute(
                select(File).where(File.id == file_id,
                                   File.tenant_id == principal.tenant_id)
            )).scalar_one_or_none()
            if existing is not None:
                record = existing
                await idempotency.settle_leased(
                    session, guard, status=status.HTTP_201_CREATED,
                    body=jsonable_encoder(
                        FileResponse.model_validate(record, from_attributes=True)))
                return FileResponse.model_validate(record, from_attributes=True)

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
            answer = FileResponse.model_validate(record, from_attributes=True)
            # **الإنهاءُ في المعاملة نفسِها**: الصفُّ والمنحةُ والإسنادُ
            # والتدقيقُ والإتمامُ معًا أو لا شيء. وعاملٌ بائتٌ يرفع
            # `LeaseSuperseded` هنا فتُرجَع المعاملةُ كلُّها.
            await idempotency.settle_leased(
                session, guard, status=status.HTTP_201_CREATED,
                body=jsonable_encoder(answer))
    except Exception:
        # ══ ولمَ لا يُحذف الكائنُ المُمفتَح (RC-T1-H2-B3) ══
        #
        # بلا مفتاح: المفتاحُ عشوائيٌّ لا يشاركه أحد، فحذفُه عند سقوط
        # القاعدة يمنع كائنًا يتيمًا — **وهو السلوكُ القديم، ويبقى**.
        #
        # وبمفتاح: المفتاحُ **مشتركٌ** بين كلّ محاولات هذه النيّة. فقد
        # يكون مُستولٍ جديدٌ قد كتب الكائنَ نفسَه وأتمّ صفَّه بينما كنّا
        # نسقط؛ فحذفٌ «تنظيفًا» يمحو كائنَ المالكِ القائمِ الصحيح —
        # ويبقى صفُّه يشير إلى عدم. فالكائنُ يبقى **هدفَ مصالحة**:
        # محتواه هو المحتوى نفسُه (البصمةُ تضمن ذلك)، ومفتاحُه هو المفتاح
        # نفسُه. وحذفُ المهجورِ حقًّا شأنُ الطور C لا شأنُ عاملٍ ساقط.
        if guard.lease is None:
            await run_in_threadpool(storage.get_store().delete, key)
        raise

    # `expire_on_commit=False` يبقي الحقول محمَّلة بعد الإيداع، فلا قراءة
    # على جلسةٍ مغلقة.
    return answer


@router.get("/{file_id}/content")
async def stream_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    """بثّ مصادق — بلا رابط عام ولا كشف لمضيف التخزين.

    التخويل يُفحص قبل قراءة بايت واحد، وRLS تمنع أصلًا رؤية سجل مستأجر آخر:
    تخمين معرّف ملف لا يعطي شيئًا.

    **ولا معاملةَ تمتدّ على فتح المجرى** (RC-T1-H3). كانت الجلسةُ تبعيّةً
    (`Depends(get_session)`)، فتبقى معاملةُ الطلب مفتوحةً بينما يُفتح مجرى
    الكائن عند مزوّدِ تخزينٍ في مدينةٍ أخرى — والاتصالُ `idle in transaction`
    طوال ذلك. فالأطوارُ ثلاثةٌ الآن: قراءةٌ وتفويض، ثمّ فتحُ المجرى بلا
    معاملة، ثمّ تسجيلُ الوصول.

    **وهذا عطبٌ كشفه توسيعُ الماسح في هذه الدفعة**: تسليمُ عمليّةِ المخزن
    إلى `run_in_threadpool` لم يكن يُقرأ في `offenders` إلّا حين يناديه
    غيرُه، فكان هذا المسارُ يمرّ. ولا صلةَ له بتحمُّلِ الإعادة — إصلاحُ
    حدٍّ لا غير، ولا يتغيّر عقدُ المسار حرفًا.
    """
    maker = tenant_session_maker(principal.tenant_id, principal.user_id)

    # ── (١) معاملةٌ قصيرة: القراءةُ والتفويض، ثمّ تعبُر قيمٌ عاديّة ──
    async with maker() as session:
        record = (await session.execute(select(File).where(
            File.id == file_id,
            File.tenant_id == principal.tenant_id))).scalar_one_or_none()
        if record is None:
            raise NotFound("file.not_found")
        await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                         "file", file_id, "read")
        storage_key = record.storage_key
        content_type = record.content_type
        filename = record.original_filename

    # **والتسليم بثٌّ لا تحميل.** كانت الصياغة `get(...)` ثم `iter([data])`:
    # الكائن كله في ذاكرة العملية قبل أن يُرسل منه بايت. فرسالةٌ ممسوحة
    # بنصف جيجابايت على آلةٍ بنصف جيجابايت ذاكرة ليست تنزيلًا بطيئًا — هي
    # نفاد ذاكرة يقتل العملية ويُسقط معها كل طلبٍ آخر جارٍ.
    #
    # و`get_object` نفسها استدعاءٌ متزامن، فتُنفَّذ في خيطٍ جانبي: فتحُ
    # المجرى لا يُجمّد حلقة الأحداث. وStarlette يستهلك المُكرِّر المتزامن
    # في خيطٍ جانبي أيضًا، فلا يعود شيءٌ من مسار التنزيل يحجز الحلقة.
    # ── (٢) بلا معاملة: يُفتح المجرى عند المزوّد ──
    stream = await run_in_threadpool(storage.get_store().get_stream, storage_key)

    # ── (٣) معاملةٌ قصيرة: الوصولُ وقع فيُسجَّل ──
    #
    # **وبعد فتح المجرى لا قبله**: تنزيلٌ لم يبدأ لا يُسجَّل أنّه وقع.
    async with maker() as session:
        session.add(FileAccessLog(
            tenant_id=principal.tenant_id, file_id=file_id, user_id=principal.user_id,
            action="download", accessed_at=dt.datetime.now(dt.UTC),
            ip_address=principal.ip_address,
        ))
        await audit.record(
            session, tenant_id=principal.tenant_id, action="file.downloaded",
            object_type="file", object_id=file_id, actor_user_id=principal.user_id,
            request_id=principal.request_id, ip_address=principal.ip_address,
        )
    return StreamingResponse(
        stream,
        media_type=content_type,
        headers={
            "Content-Disposition":
                f'attachment; filename="{storage.safe_filename(filename)}"',
            "Cache-Control": "private, no-store",
        },
    )


# ══════════════════════════════════════════════════════════════════════
# تنظيم المكتبة: نقلٌ إلى مجلَّد، وحذفٌ هو نقلٌ إلى سلّة
# ══════════════════════════════════════════════════════════════════════
async def _owned_file(session: AsyncSession, principal: Principal,
                      file_id: uuid.UUID, action: str) -> File:
    """قراءةٌ محروسة — **والحارس نفسه يقرأه الفعل الجماعيّ**.

    ونسختان منه تفترقان بأول تعديل: يُشدَّد المفرد ويبقى الجماعيّ يقبل ما
    لا يقبله — وهو أخطرهما، فهو يمرّ على عشرين ملفًا لا على واحد.
    """
    return await library.owned_file(session, tenant_id=principal.tenant_id,
                                    user_id=principal.user_id, file_id=file_id,
                                    action=action)


async def _active_project_links(session: AsyncSession, principal: Principal,
                                file_id: uuid.UUID) -> int:
    """كم بحثًا قائمًا يستعمل هذا الملف؟ — والعدد هو التحذير لا نصُّه."""
    return await library.active_project_links(
        session, tenant_id=principal.tenant_id, file_ids=[file_id])


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
        await _writable_folder(session, principal, payload.folder_id)

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

    **وحدٌّ ثانٍ لا يُقايَض**: ملفٌّ تقرؤه مهمّةٌ جاريةٌ الآن لا يُنقل، ولا
    يتجاوز ذلك إقرار. انظر التعليق في الجسم.
    """
    record = await _owned_file(session, principal, file_id, "delete")

    # ── حدٌّ لا يُقايَض: ملفٌّ تقرؤه مهمّةٌ جاريةٌ الآن لا يُنقل ──
    #
    # **والشاشةُ وحدها لم تكن تكفي.** مركزُ الرسائل يُخفي «انقل إلى السلّة»
    # ما دامت المعالجة جارية، وهذه النقطةُ كانت تقبل الطلب على أيّ حال: من
    # نادى الواجهة مباشرةً سحب الملفَّ من تحت مهمّةٍ تقرؤه. **وشاشةٌ تُخفي
    # زرًّا وخادمٌ يقبل الطلبَ حارسٌ واحدٌ لا اثنان.**
    #
    # **ولا عقدَ إلغاءٍ في هذا المنتج** — لا سبيل إلى إيقاف المهمّة ولا إلى
    # تسلسلها مع النقل. فيُردّ الطلب صراحةً بسببه، ولا يُدَّعى إلغاءٌ لا
    # وجود له، ولا يُمسّ صفُّ الرسالة.
    #
    # والمفردةُ `IN_FLIGHT` تُستورَد من موضعها الواحد
    # (`services/thesis/processing.py`): نسختان تفترقان بأوّل تعديل، وأوّلُ
    # موضعٍ ينسى التعديلَ يصير ثغرة.
    #
    # **والشرطُ يسبق فحصَ الارتباط بالبحوث** لأنّه غير قابلٍ للإقرار:
    # `confirm` يتجاوز التحذير، ولا يتجاوز هذا. ولو أُخِّر لمرّ طلبٌ يحمل
    # `confirm: true` إلى الكتابة قبل أن يُسأل عن المعالجة.
    busy = (await session.execute(
        select(Thesis.id).where(
            Thesis.tenant_id == principal.tenant_id,
            Thesis.file_id == file_id,
            Thesis.processing_state.in_(thesis_processing.IN_FLIGHT),
        ).limit(1)
    )).scalar_one_or_none()
    if busy is not None:
        raise AtheraError("library.file_busy_processing", status_code=409,
                          thesis_id=busy)

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
