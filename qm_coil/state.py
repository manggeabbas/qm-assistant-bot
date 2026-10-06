"""Manajemen state sesi pengguna dan idempotensi update_id Telegram.

Port dari: ``src/state.js`` (68 baris, qm-ywi-telegram-bot).
Status: PORTED (+ test sendiri; tidak ada test JS aslinya).

State sesi memakai dict dengan kunci camelCase seperti di JS aslinya,
agar bisa langsung dipakai oleh ``form.py`` dan (nanti) ``wizard.py``
tanpa lapisan translasi.
"""

from __future__ import annotations

from collections import deque


def create_initial_state() -> dict:
    """State sesi kosong awal untuk satu user."""
    return {
        "step": "IDLE",
        "machine": None,
        "sourceCoil": None,
        "materialCode": None,
        "material": None,
        "specification": None,
        "count": None,
        "startDigit": None,
        "generatedCoils": [],
        # Pointer loop input data per coil
        "inspections": [],
        "currentCoilIndex": 0,
        "currentCoilData": {},
        # Data edit sementara: {"coilIndex": int, "field": str} | None
        "editTarget": None,
    }


class CoilSessionStore:
    """Penyimpanan state sesi per user (in-memory)."""

    def __init__(self) -> None:
        self._sessions: dict[str, dict] = {}

    def get(self, user_id: object) -> dict:
        key = str(user_id)
        if key not in self._sessions:
            self._sessions[key] = create_initial_state()
        return self._sessions[key]

    def set(self, user_id: object, updates: dict) -> dict:
        key = str(user_id)
        current = self.get(key)
        updated = {**current, **updates}
        self._sessions[key] = updated
        return updated

    def clear(self, user_id: object) -> None:
        self._sessions.pop(str(user_id), None)

    def has(self, user_id: object) -> bool:
        return str(user_id) in self._sessions


class IdempotencyCache:
    """Cache update_id Telegram yang sudah diproses (FIFO, batas ukuran)."""

    def __init__(self, max_size: int = 10000) -> None:
        self.max_size = max_size
        self._processed: set[int] = set()
        self._order: deque[int] = deque()

    @staticmethod
    def _normalize(update_id: object) -> int | None:
        if update_id is None:
            return None
        try:
            return int(update_id)
        except (ValueError, TypeError):
            return None

    def has(self, update_id: object) -> bool:
        normalized = self._normalize(update_id)
        if normalized is None:
            return False
        return normalized in self._processed

    def add(self, update_id: object) -> None:
        normalized = self._normalize(update_id)
        if normalized is None or normalized in self._processed:
            return
        self._processed.add(normalized)
        self._order.append(normalized)
        while len(self._order) > self.max_size:
            oldest = self._order.popleft()
            self._processed.discard(oldest)

    def clear(self) -> None:
        self._processed.clear()
        self._order.clear()


# Singleton modul (seperti di JS aslinya); wizard membuat instans sendiri
# bila butuh isolasi (mis. untuk test).
sessions = CoilSessionStore()
idempotency_cache = IdempotencyCache()
