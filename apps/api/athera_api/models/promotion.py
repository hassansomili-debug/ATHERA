"""محرك الترقية | Promotion policy engine (§11، §3).

القاعدة الحاكمة من §3: **لا قواعد Hard-coded**. كل شرط ترقية صف في
`promotion_rules` له نوع ومعاملات ونسخة وتاريخ سريان ومصدر وحالة تحقق.
تغيير اللائحة تغييرُ بيانات، لا تغيير كود.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BilingualName, TenantScoped, Timestamped, uuid_pk

# §11.3 — أنواع القواعد الاثنا عشر. الحاسبة تعرف الأنواع، لا القيم.
RULE_TYPES: Final[dict[str, tuple[str, str]]] = {
    "service_duration": ("مدة الخدمة في الرتبة", "Service duration in rank"),
    "minimum_units": ("الحد الأدنى من الوحدات", "Minimum research units"),
    "sole_author_works": ("الأعمال المنفردة", "Sole-authored works"),
    "authorship_credit": ("طريقة احتساب المشاركة", "Authorship credit method"),
    "minimum_refereed_journals": ("الحد الأدنى من المجلات المحكمة", "Minimum refereed journals"),
    "outlet_diversity": ("تنوع منافذ النشر", "Publication outlet diversity"),
    "production_points": ("نقاط الإنتاج العلمي", "Scientific production points"),
    "indexing_requirement": ("شروط الفهرسة", "Indexing requirements"),
    "date_window": ("شروط التاريخ", "Date window conditions"),
    "thesis_derived_limit": ("استبعاد الرسائل أو الاستلال منها", "Thesis-derived work limits"),
    "first_or_corresponding_author": ("شروط المؤلف الأول/المراسل", "First/corresponding author"),
    "teaching_service_requirement": ("متطلبات التدريس والخدمة", "Teaching and service requirements"),
}

VERIFICATION_STATES: Final = ("unverified", "verified", "rejected")


class PromotionPolicy(Base, TenantScoped, Timestamped, BilingualName):
    """§11.2 — السياسة نفسها. النسخ والتواريخ في جدول مستقل."""

    __tablename__ = "promotion_policies"

    id: Mapped[uuid.UUID] = uuid_pk()
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    target_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PromotionPolicyVersion(Base, TenantScoped, Timestamped):
    """نسخة سياسة بتاريخ سريان ومصدر.

    الحساب يُربط بنسخة بعينها، فتعديل اللائحة لاحقًا لا يعيد كتابة حساب
    سابق (AT-S3-07). تاريخ القرار جزء من القرار.
    """

    __tablename__ = "promotion_policy_versions"
    __table_args__ = (
        UniqueConstraint("policy_id", "version_label", name="uq_policy_version_label"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    policy_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_policies.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[dt.date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PromotionRule(Base, TenantScoped, Timestamped):
    """قاعدة واحدة قابلة للحساب.

    `params` تحمل كل ما يخص جامعة بعينها. الحاسبة تقرأها ولا تفترض شيئًا:
    معامل مفقود يعني «يحتاج تحققًا مؤسسيًا»، لا قيمة افتراضية مخمّنة.
    """

    __tablename__ = "promotion_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_policy_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(String(48), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(64), nullable=False)
    statement_ar: Mapped[str] = mapped_column(Text, nullable=False)
    statement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # الموضع في وثيقة اللائحة — قاعدة بلا موضع لا تُعتمد (نفس منطق §29.2).
    source_locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearcherPublication(Base, TenantScoped, Timestamped):
    """منشورات الباحث السابقة (§10.1).

    جدول مقترح خارج قائمة §29.1 — مسجَّل في خطة Sprint 3 §3. الوحدات تُحسب
    منه، وهو ليس مشروعًا في المنصة ولا مصدرًا ببليوغرافيًا عامًا.
    """

    __tablename__ = "researcher_publications"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    journal_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    journal_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    author_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    author_position: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_refereed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_thesis_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # الفهارس كما تحققت وقت الفحص، مع تاريخه — الفهرسة متغيرة (§20.1).
    indexes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    indexing_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PromotionCase(Base, TenantScoped, Timestamped):
    """حالة ترقية محسوبة مقابل نسخة سياسة بعينها."""

    __tablename__ = "promotion_cases"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # عدّادات صريحة بدل نسبة واحدة تخفي شرطًا حاجبًا.
    rules_met: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rules_blocking: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rules_needing_verification: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    units_total: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    units_computable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class PromotionEvidence(Base, TenantScoped, Timestamped):
    """ربط كل وحدة محسوبة بقاعدتها ومصدرها (AT-S3-05)."""

    __tablename__ = "promotion_evidence"

    id: Mapped[uuid.UUID] = uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_cases.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_rules.id", ondelete="RESTRICT"), nullable=False
    )
    publication_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_publications.id", ondelete="SET NULL"), nullable=True
    )
    contribution: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    explanation_ar: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_en: Mapped[str] = mapped_column(Text, nullable=False)


class PromotionScenario(Base, TenantScoped, Timestamped, BilingualName):
    """§11.6 — إسقاط، لا حالة. لا يمس `promotion_cases` إطلاقًا."""

    __tablename__ = "promotion_scenarios"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    policy_version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("promotion_policy_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # minimum | safe | ambitious | rejection_impact | indexing_change
    scenario_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    projection: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # وسم صريح يمنع قراءة الإسقاط كإنجاز.
    is_projection: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
