"""Layanan Bantuan QC: kamus cacat, daftar per tahap, latihan kilat, analisis foto.

Data-driven dari ``qm_bantuan/data/atlas.json`` (bukan hardcode standar).
Dipakai router sebagai ``qc_handler``: ``QCGateway().handle(IncomingMessage)``.
"""

from __future__ import annotations

__all__ = ["QCGateway"]


def __getattr__(name: str):
    if name == "QCGateway":
        from qm_bantuan.gateway import QCGateway

        return QCGateway
    raise AttributeError(name)
