"""Run a blocking operation and show a sticker indicator if it is slow.

Flow (per operation):
    start op -> wait `threshold` -> still running? -> send sticker
             -> op done -> delete sticker -> send normal result

One operation shows at most one sticker. Indicator failures never fail the
operation.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, TypeVar

T = TypeVar("T")
DEFAULT_SLOW_THRESHOLD_SECONDS = 0.5

logger = logging.getLogger(__name__)


def run_with_sticker_indicator(
    func: Callable[[], T],
    send_sticker: Callable[[], int | None],
    delete_sticker: Callable[[int], None],
    threshold: float = DEFAULT_SLOW_THRESHOLD_SECONDS,
    min_sticker_display_seconds: float = 0.0,
):
    """Run ``func``; if it exceeds ``threshold`` show one sticker, then clean up.

    - If ``func`` finishes within ``threshold``: no sticker.
    - If it is slower: send exactly one sticker and delete it when finished.
    - ``min_sticker_display_seconds`` keeps the sticker visible at least that
      long (so a fast-finishing operation still shows something).
    - If ``func`` raises after a sticker was sent: delete it, then re-raise.
    - Sticker send/delete errors are logged and never fail the operation.
    """
    done = threading.Event()
    box: dict = {}
    state: dict = {"finished": False, "message_id": None, "shown_at": None}
    lock = threading.Lock()

    def worker() -> None:
        try:
            box["result"] = func()
        except BaseException as exc:  # noqa: BLE001 - forwarded to the caller
            box["error"] = exc
        finally:
            done.set()

    def timer() -> None:
        # Only fires if the operation is still running after the threshold.
        if done.wait(threshold):
            return
        if done.is_set():
            return
        try:
            message_id = send_sticker()
        except Exception as exc:  # noqa: BLE001 - indicator must not break the op
            logger.warning("sticker indicator failed to send: %s", type(exc).__name__)
            return
        if message_id is None:
            return
        logger.info("processing sticker shown message_id=%s", message_id)
        with lock:
            already_finished = state["finished"]
            if not already_finished:
                state["message_id"] = message_id
                state["shown_at"] = time.monotonic()
        if already_finished:
            # Operation ended while the sticker was being sent: clean it up.
            try:
                delete_sticker(message_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("sticker indicator failed to delete: %s", type(exc).__name__)

    worker_thread = threading.Thread(target=worker, daemon=True)
    timer_thread = threading.Thread(target=timer, daemon=True)
    worker_thread.start()
    timer_thread.start()
    worker_thread.join()  # the result is never delayed by a slow sticker upload

    with lock:
        state["finished"] = True
        message_id = state["message_id"]
        shown_at = state["shown_at"]
        state["message_id"] = None

    if message_id is not None:
        if min_sticker_display_seconds and shown_at is not None:
            remaining = min_sticker_display_seconds - (time.monotonic() - shown_at)
            if remaining > 0:
                time.sleep(remaining)
        try:
            delete_sticker(message_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sticker indicator failed to delete: %s", type(exc).__name__)

    if "error" in box:
        raise box["error"]
    return box.get("result")
