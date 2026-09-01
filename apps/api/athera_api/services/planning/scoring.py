"""جهوزية الأدلة | Evidence readiness (S5D §15، §16).

**سؤالٌ واحد لا غيره:** «كم هذه الفرصة جاهزة للتطوير من الأدلة التي بين
أيدينا؟» ولا تُجيب أبدًا عن «كم احتمال أن تقبلها مجلة؟» — ذلك سؤالٌ لا تملك
أثيرا بيانات الإجابة عنه، واختراع رقم له يبيع للباحث يقينًا لا يملكه أحد.

ومستقلّة عن `readiness_score` القائم في `services/thesis/readiness.py`: ذاك
يقيس جهوزية **التحويل إلى مشروع** بثمانية مكوّنات فيها الجدة وملاءمة المجلة،
وهما ما لا يُقاس والسجل مغلق. فلا يُمسّ، ولا يُعاد تعريفه.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .context import ResearchContext

# أبعادٌ **كلها مشتقّة من الأدلة الموجودة** — ولا بُعد خارجي فيها.
DIMENSIONS: Final[dict[str, tuple[int, str, str]]] = {
    "evidence_sufficiency": (30, "كفاية الأدلة", "Evidence sufficiency"),
    "question_clarity": (20, "وضوح السؤال", "Question clarity"),
    "methodological_feasibility": (20, "جدوى المنهج", "Methodological feasibility"),
    "results_availability": (20, "توفّر النتائج", "Results availability"),
    "distinctiveness": (10, "تميّزها عن أخواتها", "Distinctiveness"),
}


@dataclass(frozen=True, slots=True)
class Dimension:
    key: str
    weight: int
    ratio: float
    label_ar: str
    label_en: str

    @property
    def points(self) -> float:
        return round(self.weight * self.ratio, 2)


@dataclass(frozen=True, slots=True)
class EvidenceReadiness:
    score: float
    dimensions: tuple[Dimension, ...]
    missing: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "dimensions": [
                {"key": d.key, "weight": d.weight, "ratio": d.ratio,
                 "points": d.points, "label_ar": d.label_ar, "label_en": d.label_en}
                for d in self.dimensions
            ],
            "missing": list(self.missing),
            # يُقال صراحةً في المخرَج نفسه، فلا يُقرأ رقمًا آخر.
            "means": "readiness of the evidence, not journal acceptance",
        }


def compute(context: ResearchContext, proposal, *, overlap_max: float | None = None,
            ) -> EvidenceReadiness:
    """يحسب من اللقطة والمقترح — بلا أي مدخل خارجي.

    و`overlap_max` أعلى تداخل مع فرصة أخرى، من محرّك التداخل القائم.
    """
    roles = {i.role for i in context.items}
    used = [r for r in (proposal.evidence_roles or []) if r in roles]

    sufficiency = min(len(used) / 4.0, 1.0) if used else 0.0
    question = 1.0 if len((proposal.research_question_ar or "").strip()) >= 25 else 0.5
    method = 1.0 if {"methodology", "sample"} & roles else 0.0
    results = 1.0 if "result" in roles else 0.0
    # التميّز عكس التداخل — و«لم يُحسب» ليس صفرًا: يُترك محايدًا.
    distinct = 1.0 if overlap_max is None else max(0.0, 1.0 - overlap_max)

    ratios = {
        "evidence_sufficiency": sufficiency,
        "question_clarity": question,
        "methodological_feasibility": method,
        "results_availability": results,
        "distinctiveness": distinct,
    }
    dimensions = tuple(
        Dimension(key, weight, round(ratios[key], 3), ar, en)
        for key, (weight, ar, en) in DIMENSIONS.items()
    )
    missing = []
    if not method:
        missing.append("methodology_or_sample")
    if not results:
        missing.append("verified_results")
    if sufficiency < 0.5:
        missing.append("more_verified_evidence")
    return EvidenceReadiness(
        score=round(sum(d.points for d in dimensions), 2),
        dimensions=dimensions,
        missing=tuple(missing),
    )
