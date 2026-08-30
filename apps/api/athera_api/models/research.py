"""ملف الباحث والذاكرة الموثقة | Researcher profile and verified memory.

المراجع: §7.3 (فئات الذاكرة)، §7.4 (قاعدة الترقية)، §10 (ملف الباحث)،
§33.1 (التقطيع والـlocators).

القاعدة الحاكمة: لا شيء هنا يصبح «موثقًا» بمرور الوقت أو بثقة النموذج —
بل بمسار من أربعة فقط، وبقرار إنسان حيث يلزم.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# §7.3 — فئات الذاكرة الثماني ومستوى التحقق المطلوب لكل واحدة.
MEMORY_CATEGORIES: Final[dict[str, str]] = {
    "researcher_fact": "user_or_document",     # الرتبة، التخصص، المهارات
    "promotion_policy": "official_source",     # الوحدات، النقاط، شروط المجلات
    "verified_evidence": "bibliographic",      # دراسة، DOI، نتيجة منشورة
    "project_decision": "human_approval",      # السؤال، النظرية، المنهج، المجلة
    "working_hypothesis": "provisional",       # فكرة أو علاقة مقترحة
    "journal_fact": "source_with_timestamp",   # الفهرسة، الرسوم، النطاق
    "analysis_result": "reproducible_run",     # قيمة إحصائية أو جدول
    "temporary_context": "expires",            # محادثة مؤقتة
}

# §7.4 — المسارات الأربعة التي تسمح وحدها بالوصول إلى verified.
PROMOTION_PATHS: Final = ("external_source", "upload", "analysis_run", "user_statement")


class ResearcherProfile(Base, TenantScoped, Timestamped):
    """§10.1 — ملف الباحث الأكاديمي."""

    __tablename__ = "researcher_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_researcher_profiles_user"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )

    institution_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    college_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    college_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_en: Mapped[str | None] = mapped_column(String(255), nullable=True)

    current_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rank_started_on: Mapped[dt.date | None] = mapped_column(nullable=True)

    primary_field_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_field_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scholar_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # §10.1 — تفضيلات الكتابة، والأبحاث التي لا يريد الباحث تكرارها.
    writing_preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    excluded_topics: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    future_interests: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # بوابة G0 (§9) — الملف لا يُعتمد بمجرد اكتماله.
    g0_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    g0_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )


class ResearcherSkill(Base, TenantScoped, Timestamped):
    """§10.1 — النظريات والمناهج والبرمجيات واللغات، كل واحدة بمصدرها."""

    __tablename__ = "researcher_skills"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False
    )
    # theory | method | software | language | design
    skill_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # مثبت بالتدريب أم بالاستخدام الفعلي — الفرق يهم في ملف الترقية.
    evidence_level: Mapped[str] = mapped_column(String(24), nullable=False, default="claimed")
    memory_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ResearcherMemory(Base, TenantScoped, Timestamped):
    """§7.3 — الذاكرة المنظمة. ليست سجل محادثة، بل كائنات لها مصدر وحالة."""

    __tablename__ = "researcher_memories"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=True
    )
    memory_category: Mapped[str] = mapped_column(String(32), nullable=False)

    statement_ar: Mapped[str] = mapped_column(Text, nullable=False)
    statement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # المصدر: أحد مسارات §7.4 الأربعة، مع موضع دقيق واقتباس حرفي.
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    source_locator: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)

    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # temporary_context وحدها تنتهي صلاحيتها (§7.3).
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class DocumentChunk(Base, TenantScoped, Timestamped):
    """§33.1 — تقطيع بنيوي مع موضع دقيق. مقطع بلا locator لا يصلح مصدرًا."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "seq", name="uq_document_chunks_seq"),
        CheckConstraint("length(text) > 0", name="ck_document_chunks_text_not_empty"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # الموضع القابل للاستشهاد: "p.12 §3.2 ¶4"
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)

    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # §33.3 — كل ما جاء من ملف أو ويب أو API محتوى غير موثوق.
    is_untrusted: Mapped[bool] = mapped_column(nullable=False, default=True)
    # يُملأ فقط عند توفر مزود embeddings حقيقي؛ NULL ليس خطأ.
    embedding_model: Mapped[str | None] = mapped_column(String(96), nullable=True)


class ExtractionRun(Base, TenantScoped, Timestamped):
    """تشغيلة استخراج واحدة على ملف — قابلة للإعادة والمقارنة."""

    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    extractor: Mapped[str] = mapped_column(String(32), nullable=False)  # rules | model
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    chunks_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_proposed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # مرشّحات رُفضت آليًا لأن اقتباسها غير موجود في المصدر — مؤشر اختلاق مباشر.
    candidates_rejected_unquoted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class FactCandidate(Base, TenantScoped, Timestamped):
    """§10.2 — شاشة المراجعة: Fact · Source File · Page/Section · Confidence · Status.

    يبدأ دائمًا `unverified`. لا يوجد مسار يجعله يبدأ بغير ذلك.
    """

    __tablename__ = "fact_candidates"

    id: Mapped[uuid.UUID] = uuid_pk()
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("extraction_runs.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )

    memory_category: Mapped[str] = mapped_column(String(32), nullable=False)
    field_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    statement_ar: Mapped[str] = mapped_column(Text, nullable=False)
    statement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # الاقتباس الحرفي — شرط قبول لا حقل عرض. يُتحقق من وجوده في نص المقطع.
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resulting_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_memories.id", ondelete="SET NULL"), nullable=True
    )
