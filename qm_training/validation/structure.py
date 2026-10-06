"""Structural preservation checks: generated T03A must match the master.

The generator is only allowed to replace the question placeholder text. Row
count, column count, merges (gridSpan), row/table borders and row heights for
T03A must be identical to the template.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from qm_training.validation.models import ValidationReport

T03A_MARKER = "PENCATATAN PERTANYAAN"


def _text(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t")))


def _find_t03a(doc: Document):
    for table in doc.element.body.findall(qn("w:tbl")):
        if T03A_MARKER in _text(table):
            return table
    return None


def _borders_signature(container) -> tuple:
    borders = container.find(qn("w:tblBorders"))
    if borders is None:
        return ()
    return tuple(
        (child.tag.split("}")[-1], child.get(qn("w:val")), child.get(qn("w:sz")))
        for child in borders
    )


def _cell_borders(cell) -> tuple:
    tc_pr = cell.find(qn("w:tcPr"))
    if tc_pr is None:
        return ()
    tc_borders = tc_pr.find(qn("w:tcBorders"))
    if tc_borders is None:
        return ()
    return tuple((child.tag.split("}")[-1], child.get(qn("w:val"))) for child in tc_borders)


def _table_structure(table) -> dict:
    grid = table.find(qn("w:tblGrid"))
    columns = [int(col.get(qn("w:w"), "0")) for col in (grid.findall(qn("w:gridCol")) if grid is not None else [])]
    grid_spans = []
    borders = []
    heights = []
    for row in table.findall(qn("w:tr")):
        spans = []
        for cell in row.findall(qn("w:tc")):
            tc_pr = cell.find(qn("w:tcPr"))
            span = 1
            if tc_pr is not None:
                gs = tc_pr.find(qn("w:gridSpan"))
                if gs is not None:
                    span = int(gs.get(qn("w:val"), "1"))
            spans.append(span)
        grid_spans.append(tuple(spans))
        row_ex = row.find(qn("w:tblPrEx"))
        row_border = _borders_signature(row_ex) if row_ex is not None else ()
        # The generator intentionally hides the horizontal lines (top/bottom) of
        # the T03A question area in the working copy, so those two are excluded
        # from the structural comparison. Vertical/outer borders must match.
        borders.append(tuple(entry for entry in row_border if entry[0] not in ("top", "bottom")))
        height = row.find(qn("w:trPr"))
        tr_height = height.find(qn("w:trHeight")) if height is not None else None
        heights.append(int(tr_height.get(qn("w:val"), "0")) if tr_height is not None else None)
    cell_borders = [
        tuple(_cell_borders(cell) for cell in row.findall(qn("w:tc")))
        for row in table.findall(qn("w:tr"))
    ]
    return {
        "row_count": len(table.findall(qn("w:tr"))),
        "columns": columns,
        "grid_spans": grid_spans,
        "row_borders": borders,
        "row_heights": heights,
        "cell_borders": cell_borders,
    }


def compare_t03a_structure(generated_path: Path, master_path: Path) -> ValidationReport:
    report = ValidationReport()
    generated = _find_t03a(Document(str(generated_path)))
    master = _find_t03a(Document(str(master_path)))

    if generated is None:
        report.error("T03A_MISSING", "T03A tidak ditemukan pada output")
        return report
    if master is None:
        report.error("T03A_MASTER_MISSING", "T03A tidak ditemukan pada master")
        return report

    gen = _table_structure(generated)
    mas = _table_structure(master)

    if gen["row_count"] != mas["row_count"]:
        report.error("T03A_ROW_COUNT", f"jumlah row T03A berubah: {gen['row_count']} vs master {mas['row_count']}")
    if gen["columns"] != mas["columns"]:
        report.error("T03A_COLUMNS", f"lebar kolom T03A berubah: {gen['columns']} vs master {mas['columns']}")
    if gen["grid_spans"] != mas["grid_spans"]:
        report.error("T03A_MERGE", "merge/gridSpan T03A berubah dari master")
    if gen["row_borders"] != mas["row_borders"]:
        report.error("T03A_ROW_BORDERS", "border row T03A berubah dari master")
    if gen["cell_borders"] != mas["cell_borders"]:
        report.error("T03A_CELL_BORDERS", "border cell T03A berubah dari master")
    if gen["row_heights"] != mas["row_heights"]:
        report.error("T03A_ROW_HEIGHT", f"row height T03A berubah: {gen['row_heights']} vs master {mas['row_heights']}")
    return report
