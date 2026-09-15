"""الفرصُ البحثية | RC-T1C recruitment HTTP surface.

**ثلاثةُ أسطحٍ في موجّهٍ واحد، وحدُّ كلٍّ منها مختلف:**

  • **الاكتشافُ العالميّ** — باحثٌ مصادَقٌ في أيّ مؤسسة. ويُجاب بإسقاطٍ
    آمنٍ **لا يملك** معرّفَ بحثٍ ولا مستأجرٍ ولا منشئ: `PublicOpportunity`
    نموذجٌ منفصلٌ بنيويًّا، فإضافةُ عمودٍ للمدير غدًا لا تخرج إلى العالَم.
  • **إدارةُ الإعلان** — بجلسةِ بحثٍ (`get_project_session`) وبتفويضِ
    `manage_team`. والمستأجرُ يُقرأ من الجلسة بعد العبور لا من الرمز.
  • **التقدّمُ والاختيار** — المتقدّمُ يُشتقّ من رمزه الموقَّع، والمرشَّحُ
    يُشتقّ من صفّ التطبيق. **ولا هويّةَ تُقبل في جسم طلب.**

## وما لا يُكتب هنا

لا سطرَ في هذا الموجّه يُنشئ عضويّةً: الاختيارُ يُصدر `ProjectInvitation`
بخدمة التحويل، والعضويّةُ لا تُنشأ إلّا بقبولٍ شخصيّ عبر
`/api/v1/invitations/accept`.

ولا مفرداتَ توظيف: «مساعد بحث» وسمُ تعاونٍ لا دورَ عضوية.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import invitation_session, scoped_tenant, tenant_session
from ..deps import Principal, get_principal, get_project_session, get_session
from ..errors import AtheraError, NotFound
from ..models.collaboration import ProjectInvitation
from ..models.identity import User
from ..models.recruitment import (
    RecruitmentApplication,
    RecruitmentOpportunity,
    RecruitmentOpportunityListing,
)
from ..schemas.recruitment import (
    ApplicationCreateRequest,
    InviteRequest,
    LinkedInvitation,
    ManagerApplication,
    ManagerOpportunity,
    MyApplication,
    OpportunityCreateRequest,
    OpportunityPatchRequest,
    PublicOpportunity,
    RecruitmentInvitationResponse,
)
from ..services import collaboration, recruitment

router = APIRouter(prefix="/api/v1/recruitment", tags=["recruitment"])


def _tenant(session: AsyncSession, principal: Principal) -> uuid.UUID:
    """المستأجرُ النافذُ لهذه المعاملة — وهو دائمًا معروف.

    و`scoped_tenant` تقبل غيابَه لأنّ جلسةً بلا سياقٍ ممكنةٌ في مسارات
    ما قبل المصادقة. وهذا الموجّهُ لا يُفتح إلّا برمزٍ موقَّع، فالمستأجرُ
    الأصليُّ حاضرٌ دائمًا — ويُقال ذلك في النوع لا يُترك ظنًّا.
    """
    return scoped_tenant(session, principal.tenant_id) or principal.tenant_id


async def _gate(session: AsyncSession, principal: Principal, project_id: uuid.UUID,
                *, permission: str = "manage_team"):
    """بوابةُ البحث — **والنداءُ صريحٌ في هذا الموجّه كما في أخواته**.

    وعقدُ RC-T1A يقرأ الموجّهاتَ تحليلًا ساكنًا ويتبع النداءَ داخل الوحدة
    بنقطةٍ ثابتة؛ ولا يعبُر إلى الخدمات. فمسارٌ يُفوّض عبر مُساعِدٍ في
    وحدةٍ أخرى **يبدو له ثغرةً** — وهو ما وقع. فتُنادى البوابةُ هنا.

    والمستأجرُ يُقرأ من الجلسة لا من الرمز: بعد عبور جسر البحث لم يعد
    مستأجرُ الرمز هو مستأجرَ المعاملة.
    """
    return await collaboration.ensure_project_access(
        session, tenant_id=_tenant(session, principal),
        project_id=project_id, user_id=principal.user_id, permission=permission,
        not_found_code="recruitment.opportunity_not_found")


def _linked(invitation: ProjectInvitation | None) -> LinkedInvitation | None:
    view = recruitment.invitation_view(invitation)
    return None if view is None else LinkedInvitation(**view)


def _public(listing: RecruitmentOpportunityListing) -> PublicOpportunity:
    return PublicOpportunity(
        opportunity_id=listing.opportunity_id, title=listing.title,
        description=listing.description, contributions=listing.contributions,
        requirements=listing.requirements, specialization=listing.specialization,
        openings_count=listing.openings_count,
        collaboration_type=listing.collaboration_type,
        public_label=listing.public_label, starts_at=listing.starts_at,
        ends_at=listing.ends_at,
        effective_status=recruitment.effective_status(listing))


def _manager(listing: RecruitmentOpportunityListing, *,
             applications: int) -> ManagerOpportunity:
    return ManagerOpportunity(
        **_public(listing).model_dump(), stored_status=listing.status,
        deleted_at=listing.deleted_at, applications_count=applications,
        created_at=listing.created_at)


# ═══════════════════ الاكتشافُ العالميّ ═══════════════════


@router.get("/opportunities", response_model=list[PublicOpportunity])
async def discover(
    session: AsyncSession = Depends(get_session),
) -> list[PublicOpportunity]:
    """ما يُكتشف الآن — **والقاعدةُ هي التي ترشّح**.

    ولا شرطَ مكتوبٌ هنا: سياسةُ الاكتشاف على جدول الإعلانات لا تُسلّم إلّا
    المفتوحَ داخل نافذته. فمسوّدةٌ ومجدولةٌ ومغلقةٌ ومحذوفةٌ ومنقضيةٌ لا
    تصل هذه الدالّةَ أصلًا — ولو نُسي شرطٌ في موجّهٍ ما.
    """
    rows = (await session.execute(
        select(RecruitmentOpportunityListing)
        .order_by(RecruitmentOpportunityListing.created_at.desc())
        .limit(200))).scalars().all()
    return [_public(row) for row in rows]


@router.get("/opportunities/{opportunity_id}", response_model=PublicOpportunity)
async def discover_one(
    opportunity_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> PublicOpportunity:
    """وما لا يُكتشف يُجاب جوابَ المعدوم — لا «موجودٌ ولا يُعرض»."""
    row = (await session.execute(
        select(RecruitmentOpportunityListing).where(
            RecruitmentOpportunityListing.opportunity_id == opportunity_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("recruitment.opportunity_not_found")
    return _public(row)


# ═══════════════════ إدارةُ الإعلان ═══════════════════


@router.get("/projects/{project_id}/opportunities",
            response_model=list[ManagerOpportunity])
async def list_project_opportunities(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> list[ManagerOpportunity]:
    await _gate(session, principal, project_id)
    rows = (await session.execute(
        select(RecruitmentOpportunityListing, RecruitmentOpportunity.id)
        .join(RecruitmentOpportunity,
              RecruitmentOpportunity.id
              == RecruitmentOpportunityListing.opportunity_id)
        .where(RecruitmentOpportunity.project_id == project_id)
        .order_by(RecruitmentOpportunityListing.created_at.desc()))).all()
    out = []
    for listing, _ in rows:
        count = await recruitment.applications_count(
            session, opportunity_id=listing.opportunity_id)
        out.append(_manager(listing, applications=count))
    return out


@router.post("/projects/{project_id}/opportunities",
             response_model=ManagerOpportunity,
             status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    project_id: uuid.UUID,
    payload: OpportunityCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    await _gate(session, principal, project_id)
    tenant_id = _tenant(session, principal)
    _owner, listing = await recruitment.create_opportunity(
        session, project_id=project_id, tenant_id=tenant_id,
        actor_user_id=principal.user_id, fields=payload.model_dump())
    return _manager(listing, applications=0)


@router.get("/projects/{project_id}/opportunities/{opportunity_id}",
            response_model=ManagerOpportunity)
async def get_project_opportunity(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    tenant_id = _tenant(session, principal)
    await _gate(session, principal, project_id)
    _owner, listing = await recruitment._listing_for_manager(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id)
    count = await recruitment.applications_count(
        session, opportunity_id=opportunity_id)
    return _manager(listing, applications=count)


@router.patch("/projects/{project_id}/opportunities/{opportunity_id}",
              response_model=ManagerOpportunity)
async def patch_opportunity(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    payload: OpportunityPatchRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    await _gate(session, principal, project_id)
    tenant_id = _tenant(session, principal)
    listing = await recruitment.patch_opportunity(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id, actor_user_id=principal.user_id,
        changes=payload.model_dump(exclude_unset=True))
    count = await recruitment.applications_count(
        session, opportunity_id=opportunity_id)
    return _manager(listing, applications=count)


async def _lifecycle(project_id, opportunity_id, principal, session, action):
    await _gate(session, principal, project_id)
    tenant_id = _tenant(session, principal)
    listing = await recruitment.set_lifecycle(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id, actor_user_id=principal.user_id,
        action=action)
    count = await recruitment.applications_count(
        session, opportunity_id=opportunity_id)
    return _manager(listing, applications=count)


@router.post("/projects/{project_id}/opportunities/{opportunity_id}/publish",
             response_model=ManagerOpportunity)
async def publish_opportunity(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    return await _lifecycle(project_id, opportunity_id, principal, session, "publish")


@router.post("/projects/{project_id}/opportunities/{opportunity_id}/close",
             response_model=ManagerOpportunity)
async def close_opportunity(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    return await _lifecycle(project_id, opportunity_id, principal, session, "close")


@router.delete("/projects/{project_id}/opportunities/{opportunity_id}",
               response_model=ManagerOpportunity)
async def delete_opportunity(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> ManagerOpportunity:
    """**حذفٌ ناعمٌ لا إتلاف.** فمن تقدّم يبقى تقدُّمُه، ودعوتُه، وعضويّتُه."""
    return await _lifecycle(project_id, opportunity_id, principal, session, "delete")


# ═══════════════════ التقدّم ═══════════════════


@router.post("/opportunities/{opportunity_id}/applications",
             response_model=MyApplication, status_code=status.HTTP_201_CREATED)
async def apply(
    opportunity_id: uuid.UUID,
    payload: ApplicationCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MyApplication:
    """تقدُّمٌ — **وهويّةُ المتقدّم من رمزه لا من جسم طلبه**.

    ولا شرطَ حالٍ مكتوبٌ هنا: سياسةُ الإدراج تشترط بابًا مفتوحًا الآن،
    والفهرسُ الجزئيُّ يمنع تقدُّمًا قائمًا ثانيًا. فبابٌ مغلقٌ يُجاب
    بـ٤٠٤، وتكرارٌ بـ٤٠٩ — وكلاهما من القاعدة.
    """
    listing = (await session.execute(
        select(RecruitmentOpportunityListing).where(
            RecruitmentOpportunityListing.opportunity_id == opportunity_id))
    ).scalar_one_or_none()
    if listing is None:
        raise NotFound("recruitment.opportunity_not_found")
    try:
        row = await recruitment.submit_application(
            session, opportunity_id=opportunity_id,
            applicant_user_id=principal.user_id,
            applicant_tenant_id=principal.tenant_id, message=payload.message)
    except IntegrityError as exc:
        # **والتكرارُ تعارضٌ صادقٌ لا خطأُ خادم.** والفهرسُ الجزئيُّ هو
        # الذي يرفض — فطلبانِ متزامنان يسقط أحدُهما عند المحرّك لا عند
        # فحصٍ سبق الكتابة.
        if "uq_recruitment_applications_active" in str(exc):
            raise AtheraError("recruitment.already_applied",
                              status_code=409) from exc
        raise
    return MyApplication(
        application_id=row.id, opportunity_id=opportunity_id,
        title=listing.title, status=row.status, message=row.message,
        submitted_at=row.created_at, decided_at=row.decided_at, invitation=None)


@router.get("/applications/me", response_model=list[MyApplication])
async def my_applications(
    session: AsyncSession = Depends(get_session),
) -> list[MyApplication]:
    """تقدُّماتي وحدها — وسياسةُ «تقدُّمي» في القاعدة هي التي ترشّح.

    والدعوةُ المرتبطةُ تُعرض **بصلاحيةٍ محسوبة**: حالُ التطبيق تبقى
    «مدعوّ» تاريخًا، والدعوةُ قد انقضت أو نُقضت أو قُبلت.
    """
    rows = (await session.execute(
        select(RecruitmentApplication, RecruitmentOpportunityListing.title,
               ProjectInvitation)
        .join(RecruitmentOpportunityListing,
              RecruitmentOpportunityListing.opportunity_id
              == RecruitmentApplication.opportunity_id, isouter=True)
        .join(ProjectInvitation,
              ProjectInvitation.id == RecruitmentApplication.invitation_id,
              isouter=True)
        .order_by(RecruitmentApplication.created_at.desc()))).all()
    return [
        MyApplication(
            application_id=app.id, opportunity_id=app.opportunity_id,
            title=title or "", status=app.status, message=app.message,
            submitted_at=app.created_at, decided_at=app.decided_at,
            invitation=_linked(invitation))
        for app, title, invitation in rows
    ]


@router.post("/applications/{application_id}/withdraw",
             response_model=MyApplication)
async def withdraw(
    application_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> MyApplication:
    """انسحابٌ — **ويُسقط الدعوةَ المعلَّقة في مستأجرها**.

    والدعوةُ تعيش في مستأجر البحث، فلا تُعدَّل من جلسةِ المتقدّم الأصليّة:
    سياسةُ «الدعوةُ إليّ» تُريه صفَّه ولا تُكتبه. فيُقرأ رمزُها المجزَّأ
    أوّلًا بجلسته، ثمّ يُعبَر بجسر الدعوة لتقع الكتابتان معًا.
    """
    async with tenant_session(principal.tenant_id, principal.user_id) as session:
        row = (await session.execute(
            select(RecruitmentApplication, ProjectInvitation.token_hash)
            .join(ProjectInvitation,
                  ProjectInvitation.id == RecruitmentApplication.invitation_id,
                  isouter=True)
            .where(RecruitmentApplication.id == application_id))).first()
        if row is None:
            raise NotFound("recruitment.application_not_found")
        application, token_hash = row
        opportunity_id = application.opportunity_id

    if token_hash is None:
        async with tenant_session(principal.tenant_id, principal.user_id) as session:
            updated = await recruitment.withdraw_application(
                session, application_id=application_id,
                actor_user_id=principal.user_id)
            state = (updated.status, updated.decided_at, updated.created_at,
                     updated.message)
    else:
        async with invitation_session(token_hash, principal.tenant_id,
                                      principal.user_id) as session:
            updated = await recruitment.withdraw_application(
                session, application_id=application_id,
                actor_user_id=principal.user_id)
            state = (updated.status, updated.decided_at, updated.created_at,
                     updated.message)

    return MyApplication(
        application_id=application_id, opportunity_id=opportunity_id,
        title="", status=state[0], message=state[3], submitted_at=state[2],
        decided_at=state[1], invitation=None)


# ═══════════════════ المتقدّمون والاختيار ═══════════════════


@router.get("/projects/{project_id}/opportunities/{opportunity_id}/applications",
            response_model=list[ManagerApplication])
async def list_applicants(
    project_id: uuid.UUID, opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_project_session),
) -> list[ManagerApplication]:
    """متقدّمو هذه الفرصة — **وما يلزم للاختيار لا أكثر**.

    ولا مؤسسةَ المتقدّم ولا معرّفُ حسابه: الاختيارُ يقع على التطبيق،
    والخدمةُ تشتقّ الحسابَ في الخادم عند التحويل.
    """
    tenant_id = _tenant(session, principal)
    await _gate(session, principal, project_id)
    await recruitment._listing_for_manager(
        session, project_id=project_id, tenant_id=tenant_id,
        opportunity_id=opportunity_id)
    rows = (await session.execute(
        select(RecruitmentApplication, User.full_name_ar, ProjectInvitation)
        .join(User, User.id == RecruitmentApplication.applicant_user_id)
        .join(ProjectInvitation,
              ProjectInvitation.id == RecruitmentApplication.invitation_id,
              isouter=True)
        .where(RecruitmentApplication.opportunity_id == opportunity_id)
        .order_by(RecruitmentApplication.created_at))).all()
    return [
        ManagerApplication(
            application_id=app.id, display_name=name or "باحث",
            status=app.status, message=app.message,
            submitted_at=app.created_at, decided_at=app.decided_at,
            invitation=_linked(invitation))
        for app, name, invitation in rows
    ]


async def _decide(application_id, principal, decision):
    """قرارُ مديرٍ — **وجلستُه جلسةُ البحث** لا جلسةُ مستأجره.

    فالتطبيقُ يُقرأ بسياسةِ «أُدير فرصتَه»، وهي تستوجب سياقَ مستأجر
    البحث. والمديرُ قد يكون متعاونًا من مؤسسةٍ أخرى، فيُعبَر بجسر البحث
    المُشتقِّ من الفرصة نفسِها.
    """
    from ..db import project_session

    async with tenant_session(principal.tenant_id, principal.user_id) as probe:
        project_id = (await probe.execute(
            select(RecruitmentOpportunity.project_id)
            .join(RecruitmentApplication,
                  RecruitmentApplication.opportunity_id == RecruitmentOpportunity.id)
            .where(RecruitmentApplication.id == application_id))).scalar_one_or_none()
    if project_id is None:
        # ولا يُفصح عن سببٍ: المعدومُ وغيرُ المأذون جوابُهما واحد.
        raise NotFound("recruitment.application_not_found")

    async with project_session(project_id, principal.tenant_id,
                               principal.user_id) as session:
        return await recruitment.decide_application(
            session, application_id=application_id,
            actor_user_id=principal.user_id, decision=decision)


@router.post("/applications/{application_id}/shortlist",
             response_model=ManagerApplication)
async def shortlist(
    application_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> ManagerApplication:
    row = await _decide(application_id, principal, "shortlisted")
    return ManagerApplication(
        application_id=row.id, display_name="", status=row.status,
        message=row.message, submitted_at=row.created_at,
        decided_at=row.decided_at, invitation=None)


@router.post("/applications/{application_id}/decline",
             response_model=ManagerApplication)
async def decline_applicant(
    application_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> ManagerApplication:
    row = await _decide(application_id, principal, "declined")
    return ManagerApplication(
        application_id=row.id, display_name="", status=row.status,
        message=row.message, submitted_at=row.created_at,
        decided_at=row.decided_at, invitation=None)


@router.post("/applications/{application_id}/invite",
             response_model=RecruitmentInvitationResponse)
async def invite_applicant(
    application_id: uuid.UUID,
    payload: InviteRequest,
    principal: Principal = Depends(get_principal),
) -> RecruitmentInvitationResponse:
    """اختيارُ مرشَّح — **ولا هويّةَ في الطلب**.

    فالمديرُ يُرسل دورًا وصلاحياتٍ ومهلةً. والمرشَّحُ يُشتقّ من
    `RecruitmentApplication.applicant_user_id`، والبحثُ من فرصته،
    والمستأجرُ من نسبها — كلُّها في الخادم.

    **والرمزُ يُعاد مرّةً واحدة.** ولا سبيلَ لتسليمه في هذه النسخة (لا
    بريدَ ولا إشعار)، فيُسلّمه المديرُ بنفسه — وهو سلوكُ دعوات الفريق
    القائم. ولا يُخزَّن خامًّا ولا يُكتب في سجلٍّ ولا يعود من أيّ قراءة.
    """
    from ..db import project_session

    async with tenant_session(principal.tenant_id, principal.user_id) as probe:
        project_id = (await probe.execute(
            select(RecruitmentOpportunity.project_id)
            .join(RecruitmentApplication,
                  RecruitmentApplication.opportunity_id == RecruitmentOpportunity.id)
            .where(RecruitmentApplication.id == application_id))).scalar_one_or_none()
    if project_id is None:
        raise NotFound("recruitment.application_not_found")

    async with project_session(project_id, principal.tenant_id,
                               principal.user_id) as session:
        selection = await recruitment.invite_applicant(
            session, application_id=application_id,
            actor_user_id=principal.user_id, role=payload.role,
            permissions=list(payload.permissions), ttl_hours=payload.ttl_hours)
        return RecruitmentInvitationResponse(
            application_id=selection.application.id,
            application_status=selection.application.status,
            invitation_id=selection.invitation.id,
            invitation_state=selection.invitation.state,
            role=selection.invitation.proposed_role,
            permissions=list(selection.invitation.proposed_permissions or []),
            expires_at=selection.invitation.expires_at,
            token=selection.token)
