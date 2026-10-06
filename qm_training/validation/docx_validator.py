"""Structural validation of the generated DOCX."""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from qm_training.validation.models import ValidationReport

PAGE_WIDTH_TWIPS = 11906
BANNED_SAMPLE_PHOTOS = ("word/media/image3.jpeg", "word/media/image4.jpeg", "word/media/image5.jpeg")


def _text(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def _tables(doc: Document) -> list:
    return doc.element.body.findall(qn("w:tbl"))


def missing_questions(path: Path, questions: list[str]) -> list[str]:
    """Return the questions whose text is not present in the generated DOCX."""
    document = Document(str(path))
    text = "\n".join(_text(element) for element in document.element.body)
    return [question for question in questions if question.strip() and question not in text]


def validate_docx(path: Path) -> ValidationReport:
    report = ValidationReport()
    path = Path(path)
    doc = Document(str(path))
    tables = _tables(doc)

    t01a = [t for t in tables if "Tema Pelatihan" in _text(t)]
    t02a = [t for t in tables if "Foto pertama" in _text(t)]
    t03a = [t for t in tables if "PENCATATAN PERTANYAAN" in _text(t)]

    if not t01a:
        report.error("T01A_MISSING", "Tabel T01A tidak ditemukan")
    else:
        data_rows = t01a[0].findall(qn("w:tr"))[5:20]
        numbers = []
        for row in data_rows:
            cell = row.findall(qn("w:tc"))[0]
            paragraphs = cell.findall(qn("w:p"))
            numbers.append(_text(paragraphs[0]).strip() if paragraphs else "")
        if numbers != [str(i) for i in range(1, 16)]:
            report.error("T01A_NUMBERING", f"Nomor personil T01A tidak 1..15: {numbers}")

    if not t02a:
        report.error("T02A_MISSING", "Blok T02A tidak ditemukan")
    if not t03a:
        report.error("T03A_MISSING", "Tabel T03A tidak ditemukan")

    full_text = "\n".join(_text(element) for element in doc.element.body)

    if full_text.count("PERTANYAAN 1 ") < 1:
        report.error("T03A_QUESTIONS", "PERTANYAAN 1 tidak ditemukan")
    for index in range(1, 6):
        if f"PERTANYAAN {index}" not in full_text:
            report.error("T03A_QUESTIONS", f"PERTANYAAN {index} tidak ditemukan")
    if "PERTANYAAN 6" in full_text:
        report.error("T03A_QUESTIONS", "PERTANYAAN 6 ditemukan (harus tepat 5)")

    if "KUNCI JAWABAN" not in full_text:
        report.error("ANSWER_KEY_MISSING", "Halaman KUNCI JAWABAN tidak ditemukan")

    if "TEMPATKAN PERTANYAAN DISINI" in full_text:
        report.error(
            "PLACEHOLDER_NOT_REPLACED",
            "Placeholder 'TEMPATKAN PERTANYAAN DISINI' masih ada di output",
        )

    if t03a:
        for row_index in (5, 7, 9, 11, 13):
            cells = t03a[0].findall(qn("w:tr"))[row_index].findall(qn("w:tc"))
            paragraphs = cells[0].findall(qn("w:p"))
            answer_area = paragraphs[1] if len(paragraphs) > 1 else paragraphs[0]
            if _text(answer_area).strip():
                report.error("ANSWER_AREA_NOT_BLANK", f"Area JAWABAN baris {row_index} tidak kosong")

    doc_pr = [node.get("id") for node in doc.element.body.iter(qn("wp:docPr"))]
    duplicates = [value for value, count in Counter(doc_pr).items() if count > 1]
    if duplicates:
        report.error("DUPLICATE_DRAWING_ID", f"wp:docPr id ganda: {duplicates}")

    for table in tables:
        width = table.find(qn("w:tblPr")).find(qn("w:tblW")) if table.find(qn("w:tblPr")) is not None else None
        if width is not None:
            value = int(width.get(qn("w:w"), "0"))
            if value > PAGE_WIDTH_TWIPS:
                report.warning("TABLE_WIDER_THAN_PAGE", f"Tabel {value} twips > lebar halaman {PAGE_WIDTH_TWIPS}")

    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    for banned in BANNED_SAMPLE_PHOTOS:
        if banned in names:
            report.error("SAMPLE_PHOTO_PRESENT", f"Foto contoh master ikut terbawa: {banned}")

    if not re.search(r"_", path.stem):
        report.warning("FILENAME_FORMAT", f"Nama file tidak mengikuti <ARCHIVE>_<SHIFT_GROUP>: {path.name}")

    return report
