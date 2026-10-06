"""Phase 6 tests: end-to-end hardening + validator efficacy.

E2E cases use mock AI + mock Telegram transport but REAL document generation,
REAL LibreOffice PDF conversion and REAL validation.
"""

from __future__ import annotations

import shutil
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
from qm_training.core.errors import ConversionError
from qm_training.document.engine import generate as real_generate
from qm_training.document.pdf import convert_to_pdf, find_soffice
from qm_training.document.render import pdf_page_count
from qm_training.testing.datasets import long_questions, make_photos
from qm_training.testing.fixtures import build_docx
from qm_training.validation import validate_document, validate_filename
from qm_training.validation.models import ValidationReport
from qm_training.validation.pipeline import raise_if_invalid

BASE = Path("output/phase6")
MATERIAL: Path


def setUpModule() -> None:
    global MATERIAL
    if find_soffice() is None:
        raise unittest.SkipTest("LibreOffice tidak tersedia untuk e2e PDF")
    BASE.mkdir(parents=True, exist_ok=True)
    MATERIAL = build_docx(BASE / "material.docx")


def make_workflow(case: str, ai=None, convert=convert_to_pdf, validate=validate_document, photo_count=0):
    case_dir = BASE / case
    if case_dir.exists():
        shutil.rmtree(case_dir)
    store = SessionStore(case_dir / "sessions")
    workflow = Workflow(
        store=store,
        ai_service=AIService(ai or MockAIProvider()),
        settings=Settings(ai_provider="mock"),
        generate_docx=real_generate,
        convert_pdf=convert,
        validate=validate,
    )
    adapter = MockTelegramAdapter(workflow)
    return workflow, store, adapter, case_dir


def drive_to_data_review(adapter, personnel: str = "15") -> None:
    adapter.receive("1", "/new_training")
    adapter.receive("1", document_path=MATERIAL)
    adapter.receive("1", BTN_USE_THEME)
    adapter.receive("1", "2026-QM-LZ-09-03")
    adapter.receive("1", "03 September 2026")
    adapter.receive("1", "Ruang Training QM")
    adapter.receive("1", "Budi Santoso")
    adapter.receive("1", "REGU A")
    adapter.receive("1", personnel)


def complete_flow(adapter, photos: list[Path]) -> list:
    adapter.receive("1", BTN_CONFIRM)
    adapter.receive("1", BTN_CONFIRM)
    for photo in photos:
        adapter.receive("1", photo_path=photo)
    return adapter.receive("1", BTN_DONE)


class TestEndToEndDocuments(unittest.TestCase):
    def _run(self, case: str, photo_count: int, personnel="15", ai=None, expected_pages=None):
        photo_dir = BASE / f"{case}_photos"
        photos = make_photos(photo_count, photo_dir, prefix=case) if photo_count else []
        workflow, store, adapter, case_dir = make_workflow(case, ai=ai)
        drive_to_data_review(adapter, personnel=personnel)
        messages = complete_flow(adapter, photos)
        session = store.get("1")
        self.assertEqual(session.state, State.COMPLETED.value, messages[-1].text)
        docx, pdf = Path(session.output_docx), Path(session.output_pdf)
        self.assertTrue(docx.exists() and pdf.exists())
        report = validate_document(docx, pdf)
        raise_if_invalid(report)
        self.assertEqual(report.errors, [], report.summary())
        self.assertTrue(validate_filename(docx, "2026-QM-LZ-09-03", "REGU A").ok)
        if expected_pages is not None:
            self.assertEqual(pdf_page_count(pdf), expected_pages)
        return session

    def test_case_1_zero_photo_skip(self) -> None:
        session = self._run("case1", 0, personnel=BTN_SKIP, expected_pages=4)
        self.assertTrue(session.personnel_set)
        self.assertIsNone(session.personnel_count)

    def test_case_2_one_photo(self) -> None:
        self._run("case2", 1, expected_pages=4)

    def test_case_3_two_photos(self) -> None:
        self._run("case3", 2, expected_pages=4)

    def test_case_4_three_photos(self) -> None:
        self._run("case4", 3, expected_pages=5)

    def test_case_5_five_photos(self) -> None:
        self._run("case5", 5, expected_pages=6)

    def test_case_6_long_questions_rejected(self) -> None:
        # Long questions must be rejected by the new concise-question rule so
        # the T03A form stays on one page.
        ai = MockAIProvider(questions=long_questions())
        workflow, store, adapter, _ = make_workflow("case6", ai=ai)
        workflow.ai.max_retries = 1
        drive_to_data_review(adapter)
        messages = adapter.receive("1", BTN_CONFIRM)
        self.assertIn("panjang", messages[-1].text.lower())
        self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)


class TestEndToEndFailures(unittest.TestCase):
    def test_case_7_invalid_material(self) -> None:
        workflow, store, adapter, _ = make_workflow("case7")
        adapter.receive("1", "/new_training")
        bad = BASE / "case7" / "bad.txt"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("x", encoding="utf-8")
        messages = adapter.receive("1", document_path=bad)
        self.assertIn("tidak dapat dibaca", messages[0].text.lower())
        self.assertEqual(store.get("1").state, State.WAITING_MATERIAL.value)

    def test_case_8_ai_failure(self) -> None:
        ai = MockAIProvider(question_provider_errors=99)
        workflow, store, adapter, _ = make_workflow("case8", ai=ai)
        workflow.ai.max_retries = 1
        drive_to_data_review(adapter)
        messages = adapter.receive("1", BTN_CONFIRM)  # data confirm -> questions AI fails
        self.assertIn("gagal", messages[-1].text.lower())
        self.assertEqual(store.get("1").state, State.DATA_REVIEW.value)

    def test_case_9_pdf_conversion_failure(self) -> None:
        def broken_convert(docx_path, out_dir=None, **kwargs):
            raise ConversionError("mock pdf failure")

        workflow, store, adapter, _ = make_workflow("case9", convert=broken_convert)
        drive_to_data_review(adapter)
        adapter.receive("1", BTN_CONFIRM)
        adapter.receive("1", BTN_CONFIRM)
        messages = adapter.receive("1", BTN_DONE)
        self.assertEqual(store.get("1").state, State.ERROR.value)
        self.assertIn("gagal", messages[-1].text.lower())

    def test_case_10_layout_failure(self) -> None:
        def failing_validate(docx_path, pdf_path=None):
            report = ValidationReport()
            report.error("LAYOUT", "overlap terdeteksi")
            return report

        workflow, store, adapter, _ = make_workflow("case10", validate=failing_validate)
        drive_to_data_review(adapter)
        adapter.receive("1", BTN_CONFIRM)
        adapter.receive("1", BTN_CONFIRM)
        adapter.receive("1", BTN_DONE)
        self.assertEqual(store.get("1").state, State.ERROR.value)


class TestEndToEndWorkflowCases(unittest.TestCase):
    def test_case_11_unauthorized(self) -> None:
        case_dir = BASE / "case11"
        store = SessionStore(case_dir / "sessions")
        workflow = Workflow(
            store=store,
            ai_service=AIService(MockAIProvider()),
            settings=Settings(ai_provider="mock", allowed_user_ids=("999",)),
        )
        adapter = MockTelegramAdapter(workflow)
        messages = adapter.receive("1", "/new_training")
        self.assertIn("terdaftar", messages[0].text.lower())

    def test_case_12_interrupted_session(self) -> None:
        workflow, store, adapter, _ = make_workflow("case12")
        drive_to_data_review(adapter)
        resumed = Workflow(
            store=store,
            ai_service=AIService(MockAIProvider()),
            settings=Settings(ai_provider="mock"),
            generate_docx=real_generate,
            convert_pdf=convert_to_pdf,
            validate=validate_document,
        )
        adapter2 = MockTelegramAdapter(resumed)
        adapter2.receive("1", BTN_CONFIRM)
        self.assertEqual(store.get("1").state, State.WAITING_QUESTION_CONFIRMATION.value)

    def test_case_13_edit_theme(self) -> None:
        workflow, store, adapter, _ = make_workflow("case13")
        adapter.receive("1", "/new_training")
        adapter.receive("1", document_path=MATERIAL)
        adapter.receive("1", BTN_EDIT_THEME)
        adapter.receive("1", "Tema Edit Sendiri")
        self.assertEqual(store.get("1").theme, "Tema Edit Sendiri")

    def test_case_14_regenerate_questions(self) -> None:
        workflow, store, adapter, _ = make_workflow("case14")
        drive_to_data_review(adapter)
        adapter.receive("1", BTN_CONFIRM)
        adapter.receive("1", BTN_REGENERATE)
        self.assertEqual(len(store.get("1").questions), 5)

    def test_case_15_session_isolation(self) -> None:
        workflow, store, adapter, _ = make_workflow("case15")
        adapter.receive("A", "/new_training")
        adapter.receive("A", document_path=MATERIAL)
        adapter.receive("A", BTN_USE_THEME)
        adapter.receive("B", "/new_training")
        self.assertEqual(store.get("A").state, State.WAITING_ARCHIVE.value)
        self.assertEqual(store.get("B").state, State.WAITING_MATERIAL.value)


class TestValidatorEfficacy(unittest.TestCase):
    def test_validator_flags_missing_answer_key(self) -> None:
        workflow, store, adapter, case_dir = make_workflow("validator_missing_key")
        drive_to_data_review(adapter)
        complete_flow(adapter, [])
        session = store.get("1")
        docx = Path(session.output_docx)

        from docx import Document
        from docx.oxml.ns import qn

        document = Document(str(docx))
        removed = 0
        for element in list(document.element.body):
            text = "".join(node.text or "" for node in element.iter(qn("w:t")))
            if "KUNCI JAWABAN" in text:
                element.getparent().remove(element)
                removed += 1
        self.assertGreater(removed, 0)
        tampered = case_dir / "tampered.docx"
        document.save(str(tampered))
        report = validate_document(tampered, None)
        self.assertFalse(report.ok)
        self.assertIn("ANSWER_KEY_MISSING", [issue.code for issue in report.errors])

    def test_validator_flags_non_document_pdf(self) -> None:
        from qm_training.validation.pdf_validator import validate_pdf

        pdf = convert_to_pdf(MATERIAL, BASE / "validator_pdf")
        report = validate_pdf(pdf)
        self.assertFalse(report.ok)  # material PDF has no QM footer/structure

    def test_raise_if_invalid(self) -> None:
        report = ValidationReport()
        report.error("X", "boom")
        with self.assertRaises(Exception):
            raise_if_invalid(report)


if __name__ == "__main__":
    unittest.main()
