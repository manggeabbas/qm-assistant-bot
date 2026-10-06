"""Theme confirmation gate + update idempotency (Telegram workflow).

Covers the reported issues:
- duplicate "Kirim materi pelatihan" for one /start;
- bot skipping theme confirmation and jumping to the archive prompt;
- duplicate Telegram updates producing duplicate messages.
"""

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
    BTN_EDIT_THEME,
    BTN_USE_THEME,
)
from qm_training.core.config import Settings
from qm_training.testing.fixtures import build_docx
from qm_training.validation.models import ValidationReport

MATERIAL: Path


def setUpModule() -> None:
    global MATERIAL
    root = Path("output/phase9_gate")
    root.mkdir(parents=True, exist_ok=True)
    MATERIAL = build_docx(root / "material.docx")


def fake_convert(docx_path, out_dir=None, **kwargs):
    out = Path(out_dir or Path(docx_path).parent) / f"{Path(docx_path).stem}.pdf"
    out.write_bytes(b"%PDF-1.4\nstub\n")
    return out


def make_workflow(tmp: Path, ai=None):
    store = SessionStore(tmp)
    workflow = Workflow(
        store=store,
        ai_service=AIService(ai or MockAIProvider()),
        settings=Settings(ai_provider="mock"),
        convert_pdf=fake_convert,
        validate=lambda d, p=None: ValidationReport(),
    )
    return workflow, store, MockTelegramAdapter(workflow)


class TestStartIdempotency(unittest.TestCase):
    def test_case_1_start_sends_single_upload_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = make_workflow(Path(tmp))
            messages = adapter.receive("1", "/new_training", update_id=1)
            self.assertEqual(len(messages), 1)
            self.assertIn("Kirim materi pelatihan", messages[0].text)

    def test_case_6_duplicate_start_update_processed_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, _, adapter = make_workflow(Path(tmp))
            first = adapter.receive("1", "/new_training", update_id=1)
            second = adapter.receive("1", "/new_training", update_id=1)
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])  # same update_id -> no duplicate message


class TestThemeGate(unittest.TestCase):
    def test_case_2_upload_shows_theme_and_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            messages = adapter.receive("1", document_path=MATERIAL, update_id=2)
            self.assertEqual(len(messages), 1)
            self.assertIn("Tema terdeteksi", messages[0].text)
            self.assertEqual(messages[0].buttons, [BTN_USE_THEME, BTN_EDIT_THEME])
            # Must STOP at theme confirmation.
            self.assertEqual(store.get("1").state, State.WAITING_THEME_CONFIRMATION.value)
            self.assertFalse(store.get("1").theme_confirmed)
            self.assertNotIn("Nomor Arsip", messages[0].text)

    def test_case_3_use_theme_advances_to_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=MATERIAL, update_id=2)
            messages = adapter.receive("1", BTN_USE_THEME, update_id=3)
            self.assertEqual(store.get("1").state, State.WAITING_ARCHIVE.value)
            self.assertTrue(store.get("1").theme_confirmed)
            self.assertIn("Nomor Arsip", messages[0].text)

    def test_case_4_edit_theme_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=MATERIAL, update_id=2)
            messages = adapter.receive("1", BTN_EDIT_THEME, update_id=3)
            self.assertEqual(store.get("1").state, State.WAITING_THEME_EDIT.value)
            self.assertIn("Kirim tema baru", messages[0].text)

            messages = adapter.receive("1", "Keselamatan Pengoperasian Mesin", update_id=4)
            self.assertEqual(store.get("1").theme, "Keselamatan Pengoperasian Mesin")
            self.assertTrue(store.get("1").theme_confirmed)
            self.assertEqual(store.get("1").state, State.WAITING_ARCHIVE.value)
            self.assertIn("Nomor Arsip", messages[0].text)

    def test_case_5_plain_text_does_not_advance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            original = adapter.receive("1", document_path=MATERIAL, update_id=2)[0].text
            theme_before = store.get("1").theme

            messages = adapter.receive("1", "2026-QM-LZ-09-03", update_id=3)
            self.assertEqual(store.get("1").state, State.WAITING_THEME_CONFIRMATION.value)
            self.assertEqual(store.get("1").theme, theme_before)  # theme not overwritten
            self.assertIn("Tema terdeteksi", messages[0].text)
            self.assertNotIn("Nomor Arsip", messages[0].text)
            self.assertEqual(messages[0].text, original)

    def test_empty_document_update_does_not_advance(self) -> None:
        # Reproduces the duplicate-update bug: an empty document update while in
        # theme confirmation must not jump to the archive prompt.
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=MATERIAL, update_id=2)
            messages = adapter.receive("1", text="", update_id=3)
            self.assertEqual(store.get("1").state, State.WAITING_THEME_CONFIRMATION.value)
            self.assertNotIn("Nomor Arsip", messages[0].text)

    def test_case_10_duplicate_callback_single_archive_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=MATERIAL, update_id=2)
            first = adapter.receive("1", BTN_USE_THEME, update_id=3)
            second = adapter.receive("1", BTN_USE_THEME, update_id=3)
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            self.assertEqual(store.get("1").state, State.WAITING_ARCHIVE.value)


class TestSingleThemePerMaterial(unittest.TestCase):
    def test_case_11_ai_retry_single_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ai = MockAIProvider(question_malformed=1)  # forces one internal retry
            _, store, adapter = make_workflow(Path(tmp), ai=ai)
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=MATERIAL, update_id=2)
            adapter.receive("1", BTN_USE_THEME, update_id=3)
            for i, value in enumerate(["A", "D", "L", "T", "S", "15"], start=4):
                adapter.receive("1", value, update_id=i)
            messages = adapter.receive("1", BTN_CONFIRM, update_id=10)
            previews = [m for m in messages if "Preview Pertanyaan" in m.text]
            self.assertEqual(len(previews), 1)
            self.assertEqual(store.get("1").generate_questions_calls, 1)
            self.assertEqual(len(store.get("1").questions), 5)

    def test_case_12_one_upload_one_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            messages = adapter.receive("1", document_path=MATERIAL, update_id=2)
            theme_messages = [m for m in messages if "Tema terdeteksi" in m.text]
            self.assertEqual(len(theme_messages), 1)
            self.assertIsInstance(store.get("1").theme, str)
            self.assertTrue(store.get("1").theme.strip())

    def test_case_9_duplicate_material_update_single_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = make_workflow(Path(tmp))
            adapter.receive("1", "/new_training", update_id=1)
            first = adapter.receive("1", document_path=MATERIAL, update_id=2)
            second = adapter.receive("1", document_path=MATERIAL, update_id=2)
            self.assertEqual(len(first), 1)
            self.assertEqual(second, [])
            self.assertEqual(store.get("1").state, State.WAITING_THEME_CONFIRMATION.value)


if __name__ == "__main__":
    unittest.main()
