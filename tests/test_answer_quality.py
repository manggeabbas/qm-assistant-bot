"""Feature 2 tests: informative 1-3 sentence answers in KUNCI JAWABAN."""

from __future__ import annotations

import re
import shutil
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from qm_training.ai.mock import MockAIProvider
from qm_training.ai.prompts import QUESTIONS_INSTRUCTION
from qm_training.ai.schema import MAX_ANSWER_CHARS, MAX_QUESTION_CHARS
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.bot.adapters import MockTelegramAdapter
from qm_training.bot.states import State
from qm_training.bot.workflow import BTN_CONFIRM, BTN_DONE, BTN_USE_THEME
from qm_training.core.config import Settings
from qm_training.document.engine import generate as real_generate
from qm_training.document.schema import QAPair
from qm_training.testing.fixtures import build_docx
from qm_training.validation.models import ValidationReport

BASE = Path("output/phase13_answers")
MATERIAL: Path

# 5 short questions (<= MAX_QUESTION_CHARS) with informative 2-sentence answers.
QUESTIONS = [
    QAPair(
        "Apa tujuan utama briefing keselamatan kerja?",
        "Briefing bertujuan mencegah kecelakaan kerja dan memastikan personil memahami prosedur. "
        "Semua personil wajib mengikuti instruksi keselamatan yang diberikan.",
    ),
    QAPair(
        "Alat pelindung diri apa yang wajib digunakan?",
        "Alat pelindung diri meliputi jas laboratorium, sarung tangan, kacamata pelindung, dan sepatu tertutup. "
        "Semua pelindung wajib dipakai sebelum masuk area kerja.",
    ),
    QAPair(
        "Apa yang dilakukan bila menemukan bahan kimia tanpa label?",
        "Bahan tanpa label harus dipisahkan dan dilaporkan kepada penanggung jawab. "
        "Identifikasi dilakukan agar bahan tidak salah digunakan.",
    ),
    QAPair(
        "Mengapa peralatan harus diperiksa sebelum digunakan?",
        "Pemeriksaan memastikan peralatan berfungsi dengan benar. "
        "Hal ini mencegah kerusakan alat dan risiko cedera bagi operator.",
    ),
    QAPair(
        "Apa tindakan saat terjadi tumpahan bahan kimia?",
        "Area harus segera diamankan dan spill kit digunakan sesuai prosedur. "
        "Kejadian kemudian dilaporkan kepada atasan dan petugas K3.",
    ),
]


def setUpModule() -> None:
    global MATERIAL
    if BASE.exists():
        shutil.rmtree(BASE)
    BASE.mkdir(parents=True, exist_ok=True)
    MATERIAL = build_docx(BASE / "material.docx")


def _sentences(text: str) -> int:
    return len([s for s in re.split(r"[.!?]+", text) if s.strip()])


def _text_of(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


class TestPromptGuidance(unittest.TestCase):
    def test_prompt_requires_informative_grounded_answers(self) -> None:
        self.assertIn("1-3 kalimat", QUESTIONS_INSTRUCTION)
        self.assertIn("berdasarkan materi", QUESTIONS_INSTRUCTION)
        self.assertIn("JANGAN" if "JANGAN" in QUESTIONS_INSTRUCTION else "jangan", QUESTIONS_INSTRUCTION)


class TestAnswerQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        store = SessionStore(BASE / "sessions")
        workflow = Workflow(
            store=store,
            ai_service=AIService(MockAIProvider(questions=[QAPair(q.question, q.answer) for q in QUESTIONS])),
            settings=Settings(ai_provider="mock"),
            generate_docx=real_generate,
            convert_pdf=lambda docx, out_dir=None, **k: Path(out_dir or Path(docx).parent) / f"{Path(docx).stem}.pdf",
            validate=lambda d, p=None: ValidationReport(),
        )
        cls.adapter = MockTelegramAdapter(workflow, slow_threshold=5.0)
        cls.store = store

        cls.adapter.receive("1", "/new_training", update_id=1)
        cls.adapter.receive("1", document_path=MATERIAL, update_id=2)
        cls.adapter.receive("1", BTN_USE_THEME, update_id=3)
        for i, value in enumerate(["2026-QM-A-01", "2026/09/15", "Area", "Trainer", "REGU A", "15"], start=4):
            cls.adapter.receive("1", value, update_id=i)
        cls.preview = cls.adapter.receive("1", BTN_CONFIRM, update_id=10)
        cls.session_after_preview = store.get("1")
        cls.adapter.receive("1", BTN_CONFIRM, update_id=11)
        cls.adapter.receive("1", BTN_DONE, update_id=12)
        cls.session = store.get("1")

    def test_9_exactly_five_questions(self) -> None:
        self.assertEqual(len(self.session.questions), 5)

    def test_10_each_question_has_answer(self) -> None:
        for item in self.session.questions:
            self.assertIn("answer", item)

    def test_11_answer_not_empty(self) -> None:
        for item in self.session.questions:
            self.assertTrue(item["answer"].strip())

    def test_12_answers_are_1_to_3_sentences(self) -> None:
        for item in self.session.questions:
            count = _sentences(item["answer"])
            self.assertGreaterEqual(count, 1, item["answer"])
            self.assertLessEqual(count, 3, item["answer"])

    def test_13_answer_more_informative_than_a_phrase(self) -> None:
        for item in self.session.questions:
            self.assertGreater(len(item["answer"]), 40, "jawaban terlalu pendek/sekadar frasa")
            self.assertLessEqual(len(item["answer"]), MAX_ANSWER_CHARS)

    def test_14_questions_stay_short(self) -> None:
        for item in self.session.questions:
            self.assertLessEqual(len(item["question"]), MAX_QUESTION_CHARS)

    def test_15_17_single_question_set_and_generation(self) -> None:
        self.assertEqual(self.session.generate_questions_calls, 1)
        self.assertTrue(self.session.question_set_created)
        self.assertEqual(self.session.questions, self.session_after_preview.questions)

    def test_16_preview_sent_once(self) -> None:
        previews = [m for m in self.preview if "Preview Pertanyaan" in m.text]
        self.assertEqual(len(previews), 1)
        self.assertEqual(self.session.preview_sent, 1)

    def test_answers_present_in_docx_answer_key(self) -> None:
        docx = Path(self.session.output_docx)
        self.assertTrue(docx.exists())
        full = _text_of(Document(str(docx)).element.body)
        for item in self.session.questions:
            self.assertIn(item["answer"], full, "jawaban tidak ada di KUNCI JAWABAN")

    def test_completed(self) -> None:
        self.assertEqual(self.session.state, State.COMPLETED.value)


if __name__ == "__main__":
    unittest.main()
