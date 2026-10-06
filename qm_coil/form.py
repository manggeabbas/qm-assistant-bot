"""Format output Mandarin workplace dan preview form QM-YWI.

Port dari: ``src/form.js`` (99 baris, qm-ywi-telegram-bot).
Status: PORTED (termasuk test, dari test/form.test.js).

CATATAN: ``format_full_preview`` mempertahankan format Markdown aslinya
(``*tebal*``, `` `kode` ``) seperti di bot JS (grammy memakai
``parse_mode: "Markdown"``). Adapter Telegram di repo ini mengirim teks
biasa, jadi saat wizard di-port, lapisan UI yang memutuskan render-nya.
"""

from __future__ import annotations

from typing import Mapping


def format_numbering_preview(coils: list[str], material: str) -> str:
    """Preview nomor gulungan yang akan dibuat (PRD Section 9)."""
    lines = ["Nomor gulungan yang akan dibuat:\n"]
    for idx, coil in enumerate(coils, start=1):
        lines.append(f"{idx}. {coil}")
    lines.append(f"\nMaterial: {material}")
    return "\n".join(lines)


def generate_workplace_mandarin_output(state: Mapping) -> str:
    """Output teks final standar Mandarin Workplace (PRD Section 13).

    ``state``: mapping dengan kunci ``machine``, ``sourceCoil``,
    ``material``, ``specification``, ``inspections`` (list mapping dengan
    kunci ``coilNumber``, ``grade``, ``mainDefect``, ``remark``,
    ``diameter``, ``changeDiameter``, ``length``).
    """
    machine = state["machine"]
    source_coil = state["sourceCoil"]
    material = state["material"]
    specification = state["specification"]
    inspections = state["inspections"]

    header = "\n".join([f"机组：{machine}", f"{source_coil}", "要生成新卷号"])

    blocks = []
    for item in inspections:
        remark = item.get("remark", "")
        remark = remark.strip() if isinstance(remark, str) and remark.strip() else "-"
        blocks.append(
            "\n".join(
                [
                    f"{item['coilNumber']}",
                    f"{material}",
                    f"{specification}",
                    f"等级: {item['grade']}",
                    f"主缺陷: {item['mainDefect']}",
                    f"备注: {remark}",
                    f"目前内径: {item['diameter']}",
                    f"是否需改内径: {item['changeDiameter']}",
                    f"长度: {item['length']}米",
                ]
            )
        )

    return f"{header}\n\n" + "\n\n".join(blocks)


def format_full_preview(state: Mapping) -> str:
    """Preview seluruh form dalam Bahasa Indonesia sebelum konfirmasi (PRD Section 12)."""
    lines = [
        "📋 *PREVIEW DATA INSPEKSI QM-YWI*",
        "----------------------------------------",
        f"*Mesin:* {state['machine']}",
        f"*Gulungan Asal:* `{state['sourceCoil']}`",
        f"*Material:* {state['material']} ({state['materialCode']})",
        f"*Spesifikasi:* `{state['specification']}`",
        f"*Jumlah Gulungan:* {state['count']} coil",
        "----------------------------------------",
    ]

    for index, item in enumerate(state["inspections"], start=1):
        lines.append(f"\n🔹 *Coil {index}: `{item['coilNumber']}`*")
        lines.append(f"• Grade: *{item['grade']}*")
        lines.append(f"• Cacat Utama: *{item['mainDefect']}*")
        lines.append(f"• Remark: *{item.get('remark') or '-'}*")
        lines.append(f"• Diameter Dalam: *{item['diameter']}*")
        lines.append(f"• Ubah Diameter: *{item['changeDiameter']}*")
        lines.append(f"• Panjang: *{item['length']}米*")

    lines.append("\n----------------------------------------")
    lines.append("Periksa seluruh data di atas. Apakah data sudah benar?")

    return "\n".join(lines)
