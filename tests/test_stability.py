"""Stability tests: blank pages, duplicate validation, PDF-from-DOCX (V/W)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from qm_training.ai.mock import MockAIProvider
from qm_training.ai.service import AIService
from qm_training.bot import SessionStore, Workflow
from qm_training.bot.adapters import MockTelegramAdapter
from qm_training.bot.states import State
from qm_training.bot.workflow import BTN_CONFIRM, BTN_DONE, BTN_USE_THEME
from qm_training.core.config import Settings
from qm_training.document.engine import generate
from qm_training.document.pdf import convert_to_pdf, find_soffice
from qm_training.document.render import pdf_page_count, pdf_pages_text, render_pdf_to_png
from qm_training.testing.datasets import dataset
from qm_training.testing.fixtures import build_docx
from qm_training.validation.models import ValidationReport
from qm_training.validation.pdf_validator import validate_pdf

BASE = Path("output/phase12_stability")
MATERIAL: Path


def setUpModule() -> None:
    if find_soffice() is None:
        raise unittest.SkipTest("LibreOffice tidak tersedia")
    global MATERIAL
    BASE.mkdir(parents=True, exist_ok=True)
    MATERIAL = build_docx(BASE / "material.docx")


def blank_pages(pdf: Path) -> list[int]:
    pages = pdf_pages_text(pdf)
    return [
        index
        for index, text in enumerate(pages, start=1)
        if not "\n".join(line for line in text.splitlines() if "页" not in line).strip()
    ]


class TestNoBlankPages(unittest.TestCase):
    def _check(self, photo_count: int) -> Path:
        data = dataset(personnel_count=4, photo_count=photo_count, photo_dir=BASE / f"photos{photo_count}")
        docx = generate(data, out_dir=BASE, output_name=f"case_{photo_count}")
        pdf = convert_to_pdf(docx, BASE)
        self.assertEqual(blank_pages(pdf), [], f"{photo_count} foto: ada halaman kosong")
        report = validate_pdf(pdf)
        self.assertEqual([i for i in report.issues if i.code == "BLANK_PAGE"], [])
        return pdf

    def test_28_zero_photos(self) -> None:
        self.assertEqual(pdf_page_count(self._check(0)), 4)

    def test_29_one_photo(self) -> None:
        self._check(1)

    def test_30_two_photos(self) -> None:
        self._check(2)

    def test_31_three_photos(self) -> None:
        self.assertEqual(pdf_page_count(self._check(3)), 5)

    def test_long_questions_do_not_create_blank_page(self) -> None:
        data = dataset(
            personnel_count=15,
            photo_count=2,
            photo_dir=BASE / "longq_photos",
            use_long_questions=True,
        )
        docx = generate(data, out_dir=BASE, output_name="long_questions")
        pdf = convert_to_pdf(docx, BASE)
        self.assertEqual(blank_pages(pdf), [], "pertanyaan panjang menghasilkan halaman kosong")
        report = validate_pdf(pdf)
        self.assertEqual([i for i in report.issues if i.code == "BLANK_PAGE"], [])


class TestPdfFromDocx(unittest.TestCase):
    def test_22_23_pdf_content_matches_docx(self) -> None:
        data = dataset(personnel_count=15, photo_count=0, photo_dir=BASE / "pdfcheck_photos")
        docx = generate(data, out_dir=BASE, output_name="pdf_from_docx")
        pdf = convert_to_pdf(docx, BASE)
        pages_text = "\n".join(pdf_pages_text(pdf))
        for qa in data.questions:
            self.assertIn(qa.question, pages_text, "pertanyaan PDF != DOCX")

    def test_t03a_single_page_for_concise_questions(self) -> None:
        data = dataset(personnel_count=15, photo_count=2, photo_dir=BASE / "onepage_photos")
        docx = generate(data, out_dir=BASE, output_name="t03a_one_page")
        pdf = convert_to_pdf(docx, BASE)
        pages = pdf_pages_text(pdf)
        t03a_pages = [t for t in pages if "PERTANYAAN 1" in t]
        self.assertEqual(len(t03a_pages), 1, "T03A harus satu halaman untuk pertanyaan singkat")
        self.assertIn("PERTANYAAN 5", t03a_pages[0])
        self.assertIn("JAWABAN", t03a_pages[0])

    def test_t03a_single_page_at_max_question_length(self) -> None:
        from qm_training.ai.schema import MAX_QUESTION_CHARS
        from qm_training.document.schema import QAPair

        base = "Apa langkah pencegahan utama operator sebelum memulai proses mesin produksi"
        questions = [
            QAPair((base[: MAX_QUESTION_CHARS - 1]).rstrip(" ,.") + "?", "Jawaban singkat sesuai materi.")
            for _ in range(5)
        ]
        data = dataset(personnel_count=15, photo_count=2, photo_dir=BASE / "maxlen_photos")
        data.questions = questions
        docx = generate(data, out_dir=BASE, output_name="t03a_maxlen")
        pdf = convert_to_pdf(docx, BASE)
        t03a_pages = [t for t in pdf_pages_text(pdf) if "PERTANYAAN 1" in t]
        self.assertEqual(len(t03a_pages), 1, "T03A harus tetap satu halaman pada batas panjang")
        self.assertIn("PERTANYAAN 5", t03a_pages[0])


class TestT03aPdfBorders(unittest.TestCase):
    def _horizontal_lines(self, png, x0=80, x1=860, dark=110, frac=0.85):
        image = Image.open(png).convert("L")
        w, h = image.size
        x1 = min(x1, w - 1)
        px = image.load()
        rows = []
        for y in range(h):
            dark_count = sum(1 for x in range(x0, x1) if px[x, y] < dark)
            if dark_count >= (x1 - x0) * frac:
                rows.append(y)
        groups = []
        for y in rows:
            if groups and y - groups[-1][-1] <= 2:
                groups[-1].append(y)
            else:
                groups.append([y])
        return [sum(g) // len(g) for g in groups]

    def test_t03a_pdf_has_outer_horizontal_lines(self) -> None:
        data = dataset(personnel_count=15, photo_count=0, photo_dir=BASE / "border_photos")
        docx = generate(data, out_dir=BASE, output_name="border_pdf")
        pdf = convert_to_pdf(docx, BASE)
        pages = pdf_pages_text(pdf)
        idx = next(i for i, t in enumerate(pages, 1) if "T03A" in t)
        png = render_pdf_to_png(pdf, BASE / "border_png")[idx - 1]
        lines = self._horizontal_lines(png)
        # table top + identity rows + question-block top + table bottom edge
        self.assertGreaterEqual(len(lines), 5, f"garis horizontal T03A hilang di PDF: {lines}")


class TestDuplicateValidationError(unittest.TestCase):
    def _workflow(self, tmp: Path):
        def failing_validate(docx_path, pdf_path=None):
            report = ValidationReport()
            report.error("BLANK_PAGE", "Halaman 2 kosong")
            return report

        def fake_convert(docx_path, out_dir=None, **kwargs):
            out = Path(out_dir or Path(docx_path).parent) / f"{Path(docx_path).stem}.pdf"
            out.write_bytes(b"%PDF-1.4\nstub\n")
            return out

        store = SessionStore(tmp)
        wf = Workflow(
            store=store,
            ai_service=AIService(MockAIProvider()),
            settings=Settings(ai_provider="mock"),
            convert_pdf=fake_convert,
            validate=failing_validate,
        )
        return wf, store, MockTelegramAdapter(wf)

    def _drive_to_photos(self, adapter, update_start=1):
        u = update_start
        adapter.receive("1", "/new_training", update_id=u); u += 1
        adapter.receive("1", document_path=MATERIAL, update_id=u); u += 1
        adapter.receive("1", BTN_USE_THEME, update_id=u); u += 1
        for value in ("A", "D", "L", "T", "S", "15"):
            adapter.receive("1", value, update_id=u); u += 1
        adapter.receive("1", BTN_CONFIRM, update_id=u); u += 1  # data
        adapter.receive("1", BTN_CONFIRM, update_id=u); u += 1  # questions
        return u

    def test_32_33_34_single_validation_and_single_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, store, adapter = self._workflow(Path(tmp))
            u = self._drive_to_photos(adapter)
            first = adapter.receive("1", BTN_DONE, update_id=u)
            duplicate = adapter.receive("1", BTN_DONE, update_id=u)  # same update id
            later = adapter.receive("1", BTN_DONE, update_id=u + 1)  # new update id

            session = store.get("1")
            self.assertEqual(session.document_generation, 1)
            self.assertEqual(session.validation_runs, 1)
            self.assertEqual(session.validation_error_messages_sent, 1)
            errors = [m for m in first if "gagal divalidasi" in m.text]
            self.assertEqual(len(errors), 1)
            self.assertEqual(duplicate, [])
            self.assertFalse(any("gagal divalidasi" in m.text for m in later))
            self.assertEqual(session.state, State.ERROR.value)


if __name__ == "__main__":
    unittest.main()
