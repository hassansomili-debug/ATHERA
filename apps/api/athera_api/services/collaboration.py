"""تعاون فريق البحث | Research collaboration (PUBRIVA، §12، §24، §28).

**هذه الطبقة تحرس فرقًا أربعة يسهل طيُّها، وطيُّها يُنتج تزوير تأليف:**

    الدورُ في المشروع     ليس صلاحية
    الصلاحيةُ              ليست مساهمةَ CRediT
    مساهمةُ CRediT         ليست تأليفًا
    عضويةُ الفريق          ليست موافقةً على التأليف

ولا دالّة هنا تُنشئ واحدًا من الأربعة من الآخر. ولا دالّة هنا تستنتج دورَ
CRediT من نشاطٍ في المنصّة: «حرّرتَ المنهجية، إذن أنت صاحب المنهجية» جملةٌ
تبدو ذكيّة وتُنتج نزاعَ تأليفٍ في كل فريق تُطبَّق عليه.

## والموافقةُ تُربط بالهويّة في ثلاث طبقات

  ١) الموجّه يرفض ما ليس من صاحبه.
  ٢) هذه الطبقة تكتب `consent_method` و`consent_recorded_by` معًا.
  ٣) والقاعدة ترفض «ذاتيّةً» سجّلها غيرُ صاحبها — قيدًا لا سطرَ كود.

والثالثةُ وحدها هي التي تصمد أمام موجّهٍ يُكتب غدًا.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, Forbidden, NotFound
from ..models.audit import AuditEvent
from ..models.collaboration import (
    ProjectInvitation,
    ProjectMemberEvent,
    ProjectMemberPermission,
)
from ..models.identity import Membership, User
from ..models.portfolio import ProjectMember, ResearchProject
from ..models.research import ResearcherProfile
from . import audit, team

# أفعالُ إنشاء البحث في سجلّ التدقيق — منها يُشتقّ مالكُ بحثٍ لا ملفَّ له.
# ومصدرُها سجلٌّ لا يُعدَّل ولا يُحذف منه، فالنسبة إليه نسبةٌ إلى واقعة.
PROJECT_CREATED_ACTIONS = (
    "portfolio.project_created",
    "workspace.project_created",
    "thesis.project_created",
    "synthesis.project_created",
)

PROJECT_OBJECT_TYPE = "research_project"
MEMBER_OBJECT_TYPE = "project_member"
INVITATION_OBJECT_TYPE = "project_invitation"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ═══════════════════════ الرمز: يُسلَّم مرّةً ولا يُخزَّن ═══════════════════════

def new_invitation_token() -> tuple[str, str]:
    """يعيد (الخام، التجزئة). **والخام لا يُكتب في قاعدةٍ ولا في سجلّ.**

    فرمزُ دعوةٍ مخزَّنٌ خامًا يعني أن من قرأ نسخةً احتياطية يستطيع أن يقبل
    دعوةً باسم غيره، فيربط حسابَه ببحثٍ لم يُدعَ إليه. والتجزئة تجعل
    الجدول عديمَ القيمة لمن سرقه، وتبقى المقارنة ممكنة.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_invitation_token(raw)


def hash_invitation_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ═══════════════════════ الوصول: العضويةُ ثمّ الصلاحية ═══════════════════════

@dataclass(frozen=True, slots=True)
class Access:
    """ما يملكه فاعلٌ في بحثٍ بعينه — عضويّتُه وصلاحياتُه المصرَّح بها."""

    member: ProjectMember
    permissions: frozenset[str]

    def allows(self, permission: str) -> bool:
        return permission in self.permissions


async def _project(session: AsyncSession, project_id: uuid.UUID) -> ResearchProject:
    row = (
        await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )
    ).scalar_one_or_none()
    if row is None:
        # RLS تحجب بحثَ مستأجرٍ آخر، فيُقرأ الحجب «غير موجود» — وهو الصواب:
        # «ممنوع» تخبر الغريب أن البحث موجود، و«غير موجود» لا تخبره بشيء.
        raise NotFound("team.project_not_found")
    return row


async def owner_user_id(
    session: AsyncSession, *, project_id: uuid.UUID
) -> uuid.UUID | None:
    """مالكُ البحث — من مصدرين موثوقين، **ولا واحد منهما اسمٌ معروض**.

    ١) ملفُّ الباحث الذي يشير إليه البحث.
    ٢) فاعلُ حدث إنشائه في سجلّ التدقيق، وهو سجلٌّ يُضاف إليه ولا يُعدَّل.

    ومسارُ `workspace` يُنشئ بحثًا بلا `profile_id`، فالثاني ليس احتياطًا
    نظريًّا: هو المصدر الوحيد لأكثر البحوث التي يبدؤها الباحث اليوم.
    """
    # `None` هنا حالان لا واحدة: بحثٌ لا وجود له، وبحثٌ بلا ملفِّ باحث.
    # وكلتاهما تعني «لا مالك من هذا الطريق»، فيُجرَّب الطريق الثاني.
    profile_id = (
        await session.execute(
            select(ResearchProject.profile_id).where(ResearchProject.id == project_id)
        )
    ).scalar_one_or_none()
    if profile_id is not None:
        user_id = (
            await session.execute(
                select(ResearcherProfile.user_id)
                .where(ResearcherProfile.id == profile_id)
            )
        ).scalar_one_or_none()
        if user_id is not None:
            return user_id

    return (
        await session.execute(
            select(AuditEvent.actor_user_id)
            .where(
                AuditEvent.object_type == PROJECT_OBJECT_TYPE,
                AuditEvent.object_id == project_id,
                AuditEvent.action.in_(PROJECT_CREATED_ACTIONS),
                AuditEvent.actor_user_id.is_not(None),
            )
            .order_by(AuditEvent.occurred_at)
            .limit(1)
        )
    ).scalar_one_or_none()


async def member_for(
    session: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    """عضويّةُ حسابٍ في بحثٍ بعينه.

    والبحثُ بالمعرِّف **وبالحساب معًا**: RLS تعزل بين المستأجرين ولا تعزل
    بين بحثين في المستأجر الواحد، وهو عطبٌ وقع في هذا المنتج من قبل.
    """
    return (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    ).scalar_one_or_none()


async def permissions_of(
    session: AsyncSession, *, member_id: uuid.UUID
) -> frozenset[str]:
    rows = (
        await session.execute(
            select(ProjectMemberPermission.permission_key)
            .where(ProjectMemberPermission.member_id == member_id)
        )
    ).scalars().all()
    return frozenset(rows)


async def ensure_owner_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> ProjectMember | None:
    """يُنشئ عضويةَ المالك إن كان الطالبُ هو المالك ولا عضوية له.

    **جسرٌ لا بابٌ خلفيّ.** فالبحوث تُنشأ في موجّهاتٍ لا تملكها هذه الطبقة
    (`workspace`، `portfolio`، `thesis`)، ولا تُنشئ عضويةً لصاحبها. وبلا
    هذا الجسر يفقد كلُّ باحثٍ بحثَه في أوّل طلبٍ بعد الترحيل.

    والشرطُ ضيّق قصدًا: الطالبُ **هو** المالك المشتقّ من مصدرٍ موثوق، لا
    «عضوٌ ما»، ولا «من يعرف المعرِّف». وما يُمنح هو ما كان الترحيل ليمنحه
    لو عرف البحث — لا زيادةَ صلاحيةٍ ولا استثناء. والحدث يُكتب في السجلّ
    باسمه، فلا تنشأ عضويةٌ لا يعرف أحدٌ من أين جاءت.
    """
    if await owner_user_id(session, project_id=project_id) != actor_user_id:
        return None
    existing = await member_for(session, project_id=project_id, user_id=actor_user_id)
    if existing is not None:
        return existing

    user = (
        await session.execute(select(User).where(User.id == actor_user_id))
    ).scalar_one_or_none()
    if user is None:
        return None

    member = ProjectMember(
        tenant_id=tenant_id, project_id=project_id, user_id=actor_user_id,
        display_name=(user.full_name_ar or "").strip() or user.email,
        invited_email=team.normalize_email(user.email),
        role="principal_investigator", access_state="active",
        consent_state="not_requested", is_author=False,
    )
    session.add(member)
    await session.flush()

    await _grant_permissions(
        session, tenant_id=tenant_id, member=member,
        keys=team.default_permissions("principal_investigator"),
        granted_by=actor_user_id,
    )
    await record_member_event(
        session, tenant_id=tenant_id, project_id=project_id, member_id=member.id,
        event_kind="accepted", actor_user_id=actor_user_id,
        subject_user_id=actor_user_id,
        state_after={"role": "principal_investigator", "bootstrap": "project_owner"},
        note_ar="عضوية المالك أُنشئت من نسبة إنشاء البحث، لا من اسم معروض.",
    )
    await audit.record(
        session, tenant_id=tenant_id, action="team.owner_membership_bootstrapped",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id,
        state_after={"project_id": str(project_id), "role": "principal_investigator"},
        reason="the project owner is derived from the immutable creation audit event, "
               "never from a display name",
    )
    return member


async def access_for(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Access:
    """يقرأ ما يملكه الطالبُ في هذا البحث — ويرفض إن لم يملك عضويةً حيّة."""
    await _project(session, project_id)
    member = await member_for(session, project_id=project_id, user_id=user_id)
    if member is None:
        member = await ensure_owner_membership(
            session, tenant_id=tenant_id, project_id=project_id,
            actor_user_id=user_id)
    if member is None:
        raise Forbidden("team.not_a_project_member", project_id=str(project_id))
    if member.access_state == "suspended":
        raise Forbidden("team.access_suspended", project_id=str(project_id))
    if member.access_state == "removed":
        raise Forbidden("team.access_removed", project_id=str(project_id))
    if member.access_state == "invited":
        raise Forbidden("team.invitation_not_accepted", project_id=str(project_id))
    return Access(member=member, permissions=await permissions_of(
        session, member_id=member.id))


async def require_permission(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    permission: str,
) -> Access:
    """**العضويةُ وحدها لا تمنح شيئًا.** والصلاحيةُ صفٌّ يُقرأ، لا دورٌ يُفسَّر."""
    access = await access_for(
        session, tenant_id=tenant_id, project_id=project_id, user_id=user_id)
    if not access.allows(permission):
        raise Forbidden("team.permission_required", permission=permission,
                        project_id=str(project_id))
    return access


# ═══════════════════════ سجلّ دورة الحياة ═══════════════════════

async def record_member_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    event_kind: str,
    actor_user_id: uuid.UUID,
    member_id: uuid.UUID | None = None,
    invitation_id: uuid.UUID | None = None,
    subject_user_id: uuid.UUID | None = None,
    state_before: dict | None = None,
    state_after: dict | None = None,
    note_ar: str | None = None,
) -> ProjectMemberEvent:
    if event_kind not in team.MEMBER_EVENT_KINDS:
        raise AtheraError("team.unknown_event_kind", status_code=422, kind=event_kind)
    row = ProjectMemberEvent(
        tenant_id=tenant_id, project_id=project_id, member_id=member_id,
        invitation_id=invitation_id, event_kind=event_kind,
        actor_user_id=actor_user_id, subject_user_id=subject_user_id,
        state_before=state_before, state_after=state_after, note_ar=note_ar,
        occurred_at=_now(),
    )
    session.add(row)
    await session.flush()
    return row


async def _grant_permissions(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    member: ProjectMember,
    keys: tuple[str, ...] | list[str],
    granted_by: uuid.UUID,
) -> None:
    for key in dict.fromkeys(keys):
        session.add(ProjectMemberPermission(
            tenant_id=tenant_id, project_id=member.project_id, member_id=member.id,
            permission_key=key, granted_by=granted_by, granted_at=_now()))
    await session.flush()


# ═══════════════════════ الدعوات ═══════════════════════

@dataclass(frozen=True, slots=True)
class IssuedInvitation:
    invitation: ProjectInvitation
    # يُعاد مرّةً واحدة إلى الداعي ليُسلَّم إلى المدعوّ. ولا يُخزَّن ولا يُسجَّل.
    token: str


async def invite_member(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    inviter_user_id: uuid.UUID,
    email: str,
    display_name: str,
    role: str,
    permissions: list[str] | None = None,
    ttl_hours: int | None = None,
) -> IssuedInvitation:
    """دعوةٌ إلى بحث — بمهلةٍ، ورمزٍ مجزَّأ، واقتراحِ دورٍ وصلاحيات.

    والاقتراحُ اقتراح: لا يصير صلاحيةً إلّا بعد قبولٍ من حسابٍ مصادَق.
    """
    if role not in team.MEMBER_ROLES:
        raise AtheraError("team.unknown_member_role", status_code=422, role=role)
    proposed = list(permissions) if permissions is not None else list(
        team.default_permissions(role))
    try:
        team.validate_author_name(display_name)
        team.validate_permissions(proposed)
    except team.TeamError as exc:
        raise AtheraError("team.invalid_invitation", status_code=422,
                          detail=str(exc)) from exc

    normalized = team.normalize_email(email)
    if "@" not in normalized or len(normalized) < 3:
        raise AtheraError("team.invalid_invitation", status_code=422, detail="email")

    # دعوةٌ حيّةٌ ثانيةٌ لنفس البريد تعني رمزين يعملان — والقاعدة ترفضها
    # بفهرسٍ جزئيّ. ويُقال هنا بلغةٍ مفهومة قبل أن يصطدم بها المستعمل.
    live = (
        await session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.project_id == project_id,
                func.lower(ProjectInvitation.invited_email) == normalized,
                ProjectInvitation.state == "invited",
            )
        )
    ).scalar_one_or_none()
    if live is not None:
        # **ودعوةٌ انتهت مهلتُها ليست دعوةً حيّة.** وإبقاؤها `invited` يجعل
        # الفهرسَ الجزئيّ يمنع دعوةً جديدةً لنفس الشخص إلى الأبد — فيصير
        # نسيانُ الردّ حظرًا دائمًا لا يفهم أحدٌ سببه.
        if live.expires_at <= _now():
            await _settle(session, tenant_id=tenant_id, invitation=live,
                          state="expired", actor_user_id=inviter_user_id)
        else:
            raise AtheraError("team.invitation_already_live", status_code=409)

    # **الترشيحُ داخل المستأجر وحده.** وحسابٌ في مستأجرٍ آخر يحمل البريد
    # نفسه لا يُرشَّح: RLS تمنعه من بلوغ الدعوة أصلًا، فترشيحُه يُنتج دعوةً
    # لا يستطيع أحدٌ قبولها — ويكتب في القاعدة إشارةً إلى حسابٍ خارج المستأجر.
    candidate = (
        await session.execute(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(func.lower(User.email) == normalized,
                   Membership.tenant_id == tenant_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if candidate is not None:
        existing = await member_for(
            session, project_id=project_id, user_id=candidate.id)
        if existing is not None and existing.access_state in ("active", "suspended"):
            raise AtheraError("team.already_a_member", status_code=409)

    raw, token_hash = new_invitation_token()
    invitation = ProjectInvitation(
        tenant_id=tenant_id, project_id=project_id, invited_email=normalized,
        invited_display_name=display_name.strip(),
        # ترشيحٌ لا ربط — الربط لا يقع إلّا بقبولٍ من الحساب نفسه.
        invited_user_id=candidate.id if candidate is not None else None,
        invited_by=inviter_user_id, proposed_role=role, proposed_permissions=proposed,
        token_hash=token_hash, state="invited",
        expires_at=_now() + dt.timedelta(
            hours=ttl_hours or team.INVITATION_TTL_HOURS),
    )
    session.add(invitation)
    await session.flush()

    await record_member_event(
        session, tenant_id=tenant_id, project_id=project_id,
        invitation_id=invitation.id, event_kind="invited",
        actor_user_id=inviter_user_id,
        subject_user_id=candidate.id if candidate is not None else None,
        state_after={"role": role, "permissions": proposed,
                     "expires_at": invitation.expires_at.isoformat()},
    )
    await audit.record(
        session, tenant_id=tenant_id, action="team.member_invited",
        object_type=INVITATION_OBJECT_TYPE, object_id=invitation.id,
        actor_user_id=inviter_user_id,
        # **لا بريدَ كاملًا ولا رمزَ في السجلّ.** السجلّ يُقرأ في التدقيق،
        # ولا يحتاج قارئُه إلى ما يكفي لانتحال الدعوة.
        state_after={"project_id": str(project_id), "proposed_role": role,
                     "proposed_permissions": proposed},
        reason="an invitation proposes a role; it grants nothing until the invited "
               "account accepts it in person",
    )
    return IssuedInvitation(invitation=invitation, token=raw)


async def _settle(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    invitation: ProjectInvitation,
    state: str,
    actor_user_id: uuid.UUID,
) -> ProjectInvitation:
    invitation.state = state
    invitation.responded_at = _now()
    await session.flush()
    await record_member_event(
        session, tenant_id=tenant_id, project_id=invitation.project_id,
        invitation_id=invitation.id, event_kind=state,
        actor_user_id=actor_user_id, state_after={"state": state})
    return invitation


async def _invitation_by_token(
    session: AsyncSession, *, token: str
) -> ProjectInvitation:
    row = (
        await session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.token_hash == hash_invitation_token(token))
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("team.invitation_not_found")
    return row


async def accept_invitation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    token: str,
    accepting_user_id: uuid.UUID,
) -> ProjectMember:
    """يربط العضويةَ بـ**الحساب المصادَق الذي قبِل** — لا باسمٍ ولا ببريد.

    فمطابقةُ الاسم المعروض تمنح غريبًا حقَّ قراءة بحثٍ لم يُدعَ إليه لمجرّد
    تشابه اسم؛ ومطابقةُ البريد وحدها تمنحه إياه لمن يعرف بريدَ غيره. فالذي
    يُكتب في `user_id` هو `sub` من الرمز الموقّع، ولا شيء سواه.
    """
    invitation = await _invitation_by_token(session, token=token)

    if invitation.state != "invited":
        raise AtheraError("team.invitation_not_open", status_code=409,
                          state=invitation.state)
    # **المهلةُ تُقرأ من `expires_at` ولا يُعوَّل على وسمها.** ووسمُها هنا
    # كتابةٌ تُلغى مع المعاملة التي يُنهيها هذا الرفض نفسه — فتبدو الشيفرة
    # كأنها تُغلق الدعوة وهي لا تفعل. والوسمُ يقع في `invite_member` حيث
    # تنجح المعاملة، وهو الموضع الذي يلزم فيه فعلًا.
    if invitation.expires_at <= _now():
        raise AtheraError("team.invitation_expired", status_code=409)

    accepting = (
        await session.execute(select(User).where(User.id == accepting_user_id))
    ).scalar_one_or_none()
    if accepting is None:
        raise Forbidden("team.invitation_not_yours")
    # **الدعوةُ لبريدٍ بعينه.** ورمزٌ صحيح في يد حسابٍ آخر لا يُقبل: وإلّا
    # صار تسريبُ الرابط في محادثةٍ عامّة بابًا إلى بيانات البحث.
    if team.normalize_email(accepting.email) != team.normalize_email(
            invitation.invited_email):
        raise Forbidden("team.invitation_not_yours")

    existing = await member_for(
        session, project_id=invitation.project_id, user_id=accepting_user_id)
    if existing is not None and existing.access_state in ("active", "suspended"):
        raise AtheraError("team.already_a_member", status_code=409)

    if existing is not None:
        member = existing
        member.access_state = "active"
        member.removed_at = None
        member.role = invitation.proposed_role
    else:
        member = ProjectMember(
            tenant_id=tenant_id, project_id=invitation.project_id,
            user_id=accepting_user_id,
            display_name=invitation.invited_display_name,
            invited_email=invitation.invited_email,
            role=invitation.proposed_role, access_state="active",
            # **القبولُ ليس موافقةً على التأليف، ولا إعلانَ تأليف.**
            consent_state="not_requested", is_author=False,
        )
        session.add(member)
    await session.flush()

    current = await permissions_of(session, member_id=member.id)
    await _grant_permissions(
        session, tenant_id=tenant_id, member=member,
        keys=[key for key in (invitation.proposed_permissions or [])
              if key not in current],
        granted_by=invitation.invited_by,
    )

    invitation.state = "accepted"
    invitation.responded_at = _now()
    invitation.accepted_user_id = accepting_user_id
    invitation.member_id = member.id
    await session.flush()

    await record_member_event(
        session, tenant_id=tenant_id, project_id=invitation.project_id,
        member_id=member.id, invitation_id=invitation.id, event_kind="accepted",
        actor_user_id=accepting_user_id, subject_user_id=accepting_user_id,
        state_after={"role": member.role,
                     "permissions": sorted(invitation.proposed_permissions or [])},
        note_ar="العضوية رُبطت بالحساب المصادَق الذي قبِل الدعوة.",
    )
    await audit.record(
        session, tenant_id=tenant_id, action="team.invitation_accepted",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=accepting_user_id,
        state_after={"project_id": str(invitation.project_id), "role": member.role},
        reason="membership binds to the authenticated accepting account, never to a "
               "display name",
    )
    return member


async def decline_invitation(
    session: AsyncSession, *, tenant_id: uuid.UUID, token: str,
    declining_user_id: uuid.UUID,
) -> ProjectInvitation:
    invitation = await _invitation_by_token(session, token=token)
    if invitation.state != "invited":
        raise AtheraError("team.invitation_not_open", status_code=409,
                          state=invitation.state)
    declining = (
        await session.execute(select(User).where(User.id == declining_user_id))
    ).scalar_one_or_none()
    if declining is None or team.normalize_email(declining.email) != \
            team.normalize_email(invitation.invited_email):
        raise Forbidden("team.invitation_not_yours")
    return await _settle(session, tenant_id=tenant_id, invitation=invitation,
                         state="declined", actor_user_id=declining_user_id)


async def revoke_invitation(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    invitation_id: uuid.UUID, actor_user_id: uuid.UUID,
) -> ProjectInvitation:
    invitation = (
        await session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.id == invitation_id,
                ProjectInvitation.project_id == project_id)
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise NotFound("team.invitation_not_found")
    if invitation.state != "invited":
        raise AtheraError("team.invitation_not_open", status_code=409,
                          state=invitation.state)
    await audit.record(
        session, tenant_id=tenant_id, action="team.invitation_revoked",
        object_type=INVITATION_OBJECT_TYPE, object_id=invitation.id,
        actor_user_id=actor_user_id, state_before={"state": "invited"},
        state_after={"state": "revoked"},
        reason="a revoked invitation can no longer be accepted; its token is dead")
    return await _settle(session, tenant_id=tenant_id, invitation=invitation,
                         state="revoked", actor_user_id=actor_user_id)


# ═══════════════════════ موافقةُ التأليف ═══════════════════════

async def request_consent(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID,
) -> ProjectMember:
    """يطلب الموافقة — **ولا يمنحها**. ولا يصحّ الطلبُ لمن ليس مؤلفًا معلَنًا."""
    if not member.is_author:
        raise AtheraError("team.consent_needs_authorship", status_code=422)
    if member.user_id is None:
        raise AtheraError("team.consent_needs_an_account", status_code=422)
    if member.consent_state in ("granted", "declined"):
        raise AtheraError("team.consent_already_recorded", status_code=422)
    member.consent_state = "pending"
    await session.flush()
    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind="consent_requested",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_after={"consent_state": "pending"})
    return member


async def record_self_consent(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    member: ProjectMember,
    actor_user_id: uuid.UUID,
    granted: bool,
) -> ProjectMember:
    """§24 — **الموافقةُ فعلُ صاحبها، ولا تُسجَّل عنه.**

    والفحصُ هنا ليس تكرارًا لفحص الموجّه: خدمةٌ تُستدعى من مسارٍ ثانٍ غدًا
    ستمرّ من هنا ولن تمرّ من ذاك. وتحتهما قيدٌ في القاعدة يرفض «ذاتيّةً»
    سجّلها غيرُ صاحبها، فالطبقات ثلاث لا واحدة.
    """
    if member.user_id is None:
        raise AtheraError("team.consent_needs_an_account", status_code=422)
    if member.user_id != actor_user_id:
        # ليست 404: العضو موجود، والطالبُ ممنوعٌ بعينه. وإخفاءُ ذلك يجعل
        # رئيسَ الفريق يظن أن العضو غير موجود فيضيف آخر باسمه.
        raise Forbidden("team.consent_is_personal", member_id=str(member.id))
    if not member.is_author:
        raise AtheraError("team.consent_needs_authorship", status_code=422)
    if member.consent_state in ("granted", "declined"):
        raise AtheraError("team.consent_already_recorded", status_code=422)

    before = member.consent_state
    member.consent_state = "granted" if granted else "declined"
    member.consent_recorded_at = _now()
    member.consent_recorded_by = actor_user_id
    member.consent_method = "self"
    await session.flush()

    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id,
        event_kind="consent_granted" if granted else "consent_declined",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before={"consent_state": before},
        state_after={"consent_state": member.consent_state, "method": "self"})
    await audit.record(
        session, tenant_id=tenant_id,
        action="team.consent_recorded" if granted else "team.consent_declined",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id,
        state_before={"consent_state": before},
        state_after={"consent_state": member.consent_state, "method": "self"},
        reason="§24 — consent is the author's own act; the authenticated caller is "
               "the member")
    return member


async def record_administrative_consent(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    member: ProjectMember,
    actor_user_id: uuid.UUID,
    evidence_ar: str,
) -> ProjectMember:
    """مسارٌ إداريٌّ **منفصلٌ ومعلَنٌ ومُدقَّق** — لا اختصارٌ للأوّل.

    ويوجد لأن الواقع يحتوي على موافقةٍ وقّعها المؤلف على ورق وأُودعت لدى
    الجهة. وثلاثةٌ تفرّقه عمّا كان يقع قبل الترحيل 0028:

      • يلزمه سندٌ مكتوب — والقاعدة ترفضه بلا سند.
      • يُوسم `administrative` في السجلّ، فلا يُقرأ كموافقةٍ شخصية أبدًا.
      • يظهر في الشاشة موسومًا، فيراه المؤلف نفسه ويستطيع الاعتراض.

    وما لا يوجد: زرٌّ يوافق عن الجميع، ولا مسارٌ صامتٌ يبدو ذاتيًّا.
    """
    if member.consent_state in ("granted", "declined"):
        raise AtheraError("team.consent_already_recorded", status_code=422)
    if not member.is_author:
        raise AtheraError("team.consent_needs_authorship", status_code=422)
    evidence = (evidence_ar or "").strip()
    if len(evidence) < 12:
        raise AtheraError("team.proxy_consent_needs_evidence", status_code=422)

    before = member.consent_state
    member.consent_state = "granted"
    member.consent_recorded_at = _now()
    member.consent_recorded_by = actor_user_id
    member.consent_method = "administrative"
    member.consent_evidence_ar = evidence
    await session.flush()

    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind="consent_granted",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before={"consent_state": before},
        state_after={"consent_state": "granted", "method": "administrative"},
        note_ar=evidence)
    await audit.record(
        session, tenant_id=tenant_id, action="team.proxy_consent_recorded",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id,
        state_before={"consent_state": before},
        state_after={"consent_state": "granted", "method": "administrative"},
        reason="administrative consent is a separate, evidenced and audited path; it "
               "is never presented as the author's own act")
    return member


# ═══════════════════════ دورةُ حياة العضو ═══════════════════════

async def declare_authorship(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID, is_author: bool, position: int | None = None,
) -> ProjectMember:
    """**العضويةُ لا تُنتج تأليفًا.** والتأليفُ إعلانٌ صريحٌ يُنسب إلى معلنه.

    وسحبُ الإعلان يمحو الترتيب ولا يمحو موافقةً سُجِّلت: مَن وافق وافق،
    وحذفُ أثرِ موافقته لأن أحدًا غيَّر رأيه في القائمة يمحو واقعة.
    """
    before = {"is_author": member.is_author, "author_position": member.author_position}
    member.is_author = is_author
    member.author_position = position if is_author else None
    await session.flush()
    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id,
        event_kind="authorship_declared" if is_author else "authorship_withdrawn",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before=before,
        state_after={"is_author": is_author, "author_position": member.author_position})
    await audit.record(
        session, tenant_id=tenant_id, action="team.authorship_declared",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id, state_before=before,
        state_after={"is_author": is_author, "author_position": member.author_position},
        reason="authorship is declared by a person and consented to by its subject; "
               "it is never inferred from membership or activity")
    return member


async def set_credit_roles(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID, roles: list[str],
) -> ProjectMember:
    """§24 — أدوارُ CRediT **إقرارٌ يُعلَن**، ولا تُستنتج من نشاطٍ في المنصّة.

    و«حرّرتَ المنهجية، إذن أنت صاحب المنهجية» جملةٌ تبدو خدمةً وهي إسنادُ
    مسؤوليةٍ علمية بلا إقرار. فما يُقبل هنا قائمةٌ يكتبها إنسان، والتغيير
    يُحفظ في السجلّ بما كان وما صار.
    """
    try:
        team.validate_credit_roles(roles)
    except team.TeamError as exc:
        raise AtheraError("team.invalid_member", status_code=422,
                          detail=str(exc)) from exc
    before = list(member.credit_roles or [])
    member.credit_roles = list(dict.fromkeys(roles)) or None
    await session.flush()
    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind="credit_changed",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before={"credit_roles": before},
        state_after={"credit_roles": list(member.credit_roles or [])},
        note_ar="أدوار CRediT إقرار معلن، لا استنتاج من نشاط.")
    await audit.record(
        session, tenant_id=tenant_id, action="team.credit_roles_declared",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id, state_before={"credit_roles": before},
        state_after={"credit_roles": list(member.credit_roles or [])},
        reason="§24 — CRediT roles are declarations recorded by a person; PUBRIVA "
               "never infers them from platform activity")
    return member


async def change_role(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID, role: str,
) -> ProjectMember:
    """يغيّر الدور — **ولا يمسّ الصلاحيات**.

    فلو غيّرها معه لصار «رقّيتُه إلى مشرف» سحبًا صامتًا لحقّه في البيانات،
    أو منحًا صامتًا لحقّ الاعتماد. والصلاحيةُ تُغيَّر بطلبٍ يقول ما يغيّره.
    """
    if role not in team.MEMBER_ROLES:
        raise AtheraError("team.unknown_member_role", status_code=422, role=role)
    before = member.role
    member.role = role
    await session.flush()
    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind="role_changed",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before={"role": before}, state_after={"role": role},
        note_ar="تغيير الدور لا يغيّر الصلاحيات؛ لكلٍّ منهما طلبه.")
    await audit.record(
        session, tenant_id=tenant_id, action="team.role_changed",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id, state_before={"role": before},
        state_after={"role": role},
        reason="a project role is not a permission set; changing one never changes "
               "the other by side effect")
    return member


async def set_permissions(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID, keys: list[str],
) -> frozenset[str]:
    try:
        team.validate_permissions(keys)
    except team.TeamError as exc:
        raise AtheraError("team.unknown_permission", status_code=422,
                          detail=str(exc)) from exc

    before = await permissions_of(session, member_id=member.id)
    wanted = frozenset(keys)
    for row in (
        await session.execute(
            select(ProjectMemberPermission).where(
                ProjectMemberPermission.member_id == member.id)
        )
    ).scalars().all():
        if row.permission_key not in wanted:
            await session.delete(row)
    await session.flush()
    await _grant_permissions(
        session, tenant_id=tenant_id, member=member,
        keys=sorted(wanted - before), granted_by=actor_user_id)

    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind="permissions_changed",
        actor_user_id=actor_user_id, subject_user_id=member.user_id,
        state_before={"permissions": sorted(before)},
        state_after={"permissions": sorted(wanted)})
    await audit.record(
        session, tenant_id=tenant_id, action="team.permissions_changed",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id, state_before={"permissions": sorted(before)},
        state_after={"permissions": sorted(wanted)},
        reason="least privilege: a permission is granted explicitly, never implied "
               "by team membership")
    return wanted


async def set_access_state(
    session: AsyncSession, *, tenant_id: uuid.UUID, member: ProjectMember,
    actor_user_id: uuid.UUID, state: str, left_voluntarily: bool = False,
) -> ProjectMember:
    """إيقافُ الوصول وإعادتُه والإزالة — **ولا يُحذف الصفّ**.

    فحذفُ العضو يمحو من كان في الفريق ومتى، ويمحو معه أثرَ موافقته وأدوارَ
    CRediT التي أقرّها. والورقةُ تُنشر بعد سنة، والسؤال «من كان يعمل عليها»
    يُسأل بعدها بسنتين.
    """
    # `invited` حالُ نشأةٍ تبلغها الدعوة، ولا تُفرض بطلبٍ إداري: فرضُها على
    # عضوٍ قائم يقطع وصولَه بلا دعوةٍ يقبلها، ولا رمزَ له يعود به.
    if state not in ("active", "suspended", "removed"):
        raise AtheraError("team.unknown_access_state", status_code=422, state=state)
    before = member.access_state
    now = _now()
    member.access_state = state
    member.suspended_at = now if state == "suspended" else None
    member.removed_at = now if state == "removed" else None
    await session.flush()

    kind = {"suspended": "access_suspended", "active": "access_restored",
            "removed": "left" if left_voluntarily else "removed"}.get(state, "removed")
    await record_member_event(
        session, tenant_id=tenant_id, project_id=member.project_id,
        member_id=member.id, event_kind=kind, actor_user_id=actor_user_id,
        subject_user_id=member.user_id, state_before={"access_state": before},
        state_after={"access_state": state})
    await audit.record(
        session, tenant_id=tenant_id, action=f"team.{kind}",
        object_type=MEMBER_OBJECT_TYPE, object_id=member.id,
        actor_user_id=actor_user_id, state_before={"access_state": before},
        state_after={"access_state": state},
        reason="a member's access is a state, never a deleted row; the record of who "
               "worked on the paper outlives the collaboration")
    return member
