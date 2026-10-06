"""PDF extractor (text layer)."""

from __future__ import annotations

from pathlib import Path

from qm_training.material.base import MaterialBlock, MaterialDocument


def read_pdf(path: Path) -> MaterialDocument:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    blocks: list[MaterialBlock] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 - malformed page
            text = ""
        blocks.append(MaterialBlock("page", text, meta={"page": index}))
    return MaterialDocument(source=str(path), format="pdf", blocks=blocks)
