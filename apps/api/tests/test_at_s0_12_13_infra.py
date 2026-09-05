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


#: الخطواتُ المسموح لها بتثبيت رقمِ ترحيل في `ci.yml` — **وهي اليوم لا شيء**.
#:
#: كانت خطواتُ نافذة 0028 مستثناةً بسببٍ مكتوب: الرقمُ فيها هو الخاصّيّةُ
#: المفحوصة لا قيمةٌ تتقادم. وقد أُغلقت تلك النافذة وذهبت خطواتُها، فذهب
#: موجبُ الاستثناء معها.
#:
#: **واستثناءٌ يبقى بعد زوال موجبه يصير بابًا.** فالقائمةُ تُفرَّغ ولا
#: تُترك مفتوحةً على «ما قد يُستثنى يومًا»: من أراد تثبيتًا جديدًا كتب
#: سببَه هنا، ورآه المراجع.
PINNED_BY_DESIGN: tuple[str, ...] = ()


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


def test_no_migration_number_is_pinned_in_ci_at_all():
    """**واستثناءٌ بلا حدٍّ يصير قاعدة — واستثناءٌ زال موجبُه يصير بابًا.**

    كان يُسمح بـ`0028` وحده، لأنّ خطوةَ النافذة كانت تقيس ذلك الرقم بعينه.
    وقد ذهبت الخطوة، فالمسموحُ اليوم **لا شيء**: كلُّ رقمٍ في `ci.yml`
    يُشتقّ من الرأس، وأيُّ تثبيتٍ جديد يمرّ على المراجعة بسببه المكتوب.

    **والشرطُ يضيق ولا يُترك مفتوحًا**: `<= {"0028"}` كان يمرّ اليوم على
    الفراغ ويمرّ غدًا على عودةِ `0028` بلا خطوةٍ تبرّرها. فيُطلب الفراغُ
    صراحةً.
    """
    import re

    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    pinned = {m for m in re.findall(r'=\s*"(0\d{3})"', workflow)}
    assert pinned == set(), f"رقمُ ترحيلٍ مثبَّت في المشغّل: {sorted(pinned)}"
    # وقائمةُ الاستثناءات فارغةٌ فعلًا — فلا يمرّ تثبيتٌ من بابها بصمت.
    assert PINNED_BY_DESIGN == (), (
        f"استثناءٌ قائمٌ بلا خطوةٍ تبرّره: {PINNED_BY_DESIGN}")


def _rc_head_pin_step() -> str:
    """كتلةُ خطوةِ تثبيت الرأس وحدها — **لا الملفّ كلّه**.

    والفرقُ جوهريّ: الملفّ يذكر أرقام ترحيلٍ أخرى في شرحه — «الإنتاج عند
    `0029`» مثلًا — وهي **وصفُ واقعٍ لا تثبيتُ شرط**. فحارسٌ يمسح الملفّ
    كلّه يسقط على نثرٍ صحيح، ويُدفع من يقرؤه إلى حذف الشرح ليخضرّ الفحص.
    فيُقرأ ما يُفحَص وحده: اسمُ الخطوة وجسمُها.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "rc-e2e.yml").read_text(
        encoding="utf-8")
    lines = workflow.splitlines()
    opener = next(
        (i for i, line in enumerate(lines)
         if line.strip().startswith("- name: Assert the schema head")), None)
    assert opener is not None, (
        "لا خطوةَ تثبّت رأسَ المخطَّط في رحلة المرشَّح — "
        "فلا شيء يفصل عطبَ المنتج عن انحراف النسخ")
    block = [lines[opener]]
    for line in lines[opener + 1:]:
        stripped = line.strip()
        if stripped.startswith(("- name:", "- uses:", "- run:")):
            break
        block.append(line)
    return "\n".join(block)


def test_the_rc_head_pin_says_one_number_and_it_is_the_chain_head():
    """**رحلةُ المرشَّح تثبّت رقمًا، فيجب أن يكون رقمَ الرأس — ورقمًا واحدًا.**

    والتثبيتُ هناك مقصود، خلافًا لـ`ci.yml`: السؤال «أهذه بيئةُ هذه الموجة؟»
    وجوابه رقمٌ بعينه اتُّفق عليه، لا «أيًّا كان رأسُ اليوم». ولو اشتُقّ
    لقال الفحصُ «موافق» على أيّ رأسٍ كان فلا يحرس شيئًا.

    **لكنّ تثبيتًا يتقادم أخطرُ من اشتقاق.** والعطبُ وقع فعلًا: أُضيف
    الترحيل `0030` وبقيت الرحلةُ تشترط `0029`، فسقطت المهمّةُ على تصميمٍ
    صحيح. فيُطلب هنا أمران:

      ١ **أنّ الرقم المثبَّت هو رأسُ السلسلة في هذا المستودع** — فأوّلُ
        ترحيلٍ جديد يُسقط هذا الفحص في المكان الذي يُصلَح فيه العطب، لا في
        مهمّةٍ تُشغَّل بعد الدمج.
      ٢ **وأنّه رقمٌ واحد في الخطوة كلّها** — الاسمُ والشرطُ والسجلُّ ونصُّ
        الخطأ. ورقمان مختلفان يعنيان بيّنةً تُناقض الشرطَ الذي تشهد له:
        يُقال «required: 0029» ويُفحص `!= "0030"`، فيُقرأ سببُ السقوط
        خاطئًا ويُبحث عن العلّة حيث ليست.
    """
    import re

    versions = REPO_ROOT / "infra" / "db" / "migrations" / "versions"
    head = sorted(path.name.split("_", 1)[0] for path in versions.glob("0*.py"))[-1]

    step = _rc_head_pin_step()
    mentioned = set(re.findall(r"\b(0\d{3})\b", step))

    assert mentioned, "خطوةُ التثبيت لا تذكر رقمًا أصلًا — فهي لا تحرس شيئًا"
    assert mentioned == {head}, (
        f"خطوةُ رحلة المرشَّح تذكر {sorted(mentioned)} ورأسُ السلسلة {head} — "
        "بيّنةٌ تُناقض الشرط، أو تثبيتٌ تقادم")
    # **وتُفحص المواضع الأربعة بأعيانها**: اسمٌ وشرطٌ وسجلٌّ ونصُّ خطأ.
    assert step.count(head) >= 4, (
        f"الرأس `{head}` مذكورٌ {step.count(head)} مرّةً في الخطوة — "
        "يُنتظر أربعةٌ على الأقل: الاسم والشرط والسجلّ ونصّ الخطأ")


def test_the_rc_head_guard_would_notice_a_stale_pin():
    """**حارسٌ لا يسقط أبدًا ليس حارسًا.**

    يُحاكى الحسابُ نفسه على نصٍّ تقادم رقمُه، وعلى آخر يذكر رقمين — فيجب
    أن يُرى الاثنان مخالفَين، وأن يُقبل السليمُ وحده.
    """
    import re

    def mentioned(text: str) -> set[str]:
        return set(re.findall(r"\b(0\d{3})\b", text))

    assert mentioned("required: '0029'") != {"0030"}, "تثبيتٌ تقادم يمرّ"
    assert mentioned("name: head is 0029\nif [ x != 0030 ]") != {"0030"}, "رقمان يمرّان"
    assert mentioned("required: '0030'\nverified: 0030") == {"0030"}, "السليمُ يُردّ"


def test_the_rc_pin_guard_reads_the_step_and_not_the_prose_around_it():
    """**والحارسُ لا يُسقطه شرحٌ صحيح.**

    الملفّ يذكر `0029` وصفًا لحال الإنتاج، وهو نثرٌ صادق لا تثبيتُ شرط.
    فتُقرأ الخطوةُ وحدها، ويُثبَت أنّ ما حولها بقي خارج القراءة.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "rc-e2e.yml").read_text(
        encoding="utf-8")
    step = _rc_head_pin_step()
    assert len(step) < len(workflow), "الحارس يقرأ الملفّ كلّه لا الخطوة"
    assert "- name: Assert the schema head" in step
    assert "version_num FROM alembic_version" in step, "جسمُ الخطوة لم يُقرأ"
