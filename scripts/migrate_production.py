#!/usr/bin/env python3
"""ترحيل قاعدة الإنتاج | the one explicit production migration path.

**لماذا أمرٌ مستقل ولا `alembic upgrade head` مباشرة.**

اعتماد الترحيل مميَّز: يملك الجداول، ويُنشئ الأدوار، ويتجاوز عزل
المستأجرين. وكان يعيش في `.env` العام على جهاز المطوّر — فيُحمَّل ضمنًا مع
كل أمر يُشغَّل من جذر المستودع. وهكذا بلغت تشغيلة `pytest` قاعدة الإنتاج
وتركت فيها مئة وأربعة مستأجرين اصطناعيين.

فالاعتماد الآن في ملفٍ لا يقرؤه شيء تلقائيًّا، ولا يُحمَّل إلا هنا، وبنيّة
موجبة: يكتب المشغّل **مرجع المشروع الإنتاجي بنفسه**. ولا يُكتب سهوًا.

وثلاثة فحوص قبل أي DDL:

  ١. الهدف إنتاجيٌّ فعلًا — فأمر الإنتاج لا يُشغَّل على قاعدة تطوير سهوًا.
  ٢. المرجع المكتوب يطابق الهدف — فلا يُرحَّل مشروعٌ بدل آخر.
  ٣. الدور ليس دور زمن التشغيل — فاعتماد الترحيل لا يصير `DATABASE_URL`.

    python scripts/migrate_production.py --confirm <project-ref>
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ENV = REPO / ".env.production.migration"
RUNTIME_ROLE = "athera_app"

sys.path.insert(0, str(REPO / "apps" / "api"))
from athera_api.dbtarget import parse as parse_target  # noqa: E402


def load_env(path: pathlib.Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(
            f"missing {path.name}. Production migration credentials live only in that "
            "file and are never loaded by app startup, pytest, or ordinary commands."
        )
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True,
                        help="مرجع المشروع الإنتاجي — يُكتب بالكامل ويُطابَق بالهدف")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--command", default="upgrade head",
                        help="أمر alembic (الافتراضي: upgrade head)")
    args = parser.parse_args()

    env_path = pathlib.Path(args.env_file).expanduser()
    env = load_env(env_path)
    url = env.get("DATABASE_MIGRATION_URL", "")
    if not url:
        raise SystemExit(f"{env_path.name} carries no DATABASE_MIGRATION_URL")

    target = parse_target(url)
    if target is None:
        raise SystemExit("DATABASE_MIGRATION_URL could not be parsed — refusing")

    # ١ — الهدف إنتاجيٌّ فعلًا.
    if not target.looks_managed:
        raise SystemExit(
            f"refusing: {target.describe()} is a local database. This command exists "
            "for production only; use `make migrate` for local development."
        )

    # ٢ — المرجع المكتوب يطابق الهدف.
    reference = target.username.partition(".")[2] or target.host
    if args.confirm != reference:
        raise SystemExit(
            "refusing: --confirm does not match the target's project reference. "
            "Type the production project reference exactly; this step exists so a "
            "production migration is never a typo."
        )

    # ٣ — الدور ليس دور زمن التشغيل.
    if target.username.partition(".")[0] == RUNTIME_ROLE:
        raise SystemExit(
            f"refusing: the migration URL uses the runtime role {RUNTIME_ROLE!r}. "
            "Runtime and migration credentials stay separate — that separation is "
            "what keeps a BYPASSRLS role out of DATABASE_URL."
        )

    print(f"target      : {target.describe()}")
    print(f"alembic     : {args.command}")

    # `sys.executable -m alembic` لا `alembic` من المسار: الأمر يعمل بمفسّر
    # البيئة التي شُغِّل بها، فلا يعتمد على ما صادف أن يكون في PATH.
    shell_env = {**env, "PATH": __import__("os").environ.get("PATH", "")}
    base = [sys.executable, "-m", "alembic", "-c", "alembic.ini"]
    cwd = REPO / "infra" / "db"

    before = subprocess.run([*base, "current"], cwd=cwd, env=shell_env,
                            capture_output=True, text=True)
    print(f"revision before: {before.stdout.strip().splitlines()[-1:] or ['(none)']}")

    result = subprocess.run([*base, *args.command.split()], cwd=cwd, env=shell_env)
    if result.returncode:
        return result.returncode

    after = subprocess.run([*base, "current"], cwd=cwd, env=shell_env,
                           capture_output=True, text=True)
    print(f"revision after : {after.stdout.strip().splitlines()[-1:] or ['(none)']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
