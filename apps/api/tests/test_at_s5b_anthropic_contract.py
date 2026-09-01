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


# ══════════ اسم النموذج إعدادٌ لا ثابت في الكود ══════════

def _settings(monkeypatch, **values):
    from athera_api.config import get_settings

    settings = get_settings()
    import importlib.util

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object())
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value, raising=False)
    return settings


def test_no_hardcoded_model_name_remains_in_any_provider_implementation():
    """حارس انحدار: اسم نموذج في الكود يعني ترقيةً تحتاج إعادة نشر."""
    import pathlib

    adapter = pathlib.Path("athera_api/providers/anthropic_adapter.py").read_text(encoding="utf-8")
    assert "claude-opus-5" not in adapter
    assert "DEFAULT_MODEL" not in adapter


def test_anthropic_without_a_configured_model_is_not_configured(monkeypatch):
    from athera_api.providers import gateway

    _settings(monkeypatch, model_provider="anthropic",
              anthropic_api_key="key", anthropic_model="")
    assert gateway.provider_readiness() == ("anthropic", False, "model_missing")


def test_anthropic_with_key_model_and_sdk_is_configured(monkeypatch):
    from athera_api.providers import gateway

    _settings(monkeypatch, model_provider="anthropic",
              anthropic_api_key="key", anthropic_model="claude-x")
    assert gateway.provider_readiness() == ("anthropic", True, "ready")


def test_workspace_id_stays_optional(monkeypatch):
    from athera_api.providers import gateway

    _settings(monkeypatch, model_provider="anthropic", anthropic_api_key="key",
              anthropic_model="claude-x", anthropic_workspace_id="")
    assert gateway.provider_readiness()[1] is True


def test_adapter_refuses_to_be_built_without_a_model():
    from athera_api.providers.anthropic_adapter import AnthropicAdapter

    with pytest.raises(ValueError, match="ANTHROPIC_MODEL"):
        AnthropicAdapter(api_key="key", default_model="")


def test_adapter_uses_the_configured_model_and_explicit_request_wins():
    """الأسبقية: نموذج يطلبه الخادم صراحةً ← ثم الافتراضي المُعلَن."""
    from athera_api.providers.anthropic_adapter import AnthropicAdapter
    from athera_api.providers.base import Message, ModelRequest

    adapter = AnthropicAdapter(api_key="key", default_model="configured-model")
    assert adapter._default_model == "configured-model"

    plain = ModelRequest(messages=[Message(role="user", content="x")])
    explicit = ModelRequest(messages=[Message(role="user", content="x")], model="workflow-model")
    assert (plain.model or adapter._default_model) == "configured-model"
    assert (explicit.model or adapter._default_model) == "workflow-model"


def test_workspace_header_is_sent_only_when_configured():
    from athera_api.providers.anthropic_adapter import AnthropicAdapter

    without = AnthropicAdapter(api_key="key", default_model="m")
    with_id = AnthropicAdapter(api_key="key", default_model="m", workspace_id="ws-1")
    assert without._workspace_id == ""
    assert with_id._workspace_id == "ws-1"
