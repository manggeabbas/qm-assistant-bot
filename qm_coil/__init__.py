"""qm_coil: port Python dari bot Form Gulungan (qm-ywi-telegram-bot).

Sumber asli: https://github.com/manggeabbas/qm-ywi-telegram-bot
(JavaScript + grammy, ~3.500 baris, 18 modul).

STATUS: port bertahap. Modul yang sudah di-port penuh:
  - material (deteksi Z/K/G + test, dari src/material.js)
  - numbering (aturan HAxx + test, dari src/numbering.js)
  - diameter (aturan FT/FJ + test, dari src/diameter.js)
  - form (output Mandarin + preview + test, dari src/form.js)
  - validation (validator tiap langkah + test, dari src/validation.js)
  - state (sesi per user + idempotensi + test, dari src/state.js)
  - db (SQLite + test, dari src/db.js)
  - users (repository user + test, dari src/users.js)
  - employees (direktori karyawan + test, dari src/employees.js)
  - invites (token undangan + test, dari src/invites.js)
  - access (is_owner + status + test, dari src/access.js)
  - registration (tahap + NIK murni + test, dari src/registration.js)
  - config (env + test ringan, dari src/config.js)
  - logger (logging + sanitasi, dari src/logger.js)
  - menu (menu utama + test, dari src/menu.js)
  - texts (teks UI + test, dari src/texts.js)
  - wizard (state machine + dispatcher callback + test, dari src/wizard.js
    dan handler callback di src/bot.js)
  - admin (panel /admin + test, dari src/admin.js)

Semua 18 modul selesai di-port. Belum dikerjakan: pengkabelan
end-to-end (access guard + registrasi + idempotensi di router,
perintah /new /cancel /help, middleware admin di depan wizard).

Sisanya masih stub yang memetakan 1:1 ke file ``src/*.js`` aslinya
(hanya ``admin.py`` yang belum di-port).
"""

from __future__ import annotations

from qm_coil.access import is_owner, resolve_user_status
from qm_coil.admin import (
    ADMIN_CALLBACK,
    AdminPanel,
    AdminReply,
    admin_panel_keyboard,
    admin_panel_text,
    format_datetime,
    user_detail_keyboard,
    user_detail_text,
)
from qm_coil.config import (
    DB_PATH,
    DEFAULT_TOKEN_TTL_DAYS,
    DEPARTMENT,
    DIVISION,
    HEADER_TEXT,
    MOTTO,
    OWNER_TELEGRAM_ID,
    OWNER_TELEGRAM_IDS,
    VERSION,
)
from qm_coil.db import get_db, migrate, now_iso, open_db, transaction
from qm_coil.diameter import (
    DIAMETER_CONSTANTS,
    DiameterOption,
    DiameterPrompt,
    DiameterResolution,
    get_diameter_prompt,
    resolve_diameter,
)
from qm_coil.employees import (
    add_or_update_employee,
    bulk_import_employees,
    count_employees,
    delete_employee,
    get_employee_by_nik,
    list_employees,
    parse_employee_line,
    row_to_employee,
)
from qm_coil.form import (
    format_full_preview,
    format_numbering_preview,
    generate_workplace_mandarin_output,
)
from qm_coil.invites import (
    TOKEN_STATUS,
    RedeemResult,
    create_invite_tokens,
    generate_invite_token,
    hash_invite_token,
    list_invite_tokens,
    mark_expired_tokens,
    normalize_token,
    redeem_token_for_user,
)
from qm_coil.logger import logger
from qm_coil.material import (
    MATERIAL_MAP,
    UNKNOWN_MATERIAL_MESSAGE,
    MaterialDetection,
    detect_material,
    get_material_name,
)
from qm_coil.menu import (
    MenuButton,
    MenuKeyboard,
    callback_of,
    main_menu_keyboard,
    main_menu_text,
    to_reply_buttons,
)
from qm_coil.numbering import (
    CoilGeneration,
    ParamsCheck,
    SuffixParse,
    generate_coil_numbers,
    parse_source_coil_suffix,
    validate_numbering_params,
)
from qm_coil.registration import (
    REG_CALLBACKS,
    RegistrationReply,
    begin_registration,
    handle_registration_callback,
    handle_registration_text,
    process_nik_input,
    registration_stage,
    reset_nik,
    resume_registration,
    send_confirmation,
)
from qm_coil.state import (
    CoilSessionStore,
    IdempotencyCache,
    create_initial_state,
    idempotency_cache,
    sessions,
)
from qm_coil.texts import TEXTS, Texts
from qm_coil.users import (
    USER_STATUS,
    create_user,
    get_or_create_user,
    get_status,
    get_user_by_id,
    get_user_by_telegram_id,
    is_nik_taken_by_other,
    list_users,
    mask_nik,
    row_to_user,
    update_user,
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
from qm_coil.wizard import (
    STEPS,
    CoilWizard,
    WizardReply,
    cancel_wizard,
    handle_callback,
    handle_machine_selection,
    handle_text_input,
    start_new_wizard,
)

__all__ = [
    "CoilWizard",
    "STEPS",
    "WizardReply",
    "cancel_wizard",
    "handle_callback",
    "handle_machine_selection",
    "handle_text_input",
    "start_new_wizard",
    "ADMIN_CALLBACK",
    "AdminPanel",
    "AdminReply",
    "admin_panel_keyboard",
    "admin_panel_text",
    "format_datetime",
    "user_detail_keyboard",
    "user_detail_text",
    "is_owner",
    "resolve_user_status",
    "DB_PATH",
    "DEFAULT_TOKEN_TTL_DAYS",
    "DEPARTMENT",
    "DIVISION",
    "HEADER_TEXT",
    "MOTTO",
    "OWNER_TELEGRAM_ID",
    "OWNER_TELEGRAM_IDS",
    "VERSION",
    "get_db",
    "migrate",
    "now_iso",
    "open_db",
    "transaction",
    "add_or_update_employee",
    "bulk_import_employees",
    "count_employees",
    "delete_employee",
    "get_employee_by_nik",
    "list_employees",
    "parse_employee_line",
    "row_to_employee",
    "TOKEN_STATUS",
    "RedeemResult",
    "create_invite_tokens",
    "generate_invite_token",
    "hash_invite_token",
    "list_invite_tokens",
    "mark_expired_tokens",
    "normalize_token",
    "redeem_token_for_user",
    "logger",
    "REG_CALLBACKS",
    "RegistrationReply",
    "begin_registration",
    "handle_registration_callback",
    "handle_registration_text",
    "process_nik_input",
    "registration_stage",
    "reset_nik",
    "resume_registration",
    "send_confirmation",
    "MenuButton",
    "MenuKeyboard",
    "callback_of",
    "main_menu_keyboard",
    "main_menu_text",
    "to_reply_buttons",
    "TEXTS",
    "Texts",
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
    "CoilSessionStore",
    "IdempotencyCache",
    "create_initial_state",
    "idempotency_cache",
    "sessions",
    "USER_STATUS",
    "create_user",
    "get_or_create_user",
    "get_status",
    "get_user_by_id",
    "get_user_by_telegram_id",
    "is_nik_taken_by_other",
    "list_users",
    "mask_nik",
    "row_to_user",
    "update_user",
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
