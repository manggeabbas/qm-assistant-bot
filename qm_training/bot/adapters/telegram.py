"""Real Telegram Bot API adapter (requires TELEGRAM_BOT_TOKEN).

Processing indicator: an animated Telegram sticker (.tgs, hourglass). If a
handler takes longer than a threshold (default 0.5s), the sticker is sent;
when the handler finishes the sticker is deleted, then the normal result is
sent. Uses `sendSticker` (NOT GIF / sendAnimation). A returned sticker
file_id is cached and reused so the .tgs is not uploaded repeatedly.

PENDING_EXTERNAL_CREDENTIAL until verified with a real token.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import requests

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage
from qm_training.bot.processing import DEFAULT_SLOW_THRESHOLD_SECONDS, run_with_sticker_indicator
from qm_training.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


class TelegramBotAdapter:
    def __init__(
        self,
        token: str,
        workflow,
        api_base: str = "https://api.telegram.org",
        *,
        slow_threshold: float = DEFAULT_SLOW_THRESHOLD_SECONDS,
        sticker_file_id: str | None = None,
        sticker_path: str = "assets/hourglass.tgs",
        sticker_min_display: float = 0.7,
        allow_sticker_upload: bool = False,
    ) -> None:
        self.token = token
        self.workflow = workflow
        self.api_base = api_base.rstrip("/")
        self.slow_threshold = slow_threshold
        self.sticker_file_id = sticker_file_id
        self.sticker_path = sticker_path
        self.sticker_min_display = sticker_min_display
        self.allow_sticker_upload = allow_sticker_upload
        self._sticker_file_id: str | None = None  # cached after first send
        self.session = requests.Session()
        self._send_lock = threading.Lock()
        self._offset: int | None = None

    def _url(self, method: str) -> str:
        return f"{self.api_base}/bot{self.token}/{method}"

    # -- sending ----------------------------------------------------------- #

    def send_message(self, chat_id: str, message: OutgoingMessage) -> None:
        payload = {"chat_id": chat_id, "text": message.text}
        if message.buttons:
            payload["reply_markup"] = {
                "keyboard": [[{"text": button}] for button in message.buttons],
                "resize_keyboard": True,
            }
        with self._send_lock:
            self.session.post(self._url("sendMessage"), json=payload, timeout=30)
        for document in message.documents:
            with open(document, "rb") as handle:
                with self._send_lock:
                    self.session.post(
                        self._url("sendDocument"),
                        data={"chat_id": chat_id},
                        files={"document": (Path(document).name, handle)},
                        timeout=120,
                    )

    def _sticker_source(self) -> tuple[str, str] | None:
        """Return ('file_id', value) or ('path', value) or None.

        By default only a Telegram file_id is used (fast and reliable). Uploading
        a local .tgs is opt-in via ``allow_sticker_upload`` because an invalid
        .tgs is delivered as a document (an unrelated file in the chat).
        """
        if self._sticker_file_id:
            return ("file_id", self._sticker_file_id)
        if self.sticker_file_id:
            return ("file_id", self.sticker_file_id)
        if self.allow_sticker_upload:
            candidate = Path(self.sticker_path)
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            if candidate.exists():
                return ("path", str(candidate))
        return None

    def send_sticker(self, chat_id: str) -> int | None:
        """Send the hourglass animated sticker; return its message_id (or None)."""
        source = self._sticker_source()
        if source is None:
            return None
        kind, value = source
        try:
            with self._send_lock:
                if kind == "path":
                    with open(value, "rb") as handle:
                        response = self.session.post(
                            self._url("sendSticker"),
                            data={"chat_id": chat_id},
                            files={"sticker": (Path(value).name, handle)},
                            timeout=120,
                        )
                else:
                    response = self.session.post(
                        self._url("sendSticker"),
                        json={"chat_id": chat_id, "sticker": value},
                        timeout=30,
                    )
            payload = response.json()
            if isinstance(payload, dict) and payload.get("ok") is False:
                logger.warning("sendSticker rejected: %s", payload.get("description"))
                return None
            result = payload.get("result", {}) if isinstance(payload, dict) else {}
            file_id = result.get("sticker", {}).get("file_id")
            if file_id:
                self._sticker_file_id = file_id  # reuse next time (no re-upload)
            message_id = result.get("message_id")
            if message_id:
                logger.info("sendSticker ok message_id=%s", message_id)
            return message_id
        except (requests.RequestException, ValueError, AttributeError, OSError) as exc:
            logger.warning("sendSticker failed: %s", type(exc).__name__)
            return None

    def delete_message(self, chat_id: str, message_id: int) -> None:
        with self._send_lock:
            self.session.post(
                self._url("deleteMessage"),
                json={"chat_id": chat_id, "message_id": message_id},
                timeout=15,
            )

    def send_chat_action(self, chat_id: str, action: str = "typing") -> None:
        """Native Telegram activity indicator (fallback when no valid sticker)."""
        try:
            with self._send_lock:
                self.session.post(
                    self._url("sendChatAction"),
                    json={"chat_id": chat_id, "action": action},
                    timeout=15,
                )
        except requests.RequestException as exc:
            logger.warning("sendChatAction failed: %s", type(exc).__name__)

    def _send_processing_indicator(self, chat_id: str) -> int | None:
        """Send the hourglass sticker; fall back to a native typing action."""
        message_id = self.send_sticker(chat_id)
        if message_id is None:
            self.send_chat_action(chat_id)
        return message_id

    # -- receiving --------------------------------------------------------- #

    def get_updates(self, offset: int | None = None) -> list[IncomingMessage]:
        params = {"timeout": 30}
        if offset is not None:
            params["offset"] = offset
        response = self.session.get(self._url("getUpdates"), params=params, timeout=60)
        response.raise_for_status()
        messages: list[IncomingMessage] = []
        seen: set[int] = set()
        for update in response.json().get("result", []):
            update_id = update["update_id"]
            self._offset = update_id + 1
            if update_id in seen:  # defensive: never hand the same update twice
                continue
            seen.add(update_id)
            try:
                messages.append(self._to_incoming(update))
            except Exception as exc:  # noqa: BLE001 - skip poison updates, keep polling
                chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                if chat_id:
                    self._notify_error(chat_id, exc)
        return messages

    def _to_incoming(self, update: dict) -> IncomingMessage:
        update_id = update.get("update_id")
        if "callback_query" in update:
            callback = update["callback_query"]
            return IncomingMessage(
                user_id=str(callback.get("from", {}).get("id", "")),
                text=str(callback.get("data", "")),
                update_id=update_id,
            )
        message = update.get("message", {})
        chat = message.get("chat", {})
        user_id = str(chat.get("id", ""))
        text = message.get("text", "")
        document = None
        photo = None
        if "document" in message:
            document = self.download_file(
                message["document"]["file_id"], Path("storage/sessions") / user_id / "input"
            )
        if "photo" in message:
            largest = message["photo"][-1]
            photo = self.download_file(
                largest["file_id"], Path("storage/sessions") / user_id / "photos"
            )
        return IncomingMessage(
            user_id=user_id, text=text, document_path=document, photo_path=photo, update_id=update_id
        )

    def download_file(self, file_id: str, destination: Path) -> Path:
        info = self.session.get(self._url("getFile"), params={"file_id": file_id}, timeout=30).json()
        file_path = info["result"]["file_path"]
        url = f"{self.api_base}/file/bot{self.token}/{file_path}"
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / Path(file_path).name
        with self.session.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with open(target, "wb") as handle:
                for chunk in response.iter_content(chunk_size=65536):
                    handle.write(chunk)
        return target

    # -- dispatch ---------------------------------------------------------- #

    def _handle_incoming(self, incoming: IncomingMessage) -> None:
        outgoing = run_with_sticker_indicator(
            lambda: self.workflow.handle(incoming),
            send_sticker=lambda: self._send_processing_indicator(incoming.user_id),
            delete_sticker=lambda message_id: self.delete_message(incoming.user_id, message_id),
            threshold=self.slow_threshold,
            min_sticker_display_seconds=self.sticker_min_display,
        )
        for message in outgoing:
            self.send_message(incoming.user_id, message)

    def _notify_error(self, chat_id: str, exc: Exception) -> None:
        try:
            self.send_message(
                chat_id,
                OutgoingMessage(
                    f"❌ Terjadi kesalahan internal ({type(exc).__name__}). "
                    "Silakan kirim /new_training dan coba lagi."
                ),
            )
        except Exception:  # noqa: BLE001 - never let error reporting crash the loop
            pass

    def run_forever(self, retry_delay: float = 2.0) -> None:  # pragma: no cover - requires real token
        while True:
            try:
                updates = self.get_updates(self._offset)
            except requests.RequestException:
                time.sleep(retry_delay)
                continue
            except Exception:  # noqa: BLE001 - keep the bot alive no matter what
                time.sleep(retry_delay)
                continue
            for incoming in updates:
                try:
                    self._handle_incoming(incoming)
                except Exception as exc:  # noqa: BLE001
                    self._notify_error(incoming.user_id, exc)
