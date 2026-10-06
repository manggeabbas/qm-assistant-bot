"""Keyboard menu Form Gulungan.

Port dari: ``src/menu.js`` (38 baris, qm-ywi-telegram-bot).
Status: PORTED.

Beda dengan aslinya: ``grammy.InlineKeyboard`` tidak dipakai.
Menu dinyatakan sebagai data murni — daftar baris, tiap baris berisi
tuple ``(label, callback_data)``. Adapter Telegram sekarang hanya
mendukung reply keyboard teks biasa, jadi ``to_reply_buttons()``
meratakan label menjadi daftar tombol yang kompatibel dengan
``OutgoingMessage.buttons``. ``callback_data`` tetap dipertahankan
agar wizard/admin bisa me-routing callback persis seperti aslinya.
"""

from __future__ import annotations

MenuButton = tuple[str, str]  # (label, callback_data)
MenuKeyboard = list[list[MenuButton]]  # daftar baris

# -- callback_data (identik dengan src/menu.js + src/registration.js) --
MENU_NEW_FORM: MenuButton = ("🆕 Form Baru", "menu:new_form")
MENU_HELP: MenuButton = ("ℹ️ Bantuan", "menu:help")
REG_CONFIRM: MenuButton = ("✅ Ya, Benar", "reg:confirm")
REG_EDIT_NIK: MenuButton = ("✏️ Ubah NIK", "reg:edit_nik")
FORM_CANCEL: MenuButton = ("❌ Batalkan", "form:cancel")


def create_main_menu_keyboard() -> MenuKeyboard:
    """Menu utama: [🆕 Form Baru] di baris sendiri, [ℹ️ Bantuan] di bawahnya."""
    return [[MENU_NEW_FORM], [MENU_HELP]]


def create_registration_keyboard() -> MenuKeyboard:
    """Konfirmasi registrasi: [✅ Ya, Benar] [✏️ Ubah NIK] dalam satu baris."""
    return [[REG_CONFIRM, REG_EDIT_NIK]]


def create_cancel_keyboard() -> MenuKeyboard:
    """Tombol batalkan isi form."""
    return [[FORM_CANCEL]]


def to_reply_buttons(keyboard: MenuKeyboard) -> list[str]:
    """Ratakan menu menjadi daftar label untuk reply keyboard adapter."""
    return [button[0] for row in keyboard for button in row]


def callback_of(label: str, keyboard: MenuKeyboard) -> str | None:
    """Cari callback_data dari sebuah label tombol (routing callback)."""
    for row in keyboard:
        for text, data in row:
            if text == label:
                return data
    return None
