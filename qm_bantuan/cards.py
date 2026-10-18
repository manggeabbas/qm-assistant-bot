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
    "Grade: A/A1/B/B1 = lolos bertingkat · "
    "C = Giling Ulang · R = Digulung Ulang · "
    "F = Diiris Samping · S = Pembuangan"
)


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


def _handling_notes(entry: dict) -> str:
    parts = []
    rule = (entry.get("rule") or "").strip()
    if rule:
        parts.append(f"📏 Aturan: {rule}")
    notes = (entry.get("notes") or "").strip()
    if notes:
        parts.append(f"📌 Catatan: {notes}")
    sup = (entry.get("superseded_note") or "").strip()
    if sup:
        parts.append(f"⚠️ {sup}")
    return "\n".join(parts)


def defect_card(entry: dict, variant: dict | None = None) -> str:
    """Kartu lengkap satu cacat (markdown). Grade/keputusan selalu di depan."""
    lines = [_header(entry, variant), ""]

    if Atlas.has_criteria(entry, variant):
        for lv in Atlas.ordered_levels(entry, variant):
            lvl = Atlas.levels_of(entry, variant)[lv]
            desc = (lvl.get("desc") or "").strip()
            grade = (lvl.get("grade") or "").strip()
            lines.append(f"*{lv}* ({LEVEL_NAMES[lv]}) → *{grade_label(grade)}*")
            if desc:
                lines.append(f"  {desc}")
        lines.append("")
        lines.append(_GRADE_LEGEND)
    else:
        # Tanpa kriteria: pengertian saja + "database belum ada" (jangan karang).
        if Atlas.has_rule(entry):
            lines.append(f"📏 Aturan: {(entry.get('rule') or '').strip()}")
            lines.append("")
        lines.append("ℹ️ Kriteria tingkat: *database belum ada*.")

    notes = _handling_notes(entry)
    # _handling_notes sudah mencakup rule; hindari duplikasi untuk kasus berkriteria.
    if Atlas.has_criteria(entry, variant):
        if notes:
            lines.append("")
            lines.append(notes)
    elif Atlas.has_rule(entry):
        extra = "\n".join(
            p
            for p in notes.split("\n")
            if not p.startswith("📏 Aturan:")
        )
        if extra:
            lines.append("")
            lines.append(extra)

    return "\n".join(lines).strip()


def variant_summary(entry: dict) -> str:
    """Ringkasan varian Jenis (satu baris per varian: tingkat → grade)."""
    lines = [_header(entry), ""]
    for i, v in enumerate(Atlas.variants(entry)):
        pairs = ", ".join(
            f"{lv}→{Atlas.levels_of(entry, v)[lv].get('grade', '?')}"
            for lv in Atlas.ordered_levels(entry, v)
        )
        lines.append(f"{i + 1}. {v.get('jenis') or f'Jenis {i + 1}'}: {pairs or '—'}")
    lines.append("")
    lines.append("Pilih jenis untuk melihat kriteria lengkap.")
    return "\n".join(lines).strip()


def search_line(entry: dict) -> str:
    """Satu baris hasil pencarian: 'C11 · Tergores (Asam Dingin)'."""
    section = SECTION_NAMES.get(entry.get("section", ""), "")
    label = f"{entry['code']} · {Atlas.display_name(entry)}"
    return f"{label} ({section})" if section else label


def section_line(entry: dict) -> str:
    return f"{entry['code']} · {Atlas.display_name(entry)}"
