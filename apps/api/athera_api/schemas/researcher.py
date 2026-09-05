"""عقودُ ذكاء الباحث | Researcher intelligence contracts (Wave 2-A).

**ولا رقمَ يوهم يقينًا في هذا الملفّ.** لا `float` ولا `Decimal` ولا حقلٌ
اسمُه نسبةٌ أو احتمالٌ أو درجة — ولا في مخرَجٍ ولا في مدخَل. والمنعُ بنيويّ
لا سلوكيّ: ما لا يوجد له نوعٌ في العقد لا يُرسَل سهوًا في مراجعةٍ قادمة.
والعددُ الصحيحُ الوحيد المسموح هو رقمُ الإصدار — وهو ترتيبٌ لا قياس.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from ..models.researcher_intelligence import (
    ALIGNMENT_VERDICTS,
    CANDIDATE_SOURCE_TYPES,
    CANDIDATE_STATUSES,
    CONSTRAINT_TYPES,
    EXTRACTION_METHODS,
    GOAL_PRIORITIES,
    GOAL_STATUSES,
    GOAL_TYPES,
    ORCID_STATUSES,
    PROFILE_STATES,
    STRATEGY_STATUSES,
)

GoalType = Literal[GOAL_TYPES]  # type: ignore[valid-type]
GoalStatus = Literal[GOAL_STATUSES]  # type: ignore[valid-type]
GoalPriority = Literal[GOAL_PRIORITIES]  # type: ignore[valid-type]
ConstraintType = Literal[CONSTRAINT_TYPES]  # type: ignore[valid-type]
CandidateStatus = Literal[CANDIDATE_STATUSES]  # type: ignore[valid-type]
CandidateSourceType = Literal[CANDIDATE_SOURCE_TYPES]  # type: ignore[valid-type]
ExtractionMethod = Literal[EXTRACTION_METHODS]  # type: ignore[valid-type]
ProfileState = Literal[PROFILE_STATES]  # type: ignore[valid-type]
OrcidStatus = Literal[ORCID_STATUSES]  # type: ignore[valid-type]
StrategyStatus = Literal[STRATEGY_STATUSES]  # type: ignore[valid-type]
AlignmentVerdict = Literal[ALIGNMENT_VERDICTS]  # type: ignore[valid-type]

# لغتان لا ثالثة (§8).
Language = Literal["ar", "en"]


# ═══════════════════ الملفّ ═══════════════════


class ResearcherProfileResponse(BaseModel):
    """الملفُّ الفعّال — وما فيه إمّا كُتب بيد صاحبه وإمّا أكّده."""

    id: uuid.UUID
    user_id: uuid.UUID

    institution_ar: str | None = None
    institution_en: str | None = None
    college_ar: str | None = None
    college_en: str | None = None
    department_ar: str | None = None
    department_en: str | None = None
    current_rank: str | None = None
    target_rank: str | None = None
    primary_field_ar: str | None = None
    primary_field_en: str | None = None
    country: str | None = None
    keywords: list[str] | None = None

    # §8 — أربعةُ مفاهيم، وثلاثةٌ منها هنا. **ولغةُ الواجهة ليست منها**:
    # هي تفضيلُ عرضٍ في المتصفّح، ولا تُخزَّن في هذا الملفّ ولا تُبدّله.
    preferred_research_languages: list[Language] | None = None
    preferred_working_language: Language | None = None
    preferred_manuscript_language: Language | None = None
    ai_response_language: Language | None = None

    orcid: str | None = None
    #: **والصيغةُ الصحيحة ليست توثيقًا** — الحقلان يُقرآن معًا أو لا يُقرآن.
    orcid_status: OrcidStatus
    orcid_verified_at: dt.datetime | None = None
    orcid_source: str | None = None

    #: كيف صار كلُّ حقلٍ إلى ما هو عليه — الحالاتُ الخمس مقروءةً حقلًا حقلًا.
    field_provenance: dict[str, dict[str, str | None]] | None = None


class ResearcherProfilePatch(BaseModel):
    """ما يكتبه الباحثُ بيده — ويدخل الملفَّ بحال `user_declared`."""

    institution_ar: str | None = Field(default=None, max_length=255)
    institution_en: str | None = Field(default=None, max_length=255)
    college_ar: str | None = Field(default=None, max_length=255)
    college_en: str | None = Field(default=None, max_length=255)
    department_ar: str | None = Field(default=None, max_length=255)
    department_en: str | None = Field(default=None, max_length=255)
    current_rank: str | None = Field(default=None, max_length=64)
    target_rank: str | None = Field(default=None, max_length=64)
    primary_field_ar: str | None = Field(default=None, max_length=255)
    primary_field_en: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=64)
    keywords: list[str] | None = None

    preferred_research_languages: list[Language] | None = None
    preferred_working_language: Language | None = None
    preferred_manuscript_language: Language | None = None
    ai_response_language: Language | None = None

    #: يُتحقَّق من صيغته وخانةِ تدقيقه، **ولا يُرفَع بذلك إلى موثَّق** (§6).
    #: ولا حقلَ هنا يقبل `orcid_status`: حالُ التوثيق ليست مما يُصرَّح به.
    orcid: str | None = Field(default=None, max_length=64)


# ═══════════════════ المرشَّحات ═══════════════════


class ProfileCandidateResponse(BaseModel):
    id: uuid.UUID
    field_name: str
    candidate_value: str
    source_type: CandidateSourceType
    source_id: uuid.UUID | None = None
    provenance: str | None = None
    extraction_method: ExtractionMethod
    #: إحدى الحالات الخمس (§2) — ولا تُدمج باثنتين.
    profile_state: ProfileState
    status: CandidateStatus
    #: **أهو في الملفّ الفعّال؟** جوابٌ صريحٌ لا يُستنتج من اللون.
    in_active_profile: bool
    created_at: dt.datetime
    decided_at: dt.datetime | None = None
    decided_by: uuid.UUID | None = None
    decision_reason: str | None = None


class ProfileCandidateCreate(BaseModel):
    """إدخالٌ يدويّ يُراجَع لاحقًا — ولا يدخل الملفَّ قبل تأكيده."""

    field_name: str = Field(max_length=64)
    candidate_value: str = Field(min_length=1, max_length=2000)
    provenance: str | None = Field(default=None, max_length=1000)


class CandidateDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


# ═══════════════════ الأهداف ═══════════════════


class GoalResponse(BaseModel):
    id: uuid.UUID
    goal_type: GoalType
    target: str
    priority: GoalPriority
    timeframe: str | None = None
    status: GoalStatus
    researcher_confirmed: bool
    notes: str | None = None
    created_at: dt.datetime


class GoalCreate(BaseModel):
    """**والهدفُ ليس وعدًا** — لا حقلَ هنا يقبل احتمالًا ولا نسبةَ إنجاز."""

    goal_type: GoalType
    target: str = Field(min_length=1, max_length=2000)
    priority: GoalPriority = "medium"
    timeframe: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    researcher_confirmed: bool = False


class GoalPatch(BaseModel):
    goal_type: GoalType | None = None
    target: str | None = Field(default=None, min_length=1, max_length=2000)
    priority: GoalPriority | None = None
    timeframe: str | None = Field(default=None, max_length=64)
    status: GoalStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)
    researcher_confirmed: bool | None = None


# ═══════════════════ القيود ═══════════════════


class ConstraintResponse(BaseModel):
    id: uuid.UUID
    constraint_type: ConstraintType
    value: str
    notes: str | None = None
    researcher_confirmed: bool
    created_at: dt.datetime


class ConstraintCreate(BaseModel):
    """**ولا يُخترع قيدٌ غائب** — والقيمةُ نصٌّ يقوله الباحث، لا رقمٌ يُحسب."""

    constraint_type: ConstraintType
    value: str = Field(min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    researcher_confirmed: bool = False


class ConstraintPatch(BaseModel):
    constraint_type: ConstraintType | None = None
    value: str | None = Field(default=None, min_length=1, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    researcher_confirmed: bool | None = None


# ═══════════════════ الاستراتيجيّة ═══════════════════


class StrategyResponse(BaseModel):
    id: uuid.UUID
    #: ترتيبٌ لا قياس — و`1` ليست أقلَّ جودةً من `2`، بل أسبقُ منها.
    strategy_version: int
    status: StrategyStatus
    generated_at: dt.datetime
    approved_at: dt.datetime | None = None
    approved_by: uuid.UUID | None = None
    superseded_by: uuid.UUID | None = None

    rationale_ar: str | None = None
    rationale_en: str | None = None
    #: **والناقصُ يُقال دائمًا** (§7) — مفاتيحُ تُترجَم في الواجهة.
    missing_information: list[str]

    profile_snapshot: dict | None = None
    goals_snapshot: list | None = None
    constraints_snapshot: list | None = None


class StrategyCreate(BaseModel):
    rationale_ar: str | None = Field(default=None, max_length=4000)
    rationale_en: str | None = Field(default=None, max_length=4000)


class StrategyApproval(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AlignmentResponse(BaseModel):
    """**ولا نسبة** — حكمٌ من أربعةٍ وتعليلُه، و`unknown` جوابٌ مشروع."""

    id: uuid.UUID
    strategy_id: uuid.UUID
    project_id: uuid.UUID
    verdict: AlignmentVerdict
    rationale_ar: str | None = None
    rationale_en: str | None = None
    missing_information: list[str] | None = None
    assessed_at: dt.datetime
