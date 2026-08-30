"""الخيط الذهبي والمنهجية | Golden thread and methodology (§15، §16، §29.1).

عناصر الخيط كائنات مستقلة لا حقول نصية في مستند: هذا ما يجعل اختبارات
الاتساق في §15.2 قابلة للتشغيل أصلًا. سؤال بلا تحليل يُكتشف لأن السؤال
والتحليل عقدتان والرابط بينهما إما موجود أو غير موجود.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# مفردات المجال مصدرها طبقة الخدمات لا العكس — انظر services/golden_thread/vocab.py
from ..services.golden_thread.vocab import (  # noqa: E402
    LINK_TYPES,
    SAMPLING_STRATEGIES,
    STUDY_TYPES,
    THREAD_ELEMENTS,
)

__all__ = [
    "THREAD_ELEMENTS", "LINK_TYPES", "STUDY_TYPES", "SAMPLING_STRATEGIES",
    "Theory", "ThreadElement", "ThreadLink", "Construct", "Variable",
    "Method", "Instrument", "InstrumentItem", "Protocol",
]


class Theory(Base, TenantScoped, Timestamped):
    __tablename__ = "theories"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rationale_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # §8 (Theory Agent) — «يوضح البدائل والقيود».
    alternatives: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    limitations_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)  # G3


class ThreadElement(Base, TenantScoped, Timestamped):
    """عقدة في الخيط الذهبي.

    جدول واحد لكل الأنواع بدل أربعة عشر جدولًا: الاتساق يُفحص على الرسم،
    والرسم يحتاج عقدًا متجانسة. الأنواع المتخصصة (المتغيرات، الأدوات)
    تحتفظ بجداولها لتفاصيلها.
    """

    __tablename__ = "thread_elements"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    element_type: Mapped[str] = mapped_column(String(24), nullable=False)
    label_ar: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    theory_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theories.id", ondelete="SET NULL"), nullable=True
    )
    # للفروض: هل الفرض قابل للاختبار بمتغيرات مقاسة؟ يُحسب لا يُدّعى.
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ThreadLink(Base, TenantScoped, Timestamped):
    """رابط بين عقدتين. غيابه هو ما تكتشفه اختبارات §15.2."""

    __tablename__ = "thread_links"
    __table_args__ = (
        UniqueConstraint("source_element_id", "target_element_id", "link_type",
                         name="uq_thread_link"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    source_element_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("thread_elements.id", ondelete="CASCADE"), nullable=False
    )
    target_element_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("thread_elements.id", ondelete="CASCADE"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(String(24), nullable=False)
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class Construct(Base, TenantScoped, Timestamped):
    __tablename__ = "constructs"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    conceptual_definition_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    theory_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theories.id", ondelete="SET NULL"), nullable=True
    )
    # reflective | formative (§18.2 SmartPLS)
    measurement_model: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Variable(Base, TenantScoped, Timestamped):
    """§16.1 — المتغير بتعريفه الإجرائي. بلا تعريف إجرائي لا يُقاس."""

    __tablename__ = "variables"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    construct_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("constructs.id", ondelete="SET NULL"), nullable=True
    )
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # independent | dependent | mediator | moderator | control
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    operational_definition_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    scale_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    appears_in_title: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Method(Base, TenantScoped, Timestamped):
    """§16 — التصميم المنهجي وأسلوب المعاينة."""

    __tablename__ = "methods"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    study_type: Mapped[str] = mapped_column(String(24), nullable=False)
    design_label_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # correlational | descriptive | experimental | quasi_experimental | case_study | ethnographic
    design_family: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sampling_strategy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    population_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sample_size_justification_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_plan_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)  # G4


class Instrument(Base, TenantScoped, Timestamped):
    __tablename__ = "instruments"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_translated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    back_translation_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pilot_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reliability: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    validity: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)  # G5


class InstrumentItem(Base, TenantScoped, Timestamped):
    """بند في الأداة — يربط القياس بمتغيره. غيابه يكشف «متغير بلا أداة»."""

    __tablename__ = "instrument_items"

    id: Mapped[uuid.UUID] = uuid_pk()
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    variable_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("variables.id", ondelete="SET NULL"), nullable=True
    )
    item_text_ar: Mapped[str] = mapped_column(Text, nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Protocol(Base, TenantScoped, Timestamped):
    """§9 — البروتوكول ببواباته. الاعتماد كائن له فاعل وتاريخ."""

    __tablename__ = "protocols"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    summary_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_gate: Mapped[str] = mapped_column(String(8), nullable=False, default="G2")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    approved_gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # لقطة نتائج فحص الاتساق وقت الاعتماد — الاعتماد يقع على حالة معروفة.
    consistency_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
