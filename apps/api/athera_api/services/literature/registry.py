"""سجلات الأدبيات الخارجية | External source registries (§14.1، §34.1).

نفس نمط §32: واجهة واحدة، ومحوّلات خلفها، ولا استيراد شبكي في طبقة الأعمال.
`OfflineRegistry` يجعل كل اختبارات السجل تعمل بلا شبكة — وهذا ليس تسهيلًا
للاختبار بل شرط أن يبقى المنتج مستقلًا عن أي مزوّد بيانات بعينه.

واستجابة أي سجل خارجي **محتوى غير موثوق** (§33.3): تُخزَّن في `raw_metadata`
ولا تُنفَّذ منها تعليمات، ولا يُشتق منها نص علمي بلا حق وصول.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

# تعريفٌ واحد للـDOI في المنتج كلّه — مكانه حزمة الاكتشاف النقيّة، ويُعاد
# تصديره هنا لمن اعتاده. ونسختان منه تعنيان قاعدتَي قبولٍ تفترقان يومًا:
# مُعرّفٌ يقبله الاستيراد ويرفضه البحث، فيُتّهم المنتج بأنه «لا يجد» ما
# استورده هو نفسه.
# وترويسةُ الهويّة واحدة كذلك: Crossref وOpenAlex يشترطان في أدب استعمالهما
# هويّةً وجهةَ اتصال في **كل** طلب. وكان الاستيراد يمضي بلا ترويسة ما لم
# يُضبط بريد — أي أنّ أكثر النشرات تطلب مجهولةً، وأول ما يُحجب المجهول
# يسقط الاستيراد بلا أن يعرف أحد لماذا.
from ...discovery.base import USER_AGENT
from ...discovery.normalize import DOI_PATTERN as DOI_PATTERN  # noqa: PLC0414
from ...discovery.normalize import normalize_doi as normalize_doi  # noqa: PLC0414


@dataclass(slots=True)
class RegistryRecord:
    """سجل خارجي محايد تجاه المزود."""

    registry: str
    registry_id: str
    title: str
    doi: str | None = None
    publication_year: int | None = None
    journal_name: str | None = None
    issn: str | None = None
    authors: list[str] = field(default_factory=list)
    is_open_access: bool | None = None
    retraction_status: str = "unknown"
    retraction_detail: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def access_state(self) -> str:
        """السجل الخارجي لا يمنح نصًا إلا إذا كان مفتوح الوصول صراحةً.

        الافتراض المحافظ مقصود: Metadata فقط ما لم يثبت العكس (§14.2، §14.5).
        """
        return "open_access_full_text" if self.is_open_access else "abstract_metadata_only"


class SourceNotFound(Exception):
    """المعرّف لم يُحلّ في هذا السجل. لا يُختلق بديل (TC-02)."""


class SourceRegistry(abc.ABC):
    name: str = "abstract"

    @abc.abstractmethod
    async def get_by_doi(self, doi: str) -> RegistryRecord: ...

    @abc.abstractmethod
    async def search(self, query: str, *, limit: int = 20) -> list[RegistryRecord]: ...


class OfflineRegistry(SourceRegistry):
    """سجل حتمي بلا شبكة — للاختبارات وللتشغيل في بيئة معزولة.

    لا يخترع سجلات: يعيد ما زُرع فيه فقط، ويرفع `SourceNotFound` لما عداه.
    """

    name = "offline"

    def __init__(self, records: dict[str, RegistryRecord] | None = None) -> None:
        self._records = dict(records or {})

    def seed(self, record: RegistryRecord) -> None:
        if record.doi:
            self._records[record.doi] = record

    async def get_by_doi(self, doi: str) -> RegistryRecord:
        normalized = normalize_doi(doi)
        if normalized is None or normalized not in self._records:
            raise SourceNotFound(doi)
        return self._records[normalized]

    async def search(self, query: str, *, limit: int = 20) -> list[RegistryRecord]:
        needle = query.strip().lower()
        return [
            record for record in self._records.values()
            if needle in record.title.lower()
        ][:limit]


class OpenAlexRegistry(SourceRegistry):
    """§34.1 — OpenAlex. الاستيراد الشبكي كسول ومحصور هنا."""

    name = "openalex"
    BASE_URL = "https://api.openalex.org"

    def __init__(self, mailto: str | None = None, timeout: float = 10.0) -> None:
        self._mailto = mailto
        self._timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        import httpx  # noqa: PLC0415 — استيراد كسول مقصود

        if self._mailto:
            params = {**params, "mailto": self._mailto}
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = await client.get(f"{self.BASE_URL}{path}", params=params)
            if response.status_code == 404:
                raise SourceNotFound(path)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _to_record(payload: dict) -> RegistryRecord:
        location = (payload.get("primary_location") or {}).get("source") or {}
        return RegistryRecord(
            registry="openalex",
            registry_id=str(payload.get("id", "")),
            title=payload.get("title") or payload.get("display_name") or "",
            doi=normalize_doi(payload.get("doi") or ""),
            publication_year=payload.get("publication_year"),
            journal_name=location.get("display_name"),
            issn=(location.get("issn_l") or None),
            authors=[
                (a.get("author") or {}).get("display_name", "")
                for a in payload.get("authorships", [])
            ],
            is_open_access=(payload.get("open_access") or {}).get("is_oa"),
            # OpenAlex يشير إلى السحب عبر `is_retracted`؛ غيابه ليس نفيًا.
            retraction_status="retracted" if payload.get("is_retracted") else "unknown",
            raw=payload,
        )

    async def get_by_doi(self, doi: str) -> RegistryRecord:
        normalized = normalize_doi(doi)
        if normalized is None:
            raise SourceNotFound(doi)
        return self._to_record(await self._get(f"/works/doi:{normalized}", {}))

    async def search(self, query: str, *, limit: int = 20) -> list[RegistryRecord]:
        payload = await self._get("/works", {"search": query, "per-page": min(limit, 50)})
        return [self._to_record(item) for item in payload.get("results", [])]


class CrossrefRegistry(SourceRegistry):
    """§34.2 — Crossref، ومنه حالة السحب والتصحيح (`update-to`)."""

    name = "crossref"
    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: str | None = None, timeout: float = 10.0) -> None:
        self._mailto = mailto
        self._timeout = timeout

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        import httpx  # noqa: PLC0415

        agent = USER_AGENT + (f" mailto:{self._mailto}" if self._mailto else "")
        async with httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": agent}
        ) as client:
            response = await client.get(f"{self.BASE_URL}{path}", params=params)
            if response.status_code == 404:
                raise SourceNotFound(path)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _to_record(item: dict) -> RegistryRecord:
        updates = item.get("update-to") or []
        retraction, detail = "none", None
        for update in updates:
            label = str(update.get("type", "")).lower()
            if "retraction" in label:
                retraction, detail = "retracted", update.get("DOI")
                break
            if "correction" in label or "erratum" in label:
                retraction, detail = "correction", update.get("DOI")
            elif "concern" in label:
                retraction, detail = "expression_of_concern", update.get("DOI")
        titles = item.get("title") or [""]
        issued = (item.get("issued") or {}).get("date-parts") or [[None]]
        return RegistryRecord(
            registry="crossref",
            registry_id=item.get("DOI", ""),
            title=titles[0] if titles else "",
            doi=normalize_doi(item.get("DOI") or ""),
            publication_year=issued[0][0] if issued and issued[0] else None,
            journal_name=(item.get("container-title") or [None])[0],
            issn=(item.get("ISSN") or [None])[0],
            authors=[
                " ".join(filter(None, [a.get("given"), a.get("family")]))
                for a in item.get("author", [])
            ],
            retraction_status=retraction,
            retraction_detail=detail,
            raw=item,
        )

    async def get_by_doi(self, doi: str) -> RegistryRecord:
        normalized = normalize_doi(doi)
        if normalized is None:
            raise SourceNotFound(doi)
        payload = await self._get(f"/works/{normalized}", {})
        return self._to_record(payload.get("message", {}))

    async def search(self, query: str, *, limit: int = 20) -> list[RegistryRecord]:
        payload = await self._get("/works", {"query.bibliographic": query, "rows": min(limit, 50)})
        return [self._to_record(item) for item in payload.get("message", {}).get("items", [])]
