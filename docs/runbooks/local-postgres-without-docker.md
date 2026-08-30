# PostgreSQL محلي بلا Docker | Local PostgreSQL without Docker

تشغيل قاعدة بيانات حقيقية للتحقق، على جهاز بلا Docker ولا Homebrew ولا صلاحية إدارية.

## لماذا

القيود في الترحيلات الثلاثة عشر هي جوهر ضمانات المنتج — العزل، مناعة التدقيق، قاعدة §7.4، بوابة GT1، منع تعديل RAW. وقيمتها **صفر حتى تُطبَّق على قاعدة حقيقية مرة واحدة**. هذا المسار يحقق ذلك بلا تثبيت على مستوى النظام.

## التثبيت

```bash
python3 -m pip install --user pgserver "psycopg[binary]" alembic sqlalchemy
```

`pgserver` يحزم PostgreSQL 16 وpgvector ويشغّلهما في مجلد المستخدم عبر مقبس Unix — بلا منفذ شبكي وبلا root.

## التشغيل

```python
import pgserver, pathlib
db = pgserver.get_server(str(pathlib.Path("pgdata").absolute()), cleanup_mode=None)
socket_dir = db.get_uri().split("host=")[1]
db.psql("CREATE DATABASE athera;")
db.psql("CREATE ROLE athera_owner LOGIN SUPERUSER PASSWORD 'athera_owner_pw';")
db.psql("ALTER DATABASE athera OWNER TO athera_owner;")
```

```bash
export DATABASE_MIGRATION_URL="postgresql+psycopg://athera_owner:athera_owner_pw@/athera?host=$SOCKET_DIR"
cd infra/db && python3 -m alembic upgrade head
```

## التحقق

```bash
export DATABASE_VERIFY_URL="postgresql+psycopg://athera_app:athera_app_pw@/athera?host=$SOCKET_DIR"
python3 scripts/verify_db_constraints.py
```

## حدود هذا المسار

| ما يعمل | ما لا يعمل |
|---|---|
| الترحيلات الثلاثة عشر صعودًا ونزولًا | اختبارات pytest التي تستورد نماذج SQLAlchemy — تحتاج Python 3.10+ |
| العزل بـRLS وكل قيود CHECK والمشغّلات | Temporal وMinIO والواجهة |
| `pgvector` | `pg_trgm` — غير محزَّم، والفهرس الثلاثي يُتخطى بتحذير |

`pg_trgm` متوفر في صورة `pgvector/pgvector:pg16` المستخدمة في `docker-compose`، فالإنتاج غير متأثر.

## ما أثبته أول تشغيل

| الفحص | النتيجة |
|---|---|
| الترحيلات 0001→0013 | نجحت — 96 جدولًا، 141 قيد CHECK، 7 مشغّلات |
| RLS إجبارية على كل جدول بـ`tenant_id` | 95 من 95 |
| دور التطبيق لا يتجاوز RLS | `rolbypassrls = false` |
| اثنتا عشرة عملية ممنوعة | مُنعت كلها |
| العزل بين مستأجرين + تزوير `tenant_id` | صفر تسريب |
| التراجع الكامل إلى الصفر | نظيف — لم يبقَ إلا `alembic_version` |

## الخادم يتوقف عند خروج العملية التي أقلعته

`pgserver.get_server()` يربط عمر الخادم بعمر العملية التي استدعته. تشغيله من `python -c` يعني أن الخادم يموت مع انتهاء الأمر، فتُتخطّى كل اختبارات القاعدة بعدها برسالة «PostgreSQL غير متاحة» — وهو تخطٍّ مطمئن يخفي أن شيئًا لم يُختبر.

لإقلاع مستقل عن أي عملية، تُستخدم ثنائيات PostgreSQL المضمَّنة في الحزمة مباشرةً:

```bash
PGBIN=$(python3 -c "import pgserver,pathlib;print(pathlib.Path(pgserver.__file__).parent/'pginstall'/'bin')")
SOCK="$HOME/Library/Caches/TemporaryItems/python_PostgresServer/<hash>"
mkdir -p "$SOCK"
"$PGBIN/pg_ctl" -D <pgdata> -l pg.log -o "-k '$SOCK' -h ''" start
"$PGBIN/pg_isready" -h "$SOCK"
```

`-h ''` يعطّل الإصغاء على TCP، فلا يتعارض مع أي PostgreSQL آخر ولا ينكشف على الشبكة. الاتصال عبر مقبس Unix وحده.

## اسم متغيّر البيئة

`Settings` في [`config.py`](../../apps/api/athera_api/config.py) بلا `env_prefix`، فالمتغيّر هو `DATABASE_URL` لا `ATHERA_DATABASE_URL`. تمرير الاسم الخاطئ لا يُنتج خطأ: تعود الإعدادات إلى `localhost:5432` الافتراضي، ويتخطّى كل اختبار قاعدة بيانات بهدوء.
