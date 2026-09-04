"""عقود مجلدات المكتبة | Library folder contracts (My Library V2)."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class FolderCreateRequest(BaseModel):
    """مجلَّدٌ جديد — باسمٍ وأبٍ اختياري، والجذر `None`."""

    name: str = Field(min_length=1, max_length=255)
    parent_folder_id: uuid.UUID | None = None


class FolderRenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FolderMoveRequest(BaseModel):
    """`None` تعني جذر المكتبة — وهي قيمةٌ مقصودة لا حقلٌ منسيّ."""

    parent_folder_id: uuid.UUID | None = None


class FileMoveRequest(BaseModel):
    """نقلُ ملفٍّ إلى مجلَّد، و`None` إلى الجذر.

    **وهذا كلُّ ما يقع.** لا يُمسّ مفتاح التخزين، ولا ربطُ الملف ببحث، ولا
    حالُ مرشّحٍ استُخرج منه. فمن نظّم مكتبته لا يجوز أن يفقد سند ورقته.
    """

    folder_id: uuid.UUID | None = None


class TrashRequest(BaseModel):
    """الإقرار بعد أن يُقال ما يترتّب — لا قبله.

    الحذفُ هنا نقلٌ إلى سلّة، لكنّ الملف الذي يسند بحوثًا يختفي من مكتبة
    صاحبه، فيُقال له كم بحثًا يستعمله ثم يقرّر. والإقرار الصامت الافتراضي
    يجعل السؤال زينة.
    """

    confirm: bool = False


# ── الأفعال على المختار ────────────────────────────────────────────────
#
# **من رفع ثلاثين ورقةً في الجذر لا ينظّمها بثلاثين ضغطة.** والاختيار قائمة
# معرّفات لا «كل الملفات» ولا مرشِّح: فعلٌ يُوصف بشرطٍ يمسّ ما لم يره الباحث
# حين ضغط — ولو تغيّرت القائمة تحت يده لأصاب الفعلُ غير ما قصد.


class BulkMoveRequest(BaseModel):
    """نقلُ المختار إلى مجلَّد، و`None` إلى الجذر — **وعمودٌ واحد يتغيّر**."""

    file_ids: list[uuid.UUID] = Field(min_length=1)
    folder_id: uuid.UUID | None = None


class BulkTrashRequest(BaseModel):
    """حذفُ المختار إلى السلّة — والإقرار بعد أن يُقال ما يترتّب لا قبله.

    والتحذير الجماعيّ أخطر من المفرد: ضغطةٌ واحدة تُخفي عشرين ملفًا، وقد
    يسند بعضها بحوثًا قائمة. فيُقال عددُها ثم يُقرّر الباحث.
    """

    file_ids: list[uuid.UUID] = Field(min_length=1)
    confirm: bool = False


class BulkLinkRequest(BaseModel):
    """ربطُ المختار ببحثٍ قائم — بلا نسخٍ وبلا نقلٍ من مجلَّده."""

    file_ids: list[uuid.UUID] = Field(min_length=1)
    project_id: uuid.UUID


class BulkOutcome(BaseModel):
    """ما وقع بعدده — **لا «تم» تصلح لكل شيء**.

    و«اخترتَ عشرين، تغيّر منها اثنا عشر، وكان ثمانيةٌ كذلك من قبل» جملةٌ
    يفهمها صاحبها ويصدّقها. أمّا «تم» فتُقرأ «وقع لعشرين»، فيبحث عن أثرٍ
    لم يقع لثمانيةٍ منها ولا يجده.
    """

    selected: int = 0
    changed: int = 0
    already: int = 0
    project_links: int = 0


class Crumb(BaseModel):
    id: uuid.UUID
    name: str


class FolderView(BaseModel):
    """مجلَّدٌ كما يُعرض في القائمة — بعدد ما فيه، لا بشجرته."""

    id: uuid.UUID
    name: str
    parent_folder_id: uuid.UUID | None = None
    created_at: dt.datetime
    trashed_at: dt.datetime | None = None
    # ما يحتويه **مباشرةً**: عددان يُقرآن في العبارة نفسها، ولا تُحمَّل
    # الذرّية أبدًا في قائمة.
    files: int = 0
    folders: int = 0


class FolderListing(BaseModel):
    """محتوى مجلَّدٍ واحد: فتاتُ طريقه ومجلَّداته المباشرة.

    والملفات تُقرأ من `GET /api/v1/files?folder=…` بترقيمها المفتاحيّ — لا
    تُحشر هنا، فتفقد الصفحةَ حدَّها.
    """

    folder_id: uuid.UUID | None = None
    breadcrumb: list[Crumb] = Field(default_factory=list)
    folders: list[FolderView] = Field(default_factory=list)


class FolderOption(BaseModel):
    """مجلَّدٌ في قائمة «نقل إلى…» — بمساره كاملًا ليُميَّز عن شبيهه بالاسم."""

    id: uuid.UUID
    name: str
    parent_folder_id: uuid.UUID | None = None
    path: str


class FileTrashView(BaseModel):
    """ما وقع للملف، وما كان يسنده — يُقال بعدده لا بتحذيرٍ عامّ."""

    id: uuid.UUID
    trashed_at: dt.datetime | None = None
    project_links: int = 0
