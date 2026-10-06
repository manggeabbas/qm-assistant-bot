"""Alur registrasi pengguna Form Gulungan (setelah token undangan valid).

Port dari: ``src/registration.js`` (175 baris, qm-ywi-telegram-bot).
Status: PORTED sebagian — logika tahap (``registration_stage``),
konstanta callback, dan pemrosesan NIK murni di-port (+ test).
Fungsi terikat grammy ctx (``beginRegistration``, ``sendConfirmation``,
dst.) tidak di-port; pengkabelan UI-nya menjadi bagian ``wizard.py``.

User hanya memasukkan NIK (8 digit). NAMA dikenali otomatis dari
direktori karyawan yang diisi admin. NIK yang tidak terdaftar ditolak.
"""

from __future__ import annotations

import sqlite3

from qm_coil.employees import get_employee_by_nik
from qm_coil.users import (
    USER_STATUS,
    get_user_by_telegram_id,
    is_nik_taken_by_other,
    update_user,
)
from qm_coil.validation import validate_nik

REG_CALLBACKS = {
    "CONFIRM": "reg:confirm",
    "EDIT_NIK": "reg:edit_nik",
}


def registration_stage(user: dict | None) -> str | None:
    """Tahap registrasi dari data tersimpan: 'NIK' | 'CONFIRM' | None."""
    if not user or user.get("status") != USER_STATUS["REGISTRATION"]:
        return None
    if not user.get("nik") or not user.get("name"):
        return "NIK"
    return "CONFIRM"


def process_nik_input(
    user: dict,
    text: object,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Proses input NIK pada tahap registrasi (murni, tanpa ctx).

    Kembalikan dict dengan kunci ``ok`` (bool) dan salah satu:
    - ``{"ok": True, "user": <user terbaru>}`` -> lanjut ke konfirmasi
    - ``{"ok": False, "error": <kode> }`` dengan kode:
      ``NIK_INVALID`` | ``NIK_TAKEN`` | ``NIK_NOT_REGISTERED``
    """
    check = validate_nik(text)
    if not check.valid:
        return {"ok": False, "error": "NIK_INVALID"}

    nik = check.value
    if is_nik_taken_by_other(nik, user["telegramUserId"], conn):
        return {"ok": False, "error": "NIK_TAKEN"}

    employee = get_employee_by_nik(nik, conn)
    if employee is None:
        return {"ok": False, "error": "NIK_NOT_REGISTERED"}

    update_user(user["telegramUserId"], {"nik": nik, "name": employee["name"]}, conn)
    return {"ok": True, "user": get_user_by_telegram_id(user["telegramUserId"], conn)}


def reset_nik(
    user: dict, conn: sqlite3.Connection | None = None
) -> dict | None:
    """Kosongkan NIK & nama agar dapat dikenali ulang (callback reg:edit_nik)."""
    update_user(user["telegramUserId"], {"nik": None, "name": None}, conn)
    return get_user_by_telegram_id(user["telegramUserId"], conn)
