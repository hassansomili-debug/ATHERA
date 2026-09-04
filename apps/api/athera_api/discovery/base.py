"""واجهة مزوّدي الاكتشاف | Discovery provider interface.

مزوّدٌ واحدٌ لا يُملي الشكل: كلٌّ يُترجم ردَّه إلى `ProviderClaim` ثم ينتهي
دوره. وهذا ما يجعل إضافة فهرسٍ ثالثٍ لاحقًا تغييرًا في ملفّ واحد.

**والتعذّر ليس فراغًا.** `ProviderUnavailable` نوعٌ قائم بذاته لأن الفرق
بين «الفهرس لم يجب» و«الفهرس أجاب بلا نتائج» هو الفرق بين رسالةٍ صادقة
وكذبةٍ صامتة يقرؤها الباحث «لا يوجد شيء عن موضوعي».
"""
from __future__ import annotations

import abc

from .contracts import ProviderClaim

# مهلةٌ محدودة لكل نداءٍ خارجي. بلا سقفٍ يصير بطءُ فهرسٍ بطءَ المنصّة كلها،
# والباحث ينتظر شاشةً لا تقول له شيئًا.
DEFAULT_TIMEOUT_SECONDS = 8.0

# أدب الاستعمال الذي يطلبه Crossref وOpenAlex صراحةً: هويّةٌ وجهةُ اتصال في
# كل طلب. هذا شرط استعمالٍ لا تزيين — به يُميَّز مرورنا ويُبلَّغ إن أخطأنا.
USER_AGENT = "PUBRIVA/1.0 (+https://pubriva.com; reference discovery)"


class ProviderUnavailable(Exception):
    """تعذّر بلوغ الفهرس أو فهمُ ردّه. يُعلَن باسم مزوّده ولا يُبتلع."""

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(f"{provider}: {detail}")
        self.provider = provider
        self.detail = detail


class DiscoveryProvider(abc.ABC):
    """فهرسٌ خارجيّ حرّ بلا مفتاح. لا يُخزّن شيئًا ولا يقرّر شيئًا."""

    name: str = "abstract"

    @abc.abstractmethod
    async def search(self, query: str, *, limit: int) -> list[ProviderClaim]:
        """بحثٌ نصّي. يرفع `ProviderUnavailable` عند التعذّر، ولا يعيد فراغًا مضلّلًا."""

    @abc.abstractmethod
    async def by_doi(self, doi: str) -> ProviderClaim | None:
        """جلبٌ بمعرّفٍ شرعي. `None` تعني «لم يُعرف في هذا الفهرس» لا «غير موجود»."""
