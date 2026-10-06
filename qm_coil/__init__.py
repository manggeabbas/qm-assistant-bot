"""qm_coil: port Python dari bot Form Gulungan (qm-ywi-telegram-bot).

Sumber asli: https://github.com/manggeabbas/qm-ywi-telegram-bot
(JavaScript + grammy, ~3.500 baris, 18 modul).

STATUS: port bertahap. Modul yang sudah di-port penuh:
  - material (deteksi Z/K/G + test, dari src/material.js)
  - numbering (aturan HAxx + test, dari src/numbering.js)
  - diameter (aturan FT/FJ + test, dari src/diameter.js)
  - form (output Mandarin + preview + test, dari src/form.js)
  - validation (validator tiap langkah + test, dari src/validation.js)

Sisanya masih stub yang memetakan 1:1 ke file ``src/*.js`` aslinya.
Urutan port yang disarankan: numbering -> diameter -> form ->
validation -> state -> registration/invites/users/employees/access ->
db -> menu/texts -> wizard -> admin -> bot.
"""

from __future__ import annotations

from qm_coil.diameter import (
    DIAMETER_CONSTANTS,
    DiameterOption,
    DiameterPrompt,
    DiameterResolution,
    get_diameter_prompt,
    resolve_diameter,
)
from qm_coil.form import (
    format_full_preview,
    format_numbering_preview,
    generate_workplace_mandarin_output,
)
from qm_coil.material import (
    MATERIAL_MAP,
    UNKNOWN_MATERIAL_MESSAGE,
    MaterialDetection,
    detect_material,
    get_material_name,
)
from qm_coil.numbering import (
    CoilGeneration,
    ParamsCheck,
    SuffixParse,
    generate_coil_numbers,
    parse_source_coil_suffix,
    validate_numbering_params,
)
from qm_coil.validation import (
    VALID_GRADES,
    VALID_MACHINES,
    ValidationResult,
    validate_count,
    validate_grade,
    validate_length,
    validate_machine,
    validate_main_defect,
    validate_name,
    validate_nik,
    validate_remark,
    validate_source_coil,
    validate_specification,
    validate_start_digit,
)
from qm_coil.wizard import CoilWizard

__all__ = [
    "CoilWizard",
    "MATERIAL_MAP",
    "UNKNOWN_MATERIAL_MESSAGE",
    "MaterialDetection",
    "detect_material",
    "get_material_name",
    "CoilGeneration",
    "ParamsCheck",
    "SuffixParse",
    "generate_coil_numbers",
    "parse_source_coil_suffix",
    "validate_numbering_params",
    "DIAMETER_CONSTANTS",
    "DiameterOption",
    "DiameterPrompt",
    "DiameterResolution",
    "get_diameter_prompt",
    "resolve_diameter",
    "format_full_preview",
    "format_numbering_preview",
    "generate_workplace_mandarin_output",
    "VALID_GRADES",
    "VALID_MACHINES",
    "ValidationResult",
    "validate_count",
    "validate_grade",
    "validate_length",
    "validate_machine",
    "validate_main_defect",
    "validate_name",
    "validate_nik",
    "validate_remark",
    "validate_source_coil",
    "validate_specification",
    "validate_start_digit",
]
