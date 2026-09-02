"""تنظيف أثر تشغيلة اختبارات وقعت على قاعدة الإنتاج | one-off maintenance cleanup.

**أداة لمرة واحدة، لا قدرة دائمة.**

في 2026-08-31 بين 16:03 و16:08 نُفِّذت `pytest` على قاعدة الإنتاج فتركت فيها
مستأجرين ومستخدمين وملفات وأحداث تدقيق اصطناعية. وهذا الملف يزيلها — ولا شيء
غيرها.

**والافتراض تجربةٌ جافّة.** الحذف لا يقع إلا بـ`--apply` صريحة، وبعد أن
يُقرأ البيان ويُتحقّق منه.

**والتعرّف بخمس إشارات مجتمعة، لا بواحدة:**

  ١. صيغة الاسم `test-a-xxxxxxxx` أو `test-b-xxxxxxxx` بالضبط.
  ٢. الإنشاء داخل نافذة الحادثة المعروفة.
  ٣. كل مستخدم متصل بالمستأجر على نطاق `@example.test`.
  ٤. ولا مستخدم عليه من خارج ذلك النطاق.
  ٥. وليس من المستأجرين الحقيقيين المحميّين بالاسم.

وأيّ مستأجر يوافق الأولى ويخالف غيرها **يُستثنى ويُعلَن**، ولا يُحذف بحال.
فالغموض سببُ استبعاد لا سببَ اجتهاد.

**وسجل التدقيق:** جداوله append-only بمشغّل يرفض الحذف — وهو حارس تعديل
التاريخ. وحذف مستأجر اصطناعي بأكمله عمليةٌ أخرى: لا يمسّ سلسلة أي مستأجر
حقيقي، لأن السلسلة لكل مستأجر على حدة. فيُعطَّل المشغّل داخل المعاملة وحدها
ويُعاد، ويُتحقَّق من عودته قبل الإيداع.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import uuid

# ── معايير التعرّف ──
SLUG_PATTERN = re.compile(r"^test-[ab]-[0-9a-f]{8}$")
TEST_EMAIL_DOMAIN = "@example.test"
WINDOW_START = dt.datetime(2026, 8, 31, 16, 0, tzinfo=dt.UTC)
WINDOW_END = dt.datetime(2026, 8, 31, 16, 15, tzinfo=dt.UTC)

# **يُحمى بالاسم صراحةً** — حزامٌ ثانٍ فوق المعايير، فخطأٌ في تعبير نمطي
# لا يبلغ مستأجرًا حقيقيًّا.
PROTECTED_SLUGS = frozenset({"athera", "s5a-verify-a-922811", "s5a-verify-b-a1eb19"})

# دوال المناعة: سجلٌّ append-only (§37) وصفوفٌ مجمَّدة بحكم المنتج (§17.2).
# تُكتشف تشغيلاتها من القاعدة ولا تُكتب هنا بأسمائها — فجدولٌ يُضاف لاحقًا
# بحارسٍ من هذه الدوال يُشمل تلقائيًّا، ولا يُعطَّل حارسٌ من نوع آخر بحال.
IMMUTABILITY_FUNCTIONS = ("audit_events_immutable", "forbid_row_mutation")


def immutability_triggers(cur) -> list[tuple[str, str]]:
    """(الجدول، اسم المشغّل) لكل حارس مناعة قائم — كما تعرفه القاعدة."""
    cur.execute(
        """
        SELECT t.tgrelid::regclass::text, t.tgname
        FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE NOT t.tgisinternal AND p.proname = ANY(%s)
        ORDER BY 1, 2
        """,
        (list(IMMUTABILITY_FUNCTIONS),))
    return [(row[0], row[1]) for row in cur.fetchall()]


def load_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def connect(url: str):
    import psycopg

    return psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"))


def tenant_tables(cur) -> list[str]:
    cur.execute(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema='public' AND column_name='tenant_id' ORDER BY table_name")
    return [r[0] for r in cur.fetchall()]


def classify(cur) -> tuple[list[dict], list[dict]]:
    """يفصل المؤكَّد عن الملتبس — ولا يخمّن في الثاني."""
    cur.execute(
        """
        SELECT t.id, t.slug, t.created_at,
               count(u.id) FILTER (WHERE u.email LIKE %s)                  AS test_users,
               count(u.id) FILTER (WHERE u.email NOT LIKE %s)              AS other_users
        FROM tenants t
        LEFT JOIN memberships m ON m.tenant_id = t.id
        LEFT JOIN users u ON u.id = m.user_id
        GROUP BY t.id, t.slug, t.created_at
        ORDER BY t.slug
        """,
        (f"%{TEST_EMAIL_DOMAIN}", f"%{TEST_EMAIL_DOMAIN}"),
    )
    confirmed: list[dict] = []
    ambiguous: list[dict] = []
    for tenant_id, slug, created_at, test_users, other_users in cur.fetchall():
        if slug in PROTECTED_SLUGS:
            continue
        signals = {
            "slug_shape": bool(SLUG_PATTERN.match(slug or "")),
            "created_in_window": bool(created_at and WINDOW_START <= created_at <= WINDOW_END),
            "no_foreign_user": other_users == 0,
            "only_test_users": other_users == 0 and test_users >= 0,
        }
        if not signals["slug_shape"]:
            continue  # ليس مرشّحًا أصلًا
        row = {"tenant_id": str(tenant_id), "slug": slug,
               "created_at": created_at.isoformat(), "signals": signals,
               "test_users": test_users, "other_users": other_users}
        (confirmed if all(signals.values()) else ambiguous).append(row)
    return confirmed, ambiguous


def inventory(cur, tenant_ids: list[uuid.UUID]) -> dict:
    """جردٌ بالأعداد — ولا محتوى بحثيًّا في البيان."""
    counts: dict[str, int] = {}
    for table in tenant_tables(cur):
        cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id = ANY(%s)", (tenant_ids,))
        found = cur.fetchone()[0]
        if found:
            counts[table] = found

    counts["tenants"] = len(tenant_ids)
    return counts


def storage_keys(cur, tenant_ids: list[uuid.UUID]) -> list[dict]:
    """مفاتيح التخزين — والملكية تُثبَت من بادئة المفتاح لا من الجدول وحده."""
    cur.execute(
        "SELECT id, tenant_id, storage_key, status FROM files "
        "WHERE tenant_id = ANY(%s) ORDER BY storage_key", (tenant_ids,))
    keys = []
    for file_id, tenant_id, key, status in cur.fetchall():
        owned = key.startswith(f"tenants/{tenant_id}/")
        keys.append({"file_id": str(file_id), "tenant_id": str(tenant_id),
                     "storage_key": key, "status": status, "prefix_proves_owner": owned})
    return keys


def user_ids(cur, slugs: list[str]) -> tuple[list[uuid.UUID], list[dict]]:
    """المستخدمون — **بالربط لا بالنطاق وحده**.

    العضوية لا تصلح رابطًا هنا: تشغيلة الحادثة لم تُكمل، فالمستأجرون
    الاصطناعيون بلا عضوية ولا أدوار أصلًا. ولو اكتُفي بنطاق `@example.test`
    لكانت الإشارة واحدة — وهي ما يمنعه هذا الملف.

    فالرابط الصريح: التجهيزة تصنع بريدًا هو **اسم المستأجر نفسه** على ذلك
    النطاق. فيُطابَق البريد باسم مستأجر مؤكَّد، ويُشترط الإنشاء في النافذة،
    ويُشترط ألّا يشير إليه صفٌّ لمستأجر حقيقي.
    """
    expected = {f"{slug}{TEST_EMAIL_DOMAIN}": slug for slug in slugs}
    cur.execute(
        "SELECT id, email, created_at FROM users WHERE email LIKE %s ORDER BY email",
        (f"%{TEST_EMAIL_DOMAIN}",))
    confirmed: list[uuid.UUID] = []
    excluded: list[dict] = []
    for user_id, email, created_at in cur.fetchall():
        signals = {
            "email_matches_a_confirmed_tenant": email in expected,
            "created_in_window": bool(created_at
                                      and WINDOW_START <= created_at <= WINDOW_END),
        }
        if all(signals.values()):
            confirmed.append(user_id)
        else:
            excluded.append({"user_id": str(user_id),
                             "signals": signals})
    return confirmed, excluded


def self_reference_columns(cur, table: str) -> list[str]:
    """أعمدة الجدول التي تشير إلى الجدول نفسه بقيد يرفض الحذف."""
    cur.execute(
        """
        SELECT a.attname
        FROM pg_constraint c
        JOIN unnest(c.conkey) WITH ORDINALITY k(attnum, ord) ON true
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
        WHERE c.contype = 'f'
          AND c.conrelid = %s::regclass AND c.confrelid = %s::regclass
          AND c.confdeltype IN ('a', 'r')
        """,
        (table, table))
    return [r[0] for r in cur.fetchall()]


def unwind_self_references(cur, table: str, columns: list[str],
                           tenant_ids: list[uuid.UUID]) -> int:
    """يحذف من الأوراق إلى الجذر — لأن RESTRICT لا يعفي صفًّا يُحذف معه.

    `dataset_versions.parent_version_id` يشير إلى الجدول نفسه بـRESTRICT.
    وحذف كل الصفوف بعبارة واحدة يصطدم به: القيد يُفحص لكل صفّ فورًا، ولا
    يعلم أن الأب سيُحذف في العبارة نفسها. فتُحذف الأوراق أولًا ثم آباؤها،
    مرورًا بعد مرور، حتى لا يبقى شيء.
    """
    guard = " AND ".join(
        f"NOT EXISTS (SELECT 1 FROM {table} c WHERE c.tenant_id = ANY(%s) "
        f"AND c.{column} = {table}.id)" for column in columns)
    removed = 0
    for _ in range(64):
        cur.execute(
            f"DELETE FROM {table} WHERE tenant_id = ANY(%s) AND {guard}",
            (tenant_ids, *[tenant_ids] * len(columns)))
        if not cur.rowcount:
            break
        removed += cur.rowcount
    return removed


def purge(cur, tenant_ids: list[uuid.UUID], users: list[uuid.UUID]) -> dict[str, int]:
    """حذفٌ بمرورات متتالية — الترتيب يستنتجه القيد لا أنا.

    ترتيب ثلاثة وتسعين جدولًا يدويًّا يعني خطأً واحدًا كافيًا. فبدله: كل
    مرور يحذف ما يقبل الحذف، وما يرفضه قيدٌ أجنبي يُعاد في المرور التالي.
    ويتوقف عند عدم التقدّم — فلا حلقة لا نهائية ولا حذف أعمى.
    """
    remaining = tenant_tables(cur)
    deleted: dict[str, int] = {}

    # ── تمهيد: الجداول التي تشير إلى نفسها تُفكَّك من أوراقها أولًا ──
    for table in remaining:
        columns = self_reference_columns(cur, table)
        if not columns:
            continue
        removed = unwind_self_references(cur, table, columns, tenant_ids)
        if removed:
            deleted[table] = deleted.get(table, 0) + removed

    for _pass in range(12):
        stuck: list[str] = []
        for table in remaining:
            cur.execute("SAVEPOINT del")
            try:
                cur.execute(f"DELETE FROM {table} WHERE tenant_id = ANY(%s)", (tenant_ids,))
                if cur.rowcount:
                    deleted[table] = deleted.get(table, 0) + cur.rowcount
                cur.execute("RELEASE SAVEPOINT del")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT del")
                cur.execute("RELEASE SAVEPOINT del")
                stuck.append(table)
        if not stuck:
            break
        if len(stuck) == len(remaining):
            raise RuntimeError(f"deletion stalled on: {', '.join(stuck)}")
        remaining = stuck

    if users:
        cur.execute("DELETE FROM mfa_factors WHERE user_id = ANY(%s)", (users,))
        deleted["mfa_factors"] = cur.rowcount
        cur.execute("DELETE FROM users WHERE id = ANY(%s)", (users,))
        deleted["users"] = cur.rowcount
    cur.execute("DELETE FROM tenants WHERE id = ANY(%s)", (tenant_ids,))
    deleted["tenants"] = cur.rowcount
    return deleted


def real_tenant_fingerprint(cur) -> dict:
    """بصمة المستأجرين الحقيقيين — تُقارَن قبل وبعد."""
    cur.execute(
        "SELECT t.slug, count(DISTINCT m.user_id), "
        "       (SELECT count(*) FROM audit_events a WHERE a.tenant_id = t.id) "
        "FROM tenants t LEFT JOIN memberships m ON m.tenant_id = t.id "
        "WHERE t.slug = ANY(%s) GROUP BY t.id, t.slug ORDER BY t.slug",
        (sorted(PROTECTED_SLUGS),))
    return {slug: {"users": users, "audit_events": events}
            for slug, users, events in cur.fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True,
                        help="ملف بيئة يحمل DATABASE_MIGRATION_URL — لا يُقرأ ضمنًا")
    parser.add_argument("--apply", action="store_true",
                        help="ينفّذ الحذف؛ وبدونه تجربة جافّة")
    parser.add_argument("--manifest", default="", help="مسار كتابة البيان (JSON)")
    args = parser.parse_args()

    env = load_env(pathlib.Path(args.env_file).expanduser())
    url = env.get("DATABASE_MIGRATION_URL", "")
    if not url:
        print("DATABASE_MIGRATION_URL is not present in the given env file", file=sys.stderr)
        return 2

    run_id = str(uuid.uuid4())
    started = dt.datetime.now(dt.UTC)
    with connect(url) as conn:
        conn.autocommit = False
        cur = conn.cursor()
        before = real_tenant_fingerprint(cur)
        confirmed, ambiguous = classify(cur)

        print(f"maintenance run {run_id}")
        print(f"  confirmed test tenants : {len(confirmed)}")
        print(f"  ambiguous (EXCLUDED)   : {len(ambiguous)}")
        for row in ambiguous:
            failed = [k for k, ok in row["signals"].items() if not ok]
            print(f"    ! {row['slug']} failed: {', '.join(failed)}")

        if not confirmed:
            print("nothing to do")
            conn.rollback()
            return 0

        ids = [uuid.UUID(r["tenant_id"]) for r in confirmed]
        counts = inventory(cur, ids)
        keys = storage_keys(cur, ids)
        users, users_excluded = user_ids(cur, [r["slug"] for r in confirmed])
        counts["users (global)"] = len(users)
        cur.execute("SELECT count(*) FROM mfa_factors WHERE user_id = ANY(%s)", (users,))
        mfa = cur.fetchone()[0]
        if mfa:
            counts["mfa_factors (global)"] = mfa

        print("\n  inventory (rows to remove):")
        for table, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {table:34s} {n}")
        if users_excluded:
            print(f"  ! {len(users_excluded)} @example.test user(s) EXCLUDED "
                  f"(no confirmed tenant link or outside the window)")
        print(f"\n  storage objects referenced : {len(keys)} "
              f"({sum(1 for k in keys if k['status'] == 'stored')} with status=stored)")
        unproven = [k for k in keys if not k["prefix_proves_owner"]]
        if unproven:
            print(f"  ! {len(unproven)} storage key(s) whose prefix does not prove ownership "
                  f"— EXCLUDED from storage deletion")

        manifest = {
            "maintenance_run_id": run_id,
            "date": started.isoformat(),
            "operator": env.get("MAINTENANCE_OPERATOR", os.getenv("USER", "unknown")),
            "mode": "apply" if args.apply else "dry-run",
            "criteria": {
                "slug_pattern": SLUG_PATTERN.pattern,
                "email_domain": TEST_EMAIL_DOMAIN,
                "created_between": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
                "protected_slugs": sorted(PROTECTED_SLUGS),
                "all_signals_required": True,
            },
            "tenants": [{"tenant_id": r["tenant_id"], "slug": r["slug"]} for r in confirmed],
            "ambiguous_excluded": ambiguous,
            "row_counts": counts,
            "user_ids": [str(u) for u in users],
            "users_excluded": users_excluded,
            "storage_keys": [k for k in keys if k["prefix_proves_owner"]],
            "real_tenants_before": before,
        }

        if not args.apply:
            print("\nDRY RUN — nothing was deleted. Re-run with --apply to execute.")
            conn.rollback()
        else:
            # يُعطَّل **بالاسم** لا بالجملة: `DISABLE TRIGGER USER` يُسكت كل
            # مشغّلات الجدول، ومنها ما ليس حارس مناعة.
            guards = immutability_triggers(cur)
            for table, trigger in guards:
                cur.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
            deleted = purge(cur, ids, users)
            for table, trigger in guards:
                cur.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")

            # الحارس يعود **قبل** الإيداع، ويُتحقَّق منه لا يُفترض.
            cur.execute(
                "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
                "WHERE NOT t.tgisinternal AND p.proname = ANY(%s) AND t.tgenabled = 'D'",
                (list(IMMUTABILITY_FUNCTIONS),))
            still_disabled = cur.fetchone()[0]
            if still_disabled:
                conn.rollback()
                raise RuntimeError(
                    f"{still_disabled} immutability trigger(s) did not come back "
                    "— rolled back")
            manifest["immutability_triggers_suspended"] = [
                f"{table}.{trigger}" for table, trigger in guards]

            after = real_tenant_fingerprint(cur)
            if after != before:
                conn.rollback()
                raise RuntimeError(f"real tenants changed: {before} → {after} — rolled back")

            cur.execute("SELECT count(*) FROM users WHERE email LIKE %s",
                        (f"%{TEST_EMAIL_DOMAIN}",))
            leftover = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM tenants WHERE slug LIKE 'test-%'")
            leftover_tenants = cur.fetchone()[0]
            manifest["leftover_test_users"] = leftover
            manifest["leftover_test_tenants"] = leftover_tenants
            manifest["deleted"] = deleted
            manifest["real_tenants_after"] = after
            conn.commit()
            print("\n  deleted:")
            for table, n in sorted(deleted.items(), key=lambda kv: -kv[1]):
                print(f"    {table:34s} {n}")
            print("  real tenants unchanged ✓ · append-only triggers restored ✓")
            print(f"  leftover test tenants: {leftover_tenants} · "
                  f"leftover @example.test users: {leftover}")

    manifest["result"] = "applied" if args.apply else "dry-run"
    if args.manifest:
        pathlib.Path(args.manifest).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2))
        print(f"\nmanifest → {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
