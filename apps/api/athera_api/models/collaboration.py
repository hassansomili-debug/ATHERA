"""تعاون فريق البحث | Research collaboration (PUBRIVA، §12، §24، §28).

ثلاثة جداول، وكلٌّ منها يحمل تمييزًا يسهل طيُّه في الواجهة:

  `project_invitations`         دعوةٌ لها **رمزٌ مجزَّأ ومهلة وحالٌ وقابل**.
  `project_member_permissions`  الصلاحيةُ صفٌّ مستقلٌّ عن الدور.
  `project_member_events`       دورةُ الحياة تُضاف ولا تُعدَّل.

و**الرمزُ الخام لا يُخزَّن ولا يُسجَّل**: يُسلَّم مرّةً واحدة لصاحبه،
ويبقى في القاعدة تجزئتُه وحدها.
"""

import datetime as dt
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


class ProjectInvitation(Base, TenantScoped, Timestamped):
    """دعوةٌ إلى بحث — **تربط حسابًا، لا اسمًا معروضًا**.

    عضوٌ باسمٍ وحده لا يتعاون: لا يدخل، ولا يوافق على تأليف، ولا يُنسب
    إليه فعل. فالقبول يقع من حسابٍ مصادَق، ويُكتب معرِّفه في
    `accepted_user_id` وفي `ProjectMember.user_id` معًا.

    والمطابقةُ بالاسم المعروض ممنوعة قصدًا: «د. محمد العلي» في مستأجرٍ
    جامعيّ قد يكون ثلاثةَ أشخاص، وربطُ أحدهم بالبحث لتشابه الاسم يمنح
    غريبًا حقَّ قراءة بياناتٍ لم يُدعَ إليها.
    """

    __tablename__ = "project_invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_project_invitations_token"),
        UniqueConstraint("id", "project_id", name="uq_project_invitations_scoped"),
        ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="SET NULL", name="fk_project_invitations_member"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    invited_email: Mapped[str] = mapped_column(String(320), nullable=False)
    invited_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ترشيحٌ لا ربط: البريد معروفٌ في المنصّة، والربط لا يقع إلّا بالقبول.
    invited_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    # اقتراحُ دورٍ واقتراحُ صلاحيات — **اقتراحٌ يُراجَع عند القبول**، لا أمر.
    proposed_role: Mapped[str] = mapped_column(String(32), nullable=False)
    proposed_permissions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # تجزئةُ الرمز وحدها. لا عمود للرمز الخام في هذا النموذج، ولا في غيره.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="invited")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    accepted_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)


class ProjectMemberPermission(Base, TenantScoped, Timestamped):
    """صلاحيةُ عضوٍ في بحث — **صفٌّ يُمنح ويُسحب، لا صفةٌ للدور**.

    ولو اشتُقّت من `role` لتغيّرت الصلاحياتُ بأثرٍ جانبيٍّ لتغيير الدور،
    ولاستحال ما يقع كلَّ يوم: محلّلٌ إحصائيّ له حقُّ البيانات ولا إدارةَ
    له على المشروع، ومشرفٌ يراجع المنهجية ولا يحرّر البيانات.
    """

    __tablename__ = "project_member_permissions"
    __table_args__ = (
        UniqueConstraint("member_id", "permission_key",
                         name="uq_project_member_permissions_grant"),
        ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="CASCADE", name="fk_project_member_permissions_member"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    permission_key: Mapped[str] = mapped_column(String(32), nullable=False)
    granted_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    granted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.UTC))


class ProjectMemberEvent(Base, TenantScoped, Timestamped):
    """دورةُ حياة العضو — **تُضاف ولا تُعدَّل**.

    ومَن غيّر دورَ عضوٍ أو صلاحياته أو أدوارَ CRediT المعلَنة عنه يُنسب إليه
    ما فعل. فتغييرٌ يُكتب فوق سابقه يجعل الشاشة تقول ما هو الحال الآن،
    ولا تقول كيف صار — وهو بالضبط ما يُحتاج إليه في نزاع تأليف.
    """

    __tablename__ = "project_member_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="CASCADE", name="fk_project_member_events_member"),
        ForeignKeyConstraint(
            ["invitation_id", "project_id"],
            ["project_invitations.id", "project_invitations.project_id"],
            ondelete="CASCADE", name="fk_project_member_events_invitation"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True)
    event_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    state_before: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_after: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    note_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: dt.datetime.now(dt.UTC))


__all__ = [
    "ProjectInvitation",
    "ProjectMemberEvent",
    "ProjectMemberPermission",
]
