"""استقطابُ المتعاونين | Research recruitment — opportunities and applications.

**ولمَ نطاقٌ جديد لا إعادةُ استعمال ما هو قائم.**

فُتِّش أوّلًا (§34)، ووُجد اسمانِ مشغولان بمفهومَين آخرين تمامًا:

  • `models.synthesis.ResearchOpportunity` (جدول `research_opportunities`) —
    **فرصةٌ بحثية مشتقّةٌ من فجوةٍ في الأدبيّات**: سؤالٌ يستحقّ أن يُدرس،
    نصفُ مفتاحِه الأجنبيّ حالُ الفجوة. لا علاقةَ له باستقطاب أحد.
  • `models.thesis.PublicationOpportunity` — **فرصةُ نشرٍ مستخرجةٌ من
    رسالة**: ورقةٌ يمكن أن تُكتب. ولا علاقةَ لها بالاستقطاب كذلك.

فالاسمُ الثالث يلزم، ولا يجوز تحميلُ أحد القائمين معنًى ثالثًا: جدولٌ
يحمل مفهومَين يصير كلُّ استعلامٍ عليه سؤالًا عن «أيَّ نوعٍ تقصد».

## الحدُّ الذي يميّز هذا النطاق عن كلّ ما قبله

**التطبيقُ قد يأتي من مستأجرٍ آخر.** وهذا أوّلُ صفٍّ في المنصّة كلِّها
يُكتب بيد فاعلٍ لا ينتمي إلى مستأجر الصفّ — فباحثٌ في جامعةٍ يتقدّم إلى
فرصةٍ أنشأها بحثٌ في جامعةٍ أخرى.

ولذلك **لا تحمل `RecruitmentApplication` سياسةَ عزلٍ بالمستأجر.** ولو
حملتها لاستحال المنتج: بأيّ مستأجرٍ تُوسم؟ لو وُسمت بمستأجر الفرصة لم
يرَ المتقدّمُ تقدّمَه، ولو وُسمت بمستأجر المتقدّم لم يرَه صاحبُ الفرصة.
فحدُّها **الفاعلُ** (`app_current_actor()`) لا المستأجر — وهو ما استوجب
تدقيقَ مصدر الفاعل قبل كتابة سطرٍ واحد من سياساتها.

و`applicant_tenant_id` يبقى عمودًا **للأثر والتدقيق لا للتفويض**: يُعرف
منه من أيّ مؤسسةٍ جاء المتقدّم، ولا تُبنى عليه سياسة.

## وما لا يقع هنا

ولا عضويّةَ تُنشأ من قبولِ تطبيق: المتقدّمُ المختار يُدعى بـ
`ProjectInvitation` القائمة، والدعوةُ تُقبل بيد صاحبها. والعضويّةُ ليست
تأليفًا، ولا أدوارَ CRediT تُكتب من هنا (§11 من التكليف، و§ ROLE !=
CREDIT != AUTHORSHIP).

ولا مفرداتَ توظيفٍ في هذا النطاق: لا راتبَ ولا عقدَ عملٍ ولا «تعيين».
«مساعدُ بحث» وسمُ تعاونٍ لا وظيفة.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

#: حالاتُ الفرصة — **حتميّةٌ ومغلقة**، والقاعدةُ لا تقبل غيرها.
#:
#: و`deleted` حالةٌ لا حذفٌ: الفرصةُ التي تقدّم إليها باحثون لا تُمحى من
#: تحت تطبيقاتهم، فيبقى الصفُّ وتسقط الفرصةُ من كلّ اكتشاف.
OPPORTUNITY_STATES: Final[tuple[str, ...]] = (
    "draft", "scheduled", "open", "closed", "deleted")

#: حالاتُ التطبيق.
APPLICATION_STATES: Final[tuple[str, ...]] = (
    "pending", "shortlisted", "declined", "invited", "withdrawn")

#: **ما يُعَدّ تطبيقًا قائمًا** — وعليه يقوم منعُ التكرار.
#:
#: والمنسحبُ والمرفوضُ ليسا قائمَين: من انسحب له أن يعود، ومن رُفض له أن
#: يتقدّم لفرصةٍ أخرى من الفرص نفسها لو أُعيد فتحُها. أمّا `invited` فقائم:
#: الدعوةُ أُرسلت ولم يُحسم أمرُها بعد.
ACTIVE_APPLICATION_STATES: Final[tuple[str, ...]] = (
    "pending", "shortlisted", "invited")

#: الصلاحيةُ التي تُدير الاستقطاب — صفٌّ صريح، لا دورٌ يُفسَّر.
MANAGE_RECRUITMENT: Final = "manage_team"


class RecruitmentOpportunity(Base, TenantScoped, Timestamped):
    """فرصةُ تعاونٍ يُعلنها بحثٌ ليجد من يشارك فيه.

    وهي مملوكةٌ لبحثٍ، فلها مستأجرٌ ومشروعٌ ومديرٌ. والاكتشافُ العالميّ
    يقرأ منها **إسقاطًا آمنًا** لا الصفَّ نفسه — انظر العرض
    `recruitment_opportunities_public` في الترحيل 0034.
    """

    __tablename__ = "recruitment_opportunities"
    __table_args__ = (
        # **والأسماءُ قصيرةٌ عمدًا.** اصطلاحُ `ck_%(table_name)s_%(constraint_name)s`
        # يُبادئ ما يُكتب هنا، واسمٌ مكتوبٌ كاملًا يتجاوز ثلاثةً وستين محرفًا
        # **فيُقصّ صامتًا** — وهو العطبُ الذي شرحه الترحيل 0032.
        CheckConstraint(
            "status IN ('draft','scheduled','open','closed','deleted')",
            name="status_is_known"),
        # نافذةٌ لها معنًى: نهايةٌ قبل بدايةٍ فرصةٌ لا تُفتح أبدًا، وقاعدةٌ
        # تقبلها تترك صفًّا لا يظهر ولا يُفهم سببُ غيابه.
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR starts_at < ends_at",
            name="window_is_ordered"),
        CheckConstraint("openings_count > 0", name="openings_are_positive"),
        # و«مفتوحة» تستوجب بدايةً: بلا `starts_at` لا يُعرف متى تُكتشف.
        CheckConstraint(
            "status <> 'open' OR starts_at IS NOT NULL",
            name="open_needs_a_start"),
        Index("ix_recruitment_opportunities_project", "project_id"),
        # فهرسُ الاكتشاف: الحالةُ والنافذةُ معًا، وهما شرطا كلّ قراءةٍ عالمية.
        Index("ix_recruitment_opportunities_discovery",
              "status", "starts_at", "ends_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: ما سيقدّمه المتعاون — مهامٌّ لا وعودُ نتائج.
    contributions: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ما يُطلب منه — مهاراتٌ ومعرفة.
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    openings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    collaboration_type: Mapped[str] = mapped_column(String(40), nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    starts_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ends_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    #: وسمٌ عامٌّ **يُكتب صراحةً** ليُعرض في الاكتشاف — ولا يُشتقّ من البحث.
    #:
    #: فعنوانُ البحث الحقيقيّ قد يُفصح عن فكرةٍ لم تُنشر بعد. فمن أراد أن
    #: يُظهر انتماءً كتبه بيده، ومن سكت لم يُظهر شيئًا.
    public_label: Mapped[str | None] = mapped_column(String(160), nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False)
    #: حذفٌ ناعم — والصفُّ يبقى تحت تطبيقات من تقدّموا.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class RecruitmentApplication(Base, Timestamped):
    """تقدُّمُ باحثٍ إلى فرصةٍ — **وقد يكون من مستأجرٍ آخر**.

    ولا `TenantScoped` هنا، وذاك مقصودٌ ومشروح في رأس الوحدة: الصفُّ يعيش
    بين مستأجرَين، فحدُّه الفاعلُ لا المستأجر.
    """

    __tablename__ = "recruitment_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','shortlisted','declined','invited','withdrawn')",
            name="status_is_known"),
        # والمنسحبُ له وقتُ انسحاب، والمحسومُ له وقتُ حسمٍ وفاعله — فحالةٌ
        # بلا وقتها تجعل «متى انسحب؟» سؤالًا لا جواب له.
        CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="withdrawal_has_a_time"),
        # **ولا تطبيقانِ قائمان لحسابٍ واحد على فرصةٍ واحدة.**
        #
        # وفهرسٌ **جزئيّ** لا قيدٌ كامل: من انسحب له أن يعود، ومن رُفض لا
        # يُحجَب عن فرصةٍ أخرى. فالمنعُ على القائم وحده، والقاعدةُ تحمله —
        # لا فحصٌ في الواجهة يُتجاوَز بطلبين متزامنين.
        Index("uq_recruitment_applications_active",
              "opportunity_id", "applicant_user_id",
              unique=True,
              postgresql_where=text(
                  "status IN ('pending','shortlisted','invited')")),
        Index("ix_recruitment_applications_opportunity", "opportunity_id"),
        Index("ix_recruitment_applications_applicant", "applicant_user_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    #: **و`RESTRICT` لا `CASCADE`**: تسلسلُ الحذف يجري بحقوق مالك الجدول
    #: فلا RLS تراه — وحذفُ صفِّ فرصةٍ كان سيمحو تقدُّمَ باحثين في مستأجرين
    #: آخرين. فالتطبيقُ يُثبّت فرصتَه، والإخفاءُ بـ`deleted_at`.
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("recruitment_opportunities.id", ondelete="RESTRICT"),
        nullable=False)

    #: صاحبُ التطبيق — وهو الحدُّ الأمنيّ: يُقارَن بـ`app_current_actor()`.
    applicant_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False)
    #: مؤسسةُ المتقدّم — **للأثر لا للتفويض**. ولا سياسةَ تُبنى عليه.
    applicant_tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    withdrawn_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True)


__all__ = [
    "ACTIVE_APPLICATION_STATES",
    "APPLICATION_STATES",
    "MANAGE_RECRUITMENT",
    "OPPORTUNITY_STATES",
    "RecruitmentApplication",
    "RecruitmentOpportunity",
]
