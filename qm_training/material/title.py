"""Extract the ORIGINAL Indonesian main title from a material document.

This is title *extraction*, not theme *generation*: the returned text must
already exist in the document. It never translates, summarizes or paraphrases.
If no confident Indonesian title can be found, the caller asks the user for a
theme manually.
"""

from __future__ import annotations

import re

from qm_training.material.base import MaterialDocument

_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
_SKIP_PREFIXES = ("kode", "编号", "第 ", "页", "hal.", "page ")
MAX_TITLE_LEN = 200
MIN_TITLE_LEN = 3


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "")).strip()


def _is_title_like(line: str) -> bool:
    if not (MIN_TITLE_LEN <= len(line) <= MAX_TITLE_LEN):
        return False
    if not any(ch.isalpha() for ch in line):
        return False
    lowered = line.lower()
    return not any(lowered.startswith(prefix) for prefix in _SKIP_PREFIXES)


def _candidate_lines(document: MaterialDocument) -> list[str]:
    """Ordered title candidates: structural titles first, then early content."""
    primary: list[str] = []
    secondary: list[str] = []
    for block in document.blocks:
        lines = [line for line in (block.text or "").splitlines() if line.strip()]
        if block.kind == "heading":
            primary.extend(lines)
        elif block.kind in ("slide", "page"):
            primary.extend(lines)
        elif block.kind in ("paragraph", "row"):
            secondary.extend(lines)
    # de-duplicate while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for line in primary + secondary:
        cleaned = _clean(line)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def extract_title(document: MaterialDocument) -> tuple[str | None, str]:
    """Return (title, source). Title is verbatim from the document.

    source is ``document_title_indonesian`` when an Indonesian title is found,
    otherwise ``not_found`` (caller should ask the user).
    """
    for line in _candidate_lines(document):
        if not _is_title_like(line):
            continue
        if has_cjk(line):  # skip Mandarin titles
            continue
        return line, "document_title_indonesian"
    return None, "not_found"
