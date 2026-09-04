"""التعارضات | Contradictions — and what is not one (PUBRIVA).

**أكثرُ ما يُسمّى تعارضًا ليس تعارضًا.**

  اختلافُ البناءات ليس تعارضًا. دراسةٌ عن أثر التدريب في الأداء وأخرى عن
  أثره في الرضا لا تتعارضان مهما اختلفت نتيجتاهما — هما عن شيئين.

  اختلافُ الصياغة ليس تعارضًا. «علاقة إيجابية دالّة» و«ارتباط موجب ذو
  دلالة» جملتان لقولٍ واحد؛ ومن قابل النصّين حرفًا بحرف صنع تعارضًا من
  قاموس.

  وصمتُ ورقةٍ ليس نصفَ تعارض. «لم تُذكر الدلالة» ليست «غير دالّ».

فالتعارض هنا في أربعٍ لا خامس لها: اتجاهٌ مقابل اتجاه، ودالٌّ مقابل غير
دالّ، وأثرٌ مقابل لا أثر، وخلاصتان مختلفتان — **وكلّها على بناءَين
متقابلين**.

## والتقابل يُشترط تطابق البناءات لا تقاطعها

وهذا اختيارٌ محافظ عن عمد: يفوّت تعارضاتٍ حقيقية، ولا يخترع واحدًا. والخطأ
في هذه الطبقة غير متماثل — تعارضٌ فائت يجده الباحث بنفسه، وتعارضٌ مخترَع
يُكتب في ورقةٍ ثم يُنشر.

## والسياق يُعرَض، ولا تُسمّى دراسةٌ خاطئة

«الدراستان تبدوان متعارضتين، لكن إحداهما درست المستهلكين في السعودية
والأخرى موظفي شركات في الولايات المتحدة» تعيد الباحث إلى التفكير؛
و«الدراستان تتعارضان» تُغلقه. ولا يُقال في أيٍّ منهما إنها خطأ: الحكم في
نزاعٍ علميّ ليس للمنصّة.

**وغيابُ الذكر ليس غيابًا للاختلاف.** فحين لا تُسجَّل بلدان الدراستين لا
يُقال «الظروف واحدة»؛ يُقال إن الفرق **غير مسجَّل في المصفوفة**.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Final

from . import textual
from .corpus import CorpusSnapshot, StudySnapshot
from .vocab import CONTEXT_DIMENSION_LABELS

# العمود الذي تُقرأ منه النتيجة. و«الخلاصة» تُقرأ منه ومن «الفجوات».
RESULT_FIELD: Final = "findings"

CONSTRUCT_FIELD: Final = "constructs"

# ترتيبُ الحسم بين أنواع التعارض: الأقوى دلالةً أولًا.
CONFLICT_PRIORITY: Final = ("direction", "effect_presence", "significance", "conclusion")


@dataclass(frozen=True, slots=True)
class SideSnapshot:
    """طرفٌ واحد بنتيجته وسياقه — **وكلُّ سياقٍ غير مذكورٍ يبقى `None`**."""

    source_id: uuid.UUID
    title: str
    result_ar: str
    direction: str
    significance: str
    evidence_scope: str
    matrix_cell_id: uuid.UUID | None = None
    population_ar: str | None = None
    country_ar: str | None = None
    method_ar: str | None = None
    measurement_ar: str | None = None
    period_year: int | None = None

    @property
    def states_something(self) -> bool:
        return self.direction != "not_stated" or self.significance != "not_stated"


@dataclass(frozen=True, slots=True)
class ContradictionProposal:
    """تعارضٌ محتمل — بطرفيه كليهما، وبأبعاد اختلافهما مسمّاة."""

    construct_a_ar: str
    construct_b_ar: str | None
    relationship_ar: str
    conflict_kind: str
    side_a: SideSnapshot
    side_b: SideSnapshot
    context_divergence: tuple[str, ...] = ()
    context_explanation_ar: str = ""
    shared_terms: tuple[str, ...] = field(default_factory=tuple)


def _side_of(study: StudySnapshot) -> SideSnapshot | None:
    """يبني طرفًا من دراسة — و`None` إن لم تقل نتيجتها شيئًا يُقارَن."""
    cell = study.stated(RESULT_FIELD)
    if cell is None or cell.source_scope == "metadata_only":
        # **ولا طرف من عنوان.** التعارض حكمٌ على نتيجتين مقروءتين.
        return None
    direction = textual.direction_of(cell.value_ar)
    significance = textual.significance_of(cell.value_ar)
    if direction == "not_stated" and significance == "not_stated":
        return None
    context_text = study.text_of("context")
    population_text = study.text_of("population", "sample")
    return SideSnapshot(
        source_id=study.source_id,
        title=study.title,
        result_ar=cell.value_ar or "",
        direction=direction,
        significance=significance,
        evidence_scope=cell.source_scope,
        matrix_cell_id=cell.cell_id,
        population_ar=population_text,
        country_ar=textual.country_in(context_text, population_text),
        method_ar=study.text_of("design", "method"),
        measurement_ar=study.text_of("measures"),
        period_year=study.publication_year,
    )


def constructs_are_comparable(a: frozenset[str], b: frozenset[str]) -> bool:
    """**تطابقٌ لا تقاطع.** «التدريب/الأداء» و«التدريب/الرضا» غير متقابلين.

    ولو قُبل التقاطع لصار كلُّ ما يشترك في كلمةٍ واحدة قابلًا للتعارض —
    وأكثرُ ورقتين في مجالٍ واحد تشتركان في كلمة.
    """
    return bool(a) and bool(b) and a == b


def conflict_between(a: SideSnapshot, b: SideSnapshot) -> str | None:
    """نوعُ التعارض إن وُجد — و`None` حين لا يوجد.

    والصمت لا يُقابَل: طرفٌ لم يذكر دلالته لا يعارض طرفًا ذكرها.
    """
    directions = {a.direction, b.direction}
    if "positive" in directions and "negative" in directions:
        return "direction"
    if "none" in directions and ({"positive", "negative"} & directions):
        return "effect_presence"
    if ({a.significance, b.significance} == {"significant", "not_significant"}):
        return "significance"
    return None


def _conclusion_conflict(a: StudySnapshot, b: StudySnapshot) -> bool:
    """خلاصتان مختلفتان — من تصريحٍ في النصّ لا من فرق حروف."""
    stance_a = textual.stance_of(a.text_of(RESULT_FIELD, "gaps"))
    stance_b = textual.stance_of(b.text_of(RESULT_FIELD, "gaps"))
    return {stance_a, stance_b} == {"supports", "refutes"}


def _divergence(a: SideSnapshot, b: SideSnapshot) -> tuple[str, ...]:
    """الأبعاد التي **سُجّل** فيها اختلاف — ولا يُعدّ الصمت اختلافًا ولا اتفاقًا."""
    out: list[str] = []
    pairs = (
        ("country", a.country_ar, b.country_ar),
        ("population", a.population_ar, b.population_ar),
        ("method", a.method_ar, b.method_ar),
        ("measurement", a.measurement_ar, b.measurement_ar),
    )
    for name, left, right in pairs:
        if left and right and textual.normalize(left) != textual.normalize(right):
            out.append(name)
    if (a.period_year and b.period_year
            and abs(a.period_year - b.period_year) >= 5):
        out.append("period")
    return tuple(out)


def _phrase(name: str, a: SideSnapshot, b: SideSnapshot) -> str:
    values = {
        "country": (a.country_ar, b.country_ar),
        "population": (a.population_ar, b.population_ar),
        "method": (a.method_ar, b.method_ar),
        "measurement": (a.measurement_ar, b.measurement_ar),
        "period": (str(a.period_year), str(b.period_year)),
    }[name]
    label = CONTEXT_DIMENSION_LABELS[name]["ar"]
    return f"{label} ({values[0]} مقابل {values[1]})"


def explain_context(a: SideSnapshot, b: SideSnapshot,
                    divergence: tuple[str, ...]) -> str:
    """التفسير السياقي المحتمَل — **ولا يُسمّى أحدهما خطأ**."""
    if not divergence:
        return (
            "لم يُسجَّل في المصفوفة اختلافٌ بين الدراستين في البلد أو المجتمع أو "
            "المنهج أو القياس أو الفترة. **وغيابُ التسجيل ليس غيابًا للاختلاف**: "
            "قد يكون الفرق قائمًا ولم يُملأ في المصفوفة بعد. فقبل عدّ هذا تعارضًا "
            "علميًّا، أكمِل أعمدة السياق للدراستين."
        )
    parts = "، و".join(_phrase(name, a, b) for name in divergence)
    return (
        f"الدراستان تبدوان متعارضتين، لكنهما تختلفان في: {parts}. "
        "وهذا اختلافٌ في الظروف قد يفسّر اختلاف النتيجتين، ولا يجعل إحداهما "
        "أصوب من الأخرى — النتيجتان قد تكونان صحيحتين كلٌّ في سياقها."
    )


def propose_contradictions(corpus: CorpusSnapshot) -> tuple[ContradictionProposal, ...]:
    """يقترح التعارضات المحتملة — **على بناءَين متقابلين وحدهما**.

    والترتيب حتميّ (بالبناء ثم بعنوانَي الطرفين)، فتُقارن قائمتان.
    """
    sides: list[tuple[StudySnapshot, SideSnapshot, frozenset[str]]] = []
    for study in corpus.studies:
        side = _side_of(study)
        if side is None:
            continue
        cell = study.stated(CONSTRUCT_FIELD)
        if cell is None or cell.source_scope == "metadata_only":
            # **بلا بناءاتٍ مسجَّلة لا تقابل.** ومقارنةُ نتيجتين بلا معرفة
            # ما تقيسانه هي بالضبط اختراع التعارض.
            continue
        sides.append((study, side, textual.terms(cell.value_ar)))

    out: list[ContradictionProposal] = []
    for i in range(len(sides)):
        study_a, side_a, terms_a = sides[i]
        for j in range(i + 1, len(sides)):
            study_b, side_b, terms_b = sides[j]
            if not constructs_are_comparable(terms_a, terms_b):
                continue
            kind = conflict_between(side_a, side_b)
            if kind is None and _conclusion_conflict(study_a, study_b):
                kind = "conclusion"
            if kind is None:
                continue
            divergence = _divergence(side_a, side_b)
            shared = tuple(sorted(terms_a))
            construct_a = study_a.stated(CONSTRUCT_FIELD)
            out.append(ContradictionProposal(
                construct_a_ar=(construct_a.value_ar if construct_a else
                                " · ".join(shared)),
                construct_b_ar=None,
                relationship_ar=(
                    f"نتيجتان مختلفتان على البناءات نفسها: "
                    f"«{side_a.result_ar}» مقابل «{side_b.result_ar}»."),
                conflict_kind=kind,
                side_a=side_a,
                side_b=side_b,
                context_divergence=divergence,
                context_explanation_ar=explain_context(side_a, side_b, divergence),
                shared_terms=shared,
            ))

    out.sort(key=lambda p: (p.construct_a_ar, p.side_a.title, p.side_b.title))
    return tuple(out)


__all__ = [
    "CONFLICT_PRIORITY",
    "CONSTRUCT_FIELD",
    "RESULT_FIELD",
    "ContradictionProposal",
    "SideSnapshot",
    "conflict_between",
    "constructs_are_comparable",
    "explain_context",
    "propose_contradictions",
]
