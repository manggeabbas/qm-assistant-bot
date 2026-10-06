"""Test qm_coil/db.py + qm_coil/users.py (SQLite :memory:)."""

from __future__ import annotations

import sqlite3
import unittest

from qm_coil.db import migrate, now_iso, open_db, transaction
from qm_coil.users import (
    USER_STATUS,
    create_user,
    get_or_create_user,
    get_status,
    get_user_by_id,
    get_user_by_telegram_id,
    is_nik_taken_by_other,
    list_users,
    mask_nik,
    update_user,
)


def fresh_db() -> sqlite3.Connection:
    return open_db(":memory:")


class DbTest(unittest.TestCase):
    def test_migrate_membuat_tabel(self):
        conn = fresh_db()
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("users", tables)
        self.assertIn("invite_tokens", tables)
        self.assertIn("employees", tables)

    def test_now_iso_format(self):
        stamp = now_iso()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_transaction_commit(self):
        conn = fresh_db()
        with transaction(conn):
            conn.execute(
                "INSERT INTO users (telegram_user_id, status, created_at,"
                " updated_at) VALUES (?, 'NEW', ?, ?)",
                ("1", now_iso(), now_iso()),
            )
        self.assertIsNotNone(get_user_by_telegram_id("1", conn))

    def test_transaction_rollback(self):
        conn = fresh_db()
        with self.assertRaises(RuntimeError):
            with transaction(conn):
                conn.execute(
                    "INSERT INTO users (telegram_user_id, status, created_at,"
                    " updated_at) VALUES (?, 'NEW', ?, ?)",
                    ("1", now_iso(), now_iso()),
                )
                raise RuntimeError("boom")
        self.assertIsNone(get_user_by_telegram_id("1", conn))


class UsersTest(unittest.TestCase):
    def test_create_dan_get(self):
        conn = fresh_db()
        user = create_user("123", telegram_username="budi", conn=conn)
        self.assertEqual(user["telegramUserId"], "123")
        self.assertEqual(user["telegramUsername"], "budi")
        self.assertEqual(user["status"], "NEW")

        fetched = get_user_by_telegram_id(123, conn)  # int juga bisa
        self.assertEqual(fetched["id"], user["id"])
        self.assertEqual(get_user_by_id(user["id"], conn)["telegramUserId"], "123")
        self.assertIsNone(get_user_by_telegram_id("999", conn))

    def test_create_duplikat_melempar_error(self):
        conn = fresh_db()
        create_user("123", conn=conn)
        with self.assertRaises(sqlite3.IntegrityError):
            create_user("123", conn=conn)

    def test_update_user(self):
        conn = fresh_db()
        create_user("123", conn=conn)
        updated = update_user(
            "123", {"name": "Budi", "nik": "12345678", "unknown_field": "x"}, conn
        )
        self.assertEqual(updated["name"], "Budi")
        self.assertEqual(updated["nik"], "12345678")

    def test_update_user_terima_kunci_camelcase(self):
        # Bentuk baca row_to_user / JS asli: registeredAt, invitedAt.
        conn = fresh_db()
        create_user("123", conn=conn)
        updated = update_user(
            "123",
            {"registeredAt": "2026-10-07T01:00:00.000Z", "telegramUsername": "budi"},
            conn,
        )
        self.assertEqual(updated["registeredAt"], "2026-10-07T01:00:00.000Z")
        self.assertEqual(updated["telegramUsername"], "budi")

    def test_get_or_create(self):
        conn = fresh_db()
        first = get_or_create_user("123", "budi", conn)
        second = get_or_create_user("123", "budi", conn)
        self.assertEqual(first["id"], second["id"])
        # username berubah -> diupdate
        third = get_or_create_user("123", "budi_baru", conn)
        self.assertEqual(third["telegramUsername"], "budi_baru")

    def test_get_status(self):
        conn = fresh_db()
        self.assertEqual(get_status("123", conn), "NEW")
        create_user("123", status=USER_STATUS["ACTIVE"], conn=conn)
        self.assertEqual(get_status("123", conn), "ACTIVE")

    def test_nik_taken_by_other(self):
        conn = fresh_db()
        create_user("111", conn=conn)
        update_user("111", {"nik": "12345678"}, conn)
        self.assertTrue(is_nik_taken_by_other("12345678", "222", conn))
        self.assertFalse(is_nik_taken_by_other("12345678", "111", conn))
        self.assertFalse(is_nik_taken_by_other("87654321", "222", conn))
        self.assertFalse(is_nik_taken_by_other(None, "222", conn))

    def test_list_users(self):
        conn = fresh_db()
        create_user("2", conn=conn)
        create_user("1", conn=conn)
        users = list_users(conn)
        self.assertEqual([u["telegramUserId"] for u in users], ["2", "1"])

    def test_mask_nik(self):
        self.assertEqual(mask_nik("12345678"), "********")
        self.assertEqual(mask_nik(None), "-")
        self.assertEqual(mask_nik(""), "-")


if __name__ == "__main__":
    unittest.main()
