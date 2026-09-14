"""أساسُ الاستقطاب الآمن | RC-T1B: cross-tenant recruitment, narrowly.

**الحدُّ الذي يُكسَر هنا لأوّل مرّة، ولمَ يجوز كسرُه.**

كلُّ صفٍّ في المنصّة قبل هذا الترحيل يُقرأ ويُكتب داخل مستأجرٍ واحد:
`tenant_id = app_current_tenant()`، لا استثناء. وقرارُ المنتج في هذه
المرحلة يستوجب أن **يكتشف باحثٌ في مؤسسةٍ فرصةَ تعاونٍ أعلنها بحثٌ في
مؤسسةٍ أخرى، وأن يتقدّم إليها**.

ولو تُرك ذلك للتطبيق — استعلامٌ بلا شرط مستأجر — لصار العزلُ سياسةَ
كتابةِ كودٍ لا خاصيّةَ قاعدة. فالحدُّ يُكسَر **في القاعدة، وبأضيق ما
يكفي**:

  ١. الفرصةُ تبقى مملوكةً لمستأجرها، ولها سياستان لا واحدة:
     • سياسةُ المدير — كلُّ الأفعال، داخل المستأجر، وبتفويضٍ مُثبت.
     • سياسةُ الاكتشاف — **قراءةٌ فقط**، ومحدودةٌ بصفوفٍ بعينها:
       `open` وغيرُ محذوفةٍ وداخلَ نافذتها الزمنية. **ولا
       `USING (true)` في هذا الترحيل ولا في غيره.**
  ٢. التطبيقُ — وهو الصفُّ الذي يعيش بين مستأجرَين — **حدُّه الفاعل لا
     المستأجر**: `applicant_user_id = app_current_actor()`.

ولذلك سبق هذا الترحيلَ تدقيقُ مصدر الفاعل من طرفٍ إلى طرف: سياسةٌ تعتمد
`app_current_actor()` لا تصحّ إلّا إذا كان الفاعلُ غيرَ قابلٍ للاختيار من
العميل. وهو كذلك: يُضبط في `db.tenant_session` و`routers.auth._bind_tenant`
وحدهما، ومصدرُه في كلّ مرّة رمزٌ مُوقَّع أو سجلُّ اعتمادٍ مُتحقَّق — لا جسمُ
طلبٍ ولا مُعامِلُ استعلامٍ ولا ترويسة.

## والفشلُ آمنٌ بالبناء لا بالاتفاق

`app_current_actor()` تُعيد `NULL` عند غياب الضبط، وكلُّ مقارنةٍ بـ`NULL`
تُعطي `NULL` — والسياسةُ لا تطابق. فجلسةٌ بلا فاعلٍ **لا ترى تطبيقًا ولا
تكتبه**، وجلسةٌ بفاعلٍ مشوَّه يسقط `::uuid` فيها فتُلغى المعاملة.

## ولمَ دالّةٌ بحقوق المستدعي لا `SECURITY DEFINER`

`app_manages_project()` تُقرأ داخل السياسات، وهي **بحقوق مستدعيها**
قصدًا: فتبقى الجداولُ التي تقرأها (`research_projects`،
`project_members`، `project_member_permissions`، `researcher_profiles`،
`audit_events`) خاضعةً لـRLS بحقوق القارئ نفسِه. فلو استُدعيت من جلسة
المتقدّم في مستأجرٍ آخر لم ترَ شيئًا وأعادت `false`.

**وقد جُرّبت بـ`SECURITY DEFINER` فلم يتغيّر سلوكٌ واحد** — والسببُ أنّ
الجداولَ الخمسةَ كلَّها عليها `FORCE ROW LEVEL SECURITY`، فمالكُها خاضعٌ
لسياساتها أيضًا. فالسببُ ليس ثقبًا قائمًا بل **ألّا يتعلّق هذا الضمانُ
بخمسة جداولٍ أخرى**: يكفي أن يسقط `FORCE` عن أحدها في ترحيلٍ لاحق، أو أن
يصير المالكُ دورًا متجاوزًا، ليصير `DEFINER` ثقبًا بحجم الدالّة. وحقوقُ
المستدعي لا تحتاج شيئًا من ذلك لتبقى صحيحة.

وهي مرآةٌ حرفيّة لـ`services/collaboration.py`: المالكُ من نسبٍ مُثبت
(ملفُّ الباحث، ثمّ فاعلُ حدث الإنشاء)، والمديرُ غيرُ المالك عضوٌ **نشِط**
له `view_project` أساسًا **و**`manage_team` صريحة. **ولا دورَ يُترجم إلى
سلطة**: `principal_investigator` اسمُ دورٍ لا تفويض.

## وعرضٌ للإسقاط، وسياسةٌ للصفوف

RLS تحكم الصفوفَ لا الأعمدة. فالإسقاطُ الآمن عرضٌ صريح —
`recruitment_opportunities_public` — لا يحمل `project_id` ولا `tenant_id`
ولا `created_by`. وهو `security_invoker` كي تُقيَّم السياساتُ بحقوق
القارئ لا بحقوق مالك العرض، و`security_barrier` كي لا يُسرَّب شيءٌ عبر
دالّةٍ رخيصةٍ تُدفع تحت الشرط.

## توسعةٌ محضة

جدولان جديدان ودالّةٌ وعرض. لا عمودَ يُحذف، ولا جدولَ قائمٌ يُغيَّر، ولا
سياسةَ قائمةٌ تُمسّ، ولا صفَّ يُكتب. والخادمُ الذي لا يعرف هذا الترحيل
يبقى صحيحًا بعد الصعود.

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

OPPORTUNITIES = "recruitment_opportunities"
APPLICATIONS = "recruitment_applications"
PUBLIC_VIEW = "recruitment_opportunities_public"

# ── المفردات المغلقة — مرآتها في `athera_api/models/recruitment.py` ──

OPPORTUNITY_STATES = ("draft", "scheduled", "open", "closed", "deleted")
APPLICATION_STATES = ("pending", "shortlisted", "declined", "invited", "withdrawn")
ACTIVE_APPLICATION_STATES = ("pending", "shortlisted", "invited")

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

# شرطُ الاكتشاف — **مكتوبٌ مرّةً واحدة**، يُستعمل في السياسة وفي العرض.
# فشرطانِ متطابقانِ منسوخانِ يفترقان بأوّل تعديل، وحينها يعرض العرضُ ما
# لا تسمح به السياسة أو العكس.
DISCOVERABLE = (
    "status = 'open' AND deleted_at IS NULL "
    "AND starts_at IS NOT NULL AND starts_at <= now() "
    "AND (ends_at IS NULL OR ends_at > now())"
)


def upgrade() -> None:
    # ── ٠. شرطُ إصدارٍ صريح، لا مفاجأةٌ صامتة ──
    #
    # `security_invoker` على العروض من PostgreSQL 15. وعلى إصدارٍ أقدم
    # يُتجاهل الخيارُ **بلا خطأ**، فيُقيَّم العرضُ بحقوق مالكه ويصير
    # الإسقاطُ الآمنُ بابًا. فيُرفع الخطأُ هنا صراحةً.
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

    # ── ١. الفرص ──
    op.create_table(
        OPPORTUNITIES,
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("project_id", UUID,
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("contributions", sa.Text, nullable=True),
        sa.Column("requirements", sa.Text, nullable=True),
        sa.Column("specialization", sa.String(120), nullable=True),
        sa.Column("openings_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("collaboration_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("starts_at", TS, nullable=True),
        sa.Column("ends_at", TS, nullable=True),
        sa.Column("public_label", sa.String(160), nullable=True),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("deleted_at", TS, nullable=True),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        # **والأسماءُ قصيرةٌ عمدًا**: الاصطلاحُ يُبادئها، والتجاوزُ فوق
        # ثلاثةٍ وستين محرفًا **يُقصّ صامتًا** (الترحيل 0032).
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
    op.create_index("ix_recruitment_opportunities_tenant_id", OPPORTUNITIES, ["tenant_id"])
    op.create_index("ix_recruitment_opportunities_project", OPPORTUNITIES, ["project_id"])
    op.create_index("ix_recruitment_opportunities_discovery", OPPORTUNITIES,
                    ["status", "starts_at", "ends_at"])

    # ── ٢. التطبيقات — ولا عمودَ `tenant_id` فيها ──
    #
    # وهذا **قصدٌ لا سهو**. الصفُّ يعيش بين مستأجرَين: المتقدّمُ في واحد،
    # والفرصةُ في آخر. فبأيِّهما يُوسم؟ لو وُسم بمستأجر الفرصة لم يرَ
    # المتقدّمُ تقدُّمَه، ولو وُسم بمستأجر المتقدّم لم يرَه صاحبُ الفرصة.
    # فلا وسمَ مستأجرٍ يحكمه، و`applicant_tenant_id` **للأثر لا للتفويض**.
    op.create_table(
        APPLICATIONS,
        sa.Column("id", UUID, primary_key=True),
        # **و`RESTRICT` لا `CASCADE`.** الحذفُ المتسلسل كان سيجعل حذفَ صفِّ
        # فرصةٍ واحدًا يمحو تقدُّمَ باحثين في مستأجرين آخرين — ويجري
        # بحقوق مالك الجدول، فلا RLS تراه ولا صلاحيةَ تمنعه. فالتطبيقُ
        # يُثبّت فرصتَه، والإخفاءُ يقع بـ`deleted_at` لا بالإتلاف.
        sa.Column("opportunity_id", UUID,
                  sa.ForeignKey(f"{OPPORTUNITIES}.id", ondelete="RESTRICT"),
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
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            f"status IN ({_quoted(APPLICATION_STATES)})",
            name="status_is_known"),
        sa.CheckConstraint(
            "(status = 'withdrawn') = (withdrawn_at IS NOT NULL)",
            name="withdrawal_has_a_time"),
    )
    op.create_index("ix_recruitment_applications_opportunity", APPLICATIONS,
                    ["opportunity_id"])
    op.create_index("ix_recruitment_applications_applicant", APPLICATIONS,
                    ["applicant_user_id"])

    # **ولا تطبيقانِ قائمان لحسابٍ واحد على فرصةٍ واحدة — والقاعدةُ تمنع.**
    #
    # وفهرسٌ **جزئيّ** لا قيدٌ كامل: المنسحبُ له أن يعود، والمرفوضُ لا
    # يُحجَب عن غيرها. والمنعُ في القاعدة لا في الواجهة، فطلبانِ متزامنان
    # يسقط أحدُهما بيد المحرّك لا بيد فحصٍ سبقَ الكتابة.
    op.execute(
        f"CREATE UNIQUE INDEX uq_recruitment_applications_active "
        f"ON {APPLICATIONS} (opportunity_id, applicant_user_id) "
        f"WHERE status IN ({_quoted(ACTIVE_APPLICATION_STATES)})"
    )

    # ── ٣. دالّةُ الإدارة ──
    op.execute(MANAGES_PROJECT_FN)
    # ولا تنفيذَ عامّ: دورُ التطبيق وحده.
    op.execute("REVOKE ALL ON FUNCTION app_manages_project(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app_manages_project(uuid) TO athera_app")

    # ── ٤. العزل ──
    for table in (OPPORTUNITIES, APPLICATIONS):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE: السياسةُ تنطبق على مالك الجدول أيضًا — لا بابَ خلفيًّا.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO athera_app")
        # **وحزامٌ ثانٍ تحت السياسة** — كما فعل 0003 بسجلّ التدقيق: لا
        # صلاحيةَ حذفٍ أصلًا، فلا سياسةٌ تُكتب سهوًا تُفتح بها ثغرة.
        op.execute(f"REVOKE DELETE ON {table} FROM athera_app")

    # الفرص: سلطةُ المدير داخل مستأجره.
    #
    # **وثلاثُ سياساتٍ بأفعالها لا `FOR ALL` واحدة.** فـ`FOR ALL` تشمل
    # `DELETE`، ودورةُ الحياة المُقرَّرة حذفٌ ناعم: `deleted_at`. ولو
    # كُتبت شاملةً لبقي الحذفُ الصلبُ ممنوعًا بالصلاحية وحدها — ومنحٌ
    # شاملٌ في ترحيلٍ لاحق (وهو نمطٌ قائم في 0003) كان سيفتحه صامتًا.
    # فلا فعلَ حذفٍ مسموحٌ **في السياسة نفسها**.
    manager = "tenant_id = app_current_tenant() AND app_manages_project(project_id)"
    op.execute(
        f"CREATE POLICY {OPPORTUNITIES}_manager_read ON {OPPORTUNITIES} "
        f"FOR SELECT USING ({manager})"
    )
    op.execute(
        f"CREATE POLICY {OPPORTUNITIES}_manager_insert ON {OPPORTUNITIES} "
        f"FOR INSERT WITH CHECK ({manager})"
    )
    op.execute(
        f"CREATE POLICY {OPPORTUNITIES}_manager_update ON {OPPORTUNITIES} "
        f"FOR UPDATE USING ({manager}) WITH CHECK ({manager})"
    )
    # والاكتشافُ عبر المستأجرين: **قراءةٌ فقط، وصفوفٌ بعينها**.
    #
    # و`FOR SELECT` بلا `WITH CHECK` — فلا تُسهم هذه السياسةُ في إدراجٍ
    # ولا تعديلٍ ولا حذف. والفاعلُ شرط: الاكتشافُ لباحثٍ معروفٍ لا لجلسةٍ
    # بلا هويّة.
    op.execute(
        f"CREATE POLICY {OPPORTUNITIES}_discovery ON {OPPORTUNITIES} "
        f"FOR SELECT USING (app_current_actor() IS NOT NULL AND {DISCOVERABLE})"
    )

    # التطبيقات: حدُّها الفاعل.
    #
    # وأربعُ سياساتٍ لا واحدةٌ شاملة، لأنّ الأفعالَ تختلف في شرطها:
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_read ON {APPLICATIONS} "
        "FOR SELECT USING (applicant_user_id = app_current_actor())"
    )
    # وعند التقدّم يُقيَّد المستأجرُ المُعلَن بالسياق: **لا يُزوّر المتقدّم
    # المؤسسةَ التي جاء منها**، وهي ما يُقرأ في التدقيق بعد شهور.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_insert ON {APPLICATIONS} "
        "FOR INSERT WITH CHECK (applicant_user_id = app_current_actor() "
        "AND applicant_tenant_id = app_current_tenant())"
    )
    # والانسحابُ تعديلٌ بيد صاحبه. ولا شرطَ مستأجرٍ هنا: من ينتمي إلى
    # مؤسستين ويدخل بالثانية يبقى صاحبَ تقدُّمه الأوّل.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_self_update ON {APPLICATIONS} "
        "FOR UPDATE USING (applicant_user_id = app_current_actor()) "
        "WITH CHECK (applicant_user_id = app_current_actor())"
    )
    # **ولا سياسةَ حذفٍ لأحد.** التطبيقُ يُنسحب منه ولا يُمحى: أثرُ من
    # تقدّم ومن رُفض هو نفسُه ما يُسأل عنه في نزاع.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_manager_read ON {APPLICATIONS} "
        "FOR SELECT USING (EXISTS ("
        f"  SELECT 1 FROM {OPPORTUNITIES} o "
        "   WHERE o.id = opportunity_id "
        "     AND o.tenant_id = app_current_tenant() "
        "     AND app_manages_project(o.project_id)))"
    )
    # والمديرُ يُرشّح ويعتذر — ولا **يُنشئ** تطبيقًا عن أحد. فالتقدّمُ فعلٌ
    # شخصيّ، وتطبيقٌ يكتبه غيرُ صاحبه إقرارٌ منسوبٌ إلى من لم يُقرّ.
    op.execute(
        f"CREATE POLICY {APPLICATIONS}_manager_update ON {APPLICATIONS} "
        "FOR UPDATE USING (EXISTS ("
        f"  SELECT 1 FROM {OPPORTUNITIES} o "
        "   WHERE o.id = opportunity_id "
        "     AND o.tenant_id = app_current_tenant() "
        "     AND app_manages_project(o.project_id))) "
        "WITH CHECK (EXISTS ("
        f"  SELECT 1 FROM {OPPORTUNITIES} o "
        "   WHERE o.id = opportunity_id "
        "     AND o.tenant_id = app_current_tenant() "
        "     AND app_manages_project(o.project_id)))"
    )

    # ── ٥. الإسقاطُ الآمن ──
    #
    # **وما لا يخرج من هذا العرض**: `project_id` و`tenant_id`
    # و`created_by` و`status` و`deleted_at` و`updated_at`. فمعرّفُ البحث
    # مفتاحٌ إلى كلِّ ما يتعلّق به، ومعرّفُ المستأجر يكشف المؤسسةَ لمن لم
    # يُعلنها صاحبُها، ومنشئُ الفرصة اسمُ إنسانٍ لا حاجةَ به في الاكتشاف.
    # والانتماءُ يُعلَن بـ`public_label` **إن كتبه صاحبُه** ولا يُشتقّ من
    # عنوان البحث: عنوانٌ حقيقيّ قد يُفصح عن فكرةٍ لم تُنشر.
    # ولا لقبَ جدولٍ هنا: `DISCOVERABLE` تُكتب مرّةً وتُستعمل حرفيًّا في
    # السياسة وفي العرض، فلا نسختانِ تفترقان.
    op.execute(
        f"CREATE VIEW {PUBLIC_VIEW} "
        "WITH (security_invoker = true, security_barrier = true) AS "
        "SELECT id, title, description, contributions, requirements, "
        "       specialization, collaboration_type, openings_count, "
        "       public_label, starts_at, ends_at, created_at "
        f"  FROM {OPPORTUNITIES} "
        f" WHERE {DISCOVERABLE}"
    )
    op.execute(f"GRANT SELECT ON {PUBLIC_VIEW} TO athera_app")
    # **ولا كتابةَ عبر العرض.** `ALTER DEFAULT PRIVILEGES` في 0003 تمنح
    # الكتابةَ على كلّ ما يُنشأ في المخطَّط — والعروضُ منه. وعرضُ
    # الاكتشاف إسقاطٌ للقراءة، لا بابٌ تُكتب الفرصُ منه بأعمدةٍ ناقصة.
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {PUBLIC_VIEW} FROM athera_app")


def downgrade() -> None:
    op.execute(f"DROP VIEW IF EXISTS {PUBLIC_VIEW}")
    for table in (APPLICATIONS, OPPORTUNITIES):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
    # والدالّةُ تُسقط بعد السياساتِ التي تقرؤها، لا قبلها.
    op.execute("DROP FUNCTION IF EXISTS app_manages_project(uuid)")
