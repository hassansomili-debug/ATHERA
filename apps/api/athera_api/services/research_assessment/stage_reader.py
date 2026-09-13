"""وقائعُ المراحل من الوحدات صاحبةِ الحقيقة | Reading stage facts (RC-0).

**لا تملك الرحلةُ شيئًا من هذا.** كلُّ رقمٍ هنا يُقرأ من الجدول الذي يملكه:
المصادرُ من `project_sources`، والدراساتُ من `literature_matrix_cells`،
والتحليلُ من `analysis_*`، والورقةُ من `manuscript_*`. والرحلةُ تقرأ
وتفسّر ولا تخزّن (§9).

## والعدُّ هو الزمن

الـAPI في سنغافورة والقاعدة في مومباي، فكلُّ عبارةٍ تدفع ذهابًا وإيابًا عبر
البحر — نحو ستين مللي ثانية قبل أن تبدأ القاعدةُ عملها أصلًا. ولو سُئل كلُّ
عدٍّ في عبارةٍ لبلغت الرحلةُ الواحدة عشرين زيارة.

فيُجمع العدُّ كلُّه في **عبارةٍ واحدة** باستعلاماتٍ فرعية قياسية، كما تفعل
`workspace.file_processing_state_columns` بالضبط. والمنهجُ وحدَه في عبارةٍ
ثانية لأنّه صفٌّ يُقرأ لا عددٌ يُحصى.

## وكلُّ استعلامٍ مقيَّدٌ بالبحث وبالمستأجر

والعطبُ مسجَّلٌ في `services/workspace.py`: أوّلُ صياغةٍ لـ«دماغ البحث»
قرأت ذاكرةَ المستأجر كلَّها، فعرض بحثٌ معرفةً استُخرجت من بحثٍ غيره —
والباحثُ لا يرى الفرق. فما دون قيدِ `project_id` هنا عطبٌ لا تفصيل.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.analysis import (
    AnalysisOutputRow,
    AnalysisPlanRow,
    AnalysisRun,
    Dataset,
    InterpretationRow,
)
from ...models.golden_thread import (
    Construct,
    Instrument,
    InstrumentItem,
    Method,
    Theory,
    ThreadElement,
    Variable,
)
from ...models.portfolio import ProjectSource
from ...models.publishing import Manuscript, ManuscriptSection, ManuscriptVersion
from ...models.screening import LiteratureMatrixCell
from ...models.synthesis import ContradictionCandidate, GapCandidate, ThemeCandidate
from ...research_brain.stages import StageFacts

#: حالُ الخليّة التي تعني «قُرئت فعلًا» — من `models/screening.CELL_STATES`.
CELL_KNOWN = "known"
#: و«مُدرَج» قرارٌ له صاحبٌ ووقت — من `models/portfolio.ProjectSource`.
SOURCE_INCLUDED = "included"
#: ومدى القراءة الأقوى — من `models/screening.SOURCE_SCOPES`.
FULL_TEXT = "full_text"


def _count(stmt: Select) -> Select:
    """استعلامٌ فرعيّ قياسيّ يُركَّب في العبارة الواحدة."""
    return stmt.scalar_subquery()


async def read(session: AsyncSession, *, tenant_id: uuid.UUID,
               project_id: uuid.UUID) -> StageFacts:
    """يقرأ وقائعَ المراحل التسع — بعبارتين لا بعشرين."""
    t, p = tenant_id, project_id

    def thread(kind: str):
        return _count(
            select(func.count(ThreadElement.id)).where(
                ThreadElement.tenant_id == t, ThreadElement.project_id == p,
                ThreadElement.element_type == kind))

    def simple(model):
        return _count(
            select(func.count(model.id)).where(
                model.tenant_id == t, model.project_id == p))

    #: تشغيلاتُ التحليل تخصّ هذا البحث عبر خطّته — لا عمودَ مباشر لها.
    runs_of_project = (
        select(AnalysisRun.id)
        .join(AnalysisPlanRow, AnalysisPlanRow.id == AnalysisRun.plan_id)
        .where(AnalysisRun.tenant_id == t, AnalysisPlanRow.tenant_id == t,
               AnalysisPlanRow.project_id == p)
    )
    outputs_of_project = (
        select(AnalysisOutputRow.id)
        .where(AnalysisOutputRow.tenant_id == t,
               AnalysisOutputRow.run_id.in_(runs_of_project))
    )
    #: أقسامُ المخطوطة تخصّ البحث عبر نسختها ومخطوطتها.
    sections_of_project = (
        select(ManuscriptSection.id, ManuscriptSection.text_ar,
               ManuscriptSection.text_en, ManuscriptSection.review_status)
        .join(ManuscriptVersion, ManuscriptVersion.id == ManuscriptSection.version_id)
        .join(Manuscript, Manuscript.id == ManuscriptVersion.manuscript_id)
        .where(ManuscriptSection.tenant_id == t, Manuscript.project_id == p)
        .subquery()
    )

    row = (await session.execute(select(
        thread("question").label("questions"),
        thread("objective").label("objectives"),
        simple(ProjectSource).label("sources_linked"),
        _count(select(func.count(ProjectSource.id)).where(
            ProjectSource.tenant_id == t, ProjectSource.project_id == p,
            ProjectSource.use_state == SOURCE_INCLUDED)).label("sources_included"),
        _count(select(func.count(func.distinct(LiteratureMatrixCell.source_id))).where(
            LiteratureMatrixCell.tenant_id == t, LiteratureMatrixCell.project_id == p,
            LiteratureMatrixCell.source_scope == FULL_TEXT)).label("sources_full_text"),
        _count(select(func.count(func.distinct(LiteratureMatrixCell.source_id))).where(
            LiteratureMatrixCell.tenant_id == t, LiteratureMatrixCell.project_id == p,
            LiteratureMatrixCell.cell_state == CELL_KNOWN)).label("matrix_sources"),
        _count(select(func.count(LiteratureMatrixCell.id)).where(
            LiteratureMatrixCell.tenant_id == t, LiteratureMatrixCell.project_id == p,
            LiteratureMatrixCell.cell_state == CELL_KNOWN)).label("matrix_cells_known"),
        simple(ThemeCandidate).label("themes"),
        simple(ContradictionCandidate).label("contradictions"),
        simple(GapCandidate).label("gaps"),
        simple(Theory).label("theories"),
        simple(Construct).label("constructs"),
        simple(Variable).label("variables"),
        simple(Instrument).label("instruments"),
        _count(select(func.count(InstrumentItem.id))
               .where(InstrumentItem.tenant_id == t,
                      InstrumentItem.instrument_id.in_(
                          select(Instrument.id).where(
                              Instrument.tenant_id == t,
                              Instrument.project_id == p)))).label("instrument_items"),
        simple(Dataset).label("datasets"),
        _count(select(func.count()).select_from(
            runs_of_project.subquery())).label("analysis_runs"),
        _count(select(func.count()).select_from(
            outputs_of_project.subquery())).label("analysis_outputs"),
        # **النتيجةُ تفسيرٌ مسجَّلٌ على مخرَج** — لا المخرَجُ نفسه (§36).
        _count(select(func.count(InterpretationRow.id)).where(
            InterpretationRow.tenant_id == t,
            InterpretationRow.output_id.in_(outputs_of_project))).label("findings"),
        simple(Manuscript).label("manuscripts"),
        _count(select(func.count()).select_from(sections_of_project).where(
            func.coalesce(
                func.nullif(func.trim(func.coalesce(sections_of_project.c.text_ar, "")), ""),
                func.nullif(func.trim(func.coalesce(sections_of_project.c.text_en, "")), ""),
            ).is_not(None))).label("sections_with_text"),
        _count(select(func.count()).select_from(sections_of_project).where(
            sections_of_project.c.review_status == "approved")).label("sections_approved"),
    ))).one()

    #: المنهجُ صفٌّ يُقرأ لا عددٌ يُحصى — والأحدثُ هو المعمول به.
    method = (await session.execute(
        select(Method.study_type, Method.design_family)
        .where(Method.tenant_id == t, Method.project_id == p)
        .order_by(Method.created_at.desc(), Method.id.desc()).limit(1)
    )).first()

    return StageFacts(
        questions=row.questions, objectives=row.objectives,
        sources_linked=row.sources_linked, sources_included=row.sources_included,
        sources_full_text=row.sources_full_text,
        matrix_sources=row.matrix_sources, matrix_cells_known=row.matrix_cells_known,
        themes=row.themes, contradictions=row.contradictions, gaps=row.gaps,
        has_method_row=method is not None,
        study_type=method[0] if method else None,
        design_family=method[1] if method else None,
        theories=row.theories, constructs=row.constructs, variables=row.variables,
        instruments=row.instruments, instrument_items=row.instrument_items,
        datasets=row.datasets,
        analysis_runs=row.analysis_runs, analysis_outputs=row.analysis_outputs,
        findings=row.findings,
        manuscripts=row.manuscripts,
        sections_with_text=row.sections_with_text,
        sections_approved=row.sections_approved,
    )


__all__ = ["CELL_KNOWN", "FULL_TEXT", "SOURCE_INCLUDED", "read"]
