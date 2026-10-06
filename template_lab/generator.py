"""Backward-compatibility shim.

The document engine now lives in :mod:`qm_training.document`. This module is
kept so Phase 1 (Template Laboratory) scripts and tests keep working.
"""

from __future__ import annotations

from qm_training.document.engine import build_document, generate
from qm_training.document.schema import QAPair, TrainingData
from qm_training.document.template import load_map
from qm_training.document.xmlutil import cells, paragraphs, rows

__all__ = [
    "QAPair",
    "TrainingData",
    "generate",
    "build_document",
    "load_map",
    "rows",
    "cells",
    "paragraphs",
]
