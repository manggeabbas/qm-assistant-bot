"""QM Assistant: router menu + sesi gabungan untuk 1 bot, 1 token.

Paket ini menyatukan dua alur tanpa mengubah ``qm_training``:

- ``router.py``       -- ``/start`` menjadi menu: Form Gulungan | Form Pelatihan.
- ``session.py``      -- mode aktif per user (menu / training / coil).
- ``coil_gateway.py`` -- pengkabelan Form Gulungan: access guard + registrasi
  + admin + wizard + idempotensi (dipakai router sebagai coil_handler).
"""

from __future__ import annotations

from qm_assistant.coil_gateway import CoilGateway
from qm_assistant.router import BTN_COIL, BTN_TRAINING, AssistantRouter
from qm_assistant.session import AssistantSessionStore

__all__ = [
    "AssistantRouter",
    "AssistantSessionStore",
    "BTN_COIL",
    "BTN_TRAINING",
    "CoilGateway",
]
