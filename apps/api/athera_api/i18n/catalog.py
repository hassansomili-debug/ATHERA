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
    "auth.workspace_name_taken": {
        "ar": "اسم مساحة العمل هذا مأخوذ. اختر اسمًا آخر — والانضمام إلى مساحة "
              "قائمة يكون بدعوة من مسؤولها لا بالتسجيل.",
        "en": "That workspace name is taken. Choose another — joining an existing "
              "workspace happens by invitation from its administrator, not by "
              "registering.",
    },
    "document.not_stored": {
        "ar": "لم يكتمل حفظ هذا الملف بعد — أعد المحاولة بعد قليل.",
        "en": "This file is not fully stored yet — try again shortly.",
    },
    "document.unsupported_type": {
        "ar": "نوع هذا الملف لا يمكن قراءته: تُقرأ ملفات PDF وWord والنصوص.",
        "en": "This file type cannot be read: PDF, Word and text files are supported.",
    },
    "tenant.context_missing": {
        "ar": "لم يُحدَّد سياق المستأجر للطلب.",
        "en": "No tenant context was resolved for this request.",
    },
    "file.not_found": {
        "ar": "الملف غير موجود.",
        "en": "File not found.",
    },
    # ── مجلَّدات المكتبة (الترحيل 0022) ──
    #
    # **الرسالة تقول ما يفعله الباحث الآن**، لا ما رفضه النظام فحسب. ومفتاحٌ
    # تقنيّ بلا ترجمة يصل الباحث كما هو — وهو ليس رسالة.
    "library.folder_not_found": {
        "ar": "المجلَّد غير موجود.",
        "en": "Folder not found.",
    },
    "library.folder_name_required": {
        "ar": "اسم المجلَّد لا يكون فارغًا.",
        "en": "A folder name cannot be empty.",
    },
    "library.folder_cycle": {
        "ar": "لا يُنقل المجلَّد إلى نفسه ولا إلى مجلَّدٍ بداخله — "
              "فذلك يقطع ما تحته عن مكتبتك.",
        "en": "A folder cannot move into itself or into one of its own subfolders; "
              "that would cut everything below it out of your library.",
    },
    "library.folder_depth_exceeded": {
        "ar": "تجاوزتَ أقصى عمقٍ للمجلَّدات. اجعل التنظيم أقلّ تداخلًا.",
        "en": "That exceeds the maximum folder depth. Use a flatter structure.",
    },
    "library.folder_not_empty": {
        "ar": "المجلَّد ليس فارغًا. انقل ما فيه أو احذفه أولًا، ثم احذف المجلَّد.",
        "en": "The folder is not empty. Move or delete what it holds first, then "
              "delete the folder.",
    },
    "library.folder_in_trash": {
        "ar": "هذا المجلَّد في سلّة المهملات.",
        "en": "This folder is in the trash.",
    },
    "library.folder_not_in_trash": {
        "ar": "هذا المجلَّد ليس في سلّة المهملات.",
        "en": "This folder is not in the trash.",
    },
    "library.parent_in_trash": {
        "ar": "المجلَّد الذي كان يحويه في سلّة المهملات. استعِده أولًا.",
        "en": "The folder that held it is in the trash. Restore that folder first.",
    },
    "library.file_not_in_trash": {
        "ar": "هذا الملف ليس في سلّة المهملات.",
        "en": "This file is not in the trash.",
    },
    "library.file_linked_to_projects": {
        "ar": "هذا الملف مرتبط ببحوثٍ قائمة، وحذفه يُخفيه عنها. "
              "الحذف نقلٌ إلى السلّة ولا يُتلف شيئًا — أكّد إن أردت المتابعة.",
        "en": "This file is linked to live projects, and deleting it hides it from "
              "them. Deleting moves it to the trash and destroys nothing — confirm "
              "to continue.",
    },
    "library.unknown_filter": {
        "ar": "لا نعرف هذا المرشّح. المرشّحات المتاحة مذكورة في تفاصيل الرسالة.",
        "en": "That filter is not one we know. The available filters are listed in "
              "the message details.",
    },
    "library.nothing_selected": {
        "ar": "لم تختر ملفًّا واحدًا لهذا الفعل.",
        "en": "No file was selected for this action.",
    },
    "library.selection_too_large": {
        "ar": "اخترت أكثر مما يُنفَّذ دفعةً واحدة. نفّذ على دفعاتٍ أصغر — "
              "والحدُّ مذكور في تفاصيل الرسالة.",
        "en": "You selected more than one batch can carry. Do it in smaller "
              "batches — the limit is in the message details.",
    },
    "library.selection_linked_to_projects": {
        "ar": "بعض ما اخترته يسند بحوثًا قائمة، وحذفه يُخفيه عنها. "
              "الحذف نقلٌ إلى السلّة ولا يُتلف شيئًا — أكّد إن أردت المتابعة.",
        "en": "Some of what you selected supports live projects, and deleting it "
              "hides it from them. Deleting moves it to the trash and destroys "
              "nothing — confirm to continue.",
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
    # ── ذكاءُ الباحث، الموجة الثانية ──
    #
    # ورسالةُ ORCID تقول ما وقع بالضبط: **صيغةٌ** لم تصحّ. ولا تقول
    # «لم يُوثَّق»، لأنّ التوثيق لم يُطلب أصلًا ولم يُدَّعَ (§6).
    "researcher.orcid_malformed": {
        "ar": "صيغة معرّف ORCID غير صحيحة — يُتوقّع ١٦ رقمًا على هيئة 0000-0000-0000-0000.",
        "en": "The ORCID identifier is malformed — 16 digits are expected, as 0000-0000-0000-0000.",
    },
    "researcher.orcid_checksum_failed": {
        "ar": "خانة التدقيق في معرّف ORCID لا تطابق أرقامه. وهذا فحصُ صيغةٍ لا توثيقَ ملكية.",
        "en": "The ORCID check digit does not match. This is a format check, not proof of ownership.",
    },
    "researcher.candidate_not_found": {
        "ar": "لا مرشّح بهذا المعرّف في ملفّك.",
        "en": "No candidate with this identifier exists in your profile.",
    },
    "researcher.candidate_already_decided": {
        "ar": "هذا المرشّح قُرّر من قبل، ولا يُقرّر مرتين.",
        "en": "This candidate was already decided, and is not decided twice.",
    },
    "researcher.candidate_field_unknown": {
        "ar": "هذا الحقل ليس من حقول الملفّ التي يجوز تأكيدها.",
        "en": "This field is not one of the profile fields that may be confirmed.",
    },
    "researcher.goal_not_found": {
        "ar": "لا هدف بهذا المعرّف في ملفّك.",
        "en": "No goal with this identifier exists in your profile.",
    },
    "researcher.constraint_not_found": {
        "ar": "لا قيد بهذا المعرّف في ملفّك.",
        "en": "No constraint with this identifier exists in your profile.",
    },
    "researcher.strategy_not_found": {
        "ar": "لا استراتيجية بهذا المعرّف في ملفّك.",
        "en": "No strategy with this identifier exists in your profile.",
    },
    "researcher.strategy_not_approvable": {
        "ar": "لا تُعتمد إلا مسوّدة أو استراتيجية قيد المراجعة. والمعتمَدة لا تُعدَّل — التغيير يُنشئ إصدارًا تاليًا.",
        "en": "Only a draft or a strategy under review can be approved. An approved strategy is immutable — a change creates the next version.",
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
    "workspace.project_not_found": {
        "ar": "لم يُعثر على هذا البحث.",
        "en": "This project was not found.",
    },
    "workspace.file_not_found": {
        "ar": "لم يُعثر على هذا الملف في مكتبتك.",
        "en": "This file was not found in your library.",
    },
    "workspace.file_not_linked": {
        "ar": "هذا الملف غير مرتبط بهذا البحث.",
        "en": "This file is not linked to this project.",
    },
    "workspace.source_not_found": {
        "ar": "لم يُعثر على هذا المرجع.",
        "en": "This source was not found.",
    },
    "workspace.source_not_linked": {
        "ar": "هذا المرجع غير مرتبط بهذا البحث.",
        "en": "This source is not linked to this project.",
    },
    "workspace.removal_needs_acknowledgement": {
        "ar": "إزالة هذا الملف تقطع السند عن عملٍ اعتمدته. راجع ما يترتب ثم أكّد.",
        "en": "Removing this file breaks support for work you approved. Review the consequences, then confirm.",
    },
    "workspace.exclusion_needs_reason": {
        "ar": "الاستبعاد يحتاج سببًا من القائمة، و«سبب آخر» يحتاج نصًّا يوضّحه.",
        "en": "Excluding a study requires a reason from the list; “other” requires a note.",
    },
    "workspace.matrix_needs_included_source": {
        "ar": "مصفوفة الأدبيات للدراسات المدرجة وحدها. أدرِج هذه الدراسة أولًا.",
        "en": "The literature matrix covers included studies only. Include this study first.",
    },
    "workspace.matrix_field_unknown": {
        "ar": "لا يوجد عمود بهذا الاسم في مصفوفة الأدبيات.",
        "en": "No such column exists in the literature matrix.",
    },
    "workspace.matrix_cell_not_found": {
        "ar": "لم تُكتب هذه الخانة بعد، فلا شيء يُراجَع فيها.",
        "en": "This cell has not been filled in yet, so there is nothing to review.",
    },
    "workspace.scope_not_available": {
        "ar": "ما هو متاح من هذه الدراسة أقلّ مما يدّعيه هذا الإدخال. "
              "الملخّص وحده لا يُقرأ نصًّا كاملًا، والبيانات الوصفية ليست ملخّصًا.",
        "en": "This entry claims more of the study than is actually available. "
              "An abstract is not the full text, and metadata is not an abstract.",
    },
    "workspace.missing_cell_carries_value": {
        "ar": "«غير مذكور» لا تحمل قيمة. ما لم يُذكر في المصدر يبقى غير مذكور.",
        "en": "A “not stated” cell carries no value. What the source omits stays omitted.",
    },
    "workspace.stated_cell_needs_value": {
        "ar": "خانةٌ ليست «غير مذكور» تحتاج نصًّا يقول ما وُجد.",
        "en": "A cell that is not “not stated” needs text saying what was found.",
    },
    "workspace.quote_without_text": {
        "ar": "لا يُقتبس من بياناتٍ وصفية: الاقتباس يحتاج نصًّا مقروءًا.",
        "en": "Metadata cannot be quoted; a quotation requires readable text.",
    },
    "workspace.page_without_full_text": {
        "ar": "رقم الصفحة والقسم لا يُكتبان إلا من النص الكامل — والملخّص لا صفحات له.",
        "en": "A page number or section can only come from full text; an abstract has "
              "no pages.",
    },
    "workspace.invented_locator": {
        "ar": "لا موضع لخانةٍ قُرئت من الملخّص أو من البيانات الوصفية — ولا صفحة للملخّص.",
        "en": "A cell read from an abstract or from metadata has no page locator.",
    },
    "workspace.source_still_cited": {
        "ar": "لا يمكن استبعاد مرجعٍ ما زال يُستشهد به في ادعاءات هذا البحث.",
        "en": "A source still cited by this project's claims cannot be excluded.",
    },
    # ── طبقة التركيب: الموضوعات والتعارضات والفجوات المحتملة والفرص ──
    #
    # ولا رمز هنا يقول «فجوة» بلا «محتملة»: نصّ الخطأ يقرؤه الباحث في لحظة
    # ضغطٍ على زرّ، وهو من أكثر ما يعلق في ذهنه عن معنى ما يفعله.
    "synthesis.project_not_found": {
        "ar": "لم يُعثر على هذا البحث.",
        "en": "This project was not found.",
    },
    "synthesis.theme_not_found": {
        "ar": "لم يُعثر على هذا الموضوع في هذا البحث.",
        "en": "This theme was not found in this project.",
    },
    "synthesis.contradiction_not_found": {
        "ar": "لم يُعثر على هذا التعارض في هذا البحث.",
        "en": "This contradiction was not found in this project.",
    },
    "synthesis.gap_not_found": {
        "ar": "لم يُعثر على هذه الفجوة المحتملة في هذا البحث.",
        "en": "This gap candidate was not found in this project.",
    },
    "synthesis.opportunity_not_found": {
        "ar": "لم يُعثر على هذه الفرصة البحثية في هذا البحث.",
        "en": "This research opportunity was not found in this project.",
    },
    "synthesis.gap_not_approved": {
        "ar": "الفرصة البحثية لا تُنشأ إلا من فجوةٍ محتملة اعتمدتها بنفسك. "
              "راجِع الفجوة أولًا ثم اعتمدها إن رأيت متابعتها.",
        "en": "A research opportunity may only come from a gap candidate you have "
              "approved yourself. Review the gap first, then approve it if you "
              "decide to pursue it.",
    },
    "synthesis.confirmation_required": {
        "ar": "هذا الإجراء يحتاج تأكيدًا صريحًا. راجِع المعاينة ثم أكّد.",
        "en": "This action needs an explicit confirmation. Review the preview, then confirm.",
    },
    "synthesis.gap_carries_an_opportunity": {
        "ar": "لا يمكن سحب اعتماد فجوةٍ أُنشئت فوقها فرصة بحثية. "
              "احذف الفرصة أولًا إن كنت تريد إعادة النظر في الفجوة.",
        "en": "A gap that already carries a research opportunity cannot be "
              "un-approved. Remove the opportunity first if you want to reconsider it.",
    },
    "synthesis.project_already_created": {
        "ar": "سبق أن أُنشئ بحثٌ من هذه الفرصة.",
        "en": "A project has already been created from this opportunity.",
    },
    "auth.current_password_wrong": {
        "ar": "كلمة المرور الحالية غير صحيحة.",
        "en": "The current password is incorrect.",
    },
    "auth.password_too_short": {
        "ar": "كلمة المرور الجديدة أقصر من ١٢ حرفًا.",
        "en": "The new password is shorter than 12 characters.",
    },
    "auth.password_too_long": {
        "ar": "كلمة المرور الجديدة أطول مما يُقبل.",
        "en": "The new password is longer than allowed.",
    },
    "auth.password_unchanged": {
        "ar": "كلمة المرور الجديدة مطابقة للحالية.",
        "en": "The new password is the same as the current one.",
    },
    "auth.reset_token_invalid": {
        "ar": "رابط إعادة التعيين غير صالح أو انتهت صلاحيته. اطلب رابطًا جديدًا.",
        "en": "This reset link is invalid or has expired. Request a new one.",
    },
    "auth.reset_rate_limited": {
        "ar": "طُلبت الاستعادة مرات كثيرة. انتظر قليلًا ثم أعد المحاولة.",
        "en": "Too many recovery requests. Wait a little, then try again.",
    },
    "portfolio.profile_required": {
        "ar": "يلزم إنشاء الملف الأكاديمي قبل إنشاء مشروع بحثي.",
        "en": "An academic profile is required before creating a research project.",
    },
    "evidence.reference_search_rate_limited": {
        "ar": "بحثٌ متكرّر أكثر من اللازم. البحث يسأل فهارس علمية تمنحنا الاستعمال بأدبٍ لا بعقد، فننتظر قليلًا حمايةً لبقية الباحثين — وليست هذه «لا نتائج».",
        "en": "Too many searches in a row. Each search asks scholarly indexes that grant us access by courtesy, so we pause briefly to protect other researchers — this is not “no results”.",
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
    # ── Wave 1-C: حدودُ إعادة المعالجة تُقال بلغة الباحث ──
    "thesis.processing_in_flight": {
        "ar": "المعالجة جارية على هذه الرسالة الآن؛ انتظر انتهاءها قبل طلب إعادتها.",
        "en": "This thesis is being processed right now; wait for it to finish before asking again.",
    },
    # **حدٌّ يُعلَن ولا يُخفى خلف زرٍّ يخذل.** إعادة قراءة مستندٍ ممسوح
    # ضوئيًّا تُنتج النتيجة نفسها حرفًا بحرف ما دام لا OCR.
    "thesis.retry_needs_ocr": {
        "ar": "المستند ممسوح ضوئيًّا بلا طبقة نصّ؛ إعادة القراءة لن تغيّر شيئًا "
              "ما دامت القراءة الضوئية (OCR) غير متاحة.",
        "en": "The document is scanned with no text layer; rereading changes nothing "
              "while OCR is unavailable.",
    },
    "thesis.unknown_view": {
        "ar": "خيار العرض غير معروف.", "en": "Unknown listing view.",
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
    # ── فرق البحث ٢ (الترحيل 0028) ──
    "team.not_a_project_member": {
        "ar": "لست عضوًا في هذا البحث.", "en": "You are not a member of this project.",
    },
    "team.access_suspended": {
        "ar": "وصولك إلى هذا البحث موقوف.",
        "en": "Your access to this project is suspended.",
    },
    "team.access_removed": {
        "ar": "أُزيلت عضويتك من هذا البحث.",
        "en": "Your membership in this project was removed.",
    },
    "team.invitation_not_accepted": {
        "ar": "دعوتك إلى هذا البحث لم تُقبل بعد.",
        "en": "Your invitation to this project has not been accepted yet.",
    },
    "team.permission_required": {
        "ar": "لا تملك الصلاحية المطلوبة في هذا البحث.",
        "en": "You do not hold the required permission in this project.",
    },
    "team.unknown_permission": {
        "ar": "صلاحية غير معروفة.", "en": "Unknown project permission.",
    },
    "team.unknown_access_state": {
        "ar": "حال وصول غير معروفة.", "en": "Unknown access state.",
    },
    "team.unknown_event_kind": {
        "ar": "نوع حدث غير معروف في سجل الفريق.",
        "en": "Unknown team lifecycle event kind.",
    },
    "team.invalid_invitation": {
        "ar": "بيانات الدعوة غير صالحة.", "en": "Invalid invitation details.",
    },
    "team.invitation_not_found": {
        "ar": "الدعوة غير موجودة.", "en": "Invitation not found.",
    },
    "team.invitation_not_open": {
        "ar": "هذه الدعوة لم تعد قائمة.", "en": "This invitation is no longer open.",
    },
    "team.invitation_expired": {
        "ar": "انتهت مهلة الدعوة.", "en": "The invitation has expired.",
    },
    "team.invitation_already_live": {
        "ar": "توجد دعوة قائمة لهذا البريد في هذا البحث.",
        "en": "A live invitation already exists for this email in this project.",
    },
    "team.invitation_not_yours": {
        "ar": "هذه الدعوة ليست لحسابك.",
        "en": "This invitation was not issued to your account.",
    },
    "team.already_a_member": {
        "ar": "هذا الحساب عضو في البحث بالفعل.",
        "en": "This account is already a member of the project.",
    },
    "team.consent_is_personal": {
        "ar": "الموافقة على التأليف فعل صاحبها؛ لا تُسجَّل عنه (§24).",
        "en": "Author consent is the author's own act; it is not recorded on their "
              "behalf (§24).",
    },
    "team.use_the_personal_consent_route": {
        "ar": "موافقتك أنت تُسجَّل من مسارها الشخصي، لا من المسار الإداري.",
        "en": "Record your own consent through the personal route, not the "
              "administrative one.",
    },
    "team.consent_needs_authorship": {
        "ar": "الموافقة تلزم من أُعلن مؤلفًا؛ وعضوية الفريق ليست تأليفًا (§24).",
        "en": "Consent applies to a declared author; team membership is not "
              "authorship (§24).",
    },
    "team.consent_needs_an_account": {
        "ar": "الموافقة تحتاج عضوًا مربوطًا بحساب حقيقي.",
        "en": "Consent requires a member linked to a real account.",
    },
    "team.proxy_consent_needs_evidence": {
        "ar": "الموافقة الإدارية تلزمها إشارة إلى سند مكتوب.",
        "en": "Administrative consent requires a reference to written evidence.",
    },
    "team.last_manager": {
        "ar": "لا يبقى البحث بلا من يديره.",
        "en": "A project cannot be left with nobody able to manage its team.",
    },
    "thesis.consent_is_personal": {
        "ar": "الموافقة على التأليف فعل صاحبها؛ وتسجيلها عنه يلزمه سند مكتوب (§24).",
        "en": "Author consent is the author's own act; recording it for them "
              "requires written evidence (§24).",
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
    # ── إدارة المشروع البحثي (Wave1-B) ──
    "project_management.project_not_found": {
        "ar": "البحث غير موجود أو خارج نطاق صلاحيتك.",
        "en": "Project not found or outside your scope.",
    },
    "project_management.project_not_in_trash": {
        "ar": "هذا البحث ليس في السلّة — والإتلاف الدائم يسبقه نقلٌ إليها.",
        "en": "This project is not in the trash; permanent deletion is preceded "
              "by moving it there.",
    },
    "project_management.task_not_found": {
        "ar": "المهمّة غير موجودة في هذا البحث.",
        "en": "That task does not exist in this project.",
    },
    "project_management.member_not_in_project": {
        "ar": "لا تُسنَد المهمّة إلا إلى عضوٍ في فريق هذا البحث.",
        "en": "A task can only be assigned to a member of this project's team.",
    },
    "project_management.milestone_unknown": {
        "ar": "مَعْلَمٌ غير معروف.",
        "en": "Unknown milestone.",
    },
    "project_management.permanent_delete_blocked": {
        "ar": "الإتلاف الدائم موقوف: لا سياسةَ احتفاظٍ قابلةً للتنفيذ في هذا "
              "النظام، فلا يُتلَف ما لا تُعرف مشروعيّة إتلافه. والبحث باقٍ في "
              "السلّة ويمكن استعادته كما هو.",
        "en": "Permanent deletion is blocked: this system has no enforceable "
              "retention policy, so nothing is destroyed whose destruction cannot "
              "be shown to be lawful. The project stays in the trash and can be "
              "restored unchanged.",
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
