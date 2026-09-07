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
        s for s in workflow["jobs"]["db-migrate"]["steps"]
        if "Apply migration" in (s.get("name") or ""))
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


def test_the_pre_migration_gate_still_demands_exactly_0029(workflow):
    """**ولا يُمرَّر `0030` من بوابة ما قبل الترحيل**، ولا تُجعل مُعادةً."""
    steps = workflow["jobs"]["db-migrate"]["steps"]
    gate = next(s for s in steps if "Gate" in (s.get("name") or ""))
    assert "--expect-version 0029" in gate["run"]
    after = next(s for s in steps if "Prove the schema" in (s.get("name") or ""))
    assert "--expect-version 0030" in after["run"]
    assert "--after-migration" in after["run"]


def test_the_migration_credential_stays_runner_local_and_is_always_removed(workflow):
    steps = workflow["jobs"]["db-migrate"]["steps"]
    write = next(s for s in steps if "Materialise" in (s.get("name") or ""))
    assert "RUNNER_TEMP" in write["run"], "الاعتماد يُكتب خارج مجلّد المشغّل"
    assert "chmod 600" in write["run"] and "umask 077" in write["run"]

    remove = next(s for s in steps if "Remove the migration credential" in (s.get("name") or ""))
    assert remove.get("if") == "always()", (
        "ملفُّ الاعتماد لا يُمحى إلّا عند النجاح — والفشلُ يتركه")
    assert "rm -f" in remove["run"]


def test_the_write_capable_jobs_still_carry_the_production_environment(workflow):
    for name in ("db-migrate", "deploy-api", "deploy-web"):
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
