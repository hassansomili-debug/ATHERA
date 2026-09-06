"""حرّاسُ مخطَّط الإصدار | Release schema gates for the production database.

**لماذا سكربتٌ لا أسطرٌ في المشغّل.** هذه الفحوص عشرةُ استعلامات، لكلٍّ
شرطُ نجاحٍ مكتوب، وبعضُها يقرأ `pg_roles` و`pg_class` و`pg_constraint`.
وكتابتُها متتاليةً داخل YAML تجعلها غيرَ مقروءة وغيرَ قابلةٍ للتشغيل خارج
المشغّل — فلا تُجرَّب إلا في الإنتاج، وذاك أسوأ مكانٍ لتجربة حارس.

**ولا يُطبع رابطُ الاتصال ولا أيُّ سرّ.** الرابط يُبنى في الذاكرة من
عنوانٍ ودورٍ وكلمةِ مرور تصل عبر البيئة، ويُستهلك ولا يُعرض؛ وما يُطبع هو
أسماءُ الفحوص ونتائجها وحدها. ورسائلُ الخطأ تصف الحال لا الاعتماد.

الأوضاع:

    --expect-version 0029      يفشل ما لم يكن `alembic_version` هو المذكور
    --expect-version 0030 --after-migration
                               ويطلب معه حرّاسَ ما بعد الترحيل كلَّها

والخروجُ بصفر يعني «كلُّ ما فُحص مرّ»، ولا يعني أكثر من ذلك.
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import quote, urlparse

#: الدورُ الذي يخدم الطلبات — **ولا يجوز أن يتجاوز عزل المستأجرين**.
RUNTIME_ROLE = "athera_app"

#: المنفذُ المباشر. **لا 6543.** مُجمِّع المعاملات لا يضمن جلسةً واحدة بين
#: العبارات، و`SET LOCAL` وقفلُ الاستشارة والترحيلُ نفسه تفترض ذلك.
DIRECT_PORT = 5432

#: **السائقُ المتزامن الوحيد المثبَّت في مسار الإصدار** — psycopg 3.
#: والمشغّل يثبّت `psycopg[binary]`، ولا يثبّت `psycopg2`.
SYNC_DRIVER = "psycopg"


def normalize_sync_pg_url(url: str, *, label: str) -> str:
    """يوحّد رابطَ اتصالٍ على psycopg 3 — **أو يرفضه بصراحة**.

    ## العطب الذي أسقط تشغيلة الإصدار الأولى

    `postgresql://` بلا سائقٍ مذكور تختار SQLAlchemy له **psycopg2** سائقًا
    افتراضيًّا؛ ومسارُ الإصدار يثبّت psycopg 3 وحده. فسقط الفحصُ بـ
    `ModuleNotFoundError: No module named 'psycopg2'` **قبل أن يتصل**، أي
    قبل أن يقرأ `alembic_version` أصلًا. والسرُّ كان مضبوطًا سليمًا؛ الذي
    انكسر هو أنّ الرابط الوارد يُمرَّر كما هو بينما الرابطُ المبنيّ داخليًّا
    يُكتب `postgresql+psycopg://` — **توحيدٌ لما نبنيه وتركٌ لما نُعطاه**،
    وتلك اللاتماثلية هي العطب.

    القواعد:

      • `postgresql://`         ← يُوحَّد إلى `postgresql+psycopg://`
      • `postgres://`           ← يُوحَّد كذلك
      • `postgresql+psycopg://` ← يبقى كما هو
      • أيُّ سائقٍ آخر — و`asyncpg` قبل غيره — **يُرفض ولا يُصحَّح بصمت**:
        `create_engine` متزامن، وتسليمُه سائقًا لا متزامنًا خطأٌ في النيّة
        لا في الإملاء، فيُقال لصاحبه بدل أن يُخمَّن مراده.

    **ولا يُطبع الرابط ولا كلمةُ المرور في أيّ رسالة خطأ** — يُذكر اسمُ
    المتغيّر واسمُ السائق وحدهما.
    """
    scheme, separator, remainder = url.partition("://")
    if not separator:
        raise SystemExit(f"refusing: {label} is not a database URL")
    base, _, driver = scheme.partition("+")
    if base not in ("postgresql", "postgres"):
        raise SystemExit(
            f"refusing: {label} is not a PostgreSQL URL (scheme {base!r})")
    if driver and driver != SYNC_DRIVER:
        raise SystemExit(
            f"refusing: {label} names the {driver!r} driver. These checks run on a "
            f"synchronous SQLAlchemy engine, which needs {SYNC_DRIVER!r} (psycopg 3); "
            "a bare postgresql:// URL is normalised to it. An async driver such as "
            "asyncpg cannot drive create_engine, and is never substituted silently."
        )
    return f"postgresql+{SYNC_DRIVER}://{remainder}"



def build_verify_url() -> str:
    """يبني رابطَ التحقّق بدور زمن التشغيل — **من عنوانٍ يصل مبنيًّا، أو من
    مكوّناته**. ولا يُشتقّ من رابط الترحيل: ذاك اعتمادٌ مميَّز لا يُمرَّر
    إلى فحصٍ لا يحتاجه.
    """
    explicit = os.environ.get("DATABASE_VERIFY_URL", "").strip()
    if explicit:
        # **التوحيدُ أوّلًا، ثمّ حارسُ المنفذ — والحارسُ باقٍ كما كان.**
        # التوحيدُ لا يمسّ إلا مقطعَ السائق، فالمضيفُ والمنفذ يصلان الحارسَ
        # كما وردا؛ ولا يُتخطّى ولا يُعاد ترتيبه.
        normalized = normalize_sync_pg_url(explicit, label="DATABASE_VERIFY_URL")
        try:
            port = urlparse(normalized).port
        except ValueError:
            # منفذٌ لا يُقرأ رقمًا: يُرفض ولا يُفترض 5432 — والفشلُ مغلق.
            raise SystemExit(
                "refusing: DATABASE_VERIFY_URL carries an unreadable port") from None
        if port and port != DIRECT_PORT:
            raise SystemExit(
                f"refusing: DATABASE_VERIFY_URL targets port {port}. "
                f"Release verification uses the direct port {DIRECT_PORT}; the "
                "transaction pooler does not guarantee one session across statements."
            )
        return normalized

    host = os.environ.get("PGHOST", "").strip()
    user = os.environ.get("PGUSER", "").strip()
    password = os.environ.get("PGPASSWORD", "")
    database = os.environ.get("PGDATABASE", "postgres").strip()
    if not (host and user and password):
        raise SystemExit(
            "no verification target: set DATABASE_VERIFY_URL, or PGHOST/PGUSER/"
            "PGPASSWORD. Values are read from the environment and never printed."
        )
    return (f"postgresql+psycopg://{quote(user)}:{quote(password)}@"
            f"{host}:{DIRECT_PORT}/{database}?sslmode=require")


# ═════════════════ الفحوص ═════════════════
#
# كلُّ فحصٍ: مفتاحٌ، وسؤالٌ بـSQL، ودالّةُ حكمٍ على الجواب، ونصُّ فشلٍ يقول
# ما الذي انكسر — لا «فشل الفحص رقم ٤».

ARCHIVE_COLUMNS = """
SELECT column_name, is_nullable FROM information_schema.columns
 WHERE table_name = 'theses' AND column_name IN ('archived_at', 'archived_by')
"""

PAIRED_NULL_CONSTRAINT = """
SELECT conname FROM pg_constraint
 WHERE conrelid = 'theses'::regclass AND conname = 'ck_theses_archive_is_named'
"""

LIVE_PAGE_INDEX = """
SELECT indexname FROM pg_indexes
 WHERE tablename = 'theses' AND indexname = 'ix_theses_tenant_live_page'
"""

FORCED_RLS = """
SELECT relname FROM pg_class
 WHERE relname IN ('theses', 'files', 'publication_opportunities')
   AND (relrowsecurity IS FALSE OR relforcerowsecurity IS FALSE)
"""

RUNTIME_ROLE_POSTURE = """
SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :role
"""

ALEMBIC_VERSION = "SELECT version_num FROM alembic_version"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-version", required=True,
                        help="the only alembic_version this run will accept")
    parser.add_argument("--after-migration", action="store_true",
                        help="also run the post-migration schema gates")
    args = parser.parse_args(argv)

    from sqlalchemy import create_engine, text  # noqa: PLC0415 — بعد فحص الوسائط

    engine = create_engine(build_verify_url(), pool_pre_ping=True)
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(f"{name}: {detail}")

    with engine.connect() as conn:
        versions = [row[0] for row in conn.execute(text(ALEMBIC_VERSION))]
        print(f"alembic_version rows: {len(versions)}")
        print(f"alembic_version     : {versions}")

        # **رأسٌ واحد لا اثنان.** صفّان في `alembic_version` يعنيان فرعين
        # مدموجين بلا حسم، و`upgrade head` حينها غامضة.
        check("exactly one alembic head recorded", len(versions) == 1,
              f"found {len(versions)} rows")
        check(f"alembic_version == {args.expect_version}",
              versions == [args.expect_version],
              f"found {versions}, expected ['{args.expect_version}']")

        if args.after_migration:
            columns = {row[0]: row[1] for row in conn.execute(text(ARCHIVE_COLUMNS))}
            check("theses.archived_at exists", "archived_at" in columns, "missing")
            check("theses.archived_by exists", "archived_by" in columns, "missing")
            # **يقبلان الفراغ** — وإلّا انكسر خادمُ v88 الذي لا يعرفهما.
            check("both archive columns are nullable",
                  all(value == "YES" for value in columns.values()),
                  f"nullability: {columns}")

            named = [row[0] for row in conn.execute(text(PAIRED_NULL_CONSTRAINT))]
            check("ck_theses_archive_is_named present", bool(named), "constraint missing")

            index = [row[0] for row in conn.execute(text(LIVE_PAGE_INDEX))]
            check("ix_theses_tenant_live_page present", bool(index), "index missing")

            unforced = [row[0] for row in conn.execute(text(FORCED_RLS))]
            check("RLS still ENABLE+FORCE on tenant tables", not unforced,
                  f"not forced: {unforced}")

            posture = conn.execute(text(RUNTIME_ROLE_POSTURE),
                                   {"role": RUNTIME_ROLE}).first()
            check(f"runtime role {RUNTIME_ROLE} exists", posture is not None, "no such role")
            if posture is not None:
                # **الدورُ الذي يخدم الطلبات لا يتجاوز RLS.** وهذا هو الحدّ
                # الذي يجعل عزلَ المستأجرين خاصّيّةَ قاعدةٍ لا نيّةَ شيفرة.
                check(f"{RUNTIME_ROLE} is not superuser", posture[0] is False,
                      f"rolsuper={posture[0]}")
                check(f"{RUNTIME_ROLE} has no BYPASSRLS", posture[1] is False,
                      f"rolbypassrls={posture[1]}")

    if failures:
        print("\nFAILED GATES:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\nall schema gates passed")
    return 0


if __name__ == "__main__":  # pragma: no cover - يحتاج قاعدةً حيّة
    sys.exit(run())
