"""القيم وحالاتها | Values and their epistemic state.

**رقمٌ بلا حالةٍ ومصدرٍ لا يُمثَّل هنا أصلًا.**

هذا هو الفرق بين حارسٍ يمنع الاختلاق وعقدٍ يجعله غير قابلٍ للكتابة. الحارس
يفحص بعد أن يُكتب الرقم، فيمرّ ما لم يخطر ببال كاتب الحارس. والعقد يجعل
الرقم بلا مصدر **خطأ تحقّقٍ عند الإنشاء**: لا يوجد شكلٌ صحيح من `Quantity`
يحمل قيمةً ولا يقول من أين جاءت.

والحالات ثلاث لا اثنتان، وهو الدرس المسجَّل في ترحيل 0016 مطبَّقًا على
الأرقام لا على قرارات الباحث:

    known    قيمةٌ مسجَّلة، ومعها معرّف ما أنتجها
    missing  ليست مسجَّلة — وهذا يُعلَن ولا يُملأ
    unknown  سُئل عنها ولم يُعرف الجواب

و`missing` ليست صفرًا وليست `None` تُقرأ صفرًا: «حجم العينة غير مسجَّل»
جوابٌ صحيح، و«حجم العينة صفر» كذبة، و«حجم العينة 384» مخترعةً هي الكذبة
التي تُبنى عليها ورقة.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator


class ValueState(str, Enum):
    KNOWN = "known"
    MISSING = "missing"
    UNKNOWN = "unknown"


class Quantity(BaseModel):
    """قيمة عدديّة بحالتها ومصدرها.

    `source_ref` معرّف ما أنتج الرقم — مخرَج تحليل أو ذاكرة موثقة. وهو
    إلزاميٌّ مع `known` لأن السلسلة التي يفرضها `ClaimAnalysisLink` في
    المخطوطات هي نفسها المطلوبة هنا: السند أن تكون **هذه القيمة** في **ذلك
    المخرَج**، لا أن تكون تشغيلةٌ ما موجودة في مكانٍ ما.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: ValueState
    value: float | None = None
    source_ref: str | None = None

    @model_validator(mode="after")
    def _value_and_state_must_agree(self) -> Quantity:
        if self.state is ValueState.KNOWN:
            if self.value is None:
                raise ValueError("a known quantity must carry its value")
            if not (self.source_ref or "").strip():
                raise ValueError("a known quantity must name what produced it")
        elif self.value is not None:
            raise ValueError("only a known quantity may carry a value")
        return self

    @property
    def is_known(self) -> bool:
        return self.state is ValueState.KNOWN

    def label(self) -> tuple[str, str]:
        """كيف تُكتب هذه القيمة للباحث — ولا تُكتب فراغًا أبدًا."""
        if self.state is ValueState.KNOWN:
            text = f"{self.value:g}"
            return (text, text)
        if self.state is ValueState.MISSING:
            return ("غير مسجَّلة", "MISSING")
        return ("غير معروفة", "UNKNOWN")


def missing() -> Quantity:
    return Quantity(state=ValueState.MISSING)


def unknown() -> Quantity:
    return Quantity(state=ValueState.UNKNOWN)


def known(value: float, *, source_ref: str) -> Quantity:
    """لا مسار لبناء قيمةٍ معلومة بلا مصدر — والمعامل مُسمّى فلا يُنسى موضعه."""
    return Quantity(state=ValueState.KNOWN, value=value, source_ref=source_ref)
