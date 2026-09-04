"""OpenAlex — فهرسٌ مفتوح مجّانيّ بلا مفتاح، وبأدب استعمالٍ مُعلَن.

OpenAlex يرسل الملخّص «مقلوب الفهرسة» (كلمة ← مواضعها). إعادة ترتيبه ليست
توليدًا: كل كلمةٍ وكل موضعٍ من المزوّد، والناتج هو نصّ المؤلّف نفسه. وإن
غاب الفهرس المقلوب بقي الملخّص `None` — ولا يُؤلَّف بديل.
"""
from __future__ import annotations

from typing import Any

from .base import DEFAULT_TIMEOUT_SECONDS, USER_AGENT, DiscoveryProvider
from .contracts import ProviderClaim
from .normalize import normalize_doi
from .resilience import fetch_json

# سقفٌ على الملخّص المُعاد بناؤه: فهرسٌ مقلوب ضخم لا يُعاد تركيبه بلا حدّ.
_MAX_ABSTRACT_WORDS = 4000


def _abstract(inverted: dict[str, list[int]] | None) -> str | None:
    if not inverted:
        return None
    positions: list[tuple[int, str]] = []
    for word, places in inverted.items():
        for place in places or []:
            if isinstance(place, int):
                positions.append((place, word))
    if not positions or len(positions) > _MAX_ABSTRACT_WORDS:
        return None
    positions.sort()
    return " ".join(word for _place, word in positions).strip() or None


def _short_id(value: str | None) -> str:
    """`https://openalex.org/W123` ← `W123`. المعرّف يُقارَن بصورةٍ واحدة."""
    return (value or "").rsplit("/", 1)[-1]


def to_claim(payload: dict[str, Any]) -> ProviderClaim:
    """يحوّل عملًا واحدًا من OpenAlex إلى ادعاءٍ منسوب إليه — بلا شبكة، فيُختبر."""
    ids = payload.get("ids") or {}
    location = (payload.get("primary_location") or {})
    source = location.get("source") or {}
    biblio = payload.get("biblio") or {}
    first, last = biblio.get("first_page"), biblio.get("last_page")
    pages = f"{first}-{last}" if first and last else (first or last or None)

    alternates: set[str] = set()
    for key in ("pmid", "pmcid", "mag"):
        if ids.get(key):
            alternates.add(f"{key}:{_short_id(str(ids[key]))}")

    doi = normalize_doi(payload.get("doi") or ids.get("doi") or "")
    return ProviderClaim(
        provider="openalex",
        provider_id=_short_id(payload.get("id")),
        title=(payload.get("title") or payload.get("display_name") or "").strip(),
        doi=doi,
        authors=tuple(
            name for name in (
                ((a.get("author") or {}).get("display_name") or "").strip()
                for a in payload.get("authorships") or []
            ) if name
        ),
        year=payload.get("publication_year") if isinstance(
            payload.get("publication_year"), int) else None,
        venue=source.get("display_name") or None,
        volume=biblio.get("volume") or None,
        issue=biblio.get("issue") or None,
        pages=pages,
        abstract=_abstract(payload.get("abstract_inverted_index")),
        url=location.get("landing_page_url") or payload.get("id") or None,
        open_access=(payload.get("open_access") or {}).get("is_oa"),
        citation_count=payload.get("cited_by_count"),
        type=payload.get("type") or None,
        # `is_retracted` صريحٌ عند OpenAlex: `False` نفيٌ مُعلَن، وغيابه لا يُنفى.
        retraction_status=(
            "retracted" if payload.get("is_retracted") is True
            else "none" if payload.get("is_retracted") is False
            else "unknown"
        ),
        alternate_ids=frozenset(alternates),
        raw=payload,
    )


class OpenAlexProvider(DiscoveryProvider):
    name = "openalex"
    BASE_URL = "https://api.openalex.org"

    def __init__(self, *, mailto: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._mailto = mailto
        self._timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """نداءٌ واحد بمحاولاتٍ محدودة — بقاعدة الإعادة نفسها التي لجاره."""
        import httpx  # noqa: PLC0415

        query = {**params, "mailto": self._mailto} if self._mailto else params

        async def send() -> tuple[int, dict[str, Any] | None]:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(f"{self.BASE_URL}{path}", params=query)
                if response.status_code >= 400:
                    return response.status_code, None
                return response.status_code, response.json()

        return await fetch_json(send, provider=self.name)

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        payload = await self._get("/works", {"search": query, "per-page": min(limit, 50)})
        return [to_claim(item) for item in payload.get("results") or [] if item.get("id")]

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        normalized = normalize_doi(doi)
        if normalized is None:
            return None
        payload = await self._get(f"/works/doi:{normalized}", {})
        return to_claim(payload) if payload.get("id") else None
