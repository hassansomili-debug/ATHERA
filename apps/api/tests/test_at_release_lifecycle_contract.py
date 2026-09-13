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
