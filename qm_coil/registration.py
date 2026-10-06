"""Alur registrasi pengguna Form Gulungan (setelah token undangan valid).

Port dari: ``src/registration.js`` (175 baris, qm-ywi-telegram-bot).
Status: PORTED.

Fungsi-fungsi di sini bebas framework: tidak menerima ``ctx`` grammy,
melainkan mengembalikan ``RegistrationReply`` (teks + tombol) yang
nantinya dikirim oleh lapisan Telegram. Alur lengkap:

- ``begin_registration`` / ``resume_registration`` — mulai/lanjutkan
- ``send_confirmation`` — preview konfirmasi data + tombol
- ``handle_registration_text`` — proses input NIK (memakai TEXTS)
- ``handle_registration_callback`` — reg:confirm / reg:edit_nik
- ``registration_stage`` / ``process_nik_input`` / ``reset_nik`` —
  logika murni yang dipakai fungsi-fungsi di atas

User hanya memasukkan NIK (8 digit). NAMA dikenali otomatis dari
direktori karyawan yang diisi admin. NIK yang tidak terdaftar ditolak.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from qm_coil.db import now_iso
from qm_coil.employees import get_employee_by_nik
from qm_coil.menu import MenuKeyboard, main_menu_keyboard, main_menu_text
from qm_coil.texts import TEXTS
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


@dataclass
class RegistrationReply:
    """Satu pesan balasan alur registrasi."""

    text: str
    buttons: MenuKeyboard = field(default_factory=list)
    markdown: bool = False


def registration_stage(user: dict | None) -> str | None:
    """Tahap registrasi dari data tersimpan: 'NIK' | 'CONFIRM' | None."""
    if not user or user.get("status") != USER_STATUS["REGISTRATION"]:
        return None
    if not user.get("nik") or not user.get("name"):
        return "NIK"
    return "CONFIRM"


def send_confirmation(user: dict) -> RegistrationReply:
    """Preview konfirmasi data registrasi + tombol Benar/Ubah NIK."""
    return RegistrationReply(
        text=TEXTS.reg_confirm(user["name"], user["nik"]),
        buttons=[
            [("✅ Benar", REG_CALLBACKS["CONFIRM"])],
            [("✏️ Ubah NIK", REG_CALLBACKS["EDIT_NIK"])],
        ],
    )


def begin_registration(
    user: dict | None, conn: sqlite3.Connection | None = None
) -> list[RegistrationReply]:
    """Mulai alur registrasi (dipanggil setelah token valid)."""
    if registration_stage(user) == "CONFIRM":
        return [send_confirmation(user)]
    return [RegistrationReply(text=TEXTS.REG_PROMPT_NIK)]


def resume_registration(
    user: dict | None, conn: sqlite3.Connection | None = None
) -> list[RegistrationReply]:
    """Lanjutkan registrasi saat pengguna mengirim /start di tengah proses."""
    if registration_stage(user) == "CONFIRM":
        return [send_confirmation(user)]
    return [RegistrationReply(text=TEXTS.REG_CONTINUE_NIK)]


def handle_registration_text(
    user: dict,
    text: object,
    conn: sqlite3.Connection | None = None,
) -> list[RegistrationReply]:
    """Tangani input teks pada alur registrasi."""
    stage = registration_stage(user)

    if stage == "NIK":
        result = process_nik_input(user, text, conn)
        if not result["ok"]:
            error_texts = {
                "NIK_INVALID": TEXTS.NIK_INVALID,
                "NIK_TAKEN": TEXTS.NIK_TAKEN,
                "NIK_NOT_REGISTERED": TEXTS.NIK_NOT_REGISTERED,
            }
            return [RegistrationReply(text=error_texts[result["error"]])]
        return [send_confirmation(result["user"])]

    if stage == "CONFIRM":
        return [send_confirmation(user)]

    return [RegistrationReply(text=TEXTS.REG_PROMPT_NIK)]


def handle_registration_callback(
    user: dict,
    data: str,
    conn: sqlite3.Connection | None = None,
) -> list[RegistrationReply]:
    """Tangani callback inline pada alur registrasi (reg:confirm/reg:edit_nik)."""
    if data == REG_CALLBACKS["EDIT_NIK"]:
        # Kosongkan NIK & nama agar dapat dikenali ulang dari direktori.
        reset_nik(user, conn)
        return [RegistrationReply(text=TEXTS.REG_PROMPT_NIK)]

    if data == REG_CALLBACKS["CONFIRM"]:
        current = get_user_by_telegram_id(user["telegramUserId"], conn) or user

        if registration_stage(current) != "CONFIRM":
            return [RegistrationReply(text=TEXTS.REG_PROMPT_NIK)]

        if is_nik_taken_by_other(current["nik"], current["telegramUserId"], conn):
            return [RegistrationReply(text=TEXTS.NIK_TAKEN)]

        update_user(
            current["telegramUserId"],
            {"status": USER_STATUS["ACTIVE"], "registeredAt": now_iso()},
            conn,
        )
        # Seperti aslinya: pesan sukses lalu menu utama.
        return [
            RegistrationReply(
                text=TEXTS.register_success(current["name"], current["nik"])
            ),
            RegistrationReply(
                text=main_menu_text(), buttons=main_menu_keyboard(), markdown=True
            ),
        ]

    return []


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
