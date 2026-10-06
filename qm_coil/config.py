"""Konfigurasi Form Gulungan.

Port dari: ``src/config.js`` (31 baris, qm-ywi-telegram-bot).
Status: PORTED.

Dibaca dari environment variable (dimuat otomatis bila ``.env`` ada —
``python-dotenv`` dipakai bila terinstal, tanpa dependency wajib).
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - opsional
    pass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Telegram User ID owner/admin (dipisahkan koma bila lebih dari satu).
# Wajib diisi agar /admin berfungsi.
OWNER_TELEGRAM_IDS: list[str] = [
    part.strip()
    for part in os.environ.get("OWNER_TELEGRAM_ID", "").split(",")
    if part.strip()
]
# Owner utama (kompatibilitas: owner pertama).
OWNER_TELEGRAM_ID: str = OWNER_TELEGRAM_IDS[0] if OWNER_TELEGRAM_IDS else ""

# Lokasi file database SQLite (":memory:" untuk pengujian).
DB_PATH: str = os.environ.get("DB_PATH") or str(
    Path(__file__).resolve().parent.parent / "storage" / "qm_coil.sqlite"
)

# Masa berlaku default token undangan bila tidak dipilih (hari),
# 0 = tidak expired.
DEFAULT_TOKEN_TTL_DAYS: int = _int_env("DEFAULT_TOKEN_TTL_DAYS", 0)

HEADER_TEXT: str = (
    "Department of Quality Management\nQM-YWI\n\nPeriksa dengan teliti, Pastikan Sempurna!"
)

DEPARTMENT: str = "Department of Quality Management"
DIVISION: str = "QM-YWI"
MOTTO: str = "Periksa dengan teliti, Pastikan Sempurna!"
VERSION: str = "2.1"
