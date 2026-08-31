"""عقود محفظة الأبحاث | Research portfolio contracts (§12).

كانت هذه العقود داخل `schemas/promotion.py` — بقيةُ زمنٍ كان فيه المشروع
وحدةً في ملف ترقية. المشروع الآن وحدة البحث نفسها، فانتقلت إلى ملفها.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    """§12.2 — حقول المشروع."""

    working_title_ar: str = Field(min_length=2)
    working_title_en: str | None = None
    program_id: uuid.UUID | None = None
    study_type: str | None = None
    expected_units: float | None = Field(default=None, ge=0, le=10)
    target_journal_name: str | None = None
    target_index_tier: str | None = None
    intended_author_count: int | None = Field(default=None, ge=1, le=50)
    intended_author_position: int | None = Field(default=None, ge=1, le=50)
    risks: list[str] | None = None
    target_date: dt.date | None = None
    is_thesis_derived: bool = False


class ProjectResponse(BaseModel):
    id: uuid.UUID
    working_title: str
    working_title_ar: str
    working_title_en: str | None
    program_id: uuid.UUID | None
    study_type: str | None
    status: str
    expected_units: float | None
    target_journal_name: str | None
    target_index_tier: str | None
    risks: list[str] | None
    target_date: dt.date | None
    current_gate: str | None
    is_thesis_derived: bool
