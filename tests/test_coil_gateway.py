"""Test qm_assistant/coil_gateway.py — pengkabelan end-to-end."""

from __future__ import annotations

import unittest

from qm_assistant.coil_gateway import CoilGateway
from qm_coil.db import open_db
from qm_coil.employees import add_or_update_employee
from qm_coil.invites import create_invite_tokens
from qm_coil.texts import TEXTS
from qm_coil.users import USER_STATUS, create_user, get_user_by_telegram_id, update_user
from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage


def _labels(msg: OutgoingMessage) -> list[str]:
    """Label tombol dari inline_buttons sebuah pesan."""
    return [t_ for row in (msg.inline_buttons or []) for t_, _ in row]


def msg(user_id, text, update_id=None, username=None):
    return IncomingMessage(
        user_id=user_id, text=text, update_id=update_id, username=username
    )


class GatewayAccessTest(unittest.TestCase):
    def setUp(self):
        self.conn = open_db(":memory:")
        self.gw = CoilGateway(owner_ids=["1"], conn=self.conn)

    def test_idempotensi_update_ganda(self):
        out1 = self.gw.handle(msg("42", "halo", update_id=100))
        out2 = self.gw.handle(msg("42", "halo", update_id=100))
        self.assertTrue(out1)  # diproses sekali
        self.assertEqual(out2, [])  # duplikat diabaikan

    def test_user_baru_teks_asing_dianggap_token(self):
        # Seperti aslinya: teks non-command dari user NEW diperlakukan
        # sebagai upaya memasukkan token.
        out = self.gw.handle(msg("42", "halo"))
        self.assertEqual(out[0].text, TEXTS.TOKEN_INVALID)

    def test_user_baru_command_tetap_diminta_token(self):
        out = self.gw.handle(msg("42", "/new"))
        self.assertEqual(out[0].text, TEXTS.INVITE_PROMPT)

    def test_redeem_token_valid_lanjut_registrasi(self):
        token = create_invite_tokens(1, created_by="1", conn=self.conn)[0]["token"]
        out = self.gw.handle(msg("42", token, username="budi"))
        self.assertEqual(out[0].text, TEXTS.TOKEN_VALID)
        self.assertIn("REGISTRASI PENGGUNA", out[1].text)
        user = get_user_by_telegram_id("42", self.conn)
        self.assertEqual(user["status"], USER_STATUS["REGISTRATION"])
        self.assertEqual(user["telegramUsername"], "budi")

    def test_redeem_token_acak_ditolak(self):
        out = self.gw.handle(msg("42", "QMYWI-XXXX-XXXX-XXXX"))
        self.assertEqual(out[0].text, TEXTS.TOKEN_INVALID)
        self.assertIsNone(get_user_by_telegram_id("42", self.conn))

    def test_registrasi_nik_sampai_aktif(self):
        add_or_update_employee("12345678", "Budi Santoso", conn=self.conn)
        token = create_invite_tokens(1, created_by="1", conn=self.conn)[0]["token"]
        self.gw.handle(msg("42", token))

        out = self.gw.handle(msg("42", "12345678"))
        self.assertIn("KONFIRMASI DATA", out[0].text)
        self.assertIn("✅ Benar", _labels(out[0]))

        out = self.gw.handle(msg("42", "✅ Benar"))
        self.assertIn("Registrasi berhasil", out[0].text)
        self.assertIn("Form Generator", out[1].text)
        self.assertEqual(
            get_user_by_telegram_id("42", self.conn)["status"],
            USER_STATUS["ACTIVE"],
        )

    def test_registrasi_command_dibatasi(self):
        token = create_invite_tokens(1, created_by="1", conn=self.conn)[0]["token"]
        self.gw.handle(msg("42", token))
        out = self.gw.handle(msg("42", "/new"))
        self.assertEqual(out[0].text, TEXTS.RESTRICTED_REGISTRATION)

    def test_user_diblokir_ditolak(self):
        create_user("42", status=USER_STATUS["BLOCKED"], conn=self.conn)
        out = self.gw.handle(msg("42", "/new"))
        self.assertEqual(out[0].text, TEXTS.BLOCKED)

    def test_masuk_coil_user_baru_diminta_token(self):
        # Regresi: label tombol "📋 Form Gulungan" tidak boleh dianggap
        # upaya token oleh user NEW.
        out = self.gw.handle(msg("42", "/coil"))
        self.assertEqual(out[0].text, TEXTS.INVITE_PROMPT)

    def test_masuk_coil_lanjut_registrasi(self):
        token = create_invite_tokens(1, created_by="1", conn=self.conn)[0]["token"]
        self.gw.handle(msg("42", token))
        out = self.gw.handle(msg("42", "/coil"))
        self.assertIn("NIK", out[0].text)
        # tanpa teguran RESTRICTED
        self.assertNotIn("menyelesaikan registrasi", out[0].text)


class GatewayActiveTest(unittest.TestCase):
    def setUp(self):
        self.conn = open_db(":memory:")
        self.gw = CoilGateway(owner_ids=["1"], conn=self.conn)
        create_user("42", status=USER_STATUS["ACTIVE"], conn=self.conn)

    def test_new_memulai_wizard(self):
        out = self.gw.handle(msg("42", "/new"))
        self.assertIn("Silakan pilih mesin", out[0].text)
        self.assertIn("FT", _labels(out[0]))

    def test_masuk_coil_tampilkan_menu_utama(self):
        out = self.gw.handle(msg("42", "/coil"))
        self.assertIn("Form Generator", out[0].text)
        self.assertIn("🚀 Mulai Buat Form", _labels(out[0]))
        self.assertTrue(out[0].markdown)

    def test_tombol_menu_coil(self):
        self.gw.handle(msg("42", "/coil"))
        out = self.gw.handle(msg("42", "🚀 Mulai Buat Form"))
        self.assertIn("Silakan pilih mesin", out[0].text)
        out = self.gw.handle(msg("42", "ℹ️ Referensi Material"))
        self.assertIn("TABEL REFERENSI MATERIAL", out[0].text)
        out = self.gw.handle(msg("42", "📖 Bantuan"))
        self.assertIn("PANDUAN", out[0].text)

    def test_tap_ft_setelah_mulai_lewat_tombol_menu(self):
        # Regresi: tap "🚀 Mulai Buat Form" lalu "FT" harus lanjut ke
        # input nomor gulungan, bukan "Perintah tidak dikenali".
        self.gw.handle(msg("42", "/coil"))
        out = self.gw.handle(msg("42", "🚀 Mulai Buat Form"))
        self.assertIn("Silakan pilih mesin", out[0].text)
        out = self.gw.handle(msg("42", "FT"))
        self.assertNotIn("tidak dikenali", out[0].text)
        self.assertIn("nomor gulungan asal", out[0].text)

    def test_help_material_about(self):
        out = self.gw.handle(msg("42", "/help"))
        self.assertIn("PANDUAN", out[0].text)
        self.assertTrue(out[0].markdown)
        out = self.gw.handle(msg("42", "/material"))
        self.assertIn("TABEL REFERENSI MATERIAL", out[0].text)
        out = self.gw.handle(msg("42", "/about"))
        self.assertIn("Quality Management", out[0].text)

    def test_admin_ditolak_untuk_non_owner(self):
        out = self.gw.handle(msg("42", "/admin"))
        self.assertEqual(out[0].text, TEXTS.ADMIN_DENIED)

    def test_owner_bisa_buka_panel_admin(self):
        out = self.gw.handle(msg("1", "/admin"))
        self.assertIn("PANEL ADMINISTRATOR", out[0].text)

    def test_owner_buat_token_lewat_gateway(self):
        out = self.gw.handle(msg("1", "/admin"))
        out = self.gw.handle(msg("1", "🎟 Buat Token"))
        self.assertIn("BUAT TOKEN", out[0].text)
        out = self.gw.handle(msg("1", "2"))
        self.assertIn("masa berlaku", out[0].text)
        out = self.gw.handle(msg("1", "Tidak Expired"))
        self.assertIn("Berhasil membuat 2 token", out[0].text)
        self.assertIn("QMYWI-", out[0].text)


if __name__ == "__main__":
    unittest.main()


class GatewayBotUserAdminTest(unittest.TestCase):
    """Menu /admin -> User Bot: tambah & daftar user (UserStore training)."""

    def setUp(self):
        import tempfile
        from qm_training.core.users import UserStore
        self.tmp = tempfile.mkdtemp()
        self.store = UserStore(path=f"{self.tmp}/users.json")
        self.conn = open_db(":memory:")
        self.gw = CoilGateway(owner_ids=["1"], conn=self.conn, user_store=self.store)

    def _admin(self, uid, text, is_cb=False):
        from qm_training.bot.adapters.base import IncomingMessage
        return self.gw.handle(
            IncomingMessage(user_id=uid, text=text, is_callback=is_cb)
        )

    def _data(self, out_msg, label):
        for row in (out_msg.inline_buttons or []):
            for t_, d in row:
                if t_ == label:
                    return d
        raise AssertionError(f"tombol '{label}' tidak ada")

    def test_panel_memuat_menu_user_bot(self):
        out = self._admin("1", "/admin")
        out = self._admin("1", self._data(out[0], "👤 User Bot"), is_cb=True)
        self.assertIn("USER BOT", out[0].text)

    def test_tambah_user_valid(self):
        out = self._admin("1", "/admin")
        out = self._admin("1", self._data(out[0], "👤 User Bot"), is_cb=True)
        out = self._admin("1", self._data(out[0], "➕ Tambah User"), is_cb=True)
        self.assertIn("ID Telegram", out[0].text)
        out = self._admin("1", "777000111")
        self.assertIn("ditambahkan", out[0].text)
        self.assertTrue(self.store.is_active("777000111"))

    def test_tambah_user_id_tidak_valid(self):
        out = self._admin("1", "/admin")
        out = self._admin("1", self._data(out[0], "👤 User Bot"), is_cb=True)
        out = self._admin("1", self._data(out[0], "➕ Tambah User"), is_cb=True)
        out = self._admin("1", "bukan-angka")
        self.assertIn("tidak valid", out[0].text)
        self.assertFalse(self.store.is_active("bukan-angka"))

    def test_daftar_user_menampilkan_yang_ditambah(self):
        self.store.add("777000111")
        self.store.add("777000222")
        out = self._admin("1", "/admin")
        out = self._admin("1", self._data(out[0], "👤 User Bot"), is_cb=True)
        out = self._admin("1", self._data(out[0], "📋 Daftar User"), is_cb=True)
        self.assertIn("777000111", out[0].text)
        self.assertIn("777000222", out[0].text)

    def test_bukan_owner_ditolak(self):
        create_user("9", "Bukan Owner", USER_STATUS["ACTIVE"], conn=self.conn)
        out = self._admin("9", "/admin")
        self.assertIn("tidak memiliki akses", out[0].text.lower())


if __name__ == "__main__":
    unittest.main()
