"""Panel administrator / owner QM-YWI.

Port dari: ``src/admin.js`` (537 baris, qm-ywi-telegram-bot).
Status: PORTED.

Hanya owner (``OWNER_TELEGRAM_IDS``) yang boleh mengakses; setiap
callback admin diverifikasi ulang sebagai owner (defense in depth).

Beda dengan aslinya: bebas framework — fungsi menerima ``user_id``
dan mengembalikan ``list[AdminReply]`` (teks + tombol + flag).
``handle_callback`` mengembalikan ``None`` untuk data non-admin agar
diteruskan ke handler berikutnya; ``handle_text`` mengembalikan
``None`` bila tidak ada alur pending.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from qm_coil.access import is_owner
from qm_coil.employees import (
    bulk_import_employees,
    count_employees,
    delete_employee,
    list_employees,
)
from qm_coil.invites import create_invite_tokens, list_invite_tokens
from qm_coil.menu import MenuButton, MenuKeyboard
from qm_coil.texts import TEXTS
from qm_coil.users import (
    USER_STATUS,
    get_user_by_id,
    list_users,
    mask_nik,
    update_user,
)

MAX_TOKENS_PER_BATCH = 50
MAX_USERS_LISTED = 20
MAX_EMPLOYEES_LISTED = 100

ADMIN_CALLBACK = {
    "PANEL": "admin:panel",
    "CREATE_TOKEN": "admin:create_token",
    "LIST_TOKENS": "admin:list_tokens",
    "LIST_USERS": "admin:list_users",
    "EMPLOYEES": "admin:employees",
    "EMPLOYEE_ADD": "admin:employees:add",
    "EMPLOYEE_LIST": "admin:employees:list",
    "EMPLOYEE_DELETE": "admin:employees:delete",
}


@dataclass
class AdminReply:
    """Satu pesan balasan panel admin."""

    text: str
    buttons: MenuKeyboard = field(default_factory=list)
    markdown: bool = False
    edit: bool = False


def _btn(label: str, data: str) -> MenuButton:
    return (label, data)


def format_datetime(value: object) -> str:
    """'2026-10-07T01:23:45.678Z' -> '2026-10-07 01:23 UTC' (seperti aslinya)."""
    if not value:
        return "-"
    try:
        text = str(value)
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return moment.strftime("%Y-%m-%d %H:%M") + " UTC"
    except (ValueError, TypeError):
        return str(value)


def admin_panel_text() -> str:
    return "🛠 *PANEL ADMINISTRATOR QM-YWI*\n\nPilih menu di bawah ini."


def admin_panel_keyboard() -> MenuKeyboard:
    return [
        [_btn("🎟 Buat Token", ADMIN_CALLBACK["CREATE_TOKEN"])],
        [
            _btn("📋 Daftar Token", ADMIN_CALLBACK["LIST_TOKENS"]),
            _btn("👥 Daftar Pengguna", ADMIN_CALLBACK["LIST_USERS"]),
        ],
        [_btn("👔 Data Karyawan", ADMIN_CALLBACK["EMPLOYEES"])],
    ]


def user_detail_text(user: dict) -> str:
    username = f"@{user['telegramUsername']}" if user.get("telegramUsername") else "-"
    return (
        "👤 DETAIL PENGGUNA\n\n"
        f"Nama: {user.get('name') or '-'}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user['telegramUserId']}\n"
        f"NIK: {mask_nik(user.get('nik'))}\n"
        f"Status: {user['status']}\n"
        f"Diundang: {format_datetime(user.get('invitedAt'))}\n"
        f"Terdaftar: {format_datetime(user.get('registeredAt'))}"
    )


def user_detail_keyboard(user: dict) -> MenuKeyboard:
    buttons: MenuKeyboard = []
    if user["status"] == USER_STATUS["BLOCKED"]:
        buttons.append([_btn("✅ Aktifkan Kembali", f"admin:unblock:{user['id']}")])
    else:
        buttons.append([_btn("🚫 Blokir", f"admin:block:{user['id']}")])
    buttons.append([_btn("⬅️ Kembali", ADMIN_CALLBACK["LIST_USERS"])])
    return buttons


class AdminPanel:
    """Panel admin dengan state pending in-memory per owner."""

    def __init__(
        self,
        owner_ids: list[str] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        from qm_coil.config import OWNER_TELEGRAM_IDS

        self.owner_ids = owner_ids if owner_ids is not None else OWNER_TELEGRAM_IDS
        self.conn = conn
        self._pending: dict[str, dict] = {}

    # -- pending helpers -------------------------------------------------
    def _get_pending(self, user_id: object) -> dict | None:
        return self._pending.get(str(user_id))

    def _set_pending(self, user_id: object, value: dict) -> None:
        self._pending[str(user_id)] = value

    def _clear_pending(self, user_id: object) -> None:
        self._pending.pop(str(user_id), None)

    def clear_all_pending(self) -> None:
        self._pending.clear()

    def _owner(self, user_id: object) -> bool:
        return is_owner(user_id, self.owner_ids)

    # -- command ----------------------------------------------------------
    def handle_admin_command(self, user_id: object) -> list[AdminReply]:
        if not self._owner(user_id):
            return [AdminReply(text=TEXTS.ADMIN_DENIED)]
        self._clear_pending(user_id)
        return [
            AdminReply(
                text=admin_panel_text(),
                buttons=admin_panel_keyboard(),
                markdown=True,
            )
        ]

    # -- sub-tampilan ------------------------------------------------------
    def _show_token_list(self) -> AdminReply:
        tokens = list_invite_tokens(limit=MAX_TOKENS_PER_BATCH, conn=self.conn)
        lines = ["🎟 DAFTAR TOKEN UNDANGAN", ""]
        if not tokens:
            lines.append("Belum ada token undangan.")
        else:
            for token in tokens:
                lines.append(f"#{token['id']} {token['status']}")
                lines.append(f"   Dibuat: {format_datetime(token['createdAt'])}")
                exp = (
                    format_datetime(token["expiresAt"])
                    if token.get("expiresAt")
                    else "-"
                )
                lines.append(f"   Exp: {exp}")
                if token.get("usedBy"):
                    lines.append(
                        f"   Digunakan oleh: {token['usedBy']} "
                        f"({format_datetime(token.get('usedAt'))})"
                    )
                lines.append("")
            lines.append(
                "_Token asli tidak ditampilkan karena hanya disimpan sebagai hash._"
            )
        return AdminReply(
            text="\n".join(lines),
            buttons=[[_btn("⬅️ Kembali", ADMIN_CALLBACK["PANEL"])]],
            markdown=True,
            edit=True,
        )

    def _show_user_list(self) -> AdminReply:
        users = list_users(self.conn)[:MAX_USERS_LISTED]
        lines = ["👥 DAFTAR PENGGUNA", ""]
        if not users:
            lines.append("Belum ada pengguna terdaftar.")
        else:
            for index, user in enumerate(users):
                lines.append(f"{index + 1}. {user.get('name') or '(belum ada nama)'}")
                lines.append(f"   NIK: {mask_nik(user.get('nik'))}")
                lines.append(f"   Status: {user['status']}")
                lines.append("")
        buttons: MenuKeyboard = [
            [
                _btn(
                    f"{index + 1}. {user.get('name') or 'Tanpa Nama'} ({user['status']})",
                    f"admin:user:{user['id']}",
                )
            ]
            for index, user in enumerate(users)
        ]
        buttons.append([_btn("⬅️ Kembali", ADMIN_CALLBACK["PANEL"])])
        return AdminReply(text="\n".join(lines), buttons=buttons, edit=True)

    def _show_employee_panel(self) -> AdminReply:
        total = count_employees(self.conn)
        text = (
            "👔 *DATA KARYAWAN*\n\n"
            f"Total karyawan terdaftar: *{total}*\n\n"
            "Data ini dipakai bot untuk mengenali NAMA otomatis saat user baru\n"
            "memasukkan NIK. Pilih menu:"
        )
        buttons: MenuKeyboard = [
            [_btn("➕ Tambah Karyawan", ADMIN_CALLBACK["EMPLOYEE_ADD"])],
            [_btn("📋 Daftar Karyawan", ADMIN_CALLBACK["EMPLOYEE_LIST"])],
            [_btn("🗑 Hapus Karyawan", ADMIN_CALLBACK["EMPLOYEE_DELETE"])],
            [_btn("⬅️ Kembali", ADMIN_CALLBACK["PANEL"])],
        ]
        return AdminReply(text=text, buttons=buttons, markdown=True, edit=True)

    def _show_employee_list(self) -> AdminReply:
        total = count_employees(self.conn)
        employees = list_employees(limit=MAX_EMPLOYEES_LISTED, conn=self.conn)
        lines = [f"👔 DAFTAR KARYAWAN ({total} total)", ""]
        if not employees:
            lines.append("Belum ada data karyawan.")
        else:
            for index, emp in enumerate(employees):
                lines.append(f"{index + 1}. {emp['nik']} — {emp['name']}")
        return AdminReply(
            text="\n".join(lines),
            buttons=[[_btn("⬅️ Kembali", ADMIN_CALLBACK["EMPLOYEES"])]],
            edit=True,
        )

    def _show_user_detail(self, user_id: int) -> AdminReply:
        user = get_user_by_id(user_id, self.conn)
        if not user:
            return AdminReply(text="Pengguna tidak ditemukan.", edit=True)
        return AdminReply(
            text=user_detail_text(user),
            buttons=user_detail_keyboard(user),
            edit=True,
        )

    def _generate_and_show_tokens(
        self, owner_id: object, count: int, ttl_days: int | None
    ) -> list[AdminReply]:
        created = create_invite_tokens(
            count, created_by=str(owner_id), ttl_days=ttl_days, conn=self.conn
        )
        expiry_label = f"{ttl_days} hari" if ttl_days else "Tidak Expired"
        lines = [
            f"✅ Berhasil membuat {len(created)} token undangan",
            f"Masa berlaku: {expiry_label}",
            "",
            *(item["token"] for item in created),
            "",
            "⚠️ Simpan token ini sekarang. "
            "Token tidak dapat ditampilkan lagi setelah pesan ini.",
        ]
        return [
            AdminReply(
                text="\n".join(lines),
                buttons=[[_btn("🛠 Panel Admin", ADMIN_CALLBACK["PANEL"])]],
            )
        ]

    # -- dispatcher callback ----------------------------------------------
    def handle_callback(
        self, user_id: object, data: str
    ) -> list[AdminReply] | None:
        """Tangani callback admin. None -> bukan callback admin (teruskan)."""
        data = data or ""
        if not data.startswith("admin:"):
            return None
        if not self._owner(user_id):
            return [AdminReply(text=TEXTS.ADMIN_DENIED)]

        if data == ADMIN_CALLBACK["PANEL"]:
            return [
                AdminReply(
                    text=admin_panel_text(),
                    buttons=admin_panel_keyboard(),
                    markdown=True,
                    edit=True,
                )
            ]

        if data == ADMIN_CALLBACK["CREATE_TOKEN"]:
            self._set_pending(user_id, {"action": "awaiting_count"})
            return [
                AdminReply(
                    text=(
                        "🎟 *BUAT TOKEN UNDANGAN*\n\n"
                        "Berapa token yang ingin dibuat?\n"
                        "Kirim angka (contoh: `5`). "
                        f"Maksimal {MAX_TOKENS_PER_BATCH} per pembuatan."
                    ),
                    buttons=[[_btn("⬅️ Batal", ADMIN_CALLBACK["PANEL"])]],
                    markdown=True,
                    edit=True,
                )
            ]

        if data == ADMIN_CALLBACK["LIST_TOKENS"]:
            return [self._show_token_list()]

        if data == ADMIN_CALLBACK["LIST_USERS"]:
            return [self._show_user_list()]

        if data == ADMIN_CALLBACK["EMPLOYEES"]:
            return [self._show_employee_panel()]

        if data == ADMIN_CALLBACK["EMPLOYEE_LIST"]:
            return [self._show_employee_list()]

        if data == ADMIN_CALLBACK["EMPLOYEE_ADD"]:
            self._set_pending(user_id, {"action": "awaiting_employees"})
            return [
                AdminReply(
                    text=(
                        "➕ *TAMBAH DATA KARYAWAN*\n\n"
                        "Kirim data dengan format satu karyawan per baris:\n"
                        "`NIK,Nama`\n\n"
                        "Contoh (boleh banyak sekaligus):\n"
                        "`12345678,Budi Santoso`\n"
                        "`87654321,Siti Aminah`\n\n"
                        "NIK harus 8 digit angka. "
                        "NIK yang sudah ada akan diperbarui namanya."
                    ),
                    buttons=[[_btn("⬅️ Batal", ADMIN_CALLBACK["EMPLOYEES"])]],
                    markdown=True,
                    edit=True,
                )
            ]

        if data == ADMIN_CALLBACK["EMPLOYEE_DELETE"]:
            self._set_pending(user_id, {"action": "awaiting_delete_employee"})
            return [
                AdminReply(
                    text="🗑 *HAPUS DATA KARYAWAN*\n\nKirim NIK (8 digit) yang ingin dihapus.",
                    buttons=[[_btn("⬅️ Batal", ADMIN_CALLBACK["EMPLOYEES"])]],
                    markdown=True,
                    edit=True,
                )
            ]

        if data.startswith("admin:user:"):
            try:
                target_id = int(data.split(":")[2])
            except (IndexError, ValueError):
                return [AdminReply(text="Pengguna tidak ditemukan.", edit=True)]
            return [self._show_user_detail(target_id)]

        if data.startswith("admin:block:"):
            try:
                target_id = int(data.split(":")[2])
            except (IndexError, ValueError):
                return [AdminReply(text="Pengguna tidak ditemukan.", edit=True)]
            user = get_user_by_id(target_id, self.conn)
            if user:
                update_user(
                    user["telegramUserId"],
                    {"status": USER_STATUS["BLOCKED"]},
                    self.conn,
                )
            return [self._show_user_detail(target_id)]

        if data.startswith("admin:unblock:"):
            try:
                target_id = int(data.split(":")[2])
            except (IndexError, ValueError):
                return [AdminReply(text="Pengguna tidak ditemukan.", edit=True)]
            user = get_user_by_id(target_id, self.conn)
            if user:
                # Kembalikan ke ACTIVE bila registrasi pernah selesai,
                # jika belum kembalikan ke REGISTRATION.
                next_status = (
                    USER_STATUS["ACTIVE"]
                    if user.get("registeredAt")
                    else USER_STATUS["REGISTRATION"]
                )
                update_user(
                    user["telegramUserId"], {"status": next_status}, self.conn
                )
            return [self._show_user_detail(target_id)]

        if data.startswith("admin:expiry:"):
            choice = data.split(":")[2] if data.count(":") >= 2 else ""
            pending = self._get_pending(user_id)
            if not pending or pending.get("action") != "awaiting_expiry":
                return [
                    AdminReply(
                        text="Sesi pembuatan token tidak aktif. Ulangi dari panel admin.",
                        edit=True,
                    )
                ]
            try:
                ttl_days = None if choice == "none" else int(choice)
            except ValueError:
                ttl_days = None
            self._clear_pending(user_id)
            return self._generate_and_show_tokens(
                user_id, pending["count"], ttl_days
            )

        return []

    # -- pesan teks (alur pending) ------------------------------------------
    def handle_text(
        self, user_id: object, text: str
    ) -> list[AdminReply] | None:
        """Tangani pesan teks saat ada alur pending. None -> teruskan."""
        if not self._owner(user_id):
            return None
        pending = self._get_pending(user_id)
        if not pending:
            return None
        clean = (text or "").strip()
        if not clean or clean.startswith("/"):
            return None

        if pending.get("action") == "awaiting_count":
            try:
                count = int(clean)
            except ValueError:
                count = 0
            if not 1 <= count <= MAX_TOKENS_PER_BATCH:
                return [
                    AdminReply(
                        text=f"Jumlah tidak valid. Kirim angka 1–{MAX_TOKENS_PER_BATCH}."
                    )
                ]
            self._set_pending(
                user_id, {"action": "awaiting_expiry", "count": count}
            )
            return [
                AdminReply(
                    text=f"Jumlah: *{count} token*\n\nPilih masa berlaku token:",
                    buttons=[
                        [
                            _btn("7 Hari", "admin:expiry:7"),
                            _btn("30 Hari", "admin:expiry:30"),
                        ],
                        [_btn("Tidak Expired", "admin:expiry:none")],
                    ],
                    markdown=True,
                )
            ]

        if pending.get("action") == "awaiting_employees":
            result = bulk_import_employees(clean, str(user_id), self.conn)
            self._clear_pending(user_id)
            lines = [
                "✅ Impor data karyawan selesai.",
                f"Ditambahkan: {result['created']}",
                f"Diperbarui: {result['updated']}",
                f"Gagal: {len(result['failed'])}",
            ]
            if result["failed"]:
                lines.append("")
                lines.append("Baris gagal:")
                for failure in result["failed"][:10]:
                    lines.append(f"• {failure['reason']}")
                if len(result["failed"]) > 10:
                    lines.append(f"… dan {len(result['failed']) - 10} baris lainnya")
            if result["created"] + result["updated"] > 0:
                lines.append("")
                lines.append(f"Total karyawan sekarang: {count_employees(self.conn)}")
            return [
                AdminReply(
                    text="\n".join(lines),
                    buttons=[[_btn("👔 Data Karyawan", ADMIN_CALLBACK["EMPLOYEES"])]],
                )
            ]

        if pending.get("action") == "awaiting_delete_employee":
            if not re.fullmatch(r"\d{8}", clean):
                return [
                    AdminReply(text="NIK tidak valid. Kirim NIK 8 digit angka.")
                ]
            self._clear_pending(user_id)
            removed = delete_employee(clean, self.conn)
            return [
                AdminReply(
                    text=(
                        f"✅ Karyawan dengan NIK {clean} dihapus."
                        if removed
                        else f"ℹ️ NIK {clean} tidak ditemukan."
                    ),
                    buttons=[[_btn("👔 Data Karyawan", ADMIN_CALLBACK["EMPLOYEES"])]],
                )
            ]

        return None
