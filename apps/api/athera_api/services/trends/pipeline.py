"""خط الأنابيب الاستباقي وبطاقة الفرصة | Proactive pipeline (§51.4، §51.5، §51.6).

ثلاث قواعد تحكم هذا الملف:

  • البطاقة **لا تبدأ بالكتابة** (§51.4): تحمل سؤالًا وفجوة وأدلة ومنهجًا
    مقترحًا، ولا حقل فيها لنص مخطوطة.
  • الهدف **Ready for Submission** لا النشر (§51.5)، والشروط الاثنا عشر
    تُفحص كلها ويُسمّى الناقص (§51.6).
  • P14 بوابة بشرية: لا تقديم خارجي إلا بفعل صريح أو تفويض **قابل للسحب**.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .vocab import PIPELINE_STAGES, READY_CONDITIONS

STAGE_KEYS: tuple[str, ...] = tuple(key for key, _, _ in PIPELINE_STAGES)
FINAL_STAGE = "P14"


class PipelineError(Exception):
    pass


@dataclass(slots=True)
class OpportunityCard:
    """§51.4 — بطاقة فرصة استباقية بحقولها.

    لاحظ ما ليس فيها: لا `draft_text` ولا `manuscript`. «لا تبدأ بالكتابة
    مباشرة» منفَّذة بغياب الحقل لا بتعليمة.
    """

    card_id: str
    working_title_ar: str
    central_question_ar: str
    trend_summary_ar: str
    evidence_signal_ids: tuple[str, ...]
    gap_ar: str
    gap_confidence: float
    proposed_theory_ar: str | None = None
    proposed_method_ar: str | None = None
    required_data_ar: str | None = None
    data_is_available: bool | None = None
    novelty_note_ar: str | None = None
    candidate_journal_ids: tuple[str, ...] = ()
    execution_risk_ar: str | None = None
    estimated_months: int | None = None
    overlap_note_ar: str | None = None
    approved_by: str | None = None
    approved_at: dt.datetime | None = None

    def __post_init__(self) -> None:
        if not self.central_question_ar.strip():
            raise PipelineError("§51.8 — a trend never becomes a card without a question")
        if not self.gap_ar.strip():
            raise PipelineError("§51.8 — a card requires a defensible gap")
        if not self.evidence_signal_ids:
            raise PipelineError("§51.4 — a card must cite the signals that justify it")
        if not 0.0 <= self.gap_confidence <= 1.0:
            raise PipelineError("gap confidence must be within [0, 1]")

    @property
    def is_approved(self) -> bool:
        return self.approved_by is not None and self.approved_at is not None

    def approve(self, *, by: str, at: dt.datetime) -> None:
        """§51.11 — لا تُحوَّل البطاقة إلى مشروع إلا بعد اعتماد المستخدم."""
        if self.is_approved:
            raise PipelineError("this card is already approved")
        self.approved_by = by
        self.approved_at = at


@dataclass(frozen=True, slots=True)
class SubmissionDelegation:
    """§51.5 P14 — تفويض مؤسسي **قابل للسحب والتدقيق**، لا علم منطقي."""

    delegation_id: str
    granted_by: str
    granted_at: dt.datetime
    scope_ar: str
    expires_at: dt.datetime | None = None
    revoked_at: dt.datetime | None = None

    def is_active(self, *, at: dt.datetime) -> bool:
        if self.revoked_at is not None and self.revoked_at <= at:
            return False
        if self.expires_at is not None and self.expires_at <= at:
            return False
        return True


@dataclass(slots=True)
class StageState:
    stage: str
    label_ar: str
    label_en: str
    completed: bool


@dataclass(slots=True)
class PipelineState:
    card_id: str
    current_stage: str
    stages: list[StageState]
    ready_conditions: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.current_stage not in STAGE_KEYS:
            raise PipelineError(f"unknown pipeline stage: {self.current_stage}")

    @property
    def unmet_ready_conditions(self) -> list[str]:
        return [key for key in READY_CONDITIONS if not self.ready_conditions.get(key, False)]

    @property
    def can_reach_ready_for_submission(self) -> bool:
        """§51.6 — الشروط الاثنا عشر كلها، لا أغلبها."""
        return not self.unmet_ready_conditions


def build_state(card_id: str, *, completed_stages: set[str],
                ready_conditions: dict[str, bool] | None = None) -> PipelineState:
    unknown = completed_stages - set(STAGE_KEYS)
    if unknown:
        raise PipelineError(f"unknown stages: {sorted(unknown)}")

    stages = [
        StageState(stage=key, label_ar=label_ar, label_en=label_en,
                   completed=key in completed_stages)
        for key, label_ar, label_en in PIPELINE_STAGES
    ]
    current = next((s.stage for s in stages if not s.completed), FINAL_STAGE)
    return PipelineState(card_id=card_id, current_stage=current, stages=stages,
                         ready_conditions=ready_conditions or {})


@dataclass(slots=True)
class SubmissionDecision:
    allowed: bool
    basis: str            # human_act | delegation | blocked
    reason_ar: str
    reason_en: str
    unmet_conditions: list[str] = field(default_factory=list)


def authorize_submission(
    state: PipelineState, *, human_act_by: str | None = None,
    delegation: SubmissionDelegation | None = None, at: dt.datetime,
) -> SubmissionDecision:
    """§51.5 P14 — الباب الوحيد إلى تقديم خارجي."""
    unmet = state.unmet_ready_conditions
    if unmet:
        return SubmissionDecision(
            allowed=False, basis="blocked",
            reason_ar="الشروط الاثنا عشر غير مكتملة؛ الحالة ليست Ready for Submission.",
            reason_en="The twelve conditions are unmet; status is not Ready for Submission.",
            unmet_conditions=unmet,
        )
    if human_act_by:
        return SubmissionDecision(
            allowed=True, basis="human_act",
            reason_ar="تقديم بفعل بشري صريح من الباحث.",
            reason_en="Submission by an explicit human act.",
        )
    if delegation is not None and delegation.is_active(at=at):
        return SubmissionDecision(
            allowed=True, basis="delegation",
            reason_ar=f"تفويض مؤسسي ساري وقابل للسحب: {delegation.scope_ar}.",
            reason_en=f"Active, revocable institutional delegation: {delegation.scope_ar}.",
        )
    return SubmissionDecision(
        allowed=False, basis="blocked",
        reason_ar="لا فعل بشري ولا تفويض ساري؛ لا يقع تقديم خارجي (§51.5 P14).",
        reason_en="No human act and no active delegation; no external submission (§51.5 P14).",
    )
