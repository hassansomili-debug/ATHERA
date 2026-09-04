"""Crossref — فهرس الناشرين. مجّانيّ بلا مفتاح، وبأدب استعمالٍ مُعلَن.

هنا يُقرأ ما يقوله Crossref فقط. ولا يُملأ حقلٌ لم يقله: عنوانُ دوريّةٍ
غائبٌ يبقى غائبًا، وملخّصٌ لم يُرسَل لا يُؤلَّف من العنوان. هذا هو الفرق
العملي بين فهرسة الأدبيات وتوليد النصوص.
"""
from __future__ import annotations

import re
from typing import Any

from .base import DEFAULT_TIMEOUT_SECONDS, USER_AGENT, DiscoveryProvider, ProviderUnavailable
from .contracts import ProviderClaim
from .normalize import normalize_doi

_JATS_TAG = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def _abstract(raw: str | None) -> str | None:
    """Crossref يرسل الملخّص بترميز JATS. تُنزع الوسوم ويبقى نصّ المؤلّف.

    ولا يُختلق ملخّصٌ عند غيابه: `None` تعني «لم يُرسِله الناشر».
    """
    if not raw:
        return None
    text = _SPACES.sub(" ", _JATS_TAG.sub(" ", raw)).strip()
    return text or None


def _retraction(item: dict[str, Any]) -> tuple[str, str | None]:
    """`update-to` هو ما يعلنه Crossref عن سحبٍ أو تصحيح.

    وغيابه **ليس نفيًا للسحب** — لذلك الافتراض `unknown` لا `none`: الادعاء
    بأن ورقةً غير مسحوبة يحتاج مصدرًا كسائر الادعاءات.
    """
    status, detail = "unknown", None
    for update in item.get("update-to") or []:
        label = str(update.get("type", "")).lower()
        if "retraction" in label:
            return "retracted", update.get("DOI")
        if "concern" in label:
            status, detail = "expression_of_concern", update.get("DOI")
        elif "correction" in label or "erratum" in label:
            status, detail = "correction", update.get("DOI")
    return status, detail


def to_claim(item: dict[str, Any]) -> ProviderClaim:
    """يحوّل عنصر Crossref واحدًا إلى ادعاءٍ منسوب إليه — بلا شبكة، فيُختبر."""
    doi = normalize_doi(item.get("DOI") or "")
    titles = [t for t in (item.get("title") or []) if t]
    issued = (item.get("issued") or {}).get("date-parts") or []
    year = None
    if issued and issued[0]:
        year = issued[0][0]
    status, _detail = _retraction(item)
    authors = tuple(
        name for name in (
            " ".join(filter(None, [a.get("given"), a.get("family")])).strip()
            or (a.get("name") or "").strip()
            for a in item.get("author") or []
        ) if name
    )
    containers = [c for c in (item.get("container-title") or []) if c]
    return ProviderClaim(
        provider="crossref",
        # المعرّف القانوني في Crossref هو الـDOI نفسه.
        provider_id=doi or str(item.get("DOI") or ""),
        title=(titles[0] if titles else "").strip(),
        doi=doi,
        authors=authors,
        year=year if isinstance(year, int) else None,
        venue=containers[0] if containers else None,
        volume=item.get("volume") or None,
        issue=item.get("issue") or None,
        pages=item.get("page") or None,
        abstract=_abstract(item.get("abstract")),
        url=item.get("URL") or (f"https://doi.org/{doi}" if doi else None),
        # Crossref لا يعلن الوصول المفتوح إعلانًا موثوقًا، فلا يُدَّعى عنه:
        # `None` هنا تعني «لم يقل»، ولو كُتبت `False` لصارت دعوى إغلاقٍ كاذبة.
        open_access=None,
        citation_count=item.get("is-referenced-by-count"),
        type=item.get("type") or None,
        retraction_status=status,
        raw=item,
    )


class CrossrefProvider(DiscoveryProvider):
    name = "crossref"
    BASE_URL = "https://api.crossref.org"

    def __init__(self, *, mailto: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._mailto = mailto
        self._timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        import httpx  # noqa: PLC0415 — استيراد كسول: الطبقة النقيّة تُختبر بلا httpx

        headers = {"User-Agent": USER_AGENT}
        if self._mailto:
            params = {**params, "mailto": self._mailto}
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                response = await client.get(f"{self.BASE_URL}{path}", params=params)
                if response.status_code == 404:
                    return {}
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001 — كل تعذّرٍ يُترجم إلى نوعٍ مُعلَن
            raise ProviderUnavailable(self.name, type(exc).__name__) from exc

    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        payload = await self._get(
            "/works",
            {"query.bibliographic": query, "rows": min(limit, 50), "select": ",".join((
                "DOI", "title", "author", "issued", "container-title", "volume", "issue",
                "page", "abstract", "URL", "is-referenced-by-count", "type", "update-to",
            ))},
        )
        items = (payload.get("message") or {}).get("items") or []
        return [to_claim(item) for item in items if item.get("DOI")]

    async def by_doi(self, doi: str) -> ProviderClaim | None:
        normalized = normalize_doi(doi)
        if normalized is None:
            return None
        payload = await self._get(f"/works/{normalized}", {})
        message = payload.get("message") or {}
        return to_claim(message) if message.get("DOI") else None
