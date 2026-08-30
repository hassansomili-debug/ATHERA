"""عقود العقل البحثي والأثر | Brain and trace contracts."""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class AgentSpecResponse(BaseModel):
    """السجل قابل للتفتيش: القيد يُعرض كما ورد في §8، لا مخفيًا في تعليمات."""

    key: str
    name: str
    name_ar: str
    name_en: str
    responsibility: str
    constraint: str
    constraint_ar: str
    constraint_en: str
    allowed_tools: list[str]
    guards: list[str]
    reads_memory: list[str]
    gate: str | None


class ToolSpecResponse(BaseModel):
    key: str
    name: str
    side_effect: str
    returns_classification: str


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    agent_key: str = Field(default="research_manager")
    memory_category: str | None = None
    search: str | None = Field(default=None, max_length=200)


class CitationResponse(BaseModel):
    memory_id: str
    locator: str | None = None
    quote: str | None = None


class AskResponse(BaseModel):
    trace_id: uuid.UUID
    agent_run_id: uuid.UUID
    agent_key: str
    answer: str
    answer_ar: str
    answer_en: str | None
    citations: list[CitationResponse]
    unsupported_claims: list[str]
    evidence_gaps: list[str]
    context_items: int
    provider: str


class GuardrailCheckResponse(BaseModel):
    guard_key: str
    result: str
    detail: str | None
    excerpt: str | None


class ToolRunResponse(BaseModel):
    tool_key: str
    tool_kind: str | None
    status: str
    duration_ms: int | None


class ModelRunResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model: str
    operation: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int | None
    max_classification_sent: str


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    agent_key: str
    status: str
    gate: str | None
    blocked_reason: str | None
    started_at: dt.datetime
    finished_at: dt.datetime | None
    output_summary: dict | None
    tool_runs: list[ToolRunResponse]
    model_runs: list[ModelRunResponse]
    guardrail_checks: list[GuardrailCheckResponse]


class TraceResponse(BaseModel):
    trace_id: uuid.UUID
    agent_runs: list[AgentRunResponse]
    total_cost_usd: float
    total_latency_ms: int
    blocked: bool


class TraceSummary(BaseModel):
    trace_id: uuid.UUID | None
    agent_key: str
    status: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    blocked_reason: str | None
