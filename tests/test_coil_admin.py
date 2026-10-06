"""Test qm_coil/admin.py — panel /admin."""

from __future__ import annotations

import unittest

from qm_coil.admin import (
    ADMIN_CALLBACK,
    AdminPanel,
    format_datetime,
)
from qm_coil.db import open_db
from qm_coil.texts import TEXTS
from qm_coil.users import USER_STATUS, create_user, get_user_by_telegram_id


class AdminPanelTest(unittest.TestCase):
    def setUp(self):
        self.conn = open_db(":memory:")
        self.panel = AdminPanel(owner_ids=["1"], conn=self.conn)
        self.user = create_user("42", telegram_username="budi", conn=self.conn)
        from qm_coil.users import update_user

        update_user(
            "42",
            {
                "name": "Budi",
                "nik": "12345678",
                "status": USER_STATUS["ACTIVE"],
                "registeredAt": "2026-10-07T01:00:00.000Z",
            },
            self.conn,
        )

    def test_bukan_owner_ditolak(self):
        replies = self.panel.handle_admin_command("99")
        self.assertEqual(replies[0].text, TEXTS.ADMIN_DENIED)
        self.assertIsNotNone(self.panel.handle_callback("99", "admin:panel"))
        self.assertEqual(
            self.panel.handle_callback("99", "admin:panel")[0].text,
            TEXTS.ADMIN_DENIED,
        )
        # teks non-admin diteruskan (None)
        self.assertIsNone(self.panel.handle_text("99", "halo"))

    def test_panel_utama(self):
        replies = self.panel.handle_admin_command("1")
        self.assertIn("PANEL ADMINISTRATOR", replies[0].text)
        self.assertTrue(replies[0].markdown)
        callbacks = [b[1] for row in replies[0].buttons for b in row]
        self.assertIn("admin:create_token", callbacks)

    def test_buat_token_alur_penuh(self):
        replies = self.panel.handle_callback("1", ADMIN_CALLBACK["CREATE_TOKEN"])
        self.assertIn("BUAT TOKEN", replies[0].text)

        # jumlah tidak valid
        replies = self.panel.handle_text("1", "abc")
        self.assertIn("tidak valid", replies[0].text)
        replies = self.panel.handle_text("1", "999")
        self.assertIn("tidak valid", replies[0].text)

        # jumlah valid -> pilih masa berlaku
        replies = self.panel.handle_text("1", "2")
        self.assertIn("masa berlaku", replies[0].text)

        # pilih 7 hari
        replies = self.panel.handle_callback("1", "admin:expiry:7")
        self.assertIn("Berhasil membuat 2 token", replies[0].text)
        self.assertIn("7 hari", replies[0].text)
        self.assertIn("QMYWI-", replies[0].text)
        self.assertIn("Simpan token ini", replies[0].text)

    def test_expiry_tanpa_pending(self):
        replies = self.panel.handle_callback("1", "admin:expiry:none")
        self.assertIn("tidak aktif", replies[0].text)

    def test_daftar_token(self):
        self.panel.handle_callback("1", ADMIN_CALLBACK["CREATE_TOKEN"])
        self.panel.handle_text("1", "1")
        self.panel.handle_callback("1", "admin:expiry:none")
        replies = self.panel.handle_callback("1", ADMIN_CALLBACK["LIST_TOKENS"])
        self.assertIn("DAFTAR TOKEN UNDANGAN", replies[0].text)
        self.assertIn("hash", replies[0].text)
        self.assertNotIn("QMYWI-", replies[0].text)  # plaintext tak tampil

    def test_daftar_pengguna_dan_blokir(self):
        replies = self.panel.handle_callback("1", ADMIN_CALLBACK["LIST_USERS"])
        self.assertIn("DAFTAR PENGGUNA", replies[0].text)
        self.assertIn("********", replies[0].text)  # NIK disamarkan
        self.assertNotIn("12345678", replies[0].text)

        # detail user
        replies = self.panel.handle_callback("1", f"admin:user:{self.user['id']}")
        self.assertIn("DETAIL PENGGUNA", replies[0].text)
        self.assertIn("Budi", replies[0].text)

        # blokir
        replies = self.panel.handle_callback("1", f"admin:block:{self.user['id']}")
        self.assertIn("BLOCKED", replies[0].text)
        self.assertEqual(
            get_user_by_telegram_id("42", self.conn)["status"],
            USER_STATUS["BLOCKED"],
        )

        # aktifkan kembali (registeredAt ada -> ACTIVE)
        replies = self.panel.handle_callback(
            "1", f"admin:unblock:{self.user['id']}"
        )
        self.assertIn("ACTIVE", replies[0].text)
        self.assertEqual(
            get_user_by_telegram_id("42", self.conn)["status"],
            USER_STATUS["ACTIVE"],
        )

    def test_unblock_user_belum_registrasi(self):
        u = create_user("77", status=USER_STATUS["REGISTRATION"], conn=self.conn)
        from qm_coil.users import update_user

        update_user("77", {"status": USER_STATUS["BLOCKED"]}, self.conn)
        self.panel.handle_callback("1", f"admin:unblock:{u['id']}")
        self.assertEqual(
            get_user_by_telegram_id("77", self.conn)["status"],
            USER_STATUS["REGISTRATION"],
        )

    def test_kelola_karyawan(self):
        # panel
        replies = self.panel.handle_callback("1", ADMIN_CALLBACK["EMPLOYEES"])
        self.assertIn("DATA KARYAWAN", replies[0].text)

        # tambah
        self.panel.handle_callback("1", ADMIN_CALLBACK["EMPLOYEE_ADD"])
        replies = self.panel.handle_text(
            "1", "12345678,Budi Santoso\n87654321,Ani Wijaya"
        )
        self.assertIn("Ditambahkan: 2", replies[0].text)
        self.assertIn("Total karyawan sekarang: 2", replies[0].text)

        # daftar
        replies = self.panel.handle_callback("1", ADMIN_CALLBACK["EMPLOYEE_LIST"])
        self.assertIn("12345678 — Budi Santoso", replies[0].text)

        # hapus: NIK tidak valid dulu
        self.panel.handle_callback("1", ADMIN_CALLBACK["EMPLOYEE_DELETE"])
        replies = self.panel.handle_text("1", "abc")
        self.assertIn("tidak valid", replies[0].text)
        replies = self.panel.handle_text("1", "12345678")
        self.assertIn("dihapus", replies[0].text)

    def test_callback_bukan_admin_diteruskan(self):
        self.assertIsNone(self.panel.handle_callback("1", "menu:new_form"))

    def test_format_datetime(self):
        self.assertEqual(
            format_datetime("2026-10-07T01:23:45.678Z"), "2026-10-07 01:23 UTC"
        )
        self.assertEqual(format_datetime(None), "-")
        self.assertEqual(format_datetime(""), "-")


if __name__ == "__main__":
    unittest.main()
