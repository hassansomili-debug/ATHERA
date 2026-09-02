"""هيكل الورقة | Manuscript outline (S5D §27، §28).

**هيكلٌ لا نثر.** كل قسم يقول: ما غرضه، وأي أسئلة يجيب، وأي أدلة متاحة له،
وأيها ناقص، وما يجوز ادّعاؤه فيه وما لا يجوز بعد. ولا فقرة مكتوبة — كتابة
الورقة مرحلةٌ أخرى.

**والمناقشة تقول الحقيقة:** سجل الأدبيات مغلق، فمقارنة النتائج بالدراسات
السابقة **بانتظار البحث** — لا مراجع تُخترع لتملأ الفراغ.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..publishing.vocab import MANUSCRIPT_SECTIONS
from .context import ResearchContext

LITERATURE_PENDING_AR: Final = "مقارنة النتائج بالدراسات السابقة — بانتظار البحث العلمي"
LITERATURE_PENDING_EN: Final = "Comparison with prior studies — pending literature search"


@dataclass(frozen=True, slots=True)
class SectionSpec:
    """مواصفة قسم — و`key` **من المفردات القانونية لا بجانبها**.

    كان هذا المفتاح يُكتب هنا حرًّا، فأصدر الهيكل `methods` و`literature`
    بينما `MANUSCRIPT_SECTIONS` تقول `method` و`literature_review`،
    و`manuscript_sections.section_key` عليه قيدٌ بالثانية. فأول تحويل لهيكل
    إلى أقسام مخطوطة كانت القاعدة سترفضه.

    وهو صنف العطب نفسه الذي أنتج عوائق S5D الثلاثة: معرّفٌ يُكتب بجانب
    سجلّه بدل أن يُشتقّ منه. والفحص هنا يُغلق الصنف **عند الاستيراد** لا عند
    الاستعمال، فينكسر البناء لا الإنتاج.
    """

    key: str
    title_ar: str
    title_en: str
    purpose_ar: str
    roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.key not in MANUSCRIPT_SECTIONS:
            raise ValueError(
                f"outline section key {self.key!r} is not in MANUSCRIPT_SECTIONS; "
                "the manuscript vocabulary is the single authority for section keys"
            )


# الهيكل الافتراضي لورقة كمّية — ويُكيَّف بنوع المقالة.
DEFAULT_SECTIONS: Final[tuple[SectionSpec, ...]] = (
    SectionSpec("title", "العنوان", "Title",
                "يسمّي ما تفعله الورقة فعلًا، بلا لغة أقوى من تصميمها.", ()),
    SectionSpec("abstract", "خطة الملخص", "Abstract plan",
                "مشكلة، ثم سؤال، ثم منهج، ثم نتيجة، ثم دلالة — بلا ادعاء زائد.",
                ("problem", "question", "methodology", "result")),
    SectionSpec("introduction", "المقدمة", "Introduction",
                "تُقرّر المشكلة وتبرّر أهميتها وتنتهي بالسؤال.",
                ("problem", "question", "objective")),
    SectionSpec("literature_review", "الإطار النظري والأدبيات", "Literature and theory",
                "يضع الدراسة في نظريتها — والمقارنة بالسابق بانتظار البحث.",
                ("theory",)),
    SectionSpec("method", "المنهجية", "Methods",
                "التصميم والمجتمع والعينة والأداة وإجراءات الصدق والثبات.",
                ("methodology", "sample")),
    SectionSpec("results", "النتائج", "Results",
                "ما وُجد فعلًا — ولا رقم هنا بلا دليل موثق.",
                ("analysis", "result")),
    SectionSpec("discussion", "المناقشة", "Discussion",
                "تفسير النتائج في ضوء النظرية، والمقارنة بالسابق معلّقة.",
                ("result", "theory")),
    SectionSpec("conclusion", "الخاتمة", "Conclusion",
                "ما أضافته الدراسة، بحدوده.", ("objective", "result")),
    SectionSpec("limitations", "حدود الدراسة", "Limitations",
                "ما لا تسمح به العينة والتصميم.", ("limitation",)),
    SectionSpec("implications", "الدلالات والتوصيات", "Implications",
                "ما يترتب عمليًّا — بلا تجاوز لما تسنده النتائج.", ("limitation",)),
)


def build(context: ResearchContext, opportunity, *, article_type: str | None = None
          ) -> list[dict]:
    """يبني الهيكل حتميًّا من اللقطة — **بلا نداء نموذج**.

    فبنية الورقة العلمية معروفة، وما يحتاج ذكاءً هو ربطها بالأدلة — وذلك
    عملٌ حتمي: أي دور دليل يخدم أي قسم.
    """
    proposal = (opportunity.readiness_components or {}).get("proposal", {})
    available = {i.role for i in context.items}
    sections: list[dict] = []

    for spec in DEFAULT_SECTIONS:
        have = [r for r in spec.roles if r in available]
        missing = [r for r in spec.roles if r not in available]
        evidence = [
            {"role": item.role, "memory_id": str(item.memory_id),
             "locator": item.locator, "statement_ar": item.statement[:300]}
            for role in have for item in context.by_role(role)
        ]
        allowed: list[str] = []
        unsupported: list[str] = []

        if spec.key == "results":
            # §26 — لا قيمة إحصائية تظهر حقيقةَ مصدر بلا دليل.
            if "result" in available:
                allowed.append("عرض النتائج الموثقة بمواضعها")
            else:
                unsupported.append("لا نتائج موثقة بعد — لا يُكتب هذا القسم")
        if spec.key == "discussion":
            # §28 — لا مراجع تُخترع.
            unsupported.append(LITERATURE_PENDING_AR)
        if spec.key == "literature_review":
            unsupported.append(LITERATURE_PENDING_AR)
        if spec.key == "title" and opportunity.working_title_ar:
            allowed.append(opportunity.working_title_ar)
        if spec.key == "conclusion" and proposal.get("claim_boundaries_ar"):
            unsupported.append(proposal["claim_boundaries_ar"])

        sections.append({
            "key": spec.key,
            "title_ar": spec.title_ar, "title_en": spec.title_en,
            "purpose_ar": spec.purpose_ar,
            "evidence_roles_available": have,
            "evidence_roles_missing": missing,
            "evidence": evidence,
            "claims_allowed_ar": allowed,
            "claims_unsupported_ar": unsupported,
        })
    return sections
