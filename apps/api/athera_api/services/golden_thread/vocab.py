"""مفردات المجال | Domain vocabulary (§15.1، §16).

هذه ثوابت **علمية** لا تفاصيل تخزين: سلسلة الخيط، أنواع الروابط، أنواع
الدراسات، وأساليب المعاينة وما إذا كانت تسمح بالتعميم.

موضعها هنا لا في طبقة النماذج لأن الاعتماد يجب أن يسير في اتجاه واحد:
النماذج تعرف المجال، والمجال لا يعرف قاعدة البيانات. هذا ما يبقي فحوص
§15.2 قابلة للتشغيل والاختبار بلا قاعدة بيانات.
"""
from typing import Final

# §15.1 — سلسلة العلاقات. الترتيب مقصود: كل عنصر يستمد مشروعيته مما قبله.
THREAD_ELEMENTS: Final[tuple[str, ...]] = (
    "phenomenon", "problem", "gap", "question", "objective", "theory",
    "construct", "variable", "method", "instrument", "analysis",
    "result", "discussion", "recommendation",
)

# أنواع الروابط المسموح بها — لا رابط عشوائي في الخيط.
LINK_TYPES: Final[dict[str, tuple[str, str]]] = {
    "addresses": ("يعالج", "addresses"),
    "answers": ("يجيب عن", "answers"),
    "maps_to": ("يقابل", "maps to"),
    "operationalizes": ("يُفعّل إجرائيًا", "operationalizes"),
    "measures": ("يقيس", "measures"),
    "analyzes": ("يحلّل", "analyzes"),
    "produces": ("ينتج", "produces"),
    "supports": ("يدعم", "supports"),
    "explains": ("يفسّر", "explains"),
    "derives_from": ("مشتق من", "derives from"),
}

# §16 — أنواع الدراسات.
STUDY_TYPES: Final[tuple[str, ...]] = (
    "quantitative", "qualitative", "mixed_methods", "experimental", "review",
)

# أساليب المعاينة، والقيمة تعني: هل تسمح بالتعميم على المجتمع؟
# هذا هو المعيار الذي يفحص عليه كشف «تعميم أكبر من العينة» (§15.2).
SAMPLING_STRATEGIES: Final[dict[str, bool]] = {
    "simple_random": True,
    "stratified_random": True,
    "systematic_random": True,
    "cluster_random": True,
    "census": True,
    "convenience": False,
    "purposive": False,
    "snowball": False,
    "quota": False,
}

# تصاميم تكون السببية فيها مشروعة — كشف اللغة السببية لا يعمل عليها.
CAUSAL_DESIGNS: Final[frozenset[str]] = frozenset({"experimental", "quasi_experimental"})
