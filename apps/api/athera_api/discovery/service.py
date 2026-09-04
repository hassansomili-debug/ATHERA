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
from .normalize import external_access_link
from .openalex import OpenAlexProvider
from .query import parse_query
from .ranking import rank_candidates

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
    # التصفية على السلّة الموحّدة لا على نصّ الفهرس الخام: `journal-article`
    # و`article` اسمان لشيءٍ واحد، ومقارنةُ الحرف تُخفي نصف النتائج بحسب
    # أيّ فهرسٍ ردّ أوّلًا.
    if work_type and candidate.work_type != work_type.strip().lower():
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
    accepted_terms: object = (),
    now_year: int | None = None,
) -> DiscoveryResult:
    """يبحث في كل الفهارس، ويوحّد، ويرتّب مُعلِّلًا — والنسبة محفوظة.

    **والترتيب يسبق القصّ.** لو قُصّ العشرون الأوائل بترتيب وصول الفهارس ثم
    رُتِّبوا، لصارت «الأفضل» أفضلَ ما وصل أولًا لا أفضل ما وُجد؛ وورقةٌ
    تأسيسية جاءت في الترتيب الحادي والعشرين من فهرسٍ بطيء تختفي بلا أثر.
    """
    limit = max(1, min(limit, MAX_LIMIT))
    text = (query or "").strip()
    parsed = parse_query(text, accepted_terms=accepted_terms)

    # الرابط الممنوع جمعه يُكتشف **قبل أي نداء**: لا يُطلب من المنصّة شيء،
    # ولا تُقرأ منها بيانات. ويُستخرج منه DOI إن كان مكتوبًا فيه صراحةً —
    # فذاك معرّفٌ شرعيّ يُسأل عنه الفهرسان، لا استخراجٌ من صفحتها.
    blocked = external_access_link(text)
    link = ExternalAccessLink(url=blocked[0], host=blocked[1]) if blocked else None

    if link is not None and parsed.doi is None:
        # لا معرّف شرعيّ في الرابط: يُعاد الرابط وحده بلا بياناتٍ موصوفة،
        # ولا يُقال إنّ شيئًا تُحقِّق منه.
        return DiscoveryResult(
            ranked=(), provider_statuses=(), external_link=link, query=parsed,
        )

    outcomes = await asyncio.gather(
        *(_collect(provider, parsed.sent, parsed.doi, limit) for provider in providers)
    )
    statuses = tuple(status for status, _claims in outcomes)
    claims: list[ProviderClaim] = []
    for _status, found in outcomes:
        claims.extend(found)

    # مُرشِّح الشاشة يعلو على ما قرأه المحلّل من النصّ: الباحث الذي ضبط
    # «من سنة» صراحةً قال قولًا أخيرًا، و`year:2019` داخل النصّ يملأ الفراغ
    # ولا ينسخ اختيارًا. وإلا لتغيّر المُرشِّح المرئي بكلمةٍ كتبها في السطر.
    low = year_from if year_from is not None else (parsed.year or parsed.year_from)
    high = year_to if year_to is not None else (parsed.year or parsed.year_to)

    candidates = [
        candidate for candidate in deduplicate(claims)
        if _passes(candidate, year_from=low, year_to=high,
                   work_type=work_type, open_access_only=open_access_only)
    ]
    ranked = rank_candidates(candidates, parsed, now_year=now_year)[:limit]
    return DiscoveryResult(
        ranked=ranked, provider_statuses=statuses, external_link=link, query=parsed,
    )
