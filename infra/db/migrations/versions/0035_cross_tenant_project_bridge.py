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

════════════════════════════════════════════════════════════════════

# ٢ · وربطُ المرشَّح بعينه — الدَّينُ الذي تركه RC-T1B صريحًا

أبقى الترحيلُ 0034 كتلةَ تحقّقٍ **غيرَ قابلةٍ للبلوغ** تُثبت أنّ الدعوةَ
لبحثِ الفرصة، وكتب فيها صريحًا أنّها **ناقصة**: لا تُثبت أنّها لصاحب هذا
التطبيق بعينه. وكان ذلك صحيحًا حينه — الدعواتُ محلّيّةُ المستأجر
والتطبيقاتُ عابرةٌ له، فالربطُ الدقيق كان يستوجب تصميمَ خدمة.

والآن بُنيت الخدمة، فيُغلق الدَّين.

**ومصدرُ حقٍّ واحدٌ لا اثنان**: تُستبدل دالّةُ المُشغِّل التي أنشأها 0034
بنسخةٍ تحمل القاعدةَ كاملة — فلا كتلةٌ قديمةٌ ناقصةٌ تبقى بجوار قاعدةٍ
جديدة تُناقضها.

وحينَ تصير الحالُ `invited` تُثبت القاعدةُ **سبعةَ أمور**:

  ١ `invitation_id` غيرُ فارغة
  ٢ وصفُّ الدعوة موجود
  ٣ وبحثُها هو بحثُ الفرصة
  ٤ و`invited_user_id` غيرُ فارغة
  ٥ **وهي صاحبُ هذا التطبيق بعينه**
  ٦ وحالُ الدعوة `invited` — لا مقبولةٌ ولا مرفوضةٌ ولا منقوضة
  ٧ ومهلتُها لم تنتهِ

**ولا دعوةَ واحدةٌ تُشبع تطبيقَين**: فهرسٌ فريدٌ جزئيّ على
`invitation_id`.

و`shortlisted → invited` تُضاف إلى مصفوفة المدير **بعد** ذلك كلِّه، لا
قبله. و`pending → invited` تبقى ممنوعةً: الاختيارُ يمرّ بالترشيح.

## توسعةٌ محضة

ثلاثُ سياساتِ قراءة، ودالّةُ مُشغِّلٍ تُستبدل بنسخةٍ أقوى، وفهرسٌ فريدٌ
جزئيّ. لا جدولَ يُنشأ، ولا عمودَ يُحذف، ولا سياسةَ قائمةٌ تُسقط، ولا
صلاحيةَ تُمنح. **ولا يُمَسّ الترحيل 0034 نفسُه** — وهو في الإنتاج.

Revision ID: 0035
"""
from __future__ import annotations

import importlib.util
import pathlib

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


APPLICATIONS = "recruitment_applications"
OWNERS = "recruitment_opportunities"

#: مصفوفةُ انتقالات المدير — **وقد فُتحت «مدعوّ»**، وشرطُها أدناه.
#:
#: و`pending → invited` تبقى ممنوعة: الاختيارُ يمرّ بالترشيح، فقرارٌ
#: يُتّخذ بلا ترشيحٍ ظاهرٍ لا أثرَ له يُراجَع.
MANAGER_TRANSITIONS = (
    ("pending", "shortlisted"),
    ("pending", "declined"),
    ("shortlisted", "declined"),
    ("shortlisted", "invited"),
)

ACTIVE_APPLICATION_STATES = ("pending", "shortlisted", "invited")

#: **ربطُ المرشَّح بعينه** — وهو ما كان ناقصًا في 0034.
#:
#: ويُقرأ `project_invitations` بحقوق المستدعي: المديرُ في مستأجر البحث،
#: فسياسةُ العزل تُسلّمه الصفَّ. ومن لا يراه لا يُثبت شيئًا فيُرَدّ.
EXACT_BINDING_SQL = """
        SELECT o.project_id INTO owning_project
          FROM recruitment_opportunities o WHERE o.id = OLD.opportunity_id;
        IF owning_project IS NULL THEN
            RAISE EXCEPTION 'the opportunity behind this application is not readable'
              USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM project_invitations i
             WHERE i.id = NEW.invitation_id
               AND i.project_id = owning_project
               AND i.invited_user_id IS NOT NULL
               AND i.invited_user_id = OLD.applicant_user_id
               AND i.state = 'invited'
               AND i.expires_at > now()
        ) THEN
            RAISE EXCEPTION
              'INVITED requires a live ProjectInvitation on this opportunity''s own '
              'project, issued to this exact applicant'
              USING ERRCODE = 'check_violation';
        END IF;
"""


def _guard_v2() -> str:
    """جسمُ المُشغِّل كما يصير في 0035.

    ويُبنى من جسم 0034 **بتبديلين موضعيّين** لا بنسخةٍ ثانيةٍ كاملة:
    فنسخةٌ منسوخةٌ بيد تفترق عن أصلها بأوّل تعديلٍ هناك، ويصير للقاعدة
    الواحدة نصّان.
    """
    previous = _previous_guard()
    matrix_before = ", ".join(
        f"('{a}','{b}')" for a, b in MANAGER_TRANSITIONS[:-1])
    matrix_after = ", ".join(f"('{a}','{b}')" for a, b in MANAGER_TRANSITIONS)
    assert matrix_before in previous, "مصفوفةُ 0034 لم تُوجد في جسمها"
    body = previous.replace(matrix_before, matrix_after, 1)

    # وتُستبدل كتلةُ «لا طريقَ إلى مدعوّ» بقاعدة الربط الدقيق.
    start = body.index("    IF NEW.status = 'invited' THEN")
    end = body.index("    ELSIF NEW.invitation_id IS DISTINCT FROM OLD.invitation_id THEN",
                     start)
    body = body[:start] + "    IF NEW.status = 'invited' THEN" + EXACT_BINDING_SQL         + body[end:]
    assert "issued to this exact applicant" in body
    return body


def _previous_guard() -> str:
    """جسمُ المُشغِّل كما أنشأه 0034 — يُقرأ من ملفّه لا يُنسخ."""
    path = pathlib.Path(__file__).with_name("0034_recruitment_security_foundation.py")
    spec = importlib.util.spec_from_file_location("_m0034", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.APPLICATION_GUARD_FN


def upgrade() -> None:
    for table, name, predicate in SELF_POLICIES:
        op.execute(f"CREATE POLICY {name} ON {table} FOR SELECT USING ({predicate})")

    # ولا دعوةَ واحدةٌ تُشبع تطبيقَين — والقاعدةُ تمنع، لا مراجعةُ شيفرة.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recruitment_applications_invitation "
        f"ON {APPLICATIONS} (invitation_id) WHERE invitation_id IS NOT NULL"
    )
    op.execute(_guard_v2())


def downgrade() -> None:
    # وتُعاد دالّةُ 0034 بنصِّها هي — فالتنازلُ يُرجع ما كان لا ما يُشبهه.
    op.execute(_previous_guard())
    op.execute(f"DROP INDEX IF EXISTS uq_recruitment_applications_invitation")
    for table, name, _ in reversed(SELF_POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
