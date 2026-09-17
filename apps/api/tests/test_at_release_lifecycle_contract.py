"""كلُّ برهانٍ في موضعه من دورة الحياة | Each proof at the stage that can prove it.

**العطبُ الذي وقع، بأرقامه.**

التشغيلة `34754134574` على `main` عند `de5e49ac` سقطت — لا لأنّ الشيفرة
خطأ، بل لأنّ فحصَ المصدر كان يشترط أن يحمل الإنتاجُ شيفرةً **لم تُنشر
بعد**. والدورةُ كانت هكذا:

    يُدمج الفرع
      → Vercel ينشر الوِب فورًا (تكاملُ Git)
      → CI على `main` يفحص https://pubriva.com
      → والخادمُ ما زال `31345edd` لأنّ النشرَ المحروس يقع **بعد** خضرة CI
      → فتسقط رحلةُ القبول
      → فلا يُنشر الخادم
      → فلا تخضرّ

حلقةٌ مغلقة. ومشغّلٌ يُطلب منه أن يُثبت ما لا يستطيع إثباتَه بعد يسقط
سقوطًا صادقًا — والخطأ في موضع السؤال لا في الجواب.

**والدليلُ التشغيليّ كان يقول الصواب أصلًا** (§9): «قبولُ المنتج بوّابةٌ
منفصلة» تُشغَّل بعد النشر. فكان `ci.yml` يناقض الدليلَ الذي في المستودع
نفسِه.

فتُحرس هنا قاعدتان، بنيويًّا لا بالنيّة:

١) **فحصُ المصدر لا يعتمد على إنتاجٍ منشور.** لا مشغّلَ يعمل على `push`
   أو `pull_request` يوجّه فحصًا إلى `pubriva.com`.

٢) **وقبولُ المنتج لا يُشغَّل إلا بيد**، ولا يصمت حين يعجز.
"""
from __future__ import annotations

import pathlib
import re

import pytest

yaml = pytest.importorskip("yaml")

REPO = pathlib.Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"

#: المشغّلُ الوحيد المأذون له بفحص الإنتاج المنشور.
ACCEPTANCE = WORKFLOWS / "production-acceptance.yml"

#: **هدفُ الفحص**، لا كلُّ ذكرٍ لعنوان.
#:
#: والتمييزُ مقصود. `NEXT_PUBLIC_API_BASE_URL: https://athera-api.fly.dev`
#: قائمٌ في `ci.yml` لرقعات المتصفّح المعزولة، وهو **قيمةُ بناء** تُخبز في
#: الحزمة؛ وتلك الرقعاتُ تعترض `**/api/v1/**` فلا يخرج منها نداءٌ إلى
#: الشبكة. فمنعُها يُسقط فحوصًا سليمةً، وحارسٌ يعاقب على شيفرةٍ سليمة
#: يُضعَّف ثمّ لا يحرس شيئًا.
#:
#: والخطرُ الحقيقيّ أن يُوجَّه **هدفُ** رحلةٍ إلى موقعٍ منشور: `PUBRIVA_WEB_URL`.
TARGET_KEYS = ("PUBRIVA_WEB_URL",)
PRODUCTION_HOSTS = ("pubriva.com",)

#: المحفّزاتُ التي تعني «فحصُ مصدرٍ قبل الإصدار».
PRE_RELEASE_TRIGGERS = ("push", "pull_request", "pull_request_target", "schedule")


def _load(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(doc: dict) -> set[str]:
    """محفّزاتُ المشغّل — و`on` تُقرأ `True` في YAML 1.1، فتُلتمس الاثنتان."""
    node = doc.get("on", doc.get(True))
    if isinstance(node, str):
        return {node}
    if isinstance(node, list):
        return set(node)
    if isinstance(node, dict):
        return set(node)
    return set()  # pragma: no cover - مشغّلٌ بلا محفّز لا يعمل أصلًا


def _workflow_files() -> list[pathlib.Path]:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not files:  # pragma: no cover
        pytest.skip("لا مشغّلات في هذه الشجرة")
    return files


# ═════════════ ١ · فحصُ المصدر لا ينتظر نشرًا لم يقع ═════════════


def test_no_pre_release_workflow_tests_deployed_production():
    """**الحلقةُ المغلقة لا تعود.**

    ومشغّلٌ يعمل على `push`/`pull_request` ثمّ يوجّه فحصًا إلى الإنتاج
    يسأل عن شيفرةٍ لم تُنشر — فيسقط صدقًا ويمنع النشرَ الذي كان سيُصلحه.
    """
    offenders: list[str] = []
    for path in _workflow_files():
        if path == ACCEPTANCE:
            continue
        doc = _load(path)
        if not (_triggers(doc) & set(PRE_RELEASE_TRIGGERS)):
            continue
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            # التعليقُ يشرح العطبَ ويسمّي الإنتاج — ولا يُشغّل شيئًا.
            if line.lstrip().startswith("#"):
                continue
            aims_at_production = any(host in line for host in PRODUCTION_HOSTS)
            is_a_target = any(key in line for key in TARGET_KEYS)
            if aims_at_production and is_a_target:
                offenders.append(f"{path.name}:{line_no}: {line.strip()[:70]}")
            # ورحلةُ القبول نفسُها ممنوعةٌ هنا مهما كان هدفُها.
            if "npm run test:acceptance" in line:
                offenders.append(f"{path.name}:{line_no}: runs the acceptance journey")

    assert offenders == [], (
        "فحصُ مصدرٍ يقصد إنتاجًا منشورًا — وهي الحلقةُ التي أسقطت "
        "34754134574:\n  " + "\n  ".join(offenders))


def test_the_guard_would_notice_the_step_coming_back():
    """**وحارسٌ لا يُجرَّب لا يُوثَق به.**

    فيُركَّب هنا مشغّلٌ متخيَّل يحمل العطبَ نفسَه، ويُثبَت أنّ المنطقَ
    أعلاه يمسكه — بلا كتابة ملفٍّ في الشجرة.
    """
    fake = yaml.safe_load(
        "on:\n  push:\n    branches: [main]\njobs:\n  x:\n    steps: []\n")
    assert _triggers(fake) & set(PRE_RELEASE_TRIGGERS)

    bad = "          PUBRIVA_WEB_URL: https://pubriva.com"
    assert any(h in bad for h in PRODUCTION_HOSTS) and any(k in bad for k in TARGET_KEYS)

    # **ولا يُمسك ما ليس خطرًا**: قيمةُ بناءٍ لرقعاتٍ تعترض الشبكة.
    benign = "          NEXT_PUBLIC_API_BASE_URL: https://athera-api.fly.dev"
    assert not (any(h in benign for h in PRODUCTION_HOSTS)
                and any(k in benign for k in TARGET_KEYS))

    # وتعليقٌ يذكر الإنتاج لا يُعدّ مخالفة.
    assert "          # PUBRIVA_WEB_URL: https://pubriva.com".lstrip().startswith("#")


def test_ci_no_longer_runs_the_acceptance_journey():
    """**والرقعةُ المنقولة لم تعد تُنادى من فحص المصدر.**"""
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    runs = [line for line in ci.splitlines()
            if "npm run test:acceptance" in line and not line.lstrip().startswith("#")]
    assert runs == [], f"`ci.yml` ما زالت تنادي رحلةَ القبول: {runs}"


# ═════════════ ٢ · وقبولُ المنتج بوّابةٌ صريحة ═════════════


def test_production_acceptance_workflow_exists_and_is_manual_only():
    assert ACCEPTANCE.exists(), "لا مشغّلَ لقبول المنتج — والبوّابةُ لازمة"
    doc = _load(ACCEPTANCE)
    triggers = _triggers(doc)
    assert triggers == {"workflow_dispatch"}, (
        f"قبولُ المنتج يجب أن يُشغَّل بيدٍ بعد الإصدار وحده، لا بـ{triggers}")


def test_production_acceptance_requires_the_released_commit():
    """**ولا «آخرُ main»**: الرحلةُ تفحص ما نُشر، فتُشتقّ دعاويها منه."""
    doc = _load(ACCEPTANCE)
    node = doc.get("on", doc.get(True))
    inputs = node["workflow_dispatch"]["inputs"]
    assert "expected_release_sha" in inputs
    assert inputs["expected_release_sha"]["required"] is True

    text = ACCEPTANCE.read_text(encoding="utf-8")
    # ويُفحص أنّه التزامٌ مُراجَع على `main` لا فرعٌ لم يُدمج.
    assert "merge-base --is-ancestor" in text
    assert re.search(r"\^\[0-9a-f\]\{40\}\$", text), "لا فحصَ لشكل المعرّف"


def test_production_acceptance_fails_loudly_instead_of_skipping():
    """**والصمتُ ليس نجاحًا.**

    مشغّلٌ يتخطّى حين لا يجد اعتمادًا يُقرأ أخضرَ، فيُظنّ المنتجُ مفحوصًا
    وهو لم يُفحص. فيسقط صراحةً ويقول لماذا.
    """
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert "PRODUCT ACCEPTANCE NOT RUN" in text
    assert "exit 1" in text
    # ولا `continue-on-error` يبتلع السقوط.
    assert "continue-on-error" not in text


def test_the_acceptance_run_destroys_its_artifacts():
    """**ولا يُرفع أثرٌ من رحلةٍ باعتماد** — `error-context.md` يحمل DOM."""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert "rm -rf apps/web/playwright-report apps/web/test-results" in text
    assert "upload-artifact" not in text, "رفعُ أثرٍ من رحلةِ اعتماد"


def test_the_acceptance_workflow_never_writes_to_the_repository():
    doc = _load(ACCEPTANCE)
    assert doc.get("permissions") == {"contents": "read"}


# ═════════════ ٣ · والرقعةُ ما زالت مبلوغة ═════════════


def test_the_acceptance_spec_is_still_reachable_from_some_workflow():
    """**ونقلُها ليس إسقاطَها.** رقعةٌ لا يبلغها مشغّلٌ حبرٌ على ورق."""
    invoked: set[str] = set()
    for path in _workflow_files():
        invoked |= set(re.findall(r"npm run ([A-Za-z0-9:_-]+)",
                                  path.read_text(encoding="utf-8")))
    assert "test:acceptance" in invoked


def test_the_acceptance_spec_no_longer_requires_the_retired_card():
    """**ولا يُحيا منتجٌ متقاعد لأجل فحص.**

    «بُبريفا تقترح» عنوانُ البطاقة الرفيعة التي أزالها RC-0 وأحلّ محلَّها
    رحلةَ البحث. وإبقاءُ الدعوى كان يُلزمنا بإرجاعها — وذاك عكسُ الترتيب.
    """
    spec = (REPO / "apps" / "web" / "tests" / "acceptance.spec.ts").read_text(
        encoding="utf-8")
    live = [line for line in spec.splitlines()
            if "بُبريفا تقترح" in line and not line.lstrip().startswith("//")]
    assert live == [], f"دعوى البطاقة المتقاعدة ما زالت حيّة: {live}"

    # **والمفحوصُ صار أكثر**: رحلةُ RC-0 بمعرّفاتها المستقرّة.
    for testid in ("research-journey", "journey-current-stage",
                   "journey-next-title", "journey-next-why", "journey-failed"):
        assert testid in spec, f"رحلةُ RC-0 غيرُ مفحوصةٍ في القبول: {testid}"


# ═════════════ ٤ · ومشغّلُ الفحص يُثبَّت قبل أن يُنادى ═════════════
#
# **العطبُ الذي أسقط التشغيلة `34765368242`.**
#
# `@playwright/test` ليست في `apps/web/package.json` عن قصد — لا Node على
# جهاز التطوير لإعادة توليد القفل، وإضافتُها بلا قفلٍ مطابق تكسر `npm ci`
# في كلّ مهمّة. فيُثبِّتها كلُّ مشغّلٍ يحتاجها بـ`--no-save`.
#
# وسقطت هذه الخطوةُ من مشغّل القبول وحده. فخرج `npm run test:acceptance`
# بـ`playwright: not found` ورمزِ ١٢٧ — **قبل أن يبلغ المنتجَ أصلًا**.
# والأسوأُ أنّ الرسالةَ تبدو عطبَ منتجٍ لمن يقرأ العنوان وحده.

#: السطرُ المتّبع في المستودع — والنسخةُ تطابق ما يعلنه Next.
RUNNER_INSTALL = "npm install --no-save @playwright/test@^1.51.1"


def _acceptance_steps() -> list[dict]:
    doc = _load(ACCEPTANCE)
    return doc["jobs"]["acceptance"]["steps"]


def _index_of_id(steps: list[dict], step_id: str) -> int:
    """موضعُ خطوةٍ **بمعرّفها** — أدقُّ من مطابقةِ نصّ.

    ومطابقةُ النصّ أخطأت فعلًا: خطوةُ استخراج الأداة تذكر أسماءَ الملفّات
    في حلقتها، فصار `_index_of` يجدها هي لا خطوةَ التشغيل. والمعرّفُ لا
    يلتبس.
    """
    for i, step in enumerate(steps):
        if step.get("id") == step_id:
            return i
    return -1


def _index_of(steps: list[dict], needle: str) -> int:
    """موضعُ أوّل خطوةٍ تُنفّذ `needle` — **بالبنية لا برقم سطر**.

    فرقمُ السطر يتغيّر بأيّ تعليقٍ يُضاف، وحارسٌ يسقط على تعليقٍ يُعطَّل.
    """
    for i, step in enumerate(steps):
        if needle in (step.get("run") or ""):
            return i
    return -1


def test_the_acceptance_workflow_installs_the_pinned_test_runner():
    """**ولا يُنادى مشغّلٌ لم يُثبَّت.**"""
    steps = _acceptance_steps()
    assert _index_of(steps, RUNNER_INSTALL) != -1, (
        "مشغّلُ القبول لا يثبّت مشغّلَ الفحص — وهو العطبُ الذي أسقط "
        f"34765368242. يلزم: {RUNNER_INSTALL}")


def test_the_runner_version_matches_the_rest_of_the_repository():
    """**ونسخةٌ واحدة في المستودع كلِّه.**

    ولا تُستعمل `playwright@1.63.0` التي يجلبها `npx` عرضًا: تلك حزمةُ
    تنزيلِ متصفّحات لا مشغّلُ فحص، وتثبيتُ نسخةٍ أخرى يُخرج ERESOLVE أو
    يُشغّل الفحوصَ على مشغّلٍ لم تُجرَّب عليه.
    """
    pinned = {
        path.name
        for path in _workflow_files()
        if RUNNER_INSTALL in path.read_text(encoding="utf-8")
    }
    assert {"ci.yml", "rc-e2e.yml", ACCEPTANCE.name} <= pinned, (
        f"نسخةُ مشغّل الفحص ليست واحدة — المثبِّتون: {sorted(pinned)}")


def test_the_acceptance_steps_run_in_a_workable_order():
    """**والترتيبُ هو الشرط**: تركيبٌ، فمشغّل، فمتصفّح، ثمّ الرحلة.

    ومشغّلٌ يُثبَّت بعد أن يُنادى لا ينفع، ومتصفّحٌ يُنزَّل قبل التركيب
    يُنزَّل إلى شجرةٍ تُمحى.
    """
    steps = _acceptance_steps()
    ci = _index_of(steps, "npm ci")
    runner = _index_of(steps, RUNNER_INSTALL)
    browser = _index_of(steps, "playwright install --with-deps chromium")
    journey = _index_of(steps, "npm run test:acceptance")

    for label, idx in (("npm ci", ci), ("runner", runner),
                       ("chromium", browser), ("journey", journey)):
        assert idx != -1, f"خطوةٌ مفقودة من مشغّل القبول: {label}"

    assert ci < runner < browser < journey, (
        "ترتيبُ خطوات القبول لا يعمل: "
        f"npm ci={ci} · runner={runner} · chromium={browser} · journey={journey}")


def test_the_test_runner_is_not_added_to_the_web_manifest():
    """**والاتّفاقُ يبقى**: تُثبَّت عابرةً، ولا تدخل بيانَ الحزمة.

    وإدخالُها بلا قفلٍ مطابق يكسر `npm ci` في كلّ مهمّة — وذاك أوسعُ ضررًا
    من الخطوة الساقطة التي أُصلحت.
    """
    import json

    manifest = json.loads(
        (REPO / "apps" / "web" / "package.json").read_text(encoding="utf-8"))
    for section in ("dependencies", "devDependencies", "peerDependencies",
                    "optionalDependencies"):
        found = [n for n in manifest.get(section, {}) if "playwright" in n.lower()]
        assert found == [], (
            f"`{section}` صارت تحمل {found} — والاتّفاق تثبيتٌ عابر في المشغّل")


# ════════════ برهانُ الإعادة بمفتاح على الإنتاج (RC-T1-H2-A) ════════════
#
# **ولمَ حارسٌ ساكن لهذه الخطوة بعينها.**
#
# رحلةُ المتصفّح لا تُرسل `Idempotency-Key` — والوِبُّ لا يُرسله بعد. فلو
# حُذفت خطوةُ البرهان يومًا لبقي القبولُ أخضرَ وهو لا يمسّ H2-A بحرف،
# **ولا حارسَ مخطَّطٍ يكشف ذلك**: `verify_release_schema.py` لا يفحص جدولَ
# التكرار أصلًا. فالحذفُ يمرّ صامتًا، وذاك أسوأُ من سقوطٍ صريح.

#: ملفّا البرهان — ويُقرآن نصًّا لا يُستوردان: هما يعملان في المشغّل.
KEYED_SMOKE = REPO / ".github" / "acceptance" / "h2a_keyed_replay.py"
RECORD_PROOF = REPO / ".github" / "acceptance" / "h2a_record_proof.py"
CLEANUP = REPO / ".github" / "acceptance" / "h2a_cleanup.py"


def test_the_acceptance_workflow_carries_the_keyed_replay_smoke():
    """**والدعوى تُطرق بطلبٍ حقيقيّ، لا تُفترض من خضرةِ المتصفّح.**"""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    for needle in ("Idempotency-Key", "Idempotency-Replayed",
                   "/api/v1/workspace/projects", "expected_release_sha",
                   "PUBRIVA_ACCEPT_EMAIL", "PUBRIVA_ACCEPT_PASSWORD"):
        assert needle in text, f"مشغّلُ القبول لا يذكر {needle!r}"

    assert KEYED_SMOKE.exists(), "سكربتُ برهان الإعادة مفقود"
    assert RECORD_PROOF.exists(), "سكربتُ برهان الصفّ مفقود"

    smoke = KEYED_SMOKE.read_text(encoding="utf-8")
    assert "Idempotency-Key" in smoke, "البرهانُ لا يُرسل الترويسة"

    # **ووجودُ الاسم ليس دعوى.** أوّلُ صياغةٍ لهذا الحارس اكتفت بأن يَرِد
    # `idempotency-replayed` في الملفّ — ومرّت عليها إزالةُ الدعوى نفسِها،
    # لأنّ فحصَ الطلب الأوّل (ألّا يُعلن نفسَه إعادةً) يذكر الاسمَ أيضًا.
    # فيُشترط **الشرطُ بعينه** على جواب الإعادة، لا ذكرُ الترويسة.
    assert 'headers2.get("idempotency-replayed") != "true"' in smoke, (
        "البرهانُ لا يشترط `Idempotency-Replayed: true` على جواب الإعادة")
    assert 'raise Failure("replay_header_missing"' in smoke, (
        "لا صنفَ سقوطٍ لغياب ترويسة الإعادة")
    # والطلبُ الأوّل لا يُعلن نفسَه إعادةً — وهذه دعوى ثانية مستقلّة.
    assert 'headers1.get("idempotency-replayed") == "true"' in smoke, (
        "البرهانُ لا يرفض أن يُعلن التنفيذُ الأوّل نفسَه إعادةً")
    # وهويّةُ المورد وجسمُ الجواب يُطابَقان، لا الحالُ وحدها.
    assert 'raise Failure("resource_id_mismatch"' in smoke, "لا مطابقةَ لمعرّف المورد"
    assert 'raise Failure("stored_response_mismatch"' in smoke, "لا مطابقةَ لجسم الجواب"


def test_the_record_proof_reads_production_in_a_read_only_transaction():
    """**ولا يُقرأ الإنتاجُ بمعاملةٍ قابلةٍ للكتابة.**

    والعلامةُ صريحةٌ ويُتحقّق منها في التشغيل أيضًا (`SHOW`)، فلا يكفي
    أن تُكتب العبارةُ ثمّ يُفترض أنّها نفذت.
    """
    proof = RECORD_PROOF.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in proof, "لا علامةَ قراءةٍ فقط في البرهان"
    assert "transaction_read_only" in proof, "لا تحقّقَ من وضع المعاملة"
    assert "ROLLBACK" in proof or "rollback()" in proof, "المعاملةُ لا تُرجَع"

    # ولا تُعطَّل سياسةُ الصفّ لتُقرأ، ولا يُستعمل اعتمادُ ترحيل.
    # **ومنعُ ذكرِ الاسم ليس منعَ الاعتماد عليه.** أوّلُ صياغةٍ منعت نصَّ
    # `BYPASSRLS` كلَّه، فصارت تسقط على البرهان وهو **يرفضه** — ولا بدّ له
    # أن يقرأ `rolbypassrls` ليرفضه. فيُمنع الاعتمادُ لا الذكر، ويبقى
    # الإنفاذُ محروسًا في فحصه هو.
    for forbidden in ("SECURITY DEFINER", "DISABLE ROW LEVEL SECURITY",
                      "DATABASE_MIGRATION_URL", "SET ROLE ", "SET SESSION AUTHORIZATION"):
        assert forbidden not in proof, f"البرهانُ يعتمد {forbidden!r}"

    for write in ("INSERT INTO", "UPDATE ", "DELETE FROM", "TRUNCATE",
                  "CREATE TABLE", "ALTER TABLE", "DROP TABLE", "GRANT ", "REVOKE "):
        assert write not in proof.upper().replace("SET TRANSACTION READ ONLY", ""), (
            f"البرهانُ يحمل عبارةَ كتابة: {write!r}")


def test_the_keyed_smoke_runs_before_the_browser_journey():
    """**وهو شرطٌ لا خطوةٌ موازية.**

    فلو سقط البرهانُ بعد رحلةِ المتصفّح لَقيل «القبولُ أخضر» ثمّ نُقض —
    والترتيبُ هو ما يجعله بوّابة.
    """
    steps = _acceptance_steps()
    staging = _index_of_id(steps, "harness")
    smoke = _index_of_id(steps, "keyed")
    record = next((i for i, x in enumerate(steps)
                   if RECORD_PROOF.name in (x.get("run") or "")
                   and x.get("id") != "harness"), -1)
    journey = _index_of(steps, "npm run test:acceptance")

    assert staging != -1, "خطوةُ استخراج الأداة مفقودة"
    assert smoke != -1, "خطوةُ برهان الإعادة مفقودة من مشغّل القبول"
    assert record != -1, "خطوةُ برهان الصفّ مفقودة من مشغّل القبول"
    assert journey != -1, "رحلةُ المتصفّح مفقودة"
    # والاستخراجُ قبل التشغيل، والتشغيلُ قبل المتصفّح.
    assert staging < smoke < record < journey, (
        "ترتيبُ البوّابة لا يعمل: "
        f"harness={staging} · keyed={smoke} · record={record} · journey={journey}")


def test_the_keyed_smoke_cleans_up_and_destroys_its_credential_state():
    """**ولا يُترك أثرٌ ولا رمزٌ يعيش إلى رحلةِ المتصفّح.**"""
    steps = _acceptance_steps()
    trash = _index_of_id(steps, "cleanup")
    destroy = _index_of(steps, "h2a_smoke_token")
    journey = _index_of(steps, "npm run test:acceptance")

    assert trash != -1, "لا تنظيفَ للبحث المُستهلَك عبر مسار المنتج"
    # **والمسارُ مسارُ المنتج** — ويُقرأ في الأداة، فهناك يعمل.
    assert "/api/v1/workspace/projects" in CLEANUP.read_text(encoding="utf-8"), (
        "أداةُ التنظيف لا تنادي مسارَ المنتج")
    assert destroy != -1, "لا إتلافَ لحالة الاعتماد المؤقّتة"
    assert destroy < journey, "الرمزُ يعيش إلى رحلةِ المتصفّح"

    # **والتنظيفُ بمسار المنتج لا بـSQL** — والحذفُ هناك تأجيلٌ لا إتلاف.
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert "DELETE FROM" not in text.upper(), "تنظيفٌ بـSQL في مشغّل القبول"
    for step in (steps[trash], steps[destroy]):
        assert "always()" in str(step.get("if", "")), (
            "خطوةُ التنظيف/الإتلاف لا تعمل عند السقوط")


def test_the_keyed_smoke_never_prints_a_secret():
    """**ولا سرٌّ يُطبع ولا يُرفع** — ولا `set -x` ولا `curl -v` في مسارٍ باعتماد."""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    smoke = KEYED_SMOKE.read_text(encoding="utf-8")
    proof = RECORD_PROOF.read_text(encoding="utf-8")

    for blob, label in ((text, "workflow"), (smoke, "keyed smoke"), (proof, "record proof")):
        assert "set -x" not in blob, f"{label}: `set -x` يُفرِغ الأسرار"
        assert "curl -v" not in blob, f"{label}: `curl -v` يُفرِغ الترويسات"
        for leak in ('echo "${PUBRIVA_ACCEPT_PASSWORD}"',
                     'echo "${PUBRIVA_ACCEPT_EMAIL}"',
                     'echo "${access_token}"',
                     "echo $PUBRIVA_ACCEPT_PASSWORD",
                     "echo $FLY_API_TOKEN"):
            assert leak not in blob, f"{label}: يطبع سرًّا — {leak!r}"

    # والمُخرَجاتُ غيرُ السرّيّة وحدها تعبُر إلى الخطوات التالية.
    assert "GITHUB_OUTPUT" in smoke, "البرهانُ لا يُصدّر شيئًا"
    for secret in ("access_token", "refresh_token", "raw_key", "password"):
        assert f'_emit("{secret}"' not in smoke, f"سرٌّ يُصدَّر كمُخرَج: {secret}"


# ════════════ طوبولوجيا التنفيذ: مصدرانِ لا مصدر (RC-T1-H2-A) ════════════
#
# **والعطبُ الذي يحرسه هذا الفحصُ كان قاتلًا ومقيسًا.**
#
# شجرةُ العمل هي `expected_release_sha` — المنتجُ المنشور — وملفّا برهان
# H2-A ليسا فيه: هما أحدثُ منه. فكان المشغّلُ يُشغّل
# `python3 .github/acceptance/h2a_keyed_replay.py` من شجرةٍ لا تحمله،
# فيسقط بـ`No such file or directory` **قبل أن يلمس الإنتاج**. وقد أُعيد
# إنتاجُ ذلك في شجرةٍ مُستخرَجةٍ عند ذلك الالتزام بعينه.
#
# ولا يُحَلّ بتبديل الجذر إلى `main`: لو فُعل لَفحصت رحلةُ المتصفّح شيفرةً
# غيرَ المنشورة. فالمصدرانِ يبقيان متمايزَين، وهذا الفحصُ يُثبّت التمييز.



def test_the_harness_is_staged_from_the_workflow_commit_not_the_product_tree():
    """**والأداةُ تُستخرَج من `GITHUB_SHA`، والجذرُ يبقى المنتجَ المنشور.**"""
    text = ACCEPTANCE.read_text(encoding="utf-8")

    # الجذرُ ما زال المنتجَ المنشور — ولا يُبدَّل إلى `main`.
    assert "ref: ${{ inputs.expected_release_sha }}" in text, (
        "جذرُ الشجرة ليس الالتزامَ المنشور — رحلةُ المتصفّح تفحص غيرَ المنشور")

    # والأداةُ من التزام المشغّل بعينه.
    assert "GITHUB_SHA" in text or "${{ github.sha }}" in text, (
        "لا مرجعَ لالتزام المشغّل — فمن أين تُستخرَج الأداة؟")
    # **ويُقرأ جسمُ خطوةِ الاستخراج بعينه**، لا الملفُّ كلُّه: ذكرُ اسمٍ
    # في تعليقٍ ليس استخراجًا.
    steps = _acceptance_steps()
    staging = next((x for x in steps if x.get("id") == "harness"), None)
    assert staging is not None, "لا خطوةَ تستخرج الأداة"
    body = staging.get("run") or ""
    assert 'git show "${GITHUB_SHA}:.github/acceptance/' in body, (
        "الأداةُ لا تُستخرَج من التزام المشغّل بـ`git show`")
    # **والأسماءُ تُشتقّ من الثوابت، ولا تُكرَّر نصًّا.** وتكرارُها ثلاثةً
    # في سطرٍ واحد أسقط ماسحَ الأسرار (`generic-api-key`، إنتروبيا ٣٫٥):
    # بلاغٌ كاذب، لكنّ إسكاتَه بقائمةِ سماحٍ للمستودع كلِّه يُخفي بلاغًا
    # صادقًا غدًا. فالمصدرُ واحد، ولا نصَّ مُعادًا يُشبه سرًّا.
    for path in (KEYED_SMOKE, RECORD_PROOF, CLEANUP):
        assert path.name in body, f"لا استخراجَ لـ{path.name}"

    # ويُتحقّق أنّه التزامٌ حقيقيٌّ ومن `main` المُراجَعة.
    assert 'git cat-file -e "${GITHUB_SHA}^{commit}"' in text, (
        "لا تحقّقَ من أنّ التزامَ المشغّل التزامٌ أصلًا")
    assert 'git merge-base --is-ancestor "${GITHUB_SHA}" origin/main' in text, (
        "أداةُ فحصٍ من التزامٍ غيرِ مُراجَع")


def test_the_keyed_smoke_never_runs_from_the_product_tree():
    """**والانحدارُ إلى مسار الجذر يُرفض بعينه** — وهو صيغةُ العطب الأصليّة."""
    steps = _acceptance_steps()

    for needle in ("python3 .github/acceptance/h2a_keyed_replay.py",
                   "python3 .github/acceptance/h2a_record_proof.py",
                   "base64 -w0 .github/acceptance/h2a_record_proof.py"):
        for step in steps:
            assert needle not in (step.get("run") or ""), (
                f"المشغّلُ يُشغّل الأداةَ من شجرة المنتج: {needle!r}")

    # والتشغيلُ من الموضع المُنفصل المُستخرَج.
    keyed = _index_of(steps, KEYED_SMOKE.name)
    assert keyed != -1, "خطوةُ برهان الإعادة مفقودة"
    body = steps[keyed].get("run") or ""
    assert "harness" in body.lower() or "RUNNER_TEMP" in body, (
        "برهانُ الإعادة لا يُشغَّل من أداةٍ مُستخرَجةٍ منفصلة")

    # والأداةُ تُمحى قبل رحلةِ المتصفّح.
    destroy = _index_of(steps, "h2a-harness")
    journey = _index_of(steps, "npm run test:acceptance")
    assert destroy != -1, "الأداةُ المُستخرَجة لا تُمحى"
    assert destroy < journey, "الأداةُ تعيش إلى رحلةِ المتصفّح"


def test_the_record_proof_requires_the_runtime_role_and_not_merely_prints_it():
    """**والطبعُ ملاحظةٌ لا إنفاذ.**

    ودعوى «قُرئ بسياسة الصفّ نافذة» لا تصحّ إن كان الاتصالُ فائقًا أو
    متجاوزًا. فرابطٌ يُضبط يومًا باعتماد الترحيل يجب أن **يُسقط** البرهان،
    لا أن يُسجَّل في سطرٍ ويمضي.
    """
    proof = RECORD_PROOF.read_text(encoding="utf-8")

    assert 'RUNTIME_ROLE = "athera_app"' in proof, "لا دورَ متوقَّعٌ مُعلَن"
    assert "rolsuper" in proof and "rolbypassrls" in proof, "لا قراءةَ لأعلام الدور"
    # والإنفاذُ شرطٌ يُسقط، لا سطرُ طبع.
    assert "if who != RUNTIME_ROLE:" in proof, "الدورُ لا يُشترط"
    assert "if is_super:" in proof, "الدورُ الفائق لا يُرفض"
    assert "if bypasses:" in proof, "تجاوزُ سياسة الصفّ لا يُرفض"
    assert proof.count("FAILURE=db_read_only_verification_failed") >= 4, (
        "أصنافُ السقوط أقلُّ من الشروط المُعلَنة")
    # والسياقُ يُقرأ بعد ضبطه، فصفرُ الصفوف لا يُقرأ «لا صفّ» وهو «لا سياق».
    assert "current_setting" in proof, "لا قراءةَ للسياق بعد ضبطه"
    assert "RLS_CONTEXT_APPLIED" in proof, "لا إثباتَ لتطبيق السياق"


def test_cleanup_reports_truthfully_and_fails_when_it_cannot_clean():
    """**وتنظيفٌ يُخفق لا يُقال عنه «نُقل إلى السلّة».**"""
    text = ACCEPTANCE.read_text(encoding="utf-8")
    assert CLEANUP.exists(), "أداةُ التنظيف مفقودة"
    cleanup = CLEANUP.read_text(encoding="utf-8")

    # حالٌ صريحةٌ بثلاث قيم، والملخّصُ يقرؤها ولا يفترضها.
    for status in ("pass", "not_needed", "failed"):
        assert f'_emit("{status}")' in cleanup, f"لا حالَ `{status}`"
    assert "cleanup_status" in text, "الملخّصُ لا يقرأ حالَ التنظيف"
    assert "steps.cleanup.outputs.cleanup_status" in text, (
        "حالُ التنظيف لا تُمرَّر إلى الملخّص")
    assert "trashed through the product route |" not in text, (
        "الملخّصُ يدّعي النقلَ إلى السلّة بلا شرط")

    # ══ ويسقط، ولا يُحذّر فقط — ويُقاس بالبنية لا بحضورِ نصّ ══
    #
    # **وأوّلُ صياغةٍ لهذا الشرط لم تعضّ.** كانت تشترط ورودَ
    # `FAILURE=cleanup_failed` في الملفّ، وهو يَرِد في فرعِ الاحتياط
    # بالعنوان أيضًا — فإضعافُ الفرع الأساسيّ إلى تحذيرٍ مرّ عليها.
    # فيُقرأ **الفرعُ بعينه**: جوابٌ غيرُ ٢٠٠ ⇒ حالٌ `failed` ⇒ خروجٌ بواحد.
    import ast as _ast

    tree = _ast.parse(cleanup)
    main = next((n for n in tree.body
                 if isinstance(n, _ast.FunctionDef) and n.name == "main"), None)
    assert main is not None, "لا دالّةَ `main` في أداة التنظيف"

    def _emits_failed_and_returns_one(node) -> bool:
        emits = any(
            isinstance(c, _ast.Call) and getattr(c.func, "id", "") == "_emit"
            and c.args and isinstance(c.args[0], _ast.Constant)
            and c.args[0].value == "failed"
            for c in _ast.walk(node))
        returns = any(
            isinstance(r, _ast.Return) and isinstance(r.value, _ast.Constant)
            and r.value.value == 1
            for r in _ast.walk(node))
        return emits and returns

    non_ok_branches = [
        node for node in _ast.walk(main)
        if isinstance(node, _ast.If)
        and any(isinstance(cmp_, _ast.Compare)
                and any(isinstance(o, _ast.NotEq) for o in cmp_.ops)
                and any(isinstance(c, _ast.Constant) and c.value == 200
                        for c in cmp_.comparators)
                for cmp_ in _ast.walk(node.test))]
    assert non_ok_branches, "لا فرعَ يفحص أنّ جوابَ الحذف ليس ٢٠٠"
    assert all(_emits_failed_and_returns_one(b) for b in non_ok_branches), (
        "فرعُ الحذف غيرِ الناجح لا يُصدر `failed` ولا يسقط — تحذيرٌ لا إنفاذ")

    # ولا حالَ `failed` تُصدَر بلا سقوط.
    for node in _ast.walk(main):
        if (isinstance(node, _ast.Call) and getattr(node.func, "id", "") == "_emit"
                and node.args and isinstance(node.args[0], _ast.Constant)
                and node.args[0].value == "failed"):
            break
    else:  # pragma: no cover
        raise AssertionError("أداةُ التنظيف لا تُصدر حالَ إخفاقٍ أبدًا")

    # والحالةُ الغامضةُ تُعالَج: معرّفٌ مفقودٌ وعنوانٌ حتميّ.
    assert "SMOKE_TITLE" in cleanup, "لا احتياطَ بالعنوان الحتميّ"
    assert "SMOKE_TITLE" in text, "العنوانُ لا يُمرَّر إلى التنظيف"
    # ولا SQL ولا إتلاف.
    assert "DELETE FROM" not in cleanup.upper(), "تنظيفٌ بـSQL"


# ════════════ تجاهُلُ الأسرار: بصمةٌ مُثبَّتةٌ لا قائمةُ سماح ════════════

GITLEAKS_IGNORE = REPO / ".gitleaksignore"
GITLEAKS_CONFIG = REPO / ".gitleaks.toml"

#: بصمةُ gitleaks: التزامٌ (٤٠ ست عشريًّا) : ملفّ : قاعدة : سطر.
_FINGERPRINT = re.compile(r"^[0-9a-f]{40}:[^:]+:[A-Za-z0-9._-]+:\d+$")


def test_secret_scanner_exceptions_are_pinned_fingerprints_not_allowlists():
    """**وتجاهُلُ بلاغٍ كاذبٍ يُثبَّت ببصمته، ولا يُوسَّع نمطًا.**

    وبصمةٌ تحمل التزامًا وملفًّا وقاعدةً وسطرًا لا تُخفي غيرَها: لا سطرًا
    آخرَ في الملفّ نفسِه، ولا الالتزامَ التالي. أمّا قائمةُ سماحٍ بنمطٍ أو
    بمسارٍ فتجعل بلاغًا صادقًا غدًا يمرّ صامتًا — وفحصٌ أحمرُ أفضلُ من فحصٍ
    أخضرَ لا يفحص.

    ## ولا خروجَ مبكّرًا في هذا الفحص

    **وأوّلُ صياغةٍ كانت تخرج مبكّرًا إن غاب `.gitleaksignore`** — وغيابُه
    هو حالُ المستودع الطبيعيّة. فصار حارسُ `.gitleaks.toml` شيفرةً ميّتة:
    إعدادٌ بـ`regexes = [".*"]` — سماحٌ يُسكِت كلَّ قاعدةٍ في المستودع —
    كان يمرّ والفحوصُ كلُّها خضراء.

    فالحارسانِ شرطُهما مختلف، ولا يُعلَّق أحدُهما على وجود الآخر:

      • **إعدادُ gitleaks يُفحَص دائمًا** — وجودُه هو الخطر، لا غيابُه.
      • **وملفُّ التجاهُل يُفحَص إن وُجد** — وغيابُه هو الحالُ المُفضَّلة.

    ولا `return` في هذا الفحص بعد اليوم، فلا يعود الفخُّ نفسُه.
    """
    # ══ ١ · الإعداد: يُفحَص بلا شرط ══
    #
    # وغيابُ `.gitleaks.toml` هو المُفضَّل (والماسحُ يقول
    # «no gitleaks config found … using default»). فإن وُجد فُحص، ولا
    # يُقبل فيه سماحٌ بنمطٍ ولا بمسار.
    if GITLEAKS_CONFIG.exists():
        config = GITLEAKS_CONFIG.read_text(encoding="utf-8")
        for loose in ("[[allowlist", "[allowlist", "allowlists",
                      "regexes", "paths", "stopwords"):
            assert loose not in config, (
                f"إعدادُ gitleaks يحمل سماحًا واسعًا: {loose!r} — "
                "والاستثناءُ يُثبَّت ببصمةٍ في `.gitleaksignore`، لا بنمطٍ هنا")

    # ══ ٢ · ملفُّ التجاهُل: يُفحَص إن وُجد وحدَه ══
    if GITLEAKS_IGNORE.exists():
        lines = [
            line.strip()
            for line in GITLEAKS_IGNORE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert lines, "ملفُّ التجاهُل بلا بصمةٍ واحدة — يُحذف بدل أن يبقى فارغًا"
        for line in lines:
            assert _FINGERPRINT.match(line), (
                f"سطرٌ ليس بصمةً مُثبَّتة: {line!r} — "
                "لا أنماطَ ولا مساراتٍ في تجاهُل الأسرار")
