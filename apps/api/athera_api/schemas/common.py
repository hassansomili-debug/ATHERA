"""نماذج مشتركة | Shared response models."""
from __future__ import annotations

from pydantic import BaseModel, Field


class BilingualText(BaseModel):
    """نص بلغتين — العربية إلزامية والإنجليزية اختيارية (§26.4)."""

    ar: str
    en: str | None = None

    def resolve(self, locale: str) -> str:
        return (self.en or self.ar) if locale == "en" else self.ar


class Health(BaseModel):
    status: str
    locale: str
    supported_locales: list[str]
    provider: str = Field(description="Active model provider (§32)")
