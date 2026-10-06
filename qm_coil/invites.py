"""Sistem invite token Form Gulungan.

Port dari: ``src/invites.js`` (224 baris, qm-ywi-telegram-bot).
Status: PORTED (+ test).

Token dibuat acak secara kriptografis, disimpan HANYA sebagai hash
SHA-256 (tidak ada plaintext di database), dan hanya dapat diredeem
satu kali.

Fungsi yang terikat grammy ctx (``sendInvitePrompt`` / ``handleTokenInput``)
tidak di-port di sini; pengkabelan UI-nya menjadi bagian ``wizard.py``.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from qm_coil.db import get_db, now_iso, transaction
from qm_coil.users import (
    USER_STATUS,
    create_user,
    get_user_by_telegram_id,
    update_user,
)

# Alfabet bebas karakter ambigu (tanpa 0, 1, I, L, O, U).
_TOKEN_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
_TOKEN_GROUPS = 3
_GROUP_LENGTH = 4
_WS_PATTERN = re.compile(r"\s+")

TOKEN_STATUS = {
    "AVAILABLE": "AVAILABLE",
    "USED": "USED",
    "EXPIRED": "EXPIRED",
    "REVOKED": "REVOKED",
}


def _conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    return conn if conn is not None else get_db()


def generate_invite_token() -> str:
    """Token undangan acak kriptografis, contoh: QMYWI-7K9P-X4M2-AB3C."""
    total = _TOKEN_GROUPS * _GROUP_LENGTH
    body = "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(total))
    groups = [
        body[i * _GROUP_LENGTH : (i + 1) * _GROUP_LENGTH]
        for i in range(_TOKEN_GROUPS)
    ]
    return f"QMYWI-{'-'.join(groups)}"


def normalize_token(input: object) -> str:
    """Normalisasi input token: trim, buang spasi, uppercase."""
    if not input:
        return ""
    return _WS_PATTERN.sub("", str(input).strip()).upper()


def hash_invite_token(token: object) -> str:
    """Hash SHA-256 hex dari token yang sudah dinormalisasi."""
    return hashlib.sha256(normalize_token(token).encode("utf-8")).hexdigest()


def _expires_at(ttl_days: float | int | None) -> str | None:
    if ttl_days is None or isinstance(ttl_days, bool):
        return None
    try:
        days = float(ttl_days)
    except (TypeError, ValueError):
        return None
    if days <= 0:
        return None
    future = datetime.now(timezone.utc) + timedelta(days=days)
    return future.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def create_invite_tokens(
    count: int,
    created_by: object,
    ttl_days: float | int | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Buat sejumlah token undangan baru. Kembalikan plaintext + expiry."""
    db = _conn(conn)
    created: list[dict] = []
    with transaction(db):
        for _ in range(count):
            # Kemungkinan bentrok sangat kecil, tetapi tetap dijaga.
            while True:
                token = generate_invite_token()
                digest = hash_invite_token(token)
                exists = db.execute(
                    "SELECT 1 FROM invite_tokens WHERE token_hash = ?",
                    (digest,),
                ).fetchone()
                if exists is None:
                    break
            created_at = now_iso()
            expires_at = _expires_at(ttl_days)
            db.execute(
                "INSERT INTO invite_tokens (token_hash, status, created_by,"
                " created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (
                    digest,
                    TOKEN_STATUS["AVAILABLE"],
                    str(created_by),
                    created_at,
                    expires_at,
                ),
            )
            created.append({"token": token, "expiresAt": expires_at})
    return created


def mark_expired_tokens(conn: sqlite3.Connection | None = None) -> None:
    """Tandai token yang lewat masa berlaku sebagai EXPIRED."""
    _conn(conn).execute(
        "UPDATE invite_tokens SET status = ? WHERE status = ?"
        " AND expires_at IS NOT NULL AND expires_at <= ?",
        (TOKEN_STATUS["EXPIRED"], TOKEN_STATUS["AVAILABLE"], now_iso()),
    )


def list_invite_tokens(
    limit: int = 50, conn: sqlite3.Connection | None = None
) -> list[dict]:
    """Daftar token (tanpa plaintext) untuk panel admin."""
    db = _conn(conn)
    mark_expired_tokens(db)
    rows = db.execute(
        "SELECT * FROM invite_tokens ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        {
            "id": row["id"],
            "status": row["status"],
            "createdBy": row["created_by"],
            "createdAt": row["created_at"],
            "expiresAt": row["expires_at"],
            "usedBy": row["used_by"],
            "usedAt": row["used_at"],
        }
        for row in rows
    ]


@dataclass
class RedeemResult:
    valid: bool


def redeem_token_for_user(
    raw_token: object,
    telegram_user_id: object,
    telegram_username: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> RedeemResult:
    """Redeem token secara atomic: token -> USED, user -> REGISTRATION.

    Tidak pernah membocorkan apakah token tertentu pernah ada.
    """
    db = _conn(conn)
    digest = hash_invite_token(raw_token)
    now = now_iso()

    with transaction(db):
        row = db.execute(
            "SELECT * FROM invite_tokens WHERE token_hash = ?", (digest,)
        ).fetchone()
        if row is None or row["status"] != TOKEN_STATUS["AVAILABLE"]:
            return RedeemResult(valid=False)
        if row["expires_at"] and row["expires_at"] <= now:
            db.execute(
                "UPDATE invite_tokens SET status = ? WHERE id = ?",
                (TOKEN_STATUS["EXPIRED"], row["id"]),
            )
            return RedeemResult(valid=False)

        cursor = db.execute(
            "UPDATE invite_tokens SET status = ?, used_by = ?, used_at = ?"
            " WHERE id = ? AND status = ?",
            (
                TOKEN_STATUS["USED"],
                str(telegram_user_id),
                now,
                row["id"],
                TOKEN_STATUS["AVAILABLE"],
            ),
        )
        if cursor.rowcount != 1:
            # Sudah diambil request lain secara bersamaan.
            return RedeemResult(valid=False)

        existing = get_user_by_telegram_id(telegram_user_id, db)
        if existing:
            update_user(
                telegram_user_id,
                {
                    "status": USER_STATUS["REGISTRATION"],
                    "telegram_username": telegram_username,
                    "invited_at": existing["invitedAt"] or now,
                },
                db,
            )
        else:
            create_user(
                telegram_user_id,
                telegram_username=telegram_username,
                status=USER_STATUS["REGISTRATION"],
                invited_at=now,
                conn=db,
            )
        return RedeemResult(valid=True)
