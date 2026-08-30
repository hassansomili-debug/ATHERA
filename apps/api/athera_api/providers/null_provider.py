"""مزود حتمي للاختبارات | Deterministic provider for tests (AT-S0-08).

ليس محاكاة ذكاء: يعيد مخرجات ثابتة حتى تبقى الاختبارات حتمية، ويثبت أن
لا شيء في المنظومة يعتمد على مزود بعينه.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from .base import ModelProvider, ModelRequest, ModelResponse, ModelUsage


class NullProvider(ModelProvider):
    name = "null"

    async def generate_structured(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="",
            structured={},
            usage=ModelUsage(input_tokens=0, output_tokens=0, cost_usd=0.0, latency_ms=0),
            provider=self.name,
            model=request.model or "null",
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        # متجه صفري بأبعاد ثابتة — يكفي لإثبات المسار دون ادعاء دلالة.
        return [[0.0] * 1536 for _ in texts]

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        async def _empty() -> AsyncIterator[str]:
            if False:  # pragma: no cover
                yield ""
        return _empty()

    async def tool_call(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="", structured={}, provider=self.name,
                             model=request.model or "null")
