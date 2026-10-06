"""PDF rendering / text helpers (poppler)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True)
    match = re.search(r"^Pages:\s+(\d+)", result.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("tidak dapat membaca jumlah halaman PDF")
    return int(match.group(1))


def pdf_pages_text(pdf_path: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"], capture_output=True, text=True, check=True
    )
    pages = result.stdout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def render_pdf_to_png(pdf_path: Path, out_dir: Path, dpi: int = 110) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / Path(pdf_path).stem
    for stale in out_dir.glob(f"{prefix.name}-*.png"):
        stale.unlink()
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(out_dir.glob(f"{prefix.name}-*.png"))
