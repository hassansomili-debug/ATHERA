"""حلقةُ أحداثِ الحزمة | The suite's event loop — ضبطٌ يُقرأ، لا تجهيزةٌ ميّتة.

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
