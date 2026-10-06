"""Pagination validation of the generated PDF.

Per PRD, each question block and its participant answer area must stay
together; T03A itself may legitimately span more than one page for very long
questions. A page that contains only the footer is an unintended blank page.
"""

from __future__ import annotations

import re
from pathlib import Path

from qm_training.document.render import pdf_page_count, pdf_pages_text
from qm_training.validation.models import ValidationReport

FOOTER_RE = re.compile(r"第\s*\d+\s*页\s*共\s*\d+\s*页")


def _content_without_footer(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not FOOTER_RE.search(line)).strip()


def _answer_label_pages(pages: list[str]) -> list[int]:
    """Page index of each ordered 'JAWABAN 答' occurrence."""
    positions: list[int] = []
    for index, text in enumerate(pages):
        start = 0
        while True:
            found = text.find("JAWABAN 答", start)
            if found == -1:
                break
            positions.append(index)
            start = found + 1
    return positions


def validate_pdf(path: Path) -> ValidationReport:
    report = ValidationReport()
    pages = pdf_pages_text(path)
    count = pdf_page_count(path)

    if count != len(pages):
        report.warning("PAGE_COUNT_MISMATCH", f"pdfinfo={count} vs pdftotext={len(pages)}")

    if count < 4:
        report.error("TOO_FEW_PAGES", f"Dokumen hanya {count} halaman (minimal T01A/T02A/T03A/KUNCI)")

    for index, text in enumerate(pages, start=1):
        if not _content_without_footer(text):
            report.error("BLANK_PAGE", f"Halaman {index} kosong")
        if "页" not in text:
            report.error("FOOTER_MISSING", f"Footer tidak ditemukan di halaman {index}")

    joined = "\n".join(pages)
    if "KUNCI JAWABAN" not in joined:
        report.error("ANSWER_KEY_MISSING", "Halaman KUNCI JAWABAN tidak ada di PDF")

    answer_pages = _answer_label_pages(pages)
    for question in range(1, 6):
        question_pages = [index for index, text in enumerate(pages) if f"PERTANYAAN {question}" in text]
        if not question_pages:
            report.error("T03A_MISSING", f"PERTANYAAN {question} tidak ditemukan di PDF")
            continue
        if question - 1 >= len(answer_pages):
            report.error("T03A_SPLIT", f"area jawaban untuk PERTANYAAN {question} tidak ditemukan")
            continue
        if answer_pages[question - 1] not in question_pages:
            report.error(
                "T03A_SPLIT",
                f"PERTANYAAN {question} terpisah dari area jawabannya antar halaman",
            )

    return report
