"""محفظة الأبحاث | Research portfolio (§12).

الهدف من §12.1: إدارة عدة أوراق متوازية تخدم خطًا علميًا واحدًا، بدل
أبحاث متفرقة. لذلك المشروع ينتمي إلى `research_program` — والبرنامج هو
«الخط العلمي» الذي يمنع تشتت المحفظة.
"""

import datetime as dt
import uuid

from sqlalchemy import (
    Boolean,
    Date,
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

from .base import Base, BilingualName, TenantScoped, Timestamped, uuid_pk


class ResearchProgram(Base, TenantScoped, Timestamped, BilingualName):
    """الخط العلمي الذي تخدمه عدة أوراق (§12.1)."""

    __tablename__ = "research_programs"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True
    )
    description_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearchProject(Base, TenantScoped, Timestamped):
    """§12.2 — حقول المشروع كما وردت في الوثيقة، بلا نقصان."""

    __tablename__ = "research_projects"

    id: Mapped[uuid.UUID] = uuid_pk()
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_programs.id", ondelete="SET NULL"), nullable=True
    )
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("researcher_profiles.id", ondelete="SET NULL"), nullable=True
    )

    working_title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    working_title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    study_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")

    # الوحدة المتوقعة إسقاط لا إنجاز — تبقى منفصلة عن الوحدات المحسوبة فعليًا.
    expected_units: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)
    target_journal_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    target_index_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intended_author_count: Mapped[int | None] = mapped_column(nullable=True)
    intended_author_position: Mapped[int | None] = mapped_column(nullable=True)

    risks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    # ── سلّة المهملات (PUBRIVA) ──
    #
    # **الحذف الظاهر تأجيلٌ لا إتلاف.** بحثٌ يُحذف بضغطة لا يُستعاد،
    # وسنواتُ عملٍ لا تُعاد كتابتها. فالحذف نقلٌ إلى سلّة، والإتلاف قرارٌ ثانٍ.
    archived_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)

    @property
    def is_live(self) -> bool:
        return self.deleted_at is None

    current_gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gate_approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_thesis_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProjectMember(Base, TenantScoped, Timestamped):
    """عضوٌ في بحث — **وأربعةُ أشياء لا تُخلط فيه** (الترحيل 0028).

      الدور        `role` — موقعُه في الفريق.
      الصلاحية     صفوفٌ في `project_member_permissions`، لا تُشتقّ من الدور.
      مساهمةُ CRediT `credit_roles` — **إقرارٌ يُعلَن**، ولا يُستنتج من نشاط.
      التأليف      `is_author` — إعلانٌ صريح، ولا ينشأ من وجود هذا الصفّ.

    فمحلّلٌ إحصائيّ له مساهمةُ تحليل ولا إدارةَ له على المشروع؛ ومشرفٌ
    يراجع المنهجية ولا يحرّر البيانات؛ وعضوُ فريقٍ **ليس مؤلفًا** حتى
    يُعلَن ذلك ويوافق هو عليه بحسابه.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("id", "project_id", name="uq_project_members_project_scoped"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    # **الربطُ بحساب حقيقي شرطُ التعاون.** واسمٌ معروض بلا حساب صفٌّ في
    # قائمة، لا شريكٌ يدخل ويوافق ويُنسب إليه فعل.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invited_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="co_author")
    access_state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    suspended_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    removed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    # §24 — أدوار CRediT تُسجَّل ولا تُستنتج.
    credit_roles: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── موافقةُ التأليف: مَن وافق، ومتى، وبأيّ طريق ──
    #
    # **العطبُ الذي أُصلح في 0028**: كان `consent_recorded_at` وحده، فكان
    # السجلّ يقول «وُوفق عليه» ولا يقول مَن وافق. وأيُّ مصادَقٍ في المستأجر
    # كان يكتبها عن أيِّ عضو. والقيد
    # `ck_project_members_self_consent_is_the_member` يفرض الآن في القاعدة
    # أن تكون الموافقةُ الذاتية بيد صاحبها.
    consent_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_requested")
    consent_recorded_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_recorded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    consent_method: Mapped[str | None] = mapped_column(String(24), nullable=True)
    consent_evidence_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── التأليف: إعلانٌ منفصلٌ عن العضوية ──
    is_author: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    author_position: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ProjectDecision(Base, TenantScoped, Timestamped):
    """§7.3 Project Decision — قرار له اعتماد بشري وتاريخ ونسخة."""

    __tablename__ = "project_decisions"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False
    )
    decision_kind: Mapped[str] = mapped_column(String(48), nullable=False)
    statement_ar: Mapped[str] = mapped_column(Text, nullable=False)
    statement_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate: Mapped[str | None] = mapped_column(String(8), nullable=True)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("approvals.id", ondelete="SET NULL"), nullable=True
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ProjectFile(Base, TenantScoped, Timestamped):
    """ربط ملفٍ ببحث — **رابطٌ لا نسخة** (PUBRIVA).

    الملف أصلٌ في مكتبة الباحث العامة، وقد يخدم أكثر من بحث: بياناتٌ تُقرأ
    في سياقين، أو رسالةٌ يُبنى عليها مشروعان. وعمودٌ واحد على `files` يفرض
    نسخًا — ونسخةٌ ثانية للأصل تفترق عنه بأول تعديل، ولا يعرف أحدٌ أيّهما
    الصحيح.

    و`RESTRICT` على الملف عمدًا: إزالته من مشروع شيء، وحذفه من المكتبة شيء
    آخر — ولا يقع الثاني بأثرٍ جانبي للأول.
    """

    __tablename__ = "project_files"
    __table_args__ = (UniqueConstraint("project_id", "file_id", name="uq_project_file"),)

    # **حالا الرابط، مكتوبتان مرّة واحدة.** والقيد في القاعدة لا يقبل غيرهما.
    # وكان الموجّه يكتب `"removed"` بجانبهما — لفظًا لا وجود له في القيد —
    # فكانت كل إزالةٍ ملفٍّ من بحثٍ تُنتج 500 في الإنتاج. وهو الخطأ المتكرر
    # نفسه: مفردةٌ تُكتب بجانب سجلّها بدل أن تُشتقّ منه.
    #
    # و`ARCHIVED` هي «أُزيل من هذا البحث»: الرابط يبقى للأثر ولا يُعدّ قائمًا.
    ACTIVE = "active"
    ARCHIVED = "archived"
    STATES = (ACTIVE, ARCHIVED)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("files.id", ondelete="RESTRICT"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    added_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProjectSource(Base, TenantScoped, Timestamped):
    """ربط مصدرٍ ببحث — **بحال استعماله فيه** (PUBRIVA).

    مصدرٌ «مُدرَج» في مشروع قد يكون «محفوظًا فقط» في آخر و«مستبعَدًا» في
    ثالث، وهو مصدرٌ واحد. فحالُ الاستعمال تخصّ العلاقة لا الشيء.

    والافتراض `saved_only`: **استيرادُ مصدرٍ ليس حكمًا بصلاحيته دليلًا**.
    وجعلُ كل ما يُخزَّن دليلًا افتراضًا يبني ورقةً على ما لم يقرأه أحد.
    """

    __tablename__ = "project_sources"
    __table_args__ = (UniqueConstraint("project_id", "source_id",
                                       name="uq_project_source"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    use_state: Mapped[str] = mapped_column(String(16), nullable=False,
                                           default="saved_only")
    added_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    reason_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    # **الاستبعاد حكمٌ يلزمه سبب** (الترحيل 0023). و«استُبعد» بلا سببٍ
    # مسجَّل لا يُراجَع بعد شهر ولا يُكتب في قسم المنهجية: يقرأ الباحث اسم
    # الدراسة ولا يذكر لماذا تركها — فيعيد قراءتها، أو يذكر لها سببًا من
    # ذاكرته الآن وهو أسوأ.
    #
    # والرمز من قائمةٍ مغلقة تُعدّ وتُقارن؛ و`reason_ar` نصُّها الحرّ، لازمٌ
    # مع «سبب آخر» وحده. والقيد في القاعدة يرفض الاستبعاد بلا رمز، ويرفض
    # بقاء الرمز بعد أن يزول الاستبعاد.
    exclusion_reason_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
