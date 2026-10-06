"""Legacy Office formats (.doc/.ppt/.xls) via LibreOffice conversion.

LibreOffice is converted to the modern OOXML equivalent in a temp directory and
then read by the corresponding reader. The reported format keeps the original
extension so callers still know what the user uploaded.
"""

from __future__ import annotations

from pathlib import Path

from qm_training.core.errors import MaterialError
from qm_training.core.libreoffice import convert
from qm_training.material.base import MaterialDocument
from qm_training.material.docx_reader import read_docx
from qm_training.material.pptx_reader import read_pptx
from qm_training.material.xlsx_reader import read_xlsx
from qm_training.paths import OUTPUT_DIR

LEGACY_TARGETS = {".doc": "docx", ".ppt": "pptx", ".xls": "xlsx"}
DEFAULT_WORK_DIR = OUTPUT_DIR / "material_tmp"


def read_legacy(path: Path, work_dir: Path | None = None) -> MaterialDocument:
    extension = Path(path).suffix.lower()
    target = LEGACY_TARGETS.get(extension)
    if target is None:
        raise MaterialError(f"format legacy tidak didukung: {extension}")
    # LibreOffice (flatpak) tidak dapat mengakses /tmp host, jadi default work
    # dir ditempatkan di dalam project (di bawah home).
    out_dir = Path(work_dir) if work_dir else DEFAULT_WORK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    converted = convert(Path(path), target, out_dir)
    reader = {"docx": read_docx, "pptx": read_pptx, "xlsx": read_xlsx}[target]
    document = reader(converted)
    document.format = extension.lstrip(".")
    return document
