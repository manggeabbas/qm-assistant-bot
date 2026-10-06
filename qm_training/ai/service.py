"""AI service: theme extraction + question generation with retry/repair."""

from __future__ import annotations

from dataclasses import dataclass

from qm_training.ai.base import AIProvider
from qm_training.ai.prompts import SYSTEM_PROMPT, answer_prompt, questions_prompt, repair_note, theme_prompt
from qm_training.ai.schema import parse_answer, parse_questions, parse_theme
from qm_training.core.errors import AIProviderError, AIValidationError
from qm_training.document.schema import QAPair


@dataclass
class AIResult:
    theme: str
    questions: list[QAPair]


class AIService:
    def __init__(self, provider: AIProvider, max_retries: int = 2) -> None:
        self.provider = provider
        self.max_retries = max(0, max_retries)

    def _chat_with_repair(self, user_prompt: str, parser):
        last_error: Exception | None = None
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            prompt = user_prompt if attempt == 0 else user_prompt + repair_note(str(last_error))
            try:
                raw = self.provider.chat(SYSTEM_PROMPT, prompt)
                return parser(raw)
            except AIProviderError as exc:
                last_error = exc
            except AIValidationError as exc:
                last_error = exc
        raise AIValidationError(f"AI gagal setelah {attempts} percobaan: {last_error}")

    def extract_theme(self, material_text: str) -> str:
        return self._chat_with_repair(theme_prompt(material_text), parse_theme)

    def generate_questions(self, material_text: str, theme: str) -> list[QAPair]:
        return self._chat_with_repair(questions_prompt(material_text, theme), parse_questions)

    def generate_answer(self, material_text: str, question: str) -> str:
        return self._chat_with_repair(answer_prompt(material_text, question), parse_answer)

    def analyze(self, material_text: str) -> AIResult:
        theme = self.extract_theme(material_text)
        questions = self.generate_questions(material_text, theme)
        return AIResult(theme=theme, questions=questions)
