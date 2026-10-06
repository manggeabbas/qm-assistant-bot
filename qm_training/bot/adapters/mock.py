"""Mock Telegram adapter/test harness (not a real integration)."""

from __future__ import annotations

from pathlib import Path

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.bot.processing import DEFAULT_SLOW_THRESHOLD_SECONDS, run_with_sticker_indicator


class MockTelegramAdapter:
    def __init__(
        self,
        workflow,
        slow_threshold: float = DEFAULT_SLOW_THRESHOLD_SECONDS,
        sticker_fails: bool = False,
        sticker_returns_none: bool = False,
        sticker_available: bool = True,
    ) -> None:
        self.workflow = workflow
        self.slow_threshold = slow_threshold
        self.sticker_fails = sticker_fails
        self.sticker_returns_none = sticker_returns_none
        self.sticker_available = sticker_available
        self.sent: list[tuple[str, OutgoingMessage]] = []
        self.stickers_sent: list[tuple[str, int]] = []
        self.stickers_deleted: list[tuple[str, int]] = []
        self.chat_actions: list[tuple[str, str]] = []
        self._next_message_id = 1000

    def send_message(self, chat_id: str, message: OutgoingMessage) -> None:
        self.sent.append((chat_id, message))

    def send_chat_action(self, chat_id: str, action: str = "typing") -> None:
        self.chat_actions.append((chat_id, action))

    def send_sticker(self, chat_id: str) -> int | None:
        if self.sticker_fails:
            raise RuntimeError("mock sticker send failure")
        if self.sticker_returns_none:
            return None
        message_id = self._next_message_id
        self._next_message_id += 1
        self.stickers_sent.append((chat_id, message_id))
        return message_id

    def _send_processing_indicator(self, chat_id: str) -> int | None:
        message_id = self.send_sticker(chat_id) if self.sticker_available else None
        if message_id is None:
            self.send_chat_action(chat_id)  # native fallback (no file sent)
        return message_id

    def delete_message(self, chat_id: str, message_id: int) -> None:
        self.stickers_deleted.append((chat_id, message_id))

    def receive(
        self,
        user_id: str,
        text: str = "",
        document_path: Path | None = None,
        photo_path: Path | None = None,
        update_id: int | None = None,
    ) -> list[OutgoingMessage]:
        incoming = IncomingMessage(
            user_id=str(user_id),
            text=text,
            document_path=document_path,
            photo_path=photo_path,
            update_id=update_id,
        )
        messages = run_with_sticker_indicator(
            lambda: self.workflow.handle(incoming),
            send_sticker=lambda: self._send_processing_indicator(str(user_id)),
            delete_sticker=lambda message_id: self.delete_message(str(user_id), message_id),
            threshold=self.slow_threshold,
        )
        for message in messages:
            self.send_message(str(user_id), message)
        return messages

    def get_updates(self, offset: int | None = None) -> list[IncomingMessage]:  # pragma: no cover
        return []

    def download_file(self, file_id: str, destination: Path) -> Path:  # pragma: no cover
        raise NotImplementedError
