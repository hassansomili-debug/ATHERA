"""جسرُ التعاون عبر المؤسسات | RC-T1C: the narrow actor-aware self-RLS bridge.

**المشكلةُ التي يفتحها هذا الترحيل.**

أتاح RC-T1B أن يتقدّم باحثٌ في مؤسسةٍ إلى فرصةٍ أعلنها بحثٌ في أخرى. وبقي
نصفُ القصّة: إذا قُبل، **كيف يعمل على البحث نفسِه؟**

وكلُّ طلبٍ في المنصّة يُفتح بـ`tenant_session(principal.tenant_id, ...)` —
أي بمستأجر الباحث **الأصليّ**. و`research_projects` و`project_members`
و`project_invitations` كلُّها محكومةٌ بـ`tenant_id = app_current_tenant()`.
فالمتعاونُ الخارجيّ لا يرى البحثَ، **ولا يرى عضويّتَه فيه، ولا يرى دعوتَه
إليه**. ثلاثةُ أبوابٍ مغلقة، لا واحد.

════════════════════════════════════════════════════════════════════

## ولمَ لا دالّةَ `SECURITY DEFINER` تحلّها

كان المقترحُ الأوّل دالّةَ `app_project_scope()` بحقوق مُعرِّفها، على غرار
`app_login_tenant` و`app_refresh_token_tenant` و`app_user_tenants`
القائمات. **وقد سقط المقترحُ عند القياس.**

فمالكُ تلك الدوالِّ `athera_owner`، وهو `rolsuper = t` و
`rolbypassrls = t`. وقِيس الفرقُ بمسبارَين متطابقَين إلّا في كلمةٍ واحدة،
يُنادَيان بدور التطبيق **وبلا أيّ سياق مستأجر**:

    SECURITY DEFINER  →  ٨٥٠٣ صفًّا من `project_members`
    حقوقُ المستدعي    →  صفرٌ

فـ`FORCE ROW LEVEL SECURITY` **لا تُخضع مالكًا متميّزًا**. ودالّةٌ جديدةٌ
بحقوق ذلك المالك كانت ستصير **مسارَ تفويضٍ قائمًا على تجاوز العزل** — وهو
بالضبط ما يمنعه التكليف.

### وتصحيحٌ لازم: تعليقٌ في الترحيل 0034 يقول غيرَ الصحيح

يقول 0034 إنّ `SECURITY DEFINER` لم تُغيّر سلوكَ `app_manages_project`
«لأنّ الجداولَ عليها `FORCE ROW LEVEL SECURITY`، فمالكُها خاضعٌ
لسياساتها». **وهذا التعليلُ خاطئ** — والقياسُ أعلاه يُبطله.

والسببُ الحقيقيّ أنّ جسمَ تلك الدالّة يحمل `tenant_id =
app_current_tenant()` **صريحةً في كلّ فرع**، فالحدُّ يقوم بمُسنَدها لا
بـRLS. وهي بحقوق مستدعيها فلا أثرَ عمليًّا اليوم — **لكنّ التعليلَ
المكتوب خطِر**: من يقرؤه قد يكتب دالّةً بلا تلك المُسنَدات ويظنّها
محميّة.

و0034 في الإنتاج فلا يُعدَّل. فيُصحَّح هنا وفي نموذج التهديد.

════════════════════════════════════════════════════════════════════

## الجسرُ المعتمَد: أن يعرف الفاعلُ نفسَه، ولا شيءَ غيرَ نفسه

ثلاثُ سياساتِ **قراءةٍ** مُضافة، كلُّها مربوطةٌ بـ`app_current_actor()`:

  ١ `project_members` — صفوفُ عضويّته هو، عبر المستأجرين.
  ٢ `project_member_permissions` — صلاحياتُ عضويّاته هو وحدها.
  ٣ `project_invitations` — الدعوةُ الموجَّهةُ إليه هو بعينه.

**وما لا تمنحه هذه السياسات**: لا عضوًا آخرَ، ولا بحثًا، ولا دعوةَ غيره،
ولا صفًّا واحدًا من بيانات البحث. فالفاعلُ يعرف **نفسَه** — وذاك ما يحتاجه
ليُثبت أنّ له مدخلًا، ولا يزيد.

وهي `FOR SELECT` وحدها: لا تُسهم في إدراجٍ ولا تعديلٍ ولا حذف. ولا
`USING (true)` فيها.

## والتفويضُ لا يقع بها

هذه السياساتُ تُريه صفَّه فحسب. أمّا «هل يدخل هذا البحث؟» فيبقى جوابُه
عند `ensure_project_access` كما كان منذ RC-T1A: مالكٌ مُثبت، أو عضوٌ
**نشِط** يحمل `view_project` صفًّا صريحًا. فالجسرُ يفتح بابَ السياق،
والحارسُ القديمُ يقف خلفه لم يُمسّ.

**وأساسُ `view_project` شرطٌ في الجسر نفسِه**: صلاحيةُ فعلٍ وحدها —
`manage_sources` أو `manage_data` أو `manage_team` — لا تنقل أحدًا إلى
مستأجرٍ آخر.

## توسعةٌ محضة

ثلاثُ سياساتِ قراءة. لا جدولَ يُنشأ، ولا عمودَ يُحذف، ولا سياسةَ قائمةٌ
تُعدَّل أو تُسقط، ولا صلاحيةَ تُمنح، ولا دالّةَ ولا مُشغِّل. والخادمُ
الذي لا يعرف هذا الترحيل يبقى صحيحًا بعد الصعود.

Revision ID: 0035
"""
from __future__ import annotations

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None

MEMBERS = "project_members"
PERMISSIONS = "project_member_permissions"
INVITATIONS = "project_invitations"

SELF_POLICIES = (
    # ── ١. «أين أنا عضو؟» ──
    #
    # و`user_id` قد يكون فارغًا (عضوٌ معروضٌ بلا حساب)، و`NULL = actor`
    # تُعطي `NULL` — فلا يُطابق. والفشلُ آمنٌ بالبناء.
    (MEMBERS, f"{MEMBERS}_self_read",
     "user_id = app_current_actor()"),

    # ── ٢. «وما صلاحياتي هناك؟» ──
    #
    # ولا تُقرأ صلاحيةُ عضوٍ آخر: الشرطُ يمرّ بصفّ العضويّة، وهو نفسُه
    # محكومٌ بالسياسة الأولى — فما لا يراه لا يستند إليه.
    (PERMISSIONS, f"{PERMISSIONS}_self_read",
     f"EXISTS (SELECT 1 FROM {MEMBERS} m "
     "          WHERE m.id = member_id AND m.user_id = app_current_actor())"),

    # ── ٣. «وهل دُعيتُ؟» ──
    #
    # **وهذا لازمٌ قبل العضويّة لا بعدها**: المتقدّمُ المختار يُدعى وهو
    # ليس عضوًا بعد، فلا سياسةَ عضويّةٍ تُريه دعوتَه. والحدُّ حسابُه
    # بعينه — لا بريدُه: `invited_user_id` عمودٌ يُكتب في الخادم.
    (INVITATIONS, f"{INVITATIONS}_self_read",
     "invited_user_id = app_current_actor()"),
)


def upgrade() -> None:
    for table, name, predicate in SELF_POLICIES:
        op.execute(f"CREATE POLICY {name} ON {table} FOR SELECT USING ({predicate})")


def downgrade() -> None:
    for table, name, _ in reversed(SELF_POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
