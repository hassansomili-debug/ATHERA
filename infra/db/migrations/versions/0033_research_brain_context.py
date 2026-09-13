"""ذاكرةُ حالِ البحث عبر الزمن | Brain V1: the context snapshot.

**العطبُ الذي يُصلَح: لا شيء يتذكّر.**

مسجَّلٌ منذ أن بُني الأساس، بندًا أوّلَ في
`docs/research-brain-foundation.md`: «التقييم يُحسب عند كل نداء، ولا يمكن
اليوم مقارنةُ تقييمِ اليوم بتقييم الأمس ولا معرفةُ متى ظهرت مخالفةٌ أو
زالت».

فلا تعرف المنصّةُ **متى** تغيّر حالُ بحثٍ تغيّرًا ذا معنى، ولا كم لبث على
حاله. والبصمةُ هي ما ينقص، وهذا الجدولُ يحملها.

## ولمَ جدولٌ جديد لا عمودٌ في جدولٍ قائم

فُتِّش أوّلًا (§34)، والجوابُ في رأس `models/research_brain.py` جدولًا:
`audit_events` سلسلةٌ ملحقةٌ لا تُستعلَم هكذا، و`project_decisions` قرارُ
إنسانٍ لا حالُ بحثٍ عبر الزمن.

## وجدولُ التوصيات أُسقط قبل الدمج

كان هذا الترحيلُ يُنشئ جدولًا ثانيًا — `research_recommendations` — فأُسقط
في مراجعةٍ معمارية. والسببُ أنّ الخطوةَ المقترحة تُحسب من الحال الراهنة في
كلّ طلب (`journey.decide()` دالّةٌ خالصة)، فكان الجدولُ **يُكتب ولا يُقرأ
إلا على نفسه**، ويحمل مفاهيمَ لا مسارَ لها بعد: `accepted` و`rejected`
و`decided_by` و`provider`.

وحفظُ «أوصت المنصّةُ بكذا تحت البصمة F1» مراقبةٌ وتدقيق، تُبنى حين يُبنى
ما يستهلكها.

## توسعةٌ محضة

لا عمودَ يُحذف، ولا جدولَ يُغيَّر، ولا صفَّ يُكتب. والخادمُ الذي لا يعرف
هذا الجدولَ يبقى صحيحًا بعد الصعود — فالنشرُ لا يشترط ترتيبًا.

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

TABLE = "research_context_snapshots"


def upgrade() -> None:
    op.create_table(
        TABLE,
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
        # **والاسمُ قصيرٌ عمدًا.** اصطلاحُ `ck_%(table_name)s_%(constraint_name)s`
        # يُطبَّق على ما يُكتب هنا، فاسمٌ مكتوبٌ كاملًا يُبادَأ مرّتين
        # ويتجاوز حدَّ ثلاثةٍ وستين محرفًا **فيُقصّ صامتًا** — وهو العطبُ
        # عينه الذي شرحه 0032، ووقع في أول صياغةٍ لهذا الترحيل.
        sa.CheckConstraint("length(context_fingerprint) = 64",
                           name="ck_context_fingerprint_is_sha256"),
    )
    op.create_index("ix_research_context_snapshots_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_research_context_snapshots_project_seen",
                    TABLE, ["project_id", "last_seen_at"])

    # ═════════ العزل — سياسةٌ للجدول الجديد (ADR-0002) ═════════
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {TABLE}_tenant_isolation ON {TABLE} "
        "USING (tenant_id = app_current_tenant()) "
        "WITH CHECK (tenant_id = app_current_tenant())"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO athera_app")


def downgrade() -> None:
    """التراجعُ يُسقط الجدول — **ولا يُتلف شيئًا سواه**.

    وهذا ممكنٌ هنا وحده لأنّ ما فيه **مشتقٌّ كلُّه**: البصمةُ تُحسب من حال
    البحث متى شئت. فلا معرفةَ أصليّةٌ تضيع، ولا قرارَ إنسانٍ يُمحى —
    والقرارُ في `project_decisions`، ولم يمسّه هذا الترحيل.

    ولو حمل الجدولُ قبولَ باحثٍ لشيء لَما جاز هذا: كان يُطلب الحسمُ أوّلًا
    كما في 0016 و0020 و0025. والمفقودُ بالتراجع **تاريخُ** البصمات وحدَه —
    ومتى تغيّر البحثُ لا يُستعاد بإعادة الحساب.
    """
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE}")
    op.drop_table(TABLE)
