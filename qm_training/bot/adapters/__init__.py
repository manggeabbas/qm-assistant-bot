"""Telegram adapters (transport layer)."""

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.bot.adapters.mock import MockTelegramAdapter

__all__ = ["IncomingMessage", "OutgoingMessage", "MockTelegramAdapter"]
