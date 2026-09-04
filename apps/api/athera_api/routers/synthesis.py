"""طبقة التركيب | Synthesis routes: themes, contradictions, gaps, opportunities.

**كل ما يخرج من هنا مرشَّح.** ولا نقطة في هذا الموجّه تُرجع «فجوة مؤكَّدة»
ولا «موضوعًا ثابتًا»: الأسماء `candidate` في القاعدة، والحال `generated`
حتى يقول إنسانٌ شيئًا.

**والقراءة مقيَّدةٌ بالبحث في كل استعلام.** `_project` تُثبت أن البحث لهذا
المستأجر، ثم كل دالّةٍ في `store` تشترط `project_id` أيضًا. وRLS تحمي بين
المستأجرين ولا تحمي بين بحثين في مستأجرٍ واحد.

**ولا شيء يقع بلا تأكيدٍ صريح.** التوليد يكتب مرشَّحات، والقرار يكتب حكمًا
منسوبًا، والفرصة تلزمها فجوةٌ معتمَدة **و**`confirmed`، وإنشاء البحث يلزمه
معاينةٌ ثم `confirmed` ثانٍ. ولا مسار هنا يكتب `use_state` لمرجع.

## هذا الموجّه **غير مركَّب في التطبيق بعد**

تركيبُ الموجّهات في هذا المستودع صريحٌ في `main.py`: سطرُ استيرادٍ وسطرُ
`include_router`، ولا اكتشاف تلقائيّ. وتعديلُ `main.py` خارج نطاق هذا
العمل، فلم يُعدَّل. فالنقاط أدناه مكتوبةٌ ومُختبَرة ولا يبلغها طلبُ HTTP حتى
يُضاف السطران:

    from .routers import synthesis as synthesis_router
    app.include_router(synthesis_router.router)

وهذا نقصٌ يُقال صراحةً لا يُترك ليُكتشف: من قرأ الملف ورأى النقاط قد يظنّ
الميزة قائمة، وهي لا تُستدعى من المتصفّح بعد.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import Principal, get_principal, get_session
from ..errors import AtheraError, NotFound
from ..models.literature import Source
from ..models.portfolio import ResearchProject
from ..models.screening import LiteratureMatrixCell
from ..models.synthesis import GAP_STRENGTHS, THEME_BASES, ResearchOpportunity
from ..schemas.synthesis import (
    ContradictionSideView,
    ContradictionsView,
    ContradictionView,
    DecisionRequest,
    EvidenceLink,
    GapsView,
    GapView,
    NotAssessedView,
    OpportunitiesView,
    OpportunityCreateRequest,
    OpportunityPreviewView,
    OpportunityView,
    ProjectFromOpportunityRequest,
    ProjectPreviewView,
    RelatedStudyView,
    SearchScopeView,
    ThemesView,
    ThemeTraceView,
    ThemeView,
    VocabularyEntry,
)
from ..services import audit, workspace
from ..services.synthesis import (
    assess_gaps,
    build_project_preview,
    gap_may_become_opportunity,
    load_corpus,
    propose_contradictions,
    propose_themes,
    store,
)
from ..services.synthesis.gaps import GapProposal
from ..services.synthesis.opportunities import RelatedStudy, build_preview
from ..services.synthesis.vocab import (
    BASIS_LABELS,
    BASIS_MEANING,
    CONFLICT_LABELS,
    CONTEXT_DIMENSION_LABELS,
    DIRECTION_LABELS,
    GAP_TYPE_LABELS,
    SIGNIFICANCE_LABELS,
    STATUS_LABELS,
    STRENGTH_LABELS,
    STRENGTH_MEANING,
)

router = APIRouter(prefix="/api/v1/synthesis", tags=["synthesis"])


async def _project(session: AsyncSession, principal: Principal,
                   project_id: uuid.UUID) -> ResearchProject:
    row = await workspace.live_project(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    if row is None:
        raise NotFound("synthesis.project_not_found")
    return row


async def _titles(session: AsyncSession, principal: Principal,
                  source_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """عناوينُ المراجع — **عبارةٌ واحدة للقائمة كلّها**، لا واحدةٌ لكل سطر."""
    if not source_ids:
        return {}
    rows = (await session.execute(
        select(Source.id, Source.title).where(
            Source.tenant_id == principal.tenant_id, Source.id.in_(source_ids))
    )).all()
    return dict(rows)


async def _cells(session: AsyncSession, principal: Principal, project_id: uuid.UUID,
                 cell_ids: list[uuid.UUID]) -> dict[uuid.UUID, LiteratureMatrixCell]:
    """الخلايا التي تسند هذه الصفوف — وهي آخر حلقةٍ قبل الشاهد نفسه."""
    wanted = [c for c in cell_ids if c is not None]
    if not wanted:
        return {}
    rows = (await session.execute(
        select(LiteratureMatrixCell).where(
            LiteratureMatrixCell.tenant_id == principal.tenant_id,
            LiteratureMatrixCell.project_id == project_id,
            LiteratureMatrixCell.id.in_(wanted))
    )).scalars().all()
    return {row.id: row for row in rows}


def _link(row, titles, cells) -> EvidenceLink:
    cell = cells.get(row.matrix_cell_id) if row.matrix_cell_id else None
    return EvidenceLink(
        source_id=row.source_id,
        title=titles.get(row.source_id, "—"),
        role=row.role,
        basis_field_key=getattr(row, "basis_field_key", None) or (
            cell.field_key if cell else None),
        matrix_cell_id=row.matrix_cell_id,
        evidence_scope=row.evidence_scope,
        evidence_quote=cell.evidence_quote if cell else None,
        evidence_locator=cell.evidence_locator if cell else None,
        cell_state=cell.cell_state if cell else None,
        cell_value_ar=cell.value_ar if cell else None,
    )


def _scope_view(payload: dict) -> SearchScopeView:
    return SearchScopeView(**{k: v for k, v in payload.items()
                             if k in SearchScopeView.model_fields})


# ═════════════════════ الموضوعات ═════════════════════

def _theme_view(row, *, supporting: int, contradicting: int,
                traceable: bool) -> ThemeView:
    return ThemeView(
        id=row.id, label_ar=row.label_ar, description_ar=row.description_ar,
        basis=row.basis, basis_label_ar=BASIS_LABELS[row.basis]["ar"],
        basis_meaning_ar=BASIS_MEANING[row.basis]["ar"],
        status=row.status, status_label_ar=STATUS_LABELS[row.status]["ar"],
        source_scope_summary=dict(row.source_scope_summary or {}),
        supporting_count=supporting, contradicting_count=contradicting,
        is_traceable=traceable,
        generated_at=row.generated_at, decided_at=row.decided_at)


@router.get("/projects/{project_id}/themes", response_model=ThemesView)
async def list_themes(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThemesView:
    """الموضوعات — **والتجميعُ الموضوعي معها مفصولًا باسمه**.

    ولا يُخفى التجميع ولا يُرقَّى: إخفاؤه يحرم الباحث ترتيبًا نافعًا،
    وترقيتُه يجعله نتيجةً ليست له.
    """
    await _project(session, principal, project_id)
    rows = await store.list_themes(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    supports = await store.theme_supports(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        theme_ids=[row.id for row in rows])

    tally: dict[uuid.UUID, dict[str, int]] = {}
    traceable: dict[uuid.UUID, bool] = {}
    for support in supports:
        bucket = tally.setdefault(support.theme_id, {"supporting": 0,
                                                     "contradicting": 0})
        bucket[support.role] += 1
        ok = (support.evidence_scope == "metadata_only"
              or support.matrix_cell_id is not None)
        traceable[support.theme_id] = traceable.get(support.theme_id, True) and ok

    views = [
        _theme_view(row,
                    supporting=tally.get(row.id, {}).get("supporting", 0),
                    contradicting=tally.get(row.id, {}).get("contradicting", 0),
                    traceable=traceable.get(row.id, False))
        for row in rows
    ]
    corpus_size = len({s.source_id for s in supports})
    note = ""
    if views and all(v.basis == "topic_cluster" for v in views):
        note = (
            "كلُّ ما ظهر تجميعاتٌ موضوعية من العناوين — **ولا نتيجة فيها**. "
            "لتظهر موضوعاتٌ علمية املأ أعمدة المحتوى في مصفوفة الأدبيات "
            "(المشكلة، الهدف، البناءات، النتائج) لدراستين على الأقل.")
    elif not views:
        note = ("لم يُقترح شيء بعد. اضغط «حلّل الموضوعات» بعد إدراج دراستين "
                "على الأقل في الفرز.")

    return ThemesView(
        project_id=project_id, themes=views, corpus_size=corpus_size, note_ar=note,
        basis_vocabulary=[
            VocabularyEntry(key=key, label_ar=BASIS_LABELS[key]["ar"],
                            label_en=BASIS_LABELS[key]["en"],
                            meaning_ar=BASIS_MEANING[key]["ar"])
            for key in THEME_BASES],
    )


@router.get("/projects/{project_id}/themes/{theme_id}/trace",
            response_model=ThemeTraceView)
async def theme_trace(
    project_id: uuid.UUID,
    theme_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThemeTraceView:
    """المسار من الموضوع إلى الشاهد — **لا موضوع بلا أثرٍ يُتتبَّع**.

    ولولا هذه النقطة لكان الموضوع دعوى: الباحث يقرأ اسمًا ولا يعرف من أين
    جاء، فيصدّقه أو يهمله — وكلاهما خسارة.
    """
    await _project(session, principal, project_id)
    row = await store.theme_of(session, tenant_id=principal.tenant_id,
                               project_id=project_id, theme_id=theme_id)
    if row is None:
        raise NotFound("synthesis.theme_not_found")
    supports = await store.theme_supports(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        theme_ids=[row.id])
    titles = await _titles(session, principal, [s.source_id for s in supports])
    cells = await _cells(session, principal, project_id,
                         [s.matrix_cell_id for s in supports])
    links = [_link(s, titles, cells) for s in supports]
    traceable = all(s.evidence_scope == "metadata_only" or s.matrix_cell_id
                    for s in supports)
    return ThemeTraceView(
        theme=_theme_view(
            row,
            supporting=sum(1 for s in supports if s.role == "supporting"),
            contradicting=sum(1 for s in supports if s.role == "contradicting"),
            traceable=traceable),
        supporting=[link for link in links if link.role == "supporting"],
        contradicting=[link for link in links if link.role == "contradicting"],
    )


# ═════════════════════ التوليد ═════════════════════

@router.post("/projects/{project_id}/analyze", response_model=ThemesView,
             status_code=status.HTTP_201_CREATED)
async def analyze(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThemesView:
    """يعيد التحليل — **ولا يمحو حكمًا قاله الباحث**.

    ما لم يُحكم فيه يُستبدل، وما حُكم فيه يبقى بحاله وصاحبه. ومسحُ الجميع
    يجعل زرًّا واحدًا يُلغي مراجعة أسبوع بلا سؤال.

    والتوليد حتميّ بلا نموذج: التشغيلة نفسها على المصفوفة نفسها تُنتج
    القائمة نفسها بالترتيب نفسه.
    """
    await _project(session, principal, project_id)
    moment = dt.datetime.now(dt.UTC)
    corpus = await load_corpus(session, tenant_id=principal.tenant_id,
                               project_id=project_id, taken_at=moment)

    contradictions = propose_contradictions(corpus)
    keys = await store.replace_generated_contradictions(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        proposals=contradictions, generated_at=moment)
    assessment = assess_gaps(corpus, contradictions=contradictions)
    await store.replace_generated_gaps(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        proposals=assessment.proposals, contradiction_ids=keys,
        generated_at=moment)
    themes = propose_themes(corpus)
    await store.replace_generated_themes(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        proposals=themes, generated_at=moment)

    # **ولا محتوى مستندٍ في السجلّ** (§37): الأعداد تُسجَّل، ولا نصّ خليةٍ
    # ولا اقتباس يُنسخ إلى سجلّ التدقيق.
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="synthesis.analysed", object_type="research_project",
        object_id=project_id, actor_user_id=principal.user_id,
        state_after={"corpus_size": corpus.size, "themes": len(themes),
                     "contradictions": len(contradictions),
                     "gap_candidates": len(assessment.proposals),
                     "not_assessed": len(assessment.not_assessed)},
        reason="deterministic synthesis over the included corpus; candidates only",
        request_id=principal.request_id, ip_address=principal.ip_address)
    await session.commit()
    return await list_themes(project_id, principal, session)


# ═════════════════════ القرارات ═════════════════════

async def _decide(session: AsyncSession, principal: Principal, row, *,
                  payload: DecisionRequest, object_type: str) -> None:
    before = store.apply_decision(row, status=payload.status,
                                  actor_id=principal.user_id)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action=f"{object_type}.decided", object_type=object_type, object_id=row.id,
        actor_user_id=principal.user_id, state_before=before,
        state_after={"status": row.status},
        reason=payload.note_ar or "a synthesis candidate is decided by a person",
        request_id=principal.request_id, ip_address=principal.ip_address)
    await session.commit()


@router.post("/projects/{project_id}/themes/{theme_id}/decision",
             response_model=ThemeView)
async def decide_theme(
    project_id: uuid.UUID,
    theme_id: uuid.UUID,
    payload: DecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ThemeView:
    """حكمُ الباحث على موضوع — **ويُنسب إليه رفضًا كما اعتمادًا**."""
    await _project(session, principal, project_id)
    row = await store.theme_of(session, tenant_id=principal.tenant_id,
                               project_id=project_id, theme_id=theme_id)
    if row is None:
        raise NotFound("synthesis.theme_not_found")
    await _decide(session, principal, row, payload=payload,
                  object_type="theme_candidate")
    # **ولا تُعاد أعدادٌ صفرية بدل الحقيقية.** رقمٌ مخترَع في جوابٍ يُعرض
    # للباحث أسوأ من غيابه: يقرأ «صفر مراجع مُسنِدة» عن موضوعٍ اعتمده لتوّه.
    supports = await store.theme_supports(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        theme_ids=[row.id])
    return _theme_view(
        row,
        supporting=sum(1 for s in supports if s.role == "supporting"),
        contradicting=sum(1 for s in supports if s.role == "contradicting"),
        traceable=all(s.evidence_scope == "metadata_only" or s.matrix_cell_id
                      for s in supports))


# ═════════════════════ التعارضات ═════════════════════

@router.get("/projects/{project_id}/contradictions", response_model=ContradictionsView)
async def list_contradictions(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ContradictionsView:
    """التعارضات المحتملة — **بطرفيهما وسياقهما**، ولا حكم على دراسة."""
    await _project(session, principal, project_id)
    rows = await store.list_contradictions(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    sides = await store.contradiction_sides(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        contradiction_ids=[row.id for row in rows])
    titles = await _titles(session, principal, [s.source_id for s in sides])

    by_parent: dict[uuid.UUID, list] = {}
    for side in sides:
        by_parent.setdefault(side.contradiction_id, []).append(side)

    views = []
    for row in rows:
        divergence = list(row.context_divergence or [])
        views.append(ContradictionView(
            id=row.id, construct_a_ar=row.construct_a_ar,
            construct_b_ar=row.construct_b_ar,
            relationship_ar=row.relationship_ar,
            conflict_kind=row.conflict_kind,
            conflict_label_ar=CONFLICT_LABELS[row.conflict_kind]["ar"],
            context_divergence=divergence,
            context_divergence_labels_ar=[
                CONTEXT_DIMENSION_LABELS[name]["ar"] for name in divergence
                if name in CONTEXT_DIMENSION_LABELS],
            context_explanation_ar=row.context_explanation_ar,
            status=row.status, status_label_ar=STATUS_LABELS[row.status]["ar"],
            sides=[ContradictionSideView(
                side=side.side, source_id=side.source_id,
                title=titles.get(side.source_id, "—"), result_ar=side.result_ar,
                direction=side.direction,
                direction_label_ar=DIRECTION_LABELS[side.direction]["ar"],
                significance=side.significance,
                significance_label_ar=SIGNIFICANCE_LABELS[side.significance]["ar"],
                population_ar=side.population_ar, country_ar=side.country_ar,
                method_ar=side.method_ar, measurement_ar=side.measurement_ar,
                period_year=side.period_year, evidence_scope=side.evidence_scope,
                matrix_cell_id=side.matrix_cell_id)
                for side in by_parent.get(row.id, [])],
            generated_at=row.generated_at, decided_at=row.decided_at))

    return ContradictionsView(project_id=project_id, contradictions=views,
                              corpus_size=len({s.source_id for s in sides}))


@router.post("/projects/{project_id}/contradictions/{contradiction_id}/decision",
             response_model=DecisionRequest)
async def decide_contradiction(
    project_id: uuid.UUID,
    contradiction_id: uuid.UUID,
    payload: DecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> DecisionRequest:
    await _project(session, principal, project_id)
    rows = await store.list_contradictions(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    row = next((r for r in rows if r.id == contradiction_id), None)
    if row is None:
        raise NotFound("synthesis.contradiction_not_found")
    await _decide(session, principal, row, payload=payload,
                  object_type="contradiction_candidate")
    return payload


# ═════════════════════ الفجوات ═════════════════════

async def _gap_views(session: AsyncSession, principal: Principal,
                     project_id: uuid.UUID, rows) -> list[GapView]:
    refs = await store.gap_sources(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        gap_ids=[row.id for row in rows])
    titles = await _titles(session, principal, [r.source_id for r in refs])
    cells = await _cells(session, principal, project_id,
                         [r.matrix_cell_id for r in refs])
    by_gap: dict[uuid.UUID, list] = {}
    for ref in refs:
        by_gap.setdefault(ref.gap_id, []).append(ref)

    views = []
    for row in rows:
        links = [_link(ref, titles, cells) for ref in by_gap.get(row.id, [])]
        views.append(GapView(
            id=row.id, gap_type=row.gap_type,
            gap_type_label_ar=GAP_TYPE_LABELS[row.gap_type]["ar"],
            description_ar=row.description_ar,
            why_suggested_ar=row.why_suggested_ar,
            known_limitations_ar=row.known_limitations_ar,
            strength=row.strength,
            strength_label_ar=STRENGTH_LABELS[row.strength]["ar"],
            strength_meaning_ar=STRENGTH_MEANING[row.strength]["ar"],
            sources_considered=row.sources_considered,
            search_scope=_scope_view(row.search_scope or {}),
            source_scope_distribution=dict(row.source_scope_distribution or {}),
            supporting=[link for link in links if link.role == "supporting"],
            contradicting=[link for link in links if link.role == "contradicting"],
            considered=[link for link in links if link.role == "considered"],
            contradiction_id=row.contradiction_id,
            status=row.status, status_label_ar=STATUS_LABELS[row.status]["ar"],
            generated_at=row.generated_at, decided_at=row.decided_at,
            may_become_opportunity=gap_may_become_opportunity(row.status)))
    return views


@router.get("/projects/{project_id}/gaps", response_model=GapsView)
async def list_gaps(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GapsView:
    """الفجوات المحتملة — **وما تعذّر الحكم فيه معها في الصفحة نفسها**.

    وقائمةٌ تذكر ما وجدته وتصمت عمّا عجزت عنه يقرأها الباحث «لا شيء آخر»،
    وهو جوابٌ لم يُفحص. فالعجز يُعرض بقدر ما يُعرض ما وُجد — كما في
    `EvaluationReport.unevaluated`.
    """
    await _project(session, principal, project_id)
    rows = await store.list_gaps(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    views = await _gap_views(session, principal, project_id, rows)

    # ما تعذّر الحكم فيه يُحسب من اللقطة الحيّة: هو حالُ المجموعة الآن، لا
    # صفٌّ مخزَّن يتقادم بصمت.
    corpus = await load_corpus(session, tenant_id=principal.tenant_id,
                               project_id=project_id,
                               taken_at=dt.datetime.now(dt.UTC))
    assessment = assess_gaps(corpus, contradictions=propose_contradictions(corpus))
    return GapsView(
        project_id=project_id, gaps=views,
        not_assessed=[NotAssessedView(
            gap_type=item.gap_type,
            gap_type_label_ar=GAP_TYPE_LABELS[item.gap_type]["ar"],
            verdict=item.verdict, reason_ar=item.reason_ar)
            for item in assessment.not_assessed],
        corpus_size=corpus.size,
        search_scope=_scope_view(corpus.search_scope()),
        strength_vocabulary=[
            VocabularyEntry(key=key, label_ar=STRENGTH_LABELS[key]["ar"],
                            label_en=STRENGTH_LABELS[key]["en"],
                            meaning_ar=STRENGTH_MEANING[key]["ar"])
            for key in GAP_STRENGTHS],
    )


@router.post("/projects/{project_id}/gaps/{gap_id}/decision", response_model=GapView)
async def decide_gap(
    project_id: uuid.UUID,
    gap_id: uuid.UUID,
    payload: DecisionRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> GapView:
    """حكمُ الباحث على فجوةٍ محتملة.

    و«اعتمد» هنا تعني **«قرّرتُ متابعتها»** لا «ثبتت»؛ وهو ما تقوله الشاشة
    نصًّا قبل الزرّ. وسحبُ الاعتماد بعد إنشاء فرصةٍ فوقه ترفضه القاعدة.
    """
    await _project(session, principal, project_id)
    row = await store.gap_of(session, tenant_id=principal.tenant_id,
                             project_id=project_id, gap_id=gap_id)
    if row is None:
        raise NotFound("synthesis.gap_not_found")
    if row.status == "approved" and payload.status != "approved":
        spawned = (await session.execute(
            select(ResearchOpportunity.id).where(
                ResearchOpportunity.tenant_id == principal.tenant_id,
                ResearchOpportunity.project_id == project_id,
                ResearchOpportunity.gap_candidate_id == row.id).limit(1)
        )).first()
        if spawned is not None:
            raise AtheraError("synthesis.gap_carries_an_opportunity",
                              status_code=status.HTTP_409_CONFLICT)
    await _decide(session, principal, row, payload=payload,
                  object_type="gap_candidate")
    views = await _gap_views(session, principal, project_id, [row])
    return views[0]


# ═════════════════════ الفرص البحثية ═════════════════════

@router.get("/projects/{project_id}/gaps/{gap_id}/opportunity-preview",
            response_model=OpportunityPreviewView)
async def opportunity_preview(
    project_id: uuid.UUID,
    gap_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityPreviewView:
    """معاينةُ البطاقة — **ولا تكتب شيئًا**.

    ومعاينةٌ تكتب صفًّا تجعل كل استطلاعٍ لفكرةٍ أثرًا دائمًا في البحث.
    """
    await _project(session, principal, project_id)
    row = await store.gap_of(session, tenant_id=principal.tenant_id,
                             project_id=project_id, gap_id=gap_id)
    if row is None:
        raise NotFound("synthesis.gap_not_found")
    if not gap_may_become_opportunity(row.status):
        raise AtheraError("synthesis.gap_not_approved",
                          status_code=status.HTTP_409_CONFLICT,
                          current_status=row.status)
    refs = await store.gap_sources(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        gap_ids=[row.id])
    titles = await _titles(session, principal, [r.source_id for r in refs])
    related = tuple(RelatedStudy(
        source_id=str(ref.source_id), title=titles.get(ref.source_id, "—"),
        role=ref.role, evidence_scope=ref.evidence_scope) for ref in refs)
    preview = build_preview(
        gap_id=str(row.id),
        gap=GapProposal(
            gap_type=row.gap_type, description_ar=row.description_ar,
            why_suggested_ar=row.why_suggested_ar,
            known_limitations_ar=row.known_limitations_ar, strength=row.strength,
            sources_considered=row.sources_considered,
            search_scope=dict(row.search_scope or {}),
            source_scope_distribution=dict(row.source_scope_distribution or {})),
        related=related)
    return OpportunityPreviewView(
        gap_candidate_id=row.id, gap_type=preview.gap_type,
        gap_type_label_ar=preview.gap_type_label_ar,
        what_we_noticed_ar=preview.what_we_noticed_ar,
        why_it_might_matter_ar=preview.why_it_might_matter_ar,
        evidence_basis_ar=preview.evidence_basis_ar,
        related_studies=[RelatedStudyView(
            source_id=uuid.UUID(item.source_id), title=item.title, role=item.role,
            evidence_scope=item.evidence_scope) for item in preview.related_studies],
        still_uncertain_ar=preview.still_uncertain_ar,
        strength_label_ar=preview.strength_label_ar,
        strength_meaning_ar=preview.strength_meaning_ar,
        next_step_ar=preview.next_step_ar,
        editable_fields=list(preview.editable_fields))


def _opportunity_view(row, gap_type: str) -> OpportunityView:
    return OpportunityView(
        id=row.id, gap_candidate_id=row.gap_candidate_id, gap_type=gap_type,
        gap_type_label_ar=GAP_TYPE_LABELS[gap_type]["ar"],
        phenomenon_ar=row.phenomenon_ar, context_ar=row.context_ar,
        population_ar=row.population_ar, constructs_ar=row.constructs_ar,
        possible_contribution_ar=row.possible_contribution_ar,
        methodological_opportunity_ar=row.methodological_opportunity_ar,
        evidence_basis_ar=row.evidence_basis_ar,
        uncertainties_ar=row.uncertainties_ar, created_at=row.created_at,
        spawned_project_id=row.spawned_project_id)


@router.get("/projects/{project_id}/opportunities", response_model=OpportunitiesView)
async def list_opportunities(
    project_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunitiesView:
    await _project(session, principal, project_id)
    rows = await store.list_opportunities(
        session, tenant_id=principal.tenant_id, project_id=project_id)
    gaps = {row.id: row for row in await store.list_gaps(
        session, tenant_id=principal.tenant_id, project_id=project_id)}
    return OpportunitiesView(
        project_id=project_id,
        opportunities=[
            _opportunity_view(row, gaps[row.gap_candidate_id].gap_type)
            for row in rows if row.gap_candidate_id in gaps])


@router.post("/projects/{project_id}/opportunities", response_model=OpportunityView,
             status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    project_id: uuid.UUID,
    payload: OpportunityCreateRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityView:
    """بطاقةُ فرصة — **من فجوةٍ اعتمدها إنسان، وبتأكيدٍ صريح منه**.

    وثلاثة حرّاس على الشيء نفسه عمدًا: العقد يطلب `confirmed`، والخدمة تفحص
    حال الفجوة، والقاعدة ترفض المفتاح المركّب. فمن التفّ على واحدٍ اصطدم
    بالآخر — ولا يقع إنشاءٌ تلقائيّ بحال.
    """
    await _project(session, principal, project_id)
    if not payload.confirmed:
        raise AtheraError("synthesis.confirmation_required",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    gap = await store.gap_of(session, tenant_id=principal.tenant_id,
                             project_id=project_id,
                             gap_id=payload.gap_candidate_id)
    if gap is None:
        raise NotFound("synthesis.gap_not_found")
    if not gap_may_become_opportunity(gap.status):
        raise AtheraError("synthesis.gap_not_approved",
                          status_code=status.HTTP_409_CONFLICT,
                          current_status=gap.status)

    row = ResearchOpportunity(
        tenant_id=principal.tenant_id, project_id=project_id,
        gap_candidate_id=gap.id, gap_status=gap.status,
        phenomenon_ar=payload.phenomenon_ar, context_ar=payload.context_ar,
        population_ar=payload.population_ar, constructs_ar=payload.constructs_ar,
        possible_contribution_ar=payload.possible_contribution_ar,
        methodological_opportunity_ar=payload.methodological_opportunity_ar,
        evidence_basis_ar=payload.evidence_basis_ar,
        uncertainties_ar=payload.uncertainties_ar,
        created_by=principal.user_id)
    session.add(row)
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="research_opportunity.created", object_type="research_opportunity",
        object_id=row.id, actor_user_id=principal.user_id,
        state_after={"gap_candidate_id": str(gap.id), "gap_type": gap.gap_type},
        reason="a person confirmed an approved gap candidate into an opportunity card",
        request_id=principal.request_id, ip_address=principal.ip_address)
    await session.commit()
    return _opportunity_view(row, gap.gap_type)


@router.get("/projects/{project_id}/opportunities/{opportunity_id}/project-preview",
            response_model=ProjectPreviewView)
async def project_preview(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> ProjectPreviewView:
    """ما سيقع بالضبط عند «إنشاء مشروع بحثي» — **قبل أن يقع**."""
    await _project(session, principal, project_id)
    row = await store.opportunity_of(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        opportunity_id=opportunity_id)
    if row is None:
        raise NotFound("synthesis.opportunity_not_found")
    gap = await store.gap_of(session, tenant_id=principal.tenant_id,
                             project_id=project_id, gap_id=row.gap_candidate_id)
    if gap is None:  # pragma: no cover - المفتاح الأجنبي يمنعها
        raise NotFound("synthesis.gap_not_found")
    preview = build_project_preview(
        opportunity_id=str(row.id), title_ar=row.phenomenon_ar,
        gap_type=gap.gap_type)
    return ProjectPreviewView(
        working_title_ar=preview.working_title_ar,
        from_opportunity_id=row.id,
        gap_type_label_ar=preview.gap_type_label_ar,
        will_create_ar=list(preview.will_create_ar),
        will_not_create_ar=list(preview.will_not_create_ar),
        unchanged_ar=list(preview.unchanged_ar))


@router.post("/projects/{project_id}/opportunities/{opportunity_id}/project",
             response_model=OpportunityView, status_code=status.HTTP_201_CREATED)
async def create_project_from_opportunity(
    project_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    payload: ProjectFromOpportunityRequest,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> OpportunityView:
    """ينشئ بحثًا من فرصة — **بعد معاينةٍ وبتأكيدٍ صريح**.

    **ولا يُنقل مرجعٌ ولا يُقلَب إلى «مُدرَج».** بحثٌ جديد يرث أدلّة بحثٍ
    آخر بلا قرار باحثٍ يجعل الإدراج — وهو أخطر قرارٍ في الفرز — يقع بأثرٍ
    جانبي لضغطة زرّ.
    """
    await _project(session, principal, project_id)
    if not payload.confirmed:
        raise AtheraError("synthesis.confirmation_required",
                          status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    row = await store.opportunity_of(
        session, tenant_id=principal.tenant_id, project_id=project_id,
        opportunity_id=opportunity_id)
    if row is None:
        raise NotFound("synthesis.opportunity_not_found")
    if row.spawned_project_id is not None:
        raise AtheraError("synthesis.project_already_created",
                          status_code=status.HTTP_409_CONFLICT)
    gap = await store.gap_of(session, tenant_id=principal.tenant_id,
                             project_id=project_id, gap_id=row.gap_candidate_id)

    created = ResearchProject(
        tenant_id=principal.tenant_id,
        working_title_ar=payload.working_title_ar,
        status="planned")
    session.add(created)
    await session.flush()
    row.spawned_project_id = created.id
    await session.flush()
    await audit.record(
        session, tenant_id=principal.tenant_id,
        action="research_project.created_from_opportunity",
        object_type="research_project", object_id=created.id,
        actor_user_id=principal.user_id,
        state_after={"from_opportunity": str(row.id),
                     "gap_type": gap.gap_type if gap else None,
                     "sources_copied": 0},
        reason="a person previewed and confirmed; no source was linked or included",
        request_id=principal.request_id, ip_address=principal.ip_address)
    await session.commit()
    return _opportunity_view(row, gap.gap_type if gap else "context_gap")
