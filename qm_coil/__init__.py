"""qm_coil: port Python dari bot Form Gulungan (qm-ywi-telegram-bot).

Sumber asli: https://github.com/manggeabbas/qm-ywi-telegram-bot
(JavaScript + grammy, ~3.500 baris, 18 modul).

STATUS: skeleton. Setiap modul di bawah ini adalah stub yang memetakan
1:1 ke file ``src/*.js`` aslinya. Port penuh dilakukan bertahap per modul,
didahulukan yang tanpa state: material -> numbering -> diameter -> form ->
validation -> state -> registration/invites/users/employees/access ->
db -> menu/texts -> wizard -> admin -> bot.
"""

from __future__ import annotations

from qm_coil.wizard import CoilWizard

__all__ = ["CoilWizard"]
