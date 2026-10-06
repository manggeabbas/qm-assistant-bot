"""Mode sesi per user untuk router QM Assistant.

Skeleton: in-memory saja. Jika bot restart, mode kembali ke "menu" dan
user cukup kirim /start lagi. Persistensi (SQLite/JSON) ditambahkan saat
modul coil di-port penuh.
"""

from __future__ import annotations

MODE_MENU = "menu"
MODE_TRAINING = "training"
MODE_COIL = "coil"

_VALID_MODES = (MODE_MENU, MODE_TRAINING, MODE_COIL)


class AssistantSessionStore:
    """Menyimpan mode aktif per user_id (in-memory)."""

    def __init__(self) -> None:
        self._modes: dict[str, str] = {}

    def get_mode(self, user_id: str) -> str:
        return self._modes.get(str(user_id), MODE_MENU)

    def set_mode(self, user_id: str, mode: str) -> None:
        if mode not in _VALID_MODES:
            raise ValueError(f"mode tidak dikenal: {mode}")
        self._modes[str(user_id)] = mode

    def reset(self, user_id: str) -> None:
        self._modes[str(user_id)] = MODE_MENU
