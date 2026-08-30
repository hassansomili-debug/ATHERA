"""الخيط الذهبي والمنهجية والبروتوكول | Golden thread API (§15، §16، §9).

البوابة لا تُفتح بالدرجة بل بغياب الكشوفات الحاجبة والعناصر المفقودة —
والفرق جوهري: درجة 88 بلا عيب حاجب أفضل من 95 بعيب واحد يوقف الورقة.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.golden_thread import (
    Instrument,
    InstrumentItem,
    Method,
    Protocol,
    ThreadElement,
    ThreadLink,
    Variable,
)
from ..schemas.golden_thread import (
    ConsistencyResponse,
    ElementCreateRequest,
    ElementResponse,
    FindingResponse,
    GateSubmitRequest,
    LinkCreateRequest,
    MethodologyResponse,
    ProtocolCreateRequest,
    ProtocolResponse,
    RequirementResponse,
)
from ..services import audit
from ..services.golden_thread import graph as thread_graph
from ..services.golden_thread import methodology, score

router = APIRouter(prefix="/api/v1", tags=["golden-thread"])


def _pick(locale: str, ar: str, en: str | None) -> str:
    return (en or ar) if locale == "en" else ar


async def _build_graph(session: AsyncSession, project_id: uuid.UUID) -> thread_graph.ThreadGraph:
    elements = (
        await session.execute(select(ThreadElement).where(ThreadElement.project_id == project_id))
    ).scalars().all()
    links = (
        await session.execute(select(ThreadLink).where(ThreadLink.project_id == project_id))
    ).scalars().all()
    variables = (
        await session.execute(select(Variable).where(Variable.project_id == project_id))
    ).scalars().all()
    instruments = (
        await session.execute(select(Instrument).where(Instrument.project_id == project_id))
    ).scalars().all()
    method = (
        await session.execute(select(Method).where(Method.project_id == project_id))
    ).scalars().first()

    measured: dict[uuid.UUID, list[str]] = {}
    if instruments:
        items = (
            await session.execute(
                select(InstrumentItem).where(
                    InstrumentItem.instrument_id.in_([i.id for i in instruments])
                )
            )
        ).scalars().all()
        for item in items:
            if item.variable_id:
                measured.setdefault(item.instrument_id, []).append(str(item.variable_id))

    discussion = "\n".join(e.detail_ar or e.label_ar for e in elements if e.element_type == "discussion")
    results = "\n".join(e.detail_ar or e.label_ar for e in elements if e.element_type == "result")

    return thread_graph.ThreadGraph(
        elements=[
            thread_graph.Element(
                element_id=str(e.id), element_type=e.element_type, label=e.label_ar,
                detail=e.detail_ar, theory_id=str(e.theory_id) if e.theory_id else None,
            )
            for e in elements
        ],
        links=[
            thread_graph.Link(str(link.source_element_id), str(link.target_element_id), link.link_type)
            for link in links
        ],
        variables=[
            thread_graph.VariableSpec(
                variable_id=str(v.id), name=v.name_ar, role=v.role,
                has_operational_definition=bool((v.operational_definition_ar or "").strip()),
                appears_in_title=v.appears_in_title,
                construct_id=str(v.construct_id) if v.construct_id else None,
            )
            for v in variables
        ],
        instruments=[
            thread_graph.InstrumentSpec(
                instrument_id=str(i.id), name=i.name_ar,
                measured_variable_ids=tuple(measured.get(i.id, [])),
            )
            for i in instruments
        ],
        method=(
            thread_graph.MethodSpec(
                study_type=method.study_type, design_family=method.design_family,
                sampling_strategy=method.sampling_strategy, sample_size=method.sample_size,
                population=method.population_ar,
            )
            if method else None
        ),
        discussion_text=discussion,
        results_text=results,
    )


def _consistency_response(result: score.GoldenThreadScore, locale: str) -> ConsistencyResponse:
    return ConsistencyResponse(
        score=result.score,
        findings=[
            FindingResponse(
                check_key=f.check_key, kind=f.kind, is_blocking=f.is_blocking,
                detail=_pick(locale, f.detail_ar, f.detail_en),
                detail_ar=f.detail_ar, detail_en=f.detail_en,
                element_ids=f.element_ids, excerpt=f.excerpt,
            )
            for f in result.findings
        ],
        missing_elements=result.missing_elements,
        blocking_count=result.blocking_count,
        advisory_count=result.advisory_count,
        can_pass_gate=result.can_pass_gate,
        note=_pick(locale, result.note_ar, result.note_en),
        note_ar=result.note_ar, note_en=result.note_en,
    )


@router.post("/projects/{project_id}/thread/elements", response_model=ElementResponse,
             status_code=status.HTTP_201_CREATED)
async def create_element(
    project_id: uuid.UUID,
    payload: ElementCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ElementResponse:
    element = ThreadElement(
        tenant_id=principal.tenant_id, project_id=project_id,
        element_type=payload.element_type, label_ar=payload.label_ar,
        label_en=payload.label_en, detail_ar=payload.detail_ar, ordinal=payload.ordinal,
    )
    session.add(element)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="thread.element_created",
        object_type="thread_element", object_id=element.id, actor_user_id=principal.user_id,
        state_after={"type": payload.element_type, "label": payload.label_ar[:120]},
    )
    return ElementResponse(
        id=element.id, element_type=element.element_type,
        label=_pick(principal.locale, element.label_ar, element.label_en),
        label_ar=element.label_ar, label_en=element.label_en, ordinal=element.ordinal,
    )


@router.post("/projects/{project_id}/thread/links", status_code=status.HTTP_201_CREATED)
async def create_link(
    project_id: uuid.UUID,
    payload: LinkCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    link = ThreadLink(
        tenant_id=principal.tenant_id, project_id=project_id,
        source_element_id=payload.source_element_id,
        target_element_id=payload.target_element_id,
        link_type=payload.link_type, note_ar=payload.note_ar,
    )
    session.add(link)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="thread.link_created",
        object_type="thread_link", object_id=link.id, actor_user_id=principal.user_id,
        state_after={"link_type": payload.link_type},
    )
    return {"id": str(link.id), "link_type": link.link_type}


@router.get("/projects/{project_id}/thread/consistency", response_model=ConsistencyResponse)
async def consistency(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ConsistencyResponse:
    result = score.compute(await _build_graph(session, project_id))
    return _consistency_response(result, principal.locale)


@router.get("/methodology/requirements/{study_type}", response_model=MethodologyResponse)
async def methodology_requirements(
    study_type: str,
    principal: Principal = Depends(get_principal),
    satisfied: str = "",
) -> MethodologyResponse:
    try:
        gaps = methodology.evaluate(
            study_type, {key.strip() for key in satisfied.split(",") if key.strip()}
        )
    except ValueError as exc:
        raise AtheraError("thread.unknown_study_type", status_code=422,
                          study_type=study_type) from exc
    return MethodologyResponse(
        study_type=gaps.study_type,
        requirements=[
            RequirementResponse(
                key=s.requirement.key,
                label=_pick(principal.locale, s.requirement.label_ar, s.requirement.label_en),
                label_ar=s.requirement.label_ar, label_en=s.requirement.label_en,
                is_blocking=s.requirement.is_blocking, gate=s.requirement.gate,
                satisfied=s.satisfied,
            )
            for s in gaps.statuses
        ],
        missing_blocking=[r.key for r in gaps.missing_blocking],
        missing_advisory=[r.key for r in gaps.missing_advisory],
        is_complete=gaps.is_complete,
    )


@router.post("/projects/{project_id}/protocol", response_model=ProtocolResponse,
             status_code=status.HTTP_201_CREATED)
async def create_protocol(
    project_id: uuid.UUID,
    payload: ProtocolCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProtocolResponse:
    protocol = Protocol(
        tenant_id=principal.tenant_id, project_id=project_id,
        version_label=payload.version_label, title_ar=payload.title_ar,
        summary_ar=payload.summary_ar, summary_en=payload.summary_en,
        current_gate="G2", status="draft",
    )
    session.add(protocol)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="protocol.created",
        object_type="protocol", object_id=protocol.id, actor_user_id=principal.user_id,
        state_after={"version": payload.version_label, "gate": "G2"},
    )
    return ProtocolResponse(
        id=protocol.id, project_id=project_id, version_label=protocol.version_label,
        title_ar=protocol.title_ar, current_gate=protocol.current_gate, status=protocol.status,
        approved_gate=None, approved_at=None, consistency=None,
    )


@router.post("/projects/{project_id}/protocol/submit-gate", response_model=ProtocolResponse)
async def submit_gate(
    project_id: uuid.UUID,
    payload: GateSubmitRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProtocolResponse:
    """§9 — البوابة تُفتح بغياب العيوب الحاجبة، لا ببلوغ درجة.

    ولقطة الاتساق تُحفظ مع الاعتماد: القرار يقع على حالة معروفة وموثقة، لا
    على حالة يمكن أن تتغير بعده بصمت.
    """
    protocol = (
        await session.execute(
            select(Protocol).where(Protocol.project_id == project_id)
            .order_by(Protocol.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if protocol is None:
        raise NotFound("thread.protocol_not_found")

    result = score.compute(await _build_graph(session, project_id))
    snapshot = {
        "score": result.score,
        "blocking_count": result.blocking_count,
        "advisory_count": result.advisory_count,
        "missing_elements": result.missing_elements,
        "findings": [f.check_key for f in result.findings],
    }

    if not result.can_pass_gate:
        protocol.consistency_snapshot = snapshot
        await audit.record(
            session, tenant_id=principal.tenant_id, action="protocol.gate_refused",
            object_type="protocol", object_id=protocol.id, actor_user_id=principal.user_id,
            state_after=snapshot,
            reason="blocking consistency findings or missing thread elements (§15.2)",
        )
        raise AtheraError("thread.gate_blocked", status_code=422,
                          blocking=str(result.blocking_count))

    protocol.current_gate = payload.gate
    protocol.approved_gate = payload.gate
    protocol.approved_by = principal.user_id
    protocol.approved_at = dt.datetime.now(dt.UTC)
    protocol.status = "approved"
    protocol.consistency_snapshot = snapshot

    await audit.record(
        session, tenant_id=principal.tenant_id, action="protocol.gate_approved",
        object_type="protocol", object_id=protocol.id, actor_user_id=principal.user_id,
        state_after={**snapshot, "gate": payload.gate},
        reason=payload.reason or "researcher approved the protocol gate",
    )
    return ProtocolResponse(
        id=protocol.id, project_id=project_id, version_label=protocol.version_label,
        title_ar=protocol.title_ar, current_gate=protocol.current_gate, status=protocol.status,
        approved_gate=protocol.approved_gate, approved_at=protocol.approved_at,
        consistency=_consistency_response(result, principal.locale),
    )
