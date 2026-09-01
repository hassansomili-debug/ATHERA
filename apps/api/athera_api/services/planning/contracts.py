"""عقد تخطيط النشر | The planning output contract (S5D §12، §13).

النموذج يعيد **بنية** لا نثرًا. وكل ما يعيده **مقترحٌ**: عنوانٌ وسؤالٌ
ومساهمةٌ يقترحها، لا حقائق مصدر. والحقائق تأتي من الذاكرة الموثقة وحدها،
ويُربَط المقترح بها بأدوارٍ يعلنها.
"""
from __future__ import annotations

from typing import Final

from pydantic import BaseModel, Field

# أنواع الفرص والأوراق — من مفردات المستودع القائمة، فلا يخترع النموذج نوعًا.
from ..thesis.vocab import OPPORTUNITY_KINDS, PAPER_KINDS

OPPORTUNITY_KIND_PATTERN: Final = "^(" + "|".join(OPPORTUNITY_KINDS) + ")$"
PAPER_KIND_PATTERN: Final = "^(" + "|".join(PAPER_KINDS) + ")$"


class ProposedOpportunity(BaseModel):
    """فرصة نشر **مقترحة** — لا حقيقة معتمدة.

    و`evidence_roles` هي ما يربطها بأدلتها: الأدوار التي استندت إليها من
    اللقطة. ولا يعيد النموذج معرّفات ذاكرة — يعيد أدوارًا، والكود يربط.
    """

    working_title_ar: str = Field(min_length=8, max_length=400)
    working_title_en: str | None = Field(default=None, max_length=400)
    research_question_ar: str = Field(min_length=8, max_length=1000)
    opportunity_kind: str = Field(pattern=OPPORTUNITY_KIND_PATTERN)
    paper_kind: str = Field(pattern=PAPER_KIND_PATTERN)
    proposed_contribution_ar: str = Field(min_length=8, max_length=1500)
    # ما تستند إليه من أدوار اللقطة — الحارس يرفض دورًا غير موجود فيها.
    evidence_roles: list[str] = Field(default_factory=list)
    methodological_approach_ar: str | None = Field(default=None, max_length=1000)
    analysis_opportunity_ar: str | None = Field(default=None, max_length=1000)
    theoretical_basis_ar: str | None = Field(default=None, max_length=1000)
    # حدود ما يجوز ادّعاؤه بهذه الأدلة — والنموذج يُسأل عنها صراحةً.
    claim_boundaries_ar: str | None = Field(default=None, max_length=1000)
    limitations_ar: str | None = Field(default=None, max_length=1000)
    missing_requirements_ar: list[str] = Field(default_factory=list)


class OpportunityBatch(BaseModel):
    opportunities: list[ProposedOpportunity] = Field(default_factory=list)


class OutlineSection(BaseModel):
    """قسم من هيكل الورقة — غرضٌ وأدلة، **لا نثر** (§27)."""

    key: str = Field(max_length=32)
    title_ar: str = Field(max_length=200)
    purpose_ar: str = Field(max_length=800)
    questions_ar: list[str] = Field(default_factory=list)
    evidence_roles: list[str] = Field(default_factory=list)
    claims_allowed_ar: list[str] = Field(default_factory=list)
    claims_unsupported_ar: list[str] = Field(default_factory=list)


class OutlineDraft(BaseModel):
    article_type: str | None = Field(default=None, max_length=32)
    sections: list[OutlineSection] = Field(default_factory=list)
