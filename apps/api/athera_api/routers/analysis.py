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

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import project_session, scoped_tenant, tenant_session
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
from ..services import audit, collaboration, data_scope, idempotency
from ..services.analysis import exports, interpretation, lineage, plan, reproducibility, vocab
from ..transaction import TransactionalRoute

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"], route_class=TransactionalRoute)


# ═════════════ حدُّ البحث على طبقة البيانات ═════════════
#
# **هذه أخطرُ سطوحِ المنصّة، وكانت أعراها.** لا مسارَ هنا كان يسأل عن
# البحث أصلًا: كلُّ شيء كان يُقرأ ويُكتب بمعرّفه وحده متّكلًا على عزل
# المستأجر. فكان أيُّ باحثٍ في المؤسسة يُدرج مجموعةَ بيانات في بحثِ زميله،
# ويقرأ قاموسَ أعمدتها — **وفيه الأعمدةُ الموسومةُ ببياناتٍ شخصية** —
# ويجمّد نسخةً، ويشغّل تحليلًا، ويصدّرها إلى أداةٍ خارجية.
#
# و«الاطّلاع على البحث» ليس إذنًا بالبيانات: القراءةُ تكفي لرؤية أنّ هناك
# مجموعة، وكلُّ مساسٍ بها يطلب `manage_data` — وهو الصفُّ الذي يحمله
# الإحصائيّ في هذا النظام، لا كلُّ من رأى البحث.
#
# والسلسلةُ تُتبع إلى جذرها دائمًا: المخرَجُ إلى تشغيلته، والتشغيلةُ إلى
# خطّتها، والخطّةُ إلى بحثها؛ والنسخةُ إلى مجموعتها، والمجموعةُ إلى بحثها.
# **ولا تُقطع السلسلةُ عند أوّل جدولٍ يحمل `tenant_id`** — فذاك بالضبط
# ما جعل هذه الطبقة مفتوحة.

DATA = "manage_data"
EDIT = "edit_research_content"
APPROVE = "approve_scientific_candidates"


@dataclass(frozen=True, slots=True)
class _Scope:
    """نطاقُ بحثٍ مفتوحٌ: جلسةٌ في مستأجره، ومعرّفُه، ومستأجرُه النافذ."""

    session: AsyncSession
    project_id: uuid.UUID
    tenant_id: uuid.UUID


@asynccontextmanager
async def _scope(
    principal: Principal, *, permission: str, not_found: str,
    project_id: uuid.UUID | None = None,
    **keys: uuid.UUID,
) -> AsyncIterator[_Scope]:
    """**البوابةُ الوحيدةُ لكلّ مسارٍ في هذه الطبقة** — تحديدًا ثمّ عبورًا.

    وثلاثُ خطواتٍ بترتيبٍ مقصود:

      ١ **التحديد**: أيُّ بحثٍ يملك هذا الكيان؟ — من جلسة البيت، بسياسات
        تحديد الموضع (0036). ومن سأل عن معرّفٍ لا يملكه يُردّ جوابَ
        المعدوم، فلا يُعلم أوجد أم لا.
      ٢ **العبور**: `project_session` تُدخل مستأجرَ البحث إن كان للفاعل
        فيه عضويّةٌ نشِطةٌ حاملةٌ للاطّلاع — والفاعلُ لا يتبدّل.
      ٣ **التفويض**: `ensure_project_access` **داخلَ** مستأجر البحث،
        بالصلاحية التي يطلبها هذا المسار بعينه.

    ## والصلاحيةُ صلاحيةُ المسار، لا صلاحيةُ الجسر

    فمن يُوافق على خطّةٍ يحتاج `approve_scientific_candidates`، ومن يفسّر
    مخرَجًا يحتاج `edit_research_content` — **ولا يوسّعهما `manage_data`**.
    وهذا الفرقُ محفوظٌ كما كان قبل الجسر: البوابةُ تنقل السياق، ولا
    تُغيّر مَن يملك ماذا.

    وأثرُ سياسة التحديد أنّها **تضيّق** لا توسّع: الكيانُ غيرُ المباشر
    لا يُعلم موضعُه عبرَ المؤسسات إلّا لمن يحمل إدارةَ البيانات. فمتعاونٌ
    من مؤسسةٍ أخرى يحمل التحريرَ بلا إدارةِ بيانات لا يبلغ مخرَجًا
    بمعرّفه — وذاك أضيقُ من نظيره في المستأجر نفسِه، وهو مقصودٌ ومُعلَن.

    ## ولمَ جلستان

    الأولى تُحدّد الموضع ثمّ **تُغلق**، والثانية تعمل في مستأجر البحث.
    ودمجُهما غيرُ ممكن: المعرّفُ لا يُعلم بحثَه إلّا بقراءةٍ، والقراءةُ
    في المستأجر الخطأ ترى صفرَ صفوف. وللمسارات التي تحمل معرّفَ البحث
    أصلًا **لا تُفتح الأولى**: تُعبَر مباشرةً.
    """
    if project_id is None:
        async with tenant_session(principal.tenant_id, principal.user_id) as home:
            project_id = await data_scope.locate(home, **keys)
        if project_id is None:
            raise NotFound(not_found)

    async with project_session(project_id, principal.tenant_id,
                               principal.user_id) as session:
        tenant_id = scoped_tenant(session, principal.tenant_id)
        assert tenant_id is not None  # noqa: S101 — مضمونٌ بمُعامِلٍ غيرِ فارغ
        await collaboration.ensure_project_access(
            session, tenant_id=tenant_id, project_id=project_id,
            user_id=principal.user_id, permission=permission,
            not_found_code=not_found)
        yield _Scope(session=session, project_id=project_id, tenant_id=tenant_id)


@asynccontextmanager
async def _scope_pair(
    principal: Principal, *, permission: str, not_found: str,
    first: dict[str, uuid.UUID], second: dict[str, uuid.UUID],
) -> AsyncIterator[_Scope]:
    """نطاقٌ لكيانَين **يجب أن يكون جذرُهما بحثًا واحدًا**.

    فتشغيلةٌ تُبنى على خطّةٍ ونسخةِ بيانات: لو فُوّض كلٌّ على حدة لَشغّل
    مَن يُدير بحثين خطّةَ هذا على بياناتِ ذاك — وبعد جسر المؤسسات يصير
    ذلك خلطًا لبيانات مؤسسةٍ في خطّةِ أخرى. وجوابُ عدمِ التطابق جوابُ
    المعدوم: لا يُقال أيُّهما لم يُطابق.
    """
    async with tenant_session(principal.tenant_id, principal.user_id) as home:
        project_id = await data_scope.same_project(
            home, first=first, second=second)
    if project_id is None:
        raise NotFound(not_found)
    async with _scope(principal, permission=permission, not_found=not_found,
                      project_id=project_id) as scope:
        yield scope


async def _managed(session: AsyncSession, principal: Principal) -> set[uuid.UUID]:
    """بحوثٌ يملك فيها الطالبُ **إدارةَ البيانات** — لا التي يراها فقط.

    فقوائمُ هذه الطبقة تفصيليّة: المجموعةُ بنسخها وحالاتها، والخطّةُ
    باختباراتها ومتغيّراتها، والتصديرُ بأداته وحدوده. و«يرى البحث» ليس
    «يرى بياناته» — فالمُرشِّح يقرأ الصفَّ المخصّص لها.
    """
    #
    # **وتعبُر المؤسسات منذ 0036.** فالإحصائيُّ المدعوُّ من مؤسسةٍ أخرى
    # يرى مجموعاتِ البحث الذي قُبل فيه — وصفوفُها مرئيّةٌ له بسياسات
    # تحديد الموضع. **ولا يرى بحثًا آخرَ في تلك المؤسسة**: المُرشِّحُ
    # مجموعةُ بحوثه هو، والسياسةُ حدُّها الثاني.
    return await collaboration.project_ids_with_across_tenants(
        session, tenant_id=principal.tenant_id, user_id=principal.user_id,
        permission=DATA)


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
) -> DatasetVersionResponse:
    # **والبحثُ في الجسم مُنتقي نطاقٍ لا سلطة**: يُعبَر به، ثمّ يقرّر
    # `ensure_project_access` من يدخل. ولا مستأجرَ يأتي من عميل.
    async with _scope(principal, permission=DATA,
                      not_found="workspace.project_not_found",
                      project_id=payload.project_id) as scope:
        dataset = Dataset(
            tenant_id=scope.tenant_id, project_id=payload.project_id,
            name_ar=payload.name_ar, name_en=payload.name_en,
            classification=payload.classification,
        )
        scope.session.add(dataset)
        await scope.session.flush()

        raw = DatasetVersionRow(
            tenant_id=scope.tenant_id, dataset_id=dataset.id, state="raw",
            label=payload.raw_label, checksum=payload.raw_checksum, row_count=payload.row_count,
        )
        scope.session.add(raw)
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.dataset_created",
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
    visible = await _managed(session, principal)
    datasets = [] if not visible else (
        await session.execute(select(Dataset)
                              .where(Dataset.project_id.in_(visible))
                              .order_by(Dataset.created_at.desc()))
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
) -> list[DatasetVersionResponse]:
    # **ونسخُ المجموعة بيانُ إدارةٍ لا بيانُ تقدّم**: الحالاتُ والبصماتُ
    # وأعدادُ الصفوف ومعرّفاتُ التجميد. و«أنّ للبحث مجموعةً» تقوله الرحلةُ
    # بلا شيءٍ من هذا.
    async with _scope(principal, permission=DATA,
                      not_found="analysis.dataset_not_found",
                      dataset=dataset_id) as scope:
        rows = (
            await scope.session.execute(
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
) -> DatasetVersionResponse:
    """TC-07 — التنظيف ينشئ نسخة ولا يعدّل الأصل."""
    async with _scope(principal, permission=DATA,
                      not_found="analysis.dataset_not_found",
                      dataset=dataset_id) as scope:
        parent = (
            await scope.session.execute(
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
            tenant_id=scope.tenant_id, dataset_id=dataset_id, state=payload.state,
            label=payload.label, checksum=payload.checksum, parent_version_id=parent.id,
            row_count=payload.row_count, change_note_ar=payload.change_note_ar,
        )
        scope.session.add(row)
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.version_derived",
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
) -> FreezeResponse:
    """§17.3 — بوابة G6."""
    async with _scope(principal, permission=DATA,
                      not_found="analysis.version_not_found",
                      version=version_id) as scope:
        row = (
            await scope.session.execute(
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
            scope.session, tenant_id=scope.tenant_id, action="analysis.version_frozen",
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
    visible = await _managed(session, principal)
    rows = [] if not visible else (
        await session.execute(
            select(AnalysisPlanRow)
            .where(AnalysisPlanRow.project_id.in_(visible))
            .order_by(AnalysisPlanRow.created_at.desc())
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
) -> PlanResponse:
    for test in payload.tests:
        if test.test_kind not in vocab.TEST_KINDS:
            raise AtheraError("analysis.unknown_test_kind", status_code=422,
                              kind=test.test_kind)
    async with _scope(principal, permission=DATA,
                      not_found="workspace.project_not_found",
                      project_id=payload.project_id) as scope:
        row = AnalysisPlanRow(
            tenant_id=scope.tenant_id, project_id=payload.project_id,
            version_label=payload.version_label, summary_ar=payload.summary_ar,
        )
        scope.session.add(row)
        await scope.session.flush()
        for test in payload.tests:
            scope.session.add(PlannedTestRow(
                tenant_id=scope.tenant_id, plan_id=row.id, test_key=test.test_key,
                test_kind=test.test_kind, variables=test.variables, note_ar=test.note_ar,
            ))
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.plan_created",
            object_type="analysis_plan", object_id=row.id, actor_user_id=principal.user_id,
            state_after={"tests": len(payload.tests)},
        )
        return PlanResponse(id=row.id, version_label=row.version_label, is_locked=False,
                            approved_at=None, tests=payload.tests)


async def _approve_plan_in_scope(
    scope: _Scope, plan_id: uuid.UUID, principal: Principal,
) -> PlanResponse:
    """اعتمادُ الخطّة داخلَ نطاقٍ مفتوح — **نواةٌ واحدةٌ لشكلَي المسار**.

    فالمسارُ القديم يُحدّد البحثَ من الخطّة، والجديدُ يأخذه في مساره.
    والعملُ بعد ذلك واحد: نسختان منه تفترقان بأوّل تعديل، فيصير شكلٌ
    يقفل القائمةَ بتجزئةٍ وآخرُ ينساها.
    """
    row = (
        await scope.session.execute(
            select(AnalysisPlanRow).where(AnalysisPlanRow.id == plan_id))
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("analysis.plan_not_found")

    tests = (
        await scope.session.execute(
            select(PlannedTestRow).where(PlannedTestRow.plan_id == plan_id))
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
        scope.session, tenant_id=scope.tenant_id, action="analysis.plan_approved",
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


@router.post("/projects/{project_id}/plans/{plan_id}/approve",
             response_model=PlanResponse)
async def approve_plan_in_project(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> PlanResponse:
    """§9 G7 — الاعتماد في نطاق بحثه: **الصلاحياتُ مستقلّةٌ فعلًا**.

    ## ولمَ شكلٌ ثانٍ لهذا المسار

    الاعتمادُ يطلب `approve_scientific_candidates` — لا `manage_data`.
    والشكلُ القديم يُعرَّف بمعرّف الخطّة وحده، فيلزمه **تحديدُ موضع**
    ليعرف بحثَها؛ وجسرُ تحديد الموضع (0036) مشروطٌ بإدارةِ البيانات.
    فكان المشرفُ من مؤسسةٍ أخرى — وهو من يعتمد — يحتاج صلاحيةً لا شأنَ
    لها بعمله: `manage_data + approve`. **وذاك نقضٌ لاستقلال الصلاحيات**،
    ولا يجوز أن يصير دلالةَ RC-T1C.

    فيُمرَّر البحثُ في المسار، فلا حاجةَ إلى تحديدِ موضع: يُعبَر إليه
    مباشرةً، ويُسأل عن **صلاحيّة الاعتماد وحدها**.

    ## والبحثُ في المسار مُنتقي نطاقٍ لا سلطة

    فلا يُفتح بابٌ بذكر معرّف: `ensure_project_access` تقرّر بعد العبور.
    **ثمّ تُطابق جذورُ الخطّة بالبحث المذكور** — فمن ذكر بحثًا يعتمد فيه
    وخطّةً من بحثٍ آخرَ يُردّ جوابَ المعدوم، ولا يُقال أيُّهما لم يُطابق.
    """
    async with _scope(principal, permission=APPROVE,
                      not_found="analysis.plan_not_found",
                      project_id=project_id) as scope:
        root = (
            await scope.session.execute(
                select(AnalysisPlanRow.project_id)
                .where(AnalysisPlanRow.id == plan_id))
        ).scalar_one_or_none()
        if root != project_id:
            raise NotFound("analysis.plan_not_found")
        return await _approve_plan_in_scope(scope, plan_id, principal)


@router.post("/plans/{plan_id}/approve", response_model=PlanResponse)
async def approve_plan(
    plan_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> PlanResponse:
    """§9 G7 — الاعتماد يقفل القائمة بتجزئة. **والشكلُ القديم باقٍ.**

    ولا يُحوَّل ولا يُحذف: من حفظ عنوانَه يجده يعمل، وسلوكُه في المستأجر
    الواحد كما كان بحرفه.

    **وحدُّه المعلَن**: عبرَ المؤسسات يلزمه `manage_data` أيضًا — لأنّ
    تحديدَ موضع الخطّة يمرّ بجسر البيانات. والمسارُ المُعشَّشُ في بحثه
    هو الطريقُ القانونيُّ لذلك، وهو ما تستعمله واجهةُ المنتج متى كان
    البحثُ معلومًا.
    """
    # **والموافقةُ تبقى `approve_scientific_candidates`** — لا يوسّعها
    # `manage_data` ولا الجسر.
    async with _scope(principal, permission=APPROVE,
                      not_found="analysis.plan_not_found",
                      plan=plan_id) as scope:
        return await _approve_plan_in_scope(scope, plan_id, principal)


@router.post("/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    request: Request,
    payload: RunCreateRequest,
    principal: Principal = Depends(get_principal),
) -> RunResponse | JSONResponse:
    # **والخطّةُ والنسخةُ من بحثٍ واحد أو لا تشغيلة.** وكان كلٌّ
    # يُفوَّض على حدة، فمن يُدير بحثين يشغّل خطّةَ هذا على بياناتِ ذاك.
    async with _scope_pair(
            principal, permission=DATA, not_found="analysis.plan_not_found",
            first={"plan": payload.plan_id},
            second={"version": payload.dataset_version_id}) as scope:
        # ══ تحمُّلُ إعادةٍ آمنة (RC-T1-H2-A) — **داخل النطاق المُفوَّض** ══
        #
        # و`_scope_pair` فوق قد حدّدت البحثَ وعبرت إلى مستأجره وفوّضت
        # بصلاحية `manage_data`. فالحارسُ هنا يقع **بعد** ذلك كلِّه: مَن
        # سُحبت صلاحيّتُه لا يبلغ هذا السطرَ أصلًا، فلا جوابَ مخزونٌ يُعاد له.
        #
        # **والمستأجرُ هو المستأجرُ النافذ** (`scope.tenant_id`) لا مستأجرُ
        # الرمز: الجلسةُ في مستأجر البحث، وسياسةُ الصفّ تقارن بما ضُبط
        # فيها. ومتعاونٌ من مؤسسةٍ أخرى يُكتب صفُّه حيث تقع طفرتُه.
        #
        # وهذا المسارُ يملك معاملتَه في متنه — جلسةُ النطاق لا جلسةُ
        # البيت — فالصفُّ والتشغيلةُ يُودَعان معًا عند خروج النطاق.
        guard = await idempotency.begin(
            request, scope.session, tenant_id=scope.tenant_id,
            actor_user_id=principal.user_id,
            body=payload.model_dump(mode="json"))
        if guard.replay is not None:
            return guard.replay_response()

        plan_row = (
            await scope.session.execute(
                select(AnalysisPlanRow).where(AnalysisPlanRow.id == payload.plan_id)
            )
        ).scalar_one_or_none()
        if plan_row is None:
            raise NotFound("analysis.plan_not_found")
        version = (
            await scope.session.execute(
                select(DatasetVersionRow).where(DatasetVersionRow.id == payload.dataset_version_id)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFound("analysis.version_not_found")
        if version.freeze_id is None:
            raise AtheraError("analysis.dataset_not_frozen", status_code=422,
                              version_id=str(version.id))

        tests = (
            await scope.session.execute(
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
            id=run_id, tenant_id=scope.tenant_id, plan_id=plan_row.id,
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
        scope.session.add(row)
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.run_recorded",
            object_type="analysis_run", object_id=row.id, actor_user_id=principal.user_id,
            state_after={
                "reproducible": state.reproducible, "missing": state.missing,
                "exploratory": compliance.exploratory_keys,
                "planned_not_run": compliance.planned_not_run,
            },
            reason="exploratory tests are disclosed, never silently dropped (§51.8)",
        )
        response = RunResponse(
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
        await guard.finish(scope.session, status=status.HTTP_201_CREATED,
                           body=jsonable_encoder(response))
        return response


@router.post("/runs/{run_id}/outputs", status_code=status.HTTP_201_CREATED)
async def create_output(
    run_id: uuid.UUID,
    payload: OutputCreateRequest,
    principal: Principal = Depends(get_principal),
) -> dict:
    """§39 — المخرَج لا يوجد بلا تشغيلة."""
    async with _scope(principal, permission=DATA,
                      not_found="analysis.run_not_found",
                      run=run_id) as scope:
        run = (
            await scope.session.execute(select(AnalysisRun).where(AnalysisRun.id == run_id))
        ).scalar_one_or_none()
        if run is None:
            raise NotFound("analysis.run_not_found")

        row = AnalysisOutputRow(
            tenant_id=scope.tenant_id, run_id=run_id, output_kind=payload.output_kind,
            test_key=payload.test_key, label_ar=payload.label_ar, label_en=payload.label_en,
            payload=payload.payload,
        )
        scope.session.add(row)
        await scope.session.flush()
        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.output_recorded",
            object_type="analysis_output", object_id=row.id, actor_user_id=principal.user_id,
            state_after={"kind": payload.output_kind, "run": str(run_id)},
        )
        return {"id": str(row.id), "run_id": str(run_id)}


async def _interpret_in_scope(
    scope: _Scope, output_id: uuid.UUID, payload: InterpretationRequest,
    principal: Principal,
) -> InterpretationResponse:
    """التفسيرُ داخلَ نطاقٍ مفتوح — **نواةٌ واحدةٌ لشكلَي المسار**."""
    output = (
        await scope.session.execute(
            select(AnalysisOutputRow).where(AnalysisOutputRow.id == output_id))
    ).scalar_one_or_none()
    if output is None:
        raise NotFound("analysis.output_not_found")

    try:
        domain = interpretation.Interpretation(
            output_id=str(output_id), result_ar=payload.result_ar,
            result_en=payload.result_en, statistical_ar=payload.statistical_ar,
            theoretical_ar=payload.theoretical_ar,
            managerial_ar=payload.managerial_ar,
        )
    except interpretation.InterpretationError as exc:
        raise AtheraError("analysis.invalid_interpretation", status_code=422,
                          detail=str(exc)) from exc

    now = dt.datetime.now(dt.UTC)
    existing = (
        await scope.session.execute(
            select(InterpretationRow).where(InterpretationRow.output_id == output_id))
    ).scalar_one_or_none()
    row = existing or InterpretationRow(
        tenant_id=scope.tenant_id, output_id=output_id, result_ar=payload.result_ar
    )
    row.result_ar = payload.result_ar
    row.result_en = payload.result_en
    row.statistical_ar = payload.statistical_ar
    row.theoretical_ar = payload.theoretical_ar
    row.managerial_ar = payload.managerial_ar
    # **ودَينٌ قائمٌ يُسجَّل ولا يُعاد تصميمُه هنا**: الكتابةُ والاعتمادُ
    # فعلٌ واحدٌ تحت `edit_research_content`، ولا بوّابةَ اعتمادٍ مستقلّةٌ
    # للتفسير اليوم. ولا تُصلَح دلالةُ G8 في دفعةِ تعاون.
    row.approved_by = principal.user_id
    row.approved_at = now
    if existing is None:
        scope.session.add(row)
    await scope.session.flush()

    await audit.record(
        scope.session, tenant_id=scope.tenant_id,
        action="analysis.interpretation_approved",
        object_type="interpretation", object_id=row.id,
        actor_user_id=principal.user_id,
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


@router.post("/projects/{project_id}/outputs/{output_id}/interpret",
             response_model=InterpretationResponse)
async def interpret_in_project(
    project_id: uuid.UUID,
    output_id: uuid.UUID,
    payload: InterpretationRequest,
    principal: Principal = Depends(get_principal),
) -> InterpretationResponse:
    """§18.3 / §9 G8 — التفسيرُ في نطاق بحثه: **الصلاحياتُ مستقلّة**.

    فالتفسيرُ تحريرُ محتوًى علميّ (`edit_research_content`)، والمؤلِّفُ
    المشاركُ من مؤسسةٍ أخرى يحمله ولا يحمل إدارةَ البيانات. والشكلُ
    القديمُ يُعرَّف بمعرّف المخرَج وحده فيلزمه تحديدُ موضعٍ مشروطٌ
    بإدارة البيانات — فكان يُطلب منه ما لا شأنَ له بعمله.

    **وسلسلةُ الجذر تُتبع كاملةً**: المخرَجُ إلى تشغيلته، والتشغيلةُ إلى
    خطّتها، والخطّةُ إلى بحثها — ويُطابق ببحث المسار أو يُردّ جوابَ
    المعدوم.
    """
    async with _scope(principal, permission=EDIT,
                      not_found="analysis.output_not_found",
                      project_id=project_id) as scope:
        root = (
            await scope.session.execute(
                select(AnalysisPlanRow.project_id)
                .join(AnalysisRun, AnalysisRun.plan_id == AnalysisPlanRow.id)
                .join(AnalysisOutputRow, AnalysisOutputRow.run_id == AnalysisRun.id)
                .where(AnalysisOutputRow.id == output_id))
        ).scalar_one_or_none()
        if root != project_id:
            raise NotFound("analysis.output_not_found")
        return await _interpret_in_scope(scope, output_id, payload, principal)


@router.post("/outputs/{output_id}/interpret", response_model=InterpretationResponse)
async def interpret(
    output_id: uuid.UUID,
    payload: InterpretationRequest,
    principal: Principal = Depends(get_principal),
) -> InterpretationResponse:
    """§18.3 / §9 G8 — أربع طبقات منفصلة بسلسلة سند. **والشكلُ القديم باقٍ.**

    وحدُّه المعلَن كحدِّ نظيره: عبرَ المؤسسات يلزمه `manage_data` أيضًا،
    لأنّ تحديدَ موضع المخرَج يمرّ بجسر البيانات. والمسارُ المُعشَّشُ في
    بحثه هو الطريقُ القانونيُّ لذلك.
    """
    # **والتفسيرُ تحريرُ محتوًى علميّ** — `edit_research_content`، لا
    # `manage_data`. فالإحصائيُّ يُخرج النتيجة، ومن يفسّرها يحمل صلاحيةَ
    # المحتوى. وهذا الفرقُ محفوظٌ عبرَ المؤسسات كما هو داخلها.
    async with _scope(principal, permission=EDIT,
                      not_found="analysis.output_not_found",
                      output=output_id) as scope:
        return await _interpret_in_scope(scope, output_id, payload, principal)


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


async def _dictionary_view(
    session: AsyncSession, version_id: uuid.UUID, locale: str,
) -> DictionaryCoverageResponse:
    """إسقاطُ القاموس — **يُقرأ في الجلسة المُعطاة، أيًّا كان مستأجرُها**.

    ومشتركٌ بين القراءة والتحديث عمدًا: كان التحديثُ ينادي مسارَ القراءة
    نفسَه، فصار ذلك بعد الجسر يفتح **نطاقًا ثانيًا** — رحلتين زائدتين،
    وقراءةً تتبع كتابةً في معاملةٍ أخرى. وذاك بعينه ما يُحذَّر منه في
    RC-T1-H1.
    """
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
        note=_pick(locale, note_ar, note_en),
    )


@router.get("/datasets/versions/{version_id}/dictionary",
            response_model=DictionaryCoverageResponse)
async def read_dictionary(
    version_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
) -> DictionaryCoverageResponse:
    # **والقاموسُ أخطرُ ما في هذه الطبقة قراءةً**: أسماءُ الأعمدة ووصفُها
    # ومقاييسُها — **ووسمُ ما يحمل بياناتٍ شخصية**. فقراءتُه إدارةُ بيانات
    # لا اطّلاعٌ على بحث، ومن دُعي ليقرأ البحث لم يُدعَ ليقرأ عمودَ الهويّات.
    async with _scope(principal, permission=DATA,
                      not_found="analysis.version_not_found",
                      version=version_id) as scope:
        return await _dictionary_view(
            scope.session, version_id, principal.locale)


@router.put("/datasets/versions/{version_id}/dictionary",
            response_model=DictionaryCoverageResponse)
async def upsert_dictionary(
    version_id: uuid.UUID,
    payload: list[DictionaryEntryInput],
    principal: Principal = Depends(get_principal),
) -> DictionaryCoverageResponse:
    """§17.4 — القاموس يُكتب على نسخة **قبل** تجميدها.

    نسخة مجمَّدة تُرفض هنا: تغيير وصف عمود بعد التجميد يغيّر معنى تحليل جرى
    على الوصف القديم، بلا أن يتغيّر شيء في السجل يشي بذلك.
    """
    async with _scope(principal, permission=DATA,
                      not_found="analysis.version_not_found",
                      version=version_id) as scope:
        version = (
            await scope.session.execute(
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
            await scope.session.execute(
                select(DataDictionary).where(DataDictionary.dataset_version_id == version_id)
            )
        ).scalars().all()
        by_name = {row.column_name: row for row in existing}

        for entry in payload:
            row = by_name.get(entry.column_name)
            if row is None:
                row = DataDictionary(
                    tenant_id=scope.tenant_id, dataset_version_id=version_id,
                    column_name=entry.column_name,
                )
                scope.session.add(row)
            row.label_ar = entry.label_ar
            row.scale_type = entry.scale_type
            row.value_labels = entry.value_labels
            row.is_pii = entry.is_pii
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.dictionary_updated",
            object_type="dataset_version", object_id=version_id, actor_user_id=principal.user_id,
            state_after={"columns": len(payload),
                         "pii": sum(1 for entry in payload if entry.is_pii)},
        )
        # **والقراءةُ في المعاملة نفسِها** — لا نطاقٌ ثانٍ ولا قراءةٌ
        # تتبع كتابةً عبرَ معاملتين (وهو حدُّ RC-T1-H1 المعلَن).
        return await _dictionary_view(
            scope.session, version_id, principal.locale)


# ---------------------------------------------------------------------------
# §18.5 — تصدير إلى الأدوات
# ---------------------------------------------------------------------------


@router.get("/exports", response_model=list[ToolExportResponse])
async def list_exports(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ToolExportResponse]:
    visible = await _managed(session, principal)
    rows = [] if not visible else (
        await session.execute(
            select(ToolExport)
            .join(DatasetVersionRow,
                  DatasetVersionRow.id == ToolExport.dataset_version_id)
            .join(Dataset, Dataset.id == DatasetVersionRow.dataset_id)
            .where(Dataset.project_id.in_(visible))
            .order_by(ToolExport.created_at.desc()))
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
) -> ToolExportResponse:
    """§18.5 — كل تصدير يُسجَّل ومعه ما لا تدعمه الصيغة.

    الحدود تُنسخ من قدرات الأداة وقت التصدير، لا تُقرأ لاحقًا: لو تغيّرت
    القدرات غدًا، يبقى التصدير القديم يحمل ما قيل لصاحبه يومها.
    """
    # **والتشغيلةُ المُرفَقة تُفوَّض هي أيضًا، وتُشترط من البحث نفسِه.**
    #
    # وكان `run_id` يُقبل من العميل **بلا تفويضٍ أصلًا** ويُخزَّن كما
    # وصل: فيُنسب تصديرٌ إلى تشغيلةِ بحثٍ آخر — وبعد جسر المؤسسات إلى
    # تشغيلةِ مؤسسةٍ أخرى. فإن جاءت، فجذرُها جذرُ النسخة أو لا تصدير.
    scope_for = (
        _scope_pair(principal, permission=DATA,
                    not_found="analysis.version_not_found",
                    first={"version": payload.dataset_version_id},
                    second={"run": payload.run_id})
        if payload.run_id is not None else
        _scope(principal, permission=DATA,
               not_found="analysis.version_not_found",
               version=payload.dataset_version_id))
    async with scope_for as scope:
        version = (
            await scope.session.execute(
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
            tenant_id=scope.tenant_id, run_id=payload.run_id,
            dataset_version_id=payload.dataset_version_id, tool=payload.tool,
            export_format=payload.export_format,
            limitations_ar=cap.not_supported_ar, limitations_en=cap.not_supported_en,
        )
        scope.session.add(row)
        await scope.session.flush()

        await audit.record(
            scope.session, tenant_id=scope.tenant_id, action="analysis.exported",
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
