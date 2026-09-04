"""مجلدات المكتبة | Library folders (My Library V2).

**المجلَّد تنظيمٌ لا حالُ دليل.** انتماءُ الملف إلى مجلَّد يقول أين وضعه
صاحبه في مكتبته، ولا يقول شيئًا عن كونه دليلًا مقبولًا ولا عن ربطه ببحث
ولا عن اعتماد ما استُخرج منه. فنقلُه بين مجلَّدين يغيّر `File.folder_id`
وحده — ولا يُسمح لأي مسار أن يغيّر معه شيئًا آخر.
"""

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# **حدُّ العمق مُعلَن.** شجرةٌ بلا حدّ تجعل فتات الطريق سطرًا لا يُقرأ،
# وتجعل كل مشيٍ صاعدٍ في الأجداد استعلامًا لا يُعرف طوله. والستّة عشر تكفي
# أعمق تنظيمٍ يكتبه إنسان، وتبقي كل قراءةٍ محدودةً بيقين.
MAX_FOLDER_DEPTH = 16

# نوع الكائن في `object_grants` — يُكتب مرّة هنا ويُقرأ حيث يُحتاج، فلا
# يفترق موضعان بحرفٍ فيصير الفحص يسأل عن كائنٍ لا وجود له.
FOLDER_OBJECT_TYPE = "library_folder"


class LibraryFolder(Base, TenantScoped, Timestamped):
    """مجلَّدٌ في مكتبة الباحث — شجرةٌ في جدولٍ واحد، وجذرُها `NULL`."""

    __tablename__ = "library_folders"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_folder_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("library_folders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # الملكية بنمط `files.uploaded_by`: صفٌّ يذكر صاحبه، ومنحةُ كائن في
    # `object_grants` تحرس الفعل. ولا نموذج ملكيةٍ ثانٍ.
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # «حذف» في الشاشة يكتب هنا — ولا يمحو صفًّا (فلسفة الترحيل 0020).
    trashed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    trashed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


__all__ = ["FOLDER_OBJECT_TYPE", "MAX_FOLDER_DEPTH", "LibraryFolder"]
