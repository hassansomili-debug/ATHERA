"""محرك التحليل | Analysis API (§17، §18، §31.6).

القواعد التي يفرضها هذا الموجّه:
  • RAW لا يُعدَّل: التنظيف ينشئ نسخة (TC-07).
  • لا تشغيل إلا على نسخة مجمَّدة (§17.3).
  • الخطة تُقفل قبل التنفيذ، والاستكشاف يُعلَن لا يُمنع (§9 G7، §51.8).
  • لا مخرَج بلا تشغيلة (§39)، ولا تفسير بلا مخرَج (§18.3).
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.analysis import (
    DataDictionary,
    ToolExport,
    AnalysisOutputRow,
    AnalysisPlanRow,
    AnalysisRun,
    Dataset,
    DatasetVersionRow,
    InterpretationRow,
    PlannedTestRow,
)
from ..schemas.analysis import (
    DatasetResponse,
    DictionaryCoverageResponse,
    DictionaryEntryInput,
    DictionaryEntryResponse,
    ToolExportRequest,
    ToolExportResponse,
    DatasetCreateRequest,
    DatasetVersionResponse,
    FreezeResponse,
    InterpretationRequest,
    InterpretationResponse,
    LayerResponse,
    OutputCreateRequest,
    PlanCreateRequest,
    PlannedTestInput,
    PlanResponse,
    RunCreateRequest,
    RunResponse,
    TestClassificationResponse,
    ToolCapabilityResponse,
    VersionCreateRequest,
)
from ..services import audit
from ..services.analysis import exports, interpretation, lineage, plan, reproducibility, vocab

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


def _pick(locale: str, arabic: str, english: str | None) -> str:
    return (english or arabic) if locale == "en" else arabic


def _version_response(row: DatasetVersionRow, locale: str) -> DatasetVersionResponse:
    label_ar, label_en = vocab.DATASET_STATES[row.state]
    return DatasetVersionResponse(
        id=row.id, dataset_id=row.dataset_id, state=row.state,
        state_label=_pick(locale, label_ar, label_en), label=row.label,
        checksum=row.checksum, parent_version_id=row.parent_version_id,
        row_count=row.row_count, change_note_ar=row.change_note_ar,
        freeze_id=row.freeze_id, frozen_at=row.frozen_at,
        is_immutable=row.state == "raw" or row.frozen_at is not None,
    )


@router.post("/datasets", response_model=DatasetVersionResponse,
             status_code=status.HTTP_201_CREATED)
async def create_dataset(
    payload: DatasetCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DatasetVersionResponse:
    dataset = Dataset(
        tenant_id=principal.tenant_id, project_id=payload.project_id,
        name_ar=payload.name_ar, name_en=payload.name_en,
        classification=payload.classification,
    )
    session.add(dataset)
    await session.flush()

    raw = DatasetVersionRow(
        tenant_id=principal.tenant_id, dataset_id=dataset.id, state="raw",
        label=payload.raw_label, checksum=payload.raw_checksum, row_count=payload.row_count,
    )
    session.add(raw)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.dataset_created",
        object_type="dataset", object_id=dataset.id, actor_user_id=principal.user_id,
        state_after={"classification": payload.classification, "raw_version": str(raw.id)},
        reason="raw version is immutable from creation (§17.2)",
    )
    return _version_response(raw, principal.locale)


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DatasetResponse]:
    datasets = (
        await session.execute(select(Dataset).order_by(Dataset.created_at.desc()))
    ).scalars().all()
    out: list[DatasetResponse] = []
    for dataset in datasets:
        versions = (
            await session.execute(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.dataset_id == dataset.id)
                .order_by(DatasetVersionRow.created_at)
            )
        ).scalars().all()
        out.append(DatasetResponse(
            id=dataset.id, project_id=dataset.project_id,
            name=_pick(principal.locale, dataset.name_ar, dataset.name_en),
            classification=dataset.classification,
            versions=[_version_response(v, principal.locale) for v in versions],
        ))
    return out


@router.get("/datasets/{dataset_id}/versions", response_model=list[DatasetVersionResponse])
async def list_versions(
    dataset_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[DatasetVersionResponse]:
    rows = (
        await session.execute(
            select(DatasetVersionRow)
            .where(DatasetVersionRow.dataset_id == dataset_id)
            .order_by(DatasetVersionRow.created_at)
        )
    ).scalars().all()
    return [_version_response(r, principal.locale) for r in rows]


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionResponse,
             status_code=status.HTTP_201_CREATED)
async def create_version(
    dataset_id: uuid.UUID,
    payload: VersionCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DatasetVersionResponse:
    """TC-07 — التنظيف ينشئ نسخة ولا يعدّل الأصل."""
    parent = (
        await session.execute(
            select(DatasetVersionRow).where(DatasetVersionRow.id == payload.parent_version_id)
        )
    ).scalar_one_or_none()
    if parent is None:
        raise NotFound("analysis.version_not_found")

    try:
        lineage.derive(
            lineage.DatasetVersion(
                version_id=str(parent.id), dataset_id=str(parent.dataset_id),
                state=parent.state, label=parent.label, checksum=parent.checksum,
                parent_version_id=(str(parent.parent_version_id)
                                   if parent.parent_version_id else None),
                frozen_at=parent.frozen_at, freeze_id=parent.freeze_id,
            ),
            new_state=payload.state, label=payload.label, checksum=payload.checksum,
            change_note_ar=payload.change_note_ar, row_count=payload.row_count,
            version_id=str(uuid.uuid4()),
        )
    except lineage.LineageError as exc:
        raise AtheraError("analysis.invalid_transition", status_code=422,
                          detail=str(exc)) from exc

    row = DatasetVersionRow(
        tenant_id=principal.tenant_id, dataset_id=dataset_id, state=payload.state,
        label=payload.label, checksum=payload.checksum, parent_version_id=parent.id,
        row_count=payload.row_count, change_note_ar=payload.change_note_ar,
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.version_derived",
        object_type="dataset_version", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"from": parent.state, "to": payload.state,
                     "reason": payload.change_note_ar[:200]},
        reason="a derived version never mutates its parent (TC-07)",
    )
    return _version_response(row, principal.locale)


@router.post("/datasets/versions/{version_id}/freeze", response_model=FreezeResponse)
async def freeze_version(
    version_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> FreezeResponse:
    """§17.3 — بوابة G6."""
    row = (
        await session.execute(
            select(DatasetVersionRow).where(DatasetVersionRow.id == version_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("analysis.version_not_found")

    now = dt.datetime.now(dt.UTC)
    try:
        frozen = lineage.freeze(
            lineage.DatasetVersion(
                version_id=str(row.id), dataset_id=str(row.dataset_id), state=row.state,
                label=row.label, checksum=row.checksum,
                parent_version_id=(str(row.parent_version_id)
                                   if row.parent_version_id else None),
                frozen_at=row.frozen_at, freeze_id=row.freeze_id,
            ),
            at=now,
        )
    except lineage.LineageError as exc:
        raise AtheraError("analysis.cannot_freeze", status_code=422, detail=str(exc)) from exc

    row.state = frozen.state
    row.freeze_id = frozen.freeze_id
    row.frozen_at = now
    row.frozen_by = principal.user_id

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.version_frozen",
        object_type="dataset_version", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"freeze_id": frozen.freeze_id, "state": frozen.state},
        reason="G6 — every later analysis cites this freeze id (§17.3)",
    )
    return FreezeResponse(version_id=row.id, freeze_id=frozen.freeze_id, frozen_at=now)


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[PlanResponse]:
    rows = (
        await session.execute(
            select(AnalysisPlanRow).order_by(AnalysisPlanRow.created_at.desc())
        )
    ).scalars().all()
    out: list[PlanResponse] = []
    for row in rows:
        tests = (
            await session.execute(
                select(PlannedTestRow).where(PlannedTestRow.plan_id == row.id)
            )
        ).scalars().all()
        out.append(PlanResponse(
            id=row.id, version_label=row.version_label, is_locked=row.lock_hash is not None,
            approved_at=row.approved_at,
            tests=[
                PlannedTestInput(test_key=t.test_key, test_kind=t.test_kind,
                                 variables=list(t.variables or []), note_ar=t.note_ar)
                for t in tests
            ],
        ))
    return out


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PlanResponse:
    for test in payload.tests:
        if test.test_kind not in vocab.TEST_KINDS:
            raise AtheraError("analysis.unknown_test_kind", status_code=422,
                              kind=test.test_kind)
    row = AnalysisPlanRow(
        tenant_id=principal.tenant_id, project_id=payload.project_id,
        version_label=payload.version_label, summary_ar=payload.summary_ar,
    )
    session.add(row)
    await session.flush()
    for test in payload.tests:
        session.add(PlannedTestRow(
            tenant_id=principal.tenant_id, plan_id=row.id, test_key=test.test_key,
            test_kind=test.test_kind, variables=test.variables, note_ar=test.note_ar,
        ))
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.plan_created",
        object_type="analysis_plan", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"tests": len(payload.tests)},
    )
    return PlanResponse(id=row.id, version_label=row.version_label, is_locked=False,
                        approved_at=None, tests=payload.tests)


@router.post("/plans/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan(
    plan_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> PlanResponse:
    """§9 G7 — الاعتماد يقفل القائمة بتجزئة."""
    row = (
        await session.execute(select(AnalysisPlanRow).where(AnalysisPlanRow.id == plan_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("analysis.plan_not_found")

    tests = (
        await session.execute(select(PlannedTestRow).where(PlannedTestRow.plan_id == plan_id))
    ).scalars().all()
    domain = plan.AnalysisPlan(
        plan_id=str(row.id),
        tests=[
            plan.PlannedTest(test_key=t.test_key, test_kind=t.test_kind,
                             variables=tuple(t.variables or ()))
            for t in tests
        ],
    )
    now = dt.datetime.now(dt.UTC)
    try:
        domain.approve(by=str(principal.user_id), at=now)
    except plan.PlanError as exc:
        raise AtheraError("analysis.cannot_approve_plan", status_code=422,
                          detail=str(exc)) from exc

    row.lock_hash = domain.lock_hash
    row.approved_by = principal.user_id
    row.approved_at = now

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.plan_approved",
        object_type="analysis_plan", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"lock_hash": domain.lock_hash, "tests": len(tests)},
        reason="G7 — tests are frozen before execution (§9)",
    )
    return PlanResponse(
        id=row.id, version_label=row.version_label, is_locked=True, approved_at=now,
        tests=[
            PlannedTestInput(test_key=t.test_key, test_kind=t.test_kind,
                             variables=list(t.variables or []), note_ar=t.note_ar)
            for t in tests
        ],
    )


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> RunResponse:
    plan_row = (
        await session.execute(
            select(AnalysisPlanRow).where(AnalysisPlanRow.id == payload.plan_id)
        )
    ).scalar_one_or_none()
    if plan_row is None:
        raise NotFound("analysis.plan_not_found")
    version = (
        await session.execute(
            select(DatasetVersionRow).where(DatasetVersionRow.id == payload.dataset_version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("analysis.version_not_found")
    if version.freeze_id is None:
        raise AtheraError("analysis.dataset_not_frozen", status_code=422,
                          version_id=str(version.id))

    tests = (
        await session.execute(
            select(PlannedTestRow).where(PlannedTestRow.plan_id == plan_row.id)
        )
    ).scalars().all()
    domain = plan.AnalysisPlan(
        plan_id=str(plan_row.id),
        tests=[
            plan.PlannedTest(test_key=t.test_key, test_kind=t.test_kind,
                             variables=tuple(t.variables or ()))
            for t in tests
        ],
        approved_at=plan_row.approved_at,
        approved_by=str(plan_row.approved_by) if plan_row.approved_by else None,
        lock_hash=plan_row.lock_hash,
    )
    try:
        compliance = plan.classify_run(domain, payload.executed_test_keys)
    except plan.PlanError as exc:
        raise AtheraError("analysis.plan_not_locked", status_code=422,
                          detail=str(exc)) from exc

    manifest = reproducibility.RunManifest(
        code_hash=payload.code_hash, runtime=payload.runtime, packages=payload.packages,
        dataset_version_id=str(version.id), dataset_freeze_id=version.freeze_id,
        random_seed=payload.random_seed,
    )
    run_id = uuid.uuid4()
    state = reproducibility.assess(str(run_id), manifest)

    row = AnalysisRun(
        id=run_id, tenant_id=principal.tenant_id, plan_id=plan_row.id,
        dataset_version_id=version.id, dataset_freeze_id=version.freeze_id,
        tool=payload.tool, code_hash=payload.code_hash, runtime=payload.runtime,
        packages=payload.packages, random_seed=payload.random_seed,
        fingerprint=state.fingerprint, is_reproducible=state.reproducible,
        missing_manifest_fields=state.missing,
        executed_test_keys=payload.executed_test_keys,
        exploratory_test_keys=compliance.exploratory_keys,
        requires_disclosure=compliance.requires_disclosure,
        network_egress=False, started_at=dt.datetime.now(dt.UTC), status="completed",
        finished_at=dt.datetime.now(dt.UTC),
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.run_recorded",
        object_type="analysis_run", object_id=row.id, actor_user_id=principal.user_id,
        state_after={
            "reproducible": state.reproducible, "missing": state.missing,
            "exploratory": compliance.exploratory_keys,
            "planned_not_run": compliance.planned_not_run,
        },
        reason="exploratory tests are disclosed, never silently dropped (§51.8)",
    )
    return RunResponse(
        id=row.id, tool=row.tool, status=row.status, is_reproducible=state.reproducible,
        missing_manifest_fields=state.missing, fingerprint=state.fingerprint,
        classifications=[
            TestClassificationResponse(
                test_key=c.test_key, origin=c.origin,
                reason=_pick(principal.locale, c.reason_ar, c.reason_en),
            )
            for c in compliance.classifications
        ],
        exploratory_test_keys=compliance.exploratory_keys,
        planned_not_run=compliance.planned_not_run,
        requires_disclosure=compliance.requires_disclosure,
        detail=_pick(principal.locale, state.detail_ar, state.detail_en),
        detail_ar=state.detail_ar, detail_en=state.detail_en,
    )


@router.post("/runs/{run_id}/outputs", status_code=status.HTTP_201_CREATED)
async def create_output(
    run_id: uuid.UUID,
    payload: OutputCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """§39 — المخرَج لا يوجد بلا تشغيلة."""
    run = (
        await session.execute(select(AnalysisRun).where(AnalysisRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise NotFound("analysis.run_not_found")

    row = AnalysisOutputRow(
        tenant_id=principal.tenant_id, run_id=run_id, output_kind=payload.output_kind,
        test_key=payload.test_key, label_ar=payload.label_ar, label_en=payload.label_en,
        payload=payload.payload,
    )
    session.add(row)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.output_recorded",
        object_type="analysis_output", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"kind": payload.output_kind, "run": str(run_id)},
    )
    return {"id": str(row.id), "run_id": str(run_id)}


@router.post("/outputs/{output_id}/interpret", response_model=InterpretationResponse)
async def interpret(
    output_id: uuid.UUID,
    payload: InterpretationRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> InterpretationResponse:
    """§18.3 / §9 G8 — أربع طبقات منفصلة بسلسلة سند."""
    output = (
        await session.execute(
            select(AnalysisOutputRow).where(AnalysisOutputRow.id == output_id)
        )
    ).scalar_one_or_none()
    if output is None:
        raise NotFound("analysis.output_not_found")

    try:
        domain = interpretation.Interpretation(
            output_id=str(output_id), result_ar=payload.result_ar,
            result_en=payload.result_en, statistical_ar=payload.statistical_ar,
            theoretical_ar=payload.theoretical_ar, managerial_ar=payload.managerial_ar,
        )
    except interpretation.InterpretationError as exc:
        raise AtheraError("analysis.invalid_interpretation", status_code=422,
                          detail=str(exc)) from exc

    now = dt.datetime.now(dt.UTC)
    existing = (
        await session.execute(
            select(InterpretationRow).where(InterpretationRow.output_id == output_id)
        )
    ).scalar_one_or_none()
    row = existing or InterpretationRow(
        tenant_id=principal.tenant_id, output_id=output_id, result_ar=payload.result_ar
    )
    row.result_ar = payload.result_ar
    row.result_en = payload.result_en
    row.statistical_ar = payload.statistical_ar
    row.theoretical_ar = payload.theoretical_ar
    row.managerial_ar = payload.managerial_ar
    row.approved_by = principal.user_id
    row.approved_at = now
    if existing is None:
        session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.interpretation_approved",
        object_type="interpretation", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"layers": domain.layers_present},
        reason="G8 — interpretation is bound to an actual output (§18.3)",
    )
    return InterpretationResponse(
        output_id=output_id,
        layers=[
            LayerResponse(layer=v.layer,
                          label=_pick(principal.locale, v.label_ar, v.label_en),
                          text_ar=v.text_ar, text_en=v.text_en)
            for v in interpretation.layers(domain)
        ],
        layers_present=domain.layers_present, approved_at=now,
    )


@router.get("/tools", response_model=list[ToolCapabilityResponse])
async def tool_capabilities(
    principal: Principal = Depends(get_principal),
) -> list[ToolCapabilityResponse]:
    """§18.2 / §47.9 — كل أداة تعلن ما لا تدعمه."""
    return [
        ToolCapabilityResponse(
            tool=c.tool, label=_pick(principal.locale, c.label_ar, c.label_en),
            import_formats=list(c.import_formats), export_formats=list(c.export_formats),
            supported=_pick(principal.locale, c.supported_ar, c.supported_en),
            not_supported=_pick(principal.locale, c.not_supported_ar, c.not_supported_en),
            not_supported_ar=c.not_supported_ar, not_supported_en=c.not_supported_en,
        )
        for c in exports.all_capabilities()
    ]


# ---------------------------------------------------------------------------
# §17.4 — قاموس البيانات
# ---------------------------------------------------------------------------


def _entry(row: DataDictionary) -> DictionaryEntryResponse:
    return DictionaryEntryResponse(
        id=row.id, dataset_version_id=row.dataset_version_id, column_name=row.column_name,
        label_ar=row.label_ar, scale_type=row.scale_type,
        value_labels=row.value_labels, is_pii=row.is_pii,
    )


@router.get("/datasets/versions/{version_id}/dictionary",
            response_model=DictionaryCoverageResponse)
async def read_dictionary(
    version_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DictionaryCoverageResponse:
    rows = (
        await session.execute(
            select(DataDictionary)
            .where(DataDictionary.dataset_version_id == version_id)
            .order_by(DataDictionary.column_name)
        )
    ).scalars().all()
    pii = sum(1 for row in rows if row.is_pii)
    note_ar = (
        f"موصوف: {len(rows)} عمودًا، منها {pii} تحمل بيانات شخصية. "
        "التغطية تُقاس مقابل الأعمدة الفعلية في الملف، ولا تُستنتج من هذا العدد وحده."
    )
    note_en = (
        f"{len(rows)} described columns, {pii} carrying personal data. "
        "Coverage is measured against the file's actual columns, not inferred from this count."
    )
    return DictionaryCoverageResponse(
        dataset_version_id=version_id, described_columns=len(rows), pii_columns=pii,
        entries=[_entry(row) for row in rows],
        note=_pick(principal.locale, note_ar, note_en),
    )


@router.put("/datasets/versions/{version_id}/dictionary",
            response_model=DictionaryCoverageResponse)
async def upsert_dictionary(
    version_id: uuid.UUID,
    payload: list[DictionaryEntryInput],
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DictionaryCoverageResponse:
    """§17.4 — القاموس يُكتب على نسخة **قبل** تجميدها.

    نسخة مجمَّدة تُرفض هنا: تغيير وصف عمود بعد التجميد يغيّر معنى تحليل جرى
    على الوصف القديم، بلا أن يتغيّر شيء في السجل يشي بذلك.
    """
    version = (
        await session.execute(
            select(DatasetVersionRow).where(DatasetVersionRow.id == version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("analysis.version_not_found")
    if version.frozen_at is not None:
        raise AtheraError("analysis.dictionary_frozen", status_code=422)

    names = [entry.column_name for entry in payload]
    if len(names) != len(set(names)):
        raise AtheraError("analysis.duplicate_column", status_code=422)

    existing = (
        await session.execute(
            select(DataDictionary).where(DataDictionary.dataset_version_id == version_id)
        )
    ).scalars().all()
    by_name = {row.column_name: row for row in existing}

    for entry in payload:
        row = by_name.get(entry.column_name)
        if row is None:
            row = DataDictionary(
                tenant_id=principal.tenant_id, dataset_version_id=version_id,
                column_name=entry.column_name,
            )
            session.add(row)
        row.label_ar = entry.label_ar
        row.scale_type = entry.scale_type
        row.value_labels = entry.value_labels
        row.is_pii = entry.is_pii
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.dictionary_updated",
        object_type="dataset_version", object_id=version_id, actor_user_id=principal.user_id,
        state_after={"columns": len(payload),
                     "pii": sum(1 for entry in payload if entry.is_pii)},
    )
    return await read_dictionary(version_id, principal, session)


# ---------------------------------------------------------------------------
# §18.5 — تصدير إلى الأدوات
# ---------------------------------------------------------------------------


@router.get("/exports", response_model=list[ToolExportResponse])
async def list_exports(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ToolExportResponse]:
    rows = (
        await session.execute(select(ToolExport).order_by(ToolExport.created_at.desc()))
    ).scalars().all()
    out: list[ToolExportResponse] = []
    for row in rows:
        cap = exports.capability(row.tool)
        out.append(ToolExportResponse(
            id=row.id, dataset_version_id=row.dataset_version_id, run_id=row.run_id,
            tool=row.tool, tool_label=_pick(principal.locale, cap.label_ar, cap.label_en),
            export_format=row.export_format,
            limitations=_pick(principal.locale, row.limitations_ar, row.limitations_en),
            created_at=row.created_at,
        ))
    return out


@router.post("/exports", response_model=ToolExportResponse,
             status_code=status.HTTP_201_CREATED)
async def create_export(
    payload: ToolExportRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ToolExportResponse:
    """§18.5 — كل تصدير يُسجَّل ومعه ما لا تدعمه الصيغة.

    الحدود تُنسخ من قدرات الأداة وقت التصدير، لا تُقرأ لاحقًا: لو تغيّرت
    القدرات غدًا، يبقى التصدير القديم يحمل ما قيل لصاحبه يومها.
    """
    version = (
        await session.execute(
            select(DatasetVersionRow).where(
                DatasetVersionRow.id == payload.dataset_version_id
            )
        )
    ).scalar_one_or_none()
    if version is None:
        raise NotFound("analysis.version_not_found")

    try:
        cap = exports.capability(payload.tool)
    except exports.ExportError as exc:
        raise AtheraError("analysis.unknown_tool", status_code=422,
                          detail=str(exc)) from exc
    if payload.export_format not in cap.export_formats:
        raise AtheraError("analysis.unsupported_format", status_code=422,
                          tool=payload.tool, format=payload.export_format)

    row = ToolExport(
        tenant_id=principal.tenant_id, run_id=payload.run_id,
        dataset_version_id=payload.dataset_version_id, tool=payload.tool,
        export_format=payload.export_format,
        limitations_ar=cap.not_supported_ar, limitations_en=cap.not_supported_en,
    )
    session.add(row)
    await session.flush()

    await audit.record(
        session, tenant_id=principal.tenant_id, action="analysis.exported",
        object_type="tool_export", object_id=row.id, actor_user_id=principal.user_id,
        state_after={"tool": payload.tool, "format": payload.export_format},
        reason=cap.not_supported_ar,
    )
    return ToolExportResponse(
        id=row.id, dataset_version_id=row.dataset_version_id, run_id=row.run_id,
        tool=row.tool, tool_label=_pick(principal.locale, cap.label_ar, cap.label_en),
        export_format=row.export_format,
        limitations=_pick(principal.locale, cap.not_supported_ar, cap.not_supported_en),
        created_at=row.created_at,
    )
