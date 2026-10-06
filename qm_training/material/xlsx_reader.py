"""XLSX extractor (sheets + rows + columns)."""

from __future__ import annotations

from pathlib import Path

from qm_training.material.base import MaterialBlock, MaterialDocument


def read_xlsx(path: Path) -> MaterialDocument:
    import openpyxl

    workbook = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    blocks: list[MaterialBlock] = []
    try:
        for sheet in workbook.worksheets:
            blocks.append(MaterialBlock("sheet", sheet.title, meta={"sheet": sheet.title}))
            for row in sheet.iter_rows(values_only=True):
                values = [str(value) for value in row if value is not None and str(value).strip()]
                if values:
                    blocks.append(MaterialBlock("row", " | ".join(values), meta={"sheet": sheet.title}))
    finally:
        workbook.close()
    return MaterialDocument(source=str(path), format="xlsx", blocks=blocks)
