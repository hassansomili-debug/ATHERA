"""فريق المشروع وقراراته | Project team and decisions (§12، §24).

ما لا يفعله هذا الموجّه: لا يستنتج أدوار CRediT من نشاط أحد، ولا يسجّل
موافقة نيابةً عن مؤلف، ولا يعدّل قرارًا محسومًا.

## والعطبُ الذي أُصلح هنا

كان `POST /projects/{id}/members/{member_id}/consent` يقرأ العضو بمعرِّفه،
ويكتب `consent_recorded_at`، **ولا يسأل مَن الطالب**. فكان رئيسُ الفريق —
وأيُّ مصادَقٍ في المستأجر — يسجّل موافقةَ أيِّ مؤلفٍ مشارك. وهذا ليس
اختصارًا: هو تزويرُ تأليف، وينتهي بورقةٍ تحمل اسمَ من لم يوافق.

فصار المسار **شخصيًّا في عنوانه**: `/members/me/consent`. ولا يقبل معرِّف
عضوٍ أصلًا، فلا مكان في الطلب لاسم غيرك. والمسارُ الإداري — إن لزم قانونًا —
منفصلٌ ومعلَنٌ ويلزمه سندٌ مكتوب، ويُوسَم في السجلّ والشاشة `administrative`
فلا يُقرأ أبدًا كموافقةٍ شخصية.

## ولا شيء هنا يُقرأ بالعضوية وحدها

كلُّ مسارٍ يمرّ بـ`collaboration.require_permission`. والعضويةُ تفتح الباب
ولا تمنح ما وراءه: الصلاحيةُ صفٌّ يُقرأ، لا دورٌ يُفسَّر.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, Forbidden, NotFound
from ..models.collaboration import ProjectInvitation, ProjectMemberEvent
from ..models.portfolio import ProjectDecision, ProjectMember, ResearchProject
from ..schemas.team import (
    AuthorshipDeclarationRequest,
    DecisionCreateRequest,
    DecisionResponse,
    InvitationCreateRequest,
    InvitationResponse,
    InvitationTokenRequest,
    IssuedInvitationResponse,
    MemberAccessRequest,
    MemberCreateRequest,
    MemberCreditRequest,
    MemberEventResponse,
    MemberPermissionsRequest,
    MemberResponse,
    MemberRoleRequest,
    PendingActionResponse,
    ProxyConsentRequest,
    SelfConsentRequest,
    VocabularyResponse,
)
from ..services import audit, collaboration, team

router = APIRouter(prefix="/api/v1", tags=["team"])


def _pick(locale: str, arabic: str, english: str | None) -> str:
    return (english or arabic) if locale == "en" else arabic


def _label(mapping: dict[str, tuple[str, str]], key: str, locale: str) -> str:
    return _pick(locale, *mapping.get(key, (key, key)))


def _vocab(mapping: dict[str, tuple[str, str]], locale: str) -> list[VocabularyResponse]:
    return [
        VocabularyResponse(key=key, label=_pick(locale, *value))
        for key, value in mapping.items()
    ]


@router.get("/vocab/credit-roles", response_model=list[VocabularyResponse])
async def credit_roles(principal: Principal = Depends(get_principal)):
    return _vocab(team.CREDIT_ROLES, principal.locale)


@router.get("/vocab/member-roles", response_model=list[VocabularyResponse])
async def member_roles(principal: Principal = Depends(get_principal)):
    return _vocab(team.MEMBER_ROLES, principal.locale)


@router.get("/vocab/decision-kinds", response_model=list[VocabularyResponse])
async def decision_kinds(principal: Principal = Depends(get_principal)):
    return _vocab(team.DECISION_KINDS, principal.locale)


@router.get("/vocab/project-permissions", response_model=list[VocabularyResponse])
async def project_permissions(principal: Principal = Depends(get_principal)):
    """الصلاحياتُ مفردةٌ مغلقة تبنيها الشاشة منها، ولا تكرّرها في نفسها."""
    return _vocab(team.PROJECT_PERMISSIONS, principal.locale)


async def _require_project(session: AsyncSession, project_id: uuid.UUID) -> ResearchProject:
    row = (
        await session.execute(select(ResearchProject).where(ResearchProject.id == project_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("team.project_not_found")
    return row


async def _member_in(
    session: AsyncSession, project_id: uuid.UUID, member_id: uuid.UUID
) -> ProjectMember:
    """يقرأ عضوًا **بمعرِّفه ومعرِّف بحثه معًا**.

    ومعرِّفٌ وحده يكفي للقراءة في القاعدة، ويسمح لعضوٍ في بحثٍ أن يعدّل عضوًا
    في بحثٍ آخر من المستأجر نفسه إن عرف معرِّفه. وRLS لا تمنع هذا: هي تعزل
    المستأجرين، لا البحوث بعضها عن بعض.
    """
    row = (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.id == member_id, ProjectMember.project_id == project_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("team.member_not_found")
    return row


def _member(row: ProjectMember, permissions: frozenset[str], locale: str) -> MemberResponse:
    credit = list(row.credit_roles or [])
    granted = sorted(permissions)
    return MemberResponse(
        id=row.id, project_id=row.project_id, display_name=row.display_name,
        user_id=row.user_id,
        # الشاشة تحتاج هذا صراحةً: صفٌّ بلا حساب لا يدخل ولا يوافق.
        is_account_linked=row.user_id is not None,
        invited_email=row.invited_email,
        role=row.role, role_label=_label(team.MEMBER_ROLES, row.role, locale),
        access_state=row.access_state,
        access_label=_label(team.ACCESS_STATE_LABELS, row.access_state, locale),
        permissions=granted,
        permission_labels=[
            _label(team.PROJECT_PERMISSIONS, key, locale) for key in granted],
        credit_roles=credit,
        credit_labels=[
            _pick(locale, *team.CREDIT_ROLES[key]) for key in credit
            if key in team.CREDIT_ROLES
        ],
        is_author=row.is_author, author_position=row.author_position,
        consent_state=row.consent_state,
        consent_label=_label(team.CONSENT_STATE_LABELS, row.consent_state, locale),
        consent_method=row.consent_method,
        consent_method_label=(
            _label(team.CONSENT_METHOD_LABELS, row.consent_method, locale)
            if row.consent_method else None),
        consent_recorded_at=row.consent_recorded_at,
        consent_recorded_by=row.consent_recorded_by,
        # **الموافقةُ التي سُجِّلت تحت المسار المعطوب تُعلَن بحاجتها إلى
        # إعادة جمع.** وطيُّها في «مُنحت» يجعل الشاشة تكرّر الادّعاء الذي
        # أوجد العطب: أن أحدًا وافق، بينما لا يُعرف من كتبها.
        consent_needs_recollection=row.consent_method == "legacy_unverified",
    )


async def _members_with_permissions(
    session: AsyncSession, project_id: uuid.UUID, locale: str
) -> list[MemberResponse]:
    rows = (
        await session.execute(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
            .order_by(ProjectMember.created_at)
        )
    ).scalars().all()
    return [
        _member(row, await collaboration.permissions_of(session, member_id=row.id),
                locale)
        for row in rows
    ]


# ═══════════════════════════ الأعضاء ═══════════════════════════

@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[MemberResponse]:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="view_project")
    return await _members_with_permissions(session, project_id, principal.locale)


@router.post("/projects/{project_id}/members", response_model=MemberResponse,
             status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: uuid.UUID,
    payload: MemberCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """يسجّل مساهمًا **باسمه وحده** — ولا يربط حسابًا.

    والربطُ بحساب طريقٌ واحد: دعوةٌ يقبلها صاحبُ الحساب بنفسه. وكان هذا
    المسار يقبل `user_id` من جسم الطلب، فكان يربط زميلًا ببحثٍ لم يدخله.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    if payload.role not in team.MEMBER_ROLES:
        raise AtheraError("team.unknown_member_role", status_code=422, role=payload.role)
    try:
        team.validate_author_name(payload.display_name)
        team.validate_credit_roles(payload.credit_roles)
    except team.TeamError as exc:
        raise AtheraError("team.invalid_member", status_code=422, detail=str(exc)) from exc

    row = ProjectMember(
        tenant_id=principal.tenant_id, project_id=project_id,
        user_id=None, display_name=payload.display_name.strip(),
        role=payload.role, credit_roles=payload.credit_roles or None,
        access_state="active", consent_state="not_requested", is_author=False,
    )
    session.add(row)
    await session.flush()

    await collaboration.record_member_event(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        member_id=row.id, event_kind="accepted", actor_user_id=principal.user_id,
        state_after={"role": payload.role, "credit_roles": payload.credit_roles,
                     "account_linked": False},
        note_ar="مساهم بلا حساب: لا يدخل ولا يوافق حتى يُدعى ويقبل بنفسه.")
    await audit.record(
        session, tenant_id=principal.tenant_id, action="team.member_added",
        object_type="project_member", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"role": payload.role, "credit_roles": payload.credit_roles,
                     "account_linked": False},
        reason="CRediT roles are recorded as declared, never inferred (§24); an "
               "account is bound only by the invited person accepting in person",
    )
    return _member(row, frozenset(), principal.locale)


@router.patch("/projects/{project_id}/members/{member_id}/role",
              response_model=MemberResponse)
async def change_member_role(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberRoleRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """يغيّر الدور — **ولا يمسّ الصلاحيات**؛ لكلٍّ منهما طلبُه."""
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    await collaboration.change_role(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, role=payload.role)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


@router.put("/projects/{project_id}/members/{member_id}/permissions",
            response_model=MemberResponse)
async def set_member_permissions(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberPermissionsRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    granted = await collaboration.set_permissions(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, keys=payload.permissions)
    return _member(member, granted, principal.locale)


@router.put("/projects/{project_id}/members/{member_id}/credit",
            response_model=MemberResponse)
async def set_member_credit(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberCreditRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """§24 — إقرارُ أدوار CRediT.

    والباحثُ يعدّل إقرارَه، والفريقُ يعدّل الإقرارات. وما لا يقع أبدًا: أن
    تكتب المنصّة دورًا لأن أحدًا حرّر ملفًّا. فالمساهمةُ مسؤوليةٌ يُقرّ بها
    صاحبها، لا أثرٌ تقرؤه آلة.
    """
    member = await _member_in(session, project_id, member_id)
    # صاحبُ الإقرار يعدّل إقراره بلا صلاحية إدارة — وغيرُه يحتاجها.
    if member.user_id != principal.user_id:
        await collaboration.require_permission(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            user_id=principal.user_id, permission="manage_team")
    else:
        await collaboration.require_permission(
            session, tenant_id=principal.tenant_id, project_id=project_id,
            user_id=principal.user_id, permission="view_project")
    await collaboration.set_credit_roles(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, roles=payload.credit_roles)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


@router.put("/projects/{project_id}/members/{member_id}/authorship",
            response_model=MemberResponse)
async def declare_member_authorship(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: AuthorshipDeclarationRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """**عضويةُ الفريق ليست تأليفًا.** والتأليفُ إعلانٌ صريحٌ يُنسب إلى معلنه.

    والإعلانُ وحده لا يكفي: الموافقةُ بعده، ولا يملكها إلّا صاحبُها.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    await collaboration.declare_authorship(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, is_author=payload.is_author,
        position=payload.author_position)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


@router.patch("/projects/{project_id}/members/{member_id}/access",
              response_model=MemberResponse)
async def change_member_access(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: MemberAccessRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    # **لا يُوقف أحدٌ آخرَ مديري الفريق.** وبحثٌ بلا من يديره لا يُستعاد
    # إلّا بتدخّل يدويّ في القاعدة.
    if payload.access_state != "active" and member.user_id is not None:
        await _refuse_if_last_team_manager(session, project_id, member)
    await collaboration.set_access_state(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, state=payload.access_state)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


async def _refuse_if_last_team_manager(
    session: AsyncSession, project_id: uuid.UUID, member: ProjectMember
) -> None:
    others = (
        await session.execute(
            select(ProjectMember.id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.id != member.id,
                ProjectMember.access_state == "active",
                ProjectMember.user_id.is_not(None),
            )
        )
    ).scalars().all()
    for other_id in others:
        if "manage_team" in await collaboration.permissions_of(
                session, member_id=other_id):
            return
    if "manage_team" in await collaboration.permissions_of(
            session, member_id=member.id):
        raise AtheraError("team.last_manager", status_code=409)


@router.post("/projects/{project_id}/members/me/leave", response_model=MemberResponse)
async def leave_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """يخرج الشريكُ بنفسه — **وأثرُه يبقى**.

    فخروجُه من التعاون شيء، ومحوُ أنه كان فيه شيءٌ آخر. وموافقتُه على
    تأليفٍ سُجِّلت تبقى كما سُجِّلت: هي واقعةٌ وقعت.
    """
    access = await collaboration.access_for(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id)
    await _refuse_if_last_team_manager(session, project_id, access.member)
    await collaboration.set_access_state(
        session, tenant_id=principal.tenant_id, member=access.member,
        actor_user_id=principal.user_id, state="removed", left_voluntarily=True)
    return _member(access.member, access.permissions, principal.locale)


# ═══════════════════════════ الموافقة على التأليف ═══════════════════════════

@router.post("/projects/{project_id}/members/{member_id}/consent-request",
             response_model=MemberResponse)
async def request_member_consent(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """يطلب الموافقة — **ولا يمنحها**. والفرقُ هو كلُّ الموضوع."""
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    await collaboration.request_consent(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


@router.post("/projects/{project_id}/members/me/consent", response_model=MemberResponse)
async def record_own_consent(
    project_id: uuid.UUID,
    payload: SelfConsentRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """§24 — **موافقتُك أنت، ولا يقبل هذا المسار اسمَ أحدٍ سواك.**

    والعنوان `me` ليس تجميلًا: المسارُ القديم كان يأخذ `member_id`، فكان
    جسمُ الطلب نفسه يسمح بأن يُكتب اسمُ غيرك. وحذفُ الحقل يحذف الاحتمال.

    ولا زرَّ «وافق الجميع» في المنصّة: موافقةٌ تُمنح بضغطةٍ واحدة عن آخرين
    ليست موافقة.
    """
    access = await collaboration.access_for(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id)
    await collaboration.record_self_consent(
        session, tenant_id=principal.tenant_id, member=access.member,
        actor_user_id=principal.user_id, granted=payload.granted)
    return _member(access.member, access.permissions, principal.locale)


@router.post("/projects/{project_id}/members/{member_id}/administrative-consent",
             response_model=MemberResponse)
async def record_administrative_consent(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: ProxyConsentRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """المسارُ الإداري — **منفصلٌ، معلَنٌ، مُدقَّق، ويلزمه سند**.

    ويوجد لأنّ موافقةً موقَّعةً على ورقٍ لدى الجهة واقعةٌ حقيقية. وثلاثةٌ
    تفرّقه عمّا كان يقع قبل الترحيل 0028: يلزمه سندٌ مكتوب ترفضه القاعدة
    بدونه، ويُوسم `administrative` فلا يُقرأ كموافقةٍ شخصية، ويظهر موسومًا
    في الشاشة فيراه المؤلف نفسه ويستطيع الاعتراض.

    وما لا يفعله: أن يبدو ذاتيًّا. القيدُ في القاعدة يمنع ذلك ولو أمره كود.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    member = await _member_in(session, project_id, member_id)
    # **ولا يسجّل أحدٌ موافقتَه هو من هذا الباب.** فمسارٌ إداريٌّ يقبل صاحبَه
    # يصير طريقًا ثانيًا للموافقة الذاتية بلا وسمها، وهو الباب الخلفي عينه.
    if member.user_id is not None and member.user_id == principal.user_id:
        raise Forbidden("team.use_the_personal_consent_route")
    await collaboration.record_administrative_consent(
        session, tenant_id=principal.tenant_id, member=member,
        actor_user_id=principal.user_id, evidence_ar=payload.evidence_ar)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


# ═══════════════════════════ الدعوات ═══════════════════════════

def _invitation(row: ProjectInvitation, locale: str) -> InvitationResponse:
    return InvitationResponse(
        id=row.id, project_id=row.project_id, invited_email=row.invited_email,
        invited_display_name=row.invited_display_name,
        proposed_role=row.proposed_role,
        proposed_role_label=_label(team.MEMBER_ROLES, row.proposed_role, locale),
        proposed_permissions=list(row.proposed_permissions or []),
        state=row.state,
        state_label=_label(team.INVITATION_STATE_LABELS, row.state, locale),
        expires_at=row.expires_at, responded_at=row.responded_at,
        accepted_user_id=row.accepted_user_id, member_id=row.member_id,
    )


@router.get("/projects/{project_id}/invitations", response_model=list[InvitationResponse])
async def list_invitations(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[InvitationResponse]:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    rows = (
        await session.execute(
            select(ProjectInvitation).where(ProjectInvitation.project_id == project_id)
            .order_by(ProjectInvitation.created_at)
        )
    ).scalars().all()
    return [_invitation(row, principal.locale) for row in rows]


@router.post("/projects/{project_id}/invitations",
             response_model=IssuedInvitationResponse,
             status_code=status.HTTP_201_CREATED)
async def create_invitation(
    project_id: uuid.UUID,
    payload: InvitationCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> IssuedInvitationResponse:
    """يدعو باحثًا — **ولا يضيفه**. والفرقُ أنّ الطرف الآخر يملك القرار.

    والرمزُ يُعاد هنا **مرّةً واحدة** ليُسلَّم إلى صاحبه؛ ولا تُعيده أيُّ
    قراءةٍ بعدها، ولا يُخزَّن خامًا، ولا يُكتب في سجلّ تدقيق.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    await _require_project(session, project_id)
    issued = await collaboration.invite_member(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        inviter_user_id=principal.user_id, email=payload.email,
        display_name=payload.display_name, role=payload.role,
        permissions=payload.permissions)
    base = _invitation(issued.invitation, principal.locale)
    return IssuedInvitationResponse(**base.model_dump(), token=issued.token)


@router.delete("/projects/{project_id}/invitations/{invitation_id}",
               response_model=InvitationResponse)
async def revoke_invitation(
    project_id: uuid.UUID,
    invitation_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> InvitationResponse:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="manage_team")
    row = await collaboration.revoke_invitation(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        invitation_id=invitation_id, actor_user_id=principal.user_id)
    return _invitation(row, principal.locale)


@router.post("/invitations/accept", response_model=MemberResponse)
async def accept_invitation(
    payload: InvitationTokenRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemberResponse:
    """يقبل المدعوُّ **بحسابه هو**.

    ولا مسارَ هنا يقبل عن أحد: `principal.user_id` يأتي من رمزٍ موقَّع، وهو
    ما يُكتب في `ProjectMember.user_id`. والمطابقةُ بالاسم المعروض ممنوعة —
    «د. محمد العلي» في مستأجرٍ جامعيّ قد يكون ثلاثةَ أشخاص.
    """
    member = await collaboration.accept_invitation(
        session, tenant_id=principal.tenant_id, token=payload.token,
        accepting_user_id=principal.user_id)
    return _member(member, await collaboration.permissions_of(
        session, member_id=member.id), principal.locale)


@router.post("/invitations/decline", response_model=InvitationResponse)
async def decline_invitation(
    payload: InvitationTokenRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> InvitationResponse:
    row = await collaboration.decline_invitation(
        session, tenant_id=principal.tenant_id, token=payload.token,
        declining_user_id=principal.user_id)
    return _invitation(row, principal.locale)


# ═══════════════════════════ سجلّ دورة الحياة ═══════════════════════════

@router.get("/projects/{project_id}/member-events",
            response_model=list[MemberEventResponse])
async def list_member_events(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[MemberEventResponse]:
    """كيف صار الفريق إلى ما هو عليه — لا ما هو عليه فقط.

    ونزاعُ التأليف يُحسم بهذا السجلّ لا بالحال الراهن: من غيّر، ومتى،
    وما الذي كان قبله.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="view_project")
    rows = (
        await session.execute(
            select(ProjectMemberEvent)
            .where(ProjectMemberEvent.project_id == project_id)
            .order_by(ProjectMemberEvent.occurred_at)
        )
    ).scalars().all()
    return [
        MemberEventResponse(
            id=row.id, member_id=row.member_id, invitation_id=row.invitation_id,
            event_kind=row.event_kind, actor_user_id=row.actor_user_id,
            subject_user_id=row.subject_user_id, state_before=row.state_before,
            state_after=row.state_after, note_ar=row.note_ar,
            occurred_at=row.occurred_at)
        for row in rows
    ]


# ═══════════════════════════ القرارات ═══════════════════════════

def _decision(row: ProjectDecision, superseded_by: dict[uuid.UUID, uuid.UUID],
              locale: str) -> DecisionResponse:
    kind = team.DECISION_KINDS.get(row.decision_kind,
                                   (row.decision_kind, row.decision_kind))
    successor = superseded_by.get(row.id)
    return DecisionResponse(
        id=row.id, project_id=row.project_id, decision_kind=row.decision_kind,
        kind_label=_pick(locale, *kind),
        statement=_pick(locale, row.statement_ar, row.statement_en),
        gate=row.gate, approval_id=row.approval_id, decided_by=row.decided_by,
        decided_at=row.decided_at, supersedes_id=row.supersedes_id,
        is_superseded=successor is not None,
        is_current=successor is None,
        superseded_by_id=successor,
    )


@router.get("/projects/{project_id}/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DecisionResponse]:
    """**سجلُّ القرارات** — السلسلة كاملة، المنسوخ والناسخ معًا.

    وهو غيرُ «ما يحتاج فعلًا» (`/decisions/inbox`): خلطُهما في قائمةٍ واحدة
    بلا وسمٍ يجعل الفريق لا يعرف أيُّ سطرٍ ينتظره وأيُّها انتهى، فيُقرأ
    القديم على أنه مطلوبٌ اليوم أو يُترك المطلوبُ لأنه يشبه سجلًّا.

    وإخفاءُ المنسوخ يجعل السجل يبدو كأن الرأي الحالي هو الرأي الوحيد.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="view_project")
    rows = (
        await session.execute(
            select(ProjectDecision).where(ProjectDecision.project_id == project_id)
            .order_by(ProjectDecision.created_at)
        )
    ).scalars().all()
    superseded_by = {
        row.supersedes_id: row.id for row in rows if row.supersedes_id}
    return [_decision(row, superseded_by, principal.locale) for row in rows]


@router.post("/projects/{project_id}/decisions", response_model=DecisionResponse,
             status_code=status.HTTP_201_CREATED)
async def record_decision(
    project_id: uuid.UUID,
    payload: DecisionCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DecisionResponse:
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="edit_research_content")
    if payload.decision_kind not in team.DECISION_KINDS:
        raise AtheraError("team.unknown_decision_kind", status_code=422,
                          kind=payload.decision_kind)

    if payload.supersedes_id is not None:
        previous = (
            await session.execute(
                select(ProjectDecision).where(
                    ProjectDecision.id == payload.supersedes_id)
            )
        ).scalar_one_or_none()
        if previous is None:
            raise NotFound("team.decision_not_found")
        if previous.project_id != project_id:
            raise AtheraError("team.decision_other_project", status_code=422)

    row = ProjectDecision(
        tenant_id=principal.tenant_id, project_id=project_id,
        decision_kind=payload.decision_kind, statement_ar=payload.statement_ar,
        statement_en=payload.statement_en, gate=payload.gate,
        supersedes_id=payload.supersedes_id,
        decided_by=principal.user_id, decided_at=dt.datetime.now(dt.UTC),
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="team.decision_recorded",
        object_type="project_decision", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"kind": payload.decision_kind,
                     "supersedes": str(payload.supersedes_id) if payload.supersedes_id else None},
    )
    return _decision(row, {}, principal.locale)


# ═══════════════════════════ صندوقُ ما يحتاج فعلًا ═══════════════════════════

_PENDING_LABELS: dict[str, tuple[str, str]] = {
    "author_consent": ("موافقة تأليف بانتظار صاحبها", "Author consent awaited"),
    "invitation_reply": ("دعوة بانتظار ردّ", "Invitation awaiting a reply"),
    "consent_recollection": ("موافقة قديمة تحتاج إعادة جمع",
                             "Legacy consent must be re-collected"),
}


@router.get("/projects/{project_id}/decisions/inbox",
            response_model=list[PendingActionResponse])
async def decision_inbox(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[PendingActionResponse]:
    """**ما يحتاج فعلًا الآن** — لا ما قرّره الفريق يومًا.

    وهو مشتقٌّ من الحال الحقيقية لا من طابورٍ يُكتب فيه ما نتمنّى: بندٌ هنا
    يختفي حين يقع الفعلُ الذي ينتظره، لأنه لم يكن صفًّا بل قراءةً للواقع.
    وطابورٌ يُكتب فيه ما «ينبغي» يتراكم فيه ما وقع أصلًا، فيُهمَل كلُّه.

    و`is_mine` تفرّق ما تنتظره **أنت** عمّا ينتظره الفريق: قائمةٌ لا تفرّق
    تجعل الشريك يرى بندًا لا يستطيع إغلاقه، فيتعلّم تجاهل القائمة.
    """
    await collaboration.require_permission(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        user_id=principal.user_id, permission="view_project")

    items: list[PendingActionResponse] = []
    members = (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.access_state.in_(("active", "invited")))
            .order_by(ProjectMember.created_at)
        )
    ).scalars().all()
    for member in members:
        if member.is_author and member.consent_state == "pending":
            items.append(PendingActionResponse(
                kind="author_consent",
                kind_label=_label(_PENDING_LABELS, "author_consent", principal.locale),
                subject_id=member.id,
                statement=member.display_name,
                is_mine=member.user_id == principal.user_id,
                blocking_since=member.updated_at))
        if member.consent_method == "legacy_unverified":
            items.append(PendingActionResponse(
                kind="consent_recollection",
                kind_label=_label(_PENDING_LABELS, "consent_recollection",
                                  principal.locale),
                subject_id=member.id, statement=member.display_name,
                is_mine=member.user_id == principal.user_id,
                blocking_since=member.consent_recorded_at))

    invitations = (
        await session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.project_id == project_id,
                ProjectInvitation.state == "invited")
        )
    ).scalars().all()
    for invitation in invitations:
        items.append(PendingActionResponse(
            kind="invitation_reply",
            kind_label=_label(_PENDING_LABELS, "invitation_reply", principal.locale),
            subject_id=invitation.id, statement=invitation.invited_display_name,
            is_mine=invitation.invited_user_id == principal.user_id,
            blocking_since=invitation.created_at))
    return items
