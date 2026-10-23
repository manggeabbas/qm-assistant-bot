"""Konversi teks Mandarin ke pinyin (bantuan baca, nada ditandai diakritik).

Dipakai untuk setiap teks Mandarin yang ditampilkan bot (nama, kriteria,
aturan, catatan di kartu cacat). Untuk aksara yang punya banyak bacaan
dipakai bacaan default pypinyin — cukup sebagai bantuan baca, bukan
rujukan pelafalan resmi.

Bila pypinyin belum terpasang (mis. salinan bot di HP yang belum update
dependency), fungsi mengembalikan string kosong sehingga kartu tetap tampil
tanpa pinyin, bukan error.
"""

from __future__ import annotations

try:
    from pypinyin import Style
    from pypinyin import pinyin as _pinyin
except ImportError:  # pragma: no cover - dependency belum terpasang
    _pinyin = None


def to_pinyin(text: str | None) -> str:
    """'划伤' -> 'huà shāng'; teks kosong/None -> ''."""
    if not text or _pinyin is None:
        return ""
    return " ".join(group[0] for group in _pinyin(text, style=Style.TONE))
