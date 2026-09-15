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

CHILD_TOOL_EXPORTS = """
EXISTS (
    SELECT 1 FROM dataset_versions v
    JOIN datasets d ON d.id = v.dataset_id
     WHERE v.id = tool_exports.dataset_version_id
       AND app_can_manage_project_data(d.project_id)
)
"""

CHILD_PLANNED_TESTS = """
EXISTS (
    SELECT 1 FROM analysis_plans p
     WHERE p.id = planned_tests.plan_id
       AND app_can_manage_project_data(p.project_id)
)
"""

CHILD_ANALYSIS_RUNS = """
EXISTS (
    SELECT 1 FROM analysis_plans p
     WHERE p.id = analysis_runs.plan_id
       AND app_can_manage_project_data(p.project_id)
)
"""

CHILD_ANALYSIS_OUTPUTS = """
EXISTS (
    SELECT 1 FROM analysis_runs r
    JOIN analysis_plans p ON p.id = r.plan_id
     WHERE r.id = analysis_outputs.run_id
       AND app_can_manage_project_data(p.project_id)
)
"""

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
    op.execute(CAN_MANAGE_DATA_FN)

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
    op.execute(DROP_CAN_MANAGE_DATA_FN)
