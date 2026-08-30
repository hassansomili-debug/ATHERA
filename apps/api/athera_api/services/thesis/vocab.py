"""مفردات تحويل الرسائل | Thesis-to-papers vocabulary (§23، §24).

مفردات مجال لا تفاصيل تخزين — والنماذج تستورد منها، لا العكس (الدرس
المسجَّل في Sprint 5).
"""
from typing import Final

# §23.3 — ما يستخرجه المفكِّك من الرسالة (ستة عشر عنصرًا).
THESIS_SECTIONS: Final[tuple[str, ...]] = (
    "title", "degree", "year", "research_problem", "questions", "hypotheses",
    "objectives", "theories", "constructs", "population_sample", "instruments",
    "data_sources", "analyses", "results", "tables_figures", "limitations",
    "future_research", "appendices",
)

# §23.4 — أنواع فرص النشر العشرة.
OPPORTUNITY_KINDS: Final[dict[str, tuple[str, str]]] = {
    "independent_question": ("سؤال مستقل", "Independent research question"),
    "sub_model": ("نموذج فرعي قابل للنشر", "Publishable sub-model"),
    "qualitative_phase": ("مرحلة كيفية مستقلة", "Independent qualitative phase"),
    "scale_development": ("ورقة بناء مقياس", "Scale development paper"),
    "antecedents": ("ورقة المحددات", "Antecedents paper"),
    "consequences": ("ورقة النتائج المترتبة", "Consequences paper"),
    "comparative": ("ورقة مقارنة", "Comparative paper"),
    "null_unexpected": ("نتائج سالبة أو غير متوقعة", "Null or unexpected results"),
    "secondary_analysis": ("تحليل ثانوي", "Secondary analysis"),
    "extension": ("ورقة امتداد", "Extension paper"),
}

# §23.5 — نوعا الورقة.
PAPER_KINDS: Final[dict[str, tuple[str, str]]] = {
    "extraction": ("ورقة استخلاص", "Extraction paper"),
    "extension": ("ورقة امتداد", "Extension paper"),
}

# §23.7 — أبعاد مصفوفة التداخل السبعة.
OVERLAP_DIMENSIONS: Final[dict[str, tuple[str, str]]] = {
    "research_question": ("تداخل السؤال البحثي", "Research question overlap"),
    "sample": ("تداخل العينة", "Sample overlap"),
    "variable": ("تداخل المتغيرات", "Variable overlap"),
    "result": ("تداخل النتائج", "Result overlap"),
    "table_figure": ("تداخل الجداول والأشكال", "Table/figure overlap"),
    "text": ("تداخل النص", "Text overlap"),
    "published_output": ("تداخل مع منشور سابق", "Published-output overlap"),
}

# §23.6 — مكونات درجة جاهزية النشر وأوزانها. مجموعها 100 بنص الوثيقة.
READINESS_COMPONENTS: Final[dict[str, tuple[int, str, str]]] = {
    "novelty": (20, "الجدة", "Novelty"),
    "independent_question": (15, "سؤال بحثي مستقل", "Independent research question"),
    "independent_results": (15, "نتائج مستقلة", "Independent results"),
    "method_data_strength": (15, "قوة المنهج والبيانات", "Method and data strength"),
    "topic_currency": (10, "حداثة الموضوع", "Topic currency"),
    "literature_update_feasibility": (10, "قابلية تحديث الأدبيات",
                                      "Literature update feasibility"),
    "journal_fit": (10, "ملاءمة المجلة", "Journal fit"),
    "overlap_risk": (5, "مخاطر التداخل", "Overlap risk"),
}

# §23.6 — المخرجات الخمسة.
READINESS_OUTCOMES: Final[dict[str, tuple[str, str]]] = {
    "ready_to_convert": ("جاهزة للتحويل", "Ready to convert"),
    "needs_reanalysis": ("تحتاج إعادة تحليل", "Needs re-analysis"),
    "needs_theoretical_update": ("تحتاج تحديثًا نظريًا كبيرًا",
                                 "Needs major theoretical update"),
    "merge_with_another": ("تُدمج مع فرصة أخرى", "Merge with another opportunity"),
    "do_not_publish_separately": ("لا تُنشر منفصلة", "Do not publish separately"),
}

# §24.1 — أدوار CRediT الأربعة عشر.
CREDIT_ROLES: Final[dict[str, tuple[str, str]]] = {
    "conceptualization": ("التصور", "Conceptualization"),
    "data_curation": ("تنظيم البيانات", "Data curation"),
    "formal_analysis": ("التحليل الرسمي", "Formal analysis"),
    "funding_acquisition": ("الحصول على التمويل", "Funding acquisition"),
    "investigation": ("الاستقصاء", "Investigation"),
    "methodology": ("المنهجية", "Methodology"),
    "project_administration": ("إدارة المشروع", "Project administration"),
    "resources": ("الموارد", "Resources"),
    "software": ("البرمجيات", "Software"),
    "supervision": ("الإشراف", "Supervision"),
    "validation": ("التحقق", "Validation"),
    "visualization": ("العرض المرئي", "Visualization"),
    "writing_original_draft": ("كتابة المسودة الأصلية", "Writing – original draft"),
    "writing_review_editing": ("المراجعة والتحرير", "Writing – review & editing"),
}

# §24.2 — الأطراف التي يمكن أن تحمل دورًا. لا قيمة تمثل نموذجًا أو أجنتًا:
# «AI لا يكون مؤلفًا» مفروضة بغياب القيمة، لا بفحص نصي.
AUTHORSHIP_PARTY_KINDS: Final[tuple[str, ...]] = ("person", "organization")

# §23.2 — من يحق له استخدام الوحدة.
RIGHTS_BASES: Final[dict[str, tuple[str, str]]] = {
    "thesis_owner": ("صاحب الرسالة", "Thesis owner"),
    "supervisor_with_consent": ("مشرف بموافقة صاحب الرسالة",
                                "Supervisor with the owner's consent"),
    "institution_policy": ("الجهة المالكة وفق سياستها", "Owning institution under its policy"),
}
