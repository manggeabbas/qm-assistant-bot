"""Akses data atlas cacat CRP-YWI.

Seluruh standar cacat dibaca dari JSON saat start (data-driven); jangan
hardcode nama/kriteria/grade di kode. Update standar = ganti file
``qm_bantuan/data/atlas.json`` lalu restart bot (lihat README di folder data).
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
ATLAS_PATH = DATA_DIR / "atlas.json"

# Tahap produksi sesuai urutan alur lini.
SECTIONS: list[tuple[str, str]] = [
    ("bahan_baku", "Bahan Baku"),
    ("asam_panas", "Asam Panas"),
    ("rolling_mill", "Rolling Mill"),
    ("asam_dingin", "Asam Dingin"),
    ("penyelesaian", "Penyelesaian"),
]
SECTION_NAMES = dict(SECTIONS)

# Pembagian menu per bagian divisi (keputusan user 2026-10-18):
# Bahan Baku = urutan produksi dari bahan baku (S,F,R,W,D03,D21,D38);
# Jalur Utama = 1 rangkaian mesin (A,B,C);
# Luar Jalur = penyelesaian / mesin FT & FJ (D).
BAGIAN: list[tuple[str, str, list[str]]] = [
    ("bahan_baku", "📦 Bahan Baku", ["bahan_baku"]),
    ("jalur_utama", "🏭 Jalur Utama", ["asam_panas", "rolling_mill", "asam_dingin"]),
    ("luar_jalur", "🔧 Luar Jalur", ["penyelesaian"]),
]
BAGIAN_NAMES = {b[0]: b[1] for b in BAGIAN}
BAGIAN_SECTIONS = {b[0]: b[2] for b in BAGIAN}

# Urutan tingkat keparahan: L -> M -> H -> S (keputusan user, jangan diubah).
LEVEL_ORDER = ["L", "M", "H", "S"]
LEVEL_NAMES = {"L": "Ringan", "M": "Sedang", "H": "Parah", "S": "Serius"}

GRADE_NAMES = {
    "A": "Kualitas A",
    "A1": "Kualitas A1",
    "B": "Kualitas B",
    "B1": "Kualitas B1",
    "C": "Giling Ulang",
    "R": "Digulung Ulang",
    "F": "Diiris Samping",
    "S": "Pembuangan",
    "TIDAK_DIIZINKAN": "Tidak diizinkan",
}

# Grade yang berupa kode tunggal (bisa dipakai untuk opsi kuis).
PLAIN_GRADES = set(GRADE_NAMES)


def _norm_code(code: str) -> str:
    return (code or "").strip().upper()


class Atlas:
    """Bungkus atlas.json: cari per kode, kata kunci, atau tahap."""

    def __init__(self, path: str | Path | None = None) -> None:
        path = Path(path) if path else ATLAS_PATH
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self._entries: list[dict] = list(raw.get("defects", []))
        self._by_code = {_norm_code(e.get("code", "")): e for e in self._entries}
        self.meta = raw.get("meta", {})

    @classmethod
    def bundled(cls) -> "Atlas":
        return cls(ATLAS_PATH)

    @classmethod
    def _from_entries(cls, entries: list[dict], meta: dict) -> "Atlas":
        obj = cls.__new__(cls)
        obj._entries = list(entries)
        obj._by_code = {_norm_code(e.get("code", "")): e for e in obj._entries}
        obj.meta = dict(meta)
        return obj

    def scoped(self, sections: list[str]) -> "Atlas":
        """Atlas baru yang hanya berisi entri dari seksi-seksi berikut."""
        wanted = set(sections)
        return self._from_entries(
            [e for e in self._entries if e.get("section") in wanted], self.meta
        )

    @property
    def entries(self) -> list[dict]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def codes(self) -> list[str]:
        return [e["code"] for e in self._entries]

    # -- lookup -------------------------------------------------------- #

    def get(self, code: str) -> dict | None:
        """Entri per kode cacat (case-insensitive, mis. 'c11' -> 'C11')."""
        return self._by_code.get(_norm_code(code))

    def by_section(self, section: str) -> list[dict]:
        return [e for e in self._entries if e.get("section") == section]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Cari kode/nama. Urutan: kode persis > awalan kode > nama > kode mengandung."""
        q = (query or "").strip()
        if not q:
            return []
        qu = q.upper()
        ql = q.lower()

        exact = self.get(qu)
        hits: list[dict] = []
        if exact:
            hits.append(exact)

        def _name(e: dict) -> str:
            return f"{e.get('name_id') or ''} {e.get('name_cn') or ''}".lower()

        prefix = [e for e in self._entries if e["code"].upper().startswith(qu) and e not in hits]
        name_hits = [e for e in self._entries if ql in _name(e) and e not in hits and e not in prefix]
        code_contains = [
            e for e in self._entries
            if qu in e["code"].upper() and e not in hits and e not in prefix and e not in name_hits
        ]
        hits.extend(prefix)
        hits.extend(name_hits)
        hits.extend(code_contains)
        return hits[:limit]

    # -- bentuk entri --------------------------------------------------- #

    @staticmethod
    def variants(entry: dict) -> list[dict]:
        return list(entry.get("variants") or [])

    @staticmethod
    def levels_of(entry: dict, variant: dict | None = None) -> dict:
        target = variant if variant is not None else entry
        return dict(target.get("levels") or {})

    @classmethod
    def ordered_levels(cls, entry: dict, variant: dict | None = None) -> list[str]:
        """Tingkat yang ada, selalu terurut L -> M -> H -> S."""
        levels = cls.levels_of(entry, variant)
        return [lv for lv in LEVEL_ORDER if lv in levels]

    @classmethod
    def has_criteria(cls, entry: dict, variant: dict | None = None) -> bool:
        """Punya kriteria tingkat (bukan sekadar aturan/nama)."""
        if variant is not None:
            return bool(cls.levels_of(entry, variant))
        if cls.levels_of(entry):
            return True
        return any(cls.levels_of(entry, v) for v in cls.variants(entry))

    @staticmethod
    def has_rule(entry: dict) -> bool:
        return bool((entry.get("rule") or "").strip())

    @staticmethod
    def display_name(entry: dict) -> str:
        """Nama Indonesia; bila kosong pakai Mandarin (jangan karang)."""
        return entry.get("name_id") or entry.get("name_cn") or entry.get("code", "")


PANDUAN_PATH = DATA_DIR / "panduan.json"


class Panduan:
    """Bungkus panduan.json: topik panduan kerja (data-driven, tanpa hardcode).

    Skema tiap topik: {"id", "emoji", "judul", "isi" (markdown),
    opsional "grup" (mis. "🔧 Mesin FT" untuk menu Prosedur Kerja)}.
    Update isi = ganti file panduan.json lalu restart bot.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        path = Path(path) if path else PANDUAN_PATH
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self._topics: list[dict] = list(raw.get("topics", []))
        self._by_id = {str(t.get("id", "")): t for t in self._topics}

    @classmethod
    def bundled(cls) -> "Panduan":
        return cls(PANDUAN_PATH)

    def topics(self) -> list[dict]:
        return list(self._topics)

    def get(self, topic_id: str) -> dict | None:
        return self._by_id.get(str(topic_id or "").strip())

    def groups(self) -> list[str]:
        """Daftar grup prosedur (mis. '🔧 Mesin FT'), sesuai urutan kemunculan."""
        seen: list[str] = []
        for t in self._topics:
            g = (t.get("grup") or "").strip()
            if g and g not in seen:
                seen.append(g)
        return seen

    def by_group(self, grup: str) -> list[dict]:
        return [t for t in self._topics if (t.get("grup") or "").strip() == grup]

    def search(self, query: str, limit: int = 6) -> list[dict]:
        """Cari topik yang judul/isi-nya memuat kata kunci (semua kata)."""
        q = (query or "").strip().lower()
        if not q:
            return []
        words = q.split()
        out = []
        for t in self._topics:
            hay = f"{t.get('judul', '')}\n{t.get('isi', '')}".lower()
            if all(w in hay for w in words):
                out.append(t)
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def label(topic: dict) -> str:
        return f"{topic.get('emoji', '📘')} {topic.get('judul', '')}".strip()
