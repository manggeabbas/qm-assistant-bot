"""qm_coil: port Python dari bot Form Gulungan (qm-ywi-telegram-bot).

Sumber asli: https://github.com/manggeabbas/qm-ywi-telegram-bot
(JavaScript + grammy, ~3.500 baris, 18 modul).

STATUS: port bertahap. Modul yang sudah di-port penuh:
  - material (deteksi Z/K/G + test, dari src/material.js)

Sisanya masih stub yang memetakan 1:1 ke file ``src/*.js`` aslinya.
Urutan port yang disarankan: numbering -> diameter -> form ->
validation -> state -> registration/invites/users/employees/access ->
db -> menu/texts -> wizard -> admin -> bot.
"""

from __future__ import annotations

from qm_coil.material import (
    MATERIAL_MAP,
    UNKNOWN_MATERIAL_MESSAGE,
    MaterialDetection,
    detect_material,
    get_material_name,
)
from qm_coil.wizard import CoilWizard

__all__ = [
    "CoilWizard",
    "MATERIAL_MAP",
    "UNKNOWN_MATERIAL_MESSAGE",
    "MaterialDetection",
    "detect_material",
    "get_material_name",
]
