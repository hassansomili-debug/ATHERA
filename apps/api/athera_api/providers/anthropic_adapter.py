"""محوّل Anthropic | Anthropic adapter (§32، ADR-0003).

أحد موضعين فقط يُسمح فيهما باستيراد SDK مزود. الاستيراد كسول: الحزمة ليست
تبعية إلزامية لتشغيل الاختبارات، والبنية تعمل بلا أي مزود (`null`).

ما لا يفعله هذا المحوّل: لا يحوّل نصًّا إلى «حقيقة»، ولا يمرّ به شيء إلى
الذاكرة الموثقة. كل ذلك يقع خلف البوابة وحواجز النزاهة في §4 و§8.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from time import perf_counter

from .base import ModelProvider, ModelRequest, ModelResponse, ModelUsage

# أحدث عائلة نماذج Claude. النسخة صريحة لا «الأحدث»: تغيّر النموذج تحت
# التحليل نفسه يجعل نتيجتين غير قابلتين للمقارنة بلا أن يتغيّر شيء ظاهر.
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EMBEDDING_NOTE = (
    "Anthropic لا يقدّم واجهة تضمين؛ التضمين يأتي من مزوّد مستقل (§32.4)."
)


class AnthropicEmbeddingUnsupported(NotImplementedError):
    """يُرفع صراحةً بدل إعادة متجهات صفرية.

    إعادة أصفار كانت ستمرّ صامتة عبر pgvector فتُنتج جوارًا عشوائيًّا يبدو
    نتيجة بحث دلالي.
    """


def _split_system(request: ModelRequest) -> tuple[str | None, list[dict[str, str]]]:
    """Anthropic يفصل رسالة النظام عن المحادثة، بخلاف الواجهة المحايدة."""
    system_parts = [m.content for m in request.messages if m.role == "system"]
    turns = [
        {"role": m.role, "content": m.content}
        for m in request.messages
        if m.role in ("user", "assistant")
    ]
    return ("\n\n".join(system_parts) or None), turns


def _usage(raw, latency_ms: int) -> ModelUsage:
    return ModelUsage(
        input_tokens=getattr(raw, "input_tokens", None) if raw else None,
        output_tokens=getattr(raw, "output_tokens", None) if raw else None,
        latency_ms=latency_ms,
    )


def _text(response) -> str:
    blocks = getattr(response, "content", None) or []
    return "".join(
        getattr(block, "text", "") for block in blocks
        if getattr(block, "type", "") == "text"
    )


class AnthropicAdapter(ModelProvider):
    name = "anthropic"

    def __init__(self, api_key: str, default_model: str = DEFAULT_MODEL,
                 workspace_id: str = "") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the anthropic provider")
        self._api_key = api_key
        self._default_model = default_model
        self._workspace_id = workspace_id or ""
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic  # noqa: PLC0415 — استيراد كسول مقصود

            # مفتاح مرتبط بهوية يتطلب `anthropic-workspace-id`؛ ومفتاح مرتبط
            # بمساحة عمل لا يحتاجها. الترويسة تُرسل إن ضُبطت وحدها، فيعمل
            # النوعان بلا فرض إعداد لا يلزم أحدهما.
            #
            # وهي تفصيل مزوّد بحت، فموضعها هنا لا في المنسّق ولا في الموجّه.
            headers = {"anthropic-workspace-id": self._workspace_id} if self._workspace_id else None
            self._client = AsyncAnthropic(api_key=self._api_key, default_headers=headers)
        return self._client

    async def generate_structured(self, request: ModelRequest) -> ModelResponse:
        """يستخدم أداة إجبارية عند وجود مخطط — لا «التزم بالـJSON» في التعليمة.

        الطلب النصي بالالتزام بمخطط يفشل صامتًا فيعيد نصًّا يشبه JSON؛ وأداة
        بمخطط إمّا تنجح وإمّا تفشل صراحةً.
        """
        started = perf_counter()
        client = self._get_client()
        model = request.model or self._default_model
        system, turns = _split_system(request)

        kwargs: dict = {
            "model": model,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or 4096,
        }
        if system:
            kwargs["system"] = system

        structured = None
        if request.schema:
            kwargs["tools"] = [{
                "name": "emit_result",
                "description": "Return the result using this exact schema.",
                "input_schema": request.schema,
            }]
            kwargs["tool_choice"] = {"type": "tool", "name": "emit_result"}

        response = await client.messages.create(**kwargs)
        latency_ms = int((perf_counter() - started) * 1000)

        if request.schema:
            for block in getattr(response, "content", None) or []:
                if getattr(block, "type", "") == "tool_use":
                    structured = dict(getattr(block, "input", {}) or {})
                    break

        return ModelResponse(
            content=_text(response) or (json.dumps(structured, ensure_ascii=False)
                                        if structured else ""),
            structured=structured,
            usage=_usage(getattr(response, "usage", None), latency_ms),
            provider=self.name, model=model,
        )

    async def tool_call(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        client = self._get_client()
        model = request.model or self._default_model
        system, turns = _split_system(request)

        kwargs: dict = {
            "model": model,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or 4096,
            "tools": request.tools,
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)
        latency_ms = int((perf_counter() - started) * 1000)

        calls = [
            {"name": getattr(block, "name", ""), "input": dict(getattr(block, "input", {}) or {})}
            for block in (getattr(response, "content", None) or [])
            if getattr(block, "type", "") == "tool_use"
        ]
        return ModelResponse(
            content=_text(response), structured={"tool_calls": calls} if calls else None,
            usage=_usage(getattr(response, "usage", None), latency_ms),
            provider=self.name, model=model,
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[str]:
        client = self._get_client()
        model = request.model or self._default_model
        system, turns = _split_system(request)

        kwargs: dict = {
            "model": model,
            "messages": turns,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or 4096,
        }
        if system:
            kwargs["system"] = system

        async with client.messages.stream(**kwargs) as stream:
            async for chunk in stream.text_stream:
                yield chunk

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        raise AnthropicEmbeddingUnsupported(DEFAULT_EMBEDDING_NOTE)
