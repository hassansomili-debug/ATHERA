"""طبقة السياسة أمام المزود | Policy layer in front of any provider (§32، §36.3).

كل استدعاء يمر من هنا: يفحص تصنيف البيانات أولًا، ثم ينفّذ، ثم يسجّل التكلفة
والـlatency في `model_runs`. لا مسار جانبي.
"""
from __future__ import annotations

import datetime as dt
import uuid
import importlib.util
from time import perf_counter
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..errors import AtheraError
from ..models.runs import ModelRun
from .base import CLASSIFICATION_ORDER, ModelProvider, ModelRequest, ModelResponse
from .null_provider import NullProvider


# أي إعداد يحمل مفتاح كل مزوّد. الإضافة هنا سطر واحد، لا تغيير في المنطق.
_KEY_BY_PROVIDER: Final[dict[str, str]] = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
}

# اسم الحزمة التي يحتاجها كل محوّل — تُفحص وجودًا لا تُستورد.
_SDK_BY_PROVIDER: Final[dict[str, str]] = {
    "openai": "openai",
    "anthropic": "anthropic",
}


def build_provider() -> ModelProvider:
    settings = get_settings()
    if settings.model_provider == "anthropic":
        from .anthropic_adapter import AnthropicAdapter  # noqa: PLC0415

        return AnthropicAdapter(api_key=settings.anthropic_api_key,
                                workspace_id=settings.anthropic_workspace_id)
    if settings.model_provider == "openai":
        from .openai_adapter import OpenAIAdapter  # noqa: PLC0415

        return OpenAIAdapter(api_key=settings.openai_api_key)
    if settings.model_provider != "null":
        # اسم مزود غير معروف يُرفض ولا يسقط بصمت إلى `null`: تشغيل ظنّ صاحبه
        # أنه يستدعي نموذجًا بينما لا يستدعي شيئًا أسوأ من تشغيل يفشل بوضوح.
        raise AtheraError("provider.unknown", status_code=500,
                          provider=settings.model_provider)
    return NullProvider()


def provider_readiness() -> tuple[str, bool, str]:
    """(اسم المزوّد، جاهز؟، سبب عدم الجهوزية) — بلا كشف أي سرّ.

    **اسم المزوّد ليس دليل جهوزية.** ضبط `MODEL_PROVIDER=openai` بلا مفتاح
    يجعل الإعلان يقول «الذكاء متاح» بينما أول طلب يفشل. وهذا نفس العطب
    الذي أصلحناه في التخزين، ولا سبب لتكراره هنا.

    ولا تُعاد قيمة المفتاح ولا طوله ولا بادئته — الجهوزية `bool` والسبب رمز.
    """
    settings = get_settings()
    provider = settings.model_provider

    if provider == "null":
        return provider, False, "provider_disabled"
    if provider not in _KEY_BY_PROVIDER:
        return provider, False, "provider_unknown"

    if not (getattr(settings, _KEY_BY_PROVIDER[provider], "") or "").strip():
        return provider, False, "missing_api_key"

    # **والحزمة نفسها.** المحوّل يستوردها استيرادًا كسولًا داخل الدالة — وهو
    # مقصود ليبقى المزوّد خارج مسار الاستيراد العام — لكن أثره أن غيابها لا
    # يظهر إلا عند أول استدعاء حقيقي. فتُعلن الجهوزية `ready` بينما كل طلب
    # يفشل. ثالث صورة من عطب واحد: الاسم ليس دليل القدرة.
    if importlib.util.find_spec(_SDK_BY_PROVIDER[provider]) is None:
        return provider, False, "sdk_missing"

    return provider, True, "ready"


def provider_ready() -> bool:
    return provider_readiness()[1]


def classification_allowed(classification: str, ceiling: str) -> bool:
    try:
        return CLASSIFICATION_ORDER.index(classification) <= CLASSIFICATION_ORDER.index(ceiling)
    except ValueError:
        return False


class ModelGateway:
    def __init__(self, provider: ModelProvider | None = None) -> None:
        self._provider = provider or build_provider()
        self._settings = get_settings()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def generate_structured(
        self,
        session: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        request: ModelRequest,
        agent_run_id: uuid.UUID | None = None,
    ) -> tuple[ModelResponse, ModelRun]:
        ceiling = self._settings.model_external_send_max_classification
        # المزود المحلي/الصفري لا يغادر بياناته الخادم، فلا يخضع لسقف الإرسال الخارجي.
        if self._provider.name != "null" and not classification_allowed(request.classification, ceiling):
            raise AtheraError(
                "provider.disabled_for_classification",
                status_code=403,
                classification=request.classification,
                ceiling=ceiling,
            )

        started = perf_counter()
        status, error = "ok", None
        try:
            response = await self._provider.generate_structured(request)
        except Exception as exc:  # noqa: BLE001 — نسجّل الفشل ثم نعيد رفعه
            status, error = "error", str(exc)[:500]
            response = ModelResponse(content="", provider=self._provider.name, model=request.model or "")
            raise
        finally:
            run = ModelRun(
                tenant_id=tenant_id,
                agent_run_id=agent_run_id,
                provider=self._provider.name,
                model=request.model or response.model or "unknown",
                operation="generate_structured",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                cost_usd=response.usage.cost_usd,
                latency_ms=response.usage.latency_ms or int((perf_counter() - started) * 1000),
                status=status,
                max_classification_sent=request.classification,
                error=error,
                created_at=dt.datetime.now(dt.UTC),
            )
            session.add(run)
            await session.flush()

        return response, run
