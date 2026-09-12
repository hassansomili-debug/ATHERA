"""ذاكرةُ حالِ البحث عبر الزمن | Brain V1: context snapshots and recommendations.

**العطبُ الذي يُصلَح: لا شيء يتذكّر.**

مسجَّلٌ منذ أن بُني الأساس، بندًا أوّلَ في
`docs/research-brain-foundation.md`: «التقييم يُحسب عند كل نداء، ولا يمكن
اليوم مقارنةُ تقييمِ اليوم بتقييم الأمس ولا معرفةُ متى ظهرت مخالفةٌ أو
زالت».

ونتيجتُه أنّ **كلّ قولٍ عن البحث جارٍ أبدًا**. تُعرض «شغّل تحليلًا» بعد أن
حُذفت مجموعةُ البيانات، و«المنهج كمّي» بعد أن صار كيفيًّا — لا لأنّ الحكم
خطأ، بل لأنّ لا أحدَ يعرف تحت أيّ حالٍ قيل. فالبصمةُ هي ما ينقص، وهذان
الجدولان يحملانها.

## ولمَ جدولان جديدان لا عمودٌ في جدولٍ قائم

فُتِّش أوّلًا (§34)، والجوابُ في رأس `models/research_brain.py` جدولًا:
`audit_events` سلسلةٌ ملحقةٌ لا تُستعلَم هكذا، و`project_decisions` قرارُ
**إنسان** — والتوصيةُ اقتراحٌ لم يقرّره أحد، ودمجُهما يجعل قولَ آلةٍ قرارًا
موقَّعًا.

## توسعةٌ محضة

لا عمودَ يُحذف، ولا جدولَ يُغيَّر، ولا صفَّ يُكتب. والخادمُ الذي لا يعرف
هذين الجدولين يبقى صحيحًا بعد الصعود — فالنشرُ لا يشترط ترتيبًا.

**ولا يُنفَّذ هذا الترحيل في الإنتاج في هذه الموجة.** رأسُ الإنتاج `0032`،
ويبقى.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

NEW_TABLES = ("research_context_snapshots", "research_recommendations")


def upgrade() -> None:
    op.create_table(
        "research_context_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("fingerprint_schema", sa.String(64), nullable=False),
        sa.Column("entity_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relationship_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("contradiction_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("read_note_keys", postgresql.JSONB(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        # **بصمةٌ واحدة لكلّ بحثٍ مرّةً واحدة** — وإلا صار الجدولُ سجلَّ
        # زياراتٍ لا تاريخَ بحث.
        sa.UniqueConstraint("project_id", "context_fingerprint",
                            name="uq_research_context_snapshots_project_id"),
        sa.CheckConstraint("length(context_fingerprint) = 64",
                           name="ck_context_fingerprint_is_sha256"),
    )
    op.create_index("ix_research_context_snapshots_tenant_id",
                    "research_context_snapshots", ["tenant_id"])
    op.create_index("ix_research_context_snapshots_project_seen",
                    "research_context_snapshots", ["project_id", "last_seen_at"])

    op.create_table(
        "research_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_projects.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("research_context_snapshots.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("context_fingerprint", sa.String(64), nullable=False),
        sa.Column("action_key", sa.String(64), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="proposed"),
        sa.Column("title_ar", sa.Text(), nullable=False),
        sa.Column("title_en", sa.Text(), nullable=True),
        sa.Column("reason_ar", sa.Text(), nullable=False),
        sa.Column("reason_en", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=True),
        sa.Column("limitations_ar", sa.Text(), nullable=True),
        sa.Column("generated_by", sa.String(16), nullable=False, server_default="rule"),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'superseded')",
            name="ck_status_is_known"),
        sa.CheckConstraint(
            "generated_by IN ('rule', 'model', 'hybrid')",
            name="ck_generated_by_is_known"),
        # **مخرَجُ نموذجٍ يُسمّى مزوّدَه، والقاعدةُ الحتمية لا مزوّدَ لها.**
        sa.CheckConstraint(
            "(generated_by = 'rule' AND provider IS NULL) OR generated_by <> 'rule'",
            name="ck_rule_has_no_provider"),
        sa.CheckConstraint(
            "length(context_fingerprint) = 64",
            name="ck_fingerprint_is_sha256"),
        sa.UniqueConstraint("project_id", "context_fingerprint", "action_key",
                            name="uq_research_recommendations_project_id"),
    )
    op.create_index("ix_research_recommendations_tenant_id",
                    "research_recommendations", ["tenant_id"])
    op.create_index("ix_research_recommendations_project_status",
                    "research_recommendations", ["project_id", "status"])

    # ═════════ العزل — سياسةٌ لكل جدولٍ جديد (ADR-0002) ═════════
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
    """التراجعُ يُسقط الجدولين — **ولا يُتلف شيئًا سواهما**.

    وهذا ممكنٌ هنا وحده لأنّ ما فيهما **مشتقٌّ كلُّه**: البصمةُ تُحسب من
    حال البحث متى شئت، والتوصيةُ تُولَّد من القواعد على تلك الحال. فلا
    معرفةَ أصليّةٌ تضيع، ولا قرارَ إنسانٍ يُمحى — والقرارُ في
    `project_decisions`، ولم يمسّه هذا الترحيل.

    ولو حمل الجدولان قبولَ باحثٍ لتوصية لَما جاز هذا: كان يُطلب الحسمُ
    أوّلًا كما في 0016 و0020 و0025. **و`decided_by` يبقى فارغًا في V1**
    لأنّ مسارَ القبول لم يُفتح (§85).
    """
    for table in NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("research_recommendations")
    op.drop_table("research_context_snapshots")
