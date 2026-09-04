#!/usr/bin/env python3
"""تقريرُ البيانات الاصطناعية — **قراءةٌ فقط، ولا حذف بحال**.

    python scripts/synthetic_data_report.py --confirm <project-ref>

لا `--apply` في هذا الملفّ ولا نيّةَ إضافتها. الحذفُ من الإنتاج قرارُ
المالك، وله مسارُه المُدقَّق. وهذا يجيب سؤالًا واحدًا: **ما الذي تراكم،
ومن أنشأه، ومنذ متى؟**

وسببُ وجوده أنّ رحلةَ القبول تسجّل حسابًا على الإنتاج في كل تشغيلةٍ على
`main`. فهذا تراكمٌ **بالتصميم** لا بحادثة، ومن لم يقسه لم يعرف متى صار
عبئًا.

والتصنيفُ من `athera_api.synthetic` وحده — لا نسخةَ ثانية من البادئات هنا.
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "api"))
sys.path.insert(0, str(REPO / "scripts"))


def main() -> int:
    import psycopg
    from athera_api.synthetic import SYNTHETIC_PREFIXES, classify
    from migrate_production import DEFAULT_ENV, load_env

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True,
                        help="مرجعُ المشروع — تأكيدُ أنّك تقصد هذا الهدف")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    args = parser.parse_args()

    env = load_env(pathlib.Path(args.env_file).expanduser())
    url = env.get("DATABASE_MIGRATION_URL", "")
    if args.confirm not in url:
        raise SystemExit("refusing: --confirm does not match the target")
    url = url.replace("postgresql+psycopg://", "postgresql://")

    with psycopg.connect(url, connect_timeout=30) as conn, conn.cursor() as cur:
        cur.execute("SELECT email, created_at FROM users ORDER BY created_at")
        rows = cur.fetchall()

        tally: Counter[str] = Counter()
        oldest: dict[str, object] = {}
        newest: dict[str, object] = {}
        for email, created in rows:
            kind = classify(email)
            tally[kind] += 1
            oldest.setdefault(kind, created)
            newest[kind] = created

        print(f"users total: {len(rows)}\n")
        print(f"{'class':18} {'count':>6}   {'first':<28} {'last'}")
        for kind in ("real", "synthetic", "review_candidate", "legacy_incident"):
            if tally[kind]:
                print(f"{kind:18} {tally[kind]:>6}   "
                      f"{oldest[kind]!s:<28} {newest[kind]}")

        # **وأيُّ بادئةٍ تتراكم أسرع؟** الرقمُ وحده لا يقول من يُنتجه.
        print("\nby marker:")
        for prefix in SYNTHETIC_PREFIXES:
            n = sum(1 for email, _ in rows
                    if classify(email) == "synthetic"
                    and email.lower().startswith(prefix + "-"))
            print(f"  {prefix:20} {n:>5}   — {SYNTHETIC_PREFIXES[prefix]}")

        cur.execute("SELECT count(*) FROM research_projects")
        print(f"\nresearch_projects total: {cur.fetchone()[0]}")

    print("\n**تقريرٌ فقط.** لا يحذف هذا الملفّ شيئًا، ولا يملك ذلك.")
    print("والحذفُ قرارُ المالك — ولأثر حادثة 2026-08-31 أداتُه الخاصّة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
