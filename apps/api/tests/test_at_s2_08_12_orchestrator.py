"""AT-S2-08…12 — المنسّق: الحجب، العقد، الأثر، والسياق الموثق فقط.

يحتاج قاعدة بيانات حية — الأثر والتنبيهات وسجل التدقيق كلها صفوف حقيقية.
"""
import datetime as dt

import pytest
from sqlalchemy import select

from athera_api.brain.contracts import BrainAnswer, ContractViolation, parse_contract
from athera_api.brain.orchestrator import AgentPolicyError, Orchestrator, OutputBlocked, ToolCall
from athera_api.db import tenant_session
from athera_api.models.audit import AuditEvent, IntegrityAlert
from athera_api.models.brain import GuardrailCheck
from athera_api.models.research import FactCandidate, ResearcherMemory
from athera_api.models.runs import AgentRun, ModelRun, ToolRun
from athera_api.providers.base import ModelResponse, ModelUsage
from athera_api.providers.gateway import ModelGateway
from athera_api.providers.null_provider import NullProvider

pytestmark = pytest.mark.asyncio


class ScriptedProvider(NullProvider):
    """مزود يعيد مخرَجًا محددًا — لاختبار الحواجز لا لاختبار النموذج."""

    name = "null"  # يبقى null حتى لا يفعّل سقف التصنيف الخارجي

    def __init__(self, payload: dict | None) -> None:
        self._payload = payload

    async def generate_structured(self, request):
        return ModelResponse(
            content="", structured=self._payload,
            usage=ModelUsage(input_tokens=10, output_tokens=5, cost_usd=0.0001, latency_ms=12),
            provider=self.name, model="scripted",
        )


def _gateway(payload: dict | None) -> ModelGateway:
    return ModelGateway(provider=ScriptedProvider(payload))


async def _seed_verified_memory(tenant_id, user_id, statement="التخصص هو الإعلان والاتصال التسويقي"):
    async with tenant_session(tenant_id, user_id) as session:
        session.add(ResearcherMemory(
            tenant_id=tenant_id, memory_category="researcher_fact",
            statement_ar=statement, statement_en="Field is advertising and marketing communication",
            source_type="user_statement", verification_status="verified",
            verified_by=user_id, verified_at=dt.datetime.now(dt.UTC),
        ))


async def test_tool_outside_capability_is_denied_and_recorded(two_tenants):
    """AT-S2-02 على مستوى التنفيذ: المحاولة تُسجَّل قبل أن تُرفض."""
    a = two_tenants["a"]
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(AgentPolicyError):
            await Orchestrator(_gateway({})).run_agent(
                session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
                agent_key="journal_matcher",           # لا يملك profile.read
                question="ما المجلات المناسبة؟",
                tool_calls=[ToolCall(key="profile.read", kwargs={"user_id": a["user_id"]})],
            )

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        denied = (
            await session.execute(select(ToolRun).where(ToolRun.status == "denied"))
        ).scalars().all()
        assert denied and denied[0].tool_key == "profile.read"
        event = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "brain.tool_denied")
            )
        ).scalars().first()
        assert event is not None


async def test_blocked_output_never_reaches_the_caller(two_tenants):
    """AT-S2-08 — الحجب حدث مرئي: استثناء + تنبيه نزاهة + سجل تدقيق."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"])

    payload = {
        "answer_ar": "المجلة المقترحة تضمن القبول خلال شهرين.",
        "answer_en": "The suggested journal guarantees acceptance within two months.",
        "citations": [], "unsupported_claims": [], "evidence_gaps": [],
    }
    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(OutputBlocked) as exc:
            await Orchestrator(_gateway(payload)).run_agent(
                session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
                agent_key="journal_matcher", question="اقترح مجلة مناسبة",
            )
        assert "no_acceptance_guarantee" in {v.guard_key for v in exc.value.violations}

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        run = (
            await session.execute(
                select(AgentRun).where(AgentRun.agent_key == "journal_matcher",
                                       AgentRun.status == "blocked")
            )
        ).scalars().first()
        assert run is not None and "no_acceptance_guarantee" in run.blocked_reason

        alert = (
            await session.execute(
                select(IntegrityAlert).where(IntegrityAlert.alert_type == "guardrail_block")
            )
        ).scalars().first()
        assert alert is not None and alert.detail_ar and alert.detail_en

        event = (
            await session.execute(
                select(AuditEvent).where(AuditEvent.action == "brain.output_blocked")
            )
        ).scalars().first()
        assert event is not None


async def test_every_guard_is_recorded_pass_or_block(two_tenants):
    """معرفة أن حاجزًا عمل ونجح جزء من الأثر، لا المخالفات فقط."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"])
    payload = {"answer_ar": "لا توجد مجلة مؤكدة بعد؛ القرار يعتمد على التحكيم.",
               "answer_en": "No journal is confirmed yet.", "citations": [],
               "unsupported_claims": [], "evidence_gaps": []}

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        result = await Orchestrator(_gateway(payload)).run_agent(
            session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
            agent_key="journal_matcher", question="ما وضع المجلة؟",
        )
        run_id = result.agent_run_id

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        checks = (
            await session.execute(select(GuardrailCheck).where(GuardrailCheck.agent_run_id == run_id))
        ).scalars().all()
        from athera_api.brain.agents import AGENTS

        assert {c.guard_key for c in checks} == set(AGENTS["journal_matcher"].guards)
        assert all(c.result == "passed" for c in checks)


async def test_malformed_structured_output_fails_without_repair(two_tenants):
    """AT-S2-09 — ترميم مخرَج مشوّه هو اللحظة التي يتسرب فيها الاختلاق."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        with pytest.raises(ContractViolation):
            await Orchestrator(_gateway({"answer_en": "missing the Arabic answer"})).run_agent(
                session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
                agent_key="research_manager", question="ما التالي؟",
            )

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        run = (
            await session.execute(select(AgentRun).where(AgentRun.status == "failed"))
        ).scalars().first()
        assert run is not None and "contract" in (run.error or "").lower()


def test_contract_rejects_empty_and_missing_payloads():
    with pytest.raises(ContractViolation):
        parse_contract(BrainAnswer, None)
    with pytest.raises(ContractViolation):
        parse_contract(BrainAnswer, {"answer_ar": ""})
    ok = parse_contract(BrainAnswer, {"answer_ar": "إجابة"})
    assert ok.answer_ar == "إجابة" and ok.citations == []


async def test_context_contains_verified_memory_only(two_tenants):
    """AT-S2-11 — المرشّح غير المتحقق لا يدخل سياق النموذج إطلاقًا (TC-01)."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"], "الرتبة الحالية أستاذ مشارك")

    from athera_api.brain.tools import get_tool

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        pending = (
            await session.execute(select(FactCandidate).where(FactCandidate.status == "unverified"))
        ).scalars().all()
        rows = await get_tool("memory.search_verified").handler(
            session, tenant_id=a["tenant_id"], query=None, category=None
        )

    statements = " ".join(row["statement_ar"] for row in rows)
    assert "أستاذ مشارك" in statements
    for candidate in pending:
        assert candidate.statement_ar not in statements


async def test_trace_links_agent_tool_and_model_runs(two_tenants):
    """AT-S2-10 — الشجرة كاملة: أجنت ← أدوات ← نماذج، بالتكلفة والزمن."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"])
    payload = {"answer_ar": "الخطوة التالية هي اعتماد ملف الباحث.",
               "answer_en": "Next step is approving the profile.", "citations": [],
               "unsupported_claims": [], "evidence_gaps": []}

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        result = await Orchestrator(_gateway(payload)).run_agent(
            session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
            agent_key="research_manager", question="ما الخطوة التالية؟",
        )
        trace_id, run_id = result.trace_id, result.agent_run_id

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        run = (await session.execute(select(AgentRun).where(AgentRun.id == run_id))).scalar_one()
        assert run.trace_id == trace_id and run.status == "completed"
        assert run.requested_by == a["user_id"]

        tools = (
            await session.execute(select(ToolRun).where(ToolRun.agent_run_id == run_id))
        ).scalars().all()
        models = (
            await session.execute(select(ModelRun).where(ModelRun.agent_run_id == run_id))
        ).scalars().all()
        assert tools and models
        assert models[0].latency_ms is not None
        assert models[0].max_classification_sent in {"C0", "C1", "C2"}


async def test_pipeline_runs_with_the_real_null_provider(two_tenants):
    """AT-S2-12 — المنظومة كاملة بلا مزود: إجابة صريحة لا نص مختلق."""
    a = two_tenants["a"]
    await _seed_verified_memory(a["tenant_id"], a["user_id"])

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        result = await Orchestrator(ModelGateway(provider=NullProvider())).run_agent(
            session, tenant_id=a["tenant_id"], actor_user_id=a["user_id"],
            agent_key="research_manager", question="ما الخطوة التالية؟",
        )
    assert result.status == "completed"
    assert result.answer is not None
    assert "لا يوجد مزود" in result.answer.answer_ar
    assert result.answer.citations == []
