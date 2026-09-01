"""فهرس الحقول | The extraction field catalogue (§10–§14).

كل حقل يعلن **من يستخرجه**: الكود الحتمي أم النموذج. والقاعدة في §9:
لا يُسأل النموذج عمّا يعرفه الكود يقينًا.

ويعلن **أين يُبحث عنه**: كلمات مفتاحية تختار المقاطع، فلا تُرسل رسالة من
مئتَي صفحة في مطالبة واحدة (§8).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Section(StrEnum):
    """أقسام شاشة المراجعة (§17) — بالترتيب الذي يراه الباحث."""

    METADATA = "metadata"            # بيانات الرسالة
    PROBLEM = "problem"              # مشكلة الدراسة وأهدافها
    QUESTIONS = "questions"          # الأسئلة والفروض
    THEORY = "theory"                # النظرية والإطار
    METHODOLOGY = "methodology"      # المنهجية
    FINDINGS = "findings"            # النتائج
    LIMITS = "limits"                # الحدود والتوصيات


class Method(StrEnum):
    DETERMINISTIC = "deterministic"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class FieldSpec:
    key: str
    section: Section
    label_ar: str
    label_en: str
    method: Method
    # كلمات تدلّ على المقاطع التي يُرجَّح وجود الحقل فيها.
    cues_ar: tuple[str, ...] = ()
    cues_en: tuple[str, ...] = ()
    multi: bool = False
    # حقول قد تحمل أسماء أشخاص — تُعرض للمراجعة ولا تُرقّى تلقائيًا (§20).
    names_people: bool = False


def _f(key, section, ar, en, method, cues_ar=(), cues_en=(), multi=False, people=False):
    return FieldSpec(key, section, ar, en, method, cues_ar, cues_en, multi, people)


FIELD_CATALOGUE: Final[tuple[FieldSpec, ...]] = (
    # ── §10 بيانات الرسالة ──
    _f("page_count", Section.METADATA, "عدد الصفحات", "Page count", Method.DETERMINISTIC),
    _f("source_filename", Section.METADATA, "اسم الملف", "Source filename", Method.DETERMINISTIC),
    _f("title_ar", Section.METADATA, "عنوان الرسالة بالعربية", "Thesis title (Arabic)", Method.MODEL,
       ("عنوان الرسالة", "رسالة مقدمة", "أطروحة"), ("thesis", "dissertation", "submitted")),
    _f("title_en", Section.METADATA, "عنوان الرسالة بالإنجليزية", "Thesis title (English)", Method.MODEL,
       ("عنوان",), ("thesis title", "dissertation")),
    _f("student_name", Section.METADATA, "اسم الباحث", "Researcher name", Method.MODEL,
       ("إعداد الطالب", "إعداد الباحث", "مقدمة من"), ("submitted by", "by student"), people=True),
    _f("degree", Section.METADATA, "الدرجة", "Degree", Method.MODEL,
       ("درجة الماجستير", "درجة الدكتوراه", "استكمالًا لمتطلبات"),
       ("master", "doctor of philosophy", "ph.d")),
    _f("university", Section.METADATA, "الجامعة", "University", Method.MODEL,
       ("جامعة",), ("university",)),
    _f("college", Section.METADATA, "الكلية", "College", Method.MODEL, ("كلية",), ("college", "faculty")),
    _f("department", Section.METADATA, "القسم", "Department", Method.MODEL, ("قسم",), ("department",)),
    _f("year", Section.METADATA, "السنة", "Year", Method.MODEL, ("هـ", "م", "العام الجامعي"), ("year",)),
    _f("defense_date", Section.METADATA, "تاريخ المناقشة", "Defense date", Method.MODEL,
       ("تاريخ المناقشة", "نوقشت"), ("defended", "defense date")),
    _f("supervisors", Section.METADATA, "المشرفون", "Supervisors", Method.MODEL,
       ("إشراف", "المشرف"), ("supervised by", "supervisor"), multi=True, people=True),

    # ── §11 بنية البحث ──
    _f("background", Section.PROBLEM, "خلفية الدراسة", "Background", Method.MODEL,
       ("خلفية", "تمهيد"), ("background", "introduction")),
    _f("problem", Section.PROBLEM, "مشكلة الدراسة", "Research problem", Method.MODEL,
       ("مشكلة الدراسة", "مشكلة البحث"), ("research problem", "problem statement")),
    _f("gap", Section.PROBLEM, "الفجوة البحثية", "Research gap", Method.MODEL,
       ("الفجوة", "ندرة الدراسات"), ("research gap", "gap in the literature")),
    _f("objectives", Section.PROBLEM, "أهداف الدراسة", "Objectives", Method.MODEL,
       ("أهداف الدراسة", "تهدف الدراسة"), ("objectives", "aims"), multi=True),
    _f("questions", Section.QUESTIONS, "أسئلة الدراسة", "Research questions", Method.MODEL,
       ("أسئلة الدراسة", "تساؤلات"), ("research questions",), multi=True),
    _f("hypotheses", Section.QUESTIONS, "الفروض", "Hypotheses", Method.MODEL,
       ("فرضيات", "فروض الدراسة"), ("hypotheses", "hypothesis"), multi=True),
    _f("theoretical_framework", Section.THEORY, "الإطار النظري", "Theoretical framework", Method.MODEL,
       ("الإطار النظري", "نظرية"), ("theoretical framework", "theory")),
    _f("constructs", Section.THEORY, "المتغيرات والبناءات", "Constructs and variables", Method.MODEL,
       ("المتغيرات", "المتغير المستقل", "المتغير التابع"),
       ("variables", "independent variable", "dependent variable"), multi=True),

    # ── §12 المنهجية ──
    _f("design", Section.METHODOLOGY, "تصميم الدراسة", "Research design", Method.MODEL,
       ("منهج الدراسة", "التصميم"), ("research design", "methodology")),
    _f("approach", Section.METHODOLOGY, "النوع (كمي/كيفي/مختلط)", "Approach", Method.MODEL,
       ("كمي", "كيفي", "مختلط"), ("quantitative", "qualitative", "mixed methods")),
    _f("population", Section.METHODOLOGY, "مجتمع الدراسة", "Population", Method.MODEL,
       ("مجتمع الدراسة",), ("population",)),
    _f("sample_size", Section.METHODOLOGY, "حجم العينة", "Sample size", Method.MODEL,
       ("حجم العينة", "بلغ عدد"), ("sample size", "n =")),
    _f("sampling", Section.METHODOLOGY, "أسلوب المعاينة", "Sampling technique", Method.MODEL,
       ("أسلوب العينة", "العينة العشوائية"), ("sampling technique", "random sample")),
    _f("instruments", Section.METHODOLOGY, "أدوات جمع البيانات", "Instruments", Method.MODEL,
       ("الاستبانة", "أداة الدراسة", "المقابلة"), ("questionnaire", "instrument", "interview"), multi=True),
    _f("validity", Section.METHODOLOGY, "إجراءات الصدق", "Validity procedures", Method.MODEL,
       ("صدق الأداة", "الصدق"), ("validity",)),
    _f("reliability", Section.METHODOLOGY, "إجراءات الثبات", "Reliability procedures", Method.MODEL,
       ("ثبات الأداة", "ألفا كرونباخ"), ("reliability", "cronbach")),
    _f("analysis_methods", Section.METHODOLOGY, "أساليب التحليل", "Analysis methods", Method.MODEL,
       ("الأساليب الإحصائية", "تحليل"), ("statistical analysis", "analysis method"), multi=True),
    _f("software", Section.METHODOLOGY, "البرمجيات", "Software", Method.MODEL,
       ("SPSS", "AMOS", "SmartPLS", "NVivo"), ("spss", "amos", "smartpls", "nvivo"), multi=True),

    # ── §13 النتائج ──
    _f("primary_findings", Section.FINDINGS, "النتائج الرئيسة", "Primary findings", Method.MODEL,
       ("النتائج", "توصلت الدراسة"), ("findings", "results"), multi=True),
    _f("hypothesis_results", Section.FINDINGS, "نتائج الفروض", "Hypothesis results", Method.MODEL,
       ("قبول الفرض", "رفض الفرض"), ("supported", "rejected hypothesis"), multi=True),
    _f("qualitative_themes", Section.FINDINGS, "الثيمات الكيفية", "Qualitative themes", Method.MODEL,
       ("الثيمات", "المحاور"), ("themes",), multi=True),

    # ── §14 الحدود والتوصيات ──
    _f("limitations", Section.LIMITS, "حدود الدراسة", "Limitations", Method.MODEL,
       ("حدود الدراسة", "محددات"), ("limitations",), multi=True),
    _f("recommendations", Section.LIMITS, "التوصيات", "Recommendations", Method.MODEL,
       ("التوصيات", "يوصي الباحث"), ("recommendations",), multi=True),
    _f("future_research", Section.LIMITS, "بحوث مستقبلية", "Future research", Method.MODEL,
       ("دراسات مستقبلية", "بحوث مقترحة"), ("future research",), multi=True),
)

BY_KEY: Final[dict[str, FieldSpec]] = {spec.key: spec for spec in FIELD_CATALOGUE}

# فئة الذاكرة لكل قسم (§7.3) — تُستعمل عند الترقية بعد اعتماد الباحث.
#
# **ولا فئة جديدة تُخترع هنا:** الفئات السبع قائمة في `MEMORY_CATEGORIES`،
# وما يفعله هذا الجدول هو اختيار الأنسب منها لا توسيع القائمة. فبيانات
# الرسالة حقائق باحث، وسؤالها ونظريتها ومنهجها قرارات مشروع، ونتائجها دليل
# مصدره الرسالة نفسها.
SECTION_MEMORY_CATEGORY: Final[dict[Section, str]] = {
    Section.METADATA: "researcher_fact",
    Section.PROBLEM: "project_decision",
    Section.QUESTIONS: "project_decision",
    Section.THEORY: "project_decision",
    Section.METHODOLOGY: "project_decision",
    Section.FINDINGS: "verified_evidence",
    Section.LIMITS: "project_decision",
}


def memory_category_for(spec: FieldSpec) -> str:
    return SECTION_MEMORY_CATEGORY[spec.section]

MODEL_FIELDS: Final = tuple(f for f in FIELD_CATALOGUE if f.method is Method.MODEL)
DETERMINISTIC_FIELDS: Final = tuple(f for f in FIELD_CATALOGUE if f.method is Method.DETERMINISTIC)
