"""Logging terpusat Form Gulungan.

Port dari: ``src/logger.js`` (36 baris, qm-ywi-telegram-bot).
Status: PORTED.

Memakai ``logging`` stdlib; pesan otomatis disanitasi agar tidak
membocorkan token.
"""

from __future__ import annotations

import logging
import os

_logger = logging.getLogger("qm_coil")


def _sanitize(message: object) -> str:
    text = message if isinstance(message, str) else str(message)
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if bot_token and len(bot_token) > 5:
        text = text.replace(bot_token, "[REDACTED_BOT_TOKEN]")
    webhook_secret = os.environ.get("WEBHOOK_SECRET_TOKEN", "")
    if webhook_secret and len(webhook_secret) > 3:
        text = text.replace(webhook_secret, "[REDACTED_SECRET]")
    return text


class _CoilLogger:
    def info(self, *args: object) -> None:
        _logger.info(" ".join(_sanitize(a) for a in args))

    def warning(self, *args: object) -> None:
        _logger.warning(" ".join(_sanitize(a) for a in args))

    warn = warning

    def error(self, *args: object) -> None:
        _logger.error(" ".join(_sanitize(a) for a in args))

    def debug(self, *args: object) -> None:
        # Seperti aslinya: debug hanya bila env DEBUG diset.
        if os.environ.get("DEBUG"):
            _logger.debug(" ".join(_sanitize(a) for a in args))


logger = _CoilLogger()
