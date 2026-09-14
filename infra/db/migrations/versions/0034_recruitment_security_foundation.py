"""أساسُ الاستقطاب الآمن | RC-T1B: cross-tenant recruitment, narrowly.

**الحدُّ الذي يُكسَر هنا لأوّل مرّة، ولمَ يجوز كسرُه.**

كلُّ صفٍّ قبل هذا الترحيل يُقرأ ويُكتب داخل مستأجرٍ واحد:
`tenant_id = app_current_tenant()`، لا استثناء. وقرارُ المنتج في هذه
المرحلة يستوجب أن **يكتشف باحثٌ في مؤسسةٍ فرصةَ تعاونٍ أعلنها بحثٌ في
مؤسسةٍ أخرى، وأن يتقدّم إليها**.

ولو تُرك ذلك للتطبيق — استعلامٌ بلا شرط مستأجر — لصار العزلُ سياسةَ
كتابةِ كودٍ لا خاصيّةَ قاعدة. فالحدُّ يُكسَر **في القاعدة، وبأضيق ما
يكفي**.

════════════════════════════════════════════════════════════════════

## ١ · ولمَ جدولان للفرصة لا جدولٌ واحد

**وهذا تصحيحٌ لتصميمٍ سابقٍ في هذا الترحيل نفسِه، لم يُدمج ولم يُنشر.**

كانت الفرصةُ جدولًا واحدًا يحمل النصَّ المُعلَن ومعه `tenant_id`
و`project_id` و`created_by`، وعليه سياسةُ اكتشافٍ عابرةٌ للمستأجرين
مقيَّدةٌ بالصفوف المفتوحة. وRLS تحكم **الصفوفَ لا الأعمدة** — فباحثٌ في
مستأجرٍ آخر يستعلم الجدولَ الأصلَ مباشرةً كان يحصل، في تلك الصفوف
وحدها، على معرّف البحث ومعرّف المؤسسة ومنشئِ الفرصة. وكان العلاجُ
المكتوب أنّ «العرضَ الآمن هو الطريقُ المُعتمد للاكتشاف» —
**أي اتفاقًا في التطبيق لا حدًّا في القاعدة**. ومراجعةٌ أمنيةٌ مستقلّة
رفضت ذلك بحقّ.

فانفصل **النسبُ** عن **الإعلان**:

| | يحمل | مَن يقرؤه |
|---|---|---|
| `recruitment_opportunities` | مستأجرٌ وبحثٌ ومنشئ | **المديرُ وحده** — ولا سياسةَ عابرةً للمستأجرين عليه إطلاقًا |
| `recruitment_opportunity_listings` | النصُّ المُعلَن وحالتُه ونافذتُه | المديرُ، **وكلُّ باحثٍ مصادقٍ للصفوف المفتوحة** |

**والعمودُ غيرُ الموجود لا يُسرَّب.** فما يبلغه الغريبُ من الجدول الأصل
مباشرةً هو نفسُه ما يبلغه من العرض: نصٌّ كُتب ليُقرأ.

و«الحالةُ» على الإعلان لا على النسب **قصدًا**: شرطُ الاكتشاف يصير كلُّه
محلّيًّا في جدولٍ واحد، فلا شرطَ يعبُر جدولين ولا نسخةٌ ثانيةٌ من
النافذة تفترق عن أختها.

والنسبُ هو **الأصل** والإعلانُ فرعُه، لا العكس: فيُكتب النسبُ أوّلًا
بتفويضٍ يقوم على `project_id` وحده — سؤالٌ مكتملٌ بذاته — ثمّ يُكتب
الإعلانُ بتفويضٍ يقرأ أباه. ولو انعكس الترتيبُ لاحتاج إعلانٌ إلى نسبٍ لم
يُكتب بعد، فاستحال تفويضُ إدراجه.

## ٢ · والنسبُ يُكتب مرّةً ولا يُعدَّل

ولا سياسةَ تعديلٍ على `recruitment_opportunities` ولا صلاحيةَ تعديل —
كما فعل 0003 بسجلّ التدقيق. فـ«لا تُنقل فرصةٌ إلى بحثٍ آخر» و«لا يُعاد
كتابةُ من أنشأها» ليستا حارسًا يُفحَص بل **غيابَ الطريق**.

## ٣ · و`OLD` لا تعرفها RLS — فالمُشغِّلُ يحملها

سياسةُ تعديلٍ تقول «صاحبُ التطبيق يعدّله» تسمح له أن يُرشّح نفسَه
`shortlisted`، وأن ينقل تقدُّمَه إلى فرصةٍ أخرى، وأن يكتب `decided_by`.
و`WITH CHECK` ترى الصفَّ الجديد ولا ترى القديم، فلا تقدر على قاعدةِ
انتقال.

فمصفوفةُ الانتقالات في مُشغِّلٍ `BEFORE` — وهو النمطُ القائم في
المستودع (`audit_events_immutable`، `forbid_row_mutation`،
`enforce_frozen_dataset_for_run`) لا اختراعًا:

  • هويّةُ التطبيق **ثابتة**: الفرصةُ والمتقدّمُ ومؤسستُه ووقتُ الإنشاء
    ونصُّ صاحبه.
  • والمتقدّمُ **ينسحب وحسب**. ولا يُرشّح نفسَه ولا يرفضها عن نفسه ولا
    يكتب حسمًا.
  • والمديرُ **يُرشّح ويعتذر** — ولا ينسحب عن أحد، ولا ينتحل.
  • و**«مدعوّ» لا طريقَ إليها في هذه المرحلة**: محجوزةٌ لخدمةِ تحويلٍ
    تربط المتقدّمَ بدعوةٍ له بعينه في RC-T1C. والمصفوفةُ لا تحملها
    هدفًا، والإدراجُ يُولد في الانتظار — فلا صفَّ يبلغها بحال.
  • و«مدعوّ» يستوجب `invitation_id` لدعوةٍ حقيقيةٍ **في بحثِ الفرصة
    نفسِه** — فالاستقطابُ لا يصير طريقًا ثانيةً إلى الفريق تتجاوز
    `ProjectInvitation`.

## ٤ · والتقدّمُ لا يُقبل إلّا على بابٍ مفتوحٍ الآن

ومعرّفُ فرصةٍ عُرف حين كانت مفتوحةً لا يصير مفتاحًا بعد إغلاقها. فشرطُ
القبول **نفسُ شرطِ الاكتشاف**، مكتوبًا مرّةً في `DISCOVERABLE` ومقروءًا
في: سياسةِ الاكتشاف، ودالّةِ القبول، والعرضِ الآمن.

## ٥ · والفشلُ آمنٌ بالبناء لا بالاتفاق

`app_current_actor()` تُعيد `NULL` عند غياب الضبط، وكلُّ مقارنةٍ بـ`NULL`
تُعطي `NULL` — والسياسةُ لا تطابق. فجلسةٌ بلا فاعلٍ لا ترى تطبيقًا ولا
تكتبه، وجلسةٌ بفاعلٍ مشوَّه يسقط `::uuid` فيها فتُلغى المعاملة.

## ٦ · ولمَ دالّتا التفويض بحقوق المستدعي

`app_manages_project()` و`app_manages_opportunity()` تُقرآن داخل
السياسات، وهما **بحقوق مستدعيهما** قصدًا: فتبقى الجداولُ التي تقرآنها
خاضعةً لـRLS بحقوق القارئ نفسِه.

**وقد جُرّبت الأولى بـ`SECURITY DEFINER` فلم يتغيّر سلوكٌ واحد** —
والسببُ أنّ الجداولَ التي تقرؤها عليها `FORCE ROW LEVEL SECURITY`،
فمالكُها خاضعٌ لسياساتها. فالسببُ ليس ثقبًا قائمًا بل **ألّا يتعلّق هذا
الضمانُ بجداولَ أخرى**: يكفي أن يسقط `FORCE` عن أحدها في ترحيلٍ لاحق،
أو أن يصير المالكُ دورًا متجاوزًا، ليصير `DEFINER` ثقبًا بحجم الدالّة.

## توسعةٌ محضة

ثلاثةُ جداولٍ جديدة، ودالّتان، ومُشغِّلان، وعرض. لا عمودَ يُحذف، ولا
جدولَ قائمٌ يُغيَّر، ولا سياسةَ قائمةٌ تُمسّ، ولا صفَّ يُكتب. والخادمُ
الذي لا يعرف هذا الترحيل يبقى صحيحًا بعد الصعود.

**ولا يُنفَّذ في الإنتاج في هذه المرحلة.**

Revision ID: 0034
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)
UUID = postgresql.UUID(as_uuid=True)

OWNERS = "recruitment_opportunities"
LISTINGS = "recruitment_opportunity_listings"
APPLICATIONS = "recruitment_applications"
PUBLIC_VIEW = "recruitment_opportunities_public"

# ── المفردات المغلقة — مرآتها في `athera_api/models/recruitment.py` ──

OPPORTUNITY_STATES = ("draft", "scheduled", "open", "closed", "deleted")
APPLICATION_STATES = ("pending", "shortlisted", "declined", "invited", "withdrawn")
ACTIVE_APPLICATION_STATES = ("pending", "shortlisted", "invited")

# مصفوفةُ انتقالات المدير — `قبل → بعد`، ولا غيرَها.
#
# **و«مدعوّ» ليست هدفًا في هذه المرحلة، وذاك قرارُ منتجٍ لا نقصُ تنفيذ.**
#
# فالدعوةُ الصحيحة تستوجب `ProjectInvitation` **لصاحب هذا التطبيق بعينه**،
# و`ProjectInvitation` اليوم محلّيّةُ المستأجر: إصدارُها يبحث عن الحساب
# داخل مستأجر البحث. وفرصُ البحث عابرةٌ للمستأجرين قصدًا — فباحثٌ في
# مؤسسةٍ يتقدّم إلى بحثٍ في أخرى.
#
# فربطُ المتقدّم بدعوةٍ عبر المستأجرين يستوجب تصميمَ خدمةٍ صريحًا في
# RC-T1C، **ولا يُوسَّع سلوكُ الدعوات المحلّيّ خِلسةً داخل دفعةٍ أمنية**.
# فبقيت المفردةُ في المخطَّط ولا طريقَ إليها.
MANAGER_TRANSITIONS = (
    ("pending", "shortlisted"),
    ("pending", "declined"),
    ("shortlisted", "declined"),
)

# أفعالُ إنشاء البحث — مرآةُ `collaboration.PROJECT_CREATED_ACTIONS`.
# **ولو زيد فعلٌ هناك ولم يُزد هنا لفقد مالكٌ سلطتَه على بحثه** — ولذلك
# يُقارن الطرفان في فحصٍ صريح لا يُترك للذاكرة.
PROJECT_CREATED_ACTIONS = (
    "portfolio.project_created",
    "workspace.project_created",
    "thesis.project_created",
    "synthesis.project_created",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# ── شرطُ الاكتشاف والقبول: **نصٌّ واحد** ──
#
# يُقرأ في ثلاثة مواضع: سياسةِ الاكتشاف على الإعلانات، ودالّةِ القبول،
# والعرضِ الآمن. وثلاثُ نسخٍ منه تفترق بأوّل تعديل، وحينها يعرض العرضُ
# ما لا تسمح به السياسة، أو يُقبل تقدُّمٌ على بابٍ لا يُرى.
DISCOVERABLE = (
    "status = 'open' AND deleted_at IS NULL "
    "AND starts_at IS NOT NULL AND starts_at <= now() "
    "AND (ends_at IS NULL OR ends_at > now())"
)


# ── دالّةُ الإدارة: سؤالٌ واحد، بحقوق المستدعي ──
#
# «هل الفاعلُ الحاليُّ مديرُ استقطابٍ لهذا البحث؟» — ولا تُجيب عن غيره.
#
# و`STABLE` لا `IMMUTABLE`: جوابُها يتغيّر بتغيّر الصفوف والسياق، ويثبت
# داخل العبارة الواحدة — وهو ما تحتاجه السياساتُ بالضبط.
MANAGES_PROJECT_FN = f"""
CREATE OR REPLACE FUNCTION app_manages_project(p_project_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT app_current_actor() IS NOT NULL
       AND app_current_tenant() IS NOT NULL
       AND (
        -- ١. المالكُ المُثبت: ملفُّ الباحث أوّلًا، ثمّ فاعلُ حدثِ الإنشاء.
        EXISTS (
            SELECT 1
            FROM research_projects p
            LEFT JOIN researcher_profiles rp ON rp.id = p.profile_id
            WHERE p.id = p_project_id
              AND p.tenant_id = app_current_tenant()
              AND coalesce(
                    rp.user_id,
                    (SELECT a.actor_user_id
                       FROM audit_events a
                      WHERE a.object_type = 'research_project'
                        AND a.object_id = p.id
                        AND a.action IN ({_quoted(PROJECT_CREATED_ACTIONS)})
                        AND a.actor_user_id IS NOT NULL
                      ORDER BY a.occurred_at
                      LIMIT 1)
                  ) = app_current_actor()
        )
        -- ٢. أو عضوٌ نشِطٌ له الأساسُ والصلاحيةُ الصريحة معًا.
        --
        -- و`m.tenant_id` **حزامٌ ثانٍ مُعترَفٌ بزيادته**: `project_members`
        -- محكومٌ بسياسة العزل أصلًا، وجُرّب إسقاطُ الشرط فلم يتغيّر سلوك.
        -- فيبقى لأنّه نفسُ المُسنَد الذي يقرؤه RC-T1A، ولا يُدَّعى أنّه
        -- الطبقةُ التي تمنع.
        OR EXISTS (
            SELECT 1
            FROM project_members m
            JOIN project_member_permissions baseline
              ON baseline.member_id = m.id
             AND baseline.permission_key = 'view_project'
            JOIN project_member_permissions wanted
              ON wanted.member_id = m.id
             AND wanted.permission_key = 'manage_team'
            WHERE m.project_id = p_project_id
              AND m.tenant_id = app_current_tenant()
              AND m.user_id = app_current_actor()
              AND m.access_state = 'active'
        )
       )
$$;
"""

# ── «هل يدير الفاعلُ هذه الفرصة؟» ──
#
# وتقرأ **جدولَ النسب** — وهو محكومٌ بسياسة مديره. فجلسةُ متقدّمٍ في
# مستأجرٍ آخر لا ترى صفَّ النسب أصلًا، فتُعيد `false` بلا أن تُسأل عن
# مستأجر. والشرطُ مكتوبٌ فوق ذلك صريحًا: حزامان لا حزام.
MANAGES_OPPORTUNITY_FN = f"""
CREATE OR REPLACE FUNCTION app_manages_opportunity(p_opportunity_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM {OWNERS} o
         WHERE o.id = p_opportunity_id
           AND o.tenant_id = app_current_tenant()
           AND app_manages_project(o.project_id)
    )
$$;
"""

# ── «هل يقبل هذا البابُ تقدُّمًا الآن؟» ──
#
# وهي شرطُ القبول، ونصُّها نصُّ الاكتشاف نفسُه. وبحقوق المستدعي: فسياسةُ
# الاكتشاف على الإعلانات هي التي تُسلّمها الصفَّ، فمن لا يرى إعلانًا لا
# يتقدّم إليه.
ADMITS_FN = f"""
CREATE OR REPLACE FUNCTION app_opportunity_admits(p_opportunity_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM {LISTINGS}
         WHERE opportunity_id = p_opportunity_id
           AND {DISCOVERABLE}
    )
$$;
"""

# ── مُشغِّلُ الإعلان: هويّتُه ثابتة ──
LISTING_GUARD_FN = """
CREATE OR REPLACE FUNCTION recruitment_listing_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    -- **ولا يُنقل إعلانٌ إلى فرصةٍ أخرى**: مفتاحُه الأوّلُ هو نسبُه،
    -- وتعديلُه نقلُ نصٍّ مُعلَنٍ إلى بحثٍ لم يكتبه.
    IF NEW.opportunity_id <> OLD.opportunity_id THEN
        RAISE EXCEPTION
          'a recruitment listing belongs to the opportunity it was written for'
          USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'the birth time of a recruitment listing is not editable'
          USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;
"""

# ── مُشغِّلُ التطبيق: الهويّةُ ثابتة، والانتقالُ مصفوفةٌ مكتوبة ──
#
# **وهذا ما لا تقدر عليه RLS**: `WITH CHECK` ترى الصفَّ الجديد ولا ترى
# القديم، فلا تعرف «من أيّ حالٍ إلى أيّ حال» ولا «أيُّ عمودٍ تغيّر».
APPLICATION_GUARD_FN = f"""
CREATE OR REPLACE FUNCTION recruitment_application_guard() RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
    actor uuid := app_current_actor();
    owning_project uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- **ويُولد التطبيقُ في الانتظار**: فمن يكتب صفَّه `shortlisted`
        -- من أوّل لحظةٍ يمنح نفسَه ما لا يملك، ولا `OLD` تمنعه.
        IF NEW.status <> 'pending' THEN
            RAISE EXCEPTION
              'a recruitment application is born pending, not %', NEW.status
              USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.decided_at IS NOT NULL OR NEW.decided_by IS NOT NULL
           OR NEW.withdrawn_at IS NOT NULL OR NEW.invitation_id IS NOT NULL THEN
            RAISE EXCEPTION
              'a new recruitment application carries no decision, no withdrawal '
              'and no invitation'
              USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- ── هويّةٌ ثابتة: لا تُنقل، ولا تُنتحل، ولا يُحرَّف نصُّ صاحبها ──
    IF NEW.id <> OLD.id
       OR NEW.opportunity_id <> OLD.opportunity_id
       OR NEW.applicant_user_id <> OLD.applicant_user_id
       OR NEW.applicant_tenant_id <> OLD.applicant_tenant_id
       OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'the identity of a recruitment application is immutable'
          USING ERRCODE = 'check_violation';
    END IF;
    -- ونصُّ المتقدّم لا يُعدَّل بعد الإرسال: تعديلُ المدير تحريفُ إقرارِ
    -- غيره، وتعديلُ صاحبه بعد القراءة يُغيّر ما بُني عليه قرار.
    IF NEW.message IS DISTINCT FROM OLD.message THEN
        RAISE EXCEPTION 'an applicant''s own words are not edited after submission'
          USING ERRCODE = 'check_violation';
    END IF;

    -- ══ صاحبُ التطبيق: ينسحب وحسب ══
    IF actor IS NOT NULL AND actor = OLD.applicant_user_id THEN
        IF NEW.decided_at IS DISTINCT FROM OLD.decided_at
           OR NEW.decided_by IS DISTINCT FROM OLD.decided_by
           OR NEW.invitation_id IS DISTINCT FROM OLD.invitation_id THEN
            RAISE EXCEPTION 'an applicant writes no decision about their own application'
              USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status = OLD.status THEN
            -- **ووقتُ الانسحاب لا يُعاد كتابتُه على حالٍ لم تتغيّر.**
            -- وهذا وُجد بعضّ الحارس: كان البابُ مفتوحًا لصاحبِ صفٍّ
            -- منسحبٍ أن يُقدّم وقتَ انسحابه أو يؤخّره، وذاك أثرٌ يُقرأ
            -- في نزاعٍ على أسبقيّة.
            IF NEW.withdrawn_at IS DISTINCT FROM OLD.withdrawn_at THEN
                RAISE EXCEPTION 'the time of a withdrawal is written once'
                  USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END IF;
        IF NEW.status <> 'withdrawn' THEN
            RAISE EXCEPTION
              'an applicant may only withdraw; ''%'' is a decision, and a decision '
              'is never self-awarded', NEW.status
              USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.status NOT IN ({_quoted(ACTIVE_APPLICATION_STATES)}) THEN
            RAISE EXCEPTION 'only a live application can be withdrawn (it was ''%'')',
              OLD.status
              USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- ══ المدير: يُرشّح ويعتذر — ولا ينسحب عن أحد ══
    --
    -- وسلطتُه على هذه الفرصة أثبتتها السياسةُ قبل بلوغ هذا المُشغِّل.
    IF NEW.status = 'withdrawn' OR NEW.withdrawn_at IS DISTINCT FROM OLD.withdrawn_at THEN
        RAISE EXCEPTION 'withdrawal is the applicant''s own act, not a decision about them'
          USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.status = OLD.status THEN
        IF NEW.decided_at IS DISTINCT FROM OLD.decided_at
           OR NEW.decided_by IS DISTINCT FROM OLD.decided_by
           OR NEW.invitation_id IS DISTINCT FROM OLD.invitation_id THEN
            RAISE EXCEPTION 'a decision is not rewritten after the fact'
              USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    IF (OLD.status, NEW.status) NOT IN (
        {", ".join(f"('{a}','{b}')" for a, b in MANAGER_TRANSITIONS)}
    ) THEN
        RAISE EXCEPTION 'no such transition on a recruitment application: ''%'' -> ''%''',
          OLD.status, NEW.status
          USING ERRCODE = 'check_violation';
    END IF;
    -- ومن حسم يُنسب إليه ما حسم — بفاعل الجلسة لا بما كُتب في الطلب.
    IF NEW.decided_by IS DISTINCT FROM actor THEN
        RAISE EXCEPTION 'a decision names its author, and its author is the acting session'
          USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.decided_at IS NULL THEN
        RAISE EXCEPTION 'a decision has a time'
          USING ERRCODE = 'check_violation';
    END IF;

    -- ══ و«مدعوّ» لا طريقَ إليها في هذه المرحلة ══
    --
    -- **والمانعُ هو المصفوفةُ أعلاه**: لا زوجَ فيها هدفُه `invited`، فأيُّ
    -- محاولةٍ تسقط عند «لا انتقالَ كهذا» قبل أن تبلغ هذا الموضع. وهذه
    -- الكتلةُ **غيرُ قابلةٍ للبلوغ في RC-T1B**، ولا يُدَّعى أنّها
    -- الطبقةُ التي تمنع.
    --
    -- وتبقى لأنّها تمنع عطبًا مُحتملًا بعينه: مَن يزيد «مدعوّ» هدفًا إلى
    -- المصفوفة **قبل أن تُبنى خدمةُ التحويل** يجد أنّ الحالةَ ما زالت
    -- تستوجب دعوةً حقيقيةً في بحثِ الفرصة نفسِه. فهي حزامٌ تحت خطأٍ
    -- متوقَّع لا اكتمالٌ نظريّ.
    --
    -- **وما تزال ناقصةً حتى لذلك الغرض**: تُثبت أنّ الدعوةَ لبحثِ الفرصة
    -- ولا تُثبت أنّها **لصاحب هذا التطبيق بعينه** — وذاك بالضبط ما يستوجب
    -- تصميمَ RC-T1C، لأنّ الدعواتَ محلّيّةُ المستأجر والتطبيقاتُ عابرةٌ له.
    IF NEW.status = 'invited' THEN
        SELECT o.project_id INTO owning_project
          FROM {OWNERS} o WHERE o.id = OLD.opportunity_id;
        IF owning_project IS NULL OR NOT EXISTS (
            SELECT 1 FROM project_invitations i
             WHERE i.id = NEW.invitation_id
               AND i.project_id = owning_project
        ) THEN
            RAISE EXCEPTION
              'INVITED requires a real ProjectInvitation on the opportunity''s own '
              'project — recruitment is not a second door into a research team'
              USING ERRCODE = 'check_violation';
        END IF;
    ELSIF NEW.invitation_id IS DISTINCT FROM OLD.invitation_id THEN
        RAISE EXCEPTION 'an invitation is linked only when the application becomes invited'
          USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END
$$;
"""


def upgrade() -> None:
    # ── ٠. شرطُ إصدارٍ صريح، لا مفاجأةٌ صامتة ──
    #
    # `security_invoker` على العروض من PostgreSQL 15. وعلى إصدارٍ أقدم
    # يُتجاهل الخيارُ **بلا خطأ**، فيُقيَّم العرضُ بحقوق مالكه.
    op.execute(
        """
        DO $$
        BEGIN
            IF current_setting('server_version_num')::int < 150000 THEN
                RAISE EXCEPTION
                  'recruitment discovery needs PostgreSQL 15+ for security_invoker views (found %)',
                  current_setting('server_version');
            END IF;
        END
        $$;
        """
    )

    # ══════ ١. النسب — السجلُّ الخاصُّ الذي لا يعبُر المستأجر ══════
    op.create_table(
        OWNERS,
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("project_id", UUID,
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_recruitment_opportunities_tenant_id", OWNERS, ["tenant_id"])
    op.create_index("ix_recruitment_opportunities_project", OWNERS, ["project_id"])

    # ══════ ٢. الإعلان — وهذا وحده ما يُقرأ من خارج المستأجر ══════
    #
    # **ولا `tenant_id` فيه ولا `project_id` ولا `created_by`** — وذاك هو
    # الحدّ، لا السياسةُ وحدها.
    op.create_table(
        LISTINGS,
        sa.Column("opportunity_id", UUID,
                  sa.ForeignKey(f"{OWNERS}.id", ondelete="RESTRICT"),
                  primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("contributions", sa.Text, nullable=True),
        sa.Column("requirements", sa.Text, nullable=True),
        sa.Column("specialization", sa.String(120), nullable=True),
        sa.Column("openings_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("collaboration_type", sa.String(40), nullable=False),
        sa.Column("public_label", sa.String(160), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("starts_at", TS, nullable=True),
        sa.Column("ends_at", TS, nullable=True),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        # **والأسماءُ قصيرةٌ عمدًا** — الاصطلاحُ يُبادئها، والتجاوزُ فوق
        # ثلاثةٍ وستين محرفًا **يُقصّ صامتًا** (0032).
        sa.CheckConstraint(
            f"status IN ({_quoted(OPPORTUNITY_STATES)})",
            name="status_is_known"),
        sa.CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR starts_at < ends_at",
            name="window_is_ordered"),
        sa.CheckConstraint(
            "openings_count > 0",
            name="openings_are_positive"),
        sa.CheckConstraint(
            "status <> 'open' OR starts_at IS NOT NULL",
            name="open_needs_a_start"),
    )
    op.create_index("ix_recruitment_listings_discovery", LISTINGS,
                    ["status", "starts_at", "ends_at"])

    # ══════ ٣. التطبيقات — ولا عمودَ `tenant_id` حاكمًا فيها ══════
    #
    # وهذا **قصدٌ لا سهو**. الصفُّ يعيش بين مستأجرَين: المتقدّمُ في واحد،
    # والفرصةُ في آخر. فبأيِّهما يُوسم؟ لو وُسم بمستأجر الفرصة لم يرَ
    # المتقدّمُ تقدُّمَه، ولو وُسم بمستأجر المتقدّم لم يرَه صاحبُ الفرصة.
    op.create_table(
        APPLICATIONS,
        sa.Column("id", UUID, primary_key=True),
        # **و`RESTRICT` لا `CASCADE`.** الحذفُ المتسلسل كان سيجعل حذفَ صفِّ
        # فرصةٍ واحدًا يمحو تقدُّمَ باحثين في مستأجرين آخرين — ويجري
        # بحقوق مالك الجدول، فلا RLS تراه ولا صلاحيةَ تمنعه.
        sa.Column("opportunity_id", UUID,
                  sa.ForeignKey(f"{OWNERS}.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("applicant_user_id", UUID,
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("applicant_tenant_id", UUID,
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("withdrawn_at", TS, nullable=True),
        sa.Column("decided_at", TS, nullable=True),
        sa.Column("decided_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("invitation_id", UUID,
                  sa.ForeignKey("project_invitations.id", ondelete="RESTRICT"),
                  nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_quoted(APPLICATION_STATES)})",
            name="status_is_known"),
        sa.CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="withdrawal_has_a_time"),
        # **و«مدعوّ» لا تُكتب بلا دعوةٍ حقيقية** — والمُشغِّل يشترط فوق
        # ذلك أن تكون دعوةَ بحثِ الفرصة نفسِه.
        sa.CheckConstraint(
            "status <> 'invited' OR invitation_id IS NOT NULL",
            name="invited_needs_an_invitation"),
    )
    op.create_index("ix_recruitment_applications_opportunity", APPLICATIONS,
                    ["opportunity_id"])
    op.create_index("ix_recruitment_applications_applicant", APPLICATIONS,
                    ["applicant_user_id"])

    # **ولا تطبيقانِ قائمان لحسابٍ واحد على فرصةٍ واحدة.**
    #
    # وفهرسٌ **جزئيّ** لا قيدٌ كامل: المنسحبُ له أن يعود، والمرفوضُ لا
    # يُحجَب عن غيرها. والمنعُ في القاعدة لا في الواجهة، فطلبانِ متزامنان
    # يسقط أحدُهما بيد المحرّك لا بيد فحصٍ سبقَ الكتابة.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recruitment_applications_active "
        f"ON {APPLICATIONS} (opportunity_id, applicant_user_id) "
        f"WHERE status IN ({_quoted(ACTIVE_APPLICATION_STATES)})"
    )

    # ══════ ٤. دوالُّ التفويض والقبول ══════
    for statement in (MANAGES_PROJECT_FN, MANAGES_OPPORTUNITY_FN, ADMITS_FN):
        op.execute(statement)
    # ولا تنفيذَ عامّ: دورُ التطبيق وحده.
    for signature in ("app_manages_project(uuid)", "app_manages_opportunity(uuid)",
                      "app_opportunity_admits(uuid)"):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO athera_app")

    # ══════ ٥. العزل والصلاحيات ══════
    for table in (OWNERS, LISTINGS, APPLICATIONS):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE: السياسةُ تنطبق على مالك الجدول أيضًا — لا بابَ خلفيًّا.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # **والنسبُ يُكتب مرّةً**: قراءةٌ وإدراجٌ ولا شيءَ بعدهما — كما فعل
    # 0003 بسجلّ التدقيق. فثباتُ `tenant_id` و`project_id` و`created_by`
    # **غيابُ طريقٍ لا حارسٌ يُفحَص**.
    op.execute(f"GRANT SELECT, INSERT ON {OWNERS} TO athera_app")
    op.execute(f"REVOKE UPDATE, DELETE ON {OWNERS} FROM athera_app")
    for table in (LISTINGS, APPLICATIONS):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO athera_app")
        # وحزامٌ ثانٍ تحت السياسة: لا صلاحيةَ حذفٍ أصلًا، فلا سياسةٌ تُكتب
        # سهوًا تُفتح بها ثغرة.
        op.execute(f"REVOKE DELETE ON {table} FROM athera_app")

    # ── ٥أ. النسب: سياسةُ مديرٍ وحدها ولا سياسةَ عابرةً للمستأجرين ──
    owner_manager = "tenant_id = app_current_tenant() AND app_manages_project(project_id)"
    op.execute(
        f"CREATE POLICY {OWNERS}_manager_read ON {OWNERS} "
        f"FOR SELECT USING ({owner_manager})"
    )
    # **ومن أنشأ يُنسب إليه ما أنشأ** — بفاعل الجلسة لا بما كُتب في الطلب.
    op.execute(
        f"CREATE POLICY {OWNERS}_manager_insert ON {OWNERS} "
        f"FOR INSERT WITH CHECK ({owner_manager} AND created_by = app_current_actor())"
    )

    # ── ٥ب. الإعلان: مديرٌ يكتب ويعدّل، وعالَمٌ يقرأ المفتوحَ وحده ──
    op.execute(
        f"CREATE POLICY {LISTINGS}_manager_read ON {LISTINGS} "
        "FOR SELECT USING (app_manages_opportunity(opportunity_id))"
    )
    op.execute(
        f"CREATE POLICY {LISTINGS}_manager_insert ON {LISTINGS} "
        "FOR INSERT WITH CHECK (app_manages_opportunity(opportunity_id))"
    )
    op.execute(
        f"CREATE POLICY {LISTINGS}_manager_update ON {LISTINGS} "
        "FOR UPDATE USING (app_manages_opportunity(opportunity_id)) "
        "WITH CHECK (app_manages_opportunity(opportunity_id))"
    )
    # والاكتشافُ عبر المستأجرين: **قراءةٌ فقط، وصفوفٌ بعينها**.
    #
    # و`FOR SELECT` بلا `WITH CHECK` — فلا تُسهم هذه السياسةُ في إدراجٍ
    # ولا تعديلٍ ولا حذف. والفاعلُ شرط: الاكتشافُ لباحثٍ معروفٍ لا لجلسةٍ
    # بلا هويّة. **ولا `USING (true)` في هذا الترحيل.**
    op.execute(
        f"CREATE POLICY {LISTINGS}_discovery ON {LISTINGS} "
        f"FOR SELECT USING (app_current_actor() IS NOT NULL AND {DISCOVERABLE})"
    )

    # ── ٥ج. التطبيقات: حدُّها الفاعل ──
    #
    # وأربعُ سياساتٍ لا واحدةٌ شاملة، لأنّ الأفعالَ تختلف في شرطها.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_read ON {APPLICATIONS} "
        "FOR SELECT USING (applicant_user_id = app_current_actor())"
    )
    # وعند التقدّم يُقيَّد المستأجرُ المُعلَن بالسياق (**لا يُزوّر المتقدّم
    # المؤسسةَ التي جاء منها**)، ويُشترط **بابٌ مفتوحٌ الآن**: فمعرّفُ
    # فرصةٍ عُرف حين كانت مفتوحةً لا يصير مفتاحًا بعد إغلاقها.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_insert ON {APPLICATIONS} "
        "FOR INSERT WITH CHECK (applicant_user_id = app_current_actor() "
        "AND applicant_tenant_id = app_current_tenant() "
        "AND app_opportunity_admits(opportunity_id))"
    )
    # والانسحابُ تعديلٌ بيد صاحبه — والمُشغِّلُ يحصره في الانسحاب. ولا
    # شرطَ مستأجرٍ هنا: من ينتمي إلى مؤسستين ويدخل بالثانية يبقى صاحبَ
    # تقدُّمه الأوّل.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_update ON {APPLICATIONS} "
        "FOR UPDATE USING (applicant_user_id = app_current_actor()) "
        "WITH CHECK (applicant_user_id = app_current_actor())"
    )
    # **ولا سياسةَ حذفٍ لأحد.** التطبيقُ يُنسحب منه ولا يُمحى: أثرُ من
    # تقدّم ومن رُفض هو نفسُه ما يُسأل عنه في نزاع.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_manager_read ON {APPLICATIONS} "
        "FOR SELECT USING (app_manages_opportunity(opportunity_id))"
    )
    # والمديرُ يُرشّح ويعتذر — ولا **يُنشئ** تطبيقًا عن أحد. فالتقدّمُ
    # فعلٌ شخصيّ، وتطبيقٌ يكتبه غيرُ صاحبه إقرارٌ منسوبٌ إلى من لم يُقرّ.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_manager_update ON {APPLICATIONS} "
        "FOR UPDATE USING (app_manages_opportunity(opportunity_id)) "
        "WITH CHECK (app_manages_opportunity(opportunity_id))"
    )

    # ══════ ٦. المُشغِّلات — ما لا تقدر عليه RLS ══════
    op.execute(LISTING_GUARD_FN)
    op.execute(APPLICATION_GUARD_FN)
    op.execute(
        f"CREATE TRIGGER trg_{LISTINGS}_guard BEFORE UPDATE ON {LISTINGS} "
        "FOR EACH ROW EXECUTE FUNCTION recruitment_listing_guard()"
    )
    op.execute(
        f"CREATE TRIGGER trg_{APPLICATIONS}_guard "
        f"BEFORE INSERT OR UPDATE ON {APPLICATIONS} "
        "FOR EACH ROW EXECUTE FUNCTION recruitment_application_guard()"
    )

    # ══════ ٧. الإسقاطُ الآمن ══════
    #
    # وهو الآن **راحةٌ لا حدّ**: الحدُّ صار في المخطَّط، فالإعلانُ لا يحمل
    # عمودًا خاصًّا أصلًا. ويبقى العرضُ لأنّه يُسمّي ما يُعرض صريحًا،
    # ويُسقط ما لا معنى له في الاكتشاف (`status` و`deleted_at`
    # و`updated_at`) — ولو قُرئ الجدولُ مباشرةً لم يُكشف شيءٌ خاصّ.
    op.execute(
        f"CREATE VIEW {PUBLIC_VIEW} "
        "WITH (security_invoker = true, security_barrier = true) AS "
        "SELECT opportunity_id AS id, title, description, contributions, requirements, "
        "       specialization, collaboration_type, openings_count, "
        "       public_label, starts_at, ends_at, created_at "
        f"  FROM {LISTINGS} "
        f" WHERE {DISCOVERABLE}"
    )
    op.execute(f"GRANT SELECT ON {PUBLIC_VIEW} TO athera_app")
    # ولا كتابةَ عبر العرض: `ALTER DEFAULT PRIVILEGES` في 0003 تمنح
    # الكتابةَ على كلّ ما يُنشأ في المخطَّط — والعروضُ منه.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {PUBLIC_VIEW} FROM athera_app")


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {PUBLIC_VIEW}")
    # والمُشغِّلاتُ تسقط مع جداولها، ودوالُّها تُسقط صريحًا بعدها.
    for table in (APPLICATIONS, LISTINGS, OWNERS):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    op.execute("DROP FUNCTION IF EXISTS recruitment_application_guard()")
    op.execute("DROP FUNCTION IF EXISTS recruitment_listing_guard()")
    # والدوالُّ تُسقط بعد السياساتِ التي تقرؤها، لا قبلها.
    op.execute("DROP FUNCTION IF EXISTS app_opportunity_admits(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_manages_opportunity(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_manages_project(uuid)")
