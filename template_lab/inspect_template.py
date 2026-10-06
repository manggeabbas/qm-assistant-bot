"""Read-only inspection of the master DOCX template.

STEP 1 of the Template Laboratory. The script reports the physical structure of
the document (sections, body blocks, tables, rows, cells, drawings, images,
footer) and writes a machine-readable inventory that is used to build
``template_map.json``.

The master file is opened read-only; nothing is written back to it.

Run:
    .venv/bin/python -m template_lab.inspect_template
    .venv/bin/python -m template_lab.inspect_template --docx path/to/file.docx
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from template_lab.paths import MASTER_TEMPLATE, OUTPUT_DIR, TEMPLATE_INVENTORY

# --------------------------------------------------------------------------- #
# XML namespaces
# --------------------------------------------------------------------------- #

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

TWIPS_PER_CM = 566.929


def qn(tag: str) -> str:
    """Expand ``prefix:local`` into Clark notation for lxml."""
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


# --------------------------------------------------------------------------- #
# Package / part loading
# --------------------------------------------------------------------------- #


def read_package(docx_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(docx_path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def parse_rels(data: bytes | None) -> dict[str, dict[str, str]]:
    if not data:
        return {}
    root = etree.fromstring(data)
    rels: dict[str, dict[str, str]] = {}
    for rel in root.findall(qn("rel:Relationship")):
        rels[rel.get("Id", "")] = {
            "type": rel.get("Type", ""),
            "target": rel.get("Target", ""),
        }
    return rels


# --------------------------------------------------------------------------- #
# Low-level readers
# --------------------------------------------------------------------------- #


def element_text(element: etree._Element) -> str:
    """Concatenate visible text of a paragraph/cell, marking tabs and breaks."""
    parts: list[str] = []
    for node in element.iter():
        if node.tag == qn("w:t"):
            parts.append(node.text or "")
        elif node.tag == qn("w:tab"):
            parts.append("\t")
        elif node.tag == qn("w:br"):
            kind = node.get(qn("w:type"))
            parts.append("<PAGE_BREAK>" if kind == "page" else "\n")
        elif node.tag == qn("w:cr"):
            parts.append("\n")
    return "".join(parts)


def drawing_info(drawing: etree._Element, rels: dict[str, dict[str, str]]) -> dict[str, Any]:
    inline = drawing.find(qn("wp:inline"))
    anchor = drawing.find(qn("wp:anchor"))
    node = inline if inline is not None else anchor
    kind = "inline" if inline is not None else ("anchor" if anchor is not None else "unknown")

    info: dict[str, Any] = {"kind": kind}
    if node is None:
        return info

    extent = node.find(qn("wp:extent"))
    if extent is not None:
        cx = int(extent.get("cx", "0"))
        cy = int(extent.get("cy", "0"))
        info["extent_emu"] = {"cx": cx, "cy": cy}
        info["extent_cm"] = {
            "cx": round(cx / 360000, 2),
            "cy": round(cy / 360000, 2),
        }

    doc_pr = node.find(qn("wp:docPr"))
    if doc_pr is not None:
        info["doc_pr"] = {
            "id": doc_pr.get("id"),
            "name": doc_pr.get("name"),
            "descr": doc_pr.get("descr"),
        }

    blip = node.find(f".//{qn('a:blip')}")
    if blip is not None:
        embed = blip.get(qn("r:embed"))
        info["embed"] = embed
        info["target"] = rels.get(embed, {}).get("target") if embed else None

    if anchor is not None:
        for wrap in ("wrapNone", "wrapSquare", "wrapTight", "wrapThrough", "wrapTopAndBottom"):
            if anchor.find(qn(f"wp:{wrap}")) is not None:
                info["wrap"] = wrap
                break
        for axis in ("positionH", "positionV"):
            pos = anchor.find(qn(f"wp:{axis}"))
            if pos is not None:
                offset = pos.find(qn("wp:posOffset"))
                info[f"{axis}_offset"] = int(offset.text) if offset is not None and offset.text else None
                info[f"{axis}_relative_from"] = pos.get("relativeFrom")

    return info


def run_info(run: etree._Element) -> dict[str, Any]:
    r_pr = run.find(qn("w:rPr"))
    fonts = r_pr.find(qn("w:rFonts")) if r_pr is not None else None
    size = r_pr.find(qn("w:sz")) if r_pr is not None else None
    bold = r_pr.find(qn("w:b")) if r_pr is not None else None
    return {
        "text": element_text(run),
        "ascii_font": fonts.get(qn("w:ascii")) if fonts is not None else None,
        "east_asia_font": fonts.get(qn("w:eastAsia")) if fonts is not None else None,
        "size_half_points": int(size.get(qn("w:val"), "0")) if size is not None else None,
        "bold": bold is not None and bold.get(qn("w:val"), "true") not in ("0", "false"),
    }


def paragraph_info(paragraph: etree._Element, rels: dict[str, dict[str, str]]) -> dict[str, Any]:
    p_pr = paragraph.find(qn("w:pPr"))
    style = None
    justification = None
    if p_pr is not None:
        style_node = p_pr.find(qn("w:pStyle"))
        style = style_node.get(qn("w:val")) if style_node is not None else None
        jc_node = p_pr.find(qn("w:jc"))
        justification = jc_node.get(qn("w:val")) if jc_node is not None else None

    text = element_text(paragraph)
    page_break = "<PAGE_BREAK>" in text
    drawings = [drawing_info(d, rels) for d in paragraph.iter(qn("w:drawing"))]
    runs = [run_info(r) for r in paragraph.findall(qn("w:r"))]

    return {
        "text": text.replace("<PAGE_BREAK>", ""),
        "style": style,
        "justification": justification,
        "page_break": page_break,
        "drawings": drawings,
        "run_count": len(runs),
        "runs": runs,
    }


def cell_info(cell: etree._Element, rels: dict[str, dict[str, str]]) -> dict[str, Any]:
    tc_pr = cell.find(qn("w:tcPr"))
    width = None
    width_type = None
    grid_span = 1
    vertical_merge = None
    if tc_pr is not None:
        tc_w = tc_pr.find(qn("w:tcW"))
        if tc_w is not None:
            width = int(tc_w.get(qn("w:w"), "0"))
            width_type = tc_w.get(qn("w:type"))
        gs = tc_pr.find(qn("w:gridSpan"))
        if gs is not None:
            grid_span = int(gs.get(qn("w:val"), "1"))
        vm = tc_pr.find(qn("w:vMerge"))
        if vm is not None:
            vertical_merge = vm.get(qn("w:val"), "continue")

    paragraphs = [paragraph_info(p, rels) for p in cell.findall(qn("w:p"))]
    text = "\n".join(p["text"] for p in paragraphs)
    drawings = [d for p in paragraphs for d in p["drawings"]]

    return {
        "width_twips": width,
        "width_type": width_type,
        "grid_span": grid_span,
        "vertical_merge": vertical_merge,
        "text": text,
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
        "drawings": drawings,
    }


def row_info(row: etree._Element, rels: dict[str, dict[str, str]]) -> dict[str, Any]:
    tr_pr = row.find(qn("w:trPr"))
    height = None
    height_rule = None
    if tr_pr is not None:
        tr_h = tr_pr.find(qn("w:trHeight"))
        if tr_h is not None:
            height = int(tr_h.get(qn("w:val"), "0"))
            height_rule = tr_h.get(qn("w:hRule"))
    cells = [cell_info(tc, rels) for tc in row.findall(qn("w:tc"))]
    return {
        "height_twips": height,
        "height_rule": height_rule,
        "cells": cells,
        "text": " | ".join(c["text"].strip() for c in cells),
    }


def table_info(table: etree._Element, index: int, rels: dict[str, dict[str, str]]) -> dict[str, Any]:
    tbl_pr = table.find(qn("w:tblPr"))
    width = None
    layout = None
    justification = None
    if tbl_pr is not None:
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is not None:
            width = int(tbl_w.get(qn("w:w"), "0"))
        layout_node = tbl_pr.find(qn("w:tblLayout"))
        layout = layout_node.get(qn("w:type")) if layout_node is not None else None
        jc_node = tbl_pr.find(qn("w:jc"))
        justification = jc_node.get(qn("w:val")) if jc_node is not None else None

    grid = table.find(qn("w:tblGrid"))
    columns = [
        int(col.get(qn("w:w"), "0"))
        for col in (grid.findall(qn("w:gridCol")) if grid is not None else [])
    ]

    rows = [row_info(tr, rels) for tr in table.findall(qn("w:tr"))]
    return {
        "index": index,
        "width_twips": width,
        "layout": layout,
        "justification": justification,
        "column_count": len(columns),
        "column_widths_twips": columns,
        "row_count": len(rows),
        "rows": rows,
    }


def section_info(sect_pr: etree._Element) -> dict[str, Any]:
    page_size = sect_pr.find(qn("w:pgSz"))
    margins = sect_pr.find(qn("w:pgMar"))
    cols = sect_pr.find(qn("w:cols"))

    info: dict[str, Any] = {}
    if page_size is not None:
        info["page_size_twips"] = {
            "w": int(page_size.get(qn("w:w"), "0")),
            "h": int(page_size.get(qn("w:h"), "0")),
        }
    if margins is not None:
        info["margins_twips"] = {
            key: int(margins.get(qn(f"w:{key}"), "0"))
            for key in ("top", "right", "bottom", "left", "header", "footer", "gutter")
        }
    if cols is not None:
        info["columns"] = int(cols.get(qn("w:num"), "1"))

    if "page_size_twips" in info and "margins_twips" in info:
        ps = info["page_size_twips"]
        mg = info["margins_twips"]
        info["content_width_twips"] = ps["w"] - mg["left"] - mg["right"]
        info["content_height_twips"] = ps["h"] - mg["top"] - mg["bottom"]

    info["footer_references"] = [
        {"id": ref.get(qn("r:id")), "type": ref.get(qn("w:type"))}
        for ref in sect_pr.findall(qn("w:footerReference"))
    ]
    info["header_references"] = [
        {"id": ref.get(qn("r:id")), "type": ref.get(qn("w:type"))}
        for ref in sect_pr.findall(qn("w:headerReference"))
    ]
    return info


def footer_info(parts: dict[str, bytes]) -> dict[str, Any] | None:
    data = parts.get("word/footer1.xml")
    if not data:
        return None
    root = etree.fromstring(data)
    paragraphs = [p for p in root.iter(qn("w:p"))]
    text = "".join(element_text(p) for p in paragraphs)
    fields = [node.text.strip() for node in root.iter(qn("w:instrText")) if node.text]
    return {"part": "footer1.xml", "text": text, "fields": fields}


def media_info(parts: dict[str, bytes]) -> list[dict[str, Any]]:
    from PIL import Image  # imported lazily so inspection of XML-only data still works

    items: list[dict[str, Any]] = []
    for name in sorted(parts):
        if not name.startswith("word/media/") or name.endswith("/"):
            continue
        data = parts[name]
        entry: dict[str, Any] = {"name": name.rsplit("/", 1)[-1], "bytes": len(data)}
        try:
            with Image.open(io.BytesIO(data)) as image:
                entry["pixel_size"] = {"w": image.width, "h": image.height}
                entry["format"] = image.format
        except Exception as exc:  # pragma: no cover - defensive
            entry["error"] = str(exc)
        items.append(entry)
    return items


def app_properties(parts: dict[str, bytes]) -> dict[str, Any]:
    data = parts.get("docProps/app.xml")
    if not data:
        return {}
    root = etree.fromstring(data)
    out: dict[str, Any] = {}
    for child in root:
        tag = etree.QName(child).localname
        if child.text:
            out[tag] = child.text
    return out


# --------------------------------------------------------------------------- #
# Body traversal
# --------------------------------------------------------------------------- #


def body_structure(body: etree._Element, rels: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    table_index = 0
    for child in body:
        if child.tag == qn("w:p"):
            info = paragraph_info(child, rels)
            info["kind"] = "paragraph"
            blocks.append(info)
        elif child.tag == qn("w:tbl"):
            info = table_info(child, table_index, rels)
            info["kind"] = "table"
            blocks.append(info)
            table_index += 1
        elif child.tag == qn("w:sectPr"):
            blocks.append({"kind": "section_properties", "section": section_info(child)})
    return blocks


def find_sect_pr(body: etree._Element) -> etree._Element | None:
    sect = body.find(qn("w:sectPr"))
    if sect is not None:
        return sect
    for paragraph in body.findall(qn("w:p")):
        p_pr = paragraph.find(qn("w:pPr"))
        if p_pr is not None:
            nested = p_pr.find(qn("w:sectPr"))
            if nested is not None:
                return nested
    return None


# --------------------------------------------------------------------------- #
# Warnings (layout/consistency issues found during inspection)
# --------------------------------------------------------------------------- #


def collect_warnings(inventory: dict[str, Any]) -> list[str]:
    warnings: list[str] = []

    body_text = " ".join(
        block.get("text", "") for block in inventory["body"] if block["kind"] == "paragraph"
    )
    for table in inventory["tables"]:
        for row in table["rows"]:
            for cell in row["cells"]:
                body_text += " " + cell["text"]
    if "kunci" not in body_text.lower() and "答案" not in body_text:
        warnings.append(
            "Halaman KUNCI JAWABAN tidak ditemukan di master (tidak ada teks 'KUNCI'/'答案')."
        )

    content_width = inventory["section"].get("content_width_twips")
    for table in inventory["tables"]:
        width = table.get("width_twips")
        if width and content_width and width > content_width:
            warnings.append(
                f"Tabel #{table['index']} lebih lebar dari area teks "
                f"({width} > {content_width} twips); melebar ke margin (by design, jangan diubah tanpa keputusan)."
            )

    for block in inventory["body"]:
        if block["kind"] != "paragraph":
            continue
        for drawing in block.get("drawings", []):
            extent = drawing.get("extent_emu")
            if extent and (extent["cx"] <= 0 or extent["cy"] <= 0):
                warnings.append(
                    f"Gambar rusak (extent {extent['cx']}x{extent['cy']} EMU) pada "
                    f"{drawing.get('target')} — harus diabaikan pada working copy."
                )
    for table in inventory["tables"]:
        for row in table["rows"]:
            for cell in row["cells"]:
                for drawing in cell["drawings"]:
                    extent = drawing.get("extent_emu")
                    if extent and (extent["cx"] <= 0 or extent["cy"] <= 0):
                        warnings.append(
                            f"Gambar rusak (extent {extent['cx']}x{extent['cy']} EMU) pada "
                            f"{drawing.get('target')} — harus diabaikan pada working copy."
                        )

    for table in inventory["tables"]:
        numbers = []
        for row in table["rows"]:
            if not row["cells"]:
                continue
            first = row["cells"][0]["text"].strip()
            if first.isdigit():
                numbers.append(int(first))
        if numbers and numbers != list(range(1, len(numbers) + 1)):
            warnings.append(
                f"Nomor urut kolom pertama Tabel #{table['index']} tidak berurutan: {numbers}."
            )

    if not inventory["section"].get("header_references"):
        warnings.append("Master tidak memiliki header (hanya footer).")

    return warnings


# --------------------------------------------------------------------------- #
# Top-level inspection
# --------------------------------------------------------------------------- #


def inspect(docx_path: Path) -> dict[str, Any]:
    parts = read_package(docx_path)
    document = etree.fromstring(parts["word/document.xml"])
    rels = parse_rels(parts.get("word/_rels/document.xml.rels"))
    body = document.find(qn("w:body"))

    sect_pr = find_sect_pr(body)
    section = section_info(sect_pr) if sect_pr is not None else {}
    # Resolve footer/header relationships to concrete parts.
    section["footer_parts"] = [
        rels.get(ref["id"], {}).get("target") for ref in section.get("footer_references", [])
    ]
    section["header_parts"] = [
        rels.get(ref["id"], {}).get("target") for ref in section.get("header_references", [])
    ]

    body_blocks = body_structure(body, rels)
    tables = [block for block in body_blocks if block["kind"] == "table"]

    inventory: dict[str, Any] = {
        "source": str(docx_path),
        "package": {
            "part_count": len(parts),
            "parts": sorted(parts),
            "app_properties": app_properties(parts),
        },
        "section": section,
        "footer": footer_info(parts),
        "media": media_info(parts),
        "tables": tables,
        "body": [
            block if block["kind"] != "table" else {"kind": "table", "index": block["index"]}
            for block in body_blocks
        ],
    }
    inventory["warnings"] = collect_warnings(inventory)
    return inventory


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def twips_to_cm(value: int) -> float:
    return round(value / TWIPS_PER_CM, 2)


def print_summary(inv: dict[str, Any]) -> None:
    print(f"MASTER : {inv['source']}")
    app = inv["package"]["app_properties"]
    print(
        f"PACKAGE: {inv['package']['part_count']} parts | "
        f"Pages(cached)={app.get('Pages', '?')} | Words={app.get('Words', '?')}"
    )

    section = inv["section"]
    ps = section.get("page_size_twips", {})
    mg = section.get("margins_twips", {})
    print(
        "PAGE   : "
        f"{ps.get('w')}x{ps.get('h')} twips | margins T{mg.get('top')} "
        f"R{mg.get('right')} B{mg.get('bottom')} L{mg.get('left')} | "
        f"content {section.get('content_width_twips')}x{section.get('content_height_twips')} twips"
    )
    print(f"COLUMNS: {section.get('columns')}")
    if inv["footer"]:
        fields = ", ".join(inv["footer"]["fields"])
        print(f"FOOTER : {inv['footer']['part']} | fields=[{fields}]")
    else:
        print("FOOTER : (none)")
    print(f"HEADER : {section.get('header_parts') or '(none)'}")

    print("\nBODY ORDER")
    for i, block in enumerate(inv["body"]):
        if block["kind"] == "table":
            print(f"  [{i}] table #{block['index']}")
        elif block["kind"] == "paragraph":
            flags = []
            if block["page_break"]:
                flags.append("PAGE_BREAK")
            if block["drawings"]:
                flags.append(f"{len(block['drawings'])} drawing(s)")
            text = block["text"].strip().replace("\n", " ")
            if len(text) > 60:
                text = text[:57] + "..."
            suffix = f" <{', '.join(flags)}>" if flags else ""
            print(f"  [{i}] paragraph {text!r}{suffix}")
        elif block["kind"] == "section_properties":
            print(f"  [{i}] section_properties")

    for table in inv["tables"]:
        print(
            f"\nTABLE #{table['index']}: {table['column_count']} cols x {table['row_count']} rows | "
            f"width={table['width_twips']} twips ({twips_to_cm(table['width_twips']) if table['width_twips'] else '?'} cm) | "
            f"layout={table['layout']} | jc={table['justification']}"
        )
        for r_i, row in enumerate(table["rows"]):
            parts = []
            for cell in row["cells"]:
                span = f"/s{cell['grid_span']}" if cell["grid_span"] > 1 else ""
                text = cell["text"].strip().replace("\n", " ")
                if len(text) > 26:
                    text = text[:23] + "..."
                images = f" +{len(cell['drawings'])}img" if cell["drawings"] else ""
                parts.append(f"[{cell['width_twips']}{span}]{text!r}{images}")
            print(f"  r{r_i} h={row['height_twips']}: " + " | ".join(parts))

    if inv["media"]:
        print("\nMEDIA")
        for item in inv["media"]:
            size = item.get("pixel_size", {})
            print(
                f"  {item['name']}: {size.get('w')}x{size.get('h')} px, "
                f"{item.get('format')}, {item['bytes']} bytes"
            )

    print("\nWARNINGS")
    if inv["warnings"]:
        for warning in inv["warnings"]:
            print(f"  - {warning}")
    else:
        print("  (none)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the master DOCX template (read-only).")
    parser.add_argument("--docx", type=Path, default=MASTER_TEMPLATE)
    parser.add_argument("--out", type=Path, default=TEMPLATE_INVENTORY)
    parser.add_argument("--quiet", action="store_true", help="only write the JSON, no summary")
    args = parser.parse_args()

    if not args.docx.exists():
        parser.error(f"file not found: {args.docx}")

    inventory = inspect(args.docx)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(inventory, indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.quiet:
        print_summary(inventory)
        print(f"\nInventory written to: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
