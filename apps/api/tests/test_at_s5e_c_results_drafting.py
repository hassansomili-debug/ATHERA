"""S5E-C — النتائج بوضعٍ صارم.

**السؤال الذي يحرسه هذا الملف:** هل يستطيع رقمٌ لم يُحسب أن يصير نتيجةً في
ورقة؟

فالنتائج أخطر أقسام الورقة: جملةٌ تقول «p = 0.03» تُقرأ حكمًا نهائيًّا، ولا
يملك المحكِّم ولا القارئ وسيلةً لفحصها. ورقمٌ معقول لا يُميَّز عن رقمٍ محسوب
بالقراءة — يميّزهما شيءٌ واحد: أن يوجد مخرَج تحليل يحمله.

**ولا تقريب:** `0.047` و`0.05` ليستا القيمة نفسها. ومن قرّب بينهما جعل رقمًا
لم يُحسب يبدو محسوبًا.
"""
from __future__ import annotations

import uuid

import pytest

from tests.conftest import requires_db

RESULT_FACT = "أظهرت النتائج وجود فروق دالة إحصائيًا عند مستوى 0.05 لصالح المجموعة التجريبية"
SAMPLE_FACT = "بلغت عينة الدراسة 120 طالبًا وُزّعوا بالتساوي على مجموعتين"


def _item(role, statement, memory_id=None):
    from athera_api.services.planning.context import EvidenceItem

    return EvidenceItem(memory_id or uuid.uuid4(), role, None, statement,
                        "project_decision", None, "§النتائج ¶18", statement)


def _output(payload, output_id=None, test_key="t_test"):
    from athera_api.services.publishing.drafting.context import AnalysisOutput

    return AnalysisOutput(output_id=output_id or uuid.uuid4(), run_id=uuid.uuid4(),
                          test_key=test_key, label_ar="اختبار (ت)", payload=payload)


def _context(*items, outputs=(), section="results"):
    from athera_api.services.publishing.drafting.context import DraftingContext

    return DraftingContext(
        tenant_id=uuid.UUID(int=1), project_id=uuid.UUID(int=2),
        manuscript_id=uuid.UUID(int=3), opportunity_id=uuid.UUID(int=4),
        outline_id=None, section_key=section, language="ar",
        purpose_ar="النتائج", items=tuple(items), thread_labels=(),
        missing_roles=(), fingerprint="a" * 64, outputs=tuple(outputs))


def _draft(text, claims=()):
    from athera_api.services.publishing.drafting.contracts import SectionDraft

    return SectionDraft(section_text_ar=text, claims=list(claims))


def _claim(text, *, origin="fact", memory_ids=(), output_ids=()):
    from athera_api.services.publishing.drafting.contracts import DraftedClaim

    return DraftedClaim(text_ar=text, claim_type="empirical", origin=origin,
                        memory_ids=list(memory_ids), analysis_output_ids=list(output_ids))


def _run(draft, context):
    from athera_api.services.publishing.drafting import checks

    return checks.run(draft, context, known_memory_ids=context.memory_ids,
                      known_output_ids=context.output_ids)


def _keys(issues):
    return {i.issue_key for i in issues}


# ══════════ 1. استخراج القيم الإحصائية ══════════

@pytest.mark.parametrize(("text", "kind", "value"), [
    ("p = 0.003", "p_value", "0.003"),
    ("p < .05", "p_value", ".05"),
    ("t(118) = 4.21", "t_statistic", "4.21"),
    ("F(1, 118) = 17.7", "f_statistic", "17.7"),
    ("β = 0.42", "beta", "0.42"),
    ("R² = 0.31", "r_squared", "0.31"),
    ("بلغ مربع إيتا 0.42", "eta_squared", "0.42"),
    ("M = 24.6", "mean", "24.6"),
    ("SD = 3.1", "std_dev", "3.1"),
    ("حقق 62% من الطلاب", "percentage", "62"),
    ("المتوسط الحسابي = 18.4", "mean", "18.4"),
])
def test_a_publication_statistic_is_detected(text, kind, value):
    from athera_api.services.publishing.drafting import numbers

    hits = {(h.kind, h.value) for h in numbers.find(text)}
    assert (kind, value) in hits, hits


def test_arabic_indic_digits_are_read_as_numbers():
    """المنتج ثنائي اللغة، والباحث يكتب بالنظامين."""
    from athera_api.services.publishing.drafting import numbers

    hits = numbers.find("p = ٠٫٠٣")
    assert hits and hits[0].kind == "p_value" and hits[0].value == "0.03"


def test_a_sample_size_is_not_a_statistical_result():
    """§5 — «بلغ حجم العينة 120» واقعة عيّنة، لا مخرَج تحليل."""
    from athera_api.services.publishing.drafting import numbers

    assert numbers.find(SAMPLE_FACT) == []


def test_a_bare_significance_claim_is_a_statistical_claim():
    """«فروق دالة إحصائيًّا» يقرّر نتيجة اختبار فرضية ولو خلا من رقم.

    واشتراطُ رقمٍ ظاهر يجعل حذف الرقم وسيلةً لتمرير الادعاء نفسه.
    """
    from athera_api.services.publishing.drafting import numbers

    hits = numbers.find("كان الفرق دالًا إحصائيًّا")
    assert any(h.kind == "significance" and h.is_bare_significance for h in hits)


# ══════════ 2. لا تقريب ══════════

def test_a_near_value_is_not_the_same_result():
    """§20 — `0.047` و`0.05` ليستا واحدة."""
    from athera_api.services.publishing.drafting import numbers

    hit = numbers.find("p = 0.05")[0]
    assert numbers.supports(hit, {"p_value": 0.05})
    assert not numbers.supports(hit, {"p_value": 0.047})
    assert not numbers.supports(hit, {"p_value": 0.0501})


def test_equivalent_notations_of_the_same_value_match():
    """`.05` و`0.05` و`0.050` قيمة واحدة — والتمثيل ليس القيمة."""
    from athera_api.services.publishing.drafting import numbers

    hit = numbers.find("p = .05")[0]
    for stored in (0.05, "0.050", ".05"):
        assert numbers.supports(hit, {"p": stored}), stored


def test_a_value_nested_deep_in_the_payload_is_found():
    from athera_api.services.publishing.drafting import numbers

    hit = numbers.find("t(118) = 4.21")[0]
    assert numbers.supports(hit, {"tests": [{"statistic": {"t": 4.21}}]})


# ══════════ 3. الحجب قبل الإرسال (§21) ══════════

def test_an_unsupported_statistic_is_withheld_from_the_model():
    """لا يُدعى النموذج إلى إعادة رقمٍ سيرفضه المدقّق بعد قليل."""
    context = _context(_item("result", RESULT_FACT))
    sent = context.model_context()
    assert len(sent) == 1
    assert "دالة إحصائيًا" not in sent[0]["statement_ar"]
    assert "غير مسنَدة بمخرَج تحليل" in sent[0]["statement_ar"]
    # والمعنى الذي يسنده الدليل باقٍ.
    assert "لصالح المجموعة التجريبية" in sent[0]["statement_ar"]


def test_the_methods_section_is_not_redacted():
    """الحجب للنتائج وحدها — والمنهجية تصف إجراءً لا تُبلّغ نتيجة."""
    context = _context(_item("methodology", RESULT_FACT), section="method")
    assert "دالة إحصائيًا" in context.model_context()[0]["statement_ar"]


def test_the_redaction_policy_names_the_sections_it_applies_to():
    """الحجب معلَنٌ بقسمه، لا سلوكٌ عامّ يفاجئ من يقرأ."""
    from athera_api.services.publishing.drafting import context as ctx

    assert ctx.REDACT_STATISTICS_IN == frozenset({"results"})


# ══════════ 4. الرفض الصارم ══════════

def test_a_statistic_without_any_analysis_output_is_refused():
    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft("بلغت قيمة (ت) 4.21 عند مستوى دلالة p = 0.003"), context)
    assert "statistic_without_analysis_output" in _keys(issues)


def test_a_significance_claim_without_an_output_is_refused():
    """§6 — «وجود فرق» مسموح؛ «دالّ إحصائيًّا» ليس كذلك بلا سند."""
    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft("أظهرت النتائج أن الفرق كان دالًا إحصائيًّا"), context)
    assert "significance_without_analysis_output" in _keys(issues)


def test_the_supportable_part_of_the_same_finding_passes():
    """§6 — الجزء الذي يسنده الدليل يُكتب، والباقي يبقى ناقصًا."""
    item = _item("result", RESULT_FACT)
    context = _context(item)
    issues = _run(_draft("أظهرت النتائج وجود فروق لصالح المجموعة التجريبية",
                         [_claim("وجود فروق لصالح المجموعة التجريبية",
                                 memory_ids=[str(item.memory_id)])]), context)
    assert _keys(issues) == set(), [i.issue_key for i in issues]


def test_a_statistic_backed_by_the_exact_output_passes():
    """المسار الموجب: القيمة في المخرَج المرتبط بها."""
    item = _item("result", RESULT_FACT)
    output = _output({"test": "independent_t", "t": 4.21, "p": 0.003, "df": 118})
    context = _context(item, outputs=[output])
    claim = _claim("بلغت قيمة t(118) = 4.21 بمستوى p = 0.003",
                   memory_ids=[str(item.memory_id)],
                   output_ids=[str(output.output_id)])
    issues = _run(_draft("بلغت قيمة t(118) = 4.21 بمستوى p = 0.003", [claim]), context)
    assert _keys(issues) == set(), [i.issue_key for i in issues]


def test_a_wrong_value_linked_to_a_real_output_is_refused():
    """§7 — المعرّف إشارةٌ لا سلطة: القيمة تُقابَل بالمخرَج."""
    item = _item("result", RESULT_FACT)
    output = _output({"t": 4.21, "p": 0.003})
    context = _context(item, outputs=[output])
    claim = _claim("بلغت قيمة p = 0.05", memory_ids=[str(item.memory_id)],
                   output_ids=[str(output.output_id)])
    issues = _run(_draft("بلغت قيمة p = 0.05", [claim]), context)
    assert "statistic_value_mismatch" in _keys(issues)


def test_an_output_id_never_supplied_is_refused():
    item = _item("result", RESULT_FACT)
    context = _context(item, outputs=[])
    claim = _claim("بلغت قيمة p = 0.003", memory_ids=[str(item.memory_id)],
                   output_ids=[str(uuid.uuid4())])
    issues = _run(_draft("بلغت قيمة p = 0.003", [claim]), context)
    assert "claim_references_unknown_evidence" in _keys(issues)
    assert "statistic_without_analysis_output" in _keys(issues)


def test_an_unrelated_output_does_not_ground_a_different_statistic():
    """مخرَجٌ حقيقي لاختبارٍ آخر لا يسند رقمًا ليس فيه."""
    item = _item("result", RESULT_FACT)
    output = _output({"chi_square": 9.8, "p": 0.002}, test_key="chi_square")
    context = _context(item, outputs=[output])
    claim = _claim("بلغ مربع إيتا 0.42", memory_ids=[str(item.memory_id)],
                   output_ids=[str(output.output_id)])
    issues = _run(_draft("بلغ مربع إيتا 0.42", [claim]), context)
    assert "statistic_value_mismatch" in _keys(issues)


def test_the_eta_squared_case_still_refuses_invention():
    """§35 — المشروع لا يحمل قيمة مربع إيتا موثقة، فلا تظهر."""
    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft("وبلغ حجم الأثر مربع إيتا 0.42 وهو أثر كبير"), context)
    assert "statistic_without_analysis_output" in _keys(issues)


# ══════════ 5. النتائج وصفٌ لا تفسير ══════════

@pytest.mark.parametrize("interpretation", [
    "ويُعزى هذا الفرق إلى فاعلية التعلّم النشط",
    "مما يدل على أن الاستراتيجية أكثر فاعلية",
    "وتتفق هذه النتيجة مع ما توصّلت إليه دراسات سابقة",
    "ونوصي باعتماد الاستراتيجية في المدارس",
])
def test_interpretation_inside_results_is_flagged(interpretation):
    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft(f"أظهرت النتائج وجود فروق. {interpretation}"), context)
    assert "interpretation_in_results" in _keys(issues)


def test_a_proposal_presented_as_a_result_is_flagged():
    item = _item("result", RESULT_FACT)
    context = _context(item)
    issues = _run(_draft("أظهرت النتائج وجود فروق",
                         [_claim("قد يكون البرنامج مفيدًا", origin="proposal")]), context)
    assert "proposal_in_results" in _keys(issues)


def test_a_descriptive_result_sentence_is_not_flagged_as_interpretation():
    """الحارس الذي يعاقب الوصف الصحيح أسوأ من الذي يفوّت تفسيرًا."""
    item = _item("result", RESULT_FACT)
    context = _context(item)
    issues = _run(_draft("أظهرت النتائج وجود فروق لصالح المجموعة التجريبية",
                         [_claim("وجود فروق", memory_ids=[str(item.memory_id)])]),
                  context)
    assert "interpretation_in_results" not in _keys(issues)


def test_a_fabricated_citation_in_results_is_refused():
    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft("وتتوافق النتيجة مع (العتيبي، 2021)"), context)
    assert "fabricated_citation" in _keys(issues)


# ══════════ 6. الفشل المغلق ══════════

def test_fabrication_issues_are_named_and_separated_from_warnings():
    """§25 — الاختلاق لا يصير نصًّا؛ وبقية الكشوفات تحذيرات على نصٍّ قائم."""
    from athera_api.services.publishing.drafting import checks

    assert "statistic_without_analysis_output" in checks.FABRICATION_ISSUES
    assert "statistic_value_mismatch" in checks.FABRICATION_ISSUES
    assert "claim_references_unknown_evidence" in checks.FABRICATION_ISSUES
    assert "fabricated_citation" in checks.FABRICATION_ISSUES
    # والتفسير تحذير: نصٌّ صحيح في غير موضعه، لا واقعة مخترَعة.
    assert "interpretation_in_results" not in checks.FABRICATION_ISSUES
    assert "causal_language_beyond_design" not in checks.FABRICATION_ISSUES


def test_the_router_refuses_before_persisting():
    import inspect

    from athera_api.routers import manuscript_drafting as drafting

    source = inspect.getsource(drafting.draft_section)
    assert source.index("draft_checks.fabrications") < source.index("generate.persist")
    assert "drafting.unsupported_content" in source


# ══════════ 7. المقتطف يُستخرج ولا يكتبه النموذج ══════════

def test_the_statistic_excerpt_comes_from_the_claim_text():
    import inspect

    from athera_api.services.publishing.drafting import generate

    source = inspect.getsource(generate.persist)
    assert "numbers.find(drafted.text_ar)" in source
    assert "statistic_excerpt=excerpt" in source


# ══════════ 8. تأهيل المخرجات: الملكية والاكتمال ══════════

def test_output_eligibility_proves_ownership_through_the_chain():
    import inspect

    from athera_api.services.publishing.drafting import context as ctx

    source = inspect.getsource(ctx.eligible_outputs)
    for link in ("AnalysisRun.id == AnalysisOutputRow.run_id",
                 "AnalysisPlanRow.id == AnalysisRun.plan_id",
                 "ResearchProject.id == AnalysisPlanRow.project_id"):
        assert link in source, link
    for scope in ("AnalysisOutputRow.tenant_id == tenant_id",
                  "AnalysisRun.tenant_id == tenant_id",
                  "AnalysisPlanRow.tenant_id == tenant_id",
                  "ResearchProject.tenant_id == tenant_id"):
        assert scope in source, scope
    assert 'AnalysisRun.status == "completed"' in source
    assert "AnalysisRun.is_reproducible.is_(True)" in source


@requires_db
@pytest.mark.asyncio
async def test_a_non_reproducible_run_never_supports_publication(two_tenants):
    """§9 — نتيجةٌ لا يستطيع صاحبها إعادة إنتاجها لا تُبنى عليها ورقة."""
    from athera_api.db import tenant_session
    from athera_api.services.publishing.drafting import context as ctx

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id, _out = await _seed_analysis(tid, uid, reproducible=False)

    async with tenant_session(tid, uid) as session:
        outputs = await ctx.eligible_outputs(session, tenant_id=tid, project_id=project_id)
    assert outputs == (), "مخرَج تشغيلة غير قابلة لإعادة الإنتاج دخل النشر"


@requires_db
@pytest.mark.asyncio
async def test_a_reproducible_completed_run_is_eligible(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.services.publishing.drafting import context as ctx

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    project_id, output_id = await _seed_analysis(tid, uid, reproducible=True)

    async with tenant_session(tid, uid) as session:
        outputs = await ctx.eligible_outputs(session, tenant_id=tid, project_id=project_id)
    assert [o.output_id for o in outputs] == [output_id]
    assert outputs[0].payload.get("p") == 0.003


@requires_db
@pytest.mark.asyncio
async def test_an_output_from_another_project_is_not_eligible(two_tenants):
    """§10 — الملكية بالسلسلة لا بالمعرّف."""
    from athera_api.db import tenant_session
    from athera_api.models.portfolio import ResearchProject
    from athera_api.services.publishing.drafting import context as ctx

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    _project, _output = await _seed_analysis(tid, uid, reproducible=True)

    async with tenant_session(tid, uid) as session:
        other = ResearchProject(tenant_id=tid, working_title_ar="مشروع آخر")
        session.add(other)
        await session.flush()
        other_id = other.id

    async with tenant_session(tid, uid) as session:
        outputs = await ctx.eligible_outputs(session, tenant_id=tid, project_id=other_id)
    assert outputs == ()


@requires_db
@pytest.mark.asyncio
async def test_another_tenant_sees_no_analysis_output(two_tenants):
    from athera_api.db import tenant_session
    from athera_api.services.publishing.drafting import context as ctx

    a, b = two_tenants["a"], two_tenants["b"]
    project_id, _output = await _seed_analysis(a["tenant_id"], a["user_id"],
                                               reproducible=True)
    async with tenant_session(b["tenant_id"], b["user_id"]) as session:
        outputs = await ctx.eligible_outputs(session, tenant_id=b["tenant_id"],
                                             project_id=project_id)
    assert outputs == ()


async def _seed_analysis(tid, uid, *, reproducible: bool):
    """مجموعة بيانات وخطة وتشغيلة ومخرَج — عبر النماذج القائمة.

    و`is_reproducible` يُضبط كما يحسبه المنتج: بيانٌ كامل وبيانات مجمَّدة.
    """
    import datetime as dt

    from athera_api.db import tenant_session
    from athera_api.models.analysis import (
        AnalysisOutputRow,
        AnalysisPlanRow,
        AnalysisRun,
        DatasetRow,
        DatasetVersionRow,
    )
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="مشروع تحليل")
        session.add(project)
        await session.flush()
        dataset = DatasetRow(tenant_id=tid, project_id=project.id,
                             name_ar="بيانات اصطناعية", classification="C3")
        session.add(dataset)
        await session.flush()
        version = DatasetVersionRow(
            tenant_id=tid, dataset_id=dataset.id, state="cleaned", label="v1",
            checksum="a" * 64, freeze_id="frz-test" if reproducible else None)
        session.add(version)
        await session.flush()
        plan = AnalysisPlanRow(tenant_id=tid, project_id=project.id, version_label="v1",
                               lock_hash="b" * 64, approved_by=uid,
                               approved_at=dt.datetime.now(dt.UTC))
        session.add(plan)
        await session.flush()
        run = AnalysisRun(
            tenant_id=tid, plan_id=plan.id, dataset_version_id=version.id,
            dataset_freeze_id=version.freeze_id or "none", tool="python",
            code_hash="c" * 64 if reproducible else None,
            runtime="python 3.12" if reproducible else None,
            packages={"scipy": "1.14"} if reproducible else None,
            random_seed=7 if reproducible else None,
            is_reproducible=reproducible,
            missing_manifest_fields=[] if reproducible else ["code_hash"],
            status="completed", started_at=dt.datetime.now(dt.UTC),
            finished_at=dt.datetime.now(dt.UTC))
        session.add(run)
        await session.flush()
        output = AnalysisOutputRow(
            tenant_id=tid, run_id=run.id, output_kind="statistic",
            test_key="independent_t", label_ar="اختبار (ت) للعينات المستقلة",
            payload={"t": 4.21, "df": 118, "p": 0.003})
        session.add(output)
        await session.flush()
        return project.id, output.id
