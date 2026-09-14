"""استقطابُ المتعاونين | Research recruitment — opportunities and applications.

**ولمَ نطاقٌ جديد لا إعادةُ استعمال ما هو قائم.**

فُتِّش أوّلًا (§34)، ووُجد اسمانِ مشغولان بمفهومَين آخرين تمامًا:

  • `models.synthesis.ResearchOpportunity` (جدول `research_opportunities`) —
    **فرصةٌ بحثية مشتقّةٌ من فجوةٍ في الأدبيّات**: سؤالٌ يستحقّ أن يُدرس.
    لا علاقةَ له باستقطاب أحد.
  • `models.thesis.PublicationOpportunity` — **فرصةُ نشرٍ مستخرجةٌ من
    رسالة**: ورقةٌ يمكن أن تُكتب. ولا علاقةَ لها بالاستقطاب كذلك.

## الحدُّ الذي يميّز هذا النطاق عن كلّ ما قبله

**التطبيقُ قد يأتي من مستأجرٍ آخر.** وهذا أوّلُ صفٍّ في المنصّة كلِّها
يُكتب بيد فاعلٍ لا ينتمي إلى مستأجر الصفّ — فباحثٌ في جامعةٍ يتقدّم إلى
فرصةٍ أنشأها بحثٌ في جامعةٍ أخرى.

## ولمَ جدولان للفرصة لا جدولٌ واحد

**العطبُ الذي أُغلق بهذا الفصل، وقد كان قائمًا في أوّل كتابةٍ لهذا
النطاق:** كانت الفرصةُ جدولًا واحدًا يحمل النصَّ المُعلَن ومعه
`tenant_id` و`project_id` و`created_by`، وعليه سياسةُ اكتشافٍ عابرةٌ
للمستأجرين. وRLS تحكم **الصفوف لا الأعمدة** — فباحثٌ في مستأجرٍ آخر
يستعلم الجدولَ الأصلَ مباشرةً كان يحصل على معرّف البحث ومعرّف المؤسسة
ومنشئِ الفرصة. وكان العلاجُ المكتوب «العرضُ الآمن هو الطريقُ المُعتمد»،
أي **اتفاقًا في التطبيق لا حدًّا في القاعدة**.

فانفصل النسبُ عن الإعلان:

  • `RecruitmentOpportunity` — **السجلُّ الخاصّ**: هويّةُ الفرصة ونسبُها.
    مستأجرٌ وبحثٌ ومنشئ، **ولا شيءَ غيرَ ذلك**. وسياستُه سياسةُ مديرٍ
    وحدها، **ولا سياسةَ عابرةً للمستأجرين عليه إطلاقًا**. فما لا يُطابقه
    غيرُ المدير لا يقرؤه بحال.
  • `RecruitmentOpportunityListing` — **الإعلانُ العامّ**: ما كُتب ليُقرأ
    في الاكتشاف، وحالتُه ونافذتُه. **ولا يحمل معرّفَ بحثٍ ولا مستأجرٍ ولا
    منشئ** — فالعمودُ غيرُ الموجود لا يُسرَّب.

والنسبُ هو **الأصل** والإعلانُ فرعُه: فيُكتب السجلُّ أوّلًا بتفويضٍ يقوم
على `project_id` وحده (سؤالٌ مكتملٌ بذاته)، ثمّ يُكتب الإعلانُ بتفويضٍ
يقرأ أباه. ولو انعكس الترتيبُ لاحتاج إعلانٌ إلى نسبٍ لم يُكتب بعد.

وحالةُ الإعلان ونافذتُه على الإعلان لا على النسب **قصدًا**: شرطُ
الاكتشاف يصير كلُّه محلّيًّا في جدولٍ واحد، فلا شرطَ عبر جدولين ولا نسخةٌ
ثانيةٌ من النافذة تفترق عن أختها.

## والسجلُّ الخاصُّ يُكتب مرّةً ولا يُعدَّل

ولا سياسةَ تعديلٍ عليه ولا صلاحيةَ تعديل — كما فعل الترحيلُ 0003 بسجلّ
التدقيق. فـ«لا تُنقل فرصةٌ إلى بحثٍ آخر» و«لا يُعاد كتابةُ من أنشأها»
ليستا حارسًا يُفحَص بل **غيابَ الطريق**.

## وما لا يقع هنا

ولا عضويّةَ تُنشأ من قبولِ تطبيق: المتقدّمُ المختار يُدعى بـ
`ProjectInvitation` القائمة، والدعوةُ تُقبل بيد صاحبها. و«مدعوّ» حالٌ
**لا تُكتب بلا دعوةٍ حقيقيةٍ خلفها** — و`invitation_id` هو ما يجعل ذلك
قيدًا في القاعدة لا وعدًا. والعضويّةُ ليست تأليفًا، ولا أدوارَ CRediT
تُكتب من هنا.

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

#: حالاتُ الإعلان — **حتميّةٌ ومغلقة**، والقاعدةُ لا تقبل غيرها.
#:
#: و`deleted` حالةٌ لا حذفٌ: الفرصةُ التي تقدّم إليها باحثون لا تُمحى من
#: تحت تطبيقاتهم، فيبقى الصفُّ ويسقط الإعلانُ من كلّ اكتشاف.
OPPORTUNITY_STATES: Final[tuple[str, ...]] = (
    "draft", "scheduled", "open", "closed", "deleted")

#: حالاتُ التطبيق.
APPLICATION_STATES: Final[tuple[str, ...]] = (
    "pending", "shortlisted", "declined", "invited", "withdrawn")

#: **ما يُعَدّ تطبيقًا قائمًا** — وعليه يقوم منعُ التكرار.
#:
#: والمنسحبُ والمرفوضُ ليسا قائمَين: من انسحب له أن يعود، ومن رُفض له أن
#: يتقدّم لفرصةٍ أخرى. أمّا `invited` فقائم: الدعوةُ أُرسلت ولم تُحسم.
ACTIVE_APPLICATION_STATES: Final[tuple[str, ...]] = (
    "pending", "shortlisted", "invited")

#: **مصفوفةُ الانتقالات التي يملكها المدير** — `قبل → بعد`.
#:
#: وهي مكتوبةٌ صريحةً لأنّ RLS لا تعرف `OLD`: سياسةُ تعديلٍ تقول «صاحبُه
#: يعدّله» تسمح له أن يُرشّح نفسَه. فالمصفوفةُ في مُشغِّلٍ على القاعدة،
#: ومرآتُها هنا.
MANAGER_TRANSITIONS: Final[tuple[tuple[str, str], ...]] = (
    ("pending", "shortlisted"),
    ("pending", "declined"),
    ("shortlisted", "declined"),
    ("shortlisted", "invited"),
)

#: والانسحابُ فعلُ صاحبه وحده، من أيّ حالٍ قائمة.
APPLICANT_TRANSITIONS: Final[tuple[tuple[str, str], ...]] = tuple(
    (state, "withdrawn") for state in ACTIVE_APPLICATION_STATES)

#: الصلاحيةُ التي تُدير الاستقطاب — صفٌّ صريح، لا دورٌ يُفسَّر.
MANAGE_RECRUITMENT: Final = "manage_team"


class RecruitmentOpportunity(Base, TenantScoped, Timestamped):
    """نسبُ الفرصة — **السجلُّ الخاصُّ الذي لا يعبُر المستأجر**.

    مستأجرٌ وبحثٌ ومنشئ. ولا نصَّ معروضٌ فيه ولا حالةَ إعلان: تلك في
    `RecruitmentOpportunityListing`. وهو الأصلُ الذي تتعلّق به التطبيقات.

    **ويُكتب مرّةً ولا يُعدَّل** — لا سياسةَ تعديلٍ عليه ولا صلاحية.
    """

    __tablename__ = "recruitment_opportunities"
    __table_args__ = (
        Index("ix_recruitment_opportunities_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)
    #: **ويُقاس بفاعل الجلسة عند الكتابة** — فلا تُنسب فرصةٌ إلى غير كاتبها.
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False)


class RecruitmentOpportunityListing(Base, Timestamped):
    """الإعلانُ العامّ — وهذا وحده ما يُقرأ من خارج المستأجر.

    **ولا `TenantScoped` هنا، ولا `project_id`، ولا `created_by`.** وذاك
    هو الحدّ: RLS تحكم الصفوفَ لا الأعمدة، فالعمودُ الخاصُّ الذي لا وجودَ
    له في هذا الجدول لا يُسرَّب منه ولو قُرئ الجدولُ الأصلُ مباشرةً.

    و«الحالةُ» هنا حالةُ **الإعلان**: مسوّدةٌ تُكتب، ومجدولةٌ تنتظر
    بدايتَها، ومفتوحةٌ تُكتشف، ومغلقةٌ انتهت، ومحذوفةٌ سقطت. والمكشوفُ
    منها للغريب `open` وحدها — وهي شرطُ رؤيته للصفّ، فلا تُخبره بشيءٍ لم
    يعرفه من كونه رآه.
    """

    __tablename__ = "recruitment_opportunity_listings"
    __table_args__ = (
        # **والأسماءُ قصيرةٌ عمدًا.** اصطلاحُ `ck_%(table_name)s_%(constraint_name)s`
        # يُبادئ ما يُكتب هنا، واسمٌ مكتوبٌ كاملًا يُبادأ مرّتين **فيُقصّ
        # صامتًا** فوق ثلاثةٍ وستين محرفًا — وهو العطبُ الذي شرحه 0032،
        # وقد وقع في أوّل كتابةٍ لهذا الترحيل فعلًا.
        CheckConstraint(
            "status IN ('draft','scheduled','open','closed','deleted')",
            name="status_is_known"),
        # نافذةٌ لها معنًى: نهايةٌ قبل بدايةٍ إعلانٌ لا يُفتح أبدًا.
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR starts_at < ends_at",
            name="window_is_ordered"),
        CheckConstraint("openings_count > 0", name="openings_are_positive"),
        # و«مفتوح» يستوجب بدايةً: بلا `starts_at` لا يُعرف متى يُكتشف.
        CheckConstraint(
            "status <> 'open' OR starts_at IS NOT NULL",
            name="open_needs_a_start"),
        # فهرسُ الاكتشاف: الحالةُ والنافذةُ معًا، وهي شرطُ كلّ قراءةٍ عالمية.
        Index("ix_recruitment_listings_discovery",
              "status", "starts_at", "ends_at"),
    )

    #: مفتاحٌ أوّلٌ **وأجنبيٌّ معًا**: إعلانٌ واحدٌ لكلّ فرصة، ولا إعلانَ بلا نسب.
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("recruitment_opportunities.id", ondelete="RESTRICT"),
        primary_key=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: ما سيقدّمه المتعاون — مهامٌّ لا وعودُ نتائج.
    contributions: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ما يُطلب منه — مهاراتٌ ومعرفة.
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(120), nullable=True)
    openings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    collaboration_type: Mapped[str] = mapped_column(String(40), nullable=False)

    #: وسمٌ عامٌّ **يُكتب صراحةً** ولا يُشتقّ من البحث.
    #:
    #: فعنوانُ البحث الحقيقيّ قد يُفصح عن فكرةٍ لم تُنشر بعد. فمن أراد أن
    #: يُظهر انتماءً كتبه بيده، ومن سكت لم يُظهر شيئًا.
    public_label: Mapped[str | None] = mapped_column(String(160), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    starts_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    ends_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    #: حذفٌ ناعم — والصفُّ يبقى تحت تطبيقات من تقدّموا.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class RecruitmentApplication(Base, Timestamped):
    """تقدُّمُ باحثٍ إلى فرصة — **وقد يكون من مستأجرٍ آخر**.

    ولا `TenantScoped` هنا، وذاك مقصودٌ ومشروح في رأس الوحدة: الصفُّ يعيش
    بين مستأجرَين، فحدُّه الفاعلُ لا المستأجر. ولو وُسم بمستأجر الفرصة لم
    يرَ المتقدّمُ تقدُّمَه، ولو وُسم بمستأجر المتقدّم لم يرَه صاحبُ الفرصة.

    و`applicant_tenant_id` عمودٌ **للأثر والتدقيق لا للتفويض**.
    """

    __tablename__ = "recruitment_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','shortlisted','declined','invited','withdrawn')",
            name="status_is_known"),
        # والمنسحبُ له وقتُ انسحاب — فحالةٌ بلا وقتها تجعل «متى انسحب؟»
        # سؤالًا لا جواب له.
        CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="withdrawal_has_a_time"),
        # **و«مدعوّ» لا تُكتب بلا دعوةٍ حقيقية.** فحالةٌ اسمُها دعوةٌ بلا
        # دعوةٍ خلفها تجعل الاستقطابَ طريقًا ثانيًا إلى الفريق يتجاوز
        # `ProjectInvitation` — وهي الطريقُ الوحيدةُ المُقرَّرة.
        CheckConstraint(
            "status <> 'invited' OR invitation_id IS NOT NULL",
            name="invited_needs_an_invitation"),
        # **ولا تطبيقانِ قائمان لحسابٍ واحد على فرصةٍ واحدة.**
        #
        # وفهرسٌ **جزئيّ** لا قيدٌ كامل: من انسحب له أن يعود، ومن رُفض لا
        # يُحجَب عن غيرها. فالمنعُ على القائم وحده، والقاعدةُ تحمله — لا
        # فحصٌ في الواجهة يُتجاوَز بطلبين متزامنين.
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
    #: نصُّ صاحبه — **ولا يُعدَّل بعد الإرسال في هذه المرحلة**، لا بيده ولا
    #: بيد مديرٍ يقرؤه. فتعديلُ المدير تحريفُ إقرارِ غيره، وتعديلُ صاحبه
    #: بعد قراءةِ المدير يُغيّر ما بُني عليه قرار.
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    withdrawn_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    #: ومن حسم يُنسب إليه ما حسم — ويُقاس بفاعل الجلسة في المُشغِّل.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True)
    #: الدعوةُ الحقيقيةُ خلف حال «مدعوّ» — والقيدُ أعلاه يجعلها شرطًا.
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("project_invitations.id", ondelete="RESTRICT"),
        nullable=True)


__all__ = [
    "ACTIVE_APPLICATION_STATES",
    "APPLICANT_TRANSITIONS",
    "APPLICATION_STATES",
    "MANAGER_TRANSITIONS",
    "MANAGE_RECRUITMENT",
    "OPPORTUNITY_STATES",
    "RecruitmentApplication",
    "RecruitmentOpportunity",
    "RecruitmentOpportunityListing",
]
