"""ماسحُ الانتظارات الخارجيّة تحت معاملةٍ حيّة — بحلِّ الاستيراد لا بالأسماء.

## الدعوى التي يحرسها

> **لا مسارَ HTTP يمسك معاملةَ قاعدةٍ عبر زمنٍ خارجيٍّ غيرِ محدود** — شبكةً
> كان أو تخزينًا أو نداءَ نموذج.

## ولمَ لا `grep`

`grep` على `run_agent` يتّهم تعليقًا يذكره، ويفوته استدعاءٌ مقسومٌ على
سطرَين. وماسحٌ يطابق الأسماءَ المجرّدة أسوأ: في هذا المستودع تصادمت
`search` و`find` و`run` فنُسبت شبكةٌ إلى دوالَّ نقيّةٍ محضة — خمسةَ عشرَ
مسارًا زائفًا في أوّل جردٍ لـRC-T1-H3.

فهذا الماسحُ **يحلّ** كلَّ حافةٍ إلى هدفٍ مؤهَّل عبر جدول استيراد وحدتها،
أو يُهملها. وأربعُ آليّاتٍ تُغلق ما لا يُحلّ بالاستيراد وحده:

  ١ **نوعُ سمةٍ من `__init__`** — `self._gateway = ModelGateway()`.
  ٢ **مصنعٌ يُتبَع** — `self._provider = build_provider()` وهي تعيد ثلاثةَ
    أصناف، فتُوسَّع السمةُ إلى اتّحادها.
  ٣ **تعليقٌ نوعيٌّ محلّيّ** — `registries: list[SourceRegistry]` ثمّ
    `for r in registries: await r.get_by_doi(...)`. وهذا ما يفتح
    الاعتمادَ المُمرَّر مُعامِلًا، وهو نمطُ هذا المستودع.
  ٤ **إعادةُ تصديرٍ من حزمة** — `athera_api.discovery:discover` مُعلَنةٌ في
    `discovery/service.py`.

## وثلاثُ واجهاتٍ تُبذَر صريحًا

الاعتمادُ المُمرَّر مُعامِلًا لا يُعرَف منفّذُه في زمن الترجمة. فتُبذَر
الطريقةُ المجرّدةُ نفسُها، بعد قراءةِ كلِّ تحقيقاتها:

  • `SourceRegistry` — ثلاثةُ تحقيقات: `OfflineRegistry` بلا شبكة،
    و`OpenAlexRegistry` و`CrossrefRegistry` بـ`httpx`.
  • `DiscoveryProvider` — تحقيقان، كلاهما بـ`httpx`.
  • `Extractor` — أحدُ تحقيقاتها (`ModelExtractor`) ينادي بوابةَ النموذج.

**والمسارُ لا يعرف أيَّ تحقيقٍ سيأخذ في زمن التشغيل**، فإمساكُ معاملةٍ عبر
النداء عطبٌ على أيّ حال — ولو كان المنفّذُ في بيئة الفحص هو الصامت.

و`Extractor` بعينها وجدها **القارئ لا الماسح**: `ModelExtractor` كان يُبنى
بجلسة الطلب فيُمرّرها إلى البوابة، فيقع نداءُ نموذجٍ داخل معاملةٍ حيّة.
فبُذرت لتُكشف كلُّ إعادةٍ للنمط، لا لتُصطاد مرّةً.
"""
from __future__ import annotations

import ast
import collections
import pathlib

PACKAGE = "athera_api"

#: تبعيّاتُ جلسةٍ **يُديرها الطلب** — وهي موضعُ الدعوى.
SESSION_DEPENDENCIES = {"get_session", "get_project_session"}

#: سياقاتُ جلسةٍ يملكها المتن — معاملةٌ حيّةٌ كذلك داخل مداها.
SESSION_CONTEXTS = {"tenant_session", "project_session", "invitation_session",
                    "system_session"}

#: بذورٌ على حدِّ الواجهة (انظر رأس الملفّ). كلُّ واحدةٍ مقروءةُ التحقيقات.
INTERFACE_SEEDS = {
    "athera_api.services.literature.registry:SourceRegistry.search": "NETWORK",
    "athera_api.services.literature.registry:SourceRegistry.get_by_doi": "NETWORK",
    "athera_api.discovery.base:DiscoveryProvider.search": "NETWORK",
    "athera_api.services.extraction.base:Extractor.propose": "MODEL",
}


class Offender:
    """مسارٌ ينتظر خارجَ العمليّة ومعاملةٌ حيّة — ومعه سلسلةُ النداء."""

    __slots__ = ("file", "handler", "method", "route", "call", "line", "kind",
                 "held_by", "chain")

    def __init__(self, file, handler, method, route, call, line, kind, held_by, chain):
        self.file, self.handler, self.method, self.route = file, handler, method, route
        self.call, self.line, self.kind = call, line, kind
        self.held_by, self.chain = held_by, chain

    @property
    def key(self) -> tuple[str, str]:
        return (self.file, self.handler)

    def describe(self) -> str:
        arrow = "\n        ".join(
            "  " * i + step for i, step in enumerate(self.chain))
        return (f"  {self.file}::{self.handler}  [{self.method} {self.route}]\n"
                f"    line {self.line}: {self.call}  ({self.kind}, "
                f"session held by {self.held_by})\n"
                f"        {arrow}")


def _annotation_root(node):
    """اسمُ الصنف من تعليقٍ نوعيّ — **مُنقَّطًا** ليُحلَّ عبر الاستيراد."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Subscript):
        return _annotation_root(node.slice)
    if isinstance(node, ast.BinOp):
        return _annotation_root(node.left) or _annotation_root(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            return _annotation_root(ast.parse(node.value, mode="eval").body)
        except SyntaxError:
            return None
    if isinstance(node, ast.Attribute):
        base = _annotation_root(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


class _Audit:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.trees: dict[str, ast.AST] = {}
        self.source: dict[str, str] = {}
        self.packages: set[str] = set()
        self.imports: dict[str, dict[str, str]] = {}
        self.defs: dict[str, ast.AST] = {}
        self.owner: dict[str, str] = {}
        self.edges: dict[str, set[str]] = collections.defaultdict(set)
        self.attr_class: dict[tuple[str, str, str], str] = {}
        self.factory: dict[tuple[str, str, str], set[str]] = {}
        self.egress: dict[str, str] = {}
        self.reach: dict[str, str] = {}
        self.chain: dict[str, list[str]] = {}
        self.missing_seeds: list[str] = []
        self._load()

    # ───────────────────────────── القراءة ─────────────────────────────

    def _load(self) -> None:
        for path in sorted(self.root.rglob("*.py")):
            module = str(path.relative_to(self.root.parent))[:-3].replace("/", ".")
            if module.endswith(".__init__"):
                module = module[: -len(".__init__")]
                self.packages.add(module)
            text = path.read_text(encoding="utf-8")
            self.trees[module] = ast.parse(text)
            self.source[module] = text
        self._read_imports()
        self._read_attributes()
        self._read_definitions()
        self._read_egress()
        self._close_transitively()

    def _read_imports(self) -> None:
        for module, tree in self.trees.items():
            table: dict[str, str] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        table[alias.asname or alias.name.split(".")[0]] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        # **والحزمةُ ليست كالوحدة.** في `pkg/__init__.py`
                        # يعني المستوى الأوّل «هذه الحزمة»، وقد نُزع
                        # `.__init__` من اسمها — فالنزولُ مرّةً يُخرِج منها.
                        base = module
                        strip = node.level - (1 if module in self.packages else 0)
                        for _ in range(strip):
                            base = base.rsplit(".", 1)[0] if "." in base else base
                        source = f"{base}.{node.module}" if node.module else base
                    else:
                        source = node.module or ""
                    for alias in node.names:
                        table[alias.asname or alias.name] = f"{source}:{alias.name}"
            self.imports[module] = table

    def _read_attributes(self) -> None:
        for module, tree in self.trees.items():
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                for fn in cls.body:
                    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                            or fn.name != "__init__":
                        continue
                    for node in ast.walk(fn):
                        if not isinstance(node, ast.Assign):
                            continue
                        targets = [t.attr for t in node.targets
                                   if isinstance(t, ast.Attribute)
                                   and isinstance(t.value, ast.Name)
                                   and t.value.id == "self"]
                        if not targets:
                            continue
                        for call in ast.walk(node.value):
                            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                                hit = self.imports[module].get(call.func.id)
                                target = hit if (hit and ":" in hit) \
                                    else f"{module}:{call.func.id}"
                                for attr in targets:
                                    self.attr_class[(module, cls.name, attr)] = target
                                break

    def _read_definitions(self) -> None:
        for module, tree in self.trees.items():
            self._walk_definitions(module, tree)
        # المصانعُ تُوسَّع بعد أن تُعرَف كلُّ التعريفات
        for key, target in list(self.attr_class.items()):
            expanded = self._factory_classes(target)
            if expanded:
                self.factory[key] = expanded
        # ثمّ تُعاد الحواف ليُستفاد من التوسيع
        self.edges.clear()
        for module, tree in self.trees.items():
            self._walk_definitions(module, tree, edges_only=True)

    def _walk_definitions(self, module: str, tree: ast.AST, *, edges_only=False) -> None:
        audit = self

        class Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.stack: list[str] = []

            def visit_ClassDef(self, node):  # noqa: N802
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def _function(self, node):
                qualified = f"{module}:{'.'.join([*self.stack, node.name])}"
                if not edges_only:
                    audit.defs[qualified] = node
                    audit.owner[qualified] = module
                cls_name = self.stack[0] if self.stack else None
                locals_ = audit._local_types(module, node)
                for sub in ast.walk(node):
                    if not isinstance(sub, ast.Call):
                        continue
                    target = audit._resolve(module, sub.func, cls_name, locals_)
                    if target:
                        audit.edges[qualified].add(target)
                    func = sub.func
                    if isinstance(func, ast.Attribute) \
                            and isinstance(func.value, ast.Attribute) \
                            and isinstance(func.value.value, ast.Name) \
                            and func.value.value.id == "self" and cls_name:
                        for cand in audit.factory.get(
                                (module, cls_name, func.value.attr), ()):
                            cmod, cname = cand.split(":", 1)
                            audit.edges[qualified].add(f"{cmod}:{cname}.{func.attr}")
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            visit_FunctionDef = _function      # noqa: N815
            visit_AsyncFunctionDef = _function  # noqa: N815

        Visitor().visit(tree)

    # ───────────────────────────── الحلّ ─────────────────────────────

    def _local_types(self, module: str, fn) -> dict[str, str]:
        types: dict[str, str] = {}
        args = getattr(fn, "args", None)
        if args is None:
            return types
        for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
            root = _annotation_root(arg.annotation) if arg.annotation else None
            if root:
                types[arg.arg] = root
        for node in ast.walk(fn):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                root = _annotation_root(node.annotation)
                if root:
                    types[node.target.id] = root
            target = getattr(node, "target", None)
            iterable = getattr(node, "iter", None)
            if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)) \
                    and isinstance(target, ast.Name):
                if isinstance(iterable, ast.Name) and iterable.id in types:
                    types[target.id] = types[iterable.id]
                elif isinstance(iterable, ast.Call):
                    # حلقةٌ على نداءٍ مُعلَّقِ العودة: `for r in _registries():`
                    callee = iterable.func
                    name = (callee.id if isinstance(callee, ast.Name)
                            else callee.attr if isinstance(callee, ast.Attribute)
                            else None)
                    if name:
                        for qualified, node_ in self.defs.items():
                            if self.owner.get(qualified) == module \
                                    and qualified.split(":")[1] == name \
                                    and getattr(node_, "returns", None) is not None:
                                root = _annotation_root(node_.returns)
                                if root:
                                    types[target.id] = root
                                break
        return types

    def _factory_classes(self, target: str) -> set[str]:
        if target not in self.defs:
            return set()
        fn = self.defs[target]
        module = self.owner[target]
        found: set[str] = set()
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Return) and node.value is not None):
                continue
            for call in ast.walk(node.value):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    hit = self.imports[module].get(call.func.id)
                    cand = hit if (hit and ":" in hit) else f"{module}:{call.func.id}"
                    if any(q.startswith(cand + ".") for q in self.defs):
                        found.add(cand)
        return found

    def _resolve(self, module, node, cls_name=None, local_types=None):
        table = self.imports[module]
        if isinstance(node, ast.Name):
            hit = table.get(node.id)
            return hit if (hit and ":" in hit) else f"{module}:{node.id}"
        if not isinstance(node, ast.Attribute):
            return None
        base = node.value
        if isinstance(base, ast.Name):
            if local_types and base.id in local_types:
                cls = local_types[base.id]
                if "." in cls:
                    head, tail = cls.rsplit(".", 1)
                    owner = table.get(head)
                    if owner:
                        # `from X import Y` واسمُ Y وحدةٌ ⇒ الوحدةُ `X.Y`.
                        owner = owner.replace(":", ".") if ":" in owner else owner
                        return f"{owner}:{tail}.{node.attr}"
                hit = table.get(cls)
                if hit and ":" in hit:
                    hmod, hname = hit.split(":", 1)
                    return f"{hmod}:{hname}.{node.attr}"
                if f"{module}:{cls}.{node.attr}" in self.defs:
                    return f"{module}:{cls}.{node.attr}"
            hit = table.get(base.id)
            if hit:
                if ":" in hit:
                    hmod, hname = hit.split(":", 1)
                    return f"{hmod}.{hname}:{node.attr}"
                return f"{hit}:{node.attr}"
            if base.id in ("self", "cls") and cls_name:
                owner = self.attr_class.get((module, cls_name, node.attr))
                return owner or f"{module}:{cls_name}.{node.attr}"
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                and base.value.id == "self" and cls_name:
            owner = self.attr_class.get((module, cls_name, base.attr))
            if owner:
                omod, oname = owner.split(":", 1)
                return f"{omod}:{oname}.{node.attr}"
        if isinstance(base, ast.Call):
            inner = self._resolve(module, base.func, cls_name, local_types)
            if inner:
                imod, iname = inner.split(":", 1)
                return f"{imod}:{iname}.{node.attr}"
        return None

    def _candidates(self, target: str, depth: int = 0) -> set[str]:
        if target in self.defs:
            return {target}
        module, name = target.split(":", 1)
        if depth < 4 and module in self.imports:
            redirect = self.imports[module].get(name.split(".")[0])
            if redirect and ":" in redirect:
                rest = name.split(".", 1)[1] if "." in name else None
                rmod, rname = redirect.split(":", 1)
                nxt = f"{rmod}:{rname}" + (f".{rest}" if rest else "")
                if nxt != target:
                    found = self._candidates(nxt, depth + 1)
                    if found:
                        return found
        if "." in module:
            head, tail = module.rsplit(".", 1)
            cand = f"{head}:{tail}.{name}"
            if cand in self.defs:
                return {cand}
        return set()

    # ───────────────────────── جذورُ الخروج ─────────────────────────

    def _read_egress(self) -> None:
        for qualified, node in self.defs.items():
            segment = ast.get_source_segment(self.source[self.owner[qualified]], node) or ""
            module = self.owner[qualified]
            if "httpx.AsyncClient" in segment or "httpx.Client" in segment:
                self.egress[qualified] = "NETWORK"
            elif "boto3" in segment or "self._s3" in segment or "_s3()" in segment:
                self.egress[qualified] = "STORAGE"
            elif module.endswith(("anthropic_adapter", "openai_adapter")) and (
                    "await self._client" in segment or "messages.create" in segment
                    or "responses.create" in segment or "chat.completions" in segment):
                self.egress[qualified] = "MODEL"
        for seed, kind in INTERFACE_SEEDS.items():
            if seed in self.defs:
                self.egress.setdefault(seed, kind)
            else:
                # **بذرةٌ فُقدت تُقال**: واجهةٌ أُعيد تشكيلها تُسقط الحارسَ
                # صامتًا لو أُهملت.
                self.missing_seeds.append(seed)

    def _close_transitively(self) -> None:
        self.reach = dict(self.egress)
        self.chain = {q: [q] for q in self.egress}
        for _ in range(80):
            grew = False
            for qualified in self.defs:
                if qualified in self.reach:
                    continue
                for target in self.edges[qualified]:
                    done = False
                    for cand in self._candidates(target):
                        if cand in self.reach:
                            self.reach[qualified] = self.reach[cand]
                            self.chain[qualified] = [qualified, *self.chain[cand]]
                            grew = done = True
                            break
                    if done:
                        break
            if not grew:
                break

    # ───────────────────────────── المسارات ─────────────────────────────

    def offenders(self) -> list[Offender]:
        found: list[Offender] = []
        for path in sorted((self.root / "routers").glob("*.py")):
            module = str(path.relative_to(self.root.parent))[:-3].replace("/", ".")
            tree = self.trees.get(module)
            if tree is None:
                continue
            for fn in tree.body:
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                decorators = [d for d in fn.decorator_list
                              if isinstance(d, ast.Call)
                              and isinstance(d.func, ast.Attribute)
                              and d.func.attr in {"get", "post", "put", "patch", "delete"}]
                if not decorators:
                    continue
                first = decorators[0]
                route = (first.args[0].value
                         if first.args and isinstance(first.args[0], ast.Constant) else "?")
                managed = [d.args[0].id for d in
                           [*fn.args.defaults,
                            *[k for k in fn.args.kw_defaults if k is not None]]
                           if isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
                           and d.func.id == "Depends" and d.args
                           and isinstance(d.args[0], ast.Name)
                           and d.args[0].id in SESSION_DEPENDENCIES]
                owned: list[tuple[int, int]] = []
                for node in ast.walk(fn):
                    if isinstance(node, ast.AsyncWith) and any(
                            isinstance(i.context_expr, ast.Call)
                            and isinstance(i.context_expr.func, ast.Name)
                            and i.context_expr.func.id in SESSION_CONTEXTS
                            for i in node.items):
                        owned.append((node.lineno,
                                      max(getattr(x, "lineno", node.lineno)
                                          for x in ast.walk(node))))
                locals_ = self._local_types(module, fn)
                seen: set[tuple[str, int]] = set()
                for node in ast.walk(fn):
                    if not (isinstance(node, ast.Await) and isinstance(node.value, ast.Call)):
                        continue
                    target = self._resolve(module, node.value.func, None, locals_)
                    if not target:
                        continue
                    for cand in self._candidates(target):
                        if cand not in self.reach:
                            continue
                        inside = any(a <= node.lineno <= b for a, b in owned)
                        if not (managed or inside):
                            break
                        label = ast.unparse(node.value.func)
                        if (label, node.lineno) in seen:
                            break
                        seen.add((label, node.lineno))
                        found.append(Offender(
                            file=path.name, handler=fn.name,
                            method=first.func.attr.upper(), route=route,
                            call=label, line=node.lineno, kind=self.reach[cand],
                            held_by="request dependency" if managed else "handler body",
                            chain=self.chain[cand]))
                        break
        return found


def audit(api_root: pathlib.Path | None = None) -> _Audit:
    """يُجري المسحَ ويعيد نتيجتَه — تُستدعى من الفحوص."""
    root = api_root or (pathlib.Path(__file__).resolve().parents[1] / PACKAGE)
    return _Audit(root)
