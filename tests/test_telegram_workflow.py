"""Phase 5 tests: Telegram workflow (mock adapter, mock AI)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qm_training.ai.mock import MockAIProvider
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.bot.adapters import MockTelegramAdapter
from qm_training.bot.states import State
from qm_training.bot.workflow import (
    BTN_CONFIRM,
    BTN_DONE,
    BTN_EDIT_DATA,
    BTN_EDIT_Q,
    BTN_EDIT_THEME,
    BTN_REGENERATE,
    BTN_SKIP,
    BTN_USE_THEME,
)
from qm_training.core.config import Settings
from qm_training.testing.datasets import make_photos
from qm_training.testing.fixtures import build_docx
from qm_training.validation.models import ValidationReport

MATERIAL: Path
PHOTOS: list[Path]


def setUpModule() -> None:
    global MATERIAL, PHOTOS
    root = Path("output/phase5")
    root.mkdir(parents=True, exist_ok=True)
    MATERIAL = build_docx(root / "material.docx")
    PHOTOS = make_photos(3, root / "photos", prefix="wf")


def fake_convert(docx_path, out_dir=None, **kwargs) -> Path:
    out = Path(out_dir or Path(docx_path).parent) / f"{Path(docx_path).stem}.pdf"
    out.write_bytes(b"%PDF-1.4\nstub\n")
    return out


def ok_validate(docx_path, pdf_path=None) -> ValidationReport:
    return ValidationReport()


def make_workflow(tmp: Path, allowed=(), ai=None, convert=fake_convert, validate=ok_validate, store=None):
    store = store or SessionStore(tmp)
    workflow = Workflow(
        store=store,
        ai_service=AIService(ai or MockAIProvider()),
        settings=Settings(ai_provider="mock", allowed_user_ids=tuple(allowed)),
        convert_pdf=convert,
        validate=validate,
    )
    return workflow, store


def run_to_data_review(adapter: MockTelegramAdapter, user: str = "1", personnel: str = "15") -> None:
    adapter.receive(user, "/new_training")
    adapter.receive(user, document_path=MATERIAL)
    adapter.receive(user, BTN_USE_THEME)
    adapter.receive(user, "2026-QM-LZ-09-03")
    adapter.receive(user, "03 September 2026")
    adapter.receive(user, "Ruang Training QM")
    adapter.receive(user, "Budi Santoso")
    adapter.receive(user, "REGU A")
    adapter.receive(user, personnel)


class TestAuthorization(unittest.TestCase):
    def test_unauthorized_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp), allowed=["42"])
            adapter = MockTelegramAdapter(workflow)
            messages = adapter.receive("1", "/new_training")
            self.assertIn("terdaftar", messages[0].text.lower())
            self.assertEqual(store.get("1").state, State.IDLE.value)

    def test_authorized_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp), allowed=["1"])
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            self.assertEqual(store.get("1").state, State.WAITING_MATERIAL.value)


class TestHappyPath(unittest.TestCase):
    def test_full_flow_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)

            adapter.receive("1", BTN_CONFIRM)
            self.assertEqual(store.get("1").state, State.WAITING_QUESTION_CONFIRMATION.value)
            self.assertEqual(len(store.get("1").questions), 5)

            adapter.receive("1", BTN_CONFIRM)
            self.assertEqual(store.get("1").state, State.QUESTION_CONFIRMED.value)

            adapter.receive("1", photo_path=PHOTOS[0])
            adapter.receive("1", photo_path=PHOTOS[1])
            messages = adapter.receive("1", BTN_DONE)

            session = store.get("1")
            self.assertEqual(session.state, State.COMPLETED.value)
            self.assertTrue(Path(session.output_docx).exists())
            self.assertTrue(Path(session.output_pdf).exists())
            self.assertEqual(len(messages[-1].documents), 2)

    def test_theme_extraction_from_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            messages = adapter.receive("1", document_path=MATERIAL)
            self.assertIn("Tema terdeteksi", messages[0].text)
            self.assertTrue(store.get("1").material_text)


class TestEdits(unittest.TestCase):
    def test_edit_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            adapter.receive("1", document_path=MATERIAL)
            adapter.receive("1", BTN_EDIT_THEME)
            adapter.receive("1", "Tema Baru Pilihan User")
            self.assertEqual(store.get("1").theme, "Tema Baru Pilihan User")
            self.assertEqual(store.get("1").state, State.WAITING_ARCHIVE.value)

    def test_edit_data_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            adapter.receive("1", "edit:location")
            adapter.receive("1", "Lokasi Baru")
            self.assertEqual(store.get("1").location, "Lokasi Baru")
            self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)

    def test_regenerate_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            adapter.receive("1", BTN_CONFIRM)
            adapter.receive("1", BTN_REGENERATE)
            self.assertEqual(store.get("1").state, State.WAITING_QUESTION_CONFIRMATION.value)
            self.assertEqual(len(store.get("1").questions), 5)

    def test_edit_single_question_regenerates_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            adapter.receive("1", BTN_CONFIRM)
            adapter.receive("1", BTN_EDIT_Q)
            adapter.receive("1", "edit_q:1")
            adapter.receive("1", "Pertanyaan baru dari user?")
            session = store.get("1")
            self.assertEqual(session.questions[0]["question"], "Pertanyaan baru dari user?")
            self.assertEqual(session.questions[0]["answer"], MockAIProvider().answer_text)


class TestPersonnel(unittest.TestCase):
    def test_personnel_skip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter, personnel=BTN_SKIP)
            session = store.get("1")
            self.assertTrue(session.personnel_set)
            self.assertIsNone(session.personnel_count)
            self.assertIn("Personil   : —", adapter.sent[-1][1].text)

    def test_personnel_invalid_then_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            adapter.receive("1", document_path=MATERIAL)
            adapter.receive("1", BTN_USE_THEME)
            adapter.receive("1", "A")
            adapter.receive("1", "D")
            adapter.receive("1", "L")
            adapter.receive("1", "T")
            adapter.receive("1", "S")
            adapter.receive("1", "bukan angka")
            self.assertEqual(store.get("1").state, State.WAITING_PERSONNEL_COUNT.value)
            adapter.receive("1", "15")
            self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)
            self.assertIn("15人", adapter.sent[-1][1].text)


class TestFailures(unittest.TestCase):
    def test_invalid_material_keeps_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            bad = Path(tmp) / "notes.txt"
            bad.write_text("tidak didukung", encoding="utf-8")
            messages = adapter.receive("1", document_path=bad)
            self.assertIn("tidak dapat dibaca", messages[0].text.lower())
            self.assertEqual(store.get("1").state, State.WAITING_MATERIAL.value)

    def test_ai_failure_keeps_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ai = MockAIProvider(question_provider_errors=99)
            workflow, store = make_workflow(Path(tmp), ai=ai)
            workflow.ai.max_retries = 1
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            messages = adapter.receive("1", BTN_CONFIRM)  # data confirm -> questions AI fails
            self.assertIn("gagal", messages[-1].text.lower())
            self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)

    def test_validation_failure_marks_error(self) -> None:
        def failing_validate(docx_path, pdf_path=None):
            report = ValidationReport()
            report.error("TEST", "layout gagal")
            return report

        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp), validate=failing_validate)
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            adapter.receive("1", BTN_CONFIRM)
            adapter.receive("1", BTN_CONFIRM)
            adapter.receive("1", BTN_DONE)
            self.assertEqual(store.get("1").state, State.ERROR.value)


class TestRobustnessAgainstBadFiles(unittest.TestCase):
    def test_corrupt_upload_keeps_waiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            bad = Path(tmp) / "corrupt.pptx"
            bad.write_bytes(b"garbage not a zip")
            messages = adapter.receive("1", document_path=bad)
            self.assertIn("tidak dapat dibaca", messages[0].text.lower())
            self.assertEqual(store.get("1").state, State.WAITING_MATERIAL.value)

    def test_unexpected_reader_error_does_not_crash(self) -> None:
        import qm_training.bot.workflow as workflow_module

        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("1", "/new_training")
            original = workflow_module.read_material

            def boom(path):
                raise RuntimeError("unexpected parser failure")

            workflow_module.read_material = boom
            try:
                messages = adapter.receive("1", document_path=Path(tmp) / "whatever.docx")
            finally:
                workflow_module.read_material = original
            self.assertIn("kesalahan", messages[0].text.lower())
            self.assertEqual(store.get("1").state, State.WAITING_MATERIAL.value)


class TestSessions(unittest.TestCase):
    def test_session_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            adapter.receive("A", "/new_training")
            adapter.receive("A", document_path=MATERIAL)
            adapter.receive("B", "/new_training")
            adapter.receive("B", document_path=MATERIAL)
            adapter.receive("B", BTN_USE_THEME)
            self.assertEqual(store.get("A").state, State.WAITING_THEME_CONFIRMATION.value)
            self.assertEqual(store.get("B").state, State.WAITING_ARCHIVE.value)

    def test_interrupted_session_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SessionStore(Path(tmp))
            workflow, _ = make_workflow(Path(tmp), store=store)
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            # simulate restart with the same store
            workflow2, _ = make_workflow(Path(tmp), store=store)
            adapter2 = MockTelegramAdapter(workflow2)
            adapter2.receive("1", BTN_CONFIRM)
            self.assertEqual(store.get("1").state, State.WAITING_QUESTION_CONFIRMATION.value)

    def test_new_training_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workflow, store = make_workflow(Path(tmp))
            adapter = MockTelegramAdapter(workflow)
            run_to_data_review(adapter)
            adapter.receive("1", "/new_training")
            session = store.get("1")
            self.assertEqual(session.state, State.WAITING_MATERIAL.value)
            self.assertIsNone(session.archive_number)


if __name__ == "__main__":
    unittest.main()
