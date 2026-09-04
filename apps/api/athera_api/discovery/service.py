"""تنسيق الاكتشاف | Discovery orchestration.

الفهارس تُسأل **معًا** لا بالتتابع: التتابع يجعل زمن الاستجابة مجموع
المزوّدين، وأسوأُهم بطئًا يحكم على أسرعهم. ويُسأل كلٌّ منهما دائمًا حتى
لو أجاب الأول — لأن غاية هذه الشاشة أن يُرى ما يقوله الفهرسان معًا عن
الورقة نفسها، لا أن يُكتفى بأوّل من ردّ.

**وتعذّرُ مزوّدٍ يُعلَن باسمه.** الفهرس الذي لم يجب ليس فهرسًا قال «لا
يوجد»؛ والخلط بينهما يجعل الشاشة تكذب في أسوأ لحظة: حين تكون الشبكة
معطوبة والباحث يظنّ موضوعه بكرًا.
"""
from __future__ import annotations

import asyncio

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
from .normalize import extract_doi_anywhere, external_access_link
from .openalex import OpenAlexProvider

MAX_LIMIT = 50


def default_providers(*, mailto: str | None = None) -> list[DiscoveryProvider]:
    """المزوّدان الحرّان بلا مفتاح. الترتيب هو ترتيب الأسبقية في العرض."""
    return [CrossrefProvider(mailto=mailto), OpenAlexProvider(mailto=mailto)]


def _passes(candidate: ReferenceCandidate, *, year_from: int | None, year_to: int | None,
            work_type: str | None, open_access_only: bool) -> bool:
    """المرشِّحات تُطبَّق على المرشَّح المدموج لا على ادعاءٍ منفرد.

    ولو صُفّي على ادعاءٍ واحدٍ لسقطت ورقةٌ لأن أحد الفهرسين لم يذكر سنتها،
    بينما ذكرها الآخر — وهذا إخفاءُ نتيجةٍ صحيحة بسبب نقصٍ في فهرس.
    """
    year = candidate.year
    if year_from is not None and (year is None or year < year_from):
        return False
    if year_to is not None and (year is None or year > year_to):
        return False
    if work_type and (candidate.type or "").lower() != work_type.lower():
        return False
    # «المفتوح فقط» يُقصي المجهول أيضًا، وهو المقصود: إدراجُ ما لم يُعلَن
    # مفتوحًا تحت عنوان «مفتوح الوصول» ادّعاءُ حقٍّ لم يمنحه أحد.
    return not (open_access_only and candidate.open_access is not True)


async def _collect(provider: DiscoveryProvider, query: str, doi: str | None,
                   limit: int) -> tuple[ProviderStatus, list[ProviderClaim]]:
    try:
        if doi:
            found = await provider.by_doi(doi)
            claims = [found] if found is not None else []
        else:
            claims = await provider.search(query, limit=limit)
    except ProviderUnavailable as exc:
        return ProviderStatus(provider=provider.name, ok=False, detail=exc.detail), []
    except Exception as exc:  # noqa: BLE001 — لا يسقط البحث كلّه بسبب فهرسٍ واحد
        return ProviderStatus(provider=provider.name, ok=False,
                              detail=type(exc).__name__), []
    return ProviderStatus(provider=provider.name, ok=True, results=len(claims)), claims


async def discover(
    providers: list[DiscoveryProvider],
    query: str,
    *,
    limit: int = 20,
    year_from: int | None = None,
    year_to: int | None = None,
    work_type: str | None = None,
    open_access_only: bool = False,
) -> DiscoveryResult:
    """يبحث في كل الفهارس، ويوحّد، ويُبقي نسبة كل ادعاء إلى قائله."""
    limit = max(1, min(limit, MAX_LIMIT))
    text = (query or "").strip()

    # الرابط الممنوع جمعه يُكتشف **قبل أي نداء**: لا يُطلب من المنصّة شيء،
    # ولا تُقرأ منها بيانات. ويُستخرج منه DOI إن كان مكتوبًا فيه صراحةً —
    # فذاك معرّفٌ شرعيّ يُسأل عنه الفهرسان، لا استخراجٌ من صفحتها.
    blocked = external_access_link(text)
    link = ExternalAccessLink(url=blocked[0], host=blocked[1]) if blocked else None

    doi = extract_doi_anywhere(text)
    if link is not None and doi is None:
        # لا معرّف شرعيّ في الرابط: يُعاد الرابط وحده بلا بياناتٍ موصوفة،
        # ولا يُقال إنّ شيئًا تُحقِّق منه.
        return DiscoveryResult(candidates=(), provider_statuses=(), external_link=link)

    outcomes = await asyncio.gather(
        *(_collect(provider, text, doi, limit) for provider in providers)
    )
    statuses = tuple(status for status, _claims in outcomes)
    claims: list[ProviderClaim] = []
    for _status, found in outcomes:
        claims.extend(found)

    candidates = tuple(
        candidate for candidate in deduplicate(claims)
        if _passes(candidate, year_from=year_from, year_to=year_to,
                   work_type=work_type, open_access_only=open_access_only)
    )
    return DiscoveryResult(
        candidates=candidates[:limit], provider_statuses=statuses, external_link=link,
    )
