"""Phase 4 tests: AI abstraction, structured output, retry/repair, providers."""

from __future__ import annotations

import json
import unittest
from unittest import mock

import requests

from qm_training.ai.factory import create_provider, create_provider_or_mock
from qm_training.ai.mock import DEFAULT_QUESTIONS, MockAIProvider
from qm_training.ai.providers import DeepSeekProvider
from qm_training.ai.schema import extract_json, parse_questions, parse_theme
from qm_training.ai.service import AIService
from qm_training.core.config import Settings
from qm_training.core.errors import AIProviderError, AIValidationError

MATERIAL = "Materi keselamatan kerja: gunakan APD, periksa peralatan, tangani tumpahan kimia."


def questions_json(count: int = 5, answer: str = "jawaban") -> str:
    return json.dumps(
        {"questions": [{"question": f"Pertanyaan {i}", "answer": answer} for i in range(1, count + 1)]}
    )


class TestParsing(unittest.TestCase):
    def test_parse_theme(self) -> None:
        self.assertEqual(parse_theme('{"theme": "Keselamatan"}'), "Keselamatan")

    def test_parse_theme_with_code_fence(self) -> None:
        self.assertEqual(parse_theme('```json\n{"theme": "X"}\n```'), "X")

    def test_parse_theme_invalid(self) -> None:
        with self.assertRaises(AIValidationError):
            parse_theme("bukan json")

    def test_parse_questions_valid(self) -> None:
        pairs = parse_questions(questions_json())
        self.assertEqual(len(pairs), 5)

    def test_parse_questions_wrong_count(self) -> None:
        for count in (4, 6):
            with self.assertRaises(AIValidationError):
                parse_questions(questions_json(count))

    def test_parse_questions_empty_answer(self) -> None:
        with self.assertRaises(AIValidationError):
            parse_questions(questions_json(5, answer="   "))

    def test_extract_json_with_text_around(self) -> None:
        payload = extract_json('Berikut hasilnya: {"theme": "A"} semoga membantu')
        self.assertEqual(payload["theme"], "A")

    def test_parse_questions_rejects_long_question(self) -> None:
        from qm_training.ai.schema import MAX_QUESTION_CHARS

        raw = json.dumps(
            {"questions": [{"question": "x" * (MAX_QUESTION_CHARS + 1), "answer": "ok"} for _ in range(5)]}
        )
        with self.assertRaises(AIValidationError):
            parse_questions(raw)

    def test_parse_questions_rejects_long_answer(self) -> None:
        from qm_training.ai.schema import MAX_ANSWER_CHARS

        raw = json.dumps(
            {"questions": [{"question": "singkat?", "answer": "y" * (MAX_ANSWER_CHARS + 1)} for _ in range(5)]}
        )
        with self.assertRaises(AIValidationError):
            parse_questions(raw)

    def test_parse_answer_rejects_long_answer(self) -> None:
        from qm_training.ai.schema import MAX_ANSWER_CHARS, parse_answer

        with self.assertRaises(AIValidationError):
            parse_answer(json.dumps({"answer": "z" * (MAX_ANSWER_CHARS + 1)}))


class TestService(unittest.TestCase):
    def test_analyze_success(self) -> None:
        result = AIService(MockAIProvider()).analyze(MATERIAL)
        self.assertTrue(result.theme)
        self.assertEqual(len(result.questions), 5)

    def test_exactly_five_questions(self) -> None:
        result = AIService(MockAIProvider()).analyze(MATERIAL)
        self.assertEqual(len(result.questions), 5)
        self.assertTrue(all(qa.answer for qa in result.questions))

    def test_retry_after_provider_error(self) -> None:
        provider = MockAIProvider(theme_provider_errors=1, question_provider_errors=1)
        result = AIService(provider, max_retries=2).analyze(MATERIAL)
        self.assertEqual(len(result.questions), 5)

    def test_retry_after_malformed(self) -> None:
        provider = MockAIProvider(theme_malformed=1, question_malformed=1)
        result = AIService(provider, max_retries=2).analyze(MATERIAL)
        self.assertEqual(len(result.questions), 5)

    def test_persistent_failure_raises(self) -> None:
        provider = MockAIProvider(theme_provider_errors=99)
        with self.assertRaises(AIValidationError):
            AIService(provider, max_retries=1).analyze(MATERIAL)

    def test_wrong_count_then_valid(self) -> None:
        provider = MockAIProvider(question_count=4)
        # always 4 -> should ultimately fail after retries
        with self.assertRaises(AIValidationError):
            AIService(provider, max_retries=1).generate_questions(MATERIAL, "Tema")


class TestProviderFactory(unittest.TestCase):
    def test_mock_provider(self) -> None:
        provider = create_provider(Settings(ai_provider="mock"))
        self.assertIsInstance(provider, MockAIProvider)

    def test_deepseek_requires_key(self) -> None:
        with self.assertRaises(AIProviderError):
            create_provider(Settings(ai_provider="deepseek", deepseek_api_key=None))

    def test_deepseek_with_key(self) -> None:
        provider = create_provider(Settings(ai_provider="deepseek", deepseek_api_key="dummy"))
        self.assertIsInstance(provider, DeepSeekProvider)

    def test_fallback_to_mock(self) -> None:
        provider, is_mock = create_provider_or_mock(Settings(ai_provider="openai", openai_api_key=None))
        self.assertTrue(is_mock)
        self.assertIsInstance(provider, MockAIProvider)

    def test_switching_providers(self) -> None:
        for name in ("deepseek", "openai", "gemini"):
            settings = Settings(ai_provider=name, deepseek_api_key="k", openai_api_key="k", gemini_api_key="k")
            provider = create_provider(settings)
            self.assertEqual(provider.name, name)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


class TestHttpProviderErrors(unittest.TestCase):
    def test_http_error_maps_to_ai_error(self) -> None:
        provider = DeepSeekProvider(api_key="k")
        with mock.patch("qm_training.ai.providers.requests.post", return_value=_FakeResponse(500, text="boom")):
            with self.assertRaises(AIProviderError):
                provider.chat("sys", "user")

    def test_timeout_maps_to_ai_error(self) -> None:
        provider = DeepSeekProvider(api_key="k")
        with mock.patch("qm_training.ai.providers.requests.post", side_effect=requests.Timeout("timeout")):
            with self.assertRaises(AIProviderError):
                provider.chat("sys", "user")

    def test_success_parsing(self) -> None:
        provider = DeepSeekProvider(api_key="k")
        payload = {"choices": [{"message": {"content": "hello"}}]}
        with mock.patch("qm_training.ai.providers.requests.post", return_value=_FakeResponse(200, payload)):
            self.assertEqual(provider.chat("sys", "user"), "hello")


if __name__ == "__main__":
    unittest.main()
