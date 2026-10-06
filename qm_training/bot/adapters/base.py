"""Adapter-independent message model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class IncomingMessage:
    user_id: str
    text: str = ""
    document_path: Path | None = None
    photo_path: Path | None = None
    # Telegram update id, used for idempotency (dedup of redelivered updates).
    update_id: int | None = None
    # Username Telegram pengirim (opsional; dipakai saat redeem token).
    username: str | None = None


@dataclass
class OutgoingMessage:
    text: str
    buttons: list[str] = field(default_factory=list)
    documents: list[Path] = field(default_factory=list)
    # True -> kirim dengan parse_mode Markdown (dipakai Form Gulungan).
    markdown: bool = False


class TelegramAdapter(Protocol):
    def send_message(self, chat_id: str, message: OutgoingMessage) -> None: ...

    def get_updates(self, offset: int | None = None) -> list[IncomingMessage]: ...

    def download_file(self, file_id: str, destination: Path) -> Path: ...
