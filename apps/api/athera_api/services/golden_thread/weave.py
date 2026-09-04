"""نسج الخيط الذهبي للعرض | Weaving the golden thread for display.

**خطٌّ في الرسم دعوى.** فرسمُ وصلةٍ بين هدفٍ وبناءٍ لأن الاثنين في البحث
نفسه كذبٌ في صورة، وهو أسوأ من فراغ: الفراغ يُرى فيُسأل عنه، والخطُّ
المخترَع يُقرأ إثباتًا ويُنقل إلى قسم المنهجية. فكل وصلةٍ هنا لها **صفٌّ
مخزَّن** يشهد لها، ويُذكر اسم ذلك الصفّ في `basis` — ومن لا صفَّ له لا
وصلة له.

## الحالات الأربع، ومتى تُقال

    known         صفٌّ مخزَّن يصل الطرفين، ولا صفٌّ آخر ينقضه
    conflicting   صفٌّ مخزَّن يقول شيئًا وصفٌّ آخر مخزَّن يقول نقيضه
    needs_review  إمّا أنّ الوصلة **لا تُسجَّل في المنصّة أصلًا**، وإمّا أنّ
                  ما يثبتها ناقصٌ فلا يُحكم بوجودها ولا بغيابها
    missing       الوصلة تُسجَّل، ولا صفَّ لها

والفرق بين الأخيرتين هو كل شيء: «ناقص» تقول للباحث «اربطهما»، و«يحتاج
مراجعة» حين تكون المنصّة هي العاجزة تقول «لا تستطيع أن تربطهما هنا» —
وعرضُ الثانية بلفظ الأولى يرسل الباحث يبحث عن زرٍّ غير موجود.

## المفردة صغيرة كما في بقيّة المستودع

`known | needs_review | missing | conflicting` — هي حالات `BrainFieldView`
و`services/workspace.py` و`MatrixCell` نفسها. ومفردتان للشيء الواحد تجعلان
الوصلة «معلومة» في شاشةٍ و«KNOWN» في أخرى، وهو أكثر عطبٍ تكرارًا هنا.
"""
from __future__ import annotations

from dataclasses import dataclass, field

KNOWN = "known"
NEEDS_REVIEW = "needs_review"
MISSING = "missing"
CONFLICTING = "conflicting"

# مراحل الخيط بترتيبها — كلٌّ تستمدّ مشروعيتها ممّا قبلها (§15.1).
#
# والأسماء مأخوذة من `vocab.THREAD_ELEMENTS` حيث لها مقابل، فلا تُسنّ هنا
# مفردةٌ ثانية لعنصرٍ له اسمٌ في المستودع.
STAGES: tuple[tuple[str, str, str], ...] = (
    ("problem", "المشكلة", "Problem"),
    ("objective", "الأهداف", "Objectives"),
    ("question", "الأسئلة والفروض", "Questions and hypotheses"),
    ("theory", "النظرية", "Theory"),
    ("construct", "البُنى", "Constructs"),
    ("method", "المنهج والأدوات", "Method and instruments"),
    ("analysis", "التحليل", "Analysis"),
    ("finding", "النتائج", "Findings"),
    ("recommendation", "التوصيات", "Recommendations"),
)

STAGE_KEYS: tuple[str, ...] = tuple(key for key, _ar, _en in STAGES)


@dataclass(frozen=True, slots=True)
class Node:
    """عقدةٌ في الخيط — ومصدرُ صفّها معها.

    `origin` اسم الجدول الذي قُرئت منه. وعقدتان بالاسم نفسه من جدولين
    مختلفين ليستا الشيء نفسه: «نتيجة» في `thread_elements` كتبها الباحث،
    و«نتيجة» في `analysis_outputs` أخرجتها تشغيلة — والخلط بينهما يجعل
    توصيةً مسنودةً إلى نصٍّ تُقرأ مسنودةً إلى تحليل.
    """

    id: str
    stage: str
    label: str
    origin: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class Connection:
    """وصلةٌ واحدة، أو غيابُ وصلة — والخيط يجري دائمًا من `source` إلى `target`.

    وحين تكون الحال غير `known` يبقى أحد الطرفين `None`: هو الطرف الذي لا
    وجود له في البيانات. **ولا يُملأ بأقرب عقدةٍ في مرحلته**، فذلك بعينه
    الخطّ المخترَع الذي تمنعه هذه الوحدة؛ والطرف الحاضر وحده هو ما تتحدّث
    عنه الوصلة.
    """

    stage_from: str
    stage_to: str
    state: str
    detail_ar: str
    detail_en: str
    source_id: str | None = None
    source_label: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    # اسم الصفّ المخزَّن الذي يشهد للوصلة — فارغٌ حين لا صفَّ يشهد.
    basis: str | None = None


@dataclass(frozen=True, slots=True)
class ReadNote:
    """ما تعذّر قراءته أو تسجيله — يُعلَن بجانب الرسم لا في حاشية.

    ورسمٌ يسكت عمّا لا يستطيع أن يسجّله يُقرأ «فُحص فلم يوجد».
    """

    key: str
    detail_ar: str
    detail_en: str


# ── مدخلات النسج: صفوفٌ مقروءة، بلا جلسةٍ ولا كائن ORM ──
#
# والسبب هو سبب `Assessment` نفسه في `research_brain/rules.py`: بنيةٌ خالصة
# تجعل كل اشتقاقٍ هنا قابلًا للاختبار بلا قاعدة بيانات، فيصير الإثبات
# ممكنًا لا موعودًا.

@dataclass(frozen=True, slots=True)
class ElementRow:
    id: str
    element_type: str
    label: str
    detail: str | None = None
    theory_id: str | None = None


@dataclass(frozen=True, slots=True)
class LinkRow:
    source_id: str
    target_id: str
    link_type: str


@dataclass(frozen=True, slots=True)
class TheoryRow:
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class ConstructRow:
    id: str
    label: str
    theory_id: str | None = None


@dataclass(frozen=True, slots=True)
class VariableRow:
    id: str
    label: str
    construct_id: str | None
    has_operational_definition: bool
    appears_in_title: bool


@dataclass(frozen=True, slots=True)
class InstrumentRow:
    id: str
    label: str
    measured_variable_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodRow:
    id: str
    label: str
    study_type: str | None = None
    design_family: str | None = None


@dataclass(frozen=True, slots=True)
class PlannedTestRow:
    id: str
    test_key: str
    plan_id: str
    hypothesis_id: str | None = None


@dataclass(frozen=True, slots=True)
class RunRow:
    id: str
    label: str
    plan_id: str
    # متغيّرات قاموس البيانات لنسخة المجموعة التي شُغّلت عليها — مفتاحٌ
    # مخزَّن (`data_dictionaries.variable_id`) لا مطابقةَ أسماء.
    dictionary_variable_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OutputRow:
    id: str
    label: str
    run_id: str
    test_key: str | None = None


@dataclass(frozen=True, slots=True)
class ImplicationRow:
    """الدلالة الإدارية لنتيجة — **مربوطةٌ بمخرَجها بعمود، وبسلسلةٍ مفروضة**.

    `interpretations.output_id` مفتاحٌ إلى `analysis_outputs`، و§18.3 تفرض
    بقيدٍ في القاعدة ألّا تُكتب دلالةٌ إدارية بلا تفسيرٍ نظري، ولا نظريّ
    بلا إحصائي. فهذه **توصيةٌ متعقَّبة إلى نتيجة بمفتاح**، لا مطابقةَ نصّ.

    وهي ليست «التوصية» في `thread_elements`: تلك صفٌّ آخر في جدولٍ آخر بلا
    مفتاح إلى مخرَج. والاثنتان تُعرضان في مرحلة التوصيات، كلٌّ باسم جدولها،
    ولا تُدمجان — ودمجُهما يجعل توصيةً كتبها الباحث تُقرأ مسنودةً إلى تحليل.
    """

    id: str
    label: str
    output_id: str


@dataclass(slots=True)
class ThreadSnapshot:
    """كل ما قُرئ من صفوف هذا البحث — ولا شيء غيره."""

    elements: list[ElementRow] = field(default_factory=list)
    links: list[LinkRow] = field(default_factory=list)
    theories: list[TheoryRow] = field(default_factory=list)
    constructs: list[ConstructRow] = field(default_factory=list)
    variables: list[VariableRow] = field(default_factory=list)
    instruments: list[InstrumentRow] = field(default_factory=list)
    method: MethodRow | None = None
    planned_tests: list[PlannedTestRow] = field(default_factory=list)
    runs: list[RunRow] = field(default_factory=list)
    outputs: list[OutputRow] = field(default_factory=list)
    implications: list[ImplicationRow] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WovenThread:
    """الخيط كما يُعرض — عقدٌ ووصلات وما تعذّر.

    **ولا درجة هنا ولا حقلٌ تُكتب فيه.** و`services/golden_thread/score.py`
    يحسب درجةً لبوابة البروتوكول، وهي قرارٌ آخر لجهةٍ أخرى؛ ونقلُها إلى
    هذه الشاشة يعيد بالضبط ما مُنع في «ما نعرفه»: رقمٌ يخفي الفرق بين خيطٍ
    تنقصه وصلةٌ وخيطٍ ينقصه منهج.
    """

    nodes: tuple[Node, ...] = ()
    connections: tuple[Connection, ...] = ()
    read_notes: tuple[ReadNote, ...] = ()

    def stage_nodes(self, stage: str) -> tuple[Node, ...]:
        return tuple(n for n in self.nodes if n.stage == stage)

    def counts(self) -> dict[str, int]:
        """عدد الوصلات بكل حال — عددٌ لا نسبة، ولا مجموعَ نقاط."""
        out = {KNOWN: 0, NEEDS_REVIEW: 0, MISSING: 0, CONFLICTING: 0}
        for link in self.connections:
            out[link.state] += 1
        return out


# نوعُ عنصر الخيط ← مرحلته في هذا العرض.
#
# و`hypothesis` تُعرض مع `question` لأنّهما جوابُ سؤالٍ واحد للباحث: «ما
# الذي أسأله؟». وما ليس من المراحل التسع (`gap`، `phenomenon`، `discussion`)
# لا يُحشر في أقربها: عقدةٌ في مرحلةٍ ليست لها تجعل الوصلات تُحسب على غير
# أهلها.
_ELEMENT_STAGE: dict[str, str] = {
    "problem": "problem",
    "objective": "objective",
    "question": "question",
    "hypothesis": "question",
    "result": "finding",
    "recommendation": "recommendation",
}

_QUESTION_TYPES = ("question", "hypothesis")


def _related(links: list[LinkRow], element_id: str) -> list[tuple[str, str]]:
    """جيرانُ عقدةٍ في `thread_links` — بالاتجاهين، ومع نوع الرابط.

    والاتجاه لا يُشترط لأنّ العقد قد تُربط من أيّ طرف (`create_link` تقبل
    الطرفين كما وردا)، واشتراطُه يجعل رابطًا **مخزَّنًا** يُقرأ غيابًا —
    وهو الكذب نفسه في الجهة المقابلة.
    """
    out: list[tuple[str, str]] = []
    for link in links:
        if link.source_id == element_id:
            out.append((link.target_id, link.link_type))
        elif link.target_id == element_id:
            out.append((link.source_id, link.link_type))
    return out


def _nodes(snap: ThreadSnapshot) -> list[Node]:
    nodes: list[Node] = []
    for row in snap.elements:
        stage = _ELEMENT_STAGE.get(row.element_type)
        if stage is not None:
            nodes.append(Node(id=row.id, stage=stage, label=row.label,
                              origin="thread_elements", detail=row.detail))
    nodes.extend(Node(id=t.id, stage="theory", label=t.label, origin="theories")
                 for t in snap.theories)
    nodes.extend(Node(id=c.id, stage="construct", label=c.label, origin="constructs")
                 for c in snap.constructs)
    if snap.method is not None:
        nodes.append(Node(id=snap.method.id, stage="method", label=snap.method.label,
                          origin="methods"))
    nodes.extend(Node(id=i.id, stage="method", label=i.label, origin="instruments")
                 for i in snap.instruments)
    nodes.extend(Node(id=r.id, stage="analysis", label=r.label, origin="analysis_runs")
                 for r in snap.runs)
    nodes.extend(Node(id=o.id, stage="finding", label=o.label, origin="analysis_outputs")
                 for o in snap.outputs)
    nodes.extend(Node(id=i.id, stage="recommendation", label=i.label,
                      origin="interpretations") for i in snap.implications)
    return nodes


def _adjacent_by_link(snap: ThreadSnapshot, later: str, earlier: str,
                      out: list[Connection]) -> None:
    """وصلةٌ بين مرحلتين متجاورتين شاهدُها صفٌّ في `thread_links`.

    والسؤال المطروح على كل عقدةٍ متأخّرة هو «ممّ استمدَدْتَ مشروعيتك؟» —
    وهو ترتيب `THREAD_ELEMENTS` نفسه: كل عنصر يستمد مشروعيته ممّا قبله.
    """
    earlier_ids = {row.id: row.label for row in snap.elements
                   if _ELEMENT_STAGE.get(row.element_type) == earlier}
    for row in snap.elements:
        if _ELEMENT_STAGE.get(row.element_type) != later:
            continue
        found = [(other, kind) for other, kind in _related(snap.links, row.id)
                 if other in earlier_ids]
        if found:
            for other, kind in found:
                out.append(Connection(
                    stage_from=earlier, stage_to=later, state=KNOWN,
                    source_id=other, source_label=earlier_ids[other],
                    target_id=row.id, target_label=row.label,
                    basis=f"thread_links.{kind}",
                    detail_ar="رابطٌ مخزَّن بين العنصرين.",
                    detail_en="A stored link joins the two elements."))
            continue
        detail_ar = ("لا رابط مخزَّن يصل هذا العنصر بأيّ عنصرٍ قبله."
                     if earlier_ids else
                     "لا عنصر مسجَّل في المرحلة السابقة يستند إليه هذا العنصر.")
        detail_en = ("No stored link joins this element to any element before it."
                     if earlier_ids else
                     "No element is recorded in the preceding stage for this one to rest on.")
        out.append(Connection(stage_from=earlier, stage_to=later, state=MISSING,
                              target_id=row.id, target_label=row.label,
                              detail_ar=detail_ar, detail_en=detail_en))


def _theory_links(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """السؤال ← النظرية، والنظرية ← البناء — مفتاحان مخزَّنان لا مطابقةَ أسماء."""
    questions = [row for row in snap.elements if row.element_type in _QUESTION_TYPES]
    for theory in snap.theories:
        holders = [row for row in questions if row.theory_id == theory.id]
        if holders:
            for row in holders:
                out.append(Connection(
                    stage_from="question", stage_to="theory", state=KNOWN,
                    source_id=row.id, source_label=row.label,
                    target_id=theory.id, target_label=theory.label,
                    basis="thread_elements.theory_id",
                    detail_ar="السؤال مسجَّلٌ على هذه النظرية في صفّه.",
                    detail_en="The question records this theory on its own row."))
        else:
            out.append(Connection(
                stage_from="question", stage_to="theory", state=MISSING,
                target_id=theory.id, target_label=theory.label,
                detail_ar="لا سؤال ولا فرض مسجَّلٌ على هذه النظرية.",
                detail_en="No question or hypothesis records this theory."))

    for construct in snap.constructs:
        parent = next((t for t in snap.theories if t.id == construct.theory_id), None)
        if parent is not None:
            out.append(Connection(
                stage_from="theory", stage_to="construct", state=KNOWN,
                source_id=parent.id, source_label=parent.label,
                target_id=construct.id, target_label=construct.label,
                basis="constructs.theory_id",
                detail_ar="البناء مسجَّلٌ تحت هذه النظرية في صفّه.",
                detail_en="The construct records this theory on its own row."))
        else:
            out.append(Connection(
                stage_from="theory", stage_to="construct", state=MISSING,
                target_id=construct.id, target_label=construct.label,
                detail_ar="لا نظرية مسجَّلة على هذا البناء في صفّه.",
                detail_en="The construct's row records no theory."))


def _question_to_construct(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """السؤال ← البناء — **بمفتاحين مخزَّنين، ولا مفتاح مباشر بينهما**.

    `QUESTION_USES_CONSTRUCT` ليس له عمود: البناء صفٌّ في `constructs`
    والسؤال صفٌّ في `thread_elements`، ولا مفتاح يصلهما. فما يُعرض هنا يمرّ
    بالنظرية — `thread_elements.theory_id` ثم `constructs.theory_id` — وكلاهما
    مخزَّن. ومطابقةُ أسماء البُنى بنصّ السؤال كانت ستملأ الرسم، وهي تأويلٌ
    لا مفتاح: «النية السلوكية» في هدفٍ لا تثبت وجود بناءٍ بهذا الاسم.

    ولذلك: سؤالٌ لا يصل إلى بناءٍ عبر نظريته حالُه **ناقص** — وهو ما يجعل
    هدفًا يذكر بناءً لم يُسجَّل يظهر فراغًا لا خطًّا.
    """
    for row in snap.elements:
        if row.element_type not in _QUESTION_TYPES:
            continue
        reached = [c for c in snap.constructs
                   if row.theory_id is not None and c.theory_id == row.theory_id]
        if reached:
            for construct in reached:
                out.append(Connection(
                    stage_from="question", stage_to="construct", state=KNOWN,
                    source_id=row.id, source_label=row.label,
                    target_id=construct.id, target_label=construct.label,
                    basis="thread_elements.theory_id → constructs.theory_id",
                    detail_ar="يصل السؤال إلى البناء عبر النظرية المسجَّلة على كليهما.",
                    detail_en="The question reaches the construct through the theory "
                              "recorded on both."))
            continue
        detail_ar = ("لا نظرية مسجَّلة على هذا السؤال، ولا مفتاح مباشر بين سؤالٍ وبناء — "
                     "فلا يُعرف بناءٌ يقيسه."
                     if row.theory_id is None else
                     "نظرية هذا السؤال مسجَّلة، ولا بناء مسجَّلٌ تحتها.")
        detail_en = ("This question records no theory, and no direct key joins a question "
                     "to a construct, so no construct is known for it."
                     if row.theory_id is None else
                     "The question's theory is recorded, but no construct sits under it.")
        out.append(Connection(stage_from="question", stage_to="construct", state=MISSING,
                              source_id=row.id, source_label=row.label,
                              detail_ar=detail_ar, detail_en=detail_en))


def _construct_to_method(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """البناء ← ما يقيسه — و«لا يُقاس» ثلاثُ حالاتٍ لا حالٌ واحدة.

    فبناءٌ بلا متغيّر **ناقص**، وبناءٌ متغيّراته بلا تعريف إجرائي **يحتاج
    مراجعة** (لا يُعلم أتُقاس أم لا)، وبناءٌ لا تقيسه أداةٌ **بينما تقيس
    الأدوات المسجَّلة بُنى أخرى** = **تعارض**: صفّان مخزَّنان يقولان قولين —
    البحث يعلن أنه يدرس هذا البناء، وأدواته تقيس غيره.
    """
    measured: dict[str, list[str]] = {}
    for instrument in snap.instruments:
        for variable_id in instrument.measured_variable_ids:
            measured.setdefault(variable_id, []).append(instrument.id)
    labels = {i.id: i.label for i in snap.instruments}
    anything_measured = bool(measured)

    for construct in snap.constructs:
        own = [v for v in snap.variables if v.construct_id == construct.id]
        hits = [(v, iid) for v in own for iid in measured.get(v.id, ())]
        if hits:
            for variable, instrument_id in hits:
                out.append(Connection(
                    stage_from="construct", stage_to="method", state=KNOWN,
                    source_id=construct.id, source_label=construct.label,
                    target_id=instrument_id, target_label=labels[instrument_id],
                    basis="variables.construct_id → instrument_items.variable_id",
                    detail_ar=f"أداةٌ مسجَّلة تقيس متغيّره «{variable.label}».",
                    detail_en=f"A recorded instrument measures its variable "
                              f"'{variable.label}'."))
            continue
        if not own:
            state, detail_ar, detail_en = (
                MISSING,
                "لا متغيّر مسجَّل لهذا البناء، فلا شيء في المنهج يقيسه.",
                "No variable is recorded for this construct, so nothing in the method "
                "measures it.")
        elif any(not v.has_operational_definition for v in own):
            state, detail_ar, detail_en = (
                NEEDS_REVIEW,
                "متغيّرات هذا البناء بلا تعريف إجرائي مسجَّل، فلا يُحكم أتُقاس أم لا.",
                "This construct's variables record no operational definition, so whether "
                "they are measured cannot be judged.")
        elif anything_measured:
            state, detail_ar, detail_en = (
                CONFLICTING,
                "الأدوات المسجَّلة تقيس متغيّرات بُنًى أخرى ولا تقيس متغيّرات هذا "
                "البناء — والبحث يعلن أنه يدرسه.",
                "The recorded instruments measure other constructs' variables and not "
                "this one's, while the project declares it studies it.")
        else:
            state, detail_ar, detail_en = (
                MISSING,
                "لا أداة مسجَّلة تقيس متغيّرات هذا البناء.",
                "No recorded instrument measures this construct's variables.")
        out.append(Connection(stage_from="construct", stage_to="method", state=state,
                              source_id=construct.id, source_label=construct.label,
                              detail_ar=detail_ar, detail_en=detail_en))


def _analysis_lineage(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """التشغيلة ← متغيّراتها وفروضها — مفتاحان مخزَّنان لا اسمان متقاربان.

    الأول `data_dictionaries.variable_id` على نسخة المجموعة التي شُغّلت
    عليها، والثاني `planned_tests.hypothesis_id` على خطّة التشغيلة. وكلاهما
    عمودٌ في القاعدة، بخلاف `planned_tests.variables` — فهي **قائمة نصوص
    حرّة**، ومطابقتُها بأسماء المتغيّرات تأويلٌ يُنتج وصلةً بلا صفّ.
    """
    variables = {v.id: v.label for v in snap.variables}
    questions = {row.id: row.label for row in snap.elements
                 if row.element_type in _QUESTION_TYPES}

    for run in snap.runs:
        hits = [vid for vid in run.dictionary_variable_ids if vid in variables]
        if hits:
            for vid in hits:
                out.append(Connection(
                    stage_from="method", stage_to="analysis", state=KNOWN,
                    source_id=vid, source_label=variables[vid],
                    target_id=run.id, target_label=run.label,
                    basis="data_dictionaries.variable_id",
                    detail_ar="عمودٌ في قاموس بيانات هذه التشغيلة مربوطٌ بهذا المتغيّر.",
                    detail_en="A column in this run's data dictionary is bound to this "
                              "variable."))
        else:
            out.append(Connection(
                stage_from="method", stage_to="analysis", state=MISSING,
                target_id=run.id, target_label=run.label,
                detail_ar="لا عمود في قاموس بيانات هذه التشغيلة مربوطٌ بمتغيّر مسجَّل.",
                detail_en="No column in this run's data dictionary is bound to a recorded "
                          "variable."))

        bound = [t for t in snap.planned_tests
                 if t.plan_id == run.plan_id and t.hypothesis_id in questions]
        if bound:
            for test in bound:
                out.append(Connection(
                    stage_from="question", stage_to="analysis", state=KNOWN,
                    source_id=test.hypothesis_id,
                    source_label=questions[str(test.hypothesis_id)],
                    target_id=run.id, target_label=run.label,
                    basis="planned_tests.hypothesis_id",
                    detail_ar=f"الاختبار المخطَّط «{test.test_key}» مسجَّلٌ على هذا الفرض.",
                    detail_en=f"Planned test '{test.test_key}' records this hypothesis."))
        else:
            out.append(Connection(
                stage_from="question", stage_to="analysis", state=MISSING,
                target_id=run.id, target_label=run.label,
                detail_ar="لا اختبار مخطَّط في خطّة هذه التشغيلة مربوطٌ بفرضٍ مسجَّل.",
                detail_en="No planned test in this run's plan is bound to a recorded "
                          "hypothesis."))


def _finding_lineage(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """النتيجة ← تشغيلتها — و«نتيجتان» ليستا من جنسٍ واحد.

    مخرَجُ `analysis_outputs` سلسلتُه مفروضةٌ بقيد: `run_id` لا تقبل الفراغ
    (§39)، فوصلته `known` بالبناء. و«النتيجة» التي يكتبها الباحث عنصرًا في
    `thread_elements` لا عمود لها يشير إلى تشغيلة إطلاقًا — فحالُها **يحتاج
    مراجعة**، لا «ناقص»: ليس في المنصّة ما يربطها كي يُقال إنه غاب.
    """
    runs = {r.id: r.label for r in snap.runs}
    for row in snap.outputs:
        out.append(Connection(
            stage_from="analysis", stage_to="finding", state=KNOWN,
            source_id=row.run_id, source_label=runs.get(row.run_id, row.run_id),
            target_id=row.id, target_label=row.label,
            basis="analysis_outputs.run_id",
            detail_ar="مخرَجٌ لا يوجد إلا بتشغيلته — والعمود لا يقبل الفراغ.",
            detail_en="An output cannot exist without its run; the column is not nullable."))
    for element in snap.elements:
        if element.element_type != "result":
            continue
        out.append(Connection(
            stage_from="analysis", stage_to="finding", state=NEEDS_REVIEW,
            target_id=element.id, target_label=element.label,
            detail_ar="نتيجةٌ كُتبت عنصرًا في الخيط، ولا عمود في المنصّة يربطها بتشغيلة "
                      "تحليل — فلا يُقال إنّ سندها غاب ولا إنه حاضر.",
            detail_en="A result written as a thread element; the platform stores no column "
                      "binding it to an analysis run, so its lineage is neither present "
                      "nor absent."))


def _recommendation_lineage(snap: ThreadSnapshot, out: list[Connection]) -> None:
    """التوصية ← نتيجتها — **وهما طريقان لا طريق واحد**.

    الأول مخزَّنٌ بمفتاح: `interpretations.output_id` يربط الدلالة الإدارية
    بمخرَج التحليل الذي اشتُقّت منه، و§18.3 تفرض بقيدٍ في القاعدة ألّا
    تُكتب بلا تفسيرٍ نظري قبلها ولا إحصائيٍّ قبله. فهذه توصيةٌ متعقَّبة
    إلى نتيجة بعمود، وتُرسم `known`.

    والثاني رابطٌ بين عنصرَي خيط: توصيةٌ و«نتيجة» كتبها الباحث في
    `thread_elements`. فإن غاب، فالحال **يحتاج مراجعة** لا «ناقص» — لأنّ
    التوصية في `thread_elements` لا عمود لها إلى `analysis_outputs`
    (`RECOMMENDATION_DERIVED_FROM_FINDING`)، فنصفُ ما قد يسندها لا سبيل إلى
    تسجيله أصلًا، و«ناقص» كانت سترسل الباحث يبحث عن زرٍّ غير موجود.

    **ولا تُدمج التوصيتان.** ودمجُهما — بمطابقة نصّ الدلالة الإدارية بنصّ
    التوصية مثلًا — يجعل توصيةً كتبها الباحث تُقرأ مسنودةً إلى تحليل.
    """
    outputs = {row.id: row.label for row in snap.outputs}
    for row in snap.implications:
        out.append(Connection(
            stage_from="finding", stage_to="recommendation", state=KNOWN,
            source_id=row.output_id,
            source_label=outputs.get(row.output_id, row.output_id),
            target_id=row.id, target_label=row.label,
            basis="interpretations.output_id",
            detail_ar="دلالةٌ إدارية مسجَّلة على هذا المخرَج، ولا تُكتب بلا تفسيرٍ "
                      "نظريّ قبلها ولا إحصائيٍّ قبله (§18.3).",
            detail_en="A managerial implication recorded against this output; it cannot be "
                      "written without a theoretical layer before it and a statistical one "
                      "before that (§18.3)."))

    results = {row.id: row.label for row in snap.elements if row.element_type == "result"}
    for element in snap.elements:
        if element.element_type != "recommendation":
            continue
        found = [(other, kind) for other, kind in _related(snap.links, element.id)
                 if other in results]
        if found:
            for other, kind in found:
                out.append(Connection(
                    stage_from="finding", stage_to="recommendation", state=KNOWN,
                    source_id=other, source_label=results[other],
                    target_id=element.id, target_label=element.label,
                    basis=f"thread_links.{kind}",
                    detail_ar="رابطٌ مخزَّن يسند هذه التوصية إلى نتيجةٍ في الخيط.",
                    detail_en="A stored link grounds this recommendation in a thread result."))
            continue
        out.append(Connection(
            stage_from="finding", stage_to="recommendation", state=NEEDS_REVIEW,
            target_id=element.id, target_label=element.label,
            detail_ar="لا رابط مخزَّن يسند هذه التوصية إلى نتيجة، ولا مفتاح في المنصّة "
                      "يربط توصيةً بمخرَج تحليل — فسندُها غير قابل للإثبات هنا.",
            detail_en="No stored link grounds this recommendation in a result, and the "
                      "platform stores no key from a recommendation to an analysis "
                      "output, so its basis cannot be established here."))


def _read_notes(snap: ThreadSnapshot) -> list[ReadNote]:
    """ما تعذّر — يُعلَن بجانب الرسم ولا يُبتلع.

    ورسمٌ ينقصه خطٌّ لأنّ المنصّة لا تسجّله يُقرأ «فُحص فلم يوجد»، فيذهب
    الباحث يبحث عن زرٍّ ليربط ما لا يُربط.
    """
    notes = [
        ReadNote(
            "recommendation_to_output_not_stored",
            "التوصية التي تكتبها عنصرًا في الخيط لا عمود لها يشير إلى مخرَج تحليل، "
            "فسندُها يُقرأ من روابط الخيط وحدها. والدلالة الإدارية لنتيجةٍ شيءٌ آخر: "
            "هي مربوطةٌ بمخرَجها بعمود، وتُعرض متعقَّبةً إليه — والاثنتان لا تُدمجان.",
            "A recommendation you write as a thread element has no column pointing at an "
            "analysis output, so its basis is read from thread links alone. A finding's "
            "managerial implication is a different thing: it is bound to its output by a "
            "column and is shown traced to it. The two are never merged."),
        ReadNote(
            "question_to_construct_not_stored",
            "لا مفتاح مباشر بين سؤالٍ وبناء. وما يُعرض هنا يمرّ بالنظرية المسجَّلة "
            "على كليهما، ولا يُطابَق باسم البناء في نصّ السؤال.",
            "No direct key joins a question to a construct. What is shown travels through "
            "the theory recorded on both; construct names are not matched against question "
            "text."),
    ]
    if snap.method is None:
        notes.append(ReadNote(
            "method_not_recorded",
            "لا منهج مسجَّل لهذا البحث، فلا يُحكم على ملاءمة تصميمٍ لم يُذكر.",
            "No method is recorded for this project, so the fit of an unrecorded design is "
            "not judged."))
    if not snap.instruments:
        notes.append(ReadNote(
            "instruments_not_recorded",
            "لا أداة قياس مسجَّلة، فغيابُ القياس عن بناءٍ هنا غيابُ تسجيلٍ لا تعارض.",
            "No instrument is recorded, so a construct shown as unmeasured reflects an "
            "unrecorded instrument rather than a contradiction."))
    return notes


def weave(snap: ThreadSnapshot) -> WovenThread:
    """يبني العقد والوصلات من الصفوف — **ولا وصلة بلا صفّ يشهد لها**."""
    connections: list[Connection] = []
    _adjacent_by_link(snap, later="objective", earlier="problem", out=connections)
    _adjacent_by_link(snap, later="question", earlier="objective", out=connections)
    _theory_links(snap, connections)
    _question_to_construct(snap, connections)
    _construct_to_method(snap, connections)
    _analysis_lineage(snap, connections)
    _finding_lineage(snap, connections)
    _recommendation_lineage(snap, connections)
    return WovenThread(nodes=tuple(_nodes(snap)), connections=tuple(connections),
                       read_notes=tuple(_read_notes(snap)))


__all__ = ["CONFLICTING", "Connection", "ConstructRow", "ElementRow", "ImplicationRow",
           "InstrumentRow", "KNOWN", "LinkRow", "MISSING", "MethodRow", "NEEDS_REVIEW",
           "Node", "OutputRow", "PlannedTestRow", "ReadNote", "RunRow", "STAGES",
           "STAGE_KEYS", "TheoryRow", "ThreadSnapshot", "VariableRow", "WovenThread",
           "weave"]
