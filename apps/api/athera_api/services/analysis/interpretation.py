"""طبقات التفسير | Interpretation layers (§18.3، §9 بوابة G8).

§18.3 تفصل أربع طبقات: النتيجة · التفسير الإحصائي · التفسير النظري ·
الدلالة الإدارية.

الفصل ليس تنظيمًا: دمجها هو بالضبط كيف تصير «p = 0.03» جملةً عن سلوك
المستهلك السعودي. كل طبقة حقل مستقل، والانتقال من طبقة إلى ما بعدها
يحتاج سندًا من التي قبلها.
"""
from __future__ import annotations

from dataclasses import dataclass

from .vocab import INTERPRETATION_LAYERS


class InterpretationError(Exception):
    pass


@dataclass(slots=True)
class Interpretation:
    """تفسير مرتبط بمخرَج فعلي.

    `output_id` إلزامي: §18.3 تنص أن الذكاء الاصطناعي «يفسر النتائج الفعلية
    فقط»، فتفسير بلا نتيجة ليس ناقصًا بل غير مشروع.
    """

    output_id: str
    result_ar: str
    statistical_ar: str | None = None
    theoretical_ar: str | None = None
    managerial_ar: str | None = None
    result_en: str | None = None
    statistical_en: str | None = None
    theoretical_en: str | None = None
    managerial_en: str | None = None
    approved_by: str | None = None
    approved_at: object | None = None

    def __post_init__(self) -> None:
        if not self.output_id.strip():
            raise InterpretationError(
                "an interpretation must reference an actual output (§18.3)"
            )
        if not self.result_ar.strip():
            raise InterpretationError("the result layer cannot be empty (§18.3)")

        # سلسلة السند: لا تفسير نظري بلا إحصائي، ولا دلالة إدارية بلا نظري.
        if self.theoretical_ar and not self.statistical_ar:
            raise InterpretationError(
                "a theoretical interpretation requires a statistical one first (§18.3)"
            )
        if self.managerial_ar and not self.theoretical_ar:
            raise InterpretationError(
                "a managerial implication requires a theoretical interpretation first (§18.3)"
            )

    @property
    def layers_present(self) -> list[str]:
        values = {
            "result": self.result_ar, "statistical": self.statistical_ar,
            "theoretical": self.theoretical_ar, "managerial": self.managerial_ar,
        }
        return [key for key in INTERPRETATION_LAYERS if values.get(key)]

    @property
    def is_approved(self) -> bool:
        return self.approved_by is not None and self.approved_at is not None


@dataclass(slots=True)
class LayerView:
    layer: str
    label_ar: str
    label_en: str
    text_ar: str | None
    text_en: str | None


def layers(interpretation: Interpretation) -> list[LayerView]:
    """يعرض الطبقات الأربع منفصلة — لا نصًا واحدًا مدموجًا."""
    mapping = {
        "result": (interpretation.result_ar, interpretation.result_en),
        "statistical": (interpretation.statistical_ar, interpretation.statistical_en),
        "theoretical": (interpretation.theoretical_ar, interpretation.theoretical_en),
        "managerial": (interpretation.managerial_ar, interpretation.managerial_en),
    }
    return [
        LayerView(layer=key, label_ar=label_ar, label_en=label_en,
                  text_ar=mapping[key][0], text_en=mapping[key][1])
        for key, (label_ar, label_en) in INTERPRETATION_LAYERS.items()
    ]


def merged_text_is_refused(text: str) -> None:
    """حارس صريح ضد إرسال الطبقات كنص واحد.

    وجود هذه الدالة يوثّق أن الدمج قرار مرفوض لا حالة غير مدعومة.
    """
    raise InterpretationError(
        "interpretation layers are stored separately and never as one merged text (§18.3)"
    )
