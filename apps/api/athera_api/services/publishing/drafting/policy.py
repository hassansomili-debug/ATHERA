"""سجلّ سياسات الأقسام | The canonical section-policy registry (S5E-D §2).

**موضعٌ واحد يقول ما يجوز في كل قسم.**

كانت القواعد موزّعة على ثلاثة ملفات: الأقسام المفعَّلة في المسار، وأدوار
الأدلة وحجب الأرقام في بناء السياق، والأقسام الوصفية في المدقّق. وقارئٌ
يسأل «ما الذي يجوز في المناقشة؟» كان عليه أن يجمع الجواب من ثلاثة أمكنة —
ومحرِّرٌ يضيف قسمًا عليه أن يتذكّر ثلاثتها. وأول موضع يُنسى يصير ثغرة صامتة:
قسمٌ يُفعَّل بلا مدقّق، أو تُرسل إليه أرقامٌ لا يجوز أن يعيدها.

فكل ما يخصّ قسمًا يُعلَن هنا، ويُقرأ من هنا. والمفتاح **من المفردات
القانونية** لا بجانبها — يُغلق ذلك عند الاستيراد لا عند الاستعمال.

**وأدوار الأدلة تُشتقّ من هيكل S5D** (`outline.DEFAULT_SECTIONS`): هو ما
يقرؤه الباحث في هيكله، فلا يجوز أن يقرأ النموذج غيره. وما يزيد عليه يُعلَن
`extra_roles` صراحةً بسببه المكتوب.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from ...planning import outline as outline_service
from ..vocab import MANUSCRIPT_SECTIONS

# هل يجوز أن يحمل القسم قيمًا إحصائية، وبأي سند؟
#
#   forbidden — لا قيمة إحصائية أصلًا (العنوان مثلًا)
#   grounded  — تجوز **بمخرَج تحليل بعينه** لا غير
#   reused    — تجوز إن كانت مسنَدة **في قسم آخر من المخطوطة نفسها**
Statistics = Literal["forbidden", "grounded", "reused"]

# حال الأدبيات الخارجية قبل تفعيل S5F.
#
#   none    — لا يحتاجها القسم
#   pending — يحتاجها، وتُعلَن ناقصةً ولا تُختلق
#   blocked — لا يُكتب القسم أصلًا قبل S5F
Literature = Literal["none", "pending", "blocked"]


@dataclass(frozen=True, slots=True)
class SectionPolicy:
    """ما يجوز في قسم واحد — كاملًا، في مكان واحد."""

    key: str
    enabled: bool = False

    # ── الأدلة ──
    extra_roles: tuple[str, ...] = ()
    required_any: tuple[str, ...] = ()
    thread_types: tuple[str, ...] = ()

    # ── الأرقام ──
    statistics: Statistics = "forbidden"
    # هل تُحجب القيم الإحصائية من الأدلة **قبل إرسالها** إلى النموذج؟
    redact_statistics: bool = False

    # ── طبيعة المحتوى (§5، §14) ──
    allow_inference: bool = False
    allow_proposal: bool = False
    allow_causal: bool = False
    descriptive_only: bool = False

    # ── الأدبيات (§25) ──
    literature: Literature = "none"
    allow_citations: bool = False

    # ── ما لا يجوز ادّعاؤه في هذا القسم بالذات ──
    forbidden_claims: tuple[str, ...] = ()
    purpose_note_ar: str = ""

    def __post_init__(self) -> None:
        if self.key not in MANUSCRIPT_SECTIONS:
            raise ValueError(
                f"section policy {self.key!r} is not in MANUSCRIPT_SECTIONS; "
                "the manuscript vocabulary is the single authority for section keys")
        if self.redact_statistics and self.statistics == "forbidden":
            raise ValueError(
                f"{self.key}: redacting statistics is meaningless where none may appear")

    @property
    def roles(self) -> tuple[str, ...]:
        """أدوار الأدلة — **من الهيكل** ثم ما أُعلن زيادةً عليه."""
        base = _OUTLINE_ROLES.get(self.key, ())
        return tuple(dict.fromkeys(base + self.extra_roles))

    @property
    def allows_statistics(self) -> bool:
        return self.statistics != "forbidden"


_OUTLINE_ROLES: Final[dict[str, tuple[str, ...]]] = {
    spec.key: spec.roles for spec in outline_service.DEFAULT_SECTIONS
}


# ══════════ السجلّ ══════════
#
# ولا يُفعَّل قسمٌ بلا سياسة، ولا تُكتب سياسةٌ بلا مفتاح قانوني.

_POLICIES: Final[tuple[SectionPolicy, ...]] = (
    SectionPolicy(
        key="title", enabled=True,
        # العنوان يسمّي ما فعلته الدراسة، ولا يَعِد بما لم تفعله.
        forbidden_claims=("causal_language_beyond_design", "generalization"),
        purpose_note_ar="يسمّي ما تفعله الورقة فعلًا، بلغةٍ لا تتجاوز تصميمها.",
    ),
    SectionPolicy(
        key="abstract", enabled=True,
        extra_roles=("sample", "analysis"),
        required_any=("problem", "question"),
        # §5 — الملخص يلخّص ما سُنِد في مكانٍ آخر، ولا يأتي بجديد. فقيمته
        # الإحصائية **معادة** من نتيجة مسنَدة، لا مولَّدة من جديد.
        statistics="reused",
        literature="none",
        purpose_note_ar="يلخّص ما سُنِد في أقسام الورقة، ولا يُدخل واقعة جديدة.",
    ),
    SectionPolicy(
        key="introduction", enabled=True,
        required_any=("problem", "question"),
        thread_types=("problem", "objective", "question"),
        # مقارنةُ الأدبيات تحتاج S5F — وتُعلَن ناقصةً لا تُختلق.
        literature="pending",
        purpose_note_ar="تُقرّر المشكلة وتبرّر أهميتها وتنتهي بالسؤال.",
    ),
    SectionPolicy(
        key="theory", enabled=True,
        required_any=("theory",),
        thread_types=("theory",),
        literature="pending",
        purpose_note_ar="يضع الدراسة في نظريتها الموثقة — ولا يبني نظريةً جديدة.",
    ),
    SectionPolicy(
        key="literature_review",
        # **معطَّل بصدق.** القسم يحتاج بحثًا في سجلّ أدبيات مغلق، وتفعيله
        # اليوم يعني نثرًا بلا مصادر — وهو أسوأ من قسمٍ فارغ معلَن.
        enabled=False, literature="blocked",
        purpose_note_ar="بانتظار البحث العلمي (S5F) — ولا يُكتب من الذاكرة.",
    ),
    SectionPolicy(
        key="method", enabled=True,
        extra_roles=("analysis", "variable"),
        required_any=("methodology", "sample"),
        thread_types=("method", "analysis"),
        purpose_note_ar="التصميم والمجتمع والعينة والأداة وإجراءات الصدق والثبات.",
    ),
    SectionPolicy(
        key="results", enabled=True,
        extra_roles=("sample",),
        required_any=("result",),
        thread_types=("question", "hypothesis", "result"),
        statistics="grounded", redact_statistics=True,
        descriptive_only=True,
        purpose_note_ar="ما وُجد فعلًا — ولا قيمة هنا بلا مخرَج تحليل يحملها.",
    ),
    SectionPolicy(
        key="discussion", enabled=True,
        extra_roles=("question", "limitation"),
        required_any=("result",),
        thread_types=("question", "result", "theory"),
        # §10 — المناقشة تفسير: الاستنتاج مأذون، والمقارنة بالسابق معلّقة.
        statistics="reused", allow_inference=True,
        literature="pending",
        purpose_note_ar="تفسير النتائج في ضوء النظرية الموثقة — والمقارنة بالسابق معلّقة.",
    ),
    SectionPolicy(
        key="conclusion", enabled=True,
        extra_roles=("question", "problem"),
        required_any=("result", "objective"),
        thread_types=("objective", "result"),
        # §11 — لا دليل جديد ولا رقم جديد: الخاتمة تُغلق ما فُتح.
        purpose_note_ar="ما أضافته الدراسة، بحدوده — بلا واقعة جديدة ولا رقم جديد.",
    ),
    SectionPolicy(
        key="limitations", enabled=True,
        extra_roles=("sample", "methodology"),
        # §12 — حدٌّ ذكره الباحث واقعة، وحدٌّ استنتجته المنصّة استنتاج.
        allow_inference=True,
        purpose_note_ar="ما لا تسمح به العينة والتصميم — ويُفصل المذكور عن المستنتَج.",
    ),
    SectionPolicy(
        key="implications", enabled=True,
        extra_roles=("result", "limitation"),
        required_any=("result",),
        # §13 — الدلالات استنتاجٌ أو اقتراح، ولا تُعرض واقعةً مرصودة.
        allow_inference=True, allow_proposal=True,
        purpose_note_ar="ما يترتب عمليًّا — استنتاجًا أو اقتراحًا، لا واقعةً مرصودة.",
    ),
    SectionPolicy(
        key="references", enabled=False, literature="blocked",
        purpose_note_ar="بانتظار البحث العلمي (S5F) — ولا مرجع يُبنى من ذاكرة نموذج.",
    ),
)

POLICIES: Final[dict[str, SectionPolicy]] = {p.key: p for p in _POLICIES}

ENABLED_SECTIONS: Final[frozenset[str]] = frozenset(
    key for key, policy in POLICIES.items() if policy.enabled)

# أقسامٌ معروفةٌ لكنها معطَّلة بسببٍ معلَن — تُقال للباحث ولا تُخفى.
PENDING_SECTIONS: Final[frozenset[str]] = frozenset(
    key for key, policy in POLICIES.items()
    if not policy.enabled and policy.literature == "blocked")


def policy_for(section_key: str) -> SectionPolicy | None:
    return POLICIES.get(section_key)


def ordered_sections() -> tuple[str, ...]:
    """ترتيب الأقسام كما يقرؤها الباحث — بترتيب المفردات القانونية."""
    return tuple(key for key in MANUSCRIPT_SECTIONS if key in POLICIES)


__all__ = ["ENABLED_SECTIONS", "PENDING_SECTIONS", "POLICIES", "Literature",
           "SectionPolicy", "Statistics", "ordered_sections", "policy_for"]
