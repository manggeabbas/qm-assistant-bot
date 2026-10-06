"""T02A photo handling: remove broken master samples and place user photos."""

from __future__ import annotations

import copy
import math
from pathlib import Path

from docx.oxml.ns import qn
from docx.shared import Emu
from docx.text.paragraph import Paragraph
from PIL import Image

from qm_training.document.xmlutil import (
    EMU_PER_TWIP,
    cells,
    paragraphs,
    rows,
    set_page_break_before,
    set_row_min_height,
    strip_dup_ids,
)

# Ruang yang disisihkan untuk paragraf caption di setiap baris foto.
CAPTION_ALLOWANCE_TWIPS = 700


def clean_t02a(doc, table, template: dict) -> None:
    """Buang gambar foto contoh master yang rusak (extent 0) dan relasinya."""
    for cell in table.iter(qn("w:tc")):
        for drawing in list(cell.iter(qn("w:drawing"))):
            drawing.getparent().remove(drawing)
    for rel_id in template["t02a"]["master_broken_images"]["relationship_ids"]:
        try:
            doc.part.drop_rel(rel_id)
        except KeyError:
            pass


def _add_photo(doc, paragraph_el, photo: Path, max_w: int, max_h: int) -> None:
    with Image.open(photo) as image:
        width, height = image.size
    scale = min(max_w / width, max_h / height)
    draw_w = max(1, int(width * scale))
    draw_h = max(1, int(height * scale))
    run = Paragraph(paragraph_el, doc).add_run()
    run.add_picture(str(photo), width=Emu(draw_w), height=Emu(draw_h))


def photo_frame(template: dict) -> tuple[int, int]:
    frame = template["t02a"]["cell_frame"]
    max_w = frame["inner_width_twips"] * EMU_PER_TWIP
    max_h = max(1, frame["row_height_twips"] - CAPTION_ALLOWANCE_TWIPS) * EMU_PER_TWIP
    return max_w, max_h


def build_t02a_photos(doc, template: dict, photos: list[Path], table, templates: list) -> None:
    """Distribusikan foto ke slot T02A; duplikasi blok tiap 2 foto."""
    per_page = template["t02a"]["max_photos_per_page"]
    pages = max(1, math.ceil(len(photos) / per_page))
    max_w, max_h = photo_frame(template)

    page_tables = [table]
    last = table
    for _ in range(1, pages):
        for position, original in enumerate(templates):
            clone = copy.deepcopy(original)
            strip_dup_ids(clone)
            if position == 0 and clone.tag == qn("w:p"):
                set_page_break_before(clone)  # page break, but no blank page
            last.addnext(clone)
            last = clone
            if original is table:
                page_tables.append(clone)

    # Paksa tinggi baris sesuai template agar 2 foto muat dalam 1 halaman.
    # Nilai master (5328 twips atLeast) + header ~3800 twips melebihi tinggi
    # badan halaman (14390 twips) sehingga baris kedua tumpah ke halaman baru.
    row_height = template["t02a"]["cell_frame"]["row_height_twips"]
    for page_table in page_tables:
        for row in rows(page_table):
            set_row_min_height(row, row_height)

    slots = []
    for page_table in page_tables:
        for row in rows(page_table):
            cell_paragraphs = paragraphs(cells(row)[0])
            slots.append(cell_paragraphs[1] if len(cell_paragraphs) > 1 else cell_paragraphs[0])

    for photo, slot in zip(photos, slots):
        _add_photo(doc, slot, Path(photo), max_w, max_h)
