"""Aturan diameter mesin FT dan FJ QM-YWI.

Port dari: ``src/diameter.js`` (68 baris, qm-ywi-telegram-bot).
Status: PORTED (termasuk test, dari test/diameter.test.js).
"""

from __future__ import annotations

from dataclasses import dataclass

DIAMETER_CONSTANTS = {
    "FT_DEFAULT_DIAMETER": 610,
    "FT_CHANGE_YES": "Perlu Ubah Diameter 508",
    "FT_CHANGE_NO": "Tidak Perlu",
    "FJ_DEFAULT_CHANGE": "Tidak Perlu",
    "FJ_DIAMETER_CHOICES": [610, 508],
}


@dataclass
class DiameterOption:
    label: str
    value: object  # str untuk FT, int untuk FJ (seperti aslinya)


@dataclass
class DiameterPrompt:
    machine: str
    question: str
    options: list[DiameterOption]


@dataclass
class DiameterResolution:
    diameter: int
    change_diameter: str


def get_diameter_prompt(machine: str) -> DiameterPrompt:
    """Konfigurasi prompt diameter berdasarkan mesin (FT/FJ)."""
    if machine == "FT":
        return DiameterPrompt(
            machine="FT",
            question="目前内径: 610\n\nApakah perlu ubah diameter menjadi 508?",
            options=[
                DiameterOption(
                    label="Perlu Ubah Diameter 508",
                    value=DIAMETER_CONSTANTS["FT_CHANGE_YES"],
                ),
                DiameterOption(
                    label="Tidak Perlu",
                    value=DIAMETER_CONSTANTS["FT_CHANGE_NO"],
                ),
            ],
        )
    if machine == "FJ":
        return DiameterPrompt(
            machine="FJ",
            question="Pilih diameter dalam saat ini (目前内径):",
            options=[
                DiameterOption(label="610", value=610),
                DiameterOption(label="508", value=508),
            ],
        )
    raise ValueError(f"Mesin tidak dikenal: {machine}")


def resolve_diameter(machine: str, selection: object) -> DiameterResolution:
    """Selesaikan nilai diameter & status ubah diameter dari pilihan user."""
    if machine == "FT":
        is_change = "508" in str(selection) or selection == DIAMETER_CONSTANTS["FT_CHANGE_YES"]
        return DiameterResolution(
            diameter=DIAMETER_CONSTANTS["FT_DEFAULT_DIAMETER"],
            change_diameter=(
                DIAMETER_CONSTANTS["FT_CHANGE_YES"]
                if is_change
                else DIAMETER_CONSTANTS["FT_CHANGE_NO"]
            ),
        )
    if machine == "FJ":
        try:
            parsed = int(str(selection).strip())
        except (ValueError, TypeError):
            parsed = 610  # seperti parseInt -> NaN -> fallback 610 di JS
        diameter = 508 if parsed == 508 else 610
        return DiameterResolution(
            diameter=diameter,
            change_diameter=DIAMETER_CONSTANTS["FJ_DEFAULT_CHANGE"],
        )
    raise ValueError(f"Mesin tidak dikenal: {machine}")
