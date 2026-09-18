"""جلسةٌ تُستعمل بعد خروج مالكها | a session used past its owning scope.

## العطب، مقيسًا

`AsyncSession.close()` **يُخلي الجلسةَ ولا يُعطّلها**. فالجلسةُ التي خرج
`async with` مالكُها تبقى كائنًا صالحًا للاستعمال: وأوّلُ عمليّةِ قاعدةٍ
بعد ذلك تفتح معاملةً جديدةً تلقائيًّا (`autobegin`) وتسحب اتصالًا — **ولا
مالكَ يُعيده**. فيبقى مسحوبًا حتى يجمعه جامعُ المهملات، فيُنهيه SQLAlchemy
بتحذير:

    The garbage collector is trying to clean up non-checked-in connection

**وموضعُ التحذير ليس موضعَ العطب.** الجمعُ يقع متأخّرًا — في فحصٍ آخرَ
لا صلةَ له — فيظهر الخطأُ عشوائيًّا في ملفٍّ بريء. وهذا ما كان يقع: خطأٌ
واحدٌ في تشغيلةٍ كاملة، على فحصٍ **مختلفٍ كلَّ مرّة**.

## ولمَ ماسحٌ بنيويٌّ لا بحثٌ عن نصّ

اسمُ الجلسةِ يتكرّر في كلّ ملفّ، فحضورُ `session.execute` لا يقول شيئًا.
والمقصودُ **موضعُه من نطاق مالكه**: أسطرُ `async with … as session` تُحدَّد،
ثمّ يُسأل عمّا بعد آخرِ سطرٍ منها. وإعادةُ ربطِ الاسم بمالكٍ جديدٍ تُبرّئ
ما بعدها — وإلّا لَاتُّهم كلُّ فحصٍ يفتح جلستين على التوالي.
"""
from __future__ import annotations

import ast
import pathlib

#: مصانعُ الجلسات في هذا المستودع — ما تُعطيه يملك إعادتَه.
FACTORIES = frozenset({
    "tenant_session", "system_session", "project_session", "invitation_session",
    "SessionFactory", "async_sessionmaker", "tenant_session_maker",
})

#: عملياتٌ تُلامس القاعدة. و`add` فيها لأنّها تُلحِق بجلسةٍ ستُغسل.
DB_OPS = frozenset({
    "execute", "flush", "commit", "rollback", "add", "add_all", "get",
    "scalars", "scalar", "refresh", "merge", "delete", "stream", "begin",
    "connection", "run_sync",
})


class Offender:
    """جلسةٌ استُعملت بعد خروج مالكها — ومعها موضعُها ووجهُ الاستعمال."""

    __slots__ = ("file", "function", "line", "name", "factory", "use")

    def __init__(self, file, function, line, name, factory, use) -> None:
        self.file, self.function, self.line = file, function, line
        self.name, self.factory, self.use = name, factory, use

    def describe(self) -> str:
        return (f"  {self.file}:{self.line}\n"
                f"      in {self.function}() — `{self.name}` from "
                f"{self.factory}() used after its scope closed: {self.use}")


def _factory_of(node) -> str | None:
    """اسمُ المصنعِ إن كان هذا التعبيرُ نداءً له، وإلّا `None`."""
    current = node
    for _ in range(3):
        if isinstance(current, ast.Await):
            current = current.value
            continue
        if isinstance(current, ast.Call):
            func = current.func
            if isinstance(func, ast.Name) and func.id in FACTORIES:
                return func.id
            if isinstance(func, ast.Attribute) and func.attr in FACTORIES:
                return func.attr
            current = func
            continue
        break
    return None


def _owned_scopes(fn) -> list[tuple[str, int, int, str]]:
    """(الاسم، أوّلُ سطر، آخرُ سطر، المصنع) لكلّ `async with <مصنع> as <اسم>`."""
    scopes: list[tuple[str, int, int, str]] = []
    for node in ast.walk(fn):
        if not isinstance(node, (ast.AsyncWith, ast.With)):
            continue
        for item in node.items:
            factory = _factory_of(item.context_expr)
            if factory is None or not isinstance(item.optional_vars, ast.Name):
                continue
            last = max((getattr(x, "lineno", node.lineno) for x in ast.walk(node)),
                       default=node.lineno)
            scopes.append((item.optional_vars.id, node.lineno, last, factory))
    return scopes


#: وسمُ استثناءٍ **ظاهرٌ ومعدود**: يُكتب على السطر المُتعمَّد نفسِه.
#:
#: ولمَ وسمٌ لا قائمةُ سماح: القائمةُ تُخفي المسارَ المُستثنى في الماسح،
#: فتنمو بلا أن يُنظَر إليها. والوسمُ يقف حيث العطبُ فيُقرأ مع الشِّفرة،
#: **ويُعَدّ**: `test_at_test_session_lifecycle` يشترط أن تكون الوسومُ
#: كلُّها في ملفِّ البرهان وحدَه، فلا يُرَشّ وسمٌ في فحصٍ آخر بلا كشف.
MARKER = "lifecycle-audit: deliberate-leak"


def marked_lines(source: str) -> set[int]:
    """أرقامُ الأسطرِ التي تحمل وسمَ الاستثناء."""
    return {i for i, line in enumerate(source.splitlines(), start=1)
            if MARKER in line}


def _scan_function(path: str, fn, marked: frozenset[int] = frozenset()) -> list[Offender]:
    scopes = _owned_scopes(fn)
    found: list[Offender] = []
    for name, _start, end, factory in scopes:
        # مالكٌ لاحقٌ للاسم نفسِه يُبرّئ كلَّ ما بعد سطرِ فتحه.
        later = [s for other, s, _e, _f in scopes if other == name and s > end]
        horizon = min(later) if later else 10 ** 9
        for node in ast.walk(fn):
            line = getattr(node, "lineno", None)
            if line is None or not (end < line < horizon):
                continue
            if line in marked:
                continue
            if not isinstance(node, ast.Call):
                continue
            # (أ) عمليّةُ قاعدةٍ على الجلسة نفسِها بعد الخروج
            func = node.func
            if (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == name
                    and func.attr in DB_OPS):
                found.append(Offender(path, fn.name, line, name, factory,
                                      f"{name}.{func.attr}(...)"))
                continue
            # (ب) تمريرُها إلى خدمةٍ تعمل بها بعد الخروج
            if any(isinstance(a, ast.Name) and a.id == name for a in node.args):
                found.append(Offender(path, fn.name, line, name, factory,
                                      f"{ast.unparse(func)}({name}, ...)"))
    return found


def audit_source(source: str, path: str = "<memory>") -> list[Offender]:
    """يمسح نصًّا واحدًا — تُستعمل للعضّ بنصٍّ مُصطنَع."""
    tree = ast.parse(source)
    marked = frozenset(marked_lines(source))
    found: list[Offender] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.extend(_scan_function(path, node, marked))
    return found


def audit(root: pathlib.Path | None = None) -> list[Offender]:
    """يمسح شجرةَ الفحوص كلَّها."""
    base = root or pathlib.Path(__file__).resolve().parent
    found: list[Offender] = []
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        marked = frozenset(marked_lines(source))
        rel = str(path.relative_to(base.parent))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.extend(_scan_function(rel, node, marked))
    return found
