# النشر على Supabase وVercel | Deploying to Supabase and Vercel

> هذا الدليل يصف **ما يعمل وما لا يعمل** على هذين المستضيفين. الجزء الثاني
> أهم: منصة تُنشر نصفها وتُترك نصفها الآخر معطّلًا بلا إعلان هي أسوأ من
> منصة لم تُنشر.

---

## ١. توزيع المكوّنات

| المكوّن | المستضيف | لماذا |
|---|---|---|
| `apps/web` (Next.js) | **Vercel** | مناسب تمامًا |
| `apps/api` (FastAPI) | **Fly.io / Railway / Render** | عملية دائمة، وليست دوال بلا حالة |
| `services/worker` (Temporal) | نفس مستضيف الـAPI | عملية تعمل بلا انقطاع |
| خادم Temporal | **Temporal Cloud** أو مستضاف | لا يعمل على Vercel |
| PostgreSQL + pgvector | **Supabase** | pgvector وRLS مدعومان |
| تخزين الملفات | **Supabase Storage** أو S3 | متوافق مع S3 |

**الـAPI لا يُنشر على Vercel.** دوال Vercel بلا حالة ولها مهلة قصيرة، بينما
تعتمد المنصة على تجمّع اتصالات دائم وسياق مستأجر داخل معاملة. النشر عليها
يعمل في العرض ويفشل تحت الحمل.

---

## ٢. Supabase — خطوة بخطوة

### أ. الاتصال: أي منفذ؟

| المنفذ | الوضع | الاستخدام |
|---|---|---|
| **5432** | اتصال مباشر | **الترحيلات** — تحتاج جلسة واحدة متصلة |
| **6543** | مجمّع بوضع المعاملة | **الـAPI** — تجمّع عالي التزامن |

الكود يكتشف المجمّع من نصّ الرابط (`:6543` أو `pooler.`) ويعطّل ذاكرة
العبارات المهيّأة في asyncpg — انظر `_connect_args()` في
[`db.py`](../../apps/api/athera_api/db.py). بدون ذلك يظهر
`DuplicatePreparedStatementError` **تحت الحمل فقط**، أي في الإنتاج لا في
الاختبار.

`SET LOCAL app.tenant_id` سليم مع وضع المعاملة: `tenant_session` تفتح معاملة
صريحة، فالضبط والاستعلام في المعاملة نفسها.

### ب. الامتدادات

```sql
create extension if not exists vector;
create extension if not exists pg_trgm;
```

Supabase يضعها في مخطط `extensions`. الترحيلات لا تفترض مخططًا بعينه، و
`pg_trgm` ملفوف بـ`DO` يُصدر تحذيرًا ولا يفشل — فهو فهرس أداء لا قيد صحة.

### ج. دور التطبيق

الترحيل `0001` ينشئ `athera_app` **بلا BYPASSRLS**. هذا جوهر ADR-0002: حتى
لو أخطأ الكود، لا تعود صفوف مستأجر آخر.

```bash
export ATHERA_DB_APP_PASSWORD='<كلمة قوية>'
export APP_ENV=production
export DATABASE_MIGRATION_URL='postgresql+psycopg://postgres:<pw>@db.<ref>.supabase.co:5432/postgres'
make migrate
```

الترحيل **يفشل** خارج `development` بلا `ATHERA_DB_APP_PASSWORD`. الفشل هنا
أرخص من قاعدة إنتاج بكلمة معروفة في المستودع.

ثم يشير `DATABASE_URL` إلى `athera_app` عبر المجمّع:

```
postgresql+asyncpg://athera_app:<pw>@<ref>.pooler.supabase.com:6543/postgres
```

### د. ما يجب التحقق منه بعد الترحيل

```bash
python scripts/verify_db_constraints.py    # اثنتا عشرة عملية ممنوعة
python scripts/verify_audit_chain.py       # سلامة سلسلة التدقيق
```

نجاح الترحيل لا يعني أن RLS تعمل. هذان السكربتان **يحاولان** الممنوع
ويفشلان إن نجح أيٌّ منه.

### هـ. ما لا يُستخدم من Supabase

- **Supabase Auth**: المنصة تملك مصادقتها بأدوار §28 وMFA للأدوار الإدارية.
  استخدام الاثنين معًا يعني مصدرين للحقيقة عن هوية المستخدم.
- **Supabase RLS عبر `auth.uid()`**: سياساتنا تعتمد `app_current_tenant()`
  المضبوطة من رمز موقّع في طبقتنا. خلط الآليتين يترك ثغرة عند حافة كلٍّ منهما.
- **PostgREST**: الوصول المباشر إلى الجداول من المتصفح يلتف على البوابات
  والتدقيق. **يجب تعطيله** أو حصر مخطط `public` عنه.

> هذه ليست تفضيلات: الوصول المباشر من المتصفح إلى الجداول يعني ادعاءً يُكتب
> بلا حاجز نزاهة، واعتمادًا يُسجَّل بلا سلسلة تجزئة.

---

## ٣. Vercel — الواجهة

### أ. الإعداد

| المفتاح | القيمة |
|---|---|
| Root Directory | `apps/web` |
| Framework | Next.js |
| Build Command | `npm run build` |
| Install Command | `npm ci` |

### ب. متغيّرات البيئة

```
NEXT_PUBLIC_API_BASE_URL=https://api.<نطاقك>
```

هذا **المتغيّر الوحيد** الذي تحتاجه الواجهة. لا مفتاح مزوّد نموذج هنا ولا
في أي مكان يصل إليه المتصفح — CSP في
[`next.config.mjs`](../../apps/web/next.config.mjs) تمنع ذلك، و`AT-S0-09`
يفشل البناء لو حاول أحد.

### ج. على الـAPI

بعد أول نشر، أضف نطاق Vercel إلى الـAPI:

```
CORS_ALLOWED_ORIGINS=https://pubriva.com
# النطاق القانوني وحده. وأسماء استضافة Vercel لا تُدرَج إلا نافذةَ
# ترحيلٍ محدودة، وتُنزع بعدها — فما يُترك مسموحًا يبقى مسموحًا.
```

نسيان هذا يعني واجهة تعمل ولا تصل إلى شيء. الافتراض هو `localhost` وحده
عمدًا: الـAPI لا يُفتح لأي نطاق بالصدفة.

---

## ٤. ما يبقى معطّلًا بعد هذا النشر

| القدرة | ما تحتاجه |
|---|---|
| استدعاء نموذج | `MODEL_PROVIDER` + مفتاح |
| بوابات الاعتماد الدائمة | خادم Temporal + `TEMPORAL_ENABLED=1` |
| الرصد المجدول (§51.11) | Temporal + `LITERATURE_REGISTRY` غير `offline` |
| WoS · Scopus · JCR | قرار §47.3 |

شاشة **الإعدادات ووضع التشغيل** تعرض هذه الحالات صراحةً. المستخدم يرى أن
النظام لا يستدعي نموذجًا بدل أن يقرأ صمته على أنه رأي.
