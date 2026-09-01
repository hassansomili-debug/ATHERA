"""توافق محوّل Anthropic مع الـSDK المثبَّت فعلًا.

**لا مزوّد وهمي هنا.** المزوّد الوهمي يثبت أن أثيرا تتصرّف صحيحًا؛ ولا يثبت
أن ما تُرسله يقبله الـSDK. والعطب الذي أوقف الإنتاج كان من هذا النوع
بالضبط: معامل واحد أزالته الواجهة، ولا اختبار يوقظه لأن كل الاختبارات
تتحدث إلى بديل.

فهذه الاختبارات تقرأ توقيع الـSDK نفسه وتقابله بما يبنيه المحوّل — بلا
شبكة، وبلا مفتاح، وبلا أي طلب حقيقي.
"""
import inspect

import pytest

anthropic = pytest.importorskip(
    "anthropic", reason="حزم المزودين اختيارية؛ يُتخطّى حيث لا تُثبَّت"
)


def _create_params() -> set[str]:
    import anthropic.resources.messages as messages

    return set(inspect.signature(messages.AsyncMessages.create).parameters)


def test_every_kwarg_the_adapter_sends_is_accepted_by_the_sdk():
    """كل مفتاح يبنيه المحوّل موجود في التوقيع — وإلا سقط أول استدعاء."""
    sent = {"model", "messages", "max_tokens", "system", "tools", "tool_choice"}
    accepted = _create_params()
    unknown = sent - accepted
    assert not unknown, f"معاملات يرسلها المحوّل ولا يقبلها الـSDK: {unknown}"


def test_temperature_is_not_sent_because_the_api_removed_it():
    """حارس انحدار: إعادته تكسر الإنتاج بصمت في الاختبارات الوهمية."""
    import pathlib

    source = pathlib.Path("athera_api/providers/anthropic_adapter.py").read_text(encoding="utf-8")
    assert '"temperature": request.temperature' not in source
    assert "temperature" not in _create_params()


def test_usage_fields_the_adapter_reads_exist():
    """الرصد يعتمدهما: رموز الدخل والخرج."""
    from anthropic.types import Usage

    assert {"input_tokens", "output_tokens"} <= set(Usage.model_fields)


def test_streaming_surface_exists():
    import anthropic.resources.messages as messages

    assert hasattr(messages.AsyncMessages, "stream")


def test_error_classes_the_gateway_may_surface_exist():
    for name in ("APITimeoutError", "RateLimitError", "AuthenticationError", "BadRequestError"):
        assert hasattr(anthropic, name), name


def test_adapter_accepts_an_optional_workspace_id_without_requiring_it():
    """مفتاح مساحة العمل لا يحتاج الترويسة، ومفتاح الهوية يحتاجها."""
    from athera_api.providers.anthropic_adapter import AnthropicAdapter

    params = inspect.signature(AnthropicAdapter.__init__).parameters
    assert params["workspace_id"].default == ""
