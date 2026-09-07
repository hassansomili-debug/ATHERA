"""جسرُ المعرفة المعتمَدة | Reviewed knowledge feeds the miner.

**العطب الذي يسدّه هذا الملف.** خطُّ معالجة المستندات الحديث يكتب
`FactCandidate`، ويعتمدها الباحث فتصير `ResearcherMemory` موثقة. والمنقّبُ
كان يقرأ `ThesisSection` و`ThesisResult` وحدهما — وهما جدولان لا يكتبهما
المسارُ الحديث. ‏`ThesisResult` **لا كاتبَ له في التطبيق كلّه**، و`ThesisSection`
يُكتب بمفتاحَين اثنين (`results` و`research_problem`) بينما المنقّب يقرأ
`questions` وهو مفتاحٌ لا يُكتب أبدًا.

فرسالةٌ تُرفع اليوم، ويراجع الباحثُ استخراجَها بصبر ويعتمد حقائقَها، ثم
يضغط «افحص فرص النشر» — فيُجاب بصفر. لا خطأ، ولا رسالة؛ صفرٌ صامت.

**وهذا الملف محوِّلُ قراءةٍ لا نموذجَ مجال.** يبني `ThesisFacts` القائمة من
الحقائق المعتمَدة. ولا يَنسخ `FactCandidate` إلى `ThesisSection` ولا إلى
`ThesisResult`: نسخُ المعرفة بين معماريّتين يُنتج نسختين تتباعدان، ومصدرَ
حقيقةٍ ثانيًا لا أحد يعرف أيّهما الأصل.

## عقدُ الثقة — الدليلُ من اعتمادِ الباحث وحده

لا يدخل شيءٌ إلى المنقّب إلّا إذا اجتمعت أربعة، ولا يكفي بعضُها:

  ١ ‏`FactCandidate.status == "approved"`
  ٢ ويُحَلّ عبر `resulting_memory_id` إلى `ResearcherMemory`
  ٣ وتلك الذاكرة `verification_status == "verified"`
  ٤ و`source_file_id` لها **هو ملفُّ هذه الرسالة بعينه**، والمستأجرُ واحد.

**واستخراجُ النموذج وحده ليس دليلًا معتمَدًا.** المرشّح يبدأ `unverified`
دائمًا؛ والاعتمادُ فعلُ إنسان. ولا تُقبل ذاكرةٌ من ملفٍّ آخر لأنّ نصَّها
يشبه هذه الرسالة — الرابطةُ معرّفُ ملفّ، لا مشابهةُ نصّ.
"""
from __future__ import annotations

import dataclasses
import re
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...models.research import FactCandidate, ResearcherMemory
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
# إلّا بعبارةٍ **تُصرّح** بذلك في الحقيقة التي اعتمدها الباحث.
_NULL_RESULT_MARKERS: Final[re.Pattern[str]] = re.compile(
    r"(غير\s+دال|غيرُ\s+دال|لم\s+تكن\s+دال|لم\s+يكن\s+دال|"
    r"عدم\s+وجود\s+فروق|لا\s+توجد\s+فروق|لا\s+توجد\s+علاقة|"
    r"not\s+statistically\s+significant|not\s+significant|"
    r"no\s+significant\s+(difference|effect|relationship)|null\s+result)",
    re.IGNORECASE,
)


@dataclasses.dataclass(frozen=True, slots=True)
class CanonicalEvidence:
    """ما بُني من الحقائق المعتمَدة — ومعه عددُ ما استُهلك منها."""

    facts: miner.ThesisFacts
    #: عددُ الحقائق المعتمَدة التي دخلت البناء فعلًا.
    approved_facts_used: int
    #: عنوانٌ معتمَد إن وُجد — يُستعمل في الكتابة الخلفية المشروطة.
    approved_title: str | None
    #: معرّفُ حقيقةِ العنوان المعتمَدة — للأثر، بلا نصّ المستند.
    approved_title_fact_id: uuid.UUID | None

    @property
    def has_evidence(self) -> bool:
        """**وجودُ حقائقَ معتمَدة، لا وجودُ فرص.** والفرقُ بينهما خبران.

        فإن لم يعتمد الباحثُ شيئًا بعد فذاك حالٌ يُقال باسمه؛ وإن اعتمد
        ولم يجد المنقّبُ فرصةً فذاك خبرٌ آخر تمامًا — وكلاهما كان يُقرأ
        «صفر».
        """
        return self.approved_facts_used > 0


def _texts(candidate: FactCandidate) -> list[str]:
    """قيمُ الحقيقةِ الواحدة نصًّا — **بلا تقطيعٍ للنثر**.

    والشكلُ المخزون `{"value": …, "extraction_status": …}` و`value` نوعُه
    `Any`: نصٌّ للحقول المفردة، وقائمةٌ للحقول المتعدّدة (`multi=True`).
    ولا تُشطر عبارةٌ واحدة إلى عبارتين لتكثر المقترحات — الكثرةُ المصنوعة
    تُنتج فرصًا لا أصل لها.
    """
    payload = candidate.value if isinstance(candidate.value, dict) else None
    raw = payload.get("value") if payload else None

    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            # عنصرٌ ليس نصًّا ولا رقمًا يُترك — ولا يُخمَّن له تمثيل.
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
    # **العبارةُ التي اعتمدها الباحث** — تُصان حين تعذّرت قراءةُ القيمة.
    statement = (candidate.statement_ar or "").strip()
    return [statement] if statement else []


async def load(
    session: AsyncSession, *, tenant_id: uuid.UUID, thesis_id: uuid.UUID,
    file_id: uuid.UUID | None,
) -> CanonicalEvidence:
    """يجمع الحقائقَ المعتمَدة لهذه الرسالة ويبني منها `ThesisFacts`.

    **ورسالةٌ بلا ملفّ لا معرفةَ معتمَدة لها**: الرابطة كلُّها معرّفُ ملفّ،
    فتُردّ حصيلةٌ فارغة بلا استعلام.
    """
    empty = CanonicalEvidence(
        facts=miner.ThesisFacts(thesis_id=str(thesis_id)),
        approved_facts_used=0, approved_title=None, approved_title_fact_id=None,
    )
    if file_id is None:
        return empty

    # ── الاستعلامُ هو عقدُ الثقة مكتوبًا ──
    #
    # ورابطةُ الذاكرة شرطٌ في الوصل لا فحصٌ بعده: مرشّحٌ «معتمَد» بلا ذاكرة
    # موثقة لا يمرّ، ولا تمرّ ذاكرةُ ملفٍّ آخر.
    rows = (
        await session.execute(
            select(FactCandidate, ResearcherMemory)
            .join(ResearcherMemory, ResearcherMemory.id == FactCandidate.resulting_memory_id)
            .where(
                FactCandidate.tenant_id == tenant_id,
                FactCandidate.file_id == file_id,
                FactCandidate.status == "approved",
                ResearcherMemory.tenant_id == tenant_id,
                ResearcherMemory.verification_status == "verified",
                ResearcherMemory.source_file_id == file_id,
                FactCandidate.field_key.in_(READ_KEYS),
            )
            .order_by(FactCandidate.created_at, FactCandidate.id)
        )
    ).all()
    if not rows:
        return empty

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

    for candidate, _memory in rows:
        texts = _texts(candidate)
        if not texts:
            continue
        used += 1
        # **معرّفُ الحقيقةِ المعتمَدة هو المرجع** — ولا يُصنع معرّفٌ دلاليّ.
        # وقيمٌ عدّة من حقيقةٍ واحدة تتشارك معرّفَها، وذلك صدقٌ لا نقص:
        # مرجعُها واحد، وإليه يعود الأثر.
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
        # **الثيمةُ ليست مرحلةَ دراسة.** الثيماتُ تُغذّي النتائج أعلاه؛
        # و«المرحلة الكيفية» ادّعاءٌ عن تصميم الدراسة لا تُثبته ثيمة.
        qualitative_phases=(),
        null_result_ids=tuple(dict.fromkeys(null_result_ids)),
        # **ولا نشرَ يُدّعى بلا رابطةِ نشرٍ حقيقية.** لا يوجد اليوم حقلٌ
        # معتمَد يثبت أنّ نتيجةً نُشرت، فتبقى فارغة ولا تُخمَّن.
        published_result_ids=(),
    )
    return CanonicalEvidence(
        facts=facts, approved_facts_used=used,
        approved_title=title, approved_title_fact_id=title_fact_id,
    )
