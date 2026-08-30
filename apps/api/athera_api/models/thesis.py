"""الرسائل وفرص النشر | Theses and publication opportunities (§23، §24).

قيدان يحملان وزن السبرنت كله:

  • `publication_opportunities.status='ready_to_submit'` يستلزم اعتماد
    الحقوق **والتأليف** (§23.9، TC-06). التحليل الداخلي مسموح بلا ذلك —
    المنع على التقدم لا على الفهم.
  • `authorship_parties.party_kind` من قيمتين فقط: person و organization.
    «AI لا يكون مؤلفًا» (§24.2) مفروضة بغياب القيمة، لا بفحص نصي.
"""

import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..services.thesis.vocab import (  # noqa: F401 — تُعاد التصديرة للاستخدام الخارجي
    AUTHORSHIP_PARTY_KINDS,
    CREDIT_ROLES,
    OPPORTUNITY_KINDS,
    OVERLAP_DIMENSIONS,
    PAPER_KINDS,
    READINESS_OUTCOMES,
    RIGHTS_BASES,
    THESIS_SECTIONS,
)
from .base import Base, TenantScoped, Timestamped, uuid_pk

__all__ = [
    "Thesis", "ThesisOwner", "ThesisSupervisor", "ThesisSection", "ThesisResult",
    "PublicationOpportunity", "OpportunityOverlapScore", "OverlapPolicyRow",
    "AuthorshipParty", "AuthorshipAgreement", "CreditRoleAssignment",
    "THESIS_SECTIONS", "OPPORTUNITY_KINDS", "PAPER_KINDS", "OVERLAP_DIMENSIONS",
    "READINESS_OUTCOMES", "CREDIT_ROLES", "AUTHORSHIP_PARTY_KINDS", "RIGHTS_BASES",
]


class Thesis(Base, TenantScoped, Timestamped):
    """§23.3 — الرسالة ومصدرها. `data_collected_on` أساس حساب عمر البيانات (§23.8)."""

    __tablename__ = "theses"

    id: Mapped[uuid.UUID] = uuid_pk()
    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    degree: Mapped[str] = mapped_column(String(24), nullable=False)  # masters | phd
    defended_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    data_collected_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    institution_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    # §23.2 — أساس حق الاستخدام، وهو غير اعتماد الحقوق: الأول ادعاء والثاني قرار.
    rights_basis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parsed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # §23.8 — منشورات سبق استخراجها من هذه الرسالة.
    existing_publications: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class ThesisOwner(Base, TenantScoped, Timestamped):
    __tablename__ = "thesis_owners"

    id: Mapped[uuid.UUID] = uuid_pk()
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    consent_recorded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ThesisSupervisor(Base, TenantScoped, Timestamped):
    __tablename__ = "thesis_supervisors"

    id: Mapped[uuid.UUID] = uuid_pk()
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ThesisSection(Base, TenantScoped, Timestamped):
    """§23.3 — قسم مستخرج بموضعه واقتباسه، بنفس حاجز التأصيل في Sprint 1."""

    __tablename__ = "thesis_sections"
    __table_args__ = (UniqueConstraint("thesis_id", "section_key", name="uq_thesis_section"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(32), nullable=False)
    content_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")


class ThesisResult(Base, TenantScoped, Timestamped):
    """نتيجة في الرسالة — الوحدة التي يُقاس عليها تداخل النتائج (§23.7)."""

    __tablename__ = "thesis_results"

    id: Mapped[uuid.UUID] = uuid_pk()
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False
    )
    label_ar: Mapped[str] = mapped_column(Text, nullable=False)
    result_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    table_figure_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OverlapPolicyRow(Base, TenantScoped, Timestamped):
    """§23.7 — العتبات بيانات سياسة، لا ثوابت في الكود."""

    __tablename__ = "overlap_policies"

    id: Mapped[uuid.UUID] = uuid_pk()
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    salami_min_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    critical_dimensions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class PublicationOpportunity(Base, TenantScoped, Timestamped):
    """§23.4–23.6 — فرصة نشر مستخرجة من رسالة."""

    __tablename__ = "publication_opportunities"

    id: Mapped[uuid.UUID] = uuid_pk()
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("theses.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    paper_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    working_title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    working_title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_question_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    # بصمة التداخل — مصدرها عناصر الرسالة لا تخمين.
    sample_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    variable_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    result_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    table_figure_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    published_output_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    draft_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    readiness_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    readiness_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    readiness_components: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    salami_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # §23.8 — أعمار تُحسب وتُعلَن قبل التحويل.
    data_age_years: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    literature_age_years: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # §23.9 / TC-06 — بوابة GT1.
    rights_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    rights_approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authorship_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    authorship_approved_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # discovered | analysed | rights_pending | ready_to_submit | converted | rejected
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="discovered")
    converted_project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="SET NULL"), nullable=True
    )


class OpportunityOverlapScore(Base, TenantScoped, Timestamped):
    """§23.7 — نتيجة مقارنة زوج، بسياستها. التداخل علاقة لا خاصية فرصة."""

    __tablename__ = "opportunity_overlap_scores"
    __table_args__ = (
        UniqueConstraint("left_opportunity_id", "right_opportunity_id", "policy_id",
                         name="uq_overlap_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    left_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )
    right_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("overlap_policies.id", ondelete="RESTRICT"), nullable=False
    )
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    exceeded: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    not_computed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    salami_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # قرار بشري عند التنبيه: دمج أو تبرير معتمد (TC-05).
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resolution_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthorshipParty(Base, TenantScoped, Timestamped):
    """§24.2 — طرف يمكن أن يحمل تأليفًا: إنسان أو جهة. لا ثالث لهما."""

    __tablename__ = "authorship_parties"

    id: Mapped[uuid.UUID] = uuid_pk()
    party_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    affiliation_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AuthorshipAgreement(Base, TenantScoped, Timestamped):
    """§23.9 — اتفاق تأليف على فرصة، بترتيبه وموافقته الموثقة."""

    __tablename__ = "authorship_agreements"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "party_id", name="uq_authorship_agreement"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="CASCADE"),
        nullable=False,
    )
    party_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("authorship_parties.id", ondelete="RESTRICT"),
        nullable=False,
    )
    author_position: Mapped[int] = mapped_column(Integer, nullable=False)
    is_corresponding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    consent_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    consent_recorded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # §24.2 — كل تغيير في الترتيب يُسجَّل بتاريخه.
    order_change_log: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class CreditRoleAssignment(Base, TenantScoped, Timestamped):
    """§24.1 — دور CRediT مُسند إلى طرف. لا يُستنتج ولا يُمنح تلقائيًا."""

    __tablename__ = "credit_role_assignments"
    __table_args__ = (
        UniqueConstraint("agreement_id", "credit_role", name="uq_credit_role_assignment"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    agreement_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("authorship_agreements.id", ondelete="CASCADE"),
        nullable=False,
    )
    credit_role: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
