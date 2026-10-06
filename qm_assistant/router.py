"""Router /start QM Assistant: 1 bot, 1 token, 2 alur.

Alur pesan:

    /start atau /menu
        -> menu (mode=menu): [📋 Form Gulungan] [📚 Form Pelatihan]
    pilih "📚 Form Pelatihan"
        -> mode=training, pesan sintetis "/new_training" diteruskan ke
           workflow qm_training (tidak ada perubahan di qm_training/)
    pilih "📋 Form Gulungan"
        -> mode=coil, diteruskan ke qm_coil (skeleton: stub "dalam porting")
    /cancel atau /batal (mode apa pun)
        -> kembali ke menu

Otorisasi memakai aturan yang sama dengan workflow training
(owner ids / user store aktif / ALLOWED_TELEGRAM_USER_IDS).
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

_MENU_COMMANDS = ("/start", "/menu")
_CANCEL_COMMANDS = ("/cancel", "/batal")


class AssistantRouter:
    """Menerima IncomingMessage, mengembalikan list[OutgoingMessage].

    ``training_workflow`` adalah instance ``qm_training.bot.workflow.Workflow``
    (dibangun oleh ``qm_training.app.build_workflow``). ``coil_handler``
    adalah ``qm_coil.CoilmWizard`` (saat ini stub).
    """

    def __init__(self, training_workflow, coil_handler, store: AssistantSessionStore | None = None) -> None:
        self.training = training_workflow
        self.coil = coil_handler
        self.store = store or AssistantSessionStore()

    # -- entrypoint (dipakai TelegramBotAdapter sebagai .handle) ------------- #

    def handle(self, message: IncomingMessage) -> list[OutgoingMessage]:
        if not self._authorized(message.user_id):
            return [
                OutgoingMessage(
                    "⛔ Anda belum terdaftar.\n"
                    f"ID Telegram Anda: {message.user_id}\n"
                    "Minta admin menambahkan ID ini untuk mendapat akses."
                )
            ]

        text = (message.text or "").strip()
        lowered = text.lower()

        if lowered in _MENU_COMMANDS:
            self.store.reset(message.user_id)
            return [self._menu_message()]

        if lowered in _CANCEL_COMMANDS:
            self.store.reset(message.user_id)
            return [OutgoingMessage("Dibatalkan.", buttons=[BTN_COIL, BTN_TRAINING])]

        mode = self.store.get_mode(message.user_id)

        # Pindah layanan via tombol: berlaku dari mode apa pun.
        # (Tanpa ini, user yang sedang di mode coil tidak bisa pindah ke
        # Form Pelatihan lewat tombol — terjebak sampai kirim /menu.)
        if text == BTN_TRAINING:
            self.store.set_mode(message.user_id, MODE_TRAINING)
            # Mulai alur training tanpa menyentuh /start-nya workflow.
            return self.training.handle(replace(message, text="/new_training"))
        if text == BTN_COIL:
            self.store.set_mode(message.user_id, MODE_COIL)
            return self.coil.handle(message)

        if mode == MODE_MENU:
            return [self._menu_message()]

        if mode == MODE_TRAINING:
            return self.training.handle(message)

        # mode == MODE_COIL
        return self.coil.handle(message)

    # -- helpers ------------------------------------------------------------ #

    def _menu_message(self) -> OutgoingMessage:
        return OutgoingMessage(
            "🤖 *QM Assistant*\n\n"
            "Pilih layanan yang Anda butuhkan:",
            buttons=[BTN_COIL, BTN_TRAINING],
        )

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
