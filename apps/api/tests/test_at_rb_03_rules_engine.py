"""AT-RB-03 — محرّك القواعد: رتبتها، وحكمها الرابع، وأنها لا تحجب اليوم.

هذا الملف يحرس خاصّيتين لا تُرى واحدةٌ منهما في الشاشة:

١. **لا قاعدة تحجب** ما دامت `DRAFT`. ولو انقلبت هذه الخاصّية سهوًا لبدأ
   المحرّك يوقف باحثين بقواعد لم يراجعها مختصّ.
٢. **الجهل يُعلَن**. قاعدةٌ لا تجد ما تفحصه ترجع `insufficient_information`
   لا `pass` — والفرق بينهما هو الفرق بين «فُحص وسلم» و«لم يُفحص».
"""
import pathlib

import pytest

from athera_api.research_brain import catalogue, rules
from athera_api.research_brain.rules import Assessment, RuleStatus, Verdict
from athera_api.services.analysis.vocab import TEST_KINDS
from athera_api.services.inbox import ALERT_SEVERITIES, is_blocking

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WORKSPACE = REPO_ROOT / "apps" / "api" / "athera_api" / "services" / "workspace.py"

# العشر مكتوبةً بأسمائها — فيفشل الاختبار إذا حُذفت قاعدة بصمت.
EXPECTED_RULES = {
    "RB-CAUSALITY-01", "RB-FABRICATION-01", "RB-FABRICATION-02",
    "RB-DESIGN-01", "RB-DESIGN-02", "RB-LINEAGE-01",
    "RB-EVIDENCE-01", "RB-EVIDENCE-02",
    "RB-PROVENANCE-01", "RB-PROVENANCE-02",
}


def test_the_ten_rules_are_registered():
    assert {rule.id for rule in catalogue.RULES} == EXPECTED_RULES
    assert len(catalogue.RULES) == len(catalogue.BY_ID) == 10


# ── الرتبة ────────────────────────────────────────────────────────────────

def test_every_rule_is_draft_because_no_expert_has_reviewed_one():
    """لا قاعدة تدّعي مراجعةً لم تقع. من كتب الشيفرة لا يمنح رتبة مراجع."""
    for rule in catalogue.RULES:
        assert rule.status is RuleStatus.DRAFT, rule.id


def test_no_rule_can_block_today():
    for rule in catalogue.RULES:
        assert not rule.is_enforceable, rule.id
        assert not rule.blocks, rule.id


def test_expert_review_alone_does_not_make_a_rule_block():
    """المراجعة تقول «صحيحة علميًّا»، والاعتماد يقول «توقف عليها العمل»."""
    rule = catalogue.BY_ID["RB-EVIDENCE-01"]
    reviewed = replace_status(rule, RuleStatus.EXPERT_REVIEWED)
    approved = replace_status(rule, RuleStatus.APPROVED)
    assert not reviewed.blocks
    assert approved.blocks


def replace_status(rule, status):
    import dataclasses
    return dataclasses.replace(rule, status=status)


def test_a_deprecated_rule_is_not_run_but_is_not_deleted():
    """قاعدةٌ مهجورة تبقى بتاريخها في السجل ولا تُشغَّل."""
    retired = replace_status(catalogue.BY_ID["RB-EVIDENCE-01"], RuleStatus.DEPRECATED)
    report = rules.evaluate(Assessment(), (retired,))
    assert report.results == ()


# ── العقد ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rule", sorted(catalogue.RULES, key=lambda r: r.id),
                         ids=lambda r: r.id)
def test_every_rule_is_bilingual_and_carries_its_provenance(rule):
    assert any("؀" <= ch <= "ۿ" for ch in rule.message_ar), rule.id
    assert any("؀" <= ch <= "ۿ" for ch in rule.condition_ar), rule.id
    assert rule.message_en.strip() and rule.condition_en.strip()
    # المصدر ليس حقلًا تجميليًّا: قاعدةٌ بلا مصدر لا تُراجَع ولا تسقط.
    assert len(rule.provenance.strip()) > 20, rule.id
    assert rule.severity in ALERT_SEVERITIES
    assert rule.version >= 1


def test_severity_vocabulary_is_the_platform_vocabulary():
    """`info | warning | blocking` — لا مقياس شدّة ثانٍ للشيء نفسه."""
    assert set(ALERT_SEVERITIES) == {"info", "warning", "blocking"}
    assert is_blocking("blocking") and not is_blocking("warning")
    # شدّة مجهولة تُعامل معاملة الحاجب — الفشل مغلق كما في `services/inbox.py`.
    assert is_blocking("critical")


def test_a_rule_without_provenance_cannot_be_built():
    with pytest.raises(ValueError):
        rules.ScientificRule(
            id="X", category=rules.RuleCategory.EVIDENCE, severity="blocking",
            condition_ar="ش", condition_en="c", message_ar="رسالة", message_en="m",
            provenance="   ", predicate=lambda a: rules.passed())


def test_a_rule_without_an_arabic_message_cannot_be_built():
    with pytest.raises(ValueError):
        rules.ScientificRule(
            id="X", category=rules.RuleCategory.EVIDENCE, severity="blocking",
            condition_ar="ش", condition_en="c", message_ar="english only", message_en="m",
            provenance="a documented source of this rule", predicate=lambda a: rules.passed())


def test_an_unknown_severity_cannot_be_built():
    with pytest.raises(ValueError):
        rules.ScientificRule(
            id="X", category=rules.RuleCategory.EVIDENCE, severity="critical",
            condition_ar="ش", condition_en="c", message_ar="رسالة", message_en="m",
            provenance="a documented source of this rule", predicate=lambda a: rules.passed())


def test_a_violation_must_name_what_it_found():
    """«هناك مشكلة في مكانٍ ما» ليست نتيجة قابلة للتصحيح."""
    with pytest.raises(ValueError):
        rules.violated()


# ── المحرّك ───────────────────────────────────────────────────────────────

def test_an_empty_assessment_yields_no_violation_and_no_crash():
    report = rules.evaluate(Assessment(), catalogue.RULES)
    assert len(report.results) == 10
    assert report.violations == ()
    assert report.blocking == ()


def test_the_report_is_ordered_by_rule_id_not_by_registry_order():
    """تقريران لا يُقارَنان إلا إذا خرجا بالترتيب نفسه في كل تشغيلة."""
    report = rules.evaluate(Assessment(), catalogue.RULES)
    ids = [result.rule.id for result in report.results]
    assert ids == sorted(ids)
    assert ids == [r.rule.id for r in rules.evaluate(Assessment(), catalogue.RULES).results]


def test_a_broken_predicate_is_not_swallowed():
    """استثناءٌ في قاعدة حتمية عطبٌ فيها — وابتلاعُه يقتل الحارس صامتًا."""
    def explode(_assessment):
        raise RuntimeError("boom")

    broken = rules.ScientificRule(
        id="X", category=rules.RuleCategory.EVIDENCE, severity="blocking",
        condition_ar="ش", condition_en="c", message_ar="رسالة", message_en="m",
        provenance="a documented source of this rule", predicate=explode)
    with pytest.raises(RuntimeError):
        rules.evaluate(Assessment(), (broken,))


def test_unevaluated_rules_are_reported_as_loudly_as_violations():
    """تقريرٌ يذكر المخالفات ويصمت عمّا عجز عنه يُقرأ «سليم»."""
    report = rules.evaluate(
        Assessment(sections={"discussion": "يؤدي التدريب إلى تحسّن الأداء."}),
        catalogue.RULES)
    # التصميم غير مسجَّل: اللغة السببية تُعرض ولا يُحكم عليها.
    result = report.by_rule("RB-CAUSALITY-01")
    assert result.outcome.verdict is Verdict.INSUFFICIENT_INFORMATION
    assert result.findings, "ما لُوحظ يُحمل مع «لم أستطع الفحص» ولا يُطرح"
    assert result in report.unevaluated


# ── مفردات القواعد ────────────────────────────────────────────────────────

def test_test_fitness_names_only_real_test_kinds():
    assert set(catalogue.TEST_FITNESS) <= set(TEST_KINDS)


def test_tests_without_a_recorded_fitness_rule_are_declared_not_guessed():
    """ثمانية اختبارات بلا حكم — والقاعدة تقولها ولا تفترض ملاءمة."""
    uncovered = set(TEST_KINDS) - set(catalogue.TEST_FITNESS)
    assert uncovered == {
        "descriptive", "reliability", "validity", "sem", "pls_sem",
        "mediation", "moderation", "factor_analysis",
    }


def test_brain_field_states_match_the_workspace_service():
    """الحالات الأربع مقروءة من الخدمة التي تُنتجها لا من الذاكرة."""
    text = WORKSPACE.read_text(encoding="utf-8")
    assert "`known` | `needs_review` | `missing` | `conflicting`" in text
    for state in ("known", "needs_review", "missing", "conflicting"):
        rules.BrainFieldView(key="question", state=state)
    with pytest.raises(Exception):
        rules.BrainFieldView(key="question", state="verified")


def test_candidate_statuses_are_the_four_of_migration_0016():
    for status in ("unverified", "approved", "rejected", "unknown"):
        rules.CandidateView(id="c", status=status)
    with pytest.raises(Exception):
        rules.CandidateView(id="c", status="pending")


def test_related_issue_keys_point_at_checks_that_exist():
    """ربطُ القاعدة بمفاتيح الفحوص القائمة يمنع تنبيهين لعطبٍ واحد عند التفعيل."""
    api_src = REPO_ROOT / "apps" / "api" / "athera_api"
    haystack = "\n".join(
        path.read_text(encoding="utf-8") for path in api_src.rglob("*.py")
        if "research_brain" not in path.parts
    )
    for rule in catalogue.RULES:
        for key in rule.related_issue_keys:
            assert f'"{key}"' in haystack, f"{rule.id} → {key}"


def test_the_narrative_is_ordered_by_manuscript_sections():
    """ترتيب القاموس ترتيبُ الإدخال — ومخرَجٌ حتميّ لا يتبع ترتيب الكتابة."""
    first = Assessment(sections={"discussion": "ب", "introduction": "أ"})
    second = Assessment(sections={"introduction": "أ", "discussion": "ب"})
    assert first.narrative() == second.narrative() == "أ\nب"
