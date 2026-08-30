"""AT-S3-02…10 — سلوك الحاسبة على الحالة المرجعية وحدودها (§11)."""
import datetime as dt

import pytest

from athera_api.services.promotion import calculator as calc
from athera_api.services.promotion import scenarios as sc
from athera_api.services.promotion.calculator import RuleInput, evaluate
from athera_api.services.promotion.facts import CaseFacts, PublicationFact

TODAY = dt.date(2026, 8, 30)


def rule(rule_type, key, params, *, verified=True, blocking=True, ef=None, et=None) -> RuleInput:
    return RuleInput(
        rule_id=f"r-{key}", rule_type=rule_type, rule_key=key,
        statement_ar=f"قاعدة {key}", statement_en=None, params=params,
        verification_status="verified" if verified else "unverified",
        is_blocking=blocking, effective_from=ef, effective_to=et,
    )


def publication(**kwargs) -> PublicationFact:
    defaults = dict(
        publication_id="p1", title="ورقة", published_on=dt.date(2025, 1, 1), author_count=1,
        author_position=1, is_corresponding=True, is_refereed=True, is_thesis_derived=False,
        indexes=(), journal_name="J1", verification_status="verified",
    )
    defaults.update(kwargs)
    return PublicationFact(**defaults)


REFERENCE_RULES = [
    rule("service_duration", "duration", {"min_years": 4}),
    rule("minimum_units", "units", {"min_units": 8}),
    rule("authorship_credit", "credit", {"credit_table": {"sole": 1.0, "2": 0.5, "3": 0.34}}),
    rule("indexing_requirement", "wos_strict",
         {"indexes": ["SSCI", "AHCI", "SCIE"], "min_count": 1, "count_esci": False}),
]

REFERENCE_FACTS = CaseFacts(
    as_of=TODAY, rank_started_on=dt.date(2022, 8, 30),
    current_rank="associate_professor", target_rank="professor", publications=(),
)


def test_reference_case_matches_the_spec():
    """AT-S3-03 — §11.4 حرفيًا: المدة مكتملة، 0 أبحاث، 0 وحدات، WoS غير مكتمل."""
    result = evaluate(REFERENCE_RULES, REFERENCE_FACTS)
    by_key = {e.rule_key: e for e in result.evaluations}

    assert by_key["duration"].status == calc.MET
    assert by_key["duration"].actual >= 4
    assert result.units_total == 0.0 and result.units_computable
    assert by_key["units"].status == calc.NOT_MET
    assert by_key["wos_strict"].status == calc.NOT_MET
    assert not result.is_ready


def test_unverified_rule_counts_in_neither_direction():
    """AT-S3-02 — ادعاء عدم الاستيفاء بقاعدة غير موثقة خطأ كادعاء الاستيفاء."""
    result = evaluate([rule("service_duration", "d", {"min_years": 99}, verified=False)],
                      REFERENCE_FACTS)
    assert result.evaluations[0].status == calc.NEEDS_VERIFICATION
    assert result.rules_blocking == 0
    assert result.rules_met == 0
    assert result.rules_needing_verification == 1


def test_units_are_unknown_not_zero_without_a_credit_table():
    """AT-S3-04 — «صفر» و«غير معلوم» ليسا الشيء نفسه."""
    facts = CaseFacts(as_of=TODAY, rank_started_on=dt.date(2022, 8, 30),
                      publications=(publication(author_count=2, author_position=1),))
    result = evaluate(
        [rule("authorship_credit", "credit", {}), rule("minimum_units", "units", {"min_units": 8})],
        facts,
    )
    assert result.units_total is None
    assert result.units_computable is False
    units_rule = next(e for e in result.evaluations if e.rule_key == "units")
    assert units_rule.status == calc.NEEDS_VERIFICATION


def test_units_are_zero_when_there_are_no_publications():
    """الفرق الآخر من الاتجاه المعاكس: لا منشورات ⇒ صفر مؤكد."""
    result = evaluate([rule("minimum_units", "units", {"min_units": 8})], REFERENCE_FACTS)
    assert result.units_total == 0.0 and result.units_computable


def test_unverified_credit_table_blocks_unit_computation():
    facts = CaseFacts(as_of=TODAY, publications=(publication(),))
    result = evaluate(
        [rule("authorship_credit", "credit", {"credit_table": {"sole": 1.0}}, verified=False)],
        facts,
    )
    assert result.units_total is None and not result.units_computable
    assert result.evaluations[0].status == calc.NEEDS_VERIFICATION


def test_each_unit_traces_to_its_publication():
    """AT-S3-05 — وحدة بلا مصدر لا تُقبل في ملف ترقية."""
    facts = CaseFacts(as_of=TODAY, publications=(publication(author_count=2, author_position=1),))
    result = evaluate(
        [rule("authorship_credit", "credit", {"credit_table": {"sole": 1.0, "2": 0.5}})], facts
    )
    contribution = result.evaluations[0].contributions[0]
    assert result.units_total == 0.5
    assert contribution.publication_id == "p1"
    assert contribution.explanation_ar.strip() and contribution.explanation_en.strip()


def test_conditional_index_is_excluded_unless_the_policy_says_otherwise():
    """AT-S3-09 — §20.3 عبر آلية عامة.

    شرط WoS الصارم يُعبَّر عنه بـ`conditional_indexes: {"ESCI": false}`. اسم
    الفهرس بيانات لائحة، لا ثابت في الحاسبة — فلائحة تستثني فهرسًا آخر تعمل
    بلا تعديل كود.
    """
    facts = CaseFacts(as_of=TODAY, publications=(publication(indexes=("ESCI",)),))

    strict = rule("indexing_requirement", "wos", {
        "indexes": ["SSCI", "AHCI", "SCIE"], "min_count": 1,
        "conditional_indexes": {"ESCI": False},
    })
    assert evaluate([strict], facts).evaluations[0].status == calc.NOT_MET

    # فهرس غير مذكور في `indexes` لا يُحتسب أصلًا — سكوت اللائحة ليس إذنًا.
    silent = rule("indexing_requirement", "wos", {"indexes": ["SSCI"], "min_count": 1})
    assert evaluate([silent], facts).evaluations[0].status == calc.NOT_MET

    explicit = rule("indexing_requirement", "wos", {
        "indexes": ["SSCI"], "min_count": 1, "conditional_indexes": {"ESCI": True},
    })
    assert evaluate([explicit], facts).evaluations[0].status == calc.MET


def test_the_exclusion_mechanism_is_not_specific_to_one_index():
    """الدليل على العمومية: استثناء فهرس آخر يعمل بالآلية نفسها."""
    facts = CaseFacts(as_of=TODAY, publications=(publication(indexes=("SCOPUS_Q4",)),))
    excluded = rule("indexing_requirement", "idx", {
        "indexes": ["SCOPUS_Q1", "SCOPUS_Q2"], "min_count": 1,
        "conditional_indexes": {"SCOPUS_Q4": False},
    })
    assert evaluate([excluded], facts).evaluations[0].status == calc.NOT_MET
    allowed = rule("indexing_requirement", "idx", {
        "indexes": ["SCOPUS_Q1"], "min_count": 1,
        "conditional_indexes": {"SCOPUS_Q4": True},
    })
    assert evaluate([allowed], facts).evaluations[0].status == calc.MET


def test_rule_outside_its_effective_window_does_not_apply():
    """AT-S3-08 — §11.2: تاريخ السريان جزء من القاعدة."""
    expired = rule("service_duration", "d", {"min_years": 1},
                   ef=dt.date(2020, 1, 1), et=dt.date(2021, 1, 1))
    result = evaluate([expired], REFERENCE_FACTS)
    assert result.evaluations[0].status == calc.NOT_APPLICABLE
    assert result.rules_blocking == 0


def test_all_twelve_rule_types_are_evaluated_and_bilingual():
    """AT-S3-10 — §11.3 كاملة، وكل تقييم يشرح بالعربية والإنجليزية."""
    every_type = REFERENCE_RULES + [
        rule("sole_author_works", "sole", {"min_count": 6}),
        rule("minimum_refereed_journals", "refereed", {"min_count": 4}),
        rule("outlet_diversity", "diversity", {"min_distinct_outlets": 3}),
        rule("production_points", "points", {"points_table": {"SSCI": 4}, "min_points": 10}),
        rule("date_window", "window", {"counts_from": "rank_start"}),
        rule("thesis_derived_limit", "thesis", {"exclude_all": True}),
        rule("first_or_corresponding_author", "first", {"min_count": 2}),
        rule("teaching_service_requirement", "teaching", {"min_courses": 3}),
    ]
    result = evaluate(every_type, REFERENCE_FACTS)
    assert len(result.evaluations) == 12

    for evaluation in result.evaluations:
        assert evaluation.explanation_ar.strip(), f"{evaluation.rule_key} has no Arabic explanation"
        assert evaluation.explanation_en.strip(), f"{evaluation.rule_key} has no English explanation"
        assert any("؀" <= ch <= "ۿ" for ch in evaluation.explanation_ar)


def test_teaching_and_service_are_declared_not_guessed():
    """المنصة لا تملك سجلات الجامعة — تقولها بدل أن تفترض."""
    result = evaluate([rule("teaching_service_requirement", "t", {"min_courses": 3})],
                      REFERENCE_FACTS)
    assert result.evaluations[0].status == calc.NEEDS_VERIFICATION


def test_readiness_requires_no_pending_verification():
    """جاهزية مع قاعدة تنتظر تحققًا مؤسسيًا ليست جاهزية."""
    result = evaluate(
        [rule("service_duration", "d", {"min_years": 1}),
         rule("sole_author_works", "s", {"min_count": 1}, verified=False)],
        REFERENCE_FACTS,
    )
    assert result.rules_met == 1
    assert result.rules_needing_verification == 1
    assert not result.is_ready


def test_scenario_is_a_projection_and_never_mutates_the_case():
    """AT-S3-06 — الإسقاط ليس إنجازًا."""
    planned = [sc.PlannedWork(title="ورقة منفردة", author_count=1,
                              indexes=("SSCI",), journal_name="J9")]
    result = sc.project(kind="safe", rules=REFERENCE_RULES, facts=REFERENCE_FACTS,
                        planned_works=planned)

    assert result.is_projection is True
    assert result.baseline.units_total == 0.0
    assert result.projected.units_total == 1.0
    assert REFERENCE_FACTS.publications == ()          # الوقائع الأصلية لم تُمس
    assert any("غير مضمون" in text for text in result.assumptions_ar)
    assert len(result.assumptions_ar) == len(result.assumptions_en)


def test_unknown_scenario_kind_is_refused():
    with pytest.raises(ValueError):
        sc.project(kind="guaranteed_promotion", rules=REFERENCE_RULES,
                   facts=REFERENCE_FACTS, planned_works=[])
