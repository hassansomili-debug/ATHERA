"""طبقة التركيب | Synthesis: themes, contradictions, gaps, opportunities (PUBRIVA).

**المفردات تُكتب مرّة.** الترحيل 0024 يحمل القيد، وهذه هي المفردة نفسها في
الشيفرة — واختبارٌ يقابل الاثنين مجموعةً بمجموعة، لأن الخطأ المتكرر في هذا
المستودع مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.

**ولا مفردةً جديدة تعني ما للمنصّة مفردةٌ له.** `needs_review` من حالات
الخلية في 0023 ومن «دماغ البحث»، و`unknown` من ترحيل 0016 — والثالثة هي
التي تحفظ الفرق بين «راجعتُه ورفضتُه» و«راجعتُه ولم أستطع الحكم». ولا
`UNSURE` ولا `MAYBE` هنا.

**والاسم عقد.** `GapCandidate` لا `ConfirmedGap`: لا صفّ في هذه الجداول
يقول «هذه فجوة مؤكَّدة»، و`approved` تعني «قرّر باحثٌ متابعتها» لا «ثبتت».
"""

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# ── المفردات ──

SYNTHESIS_STATUSES: Final = ("generated", "needs_review", "approved", "rejected",
                             "unknown")

# الحالات التي لم يقلها إنسان بعد — وما عداها يلزمه صاحبٌ ووقت.
UNDECIDED_STATUSES: Final = ("generated", "needs_review")

# الحالات التي يقبلها الـAPI مُدخَلًا في قرار الباحث. و`generated` ليست
# منها: هي حالُ النشأة، وقبولها مُدخَلًا يعني «أعِد المرشَّح إلى ما قبل أن
# ينظر فيه أحد» — وهو محوُ مراجعةٍ وقعت.
DECIDABLE_STATUSES: Final = ("needs_review", "approved", "rejected", "unknown")

THEME_BASES: Final = ("topic_cluster", "content_synthesis")

# **تجميعٌ موضوعي ليس نتيجة.** عناوينُ تتشارك كلمات تُجمَع؛ والموضوع العلمي
# يلزمه محتوًى قُرئ من الورقة نفسها.
TOPIC_CLUSTER: Final = "topic_cluster"
CONTENT_SYNTHESIS: Final = "content_synthesis"

GENERATION_METHODS: Final = ("deterministic", "researcher")

SUPPORT_ROLES: Final = ("supporting", "contradicting")
GAP_SOURCE_ROLES: Final = ("supporting", "contradicting", "considered")

CONFLICT_KINDS: Final = ("direction", "significance", "effect_presence", "conclusion")

EFFECT_DIRECTIONS: Final = ("positive", "negative", "none", "mixed", "not_stated")
SIGNIFICANCE_STATES: Final = ("significant", "not_significant", "not_stated")

GAP_TYPES: Final = (
    "context_gap",
    "population_gap",
    "method_gap",
    "theory_gap",
    "measurement_gap",
    "temporal_gap",
    "contradictory_evidence",
    "understudied_relationship",
    "replication_need",
)

GAP_STRENGTHS: Final = ("weak_signal", "emerging_pattern", "supported_candidate")

SOURCE_SCOPES: Final = ("metadata_only", "abstract_only", "full_text")


class ThemeCandidate(Base, TenantScoped, Timestamped):
    """موضوعٌ مرشَّح — و`basis` يقول أهو تجميعٌ موضوعي أم تركيبٌ من محتوى."""

    __tablename__ = "theme_candidates"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_theme_candidates_scoped"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    label_ar: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    basis: Mapped[str] = mapped_column(String(24), nullable=False)
    source_scope_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generation_method: Mapped[str] = mapped_column(
        String(24), nullable=False, default="deterministic")
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="generated")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class ThemeCandidateSupport(Base, TenantScoped, Timestamped):
    """سندُ موضوعٍ واحد — **ومعه الخلية التي قُرئ منها**.

    وهو ما يجعل المسار كاملًا: موضوع ← مرجع ← خلية ← شاهد. وسندٌ يدّعي
    محتوًى بلا خليةٍ يشير إليها يرفضه القيد في القاعدة.
    """

    __tablename__ = "theme_candidate_supports"
    __table_args__ = (
        UniqueConstraint("theme_id", "source_id", "role", "basis_field_key",
                         name="uq_theme_support"),
        ForeignKeyConstraint(
            ["theme_id", "project_id"],
            ["theme_candidates.id", "theme_candidates.project_id"],
            ondelete="CASCADE", name="fk_theme_candidate_supports_theme"),
        ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_theme_candidate_supports_cell"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    basis_field_key: Mapped[str] = mapped_column(String(32), nullable=False)
    matrix_cell_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    evidence_scope: Mapped[str] = mapped_column(String(16), nullable=False)


class ContradictionCandidate(Base, TenantScoped, Timestamped):
    """تعارضٌ محتمل بين نتيجتين — **ببناءَيه المتقابلين وسياق اختلافهما**."""

    __tablename__ = "contradiction_candidates"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_contradiction_candidates_scoped"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    construct_a_ar: Mapped[str] = mapped_column(Text, nullable=False)
    construct_b_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    relationship_ar: Mapped[str] = mapped_column(Text, nullable=False)
    conflict_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    context_explanation_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_divergence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    generation_method: Mapped[str] = mapped_column(
        String(24), nullable=False, default="deterministic")
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="generated")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class ContradictionSide(Base, TenantScoped, Timestamped):
    """طرفٌ واحد من التعارض — **والطرفان يُحفظان كلاهما**.

    ولا يُسمّى أحدهما خطأً: تعارضٌ يُسجَّل بطرفٍ واحد يجعل الثاني باطلًا
    بالسكوت عنه.
    """

    __tablename__ = "contradiction_sides"
    __table_args__ = (
        UniqueConstraint("contradiction_id", "side", "source_id",
                         name="uq_contradiction_side"),
        ForeignKeyConstraint(
            ["contradiction_id", "project_id"],
            ["contradiction_candidates.id", "contradiction_candidates.project_id"],
            ondelete="CASCADE", name="fk_contradiction_sides_parent"),
        ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_contradiction_sides_cell"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    contradiction_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False)
    side: Mapped[str] = mapped_column(String(1), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    matrix_cell_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    result_ar: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False,
                                           default="not_stated")
    significance: Mapped[str] = mapped_column(String(16), nullable=False,
                                              default="not_stated")
    population_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    method_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    measurement_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_scope: Mapped[str] = mapped_column(String(16), nullable=False)


class GapCandidate(Base, TenantScoped, Timestamped):
    """فجوةٌ **محتملة** — بحدودها معلنةً معها لا بعدها.

    و`sources_considered` و`search_scope` ليسا زينة: بدونهما لا يمكن الحكم
    على الدعوى أصلًا، وتصير «لم تظهر دراسة» جملةً مطلقة لا يحدّها شيء.
    """

    __tablename__ = "gap_candidates"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_gap_candidates_scoped"),
        UniqueConstraint("id", "status", name="uq_gap_candidates_status"),
        ForeignKeyConstraint(
            ["contradiction_id", "project_id"],
            ["contradiction_candidates.id", "contradiction_candidates.project_id"],
            ondelete="CASCADE", name="fk_gap_candidates_contradiction"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    gap_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)
    why_suggested_ar: Mapped[str] = mapped_column(Text, nullable=False)
    sources_considered: Mapped[int] = mapped_column(Integer, nullable=False)
    search_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_scope_distribution: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict)
    known_limitations_ar: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[str] = mapped_column(String(24), nullable=False)
    contradiction_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    generation_method: Mapped[str] = mapped_column(
        String(24), nullable=False, default="deterministic")
    generated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="generated")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class GapCandidateSource(Base, TenantScoped, Timestamped):
    """مرجعٌ في مدى فجوةٍ — مُسنِدًا أو معارضًا أو **منظورًا فيه**.

    والثالثة هي التي تمنع الفجوة من أن تبدو أوسع مما نُظر فيه: مرجعٌ فُحص
    ولم يسند ولم يعارض جزءٌ من الجواب، لا صمتٌ يُطرح.
    """

    __tablename__ = "gap_candidate_sources"
    __table_args__ = (
        UniqueConstraint("gap_id", "source_id", "role", name="uq_gap_source"),
        ForeignKeyConstraint(
            ["gap_id", "project_id"],
            ["gap_candidates.id", "gap_candidates.project_id"],
            ondelete="CASCADE", name="fk_gap_candidate_sources_gap"),
        ForeignKeyConstraint(
            ["matrix_cell_id", "project_id"],
            ["literature_matrix_cells.id", "literature_matrix_cells.project_id"],
            name="fk_gap_candidate_sources_cell"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    gap_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    matrix_cell_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    evidence_scope: Mapped[str] = mapped_column(String(16), nullable=False)


class ResearchOpportunity(Base, TenantScoped, Timestamped):
    """بطاقةُ فرصةٍ بحثية — **من فجوةٍ اعتمدها إنسان وحدها**.

    و`gap_status` ليست نسخةً تتقادم: هي نصف مفتاحٍ أجنبيٍّ مركّب يجعل
    القاعدة نفسها ترفض فرصةً فوق فجوةٍ غير معتمَدة، و`ON UPDATE RESTRICT`
    يمنع سحب الاعتماد من تحت فرصةٍ قائمة.
    """

    __tablename__ = "research_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["gap_candidate_id", "gap_status"],
            ["gap_candidates.id", "gap_candidates.status"],
            onupdate="RESTRICT", ondelete="RESTRICT",
            name="fk_research_opportunities_gap"),
        ForeignKeyConstraint(
            ["gap_candidate_id", "project_id"],
            ["gap_candidates.id", "gap_candidates.project_id"],
            name="fk_research_opportunities_gap_project"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    gap_candidate_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False)
    gap_status: Mapped[str] = mapped_column(String(16), nullable=False,
                                            default="approved")
    phenomenon_ar: Mapped[str] = mapped_column(Text, nullable=False)
    context_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    population_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    constructs_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_contribution_ar: Mapped[str] = mapped_column(Text, nullable=False)
    methodological_opportunity_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_basis_ar: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainties_ar: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    spawned_project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="SET NULL"),
        nullable=True)


__all__ = [
    "CONFLICT_KINDS",
    "CONTENT_SYNTHESIS",
    "DECIDABLE_STATUSES",
    "EFFECT_DIRECTIONS",
    "GAP_SOURCE_ROLES",
    "GAP_STRENGTHS",
    "GAP_TYPES",
    "GENERATION_METHODS",
    "SIGNIFICANCE_STATES",
    "SOURCE_SCOPES",
    "SUPPORT_ROLES",
    "SYNTHESIS_STATUSES",
    "THEME_BASES",
    "TOPIC_CLUSTER",
    "UNDECIDED_STATUSES",
    "ContradictionCandidate",
    "ContradictionSide",
    "GapCandidate",
    "GapCandidateSource",
    "ResearchOpportunity",
    "ThemeCandidate",
    "ThemeCandidateSupport",
]
