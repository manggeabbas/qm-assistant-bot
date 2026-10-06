"""Format-specific extractors."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from qm_training.material.base import MaterialBlock, MaterialDocument


def read_docx(path: Path) -> MaterialDocument:
    document = Document(str(path))
    blocks: list[MaterialBlock] = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            text = (paragraph.text or "").strip()
            if not text:
                continue
            style = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
            if style.startswith("heading") or style in ("title", "subtitle"):
                level = None
                digits = "".join(ch for ch in style if ch.isdigit())
                if digits:
                    level = int(digits)
                blocks.append(MaterialBlock("heading", text, level=level))
            else:
                blocks.append(MaterialBlock("paragraph", text))
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            lines = [" | ".join((cell.text or "").strip() for cell in row.cells) for row in table.rows]
            text = "\n".join(line for line in lines if line.strip(" |"))
            if text:
                blocks.append(MaterialBlock("table", text, meta={"rows": len(table.rows)}))
    return MaterialDocument(source=str(path), format="docx", blocks=blocks)
