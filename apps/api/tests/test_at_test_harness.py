"""حزامُ الاختبارات | The test harness — حلقةٌ واحدة، ومحرّكٌ مملوك.

**والعطبُ كان حارسًا يبدو حيًّا.** `tests/conftest.py` حملت تجهيزةَ
`event_loop` بنطاق الجلسة تقصد أن تجري الحزمةُ كلُّها على حلقةٍ واحدة —
لأنّ `athera_api.db` ينشئ `AsyncEngine` واحدًا عامًّا، و`AsyncAdaptedQueuePool`
يحتفظ باتصالات asyncpg بين الاختبارات، وكلُّ اتصالٍ مربوطٌ بالحلقة التي
أنشأته.

وأزال pytest-asyncio تلك التجهيزةَ في 1.0 (أُنذر بها في 0.23). والمدى في
`pyproject.toml` كان `>=0.24` بلا سقف، فدخل الرئيسيُّ الجديد في CI صامتًا:
بقيت الدالّةُ في الملفّ ولا أحدَ يسألها. فجرى كلُّ اختبارٍ على حلقته
(`function` هو الافتراض)، وعبَرت اتصالاتُ المجمَّع بين الحلقات:

    RuntimeError: got Future <Future pending> attached to a different loop
    Exception closing connection <asyncpg.connection.Connection>

**فلا يُفحص هنا نصُّ الضبط فقط، بل يُسأل pytest نفسُه** — لأنّ الدرسَ
بعينه أنّ ضبطًا مكتوبًا في مكانٍ لا يقرؤه المكوّنُ ليس ضبطًا.
"""
from __future__ import annotations

import ast
import pathlib
import tomllib

HERE = pathlib.Path(__file__).resolve()
API_ROOT = HERE.parents[1]
TESTS = HERE.parent


def _ini() -> dict:
    with (API_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["tool"]["pytest"]["ini_options"]


def test_the_loop_scope_is_read_by_pytest_itself(pytestconfig):
    """**والدعوى هي ما يقرؤه المكوّن، لا ما كُتب في ملفّ.**

    فحصٌ يقرأ `pyproject.toml` وحده كان يمرّ يوم العطب أيضًا: النصُّ كان
    صحيحًا في نيّته، والمكوّنُ لا يراه. فيُسأل `pytestconfig` الحيّ.
    """
    assert pytestconfig.getini("asyncio_default_fixture_loop_scope") == "session"
    assert pytestconfig.getini("asyncio_default_test_loop_scope") == "session"


def test_both_scopes_widen_together():
    """**ونطاقٌ واحدٌ يتّسع يترك الحدَّ مقطوعًا.**

    تجهيزةٌ في حلقةِ الجلسة واختبارٌ في حلقةِ دالّة يتشاركان المجمَّعَ ولا
    يتشاركان الحلقة — وهو العطبُ نفسُه بثوبٍ آخر. فيلزمان معًا.
    """
    ini = _ini()
    assert ini["asyncio_default_fixture_loop_scope"] == (
        ini["asyncio_default_test_loop_scope"]), (
        "نطاقُ التجهيزات ونطاقُ الاختبارات افترقا — واتصالُ المجمَّع يعبُر بينهما")


def test_no_fixture_hand_builds_an_event_loop():
    """**ولا حلقةَ تُبنى باليد.** تلك الواجهةُ أُزيلت، والتجهيزةُ تصير ميّتة.

    ويُفحص على الشجرة لا بالنصّ: تعليقٌ يذكر `new_event_loop` لا يُسقط
    الفحص، وتجهيزةٌ تبنيها تُسقطه.
    """
    offenders: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(
                    node.func, "attr", "") in {"new_event_loop", "set_event_loop"}:
                offenders.append(f"{path.name}:{node.lineno}")
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "event_loop"
                    and any("fixture" in ast.unparse(d) for d in node.decorator_list)):
                offenders.append(f"{path.name}:{node.lineno} (تجهيزة event_loop)")
    assert offenders == [], (
        "حلقةُ أحداثٍ تُبنى باليد — وpytest-asyncio لا يسألها:\n"
        + "\n".join(offenders))


def test_the_asyncio_plugin_floor_supports_the_declared_scopes():
    """**ومدًى بلا سقفٍ هو ما أدخل الكسرَ صامتًا.**

    القاعُ 1.0 لأنّ `event_loop` أُزيلت فيه، فلا سبيلَ إلى توحيد الحلقة
    إلّا هذا الضبطُ — ولا تجهيزةَ صامتةً تُوهم أنّها تفعل. والسقفُ على
    الرئيسيّ وحده.
    """
    with (API_ROOT / "pyproject.toml").open("rb") as fh:
        dev = tomllib.load(fh)["project"]["optional-dependencies"]["dev"]
    pin = next(p for p in dev if p.startswith("pytest-asyncio"))
    assert pin == "pytest-asyncio>=1.0,<2", f"مدًى غيرُ محروس: {pin}"


# ═════════════ ٢. المحرّك: مملوكٌ للحزمة، وبلا مجمَّع ═════════════
#
# **والعطبُ الثاني كان مِلكيّة.** الحزمةُ تعمل على محرّك التطبيق العامّ —
# `AsyncAdaptedQueuePool` يحتفظ باتصالات asyncpg بين الاختبارات، وكلُّ
# اتصالٍ مربوطٌ بحلقةٍ. فكانت التجهيزاتُ تُعالج العَرَض: `engine.dispose()`
# قبل كلِّ اختبارٍ وبعده في ثلاثة عشر ملفًّا — تدفع ثمنَ اتصالٍ جديدٍ في
# كلِّ اختبار، ويبقى السببُ قائمًا.

def _conftest_source() -> str:
    return (TESTS / "conftest.py").read_text(encoding="utf-8")


def test_the_suite_owns_its_engine_and_it_has_no_pool():
    """**بلا مجمَّعٍ لا يعبُر اتصالٌ بين حلقتين — ولو أخطأ النطاقُ يومًا.**"""
    source = _conftest_source()
    assert "poolclass=NullPool" in source, "محرّكُ الاختبارات بمجمَّع"
    assert "create_async_engine(" in source, "لا محرّكَ مملوكًا للحزمة"


def _imports_the_app_engine(tree: ast.AST) -> list[int]:
    """أسطرُ `from …db import engine` أينما وقعت — من الشجرة لا من النصّ.

    والفرقُ ليس تجميلًا: نصُّ هذا الملفِّ نفسِه يذكر تلك العبارةَ في رسائل
    الإخفاق، ففحصٌ بالنصّ يتّهم حارسَه.
    """
    return [
        node.lineno for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        and node.module.split(".")[-1] == "db"
        and any(alias.name == "engine" for alias in node.names)
    ]


def test_db_ready_never_disposes_a_pool_per_test():
    """البند ٥: **لا `dispose()` قبل كلِّ اختبار** — ذاك عِلاجُ عَرَض."""
    tree = ast.parse(_conftest_source())
    ready = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
        and n.name == "db_ready" and n.body)

    disposals = [n.lineno for n in ast.walk(ready)
                 if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "dispose"]
    assert disposals == [], f"`db_ready` ما زالت تتخلّص من مجمَّع: {disposals}"
    assert _imports_the_app_engine(ready) == [], (
        "`db_ready` ما زالت تمسك المحرّك العامّ")


def test_no_test_disposes_the_global_application_engine():
    """**ولا ملفَّ اختبارٍ يتصرّف بمِلك التطبيق.**

    كان ثلاثة عشر ملفًّا يفعلون، وكلُّهم عِلاجُ العَرَض نفسِه: يتخلّصون من
    مجمَّع محرّك التطبيق بعد كلِّ اختبار كي لا يعبُر اتصالٌ بين حلقتين.
    """
    offenders: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders += [f"{path.name}:{line}" for line in _imports_the_app_engine(tree)]
    assert offenders == [], (
        "ملفّاتٌ ما زالت تمسك محرّك التطبيق العامّ:\n" + "\n".join(offenders))


def test_no_module_level_import_captures_the_engine_or_factory():
    """**واستيرادُ الاسم في الرأس يلتقط الكائنَ قبل الربط.**

    `tenant_session` و`system_session` تقرآن `SessionFactory` من فضاء
    الوحدة عند النداء، فالربطُ يبلغهما. أمّا
    `from athera_api.db import SessionFactory` على مستوى الوحدة فيلتقط
    المصنعَ القديم عند الجمع — قبل أن تُربط الحزمة — فيعمل ذلك الملفّ على
    المحرّك العامّ وحده: نصفُ إصلاحٍ يبدو تامًّا.
    """
    offenders: list[str] = []
    for root in (TESTS, API_ROOT / "athera_api"):
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:  # المستوى الأعلى وحده
                if (isinstance(node, ast.ImportFrom) and node.module
                        and node.module.split(".")[-1] == "db"):
                    names = {a.name for a in node.names}
                    if names & {"engine", "SessionFactory"}:
                        offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == [], (
        "استيرادٌ في الرأس يلتقط المحرّك/المصنع قبل الربط:\n" + "\n".join(offenders))


def test_the_whole_application_is_bound_to_the_test_engine(test_engine):
    """**الدعوى التي تفصل الإصلاح التامّ عن نصفه** — وتُفحص بلا قاعدة.

    لا اتصالَ هنا: تُقارن الهُويّات وحدها. فمسارُ الـAPI كلُّه
    (`get_session` ← `tenant_session` ← `SessionFactory`) يجب أن يشير إلى
    محرّك الاختبار، لا إلى محرّك التطبيق.
    """
    from athera_api import db

    assert db.engine is test_engine, "المحرّكُ العامّ لم يُربط بمحرّك الاختبار"
    assert db.SessionFactory.kw["bind"] is test_engine, (
        "مصنعُ الجلسات ما زال على محرّك التطبيق — فالموجّهاتُ خارج الربط")
    assert type(test_engine.pool).__name__ == "NullPool", (
        f"محرّكُ الاختبار بمجمَّع {type(test_engine.pool).__name__}")


def test_the_production_database_guard_still_runs_before_collection():
    """البند ٧: **حارسُ قاعدة الإنتاج لا يُمَسّ** — ويبقى قبل أيّ تجهيزة."""
    source = _conftest_source()
    assert "def pytest_configure" in source
    assert "_guard_test_database()" in source
    assert "raise pytest.UsageError" in source, "الحارسُ لم يعد يُسقط التشغيلة"
