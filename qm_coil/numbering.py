"""Parsing dan generator penomoran gulungan HAxx QM-YWI.

Port dari: ``src/numbering.js`` (96 baris, qm-ywi-telegram-bot).
Status: PORTED (termasuk test, dari test/numbering.test.js).

Aturan inti: hanya digit TERAKHIR suffix yang berubah (HA10 -> HA11,
HA12, ...); penomoran ditolak bila digit akhir akan melebihi 9
(mencegah hasil tidak valid seperti HA110).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# [0-9] dipakai (bukan \d) agar hanya digit ASCII, sama seperti /\d/ di JS.
_SUFFIX_PATTERN = re.compile(r"^(.*HA[0-9])([0-9])$")


@dataclass
class ParamsCheck:
    valid: bool
    error: str | None = None


@dataclass
class SuffixParse:
    valid: bool
    base_prefix: str | None = None
    group_prefix: str | None = None
    last_digit: int | None = None
    error: str | None = None


@dataclass
class CoilGeneration:
    valid: bool
    coils: list[str] | None = None
    error: str | None = None


def _is_int(value: object) -> bool:
    # bool adalah subclass int di Python; True/False bukan bilangan yang valid
    # di sini (seperti Number.isInteger di JS yang menolak boolean).
    return isinstance(value, int) and not isinstance(value, bool)


def validate_numbering_params(count: int, start_digit: int) -> ParamsCheck:
    """Validasi parameter jumlah & digit awal penomoran."""
    if not _is_int(count) or count < 1:
        return ParamsCheck(
            valid=False,
            error="Jumlah gulungan harus berupa bilangan bulat positif (minimal 1).",
        )
    if not _is_int(start_digit) or start_digit < 0 or start_digit > 9:
        return ParamsCheck(
            valid=False,
            error="Digit awal penomoran harus bernilai antara 0 sampai 9.",
        )
    max_digit = start_digit + count - 1
    if max_digit > 9:
        return ParamsCheck(
            valid=False,
            error=(
                f"Penomoran ditolak: digit awal ({start_digit}) + jumlah ({count})"
                f" - 1 = {max_digit} (> 9).\nDigit terakhir suffix hanya boleh"
                " bernilai 0–9 agar tidak melebihi grup suffix (mencegah"
                " penomoran tidak valid seperti HA110)."
            ),
        )
    return ParamsCheck(valid=True)


def parse_source_coil_suffix(source_coil: str | None) -> SuffixParse:
    """Ekstrak basis prefix nomor gulungan hingga digit grup suffix HA.

    Contoh: ``QH2608K2531HA10`` ->
    base_prefix ``QH2608K2531HA1``, group_prefix ``HA1``, last_digit ``0``.
    """
    if not isinstance(source_coil, str) or not source_coil:
        return SuffixParse(valid=False, error="Nomor gulungan asal tidak boleh kosong.")

    clean = source_coil.strip().upper()
    match = _SUFFIX_PATTERN.match(clean)
    if match is None:
        return SuffixParse(
            valid=False,
            error=(
                "Nomor gulungan asal harus memiliki suffix format HAxx dengan "
                "2 digit angka (contoh: QH2608K2531HA10)."
            ),
        )
    base_prefix = match.group(1)
    return SuffixParse(
        valid=True,
        base_prefix=base_prefix,
        group_prefix=base_prefix[-3:],
        last_digit=int(match.group(2)),
    )


def generate_coil_numbers(
    source_coil: str | None, count: int, start_digit: int
) -> CoilGeneration:
    """Hasilkan daftar nomor gulungan baru dari nomor asal.

    Contoh: (``QH2608K2531HA10``, 3, 1) ->
    [``QH2608K2531HA11``, ``QH2608K2531HA12``, ``QH2608K2531HA13``].
    """
    parsed = parse_source_coil_suffix(source_coil)
    if not parsed.valid:
        return CoilGeneration(valid=False, error=parsed.error)

    check = validate_numbering_params(count, start_digit)
    if not check.valid:
        return CoilGeneration(valid=False, error=check.error)

    assert parsed.base_prefix is not None
    coils = [f"{parsed.base_prefix}{start_digit + i}" for i in range(count)]
    return CoilGeneration(valid=True, coils=coils)
