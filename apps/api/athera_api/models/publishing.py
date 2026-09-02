"""المخطوطة والمجلات والمراجعة | Manuscripts, journals and review (§19، §20، §21، §22)."""

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..services.publishing.vocab import (  # noqa: F401 — إعادة تصدير مقصودة
    MANUSCRIPT_SECTIONS,
    READINESS_STATUSES,
    REVIEWER_ROLES,
    SUBMISSION_PACKAGE_ITEMS,
    TRUST_TIERS,
)
from .base import Base, TenantScoped, Timestamped, uuid_pk

__all__ = [
    "Manuscript", "ManuscriptVersion", "ManuscriptSection", "JournalProfile",
    "JournalPolicyCheck", "JournalMatchRow", "ReviewRound", "ReviewerReportRow",
    "ReviewPatch", "SubmissionPackage",
    "MANUSCRIPT_SECTIONS", "TRUST_TIERS", "REVIEWER_ROLES", "READINESS_STATUSES",
    "SUBMISSION_PACKAGE_ITEMS",
    "ManuscriptSectionClaim", "ClaimMemoryLink", "ClaimAnalysisLink",
]


class Manuscript(Base, TenantScoped, Timestamped):
    """§19 — المخطوطة. بوابة G9 لها لقطة جاهزية، فالاعتماد يقع على حالة معروفة."""

    __tablename__ = "manuscripts"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="ar")
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    g9_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    g9_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    g9_readiness_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── S5E — من أي فرصة ومن أي هيكل وُلدت هذه المخطوطة ──
    #
    # عمودان لا كيانٌ ثالث: `Manuscript → ManuscriptVersion → ManuscriptSection`
    # تمثّل بالفعل وعاء المسودة وتاريخ مراجعاتها ومحتوى أقسامها. وكلاهما قابل
    # للعدم — مخطوطات ما قبل S5E لا فرصة لها ولا هيكل، ولا تُخترع لها قيمة.
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("publication_opportunities.id", ondelete="SET NULL"),
        nullable=True,
    )
    outline_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_outlines.id", ondelete="SET NULL"),
        nullable=True,
    )


class ManuscriptVersion(Base, TenantScoped, Timestamped):
    """§19.2 — لا تغيير لعنصر معتمد دون نسخة جديدة بسبب مكتوب."""

    __tablename__ = "manuscript_versions"
    __table_args__ = (UniqueConstraint("manuscript_id", "version_label",
                                       name="uq_manuscript_version"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    change_reason_ar: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ManuscriptSection(Base, TenantScoped, Timestamped):
    __tablename__ = "manuscript_sections"
    __table_args__ = (UniqueConstraint("version_id", "section_key",
                                       name="uq_manuscript_section"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_key: Mapped[str] = mapped_column(String(32), nullable=False)
    text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # §19.2 — الادعاءات والتشغيلات مرتبطة بالقسم، فتُفحص بوابة G9 عليها.
    # **موروثة، وليست مرجعًا** (S5E): السند البنيوي في
    # `manuscript_section_claims` و`claim_analysis_links`.
    claim_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    analysis_run_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # ── S5E — حال مراجعة القسم وبصمة سياق صياغته ──
    #
    # والبصمة على القسم لا على المخطوطة: الإذن يُعطى لصياغة **قسم** من أدلةٍ
    # بعينها، وأدلةٌ تُضاف بعده لا تُرسل تحته.
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    drafting_context_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )


class JournalProfile(Base, TenantScoped, Timestamped):
    """§20.1 — ملف المجلة. طبقة الثقة بلا تاريخ حساب ادعاء بلا زمن."""

    __tablename__ = "journal_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="CASCADE"), nullable=False
    )
    trust_tier: Mapped[str | None] = mapped_column(String(1), nullable=True)
    tier_computed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scope_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    recent_article_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    accepted_methods: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    apc_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    oa_model: Mapped[str | None] = mapped_column(String(24), nullable=True)
    ai_policy_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_requirements: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    median_review_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_suspicious: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class JournalPolicyCheck(Base, TenantScoped, Timestamped):
    """§20.3 / TC-04 — سجل إعادة التحقق عند النقاط الأربع."""

    __tablename__ = "journal_policy_checks"

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="CASCADE"), nullable=False
    )
    verification_point: Mapped[str] = mapped_column(String(24), nullable=False)
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    indexing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)


class JournalMatchRow(Base, TenantScoped, Timestamped):
    """§20.4 — لا حقل لاحتمال قبول هنا، وهذه هي الضمانة."""

    __tablename__ = "journal_matches"
    __table_args__ = (UniqueConstraint("manuscript_id", "journal_id", name="uq_journal_match"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="RESTRICT"), nullable=False
    )
    fit_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trust_tier: Mapped[str] = mapped_column(String(1), nullable=False)
    blockers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    uncomputed: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    indexing_verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    g10_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    g10_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReviewRound(Base, TenantScoped, Timestamped):
    __tablename__ = "review_rounds"
    __table_args__ = (UniqueConstraint("manuscript_id", "round_number", name="uq_review_round"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    readiness_status: Mapped[str] = mapped_column(String(24), nullable=False)
    major_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviewers_missing: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class ReviewerReportRow(Base, TenantScoped, Timestamped):
    __tablename__ = "reviewer_reports"
    __table_args__ = (UniqueConstraint("round_id", "reviewer_role", name="uq_reviewer_report"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    round_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_role: Mapped[str] = mapped_column(String(24), nullable=False)
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    major_concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    minor_concerns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    rejection_reasons: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ReviewPatch(Base, TenantScoped, Timestamped):
    """§21 — الرقعة تبدأ مقترحة، وتطبيقها يستلزم فاعلًا و**نسخة جديدة**."""

    __tablename__ = "review_patches"

    id: Mapped[uuid.UUID] = uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("reviewer_reports.id", ondelete="CASCADE"), nullable=False
    )
    section_key: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale_ar: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_text_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_in_version_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_versions.id", ondelete="SET NULL"),
        nullable=True,
    )


class SubmissionPackage(Base, TenantScoped, Timestamped):
    """§22.1 — «مكتملة» تعني فعلًا لا عنصر إلزاميًا ناقصًا."""

    __tablename__ = "submission_packages"

    id: Mapped[uuid.UUID] = uuid_pk()
    manuscript_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscripts.id", ondelete="CASCADE"), nullable=False
    )
    journal_match_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journal_matches.id", ondelete="SET NULL"), nullable=True
    )
    items_present: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_required: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_optional: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    assembled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ManuscriptSectionClaim(Base, TenantScoped, Timestamped):
    """قسم مخطوطة ← ادعاء، **بمفتاح أجنبي لا بمصفوفة معرّفات** (S5E).

    `ManuscriptSection.claim_ids` تبقى للتوافق ولا تكون مرجعًا: مصفوفة JSON
    تُجيب اليوم وتكذب غدًا حين يُحذف ادعاء فيبقى معرّفه معلّقًا بلا أن ينبّه
    أحد. والمفتاح الأجنبي يمنع ذلك أو يعلنه.
    """

    __tablename__ = "manuscript_section_claims"
    __table_args__ = (UniqueConstraint("section_id", "claim_id", name="uq_section_claim"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("manuscript_sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ClaimMemoryLink(Base, TenantScoped, Timestamped):
    """ادعاء ← ذاكرة الباحث الموثقة (S5E).

    `ClaimEvidenceLink` القائم يشترط مقتطفًا من **مصدر أدبيات خارجي**،
    وكلا المفتاحين غير قابل للعدم. فلا يستطيع أن يقول: «هذا الادعاء تسنده
    معرفة الباحث الموثقة» — وذلك بالضبط ما تحتاجه S5E، والسجل الخارجي مغلق
    حتى S5F.

    **ولا نسخ للإسناد:** الموضع والاقتباس والملف تملكها `researcher_memories`.
    والسلسلة: قسم → ادعاء → رابط → ذاكرة → إسناد.
    """

    __tablename__ = "claim_memory_links"
    __table_args__ = (UniqueConstraint("claim_id", "memory_id", name="uq_claim_memory"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    # `RESTRICT` عمدًا: دليلٌ يسند ادعاءً في مخطوطة لا يختفي صامتًا.
    memory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_memories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    support_level: Mapped[str] = mapped_column(String(16), nullable=False)


class ClaimAnalysisLink(Base, TenantScoped, Timestamped):
    """ادعاء ← **المخرَج التحليلي بعينه** لا التشغيلة وحدها (S5E §27).

    `ManuscriptSection.analysis_run_ids` تثبت أن «تشغيلةً ما موجودة في هذا
    القسم» — ولا تثبت أن **هذا الرقم** خرج من **ذلك المخرَج**. وقسمٌ فيه
    تشغيلة انحدار لا يجعل متوسطًا مكتوبًا فيه مسنَدًا.

    و`statistic_excerpt` يحفظ الصيغة كما وردت في الادعاء، فيبقى التطابق
    قابلًا للفحص بعد شهور.

    **ولا عمود `run_id`:** التشغيلة تُشتقّ من `AnalysisOutputRow.run_id` —
    مصدر حقيقة واحد لا عمودان يفترقان.
    """

    __tablename__ = "claim_analysis_links"
    __table_args__ = (UniqueConstraint("claim_id", "output_id", name="uq_claim_analysis"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    output_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("analysis_outputs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    statistic_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
