"""AT-S10-* عبر HTTP — الرفض يقع في الخادم لا في الشاشة.

قاعدة صحيحة في `services/` لا ينفعها شيء إن لم يستدعها الموجّه.
"""
import datetime as dt
import uuid

import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(two_tenants):
    """**البحثُ يُنشأ من الطريق الذي يسلكه الباحث** — لا بزرعٍ في القاعدة.

    وكان يُزرع صفًّا مباشرةً، فينشأ بحثٌ لا مالك له: لا ملفَّ باحثٍ يشير
    إليه، ولا حدثَ إنشاءٍ في السجلّ. وذلك بالضبط ما لا يقع في المنتج، وهو
    ما كان يخفي أن الفريق كان بلا مالكٍ أصلًا — فيقرأ أيُّ مصادَقٍ فريقَ
    أيِّ بحثٍ في المستأجر.
    """
    import httpx

    from athera_api.main import app
    from athera_api.security import issue_access_token

    tenant = two_tenants["a"]
    token = issue_access_token(
        user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
        roles=["researcher"], mfa_satisfied=True,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as http:
        created = await http.post("/api/v1/workspace/projects",
                                  json={"title_ar": "مشروع اختبار"})
        assert created.status_code == 201, created.text
        yield http, created.json()["id"], tenant

    from athera_api.db import engine

    await engine.dispose()


async def _seed_approval(tenant, *, requested_by):
    """يزرع طلب اعتماد معلّقًا مباشرةً — سير Temporal ليس شرطًا لاختبار البوابة."""
    from athera_api.db import tenant_session
    from athera_api.models.audit import Approval

    async with tenant_session(tenant["tenant_id"], tenant["user_id"]) as session:
        row = Approval(
            tenant_id=tenant["tenant_id"], gate="G2", object_type="research_project",
            object_id=uuid.uuid4(), status="pending", requested_by=requested_by,
        )
        session.add(row)
        await session.flush()
        return str(row.id)


async def test_requester_cannot_decide_their_own_approval(client):
    """AT-S10-01 — الفصل بين الطلب والقرار هو ما يجعل البوابة بوابةً."""
    http, _project, tenant = client
    approval_id = await _seed_approval(tenant, requested_by=tenant["user_id"])

    response = await http.post(f"/api/v1/approvals/{approval_id}/decide",
                               json={"approved": True, "reason": "يبدو جيدًا"})
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "inbox.self_approval_forbidden"
    assert set(response.json()["error"]["messages"]) == {"ar", "en"}


async def test_decision_without_a_reason_is_refused(client):
    """AT-S10-02 — الرفض يحتاج سببًا كما الاعتماد.

    قرار بلا سبب يجعل السجل يقول «رُفض» ولا يقول لماذا، فيتكرر الطلب نفسه.
    """
    http, _project, tenant = client
    other_user = tenant["user_id"]
    approval_id = await _seed_approval(tenant, requested_by=other_user)

    for body in ({"approved": True, "reason": ""}, {"approved": False, "reason": "لا"}):
        response = await http.post(f"/api/v1/approvals/{approval_id}/decide", json=body)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation.failed"


async def test_non_human_author_is_refused_over_http(client):
    """AT-S10-06 عبر الـAPI — لا يُسند تأليف لنموذج."""
    http, project_id, _tenant = client
    response = await http.post(f"/api/v1/projects/{project_id}/members", json={
        "display_name": "ChatGPT", "role": "co_author",
        "credit_roles": ["writing_original_draft"],
    })
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "team.invalid_member"


async def test_a_project_leader_cannot_consent_on_behalf_of_a_coauthor(client):
    """§24 — **وكان هذا المسار يسمح بذلك، وهو تزوير تأليف.**

    الصيغةُ القديمة لهذا الفحص كانت تثبت العطب وتسمّيه صوابًا: رئيسُ الفريق
    يطلب `/members/{id}/consent` لعضوٍ ليس هو، فيُسجَّل. فتصير الورقةُ تحمل
    اسمَ من لم يوافق، ويقول السجلّ إنه وافق.

    فما يُثبَت هنا الآن أقوى من «تُسجَّل مرّةً واحدة»:

      ١) لا مسار في المنصّة يقبل معرِّف عضوٍ آخر للموافقة الشخصية أصلًا.
      ٢) والمسارُ الإداري موجودٌ ومعلَن، **ويلزمه سندٌ مكتوب**، ويُوسم
         `administrative` فلا يُقرأ أبدًا كموافقةٍ منحها صاحبها.
      ٣) وما لا حساب له لا يملك موافقةً ذاتية — لا سبيل إلى إثبات أنه هو.
    """
    http, project_id, _tenant = client
    created = await http.post(f"/api/v1/projects/{project_id}/members", json={
        "display_name": "نورة العتيبي", "role": "co_author",
        "credit_roles": ["methodology"],
    })
    assert created.status_code == 201, created.text
    member = created.json()
    member_id = member["id"]
    assert member["consent_recorded_at"] is None
    assert member["credit_labels"] == ["المنهجية"]
    # **العضويةُ ليست تأليفًا**: تُضاف ولا تحمل تأليفًا ولا موافقة.
    assert member["is_author"] is False
    assert member["consent_state"] == "not_requested"
    # ولا ربطَ بحساب من جسم الطلب — الربط بدعوةٍ يقبلها صاحبها.
    assert member["is_account_linked"] is False

    # ١) المسارُ الذي كان يقبل معرِّف غيرك لم يعد له وجود.
    gone = await http.post(
        f"/api/v1/projects/{project_id}/members/{member_id}/consent")
    assert gone.status_code == 404, gone.text

    # ٢) والمسارُ الإداري يرفض بلا سند.
    declared = await http.put(
        f"/api/v1/projects/{project_id}/members/{member_id}/authorship",
        json={"is_author": True, "author_position": 2})
    assert declared.status_code == 200, declared.text
    # والإعلانُ وحده لا يُنتج موافقة — وهو الفرق الذي أُصلح.
    assert declared.json()["is_author"] is True
    assert declared.json()["consent_state"] == "not_requested"
    bare = await http.post(
        f"/api/v1/projects/{project_id}/members/{member_id}/administrative-consent",
        json={"evidence_ar": "لا"})
    assert bare.status_code == 422, bare.text

    # ويقبل بسندٍ مكتوب — **موسومًا بأنه ليس موافقةَ صاحبها**.
    documented = await http.post(
        f"/api/v1/projects/{project_id}/members/{member_id}/administrative-consent",
        json={"evidence_ar": "إقرار تأليف موقَّع بخطّ اليد، محفوظ لدى عمادة البحث"})
    assert documented.status_code == 200, documented.text
    body = documented.json()
    assert body["consent_method"] == "administrative"
    assert body["consent_recorded_at"] is not None
    assert body["consent_state"] == "granted"

    # ولا تُسجَّل مرتين — الحكمُ المسجَّل لا يُكتب فوقه.
    again = await http.post(
        f"/api/v1/projects/{project_id}/members/{member_id}/administrative-consent",
        json={"evidence_ar": "إقرار تأليف موقَّع بخطّ اليد، محفوظ لدى عمادة البحث"})
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "team.consent_already_recorded"


async def test_superseded_decision_stays_visible(client):
    """§12.4 — إخفاء المنسوخ يجعل السجل يبدو كأن الرأي الحالي هو الوحيد."""
    http, project_id, _tenant = client
    first = await http.post(f"/api/v1/projects/{project_id}/decisions", json={
        "decision_kind": "question", "statement_ar": "ما أثر التحول الرقمي؟",
    })
    assert first.status_code == 201, first.text

    second = await http.post(f"/api/v1/projects/{project_id}/decisions", json={
        "decision_kind": "question",
        "statement_ar": "ما أثر التحول الرقمي في المنشآت الصغيرة؟",
        "supersedes_id": first.json()["id"],
    })
    assert second.status_code == 201, second.text

    listing = await http.get(f"/api/v1/projects/{project_id}/decisions")
    rows = listing.json()
    assert len(rows) == 2
    assert [row["is_superseded"] for row in rows] == [True, False]


async def test_dictionary_of_a_frozen_version_cannot_be_edited(client):
    """AT-S10-08 — §17.4: وصف عمود يتغيّر بعد التجميد يغيّر معنى تحليل جرى عليه."""
    http, project_id, _tenant = client
    dataset = await http.post("/api/v1/analysis/datasets", json={
        "project_id": project_id, "name_ar": "بيانات", "classification": "C3",
        "raw_label": "الرفع الأول", "raw_checksum": "b" * 64, "row_count": 50,
    })
    assert dataset.status_code == 201, dataset.text
    raw_version = dataset.json()["id"]

    cleaned = await http.post(f"/api/v1/analysis/datasets/{dataset.json()['dataset_id']}/versions",
                              json={
                                  "parent_version_id": raw_version, "state": "cleaned",
                                  "label": "منقّاة", "checksum": "c" * 64,
                                  "change_note_ar": "حذف صفوف ناقصة", "row_count": 48,
                              })
    assert cleaned.status_code == 201, cleaned.text
    version_id = cleaned.json()["id"]

    wrote = await http.put(f"/api/v1/analysis/datasets/versions/{version_id}/dictionary",
                           json=[{"column_name": "age", "label_ar": "العمر",
                                  "scale_type": "ratio", "is_pii": False}])
    assert wrote.status_code == 200, wrote.text
    assert wrote.json()["described_columns"] == 1

    frozen = await http.post(
        f"/api/v1/analysis/datasets/versions/{version_id}/freeze")
    assert frozen.status_code == 200, frozen.text

    blocked = await http.put(f"/api/v1/analysis/datasets/versions/{version_id}/dictionary",
                             json=[{"column_name": "age", "label_ar": "السنّ",
                                    "scale_type": "ratio", "is_pii": True}])
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "analysis.dictionary_frozen"


async def test_export_carries_its_limitations(client):
    """AT-S10-09 — §18.5: تصدير بلا إعلان حدوده يُوهم بنقل كامل."""
    http, project_id, _tenant = client
    dataset = await http.post("/api/v1/analysis/datasets", json={
        "project_id": project_id, "name_ar": "بيانات التصدير", "classification": "C3",
        "raw_label": "الرفع الأول", "raw_checksum": "d" * 64,
    })
    assert dataset.status_code == 201, dataset.text
    version_id = dataset.json()["id"]

    caps = await http.get("/api/v1/analysis/tools")
    assert caps.status_code == 200
    smartpls = next(c for c in caps.json() if c["tool"] == "smartpls")

    export = await http.post("/api/v1/analysis/exports", json={
        "dataset_version_id": version_id, "tool": "smartpls",
        "export_format": smartpls["export_formats"][0],
    })
    assert export.status_code == 201, export.text
    assert export.json()["limitations"].strip()

    bad = await http.post("/api/v1/analysis/exports", json={
        "dataset_version_id": version_id, "tool": "smartpls", "export_format": "sav",
    })
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "analysis.unsupported_format"


async def test_brief_survives_being_empty(client):
    """§51.9 — نشرة فارغة تُحفظ وتقول إن الرصد عمل ولم يجد."""
    http, _project, _tenant = client
    now = dt.datetime.now(dt.UTC)
    created = await http.post("/api/v1/briefs", json={
        "cadence": "weekly",
        "period_start": (now - dt.timedelta(days=7)).isoformat(),
        "period_end": now.isoformat(),
    })
    assert created.status_code == 201, created.text
    assert created.json()["is_empty"] is True
    assert "لم يجد" in created.json()["summary"]

    listing = await http.get("/api/v1/briefs")
    assert any(row["id"] == created.json()["id"] for row in listing.json())


async def test_brief_item_without_evidence_is_refused_over_http(client):
    """AT-S10-10 عبر الـAPI."""
    http, _project, _tenant = client
    now = dt.datetime.now(dt.UTC)
    response = await http.post("/api/v1/briefs", json={
        "cadence": "weekly",
        "period_start": (now - dt.timedelta(days=7)).isoformat(),
        "period_end": now.isoformat(),
        "new_trends": [{"item_key": "t1", "title_ar": "اتجاه", "evidence_ref": ""}],
    })
    assert response.status_code == 422, response.text


async def test_runtime_posture_names_the_provider_and_hides_the_key(client):
    """§36.2 — تُعرض حالة المفتاح لا قيمته، ووضع التشغيل يُفصح عنه صراحةً."""
    http, _project, _tenant = client
    response = await http.get("/api/v1/settings/posture")
    assert response.status_code == 200, response.text
    body = response.json()

    keys = {item["key"] for item in body["items"]}
    assert {"model_provider", "literature_registry", "scheduled_monitoring"} <= keys
    assert body["supported_locales"] == ["ar", "en"]

    payload = response.text.lower()
    for secret_marker in ("sk-", "api_key", "secret"):
        assert secret_marker not in payload, f"تسريب محتمل: {secret_marker}"


async def test_inbox_summary_keeps_approvals_and_alerts_apart(client):
    """العدّادات لا تُجمع: انتظار قرار ≠ إخفاق مرصود."""
    http, _project, _tenant = client
    response = await http.get("/api/v1/inbox/summary")
    assert response.status_code == 200, response.text
    body = response.json()
    assert {"pending_approvals", "open_alerts", "blocking_alerts",
            "unread_notifications"} == set(body)
