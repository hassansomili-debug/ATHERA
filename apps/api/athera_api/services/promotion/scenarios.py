"""سيناريوهات What-if | Promotion scenarios (§11.6).

قاعدة واحدة تحكم هذا الملف: **الإسقاط ليس إنجازًا.** كل مخرَج هنا موسوم
`is_projection=true`، ولا يكتب في `promotion_cases` ولا يغيّر وحدة واحدة
محسوبة. ولا يعد أي سيناريو بقبول ورقة — يفترض قبولها ويقول ذلك صراحةً.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .calculator import CaseResult, RuleInput, evaluate
from .facts import CaseFacts, PublicationFact

SCENARIO_KINDS = ("minimum", "safe", "ambitious", "rejection_impact", "indexing_change")


@dataclass(slots=True)
class PlannedWork:
    """عمل مخطط — ليس منشورًا. يدخل الإسقاط فقط."""

    title: str
    author_count: int = 1
    author_position: int = 1
    is_corresponding: bool = True
    indexes: tuple[str, ...] = field(default_factory=tuple)
    journal_name: str | None = None
    is_thesis_derived: bool = False
    expected_on: dt.date | None = None


@dataclass(slots=True)
class ScenarioResult:
    kind: str
    is_projection: bool
    assumptions_ar: list[str]
    assumptions_en: list[str]
    baseline: CaseResult
    projected: CaseResult
    added_works: int


def _as_publication(work: PlannedWork, index: int) -> PublicationFact:
    """يحوّل عملًا مخططًا إلى واقعة **افتراضية** موسومة بمعرّف مؤقت."""
    return PublicationFact(
        publication_id=f"planned-{index}",
        title=work.title,
        published_on=work.expected_on,
        author_count=work.author_count,
        author_position=work.author_position,
        is_corresponding=work.is_corresponding,
        is_refereed=True,
        is_thesis_derived=work.is_thesis_derived,
        indexes=tuple(work.indexes),
        journal_name=work.journal_name,
        # يدخل الإسقاط بوصفه متحققًا افتراضًا، وهذا الافتراض معلن في المخرَج.
        verification_status="verified",
    )


def project(
    *,
    kind: str,
    rules: list[RuleInput],
    facts: CaseFacts,
    planned_works: list[PlannedWork],
    as_of: dt.date | None = None,
) -> ScenarioResult:
    if kind not in SCENARIO_KINDS:
        raise ValueError(f"unknown scenario kind: {kind}")

    baseline = evaluate(rules, facts)

    projected_facts = CaseFacts(
        as_of=as_of or facts.as_of,
        rank_started_on=facts.rank_started_on,
        current_rank=facts.current_rank,
        target_rank=facts.target_rank,
        publications=facts.publications + tuple(
            _as_publication(work, index) for index, work in enumerate(planned_works, start=1)
        ),
        teaching_records=facts.teaching_records,
        service_records=facts.service_records,
    )
    projected = evaluate(rules, projected_facts)

    assumptions_ar = [
        f"يفترض هذا الإسقاط قبول ونشر {len(planned_works)} عملًا مخططًا.",
        "القبول في المجلات غير مضمون، وهذا الرقم ليس تنبؤًا بقرار التحكيم.",
        "حالة فهرسة المجلات تُعاد مراجعتها عند اختيار المجلة فعليًا (§20.3).",
    ]
    assumptions_en = [
        f"This projection assumes {len(planned_works)} planned work(s) are accepted and published.",
        "Journal acceptance is not guaranteed; this is not a prediction of a review decision.",
        "Journal indexing status is re-verified when a journal is actually selected (§20.3).",
    ]
    if kind == "rejection_impact":
        assumptions_ar.append("يقيس هذا السيناريو أثر فقدان الأعمال المخططة، لا أثر قبولها.")
        assumptions_en.append("This scenario measures the impact of losing the planned works.")
    if kind == "indexing_change":
        assumptions_ar.append("يفترض تغيّر فهرسة مجلة مستهدفة قبل النشر.")
        assumptions_en.append("Assumes a target journal's indexing changes before publication.")

    return ScenarioResult(
        kind=kind,
        is_projection=True,
        assumptions_ar=assumptions_ar,
        assumptions_en=assumptions_en,
        baseline=baseline,
        projected=projected,
        added_works=len(planned_works),
    )
