"""Test invites + registration + access (SQLite :memory:)."""

from __future__ import annotations

import re
import unittest

from qm_coil.access import is_owner, resolve_user_status
from qm_coil.db import open_db
from qm_coil.employees import add_or_update_employee
from qm_coil.invites import (
    TOKEN_STATUS,
    create_invite_tokens,
    generate_invite_token,
    hash_invite_token,
    list_invite_tokens,
    mark_expired_tokens,
    normalize_token,
    redeem_token_for_user,
)
from qm_coil.registration import (
    REG_CALLBACKS,
    process_nik_input,
    registration_stage,
    reset_nik,
)
from qm_coil.users import USER_STATUS, get_user_by_telegram_id, update_user


class InvitesTest(unittest.TestCase):
    def test_generate_format(self):
        token = generate_invite_token()
        self.assertRegex(token, r"^QMYWI-[2-9A-HJKMNP-TV-Z]{4}-[2-9A-HJKMNP-TV-Z]{4}-[2-9A-HJKMNP-TV-Z]{4}$")
        # dua token berbeda
        self.assertNotEqual(token, generate_invite_token())

    def test_normalize(self):
        self.assertEqual(normalize_token(" qmywi-ab12 cd34 "), "QMYWI-AB12CD34")
        self.assertEqual(normalize_token(""), "")
        self.assertEqual(normalize_token(None), "")

    def test_hash_konsisten_dan_tidak_menyimpan_plaintext(self):
        conn = open_db(":memory:")
        created = create_invite_tokens(1, created_by="1", conn=conn)
        token = created[0]["token"]
        self.assertEqual(hash_invite_token(token), hash_invite_token(token.lower()))
        row = conn.execute("SELECT * FROM invite_tokens").fetchone()
        self.assertNotIn(token, row["token_hash"])
        self.assertEqual(len(row["token_hash"]), 64)

    def test_create_dan_list(self):
        conn = open_db(":memory:")
        created = create_invite_tokens(2, created_by="1", conn=conn)
        self.assertEqual(len(created), 2)
        listed = list_invite_tokens(conn=conn)
        self.assertEqual(len(listed), 2)
        self.assertTrue(all(t["status"] == TOKEN_STATUS["AVAILABLE"] for t in listed))
        self.assertNotIn("token", listed[0])  # tanpa plaintext

    def test_redeem_valid(self):
        conn = open_db(":memory:")
        token = create_invite_tokens(1, created_by="1", conn=conn)[0]["token"]
        result = redeem_token_for_user(token, "42", "budi", conn=conn)
        self.assertTrue(result.valid)
        user = get_user_by_telegram_id("42", conn)
        self.assertEqual(user["status"], USER_STATUS["REGISTRATION"])
        self.assertIsNotNone(user["invitedAt"])

    def test_redeem_ganda_gagal(self):
        conn = open_db(":memory:")
        token = create_invite_tokens(1, created_by="1", conn=conn)[0]["token"]
        self.assertTrue(redeem_token_for_user(token, "42", conn=conn).valid)
        self.assertFalse(redeem_token_for_user(token, "43", conn=conn).valid)

    def test_redeem_token_asing_gagal_tanpa_bocor(self):
        conn = open_db(":memory:")
        create_invite_tokens(1, created_by="1", conn=conn)
        self.assertFalse(
            redeem_token_for_user("QMYWI-XXXX-XXXX-XXXX", "42", conn=conn).valid
        )
        self.assertIsNone(get_user_by_telegram_id("42", conn))

    def test_redeem_token_expired(self):
        conn = open_db(":memory:")
        token = create_invite_tokens(1, created_by="1", ttl_days=30, conn=conn)[0]["token"]
        digest = hash_invite_token(token)
        conn.execute(
            "UPDATE invite_tokens SET expires_at = ? WHERE token_hash = ?",
            ("2000-01-01T00:00:00.000Z", digest),
        )
        self.assertFalse(redeem_token_for_user(token, "42", conn=conn).valid)
        listed = list_invite_tokens(conn=conn)
        self.assertEqual(listed[0]["status"], TOKEN_STATUS["EXPIRED"])

    def test_mark_expired(self):
        conn = open_db(":memory:")
        create_invite_tokens(1, created_by="1", ttl_days=30, conn=conn)
        conn.execute("UPDATE invite_tokens SET expires_at = '2000-01-01T00:00:00.000Z'")
        mark_expired_tokens(conn)
        self.assertEqual(
            list_invite_tokens(conn=conn)[0]["status"], TOKEN_STATUS["EXPIRED"]
        )


class RegistrationTest(unittest.TestCase):
    def _user_registrasi(self, conn, user_id="42"):
        from qm_coil.users import create_user

        return create_user(
            user_id, status=USER_STATUS["REGISTRATION"], conn=conn
        )

    def test_stage(self):
        conn = open_db(":memory:")
        self.assertIsNone(registration_stage(None))
        user = self._user_registrasi(conn)
        self.assertEqual(registration_stage(user), "NIK")
        update_user("42", {"nik": "12345678", "name": "Budi"}, conn)
        user = get_user_by_telegram_id("42", conn)
        self.assertEqual(registration_stage(user), "CONFIRM")
        update_user("42", {"status": USER_STATUS["ACTIVE"]}, conn)
        user = get_user_by_telegram_id("42", conn)
        self.assertIsNone(registration_stage(user))

    def test_process_nik_valid(self):
        conn = open_db(":memory:")
        add_or_update_employee("12345678", "Budi Santoso", conn=conn)
        user = self._user_registrasi(conn)
        result = process_nik_input(user, "12345678", conn)
        self.assertTrue(result["ok"])
        self.assertEqual(result["user"]["name"], "Budi Santoso")
        self.assertEqual(registration_stage(result["user"]), "CONFIRM")

    def test_process_nik_invalid(self):
        conn = open_db(":memory:")
        user = self._user_registrasi(conn)
        self.assertEqual(
            process_nik_input(user, "123", conn)["error"], "NIK_INVALID"
        )

    def test_process_nik_tidak_terdaftar(self):
        conn = open_db(":memory:")
        user = self._user_registrasi(conn)
        self.assertEqual(
            process_nik_input(user, "12345678", conn)["error"],
            "NIK_NOT_REGISTERED",
        )

    def test_process_nik_diambil_orang_lain(self):
        conn = open_db(":memory:")
        from qm_coil.users import create_user

        add_or_update_employee("12345678", "Budi Santoso", conn=conn)
        other = create_user("99", status=USER_STATUS["ACTIVE"], conn=conn)
        update_user("99", {"nik": "12345678"}, conn)
        user = self._user_registrasi(conn, "42")
        self.assertEqual(
            process_nik_input(user, "12345678", conn)["error"], "NIK_TAKEN"
        )
        self.assertIsNotNone(other)

    def test_reset_nik(self):
        conn = open_db(":memory:")
        user = self._user_registrasi(conn)
        update_user("42", {"nik": "12345678", "name": "Budi"}, conn)
        user = get_user_by_telegram_id("42", conn)
        reset = reset_nik(user, conn)
        self.assertIsNone(reset["nik"])
        self.assertIsNone(reset["name"])
        self.assertEqual(registration_stage(reset), "NIK")

    def test_reg_callbacks(self):
        self.assertEqual(REG_CALLBACKS["CONFIRM"], "reg:confirm")
        self.assertEqual(REG_CALLBACKS["EDIT_NIK"], "reg:edit_nik")


class AccessTest(unittest.TestCase):
    def test_is_owner(self):
        self.assertTrue(is_owner("123", ["123", "456"]))
        self.assertTrue(is_owner(123, ["123"]))
        self.assertFalse(is_owner("999", ["123"]))
        self.assertFalse(is_owner(None, ["123"]))

    def test_resolve_status(self):
        conn = open_db(":memory:")
        # belum terdaftar -> NEW
        self.assertEqual(resolve_user_status("42", ["1"], conn), "NEW")
        # owner selalu ACTIVE
        self.assertEqual(resolve_user_status("1", ["1"], conn), "ACTIVE")


if __name__ == "__main__":
    unittest.main()
