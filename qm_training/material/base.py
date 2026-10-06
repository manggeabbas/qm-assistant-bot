"""Structured material model.

Documents are normalized to an ordered list of blocks that preserve context
(heading, paragraph, table row, sheet, slide).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BLOCK_KINDS = ("heading", "paragraph", "table", "row", "sheet", "slide", "page", "note")


@dataclass
class MaterialBlock:
    kind: str
    text: str = ""
    level: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class MaterialDocument:
    source: str
    format: str
    blocks: list[MaterialBlock]

    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks if block.text)

    def is_empty(self) -> bool:
        return not self.text().strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "format": self.format,
            "blocks": [
                {"kind": b.kind, "text": b.text, "level": b.level, "meta": b.meta} for b in self.blocks
            ],
        }
