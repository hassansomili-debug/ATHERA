"""اختيار السجل الخارجي | Registry selection (§14.1، §34.1).

نقطة الحقن الوحيدة. الافتراض **بلا شبكة**: بيئة لم تُعلن سجلها صراحةً تعمل
على `OfflineRegistry`، فلا يقع استدعاء خارجي بالصدفة في اختبار أو في تشغيل
محلي — وهو ما يجعل نتائج الاختبارات حتمية.
"""
from __future__ import annotations

import os
from functools import lru_cache

from .registry import CrossrefRegistry, OfflineRegistry, OpenAlexRegistry, SourceRegistry

_REGISTRIES: dict[str, type[SourceRegistry]] = {
    "offline": OfflineRegistry,
    "openalex": OpenAlexRegistry,
    "crossref": CrossrefRegistry,
}


class UnknownRegistry(Exception):
    """اسم سجل غير معروف يُرفض ولا يُستبدل بافتراض صامت."""


@lru_cache(maxsize=4)
def get_registry(name: str | None = None) -> SourceRegistry:
    key = (name or os.getenv("LITERATURE_REGISTRY", "offline")).strip().lower()
    factory = _REGISTRIES.get(key)
    if factory is None:
        raise UnknownRegistry(
            f"unknown literature registry: {key}. "
            f"available: {', '.join(sorted(_REGISTRIES))}"
        )
    return factory()
