"""ما يُحفظ من العقل البحثيّ — لقطةٌ واحدة | Brain V1 persistence (Wave 2-A §35).

**جدولٌ واحد، وسؤالٌ واحد لا يجيب عنه جدولٌ قائم:**

> متى تغيّر حالُ هذا البحث تغيّرًا ذا معنى؟

وقد فُتِّش عن بديلٍ قبل أن يُكتب ترحيل (§34):

| البديلُ المرشَّح | ولمَ لا يكفي |
|---|---|
| `audit_events` | سلسلةُ تجزئةٍ ملحقةٌ لا تُستعلَم بالبحث وبالبصمة، وتحميلُها هذا يُفسد ما هي له |
| `project_decisions` | قرارُ إنسان، لا حالُ بحثٍ عبر الزمن |
| `researcher_memories` | معرفةٌ موثقةٌ عن البحث، لا بصمةُ حاله |
| `guardrail_checks` | فحصُ مخرَجِ نموذج |
| `research_intelligence_briefs` | موجزُ رادارٍ خارجيّ عن مجالٍ، لا لقطةُ مشروعٍ بعينه |

**والحاجةُ مسجَّلةٌ قبل هذا الترحيل** في `docs/research-brain-foundation.md`
بندًا أوّلَ: «التقييم يُحسب عند كل نداء، ولا يمكن اليوم مقارنةُ تقييمِ اليوم
بتقييم الأمس ولا معرفةُ متى ظهرت مخالفةٌ أو زالت».

## ولمَ لا جدولَ ثانٍ للتوصيات

كان هنا `research_recommendations`، وأُسقط في مراجعةٍ معمارية قبل الدمج.
والسببُ أنّ **الخطوةَ المقترحة تُحسب من الحال الراهنة في كلّ طلب**:
`journey.decide()` دالّةٌ خالصة لا تقرأ قاعدةً ولا تكتب فيها. فالمعروضُ
على الباحث لا يأتي من صفٍّ محفوظ ولم يكن يأتي منه قطّ.

فكان الجدولُ **يُكتب ولا يُقرأ**: قراءتُه الوحيدة كانت على نفسه، ليمنع
تكرارَ إدخالٍ فيه. وصفٌّ لا يُقرأ لا يحرس شيئًا، ويحمل معه مفاهيمَ لا
مسارَ لها بعد — `accepted` و`rejected` و`decided_by` و`provider` — فتبدو
موجودةً وهي لا تقع.

**والتقادمُ الذي كان يحرسه بنيويٌّ بلا جدول:** ما دامت التوصيةُ تُحسب من
الحال الراهنة، فلا سبيلَ أصلًا إلى عرض توصيةٍ قديمةٍ على أنها جارية.
وحفظُ تاريخِ «أوصت المنصّةُ بكذا تحت البصمة F1» **مراقبةٌ وتدقيق**، تُبنى
حين يُبنى ما يستهلكها — لا قبله.

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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk


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


__all__ = ["ResearchContextSnapshot"]
