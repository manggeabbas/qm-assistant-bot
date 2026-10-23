"""Format kartu jawaban Bantuan QC (ringkas, scannable, keputusan di depan).

Aturan perilaku bot (VERIFIKASI.md):
- entri tanpa kriteria -> tampilkan pengertian ID + Mandarin; untuk kriteria
  jawab "database belum ada" (jangan mengarang);
- urutan tingkat selalu L -> M -> H -> S.
"""

from __future__ import annotations

from qm_bantuan.data import (
    GRADE_NAMES,
    LEVEL_NAMES,
    SECTION_NAMES,
    Atlas,
)

_GRADE_LEGEND = (
    "Kualitas: A/A1/B/B1 = lolos bertingkat · "
    "C = Giling Ulang · R = Digulung Ulang · "
    "F = Diiris Samping · S = Pembuangan"
)

# Emoji sub-topik: warna mengikuti keparahan tingkat.
_LEVEL_EMOJI = {"L": "🟢", "M": "🟡", "H": "🟠", "S": "🔴"}


def _pre(text: str) -> str:
    """Blok monospace = highlight penjelasan (kotak abu-abu, aman dari
    backtick di teks).

    Catatan: aplikasi Telegram kadang memunculkan tombol COPY CODE pada
    blok ``` — itu perilaku aplikasi (tidak bisa dimatikan dari bot) dan
    tidak mengganggu. Format blok dipertahankan karena paling rapi untuk
    kartu cacat. Form generator (qm_coil) memakai blok ```text``` sendiri.
    """
    clean = text.replace("```", "").replace("`", "")
    return f"```\n{clean}\n```"


def grade_label(grade: str) -> str:
    """'C' -> 'C (Giling Ulang)'; grade tak dikenal dikembalikan apa adanya."""
    name = GRADE_NAMES.get(grade)
    return f"{grade} ({name})" if name and grade not in ("A", "A1", "B", "B1") else grade


def _header(entry: dict, variant: dict | None = None) -> str:
    name = Atlas.display_name(entry)
    cn = entry.get("name_cn") or ""
    section = SECTION_NAMES.get(entry.get("section", ""), entry.get("section", ""))
    title = f"🔍 *{entry['code']}* — {name}"
    if variant:
        title += f" · {variant.get('jenis') or ''}".rstrip()
    sub = " · ".join(p for p in (cn, section) if p and p != name)
    return f"{title}\n{sub}" if sub else title


def _cn_line(cn_text: str | None) -> str:
    """Baris Mandarin pendamping (tetap ditampilkan di samping terjemahan)."""
    cn = (cn_text or "").strip()
    return f"🇨🇳 _{cn}_" if cn else ""


def _handling_block(entry: dict) -> str:
    """Blok penanganan di bawah sub-topik 📏: isi penjelasan masuk satu
    box (konsisten dengan kriteria tingkat); baris Mandarin tetap di luar
    sebagai anotasi miring, sama seperti pola kriteria."""
    items = []
    rule = (entry.get("rule") or "").strip()
    if rule:
        items.append(f"Aturan: {rule}")
    notes = (entry.get("notes") or "").strip()
    if notes:
        items.append(f"Catatan: {notes}")
    sup = (entry.get("superseded_note") or "").strip()
    if sup:
        items.append(f"⚠️ {sup}")
    if not items:
        return ""
    out = ["📏 *Penanganan:*", _pre("\n".join(items))]
    for key in ("notes_cn", "rule_cn"):
        cn = _cn_line(entry.get(key))
        if cn:
            out.append(cn)
    return "\n".join(out)


def defect_card(entry: dict, variant: dict | None = None) -> str:
    """Kartu lengkap satu cacat (markdown). Grade/keputusan selalu di depan."""
    lines = [_header(entry, variant), ""]

    if Atlas.has_criteria(entry, variant):
        lines.append("📋 *Kriteria tingkat:*")
        for lv in Atlas.ordered_levels(entry, variant):
            lvl = Atlas.levels_of(entry, variant)[lv]
            desc = (lvl.get("desc") or "").strip()
            grade = (lvl.get("grade") or "").strip()
            emoji = _LEVEL_EMOJI.get(lv, "•")
            lines.append(f"{emoji} *{lv}* ({LEVEL_NAMES[lv]}) → *{grade_label(grade)}*")
            if desc:
                lines.append(_pre(desc))
                cn = _cn_line(lvl.get("desc_cn"))
                if cn:
                    lines.append(cn)
        lines.append("")
        lines.append(f"ℹ️ {_GRADE_LEGEND}")
        handling = _handling_block(entry)
        if handling:
            lines.append("")
            lines.append(handling)
    else:
        # Tanpa kriteria: pengertian saja + "database belum ada" (jangan karang).
        handling = _handling_block(entry)
        if handling:
            lines.append(handling)
            lines.append("")
        lines.append("ℹ️ Kriteria tingkat: *database belum ada*.")

    return "\n".join(lines).strip()


def variant_summary(entry: dict) -> str:
    """Ringkasan varian Jenis (satu baris per varian: tingkat → grade)."""
    lines = [_header(entry), "", "📑 *Varian jenis:*"]
    for i, v in enumerate(Atlas.variants(entry)):
        pairs = ", ".join(
            f"{lv}→{Atlas.levels_of(entry, v)[lv].get('grade', '?')}"
            for lv in Atlas.ordered_levels(entry, v)
        )
        lines.append(f"{i + 1}. {v.get('jenis') or f'Jenis {i + 1}'}: {pairs or '—'}")
    lines.append("")
    lines.append("👉 Pilih jenis untuk melihat kriteria lengkap.")
    return "\n".join(lines).strip()


def search_line(entry: dict) -> str:
    """Satu baris hasil pencarian: 'C11 · Tergores (Asam Dingin)'."""
    section = SECTION_NAMES.get(entry.get("section", ""), "")
    label = f"{entry['code']} · {Atlas.display_name(entry)}"
    return f"{label} ({section})" if section else label


def section_line(entry: dict) -> str:
    return f"{entry['code']} · {Atlas.display_name(entry)}"
