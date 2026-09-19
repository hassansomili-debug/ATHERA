"""لوحة الإدارة — الاستعلامات | Admin Console V1 queries (Stage 9).

## الحدودُ التي لا تُساوَم

**١ · مستأجرٌ واحد، ومن الرمز.** كلُّ عبارةٍ هنا تشترط `tenant_id == tid`
صراحةً، و`tid` هو `principal.tenant_id` — لا مُعاملٌ من المتصفّح. وRLS فوق
ذلك طبقةٌ ثانية لا الأولى.

**٢ · `users` جدولٌ عامّ — وسياستُه `global_readwrite: true`.** قِيس ذلك من
القاعدة الحيّة: RLS **لا تحمي** هذا الجدول. فالمستخدمُ لا يُبلَغ هنا إلّا
**عبر عضويّةٍ في هذا المستأجر** (`memberships` محميّةٌ بـRLS): كلُّ عبارةٍ
تقرأ `User` تبدأ من `Membership` أو تُقيَّد بمعرّفاتٍ ثبتت عضويّتُها أوّلًا.
ولا بحثٌ عامٌّ يُصفّى بعده. فمديرُ المستأجر A لا يكتشف مستخدمًا لا يعرفه
إلّا المستأجرُ B — لا في قائمةٍ ولا بحثٍ ولا عدٍّ ولا تفصيل.

**٣ · بياناتُ تشغيلٍ لا محتوى بحث.** لا `request_payload` ولا
`response_payload` ولا `input_summary`/`output_summary` ولا نصُّ خطأٍ حرّ —
بل **حضورُ** الخطأ وحدَه. ورمزُ إخفاق الرسالة يُعرض لأنّه من مفرداتٍ مغلقةٍ
يفرضها قيدٌ في القاعدة.

**٤ · محدود.** نوافذُ زمنيّةٌ صريحة بساعة القاعدة، وصفحاتٌ بحدٍّ أقصى، وعددُ
عباراتٍ ثابتٌ للصفحة الواحدة (لا N+1). ولا تحقّقَ كاملًا من سلسلة التدقيق مع
كلّ تحميل.

**٥ · لا طفرة.** لا تفعيلَ حسابٍ ولا تعطيلَه، ولا انتحالَ هُويّة، ولا منحَ
دور، ولا حذف. ذلك كلُّه مُحالٌ إلى المرحلة ١٠.
"""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, exists, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AtheraError, NotFound
from ..models.audit import AuditEvent
from ..models.files import File
from ..models.identity import Membership, Role, Tenant, User
from ..models.portfolio import ProjectFile, ProjectMember, ResearchProject
from ..models.publishing import Manuscript
from ..models.research import ResearcherProfile
from ..models.runs import AgentRun, ModelRun, ToolRun
from ..models.thesis import Thesis
from ..schemas import admin as S
from . import rbac
from .collaboration import PROJECT_CREATED_ACTIONS, PROJECT_OBJECT_TYPE
from .thesis import processing

#: حدودُ الصفحات.
DEFAULT_PAGE = 25
MAX_PAGE = 100
DEFAULT_OPS = 50
MAX_OPS = 200
#: نافذةُ العمليات — حتى «الكلّ» محدودٌ زمنيًّا لا مسحٌ لتاريخٍ لا حدَّ له.
OPERATIONS_WINDOW_DAYS = 90
#: النوافذُ المسموحة للاستخدام.
USAGE_WINDOWS = {"7d": 7, "30d": 30, "90d": 90}
#: حدُّ بحوث المستخدم في صفحة تفصيله.
DETAIL_PROJECTS = 20

MODEL_OK = "ok"
MODEL_FAILED = ("error",)
MODEL_AMBIGUOUS = "ambiguous"


# ═════════════════════════════ أدوات ═════════════════════════════


def _window(days: int):
    """بداية النافذة **بساعة القاعدة** — لا بساعة العمليّة."""
    return func.now() - dt.timedelta(days=days)


def _display(locale: str, ar: str | None, en: str | None, email: str) -> str:
    if locale == "en":
        return en or ar or email
    return ar or en or email


def _like(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def encode_cursor(stamp: dt.datetime, ident: uuid.UUID) -> str:
    """مؤشّرٌ **معتِمٌ** للمتصفّح: لا عبارةَ SQL فيه ولا اسمَ عمود."""
    raw = json.dumps({"t": stamp.isoformat(), "i": str(ident)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[dt.datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
        return dt.datetime.fromisoformat(data["t"]), uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise AtheraError("admin.invalid_cursor", status_code=422) from exc


def clamp(limit: int | None, default: int, maximum: int) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), maximum))


def _owner_expr():
    """مالكُ البحث — **بالتعريف نفسِه الذي يستعمله المنتج** (`owner_user_id`).

    ملفُّ الباحث أوّلًا، ثمّ فاعلُ أوّلِ حدثِ إنشاءٍ في سجلّ التدقيق. وهنا تعبيرٌ
    واحدٌ مترابط لا نداءٌ لكلّ بحث — فالقائمةُ عبارةٌ واحدة لا N+1.
    """
    profile_user = (
        select(ResearcherProfile.user_id)
        .where(ResearcherProfile.id == ResearchProject.profile_id)
        .correlate(ResearchProject).scalar_subquery()
    )
    first_creator = (
        select(AuditEvent.actor_user_id)
        .where(AuditEvent.tenant_id == ResearchProject.tenant_id,
               AuditEvent.object_type == PROJECT_OBJECT_TYPE,
               AuditEvent.object_id == ResearchProject.id,
               AuditEvent.action.in_(PROJECT_CREATED_ACTIONS),
               AuditEvent.actor_user_id.is_not(None))
        .order_by(AuditEvent.occurred_at).limit(1)
        .correlate(ResearchProject).scalar_subquery()
    )
    return func.coalesce(profile_user, first_creator)


def _lifecycle_expr():
    return case(
        (ResearchProject.deleted_at.is_not(None), "trashed"),
        (ResearchProject.archived_at.is_not(None), "archived"),
        else_="active",
    )


async def _member_names(session: AsyncSession, tid: uuid.UUID, user_ids: set[uuid.UUID],
                        locale: str) -> dict[uuid.UUID, str]:
    """أسماءُ من ثبتت عضويّتُه هنا **وحدَه** — عبارةٌ واحدة، ومرساتُها العضويّة."""
    ids = {u for u in user_ids if u is not None}
    if not ids:
        return {}
    rows = (await session.execute(
        select(User.id, User.full_name_ar, User.full_name_en, User.email)
        .where(User.id.in_(ids),
               exists().where(Membership.tenant_id == tid, Membership.user_id == User.id))
    )).all()
    return {r[0]: _display(locale, r[1], r[2], r[3]) for r in rows}


# ═════════════════════════════ استخدامُ النموذج ═════════════════════════════


async def model_usage(session: AsyncSession, tid: uuid.UUID, days: int,
                      requested_by: uuid.UUID | None = None) -> S.ModelUsage:
    """ملخّصُ `model_runs` في النافذة — ومع `requested_by` المنسوبُ إليه وحدَه."""
    cost_known = ModelRun.cost_usd.is_not(None)
    query = (
        select(
            func.count(ModelRun.id),
            func.count(ModelRun.id).filter(ModelRun.status == MODEL_OK),
            func.count(ModelRun.id).filter(ModelRun.status.in_(MODEL_FAILED)),
            func.count(ModelRun.id).filter(ModelRun.status == MODEL_AMBIGUOUS),
            func.coalesce(func.sum(ModelRun.input_tokens), 0),
            func.coalesce(func.sum(ModelRun.output_tokens), 0),
            # **المسجَّلُ وحدَه**: `SUM` تتخطّى الفارغ، و`coalesce` للنتيجة لا للصفوف.
            func.coalesce(func.sum(ModelRun.cost_usd).filter(cost_known), 0),
            func.count(ModelRun.id).filter(cost_known),
            func.count(ModelRun.id).filter(~cost_known),
        )
        .where(ModelRun.tenant_id == tid, ModelRun.created_at >= _window(days))
    )
    if requested_by is not None:
        query = query.join(AgentRun, AgentRun.id == ModelRun.agent_run_id).where(
            AgentRun.tenant_id == tid, AgentRun.requested_by == requested_by)
    row = (await session.execute(query)).one()
    total, ok, failed, ambiguous = int(row[0]), int(row[1]), int(row[2]), int(row[3])
    return S.ModelUsage(
        window_days=days, model_runs=total, succeeded=ok, failed=failed, ambiguous=ambiguous,
        other_status=total - ok - failed - ambiguous,
        input_tokens=int(row[4]), output_tokens=int(row[5]),
        recorded_cost_usd=Decimal(row[6]), runs_with_cost=int(row[7]),
        runs_without_cost=int(row[8]),
    )


# ═════════════════════════════ النظرة العامّة ═════════════════════════════


async def overview(session: AsyncSession, *, tid: uuid.UUID, roles: list[str],
                   locale: str) -> S.AdminOverview:
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tid))).scalar_one()

    # ── المستخدمون: أشخاصٌ متمايزون عبر العضويّة ──
    members = (
        select(Membership.user_id).where(Membership.tenant_id == tid).distinct().subquery()
    )
    urow = (await session.execute(
        select(
            func.count(User.id),
            func.count(User.id).filter(User.is_active.is_(True)),
            func.count(User.id).filter(User.last_login_at >= _window(7)),
            func.count(User.id).filter(User.last_login_at >= _window(30)),
        ).join(members, members.c.user_id == User.id)
    )).one()

    prow = (await session.execute(
        select(
            func.count(ResearchProject.id).filter(ResearchProject.deleted_at.is_(None)),
            func.count(ResearchProject.id).filter(ResearchProject.deleted_at.is_(None),
                                                  ResearchProject.archived_at.is_(None)),
            func.count(ResearchProject.id).filter(ResearchProject.deleted_at.is_(None),
                                                  ResearchProject.archived_at.is_not(None)),
            func.count(ResearchProject.id).filter(ResearchProject.deleted_at.is_not(None)),
        ).where(ResearchProject.tenant_id == tid)
    )).one()

    frow = (await session.execute(
        select(
            func.count(File.id).filter(File.trashed_at.is_(None)),
            func.coalesce(func.sum(File.size_bytes).filter(File.trashed_at.is_(None)), 0),
            func.count(File.id).filter(File.trashed_at.is_not(None)),
            func.count(File.id).filter(File.trashed_at.is_(None), File.status == "pending"),
        ).where(File.tenant_id == tid)
    )).one()

    trows = (await session.execute(
        select(Thesis.processing_state, func.count(Thesis.id))
        .where(Thesis.tenant_id == tid).group_by(Thesis.processing_state)
    )).all()
    by_state = {state: 0 for state in processing.PROCESSING_STATES}
    by_state.update({r[0]: int(r[1]) for r in trows})
    stalled = int((await session.execute(
        select(func.count(Thesis.id)).where(
            Thesis.tenant_id == tid, Thesis.processing_state.in_(processing.IN_FLIGHT),
            Thesis.processing_state_changed_at <= func.now() - processing.STALE_AFTER)
    )).scalar_one())

    ai = await model_usage(session, tid, 30)

    arow = (await session.execute(
        select(
            func.count(AgentRun.id).filter(AgentRun.status == "failed"),
            func.count(AgentRun.id).filter(AgentRun.status == "blocked"),
        ).where(AgentRun.tenant_id == tid, AgentRun.created_at >= _window(30))
    )).one()
    trow = (await session.execute(
        select(
            func.count(ToolRun.id).filter(ToolRun.status == "error"),
            func.count(ToolRun.id).filter(ToolRun.status == "denied"),
        ).where(ToolRun.tenant_id == tid, ToolRun.created_at >= _window(30))
    )).one()

    audit_row = (await session.execute(
        select(func.max(AuditEvent.chain_seq), func.max(AuditEvent.occurred_at))
        .where(AuditEvent.tenant_id == tid)
    )).one()

    return S.AdminOverview(
        scope=S.AdminScope(
            tenant_id=tid, tenant_name=tenant.display(locale),
            current_admin_roles=sorted(set(roles) & rbac.ADMIN_ROLE_KEYS)),
        users=S.UserCounts(member_count=int(urow[0]), active_identity_count=int(urow[1]),
                           signed_in_7d=int(urow[2]), signed_in_30d=int(urow[3])),
        projects=S.ProjectCounts(total=int(prow[0]), active=int(prow[1]),
                                 archived=int(prow[2]), trashed=int(prow[3])),
        files=S.FileCounts(total=int(frow[0]), total_bytes=int(frow[1]),
                           trashed=int(frow[2]), pending=int(frow[3])),
        theses=S.ThesisCounts(total=sum(by_state.values()), by_processing_state=by_state,
                              stalled=stalled),
        ai=ai,
        operations=S.OperationCounts(
            window_days=30, failed_agent_runs=int(arow[0]), blocked_agent_runs=int(arow[1]),
            failed_model_runs=ai.failed, ambiguous_model_runs=ai.ambiguous,
            failed_tool_runs=int(trow[0]), denied_tool_runs=int(trow[1]),
            thesis_processing_failures=sum(by_state.get(s, 0)
                                           for s in processing.FAILURE_STATES)),
        audit=S.AuditSummary(latest_seq=audit_row[0], latest_at=audit_row[1]),
    )


# ═════════════════════════════════ المستخدمون ═════════════════════════════════


def _member_aggregate(tid: uuid.UUID):
    """شخصٌ واحدٌ لكلّ صفّ — **ولو كانت له ثلاثُ عضويّات**. ومرساتُه العضويّة."""
    return (
        select(
            Membership.user_id.label("uid"),
            func.min(Membership.created_at).label("since"),
            func.max(Membership.created_at).label("latest"),
            func.array_agg(func.distinct(Role.key)).label("roles"),
        )
        .join(Role, Role.id == Membership.role_id)
        .where(Membership.tenant_id == tid, Role.tenant_id == tid)
        .group_by(Membership.user_id)
    ).subquery()


async def _user_row_counts(session: AsyncSession, tid: uuid.UUID, ids: list[uuid.UUID]
                           ) -> tuple[dict, dict, dict]:
    """ثلاثُ عباراتٍ **للصفحة كلّها** — لا عبارةٌ لكلّ صفّ."""
    if not ids:
        return {}, {}, {}
    owner = _owner_expr()
    projects = dict((await session.execute(
        select(owner, func.count(ResearchProject.id))
        .where(ResearchProject.tenant_id == tid, ResearchProject.deleted_at.is_(None),
               owner.in_(ids))
        .group_by(owner)
    )).all())
    files = dict((await session.execute(
        select(File.uploaded_by, func.count(File.id))
        .where(File.tenant_id == tid, File.trashed_at.is_(None), File.uploaded_by.in_(ids))
        .group_by(File.uploaded_by)
    )).all())
    runs = dict((await session.execute(
        select(AgentRun.requested_by, func.count(ModelRun.id))
        .join(AgentRun, AgentRun.id == ModelRun.agent_run_id)
        .where(ModelRun.tenant_id == tid, AgentRun.tenant_id == tid,
               AgentRun.requested_by.in_(ids), ModelRun.created_at >= _window(30))
        .group_by(AgentRun.requested_by)
    )).all())
    return projects, files, runs


async def list_users(session: AsyncSession, *, tid: uuid.UUID, locale: str,
                     search: str | None, role: str | None, active: bool | None,
                     cursor: str | None, limit: int | None) -> S.AdminUserPage:
    size = clamp(limit, DEFAULT_PAGE, MAX_PAGE)
    agg = _member_aggregate(tid)
    query = (
        select(User.id, User.full_name_ar, User.full_name_en, User.email,
               User.preferred_locale, User.is_active, User.last_login_at,
               agg.c.since, agg.c.roles)
        # **المرساةُ العضويّة**: `JOIN` لا `LEFT JOIN` — من لا عضويّةَ له لا صفَّ له.
        .join(agg, agg.c.uid == User.id)
    )
    if search:
        pattern = _like(search.strip())
        query = query.where(or_(User.email.ilike(pattern, escape="\\"),
                                User.full_name_ar.ilike(pattern, escape="\\"),
                                User.full_name_en.ilike(pattern, escape="\\")))
    if role:
        query = query.where(exists().where(
            Membership.tenant_id == tid, Membership.user_id == User.id,
            Membership.role_id == Role.id, Role.tenant_id == tid, Role.key == role))
    if active is not None:
        query = query.where(User.is_active.is_(active))
    after = decode_cursor(cursor)
    if after is not None:
        query = query.where(tuple_(agg.c.since, User.id) < tuple_(after[0], after[1]))
    rows = (await session.execute(
        query.order_by(agg.c.since.desc(), User.id.desc()).limit(size + 1))).all()

    page, more = rows[:size], len(rows) > size
    ids = [r[0] for r in page]
    projects, files, runs = await _user_row_counts(session, tid, ids)
    items = [
        S.AdminUserRow(
            user_id=r[0], display_name=_display(locale, r[1], r[2], r[3]), email=r[3],
            preferred_locale=r[4], is_active=bool(r[5]), last_login_at=r[6],
            roles=sorted(set(r[8] or [])), member_since=r[7],
            project_count=int(projects.get(r[0], 0)), file_count=int(files.get(r[0], 0)),
            attributed_model_runs_30d=int(runs.get(r[0], 0)),
        )
        for r in page
    ]
    next_cursor = encode_cursor(page[-1][7], page[-1][0]) if more and page else None
    return S.AdminUserPage(items=items, next_cursor=next_cursor)


async def user_detail(session: AsyncSession, *, tid: uuid.UUID, locale: str,
                      user_id: uuid.UUID) -> S.AdminUserDetail:
    # ══ العضويّةُ أوّلًا — ومن لا عضويّةَ له هنا «غيرُ موجود» ══
    #
    # **والرمزُ واحدٌ للحالين**: معرّفٌ لا حسابَ له، وحسابٌ في مستأجرٍ آخر.
    # فجوابان مختلفان يجعلان هذا البابَ كاشفًا لوجود حساباتٍ خارج المساحة.
    agg = _member_aggregate(tid)
    row = (await session.execute(
        select(User.id, User.full_name_ar, User.full_name_en, User.email,
               User.preferred_locale, User.is_active, User.last_login_at,
               agg.c.since, agg.c.roles, agg.c.latest)
        .join(agg, agg.c.uid == User.id)
        .where(User.id == user_id)
    )).one_or_none()
    if row is None:
        raise NotFound("admin.user_not_found")

    projects_map, files_map, runs_map = await _user_row_counts(session, tid, [user_id])
    base = S.AdminUserRow(
        user_id=row[0], display_name=_display(locale, row[1], row[2], row[3]), email=row[3],
        preferred_locale=row[4], is_active=bool(row[5]), last_login_at=row[6],
        roles=sorted(set(row[8] or [])), member_since=row[7],
        project_count=int(projects_map.get(user_id, 0)),
        file_count=int(files_map.get(user_id, 0)),
        attributed_model_runs_30d=int(runs_map.get(user_id, 0)),
    )

    owner = _owner_expr()
    owned = (await session.execute(
        select(ResearchProject.id, ResearchProject.working_title_ar,
               ResearchProject.working_title_en, _lifecycle_expr(),
               ResearchProject.created_at)
        .where(ResearchProject.tenant_id == tid, ResearchProject.deleted_at.is_(None),
               owner == user_id)
        .order_by(ResearchProject.created_at.desc(), ResearchProject.id.desc())
        .limit(DETAIL_PROJECTS + 1)
    )).all()
    projects = [
        S.AdminProjectSummary(project_id=p[0], title=_display(locale, p[1], p[2], "—"),
                              lifecycle=p[3], created_at=p[4])
        for p in owned[:DETAIL_PROJECTS]
    ]

    file_bytes = int((await session.execute(
        select(func.coalesce(func.sum(File.size_bytes), 0))
        .where(File.tenant_id == tid, File.trashed_at.is_(None), File.uploaded_by == user_id)
    )).scalar_one())
    thesis_count = int((await session.execute(
        select(func.count(Thesis.id)).join(File, File.id == Thesis.file_id)
        .where(Thesis.tenant_id == tid, File.tenant_id == tid, File.uploaded_by == user_id)
    )).scalar_one())
    latest_model = (await session.execute(
        select(func.max(ModelRun.created_at))
        .join(AgentRun, AgentRun.id == ModelRun.agent_run_id)
        .where(ModelRun.tenant_id == tid, AgentRun.tenant_id == tid,
               AgentRun.requested_by == user_id)
    )).scalar_one()
    agent_runs = int((await session.execute(
        select(func.count(AgentRun.id))
        .where(AgentRun.tenant_id == tid, AgentRun.requested_by == user_id,
               AgentRun.created_at >= _window(30))
    )).scalar_one())

    return S.AdminUserDetail(
        user=base, first_membership_at=row[7], latest_membership_at=row[9],
        projects=projects, projects_truncated=len(owned) > DETAIL_PROJECTS,
        file_bytes=file_bytes, thesis_count=thesis_count,
        ai_30d=await model_usage(session, tid, 30, requested_by=user_id),
        latest_model_activity_at=latest_model, agent_runs_30d=agent_runs,
    )


# ═════════════════════════════════ البحوث ═════════════════════════════════


async def list_projects(session: AsyncSession, *, tid: uuid.UUID, locale: str,
                        search: str | None, lifecycle: str | None,
                        owner_id: uuid.UUID | None, cursor: str | None,
                        limit: int | None) -> S.AdminProjectPage:
    size = clamp(limit, DEFAULT_PAGE, MAX_PAGE)
    owner = _owner_expr().label("owner")
    life = _lifecycle_expr().label("lifecycle")
    query = (
        select(ResearchProject.id, ResearchProject.working_title_ar,
               ResearchProject.working_title_en, ResearchProject.status, life,
               ResearchProject.current_gate, owner, ResearchProject.created_at,
               ResearchProject.updated_at)
        .where(ResearchProject.tenant_id == tid)
    )
    if search:
        pattern = _like(search.strip())
        query = query.where(or_(ResearchProject.working_title_ar.ilike(pattern, escape="\\"),
                                ResearchProject.working_title_en.ilike(pattern, escape="\\")))
    if lifecycle in ("active", "archived", "trashed"):
        query = query.where(_lifecycle_expr() == lifecycle)
    elif lifecycle is None:
        # الافتراضُ: ما ليس في السلّة — كقائمة المحفظة نفسِها.
        query = query.where(ResearchProject.deleted_at.is_(None))
    if owner_id is not None:
        query = query.where(_owner_expr() == owner_id)
    after = decode_cursor(cursor)
    if after is not None:
        query = query.where(tuple_(ResearchProject.created_at, ResearchProject.id)
                            < tuple_(after[0], after[1]))
    rows = (await session.execute(
        query.order_by(ResearchProject.created_at.desc(), ResearchProject.id.desc())
        .limit(size + 1))).all()
    page, more = rows[:size], len(rows) > size
    ids = [r[0] for r in page]

    collaborators: dict = {}
    files: dict = {}
    manuscripts: dict = {}
    if ids:
        collaborators = dict((await session.execute(
            select(ProjectMember.project_id, func.count(ProjectMember.id))
            .where(ProjectMember.tenant_id == tid, ProjectMember.project_id.in_(ids),
                   ProjectMember.removed_at.is_(None))
            .group_by(ProjectMember.project_id))).all())
        files = dict((await session.execute(
            select(ProjectFile.project_id, func.count(ProjectFile.id))
            .where(ProjectFile.tenant_id == tid, ProjectFile.project_id.in_(ids),
                   ProjectFile.state == "active")
            .group_by(ProjectFile.project_id))).all())
        manuscripts = dict((await session.execute(
            select(Manuscript.project_id, func.count(Manuscript.id))
            .where(Manuscript.tenant_id == tid, Manuscript.project_id.in_(ids))
            .group_by(Manuscript.project_id))).all())
    names = await _member_names(session, tid, {r[6] for r in page}, locale)

    items = [
        S.AdminProjectRow(
            project_id=r[0], title=_display(locale, r[1], r[2], "—"), status=r[3],
            lifecycle=r[4], current_gate=r[5], owner_user_id=r[6],
            # **ولا اسمَ إلّا لعضوٍ هنا** — مالكٌ غادر المساحةَ يبقى معرّفًا بلا اسم.
            owner_name=names.get(r[6]), created_at=r[7], updated_at=r[8],
            collaborators=int(collaborators.get(r[0], 0)), files=int(files.get(r[0], 0)),
            manuscripts=int(manuscripts.get(r[0], 0)),
        )
        for r in page
    ]
    next_cursor = encode_cursor(page[-1][7], page[-1][0]) if more and page else None
    return S.AdminProjectPage(items=items, next_cursor=next_cursor)


# ═════════════════════════════ الاستخدام ═════════════════════════════


async def _buckets(session: AsyncSession, tid: uuid.UUID, days: int, key: Any,
                   limit: int = 60) -> list[S.UsageBucket]:
    cost_known = ModelRun.cost_usd.is_not(None)
    rows = (await session.execute(
        select(
            key.label("k"),
            func.count(ModelRun.id),
            func.count(ModelRun.id).filter(ModelRun.status.in_(MODEL_FAILED)),
            func.coalesce(func.sum(ModelRun.input_tokens), 0),
            func.coalesce(func.sum(ModelRun.output_tokens), 0),
            func.coalesce(func.sum(ModelRun.cost_usd).filter(cost_known), 0),
            func.count(ModelRun.id).filter(cost_known),
        )
        .where(ModelRun.tenant_id == tid, ModelRun.created_at >= _window(days))
        .group_by(key).order_by(func.count(ModelRun.id).desc(), key).limit(limit)
    )).all()
    return [
        S.UsageBucket(key=str(r[0]) if r[0] is not None else "—", model_runs=int(r[1]),
                      failed=int(r[2]), input_tokens=int(r[3]), output_tokens=int(r[4]),
                      recorded_cost_usd=Decimal(r[5]), runs_with_cost=int(r[6]))
        for r in rows
    ]


async def usage(session: AsyncSession, *, tid: uuid.UUID, window: str) -> S.AdminUsage:
    if window not in USAGE_WINDOWS:
        raise AtheraError("admin.invalid_window", status_code=422)
    days = USAGE_WINDOWS[window]
    summary = await model_usage(session, tid, days)
    counts = (await session.execute(
        select(
            select(func.count(AgentRun.id)).where(
                AgentRun.tenant_id == tid, AgentRun.created_at >= _window(days)
            ).scalar_subquery(),
            select(func.count(ToolRun.id)).where(
                ToolRun.tenant_id == tid, ToolRun.created_at >= _window(days)
            ).scalar_subquery(),
        )
    )).one()
    lat = (await session.execute(
        select(func.count(ModelRun.id), func.avg(ModelRun.latency_ms),
               func.percentile_cont(0.5).within_group(ModelRun.latency_ms))
        .where(ModelRun.tenant_id == tid, ModelRun.created_at >= _window(days),
               ModelRun.latency_ms.is_not(None))
    )).one()
    day = func.to_char(func.date_trunc("day", ModelRun.created_at), "YYYY-MM-DD")
    by_day = sorted(await _buckets(session, tid, days, day, limit=days + 1),
                    key=lambda b: b.key)
    return S.AdminUsage(
        window_days=days, summary=summary, agent_runs=int(counts[0]),
        tool_runs=int(counts[1]),
        latency=S.LatencySummary(
            runs_with_latency=int(lat[0]),
            average_ms=int(lat[1]) if lat[1] is not None else None,
            median_ms=int(lat[2]) if lat[2] is not None else None),
        by_day=by_day,
        by_provider=await _buckets(session, tid, days, ModelRun.provider),
        by_model=await _buckets(session, tid, days, ModelRun.model),
        by_status=await _buckets(session, tid, days, ModelRun.status),
        by_operation=await _buckets(session, tid, days, ModelRun.operation),
    )


# ═════════════════════════════════ العمليات ═════════════════════════════════

OPERATION_VIEWS = ("failed", "in_progress", "all")


async def operations(session: AsyncSession, *, tid: uuid.UUID, locale: str, view: str,
                     limit: int | None) -> S.AdminOperations:
    if view not in OPERATION_VIEWS:
        raise AtheraError("admin.invalid_view", status_code=422)
    size = clamp(limit, DEFAULT_OPS, MAX_OPS)
    since = _window(OPERATIONS_WINDOW_DAYS)

    agent_q = select(AgentRun.id, AgentRun.trace_id, AgentRun.agent_key, AgentRun.status,
                     AgentRun.gate, AgentRun.started_at, AgentRun.finished_at,
                     AgentRun.requested_by, AgentRun.error.is_not(None)).where(
        AgentRun.tenant_id == tid, AgentRun.created_at >= since)
    model_q = select(ModelRun.id, ModelRun.agent_run_id, ModelRun.provider, ModelRun.model,
                     ModelRun.operation, ModelRun.status, ModelRun.latency_ms,
                     ModelRun.created_at, ModelRun.error.is_not(None)).where(
        ModelRun.tenant_id == tid, ModelRun.created_at >= since)
    tool_q = select(ToolRun.id, ToolRun.agent_run_id, ToolRun.tool_key, ToolRun.tool_kind,
                    ToolRun.status, ToolRun.duration_ms, ToolRun.created_at,
                    ToolRun.error.is_not(None)).where(
        ToolRun.tenant_id == tid, ToolRun.created_at >= since)
    stale = and_(Thesis.processing_state.in_(processing.IN_FLIGHT),
                 Thesis.processing_state_changed_at <= func.now() - processing.STALE_AFTER)
    thesis_q = select(Thesis.id, Thesis.processing_state, Thesis.failure_code,
                      Thesis.processing_state_changed_at, Thesis.processing_attempts,
                      stale).where(Thesis.tenant_id == tid)

    if view == "failed":
        agent_q = agent_q.where(AgentRun.status.in_(("failed", "blocked")))
        model_q = model_q.where(ModelRun.status.in_((*MODEL_FAILED, MODEL_AMBIGUOUS)))
        tool_q = tool_q.where(ToolRun.status.in_(("error", "denied")))
        thesis_q = thesis_q.where(or_(Thesis.processing_state.in_(processing.FAILURE_STATES),
                                      stale))
    elif view == "in_progress":
        agent_q = agent_q.where(AgentRun.status == "running")
        model_q = model_q.where(ModelRun.status == MODEL_AMBIGUOUS)
        tool_q = tool_q.where(False)
        thesis_q = thesis_q.where(Thesis.processing_state.in_(processing.IN_FLIGHT))

    agents = (await session.execute(
        agent_q.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).limit(size))).all()
    models = (await session.execute(
        model_q.order_by(ModelRun.created_at.desc(), ModelRun.id.desc()).limit(size))).all()
    tools = (await session.execute(
        tool_q.order_by(ToolRun.created_at.desc(), ToolRun.id.desc()).limit(size))).all()
    theses = (await session.execute(
        thesis_q.order_by(Thesis.processing_state_changed_at.desc().nulls_last(),
                          Thesis.id.desc()).limit(size))).all()
    names = await _member_names(session, tid, {a[7] for a in agents}, locale)

    return S.AdminOperations(
        view=view, limit=size,
        agent_runs=[S.OpAgentRun(
            run_id=a[0], trace_id=a[1], agent_key=a[2], status=a[3], gate=a[4],
            started_at=a[5], finished_at=a[6], requested_by=a[7],
            requested_by_name=names.get(a[7]), error_present=bool(a[8])) for a in agents],
        model_runs=[S.OpModelRun(
            run_id=m[0], agent_run_id=m[1], provider=m[2], model=m[3], operation=m[4],
            status=m[5], latency_ms=m[6], created_at=m[7], error_present=bool(m[8]))
            for m in models],
        tool_runs=[S.OpToolRun(
            run_id=t[0], agent_run_id=t[1], tool_key=t[2], tool_kind=t[3], status=t[4],
            duration_ms=t[5], created_at=t[6], error_present=bool(t[7])) for t in tools],
        theses=[S.OpThesis(
            thesis_id=h[0], processing_state=h[1], failure_code=h[2],
            processing_state_changed_at=h[3], processing_attempts=int(h[4] or 0),
            stalled=bool(h[5])) for h in theses],
    )
