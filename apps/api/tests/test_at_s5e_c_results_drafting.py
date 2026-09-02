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
    # ولا علامة تحلّ محلّه: علامةٌ تقول «هنا شيءٌ حُجب» تُفشي ما تحجبه.
    assert "[غير متاح]" not in sent[0]["statement_ar"]
    # والمعنى الذي يسنده الدليل باقٍ.
    assert "لصالح المجموعة التجريبية" in sent[0]["statement_ar"]


def test_the_methods_section_is_not_redacted():
    """الحجب للنتائج وحدها — والمنهجية تصف إجراءً لا تُبلّغ نتيجة."""
    context = _context(_item("methodology", RESULT_FACT), section="method")
    assert "دالة إحصائيًا" in context.model_context()[0]["statement_ar"]


def test_the_redaction_policy_follows_the_evidence_that_flows_in():
    """الحجب يتبع الأدلة: كل قسمٍ تصله أدلةُ نتائج يُحجب عنه الادعاء
    الإحصائي الذي لا يسنده مخرَج.

    وكان مقصورًا على «النتائج» وحدها، فحُجبت الخاتمة في الإنتاج بعد أن
    أعادت الادعاء نفسه من الدليل نفسه.
    """
    from athera_api.services.publishing.drafting import context as ctx
    from athera_api.services.publishing.drafting import policy

    assert "results" in ctx.REDACT_STATISTICS_IN
    assert "conclusion" in ctx.REDACT_STATISTICS_IN
    assert "method" not in ctx.REDACT_STATISTICS_IN
    assert ctx.REDACT_STATISTICS_IN == frozenset(
        key for key, spec in policy.POLICIES.items() if "result" in spec.roles)


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
        Dataset,
        DatasetVersionRow,
    )
    from athera_api.models.portfolio import ResearchProject

    async with tenant_session(tid, uid) as session:
        project = ResearchProject(tenant_id=tid, working_title_ar="مشروع تحليل")
        session.add(project)
        await session.flush()
        dataset = Dataset(tenant_id=tid, project_id=project.id,
                             name_ar="بيانات اصطناعية", classification="C3")
        session.add(dataset)
        await session.flush()
        # قيود §17.2 و§17.3 تُحترم كما تفرضها القاعدة، ولا يُلتفّ عليها:
        # الخام بلا أصل، والمشتقّ يعرف أصله وسبب تغييره، والتجميد له معرّف
        # وفاعل وتاريخ أو ليس تجميدًا.
        raw = DatasetVersionRow(
            tenant_id=tid, dataset_id=dataset.id, state="raw", label="raw",
            checksum="0" * 64)
        session.add(raw)
        await session.flush()
        # **والتجميد في الحالتين.** مشغّلٌ في القاعدة يمنع تشغيل تحليل على
        # بيانات غير مجمَّدة أصلًا (§17.3) — فالتشغيلة غير القابلة لإعادة
        # الإنتاج ليست تشغيلةً على بيانات سائلة، بل تشغيلةٌ نقص بيانها:
        # بلا بصمة كود ولا بيئة ولا حزم ولا بذرة عشوائية.
        version = DatasetVersionRow(
            tenant_id=tid, dataset_id=dataset.id, state="cleaned", label="v1",
            checksum="a" * 64, parent_version_id=raw.id,
            change_note_ar="تنظيف اصطناعي للاختبار",
            freeze_id=f"frz-{uuid.uuid4().hex[:8]}",
            frozen_at=dt.datetime.now(dt.UTC), frozen_by=uid)
        session.add(version)
        await session.flush()
        plan = AnalysisPlanRow(tenant_id=tid, project_id=project.id, version_label="v1",
                               lock_hash="b" * 64, approved_by=uid,
                               approved_at=dt.datetime.now(dt.UTC))
        session.add(plan)
        await session.flush()
        run = AnalysisRun(
            tenant_id=tid, plan_id=plan.id, dataset_version_id=version.id,
            dataset_freeze_id=version.freeze_id, tool="python",
            code_hash="c" * 64 if reproducible else None,
            runtime="python 3.12" if reproducible else None,
            packages={"scipy": "1.14"} if reproducible else None,
            random_seed=7 if reproducible else None,
            # §18.1 — «قابل لإعادة الإنتاج» يعني بيانًا كاملًا **وبصمة**،
            # والقاعدة تفرض ذلك بقيد لا بالتوثيق وحده.
            fingerprint="d" * 64 if reproducible else None,
            is_reproducible=reproducible,
            missing_manifest_fields=[] if reproducible else
            ["code_hash", "runtime", "packages", "random_seed"],
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


# ══════════ 9. التعليمات: النقص الصادق مخرَجٌ مقبول ══════════

def test_the_results_rules_are_added_not_substituted():
    """قواعد القسم تُضاف إلى العامة — فلا يسقط منعُ الاختلاق بفتح قسم."""
    from athera_api.services.publishing.drafting import generate

    assert generate.instruction_for("method") == generate.INSTRUCTION
    results = generate.instruction_for("results")
    assert results.startswith(generate.INSTRUCTION)
    assert len(results) > len(generate.INSTRUCTION)


def test_the_results_rules_forbid_reconstructing_withheld_values():
    """أول نداء إنتاجي أعاد بناء دلالةٍ حُجبت — فالمنع صار مكتوبًا."""
    from athera_api.services.publishing.drafting import generate

    rules = generate.SECTION_RULES["results"]
    assert "[غير متاح]" in rules
    assert "لا تعِد بناءه" in rules
    # ولا يشتقّ رقمًا بالحساب.
    assert "60 في كل مجموعة" in rules
    # والنقص الصادق مخرَجٌ مقبول (§26).
    assert "قسمٌ ناقص صادق" in rules


def test_redaction_leaves_no_trace_the_model_can_read_or_copy():
    """العلامة المحايدة كانت أهون من الوصفية — ولا تزال تقول «هنا شيءٌ حُجب».

    فيعيد النموذج بناءه من السياق، وينسخ العلامة نفسها إلى نصّ المخطوطة.
    وقد وقع الاثنان في أول نداء إنتاجي للخاتمة.
    """
    from athera_api.services.publishing.drafting import numbers
    from athera_api.services.publishing.vocab import INTERNAL_MARKERS

    body, removed = numbers.redact(RESULT_FACT)
    assert removed, "لم يُحجب شيء"
    for marker in INTERNAL_MARKERS:
        assert marker not in body, marker
    assert "دالة إحصائيًا" not in body
    assert "لصالح المجموعة التجريبية" in body


def test_no_outputs_means_no_output_block_content():
    import json

    from athera_api.services.publishing.drafting import generate

    context = _context(_item("result", RESULT_FACT))
    payload = json.loads(generate.build_prompt(context))
    assert payload["analysis_outputs"] == []
    assert payload["allowed_analysis_output_ids"] == []


def test_the_rules_forbid_copying_the_redaction_marker():
    """العلامة أداةٌ داخلية — ولا موضع لها في نصّ ورقة."""
    from athera_api.services.publishing.drafting import generate

    rules = generate.SECTION_RULES["results"]
    assert "لا تنسخ العلامة [غير متاح]" in rules
    assert "فاذكرها" in rules and "ولا تقرّبها" in rules


# ══════════ 11. أرقام العيّنة: توحيدٌ ونزعُ الإحصائي ══════════

@pytest.mark.parametrize("text", [
    "بلغت قيمة (ت) ٣٫٠٨",          # فاصلة عشرية عربية
    "t(118) = 3.08",
    "عند مستوى p = 0.003",
    "بلغ مربع إيتا 0.106",
    "p = 0,003",                    # فاصلة لاتينية — وهي ما أفلت أول علاج
    "قيمة (ت) 3,08",
    "مستوى الدلالة 0.003",          # كسرٌ بلا رمز إحصائي يسبقه
])
def test_a_decimal_fragment_is_never_read_as_a_sample_number(text):
    """`\\d` في بايثون يطابق الأرقام العربية الهندية، والفاصلة `٫` ليست في
    نظرة الخلف — فكان `٣٫٠٨` يُقرأ رقمين ويُبلَّغ عن «٠٨» رقمَ عيّنة مخترَعًا.
    """
    from athera_api.services.publishing.drafting import checks

    assert checks._sample_numbers(text) == set(), text


def test_a_real_sample_number_is_still_read():
    """ولا يُرخى الحارس: رقمٌ صحيح يُقرأ، ورقمٌ مشتقّ بالحساب يُكشف."""
    from athera_api.services.publishing.drafting import checks

    assert checks._sample_numbers(SAMPLE_FACT) == {"120"}
    assert checks._sample_numbers("120 طالبًا، 60 في كل مجموعة") == {"120", "60"}


def test_a_statistic_is_not_reported_twice_under_two_names():
    """قيمةٌ إحصائية تُفحص بفحصها — ومرورها في فحص العيّنة يجعلها كشفين."""
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("result", RESULT_FACT))
    issues = checks.run(_draft("بلغ مربع إيتا 0.106"), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=frozenset())
    keys = [i.issue_key for i in issues]
    assert "statistic_without_analysis_output" in keys
    assert "unsupported_sample_number" not in keys


# ══════════ 9. العطب الإنتاجي: قيمة حقيقية علّق النموذج مخرَجها في مكانٍ آخر ══════════
#
# المخرَج الحقيقي في مشروع التحقق يحمل `t = 3.738 · df = 118 · η² = 0.106`.
# وكتب النموذج «η² = 0.106» في نصّ القسم، وعلّق معرّف المخرَج على ادعاءٍ آخر
# لا يحمل هذه السلسلة. فرفضه الفحص بوصفه رقمًا بلا مخرَج — **وهو رقم حقيقي**.
#
# والعطب في الربط لا في العلم. ورسالة الرفض كانت تقول العكس.

REAL_PAYLOAD = {
    "test": "independent_samples_t", "t": 3.738, "df": 118, "eta_squared": 0.106,
    "n_control": 60, "n_treatment": 60, "mean_control": 62.66, "mean_treatment": 68.9,
    "sd_control": 9.05, "sd_treatment": 6.75,
}


def test_a_real_statistic_is_not_called_unsupported_when_the_claim_binding_is_elsewhere():
    """العطب الإنتاجي حرفيًّا — ويجب أن يفشل قبل الإصلاح."""
    from athera_api.services.publishing.drafting import checks

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    prose = "بلغ حجم الأثر η² = 0.106."
    # النموذج علّق المخرَج على ادعاءٍ لا يحمل السلسلة.
    elsewhere = _claim("أظهرت المقارنة تفوّق المجموعة التجريبية",
                       output_ids=[str(output.output_id)])
    issues = checks.run(_draft(prose, [elsewhere]), context,
                        known_memory_ids=context.memory_ids,
                        known_output_ids=context.output_ids)
    keys = _keys(issues)
    # الرقم حقيقي: فلا يُقال إنه بلا مخرَج.
    assert "statistic_without_analysis_output" not in keys, keys
    # لكنه بلا إسناد بنيوي: ويُقال ذلك باسمه.
    assert "statistic_without_claim_binding" in keys, keys


def test_the_binder_creates_an_atomic_claim_from_the_exact_span():
    """§6 — فهرسةُ نصٍّ قائم: الجملة تُقتطع كما هي، حرفًا بحرف."""
    from athera_api.services.publishing.drafting import generate

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    prose = "أظهرت النتائج تفوّق المجموعة التجريبية. وبلغ حجم الأثر η² = 0.106."
    draft = _draft(prose, [_claim("تفوّق المجموعة التجريبية",
                                  output_ids=[str(output.output_id)])])
    bound, _dropped = generate.ground(draft, context)
    created = generate.bind_statistics(draft, context, bound)

    assert created == 1
    atomic = bound[-1]
    assert atomic.derived_from_section_span is True
    assert atomic.output_ids == [str(output.output_id)]
    # **حرفيًّا من النصّ** — ولا حرف زيد ولا نقص.
    assert atomic.claim.text_ar in prose
    assert "η² = 0.106" in atomic.claim.text_ar


def test_binding_closes_the_production_false_negative():
    """بعد الربط: لا كشف حاجب على قيمة حقيقية."""
    from athera_api.services.publishing.drafting import checks, generate

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    prose = "وبلغ حجم الأثر η² = 0.106."
    draft = _draft(prose, [_claim("تفوّق المجموعة التجريبية",
                                  output_ids=[str(output.output_id)])])
    bound, _ = generate.ground(draft, context)
    generate.bind_statistics(draft, context, bound)

    verified = draft.model_copy(update={"claims": [
        b.claim.model_copy(update={"memory_ids": b.memory_ids,
                                   "analysis_output_ids": b.output_ids})
        for b in bound]})
    issues = checks.run(verified, context, known_memory_ids=context.memory_ids,
                        known_output_ids=context.output_ids)
    assert _keys(issues) == set(), [i.issue_key for i in issues]


def test_an_existing_claim_carrying_the_statistic_is_reused_not_duplicated():
    """§6 — إن وُجد ادعاءٌ يحمل القيمة فهو الأولى، ولا يُصنع ثانٍ."""
    from athera_api.services.publishing.drafting import generate

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    prose = "وبلغ حجم الأثر η² = 0.106."
    draft = _draft(prose, [_claim("وبلغ حجم الأثر η² = 0.106")])
    bound, _ = generate.ground(draft, context)
    created = generate.bind_statistics(draft, context, bound)

    assert created == 0, "أُنشئ ادعاء ذرّي مع وجود ادعاء يحمل القيمة"
    assert bound[0].output_ids == [str(output.output_id)]


def test_two_statistics_in_one_sentence_become_two_atomic_claims():
    """§7 — مخرَجٌ واحد بعدة نتائج: ادعاءٌ ذرّي لكل قيمة، فلا يضعف الإسناد."""
    from athera_api.services.publishing.drafting import generate

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    prose = "بلغت قيمة t(118) = 3.738 وحجم الأثر η² = 0.106."
    draft = _draft(prose, [])
    bound, _ = generate.ground(draft, context)
    created = generate.bind_statistics(draft, context, bound)

    assert created == 2, [b.claim.text_ar for b in bound]
    assert all(b.output_ids == [str(output.output_id)] for b in bound)


# ══════════ 10. المطابقة بالنوع والأبعاد ══════════

@pytest.mark.parametrize(("prose", "grounded"), [
    ("η² = 0.106", True),
    ("η² = 0.105", False),
    ("η² = 0.11", False),
    ("t(118) = 3.738", True),
    ("t(118) = 3.739", False),
    ("t(117) = 3.738", False),
    ("M = 62.66", True),
    ("SD = 6.75", True),
])
def test_exact_kind_value_and_dimension_matching(prose, grounded):
    from athera_api.services.publishing.drafting import checks

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    hit = __import__("athera_api.services.publishing.drafting.numbers",
                     fromlist=["find"]).find(prose)[0]
    assert bool(checks.outputs_carrying(hit, context)) is grounded


def test_a_matching_decimal_of_another_metric_does_not_ground_the_statistic():
    """§4 — `p = 0.106` ليس مسنَدًا لأن `η² = 0.106` موجود."""
    from athera_api.services.publishing.drafting import checks, numbers

    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    hit = numbers.find("p = 0.106")[0]
    assert checks.outputs_carrying(hit, context) == []


def test_no_fabricated_p_value_even_with_a_real_t_statistic():
    """§18 — النموذج لا يحسب الدلالة، والمخرَج لا يحمل قيمة p."""
    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    issues = _run(_draft("بلغت t(118) = 3.738 وكان الفرق دالًا عند p < .05"), context)
    assert "statistic_without_analysis_output" in _keys(issues)


# ══════════ 11. الغموض يفشل مغلقًا ══════════

def test_two_outputs_carrying_the_same_statistic_fail_closed():
    """§9 — لا يُختار أحدهما اعتباطًا: إسنادٌ غير محدَّد ليس إسنادًا."""
    first = _output({"eta_squared": 0.106, "test": "anova_a"})
    second = _output({"eta_squared": 0.106, "test": "anova_b"})
    context = _context(_item("result", RESULT_FACT), outputs=[first, second])
    issues = _run(_draft("وبلغ حجم الأثر η² = 0.106."), context)
    assert "statistic_output_ambiguous" in _keys(issues)


def test_the_binder_creates_nothing_when_provenance_is_ambiguous():
    from athera_api.services.publishing.drafting import generate

    first = _output({"eta_squared": 0.106})
    second = _output({"eta_squared": 0.106})
    context = _context(_item("result", RESULT_FACT), outputs=[first, second])
    draft = _draft("وبلغ حجم الأثر η² = 0.106.")
    bound, _ = generate.ground(draft, context)
    assert generate.bind_statistics(draft, context, bound) == 0


# ══════════ 12. تسرّب علامة الحجب الداخلية ══════════

@pytest.mark.parametrize("marker", [
    "[غير متاح]",
    "[قيمة إحصائية غير متاحة بنيويًّا]",
    "[دلالة إحصائية غير مسنَدة بمخرَج تحليل]",
])
def test_an_internal_marker_in_manuscript_prose_is_blocking(marker):
    """§11 — لغةٌ بيننا وبين النموذج، لا نصٌّ يُنشر."""
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("result", RESULT_FACT))
    issues = _run(_draft(f"أظهرت النتائج وجود فروق {marker} لصالح التجريبية"), context)
    assert "internal_redaction_marker_leak" in _keys(issues)
    assert "internal_redaction_marker_leak" in checks.FABRICATION_ISSUES


def test_the_marker_is_not_silently_stripped():
    """تنظيفه صامتًا يجعلنا ندّعي أن المخرَج مرّ كما هو."""
    import inspect

    from athera_api.routers import manuscript_drafting as drafting

    source = inspect.getsource(drafting.draft_section)
    assert ".replace(" not in source, "المسودة تُنظَّف بدل أن تُرفض"


# ══════════ 13. المسار السردي لا ينكسر ══════════

def test_a_narrative_result_needs_no_analysis_output():
    """§16 — لا تُدفع كل جملة نتائج عبر محرّك التحليل."""
    item = _item("result", RESULT_FACT)
    context = _context(item, outputs=[])
    issues = _run(_draft("أظهرت النتائج وجود فروق بين المجموعتين",
                         [_claim("وجود فروق بين المجموعتين",
                                 memory_ids=[str(item.memory_id)])]), context)
    assert _keys(issues) == set(), [i.issue_key for i in issues]


@pytest.mark.parametrize("sample_text", [
    "بلغت عينة الدراسة 120 طالبًا",
    "شارك 60 طالبًا في كل مجموعة",
])
def test_sample_counts_are_not_read_as_statistics(sample_text):
    """§17 — رقمُ عيّنة ليس مخرَج تحليل، ولا يُطالَب بسنده."""
    from athera_api.services.publishing.drafting import numbers

    assert numbers.find(sample_text) == []


@pytest.mark.parametrize("decimal", ["0.106", "0,106", "٠٫١٠٦"])
def test_every_decimal_separator_is_read_as_one_value(decimal):
    """§17 — النقطة والفاصلة والفاصلة العربية تمثيلاتٌ لقيمة واحدة."""
    from athera_api.services.publishing.drafting import numbers

    hits = numbers.find(f"η² = {decimal}")
    assert hits and hits[0].value.replace(",", ".") in ("0.106", ".106")


def test_a_grounded_decimal_is_not_reported_as_an_invented_sample_number():
    """`3.738` ليست عيّنةً من 738 مشاركًا — ولا تُحسب كشفًا مرتين."""
    from athera_api.services.publishing.drafting import checks

    output = _output(REAL_PAYLOAD)
    context = _context(_item("result", RESULT_FACT), outputs=[output])
    issues = checks.run(_draft("بلغت قيمة t(118) = 3.738",
                               [_claim("بلغت قيمة t(118) = 3.738",
                                       output_ids=[str(output.output_id)])]),
                        context, known_memory_ids=context.memory_ids,
                        known_output_ids=context.output_ids)
    assert "unsupported_sample_number" not in _keys(issues), [i.excerpt for i in issues]


# ══════════ 14. النسخة الجديدة تنقل إسناد ما لم يتغيّر ══════════

def test_carrying_a_section_forward_also_carries_its_claim_links():
    """**عطبٌ وجده الإنتاج.** القسم كان يُنسخ بنصّه وحاله ويترك روابطه خلفه.

    فبقي `claim_ids` الموروث يقول إن للمنهجية المعتمَدة ادعاءاتها، بينما
    `manuscript_section_claims` — وهو المرجع — فارغ. وذلك بعينه ما بُني ذلك
    الجدول ليمنعه: مصفوفةٌ تُجيب اليوم وتكذب غدًا.

    وفي الإنتاج: المنهجية في v2 لها رابطان، وفي v3 وv4 صفر — ونصّها لم يتغيّر.
    """
    import inspect

    from athera_api.routers import manuscript_drafting as drafting

    source = inspect.getsource(drafting._new_version)
    assert "ManuscriptSectionClaim(" in source, "النسخة الجديدة لا تنقل الروابط"
    assert "claim_id=link.claim_id" in source
    # والادعاء لا يُستنسخ: كيانٌ مملوك للمشروع لا للنسخة.
    # (نظرةُ خلفٍ سالبة كي لا يُطابَق `ManuscriptSectionClaim(`.)
    import re as _re

    assert not _re.search(r"(?<![A-Za-z])Claim\(", source), "الادعاء يُستنسخ بدل أن يُربط"


@requires_db
@pytest.mark.asyncio
async def test_an_approved_section_keeps_its_provenance_across_versions(two_tenants):
    """المنهجية المعتمَدة تبقى نصًّا **وإسنادًا** بعد إعادة صياغة النتائج."""
    from sqlalchemy import func, select

    from athera_api.db import tenant_session
    from athera_api.deps import Principal
    from athera_api.models.literature import Claim
    from athera_api.models.publishing import (
        Manuscript,
        ManuscriptSection,
        ManuscriptSectionClaim,
        ManuscriptVersion,
    )
    from athera_api.routers import manuscript_drafting as drafting

    tenant = two_tenants["a"]
    tid, uid = tenant["tenant_id"], tenant["user_id"]
    principal = Principal(user_id=uid, tenant_id=tid, roles=["researcher"],
                          mfa_satisfied=True, locale="ar")

    async with tenant_session(tid, uid) as session:
        from athera_api.models.portfolio import ResearchProject

        project = ResearchProject(tenant_id=tid, working_title_ar="مشروع")
        session.add(project)
        await session.flush()
        record = Manuscript(tenant_id=tid, project_id=project.id, title_ar="مخطوطة",
                            language="ar", status="draft")
        session.add(record)
        await session.flush()
        old = ManuscriptVersion(tenant_id=tid, manuscript_id=record.id,
                                version_label="v1", created_by=uid,
                                change_reason_ar="الأولى")
        session.add(old)
        await session.flush()
        section = ManuscriptSection(
            tenant_id=tid, version_id=old.id, section_key="method",
            text_ar="نصّ المنهجية المعتمَد", review_status="approved",
            reviewed_by=uid, reviewed_at=func.now())
        session.add(section)
        claim = Claim(tenant_id=tid, project_id=project.id, text_ar="ادعاء منهجي",
                      claim_type="empirical", status="supported")
        session.add(claim)
        await session.flush()
        session.add(ManuscriptSectionClaim(tenant_id=tid, section_id=section.id,
                                           claim_id=claim.id, ordinal=1))
        await session.flush()
        manuscript_id, old_id, claim_id = record.id, old.id, claim.id

    async with tenant_session(tid, uid) as session:
        record = (await session.execute(
            select(Manuscript).where(Manuscript.id == manuscript_id))).scalar_one()
        old = (await session.execute(
            select(ManuscriptVersion).where(ManuscriptVersion.id == old_id))).scalar_one()
        fresh = await drafting._new_version(session, principal, record, old,
                                            reason="إعادة صياغة النتائج",
                                            replace="results")

    async with tenant_session(tid, uid) as session:
        carried = (await session.execute(
            select(ManuscriptSection).where(
                ManuscriptSection.version_id == fresh.id,
                ManuscriptSection.section_key == "method"))).scalar_one()
        links = (await session.execute(
            select(ManuscriptSectionClaim).where(
                ManuscriptSectionClaim.section_id == carried.id))).scalars().all()
        total_claims = (await session.execute(
            select(func.count(Claim.id)).where(Claim.tenant_id == tid))).scalar_one()

    assert carried.review_status == "approved"
    assert carried.text_ar == "نصّ المنهجية المعتمَد"
    assert [link.claim_id for link in links] == [claim_id], "ضاع إسناد قسمٍ معتمَد"
    # والادعاء لم يُستنسخ — كيانٌ واحد مرتبط بنسختين.
    assert total_claims == 1


# ══════════ 15. بوابة الجاهزية ترفض علامة التحكّم الداخلية ══════════

def test_readiness_refuses_an_internal_marker_in_any_section():
    """**حارس التوليد وحده لا يكفي.**

    نسخةٌ قديمة تحمل العلامة تمرّ إلى بوابة النشر بلا أن تمرّ بالتوليد مرة
    أخرى. وقد وقع ذلك: ثلاثة أقسام محفوظة في الإنتاج تحملها، وكلها كُتبت
    قبل أن يوجد حارس التوليد.
    """
    from athera_api.services.publishing import manuscript

    for marker in ("[غير متاح]", "[قيمة إحصائية غير متاحة بنيويًّا]"):
        result = manuscript.evaluate([manuscript.SectionState(
            section_key="results", text=f"أظهرت النتائج فروقًا {marker} لصالح التجريبية")])
        keys = {i.issue_key for i in result.issues}
        assert "internal_redaction_marker" in keys, marker
        assert result.can_pass_g9 is False


def test_clean_prose_still_passes_the_marker_check():
    """الحارس الذي يعاقب النصّ السليم أسوأ من الحارس الذي يفوّت علامة."""
    from athera_api.services.publishing import manuscript

    result = manuscript.evaluate([manuscript.SectionState(
        section_key="method", text="استخدمت الدراسة المنهج شبه التجريبي")])
    assert "internal_redaction_marker" not in {i.issue_key for i in result.issues}


def test_the_marker_vocabulary_has_one_home():
    """مفردةٌ واحدة تقرؤها الصياغة والبوابة — لا نسختان تفترقان."""
    from athera_api.services.publishing import vocab
    from athera_api.services.publishing.drafting import checks

    assert checks.INTERNAL_MARKERS is vocab.INTERNAL_MARKERS


# ══════════ 16. عددٌ حقيقي من التحليل ليس رقم عيّنة مخترَعًا ══════════

def test_a_degrees_of_freedom_value_is_not_an_invented_sample_number():
    """**عطبٌ حجب مسودة صحيحة في الإنتاج.**

    كتب النموذج درجات الحرية خارج صيغة الاختبار — «د.ح = 118» بدل
    `t(118)` — فلم يرها مستخرِج الإحصاءات، ورآها حارسُ أرقام العيّنة رقمًا
    لا يرد في المادة الموثقة. و`118` عددٌ حقيقي خرج من التحليل.
    """
    from athera_api.services.publishing.drafting import checks

    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    issues = _run(_draft("بلغت درجات الحرية 118 في اختبار المجموعتين"), context)
    assert "unsupported_sample_number" not in _keys(issues), [i.excerpt for i in issues]
    assert checks.fabrications(issues) == []


def test_an_untyped_payload_value_is_also_excluded():
    """`n_control` مفتاحٌ لا نعرف نوعه — ويبقى عددًا حقيقيًّا من التحليل."""
    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    issues = _run(_draft("بلغ حجم كل مجموعة 60 مشاركًا"), context)
    assert "unsupported_sample_number" not in _keys(issues)


def test_a_number_in_no_output_and_no_evidence_is_still_refused():
    """والاستثناء لا يتّسع: رقمٌ لا في الأدلة ولا في المخرجات يبقى مرفوضًا."""
    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    issues = _run(_draft("شارك 240 طالبًا في الدراسة"), context)
    assert "unsupported_sample_number" in _keys(issues)


def test_the_exclusion_does_not_loosen_statistic_grounding():
    """رقمٌ في المخرَج لا يجعل **ادعاءً إحصائيًّا** مسنَدًا بنوع آخر."""
    context = _context(_item("result", RESULT_FACT), outputs=[_output(REAL_PAYLOAD)])
    issues = _run(_draft("بلغت قيمة p = 0.106 في الاختبار"), context)
    assert "statistic_without_analysis_output" in _keys(issues)
