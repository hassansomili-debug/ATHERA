"""اكتشاف المراجع | Reference discovery (V2).

حزمةٌ مستقلة عن الخادم وعن قاعدة البيانات: فهارس حرّة بلا مفاتيح، تُسأل
وتُترجَم إلى ادعاءاتٍ منسوبة، ثم تُوحَّد بقواعد فصلٍ متحفّظة. لا تكتب
شيئًا ولا تقرّر شيئًا — القرار في الطبقة التي فوقها، والتخزين في المكتبة.

وV2 تضيف طبقتين لا تكسران الأولى: فهمُ الاستعلام (`query`) وترتيبٌ مُعلَّل
(`ranking`). كلتاهما نقيّةٌ بلا شبكة، وكلتاهما تُخرج تفسيرًا لا رقمًا.
"""
from .base import DiscoveryProvider, ProviderUnavailable
from .contracts import (
    DiscoveryResult,
    ExternalAccessLink,
    ProviderClaim,
    ProviderStatus,
    ReferenceCandidate,
)
from .crossref import CrossrefProvider
from .dedup import deduplicate
from .openalex import OpenAlexProvider
from .query import ParsedQuery, SuggestedTerm, parse_query
from .ranking import RankedReference, Ranking, RankReason, rank_candidates
from .resilience import fetch_json
from .service import default_providers, discover

__all__ = [
    "CrossrefProvider",
    "DiscoveryProvider",
    "DiscoveryResult",
    "ExternalAccessLink",
    "OpenAlexProvider",
    "ParsedQuery",
    "ProviderClaim",
    "ProviderStatus",
    "ProviderUnavailable",
    "RankReason",
    "RankedReference",
    "Ranking",
    "ReferenceCandidate",
    "SuggestedTerm",
    "deduplicate",
    "default_providers",
    "discover",
    "fetch_json",
    "parse_query",
    "rank_candidates",
]
