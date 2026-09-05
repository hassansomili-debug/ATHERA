"""ذكاءُ الباحث — الموجة الثانية | Researcher intelligence (PUBRIVA, Wave 2-A).

المرجع: `docs/wave2/researcher-intelligence-product-spec.md`.

**أهمُّ سطرٍ هنا: الحالاتُ الخمس لا تُدمج اثنتان منها.** ولا يصير مرشَّحٌ
مؤكَّدًا إلّا بفعلِ إنسانٍ يُنسب إلى صاحبه ووقته. وهذا مفروضٌ في القاعدة —
لا في الموجّه وحده — لأنّ موجّهًا يُكتب غدًا يعيد العطب.

**ولا رقمَ يوهم يقينًا.** لا نسبةَ جاهزية، ولا احتمالَ قَبول، ولا درجةَ
نجاح. والمنعُ بنيويّ: لا عمودَ عائمًا ولا عشريًّا في هذا الملفّ كلِّه.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Final

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TenantScoped, Timestamped, uuid_pk

# ── §2 — الحالاتُ الخمس. مفرداتٌ مغلقة، ومرآتها قيدُ CHECK في 0030 ──
#
# ولا تصير حالٌ حالًا أخرى إلّا بفعلِ إنسان: لا استخراجٌ يكتب في الملفّ،
# ولا نموذجٌ يرقّي اقتراحه، ولا تنسيقٌ صحيحٌ يُنتج توثيقًا.
PROFILE_STATES: Final[tuple[str, ...]] = (
    "user_declared",        # كتبها الباحثُ بيده
    "document_extracted",   # قُرئت من سيرةٍ ذاتية — وليست في الملفّ الفعّال
    "confirmed",            # نظر فيها الباحثُ وأقرّها
    "externally_verified",  # جاءت من مصدرٍ خارجيّ مُتحقَّق، وتُحفظ بمصدرها
    "model_suggested",      # رآه نموذجٌ لغويّ — وليس في الملفّ الفعّال
)

#: الحالاتُ التي **لا** تدخل الملفَّ الفعّال بحال (§2).
STATES_OUTSIDE_THE_ACTIVE_PROFILE: Final[tuple[str, ...]] = (
    "document_extracted",
    "model_suggested",
)

# مفرداتُ القرار — تُستعار كما هي من مسار `fact_candidates` القائم،
# فلا تنشأ لغتان لشيءٍ واحد (§1).
CANDIDATE_STATUSES: Final[tuple[str, ...]] = (
    "proposed", "confirmed", "rejected", "needs_review",
)

CANDIDATE_SOURCE_TYPES: Final[tuple[str, ...]] = ("manual", "cv_upload", "orcid", "model")

EXTRACTION_METHODS: Final[tuple[str, ...]] = ("researcher", "deterministic", "model")

# §6 — حالُ توثيق ORCID. والصيغةُ الصحيحة ليست توثيقًا.
ORCID_STATUSES: Final[tuple[str, ...]] = (
    "unverified", "user_declared", "externally_verified",
)

GOAL_TYPES: Final[tuple[str, ...]] = (
    "publication", "promotion", "funding", "collaboration",
    "skill", "visibility", "thesis", "other",
)

GOAL_STATUSES: Final[tuple[str, ...]] = ("active", "achieved", "abandoned", "deferred")

GOAL_PRIORITIES: Final[tuple[str, ...]] = ("high", "medium", "low")

# §4 — القيود. وغيابُ القيد «غيرُ معروف»، لا «لا قيد».
CONSTRAINT_TYPES: Final[tuple[str, ...]] = (
    "time",
    "publication_budget",
    "no_fee_preference",
    "language",
    "data_availability",
    "institutional",
    "deadline",
    "methodological",
    "geography_community",
    "collaboration",
)

STRATEGY_STATUSES: Final[tuple[str, ...]] = (
    "draft", "needs_review", "approved", "superseded",
)

#: §4 — ولا نسبة. حكمٌ مُعلَّل بأربع كلماتٍ لا بدرجة.
ALIGNMENT_VERDICTS: Final[tuple[str, ...]] = (
    "aligns", "partially_aligns", "conflicts", "unknown",
)


class ResearcherProfileCandidate(Base, TenantScoped, Timestamped):
    """§4 — مرشَّحُ حقلٍ في الملفّ الشخصيّ. **ولا يكتب مرشَّحٌ في الملفّ.**

    ولماذا كيانٌ جديد ولم يُستعمل `FactCandidate`؟ لأنّ ذاك مربوطٌ ببنيةٍ
    مستنديّة: `file_id` و`chunk_id` غيرُ قابلين للعدم — وهو صوابٌ لما وُضع
    له. ومرشَّحُ الملفّ قد يأتي من إدخالٍ يدويّ أو من ORCID أو من اقتراحِ
    نموذج، ولا مستندَ خلفه ولا مقطع. وحشرُه هناك يُنتج أعمدةً فارغةً تكذب
    أو تخفيفَ قيدٍ يحرس أثرَ الاستخراج (§1).
    """

    __tablename__ = "researcher_profile_candidates"
    __table_args__ = (
        # **قرارٌ بلا صاحبٍ ووقتٍ لا يكون** (§4). القيدان في القاعدة لأنّ
        # الموجّه يُعاد كتابته والقاعدة لا.
        CheckConstraint(
            "(status = 'proposed') = (decided_by IS NULL)",
            name="decision_has_an_actor",
        ),
        CheckConstraint(
            "(decided_by IS NULL) = (decided_at IS NULL)",
            name="decision_has_a_time",
        ),
        # الحالُ الخامسة `confirmed` تُقارن حرفًا بحرف مع قرار التأكيد،
        # فلا يصير صفٌّ «مؤكَّدًا» في عمودٍ ومقترحًا في الآخر.
        CheckConstraint(
            "(profile_state = 'confirmed') = (status = 'confirmed')",
            name="state_matches_status",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # نصٌّ لا رقم: قيمةُ حقلٍ في ملفٍّ شخصيّ ليست كمًّا يُقاس.
    candidate_value: Mapped[str] = mapped_column(Text, nullable=False)

    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # قابلٌ للعدم عمدًا: الإدخالُ اليدويّ لا مصدرَ له غيرُ صاحبه.
    source_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    # نصٌّ يقول من أين ولماذا — يُعرض للباحث كما هو.
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(16), nullable=False)

    profile_state: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")

    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearcherGoal(Base, TenantScoped, Timestamped):
    """§4 — **والهدفُ ليس وعدًا.**

    «أنشر في Q1» نيّةٌ يقيس عليها الباحثُ نفسه، ولا تقرؤها المنصّةُ تعهّدًا
    ولا تبني عليها احتمالًا. فلا عمودَ هنا يحمل نسبةً ولا أجلًا محسوبًا.
    """

    __tablename__ = "researcher_goals"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    goal_type: Mapped[str] = mapped_column(String(24), nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="medium")
    # قابلٌ للعدم: «متى» قد لا يكون معروفًا، والمجهولُ يبقى مجهولًا.
    timeframe: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    researcher_confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ResearcherConstraint(Base, TenantScoped, Timestamped):
    """§4 — **ولا يُخترع قيدٌ غائب.** غيابُ القيد «غيرُ معروف»، لا «لا قيد»."""

    __tablename__ = "researcher_constraints"

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    constraint_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # نصٌّ لا رقم — حتى «الميزانية» تُكتب كما يقولها الباحث. ورقمٌ هنا يصير
    # مدخلًا لحسابٍ يوهم يقينًا لا نملكه.
    value: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    researcher_confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)


class ResearchStrategy(Base, TenantScoped, Timestamped):
    """§4 — استراتيجيّةٌ مُرقَّمةُ الإصدار. **والمعتمَدُ لا يُعدَّل.**

    تغييرُ استراتيجيّةٍ معتمَدة يُنشئ إصدارًا تاليًا ويُحيل الأوّل
    `superseded`. واللقطاتُ تُخزَّن لأنّ الأهدافَ تتبدّل، وقرارٌ اتُّخذ على
    حالٍ سابقة يُقرأ خطأً إن قيس بحالٍ لاحقة.
    """

    __tablename__ = "research_strategies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "profile_id", "strategy_version", name="uq_research_strategies_version"
        ),
        CheckConstraint("strategy_version >= 1", name="version_starts_at_one"),
        # اعتمادٌ بلا وقتٍ وصاحبٍ لا يكون — وهي القاعدةُ نفسها التي تحكم
        # قرارَ المرشَّح، مطبَّقةً على قرارِ الاعتماد.
        CheckConstraint(
            "(approved_at IS NULL) = (approved_by IS NULL)",
            name="approval_has_an_actor",
        ),
        CheckConstraint(
            "status <> 'approved' OR approved_at IS NOT NULL",
            name="approved_carries_its_time",
        ),
        # و«مُحالٌ» لا يكون إلّا لما اعتُمد: إحالةُ مسوّدةٍ تعني أنّ قرارًا
        # اتُّخذ ولم يُتَّخذ.
        CheckConstraint(
            "approved_at IS NULL OR status IN ('approved', 'superseded')",
            name="approval_only_when_decided",
        ),
        CheckConstraint(
            "(status = 'superseded') = (superseded_by IS NOT NULL)",
            name="superseded_names_its_successor",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("researcher_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    strategy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    # تعليلٌ بالكلمات — وهو كلُّ ما تملكه المنصّة. ولا درجةَ تصاحبه.
    rationale_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # **والناقصُ يُقال دائمًا** (§7): ما لا تعرفه الاستراتيجيّة مكتوبٌ فيها.
    missing_information: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    goals_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)
    constraints_snapshot: Mapped[list] = mapped_column(JSONB, nullable=False)

    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("research_strategies.id", ondelete="SET NULL"),
        nullable=True,
    )


class ProjectStrategyAssessment(Base, TenantScoped, Timestamped):
    """§4 — محاذاةُ مشروعٍ لاستراتيجيّة. **ولا نسبة.**

    لا جاهزيّة، ولا احتمالُ قَبول، ولا درجةُ نجاح — حكمٌ من أربعةٍ وتعليلُه.
    و`unknown` جوابٌ مشروعٌ يُقال، لا فراغٌ يُملأ بتخمين.

    والجدولُ يُنشأ في هذه الموجة ولا يُملأ آليًّا: **ترتيبُ المشاريع آليًّا
    مؤجَّلٌ عمدًا** (§13)، فلا مسارَ في هذه الموجة يكتب فيه حكمًا من نفسه.
    """

    __tablename__ = "project_strategy_assessments"
    __table_args__ = (
        UniqueConstraint(
            "strategy_id", "project_id", name="uq_project_strategy_assessments_strategy_id"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("research_strategies.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("research_projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    verdict: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    rationale_ar: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    missing_information: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    assessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
