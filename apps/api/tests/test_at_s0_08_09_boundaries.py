"""AT-S0-08/09 — استقلال المزود وحدود الواجهة (§32، §38.6.8، ADR-0003)."""
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
WEB_SRC = REPO_ROOT / "apps" / "web"
API_SRC = REPO_ROOT / "apps" / "api" / "athera_api"

VENDOR_TOKENS = ("openai", "anthropic", "google.generativeai", "cohere", "mistralai")


def test_no_vendor_sdk_outside_providers_package():
    """AT-S0-08 — لا استيراد لمزود خارج athera_api/providers/."""
    offenders = []
    for path in API_SRC.rglob("*.py"):
        if "providers" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and any(v in stripped for v in VENDOR_TOKENS):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {stripped}")
    assert not offenders, "vendor SDK imported outside the adapter layer:\n" + "\n".join(offenders)


def test_web_contains_no_provider_sdk_or_api_key():
    """AT-S0-09 — الواجهة لا تحمل SDK مزود ولا مفتاحًا (§38.6.8)."""
    if not WEB_SRC.exists():
        pytest.skip("web app not present")
    offenders = []
    key_pattern = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY|ANTHROPIC_API_KEY)")
    for path in WEB_SRC.rglob("*"):
        if not path.is_file() or "node_modules" in path.parts or ".next" in path.parts:
            continue
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".json", ".mjs"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if key_pattern.search(text):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: provider key reference")
        if path.name == "package.json" and any(v in text for v in VENDOR_TOKENS):
            offenders.append(f"{path.relative_to(REPO_ROOT)}: provider SDK dependency")
    assert not offenders, "the web client must never reach a model provider:\n" + "\n".join(offenders)


def test_web_csp_blocks_provider_domains():
    config = WEB_SRC / "next.config.mjs"
    if not config.exists():
        pytest.skip("next.config.mjs not present")
    text = config.read_text(encoding="utf-8")
    assert "connect-src" in text, "CSP must restrict connect-src (§38.6.8)"
    assert "api.openai.com" not in text, "provider domains must not be allowed from the browser"


@pytest.mark.asyncio
async def test_null_provider_satisfies_the_full_interface():
    """تبديل المزود لا يكسر شيئًا — وهذا معنى Provider Independent."""
    from athera_api.providers.base import Message, ModelProvider, ModelRequest
    from athera_api.providers.null_provider import NullProvider

    provider = NullProvider()
    assert isinstance(provider, ModelProvider)
    request = ModelRequest(messages=[Message(role="user", content="مرحبًا")])
    response = await provider.generate_structured(request)
    assert response.provider == "null"
    vectors = await provider.embed(["نص", "text"])
    assert len(vectors) == 2 and len(vectors[0]) == 1536


def test_classification_ceiling_blocks_sensitive_data():
    """§36.3 — القيمة الافتراضية هي الأشد تقييدًا، والسقف يُحترم."""
    from athera_api.providers.gateway import classification_allowed

    assert classification_allowed("C0", "C1")
    assert classification_allowed("C1", "C1")
    assert not classification_allowed("C2", "C1")
    assert not classification_allowed("C4", "C1")
    assert not classification_allowed("unknown", "C1")
