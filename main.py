"""Entrypoint untuk QM Assistant Telegram bot (1 bot, 1 token).

Dua layanan dalam satu bot:
- 📋 Form Gulungan  (qm_coil, hasil port qm-ywi-telegram-bot)
- 📚 Form Pelatihan (qm_training, dari formpelatihanQM)

Usage:
    python main.py            # run the bot (requires TELEGRAM_BOT_TOKEN)
    python main.py --check    # environment / dependency report
"""

from __future__ import annotations

import sys

from qm_training.app import access_refusal_reason, build_workflow
from qm_training.core.config import Settings
from qm_training.core.singleton import AlreadyRunningError, SingleInstance
from qm_training.paths import OUTPUT_DIR

from qm_assistant import AssistantRouter
from qm_assistant.coil_gateway import CoilGateway

LOCK_PATH = OUTPUT_DIR / "bot.lock"


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    if "--check" in argv:
        from scripts.check_environment import main as check_main

        return check_main()

    settings = Settings.from_env()
    workflow, ai_is_mock = build_workflow(settings)

    if not settings.telegram_bot_token:
        print(
            "TELEGRAM_BOT_TOKEN belum diset.\n"
            "Salin .env.example menjadi .env dan isi token, lalu jalankan lagi.\n"
            "Status: PENDING_EXTERNAL_CREDENTIAL",
            flush=True,
        )
        return 2

    refusal = access_refusal_reason(settings)
    if refusal:
        print(f"⛔ Bot tidak dijalankan.\n{refusal}", flush=True)
        return 4

    from qm_training.bot.adapters.telegram import TelegramBotAdapter

    if ai_is_mock:
        print("PERINGATAN: AI provider berjalan sebagai MOCK (credential belum diisi).", flush=True)

    # Router: /start menjadi menu (Form Gulungan | Form Pelatihan),
    # lalu didelegasikan ke workflow training atau gateway coil
    # (access guard + registrasi + admin + wizard).
    router = AssistantRouter(training_workflow=workflow, coil_handler=CoilGateway())

    # Single instance: two pollers would process every update twice.
    lock = SingleInstance(LOCK_PATH)
    try:
        lock.acquire()
    except AlreadyRunningError:
        print(
            "Instance lain sudah berjalan (polling aktif). Hentikan dulu sebelum menjalankan yang baru.",
            flush=True,
        )
        return 3
    try:
        print("Bot berjalan. Tekan Ctrl+C untuk berhenti.", flush=True)
        TelegramBotAdapter(
            settings.telegram_bot_token,
            router,
            slow_threshold=settings.processing_delay_seconds,
            sticker_file_id=settings.hourglass_sticker_file_id,
            sticker_path=settings.hourglass_sticker_path,
            sticker_min_display=settings.processing_sticker_min_seconds,
            allow_sticker_upload=settings.hourglass_sticker_upload,
        ).run_forever()
    finally:
        lock.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
