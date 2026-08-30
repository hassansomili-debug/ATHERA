"""محوّل OpenAI | OpenAI adapter (§38.6.3، ADR-0003).

المكان الوحيد المسموح فيه باستيراد SDK مزود. الاستيراد كسول حتى لا تصبح
الحزمة تبعية إلزامية لتشغيل الاختبارات.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from time import perf_counter

from .base import ModelProvider, ModelRequest, ModelResponse, ModelUsage


class OpenAIAdapter(ModelProvider):
    name = "openai"

    def __init__(self, api_key: str, default_model: str = "gpt-4.1") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the openai provider")
        self._api_key = api_key
        self._default_model = default_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI  # noqa: PLC0415 — استيراد كسول مقصود

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate_structured(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        client = self._get_client()
        model = request.model or self._default_model
        response = await client.responses.create(
            model=model,
            input=[{"role": m.role, "content": m.content} for m in request.messages],
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
        )
        latency_ms = int((perf_counter() - started) * 1000)
        usage = getattr(response, "usage", None)
        return ModelResponse(
            content=getattr(response, "output_text", "") or "",
            structured=None,
            usage=ModelUsage(
                input_tokens=getattr(usage, "input_tokens", None) if usage else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage else None,
                latency_ms=latency_ms,
            ),
            provider=self.name,
            model=model,
        )

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        client = self._get_client()
        response = await client.embeddings.create(model=model or "text-embedding-3-small", input=texts)
        return [item.embedding for item in response.data]

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        client = self._get_client()

        async def _iter() -> AsyncIterator[str]:
            stream = await client.responses.create(
                model=request.model or self._default_model,
                input=[{"role": m.role, "content": m.content} for m in request.messages],
                stream=True,
            )
            async for event in stream:
                delta = getattr(event, "delta", None)
                if isinstance(delta, str) and delta:
                    yield delta

        return _iter()

    async def tool_call(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError("Tool calling lands with the Research Brain orchestrator, not Sprint 0")
