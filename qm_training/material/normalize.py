"""Normalization of extracted material."""

from __future__ import annotations

import re

from qm_training.material.base import MaterialBlock, MaterialDocument

_WHITESPACE = re.compile(r"[ \t\u3000]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_text(text: str, max_chars: int | None = None) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(_WHITESPACE.sub(" ", line).strip() for line in text.split("\n"))
    text = _BLANK_LINES.sub("\n\n", text)
    text = text.strip()
    if max_chars and len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return text


def normalize_document(document: MaterialDocument, max_chars_per_block: int = 20000) -> MaterialDocument:
    blocks: list[MaterialBlock] = []
    for block in document.blocks:
        text = normalize_text(block.text, max_chars=max_chars_per_block)
        if not text and block.kind not in ("sheet",):
            continue
        blocks.append(MaterialBlock(kind=block.kind, text=text, level=block.level, meta=block.meta))
    return MaterialDocument(source=document.source, format=document.format, blocks=blocks)
