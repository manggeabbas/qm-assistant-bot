"""Router /start QM Assistant: 1 bot, 1 token, 2 alur.

Alur pesan:

    /start atau /menu
        -> menu (mode=menu): [📋 Form Gulungan] [📚 Form Pelatihan]
           (menu selalu terbuka; otorisasi dicek per layanan)
    pilih "📚 Form Pelatihan"
        -> mode=training, pesan sintetis "/new_training" diteruskan ke
           workflow qm_training (tidak ada perubahan di qm_training/).
           Otorisasi: owner ids / user store aktif / ALLOWED_TELEGRAM_USER_IDS.
    pilih "📋 Form Gulungan"
        -> mode=coil, diteruskan ke CoilGateway (qm_assistant/coil_gateway.py).
           Otorisasi milik Form Gulungan sendiri (SQLite): owner selalu
           lolos, user NEW redeem token undangan, REGISTRATION
           menyelesaikan NIK, BLOCKED ditolak. Dikelola via /admin.
    /cancel atau /batal (mode apa pun)
        -> kembali ke menu
    tombol "🏠 Menu Utama" (mode/layanan apa pun)
        -> kembali ke menu utama (sama seperti /start); router
           menambahkan tombol ini ke setiap pesan mode layanan agar
           user tidak perlu mengetik /start untuk berpindah fungsi.
"""

from __future__ import annotations

from dataclasses import replace

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_assistant.session import (
    MODE_COIL,
    MODE_MENU,
    MODE_TRAINING,
    AssistantSessionStore,
)

BTN_COIL = "📋 Form Gulungan"
BTN_TRAINING = "📚 Form Pelatihan"
BTN_ADMIN = "🛠 Admin"
BTN_HOME = "🏠 Menu Utama"

_MENU_COMMANDS = ("/start", "/menu")
_CANCEL_COMMANDS = ("/cancel", "/batal")
_ADMIN_COMMANDS = ("/admin",)


class AssistantRouter:
    """Menerima IncomingMessage, mengembalikan list[OutgoingMessage].

    ``training_workflow`` adalah instance ``qm_training.bot.workflow.Workflow``
    (dibangun oleh ``qm_training.app.build_workflow``). ``coil_handler``
    adalah ``qm_assistant.coil_gateway.CoilGateway``.
    """

    def __init__(self, training_workflow, coil_handler, store: AssistantSessionStore | None = None) -> None:
        self.training = training_workflow
        self.coil = coil_handler
        self.store = store or AssistantSessionStore()

    # -- entrypoint (dipakai TelegramBotAdapter sebagai .handle) ------------- #

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        text = (message.text or "").strip()
        lowered = text.lower()

        # Menu & batal selalu terbuka: pintu masuk, otorisasi per layanan.
        # Tombol 🏠 Menu Utama juga kembali ke menu dari mana pun.
        if lowered in _MENU_COMMANDS or text == BTN_HOME:
            self.store.reset(message.user_id)
            return [self._menu_message(message.user_id)]

        if lowered in _CANCEL_COMMANDS:
            self.store.reset(message.user_id)
            return [
                OutgoingMessage(
                    "Dibatalkan.", buttons=self._menu_buttons(message.user_id)
                )
            ]

        # /admin global: bisa diketik dari mode apa pun. Gateway
        # memverifikasi owner (ADMIN_DENIED bila bukan owner).
        if lowered in _ADMIN_COMMANDS:
            self.store.set_mode(message.user_id, MODE_COIL)
            return self._with_home(self.coil.handle(replace(message, text="/admin")))

        # Menu khusus admin: hanya owner yang melihat tombolnya; gateway
        # memverifikasi ulang (ADMIN_DENIED bila bukan owner).
        if text == BTN_ADMIN:
            self.store.set_mode(message.user_id, MODE_COIL)
            return self._with_home(self.coil.handle(replace(message, text="/admin")))

        # Pindah layanan via tombol: berlaku dari mode apa pun.
        # (Tanpa ini, user yang sedang di mode coil tidak bisa pindah ke
        # Form Pelatihan lewat tombol — terjebak sampai kirim /menu.)
        if text == BTN_TRAINING:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            self.store.set_mode(message.user_id, MODE_TRAINING)
            # Mulai alur training tanpa menyentuh /start-nya workflow.
            return self._with_home(
                self.training.handle(replace(message, text="/new_training"))
            )
        if text == BTN_COIL:
            self.store.set_mode(message.user_id, MODE_COIL)
            # Masuk coil sebagai perintah "/coil" (bukan label tombol),
            # agar gateway menyambut sesuai status: NEW -> minta token,
            # REGISTRATION -> lanjutkan registrasi, ACTIVE -> menu coil.
            # (Tanpa ini, label "📋 Form Gulungan" dianggap upaya token
            # oleh user NEW dan dijawab "Token tidak valid".)
            return self._with_home(self.coil.handle(replace(message, text="/coil")))

        mode = self.store.get_mode(message.user_id)

        if mode == MODE_MENU:
            return [self._menu_message(message.user_id)]

        if mode == MODE_TRAINING:
            if not self._authorized(message.user_id):
                return [self._denied_message(message.user_id)]
            return self._with_home(self.training.handle(message))

        # mode == MODE_COIL: otorisasi milik gateway (invite/registrasi/DB).
        return self._with_home(self.coil.handle(message))

    # -- helpers ------------------------------------------------------------ #

    def _menu_buttons(self, user_id: str | None = None) -> list[str]:
        buttons = [BTN_COIL, BTN_TRAINING]
        if user_id is not None and self._is_coil_owner(user_id):
            buttons.append(BTN_ADMIN)
        return buttons

    def _is_coil_owner(self, user_id: str) -> bool:
        """Owner Form Gulungan (pengelola /admin)."""
        owner_ids = getattr(self.coil, "owner_ids", None) or ()
        return str(user_id) in {str(o) for o in owner_ids}

    def _menu_message(self, user_id: str | None = None) -> OutgoingMessage:
        return OutgoingMessage(
            "🤖 QM Assistant\n\n"
            "Pilih layanan yang Anda butuhkan:",
            buttons=self._menu_buttons(user_id),
        )

    def _with_home(
        self, messages: list[OutgoingMessage]
    ) -> list[OutgoingMessage]:
        """Tambahkan tombol 🏠 Menu Utama ke pesan mode layanan.

        Router mencegat tombol ini sebelum dispatch (lihat handle()),
        jadi user bisa kembali ke menu utama dari alur mana pun tanpa
        mengetik /start. Tidak ditambahkan ke pesan menu utama itu
        sendiri.
        """
        out = []
        for message in messages:
            buttons = list(message.buttons or [])
            if BTN_HOME not in buttons:
                buttons.append(BTN_HOME)
            out.append(replace(message, buttons=buttons))
        return out

    def _authorized(self, user_id: str) -> bool:
        """Aturan yang sama dengan Workflow._authorized (via atribut publik)."""
        uid = str(user_id)
        if uid in self.training.owner_ids:
            return True
        if self.training.users.is_active(uid):
            return True
        if not self.training.settings.allowed_user_ids:
            return True  # mode terbuka (tanpa allowlist)
        return uid in self.training.settings.allowed_user_ids

    def _denied_message(self, user_id: str) -> OutgoingMessage:
        return OutgoingMessage(
            "⛔ Anda belum terdaftar.\n"
            f"ID Telegram Anda: {user_id}\n"
            "Minta admin menambahkan ID ini untuk mendapat akses."
        )
