"""خطة التحليل وقفلها | Analysis plan and its lock (§9 بوابة G7، §51.8).

§9 G7: «اعتماد الاختبارات قبل التنفيذ». عند الاعتماد تُجمَّد قائمة الاختبارات
بتجزئة، فيصير أي تشغيل قابلًا للمقارنة بما وُعد به.

والقرار الدقيق: تشغيل اختبار خارج الخطة **ليس ممنوعًا** — العلم يحتاج
استكشافًا — لكنه يُوسم `exploratory` ويُعلَن في المخرَج. §51.8 تمنع «إعادة
التحليل بقصد مطاردة الدلالة»، والمنع المطلق يدفع إلى التحايل بينما الإعلان
الإلزامي يجعل الاستكشاف مشروعًا ومرئيًا.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, field

from .vocab import TEST_KINDS


class PlanError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PlannedTest:
    test_key: str
    test_kind: str
    variables: tuple[str, ...]
    hypothesis_id: str | None = None
    note_ar: str | None = None

    def __post_init__(self) -> None:
        if self.test_kind not in TEST_KINDS:
            raise PlanError(f"unknown test kind: {self.test_kind}")
        if not self.test_key.strip():
            raise PlanError("a planned test needs a stable key")

    def signature(self) -> str:
        return json.dumps(
            {"key": self.test_key, "kind": self.test_kind,
             "variables": sorted(self.variables), "hypothesis": self.hypothesis_id},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        )


@dataclass(slots=True)
class AnalysisPlan:
    plan_id: str
    tests: list[PlannedTest]
    approved_at: dt.datetime | None = None
    approved_by: str | None = None
    lock_hash: str | None = None

    @property
    def is_locked(self) -> bool:
        return self.lock_hash is not None

    def compute_hash(self) -> str:
        payload = "|".join(sorted(test.signature() for test in self.tests))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def approve(self, *, by: str, at: dt.datetime) -> None:
        """بوابة G7 — الاعتماد يجمّد القائمة ويسجّل فاعله."""
        if self.is_locked:
            raise PlanError("this plan is already locked; create a new version instead")
        if not self.tests:
            raise PlanError("an empty plan cannot be approved (§9 G7)")
        self.lock_hash = self.compute_hash()
        self.approved_by = by
        self.approved_at = at

    def has_drifted(self) -> bool:
        """هل عُدِّلت الخطة بعد قفلها؟ التعديل الصامت هو ما نمنعه."""
        return self.is_locked and self.compute_hash() != self.lock_hash


@dataclass(slots=True)
class TestClassification:
    test_key: str
    origin: str          # planned | exploratory
    reason_ar: str
    reason_en: str


@dataclass(slots=True)
class PlanCompliance:
    classifications: list[TestClassification]
    planned_not_run: list[str] = field(default_factory=list)

    @property
    def exploratory_keys(self) -> list[str]:
        return [c.test_key for c in self.classifications if c.origin == "exploratory"]

    @property
    def requires_disclosure(self) -> bool:
        """§51.8 — وجود استكشاف أو اختبار مخطط لم يُشغَّل يستوجب إفصاحًا."""
        return bool(self.exploratory_keys) or bool(self.planned_not_run)


def classify_run(plan: AnalysisPlan, executed_test_keys: list[str]) -> PlanCompliance:
    """يقارن ما نُفِّذ بما اعتُمد — ولا يمنع، بل يُعلن."""
    if not plan.is_locked:
        raise PlanError("a run must reference an approved (locked) plan (§9 G7)")
    if plan.has_drifted():
        raise PlanError("the plan changed after approval; re-approve before running")

    planned = {test.test_key for test in plan.tests}
    executed = list(dict.fromkeys(executed_test_keys))

    classifications = [
        TestClassification(
            test_key=key,
            origin="planned" if key in planned else "exploratory",
            reason_ar=("اختبار معتمد في خطة التحليل." if key in planned
                       else "اختبار خارج الخطة المعتمدة — يُعلَن كاستكشافي (§51.8)."),
            reason_en=("Test approved in the analysis plan." if key in planned
                       else "Test outside the approved plan — disclosed as exploratory (§51.8)."),
        )
        for key in executed
    ]
    return PlanCompliance(
        classifications=classifications,
        planned_not_run=sorted(planned - set(executed)),
    )
