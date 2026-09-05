"""ذكاءُ الباحث — أساسُ الموجة الثانية | Researcher intelligence foundation.

المرجع: `docs/wave2/researcher-intelligence-product-spec.md`.

## توسعةٌ محضة — وهذا قرارٌ لا صدفة

الإنتاج اليوم يشغّل خادمَ الموجة الأولى (v88)، وبين تطبيقِ هذا الترحيل
ونزولِ الموجة الثانية نافذةٌ يخدم فيها **الخادمُ القديم مخطَّطًا جديدًا**.
فكلُّ ما يُضاف هنا إمّا **جدولٌ جديد** لا يعرفه ذلك الخادم أصلًا، وإمّا
عمودٌ على `researcher_profiles` **قابلٌ للعدم أو ذو قيمةٍ افتراضية في
الخادم**. ولا قيدَ CHECK ولا UNIQUE ولا FK يُفرض على عمودٍ **يكتبه**
الخادمُ القديم.

وقيدُ `ck_researcher_profiles_orcid_status` استثناءٌ ظاهريّ لا حقيقيّ:
العمودُ يُنشأ في هذا الترحيل نفسه، والخادمُ القديم لا يعرفه ولا يُدرجه في
`INSERT` ولا `UPDATE` — فتُطبَّق القيمةُ الافتراضية `'unverified'` دائمًا،
وهي من المفردات المسموحة. فلا `INSERT` قديمٌ ولا `UPDATE` قديمٌ يقدر على
مخالفته. (والخادمُ القديم يكتب `orcid` وحده — `routers/profile.py:80`.)

فلا حاجة إلى فصلِ توسعةٍ عن تعاقدٍ كما لزم في 0028 ← 0029.

## والقيدُ في القاعدة لا في الموجّه

`(status = 'proposed') = (decided_by IS NULL)` مكتوبةٌ هنا لا هناك، لأنّ
موجّهًا يُكتب غدًا يعيد العطب، والقاعدةُ لا تُعاد كتابتها. وكذلك
**المعتمَدُ لا يُعدَّل**: مُشغِّلٌ يرفض تعديلَ استراتيجيّةٍ معتمَدة، ولا
يسمح إلّا بانتقالٍ واحد — إحالتِها إلى خَلَفٍ يذكرُه اسمُه.

Revision ID: 0030
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

TS = sa.DateTime(timezone=True)

NEW_TABLES = (
    "researcher_profile_candidates",
    "researcher_goals",
    "researcher_constraints",
    "research_strategies",
    "project_strategy_assessments",
)

# ── المفرداتُ المغلقة — مرآتها `athera_api/models/researcher_intelligence.py` ──

PROFILE_STATES = (
    "user_declared", "document_extracted", "confirmed",
    "externally_verified", "model_suggested",
)
CANDIDATE_STATUSES = ("proposed", "confirmed", "rejected", "needs_review")
CANDIDATE_SOURCE_TYPES = ("manual", "cv_upload", "orcid", "model")
EXTRACTION_METHODS = ("researcher", "deterministic", "model")
ORCID_STATUSES = ("unverified", "user_declared", "externally_verified")
GOAL_TYPES = (
    "publication", "promotion", "funding", "collaboration",
    "skill", "visibility", "thesis", "other",
)
GOAL_STATUSES = ("active", "achieved", "abandoned", "deferred")
GOAL_PRIORITIES = ("high", "medium", "low")
CONSTRAINT_TYPES = (
    "time", "publication_budget", "no_fee_preference", "language",
    "data_availability", "institutional", "deadline", "methodological",
    "geography_community", "collaboration",
)
STRATEGY_STATUSES = ("draft", "needs_review", "approved", "superseded")
ALIGNMENT_VERDICTS = ("aligns", "partially_aligns", "conflicts", "unknown")

#: الأعمدةُ المُضافة إلى `researcher_profiles` — كلُّها قابلةٌ للعدم عدا
#: `orcid_status` وله قيمةٌ افتراضية في الخادم.
PROFILE_COLUMNS = (
    "country",
    "preferred_research_languages",
    "preferred_working_language",
    "preferred_manuscript_language",
    "ai_response_language",
    "orcid_status",
    "orcid_verified_at",
    "orcid_source",
    "field_provenance",
)

IMMUTABILITY_FUNCTION = "research_strategy_approved_is_immutable"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _scoped_columns() -> tuple:
    """الأعمدةُ المشتركة — و`tenant_id` شرطُ تفعيل RLS (ADR-0002)."""
    return (
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", TS, server_default=sa.text("now()"), nullable=False),
    )


def _profile_column() -> sa.Column:
    return sa.Column(
        "profile_id", PgUUID(as_uuid=True),
        sa.ForeignKey("researcher_profiles.id", ondelete="CASCADE"), nullable=False,
    )


def upgrade() -> None:
    # ═══ ١) توسعةُ ملفّ الباحث القائم — ولا يُنشأ ملفٌّ ثانٍ (§1) ═══

    op.add_column("researcher_profiles", sa.Column("country", sa.String(64), nullable=True))

    # §8 — أربعةُ مفاهيمَ لغويّة لا مفهومٌ واحد، وأعمدةٌ أربعةٌ لا عمود.
    # ودمجُها كان يعني أنّ تبديلَ لغة الشاشة يبدّل لغةَ المخطوطة المستهدَفة،
    # فيغيّر هدفَ نشرٍ بضغطة زرّ.
    op.add_column("researcher_profiles",
                  sa.Column("preferred_research_languages", JSONB, nullable=True))
    op.add_column("researcher_profiles",
                  sa.Column("preferred_working_language", sa.String(8), nullable=True))
    op.add_column("researcher_profiles",
                  sa.Column("preferred_manuscript_language", sa.String(8), nullable=True))
    op.add_column("researcher_profiles",
                  sa.Column("ai_response_language", sa.String(8), nullable=True))

    # §6 — **والصيغةُ الصحيحة ليست توثيقًا.** الحالُ الافتراضية `unverified`،
    # ولا يرفعها إلى `externally_verified` إلّا مصدرٌ خارجيّ.
    op.add_column(
        "researcher_profiles",
        sa.Column("orcid_status", sa.String(24), nullable=False,
                  server_default="unverified"),
    )
    op.add_column("researcher_profiles",
                  sa.Column("orcid_verified_at", TS, nullable=True))
    op.add_column("researcher_profiles",
                  sa.Column("orcid_source", sa.String(32), nullable=True))
    op.add_column("researcher_profiles",
                  sa.Column("field_provenance", JSONB, nullable=True))

    # اسمٌ **مجرَّد** — واصطلاحُ التسمية يصير به `ck_researcher_profiles_orcid_status`
    # عند الإنشاء، ويُحذف بالاسم الكامل صراحةً في التنازل (درسُ 0017 و0028).
    op.create_check_constraint(
        "orcid_status", "researcher_profiles", _in("orcid_status", ORCID_STATUSES)
    )
    # توثيقٌ بلا وقتٍ ومصدرٍ ليس توثيقًا — وهو ادّعاءُ ملكيّةٍ بلا سند (§9).
    op.create_check_constraint(
        "external_verification_is_evidenced",
        "researcher_profiles",
        "orcid_status <> 'externally_verified' "
        "OR (orcid_verified_at IS NOT NULL AND orcid_source IS NOT NULL)",
    )

    # ═══ ٢) مرشَّحاتُ الملفّ — ولا يكتب مرشَّحٌ في الملفّ (§4) ═══

    op.create_table(
        "researcher_profile_candidates",
        *_scoped_columns(),
        _profile_column(),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("candidate_value", sa.Text, nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("provenance", sa.Text, nullable=True),
        sa.Column("extraction_method", sa.String(16), nullable=False),
        sa.Column("profile_state", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("decided_at", TS, nullable=True),
        sa.Column("decided_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("decision_reason", sa.Text, nullable=True),
        # **الحالاتُ الخمس، ولا تُدمج اثنتان** (§2).
        sa.CheckConstraint(_in("profile_state", PROFILE_STATES), name="profile_state"),
        sa.CheckConstraint(_in("status", CANDIDATE_STATUSES), name="status"),
        sa.CheckConstraint(_in("source_type", CANDIDATE_SOURCE_TYPES), name="source_type"),
        sa.CheckConstraint(_in("extraction_method", EXTRACTION_METHODS),
                           name="extraction_method"),
        # **قرارٌ بلا صاحبٍ ووقتٍ لا يكون.**
        sa.CheckConstraint("(status = 'proposed') = (decided_by IS NULL)",
                           name="decision_has_an_actor"),
        sa.CheckConstraint("(decided_by IS NULL) = (decided_at IS NULL)",
                           name="decision_has_a_time"),
        sa.CheckConstraint("(profile_state = 'confirmed') = (status = 'confirmed')",
                           name="confirmed_state_is_a_confirmed_decision"),
    )
    op.create_index("ix_researcher_profile_candidates_tenant_id",
                    "researcher_profile_candidates", ["tenant_id"])
    op.create_index("ix_researcher_profile_candidates_profile",
                    "researcher_profile_candidates", ["profile_id", "status"])

    # ═══ ٣) الأهداف — والهدفُ ليس وعدًا (§4) ═══

    op.create_table(
        "researcher_goals",
        *_scoped_columns(),
        _profile_column(),
        sa.Column("goal_type", sa.String(24), nullable=False),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("priority", sa.String(8), nullable=False, server_default="medium"),
        sa.Column("timeframe", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("researcher_confirmed", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.CheckConstraint(_in("goal_type", GOAL_TYPES), name="goal_type"),
        sa.CheckConstraint(_in("status", GOAL_STATUSES), name="status"),
        sa.CheckConstraint(_in("priority", GOAL_PRIORITIES), name="priority"),
        sa.CheckConstraint("length(btrim(target)) > 0", name="target_is_not_empty"),
    )
    op.create_index("ix_researcher_goals_tenant_id", "researcher_goals", ["tenant_id"])
    op.create_index("ix_researcher_goals_profile", "researcher_goals",
                    ["profile_id", "status"])

    # ═══ ٤) القيود — ولا يُخترع قيدٌ غائب (§4) ═══

    op.create_table(
        "researcher_constraints",
        *_scoped_columns(),
        _profile_column(),
        sa.Column("constraint_type", sa.String(32), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("researcher_confirmed", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.CheckConstraint(_in("constraint_type", CONSTRAINT_TYPES), name="constraint_type"),
        sa.CheckConstraint("length(btrim(value)) > 0", name="value_is_not_empty"),
    )
    op.create_index("ix_researcher_constraints_tenant_id",
                    "researcher_constraints", ["tenant_id"])
    op.create_index("ix_researcher_constraints_profile",
                    "researcher_constraints", ["profile_id", "constraint_type"])

    # ═══ ٥) الاستراتيجيّة — والمعتمَدُ لا يُعدَّل (§4) ═══

    op.create_table(
        "research_strategies",
        *_scoped_columns(),
        _profile_column(),
        sa.Column("strategy_version", sa.Integer, nullable=False),
        sa.Column("generated_at", TS, nullable=False),
        sa.Column("approved_at", TS, nullable=True),
        sa.Column("approved_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("rationale_ar", sa.Text, nullable=True),
        sa.Column("rationale_en", sa.Text, nullable=True),
        sa.Column("missing_information", JSONB, nullable=True),
        # اللقطاتُ تُخزَّن لأنّ الأهدافَ تتبدّل، وقرارٌ اتُّخذ على حالٍ سابقة
        # يُقرأ خطأً إن قيس بحالٍ لاحقة.
        sa.Column("profile_snapshot", JSONB, nullable=False),
        sa.Column("goals_snapshot", JSONB, nullable=False),
        sa.Column("constraints_snapshot", JSONB, nullable=False),
        sa.Column("superseded_by", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_strategies.id", ondelete="SET NULL"),
                  nullable=True),
        sa.UniqueConstraint("tenant_id", "profile_id", "strategy_version",
                            name="uq_research_strategies_version"),
        sa.CheckConstraint(_in("status", STRATEGY_STATUSES), name="status"),
        sa.CheckConstraint("strategy_version >= 1", name="version_starts_at_one"),
        sa.CheckConstraint("(approved_at IS NULL) = (approved_by IS NULL)",
                           name="approval_has_an_actor"),
        sa.CheckConstraint("status <> 'approved' OR approved_at IS NOT NULL",
                           name="approved_carries_its_time"),
        sa.CheckConstraint("approved_at IS NULL OR status IN ('approved', 'superseded')",
                           name="only_a_decided_strategy_carries_an_approval"),
        sa.CheckConstraint("(status = 'superseded') = (superseded_by IS NOT NULL)",
                           name="superseded_names_its_successor"),
    )
    op.create_index("ix_research_strategies_tenant_id", "research_strategies", ["tenant_id"])
    op.create_index("ix_research_strategies_profile", "research_strategies",
                    ["profile_id", "strategy_version"])

    # ═══ ٦) محاذاةُ المشاريع — ولا نسبة (§4) ═══

    op.create_table(
        "project_strategy_assessments",
        *_scoped_columns(),
        sa.Column("strategy_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_strategies.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("project_id", PgUUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("verdict", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("rationale_ar", sa.Text, nullable=True),
        sa.Column("rationale_en", sa.Text, nullable=True),
        sa.Column("missing_information", JSONB, nullable=True),
        sa.Column("assessed_at", TS, nullable=False),
        sa.UniqueConstraint("strategy_id", "project_id",
                            name="uq_project_strategy_assessments_strategy_id"),
        sa.CheckConstraint(_in("verdict", ALIGNMENT_VERDICTS), name="verdict"),
    )
    op.create_index("ix_project_strategy_assessments_tenant_id",
                    "project_strategy_assessments", ["tenant_id"])
    op.create_index("ix_project_strategy_assessments_project",
                    "project_strategy_assessments", ["project_id"])

    # ═══ ٧) **المعتمَدُ لا يُعدَّل** — مُشغِّلٌ لا تعليقٌ في مراجعة ═══
    #
    # القيدُ لا يكفي هنا: CHECK يرى الصفَّ الجديد ولا يرى القديم، فلا يعرف
    # أنّ صفًّا كان معتمَدًا. والمُشغِّل يرى الاثنين. والانتقالُ المسموح
    # واحدٌ: إحالةُ المعتمَدة إلى خَلَفٍ يذكره اسمُه — واللقطةُ والتعليلُ
    # والوقتُ والصاحبُ كما هي حرفًا بحرف.
    op.execute(f"""
        CREATE FUNCTION {IMMUTABILITY_FUNCTION}() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.status = 'superseded' THEN
                RAISE EXCEPTION
                    'a superseded research strategy is a historical record and '
                    'cannot be modified (version %) | '
                    'استراتيجيّةٌ مُحالةٌ سجلٌّ تاريخيّ لا يُعدَّل',
                    OLD.strategy_version;
            END IF;

            IF OLD.status = 'approved' THEN
                IF NEW.status = 'superseded'
                   AND NEW.superseded_by IS NOT NULL
                   AND NEW.strategy_version = OLD.strategy_version
                   AND NEW.profile_id = OLD.profile_id
                   AND NEW.generated_at = OLD.generated_at
                   AND NEW.approved_at IS NOT DISTINCT FROM OLD.approved_at
                   AND NEW.approved_by IS NOT DISTINCT FROM OLD.approved_by
                   AND NEW.rationale_ar IS NOT DISTINCT FROM OLD.rationale_ar
                   AND NEW.rationale_en IS NOT DISTINCT FROM OLD.rationale_en
                   AND NEW.missing_information IS NOT DISTINCT FROM OLD.missing_information
                   AND NEW.profile_snapshot = OLD.profile_snapshot
                   AND NEW.goals_snapshot = OLD.goals_snapshot
                   AND NEW.constraints_snapshot = OLD.constraints_snapshot
                THEN
                    RETURN NEW;
                END IF;

                RAISE EXCEPTION
                    'an approved research strategy is immutable (version %); '
                    'a change creates the next version and supersedes this one | '
                    'الاستراتيجيّةُ المعتمَدة لا تُعدَّل — التغييرُ يُنشئ إصدارًا تاليًا',
                    OLD.strategy_version;
            END IF;

            RETURN NEW;
        END;
        $$
    """)
    op.execute(
        "CREATE TRIGGER research_strategies_approved_is_immutable "
        "BEFORE UPDATE ON research_strategies "
        f"FOR EACH ROW EXECUTE FUNCTION {IMMUTABILITY_FUNCTION}()"
    )

    # ═══ ٨) العزل — ENABLE **و** FORCE، وسياسةٌ وصلاحيات (§10) ═══
    #
    # و`FORCE` ليست تزيّدًا على `ENABLE`: بدونها لا تسري السياسةُ على مالك
    # الجدول، وهو حسابُ الترحيلات نفسه.
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
    """التنازل يرفض ولا يمحو قرارًا نسبه الباحثُ إلى نفسه.

    ومرشَّحٌ قرّره صاحبُه، واستراتيجيّةٌ اعتمدها، وهدفٌ وقيدٌ أكّدهما —
    كلُّها أفعالٌ بشريّةٌ منسوبةٌ إلى وقتها. وإسقاطُ جداولها لإرضاء تنازلٍ
    إتلافٌ لتلك النسبة، فيُطلب الحسمُ أوّلًا — كما في 0016 و0020 و0022
    و0023 و0025 و0026.

    والمسوّداتُ وغيرُ المؤكَّد تُسقط بلا سؤال: لا قرارَ فيها يُتلف.
    """
    bind = op.get_bind()

    decided = bind.execute(sa.text(
        "SELECT count(*) FROM researcher_profile_candidates WHERE decided_by IS NOT NULL"
    )).scalar_one()
    if decided:
        raise RuntimeError(
            f"downgrade refused: {decided} profile candidate(s) carry a researcher's "
            "decision with its actor and time. Dropping the table would erase who "
            "decided what and when — the exact attribution this migration exists to "
            "keep. | "
            f"التنازل مرفوض: {decided} مرشَّحًا تحمل قرارَ صاحبها ووقتَه."
        )

    approved = bind.execute(sa.text(
        "SELECT count(*) FROM research_strategies "
        "WHERE status IN ('approved', 'superseded')"
    )).scalar_one()
    if approved:
        raise RuntimeError(
            f"downgrade refused: {approved} research strateg(ies) were approved by a "
            "researcher. Dropping them would erase an approval and the snapshot it "
            "was decided on. | "
            f"التنازل مرفوض: {approved} استراتيجيّةً اعتمدها باحثٌ بنفسه."
        )

    confirmed = bind.execute(sa.text(
        "SELECT (SELECT count(*) FROM researcher_goals WHERE researcher_confirmed) "
        "     + (SELECT count(*) FROM researcher_constraints WHERE researcher_confirmed)"
    )).scalar_one()
    if confirmed:
        raise RuntimeError(
            f"downgrade refused: {confirmed} goal(s)/constraint(s) were confirmed by "
            "the researcher. | "
            f"التنازل مرفوض: {confirmed} هدفًا أو قيدًا أكّدها الباحثُ بنفسه."
        )

    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.execute("DROP TRIGGER IF EXISTS research_strategies_approved_is_immutable "
               "ON research_strategies")
    op.execute(f"DROP FUNCTION IF EXISTS {IMMUTABILITY_FUNCTION}()")

    op.drop_index("ix_project_strategy_assessments_project",
                  table_name="project_strategy_assessments")
    op.drop_index("ix_project_strategy_assessments_tenant_id",
                  table_name="project_strategy_assessments")
    op.drop_table("project_strategy_assessments")

    op.drop_index("ix_research_strategies_profile", table_name="research_strategies")
    op.drop_index("ix_research_strategies_tenant_id", table_name="research_strategies")
    op.drop_table("research_strategies")

    op.drop_index("ix_researcher_constraints_profile", table_name="researcher_constraints")
    op.drop_index("ix_researcher_constraints_tenant_id", table_name="researcher_constraints")
    op.drop_table("researcher_constraints")

    op.drop_index("ix_researcher_goals_profile", table_name="researcher_goals")
    op.drop_index("ix_researcher_goals_tenant_id", table_name="researcher_goals")
    op.drop_table("researcher_goals")

    op.drop_index("ix_researcher_profile_candidates_profile",
                  table_name="researcher_profile_candidates")
    op.drop_index("ix_researcher_profile_candidates_tenant_id",
                  table_name="researcher_profile_candidates")
    op.drop_table("researcher_profile_candidates")

    # **قيدُ CHECK يُحذف بـSQL صريحٍ بالاسم الكامل** — واجهةُ alembic تعيد
    # تطبيق اصطلاح التسمية على اسمٍ طُبّق عليه أصلًا، فتطلب اسمًا لا وجود
    # له. وهو الدرسُ المكتوب في 0017 و0028.
    for constraint in ("orcid_status", "external_verification_is_evidenced"):
        op.execute("ALTER TABLE researcher_profiles DROP CONSTRAINT "
                   f"ck_researcher_profiles_{constraint}")

    for column in reversed(PROFILE_COLUMNS):
        op.drop_column("researcher_profiles", column)
