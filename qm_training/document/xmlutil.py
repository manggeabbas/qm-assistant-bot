"""Low-level OOXML helpers shared by the document modules."""

from __future__ import annotations

import copy

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
W14_NS = "{http://schemas.microsoft.com/office/word/2010/wordml}"
EMU_PER_TWIP = 635
EMU_PER_CM = 360000
BODY_FONT_ASCII = "Times New Roman"
BODY_FONT_EAST_ASIA = "仿宋"


def rows(table) -> list:
    return table.findall(qn("w:tr"))


def cells(row) -> list:
    return row.findall(qn("w:tc"))


def paragraphs(cell) -> list:
    return cell.findall(qn("w:p"))


def strip_dup_ids(element) -> None:
    """Remove w14 ids from a cloned element so cloned content stays unique."""
    for node in element.iter():
        for attr in list(node.attrib):
            if attr.startswith(W14_NS):
                del node.attrib[attr]


def ensure_unique_drawing_ids(body) -> None:
    """Reassign unique wp:docPr / pic:cNvPr ids across the whole document."""
    counter = 1
    for node in body.iter(qn("wp:docPr")):
        node.set("id", str(counter))
        node.set("name", f"Picture {counter}")
        counter += 1
    for node in body.iter(qn("pic:cNvPr")):
        node.set("id", str(counter))
        counter += 1


def rpr_at(table, row: int, cell: int, paragraph: int, run: int):
    runs = paragraphs(cells(rows(table)[row])[cell])[paragraph].findall(qn("w:r"))
    if 0 <= run < len(runs):
        return runs[run].find(qn("w:rPr"))
    return None


def append_text_run(paragraph, text: str, rpr=None):
    run = OxmlElement("w:r")
    if rpr is not None:
        run.append(copy.deepcopy(rpr))
    node = OxmlElement("w:t")
    node.set(XML_SPACE, "preserve")
    node.text = text
    run.append(node)
    paragraph.append(run)
    return run


def replace_paragraph_text(paragraph, text: str) -> None:
    rpr = None
    for run in paragraph.findall(qn("w:r")):
        found = run.find(qn("w:rPr"))
        if found is not None:
            rpr = found
            break
    for run in list(paragraph.findall(qn("w:r"))):
        paragraph.remove(run)
    append_text_run(paragraph, text, rpr)


def replace_text_across_runs(paragraph, needle: str, replacement: str) -> int:
    """Replace ``needle`` with ``replacement`` inside an existing paragraph.

    Handles a placeholder that is split across several Word runs, without
    creating/removing paragraphs or runs. The replacement inherits the
    formatting of the run where the match starts. Returns the number of
    replacements performed.
    """
    if not needle:
        return 0
    nodes = list(paragraph.iter(qn("w:t")))
    if not nodes:
        return 0

    count = 0
    while count < 50:
        texts = [node.text or "" for node in nodes]
        full = "".join(texts)
        start = full.find(needle)
        if start == -1:
            break
        end = start + len(needle)

        offsets, position = [], 0
        for text in texts:
            offsets.append(position)
            position += len(text)

        start_index = max(i for i, offset in enumerate(offsets) if offset <= start)
        end_index = max(i for i, offset in enumerate(offsets) if offset <= end - 1)
        start_offset = start - offsets[start_index]
        end_offset = (end - 1) - offsets[end_index] + 1

        start_text = texts[start_index]
        if start_index == end_index:
            nodes[start_index].text = start_text[:start_offset] + replacement + start_text[end_offset:]
        else:
            nodes[start_index].text = start_text[:start_offset] + replacement
            for middle in range(start_index + 1, end_index):
                nodes[middle].text = ""
            nodes[end_index].text = texts[end_index][end_offset:]
        count += 1
    return count


def set_page_break_before(paragraph) -> None:
    """Force a page break BEFORE this paragraph (idempotent, no blank page).

    Unlike a standalone page-break run, `w:pageBreakBefore` does not create an
    extra blank page when the paragraph already starts at the top of a page.
    """
    p_pr = paragraph.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        paragraph.insert(0, p_pr)
    node = p_pr.find(qn("w:pageBreakBefore"))
    if node is None:
        node = OxmlElement("w:pageBreakBefore")
        # keep schema order: pStyle, keepNext, keepLines, pageBreakBefore, ...
        anchor = None
        for tag in ("w:keepLines", "w:keepNext", "w:pStyle"):
            found = p_pr.find(qn(tag))
            if found is not None:
                anchor = found
                break
        if anchor is not None:
            anchor.addnext(node)
        else:
            p_pr.insert(0, node)
    node.set(qn("w:val"), "1")


def keep_with_next(paragraph) -> None:
    """Keep this paragraph (and its lines) on the same page as the next one.

    The master ships these properties with ``w:val="0"``; we must flip them to
    ``1`` (presence alone is not enough).
    """
    p_pr = paragraph.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        paragraph.insert(0, p_pr)
    for tag in ("w:keepNext", "w:keepLines"):
        node = p_pr.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            style = p_pr.find(qn("w:pStyle"))
            if style is not None:
                style.addnext(node)
            else:
                p_pr.insert(0, node)
        node.set(qn("w:val"), "1")


def set_paragraph_tight_left(paragraph) -> None:
    """Rata kiri + spasi rapat untuk paragraf nilai (mis. topik T03A).

    Menimpa ``w:jc`` menjadi ``left`` dan ``w:spacing`` menjadi single
    tanpa before/after, sehingga teks panjang yang membungkus tidak
    terlihat renggang. Hanya working copy yang diubah; master utuh.
    """
    p_pr = paragraph.find(qn("w:pPr"))
    if p_pr is None:
        p_pr = OxmlElement("w:pPr")
        paragraph.insert(0, p_pr)
    jc = p_pr.find(qn("w:jc"))
    if jc is None:
        jc = OxmlElement("w:jc")
        p_pr.append(jc)
    jc.set(qn("w:val"), "left")
    spacing = p_pr.find(qn("w:spacing"))
    if spacing is None:
        spacing = OxmlElement("w:spacing")
        p_pr.append(spacing)
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "240")
    spacing.set(qn("w:lineRule"), "auto")


def set_row_cant_split(row) -> None:
    """Prevent a table row from being split across pages."""
    tr_pr = row.find(qn("w:trPr"))
    if tr_pr is None:
        tr_pr = OxmlElement("w:trPr")
        row.insert(0, tr_pr)
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.insert(0, OxmlElement("w:cantSplit"))


def set_row_borders(row, *, top: bool | None = None, bottom: bool | None = None) -> None:
    """Enable/disable the top/bottom borders of a row (row-level tblPrEx).

    ``None`` leaves the border untouched. Used to hide the horizontal lines of
    the T03A question area while keeping vertical/outer borders.
    """
    table_ex = row.find(qn("w:tblPrEx"))
    if table_ex is None:
        return
    borders = table_ex.find(qn("w:tblBorders"))
    if borders is None:
        return
    for tag, wanted in (("w:top", top), ("w:bottom", bottom)):
        if wanted is None:
            continue
        node = borders.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            borders.append(node)
        node.set(qn("w:val"), "single" if wanted else "none")
        node.set(qn("w:sz"), "4" if wanted else "0")


def set_row_min_height(row, twips: int) -> None:
    tr_pr = row.find(qn("w:trPr"))
    if tr_pr is None:
        tr_pr = OxmlElement("w:trPr")
        row.insert(0, tr_pr)
    tr_h = tr_pr.find(qn("w:trHeight"))
    if tr_h is None:
        tr_h = OxmlElement("w:trHeight")
        tr_pr.append(tr_h)
    tr_h.set(qn("w:val"), str(twips))
    tr_h.set(qn("w:hRule"), "atLeast")


def make_page_break_paragraph():
    paragraph = OxmlElement("w:p")
    run = OxmlElement("w:r")
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run.append(br)
    paragraph.append(run)
    return paragraph


def _run_properties(size_half_points: int, bold: bool):
    r_pr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        fonts.set(qn(attr), BODY_FONT_ASCII)
    fonts.set(qn("w:eastAsia"), BODY_FONT_EAST_ASIA)
    fonts.set(qn("w:hint"), "eastAsia")
    r_pr.append(fonts)
    if bold:
        r_pr.append(OxmlElement("w:b"))
    for tag in ("w:sz", "w:szCs"):
        size = OxmlElement(tag)
        size.set(qn("w:val"), str(size_half_points))
        r_pr.append(size)
    return r_pr


def make_text_paragraph(
    text: str,
    size_half_points: int = 20,
    bold: bool = False,
    center: bool = False,
    space_after: int = 120,
):
    paragraph = OxmlElement("w:p")
    p_pr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:after"), str(space_after))
    spacing.set(qn("w:line"), "300")
    spacing.set(qn("w:lineRule"), "auto")
    p_pr.append(spacing)
    if center:
        jc = OxmlElement("w:jc")
        jc.set(qn("w:val"), "center")
        p_pr.append(jc)
    paragraph.append(p_pr)

    run = OxmlElement("w:r")
    run.append(_run_properties(size_half_points, bold))
    node = OxmlElement("w:t")
    node.set(XML_SPACE, "preserve")
    node.text = text
    run.append(node)
    paragraph.append(run)
    return paragraph
