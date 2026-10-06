"""DOCX -> PDF conversion via LibreOffice headless."""

from __future__ import annotations

from pathlib import Path

from qm_training.core.errors import ConversionError
from qm_training.core.libreoffice import convert as _convert
from qm_training.core.libreoffice import find_soffice as _find_soffice


def find_soffice() -> str | None:
    return _find_soffice()


def convert_to_pdf(docx_path: Path, out_dir: Path | None = None, timeout: int = 300) -> Path:
    docx_path = Path(docx_path)
    out_dir = Path(out_dir) if out_dir else docx_path.parent
    try:
        return _convert(docx_path, "pdf", out_dir, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - normalize to ConversionError
        raise ConversionError(f"konversi PDF gagal: {exc}") from exc
