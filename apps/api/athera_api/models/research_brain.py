"""ما يُحفظ من العقل البحثيّ — لقطةٌ وتوصية | Brain V1 persistence (Wave 2-A §35).

**جدولان، ولكلٍّ منهما سؤالٌ لا يجيب عنه جدولٌ قائم.**

وقد فُتِّش عن بديلٍ قبل أن يُكتب ترحيل (§34):

| البديلُ المرشَّح | ولمَ لا يكفي |
|---|---|
| `audit_events` | سلسلةُ تجزئةٍ ملحقةٌ لا تُستعلَم بالبحث وبالبصمة، وتحميلُها هذا يُفسد ما هي له |
| `project_decisions` | قرارُ إنسان؛ والتوصيةُ **اقتراحٌ لم يقرّره أحد**، ودمجُهما يجعل قولَ آلةٍ قرارًا موقَّعًا |
| `researcher_memories` | معرفةٌ موثقةٌ عن البحث؛ والتوصيةُ ليست معرفةً عنه (§64) |
| `guardrail_checks` | فحصُ مخرَجِ نموذج، لا حالُ بحثٍ عبر الزمن |
| `research_intelligence_briefs` | موجزُ رادارٍ خارجيّ عن مجالٍ، لا لقطةُ مشروعٍ بعينه |

**والحاجةُ مسجَّلةٌ قبل هذا الترحيل** في `docs/research-brain-foundation.md`
بندًا أوّلَ: «التقييم يُحسب عند كل نداء، ولا يمكن اليوم مقارنةُ تقييمِ اليوم
بتقييم الأمس ولا معرفةُ متى ظهرت مخالفةٌ أو زالت». وهذا هو ما يُصلَح هنا.

## ولا نسخةَ ثانيةً لقاعدة البيانات

لا يُحفظ هنا متنُ مصدرٍ ولا صفٌّ من مجموعة بيانات ولا نصُّ مخطوطة (§38).
تُحفظ **البصمةُ والعدُّ والإحالة**: الوحداتُ الأصلية تبقى صاحبةَ الحقيقة،
وهذه تشير إليها.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

#: حالُ التوصية — أربعٌ، ولا خامسةَ تُخترع في الشيفرة.
PROPOSED = "proposed"
ACCEPTED = "accepted"
REJECTED = "rejected"
SUPERSEDED = "superseded"
RECOMMENDATION_STATUSES = (PROPOSED, ACCEPTED, REJECTED, SUPERSEDED)

#: مَن أنتج التوصية — ويُسجَّل لأنّ قاعدةً حتمية ونموذجًا احتماليًّا
#: لا يُقرآن بالثقة نفسها (§28).
BY_RULE = "rule"
BY_MODEL = "model"
BY_HYBRID = "hybrid"
GENERATORS = (BY_RULE, BY_MODEL, BY_HYBRID)


class ResearchContextSnapshot(Base, TenantScoped, Timestamped):
    """بصمةُ حالِ بحثٍ في لحظة — **ولا متنَ فيها**.

    والصفُّ لا يُعاد كتابتُه: كلُّ بصمةٍ جديدةٍ صفٌّ جديد، فيبقى تاريخُ
    البحث مقروءًا. وبصمةٌ تكرّرت (لم يتغيّر شيءٌ ذو معنى) **لا تُضاعِف
    صفًّا** — يمنعها القيدُ الفريد أدناه، ويُحدَّث `last_seen_at` مكانها.
    """

    __tablename__ = "research_context_snapshots"
    __table_args__ = (
        # **بصمةٌ واحدة لكلّ بحثٍ مرّةً واحدة.** ولولاه لَتَراكم صفٌّ لكلّ
        # فتحةِ شاشة، فصار الجدولُ سجلَّ زياراتٍ لا تاريخَ بحث.
        UniqueConstraint("project_id", "context_fingerprint",
                         name="uq_research_context_snapshots_project_id"),
        CheckConstraint("length(context_fingerprint) = 64",
                        name="ck_context_fingerprint_is_sha256"),
        Index("ix_research_context_snapshots_project_seen",
              "project_id", "last_seen_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)

    #: ستٌّ وستون محرفًا من `sha256` — تُحسب في `research_brain/fingerprint.py`.
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    #: نسخةُ صيغة البصمة. بصمتان بصيغتين مختلفتين لا تُقارَنان.
    fingerprint_schema: Mapped[str] = mapped_column(String(64), nullable=False)

    #: عدٌّ لا متن — يكفي للعرض والتشخيص ولا ينسخ البيانات.
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    relationship_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contradiction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: مفاتيحُ ما تعذّرت قراءتُه — رموزٌ لا رسائل (§53: لا متنَ سرّيّ في السجل).
    read_note_keys: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False)


class ResearchRecommendation(Base, TenantScoped, Timestamped):
    """اقتراحٌ قيل عن بحثٍ، **ومعه البصمةُ التي قيل تحتها**.

    وهذا العمودُ — `context_fingerprint` — هو كلُّ الفرق. توصيةٌ بلا بصمةٍ
    لا يمكن أن تَبْلى: تبقى معروضةً بعد أن تغيّر ما بُنيت عليه، فيقرأ
    الباحثُ قولًا عن بحثٍ لم يعد بحثَه. وبها تُقارَن بالبصمة الحالية فيُعرف
    أنّها **ليست جارية** (§41).

    **ولا يُغيَّر بها بحث.** قبولُ توصيةٍ لا يكتب في حقلٍ منهجيّ ولا يُنشئ
    قرارًا بأثرٍ جانبيّ: التغييرُ يقع بمسار الوحدة صاحبة الحقيقة، وقبولُ
    التوصية يُسجَّل هنا (§85). وV1 لا يفتح مسارَ قبولٍ أصلًا — والقراءةُ
    وحدها أصدقُ من فعلٍ يُوهم بأثرٍ لا يقع.
    """

    __tablename__ = "research_recommendations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'superseded')",
            name="ck_status_is_known"),
        CheckConstraint(
            "generated_by IN ('rule', 'model', 'hybrid')",
            name="ck_generated_by_is_known"),
        # **مخرَجُ نموذجٍ يُسمّى مزوّدَه.** وقاعدةٌ حتمية لا مزوّدَ لها.
        CheckConstraint(
            "(generated_by = 'rule' AND provider IS NULL) OR generated_by <> 'rule'",
            name="ck_rule_has_no_provider"),
        CheckConstraint("length(context_fingerprint) = 64",
                        name="ck_fingerprint_is_sha256"),
        UniqueConstraint("project_id", "context_fingerprint", "action_key",
                         name="uq_research_recommendations_project_id"),
        Index("ix_research_recommendations_project_status",
              "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("research_context_snapshots.id", ondelete="SET NULL"), nullable=True)

    #: البصمةُ التي وُلدت التوصيةُ تحتها — **لا البصمةُ الحالية**.
    context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    action_key: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PROPOSED)

    title_ar: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_ar: Mapped[str] = mapped_column(Text, nullable=False)
    reason_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: سندُ القول: معرّفاتُ الكيانات التي قُرئت — إحالةٌ لا نسخة.
    evidence_refs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: ما لا تعرفه هذه التوصية — يُقال ولا يُسكت عنه (§28).
    limitations_ar: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_by: Mapped[str] = mapped_column(String(16), nullable=False, default=BY_RULE)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    decided_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


__all__ = [
    "ACCEPTED", "BY_HYBRID", "BY_MODEL", "BY_RULE", "GENERATORS", "PROPOSED",
    "RECOMMENDATION_STATUSES", "REJECTED", "SUPERSEDED",
    "ResearchContextSnapshot", "ResearchRecommendation",
]
