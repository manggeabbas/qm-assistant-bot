"""Backward-compatibility shim for Phase 1; use qm_training.document.pdf."""

from qm_training.document.pdf import convert_to_pdf, find_soffice

__all__ = ["convert_to_pdf", "find_soffice"]
