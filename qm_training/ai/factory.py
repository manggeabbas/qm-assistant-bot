"""Provider factory (configuration-driven, no hard-coded provider in logic)."""

from __future__ import annotations

from qm_training.ai.base import AIProvider
from qm_training.ai.mock import MockAIProvider
from qm_training.ai.providers import DeepSeekProvider, GeminiProvider, OpenAIProvider
from qm_training.core.config import Settings
from qm_training.core.errors import AIProviderError

_REGISTRY = {
    "deepseek": DeepSeekProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def create_provider(settings: Settings) -> AIProvider:
    name = (settings.ai_provider or "deepseek").lower()
    if name == "mock":
        return MockAIProvider()
    provider_class = _REGISTRY.get(name)
    if provider_class is None:
        raise AIProviderError(f"provider AI tidak dikenal: {name}")
    key = settings.api_key_for(name)
    if not key:
        raise AIProviderError(
            f"API key untuk provider '{name}' belum tersedia. Set variabel environment-nya di .env"
        )
    return provider_class(api_key=key, model=settings.ai_model, timeout=settings.ai_timeout_seconds)


def create_provider_or_mock(settings: Settings) -> tuple[AIProvider, bool]:
    """Return (provider, is_mock). Falls back to mock when no credential exists."""
    if (settings.ai_provider or "").lower() == "mock":
        return MockAIProvider(), True
    try:
        return create_provider(settings), False
    except AIProviderError:
        return MockAIProvider(), True
