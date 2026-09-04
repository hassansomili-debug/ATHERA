"""الخيط الذهبي والمنهجية والبروتوكول | Golden thread API (§15، §16، §9).

البوابة لا تُفتح بالدرجة بل بغياب الكشوفات الحاجبة والعناصر المفقودة —
والفرق جوهري: درجة 88 بلا عيب حاجب أفضل من 95 بعيب واحد يوقف الورقة.
"""
from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.analysis import (
    AnalysisOutputRow,
    AnalysisPlanRow,
    AnalysisRun,
    DataDictionary,
    InterpretationRow,
    PlannedTestRow,
)
from ..models.golden_thread import (
    Construct,
    Instrument,
    InstrumentItem,
    Method,
    Protocol,
    Theory,
    ThreadElement,
    ThreadLink,
    Variable,
)
from ..models.portfolio import ResearchProject
from ..schemas.golden_thread import (
    ConsistencyResponse,
    ElementCreateRequest,
    ElementResponse,
    FindingResponse,
    GateSubmitRequest,
    GoldenThreadView,
    LinkCreateRequest,
    MethodologyResponse,
    ProtocolCreateRequest,
    ProtocolResponse,
    RequirementResponse,
    ThreadConnectionView,
    ThreadNodeView,
    ThreadReadNoteView,
    ThreadStageView,
)
from ..services import audit
from ..services.golden_thread import graph as thread_graph
from ..services.golden_thread import methodology, score, weave

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


# ────────────────────────── الخيط كما يُعرض للباحث ──────────────────────────

NO_SCORE_NOTE_AR = (
    "لا تُعرض درجة اتساق هنا: الدرجة تُحسب لبوابة البروتوكول، ورقمٌ واحد يخفي "
    "الفرق بين خيطٍ تنقصه وصلةٌ وخيطٍ ينقصه منهج. وكل خطٍّ أدناه خلفه صفٌّ "
    "مخزَّن، وما لا صفَّ له يُترك فراغًا."
)
NO_SCORE_NOTE_EN = (
    "No consistency score is shown here: the score is computed for the protocol gate, and "
    "one number hides the difference between a thread missing a link and one missing a "
    "method. Every line below rests on a stored row; what has none is left blank."
)


async def _thread_snapshot(session: AsyncSession, tenant_id: uuid.UUID,
                           project_id: uuid.UUID) -> weave.ThreadSnapshot:
    """يقرأ صفوف هذا البحث كما هي — **ولا يشتقّ منها شيئًا**.

    والاشتقاق كله في `services/golden_thread/weave.py` لأنه منطقٌ علمي يجب
    أن يُختبر بلا قاعدة بيانات؛ وهذه الدالة نقلٌ من الجداول إلى بنيةٍ خالصة
    لا أكثر.

    وكل استعلامٍ هنا يذكر المستأجر والمشروع، أو يمرّ بصفٍّ يذكرهما. ولا
    قارئ يقرأ بالمستأجر وحده: الحادثة أثبتت أن RLS قد تسقط بسطرٍ في سرّ
    نشر، فتبقى الطبقة الثانية.
    """
    elements = (await session.execute(
        select(ThreadElement).where(ThreadElement.tenant_id == tenant_id,
                                    ThreadElement.project_id == project_id)
        .order_by(ThreadElement.ordinal)
    )).scalars().all()
    links = (await session.execute(
        select(ThreadLink).where(ThreadLink.tenant_id == tenant_id,
                                 ThreadLink.project_id == project_id)
    )).scalars().all()
    theories = (await session.execute(
        select(Theory).where(Theory.tenant_id == tenant_id,
                             Theory.project_id == project_id)
    )).scalars().all()
    constructs = (await session.execute(
        select(Construct).where(Construct.tenant_id == tenant_id,
                                Construct.project_id == project_id)
    )).scalars().all()
    variables = (await session.execute(
        select(Variable).where(Variable.tenant_id == tenant_id,
                               Variable.project_id == project_id)
    )).scalars().all()
    instruments = (await session.execute(
        select(Instrument).where(Instrument.tenant_id == tenant_id,
                                 Instrument.project_id == project_id)
    )).scalars().all()
    method = (await session.execute(
        select(Method).where(Method.tenant_id == tenant_id, Method.project_id == project_id)
        .order_by(Method.created_at.desc()).limit(1)
    )).scalars().first()

    measured: dict[uuid.UUID, list[str]] = {}
    if instruments:
        items = (await session.execute(
            select(InstrumentItem).where(
                InstrumentItem.tenant_id == tenant_id,
                InstrumentItem.instrument_id.in_([i.id for i in instruments]))
        )).scalars().all()
        for item in items:
            if item.variable_id:
                measured.setdefault(item.instrument_id, []).append(str(item.variable_id))

    plans = (await session.execute(
        select(AnalysisPlanRow).where(AnalysisPlanRow.tenant_id == tenant_id,
                                      AnalysisPlanRow.project_id == project_id)
    )).scalars().all()
    plan_ids = [p.id for p in plans]
    tests: Sequence[PlannedTestRow] = ()
    runs: Sequence[AnalysisRun] = ()
    outputs: Sequence[AnalysisOutputRow] = ()
    implications: Sequence[InterpretationRow] = ()
    columns: dict[uuid.UUID, list[str]] = {}
    if plan_ids:
        tests = (await session.execute(
            select(PlannedTestRow).where(PlannedTestRow.tenant_id == tenant_id,
                                         PlannedTestRow.plan_id.in_(plan_ids))
        )).scalars().all()
        runs = (await session.execute(
            select(AnalysisRun).where(AnalysisRun.tenant_id == tenant_id,
                                      AnalysisRun.plan_id.in_(plan_ids))
            .order_by(AnalysisRun.started_at)
        )).scalars().all()
    if runs:
        outputs = (await session.execute(
            select(AnalysisOutputRow).where(AnalysisOutputRow.tenant_id == tenant_id,
                                            AnalysisOutputRow.run_id.in_([r.id for r in runs]))
        )).scalars().all()
        # **المتغيّر يُقرأ من مفتاح قاموس البيانات لا من اسمٍ في نصّ.**
        # `planned_tests.variables` قائمةُ نصوصٍ حرّة، ومطابقتُها بأسماء
        # المتغيّرات تُنتج وصلةً بلا صفّ — وهي بالضبط ما تمنعه هذه الشاشة.
        dictionary = (await session.execute(
            select(DataDictionary).where(
                DataDictionary.tenant_id == tenant_id,
                DataDictionary.dataset_version_id.in_([r.dataset_version_id for r in runs]),
                DataDictionary.variable_id.is_not(None))
        )).scalars().all()
        for column in dictionary:
            columns.setdefault(column.dataset_version_id, []).append(str(column.variable_id))
        # **الدلالة الإدارية وحدها هي التوصية.** والطبقات الأربع في صفٍّ
        # واحد (§18.3)، فصفٌّ بلا طبقةٍ إدارية تفسيرٌ لا توصية — وعرضُه
        # توصيةً يجعل «فُسِّرت النتيجة» تُقرأ «أُوصي بشيء».
        implications = [
            row for row in (await session.execute(
                select(InterpretationRow).where(
                    InterpretationRow.tenant_id == tenant_id,
                    InterpretationRow.output_id.in_([o.id for o in outputs]))
            )).scalars().all()
            if (row.managerial_ar or "").strip()
        ] if outputs else []

    def _run_label(row: AnalysisRun) -> str:
        # التشغيلة بلا عمود تسمية، فتُسمّى بما نفّذته — وهو ما يعرفه الباحث
        # عنها. و«تشغيلة» وحدها تجعل خمس تشغيلاتٍ خمسةَ أسطرٍ متطابقة.
        return " · ".join(row.executed_test_keys or ()) or row.tool

    return weave.ThreadSnapshot(
        elements=[weave.ElementRow(
            id=str(e.id), element_type=e.element_type, label=e.label_ar,
            detail=e.detail_ar, theory_id=str(e.theory_id) if e.theory_id else None)
            for e in elements],
        links=[weave.LinkRow(str(link.source_element_id), str(link.target_element_id),
                             link.link_type) for link in links],
        theories=[weave.TheoryRow(str(t.id), t.name_ar) for t in theories],
        constructs=[weave.ConstructRow(
            str(c.id), c.name_ar, str(c.theory_id) if c.theory_id else None)
            for c in constructs],
        variables=[weave.VariableRow(
            id=str(v.id), label=v.name_ar,
            construct_id=str(v.construct_id) if v.construct_id else None,
            has_operational_definition=bool((v.operational_definition_ar or "").strip()),
            appears_in_title=v.appears_in_title) for v in variables],
        instruments=[weave.InstrumentRow(
            str(i.id), i.name_ar, tuple(measured.get(i.id, ()))) for i in instruments],
        method=(weave.MethodRow(
            id=str(method.id),
            label=method.design_label_ar or method.study_type,
            study_type=method.study_type, design_family=method.design_family)
            if method is not None else None),
        planned_tests=[weave.PlannedTestRow(
            id=str(t.id), test_key=t.test_key, plan_id=str(t.plan_id),
            hypothesis_id=str(t.hypothesis_id) if t.hypothesis_id else None)
            for t in tests],
        runs=[weave.RunRow(
            id=str(r.id), label=_run_label(r), plan_id=str(r.plan_id),
            dictionary_variable_ids=tuple(columns.get(r.dataset_version_id, ())))
            for r in runs],
        outputs=[weave.OutputRow(str(o.id), o.label_ar, str(o.run_id), o.test_key)
                 for o in outputs],
        implications=[weave.ImplicationRow(
            id=str(row.id), label=(row.managerial_ar or "")[:255],
            output_id=str(row.output_id)) for row in implications],
    )


@router.get("/projects/{project_id}/thread/golden-view", response_model=GoldenThreadView)
async def golden_view(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GoldenThreadView:
    """الخيط الذهبي مرسومًا — **ولا خطّ إلا خلفه صفّ**.

    وهذه قراءةٌ لا تكتب شيئًا ولا تفتح بوابة. والبوابة قرارٌ آخر في
    `submit-gate`، والدرجة تُحسب هناك ولا تُنقل إلى هنا: الباحث الذي يقرأ
    «٧٤٪» يطمئنّ، والذي يقرأ «ثلاث وصلات لا صفَّ لها» يذهب فيسجّلها.
    """
    project = (await session.execute(
        select(ResearchProject).where(ResearchProject.id == project_id,
                                      ResearchProject.tenant_id == principal.tenant_id,
                                      ResearchProject.deleted_at.is_(None))
    )).scalar_one_or_none()
    if project is None:
        raise NotFound("workspace.project_not_found")

    woven = weave.weave(await _thread_snapshot(session, principal.tenant_id, project_id))
    arabic = principal.locale != "en"

    return GoldenThreadView(
        project_id=project_id, title=project.working_title_ar,
        stages=[ThreadStageView(
            key=key, label=label_ar if arabic else label_en,
            label_ar=label_ar, label_en=label_en,
            nodes=[ThreadNodeView(id=n.id, stage=n.stage, label=n.label,
                                  origin=n.origin, detail=n.detail)
                   for n in woven.stage_nodes(key)])
            for key, label_ar, label_en in weave.STAGES],
        connections=[ThreadConnectionView(
            stage_from=c.stage_from, stage_to=c.stage_to, state=c.state,
            detail=c.detail_ar if arabic else c.detail_en,
            detail_ar=c.detail_ar, detail_en=c.detail_en,
            source_id=c.source_id, source_label=c.source_label,
            target_id=c.target_id, target_label=c.target_label, basis=c.basis)
            for c in woven.connections],
        read_notes=[ThreadReadNoteView(
            key=n.key, detail=n.detail_ar if arabic else n.detail_en,
            detail_ar=n.detail_ar, detail_en=n.detail_en) for n in woven.read_notes],
        counts=woven.counts(),
        note=NO_SCORE_NOTE_AR if arabic else NO_SCORE_NOTE_EN,
        note_ar=NO_SCORE_NOTE_AR, note_en=NO_SCORE_NOTE_EN)


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
