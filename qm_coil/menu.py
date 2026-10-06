"""Menu utama QM-YWI (dipakai setelah user ACTIVE / owner).

Port dari: ``src/menu.js`` (38 baris, qm-ywi-telegram-bot).
Status: PORTED.

Beda dengan aslinya: ``grammy`` inline keyboard tidak dipakai.
Keyboard dinyatakan sebagai data murni — daftar baris berisi tuple
``(label, callback_data)``. ``to_reply_buttons()`` meratakannya menjadi
daftar label untuk reply keyboard adapter Telegram.
"""

from __future__ import annotations

from qm_coil.config import HEADER_TEXT, VERSION

MenuButton = tuple[str, str]  # (label, callback_data)
MenuKeyboard = list[list[MenuButton]]  # daftar baris


def main_menu_text() -> str:
    return (
        f"{HEADER_TEXT}\n\n"
        f"Selamat datang di *QM-YWI Telegram Form Generator* (v{VERSION}).\n"
        "Bot ini membantu inspector/operator membuat data gulungan baru "
        "secara bertahap, cepat, konsisten, dan meminimalkan kesalahan.\n\n"
        "Tekan tombol di bawah atau ketik /new untuk mulai membuat form."
    )


def main_menu_keyboard() -> MenuKeyboard:
    return [
        [("🚀 Mulai Buat Form", "action:new_form")],
        [
            ("ℹ️ Referensi Material", "cmd:material"),
            ("📖 Bantuan", "cmd:help"),
        ],
    ]


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
