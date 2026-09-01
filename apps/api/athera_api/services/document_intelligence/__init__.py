"""ذكاء المستندات | Document intelligence (S5C).

يقرأ الرسالة المرفوعة ويقترح ما فيها — **ولا يقرر شيئًا**. كل مخرَج مرشّح
ينتظر إنسانًا، وكل مرشّح يحمل موضعه في المصدر.
"""
from .fields import FIELD_CATALOGUE, FieldSpec, Section
from .selection import select_chunks_for
from .states import STATE_FLOW, Status  # noqa: F401

__all__ = ["FIELD_CATALOGUE", "FieldSpec", "Section", "STATE_FLOW", "Status", "select_chunks_for"]
