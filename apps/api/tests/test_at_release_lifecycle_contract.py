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
    for forbidden in ("BYPASSRLS", "SECURITY DEFINER", "DISABLE ROW LEVEL SECURITY",
                      "DATABASE_MIGRATION_URL", "SET ROLE"):
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
    smoke = _index_of(steps, "h2a_keyed_replay.py")
    record = _index_of(steps, "h2a_record_proof.py")
    journey = _index_of(steps, "npm run test:acceptance")

    assert smoke != -1, "خطوةُ برهان الإعادة مفقودة من مشغّل القبول"
    assert record != -1, "خطوةُ برهان الصفّ مفقودة من مشغّل القبول"
    assert journey != -1, "رحلةُ المتصفّح مفقودة"
    assert smoke < record < journey, (
        "ترتيبُ البوّابة لا يعمل: "
        f"keyed={smoke} · record={record} · journey={journey}")


def test_the_keyed_smoke_cleans_up_and_destroys_its_credential_state():
    """**ولا يُترك أثرٌ ولا رمزٌ يعيش إلى رحلةِ المتصفّح.**"""
    steps = _acceptance_steps()
    trash = _index_of(steps, "/api/v1/workspace/projects/")
    destroy = _index_of(steps, "h2a_smoke_token")
    journey = _index_of(steps, "npm run test:acceptance")

    assert trash != -1, "لا تنظيفَ للبحث المُستهلَك عبر مسار المنتج"
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
