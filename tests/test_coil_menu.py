"""Test qm_coil/menu.py + qm_coil/texts.py (+ registrasi penuh)."""

from __future__ import annotations

import unittest

from qm_coil.db import open_db
from qm_coil.employees import add_or_update_employee
from qm_coil.menu import (
    callback_of,
    main_menu_keyboard,
    main_menu_text,
    to_reply_buttons,
)
from qm_coil.registration import (
    begin_registration,
    handle_registration_callback,
    handle_registration_text,
    resume_registration,
    send_confirmation,
)
from qm_coil.texts import TEXTS
from qm_coil.users import USER_STATUS, create_user, get_user_by_telegram_id


class MenuTest(unittest.TestCase):
    def test_main_menu_text(self):
        text = main_menu_text()
        self.assertIn("QM-YWI Telegram Form Generator", text)
        self.assertIn("Periksa dengan teliti", text)  # HEADER_TEXT
        self.assertIn("/new", text)

    def test_main_menu_keyboard(self):
        keyboard = main_menu_keyboard()
        self.assertEqual(
            keyboard,
            [
                [("🚀 Mulai Buat Form", "action:new_form")],
                [
                    ("ℹ️ Referensi Material", "cmd:material"),
                    ("📖 Bantuan", "cmd:help"),
                ],
            ],
        )
        self.assertEqual(
            to_reply_buttons(keyboard),
            ["🚀 Mulai Buat Form", "ℹ️ Referensi Material", "📖 Bantuan"],
        )

    def test_callback_of(self):
        keyboard = main_menu_keyboard()
        self.assertEqual(callback_of("🚀 Mulai Buat Form", keyboard), "action:new_form")
        self.assertEqual(callback_of("📖 Bantuan", keyboard), "cmd:help")
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
        self.assertIn("\n", TEXTS.INVITE_PROMPT)
        self.assertNotIn("\\n", TEXTS.INVITE_PROMPT)


class RegistrationFlowTest(unittest.TestCase):
    def setUp(self):
        self.conn = open_db(":memory:")
        add_or_update_employee("12345678", "Budi Santoso", conn=self.conn)

    def _reg_user(self, user_id="42"):
        return create_user(
            user_id, status=USER_STATUS["REGISTRATION"], conn=self.conn
        )

    def test_begin_dan_resume(self):
        user = self._reg_user()
        self.assertIn("REGISTRASI PENGGUNA", begin_registration(user, self.conn)[0].text)
        self.assertIn(
            "belum selesai", resume_registration(user, self.conn)[0].text
        )

    def test_alur_nik_sampai_konfirmasi(self):
        user = self._reg_user()
        replies = handle_registration_text(user, "12345678", self.conn)
        self.assertIn("KONFIRMASI DATA", replies[0].text)
        self.assertIn("Budi Santoso", replies[0].text)
        # tombol konfirmasi
        labels = [b[0] for row in replies[0].buttons for b in row]
        self.assertIn("✅ Benar", labels)
        self.assertIn("✏️ Ubah NIK", labels)

    def test_nik_invalid_dan_tidak_terdaftar(self):
        user = self._reg_user()
        self.assertIn(
            "Format NIK tidak valid",
            handle_registration_text(user, "abc", self.conn)[0].text,
        )
        self.assertIn(
            "tidak terdaftar pada data karyawan",
            handle_registration_text(user, "87654321", self.conn)[0].text,
        )

    def test_confirm_mengaktifkan_dan_tampilkan_menu(self):
        user = self._reg_user()
        handle_registration_text(user, "12345678", self.conn)
        user = get_user_by_telegram_id("42", self.conn)
        replies = handle_registration_callback(user, "reg:confirm", self.conn)
        self.assertEqual(len(replies), 2)
        self.assertIn("Registrasi berhasil", replies[0].text)
        self.assertIn("Form Generator", replies[1].text)
        self.assertEqual(
            get_user_by_telegram_id("42", self.conn)["status"],
            USER_STATUS["ACTIVE"],
        )

    def test_edit_nik_mereset(self):
        user = self._reg_user()
        handle_registration_text(user, "12345678", self.conn)
        user = get_user_by_telegram_id("42", self.conn)
        replies = handle_registration_callback(user, "reg:edit_nik", self.conn)
        self.assertIn("REGISTRASI PENGGUNA", replies[0].text)
        fresh = get_user_by_telegram_id("42", self.conn)
        self.assertIsNone(fresh["nik"])

    def test_send_confirmation(self):
        user = self._reg_user("43")
        from qm_coil.users import update_user

        update_user("43", {"nik": "12345678", "name": "Budi Santoso"}, self.conn)
        reply = send_confirmation(get_user_by_telegram_id("43", self.conn))
        self.assertIn("KONFIRMASI DATA", reply.text)


if __name__ == "__main__":
    unittest.main()
