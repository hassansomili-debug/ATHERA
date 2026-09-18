"""بوابة مزود النموذج | Model Provider Gateway (§32، ADR-0003).

واجهة واحدة بأربع عمليات. لا تظهر أنواع أو حمولات خاصة بمزود بعينه خارج
هذا المجلد — يفرض ذلك `import-linter` في pyproject.toml، لا التوثيق.
"""
from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

# ترتيب تصنيفات الحساسية | data classification ordering (§36، Data Classification Matrix)
CLASSIFICATION_ORDER = ("C0", "C1", "C2", "C3", "C4")

# ══════════ قدرةُ المزوّد على إزالة التكرار (RC-T1-H2-B4) ══════════
#
# **ولا يعرف الموجِّهُ ولا المنسّقُ بائعًا.** يسأل عن قدرةٍ مُعلَنة، فيقرّر.
# وADR-0003 قائم: أسماءُ ترويسات البائعين وخياراتُه تبقى في `providers/`.
#
# `SERVER_DEDUPLICATED` — أثبتت موادُّ المزوّد الرسميّةُ أنّ مفتاحًا
#   يُرسله العميلُ يمنع تنفيذًا مكرَّرًا للطلب نفسِه عند الخادم.
#
# `UNPROVEN` — لم يُثبَت ذلك. **وهو الافتراض**، ولا يُرقّى بترويسةٍ اسمُها
#   موحٍ ولا بمعرّفِ طلبٍ تشخيصيّ ولا بعدّادِ إعادةٍ في SDK.
SERVER_DEDUPLICATED = "server_deduplicated"
UNPROVEN = "unproven"


@dataclass(slots=True)
class Message:
    role: str
    content: str


@dataclass(slots=True)
class ModelRequest:
    """طلب محايد تجاه المزود | vendor-neutral request."""

    messages: list[Message]
    schema: dict[str, Any] | None = None
    model: str | None = None
    temperature: float = 0.0
    max_output_tokens: int | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    # أعلى تصنيف حساسية داخل هذا الطلب — تفحصه البوابة قبل أي إرسال.
    classification: str = "C0"
    locale: str = "ar"


@dataclass(slots=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None


@dataclass(slots=True)
class ModelResponse:
    content: str
    structured: dict[str, Any] | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    provider: str = ""
    model: str = ""


class ModelProvider(abc.ABC):
    """الواجهة الموحدة الواردة في §32."""

    name: str = "abstract"

    #: قدرةُ هذا المزوّد على إزالة التكرار — **والافتراضُ عدمُها**.
    #:
    #: فمن أراد ترقيتَها فعليه البرهان، ولا يُرقّى محوّلٌ بالسكوت. وانظر
    #: `SERVER_DEDUPLICATED` أعلاه.
    model_idempotency_capability: str = UNPROVEN

    @abc.abstractmethod
    async def generate_structured(self, request: ModelRequest) -> ModelResponse: ...

    @abc.abstractmethod
    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]: ...

    @abc.abstractmethod
    def stream(self, request: ModelRequest) -> AsyncIterator[str]: ...

    @abc.abstractmethod
    async def tool_call(self, request: ModelRequest) -> ModelResponse: ...
