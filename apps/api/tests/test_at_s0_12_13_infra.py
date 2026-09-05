"""AT-S0-12/13 — الترحيلات والنسخ الاحتياطي والامتدادات."""
import pathlib

import pytest
from sqlalchemy import text

from athera_api.db import tenant_session

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "infra" / "db" / "migrations" / "versions"


@pytest.mark.asyncio
async def test_pgvector_extension_is_installed(db_ready):
    async with tenant_session(None) as session:
        row = (
            await session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        ).scalar_one_or_none()
    assert row == "vector", "pgvector is required by §31.3"


def test_every_migration_has_a_real_downgrade():
    """AT-S0-13 — ترحيل بلا تراجع نظيف يعني بيئة لا يمكن إصلاحها."""
    offenders = []
    for path in sorted(MIGRATIONS.glob("[0-9]*.py")):
        source = path.read_text(encoding="utf-8")
        body = source.split("def downgrade()")[-1]
        if body.strip().endswith("pass") or "pass" == body.split(":", 1)[-1].strip():
            offenders.append(path.name)
    assert not offenders, f"migrations without a downgrade: {offenders}"


def test_migrations_form_a_single_chain():
    revisions, downs = {}, {}
    for path in sorted(MIGRATIONS.glob("[0-9]*.py")):
        source = path.read_text(encoding="utf-8")
        rev = source.split('revision = "')[1].split('"')[0]
        down_raw = source.split("down_revision = ")[1].split("\n")[0].strip()
        revisions[rev] = path.name
        downs[rev] = None if down_raw == "None" else down_raw.strip('"')
    roots = [rev for rev, down in downs.items() if down is None]
    assert len(roots) == 1, f"expected exactly one root migration, found {roots}"
    for rev, down in downs.items():
        assert down is None or down in revisions, f"{revisions[rev]} points at unknown revision {down}"


def test_the_migration_drill_runs_on_its_own_database():
    """AT-S0-13 — تدريب الترحيل معزول عن قاعدة الاختبارات.

    **لماذا اختبارٌ لهذا؟** لأن الاثنتين كانتا قاعدةً واحدة، فاصطدم
    `downgrade base` ببيانات قبولٍ صحيحة تركتها الاختبارات. والحارس الذي
    رفض التنازل كان محقًّا — العطب في عزل التدريب. وإصلاحه بإضعاف الحارس
    كان سيبدّد الضمان الذي وُجد لأجله، فيُثبَّت العزل هنا حتى لا يعود.

    ولا آلية ثانية تُخترع: `DATABASE_MIGRATION_URL` قائمة في `env.py`،
    وكل ما يجري هو توجيهها إلى قاعدة أخرى في خطوة التدريب.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "athera_migration" in workflow, "لا قاعدة تدريب مخصَّصة"
    assert "CREATE DATABASE athera_migration" in workflow

    # الدورة كاملة لا تنازلًا وحده: `head → base → head`.
    assert "alembic upgrade head" in workflow
    assert "alembic downgrade base" in workflow

    # والتدريب لا يشير إلى قاعدة الاختبارات.
    drill = workflow.split("Migration roundtrip drill")[1].split("- name:")[0]
    assert "MIGRATION_DRILL_URL" in drill
    assert "/athera\n" not in drill and "5432/athera " not in drill

    # ولا آلية إعداد ثانية: `env.py` يقرأ `DATABASE_MIGRATION_URL` وحدها.
    env_py = (MIGRATIONS.parent / "env.py").read_text(encoding="utf-8")
    assert 'os.getenv(\n    "DATABASE_MIGRATION_URL"' in env_py or \
        '"DATABASE_MIGRATION_URL"' in env_py


def test_ci_asserts_the_drill_database_starts_clean():
    """قاعدةٌ ليست نظيفة تجعل التدريب يفحص شيئًا آخر بلا أن يقول."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "drill database is not clean" in workflow
    assert "information_schema.tables" in workflow


def test_ci_asserts_the_acceptance_database_survives_the_drill():
    """التدريب لا يمسّ بيانات القبول — والادعاء يُفحص لا يُترك."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "the drill mutated the acceptance-test database" in workflow
    assert "status = 'unknown'" in workflow
    # ورأس التدريب يُفحص صراحةً — **بالمقارنة بالمشتقّ لا برقم محفوظ**.
    assert 'test "$head" = "$expected"' in workflow


def test_ci_never_clears_decisions_to_make_the_drill_pass():
    """الطرق المحرّمة: حذف «لا أعرف» أو تحويلها لتمرير التنازل."""
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    forbidden = (
        "DELETE FROM fact_candidates",
        "UPDATE fact_candidates",
        "TRUNCATE fact_candidates",
    )
    for statement in forbidden:
        assert statement not in workflow, statement


def test_migration_0016_still_refuses_a_destructive_downgrade():
    """الحارس لم يُمسّ أثناء إصلاح العزل."""
    source = (MIGRATIONS / "0016_unknown_decision_state.py").read_text(encoding="utf-8")
    downgrade = source.split("def downgrade")[1]
    assert "raise RuntimeError" in downgrade
    assert "downgrade refused" in downgrade
    # ولا تحويل ولا حذف داخل الترحيل نفسه.
    for statement in ("UPDATE fact_candidates", "DELETE FROM fact_candidates", "TRUNCATE"):
        assert statement not in source, statement


def test_backup_restore_drill_is_documented():
    """§38.2 — الاستعادة غير المختبرة ليست نسخة احتياطية."""
    runbook = REPO_ROOT / "docs" / "runbooks" / "backup-restore.md"
    assert runbook.exists(), "AT-S0-12 requires a documented and executed restore drill"
    text_content = runbook.read_text(encoding="utf-8")
    assert "pg_restore" in text_content or "pg_dump" in text_content


def test_ci_derives_the_expected_migration_head_instead_of_hardcoding_it():
    """رقمٌ محفوظ في CI يقيس عمر الملف لا صحّة الترحيل.

    كانت الخطوة تكتب `test "$head" = "0016"` حرفيًّا. فلمّا أُضيف 0017 سقط
    الفحص — **والتدريب نفسه كان ناجحًا**: بلغ الرأس الصحيح، والتأكيد وحده
    كان يقيس رقمًا قديمًا. وهذا الصنف يتكرّر مع كل ترحيل ويطلب تعديلًا
    يدويًّا يُنسى.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    drill = workflow.split("Assert the drill reached")[1]

    assert "alembic heads" in drill, "الرأس لا يُشتقّ"
    assert 'test "$head" = "$expected"' in drill
    # ولا رقم ترحيل مثبَّت في المقارنة.
    import re

    assert not re.search(r'test "\$head" = "0\d{3}"', drill), "رقم مثبَّت عاد"


#: الخطواتُ المسموح لها بتثبيت رقمِ ترحيل — **بسببٍ مكتوب، لا بالتسامح**.
#:
#: قاعدةُ نافذة النشر تقف عند `0028` عمدًا: بين ترحيل الإنتاج ونشر الموجة
#: يخدم الخادمُ القديم ذلك المخطَّط بعينه، والرقمُ هنا **هو الخاصّيّة
#: المفحوصة** لا قيمةً تتقادم. ولو اشتُقّ من الرأس لصار الفحصُ يقيس الرأس
#: مرّتين ولا يقيس النافذة أصلًا.
PINNED_BY_DESIGN = ("athera_expand", "expand-window", "upgrade 0028")


def test_no_ci_step_pins_a_migration_revision_number():
    """الحارس أوسع من الخطوة الواحدة: لا مقارنة برقم ترحيل في أي مكان.

    وللنافذة استثناءٌ معلَّل: يُسمح بتثبيت `0028` في خطواتها وحدها.
    """
    import re

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    block = ""
    for line in workflow.splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:"):
            block = stripped
        if stripped.startswith("#"):
            continue
        if any(mark in line or mark in block for mark in PINNED_BY_DESIGN):
            continue
        assert not re.search(r'=\s*"0\d{3}"', line), f"رقم ترحيل مثبَّت: {stripped}"


def test_the_pinned_exception_is_only_the_window():
    """**واستثناءٌ بلا حدٍّ يصير قاعدة.**

    فيُطلب أن يبقى الرقم المثبَّت `0028` وحده: لو ثُبّت رأسُ السلسلة يومًا
    لعاد العطبُ الذي وُضع الحارسُ لأجله، متسلّلًا من باب الاستثناء.
    """
    import re

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pinned = {m for m in re.findall(r'=\s*"(0\d{3})"', workflow)}
    assert pinned <= {"0028"}, f"أرقامٌ مثبَّتة خارج النافذة: {sorted(pinned)}"


def test_the_rc_head_pin_says_one_number_and_it_is_the_chain_head():
    """**ودليلٌ يناقض شرطَه أسوأ من غياب الدليل.**

    خطوةُ RC تُثبّت رأسَ السلسلة نصًّا **عن قصد** (السؤال: أهذه بيئةُ
    الموجة المتوقَّعة؟ وجوابُه رقمٌ مُعلَن لا «أيًّا كان رأسُ اليوم»). لكنّ
    الرقم مكتوبٌ أربع مرّات: في اسم الخطوة، وفي الشرط، وفي سطر السجلّ، وفي
    نصّ الخطأ. ومن حدّث بعضَها ونسي بعضًا أنتج مخرَجًا يقول «required: 0029»
    بينما الشرطُ يقيس غيرَه — وقد وقع هذا مرّتين: عند 0028←0029، ثمّ عند
    0029←0030.

    فيُطلب أمران: أن يقول الموضعُ رقمًا **واحدًا**، وأن يكون ذلك الرقمُ رأسَ
    السلسلة فعلًا — إذ الخطوةُ تلي `alembic upgrade head`، فرقمٌ يخالف الرأسَ
    يجعلها ترفض كلَّ تشغيلةٍ إلى الأبد.

    **ولا يُشتقّ الرقمُ في المشغّل** — يبقى مكتوبًا هناك صريحًا كما قُصد،
    وهذا الحارسُ وحده يسأل: أهو الرقمُ الصحيح، وأهو واحد.
    """
    import re

    workflow = (REPO_ROOT / ".github" / "workflows" / "rc-e2e.yml").read_text(
        encoding="utf-8")
    marker = "Assert the schema head is exactly"
    assert marker in workflow, "خطوةُ تثبيت الرأس في RC اختفت — والحارسُ بلا هدف"

    step = workflow.split(marker, 1)[1].split("\n      - name:", 1)[0]
    stated = set(re.findall(r"\b0\d{3}\b", step))
    assert len(stated) == 1, (
        f"الخطوةُ تذكر أكثر من رقم — الدليلُ يناقض الشرط: {sorted(stated)}")

    versions = REPO_ROOT / "infra" / "db" / "migrations" / "versions"
    revisions, downs = set(), set()
    for path in versions.glob("0*.py"):
        source = path.read_text(encoding="utf-8")
        revisions.add(re.search(r'^revision = "([^"]+)"', source, re.M).group(1))
        downs.add(
            re.search(r'^down_revision = "?([^"\n]+)"?', source, re.M).group(1))
    heads = revisions - downs

    assert heads == stated, (
        f"RC يُثبّت {sorted(stated)} ورأسُ السلسلة {sorted(heads)} — "
        "الخطوةُ سترفض كلَّ تشغيلة")
