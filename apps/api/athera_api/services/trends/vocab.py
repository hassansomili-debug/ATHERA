"""مفردات الذكاء الاستباقي | Trend intelligence vocabulary (§51)."""
from typing import Final

# §51.1 — أنماط الاكتشاف التسعة.
DETECTION_PATTERNS: Final[dict[str, tuple[str, str]]] = {
    "topic_emergence": ("ظهور موضوع جديد", "Topic emergence"),
    "topic_acceleration": ("تسارع موضوع قائم", "Topic acceleration"),
    "declining_topic": ("انحسار موضوع", "Declining topic"),
    "theory_shift": ("تحول نظري", "Theory shift"),
    "method_shift": ("تحول منهجي", "Method shift"),
    "geographic_gap": ("فجوة جغرافية", "Geographic gap"),
    "contradictory_findings": ("تناقض في النتائج", "Contradictory findings"),
    "replication_opportunity": ("فرصة إعادة اختبار", "Replication opportunity"),
    "data_opportunity": ("فرصة بيانات متاحة", "Data opportunity"),
}

# §51.2 — ملفات المراقبة الستة.
WATCHLIST_KINDS: Final[dict[str, tuple[str, str]]] = {
    "personal": ("مراقبة شخصية مرتبطة بتخصص الباحث", "Personal watchlist tied to the field"),
    "project": ("مراقبة لكل مشروع نشط", "Per-active-project watchlist"),
    "construct": ("مراقبة نظرية أو متغير أو منهج", "Theory, variable or method watchlist"),
    "journal": ("مراقبة المجلات المستهدفة", "Target journals watchlist"),
    "supervised_thesis": ("مراقبة موضوعات الرسائل المشرَف عليها", "Supervised theses watchlist"),
    "competitive": ("مراقبة تنافسية لباحثين أو مراكز", "Competitive watchlist"),
}

# §51.3 — معايير درجة الفرصة الثمانية وأوزانها. مجموعها 100 بنص الوثيقة.
OPPORTUNITY_CRITERIA: Final[dict[str, tuple[int, str, str]]] = {
    "novelty": (20, "الجدة", "Novelty"),
    "momentum": (15, "الزخم", "Momentum"),
    "research_gap": (15, "الفجوة", "Research gap"),
    "researcher_fit": (15, "ملاءمة الباحث", "Researcher fit"),
    "data_feasibility": (10, "قابلية الحصول على البيانات", "Data feasibility"),
    "journal_fit": (10, "ملاءمة المجلات", "Journal fit"),
    "promotion_value": (10, "قيمة الترقية", "Promotion value"),
    "execution_risk": (5, "مخاطر التنفيذ", "Execution risk"),
}

# مصادر الإشارات المقبولة. `model_output` مسجَّل لكنه **لا يُحتسب** (§51.1).
SIGNAL_SOURCE_TYPES: Final[dict[str, bool]] = {
    "openalex": True,
    "crossref": True,
    "doaj": True,
    "licensed_index": True,
    "user_upload": True,
    "journal_site": True,
    "model_output": False,   # ذاكرة النموذج ليست دليلًا (§51.1)
}

# §51.5 — مراحل خط الأنابيب الخمس عشرة.
PIPELINE_STAGES: Final[tuple[tuple[str, str, str], ...]] = (
    ("P0", "اكتشاف الاتجاه وتوثيق الأدلة", "Trend discovery and evidence capture"),
    ("P1", "فحص الجدة والتداخل", "Novelty and overlap check"),
    ("P2", "اعتماد السؤال والفجوة والمساهمة", "Approve question, gap and contribution"),
    ("P3", "البروتوكول والنظرية والمنهج وخطة البيانات", "Protocol, theory, method, data plan"),
    ("P4", "الأخلاقيات والموافقات", "Ethics and approvals"),
    ("P5", "جمع أو استيراد البيانات", "Data collection or lawful import"),
    ("P6", "قفل خطة التحليل وإغلاق نسخة البيانات", "Lock analysis plan and freeze data"),
    ("P7", "تشغيل التحليل القابل لإعادة الإنتاج", "Run reproducible analysis"),
    ("P8", "بناء النتائج من المخرجات الفعلية", "Build results from actual outputs"),
    ("P9", "كتابة المخطوطة من سجل الأدلة", "Draft from the evidence ledger"),
    ("P10", "تحديث الأدبيات قبل التقديم", "Refresh literature before submission"),
    ("P11", "مطابقة المجلة وتعليمات النشر", "Journal match and author guidelines"),
    ("P12", "المراجعة النظرية والمنهجية والإحصائية والتحريرية والنزاهية",
     "Theoretical, methodological, statistical, editorial and integrity review"),
    ("P13", "إنتاج حزمة التقديم ووضعها بانتظار اعتماد الباحث",
     "Assemble the submission package, awaiting researcher approval"),
    ("P14", "لا تقديم خارجي إلا بفعل بشري صريح أو تفويض قابل للسحب",
     "No external submission without an explicit human act or a revocable delegation"),
)

# §51.6 — الشروط الاثنا عشر لحالة Ready for Submission.
READY_CONDITIONS: Final[dict[str, tuple[str, str]]] = {
    "question_gap_contribution": ("سؤال وفجوة ومساهمة معتمدة ومتسقة",
                                  "Approved, consistent question, gap and contribution"),
    "recent_verified_literature": ("أدبيات حديثة ومراجع متحققة بلا اختلاق",
                                   "Recent literature and verified references, none fabricated"),
    "claims_evidenced": ("كل ادعاء جوهري مرتبط بدليل أو مصنَّف استنتاجًا",
                         "Every substantive claim evidenced or labelled as inference"),
    "method_ethics_complete": ("المنهجية والأخلاقيات والعينة والأداة مكتملة",
                               "Method, ethics, sample and instrument complete"),
    "results_reproducible": ("النتائج من بيانات وتحليل قابل لإعادة الإنتاج",
                             "Results from data and reproducible analysis"),
    "golden_thread_complete": ("الخيط الذهبي مكتمل من المشكلة حتى التوصيات",
                               "Golden thread complete from problem to recommendations"),
    "no_duplicate_publication": ("لا نشر مكرر ولا تجزئة غير مبررة",
                                 "No duplicate publication or unjustified salami slicing"),
    "authorship_settled": ("التأليف والمساهمات والموافقات محسومة",
                           "Authorship, contributions and consents settled"),
    "journal_verified": ("المجلة موثقة وملائمة وفهرستها حديثة",
                         "Journal documented, suitable, indexing current"),
    "guidelines_followed": ("المخطوطة مطابقة لتعليمات المجلة وقائمة الإبلاغ",
                            "Manuscript follows journal and reporting guidelines"),
    "internal_review_passed": ("اجتياز مجلس المحكّمين وحل الملاحظات الحرجة",
                               "Internal council passed and critical notes resolved"),
    "package_assembled": ("إنتاج خطاب التقديم وصفحة العنوان والنسخة المعمّاة والإفصاحات",
                          "Cover letter, title page, blinded manuscript and disclosures produced"),
}

# §51.8 — قواعد الاستقلال والنزاهة السبع.
INDEPENDENCE_RULES: Final[dict[str, tuple[str, str]]] = {
    "no_generated_data": ("لا ينتج النظام بيانات أو نتائج تجريبية من تلقاء نفسه",
                          "The system never generates data or empirical results on its own"),
    "trend_needs_question": ("لا يحول ترندًا إلى ورقة بلا سؤال وفجوة ومساهمة",
                             "A trend never becomes a paper without question, gap and contribution"),
    "no_results_before_data": ("لا كتابة نتائج قبل وجود بيانات ومخرجات تحليل",
                               "No results written before data and analysis outputs exist"),
    "no_selective_reporting": ("لا انتقاء نتائج ولا مطاردة للدلالة الإحصائية",
                               "No selective reporting and no significance chasing"),
    "no_undisclosed_reuse": ("لا إعادة تدوير نصوص أو نتائج بلا إفصاح ومشروعية",
                             "No recycling of text or results without disclosure and legitimacy"),
    "no_acceptance_guarantee": ("لا ضمان قبول ولا نسبة قبول مختلقة",
                                "No acceptance guarantee and no fabricated acceptance rate"),
    "ai_disclosure_required": ("كل أتمتة تخضع لسياسة المجلة ومتطلبات الإفصاح",
                               "All automation follows journal policy and disclosure requirements"),
}

# §51.7 — إيقاعات التقارير.
BRIEF_CADENCES: Final[dict[str, tuple[str, str]]] = {
    "daily": ("موجز يومي اختياري للمستجدات العاجلة", "Optional daily brief for urgent updates"),
    "weekly": ("تقرير أسبوعي افتراضي", "Default weekly report"),
    "monthly": ("تقرير شهري للمحفظة", "Monthly portfolio report"),
    "alert": ("تنبيه فوري", "Immediate alert"),
}

TREND_STATUSES: Final[tuple[str, ...]] = ("candidate", "validated", "noise", "declining", "retired")
