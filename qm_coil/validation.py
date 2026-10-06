"""Validasi input tiap langkah wizard Form Gulungan.

Port dari: ``src/validation.js`` (166 baris, qm-ywi-telegram-bot).
Status: PORTED (termasuk test, dari test/validation.test.js).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from qm_coil.material import detect_material
from qm_coil.numbering import validate_numbering_params

VALID_GRADES = ["A1", "B", "B1", "R", "S"]
VALID_MACHINES = ["FT", "FJ"]

_NIK_PATTERN = re.compile(r"[0-9]{8}")
_WS_PATTERN = re.compile(r"\s+")


@dataclass
class ValidationResult:
    valid: bool
    value: object = None
    error: str | None = None
    material_code: str | None = None
    material: str | None = None


def _to_number(value: object) -> float | int | None:
    """Padanan Number(input) di JS: int bila memungkinkan, else float, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            pass
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _as_int(value: float | int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def validate_machine(input: object) -> ValidationResult:
    """Validasi pilihan mesin (FT/FJ)."""
    if not input:
        return ValidationResult(valid=False, error="Pilih mesin FT atau FJ.")
    upper = str(input).strip().upper()
    if upper in VALID_MACHINES:
        return ValidationResult(valid=True, value=upper)
    return ValidationResult(valid=False, error="Mesin hanya boleh FT atau FJ.")


def validate_source_coil(input: object) -> ValidationResult:
    """Validasi nomor gulungan asal + deteksi material."""
    if not input or not isinstance(input, str):
        return ValidationResult(valid=False, error="Nomor gulungan asal tidak boleh kosong.")
    clean = input.strip().upper()
    detection = detect_material(clean)
    if not detection.valid:
        return ValidationResult(
            valid=False, error=detection.error, material_code=detection.material_code
        )
    return ValidationResult(
        valid=True,
        value=clean,
        material_code=detection.material_code,
        material=detection.material,
    )


def validate_specification(input: object) -> ValidationResult:
    """Validasi spesifikasi (contoh: 1.24*1524)."""
    if not input or not isinstance(input, str):
        return ValidationResult(
            valid=False, error="Spesifikasi tidak boleh kosong (contoh: 1.24*1524)."
        )
    clean = input.strip()
    if len(clean) < 3:
        return ValidationResult(
            valid=False,
            error="Format spesifikasi terlalu pendek. Contoh format: 1.24*1524",
        )
    return ValidationResult(valid=True, value=clean)


def validate_count(input: object) -> ValidationResult:
    """Validasi jumlah gulungan (bilangan bulat positif)."""
    raw = _to_number(input)
    num = _as_int(raw) if raw is not None else None
    if num is None or num < 1:
        return ValidationResult(
            valid=False,
            error="Jumlah gulungan harus berupa bilangan bulat positif minimal 1.",
        )
    return ValidationResult(valid=True, value=num)


def validate_start_digit(input: object, count: int = 1) -> ValidationResult:
    """Validasi digit awal penomoran (0-9, tidak melewati grup suffix)."""
    raw = _to_number(input)
    num = _as_int(raw) if raw is not None else None
    if num is None or num < 0 or num > 9:
        return ValidationResult(
            valid=False, error="Digit awal penomoran harus bernilai 0 sampai 9."
        )
    check = validate_numbering_params(count, num)
    if not check.valid:
        return ValidationResult(valid=False, error=check.error)
    return ValidationResult(valid=True, value=num)


def validate_grade(input: object) -> ValidationResult:
    """Validasi grade (A1, B, B1, R, S)."""
    if not input:
        return ValidationResult(
            valid=False, error="Grade harus dipilih (A1, B, B1, R, S)."
        )
    clean = str(input).strip().upper()
    if clean in VALID_GRADES:
        return ValidationResult(valid=True, value=clean)
    return ValidationResult(
        valid=False,
        error=f"Grade tidak valid. Pilihan yang diperbolehkan: {', '.join(VALID_GRADES)}",
    )


def validate_main_defect(input: object) -> ValidationResult:
    """Validasi cacat utama (contoh: B22, R20, C13)."""
    if not input or not isinstance(input, str):
        return ValidationResult(
            valid=False,
            error="Cacat utama tidak boleh kosong (contoh: B22, R20, C13).",
        )
    clean = input.strip().upper()
    if len(clean) == 0:
        return ValidationResult(valid=False, error="Cacat utama tidak boleh kosong.")
    return ValidationResult(valid=True, value=clean)


def validate_remark(input: object) -> ValidationResult:
    """Validasi remark; kosong -> '-'."""
    if not input or not isinstance(input, str):
        return ValidationResult(valid=True, value="-")
    clean = input.strip()
    if len(clean) == 0 or clean == "-":
        return ValidationResult(valid=True, value="-")
    return ValidationResult(valid=True, value=clean)


def validate_length(input: object) -> ValidationResult:
    """Validasi panjang gulungan dalam meter (angka positif, dibulatkan)."""
    num = _to_number(input)
    if (
        num is None
        or isinstance(num, bool)
        or not math.isfinite(num)
        or num <= 0
    ):
        return ValidationResult(
            valid=False,
            error="Panjang harus berupa angka positif dalam satuan meter (contoh: 955).",
        )
    # Math.round di JS membulatkan setengah ke atas; round() Python memakai
    # banker's rounding, jadi gunakan floor(n + 0.5) untuk n positif.
    return ValidationResult(valid=True, value=math.floor(num + 0.5))


def validate_name(input: object) -> ValidationResult:
    """Validasi nama lengkap saat registrasi (2-100 karakter)."""
    if not input or not isinstance(input, str):
        return ValidationResult(
            valid=False,
            error="Nama tidak boleh kosong. Silakan masukkan NAMA lengkap Anda.",
        )
    clean = _WS_PATTERN.sub(" ", input.strip())
    if len(clean) < 2:
        return ValidationResult(
            valid=False,
            error="Nama terlalu pendek. Silakan masukkan NAMA lengkap Anda.",
        )
    if len(clean) > 100:
        return ValidationResult(
            valid=False, error="Nama terlalu panjang (maksimal 100 karakter)."
        )
    return ValidationResult(valid=True, value=clean)


def validate_nik(input: object) -> ValidationResult:
    """Validasi NIK: tepat 8 digit angka."""
    if not input or not isinstance(input, str):
        return ValidationResult(valid=False, error="NIK tidak boleh kosong.")
    clean = input.strip()
    if _NIK_PATTERN.fullmatch(clean) is None:
        return ValidationResult(
            valid=False, error="NIK harus terdiri dari 8 digit angka."
        )
    return ValidationResult(valid=True, value=clean)
