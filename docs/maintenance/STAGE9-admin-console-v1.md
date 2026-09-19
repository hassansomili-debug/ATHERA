# لوحة الإدارة V1 | PUBRIVA Admin Console V1 (Stage #9)

**الحال:** مُنجَزٌ في فرع `feature/stage9-admin-console-v1`، ومرشَّحٌ للمراجعة — **لم يُدمج**.
**الأساس:** `main` عند `a0d384d3f72922c524055e4b6c3201d45197da2a`.
**المخطَّط:** `0037` — **بلا ترحيلٍ جديد.** سبعةٌ وثلاثون ترحيلًا، ولا `0038`.

## ١ · الهدف

لوحةٌ **للقراءة وحدَها**، لمديري **مستأجرٍ واحد**: من في المساحة، وما فيها من
بحوثٍ وملفّاتٍ ورسائل، وكم استُهلك من النموذج وكم سُجّلت تكلفتُه، وأين أخفق
التشغيل — **بياناتُ تشغيلٍ لا محتوى بحث**. وتربط بما هو قائمٌ ولا تكرّره:
سجلُّ التدقيق (`/audit`) وحالةُ التشغيل (`/settings`).

وليست لوحةَ منصّة، ولا أداةَ إدارةِ حسابات. كلُّ ما يغيّر حالًا مُحالٌ إلى
المرحلة ١٠ بالاسم (§١٤).

## ٢ · حدُّ المستأجر الحاليّ

- **المستأجرُ من الرمز وحدَه**: `principal.tenant_id`. ولا مُعاملَ `tenant_id` في
  أيّ مسارٍ تحت `/api/v1/admin` أصلًا؛ و`?tenant_id=<B>` يُتجاهل (`test_18`).
- **الجلسةُ جلسةُ الطلب العاديّة** (`get_session`)، فسياقُ RLS
  (`app_current_tenant()`) قائمٌ في كلّ عبارة. لا `system_session`، ولا
  `BYPASSRLS`، ولا مفتاحُ خدمة، ولا اتصالُ مالك (`test_03`).
- **وطبقةٌ ثانيةٌ فوق RLS**: كلُّ عبارةٍ تقيّد `tenant_id == tid` صراحةً. ولأنّ RLS
  وحدَها تُخفي حذفَ هذا الشرط في الفحوص الحيّة، **يقرأ `test_22` المصدرَ** ويرفض
  أيَّ دالّةٍ تلمس نموذجًا مستأجَرًا بلا شرطه.
- **`system_admin` هنا مديرُ هذا المستأجر، لا المنصّة.** مديرٌ في A لا يرى B —
  لا عدًّا ولا بحثًا ولا تفصيلًا ولا اسمَ مالك.

## ٣ · الأدوارُ الإداريّة

الحارسُ **واحد** (`routers/admin.py`):

```python
admin_guard = require_roles(*sorted(rbac.ADMIN_ROLE_KEYS))
```

`research_admin`، `college_admin`، `institution_admin`، `system_admin` — **من
المصدر لا من قائمةٍ منسوخة** (`test_02`). ويمرّ بـ`require_roles` فيرث سياسةَ MFA
المركزيّة (`mfa_required_for_admin_roles`) كما هي: مديرٌ بلا عاملٍ ثانٍ يُردّ
بالرمز المركزيّ نفسِه (`test_08`)، ولم تُطفأ السياسةُ لتيسير فحص المتصفّح —
الرحلةُ تدخل بكلمة مرورٍ **ورمزِ TOTP حقيقيّ** (RFC 6238 في Node).

وفي المتصفّح، **ظهورُ** الرابط يُشتقّ من ادّعاء `roles` في رمز الدخول، وقائمةُ
الأدوار في `lib/admin.ts` محروسةٌ بفحصٍ يقرأ `rbac.py` نفسَه. **الظهورُ ليس إذنًا**:
الإذنُ للخادم وحدَه، وكتابةُ الرابط يدويًّا تُعطي «لا صلاحية» لا بيانات.

## ٤ · المسارات

كلُّها `GET`، وكلُّها خلف `admin_guard` (`test_01`):

| المسار | الصفحة | المحتوى |
|---|---|---|
| `/api/v1/admin/overview` | `/{locale}/admin` | عدّاداتُ المساحة |
| `/api/v1/admin/users` | `/{locale}/admin/users` | الأعضاء — بحث، دور، حال، مؤشّر |
| `/api/v1/admin/users/{user_id}` | `/{locale}/admin/users/{userId}` | تفصيلُ عضو |
| `/api/v1/admin/projects` | `/{locale}/admin/projects` | البحوث — بحث، دورةُ حياة، مالك، مؤشّر |
| `/api/v1/admin/usage?window=7d\|30d\|90d` | `/{locale}/admin/usage` | استهلاكُ النموذج |
| `/api/v1/admin/operations?view=failed\|in_progress\|all` | `/{locale}/admin/operations` | الإخفاقُ والتشغيلُ الجاري |

والتدقيقُ: `/{locale}/audit` القائم (بحارسه الإداريّ القائم) — تبويبٌ في اللوحة،
ورابطٌ منه عائدٌ إليها. وحالةُ التشغيل: `/{locale}/settings` — رابطٌ لا نسخة.

## ٥ · المقاييسُ وتعريفاتُها الدقيقة

| المقياس | التعريف |
|---|---|
| `member_count` | أشخاصٌ **متمايزون** لهم عضويّةٌ هنا — لا عددُ العضويّات (مستخدمٌ بدورين = ١) |
| `active_identity_count` | منهم من `users.is_active`. **والحالُ عامّةٌ للحساب لا للعضويّة** — يُسمّى في الواجهة «هُويّةٌ مفعَّلة» |
| `signed_in_7d/30d` | منهم من `last_login_at` في النافذة، **بساعة القاعدة** (`now() - interval`) |
| `projects.total` | بحوثٌ ليست في السلّة؛ `active` = لا أرشيفَ ولا سلّة؛ `archived`؛ `trashed` منفصل |
| `files` | ليست في السلّة: العدد، ومجموعُ `size_bytes`، و`pending`؛ و`trashed` منفصل |
| `theses` | لكلٍّ من حالات `processing_state` التسع صفرٌ صريحٌ أو عدد؛ `stalled` = في الطيران وتغيّرت حالُه قبل `STALE_AFTER` |
| `ai` (٣٠ يومًا) | من `model_runs` حرفيًّا: العدد؛ `succeeded` = `ok`؛ `failed` = `error`؛ `ambiguous` = `ambiguous` (نتيجةٌ خارجيّةٌ لا تُعرف — **ليست إخفاقًا**)؛ `other_status` الباقي؛ مجموعُ الرموز |
| `operations` (٣٠ يومًا) | `agent_runs` `failed`/`blocked`؛ `tool_runs` `error`/`denied`؛ إخفاقاتُ معالجة الرسائل من `FAILURE_STATES` |
| `audit` | آخرُ `chain_seq` وتوقيتُه — **لا تحقّقَ كاملًا من السلسلة مع كلّ تحميل**؛ التحقّقُ في `/audit` |
| `attributed_model_runs_30d` | تشغيلاتُ نموذجٍ عبر `agent_run_id → agent_runs.requested_by` — `model_runs` بلا عمودِ مستخدم، فالمنسوبُ وحدَه يُعدّ ويُسمّى كذلك |
| مالكُ البحث | ملفُّ الباحث (`researcher_profiles.user_id`) وإلّا فاعلُ أوّلِ حدثِ `*.project_created` — **التعريفُ نفسُه في المنتج**، تعبيرًا مترابطًا واحدًا |
| الكمون | متوسّطٌ ووسيطٌ (`percentile_cont(0.5)`) على ما سجّل `latency_ms` وحدَه، مع عدده |

## ٦ · ما يُستبعد عن قصد (الخصوصيّة)

لا يحمل أيُّ جوابٍ إداريّ: `password_hash`، سرَّ MFA، رموزَ الدخول أو التجديد أو
الاستعادة، مفاتيحَ الإعادة الآمنة، أسرارَ المزوّدين، `request_payload`،
`response_payload`، `input_summary`/`output_summary`، نصَّ الخطأ الحرّ،
`blocked_reason`، نصَّ بحثٍ أو ملخّصَه، آثارَ الاستثناءات.

- الخطأُ يُعرض **حضورًا** (`error_present: bool`) لا نصًّا.
- `failure_code` للرسالة يُعرض لأنّه من **مفرداتٍ مغلقة** يفرضها قيدٌ في القاعدة.
- عنوانُ البحث العاملُ وحدَه — لا ملخّصَ ولا نصّ.
- محروسٌ ثلاثَ مرّات: مخطَّطُ الجواب لا يحوي حقلًا يشبه سرًّا أو حمولة
  (`test_04`)؛ حمولةٌ بحثيّةٌ مزروعةٌ في كلّ جدول تشغيلٍ لا تظهر في أيّ جواب
  (`test_20`)؛ ولا في صفحة المتصفّح (`stage9-admin-console.spec.ts`).

## ٧ · قاعدةُ جدول `users` العامّ

قِيس من القاعدة الحيّة: `users` و`tenants` و`mfa_factors` سياستُها
**`global_readwrite: true`** — RLS **لا تحمي** هذه الجداول. فالقاعدةُ:

> **لا يُبلَغ `User` إلّا عبر `Membership` في هذا المستأجر.**

- القائمةُ `JOIN` (لا `LEFT JOIN`) على مجمَّع العضويّات.
- البحثُ **داخل** ذلك الـ`JOIN` — لا بحثٌ عامٌّ يُصفّى بعده.
- التفصيلُ: من لا عضويّةَ له هنا ⇒ `404 admin.user_not_found` — **الرمزُ نفسُه**
  لحسابٍ في مستأجرٍ آخر ولمعرّفٍ لا وجودَ له، فلا يصير البابُ كاشفًا للوجود.
- أسماءُ المالكين وطالبي التشغيل: لا اسمَ إلّا لعضوٍ هنا؛ مالكٌ غادر يبقى معرّفًا بلا اسم.

`test_14` يهاجم الجدولَ العامَّ من كلّ باب: البحثُ بالبريد، والتفصيلُ، والعدّ.

## ٨ · ما يستطيعه المدير

قراءةُ كلِّ ما سبق، وتصفيتُه وتصفّحُه، والانتقالُ من مستخدمٍ إلى بحوثه، ومن
تشغيلٍ فاشلٍ إلى صفحة الآثار، ومن اللوحة إلى التدقيق وحالة التشغيل. **رؤيةُ
الأدوار** — لا تغييرها.

## ٩ · ما لا يستطيعه — عمدًا

لا تعطيلَ حسابٍ ولا تفعيله، لا إعادةَ تعيين كلمة مرور، لا إنهاءَ جلسات، لا حذفَ
مستخدم، لا انتحالَ هُويّة، لا منحَ دورٍ ولا سحبه، لا قراءةَ مستأجرٍ آخر. ولا
مسارَ لشيءٍ من ذلك (`test_01`، `test_05`).

وما هو قائمٌ قبل المرحلة ويحمل خطرًا (`POST /tenants/{id}/members`) **لم يُعرض
في اللوحة**، وأُحيل عيبُه إلى §١٤.

## ١٠ · دلالةُ تكلفة النموذج

`model_runs.cost_usd` يقبل الفراغ، والفراغُ يعني **لم يُسجَّل** — لا «صفر».

- `recorded_cost_usd` = `SUM(cost_usd) FILTER (WHERE cost_usd IS NOT NULL)` —
  `Decimal` لا عائم، ويصل نصًّا إلى المتصفّح.
- ومعه دائمًا `runs_with_cost` و`runs_without_cost`.
- الواجهة: لا تشغيلات ⇒ «لا تشغيلات»؛ تشغيلاتٌ كلُّها بلا تكلفة ⇒ «التكلفةُ لم
  تُسجَّل» **لا «٠٫٠٠ $»**؛ وإلّا القيمةُ و«سُجّلت لـ٢ من ٣».
- اسمُها «التكلفةُ المسجَّلة» — ليست فاتورةً ولا تقديرًا.

## ١١ · الترقيم

- مؤشّرُ مجموعةِ مفاتيح (keyset) على `(since, id)` للمستخدمين و`(created_at, id)`
  للبحوث — مستقرٌّ مع التعادل، **معتِم** (base64url لـJSON)، وتالفُه ⇒
  `422 admin.invalid_cursor`.
- الافتراضُ ٢٥، والأقصى ١٠٠ (`limit=101` ⇒ ٤٢٢). العمليات: ٥٠، والأقصى ٢٠٠، ونافذةُ
  ٩٠ يومًا حتى لـ«الكلّ».
- الاستخدام: النوافذُ `7d|30d|90d` وحدَها.
- **لا N+1**: صفحةٌ من ٢٥ وصفحةٌ من ٥ تُصدران العددَ نفسَه من العبارات (`test_21`)،
  والعددُ ≤ ١٢.

## ١٢ · الفحوص

**API** — `apps/api/tests/test_at_stage9_admin_console.py`: ٢٩ فحصًا (بنيويّة،
ومستأجران حقيقيّان، وأدوارٌ متعدّدة، وMFA، ودقّةُ العدّادات، والنوافذ، والترقيم،
والهجومُ على الجدول العامّ، وحقنُ المستأجر، والخصوصيّة، وشكلُ الاستعلام، والشرطُ
الصريح).

**المتصفّح** — `apps/web/tests/stage9-admin-console.spec.ts`: ١٣ فحصًا على المكدّس
الحقيقيّ (واجهةٌ حقيقيّة، API حقيقيّ، MFA حقيقيّ، مساحتان): الرابطُ لا يظهر
للباحث وكتابتُه لا تُظهر بيانات؛ دخولُ المدير بـTOTP؛ البحثُ لا يجد عضوَ مساحةٍ
أخرى؛ المرشّحات؛ عزلُ البحوث؛ أرقامُ الاستخدام والتكلفةُ غيرُ المسجّلة؛ العملياتُ
بلا حمولة؛ لا صفرَ قبل الجواب؛ الإخفاقُ خطأٌ لا قائمةٌ فارغة؛ AR/RTL وEN/LTR.
وخطوةٌ جديدةٌ في `rc-e2e.yml` تشغّلها في CI (`npm run test:admin-console`).

**مصفوفةُ اللدغ** — ٣٥ طفرةً (٢٨ في الخادم، ٧ في الواجهة)، كلُّها تلدغ (الملحق).

## ١٣ · قرارُ المخطَّط

**لا ترحيل.** كلُّ مقياسٍ مشتقٌّ من جداولَ قائمة؛ لا جداولَ مقاييس ولا مشاهدَ
مادّيّة. ويبقى المخطَّطُ عند `0037`.

ولُوحظ ما قد يستحقّ فهرسًا لاحقًا — `model_runs (tenant_id, created_at)` — ولم
يُضف: الحجمُ الحاليّ لا يطلبه، والفهرسُ ترحيلٌ يحتاج قرارًا. مُحالٌ إلى §١٤.

## ١٤ · الدَّينُ المُحال إلى المرحلة ١٠

**لم يُنفَّذ منه شيء.** وما يلي حدودٌ تُرى الآن بوضوح:

### من دفتر المرحلة

| البند | الحالُ بعد المرحلة ٩ |
|---|---|
| مديرُ منصّةٍ عابرٌ للمستأجرين | غير موجود؛ `system_admin` مديرُ مستأجره وحدَه |
| وصولُ الدعم عبر المستأجرين | غير موجود |
| تعطيلُ الحساب/إعادةُ تفعيله | غير موجود؛ و`users.is_active` **عامّ** لا لكلّ مستأجر — قرارُ نطاقه قبل أيّ زرّ |
| سياسةُ الانتحال | غير موجودة، ولا مسار |
| هرميّةُ منح الامتيازات | غير موجودة — انظر العيبَ ١ أدناه |
| حمايةُ المدير الأخير/خفضُ الذات | غير موجودة |
| دورُ دعمٍ مخصّص | غير موجود |
| إجراءاتُ كسر الزجاج | غير موجودة |
| مدّةُ جلسةٍ إداريّةٍ مرتفعة | الجلسةُ الإداريّةُ كغيرها |
| MFA تصعيديّ فوق السياسة | السياسةُ المركزيّةُ وحدَها |
| قيودُ IP/جهاز للمدير | غير موجودة |
| مقاييسُ منصّةٍ عابرةٌ آمنة | غير موجودة |
| حدودُ معدّلٍ لأفعال الإدارة | غير موجودة (اللوحةُ قراءةٌ وحدَها) |
| مصفوفةُ هجومِ RLS رسميّةٌ للعمليّات المميّزة | غير موجودة؛ ما هنا فحوصُ قراءةٍ لا مصفوفةٌ رسميّة |

### عيوبٌ قائمةٌ قبل المرحلة ٩ — وُجدت ولم تُصلَح (خارج النطاق)

1. **تصعيدُ امتياز** — `POST /api/v1/tenants/{id}/members`
   (`routers/tenants.py:66`) يسمح لـ`research_admin` بمنح **أيِّ** دورٍ، ومنه
   `system_admin`. لا هرميّة. **لم يُعرض في اللوحة.**
2. **كاشفُ وجودِ بريد** — المسارُ نفسُه يبحث `User` بالبريد في الجدول العامّ
   (`tenants.py:76`) ويُجيب بفرقٍ بين «لا حساب» و«حساب».
3. المسارُ نفسُه لا يقبل `college_admin` في حارسه (`tenants.py:69`) وهو دورٌ إداريّ.
4. `GET /tenants/{id}/members` (`tenants.py:114`) **بلا دورٍ إداريّ** — أيُّ عضوٍ
   يرى بريدَ الأعضاء وأدوارَهم — ويقيّد المستأجرَ بـRLS وحدَها.
5. `routers/audit.py:22` يكتب قائمةَ الأدوار الإداريّة نصًّا بدلَ
   `rbac.ADMIN_ROLE_KEYS` — تطابقُها اليوم مصادفة.
6. `GET /api/v1/brain/traces/{id}` (`routers/brain.py:255`) مقروءٌ لأيِّ عضوٍ في
   المستأجر، وجوابُه يحمل تشغيلاتِ الأدوات. (لذا رابطُ اللوحة إلى الآثار
   **قائمةٌ عامّة** لا أثرٌ بعينه يحمل حمولة.)
7. `mfa_factors.secret_encrypted` (`models/identity.py:176`) يُخزَّن **نصًّا صريحًا**
   رغم اسمه، والجدولُ `global_readwrite`.
8. أدوارُ الرمز تبقى حتى انتهائه: سحبُ دورٍ لا يُسقط إذنَ اللوحة قبل ذلك.
9. `model_runs` بلا فهرس `(tenant_id, created_at)` — نوافذُ الاستخدام مسحٌ للمستأجر.

## ١٥ · معاييرُ إغلاق المرحلة ٩

| # | المعيار | البيّنة |
|---|---|---|
| 1 | `/admin` يعمل بالعربيّة والإنجليزيّة | فحصُ المتصفّح AR/RTL وEN/LTR |
| 2 | غيرُ المدير لا يقرأ | `test_06` (خمسةُ أدوار × كلّ المسارات)؛ المتصفّح |
| 3 | الأدوارُ الأربعة تدخل وفق MFA المركزيّ | `test_07`، `test_08`؛ دخولُ TOTP في المتصفّح |
| 4 | النظرةُ العامّة دقيقة | `test_09` |
| 5 | المستخدمون محصورون بالمستأجر | `test_13`، `test_14` |
| 6 | التفصيلُ لا يكشف غيرَ عضو | `test_14`، `test_16` |
| 7 | البحوثُ محصورة | `test_17`، `test_18` |
| 8 | الاستخدامُ من جداول التشغيل الحقيقيّة | `test_10`، `test_11` |
| 9 | الفراغُ في التكلفة صادق | `test_10`؛ المتصفّح (بلا «٠٫٠٠ $») |
| 10 | العملياتُ بياناتٌ وصفيّة | `test_19` |
| 11 | لا حمولةَ بحثيّة تتسرّب | `test_04`، `test_20`؛ المتصفّح |
| 12 | التدقيقُ مدمج | تبويبٌ وروابطٌ ذهابًا وإيابًا |
| 13 | حالةُ التشغيل مربوطةٌ بأمان | رابطٌ إلى `/settings` لا نسخة |
| 14 | الترقيمُ محدود | `test_15`، `test_21` |
| 15 | التحميلُ/الخطأ/الفراغ صادقة | المتصفّح: لا صفرَ قبل الجواب، الخطأُ ليس فراغًا |
| 16–18 | لا تعطيل، لا انتحال، لا مديرَ منصّة | `test_01`، `test_05`؛ §٢، §٩ |
| 19 | لا BYPASSRLS/مفتاحَ خدمة | `test_03`، `test_22` |
| 20 | لا ترحيل | §١٣ |
| 21–24 | الانحدارُ أخضر؛ H2 والمرحلة ٨ مغلقتان؛ PR #126 لم يُمسّ | تقريرُ الإغلاق |

## الملحق · مصفوفةُ اللدغ

**٣٥/٣٥ تلدغ** — كلُّ طفرةٍ تغيّر سلوكًا حقيقيًّا (لا خطأَ صياغة)، ويُعاد الملفُّ بعدها،
وطفراتُ الواجهة تُعيد بناءَ الحزمة قبل الفحص (وإلّا خدم الخادمُ القائمُ القديمَ).

| # | الطفرة | الموضع | الفحص | النتيجة |
|---|---|---|---|---|
| M01 | overview loses the admin guard | `admin.py` | `test_02 or test_06` | لدغت (6 failed / 0 passed) |
| M02 | guard drops research_admin | `admin.py` | `test_02 or test_07` | لدغت (2 failed / 3 passed) |
| M03 | guard admits researcher | `admin.py` | `test_02 or test_06` | لدغت (2 failed / 4 passed) |
| M04 | guard bypasses MFA (own role check) | `admin.py` | `test_02 or test_08` | لدغت (2 failed / 0 passed) |
| M05 | users read without the membership anchor | `admin_console.py` | `test_14 or test_13` | لدغت (2 failed / 0 passed) |
| M06 | detail reads the global users table | `admin_console.py` | `test_14 or test_16` | لدغت (1 failed / 1 passed) |
| M07 | member count counts memberships not people | `admin_console.py` | `test_09` | لدغت (1 failed / 0 passed) |
| M08 | member aggregate ignores tenant | `admin_console.py` | `test_22 or test_14` | لدغت (1 failed / 1 passed) |
| M09 | projects list drops the tenant predicate | `admin_console.py` | `test_22` | لدغت (1 failed / 0 passed) |
| M10 | NULL cost counted as zero-cost runs | `admin_console.py` | `test_09 or test_10` | لدغت (2 failed / 0 passed) |
| M11 | ambiguous counted as failed | `admin_console.py` | `test_09 or test_10` | لدغت (1 failed / 1 passed) |
| M12 | usage window unbounded | `admin_console.py` | `test_11` | لدغت (1 failed / 0 passed) |
| M13 | usage accepts any window | `admin.py` | `test_11` | لدغت (1 failed / 0 passed) |
| M14 | users page has no maximum | `admin.py` | `test_15` | لدغت (1 failed / 0 passed) |
| M15 | unstable cursor ordering (no id tiebreak) | `admin_console.py` | `test_15` | لدغت (1 failed / 0 passed) |
| M16 | duplicate role rows (no distinct) | `admin_console.py` | `test_12` | لدغت (1 failed / 0 passed) |
| M17 | password_hash exposed in user rows | `admin.py` | `test_04` | لدغت (1 failed / 0 passed) |
| M18 | MFA secret exposed in the schema | `admin.py` | `test_04` | لدغت (1 failed / 0 passed) |
| M19 | tool payload included in operations | `admin.py` | `test_04 or test_19 or test_20` | لدغت (2 failed / 1 passed) |
| M20 | free-text agent error exposed | `admin.py` | `test_19 or test_20` | لدغت (1 failed / 1 passed) |
| M21 | account-disable route added | `admin.py` | `test_01 or test_05` | لدغت (2 failed / 0 passed) |
| M22 | console reads through system_session | `admin_console.py` | `test_03` | لدغت (1 failed / 0 passed) |
| M23 | browser tenant_id honoured | `admin.py` | `test_18 or test_17` | لدغت (1 failed / 1 passed) |
| M24 | owner names without membership (cross-tenant name leak) | `admin_console.py` | `test_17 or test_22 or test_14` | لدغت (1 failed / 2 passed) |
| M25 | N+1: per-row project count | `admin_console.py` | `test_21` | لدغت (1 failed / 0 passed) |
| M26 | search walks all users then filters | `admin_console.py` | `test_14` | لدغت (1 failed / 0 passed) |
| M27 | non-member detail answers differently than unknown id | `admin_console.py` | `test_14` | لدغت (1 failed / 0 passed) |
| M28 | operations window unbounded | `admin_console.py` | `test_19` | لدغت (1 failed / 0 passed) |
| W01 | admin link shown to everyone | `NavLinks.tsx` | `«researcher sees no admin link»` | لدغت (1 failed / 0 passed) |
| W02 | browser role list drops a canonical role | `admin.ts` | `«rbac.ADMIN_ROLE_KEYS»` | لدغت (1 failed / 0 passed) |
| W03 | forbidden shown as empty data | `AdminShell.tsx` | `«researcher sees no admin link»` | لدغت (1 failed / 0 passed) |
| W04 | API failure shown as an empty list | `AdminShell.tsx` | `«failed request»` | لدغت (1 failed / 0 passed) |
| W05 | zeros painted before the overview answers | `AdminShell.tsx` | `«no zero is shown»` | لدغت (1 failed / 0 passed) |
| W06 | unrecorded cost rendered as $0.00 | `AdminShell.tsx` | `«no recorded cost»` | لدغت (1 failed / 0 passed) |
| W07 | cost coverage hidden | `AdminShell.tsx` | `«seeded 30-day totals»` | لدغت (1 failed / 0 passed) |

### ستٌّ نجت في الجولة الأولى — وكلُّها كشفت ثغرةً في الفحص لا في الطفرة

| # | لمَ نجت | ما أُضيف |
|---|---|---|
| M15 | عضويّاتُ الفحص بطوابعَ متمايزة، فلا تعادلَ يكشف غيابَ المعرّف عن المؤشّر | ثلاثون عضويّةً **بالطابع نفسِه** وحدُّ الصفحة داخلَها |
| M20 | الطفرةُ الأولى مرّرت الخطأَ عبر اسمٍ غيرِ فارغ فحُجبت | أُعيدت تسريبًا حقيقيًّا: حقلٌ في المخطَّط يحمل نصَّ الخطأ — ويلدغه `test_20` |
| M23 | RLS حجبت بياناتِ B، فمسارٌ يأخذ المستأجرَ من الطلب أجاب **فارغًا** لا مسرّبًا — والفحصُ لم يشترط إلّا غيابَ B | يُشترط أنّ بياناتِ A **باقيةٌ** تحت الحقن |
| M24 | كلُّ مالكٍ في الفحص عضو | بحثٌ في A أنشأه حسابٌ من B: المعرّفُ يظهر، والاسمُ والبريدُ لا |
| M28 | لا تشغيلَ قديمًا في الفحص | تشغيلٌ قبل ١٢٠ يومًا لا يبلغه «الكلّ» |
| W07 | الفحصُ قرأ النصَّ ولم يشترط الظهور | `toBeVisible()` على سطر التغطية |

وM13 وM14 احتاجتا إلى تطفير طبقتين معًا: النافذةُ تُرفض في المسار **وفي الخدمة**،
فكسرُ إحداهما وحدَها لا يغيّر شيئًا — وذلك دفاعٌ مقصود لا ثغرة.
