"""Deteksi dan mapping jenis material gulungan QM-YWI.

Port dari: ``src/material.js`` (104 baris, qm-ywi-telegram-bot).
Status: PORTED (termasuk test, dari test/material.test.js).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MATERIAL_MAP = {
    "Z": "S30400",
    "K": "S30403",
    "G": "S31603",
}

UNKNOWN_MATERIAL_MESSAGE = (
    "Kode jenis/material tidak dikenali.\n\n"
    "Z = S30400\n"
    "K = S30403\n"
    "G = S31603\n\n"
    "Silakan periksa kembali nomor gulungan."
)


@dataclass
class MaterialDetection:
    valid: bool
    material_code: str | None = None
    material: str | None = None
    error: str | None = None


def get_material_name(code: str | None) -> str | None:
    """Nama material dari kode huruf (Z/K/G); None bila tidak dikenal."""
    if not code:
        return None
    return MATERIAL_MAP.get(code.strip().upper())


# Pola: [Prefix huruf][Periode digit][Kode Material][Nomor urut][HA][2 digit]
# Contoh: QH + 2608 + K + 2531 + HA + 10
# [0-9] dipakai (bukan \d) agar hanya digit ASCII, sama seperti /\\d/ di JS.
_COIL_PATTERN = re.compile(r"^([A-Z]+[0-9]+)([A-Z])([0-9]+)(HA[0-9]{2})$")
_FALLBACK_PATTERN = re.compile(r"^(.+?)([A-Z])([0-9]+)(HA[0-9]{2})$")


def detect_material(coil_number: str | None) -> MaterialDetection:
    """Deteksi kode & nama material dari nomor gulungan.

    Contoh: ``QH2608K1234HA10`` -> valid, kode ``K``, material ``S30403``.
    Tidak pernah menebak: kode tak dikenal -> valid=False + pesan bantuan.
    """
    if not isinstance(coil_number, str) or not coil_number:
        return MaterialDetection(valid=False, error="Nomor gulungan tidak boleh kosong.")

    clean = coil_number.strip().upper()

    match = _COIL_PATTERN.match(clean)
    if match is None:
        # Cek apakah suffix HAxx ada.
        if "HA" not in clean:
            return MaterialDetection(
                valid=False,
                error="Nomor gulungan harus memiliki suffix HA (contoh: QH2608K2531HA10).",
            )
        # Pola umum bila prefix berbeda.
        fallback = _FALLBACK_PATTERN.match(clean)
        if fallback is None:
            return MaterialDetection(
                valid=False,
                error="Format nomor gulungan tidak valid. Contoh format: QH2608K2531HA10",
            )
        material_code = fallback.group(2)
        material = get_material_name(material_code)
        if material is None:
            return MaterialDetection(
                valid=False,
                material_code=material_code,
                error=UNKNOWN_MATERIAL_MESSAGE,
            )
        return MaterialDetection(valid=True, material_code=material_code, material=material)

    material_code = match.group(2)
    material = get_material_name(material_code)
    if material is None:
        return MaterialDetection(
            valid=False,
            material_code=material_code,
            error=UNKNOWN_MATERIAL_MESSAGE,
        )
    return MaterialDetection(valid=True, material_code=material_code, material=material)
