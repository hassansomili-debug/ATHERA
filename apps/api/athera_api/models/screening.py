"""الفرز ومصفوفة الأدبيات | Screening and the literature matrix (PUBRIVA).

**لا حقيقة موازية.** قرارُ الفرز يسكن `project_sources.use_state` كما عرّفه
الترحيل 0020، ولا جدول قراراتٍ ثانٍ هنا. وما يُضاف إليه سببُ الاستبعاد
وحده — لأن حكمًا بلا سببٍ مسجَّل لا يُراجَع ولا يُكتب في قسم المنهجية.

**والخلية ليست نصًّا.** هي نصٌّ **ومن أين قُرئ**: مصدرٌ لم يُقرأ منه إلا
الملخّص لا تُملأ منه أعمدة المقاييس والتحليل بالتخمين. فكل خليةٍ تحمل
حالها ومَداها ومَن كتبها وشاهدَها إن وُجد — وقيودُ الترحيل 0023 تمنع أن
تُكتب خليةٌ تدّعي أكثر مما قُرئ.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# **المفردات تُكتب مرّة.** الترحيل 0023 يحمل القيد، وهذه هي المفردة نفسها
# في الشيفرة — واختبارٌ يقابل الاثنين نصًّا بنصّ، لأن الخطأ المتكرر في هذا
# المستودع مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

# أسباب الاستبعاد التي يقبلها الـAPI مُدخَلًا.
EXCLUSION_REASON_CODES: Final = (
    "topic_not_relevant",
    "population_mismatch",
    "method_mismatch",
    "not_original_study",
    "outside_time_window",
    "insufficient_data",
    "duplicate",
    "other",
)

# **سببٌ يُقرأ ولا يُكتب.** صفوفٌ استُبعدت قبل أن تُطلب الأسباب تحمل هذه
# القيمة؛ وهي تقول «لم يُسجَّل سببه» ولا تخترع سببًا. ولا يقبلها الـAPI
# مُدخَلًا أبدًا — وإلا صارت بابًا خلفيًّا لاستبعادٍ بلا سبب.
LEGACY_REASON_CODE: Final = "unrecorded_legacy"

# «سبب آخر» وحده يستوجب نصًّا حرًّا؛ وبدونه ليس سببًا بل خانةٌ فارغة تُعدّ.
FREE_TEXT_REASON_CODE: Final = "other"

STORED_REASON_CODES: Final = EXCLUSION_REASON_CODES + (LEGACY_REASON_CODE,)

# حال الخلية — مفردات المنصّة نفسها («دماغ البحث»، `BrainEntryView`).
CELL_STATES: Final = ("known", "needs_review", "missing", "conflicting")

# **مدى ما قُرئ فعلًا**، مرتَّبًا من الأضعف إلى الأقوى: مقارنةُ الرتب هي ما
# يمنع خليةً تدّعي نصًّا كاملًا من مصدرٍ لا نصّ له.
SOURCE_SCOPES: Final = ("metadata_only", "abstract_only", "full_text")

EXTRACTION_METHODS: Final = ("researcher", "metadata", "model")

VERIFICATION_STATES: Final = ("unverified", "approved", "rejected", "unknown")

# المُحدِّد الوحيد المسموح لخليةٍ قُرئت من ملخّص. **ولا رقم صفحة يُخترع.**
ABSTRACT_LOCATOR: Final = "abstract"

# **من أرسل هذا الملخّص** (الترحيل 0024). قائمةٌ مغلقة كقائمة `registry`
# نفسها، ومعها `researcher`: الباحث الذي ينسخ ملخّصًا من الورقة التي بين
# يديه مصدرٌ يُسمّى كسائر المصادر، لا مجهولٌ يُخزَّن بلا نسبة.
ABSTRACT_PROVIDERS: Final = ("crossref", "openalex", "offline", "upload", "researcher")

# أعمدة المصفوفة بترتيب عرضها. المفتاح تقنيّ والاسم المعروض في كتالوج
# الواجهة — فلا يقرأ الباحث مفتاحًا إنجليزيًّا في رأس عمود.
MATRIX_FIELDS: Final = (
    "reference", "year", "problem", "objective", "theory", "design", "method",
    "population", "sample", "context", "constructs", "measures", "analysis",
    "findings", "limitations", "gaps",
)


def scope_rank(scope: str) -> int:
    """رتبةُ المدى — تُقارن ولا تُخمَّن."""
    return SOURCE_SCOPES.index(scope)


class LiteratureMatrixCell(Base, TenantScoped, Timestamped):
    """خليةٌ واحدة في مصفوفة الأدبيات — بقيمتها وحالها ومَداها وشاهدها."""

    __tablename__ = "literature_matrix_cells"
    __table_args__ = (
        UniqueConstraint("project_id", "source_id", "field_key", name="uq_matrix_cell"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(32), nullable=False)
    value_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    cell_state: Mapped[str] = mapped_column(String(16), nullable=False)
    source_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    # **من أي ملخّصٍ قُرئت** — لا «من ملخّص» مجهولٍ صاحبه. وبها تُراجَع
    # القيمة: يفتح الباحث النصّ المنسوب، ويقرأ الجملة، ثم يحكم.
    source_abstract_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("source_abstracts.id", ondelete="SET NULL"),
        nullable=True,
    )
    # **الصفحة والقسم من نصٍّ كامل وحده، وحين يُعرفان.** ورقمُ الصفحة يأتي
    # من تقطيعٍ قرأ صفحةً فعلًا، ولا يُشتقّ من ترتيب المقطع: المقطع السابع
    # ليس الصفحة السابعة. والمجهول يبقى `NULL` — الصدق أولى من الاكتمال.
    evidence_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_section: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    updated_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class SourceAbstract(Base, TenantScoped, Timestamped):
    """ملخّصٌ واحد منسوبٌ إلى الفهرس الذي أرسله — **ولا يُطوى ملخّصان في واحد**.

    فهرسان يرسلان ملخّصين مختلفين للورقة نفسها حالٌ واقعة لا نادرة؛ وأن
    يغلب أحدهما الآخر بصمت يجعل الباحث يقرأ نصف الحقيقة ويظنّه كلّها.
    فالصفّان يبقيان، والاختلاف يُعرض اختلافًا.
    """

    __tablename__ = "source_abstracts"
    __table_args__ = (
        UniqueConstraint("source_id", "provider", "content_hash",
                         name="uq_source_abstract"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)


__all__ = [
    "ABSTRACT_LOCATOR",
    "ABSTRACT_PROVIDERS",
    "CELL_STATES",
    "EXCLUSION_REASON_CODES",
    "EXTRACTION_METHODS",
    "FREE_TEXT_REASON_CODE",
    "LEGACY_REASON_CODE",
    "LiteratureMatrixCell",
    "MATRIX_FIELDS",
    "SOURCE_SCOPES",
    "STORED_REASON_CODES",
    "SourceAbstract",
    "VERIFICATION_STATES",
    "scope_rank",
]
