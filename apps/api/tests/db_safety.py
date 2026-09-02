"""حارس قاعدة الاختبار | test-database production guard.

**عيبٌ وجده تحقيق الحادثة، لا احتياطٌ نظري.**

في 2026-08-31 بين 16:03 و16:08 نُفِّذت `pytest` على قاعدة الإنتاج. فبقي
فيها ١٠٤ مستأجر اختبار و١٠٤ مستخدم `@example.test` وتسعة ملفات وتسعة وأربعون
حدث تدقيق. ولم يُنبّه شيء: التجهيزات تكتب حيث يشير `DATABASE_URL`، ولا تسأل
أين تشير.

والسبب المباشر أن الإعدادات تقرأ `.env` **من مجلد العمل**. فمن جذر المستودع
يُقرأ `.env` الذي يحمل اعتماد الإنتاج، ومن `apps/api` لا يوجد ملف فتُستعمل
القيم الافتراضية المحلية. أي أن الفرق بين قاعدة تطوير وقاعدة إنتاج كان
**المجلد الذي انطلق منه الأمر**.

فهذا الحارس يسأل قبل أن تبدأ أي تجهيزة، ويفشل **مغلقًا**: ما لم يثبت أن
الهدف قاعدة اختبار معزولة، تُرفض التشغيلة كاملةً. ولا مفتاح تجاوز في
البيئة — إضافة مضيفٍ إلى القائمة تغييرٌ في المستودع يُراجَع، لا متغيّرُ
صدفةٍ يُصدَّر في لحظة عجلة.

ولا يطبع الحارس رابطًا ولا كلمة: أسبابه بالمضيف واسم القاعدة وحدهما.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

# مضيفات قواعد الاختبار المعروفة: التطوير المحلي وخدمات docker وCI.
ALLOWED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "::1", "", "postgres", "db", "athera-postgres",
})

# أسماء قواعد الاختبار المعروفة في هذا المستودع.
ALLOWED_DATABASES = frozenset({"athera", "athera_test", "athera_migration"})

# بصمات استضافة مدارة — قاعدة الإنتاج عليها.
MANAGED_HOST_MARKERS = ("supabase.com", "supabase.co", "supabase.in",
                        "pooler.", "rds.amazonaws.com", "neon.tech")

# اسم قاعدة Supabase الافتراضي — ليس اسم قاعدة اختبار بحال.
FORBIDDEN_DATABASES = frozenset({"postgres", "template1"})


@dataclass(frozen=True, slots=True)
class Target:
    """ما يمكن قوله عن الهدف بلا إفشاء اعتماد."""

    variable: str
    host: str
    database: str
    username: str

    def describe(self) -> str:
        return f"{self.variable} → {self.host or '(no host)'}/{self.database or '(no db)'}"


def parse(variable: str, url: str) -> Target | None:
    """يفكّك الرابط، ويعدّ ما لا يُفكَّك **هدفًا مرفوضًا** لا هدفًا غائبًا."""
    if not url:
        return None
    # `postgresql+asyncpg://` → `postgresql://` كي يفهمه urlparse.
    scheme, _, rest = url.partition("://")
    parsed = urlparse(f"{scheme.split('+')[0]}://{rest}")
    return Target(
        variable=variable,
        host=(parsed.hostname or "").lower(),
        database=unquote((parsed.path or "").lstrip("/")).lower(),
        username=unquote(parsed.username or ""),
    )


def reasons_to_refuse(target: Target) -> list[str]:
    """كل إشارة تُفحص وحدها — ولا واحدة تكفي لتبرئة الهدف."""
    found: list[str] = []

    for marker in MANAGED_HOST_MARKERS:
        if marker in target.host:
            found.append(f"managed-database host ({marker}) is not a test database")
            break

    if target.host not in ALLOWED_HOSTS:
        found.append(f"host {target.host!r} is not an allowed test host")

    if target.database in FORBIDDEN_DATABASES:
        found.append(f"database {target.database!r} is never a test database")
    elif target.database not in ALLOWED_DATABASES:
        found.append(f"database {target.database!r} is not an allowed test database")

    # `postgres.<project-ref>` هو شكل اسم المستخدم على مجمّع Supabase.
    if "." in target.username:
        found.append("username carries a managed-project reference")

    return found


def guard(env: dict[str, str] | None = None) -> None:
    """يرفع `RuntimeError` ما لم يثبت أن كل هدف قاعدةٍ هدفُ اختبار.

    ويُفحص `ATHERA_TEST_BYPASSRLS_URL` كذلك: دورٌ يتجاوز RLS موجَّهٌ إلى
    الإنتاج أسوأ من كل ما سبق.
    """
    env = os.environ if env is None else env
    problems: list[str] = []

    app_env = (env.get("APP_ENV") or "development").strip().lower()
    if app_env == "production":
        problems.append("APP_ENV=production — the test suite never runs in production")

    targets: list[tuple[str, str]] = [
        (variable, env.get(variable, ""))
        for variable in ("DATABASE_URL", "DATABASE_MIGRATION_URL",
                         "MIGRATION_DRILL_URL", "ATHERA_TEST_BYPASSRLS_URL")
    ]

    # **والرابط الذي يتصل به التطبيق فعلًا** — لا متغيّرات البيئة وحدها.
    #
    # وهذا هو بيت الداء: `Settings` تقرأ `.env` من مجلد العمل. فمن جذر
    # المستودع يُحمَّل ملفٌ فيه اعتماد الإنتاج بلا أن يظهر في البيئة، ويبقى
    # حارسٌ يقرأ `os.environ` وحده أعمى عنه تمامًا. فيُسأل المصدر نفسه الذي
    # يبني منه `db.py` محرّكه.
    if env is os.environ:
        try:
            from athera_api.config import get_settings

            targets.append(("settings.database_url", get_settings().database_url))
        except Exception:  # noqa: BLE001 — بيئة بلا تبعيات: لا قاعدة تُلمس أصلًا
            pass

    checked = 0
    seen: set[str] = set()
    for variable, raw in targets:
        if not raw or raw in seen:
            continue
        seen.add(raw)
        checked += 1
        target = parse(variable, raw)
        if target is None:
            problems.append(f"{variable} could not be parsed — refusing on principle")
            continue
        problems.extend(f"{target.describe()}: {why}"
                        for why in reasons_to_refuse(target))

    # لا هدف مصرَّح به يعني القيم الافتراضية في `config.py` — وهي محلية.
    # ويُذكر العدد ليُقرأ في CI أن الفحص جرى فعلًا.
    if problems:
        raise RuntimeError(
            "refusing to run the test suite against a non-test database "
            f"({checked} target(s) inspected):\n  - " + "\n  - ".join(problems)
            + "\n\nThe acceptance suite writes real rows: tenants, users, files and "
              "audit events. It ran against the ATHERA production database once "
              "(2026-08-31) and left 104 test tenants behind. Point DATABASE_URL at "
              "a local or CI database, or run pytest from apps/api so the "
              "production .env at the repository root is not loaded."
        )


__all__ = ["ALLOWED_DATABASES", "ALLOWED_HOSTS", "FORBIDDEN_DATABASES",
           "MANAGED_HOST_MARKERS", "Target", "guard", "parse", "reasons_to_refuse"]
