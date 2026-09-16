"""عدُّ مسارات الطفرة — **بلا استيراد**، تحليلًا نحويًّا للمصدر.

## ولمَ لا يُستورَد

عدٌّ سابقٌ استورد `athera_api` فحلَّته بيئةُ بايثون إلى **الحزمة المُثبَّتة
تحريريًّا** — أي إلى مستودعٍ آخرَ على القرص، على فرعٍ آخرَ وبالتزامٍ آخر —
لا إلى شجرة العمل المقصودة. فقال «١٥٨» وشجرةُ العمل فيها ١٥٥.

والتحليلُ النحويّ لا يُخطئ هذا الخطأ: يُقرأ الملفُّ المُمرَّر مسارُه ولا
شيءَ غيرُه.

## وما يُعَدّ

كلُّ دالّةٍ عليها مُزيِّنٌ من `post|put|patch|delete` على أيّ كائن
(`router.post(...)` أو `app.delete(...)`) — فعلُ HTTP هو التعريف، لا اسمُ
الدالّة ولا موضعُها.

    python scripts/count_mutating_routes.py apps/api/athera_api
"""
from __future__ import annotations

import ast
import collections
import pathlib
import sys

MUTATING = {"post", "put", "patch", "delete"}


def main(root: pathlib.Path) -> int:
    found: list[tuple[str, str, str, str]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for deco in node.decorator_list:
                call = deco if isinstance(deco, ast.Call) else None
                func = call.func if call else deco
                if not isinstance(func, ast.Attribute) or func.attr not in MUTATING:
                    continue
                template = ""
                if call and call.args and isinstance(call.args[0], ast.Constant):
                    template = str(call.args[0].value)
                found.append((path.relative_to(root).as_posix(),
                              func.attr.upper(), template, node.name))

    per_file = collections.Counter(entry[0] for entry in found)
    print(f"TOTAL mutating routes: {len(found)}")
    print(f"files: {len(per_file)}")
    for name, count in sorted(per_file.items()):
        print(f"  {count:3}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                               else "apps/api/athera_api")))
