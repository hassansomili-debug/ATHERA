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

════════════════════════════════════════════════════════════════════

# ٣ · وكشفٌ قائمٌ في دعوات الفريق يُغلق

**وهذا دَينٌ سابقٌ اكتُشف في أثناء RC-T1C، لا شيءٌ أحدثته.**

أنشأ 0028 على `project_invitations` سياسةً واحدةً `FOR ALL` حدُّها
`tenant_id = app_current_tenant()`. فكلُّ مصادَقٍ في مستأجرٍ يقرأ **كلَّ
دعوات مستأجره**: مَن دُعي، وإلى أيّ بحث، وبأيّ دورٍ وصلاحيات — ولو لم يكن
من ذلك البحث بشيء.

والموجّهُ يشترط `manage_team`، لكنّ **حدَّ القاعدة كان أوسعَ من حدِّ
الموجّه**. وسياسةُ «الدعوةُ إليّ» التي أضافها هذا الترحيل أوّلًا لم تُضيّق
شيئًا: السياساتُ المُتاحة تتجمّع بـ«أو»، فالعريضةُ تبقى تُشبع القراءة.

فتُسقط سياسةُ 0028 **ويُوضع مكانها طقمٌ مُفصَّلٌ بالأفعال**:

| مَن | ماذا |
|---|---|
| المدعوُّ بعينه | قراءةً، وتعديلًا شخصيًّا (قبولٌ أو اعتذار) |
| مديرُ ذلك البحث | قراءةً وإصدارًا ونقضًا |
| غيرُهما | لا شيء — ولو كان في المستأجر نفسِه |

**والمدعوُّ غيرُ المربوط بحساب**: الدعواتُ لبريدٍ لا حسابَ له في المستأجر
تُكتب بـ`invited_user_id` فارغة، فلو اقتُصر على الحساب لَانكسر قبولُها.
فيُقابل البريدُ بحساب الفاعل من `users` — **للمقصود وحده**.

و«المدير» هو نفسُه `app_manages_project` من 0034. **ولا سياسةَ حذفٍ
لأحد**: النقضُ حالٌ تُكتب لا صفٌّ يُمحى.

## توسعةٌ محضة — إلّا موضعًا واحدًا مقصودًا

**وسياسةُ 0028 على الدعوات تُسقط ويُوضع مكانها ما هو أضيق** — تضييقٌ لا
توسيع. ولا جدولَ يُنشأ، ولا عمودَ يُحذف، ولا صلاحيةَ تُمنح. **ولا يُمَسّ
0034 ولا 0028**، والتنازلُ يُعيد سياسةَ 0028 بنصِّها.

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

RECIPIENT = (
    "invited_user_id = app_current_actor() "
    "OR (invited_user_id IS NULL AND EXISTS ("
    "      SELECT 1 FROM users u WHERE u.id = app_current_actor() "
    "        AND lower(u.email) = lower(invited_email)))"
)

INVITATION_MANAGER = (
    "tenant_id = app_current_tenant() AND app_manages_project(project_id)"
)

#: سياسةُ 0028 بنصِّها — تُسقط في الصعود وتُعاد في التنازل.
LEGACY_INVITATION_POLICY = (
    "CREATE POLICY project_invitations_tenant_isolation ON project_invitations "
    "USING (tenant_id = app_current_tenant()) "
    "WITH CHECK (tenant_id = app_current_tenant())"
)

INVITATION_POLICIES = (
    ("project_invitations_recipient_read", "SELECT", RECIPIENT, None),
    ("project_invitations_manager_read", "SELECT", INVITATION_MANAGER, None),
    ("project_invitations_manager_insert", "INSERT", None, INVITATION_MANAGER),
    ("project_invitations_manager_update", "UPDATE", INVITATION_MANAGER,
     INVITATION_MANAGER),
    # والقبولُ والاعتذارُ بيد صاحبها — **ولا يقبل أحدٌ عن أحد**.
    ("project_invitations_recipient_update", "UPDATE", RECIPIENT, RECIPIENT),
)

#: مُشغِّلُ الدعوة — **ما لا تقدر عليه سياسةُ الصفّ**.
#:
#: فسياسةُ تعديلِ المدعوّ تُسلّمه صفَّه، ولا تعرف **أيَّ عمودٍ** كتب ولا
#: **من أيّ حالٍ إلى أيّ حال**. فلولا مُشغِّلٌ لَنقض المدعوُّ دعوتَه —
#: فيُخفي أنّه دُعي — أو رفع عرضَها إلى دورٍ أعلى.
#:
#: وكان المانعُ الوحيدُ قبل اليوم هو الموجّه: `revoke_invitation` لا تسأل
#: عن سلطةٍ أصلًا. **وذاك حدُّ شيفرةٍ لا حدُّ قاعدة.**
INVITATION_GUARD_FN = """
CREATE OR REPLACE FUNCTION project_invitation_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    actor uuid := app_current_actor();
    is_recipient boolean;
BEGIN
    -- ══ ١ · هويّةُ الدعوة وعرضُها ومهلتُها: تُكتب مرّةً ══
    --
    -- **والمهلةُ منها.** فمن يملك تعديلَ صفّه يمدّ مهلةَ نفسِه، ولا
    -- حاجةَ في المنتج إلى تعديلها بعد الإصدار: دعوةٌ انتهت يُصدَر
    -- بدلُها صفٌّ جديد.
    IF NEW.id <> OLD.id
       OR NEW.tenant_id <> OLD.tenant_id
       OR NEW.project_id <> OLD.project_id
       OR NEW.invited_email IS DISTINCT FROM OLD.invited_email
       OR NEW.invited_display_name IS DISTINCT FROM OLD.invited_display_name
       OR NEW.invited_user_id IS DISTINCT FROM OLD.invited_user_id
       OR NEW.invited_by <> OLD.invited_by
       OR NEW.proposed_role <> OLD.proposed_role
       OR NEW.proposed_permissions IS DISTINCT FROM OLD.proposed_permissions
       OR NEW.token_hash <> OLD.token_hash
       OR NEW.expires_at <> OLD.expires_at
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION
          'the identity, the offer and the deadline of an invitation are written once'
          USING ERRCODE = 'check_violation';
    END IF;

    -- ══ ٢ · وحالُ الصفِّ تُقاس **مطلقةً** لا بما تغيّر منها ══
    --
    -- وكان الفحصُ يقارن ما تبدّل في الانتقال وحده، فيمرّ صفٌّ لُوِّث
    -- وهو `invited` ثمّ يُعتذر عنه فيحمل تلويثَه معه. فتُقاس الحالُ
    -- النهائيّةُ في كلّ تعديل، أيًّا كان الذي تغيّر.
    IF NEW.state = 'invited' THEN
        IF NEW.responded_at IS NOT NULL
           OR NEW.accepted_user_id IS NOT NULL
           OR NEW.member_id IS NOT NULL THEN
            RAISE EXCEPTION
              'a live invitation carries no answer, no account and no membership'
              USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.state = 'accepted' THEN
        IF NEW.responded_at IS NULL
           OR NEW.accepted_user_id IS NULL
           OR NEW.member_id IS NULL THEN
            RAISE EXCEPTION
              'an accepted invitation names its time, its account and its member'
              USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.invited_user_id IS NOT NULL
           AND NEW.accepted_user_id <> NEW.invited_user_id THEN
            RAISE EXCEPTION
              'an invitation is accepted by the account it was issued to'
              USING ERRCODE = 'check_violation';
        END IF;
        -- والعضويّةُ المذكورةُ هي عضويّةُ هذا الحساب في هذا البحث
        -- وبمستأجره — **ولا يكفي مفتاحٌ أجنبيٌّ يقول إنّها موجودة**.
        IF NOT EXISTS (
            SELECT 1 FROM project_members m
             WHERE m.id = NEW.member_id
               AND m.project_id = NEW.project_id
               AND m.tenant_id = NEW.tenant_id
               AND m.user_id = NEW.accepted_user_id
        ) THEN
            RAISE EXCEPTION
              'the membership an accepted invitation points to must belong to the '
              'same account, project and tenant'
              USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        -- معتذَرٌ عنها أو منقوضةٌ أو منتهية: **لا ارتباطَ عضويّةٍ بحال**.
        IF NEW.responded_at IS NULL
           OR NEW.accepted_user_id IS NOT NULL
           OR NEW.member_id IS NOT NULL THEN
            RAISE EXCEPTION
              'a settled invitation that was not accepted carries no membership'
              USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    -- ══ ٣ · وحالٌ لم تتغيّر لا تُغيّر جوابًا ══
    IF NEW.state = OLD.state THEN
        IF NEW.responded_at IS DISTINCT FROM OLD.responded_at
           OR NEW.accepted_user_id IS DISTINCT FROM OLD.accepted_user_id
           OR NEW.member_id IS DISTINCT FROM OLD.member_id THEN
            RAISE EXCEPTION
              'the answer to an invitation is written with its state, not after it'
              USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- ولا تُعاد دعوةٌ سُوّيت إلى الحياة: الجديدةُ صفٌّ جديد.
    IF OLD.state <> 'invited' THEN
        RAISE EXCEPTION 'a settled invitation is not reopened (it was %)', OLD.state
          USING ERRCODE = 'check_violation';
    END IF;

    is_recipient := actor IS NOT NULL AND (
        actor = OLD.invited_user_id
        OR (OLD.invited_user_id IS NULL AND EXISTS (
              SELECT 1 FROM users u WHERE u.id = actor
                AND lower(u.email) = lower(OLD.invited_email)))
    );

    IF is_recipient THEN
        -- **المدعوُّ يقبل أو يعتذر — ولا ينقض.**
        IF NEW.state NOT IN ('accepted', 'declined') THEN
            RAISE EXCEPTION
              'the invited account may accept or decline, not %', NEW.state
              USING ERRCODE = 'check_violation';
        END IF;
    ELSE
        -- **ولا يقبل أحدٌ عن أحد، ولا يعتذر عنه.**
        IF NEW.state NOT IN ('revoked', 'expired') THEN
            RAISE EXCEPTION
              'only the invited account may answer an invitation; a manager may '
              'revoke or expire it'
              USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    RETURN NEW;
END
$$;
"""


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

    # ── دعواتُ الفريق: تُسقط سياسةُ 0028 العريضة ويُوضع مكانها الأضيق ──
    #
    # **والإسقاطُ لازمٌ لا زيادة**: السياساتُ المُتاحة تتجمّع بـ«أو»، فلو
    # بقيت العريضةُ لَأشبعت القراءةَ وحدها وما ضيّق شيءٌ.
    op.execute(f"DROP POLICY {INVITATIONS}_tenant_isolation ON {INVITATIONS}")
    for name, command, using, check in INVITATION_POLICIES:
        clauses = f"FOR {command}"
        if using is not None:
            clauses += f" USING ({using})"
        if check is not None:
            clauses += f" WITH CHECK ({check})"
        op.execute(f"CREATE POLICY {name} ON {INVITATIONS} {clauses}")
    op.execute(f"REVOKE DELETE ON {INVITATIONS} FROM athera_app")

    op.execute(INVITATION_GUARD_FN)
    op.execute(
        f"CREATE TRIGGER trg_{INVITATIONS}_guard BEFORE UPDATE ON {INVITATIONS} "
        "FOR EACH ROW EXECUTE FUNCTION project_invitation_guard()"
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_{INVITATIONS}_guard ON {INVITATIONS}")
    op.execute("DROP FUNCTION IF EXISTS project_invitation_guard()")
    # وتُعاد سياسةُ 0028 بنصِّها — فالتنازلُ يُرجع ما كان لا ما يُشبهه.
    op.execute(f"GRANT DELETE ON {INVITATIONS} TO athera_app")
    for name, *_ in reversed(INVITATION_POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON {INVITATIONS}")
    op.execute(LEGACY_INVITATION_POLICY)

    # وتُعاد دالّةُ 0034 بنصِّها هي — فالتنازلُ يُرجع ما كان لا ما يُشبهه.
    op.execute(_previous_guard())
    op.execute(f"DROP INDEX IF EXISTS uq_recruitment_applications_invitation")
    for table, name, _ in reversed(SELF_POLICIES):
        op.execute(f"DROP POLICY IF EXISTS {name} ON {table}")
