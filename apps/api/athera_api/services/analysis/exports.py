"""مساعدات الأدوات التحليلية | Analysis tool helpers (§18.2، §47.9).

مبدأ هذا الملف: **ما لا ندعمه يُعلَن**. ادعاء توافق كامل مع صيغة مغلقة بلا
اختبار عليها أسوأ من الاعتراف بحدّها — §47.9 ما زال مفتوحًا.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .vocab import TOOL_SUPPORT


class ExportError(Exception):
    pass


@dataclass(slots=True)
class ToolCapability:
    tool: str
    label_ar: str
    label_en: str
    import_formats: tuple[str, ...]
    export_formats: tuple[str, ...]
    supported_ar: str
    supported_en: str
    not_supported_ar: str
    not_supported_en: str


def capability(tool: str) -> ToolCapability:
    spec = TOOL_SUPPORT.get(tool)
    if spec is None:
        raise ExportError(f"unsupported analysis tool: {tool}")
    return ToolCapability(
        tool=tool, label_ar=str(spec["label_ar"]), label_en=str(spec["label_en"]),
        import_formats=tuple(spec["import_formats"]),  # type: ignore[arg-type]
        export_formats=tuple(spec["export_formats"]),  # type: ignore[arg-type]
        supported_ar=str(spec["supported_ar"]), supported_en=str(spec["supported_en"]),
        not_supported_ar=str(spec["not_supported_ar"]),
        not_supported_en=str(spec["not_supported_en"]),
    )


def all_capabilities() -> list[ToolCapability]:
    return [capability(tool) for tool in TOOL_SUPPORT]


# §18.2 — قوائم فحص SmartPLS. تُعرض قبل التشغيل لا بعده.
MEASUREMENT_MODEL_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("construct_type", "تحديد المنشآت انعكاسية أم تكوينية", "Reflective vs formative constructs"),
    ("indicator_loadings", "تشبعات المؤشرات", "Indicator loadings"),
    ("internal_consistency", "الاتساق الداخلي", "Internal consistency reliability"),
    ("convergent_validity", "الصدق التقاربي (AVE)", "Convergent validity (AVE)"),
    ("discriminant_validity", "الصدق التمايزي (HTMT)", "Discriminant validity (HTMT)"),
    ("collinearity", "التداخل الخطي (VIF)", "Collinearity (VIF)"),
)

STRUCTURAL_MODEL_CHECKS: tuple[tuple[str, str, str], ...] = (
    ("bootstrapping", "التحقق بإعادة العينة", "Bootstrapping"),
    ("path_significance", "دلالة المسارات", "Path significance"),
    ("r_squared", "R² للمتغيرات التابعة", "R² for endogenous constructs"),
    ("q_squared", "Q² للقدرة التنبؤية", "Q² predictive relevance"),
    ("effect_sizes", "أحجام الأثر", "Effect sizes"),
)


@dataclass(slots=True)
class ChecklistItem:
    key: str
    label_ar: str
    label_en: str
    satisfied: bool


@dataclass(slots=True)
class ChecklistResult:
    tool: str
    stage: str
    items: list[ChecklistItem]
    missing: list[str] = field(init=False)

    def __post_init__(self) -> None:
        self.missing = [item.key for item in self.items if not item.satisfied]

    @property
    def is_complete(self) -> bool:
        return not self.missing


def smartpls_checklist(stage: str, satisfied_keys: set[str]) -> ChecklistResult:
    source = {
        "measurement": MEASUREMENT_MODEL_CHECKS,
        "structural": STRUCTURAL_MODEL_CHECKS,
    }.get(stage)
    if source is None:
        raise ExportError(f"unknown SmartPLS stage: {stage}")
    return ChecklistResult(
        tool="smartpls", stage=stage,
        items=[
            ChecklistItem(key=key, label_ar=label_ar, label_en=label_en,
                          satisfied=key in satisfied_keys)
            for key, label_ar, label_en in source
        ],
    )


def spss_syntax(test_kind: str, variables: list[str], *, dataset_label: str) -> str:
    """يولّد سينتاكس **قابلًا للمراجعة** — لا ينفّذ شيئًا.

    §18.1: التحليل يقع في بيئة حسابية، لا داخل نص توليدي. وهذا المخرَج نص
    يراجعه الباحث ويشغّله بنفسه في SPSS.
    """
    if not variables:
        raise ExportError("SPSS syntax needs at least one variable")
    joined = " ".join(variables)
    header = f"* ATHERA generated syntax for {dataset_label}. Review before running."
    templates = {
        "descriptive": f"DESCRIPTIVES VARIABLES={joined}\n  /STATISTICS=MEAN STDDEV MIN MAX.",
        "reliability": f"RELIABILITY\n  /VARIABLES={joined}\n  /MODEL=ALPHA\n  /STATISTICS=SCALE.",
        "correlation": f"CORRELATIONS\n  /VARIABLES={joined}\n  /PRINT=TWOTAIL NOSIG.",
        "regression": (
            f"REGRESSION\n  /DEPENDENT {variables[0]}\n"
            f"  /METHOD=ENTER {' '.join(variables[1:]) or variables[0]}."
        ),
        "t_test": f"T-TEST GROUPS={variables[0]}\n  /VARIABLES={' '.join(variables[1:])}.",
        "anova": f"ONEWAY {' '.join(variables[1:])} BY {variables[0]}\n  /STATISTICS DESCRIPTIVES.",
    }
    body = templates.get(test_kind)
    if body is None:
        raise ExportError(f"no SPSS syntax template for test kind: {test_kind}")
    return f"{header}\n{body}\n"


def nvivo_codebook(codes: list[tuple[str, str, str]]) -> list[dict[str, str]]:
    """§18.2 — دليل ترميز بصيغة مفتوحة قابلة للاستيراد يدويًا.

    لا تبادل مباشر لملفات NVivo الثنائية — وهذا معلن في `capability("nvivo")`.
    """
    if not codes:
        raise ExportError("a codebook needs at least one code")
    return [
        {"code": code, "definition_ar": definition_ar, "example_ar": example_ar}
        for code, definition_ar, example_ar in codes
    ]
