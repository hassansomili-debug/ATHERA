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
#:
#: **والعنوانُ حقلٌ بلغتين.** كان هذا السطر `KEY_TITLE = "title_ar"` وحده،
#: فكان الدليلُ الإنجليزيّ غيرَ مرئيٍّ للقرار الكنسيّ أصلًا: رسالةٌ
#: إنجليزية عنوانُها معتمَدٌ ومتحقَّق تُقرأ «بلا عنوان»، فتُعلَّق مقترحاتُها
#: المعنونة ويُختم التنقيبُ مكتملًا بصفر فرص. وهو صدقٌ في الوصف عن عطبٍ
#: في القراءة — وهذا موضعُه.
KEY_TITLE_AR: Final = "title_ar"
KEY_TITLE_EN: Final = "title_en"
TITLE_KEYS: Final[tuple[str, ...]] = (KEY_TITLE_AR, KEY_TITLE_EN)

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
    TITLE_KEYS + (KEY_QUESTIONS, KEY_HYPOTHESES, KEY_CONSTRUCTS, KEY_INSTRUMENTS)
    + RESULT_KEYS + SAMPLE_KEYS
)

# ═════════ قناتان لا تُخلطان: ما يُنشئ فرصةً، وما يُسمّيها ═════════
#
# **هذا هو قلبُ الإصلاح، ويُكتب صريحًا لئلّا يذوب.**
#
# الدليلُ العلميّ (سؤالٌ، فرضية، بناء، أداة، نتيجة، عيّنة) هو **وحده** ما
# يُنشئ فرصةَ نشر. والعنوانُ لا يُنشئ شيئًا أبدًا: هو تسميةٌ تُلصق بمقترحٍ
# قام على دليلٍ آخر. فرسالةٌ لا يُعرف عنها إلّا عنوانُها ليست فرصةَ نشرٍ
# مكتشَفة، مهما بلغت ثقةُ ذلك العنوان.
#
# ولذلك قناتان:
#
#   • **قناةُ الإنشاء** — حقائقُ `AUTO_ELIGIBLE` وحدها، وهي التي تُعدّ في
#     `eligible_facts_used` فتفتح بابَ التنقيب أصلًا.
#   • **قناةُ التسمية** — قد تصل إليها حقيقةٌ `SUPPORT_ONLY` مؤصَّلة. تُسمّي
#     ولا تُعَدّ، فلا تفتح بابًا ولا تُحرّك ختمًا.
#
# ومن قرأ هذا الملفّ بعد سنة فليقرأ هذا الحدَّ قبل أن يوسّع القناة الثانية.

#: لغةُ العنوان — **تُحفظ ولا تُترجم**، ولا يُكتب عنوانٌ في عمود لغةٍ أخرى.
LANG_AR: Final = "ar"
LANG_EN: Final = "en"

_LANGUAGE_OF_KEY: Final[dict[str, str]] = {KEY_TITLE_AR: LANG_AR, KEY_TITLE_EN: LANG_EN}

#: مصدرُ العنوان المختار — يُسجَّل في التدقيق كما هو.
TITLE_SOURCE_NONE: Final = "none"
TITLE_SOURCES: Final[tuple[str, ...]] = (
    "approved_title_ar", "approved_title_en",
    "auto_title_ar", "auto_title_en",
    "support_context_title_ar", "support_context_title_en",
    TITLE_SOURCE_NONE,
)


@dataclasses.dataclass(frozen=True, slots=True)
class CanonicalTitle:
    """العنوانُ المختار — **ومعه صراحةً: أيُنشئ فرصةً أم يُسمّيها فقط؟**"""

    text: str
    #: `ar` أو `en` — لغةُ الحقل الذي جاء منه، بلا ترجمة.
    language: str
    #: واحدٌ من `TITLE_SOURCES`.
    source: str
    fact_id: uuid.UUID | None
    #: **`False` لعنوان السياق.** والاسمُ صريحٌ عمدًا: من يقلبه إلى `True`
    #: يقلب معه حدًّا علميًّا، فليقلبه وهو يعلم.
    is_scientific_evidence: bool

    @property
    def column(self) -> str:
        """عمودُ الرسالة الذي يخصّ هذه اللغة — ولا يُكتب في سواه."""
        return "title_ar" if self.language == LANG_AR else "title_en"

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
    #: العنوانُ الكنسيّ المختار بالأسبقيّة، أو `None`.
    title: CanonicalTitle | None
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
        """**وجودُ حقائقَ مؤهَّلة، لا وجودُ فرص.** والفرقُ بينهما خبران.

        وعنوانُ السياق لا يُعَدّ هنا: `SUPPORT_ONLY` خارجُ `used` أصلًا،
        فرسالةٌ لا دليلَ فيها إلّا عنوانٌ ضعيفُ الثقة لا تُنقَّب.
        """
        return self.eligible_facts_used > 0

    @property
    def title_source(self) -> str:
        return self.title.source if self.title else TITLE_SOURCE_NONE

    # ── اسمان قديمان يبقيان للتوافق ──
    #
    # **ودلالتُهما كما كانت بالضبط**: عنوانٌ من قناة الإنشاء وحدها. فعنوانُ
    # السياق لا يظهر فيهما، ولا يُقرأ أحدُهما «اعتمده الباحث» — لم يكن كذلك
    # قطّ، وهو اسمٌ سبق دلالتَه.
    @property
    def approved_title(self) -> str | None:
        return self.title.text if self.title and self.title.is_scientific_evidence else None

    @property
    def approved_title_fact_id(self) -> uuid.UUID | None:
        return self.title.fact_id if self.title and self.title.is_scientific_evidence else None


def _select_title(
    verdicts: dict[uuid.UUID, "policy.Verdict"],
    by_id: dict[uuid.UUID, FactCandidate],
    texts_by_id: dict[uuid.UUID, list[str]],
) -> CanonicalTitle | None:
    """عنوانٌ واحد بأسبقيّةٍ حتميّة — **ولا يُترجَم ولا يُختلق**.

    والترتيب:

      ‏(أ) عنوانٌ اعتمده الباحثُ وتحقّقت ذاكرتُه — بأيّ لغة.
      ‏(ب) عنوانٌ آليٌّ مؤهَّل (`AUTO_ELIGIBLE`) — بأيّ لغة.
      ‏(ج) عنوانٌ `SUPPORT_ONLY` مؤصَّل — **للسياق والتسمية وحدهما**، ولا
          يُنشئ فرصةً بحال.

    وداخل الطبقة الواحدة تُقدَّم العربية ثمّ الإنجليزية: المنتجُ عربيُّ
    الأصل، والترتيبُ يجب أن يكون حتميًّا لا رهنَ ترتيبِ صفوفٍ في استعلام.

    و`SUPPORT_ONLY` لا تبلغ هذا الموضع إلّا مؤصَّلةً: التأصيلُ حدٌّ سابقٌ
    على التصنيف، وغيرُ المؤصَّل يخرج `EXCLUDED` قبل أن يُصنَّف داعمًا.
    """
    def pick(match) -> CanonicalTitle | None:
        for key in TITLE_KEYS:
            for fact_id, verdict in verdicts.items():
                candidate = by_id[fact_id]
                if (candidate.field_key or "") != key or not match(verdict):
                    continue
                texts = texts_by_id[fact_id]
                if not texts or not texts[0].strip():
                    continue
                language = _LANGUAGE_OF_KEY[key]
                evidence = verdict.eligible
                prefix = ("approved" if verdict.from_human
                          else "auto" if evidence else "support_context")
                return CanonicalTitle(
                    text=texts[0], language=language,
                    source=f"{prefix}_title_{language}", fact_id=candidate.id,
                    is_scientific_evidence=evidence,
                )
        return None

    return (pick(lambda v: v.eligible and v.from_human)
            or pick(lambda v: v.eligible and not v.from_human)
            or pick(lambda v: v.classification == policy.SUPPORT_ONLY))


def _texts(candidate: FactCandidate) -> list[str]:
    """قيمُ الحقيقةِ نصًّا — **والتطبيعُ في `fact_eligibility` وحده**.

    ونسختان من قاعدةِ قراءةٍ تتباعدان: تُشدَّد إحداهما ويبقى البابُ مفتوحًا
    من الأخرى. فتُفوَّض هنا ولا تُعاد كتابتها.
    """
    return policy.usable_texts(candidate)


async def load(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
    file_id: uuid.UUID | None,
) -> CanonicalEvidence:
    """يصنّف حقائقَ هذه الرسالة، ويبني `ThesisFacts` من المؤهَّل وحده."""
    empty = CanonicalEvidence(
        facts=miner.ThesisFacts(thesis_id=str(thesis_id)),
        eligible_facts_used=0, approved_verified_used=0, title=None,
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

    # ── الأثرُ الذي يملك الرسالة هو الأثرُ **ذو الصلة بالتنقيب** ──
    #
    # **وبياناتُ الوصف وحدها لا تحجب المسارَ القديم.** رسالةٌ قديمة رُفع
    # ملفُّها فاستُخرج منه `page_count` و`source_filename` لا تصير بذلك
    # «حديثةً محجوبة»: لا شيء ممّا استُخرج منها يُنقَّب أصلًا. وحجبُها حينئذٍ
    # يمنع تنقيبًا مشروعًا بحجّة أثرٍ لا يمتّ إليه بصلة.
    mining_relevant = any(
        (candidate.field_key or "") in READ_KEYS for candidate, _m, _c, _r in rows)
    if not mining_relevant:
        return empty

    scope = policy.SCOPE_UNKNOWN
    for candidate, _m, _chunk, run in rows:
        if (candidate.field_key or "") not in READ_KEYS:
            continue
        if run is not None:
            candidate_scope = policy.processing_scope(run.status)
            if candidate_scope == policy.SCOPE_ADVANCED:
                scope = candidate_scope
                break
            scope = candidate_scope

    verdicts: dict[uuid.UUID, policy.Verdict] = {}
    by_id: dict[uuid.UUID, FactCandidate] = {}
    texts_by_id: dict[uuid.UUID, list[str]] = {}
    human_singletons: set[str] = set()

    for candidate, memory, chunk, run in rows:
        texts = _texts(candidate)
        verdict = policy.classify(
            candidate, tenant_id=tenant_id, file_id=file_id,
            run=run, chunk=chunk, memory=memory, known_fields=READ_KEYS,
            texts=texts,
        )
        verdicts[candidate.id] = verdict
        by_id[candidate.id] = candidate
        texts_by_id[candidate.id] = texts
        # **والإبطالُ للمفرد وحده.** انظر الشرح عند تطبيقه.
        if verdict.from_human and (candidate.field_key or "") in policy.SINGLETON_FIELDS:
            human_singletons.add(candidate.field_key or "")

    # ── الإنسانُ المعتمِد يُبطل الآليَّ: في المفرد وحده ──
    #
    # **والإبطالُ على مستوى الحقل كان أوسعَ من الحقّ.** حقلٌ مفرد كالعنوان
    # لا يحتمل قيمتين، فاعتمادُ الباحثِ فيه يحسمه كلَّه. أمّا حقلٌ متعدّد
    # كالأسئلة فاعتمادُ سؤالٍ واحد **لا يقول شيئًا** عن سؤالٍ آخر مستخرَجٍ
    # صحيحٍ يشاركه المفتاحَ وحده. ومحوُه لمجرّد المشاركة يفقد دليلًا سليمًا.
    #
    # ولا يُبطَل عنصرٌ متعدّدٌ إلّا بهويّةِ عنصرٍ حتميّة — ولا وجود لها في
    # النموذج اليوم. **وعلاقةٌ مجهولة ليست علاقةَ إحلال.**
    for fact_id, verdict in list(verdicts.items()):
        if (verdict.eligible
                and not verdict.from_human
                and (by_id[fact_id].field_key or "") in human_singletons):
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

    # **والعنوانُ يُختار بقناته لا بحلقة الأدلّة.** التقاطُه من الحلقة كان
    # يجعله دليلًا كسائر الأدلّة، وهو ليس كذلك.
    title = _select_title(verdicts, by_id, texts_by_id)

    questions: list[str] = []
    hypotheses: list[str] = []
    variables: list[str] = []
    construct_refs: list[str] = []
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
        # **معرّفُ الحقيقة هو المرجع** — ولا يُصنع معرّفٌ دلاليّ. وقيمٌ عدّة
        # من حقيقةٍ واحدة تتشارك معرّفَها، وذلك صدقٌ لا نقص.
        ref = str(candidate.id)
        key = candidate.field_key

        # ── العنوانُ يُسمّي ولا يُنشئ — **والعدُّ يقع بعد هذا الشرط لا قبله** ──
        #
        # كان `used += 1` يسبق هذا الاستمرار، فيُعَدّ العنوانُ المؤهَّلُ آليًّا
        # دليلًا علميًّا. وأثرُه ليس عدًّا زائدًا وحده: `has_evidence` هي
        # `eligible_facts_used > 0`، فرسالةٌ لا شيءَ فيها إلّا عنوانٌ عاليُ
        # الثقة كانت تُعلن أنّ لديها دليلًا علميًّا كنسيًّا — ويمضي التنقيبُ
        # على `evidence_basis="canonical"` بلا نتيجةٍ ولا سؤالٍ ولا بناء.
        #
        # وحاشيةُ `has_evidence` كانت تقول إنّ «عنوانَ السياق لا يُعَدّ هنا»،
        # وهي صادقةٌ في `SUPPORT_ONLY` وحده — أمّا العنوانُ المؤهَّلُ آليًّا
        # فكان يُعَدّ. فالقاعدةُ المكتوبة في المنتج — **العنوانُ يسمّي الفرصةَ
        # ولا يُنشئ دليلًا علميًّا** — كانت مخروقةً في هذا السطر بعينه.
        #
        # واختيارُ العنوان لا يُمسّ: قناتُه `_select_title` أعلاه، و`title`
        # يخرج في `CanonicalEvidence` كما كان، ويُسمّي ويُحفظ كما كان.
        if key in TITLE_KEYS:
            continue

        used += 1
        if verdict.reason == "approved_and_verified_by_researcher":
            approved_used += 1
        if key == KEY_QUESTIONS:
            questions.extend(texts)
        elif key == KEY_HYPOTHESES:
            hypotheses.extend(texts)
        elif key == KEY_CONSTRUCTS:
            variables.extend(texts)
            # **ومعرّفُ الحقيقة يُحفظ إلى جانب نصّها** — فالمقترحُ يُسنَد
            # إلى صفٍّ قائم لا إلى عبارةٍ منسوخة.
            construct_refs.append(ref)
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
        title=title.text if title else None,
        title_is_scientific_evidence=bool(title and title.is_scientific_evidence),
        questions=tuple(dict.fromkeys(questions)),
        hypotheses=tuple(dict.fromkeys(hypotheses)),
        results=tuple(dict.fromkeys(results)),
        instruments=tuple(dict.fromkeys(instruments)),
        variables=tuple(dict.fromkeys(variables)),
        construct_refs=tuple(dict.fromkeys(construct_refs)),
        sample_ids=tuple(dict.fromkeys(sample_ids)),
        # **الثيمةُ ليست مرحلةَ دراسة.** الثيماتُ تُغذّي النتائج أعلاه.
        qualitative_phases=(),
        null_result_ids=tuple(dict.fromkeys(null_result_ids)),
        # **ولا نشرَ يُدّعى بلا رابطةِ نشرٍ حقيقية.**
        published_result_ids=(),
    )
    return CanonicalEvidence(
        facts=facts, eligible_facts_used=used, approved_verified_used=approved_used,
        title=title, has_canonical_footprint=True, processing_scope=scope,
        counts=counts, conflicts_detected=conflicts,
        facts_withheld_for_conflict=withheld, reasons=reasons,
    )
