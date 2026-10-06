"""AI provider abstraction.

Business logic must not depend on DeepSeek directly. Any provider only has to
answer a chat request with raw text; content validation lives in the service.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from qm_training.core.errors import AIProviderError


class AIProvider(ABC):
    name: str = "base"

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @abstractmethod
    def chat(self, system: str, user: str) -> str:
        """Return the raw assistant text for a system+user prompt."""
        raise NotImplementedError

    def _require_key(self) -> str:
        if not self.api_key:
            raise AIProviderError(f"API key untuk provider '{self.name}' belum diatur")
        return self.api_key
