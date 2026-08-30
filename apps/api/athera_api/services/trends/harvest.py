"""حصاد الإشارات من السجلات | Signal harvesting (§51.11، §14.1).

يحوّل نتائج بحث في سجل خارجي إلى إشارات اتجاه **مؤصَّلة**. كل إشارة تحمل
اسم السجل ومعرّفها فيه وتاريخ نشرها؛ وما ينقصه أحدها يُسقَط ويُعدّ مرفوضًا.

ما لا يفعله هذا الملف: لا يستنتج نمط اكتشاف من ذكاء، ولا يخترع تاريخًا
لسجل بلا سنة نشر. النمط يأتي من ملف المراقبة، والتاريخ من السجل أو لا شيء.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any

from ..literature.registry import RegistryRecord, SourceRegistry

# السجلات المفتوحة وحدها تُحتسب دليلًا؛ أسماؤها هي نفسها في §51.1.
_REGISTRY_TO_SIGNAL_SOURCE: dict[str, str] = {
    "openalex": "openalex",
    "crossref": "crossref",
    "doaj": "doaj",
    "offline": "openalex",
}


@dataclasses.dataclass(frozen=True, slots=True)
class HarvestOutcome:
    candidates: tuple[dict[str, Any], ...]
    rejected: int
    reasons: tuple[str, ...]


def _trend_key(term: str) -> str:
    return term.strip().lower().replace(" ", "-")[:128]


def to_candidate(
    record: RegistryRecord, *, term: str, pattern: str,
) -> dict[str, Any] | None:
    """يحوّل سجلًا إلى إشارة، أو `None` إن نقصه ما يجعله إشارة.

    سنة النشر وحدها ما نملكه من زمن في أغلب السجلات؛ تُثبَّت في أول اليوم من
    السنة ويُصرَّح بذلك في التفصيل، بدل إيهام دقّة يوميّة لا وجود لها.
    """
    source_type = _REGISTRY_TO_SIGNAL_SOURCE.get(record.registry)
    if source_type is None:
        return None
    if not record.registry_id.strip():
        return None
    if record.publication_year is None:
        return None

    observed_at = dt.datetime(record.publication_year, 1, 1, tzinfo=dt.UTC)
    return {
        "trend_key": _trend_key(term),
        "trend_label_ar": term,
        "source_type": source_type,
        "source_id": f"{record.registry}:{record.registry_id}",
        "observed_at": observed_at,
        "pattern": pattern,
        "weight": 1.0,
        "detail_ar": (
            f"«{record.title}» — سنة النشر {record.publication_year}. "
            "الدقة سنوية لأن السجل لا يعطي أكثر."
        ),
    }


async def harvest(
    registry: SourceRegistry,
    *,
    terms: list[str],
    pattern: str = "topic_acceleration",
    limit_per_term: int = 20,
) -> HarvestOutcome:
    """يبحث عن كل مصطلح ويعيد المرشّحين الصالحين وعدد ما سقط ولماذا.

    السقوط يُبلَّغ ولا يُبتلع: «لم نجد شيئًا» و«وجدنا ولم يصلح» حالتان
    مختلفتان تمامًا في قراءة نتيجة الرصد.
    """
    candidates: list[dict[str, Any]] = []
    reasons: list[str] = []
    rejected = 0

    seen: set[str] = set()
    for term in terms:
        if not term.strip():
            continue
        records = await registry.search(term, limit=limit_per_term)
        for record in records:
            candidate = to_candidate(record, term=term, pattern=pattern)
            if candidate is None:
                rejected += 1
                reasons.append(
                    f"{record.registry}:{record.registry_id or '?'} — "
                    "سجل بلا معرّف أو بلا سنة نشر لا يصلح إشارة"
                )
                continue
            key = (candidate["trend_key"], candidate["source_id"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)

    return HarvestOutcome(
        candidates=tuple(candidates), rejected=rejected, reasons=tuple(reasons[:50]),
    )
