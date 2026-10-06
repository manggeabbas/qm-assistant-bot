"""Theme = ORIGINAL Indonesian title extracted from the document (R tests)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qm_training.ai.mock import MockAIProvider
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.bot.adapters import MockTelegramAdapter
from qm_training.bot.states import State
from qm_training.bot.workflow import BTN_USE_THEME
from qm_training.core.config import Settings
from qm_training.material import read_material
from qm_training.material.title import extract_title
from qm_training.testing.fixtures import (
    build_bilingual_pptx,
    build_docx,
    build_mandarin_docx,
)
from qm_training.validation.models import ValidationReport

BASE = Path("output/phase11_theme")
INDONESIAN = '"2024.08.28" Peninjauan Kecelakaan Tersayat Sampel'


def setUpModule() -> None:
    BASE.mkdir(parents=True, exist_ok=True)


def fake_convert(docx_path, out_dir=None, **kwargs):
    out = Path(out_dir or Path(docx_path).parent) / f"{Path(docx_path).stem}.pdf"
    out.write_bytes(b"%PDF-1.4\nstub\n")
    return out


class TestTitleExtraction(unittest.TestCase):
    def test_1_bilingual_pptx_returns_indonesian(self) -> None:
        path = build_bilingual_pptx(BASE / "bilingual.pptx")
        title, source = extract_title(read_material(path))
        self.assertEqual(title, INDONESIAN)
        self.assertEqual(source, "document_title_indonesian")

    def test_2_document_title_not_filename(self) -> None:
        # A deliberately unrelated filename: the title must come from inside.
        path = build_docx(BASE / "laporan_rapat_2026.docx")
        title, _ = extract_title(read_material(path))
        self.assertEqual(title, "Prosedur Keselamatan Laboratorium")
        self.assertNotIn("laporan_rapat_2026", title)

    def test_3_only_indonesian_when_side_by_side(self) -> None:
        title, _ = extract_title(read_material(build_bilingual_pptx(BASE / "bilingual2.pptx")))
        self.assertFalse(any("\u4e00" <= ch <= "\u9fff" for ch in title))

    def test_4_5_verbatim_no_translation_no_paraphrase(self) -> None:
        title, _ = extract_title(read_material(build_bilingual_pptx(BASE / "bilingual3.pptx")))
        self.assertEqual(title, INDONESIAN)  # exact, unchanged text

    def test_no_indonesian_title_returns_none(self) -> None:
        title, source = extract_title(read_material(build_mandarin_docx(BASE / "mandarin.docx")))
        self.assertIsNone(title)
        self.assertEqual(source, "not_found")


class TestThemeWorkflow(unittest.TestCase):
    def _workflow(self, tmp: Path, material: Path):
        store = SessionStore(tmp)
        ai = MockAIProvider()
        wf = Workflow(
            store=store,
            ai_service=AIService(ai),
            settings=Settings(ai_provider="mock"),
            convert_pdf=fake_convert,
            validate=lambda d, p=None: ValidationReport(),
        )
        return wf, store, MockTelegramAdapter(wf), ai

    def test_6_one_upload_one_theme_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            material = build_bilingual_pptx(Path(tmp) / "m.pptx")
            _, store, adapter, ai = self._workflow(Path(tmp), material)
            adapter.receive("1", "/new_training", update_id=1)
            messages = adapter.receive("1", document_path=material, update_id=2)
            themes = [m for m in messages if "Tema terdeteksi" in m.text]
            self.assertEqual(len(themes), 1)
            self.assertIn(INDONESIAN, themes[0].text)
            self.assertEqual(store.get("1").theme, INDONESIAN)
            self.assertEqual(store.get("1").theme_source, "document_title_indonesian")
            self.assertEqual(store.get("1").theme_extraction_calls, 1)
            self.assertEqual(store.get("1").theme_messages_sent, 1)
            # theme is extraction only: no AI call for the theme
            self.assertEqual(ai.calls, 0)

    def test_duplicate_upload_does_not_repeat_theme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            material = build_bilingual_pptx(Path(tmp) / "m.pptx")
            _, store, adapter, _ = self._workflow(Path(tmp), material)
            adapter.receive("1", "/new_training", update_id=1)
            adapter.receive("1", document_path=material, update_id=2)
            again = adapter.receive("1", document_path=material, update_id=2)
            self.assertEqual(again, [])
            self.assertEqual(store.get("1").theme_messages_sent, 1)

    def test_manual_theme_when_no_indonesian_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            material = build_mandarin_docx(Path(tmp) / "m.docx")
            _, store, adapter, _ = self._workflow(Path(tmp), material)
            adapter.receive("1", "/new_training", update_id=1)
            messages = adapter.receive("1", document_path=material, update_id=2)
            self.assertIn("manual", messages[0].text.lower())
            self.assertEqual(store.get("1").state, State.WAITING_THEME_EDIT.value)
            # user provides the theme manually; flow continues to archive
            messages = adapter.receive("1", "Tema Manual", update_id=3)
            self.assertEqual(store.get("1").theme, "Tema Manual")
            self.assertIn("Nomor Arsip", messages[0].text)


if __name__ == "__main__":
    unittest.main()
