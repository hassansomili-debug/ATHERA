"""محوّل اكتشاف المراجع | The reference-discovery integration adapter (Wave1-D).

**هذه الوحدة هي المدخل الوحيد إلى فهارس الاكتشاف من طبقة الخدمات.**

وحزمة `discovery` نقيّة: لا تعرف إعدادًا ولا بيئة ولا قاعدة بيانات. فبقي
قرارُ «أيُّ فهارس مُفعَّلة في هذا التشغيل؟» مكتوبًا في الموجّه — نسخةً
واحدة. ولمّا احتاجه مسارٌ ثانٍ (أثيرا AI) كان الطريق المعتاد أن يُنسخ،
فتفترق النسختان بأوّل تعديل: بحثٌ يعمل في شاشة المراجع ولا يعمل في
المحادثة، بلا سببٍ يفهمه الباحث.

فالقرار هنا **مرّة واحدة**، ويقرؤه الموجّه والمحادثة من موضعٍ واحد.

**والنطاق مقصور على Crossref وOpenAlex** (D3): فهرسان علميّان يمنحان
الاستعمال بأدبٍ مُعلَن. ولا يُجمع من Google Scholar ولا ResearchGate ولا
Academia.edu — والأخيران يبقيان **رابطَي وصولٍ خارجيَّين** يحفظهما الباحث،
لا قاعدتَي بياناتٍ تُقرأ آليًّا. وهذا الحدّ مفروضٌ في `discovery.normalize`
قبل أي نداء، ومُعاد إعلانه هنا لأنّه عقدٌ لا تعليق.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from ..config import get_settings
from ..discovery import (
    DiscoveryProvider,
    DiscoveryResult,
    ReferenceCandidate,
    default_providers,
    discover,
)

# سقفُ ما يُطلب من الفهارس في نداءٍ واحدٍ من المحادثة. أقلّ من سقف الشاشة
# عمدًا: المحادثة تعرض قائمةً يقرؤها الباحث في سياق جواب، لا شبكةَ نتائج.
CHAT_SEARCH_LIMIT = 8


def enabled_providers() -> list[DiscoveryProvider]:
    """الفهارس المُفعَّلة في هذا التشغيل — **مصدرٌ واحد لكل من يسأل**.

    وبيئة الاختبار بلا فهارس عمدًا: CI حتميّة بلا شبكة، ولا نداء خارجي
    يقع بالصدفة في تشغيلةِ اختبارات.
    """
    if get_settings().app_env == "test":
        return []
    # أدب الاستعمال يطلب جهة اتصال. الترويسة تحمل نطاق المنتج دائمًا،
    # ويُضاف بريدٌ إن ضُبط.
    return default_providers(mailto=(os.getenv("LITERATURE_CONTACT_EMAIL") or None))


def provider_names() -> tuple[str, ...]:
    """أسماءُ الفهارس **من المزوّدين أنفسهم** — لا قائمةٌ تُكتب بجانبهم.

    وهو الخطأ المتكرّر في هذا المستودع: قيمةٌ تُكتب بجانب سجلّها بدل أن
    تُشتقّ منه، فيتغيّر السجلّ ويبقى النصّ يقول ما لم يعد صحيحًا.
    """
    return tuple(provider.name for provider in enabled_providers())


def is_available() -> bool:
    """هل يستطيع هذا التشغيل أن يبحث في فهرسٍ علميٍّ خارجيّ الآن؟"""
    return bool(enabled_providers())


@dataclass(frozen=True, slots=True)
class DiscoveredReference:
    """مرجعٌ مكتشَف — **بما قاله الفهرس عنه، منسوبًا إليه** (D4).

    ولا حقل هنا يُملأ استنتاجًا: غيابُ الملخّص غيابٌ، وغيابُ السنة غياب.
    و`citation_counts` قاموسٌ لكلّ فهرسٍ فيه عدّاده — **ولا مجموع ولا
    متوسّط**: جمعُ عدّادَي فهرسين يضاعف الاستشهاد الواحد، والمتوسّط رقمٌ
    لا يقوله أحدٌ ولا يمكن التحقّق منه في أيّ فهرس.
    """

    title: str
    authors: tuple[str, ...]
    year: int | None
    venue: str | None
    doi: str | None
    url: str | None
    providers: tuple[str, ...]
    citation_counts: dict[str, int]
    open_access: bool | None
    retraction_status: str
    # **مدى ما وصلنا من هذا المرجع، لا مدى ما يمكن قراءته منه.**
    # فهرسٌ أرسل ملخّصًا يعطينا `abstract_only`؛ وما عداه `metadata_only`.
    # ولا يصير `full_text` بحال من نداءٍ إلى فهرس — النصّ الكامل يأتي من
    # ملفٍّ رفعه الباحث ومرّ بمسار المعالجة، لا من بحثٍ ببليوغرافي.
    scope: str

    @property
    def has_abstract(self) -> bool:
        return self.scope == "abstract_only"


def to_reference(candidate: ReferenceCandidate) -> DiscoveredReference:
    """يحوّل مرشّحًا إلى مرجعٍ للعرض — بلا اختلاق حقلٍ لم يقله فهرس."""
    return DiscoveredReference(
        title=candidate.title,
        authors=tuple(candidate.authors),
        year=candidate.year,
        venue=candidate.venue,
        doi=candidate.doi,
        url=candidate.url,
        providers=tuple(candidate.providers),
        citation_counts=dict(candidate.citation_counts),
        open_access=candidate.open_access,
        retraction_status=candidate.retraction_status,
        scope="abstract_only" if candidate.abstract else "metadata_only",
    )


async def search(query: str, *, limit: int = CHAT_SEARCH_LIMIT) -> DiscoveryResult:
    """بحثٌ في الفهارس المُفعَّلة. يعيد نتيجةً فارغةً إن لم يكن فيها فهرس.

    ولا يُبتلع تعذّرُ فهرس: حالُ كلٍّ منهما تعود في `provider_statuses`،
    فيُقال «لم يُجب» ولا يُقال «لا يوجد».
    """
    return await discover(enabled_providers(), query, limit=limit)


def references(result: DiscoveryResult) -> list[DiscoveredReference]:
    return [to_reference(ranked.candidate) for ranked in result.ranked]
