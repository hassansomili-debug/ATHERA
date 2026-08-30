"""اختبارات الاتساق التسعة | The nine consistency checks (§15.2).

كل كشف يعيد نتيجة بشرح بلغتين وبالعناصر المتورطة فيه — لا رسالة عامة.
وسبعة منها بنيوية تحجب البوابة، واثنان لغويان يخرجان اقتراح مراجعة
(§15.2 مع القرار المسجَّل في خطة السبرنت §2ب).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Final

from .graph import ThreadGraph
from .language import find_causal_language, find_overgeneralization, mentions_theory

STRUCTURAL = "structural"
LINGUISTIC = "linguistic"


@dataclass(slots=True)
class Finding:
    check_key: str
    kind: str
    detail_ar: str
    detail_en: str
    element_ids: list[str] = field(default_factory=list)
    excerpt: str | None = None

    @property
    def is_blocking(self) -> bool:
        """البنيوي يحجب؛ اللغوي اقتراح مراجعة يقرّه الباحث."""
        return self.kind == STRUCTURAL


# ── الكشوفات البنيوية السبعة ──

def objective_without_question(graph: ThreadGraph) -> list[Finding]:
    """1. هدف بلا سؤال."""
    findings = []
    for objective in graph.by_type("objective"):
        linked = [
            link for link in graph.incoming(objective.element_id)
            if link.link_type in ("maps_to", "addresses")
        ]
        if not linked:
            findings.append(Finding(
                "objective_without_question", STRUCTURAL,
                f"الهدف «{objective.label[:80]}» غير مرتبط بأي سؤال بحثي.",
                f"Objective '{objective.label[:80]}' is not linked to any research question.",
                [objective.element_id],
            ))
    return findings


def question_without_analysis(graph: ThreadGraph) -> list[Finding]:
    """2. سؤال بلا تحليل."""
    findings = []
    for question in graph.by_type("question"):
        if not graph.has_path_to_type(question.element_id, "analysis"):
            findings.append(Finding(
                "question_without_analysis", STRUCTURAL,
                f"السؤال «{question.label[:80]}» لا يصل إلى أي تحليل يجيب عنه.",
                f"Question '{question.label[:80]}' does not reach any analysis that answers it.",
                [question.element_id],
            ))
    return findings


def hypothesis_without_measurable_variables(graph: ThreadGraph) -> list[Finding]:
    """3. فرض بلا متغيرات قابلة للقياس."""
    measurable = {
        v.variable_id for v in graph.variables if v.has_operational_definition
    }
    findings = []
    for hypothesis in graph.by_type("hypothesis"):
        linked_variables = {
            link.target_id for link in graph.outgoing(hypothesis.element_id)
        } | {link.source_id for link in graph.incoming(hypothesis.element_id)}
        if not (linked_variables & measurable):
            findings.append(Finding(
                "hypothesis_without_measurable_variables", STRUCTURAL,
                f"الفرض «{hypothesis.label[:80]}» لا يرتبط بمتغيرات لها تعريف إجرائي.",
                f"Hypothesis '{hypothesis.label[:80]}' has no variables with operational definitions.",
                [hypothesis.element_id],
            ))
    return findings


def title_variable_missing_from_instrument(graph: ThreadGraph) -> list[Finding]:
    """4. متغير في العنوان غير موجود في الأداة."""
    measured = {
        variable_id
        for instrument in graph.instruments
        for variable_id in instrument.measured_variable_ids
    }
    findings = []
    for variable in graph.variables:
        if variable.appears_in_title and variable.variable_id not in measured:
            findings.append(Finding(
                "title_variable_missing_from_instrument", STRUCTURAL,
                f"المتغير «{variable.name}» يظهر في العنوان ولا تقيسه أي أداة.",
                f"Variable '{variable.name}' appears in the title but no instrument measures it.",
                [variable.variable_id],
            ))
    return findings


def result_without_question(graph: ThreadGraph) -> list[Finding]:
    """5. نتيجة لا تجيب عن سؤال."""
    findings = []
    for result in graph.by_type("result"):
        answers = [
            link for link in graph.outgoing(result.element_id)
            if link.link_type == "answers"
        ]
        if not answers:
            findings.append(Finding(
                "result_without_question", STRUCTURAL,
                f"النتيجة «{result.label[:80]}» لا تجيب عن أي سؤال بحثي.",
                f"Result '{result.label[:80]}' does not answer any research question.",
                [result.element_id],
            ))
    return findings


def recommendation_without_result(graph: ThreadGraph) -> list[Finding]:
    """6. توصية بلا نتيجة داعمة."""
    findings = []
    for recommendation in graph.by_type("recommendation"):
        supported = [
            link for link in graph.incoming(recommendation.element_id)
            if link.link_type == "supports"
        ]
        if not supported:
            findings.append(Finding(
                "recommendation_without_result", STRUCTURAL,
                f"التوصية «{recommendation.label[:80]}» لا تستند إلى نتيجة.",
                f"Recommendation '{recommendation.label[:80]}' is not grounded in any result.",
                [recommendation.element_id],
            ))
    return findings


def theory_unused_in_discussion(graph: ThreadGraph) -> list[Finding]:
    """7. نظرية مذكورة ولم تُستخدم في المناقشة."""
    findings = []
    for theory in graph.by_type("theory"):
        if not mentions_theory(graph.discussion_text, theory.label):
            findings.append(Finding(
                "theory_unused_in_discussion", STRUCTURAL,
                f"النظرية «{theory.label[:80]}» معتمدة في الإطار ولم تُستخدم في المناقشة.",
                f"Theory '{theory.label[:80]}' is adopted but never used in the discussion.",
                [theory.element_id],
            ))
    return findings


# ── الكشفان اللغويان ──

def causal_language_in_correlational_study(graph: ThreadGraph) -> list[Finding]:
    """9. لغة سببية في دراسة ارتباطية."""
    if graph.method is None:
        return []
    text = "\n".join(filter(None, [graph.results_text, graph.discussion_text]))
    hits = find_causal_language(
        text, design_family=graph.method.design_family, study_type=graph.method.study_type
    )
    return [
        Finding(
            "causal_language_in_correlational_study", LINGUISTIC,
            f"لغة سببية «{hit.matched}» في دراسة غير تجريبية؛ راجع الصياغة أو التصميم.",
            f"Causal wording '{hit.matched}' in a non-experimental design; revise wording or design.",
            [], hit.sentence,
        )
        for hit in hits
    ]


def generalization_beyond_sample(graph: ThreadGraph) -> list[Finding]:
    """8. تعميم أكبر من العينة."""
    if graph.method is None:
        return []
    text = "\n".join(filter(None, [graph.results_text, graph.discussion_text]))
    hits = find_overgeneralization(text, sampling_strategy=graph.method.sampling_strategy)
    return [
        Finding(
            "generalization_beyond_sample", LINGUISTIC,
            f"تعميم «{hit.matched}» يتجاوز حدود عينة غير احتمالية.",
            f"Generalisation '{hit.matched}' exceeds the limits of a non-probability sample.",
            [], hit.sentence,
        )
        for hit in hits
    ]


CHECKS: Final[dict[str, Callable[[ThreadGraph], list[Finding]]]] = {
    "objective_without_question": objective_without_question,
    "question_without_analysis": question_without_analysis,
    "hypothesis_without_measurable_variables": hypothesis_without_measurable_variables,
    "title_variable_missing_from_instrument": title_variable_missing_from_instrument,
    "result_without_question": result_without_question,
    "recommendation_without_result": recommendation_without_result,
    "theory_unused_in_discussion": theory_unused_in_discussion,
    "generalization_beyond_sample": generalization_beyond_sample,
    "causal_language_in_correlational_study": causal_language_in_correlational_study,
}


def run_all(graph: ThreadGraph) -> list[Finding]:
    """يشغّل الكشوفات التسعة كلها ويعيد كل النتائج — لا يتوقف عند الأولى."""
    findings: list[Finding] = []
    for key in CHECKS:
        findings.extend(CHECKS[key](graph))
    return findings
