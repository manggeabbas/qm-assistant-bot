"""Pengkabelan end-to-end Form Gulungan ke router Telegram.

Menggabungkan seluruh modul ``qm_coil`` yang sudah di-port menjadi satu
``handle(IncomingMessage) -> list[OutgoingMessage]`` yang dipakai router
sebagai ``coil_handler``:

1. **Idempotensi** — update_id Telegram yang duplikat diabaikan
   (port middleware idempotency di ``src/bot.js``).
2. **Access guard** — port ``accessGuard`` dari ``src/access.js``:
   owner selalu lolos; BLOCKED ditolak; NEW hanya boleh redeem token;
   REGISTRATION hanya boleh menyelesaikan registrasi.
3. **Registrasi** — redeem token (``src/invites.js``: ``handleTokenInput``)
   lalu alur NIK + konfirmasi (``src/registration.js``).
4. **Admin** — ``/admin`` + callback ``admin:*`` + pesan pending
   (``src/admin.js``); selalu dicek sebelum wizard seperti middleware aslinya.
5. **Wizard** — perintah ``/new`` ``/cancel`` ``/help`` ``/material``
   ``/example`` ``/about`` + state machine percakapan.

Tombol dikirim sebagai reply keyboard teks biasa; petanya
label -> callback_data disimpan per user dari balasan terakhir
(``CoilWizard`` melakukan hal yang sama secara internal untuk wizard).
"""

from __future__ import annotations

from qm_coil.access import is_owner, resolve_user_status
from qm_coil.admin import AdminPanel
from qm_coil.config import DEPARTMENT, DIVISION, MOTTO, VERSION
from qm_coil.db import get_db
from qm_coil.invites import normalize_token, redeem_token_for_user
from qm_coil.logger import logger
from qm_coil.material import MATERIAL_MAP
from qm_coil.menu import (
    MenuKeyboard,
    main_menu_keyboard,
    main_menu_text,
    to_reply_buttons,
)
from qm_coil.registration import (
    begin_registration,
    handle_registration_callback,
    handle_registration_text,
    resume_registration,
)
from qm_coil.state import CoilSessionStore, IdempotencyCache
from qm_coil.texts import TEXTS
from qm_coil.users import USER_STATUS, get_user_by_telegram_id
from qm_coil.wizard import CoilWizard, WizardReply, handle_callback
from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage


def _label_map(replies: list) -> dict[str, str]:
    """Petakan label tombol -> callback_data dari daftar balasan."""
    mapping: dict[str, str] = {}
    for reply in replies:
        buttons: MenuKeyboard = getattr(reply, "buttons", [])
        for row in buttons:
            for label, data in row:
                mapping[label] = data
    return mapping


def _to_outgoing(replies: list) -> list[OutgoingMessage]:
    return [
        OutgoingMessage(
            text=reply.text,
            buttons=to_reply_buttons(getattr(reply, "buttons", [])),
            markdown=bool(getattr(reply, "markdown", False)),
        )
        for reply in replies
    ]


def _material_table_text() -> str:
    lines = [f"• Kode *{code}* ➔ *{name}*" for code, name in MATERIAL_MAP.items()]
    return (
        "*TABEL REFERENSI MATERIAL QM-YWI*\n\n"
        + "\n".join(lines)
        + "\n\n_Catatan: Kode material terletak setelah kode periode "
        "dan sebelum nomor urut utama._"
    )


_HELP_TEXT = """*PANDUAN PENGGUNAAN QM-YWI FORM GENERATOR*

*Perintah yang tersedia:*
/start - Menampilkan pesan pembuka dan menu awal
/new - Memulai pembuatan form gulungan baru
/help - Menampilkan panduan bantuan ini
/material - Menampilkan tabel referensi kode material (Z/K/G)
/example - Menampilkan contoh alur input dan hasil output
/cancel - Membatalkan sesi pembuatan form aktif
/about - Informasi tentang identitas QM-YWI

*Alur Pengisian:*
1. Pilih Mesin (`FT` atau `FJ`)
2. Masukkan Nomor Gulungan Asal (contoh: `QH2608K2531HA10`)
3. Konfirmasi deteksi material otomatis
4. Masukkan Spesifikasi (contoh: `1.24*1524`)
5. Masukkan Jumlah Gulungan (contoh: `3`)
6. Masukkan Digit Awal Suffix HA (contoh: `1`)
7. Preview penomoran coil hasil
8. Input data per coil: Grade (A1/B/B1/R/S), Cacat Utama, Remark, Panjang, Diameter
9. Preview seluruh data dan konfirmasi
10. Dapatkan format final Mandarin workplace QM-YWI"""

_EXAMPLE_TEXT = """*CONTOH ALUR & OUTPUT FINAL QM-YWI*

*Contoh Input:*
• Mesin: FT
• Gulungan Asal: `QH2608K2531HA10` (Material: S30403)
• Spesifikasi: `1.24*1524`
• Jumlah: 3, Digit Awal: 1
• Coil 1: A1, B22, -, 955米, 610 (Tidak Perlu)
• Coil 2: A1, B22, -, 955米, 610 (Tidak Perlu)
• Coil 3: S, C13, -, 15米, 610 (Tidak Perlu)

*Contoh Output Final Workplace:*
```text
机组：FT
QH2608K2531HA10
要生成新卷号

QH2608K2531HA11
S30403
1.24*1524
等级: A1
主缺陷: B22
备注: -
目前内径: 610
是否需改内径: Tidak Perlu
长度: 955米

QH2608K2531HA12
S30403
1.24*1524
等级: A1
主缺陷: B22
备注: -
目前内径: 610
是否需改内径: Tidak Perlu
长度: 955米

QH2608K2531HA13
S30403
1.24*1524
等级: S
主缺陷: C13
备注: -
目前内径: 610
是否需改内径: Tidak Perlu
长度: 15米
```"""


def _about_text() -> str:
    return (
        f"*{DEPARTMENT}*\n"
        f"*Divisi:* {DIVISION}\n"
        f"*Versi:* {VERSION}\n\n"
        f'_"{MOTTO}"_\n\n'
        "Bot ini dirancang khusus untuk mempermudah dan memastikan "
        "kepatuhan standar pembuatan form gulungan baru QM-YWI."
    )


# Label tombol menu coil -> callback_data (menu utama Form Gulungan).
# "🚀 Mulai Buat Form" SENGAJA tidak ada di sini: ia ditangani oleh
# CoilWizard.handle agar peta label->callback_data terisi. Kalau lewat
# handle_callback langsung (bypass), tap "FT"/"FJ" sesudahnya tidak
# dikenali ("Perintah tidak dikenali dalam langkah ini").
# "📖 Bantuan" ditangani khusus: langsung tampilkan panduan lengkap.
_COIL_MENU_LABELS = {
    "ℹ️ Referensi Material": "cmd:material",
}


class CoilGateway:
    """Satu pintu masuk alur Form Gulungan untuk router."""

    def __init__(
        self,
        owner_ids: list[str] | None = None,
        conn=None,
        sessions: CoilSessionStore | None = None,
    ) -> None:
        if owner_ids is None:
            from qm_coil.config import OWNER_TELEGRAM_IDS

            owner_ids = OWNER_TELEGRAM_IDS
        self.owner_ids = owner_ids
        self.conn = conn  # None -> get_db() lazy di tiap modul
        self.sessions = sessions or CoilSessionStore()
        self.idem = IdempotencyCache()
        self.admin = AdminPanel(owner_ids=self.owner_ids, conn=self.conn)
        self.wizard = CoilWizard(self.sessions)
        self._reg_labels: dict[str, dict[str, str]] = {}
        self._admin_labels: dict[str, dict[str, str]] = {}
        if not self.owner_ids:
            logger.warning(
                "OWNER_TELEGRAM_ID kosong - panel /admin dan tombol Admin "
                "tidak bisa diakses siapa pun."
            )

    # -- entrypoint ------------------------------------------------------
    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        # Idempotensi: abaikan update duplikat.
        if message.update_id is not None:
            if self.idem.has(message.update_id):
                return []
            self.idem.add(message.update_id)

        user_id = str(message.user_id)
        text = (message.text or "").strip()

        # Owner selalu diizinkan (agar tidak terkunci dari /admin).
        if is_owner(user_id, self.owner_ids):
            return self._handle_active(message, text)

        status = resolve_user_status(user_id, self.owner_ids, self.conn)

        if status == USER_STATUS["BLOCKED"]:
            return [OutgoingMessage(TEXTS.BLOCKED)]
        if status == USER_STATUS["NEW"]:
            return self._handle_new(message, text)
        if status == USER_STATUS["REGISTRATION"]:
            return self._handle_registration(message, text)
        return self._handle_active(message, text)

    # -- NEW: hanya boleh redeem token ------------------------------------
    def _handle_new(
        self, message: IncomingMessage, text: str
    ) -> list[OutgoingMessage]:
        user_id = str(message.user_id)
        if text.startswith("/"):
            return [OutgoingMessage(TEXTS.INVITE_PROMPT)]

        normalized = normalize_token(text)
        if not normalized:
            return [OutgoingMessage(TEXTS.TOKEN_INVALID)]

        result = redeem_token_for_user(
            normalized, user_id, message.username, self.conn
        )
        if not result.valid:
            return [OutgoingMessage(TEXTS.TOKEN_INVALID)]

        user = get_user_by_telegram_id(user_id, self.conn)
        out = [OutgoingMessage(TEXTS.TOKEN_VALID)]
        replies = begin_registration(user, self.conn)
        self._reg_labels[user_id] = _label_map(replies)
        return out + _to_outgoing(replies)

    # -- REGISTRATION: hanya boleh menyelesaikan registrasi ----------------
    def _handle_registration(
        self, message: IncomingMessage, text: str
    ) -> list[OutgoingMessage]:
        user_id = str(message.user_id)
        user = get_user_by_telegram_id(user_id, self.conn)

        # Masuk lewat tombol 📋 Form Gulungan: lanjutkan registrasi
        # tanpa teguran.
        if text == "/coil":
            replies = resume_registration(user, self.conn)
            self._reg_labels[user_id] = _label_map(replies)
            return _to_outgoing(replies)

        label_map = self._reg_labels.get(user_id, {})
        if text in label_map:
            replies = handle_registration_callback(
                user, label_map[text], self.conn
            )
            self._reg_labels[user_id] = _label_map(replies)
            return _to_outgoing(replies)

        if text and not text.startswith("/"):
            replies = handle_registration_text(user, text, self.conn)
            self._reg_labels[user_id] = _label_map(replies)
            return _to_outgoing(replies)

        out = [OutgoingMessage(TEXTS.RESTRICTED_REGISTRATION)]
        replies = resume_registration(user, self.conn)
        self._reg_labels[user_id] = _label_map(replies)
        return out + _to_outgoing(replies)

    # -- ACTIVE / owner: admin dulu, lalu wizard ----------------------------
    def _handle_active(
        self, message: IncomingMessage, text: str
    ) -> list[OutgoingMessage]:
        user_id = str(message.user_id)

        # Masuk lewat tombol 📋 Form Gulungan: tampilkan menu coil
        # (Mulai Buat Form / Referensi Material / Bantuan).
        if text == "/coil":
            return _to_outgoing(
                [
                    WizardReply(
                        text=main_menu_text(),
                        buttons=main_menu_keyboard(),
                        markdown=True,
                    )
                ]
            )

        if text == "/admin":
            replies = self.admin.handle_admin_command(user_id)
            self._admin_labels[user_id] = _label_map(replies)
            return _to_outgoing(replies)

        label_map = self._admin_labels.get(user_id, {})
        if text in label_map:
            replies = self.admin.handle_callback(user_id, label_map[text])
            if replies is not None:
                # Tombol "Batal/Kembali" juga membatalkan alur pending.
                if label_map[text] == "admin:panel":
                    self.admin._clear_pending(user_id)
                self._admin_labels[user_id] = _label_map(replies)
                return _to_outgoing(replies)

        pending_replies = self.admin.handle_text(user_id, text)
        if pending_replies is not None:
            self._admin_labels[user_id] = _label_map(pending_replies)
            return _to_outgoing(pending_replies)

        if text in ("/help", "📖 Bantuan"):
            return [OutgoingMessage(_HELP_TEXT, markdown=True)]
        if text == "/material":
            return [OutgoingMessage(_material_table_text(), markdown=True)]
        if text == "/example":
            return [OutgoingMessage(_EXAMPLE_TEXT, markdown=True)]
        if text == "/about":
            return [OutgoingMessage(_about_text(), markdown=True)]

        # Label tombol menu coil (dari menu utama Form Gulungan).
        if text in _COIL_MENU_LABELS:
            replies = handle_callback(
                user_id, _COIL_MENU_LABELS[text], self.sessions
            )
            return _to_outgoing(replies)

        return self.wizard.handle(message)
