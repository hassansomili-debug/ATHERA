"""مجلدات المكتبة | Library folders (My Library V2).

هذا الموجّه يُضمّ داخل موجّه الملفات (`/api/v1/files/folders`) لأن المجلَّد
ليس كيانًا قائمًا بذاته: هو موضعُ ملفٍّ في مكتبة صاحبه. وضمُّه هناك يجعل
تغطية التدقيق والحدود والعزل تُقاس على السطح نفسه، لا على سطحٍ ثانٍ يُنسى.

**والقراءة لا تنزل في الشجرة أبدًا.** كل قائمةٍ هنا مجلَّدٌ واحد وأبناؤه
المباشرون، وفتاتُ الطريق مسارٌ صاعدٌ محدود العمق. وذلك عمدًا: `GET
/api/v1/files` كان `1 + 3N` عبارة فبلغ ثلاثين ثانية في الإنتاج، ولا يُعاد
العطب نفسه من باب المجلَّدات.
"""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError
from ..models.files import File
from ..models.identity import ObjectGrant
from ..models.library import FOLDER_OBJECT_TYPE, MAX_FOLDER_DEPTH, LibraryFolder
from ..schemas.library import (
    Crumb,
    FolderCreateRequest,
    FolderListing,
    FolderMoveRequest,
    FolderOption,
    FolderRenameRequest,
    FolderView,
)
from ..services import audit, library, rbac

router = APIRouter(prefix="/folders", tags=["library-folders"])

# **سقفُ قائمة «نقل إلى…»** — قائمةُ اختيارٍ بلا حدّ ليست قائمة، وهي الدرس
# نفسه الذي أخرج الترقيم المفتاحيّ من عطب «المكتبة ما تتحمل كتب».
MOVE_PICKER_CAP = 200
# وسقفُ أبناء المجلَّد الواحد في الشاشة: مجلَّدٌ فيه أكثر من هذا تنظيمٌ
# انهار، ويُقال ذلك بصراحة بدل صفحةٍ لا تُحمَّل.
CHILDREN_CAP = 200


def _counts(tenant_id: uuid.UUID):
    """عددا ما في المجلَّد — استعلامان فرعيّان **في العبارة نفسها**.

    وليسا عبارتين: القاعدة تنفّذهما مع الصفوف في زيارةٍ واحدة، فلا تنمو
    كلفة الشاشة مع عدد المجلَّدات. وهو النمط نفسه في
    `workspace.file_processing_state_columns`.
    """
    child = aliased(LibraryFolder)
    files = (
        select(func.count(File.id))
        .where(File.tenant_id == tenant_id, File.folder_id == LibraryFolder.id,
               File.trashed_at.is_(None))
        .scalar_subquery()
    )
    folders = (
        select(func.count(child.id))
        .where(child.tenant_id == tenant_id, child.parent_folder_id == LibraryFolder.id,
               child.trashed_at.is_(None))
        .scalar_subquery()
    )
    return files, folders


async def _view(session: AsyncSession, tenant_id: uuid.UUID,
                folder: LibraryFolder) -> FolderView:
    """المجلَّد الواحد بعدديه — يُستعمل بعد فعلٍ مفرد لا في قائمة."""
    files, folders = _counts(tenant_id)
    row = (await session.execute(
        select(files, folders).select_from(LibraryFolder)
        .where(LibraryFolder.id == folder.id, LibraryFolder.tenant_id == tenant_id)
    )).one()
    return FolderView(
        id=folder.id, name=folder.name, parent_folder_id=folder.parent_folder_id,
        created_at=folder.created_at, trashed_at=folder.trashed_at,
        files=row[0] or 0, folders=row[1] or 0)


async def _may_change(session: AsyncSession, principal: Principal,
                      folder_id: uuid.UUID, action: str = "write") -> None:
    """المنحةُ على الكائن هي ما يحرس الفعل — لا الانتماء للمستأجر وحده.

    فالعزل يمنع مستأجرًا من رؤية مجلَّد غيره أصلًا؛ وهذا الفحص يمنع من
    **يرى** المجلَّد داخل المستأجر نفسه أن يعيد تسميته أو ينقله أو يحذفه
    بلا منحة. والمُنشئ يأخذ `owner` عند الإنشاء، كما يأخذها رافعُ الملف.
    """
    await rbac.require_object_action(session, principal.tenant_id, principal.user_id,
                                     FOLDER_OBJECT_TYPE, folder_id, action)


@router.get("/all", response_model=list[FolderOption])
async def list_all_folders(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[FolderOption]:
    """كل المجلَّدات القائمة — **لقائمة «نقل إلى…» وحدها**.

    والمسار بمساره الكامل: مجلَّدان باسم «المنهج» تحت أبوين مختلفين لا
    يُفرَّق بينهما بالاسم، فيختار الباحث غير ما أراد ولا يعلم.

    **والمسار يُركَّب هنا لا في القاعدة.** الصفوف كلها في اليد بعد عبارةٍ
    واحدة، فبناء المسار منها حسابٌ في الذاكرة لا زيارةٌ ثانية.
    """
    rows = (await session.execute(
        select(LibraryFolder)
        .where(LibraryFolder.tenant_id == principal.tenant_id,
               LibraryFolder.trashed_at.is_(None))
        .order_by(LibraryFolder.name)
        .limit(MOVE_PICKER_CAP)
    )).scalars().all()

    by_id = {row.id: row for row in rows}

    def path_of(row: LibraryFolder) -> str:
        parts, cursor, depth = [row.name], row.parent_folder_id, 0
        # الحدُّ يحرس من شجرةٍ معطوبة: لا حلقة تدور بلا نهاية في عملية.
        while cursor is not None and depth < MAX_FOLDER_DEPTH:
            parent = by_id.get(cursor)
            if parent is None:
                break
            parts.append(parent.name)
            cursor, depth = parent.parent_folder_id, depth + 1
        return " / ".join(reversed(parts))

    return [FolderOption(id=row.id, name=row.name,
                         parent_folder_id=row.parent_folder_id, path=path_of(row))
            for row in rows]


@router.get("", response_model=FolderListing)
async def list_folders(
    parent: uuid.UUID | None = Query(default=None),
    trash: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderListing:
    """محتوى مجلَّدٍ واحد: فتاتُ طريقه وأبناؤه المباشرون.

    **وثلاث عبارات ثابتة مهما كبرت المكتبة**: فتاتُ الطريق (عبارةٌ صاعدة
    مقيَّدة العمق)، والأبناء بعدديهما (عبارةٌ واحدة)، ولا ثالثة إلا حين
    يُطلب مجلَّدٌ بعينه فيُتحقَّق من وجوده. ولا استعلامَ لكل صفّ.

    و`trash=true` تعرض ما في السلّة — وهو الباب الذي تُستعاد منه المجلَّدات،
    فلا تصير الاستعادة مسارًا لا يبلغه أحد.
    """
    breadcrumb: list[Crumb] = []
    if parent is not None and not trash:
        await library.get_folder(session, tenant_id=principal.tenant_id, folder_id=parent)
        breadcrumb = [Crumb(id=node_id, name=name) for node_id, name in
                      await library.ancestors(session, tenant_id=principal.tenant_id,
                                              folder_id=parent)]

    files, folders = _counts(principal.tenant_id)
    stmt = (
        select(LibraryFolder.id, LibraryFolder.name, LibraryFolder.parent_folder_id,
               LibraryFolder.created_at, LibraryFolder.trashed_at, files, folders)
        .where(LibraryFolder.tenant_id == principal.tenant_id)
        .order_by(LibraryFolder.name)
        .limit(CHILDREN_CAP)
    )
    if trash:
        # السلّة قائمةٌ مسطّحة: ما حُذف يُعرض كله، لا بموضعه في شجرةٍ
        # قد يكون أبوها نفسه محذوفًا.
        stmt = stmt.where(LibraryFolder.trashed_at.is_not(None))
    else:
        stmt = stmt.where(LibraryFolder.trashed_at.is_(None))
        stmt = (stmt.where(LibraryFolder.parent_folder_id == parent) if parent is not None
                else stmt.where(LibraryFolder.parent_folder_id.is_(None)))

    rows = (await session.execute(stmt)).all()
    return FolderListing(
        folder_id=None if trash else parent,
        breadcrumb=breadcrumb,
        folders=[FolderView(id=row[0], name=row[1], parent_folder_id=row[2],
                            created_at=row[3], trashed_at=row[4],
                            files=row[5] or 0, folders=row[6] or 0)
                 for row in rows],
    )


@router.post("", response_model=FolderView, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: FolderCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderView:
    """مجلَّدٌ جديد — تحت مجلَّدٍ قائم أو في الجذر.

    والإنشاء تحت مجلَّد **يحتاج منحةً عليه**: من لا يملك الأب لا يضع فيه
    شيئًا. والمُنشئ يأخذ `owner` على مجلَّده فورًا — وهو نمط الملكية نفسه
    الذي يأخذه رافعُ الملف، لا نموذجٌ ثانٍ.
    """
    name = payload.name.strip()
    if not name:
        raise AtheraError("library.folder_name_required", status_code=422)

    await library.lock_tree(session, principal.tenant_id)
    if payload.parent_folder_id is not None:
        await _may_change(session, principal, payload.parent_folder_id)
    await library.assert_placement(session, tenant_id=principal.tenant_id,
                                   parent_id=payload.parent_folder_id)

    folder = LibraryFolder(
        tenant_id=principal.tenant_id, name=name,
        parent_folder_id=payload.parent_folder_id, created_by=principal.user_id)
    session.add(folder)
    await session.flush()

    session.add(ObjectGrant(
        tenant_id=principal.tenant_id, object_type=FOLDER_OBJECT_TYPE,
        object_id=folder.id, user_id=principal.user_id, grant_level="owner",
        granted_by=principal.user_id))

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.folder_created",
        object_type=FOLDER_OBJECT_TYPE, object_id=folder.id,
        actor_user_id=principal.user_id,
        state_after={"name": name[:120],
                     "parent_folder_id": str(payload.parent_folder_id)
                     if payload.parent_folder_id else None},
        reason="a folder organises the library; it never changes a file's evidence state",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return await _view(session, principal.tenant_id, folder)


@router.patch("/{folder_id}", response_model=FolderView)
async def rename_folder(
    folder_id: uuid.UUID,
    payload: FolderRenameRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderView:
    """إعادة تسمية — الاسم وحده يتغيّر، ولا شيء تحته يتحرّك."""
    name = payload.name.strip()
    if not name:
        raise AtheraError("library.folder_name_required", status_code=422)

    folder = await library.get_folder(session, tenant_id=principal.tenant_id,
                                      folder_id=folder_id)
    await _may_change(session, principal, folder_id)
    before = folder.name
    folder.name = name
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.folder_renamed",
        object_type=FOLDER_OBJECT_TYPE, object_id=folder_id,
        actor_user_id=principal.user_id,
        state_before={"name": before[:120]}, state_after={"name": name[:120]},
        reason="renaming a folder touches its name and nothing else",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return await _view(session, principal.tenant_id, folder)


@router.post("/{folder_id}/move", response_model=FolderView)
async def move_folder(
    folder_id: uuid.UUID,
    payload: FolderMoveRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderView:
    """نقلُ مجلَّدٍ تحت آخر — أو إلى الجذر بـ`parent_folder_id: null`.

    **والدورة تُرفض داخل معاملةٍ واحدة**: القفل يُؤخذ أولًا، ثم يُفحص أن
    الهدف ليس المجلَّد نفسه ولا واحدًا من ذرّيته، ثم تقع الكتابة. ولو
    فُصل الفحص عن الكتابة لمرّ نقلان متزامنان فأنتجا حلقةً تختفي بها فروعٌ
    كاملة من المكتبة بلا رسالة.

    والنقل يحتاج منحةً على المجلَّد المنقول **وعلى وجهته**: من لا يملك
    الوجهة لا يضع فيها شيئًا.
    """
    await library.lock_tree(session, principal.tenant_id)
    folder = await library.get_folder(session, tenant_id=principal.tenant_id,
                                      folder_id=folder_id)
    await _may_change(session, principal, folder_id)
    if payload.parent_folder_id is not None:
        await _may_change(session, principal, payload.parent_folder_id)
    await library.assert_placement(session, tenant_id=principal.tenant_id,
                                   parent_id=payload.parent_folder_id,
                                   moving_id=folder_id)

    before = folder.parent_folder_id
    folder.parent_folder_id = payload.parent_folder_id
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.folder_moved",
        object_type=FOLDER_OBJECT_TYPE, object_id=folder_id,
        actor_user_id=principal.user_id,
        state_before={"parent_folder_id": str(before) if before else None},
        state_after={"parent_folder_id": str(payload.parent_folder_id)
                     if payload.parent_folder_id else None},
        reason="moving a folder re-parents a row; no storage key and no evidence moves",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return await _view(session, principal.tenant_id, folder)


@router.post("/{folder_id}/trash", response_model=FolderView)
async def trash_folder(
    folder_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderView:
    """«حذف» مجلَّد = نقلُه إلى السلّة — **ولا يُحذف وفيه شيء**.

    والرفض مقصود. البديلان أسوأ: حذفٌ يجرّ ما تحته يُخفي عشرات الملفات
    بضغطةٍ واحدة ويجعل الاستعادة تخمينًا لما كان؛ وحذفٌ يترك ما تحته
    معلَّقًا يُنتج ملفاتٍ في القاعدة لا تظهر في أي شاشة — ضياعٌ صامت. فيُقال
    للباحث كم فيه، وينقل ما فيه بنفسه، ثم يحذف وعاءً فارغًا يعرف أنه فارغ.

    ولا استعلامَ نازلًا في الشجرة: العددان مباشران، والابنُ المحذوف يمنع
    حذف أبيه أيضًا — فلا يستقرّ محذوفٌ تحت محذوف.
    """
    folder = await library.get_folder(session, tenant_id=principal.tenant_id,
                                      folder_id=folder_id)
    await _may_change(session, principal, folder_id, action="delete")

    child = aliased(LibraryFolder)
    held = (await session.execute(
        select(
            select(func.count(File.id)).where(
                File.tenant_id == principal.tenant_id, File.folder_id == folder_id,
                File.trashed_at.is_(None)).scalar_subquery(),
            select(func.count(child.id)).where(
                child.tenant_id == principal.tenant_id,
                child.parent_folder_id == folder_id).scalar_subquery(),
        )
    )).one()
    if held[0] or held[1]:
        raise AtheraError("library.folder_not_empty", status_code=409,
                          files=held[0] or 0, folders=held[1] or 0)

    folder.trashed_at = dt.datetime.now(dt.UTC)
    folder.trashed_by = principal.user_id
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.folder_trashed",
        object_type=FOLDER_OBJECT_TYPE, object_id=folder_id,
        actor_user_id=principal.user_id,
        state_before={"trashed_at": None}, state_after={"trashed_at": "now"},
        reason="deleting a folder moves it to the trash; destroying it is a second decision",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return await _view(session, principal.tenant_id, folder)


@router.post("/{folder_id}/restore", response_model=FolderView)
async def restore_folder(
    folder_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FolderView:
    """استعادةٌ من السلّة — **إلى موضعها الأول إن كان قائمًا**.

    وأبٌ في السلّة يوقف الاستعادة برسالةٍ تقول ما يلزم: استعِد الأب أولًا.
    والبديل — استعادةٌ صامتة إلى الجذر — تنقل المجلَّد من حيث تركه صاحبه
    بلا أن يُقال له، فيبحث عنه حيث كان فلا يجده.
    """
    folder = await library.get_folder(session, tenant_id=principal.tenant_id,
                                      folder_id=folder_id, include_trashed=True)
    await _may_change(session, principal, folder_id)
    if folder.trashed_at is None:
        raise AtheraError("library.folder_not_in_trash", status_code=409)

    if folder.parent_folder_id is not None:
        parent = (await session.execute(
            select(LibraryFolder).where(
                LibraryFolder.id == folder.parent_folder_id,
                LibraryFolder.tenant_id == principal.tenant_id)
        )).scalar_one_or_none()
        if parent is None or parent.trashed_at is not None:
            raise AtheraError("library.parent_in_trash", status_code=409)

    folder.trashed_at = None
    folder.trashed_by = None
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.folder_restored",
        object_type=FOLDER_OBJECT_TYPE, object_id=folder_id,
        actor_user_id=principal.user_id,
        state_before={"trashed_at": "set"}, state_after={"trashed_at": None},
        reason="the trash is a waiting room; restoring returns the folder where it was",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return await _view(session, principal.tenant_id, folder)
