"""Validation pipeline: combine DOCX + PDF checks."""

from __future__ import annotations

from pathlib import Path

from qm_training.core.errors import ValidationError
from qm_training.paths import MASTER_TEMPLATE
from qm_training.validation.docx_validator import validate_docx
from qm_training.validation.models import ValidationReport
from qm_training.validation.pdf_validator import validate_pdf
from qm_training.validation.structure import compare_t03a_structure


def validate_document(
    docx_path: Path,
    pdf_path: Path | None = None,
    master_path: Path | None = MASTER_TEMPLATE,
) -> ValidationReport:
    report = validate_docx(docx_path)
    if master_path is not None and Path(master_path).exists():
        structure = compare_t03a_structure(docx_path, master_path)
        report.issues.extend(structure.issues)
    if pdf_path is not None and Path(pdf_path).exists():
        pdf_report = validate_pdf(pdf_path)
        report.issues.extend(pdf_report.issues)
    return report


def validate_filename(path: Path, archive_number: str, shift_group: str) -> ValidationReport:
    report = ValidationReport()
    import re

    clean = lambda value: re.sub(r"[^\w.\-]+", "-", str(value).strip()).strip("-")  # noqa: E731
    expected = f"{clean(archive_number)}_{clean(shift_group)}"
    if Path(path).stem != expected:
        report.error("FILENAME_MISMATCH", f"diharapkan '{expected}', ditemukan '{Path(path).stem}'")
    return report


def raise_if_invalid(report: ValidationReport) -> None:
    if not report.ok:
        details = "; ".join(f"[{issue.code}] {issue.message}" for issue in report.errors)
        raise ValidationError(f"validasi dokumen gagal: {details}")
