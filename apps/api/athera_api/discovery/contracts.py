"""عقود اكتشاف المراجع | Reference discovery contracts.

**المزوّد لا يقول الحقيقة، بل يقول ما عنده.** Crossref يقول عن ورقةٍ إنّ
استشهاداتها ١٢٠ وOpenAlex يقول ١٣٤ — وليس أحدهما كاذبًا: هما فهرسان
يعدّان مجموعتين مختلفتين. فدمجُ الرقمين في رقمٍ واحد يخترع رقمًا لا يقوله
أحد، واختيارُ أحدهما بلا نسبة يجعل ادعاء مزوّدٍ حكمًا للمنصّة.

لذلك الوحدة الأساسية هنا `ProviderClaim` — ادعاءٌ **منسوب إلى قائله**؛
و`ReferenceCandidate` ليس سجلًّا مدمجًا بل حزمةُ ادعاءاتٍ عن عملٍ واحد،
تُعرض حقولها بأسبقيةٍ معلنة ويبقى مصدر كل حقل قابلًا للسؤال.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ترتيب الأسبقية عند اختيار قيمةٍ واحدة للعرض. ليس حكمًا بأن مزوّدًا أصدق،
# بل قاعدةٌ ثابتة ومُعلَنة تمنع أن يتغيّر المعروض بتغيّر ترتيب وصول الردود.
PROVIDER_PRECEDENCE: tuple[str, ...] = ("crossref", "openalex")


def _rank(provider: str) -> int:
    try:
        return PROVIDER_PRECEDENCE.index(provider)
    except ValueError:
        return len(PROVIDER_PRECEDENCE)


@dataclass(frozen=True, slots=True)
class ProviderClaim:
    """ما قاله مزوّدٌ واحد عن عملٍ واحد. لا يُخلط بغيره ولا يُنسب إلى سواه."""

    provider: str
    provider_id: str
    title: str
    doi: str | None = None
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    # الملخّص يُملأ فقط حين يمنحه المزوّد صراحةً (§14.2). غيابه يُقال غيابًا،
    # ولا يُستنتج من عنوانٍ ولا يُولَّد.
    abstract: str | None = None
    url: str | None = None
    # ثلاثية القيم مقصودة: `None` تعني «لم يقل المزوّد»، لا «مغلق».
    open_access: bool | None = None
    citation_count: int | None = None
    type: str | None = None
    retraction_status: str = "unknown"
    # معرّفات قانونية أخرى يذكرها المزوّد عن العمل نفسه (pmid، openalex…).
    # تفيد المطابقة بين الفهارس بلا تخمين.
    alternate_ids: frozenset[str] = frozenset()
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def canonical_id(self) -> str:
        """المعرّف القانوني لهذا الادعاء داخل فهرس مزوّده."""
        return f"{self.provider}:{self.provider_id}"


@dataclass(frozen=True, slots=True)
class ReferenceCandidate:
    """مُرشَّح بحث — **ليس مرجعًا مخزَّنًا، ولا دليلًا**.

    `match_basis` يقول لماذا اجتمعت هذه الادعاءات في بطاقة واحدة، فيبقى
    الدمج مسؤولًا عن نفسه ومُراجَعًا.
    """

    claims: tuple[ProviderClaim, ...]
    match_basis: str = "single"

    def __post_init__(self) -> None:
        if not self.claims:
            raise ValueError("a candidate without any provider claim cannot exist")

    @property
    def ordered_claims(self) -> tuple[ProviderClaim, ...]:
        return tuple(sorted(self.claims, key=lambda claim: _rank(claim.provider)))

    def _first(self, attribute: str) -> Any:
        for claim in self.ordered_claims:
            value = getattr(claim, attribute)
            if value not in (None, "", ()):
                return value
        return None

    @property
    def providers(self) -> tuple[str, ...]:
        seen: list[str] = []
        for claim in self.ordered_claims:
            if claim.provider not in seen:
                seen.append(claim.provider)
        return tuple(seen)

    @property
    def doi(self) -> str | None:
        return self._first("doi")

    @property
    def title(self) -> str:
        return self._first("title") or ""

    @property
    def authors(self) -> tuple[str, ...]:
        return self._first("authors") or ()

    @property
    def year(self) -> int | None:
        return self._first("year")

    @property
    def venue(self) -> str | None:
        return self._first("venue")

    @property
    def volume(self) -> str | None:
        return self._first("volume")

    @property
    def issue(self) -> str | None:
        return self._first("issue")

    @property
    def pages(self) -> str | None:
        return self._first("pages")

    @property
    def abstract(self) -> str | None:
        return self._first("abstract")

    @property
    def url(self) -> str | None:
        return self._first("url")

    @property
    def type(self) -> str | None:
        return self._first("type")

    @property
    def open_access(self) -> bool | None:
        """`True` إن أعلنه مزوّدٌ واحد على الأقل مفتوحًا.

        وغياب الإعلان يبقى `None`: «لم يُذكر» ليس «مغلق».
        """
        for claim in self.ordered_claims:
            if claim.open_access is True:
                return True
        for claim in self.ordered_claims:
            if claim.open_access is False:
                return False
        return None

    @property
    def citation_counts(self) -> dict[str, int]:
        """عدّاد كل فهرس منسوبًا إليه — **ولا مجموع ولا متوسّط**.

        جمعُ عدّادَي فهرسين يضاعف الاستشهاد الواحد المفهرس مرّتين، والمتوسّط
        رقمٌ لا يقوله أحد ولا يمكن التحقق منه في أي فهرس.
        """
        return {
            claim.provider: claim.citation_count
            for claim in self.ordered_claims
            if claim.citation_count is not None
        }

    @property
    def retraction_status(self) -> str:
        """السحب يُعلَن إن قاله أي فهرس. الحال الأشدّ تُغلِّب — سلامةً لا تشدّدًا."""
        statuses = {claim.retraction_status for claim in self.claims}
        for state in ("retracted", "expression_of_concern", "correction"):
            if state in statuses:
                return state
        return "none" if "none" in statuses else "unknown"


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    """حال مزوّدٍ في هذه التشغيلة. الفشل يُعلَن ولا يُقرأ «لا نتائج»."""

    provider: str
    ok: bool
    detail: str | None = None
    results: int = 0


@dataclass(frozen=True, slots=True)
class ExternalAccessLink:
    """رابط وصول إضافي — رابطٌ يحفظه الباحث، **لا مصدرُ بيانات وصفية**.

    ResearchGate وAcademia.edu يمنعان الجمع الآلي، فلا يُطلبان ولا يُقرأان.
    الرابط يُحفظ كما لصقه صاحبه، وحالته غير متحقَّقة دائمًا — والبيانات
    الوصفية، إن وُجدت، تأتي من معرّفٍ شرعي أو من فهرسٍ لا منه.
    """

    url: str
    host: str
    note_code: str = "discovery.external_link_only"
    verified: bool = False


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """نتيجة اكتشافٍ كاملة: ما وُجد، ومن أجاب، ومن تعذّر."""

    candidates: tuple[ReferenceCandidate, ...]
    provider_statuses: tuple[ProviderStatus, ...]
    external_link: ExternalAccessLink | None = None

    @property
    def any_provider_failed(self) -> bool:
        return any(not status.ok for status in self.provider_statuses)

    @property
    def all_providers_failed(self) -> bool:
        return bool(self.provider_statuses) and all(
            not status.ok for status in self.provider_statuses
        )
