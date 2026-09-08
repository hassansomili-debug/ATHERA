"""جسرُ المعرفة المعتمَدة | Canonical thesis knowledge feeds the miner.

**العطب الذي يسدّه هذا الملف.** خطُّ معالجة المستندات الحديث يكتب
`FactCandidate`. والمنقّبُ كان يقرأ `ThesisSection` و`ThesisResult` وحدهما —
وهما جدولان لا يكتبهما المسارُ الحديث. ‏`ThesisResult` **لا كاتبَ له في
التطبيق كلّه**، و`ThesisSection` يُكتب بمفتاحَين اثنين بينما المنقّب يقرأ
`questions` وهو مفتاحٌ لا يُكتب أبدًا. فرسالةٌ تُرفع اليوم يُجاب صاحبُها
بصفرٍ صامت.

**وهذا الملف محوِّلُ قراءةٍ لا نموذجَ مجال.** يبني `ThesisFacts` القائمة من
الحقائق المؤهَّلة، ولا يَنسخ `FactCandidate` إلى `ThesisSection` ولا إلى
`ThesisResult`: نسخُ المعرفة بين معماريّتين يُنتج نسختين تتباعدان، ومصدرَ
حقيقةٍ ثانيًا لا أحد يعرف أيّهما الأصل.

## السياسةُ تحوّلت: الباحثُ يعتمد العلمَ لا الاستخراج

كان الشرطُ أن يعتمد الباحثُ كلَّ حقيقةٍ بيده. والمبدأ الآن: **الباحثُ يعتمد
القراراتِ العلمية، لا كلَّ استخراجٍ آليٍّ وسيط.** فلم يعد `status ==
"approved"` ولا `resulting_memory_id` شرطًا للحقائق الآليّة.

**والحمايةُ التي كان الاعتمادُ يوفّرها انتقلت كلُّها إلى التصنيف** في
`fact_eligibility.py`. فهو وحده ما يفصل تخمينَ آلةٍ عن فرصةِ نشرٍ محفوظة.

## الأسبقيّة، ولا خلطَ بين معماريّتين

  ١ حقيقةٌ اعتمدها الباحثُ وتحقّقت ذاكرتُها — **أعلى الثقة**.
  ٢ حقيقةٌ آليّةٌ مؤهَّلة (`AUTO_ELIGIBLE`).
  ٣ الجداولُ القديمة — **وحدها حين لا أثرَ حديثًا للرسالة أصلًا**.

**ولا هروبَ إلى القديم حين يُحجب الحديث.** رسالةٌ لها أثرٌ حديث لكنّ حقائقَه
ضعيفةُ الثقة أو متعارضة أو محجوبة: حجبٌ مقصود، وقعَ لسببٍ يُقال. والنزولُ
حينها إلى `ThesisSection` يحوّل الحجبَ المقصود إلى تنزيلٍ صامت — فيُنشر ما
رُفض نشرُه، من بابٍ خلفيّ.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research import DocumentChunk, ExtractionRun, FactCandidate, ResearcherMemory
from . import fact_eligibility as policy
from . import miner

#: مفاتيحُ الكتالوج المقروءة — من `services/document_intelligence/fields.py`.
KEY_TITLE: Final = "title_ar"
KEY_QUESTIONS: Final = "questions"
KEY_HYPOTHESES: Final = "hypotheses"
KEY_CONSTRUCTS: Final = "constructs"
KEY_INSTRUMENTS: Final = "instruments"

#: ثلاثةٌ تُغذّي `results` — والثيمةُ نتيجةٌ لا «مرحلةُ دراسة».
RESULT_KEYS: Final[tuple[str, ...]] = (
    "primary_findings", "hypothesis_results", "qualitative_themes",
)

#: ثلاثةٌ تُغذّي `sample_ids` — **بمعرّفاتِ حقائقها لا بمعرّف الرسالة**.
SAMPLE_KEYS: Final[tuple[str, ...]] = ("population", "sample_size", "sampling")

READ_KEYS: Final[frozenset[str]] = frozenset(
    (KEY_TITLE, KEY_QUESTIONS, KEY_HYPOTHESES, KEY_CONSTRUCTS, KEY_INSTRUMENTS)
    + RESULT_KEYS + SAMPLE_KEYS
)

# ═════════ النتائجُ السالبة: تصريحٌ لا استنتاج ═════════
#
# **الغيابُ ليس نفيًا.** نتيجةٌ لا تذكر دلالةً ليست نتيجةً غيرَ دالّة؛ وقد
# تكون دالّةً ولم يُذكر ذلك في هذه العبارة. فلا يُعدّ شيءٌ نتيجةً سالبة
# إلّا بعبارةٍ **تُصرّح** بذلك في الحقيقة نفسها.
#
# **والفجوةُ محدودةٌ بستّ كلمات عمدًا.** «لم تكن الفروقُ … دالة» نفيٌ صريح
# تفصله كلماتٌ عن موضعه؛ ونفيٌ في أول الفقرة و«دال» في آخرها ليسا عبارةً
# واحدة. فالحدُّ يقرأ الجملة ولا يجمع ما تفرّق.
_NULL_RESULT_MARKERS: Final[re.Pattern[str]] = re.compile(
    r"(?:غيرُ?\s+دال"
    r"|(?:لم\s+تكن|لم\s+يكن|ليست|ليس)(?:\s+\S+){0,6}?\s+دال"
    r"|عدم\s+وجود\s+(?:فروق|علاقة|أثر|تأثير)"
    r"|لا\s+(?:توجد|يوجد)\s+(?:فروق|علاقة|أثر|تأثير|فرق)"
    r"|not\s+(?:statistically\s+)?significant"
    r"|no\s+significant\s+(?:difference|effect|relationship)"
    r"|null\s+result)",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True, slots=True)
class CanonicalEvidence:
    """ما بُني من الحقائق المؤهَّلة، ومعه تشخيصُ ما لم يُبنَ منه."""

    facts: miner.ThesisFacts
    #: عددُ الحقائق المؤهَّلة التي دخلت البناء فعلًا.
    eligible_facts_used: int
    #: منها ما اعتمده الباحثُ وتحقّقت ذاكرتُه — **أعلى الثقة**، ويُعدّ وحده.
    approved_verified_used: int
    approved_title: str | None
    approved_title_fact_id: uuid.UUID | None
    #: **أثرٌ حديثٌ للرسالة** — ولو كان كلُّه مستبعَدًا. وبه يُمنع الهروبُ
    #: إلى الجداول القديمة: الحجبُ المقصود لا يُنزَّل صامتًا.
    has_canonical_footprint: bool
    #: حالُ التشغيل — **محورٌ مستقلّ عن جودة الدليل**.
    processing_scope: str
    counts: dict[str, int]
    conflicts_detected: int
    facts_withheld_for_conflict: int
    #: أسبابُ الاستبعاد وعددُ كلٍّ منها — بلا نصّ مستند.
    reasons: dict[str, int]

    @property
    def has_evidence(self) -> bool:
        """**وجودُ حقائقَ مؤهَّلة، لا وجودُ فرص.** والفرقُ بينهما خبران."""
        return self.eligible_facts_used > 0


def _texts(candidate: FactCandidate) -> list[str]:
    """قيمُ الحقيقةِ الواحدة نصًّا — **بلا تقطيعٍ للنثر**.

    والشكلُ المخزون `{"value": …, "extraction_status": …}` و`value` نوعُه
    `Any`: نصٌّ للحقول المفردة، وقائمةٌ للحقول المتعدّدة. ولا تُشطر عبارةٌ
    واحدة إلى عبارتين لتكثر المقترحات — الكثرةُ المصنوعة تُنتج فرصًا لا
    أصل لها.
    """
    payload = candidate.value if isinstance(candidate.value, dict) else None
    raw = payload.get("value") if payload else None

    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str | int | float) and not isinstance(item, bool):
                text = str(item).strip()
                if text:
                    out.append(text)
    elif isinstance(raw, str | int | float) and not isinstance(raw, bool):
        text = str(raw).strip()
        if text:
            out.append(text)

    if out:
        return out
    statement = (candidate.statement_ar or "").strip()
    return [statement] if statement else []


async def load(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
    file_id: uuid.UUID | None,
) -> CanonicalEvidence:
    """يصنّف حقائقَ هذه الرسالة، ويبني `ThesisFacts` من المؤهَّل وحده."""
    empty = CanonicalEvidence(
        facts=miner.ThesisFacts(thesis_id=str(thesis_id)),
        eligible_facts_used=0, approved_verified_used=0,
        approved_title=None, approved_title_fact_id=None,
        has_canonical_footprint=False, processing_scope=policy.SCOPE_UNKNOWN,
        counts={}, conflicts_detected=0, facts_withheld_for_conflict=0, reasons={},
    )
    # **ورسالةٌ بلا ملفّ لا معرفةَ حديثة لها**: الرابطة كلُّها معرّفُ ملفّ.
    if file_id is None:
        return empty

    # ── تُقرأ كلُّ المرشّحات، لا المعتمَدة وحدها ──
    #
    # والوصلاتُ يسرى: مقطعٌ مفقود أو تشغيلةٌ مفقودة **حالٌ تُصنَّف** لا صفٌّ
    # يختفي. فالاختفاءُ يجعل العطبَ غيابًا لا سببًا.
    rows = (
        await session.execute(
            select(FactCandidate, ResearcherMemory, DocumentChunk, ExtractionRun)
            .outerjoin(ResearcherMemory,
                       ResearcherMemory.id == FactCandidate.resulting_memory_id)
            .outerjoin(DocumentChunk, DocumentChunk.id == FactCandidate.chunk_id)
            .outerjoin(ExtractionRun, ExtractionRun.id == FactCandidate.extraction_run_id)
            .where(FactCandidate.tenant_id == tenant_id,
                   FactCandidate.file_id == file_id)
            .order_by(FactCandidate.created_at, FactCandidate.id)
        )
    ).all()
    if not rows:
        return empty

    scope = policy.SCOPE_UNKNOWN
    for _c, _m, _chunk, run in rows:
        if run is not None:
            candidate_scope = policy.processing_scope(run.status)
            if candidate_scope == policy.SCOPE_ADVANCED:
                scope = candidate_scope
                break
            scope = candidate_scope

    verdicts: dict[uuid.UUID, policy.Verdict] = {}
    by_id: dict[uuid.UUID, FactCandidate] = {}
    texts_by_id: dict[uuid.UUID, list[str]] = {}
    human_fields: set[str] = set()

    for candidate, memory, chunk, run in rows:
        texts = _texts(candidate)
        verdict = policy.classify(
            candidate, tenant_id=tenant_id, file_id=file_id,
            run_status=run.status if run is not None else None,
            chunk=chunk, memory=memory, known_fields=READ_KEYS,
            has_text=bool(texts),
        )
        verdicts[candidate.id] = verdict
        by_id[candidate.id] = candidate
        texts_by_id[candidate.id] = texts
        if verdict.eligible and verdict.reason == "approved_and_verified_by_researcher":
            human_fields.add(candidate.field_key or "")

    # ── الإنسانُ المعتمِد يُبطل الآليَّ في المفهوم نفسه ──
    #
    # **ولا تُخترع علاقةُ إحلالٍ دلاليّة لا يمثّلها النموذج.** الإبطالُ هنا
    # على مستوى الحقل: حقلٌ حسم فيه الباحثُ لا يُغذّيه استخراجٌ لاحق.
    for fact_id, verdict in list(verdicts.items()):
        if (verdict.eligible
                and verdict.reason != "approved_and_verified_by_researcher"
                and (by_id[fact_id].field_key or "") in human_fields):
            verdicts[fact_id] = dataclasses.replace(
                verdict, classification=policy.EXCLUDED,
                reason="superseded_by_researcher_decision")

    # ── التعارضُ المادّيّ: يُحجب المفهومُ وحده، لا الرسالة ──
    conflicts = 0
    withheld = 0
    for field_key in policy.CONFLICT_SENSITIVE_FIELDS:
        eligible_here = [
            fid for fid, v in verdicts.items()
            if v.eligible and (by_id[fid].field_key or "") == field_key
        ]
        shapes = {
            policy.conflict_key(field_key, text)
            for fid in eligible_here for text in texts_by_id[fid]
        }
        if len(shapes) > 1:
            conflicts += 1
            for fid in eligible_here:
                verdicts[fid] = dataclasses.replace(
                    verdicts[fid], classification=policy.REVIEW_REQUIRED,
                    reason="material_conflict_for_concept")
                withheld += 1

    counts: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for verdict in verdicts.values():
        counts[verdict.classification] = counts.get(verdict.classification, 0) + 1
        if verdict.classification != policy.AUTO_ELIGIBLE:
            reasons[verdict.reason] = reasons.get(verdict.reason, 0) + 1

    title: str | None = None
    title_fact_id: uuid.UUID | None = None
    questions: list[str] = []
    hypotheses: list[str] = []
    variables: list[str] = []
    instruments: list[tuple[str, str]] = []
    results: list[tuple[str, str]] = []
    sample_ids: list[str] = []
    null_result_ids: list[str] = []
    used = 0
    approved_used = 0

    for fact_id, verdict in verdicts.items():
        # **المؤهَّلُ وحده يدخل.** لا `SUPPORT_ONLY`، ولا محجوبٌ لتعارض.
        if not verdict.eligible:
            continue
        candidate = by_id[fact_id]
        texts = texts_by_id[fact_id]
        if not texts:
            continue
        used += 1
        if verdict.reason == "approved_and_verified_by_researcher":
            approved_used += 1
        # **معرّفُ الحقيقة هو المرجع** — ولا يُصنع معرّفٌ دلاليّ. وقيمٌ عدّة
        # من حقيقةٍ واحدة تتشارك معرّفَها، وذلك صدقٌ لا نقص.
        ref = str(candidate.id)
        key = candidate.field_key

        if key == KEY_TITLE:
            if title is None:
                title = texts[0]
                title_fact_id = candidate.id
        elif key == KEY_QUESTIONS:
            questions.extend(texts)
        elif key == KEY_HYPOTHESES:
            hypotheses.extend(texts)
        elif key == KEY_CONSTRUCTS:
            variables.extend(texts)
        elif key == KEY_INSTRUMENTS:
            instruments.extend((ref, text) for text in texts)
        elif key in RESULT_KEYS:
            results.extend((ref, text) for text in texts)
            if any(_NULL_RESULT_MARKERS.search(text) for text in texts):
                null_result_ids.append(ref)
        elif key in SAMPLE_KEYS:
            sample_ids.append(ref)

    facts = miner.ThesisFacts(
        thesis_id=str(thesis_id),
        title=title,
        questions=tuple(dict.fromkeys(questions)),
        hypotheses=tuple(dict.fromkeys(hypotheses)),
        results=tuple(dict.fromkeys(results)),
        instruments=tuple(dict.fromkeys(instruments)),
        variables=tuple(dict.fromkeys(variables)),
        sample_ids=tuple(dict.fromkeys(sample_ids)),
        # **الثيمةُ ليست مرحلةَ دراسة.** الثيماتُ تُغذّي النتائج أعلاه.
        qualitative_phases=(),
        null_result_ids=tuple(dict.fromkeys(null_result_ids)),
        # **ولا نشرَ يُدّعى بلا رابطةِ نشرٍ حقيقية.**
        published_result_ids=(),
    )
    return CanonicalEvidence(
        facts=facts, eligible_facts_used=used, approved_verified_used=approved_used,
        approved_title=title, approved_title_fact_id=title_fact_id,
        has_canonical_footprint=True, processing_scope=scope,
        counts=counts, conflicts_detected=conflicts,
        facts_withheld_for_conflict=withheld, reasons=reasons,
    )
