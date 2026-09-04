"""إزالة التكرار بين الفهارس | Cross-provider deduplication.

**عند الشكّ تُفصَل.** دمجُ ورقتين مختلفتين في بطاقةٍ واحدة خطأٌ لا يُرى:
الباحث يستشهد بواحدة وقد قرأ عن الأخرى، ولا شيء في الشاشة يقول له ذلك.
أما بقاءُ الورقة الواحدة في سطرين فخطأٌ يراه ويصلحه في ثانية. فالميزان
مائلٌ عمدًا إلى الفصل.

والترتيب مُلزِم:
  ١ DOI مسوًّى ومتطابق تمامًا — أقوى دليل، ولا شيء يعلوه.
  ٢ معرّف قانونيّ مشترك (openalex/pmid/pmcid/mag) — تصريح المزوّد نفسه.
  ٣ عنوان+سنة+اسم المؤلّف الأول — **ولا يُستعمل إلا حين لا DOI لأيّ منهما**.

والقيد الأخير هو الذي يمنع الخطأ الشائع: ورقتان بعنوانٍ واحد وسنةٍ واحدة
لكن بـDOI مختلفين ليستا ورقةً واحدة — هما نسختا مؤتمرٍ ودوريّة، أو ورقةٌ
وتصحيحها. فاختلاف الـDOI **نفيٌ للتطابق** لا سكوتٌ عنه.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .contracts import ProviderClaim, ReferenceCandidate
from .normalize import first_author_key, normalized_title

MATCH_DOI = "doi"
MATCH_CANONICAL_ID = "provider_id"
MATCH_TITLE_YEAR_AUTHOR = "title_year_author"
MATCH_SINGLE = "single"

# عنوانٌ قصيرٌ جدًّا («Editorial»، «Correction») يتكرر عبر آلاف الأوراق،
# فلا يصلح دليلَ هويّة. الحدّ يُقصي هذه الحالة بلا أن يُقصي عنوانًا حقيقيًّا.
_MIN_TITLE_CHARS = 12


@dataclass
class _Bucket:
    claims: list[ProviderClaim] = field(default_factory=list)
    dois: set[str] = field(default_factory=set)
    ids: set[str] = field(default_factory=set)
    fallback_keys: set[tuple[str, int, str]] = field(default_factory=set)
    basis: str = MATCH_SINGLE

    def absorb(self, claim: ProviderClaim, basis: str) -> None:
        if self.claims and basis != MATCH_SINGLE and self.basis == MATCH_SINGLE:
            self.basis = basis
        self.claims.append(claim)
        if claim.doi:
            self.dois.add(claim.doi)
        self.ids.add(claim.canonical_id)
        self.ids.update(claim.alternate_ids)
        key = _fallback_key(claim)
        if key is not None:
            self.fallback_keys.add(key)


def _fallback_key(claim: ProviderClaim) -> tuple[str, int, str] | None:
    """مفتاح الاحتياط الثلاثي، أو `None` إن نقص ركنٌ منه.

    نقصان أي ركن يمنع الاستعمال أصلًا: مطابقةٌ على عنوانٍ وحده تدمج ورقةً
    بترجمتها، وعلى سنةٍ وحدها تدمج كل نتاج عام.
    """
    title = normalized_title(claim.title)
    author = first_author_key(claim.authors)
    if len(title) < _MIN_TITLE_CHARS or claim.year is None or not author:
        return None
    return (title, claim.year, author)


def _contradicted_by_doi(bucket: _Bucket, claim: ProviderClaim) -> bool:
    """هل يحمل الطرفان DOI مختلفين؟ إن كان، فهما ورقتان — وينتهي البحث."""
    return bool(claim.doi and bucket.dois and claim.doi not in bucket.dois)


def _match(bucket: _Bucket, claim: ProviderClaim) -> str | None:
    if claim.doi and claim.doi in bucket.dois:
        return MATCH_DOI
    if _contradicted_by_doi(bucket, claim):
        return None
    shared = bucket.ids & ({claim.canonical_id} | set(claim.alternate_ids))
    if shared:
        return MATCH_CANONICAL_ID
    # القاعدة الثالثة تُطبَّق حين لا DOI **لا في الطرف ولا في الحزمة**؛
    # فحزمةٌ ذات DOI معروف لا يُضاف إليها مجهولٌ على حُسن الظنّ.
    if not claim.doi and not bucket.dois:
        key = _fallback_key(claim)
        if key is not None and key in bucket.fallback_keys:
            return MATCH_TITLE_YEAR_AUTHOR
    return None


def deduplicate(claims: Sequence[ProviderClaim]) -> list[ReferenceCandidate]:
    """يجمع ادعاءات الفهارس في مرشّحين، ويحفظ ترتيب أول ظهورٍ لكل مرشّح."""
    buckets: list[_Bucket] = []
    for claim in claims:
        placed = False
        for bucket in buckets:
            basis = _match(bucket, claim)
            if basis is not None:
                bucket.absorb(claim, basis)
                placed = True
                break
        if not placed:
            fresh = _Bucket()
            fresh.absorb(claim, MATCH_SINGLE)
            buckets.append(fresh)
    return [
        ReferenceCandidate(claims=tuple(bucket.claims), match_basis=bucket.basis)
        for bucket in buckets
    ]
