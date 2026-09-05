"""فرق البحث ٢ — التعاون وسلامة التأليف | Research teams V2 (PUBRIVA).

**العطب الذي أوجد هذا الترحيل: موافقةُ التأليف كانت تُسجَّل عن الغير.**

المسار `POST /projects/{id}/members/{member_id}/consent` كان يقرأ العضو
بمعرِّفه، ويكتب `consent_recorded_at`، **ولا يسأل مَن الطالب**. فأيُّ
مصادَقٍ في المستأجر كان يسجّل موافقةَ أيِّ مؤلف. وهذا ليس تسهيلًا: هو
تزويرُ تأليف. ورئيسُ فريقٍ يوافق نيابةً عن مؤلفٍ مشارك يُنتج ورقةً تحمل
اسمَ من لم يوافق.

## والإصلاح في القاعدة لا في الموجّه وحده

الموجّه يُصلَح، لكنّ موجّهًا آخر يُكتب غدًا يعيد العطب. فالربط مكتوبٌ
قيدًا:

    ck_project_members_self_consent_is_the_member
        consent_method <> 'self' OR consent_recorded_by = user_id

فموافقةٌ «ذاتية» سجّلها غيرُ صاحبها **ترفضها القاعدة**، ولو أمرها الكود.

## وثلاث طرائق لا واحدة

  `self`               صاحبُها سجّلها بحسابه المصادَق — وهي الأصل.
  `administrative`     مسارٌ منفصلٌ معلَن، يلزمه سندٌ مكتوب ويُدقَّق.
  `legacy_unverified`  ما سُجِّل قبل هذا الترحيل تحت المسار المعطوب.

والثالثة **لا يكتبها التطبيق أبدًا**. هي وسمُ ما لا نعرف مَن سجّله، ولا
يجوز أن يُرقَّى صامتًا إلى «ذاتية»: ترقيتُه تعني أن نقول عن موافقةٍ
مجهولةِ المصدر إنّ صاحبها منحها — وهي الكذبة نفسها التي نُصلحها هنا.

## والدعوة تربط حسابًا لا اسمًا

عضوٌ باسمٍ معروض وحده لا يتعاون: لا يدخل، ولا يوافق، ولا يُنسب إليه فعل.
فالدعوة تحمل رمزًا **مجزَّأً لا خامًا**، ومهلةً، وحالًا، ومَن قبِلها. وربطُ
`project_members.user_id` يقع بحساب **القابل المصادَق** — لا بمطابقة اسم.

## وأربعة لا تُخلط

الدورُ ليس صلاحية، والصلاحيةُ ليست مساهمةَ CRediT، ومساهمةُ CRediT ليست
تأليفًا. فالصلاحيات صفوفٌ مستقلّة عن `role`، وتغييرُ الدور لا يغيّرها
بأثرٍ جانبي؛ و`is_author` إعلانٌ صريح لا ينشأ من وجود صفِّ عضوية.

Revision ID: 0028
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0028"
# المُكامِل يعيد توجيهها إلى "0027" بعد نزول المسارين B و C — وهذا متوقَّع.
down_revision = "0027"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = (
    "project_invitations",
    "project_member_permissions",
    "project_member_events",
)

# ── المفردات المغلقة — مرآتها في `athera_api/services/team.py` ──

INVITATION_STATES = ("invited", "accepted", "declined", "expired", "revoked")

MEMBER_ACCESS_STATES = ("invited", "active", "suspended", "removed")

CONSENT_STATES = ("not_requested", "pending", "granted", "declined")

CONSENT_METHODS = ("self", "administrative", "legacy_unverified")

PROJECT_PERMISSIONS = (
    "view_project",
    "edit_research_content",
    "manage_sources",
    "manage_data",
    "manage_tasks",
    "review_scientific_candidates",
    "approve_scientific_candidates",
    "manage_team",
    "manage_submission",
)

MEMBER_EVENT_KINDS = (
    "invited", "accepted", "declined", "expired", "revoked",
    "role_changed", "permissions_changed", "credit_changed",
    "authorship_declared", "authorship_withdrawn",
    "consent_requested", "consent_granted", "consent_declined",
    "access_suspended", "access_restored", "removed", "left",
)

# أفعالُ إنشاء البحث في سجلّ التدقيق — منها يُشتقّ مالكُ بحثٍ لا ملفَّ له.
PROJECT_CREATED_ACTIONS = (
    "portfolio.project_created",
    "workspace.project_created",
    "thesis.project_created",
    "synthesis.project_created",
)


def _in(column: str, values) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _scoped_columns() -> tuple:
    return (
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
    )


def upgrade() -> None:
    # ═════════ ١. العضو: حالُ وصوله، وموافقتُه، وتأليفُه ═════════
    #
    # الأعمدة تُضاف أوّلًا، ثمّ تُملأ، ثمّ تُشدّ القيود عليها — فترحيلٌ يشدّ
    # القيد قبل أن يملأ يسقط على أوّل صفٍّ قائم.
    op.add_column("project_members",
                  sa.Column("invited_email", sa.String(320), nullable=True))
    op.add_column("project_members",
                  sa.Column("access_state", sa.String(16), nullable=False,
                            server_default="active"))
    op.add_column("project_members",
                  sa.Column("consent_state", sa.String(16), nullable=False,
                            server_default="not_requested"))
    op.add_column("project_members",
                  sa.Column("consent_recorded_by", PgUUID(as_uuid=True),
                            sa.ForeignKey("users.id", ondelete="RESTRICT"),
                            nullable=True))
    op.add_column("project_members",
                  sa.Column("consent_method", sa.String(24), nullable=True))
    op.add_column("project_members",
                  sa.Column("consent_evidence_ar", sa.Text, nullable=True))
    # **العضويةُ ليست تأليفًا.** إعلانٌ صريح، ولا يُشتقّ من وجود صفّ عضوية.
    op.add_column("project_members",
                  sa.Column("is_author", sa.Boolean, nullable=False,
                            server_default=sa.text("false")))
    op.add_column("project_members",
                  sa.Column("author_position", sa.Integer, nullable=True))
    op.add_column("project_members",
                  sa.Column("suspended_at", TS, nullable=True))
    op.add_column("project_members",
                  sa.Column("removed_at", TS, nullable=True))

    # ما سُجِّل قبل اليوم مجهولُ الصاحب — يُسمّى بذلك ولا يُرقَّى.
    op.execute(
        "UPDATE project_members SET consent_state = 'granted', "
        "consent_method = 'legacy_unverified' "
        "WHERE consent_recorded_at IS NOT NULL"
    )

    # **القيدُ المركّب يملكه 0026، ولا يُنشأ مرّتين.**
    #
    # احتاجه المساران معًا للغرض نفسه — مرجعًا لمفتاحٍ أجنبيٍّ مركّب يمنع
    # إسنادَ شيءٍ في بحثٍ إلى عضوٍ في بحثٍ آخر. وكلٌّ منهما كان معزولًا على
    # 0025 فلم يرَ الآخر، فأنشأه الاثنان بالاسم نفسه والأعمدة نفسها. ولمّا
    # صارت السلسلة 0026 ← 0027 ← 0028 سقط الترحيل الثاني:
    #
    #     DuplicateTable: relation "uq_project_members_project_scoped"
    #                     already exists
    #
    # فيُترك لصاحبه الأسبق. وهذا الملفّ يبني عليه ولا يعيده.
    # حسابٌ واحدٌ لا يكون عضوين في بحثٍ واحد — وإلّا انقسمت صلاحياته وموافقته.
    op.execute(
        "CREATE UNIQUE INDEX uq_project_members_project_account "
        "ON project_members (project_id, user_id) WHERE user_id IS NOT NULL"
    )

    for expression, name in (
        (_in("access_state", MEMBER_ACCESS_STATES), "access_state"),
        (_in("consent_state", CONSENT_STATES), "consent_state"),
        (f"consent_method IS NULL OR {_in('consent_method', CONSENT_METHODS)}",
         "consent_method"),
        # **الموافقةُ لها وقتٌ وطريقة — والقيدُ مؤجَّلٌ إلى 0029.**
        #
        # هذا ترحيلُ **توسعة**: يعمل تحته الخادمُ القديم حتى تُنشر الموجة.
        # والخادمُ القديم يكتب `consent_recorded_at` وحده ولا يعرف
        # `consent_method` (`routers/team.py:156`)، فقيدٌ يقرن العمودين
        # هنا يُسقط كلَّ تسجيل موافقةٍ بـ٥٠٠ في تلك النافذة.
        #
        # فيُنقل إلى `0029_research_teams_consent_contract` — يُفرض بعد أن
        # يصير الكاتبُ هو الموجةَ الأولى، وبعد أن تُرمَّم صفوفُ النافذة.
        # ══ الحارس البنيويّ ضدّ تزوير التأليف ══
        #
        # لا يُصلَح هذا في الموجّه وحده: موجّهٌ ثانٍ يُكتب غدًا يعيد العطب.
        # فمَن كتب «ذاتية» وجب أن يكون هو العضو نفسه — أو يرفض المحرّك.
        ("consent_method IS DISTINCT FROM 'self' OR "
         "(consent_recorded_by IS NOT NULL AND consent_recorded_by = user_id)",
         "self_consent_is_the_member"),
        # والمسارُ الإداري مسموحٌ **معلنًا وموثَّقًا**، لا صامتًا.
        ("consent_method IS DISTINCT FROM 'administrative' OR "
         "(consent_recorded_by IS NOT NULL AND consent_evidence_ar IS NOT NULL "
         "AND length(btrim(consent_evidence_ar)) > 0)",
         "proxy_consent_is_evidenced"),
        # ترتيبُ مؤلفٍ لمن ليس مؤلفًا لا معنى له.
        ("author_position IS NULL OR is_author", "position_needs_authorship"),
        ("(access_state = 'suspended') = (suspended_at IS NOT NULL)",
         "suspension_has_a_time"),
        ("(access_state = 'removed') = (removed_at IS NOT NULL)",
         "removal_has_a_time"),
    ):
        op.create_check_constraint(name, "project_members", expression)

    # ═════════ ٢. الدعوات — رمزٌ مجزَّأ، ومهلة، وحسابٌ قابل ═════════
    op.create_table(
        "project_invitations",
        *_scoped_columns(),
        sa.Column("invited_email", sa.String(320), nullable=False),
        sa.Column("invited_display_name", sa.String(255), nullable=False),
        # الحسابُ المرشَّح إن كان البريدُ معروفًا — **ترشيحٌ لا ربط**.
        sa.Column("invited_user_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invited_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposed_role", sa.String(32), nullable=False),
        sa.Column("proposed_permissions", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        # **الرمزُ الخام لا يُخزَّن أبدًا.** من قرأ الجدول لا يستطيع القبول
        # نيابةً عن أحد، ومن سرّب الجدول لا يسرّب مفتاحًا.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="invited"),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("responded_at", TS, nullable=True),
        sa.Column("accepted_user_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("member_id", PgUUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(_in("state", INVITATION_STATES), name="state"),
        sa.CheckConstraint("length(token_hash) = 64", name="token_is_hashed"),
        sa.CheckConstraint("length(btrim(invited_email)) > 0", name="email_is_not_blank"),
        # القبولُ يُسمّي الحساب الذي قبِل — ولا قبولَ بلا حساب.
        sa.CheckConstraint("(state = 'accepted') = (accepted_user_id IS NOT NULL)",
                           name="acceptance_names_its_account"),
        sa.CheckConstraint("(state = 'invited') = (responded_at IS NULL)",
                           name="settlement_has_a_time"),
        sa.UniqueConstraint("token_hash", name="uq_project_invitations_token"),
        sa.UniqueConstraint("id", "project_id", name="uq_project_invitations_scoped"),
        sa.ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="SET NULL", name="fk_project_invitations_member"),
    )
    # دعوةٌ حيّةٌ واحدةٌ لبريدٍ في بحث — وإلّا صار لصاحبها رمزان يعملان.
    op.execute(
        "CREATE UNIQUE INDEX uq_project_invitations_live "
        "ON project_invitations (project_id, lower(invited_email)) "
        "WHERE state = 'invited'"
    )
    op.create_index("ix_project_invitations_project", "project_invitations",
                    ["tenant_id", "project_id", "state"])
    op.create_index("ix_project_invitations_recipient", "project_invitations",
                    ["tenant_id", "invited_email", "state"])

    # ═════════ ٣. الصلاحيات — صفوفٌ مستقلّة عن الدور ═════════
    #
    # ولو اشتُقّت من `role` لصار تغييرُ الدور تغييرًا صامتًا للصلاحيات،
    # ولاستحال أن يكون لمحلّلٍ إحصائيّ حقُّ البيانات بلا إدارةِ المشروع.
    op.create_table(
        "project_member_permissions",
        *_scoped_columns(),
        sa.Column("member_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("permission_key", sa.String(32), nullable=False),
        sa.Column("granted_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("granted_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("permission_key", PROJECT_PERMISSIONS),
                           name="permission_key"),
        sa.UniqueConstraint("member_id", "permission_key",
                            name="uq_project_member_permissions_grant"),
        # **الحارس البنيويّ ضدّ التسرّب بين بحثين في المستأجر الواحد.**
        # منحةٌ في بحثٍ لا يمكن أن تشير إلى عضوٍ في بحثٍ آخر — لا لأن الخدمة
        # تصفّي، بل لأن القاعدة ترفض.
        sa.ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="CASCADE", name="fk_project_member_permissions_member"),
    )
    op.create_index("ix_project_member_permissions_member",
                    "project_member_permissions",
                    ["tenant_id", "project_id", "member_id"])

    # ═════════ ٤. سجلّ دورة حياة العضو — يُضاف ولا يُعدَّل ═════════
    op.create_table(
        "project_member_events",
        *_scoped_columns(),
        sa.Column("member_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("invitation_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("event_kind", sa.String(24), nullable=False),
        sa.Column("actor_user_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subject_user_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("state_before", JSONB, nullable=True),
        sa.Column("state_after", JSONB, nullable=True),
        sa.Column("note_ar", sa.Text, nullable=True),
        sa.Column("occurred_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(_in("event_kind", MEMBER_EVENT_KINDS), name="event_kind"),
        sa.CheckConstraint("member_id IS NOT NULL OR invitation_id IS NOT NULL",
                           name="event_has_a_subject"),
        sa.ForeignKeyConstraint(
            ["member_id", "project_id"],
            ["project_members.id", "project_members.project_id"],
            ondelete="CASCADE", name="fk_project_member_events_member"),
        sa.ForeignKeyConstraint(
            ["invitation_id", "project_id"],
            ["project_invitations.id", "project_invitations.project_id"],
            ondelete="CASCADE", name="fk_project_member_events_invitation"),
    )
    op.create_index("ix_project_member_events_project", "project_member_events",
                    ["tenant_id", "project_id", "occurred_at"])
    op.create_index("ix_project_member_events_member", "project_member_events",
                    ["tenant_id", "member_id", "occurred_at"])

    # ═════════ ٥. موافقةُ اتفاق التأليف تُنسب إلى مَن سجّلها ═════════
    #
    # العطبُ نفسه في `services/thesis/rights.py`: الموافقة تُكتب ولا يُسأل
    # مَن الطالب. والأعمدة هنا تجعل النسبة **مخزَّنة**، فلا يبقى في السجلّ
    # اتفاقٌ «مُوافَقٌ عليه» بلا صاحبٍ للموافقة.
    op.add_column("authorship_agreements",
                  sa.Column("consent_recorded_by", PgUUID(as_uuid=True),
                            sa.ForeignKey("users.id", ondelete="RESTRICT"),
                            nullable=True))
    op.add_column("authorship_agreements",
                  sa.Column("consent_method", sa.String(24), nullable=True))
    op.add_column("authorship_agreements",
                  sa.Column("consent_evidence_ar", sa.Text, nullable=True))
    op.execute(
        "UPDATE authorship_agreements SET consent_method = 'legacy_unverified' "
        "WHERE consent_recorded_at IS NOT NULL"
    )
    for expression, name in (
        (f"consent_method IS NULL OR {_in('consent_method', CONSENT_METHODS)}",
         "consent_method"),
        # وقيدُ «للموافقة طريقة» مؤجَّلٌ إلى 0029 للسبب نفسه:
        # `services/thesis/rights.py:190` يكتب الوقت وحده.
        ("consent_method IS DISTINCT FROM 'administrative' OR "
         "(consent_recorded_by IS NOT NULL AND consent_evidence_ar IS NOT NULL "
         "AND length(btrim(consent_evidence_ar)) > 0)",
         "proxy_consent_is_evidenced"),
    ):
        op.create_check_constraint(name, "authorship_agreements", expression)

    # ═════════ ٦. مالكُ البحث يصير عضوًا بصلاحياته ═════════
    #
    # **بلا هذا يفقد كلُّ باحثٍ قائمٍ بحثَه.** فالصلاحيات تُقرأ من صفوف
    # العضوية، ولا عضوية لأحدٍ اليوم. والمالك يُشتقّ من مصدرين موثوقين لا
    # من اسمٍ معروض: ملفُّ الباحث الذي يشير إليه البحث، أو فاعلُ حدث
    # إنشائه في سجلّ التدقيق — وهو سجلٌّ لا يُعدَّل ولا يُحذف منه.
    op.execute(
        """
        INSERT INTO project_members (
            id, tenant_id, project_id, user_id, display_name, role,
            access_state, consent_state, is_author, created_at, updated_at)
        SELECT gen_random_uuid(), p.tenant_id, p.id, o.user_id,
               COALESCE(NULLIF(btrim(u.full_name_ar), ''), u.email),
               'principal_investigator', 'active', 'not_requested', false,
               now(), now()
        FROM research_projects p
        JOIN LATERAL (
            SELECT c.user_id FROM (
                SELECT rp.user_id, 1 AS priority
                  FROM researcher_profiles rp
                 WHERE rp.id = p.profile_id
                UNION ALL
                SELECT ae.actor_user_id, 2
                  FROM audit_events ae
                 WHERE ae.object_type = 'research_project'
                   AND ae.object_id = p.id
                   AND ae.action IN (%(actions)s)
                   AND ae.actor_user_id IS NOT NULL
            ) c
            WHERE c.user_id IS NOT NULL
            ORDER BY c.priority
            LIMIT 1
        ) o ON TRUE
        JOIN users u ON u.id = o.user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM project_members m
             WHERE m.project_id = p.id AND m.user_id = o.user_id)
        """
        % {"actions": ", ".join(f"'{action}'" for action in PROJECT_CREATED_ACTIONS)}
    )
    op.execute(
        """
        INSERT INTO project_member_permissions (
            id, tenant_id, project_id, member_id, permission_key,
            granted_by, granted_at, created_at, updated_at)
        SELECT gen_random_uuid(), m.tenant_id, m.project_id, m.id, k.key,
               m.user_id, now(), now(), now()
        FROM project_members m
        CROSS JOIN (VALUES %(keys)s) AS k(key)
        WHERE m.role = 'principal_investigator'
          AND m.user_id IS NOT NULL
          AND m.access_state = 'active'
          AND NOT EXISTS (
              SELECT 1 FROM project_member_permissions g
               WHERE g.member_id = m.id AND g.permission_key = k.key)
        """
        % {"keys": ", ".join(f"('{key}')" for key in PROJECT_PERMISSIONS)}
    )

    # ═════════ ٧. العزل — سياسةٌ لكل جدولٍ جديد ═════════
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            "USING (tenant_id = app_current_tenant()) "
            "WITH CHECK (tenant_id = app_current_tenant())"
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO athera_app")


def downgrade() -> None:
    """التنازل يرفض ولا يمحو موافقةَ مؤلفٍ ولا قبولَ دعوة.

    موافقةٌ سجّلها صاحبها بحسابه إقرارٌ بمسؤوليةٍ علمية، وقبولُ دعوةٍ
    ارتباطُ حسابٍ ببحث. وإسقاطُ الأعمدة عليهما يمحو مَن وافق ومتى — فيعود
    السجلّ إلى ما كان: «مُوافَقٌ عليه» بلا صاحب، وهو العطب نفسه. فيُطلب
    الحسم أوّلًا، كما في 0016 و0020 و0025.

    ولا يُحذف عضوٌ أنشأه الصعود: الحذف إتلاف، وإعادةُ الصعود تتجاوز ما هو
    قائم بـ`NOT EXISTS` — فلا يُنتج التكرارَ ما يبرّر الإتلاف.
    """
    bind = op.get_bind()

    consents = bind.execute(sa.text(
        "SELECT count(*) FROM project_members "
        "WHERE consent_method IN ('self', 'administrative')"
    )).scalar_one()
    if consents:
        raise RuntimeError(
            f"downgrade refused: {consents} author consent(s) carry a recorded "
            "identity. Dropping these columns would erase who consented and how, "
            "returning the record to the unattributed state this migration fixed. | "
            f"التنازل مرفوض: {consents} موافقةَ تأليفٍ تحمل هويّةَ صاحبها."
        )

    accepted = bind.execute(sa.text(
        "SELECT count(*) FROM project_invitations WHERE state = 'accepted'"
    )).scalar_one()
    if accepted:
        raise RuntimeError(
            f"downgrade refused: {accepted} invitation(s) were accepted by a real "
            "account. Dropping the table would erase the binding between a person "
            "and the project they joined. | "
            f"التنازل مرفوض: {accepted} دعوةً قبِلها حسابٌ حقيقي."
        )

    # **قيدُ check يُحذف بـSQL صريح** — واجهةُ alembic تعيد تطبيق اصطلاح
    # التسمية على اسمٍ طُبّق عليه أصلًا، فتطلب اسمًا لا وجود له (0017).
    # و«consent_has_a_method» ليست من صنع هذا الترحيل بعد الفصل — تُنشئها
    # 0029 وتحذفها 0029. وحذفُ ما لم يُنشأ هنا يُسقط التنازل.
    for constraint in ("consent_method", "proxy_consent_is_evidenced"):
        op.execute("ALTER TABLE authorship_agreements DROP CONSTRAINT "
                   f"ck_authorship_agreements_{constraint}")
    op.drop_column("authorship_agreements", "consent_evidence_ar")
    op.drop_column("authorship_agreements", "consent_method")
    op.drop_column("authorship_agreements", "consent_recorded_by")

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index("ix_project_member_events_member",
                  table_name="project_member_events")
    op.drop_index("ix_project_member_events_project",
                  table_name="project_member_events")
    op.drop_table("project_member_events")

    op.drop_index("ix_project_member_permissions_member",
                  table_name="project_member_permissions")
    op.drop_table("project_member_permissions")

    op.drop_index("ix_project_invitations_recipient", table_name="project_invitations")
    op.drop_index("ix_project_invitations_project", table_name="project_invitations")
    op.execute("DROP INDEX IF EXISTS uq_project_invitations_live")
    op.drop_table("project_invitations")

    for constraint in ("access_state", "consent_state", "consent_method",
                       "self_consent_is_the_member", "proxy_consent_is_evidenced",
                       "position_needs_authorship", "suspension_has_a_time",
                       "removal_has_a_time"):
        op.execute("ALTER TABLE project_members DROP CONSTRAINT "
                   f"ck_project_members_{constraint}")
    op.execute("DROP INDEX IF EXISTS uq_project_members_project_account")
    # ولا يُحذف هنا ما لم يُنشأ هنا: 0026 أنشأه، و0026 يحذفه. وحذفُه من
    # هذا الموضع يقطع مفاتيح 0026 الأجنبية وهي قائمةٌ تحته.

    for column in ("removed_at", "suspended_at", "author_position", "is_author",
                   "consent_evidence_ar", "consent_method", "consent_recorded_by",
                   "consent_state", "access_state", "invited_email"):
        op.drop_column("project_members", column)
