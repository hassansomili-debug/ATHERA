"""AT-RB-05 — العقل البحثي على بحثٍ حقيقي: العزل، والاستشارة، وصدق الجهل.

تثبت هذه الحزمة أربعة أشياء، وأولها الذي كُتب لأجله كل ما تحته:

١) **تقييم بحثٍ لا يقرأ دليل بحثٍ آخر.** والعطب وقع فعلًا في هذا المستودع:
   أول صياغةٍ لـ«دماغ البحث» قرأت ذاكرة المستأجر كلها، فعرض بحثٌ معرفةً
   استُخرجت من بحثٍ غيره. فيُفحص العزل مرتين: بقراءة الشيفرة (كل استعلامٍ
   مقيَّد ببحثه) وبقاعدةٍ حيّة (بحثان لمستأجرٍ واحد، ومستأجران).

٢) **لا قاعدة تحجب.** كل قاعدة `DRAFT`، و`blocking` فارغة مهما بلغ عدد
   المخالفات. ولو انقلبت هذه لبدأ محرّكٌ لم يراجعه مختصّ يوقف باحثين.

٣) **«لم نجد شيئًا» ليست سلامة.** ما عجزت القاعدة عن فحصه يظهر في «ما
   يحتاج مراجعة» بنصّه، ولا يُبتلع فيُقرأ التقرير براءةً.

٤) **ولا نسبة جاهزية.** لا رقم يلخّص حال البحث في هذه الشاشة ولا في عقدها.
"""
import datetime as dt
import inspect
import pathlib
import re
import uuid

import pytest

from athera_api.research_brain import ontology as o
from athera_api.research_brain import rules
from athera_api.research_brain.catalogue import RULES
from athera_api.research_brain.rules import Assessment, BrainFieldView, CandidateView, Verdict
from athera_api.services.research_assessment import snapshot as bridge
from athera_api.services.research_assessment import view as researcher_view
from athera_api.services.research_assessment.snapshot import Contradiction, ProjectSnapshot
from tests.conftest import requires_db

API_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _snapshot(assessment: Assessment, *, contradictions=()) -> ProjectSnapshot:
    return ProjectSnapshot(
        project_id=uuid.uuid4(), title_ar="بحثٌ تحت التقييم",
        assessment=assessment, contradictions=tuple(contradictions))


# ───────────────── ١) العزل كما يُقرأ من الشيفرة ─────────────────

def _readers() -> dict[str, str]:
    """كل قارئ في الجسر بمصدره — والقارئ ما بدأ اسمه بـ`_read` أو `_scales`."""
    return {name: inspect.getsource(fn)
            for name, fn in vars(bridge).items()
            if inspect.isfunction(fn) and (name.startswith("_read")
                                           or name.startswith("_scales"))}


def test_every_reader_is_bound_to_one_project():
    """لا استعلام في الجسر يقرأ بالمستأجر وحده.

    فالمستأجر الواحد يملك بحوثًا كثيرة، وقيدُ RLS يمنع تسرّب المستأجرين ولا
    يمنع تسرّب البحوث داخل المستأجر الواحد — وهو بالضبط ما وقع.
    """
    assert _readers(), "لم يُعثر على قارئ واحد — تغيّر اسم القرّاء فمات الحارس"
    for name, source in _readers().items():
        bound = "project_id ==" in source or ".in_(" in source
        assert bound, (
            f"{name} يقرأ بلا قيدٍ على البحث — لا عمودَ `project_id` ولا حصرًا "
            "في معرّفاتٍ جُمعت من بحثٍ بعينه")


def test_the_memory_read_walks_the_chain_that_proves_belonging():
    """`researcher_memories` لا تحمل `project_id`، فالانتماء يُثبَت بالسلسلة.

    ملفات هذا البحث ← مرشّحوها ← ذاكرتها. وقراءةٌ تسقط أي حلقةٍ من الثلاث
    تعرض معرفةً من بحثٍ آخر، والباحث لا يرى الفرق.
    """
    source = inspect.getsource(bridge._read_fields_and_candidates)
    assert "FactCandidate.resulting_memory_id == ResearcherMemory.id" in source
    assert "ProjectFile.file_id == FactCandidate.file_id" in source
    assert "ProjectFile.project_id == project_id" in source
    assert "ProjectFile.state == ProjectFile.ACTIVE" in source


def test_the_engine_itself_still_touches_no_database():
    """`research_brain/` تبقى حتميةً بلا جلسة — وإلا مات إثباتُ القواعد.

    فحزمةٌ يحتاج اختبارُ قاعدةٍ فيها إلى PostgreSQL تُختبر مرةً ثم لا تُختبر.
    والجسر خارجها لهذا السبب وحده.
    """
    package = API_ROOT / "athera_api" / "research_brain"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "sqlalchemy" not in text, f"{path.name} استورد قاعدة البيانات"
        assert "AsyncSession" not in text, f"{path.name} صار يحمل جلسة"


def test_the_bridge_reuses_the_existing_number_parser():
    """محلّلُ أرقام العيّنة واحدٌ لا اثنان.

    ومحلّلٌ ثانٍ يجعل الرقم نفسه يُعدّ مخترَعًا في شاشةٍ ومسنَدًا في أخرى —
    وهو أكثر عطبٍ تكرارًا في هذا المستودع.
    """
    source = inspect.getsource(bridge)
    assert "from ..publishing.drafting.checks import sample_numbers" in source
    assert "re.compile" not in source, "الجسر كتب محلّلًا ثانيًا للأرقام"


def test_the_bridge_reads_state_names_from_their_owners():
    """أسماء الحالات تُشتقّ من سجلّها ولا تُكتب من الذاكرة.

    و«اسمُ حالةٍ يُكتب من الذاكرة بدل أن يُقرأ من مصدره» هو العطب الذي
    يفتتح به سجلّ القواعد نفسه.
    """
    source = inspect.getsource(bridge)
    assert "ProjectFile.state == ProjectFile.ACTIVE" in source, "حالُ الرابط كُتبت نصًّا"
    assert "in o.DESIGN_FAMILIES" in source, "عائلة التصميم لم تُقابَل بمفردتها"
    assert "in SAMPLING_STRATEGIES" in source, "أسلوب المعاينة لم يُقابَل بمفردته"
    assert "in MANUSCRIPT_SECTIONS" in source, "أقسام المخطوطة لم تُقابَل بمفردتها"


# ───────────────── ٢) لا حجب، ولا نسبة ─────────────────

def test_no_rule_blocks_through_this_surface():
    """بحثٌ مليءٌ بالمخالفات لا يوقفه هذا السطح — كل قاعدة مسوّدة."""
    assessment = Assessment(graph=o.ResearchGraph(entities=[
        o.Claim(id="c1", label_ar="ادّعاءٌ بلا دليل", origin="fact"),
        o.Source(id="s1", label_ar="مصدرٌ محفوظ", use_state="saved_only"),
    ], relationships=[
        o.Relationship(kind=o.RelationKind.SOURCE_SUPPORTS_CLAIM,
                       source_id="s1", target_id="c1"),
    ]))
    report, view = researcher_view.assess(_snapshot(assessment))
    assert report.violations, "الحالة لا تخالف شيئًا فلا تثبت شيئًا"
    assert report.blocking == ()
    assert view.is_advisory_only and view.blocking_count == 0
    assert view.methodological_alerts, "المخالفات لم تصل الباحث"


def test_the_advisory_note_says_so_in_arabic():
    assert "لا تُوقف" in researcher_view.ADVISORY_NOTE_AR
    assert "advisory" in researcher_view.ADVISORY_NOTE_EN


def test_nothing_in_this_surface_emits_a_readiness_score():
    """«بحثك جاهز بنسبة ٨٢٪» لا تُحسب ولا يوجد حقلٌ تُكتب فيه.

    والنسبة تخفي الفرق بين بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج — وهو القرار
    نفسه المتّخذ في شاشة الحال العامة، ولا يُنقض من بابٍ ثانٍ.
    """
    from athera_api.schemas.workspace import ProjectAssessmentView

    forbidden = re.compile(r"percent|readiness|score|ratio|جاهزية|نسبة\s*ال?جاهزية",
                           re.IGNORECASE)
    for name in ProjectAssessmentView.model_fields:
        assert not forbidden.search(name), f"عقد التقييم يحمل حقل نسبة: {name}"
    for name in researcher_view.ResearcherReport.__annotations__:
        assert not forbidden.search(name), f"تقرير الباحث يحمل حقل نسبة: {name}"

    view_source = inspect.getsource(researcher_view)
    assert "%" not in view_source.replace("٪", ""), "حُسبت نسبة في تقرير الباحث"
    assert "نسبة" in researcher_view.NO_SCORE_NOTE_AR


def test_the_five_categories_are_the_named_ones():
    """الخانات خمسٌ بأسمائها العربية — لا سادسة ولا تسمية ثانية."""
    assert [labels[0] for labels in researcher_view.CATEGORY_LABELS.values()] == [
        "ما نعرفه", "ما ينقص", "ما يحتاج مراجعة", "التعارضات", "تنبيهات منهجية"]
    report = researcher_view.researcher_report(
        _snapshot(Assessment()), rules.evaluate(Assessment(), RULES))
    for name in researcher_view.CATEGORY_LABELS:
        assert isinstance(report.category(name), tuple)


def test_the_knowledge_states_are_the_platform_states_not_a_second_vocabulary():
    """`known | needs_review | missing | conflicting` — كما في `workspace.py`.

    ومفردتان للشيء الواحد تجعلان الحقل «معلومًا» في شاشةٍ و«ناقصًا» في أخرى.
    """
    states = {researcher_view.KNOWN, researcher_view.NEEDS_REVIEW,
              researcher_view.MISSING, researcher_view.CONFLICTING}
    assert states == {"known", "needs_review", "missing", "conflicting"}
    pattern = BrainFieldView.model_fields["state"].metadata[0].pattern
    for state in states:
        assert state in pattern, f"الحالة {state} ليست من حالات `BrainFieldView`"


# ───────────────── ٣) الجهل يُعلَن ولا يُبتلع ─────────────────

def test_an_empty_project_is_never_reported_clean():
    """بحثٌ فارغ لا يخرج منه «سليم».

    وهذا هو الفخّ الذي تسقط فيه منظومات الفحص: قاعدةٌ لا تجد ما تفحصه
    فترجع `pass` تقول «فُحص وسلم» عمّا لم يُفحص، فيخرج تقريرٌ خالٍ من
    المخالفات عن بحثٍ لم يُقرأ منه شيء.
    """
    empty = Assessment(fields=tuple(
        BrainFieldView(key=key, state="missing")
        for key, *_rest in __import__(
            "athera_api.services.workspace", fromlist=["BRAIN_FIELDS"]).BRAIN_FIELDS))
    report, view = researcher_view.assess(_snapshot(empty))

    assert not report.violations, "بحثٌ فارغ لا يُخالف شيئًا"
    assert view.missing, "الفراغ لم يُعرض نقصًا"
    assert not any(item.rule_id and "فُحص وسلم" in item.detail_ar
                   for item in view.known), "قاعدةٌ لم تجد ما تفحصه قالت إنها فحصت وسلمت"


def test_insufficient_information_lands_in_needs_review_not_in_what_we_know():
    """الحكم الرابع يُعرض بنصّه — لا يُطوى ولا يُقرأ سلامة."""
    assessment = Assessment(graph=o.ResearchGraph(entities=[
        # عيّنةٌ بلا حجم مسجَّل: القاعدة لا تستطيع الفحص وتقولها.
        o.Sample(id="sample", label_ar="طلاب السنة الأولى"),
    ]))
    report, view = researcher_view.assess(_snapshot(assessment))
    assert report.verdict_of("RB-FABRICATION-02") is Verdict.INSUFFICIENT_INFORMATION
    assert any(item.rule_id == "RB-FABRICATION-02" for item in view.needs_review)
    assert not any(item.rule_id == "RB-FABRICATION-02" for item in view.known)


def test_two_papers_from_one_country_do_not_become_a_confirmed_gap():
    """كل ما في البحث مصدران ومطالبةٌ بفجوةٍ عالمية — ولا يُصدَّق الادّعاء.

    فالمنظومة لا تملك ما يثبت أن الفجوة عالمية: مصدران محفوظان لا يُبنى
    عليهما، والادّعاء يُعرض حقيقةً بلا دليل. فتسمّي حالته `evidence_gap`
    ولا تكتبه `supported`، ولا تقول «فُحص وسلم».
    """
    assessment = Assessment(graph=o.ResearchGraph(entities=[
        o.Claim(id="claim", label_ar="لا توجد دراسةٌ عالميًّا تناولت هذه العلاقة",
                origin="fact", text_ar="لا توجد دراسةٌ عالميًّا تناولت هذه العلاقة"),
        o.Source(id="s1", label_ar="دراسةٌ محليّة أولى", use_state="saved_only"),
        o.Source(id="s2", label_ar="دراسةٌ محليّة ثانية", use_state="saved_only"),
    ], relationships=[
        o.Relationship(kind=o.RelationKind.SOURCE_SUPPORTS_CLAIM,
                       source_id="s1", target_id="claim"),
        o.Relationship(kind=o.RelationKind.SOURCE_SUPPORTS_CLAIM,
                       source_id="s2", target_id="claim"),
    ]))
    report, view = researcher_view.assess(_snapshot(assessment))

    assert report.verdict_of("RB-EVIDENCE-01") is Verdict.VIOLATION
    assert report.verdict_of("RB-EVIDENCE-02") is Verdict.VIOLATION
    text = " ".join(item.detail_ar for item in view.methodological_alerts)
    assert "evidence_gap" in text
    assert not any("العلاقة" in item.detail_ar for item in view.known), (
        "ادّعاءٌ بلا دليل ظهر في «ما نعرفه»")


def test_a_recorded_contradiction_is_shown_as_a_conflict():
    """الدليل المناقض يُعرض ولا يُخفى (§14.4) — وفي خانته لا في التنبيهات."""
    view = researcher_view.researcher_report(
        _snapshot(Assessment(), contradictions=[Contradiction(
            claim_id="claim:1", detail_ar="دليلٌ مناقض غير معالَج على الادّعاء.",
            detail_en="Unresolved contradictory evidence.")]),
        rules.evaluate(Assessment(), RULES))
    assert len(view.conflicts) == 1
    assert view.conflicts[0].entity_ids == ("claim:1",)


def test_a_candidate_awaiting_a_decision_is_review_work_not_knowledge():
    """المرشّح ليس معرفة — و`unknown` ليست حكمًا كذلك (ترحيل 0016)."""
    assessment = Assessment(candidates=(
        CandidateView(id="c1", status="unverified"),
        CandidateView(id="c2", status="unknown"),
        CandidateView(id="c3", status="approved")))
    view = researcher_view.researcher_report(
        _snapshot(assessment), rules.evaluate(assessment, RULES))
    waiting = [item for item in view.needs_review if item.key == "candidates_waiting"]
    assert waiting and "2" in waiting[0].detail_ar


def test_a_field_declared_known_without_a_memory_is_a_violation_not_knowledge():
    """حقلٌ «معلوم» بلا ذاكرةٍ خلفه مخالفة — والحالة سالبة تُختبر كذلك."""
    bad = Assessment(fields=(BrainFieldView(key="question", state="known"),))
    good = Assessment(fields=(BrainFieldView(key="question", state="known",
                                             backing_memory_ids=("m1",)),))
    assert rules.evaluate(bad, RULES).verdict_of("RB-PROVENANCE-01") is Verdict.VIOLATION
    assert rules.evaluate(good, RULES).verdict_of("RB-PROVENANCE-01") is Verdict.PASS


def test_what_could_not_be_read_is_declared_beside_the_verdict():
    """لقطةٌ ناقصة تُسلَّم صامتةً تجعل القاعدة تقول `pass` عمّا لم ترَه."""
    snap = ProjectSnapshot(
        project_id=uuid.uuid4(), title_ar="بحث", assessment=Assessment(),
        notes=(bridge.ReadNote("temporal_frame_not_stored",
                               "الإطار الزمني غير مسجَّل في القاعدة.",
                               "The temporal frame is not stored."),))
    view = researcher_view.researcher_report(snap, rules.evaluate(Assessment(), RULES))
    assert any(item.key == "temporal_frame_not_stored" for item in view.read_notes)
    assert any(item.key == "temporal_frame_not_stored" for item in view.missing)


def test_the_route_never_leaks_another_tenants_project_as_a_different_error():
    """بحثٌ لغيرك و بحثٌ لا وجود له يُجابان بالجواب نفسه — 404 لا 403.

    وإلا صار الفرق بين الجوابين عدّادًا يُعدّ به ما ليس لك.
    """
    source = inspect.getsource(
        __import__("athera_api.routers.workspace", fromlist=["project_assessment"])
        .project_assessment)
    assert "_project(session, principal, project_id)" in source
    assert "Forbidden" not in source


# ───────── ٤) الجسر يُشغَّل كاملًا بجلسةٍ تسجّل ولا تتصل ─────────
#
# **ولمَ جلسةٌ مزيَّفة وقد كُتبت اختبارات القاعدة الحيّة تحت؟** لأن تلك
# تُتخطّى حيث لا PostgreSQL — في جهاز مطوّرٍ بلا Docker مثلًا — فيمرّ الجسر
# كله بلا تشغيلٍ واحد. وهذه تُشغّله دائمًا: تبني رسمًا كاملًا فتُمسك رابطًا
# مقلوب الاتجاه أو نوع طرفٍ خاطئ (`ResearchGraph` يرفضهما عند البناء)،
# وتترجم كل استعلامٍ إلى SQL فتُمسك عمودًا لا وجود له.
#
# ولا تُغني عن القاعدة الحيّة ولا تدّعي ذلك: القيود وRLS لا تُختبر إلا هناك.


class _Result:
    """نتيجةٌ مزيَّفة بواجهة `Result` التي يستعملها الجسر وحدها."""

    def __init__(self, rows):
        self._rows = list(rows)

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        return self._rows[0]

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _RecordingSession:
    """جلسةٌ تسجّل كل استعلامٍ وتردّ صفوفًا مُعدّة — ولا تتصل بشيء."""

    def __init__(self, rows: dict[str, list]):
        self.rows = rows
        self.statements: list = []

    async def execute(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        return _Result(self.rows.get(entity.__name__, []))

    def compiled(self) -> list[str]:
        from sqlalchemy.dialects import postgresql

        return [str(stmt.compile(dialect=postgresql.dialect()))
                for stmt in self.statements]


def _populated_rows() -> tuple[dict[str, list], dict[str, uuid.UUID]]:
    """بحثٌ كاملُ الحلقات، صفوفًا لا سطورًا في قاعدة."""
    from athera_api.models.analysis import (
        AnalysisOutputRow,
        AnalysisPlanRow,
        AnalysisRun,
        DataDictionary,
        Dataset,
        DatasetVersionRow,
        PlannedTestRow,
    )
    from athera_api.models.golden_thread import Construct, Method, ThreadElement, Variable
    from athera_api.models.literature import (
        Claim,
        ClaimEvidenceLink,
        EvidenceExcerpt,
        Source,
    )
    from athera_api.models.portfolio import ProjectSource, ResearchProject
    from athera_api.models.publishing import (
        ClaimMemoryLink,
        Manuscript,
        ManuscriptSection,
    )
    from athera_api.models.research import FactCandidate, ResearcherMemory

    ident = {name: uuid.uuid4() for name in (
        "project", "method", "question", "construct", "variable", "dataset",
        "version", "plan", "run", "output", "source", "claim", "excerpt",
        "memory", "candidate", "manuscript", "manuscript_version")}

    project = ResearchProject(id=ident["project"], working_title_ar="أثر التدريب",
                              status="planned")
    method = Method(id=ident["method"], project_id=ident["project"],
                    study_type="quantitative", design_family="correlational",
                    design_label_ar="مسحٌ ارتباطي", sampling_strategy="convenience",
                    sample_size=180, population_ar="معلمو التعليم العام")
    question = ThreadElement(id=ident["question"], project_id=ident["project"],
                             element_type="question", label_ar="ما أثر التدريب؟",
                             ordinal=1)
    construct = Construct(id=ident["construct"], project_id=ident["project"],
                          name_ar="الأداء الوظيفي")
    variable = Variable(id=ident["variable"], project_id=ident["project"],
                        construct_id=ident["construct"], name_ar="الأداء",
                        role="dependent", scale_type="interval",
                        operational_definition_ar="مجموع درجات المقياس")
    dataset = Dataset(id=ident["dataset"], project_id=ident["project"],
                      name_ar="بيانات المسح")
    version = DatasetVersionRow(id=ident["version"], dataset_id=ident["dataset"],
                                state="analysis_locked", label="v3",
                                checksum="a" * 64, freeze_id="FRZ-3",
                                frozen_at=_now())
    plan = AnalysisPlanRow(id=ident["plan"], project_id=ident["project"],
                           version_label="v1")
    run = AnalysisRun(id=ident["run"], plan_id=ident["plan"],
                      dataset_version_id=ident["version"],
                      # **تجميدٌ يخالف تجميد المجموعة الحالي** — البيانات
                      # استُبدلت بعد التشغيلة، وهذا ما تكشفه `RB-LINEAGE-01`.
                      dataset_freeze_id="FRZ-2", tool="python",
                      executed_test_keys=["h1_ttest"], exploratory_test_keys=[],
                      started_at=_now(), status="succeeded")
    planned = PlannedTestRow(plan_id=ident["plan"], test_key="h1_ttest",
                             test_kind="t_test", variables=["perf"])
    dictionary = DataDictionary(dataset_version_id=ident["version"],
                                column_name="perf", variable_id=ident["variable"],
                                scale_type="interval")
    output = AnalysisOutputRow(id=ident["output"], run_id=ident["run"],
                               output_kind="statistic", test_key="h1_ttest",
                               label_ar="فرق المتوسطات",
                               payload={"t": 3.738, "df": 118, "p": 0.003})
    source = Source(id=ident["source"], title="دراسةٌ سابقة", publication_year=2021,
                    retraction_status="none", verification_status="verified")
    project_source = ProjectSource(project_id=ident["project"], source_id=ident["source"],
                                   use_state="saved_only")
    claim = Claim(id=ident["claim"], project_id=ident["project"],
                  text_ar="يرفع التدريب الأداء الوظيفي.", claim_type="empirical",
                  status="draft", is_labelled_inference=False)
    excerpt = EvidenceExcerpt(id=ident["excerpt"], source_id=ident["source"],
                              quote="ارتبط التدريب بالأداء.", locator="ص4 §2",
                              access_basis="open_access_full_text")
    evidence_link = ClaimEvidenceLink(claim_id=ident["claim"], excerpt_id=ident["excerpt"],
                                      source_id=ident["source"],
                                      support_level="contradictory")
    memory = ResearcherMemory(id=ident["memory"], memory_category="project_decision",
                              statement_ar="سؤال البحث معتمَد.", source_type="upload",
                              source_locator="ص1 §1", verification_status="verified")
    memory_link = ClaimMemoryLink(claim_id=ident["claim"], memory_id=ident["memory"],
                                  support_level="direct")
    candidate = FactCandidate(id=ident["candidate"], field_key="questions",
                              memory_category="project_decision",
                              statement_ar="سؤال البحث معتمَد.", quote="سؤال",
                              locator="ص1 §1", status="approved",
                              resulting_memory_id=ident["memory"])
    manuscript = Manuscript(id=ident["manuscript"], project_id=ident["project"],
                            title_ar="ورقة", current_version_id=ident["manuscript_version"])
    section = ManuscriptSection(version_id=ident["manuscript_version"],
                                section_key="results",
                                # لغةٌ سببية في تصميمٍ ارتباطي — تُقرأ من نصّ
                                # المخطوطة نفسه، فيثبت أن مسار النصّ يصل القاعدة.
                                text_ar="يؤدي التدريب إلى ارتفاع الأداء لدى 240 معلمًا.")

    rows = {
        "ResearchProject": [project], "Method": [method], "ThreadElement": [question],
        "Theory": [], "Construct": [construct], "Variable": [variable],
        "Dataset": [dataset], "DatasetVersionRow": [version],
        "AnalysisRun": [(run, plan, version)], "PlannedTestRow": [planned],
        "DataDictionary": [(dictionary, variable)], "AnalysisOutputRow": [output],
        "ProjectSource": [(project_source, source)], "Claim": [claim],
        "ClaimEvidenceLink": [(evidence_link, excerpt, source)],
        "ClaimMemoryLink": [(memory_link, memory)],
        "ResearcherMemory": [(memory, candidate)], "FactCandidate": [candidate],
        "Manuscript": [manuscript], "ManuscriptSection": [section],
    }
    return rows, ident


@pytest.mark.asyncio
async def test_the_whole_bridge_runs_and_builds_a_graph_the_engine_accepts():
    """الجسر يُشغَّل من أوله إلى آخره، والرسم يُبنى ويُقبل.

    و`ResearchGraph` يرفض رابطًا طرفُه غير موجود أو نوعُ طرفه خاطئ — فمرورُ
    البناء هنا إثباتٌ أن الاتجاهات صحيحة، لا مجرّد أن الشيفرة لم تنفجر.
    """
    from athera_api.services.research_assessment import build_project_assessment

    rows, ident = _populated_rows()
    session = _RecordingSession(rows)
    snap = await build_project_assessment(
        session, tenant_id=uuid.uuid4(), project_id=ident["project"])

    assert snap is not None
    graph = snap.assessment.graph
    design = graph.one_of_kind(o.EntityKind.DESIGN)
    assert design.design_family == "correlational" and design.study_type == "quantitative"
    # الإطار الزمني غير مسجَّل في القاعدة — فلا يُشتقّ من عائلة التصميم.
    assert design.temporal_frame == "unknown"

    sample = graph.one_of_kind(o.EntityKind.SAMPLE)
    assert sample.size.is_known and sample.size.value == 180
    assert sample.sampling_strategy == "convenience"
    assert not sample.supports_generalization

    analysis = graph.one_of_kind(o.EntityKind.ANALYSIS)
    assert analysis.test_kind == "t_test" and analysis.outcome_scale == "interval"
    assert analysis.dataset_freeze_id == "FRZ-2"
    # الافتراضات لا تُسجَّل في المستودع — فتُترك فارغة ويُقال «لم تُفحص».
    assert analysis.assumptions == {}

    dataset = graph.one_of_kind(o.EntityKind.DATASET)
    assert dataset.current_freeze_id == "FRZ-3" and dataset.state == "analysis_locked"

    finding = graph.one_of_kind(o.EntityKind.FINDING)
    assert finding.p_value.is_known and finding.p_value.value == 0.003
    assert finding.p_value.source_ref == analysis.id, "قيمة p لا تنسب إلى تشغيلتها"
    assert analysis.id in graph.targets(
        o.RelationKind.FINDING_DERIVED_FROM_ANALYSIS, finding.id)

    claim = graph.one_of_kind(o.EntityKind.CLAIM)
    assert claim.origin == "fact"
    assert len(graph.of_kind(o.EntityKind.EVIDENCE)) == 2
    assert graph.one_of_kind(o.EntityKind.SOURCE).use_state == "saved_only"

    assert snap.assessment.sections["results"].startswith("يؤدي التدريب")
    assert 240.0 in snap.assessment.sample_numbers_in_text
    assert [row.state for row in snap.assessment.fields if row.key == "question"] == ["known"]
    assert snap.contradictions, "دليلٌ مناقض غير معالَج لم يُسجَّل تعارضًا"


@pytest.mark.asyncio
async def test_every_statement_the_bridge_issues_is_scoped_to_this_project():
    """إثباتُ العزل على SQL نفسه، لا على نصّ الشيفرة.

    وكل استعلامٍ إمّا يذكر `project_id`، وإمّا يُحصر بمعرّفٍ **جاء من صفٍّ
    قُرئ بقيد البحث** — وهذه الأعمدة مسمّاة أدناه واحدًا واحدًا، فلا يتسلّل
    استعلامٌ جديدٌ غير مقيَّد تحت عمومية «فيه IN».
    """
    from athera_api.services.research_assessment import build_project_assessment

    derived_scopes = ("project_id", "research_projects.id", "dataset_id",
                      "dataset_version_id", "version_id", "manuscript_id",
                      "plan_id", "run_id", "claim_id")
    rows, ident = _populated_rows()
    session = _RecordingSession(rows)
    await build_project_assessment(session, tenant_id=uuid.uuid4(),
                                   project_id=ident["project"])

    assert len(session.statements) >= 12, "لم تُشغَّل قراءات الجسر كلها"
    for sql in session.compiled():
        where = sql.split("WHERE", 1)[1] if "WHERE" in sql else ""
        assert any(column in where for column in derived_scopes), (
            "استعلامٌ بلا قيدٍ على البحث ولا على معرّفٍ مشتقٍّ منه:\n" + sql)
        assert "tenant_id" in where or "resulting_memory_id" in where, (
            "استعلامٌ بلا قيد المستأجر — وRLS حارسٌ ثانٍ لا أول:\n" + sql)


@pytest.mark.asyncio
async def test_a_real_project_reaches_the_expected_verdicts():
    """الحالة الكاملة أعلاه ومعها أحكامها — منصّةُ تقييمٍ على بيانات لا على خيال.

    والبيانات استُبدلت بعد التشغيلة (`FRZ-2` مقابل `FRZ-3`)، والافتراضات لم
    تُفحص، والمصدر محفوظٌ لا مُدرَج — وثلاثتها أحكامٌ مختلفة لا حكمٌ واحد.
    """
    from athera_api.services.research_assessment import assess, build_project_assessment

    rows, ident = _populated_rows()
    snap = await build_project_assessment(
        _RecordingSession(rows), tenant_id=uuid.uuid4(), project_id=ident["project"])
    report, view = assess(snap)

    # لغةٌ سببية في نصّ المخطوطة وتصميمٌ ارتباطي — والنصّ جاء من أقسام
    # `manuscript_sections`، فالمسار من الجدول إلى الحكم قائمٌ لا موعود.
    assert report.verdict_of("RB-CAUSALITY-01") is Verdict.VIOLATION
    assert report.verdict_of("RB-LINEAGE-01") is Verdict.VIOLATION
    assert report.verdict_of("RB-DESIGN-02") is Verdict.INSUFFICIENT_INFORMATION
    assert report.verdict_of("RB-EVIDENCE-01") is Verdict.VIOLATION
    assert report.verdict_of("RB-FABRICATION-01") is Verdict.PASS
    # **وحجمُ العيّنة مسجَّل، فلا اختلاق.** والرقم المخالف في النصّ (٢٤٠
    # مقابل ١٨٠) عطبُ **تطابق** لا اختلاق، ومفتاحه `sample_size_mismatch`
    # عند فاحص المسودّات — وهذه القاعدة تحرس المخترَع لا المخالف.
    assert report.verdict_of("RB-FABRICATION-02") is Verdict.PASS
    assert report.verdict_of("RB-PROVENANCE-01") is Verdict.PASS
    # مخرَجُ نموذجٍ لا يصل دليلًا: `PROMOTION_PATHS` لا تحوي `model_output`.
    assert report.verdict_of("RB-PROVENANCE-02") is Verdict.NOT_APPLICABLE

    assert report.blocking == () and view.is_advisory_only
    assert view.methodological_alerts and view.needs_review
    assert any("لم تُفحص" in item.detail_ar for item in view.needs_review)


@pytest.mark.asyncio
async def test_a_repeated_key_or_a_twice_cited_source_does_not_break_the_snapshot():
    """صفٌّ مكرَّرٌ في القاعدة لا يُسقط تقييم بحثٍ لا عيب فيه.

    فلا قيد يمنع أن يظهر مفتاح اختبارٍ في قائمتَي التشغيلة معًا، ولا أن
    يسند مصدرٌ واحد ادّعاءً بمقتطفَين. ومعرّفان متطابقان يرفضهما
    `ResearchGraph`، ورابطٌ مكرَّر يُخرج تنبيهين لعطبٍ واحد.
    """
    from athera_api.models.literature import ClaimEvidenceLink, EvidenceExcerpt
    from athera_api.services.research_assessment import build_project_assessment

    rows, ident = _populated_rows()
    run, plan, version = rows["AnalysisRun"][0]
    run.exploratory_test_keys = ["h1_ttest"]
    _link, first, source = rows["ClaimEvidenceLink"][0]
    second = EvidenceExcerpt(id=uuid.uuid4(), source_id=ident["source"],
                             quote="اقتباسٌ ثانٍ من المصدر نفسه.", locator="ص9 §1",
                             access_basis="open_access_full_text")
    rows["ClaimEvidenceLink"].append((
        ClaimEvidenceLink(claim_id=ident["claim"], excerpt_id=second.id,
                          source_id=ident["source"], support_level="direct"),
        second, source))

    snap = await build_project_assessment(
        _RecordingSession(rows), tenant_id=uuid.uuid4(), project_id=ident["project"])

    assert len(snap.assessment.graph.of_kind(o.EntityKind.ANALYSIS)) == 1
    assert len(snap.assessment.graph.links(o.RelationKind.SOURCE_SUPPORTS_CLAIM)) == 1
    assert len(snap.assessment.graph.of_kind(o.EntityKind.EVIDENCE)) == 3


def test_model_output_can_never_be_evidence_through_the_paths_the_bridge_reads():
    """القيدُ هو الحارس هنا لا الشيفرة — ويُقال ذلك صراحةً.

    `researcher_memories.source_type` مقيَّدٌ بمسارات §7.4 الأربعة و
    `model_output` ليست منها، ومقتطفُ المصدر لا يكون مخرَج نموذج. فحكم
    `RB-PROVENANCE-02` على بيانات حقيقية `not_applicable` — وهذا ليس عجزًا
    في القاعدة بل امتناعًا بنيويًّا يجب أن يبقى مرئيًّا لو تغيّر يومًا.
    """
    from athera_api.models.research import PROMOTION_PATHS

    assert "model_output" not in PROMOTION_PATHS
    source = inspect.getsource(bridge._read_sources_claims_and_evidence)
    assert "source_type=memory.source_type" in source
    assert "model_output" in source, "الامتناع البنيوي غير مذكور حيث يقع"


# ───────────────── ٥) العزل على قاعدةٍ حيّة ─────────────────

async def _seed_project(tenant_id: uuid.UUID, user_id: uuid.UUID, *, title: str,
                        sample_size: int, statement: str, claim_text: str,
                        source_title: str) -> dict:
    """بحثٌ كامل الحلقات: منهجٌ وعيّنة وسؤالٌ وذاكرةٌ موثقة وادّعاءٌ ومصدر."""
    from athera_api.db import tenant_session
    from athera_api.models.files import File
    from athera_api.models.golden_thread import Method, ThreadElement
    from athera_api.models.literature import Claim, Source
    from athera_api.models.portfolio import ProjectFile, ProjectSource, ResearchProject
    from athera_api.models.research import (
        DocumentChunk,
        ExtractionRun,
        FactCandidate,
        ResearcherMemory,
    )

    now = _now()
    async with tenant_session(tenant_id, user_id) as session:
        project = ResearchProject(tenant_id=tenant_id, working_title_ar=title,
                                  status="planned", current_gate="G1")
        session.add(project)
        await session.flush()

        method = Method(tenant_id=tenant_id, project_id=project.id,
                        study_type="quantitative", design_family="correlational",
                        sampling_strategy="convenience", sample_size=sample_size,
                        population_ar=f"مجتمع {title}")
        question = ThreadElement(tenant_id=tenant_id, project_id=project.id,
                                 element_type="question", label_ar=f"سؤال {title}",
                                 ordinal=1)
        file = File(tenant_id=tenant_id, storage_key=f"t/{uuid.uuid4()}",
                    original_filename=f"{title}.pdf", content_type="application/pdf",
                    size_bytes=2048, checksum_sha256="0" * 64, classification="C2",
                    status="stored", uploaded_by=user_id)
        session.add_all([method, question, file])
        await session.flush()

        session.add(ProjectFile(tenant_id=tenant_id, project_id=project.id,
                                file_id=file.id, state="active", added_by=user_id))
        run = ExtractionRun(tenant_id=tenant_id, file_id=file.id, extractor="rules",
                            status="completed", started_at=now)
        chunk = DocumentChunk(tenant_id=tenant_id, file_id=file.id, seq=1,
                              text=statement, locator="ص1 §1 ¶1", char_count=len(statement))
        memory = ResearcherMemory(
            tenant_id=tenant_id, memory_category="project_decision",
            statement_ar=statement, source_type="upload", source_file_id=file.id,
            source_locator="ص1 §1 ¶1", source_quote=statement,
            verification_status="verified", verified_by=user_id, verified_at=now)
        source = Source(tenant_id=tenant_id, title=source_title,
                        publication_year=2023, retraction_status="unknown")
        session.add_all([run, chunk, memory, source])
        await session.flush()

        session.add_all([
            FactCandidate(tenant_id=tenant_id, extraction_run_id=run.id, file_id=file.id,
                          chunk_id=chunk.id, memory_category="project_decision",
                          field_key="questions", statement_ar=statement,
                          quote=statement, locator="ص1 §1 ¶1", status="approved",
                          decided_by=user_id, decided_at=now,
                          resulting_memory_id=memory.id),
            ProjectSource(tenant_id=tenant_id, project_id=project.id,
                          source_id=source.id, use_state="saved_only", added_by=user_id),
            Claim(tenant_id=tenant_id, project_id=project.id, text_ar=claim_text,
                  claim_type="empirical", status="draft"),
        ])
        await session.flush()
        return {"project_id": project.id, "method_id": method.id,
                "memory_id": memory.id, "source_id": source.id}


@requires_db
@pytest.mark.asyncio
async def test_an_assessment_never_reads_another_projects_evidence(two_tenants):
    """بحثان لمستأجرٍ واحد — ولا يظهر في تقييم أحدهما شيءٌ من الآخر.

    وRLS لا تحرس هذا: المستأجر يملك البحثين معًا. فالحارس الوحيد هو أن كل
    استعلامٍ في الجسر مقيَّدٌ ببحثه، وهذا ما يُثبَت هنا على صفوفٍ حقيقية.
    """
    from athera_api.db import tenant_session
    from athera_api.services.research_assessment import build_project_assessment

    a = two_tenants["a"]
    first = await _seed_project(
        a["tenant_id"], a["user_id"], title="أثر التدريب في الأداء",
        sample_size=180, statement="سؤال البحث الأول عن أثر التدريب.",
        claim_text="ادّعاء البحث الأول.", source_title="مرجع البحث الأول")
    second = await _seed_project(
        a["tenant_id"], a["user_id"], title="اتجاهات المعلمين نحو التقنية",
        sample_size=412, statement="سؤال البحث الثاني عن الاتجاهات.",
        claim_text="ادّعاء البحث الثاني.", source_title="مرجع البحث الثاني")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        snap = await build_project_assessment(
            session, tenant_id=a["tenant_id"], project_id=first["project_id"])

    assert snap is not None
    ids = {entity.id for entity in snap.assessment.graph.entities}
    assert f"design:{first['method_id']}" in ids
    assert f"design:{second['method_id']}" not in ids, "تصميمُ بحثٍ آخر دخل التقييم"
    assert f"source:{second['source_id']}" not in ids, "مرجعُ بحثٍ آخر دخل التقييم"

    sample = snap.assessment.graph.one_of_kind(o.EntityKind.SAMPLE)
    assert sample.size.value == 180, "حجم العيّنة جاء من بحثٍ آخر"

    backing = {mid for row in snap.assessment.fields for mid in row.backing_memory_ids}
    assert str(first["memory_id"]) in backing, "ذاكرة البحث نفسه لم تُقرأ"
    assert str(second["memory_id"]) not in backing, "ذاكرةُ بحثٍ آخر عُدّت معرفةً هنا"

    claims = [c.text_ar for c in snap.assessment.graph.of_kind(o.EntityKind.CLAIM)]
    assert claims == ["ادّعاء البحث الأول."]


@requires_db
@pytest.mark.asyncio
async def test_a_project_of_another_tenant_is_not_assessed_at_all(two_tenants):
    """مستأجرٌ لا يبني تقييمًا لبحث مستأجرٍ آخر — ولا يعرف أنه موجود."""
    from athera_api.db import tenant_session
    from athera_api.services.research_assessment import build_project_assessment

    a, b = two_tenants["a"], two_tenants["b"]
    theirs = await _seed_project(
        a["tenant_id"], a["user_id"], title="بحثٌ خاص", sample_size=99,
        statement="سؤالٌ خاص.", claim_text="ادّعاءٌ خاص.", source_title="مرجعٌ خاص")

    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        snap = await build_project_assessment(
            session, tenant_id=b["tenant_id"], project_id=theirs["project_id"])
    assert snap is None, "بُني تقييمٌ لبحثٍ ليس للمستأجر"


@requires_db
@pytest.mark.asyncio
async def test_a_trashed_project_is_not_assessed(two_tenants):
    """ما في السلّة ليس قائمًا — وتقييمه يعيده إلى الشاشة من بابٍ خلفي."""
    from sqlalchemy import select

    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.services.research_assessment import build_project_assessment

    a = two_tenants["a"]
    seeded = await _seed_project(
        a["tenant_id"], a["user_id"], title="بحثٌ سيُحذف", sample_size=50,
        statement="سؤال.", claim_text="ادّعاء.", source_title="مرجع")

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        project = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == seeded["project_id"])
        )).scalar_one()
        project.deleted_at = _now()
        project.deleted_by = a["user_id"]
        await session.flush()

    async with tenant_session(a["tenant_id"], a["user_id"]) as session:
        snap = await build_project_assessment(
            session, tenant_id=a["tenant_id"], project_id=seeded["project_id"])
    assert snap is None


@requires_db
@pytest.mark.asyncio
async def test_the_assessment_route_answers_the_owner_and_hides_the_rest(two_tenants):
    """المسار: صاحبُه يراه، وغيره يُجاب 404 — لا 403 ولا 500."""
    import httpx

    from athera_api.db import engine
    from athera_api.main import app
    from athera_api.security import issue_access_token

    a, b = two_tenants["a"], two_tenants["b"]
    seeded = await _seed_project(
        a["tenant_id"], a["user_id"], title="بحثٌ يُقيَّم", sample_size=120,
        statement="سؤال البحث المقيَّم.", claim_text="ادّعاءٌ بلا دليل.",
        source_title="مرجعٌ محفوظ")
    path = f"/api/v1/workspace/projects/{seeded['project_id']}/assessment"

    def client(slot):
        token = issue_access_token(user_id=slot["user_id"], tenant_id=slot["tenant_id"],
                                   roles=["researcher"], mfa_satisfied=True)
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
            headers={"Authorization": f"Bearer {token}", "Accept-Language": "ar"})

    try:
        async with client(a) as http:
            ok = await http.get(path)
            malformed = await http.get("/api/v1/workspace/projects/not-a-uuid/assessment")
            absent = await http.get(
                f"/api/v1/workspace/projects/{uuid.uuid4()}/assessment")
        async with client(b) as http:
            theirs = await http.get(path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as http:
            anonymous = await http.get(path)
    finally:
        await engine.dispose()

    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["is_advisory_only"] is True and body["blocking_count"] == 0
    assert "نسبة" in body["note"]
    assert body["methodological_alerts"], "ادّعاءٌ بلا دليل لم يُنبَّه عليه"
    assert "readiness" not in ok.text and "percent" not in ok.text

    assert anonymous.status_code == 401
    assert malformed.status_code == 422
    assert absent.status_code == 404
    assert theirs.status_code == 404, "بحثُ غيرك يُجاب بجوابٍ يفرّقه عن المعدوم"
