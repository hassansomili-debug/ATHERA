"""استخراج حتمي | Deterministic extraction (§9).

**لا يُسأل النموذج عمّا يعرفه الكود يقينًا.** عدد الصفحات واسم الملف
معلومتان في المستند نفسه، وسؤال نموذج عنهما إنفاقٌ ومخاطرةُ اختلاق بلا سبب.

وما لا يُعرف يقينًا يبقى للنموذج — ولا يُخمَّن هنا بقواعد هشّة. الدرجة مثلًا
تحتاج قراءة صفحة العنوان لا مطابقة كلمة، فهي ليست هنا.
"""
from __future__ import annotations

from dataclasses import dataclass

from .selection import ChunkView


@dataclass(frozen=True, slots=True)
class DeterministicValue:
    field_key: str
    value: object
    quote: str
    locator: str
    chunk_id: str | None


def extract(chunks: list[ChunkView], *, filename: str) -> list[DeterministicValue]:
    """ما يُعرف بلا نموذج — وكلٌّ منه بموضعه في المصدر."""
    values: list[DeterministicValue] = []
    if not chunks:
        return values

    first = chunks[0]

    values.append(DeterministicValue(
        field_key="source_filename", value=filename,
        # الاقتباس هنا اسم الملف نفسه: مصدره البيانات الوصفية لا متن المستند.
        quote=filename, locator="file.metadata", chunk_id=None,
    ))

    pages = {c.page_number for c in chunks if c.page_number is not None}
    if pages:
        values.append(DeterministicValue(
            field_key="page_count", value=max(pages),
            quote=f"pages 1–{max(pages)}", locator=f"p.1–{max(pages)}", chunk_id=first.chunk_id,
        ))
    return values
