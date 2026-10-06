"""State machine & wizard percakapan Form Gulungan.

Port dari: ``src/wizard.js`` (678 baris) + dispatcher callback dari
``src/bot.js`` (bagian ``callback_query:data``).
Status: PORTED.

Beda dengan aslinya: fungsi-fungsi di sini bebas framework — tidak
menerima ``ctx`` grammy. Setiap fungsi menerima ``user_id`` dan
``CoilSessionStore``, lalu mengembalikan ``list[WizardReply]``
(teks + tombol + flag markdown). Lapisan Telegram (router/adapter)
yang bertugas mengirimkannya dan me-routing callback.

Alur langkah (STEPS): SELECT_MACHINE -> INPUT_SOURCE_COIL ->
CONFIRM_MATERIAL -> INPUT_SPECIFICATION -> INPUT_COUNT ->
INPUT_START_DIGIT -> PREVIEW_NUMBERING -> per coil:
INPUT_COIL_GRADE -> INPUT_COIL_DEFECT -> INPUT_COIL_REMARK ->
INPUT_COIL_LENGTH -> INPUT_COIL_DIAMETER -> PREVIEW_FULL_FORM
(-> edit -> PREVIEW_FULL_FORM) -> generate output final.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from qm_coil.config import HEADER_TEXT
from qm_coil.diameter import get_diameter_prompt, resolve_diameter
from qm_coil.form import (
    format_full_preview,
    format_numbering_preview,
    generate_workplace_mandarin_output,
)
from qm_coil.material import MATERIAL_MAP
from qm_coil.menu import MenuButton, MenuKeyboard
from qm_coil.numbering import generate_coil_numbers
from qm_coil.state import CoilSessionStore
from qm_coil.validation import (
    VALID_GRADES,
    ValidationResult,
    validate_count,
    validate_grade,
    validate_length,
    validate_machine,
    validate_main_defect,
    validate_nik,
    validate_remark,
    validate_source_coil,
    validate_specification,
    validate_start_digit,
)


class STEPS:
    IDLE = "IDLE"
    SELECT_MACHINE = "SELECT_MACHINE"
    INPUT_SOURCE_COIL = "INPUT_SOURCE_COIL"
    CONFIRM_MATERIAL = "CONFIRM_MATERIAL"
    INPUT_SPECIFICATION = "INPUT_SPECIFICATION"
    INPUT_COUNT = "INPUT_COUNT"
    INPUT_START_DIGIT = "INPUT_START_DIGIT"
    PREVIEW_NUMBERING = "PREVIEW_NUMBERING"
    INPUT_COIL_GRADE = "INPUT_COIL_GRADE"
    INPUT_COIL_DEFECT = "INPUT_COIL_DEFECT"
    INPUT_COIL_REMARK = "INPUT_COIL_REMARK"
    INPUT_COIL_LENGTH = "INPUT_COIL_LENGTH"
    INPUT_COIL_DIAMETER = "INPUT_COIL_DIAMETER"
    PREVIEW_FULL_FORM = "PREVIEW_FULL_FORM"
    EDIT_SELECT_COIL = "EDIT_SELECT_COIL"
    EDIT_SELECT_FIELD = "EDIT_SELECT_FIELD"
    EDIT_INPUT_VALUE = "EDIT_INPUT_VALUE"


@dataclass
class WizardReply:
    """Satu pesan balasan wizard."""

    text: str
    buttons: MenuKeyboard = field(default_factory=list)
    markdown: bool = False
    # True bila pesan dipicu oleh tap tombol (aslinya: editMessageText).
    edit: bool = False


def _btn(label: str, data: str) -> MenuButton:
    return (label, data)


def _cancel_row() -> list[MenuButton]:
    return [_btn("Batal", "action:cancel")]


# ---------------------------------------------------------------------------
# Mulai & pilih mesin
# ---------------------------------------------------------------------------


def start_new_wizard(
    user_id: object,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    """Mulai wizard baru: reset sesi, minta pilih mesin."""
    store.clear(user_id)
    store.set(user_id, {"step": STEPS.SELECT_MACHINE})
    return [
        WizardReply(
            text=f"{HEADER_TEXT}\n\nSilakan pilih mesin:",
            buttons=[[ _btn("FT", "machine:FT"), _btn("FJ", "machine:FJ")],
                     _cancel_row()],
            edit=from_callback,
        )
    ]


def handle_machine_selection(
    user_id: object,
    machine: str,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    check = validate_machine(machine)
    if not check.valid:
        return [WizardReply(text=check.error)]

    store.set(
        user_id, {"machine": check.value, "step": STEPS.INPUT_SOURCE_COIL}
    )
    return [
        WizardReply(
            text=(
                f"Mesin terpilih: *{check.value}*\n\n"
                "Silakan masukkan nomor gulungan asal:\n"
                "(Contoh: `QH2608K2531HA10`)"
            ),
            buttons=[
                [_btn("Kembali", "action:back_to_machine")],
                _cancel_row(),
            ],
            markdown=True,
            edit=from_callback,
        )
    ]


def cancel_wizard(user_id: object, store: CoilSessionStore) -> list[WizardReply]:
    store.clear(user_id)
    return [
        WizardReply(
            text="❌ Sesi telah dibatalkan. Ketik /new untuk mulai kembali."
        )
    ]


# ---------------------------------------------------------------------------
# Input teks per langkah
# ---------------------------------------------------------------------------


def handle_text_input(
    user_id: object, text: str, store: CoilSessionStore
) -> list[WizardReply]:
    """Tangani input teks sesuai langkah aktif di sesi."""
    session = store.get(user_id)
    step = session.get("step")

    if step == STEPS.INPUT_SOURCE_COIL:
        check = validate_source_coil(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        store.set(
            user_id,
            {
                "sourceCoil": check.value,
                "materialCode": check.material_code,
                "material": check.material,
                "step": STEPS.CONFIRM_MATERIAL,
            },
        )
        confirm_msg = (
            f"Nomor Gulungan: `{check.value}`\n"
            f"Material Terdeteksi: *{check.material}* "
            f"(Kode: `{check.material_code}`)\n\n"
            "Apakah data nomor dan material di atas sudah benar?"
        )
        return [
            WizardReply(
                text=confirm_msg,
                buttons=[
                    [_btn("Lanjut", "action:confirm_material")],
                    [_btn("Ubah Nomor Gulungan", "action:edit_source_coil")],
                    _cancel_row(),
                ],
                markdown=True,
            )
        ]

    if step == STEPS.INPUT_SPECIFICATION:
        check = validate_specification(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        store.set(
            user_id, {"specification": check.value, "step": STEPS.INPUT_COUNT}
        )
        return [
            WizardReply(
                text=(
                    f"Spesifikasi tersimpan: `{check.value}`\n\n"
                    "Silakan masukkan jumlah gulungan baru yang akan dibuat "
                    "(bilangan bulat positif):\n(Contoh: `3`)"
                ),
                buttons=[_cancel_row()],
                markdown=True,
            )
        ]

    if step == STEPS.INPUT_COUNT:
        check = validate_count(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        store.set(
            user_id, {"count": check.value, "step": STEPS.INPUT_START_DIGIT}
        )
        return [
            WizardReply(
                text=(
                    f"Jumlah gulungan: *{check.value}*\n\n"
                    "Silakan masukkan digit awal penomoran suffix HA (0–9):\n"
                    "(Contoh: `1`)"
                ),
                buttons=[_cancel_row()],
                markdown=True,
            )
        ]

    if step == STEPS.INPUT_START_DIGIT:
        check = validate_start_digit(text, session.get("count"))
        if not check.valid:
            return [WizardReply(text=check.error)]
        numbering = generate_coil_numbers(
            session.get("sourceCoil"), session.get("count"), check.value
        )
        if not numbering.valid:
            return [WizardReply(text=numbering.error)]
        store.set(
            user_id,
            {
                "startDigit": check.value,
                "generatedCoils": numbering.coils,
                "step": STEPS.PREVIEW_NUMBERING,
            },
        )
        preview_text = format_numbering_preview(
            numbering.coils, session.get("material")
        )
        return [
            WizardReply(
                text=preview_text,
                buttons=[
                    [_btn("Konfirmasi", "action:confirm_numbering")],
                    [_btn("Edit Penomoran", "action:edit_numbering")],
                    _cancel_row(),
                ],
            )
        ]

    if step == STEPS.INPUT_COIL_DEFECT:
        check = validate_main_defect(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        current = {**(session.get("currentCoilData") or {}), "mainDefect": check.value}
        store.set(user_id, {"currentCoilData": current, "step": STEPS.INPUT_COIL_REMARK})
        coil = _current_coil(session)
        return [
            WizardReply(
                text=(
                    f"{_coil_progress(session, coil)}\n"
                    f"Cacat Utama: *{check.value}*\n\n"
                    "Silakan masukkan Remark (keterangan):\n"
                    "(Ketik `-` atau gunakan tombol di bawah jika tidak ada remark)"
                ),
                buttons=[
                    [_btn("Tanpa Remark (-)", "remark:default")],
                    _cancel_row(),
                ],
                markdown=True,
            )
        ]

    if step == STEPS.INPUT_COIL_REMARK:
        check = validate_remark(text)
        current = {**(session.get("currentCoilData") or {}), "remark": check.value}
        store.set(user_id, {"currentCoilData": current, "step": STEPS.INPUT_COIL_LENGTH})
        coil = _current_coil(session)
        return [
            WizardReply(
                text=(
                    f"{_coil_progress(session, coil)}\n"
                    f"Remark: *{check.value}*\n\n"
                    "Silakan masukkan Panjang gulungan (dalam meter):\n"
                    "(Contoh: `955`)"
                ),
                buttons=[_cancel_row()],
                markdown=True,
            )
        ]

    if step == STEPS.INPUT_COIL_LENGTH:
        check = validate_length(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        current = {**(session.get("currentCoilData") or {}), "length": check.value}
        store.set(
            user_id, {"currentCoilData": current, "step": STEPS.INPUT_COIL_DIAMETER}
        )
        return _show_diameter_prompt(user_id, store)

    if step == STEPS.EDIT_INPUT_VALUE:
        return _handle_edit_value_input(user_id, text, store)

    return [
        WizardReply(
            text="Perintah tidak dikenali dalam langkah ini. "
            "Ketik /help untuk bantuan atau /cancel untuk membatalkan."
        )
    ]


def _current_coil(session: dict) -> str:
    coils = session.get("generatedCoils") or []
    idx = session.get("currentCoilIndex") or 0
    return coils[idx] if 0 <= idx < len(coils) else "?"


def _coil_progress(session: dict, coil: str) -> str:
    idx = session.get("currentCoilIndex") or 0
    total = len(session.get("generatedCoils") or [])
    return f"[Coil {idx + 1} / {total}]: `{coil}`"


# ---------------------------------------------------------------------------
# Diameter / grade / remark
# ---------------------------------------------------------------------------


def _show_diameter_prompt(
    user_id: object, store: CoilSessionStore, *, from_callback: bool = False
) -> list[WizardReply]:
    session = store.get(user_id)
    coil = _current_coil(session)
    prompt = get_diameter_prompt(session.get("machine"))
    buttons: MenuKeyboard = [
        [_btn(opt.label, f"diameter:{opt.value}")] for opt in prompt.options
    ]
    buttons.append(_cancel_row())
    return [
        WizardReply(
            text=f"{_coil_progress(session, coil)}\n\n{prompt.question}",
            buttons=buttons,
            edit=from_callback,
        )
    ]


def _handle_grade_selection(
    user_id: object,
    grade: str,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    check = validate_grade(grade)
    if not check.valid:
        return [WizardReply(text=check.error)]
    session = store.get(user_id)
    coil = _current_coil(session)
    current = {
        **(session.get("currentCoilData") or {}),
        "coilNumber": coil,
        "grade": check.value,
    }
    store.set(user_id, {"currentCoilData": current, "step": STEPS.INPUT_COIL_DEFECT})
    return [
        WizardReply(
            text=(
                f"{_coil_progress(session, coil)}\n"
                f"Grade: *{check.value}*\n\n"
                "Silakan masukkan Cacat Utama (Main Defect):\n"
                "(Contoh: `B22`, `R20`, `D02`, `C13`)"
            ),
            buttons=[_cancel_row()],
            markdown=True,
            edit=from_callback,
        )
    ]


def _handle_default_remark(
    user_id: object, store: CoilSessionStore, *, from_callback: bool = False
) -> list[WizardReply]:
    session = store.get(user_id)
    current = {**(session.get("currentCoilData") or {}), "remark": "-"}
    store.set(user_id, {"currentCoilData": current, "step": STEPS.INPUT_COIL_LENGTH})
    coil = _current_coil(session)
    return [
        WizardReply(
            text=(
                f"{_coil_progress(session, coil)}\n"
                "Remark: *-*\n\n"
                "Silakan masukkan Panjang gulungan (dalam meter):\n"
                "(Contoh: `955`)"
            ),
            buttons=[_cancel_row()],
            markdown=True,
            edit=from_callback,
        )
    ]


def _handle_diameter_selection(
    user_id: object,
    selection: str,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    session = store.get(user_id)
    resolved = resolve_diameter(session.get("machine"), selection)
    completed = {
        **(session.get("currentCoilData") or {}),
        "diameter": resolved.diameter,
        "changeDiameter": resolved.change_diameter,
    }
    inspections = list(session.get("inspections") or [])
    idx = session.get("currentCoilIndex") or 0
    while len(inspections) <= idx:
        inspections.append({})
    inspections[idx] = completed

    next_index = idx + 1
    coils = session.get("generatedCoils") or []
    if next_index < len(coils):
        store.set(
            user_id,
            {
                "inspections": inspections,
                "currentCoilIndex": next_index,
                "currentCoilData": {"coilNumber": coils[next_index]},
                "step": STEPS.INPUT_COIL_GRADE,
            },
        )
        next_coil = coils[next_index]
        grade_buttons: MenuKeyboard = [
            [_btn(g, f"grade:{g}") for g in VALID_GRADES],
            _cancel_row(),
        ]
        return [
            WizardReply(
                text=(
                    f"Coil {idx + 1} selesai!\n\n"
                    f"Lanjut ke [Coil {next_index + 1} / {len(coils)}]: "
                    f"`{next_coil}`\nSilakan pilih Grade:"
                ),
                buttons=grade_buttons,
                markdown=True,
                edit=from_callback,
            )
        ]

    store.set(user_id, {"inspections": inspections, "step": STEPS.PREVIEW_FULL_FORM})
    return _show_full_preview(user_id, store, from_callback=from_callback)


# ---------------------------------------------------------------------------
# Preview & output final
# ---------------------------------------------------------------------------


def _show_full_preview(
    user_id: object, store: CoilSessionStore, *, from_callback: bool = False
) -> list[WizardReply]:
    session = store.get(user_id)
    preview_text = format_full_preview(session)
    buttons: MenuKeyboard = [
        [_btn("✅ Konfirmasi & Generate Output", "action:generate_final")],
        [
            _btn("✏️ Edit Nomor", "edit:source_coil"),
            _btn("✏️ Edit Spesifikasi", "edit:specification"),
        ],
        [
            _btn("✏️ Edit Data Coil", "edit:select_coil"),
            _btn("❌ Batal", "action:cancel"),
        ],
    ]
    return [
        WizardReply(
            text=preview_text, buttons=buttons, markdown=True, edit=from_callback
        )
    ]


def _generate_final_output(
    user_id: object, store: CoilSessionStore, *, from_callback: bool = False
) -> list[WizardReply]:
    session = store.get(user_id)
    final_output = generate_workplace_mandarin_output(session)
    success_msg = f"✅ *FORM BERHASIL DIGENERATE*\n{HEADER_TEXT}\n\nSilakan salin teks di bawah ini:"
    code_block = f"```text\n{final_output}\n```"
    store.clear(user_id)
    return [
        WizardReply(text=success_msg, markdown=True, edit=from_callback),
        WizardReply(
            text=code_block,
            buttons=[[_btn("➕ Buat Form Baru (/new)", "action:new_form")]],
            markdown=True,
        ),
    ]


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


def _show_edit_coil_menu(
    user_id: object, store: CoilSessionStore, *, from_callback: bool = False
) -> list[WizardReply]:
    session = store.get(user_id)
    store.set(user_id, {"step": STEPS.EDIT_SELECT_COIL})
    buttons: MenuKeyboard = [
        [_btn(f"Coil {idx + 1}: {coil.get('coilNumber')}", f"edit_coil:{idx}")]
        for idx, coil in enumerate(session.get("inspections") or [])
    ]
    buttons.append([_btn("Kembali ke Preview", "action:back_to_full_preview")])
    return [
        WizardReply(
            text="Pilih coil yang ingin diubah datanya:",
            buttons=buttons,
            edit=from_callback,
        )
    ]


def _show_edit_field_menu(
    user_id: object,
    coil_index: int,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    session = store.get(user_id)
    inspections = session.get("inspections") or []
    if not (0 <= coil_index < len(inspections)):
        return _show_full_preview(user_id, store, from_callback=from_callback)
    target = inspections[coil_index]
    store.set(
        user_id,
        {"step": STEPS.EDIT_SELECT_FIELD, "editTarget": {"coilIndex": coil_index}},
    )
    buttons: MenuKeyboard = [
        [_btn("Grade", "edit_field:grade"), _btn("Cacat Utama", "edit_field:defect")],
        [_btn("Remark", "edit_field:remark"), _btn("Panjang", "edit_field:length")],
        [
            _btn("Diameter", "edit_field:diameter"),
            _btn("Kembali", "action:back_to_full_preview"),
        ],
    ]
    return [
        WizardReply(
            text=(
                f"Edit data untuk *Coil {coil_index + 1} "
                f"({target.get('coilNumber')})*:\nPilih bagian yang ingin diubah:"
            ),
            buttons=buttons,
            markdown=True,
            edit=from_callback,
        )
    ]


def _prompt_edit_value(
    user_id: object,
    field: str,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    session = store.get(user_id)
    edit_target = session.get("editTarget") or {}
    coil_index = edit_target.get("coilIndex", 0)
    inspections = session.get("inspections") or []
    coil = inspections[coil_index] if 0 <= coil_index < len(inspections) else {}
    coil_number = coil.get("coilNumber", "?")

    store.set(
        user_id,
        {
            "step": STEPS.EDIT_INPUT_VALUE,
            "editTarget": {"coilIndex": coil_index, "field": field},
        },
    )

    if field == "grade":
        return [
            WizardReply(
                text=f"Pilih Grade baru untuk `{coil_number}`:",
                buttons=[
                    [_btn(g, f"edit_grade_val:{g}") for g in VALID_GRADES],
                    [_btn("Batal Edit", "action:back_to_full_preview")],
                ],
                markdown=True,
                edit=from_callback,
            )
        ]

    if field == "diameter":
        prompt = get_diameter_prompt(session.get("machine"))
        buttons: MenuKeyboard = [
            [_btn(opt.label, f"edit_diameter_val:{opt.value}")]
            for opt in prompt.options
        ]
        buttons.append([_btn("Batal Edit", "action:back_to_full_preview")])
        return [
            WizardReply(
                text=f"Ubah diameter untuk `{coil_number}`:\n{prompt.question}",
                buttons=buttons,
                markdown=True,
                edit=from_callback,
            )
        ]

    if field == "defect":
        return [
            WizardReply(
                text=f"Masukkan Cacat Utama baru untuk `{coil_number}` (contoh: B22):",
                markdown=True,
                edit=from_callback,
            )
        ]

    if field == "remark":
        return [
            WizardReply(
                text=f"Masukkan Remark baru untuk `{coil_number}` (ketik `-` jika kosong):",
                buttons=[[_btn("Tanpa Remark (-)", "edit_remark_val:default")]],
                markdown=True,
                edit=from_callback,
            )
        ]

    if field == "length":
        return [
            WizardReply(
                text=f"Masukkan Panjang baru dalam meter untuk `{coil_number}` (contoh: 955):",
                markdown=True,
                edit=from_callback,
            )
        ]

    if field == "specification":
        return [
            WizardReply(
                text="Masukkan Spesifikasi baru (contoh: 1.24*1524):",
                markdown=True,
                edit=from_callback,
            )
        ]

    return _show_full_preview(user_id, store, from_callback=from_callback)


def _handle_edit_value_input(
    user_id: object, text: str, store: CoilSessionStore
) -> list[WizardReply]:
    session = store.get(user_id)
    edit_target = session.get("editTarget") or {}
    coil_index = edit_target.get("coilIndex", 0)
    field = edit_target.get("field")

    if field == "specification":
        check = validate_specification(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        store.set(user_id, {"specification": check.value})
        return [
            WizardReply(
                text=f"✅ Spesifikasi berhasil diperbarui menjadi `{check.value}`.",
                markdown=True,
            ),
            *_show_full_preview(user_id, store),
        ]

    inspections = list(session.get("inspections") or [])
    if not (0 <= coil_index < len(inspections)):
        return _show_full_preview(user_id, store)
    target = {**inspections[coil_index]}

    if field == "defect":
        check = validate_main_defect(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        target["mainDefect"] = check.value
    elif field == "remark":
        check = validate_remark(text)
        target["remark"] = check.value
    elif field == "length":
        check = validate_length(text)
        if not check.valid:
            return [WizardReply(text=check.error)]
        target["length"] = check.value

    inspections[coil_index] = target
    store.set(user_id, {"inspections": inspections})
    return [
        WizardReply(
            text=f"✅ Data {field} untuk `{target.get('coilNumber')}` berhasil diperbarui.",
            markdown=True,
        ),
        *_show_full_preview(user_id, store),
    ]


def _handle_edit_callback_value(
    user_id: object,
    field: str,
    value: str,
    store: CoilSessionStore,
    *,
    from_callback: bool = False,
) -> list[WizardReply]:
    session = store.get(user_id)
    edit_target = session.get("editTarget") or {}
    coil_index = edit_target.get("coilIndex", 0)
    inspections = list(session.get("inspections") or [])
    if not (0 <= coil_index < len(inspections)):
        return _show_full_preview(user_id, store, from_callback=from_callback)
    target = {**inspections[coil_index]}

    if field == "grade":
        target["grade"] = value
    elif field == "diameter":
        resolved = resolve_diameter(session.get("machine"), value)
        target["diameter"] = resolved.diameter
        target["changeDiameter"] = resolved.change_diameter
    elif field == "remark":
        target["remark"] = "-"

    inspections[coil_index] = target
    store.set(user_id, {"inspections": inspections})
    return _show_full_preview(user_id, store, from_callback=from_callback)


# ---------------------------------------------------------------------------
# Dispatcher callback (port dari handler callback_query:data di bot.js)
# ---------------------------------------------------------------------------


def _material_table_text() -> str:
    lines = [f"• Kode *{code}* ➔ *{name}*" for code, name in MATERIAL_MAP.items()]
    return "*TABEL REFERENSI MATERIAL QM-YWI*\n\n" + "\n".join(lines)


def _session_active(store: CoilSessionStore, user_id: object) -> bool:
    return store.get(user_id).get("step") not in (None, STEPS.IDLE)


def handle_callback(
    user_id: object, data: str, store: CoilSessionStore
) -> list[WizardReply]:
    """Routing callback_data -> aksi wizard. Dipicu oleh tap tombol."""
    data = data or ""

    # Stateless: tidak butuh sesi wizard aktif.
    if data == "cmd:material":
        return [WizardReply(text=_material_table_text(), markdown=True)]
    if data == "cmd:help":
        return [
            WizardReply(
                text="Ketik /help untuk panduan lengkap atau /new untuk memulai form baru."
            )
        ]
    if data == "action:new_form":
        return start_new_wizard(user_id, store, from_callback=True)
    if data == "action:cancel":
        return cancel_wizard(user_id, store)

    # Sisanya butuh sesi wizard aktif.
    if not _session_active(store, user_id):
        return [
            WizardReply(
                text="Sesi tidak aktif. Ketik /new untuk mulai membuat form."
            )
        ]

    if data.startswith("machine:"):
        return _handle_machine_selection_cb(user_id, data, store)
    if data == "action:back_to_machine":
        return start_new_wizard(user_id, store, from_callback=True)
    if data == "action:confirm_material":
        return _confirm_material(user_id, store)
    if data == "action:edit_source_coil":
        store.set(user_id, {"step": STEPS.INPUT_SOURCE_COIL})
        return [
            WizardReply(
                text="Silakan masukkan kembali nomor gulungan asal:\n"
                "(Contoh: `QH2608K2531HA10`)",
                buttons=[_cancel_row()],
                markdown=True,
                edit=True,
            )
        ]
    if data == "action:confirm_numbering":
        return _confirm_numbering(user_id, store)
    if data == "action:edit_numbering":
        store.set(user_id, {"step": STEPS.INPUT_COUNT})
        return [
            WizardReply(
                text="Silakan masukkan kembali jumlah gulungan yang akan dibuat:\n"
                "(Contoh: `3`)",
                buttons=[_cancel_row()],
                markdown=True,
                edit=True,
            )
        ]
    if data.startswith("grade:"):
        return _handle_grade_selection(
            user_id, data.split(":", 1)[1], store, from_callback=True
        )
    if data == "remark:default":
        return _handle_default_remark(user_id, store, from_callback=True)
    if data.startswith("diameter:"):
        return _handle_diameter_selection(
            user_id, data.split(":", 1)[1], store, from_callback=True
        )
    if data == "action:generate_final":
        return _generate_final_output(user_id, store, from_callback=True)
    if data == "edit:source_coil":
        store.set(user_id, {"step": STEPS.INPUT_SOURCE_COIL})
        return [
            WizardReply(
                text="Silakan masukkan nomor gulungan asal baru:\n"
                "(Contoh: `QH2608K2531HA10`)",
                markdown=True,
            )
        ]
    if data == "edit:specification":
        return _prompt_edit_value(user_id, "specification", store, from_callback=True)
    if data == "edit:select_coil":
        return _show_edit_coil_menu(user_id, store, from_callback=True)
    if data.startswith("edit_coil:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            idx = 0
        return _show_edit_field_menu(user_id, idx, store, from_callback=True)
    if data.startswith("edit_field:"):
        return _prompt_edit_value(
            user_id, data.split(":", 1)[1], store, from_callback=True
        )
    if data.startswith("edit_grade_val:"):
        return _handle_edit_callback_value(
            user_id, "grade", data.split(":", 1)[1], store, from_callback=True
        )
    if data.startswith("edit_diameter_val:"):
        return _handle_edit_callback_value(
            user_id, "diameter", data.split(":", 1)[1], store, from_callback=True
        )
    if data == "edit_remark_val:default":
        return _handle_edit_callback_value(
            user_id, "remark", "-", store, from_callback=True
        )
    if data == "action:back_to_full_preview":
        return _show_full_preview(user_id, store, from_callback=True)

    return [WizardReply(text="Perintah tidak dikenali. Ketik /new untuk mulai lagi.")]


def _handle_machine_selection_cb(
    user_id: object, data: str, store: CoilSessionStore
) -> list[WizardReply]:
    machine = data.split(":", 1)[1]
    return handle_machine_selection(user_id, machine, store, from_callback=True)


def _confirm_material(
    user_id: object, store: CoilSessionStore
) -> list[WizardReply]:
    session = store.get(user_id)
    store.set(user_id, {"step": STEPS.INPUT_SPECIFICATION})
    return [
        WizardReply(
            text=(
                f"Nomor Gulungan: `{session.get('sourceCoil')}`\n"
                f"Material: *{session.get('material')}*\n\n"
                "Silakan masukkan spesifikasi asal gulungan:\n"
                "(Contoh: `1.24*1524`)"
            ),
            buttons=[_cancel_row()],
            markdown=True,
            edit=True,
        )
    ]


def _confirm_numbering(
    user_id: object, store: CoilSessionStore
) -> list[WizardReply]:
    session = store.get(user_id)
    coils = session.get("generatedCoils") or []
    if not coils:
        return [WizardReply(text="Data penomoran belum ada. Ketik /new untuk mulai lagi.")]
    store.set(
        user_id,
        {
            "step": STEPS.INPUT_COIL_GRADE,
            "currentCoilIndex": 0,
            "currentCoilData": {"coilNumber": coils[0]},
            "inspections": [],
        },
    )
    grade_buttons: MenuKeyboard = [
        [_btn(g, f"grade:{g}") for g in VALID_GRADES],
        _cancel_row(),
    ]
    return [
        WizardReply(
            text=(
                "Penomoran dikonfirmasi!\n\n"
                "Lanjut ke pengisian data inspeksi:\n"
                f"[Coil 1 / {len(coils)}]: `{coils[0]}`\n"
                "Silakan pilih Grade:"
            ),
            buttons=grade_buttons,
            markdown=True,
            edit=True,
        )
    ]


# ---------------------------------------------------------------------------
# Kompatibilitas: kelas pembungkus untuk router lama (stub diganti fungsi penuh)
# ---------------------------------------------------------------------------


class CoilWizard:
    """Adapter: bungkus fungsi wizard agar cocok dengan antarmuka router.

    Setiap user punya ``CoilSessionStore`` sendiri; balasan dikonversi
    menjadi ``OutgoingMessage`` (label tombol diratakan, markdown
    diteruskan via flag).
    """

    def __init__(self, store: CoilSessionStore | None = None) -> None:
        from qm_coil.state import CoilSessionStore as _Store

        self.store = store or _Store()
        # label tombol -> callback_data dari keyboard terakhir per user
        self._callback_map: dict[str, dict[str, str]] = {}

    def handle(self, message) -> list:
        from qm_training.bot.adapters.base import OutgoingMessage

        from qm_coil.menu import to_reply_buttons

        user_id = message.user_id
        text = (message.text or "").strip()

        replies: list[WizardReply]
        callback_map = self._callback_map.get(str(user_id), {})
        if text in callback_map:
            replies = handle_callback(user_id, callback_map[text], self.store)
        elif text in ("/new", "mulai", "🚀 Mulai Buat Form"):
            replies = start_new_wizard(user_id, self.store)
        elif text in ("/cancel", "❌ Batal", "Batal"):
            replies = cancel_wizard(user_id, self.store)
        else:
            session = self.store.get(user_id)
            if session.get("step") in (None, STEPS.IDLE):
                replies = start_new_wizard(user_id, self.store)
            else:
                replies = handle_text_input(user_id, text, self.store)

        out = []
        merged_map: dict[str, str] = {}
        for reply in replies:
            buttons = to_reply_buttons(reply.buttons)
            for row in reply.buttons:
                for label, data in row:
                    merged_map[label] = data
            out.append(
                OutgoingMessage(
                    text=reply.text, buttons=buttons, markdown=reply.markdown
                )
            )
        if merged_map:
            self._callback_map[str(user_id)] = merged_map
        return out
