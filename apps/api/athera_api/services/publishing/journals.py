"""طبقات الثقة ومطابقة المجلات | Journal trust tiers and matching (§20).

ثلاثة قرارات تحكم هذا الملف:

1. **الفهرسة تنتهي صلاحيتها.** §20.3 تشترط إعادة التحقق عند أربع نقاط،
   فسجل تحقق أقدم من نافذة السياسة يسقط إلى «يحتاج إعادة تحقق» ولا يُحتسب
   في الطبقة. مجلة كانت في SSCI قبل عامين ليست بالضرورة فيها اليوم.

2. **لا احتمال قبول — بغياب الحقل.** §20.4 تمنع توليده، والضمانة البنيوية
   أقوى من أي فحص نصي: لا يوجد في `JournalMatch` مكان يحمل وعدًا.

3. **أسماء الفهارس بيانات لا كود.** نفس درس Sprint 3: الطبقة تُحسب من
   خرائط فهارس تأتي من السياسة، فلائحة أو مؤسسة أخرى تعمل بلا تعديل.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from .vocab import MATCH_CRITERIA, TRUST_TIERS, VERIFICATION_POINTS

NEEDS_REVERIFICATION = "needs_reverification"


@dataclass(frozen=True, slots=True)
class TierPolicy:
    """§20.2 — أي فهرس يرفع إلى أي طبقة، وكم تبقى صلاحية التحقق.

    كل شيء بيانات: `tier_a_indexes` هي «الفهارس الصارمة» لهذه المؤسسة،
    وليست ثابتًا في الكود.
    """

    policy_id: str
    tier_a_indexes: frozenset[str]
    tier_b_indexes: frozenset[str]
    tier_c_indexes: frozenset[str]
    verification_max_age_days: int
    institution_accepts_peer_reviewed: bool = True
    excluded_publishers: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class IndexingRecord:
    index_name: str
    status: str                     # active | discontinued | unknown
    last_verified_at: dt.datetime


@dataclass(frozen=True, slots=True)
class JournalFacts:
    """§20.1 — ما يلزم لتقدير الطبقة والمطابقة."""

    journal_id: str
    name: str
    indexing: tuple[IndexingRecord, ...] = ()
    publisher: str | None = None
    is_peer_reviewed: bool = True
    is_discontinued: bool = False
    is_suspicious: bool = False
    scope_keywords: frozenset[str] = frozenset()
    recent_article_keywords: frozenset[str] = frozenset()
    accepted_methods: frozenset[str] = frozenset()
    apc_usd: float | None = None
    oa_model: str | None = None
    median_review_days: int | None = None


@dataclass(slots=True)
class IndexAssessment:
    index_name: str
    status: str
    counts: bool
    reason_ar: str
    reason_en: str


@dataclass(slots=True)
class TierAssessment:
    tier: str
    label_ar: str
    label_en: str
    indexes: list[IndexAssessment]
    stale_indexes: list[str] = field(default_factory=list)

    @property
    def meets_strict_wos(self) -> bool:
        """§20.3 — الطبقة A وحدها تحقق الشرط الصارم."""
        return self.tier == "A"


def _is_fresh(record: IndexingRecord, policy: TierPolicy, as_of: dt.datetime) -> bool:
    age_days = (as_of - record.last_verified_at).days
    return age_days <= policy.verification_max_age_days


def assess_tier(facts: JournalFacts, policy: TierPolicy, *, as_of: dt.datetime) -> TierAssessment:
    """يحسب طبقة الثقة من فهرسة **متحققة حديثًا** فقط."""
    assessments: list[IndexAssessment] = []
    stale: list[str] = []
    active_fresh: set[str] = set()

    for record in facts.indexing:
        name = record.index_name.upper()
        fresh = _is_fresh(record, policy, as_of)
        active = record.status == "active"
        counts = fresh and active
        if not fresh:
            stale.append(name)
            reason_ar = "سجل التحقق أقدم من نافذة السياسة؛ يحتاج إعادة تحقق."
            reason_en = "Verification is older than the policy window; re-verification required."
        elif not active:
            reason_ar = f"حالة الفهرسة «{record.status}» لا تُحتسب."
            reason_en = f"Indexing status '{record.status}' does not count."
        else:
            reason_ar = "فهرسة نشطة ومتحقق منها حديثًا."
            reason_en = "Active indexing, recently verified."
        if counts:
            active_fresh.add(name)
        assessments.append(IndexAssessment(
            index_name=name, status=record.status if fresh else NEEDS_REVERIFICATION,
            counts=counts, reason_ar=reason_ar, reason_en=reason_en,
        ))

    if facts.is_discontinued or facts.is_suspicious or (
        facts.publisher and facts.publisher in policy.excluded_publishers
    ):
        tier = "X"
    elif active_fresh & policy.tier_a_indexes:
        tier = "A"
    elif active_fresh & policy.tier_b_indexes:
        tier = "B"
    elif active_fresh & policy.tier_c_indexes:
        tier = "C"
    elif facts.is_peer_reviewed and policy.institution_accepts_peer_reviewed:
        tier = "D"
    else:
        tier = "X"

    label_ar, label_en = TRUST_TIERS[tier]
    return TierAssessment(
        tier=tier, label_ar=label_ar, label_en=label_en,
        indexes=assessments, stale_indexes=stale,
    )


@dataclass(frozen=True, slots=True)
class ManuscriptProfile:
    """ما تعرفه المطابقة عن المخطوطة."""

    keywords: frozenset[str] = frozenset()
    method_keys: frozenset[str] = frozenset()
    target_journal_tier: str | None = None
    max_apc_usd: float | None = None
    requires_open_access: bool = False


@dataclass(slots=True)
class CriterionScore:
    key: str
    weight: int
    ratio: float | None
    label_ar: str
    label_en: str
    detail_ar: str
    detail_en: str

    @property
    def points(self) -> float:
        return 0.0 if self.ratio is None else round(self.weight * self.ratio, 2)


@dataclass(slots=True)
class JournalMatch:
    """§20.4 — درجة ملاءمة بمعاييرها.

    لا حقل لاحتمال القبول، ولا مكان يمكن أن يحمله. هذه هي الضمانة.
    """

    journal_id: str
    journal_name: str
    tier: TierAssessment
    criteria: list[CriterionScore]
    fit_score: float = field(init=False)
    uncomputed: list[str] = field(init=False)
    blockers: list[str] = field(default_factory=list)
    note_ar: str = field(
        default="درجة ملاءمة لا تنبؤ بقرار التحكيم؛ القبول لا يُضمن ولا يُقدَّر.", init=False
    )
    note_en: str = field(
        default="A fit score, not a prediction of the review decision; acceptance is never estimated.",
        init=False,
    )

    def __post_init__(self) -> None:
        self.fit_score = round(sum(c.points for c in self.criteria), 2)
        self.uncomputed = [c.key for c in self.criteria if c.ratio is None]


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float | None:
    if not left or not right:
        return None
    union = left | right
    return round(len(left & right) / len(union), 4) if union else None



# ترتيب طبقات الثقة من الأقوى إلى المستبعدة.
_TIER_ORDER = ("A", "B", "C", "D", "X")


def publication_fit(
    target: str | None, tier: TierAssessment, facts: JournalFacts
) -> tuple[float | None, str, str]:
    """§20.4 — هل هذه المجلة هي الوعاء الذي يقصده الباحث؟

    كان هذا البُعد يقيس «ملاءمة متطلبات الترقية»: طبقة تفرضها لائحة جامعية.
    صار يقيس هدف النشر الذي **يعلنه الباحث** — تفضيلًا لا شرطًا، ولا وعدًا
    بقبول. الوزن لم يتغيّر (15)، والمجموع باقٍ عند 100.

    و`None` تعني «لا يُعرف» لا «صفر»: بيانات الأرباع غير مُنمذجة، وغياب
    الرسوم أو نموذج الوصول غياب معلومة لا مخالفة. تقديرها تخمينٌ يمنعه §20.
    """
    if target is None:
        return None, "لم يُحدَّد هدف نشر لهذه المخطوطة.", "No publication target is set for this manuscript."

    # توافق خلفي: طبقة بحرف واحد تُقارن بترتيب الثقة كما كانت.
    if target in _TIER_ORDER:
        ok = _TIER_ORDER.index(tier.tier) <= _TIER_ORDER.index(target)
        return (1.0 if ok else 0.0,
                f"الهدف طبقة {target} والمجلة في الطبقة {tier.tier}.",
                f"Target tier {target}; journal is tier {tier.tier}.")

    if target == "any_peer_reviewed":
        ok = facts.is_peer_reviewed and tier.tier != "X"
        return (1.0 if ok else 0.0,
                "الهدف أي مجلة محكّمة." + ("" if ok else " والمجلة مستبعدة أو غير محكّمة."),
                "Target is any peer-reviewed journal." + ("" if ok else " This journal is excluded or not peer-reviewed."))

    if target == "web_of_science":
        ok = tier.tier in ("A", "B")
        return (1.0 if ok else 0.0,
                f"الهدف Web of Science والمجلة في الطبقة {tier.tier}.",
                f"Target is Web of Science; journal is tier {tier.tier}.")

    if target == "scopus":
        ok = tier.tier in ("A", "B", "C")
        return (1.0 if ok else 0.0,
                f"الهدف Scopus والمجلة في الطبقة {tier.tier}.",
                f"Target is Scopus; journal is tier {tier.tier}.")

    if target in ("q1", "q2"):
        # الأرباع غير مُنمذجة في `JournalFacts`. لا تُقدَّر ولا تُخمَّن.
        return None, "بيانات أرباع المجلات غير متوفرة — لا تُقدَّر.", "Journal quartile data is unavailable — never estimated."

    if target == "open_access":
        if facts.oa_model is None:
            return None, "نموذج الوصول غير موثق.", "Access model is not documented."
        ok = facts.oa_model != "closed"
        return (1.0 if ok else 0.0, f"الهدف وصول مفتوح ونموذج المجلة: {facts.oa_model}.",
                f"Target is open access; journal model: {facts.oa_model}.")

    if target == "no_apc":
        if facts.apc_usd is None:
            return None, "رسوم النشر غير معروفة.", "Article processing charge unknown."
        ok = facts.apc_usd == 0
        return (1.0 if ok else 0.0, f"الهدف بلا رسوم والرسوم {facts.apc_usd} دولار.",
                f"Target is no APC; charge is {facts.apc_usd} USD.")

    # `custom` وأي قيمة غير معروفة: هدف لا تملك المطابقة معيارًا آليًا له.
    return None, "هدف نشر مخصص — يُقيَّم بشريًا.", "Custom publication target — assessed by a human."


def match(
    manuscript: ManuscriptProfile,
    facts: JournalFacts,
    policy: TierPolicy,
    *,
    as_of: dt.datetime,
    target_journal_tier: str | None = None,
) -> JournalMatch:
    tier = assess_tier(facts, policy, as_of=as_of)
    criteria: list[CriterionScore] = []

    def add(key: str, ratio: float | None, detail_ar: str, detail_en: str) -> None:
        weight, label_ar, label_en = MATCH_CRITERIA[key]
        criteria.append(CriterionScore(
            key=key, weight=weight, ratio=ratio, label_ar=label_ar, label_en=label_en,
            detail_ar=detail_ar, detail_en=detail_en,
        ))

    scope = _jaccard(manuscript.keywords, facts.scope_keywords)
    add("scope_fit", scope,
        "تقاطع كلمات المخطوطة مع نطاق المجلة." if scope is not None
        else "نطاق المجلة أو كلمات المخطوطة غير متوفرة.",
        "Overlap between manuscript keywords and journal scope." if scope is not None
        else "Journal scope or manuscript keywords unavailable.")

    recent = _jaccard(manuscript.keywords, facts.recent_article_keywords)
    add("recent_article_similarity", recent,
        "تشابه مع ما نشرته المجلة حديثًا." if recent is not None
        else "لا تتوفر بيانات المقالات الحديثة.",
        "Similarity to the journal's recent output." if recent is not None
        else "Recent article data unavailable.")

    method = _jaccard(manuscript.method_keys, facts.accepted_methods)
    add("method_fit", method,
        "تقاطع منهج الدراسة مع مناهج المجلة." if method is not None
        else "مناهج المجلة غير موثقة.",
        "Overlap between the study method and the journal's methods." if method is not None
        else "Journal methods are not documented.")

    target = target_journal_tier or manuscript.target_journal_tier
    fit_ratio, fit_ar, fit_en = publication_fit(target, tier, facts)
    add("publication_fit", fit_ratio, fit_ar, fit_en)

    counted = [a for a in tier.indexes if a.counts]
    if not tier.indexes:
        index_ratio: float | None = None
        idx_ar, idx_en = "لا سجلات فهرسة.", "No indexing records."
    else:
        index_ratio = round(len(counted) / len(tier.indexes), 4)
        idx_ar = f"{len(counted)} من {len(tier.indexes)} سجل فهرسة نشط ومتحقق حديثًا."
        idx_en = f"{len(counted)} of {len(tier.indexes)} indexing records active and fresh."
    add("indexing_status", index_ratio, idx_ar, idx_en)

    trust = 0.0 if tier.tier == "X" else (1.0 if tier.tier in ("A", "C") else 0.6)
    add("integrity_publisher_trust", trust,
        f"الناشر والطبقة: {tier.tier}.", f"Publisher and tier: {tier.tier}.")

    if facts.apc_usd is None:
        cost_ratio: float | None = None
        cost_ar, cost_en = "رسوم النشر غير معروفة.", "Article processing charge unknown."
    elif manuscript.max_apc_usd is None:
        cost_ratio = 1.0 if facts.apc_usd == 0 else 0.5
        cost_ar = f"الرسوم {facts.apc_usd} دولار بلا سقف محدد."
        cost_en = f"APC {facts.apc_usd} USD with no stated ceiling."
    else:
        cost_ratio = 1.0 if facts.apc_usd <= manuscript.max_apc_usd else 0.0
        cost_ar = f"الرسوم {facts.apc_usd} مقابل سقف {manuscript.max_apc_usd}."
        cost_en = f"APC {facts.apc_usd} against a ceiling of {manuscript.max_apc_usd}."
    add("cost", cost_ratio, cost_ar, cost_en)

    if facts.oa_model is None:
        oa_ratio: float | None = None
        oa_ar, oa_en = "نموذج الوصول غير موثق.", "Access model is not documented."
    else:
        oa_ratio = 1.0 if (not manuscript.requires_open_access or facts.oa_model != "closed") else 0.0
        oa_ar = f"نموذج الوصول: {facts.oa_model}."
        oa_en = f"Access model: {facts.oa_model}."
    add("oa_license", oa_ratio, oa_ar, oa_en)

    if facts.median_review_days is None:
        review_ratio: float | None = None
        rev_ar = "لا معلومات تحكيم موثوقة — لا تُقدَّر ولا تُخمَّن."
        rev_en = "No trusted review information — never estimated."
    else:
        review_ratio = 1.0 if facts.median_review_days <= 120 else 0.5
        rev_ar = f"وسيط زمن التحكيم {facts.median_review_days} يومًا."
        rev_en = f"Median review time {facts.median_review_days} days."
    add("review_information", review_ratio, rev_ar, rev_en)

    blockers: list[str] = []
    if tier.tier == "X":
        blockers.append("journal_excluded")
    if tier.stale_indexes:
        blockers.append("indexing_needs_reverification")
    # الحاجب يقول إن المجلة دون هدف الباحث، لا إنها دون شرط لائحة.
    if target is not None and fit_ratio == 0.0:
        blockers.append("below_publication_target")

    return JournalMatch(
        journal_id=facts.journal_id, journal_name=facts.name, tier=tier,
        criteria=criteria, blockers=blockers,
    )


def requires_reverification(
    last_verified_at: dt.datetime | None, policy: TierPolicy, *,
    at_point: str, as_of: dt.datetime,
) -> bool:
    """§20.3 / TC-04 — هل يلزم إعادة التحقق عند هذه النقطة؟

    الجواب نعم دائمًا عند غياب سجل تحقق: «لا نعلم» ليست «سليمة».
    """
    if at_point not in VERIFICATION_POINTS:
        raise ValueError(f"unknown verification point: {at_point}")
    if last_verified_at is None:
        return True
    return (as_of - last_verified_at).days > policy.verification_max_age_days
