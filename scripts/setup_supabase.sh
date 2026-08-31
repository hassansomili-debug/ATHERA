#!/bin/zsh
# تهيئة قاعدة Supabase | Provision the Supabase database.
#
# لصقة واحدة تكفي: رابط Supabase يحمل المعرّف والمضيف والكلمة معًا.
# سؤال منفصل عن الكلمة كان يربك ويفشل — `read -rs` في زشّ يبتلع اللصق.
set -e
cd "$(dirname "$0")/.."
ROOT="$PWD"
# بايثون ٣.١٢ مع تبعيات الـAPI. يُتجاوز بـATHERA_PYTHON عند اختلاف البيئة.
PY="${ATHERA_PYTHON:-$ROOT/apps/api/.venv/bin/python}"
[[ -x "$PY" ]] || PY=python3

echo "Supabase → Connect → Transaction pooler → انسخ الرابط والصقه هنا."
echo "إن ظهرت الكلمة بين [ ] فاتركها؛ السكربت يزيل القوسين."
print -n "> "
read -r CONNSTR

"$PY" - "$CONNSTR" <<'PYEOF'
import pathlib, re, secrets, string, sys, urllib.parse

conn = sys.argv[1].strip()
m = re.match(r"postgres(?:ql)?://([^:]+):(.+)@([^:/]+):(\d+)/(\w+)", conn)
if not m:
    raise SystemExit("✗ رابط غير مفهوم. تأكّد أنك نسخت السطر كاملًا.")

user, pw, host, _port, db = m.groups()
pw = pw.strip()
# لوحة Supabase تضع الكلمة بين [ ] — تُزال، ولا تُعامل جزءًا منها.
if pw.startswith("[") and pw.endswith("]"):
    pw = pw[1:-1]

if pw.upper() in ("YOUR-PASSWORD", "YOUR_PASSWORD") or len(pw) < 8:
    raise SystemExit(
        f"✗ الكلمة غير صالحة (الطول {len(pw)}). "
        "انسخ الرابط بعد إظهار الكلمة الحقيقية في لوحة Supabase."
    )

ref = user.split(".", 1)[1] if "." in user else "?"
# الترميز إلزامي: `@` في الكلمة تكسر تحليل الرابط بصمت.
q = urllib.parse.quote(pw, safe="")

env = pathlib.Path(".env")
old = env.read_text(encoding="utf-8") if env.exists() else ""
def keep(key, default):
    hit = re.search(rf"^{key}=(.*)$", old, re.M)
    return hit.group(1) if hit and hit.group(1).strip() else default

alnum = string.ascii_letters + string.digits
app_pw = keep("ATHERA_DB_APP_PASSWORD",
              "".join(secrets.choice(alnum) for _ in range(32)))
jwt = keep("JWT_SECRET", secrets.token_urlsafe(48))

env.write_text(f"""# ATHERA — بيئة محلية. مستثنى من git.
APP_ENV=production
APP_DEFAULT_LOCALE=ar
APP_SUPPORTED_LOCALES=ar,en

# 5432 = وضع الجلسة (الترحيلات) · 6543 = وضع المعاملة (الـAPI)
DATABASE_MIGRATION_URL=postgresql+psycopg://{user}:{q}@{host}:5432/{db}
DATABASE_URL=postgresql+asyncpg://{user}:{q}@{host}:6543/{db}
ATHERA_DB_APP_PASSWORD={app_pw}

JWT_SECRET={jwt}
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=1209600
MFA_REQUIRED_FOR_ADMIN_ROLES=true

CORS_ALLOWED_ORIGINS=https://athera-bay.vercel.app

MODEL_PROVIDER=null
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
MODEL_EXTERNAL_SEND_MAX_CLASSIFICATION=C1
LITERATURE_REGISTRY=offline
TEMPORAL_ENABLED=0

S3_ENDPOINT_URL=
S3_REGION=ap-south-1
S3_BUCKET=athera
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PRESIGN_TTL_SECONDS=300
""", encoding="utf-8")
print(f"✓ المشروع {ref} · المضيف {host} · طول الكلمة {len(pw)}")
PYEOF

unset CONNSTR
set -a; source "$ROOT/.env"; set +a
export MIGRATION_URL="$DATABASE_MIGRATION_URL"

hide() { sed 's|postgres[a-z+]*://[^ ]*|<URL>|g'; }

echo "═══ ١. الاتصال ═══"
"$PY" -c "
import os, sqlalchemy as sa
with sa.create_engine(os.environ['DATABASE_MIGRATION_URL']).connect() as c:
    print('✓', c.execute(sa.text('select version()')).scalar_one().split(',')[0])
" 2>&1 | hide | tail -3

echo "═══ ٢. الترحيلات ═══"
cd "$ROOT/infra/db"
"$PY" -m alembic upgrade head 2>&1 | hide | grep -E "Running upgrade|ERROR" | tail -20
cd "$ROOT"

echo "═══ ٣. الحصيلة ═══"
"$PY" -c "
import os, sqlalchemy as sa
with sa.create_engine(os.environ['DATABASE_MIGRATION_URL']).connect() as c:
    q = lambda s: c.execute(sa.text(s)).scalar_one()
    print('الجداول:', q(\"select count(*) from information_schema.tables where table_schema='public'\"))
    print('آخر ترحيل:', q('select version_num from alembic_version'))
    print('RLS مفعّلة على:', q(\"select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname='public' and c.relrowsecurity\"), 'جدولًا')
" 2>&1 | hide

echo ""
echo "✓ تمت التهيئة."
