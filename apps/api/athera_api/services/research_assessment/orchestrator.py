"""منسّقُ الرحلة: من لقطةٍ إلى بصمةٍ وخطوةٍ تالية | The journey orchestrator bridge (Wave 2-A).

**هنا وحدَه تلتقي القاعدةُ بالجلسة.** القواعدُ في
`research_brain/journey.py` حتميّةٌ خالصة تُختبر بلا PostgreSQL، والبصمةُ
في `research_brain/fingerprint.py` كذلك. وهذه الوحدةُ تقرأ وتكتب، فتسكن
هنا لا هناك — وهو الحدُّ نفسه الذي أعلنه `snapshot.py` في رأسه.

## ولا تُعاد كتابةُ بحثٍ من هنا

هذه الوحدةُ تكتب في جدولَي العقل وحدَهما: بصمةٌ رُصدت، وتوصيةٌ قيلت. ولا
تكتب سؤالَ بحثٍ ولا منهجًا ولا قرارًا — الوحداتُ الأصلية تبقى صاحبةَ
الحقيقة (§8، §29)، والباحثُ صاحبَ القرار.

## وكيف تَبْلى التوصية

    تُولَّد توصيةٌ تحت البصمة F1
    يتغيّر البحثُ تغيّرًا ذا معنى  →  البصمة صارت F2
    فالتوصيةُ تحت F1 **ليست جارية**

ولا تُحذف: تُوسَم `superseded` ويبقى نصُّها وتاريخُها. فمحوُ ما قيل يُفقد
القدرةَ على مراجعة ما قالته المنصّةُ ومتى — وهي أوّلُ ما يُسأل عنه حين
يُشتبه في حكم.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research_brain import (
    PROPOSED,
    SUPERSEDED,
    ResearchContextSnapshot,
    ResearchRecommendation,
)
from ...research_brain import fingerprint, journey
from .snapshot import ProjectSnapshot
from .view import ResearcherReport, assess


def facts_of(snapshot: ProjectSnapshot, report: ResearcherReport) -> journey.JourneyFacts:
    """وقائعُ الرحلة من اللقطة والتقرير معًا.

    و«ما ينتظر مراجعة» يُقرأ من **التقرير** لا من اللقطة: حالُ الحقل حكمٌ
    تُصدره `view.py` بمفرداتها الأربع، وإعادةُ اشتقاقه هنا تُنتج مفردةً
    ثانيةً للشيء نفسه — وهو العطبُ الذي يحذّر منه `research_brain` في رأس
    أنطولوجيته.
    """
    return journey.read_facts(
        snapshot.assessment.graph,
        needs_review=[item.key for item in report.needs_review],
        contradictions=[row.claim_id for row in snapshot.contradictions],
        written_sections=[key for key, text in snapshot.assessment.sections.items()
                          if text],
    )


def fingerprint_of(snapshot: ProjectSnapshot) -> str:
    """بصمةُ هذه اللقطة — بالصيغة الواحدة لا بصيغةٍ محليّة."""
    return fingerprint.of(
        snapshot.assessment, project_id=str(snapshot.project_id),
        contradiction_keys=[row.claim_id for row in snapshot.contradictions])


async def record_snapshot(session: AsyncSession, *, tenant_id: uuid.UUID,
                          snapshot: ProjectSnapshot,
                          context_fingerprint: str) -> ResearchContextSnapshot:
    """يرصد البصمة — صفًّا جديدًا، أو يُحدّث «آخرُ ما رُئي» على القائم.

    **ولا صفَّ لكلّ فتحةِ شاشة.** فتحُ الصفحة عشرَ مرّاتٍ بلا تغييرٍ في
    البحث حدثٌ واحد لا عشرة، وجدولٌ يعدّه عشرًا يصير سجلَّ زياراتٍ لا
    تاريخَ بحث.
    """
    now = dt.datetime.now(dt.timezone.utc)
    existing = (await session.execute(
        select(ResearchContextSnapshot).where(
            ResearchContextSnapshot.project_id == snapshot.project_id,
            ResearchContextSnapshot.context_fingerprint == context_fingerprint,
        ))).scalar_one_or_none()

    if existing is not None:
        existing.last_seen_at = now
        return existing

    row = ResearchContextSnapshot(
        tenant_id=tenant_id,
        project_id=snapshot.project_id,
        context_fingerprint=context_fingerprint,
        fingerprint_schema=fingerprint.SCHEMA,
        entity_count=len(snapshot.assessment.graph.entities),
        relationship_count=len(snapshot.assessment.graph.relationships),
        contradiction_count=len(snapshot.contradictions),
        # **مفاتيحُ لا رسائل**: الرسالةُ تُترجَم وتتغيّر، والمفتاحُ يُقارَن.
        read_note_keys=sorted({note.key for note in snapshot.notes}) or None,
        first_seen_at=now, last_seen_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def expire_stale(session: AsyncSession, *, project_id: uuid.UUID,
                       current_fingerprint: str) -> int:
    """يوسم كلَّ توصيةٍ قيلت تحت بصمةٍ أخرى: **لم تعد جارية**.

    ولا تُحذف، ولا تُوسَم المقبولةُ ولا المرفوضة: قرارُ الباحث فيها وقع
    ويبقى. والوسمُ لـ`proposed` وحدها — وهي التي كانت ستُعرض على أنها قولٌ
    جارٍ عن البحث.
    """
    result = await session.execute(
        update(ResearchRecommendation)
        .where(ResearchRecommendation.project_id == project_id,
               ResearchRecommendation.status == PROPOSED,
               ResearchRecommendation.context_fingerprint != current_fingerprint)
        .values(status=SUPERSEDED)
    )
    return int(result.rowcount or 0)


async def persist_actions(session: AsyncSession, *, tenant_id: uuid.UUID,
                          project_id: uuid.UUID, snapshot_row: ResearchContextSnapshot,
                          context_fingerprint: str,
                          actions: tuple[journey.NextAction, ...]) -> list[ResearchRecommendation]:
    """يحفظ ما قيل تحت هذه البصمة — مرّةً واحدة.

    **و`generated_by='rule'` بلا مزوّد**: هذه قواعدُ حتمية لا نموذج، والقيدُ
    في القاعدة يرفض أن يُكتب لها مزوّد. فإن جاء يومٌ تُقترح فيه توصيةٌ من
    نموذج، لزمها أن تُسمّي مزوّدَها — ولا تختلط بهذه.
    """
    known = set((await session.execute(
        select(ResearchRecommendation.action_key).where(
            ResearchRecommendation.project_id == project_id,
            ResearchRecommendation.context_fingerprint == context_fingerprint,
        ))).scalars())

    written: list[ResearchRecommendation] = []
    for action in actions:
        # الفعلُ الممنوع لا يُحفظ توصيةً: حالٌ تُعرض، لا اقتراحٌ يُقبل.
        if action.status is journey.ActionStatus.BLOCKED:
            continue
        if action.action_key in known:
            continue
        row = ResearchRecommendation(
            tenant_id=tenant_id, project_id=project_id, snapshot_id=snapshot_row.id,
            context_fingerprint=context_fingerprint,
            action_key=action.action_key, category=action.category.value,
            status=PROPOSED,
            title_ar=action.title_ar, title_en=action.title_en,
            reason_ar=action.reason_ar, reason_en=action.reason_en,
            evidence_refs=list(action.evidence_refs) or None,
            limitations_ar=LIMITATION_AR,
            generated_by="rule", provider=None, model=None,
        )
        session.add(row)
        written.append(row)
    if written:
        await session.flush()
    return written


#: ما لا تعرفه كلُّ توصيةٍ هنا — **يُقال ولا يُسكت عنه** (§28).
LIMITATION_AR = (
    "اقتراحٌ من قاعدةٍ حتمية تقرأ ما سُجِّل في هذا البحث داخل PUBRIVA وحدَه. "
    "وما لم يُسجَّل لا يُقرأ، فقد يكون الفعلُ واقعًا خارج المنصّة."
)


class JourneyOutcome:
    """جوابُ المنسّق كاملًا — ولا يُبنى إلا من `advance`."""

    __slots__ = ("context_fingerprint", "snapshot_row", "decision", "expired",
                 "persisted", "facts")

    def __init__(self, *, context_fingerprint: str,
                 snapshot_row: ResearchContextSnapshot,
                 decision: journey.JourneyDecision, facts: journey.JourneyFacts,
                 expired: int, persisted: list[ResearchRecommendation]) -> None:
        self.context_fingerprint = context_fingerprint
        self.snapshot_row = snapshot_row
        self.decision = decision
        self.facts = facts
        self.expired = expired
        self.persisted = persisted


async def advance(session: AsyncSession, *, tenant_id: uuid.UUID,
                  snapshot: ProjectSnapshot) -> JourneyOutcome:
    """المسارُ كاملًا: لقطة ← بصمة ← رصد ← تقادمٌ ← قواعد ← حفظ.

    **ولا نموذجَ في شيءٍ من هذا** (§30). فلو سقط المزوّدُ كلُّه لبقي هذا
    عاملًا: الحالُ تُقرأ، والخطوةُ التالية تُقال، والتاريخُ يُحفظ.
    """
    _report_rules, report = assess(snapshot)
    facts = facts_of(snapshot, report)
    current = fingerprint_of(snapshot)

    snapshot_row = await record_snapshot(
        session, tenant_id=tenant_id, snapshot=snapshot, context_fingerprint=current)
    expired = await expire_stale(
        session, project_id=snapshot.project_id, current_fingerprint=current)

    decision = journey.decide(facts)
    persisted = await persist_actions(
        session, tenant_id=tenant_id, project_id=snapshot.project_id,
        snapshot_row=snapshot_row, context_fingerprint=current,
        actions=decision.actions)

    return JourneyOutcome(
        context_fingerprint=current, snapshot_row=snapshot_row, decision=decision,
        facts=facts, expired=expired, persisted=persisted)


__all__ = ["JourneyOutcome", "LIMITATION_AR", "advance", "expire_stale", "facts_of",
           "fingerprint_of", "persist_actions", "record_snapshot"]
