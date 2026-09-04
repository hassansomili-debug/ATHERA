"""أفعالٌ على المختار | Bulk library actions (My Library V2.1).

**من رفع ثلاثين ورقةً في الجذر لا ينظّمها بثلاثين ضغطة.** أفعال المكتبة
كلها كانت على ملفٍ واحد: افتح لوحته، اختر الوجهة، أكّد، ثم أعِد ذلك تسعةً
وعشرين مرّة. وذلك ليس بطئًا في الشاشة — هو أن التنظيم لا يقع أصلًا، فتبقى
المكتبة قائمةً واحدة رغم أن لها مجلَّدات.

**وثلاثةٌ لا رابع لها: نقلٌ، وحذفٌ إلى السلّة، وربطٌ ببحث.** ولا إتلاف
دائم هنا ولا في مكانٍ آخر من هذا الموجّه — والإتلاف قرارٌ لم يُبنَ بعد،
وبناؤه من باب «فعلٍ على عشرين ملفًا» أسوأ مواضعه.

**والدفعة تقع كلها أو لا يقع منها شيء.** والنجاح الجزئيّ أسوأ الخيارين:
سبعةَ عشرَ ملفًّا انتقلت وثلاثة لم تنتقل، ولا شيء في الشاشة يقول أيُّها —
فيبحث الباحث عن ملفاته في رفَّين، ويظنّ ما وجده كلَّ ما اختاره. والمعاملة
واحدة، فرفضُ واحدٍ يردّ الجميع ويُسمّى الملف الذي ردّه.

**والحدّ معلَن.** دفعةٌ بلا سقف تُصدر معاملةً لا يُعرف طولها، فتقفل صفوفًا
طويلًا وتُبطئ كلَّ قارئٍ آخر — وهو الدرس نفسه الذي أخرج الترقيم المفتاحيّ
من عطب «المكتبة ما تتحمل كتب».
"""
import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.files import File
from ..models.portfolio import ProjectFile
from ..schemas.library import (
    BulkLinkRequest,
    BulkMoveRequest,
    BulkOutcome,
    BulkTrashRequest,
)
from ..services import audit, library, workspace

router = APIRouter(prefix="/bulk", tags=["library-bulk"])

# سقفُ الدفعة الواحدة — والشاشة تعرض خمسةً وعشرين في الصفحة، وسقفُ القراءة
# مئة. فمئةٌ هنا تغطّي «اختر كل المعروض» ولا تزيد عليه.
MAX_BATCH = 100


async def _selection(session: AsyncSession, principal: Principal,
                     file_ids: list[uuid.UUID], action: str) -> list[File]:
    """الملفات المختارة، محروسةً واحدًا واحدًا — **قبل أن تقع كتابةٌ واحدة**.

    والفحص قبل الكتابة لا معها: لو فُحص ملفٌ فكُتب ثم رُدّ الذي بعده، لبقي
    الأول مكتوبًا في ذاكرة الجلسة حتى يُرجعها الرفض — وذلك يعتمد على
    الاسترجاع بدل أن يعتمد على الترتيب. والصريح أوضح.

    والتكرار يُطرح: معرّفٌ مذكور مرّتين ليس ملفَّين، وعدُّه مرّتين يجعل
    «نُقل ٢١ ملفًا» رقمًا لا يطابق ما في المكتبة.
    """
    unique = list(dict.fromkeys(file_ids))
    if not unique:
        raise AtheraError("library.nothing_selected", status_code=422)
    if len(unique) > MAX_BATCH:
        raise AtheraError("library.selection_too_large", status_code=422,
                          selected=len(unique), max_files=MAX_BATCH)
    return [await library.owned_file(session, tenant_id=principal.tenant_id,
                                     user_id=principal.user_id, file_id=file_id,
                                     action=action)
            for file_id in unique]


@router.post("/move", response_model=BulkOutcome)
async def bulk_move(
    payload: BulkMoveRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BulkOutcome:
    """نقلُ المختار إلى مجلَّد — و`folder_id: null` إلى الجذر.

    **وهذا كلُّ ما يقع، عشرين مرّة: عمودٌ واحد يتغيّر في كل صفّ.**

    ولا يُمسّ مفتاح تخزينٍ، ولا ربطُ ملفٍ ببحث، ولا حالُ مرشّحٍ استُخرج
    منه، ولا استشهادٌ بُني عليه. فالمجلَّد تنظيمٌ لا حالُ دليل — وما يصدق
    على ملفٍ واحد يصدق على عشرين، ولا يُستثنى الجماعيّ من ضمانٍ يقوم عليه
    المفرد.

    والوجهة تُفحص **مرّة واحدة** لا مرّةً لكل ملف: هي مجلَّدٌ واحد، وعدُّ
    فحصها بعدد المختار يُعيد `1 + N` في فعلٍ يُفترض أنه وفّرها.
    """
    if payload.folder_id is not None:
        await library.assert_writable(session, tenant_id=principal.tenant_id,
                                      user_id=principal.user_id,
                                      folder_id=payload.folder_id)

    records = await _selection(session, principal, payload.file_ids, "write")
    moved = 0
    for record in records:
        if record.folder_id != payload.folder_id:
            record.folder_id = payload.folder_id
            moved += 1
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.files_moved",
        object_type="file", object_id=records[0].id, actor_user_id=principal.user_id,
        state_after={"folder_id": str(payload.folder_id) if payload.folder_id else None,
                     "selected": len(records), "changed": moved},
        reason="a folder change is organisation only: storage keys, project links and "
               "evidence state are untouched, for twenty files as for one",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return BulkOutcome(selected=len(records), changed=moved)


@router.post("/trash", response_model=BulkOutcome)
async def bulk_trash(
    payload: BulkTrashRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BulkOutcome:
    """«حذف» المختار = نقلُه إلى السلّة. **ولا يُتلَف شيء هنا.**

    الكائنات باقية في المخزن، والصفوف باقية بكل حقولها، وروابطُها ببحوثها
    باقية — والاستعادة ترجع كلَّ ملفٍ إلى موضعه هو، لا إلى الجذر.

    **ويُقال ما يترتّب بعدده قبل أن يقع.** والتحذير الجماعيّ أخطر من
    المفرد: ضغطةٌ واحدة تُخفي عشرين ملفًا، وقد يسند بعضها بحوثًا قائمة.
    فيُردّ 409 بعدد البحوث التي تستعمل المختار، ولا يمضي إلا بإقرارٍ صريح.
    """
    records = await _selection(session, principal, payload.file_ids, "delete")
    links = await library.active_project_links(
        session, tenant_id=principal.tenant_id,
        file_ids=[record.id for record in records])
    if links and not payload.confirm:
        raise AtheraError("library.selection_linked_to_projects", status_code=409,
                          projects=links, files=len(records))

    now = dt.datetime.now(dt.UTC)
    trashed = 0
    for record in records:
        # وما كان في السلّة يبقى فيها بتاريخه الأول: إعادةُ ختمه تكذب على
        # صاحبه في «متى حُذف»، ولا تصنع شيئًا.
        if record.trashed_at is None:
            record.trashed_at = now
            record.trashed_by = principal.user_id
            trashed += 1
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.files_trashed",
        object_type="file", object_id=records[0].id, actor_user_id=principal.user_id,
        state_after={"selected": len(records), "changed": trashed,
                     "project_links": links},
        reason="deleting files moves them to the trash; the objects, the rows and "
               "their project links all survive",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return BulkOutcome(selected=len(records), changed=trashed, project_links=links)


@router.post("/link", response_model=BulkOutcome)
async def bulk_link(
    payload: BulkLinkRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> BulkOutcome:
    """ربطُ المختار ببحثٍ قائم — **بلا نسخ**.

    الملف يبقى ملفًّا واحدًا في مكتبة صاحبه، والرابط صفٌّ يقول إن هذا البحث
    يستعمله. ولذلك لا يمسّ الربط موضعَ الملف في المكتبة: بحثٌ يستعمل ملفًّا
    لا ينقله من رفّه.

    **والمربوط من قبل لا يُربط مرّتين.** الروابط القائمة تُقرأ بعبارةٍ
    واحدة، فيُقال «رُبط اثنا عشر، وكان ثمانيةٌ مربوطًا» — لا «رُبط عشرون»
    وفيها ثمانيةٌ لم يقع لها شيء.
    """
    project = await workspace.live_project(
        session, tenant_id=principal.tenant_id, project_id=payload.project_id)
    if project is None:
        raise NotFound("workspace.project_not_found")

    records = await _selection(session, principal, payload.file_ids, "read")
    existing = {
        row.file_id: row for row in (await session.execute(
            select(ProjectFile).where(
                ProjectFile.tenant_id == principal.tenant_id,
                ProjectFile.project_id == payload.project_id,
                ProjectFile.file_id.in_([record.id for record in records]))
        )).scalars().all()
    }

    linked = 0
    for record in records:
        link = existing.get(record.id)
        if link is None:
            session.add(ProjectFile(
                tenant_id=principal.tenant_id, project_id=payload.project_id,
                file_id=record.id, state=ProjectFile.ACTIVE,
                added_by=principal.user_id))
            linked += 1
        elif link.state != ProjectFile.ACTIVE:
            # رابطٌ أُزيل ثم أُعيد: يُحيا ولا يُنشأ ثانيةً — فصفّان لملفٍ
            # واحد في بحثٍ واحد يجعلان كل عدٍّ بعدهما خاطئًا.
            link.state = ProjectFile.ACTIVE
            linked += 1
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="library.files_linked",
        object_type="research_project", object_id=payload.project_id,
        actor_user_id=principal.user_id,
        state_after={"selected": len(records), "changed": linked},
        reason="library files are linked to a project, never copied into it, and "
               "linking never moves a file out of its folder",
        request_id=principal.request_id, ip_address=principal.ip_address)
    return BulkOutcome(selected=len(records), changed=linked,
                       already=len(records) - linked)
