"""توحيدُ روابط التحقّق على psycopg 3 | Release verification URL normalization.

**العطبُ الذي أسقط تشغيلة الإصدار الأولى، وهذه أوّلُ فحوصٍ لهذين السكربتين.**

`postgresql://` بلا سائقٍ مذكور تختار SQLAlchemy له **psycopg2** افتراضًا؛
ومسارُ الإصدار يثبّت psycopg 3 وحده (`psycopg[binary]`). فسقط حارسُ ما قبل
الترحيل بـ`ModuleNotFoundError: No module named 'psycopg2'` **قبل أن يتصل**
— أي قبل أن يقرأ `alembic_version`. والسرُّ كان مضبوطًا سليمًا؛ الذي انكسر
أنّ الرابط الوارد كان يُمرَّر كما هو بينما الرابطُ المبنيّ داخليًّا يُكتب
`postgresql+psycopg://`.

**ولم يكن للسكربتين فحصٌ واحد.** فهذه أوّلها، وتُثبّت الخاصّيّات التي
يسهل فقدُها في أوّل إعادة صياغة — وأهمُّها ألّا تظهر كلمةُ مرورٍ في نصّ
خطأ.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[3]
RELEASE = REPO / "scripts" / "release" / "verify_release_schema.py"
CONSTRAINTS = REPO / "scripts" / "verify_db_constraints.py"


def _load(path: pathlib.Path, name: str):
    """**والوحدةُ تُسجَّل قبل تنفيذها.** `@dataclass` تحلّ تلميحاتِ نوعها عبر
    `sys.modules[cls.__module__]`؛ ووحدةٌ غير مسجَّلة تجعل ذلك `None`."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release():
    return _load(RELEASE, "release_verify")


@pytest.fixture(scope="module")
def constraints():
    return _load(CONSTRAINTS, "verify_constraints")


def _both(release, constraints):
    return (("verify_release_schema", release.normalize_sync_pg_url),
            ("verify_db_constraints", constraints.normalize_sync_pg_url))


# ═════════ ١. قواعدُ التوحيد ═════════

@pytest.mark.parametrize("given", [
    "postgresql://u:p@h:5432/d",
    "postgres://u:p@h:5432/d",
])
def test_a_bare_postgres_url_is_normalized_to_psycopg3(release, constraints, given):
    """**العطبُ بعينه**: بلا هذا التوحيد تختار SQLAlchemy psycopg2 غير المثبَّت."""
    for name, normalize in _both(release, constraints):
        out = normalize(given, label="X")
        assert out.startswith("postgresql+psycopg://"), f"{name}: {out}"
        # ولا يُمسّ من الرابط غيرُ مقطع السائق.
        assert out.endswith("//u:p@h:5432/d"[1:]) or out.endswith("u:p@h:5432/d"), name


def test_an_explicit_psycopg3_url_survives_unchanged(release, constraints):
    given = "postgresql+psycopg://u:p@h:5432/d"
    for name, normalize in _both(release, constraints):
        assert normalize(given, label="X") == given, name


@pytest.mark.parametrize("driver", ["asyncpg", "psycopg2", "pg8000"])
def test_an_incompatible_sync_driver_is_refused_not_silently_rewritten(
        release, constraints, driver):
    """**ولا يُصحَّح سائقٌ خاطئ بصمت.** `create_engine` متزامن، وتسليمُه
    `asyncpg` خطأٌ في النيّة لا في الإملاء — فيُقال لصاحبه."""
    given = f"postgresql+{driver}://u:p@h:5432/d"
    for name, normalize in _both(release, constraints):
        with pytest.raises(SystemExit) as caught:
            normalize(given, label="DATABASE_VERIFY_URL")
        assert driver in str(caught.value), name


def test_a_non_postgres_url_is_refused(release, constraints):
    for _name, normalize in _both(release, constraints):
        with pytest.raises(SystemExit):
            normalize("mysql://u:p@h/d", label="X")
        with pytest.raises(SystemExit):
            normalize("not-a-url", label="X")


def test_both_scripts_normalize_identically(release, constraints):
    """**نسختان تفترقان بأوّل تعديل** — فيُقارَن سلوكُهما حرفًا بحرف.

    والتكرارُ مقصود (لا حزمةَ مشتركة بين سكربتين مستقلَّين)، فهذا الفحصُ هو
    ما يجعله آمنًا.
    """
    samples = ["postgresql://u:p@h:5432/d", "postgres://u:p@h/d",
               "postgresql+psycopg://u:p@h:5432/d"]
    for given in samples:
        assert (release.normalize_sync_pg_url(given, label="X")
                == constraints.normalize_sync_pg_url(given, label="X")), given
    for bad in ["postgresql+asyncpg://u:p@h/d", "mysql://u:p@h/d", "nope"]:
        with pytest.raises(SystemExit):
            release.normalize_sync_pg_url(bad, label="X")
        with pytest.raises(SystemExit):
            constraints.normalize_sync_pg_url(bad, label="X")


# ═════════ ٢. حارسُ المنفذ باقٍ ═════════

def test_the_direct_port_guard_still_refuses_the_pooler(release, monkeypatch):
    """**التوحيدُ لا يتخطّى حارسَ المنفذ ولا يعيد ترتيبه.**

    و6543 مُجمِّعُ المعاملات: لا يضمن جلسةً واحدة بين العبارات، والترحيلُ
    وقفلُه و`SET LOCAL` تفترضها.
    """
    monkeypatch.setenv("DATABASE_VERIFY_URL", "postgresql://u:p@h:6543/d")
    with pytest.raises(SystemExit) as caught:
        release.build_verify_url()
    assert "6543" in str(caught.value)


def test_the_direct_port_is_accepted_and_normalized(release, monkeypatch):
    """**وحارسٌ لا يسمح أبدًا ليس حارسًا.**"""
    monkeypatch.setenv("DATABASE_VERIFY_URL", "postgresql://u:p@h:5432/d")
    assert release.build_verify_url().startswith("postgresql+psycopg://")


def test_an_unreadable_port_fails_closed(release, monkeypatch):
    """**ولا يُفترض 5432 عند الغموض** — الفشلُ مغلق."""
    monkeypatch.setenv("DATABASE_VERIFY_URL", "postgresql://u:p@h:not-a-port/d")
    with pytest.raises(SystemExit):
        release.build_verify_url()


def test_no_target_configured_still_fails_closed(release, monkeypatch):
    for name in ("DATABASE_VERIFY_URL", "PGHOST", "PGUSER", "PGPASSWORD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit):
        release.build_verify_url()


# ═════════ ٣. الخاصّيّةُ التي يسهل فقدُها: لا سرَّ في نصّ خطأ ═════════

SECRET = "s3cr3t-pa55word-DO-NOT-LEAK"


@pytest.mark.parametrize("given", [
    f"postgresql+asyncpg://athera_app:{SECRET}@db.example.com:5432/postgres",
    f"mysql://athera_app:{SECRET}@db.example.com/postgres",
])
def test_a_refusal_never_carries_the_password_or_the_url(release, constraints, given):
    """**رسالةُ خطأٍ تحمل رابطًا تحمل كلمةَ مرور** — وتُطبع في سجلّ مشغّل.

    وهي أسهلُ خاصّيّةٍ تُفقد في إعادة صياغة: `f"refusing: {url}"` سطرٌ
    يبدو بريئًا ويُسرّب اعتمادَ إنتاج إلى سجلٍّ يقرؤه من يملك المستودع.
    """
    for name, normalize in _both(release, constraints):
        with pytest.raises(SystemExit) as caught:
            normalize(given, label="DATABASE_VERIFY_URL")
        message = str(caught.value)
        assert SECRET not in message, f"{name}: password leaked into the refusal"
        assert "db.example.com" not in message, f"{name}: host leaked"
        assert given not in message, f"{name}: whole URL leaked"


def test_the_port_refusal_never_carries_the_password(release, monkeypatch):
    monkeypatch.setenv(
        "DATABASE_VERIFY_URL",
        f"postgresql://athera_app:{SECRET}@db.example.com:6543/postgres")
    with pytest.raises(SystemExit) as caught:
        release.build_verify_url()
    message = str(caught.value)
    assert SECRET not in message, "password leaked into the port refusal"
    assert "db.example.com" not in message, "host leaked into the port refusal"


def test_the_composed_fallback_url_is_psycopg3_and_pinned_to_the_direct_port(
        release, monkeypatch):
    monkeypatch.delenv("DATABASE_VERIFY_URL", raising=False)
    monkeypatch.setenv("PGHOST", "db.example.com")
    monkeypatch.setenv("PGUSER", "athera_app")
    monkeypatch.setenv("PGPASSWORD", SECRET)
    built = release.build_verify_url()
    assert built.startswith("postgresql+psycopg://")
    assert ":5432/" in built


# ═════════ ٤. البرهانُ على مستوى الاستيراد ═════════

def test_a_normalized_url_selects_the_psycopg_dialect_not_psycopg2(release):
    """**الفحصُ الذي كان سيمنع العطب أصلًا.**

    ولا يتّصل بشيء: `create_engine` تحلّ اللهجة وتستورد سائقها عند الإنشاء،
    وهناك بالضبط سقطت التشغيلة. فيُبنى محرّكٌ على رابطٍ مُوحَّد ويُسأل عن
    وحدة سائقه — ويجب أن تكون `psycopg` لا `psycopg2`.
    """
    sqlalchemy = pytest.importorskip("sqlalchemy")

    engine = sqlalchemy.create_engine(
        release.normalize_sync_pg_url("postgresql://u:p@h:5432/d", label="X"))
    assert engine.dialect.driver == "psycopg", engine.dialect.driver
    assert "psycopg2" not in type(engine.dialect).__module__


def test_the_unnormalized_url_is_what_used_to_break(release):
    """**وإثباتُ العطب قبل إثباتِ إصلاحه.**

    الرابطُ الخام يحلّ إلى لهجة psycopg2؛ وفي بيئة الإصدار — psycopg 3 بلا
    psycopg2 — يسقط استيرادُها. فتُفحص اللهجةُ المختارة، لا وجودُ الحزمة،
    فيبقى الفحصُ صادقًا في بيئةٍ ثبّتت الاثنين.
    """
    pytest.importorskip("sqlalchemy")
    from sqlalchemy.engine import make_url

    raw = make_url("postgresql://u:p@h:5432/d")
    assert raw.get_dialect().driver == "psycopg2", (
        "a bare postgresql:// URL no longer resolves to psycopg2 — "
        "the premise of this fix has changed")
    fixed = make_url(release.normalize_sync_pg_url("postgresql://u:p@h:5432/d", label="X"))
    assert fixed.get_dialect().driver == "psycopg"
