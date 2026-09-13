"""ما الذي **يمكن** فعله الآن | The deterministic capability gates (Wave 2-A §24, §41).

**وهذا الملفّ يُجيب عن سؤالٍ واحد**، وكان يُجيب عن اثنين.

    ما الذي **يمكن** فعله الآن؟      حتميّ — يُقرأ من حال البحث   ← هنا
    ما الذي **يُستحسن** فعله تاليًا؟  موضعُ الباحث من رحلته      ← `stages.py`

والفرقُ ليس تنميقًا. «لا يمكن تشغيل تحليلٍ بلا بيانات» واقعةٌ يقرؤها أيُّ
قارئٍ من الصفوف نفسها فيخرج بالجواب نفسه؛ وهي ما يبقى هنا.

## ولمَ سقط سجلُّ التوصيات من هذا الملفّ

كان فيه سجلُّ قواعدَ يرتّب «الخطوة التالية» بأولوياتٍ خاصّةٍ به — مستقلّةٍ
عن ترتيب المراحل في `stages.py`. فوقع تناقضٌ حقيقيّ يراه الباحث:

    المرحلة الحالية : المراجع
    والزرُّ يقول    : حدِّد المنهج

**ورحلةٌ موحَّدة لا تخالف نفسَها.** ومحرّكان للقرار لا يُصلَحان بموازنةِ
أولوياتٍ بينهما — يُصلَحان بأن يبقى واحد. فصار الفعلُ الرئيس **نداءَ
المرحلة الحاليّة** بالبناء (`JourneyStages.primary`)، ولا يمكن أن يفترقا
لأنّهما شيءٌ واحد.

وبقيت هنا البوّاباتُ الحتمية: سؤالٌ مختلفٌ في نوعه لا في ترتيبه، ولا
يتنافس مع المراحل.

**ولا حالةَ خاصّةً برسالة هنا.** الحدُّ `project_id` وحده (§75): بحثٌ نشأ
من فكرة، أو من رسالة، أو من مجموعة بيانات، أو من ورقةٍ مرفوعة — كلُّها
تُقرأ بالقواعد نفسها. ولا `thesis_id` ولا `mining_state` ولا مفردةً من
مفردات مركز الرسائل في هذا الملف، وعقدُ الاستيراد في `pyproject.toml`
يحرس ذلك بنيويًّا لا اتفاقًا.

## ولا نسبةَ إنجاز

لا «٧٣٪ مكتمل» (§45). النسبةُ تُخترع مقامًا لا وجود له: كم خطوةً في بحثٍ
كيفيّ استكشافيّ؟ فتُسمّى الحالُ بأسمائها — «لا سؤال بحث»، «المنهج محدَّد»،
«لا تحليل بعد» — وهي أصدقُ وأنفعُ معًا.

## والقاعدة تُعلن سببها

كلُّ فعلٍ مقترح يحمل `reason_ar`/`reason_en` و`evidence_refs`: **لمَ** قيل،
و**ممّ** قُرئ (§26). و«الذكاء الاصطناعي يقترح كذا» ليس سببًا — ولا نموذجَ
يُستدعى في هذا الملف أصلًا.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .ontology import EntityKind, ResearchGraph


@dataclass(frozen=True, slots=True)
class JourneyFacts:
    """وقائعُ البحث كما تُقرأ من اللقطة — **عدٌّ لا تفسير**.

    تُشتقّ من `ResearchGraph` وحدها، فتُختبر كلُّ قاعدةٍ بلا قاعدة بيانات
    ولا جلسة — وهو الحدُّ الذي تقوم عليه هذه الحزمة كلُّها.
    """

    counts: dict[str, int] = field(default_factory=dict)
    ids: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: حقولُ «ما نعرفه» التي تنتظر مراجعةً.
    needs_review: tuple[str, ...] = ()
    #: تعارضاتٌ **مسجَّلة** في البيانات — لا مستنبَطة (§17).
    contradictions: tuple[str, ...] = ()
    #: أقسامُ المخطوطة التي فيها نصّ.
    written_sections: tuple[str, ...] = ()
    #: **حجمُ العيّنة مسجَّلٌ فعلًا** — لا مجرّدُ وجودِ كيانِ عيّنة.
    #:
    #: والفرقُ ليس تدقيقًا: الجسرُ يُنشئ كيانَ `Sample` لكلّ منهجٍ مسجَّل
    #: **ولو كان الحجمُ غيرَ مسجَّل** (يضع `missing()` في موضعه). فقاعدةٌ
    #: تسأل «أثمّة عيّنة؟» تُجاب بنعم دائمًا بمجرّد وجود منهج، فلا تُطلق
    #: أبدًا — وهو عطبُ حارسٍ ميت: موجودٌ في السجلّ، لا يحرس شيئًا.
    sample_size_recorded: bool = False

    def has(self, kind: EntityKind) -> bool:
        return self.counts.get(kind.value, 0) > 0

    def count(self, kind: EntityKind) -> int:
        return self.counts.get(kind.value, 0)

    def refs(self, *kinds: EntityKind) -> tuple[str, ...]:
        """سندُ الحكم: معرّفاتُ ما قُرئ — مرتَّبةً فلا يتغيّر الجوابُ بترتيب."""
        out: list[str] = []
        for kind in kinds:
            out.extend(self.ids.get(kind.value, ()))
        return tuple(sorted(out))


def read_facts(graph: ResearchGraph, *,
               needs_review: Iterable[str] = (),
               contradictions: Iterable[str] = (),
               written_sections: Iterable[str] = ()) -> JourneyFacts:
    """يقرأ الرسمَ عدًّا — ولا يحكم."""
    counts: dict[str, int] = {}
    ids: dict[str, list[str]] = {}
    sized = False
    for entity in graph.entities:
        key = entity.kind.value
        counts[key] = counts.get(key, 0) + 1
        ids.setdefault(key, []).append(entity.id)
        size = getattr(entity, "size", None)
        if size is not None and getattr(size, "is_known", False):
            sized = True
    return JourneyFacts(
        sample_size_recorded=sized,
        counts=counts,
        ids={k: tuple(sorted(v)) for k, v in ids.items()},
        needs_review=tuple(sorted(needs_review)),
        contradictions=tuple(sorted(contradictions)),
        written_sections=tuple(sorted(written_sections)),
    )


# ═══════════════ البوّابات الحتمية — ما **يمكن** فعله ═══════════════

class Capability(BaseModel):
    """بوّابةٌ حتمية: **يمكن** أو **لا يمكن**، ومعها السبب.

    ولا نموذجَ يُسأل عنها (§24). «هل تكفي هذه البيانات لتحليل؟» سؤالٌ
    جوابُه في الصفوف، ونموذجٌ يُجيب عنه يُجيب أحيانًا بنعم وأحيانًا بلا
    على المُدخل نفسه — فيصير حاجزًا لا يُبنى عليه منع.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str = Field(min_length=1)
    allowed: bool
    blocking_reasons: tuple[str, ...] = ()

    def model_post_init(self, _context: object) -> None:
        if not self.allowed and not self.blocking_reasons:
            raise ValueError(f"{self.key}: منعٌ بلا سبب")
        if self.allowed and self.blocking_reasons:
            raise ValueError(f"{self.key}: سببُ منعٍ مع إذن")


#: رموزُ المنع — ثابتةٌ للآلة، وتُترجَم في طبقة العرض (§81).
NO_QUESTION: Final = "research_question_missing"
NO_METHOD: Final = "method_not_selected"
NO_DATASET: Final = "dataset_missing"
NO_ANALYSIS: Final = "analysis_not_run"
NO_FINDING: Final = "no_findings_recorded"
NO_SOURCE: Final = "no_sources_linked"


def capabilities(facts: JourneyFacts) -> tuple[Capability, ...]:
    """البوّاباتُ الأربع — وكلُّها تُقرأ من الوقائع وحدها."""

    def gate(key: str, *reasons: tuple[bool, str]) -> Capability:
        blocking = tuple(code for failed, code in reasons if failed)
        return Capability(key=key, allowed=not blocking, blocking_reasons=blocking)

    return (
        # تحليلٌ بلا بياناتٍ لا يقع — مهما اقترح مقترح.
        gate("run_analysis", (not facts.has(EntityKind.DATASET), NO_DATASET)),
        # نتيجةٌ بلا تشغيلةٍ أنتجتها اختلاق — وهي `RB-FABRICATION-01` نفسها.
        gate("record_finding", (not facts.has(EntityKind.ANALYSIS), NO_ANALYSIS)),
        # ادّعاءٌ بلا مصدرٍ مربوطٍ بالبحث لا يُسنَد.
        gate("support_claim", (not facts.has(EntityKind.SOURCE), NO_SOURCE)),
        # وقسمُ النتائج لا يُصاغ قبل أن توجد نتيجة.
        gate("draft_results", (not facts.has(EntityKind.FINDING), NO_FINDING)),
    )




__all__ = [
    "Capability", "JourneyFacts",
    "NO_ANALYSIS", "NO_DATASET", "NO_FINDING", "NO_METHOD", "NO_QUESTION", "NO_SOURCE",
    "capabilities", "read_facts",
]
