"""العقل البحثي والأثر | Brain and trace API (§7، §38.5).

`/brain/agents` ليست نقطة تجميلية: عرض قيود §8 عبر الـAPI يجعل الحوكمة
قابلة للتفتيش من خارج الكود — الباحث والمؤسسة يريان ما لا يستطيع الأجنت
فعله، لا ما نَعِد بأنه لن يفعله.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..brain import agents as agent_registry
from ..brain import tools as tool_registry
from ..brain.orchestrator import Orchestrator, ToolCall
from ..deps import Principal, get_principal, get_session
from ..errors import NotFound
from ..models.brain import GuardrailCheck
from ..models.runs import AgentRun, ModelRun, ToolRun
from ..schemas.brain import (
    AgentRunResponse,
    AgentSpecResponse,
    AskRequest,
    AskResponse,
    CitationResponse,
    GuardrailCheckResponse,
    ModelRunResponse,
    ToolRunResponse,
    ToolSpecResponse,
    TraceResponse,
    TraceSummary,
)

router = APIRouter(prefix="/api/v1", tags=["brain"])


def _pick(locale: str, arabic: str, english: str) -> str:
    return english if locale == "en" else arabic


@router.get("/brain/agents", response_model=list[AgentSpecResponse])
async def list_agents(principal: Principal = Depends(get_principal)) -> list[AgentSpecResponse]:
    return [
        AgentSpecResponse(
            key=spec.key,
            name=_pick(principal.locale, spec.name_ar, spec.name_en),
            name_ar=spec.name_ar, name_en=spec.name_en,
            responsibility=_pick(principal.locale, spec.responsibility_ar, spec.responsibility_en),
            constraint=_pick(principal.locale, spec.constraint_ar, spec.constraint_en),
            constraint_ar=spec.constraint_ar, constraint_en=spec.constraint_en,
            allowed_tools=sorted(spec.allowed_tools),
            guards=sorted(spec.guards),
            reads_memory=sorted(spec.reads_memory),
            gate=spec.gate,
        )
        for spec in agent_registry.AGENTS.values()
    ]


@router.get("/brain/tools", response_model=list[ToolSpecResponse])
async def list_tools(principal: Principal = Depends(get_principal)) -> list[ToolSpecResponse]:
    return [
        ToolSpecResponse(
            key=spec.key,
            name=_pick(principal.locale, spec.name_ar, spec.name_en),
            side_effect=spec.side_effect,
            returns_classification=spec.returns_classification,
        )
        for spec in tool_registry.all_tools().values()
    ]


@router.post("/brain/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> AskResponse:
    orchestrator = Orchestrator()
    result = await orchestrator.run_agent(
        session,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        agent_key=payload.agent_key,
        question=payload.question,
        tool_calls=[
            ToolCall(
                key="memory.search_verified",
                kwargs={"query": payload.search, "category": payload.memory_category},
            )
        ],
    )
    answer = result.answer
    assert answer is not None  # المنسّق يرفع استثناءً بدل إعادة None
    return AskResponse(
        trace_id=result.trace_id,
        agent_run_id=result.agent_run_id,
        agent_key=payload.agent_key,
        answer=(answer.answer_en or answer.answer_ar) if principal.locale == "en" else answer.answer_ar,
        answer_ar=answer.answer_ar,
        answer_en=answer.answer_en,
        citations=[CitationResponse(**c.model_dump()) for c in answer.citations],
        unsupported_claims=answer.unsupported_claims,
        evidence_gaps=answer.evidence_gaps,
        context_items=result.context_items,
        provider=orchestrator._gateway.provider_name,  # noqa: SLF001 — يُعرض عمدًا في الأثر
    )


@router.get("/traces", response_model=list[TraceSummary])
async def list_traces(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, le=200),
) -> list[TraceSummary]:
    rows = (
        await session.execute(
            select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        TraceSummary(
            trace_id=row.trace_id, agent_key=row.agent_key, status=row.status,
            started_at=row.started_at, finished_at=row.finished_at,
            blocked_reason=row.blocked_reason,
        )
        for row in rows
    ]


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(
    trace_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> TraceResponse:
    runs = (
        await session.execute(
            select(AgentRun).where(AgentRun.trace_id == trace_id).order_by(AgentRun.started_at)
        )
    ).scalars().all()
    if not runs:
        raise NotFound("brain.trace_not_found")

    run_ids = [run.id for run in runs]
    tool_rows = (
        await session.execute(select(ToolRun).where(ToolRun.agent_run_id.in_(run_ids)))
    ).scalars().all()
    model_rows = (
        await session.execute(select(ModelRun).where(ModelRun.agent_run_id.in_(run_ids)))
    ).scalars().all()
    guard_rows = (
        await session.execute(select(GuardrailCheck).where(GuardrailCheck.agent_run_id.in_(run_ids)))
    ).scalars().all()

    total_cost = sum(float(m.cost_usd or 0) for m in model_rows)
    total_latency = sum(int(m.latency_ms or 0) for m in model_rows) + sum(
        int(t.duration_ms or 0) for t in tool_rows
    )

    return TraceResponse(
        trace_id=trace_id,
        agent_runs=[
            AgentRunResponse(
                id=run.id, agent_key=run.agent_key, status=run.status, gate=run.gate,
                blocked_reason=run.blocked_reason, started_at=run.started_at,
                finished_at=run.finished_at, output_summary=run.output_summary,
                tool_runs=[
                    ToolRunResponse(tool_key=t.tool_key, tool_kind=t.tool_kind,
                                    status=t.status, duration_ms=t.duration_ms)
                    for t in tool_rows if t.agent_run_id == run.id
                ],
                model_runs=[
                    ModelRunResponse(
                        id=m.id, provider=m.provider, model=m.model, operation=m.operation,
                        input_tokens=m.input_tokens, output_tokens=m.output_tokens,
                        cost_usd=float(m.cost_usd) if m.cost_usd is not None else None,
                        latency_ms=m.latency_ms,
                        max_classification_sent=m.max_classification_sent,
                    )
                    for m in model_rows if m.agent_run_id == run.id
                ],
                guardrail_checks=[
                    GuardrailCheckResponse(
                        guard_key=g.guard_key, result=g.result,
                        detail=(g.detail_en if principal.locale == "en" else g.detail_ar),
                        excerpt=g.excerpt,
                    )
                    for g in guard_rows if g.agent_run_id == run.id
                ],
            )
            for run in runs
        ],
        total_cost_usd=round(total_cost, 6),
        total_latency_ms=total_latency,
        blocked=any(run.status == "blocked" for run in runs),
    )
