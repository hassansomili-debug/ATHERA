"""حدُّ الشبكة في فحوص الاكتشاف | Mocking the indexes at the HTTP boundary.

**يُزيَّف النداء الشبكي وحده، ولا يُزيَّف المزوّد.**

ولو استُبدل `CrossrefProvider` بصنفٍ وهميّ لبقيت تسويةُ الحمولة — وهي
موضعُ أكثر العيوب — خارج ما يُفحص: عنوانٌ يُقرأ من الحقل الخطأ، ومؤلّفٌ
يُبنى بلا اسمٍ أوسط، وملخّصٌ يُقرأ بترميز JATS. فتمرّ الفحوص ويكسر الإنتاج.

فالمزوّدان هنا **حقيقيّان**، والحمولات مسجَّلة بأشكال Crossref وOpenAlex
كما تردّان، والمُزيَّف هو `fetch_json` وحده — أي السلك.

ولا نداء شبكيّ يقع في CI بحال: الحزمة لا تلمس Crossref ولا OpenAlex.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def stub_indexes(monkeypatch, *, crossref: dict | None = None,
                 openalex: dict | None = None,
                 crossref_down: bool = False,
                 openalex_down: bool = False) -> dict[str, list[str]]:
    """يجعل الفهرسين مُفعَّلين ويردّان حمولةً مسجَّلة بدل الشبكة.

    ويعيد سجلًّا بما طُلب من كلٍّ منهما، فيُثبَت **أنّ النداء وقع** ولا
    يُكتفى بأن الرد بدا صحيحًا.
    """
    from athera_api.discovery import crossref as crossref_module
    from athera_api.discovery import openalex as openalex_module
    from athera_api.discovery.base import ProviderUnavailable
    from athera_api.discovery.service import default_providers
    from athera_api.services import reference_discovery

    calls: dict[str, list[str]] = {"crossref": [], "openalex": []}

    # الفهارس مُفعَّلة في هذه الفحوص مهما كانت `APP_ENV`: البوابة البيئية
    # ليست موضوع الفحص، والسلك هو المُزيَّف.
    monkeypatch.setattr(reference_discovery, "enabled_providers",
                        lambda: default_providers())

    async def _crossref(_send, *, provider, **_kwargs):
        calls["crossref"].append(provider)
        if crossref_down:
            raise ProviderUnavailable("crossref", "ConnectTimeout")
        return crossref if crossref is not None else load("crossref_search.json")

    async def _openalex(_send, *, provider, **_kwargs):
        calls["openalex"].append(provider)
        if openalex_down:
            raise ProviderUnavailable("openalex", "ConnectTimeout")
        return openalex if openalex is not None else load("openalex_search.json")

    monkeypatch.setattr(crossref_module, "fetch_json", _crossref)
    monkeypatch.setattr(openalex_module, "fetch_json", _openalex)
    return calls


def no_indexes(monkeypatch) -> None:
    """تشغيلٌ بلا فهارس — حالٌ ثالثة تُعلَن لا تُخفى."""
    from athera_api.services import reference_discovery

    monkeypatch.setattr(reference_discovery, "enabled_providers", list)
