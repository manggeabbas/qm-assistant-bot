"""Phase 3 tests: material readers for all supported formats."""

from __future__ import annotations

import unittest
from pathlib import Path

from qm_training.core.errors import MaterialError, UnsupportedMaterialError
from qm_training.core.libreoffice import find_soffice
from qm_training.material import read_material
from qm_training.material.normalize import normalize_text
from qm_training.testing.fixtures import build_material_fixtures

OUT = Path("output/phase3")
FIXTURES: dict[str, Path] = {}


def setUpModule() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if find_soffice() is None:
        raise unittest.SkipTest("LibreOffice tidak tersedia untuk fixture legacy/PDF")
    FIXTURES.update(build_material_fixtures(OUT / "fixtures"))


class TestReaders(unittest.TestCase):
    def test_docx_structure(self) -> None:
        document = read_material(FIXTURES[".docx"])
        kinds = [block.kind for block in document.blocks]
        self.assertIn("heading", kinds)
        self.assertIn("paragraph", kinds)
        self.assertIn("table", kinds)
        heading = next(b for b in document.blocks if b.kind == "heading")
        self.assertEqual(heading.level, 1)
        self.assertIn("Keselamatan", document.text())
        self.assertIn("spill kit", document.text())

    def test_pdf(self) -> None:
        document = read_material(FIXTURES[".pdf"])
        self.assertEqual(document.format, "pdf")
        self.assertIn("Keselamatan", document.text())
        self.assertIn("spill kit", document.text())

    def test_pptx(self) -> None:
        document = read_material(FIXTURES[".pptx"])
        self.assertEqual(document.format, "pptx")
        self.assertIn("Briefing K3", document.text())
        self.assertTrue(any(b.kind == "slide" for b in document.blocks))

    def test_xlsx(self) -> None:
        document = read_material(FIXTURES[".xlsx"])
        self.assertEqual(document.format, "xlsx")
        sheets = [b.text for b in document.blocks if b.kind == "sheet"]
        self.assertIn("Checklist", sheets)
        self.assertIn("Jadwal", sheets)
        self.assertIn("Helm", document.text())

    def test_legacy_doc(self) -> None:
        document = read_material(FIXTURES[".doc"])
        self.assertEqual(document.format, "doc")
        self.assertIn("Keselamatan", document.text())

    def test_legacy_ppt(self) -> None:
        document = read_material(FIXTURES[".ppt"])
        self.assertEqual(document.format, "ppt")
        self.assertIn("Briefing", document.text())

    def test_legacy_xls(self) -> None:
        document = read_material(FIXTURES[".xls"])
        self.assertEqual(document.format, "xls")
        self.assertIn("Helm", document.text())


class TestValidation(unittest.TestCase):
    def test_unsupported_extension(self) -> None:
        path = OUT / "notes.txt"
        path.write_text("hello", encoding="utf-8")
        with self.assertRaises(UnsupportedMaterialError):
            read_material(path)

    def test_missing_file(self) -> None:
        with self.assertRaises(MaterialError):
            read_material(OUT / "tidak-ada.pdf")

    def test_empty_file(self) -> None:
        path = OUT / "empty.pdf"
        path.write_bytes(b"")
        with self.assertRaises(MaterialError):
            read_material(path)

    def test_oversize_rejected(self) -> None:
        with self.assertRaises(MaterialError):
            read_material(FIXTURES[".docx"], max_bytes=10)


class TestCorruptAndRobustness(unittest.TestCase):
    def test_garbage_pptx_raises_material_error(self) -> None:
        bad = OUT / "garbage.pptx"
        bad.write_bytes(b"this is definitely not a zip archive")
        with self.assertRaises(MaterialError):
            read_material(bad)

    def test_truncated_pptx_raises_material_error(self) -> None:
        data = FIXTURES[".pptx"].read_bytes()
        bad = OUT / "truncated.pptx"
        bad.write_bytes(data[: max(1, len(data) // 2)])
        with self.assertRaises(MaterialError):
            read_material(bad)

    def test_truncated_docx_raises_material_error(self) -> None:
        data = FIXTURES[".docx"].read_bytes()
        bad = OUT / "truncated.docx"
        bad.write_bytes(data[: max(1, len(data) // 3)])
        with self.assertRaises(MaterialError):
            read_material(bad)


class TestNormalize(unittest.TestCase):
    def test_whitespace_collapsed(self) -> None:
        self.assertEqual(normalize_text("a   b\t\tc\n\n\n\nd"), "a b c\n\nd")

    def test_max_chars(self) -> None:
        self.assertEqual(len(normalize_text("x" * 100, max_chars=10)), 10)


if __name__ == "__main__":
    unittest.main()
