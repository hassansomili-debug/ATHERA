---
project: ATHERA
document_type: PRD_SRS
version: "1.2"
language: ar
status: baseline
primary_consumers:
  - Claude Code
  - software_engineering_team
  - product_design_team
source_of_truth: true
---

# ATHERA — Product Requirements + Software Requirements Specification

> **Claude/Engineering rule:** Treat this document as the product baseline and source of truth. Do not silently remove, relax, or reinterpret requirements. When implementation requires an assumption, record it explicitly as an ADR or open question. Human approval gates, research-integrity controls, evidence provenance, and no-fabrication rules are mandatory.

# **ATHERA \| أثيرا**

## **وثيقة متطلبات المنتج والنظام الشاملة (PRD + SRS)**

الإصدار: 1.2  
التاريخ: 30 أغسطس 2026  
الحالة: Baseline للتصميم والبرمجة  
نوع المنتج: منصة ويب مستقلة متعددة المستأجرين للذكاء البحثي وإدارة الإنتاج العلمي والترقية الأكاديمية  
الاسم التجاري المبدئي: ATHERA \| أثيرا  
وصف مختصر: Research Intelligence & Academic Promotion Operating System

# 1. الملخص التنفيذي

ATHERA منصة بحثية مستقلة تُبنى حول **عقل بحثي مركزي (AI Research Brain)** وليس حول روبوت محادثة عام. وظيفة المنصة هي إدارة دورة العمل البحثي كاملة منذ بناء ملف الباحث وتحليل متطلبات الترقية، مرورًا باكتشاف الفرص البحثية، ومراجعة الأدبيات، وتصميم المنهج، وإدارة الأخلاقيات والبيانات والتحليل، وكتابة المخطوطة، واختيار المجلة، والتقديم والتحكيم، وحتى تكوين ملف الترقية الأكاديمية.

الميزة الجوهرية للمنصة هي أن كل قرار أو حقيقة أو ادعاء أو نتيجة أو ترشيح مجلة يكون **موثقًا وقابلًا للتتبع**؛ فلا يُسمح للذكاء الاصطناعي باختلاق مراجع أو بيانات أو نتائج، ولا تُحفظ الحقائق المهمة كذاكرة محادثة غير منظمة. كل معلومة مهمة يجب أن تُخزن ككائن منظم له مصدر وحالة تحقق وتاريخ وموافقة بشرية عند الحاجة.

تبدأ النسخة الأولى بالتخصصات المرتبطة بـ **الإعلان والاتصال التسويقي والإعلام والعلاقات العامة والاتصال المؤسسي والاتصال الرقمي**، مع قابلية التوسع لاحقًا إلى تخصصات أخرى.

كما تتضمن المنصة وحدة رئيسية باسم **Thesis Intelligence & Publication Mining** لتحويل رسائل الماجستير والدكتوراه التي أشرف عليها الباحث أو يملك حق استخدامها إلى فرص أوراق علمية قابلة للنشر، مع فحص الجدة، والتداخل، وحقوق التأليف، والنشر المكرر، والتحديث النظري والمنهجي.

وتتضمن المنصة محركًا استباقيًا باسم Research Trend Intelligence & Proactive Paper Pipeline لمراقبة المستجدات والاتجاهات البحثية بصورة مستمرة، واكتشاف الفرص القابلة للنشر، وتحويل الفرص المعتمدة إلى مشاريع أوراق علمية مكتملة وجاهزة للتقديم للمجلات، مع بقاء اعتماد الباحث إلزاميًا عند القرارات العلمية الحساسة وقبل أي إرسال خارجي.

# 2. الرؤية والتموضع التجاري

## 2.1 الرؤية

بناء نظام تشغيل ذكي للباحث يربط بين المعرفة والأدلة والمنهج والتحليل والنشر والترقية الأكاديمية في مسار واحد مستمر وقابل للتدقيق.

## 2.2 الوعد القيمي

> من الفكرة إلى الورقة المنشورة وملف الترقية، بعقل بحثي يتذكر ويحلل ويتحقق ولا يختلق.

## 2.3 التموضع

ATHERA ليست:

- أداة كتابة مقالات فقط.
- مدير مراجع فقط.
- محرك بحث أكاديمي فقط.
- منصة ترقية إدارية فقط.
- مساعد محادثة عام.

ATHERA هي **Research Intelligence Platform** تجمع هذه الوظائف ضمن منظومة واحدة مرتبطة بسياسات الباحث والجامعة.

## 2.4 الشرائح المستهدفة

1.  **عضو هيئة التدريس الفردي:** لبناء محفظة أبحاث للترقية.
2.  **المشرف الأكاديمي:** لتحويل الرسائل التي أشرف عليها إلى فرص نشر وفق الحقوق والموافقات.
3.  **طالب الدراسات العليا:** لتحويل الرسالة بعد المناقشة إلى أوراق.
4.  **فريق بحثي / مركز بحثي:** لإدارة عدة مشاريع ومؤلفين.
5.  **الجامعة أو الكلية:** لمتابعة الإنتاج العلمي، وتحويل الرسائل إلى منشورات، وإدارة مسارات الترقية.

# 3. الحالة المرجعية للباحث الأول (Seed Researcher)

تُستخدم هذه الحالة لاختبار النسخة الأولى، مع تصميم جميع القواعد لتكون قابلة للتخصيص لباحثين آخرين.

| **العنصر**                   | **القيمة الأولية**                                                                          |
|------------------------------|---------------------------------------------------------------------------------------------|
| المؤسسة                      | جامعة الإمام محمد بن سعود الإسلامية                                                         |
| الرتبة الحالية               | أستاذ مشارك                                                                                 |
| الرتبة المستهدفة             | أستاذ                                                                                       |
| التخصص الرئيس                | الإعلان والاتصال التسويقي                                                                   |
| تخصصات مرتبطة                | الإعلام والاتصال، العلاقات العامة، الاتصال المؤسسي، التسويق الرقمي، وسائل التواصل الاجتماعي |
| مدة الرتبة الحالية           | أربع سنوات مكتملة                                                                           |
| الأبحاث المنشورة بعد الترقية | صفر                                                                                         |
| الوحدات البحثية الحالية      | صفر                                                                                         |
| شرط شخصي للنشر               | بحث واحد على الأقل في Web of Science/ISI الصارم                                             |
| البرامج المستخدمة فعليًا      | SPSS، SmartPLS                                                                              |
| تدريب مثبت                   | NVivo                                                                                       |
| مناهج مثبتة                  | كمي، كيفي، مختلط، استبانة، مقابلات شبه منظمة، PLS-SEM، انحدار، ارتباط، تحليل موضوعي         |

> ملاحظة نظامية: قواعد الترقية يجب ألا تكون Hard-coded على هذه الحالة؛ بل تُدار عبر **Promotion Policy Engine** مع نسخة وسياسة وتاريخ سريان ومصدر رسمي.

# 4. مبادئ المنتج غير القابلة للتفاوض

1.  **Evidence First:** لا يوجد ادعاء علمي نهائي بلا دليل أو وسم واضح بأنه استنتاج/اقتراح.
2.  **No Fabrication:** لا اختلاق لمراجع أو DOI أو بيانات أو جداول أو نتائج.
3.  **Human-in-the-Loop:** القرارات الحساسة تحتاج اعتمادًا بشريًا.
4.  **Policy Aware:** الترقية واختيار المجلات يحكمهما نص السياسة الفعلية وتاريخها.
5.  **Reproducible Analysis:** أي نتيجة تحليلية يجب أن تكون مرتبطة ببيانات وكود/إعدادات تشغيل.
6.  **Provenance by Design:** كل عنصر مهم له مصدر وموقع وتاريخ وحالة تحقق.
7.  **Provider Independent:** لا تُربط المنصة بمزود نموذج واحد.

Backend-mediated AI: يمنع الاتصال المباشر بين واجهة المستخدم ومزود النموذج؛ تمر جميع استدعاءات AI عبر طبقة الخادم والسياسات والتدقيق.

8.  **Privacy by Design:** فصل البيانات الشخصية عن الذاكرة البحثية، وتقليل البيانات الحساسة.
9.  **No Salami Slicing:** منع التجزئة المفرطة للرسائل أو البيانات إلى أوراق ضعيفة متداخلة.
10. **No Autonomous Authorship Decisions:** الذكاء الاصطناعي لا يحدد مستحقي التأليف من تلقاء نفسه.
11. **Current Journal Verification:** حالة المجلة والفهرسة والرسوم والسياسات يجب أن تكون مؤرخة وقابلة لإعادة التحقق.
12. **Academic Responsibility:** الباحث هو صاحب الاعتماد النهائي والمسؤول عن التقديم والمحتوى.

# 5. نطاق المنتج

## 5.1 داخل النطاق

- ملف الباحث الأكاديمي.
- لائحة الترقية ومحرك احتساب المتطلبات.
- بناء محفظة بحثية متعددة الأوراق.
- اكتشاف فرص بحثية.
- مراجعة الأدبيات وإدارة الأدلة.
- بناء الخيط الذهبي.
- اختيار النظرية والمنهج.
- تصميم الدراسات الكمية والكيفية والمختلطة والتجريبية والمراجعات.
- الأخلاقيات وإدارة البيانات.
- استيراد وتحليل البيانات.
- SPSS/SmartPLS/NVivo-compatible workflows.
- R/Python execution sandbox.
- كتابة المخطوطات.
- التحقق من الاستشهادات والمراجع.
- مطابقة المجلات الموثوقة.
- محاكاة التحكيم.
- تجهيز حزمة التقديم.
- إدارة ردود المحكمين.
- تحويل الرسائل إلى أوراق.
- إدارة التأليف والمساهمات CRediT.
- لوحة الجامعة/الكلية مستقبلًا.

## 5.2 خارج نطاق الإصدار الأول

- ضمان قبول الورقة.
- إرسال المخطوطة تلقائيًا لجميع أنظمة المجلات دون موافقة.
- تجاوز بوابات الدخول المدفوعة أو حقوق الناشرين.
- تدريب Foundation Model خاص من البداية.
- دعم كل التخصصات العلمية منذ اليوم الأول.
- اعتبار أدوات كشف نصوص الذكاء الاصطناعي حكمًا قاطعًا.
- تنفيذ تحليلات في برامج مغلقة إذا لم يتوفر وصول قانوني أو ملفات مناسبة.

# 6. رحلة المستخدم الرئيسية

## 6.1 رحلة الترقية

>     إنشاء الحساب
>     ↓
>     بناء الملف الأكاديمي
>     ↓
>     رفع لائحة الترقية
>     ↓
>     استخراج القواعد ومراجعتها
>     ↓
>     حساب الفجوة الحالية
>     ↓
>     بناء محفظة الأبحاث
>     ↓
>     تشغيل المشاريع بالتوازي
>     ↓
>     النشر والقبول
>     ↓
>     تجميع أدلة الترقية
>     ↓
>     فحص الجاهزية النهائية

## 6.2 رحلة الورقة العلمية

>     فرصة بحثية
>     ↓
>     فحص الجدة وقابلية التنفيذ
>     ↓
>     بروتوكول البحث
>     ↓
>     الأدبيات والخيط الذهبي
>     ↓
>     المنهج والأخلاقيات
>     ↓
>     جمع/استيراد البيانات
>     ↓
>     إغلاق البيانات
>     ↓
>     التحليل القابل لإعادة الإنتاج
>     ↓
>     المخطوطة
>     ↓
>     مطابقة المجلات
>     ↓
>     المراجعة الداخلية
>     ↓
>     حزمة التقديم
>     ↓
>     التحكيم والتعديلات
>     ↓
>     النشر

## 6.3 رحلة الرسالة إلى أوراق

>     رفع الرسالة
>     ↓
>     تفكيك بنية الرسالة
>     ↓
>     استخراج الأسئلة/الفروض/النتائج/الجداول/البيانات
>     ↓
>     اكتشاف فرص الأوراق
>     ↓
>     فحص التداخل والجدة والحقوق
>     ↓
>     تحديث الأدبيات
>     ↓
>     تحديد ما يحتاج إعادة تحليل
>     ↓
>     اختيار فرصة
>     ↓
>     تحويلها إلى مشروع بحث
>     ↓
>     المجلة والمخطوطة والتقديم

# 7. العقل البحثي المركزي AI Research Brain

## 7.1 التعريف

العقل البحثي ليس Prompt واحدًا أو Chatbot، بل طبقة تنسيق وذاكرة واستدلال وحوكمة تضم:

- Persistent Structured Memory.
- Research Knowledge Graph.
- Evidence-grounded Retrieval.
- Agent Orchestration.
- Tool Execution.
- Policy Engine.
- Integrity Guardrails.
- Approval Engine.
- Provenance & Audit Trail.

## 7.2 المعمارية المنطقية

>     Web / Mobile UI
>           |
>     Workspace API
>           |
>     Research Brain Orchestrator
>           |-- Memory Manager
>           |-- Knowledge Graph
>           |-- Evidence Retriever
>           |-- Policy Engine
>           |-- Agent Router
>           |-- Tool Registry
>           |-- Integrity Guardrails
>           |-- Approval Manager
>           |-- Provenance Logger
>           |
>     Execution & Data Layer
>           |-- PostgreSQL
>           |-- pgvector
>           |-- Object Storage
>           |-- Workflow Engine
>           |-- Python/R Sandbox
>           |-- Scholarly APIs

## 7.3 فئات الذاكرة

| **فئة الذاكرة**    | **أمثلة**                       | **التحقق المطلوب**         |
|--------------------|---------------------------------|----------------------------|
| Researcher Fact    | الرتبة، التخصص، المهارات        | مستخدم أو مصدر موثق        |
| Promotion Policy   | الوحدات، النقاط، شروط المجلات   | مصدر رسمي + تاريخ سريان    |
| Verified Evidence  | دراسة، DOI، نتيجة منشورة        | تحقق ببليوغرافي            |
| Project Decision   | السؤال، النظرية، المنهج، المجلة | موافقة بشرية               |
| Working Hypothesis | فكرة أو علاقة مقترحة            | وسم Provisional            |
| Journal Fact       | الفهرسة، الرسوم، النطاق         | مصدر + Last Verified       |
| Analysis Result    | قيمة إحصائية أو جدول            | Run ID قابل لإعادة الإنتاج |
| Temporary Context  | محادثة مؤقتة                    | سياسة انتهاء صلاحية        |

## 7.4 قاعدة ترقية الذاكرة

لا يجوز تحويل مخرجات النموذج إلى **Verified Memory** تلقائيًا. يلزم أحد الآتي:

- مصدر خارجي موثق.
- ملف مرفوع مع Locator واضح.
- نتيجة تشغيل تحليل فعلية.
- تأكيد صريح من الباحث.

# 8. الأجنتات المتخصصة

| **الأجنت**          | **المسؤولية**                         | **القيود**                         |
|---------------------|---------------------------------------|------------------------------------|
| Research Manager    | إدارة المشروع والحالة والخطوات        | لا يتجاوز الاعتمادات               |
| Promotion Auditor   | تحليل اللائحة وحساب الفجوة            | لا يفترض قاعدة غير موثقة           |
| Opportunity Scout   | اكتشاف الأفكار والفجوات               | لا يختلق اتجاهات أو دراسات         |
| Literature Agent    | البحث والاسترجاع                      | يميز Metadata عن Full Text         |
| Evidence Curator    | التحقق من المراجع والأدلة             | لا يعتمد مصدرًا غير متحقق           |
| Golden Thread Agent | ربط المشكلة والأسئلة والمنهج والنتائج | لا يغير عناصر معتمدة صامتًا         |
| Theory Agent        | اقتراح الإطار النظري                  | يوضح البدائل والقيود               |
| Methodology Agent   | التصميم والعينة والأداة               | لا يفرض منهجًا لا يجيب عن السؤال    |
| Ethics Agent        | الأخلاقيات والموافقات والخصوصية       | يمنع تجاوز الموافقات               |
| Data Agent          | جودة البيانات وإصداراتها              | لا يعدل Raw Data                   |
| Analysis Agent      | تنفيذ التحليل الموثق                  | لا ينشئ أرقامًا تخمينية             |
| Scientific Writer   | صياغة الورقة من مصادر معتمدة          | لا يكتب نتائج غير موجودة           |
| Journal Matcher     | مطابقة المجلات                        | لا يضمن القبول                     |
| Peer Review Council | مراجعة نظرية/منهجية/إحصائية/تحريرية   | لا يعدل النسخة النهائية دون قرار   |
| Revision Agent      | إدارة ردود المحكمين                   | لا يدعي تنفيذ تعديل غير منفذ       |
| Thesis Miner        | استخراج فرص النشر من الرسائل          | يمنع النشر المكرر والتجزئة المفرطة |
| Authorship Agent    | إدارة المساهمات والموافقات            | لا يمنح التأليف تلقائيًا            |

# 9. بوابات الاعتماد البشري

| **الرمز** | **البوابة**         | **المطلوب قبل الانتقال**                |
|-----------|---------------------|-----------------------------------------|
| G0        | ملف الباحث والسياسة | اعتماد الهوية والقواعد                  |
| G1        | اختيار الفرصة       | اعتماد فكرة البحث                       |
| G2        | البروتوكول          | اعتماد المشكلة والأسئلة والأهداف        |
| G3        | النظرية             | اعتماد الإطار/النموذج                   |
| G4        | المنهج والأخلاقيات  | اعتماد التصميم والموافقات               |
| G5        | الأداة والعينة      | اعتماد المقاييس وخطة الجمع              |
| G6        | إغلاق البيانات      | تثبيت نسخة البيانات المستخدمة           |
| G7        | خطة التحليل         | اعتماد الاختبارات قبل التنفيذ           |
| G8        | تفسير النتائج       | اعتماد القراءة العلمية للنتائج          |
| G9        | المخطوطة            | اعتماد النسخة الجاهزة للمطابقة          |
| G10       | المجلة              | اعتماد المجلة المستهدفة                 |
| G11       | التقديم             | اعتماد الحزمة النهائية                  |
| G12       | رد المحكمين         | اعتماد الرد والنسخة المعدلة             |
| GT1       | حقوق الرسالة        | اعتماد الملكية/التأليف قبل استخراج ورقة |

# 10. وحدة ملف الباحث الأكاديمي

## 10.1 البيانات

- المؤسسة والكلية والقسم.
- الرتبة الحالية والمستهدفة.
- التخصصات والكلمات المفتاحية.
- ORCID ومعرفات الباحث الأخرى.
- قائمة المنشورات السابقة.
- النظريات والمناهج المستخدمة.
- البرمجيات التحليلية.
- اللغات العلمية.
- المشاريع والاستشارات والخبرات.
- الاهتمامات البحثية المستقبلية.
- الأبحاث التي لا يريد الباحث تكرارها.
- تفضيلات الكتابة والتنسيق.

## 10.2 استخراج المعرفة من الملفات

عند رفع CV أو رسائل أو أوراق سابقة، يستخرج النظام الحقائق إلى شاشة مراجعة:

- Fact.
- Source File.
- Page/Section.
- Confidence.
- Status: Unverified / Approved / Rejected.

لا تُحفظ المعلومة كحقيقة دائمة قبل الاعتماد.

# 11. محرك الترقية Promotion Policy Engine

## 11.1 الهدف

تحويل اللوائح إلى قواعد تنفيذية قابلة للحساب، دون ربط المنصة بجامعة واحدة.

## 11.2 نموذج السياسة

>     policy:
>       institution_id: UUID
>       policy_name: "Academic Promotion Policy"
>       version: "2026"
>       effective_from: "YYYY-MM-DD"
>       effective_to: null
>       source_document_id: UUID
>       verification_status: verified

## 11.3 أنواع القواعد

- مدة الخدمة.
- الحد الأدنى من الوحدات.
- الأعمال المنفردة.
- طريقة احتساب المشاركة.
- الحد الأدنى من المجلات المحكمة.
- تنوع منافذ النشر.
- نقاط الإنتاج العلمي.
- شروط الفهرسة.
- شروط التاريخ.
- استبعاد الرسائل أو الاستلال منها.
- شروط المؤلف الأول/المراسل إن وجدت.
- متطلبات التدريس والخدمة.

## 11.4 الحالة المرجعية الأولية

يُعرض في الحساب الأولي:

- مدة الأربع سنوات: مكتملة.
- الأبحاث بعد الترقية: 0.
- الوحدات: 0.
- شرط بحث WoS/ISI شخصي: غير مكتمل.

أي متطلب جامعي غير مثبت من مصدر ساري يوضع **Needs Institutional Verification**.

## 11.5 حاسبة الوحدات

يجب أن تكون قواعد احتساب التأليف قابلة للتخصيص حسب اللائحة، مع سيناريوهات What-if.

مثال واجهة:

| **الورقة** | **المؤلفون** | **دور الباحث** | **الوحدة المحتسبة** | **الحالة** |
|------------|--------------|----------------|---------------------|------------|
| Paper A    | 1            | Sole Author    | 1.00                | Planned    |
| Paper B    | 2            | Co-author      | 0.50                | Accepted   |

## 11.6 السيناريوهات

- الحد الأدنى النظامي.
- السيناريو الآمن.
- السيناريو الطموح.
- أثر رفض أو تأخر ورقة.
- أثر تغير فهرسة مجلة.

# 12. محفظة الأبحاث Research Portfolio

## 12.1 الهدف

إدارة عدة أوراق متوازية تخدم خطًا علميًا واحدًا بدل أبحاث متفرقة.

## 12.2 حقول المشروع

- العنوان المؤقت.
- Research Program.
- نوع الدراسة.
- حالة المشروع.
- المؤلفون.
- الوحدة المتوقعة للترقية.
- المجلة المستهدفة.
- فئة الفهرسة المطلوبة.
- المخاطر.
- الموعد المستهدف.
- الاعتماد الحالي.

## 12.3 الخطة المرجعية

الخطة الأولية المستهدفة للحالة المرجعية:

- 8 مشاريع بحثية تخطيطية.
- 6 أوراق منفردة مستهدفة.
- بحث رئيس مستهدف لـSSCI/AHCI/SCIE.
- بحث Web of Science احتياطي.
- 7 وحدات تخطيطية كهوامش أمان.

هذه الخطة **مقترحة وليست قاعدة ثابتة**، وتبقى قابلة لإعادة الترتيب.

# 13. مستكشف الفرص البحثية

## 13.1 المدخلات

- اهتمامات الباحث.
- أعماله السابقة.
- اتجاهات الأدبيات الحديثة.
- بيانات يمكن الوصول إليها.
- متطلبات الترقية.
- المجلات المستهدفة.
- القيود الزمنية والميزانية.

## 13.2 المخرجات

لكل فرصة:

- عنوان مبدئي.
- المشكلة.
- الفجوة.
- الجدة.
- السؤال المركزي.
- النظرية المحتملة.
- المنهج.
- البيانات.
- سهولة التنفيذ.
- المجلات المحتملة.
- قيمة الترقية.
- المخاطر.
- درجة الأولوية.

## 13.3 أنواع الفجوات

- نظرية.
- منهجية.
- سياقية/جغرافية.
- قطاعية.
- زمنية.
- تناقض في النتائج.
- قياس/Scale Gap.
- بيانات جديدة.
- إعادة اختبار نظرية في سياق سعودي.

# 14. محرك الأدبيات والأدلة

## 14.1 المصادر المستهدفة

- OpenAlex.
- Crossref.
- ORCID.
- DOAJ.
- ROR.
- Web of Science عبر وصول مرخص.
- Scopus عبر وصول مرخص.
- ملفات PDF التي يرفعها المستخدم قانونيًا.
- مكتبات الجامعة المصرح بها.

## 14.2 حالات الوصول إلى النص

- Open Access Full Text.
- User Uploaded / Rights Confirmed.
- Licensed Institutional Access.
- Abstract/Metadata Only.
- Restricted / No Processing Right.

## 14.3 سجل المصدر

- DOI.
- العنوان.
- المؤلفون.
- السنة.
- المجلة.
- النظرية.
- المنهج.
- العينة.
- النتائج.
- القيود.
- حالة التصحيح/السحب.
- حقوق الوصول.
- آخر تحقق.

## 14.4 Claim-to-Evidence Ledger

كل ادعاء جوهري في الورقة يجب أن يكون له:

>     {
>       "claim": "...",
>       "claim_type": "empirical|theoretical|contextual|interpretive",
>       "section": "literature_review",
>       "evidence_ids": ["EV-..."],
>       "support_level": "direct|partial|contextual|contradictory",
>       "verification_status": "verified",
>       "reviewed_by": "researcher-id"
>     }

## 14.5 قواعد المنع

- المرجع غير المتحقق لا يدخل النسخة النهائية.
- لا يُستشهد ببحث مسحوب دون تحذير وسياق واضح.
- لا تُستخدم Metadata-only كمصدر لتفاصيل لم تُتحقق من النص.

# 15. مختبر الخيط الذهبي Golden Thread Lab

## 15.1 العلاقات الأساسية

>     الظاهرة → المشكلة → الفجوة → السؤال → الهدف → النظرية → المتغيرات/المحاور → المنهج → الأداة → التحليل → النتائج → المناقشة → التوصيات

## 15.2 اختبارات الاتساق

النظام يجب أن يكتشف:

- هدفًا بلا سؤال.
- سؤالًا بلا تحليل.
- فرضًا بلا متغيرات قابلة للقياس.
- متغيرًا في العنوان غير موجود في الأداة.
- نتيجة لا تجيب عن سؤال.
- توصية بلا نتيجة داعمة.
- نظرية مذكورة ولم تُستخدم في المناقشة.
- تعميمًا أكبر من العينة.
- لغة سببية في دراسة ارتباطية.

## 15.3 درجة الاتساق

Golden Thread Score من 100 مع شرح العناصر المفقودة، مع منع استخدام الدرجة وحدها كحكم نهائي.

# 16. مختبر المنهجية

## 16.1 الدراسات الكمية

- تحديد المتغيرات.
- النموذج المفاهيمي.
- الفروض.
- التعريفات الإجرائية.
- المجتمع والعينة.
- حساب حجم العينة.
- أسلوب المعاينة.
- المقاييس.
- التحكيم والترجمة والـBack Translation عند الحاجة.
- Pilot Study.
- Reliability / Validity.
- Common Method Bias عند الحاجة.
- خطة التحليل.

## 16.2 الدراسات الكيفية

- نوع التصميم.
- استراتيجية اختيار المشاركين.
- دليل المقابلات.
- التشبع.
- التسجيل والتفريغ.
- Codebook.
- التحليل الموضوعي/المضمون.
- Reflexivity/Audit Trail.
- Member Checking أو Peer Debriefing عند ملاءمته.

## 16.3 الدراسات المختلطة

- Sequential / Concurrent.
- أولوية المسار.
- Integration Point.
- Joint Displays.
- Meta-inferences.

## 16.4 التجارب

- Randomization.
- Conditions.
- Manipulation Check.
- Pre-registration إن لزم.
- Power Analysis.
- Mediators/Moderators.

## 16.5 المراجعات العلمية

- Systematic Review.
- Scoping Review.
- Integrative Review.
- Bibliometric Review.
- Meta-analysis.
- بروتوكول البحث.
- Search Strings.
- Screening.
- Inclusion/Exclusion.
- Quality Appraisal.
- PRISMA-compatible tracking عند الملاءمة.

# 17. الأخلاقيات وإدارة البيانات

## 17.1 الوظائف

- تحديد الحاجة إلى موافقة أخلاقية.
- نموذج الموافقة.
- Participant Information Sheet.
- خطة إخفاء الهوية.
- سياسة الاحتفاظ.
- Data Management Plan.
- سجل من اطلع على البيانات.
- تصنيف الحساسية.

## 17.2 إصدارات البيانات

>     RAW (immutable)
>     ↓
>     CLEANED v1/v2/...
>     ↓
>     ANALYSIS LOCKED VERSION
>     ↓
>     DERIVED DATASETS

لا يجوز تعديل RAW Dataset.

## 17.3 إغلاق البيانات

بوابة G6 تنتج Data Freeze ID يُستخدم في جميع التحليلات اللاحقة.

# 18. محرك التحليل

## 18.1 مبادئ

- التحليل الفعلي ينفذ في بيئة حسابية، لا داخل النص التوليدي.
- كل تشغيل له Run ID.
- حفظ Code + Packages + Version + Dataset Version.
- الجداول والأشكال مرتبطة بنتيجة فعلية.

## 18.2 البرامج والمسارات

### SPSS

- استيراد وتصدير SAV.
- توليد Syntax قابل للمراجعة.
- Descriptives.
- Reliability.
- Correlation.
- Regression.
- ANOVA/ANCOVA عند الحاجة.

### SmartPLS

- تجهيز Dataset.
- Measurement Model Checklist.
- Reflective/Formative Constructs.
- Reliability/AVE/HTMT.
- Bootstrapping.
- Structural Model.
- R²/Q²/Effect Sizes حسب المنهج المعتمد.
- Export-ready outputs.

### NVivo

- Codebook.
- Cases/Nodes Mapping.
- Coding Export Templates.
- Theme Matrix.
- توافق مع ملفات التصدير عند توفرها.

### R / Python

- Reproducible Scripts.
- Environment Locking.
- Statistical validation.
- Data visualization.

## 18.3 التفسير

الذكاء الاصطناعي يفسر **النتائج الفعلية فقط**، ويجب أن يفرق بين:

- Result.
- Statistical interpretation.
- Theoretical interpretation.
- Managerial implication.

# 19. استوديو كتابة المخطوطة

## 19.1 الأقسام

- Title.
- Abstract.
- Keywords.
- Introduction.
- Problem / Gap.
- Literature Review.
- Theory.
- Hypotheses/Questions.
- Method.
- Results.
- Discussion.
- Contributions.
- Implications.
- Limitations.
- Future Research.
- Conclusion.
- Declarations.
- References.

## 19.2 قواعد الكتابة

- الكتابة من Verified Evidence فقط للادعاءات العلمية.
- نتائج البحث من Analysis Runs فقط.
- لا يتم تغيير سؤال/فرض معتمد دون Version Change.
- دعم العربية والإنجليزية.
- إمكانية تعلم Style Preference من نصوص اعتمدها الباحث، دون نسخ حرفي غير مشروع.

## 19.3 التصدير

- DOCX.
- PDF.
- LaTeX.
- Reference Styles عبر CSL.
- Journal-specific formatting لاحقًا.

# 20. محرك مطابقة المجلات Journal Intelligence

## 20.1 سجل المجلات

لكل مجلة:

- الاسم.
- ISSN/eISSN.
- الناشر.
- البلد.
- النطاق.
- أنواع المقالات.
- اللغة.
- Web of Science Index.
- Scopus Status.
- تاريخ بداية/نهاية التغطية.
- JCR Quartile عند توفر ترخيص.
- CiteScore Quartile عند توفر بيانات مرخصة.
- OA Model.
- APC.
- AI Policy.
- Submission Requirements.
- Last Verified.

## 20.2 طبقات الثقة

- **A:** WoS strict: SSCI/AHCI/SCIE active.
- **B:** WoS other, مثل ESCI، مع توضيح أنه لا يحقق الشرط الصارم افتراضيًا.
- **C:** Scopus active trusted journals.
- **D:** Peer-reviewed journals المقبولة وفق سياسة المؤسسة عند التحقق.
- **X:** Excluded / discontinued / suspicious / mismatched.

## 20.3 شرط ISI/WoS الشخصي

الإعداد الأولي:

>     strict_wos_requirement:
>       minimum_papers: 1
>       indexes: [SSCI, AHCI, SCIE]
>       count_esci: false
>       verify_at: [shortlisting, submission, acceptance, publication]

## 20.4 المطابقة

درجة من 100 تعتمد على:

- Scope Fit.
- Recent Article Similarity.
- Method Fit.
- Promotion Fit.
- Indexing Status.
- Integrity/Publisher Trust.
- Cost.
- OA/License.
- Review/Decision information إذا كان موثوقًا.

لا يتم توليد **Acceptance Probability** غير موثقة.

# 21. مجلس المحكّمين الافتراضي

يشغّل مراجعات منفصلة:

1.  **Theoretical Reviewer**.
2.  **Methodological Reviewer**.
3.  **Statistical Reviewer**.
4.  **Editorial Reviewer**.
5.  **Integrity Reviewer**.

## 21.1 التقرير

- Strengths.
- Major Concerns.
- Minor Concerns.
- Potential Rejection Reasons.
- Required Changes.
- Readiness Status: Not Ready / Major Revision / Minor Revision / Ready to Submit.

لا يجوز للمراجع الافتراضي تعديل النسخة المعتمدة مباشرة؛ يقترح Patch ويحتاج اعتمادًا.

# 22. مركز التقديم والتحكيم

## 22.1 حزمة التقديم

- Main Manuscript.
- Blinded Manuscript.
- Title Page.
- Cover Letter.
- Highlights.
- Graphical Abstract عند الحاجة.
- Figures/Tables.
- Data Availability Statement.
- Funding.
- Conflict of Interest.
- CRediT Contributions.
- AI Disclosure.
- Reporting Checklist.

## 22.2 إدارة المحكمين

عند رفع Decision Letter:

- استخراج كل تعليق.
- تصنيفه.
- ربطه بالقسم.
- تعيين مسؤول.
- اقتراح رد.
- إثبات أن التعديل نُفذ.
- إنتاج Response to Reviewers.
- إنتاج Clean / Marked versions.

# 23. Thesis Intelligence & Publication Mining

## 23.1 الهدف

تحويل الرسائل العلمية إلى **فرص نشر مستقلة ومشروعة** بدل تحويل الفصول حرفيًا إلى أوراق.

## 23.2 من يحق له استخدام الوحدة

- صاحب الرسالة.
- المشرف الذي لديه حق مشروع واستخدام بموافقة صاحب الرسالة والمؤلفين.
- الجامعة أو الجهة المالكة وفق السياسة القانونية.

يجب وجود **Rights & Authorship Gate** قبل التقديم.

## 23.3 Thesis Parser

يستخرج:

- Title / Degree / Year.
- Research Problem.
- Questions / Hypotheses.
- Objectives.
- Theories.
- Constructs/Variables.
- Population/Sample.
- Instruments.
- Data Sources.
- Analyses.
- Main/Secondary Results.
- Tables/Figures.
- Limitations.
- Future Research.
- Appendices.

## 23.4 Publication Opportunity Miner

يكتشف:

- سؤال مستقل.
- Sub-model قابل للنشر.
- مرحلة كيفية مستقلة.
- Scale Development Paper.
- Antecedents Paper.
- Consequences Paper.
- Comparative Paper.
- Null/Unexpected Results.
- Secondary Analysis.
- Extension Paper.

## 23.5 نوعا الورقة

### Extraction Paper

تعتمد على سؤال ونتائج موجودة أصلًا في الرسالة، مع تحديث ضروري للأدبيات والصياغة.

### Extension Paper

تضيف سؤالًا أو تحليلًا أو إطارًا أو مقارنة جديدة باستخدام البيانات بشكل مشروع.

## 23.6 Publication Readiness Score

درجة من 100 تشمل:

- Novelty 20.
- Independent Research Question 15.
- Independent Results 15.
- Method/Data Strength 15.
- Topic Currency 10.
- Literature Update Feasibility 10.
- Journal Fit 10.
- Overlap Risk 5.

المخرجات:

- Ready to Convert.
- Needs Re-analysis.
- Needs Major Theoretical Update.
- Merge with Another Opportunity.
- Do Not Publish Separately.

## 23.7 Overlap Matrix

المقارنة بين الأوراق المقترحة تشمل:

- Research Question overlap.
- Sample overlap.
- Variable overlap.
- Result overlap.
- Table/Figure overlap.
- Text overlap.
- Published-output overlap.

النظام يطلق Salami Slicing Alert عند تجاوز قواعد تحددها سياسات التحرير/النزاهة.

## 23.8 تحديث الرسالة

قبل تحويل أي رسالة قديمة:

- حساب عمر البيانات.
- حساب عمر الأدبيات.
- تحديث البحث حتى الوقت الحالي.
- إعادة تقييم الفجوة.
- فحص هل نُشرت دراسات أو أوراق من الرسالة سابقًا.
- اقتراح إعادة تحليل عند وجود قيمة علمية مشروعة.

## 23.9 Authorship & Rights Manager

الحقول:

- Thesis Owner.
- Main Supervisor.
- Co-supervisors.
- Existing Publications from Thesis.
- Intended Authors.
- CRediT Roles.
- Consent/Agreement Files.
- Authorship Approval Status.

لا يسمح النظام بوضع المشروع في Ready to Submit إذا لم تُعتمد الحقوق والتأليف.

## 23.10 Supervision Research Portfolio

لوحة للمشرف تعرض:

- جميع الرسائل التي أشرف عليها.
- عدد فرص النشر المكتشفة.
- فرص جاهزة/تحتاج تحديث/مرفوضة.
- الترابط الموضوعي بين الرسائل.
- فرص بحث جديدة تجمع خطًا علميًا عبر عدة رسائل دون دمج بيانات غير مصرح بها.

## 23.11 مؤشر الجامعة

**Thesis-to-Publication Rate**:

- عدد الرسائل المكتملة.
- عدد الأوراق المنشورة منها.
- عدد الفرص المحتملة.
- متوسط الزمن من المناقشة إلى النشر.

# 24. التأليف والمساهمات

## 24.1 CRediT

تدعم المنصة الأدوار الأربعة عشر القياسية مع قابلية تخصيصها.

## 24.2 القواعد

- AI لا يكون مؤلفًا.
- التأليف يحتاج قرارًا بشريًا.
- يسجل تاريخ كل تغيير في ترتيب المؤلفين.
- لا يضمن الإشراف وحده التأليف؛ تُعرض مساهمات فعلية وسياسة الجهة.
- يجب حفظ موافقة المؤلفين قبل التقديم.

# 25. النزاهة العلمية

قواعد المنع الصريحة:

1.  اختلاق مراجع.
2.  اختلاق DOI.
3.  اختلاق بيانات.
4.  تعديل البيانات لتحقيق دلالة.
5.  كتابة نتائج قبل التحليل.
6.  إخفاء التعارضات أو التمويل.
7.  التقديم المتزامن غير المسموح للمخطوطة نفسها.
8.  إضافة مؤلف بلا مساهمة.
9.  إزالة مؤلف مستحق دون توثيق.
10. إعادة نشر النتائج نفسها دون إفصاح.
11. تجزئة غير مبررة للبيانات.
12. استخدام نصوص محمية دون حق.
13. اعتبار الاستشهاد دعمًا لمجرد وجوده دون قراءة ما يدعمه.
14. تجاوز سياسة AI الخاصة بالمجلة.

# 26. الهوية والواجهة

## 26.1 الهوية المبدئية

**ATHERA \| أثيرا** — اسم تجاري مبدئي قابل للتحقق القانوني والعلامة التجارية لاحقًا.

## 26.2 الشخصية البصرية

- Premium Academic Technology.
- علمية، موثوقة، حديثة.
- ليست طبية أو مدرسية.
- لا تستخدم Brain icon تقليديًا كشعار رئيس.
- Visual motif: Golden Thread + Knowledge Nodes + Research Path.

## 26.3 الألوان المقترحة

- Midnight Navy.
- Teal.
- Warm Gold.
- Soft Ivory.
- Cool Gray.

## 26.4 اللغات

- Arabic-first RTL.
- English LTR.
- تبديل سلس بين اللغتين.

# 27. الشاشات المطلوبة

## 27.1 المستخدم الفردي

1.  Login / Onboarding.
2.  Home Dashboard.
3.  Ask Research Brain.
4.  Academic Profile.
5.  Promotion Center.
6.  Research Portfolio.
7.  Research Project Workspace.
8.  Opportunities Explorer.
9.  Literature Library.
10. Evidence Ledger.
11. Golden Thread Lab.
12. Methodology Lab.
13. Ethics & Data.
14. Analysis Workspace.
15. Manuscript Studio.
16. Journal Matcher.
17. Virtual Peer Review.
18. Submission Center.
19. Reviewer Response Workspace.
20. Thesis Library.
21. Thesis Publication Map.
22. Authorship & Rights.
23. Notifications / Decisions.
24. Settings / Integrations.

## 27.2 شاشة الباحث الرئيسية

تعرض:

- Promotion Readiness.
- Research Units.
- Sole-author units.
- Strict WoS requirement.
- Active projects.
- Decisions waiting for approval.
- Research Brain prompt box.
- Verified Memory summary.
- Risks and alerts.

## 27.3 الشاشات المؤسسية مستقبلًا

- College Research Dashboard.
- Faculty Productivity.
- Thesis-to-Publication Dashboard.
- Promotion Pipeline.
- Research Integrity Alerts.
- Journals & Policy Registry.

# 28. الصلاحيات RBAC

الأدوار الأولية:

- Researcher.
- Co-author.
- Supervisor.
- Student.
- Internal Reviewer.
- Research Admin.
- College Admin.
- Institution Admin.
- System Admin.

كل Object يجب أن يدعم:

- Owner.
- Viewer.
- Editor.
- Approver.
- Restricted fields.

# 29. نموذج البيانات الأساسي

## 29.1 الجداول الأساسية

>     users
>     organizations
>     tenants
>     memberships
>     researcher_profiles
>     researcher_skills
>     researcher_memories
>
>     promotion_policies
>     promotion_policy_versions
>     promotion_rules
>     promotion_cases
>     promotion_evidence
>
>     research_programs
>     research_projects
>     project_members
>     project_decisions
>     research_questions
>     objectives
>     hypotheses
>     theories
>     constructs
>     variables
>     methods
>     instruments
>     ethics_approvals
>
>     sources
>     source_versions
>     authors
>     journals
>     journal_indexing_records
>     claims
>     evidence_excerpts
>     claim_evidence_links
>
>     files
>     datasets
>     dataset_versions
>     data_dictionaries
>     analysis_plans
>     analysis_runs
>     analysis_outputs
>
>     manuscripts
>     manuscript_sections
>     manuscript_versions
>     comments
>     approvals
>
>     journal_profiles
>     journal_policy_checks
>     journal_matches
>     submissions
>     submission_files
>     review_rounds
>     reviewer_comments
>     reviewer_responses
>
>     theses
>     thesis_owners
>     thesis_supervisors
>     thesis_sections
>     thesis_results
>     publication_opportunities
>     opportunity_overlap_scores
>     authorship_agreements
>     credit_roles
>
>     agent_runs
>     tool_runs
>     provenance_events
>     audit_events
>     integrity_alerts
>     notifications

## 29.2 حقول Provenance إلزامية

لكل سجل معرفي مهم:

- source_type.
- source_id.
- source_locator.
- created_by.
- created_at.
- verification_status.
- verified_by.
- verified_at.
- model_run_id إذا كان مولدًا.

# 30. Knowledge Graph

## 30.1 العقد

>     Researcher
>     Institution
>     Policy
>     Rule
>     ResearchProgram
>     ResearchProject
>     Question
>     Objective
>     Hypothesis
>     Theory
>     Construct
>     Variable
>     Method
>     Instrument
>     Dataset
>     AnalysisRun
>     Result
>     Claim
>     Evidence
>     Journal
>     Publication
>     Thesis
>     PublicationOpportunity
>     Author
>     Submission
>     ReviewerComment
>     Approval

## 30.2 العلاقات

>     RESEARCHER_HAS_EXPERTISE
>     POLICY_HAS_RULE
>     PROJECT_BELONGS_TO_PROGRAM
>     QUESTION_MAPS_TO_OBJECTIVE
>     THEORY_EXPLAINS_HYPOTHESIS
>     VARIABLE_OPERATIONALIZES_CONSTRUCT
>     INSTRUMENT_MEASURES_VARIABLE
>     DATASET_SUPPORTS_ANALYSIS
>     ANALYSIS_PRODUCES_RESULT
>     RESULT_SUPPORTS_CLAIM
>     EVIDENCE_SUPPORTS_CLAIM
>     EVIDENCE_CONTRADICTS_CLAIM
>     MANUSCRIPT_TARGETS_JOURNAL
>     JOURNAL_HAS_INDEXING_RECORD
>     PUBLICATION_COUNTS_FOR_RULE
>     THESIS_GENERATES_OPPORTUNITY
>     OPPORTUNITY_OVERLAPS_WITH
>     AUTHOR_HAS_CREDIT_ROLE
>     DECISION_APPROVED_BY

في الإصدار الأول يمكن تنفيذ الرسم في PostgreSQL بدل Neo4j، مع Nodes/Edges وجداول domain الطبيعية.

# 31. المعمارية التقنية

## 31.1 Frontend

- Next.js.
- TypeScript.
- React.
- RTL/LTR.
- Responsive Web.
- Component library داخلية.

## 31.2 Backend

- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy.

## 31.3 Data

- PostgreSQL.
- pgvector.
- S3-compatible Object Storage.
- Redis للتخزين المؤقت والمهام القصيرة.

## 31.4 Workflow

- Temporal أو محرك Durable Workflow مماثل.
- Long-running workflows.
- Human approval pauses.
- Retry/Resume.

## 31.5 AI

- Model Provider Gateway.
- OpenAI كأول Adapter.
- قابلية إضافة مزود آخر أو نموذج محلي.
- Structured Outputs.
- Tool Calling.
- Agent Tracing.

## 31.6 Analysis

- Isolated Docker containers.
- Python Worker.
- R Worker.
- Resource quotas.
- No outbound internet by default أثناء تشغيل بيانات حساسة.

# 32. Model Provider Gateway

واجهة داخلية موحدة:

>     class ModelProvider:
>         generate_structured(...)
>         embed(...)
>         stream(...)
>         tool_call(...)

المتطلبات:

- عدم نشر Vendor-specific payloads في Domain Layer.
- Logging للتكلفة والـlatency.
- اختيار نموذج حسب المهمة.
- إمكانية إيقاف إرسال البيانات الحساسة لمزود خارجي.

# 33. البحث والاسترجاع RAG

## 33.1 الفهرسة

- Chunk by semantic structure وليس حجمًا ثابتًا فقط.
- حفظ Page/Section/Paragraph locators.
- Embeddings.
- Hybrid Retrieval: vector + keyword + metadata filters.

## 33.2 أولوية المصادر

1.  Verified project sources.
2.  User-approved uploads.
3.  Official scholarly metadata.
4.  Licensed databases.
5.  Open web only for tasks requiring current verification.

## 33.3 Prompt Injection Defense

كل نص وارد من PDF/Web/API يعتبر **Untrusted Content** ولا يسمح له بتغيير System/Agent instructions أو استدعاء أداة من داخل المحتوى.

# 34. التكاملات

## 34.1 المرحلة الأولى

- OpenAlex.
- Crossref.
- ORCID.
- DOAJ.
- ROR.
- File Upload.

## 34.2 المرحلة الثانية

- Web of Science API / institutional access.
- Scopus APIs / licensed data.
- Zotero.
- Crossref Retraction/updates.
- Qualtrics/REDCap عند الحاجة.

## 34.3 المرحلة المؤسسية

- SSO / SAML / OIDC.
- University repositories.
- Institutional research systems.
- Library proxy/licensing integrations.

# 35. API الأولية

## 35.1 Profile

>     POST /api/v1/profile/import
>     GET  /api/v1/profile
>     PATCH /api/v1/profile
>     POST /api/v1/profile/facts/{id}/approve

## 35.2 Promotion

>     POST /api/v1/promotion/policies/import
>     GET  /api/v1/promotion/case
>     POST /api/v1/promotion/calculate
>     POST /api/v1/promotion/scenarios

## 35.3 Projects

>     POST /api/v1/projects
>     GET  /api/v1/projects/{id}
>     POST /api/v1/projects/{id}/decisions
>     POST /api/v1/projects/{id}/approvals

## 35.4 Evidence

>     POST /api/v1/sources/search
>     POST /api/v1/sources/import
>     POST /api/v1/claims
>     POST /api/v1/claims/{id}/evidence
>     GET  /api/v1/projects/{id}/evidence-ledger

## 35.5 Analysis

>     POST /api/v1/datasets
>     POST /api/v1/analysis/plans
>     POST /api/v1/analysis/runs
>     GET  /api/v1/analysis/runs/{id}

## 35.6 Journals

>     POST /api/v1/journals/match
>     GET  /api/v1/journals/{id}
>     POST /api/v1/journals/{id}/verify

## 35.7 Theses

>     POST /api/v1/theses
>     POST /api/v1/theses/{id}/parse
>     POST /api/v1/theses/{id}/mine-opportunities
>     GET  /api/v1/theses/{id}/publication-map
>     POST /api/v1/opportunities/{id}/convert-to-project
>     POST /api/v1/opportunities/{id}/authorship-approval

# 36. الأمن والخصوصية

## 36.1 مبادئ

- Encryption in transit.
- Encryption at rest.
- MFA.
- RBAC.
- Tenant isolation.
- Audit logs.
- Key rotation.
- Secret manager.
- No credentials in source code.

## 36.2 PDPL readiness

يجب تصميم النظام بما يدعم:

- Purpose limitation.
- Data minimization.
- Consent/Legal basis records.
- Data export.
- Data deletion.
- Retention schedules.
- Cross-border transfer controls.
- Access logging.

## 36.3 بيانات المشاركين

- PII vault منفصل عند الحاجة.
- إرسال De-identified text للنماذج قدر الإمكان.
- سياسات تمنع إدخال البيانات الحساسة إلى مزود خارجي عند اختيار مؤسسة لذلك.

# 37. السجل والتدقيق Auditability

كل حدث مهم يسجل:

- من قام بالفعل.
- متى.
- ما العنصر السابق.
- ما العنصر الجديد.
- سبب التغيير.
- Model/Agent run.
- Source references.
- Approval.

يجب أن يكون سجل التدقيق غير قابل للتعديل من المستخدم العادي.

# 38. المتطلبات غير الوظيفية

## 38.1 الأداء

- فتح Dashboard: P95 \< 2.5s في الظروف الاعتيادية.
- عمليات CRUD: P95 \< 500ms دون عمليات AI.
- AI long-running tasks: asynchronous with progress states.
- Search results الأولية: \< 5s عند استخدام الخدمات الخارجية المتاحة.

## 38.2 الاعتمادية

- Durable workflows.
- Idempotent tool operations.
- Retry policies.
- Backups.
- Restore testing.

## 38.3 القابلية للتوسع

- Multi-tenant from architecture level.
- Stateless API nodes.
- Worker queues.
- Horizontal scaling.

## 38.4 إمكانية الاستخدام

- Arabic RTL as first-class, not mirrored afterthought.
- Keyboard accessibility.
- WCAG-aware components.
- Clear provenance UI.

## 38.5 الرصد

- Application logs.
- Agent traces.
- Tool traces.
- Cost monitoring.
- Latency monitoring.
- Error aggregation.

## 38.6 المكدس التقني المعتمد (Approved Technology Stack)

يعتمد الإصدار الأول من ATHERA على مكدس تقني مزدوج: TypeScript/Next.js لتجربة الويب، وPython/FastAPI للخدمات الخلفية والعقل البحثي والتحليل. هذا القرار معماري مقصود لأن واجهة المنتج تتطلب تجربة SaaS تفاعلية عالية الجودة، بينما تعتمد طبقة الذكاء البحثي على منظومة Python الأوسع في الذكاء الاصطناعي ومعالجة الوثائق والتحليل الإحصائي.

## 38.6.1 Frontend

Next.js 16+ مع TypeScript.

دعم عربي RTL وإنجليزي LTR من التصميم الأساسي.

واجهة Responsive Web مع Design System موحد.

عدم تخزين أسرار أو مفاتيح نماذج الذكاء الاصطناعي في المتصفح.

يحظر على الواجهة الاتصال المباشر بمزود النموذج؛ جميع طلبات AI تمر عبر Backend/API Gateway.

## 38.6.2 Backend & Core API

Python 3.12+.

FastAPI لبناء REST/async APIs.

Pydantic للعقود والتحقق من Structured Outputs.

SQLAlchemy + Alembic لإدارة البيانات والترحيلات.

خدمات Stateless قدر الإمكان مع فصل العمال للمهام الطويلة.

## 38.6.3 AI Research Brain

Python هو اللغة الأساسية لـ Research Brain Orchestrator والأجنتات والأدوات.

استخدام OpenAI Responses API / Agents SDK عبر ModelProvider abstraction، مع منع الارتباط الصلب بمزود واحد.

كل استدعاء نموذج يمر عبر طبقة سياسات تتحقق من الصلاحيات، مصادر الاسترجاع، الحواجز العلمية، وسجل التدقيق.

لا يعتمد العقل على ذاكرة المحادثة وحدها؛ الذاكرة الموثقة والحقائق والقرارات تحفظ في طبقة البيانات المنظمة.

## 38.6.4 Data & Retrieval

PostgreSQL قاعدة البيانات الأساسية.

pgvector للبحث الدلالي وRAG.

S3-compatible Object Storage للرسائل، الأوراق، البيانات، والمخرجات.

Redis اختياري للتخزين المؤقت، الأقفال، وحالات المهام القصيرة.

## 38.6.5 Scientific Analysis

Python: pandas, NumPy, SciPy, statsmodels, scikit-learn وأدوات معالجة البيانات المناسبة.

R Workers للدراسات التي تتطلب حزمًا إحصائية أو منهجية متخصصة.

تصدير واستيراد ملفات متوافقة مع SPSS عند الإمكان.

تجهيز بيانات ومخرجات متوافقة مع SmartPLS workflows.

Codebooks وملفات تبادل متوافقة مع NVivo workflows وفق الصيغ والتراخيص المتاحة.

تشغيل التحليل داخل حاويات معزولة، مع حفظ الكود، الإصدارات، المدخلات، والمخرجات لإعادة الإنتاج.

## 38.6.6 Workflow & Background Processing

Temporal هو الخيار المفضل لسير العمل طويل الأجل، بوابات الاعتماد، retries، وانتظار الأحداث البشرية.

يمكن استخدام Celery/worker queue للمهام القصيرة إذا أثبت Technical Discovery الحاجة، دون استبدال Durable Workflows الأساسية.

## 38.6.7 Deployment & DevOps

Docker من أول Sprint لجميع الخدمات.

Monorepo يضم Web، API، Workers، Shared Schemas، Infrastructure.

CI/CD مع اختبارات Unit وIntegration وSecurity scans.

Kubernetes يؤجل لما بعد إثبات الحاجة للتوسع؛ لا يكون شرطًا لـMVP.

Secrets Manager وإدارة مفاتيح منفصلة لكل بيئة.

## 38.6.8 قاعدة معمارية ملزمة

> Frontend لا يتصل مباشرة بأي LLM أو خدمة ذكاء اصطناعي. المسار الإلزامي هو: UI → API Gateway/Backend → Research Brain/Policy Layer → Model Provider/Tools → Audit & Provenance → Response. الهدف هو ضمان الصلاحيات، الذاكرة الموثقة، حماية البيانات، النزاهة العلمية، ضبط التكلفة، وإمكانية تغيير مزود النموذج مستقبلًا.

## 38.6.9 المكدس المرجعي المختصر

    Frontend: Next.js 16+ / TypeScript
    Backend: Python 3.12+ / FastAPI
    AI: Python / OpenAI Responses + Agents via Provider Adapter
    Database: PostgreSQL + pgvector
    Storage: S3-compatible Object Storage
    Workflow: Temporal
    Analysis: Python + R isolated workers
    Cache/Queue: Redis where justified
    Deployment: Docker; Kubernetes later if required

# 39. مؤشرات الجودة والقبول

| **المؤشر**                          | **شرط القبول**                     |
|-------------------------------------|------------------------------------|
| المراجع المختلقة                    | صفر في اختبارات الإنتاج            |
| DOI المختلقة                        | صفر                                |
| النتائج غير المرتبطة بتحليل         | صفر                                |
| Verified Memory بلا مصدر/اعتماد     | صفر                                |
| ادعاءات جوهرية بلا Evidence         | صفر في النسخة النهائية أو وسم صريح |
| Journal index status بلا تاريخ تحقق | صفر عند قرار المجلة                |
| تجاوز Human Gate                    | صفر                                |
| تعديل RAW Dataset                   | غير مسموح                          |
| Submission دون Authorship approval  | غير مسموح                          |
| Thesis paper عالي التداخل دون تحذير | غير مسموح                          |
| Audit coverage للقرارات الجوهرية    | 100%                               |

# 40. مؤشرات نجاح المنتج

## 40.1 الباحث

- نسبة المشروعات التي تصل إلى Ready to Submit.
- زمن الانتقال من فكرة إلى بروتوكول.
- زمن الانتقال من Data Freeze إلى Manuscript Draft.
- نسبة المراجع المتحقق منها.
- عدد الأخطاء المكتشفة قبل التقديم.
- Promotion Readiness progression.

## 40.2 الرسائل

- Thesis-to-Publication Rate.
- عدد الفرص المقبولة بعد فحص التداخل.
- زمن التحويل إلى أول Submission.

## 40.3 المؤسسة

- عدد أعضاء هيئة التدريس على مسار الترقية.
- معدل تقدم المحافظ البحثية.
- جودة منافذ النشر.
- زمن استكمال ملفات الترقية.

# 41. MVP المقترح

## 41.1 MVP-0: Foundation

- Monorepo.
- Auth.
- Tenant model.
- PostgreSQL + pgvector.
- Object storage.
- Audit.
- Model Gateway.

Approved stack: Next.js/TypeScript + Python/FastAPI + PostgreSQL/pgvector + Temporal + Docker.

- Workflow engine.
- Design system.

## 41.2 MVP-1: Research Brain Memory

- File upload.
- PDF/DOCX parsing.
- Fact extraction.
- Source locator.
- Fact approval UI.
- Verified memory.
- Brain chat grounded in verified memory.

## 41.3 MVP-2: Promotion & Portfolio

- Policy import.
- Rule review.
- Promotion calculator.
- Research portfolio.
- Scenario planner.

## 41.4 MVP-3: Evidence & Golden Thread

- OpenAlex/Crossref integration.
- Evidence library.
- Claims ledger.
- Golden Thread lab.
- Protocol builder.

## 41.5 MVP-4: Thesis-to-Papers

- Thesis parser.
- Publication opportunity miner.
- Overlap matrix.
- Authorship gate.
- Convert opportunity to project.

## 41.6 MVP-5: Manuscript & Journals

- Manuscript studio.
- Journal registry.
- Journal matching.
- Peer review simulation.
- Submission package export.

## 41.7 MVP-6: Analysis

- Dataset versioning.
- Python/R sandbox.
- SPSS/SmartPLS/NVivo export helpers.
- Analysis provenance.

# 42. خطة السبرنتات

## Sprint 0 — 2 أسابيع

- Architecture skeleton.
- Monorepo.
- CI/CD.
- Auth/Tenant.
- PostgreSQL/pgvector.
- File storage.
- Audit foundation.

## Sprint 1 — 2 إلى 3 أسابيع

- File ingestion.
- Parser.
- Fact extraction.
- Approval UI.
- Verified memory.

## Sprint 2 — 2 أسابيع

- Research Brain orchestrator.
- Agent registry.
- Tool registry.
- Structured outputs.
- Trace viewer.

## Sprint 3 — 2 إلى 3 أسابيع

- Promotion policy/rules.
- Calculator.
- Research portfolio.
- Dashboard.

## Sprint 4 — 3 أسابيع

- Literature sources.
- Evidence ledger.
- DOI verification.
- Claim linking.

## Sprint 5 — 2 إلى 3 أسابيع

- Golden Thread.
- Methodology workspace.
- Protocol approvals.

## Sprint 6 — 3 أسابيع

- Thesis parser.
- Opportunity miner.
- Overlap/rights/authorship.

## Sprint 7 — 3 أسابيع

- Manuscript editor.
- Journal matching.
- Internal peer review.

## Sprint 8 — 3 إلى 4 أسابيع

- Data/analysis sandbox.
- Export workflows.
- Result provenance.

> التقديرات أولية وتحتاج Technical Discovery قبل الالتزام الزمني النهائي.

# 43. حالات اختبار القبول الحرجة

## TC-01: لا ذاكرة موثقة بلا مصدر

**Given:** نموذج استخرج أن الباحث يستخدم برنامجًا معينًا.  
**When:** لا يوجد نص واضح في الملفات ولم يؤكده المستخدم.  
**Then:** يحفظ كـUnverified ولا يظهر كحقيقة مثبتة.

## TC-02: منع المرجع المختلق

**Given:** المخطوطة تحتاج مرجعًا.  
**When:** لا يوجد مصدر موثق مناسب.  
**Then:** يعرض النظام Evidence Gap ولا يولد مرجعًا.

## TC-03: منع النتيجة الوهمية

**Given:** Dataset غير مرفوع.  
**When:** يطلب المستخدم كتابة النتائج.  
**Then:** يسمح بصياغة قالب فقط ويمنع أرقامًا فعلية.

## TC-04: فهرسة المجلة

**Given:** مجلة كانت مفهرسة سابقًا.  
**When:** يتم اختيارها للبحث الذي يحقق شرط WoS.  
**Then:** يعاد التحقق من Current Coverage وتاريخها قبل اعتماد G10.

## TC-05: رسالة إلى ورقتين متداخلتين

**Given:** Opportunity A وB تستخدمان السؤال والنتائج نفسها بدرجة عالية.  
**When:** يحاول المستخدم تحويلهما إلى مشروعين.  
**Then:** يظهر Overlap Alert ويطلب دمجًا أو تبريرًا واعتمادًا.

## TC-06: حقوق التأليف

**Given:** رسالة طالب أشرف عليها الباحث.  
**When:** لم تُسجل موافقة صاحب الرسالة والمؤلفين.  
**Then:** يمكن تحليل الفرصة داخليًا، لكن لا تنتقل إلى Ready to Submit.

## TC-07: تعديل البيانات

**Given:** RAW dataset uploaded.  
**When:** تبدأ عملية التنظيف.  
**Then:** ينشئ النظام Cleaned Version ولا يعدل الأصل.

## TC-08: بوابة بشرية

**Given:** Agent اختار مجلة.  
**When:** لم يعتمد الباحث الاختيار.  
**Then:** لا تُنشأ Submission Package نهائية لهذه المجلة.

# 44. لوحة الإدارة والباحث

## 44.1 لوحة الباحث

- Progress لا Performance Theater.
- قرارات تحتاج اعتمادًا.
- مخاطر.
- فجوات أدلة.
- حالة المشاريع.
- حالة الترقية.
- آخر عمليات العقل.

## 44.2 لوحة Admin/Research Office مستقبلًا

- الباحثون والمشاريع.
- حالات اللوائح.
- المجلات المستخدمة.
- Thesis conversion pipeline.
- Research integrity alerts.
- Usage/cost.
- System health.

# 45. الأصول التجارية المستقبلية

الميزة التنافسية التراكمية للمنتج ليست النموذج اللغوي، بل:

- Promotion Policy Library.
- Researcher Verified Memory.
- Thesis-to-Publication knowledge.
- Journal history and matching outcomes.
- Evidence graph.
- Research workflow data.
- Decision/review patterns.

هذه الأصول يجب أن تُبنى قانونيًا وبصلاحيات واضحة، مع فصل بيانات العملاء وعدم استخدامها للتدريب العام دون موافقة.

# 46. نموذج الأعمال المستقبلي

## Individual

- اشتراك باحث فردي.
- عدد مشاريع نشطة محدد حسب الخطة.

## Research Pro

- محفظة ترقية كاملة.
- Thesis-to-Papers.
- Journal Intelligence.
- Advanced Analysis.

## Research Team

- مؤلفون مشاركون.
- مراجعة واعتمادات.
- Shared evidence library.

## University / Enterprise

- SSO.
- Private tenant.
- Promotion policies.
- College dashboards.
- Institutional integrations.
- Optional private deployment.

الأسعار لا تحدد في هذه الوثيقة قبل دراسة السوق والتكلفة التشغيلية.

# 47. القرارات المؤجلة قبل الإنتاج

1.  التحقق القانوني من اسم ATHERA والعلامة والنطاقات.
2.  تأكيد أحدث لائحة ترقية سارية للجامعة المرجعية.
3.  تحديد شروط استخدام WoS/Scopus وبيانات JCR/CiteScore تجاريًا.
4.  تحديد سياسة تخزين النصوص الكاملة للناشرين.
5.  تحديد Hosting region للنسخة السعودية.
6.  إعداد Legal Terms للرسائل وحقوق الطلاب والمشرفين.
7.  تحديد مزود محرر المستندات.
8.  تحديد حدود البيانات الحساسة التي يسمح بإرسالها للنماذج الخارجية.
9.  تحديد طريقة دعم ملفات SmartPLS/NVivo الفعلية وفق صيغها وتراخيصها.

# 48. Definition of Done للإصدار الأول التجاري

الإصدار الأول لا يعتبر جاهزًا للإطلاق إلا عندما يستطيع المستخدم تنفيذ السيناريو التالي دون تدخل يدوي من فريق التطوير:

1.  إنشاء حساب عربي.
2.  رفع CV ورسالة سابقة ولائحة ترقية.
3.  مراجعة الحقائق المستخرجة واعتمادها.
4.  رؤية فجوة الترقية.
5.  إنشاء محفظة مشاريع.
6.  اكتشاف فرصة بحث وتثبيت بروتوكولها.

مراقبة الاتجاهات البحثية دوريًا وإنشاء فرص نشر استباقية مع أدلة وحداثة قابلة للتحقق.

7.  جمع أدبيات موثقة وربط الادعاءات بالأدلة.
8.  اجتياز فحص الخيط الذهبي.
9.  رفع رسالة طالب واستخراج فرص أوراق مع Overlap/Authorship controls.
10. تحويل فرصة إلى مشروع.
11. إنشاء مسودة مخطوطة دون مراجع مختلقة.
12. مطابقة المشروع مع مجلات موثوقة مع Timestamp.
13. تشغيل مراجعة داخلية متعددة الأدوار.
14. إخراج Submission Package.
15. الاحتفاظ بسجل تدقيق كامل لكل قرار مهم.

# 49. ترتيب الأولوية النهائي

## Must Have

- AI Research Brain.

Research Trend Intelligence & Proactive Paper Pipeline.

- Verified Memory.
- Promotion Engine.
- Research Portfolio.
- Evidence Ledger.
- Golden Thread.
- Journal Intelligence.
- Thesis-to-Papers.
- Authorship/Rights Gate.
- Audit Trail.
- Arabic RTL.

## Should Have

- Manuscript Studio.
- Virtual Peer Review.
- Python/R analysis.
- SPSS/SmartPLS/NVivo workflows.
- Zotero integration.

## Could Have

- Institutional dashboards.
- Grant management.
- Team benchmarking.
- University-wide publication opportunity mining.

## Won't Have in V1

- Fully autonomous submission/publication without explicit human approval.
- Acceptance guarantees.
- Unlicensed paywalled scraping.
- Custom foundation model training.

# 50. التعليمات المباشرة لفريق التطوير

قبل كتابة أي كود إنتاجي:

1.  تحويل هذه الوثيقة إلى Epics وUser Stories.
2.  بناء Architecture Decision Records (ADRs).

توثيق ADR خاص بالمكدس المعتمد، ومنع أي فريق من استبدال Python/FastAPI أو Next.js/TypeScript في النواة دون قرار معماري معتمد.

3.  تثبيت نموذج الـMulti-tenancy.
4.  تثبيت Security Threat Model.
5.  إعداد Data Classification Matrix.
6.  رسم Sequence Diagrams للمسارات الحرجة.
7.  تصميم قاعدة البيانات التفصيلية.
8.  تعريف OpenAPI contract.
9.  بناء Proof of Concept للذاكرة الموثقة.
10. اختبار Thesis Parser على عدة رسائل حقيقية قبل بناء واجهة كاملة.

أهم قاعدة هندسية:

> لا توجد حقيقة أكاديمية مهمة داخل المحادثة فقط؛ كل حقيقة، مصدر، نتيجة، قرار، مجلة، سياسة، موافقة، وادعاء يجب أن يكون كائنًا منظمًا قابلًا للتتبع والتحقق.

# 51. الذكاء الاستباقي للاتجاهات البحثية وإنتاج الأوراق الجاهزة للنشر

تهدف هذه الوحدة إلى تحويل ATHERA من منصة تستجيب لطلب الباحث إلى نظام بحثي استباقي يراقب البيئة العلمية باستمرار، ويكتشف التحولات النظرية والمنهجية والموضوعية، ويربطها بملف الباحث ومحفظة الترقية والبيانات المتاحة، ثم يقترح فرصًا قابلة للنشر ويقودها - بعد الاعتمادات اللازمة - حتى تصبح مخطوطات جاهزة للتقديم إلى مجلة محددة.

## 51.1 Research Trend Intelligence Engine

مراقبة مستمرة للكلمات المفتاحية، النظريات، المتغيرات، المناهج، المجتمعات البحثية، القطاعات، التقنيات الناشئة، والمجلات ذات الصلة بتخصص الباحث.

استخدام مصادر أكاديمية موثوقة وقابلة للتوثيق مثل OpenAlex وCrossref وDOAJ، مع دعم Web of Science وScopus وفق التراخيص والصلاحيات المتاحة.

اكتشاف Topic Emergence وTopic Acceleration وDeclining Topics وTheory Shifts وMethod Shifts وGeographic Gaps وContradictory Findings وReplication Opportunities وData Opportunities.

إنشاء خط زمني لكل اتجاه يوضح متى بدأ، سرعة نموه، أهم الدراسات، أبرز المؤلفين، المجلات النشطة، والمفاهيم المرتبطة.

تمييز الاتجاه الحقيقي عن الضجيج المؤقت عبر حد أدنى من الأدلة والتكرار والاستمرارية وتنوع المصادر.

تحديث حالة الاتجاهات دوريًا مع Timestamp ومصدر كل إشارة، وعدم الاعتماد على ذاكرة النموذج وحدها.

## 51.2 ملفات المراقبة Watchlists

Watchlist شخصي مرتبط بتخصص الباحث وخطته البحثية الحالية.

Watchlist لكل مشروع بحثي نشط.

Watchlist لكل نظرية أو متغير أو منهج يختاره الباحث.

Watchlist للمجلات المستهدفة وسياساتها وحالة فهرستها والموضوعات التي تنشرها حديثًا.

Watchlist لموضوعات الرسائل التي أشرف عليها الباحث لاكتشاف فرص تحويلها إلى أوراق جديدة أو Extension Papers.

Watchlist تنافسي لمتابعة باحثين أو مجموعات أو مراكز بحثية يحددها المستخدم، دون جمع بيانات شخصية غير لازمة.

## 51.3 Trend Scoring & Opportunity Scoring

يجب أن يخرج النظام بدرجتين منفصلتين: درجة قوة الاتجاه، ودرجة ملاءمة الفرصة للباحث. لا يجوز مساواة الرواج بقابلية النشر.

| المعيار                        | الوزن | سؤال التقييم                                                 |
|--------------------------------|-------|--------------------------------------------------------------|
| Novelty / الجدة                | 20    | هل توجد إضافة واضحة غير مشبعة؟                               |
| Momentum / الزخم               | 15    | هل يتزايد النشر والاستشهاد والاهتمام بالمفهوم؟               |
| Research Gap / الفجوة          | 15    | هل توجد فجوة نظرية أو منهجية أو سياقية قابلة للدفاع؟         |
| Researcher Fit / ملاءمة الباحث | 15    | هل يتقاطع مع خبرة الباحث وخطه العلمي ومهاراته؟               |
| Data Feasibility / البيانات    | 10    | هل توجد بيانات قابلة للحصول أو إعادة الاستخدام بصورة مشروعة؟ |
| Journal Fit / المجلات          | 10    | هل توجد مجلات موثوقة تنشر هذا النوع من الأبحاث؟              |
| Promotion Value / قيمة الترقية | 10    | ما قيمة البحث ضمن محفظة الترقية؟                             |
| Execution Risk / مخاطر التنفيذ | 5     | الوقت والأخلاقيات والعينة والتكلفة والتداخل.                 |

## 51.4 Proactive Research Opportunity Cards

عند اكتشاف اتجاه ذي قيمة، ينشئ النظام بطاقة فرصة لا تبدأ بالكتابة مباشرة. تحتوي البطاقة على:

عنوان مبدئي وسؤال مركزي واضح.

وصف الاتجاه والأدلة التي تثبت أنه مستجد أو متسارع.

الفجوة المقترحة مع مستوى الثقة ومصادرها.

النظرية أو الإطار المفاهيمي المحتمل.

نوع الدراسة والمنهج والأداة والعينة المقترحة.

البيانات المطلوبة وهل هي متاحة أو يجب جمعها.

الجدة مقارنة بأقرب الدراسات الحديثة.

المجلات المحتملة مرتبة حسب الملاءمة والموثوقية ومتطلبات الترقية.

درجة فرصة النشر، درجة المخاطر، والزمن المتوقع للتنفيذ دون تقديم وعد بالقبول.

التداخل مع أبحاث الباحث الحالية أو الرسائل التي أشرف عليها.

## 51.5 Proactive Paper Pipeline

بعد اعتماد الباحث لبطاقة الفرصة، تُحوّل تلقائيًا إلى مشروع بحثي يمر بمراحل متتابعة. هدف النظام هو الوصول إلى Manuscript Ready for Submission وليس النشر أو الإرسال المستقل دون موافقة بشرية.

P0: اكتشاف الاتجاه وتوثيق الأدلة.

P1: فحص الجدة والتداخل مع الأدبيات الحالية وأعمال الباحث.

P2: اعتماد سؤال البحث والفجوة والمساهمة المتوقعة.

P3: بناء البروتوكول والنظرية والمنهج وخطة البيانات.

P4: الحصول على الأخلاقيات والموافقات عند الحاجة.

P5: جمع البيانات أو استيراد بيانات مشروعة ومتاحة.

P6: قفل خطة التحليل وإغلاق نسخة البيانات.

P7: تشغيل التحليل القابل لإعادة الإنتاج.

P8: بناء النتائج والجداول والأشكال من المخرجات الفعلية.

P9: كتابة المخطوطة من Evidence Ledger والنتائج المعتمدة.

P10: تحديث الأدبيات مرة أخرى قبل التقديم لضمان حداثة الورقة.

P11: مطابقة المجلة وتطبيق Author Guidelines وReporting Guideline.

P12: مراجعة نظرية ومنهجية وإحصائية وتحريرية ونزاهية مستقلة.

P13: إنتاج Submission Package كامل ووضع الحالة Ready for Researcher Approval.

P14: لا يتم أي Submission خارجي إلا بفعل واضح من الباحث أو تفويض مؤسسي صريح قابل للسحب والتدقيق.

## 51.6 تعريف الورقة الجاهزة للنشر

لا تستخدم المنصة عبارة "جاهزة للنشر" بمعنى ضمان القبول. الحالة الرسمية هي Ready for Submission، ولا تمنح إلا بعد تحقق الشروط التالية:

سؤال وفجوة ومساهمة علمية معتمدة ومتسقة.

أدبيات حديثة ومراجع متحققة ولا توجد مراجع مختلقة.

كل ادعاء جوهري مرتبط بدليل أو مصنف بوضوح بوصفه استنتاجًا.

المنهجية والأخلاقيات والعينة والأداة مكتملة بحسب نوع الدراسة.

النتائج مبنية على بيانات وتحليل فعلي قابل للتتبع وإعادة الإنتاج.

الخيط الذهبي مكتمل من المشكلة حتى التوصيات.

لا توجد مؤشرات نشر مكرر أو Salami Slicing غير مبرر.

التأليف والمساهمات والموافقات محسومة.

المجلة المستهدفة موثقة، ملائمة، وحالة فهرستها حديثة.

المخطوطة مطابقة لتعليمات المجلة وقائمة الإبلاغ ذات الصلة.

اجتياز مجلس المحكمين الافتراضي وحل الملاحظات الحرجة.

إنتاج Cover Letter وTitle Page وBlinded Manuscript والجداول والأشكال والإفصاحات المطلوبة.

## 51.7 Daily/Weekly Research Intelligence Brief

ملخص يومي اختياري للمستجدات العاجلة ذات الصلة المباشرة بمشروعات الباحث.

تقرير أسبوعي افتراضي يشرح الاتجاهات الجديدة، أهم الدراسات، الفرص المكتشفة، والتغير في درجات الفرص.

تقرير شهري للمحفظة يوصي بما يجب بدءه أو إيقافه أو إعادة تصميمه بناءً على حركة الأدبيات والمجلات.

تنبيه فوري عند ظهور دراسة منافسة قد تؤثر في جدة مشروع قائم، أو عند تغير حالة فهرسة مجلة مستهدفة.

## 51.8 قواعد الاستقلال والنزاهة

لا ينتج النظام بيانات أو نتائج تجريبية من تلقاء نفسه.

لا يحول مجرد ترند إلى ورقة دون سؤال وفجوة ومساهمة قابلة للدفاع.

لا يسمح بكتابة نتائج كمية أو كيفية قبل وجود بيانات ومخرجات تحليل فعلية.

لا يختار نتائج انتقائيًا لتوافق فرضية مرغوبة، ولا يعيد التحليل بقصد مطاردة الدلالة الإحصائية.

لا يعيد تدوير نصوص أو نتائج من رسالة أو بحث سابق دون الإفصاح والتأكد من مشروعية إعادة الاستخدام.

لا يضمن القبول ولا يعطي نسبة قبول مختلقة.

أي استخدام للأتمتة أو الذكاء الاصطناعي يخضع لسياسة المجلة ومتطلبات الإفصاح وقت التقديم.

## 51.9 متطلبات البيانات الجديدة

research_trends: تعريف الاتجاه، المجال، تاريخ الاكتشاف، مصادر الإثبات، درجة الزخم، حالة الاتجاه.

trend_signals: كل إشارة منفردة من مصدر وتاريخ ووزن وثقة.

research_watchlists: نطاق المراقبة والباحث/المشروع المرتبط وجدول التحديث.

opportunity_cards: السؤال والفجوة والجدة والمنهج والبيانات والمجلات والدرجات والحالة.

opportunity_evidence: علاقة كل فرصة بالدراسات أو الإشارات التي تبررها.

paper_pipeline_runs: المرحلة الحالية، الاعتمادات، المخرجات، الأخطاء وإعادة التشغيل.

competitive_novelty_checks: الدراسات القريبة ودرجات التشابه وقرار الاستمرار/التعديل.

research_intelligence_briefs: التقارير اليومية/الأسبوعية/الشهرية وسجل ما شاهده أو اعتمده المستخدم.

## 51.10 متطلبات الأجنتات الجديدة

Trend Scout Agent: جمع الإشارات ورصد التسارع والانحسار.

Trend Validator Agent: التحقق من أن الاتجاه مدعوم بأكثر من مصدر وليس ضجيجًا عابرًا.

Novelty Agent: مقارنة الفرصة بأقرب الأدبيات واكتشاف التشابه وخطر السبق البحثي.

Opportunity Strategist Agent: ربط الاتجاه بملف الباحث وخطة الترقية والبيانات والمجلات.

Paper Pipeline Manager: إدارة رحلة الفرصة المعتمدة حتى Ready for Submission.

Freshness Auditor Agent: إعادة فحص الأدبيات والمجلة قبل التقديم مباشرة.

## 51.11 معايير القبول التقنية

يمكن للمستخدم إنشاء Watchlist وتحديد التخصص والكلمات المفتاحية والنظريات والمجلات.

يحفظ كل Trend Signal مصدرًا وتاريخًا ولا توجد إشارة يتيمة بلا Provenance.

يمكن للنظام اكتشاف تغير جوهري وإعادة حساب Opportunity Score تلقائيًا.

لا تُحوّل Opportunity Card إلى مشروع إلا بعد اعتماد المستخدم.

كل مرحلة من Paper Pipeline قابلة للإيقاف والاستئناف وإعادة التشغيل دون فقد سجل القرارات.

لا يمكن ضبط مشروع على Ready for Submission إذا فشل أي Integrity Gate أو Reporting Checklist إلزامي.

يُعاد فحص حداثة الأدبيات وحالة المجلة في نافذة زمنية قابلة للضبط قبل إنشاء الحزمة النهائية.

تدعم المنصة تشغيل مراقبة مجدولة في الخلفية دون الحاجة إلى إبقاء جلسة المستخدم مفتوحة.

# 52. الخلاصة

ATHERA يجب أن تُبنى كمنصة **Policy-aware, Evidence-grounded, Human-governed Research Intelligence System**. جوهر التميز ليس كتابة نص أكاديمي بسرعة، بل بناء عقل بحثي شخصي ومؤسسي يتذكر بصورة موثقة، ويحول متطلبات الترقية إلى خطة، ويستخرج القيمة العلمية من الرسائل والبيانات، ويمنع الأخطاء الأخلاقية والمنهجية، ويقود الورقة إلى مجلة مناسبة مع بقاء الباحث صاحب القرار النهائي.

هذه الوثيقة هي Baseline v1.2 ويجب اعتبارها المرجع الوظيفي الأول للمنتج حتى يتم اعتماد نسخ تفصيلية لكل Epic.
