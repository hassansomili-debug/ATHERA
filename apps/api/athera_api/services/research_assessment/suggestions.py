"""من كشفٍ إلى فعلٍ مقترح | From a finding to a suggested action.

**الكشفُ لا يُنشئ التزامًا.** والسلسلة أربع حلقات لا حلقتين:

    كشف  →  فعلٌ مقترح  →  معاينة  →  يقبل الباحث  →  تُنشأ مهمة

والحلقة الرابعة **ليست في هذا الملف ولا في هذا المسار**: نموذجُ المهمة
للمسار «ب»، والوصلُ للمُكامِل، والطلبُ مكتوب في
`docs/integration/track-f-requests.md`. وما هنا ينتهي عند المعاينة.

## لماذا تُفصل الحلقات

محرّكٌ يقرأ نصًّا فيكتب في قائمة مهام الباحث يجعل قراءةَ آلةٍ التزامًا على
إنسان. وكلُّ قواعد السجل اليوم `DRAFT` لم يراجعها مختصّ (`rules.py`)، فلو
أنشأت مهمّةً لأنشأتها قاعدةٌ لم يوقّع عليها أحد. والباحث الذي يجد في
قائمته عشر مهامّ لم يطلبها يتوقّف عن قراءة القائمة كلها — فيسقط التنبيه
الصحيح مع الزائد.

فالاقتراح يُعرض، والمعاينة تُري الباحث **ما سيصير** لو قَبِل، والقبول فعلُه
هو. و«اقترح مهمة للمراجعة» دعوةٌ يقرؤها، لا سطرٌ ظهر في قائمته.

## والمنع بنيويّ لا اتفاقي

`creates_obligation` حقلٌ لا يُمرَّر في البناء وقيمتُه `False` دائمًا، وليس
في هذا الملف استيرادٌ لجلسةٍ ولا لنموذج. والمساران اللذان يعرضانه
`GET` — والفعلُ الذي لا يملك مسارَ كتابةٍ لا يكتب.

## وما يُقال في المعاينة صادقٌ عمّا لا يُعرف

المعاينة لا تدّعي تاريخَ استحقاقٍ ولا مسؤولًا ولا أولوية: هذه حقولُ نموذج
المهمة ولم يصل عقدُه بعد. فتُذكر بأسمائها في `undetermined_fields` بدل أن
تُملأ بقيمٍ مخترعة يقرؤها الباحث قرارًا اتُّخذ عنه.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...research_brain.rules import ScientificRule
from .view import Item, ResearcherReport

# ── حالة السطر بمفردات المستودع نفسها (§`view.py`) — لا مفردة ثانية ──
#
# الخانةُ تقول أين يقع السطر، والحالةُ تقول ما هو. و«التعارضات» خانةٌ
# حالتُها `conflicting`، و«تنبيهات منهجية» أسطرُها `needs_review` لأنّ كلّ
# قاعدةٍ اليوم مسوّدة: مخالفةُ قاعدةٍ لم يراجعها مختصّ **تُراجَع** ولا
# تُعتمد حكمًا.
CATEGORY_STATE: dict[str, str] = {
    "known": "known",
    "missing": "missing",
    "needs_review": "needs_review",
    "conflicts": "conflicting",
    "methodological_alerts": "needs_review",
}

# الخانات التي تستدعي فعلًا. و«ما نعرفه» ليست منها: ما استقام لا يُقترح
# لأجله عمل، واقتراحُ مهمّةٍ عن كل شيء يجعل القائمة ضوضاء.
ACTIONABLE_CATEGORIES: tuple[str, ...] = (
    "missing", "needs_review", "conflicts", "methodological_alerts",
)

# ── الفعلُ المقترح بحسب **باب القاعدة**، لا بحسب معرّفها ──
#
# والمحرّك لا يحمل عمود «علاج»، فاشتقاقُ نصٍّ لكل معرّفٍ على حدة يصير جدولًا
# يتقادم في أوّل قاعدةٍ تُضاف. والباب ثابتٌ ومعلَن (`RuleCategory`)، والفعل
# على مستواه صادق: يقول أين يُنظر ولا يدّعي أنّه يعرف نصّ القاعدة.
RULE_ACTIONS: dict[str, tuple[str, str, str]] = {
    "causality": (
        "review_causal_language",
        "راجع لغة السببية في نصّك، أو سجّل تصميمًا تجريبيًّا يسندها.",
        "Review the causal wording, or record an experimental design that supports it.",
    ),
    "fabrication": (
        "ground_claim_in_output",
        "أرجِع كل رقم وكل ادّعاء إلى مخرَج تحليل مسجَّل، أو احذفه من النصّ.",
        "Trace every number and claim to a recorded analysis output, or remove it.",
    ),
    "design_fit": (
        "review_test_fit",
        "راجع ملاءمة الاختبار لمقاييس متغيّراتك، أو سجّل المقاييس الناقصة.",
        "Review the test's fit to your variables' scales, or record the missing scales.",
    ),
    "evidence": (
        "link_claim_to_evidence",
        "اربط الادّعاء بدليل من مراجع أدرجتَها بقرارك.",
        "Link the claim to evidence from references you included by your own decision.",
    ),
    "provenance": (
        "decide_on_candidate",
        "اعتمد المعلومة المستخرَجة أو ارفضها — فمخرَج نموذج ليس معرفة موثقة.",
        "Approve or reject the extracted information: a model output is not documented "
        "knowledge.",
    ),
    "lineage": (
        "refreeze_dataset",
        "جمّد نسخة البيانات وأعد ربط التشغيلة بها، فسلسلة السند تُقرأ من التجميد.",
        "Freeze the dataset version and re-bind the run to it; lineage is read from the "
        "freeze.",
    ),
}

# فعلُ خانةٍ لا قاعدة خلفها — واقعةٌ مقروءة من صفوف البحث.
CATEGORY_ACTIONS: dict[str, tuple[str, str, str]] = {
    "missing": (
        "record_missing_element",
        "سجّل ما ينقص، أو بيّن لماذا لا ينطبق على تصميم بحثك.",
        "Record what is missing, or state why it does not apply to your design.",
    ),
    "needs_review": (
        "review_and_decide",
        "افتح الموضع المذكور واحسم أمره: اعتماده أو رفضه قرارُك أنت.",
        "Open the cited item and settle it: approving or rejecting it is your decision.",
    ),
    "conflicts": (
        "resolve_conflict",
        "صفّان مسجَّلان يقولان قولين — راجعهما واعتمد أحدهما.",
        "Two recorded rows disagree — review them and settle on one.",
    ),
    "methodological_alerts": (
        "review_methodology",
        "افتح الموضع المذكور وراجعه منهجيًّا.",
        "Open the cited item and review it methodologically.",
    ),
}

DEFAULT_ACTION: tuple[str, str, str] = (
    "review_item",
    "افتح الموضع المذكور وراجعه.",
    "Open the cited item and review it.",
)

# ما لا يعرفه هذا المسار عن المهمة — يُسمَّى ولا يُخترع.
UNDETERMINED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("assignee", "المسؤول", "Assignee"),
    ("due_date", "تاريخ الاستحقاق", "Due date"),
    ("priority", "الأولوية", "Priority"),
)

NOT_CREATED_AR = (
    "هذه معاينة: لم تُنشأ مهمّة، ولا شيء سُجّل في بحثك. والإنشاء لا يقع إلا "
    "بقبولك، وبعد أن يصل عقد المهام."
)
NOT_CREATED_EN = (
    "This is a preview: no task was created and nothing was written to your project. "
    "Creation happens only on your acceptance, once the task contract lands."
)

# العقد الغائب يُسمَّى باسمه، فلا تُقرأ المعاينة وعدًا بزرٍّ موجود.
PENDING_CONTRACT_AR = (
    "عقد إنشاء المهام (المسار «ب») لم يصل بعد، فزرّ القبول غير مفعَّل — "
    "ولم يُخترع له نموذجٌ محلّي كي لا تنقسم المهامّ جدولين."
)
PENDING_CONTRACT_EN = (
    "The task-creation contract (Track B) has not landed, so acceptance is not wired — "
    "and no local model was invented, to avoid splitting tasks across two tables."
)


@dataclass(frozen=True, slots=True)
class SuggestedAction:
    """فعلٌ **مقترح** على كشف — اقتراحٌ يُقرأ، لا التزامٌ نشأ.

    والحقول تحمل سندَ الاقتراح كلَّه: من أين جاء (`rule_id` ورتبتُها
    ومصدرُها)، وعلامَ يقوم (`excerpt` و`entity_ids`)، وما حالُه
    (`state` بمفردات المستودع). فسطرٌ يقول «راجع كذا» بلا هذه لا يُراجَع:
    لا يعرف الباحث أَمِن قاعدةٍ اعتمدها مختصّ جاء أم من سطرٍ في شيفرة.
    """

    key: str
    finding_key: str
    category: str
    state: str
    action_kind: str
    title_ar: str
    title_en: str
    # ما رُصد بالضبط — نصُّ الكشف نفسه، لا إعادةُ صياغةٍ تُفقده دقّته.
    detail_ar: str
    detail_en: str
    rule_id: str | None = None
    rule_status: str | None = None
    rule_is_enforceable: bool = False
    provenance: str | None = None
    excerpt: str | None = None
    entity_ids: tuple[str, ...] = ()
    # **حارسٌ بنيويّ.** لا يُمرَّر في البناء، فلا يستطيع مسارٌ أن يبنيَ
    # اقتراحًا يدّعي أنّه أنشأ شيئًا.
    creates_obligation: bool = field(default=False, init=False)

    @property
    def has_evidence(self) -> bool:
        """هل خلف الاقتراح شاهد؟ وغيابُه يُعلَن ولا يُسكت عنه."""
        return bool(self.excerpt) or bool(self.entity_ids)


@dataclass(frozen=True, slots=True)
class TaskPreview:
    """المهمّة **لو** قَبِل الباحث — نصٌّ يُقرأ، لا صفٌّ كُتب.

    و`created` و`is_preview` ثابتان لا يُمرَّران: معاينةٌ تستطيع أن تقول
    «أُنشئت» ليست معاينة. و`undetermined_fields` تُسمّي ما لا يعرفه هذا
    المسار عن المهمّة بدل أن تملأه بقيمٍ مخترعة.
    """

    action_key: str
    title_ar: str
    title_en: str
    detail_ar: str
    detail_en: str
    source_ar: str
    source_en: str
    excerpt: str | None = None
    entity_ids: tuple[str, ...] = ()
    undetermined_fields: tuple[tuple[str, str, str], ...] = UNDETERMINED_FIELDS
    is_preview: bool = field(default=True, init=False)
    created: bool = field(default=False, init=False)


def _action_for(item: Item, category: str,
                rule: ScientificRule | None) -> tuple[str, str, str]:
    if rule is not None:
        return RULE_ACTIONS.get(rule.category.value, DEFAULT_ACTION)
    return CATEGORY_ACTIONS.get(category, DEFAULT_ACTION)


def _key(category: str, item: Item) -> str:
    """مفتاحٌ ثابت لنفس الكشف — فالمعاينة تُطلب مرّتين فتعطي الشيء نفسه.

    ويدخل فيه الموضعُ لأنّ القاعدة الواحدة تقع على مواضع، ولكلِّ موضعٍ
    فعلُه: «راجع أداة المتغيّر الوسيط» ليست «راجع أداة المتغيّر التابع».
    """
    where = "-".join(item.entity_ids) if item.entity_ids else "-"
    return f"{category}:{item.key}:{where}"


def suggest(report: ResearcherReport,
            rules: dict[str, ScientificRule] | None = None) -> list[SuggestedAction]:
    """يحوّل أسطرَ التقييم إلى أفعالٍ مقترحة — **ولا يكتب شيئًا**.

    و«ما نعرفه» لا يُقترح لأجله فعل: القائمة التي تقترح عملًا عن كل شيء
    لا تُقرأ، فيسقط التنبيه الصحيح مع الزائد.
    """
    index = rules or {}
    # **ملاحظةُ القراءة ليست فجوةً في البحث.** و`view.py` تضعها في «ما ينقص»
    # لأنّها ناقصةٌ فعلًا من التقرير — لكنّ الناقص هناك ناقصٌ **من المنصّة**:
    # «هذا شيءٌ لا نخزّنه فلم نفحصه». واقتراحُ «سجّل ما ينقص» عليها يطلب من
    # الباحث أن يسجّل في حقلٍ غير موجود، ثمّ يلومه أنّه لم يفعل.
    platform_limits = {note.key for note in report.read_notes}
    out: list[SuggestedAction] = []
    for category in ACTIONABLE_CATEGORIES:
        for item in report.category(category):
            if category == "missing" and item.key in platform_limits:
                continue
            rule = index.get(item.rule_id) if item.rule_id else None
            kind, title_ar, title_en = _action_for(item, category, rule)
            out.append(SuggestedAction(
                key=_key(category, item),
                finding_key=item.key,
                category=category,
                state=CATEGORY_STATE[category],
                action_kind=kind,
                title_ar=title_ar,
                title_en=title_en,
                detail_ar=item.detail_ar,
                detail_en=item.detail_en,
                rule_id=item.rule_id,
                rule_status=rule.status.value if rule else None,
                rule_is_enforceable=bool(rule and rule.is_enforceable),
                provenance=rule.provenance if rule else None,
                excerpt=item.excerpt,
                entity_ids=tuple(item.entity_ids),
            ))
    return out


def preview(action: SuggestedAction) -> TaskPreview:
    """يعرض ما ستكون عليه المهمّة لو قَبِل الباحث — **ولا يُنشئها**.

    والسندُ يُنقل إلى المعاينة كاملًا: مهمّةٌ تقول «راجع لغة السببية» بلا
    المقطع الذي أثارها لا تُراجَع، ويعود الباحث إلى الشاشة يبحث عمّا
    قصدته.
    """
    if action.rule_id:
        source_ar = (
            f"قاعدة {action.rule_id}"
            + (f" — رتبتها: {action.rule_status}" if action.rule_status else "")
            + (f" — مصدرها: {action.provenance}" if action.provenance else "")
        )
        source_en = (
            f"Rule {action.rule_id}"
            + (f" — status: {action.rule_status}" if action.rule_status else "")
            + (f" — provenance: {action.provenance}" if action.provenance else "")
        )
    else:
        # واقعةٌ مقروءة من صفوف البحث — تُنسب إلى الخانة لا إلى قاعدة.
        source_ar = f"واقعة مقروءة من صفوف البحث — خانة «{action.category}»"
        source_en = f"A fact read from the project's rows — category '{action.category}'"

    return TaskPreview(
        action_key=action.key,
        title_ar=action.title_ar,
        title_en=action.title_en,
        detail_ar=action.detail_ar,
        detail_en=action.detail_en,
        source_ar=source_ar,
        source_en=source_en,
        excerpt=action.excerpt,
        entity_ids=action.entity_ids,
    )
