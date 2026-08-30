"""مفردات التحليل | Analysis vocabulary (§17، §18، §31.6)."""
from typing import Final

# §17.2 — سلسلة إصدارات البيانات. الترتيب مقصود ولا يُعكس.
DATASET_STATES: Final[dict[str, tuple[str, str]]] = {
    "raw": ("خام — غير قابل للتعديل", "Raw — immutable"),
    "cleaned": ("منظَّف", "Cleaned"),
    "analysis_locked": ("مقفل للتحليل", "Analysis-locked"),
    "derived": ("مشتق", "Derived"),
}

# الانتقالات المسموح بها بين الحالات. لا عودة إلى الخام.
ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "raw": frozenset({"cleaned"}),
    "cleaned": frozenset({"cleaned", "analysis_locked"}),
    "analysis_locked": frozenset({"derived"}),
    "derived": frozenset({"derived"}),
}

# §18.2 — الأدوات المدعومة ومستوى الدعم الصادق لكل منها.
TOOL_SUPPORT: Final[dict[str, dict[str, object]]] = {
    "spss": {
        "label_ar": "SPSS", "label_en": "SPSS",
        "import_formats": ("sav", "csv"),
        "export_formats": ("csv", "sps"),
        "supported_ar": "استيراد وتصدير SAV/CSV وتوليد Syntax قابل للمراجعة.",
        "supported_en": "SAV/CSV import-export and reviewable syntax generation.",
        # ما لا نملكه يُعلَن، لا يُخفى (§47.9).
        "not_supported_ar": "لا تنفيذ داخل SPSS نفسه؛ الناتج ملفات وسينتاكس للمراجعة.",
        "not_supported_en": "No execution inside SPSS itself; output is files and syntax for review.",
    },
    "smartpls": {
        "label_ar": "SmartPLS", "label_en": "SmartPLS",
        "import_formats": ("csv",),
        "export_formats": ("csv", "json"),
        "supported_ar": "تجهيز البيانات وقوائم فحص نموذج القياس والبنيوي.",
        "supported_en": "Data preparation and measurement/structural model checklists.",
        "not_supported_ar": "لا قراءة ولا كتابة لملفات المشروع الثنائية؛ ينتظر §47.9.",
        "not_supported_en": "No read/write of binary project files; pending §47.9.",
    },
    "nvivo": {
        "label_ar": "NVivo", "label_en": "NVivo",
        "import_formats": ("csv", "txt", "docx"),
        "export_formats": ("csv", "json"),
        "supported_ar": "دليل ترميز ومصفوفة موضوعات وقوالب تصدير مفتوحة.",
        "supported_en": "Codebook, theme matrix and open export templates.",
        "not_supported_ar": "لا تبادل مباشر لملفات NVivo الثنائية؛ ينتظر §47.9.",
        "not_supported_en": "No direct exchange of NVivo binary files; pending §47.9.",
    },
    "python": {
        "label_ar": "Python", "label_en": "Python",
        "import_formats": ("csv", "parquet", "json"),
        "export_formats": ("csv", "json", "parquet"),
        "supported_ar": "تشغيل قابل لإعادة الإنتاج مع تثبيت الحزم والبذرة.",
        "supported_en": "Reproducible execution with pinned packages and a fixed seed.",
        "not_supported_ar": "لا وصول إلى الإنترنت أثناء التشغيل.",
        "not_supported_en": "No internet access during execution.",
    },
    "r": {
        "label_ar": "R", "label_en": "R",
        "import_formats": ("csv", "rds"),
        "export_formats": ("csv", "json"),
        "supported_ar": "تشغيل قابل لإعادة الإنتاج مع تثبيت الحزم والبذرة.",
        "supported_en": "Reproducible execution with pinned packages and a fixed seed.",
        "not_supported_ar": "لا وصول إلى الإنترنت أثناء التشغيل.",
        "not_supported_en": "No internet access during execution.",
    },
}

# §18.3 — طبقات التفسير الأربع. منفصلة عمدًا ولا تُدمج.
INTERPRETATION_LAYERS: Final[dict[str, tuple[str, str]]] = {
    "result": ("النتيجة كما ظهرت", "The result as produced"),
    "statistical": ("التفسير الإحصائي", "Statistical interpretation"),
    "theoretical": ("التفسير النظري", "Theoretical interpretation"),
    "managerial": ("الدلالة الإدارية", "Managerial implication"),
}

# أنواع الاختبارات التي تُخطَّط وتُقفل عند G7.
TEST_KINDS: Final[tuple[str, ...]] = (
    "descriptive", "reliability", "validity", "correlation", "regression",
    "anova", "ancova", "t_test", "chi_square", "sem", "pls_sem",
    "mediation", "moderation", "factor_analysis", "thematic_coding",
)

# وسم مصدر الاختبار في التشغيلة.
RUN_TEST_ORIGINS: Final[tuple[str, ...]] = ("planned", "exploratory")

# §18.1 — عناصر بيان إعادة الإنتاج. نقص أي منها يُسقط الوصف «قابل للإعادة».
MANIFEST_FIELDS: Final[dict[str, tuple[str, str]]] = {
    "code_hash": ("بصمة الكود", "Code hash"),
    "runtime": ("بيئة التشغيل وإصدارها", "Runtime and version"),
    "packages": ("الحزم وإصداراتها المثبتة", "Pinned package versions"),
    "dataset_version_id": ("إصدار البيانات المستخدم", "Dataset version used"),
    "random_seed": ("البذرة العشوائية", "Random seed"),
}

# §31.6 — قيود بيئة التنفيذ.
SANDBOX_DEFAULTS: Final[dict[str, object]] = {
    "network_egress": False,
    "max_cpu_seconds": 900,
    "max_memory_mb": 4096,
    "max_wall_seconds": 1800,
    "writable_paths": ("/workspace/out",),
}
