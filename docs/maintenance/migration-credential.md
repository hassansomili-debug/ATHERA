# اعتماد الترحيل | the migration credential

**تاريخ الفحص:** 2026-09-02 · بعد حادثة عزل المستأجرين (P0).

## السؤال

هل يحتاج الترحيل فعلًا دور `postgres`؟ وهل يُستبدل به دورٌ أقلّ صلاحية —
`athera_migrator` مثلًا؟

## ما تحتاجه الترحيلات فعلًا

| الترحيل | ما يطلبه | الدور اللازم |
|---|---|---|
| 0001 | `CREATE ROLE athera_app` | `CREATEROLE` |
| 0001 | `CREATE EXTENSION vector` | لا شيء عمليًّا — الامتداد قائم ويملكه `supabase_admin`، والعبارة `IF NOT EXISTS` |
| 0003 | `ALTER TABLE … FORCE ROW LEVEL SECURITY` و`CREATE POLICY` | **ملكية الجدول** |
| 0003 | `GRANT … TO athera_app` و`ALTER DEFAULT PRIVILEGES` | الملكية أو حقّ المنح |
| 0003 / 0014 | `CREATE TRIGGER` و`CREATE FUNCTION` | الملكية |
| 0018 | دالتا `SECURITY DEFINER` تقرآن `memberships` و`refresh_tokens` | **مالكٌ يتجاوز RLS** |

## الدور القائم

`postgres` على Supabase **ليس superuser**:

```
rolsuper=false  rolcreaterole=true  rolcreatedb=true  rolbypassrls=true  rolreplication=true
```

وهو يملك الجداول المئة وواحدًا في `public`، ويملك الدوال الأربع `app_*`.
والخارقية الحقيقية عند `supabase_admin` وحده، ولا وصول لنا إليه.

فالدور المستعمل للترحيل هو أصلًا **دور إدارة المشروع لا خارق النظام**.

## لماذا لا يُنشأ `athera_migrator`

ثلاثة أسباب، وكلها بنيوية لا تفضيلية:

1. **`BYPASSRLS` شرطٌ لا ترف.** دالتا الترحيل 0018 `SECURITY DEFINER` تعملان
   بصلاحيات **مالكهما**. و`memberships` و`roles` عليهما RLS **مفروضة**، أي
   تنطبق على المالك أيضًا. فمالكٌ بلا `BYPASSRLS` يجعل `app_login_tenant`
   تعيد صفر صفوف — **وينكسر تسجيل الدخول كليًّا**، وهو بعينه العطب الذي
   كشفه احتواء الحادثة.

2. **الملكية شرطٌ لسياسات RLS.** `FORCE ROW LEVEL SECURITY` و`CREATE POLICY`
   تتطلبان ملكية الجدول. فدورُ ترحيلٍ حقيقي يجب أن يملك الجداول المئة
   وواحدًا — ونقل الملكية إليه يعني إعادة تصميم ملكية القاعدة كاملةً، مع
   السياسات والمشغّلات والدوال. وهذا ما نُهي عنه صراحةً: لا يُعاد تصميم
   الملكية على عمياء.

3. **فلا فرق في الصلاحية.** دورٌ يملك كل الجداول ويحمل `CREATEROLE`
   و`BYPASSRLS` **ليس أقلّ صلاحية** من `postgres`؛ هو اسمٌ آخر له. والمكسب
   الوحيد اعتمادٌ منفصل يُدوَّر — وهو مكسبٌ حقيقي لكنه لا يوازن كسر الدخول
   وإعادة تصميم الملكية.

## القرار

**يبقى `postgres` للترحيل وحده.** والفصل الذي يهمّ ليس فصل الدور بل فصل
**متى يُحمَّل اعتماده**:

- `.env` → التطوير المحلي، ولا شيء إنتاجيًّا فيه.
- `.env.production.migration` → لا يقرؤه شيء تلقائيًّا، ومدخله الوحيد
  `make migrate-prod CONFIRM=<project-ref>`.
- أسرار Fly → `DATABASE_URL` على `athera_app` وحده.

**ولا يعود الاعتماد المميَّز `DATABASE_URL` بحال.** يحرس ذلك أمرُ الترحيل
(يرفض دور زمن التشغيل)، وحارسُ الجهوزية (يرفض دورًا يتجاوز RLS)، وفحصُ Fly
على `/readyz`.

## التدوير

**لم يكتمل — ويحتاج خطوة بشرية.**

`ALTER ROLE postgres WITH PASSWORD …` مرفوض:

```
permission denied to alter role
DETAIL: Only superusers can alter privileged roles.
```

لأن `postgres` يحمل `BYPASSRLS` و`REPLICATION`، فيَعُدّه PostgreSQL دورًا
مميَّزًا لا يغيّره إلا خارق. والخارق `supabase_admin` غير متاح.

**المسار المدعوم:** لوحة Supabase → Project Settings → Database → Reset
database password. ثم تُحدَّث قيمة `DATABASE_MIGRATION_URL` في
`.env.production.migration` **وحدها** — لا مكان آخر يحمل هذا الاعتماد.

**وما يخفّف الحاجة إليه:** الملف لم يدخل تاريخ git قط (مُتحقَّق منه)، ولم
يغادر جهاز المشغّل، ولم يعد يُحمَّل ضمنًا مع أي أمر.
