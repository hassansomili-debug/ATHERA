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


# أغلفة نقل يضعها المزوّد أحيانًا حول وسائط الأداة — ليست محتوى.
#
# **ولا يُخلط هذا بالترميم.** الترميم يخترع قيمةً ناقصة؛ وهذا يزيل غلافًا
# لا يحمل معلومة أصلًا، ثم يُطبَّق العقد كاملًا على ما بداخله. ولا يُزال
# الغلاف إن كان العقد نفسه يعلن حقلًا بهذا الاسم — فالمحتوى يسبق الغلاف.
_ENVELOPES: tuple[str, ...] = ("parameters", "arguments", "input")


def _unwrap(model: type[BaseModel], payload: dict) -> dict:
    """يزيل غلافًا واحدًا لا أكثر، وبشرطين لا ثالث لهما.

    **من أين جاء هذا؟** نداءٌ إنتاجي حقيقي أعاد `{"parameters": {...}}` —
    والمحتوى بداخله مطابق للعقد تمامًا. والنداء التالي بالمدخلات نفسها أعاد
    الشكل المتوقّع. فالسلوك غير حتمي: تشغيلةٌ من كل بضع تشغيلات تسقط بـ502
    على مخرَجٍ سليم.

    فالشرطان: مفتاحٌ واحد فقط في المخرَج، واسمه من الأغلفة المعروفة، وليس
    حقلًا في العقد. وأي شكل آخر يمرّ كما هو ويُحاسَب على العقد.
    """
    if len(payload) != 1:
        return payload
    name = next(iter(payload))
    if name not in _ENVELOPES or name in model.model_fields:
        return payload
    inner = payload[name]
    return inner if isinstance(inner, dict) else payload


def parse_contract(model: type[BaseModel], payload: dict | None):
    if payload is None:
        raise ContractViolation("model returned no structured payload")
    try:
        return model.model_validate(_unwrap(model, payload))
    except ValidationError as exc:
        raise ContractViolation(f"structured output does not match contract: {exc}") from exc
