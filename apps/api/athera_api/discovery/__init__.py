"""اكتشاف المراجع | Reference discovery (V1).

حزمةٌ مستقلة عن الخادم وعن قاعدة البيانات: فهارس حرّة بلا مفاتيح، تُسأل
وتُترجَم إلى ادعاءاتٍ منسوبة، ثم تُوحَّد بقواعد فصلٍ متحفّظة. لا تكتب
شيئًا ولا تقرّر شيئًا — القرار في الطبقة التي فوقها، والتخزين في المكتبة.
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
from .service import default_providers, discover

__all__ = [
    "CrossrefProvider",
    "DiscoveryProvider",
    "DiscoveryResult",
    "ExternalAccessLink",
    "OpenAlexProvider",
    "ProviderClaim",
    "ProviderStatus",
    "ProviderUnavailable",
    "ReferenceCandidate",
    "deduplicate",
    "default_providers",
    "discover",
]
