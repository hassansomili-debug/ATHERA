"""حراسة إعداد النشر | Deployment posture guards (§36، §38.6.8، ADR-0002).

الإصلاحات التي يحرسها هذا الملف كلها من نوع واحد: **تعمل محليًّا وتنكسر أو
تُخترق في الإنتاج**. لا يكشفها اختبار وظيفي لأن الوظيفة سليمة في الحالتين.
"""
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).parents[3]


def test_no_password_literal_survives_in_migrations():
    """كلمة مرور في المستودع تبقى في تاريخ git حتى بعد تغييرها.

    الفحص على كل الترحيلات لا على واحد: القاعدة تُنتهك بإضافة ترحيل جديد
    يكرر النمط، لا بتعديل القديم.
    """
    pattern = re.compile(r"PASSWORD\s+'(?!\{)[^']+'", re.IGNORECASE)
    offenders = []
    for path in (REPO / "infra/db/migrations/versions").glob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{line_no}")
    assert not offenders, f"كلمة مرور حرفية في ترحيل: {offenders}"


def test_migration_refuses_a_default_password_outside_development(monkeypatch):
    """الفشل هنا أرخص من قاعدة إنتاج بكلمة معروفة."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "m0001", REPO / "infra/db/migrations/versions/0001_extensions_and_roles.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.delenv("ATHERA_DB_APP_PASSWORD", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    assert module._app_password() == "athera_app_pw"

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        module._app_password()

    monkeypatch.setenv("ATHERA_DB_APP_PASSWORD", "a-real-secret")
    assert module._app_password() == "a-real-secret"


def test_application_role_never_gains_bypassrls():
    """ADR-0002 — الدور بلا BYPASSRLS هو ما يجعل خطأ الكود غير كافٍ للتسريب."""
    source = (REPO / "infra/db/migrations/versions/0001_extensions_and_roles.py").read_text(
        encoding="utf-8"
    )
    assert "NOBYPASSRLS" in source
    assert not re.search(r"\bathera_app\b[^;]*\bBYPASSRLS\b", source.replace("NOBYPASSRLS", ""))


@pytest.mark.parametrize("url,expected_disabled", [
    ("postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:6543/postgres", True),
    ("postgresql+asyncpg://u:p@db.ref.supabase.co:5432/postgres", False),
    ("postgresql+asyncpg://u:p@localhost:5432/athera", False),
    ("postgresql+psycopg://u:p@host:6543/db", False),
])
def test_prepared_statement_cache_is_disabled_only_behind_a_pooler(url, expected_disabled):
    """`DuplicatePreparedStatementError` يظهر تحت الحمل فقط — أي في الإنتاج.

    والاتجاه المعاكس مقصود: تعطيلها دائمًا يكلّف أداءً على اتصال مباشر بلا سبب.
    """
    from athera_api import db

    original = db._settings.database_url
    try:
        db._settings.database_url = url
        args = db._connect_args()
    finally:
        db._settings.database_url = original

    assert bool(args.get("statement_cache_size") == 0) is expected_disabled


def test_cors_defaults_to_localhost_only():
    """§38.6.8 — نشرٌ نُسي فيه ضبط النطاقات يفشل في المتصفح، ولا يفتح الـAPI للجميع.

    القيمة الافتراضية `*` كانت ستجعل النسيان **غير مرئي** حتى وقوع الضرر.
    """
    from athera_api.config import Settings

    settings = Settings(cors_allowed_origins="http://localhost:3000")
    assert settings.allowed_origins == ["http://localhost:3000"]
    assert "*" not in settings.allowed_origins

    multi = Settings(cors_allowed_origins="https://a.vercel.app, https://athera.sa ")
    assert multi.allowed_origins == ["https://a.vercel.app", "https://athera.sa"]


def test_gitignore_excludes_every_secret_shape():
    """`.env.example` وحده يُلتزم؛ وما عداه من صيغ الأسرار مستثنى."""
    ignored = (REPO / ".gitignore").read_text(encoding="utf-8")
    for rule in (".env", "*.pem", "*.key", "!.env.example", "node_modules/"):
        assert rule in ignored, rule


def test_env_example_carries_no_real_secret():
    """النموذج يوثّق الأسماء ولا يحمل قيمًا.

    مفتاح حقيقي في `.env.example` هو أسهل طريقة لتسريب سرّ: الملف يُلتزم عمدًا.
    """
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        # الأرقام ليست أسرارًا: `ACCESS_TOKEN_TTL_SECONDS=900` مدة لا مفتاحًا.
        # الفحص على اسم يدل على سرّ **وقيمة غير رقمية**.
        if value.isdigit():
            continue
        if any(marker in key.upper() for marker in ("KEY", "SECRET", "PASSWORD", "TOKEN")):
            assert value in ("", "change-me-in-every-environment", "minioadmin"), (
                f"{key} يحمل قيمة تبدو حقيقية"
            )


def test_no_migration_drops_a_constraint_through_the_naming_convention():
    """مسار التراجع يجب أن يعمل قبل أن يُحتاج إليه، لا بعده.

    اصطلاح التسمية `ck_%(table_name)s_%(constraint_name)s` يُطبَّق عند
    `op.drop_constraint` ولا يُطبَّق عند `op.create_check_constraint`. النتيجة
    اسم مضاعف (`ck_tool_runs_ck_tool_runs_status`) لا وجود له، فينكسر
    `alembic downgrade` — وهو بالضبط ما تحتاجه حين يسوء ترحيل في الإنتاج.

    لا يكشفه اختبار وظيفي: الصعود سليم، والتراجع لا يُشغَّل إلا عند الكارثة.
    """
    offenders = []
    for path in (REPO / "infra/db/migrations/versions").glob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "drop_constraint(" in line and 'type_="check"' in line:
                offenders.append(f"{path.name}:{line_no}")
    assert not offenders, (
        "استخدم SQL صريحًا لحذف قيد check حتى لا يتدخل اصطلاح التسمية: "
        f"{offenders}"
    )
