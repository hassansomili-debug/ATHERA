# تمرين النسخ الاحتياطي والاستعادة | Backup & Restore Drill

المرجع: §38.2 · اختبار القبول AT-S0-12.
القاعدة: **الاستعادة غير المختبرة ليست نسخة احتياطية.** لا يُغلق Sprint 0 قبل تنفيذ هذا التمرين مرة واحدة على الأقل وتسجيل نتيجته أدناه.

## 1. أخذ نسخة

```bash
docker compose -f infra/compose/docker-compose.dev.yml exec -T postgres \
  pg_dump -U athera_owner -Fc athera > backups/athera-$(date +%Y%m%d-%H%M).dump
```

## 2. الاستعادة إلى قاعدة نظيفة

```bash
createdb -U athera_owner athera_restore_test
pg_restore -U athera_owner -d athera_restore_test --clean --if-exists backups/<الملف>.dump
```

## 3. التحقق بعد الاستعادة — لا يكفي أن تعمل القاعدة

| الفحص | الأمر | الشرط |
|---|---|---|
| سلامة سلسلة التدقيق | `make verify-audit` | `intact = true` لكل مستأجر |
| RLS ما زالت مفعّلة | استعلام `pg_class.relrowsecurity` | لا جدول بـ`tenant_id` بلا RLS |
| صلاحيات دور التطبيق | `\dp audit_events` | لا UPDATE/DELETE لـ`athera_app` |
| pgvector | `SELECT extname FROM pg_extension` | يحتوي `vector` |

> تحذير: `pg_restore` يستعيد الجداول والسياسات، لكن **أدوار قاعدة البيانات عنقودية لا تُستعاد مع الـdump**. بعد كل استعادة إلى عنقود جديد، شغّل الترحيل `0001` أو أنشئ `athera_app` يدويًا — وإلا عاد التطبيق يعمل بدور مالك يتجاوز RLS، وهو أسوأ فشل ممكن لأنه صامت.

## سجل التمارين

| التاريخ | المنفّذ | زمن الاستعادة | نتيجة الفحوص الأربعة | ملاحظات |
|---|---|---|---|---|
| _(لم يُنفَّذ بعد — AT-S0-12 مفتوح)_ | | | | |
