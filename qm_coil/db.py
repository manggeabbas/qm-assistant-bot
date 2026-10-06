"""Lapisan persistence SQLite untuk Form Gulungan.

Port dari: ``src/db.js`` (120 baris, qm-ywi-telegram-bot).
Status: PORTED (+ test).

JS aslinya memakai ``node:sqlite``; di Python memakai ``sqlite3`` stdlib.
Koneksi dibuka dengan ``isolation_level=None`` (autocommit) agar
``BEGIN IMMEDIATE`` / ``COMMIT`` / ``ROLLBACK`` eksplisit berperilaku sama
seperti di ``node:sqlite``.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_user_id  TEXT NOT NULL UNIQUE,
  telegram_username TEXT,
  name              TEXT,
  nik               TEXT UNIQUE,
  status            TEXT NOT NULL DEFAULT 'NEW'
                    CHECK (status IN ('NEW', 'REGISTRATION', 'ACTIVE', 'BLOCKED')),
  invited_at        TEXT,
  registered_at     TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_tokens (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash  TEXT NOT NULL UNIQUE,
  status      TEXT NOT NULL DEFAULT 'AVAILABLE'
              CHECK (status IN ('AVAILABLE', 'USED', 'EXPIRED', 'REVOKED')),
  created_by  TEXT,
  created_at  TEXT NOT NULL,
  expires_at  TEXT,
  used_by     TEXT,
  used_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_invite_tokens_status ON invite_tokens(status);

CREATE TABLE IF NOT EXISTS employees (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  nik         TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  created_by  TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(name);
"""


def default_db_path() -> Path:
    """Lokasi default file SQLite (di dalam storage/, tidak di-commit)."""
    return Path(__file__).resolve().parent.parent / "storage" / "qm_coil.sqlite"


def now_iso() -> str:
    """Timestamp ISO-8601 UTC seperti ``new Date().toISOString()`` di JS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _ensure_parent(path: str) -> None:
    if path in (":memory:",) or path.startswith("file:"):
        return
    parent = Path(path).expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def migrate(conn: sqlite3.Connection) -> None:
    """Buat schema bila belum ada."""
    conn.executescript(_SCHEMA)


def open_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Buka koneksi SQLite (plus pragma & migrate). ``:memory:`` untuk test."""
    resolved = str(path or os.environ.get("DB_PATH") or default_db_path())
    _ensure_parent(resolved)
    conn = sqlite3.connect(resolved, check_same_thread=False)
    conn.isolation_level = None  # autocommit; transaksi dikelola eksplisit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
    except sqlite3.Error:
        pass  # mis. database :memory: tidak mendukung WAL
    conn.execute("PRAGMA busy_timeout = 5000;")
    migrate(conn)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transaksi eksplisit (padanan ``withTransaction`` di JS)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass  # agar error asli tetap dilempar
        raise


_default_conn: sqlite3.Connection | None = None


def get_db() -> sqlite3.Connection:
    """Koneksi default (lazy singleton, seperti ``db`` di JS)."""
    global _default_conn
    if _default_conn is None:
        _default_conn = open_db()
    return _default_conn
