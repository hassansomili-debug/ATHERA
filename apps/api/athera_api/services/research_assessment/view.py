"""ما يُعرض للباحث | The researcher-facing report.

**خمس خانات، ولا نسبة.**

    ما نعرفه      حقولٌ خلفها ذاكرةٌ موثقة، وقواعدُ فُحصت وسلمت
    ما ينقص       حقولٌ لا سند لها — وهي حالٌ مشروعة في بحثٍ في أوله
    ما يحتاج مراجعة  ما لم يُحكم فيه بعد: مرشّحٌ ينتظر، وقاعدةٌ عجزت عن الفحص
    التعارضات     تناقضٌ **مسجَّل في البيانات**، لا مستنبَط من نصّ
    تنبيهات منهجية  مخالفاتُ القواعد — كلها استشارية اليوم

و«بحثك جاهز بنسبة ٨٢٪» لا تُكتب هنا ولا تُحسب. النسبة تخفي الفرق بين بحثٍ
ينقصه سطرٌ وبحثٍ ينقصه منهج، وتحوّل حالًا مركّبة إلى رقمٍ يطمئن. والقرار
نفسه متّخذٌ في `routers/workspace.py` لشاشة الحال العامة، ولا يُنقض هنا.

**والجهل يُعرض بقدر ما تُعرض المخالفة.** `EvaluationReport.unevaluated` —
ما لم تستطع القاعدة فحصه — يذهب إلى «ما يحتاج مراجعة» ولا يُبتلع. وتقريرٌ
يذكر المخالفات ويصمت عمّا عجز عنه يقرأه الباحث «سليمًا»، وهو أخطر من
مخالفةٍ زائدة.

**ولا شيء هنا يحجب.** كل قاعدة `DRAFT` حتى يراجعها مختصّ، و`blocking` تبقى
فارغة. فما يخرج من هذه الشاشة **مشورةٌ تُقرأ**، لا بوابةٌ تُغلق — ويُقال
ذلك للباحث بنصّه في `advisory_note_ar`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...research_brain.catalogue import RULES
from ...research_brain.rules import EvaluationReport, RuleResult, Verdict, evaluate
from .snapshot import ProjectSnapshot

# حالات المعرفة الأربع — **بمفردات المستودع نفسها**.
#
# `services/workspace.py` تكتبها صغيرةً (`known`، `needs_review`، `missing`،
# `conflicting`)، و`BrainFieldView` تفرض النمط نفسه. وكتابتها هنا كبيرةً
# تجعل مفردتين للشيء الواحد في منتجٍ واحد — وهو أكثر عطبٍ تكرارًا في هذا
# المستودع. فالحالة واحدة، والعرض شأن الواجهة.
KNOWN = "known"
NEEDS_REVIEW = "needs_review"
MISSING = "missing"
CONFLICTING = "conflicting"

# عناوين الخانات بالعربية — لغة الباحث لا مفردات المحرّك.
CATEGORY_LABELS: dict[str, tuple[str, str]] = {
    "known": ("ما نعرفه", "What we know"),
    "missing": ("ما ينقص", "What is missing"),
    "needs_review": ("ما يحتاج مراجعة", "What needs review"),
    "conflicts": ("التعارضات", "Conflicts"),
    "methodological_alerts": ("تنبيهات منهجية", "Methodological alerts"),
}

ADVISORY_NOTE_AR = (
    "كل ما في هذه الصفحة مشورةٌ تُقرأ ولا تُوقف عملًا: القواعد كلها مسوّدة "
    "حتى يراجعها مختصّ، ولا واحدة منها تحجب."
)
ADVISORY_NOTE_EN = (
    "Everything here is advisory and blocks nothing: every rule is a draft until an "
    "expert reviews it."
)

NO_SCORE_NOTE_AR = (
    "ولا تُعرض نسبة جاهزية: النسبة تخفي الفرق بين بحثٍ ينقصه سطرٌ وبحثٍ ينقصه منهج."
)
NO_SCORE_NOTE_EN = (
    "No readiness percentage is shown: a percentage hides the difference between a "
    "project missing a sentence and one missing a method."
)


@dataclass(frozen=True, slots=True)
class Item:
    """سطرٌ واحد في خانة — بسببه وموضعه، لا رسالةً عامة."""

    key: str
    detail_ar: str
    detail_en: str
    # معرّف القاعدة إن كان السطر حكمَ قاعدة — فيُعرف من أين جاء ويُراجَع.
    rule_id: str | None = None
    entity_ids: tuple[str, ...] = ()
    excerpt: str | None = None


@dataclass(frozen=True, slots=True)
class ResearcherReport:
    """التقرير كما يقرؤه الباحث."""

    project_id: str
    title_ar: str
    known: tuple[Item, ...] = ()
    missing: tuple[Item, ...] = ()
    needs_review: tuple[Item, ...] = ()
    conflicts: tuple[Item, ...] = ()
    methodological_alerts: tuple[Item, ...] = ()
    # ما تعذّرت قراءته أصلًا — يُعلَن ولا يُبتلع.
    read_notes: tuple[Item, ...] = ()
    is_advisory_only: bool = True
    blocking_count: int = 0

    def category(self, name: str) -> tuple[Item, ...]:
        return getattr(self, name)


# حقول «ما نعرفه» بأسمائها العربية — تُقرأ من الكتالوج القائم لا تُكتب هنا.
def _field_labels() -> dict[str, tuple[str, str]]:
    from ..workspace import BRAIN_FIELDS

    return {key: (label_ar, label_en) for key, label_ar, label_en, _roles in BRAIN_FIELDS}


def _rule_item(result: RuleResult) -> list[Item]:
    """حكمُ قاعدةٍ يصير أسطرًا بعدد مواضعه — لا سطرًا واحدًا مبهمًا.

    وقاعدةٌ عجزت عن الفحص ولم تُسجّل ملاحظة تصير سطرًا برسالتها العامة:
    «لم يمكن الفحص» خبرٌ يجب أن يصل، ولو بلا موضع.
    """
    if not result.findings:
        return [Item(key=result.rule.id, rule_id=result.rule.id,
                     detail_ar=result.rule.message_ar,
                     detail_en=result.rule.message_en)]
    return [Item(key=result.rule.id, rule_id=result.rule.id,
                 detail_ar=finding.detail_ar, detail_en=finding.detail_en,
                 entity_ids=finding.entity_ids, excerpt=finding.excerpt)
            for finding in result.findings]


def _recorded_facts(snapshot: ProjectSnapshot) -> list[Item]:
    """ما هو **مسجَّلٌ فعلًا** في صفوف البحث — وقائع تُقرأ لا أحكام تُصدَر.

    وهذه هي التي تجعل «ما نعرفه» يصف بحثًا لا محرّكًا: التصميمُ المسجَّل،
    وحجمُ العيّنة، وعددُ التشغيلات والمصادر المُدرَجة. وكلها أعداد وأسماء
    مقروءة من الجداول، **ولا واحد منها نسبةٌ ولا درجة**.

    و«أسلوب المعاينة لا يسمح بالتعميم» ليست قاعدةً جديدة تُسنّ هنا: قيمةُ
    الأسلوب في `SAMPLING_STRATEGIES` معناها المكتوب هو هذا بعينه، فتُقرأ
    كما تُقرأ بقيّة الأعمدة.
    """
    from ...research_brain import ontology as o
    from ..golden_thread.vocab import SAMPLING_STRATEGIES

    graph = snapshot.assessment.graph
    items: list[Item] = []

    # و`getattr` هنا اصطلاح المستودع نفسه في `catalogue.py`: `one_of_kind`
    # يُرجع `Entity` مجرّدة، والحقول المتخصّصة تُقرأ بأسمائها بلا افتراض.
    design = graph.one_of_kind(o.EntityKind.DESIGN)
    if design is not None:
        recorded = " · ".join(filter(None, (getattr(design, "study_type", None),
                                            getattr(design, "design_family", None))))
        items.append(Item(
            key="design_recorded",
            detail_ar=f"التصميم المسجَّل: {recorded or 'بلا نوعٍ مسجَّل'}.",
            detail_en=f"Recorded design: {recorded or 'no type recorded'}.",
            entity_ids=(design.id,)))

    sample = graph.one_of_kind(o.EntityKind.SAMPLE)
    size = getattr(sample, "size", None) if sample is not None else None
    if sample is not None and size is not None:
        label_ar, label_en = size.label()
        items.append(Item(
            key="sample_size_recorded",
            detail_ar=f"حجم العيّنة كما هو مسجَّل في المنهج: {label_ar}.",
            detail_en=f"Sample size as recorded in the method: {label_en}.",
            entity_ids=(sample.id,)))
        strategy = getattr(sample, "sampling_strategy", None)
        if strategy:
            allows = SAMPLING_STRATEGIES[strategy]
            items.append(Item(
                key="sampling_strategy_recorded",
                detail_ar=f"أسلوب المعاينة: {strategy} — "
                          + ("ويسمح بالتعميم على المجتمع."
                             if allows else "ولا يسمح بالتعميم على المجتمع."),
                detail_en=f"Sampling strategy: {strategy} — "
                          + ("generalisation to the population is supported."
                             if allows else "it does not support generalisation."),
                entity_ids=(sample.id,)))

    # **والعدد يأتي بعد اسمه لا قبله.** «1 تشغيلة» و«11 تشغيلة» و«3 تشغيلات»
    # ثلاثُ صيغ في العربية، وقالبٌ واحد يُخرج اثنتين منها خطأً. والصيغة
    # «الاسم: العدد» صحيحة مع كل عدد، ولا تحتاج جدول تصريف.
    counts = (
        ("analyses_recorded", o.EntityKind.ANALYSIS, "تشغيلات التحليل المسجَّلة",
         "Recorded analysis runs"),
        ("findings_recorded", o.EntityKind.FINDING, "النتائج المسجَّلة",
         "Recorded findings"),
        ("claims_recorded", o.EntityKind.CLAIM, "الادّعاءات في المخطوطة",
         "Claims in the manuscript"),
    )
    for key, kind, noun_ar, noun_en in counts:
        rows = graph.of_kind(kind)
        if rows:
            items.append(Item(key=key, detail_ar=f"{noun_ar}: {len(rows)}.",
                              detail_en=f"{noun_en}: {len(rows)}."))

    sources = graph.of_kind(o.EntityKind.SOURCE)
    if sources:
        included = [s for s in sources if getattr(s, "use_state", None) == "included"]
        items.append(Item(
            key="sources_recorded",
            detail_ar=f"مراجع هذا البحث: {len(sources)}، والمُدرَج منها دليلًا "
                      f"بقرارك: {len(included)}.",
            detail_en=f"Sources in this project: {len(sources)}; included as evidence "
                      f"by your decision: {len(included)}."))
    return items


@dataclass(slots=True)
class _Bins:
    known: list[Item] = field(default_factory=list)
    missing: list[Item] = field(default_factory=list)
    needs_review: list[Item] = field(default_factory=list)
    conflicts: list[Item] = field(default_factory=list)
    alerts: list[Item] = field(default_factory=list)


def researcher_report(snapshot: ProjectSnapshot,
                      report: EvaluationReport) -> ResearcherReport:
    """يوزّع اللقطة والحكم على الخانات الخمس — بلا رقمٍ واحد يلخّصهما."""
    labels = _field_labels()
    bins = _Bins()
    bins.known.extend(_recorded_facts(snapshot))

    for row in snapshot.assessment.fields:
        label_ar, label_en = labels.get(row.key, (row.key, row.key))
        if row.state == KNOWN:
            bins.known.append(Item(
                key=row.key,
                detail_ar=f"{label_ar}: موثّقٌ بذاكرةٍ اعتمدتَها.",
                detail_en=f"{label_en}: backed by a memory you approved.",
                entity_ids=row.backing_memory_ids))
        elif row.state == NEEDS_REVIEW:
            bins.needs_review.append(Item(
                key=row.key,
                detail_ar=f"{label_ar}: استُخرج ولم تعتمده بعد.",
                detail_en=f"{label_en}: extracted, not yet approved by you.",
                entity_ids=row.backing_candidate_ids))
        elif row.state == CONFLICTING:  # pragma: no cover - لا مسار يُنتجها اليوم
            bins.conflicts.append(Item(
                key=row.key,
                detail_ar=f"{label_ar}: مصدران موثقان يقولان قولين.",
                detail_en=f"{label_en}: two verified sources disagree."))
        else:
            # **«لا ذاكرة موثقة» لا «لا نعرف شيئًا».** فحجم العيّنة قد يكون
            # مسجَّلًا في المنهج والحقلُ هنا «ناقص»، ومعناهما مختلف: هذا
            # يقول إنه لم يُوثَّق بذاكرةٍ اعتمدها الباحث، لا إنه مجهول.
            # والوقائع المسجَّلة تُعرض بجانبه في «ما نعرفه».
            bins.missing.append(Item(
                key=row.key,
                detail_ar=f"{label_ar}: لا ذاكرة موثقة خلفه بعد — وهذه حالٌ مشروعة "
                          "في بحثٍ في أوله.",
                detail_en=f"{label_en}: no verified memory behind it yet — a legitimate "
                          "state early on."))

    waiting = [row for row in snapshot.assessment.candidates
               if row.status in ("unverified", "unknown")]
    if waiting:
        bins.needs_review.append(Item(
            key="candidates_waiting",
            detail_ar=f"{len(waiting)} معلومة مستخرَجة تنتظر حكمك.",
            detail_en=f"{len(waiting)} extracted facts await your decision."))

    for contradiction in snapshot.contradictions:
        bins.conflicts.append(Item(
            key="contradictory_evidence", detail_ar=contradiction.detail_ar,
            detail_en=contradiction.detail_en, entity_ids=(contradiction.claim_id,)))

    for result in report.results:
        verdict = result.outcome.verdict
        if verdict is Verdict.VIOLATION:
            bins.alerts.extend(_rule_item(result))
        elif verdict is Verdict.INSUFFICIENT_INFORMATION:
            # **«لم أجد شيئًا» ليست سلامة.** الحكم الرابع يُعرض في «ما يحتاج
            # مراجعة» بنصّه، فلا يُقرأ التقرير خاليًا من المخالفات براءةً.
            bins.needs_review.extend(_rule_item(result))
        elif verdict is Verdict.PASS:
            # **«فُحص ولم يقع» لا «فُحص وسلم: <شرط المخالفة>».** والصياغة
            # الأولى كانت تلصق نصّ الشرط بالحكم، فيقرأ الباحث «ادّعاءٌ بلا
            # دليل» في خانة «ما نعرفه» ويظنّها إثباتًا للعطب لا نفيًا له.
            bins.known.append(Item(
                key=result.rule.id, rule_id=result.rule.id,
                detail_ar=f"فُحص ولم يقع: {result.rule.condition_ar}",
                detail_en=f"Checked, did not occur: {result.rule.condition_en}"))

    for note in snapshot.notes:
        bins.missing.append(Item(key=note.key, detail_ar=note.detail_ar,
                                 detail_en=note.detail_en))

    return ResearcherReport(
        project_id=str(snapshot.project_id), title_ar=snapshot.title_ar,
        known=tuple(bins.known), missing=tuple(bins.missing),
        needs_review=tuple(bins.needs_review), conflicts=tuple(bins.conflicts),
        methodological_alerts=tuple(bins.alerts),
        read_notes=tuple(Item(key=n.key, detail_ar=n.detail_ar, detail_en=n.detail_en)
                         for n in snapshot.notes),
        is_advisory_only=not report.blocking,
        blocking_count=len(report.blocking))


def assess(snapshot: ProjectSnapshot) -> tuple[EvaluationReport, ResearcherReport]:
    """يشغّل السجل كاملًا على اللقطة ثم يترجم الحكم إلى خانات الباحث.

    والسجل يُمرَّر كما هو (`RULES`): انتقاءُ قواعدَ عند العرض يجعل قاعدةً
    تُشغَّل في شاشةٍ وتُهمَل في أخرى، فيختلف الحكم على البحث نفسه باختلاف
    الباب الذي دخل منه.
    """
    report = evaluate(snapshot.assessment, RULES)
    return report, researcher_report(snapshot, report)


__all__ = ["ADVISORY_NOTE_AR", "ADVISORY_NOTE_EN", "CATEGORY_LABELS", "CONFLICTING",
           "Item", "KNOWN", "MISSING", "NEEDS_REVIEW", "NO_SCORE_NOTE_AR",
           "NO_SCORE_NOTE_EN", "ResearcherReport", "assess", "researcher_report"]
