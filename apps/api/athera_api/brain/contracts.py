"""العقود المهيكلة | Structured output contracts (§38.6.2، §32).

مخرَج لا يطابق العقد **يفشل التشغيلة**. لا ترميم ولا تخمين ولا محاولة
إصلاح — لأن ترميم مخرَج مشوّه هو بالضبط اللحظة التي يتسرب فيها الاختلاق.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

__all__ = ["Citation", "BrainAnswer", "ContractViolation", "parse_contract", "ValidationError"]


class ContractViolation(Exception):
    """المخرَج خالف العقد — التشغيلة فاشلة، والنتيجة لا تُعرض."""


class Citation(BaseModel):
    """استشهاد بذاكرة موثقة — بموضعه واقتباسه، وإلا فليس استشهادًا."""

    memory_id: str
    locator: str | None = None
    quote: str | None = None


class BrainAnswer(BaseModel):
    """إجابة العقل البحثي.

    `unsupported_claims` ليس حقلًا تجميليًا: إجبار النموذج على تسمية ما لا
    يستطيع دعمه أفضل من تركه يمرّره ضمن النص (§4 Evidence First).
    """

    answer_ar: str = Field(min_length=1)
    answer_en: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


# غلافُ نقلٍ يضعه المزوّد أحيانًا حول وسائط الأداة — ليس محتوى.
#
# **والقاعدة بنيوية لا بالاسم.** أول علاج كان قائمة أسماء معروفة
# (`parameters`, `arguments`, `input`)، فجاء الإنتاج باسمٍ رابع: `answer_ar`
# — وهو اسم حقلٍ في عقدٍ آخر. وقائمةُ أسماء تلاحق سلوكًا غير حتمي تخسر
# السباق دائمًا.
#
# فالسؤال صار: هل الداخل **هو العقد** والخارج ليس كذلك؟ فإن كان، فالخارج
# غلافٌ مهما كان اسمه. ولا اختلاق في ذلك: لا يُقبل الداخل إلا إن اجتاز
# العقد كاملًا، ولا يُصحَّح فيه شيء.


def _envelope(model: type[BaseModel], payload: dict):
    """يفتح غلافًا واحدًا **متى كان ما بداخله عقدًا صالحًا وما خارجه ليس**.

    وثلاثة شروط: مفتاحٌ واحد فقط، وقيمته قاموس، وليس اسمه حقلًا في العقد
    (فالمحتوى يسبق الغلاف). ثم يُجرَّب الداخل — فإن سقط، سقط الطلب كما لو
    لم يُفتح شيء، ورسالةُ الخطأ عن العقد لا عن الغلاف.
    """
    if len(payload) != 1:
        return None
    name = next(iter(payload))
    if name in model.model_fields:
        return None
    inner = payload[name]
    if not isinstance(inner, dict):
        return None
    try:
        return model.model_validate(inner)
    except ValidationError:
        return None


def parse_contract(model: type[BaseModel], payload: dict | None):
    if payload is None:
        raise ContractViolation("model returned no structured payload")
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # المخرَج لا يطابق العقد — أهو غلافُ نقلٍ حول عقدٍ صالح؟
        unwrapped = _envelope(model, payload)
        if unwrapped is not None:
            return unwrapped
        raise ContractViolation(f"structured output does not match contract: {exc}") from exc
