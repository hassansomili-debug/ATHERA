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
    "project_ids_with",        # وترشيحُها بصلاحيةٍ بعينها لا بالاطّلاع
    "is_verified_owner",       # النسبُ المُثبَت — لدورة حياة البحث
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

# **وبواباتُ التحليل الستُّ صارت بوابةً واحدة** (0036): كانت كلُّ واحدةٍ
# تمشي السلسلةَ بنفسها ثمّ تُنادي البوابةَ المشتركة، وصارت `_scope` تُحدّد
# الموضعَ ثمّ تعبُر مستأجرَ البحث ثمّ تُنادي البوابةَ نفسَها. والعددُ نقص
# والحدُّ لم ينقص — ويُثبَت ذلك بفحصٍ إضافيٍّ أدناه لا بحذف هذا السطر.
DERIVED_GATES = {
    "publishing": ["manuscript_for_tenant"],
    "manuscript_drafting": ["manuscript_for_tenant_edit"],
    "analysis": ["_scope", "_scope_pair"],
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


def test_every_analysis_route_enters_through_the_single_data_scope():
    """**ولا مسارَ تحليلٍ يحرس نفسَه بيده** — ولا يعود إلى جلسة البيت.

    وهذا الحارسُ يقوم مقام الستّة التي كانت: يُفحص أنّ كلَّ مسارٍ يملك
    بحثًا يدخل من `_scope`/`_scope_pair`، وأنّ **ما عداها ثلاثُ قوائمَ
    عامّةٍ ومسارُ قدرات** — لا رابعَ يُضاف بصمت.

    ويُقاس بالبنية لا بالنصّ: يُقرأ جسمُ كلِّ مسارٍ من الشجرة، فلا
    يُسكَّن الحارسُ بإعادة تسميةٍ ولا بتقسيم سطر.
    """
    import ast as _ast

    source = (ROUTERS / "analysis.py").read_text(encoding="utf-8")
    tree = _ast.parse(source)
    methods = {"get", "post", "put", "patch", "delete"}

    # مساراتٌ لا تملك بحثًا واحدًا بطبيعتها — **وتُسمّى بأسمائها**:
    #   ثلاثُ قوائمَ تجمع بحوثَ الطالب كلَّها (فلا مستأجرَ واحدٌ تدخله،
    #   وتُرشَّح بمجموعة البحوث المُدارة + سياسات تحديد الموضع)،
    #   ومسارُ قدراتِ الأدوات ولا بيانَ بحثٍ فيه.
    MULTI_PROJECT = {"list_datasets", "list_plans", "list_exports"}
    NO_PROJECT = {"tool_capabilities"}

    scoped, home, other = [], [], []
    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        if not any(isinstance(d, _ast.Call) and isinstance(d.func, _ast.Attribute)
                   and d.func.attr in methods for d in node.decorator_list):
            continue
        body = _ast.get_source_segment(source, node) or ""
        calls = {n.func.id for n in _ast.walk(node)
                 if isinstance(n, _ast.Call) and isinstance(n.func, _ast.Name)}
        if {"_scope", "_scope_pair"} & calls:
            scoped.append(node.name)
            # **ولا يُقرأ مستأجرُ الرمز بعد العبور** — وإلّا كُتب الصفُّ
            # في مستأجرٍ لا يراه أحد.
            assert "principal.tenant_id" not in body, (
                f"{node.name} يقرأ مستأجرَ الرمز بعد دخول نطاق البحث")
            assert "Depends(get_session)" not in body, (
                f"{node.name} يفتح جلسةَ البيت ومعه نطاقُ بحث")
        elif node.name in MULTI_PROJECT:
            home.append(node.name)
            # القوائمُ العامّةُ تُرشَّح بمجموعةِ البحوث المُدارة — وهي
            # عابرةٌ للمستأجرين، ولا تُرشَّح بمستأجرٍ واحد.
            assert "_managed(" in body, f"{node.name} قائمةٌ بلا مُرشِّح بحوث"
            assert "principal.tenant_id" not in body, node.name
        elif node.name in NO_PROJECT:
            continue
        else:
            other.append(f"{node.name}")

    assert other == [], (
        "مساراتُ تحليلٍ لا تدخل نطاقَ بحثٍ ولا هي قائمةٌ معلَنة: "
        + ", ".join(other))
    # اثنا عشرَ مسارًا للبيانات، **وشكلانِ مُعشَّشانِ في بحثهما** للفعلين
    # اللذين لا يطلبان إدارةَ بيانات: اعتمادُ الخطّة وتفسيرُ المخرَج.
    # فالصلاحياتُ تبقى مستقلّةً عبرَ المؤسسات كما هي داخلها.
    assert len(scoped) == 14, f"عددُ مسارات النطاق تغيّر: {len(scoped)} — {scoped}"
    nested = {name for name in scoped if name.endswith("_in_project")}
    assert nested == {"approve_plan_in_project", "interpret_in_project"}, nested
    assert sorted(home) == sorted(MULTI_PROJECT), home


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


# ═══════════ د · سلطةُ المالك لا تُشتقّ من دور ═══════════


def test_owner_authority_never_derives_from_a_role():
    """**ROLE != OWNERSHIP** — وهذا الحدُّ يُحرس نصًّا لا اتفاقًا.

    كانت `OWNER_IMPLIED_PERMISSIONS` تُقرأ من
    `team.default_permissions("principal_investigator")`، فصارت سلطةُ الجذر
    معلَّقةً بما يُقترح لدورٍ **عند الدعوة**. وتلك افتراضاتٌ قابلةٌ للتغيير
    لأسبابِ منتجٍ لا علاقةَ لها بالملكيّة: لو ضُيّقت افتراضاتُ الباحث الرئيس
    غدًا — وهو تغييرٌ مشروع — لَضاقت معها سلطةُ صاحب البحث على بحثه، بلا
    أن يقصد ذلك أحد. **واقترانٌ لا يقصده أحد هو تعريفُ العطب الصامت.**

    فتُقرأ المفردةُ المعياريّة كاملةً، ولا يمرّ الاشتقاقُ بدورٍ ولا بدالّةِ
    افتراضاته. وأنّ المجموعتين متساويتان اليوم مصادفةٌ لا اعتماد.
    """
    import inspect

    from athera_api.services import collaboration, team

    # ١) القيمةُ هي المفردةُ المعياريّة كاملةً — لا مجموعةُ دورٍ توافقها.
    assert collaboration.OWNER_IMPLIED_PERMISSIONS == frozenset(
        team.PROJECT_PERMISSIONS)

    # ٢) والاشتقاقُ نفسه لا يذكر دورًا ولا دالّةَ افتراضات.
    source = inspect.getsource(collaboration)
    definition = source[source.index("OWNER_IMPLIED_PERMISSIONS: frozenset"):]
    definition = definition[:definition.index("\n\n")]
    assert "PROJECT_PERMISSIONS" in definition
    assert "default_permissions" not in definition, (
        "سلطةُ المالك تُشتقّ من افتراضات دور — والدورُ ليس ملكيّة")
    for role in team.MEMBER_ROLES:
        assert role not in definition, f"سلطةُ المالك تذكر الدور {role}"

    # ٣) و`is_verified_owner` تقرأ النسبَ وحده.
    owner_check = inspect.getsource(collaboration.is_verified_owner)
    assert "owner_user_id(" in owner_check
    assert "default_permissions" not in owner_check
    for role in team.MEMBER_ROLES:
        assert role not in owner_check, f"فحصُ النسب يذكر الدور {role}"

    # ٤) **وبيتُ الحارس**: لو ضاقت افتراضاتُ الباحث الرئيس، لا تضيق السلطة.
    #    يُثبَت بأنّ الاشتقاق لا يمرّ بالدالّة أصلًا — فتغييرُ جوابها لا
    #    يغيّر شيئًا هنا.
    narrowed = frozenset(("view_project",))
    assert collaboration.OWNER_IMPLIED_PERMISSIONS != narrowed
    assert len(collaboration.OWNER_IMPLIED_PERMISSIONS) == len(
        team.PROJECT_PERMISSIONS) == 9


def test_the_owner_only_gate_is_ownership_not_permission():
    """دورةُ حياة البحث تُحرس بالنسب — **ولا صلاحيةَ تُختلق لها**."""
    import inspect

    from athera_api.services import collaboration, team
    from athera_api.routers import workspace

    # ولا مفردةَ صلاحيةٍ جديدة دخلت المفردةَ المعياريّة في هذه الدفعة.
    assert len(team.PROJECT_PERMISSIONS) == 9
    assert "manage_project" not in team.PROJECT_PERMISSIONS
    assert "manage_lifecycle" not in team.PROJECT_PERMISSIONS

    gate = inspect.getsource(collaboration.ensure_project_access)
    assert "require_owner" in gate
    assert "OWNER_ONLY" in gate

    # والمساراتُ الثلاثة تطلبه: أرشفةً وحذفًا ظاهرًا واسترجاعًا.
    for name in ("archive_project", "trash_project"):
        body = inspect.getsource(getattr(workspace, name))
        assert "owner_only=True" in body, name
    restore = inspect.getsource(workspace.restore_project)
    assert "is_verified_owner(" in restore and "OWNER_ONLY" in restore, (
        "الاسترجاعُ يقع على محذوفٍ، فيقرأ النسبَ مباشرةً — ولا بوابةَ «قائم» له")
