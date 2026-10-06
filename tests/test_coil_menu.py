"""Test qm_coil/menu.py + qm_coil/texts.py."""

from __future__ import annotations

import unittest

from qm_coil.menu import (
    FORM_CANCEL,
    MENU_HELP,
    MENU_NEW_FORM,
    REG_CONFIRM,
    REG_EDIT_NIK,
    callback_of,
    create_cancel_keyboard,
    create_main_menu_keyboard,
    create_registration_keyboard,
    to_reply_buttons,
)
from qm_coil.texts import TEXTS


class MenuTest(unittest.TestCase):
    def test_main_menu(self):
        keyboard = create_main_menu_keyboard()
        # dua baris: Form Baru, lalu Bantuan
        self.assertEqual(keyboard, [[MENU_NEW_FORM], [MENU_HELP]])
        self.assertEqual(
            to_reply_buttons(keyboard), ["🆕 Form Baru", "ℹ️ Bantuan"]
        )

    def test_registration_keyboard(self):
        keyboard = create_registration_keyboard()
        # satu baris, dua tombol
        self.assertEqual(len(keyboard), 1)
        self.assertEqual(len(keyboard[0]), 2)
        self.assertEqual(REG_CONFIRM[1], "reg:confirm")
        self.assertEqual(REG_EDIT_NIK[1], "reg:edit_nik")

    def test_cancel_keyboard(self):
        keyboard = create_cancel_keyboard()
        self.assertEqual(keyboard, [[FORM_CANCEL]])
        self.assertEqual(FORM_CANCEL[1], "form:cancel")

    def test_callback_of(self):
        keyboard = create_main_menu_keyboard()
        self.assertEqual(callback_of("🆕 Form Baru", keyboard), "menu:new_form")
        self.assertEqual(callback_of("ℹ️ Bantuan", keyboard), "menu:help")
        self.assertIsNone(callback_of("Tombol Asing", keyboard))


class TextsTest(unittest.TestCase):
    def test_teks_utama_ada(self):
        for name in [
            "INVITE_PROMPT",
            "TOKEN_INVALID",
            "TOKEN_VALID",
            "REG_PROMPT_NIK",
            "REG_CONTINUE_NIK",
            "NIK_NOT_REGISTERED",
            "NIK_INVALID",
            "NIK_TAKEN",
            "BLOCKED",
            "ADMIN_DENIED",
            "RESTRICTED_REGISTRATION",
        ]:
            with self.subTest(teks=name):
                self.assertTrue(getattr(TEXTS, name), name)

    def test_register_success(self):
        text = TEXTS.register_success("Budi Santoso", "12345678")
        self.assertIn("Budi Santoso", text)
        self.assertIn("12345678", text)
        self.assertIn("Registrasi berhasil", text)

    def test_reg_confirm(self):
        text = TEXTS.reg_confirm("Budi Santoso", "12345678")
        self.assertIn("KONFIRMASI DATA", text)
        self.assertIn("Budi Santoso", text)
        self.assertIn("12345678", text)

    def test_teks_pakai_newline_asli(self):
        # Bukan literal backslash-n seperti kesalahan port sebelumnya.
        self.assertIn("\n", TEXTS.INVITE_PROMPT)
        self.assertNotIn("\\n", TEXTS.INVITE_PROMPT)


if __name__ == "__main__":
    unittest.main()
