"""Material reader dispatcher with validation."""

from __future__ import annotations

from pathlib import Path

from qm_training.core.errors import MaterialError, UnsupportedMaterialError
from qm_training.material.base import MaterialDocument
from qm_training.material.docx_reader import read_docx
from qm_training.material.legacy import read_legacy
from qm_training.material.normalize import normalize_document
from qm_training.material.pdf_reader import read_pdf
from qm_training.material.pptx_reader import read_pptx
from qm_training.material.xlsx_reader import read_xlsx

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}
DEFAULT_MAX_BYTES = 25 * 1024 * 1024

_MODERN = {".pdf": read_pdf, ".docx": read_docx, ".pptx": read_pptx, ".xlsx": read_xlsx}


def validate_file(path: Path, max_bytes: int = DEFAULT_MAX_BYTES) -> Path:
    path = Path(path)
    if not path.exists() or not path.is_file():
        raise MaterialError(f"file tidak ditemukan: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedMaterialError(
            f"format tidak didukung: {path.suffix}. Didukung: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if path.stat().st_size == 0:
        raise MaterialError("file kosong")
    if path.stat().st_size > max_bytes:
        raise MaterialError(f"file terlalu besar (> {max_bytes // (1024 * 1024)} MB)")
    return path


def read_material(
    path: Path,
    work_dir: Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> MaterialDocument:
    path = validate_file(path, max_bytes=max_bytes)
    extension = path.suffix.lower()
    try:
        if extension in _MODERN:
            document = _MODERN[extension](path)
        else:
            document = read_legacy(path, work_dir=work_dir)
        document = normalize_document(document)
    except MaterialError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parser failure is a material problem
        raise MaterialError(
            f"materi rusak atau tidak dapat dibaca ({type(exc).__name__})"
        ) from exc
    if document.is_empty():
        raise MaterialError("materi kosong atau tidak dapat dibaca")
    return document
