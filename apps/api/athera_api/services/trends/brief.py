"""النشرة الاستخباراتية وفحص الجدة التنافسية | §51.9، §51.10.

منطق خالص: ما الذي يدخل النشرة، ومتى يكون التشابه مع عمل منشور **حاجبًا**
لا مجرد ملاحظة.
"""
from __future__ import annotations

import dataclasses
import datetime as dt

from .vocab import BRIEF_CADENCES


class BriefError(Exception):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class BriefItem:
    """بند في النشرة. `evidence_ref` إلزامي: لا بند بلا ما يسنده."""

    item_key: str
    title_ar: str
    evidence_ref: str
    detail_ar: str | None = None

    def __post_init__(self) -> None:
        if not self.evidence_ref.strip():
            raise BriefError("§51.9 — a brief item without an evidence reference is a rumour")


@dataclasses.dataclass(frozen=True, slots=True)
class Brief:
    cadence: str
    period_start: dt.datetime
    period_end: dt.datetime
    new_trends: tuple[BriefItem, ...] = ()
    score_changes: tuple[BriefItem, ...] = ()
    new_cards: tuple[BriefItem, ...] = ()
    alerts: tuple[BriefItem, ...] = ()

    def __post_init__(self) -> None:
        if self.cadence not in BRIEF_CADENCES:
            raise BriefError(f"unknown brief cadence: {self.cadence}")
        if self.period_end <= self.period_start:
            raise BriefError("a brief period must move forward in time")

    @property
    def is_empty(self) -> bool:
        return not (self.new_trends or self.score_changes or self.new_cards or self.alerts)

    @property
    def summary_ar(self) -> str:
        """نشرة فارغة تقول ذلك صراحةً.

        إخفاؤها يجعل الصمت غامضًا: أهو «لا جديد» أم «لم يعمل الرصد»؟
        """
        if self.is_empty:
            return "لا مستجدات في هذه الفترة. الرصد عمل ولم يجد ما يستحق عرضه."
        return (
            f"اتجاهات جديدة: {len(self.new_trends)} · "
            f"تغيّر درجات: {len(self.score_changes)} · "
            f"بطاقات جديدة: {len(self.new_cards)} · "
            f"تنبيهات: {len(self.alerts)}"
        )

    @property
    def summary_en(self) -> str:
        if self.is_empty:
            return "Nothing new this period. Monitoring ran and found nothing worth showing."
        return (
            f"New trends: {len(self.new_trends)} · "
            f"Score changes: {len(self.score_changes)} · "
            f"New cards: {len(self.new_cards)} · Alerts: {len(self.alerts)}"
        )


# §51.10 — عتبتان بيانيتان لا ثوابت مبعثرة.
BLOCKING_SIMILARITY = 0.85
REVIEW_SIMILARITY = 0.60


@dataclasses.dataclass(frozen=True, slots=True)
class NoveltyVerdict:
    similarity: float
    is_blocking: bool
    needs_review: bool
    reason_ar: str
    reason_en: str


def assess_novelty(similarity: float, *, published_source_id: str | None) -> NoveltyVerdict:
    """§51.10 — تشابه عالٍ مع عمل **منشور** يحجب؛ ومع غير المنشور يُراجَع.

    التمييز جوهري: عمل قيد الإعداد في مكان آخر ليس سببًا لإسقاط فكرة، وعمل
    منشور فعلًا يجعل «الجدة» ادعاءً كاذبًا.
    """
    if not 0.0 <= similarity <= 1.0:
        raise BriefError("similarity must be within [0, 1]")

    if similarity >= BLOCKING_SIMILARITY and published_source_id:
        return NoveltyVerdict(
            similarity=similarity, is_blocking=True, needs_review=True,
            reason_ar=f"تشابه {similarity:.2f} مع عمل منشور — الجدة غير قائمة حتى يُحسم الفرق.",
            reason_en=(f"Similarity {similarity:.2f} with published work — novelty does not "
                       "hold until the difference is settled."),
        )
    if similarity >= REVIEW_SIMILARITY:
        return NoveltyVerdict(
            similarity=similarity, is_blocking=False, needs_review=True,
            reason_ar=f"تشابه {similarity:.2f} يستدعي مراجعة بشرية، ولا يحجب وحده.",
            reason_en=(f"Similarity {similarity:.2f} warrants human review; it does not "
                       "block on its own."),
        )
    return NoveltyVerdict(
        similarity=similarity, is_blocking=False, needs_review=False,
        reason_ar=f"تشابه {similarity:.2f} دون عتبة المراجعة.",
        reason_en=f"Similarity {similarity:.2f} is below the review threshold.",
    )
