"""الأدبيات والأدلة | Literature and evidence (§14).

ثلاث قواعد بنيوية تحكم هذا الملف:

1. **المقتطف لا يوجد إلا حيث يوجد نص** (§14.5). مصدر حالته Metadata-only لا
   يستطيع حمل مقتطف — بقيد في قاعدة البيانات، لا بانضباط مطوّر.
2. **السحب حالة متغيرة**. لقطات `source_versions` تجيب: متى كان هذا المصدر
   سليمًا؟ وهو السؤال الذي يحمي ورقة استشهدت به قبل سحبه.
3. **الدليل المناقض يُعرض**. `support_level='contradictory'` قيمة أولى في
   السجل، لا استثناء يُخفى.
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# §14.2 — حالات الوصول الخمس، ومعها هل تسمح كل حالة بمقتطف من النص.
ACCESS_STATES: Final[dict[str, bool]] = {
    "open_access_full_text": True,
    "user_uploaded_rights_confirmed": True,
    "licensed_institutional_access": True,
    "abstract_metadata_only": False,   # §14.5 — لا مقتطف، فلا تفاصيل نص
    "restricted_no_processing_right": False,
}

TEXT_BEARING_STATES: Final = tuple(k for k, v in ACCESS_STATES.items() if v)

# §14.4 — مستويات الدعم الأربعة.
SUPPORT_LEVELS: Final[dict[str, tuple[str, str]]] = {
    "direct": ("دعم مباشر", "Direct support"),
    "partial": ("دعم جزئي", "Partial support"),
    "contextual": ("دعم سياقي", "Contextual support"),
    "contradictory": ("دليل مناقض", "Contradictory evidence"),
}

CLAIM_TYPES: Final = ("empirical", "theoretical", "contextual", "interpretive")

# حالة السحب/التصحيح (§14.3).
RETRACTION_STATES: Final = ("none", "correction", "expression_of_concern", "retracted", "unknown")


class Journal(Base, TenantScoped, Timestamped):
    """§20.1 — سجل المجلة. الفهرسة في جدول مستقل لأنها متغيرة ومؤرَّخة."""

    __tablename__ = "journals"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(512), nullable=True)
    issn: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eissn: Mapped[str | None] = mapped_column(String(16), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_open_access: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    external_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class JournalIndexingRecord(Base, TenantScoped, Timestamped):
    """كل ادعاء فهرسة له مصدر وتاريخ تحقق — بلا ذلك لا يُقبل (§20.1، §39)."""

    __tablename__ = "journal_indexing_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="CASCADE"), nullable=False
    )
    index_name: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # active|discontinued|unknown
    coverage_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    coverage_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    last_verified_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Author(Base, TenantScoped, Timestamped):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = uuid_pk()
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True)
    external_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Source(Base, TenantScoped, Timestamped):
    """§14.3 — سجل المصدر بحقوله الثلاثة عشر."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("tenant_id", "doi", name="uq_sources_doi"),)

    id: Mapped[uuid.UUID] = uuid_pk()

    # 1–5: التعريف الببليوغرافي
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    journal_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("journals.id", ondelete="SET NULL"), nullable=True
    )
    journal_name_raw: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # 6–10: الوصف العلمي — يُملأ من النص فقط، ويبقى فارغًا لمصدر بلا نص.
    theory: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 11–13: الحالة والحقوق والتحقق
    retraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    retraction_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_state: Mapped[str] = mapped_column(String(40), nullable=False,
                                              default="abstract_metadata_only")
    last_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    registry: Mapped[str | None] = mapped_column(String(32), nullable=True)  # openalex|crossref|upload
    registry_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    # §33.3 — ما جاء من سجل خارجي بيانات لا تعليمات.
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class SourceVersion(Base, TenantScoped, Timestamped):
    """لقطة حالة عند كل تحقق — تجيب: متى كان هذا المصدر سليمًا؟"""

    __tablename__ = "source_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    registry: Mapped[str] = mapped_column(String(32), nullable=False)
    retraction_status: Mapped[str] = mapped_column(String(32), nullable=False)
    access_state: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class SourceAuthor(Base, TenantScoped, Timestamped):
    __tablename__ = "source_authors"
    __table_args__ = (UniqueConstraint("source_id", "position", name="uq_source_author_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("authors.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class EvidenceExcerpt(Base, TenantScoped, Timestamped):
    """مقتطف من نص مقروء فعلًا.

    وجوده دليل على أن النص كان متاحًا: قيد قاعدة البيانات يمنع إنشاءه لمصدر
    حالته Metadata-only أو Restricted (§14.5).
    """

    __tablename__ = "evidence_excerpts"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    # حالة الوصول وقت الاقتطاف — الحقوق قد تتغير لاحقًا.
    access_basis: Mapped[str] = mapped_column(String(40), nullable=False)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class Claim(Base, TenantScoped, Timestamped):
    """§14.4 — الادعاء الجوهري. لا يُغلق بلا دليل، ولا مع مناقض غير معالج."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=True
    )
    text_ar: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_type: Mapped[str] = mapped_column(String(24), nullable=False)
    section: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # draft | supported | evidence_gap | final
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    verification_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unverified")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    reviewed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # §4 — ما لا دليل عليه يُوسم استنتاجًا صراحةً بدل تمريره كحقيقة.
    is_labelled_inference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ClaimEvidenceLink(Base, TenantScoped, Timestamped):
    """الرابط بين ادعاء ودليل، بمستوى دعمه ومراجعه."""

    __tablename__ = "claim_evidence_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "excerpt_id", name="uq_claim_evidence"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    claim_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False
    )
    excerpt_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("evidence_excerpts.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    support_level: Mapped[str] = mapped_column(String(16), nullable=False)
    # §14.5 — الاستشهاد بمسحوب ممكن «بتحذير وسياق واضح»، لا صامتًا.
    retraction_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledgement_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # الدليل المناقض يحتاج معالجة مكتوبة قبل إغلاق الادعاء.
    resolution_note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note_en: Mapped[str | None] = mapped_column(Text, nullable=True)
