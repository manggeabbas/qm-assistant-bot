"""Single-instance guard.

Two bots polling the same token deliver duplicate messages (duplicate theme,
duplicate preview, duplicate validation error). This lock makes a second
instance exit instead of polling.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    """Another bot instance already holds the lock."""


class SingleInstance:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "w", encoding="utf-8")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise AlreadyRunningError(str(self.path)) from exc
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle, fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None


@contextmanager
def single_instance(path: Path):
    lock = SingleInstance(path)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()
