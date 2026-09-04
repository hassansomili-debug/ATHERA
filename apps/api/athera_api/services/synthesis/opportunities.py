"""الفرص البحثية | Research opportunities (PUBRIVA).

**لا فرصة من فجوةٍ لم يعتمدها إنسان.** والاعتماد فعلٌ يُنسب إلى صاحبه، لا
حالٌ تبلغها الفجوة بمرور الوقت أو بارتفاع «قوّتها». والقاعدة نفسها تحرس
ذلك بمفتاحٍ أجنبيٍّ مركّب (ترحيل 0024) — والخدمة تحرسه أيضًا لتُعطي رسالةً
مفهومة بدل خطأ قاعدة.

**والبطاقة تجيب عن سبعة أسئلة، ومنها سؤالان لا يُحذفان:**

    ما الذي لاحظناه؟ · لماذا قد يكون مهمًّا؟ · ما الأدلة؟ ·
    ما الدراسات ذات الصلة؟ · **ما الذي ما زال غير مؤكد؟** ·
    ما نوع الفجوة المحتملة؟ · ما الخطوة التالية؟

و«ما زال غير مؤكد» إلزاميٌّ في القاعدة وفي العقد: بطاقةٌ بلا عدم يقينٍ
معلن تُقرأ خطةً مثبتة، وهي عكس الغرض من هذه الطبقة كلّها.

**والمعاينة ليست إنشاء.** `preview` تبني البطاقة ولا تكتب حرفًا؛ والإنشاء
لا يقع إلا بتأكيدٍ صريح في الطلب. وكذلك «إنشاء مشروع بحثي»: معاينةٌ ثم
تأكيد — ولا يُنشأ بحثٌ بضغطةٍ واحدة.

**ولا مرجعٌ يُقلَب إلى «مُدرَج» في الخفاء.** لا سطر في هذا الملف يكتب
`use_state`؛ قرارُ الإدراج فعلُ باحثٍ في شاشة الفرز، ونقلُه إلى هنا يجعل
إنشاء فرصةٍ يغيّر أدلّة بحثٍ آخر بلا أن يرى أحد.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from ...models.synthesis import GAP_TYPES
from .gaps import GapProposal
from .vocab import GAP_TYPE_LABELS, STRENGTH_LABELS, STRENGTH_MEANING

# الحال الوحيدة التي تُولَد منها فرصة. وهي هنا نصًّا لأن الخدمة تفحصها قبل
# أن تصل القاعدة — فيقرأ الباحث سببًا مفهومًا لا انفجار قيد.
REQUIRED_GAP_STATUS: Final = "approved"


@dataclass(frozen=True, slots=True)
class RelatedStudy:
    """دراسةٌ ذات صلة كما تُعرَض في البطاقة — بعنوانها لا بمعرّفها."""

    source_id: str
    title: str
    role: str
    evidence_scope: str


@dataclass(frozen=True, slots=True)
class OpportunityPreview:
    """بطاقةُ فرصةٍ **قبل أن تُكتب** — سبعةُ أسئلةٍ بأجوبتها.

    وهي مبنيّةٌ من الفجوة نفسها: كلُّ سطرٍ فيها يعود إلى نصٍّ مسجَّل في
    `gap_candidates` أو إلى مرجعٍ في مداها. ولا سطر مولَّد من فراغ.
    """

    gap_candidate_id: str
    gap_type: str
    gap_type_label_ar: str
    what_we_noticed_ar: str
    why_it_might_matter_ar: str
    evidence_basis_ar: str
    related_studies: tuple[RelatedStudy, ...] = ()
    still_uncertain_ar: str = ""
    strength_label_ar: str = ""
    strength_meaning_ar: str = ""
    next_step_ar: str = ""
    # حقولٌ يملؤها الباحث ولا تُملأ نيابةً عنه — تُقترح فارغةً بوصفها أسئلة.
    suggested_phenomenon_ar: str = ""
    suggested_context_ar: str | None = None
    suggested_population_ar: str | None = None
    suggested_constructs_ar: str | None = None
    suggested_contribution_ar: str = ""
    suggested_method_opportunity_ar: str | None = None
    editable_fields: tuple[str, ...] = field(default_factory=tuple)


# **الحقول التي يكتبها الباحث بيده.** والمعاينة تقترح نصًّا أوّليًّا مشتقًّا
# من الفجوة، ولا تدّعي أنه صياغته: الشاشة تقول «راجِع وعدِّل» صراحةً.
EDITABLE_FIELDS: Final = (
    "phenomenon_ar", "context_ar", "population_ar", "constructs_ar",
    "possible_contribution_ar", "methodological_opportunity_ar",
    "evidence_basis_ar", "uncertainties_ar",
)


def build_preview(*, gap_id: str, gap: GapProposal,
                  related: tuple[RelatedStudy, ...]) -> OpportunityPreview:
    """يبني البطاقة **ولا يكتب شيئًا** — والفرق ليس تقنيًّا.

    معاينةٌ تكتب صفًّا تجعل كل استطلاعٍ للفكرة أثرًا دائمًا في البحث، فيمتلئ
    البحث ببطاقاتٍ لم يقصدها أحد ثم لا تُقرأ واحدة منها.
    """
    strength_label = STRENGTH_LABELS[gap.strength]["ar"]
    strength_meaning = STRENGTH_MEANING[gap.strength]["ar"]
    supporting = tuple(r for r in related if r.role == "supporting")
    contradicting = tuple(r for r in related if r.role == "contradicting")
    return OpportunityPreview(
        gap_candidate_id=gap_id,
        gap_type=gap.gap_type,
        gap_type_label_ar=GAP_TYPE_LABELS[gap.gap_type]["ar"],
        what_we_noticed_ar=gap.description_ar,
        why_it_might_matter_ar=gap.why_suggested_ar,
        evidence_basis_ar=(
            f"نُظر في {gap.sources_considered} مرجعًا مُدرَجًا؛ "
            f"{len(supporting)} منها يسند هذه الملاحظة و{len(contradicting)} "
            f"يعارضها. وتوزيع مدى القراءة: "
            + "، ".join(f"{k}: {v}" for k, v in
                        sorted(gap.source_scope_distribution.items()))
            + "."),
        related_studies=related,
        # **السؤال الذي لا يُحذف.** ويُنقل نصُّ الحدود كما سُجِّل مع الفجوة،
        # لا مُعاد صياغةً تُلطّفه.
        still_uncertain_ar=gap.known_limitations_ar,
        strength_label_ar=strength_label,
        strength_meaning_ar=strength_meaning,
        next_step_ar=(
            "الخطوة التالية ليست كتابة ورقة. الخطوة التالية بحثٌ مستقلّ في "
            "الفهارس عن هذه الملاحظة بعينها: إن ظهرت دراساتٌ تغطّيها فقد "
            "أجابت المجموعةُ الحاليةُ ناقصةً، وإن لم تظهر فقد صارت الملاحظة "
            "أقوى — وفي الحالين القرار قرارك لا قرار المنصّة."),
        suggested_phenomenon_ar="",
        suggested_context_ar=None,
        suggested_population_ar=None,
        suggested_constructs_ar=None,
        suggested_contribution_ar="",
        suggested_method_opportunity_ar=None,
        editable_fields=EDITABLE_FIELDS,
    )


def gap_may_become_opportunity(status: str) -> bool:
    """**الاعتماد شرطٌ لا تفضيل.** وأيّ حالٍ أخرى تُردّ برمزٍ له ترجمتان."""
    return status == REQUIRED_GAP_STATUS


@dataclass(frozen=True, slots=True)
class ProjectPreview:
    """معاينةُ «إنشاء مشروع بحثي» — **ما سيقع بالضبط، قبل أن يقع**.

    وثلاثةٌ تُقال صراحةً: ما يُنشأ، وما **لا** يُنشأ، وما لا يتغيّر. فباحثٌ
    ضغط زرًّا وظنّ أن مراجعه ستُنقل إلى البحث الجديد سيكتشف ظنّه بعد أسبوع.
    """

    working_title_ar: str
    from_opportunity_id: str
    gap_type_label_ar: str
    will_create_ar: tuple[str, ...] = ()
    will_not_create_ar: tuple[str, ...] = ()
    unchanged_ar: tuple[str, ...] = ()
    requires_confirmation: bool = True


def build_project_preview(*, opportunity_id: str, title_ar: str,
                          gap_type: str) -> ProjectPreview:
    return ProjectPreview(
        working_title_ar=title_ar,
        from_opportunity_id=opportunity_id,
        gap_type_label_ar=GAP_TYPE_LABELS[gap_type]["ar"],
        will_create_ar=(
            "بحثٌ جديد بعنوانٍ مبدئيّ هو ما تراه أعلاه، وحالُه «مخطَّط».",
            "رابطٌ من هذه الفرصة إلى البحث الجديد، فيُعرف من أين جاء.",
        ),
        will_not_create_ar=(
            "**لن تُنقل مراجعك** إلى البحث الجديد، ولن تُدرَج أيّ دراسة فيه.",
            "لن تُنسخ مصفوفة الأدبيات ولا خلاياها ولا شواهدها.",
            "لن يُنشأ مخطوطٌ ولا خطة تحليل.",
        ),
        unchanged_ar=(
            "بحثك الحالي كما هو: لا تتغيّر حالُ أيّ مرجع فيه، ولا تُعدَّل خلية.",
            "الفجوة تبقى معتمَدة كما اعتمدتها، ولا يمكن سحب اعتمادها بعد "
            "إنشاء فرصةٍ فوقها.",
        ),
        requires_confirmation=True,
    )


__all__ = [
    "EDITABLE_FIELDS",
    "GAP_TYPES",
    "REQUIRED_GAP_STATUS",
    "OpportunityPreview",
    "ProjectPreview",
    "RelatedStudy",
    "build_preview",
    "build_project_preview",
    "gap_may_become_opportunity",
]
