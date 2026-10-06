"""Direktori karyawan Form Gulungan.

Port dari: ``src/employees.js`` (168 baris, qm-ywi-telegram-bot).
Status: PORTED (+ test).

Diisi oleh owner/admin: pemetaan NIK (8 digit) ke NAMA. Saat registrasi,
user hanya memasukkan NIK dan NAMA dikenali otomatis dari direktori ini.
"""

from __future__ import annotations

import re
import sqlite3

from qm_coil.db import get_db, now_iso, transaction
from qm_coil.validation import validate_name, validate_nik

MAX_LIST = 100

# Format baris: "12345678,Nama" / "12345678;Nama" / "12345678<TAB>Nama"
# atau "12345678 Nama Panjang". [0-9] = digit ASCII seperti /\d/ di JS.
_SEPARATOR_PATTERN = re.compile(r"^([0-9]{8})\s*[,;\t]\s*(.+)$")
_SPACE_PATTERN = re.compile(r"^([0-9]{8})\s+(.+)$")


def _conn(conn: sqlite3.Connection | None) -> sqlite3.Connection:
    return conn if conn is not None else get_db()


def row_to_employee(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "nik": row["nik"],
        "name": row["name"],
        "createdBy": row["created_by"] or None,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_employee_by_nik(
    nik: object, conn: sqlite3.Connection | None = None
) -> dict | None:
    """Ambil karyawan berdasarkan NIK."""
    if not nik:
        return None
    row = (
        _conn(conn)
        .execute("SELECT * FROM employees WHERE nik = ?", (str(nik).strip(),))
        .fetchone()
    )
    return row_to_employee(row)


def add_or_update_employee(
    nik: str,
    name: str,
    created_by: object = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Tambah atau perbarui data karyawan berdasarkan NIK."""
    db = _conn(conn)
    now = now_iso()
    existing = get_employee_by_nik(nik, db)
    if existing:
        db.execute(
            "UPDATE employees SET name = ?, created_by = ?, updated_at = ?"
            " WHERE nik = ?",
            (
                name,
                existing["createdBy"] if created_by is None else str(created_by),
                now,
                nik,
            ),
        )
        return {"created": False, "updated": True}
    db.execute(
        "INSERT INTO employees (nik, name, created_by, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (nik, name, None if created_by is None else str(created_by), now, now),
    )
    return {"created": True, "updated": False}


def parse_employee_line(line: object) -> dict:
    """Urai satu baris menjadi {"nik", "name"} atau {"error"}."""
    raw = str(line).strip()
    if not raw:
        return {"error": "Baris kosong."}

    nik: str | None = None
    name: str | None = None

    match = _SEPARATOR_PATTERN.match(raw) or _SPACE_PATTERN.match(raw)
    if match:
        nik, name = match.group(1), match.group(2)

    if not nik:
        return {"error": f'Format tidak valid (butuh "NIK,Nama"): "{raw}"'}

    nik_check = validate_nik(nik)
    if not nik_check.valid:
        return {"error": f'NIK tidak valid (harus 8 digit): "{nik}"'}

    name_check = validate_name(name)
    if not name_check.valid:
        return {"error": f'Nama tidak valid: "{raw}"'}

    return {"nik": nik_check.value, "name": name_check.value}


def bulk_import_employees(
    text: object,
    created_by: object,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Impor massal karyawan dari teks (satu karyawan per baris)."""
    db = _conn(conn)
    lines = [
        line.strip()
        for line in re.split(r"\r?\n", str(text or ""))
        if line.strip()
    ]
    result: dict = {"created": 0, "updated": 0, "failed": []}
    with transaction(db):
        for line in lines:
            parsed = parse_employee_line(line)
            if "error" in parsed:
                result["failed"].append({"line": line, "reason": parsed["error"]})
                continue
            outcome = add_or_update_employee(
                parsed["nik"], parsed["name"], created_by, db
            )
            if outcome["created"]:
                result["created"] += 1
            if outcome["updated"]:
                result["updated"] += 1
    return result


def list_employees(
    limit: int = MAX_LIST, conn: sqlite3.Connection | None = None
) -> list[dict]:
    """Daftar karyawan (urut nama)."""
    rows = (
        _conn(conn)
        .execute("SELECT * FROM employees ORDER BY name ASC LIMIT ?", (limit,))
        .fetchall()
    )
    return [row_to_employee(row) for row in rows]


def count_employees(conn: sqlite3.Connection | None = None) -> int:
    """Total karyawan."""
    row = _conn(conn).execute("SELECT COUNT(*) AS total FROM employees").fetchone()
    return int(row["total"] or 0)


def delete_employee(nik: object, conn: sqlite3.Connection | None = None) -> bool:
    """Hapus karyawan berdasarkan NIK. True bila ada yang terhapus."""
    cursor = _conn(conn).execute(
        "DELETE FROM employees WHERE nik = ?", (str(nik).strip(),)
    )
    return cursor.rowcount > 0
