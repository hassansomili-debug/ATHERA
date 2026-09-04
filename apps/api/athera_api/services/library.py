"""شجرة المكتبة | The library folder tree (My Library V2).

**الشجرة تُقرأ صعودًا لا نزولًا.** فتاتُ الطريق مسارٌ واحد طوله محدود
بـ`MAX_FOLDER_DEPTH`، وفحصُ الدورة سؤالٌ عن أجداد الهدف — وكلاهما عبارةٌ
واحدة مقيَّدةُ العمق. أمّا تحميل الذرّية فممنوع في كل قراءةٍ تُعرض: مكتبةٌ
تُبطئ نفسها كلما امتلأت هي بعينها العطب الذي عولج في `GET /api/v1/files`،
ولا يُعاد إدخاله من باب المجلَّدات.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, NotFound
from ..models.library import MAX_FOLDER_DEPTH, LibraryFolder

# ── المشي صعودًا: من مجلَّدٍ إلى جذره، بعمقٍ مقيَّد في العبارة نفسها ──
#
# والقيد `depth < :max` داخل العبارة لا بعدها: شجرةٌ فيها دورةٌ — لو نشأت
# يومًا رغم الحرّاس — تجعل التكرار لا ينتهي، والحدُّ هنا يوقفه في القاعدة
# لا في ذاكرة العملية.
_ANCESTORS = text(
    """
    WITH RECURSIVE up AS (
        SELECT id, name, parent_folder_id, 1 AS depth
          FROM library_folders
         WHERE id = :folder_id AND tenant_id = :tenant_id
        UNION ALL
        SELECT f.id, f.name, f.parent_folder_id, up.depth + 1
          FROM library_folders f
          JOIN up ON f.id = up.parent_folder_id
         WHERE f.tenant_id = :tenant_id AND up.depth < :max_depth
    )
    SELECT id, name, depth FROM up ORDER BY depth DESC
    """
)

# ── ارتفاع الشجرة تحت مجلَّد — لفحص العمق عند النقل وحده ──
#
# **وهذه القراءةُ الوحيدة التي تنزل**، وهي فعلُ نقلٍ مقصود لا قائمةٌ
# تُعرض: تُنفَّذ مرّةً على ضغطة زرّ، وعمقها مقيَّد، ولا تعود بصفوفٍ بل
# برقمٍ واحد.
_SUBTREE_HEIGHT = text(
    """
    WITH RECURSIVE down AS (
        SELECT id, 1 AS depth
          FROM library_folders
         WHERE id = :folder_id AND tenant_id = :tenant_id
        UNION ALL
        SELECT f.id, down.depth + 1
          FROM library_folders f
          JOIN down ON f.parent_folder_id = down.id
         WHERE f.tenant_id = :tenant_id AND f.trashed_at IS NULL
           AND down.depth < :max_depth
    )
    SELECT coalesce(max(depth), 1) FROM down
    """
)

# **قفلُ معاملةٍ لكل مستأجر عند تعديل الشجرة.**
#
# فحصُ الدورة يقرأ الحال ثم يكتب على أساسها. ونقلان متزامنان — «أ» تحت «ب»
# و«ب» تحت «أ» — يمرّان معًا في الفحص ثم يُنتجان حلقةً مغلقة تختفي بها
# فروعٌ كاملة من المكتبة بلا رسالة. والقفل يجعل الفحص والكتابة فعلًا واحدًا
# غير قابلٍ للتشابك، ويموت مع المعاملة فلا يبقى معلّقًا. والنقل فعلٌ نادر،
# فثمنُ التسلسل لا يُحسّ.
#
# **والمفتاح يُحسب هنا لا في القاعدة.** الصياغة الأولى استعملت `hashtext()`،
# وهي دالّة داخلية غير موثَّقة كواجهة — ولو تغيّرت أو مُنعت لسقط كل إنشاء
# مجلَّدٍ ونقلٍ في المنتج، لا شيءٌ هامشيّ. والحساب في بايثون صريحٌ ومستقرّ
# ولا يعتمد على شيء.
#
# والقفل يُقيَّد بمساحته: `_TREE_NAMESPACE` يفصل أقفال هذه الشجرة عن أي
# استعمالٍ آخر للأقفال الاستشارية في المنصّة، فلا يتعطّل مسارٌ بمسار.
_TREE_NAMESPACE = 0x4C494246  # "LIBF"
_LOCK_TREE = text(
    "SELECT pg_advisory_xact_lock(CAST(:namespace AS int), CAST(:tenant_key AS int))")


def _tenant_key(tenant_id: uuid.UUID) -> int:
    """أربعة بايتات من معرّف المستأجر، عددًا صحيحًا بإشارة (حدّ `int4`).

    والتصادم هنا لا يضرّ: أسوأ ما يقع أن ينتظر مستأجرٌ نقلَ مجلَّدٍ لمستأجر
    آخر أجزاءً من الثانية — والنقل فعلٌ نادر. أمّا الصحّة فمن القفل نفسه.
    """
    return int.from_bytes(tenant_id.bytes[:4], "big", signed=True)


async def lock_tree(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        _LOCK_TREE, {"namespace": _TREE_NAMESPACE, "tenant_key": _tenant_key(tenant_id)})


async def ancestors(
    session: AsyncSession, *, tenant_id: uuid.UUID, folder_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """المسار من الجذر إلى المجلَّد نفسه — وهو فتاتُ الطريق كما يُعرض."""
    rows = (await session.execute(_ANCESTORS, {
        "folder_id": folder_id, "tenant_id": tenant_id,
        "max_depth": MAX_FOLDER_DEPTH + 1,
    })).all()
    return [(row[0], row[1]) for row in rows]


async def depth_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, folder_id: uuid.UUID | None
) -> int:
    """عمقُ المجلَّد: الجذر صفر، وأولُ مجلَّدٍ فيه واحد."""
    if folder_id is None:
        return 0
    return len(await ancestors(session, tenant_id=tenant_id, folder_id=folder_id))


async def subtree_height(
    session: AsyncSession, *, tenant_id: uuid.UUID, folder_id: uuid.UUID
) -> int:
    height = (await session.execute(_SUBTREE_HEIGHT, {
        "folder_id": folder_id, "tenant_id": tenant_id,
        "max_depth": MAX_FOLDER_DEPTH + 1,
    })).scalar_one()
    return int(height or 1)


async def get_folder(
    session: AsyncSession, *, tenant_id: uuid.UUID, folder_id: uuid.UUID,
    include_trashed: bool = False,
) -> LibraryFolder:
    """مجلَّدٌ قائم — **وما في السلّة ليس قائمًا**.

    ولا يُفرَّق في الرسالة بين «غير موجود» و«لمستأجرٍ آخر»: العزل يمنع
    رؤيته أصلًا، وتخمين المعرّفات لا يعطي خبرًا.
    """
    stmt = select(LibraryFolder).where(
        LibraryFolder.id == folder_id, LibraryFolder.tenant_id == tenant_id)
    if not include_trashed:
        stmt = stmt.where(LibraryFolder.trashed_at.is_(None))
    folder = (await session.execute(stmt)).scalar_one_or_none()
    if folder is None:
        raise NotFound("library.folder_not_found")
    return folder


async def assert_placement(
    session: AsyncSession, *, tenant_id: uuid.UUID, parent_id: uuid.UUID | None,
    moving_id: uuid.UUID | None = None,
) -> None:
    """هل يجوز أن يستقرّ هذا المجلَّد تحت ذاك؟ — **قبل أي كتابة**.

    ثلاثة تُرفض هنا:

    ١) **مجلَّدٌ تحت نفسه أو تحت واحدٍ من ذرّيته.** والأثر ليس تجميليًّا:
       الحلقة تقطع فرعًا كاملًا عن الجذر، فتختفي ملفاتُه من كل قائمة بينما
       هي في القاعدة سليمة — ضياعٌ صامت لا رسالةَ له.

    ٢) **مجلَّدٌ في السلّة أبًا.** فوضعُ ما يُعرض تحت ما لا يُعرض إخفاءٌ
       بلا قصد.

    ٣) **عمقٌ يتجاوز الحدّ المعلَن.** والحدُّ هو ما يجعل فتات الطريق قابلًا
       للقراءة وكل استعلامٍ صاعدٍ محدودًا بيقين.
    """
    if parent_id is None:
        if moving_id is not None:
            # النقل إلى الجذر لا يحتاج فحصًا إلا العمق — وارتفاعُ الشجرة
            # من الجذر لا يتجاوز الحدّ ما دام لم يتجاوزه قبل النقل.
            return
        return

    if moving_id is not None and parent_id == moving_id:
        raise AtheraError("library.folder_cycle", status_code=409)

    parent_path = await ancestors(session, tenant_id=tenant_id, folder_id=parent_id)
    if not parent_path:
        raise NotFound("library.folder_not_found")
    if moving_id is not None and any(node_id == moving_id for node_id, _ in parent_path):
        raise AtheraError("library.folder_cycle", status_code=409)

    parent = await get_folder(session, tenant_id=tenant_id, folder_id=parent_id)
    if parent.trashed_at is not None:  # pragma: no cover — `get_folder` يمنعه
        raise AtheraError("library.folder_in_trash", status_code=409)

    height = (await subtree_height(session, tenant_id=tenant_id, folder_id=moving_id)
              if moving_id is not None else 1)
    if len(parent_path) + height > MAX_FOLDER_DEPTH:
        raise AtheraError("library.folder_depth_exceeded", status_code=409,
                          max_depth=MAX_FOLDER_DEPTH)


__all__ = ["MAX_FOLDER_DEPTH", "ancestors", "assert_placement", "depth_of", "get_folder",
           "lock_tree", "subtree_height"]
