"""فرق البحث ٢ — التعاون وسلامة التأليف | Research teams V2 (PUBRIVA).

**هذا الملفّ حارسُ العطب الذي كان يسمح بتزوير التأليف.**

المسار القديم `POST /projects/{id}/members/{member_id}/consent` كان يقرأ
العضو بمعرِّفه ويكتب موافقتَه، **ولا يسأل مَن الطالب**. فرئيسُ الفريق — بل
أيُّ مصادَقٍ في المستأجر — كان يسجّل موافقةَ أيِّ مؤلفٍ مشارك. وينتهي ذلك
بورقةٍ منشورة تحمل اسمَ من لم يوافق، وسجلٍّ يقول إنه وافق.

فيُثبت هنا عشرة:

 ١) **الترحيل يفرض الربط في القاعدة** — لا في الموجّه وحده.
 ٢) **الأربعةُ لا تُخلط**: دورٌ، وصلاحيةٌ، وإقرارُ CRediT، وتأليف.
 ٣) **الدعوةُ لا تُخزّن رمزًا خامًا**، ولا تمنح شيئًا قبل القبول.
 ٤) **رحلةٌ كاملةٌ بحسابين حقيقيين عبر HTTP** — لا استدعاءَ خدمة.
 ٥) **العزلُ بين بحثين في المستأجر الواحد**، وهو العطب الذي وقع من قبل.
 ٦) **والعزلُ بين مستأجرين** عند الموجّه لا في SQL وحدها.
 ٧) **الصلاحيةُ تُفرض**: عضويةٌ بلا صلاحيةٍ لا تفعل شيئًا.
 ٨) **الموافقةُ تصحّ ذاتيًّا وحدها**، والمالكُ لا يوافق عن شريكه.
 ٩) **CRediT إقرارٌ يُعلَن** ولا يُستنتج، وتغييرُه يُحفظ في السجلّ.
 ١٠) **سجلُّ القرارات يبقي المنسوخ**، وصندوقُ ما يحتاج فعلًا منفصلٌ عنه.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import re
import uuid

import pytest

from tests.conftest import requires_db

# لا `pytestmark` على مستوى الملفّ: نصفُ الفحوص هنا متزامنٌ يقرأ نصًّا،
# ووسمُه بـ`asyncio` يُخرج تحذيرًا لكل واحدٍ منها فيُغرق مخرَجَ CI.

REPO = pathlib.Path(__file__).resolve().parents[3]
WEB = REPO / "apps" / "web"
MIGRATION = (REPO / "infra" / "db" / "migrations" / "versions"
             / "0028_research_teams_v2.py")
SCREEN = WEB / "src" / "app" / "[locale]" / "team" / "page.tsx"

EVIDENCE = "إقرار تأليف موقَّع بخطّ اليد، محفوظ لدى عمادة البحث العلمي"


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _migration_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("_migration_0028", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ═════════════════════ ١. الترحيل ═════════════════════

def test_the_database_itself_refuses_a_self_consent_by_someone_else():
    """**الحارسُ الذي يصمد أمام موجّهٍ يُكتب غدًا.**

    إصلاحُ الموجّه وحده يُصلح اليوم: أوّلُ مسارٍ ثانٍ يلمس `project_members`
    يعيد العطب، ولا يسقط فحصٌ ينظر إلى الموجّه القديم. فالربطُ مكتوبٌ قيدًا
    في القاعدة: موافقةٌ «ذاتية» سجّلها غيرُ صاحبها ترفضها القاعدة ولو أمرها
    الكود.
    """
    text = _migration_text()
    assert "self_consent_is_the_member" in text
    assert "consent_recorded_by = user_id" in text
    # والمسارُ الإداري مسموحٌ **موثَّقًا** — والقاعدة ترفضه بلا سند.
    assert "proxy_consent_is_evidenced" in text
    assert "length(btrim(consent_evidence_ar)) > 0" in text


def test_the_migration_never_promotes_an_unattributed_consent_to_a_personal_one():
    """ما سُجِّل تحت المسار المعطوب **يُوسَم مجهولًا ولا يُرقَّى**.

    وترقيتُه صامتًا إلى «ذاتية» تعني أن نقول عن موافقةٍ لا يُعرف كاتبها إنّ
    صاحبها منحها — وهي الكذبة نفسها التي يُصلحها هذا الترحيل، مكتوبةً مرّةً
    أخرى بيد الإصلاح.
    """
    text = _migration_text()
    assert "consent_method = 'legacy_unverified'" in text
    assert "consent_method = 'self'" not in text

    from athera_api.services import team

    assert "legacy_unverified" in team.CONSENT_METHODS
    # والتطبيقُ لا يكتبها أبدًا — القائمةُ التي يُسمح بكتابتها أضيق.
    assert "legacy_unverified" not in team.WRITABLE_CONSENT_METHODS


def test_the_migration_forces_row_level_security_not_merely_enables_it():
    """`ENABLE` وحدها تترك مالك الجدول يتجاوز سياساته (ADR-0002)."""
    text = _migration_text()
    module = _migration_module()
    assert len(module.NEW_TABLES) == 3
    assert "for table in NEW_TABLES:" in text
    assert "ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in text
    assert "ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in text
    assert "tenant_id = app_current_tenant()" in text
    assert "WITH CHECK (tenant_id = app_current_tenant())" in text
    assert "TO athera_app" in text

    from athera_api.models import collaboration as model

    tables = {value.__tablename__ for value in vars(model).values()
              if hasattr(value, "__tablename__")}
    assert tables == set(module.NEW_TABLES)


def test_the_migration_is_additive_and_refuses_to_destroy_a_consent():
    text = _migration_text()
    upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
    assert "op.drop_table" not in upgrade
    assert "op.drop_column" not in upgrade

    module = _migration_module()
    assert module.revision == "0028"
    # المُكامِل يعيد توجيهها إلى "0027" بعد نزول B و C — وذلك متوقَّع.
    assert module.down_revision in ("0025", "0026", "0027")

    downgrade = text.split("def downgrade")[1]
    assert "downgrade refused" in downgrade
    assert "consent_method IN ('self', 'administrative')" in downgrade
    assert "state = 'accepted'" in downgrade

    created = set(re.findall(r'op\.create_index\(\s*"([a-z_]+)"', text))
    dropped = set(re.findall(r'op\.drop_index\(\s*"([a-z_]+)"', text))
    assert created and created == dropped
    for table in module.NEW_TABLES:
        assert f'op.drop_table("{table}")' in downgrade
    # قيدُ check يُحذف بـSQL صريح — واجهةُ alembic تعيد تطبيق الاصطلاح.
    assert 'type_="check"' not in text


def test_the_migration_vocabulary_matches_the_service_exactly():
    """مفردةٌ تفترق بين القاعدة والخدمة تُنتج قيمةً ترفضها القاعدة صامتةً."""
    module = _migration_module()
    from athera_api.services import team

    assert tuple(team.PROJECT_PERMISSIONS) == module.PROJECT_PERMISSIONS
    assert team.INVITATION_STATES == module.INVITATION_STATES
    assert team.MEMBER_ACCESS_STATES == module.MEMBER_ACCESS_STATES
    assert team.CONSENT_STATES == module.CONSENT_STATES
    assert team.CONSENT_METHODS == module.CONSENT_METHODS
    assert team.MEMBER_EVENT_KINDS == module.MEMBER_EVENT_KINDS


def test_no_migration_or_service_stores_a_raw_invitation_token():
    text = _migration_text()
    assert "token_hash" in text
    assert "length(token_hash) = 64" in text
    assert re.search(r'sa\.Column\(\s*"token"', text) is None

    from athera_api.models.collaboration import ProjectInvitation

    columns = set(ProjectInvitation.__table__.columns.keys())
    assert "token_hash" in columns
    assert "token" not in columns


# ═════════════════════ ٢. الأربعةُ لا تُخلط ═════════════════════

def test_a_default_permission_set_never_hands_everything_to_a_team_member():
    """**العضويةُ وحدها لا تمنح كلَّ شيء**، والدورُ ليس صلاحية.

    والحالتان مكتوبتان هنا لأنهما تقعان في كل فريق: محلّلٌ إحصائيّ له
    مساهمةُ تحليلٍ ولا إدارةَ له على المشروع، ومشرفٌ يراجع المنهجية ولا
    يحرّر البيانات.
    """
    from athera_api.services import team

    everything = set(team.PROJECT_PERMISSIONS)
    for role, granted in team.ROLE_DEFAULT_PERMISSIONS.items():
        if role == "principal_investigator":
            continue
        assert set(granted) < everything, role
        assert "manage_team" not in granted, role

    statistician = set(team.default_permissions("statistician"))
    assert "manage_data" in statistician
    assert "manage_team" not in statistician
    assert "approve_scientific_candidates" not in statistician

    supervisor = set(team.default_permissions("supervisor"))
    assert "review_scientific_candidates" in supervisor
    assert "manage_data" not in supervisor
    assert "edit_research_content" not in supervisor

    # ودورٌ يُضاف غدًا بلا مدخلٍ هنا يأخذ الاطّلاع وحده — لا كلَّ شيء.
    assert team.default_permissions("a_role_invented_tomorrow") == ("view_project",)


def test_adding_a_member_cannot_bind_an_account_from_the_request_body():
    """**الربطُ بحساب لا يُقبل من جسم الطلب.**

    وكان `MemberCreateRequest` يحمل `user_id`، فكان أيُّ مصادَقٍ يكتب
    معرِّف زميله فيصير الزميل عضوًا في بحثٍ لم يدخله ولم يوافق عليه.
    """
    from athera_api.schemas.team import MemberCreateRequest

    assert "user_id" not in MemberCreateRequest.model_fields
    from athera_api.routers import team as router

    source = pathlib.Path(router.__file__).read_text(encoding="utf-8")
    assert "user_id=None" in source


def test_no_route_records_consent_for_another_member_by_id():
    """المسارُ الشخصيّ **لا يقبل معرِّف عضوٍ أصلًا** — فلا مكان لاسم غيرك."""
    from athera_api.routers import team as router

    paths = {r.path for r in router.router.routes}
    assert "/api/v1/projects/{project_id}/members/me/consent" in paths
    assert "/api/v1/projects/{project_id}/members/{member_id}/consent" not in paths
    # والمسارُ الإداري موجودٌ **باسمه**، فلا يُقرأ كأنه الشخصيّ.
    assert ("/api/v1/projects/{project_id}/members/{member_id}"
            "/administrative-consent") in paths


def test_the_authorship_agreement_records_who_consented_and_how():
    """**العطبُ نفسه كان في اتفاق التأليف** (`services/thesis/rights.py`).

    كان يكتب `consent_status = 'granted'` لأيّ اتفاقٍ بمعرِّفه ولا يسأل مَن
    الطالب، فتفتح بوّابة GT1 على ورقةٍ تحمل اسمَ من لم يوافق. فأُضيفت
    أعمدةُ النسبة في الترحيل، وصار للموافقة طريقان معلَنان لا طريقٌ صامت.
    """
    text = _migration_text()
    assert 'op.add_column("authorship_agreements"' in text
    assert '"consent_recorded_by"' in text
    # القيدُ يُبنى باسمٍ مجرَّد ويُحذف بالاسم الكامل — والاصطلاح يبني الفرق.
    assert 'op.create_check_constraint(name, "authorship_agreements", expression)' \
        in text
    assert 'f"ck_authorship_agreements_{constraint}"' in text

    from athera_api.models.thesis import AuthorshipAgreement

    columns = set(AuthorshipAgreement.__table__.columns.keys())
    assert {"consent_recorded_by", "consent_method",
            "consent_evidence_ar"} <= columns

    from athera_api.services.thesis import rights

    source = pathlib.Path(rights.__file__).read_text(encoding="utf-8")
    # النسبةُ تُقرأ من الطرف نفسه — لا من مجرّد وجود طالبٍ مصادَق.
    assert "party.user_id is not None and party.user_id == actor_user_id" in source
    assert 'method = "self"' in source
    assert 'method = "administrative"' in source


def test_credit_roles_are_never_inferred_from_activity():
    """§24 — لا مسار في المنصّة يشتقّ دور CRediT من فعلٍ وقع."""
    from athera_api.services import collaboration

    source = pathlib.Path(collaboration.__file__).read_text(encoding="utf-8")
    for forbidden in ("infer_credit", "suggest_credit", "auto_credit",
                      "derive_credit"):
        assert forbidden not in source
    assert "never infers them from platform activity" in source


# ═════════════ ٣. رحلةُ حسابين حقيقيين عبر HTTP ═════════════
#
# **الخدمةُ تُستدعى مباشرةً في الفحوص أعلاه، والباحث لا يستدعيها.** بينه
# وبينها موجّهٌ ومصادقةٌ وجلسةُ مستأجرٍ وصلاحية. وفحصٌ يبلغ الخدمة من غير
# هذا الطريق يثبت أنّ الحساب صحيح، ولا يثبت أنّ أحدًا يستطيع بلوغه.


def _client(tenant_id: uuid.UUID, user_id: uuid.UUID):
    """عميلٌ يحمل رمزًا حقيقيًّا — لا تجاوزَ للمصادقة في فحصٍ يدّعي إثباتها."""
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    token = issue_access_token(user_id=user_id, tenant_id=tenant_id,
                               roles=["researcher"], mfa_satisfied=True)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})


async def _second_user(tenant_id: uuid.UUID) -> dict:
    """حسابٌ ثانٍ حقيقيّ **في المستأجر نفسه** — بعضويّته ودوره.

    و`two_tenants` تعطي حسابًا واحدًا لكل مستأجر، وهو لا يكفي: القبولُ فعلُ
    طرفٍ ثانٍ، وفحصٌ يقبل بحساب الداعي لا يفحص شيئًا.
    """
    from sqlalchemy import select

    from athera_api.db import system_session
    from athera_api.models.identity import Membership, Role, User
    from athera_api.security import hash_password

    slug = uuid.uuid4().hex[:10]
    async with system_session() as session:
        user = User(
            email=f"second-{slug}@example.test",
            password_hash=hash_password("correct-horse-battery-staple"),
            full_name_ar="شريكة البحث", full_name_en="Research partner")
        session.add(user)
        await session.flush()
        role = (
            await session.execute(
                select(Role).where(Role.tenant_id == tenant_id,
                                   Role.key == "co_author"))
        ).scalar_one()
        session.add(Membership(tenant_id=tenant_id, user_id=user.id,
                               role_id=role.id))
        return {"user_id": user.id, "email": user.email}


async def _new_project(client, title: str) -> str:
    """بحثٌ يُنشأ **من الطريق الذي يسلكه الباحث** — فيُعرف مالكُه."""
    created = await client.post("/api/v1/workspace/projects",
                                json={"title_ar": title})
    assert created.status_code == 201, created.text
    return created.json()["id"]


@requires_db
@pytest.mark.asyncio
async def test_a_second_researcher_joins_by_accepting_with_their_own_account(
        two_tenants):
    """**الرحلةُ كاملةً بحسابين حقيقيين**: دعوةٌ، ثمّ قبولٌ، ثمّ ربطُ حساب.

    ولا تُستدعى خدمةٌ في هذا الفحص: كلُّ خطوةٍ طلبٌ يحمل رمزًا، كما يفعل
    المتصفّح. فإن سقط الموجّه من `main.py` سقط هذا الفحص.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ الفريق")

        # المالكُ عضوٌ بصلاحياته — مشتقًّا من نسبة إنشاء البحث لا من اسم.
        members = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        assert members.status_code == 200, members.text
        assert len(members.json()) == 1
        me = members.json()[0]
        assert me["user_id"] == str(owner)
        assert me["is_account_linked"] is True
        assert me["role"] == "principal_investigator"
        assert "manage_team" in me["permissions"]
        # **والعضويةُ ليست تأليفًا** — ولا حتى للمالك.
        assert me["is_author"] is False
        assert me["consent_state"] == "not_requested"

        invited = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "statistician"})
        assert invited.status_code == 201, invited.text
        token = invited.json()["token"]
        invitation_id = invited.json()["id"]
        assert invited.json()["state"] == "invited"
        assert invited.json()["accepted_user_id"] is None
        # اقتراحُ صلاحياتٍ لا كلُّ شيء.
        assert set(invited.json()["proposed_permissions"]) == {
            "view_project", "manage_data", "review_scientific_candidates"}

        # الدعوةُ لم تمنح شيئًا بعد — ولا عضوَ ثانيًا في القائمة.
        listing = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        assert len(listing.json()) == 1
        pending = await owner_http.get(
            f"/api/v1/projects/{project_id}/invitations")
        assert [row["state"] for row in pending.json()] == ["invited"]
        # ولا يُعاد الرمزُ في أيّ قراءةٍ بعد الإنشاء.
        assert "token" not in pending.json()[0]

    # ── الطرفُ الثاني يقبل بحسابه هو ──
    async with _client(tid, partner["user_id"]) as partner_http:
        # وقبلَ القبول لا يرى البحث أصلًا.
        blocked = await partner_http.get(f"/api/v1/projects/{project_id}/members")
        assert blocked.status_code == 403, blocked.text
        assert blocked.json()["error"]["code"] == "team.not_a_project_member"

        accepted = await partner_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        assert accepted.status_code == 200, accepted.text
        member = accepted.json()
        # **العضويةُ رُبطت بالحساب المصادَق الذي قبِل** — لا باسمٍ ولا ببريد.
        assert member["user_id"] == str(partner["user_id"])
        assert member["is_account_linked"] is True
        assert member["role"] == "statistician"
        assert set(member["permissions"]) == {
            "view_project", "manage_data", "review_scientific_candidates"}
        partner_member_id = member["id"]

        # وصار يبلغ البحث الذي دُعي إليه.
        allowed = await partner_http.get(f"/api/v1/projects/{project_id}/members")
        assert allowed.status_code == 200, allowed.text
        assert len(allowed.json()) == 2

        # **والصلاحيةُ تُفرض**: لا إدارةَ فريقٍ له، فلا يدعو أحدًا.
        refused = await partner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": "third@example.test", "display_name": "ثالث",
                  "role": "co_author"})
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "team.permission_required"

        # ولا يسحب دعوةً، ولا يوقف عضوًا.
        revoked = await partner_http.delete(
            f"/api/v1/projects/{project_id}/invitations/{invitation_id}")
        assert revoked.status_code == 403

    # ── والرمزُ المستعمَل لا يُستعمل مرّتين ──
    async with _client(tid, partner["user_id"]) as partner_http:
        again = await partner_http.post("/api/v1/invitations/accept",
                                        json={"token": token})
        assert again.status_code == 409, again.text
        assert again.json()["error"]["code"] == "team.invitation_not_open"

    assert partner_member_id


@requires_db
@pytest.mark.asyncio
async def test_an_invitation_is_refused_to_an_account_it_was_not_issued_to(
        two_tenants):
    """رمزٌ صحيحٌ في يدٍ أخرى **لا يُقبل**.

    وإلّا صار تسريبُ الرابط في محادثةٍ عامّة بابًا مفتوحًا إلى بيانات البحث:
    من قرأه أوّلًا صار عضوًا، ولا يعرف الفريق كيف دخل.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    invited = await _second_user(tid)
    bystander = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثٌ لدعوةٍ مسرَّبة")
        created = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": invited["email"], "display_name": "المدعوّة",
                  "role": "co_author"})
        token = created.json()["token"]

    async with _client(tid, bystander["user_id"]) as other_http:
        stolen = await other_http.post("/api/v1/invitations/accept",
                                       json={"token": token})
        assert stolen.status_code == 403, stolen.text
        assert stolen.json()["error"]["code"] == "team.invitation_not_yours"

    # والدعوةُ ما زالت قائمةً لصاحبتها — لم يُحرقها من حاول.
    async with _client(tid, invited["user_id"]) as invited_http:
        accepted = await invited_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["user_id"] == str(invited["user_id"])


@requires_db
@pytest.mark.asyncio
async def test_an_expired_invitation_does_not_lock_the_person_out_forever(
        two_tenants):
    """**نسيانُ الردّ ليس حظرًا دائمًا.**

    والفهرسُ الجزئيّ يمنع دعوتين حيّتين لبريدٍ واحد — وهو صواب. لكنّ دعوةً
    انتهت مهلتُها تبقى `invited` ما لم يمرّ بها أحد، فتمنع دعوةً جديدةً إلى
    الأبد. فالدعوةُ الجديدة تحصد القديمة أوّلًا، والحصادُ يُكتب في السجلّ.
    """
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.collaboration import ProjectInvitation

    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ المهلة")
        first = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        assert first.status_code == 201, first.text

        # دعوةٌ ثانيةٌ وهي حيّة تُرفض — رمزان يعملان ليسا صوابًا.
        duplicate = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        assert duplicate.status_code == 409, duplicate.text

    # تُدفع المهلة إلى الماضي كما يفعل الزمن.
    async with tenant_session(tid, owner) as session:
        row = (await session.execute(
            select(ProjectInvitation).where(
                ProjectInvitation.id == uuid.UUID(first.json()["id"])))
        ).scalar_one()
        row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)

    async with _client(tid, owner) as owner_http:
        renewed = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        assert renewed.status_code == 201, renewed.text
        assert renewed.json()["token"] != first.json()["token"]

        states = {row["id"]: row["state"] for row in
                  (await owner_http.get(
                      f"/api/v1/projects/{project_id}/invitations")).json()}
        assert states[first.json()["id"]] == "expired"
        assert states[renewed.json()["id"]] == "invited"

    # والرمزُ المنتهي لا يُقبل ولو حمله صاحبه.
    async with _client(tid, partner["user_id"]) as partner_http:
        stale = await partner_http.post("/api/v1/invitations/accept",
                                        json={"token": first.json()["token"]})
        assert stale.status_code == 409, stale.text
        assert stale.json()["error"]["code"] == "team.invitation_not_open"


# ═════════════ ٤. الموافقةُ فعلُ صاحبها ═════════════

@requires_db
@pytest.mark.asyncio
async def test_a_project_leader_cannot_consent_for_a_coauthor_over_http(two_tenants):
    """§24 — **العطبُ الذي أوجد هذا المسار كلَّه.**

    الرئيسُ يُعلن شريكتَه مؤلفةً — وهذا حقُّه. ثمّ يحاول أن يوافق عنها،
    فيُرفض في ثلاث نقاط: لا مسار يقبل معرِّفها للموافقة الشخصية، والمسارُ
    الإداري يلزمه سندٌ مكتوب ويُوسم بأنه ليس موافقتها، والقاعدة ترفض
    «ذاتيّةً» ليست بيد صاحبها.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ الموافقة")
        created = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        token = created.json()["token"]

    async with _client(tid, partner["user_id"]) as partner_http:
        accepted = await partner_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        member_id = accepted.json()["id"]
        # **القبولُ ليس موافقةً على التأليف، ولا إعلانَ تأليف.**
        assert accepted.json()["is_author"] is False
        assert accepted.json()["consent_state"] == "not_requested"

    async with _client(tid, owner) as owner_http:
        # الإعلانُ حقُّ الفريق؛ والموافقةُ ليست كذلك.
        declared = await owner_http.put(
            f"/api/v1/projects/{project_id}/members/{member_id}/authorship",
            json={"is_author": True, "author_position": 2})
        assert declared.status_code == 200, declared.text
        assert declared.json()["is_author"] is True
        assert declared.json()["consent_state"] == "not_requested"

        requested = await owner_http.post(
            f"/api/v1/projects/{project_id}/members/{member_id}/consent-request")
        assert requested.status_code == 200, requested.text
        assert requested.json()["consent_state"] == "pending"

        # ══ المحاولةُ التي كانت تنجح ══
        forged = await owner_http.post(
            f"/api/v1/projects/{project_id}/members/{member_id}/consent")
        assert forged.status_code == 404, forged.text

        # والمسارُ الإداري بلا سندٍ يُرفض.
        bare = await owner_http.post(
            f"/api/v1/projects/{project_id}/members/{member_id}"
            "/administrative-consent", json={"evidence_ar": "موافق"})
        assert bare.status_code == 422, bare.text

        # وموافقةُ المالك عن نفسه لا تمرّ من الباب الإداري.
        own = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        owner_member_id = next(
            row["id"] for row in own.json() if row["user_id"] == str(owner))
        sideways = await owner_http.post(
            f"/api/v1/projects/{project_id}/members/{owner_member_id}"
            "/administrative-consent", json={"evidence_ar": EVIDENCE})
        assert sideways.status_code == 403, sideways.text
        assert sideways.json()["error"]["code"] == \
            "team.use_the_personal_consent_route"

        # وحالُ الشريكة لم تتغيّر بأيٍّ من المحاولات.
        still = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        row = next(m for m in still.json() if m["id"] == member_id)
        assert row["consent_state"] == "pending"
        assert row["consent_recorded_at"] is None

    # ── وهي وحدها تستطيع ──
    async with _client(tid, partner["user_id"]) as partner_http:
        consented = await partner_http.post(
            f"/api/v1/projects/{project_id}/members/me/consent",
            json={"granted": True})
        assert consented.status_code == 200, consented.text
        body = consented.json()
        assert body["consent_state"] == "granted"
        assert body["consent_method"] == "self"
        assert body["consent_recorded_by"] == str(partner["user_id"])
        assert body["consent_needs_recollection"] is False


@requires_db
@pytest.mark.asyncio
async def test_the_database_refuses_a_self_consent_recorded_by_another_account(
        two_tenants):
    """**الطبقةُ الثالثة**: ولو التفّ كودٌ على الموجّه والخدمة معًا.

    فيُكتب هنا مباشرةً في القاعدة ما كان الموجّهُ القديم يكتبه: موافقةٌ
    ذاتيّةٌ سجّلها غيرُ صاحبها. والقاعدة ترفضها، فلا يبقى للعطب مكانٌ يعود
    منه.
    """
    from sqlalchemy.exc import IntegrityError

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ProjectMember, ResearchProject

    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with tenant_session(tid, owner) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="بحثُ القيد",
                                  status="planned")
        session.add(project)
        await session.flush()
        member = ProjectMember(
            tenant_id=tid, project_id=project.id, user_id=partner["user_id"],
            display_name="شريكة البحث", role="co_author", access_state="active",
            is_author=True, consent_state="pending")
        session.add(member)
        await session.flush()
        member_id = member.id

    with pytest.raises(IntegrityError) as caught:
        async with tenant_session(tid, owner) as session:
            row = await session.get(ProjectMember, member_id)
            row.consent_state = "granted"
            row.consent_recorded_at = dt.datetime.now(dt.UTC)
            # **المالك يدّعي أنها وافقت بنفسها.**
            row.consent_recorded_by = owner
            row.consent_method = "self"
            await session.flush()
    assert "self_consent_is_the_member" in str(caught.value)


@requires_db
@pytest.mark.asyncio
async def test_an_authorship_agreement_consent_is_refused_for_someone_else(
        two_tenants):
    """**نفسُ العطب في بوّابة GT1، مفحوصًا عبر HTTP.**

    والطرفُ هنا بلا حسابٍ مربوط — وهي الحالُ التي يُنشئها مسارُ إضافة
    المؤلف اليوم. فلا يملك «موافقةً ذاتية» أصلًا: لا سبيل إلى إثبات أنه
    هو. فتُرفض الموافقةُ الصامتة، وتُقبل بسندٍ مكتوبٍ موسومةً بأنها إدارية.
    """
    from athera_api.db import tenant_session
    from athera_api.models.thesis import PublicationOpportunity, Thesis

    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]

    async with tenant_session(tid, owner) as session:
        thesis = Thesis(tenant_id=tid, title_ar="رسالةُ الموافقة",
                        degree="phd", rights_basis="author_owned")
        session.add(thesis)
        await session.flush()
        opportunity = PublicationOpportunity(
            tenant_id=tid, thesis_id=thesis.id,
            opportunity_kind="independent_question", paper_kind="extraction",
            working_title_ar="ورقةٌ من الرسالة")
        session.add(opportunity)
        await session.flush()
        opportunity_id = opportunity.id

    async with _client(tid, owner) as http:
        added = await http.post(f"/api/v1/opportunities/{opportunity_id}/authors",
                                json={"party_kind": "person",
                                      "display_name": "أ. د. سعاد الحربي",
                                      "author_position": 2,
                                      "credit_roles": ["supervision"]})
        assert added.status_code == 201, added.text
        agreement_id = added.json()["agreement_id"]
        assert added.json()["consent_status"] == "pending"

        # ══ المحاولةُ التي كانت تنجح: موافقةٌ صامتةٌ عن الغير ══
        silent = await http.post(
            f"/api/v1/opportunities/{opportunity_id}/authors/{agreement_id}/consent")
        assert silent.status_code == 422, silent.text
        assert silent.json()["error"]["code"] == "thesis.consent_is_personal"

        # وسندٌ قصيرٌ لا يكفي — «موافق» ليست سندًا.
        thin = await http.post(
            f"/api/v1/opportunities/{opportunity_id}/authors/{agreement_id}/consent",
            json={"evidence_ar": "موافق"})
        assert thin.status_code == 422, thin.text

        documented = await http.post(
            f"/api/v1/opportunities/{opportunity_id}/authors/{agreement_id}/consent",
            json={"evidence_ar": EVIDENCE})
        assert documented.status_code == 200, documented.text
        assert documented.json()["consent_status"] == "granted"

    # والنسبةُ **مخزَّنة**: مَن سجّلها، وبأيّ طريق — لا «مُوافَقٌ عليه» وحدها.
    async with tenant_session(tid, owner) as session:
        from athera_api.models.thesis import AuthorshipAgreement

        row = await session.get(AuthorshipAgreement, uuid.UUID(agreement_id))
        assert row.consent_method == "administrative"
        assert row.consent_recorded_by == owner
        assert row.consent_evidence_ar == EVIDENCE


# ═════════════ ٥. العزل: بين بحثين، وبين مستأجرين ═════════════

@requires_db
@pytest.mark.asyncio
async def test_a_member_of_one_project_never_reaches_another_in_the_same_tenant(
        two_tenants):
    """**العطبُ الذي وقع في هذا المنتج من قبل.**

    RLS تعزل المستأجرين ولا تعزل بحثين في المستأجر الواحد. فشريكةٌ دُعيت
    إلى بحثٍ واحد لا تبلغ الثاني، ولا تعدّل عضوًا فيه، ولو عرفت معرِّفه.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        invited_project = await _new_project(owner_http, "البحثُ المدعوّة إليه")
        other_project = await _new_project(owner_http, "بحثٌ آخر للمالك نفسه")
        created = await owner_http.post(
            f"/api/v1/projects/{invited_project}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        token = created.json()["token"]
        others = await owner_http.get(f"/api/v1/projects/{other_project}/members")
        other_member_id = others.json()[0]["id"]

    async with _client(tid, partner["user_id"]) as partner_http:
        await partner_http.post("/api/v1/invitations/accept", json={"token": token})

        ok = await partner_http.get(f"/api/v1/projects/{invited_project}/members")
        assert ok.status_code == 200, ok.text

        for path in (f"/api/v1/projects/{other_project}/members",
                     f"/api/v1/projects/{other_project}/decisions",
                     f"/api/v1/projects/{other_project}/member-events",
                     f"/api/v1/projects/{other_project}/decisions/inbox"):
            leaked = await partner_http.get(path)
            assert leaked.status_code == 403, (path, leaked.text)
            assert leaked.json()["error"]["code"] == "team.not_a_project_member"

        # ولا تعدّل عضوًا في البحث الآخر ولو حملت معرِّفه.
        crossed = await partner_http.put(
            f"/api/v1/projects/{other_project}/members/{other_member_id}/credit",
            json={"credit_roles": ["software"]})
        assert crossed.status_code == 403, crossed.text

        # ولا تُهرّب عضوَ بحثٍ آخر عبر مسار بحثها — القراءة بالمعرِّفين معًا.
        smuggled = await partner_http.put(
            f"/api/v1/projects/{invited_project}/members/{other_member_id}/credit",
            json={"credit_roles": ["software"]})
        assert smuggled.status_code in (403, 404), smuggled.text


@requires_db
@pytest.mark.asyncio
async def test_the_other_tenant_is_refused_at_the_route_not_only_in_sql(two_tenants):
    """العزلُ يُفحص عند الموجّه: لو سقطت RLS، هل يمنع التطبيق؟"""
    a, b = two_tenants["a"], two_tenants["b"]

    async with _client(a["tenant_id"], a["user_id"]) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ المستأجر الأوّل")

    async with _client(b["tenant_id"], b["user_id"]) as stranger:
        for path in (f"/api/v1/projects/{project_id}/members",
                     f"/api/v1/projects/{project_id}/invitations",
                     f"/api/v1/projects/{project_id}/decisions"):
            refused = await stranger.get(path)
            # لا يُخبَر الغريبُ بوجود البحث أصلًا.
            assert refused.status_code in (403, 404), (path, refused.text)
            assert refused.json()["error"]["code"] in (
                "team.project_not_found", "team.not_a_project_member")


# ═════════════ ٦. CRediT إقرارٌ، والقرارُ سجلّ ═════════════

@requires_db
@pytest.mark.asyncio
async def test_credit_is_declared_by_the_researcher_and_kept_historically(
        two_tenants):
    """§24 — الإقرارُ يُعدَّل، **وما كان قبله يبقى مكتوبًا**.

    ونزاعُ التأليف يُحسم بالسجلّ لا بالحال الراهن: من غيّر، ومتى، وما الذي
    كان قبله. وحالٌ يُكتب فوق سابقه يجعل الشاشة تقول ما هو الآن ولا تقول
    كيف صار.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ الإقرارات")
        created = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "statistician"})
        token = created.json()["token"]

    async with _client(tid, partner["user_id"]) as partner_http:
        accepted = await partner_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        member_id = accepted.json()["id"]
        assert accepted.json()["credit_roles"] == []

        # صاحبةُ الإقرار تعدّل إقرارَها بلا صلاحية إدارة.
        first = await partner_http.put(
            f"/api/v1/projects/{project_id}/members/{member_id}/credit",
            json={"credit_roles": ["formal_analysis"]})
        assert first.status_code == 200, first.text
        assert first.json()["credit_roles"] == ["formal_analysis"]
        assert first.json()["credit_labels"] == ["التحليل الشكلي"]

        second = await partner_http.put(
            f"/api/v1/projects/{project_id}/members/{member_id}/credit",
            json={"credit_roles": ["formal_analysis", "data_curation"]})
        assert second.status_code == 200, second.text

        # ومفردةٌ خارج الأربع عشرة تُرفض — لا اختراعَ دورٍ يبرّر دعوى.
        invented = await partner_http.put(
            f"/api/v1/projects/{project_id}/members/{member_id}/credit",
            json={"credit_roles": ["chief_visionary"]})
        assert invented.status_code == 422, invented.text

        events = await partner_http.get(
            f"/api/v1/projects/{project_id}/member-events")
        assert events.status_code == 200, events.text
        changes = [row for row in events.json()
                   if row["event_kind"] == "credit_changed"]
        assert len(changes) == 2
        assert changes[0]["state_before"]["credit_roles"] == []
        assert changes[0]["state_after"]["credit_roles"] == ["formal_analysis"]
        assert changes[1]["state_before"]["credit_roles"] == ["formal_analysis"]
        assert changes[1]["actor_user_id"] == str(partner["user_id"])

    # وتغييرُ الدور **لا يغيّر الصلاحيات** بأثرٍ جانبي.
    async with _client(tid, owner) as owner_http:
        before = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        granted = next(row["permissions"] for row in before.json()
                       if row["id"] == member_id)
        changed = await owner_http.patch(
            f"/api/v1/projects/{project_id}/members/{member_id}/role",
            json={"role": "supervisor"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["role"] == "supervisor"
        assert changed.json()["permissions"] == granted


@requires_db
@pytest.mark.asyncio
async def test_the_ledger_keeps_the_superseded_decision_and_the_inbox_is_separate(
        two_tenants):
    """**سجلٌّ تاريخيّ وصندوقُ فعلٍ — قائمتان لا واحدة.**

    وخلطُهما يجعل الفريق يقرأ سطرًا لا يعرف أينتظره أم انتهى، فيتعلّم
    تجاهل القائمة كلَّها.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ السجلّ")

        first = await owner_http.post(f"/api/v1/projects/{project_id}/decisions",
                                      json={"decision_kind": "question",
                                            "statement_ar": "ما أثر التحول الرقمي؟"})
        assert first.status_code == 201, first.text
        second = await owner_http.post(
            f"/api/v1/projects/{project_id}/decisions",
            json={"decision_kind": "question",
                  "statement_ar": "ما أثره في المنشآت الصغيرة؟",
                  "supersedes_id": first.json()["id"]})
        assert second.status_code == 201, second.text

        ledger = await owner_http.get(f"/api/v1/projects/{project_id}/decisions")
        rows = {row["id"]: row for row in ledger.json()}
        assert len(rows) == 2
        old, new = rows[first.json()["id"]], rows[second.json()["id"]]
        # **المنسوخ باقٍ، وموسومٌ بأنه منسوخ، ويشير إلى ناسخه.**
        assert old["is_superseded"] is True
        assert old["is_current"] is False
        assert old["superseded_by_id"] == new["id"]
        assert new["is_current"] is True
        assert new["supersedes_id"] == old["id"]

        # والصندوقُ لا يحمل شيئًا من هذا — لا قرارَ ينتظر فعلًا.
        inbox = await owner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        assert inbox.status_code == 200, inbox.text
        assert inbox.json() == []

        created = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        token = created.json()["token"]

        # ودعوةٌ قائمةٌ **بندٌ يحتاج فعلًا** — لا سطرٌ في السجلّ التاريخي.
        with_invite = await owner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        kinds = [row["kind"] for row in with_invite.json()]
        assert kinds == ["invitation_reply"]
        assert with_invite.json()[0]["is_mine"] is False

    async with _client(tid, partner["user_id"]) as partner_http:
        accepted = await partner_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        member_id = accepted.json()["id"]

    async with _client(tid, owner) as owner_http:
        # والدعوةُ اختفت من الصندوق حين وقع الفعل — لأنه قراءةٌ للواقع.
        settled = await owner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        assert settled.json() == []

        await owner_http.put(
            f"/api/v1/projects/{project_id}/members/{member_id}/authorship",
            json={"is_author": True, "author_position": 2})
        await owner_http.post(
            f"/api/v1/projects/{project_id}/members/{member_id}/consent-request")

        waiting = await owner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        assert [row["kind"] for row in waiting.json()] == ["author_consent"]
        # وهو بندٌ ينتظر غيرَه — والفرقُ معروضٌ لا مخفيّ.
        assert waiting.json()[0]["is_mine"] is False

    async with _client(tid, partner["user_id"]) as partner_http:
        mine = await partner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        assert mine.json()[0]["is_mine"] is True

        await partner_http.post(
            f"/api/v1/projects/{project_id}/members/me/consent",
            json={"granted": True})
        cleared = await partner_http.get(
            f"/api/v1/projects/{project_id}/decisions/inbox")
        assert cleared.json() == []


# ═════════════ ٧. دورةُ الحياة: الإيقاف والخروج ═════════════

@requires_db
@pytest.mark.asyncio
async def test_suspending_a_member_stops_access_without_erasing_the_record(
        two_tenants):
    """إيقافُ الوصول حالٌ، **والحذفُ إتلاف**.

    وموافقةُ شريكةٍ على تأليفٍ سُجِّلت تبقى كما سُجِّلت بعد خروجها: هي واقعةٌ
    وقعت، والورقةُ تُنشر بعد سنة ويُسأل عنها بعدها بسنتين.
    """
    a = two_tenants["a"]
    tid, owner = a["tenant_id"], a["user_id"]
    partner = await _second_user(tid)

    async with _client(tid, owner) as owner_http:
        project_id = await _new_project(owner_http, "بحثُ دورة الحياة")
        created = await owner_http.post(
            f"/api/v1/projects/{project_id}/invitations",
            json={"email": partner["email"], "display_name": "شريكة البحث",
                  "role": "co_author"})
        token = created.json()["token"]

    async with _client(tid, partner["user_id"]) as partner_http:
        accepted = await partner_http.post("/api/v1/invitations/accept",
                                           json={"token": token})
        member_id = accepted.json()["id"]

    async with _client(tid, owner) as owner_http:
        suspended = await owner_http.patch(
            f"/api/v1/projects/{project_id}/members/{member_id}/access",
            json={"access_state": "suspended"})
        assert suspended.status_code == 200, suspended.text
        assert suspended.json()["access_state"] == "suspended"

    async with _client(tid, partner["user_id"]) as partner_http:
        stopped = await partner_http.get(f"/api/v1/projects/{project_id}/members")
        assert stopped.status_code == 403, stopped.text
        assert stopped.json()["error"]["code"] == "team.access_suspended"

    async with _client(tid, owner) as owner_http:
        restored = await owner_http.patch(
            f"/api/v1/projects/{project_id}/members/{member_id}/access",
            json={"access_state": "active"})
        assert restored.json()["access_state"] == "active"

        # **ولا يبقى البحثُ بلا من يديره.**
        own = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        owner_member_id = next(row["id"] for row in own.json()
                               if row["user_id"] == str(owner))
        orphaned = await owner_http.patch(
            f"/api/v1/projects/{project_id}/members/{owner_member_id}/access",
            json={"access_state": "removed"})
        assert orphaned.status_code == 409, orphaned.text
        assert orphaned.json()["error"]["code"] == "team.last_manager"

    async with _client(tid, partner["user_id"]) as partner_http:
        left = await partner_http.post(
            f"/api/v1/projects/{project_id}/members/me/leave")
        assert left.status_code == 200, left.text
        gone = await partner_http.get(f"/api/v1/projects/{project_id}/members")
        assert gone.status_code == 403
        assert gone.json()["error"]["code"] == "team.access_removed"

    # والصفُّ باقٍ في السجلّ بحاله، وخروجُها مكتوبٌ باسمها.
    async with _client(tid, owner) as owner_http:
        rows = await owner_http.get(f"/api/v1/projects/{project_id}/members")
        member = next(row for row in rows.json() if row["id"] == member_id)
        assert member["access_state"] == "removed"
        assert member["display_name"] == "شريكة البحث"
        events = await owner_http.get(
            f"/api/v1/projects/{project_id}/member-events")
        kinds = [row["event_kind"] for row in events.json()]
        assert "access_suspended" in kinds
        assert "access_restored" in kinds
        assert "left" in kinds


# ═════════════════════ ٨. الشاشة ═════════════════════

def test_the_team_screen_shows_each_distinction_the_backend_keeps_apart():
    """شاشةٌ تعرض «عضو» وحدها تجعل القارئ يفترض الأربعة.

    فما يُطلب هنا أن يظهر لكل عضو: أهو مربوطٌ بحساب، ودورُه، وملخّصُ
    صلاحياته، وإقراراتُ CRediT، وحالُ دعوته، وحالُ تأليفه وموافقته.
    """
    source = SCREEN.read_text(encoding="utf-8")
    for field in ("is_account_linked", "permission_labels", "credit_labels",
                  "consent_label", "consent_method", "access_label",
                  "is_author", "consent_needs_recollection", "state_label"):
        assert field in source, field


def test_the_screen_can_only_ever_ask_to_consent_as_itself():
    """**لا زرَّ يوافق عن أحد** — والفحصُ على ما تستدعيه الشاشة، لا على كلامها.

    وفحصٌ يبحث عن عبارة «وافق الجميع» في الملفّ يسقط على تعليقٍ يشرح لماذا
    لا وجود لها، ويمرّ على زرٍّ حقيقيٍّ سُمّي بالإنجليزية. فالخاصيّةُ
    المفحوصة هنا أدقّ وأقوى: **كلُّ نداءٍ للموافقة في هذه الشاشة عنوانُه
    `/members/me/consent` حرفيًّا** — ولا نداءَ يركّب معرِّف عضوٍ في مسار
    موافقة، ولا معالِجَ يأخذ معرِّفًا ليوافق به.
    """
    source = SCREEN.read_text(encoding="utf-8")
    calls = re.findall(r"/api/v1/projects/\$\{projectId\}/members/([^`\"]*consent[^`\"]*)",
                       source)
    assert calls, "الشاشة لا تستدعي مسار موافقةٍ أصلًا"
    assert set(calls) == {"me/consent"}, calls

    # ولا معالِجَ موافقةٍ يقبل معرِّفًا — التوقيعُ نفسه يمنع الاستعمال.
    assert "consentAsMyself(granted: boolean)" in source
    for forbidden in ("recordConsent(memberId", "consentAll(", "approveAll(",
                      "consentFor("):
        assert forbidden not in source, forbidden
