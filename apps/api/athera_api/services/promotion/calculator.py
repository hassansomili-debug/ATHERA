"""حاسبة الترقية | Promotion calculator (§11).

**لا يوجد في هذا الملف ثابت جامعي واحد.** لا «أربع سنوات»، ولا حد أدنى
للوحدات، ولا جدول احتساب تأليف. الحاسبة تعرف أنواع القواعد (§11.3) وتقرأ
كل قيمة من `params` القاعدة. لائحة أخرى تعمل بلا سطر كود جديد (§3).

ثلاث حالات لا حالتان — وهذا هو جوهر أمانة المخرَج:
    met                              الشرط مستوفى بدليل
    not_met                          الشرط غير مستوفى بقاعدة موثقة
    needs_institutional_verification القاعدة أو معاملها غير موثق (§11.4)

الحالة الثالثة ليست تهرّبًا: الادعاء بأن شرطًا غير مستوفٍ بناءً على قاعدة
غير موثقة خطأ بنفس قدر ادعاء استيفائه.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

from .facts import CaseFacts, PublicationFact

MET = "met"
NOT_MET = "not_met"
NEEDS_VERIFICATION = "needs_institutional_verification"
NOT_APPLICABLE = "not_applicable"


@dataclass(slots=True)
class RuleInput:
    """صورة قاعدة كما تصل الحاسبة — مفصولة عن نموذج قاعدة البيانات."""

    rule_id: str
    rule_type: str
    rule_key: str
    statement_ar: str
    statement_en: str | None
    params: dict[str, Any]
    verification_status: str
    is_blocking: bool = True
    effective_from: dt.date | None = None
    effective_to: dt.date | None = None
    source_locator: str | None = None


@dataclass(slots=True)
class UnitContribution:
    publication_id: str
    contribution: float
    explanation_ar: str
    explanation_en: str


@dataclass(slots=True)
class RuleEvaluation:
    rule_id: str
    rule_type: str
    rule_key: str
    status: str
    required: Any = None
    actual: Any = None
    is_blocking: bool = True
    explanation_ar: str = ""
    explanation_en: str = ""
    contributions: list[UnitContribution] = field(default_factory=list)


@dataclass(slots=True)
class CaseResult:
    """§27.2 — عدّادات صريحة، لا نسبة واحدة.

    نسبة «90٪ جاهز» تخفي شرطًا حاجبًا واحدًا يوقف الملف كله. العدّاد الصريح
    لا يفعل ذلك.
    """

    evaluations: list[RuleEvaluation]
    units_total: float | None
    units_computable: bool
    rules_met: int
    rules_blocking: int
    rules_needing_verification: int

    @property
    def is_ready(self) -> bool:
        """جاهز = لا شرط حاجب غير مستوفٍ، ولا قاعدة تنتظر تحققًا مؤسسيًا."""
        return self.rules_blocking == 0 and self.rules_needing_verification == 0


def _missing(rule: RuleInput, keys: list[str]) -> list[str]:
    return [key for key in keys if rule.params.get(key) is None]


def _needs(rule: RuleInput, reason_ar: str, reason_en: str) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule.rule_id, rule_type=rule.rule_type, rule_key=rule.rule_key,
        status=NEEDS_VERIFICATION, is_blocking=rule.is_blocking,
        explanation_ar=reason_ar, explanation_en=reason_en,
    )


def _verdict(
    rule: RuleInput, ok: bool, required: Any, actual: Any,
    explanation_ar: str, explanation_en: str,
    contributions: list[UnitContribution] | None = None,
) -> RuleEvaluation:
    return RuleEvaluation(
        rule_id=rule.rule_id, rule_type=rule.rule_type, rule_key=rule.rule_key,
        status=MET if ok else NOT_MET, required=required, actual=actual,
        is_blocking=rule.is_blocking, explanation_ar=explanation_ar,
        explanation_en=explanation_en, contributions=contributions or [],
    )


# ── احتساب الوحدات: جدول المشاركة معامل في قاعدة، لا ثابت في دالة ──

def credit_for(credit_table: dict[str, Any], publication: PublicationFact) -> float | None:
    """يقرأ نصيب الباحث من جدول اللائحة.

    مفاتيح مدعومة: "sole" / "1" / "2" / "3" … و"default".
    مفتاح مفقود يعيد None — أي «غير محسوب»، لا صفرًا ولا تخمينًا.
    """
    if publication.is_sole_author:
        value = credit_table.get("sole", credit_table.get("1"))
        return float(value) if value is not None else None

    by_count = credit_table.get(str(publication.author_count))
    if by_count is not None:
        return float(by_count)

    position_key = f"{publication.author_count}:{publication.author_position}"
    if credit_table.get(position_key) is not None:
        return float(credit_table[position_key])

    fallback = credit_table.get("default")
    return float(fallback) if fallback is not None else None


def _eval_authorship_credit(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    table = rule.params.get("credit_table")
    if not isinstance(table, dict) or not table:
        return _needs(
            rule,
            "جدول احتساب المشاركة غير موثق في اللائحة؛ لا يمكن حساب الوحدات.",
            "The authorship credit table is not documented; units cannot be computed.",
        )

    contributions: list[UnitContribution] = []
    uncomputable: list[str] = []
    for publication in facts.verified_publications:
        share = credit_for(table, publication)
        if share is None:
            uncomputable.append(publication.title[:60])
            continue
        contributions.append(UnitContribution(
            publication_id=publication.publication_id,
            contribution=share,
            explanation_ar=(
                f"«{publication.title[:60]}»: {publication.author_count} مؤلفًا، "
                f"ترتيب الباحث {publication.author_position} ⇒ {share} وحدة."
            ),
            explanation_en=(
                f"'{publication.title[:60]}': {publication.author_count} authors, "
                f"position {publication.author_position} ⇒ {share} unit(s)."
            ),
        ))

    if uncomputable:
        return _needs(
            rule,
            "جدول الاحتساب لا يغطي بعض الأعمال: " + "، ".join(uncomputable),
            "The credit table does not cover: " + ", ".join(uncomputable),
        )

    total = round(sum(c.contribution for c in contributions), 3)
    return _verdict(
        rule, True, None, total,
        f"احتُسبت {total} وحدة من {len(contributions)} عملًا متحققًا.",
        f"{total} unit(s) computed from {len(contributions)} verified work(s).",
        contributions,
    )


def _eval_service_duration(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    missing = _missing(rule, ["min_years"])
    if missing:
        return _needs(rule, "مدة الخدمة المطلوبة غير موثقة في اللائحة.",
                      "The required service duration is not documented.")
    if facts.rank_started_on is None:
        return _needs(rule, "تاريخ بداية الرتبة الحالية غير مسجّل في ملف الباحث.",
                      "The current rank start date is missing from the profile.")

    days = (facts.as_of - facts.rank_started_on).days
    years = round(days / 365.25, 2)
    required = float(rule.params["min_years"])
    return _verdict(
        rule, years >= required, required, years,
        f"أمضى الباحث {years} سنة في الرتبة الحالية، والمطلوب {required}.",
        f"{years} year(s) completed in rank; {required} required.",
    )


def _eval_minimum_units(rule: RuleInput, facts: CaseFacts, units: float | None) -> RuleEvaluation:
    missing = _missing(rule, ["min_units"])
    if missing:
        return _needs(rule, "الحد الأدنى للوحدات غير موثق في اللائحة.",
                      "The minimum unit threshold is not documented.")
    if units is None:
        return _needs(rule, "الوحدات غير قابلة للحساب لأن جدول الاحتساب غير موثق.",
                      "Units are not computable because the credit table is undocumented.")
    required = float(rule.params["min_units"])
    return _verdict(
        rule, units >= required, required, units,
        f"الوحدات المحسوبة {units} والمطلوب {required}.",
        f"{units} unit(s) computed; {required} required.",
    )


def _eval_sole_author_works(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    if _missing(rule, ["min_count"]):
        return _needs(rule, "عدد الأعمال المنفردة المطلوب غير موثق.",
                      "The required number of sole-authored works is not documented.")
    actual = sum(1 for p in facts.verified_publications if p.is_sole_author)
    required = int(rule.params["min_count"])
    return _verdict(
        rule, actual >= required, required, actual,
        f"الأعمال المنفردة المتحققة {actual} والمطلوب {required}.",
        f"{actual} verified sole-authored work(s); {required} required.",
    )


def _eval_minimum_refereed(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    if _missing(rule, ["min_count"]):
        return _needs(rule, "عدد المجلات المحكمة المطلوب غير موثق.",
                      "The required number of refereed journal papers is not documented.")
    actual = sum(1 for p in facts.verified_publications if p.is_refereed)
    required = int(rule.params["min_count"])
    return _verdict(
        rule, actual >= required, required, actual,
        f"الأعمال المحكمة المتحققة {actual} والمطلوب {required}.",
        f"{actual} verified refereed work(s); {required} required.",
    )


def _eval_outlet_diversity(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    if _missing(rule, ["min_distinct_outlets"]):
        return _needs(rule, "شرط تنوع منافذ النشر غير موثق.",
                      "The outlet diversity requirement is not documented.")
    outlets = {p.journal_name for p in facts.verified_publications if p.journal_name}
    required = int(rule.params["min_distinct_outlets"])
    return _verdict(
        rule, len(outlets) >= required, required, len(outlets),
        f"عدد المنافذ المختلفة {len(outlets)} والمطلوب {required}.",
        f"{len(outlets)} distinct outlet(s); {required} required.",
    )


def _eval_indexing(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    """شروط الفهرسة — بأسماء فهارس تأتي كلها من اللائحة، لا من الكود.

    `indexes` هي المجموعة المقبولة، و`conditional_indexes` خريطة لفهارس
    تُحتسب فقط إذا نصّت اللائحة صراحةً. شرط WoS الصارم في §20.3
    (`count_esci: false`) يُعبَّر عنه هكذا: ``conditional_indexes: {"ESCI": false}``
    — الآلية عامة، فلائحة تستثني فهرسًا آخر تعمل بلا سطر كود جديد (§3).
    """
    if _missing(rule, ["indexes", "min_count"]):
        return _needs(rule, "شروط الفهرسة المطلوبة غير موثقة.",
                      "The required indexing conditions are not documented.")

    accepted = {str(index).upper() for index in rule.params["indexes"]}
    conditional = rule.params.get("conditional_indexes") or {}
    excluded = set()
    for name, enabled in conditional.items():
        key = str(name).upper()
        if enabled is True:
            accepted.add(key)
        else:
            # الغياب أو القيمة الصريحة `false` كلاهما استبعاد: لا يُفسَّر
            # سكوت اللائحة لصالح الباحث.
            accepted.discard(key)
            excluded.add(key)

    matching = [
        p for p in facts.verified_publications
        if accepted & {str(index).upper() for index in p.indexes}
    ]
    required = int(rule.params["min_count"])
    note_ar = f" (لا يُحتسب: {sorted(excluded)})" if excluded else ""
    note_en = f" (not counted: {sorted(excluded)})" if excluded else ""
    return _verdict(
        rule, len(matching) >= required, required, len(matching),
        f"الأعمال المفهرسة ضمن {sorted(accepted)}: {len(matching)} والمطلوب {required}{note_ar}.",
        f"Works indexed in {sorted(accepted)}: {len(matching)}; {required} required{note_en}.",
    )


def _eval_date_window(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    not_before = rule.params.get("not_before")
    if not_before is None and rule.params.get("counts_from") != "rank_start":
        return _needs(rule, "شرط النافذة الزمنية غير موثق.",
                      "The date window condition is not documented.")
    boundary = facts.rank_started_on if rule.params.get("counts_from") == "rank_start" else (
        dt.date.fromisoformat(str(not_before))
    )
    if boundary is None:
        return _needs(rule, "تاريخ بداية الرتبة غير مسجّل، ولا يمكن تطبيق النافذة الزمنية.",
                      "Rank start date is missing; the date window cannot be applied.")
    inside = [p for p in facts.verified_publications if p.published_on and p.published_on >= boundary]
    return _verdict(
        rule, True, str(boundary), len(inside),
        f"الأعمال المتحققة بعد {boundary}: {len(inside)}.",
        f"Verified works published on or after {boundary}: {len(inside)}.",
    )


def _eval_thesis_derived(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    max_allowed = rule.params.get("max_allowed")
    if max_allowed is None and rule.params.get("exclude_all") is not True:
        return _needs(rule, "شرط الأعمال المستلة من الرسائل غير موثق.",
                      "The thesis-derived work condition is not documented.")
    derived = sum(1 for p in facts.verified_publications if p.is_thesis_derived)
    if rule.params.get("exclude_all") is True:
        return _verdict(
            rule, derived == 0, 0, derived,
            f"الأعمال المستلة من الرسائل: {derived}، واللائحة تستبعدها كليًا.",
            f"Thesis-derived works: {derived}; the policy excludes them entirely.",
        )
    required = int(max_allowed)
    return _verdict(
        rule, derived <= required, required, derived,
        f"الأعمال المستلة من الرسائل {derived} والحد الأقصى {required}.",
        f"{derived} thesis-derived work(s); maximum allowed {required}.",
    )


def _eval_first_or_corresponding(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    if _missing(rule, ["min_count"]):
        return _needs(rule, "شرط المؤلف الأول أو المراسل غير موثق.",
                      "The first/corresponding author condition is not documented.")
    actual = sum(
        1 for p in facts.verified_publications
        if p.author_position == 1 or p.is_corresponding
    )
    required = int(rule.params["min_count"])
    return _verdict(
        rule, actual >= required, required, actual,
        f"أعمال بصفة مؤلف أول أو مراسل: {actual} والمطلوب {required}.",
        f"{actual} work(s) as first or corresponding author; {required} required.",
    )


def _eval_production_points(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    table = rule.params.get("points_table")
    if not isinstance(table, dict) or rule.params.get("min_points") is None:
        return _needs(rule, "جدول نقاط الإنتاج العلمي أو حده الأدنى غير موثق.",
                      "The production points table or its threshold is not documented.")
    total = 0.0
    for publication in facts.verified_publications:
        matched = next(
            (float(table[key]) for key in table
             if key.upper() in {str(i).upper() for i in publication.indexes}),
            None,
        )
        if matched is None:
            matched = float(table.get("default", 0))
        total += matched
    required = float(rule.params["min_points"])
    total = round(total, 3)
    return _verdict(
        rule, total >= required, required, total,
        f"نقاط الإنتاج المحسوبة {total} والمطلوب {required}.",
        f"{total} production point(s); {required} required.",
    )


def _eval_teaching_service(rule: RuleInput, facts: CaseFacts) -> RuleEvaluation:
    """المنصة لا تملك سجلات التدريس والخدمة — تُعلَن كحاجة تحقق، لا تُخمَّن."""
    if not facts.teaching_records and not facts.service_records:
        return _needs(
            rule,
            "متطلبات التدريس والخدمة تُثبت من أنظمة الجامعة، ولا توجد سجلات في المنصة.",
            "Teaching and service requirements are proven by university systems; no records here.",
        )
    return _verdict(
        rule, True, rule.params, len(facts.teaching_records) + len(facts.service_records),
        "سجلات التدريس والخدمة متوفرة وتحتاج مطابقة مع اللائحة.",
        "Teaching and service records exist and require matching against the policy.",
    )


_EVALUATORS: dict[str, Callable[[RuleInput, CaseFacts], RuleEvaluation]] = {
    "service_duration": _eval_service_duration,
    "sole_author_works": _eval_sole_author_works,
    "authorship_credit": _eval_authorship_credit,
    "minimum_refereed_journals": _eval_minimum_refereed,
    "outlet_diversity": _eval_outlet_diversity,
    "indexing_requirement": _eval_indexing,
    "date_window": _eval_date_window,
    "thesis_derived_limit": _eval_thesis_derived,
    "first_or_corresponding_author": _eval_first_or_corresponding,
    "production_points": _eval_production_points,
    "teaching_service_requirement": _eval_teaching_service,
}


def _is_effective(rule: RuleInput, as_of: dt.date) -> bool:
    if rule.effective_from and as_of < rule.effective_from:
        return False
    if rule.effective_to and as_of > rule.effective_to:
        return False
    return True


def evaluate(rules: list[RuleInput], facts: CaseFacts) -> CaseResult:
    """يقيّم كل قاعدة سارية ومتحققة، ويعلن ما عداها بوضوح."""
    evaluations: list[RuleEvaluation] = []
    units_total: float | None = None
    units_computable = True

    # الوحدات أولًا: قواعد أخرى تعتمد عليها.
    credit_rules = [r for r in rules if r.rule_type == "authorship_credit"]
    if credit_rules:
        rule = credit_rules[0]
        if rule.verification_status != "verified":
            units_computable = False
            evaluations.append(_needs(
                rule,
                "جدول احتساب المشاركة لم يعتمده إنسان بعد؛ لا تُحتسب الوحدات على قاعدة غير موثقة.",
                "The credit table is not human-verified; units are not computed from an unverified rule.",
            ))
        elif not _is_effective(rule, facts.as_of):
            units_computable = False
            evaluations.append(_needs(
                rule, "جدول احتساب المشاركة خارج نافذة سريانه.",
                "The credit table is outside its effective window.",
            ))
        else:
            evaluation = _eval_authorship_credit(rule, facts)
            evaluations.append(evaluation)
            if evaluation.status == MET:
                units_total = float(evaluation.actual)
            else:
                units_computable = False
    elif not facts.publications:
        # لا منشورات ⇒ صفر وحدة معلومة يقينًا، بلا حاجة إلى جدول احتساب.
        units_total = 0.0
    else:
        units_computable = False

    if units_total is None and not facts.publications:
        units_total = 0.0

    for rule in rules:
        if rule.rule_type == "authorship_credit":
            continue
        if rule.verification_status != "verified":
            evaluations.append(_needs(
                rule,
                "القاعدة مستخرجة من مستند ولم يعتمدها إنسان بعد (§11.4).",
                "This rule was extracted from a document and is not human-verified yet (§11.4).",
            ))
            continue
        if not _is_effective(rule, facts.as_of):
            evaluations.append(RuleEvaluation(
                rule_id=rule.rule_id, rule_type=rule.rule_type, rule_key=rule.rule_key,
                status=NOT_APPLICABLE, is_blocking=False,
                explanation_ar=f"القاعدة خارج نافذة سريانها في {facts.as_of}.",
                explanation_en=f"Rule is outside its effective window as of {facts.as_of}.",
            ))
            continue

        if rule.rule_type == "minimum_units":
            evaluations.append(_eval_minimum_units(rule, facts, units_total))
            continue

        evaluator = _EVALUATORS.get(rule.rule_type)
        if evaluator is None:
            evaluations.append(_needs(
                rule, f"نوع قاعدة غير مدعوم في الحاسبة: {rule.rule_type}.",
                f"Unsupported rule type in the calculator: {rule.rule_type}.",
            ))
            continue
        evaluations.append(evaluator(rule, facts))

    met = sum(1 for e in evaluations if e.status == MET)
    blocking = sum(1 for e in evaluations if e.status == NOT_MET and e.is_blocking)
    needing = sum(1 for e in evaluations if e.status == NEEDS_VERIFICATION)

    return CaseResult(
        evaluations=evaluations,
        units_total=units_total if units_computable else None,
        units_computable=units_computable,
        rules_met=met,
        rules_blocking=blocking,
        rules_needing_verification=needing,
    )
