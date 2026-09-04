"""عقودٌ معماريّة تُفحص بالبنية لا بالنصّ | structural architecture contracts.

فحصان يمنعان عطبين وقعا في هذا المستودع فعلًا، وكلاهما مرّ والفحوص خضراء:

١. **موجّهٌ مكتوبٌ غيرُ مركَّب.** طبقةُ التركيب كاملةً — اثنتا عشرة نقطة —
   كانت في الشجرة ولم تكن في التطبيق. تسعون فحصًا تمرّ، ولا سبيل للباحث
   إليها. والبحث عن سطر التركيب بـ`grep` لا يكفي: سطرٌ موجودٌ في ملفٍّ لا
   يعني نداءً وقع.

٢. **موجّهٌ يختم المعاملة ثمّ يقرأ بها.** `tenant_session` تفتح المعاملة
   وتختمها عند الخروج؛ فمن ختم في الوسط ثمّ قرأ سقط طلبُه كلُّه بـ٥٠٠.
   أربعُ نقاطٍ شُحنت هكذا. والفحص بالنصّ يُخدع بتعليقٍ أو باسمٍ مشابه،
   فيُقرأ الشجر النحويّ.
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"


# ═════════════════════ ١. كلُّ موجّهٍ مركَّب ═════════════════════

#: موجّهاتٌ لا تُركَّب عمدًا — والقائمة تُكتب بسببٍ لا بالاسم وحده.
UNMOUNTED_BY_DESIGN: dict[str, str] = {}


def _declared_paths(stem: str) -> set[str]:
    """مساراتُ وحدةِ موجّهٍ كما كُتبت — مع بادئتها."""
    import importlib

    module = importlib.import_module(f"athera_api.routers.{stem}")
    router = getattr(module, "router", None)
    if router is None:
        return set()
    return {route.path for route in router.routes
            if getattr(route, "include_in_schema", True)
            and getattr(route, "path", None)}


def test_every_router_module_is_actually_mounted():
    """**كلُّ نقطةٍ مكتوبة تُبلَغ** — والدليل من سطح التطبيق لا من الملفّ.

    والمقياسُ `app.openapi()["paths"]`: هو ما يراه العالم فعلًا. ولا تُقاس
    هوّيةُ الدوالّ ولا تُقرأ بنيةٌ خاصّة — جرّبتُ ذلك أوّلًا فوجدت
    `app.routes` تحمل غلافًا لا يكشف ما تحته، فقال الفحصُ إنّ كلّ موجّهٍ
    غائب. **الخطأ كان في الحارس، والتطبيق سليم** — ولو صدّقتُه لطاردتُ
    عطبًا لا وجود له.
    """
    from athera_api.main import app

    reachable = set(app.openapi()["paths"])
    missing: list[str] = []

    # **والتركيبُ قد يكون على طبقتين.** `folders` و`library_bulk` يُركَّبان
    # داخل `files`، فيصير مسارُهما `/api/v1/files/folders` لا `/folders`.
    # فتُقبل النهايةُ لاحقةً لمسارٍ مبلوغ: يبقى الحارس كاشفًا لموجّهٍ لم
    # يُركَّب البتّة — وهو الذي وقع — دون أن يتّهم تركيبًا متداخلًا صحيحًا.
    def _is_reachable(declared: str) -> bool:
        return any(live == declared or live.endswith(declared)
                   for live in reachable)

    for path in sorted(ROUTERS.glob("*.py")):
        if path.stem in {"__init__", *UNMOUNTED_BY_DESIGN}:
            continue
        missing += [f"{path.stem}:{route}"
                    for route in _declared_paths(path.stem)
                    if not _is_reachable(route)]

    assert not missing, (
        "نقاطٌ مكتوبةٌ لا يبلغها أحد — الموجّه لم يُركَّب في main.py: "
        + ", ".join(sorted(missing)[:12])
    )


def test_the_mount_guard_would_notice_an_absent_router():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.** فيُجرَّب على الحالين معًا."""
    from fastapi import APIRouter, FastAPI

    bare = FastAPI()
    orphan = APIRouter()

    @orphan.get("/never-mounted")
    async def _orphan() -> dict:  # pragma: no cover — لا يُنادى
        return {}

    assert "/never-mounted" not in bare.openapi()["paths"], \
        "الفحصُ لا يميّز موجّهًا غير مركَّب"

    # وحين يُركَّب يُرى — وإلّا فالحارس يقول «غائب» عن كل شيء ولا يفيد.
    bare.openapi_schema = None
    bare.include_router(orphan)
    assert "/never-mounted" in bare.openapi()["paths"], "الفحصُ أعمى عن موجّهٍ مركَّب"


# ═════════════════════ ٢. الموجّه لا يملك الختم ═════════════════════

#: استثناءاتٌ مُبرَّرة — **بالسبب، لا بالتسامح**. وكلُّ سطرٍ هنا دَينٌ يُراجَع.
#:
#: `document_intelligence.upload_thesis`: مهمّةٌ خلفية تفتح جلسةً أخرى، فلا
#: ترى صفًّا لم يُختم. وقد وقع هذا في الإنتاج حرفيًّا: الملفُّ غيرُ مرئيٍّ
#: للمستأجر، والعزلُ سليم، والصفُّ لم يكن قد وُجد بعد. وهي لا تقرأ بالجلسة
#: بعد الختم — وذاك شرطُ سلامتها.
COMMIT_ALLOWLIST: dict[str, str] = {
    "document_intelligence": (
        "مهمّةٌ خلفية تفتح جلسةً مستقلّة ولا ترى صفًّا غير مختوم؛ "
        "ولا تُقرأ الجلسة بعد الختم"
    ),
}


def _commit_calls(tree: ast.AST) -> list[tuple[str, int]]:
    """يلتقط `<شيء>.commit()` من الشجر النحويّ — لا من النصّ."""
    found: list[tuple[str, int]] = []

    class Walker(ast.NodeVisitor):
        def __init__(self) -> None:
            self.scope: list[str] = []

        def _enter(self, node) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_FunctionDef = _enter
        visit_AsyncFunctionDef = _enter

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "commit":
                where = ".".join(self.scope) or "<module>"
                found.append((where, node.lineno))
            self.generic_visit(node)

    Walker().visit(tree)
    return found


def test_no_router_owns_its_transaction():
    """**المعاملةُ لصاحبها.** `tenant_session` تفتحها وتختمها عند الخروج.

    ومن ختم في الوسط ثمّ قرأ بالجلسة نفسها سقط طلبُه:

        InvalidRequestError: Can't operate on closed transaction

    وأربعُ نقاطٍ شُحنت بهذا العطب، ولم يكشفها فحصٌ واحد لأنّ الفحوص كانت
    تبلغ الخدمة من غير طريق الموجّه.
    """
    offenders: list[str] = []

    for path in sorted(ROUTERS.glob("*.py")):
        if path.stem in COMMIT_ALLOWLIST:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [f"{path.stem}.{where}:{line}"
                      for where, line in _commit_calls(tree)]

    assert not offenders, (
        "موجّهٌ يختم معاملةً لا يملكها — والقراءةُ بعده تسقط بـ٥٠٠: "
        + ", ".join(offenders)
    )


@pytest.mark.parametrize("module", sorted(COMMIT_ALLOWLIST))
def test_every_allowlisted_commit_still_exists_and_is_explained(module: str):
    """**استثناءٌ بلا سببٍ مكتوب يصير عادة**، واستثناءٌ بلا ختمٍ يصير أثرًا.

    فيُطلب الأمران: أن يبقى السبب مكتوبًا، وأن يبقى الختم موجودًا فعلًا —
    فإن زال الختم زال موجبُ الاستثناء، ويُحذف من القائمة لا يُترك يتراكم.
    """
    reason = COMMIT_ALLOWLIST[module]
    assert len(reason) > 30, f"{module}: الاستثناء بلا سببٍ مفهوم"

    tree = ast.parse((ROUTERS / f"{module}.py").read_text(encoding="utf-8"))
    assert _commit_calls(tree), (
        f"{module}: استثناءٌ قائمٌ بلا ختمٍ في الملفّ — يُحذف من القائمة")


def test_the_transaction_guard_reads_the_tree_not_the_text():
    """**النصُّ يُخدع، والشجرُ لا.** تعليقٌ يذكر الختم ليس ختمًا."""
    disguised = ast.parse(
        "async def handler(session):\n"
        "    # await session.commit() — مذكورٌ في تعليقٍ لا أكثر\n"
        '    text = "session.commit()"\n'
        "    return text\n")
    assert _commit_calls(disguised) == [], "الحارس يقرأ النصّ بدل الشجر"

    real = ast.parse("async def handler(session):\n"
                     "    await session.commit()\n")
    assert _commit_calls(real) == [("handler", 2)], "الحارس لا يرى ختمًا حقيقيًّا"


# ═════════════════════ ٣. لا رقعةَ متصفّحٍ بلا مشغّل ═════════════════════
#
# **فحصٌ لا يُشغَّل أسوأ من فحصٍ غائب.** الغائبُ يُطلب؛ والموجودُ الميّت
# يُحسب حراسةً قائمة فيُطمأنّ إليه وهو لا يحرس شيئًا.
#
# وقع هذا مرّتين في موجةٍ واحدة: `research-brain-surface.spec.ts` كُتبت مع
# اثنتي عشرة دعوى فما نُفِّذت واحدة، و`project-management.spec.ts` وصلت
# الفرع ولا خطوة تنادِيها. وفي الحالتين كان سطحُ المتصفّح أخضر.
#
# والقياسُ بالمرجعية لا بالبنية: يُقرأ `package.json` ليُعرف ما يشغّله كل
# سكربت، ويُقرأ المشغّل ليُعرف أيُّ سكربتٍ يُنادى فعلًا. ورقعةٌ لا يبلغها
# هذا الطريق لا يبلغها أحد.

WEB = pathlib.Path(__file__).resolve().parents[3] / "apps" / "web"
CI = pathlib.Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"

#: رقعاتٌ لا يُشغّلها المشغّل عمدًا — بسببٍ مكتوب، لا بالسكوت.
UNRUN_BY_DESIGN: dict[str, str] = {}


def _scripts() -> dict[str, str]:
    import json as _json

    return _json.loads((WEB / "package.json").read_text(encoding="utf-8"))["scripts"]


def test_every_browser_spec_is_reachable_from_the_workflow():
    """**كلُّ رقعةٍ في الشجرة يبلغها المشغّل** — وإلّا فهي حبرٌ على ورق."""
    if not (WEB / "tests").exists() or not CI.exists():   # pragma: no cover
        pytest.skip("شجرةُ الوِب أو المشغّل غير موجودَين هنا")

    scripts = _scripts()
    invoked = set(re.findall(r"npm run ([A-Za-z0-9:_-]+)", CI.read_text(encoding="utf-8")))

    covered: set[str] = set()
    for name in invoked:
        body = scripts.get(name, "")
        if "playwright test" not in body:
            continue
        # `playwright test` بلا وسائط يشمل كلّ الرقعات.
        args = body.split("playwright test", 1)[1].split()
        covered |= {pathlib.Path(a).name for a in args if a.endswith(".spec.ts")} or {"*"}

    on_disk = {p.name for p in (WEB / "tests").glob("*.spec.ts")}
    orphans = sorted(
        s for s in on_disk
        if "*" not in covered and s not in covered and s not in UNRUN_BY_DESIGN)

    assert not orphans, (
        "رقعاتٌ في الشجرة لا يشغّلها المشغّل — خضرةُ المتصفّح لا تشملها: "
        + ", ".join(orphans))


def test_the_orphan_guard_would_notice_an_unrun_spec():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.**

    يُحاكى الحسابُ نفسه على رقعةٍ لا يذكرها سكربتٌ منادى، فيجب أن تُرى.
    """
    scripts = {"test:surface": "playwright test tests/product-surface.spec.ts"}
    invoked = {"test:surface"}
    covered: set[str] = set()
    for name in invoked:
        args = scripts[name].split("playwright test", 1)[1].split()
        covered |= {pathlib.Path(a).name for a in args if a.endswith(".spec.ts")}

    on_disk = {"product-surface.spec.ts", "forgotten.spec.ts"}
    assert sorted(s for s in on_disk if s not in covered) == ["forgotten.spec.ts"]
