"""Generated answer-key page (not present in the master)."""

from __future__ import annotations

import copy

from qm_training.document.xmlutil import (
    make_text_paragraph,
    set_page_break_before,
    strip_dup_ids,
)


def add_answer_key(doc, template: dict, data, insert_after, logo_source) -> None:
    spec = template["answer_key"]

    logo_clone = copy.deepcopy(logo_source)
    strip_dup_ids(logo_clone)
    set_page_break_before(logo_clone)  # start a new page without a blank page
    elements = [logo_clone]

    heading = spec["heading"]
    elements.append(
        make_text_paragraph(
            f'{heading["text_en"]}  {heading["text_cn"]}',
            size_half_points=heading["size_half_points"],
            bold=heading["bold"],
            center=True,
            space_after=240,
        )
    )
    for index, qa in enumerate(data.questions, start=1):
        elements.append(make_text_paragraph(f"{index}. {qa.question}", size_half_points=20, bold=True, space_after=60))
        elements.append(make_text_paragraph(f"JAWABAN 答 ： {qa.answer}", size_half_points=20, space_after=160))

    last = insert_after
    for element in elements:
        last.addnext(element)
        last = element
