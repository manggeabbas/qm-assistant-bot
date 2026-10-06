"""Reusable DOCX document engine.

Input: validated :class:`~qm_training.document.schema.TrainingData`.
Output: working-copy DOCX (master untouched).

Layout is fully controlled by the template engine; the AI never touches it.
"""

from __future__ import annotations

import copy
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from qm_training.core.errors import DocumentGenerationError
from qm_training.document import photos as photos_module
from qm_training.document.answer_key import add_answer_key
from qm_training.document.schema import TrainingData
from qm_training.document.template import load_map, open_document, resolve_elements
from qm_training.document.xmlutil import (
    append_text_run,
    cells,
    ensure_unique_drawing_ids,
    paragraphs,
    replace_paragraph_text,
    rpr_at,
    replace_text_across_runs,
    rows,
    set_page_break_before,
    set_paragraph_tight_left,
    set_row_borders,
    set_row_cant_split,
    set_row_min_height,
    strip_dup_ids,
    keep_with_next,
)
from qm_training.paths import MASTER_TEMPLATE, OUTPUT_DIR, TEMPLATE_MAP

# Master memakai 504 twips untuk 13 baris. Dengan 15 baris + nilai Tema yang
# membungkus, 504 membuat baris ke-15 meluber. 450 twips tetap >= satu baris teks.
PERSONNEL_ROW_HEIGHT_TWIPS = 450


def fill_t01a(table, template: dict, data: TrainingData) -> None:
    fields = template["t01a"]["field_cells"]
    values = {
        "theme": data.theme,
        "archive_number": data.archive_number,
        "training_date": data.training_date,
        "location": data.location,
        "trainer": data.trainer,
    }
    for key, value in values.items():
        spec = fields[key]
        source = spec["style_source"]
        rpr = rpr_at(table, source["row"], source["cell"], source["paragraph"], source["run"])
        target = paragraphs(cells(rows(table)[spec["row"]])[spec["cell"]])[spec["paragraph"]]
        append_text_run(target, value, rpr)

    if data.personnel_count is not None:
        spec = fields["personnel_count"]
        source = spec["style_source"]
        rpr = rpr_at(table, source["row"], source["cell"], source["paragraph"], source["run"])
        target = paragraphs(cells(rows(table)[spec["row"]])[spec["cell"]])[spec["paragraph"]]
        append_text_run(target, f"{data.personnel_count}人", rpr)


def expand_t01a_personnel_rows(table, template: dict) -> None:
    """Working copy: pastikan tabel personil memiliki 15 baris bernomor 1..15."""
    rule = template["t01a"]["personnel_table"]
    start = rule["master_structure"]["data_rows"]["start"]
    target_count = rule["working_copy_rule"]["target_data_row_count"]
    row_template = rule["working_copy_rule"]["row_template"]

    existing = rows(table)
    missing = target_count - (len(existing) - start)
    for _ in range(max(0, missing)):
        clone = copy.deepcopy(existing[row_template])
        strip_dup_ids(clone)
        table.append(clone)

    for index, row in enumerate(rows(table)[start:start + target_count], start=1):
        set_row_min_height(row, PERSONNEL_ROW_HEIGHT_TWIPS)
        replace_paragraph_text(paragraphs(cells(row)[0])[0], str(index))


def fill_t03a(table, template: dict, data: TrainingData) -> None:
    spec = template["t03a"]
    values = {
        "name": None,
        "nik": None,
        "dept": "QM",
        "moderator": data.trainer,
        "training_date": data.training_date,
        "workshop": "QMYWI",
        "topic": data.theme,
        "score": None,
    }
    for key, cell_spec in spec["identity_cells"].items():
        value = values[key]
        if value is None:  # blank rule
            continue
        source = spec["style_sources"][key]
        rpr = rpr_at(table, source["row"], source["cell"], source["paragraph"], source["run"])
        target = paragraphs(cells(rows(table)[cell_spec["row"]])[cell_spec["cell"]])[cell_spec["paragraph"]]
        append_text_run(target, value, rpr)
        if key == "topic":
            # Topik T03A saja: paksa rata kiri + rapat agar teks panjang
            # yang membungkus tidak terlihat renggang.
            set_paragraph_tight_left(target)

    questions = spec["questions"]
    placeholder = spec.get("question_placeholder", "TEMPATKAN PERTANYAAN DISINI")
    if len(data.questions) != questions["count"]:
        raise ValueError(f"harus tepat {questions['count']} pertanyaan")

    # TEMPLATE PRESERVATION: locate the existing placeholder paragraphs and
    # replace ONLY the placeholder text. Never create rows/paragraphs/tables,
    # never touch borders/merge/table style.
    placeholder_paragraphs = [
        paragraph
        for paragraph in table.iter(qn("w:p"))
        if placeholder in "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
    ]
    if len(placeholder_paragraphs) != questions["count"]:
        raise DocumentGenerationError(
            f"jumlah placeholder '{placeholder}' = {len(placeholder_paragraphs)}, "
            f"diharapkan {questions['count']} pada master"
        )
    for paragraph, qa in zip(placeholder_paragraphs, data.questions):
        if replace_text_across_runs(paragraph, placeholder, qa.question) != 1:
            raise DocumentGenerationError("gagal mengganti placeholder pertanyaan")

    # Keep each question row together with its answer row: a question block is
    # one visual unit (PRD §25) and must not be split across pages.
    for question_spec in questions["rows"]:
        row = rows(table)[question_spec["row"]]
        for paragraph in paragraphs(cells(row)[0]):
            keep_with_next(paragraph)
    # No T03A row may split across pages (a split last row leaves an empty
    # fragment on the next page -> "blank page").
    for row in rows(table):
        set_row_cant_split(row)

    # Question area borders: keep ONLY the outer horizontal edges (the top edge
    # of the question block and the table's bottom edge); hide the inner
    # horizontal lines. Vertical borders are left untouched.
    table_rows = rows(table)
    if len(table_rows) > 4:
        set_row_borders(table_rows[3], bottom=True)             # top edge of the question block
        for row in table_rows[4:-1]:
            set_row_borders(row, top=False, bottom=False)       # inner lines hidden
        set_row_borders(table_rows[-1], top=False, bottom=True)  # outer bottom edge


def _replace_master_section_breaks(doc: Document, template: dict) -> None:
    """Convert standalone page-break paragraphs into pageBreakBefore.

    The master separates sections with a paragraph that only holds a page
    break. When the preceding table fills the page, that paragraph overflows to
    the next page and forces a *second* break, producing an empty page. Setting
    `w:pageBreakBefore` on the next section's first paragraph avoids this.
    """
    children = list(doc.element.body)
    for entry in template["page_breaks"]:
        if not entry.get("present_in_master"):
            continue
        index = entry["master_body_block"]
        if index + 1 >= len(children):
            continue
        next_element = children[index + 1]
        break_element = children[index]
        if next_element.tag == qn("w:p"):
            set_page_break_before(next_element)
        parent = break_element.getparent()
        if parent is not None:
            parent.remove(break_element)


def build_document(data: TrainingData, template: dict | None = None, master: Path = MASTER_TEMPLATE) -> Document:
    """Build the full working-copy document in memory."""
    data.validate()
    template = template or load_map()
    doc = open_document(master)
    elements = resolve_elements(doc, template)
    _replace_master_section_breaks(doc, template)

    fill_t01a(elements.t01a, template, data)
    expand_t01a_personnel_rows(elements.t01a, template)
    photos_module.clean_t02a(doc, elements.t02a, template)
    photos_module.build_t02a_photos(doc, template, data.photos, elements.t02a, elements.t02a_templates)
    fill_t03a(elements.t03a, template, data)

    # Drop the master's trailing empty paragraph (an artifact right after the
    # T03A table). If it is left after long content it overflows to an
    # unnecessary blank page. It is empty, so no visible layout is lost.
    trailing = elements.t03a.getnext()
    if trailing is not None and trailing.tag == qn("w:p"):
        if not "".join(node.text or "" for node in trailing.iter(qn("w:t"))).strip():
            trailing.getparent().remove(trailing)

    add_answer_key(doc, template, data, elements.t03a, elements.t03a_logo)
    ensure_unique_drawing_ids(doc.element.body)
    return doc


def generate(
    data: TrainingData,
    master: Path = MASTER_TEMPLATE,
    out_dir: Path = OUTPUT_DIR,
    template_map: Path = TEMPLATE_MAP,
    output_name: str | None = None,
) -> Path:
    """Generate the DOCX and return its path."""
    template = load_map(template_map)
    doc = build_document(data, template=template, master=master)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{output_name or data.output_basename()}.docx"
    doc.save(str(output))
    return output
