"""Repository pengguna Form Gulungan.

Port dari: ``src/users.js`` (161 baris, qm-ywi-telegram-bot).
Status: PORTED (+ test).

Identitas utama akun adalah ``telegram_user_id`` (unique). Nama tidak
pernah dipakai sebagai identifier. NIK bersifat unique.
"""

from __future__ import annotations

import re
import sqlite3

from qm_coil.db import get_db, now_iso

USER_STATUS = {
    "NEW": "NEW",
    "REGISTRATION": "REGISTRATION",
    "ACTIVE": "ACTIVE",
    "BLOCKED": "BLOCKED",
}

_ALLOWED_UPDATE_FIELDS = [
    "telegram_username",
    "name",
    "nik",
    "status",
    "invited_at",
    "registered_at",
]


def _conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    return conn if conn is not None else get_db()


def row_to_user(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "telegramUserId": str(row["telegram_user_id"]),
        "telegramUsername": row["telegram_username"] or None,
        "name": row["name"] or None,
        "nik": row["nik"] or None,
        "status": row["status"],
        "invitedAt": row["invited_at"] or None,
        "registeredAt": row["registered_at"] or None,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_user_by_telegram_id(
    telegram_user_id: object, conn: sqlite3.Connection | None = None
) -> dict | None:
    """Ambil user berdasarkan Telegram User ID."""
    if telegram_user_id is None:
        return None
    row = (
        _conn(conn)
        .execute(
            "SELECT * FROM users WHERE telegram_user_id = ?",
            (str(telegram_user_id),),
        )
        .fetchone()
    )
    return row_to_user(row)


def get_user_by_id(
    user_id: int, conn: sqlite3.Connection | None = None
) -> dict | None:
    """Ambil user berdasarkan primary key internal."""
    row = (
        _conn(conn)
        .execute("SELECT * FROM users WHERE id = ?", (user_id,))
        .fetchone()
    )
    return row_to_user(row)


def create_user(
    telegram_user_id: object,
    telegram_username: str | None = None,
    status: str = USER_STATUS["NEW"],
    invited_at: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    """Buat user baru. Melempar error bila telegram_user_id sudah ada."""
    db = _conn(conn)
    now = now_iso()
    cursor = db.execute(
        "INSERT INTO users (telegram_user_id, telegram_username, status,"
        " invited_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(telegram_user_id), telegram_username, status, invited_at, now, now),
    )
    return get_user_by_id(cursor.lastrowid, db)


def update_user(
    telegram_user_id: object,
    fields: dict,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    """Perbarui field user secara terbatas (hanya field yang diizinkan)."""
    db = _conn(conn)
    sets: list[str] = []
    values: list[object] = []
    for field in _ALLOWED_UPDATE_FIELDS:
        if field in fields:
            sets.append(f"{field} = ?")
            values.append(fields[field])
    if not sets:
        return get_user_by_telegram_id(telegram_user_id, db)
    sets.append("updated_at = ?")
    values.append(now_iso())
    values.append(str(telegram_user_id))
    db.execute(
        f"UPDATE users SET {', '.join(sets)} WHERE telegram_user_id = ?",
        values,
    )
    return get_user_by_telegram_id(telegram_user_id, db)


def get_or_create_user(
    telegram_user_id: object,
    telegram_username: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict | None:
    """Buat user bila belum ada, atau kembalikan user yang sudah ada."""
    db = _conn(conn)
    existing = get_user_by_telegram_id(telegram_user_id, db)
    if existing:
        if telegram_username and telegram_username != existing["telegramUsername"]:
            return update_user(
                telegram_user_id, {"telegram_username": telegram_username}, db
            )
        return existing
    return create_user(
        telegram_user_id,
        telegram_username=telegram_username,
        status=USER_STATUS["NEW"],
        conn=db,
    )


def get_status(
    telegram_user_id: object, conn: sqlite3.Connection | None = None
) -> str:
    """Status user; default NEW bila belum terdaftar."""
    user = get_user_by_telegram_id(telegram_user_id, conn)
    return user["status"] if user else USER_STATUS["NEW"]


def is_nik_taken_by_other(
    nik: str | None,
    telegram_user_id: object,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Cek apakah NIK sudah dipakai akun lain."""
    if not nik:
        return False
    row = (
        _conn(conn)
        .execute("SELECT telegram_user_id FROM users WHERE nik = ?", (nik,))
        .fetchone()
    )
    if row is None:
        return False
    return str(row["telegram_user_id"]) != str(telegram_user_id)


def list_users(conn: sqlite3.Connection | None = None) -> list[dict]:
    """Daftar seluruh user (id terkecil dulu)."""
    rows = (
        _conn(conn).execute("SELECT * FROM users ORDER BY id ASC").fetchall()
    )
    return [row_to_user(row) for row in rows]


def mask_nik(nik: str | None) -> str:
    """Samarkan NIK agar tidak ditampilkan lengkap."""
    if not nik:
        return "-"
    return re.sub(r"[0-9]", "*", str(nik))
