"""HTTP chat providers: DeepSeek, OpenAI, Gemini.

Only transport lives here; content validation is in :mod:`qm_training.ai.schema`.
The provider is selected through configuration, never hard-coded in logic.
"""

from __future__ import annotations

import re

import requests

from qm_training.ai.base import AIProvider
from qm_training.core.errors import AIProviderError

# API keys must never reach user-facing error messages. requests embeds the
# request URL (which for Gemini carries ?key=...) in its exception text.
_KEY_PARAM_RE = re.compile(r"([?&]key=)[^&\s)'\"]+")


def _redact_secrets(text: str) -> str:
    return _KEY_PARAM_RE.sub(r"\1***", text)


class _HttpChatProvider(AIProvider):
    default_model = ""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60) -> None:
        super().__init__(api_key=api_key, model=model or self.default_model or None, timeout=timeout)

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise AIProviderError(f"{self.name}: timeout setelah {self.timeout}s") from exc
        except requests.RequestException as exc:
            raise AIProviderError(f"{self.name}: koneksi gagal ({_redact_secrets(str(exc))})") from exc
        if response.status_code != 200:
            raise AIProviderError(
                f"{self.name}: HTTP {response.status_code}: {_redact_secrets(response.text[:200])}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise AIProviderError(f"{self.name}: respons bukan JSON") from exc


class DeepSeekProvider(_HttpChatProvider):
    name = "deepseek"
    default_model = "deepseek-chat"
    endpoint = "https://api.deepseek.com/chat/completions"

    def chat(self, system: str, user: str) -> str:
        key = self._require_key()
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
        }
        data = self._post(self.endpoint, {"Authorization": f"Bearer {key}"}, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name}: struktur respons tak terduga") from exc


class OpenAIProvider(_HttpChatProvider):
    name = "openai"
    default_model = "gpt-4o-mini"
    endpoint = "https://api.openai.com/v1/chat/completions"

    def chat(self, system: str, user: str) -> str:
        key = self._require_key()
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
        }
        data = self._post(self.endpoint, {"Authorization": f"Bearer {key}"}, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name}: struktur respons tak terduga") from exc


class GeminiProvider(_HttpChatProvider):
    name = "gemini"
    default_model = "gemini-1.5-flash"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def chat(self, system: str, user: str) -> str:
        key = self._require_key()
        url = self.endpoint.format(model=self.model) + f"?key={key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
        }
        data = self._post(url, {}, payload)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name}: struktur respons tak terduga") from exc
