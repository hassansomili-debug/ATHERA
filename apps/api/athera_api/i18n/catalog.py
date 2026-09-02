"""كتالوج الرسائل | Message catalog (ar + en).

كل مفتاح يجب أن يوجد باللغتين — اختبار AT-S0-11 يفشل إذا نقصت ترجمة.
Every key must exist in both locales; AT-S0-11 fails on any gap.
"""
from __future__ import annotations

from typing import Final

DEFAULT_LOCALE: Final = "ar"
SUPPORTED_LOCALES: Final = ("ar", "en")

CATALOG: Final[dict[str, dict[str, str]]] = {
    "auth.invalid_credentials": {
        "ar": "بيانات الدخول غير صحيحة.",
        "en": "Invalid credentials.",
    },
    "auth.mfa_required": {
        "ar": "التحقق بخطوتين مطلوب لهذا الدور.",
        "en": "Multi-factor authentication is required for this role.",
    },
    "auth.mfa_invalid_code": {
        "ar": "رمز التحقق غير صحيح أو منتهي الصلاحية.",
        "en": "The verification code is invalid or expired.",
    },
    "auth.token_expired": {
        "ar": "انتهت صلاحية الجلسة، يرجى تسجيل الدخول مجددًا.",
        "en": "Your session has expired. Please sign in again.",
    },
    "auth.email_taken": {
        "ar": "البريد الإلكتروني مسجّل مسبقًا.",
        "en": "This email address is already registered.",
    },
    "authz.forbidden": {
        "ar": "لا تملك صلاحية تنفيذ هذا الإجراء.",
        "en": "You do not have permission to perform this action.",
    },
    "authz.approver_required": {
        "ar": "هذا الإجراء يحتاج صلاحية اعتماد، والتحرير وحده لا يكفي.",
        "en": "This action requires approver permission; edit rights are not sufficient.",
    },
    "tenant.not_found": {
        "ar": "المستأجر غير موجود أو خارج نطاق صلاحيتك.",
        "en": "Tenant not found or outside your scope.",
    },
    "readiness.database_role_unsafe": {
        "ar": "الخدمة ليست جاهزة: إعداد قاعدة البيانات لا يستوفي شرط عزل المستأجرين.",
        "en": "Service not ready: the database configuration does not satisfy the "
              "tenant-isolation requirement.",
    },
    "publishing.project_not_found": {
        "ar": "المشروع غير موجود أو خارج نطاق صلاحيتك.",
        "en": "Project not found or outside your scope.",
    },
    "drafting.unknown_section": {
        "ar": "قسم غير معروف في بنية المخطوطة.",
        "en": "Unknown manuscript section.",
    },
    "drafting.section_not_enabled": {
        "ar": "صياغة هذا القسم لم تُفعَّل بعد — المنهجية أولًا.",
        "en": "Drafting this section is not enabled yet — Methods comes first.",
    },
    "drafting.manuscript_not_bound": {
        "ar": "المخطوطة غير مرتبطة بفرصة نشر مختارة.",
        "en": "This manuscript is not bound to a selected publication opportunity.",
    },
    "drafting.insufficient_evidence": {
        "ar": "لا توجد معرفة موثقة كافية لكتابة هذا القسم.",
        "en": "There is not enough verified knowledge to draft this section.",
    },
    "drafting.consent_required": {
        "ar": "صياغة المخطوطة تحتاج إذنًا صريحًا منك — وإذن التخطيط لا يكفي.",
        "en": "Manuscript drafting needs your explicit consent; planning consent is not enough.",
    },
    "drafting.context_changed": {
        "ar": "تغيّرت الأدلة منذ عرض الشاشة — راجعها ثم قرّر.",
        "en": "The evidence changed since this screen was shown — review it, then decide.",
    },
    "drafting.section_approved": {
        "ar": "هذا القسم معتمَد — إعادة الصياغة تحتاج طلب تعديل صريحًا.",
        "en": "This section is approved; regenerating it needs an explicit revision request.",
    },
    "drafting.section_not_drafted": {
        "ar": "لم تُكتب مسودة لهذا القسم بعد.",
        "en": "No draft exists for this section yet.",
    },
    "drafting.generation_failed": {
        "ar": "تعذّر إنتاج المسودة — لم يُحفظ نصّ ناقص.",
        "en": "The draft could not be produced; no partial text was saved.",
    },
    "drafting.unsupported_content": {
        "ar": "المسودة حُجبت: كانت ستُثبت واقعة لا يسندها دليل أو مخرَج تحليل.",
        "en": "The draft was withheld: it would have asserted content with no verified "
              "evidence or analysis output behind it.",
    },
    "tenant.context_missing": {
        "ar": "لم يُحدَّد سياق المستأجر للطلب.",
        "en": "No tenant context was resolved for this request.",
    },
    "file.not_found": {
        "ar": "الملف غير موجود.",
        "en": "File not found.",
    },
    "file.checksum_mismatch": {
        "ar": "بصمة الملف لا تطابق المرفوع؛ لم يُعتمد الرفع.",
        "en": "Checksum mismatch; the upload was not accepted.",
    },
    "file.type_rejected": {
        "ar": "نوع الملف غير مسموح به.",
        "en": "This file type is not allowed.",
    },
    "file.too_large": {
        "ar": "حجم الملف يتجاوز الحد المسموح.",
        "en": "The file exceeds the maximum allowed size.",
    },
    "audit.immutable": {
        "ar": "سجل التدقيق غير قابل للتعديل أو الحذف (§37).",
        "en": "The audit log is append-only and cannot be modified or deleted (§37).",
    },
    "provider.disabled_for_classification": {
        "ar": "تصنيف البيانات يمنع إرسالها إلى مزود نموذج خارجي.",
        "en": "The data classification forbids sending this content to an external model provider.",
    },
    "memory.candidate_not_found": {
        "ar": "مرشّح الحقيقة غير موجود.",
        "en": "Fact candidate not found.",
    },
    "memory.already_decided": {
        "ar": "تم البت في هذا المرشّح مسبقًا ولا يمكن تغييره.",
        "en": "This candidate has already been decided and cannot be changed.",
    },
    "memory.quote_not_grounded": {
        "ar": "الاقتباس غير موجود في نص المصدر؛ لا يمكن اعتماد هذه الحقيقة.",
        "en": "The quote is absent from the source text; this fact cannot be approved.",
    },
    "memory.unknown_category": {
        "ar": "فئة ذاكرة غير معروفة.",
        "en": "Unknown memory category.",
    },
    "memory.invalid_source_path": {
        "ar": "مسار المصدر لا يسمح بترقية هذه المعلومة إلى ذاكرة موثقة.",
        "en": "This source path does not permit promotion to verified memory.",
    },
    "memory.promotion_denied": {
        "ar": "تعذّرت ترقية المعلومة إلى ذاكرة موثقة.",
        "en": "The information could not be promoted to verified memory.",
    },
    "ingestion.file_not_ready": {
        "ar": "الملف لم يكتمل رفعه بعد.",
        "en": "The file upload is not complete yet.",
    },
    "ingestion.unsupported_document": {
        "ar": "تعذّر تفكيك هذا المستند؛ قد يكون ممسوحًا ضوئيًا بلا طبقة نص.",
        "en": "This document could not be parsed; it may be scanned with no text layer.",
    },
    "brain.tool_not_allowed": {
        "ar": "هذا الأجنت لا يملك صلاحية استدعاء هذه الأداة.",
        "en": "This agent is not permitted to call that tool.",
    },
    "brain.output_blocked": {
        "ar": "حُجب المخرَج لمخالفته حاجز نزاهة علمية ولم يُعرض.",
        "en": "The output was blocked by a scientific-integrity guardrail and not shown.",
    },
    "brain.trace_not_found": {
        "ar": "أثر التشغيل غير موجود.",
        "en": "Trace not found.",
    },
    "brain.unknown_agent": {
        "ar": "أجنت غير معروف.",
        "en": "Unknown agent.",
    },
    "portfolio.profile_required": {
        "ar": "يلزم إنشاء الملف الأكاديمي قبل إنشاء مشروع بحثي.",
        "en": "An academic profile is required before creating a research project.",
    },
    "evidence.doi_not_resolved": {
        "ar": "لم يُعثر على هذا المعرّف في أي سجل علمي؛ لن يُنشأ مرجع بديل.",
        "en": "This identifier was not found in any scholarly registry; no substitute reference will be created.",
    },
    "evidence.invalid_doi": {
        "ar": "صيغة معرّف DOI غير صحيحة.",
        "en": "The DOI format is invalid.",
    },
    "evidence.source_not_found": {
        "ar": "المصدر غير موجود.",
        "en": "Source not found.",
    },
    "evidence.source_not_verified": {
        "ar": "لا يُبنى دليل على مصدر غير متحقق (§14.5).",
        "en": "Evidence cannot be built on an unverified source (§14.5).",
    },
    "evidence.source_has_no_doi": {
        "ar": "المصدر بلا معرّف DOI فلا يمكن إعادة التحقق منه آليًا.",
        "en": "The source has no DOI, so it cannot be revalidated automatically.",
    },
    "evidence.no_text_access": {
        "ar": "لا يمكن اقتطاف نص من مصدر متاح بالبيانات الوصفية فقط (§14.5).",
        "en": "A quote cannot be taken from a metadata-only source (§14.5).",
    },
    "evidence.retraction_needs_acknowledgement": {
        "ar": "الاستشهاد بمصدر مسحوب يحتاج إقرارًا صريحًا وسياقًا مكتوبًا.",
        "en": "Citing a retracted source requires an explicit acknowledgement and written context.",
    },
    "evidence.claim_not_found": {
        "ar": "الادعاء غير موجود.",
        "en": "Claim not found.",
    },
    "evidence.excerpt_not_found": {
        "ar": "المقتطف غير موجود.",
        "en": "Excerpt not found.",
    },
    "evidence.unknown_support_level": {
        "ar": "مستوى دعم غير معروف.",
        "en": "Unknown support level.",
    },
    "evidence.claim_has_gap": {
        "ar": "فجوة دليل: لا يمكن إغلاق ادعاء بلا دليل داعم متحقق.",
        "en": "Evidence gap: a claim cannot be closed without verified supporting evidence.",
    },
    "evidence.claim_contradicted": {
        "ar": "يوجد دليل مناقض لم يُعالَج؛ لا يمكن إغلاق الادعاء.",
        "en": "Unresolved contradictory evidence exists; the claim cannot be closed.",
    },
    "thread.protocol_not_found": {
        "ar": "لا يوجد بروتوكول لهذا المشروع بعد.",
        "en": "This project has no protocol yet.",
    },
    "thread.gate_blocked": {
        "ar": "البوابة مغلقة: توجد عيوب اتساق حاجبة أو عناصر ناقصة في الخيط الذهبي.",
        "en": "Gate blocked: blocking consistency findings or missing golden-thread elements.",
    },
    "thread.unknown_study_type": {
        "ar": "نوع دراسة غير معروف.",
        "en": "Unknown study type.",
    },
    "thesis.not_found": {
        "ar": "الرسالة غير موجودة.",
        "en": "Thesis not found.",
    },
    "thesis.no_file": {
        "ar": "لم يُرفق ملف الرسالة بعد.",
        "en": "No thesis file has been attached yet.",
    },
    "thesis.opportunity_not_found": {
        "ar": "فرصة النشر غير موجودة.",
        "en": "Publication opportunity not found.",
    },
    "thesis.agreement_not_found": {
        "ar": "اتفاق التأليف غير موجود.",
        "en": "Authorship agreement not found.",
    },
    "thesis.invalid_party_kind": {
        "ar": "التأليف لا يُسند إلا إلى شخص أو جهة (§24.2).",
        "en": "Authorship can only be assigned to a person or an organisation (§24.2).",
    },
    "thesis.unknown_credit_role": {
        "ar": "دور CRediT غير معروف.",
        "en": "Unknown CRediT role.",
    },
    "thesis.gate_blocked": {
        "ar": "بوابة الحقوق والتأليف مغلقة؛ التحليل مسموح لكن التقدم يحتاج اعتمادًا.",
        "en": "The rights and authorship gate is closed; analysis is allowed but advancing needs approval.",
    },
    "thesis.not_ready_to_convert": {
        "ar": "لا يمكن تحويل فرصة لم تجتز بوابة الحقوق والتأليف.",
        "en": "An opportunity cannot be converted before passing the rights and authorship gate.",
    },
    "thesis.overlap_unresolved": {
        "ar": "يوجد تنبيه تداخل لم يُحسم؛ يلزم الدمج أو تبرير معتمد.",
        "en": "An unresolved overlap alert exists; a merge or an approved justification is required.",
    },
    "publishing.manuscript_not_found": {
        "ar": "المخطوطة غير موجودة.", "en": "Manuscript not found.",
    },
    "publishing.unknown_section": {
        "ar": "قسم غير معروف في بنية المخطوطة.", "en": "Unknown manuscript section.",
    },
    "publishing.g9_blocked": {
        "ar": "بوابة G9 مغلقة: ادعاء بلا دليل أو نتيجة بلا تشغيلة تحليل.",
        "en": "Gate G9 blocked: an unsupported claim or a result with no analysis run.",
    },
    "publishing.patch_not_found": {
        "ar": "الرقعة غير موجودة.", "en": "Patch not found.",
    },
    "publishing.patch_already_decided": {
        "ar": "تم البت في هذه الرقعة مسبقًا.", "en": "This patch has already been decided.",
    },
    "analysis.version_not_found": {
        "ar": "نسخة البيانات غير موجودة.", "en": "Dataset version not found.",
    },
    "analysis.invalid_transition": {
        "ar": "انتقال غير مسموح بين حالات البيانات (§17.2).",
        "en": "Disallowed dataset state transition (§17.2).",
    },
    "analysis.cannot_freeze": {
        "ar": "تعذّر تجميد هذه النسخة.", "en": "This version cannot be frozen.",
    },
    "analysis.plan_not_found": {
        "ar": "خطة التحليل غير موجودة.", "en": "Analysis plan not found.",
    },
    "analysis.cannot_approve_plan": {
        "ar": "تعذّر اعتماد خطة التحليل.", "en": "The analysis plan cannot be approved.",
    },
    "analysis.plan_not_locked": {
        "ar": "التشغيل يحتاج خطة معتمدة ومقفلة (§9 G7).",
        "en": "A run requires an approved, locked plan (§9 G7).",
    },
    "analysis.dataset_not_frozen": {
        "ar": "لا يعمل التحليل إلا على نسخة بيانات مجمَّدة (§17.3).",
        "en": "Analysis runs only on a frozen dataset version (§17.3).",
    },
    "analysis.unknown_test_kind": {
        "ar": "نوع اختبار غير معروف.", "en": "Unknown test kind.",
    },
    "analysis.run_not_found": {
        "ar": "تشغيلة التحليل غير موجودة.", "en": "Analysis run not found.",
    },
    "analysis.output_not_found": {
        "ar": "مخرَج التحليل غير موجود.", "en": "Analysis output not found.",
    },
    "analysis.invalid_interpretation": {
        "ar": "التفسير مخالف لسلسلة السند في §18.3.",
        "en": "The interpretation violates the evidence chain in §18.3.",
    },
    "trends.watchlist_needs_scope": {
        "ar": "ملف المراقبة بلا نطاق لا يراقب شيئًا.",
        "en": "A watchlist without a scope watches nothing.",
    },
    "trends.invalid_signal": {
        "ar": "إشارة غير صالحة: لا إشارة بلا مصدر ومعرّف وتاريخ (§51.11).",
        "en": "Invalid signal: no signal without a source, identifier and date (§51.11).",
    },
    "trends.invalid_fit": {
        "ar": "معايير ملاءمة غير صالحة.", "en": "Invalid opportunity criteria.",
    },
    "trends.invalid_card": {
        "ar": "بطاقة الفرصة تحتاج سؤالًا وفجوة وإشارات داعمة (§51.4).",
        "en": "An opportunity card needs a question, a gap and supporting signals (§51.4).",
    },
    "trends.card_not_found": {
        "ar": "بطاقة الفرصة غير موجودة.", "en": "Opportunity card not found.",
    },
    "trends.card_already_approved": {
        "ar": "البطاقة معتمدة مسبقًا.", "en": "This card is already approved.",
    },
    "trends.pipeline_not_found": {
        "ar": "خط الأنابيب غير موجود لهذه البطاقة.",
        "en": "No pipeline exists for this card.",
    },
    "trends.invalid_stage": {
        "ar": "مرحلة غير معروفة في خط الأنابيب.", "en": "Unknown pipeline stage.",
    },
    "trends.unknown_condition": {
        "ar": "شرط جاهزية غير معروف.", "en": "Unknown readiness condition.",
    },
    "trends.delegation_not_found": {
        "ar": "التفويض غير موجود.", "en": "Delegation not found.",
    },
    "inbox.approval_not_found": {
        "ar": "طلب الاعتماد غير موجود.", "en": "Approval request not found.",
    },
    "inbox.already_decided": {
        "ar": "بُتّ في هذا الاعتماد مسبقًا، ولا يُعاد البتّ فيه.",
        "en": "This approval was already settled and cannot be decided again.",
    },
    "inbox.self_approval_forbidden": {
        "ar": "لا يبتّ طالب الاعتماد في طلبه (§28).",
        "en": "The requester cannot decide their own approval (§28).",
    },
    "inbox.alert_not_found": {
        "ar": "تنبيه النزاهة غير موجود.", "en": "Integrity alert not found.",
    },
    "inbox.alert_already_resolved": {
        "ar": "التنبيه مُغلق مسبقًا.", "en": "This alert is already resolved.",
    },
    "inbox.notification_not_found": {
        "ar": "الإشعار غير موجود.", "en": "Notification not found.",
    },
    "provider.unknown": {
        "ar": "مزوّد نموذج غير معروف في الإعداد.",
        "en": "Unknown model provider in configuration.",
    },
    "team.project_not_found": {
        "ar": "المشروع غير موجود.", "en": "Project not found.",
    },
    "team.member_not_found": {
        "ar": "عضو الفريق غير موجود.", "en": "Team member not found.",
    },
    "team.unknown_member_role": {
        "ar": "دور غير معروف في الفريق.", "en": "Unknown team role.",
    },
    "team.invalid_member": {
        "ar": "بيانات العضو غير صالحة: لا يُسند تأليف لغير إنسان (§24).",
        "en": "Invalid member: authorship cannot be assigned to a non-human agent (§24).",
    },
    "team.consent_already_recorded": {
        "ar": "الموافقة مسجَّلة مسبقًا.", "en": "Consent is already recorded.",
    },
    "team.unknown_decision_kind": {
        "ar": "نوع قرار غير معروف.", "en": "Unknown decision kind.",
    },
    "team.decision_not_found": {
        "ar": "القرار المشار إليه غير موجود.", "en": "The referenced decision was not found.",
    },
    "team.decision_other_project": {
        "ar": "لا يُنسخ قرار من مشروع آخر.",
        "en": "A decision from another project cannot be superseded here.",
    },
    "analysis.dictionary_frozen": {
        "ar": "لا يُعدَّل قاموس نسخة مجمَّدة (§17.4).",
        "en": "The dictionary of a frozen version cannot be edited (§17.4).",
    },
    "analysis.duplicate_column": {
        "ar": "اسم عمود مكرر في القاموس.", "en": "Duplicate column name in the dictionary.",
    },
    "analysis.unknown_tool": {
        "ar": "أداة تحليل غير مدعومة.", "en": "Unsupported analysis tool.",
    },
    "analysis.unsupported_format": {
        "ar": "صيغة تصدير لا تدعمها هذه الأداة.",
        "en": "This tool does not support that export format.",
    },
    "trends.invalid_brief": {
        "ar": "نشرة غير صالحة: لا بند بلا مرجع يسنده (§51.9).",
        "en": "Invalid brief: no item without a supporting reference (§51.9).",
    },
    "trends.brief_not_found": {
        "ar": "النشرة غير موجودة.", "en": "Brief not found.",
    },
    "trends.novelty_check_not_found": {
        "ar": "فحص الجدة غير موجود.", "en": "Novelty check not found.",
    },
    "trends.novelty_already_decided": {
        "ar": "بُتّ في فحص الجدة مسبقًا.", "en": "This novelty check was already decided.",
    },
    "validation.failed": {
        "ar": "البيانات المُرسلة غير صالحة.",
        "en": "The submitted data is invalid.",
    },
    "server.error": {
        "ar": "حدث خطأ غير متوقع.",
        "en": "An unexpected error occurred.",
    },
}


def negotiate_locale(accept_language: str | None) -> str:
    """اختيار اللغة من ترويسة Accept-Language | pick a locale from Accept-Language."""
    if not accept_language:
        return DEFAULT_LOCALE
    for part in accept_language.split(","):
        code = part.split(";")[0].strip().lower()
        if not code:
            continue
        primary = code.split("-")[0]
        if primary in SUPPORTED_LOCALES:
            return primary
    return DEFAULT_LOCALE


def translate(key: str, locale: str = DEFAULT_LOCALE) -> str:
    entry = CATALOG.get(key)
    if entry is None:
        return key
    return entry.get(locale) or entry[DEFAULT_LOCALE]


def all_translations(key: str) -> dict[str, str]:
    return dict(CATALOG.get(key, {}))
