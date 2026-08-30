"""متطلبات التصميم المنهجي | Methodology requirements (§16).

قوائم تصريحية لا شيفرة شرطية: كل نوع دراسة يعلن عناصره المطلوبة كما وردت
في §16، والخدمة تقارن ما هو مسجَّل بما هو مطلوب وتعلن الناقص.

لماذا تصريحية: لأن إضافة تصميم جديد (Meta-analysis مثلًا) يجب أن تكون
إضافة بيانات، لا تعديل منطق — نفس مبدأ محرك الترقية في §3.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Requirement:
    key: str
    label_ar: str
    label_en: str
    is_blocking: bool = True
    gate: str | None = None


def _r(key, ar, en, blocking=True, gate=None) -> Requirement:
    return Requirement(key=key, label_ar=ar, label_en=en, is_blocking=blocking, gate=gate)


# §16.1 — الدراسات الكمية
QUANTITATIVE: Final[tuple[Requirement, ...]] = (
    _r("variables", "تحديد المتغيرات", "Variable identification", gate="G4"),
    _r("conceptual_model", "النموذج المفاهيمي", "Conceptual model", gate="G3"),
    _r("hypotheses", "الفروض", "Hypotheses", gate="G4"),
    _r("operational_definitions", "التعريفات الإجرائية", "Operational definitions", gate="G4"),
    _r("population", "المجتمع والعينة", "Population and sample", gate="G5"),
    _r("sample_size_justification", "حساب حجم العينة", "Sample size calculation", gate="G5"),
    _r("sampling_strategy", "أسلوب المعاينة", "Sampling strategy", gate="G5"),
    _r("instrument", "المقاييس", "Measurement instrument", gate="G5"),
    _r("instrument_validation", "التحكيم والترجمة", "Expert review and translation",
       blocking=False, gate="G5"),
    _r("pilot_study", "الدراسة الاستطلاعية", "Pilot study", blocking=False, gate="G5"),
    _r("reliability_validity", "الثبات والصدق", "Reliability and validity", gate="G5"),
    _r("common_method_bias", "تحيز المصدر الواحد", "Common method bias",
       blocking=False, gate="G5"),
    _r("analysis_plan", "خطة التحليل", "Analysis plan", gate="G7"),
)

# §16.2 — الدراسات الكيفية
QUALITATIVE: Final[tuple[Requirement, ...]] = (
    _r("design_type", "نوع التصميم", "Design type", gate="G4"),
    _r("participant_selection", "استراتيجية اختيار المشاركين", "Participant selection", gate="G5"),
    _r("interview_guide", "دليل المقابلات", "Interview guide", gate="G5"),
    _r("saturation", "التشبع", "Saturation", gate="G5"),
    _r("recording_transcription", "التسجيل والتفريغ", "Recording and transcription", gate="G5"),
    _r("codebook", "دليل الترميز", "Codebook", gate="G7"),
    _r("analysis_approach", "التحليل الموضوعي/المضمون", "Thematic/content analysis", gate="G7"),
    _r("reflexivity", "الانعكاسية ومسار التدقيق", "Reflexivity and audit trail", gate="G7"),
    _r("member_checking", "التحقق من المشاركين أو المراجعة النظيرة",
       "Member checking or peer debriefing", blocking=False, gate="G7"),
)

# §16.3 — الدراسات المختلطة
MIXED_METHODS: Final[tuple[Requirement, ...]] = (
    _r("sequence", "تتابعي أم متزامن", "Sequential or concurrent", gate="G4"),
    _r("priority", "أولوية المسار", "Strand priority", gate="G4"),
    _r("integration_point", "نقطة التكامل", "Integration point", gate="G4"),
    _r("joint_displays", "العروض المشتركة", "Joint displays", blocking=False, gate="G7"),
    _r("meta_inferences", "الاستدلالات الكلية", "Meta-inferences", gate="G8"),
)

# §16.4 — التجارب
EXPERIMENTAL: Final[tuple[Requirement, ...]] = (
    _r("randomization", "التوزيع العشوائي", "Randomization", gate="G4"),
    _r("conditions", "المعالجات والمجموعات", "Conditions", gate="G4"),
    _r("manipulation_check", "فحص المعالجة", "Manipulation check", gate="G5"),
    _r("power_analysis", "تحليل القوة الإحصائية", "Power analysis", gate="G5"),
    _r("pre_registration", "التسجيل المسبق", "Pre-registration", blocking=False, gate="G4"),
    _r("mediators_moderators", "الوسائط والمعدِّلات", "Mediators and moderators",
       blocking=False, gate="G4"),
)

# §16.5 — المراجعات العلمية
REVIEW: Final[tuple[Requirement, ...]] = (
    _r("review_type", "نوع المراجعة", "Review type", gate="G4"),
    _r("protocol", "بروتوكول البحث", "Review protocol", gate="G2"),
    _r("search_strings", "سلاسل البحث", "Search strings", gate="G5"),
    _r("screening", "الفرز", "Screening", gate="G5"),
    _r("inclusion_exclusion", "معايير التضمين والاستبعاد", "Inclusion/exclusion criteria",
       gate="G5"),
    _r("quality_appraisal", "تقييم الجودة", "Quality appraisal", gate="G7"),
    _r("prisma_tracking", "تتبّع متوافق مع PRISMA", "PRISMA-compatible tracking",
       blocking=False, gate="G7"),
)

REQUIREMENTS: Final[dict[str, tuple[Requirement, ...]]] = {
    "quantitative": QUANTITATIVE,
    "qualitative": QUALITATIVE,
    "mixed_methods": MIXED_METHODS,
    "experimental": EXPERIMENTAL,
    "review": REVIEW,
}


@dataclass(slots=True)
class RequirementStatus:
    requirement: Requirement
    satisfied: bool


@dataclass(slots=True)
class MethodologyGaps:
    study_type: str
    statuses: list[RequirementStatus]

    @property
    def missing_blocking(self) -> list[Requirement]:
        return [s.requirement for s in self.statuses if not s.satisfied and s.requirement.is_blocking]

    @property
    def missing_advisory(self) -> list[Requirement]:
        return [
            s.requirement for s in self.statuses
            if not s.satisfied and not s.requirement.is_blocking
        ]

    @property
    def is_complete(self) -> bool:
        return not self.missing_blocking


def evaluate(study_type: str, satisfied_keys: set[str]) -> MethodologyGaps:
    """يقارن ما هو مسجَّل بما تتطلبه §16 لهذا التصميم."""
    requirements = REQUIREMENTS.get(study_type)
    if requirements is None:
        raise ValueError(f"unknown study type: {study_type}")
    return MethodologyGaps(
        study_type=study_type,
        statuses=[
            RequirementStatus(requirement=req, satisfied=req.key in satisfied_keys)
            for req in requirements
        ],
    )
