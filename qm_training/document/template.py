"""Template mapping loader and working-copy creation.

The master DOCX is never modified. All work happens on a working copy opened
with python-docx.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from docx import Document

from qm_training.paths import MASTER_TEMPLATE, TEMPLATE_MAP


def load_map(path: Path = TEMPLATE_MAP) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def open_document(master: Path = MASTER_TEMPLATE) -> Document:
    """Open a fresh working copy of the master (read-only source)."""
    return Document(str(master))


@dataclass
class TemplateElements:
    t01a: object
    t02a: object
    t03a: object
    t03a_logo: object
    t02a_templates: list


def resolve_elements(doc: Document, template: dict) -> TemplateElements:
    """Capture references to the elements we need before any insertion.

    Insertions shift body positions, so references are captured once up front.
    """
    children = list(doc.element.body)
    t01a = children[template["t01a"]["body_block"]]
    t02a = children[template["t02a"]["body_block"]]
    t03a = children[template["t03a"]["body_block"]]
    t03a_logo = children[template["answer_key"]["logo"]["source_body_block"]]
    t02a_templates = [children[i] for i in template["t02a"]["header_blocks"]] + [t02a]
    return TemplateElements(t01a, t02a, t03a, t03a_logo, t02a_templates)
