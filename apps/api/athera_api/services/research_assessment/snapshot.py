"""من بحثٍ حقيقي إلى لقطةٍ يحكم عليها العقل البحثي | The project → Assessment bridge.

**هذا هو الجسر، وليس عقلًا ثانيًا.** القواعد العشر في
`athera_api/research_brain/` تقرأ `Assessment` — لقطةً خالصة بلا جلسة ولا
كائن ORM — وكانت تُبنى في الاختبارات وحدها. فما كان ينقص ليس قاعدةً حادية
عشرة، بل قارئًا يبني تلك اللقطة من صفوف بحثٍ قائم.

**ولمَ لا يسكن هذا الملف في `research_brain/`:** تلك الحزمة تُعلن في رأسها
أنها «عقودٌ وقواعد حتمية… ولا مسار API، ولا ترحيل، ولا كتابة في قاعدة
بيانات». وقراءةُ الجلسة فيها تنقض ما يجعل كل قاعدة قابلة للاختبار بلا
قاعدة بيانات. فالحدّ يبقى: هناك الحكم، وهنا القراءة.

## ثلاثة قيود تحكم كل استعلام أدناه

**الأول: البحث لا يستعير من بحثٍ آخر.** كل استعلام هنا مقيَّد بـ
`project_id` — إمّا بعمودٍ في الجدول نفسه، وإمّا بسلسلةٍ تثبت الانتماء
(ملفات هذا البحث ← مرشّحوها ← ذاكرتها). والعطب مسجَّل في
`services/workspace.py`: أول صياغةٍ لـ«دماغ البحث» قرأت ذاكرة المستأجر
كلها، فعرض بحثٌ معرفةً استُخرجت من بحثٍ غيره — والباحث لا يرى الفرق.

**والثاني: ما لا يُقرأ يُعلَن.** حقلٌ لا وجود له في القاعدة (الإطار الزمني
للتصميم مثلًا) لا يُخمَّن ولا يُملأ افتراضًا؛ يُترك على حاله المعلَنة
ويُذكر في `notes`. و`Quantity` تجعل هذا ممكنًا: «حجم العيّنة غير مسجَّل»
جوابٌ صحيح يمرّ إلى الباحث كما هو.

**والثالث: مفرداتُ الحالات تُقرأ من مصادرها.** كل اسم حالةٍ هنا —
`included` و`saved_only` و`verified` و`approved` و`active` — مأخوذٌ من
القيد الذي يحكمه في الترحيل أو من النموذج الذي يعرّفه، ولا يُكتب من
الذاكرة. وقيمةٌ في القاعدة لا تعرفها مفرداتُ الأنطولوجيا (وعمود
`methods.design_family` بلا قيد، فهذا وارد) **لا تُمرَّر**: تُسقَط ويُذكر
إسقاطها، لأن `Design` سترفضها ويسقط التقييم كله بخطأٍ تحقّق.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.analysis import (
    AnalysisOutputRow,
    AnalysisPlanRow,
    AnalysisRun,
    DataDictionary,
    Dataset,
    DatasetVersionRow,
    PlannedTestRow,
)
from ...models.golden_thread import Construct, Method, ThreadElement, Theory, Variable
from ...models.literature import Claim, ClaimEvidenceLink, EvidenceExcerpt, Source
from ...models.portfolio import ProjectFile, ProjectSource
from ...models.publishing import (
    ClaimMemoryLink,
    Manuscript,
    ManuscriptSection,
    ManuscriptVersion,
)
from ...models.research import FactCandidate, ResearcherMemory
from ...research_brain import ontology as o
from ...research_brain.rules import Assessment, BrainFieldView, CandidateView
from ...research_brain.values import known, missing
from ..golden_thread.vocab import SAMPLING_STRATEGIES
from ..publishing.drafting.checks import sample_numbers
from ..publishing.vocab import MANUSCRIPT_SECTIONS
from ..workspace import BRAIN_FIELDS

# مقاييس المتغيّرات كما يقبلها `Measure.scale_type` و`Analysis.outcome_scale`.
# وعمود `variables.scale_type` و`data_dictionaries.scale_type` كلاهما
# `String(24)` بلا قيد في القاعدة، والقيد الوحيد في المستودع هو نمط
# `schemas/analysis.py`. فما خالفه يُسقَط هنا ولا يُمرَّر.
SCALE_TYPES = frozenset({"nominal", "ordinal", "interval", "ratio"})


@dataclass(frozen=True, slots=True)
class ReadNote:
    """ما لم يُقرأ ولماذا — **يُعلَن ولا يُملأ**.

    لقطةٌ ناقصة تُسلَّم صامتةً تجعل القاعدة تقول `pass` عمّا لم تره. فيُحمل
    النقص مع اللقطة، ويُعرض للباحث بجانب الحكم.
    """

    key: str
    detail_ar: str
    detail_en: str


@dataclass(frozen=True, slots=True)
class Contradiction:
    """تعارضٌ **مسجَّل في البيانات نفسها**، لا مستنبَط من نصّ.

    ومصدره اليوم واحد: `claim_evidence_links.support_level = 'contradictory'`
    بلا `resolution_note_ar` — أي دليلٌ يناقض ادّعاءً ولم يُعالَج. وهو ما
    يقوله §14.4 حرفيًّا: الدليل المناقض يُعرض ولا يُخفى.
    """

    claim_id: str
    detail_ar: str
    detail_en: str


@dataclass(frozen=True, slots=True)
class ProjectSnapshot:
    """اللقطة وما حولها: ما قُرئ، وما تعذّر، وما تعارض."""

    project_id: uuid.UUID
    title_ar: str
    assessment: Assessment
    notes: tuple[ReadNote, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    manuscript_id: uuid.UUID | None = None


@dataclass(slots=True)
class _Collector:
    """مجمّعٌ يمرّ على القرّاء — ولا يبني `ResearchGraph` إلا بعد اكتمالهم.

    و`ResearchGraph` يرفض رابطًا طرفُه غير موجود، فالبناء دفعةً واحدة في
    آخر المسار يجعل ذلك الرفض إنذارًا مبكرًا لا انهيارًا في منتصف القراءة.
    """

    entities: list[o.Entity] = field(default_factory=list)
    links: list[o.Relationship] = field(default_factory=list)
    notes: list[ReadNote] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)

    def add(self, entity: o.Entity) -> o.Entity:
        self.entities.append(entity)
        return entity

    def link(self, kind: o.RelationKind, source_id: str, target_id: str) -> None:
        """رابطٌ واحد لا يتكرّر.

        فمصدرٌ يسند ادّعاءً بمقتطفَين رابطٌ واحد لا رابطان، وتكراره يُخرج
        للباحث تنبيهين لعطبٍ واحد — وهو ما يعلّمه تجاهُل التنبيهات.
        """
        row = o.Relationship(kind=kind, source_id=source_id, target_id=target_id)
        if row not in self.links:
            self.links.append(row)

    def note(self, key: str, detail_ar: str, detail_en: str) -> None:
        self.notes.append(ReadNote(key, detail_ar, detail_en))

    def has(self, entity_id: str) -> bool:
        return any(e.id == entity_id for e in self.entities)


def _eid(kind: str, row_id: object) -> str:
    """معرّف الكيان في اللقطة: نوعُه ثم معرّف صفّه.

    والنوع في المقدّمة لأن مخرَج تحليلٍ وتشغيلته قد يحملان معرّفًا متقاربًا
    في القراءة، ورسالةُ مخالفةٍ تذكر معرّفًا عاريًا لا تقول عن أي شيء تتكلّم.
    """
    return f"{kind}:{row_id}"


def _label(*candidates: str | None, fallback: str) -> str:
    """أول تسميةٍ غير فارغة — و`Entity.label_ar` لا تقبل الفراغ."""
    for value in candidates:
        if value and value.strip():
            return value.strip()[:255]
    return fallback


# ─────────────────────────── القرّاء، واحدًا واحدًا ───────────────────────────
#
# كلٌّ منها يذكر `project_id` في شرطه، أو يمرّ بجدولٍ يذكره. ولا قارئ هنا
# يقرأ بالمستأجر وحده.

async def _read_design_and_sample(session: AsyncSession, tenant_id: uuid.UUID,
                                  project_id: uuid.UUID, out: _Collector) -> None:
    """التصميم والعيّنة من `methods` — صفّ المنهج الأحدث لهذا البحث.

    **والإطار الزمني لا يُقرأ لأنه غير مسجَّل.** `Design.temporal_frame`
    حقلٌ أعلنت الأنطولوجيا صراحةً أنه «لا وجود له في القاعدة اليوم»، فيبقى
    `unknown` ولا يُشتقّ من عائلة التصميم: «ارتباطي» لا يعني «مقطعي»،
    واشتقاقُه يجعل القاعدة تتهم بحثًا طوليًّا بما لم يقع فيه.
    """
    row = (await session.execute(
        select(Method).where(Method.tenant_id == tenant_id,
                             Method.project_id == project_id)
        .order_by(Method.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if row is None:
        out.note("method_not_recorded",
                 "لا منهج مسجَّل لهذا البحث — فلا يُحكم على ملاءمة تصميمٍ لم يُذكر.",
                 "No method recorded for this project; the fit of an unrecorded design "
                 "is not judged.")
        return

    family = row.design_family if row.design_family in o.DESIGN_FAMILIES else None
    if row.design_family and family is None:
        # عمود `design_family` بلا قيد في القاعدة، والمفردة متفرّقة على أربعة
        # مواضع (انظر رأس `ontology.py`). فقيمةٌ خارجها تُسقَط وتُذكر، ولا
        # تُمرَّر فتُسقط التقييم كله بخطأ تحقّق.
        out.note("design_family_outside_vocabulary",
                 f"عائلة التصميم المسجَّلة «{row.design_family}» ليست من المفردة "
                 "المعروفة، فلم تُقرأ.",
                 f"The recorded design family '{row.design_family}' is outside the known "
                 "vocabulary and was not read.")

    out.add(o.Design(
        id=_eid("design", row.id),
        label_ar=_label(row.design_label_ar, row.study_type, fallback="التصميم المسجَّل"),
        study_type=row.study_type, design_family=family))
    out.note("temporal_frame_not_stored",
             "الإطار الزمني (مقطعي/طولي) غير مسجَّل في القاعدة، فلم يُقرأ ولم يُخمَّن.",
             "The temporal frame (cross-sectional/longitudinal) is not stored, so it was "
             "neither read nor guessed.")

    strategy = (row.sampling_strategy
                if row.sampling_strategy in SAMPLING_STRATEGIES else None)
    size = (known(float(row.sample_size), source_ref=_eid("method", row.id))
            if row.sample_size is not None else missing())
    out.add(o.Sample(
        id=_eid("sample", row.id),
        label_ar=_label(row.population_ar, fallback="عيّنة الدراسة"),
        sampling_strategy=strategy, size=size))


async def _read_thread_elements(session: AsyncSession, tenant_id: uuid.UUID,
                                project_id: uuid.UUID, project_entity_id: str,
                                out: _Collector) -> None:
    """أسئلة البحث وفروضه وتوصياته من `thread_elements` لهذا البحث.

    والأنواع تُقرأ من `ELEMENT_TYPE_BY_ENTITY` لا تُكتب هنا: هي الجسر
    المعلَن بين كيانات الأنطولوجيا وأنواع عناصر الخيط القائمة.
    """
    wanted = {o.ELEMENT_TYPE_BY_ENTITY[kind]: kind for kind in (
        o.EntityKind.RESEARCH_QUESTION, o.EntityKind.HYPOTHESIS,
        o.EntityKind.RECOMMENDATION)}
    rows = (await session.execute(
        select(ThreadElement).where(
            ThreadElement.tenant_id == tenant_id,
            ThreadElement.project_id == project_id,
            ThreadElement.element_type.in_(tuple(wanted)))
        .order_by(ThreadElement.ordinal)
    )).scalars().all()

    for row in rows:
        kind = wanted[row.element_type]
        entity_id = _eid(row.element_type, row.id)
        label = _label(row.label_ar, fallback=f"عنصر {row.element_type}")
        if kind is o.EntityKind.RESEARCH_QUESTION:
            out.add(o.ResearchQuestion(id=entity_id, label_ar=label, label_en=row.label_en))
            out.link(o.RelationKind.PROJECT_HAS_QUESTION, project_entity_id, entity_id)
        elif kind is o.EntityKind.HYPOTHESIS:
            out.add(o.Hypothesis(id=entity_id, label_ar=label, label_en=row.label_en))
        else:
            out.add(o.Recommendation(id=entity_id, label_ar=label, label_en=row.label_en))


async def _read_theories(session: AsyncSession, tenant_id: uuid.UUID,
                         project_id: uuid.UUID, project_entity_id: str,
                         out: _Collector) -> None:
    rows = (await session.execute(
        select(Theory).where(Theory.tenant_id == tenant_id,
                             Theory.project_id == project_id)
    )).scalars().all()
    for row in rows:
        entity_id = _eid("theory", row.id)
        out.add(o.Theory(id=entity_id, label_ar=_label(row.name_ar, fallback="نظرية"),
                         label_en=row.name_en,
                         source_id=str(row.source_id) if row.source_id else None))
        out.link(o.RelationKind.PROJECT_USES_THEORY, project_entity_id, entity_id)


async def _read_constructs_and_measures(session: AsyncSession, tenant_id: uuid.UUID,
                                        project_id: uuid.UUID, out: _Collector) -> None:
    """البُنى ومتغيّراتها — و«التعريف الإجرائي مسجَّل؟» يُقرأ لا يُدَّعى.

    و`Measure` تُقرأ من `variables` لا من `instruments`: الأنطولوجيا تقول
    صراحةً إن `Measure.scale_type` «قيمه هي قيم `variables.scale_type`
    نفسها»، والأداة وعاءٌ لبنودها لا مقياسٌ بذاته.
    """
    constructs = (await session.execute(
        select(Construct).where(Construct.tenant_id == tenant_id,
                                Construct.project_id == project_id)
    )).scalars().all()
    variables = (await session.execute(
        select(Variable).where(Variable.tenant_id == tenant_id,
                               Variable.project_id == project_id)
    )).scalars().all()

    for row in constructs:
        out.add(o.Construct(
            id=_eid("construct", row.id),
            label_ar=_label(row.name_ar, fallback="بناء"), label_en=row.name_en,
            definition_ar=row.conceptual_definition_ar,
            has_operational_definition=any(
                (v.operational_definition_ar or "").strip()
                for v in variables if v.construct_id == row.id)))

    for variable in variables:
        scale = variable.scale_type if variable.scale_type in SCALE_TYPES else None
        if variable.scale_type and scale is None:
            out.note("variable_scale_outside_vocabulary",
                     f"مقياس المتغير «{variable.name_ar}» مسجَّل «{variable.scale_type}» "
                     "وليس من المقاييس الأربعة، فلم يُقرأ.",
                     f"Variable '{variable.name_ar}' records scale "
                     f"'{variable.scale_type}', which is not one of the four scale types, "
                     "so it was not read.")
        entity_id = _eid("variable", variable.id)
        out.add(o.Measure(id=entity_id,
                          label_ar=_label(variable.name_ar, fallback="متغير"),
                          label_en=variable.name_en, scale_type=scale,
                          construct_id=(_eid("construct", variable.construct_id)
                                        if variable.construct_id else None)))
        if variable.construct_id and out.has(_eid("construct", variable.construct_id)):
            out.link(o.RelationKind.CONSTRUCT_OPERATIONALIZED_BY_MEASURE,
                     _eid("construct", variable.construct_id), entity_id)


async def _read_datasets(session: AsyncSession, tenant_id: uuid.UUID,
                         project_id: uuid.UUID, out: _Collector) -> dict[uuid.UUID, str]:
    """مجموعات البيانات وتجميدها الحالي — و«الحالي» أحدثُ إصدارٍ مجمَّد.

    و§17.3 تجعل السؤال «هل تغيّرت البيانات؟» مقارنةَ معرّفَي تجميد لا حكمًا
    تقديريًّا. فمجموعةٌ بلا إصدارٍ مجمَّد تُقرأ بلا `current_freeze_id`،
    وهذا ما يجعل `RB-LINEAGE-01` تقول «لا يُعرف» بدل أن تقول «سليم».
    """
    rows = (await session.execute(
        select(Dataset).where(Dataset.tenant_id == tenant_id,
                              Dataset.project_id == project_id)
    )).scalars().all()
    by_dataset: dict[uuid.UUID, str] = {}
    for row in rows:
        latest = (await session.execute(
            select(DatasetVersionRow).where(
                DatasetVersionRow.tenant_id == tenant_id,
                DatasetVersionRow.dataset_id == row.id,
                DatasetVersionRow.frozen_at.is_not(None))
            .order_by(DatasetVersionRow.frozen_at.desc()).limit(1)
        )).scalar_one_or_none()
        entity_id = _eid("dataset", row.id)
        by_dataset[row.id] = entity_id
        out.add(o.Dataset(
            id=entity_id, label_ar=_label(row.name_ar, fallback="مجموعة بيانات"),
            label_en=row.name_en,
            state=latest.state if latest is not None else None,
            current_freeze_id=latest.freeze_id if latest is not None else None))
        if latest is None:
            out.note("dataset_never_frozen",
                     f"مجموعة «{row.name_ar}» بلا إصدارٍ مجمَّد — فلا يُعرف أجرى "
                     "التحليل على بياناتها الحالية أم لا.",
                     f"Dataset '{row.name_ar}' has no frozen version, so whether the "
                     "analysis ran on its current data cannot be known.")
    return by_dataset


async def _read_analyses(session: AsyncSession, tenant_id: uuid.UUID,
                         project_id: uuid.UUID, datasets: dict[uuid.UUID, str],
                         out: _Collector) -> dict[uuid.UUID, list[tuple[str, str | None]]]:
    """التشغيلات — **كيانٌ لكل اختبارٍ نُفّذ**، لا لكل تشغيلة.

    لأن `Analysis.test_kind` مفردٌ وقاعدةُ الملاءمة تُطبَّق على اختبار، أما
    التشغيلة الواحدة فقد تنفّذ اختبارات عدّة. وضمُّها في كيانٍ واحد يجعل
    خمسة اختبارات تُحكم بحكم أوّلها.

    **والافتراضات لا تُقرأ لأنها لا تُسجَّل.** لا عمود في المستودع يحمل
    «هل فُحص التجانس؟»، فتُترك `assumptions` فارغة — وتقول القاعدة عندها
    «لم تُفحص»، وهو الصدق بعينه: الاختبار غير مفحوصٍ لا ناجحٍ ولا فاشل.
    """
    runs = (await session.execute(
        select(AnalysisRun, AnalysisPlanRow, DatasetVersionRow)
        .join(AnalysisPlanRow, AnalysisPlanRow.id == AnalysisRun.plan_id)
        .join(DatasetVersionRow, DatasetVersionRow.id == AnalysisRun.dataset_version_id)
        .where(AnalysisRun.tenant_id == tenant_id,
               AnalysisPlanRow.tenant_id == tenant_id,
               AnalysisPlanRow.project_id == project_id)
    )).all()
    if not runs:
        return {}

    plan_ids = {plan.id for _run, plan, _version in runs}
    planned = (await session.execute(
        select(PlannedTestRow).where(PlannedTestRow.tenant_id == tenant_id,
                                     PlannedTestRow.plan_id.in_(plan_ids))
    )).scalars().all()
    kind_by_key = {(row.plan_id, row.test_key): row.test_kind for row in planned}
    variables_by_key = {(row.plan_id, row.test_key): tuple(row.variables or ())
                        for row in planned}

    by_run: dict[uuid.UUID, list[tuple[str, str | None]]] = {}
    for run, plan, version in runs:
        scales = await _scales_for(session, tenant_id, project_id, version.id)
        # مفتاحٌ واحد لا يصير كيانين: لا قيد في القاعدة يمنع أن يظهر المفتاح
        # في القائمتين معًا، ومعرّفان متطابقان يرفضهما `ResearchGraph` فيسقط
        # التقييم كله — على بحثٍ لا عيب فيه.
        keys = list(dict.fromkeys(
            list(run.executed_test_keys or []) + list(run.exploratory_test_keys or [])))
        entries: list[tuple[str, str | None]] = []
        for key in keys or [None]:
            test_kind = kind_by_key.get((plan.id, key)) if key else None
            outcome, predictor = (None, None)
            if key:
                outcome, predictor = _match_scales(
                    variables_by_key.get((plan.id, key), ()), scales)
            entity_id = _eid("analysis", f"{run.id}:{key}" if key else run.id)
            out.add(o.Analysis(
                id=entity_id,
                label_ar=_label(key, fallback=f"تشغيلة {run.tool}"),
                test_kind=test_kind, dataset_freeze_id=run.dataset_freeze_id,
                outcome_scale=outcome, predictor_scale=predictor))
            entries.append((entity_id, key))
            dataset_entity = datasets.get(version.dataset_id)
            if dataset_entity:
                out.link(o.RelationKind.ANALYSIS_USES_DATASET, entity_id, dataset_entity)
        by_run[run.id] = entries

    out.note("assumptions_not_stored",
             "لا يُسجَّل في المستودع فحصُ افتراضات الاختبارات، فلم تُقرأ — "
             "ويُقال «لم تُفحص» ولا يُقال «تحقّقت».",
             "The repository stores no record of statistical assumption checks, so none "
             "were read; the verdict says 'never checked', never 'satisfied'.")
    return by_run


async def _scales_for(session: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID,
                      version_id: uuid.UUID) -> dict[str, tuple[str | None, str | None]]:
    """قاموس البيانات لهذه النسخة: اسم العمود ← (مقياسه، دور متغيّره).

    و`data_dictionaries` هو الموضع **الوحيد** الذي يُكتب فيه مقياسُ عمودٍ
    فعلًا في هذا المستودع (انظر `routers/analysis.py`)، أما
    `variables.scale_type` فلا يكتبه مسارٌ اليوم. فيُقرأ من حيث يُكتب.
    """
    rows = (await session.execute(
        select(DataDictionary, Variable)
        .outerjoin(Variable, Variable.id == DataDictionary.variable_id)
        .where(DataDictionary.tenant_id == tenant_id,
               DataDictionary.dataset_version_id == version_id)
    )).all()
    out: dict[str, tuple[str | None, str | None]] = {}
    for entry, variable in rows:
        # المتغيّر المرتبط يجب أن يكون متغيّر **هذا البحث**؛ وقاموسٌ يشير
        # إلى متغيّرٍ من بحثٍ آخر يُقرأ بلا دور، لا بدور الغريب.
        role = variable.role if variable is not None and variable.project_id == project_id else None
        scale = entry.scale_type if entry.scale_type in SCALE_TYPES else None
        out[entry.column_name] = (scale, role)
    return out


def _match_scales(variables: tuple[str, ...],
                  scales: dict[str, tuple[str | None, str | None]]
                  ) -> tuple[str | None, str | None]:
    """مقياسا التابع والمستقل — **وواحدٌ لا أكثر، وإلا فلا حكم**.

    `planned_tests.variables` قائمةُ نصوص حرة، فالمقابلة على اسم العمود
    نصًّا بنصّ. واختبارٌ بتابعَين لا يُقال إن مقياس تابعه كذا: يُترك بلا
    مقياس، فتصمت القاعدة عن حكمٍ لا تملكه.
    """
    outcomes = [scale for name in variables
                for scale, role in (scales.get(name, (None, None)),)
                if role == "dependent" and scale]
    predictors = [scale for name in variables
                  for scale, role in (scales.get(name, (None, None)),)
                  if role == "independent" and scale]
    return (outcomes[0] if len(outcomes) == 1 else None,
            predictors[0] if len(predictors) == 1 else None)


async def _read_findings(session: AsyncSession, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         analyses_by_run: dict[uuid.UUID, list[tuple[str, str | None]]],
                         out: _Collector) -> None:
    """النتائج من `analysis_outputs` — وقيمةُ p تُقرأ من الحمولة لا تُشتقّ.

    والاستخراج بمحلّل الأرقام القائم (`drafting/numbers.facts`): محلّلٌ ثانٍ
    هنا يجعل الرقم يُقرأ قيمةَ دلالةٍ في شاشةٍ وشيئًا آخر في أخرى.

    و`source_ref` تشير إلى كيان التشغيلة نفسه الذي تُشتقّ منه النتيجة —
    فتكون السلسلة التي تفرضها `RB-FABRICATION-01` قائمةً بالبناء لا بالوعد.
    """
    from ..publishing.drafting import numbers

    if not analyses_by_run:
        return
    rows = (await session.execute(
        select(AnalysisOutputRow)
        .where(AnalysisOutputRow.tenant_id == tenant_id,
               AnalysisOutputRow.run_id.in_(tuple(analyses_by_run)))
    )).scalars().all()

    for row in rows:
        entries = analyses_by_run.get(row.run_id) or []
        if not entries:  # pragma: no cover - لا مخرَج بلا تشغيلة (قيد §39)
            continue
        analysis_id = next((eid for eid, key in entries if key and key == row.test_key),
                           entries[0][0])
        p_value = missing()
        for fact in numbers.facts(row.payload):
            if fact.kind != "p_value":
                continue
            try:
                p_value = known(float(fact.value), source_ref=analysis_id)
            except ValueError:  # pragma: no cover - القيمة موحَّدة قبل الوصول
                pass
            break
        finding_id = _eid("finding", row.id)
        out.add(o.Finding(id=finding_id,
                          label_ar=_label(row.label_ar, fallback="نتيجة"),
                          label_en=row.label_en, p_value=p_value))
        out.link(o.RelationKind.FINDING_DERIVED_FROM_ANALYSIS, finding_id, analysis_id)


async def _read_sources_claims_and_evidence(session: AsyncSession, tenant_id: uuid.UUID,
                                            project_id: uuid.UUID,
                                            out: _Collector) -> None:
    """المصادر والادّعاءات والأدلة — بحال استعمال كلٍّ منها **في هذا البحث**.

    و`project_sources.use_state` حالُ العلاقة لا حالُ الشيء: مصدرٌ «مُدرَج»
    هنا قد يكون «محفوظًا فقط» في بحثٍ آخر. فتُقرأ من الرابط.

    **ومصدرٌ يستشهد به ادّعاءٌ ولم يُربط بالبحث** يُقرأ `saved_only` — وهي
    قيمة الترحيل الافتراضية ومعناها بالضبط «لم يقرّر أحدٌ إدراجه هنا».
    وسكوتُنا عنه يجعل ورقةً تستشهد بما لم يدخل مكتبة بحثها أصلًا.
    """
    linked = (await session.execute(
        select(ProjectSource, Source)
        .join(Source, Source.id == ProjectSource.source_id)
        .where(ProjectSource.tenant_id == tenant_id,
               ProjectSource.project_id == project_id)
    )).all()
    source_entities: dict[uuid.UUID, str] = {}
    for link, source in linked:
        entity_id = _eid("source", source.id)
        source_entities[source.id] = entity_id
        out.add(o.Source(id=entity_id, label_ar=_label(source.title, fallback="مصدر"),
                         use_state=link.use_state,
                         verification_status=source.verification_status))

    claims = (await session.execute(
        select(Claim).where(Claim.tenant_id == tenant_id,
                            Claim.project_id == project_id)
    )).scalars().all()
    if not claims:
        return
    claim_ids = tuple(c.id for c in claims)

    for row in claims:
        out.add(o.Claim(id=_eid("claim", row.id),
                        label_ar=_label(row.text_ar[:120], fallback="ادّعاء"),
                        text_ar=row.text_ar, origin=_claim_origin(row)))

    # ── دليلٌ من مقتطف مصدر ──
    excerpts = (await session.execute(
        select(ClaimEvidenceLink, EvidenceExcerpt, Source)
        .join(EvidenceExcerpt, EvidenceExcerpt.id == ClaimEvidenceLink.excerpt_id)
        .join(Source, Source.id == ClaimEvidenceLink.source_id)
        .where(ClaimEvidenceLink.tenant_id == tenant_id,
               ClaimEvidenceLink.claim_id.in_(claim_ids))
    )).all()
    for link, excerpt, source in excerpts:
        claim_entity = _eid("claim", link.claim_id)
        evidence_id = _eid("evidence-excerpt", excerpt.id)
        if not out.has(evidence_id):
            # `source_type` من مفردة `provenance_events`: مصدرٌ معه ملفٌّ
            # مرفوع مسارُه `upload`، وما جاء من سجلٍّ خارجي `external_source`.
            out.add(o.Evidence(
                id=evidence_id, label_ar=_label(excerpt.quote[:120], fallback="مقتطف"),
                source_type="upload" if source.file_id else "external_source",
                verification_status=source.verification_status,
                source_ref=excerpt.locator))
        out.link(o.RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE, claim_entity, evidence_id)

        if source.id not in source_entities:
            source_entities[source.id] = _eid("source", source.id)
            out.add(o.Source(id=source_entities[source.id],
                             label_ar=_label(source.title, fallback="مصدر"),
                             use_state="saved_only",
                             verification_status=source.verification_status))
            out.note("cited_source_not_linked_to_project",
                     f"المصدر «{source.title[:80]}» يستشهد به ادّعاءٌ في هذا البحث ولم "
                     "يُربط به — فحالُه فيه «محفوظ فقط».",
                     f"Source '{source.title[:80]}' backs a claim in this project but was "
                     "never linked to it; its use state here is `saved_only`.")
        out.link(o.RelationKind.SOURCE_SUPPORTS_CLAIM, source_entities[source.id],
                 claim_entity)

        if link.support_level == "contradictory" and not (link.resolution_note_ar or "").strip():
            out.contradictions.append(Contradiction(
                claim_id=claim_entity,
                detail_ar=f"دليلٌ مناقض غير معالَج من «{source.title[:80]}» "
                          f"على الادّعاء: {excerpt.quote[:120]}",
                detail_en=f"Unresolved contradictory evidence from "
                          f"'{source.title[:80]}' against this claim."))

    # ── دليلٌ من ذاكرةٍ موثقة ──
    #
    # و`researcher_memories.source_type` مقيَّدٌ في الترحيل 0005 بمسارات §7.4
    # الأربعة، و`model_output` ليست منها. فمخرَجُ نموذجٍ لا يصل هنا دليلًا
    # أصلًا — والقيد هو الذي يمنعه، لا هذا القارئ.
    memories = (await session.execute(
        select(ClaimMemoryLink, ResearcherMemory)
        .join(ResearcherMemory, ResearcherMemory.id == ClaimMemoryLink.memory_id)
        .where(ClaimMemoryLink.tenant_id == tenant_id,
               ClaimMemoryLink.claim_id.in_(claim_ids))
    )).all()
    for link, memory in memories:
        evidence_id = _eid("evidence-memory", memory.id)
        if not out.has(evidence_id):
            out.add(o.Evidence(
                id=evidence_id,
                label_ar=_label(memory.statement_ar[:120], fallback="ذاكرة موثقة"),
                source_type=memory.source_type,
                verification_status=memory.verification_status,
                source_ref=memory.source_locator))
        out.link(o.RelationKind.CLAIM_SUPPORTED_BY_EVIDENCE,
                 _eid("claim", link.claim_id), evidence_id)


def _claim_origin(row: Claim) -> str:
    """أصلُ الادّعاء: واقعةٌ أم تفسير؟

    و`Claim.origin` في الأنطولوجيا ثلاثٌ (`fact | interpretation | proposal`)،
    والمقابل في القاعدة عمودان: `claim_type` (§14.4) و`is_labelled_inference`
    (§4). فالموسوم استنتاجًا تفسير، والنوع `interpretive` تفسير، وما عداهما
    يُعرض واقعةً — وهو الوسم الذي تطالبه `RB-EVIDENCE-02` بدليل.
    """
    if row.is_labelled_inference or row.claim_type == "interpretive":
        return "interpretation"
    return "fact"


async def _read_fields_and_candidates(session: AsyncSession, tenant_id: uuid.UUID,
                                      project_id: uuid.UUID,
                                      out: _Collector) -> tuple[
                                          tuple[BrainFieldView, ...],
                                          tuple[CandidateView, ...]]:
    """«ما نعرفه عن هذا البحث» — بحالته وسنده معًا.

    **والسلسلة هي التي تثبت الانتماء**: ملفات هذا البحث ← مرشّحوها ←
    ذاكرتها. و`researcher_memories` لا تحمل `project_id`، فالقراءة
    بالمستأجر وحده تعرض معرفةَ بحثٍ في بحثٍ آخر — وهو العطب المسجَّل في
    `services/workspace.py`، ولا يُعاد هنا.

    وحدّ هذا الاشتقاق يُقال كما قيل هناك: من مسارات §7.4 الأربعة يمرّ
    `upload` وحده بملف. فذاكرةٌ رُقّيت من تشغيلة تحليل أو من قول الباحث لا
    تظهر هنا، ويُعرض حقلها «ناقصًا» — نقصٌ يُرى فيُسدّ، أهون من معرفةٍ
    مستعارة يُبنى عليها.

    والحالات الأربع نفسها المكتوبة في `BrainEntry.state` — تُشتقّ بالمنطق
    نفسه ولا تُعرَّف من جديد، وإلا صار الحقل «معلومًا» في شاشةٍ و«ناقصًا»
    في أخرى.
    """
    from ..planning.context import ROLE_BY_FIELD

    rows = (await session.execute(
        select(ResearcherMemory, FactCandidate)
        .join(FactCandidate, FactCandidate.resulting_memory_id == ResearcherMemory.id)
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(ResearcherMemory.tenant_id == tenant_id,
               FactCandidate.tenant_id == tenant_id,
               ProjectFile.tenant_id == tenant_id,
               ProjectFile.project_id == project_id,
               ProjectFile.state == ProjectFile.ACTIVE)
    )).all()

    by_role: dict[str, list[tuple[ResearcherMemory, FactCandidate]]] = {}
    for memory, candidate in rows:
        role = ROLE_BY_FIELD.get(candidate.field_key or "", "other")
        by_role.setdefault(role, []).append((memory, candidate))

    fields: list[BrainFieldView] = []
    for key, _label_ar, _label_en, roles in BRAIN_FIELDS:
        found = [pair for role in roles for pair in by_role.get(role, ())]
        verified = [pair for pair in found if pair[0].verification_status == "verified"]
        pending = [pair for pair in found if pair[0].verification_status != "verified"]
        if verified:
            state, backing = "known", verified
        elif pending:
            state, backing = "needs_review", pending
        else:
            state, backing = "missing", []
        fields.append(BrainFieldView(
            key=key, state=state,
            backing_memory_ids=tuple(str(memory.id) for memory, _c in backing),
            backing_candidate_ids=tuple(str(cand.id) for _m, cand in backing)))

    # المرشّحون كلهم — المعتمَد والمنتظر معًا — من ملفات هذا البحث وحدها.
    candidates = (await session.execute(
        select(FactCandidate)
        .join(ProjectFile, ProjectFile.file_id == FactCandidate.file_id)
        .where(FactCandidate.tenant_id == tenant_id,
               ProjectFile.tenant_id == tenant_id,
               ProjectFile.project_id == project_id,
               ProjectFile.state == ProjectFile.ACTIVE)
    )).scalars().all()
    return (tuple(fields),
            tuple(CandidateView(id=str(row.id), status=row.status) for row in candidates))


async def _read_sections(session: AsyncSession, tenant_id: uuid.UUID,
                         project_id: uuid.UUID,
                         out: _Collector) -> tuple[dict[str, str], uuid.UUID | None]:
    """نصّ المخطوطة — **مخطوطةٌ واحدة، أحدثها**.

    وبحثٌ له مخطوطتان ورقتان مختلفتان؛ ووصلُ نصّيهما يجعل لغةً سببية في
    إحداهما تُحسب على تصميم الأخرى. فتُقرأ الأحدث ويُذكر ما تُرك.
    """
    manuscripts = (await session.execute(
        select(Manuscript).where(Manuscript.tenant_id == tenant_id,
                                 Manuscript.project_id == project_id)
        .order_by(Manuscript.created_at.desc())
    )).scalars().all()
    if not manuscripts:
        return {}, None
    if len(manuscripts) > 1:
        out.note("more_than_one_manuscript",
                 f"للبحث {len(manuscripts)} مخطوطات، وقُرئت الأحدث وحدها — "
                 "ووصلُ نصّين لورقتين يخلط حكمَ إحداهما بالأخرى.",
                 f"The project has {len(manuscripts)} manuscripts; only the most recent was "
                 "read — joining two papers' text mixes one's verdict into the other.")
    manuscript = manuscripts[0]

    version_id = manuscript.current_version_id
    if version_id is None:
        version = (await session.execute(
            select(ManuscriptVersion).where(
                ManuscriptVersion.tenant_id == tenant_id,
                ManuscriptVersion.manuscript_id == manuscript.id)
            .order_by(ManuscriptVersion.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        version_id = version.id if version is not None else None
    if version_id is None:
        return {}, manuscript.id

    rows = (await session.execute(
        select(ManuscriptSection).where(
            ManuscriptSection.tenant_id == tenant_id,
            ManuscriptSection.version_id == version_id)
    )).scalars().all()
    sections = {row.section_key: row.text_ar or "" for row in rows
                if row.section_key in MANUSCRIPT_SECTIONS and (row.text_ar or "").strip()}
    return sections, manuscript.id


# ──────────────────────────────── الجسر ────────────────────────────────

async def build_project_assessment(session: AsyncSession, *, tenant_id: uuid.UUID,
                                   project_id: uuid.UUID) -> ProjectSnapshot | None:
    """يبني لقطة بحثٍ قائم — أو `None` إن لم يكن بحثًا قائمًا لهذا المستأجر.

    و«القائم» من `workspace.live_project`: ما في السلّة ليس قائمًا، وتقييمُ
    بحثٍ محذوف يعيده إلى الشاشة من بابٍ خلفي.
    """
    from ..workspace import live_project

    project = await live_project(session, tenant_id=tenant_id, project_id=project_id)
    if project is None:
        return None

    out = _Collector()
    project_entity_id = _eid("project", project.id)
    out.add(o.Project(id=project_entity_id,
                      label_ar=_label(project.working_title_ar, fallback="بحث"),
                      label_en=project.working_title_en))

    await _read_design_and_sample(session, tenant_id, project_id, out)
    await _read_thread_elements(session, tenant_id, project_id, project_entity_id, out)
    await _read_theories(session, tenant_id, project_id, project_entity_id, out)
    await _read_constructs_and_measures(session, tenant_id, project_id, out)
    datasets = await _read_datasets(session, tenant_id, project_id, out)
    analyses = await _read_analyses(session, tenant_id, project_id, datasets, out)
    await _read_findings(session, tenant_id, project_id, analyses, out)
    await _read_sources_claims_and_evidence(session, tenant_id, project_id, out)
    fields, candidates = await _read_fields_and_candidates(
        session, tenant_id, project_id, out)
    sections, manuscript_id = await _read_sections(session, tenant_id, project_id, out)

    narrative = "\n".join(sections[key] for key in MANUSCRIPT_SECTIONS
                          if sections.get(key))
    in_text = tuple(sorted(
        float(token) for token in sample_numbers(narrative) if token.isdigit()))

    assessment = Assessment(
        graph=o.ResearchGraph(entities=out.entities, relationships=out.links),
        sections=sections, fields=fields, candidates=candidates,
        sample_numbers_in_text=in_text)
    return ProjectSnapshot(
        project_id=project.id, title_ar=project.working_title_ar,
        assessment=assessment, notes=tuple(out.notes),
        contradictions=tuple(out.contradictions), manuscript_id=manuscript_id)


__all__ = ["Contradiction", "ProjectSnapshot", "ReadNote", "SCALE_TYPES",
           "build_project_assessment"]
