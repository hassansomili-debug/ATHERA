"""اختبارات على مستوى الـAPI للموجّهات الجديدة (Sprint 7، Sprint 8، §51).

الاختبارات القائمة تغطّي منطق النطاق وحده. وهذا لا يكفي: القاعدة قد تكون
صحيحة في `services/` ومع ذلك لا يستدعيها الموجّه، فيمرّ ما كان يجب أن يُمنع.
فما يُختبر هنا هو الرفض عبر HTTP فعلًا — من رمز موقّع، عبر سلسلة التبعيات
كاملة، إلى قاعدة بيانات حقيقية بسياسات RLS مفعّلة.
"""
import uuid

import pytest
import pytest_asyncio

# التخطي عند غياب القاعدة يأتي من `db_ready` التي تعتمد عليها `two_tenants` —
# لا يُعاد تعريف شرط التخطي هنا حتى لا يتفرّع إلى موضعين يختلفان مع الوقت.
pytestmark = pytest.mark.asyncio


async def _a_signal_id(tenant, trend_id: str) -> str:
    """معرّف إشارة حقيقية للاتجاه — البطاقة تستشهد بإشارات لا باتجاهات.

    الاستجابة تعيد قوة الاتجاه لا الإشارة، فيُقرأ المعرّف من القاعدة بدل
    تمرير معرّف الاتجاه في موضع الإشارة — وهو خطأ يمرّ صامتًا حتى يصطدم
    بقيد المفتاح الأجنبي.
    """
    import uuid as _uuid

    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.trends import TrendSignalRow

    async with tenant_session(tenant["tenant_id"], tenant["user_id"]) as session:
        row = (
            await session.execute(
                select(TrendSignalRow).where(TrendSignalRow.trend_id == _uuid.UUID(trend_id))
            )
        ).scalars().first()
    assert row is not None
    return str(row.id)


@pytest_asyncio.fixture
async def client(two_tenants):
    """عميل HTTP يحمل رمزًا موقّعًا لمستأجر حقيقي، ومشروعًا حقيقيًا يعلّق عليه."""
    import httpx

    from athera_api.db import tenant_session
    from athera_api.main import app
    from athera_api.models.portfolio import ResearchProject
    from athera_api.security import issue_access_token

    tenant = two_tenants["a"]
    async with tenant_session(tenant["tenant_id"], tenant["user_id"]) as session:
        project = ResearchProject(
            tenant_id=tenant["tenant_id"], working_title_ar="مشروع اختبار",
            status="planned",
        )
        session.add(project)
        await session.flush()
        project_id = project.id

    token = issue_access_token(
        user_id=tenant["user_id"], tenant_id=tenant["tenant_id"],
        roles=["researcher"], mfa_satisfied=True,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test",
        headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"},
    ) as http:
        yield http, str(project_id), tenant

    from athera_api.db import engine

    await engine.dispose()


async def test_analysis_run_refused_on_unfrozen_version(client):
    """§17.3 — التشغيل على نسخة غير مجمّدة يُرفض عبر الـAPI، لا في الخدمة وحدها."""
    http, project_id, _tenant = client
    created = await http.post("/api/v1/analysis/datasets", json={
        "project_id": project_id, "name_ar": "بيانات الاستبانة",
        "classification": "C3", "raw_label": "الرفع الأول",
        "raw_checksum": "a" * 64, "row_count": 120,
    })
    assert created.status_code == 201, created.text
    version_id = created.json()["id"]
    assert created.json()["frozen_at"] is None

    plan = await http.post("/api/v1/analysis/plans", json={
        "project_id": project_id, "version_label": "v1",
        "tests": [{"test_key": "h1", "test_kind": "regression", "variables": ["x", "y"]}],
    })
    assert plan.status_code == 201, plan.text

    run = await http.post("/api/v1/analysis/runs", json={
        "plan_id": plan.json()["id"], "dataset_version_id": version_id, "tool": "spss",
    })
    assert run.status_code == 422, run.text
    # الخطة غير مقفلة **و**النسخة غير مجمّدة — أيّهما رُفض أولًا فالتشغيل ممنوع.
    assert run.json()["error"]["code"] in {
        "analysis.dataset_not_frozen", "analysis.plan_not_locked",
    }
    assert set(run.json()["error"]["messages"]) == {"ar", "en"}


async def test_g9_blocked_for_result_without_analysis_run(client):
    """§20 — نتيجة رقمية بلا تشغيلة تحليل تُبقي G9 مغلقة، والزر لا يفتحها."""
    http, project_id, _tenant = client
    created = await http.post("/api/v1/manuscripts", json={
        "project_id": project_id, "title_ar": "أثر جودة الخدمة", "language": "ar",
    })
    assert created.status_code == 201, created.text
    manuscript_id = created.json()["id"]

    section = await http.post(f"/api/v1/manuscripts/{manuscript_id}/sections", json={
        "section_key": "results", "text_ar": "بلغ معامل الانحدار 0.42 (p<0.01).",
    })
    assert section.status_code in (200, 201), section.text

    readiness = await http.get(f"/api/v1/manuscripts/{manuscript_id}/readiness")
    assert readiness.status_code == 200, readiness.text
    body = readiness.json()
    assert body["can_pass_g9"] is False
    assert body["issues"], "رقم في قسم النتائج بلا تشغيلة تحليل يجب أن يُنتج عائقًا"

    approve = await http.post(f"/api/v1/manuscripts/{manuscript_id}/approve-g9")
    assert approve.status_code == 422, approve.text
    assert approve.json()["error"]["code"] == "publishing.g9_blocked"


async def test_signal_weight_cannot_exceed_one(client):
    """§51.1 — سقف الوزن جزء من العقد: إشارة واحدة لا تصنع اتجاهًا مهما «ثقلت».

    لو قُبل وزن 99 لصار بلوغ عتبة وزن الأدلة ممكنًا بإشارة واحدة، فتنهار
    الشروط الأربعة إلى شرط واحد يتحكّم فيه من يكتب الإشارة.
    """
    http, _project_id, tenant = client
    response = await http.post("/api/v1/trends/signals", json={
        "trend_key": f"trend-{uuid.uuid4().hex[:8]}", "trend_label_ar": "اتجاه",
        "source_type": "openalex", "source_id": "J-001",
        "observed_at": "2026-01-15T00:00:00Z", "pattern": "topic_acceleration",
        "weight": 99.0,
    })
    assert response.status_code == 422, response.text


async def test_a_single_signal_is_noise_not_a_trend(client):
    """§51.1 — إشارة واحدة محتسبة تبقى ضجيجًا، وينقص من الشروط ما لم يتحقق بالاسم.

    «مرشّح» محجوزة لحالة أخرى: إشارات موجودة لكن لا شيء منها يُحتسب دليلًا.
    خلط الحالتين يجعل ضجيجًا صريحًا يبدو اتجاهًا ينتظر التأكيد.
    """
    http, _project_id, tenant = client
    response = await http.post("/api/v1/trends/signals", json={
        "trend_key": f"trend-{uuid.uuid4().hex[:8]}",
        "trend_label_ar": "تصاعد استخدام SmartPLS",
        "source_type": "openalex", "source_id": "J-001",
        "observed_at": "2026-01-15T00:00:00Z", "pattern": "topic_acceleration",
        "weight": 1.0,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_validated"] is False
    assert body["status"] == "noise"
    assert {"min_signals", "min_distinct_sources", "min_span_days"} <= set(
        body["unmet_conditions"]
    )


async def test_model_output_is_recorded_but_never_counted(client):
    """§51.11 — مخرَج النموذج يُسجَّل ولا يُحتسب دليلًا."""
    http, _project_id, tenant = client
    response = await http.post("/api/v1/trends/signals", json={
        "trend_key": f"trend-{uuid.uuid4().hex[:8]}",
        "trend_label_ar": "اتجاه مقترح من نموذج",
        "source_type": "model_output", "source_id": "M-001",
        "observed_at": "2026-01-15T00:00:00Z", "pattern": "topic_acceleration",
        "weight": 1.0,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["evidence_weight"] == 0.0
    assert body["signal_count"] == 0
    assert body["ignored_signals"], "الإشارة تُسجَّل وتُعلَن مُهمَلة، ولا تختفي بصمت"


async def test_submission_refused_while_a_readiness_condition_is_unmet(client):
    """§51.5 P14 — لا تقديم خارجي قبل اكتمال شروط الجاهزية، ولو طلبه إنسان."""
    http, _project_id, tenant = client
    signal = await http.post("/api/v1/trends/signals", json={
        "trend_key": f"trend-{uuid.uuid4().hex[:8]}", "trend_label_ar": "اتجاه",
        "source_type": "openalex", "source_id": "J-002",
        "observed_at": "2026-01-15T00:00:00Z", "pattern": "topic_acceleration",
        "weight": 1.0,
    })
    assert signal.status_code == 201, signal.text
    trend_id = signal.json()["trend_id"]

    card = await http.post("/api/v1/opportunity-cards", json={
        "trend_id": trend_id,
        "working_title_ar": "أثر التحول الرقمي في الأداء",
        "central_question_ar": "كيف يؤثر التحول الرقمي في أداء المنشآت الصغيرة؟",
        "trend_summary_ar": "تصاعد الاهتمام بالموضوع خلال عام.",
        "evidence_signal_ids": [], "gap_ar": "لا دراسات في السياق المحلي.",
        "gap_confidence": 0.6,
    })
    # §51.4 — بطاقة بلا إشارات داعمة مرفوضة عند العقد قبل أن تصل إلى المنطق.
    assert card.status_code == 422, card.text
    assert card.json()["error"]["code"] == "validation.failed"
    assert set(card.json()["error"]["messages"]) == {"ar", "en"}

    card = await http.post("/api/v1/opportunity-cards", json={
        "trend_id": trend_id,
        "working_title_ar": "أثر التحول الرقمي في الأداء",
        "central_question_ar": "كيف يؤثر التحول الرقمي في أداء المنشآت الصغيرة؟",
        "trend_summary_ar": "تصاعد الاهتمام بالموضوع خلال عام.",
        "evidence_signal_ids": [await _a_signal_id(tenant, trend_id)],
        "gap_ar": "لا دراسات في السياق المحلي.", "gap_confidence": 0.6,
    })
    assert card.status_code == 201, card.text
    card_id = card.json()["id"]

    decision = await http.post(
        f"/api/v1/opportunity-cards/{card_id}/authorize-submission",
        json={"human_act": True},
    )
    assert decision.status_code == 200, decision.text
    body = decision.json()
    assert body["allowed"] is False
    assert body["unmet_conditions"], "الرفض يذكر الشرط الناقص بالاسم، ولا يكتفي بالمنع"
