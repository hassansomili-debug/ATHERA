"""RC-T1-H2-A — برهانُ الإعادة على الإنتاج | the keyed replay proof.

**ولمَ سكربتٌ لا أسطرٌ في YAML.** هذا برهانٌ بدعاوى مرتّبة، وكتابتُه
متتاليًا داخل `run:` يجعله غيرَ مقروءٍ وغيرَ قابلٍ للتشغيل خارج المشغّل.

**ولا يُطبع سرّ.** البريدُ وكلمةُ المرور والرمزُ والمفتاحُ الخام لا يُطبع
منها حرف. وما يُطبع: حالاتُ HTTP، ومعرّفُ البحث، وبصمةُ المفتاح، ونتائجُ
الدعاوى. والمكتبةُ القياسيّةُ وحدها — فلا تثبيتَ حزمٍ في مسارٍ باعتماد.

والفشلُ يُصنَّف بصنفٍ آمن (`FAILURE=<category>`) ولا يُفرَغ معه جسمُ طلبٍ
ولا ترويسةُ تفويض.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request

API = os.environ.get("PUBRIVA_API_URL", "https://athera-api.fly.dev")
ROUTE = "/api/v1/workspace/projects"
OPERATION = f"POST {ROUTE}"
#: شكلُ المفتاح كما يفرضه H2-A — ولا محرفَ خارجه.
KEY_SHAPE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class Failure(Exception):
    """سقوطٌ مصنَّف — والصنفُ وحده يُطبع، لا الحمولة."""

    def __init__(self, category: str, detail: str = "") -> None:
        super().__init__(category)
        self.category = category
        self.detail = detail


def _call(method: str, path: str, *, token: str | None = None,
          body: dict | None = None, headers: dict | None = None,
          category: str) -> tuple[int, dict, dict]:
    """نداءٌ واحد — ويُعيد الحالَ والجسمَ والترويسات، ولا يطبع شيئًا."""
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read().decode("utf-8", "replace")
            return (response.status, json.loads(payload) if payload else {},
                    {k.lower(): v for k, v in response.headers.items()})
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            parsed = {}
        return (exc.code, parsed, {k.lower(): v for k, v in exc.headers.items()})
    except Exception as exc:  # الشبكةُ تسقط بأشكال، والصنفُ يُوحَّد
        raise Failure(category, type(exc).__name__) from exc


def _claims(token: str) -> tuple[str, str]:
    """`sub` و`tid` من حمولة الرمز.

    **ولا تحقّقَ من توقيعٍ هنا ولا تجاوزَ له**: الرمزُ أصدرته الواجهةُ
    وتحقّقت منه عند الدخول، وهذه قراءةُ معرّفَين لبناء استعلامٍ لاحق.
    """
    try:
        part = token.split(".")[1]
        pad = "=" * (-len(part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(part + pad))
        return str(payload["sub"]), str(payload["tid"])
    except Exception as exc:
        raise Failure("login_failed", "token payload unreadable") from exc


def _emit(name: str, value: str) -> None:
    """مُخرَجٌ غيرُ سرّيّ فقط — ولا رمزَ ولا مفتاحَ خامّ يعبُر من هنا."""
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    print(f"{name}={value}")


def main() -> int:
    email = os.environ.get("PUBRIVA_ACCEPT_EMAIL", "")
    password = os.environ.get("PUBRIVA_ACCEPT_PASSWORD", "")
    if not email or not password:
        raise Failure("login_failed", "acceptance credentials absent")

    marker = os.environ.get("SMOKE_MARKER") or secrets.token_hex(4)
    title = f"اختبار H2-A الإنتاجي {marker}"
    # **ويُصدَّر العنوانُ قبل أن يُرسَل طلبٌ واحد.**
    #
    # فالجوابُ الأوّل قد ينقطع بعد أن يُنشئ الخادمُ البحث — وهي الحالةُ
    # الغامضةُ التي وُجد H2 لها. فلو صُدِّر العنوانُ بعد النجاح لَما وجد
    # التنظيفُ ما يتعلّق به في أسوأ الحالات بعينها. وهو غيرُ سرّيّ.
    _emit("smoke_title", title)

    # ــ المفتاحُ عشوائيٌّ آمن، وشكلُه مفروضٌ قبل الإرسال ــ
    raw_key = secrets.token_urlsafe(32).replace(".", "-")[:64]
    if not KEY_SHAPE.match(raw_key):
        raise Failure("replay_failed", "generated key does not match the H2-A shape")
    digest = hashlib.sha256(raw_key.encode()).hexdigest()

    # ══ ١ · الدخول ══
    status, token_body, _ = _call("POST", "/api/v1/auth/login",
                                  body={"email": email, "password": password},
                                  category="login_failed")
    if status != 200 or "access_token" not in token_body:
        raise Failure("login_failed", f"HTTP {status}")
    token = token_body["access_token"]
    actor_id, tenant_id = _claims(token)
    print("login: HTTP 200")

    # **ويُحفظ الرمزُ لخطوةِ التنظيف وحدها**، بصلاحياتٍ ضيّقة، ويُمحى بعدها.
    temp = os.environ.get("RUNNER_TEMP", "/tmp")
    token_path = os.path.join(temp, "h2a_smoke_token")
    with open(os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600),
              "w", encoding="utf-8") as handle:
        handle.write(token)

    # ══ ٢ · الطلبُ الأوّل بمفتاح ══
    body = {"title_ar": title, "starting_from": "empty"}
    status1, first, headers1 = _call("POST", ROUTE, token=token, body=body,
                                     headers={"Idempotency-Key": raw_key},
                                     category="first_create_failed")
    if status1 != 201:
        raise Failure("first_create_failed", f"HTTP {status1}")
    project_id = first.get("id")
    if not project_id:
        raise Failure("first_create_failed", "response carries no id")
    _emit("project_id", str(project_id))
    print(f"first create: HTTP 201 · project {project_id}")
    if headers1.get("idempotency-replayed") == "true":
        raise Failure("replay_header_missing",
                      "the first execution announced itself as a replay")

    # ══ ٣ · الإعادة: المفتاحُ نفسُه والجسمُ نفسُه ══
    status2, second, headers2 = _call("POST", ROUTE, token=token, body=body,
                                      headers={"Idempotency-Key": raw_key},
                                      category="replay_failed")
    if status2 != 201:
        raise Failure("replay_failed", f"HTTP {status2}")
    if headers2.get("idempotency-replayed") != "true":
        raise Failure("replay_header_missing", "header absent on the second response")
    if second.get("id") != project_id:
        raise Failure("resource_id_mismatch", "a different resource was returned")
    if second != first:
        raise Failure("stored_response_mismatch", "the replayed body is not the original")
    print("replay: HTTP 201 · Idempotency-Replayed: true · same project id")

    # ══ ٤ · برهانُ المجال من الواجهة: بحثٌ واحدٌ لا اثنان ══
    status3, listing, _ = _call("GET", ROUTE, token=token,
                                category="domain_duplicate")
    if status3 != 200:
        raise Failure("domain_duplicate", f"listing HTTP {status3}")
    rows = listing if isinstance(listing, list) else listing.get("items", [])
    same_id = [r for r in rows if str(r.get("id")) == str(project_id)]
    same_title = [r for r in rows if r.get("title") == title
                  or r.get("title_ar") == title]
    if len(same_id) != 1:
        raise Failure("domain_duplicate",
                      f"{len(same_id)} active projects carry the created id")
    if len(same_title) != 1:
        raise Failure("domain_duplicate",
                      f"{len(same_title)} active projects carry the smoke title")
    print("domain listing: exactly one active project for this smoke")

    _emit("tenant_id", tenant_id)
    _emit("actor_user_id", actor_id)
    _emit("key_digest", digest)
    _emit("operation", OPERATION)
    _emit("replayed", "true")
    print("H2A_API_SMOKE=pass")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"FAILURE={failure.category}")
        if failure.detail:
            print(f"detail={failure.detail}")
        print(f"::error::H2-A keyed replay smoke failed: {failure.category}")
        sys.exit(1)
