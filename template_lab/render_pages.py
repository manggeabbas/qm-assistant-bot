"""Backward-compatibility shim for Phase 1; use qm_training.document.render."""

from qm_training.document.render import pdf_page_count, pdf_pages_text, render_pdf_to_png

__all__ = ["pdf_page_count", "pdf_pages_text", "render_pdf_to_png"]
