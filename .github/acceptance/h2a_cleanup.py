"""RC-T1-H2-A — تنظيفُ أثرِ البرهان | cleanup of the smoke artifact.

**والتنظيفُ يُقال بصدق، لا يُفترض.** كانت الخطوةُ تُحذّر عند الإخفاق ثمّ
يقول الملخّصُ إنّ البحثَ نُقل إلى السلّة — وذاك تقريرٌ كاذب. فتُصدر هذه
الأداةُ حالًا صريحةً (`pass` أو `not_needed` أو `failed`)، ويقرؤها الملخّص،
**وتسقط الخطوةُ عند الإخفاق**: برهانٌ على الإنتاج لا يستطيع إزالةَ أثرِه
المعلوم ليس قبولًا كاملَ الخضرة.

## والحالةُ الغامضةُ بعينها — وهي علّةُ وجود H2 أصلًا

قد يُنشئ الخادمُ البحثَ ثمّ ينقطع الجوابُ فلا يعرف العميلُ معرّفَه. فلو
اكتُفي بمعرّفٍ مفقودٍ لَبقي بحثٌ في الإنتاج بلا تنظيف. والعنوانُ مشتقٌّ
حتميًّا من معرّف التشغيلة ومحاولتِها، فيُبحث به ويُنظَّف ما يُطابقه.

**ولا SQL ولا إتلاف**: المسارُ `DELETE /api/v1/workspace/projects/{id}` نقلٌ
إلى السلّة، والصفُّ يبقى قابلًا للاستعادة. ولا يُحذف صفُّ تكرارٍ بيد.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API = os.environ.get("PUBRIVA_API_URL", "https://athera-api.fly.dev")
ROUTE = "/api/v1/workspace/projects"


def _emit(status: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(f"cleanup_status={status}\n")
    print(f"cleanup_status={status}")


def _call(method: str, path: str, token: str) -> tuple[int, object]:
    request = urllib.request.Request(API + path, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as exc:
        return exc.code, {}
    except Exception as exc:  # noqa: BLE001 — الشبكةُ تسقط بأشكال، والحالُ صفر
        print(f"detail={type(exc).__name__}")
        return 0, {}


def main() -> int:
    token_path = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "h2a_smoke_token")
    if not os.path.exists(token_path) or os.path.getsize(token_path) == 0:
        # لم يُبلَغ الدخولُ أصلًا، فلا أثرَ يمكن أن يكون وُجد.
        print("no acceptance token was stored; there can be no artifact")
        _emit("not_needed")
        return 0
    with open(token_path, encoding="utf-8") as handle:
        token = handle.read().strip()

    project_id = os.environ.get("SMOKE_PROJECT_ID", "").strip()
    title = os.environ.get("SMOKE_TITLE", "").strip()

    # **والمعرّفُ المفقودُ لا يعني أنّ الطفرةَ لم تقع** — انظر أعلى الملفّ.
    if not project_id and title:
        status, listing = _call("GET", ROUTE, token)
        if status != 200:
            print(f"detail=listing HTTP {status}")
            print("FAILURE=cleanup_failed")
            _emit("failed")
            return 1
        rows = listing if isinstance(listing, list) else (listing or {}).get("items", [])
        matches = [r for r in rows
                   if r.get("title") == title or r.get("title_ar") == title]
        if not matches:
            print("the ambiguous first request left no project behind")
            _emit("not_needed")
            return 0
        print(f"recovered {len(matches)} project(s) by deterministic title")
        failed = False
        for row in matches:
            code, _ = _call("DELETE", f"{ROUTE}/{row['id']}", token)
            print(f"trash {row['id']}: HTTP {code}")
            failed = failed or code != 200
        if failed:
            print("FAILURE=cleanup_failed")
            _emit("failed")
            return 1
        _emit("pass")
        return 0

    if not project_id:
        print("no project id and no deterministic title; nothing can be identified")
        _emit("not_needed")
        return 0

    code, _ = _call("DELETE", f"{ROUTE}/{project_id}", token)
    print(f"trash {project_id}: HTTP {code}")
    if code != 200:
        # **ويسقط، ولا يُحذَّر فقط.** أثرٌ باقٍ في الإنتاج يُقال، لا يُبتلع.
        print("FAILURE=cleanup_failed")
        print("::error::the smoke project remains in production and must be"
              " trashed by hand; it is named with this run id")
        _emit("failed")
        return 1
    _emit("pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
