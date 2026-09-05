"""قدرات أثيرا AI | What the assistant can actually do right now (Wave1-D).

**العطب الذي تصلحه هذه الوحدة عطبُ صدقٍ لا عطبُ شكل.**

كان في الموجّه سطرٌ واحد:

    literature_online = os.getenv("LITERATURE_REGISTRY", "offline") != "offline"

فطوى ثلاث قدراتٍ مختلفةً في منطقٍ واحد، ثمّ اشتقّ منه رسالةً تقول للباحث
إنّ «البحث الخارجي في الأدبيات غير مفعّل». وهي **كذبة**: `LITERATURE_REGISTRY`
هو سجلُّ الرصد المجدول، ولا علاقة له باكتشاف المراجع. واكتشافُ المراجع
ينادي Crossref وOpenAlex في كل بحث، بلا مفتاح ولا إعداد، والإنتاج يعمل
اليوم بـ`LITERATURE_REGISTRY=offline` — أي أنّ المحادثة كانت تنفي قدرةً
قائمة، وتعتذر عن بحثٍ تستطيع إجراءه.

وأخطرُ ما في ذلك أنّ الاعتذار لم يكن يقف عند الشاشة: كان يُحقن في تعليمات
النظام، فيُقال للنموذج «لم تبحث ولا تستطيع» بينما البحث متاح.

فالقدرات هنا **ثلاثٌ منفصلة، كلٌّ مشتقّةٌ من مصدرها الحقيقي**:

* `reference_discovery_available` — من مزوّدي الاكتشاف أنفسهم.
* `literature_registry_available` — من كائن السجلّ الذي يبنيه المصنع.
* `full_text_retrieval_available` — من طبقة تخزين ملفات الباحث.

**ولا واحدةٌ منها تُكتب بجانب سجلّها.** كلٌّ تُسأل عن سجلّها وقتَ السؤال.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import reference_discovery, storage


@dataclass(frozen=True, slots=True)
class Capabilities:
    """حالُ القدرات الثلاث — مقروءةً لا مفترضة."""

    # البحث في الفهارس العلمية الخارجية (Crossref، OpenAlex).
    reference_discovery_available: bool
    reference_discovery_providers: tuple[str, ...]

    # الرصد المجدول من سجلّ أدبياتٍ خارجي — قدرةٌ أخرى تمامًا.
    literature_registry_available: bool
    literature_registry: str

    # النصّ الكامل: لا يأتي من فهرس، بل من ملفٍّ رفعه الباحث وعُولج.
    full_text_retrieval_available: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "reference_discovery_available": self.reference_discovery_available,
            "reference_discovery_providers": list(self.reference_discovery_providers),
            "literature_registry_available": self.literature_registry_available,
            "literature_registry": self.literature_registry,
            "full_text_retrieval_available": self.full_text_retrieval_available,
        }


def _registry_state() -> tuple[bool, str]:
    """حالُ سجلّ الرصد المجدول — **من الكائن الذي يبنيه المصنع**.

    ولا تُقرأ البيئة هنا مباشرةً: قراءةُ `LITERATURE_REGISTRY` بجانب المصنع
    هي بعينها العادةُ التي أنتجت العطب. والمصنعُ قد يرفض اسمًا مجهولًا،
    ورفضُه حالٌ ثالثة تُقال: لا سجلّ، وسببه أنّ الاسم غير معروف.
    """
    from .literature import registry as registry_module  # noqa: PLC0415
    from .literature import registry_factory  # noqa: PLC0415

    try:
        chosen = registry_factory.get_registry()
    except registry_factory.UnknownRegistry:
        return False, "unknown"
    # السجلّ الحتميّ لا ينادي أحدًا — وهو الحال الافتراضية وحالُ الإنتاج.
    offline = isinstance(chosen, registry_module.OfflineRegistry)
    return (not offline), chosen.name


def current() -> Capabilities:
    """يقرأ القدرات الثلاث الآن. رخيصةٌ عمدًا: لا شبكة ولا قاعدة بيانات."""
    providers = reference_discovery.provider_names()
    registry_available, registry_name = _registry_state()
    return Capabilities(
        reference_discovery_available=bool(providers),
        reference_discovery_providers=providers,
        literature_registry_available=registry_available,
        literature_registry=registry_name,
        # **النصّ الكامل مشتقٌّ من التخزين لا من الفهارس.** فهرسٌ يعلن
        # ورقةً «مفتوحة الوصول» يعلن حقًّا لا يمنح نصًّا؛ والنصّ الكامل في
        # هذا المنتج لا يوجد إلا في ملفٍّ رفعه الباحث ومرّ بالمعالجة. فبلا
        # تخزينٍ مُهيّأ لا يوجد نصٌّ كامل أصلًا، مهما قالت الفهارس.
        full_text_retrieval_available=storage.is_configured(),
    )
