#!/usr/bin/env python3
"""إعادة ضبط كلمة حساب تحقّق اصطناعي | one-off synthetic verification reset.

**أداة لمرة واحدة، ولحساب واحد، ولا واجهة لها.**

حسابات التحقق الاصطناعية أُنشئت بكلمات وُلّدت في جلسة عمل ثم زالت معها. ولا
مسار منتَج لاستعادتها اليوم — ولا يُبنى مسارٌ عام لأجل حالة تشغيلية.

**وما لا تفعله هذه الأداة أهمّ مما تفعله:**

  · لا تلمس حسابًا حقيقيًّا: تُقصر على أسماء مستأجري التحقق المعروفة بالاسم،
    وتتوقف إن لم يطابق البحث **صفًّا واحدًا بالضبط**.
  · لا تكتب كلمة في SQL ولا في سجل ولا في طرفية: تُولَّد في الذاكرة، وتُهشَّم
    بآلية التطبيق نفسها، وتُكتب إلى ملفٍ بصلاحية 600 يقرؤه المشغّل ويمحوه.
  · لا تعدّل غير `password_hash` لذلك الصفّ.
  · لا تُضعف مصادقة، ولا تُنشئ حسابًا بديلًا للالتفاف على المشكلة.

    python scripts/reset_verification_password.py \
        --env-file .env.production.migration \
        --email <address> --tenant-slug <slug> --out /path/to/secret
"""
from __future__ import annotations

import argparse
import asyncio
import pathlib
import secrets
import string
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "api"))

# **أسماء مستأجري التحقق — بالاسم لا بالنمط.** نمطٌ يتّسع بمرور الوقت حتى
# يشمل مستأجرًا حقيقيًّا؛ وقائمةٌ مكتوبة لا تتّسع إلا بتغييرٍ يُراجَع.
SYNTHETIC_TENANTS = frozenset({"s5a-verify-a-922811", "s5a-verify-b-a1eb19"})


def load_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def app_url(env: dict[str, str]) -> str:
    """رابط **دور التطبيق** لا دور الترحيل.

    الترحيل يتجاوز عزل المستأجرين، وهذه العملية لا تحتاج تجاوزًا: صفٌّ واحد
    في `users`، وحدثُ تدقيق في مستأجره. فتُنفَّذ بأقلّ صلاحية تكفي، ويمرّ
    التدقيق بمساره القانوني تحت RLS.
    """
    import urllib.parse as up

    migration = env["DATABASE_MIGRATION_URL"]
    parsed = up.urlparse(migration.replace("postgresql+psycopg://", "postgresql://"))
    reference = (parsed.username or "").partition(".")[2]
    user = f"athera_app.{reference}" if reference else "athera_app"
    password = up.quote(env["ATHERA_DB_APP_PASSWORD"], safe="")
    return (f"postgresql+asyncpg://{user}:{password}"
            f"@{parsed.hostname}:{parsed.port}{parsed.path}")


def generate() -> str:
    """كلمة قوية بأبجدية آمنة في رابط — ولا تُطبع في أي مسار."""
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(secrets.choice(alphabet) for _ in range(32))


async def run(args) -> int:
    from athera_api.models.identity import Membership, Tenant, User
    from athera_api.security import hash_password
    from athera_api.services import audit
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.sql import text

    if args.tenant_slug not in SYNTHETIC_TENANTS:
        print(f"refusing: {args.tenant_slug!r} is not a known synthetic verification "
              "tenant. This tool exists for those alone.", file=sys.stderr)
        return 2

    env = load_env(pathlib.Path(args.env_file).expanduser())
    engine = create_async_engine(app_url(env), pool_pre_ping=True,
                                 connect_args={"statement_cache_size": 0})
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session, session.begin():
        tenant = (await session.execute(
            select(Tenant).where(Tenant.slug == args.tenant_slug))
        ).scalar_one_or_none()
        if tenant is None:
            print("refusing: no such tenant", file=sys.stderr)
            return 3
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant.id)})

        # **صفٌّ واحد بالضبط.** لا صفر (فلا شيء يُضبط) ولا أكثر (فلا
        # يُختار أحدهما) — والعضوية تُثبت أن الحساب لهذا المستأجر فعلًا،
        # فلا يُضبط حسابٌ يشبه اسمه ويسكن مكانًا آخر.
        matches = (await session.execute(
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(User.email == args.email.lower(),
                   Membership.tenant_id == tenant.id))
        ).scalars().unique().all()
        if len(matches) != 1:
            print(f"refusing: matched {len(matches)} users; expected exactly one",
                  file=sys.stderr)
            return 4

        user = matches[0]
        password = generate()
        user.password_hash = hash_password(password)
        await session.flush()

        await audit.record(
            session, tenant_id=tenant.id,
            action="maintenance.verification_password_reset",
            object_type="user", object_id=user.id, actor_user_id=user.id,
            # لا كلمة، ولا تجزئة، ولا طول — بصمةُ حدثٍ لا محتواه.
            state_after={"tenant_slug": args.tenant_slug, "scope": "synthetic"},
            reason="one-off operational reset of a synthetic verification account",
        )

    destination = pathlib.Path(args.out).expanduser()
    destination.write_text(password)
    destination.chmod(0o600)
    await engine.dispose()
    print(f"reset one synthetic verification account · secret → {destination} (0600)")
    print("read it, use it, then delete it. It was never printed or logged.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--out", required=True,
                        help="ملفٌ بصلاحية 600 تُكتب فيه الكلمة — لا تُطبع أبدًا")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
