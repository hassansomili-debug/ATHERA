"""هويّةُ مشروع الإنتاج: مصدرٌ واحد مُراجَع | One reviewed source, not two secrets.

**العطب: هويّةٌ واحدة مكتوبةٌ في موضعين يُحرَّران يدويًّا.**

`scripts/migrate_production.py` يقارن `--confirm` بمرجعِ المشروع المستخرَج من
`DATABASE_MIGRATION_URL` نفسه — حارسٌ ضدّ الخطأ المطبعيّ. وكان طرفُ المقارنة
الآخر يصل من سرٍّ ثانٍ (`SUPABASE_PROJECT_REF`)، فصار للهويّة الواحدة مصدران
لا يقرن أحدَهما بالآخر شيء. وانحرفا، فرُفضت ثمانِ تشغيلاتِ إصدار عند الحارس.

**والعلاجُ ليس تصحيح السرّ بل إزالةُ التكرار.** مرجعُ المشروع مُعرِّفٌ لا
اعتماد: لا يفتح شيئًا ولا يُصادِق أحدًا، ويظهر في كلّ رابطٍ إلى لوحة
Supabase. فصار ثابتًا مُراجَعًا في المشغّل، والسرُّ للاعتماد وحده.

**ولا يُضعِف ذلك حارسًا واحدًا** — وهذه الفحوص تحرس ذلك بعينه.
"""
from __future__ import annotations

import pathlib

import pytest

yaml = pytest.importorskip("yaml")

REPO = pathlib.Path(__file__).resolve().parents[3]
WORKFLOW = REPO / ".github" / "workflows" / "production-release.yml"
RUNBOOK = REPO / "docs" / "runbooks" / "production-release.md"
MIGRATE = REPO / "scripts" / "migrate_production.py"

#: هويّةُ مشروع الإنتاج كما أقرّها المالك — **مُعرِّفٌ لا اعتماد**.
REVIEWED_REF = "ofyabufybofbxwkfalgs"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow(workflow_text: str) -> dict:
    return yaml.safe_load(workflow_text)


def _triggers(workflow: dict) -> dict:
    # `on` مفتاحٌ يقرؤه PyYAML قيمةً منطقية `True` — وهو فخُّ YAML المعروف.
    return workflow[True] if True in workflow else workflow["on"]


# ═════════ تشغيلُ شيفرةِ المشغّل نفسها، لا نسخةٍ منها ═════════
#
# **ونسختان تتباعدان.** فحصٌ يُعيد كتابة منطق القرار يبقى أخضر بعد أن
# يتغيّر المشغّل — فيُستخرج النصُّ من الملفّ ويُنفَّذ كما هو.


def _step(workflow: dict, job: str, *, step_id: str) -> dict:
    return next(s for s in workflow["jobs"][job]["steps"] if s.get("id") == step_id)


@pytest.fixture(scope="module")
def head_script(workflow: dict) -> str:
    """كتلةُ بايثون التي تشتقّ الرأس، منزوعةَ إزاحةِ المستند المضمَّن."""
    import re
    import textwrap

    body = _step(workflow, "source-preflight", step_id="head")["run"]
    match = re.search(r"python3 - <<'PY'[^\n]*\n(.*?)\n\s*PY\b", body, re.S)
    assert match, "تعذّر استخراج كتلة اشتقاق الرأس"
    return textwrap.dedent(match.group(1))


@pytest.fixture(scope="module")
def mode_script(workflow: dict) -> str:
    return _step(workflow, "db-release-gate", step_id="mode")["run"]


def _run_head(script: str, root: pathlib.Path) -> tuple[int, str, str]:
    import subprocess
    import sys
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as handle:
        handle.write(script)
        path = handle.name
    proc = subprocess.run([sys.executable, path], capture_output=True, text=True,
                          cwd=root)
    return proc.returncode, proc.stdout, proc.stderr


def _run_mode(script: str, mode: str, before: str, source: str,
              out_file: pathlib.Path) -> tuple[int, str, str]:
    import os
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
        handle.write(script)
        path = handle.name
    env = {
        **os.environ,
        "RELEASE_MODE": mode,
        "EXPECTED_SCHEMA_BEFORE": before,
        "SOURCE_SCHEMA_HEAD": source,
        "GITHUB_OUTPUT": str(out_file),
    }
    proc = subprocess.run(["bash", path], capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


# ═════════ ١. التكرار ذهب، والمصدرُ واحدٌ مُراجَع ═════════

def test_the_workflow_no_longer_depends_on_a_project_ref_secret(workflow_text):
    """**سرٌّ ثانٍ يحمل الهويّة نفسها هو العطب** — فلا يبقى له أثر."""
    assert "secrets.SUPABASE_PROJECT_REF" not in workflow_text, (
        "المشغّل ما زال يقرأ هويّة المشروع من سرّ — والتكرار هو العلّة")


def test_the_project_reference_is_a_reviewed_constant_with_the_agreed_value(workflow):
    env = workflow.get("env") or {}
    assert "PRODUCTION_SUPABASE_PROJECT_REF" in env, (
        "لا ثابتَ مُراجَعًا لهويّة المشروع")
    assert env["PRODUCTION_SUPABASE_PROJECT_REF"] == REVIEWED_REF


def test_the_migration_step_confirms_with_that_constant(workflow):
    """**والحارسُ يُنادى فعلًا** — لا يُحذف مع السرّ الذي كان يغذّيه."""
    step = next(
        s for s in workflow["jobs"]["db-release-gate"]["steps"]
        if "Apply the migration" in (s.get("name") or ""))
    script = step["run"]
    assert "scripts/migrate_production.py" in script
    assert "--confirm" in script, "الترحيل بلا حارسِ التطابق"
    assert "${PRODUCTION_SUPABASE_PROJECT_REF}" in script
    assert "--env-file" in script, "الاعتماد لم يعد يُقرأ من ملفّ معزول"
    # ولا سرَّ في بيئة هذه الخطوة: الهويّةُ ثابتٌ، والاعتمادُ في ملفّ.
    assert "SUPABASE_PROJECT_REF" not in str(step.get("env") or {})


def test_the_reviewed_reference_appears_exactly_once_in_the_workflow(workflow_text):
    """**ومصدرٌ واحد يعني مرّةً واحدة.** قيمةٌ مكتوبةٌ مرّتين تنحرف ثانية."""
    assert workflow_text.count(REVIEWED_REF) == 1, (
        f"هويّةُ المشروع مكتوبةٌ {workflow_text.count(REVIEWED_REF)} مرّات")


# ═════════ ٢. حرّاسُ الترحيل لم تُمسّ ═════════

def test_migrate_production_keeps_every_safety_check(workflow_text):
    """**العلاجُ لا يُسهّل الترحيل، بل يوحّد طرفَ المقارنة.**

    فيُقرأ السكربتُ نفسه: كلُّ رفضٍ من رفوضه الأربعة قائم.
    """
    source = MIGRATE.read_text(encoding="utf-8")
    for marker, why in (
        ("looks_managed", "فحصُ أنّ الهدف إنتاجيّ مُدار"),
        ("args.confirm != reference", "مقارنةُ مرجع المشروع"),
        ("RUNTIME_ROLE", "رفضُ دور زمن التشغيل"),
        ("--env-file", "عزلُ الاعتماد في ملفّ"),
    ):
        assert marker in source, f"حارسٌ سقط من السكربت: {why}"
    # والرفوضُ أربعةٌ على الأقلّ — لا واحد.
    assert source.count("raise SystemExit") >= 4


def test_a_mismatched_reference_is_refused_before_any_connection(tmp_path, monkeypatch):
    """يُشغَّل السكربت بوسائط صريحة: مرجعٌ لا يطابق الرابط → رفضٌ فوريّ."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("migrate_production_cli", MIGRATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_production_cli"] = module
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.production.migration"
    env_file.write_text(
        "DATABASE_MIGRATION_URL=postgresql://postgres.realref:pw@"
        "aws-0-ap-south-1.pooler.supabase.com:5432/postgres\n",
        encoding="utf-8")

    monkeypatch.setattr(
        sys, "argv",
        ["migrate_production.py", "--confirm", "WRONGREF",
         "--env-file", str(env_file)])
    with pytest.raises(SystemExit) as caught:
        module.main()
    message = str(caught.value)
    assert "--confirm does not match" in message, message
    # **ولا اعتمادَ في نصّ الرفض.**
    assert "pw" not in message.replace("password", "")


def test_a_matching_reference_passes_the_guard_and_only_then_tries_to_run(
        tmp_path, monkeypatch):
    """**وحارسٌ لا يسمح أبدًا ليس حارسًا.** المرجعُ المطابق يعبر الحارس.

    ويُوقَف التنفيذ عند حدّ استدعاء alembic، فلا اتصالَ بقاعدةٍ من هذا الفحص.
    """
    import importlib.util
    import subprocess
    import sys

    spec = importlib.util.spec_from_file_location("migrate_production_ok", MIGRATE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_production_ok"] = module
    spec.loader.exec_module(module)

    env_file = tmp_path / ".env.production.migration"
    env_file.write_text(
        "DATABASE_MIGRATION_URL=postgresql://postgres.realref:pw@"
        "aws-0-ap-south-1.pooler.supabase.com:5432/postgres\n",
        encoding="utf-8")

    reached = {}

    def _no_alembic(*args, **kwargs):
        reached["called"] = True
        raise RuntimeError("stopped before alembic on purpose")

    monkeypatch.setattr(subprocess, "run", _no_alembic)
    monkeypatch.setattr(module.subprocess, "run", _no_alembic, raising=False)
    monkeypatch.setattr(
        sys, "argv",
        ["migrate_production.py", "--confirm", "realref",
         "--env-file", str(env_file)])

    with pytest.raises(RuntimeError, match="stopped before alembic"):
        module.main()
    assert reached.get("called"), "الحارسُ ردّ مرجعًا مطابقًا"


# ═════════ ٣. حدودُ المشغّل التي لا تُمسّ ═════════

def test_the_workflow_is_still_manual_only(workflow):
    triggers = _triggers(workflow)
    assert set(triggers) == {"workflow_dispatch"}, (
        f"مُطلِقٌ غير يدويّ على مسار الإنتاج: {sorted(triggers)}")


def test_web_deploy_still_defaults_to_false(workflow):
    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]
    assert inputs["deploy_web"]["default"] is False


def test_the_release_sha_description_carries_no_stale_example(workflow):
    """**مثالٌ في وصفٍ يُلصَق.** فلا هيئةَ محفوظة في نصّ المدخل."""
    description = _triggers(workflow)["workflow_dispatch"]["inputs"][
        "expected_main_sha"]["description"]
    import re
    assert not re.search(r"\b[0-9a-f]{40}\b", description), (
        "وصفُ المدخل يحمل هيئةً بعينها — وهي تتقادم وتُلصَق كما هي")
    assert not re.search(r"\b[0-9a-f]{12,}\b", description)


# ═════════ ٣أ. المشغّلُ لا تنتهي صلاحيتُه برقم ═════════
#
# **الفحصُ السابق هنا كان يطلب `--expect-version 0029` حرفيًّا.** وكان
# صحيحًا يومَه، وصار هو نفسُه حارسَ العطب: يُثبِّت المشغّلَ على ترحيلٍ
# بعينه. فأُبطل عمدًا، ومكانَه تُفحص **الآليّة** لا الرقم.


def test_no_operative_step_pins_a_literal_revision(workflow):
    """**ولا رقمَ محفورٌ في خطوةٍ تعمل.** الأرقام في التعليقات تاريخٌ يُشرح."""
    import re

    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            script = step.get("run") or ""
            for line in script.splitlines():
                bare = line.strip()
                if bare.startswith("#"):
                    continue
                assert not re.search(r"--expect-version\s+\d{4}\b", bare), (
                    f"{job_name}/{step.get('name')}: revision pinned literally")


def test_the_schema_head_is_derived_from_the_revision_graph(head_script, tmp_path):
    """**النسبُ لا ترتيبُ الأسماء.** وترقيمٌ منتظم اليوم لا يبقى منتظمًا.

    والبرهانُ سلوكيّ لا نصّيّ: يُبنى نسبٌ يكون فيه الرأسُ في الملفّ الذي
    يسبق أبجديًّا، وأبوه في الملفّ الذي يليه. فلو قُرئ الترتيبُ حكمًا
    لأخطأ. (والفرزُ في الشيفرة لتكرارٍ مستقرّ في التشخيص، لا لاختيار رأس.)
    """
    root = tmp_path / "graph"
    versions = root / "infra/db/migrations/versions"
    versions.mkdir(parents=True)
    # الرأسُ 0002 في `a.py`، وأبوه 0001 في `z.py` — والترتيبُ معاكسٌ عمدًا.
    (versions / "a.py").write_text(
        'revision = "0002"\ndown_revision = "0001"\n', encoding="utf-8")
    (versions / "z.py").write_text(
        'revision = "0001"\ndown_revision = None\n', encoding="utf-8")

    code, out, err = _run_head(head_script, root)
    assert code == 0, err
    assert "source_schema_head=0002" in out, out


def test_the_head_derivation_fails_closed(head_script, tmp_path):
    """صفرُ رؤوس، ورأسان، وأبٌ مفقود، ومعرّفٌ مكرَّر — **كلُّها سقوط**."""
    def build(files: dict[str, tuple[str, str | None]]) -> pathlib.Path:
        root = tmp_path / f"case{len(list(tmp_path.iterdir()))}"
        versions = root / "infra/db/migrations/versions"
        versions.mkdir(parents=True)
        for name, (rev, down) in files.items():
            down_line = "None" if down is None else f'"{down}"'
            (versions / name).write_text(
                f'revision = "{rev}"\ndown_revision = {down_line}\n', encoding="utf-8")
        return root

    healthy = build({"a.py": ("0001", None), "b.py": ("0002", "0001")})
    code, out, err = _run_head(head_script, healthy)
    assert code == 0, err
    assert "source_schema_head=0002" in out

    two_heads = build({"a.py": ("0001", None), "b.py": ("0002", "0001"),
                       "c.py": ("0003", "0001")})
    code, _out, err = _run_head(head_script, two_heads)
    assert code != 0 and "exactly one head" in err

    missing_parent = build({"a.py": ("0001", None), "b.py": ("0002", "0099")})
    code, _out, err = _run_head(head_script, missing_parent)
    assert code != 0 and "missing parent" in err

    duplicate = build({"a.py": ("0001", None), "b.py": ("0001", None)})
    code, _out, err = _run_head(head_script, duplicate)
    assert code != 0 and "duplicate revision" in err

    empty = build({})
    code, _out, err = _run_head(head_script, empty)
    assert code != 0, "قائمةٌ فارغة مرّت"


# ═════════ ٣ب. الحالاتُ الأربع، بلا قاعدة إنتاج ═════════
#
# **وتُشغَّل الشيفرةُ نفسها التي في المشغّل**، لا نسخةٌ منها في الفحص:
# نسختان تتباعدان، ويبقى الفحصُ أخضر على منطقٍ لم يعد قائمًا.


@pytest.mark.parametrize(
    ("mode", "before", "source", "expect_ok", "must_say"),
    [
        ("code_only", "0030", "0030", True, "nothing is written"),
        ("code_only", "0030", "0031", False, "release_mode=schema_and_code"),
        ("schema_and_code", "0030", "0031", True, "0030 -> 0031"),
        ("schema_and_code", "0030", "0030", False, "release_mode=code_only"),
    ],
)
def test_the_four_structural_release_cases(mode_script, tmp_path, mode, before,
                                           source, expect_ok, must_say):
    out_file = tmp_path / f"out-{mode}-{before}-{source}"
    out_file.write_text("", encoding="utf-8")
    code, stdout, stderr = _run_mode(mode_script, mode, before, source, out_file)
    blob = stdout + stderr
    if expect_ok:
        assert code == 0, blob
        emitted = out_file.read_text(encoding="utf-8")
        expected_migration = "yes" if mode == "schema_and_code" else "no"
        assert f"migration_executed={expected_migration}" in emitted
        expected_after = source if mode == "schema_and_code" else before
        assert f"schema_after={expected_after}" in emitted
        assert f"schema_before={before}" in emitted
    else:
        assert code != 0, "حالةٌ يجب أن تُرفض مرّت"
    assert must_say in blob, blob


def test_code_only_never_invokes_the_migration_machinery(workflow):
    """**ولا تُلمس آلةُ الترحيل في نمطٍ لا يُرحِّل.**"""
    steps = workflow["jobs"]["db-release-gate"]["steps"]
    guarded = ("Materialise", "Apply the migration", "Prove the schema",
               "Verify database constraints")
    for step in steps:
        name = step.get("name") or ""
        if any(marker in name for marker in guarded):
            assert step.get("if") == "${{ inputs.release_mode == 'schema_and_code' }}", (
                f"خطوةٌ كاتبة بلا شرط النمط: {name}")

    for step in steps:
        script = step.get("run") or ""
        env = str(step.get("env") or {})
        touches = ("migrate_production.py" in script
                   or "verify_db_constraints.py" in script
                   or "DATABASE_MIGRATION_URL" in env)
        if touches:
            assert step.get("if"), f"خطوةٌ تمسّ الترحيل بلا شرط: {step.get('name')}"


def test_the_read_only_preflight_runs_in_both_modes(workflow):
    """**حارسُ `code_only` هو هويّةُ المخطَّط** — فلا يكون مشروطًا."""
    steps = workflow["jobs"]["db-release-gate"]["steps"]
    preflight = next(s for s in steps if "Read-only schema preflight" in (s.get("name") or ""))
    assert preflight.get("if") is None, "الفحصُ القرائيّ صار مشروطًا"
    assert "--after-migration" not in preflight["run"], (
        "الفحصُ القرائيّ يستدعي بوّابات ما بعد الترحيل")
    assert "${EXPECTED_SCHEMA_BEFORE}" in preflight["run"]


def test_the_gate_job_is_never_skipped_as_a_whole(workflow):
    """**ولا تُبنى بوّابةٌ تُتخطّى بكاملها.** التخطّي ينتشر عبر `needs`.

    وهو شكلُ العطب الذي نُصلحه: `deploy-api` معلّقٌ خلف مهمّةٍ تُتخطّى،
    فيُتخطّى النشرُ صامتًا ويُقرأ ذلك نجاحًا.
    """
    for name in ("db-release-gate", "legacy-compatibility", "deploy-api"):
        assert workflow["jobs"][name].get("if") is None, (
            f"{name} محكومةٌ بشرطٍ على مستوى المهمّة — التخطّي سينتشر")
    assert "db-release-gate" in workflow["jobs"]["deploy-api"]["needs"]


def test_the_release_mode_input_is_least_privilege_by_default(workflow):
    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]
    mode = inputs["release_mode"]
    assert mode["type"] == "choice"
    assert sorted(mode["options"]) == ["code_only", "schema_and_code"]
    assert mode["default"] == "code_only", "الافتراضُ ليس الأقلَّ صلاحية"


def test_expected_schema_before_is_required_with_no_stale_default(workflow):
    """**قيمةٌ افتراضية هنا تُعيد العطبَ بعينه**، ومثالٌ في الوصف يُنسخ."""
    import re

    inputs = _triggers(workflow)["workflow_dispatch"]["inputs"]
    field = inputs["expected_schema_before"]
    assert field["required"] is True
    assert "default" not in field, "مدخلُ المخطَّط يحمل قيمةً افتراضية تتقادم"
    assert not re.search(r"\b\d{4}\b", field["description"]), (
        "وصفُ المدخل يحمل رقمَ مراجعةٍ — والمثالُ يُنسخ كما هو")


def test_the_post_migration_proof_targets_the_derived_head(workflow):
    steps = workflow["jobs"]["db-release-gate"]["steps"]
    after = next(s for s in steps if "Prove the schema" in (s.get("name") or ""))
    assert "${SOURCE_SCHEMA_HEAD}" in after["run"]
    assert "--after-migration" in after["run"]


def test_the_summary_never_reports_a_migration_that_did_not_happen(workflow):
    step = next(s for s in workflow["jobs"]["smoke"]["steps"]
                if (s.get("name") or "") == "Summary")
    script = step["run"]
    assert "${MIGRATION_EXECUTED}" in script
    assert "Migration executed" in script
    assert "no migration credential was materialised" in script
    env = str(step.get("env") or {})
    assert "db-release-gate" in env, "الملخّصُ لا يقرأ مخرجاتِ البوّابة"


def test_the_legacy_window_no_longer_names_a_deployed_version(workflow):
    """«خادم v88» صارت «الخادمُ المنشورُ حاليًّا» — والاسمُ يتقادم."""
    job = workflow["jobs"]["legacy-compatibility"]
    assert "v88" not in job["name"]
    scripts = "\n".join(s.get("run", "") for s in job["steps"])
    assert "v88" not in scripts
    assert "${SCHEMA_AFTER}" in scripts


def test_the_migration_credential_stays_runner_local_and_is_always_removed(workflow):
    steps = workflow["jobs"]["db-release-gate"]["steps"]
    write = next(s for s in steps if "Materialise" in (s.get("name") or ""))
    assert "RUNNER_TEMP" in write["run"], "الاعتماد يُكتب خارج مجلّد المشغّل"
    assert "chmod 600" in write["run"] and "umask 077" in write["run"]

    remove = next(s for s in steps if "Remove the migration credential" in (s.get("name") or ""))
    assert remove.get("if") == "always()", (
        "ملفُّ الاعتماد لا يُمحى إلّا عند النجاح — والفشلُ يتركه")
    assert "rm -f" in remove["run"]


def test_the_write_capable_jobs_still_carry_the_production_environment(workflow):
    for name in ("db-release-gate", "deploy-api", "deploy-web"):
        assert workflow["jobs"][name].get("environment") == "production", name


def test_no_step_prints_a_credential_or_a_connection_string(workflow):
    """**ولا سرَّ يُطبع.** لا `set -x`، ولا صدى لمتغيّرٍ يحمل اعتمادًا."""
    scripts = "\n".join(
        step.get("run", "")
        for job in workflow["jobs"].values() for step in job.get("steps", []))
    for forbidden in ("set -x", "printenv", "echo $DATABASE", "echo ${DATABASE",
                      "echo $FLY_API_TOKEN", "echo ${FLY_API_TOKEN",
                      "cat \"${MIGRATION_ENV_FILE}\"", "cat ${MIGRATION_ENV_FILE}"):
        assert forbidden not in scripts, f"المشغّل يطبع اعتمادًا: {forbidden}"


def test_every_embedded_script_parses_as_shell(workflow):
    import subprocess
    import tempfile

    bad = []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            script = step.get("run")
            if not script:
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
                handle.write(script)
                path = handle.name
            proc = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
            if proc.returncode != 0:
                bad.append(f"{job_name}/{step.get('name')}: {proc.stderr}")
    assert not bad, bad


# ═════════ ٤. الدليلُ التشغيليّ يقول ما يقع ═════════

def test_the_runbook_no_longer_lists_the_project_ref_as_a_secret():
    body = RUNBOOK.read_text(encoding="utf-8")
    secrets_table = body.split("## 2. Running a release")[0]
    assert "| `SUPABASE_PROJECT_REF` |" not in secrets_table, (
        "الدليل ما زال يطلب سرًّا لم يعد المشغّل يقرؤه")


def test_the_runbook_names_the_session_pooler_and_forbids_6543():
    """**والصياغةُ هي التي أرسلتنا إلى مضيفٍ لا يُبلَغ.**

    «المنفذ المباشر» قادت إلى `db.<ref>.supabase.co` — وهو IPv6 فقط،
    ومشغّلات GitHub بلا IPv6.
    """
    body = RUNBOOK.read_text(encoding="utf-8")
    assert "pooler.supabase.com" in body, "الدليل لا يسمّي مضيفَ المُجمِّع"
    assert "session pooler" in body.lower()
    assert "6543" in body and "forbidden" in body.lower()
    assert "IPv6" in body, "الدليل لا يقول لماذا لا يُستعمل المضيف المباشر"
    # ولا تُوصَف 5432 «المنفذ المباشر» بعد اليوم.
    assert "Use the direct port." not in body
