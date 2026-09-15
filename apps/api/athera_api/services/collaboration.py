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

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError, MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..db import project_session
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

    ## وطلبانِ متزامنان لا يُسقطان الصفحة

    **«اقرأ ثمّ اكتب» في طلبين متوازيين يُنتج ٥٠٠.** وشاشةُ الفريق تفتح
    أربعةَ طلباتٍ معًا — الأعضاءَ والقرارات والصندوقَ وما أملكه — وكلُّها
    تمرّ بهذه البوابة. فيقرأ اثنان «لا عضوية»، ويكتب كلٌّ منهما، ويصطدم
    الثاني بـ`uq_project_members_project_account`. وقد وقع ذلك فعلًا في
    أوّل تشغيلةٍ بمتصفّحٍ حقيقيّ: صفحةٌ تُصيَّر وخلفها خطآن.
    ولا يُرى ذلك في اختبارٍ يُنادي الدالّةَ مرّةً.

    **والقيدُ هو مَن يفصل**، لا قراءةٌ قبله: يُحاول الإدخالُ داخل نقطةِ
    حفظٍ، فإن رفضه القيدُ رُجع إليها وأُعيدت القراءة — ومَن كتبه قد
    أتمَّ معاملتَه (وإلّا لَانتظر القيدُ نتيجتَها). فالجوابُ صفٌّ واحدٌ
    صحيحٌ في الحالين، ولا صفَّ مكرَّر ولا طلبٌ يسقط.
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
    try:
        async with session.begin_nested():
            session.add(member)
            await session.flush()
    except IntegrityError:
        # سبقني غيري إلى الصفّ نفسِه — فالصفُّ موجودٌ، والمنحُ والسجلُّ
        # كُتبا في معاملته. ولا يُعاد شيءٌ منها هنا.
        raced = await member_for(
            session, project_id=project_id, user_id=actor_user_id)
        if raced is not None:
            return raced
        raise

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
    """يقرأ ما يملكه الطالبُ في هذا البحث — ويرفض إن لم يملك عضويةً حيّة.

    **وصاحبُ البحث مستثنًى من حالِ الصفّ.** فهذه الدالّةُ بوابةُ مسارات
    الفريق، وكانت تقرأ الصفَّ وحده: فمن يحمل `manage_team` كان يوقف عضويّةَ
    المالك، فيُقصى صاحبُ البحث عن إدارة بحثه ولا مسارَ يعيده. والملكيّةُ
    سلطةُ جذر — وتوافقُ هذه البوابةِ مع `ensure_project_access` مقصود: بابانِ
    يختلفان على بحثٍ واحد عطبٌ لا حالةٌ طرفيّة.
    """
    await _project(session, project_id)
    member = await member_for(session, project_id=project_id, user_id=user_id)
    if member is None:
        member = await ensure_owner_membership(
            session, tenant_id=tenant_id, project_id=project_id,
            actor_user_id=user_id)
    if member is None:
        raise Forbidden("team.not_a_project_member", project_id=str(project_id))

    # ملكيّةٌ مُثبَتة: تُردّ سلطةُ الجذر كاملةً أيًّا كان ما في الصفّ.
    if await is_verified_owner(
            session, project_id=project_id, user_id=user_id):
        return Access(member=member, permissions=OWNER_IMPLIED_PERMISSIONS)

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
    invited_user_id: uuid.UUID | None = None,
) -> IssuedInvitation:
    """دعوةٌ إلى بحث — بمهلةٍ، ورمزٍ مجزَّأ، واقتراحِ دورٍ وصلاحيات.

    والاقتراحُ اقتراح: لا يصير صلاحيةً إلّا بعد قبولٍ من حسابٍ مصادَق.

    ## و`invited_user_id` ربطٌ صريحٌ يُغني عن الترشيح بالبريد

    والمسارُ القائم يُرشّح بالبريد **داخل مستأجر البحث**: حسابٌ في مستأجرٍ
    آخر لا يُرشَّح، فتُكتب دعوةٌ بلا `invited_user_id`. وذاك صحيحٌ لدعوةٍ
    محلّيّة — وقاصرٌ عن الاستقطاب، حيث المتقدّمُ من مؤسسةٍ أخرى قصدًا.

    فمن يعرف الحسابَ بعينه — **مشتقًّا في الخادم من صفِّ التطبيق** —
    يمرّره هنا، فيصير هو الرابط. ولا يُرشَّح بالبريد حينها: البريدُ
    للعرض والإبلاغ، والحسابُ هو الحدّ.

    **ولا يُقبل هذا المُعامِلُ من عميل**: مُناديه خدمةُ التحويل، وهي
    تقرؤه من `RecruitmentApplication.applicant_user_id`.
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
    if invited_user_id is not None:
        # ربطٌ صريح: الحسابُ معروفٌ بعينه، ولا يُبحث عنه ببريدٍ ولا
        # يُقيَّد بمستأجر البحث — وذاك هو المقصود.
        candidate = (
            await session.execute(select(User).where(User.id == invited_user_id))
        ).scalar_one_or_none()
        if candidate is None:
            raise AtheraError("team.invalid_invitation", status_code=422,
                              detail="invited_user_id")
    else:
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
    # **وحدثُ الدعوة يُكتب في مستأجرها لا في مستأجر من ردّ عليها.**
    #
    # فالمُعتذِرُ من مؤسسةٍ أخرى كان يُكتب حدثُه بمستأجره هو، فيُرفض عند
    # سياسة العزل على `project_member_events` — وهو نفسُ العطب الذي أُصلح
    # في `accept_invitation`.
    await record_member_event(
        session, tenant_id=invitation.tenant_id, project_id=invitation.project_id,
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
    # **والحسابُ هو الحدُّ متى كانت الدعوةُ مربوطةً بحساب.**
    #
    # فالبريدُ حدٌّ أضعف: حسابانِ في مستأجرَين قد يحملان بريدًا واحدًا،
    # ومطابقةُ البريد تُجيز أحدَهما مكان الآخر. ودعواتُ الاستقطاب مربوطةٌ
    # بـ`invited_user_id` في الخادم، فلا يُسأل البريدُ فيها أصلًا.
    #
    # وما لا ربطَ له — الدعواتُ المحلّيّةُ ببريدٍ لحسابٍ لم يُرشَّح — يبقى
    # على حدِّه القديم بلا تغيير.
    # **والجوابُ جوابُ المعدوم لا «ليست لك».**
    #
    # فـ«موجودةٌ وليست لك» تكشف وجودَ دعوةٍ لمن ليست له، فيُعَدّ الرموزُ
    # ويُستدلّ على مَن دُعي. والمعدومُ وغيرُ المأذون يُجابان جوابًا واحدًا
    # — وهو نفسُ ما اختاره RC-T1A للأبحاث. ومديرٌ يرى الدعوةَ بحقّ يُجاب
    # كذلك: رؤيتُها ليست حقًّا في قبولها.
    if invitation.invited_user_id is not None:
        if accepting_user_id != invitation.invited_user_id:
            raise NotFound("team.invitation_not_found")
    elif team.normalize_email(accepting.email) != team.normalize_email(
            invitation.invited_email):
        raise NotFound("team.invitation_not_found")

    # **ومستأجرُ العضويّة مستأجرُ الدعوة، لا مستأجرُ من قَبِل.**
    #
    # وكان يُكتب من المُعامِل الممرَّر. ولمتعاونٍ من مؤسسةٍ أخرى كان ذلك
    # يَسِمُ صفَّه بمستأجره هو — فلا يراه صاحبُ البحث في فريقه، ولا
    # تُطابقه استعلاماتُ RC-T1A التي ترشّح بـ`ProjectMember.tenant_id`.
    # فالعضويّةُ تعيش حيث يعيش البحث.
    member_tenant_id = invitation.tenant_id

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
            tenant_id=member_tenant_id, project_id=invitation.project_id,
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
        session, tenant_id=member_tenant_id, member=member,
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
        session, tenant_id=member_tenant_id, project_id=invitation.project_id,
        member_id=member.id, invitation_id=invitation.id, event_kind="accepted",
        actor_user_id=accepting_user_id, subject_user_id=accepting_user_id,
        state_after={"role": member.role,
                     "permissions": sorted(invitation.proposed_permissions or [])},
        note_ar="العضوية رُبطت بالحساب المصادَق الذي قبِل الدعوة.",
    )
    await audit.record(
        session, tenant_id=member_tenant_id, action="team.invitation_accepted",
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
    # والاعتذارُ حدُّه الحسابُ متى كانت الدعوةُ مربوطةً به — والجوابُ
    # جوابُ المعدوم كما في القبول.
    if declining is None:
        raise NotFound("team.invitation_not_found")
    if invitation.invited_user_id is not None:
        if declining_user_id != invitation.invited_user_id:
            raise NotFound("team.invitation_not_found")
    elif team.normalize_email(declining.email) != team.normalize_email(
            invitation.invited_email):
        raise NotFound("team.invitation_not_found")
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
    # وصاحبُ البحث لا يُنزَّل من موضعه بإدارةِ فريق: الدورُ لا يمنحه سلطةً
    # ولا يسلبها، لكنّ شاشةً تقول «شكرٌ وتقدير» عن صاحب البحث تكذب على من
    # يقرؤها. ونقلُ الملكيّة مسارٌ لم يوجد بعد.
    if role != "principal_investigator":
        await _refuse_if_verified_owner(
            session, project_id=member.project_id, member=member,
            operation="change_role")
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

    wanted = frozenset(keys)
    # **والبابُ الثاني يُسدّ مع الأول.** فحمايةُ `access_state` وحدها كانت
    # تترك هذا المسار: صفوفُ المالك تُنزع فيبقى «نشطًا» بلا صلاحيةٍ واحدة.
    # ولا يُمنع إلّا ما يُنقص — فضبطُها على سلطة الجذر كاملةً لا يُنقص شيئًا.
    if not wanted >= OWNER_IMPLIED_PERMISSIONS:
        await _refuse_if_verified_owner(
            session, project_id=member.project_id, member=member,
            operation="set_permissions")

    before = await permissions_of(session, member_id=member.id)
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
    # وصاحبُ البحث لا يُوقَف ولا يُزال — **ولا يخرج بنفسه** وهو صاحبُه.
    # فمسارُ الخروج يمرّ من هنا بـ`left_voluntarily`، وبحثٌ بلا صاحبٍ لا
    # يُستعاد إلّا بتدخّلٍ يدويّ في القاعدة. والإعادةُ إلى «نشط» تزيد ولا
    # تنقص، فتمرّ.
    if state != "active":
        await _refuse_if_verified_owner(
            session, project_id=member.project_id, member=member,
            operation="leave_project" if left_voluntarily else "set_access_state")
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


# ═══════════════ مَن يرى بحثًا — قراءةً بلا أثر (RC-T1A) ═══════════════
#
# **العطبُ الذي يُغلق هنا.** كانت قائمةُ «أبحاثي» تُبنى بـ
# `tenant_id == principal.tenant_id` وحده، فيرى كلُّ باحثٍ في المستأجر
# كلَّ بحثٍ فيه: بحوثًا لا يملكها ولا هو عضوٌ فيها. وعضويّةُ المستأجر
# ليست عضويّةَ بحث — والفرقُ هو كلُّ ما تقوم عليه فرقُ البحث.
#
# **والقاعدةُ الواحدة:** مالكٌ، أو عضوٌ **نشط** يحمل `view_project` صفًّا
# صريحًا. ولا دورَ يُفسَّر، ولا اسمَ يُطابَق، ولا انتماءَ مستأجرٍ يكفي.
#
# ## ولمَ قراءةٌ بلا أثر
#
# `access_for` تُنشئ عضويّةَ المالك عند الحاجة (`ensure_owner_membership`)،
# وذاك صحيحٌ في مسارٍ يُغيّر فريقًا. لكنّ **فتحَ صفحةٍ أو عدَّ قائمةٍ لا
# يكتب**: كتابةٌ في كلّ قراءةٍ تُنشئ صفوفًا بعدد الزيارات، وتُحوّل `GET`
# إلى تغييرٍ لا يتوقّعه أحد. فهذه الدوالُّ تقرأ وتحكم ولا تُنشئ شيئًا.

VIEW_PROJECT = "view_project"


async def _owned_project_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> set[uuid.UUID]:
    """بحوثُ هذا الباحث بالملكيّة — **بمصدري الإسناد الموثوقين معًا**.

    وهما اللذان يقرؤهما `owner_user_id` لبحثٍ واحد: ملفُّ الباحث، وفاعلُ
    حدثِ الإنشاء في سجلّ التدقيق. وتُقرآن هنا **مجموعتين** لا بحثًا بحثًا،
    فلا يصير عدُّ القائمة استعلامًا لكلّ صفّ.
    """
    by_profile = set((await session.execute(
        select(ResearchProject.id)
        .join(ResearcherProfile, ResearcherProfile.id == ResearchProject.profile_id)
        .where(ResearchProject.tenant_id == tenant_id,
               ResearcherProfile.user_id == user_id)
    )).scalars())

    by_creation = set((await session.execute(
        select(AuditEvent.object_id)
        .where(AuditEvent.tenant_id == tenant_id,
               AuditEvent.object_type == PROJECT_OBJECT_TYPE,
               AuditEvent.action.in_(PROJECT_CREATED_ACTIONS),
               AuditEvent.actor_user_id == user_id,
               AuditEvent.object_id.is_not(None))
    )).scalars())

    return by_profile | by_creation


async def _member_project_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    permission: str = VIEW_PROJECT,
) -> set[uuid.UUID]:
    """بحوثٌ هو فيها عضوٌ **نشط** يحمل الاطّلاعَ **والصلاحيةَ المطلوبة معًا**.

    و«نشط» شرطٌ لا تزيين: المدعوُّ لم يقبل بعد، والموقوفُ مُنع، والمُزال
    ذهب — وثلاثتهم ليسوا أعضاءً عاملين.

    ## ولمَ الاطّلاعُ شرطٌ مع كلّ صلاحيةٍ أخرى

    **كان هذا الفحص يسأل عن الصلاحية وحدها، فاختلف بابانِ على بحثٍ واحد.**
    فـ`_decide` — وهي قرارُ التفويض الوحيد — تشترط `view_project` أساسًا
    قبل أن تنظر في شيء: عضوٌ نُزع اطّلاعُه لا مدخلَ له مهما بقي في صفوفه.
    وكان المُرشِّح هنا يكتفي بالصفّ المطلوب، فيقع التناقضُ الآتي:

      عضوٌ نُزع منه `view_project` وبقي له `manage_data` —
        • يختفي البحثُ من «أبحاثي»،
        • وتردّ `ensure_project_access` عليه ٤٠٤،
        • **ويبقى البحثُ ظاهرًا في قوائم طبقة التحليل** التي تُرشَّح بهذا.

    وقائمةٌ تعرض ما لا يُفتح ليست تسامحًا: هي تسريبُ وجودِ بحثٍ وعنوانِه
    ومعرّفِه لمن سُحب مدخلُه — ونزعُ الاطّلاع إنّما يُفعل ليمنع هذا بعينه.

    **وعبارةٌ واحدة تُثبت الثلاثة**: العضويّةَ الحيّة، والاطّلاعَ، والصلاحيةَ
    المطلوبة — بوصلتين على الجدول نفسه بكُنيتين. ورحلةٌ ثانية إلى قاعدةٍ في
    إقليمٍ آخر ثمنٌ لا يلزم دفعه.

    وحين تكون المطلوبةُ هي الاطّلاعَ نفسه، تُطابق الوصلتان الصفَّ ذاته —
    فيبقى الجواب صحيحًا بلا فرعٍ خاصّ يُكتب له.
    """
    baseline = aliased(ProjectMemberPermission)
    wanted = aliased(ProjectMemberPermission)
    return set((await session.execute(
        select(ProjectMember.project_id)
        .join(baseline, and_(baseline.member_id == ProjectMember.id,
                             baseline.permission_key == VIEW_PROJECT))
        .join(wanted, and_(wanted.member_id == ProjectMember.id,
                           wanted.permission_key == permission))
        .where(ProjectMember.tenant_id == tenant_id,
               ProjectMember.user_id == user_id,
               ProjectMember.access_state == "active")
    )).scalars())


async def project_ids_with(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    permission: str,
) -> set[uuid.UUID]:
    """بحوثٌ يملك فيها هذا الباحث **هذه الصلاحيةَ بعينها** — بالاتّحاد.

    وقوائمُ الأسطح التفصيلية تُرشَّح بها لا بالاطّلاع: من يرى البحث ليس
    بالضرورة من يرى مجموعاتِ بياناته وخطط تحليله. والمالكُ داخلٌ دائمًا،
    فسلطةُ النسب تحمل المفردةَ كلَّها.

    والمالكُ الذي له صفُّ عضويّةٍ أيضًا يظهر مرّةً واحدة: مجموعةٌ لا قائمة.
    """
    owned = await _owned_project_ids(
        session, tenant_id=tenant_id, user_id=user_id)
    joined = await _member_project_ids(
        session, tenant_id=tenant_id, user_id=user_id, permission=permission)
    return owned | joined


async def visible_project_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> set[uuid.UUID]:
    """كلُّ بحثٍ يجوز لهذا الباحث أن **يراه** — الاطّلاع وحده."""
    return await project_ids_with(
        session, tenant_id=tenant_id, user_id=user_id, permission=VIEW_PROJECT)


async def project_ids_with_across_tenants(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    permission: str,
) -> set[uuid.UUID]:
    """بحوثٌ للطالب فيها **هذه الصلاحيةُ بعينها** — في أيّ مؤسسة.

    وهي أختُ `project_ids_with`، وتُستعمل في القوائم التي **لا تستطيع
    الدخولَ إلى مستأجرِ بحثٍ واحد** لأنّها تجمع بحوثًا كثيرة: قوائمُ
    طبقة التحليل مثلًا. وصفوفُها تُرى بسياسات تحديد الموضع (0036).

    **والملكيّةُ تبقى في مستأجرها**: صاحبُ البحث بحثُه في مؤسسته، ولا
    يحتاج جسرًا — فتُقرأ ملكيّتُه كما كانت، وتُضاف إليها عضويّاتُه
    المُثبَتة عبرَ المؤسسات.

    ولا تُستعمل هذه لتوسيع قائمةٍ يُمكن أن تُقرأ في نطاق بحثٍ واحد:
    الأضيقُ ما يكفي، والقوائمُ العامّة وحدها تحتاج الاتّحاد.
    """
    owned = await _owned_project_ids(
        session, tenant_id=tenant_id, user_id=user_id)
    joined = await _self_member_scopes(
        session, user_id=user_id, permission=permission)
    return owned | {project_id for project_id, _tenant, _role in joined}


# ═════════════════ «أبحاثي» عبرَ المستأجرين ═════════════════


@dataclass(frozen=True)
class ResearchEntry:
    """بحثٌ في قائمة «أبحاثي» — **وصلتُه بصاحبها معلنةٌ معه**.

    فالقائمةُ كانت كلُّها أبحاثَ صاحبها، فلم تحتج وسمًا. وبعد التعاون
    عبرَ المؤسسات صار فيها بحثُ غيرِه — وبطاقةٌ لا تقول ذلك تعرض على
    المتعاون أزرارَ أرشفةٍ وحذفٍ لبحثٍ ليس له، فيضغط ويُردّ، أو — وهو
    الأسوأ — يظنّ أنّ البحثَ صار بحثَه.

    و`project` صفٌّ **مُنفصلٌ عن جلسته** أحيانًا: أبحاثُ المستأجرات
    الأخرى تُقرأ في جلسةٍ تُغلق قبل العودة. و`expire_on_commit=False`
    تُبقي أعمدتَه المحمَّلة كما هي، فلا يُقرأ منه إلّا عمود — ولا علاقةٌ
    مؤجَّلة.
    """

    project: ResearchProject
    is_owner: bool
    member_role: str | None

    @property
    def relationship(self) -> str:
        """`owner` أو `collaborator` — والملكيّةُ أوّلُ ما يُسأل عنه."""
        return "owner" if self.is_owner else "collaborator"


async def _self_member_scopes(
    session: AsyncSession, *, user_id: uuid.UUID,
    permission: str = VIEW_PROJECT,
) -> list[tuple[uuid.UUID, uuid.UUID, str]]:
    """صفوفُ عضويّةِ **الفاعلِ نفسِه** — عبرَ المستأجرين — بعبارةٍ واحدة.

    وتُعيد `(project_id, tenant_id, role)` لكلّ بحثٍ هو فيه عضوٌ **نشط**
    يحمل `view_project` والصلاحيةَ المطلوبة معًا: الشروطُ الثلاثةُ نفسُها
    التي يشترطها `_member_project_ids`، بلا شرطِ المستأجر.

    ## ولمَ يُرى صفُّ عضويّةٍ في مستأجرٍ آخر أصلًا

    بسياسةِ `project_members_self_read` من الترحيل 0035 وحدها:
    `user_id = app_current_actor()`. وهي أضيقُ ما يكفي — **صفوفُ الفاعل
    هو**، لا صفوفُ فريقٍ ولا بحثٍ ولا مستأجر. ولا `SECURITY DEFINER`
    ولا `BYPASSRLS` ولا `USING (true)`: الجسرُ يعرف الفاعلَ ولا يعرف
    غيرَه.

    ## والمُرشِّحُ في SQL هو المرجع، لا السياسة

    فسياساتُ PostgreSQL المُجيزةُ تتّحد بـ**OR**: سياسةُ المستأجر
    القديمةُ باقيةٌ إلى جانب هذه، فالصفوفُ المرئيّةُ هي «صفوفي في أيّ
    مستأجر **أو** كلُّ صفٍّ في مستأجري». ولذلك يُكتب `user_id = :user_id`
    في العبارة صراحةً: هو ما يجعل الجوابَ «صفوفي» لا «صفوف زملائي».
    """
    baseline = aliased(ProjectMemberPermission)
    wanted = aliased(ProjectMemberPermission)
    rows = (await session.execute(
        select(ProjectMember.project_id, ProjectMember.tenant_id,
               ProjectMember.role)
        .join(baseline, and_(baseline.member_id == ProjectMember.id,
                             baseline.permission_key == VIEW_PROJECT))
        .join(wanted, and_(wanted.member_id == ProjectMember.id,
                           wanted.permission_key == permission))
        .where(ProjectMember.user_id == user_id,
               ProjectMember.access_state == "active")
    )).all()
    return [(r[0], r[1], r[2]) for r in rows]


async def my_research(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> list[ResearchEntry]:
    """كلُّ بحثٍ للباحث فيه مدخلٌ حقيقيّ — **وإن كان في مؤسسةٍ أخرى**.

    وهي قائمةٌ واحدة: البحثُ الذي قُبل فيه المتعاون يظهر مع أبحاثه، لا
    في شاشةٍ ثانية اسمها «أبحاثٌ مشتركة». فالتعاونُ ليس نوعًا آخرَ من
    البحث.

    ## وثلاثةُ أشياء لا تُخلط

      الملكيّة    تُشتقّ في مستأجر الباحث وحده (كما كانت).
      العضويّة    صفٌّ محفوظ — في أيّ مستأجر.
      الانتماءُ   للمؤسسة: **لا يُنشأ هنا ولا يُقرأ هنا.**

    ولا صفَّ `Membership` جديدٌ يُكتب في مستأجر البحث لأجل هذه القائمة.
    فمنحُ التعاون على بحثٍ ليس انتماءً إلى مؤسسةٍ: لو كُتب لَصار
    المتعاونُ عضوًا في كلّ ما في تلك المؤسسة، وذاك نقضُ العزل لا توسيعُ
    منتج. (والجردُ البنيويّ في SEC-P0 يُسمّي كلَّ موضعٍ يُنشئ انتماءً —
    وهذه الطبقةُ ليست منها.)

    ## والعبورُ يقع عبر الجسر القانونيّ وحده

    فبحثُ مستأجرٍ آخر لا يُقرأ من جلسةِ البيت: `research_projects` تبقى
    معزولةً بمستأجرها، ولا سياسةَ فاعلٍ عليها. ويُقرأ بـ`project_session`
    — الذي يُثبت بنفسه، في عبارته، أنّ للفاعل صفَّ عضويّةٍ نشطًا يحمل
    `view_project` في ذلك البحث بعينه، ويرفض الربطَ إن لم يكن. فلو دخل
    إلى هذه الدالّةِ معرّفُ بحثٍ لا يستحقّه الفاعل لَما رُبط، ولَما
    رُئي الصفُّ في جلسةٍ بقيت في مستأجر البيت.

    ## والثمنُ معلومٌ ومحدود

    رحلةٌ لكلّ بحثٍ **خارج** مستأجر الباحث — والقاعدةُ في إقليمٍ آخر.
    وأبحاثُ البيت كلُّها في عبارةٍ واحدة كما كانت، فالثمنُ يقع على
    التعاون عبرَ المؤسسات وحده، وعددُه في V1 آحاد. ولا يُستبدل ببوّابةٍ
    مميّزةٍ تقرأ أبحاثَ كلّ مستأجرٍ بضربةٍ واحدة: تلك تُشترى بحدِّ
    العزل نفسِه، والثمنُ أغلى من الرحلة.
    """
    owned = await _owned_project_ids(
        session, tenant_id=tenant_id, user_id=user_id)
    scopes = await _self_member_scopes(session, user_id=user_id)

    # صفٌّ واحدٌ لكلّ بحث: صاحبُ البحثِ العضوُ فيه يظهر مرّةً، بوسمِ
    # الملكيّة لا بوسمِ العضويّة — `_decide` تُقدّم الملكيّةَ كذلك.
    roles: dict[uuid.UUID, str] = {}
    foreign: dict[uuid.UUID, uuid.UUID] = {}
    for project_id, member_tenant, role in scopes:
        roles.setdefault(project_id, role)
        if member_tenant != tenant_id and project_id not in owned:
            foreign[project_id] = member_tenant

    home_ids = owned | {pid for pid, t, _ in scopes if t == tenant_id}
    found: dict[uuid.UUID, ResearchProject] = {}
    if home_ids:
        for row in (await session.execute(
            select(ResearchProject)
            .where(ResearchProject.deleted_at.is_(None),
                   ResearchProject.id.in_(home_ids))
        )).scalars():
            found[row.id] = row

    for project_id, member_tenant in foreign.items():
        async with project_session(project_id, tenant_id, user_id) as scoped:
            crossed = (await scoped.execute(
                select(ResearchProject)
                .where(ResearchProject.id == project_id,
                       ResearchProject.deleted_at.is_(None))
            )).scalar_one_or_none()
        # **ومستأجرُ الصفِّ يُطابق مستأجرَ العضويّة أو يُطرح.** فالعزلُ
        # يضمن هذا أصلًا؛ وفحصُه هنا يجعل أيَّ خللٍ في الجسر غيابًا من
        # قائمةٍ لا صفًّا من مستأجرٍ لا صلةَ للباحث به.
        if crossed is not None and crossed.tenant_id == member_tenant:
            found[project_id] = crossed

    entries = [
        ResearchEntry(project=row, is_owner=row.id in owned,
                      member_role=roles.get(row.id))
        for row in found.values()
    ]
    entries.sort(key=lambda e: e.project.created_at, reverse=True)
    return entries


# **الصلاحيّةُ تُقرأ مرّةً وتُستعمل مرارًا.** فالمسارُ الواحد يسأل عن
# الاطّلاع ثم عن التحرير، وسؤالان يعنيان رحلتين إلى قاعدةٍ في إقليمٍ آخر.
# فتُعاد المجموعةُ كاملةً، ويقرّر المسارُ منها بلا استعلامٍ ثانٍ.
#
# **وسلطةُ المالك تُشتقّ من مفردةِ الصلاحيات نفسها، لا من افتراضات دور.**
#
# كانت تُقرأ من `default_permissions("principal_investigator")`، فصارت
# سلطةُ الجذر معلَّقةً بما يُقترح لدورٍ عند الدعوة — وذاك سطرٌ قابلٌ
# للتغيير لأسبابِ منتجٍ لا علاقةَ لها بالملكيّة: لو ضُيّقت افتراضاتُ
# الباحث الرئيس غدًا (وهو تغييرٌ مشروع) لَضاقت معها سلطةُ صاحب البحث على
# بحثه في الوقت نفسه، بلا أن يقصد ذلك أحد.
#
# وهو نقضٌ للحدّ الذي تقوم عليه هذه الطبقة: **الدورُ ليس ملكيّة**. فتُقرأ
# المفردةُ المعياريّة كاملةً — كلُّ ما يُعرَّف صلاحيةَ بحثٍ في هذا النظام —
# ولا يمرّ الاشتقاقُ بدورٍ ولا بدالّةِ افتراضاته.
#
# وأنها تساوي اليوم افتراضاتِ الباحث الرئيس مصادفةٌ لا اعتماد: تلك تُساوي
# المفردةَ كلَّها الآن، وقد لا تُساويها غدًا.
OWNER_IMPLIED_PERMISSIONS: frozenset[str] = frozenset(team.PROJECT_PERMISSIONS)


def _decide(*, is_owner: bool, access_state: str | None,
            keys: frozenset[str]) -> frozenset[str] | None:
    """**القرارُ في موضعٍ واحد** — والملكيّةُ أوّلُ ما يُسأل عنه.

    ودالّتان تُحمّلان الصفوف (واحدةٌ تدمج الاستعلامات لبحثٍ قائم، وأخرى
    تقرؤها على مراحل لما في السلّة)، **وكلتاهما تقرّر من هنا**. فلو قرّرت
    كلٌّ لنفسها لافترقتا بأوّل تعديل — وبابانِ يختلفان على بحثٍ واحد هو
    العطبُ بعينه لا حالةً طرفيّة.

    ## ولمَ الملكيّةُ أوّلًا، لا صفُّ العضويّة

    كان هذا الفحصُ يقرأ صفَّ العضويّة أوّلًا ويعدّه المرجعَ متى وُجد — ليوافق
    `access_for`. وكان في ذلك عطبٌ: **مديرُ فريقٍ يُقصي صاحبَ البحث عن بحثه**.
    فمن يحمل `manage_team` كان يوقف عضويّةَ المالك أو ينزع صفوفَها، فيصير
    البحثُ الذي أنشأه محجوبًا عنه — ولا مسارَ يُعيده إليه.

    فالملكيّةُ المُثبَتة سلطةُ جذرٍ لا صفٌّ يُدار: تُشتقّ من ملفّ الباحث أو
    من حدث الإنشاء في سجلٍّ يُضاف إليه ولا يُعدَّل، ولا يملك أحدٌ تغييرَها
    من شاشة الفريق. وصفُّ العضويّة — حضورًا ودورًا وحالةً وصلاحيات — لا
    يصير وسيلةً لنقض ملكيّةٍ مُثبَتة.

    **والدورُ ليس ملكيّة.** فعضوٌ دورُه `principal_investigator` وليس صاحبَ
    النسب لا يأخذ شيئًا من هذا: المقارنةُ بـ`owner_user_id` وحدها، ولا
    تُشتقّ من مفردةٍ يكتبها مديرُ فريق.
    """
    if is_owner:
        # سلطةُ الجذر: ما كان `ensure_owner_membership` ليمنحه، ولا زيادة.
        return OWNER_IMPLIED_PERMISSIONS
    if access_state != "active":
        return None
    if VIEW_PROJECT not in keys:
        return None
    return keys


async def is_verified_owner(
    session: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID | None
) -> bool:
    """أهذا الحسابُ صاحبُ النسب المُثبَت لهذا البحث؟

    ولا يُسأل عن دورٍ ولا عن صفٍّ: `owner_user_id` وحدها، وهي تقرأ ملفَّ
    الباحث أو فاعلَ حدثِ الإنشاء — ومصدرانِ لا تكتبهما إدارةُ الفريق.
    """
    if user_id is None:
        return False
    return await owner_user_id(session, project_id=project_id) == user_id


async def _owner_implied(
    session: AsyncSession, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> frozenset[str] | None:
    """الملكيّةُ تُقرأ من مصدرها الموثوق — **بلا كتابة**.

    وهذا هو جسرُ ما قبل العضويّات أيضًا: البحوث تُنشأ في موجّهاتٍ لا تُنشئ
    لصاحبها صفًّا، وبلا هذا الطريق يفقد كلُّ باحثٍ بحثَه.
    """
    if await is_verified_owner(
            session, project_id=project_id, user_id=user_id):
        return OWNER_IMPLIED_PERMISSIONS
    return None


# ═══════════ المالكُ المُثبَت لا يُقصى عن بحثه (RC-T1A) ═══════════

OWNER_IMMUTABLE = "team.owner_is_immutable"

# **دورةُ حياة البحث لصاحبه وحده** — ولا صلاحيةَ تُذكر في الرفض.
#
# فالأرشفةُ والحذفُ الظاهر والاسترجاع أفعالٌ على البحث كلِّه لا على محتواه،
# ولا صفَّ في مفردة الصلاحيات يخصّها: `edit_research_content` كان يفتحها،
# وهو صفُّ **تحرير المحتوى العلميّ** — فكان طالبُ دراساتٍ عليا يُدعى ليحرّر
# فصلًا فيرمي البحث كلَّه في السلّة. والصفُّ الصحيح لا وجود له، ولا يُختلق
# في دفعةٍ أمنية؛ فيُرفع الحدُّ إلى النسب المُثبَت حتى يوجد.
OWNER_ONLY = "workspace.owner_only"


async def _refuse_if_verified_owner(
    session: AsyncSession, *, project_id: uuid.UUID,
    member: ProjectMember, operation: str,
) -> None:
    """يمنع كلَّ عمليةٍ تُنقص سلطةَ صاحب البحث على بحثه.

    **والمنعُ صريحٌ لا صامت.** فلو مرّت العمليةُ ثم لم تُنقص شيئًا (لأنّ
    التفويض يقرأ الملكيّة) لبقيت شاشةُ الفريق تقول «أُوقف» عن مالكٍ لم
    يُوقَف — وحالةٌ مكتوبةٌ تخالف السلوك أسوأ من رفضٍ يُقرأ.

    و٤٠٩ لا ٤٠٣: الطالبُ يملك `manage_team` فعلًا، والمانعُ ليس نقصَ إذنٍ
    بل تناقضُ الطلب مع حقيقةٍ قائمة — لا مالكَ ثانيًا لهذا البحث.

    ولا نقلَ للملكيّة في هذه الدفعة: حتى يوجد مسارٌ صريح لنقلها، صاحبُ
    النسب ثابت.
    """
    if not await is_verified_owner(
            session, project_id=project_id, user_id=member.user_id):
        return
    raise AtheraError(OWNER_IMMUTABLE, status_code=409, operation=operation,
                      project_id=str(project_id))


async def project_permissions(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> frozenset[str] | None:
    """ما يملكه هذا الباحث في هذا البحث — أو `None` إن لم يكن له أن يراه.

    و`None` ليست «مجموعةً فارغة»: الفارغةُ تعني عضوًا بلا صلاحيات، وهذه
    تعني **لا مدخلَ أصلًا** — والفرقُ بينهما هو الفرق بين ٤٠٣ و٤٠٤.

    **ولا تشترط بحثًا قائمًا**، فتصلح لما في السلّة: معاينةُ الإتلاف
    والاسترجاع يقعان على محذوفٍ بحكم التعريف، والملكيّةُ لا تزول بالحذف
    الظاهر. ومن أراد الحدَّ كاملًا — المستأجرَ والحياةَ والصلاحية — فذاك
    `ensure_project_access`، وهي تُنجزه في استعلامٍ واحد.
    """
    # **الملكيّةُ أوّلًا** — فصفُّ العضويّة لا ينقض نسبًا مُثبَتًا.
    if await is_verified_owner(
            session, project_id=project_id, user_id=user_id):
        return OWNER_IMPLIED_PERMISSIONS
    member = await member_for(
        session, project_id=project_id, user_id=user_id)
    if member is None:
        return None
    return _decide(
        is_owner=False, access_state=member.access_state,
        keys=frozenset(await permissions_of(session, member_id=member.id)))


async def may_view_project(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """أيجوز لهذا الباحث أن يفتح هذا البحث؟ — **قراءةٌ بلا أثر**."""
    return await project_permissions(
        session, tenant_id=tenant_id, project_id=project_id,
        user_id=user_id) is not None


@dataclass(frozen=True)
class ProjectAccess:
    """البحثُ ومَا يملكه طالبُه فيه — **بقراءةٍ واحدة**.

    والمسارُ يحتاجهما معًا دائمًا: الصفَّ ليعرض، والمجموعةَ ليقرّر. وردُّهما
    منفصلين يعني رحلتين إلى قاعدةٍ في إقليمٍ آخر، وعدُّ الرحلات هو زمنُ
    الاستجابة هنا.
    """

    project: ResearchProject
    permissions: frozenset[str]
    is_owner: bool = False

    def allows(self, permission: str) -> bool:
        return permission in self.permissions


async def ensure_project_access(
    session: AsyncSession, *, tenant_id: uuid.UUID, project_id: uuid.UUID,
    user_id: uuid.UUID, permission: str = VIEW_PROJECT,
    not_found_code: str = "workspace.project_not_found",
    require_owner: bool = False,
) -> ProjectAccess:
    """**البوابةُ الوحيدة لكلّ مسارٍ يقبل معرّفَ بحث.**

    ومساواةُ المستأجر ليست تفويضًا: زميلٌ في المؤسسة نفسها ليس عضوًا في
    كلّ بحثٍ فيها. وهذا هو العطب الذي أغلقته هذه الدفعة — كان كلُّ موجّهٍ
    يقرأ البحث بمعرّفه ومستأجره ثم يمضي، فقرأ زميلٌ خيطَ زميله وهيكلَه
    وكتب فيهما، وردَّ المسارُ ٢٠٠.

    وثلاثةُ فحوصٍ في ترتيبٍ مقصود:

      ١. **بحثٌ قائم** في هذا المستأجر — وما في السلّة ليس قائمًا.
      ٢. **مدخلٌ أصلًا؟** فإن لا، **٤٠٤** لا ٤٠٣: وجودُ بحثِ غيرك معلومةٌ
         لا تُفشى، ولو رددنا ٤٠٣ لصار المسارُ عدّادَ بحوثٍ لمن يجرّب
         المعرّفات. والرمزُ نفسه في الحالتين، فلا يُفرَّق بينهما بالنصّ.
      ٣. **هذا الفعلُ بعينه؟** فإن لا، **٤٠٣**: الوجودُ معلومٌ له سلفًا،
         والرسالةُ الصادقة أنفع من إنكارٍ كاذب.

    ولا تكتب شيئًا. و`access_for` تُنشئ عضويّةَ المالك عند الحاجة، وذاك
    صحيحٌ في مسارٍ يُغيّر فريقًا؛ أمّا **فتحُ صفحةٍ فلا يُنشئ عضويّة**.
    """
    # **استعلامٌ واحد لا ثلاثة.** والقاعدةُ في إقليمٍ آخر غيرِ إقليم
    # التطبيق، فكلُّ رحلةٍ ~٦٠ms — وعدُّ الرحلات هو زمنُ الاستجابة هنا.
    # وهذه البوابةُ تقع على كلّ مسارٍ يقبل معرّفَ بحث، فثلاثةُ استعلاماتٍ
    # فيها تصير مئتي جزءٍ من الثانية على كلّ شاشةٍ يفتحها الباحث.
    #
    # فالبحثُ وحالُ العضويّة وصفوفُ الصلاحيات تُقرأ معًا بوصلتين خارجيتين:
    # الخارجيّةُ لأنّ غيابَ العضويّة جوابٌ مطلوب لا سببَ لحجب الصفّ، ثم
    # يُقرّر `_decide`. والتجميعُ على مفتاح البحث الأساسيّ، فتُقرأ أعمدتُه
    # كلُّها تحت اعتماديّةٍ وظيفية.
    # **والملكيّةُ تُقرأ في العبارة نفسها**، لا برحلةٍ ثانية. وهي مصدرا
    # `owner_user_id` بترتيبهما: ملفُّ الباحث، ثمّ فاعلُ حدثِ الإنشاء —
    # و`coalesce` تُعطي أسبقيّةَ الأوّل كما تفعل تلك الدالّة بالضبط.
    owner = func.coalesce(
        select(ResearcherProfile.user_id)
        .where(ResearcherProfile.id == ResearchProject.profile_id)
        .scalar_subquery(),
        select(AuditEvent.actor_user_id)
        .where(AuditEvent.object_type == PROJECT_OBJECT_TYPE,
               AuditEvent.object_id == ResearchProject.id,
               AuditEvent.action.in_(PROJECT_CREATED_ACTIONS),
               AuditEvent.actor_user_id.is_not(None))
        .order_by(AuditEvent.occurred_at).limit(1)
        .scalar_subquery(),
    )
    keys_agg = func.array_agg(ProjectMemberPermission.permission_key)
    rows = (await session.execute(
        select(ResearchProject, owner.label("owner_user_id"),
               ProjectMember.id, ProjectMember.access_state, keys_agg)
        .outerjoin(ProjectMember,
                   and_(ProjectMember.project_id == ResearchProject.id,
                        ProjectMember.tenant_id == tenant_id,
                        ProjectMember.user_id == user_id))
        .outerjoin(ProjectMemberPermission,
                   ProjectMemberPermission.member_id == ProjectMember.id)
        .where(ResearchProject.id == project_id,
               ResearchProject.tenant_id == tenant_id,
               ResearchProject.deleted_at.is_(None))
        # **والتجميعُ على صفّ العضويّة لا على حالتها.** فلو جُمِع على
        # الحالة لاندمج صفّان مختلفان في مجموعةٍ واحدة، واتّحدت صلاحيّاتُ
        # عضويّةٍ مُزالة مع أخرى نشطة — منحةٌ تُركَّب من صفَّين لا تخصّ
        # واحدًا منهما.
        .group_by(ResearchProject.id, ProjectMember.id,
                  ProjectMember.access_state)
    )).all()
    if not rows:
        raise NotFound(not_found_code)

    project, owner_id = rows[0][0], rows[0][1]
    is_owner = owner_id is not None and owner_id == user_id
    memberships = [r for r in rows if r[2] is not None]
    if len(memberships) > 1:
        # **ولا يُخمَّن أيُّهما المقصود.** ولا قيدَ في القاعدة يمنع صفَّين
        # لحسابٍ واحد في بحثٍ واحد (`user_id` يقبل الفراغ لمدعوٍّ بالبريد
        # لم يقبل بعد، فلا مفتاحَ فريدًا عليه). و`member_for` تُعلن الخلل
        # بـ`scalar_one_or_none` — فيُعلَن هنا مثلها: صفٌّ مُزالٌ وآخر نشط
        # يجعلان الجوابَ اختيارًا عشوائيًّا، وذاك أسوأ من عطبٍ يُرى.
        raise MultipleResultsFound(
            f"project {project_id} has {len(memberships)} membership rows "
            f"for one user — the answer would be arbitrary")

    if not memberships:
        # لا صفَّ عضويّةٍ بهذا البحث لهذا الباحث — فالملكيّةُ وحدها تقرّر.
        keys = _decide(is_owner=is_owner, access_state=None, keys=frozenset())
    else:
        _p, _o, _mid, access_state, granted = memberships[0]
        # و`array_agg` على وصلةٍ بلا مطابقاتٍ تُعيد `[None]` لا `[]`.
        keys = _decide(
            is_owner=is_owner, access_state=access_state,
            keys=frozenset(k for k in (granted or ()) if k is not None))
    if keys is None:
        raise NotFound(not_found_code)

    # **والنسبُ فوق كلّ صفّ** حيث يُطلب: دورةُ حياة البحث لصاحبه وحده، ولا
    # صفَّ يُقرأ لها. و٤٠٣ لا ٤٠٤ هنا: الطالبُ عضوٌ يعرف البحث سلفًا، فإنكارُ
    # وجوده كذبٌ لا يحمي شيئًا — والصدقُ يقول له إنّ الفعل ليس له.
    if require_owner and not is_owner:
        raise Forbidden(OWNER_ONLY, project_id=str(project_id))

    if permission not in keys:
        raise Forbidden("team.permission_required", permission=permission,
                        project_id=str(project_id))
    return ProjectAccess(project=project, permissions=keys, is_owner=is_owner)
