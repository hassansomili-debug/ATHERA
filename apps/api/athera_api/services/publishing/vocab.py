"""مفردات النشر | Publishing vocabulary (§19، §20، §21، §22).

مفردات مجال — والنماذج تستورد منها لا العكس (الدرس المسجَّل في Sprint 5).
"""
from typing import Final

# §19.1 — أقسام المخطوطة الثمانية عشر.
MANUSCRIPT_SECTIONS: Final[tuple[str, ...]] = (
    "title", "abstract", "keywords", "introduction", "problem_gap",
    "literature_review", "theory", "hypotheses_questions", "method", "results",
    "discussion", "contributions", "implications", "limitations",
    "future_research", "conclusion", "declarations", "references",
)

# أقسام تحمل ادعاءات جوهرية تحتاج أدلة متحققة (§19.2 القاعدة 1).
EVIDENCE_BEARING_SECTIONS: Final[frozenset[str]] = frozenset({
    "introduction", "problem_gap", "literature_review", "theory",
    "discussion", "contributions", "implications",
})

# أقسام لا يجوز أن تحمل رقمًا إحصائيًا بلا تشغيلة تحليل (§19.2 القاعدة 2).
RESULT_BEARING_SECTIONS: Final[frozenset[str]] = frozenset({"abstract", "results", "discussion"})

# §20.2 — طبقات الثقة الخمس.
TRUST_TIERS: Final[dict[str, tuple[str, str]]] = {
    "A": ("Web of Science الصارم (SSCI/AHCI/SCIE) نشط", "Strict Web of Science (SSCI/AHCI/SCIE), active"),
    "B": ("Web of Science آخر مثل ESCI — لا يحقق الشرط الصارم افتراضيًا",
          "Other Web of Science such as ESCI — does not meet the strict requirement by default"),
    "C": ("Scopus نشط وموثوق", "Scopus active and trusted"),
    "D": ("محكمة ومقبولة وفق سياسة المؤسسة عند التحقق",
          "Peer-reviewed and accepted under institutional policy upon verification"),
    "X": ("مستبعدة أو متوقفة أو مشبوهة أو غير مطابقة للنطاق",
          "Excluded, discontinued, suspicious, or scope-mismatched"),
}

# §20.4 — معايير المطابقة التسعة وأوزانها. مجموعها 100.
MATCH_CRITERIA: Final[dict[str, tuple[int, str, str]]] = {
    "scope_fit": (20, "ملاءمة النطاق", "Scope fit"),
    "recent_article_similarity": (15, "تشابه المقالات الحديثة", "Recent article similarity"),
    "method_fit": (12, "ملاءمة المنهج", "Method fit"),
    "publication_fit": (15, "ملاءمة هدف النشر", "Publication fit"),
    "indexing_status": (15, "حالة الفهرسة", "Indexing status"),
    "integrity_publisher_trust": (12, "نزاهة الناشر وموثوقيته", "Integrity and publisher trust"),
    "cost": (5, "الكلفة", "Cost"),
    "oa_license": (3, "الوصول المفتوح والترخيص", "Open access and licence"),
    "review_information": (3, "معلومات التحكيم الموثوقة", "Trusted review information"),
}

# هدف النشر الذي يعلنه الباحث — **تفضيل لا لائحة**. كان يأتي من لائحة ترقية
# جامعية تفرض طبقة؛ صار قرار الباحث في أين يريد أن ينشر. ولا يَعِد أيٌّ منها
# بقبول: الهدف يوجّه الترشيح ولا يتنبأ بقرار محرّر.
TARGET_JOURNAL_TIERS: Final[dict[str, tuple[str, str]]] = {
    "any_peer_reviewed": ("أي مجلة محكّمة", "Any peer-reviewed journal"),
    "scopus": ("مفهرسة في Scopus", "Indexed in Scopus"),
    "web_of_science": ("مفهرسة في Web of Science", "Indexed in Web of Science"),
    "q1": ("الربع الأول", "First quartile"),
    "q2": ("الربع الثاني أو أعلى", "Second quartile or better"),
    "open_access": ("وصول مفتوح", "Open access"),
    "no_apc": ("بلا رسوم نشر", "No article processing charge"),
    "custom": ("هدف مخصص", "Custom target"),
}

# §20.3 — نقاط إعادة التحقق الأربع.
VERIFICATION_POINTS: Final[tuple[str, ...]] = (
    "shortlisting", "submission", "acceptance", "publication",
)

# §21 — المراجعون الخمسة.
REVIEWER_ROLES: Final[dict[str, tuple[str, str]]] = {
    "theoretical": ("مراجع نظري", "Theoretical reviewer"),
    "methodological": ("مراجع منهجي", "Methodological reviewer"),
    "statistical": ("مراجع إحصائي", "Statistical reviewer"),
    "editorial": ("مراجع تحريري", "Editorial reviewer"),
    "integrity": ("مراجع نزاهة", "Integrity reviewer"),
}

# §21.1 — أقسام التقرير الستة.
REPORT_SECTIONS: Final[tuple[str, ...]] = (
    "strengths", "major_concerns", "minor_concerns",
    "potential_rejection_reasons", "required_changes", "readiness_status",
)

# §21.1 — حالات الجاهزية الأربع.
READINESS_STATUSES: Final[dict[str, tuple[str, str]]] = {
    "not_ready": ("غير جاهزة", "Not ready"),
    "major_revision": ("تحتاج تعديلات كبيرة", "Major revision"),
    "minor_revision": ("تحتاج تعديلات طفيفة", "Minor revision"),
    "ready_to_submit": ("جاهزة للتقديم", "Ready to submit"),
}

# §22.1 — عناصر حزمة التقديم الثلاثة عشر.
SUBMISSION_PACKAGE_ITEMS: Final[dict[str, tuple[str, str]]] = {
    "main_manuscript": ("المخطوطة الرئيسة", "Main manuscript"),
    "blinded_manuscript": ("النسخة المعمّاة", "Blinded manuscript"),
    "title_page": ("صفحة العنوان", "Title page"),
    "cover_letter": ("خطاب التقديم", "Cover letter"),
    "highlights": ("أبرز النقاط", "Highlights"),
    "graphical_abstract": ("الملخص المرئي", "Graphical abstract"),
    "figures_tables": ("الأشكال والجداول", "Figures and tables"),
    "data_availability_statement": ("بيان إتاحة البيانات", "Data availability statement"),
    "funding": ("التمويل", "Funding"),
    "conflict_of_interest": ("تعارض المصالح", "Conflict of interest"),
    "credit_contributions": ("مساهمات CRediT", "CRediT contributions"),
    "ai_disclosure": ("إفصاح استخدام الذكاء الاصطناعي", "AI disclosure"),
    "reporting_checklist": ("قائمة الإبلاغ", "Reporting checklist"),
}

# عناصر اختيارية بحسب المجلة (§22.1) — غيابها لا يمنع الحزمة.
OPTIONAL_PACKAGE_ITEMS: Final[frozenset[str]] = frozenset({
    "highlights", "graphical_abstract",
})

# حالات الرقعة المقترحة من المراجعة (§21).
PATCH_STATUSES: Final[tuple[str, ...]] = ("proposed", "applied", "rejected")

# ── S5E — حالات مراجعة القسم (§18) ──
#
# قرار الباحث في نصٍّ ولّده نموذج. ولا تُخلط بـ`manuscripts.status` التي تصف
# دورة حياة الورقة كلها: قسمٌ معتمَد في مخطوطة ما زالت `draft` حالٌ طبيعية.
SECTION_REVIEW_STATUSES: Final[dict[str, tuple[str, str]]] = {
    "draft": ("مسودة", "Draft"),
    "needs_review": ("بانتظار مراجعتك", "Awaiting your review"),
    "approved": ("معتمَد", "Approved"),
    "revision_requested": ("مطلوب تعديله", "Revision requested"),
}

# حالات لا تكون بلا فاعل ووقت — والقاعدة تفرضها في `ck_manuscript_sections_review_actor`.
SECTION_DECIDED_STATUSES: Final[frozenset[str]] = frozenset({"approved", "revision_requested"})

# مستوى سند الادعاء — **مفردات `claim_evidence_links` القائمة نفسها**،
# فلا مفردتان لمعنى واحد.
SUPPORT_LEVELS: Final[tuple[str, ...]] = ("direct", "partial", "contextual", "contradictory")
