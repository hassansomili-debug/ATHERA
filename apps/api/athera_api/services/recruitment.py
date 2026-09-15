"""اختيارُ المتعاون | RC-T1C: application → exact invitation → membership.

**العقدُ الذي تحمله هذه الوحدة، وهو أهمُّ ما في المرحلة.**

    تطبيقُ «أ» لحسابِ «أ» على فرصةٍ في بحثِ «س»
    ⇒ دعوةٌ في بحثِ «س» **لحسابِ «أ» بعينه**
    ⇒ ثمّ يقبلها «أ» بنفسه
    ⇒ ثمّ تُنشأ العضويّة

ودعوةٌ صحيحةٌ حيّةٌ **لمرشَّحٍ آخر** لا تُشبع تطبيقَ «أ». ودعوةٌ لحسابِ
«أ» في **بحثٍ آخر** لا تُشبعه كذلك. وذاك ما كان ناقصًا في RC-T1B صريحًا،
ويُغلق هنا.

## ولمَ هويّةُ المرشَّح لا تُقبل من المدير

يُعطي المديرُ ثلاثةَ أشياء: **أيَّ تطبيقٍ اختار**، وأيَّ دورٍ حقيقيٍّ من
مفردات العضويّة، وأيَّ صلاحياتٍ صريحة. ولا يُعطي هويّةَ من يُدعى.

فلو قُبلت منه — ولو حسنَ النيّة — لصار الاختيارُ قابلًا للتحويل: يُرشَّح
باحثٌ ويُدعى غيرُه، ولا يظهر ذلك في شيء. فالهويّةُ تُشتقّ من
`RecruitmentApplication.applicant_user_id`، والبحثُ من فرصته، والمستأجرُ
من نسبها — كلُّها في الخادم.

## ولا محرّكَ دعواتٍ ثانٍ

تُستعمل `ProjectInvitation` القائمة بتجزئة رمزها وأحداثها وتدقيقها. وما
أُضيف إليها مُعامِلٌ واحد: `invited_user_id` ربطًا صريحًا يُغني عن
الترشيح بالبريد — لأنّ الترشيحَ بالبريد **محكومٌ بمستأجر البحث**،
والمتقدّمُ من مؤسسةٍ أخرى قصدًا.

## والشواغرُ تُحسب بقفلٍ لا بعدّادٍ في الشاشة

مديرانِ يختاران آخرَ شاغرٍ في اللحظة نفسها: يُقفل صفُّ النسب، وتُحسب
الشواغرُ المشغولة، فينجح أحدُهما ويُردّ الآخرُ بتعارضٍ صادق.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, Forbidden, NotFound
from ..models.collaboration import ProjectInvitation
from ..models.identity import User
from ..models.recruitment import (
    RecruitmentApplication,
    RecruitmentOpportunity,
    RecruitmentOpportunityListing,
)
from . import audit, collaboration, team

APPLICATION_OBJECT_TYPE = "recruitment_application"

#: ما يُعَدّ شاغرًا مشغولًا — دعوةٌ حيّةٌ أو عضويّةٌ قامت عنها.
#:
#: والمنقوضةُ والمنتهيةُ والمرفوضةُ لا تشغل شاغرًا إلى الأبد: فرصةٌ
#: بشاغرَين يعتذر عنها مرشَّحانِ تبقى مغلقةً بلا سبب.
OCCUPYING_INVITATION_STATES: tuple[str, ...] = ("invited", "accepted")


@dataclass(frozen=True, slots=True)
class Selection:
    """نتيجةُ الاختيار — والرمزُ يُعاد مرّةً واحدةً إلى مُصدِره."""

    application: RecruitmentApplication
    invitation: ProjectInvitation
    token: str


async def _application_for_manager(
    session: AsyncSession, *, application_id: uuid.UUID,
) -> tuple[RecruitmentApplication, RecruitmentOpportunity]:
    """التطبيقُ ونسبُ فرصته — **ويُقفلان** قبل أيّ قرار.

    و`404` لا `403` لمن لا يديره: سياسةُ القراءة لا تُسلّمه الصفَّ أصلًا،
    فالمعدومُ وغيرُ المأذون يُجابان جوابًا واحدًا.
    """
    application = (await session.execute(
        select(RecruitmentApplication)
        .where(RecruitmentApplication.id == application_id)
        .with_for_update())).scalar_one_or_none()
    if application is None:
        raise NotFound("recruitment.application_not_found")

    # **ولا قفلَ على صفّ النسب**: 0034 جعله يُكتب مرّةً ولا يُعدَّل، فلا
    # صلاحيةَ تعديلٍ عليه — و`FOR UPDATE` تشترطها. والقفلُ الذي يلزم
    # للشواغر محلُّه صفُّ الإعلان، وهو يُقفل أدناه.
    owner_row = (await session.execute(
        select(RecruitmentOpportunity)
        .where(RecruitmentOpportunity.id == application.opportunity_id))
    ).scalar_one_or_none()
    if owner_row is None:
        raise NotFound("recruitment.application_not_found")
    return application, owner_row


async def _occupied_slots(
    session: AsyncSession, *, opportunity_id: uuid.UUID,
) -> int:
    """كم شاغرًا شُغل فعلًا — بدعوةٍ حيّةٍ أو عضويّةٍ قامت عنها."""
    return (await session.execute(
        select(func.count())
        .select_from(RecruitmentApplication)
        .join(ProjectInvitation,
              ProjectInvitation.id == RecruitmentApplication.invitation_id)
        .where(RecruitmentApplication.opportunity_id == opportunity_id,
               ProjectInvitation.state.in_(OCCUPYING_INVITATION_STATES)))).scalar_one()


async def invite_applicant(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    role: str,
    permissions: list[str],
    ttl_hours: int | None = None,
) -> Selection:
    """يُختار متقدّمٌ مُرشَّح، فتُصدر له دعوةٌ **باسمه هو**.

    ولا شيءَ في هذه الدالّة يقرأ هويّةَ المرشَّح من مُعامِل: تُشتقّ من
    صفّ التطبيق. ومن أراد أن يدعو حسابًا بعينه يستعمل دعواتَ الفريق
    القائمة، لا هذا الباب.

    ## وترتيبُ الإثبات مقصود

    يُقفل الصفّان أوّلًا، ثمّ تُثبت سلطةُ المدير، ثمّ حالُ التطبيق، ثمّ
    الشواغر — فلا قرارٌ يُبنى على قراءةٍ قد تتغيّر تحته.

    ## والتكرارُ لا يُنتج دعوتَين

    ونقرةٌ مزدوجة، أو مديرانِ في اللحظة نفسها: الصفُّ مقفول، ومن وجد
    التطبيقَ مربوطًا بدعوةٍ حيّةٍ **أُعيدت له هي** ولا تُصنع ثانية.
    والفهرسُ الفريدُ على `invitation_id` حزامٌ تحت ذلك.
    """
    application, owner_row = await _application_for_manager(
        session, application_id=application_id)

    # ١ · سلطةُ المدير — مالكٌ مُثبت، أو عضوٌ نشِطٌ له تفويضُ الفريق.
    #     ولا دورَ يُفسَّر: `manage_team` صفٌّ صريح.
    await collaboration.ensure_project_access(
        session, tenant_id=owner_row.tenant_id, project_id=owner_row.project_id,
        user_id=actor_user_id, permission="manage_team",
        not_found_code="recruitment.application_not_found")

    # ٢ · وإن كان مربوطًا بدعوةٍ حيّةٍ فذاك جوابُه — لا دعوةٌ ثانية.
    if application.invitation_id is not None:
        existing = (await session.execute(
            select(ProjectInvitation)
            .where(ProjectInvitation.id == application.invitation_id))
        ).scalar_one_or_none()
        if existing is not None and existing.state == "invited":
            raise AtheraError("recruitment.already_invited", status_code=409,
                              invitation_id=str(existing.id))

    # ٣ · والاختيارُ يقع على مُرشَّحٍ لا على من لم يُرشَّح بعد.
    if application.status != "shortlisted":
        raise AtheraError("recruitment.not_shortlisted", status_code=409,
                          status=application.status)

    # ٤ · والدورُ والصلاحياتُ من مفردات المستودع، لا من وسمِ الإعلان.
    if role not in team.MEMBER_ROLES:
        raise AtheraError("team.unknown_member_role", status_code=422, role=role)
    try:
        team.validate_permissions(list(permissions))
    except team.TeamError as exc:
        raise AtheraError("team.invalid_invitation", status_code=422,
                          detail=str(exc)) from exc
    if collaboration.VIEW_PROJECT not in permissions:
        # وأساسُ الرؤية شرطٌ في الجسر نفسِه، فدعوةٌ بلا أساسٍ تُنتج عضوًا
        # يرى بحثَه في «أبحاثي» ولا يقدر على فتحه.
        raise AtheraError("team.invalid_invitation", status_code=422,
                          detail=collaboration.VIEW_PROJECT)

    # ٥ · والشواغرُ تُحسب بعد القفل.
    # ويُقفل صفُّ الإعلان: مديرانِ يختاران آخرَ شاغرٍ معًا، فينجح أحدُهما.
    listing = (await session.execute(
        select(RecruitmentOpportunityListing)
        .where(RecruitmentOpportunityListing.opportunity_id == owner_row.id)
        .with_for_update())).scalar_one_or_none()
    if listing is None:
        raise NotFound("recruitment.application_not_found")
    if await _occupied_slots(session, opportunity_id=owner_row.id) >= \
            listing.openings_count:
        raise AtheraError("recruitment.openings_filled", status_code=409,
                          openings_count=listing.openings_count)

    # ٦ · وبريدُ المتقدّم يُقرأ في الخادم من حسابه — لا يُكتب في طلب.
    applicant_email = (await session.execute(
        select(User.email).where(User.id == application.applicant_user_id))
    ).scalar_one_or_none()
    if applicant_email is None:
        raise AtheraError("recruitment.applicant_unavailable", status_code=409)

    issued = await collaboration.invite_member(
        session, tenant_id=owner_row.tenant_id, project_id=owner_row.project_id,
        inviter_user_id=actor_user_id, email=applicant_email,
        display_name=team.normalize_email(applicant_email).split("@")[0],
        role=role, permissions=list(permissions), ttl_hours=ttl_hours,
        # **الربطُ هنا** — ومصدرُه صفُّ التطبيق لا مُعامِلٌ من عميل.
        invited_user_id=application.applicant_user_id,
    )

    application.invitation_id = issued.invitation.id
    application.status = "invited"
    application.decided_at = collaboration._now()
    application.decided_by = actor_user_id
    # والمُشغِّلُ على القاعدة يُعيد إثباتَ الربط كلِّه عند هذه الكتابة:
    # البحثَ، والحسابَ، وحالَ الدعوة، ومهلتَها. فلو أخطأت هذه الدالّةُ
    # سطرًا لَما مرّت الكتابة.
    await session.flush()

    await audit.record(
        session, tenant_id=owner_row.tenant_id,
        action="recruitment.applicant_invited",
        object_type=APPLICATION_OBJECT_TYPE, object_id=application.id,
        actor_user_id=actor_user_id,
        state_after={"invitation_id": str(issued.invitation.id),
                     "project_id": str(owner_row.project_id),
                     "proposed_role": role,
                     "proposed_permissions": sorted(permissions)},
        reason="a selected applicant is invited by their own account identity, "
               "never by an identity supplied in the request",
    )
    return Selection(application=application, invitation=issued.invitation,
                     token=issued.token)


async def withdraw_application(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> RecruitmentApplication:
    """ينسحب المتقدّمُ بنفسه — **وتسقط دعوتُه المعلَّقة معه**.

    ولو بقيت الدعوةُ حيّةً بعد الانسحاب لبقي رمزُها صالحًا: فينسحب باحثٌ
    ثمّ يجد نفسَه عضوًا، أو يُقبل رمزٌ تخلّى صاحبُه عنه.
    """
    application = (await session.execute(
        select(RecruitmentApplication)
        .where(RecruitmentApplication.id == application_id)
        .with_for_update())).scalar_one_or_none()
    if application is None:
        raise NotFound("recruitment.application_not_found")
    if application.applicant_user_id != actor_user_id:
        raise Forbidden("recruitment.not_your_application")

    if application.invitation_id is not None:
        invitation = (await session.execute(
            select(ProjectInvitation)
            .where(ProjectInvitation.id == application.invitation_id)
            .with_for_update())).scalar_one_or_none()
        if invitation is not None and invitation.state == "invited":
            # **و«معتذَرٌ عنها» لا «منقوضة».**
            #
            # فالنقضُ فعلُ المدير، والاعتذارُ فعلُ المدعوّ — ومُشغِّلُ
            # الدعوات يفصل بينهما: من دُعي يقبل أو يعتذر ولا ينقض. ومن
            # انسحب فقد اعتذر عن دعوته، وكلتا الحالَين تُميت الرمز.
            invitation.state = "declined"
            invitation.responded_at = collaboration._now()
            await session.flush()

    application.status = "withdrawn"
    application.withdrawn_at = collaboration._now()
    await session.flush()
    return application


__all__ = [
    "APPLICATION_OBJECT_TYPE",
    "OCCUPYING_INVITATION_STATES",
    "Selection",
    "invite_applicant",
    "withdraw_application",
]


# ═══════════════════ الإعلانُ: حالُه وحياتُه ═══════════════════

#: الحقولُ الجوهريّة — تُجمَّد بعد أوّل تقدُّم.
#:
#: **ولمَ تُجمَّد.** من تقدّم قرأ عنوانًا ووصفًا ومهامَّ ومتطلّباتٍ وبدايةً،
#: وبنى قرارَه عليها. فتعديلُها بعده يجعله متقدّمًا إلى شيءٍ لم يره —
#: و«أُعلن عن مساعدةٍ في المراجعة فصار جمعَ بيانات» شكوى حقيقيّة.
SUBSTANTIVE_FIELDS: tuple[str, ...] = (
    "title", "description", "contributions", "requirements",
    "specialization", "collaboration_type", "starts_at",
)

#: وما يبقى مسموحًا بعده: تمديدُ الأجل، وزيادةُ الشواغر، والإغلاق، والحذف.
OPERATIONAL_FIELDS: tuple[str, ...] = ("ends_at", "openings_count", "public_label")


def effective_status(listing: RecruitmentOpportunityListing,
                     now: dt.datetime | None = None) -> str:
    """الحالُ كما يراها إنسان — **مشتقّةٌ من الزمن لا مخزَّنة**.

    **ولا مُجدوِلَ في الخلفيّة لهذه النسخة.** فالإعلانُ يُنشر بحالٍ
    مخزَّنةٍ `open` ونافذةٍ قد تبدأ غدًا: فيُعرض «مجدول» ولا يُكتشف، ثمّ
    **يُكتشف من نفسه** متى بلغ `starts_at` — لأنّ شرطَ الاكتشاف يقرأ
    الزمنَ في كلّ استعلام.

    ولو خُزّنت `scheduled` حالًا حقيقيّةً لَاحتاجت من يقلبها إلى `open`،
    فتبقى مغلقةً إلى الأبد بلا مُجدوِل. فالمفردةُ باقيةٌ في المخطَّط ولا
    يكتبها النشرُ.
    """
    now = now or collaboration._now()
    if listing.deleted_at is not None:
        return "deleted"
    if listing.status in ("draft", "closed", "deleted", "scheduled"):
        return listing.status
    if listing.starts_at is None:
        return "draft"
    if listing.starts_at > now:
        return "scheduled"
    if listing.ends_at is not None and listing.ends_at <= now:
        return "expired"
    return "open"


async def _manager_context(
    session: AsyncSession, *, project_id: uuid.UUID, tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    """سلطةُ إدارة الفريق على هذا البحث — أو ٤٠٤ يُخفيه."""
    await collaboration.ensure_project_access(
        session, tenant_id=tenant_id, project_id=project_id,
        user_id=actor_user_id, permission="manage_team",
        not_found_code="recruitment.opportunity_not_found")


async def _listing_for_manager(
    session: AsyncSession, *, project_id: uuid.UUID, tenant_id: uuid.UUID,
    opportunity_id: uuid.UUID, lock: bool = False,
) -> tuple[RecruitmentOpportunity, RecruitmentOpportunityListing]:
    owner_row = (await session.execute(
        select(RecruitmentOpportunity).where(
            RecruitmentOpportunity.id == opportunity_id,
            RecruitmentOpportunity.project_id == project_id,
            RecruitmentOpportunity.tenant_id == tenant_id))).scalar_one_or_none()
    if owner_row is None:
        raise NotFound("recruitment.opportunity_not_found")
    statement = select(RecruitmentOpportunityListing).where(
        RecruitmentOpportunityListing.opportunity_id == opportunity_id)
    if lock:
        statement = statement.with_for_update()
    listing = (await session.execute(statement)).scalar_one_or_none()
    if listing is None:
        raise NotFound("recruitment.opportunity_not_found")
    return owner_row, listing


async def applications_count(session: AsyncSession, *,
                             opportunity_id: uuid.UUID) -> int:
    return (await session.execute(
        select(func.count()).select_from(RecruitmentApplication)
        .where(RecruitmentApplication.opportunity_id == opportunity_id))).scalar_one()


async def create_opportunity(
    session: AsyncSession, *, project_id: uuid.UUID, tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID, fields: dict,
) -> tuple[RecruitmentOpportunity, RecruitmentOpportunityListing]:
    """إعلانٌ يُولد **مسوّدةً** — فلا شيءَ يُنشر بمجرّد كتابته."""
    await _manager_context(session, project_id=project_id, tenant_id=tenant_id,
                           actor_user_id=actor_user_id)
    owner_row = RecruitmentOpportunity(
        tenant_id=tenant_id, project_id=project_id, created_by=actor_user_id)
    session.add(owner_row)
    await session.flush()
    listing = RecruitmentOpportunityListing(
        opportunity_id=owner_row.id, status="draft", **fields)
    session.add(listing)
    await session.flush()
    await audit.record(
        session, tenant_id=tenant_id, action="recruitment.opportunity_created",
        object_type="recruitment_opportunity", object_id=owner_row.id,
        actor_user_id=actor_user_id,
        state_after={"project_id": str(project_id), "status": "draft"},
        reason="an opportunity is born a draft; publication is a separate act")
    return owner_row, listing


async def patch_opportunity(
    session: AsyncSession, *, project_id: uuid.UUID, tenant_id: uuid.UUID,
    opportunity_id: uuid.UUID, actor_user_id: uuid.UUID, changes: dict,
) -> RecruitmentOpportunityListing:
    """تعديلٌ — **ويُجمَّد الجوهريُّ بعد أوّل تقدُّم**."""
    await _manager_context(session, project_id=project_id, tenant_id=tenant_id,
                           actor_user_id=actor_user_id)
    _owner, listing = await _listing_for_manager(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id, lock=True)
    if listing.deleted_at is not None:
        raise AtheraError("recruitment.opportunity_deleted", status_code=409)

    already = await applications_count(session, opportunity_id=opportunity_id)
    if already:
        touched = [name for name in SUBSTANTIVE_FIELDS
                   if name in changes
                   and changes[name] is not None
                   and changes[name] != getattr(listing, name)]
        if touched:
            raise AtheraError("recruitment.substantive_edit_after_application",
                              status_code=409, fields=sorted(touched))

    if "openings_count" in changes and changes["openings_count"] is not None:
        occupied = await _occupied_slots(session, opportunity_id=opportunity_id)
        if changes["openings_count"] < occupied:
            raise AtheraError("recruitment.openings_below_selected",
                              status_code=409, occupied=occupied)

    for name, value in changes.items():
        if value is not None:
            setattr(listing, name, value)
    await session.flush()
    await audit.record(
        session, tenant_id=tenant_id, action="recruitment.opportunity_edited",
        object_type="recruitment_opportunity", object_id=opportunity_id,
        actor_user_id=actor_user_id,
        state_after={"fields": sorted(k for k, v in changes.items() if v is not None)},
        reason="an applicant applied to what they read; substantive text freezes")
    return listing


async def set_lifecycle(
    session: AsyncSession, *, project_id: uuid.UUID, tenant_id: uuid.UUID,
    opportunity_id: uuid.UUID, actor_user_id: uuid.UUID, action: str,
) -> RecruitmentOpportunityListing:
    """نشرٌ أو إغلاقٌ أو حذفٌ ناعم — وثلاثتُها كتابةُ حالٍ لا إتلاف."""
    await _manager_context(session, project_id=project_id, tenant_id=tenant_id,
                           actor_user_id=actor_user_id)
    _owner, listing = await _listing_for_manager(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id, lock=True)
    if listing.deleted_at is not None:
        raise AtheraError("recruitment.opportunity_deleted", status_code=409)

    if action == "publish":
        # **والنشرُ يُثبت ما يُقرأ** — فإعلانٌ بلا عنوانٍ أو وصفٍ يُنشر
        # يصل الاكتشافَ فارغًا، ولا يُفهم منه شيء.
        if not (listing.title or "").strip() or not (listing.description or "").strip():
            raise AtheraError("recruitment.incomplete_opportunity", status_code=422)
        if listing.openings_count < 1:
            raise AtheraError("recruitment.incomplete_opportunity", status_code=422)
        if listing.starts_at is None:
            listing.starts_at = collaboration._now()
        if listing.ends_at is not None and listing.starts_at >= listing.ends_at:
            raise AtheraError("recruitment.invalid_window", status_code=422)
        # **`open` دائمًا، ولو كانت البدايةُ غدًا.** فالنافذةُ تُقرأ في كلّ
        # استعلام، فيُكتشف من نفسه متى بلغ أجلَه — ولا مُجدوِلَ يلزم.
        listing.status = "open"
    elif action == "close":
        listing.status = "closed"
    elif action == "delete":
        listing.status = "deleted"
        listing.deleted_at = collaboration._now()
    else:  # pragma: no cover - المفرداتُ مغلقةٌ في الموجّه
        raise AtheraError("recruitment.unknown_action", status_code=422, action=action)

    await session.flush()
    await audit.record(
        session, tenant_id=tenant_id,
        action=f"recruitment.opportunity_{action}ed"
               if action != "publish" else "recruitment.opportunity_published",
        object_type="recruitment_opportunity", object_id=opportunity_id,
        actor_user_id=actor_user_id,
        state_after={"status": listing.status},
        reason="deleting an opportunity hides it; the applications it received remain")
    return listing


# ═══════════════════ التقدّمُ والاختيار ═══════════════════


async def submit_application(
    session: AsyncSession, *, opportunity_id: uuid.UUID,
    applicant_user_id: uuid.UUID, applicant_tenant_id: uuid.UUID,
    message: str | None,
) -> RecruitmentApplication:
    """تقدُّمٌ — **وهويّةُ المتقدّم من رمزه الموقَّع لا من طلبه**.

    ولا يُسأل هنا عن حالِ الإعلان: سياسةُ الإدراج في القاعدة تشترط بابًا
    مفتوحًا الآن (`app_opportunity_admits`)، والفهرسُ الجزئيُّ يمنع
    تقدُّمًا قائمًا ثانيًا. **فالحدُّ عند القاعدة لا عند الموجّه.**
    """
    row = RecruitmentApplication(
        opportunity_id=opportunity_id, applicant_user_id=applicant_user_id,
        applicant_tenant_id=applicant_tenant_id, status="pending", message=message)
    session.add(row)
    await session.flush()
    return row


async def decide_application(
    session: AsyncSession, *, application_id: uuid.UUID, actor_user_id: uuid.UUID,
    decision: str,
) -> RecruitmentApplication:
    """ترشيحٌ أو اعتذار — والمصفوفةُ على القاعدة تقبل أو تردّ."""
    application, owner_row = await _application_for_manager(
        session, application_id=application_id)
    await collaboration.ensure_project_access(
        session, tenant_id=owner_row.tenant_id, project_id=owner_row.project_id,
        user_id=actor_user_id, permission="manage_team",
        not_found_code="recruitment.application_not_found")

    application.status = decision
    application.decided_at = collaboration._now()
    application.decided_by = actor_user_id
    await session.flush()
    await audit.record(
        session, tenant_id=owner_row.tenant_id,
        action=f"recruitment.applicant_{decision}",
        object_type=APPLICATION_OBJECT_TYPE, object_id=application.id,
        actor_user_id=actor_user_id, state_after={"status": decision},
        reason="a decision about an applicant names the manager who made it")
    return application


def invitation_view(invitation: ProjectInvitation | None) -> dict | None:
    """حالُ الدعوة **صادقةً**: صلاحيتُها محسوبةٌ لا مستنتَجةٌ من حال التطبيق.

    فحالُ التطبيق تبقى «مدعوّ» تاريخًا، والدعوةُ قد تكون انقضت أو نُقضت
    أو قُبلت. فعرضُها «قابلةٌ للاستعمال» لأنّ التطبيق يقول مدعوّ **كذبٌ
    مريح**: يفتح الباحثُ الرابطَ فيُردّ ولا يفهم لماذا.
    """
    if invitation is None:
        return None
    usable = (invitation.state == "invited"
              and invitation.expires_at > collaboration._now())
    return {
        "invitation_id": invitation.id,
        "state": invitation.state,
        "usable": usable,
        "expires_at": invitation.expires_at,
        "membership_created": invitation.member_id is not None,
    }
