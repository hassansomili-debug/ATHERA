"""منسّقُ الرحلة: من لقطةٍ إلى بصمةٍ وخطوةٍ تالية | The journey orchestrator bridge (Wave 2-A).

**هنا وحدَه تلتقي القاعدةُ بالجلسة.** القواعدُ في
`research_brain/journey.py` حتميّةٌ خالصة تُختبر بلا PostgreSQL، والبصمةُ
في `research_brain/fingerprint.py` كذلك. وهذه الوحدةُ تقرأ وتكتب، فتسكن
هنا لا هناك — وهو الحدُّ نفسه الذي أعلنه `snapshot.py` في رأسه.

## ولا تُعاد كتابةُ بحثٍ من هنا

تكتب هذه الوحدةُ صفًّا واحدًا: **بصمةٌ رُصدت**. ولا تكتب سؤالَ بحثٍ ولا
منهجًا ولا قرارًا — الوحداتُ الأصلية تبقى صاحبةَ الحقيقة (§8، §29)،
والباحثُ صاحبَ القرار.

## وصاحبُ القرار واحد

الموضعُ والفعلُ الرئيسُ والخطواتُ الأخرى **كلُّها من `stages.derive`**.
وكان هنا سجلُّ توصياتٍ ثانٍ يرتّب «التالي» بأولوياتٍ خاصّةٍ به، فكانت
الشاشةُ تقول «المرحلة: المراجع» ويقول زرُّها «حدِّد المنهج». ورحلةٌ
موحَّدة لا تخالف نفسَها، ومحرّكان لا يُصلَحان بموازنةٍ بينهما.

فبقيت من `journey.py` البوّاباتُ الحتمية وحدَها — سؤالٌ مختلفٌ في نوعه
(«ما الذي يمكن») لا في ترتيبه، فلا يتنافس مع المراحل.

## ولمَ لا تُحفظ الخطوةُ المقترحة

لأنّها **تُحسب من الحال الراهنة في كلّ طلب**. و`stages.derive` دالّةٌ
خالصة: وقائعُ واحدة تُعطي الجوابَ نفسه في كلّ مرّة، فحفظُه يُنشئ نسخةً
ثانيةً من شيءٍ يُشتقّ.

**والتقادمُ الذي يُخشى منه بنيويٌّ هنا لا جدوليّ.** المخوفُ أن يقرأ
الباحثُ «شغّل تحليلًا» بعد حذف البيانات؛ وذلك يقع لو حُفظت التوصيةُ وعُرضت
لاحقًا. وما دامت تُحسب من الحال الراهنة فلا توصيةَ تعيش لتَبْلى: يُعاد
الحسابُ على ما هو قائم، فتختفي وحدَها.

وقد كان هنا جدولُ توصياتٍ ووسمُ تقادم، فأُسقطا في مراجعةٍ معمارية قبل
الدمج: الجدولُ كان يُكتب ولا يُقرأ إلا على نفسه. والتاريخُ — «أوصت
المنصّةُ بكذا تحت البصمة F1» — مراقبةٌ وتدقيق، تُبنى حين يُبنى ما
يستهلكها.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research_brain import ResearchContextSnapshot
from ...research_brain import fingerprint, journey, stages
from . import stage_reader
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


def fingerprint_of(snapshot: ProjectSnapshot,
                   stage_facts: stages.StageFacts | None = None) -> str:
    """بصمةُ هذه اللقطة — بالصيغة الواحدة لا بصيغةٍ محليّة.

    **ووقائعُ المراحل تدخلها.** فلقطةُ التقييم تخدم القواعدَ العلمية ولا
    تقرأ مصفوفةَ الدراسات ولا الأدواتِ ولا المخطوطات؛ والرحلةُ تقرؤها
    كلَّها. فبصمةٌ بلا هذه تقول «لم يتغيّر شيءٌ ذو معنى» عن تغيّرٍ نقل
    الباحثَ مرحلةً كاملة — وقد أمسك ذلك فحصٌ على قاعدةٍ حيّة.
    """
    return fingerprint.of(
        snapshot.assessment, project_id=str(snapshot.project_id),
        contradiction_keys=[row.claim_id for row in snapshot.contradictions],
        stage_facts=asdict(stage_facts) if stage_facts is not None else None)


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


class JourneyOutcome:
    """جوابُ المنسّق كاملًا — ولا يُبنى إلا من `advance`."""

    __slots__ = ("context_fingerprint", "snapshot_row", "capabilities", "facts",
                 "stages", "stage_facts")

    def __init__(self, *, context_fingerprint: str,
                 snapshot_row: ResearchContextSnapshot,
                 capabilities: tuple[journey.Capability, ...],
                 facts: journey.JourneyFacts,
                 stages: stages.JourneyStages,
                 stage_facts: stages.StageFacts) -> None:
        self.context_fingerprint = context_fingerprint
        self.snapshot_row = snapshot_row
        #: البوّاباتُ الحتمية وحدَها — **ولا سجلَّ توصياتٍ ثانيًا**.
        self.capabilities = capabilities
        self.facts = facts
        #: **صاحبةُ القرار**: منها الموضعُ والفعلُ الرئيسُ والخطواتُ الأخرى.
        self.stages = stages
        self.stage_facts = stage_facts


async def advance(session: AsyncSession, *, tenant_id: uuid.UUID,
                  snapshot: ProjectSnapshot) -> JourneyOutcome:
    """المسارُ كاملًا: لقطة ← بصمة ← رصد ← قواعد.

    **ولا نموذجَ في شيءٍ من هذا** (§30). فلو سقط المزوّدُ كلُّه لبقي هذا
    عاملًا: الحالُ تُقرأ، والخطوةُ التالية تُقال، وتاريخُ البصمات يُحفظ.
    """
    _report_rules, report = assess(snapshot)
    facts = facts_of(snapshot, report)

    # **ووقائعُ المراحل تُقرأ من الوحدات صاحبةِ الحقيقة**، لا من لقطة
    # التقييم: تلك تخدم القواعد العلمية، وهذه تخدم موضعَ الباحث من رحلته —
    # ومصدرٌ واحد يخدم الغرضين يلوي أحدَهما.
    #
    # وتُقرأ **قبل** البصمة لأنّها جزءٌ منها.
    stage_facts = await stage_reader.read(
        session, tenant_id=tenant_id, project_id=snapshot.project_id)
    current = fingerprint_of(snapshot, stage_facts)

    snapshot_row = await record_snapshot(
        session, tenant_id=tenant_id, snapshot=snapshot, context_fingerprint=current)

    return JourneyOutcome(
        context_fingerprint=current, snapshot_row=snapshot_row,
        capabilities=journey.capabilities(facts), facts=facts,
        stages=stages.derive(stage_facts, project_id=str(snapshot.project_id)),
        stage_facts=stage_facts)


__all__ = ["JourneyOutcome", "advance", "facts_of", "fingerprint_of", "record_snapshot"]
