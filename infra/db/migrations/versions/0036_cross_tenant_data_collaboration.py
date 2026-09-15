"""جسرُ التعاون على البيانات عبر المؤسسات | RC-T1C data collaboration bridge.

**العطبُ الذي يغلقه هذا الترحيل عطبُ عقدٍ لا عطبُ حدّ**: بُني في 0035
جسرٌ يُدخل المتعاونَ من مؤسسةٍ أخرى إلى بحثٍ ليس في مستأجره، وصار
`/projects/{id}/access` يقول له صادقًا إنّه يحمل `manage_data` — **ثمّ لا
تُفتح له طبقةُ البيانات**. فالإحصائيُّ المدعوُّ لعمله بعينه لا يستطيع
عمله.

وسببُه بنيويّ: مساراتُ التحليل لا تأخذ معرّفَ البحث في قوالبها. منها ما
يأخذه في الجسم، **ومنها ما لا يعرفه أصلًا** حتى يقرأ الكيان: نسخةُ
مجموعةٍ تُعرَّف بمعرّفها وحده، وبحثُها يُعلم بقراءة مجموعتها. فجسرُ 0035
— وهو يُشتقّ من معرّف البحث — لا ينطبق عليها: القراءةُ التي تكشف البحثَ
تحتاج أن تكون في مستأجره سلفًا. دورةٌ لا تُفكّ إلّا بسياسة.

## وما يفعله هذا الترحيل، وما لا يفعله

يفعل شيئًا واحدًا: **يفتح قراءةَ تحديدِ موضعٍ للفاعل** — أن يرى صفوفَ
تحليلٍ **جذرُها بحثٌ أثبت فيه صلاحيّتَه**، فيُعلم بحثُها ثمّ يُدخل
مستأجرَه بالجسر القانونيّ.

ولا يفعل الكتابة. **ولا سياسةَ فاعلٍ واحدةً على `INSERT` أو `UPDATE` أو
`DELETE`**: سياساتُ 0012 على هذه الجداول `FOR ALL` بحدِّ المستأجر،
وإضافةُ سياسةِ `SELECT` إلى جانبها توسّع القراءةَ وحدها — فيبقى حدُّ
الكتابة هو هو: **لا يُكتب صفٌّ إلّا في مستأجر البحث**، بعد العبور. وهذا
مقصودٌ لا اقتصاد: من يكتب يكتب بسلطة المستأجر الذي عبَر إليه، لا بسلطةِ
سياسةٍ تعرفه.

## ولمَ لا `SECURITY DEFINER`

قِيس في 0034 و0035: مالكُ الترحيل `rolsuper/rolbypassrls`، فدالّةٌ
بحقوقه تقرأ الجدولَ كلَّه بلا سياق (٨٥٠٣ صفًّا مقابل صفر). فدالّةُ هذا
الترحيل **بحقوق المستدعي**، وما تقرؤه يخضع لسياساته: صفوفُ عضويّةِ
الفاعل هو، بسياسات «النفس» من 0035 — لا صفوفُ غيره.

## وسلسلةُ الملكيّة لا دورةَ فيها

جذران يحملان `project_id`: `datasets` و`analysis_plans`. وكلُّ ما بعدهما
يشير **إلى أعلى** ولا يُشار إليه من فوقه:

    dataset_versions  → datasets
    tool_exports      → dataset_versions → datasets
    planned_tests     → analysis_plans
    analysis_runs     → analysis_plans
    analysis_outputs  → analysis_runs → analysis_plans

فلا سياسةُ `datasets` تسأل عن `dataset_versions` بينما تسألها الأخرى
عنها. والدالّةُ عند الجذر تقرأ العضويّةَ وصفوفَ الصلاحيات وحدها، ولا
تعود إلى جدولِ تحليلٍ — فالسلسلةُ تنتهي.

## وجدولان **بلا** سياسةٍ هنا — قصدًا

`data_dictionaries` و`interpretations` لا يُقرآن إلّا من داخل نطاق
البحث: القاموسُ بمسارٍ مفتاحُه نسخةٌ (يعبُر أوّلًا)، والتفسيرُ بمسار
`golden_thread` المفتاحُ ببحثٍ (يعبُر أوّلًا) وبمسار التفسير نفسِه (يعبُر
أوّلًا). فسياسةٌ عابرةٌ عليهما **سطحٌ لا يستعمله أحد**، وأوسعُ ما لا
يُحتاج أضيقُ ما يُراجَع. ولو ظهر مسارٌ يقرؤهما من جلسة البيت فحينها
تُضاف — بفحصٍ يُثبت الحاجة.

## والصلاحيةُ صفّان لا صفّ

`view_project` **و**`manage_data` معًا، وعضويّةٌ **نشِطة**. فالاطّلاعُ
وحده لا يفتح بيانات (وهو حدُّ 0012 نفسُه على مستوى المسار)، و`manage_data`
وحده بلا اطّلاعٍ عضويّةٌ منقوصةٌ سُحب مدخلُها. **ولا دورَ يُقرأ**: لا
`statistician` ولا غيرُه — الدورُ موقعٌ في فريق، والصلاحيةُ صفٌّ يُقرأ.
"""
from __future__ import annotations

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


# ── الدالّة: سؤالٌ واحد، بحقوق المستدعي ──
#
# «هل الفاعلُ الحاليُّ يملك إدارةَ بيانات هذا البحث؟» — ولا تُجيب عن غيره.
#
# و`STABLE` لا `IMMUTABLE`: جوابُها يتغيّر بتغيّر الصفوف والسياق، ويثبت
# داخل العبارة الواحدة — وهو ما تحتاجه السياساتُ بالضبط.
#
# **ولا ملكيّةَ هنا.** صاحبُ البحث لا يحتاج هذا الجسر: بحثُه في مستأجره،
# وسياسةُ 0012 تكفيه. وإدخالُ الملكيّة في مُسنَدٍ عابرٍ للمستأجرين يوسّعه
# بلا حاجة — والأضيقُ ما يكفي.
CAN_MANAGE_DATA_FN = """
CREATE OR REPLACE FUNCTION app_can_manage_project_data(p_project_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT app_current_actor() IS NOT NULL
       AND EXISTS (
            SELECT 1
            FROM project_members m
            JOIN project_member_permissions baseline
              ON baseline.member_id = m.id
             AND baseline.permission_key = 'view_project'
            JOIN project_member_permissions wanted
              ON wanted.member_id = m.id
             AND wanted.permission_key = 'manage_data'
            WHERE m.project_id = p_project_id
              AND m.user_id = app_current_actor()
              AND m.access_state = 'active'
       )
$$
"""

DROP_CAN_MANAGE_DATA_FN = "DROP FUNCTION IF EXISTS app_can_manage_project_data(uuid)"


# ── مُسنَداتُ تحديدِ الموضع ──
#
# **يُكتب المُسنَدُ مرّةً ويُقرأ في موضعه**، ونصُّه هو ما يُراجَع: من
# أراد أن يعرف ما يراه المتعاونُ يقرأ هذه الأسطر، لا شيفرةَ موجّه.
#
# ولاحظ أنّ القراءاتَ الداخلية تخضع لسياسات جداولها هي — وذاك سليمٌ
# ومقصود: الفاعلُ المؤهَّل يرى الأبَ بسياسة الأب، فيصحّ الابن. ومن لا
# يرى الأبَ لا يصحّ له ابنٌ — **والفشلُ مغلق**.
ROOT_DATASETS = "app_can_manage_project_data(project_id)"

ROOT_PLANS = "app_can_manage_project_data(project_id)"

CHILD_DATASET_VERSIONS = """
EXISTS (
    SELECT 1 FROM datasets d
     WHERE d.id = dataset_versions.dataset_id
       AND app_can_manage_project_data(d.project_id)
)
"""

# **والتصديرُ كذلك**: نسختُه إلزامية، وتشغيلتُه اختيارية. فإن حملها
# وجب أن يكون جذرُها جذرَ النسخة — **ولا يُعرَض معرّفُ تشغيلةٍ غريبة
# من خلال تصديرٍ مأذونٍ من جانبه الآخر**. وكان `run_id` يُقبل من
# العميل بلا تفويضٍ أصلًا، فصفوفٌ كهذه محتملةٌ في التاريخ.
CHILD_TOOL_EXPORTS = """
EXISTS (
    SELECT 1
      FROM dataset_versions v
      JOIN datasets d ON d.id = v.dataset_id
     WHERE v.id = tool_exports.dataset_version_id
       AND app_can_manage_project_data(d.project_id)
       AND (
            tool_exports.run_id IS NULL
            OR EXISTS (
                SELECT 1
                  FROM analysis_runs r
                  JOIN analysis_plans p ON p.id = r.plan_id
                 WHERE r.id = tool_exports.run_id
                   AND p.project_id = d.project_id
            )
       )
)
"""

CHILD_PLANNED_TESTS = """
EXISTS (
    SELECT 1 FROM analysis_plans p
     WHERE p.id = planned_tests.plan_id
       AND app_can_manage_project_data(p.project_id)
)
"""

# **والتشغيلةُ لها أبوان، فيُفحصان معًا.**
#
# فلو اكتُفي بجذر الخطّة لَكفى أن يكون البحثُ المأذونُ فيه بحثَ الخطّة —
# **وتظهر تشغيلةٌ نسختُها من بحثٍ آخر**. وصفوفٌ كهذه قد تكون في القاعدة
# منذ ما قبل هذه الدفعة: المسارُ القديم كان يفوّض الخطّةَ والنسخةَ كلًّا
# على حدة. فالسياسةُ تشترط **وحدةَ الجذر** قبل أن تسأل عن الإذن:
#
#   خطّةُ التشغيلة → بحثٌ   ==   نسخةُ التشغيلة → مجموعةٌ → بحث
#
# وصفٌّ مختلطٌ لا يُرى من أيّ الجانبين — لا من جانب الخطّة ولا من جانب
# البيانات. **والفشلُ مغلق**: ما لا يُثبت جذرُه لا يُعرض.
CHILD_ANALYSIS_RUNS = """
EXISTS (
    SELECT 1
      FROM analysis_plans p
      JOIN dataset_versions v ON v.id = analysis_runs.dataset_version_id
      JOIN datasets d ON d.id = v.dataset_id
     WHERE p.id = analysis_runs.plan_id
       AND p.project_id = d.project_id
       AND app_can_manage_project_data(p.project_id)
)
"""

# **والمخرَجُ يرث شرطَ تشغيلته كاملًا** — لا شرطَ خطّتها وحدها. فمخرَجٌ
# من تشغيلةٍ مختلطةٍ نتيجةٌ حُسبت على بياناتِ بحثٍ آخر، وعرضُه تحت البحث
# المأذون يجعل رقمًا من مؤسسةٍ يُقرأ نتيجةً لمؤسسةٍ أخرى.
CHILD_ANALYSIS_OUTPUTS = """
EXISTS (
    SELECT 1
      FROM analysis_runs r
      JOIN analysis_plans p ON p.id = r.plan_id
      JOIN dataset_versions v ON v.id = r.dataset_version_id
      JOIN datasets d ON d.id = v.dataset_id
     WHERE r.id = analysis_outputs.run_id
       AND p.project_id = d.project_id
       AND app_can_manage_project_data(p.project_id)
)
"""

# ══════════ فحصٌ قبليٌّ على التاريخ ══════════
#
# **الطريقُ يُقفل للجديد، والقديمُ يبقى كما تُرك.** فالمسارُ القديم كان
# يفوّض الخطّةَ والنسخةَ كلًّا على حدة، و`run_id` في التصدير كان يُقبل
# بلا تفويضٍ أصلًا — فصفوفٌ مختلطةُ الجذر **محتملةٌ في القاعدة**.
#
# وما كان مستورًا بعزل المستأجر يصير بهذا الترحيل مرئيًّا عبرَ المؤسسات
# من جانبه المأذون. فيُسأل التاريخُ **قبل** تثبيت السياسات:
#
#   • أيُّ تشغيلةٍ خطّتُها في بحثٍ ونسختُها في آخر؟
#   • أيُّ تصديرٍ نسختُه في بحثٍ وتشغيلتُه في آخر؟
#   • وأيُّ صفٍّ لا يوافق مستأجرُه مستأجرَ أبويه؟
#
# **ولا يُحذف صفٌّ ولا يُعاد كتابتُه.** بياناتُ علمٍ لا تُصلَح بترحيل:
# الترحيلُ يتوقّف، ويُقال العددُ والمعرّفاتُ والبحوثُ — ولا حمولةَ ولا
# بصمةَ ولا اسمَ مجموعة. ويُصالحها إنسانٌ يعرف ما جرى.
PREFLIGHT_RUNS = """
SELECT r.id::text, p.project_id::text, d.project_id::text
  FROM analysis_runs r
  JOIN analysis_plans p ON p.id = r.plan_id
  JOIN dataset_versions v ON v.id = r.dataset_version_id
  JOIN datasets d ON d.id = v.dataset_id
 WHERE p.project_id <> d.project_id
    OR r.tenant_id <> p.tenant_id
    OR r.tenant_id <> d.tenant_id
    OR v.tenant_id <> d.tenant_id
 ORDER BY r.id
"""

PREFLIGHT_EXPORTS = """
SELECT e.id::text, d.project_id::text, coalesce(p.project_id::text, '-')
  FROM tool_exports e
  JOIN dataset_versions v ON v.id = e.dataset_version_id
  JOIN datasets d ON d.id = v.dataset_id
  LEFT JOIN analysis_runs r ON r.id = e.run_id
  LEFT JOIN analysis_plans p ON p.id = r.plan_id
 WHERE e.tenant_id <> d.tenant_id
    OR v.tenant_id <> d.tenant_id
    OR (e.run_id IS NOT NULL AND (
            r.id IS NULL
         OR p.project_id IS DISTINCT FROM d.project_id
         OR r.tenant_id <> e.tenant_id))
 ORDER BY e.id
"""


def _preflight() -> None:
    """يقف الترحيلُ إن كان في التاريخ صفٌّ مختلطُ الجذر — **ولا يُصلحه**."""
    bind = op.get_bind()
    findings: list[str] = []

    mixed_runs = bind.exec_driver_sql(PREFLIGHT_RUNS).fetchall()
    if mixed_runs:
        findings.append(
            f"analysis_runs: {len(mixed_runs)} mixed-root row(s)\n"
            + "\n".join(
                f"  run={row[0]} plan_project={row[1]} data_project={row[2]}"
                for row in mixed_runs[:50]))

    mixed_exports = bind.exec_driver_sql(PREFLIGHT_EXPORTS).fetchall()
    if mixed_exports:
        findings.append(
            f"tool_exports: {len(mixed_exports)} mixed-root row(s)\n"
            + "\n".join(
                f"  export={row[0]} data_project={row[1]} run_project={row[2]}"
                for row in mixed_exports[:50]))

    if findings:
        raise RuntimeError(
            "HOLD — historical mixed-project analysis rows require "
            "reconciliation.\n\n"
            "0036 makes analysis rows readable across tenants from their "
            "authorised side. A row whose two parents belong to different "
            "projects would expose results derived from another project.\n\n"
            "Nothing was deleted or rewritten: research data is not repaired "
            "by a migration. Reconcile these rows, then re-run.\n\n"
            + "\n\n".join(findings))


# ══════════ حارسانِ في القاعدة للجديد ══════════
#
# **والفحصُ في الموجّه ليس حدًّا.** أُضيف إلى `POST /runs` و`POST /exports`
# شرطُ وحدةِ الجذر، وذاك صحيحٌ ولا يكفي: موجّهٌ يُكتب غدًا، أو هجرةُ
# بيانات، أو صفٌّ يُدسّ بجلسةٍ مشروعة — كلُّها تتجاوز شيفرةَ المسار.
#
# والحارسُ **بحقوق المستدعي** (لا `SECURITY DEFINER`): ما يقرؤه يخضع
# لسياساته. وفي مسار الكتابة تكون الجلسةُ في مستأجر البحث أصلًا، فترى
# أبوَيها بسياسة العزل نفسِها.
RUN_GUARD_FN = """
CREATE OR REPLACE FUNCTION analysis_run_root_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    plan_project uuid;
    plan_tenant uuid;
    data_project uuid;
    data_tenant uuid;
BEGIN
    SELECT p.project_id, p.tenant_id INTO plan_project, plan_tenant
      FROM analysis_plans p WHERE p.id = NEW.plan_id;
    IF plan_project IS NULL THEN
        RAISE EXCEPTION 'analysis run references an unreadable plan';
    END IF;

    SELECT d.project_id, d.tenant_id INTO data_project, data_tenant
      FROM dataset_versions v
      JOIN datasets d ON d.id = v.dataset_id
     WHERE v.id = NEW.dataset_version_id;
    IF data_project IS NULL THEN
        RAISE EXCEPTION 'analysis run references an unreadable dataset version';
    END IF;

    -- **جذرٌ واحدٌ أو لا تشغيلة.**
    IF plan_project <> data_project THEN
        RAISE EXCEPTION 'analysis run would mix two projects';
    END IF;

    -- والمستأجرُ واحدٌ في الثلاثة — فالبحثُ في مستأجرٍ واحد.
    IF NEW.tenant_id <> plan_tenant OR NEW.tenant_id <> data_tenant THEN
        RAISE EXCEPTION 'analysis run tenant does not match its roots';
    END IF;

    RETURN NEW;
END;
$$
"""

EXPORT_GUARD_FN = """
CREATE OR REPLACE FUNCTION tool_export_root_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    data_project uuid;
    data_tenant uuid;
    run_project uuid;
    run_tenant uuid;
BEGIN
    SELECT d.project_id, d.tenant_id INTO data_project, data_tenant
      FROM dataset_versions v
      JOIN datasets d ON d.id = v.dataset_id
     WHERE v.id = NEW.dataset_version_id;
    IF data_project IS NULL THEN
        RAISE EXCEPTION 'tool export references an unreadable dataset version';
    END IF;

    IF NEW.tenant_id <> data_tenant THEN
        RAISE EXCEPTION 'tool export tenant does not match its dataset';
    END IF;

    -- والتشغيلةُ اختيارية؛ فإن حُملت فجذرُها جذرُ النسخة.
    IF NEW.run_id IS NOT NULL THEN
        SELECT p.project_id, r.tenant_id INTO run_project, run_tenant
          FROM analysis_runs r
          JOIN analysis_plans p ON p.id = r.plan_id
         WHERE r.id = NEW.run_id;
        IF run_project IS NULL THEN
            RAISE EXCEPTION 'tool export references an unreadable run';
        END IF;
        IF run_project <> data_project THEN
            RAISE EXCEPTION 'tool export would bind a foreign run';
        END IF;
        IF run_tenant <> NEW.tenant_id THEN
            RAISE EXCEPTION 'tool export tenant does not match its run';
        END IF;
    END IF;

    RETURN NEW;
END;
$$
"""

ROOT_GUARDS = (
    ("analysis_runs", "trg_analysis_runs_root_guard", "analysis_run_root_guard"),
    ("tool_exports", "trg_tool_exports_root_guard", "tool_export_root_guard"),
)


# (الجدول، اسمُ السياسة، المُسنَد) — **قراءةٌ فقط، في كلِّ سطر**.
LOCATOR_POLICIES = (
    ("datasets", "datasets_data_collaborator_read", ROOT_DATASETS),
    ("analysis_plans", "analysis_plans_data_collaborator_read", ROOT_PLANS),
    ("dataset_versions", "dataset_versions_data_collaborator_read",
     CHILD_DATASET_VERSIONS),
    ("tool_exports", "tool_exports_data_collaborator_read", CHILD_TOOL_EXPORTS),
    ("planned_tests", "planned_tests_data_collaborator_read", CHILD_PLANNED_TESTS),
    ("analysis_runs", "analysis_runs_data_collaborator_read", CHILD_ANALYSIS_RUNS),
    ("analysis_outputs", "analysis_outputs_data_collaborator_read",
     CHILD_ANALYSIS_OUTPUTS),
)

# جداولُ التحليل كلُّها — يُتحقّق من حدِّها الأساسيّ بعد الترحيل وقبله.
ANALYSIS_TABLES = (
    "datasets", "dataset_versions", "data_dictionaries", "analysis_plans",
    "planned_tests", "analysis_runs", "analysis_outputs", "interpretations",
    "tool_exports",
)


def upgrade() -> None:
    # **التاريخُ يُسأل قبل أن تُفتح القراءة** — لا بعدها.
    _preflight()

    op.execute(CAN_MANAGE_DATA_FN)

    op.execute(RUN_GUARD_FN)
    op.execute(EXPORT_GUARD_FN)
    for table, trigger, function in ROOT_GUARDS:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(
            f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()")

    for table, policy, predicate in LOCATOR_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        # **`FOR SELECT` وحدها.** وسياسةُ 0012 `FOR ALL` باقيةٌ بجوارها،
        # فالقراءةُ تصير «مستأجري **أو** بحثٌ أثبتُّ فيه إدارةَ بياناته»،
        # والكتابةُ تبقى «مستأجري» وحدها — لا يوسّعها هذا السطر.
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR SELECT "
            f"USING ({predicate.strip()})"
        )

    # **ولا جدولَ يفقد حدَّه الأساسيّ.** والتأكيدُ في الترحيل نفسِه: لو
    # أطفأ ترحيلٌ سابقٌ `FORCE` على واحدٍ منها لَما مرّ هذا.
    for table in ANALYSIS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table, policy, _predicate in LOCATOR_POLICIES:
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    for table, trigger, function in ROOT_GUARDS:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    op.execute(DROP_CAN_MANAGE_DATA_FN)
