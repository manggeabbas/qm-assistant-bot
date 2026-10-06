"""Mock AI provider for tests and credential-less runs.

This is a mock; it must never be presented as a real integration test.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from qm_training.ai.base import AIProvider
from qm_training.core.errors import AIProviderError
from qm_training.document.schema import QAPair

DEFAULT_QUESTIONS = [
    QAPair("Apa tujuan utama briefing keselamatan kerja di laboratorium?",
           "Mencegah kecelakaan kerja dan memastikan prosedur dipahami."),
    QAPair("Sebutkan alat pelindung diri yang wajib digunakan.",
           "Jas laboratorium, sarung tangan, kacamata, sepatu tertutup."),
    QAPair("Apa yang dilakukan bila menemukan bahan kimia tanpa label?",
           "Pisahkan dan laporkan ke penanggung jawab."),
    QAPair("Mengapa peralatan harus diperiksa sebelum digunakan?",
           "Agar berfungsi benar dan mencegah cedera."),
    QAPair("Apa tindakan saat terjadi tumpahan bahan kimia?",
           "Amankan area, gunakan spill kit, lalu laporkan."),
]


@dataclass
class MockAIProvider(AIProvider):
    theme: str = "Keselamatan Kerja di Laboratorium"
    questions: list[QAPair] = field(default_factory=lambda: list(DEFAULT_QUESTIONS))
    answer_text: str = "Jawaban hasil regenerasi berdasarkan materi."
    theme_provider_errors: int = 0
    theme_malformed: int = 0
    question_provider_errors: int = 0
    question_malformed: int = 0
    question_count: int | None = None  # override to simulate wrong counts

    def __post_init__(self) -> None:
        self.name = "mock"
        self.calls = 0

    def _is_theme_request(self, user: str) -> bool:
        return "TEMA:" not in user and "PERTANYAAN" not in user.upper()

    def chat(self, system: str, user: str) -> str:
        self.calls += 1
        if "PERTANYAAN:" in user:  # answer-regeneration prompt
            return json.dumps({"answer": self.answer_text}, ensure_ascii=False)
        if self._is_theme_request(user):
            if self.theme_provider_errors > 0:
                self.theme_provider_errors -= 1
                raise AIProviderError("mock theme provider error")
            if self.theme_malformed > 0:
                self.theme_malformed -= 1
                return "ini bukan json"
            return json.dumps({"theme": self.theme}, ensure_ascii=False)

        if self.question_provider_errors > 0:
            self.question_provider_errors -= 1
            raise AIProviderError("mock question provider error")
        if self.question_malformed > 0:
            self.question_malformed -= 1
            return "```json\nbukan json\n```"
        items = self.questions
        if self.question_count is not None:
            items = items[: self.question_count]
        return json.dumps(
            {"questions": [{"question": q.question, "answer": q.answer} for q in items]},
            ensure_ascii=False,
        )
