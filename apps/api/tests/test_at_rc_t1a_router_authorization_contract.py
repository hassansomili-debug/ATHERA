"""لا مسارَ بحثٍ بلا بوابة | No project route without the canonical gate (RC-T1A).

**لماذا عقدٌ آليّ ولا اكتفاءَ بالاختبارات السلوكية.**

العطبُ الذي أُغلق في هذه الدفعة لم يكن عطبًا واحدًا في موضعٍ واحد: كان
**نمطًا** تكرّر في أحد عشر موجّهًا. كلُّ واحدٍ منها كتب حارسَه بيده، وكلُّهم
سألوا السؤالَ نفسه الخطأ — «أمِن مستأجري هذا البحث؟» — ولم يسأل واحدٌ
منهم «أهو بحثُ هذا الباحث؟».

والاختبارُ السلوكيّ يمسك المسارَ الذي يُكتب له اختبار. وموجّهٌ جديد يُضاف
بعد شهرين، ينسخ نمطَ جاره الذي كان معطوبًا، لا يمسكه شيء — **لأن أحدًا
لن يتذكّر أن يكتب له اختبارَ تسريبٍ هو نفسه لم يخطر له**.

فهذا العقدُ يقرأ الشجرةَ النحوية لكلّ موجّه، ويفرض القاعدة على ما هو
مكتوبٌ لا على ما جُرّب:

  **كلُّ مسارٍ يقبل معرّفَ بحثٍ أو يشتقّه يجب أن يبلغ البوابةَ المشتركة.**

ويتتبّع النداءَ عبر دوالّ الوحدة نفسها إلى نقطةٍ ثابتة، فالحارسُ في
`_project` أو `_gate_version` يُحتسب لمن يناديه — وهو الشكل الصحيح، إذ
البوابةُ الواحدة أولى من تكرارها في كلّ مسار.

## وما لا يفرضه هذا العقد

لا يفرض **أيَّ** صلاحيةٍ بعينها: أهي `view_project` أم `manage_data`؟ ذاك
قرارُ منتجٍ يقرؤه الإنسان، ويحرسه الاختبارُ السلوكيّ في
`test_at_rc_t1a_project_access.py`. وهذا العقد يفرض الحدَّ الذي لا يُختلف
عليه: **أن يُسأل السؤال أصلًا**.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROUTERS = pathlib.Path(__file__).resolve().parents[1] / "athera_api" / "routers"

# أسماءُ البوابة المشتركة في `services/collaboration.py`. وبلوغُ أيٍّ منها
# يعني أنّ السؤالَ سُئل — والأيُّ منها يناسب المسارَ شأنُ المراجع البشريّ.
CANONICAL = frozenset({
    "ensure_project_access",   # البحثُ والعضويّةُ والصلاحيةُ في نداءٍ واحد
    "project_permissions",     # قراءةُ الصلاحيات خامًا (للمحذوف وما شابهه)
    "visible_project_ids",     # ترشيحُ القوائم بما يجوز للباحث أن يراه
    "may_view_project",
    "require_permission",      # بوابةُ الفريق القائمة قبل هذه الدفعة
    "access_for",
})

# بواباتٌ مشتركة تعيش في موجّهٍ وتُستورد في آخر. وهي نفسُها محكومةٌ
# باختبارٍ أدناه يثبت أنها تبلغ البوابةَ المشتركة.
SHARED_ROUTER_GATES = frozenset({
    "manuscript_for_tenant", "manuscript_for_tenant_edit",
})

# **مركزُ الرسائل مؤجَّلٌ ومحفوظ، ولا يُمسّ في هذه الدفعة.** وهو ليس ثغرةً
# مسكوتًا عنها: `_thesis_or_404` يسأل `rbac.require_object_action` على
# مِنحةِ الملفّ — إذنٌ صريحٌ على كائن، لا مساواةُ مستأجر. فحدُّه قائمٌ
# بآليّةٍ أخرى، ويُستثنى من هذا العقد لأنّ مفرداتِه مفرداتُ رسالةٍ لا بحث.
EXEMPT_MODULES = frozenset({"thesis"})

# مسارٌ لا يقبل بحثًا: `project_id` فيه اسمُ حقلٍ في ردٍّ أو مفردةٍ ثابتة.
# ولا يُوسَّع هذا الاستثناء إلا ومعه سببٌ يُقرأ.
EXEMPT_ROUTES = {
    # يُنشئ بحثًا جديدًا؛ ولا بحثَ قائمًا يُسأل عنه.
    ("workspace", "create_project"),
    ("portfolio", "create_project"),
}


def _modules() -> list[tuple[str, ast.Module]]:
    out = []
    for path in sorted(ROUTERS.glob("*.py")):
        if path.stem.startswith("_") or path.stem in EXEMPT_MODULES:
            continue
        out.append((path.stem, ast.parse(path.read_text(encoding="utf-8"))))
    return out


def _functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {n.name: n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _called_names(node: ast.AST) -> set[str]:
    """كلُّ اسمٍ يُنادى داخل هذه الدالّة — بالنقطة وبلا نقطة."""
    names: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Attribute):
            names.add(n.func.attr)
        elif isinstance(n.func, ast.Name):
            names.add(n.func.id)
    return names


def _gating(tree: ast.Module) -> set[str]:
    """دوالُّ هذه الوحدة التي تبلغ البوابة — **بنقطةٍ ثابتة لا بمستوًى واحد**.

    فالمسارُ ينادي `_project`، و`_project` ينادي البوابة؛ والمسارُ ينادي
    `_gate_version`، وهي تنادي `_gate`، وهي تنادي البوابة. وفحصُ مستوًى
    واحدٍ كان سيَعُدّ الثانيةَ ثغرة.
    """
    functions = _functions(tree)
    calls = {name: _called_names(node) for name, node in functions.items()}
    gating = {name for name, names in calls.items()
              if names & CANONICAL or names & SHARED_ROUTER_GATES}
    while True:
        grown = {name for name, names in calls.items() if names & gating}
        if grown <= gating:
            return gating
        gating |= grown


def _routes(tree: ast.Module):
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and getattr(dec.func.value, "id", "") == "router" and dec.args):
                yield node, dec.func.attr.upper(), dec.args[0].value
                break


def _takes_project(node: ast.AST, path: str) -> bool:
    """أيقبل هذا المسارُ معرّفَ بحثٍ أو يشتقّه من حمولته؟"""
    if "{project_id}" in path:
        return True
    args = node.args
    params = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    if "project_id" in params:
        return True
    # `payload.project_id` — الحمولةُ تحمل المعرّف ولا يحمله المسار.
    return any(isinstance(n, ast.Attribute) and n.attr == "project_id"
               and isinstance(n.value, ast.Name) and n.value.id in params
               for n in ast.walk(node))


def _project_routes():
    for module, tree in _modules():
        gating = _gating(tree)
        for node, verb, path in _routes(tree):
            if (module, node.name) in EXEMPT_ROUTES:
                continue
            if _takes_project(node, path):
                yield module, node.name, verb, path, node.name in gating


# ═════════════════ أ · العقد نفسه ═════════════════


def test_every_project_scoped_route_reaches_the_canonical_gate():
    """**مساواةُ المستأجر ليست تفويضَ بحث** — في كلّ موجّه، لا في أشهرها."""
    holes = [f"{module}.{name} — {verb} {path}"
             for module, name, verb, path, gated in _project_routes() if not gated]
    assert not holes, (
        "مساراتٌ تقبل معرّفَ بحثٍ ولا تبلغ بوابةَ الصلاحية "
        "(`collaboration.ensure_project_access` أو أخواتها):\n  "
        + "\n  ".join(holes))


def test_the_contract_actually_sees_routes():
    """**حارسٌ لا يرى شيئًا يمرّ دائمًا.** فيُثبت أنه يعدّ ما يُفترض أن يعدّه."""
    seen = list(_project_routes())
    assert len(seen) >= 60, f"العقد وجد {len(seen)} مسارًا فقط — التحليل مكسور"
    modules = {module for module, *_ in seen}
    for expected in ("workspace", "golden_thread", "planning", "synthesis",
                     "project_management", "analysis", "literature"):
        assert expected in modules, f"{expected} لم يُفحص"


# ═════════════════ ب · البوابات المشتقّة ═════════════════
#
# مساراتٌ لا تقبل `project_id` أصلًا، بل تشتقّه: مخطوطةٌ إلى بحثها،
# ونسخةُ بياناتٍ إلى مجموعتها إلى بحثها. والعقدُ أعلاه لا يراها، فتُحرس
# بواباتُها المشتقّة بعينها — وهي قليلةٌ ومعدودة.

DERIVED_GATES = {
    "publishing": ["manuscript_for_tenant"],
    "manuscript_drafting": ["manuscript_for_tenant_edit"],
    "analysis": ["_gate", "_gate_dataset", "_gate_version", "_gate_plan",
                 "_gate_run", "_gate_output"],
    "literature": ["_claim_gate"],
}


@pytest.mark.parametrize(
    ("module", "helper"),
    [(m, h) for m, helpers in DERIVED_GATES.items() for h in helpers])
def test_derived_gates_reach_the_canonical_gate(module: str, helper: str):
    """المخطوطةُ تُحرس بحراسة بحثها، والنسخةُ بحراسة بحث مجموعتها."""
    tree = dict(_modules())[module]
    assert helper in _functions(tree), f"{module}.{helper} اختفى — العقد يشير إلى ما لا وجود له"
    assert helper in _gating(tree), (
        f"{module}.{helper} بوابةٌ مشتقّة لا تبلغ `collaboration` — "
        "فكلُّ مسارٍ خلفها مفتوح")


# ═════════════════ ج · لا بابَ جانبيّ ═════════════════


def test_no_router_reads_a_live_project_outside_the_gate():
    """`live_project` تجيب «أهو في مستأجري؟» — **وذاك ليس السؤال**.

    وهي التي كان كلُّ موجّهٍ يقف عندها. فمن ناداها في موجّهٍ اليوم إنّما
    يعيد كتابةَ الحارس بيده — وذاك أوّلُ خطوةٍ في طريق العطب نفسه.
    """
    offenders = []
    for module, tree in _modules():
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "live_project"):
                offenders.append(f"{module}:{node.lineno}")
    assert not offenders, (
        "موجّهاتٌ تقرأ البحثَ بمستأجره وحده بدل البوابة المشتركة: "
        + ", ".join(offenders))


def test_the_gate_never_bootstraps_membership():
    """**قراءةٌ لا تكتب.** و`ensure_project_access` تُنادى في `GET` كثيرًا.

    و`access_for` تُنشئ عضويّةَ المالك عند الحاجة — وذاك صحيحٌ في مسارٍ
    يُغيّر فريقًا، وكارثةٌ في مسارٍ يُفتح مئةَ مرّةٍ في اليوم: صفٌّ لكلّ
    زيارة، و`GET` صار تغييرًا لا يتوقّعه أحد.
    """
    source = (ROUTERS.parent / "services" / "collaboration.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    reading = {"project_permissions", "may_view_project", "ensure_project_access",
               "visible_project_ids", "_owned_project_ids", "_member_project_ids"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in reading:
            called = _called_names(node)
            assert "ensure_owner_membership" not in called, (
                f"`{node.name}` تُنشئ عضويّة — والقراءةُ لا تكتب")
            assert "access_for" not in called, (
                f"`{node.name}` تمرّ بـ`access_for` وهي تُنشئ عضويّة")
