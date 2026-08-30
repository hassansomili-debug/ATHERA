---
project: ATHERA
document_type: sprint_plan
sprint: 0
version: "0.1"
status: approved_in_progress
baseline_ref: athera_claude_v1.2/ATHERA_PRD_SRS_v1.2_CLAUDE.md (v1.2)
language: ar
---

# ATHERA — خطة Sprint 0 المعمارية (Foundation)

> هذه الخطة تتبع **Implementation protocol** في `CLAUDE_START_HERE.md`: تحديد المتطلبات، خطة معمارية، تغييرات Schema/API، آثار أمنية وخصوصية، اختبارات قبول، افتراضات غير محسومة — **قبل** كتابة أي كود إنتاجي.
> **الحالة: معتمدة والتنفيذ جارٍ.** اعتُمدت التوصيات في القسم 6 (schema مشتركة + RLS، مصادقة داخلية خلف `IdentityProvider`، المزود `null`)، وبقي السؤال 3 (Hosting region) مفتوحًا ولا يحجب العمل المحلي.
> **إضافة بطلب المستخدم:** ثنائية اللغة عربي/إنجليزي شرط أساسي في كل طبقة — الواجهة والـAPI والبيانات — لا ترجمة تُضاف لاحقًا. يفرضها اختبار AT-S0-11.

---

## 0. الهدف والحدود

**الهدف:** بناء الأساس الذي لا يمكن إضافته لاحقًا دون إعادة كتابة — العزل بين المستأجرين، الصلاحيات، سجل التدقيق غير القابل للتعديل، الـProvenance، تجريد مزود النموذج، وسير العمل الطويل بالاعتمادات البشرية.

**القاعدة الحاكمة (§50):** لا توجد حقيقة أكاديمية مهمة داخل المحادثة فقط؛ كل حقيقة ومصدر ونتيجة وقرار وموافقة وادعاء يجب أن يكون كائنًا منظمًا قابلًا للتتبع والتحقق. Sprint 0 يبني *الهيكل العظمي* لهذه القاعدة قبل أي منطق بحثي.

**خارج نطاق Sprint 0 صراحةً:** استخراج الحقائق، الذاكرة الموثقة، محرك الترقية، الأدبيات، المخطوطات، مطابقة المجلات، Thesis Parser، محرك التحليل، ورصد الاتجاهات (§51). ووفق تعليمة START HERE: **ممنوع البدء بتوليد المخطوطات قبل اكتمال أساسات الذاكرة الموثقة والأدلة والصلاحيات والتدقيق.**

---

## 1. المتطلبات المُنفَّذة في هذا السبرنت

| المرجع | المتطلب | التغطية في Sprint 0 |
|---|---|---|
| §42 Sprint 0 | Architecture skeleton, Monorepo, CI/CD, Auth/Tenant, PostgreSQL/pgvector, File storage, Audit foundation | كامل |
| §41.1 MVP-0 | Monorepo, Auth, Tenant model, PG+pgvector, Object storage, Audit, Model Gateway, Workflow engine, Design system | كامل |
| §38.6.1–38.6.9 | المكدس التقني المعتمد | كامل (تثبيت الإصدارات + ADR-0001) |
| §38.6.8 | القاعدة المعمارية الملزمة: `UI → API → Brain/Policy → Provider/Tools → Audit → Response` | تنفيذ سلسلة الـmiddleware + اختبار يمنع الالتفاف |
| §28 | RBAC: 9 أدوار + Owner/Viewer/Editor/Approver/Restricted fields لكل Object | كامل |
| §29.1 | الجداول الأساسية | مجموعة فرعية (القسم 3.1) |
| §29.2 | حقول Provenance الإلزامية | كامل — تُفرض على مستوى قاعدة البيانات |
| §31.1–31.4 | Frontend / Backend / Data / Workflow | كامل |
| §32 | Model Provider Gateway | الواجهة + OpenAI Adapter + NullProvider + logging للتكلفة والـlatency |
| §36.1–36.2 | الأمن ومبادئ PDPL | أساسات (القسم 4) |
| §37 | سجل تدقيق غير قابل للتعديل من المستخدم العادي | كامل |
| §38.1–38.5 | الأداء، الاعتمادية، التوسع، الاستخدام، الرصد | Budgets + observability + backup/restore drill |
| §38.4 | Arabic RTL as first-class | Design System ثنائي الاتجاه من اليوم الأول |
| §39 | مؤشرات الجودة (بند «Audit coverage للقرارات الجوهرية 100%») | اختبار آلي |
| §50 | ADRs، نموذج Multi-tenancy، Threat Model، Data Classification Matrix، OpenAPI contract | مُنتَجات هذا السبرنت |

**لا يغطي هذا السبرنت** أي بند من §39 يتعلق بالمراجع أو النتائج أو المجلات — تلك تبدأ من Sprint 1 فصاعدًا.

---

## 2. الخطة المعمارية

### 2.1 هيكل الـMonorepo (§38.6.7)

```
athera/
├─ apps/
│  ├─ web/                 # Next.js 16 + TypeScript — RTL/LTR
│  └─ api/                 # FastAPI (Python 3.12) — الواجهة العامة الوحيدة
├─ services/
│  ├─ worker/              # Temporal workers (Python)
│  └─ analysis/            # هيكل فارغ محجوز لـ Sprint 8 (Python/R معزولان)
├─ packages/
│  ├─ contracts/           # OpenAPI 3.1 كمصدر واحد → أنواع TS + نماذج Pydantic
│  └─ ui/                  # Design System (bidi-first)
├─ infra/
│  ├─ docker/              # Dockerfiles لكل خدمة
│  ├─ compose/             # docker-compose.dev.yml
│  └─ db/                  # Alembic migrations + سياسات RLS + أدوار DB
├─ docs/
│  ├─ adr/                 # Architecture Decision Records
│  ├─ threat-model.md
│  └─ data-classification.md
└─ .github/workflows/      # CI/CD
```

**إدارة الحزم:** pnpm workspaces لـ TypeScript، وuv لـ Python، وMakefile موحّد (`make dev`, `make test`, `make migrate`).
**لغة العقود:** OpenAPI 3.1 في `packages/contracts` هو المصدر الوحيد؛ يُولَّد منه عميل TypeScript ونماذج Pydantic. أي تعارض بين الكود والعقد يكسر الـCI.

### 2.2 الخدمات في بيئة التطوير (Docker من اليوم الأول)

| الخدمة | الصورة/التقنية | الدور |
|---|---|---|
| `postgres` | `pgvector/pgvector:pg16` | قاعدة البيانات + الاسترجاع الدلالي لاحقًا |
| `minio` | MinIO | S3-compatible object storage محليًا |
| `redis` | Redis 7 | cache، أقفال، حالات مهام قصيرة (§38.6.4 — اختياري لكن يُثبَّت مبكرًا) |
| `temporal` + `temporal-ui` | Temporal | Durable workflows وبوابات الاعتماد البشري |
| `api` | FastAPI | الواجهة العامة |
| `worker` | Temporal Python SDK | تنفيذ الـworkflows والـactivities |
| `web` | Next.js | واجهة المستخدم |

### 2.3 المسار الإلزامي للطلب (§38.6.8)

```
Browser (Next.js)
   │  لا يحمل أي مفتاح مزود نموذج — CSP يمنع الاتصال بنطاقات المزودين
   ▼
API Gateway (FastAPI)
   ├─ 1. Authentication            → هوية المستخدم
   ├─ 2. Tenant Resolution         → SET LOCAL app.tenant_id (يفعّل RLS)
   ├─ 3. RBAC / Object Permissions → §28
   ├─ 4. Policy Hook               → نقطة تعليق فارغة في Sprint 0، تملؤها Policy Engine لاحقًا
   ├─ 5. Handler / Workflow Start
   ├─ 6. Model Provider Gateway    → §32 (لا يُستدعى من الـdomain مباشرة)
   ├─ 7. Provenance + Audit Write  → §29.2 + §37
   └─ 8. Response
```

**فرض القاعدة تقنيًا، لا بالتوثيق فقط:**
- `import-linter` يمنع أي استيراد لحزمة مزود نموذج خارج `api/providers/`.
- اختبار معماري يفشل إذا استورد `domain/` أو `apps/web/` أي SDK مزود.
- CSP في الـweb تحظر `connect-src` نحو نطاقات المزودين.

### 2.4 نموذج تعدد المستأجرين (تفصيله في ADR-0002)

**التوصية:** قاعدة بيانات وschema مشتركة + عمود `tenant_id` على **كل** جدول + **PostgreSQL Row-Level Security** مفعّلة إجباريًا (`FORCE ROW LEVEL SECURITY`)، مع دور DB للتطبيق لا يملك `BYPASSRLS`.

- كل طلب يفتح transaction ويضبط `SET LOCAL app.tenant_id = '<uuid>'` قبل أي استعلام.
- خطأ برمجي (نسيان فلتر `WHERE tenant_id`) لا يسرّب بيانات — قاعدة البيانات تمنعه.
- مسار الترقية لعملاء Enterprise (§46): قاعدة بيانات مستقلة لكل مستأجر دون تغيير كود التطبيق.
- ملفات Object Storage: بادئة مسار `tenants/{tenant_id}/...` + سياسة bucket تمنع التجاوز.

### 2.5 المصادقة والصلاحيات

- **المصادقة:** بريد/كلمة مرور بـ Argon2id، جلسات JWT قصيرة العمر + refresh token دوّار مخزّن في قاعدة البيانات وقابل للإبطال، **MFA (TOTP) إلزامي للأدوار الإدارية** (§36.1).
- **تجريد الهوية:** واجهة `IdentityProvider` منذ اليوم الأول ليضاف SSO/SAML/OIDC في المرحلة المؤسسية (§34.3) دون إعادة كتابة.
- **RBAC:** الأدوار التسعة في §28 كبيانات لا كثوابت في الكود، وطبقة ثانية على مستوى الكائن: `Owner / Viewer / Editor / Approver / Restricted fields`.
- **فصل حاسم:** صلاحية `Approver` منفصلة عن `Editor` — من يحرّر لا يعتمد تلقائيًا (شرط سلامة بوابات §9).

### 2.6 سجل التدقيق والـProvenance (§37 + §29.2)

- `audit_events` جدول **append-only**: يُنزع `UPDATE` و`DELETE` من دور التطبيق على مستوى صلاحيات PostgreSQL، ويمنع trigger أي تعديل.
- **سلسلة تجزئة (hash chain):** كل سجل يحمل `prev_hash` و`hash`؛ مهمة تحقق دورية تكشف أي عبث حتى من مسار إداري.
- كل حدث يسجل (§37): الفاعل، الوقت، الحالة السابقة، الحالة الجديدة، سبب التغيير، `agent_run_id`/`model_run_id`، المصادر، الاعتماد.
- `provenance_events` منفصل عن التدقيق: التدقيق يجيب «من فعل ماذا»، والـProvenance يجيب «من أين جاءت هذه المعلومة».
- الحقول التسعة في §29.2 (`source_type, source_id, source_locator, created_by, created_at, verification_status, verified_by, verified_at, model_run_id`) تُفرض عبر **قيد قاعدة بيانات** على الجداول المعرفية، لا عبر انضباط المطورين.

### 2.7 Model Provider Gateway (§32) — بلا استدعاءات إنتاجية بعد

الواجهة الموحدة: `generate_structured` · `embed` · `stream` · `tool_call`.
Sprint 0 يسلّم: الواجهة + `OpenAIAdapter` + `NullProvider` للاختبارات + تسجيل التكلفة والـlatency في `model_runs` + مفتاح إيقاف إرسال البيانات الحساسة لمزود خارجي (§32، §36.3). **لا يُعرَض أي endpoint عام للنموذج في هذا السبرنت** — فقط smoke test خلف علم بيئة.

### 2.8 Temporal — إثبات بوابة الاعتماد البشري

Sprint 0 يبني workflow واحدًا تجريبيًا يثبت السلوك الذي تقوم عليه بوابات §9 كلها:
يبدأ → يتوقف بانتظار `approval` signal → يستأنف بعد الاعتماد → **ينجو من إعادة تشغيل الـworker** → كل انتقال حالة يُكتب في `audit_events`. إن لم يثبت هذا في Sprint 0، تنهار بوابات G0–G12 لاحقًا.

### 2.9 الواجهة والـDesign System

Next.js 16 App Router + TypeScript. **العربية RTL ليست انعكاسًا لاحقًا** (§38.4): الرموز المنطقية (`inline-start/end`) بدل `left/right`، اختبار لقطات في الاتجاهين، وتبديل لغة يحفظ التفضيل. Sprint 0 يسلّم: الهيكل، التوكينات اللونية (§26.3 — Midnight Navy / Teal / Warm Gold / Soft Ivory / Cool Gray)، وشاشات Login + Shell فارغ.

### 2.10 CI/CD والرصد

- CI: lint، type-check، اختبارات وحدة وتكامل، اختبارات معمارية، **secret scanning**، SAST، فحص تبعيات، بناء صور Docker.
- الرصد (§38.5): logs منظمة بـ `request_id`/`tenant_id`، OpenTelemetry traces، مقاييس زمن الاستجابة مقابل ميزانيات §38.1 (`P95 < 500ms` لعمليات CRUD)، تجميع الأخطاء، ورصد تكلفة النماذج جاهز للربط.

---

## 3. تغييرات الـSchema والـAPI

### 3.1 جداول Sprint 0 (مجموعة فرعية من §29.1)

**الهوية والمستأجرون:** `tenants` · `organizations` · `users` · `memberships` · `roles` · `permissions` · `role_permissions` · `object_grants` · `refresh_tokens` · `mfa_factors`
**الملفات:** `files` (مفاتيح Object Storage، checksum، حجم، نوع، تصنيف حساسية، حقول §29.2)
**التدقيق والأثر:** `audit_events` (append-only + hash chain) · `provenance_events` · `agent_runs` · `tool_runs` · `model_runs` · `approvals` · `integrity_alerts` · `notifications`

**إضافتان مقترحتان خارج قائمة §29.1 — تُسجَّلان صراحةً بدل تمريرهما صامتًا:**
1. `model_runs` — تستلزمها §29.2 التي تشير إلى `model_run_id` دون تعريف جدول له.
2. `object_grants` — تستلزمها §28 (Owner/Viewer/Editor/Approver لكل Object) وليست قابلة للتمثيل بالأدوار العامة وحدها.

**قواعد مفروضة على مستوى قاعدة البيانات:**
- `tenant_id UUID NOT NULL` + RLS على كل جدول.
- UUID (v7) لكل مفتاح أساسي.
- `TIMESTAMPTZ` حصرًا (UTC) — ولا يُخزَّن تاريخ سياسة أو تحقق بلا منطقة زمنية.
- `CREATE EXTENSION vector;` في أول migration مع اختبار عكسية الترحيل.
- كل الترحيلات عبر Alembic، ولا تعديل يدوي على قاعدة البيانات.

### 3.2 نقاط الـAPI في Sprint 0

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout
POST   /api/v1/auth/mfa/enroll
POST   /api/v1/auth/mfa/verify
GET    /api/v1/me

POST   /api/v1/tenants
GET    /api/v1/tenants/{id}
POST   /api/v1/tenants/{id}/members
PATCH  /api/v1/tenants/{id}/members/{member_id}

POST   /api/v1/files                  # يبدأ رفعًا موقّعًا (presigned)
POST   /api/v1/files/{id}/complete    # يثبّت الـchecksum والحقول والـprovenance
GET    /api/v1/files/{id}
GET    /api/v1/files/{id}/download    # رابط قصير الأجل + تسجيل كل تنزيل

GET    /api/v1/audit/events           # مقيّد بالمستأجر وبدور إداري، للقراءة فقط

GET    /healthz
GET    /readyz
```

**ملاحظة تعاقدية:** لا شيء من §35 (Profile / Promotion / Projects / Evidence / Analysis / Journals / Theses) يُنفَّذ الآن؛ تُحجز مساراتها في OpenAPI كـ`stub` موثّق فقط، لتثبيت الشكل التعاقدي مبكرًا دون ادعاء تنفيذ.

---

## 4. الآثار الأمنية والخصوصية

| المجال | القرار في Sprint 0 | المرجع |
|---|---|---|
| العزل بين المستأجرين | RLS إجبارية + دور DB بلا `BYPASSRLS` + بادئة مسار في التخزين | §36.1 |
| التشفير | TLS أثناء النقل؛ تشفير عند التخزين للقرص والـobject storage (SSE) | §36.1 |
| الأسرار | Secrets Manager لكل بيئة، لا مفاتيح في المستودع، فحص أسرار يكسر الـCI | §36.1 |
| MFA | إلزامي للأدوار الإدارية، اختياري ثم إلزامي لاحقًا للباحث | §36.1 |
| سجل الوصول | كل قراءة لملف أو بيانات مشارك تُسجَّل | §36.2 |
| تقليل البيانات | Sprint 0 لا يجمع بيانات مشاركين إطلاقًا؛ PII vault يُصمَّم في Sprint المخصص للأخلاقيات | §36.3 |
| تصنيف البيانات | مصفوفة C0 عام → C4 بيانات مشاركين، تحدد التشفير والاحتفاظ وحق الإرسال لنموذج خارجي | §50 |
| PDPL | حقول الأساس النظامي والاحتفاظ والحذف والتصدير تُصمَّم الآن حتى لو لم تُفعَّل واجهاتها | §36.2 |
| المحتوى غير الموثوق | كل ملف مرفوع يُوسم `untrusted` منذ لحظة الرفع — تمهيدًا لدفاع حقن الأوامر (§33.3) | §33.3 |
| رفع الملفات | حد حجم، تحقق نوع بالمحتوى لا بالامتداد، عزل التخزين، روابط موقّعة قصيرة | — |
| منع الالتفاف المعماري | اختبار يفشل البناء إذا اتصلت الواجهة أو الـdomain بمزود نموذج | §38.6.8 |
| سطح المخاطر المؤجل | Threat Model كامل (STRIDE) يُنتَج داخل هذا السبرنت كوثيقة مستقلة | §50 |

**مخاطرة معلنة:** سجل التدقيق داخل نفس قاعدة البيانات يبقى عرضة لمن يملك صلاحية DBA. سلسلة التجزئة تكشف العبث لكنها لا تمنعه. النسخ إلى مخزن WORM خارجي (S3 Object Lock) مقترح كقرار مستقل — انظر السؤال المفتوح رقم 6.

---

## 5. اختبارات القبول لـ Sprint 0

| المعرّف | الاختبار | يفشل السبرنت إذا |
|---|---|---|
| AT-S0-01 | مستخدم من المستأجر A يطلب سجلًا من B — بما في ذلك تزوير `tenant_id` في الطلب | عاد أي صف |
| AT-S0-02 | محاولة `UPDATE`/`DELETE` على `audit_events` بدور التطبيق | نجحت العملية |
| AT-S0-03 | مهمة التحقق من سلسلة التجزئة بعد تعديل صف يدويًا | لم تُكتشف |
| AT-S0-04 | كل طلب معدِّل للحالة ينتج حدث تدقيق بالفاعل والوقت والحالة قبل/بعد والسبب | وُجد مسار معدِّل بلا حدث (تغطية < 100% — §39) |
| AT-S0-05 | مصفوفة RBAC: 9 أدوار × الصلاحيات، مع إثبات أن `Editor` لا يستطيع الاعتماد | استطاع محرّر اعتماد كائن |
| AT-S0-06 | رفع ملف → تخزين → صف بحقول §29.2 كاملة → تنزيل مسجَّل ومقيَّد بالصلاحية | نقص أي حقل provenance أو مرّ تنزيل بلا تسجيل |
| AT-S0-07 | workflow يتوقف عند الاعتماد، يُعاد تشغيل الـworker، ثم يستأنف بعد الإشارة | فقد الحالة أو تجاوز الانتظار |
| AT-S0-08 | تبديل المزود إلى `NullProvider` وتشغيل كل الاختبارات | فشل شيء بسبب ارتباط بمزود بعينه |
| AT-S0-09 | فحص حزمة الواجهة: لا SDK مزود ولا مفتاح؛ CSP تحظر نطاقات المزودين | وُجد أي منهما |
| AT-S0-10 | إدخال سر في commit تجريبي | لم يكسر الـCI |
| AT-S0-11 | التطبيق يعمل ويُقرأ صحيحًا في `ar/RTL` و`en/LTR` مع حفظ التفضيل | انكسر التخطيط في أحد الاتجاهين |
| AT-S0-12 | تمرين نسخ احتياطي واستعادة فعلي موثّق مرة واحدة | لم يُنفَّذ (§38.2) |
| AT-S0-13 | `CREATE EXTENSION vector` + ترحيل عكسي نظيف | تعذّر التراجع |

---

## 6. الافتراضات والأسئلة المفتوحة — **مطلوب حسمها قبل التنفيذ**

| # | السؤال | توصيتي | الأثر إن تأخر |
|---|---|---|---|
| 1 | نموذج العزل: schema مشتركة + RLS، أم قاعدة بيانات لكل مستأجر؟ | **مشتركة + RLS** مع مسار ترقية لـEnterprise (ADR-0002) | يعيد تشكيل كل جدول وكل استعلام |
| 2 | المصادقة: بناء داخلي أم Keycloak؟ | **بناء داخلي بسيط خلف واجهة `IdentityProvider`** — Keycloak يضيف عبء تشغيل قبل وجود عميل مؤسسي | يؤخر Auth أسبوعًا إن تغيّر لاحقًا |
| 3 | مزوّد الاستضافة و**Hosting region** (§47.5) | لا توصية بلا معطى قانوني — يحدد KMS والـobject storage وTemporal Cloud | يوقف قرارات التشفير وPDPL |
| 4 | Temporal: مستضاف ذاتيًا أم Temporal Cloud في الإنتاج؟ | Docker محليًا الآن، والقرار الإنتاجي مؤجل بلا كلفة | لا شيء الآن |
| 5 | هل يُستخدم مفتاح OpenAI فعلي في Sprint 0؟ | **لا** — `NullProvider` + smoke test خلف علم بيئة | لا شيء |
| 6 | هل يُنسخ سجل التدقيق إلى مخزن WORM خارجي؟ | نعم مبدئيًا، لكنه قرار كلفة وامتثال | يصعب إضافته بأثر رجعي على سجل قائم |
| 7 | حدود البيانات الحساسة المسموح إرسالها لنموذج خارجي (§47.8) | تصميم المفتاح الآن، وضبط القيمة الافتراضية على **الأشد تقييدًا** | يُبنى منطق يصعب تقييده لاحقًا |
| 8 | تثبيت إصدارات دقيقة: Next.js 16.x، Python 3.12.x، PG 16 + pgvector | تثبيت كامل في Sprint 0 وتوثيقه في ADR-0001 | انحراف بيئات |

**افتراضات أعمل بها ما لم يُعترض عليها:** pnpm + uv كمديري حزم · UUIDv7 للمفاتيح · OpenAPI 3.1 كمصدر عقد وحيد · MinIO في التطوير · العربية لغة الواجهة الافتراضية.

---

## 7. توزيع الأسبوعين

**الأسبوع 1 — الأرض الصلبة:** Monorepo وDocker Compose · ترحيلات قاعدة البيانات وRLS وأدوار DB · Auth وMFA · نموذج المستأجرين والعضويات · هيكل CI.
**الأسبوع 2 — الضمانات:** RBAC وObject Grants · `audit_events` مع سلسلة التجزئة · `provenance_events` · رفع الملفات إلى التخزين · Model Provider Gateway · workflow الاعتماد في Temporal · Design System ثنائي الاتجاه · اختبارات القبول AT-S0-01…13 · Threat Model وData Classification Matrix.

**Definition of Done لـ Sprint 0:** `make dev` يشغّل المنظومة كاملة من مستودع نظيف · اجتياز اختبارات القبول الثلاثة عشر · اعتماد ADR-0001…0004 · نشر عقد OpenAPI · تنفيذ تمرين استعادة واحد موثّق.

---

## 8. مخاطر السبرنت

| المخاطرة | التخفيف |
|---|---|
| RLS تُنسى في جدول واحد فيسقط العزل كله | اختبار آلي يمر على `information_schema` ويفشل عند وجود جدول بلا RLS مفعّلة |
| Temporal يبطئ الفريق في أسبوعين | نطاقه محصور في workflow واحد يثبت الاعتماد البشري فقط |
| RTL يُؤجَّل «حتى يستقر التصميم» فيصبح إعادة كتابة | AT-S0-11 يجعله شرط إغلاق سبرنت لا تحسينًا لاحقًا |
| توسّع النطاق نحو استخراج الحقائق قبل اكتمال الأساس | مخالف صريح لتعليمة START HERE؛ يُرفض في المراجعة |
