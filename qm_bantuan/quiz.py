"""Latihan kilat: kuis pilihan ganda tingkat & grade cacat.

Soal dibangkitkan data-driven dari atlas (via :class:`Atlas`); tidak ada
nama cacat, kriteria, atau grade yang di-hardcode di sini. Update standar
cukup mengganti ``qm_bantuan/data/atlas.json``.
"""

from __future__ import annotations

import random

from qm_bantuan.data import LEVEL_NAMES, Atlas

# Hanya tingkat yang gradenya kode tunggal resmi yang boleh dipakai
# (grade kondisional seperti "A1 (bila ...) / B ..." dan TIDAK_DIIZINKAN
# dilewati agar opsi kuis tidak ambigu).
QUIZ_GRADES = {"A", "A1", "B", "B1", "C", "R", "F", "S"}

ARROW = "→"  # U+2192
DASH = "—"  # U+2014

_NO_QUESTION = "Belum ada soal aktif. Minta soal dulu sebelum menjawab."


class Quiz:
    """Satu sesi kuis pilihan ganda (1 sesi = 1 user)."""

    def __init__(self, atlas: Atlas, n_questions: int = 5,
                 rng: random.Random | None = None) -> None:
        self._atlas = atlas
        self._n = max(0, int(n_questions))
        self._rng = rng if rng is not None else random
        self._score = 0
        self._answered = 0
        self._asked_codes: set[str] = set()
        self._active: dict | None = None  # soal yang menunggu jawaban

        # Kandidat soal: tiap varian yang punya levels jadi kandidat
        # terpisah; bila entri tidak punya varian, entrinya sendiri.
        # Kandidat tanpa satu pun tingkat bergrade tunggal dilewati.
        self._candidates: list[tuple[dict, dict | None]] = []
        for entry in atlas.entries:
            variants = [v for v in Atlas.variants(entry)
                        if Atlas.levels_of(entry, v)]
            if variants:
                for variant in variants:
                    cand = (entry, variant)
                    if self._quiz_levels(cand):
                        self._candidates.append(cand)
            else:
                cand = (entry, None)
                if self._quiz_levels(cand):
                    self._candidates.append(cand)

    # -- status ------------------------------------------------------- #

    @property
    def score(self) -> int:
        return self._score

    @property
    def answered(self) -> int:
        return self._answered

    @property
    def done(self) -> bool:
        return self._answered >= self._n

    # -- soal ---------------------------------------------------------- #

    def next_question(self) -> dict | None:
        """Soal berikutnya, atau None bila sesi selesai/tak ada soal layak."""
        if self.done:
            return None
        pool = [c for c in self._candidates
                if c[0].get("code") not in self._asked_codes]
        self._rng.shuffle(pool)
        for cand in pool:
            question = self._build_question(cand)
            if question is not None:
                # Kode yang sudah ditanyakan tidak diulang dalam sesi ini.
                self._asked_codes.add(question["code"])
                self._active = question
                return question
        return None

    def answer(self, choice: str) -> tuple[bool, str]:
        """Jawab soal aktif. Mengembalikan (benar?, feedback)."""
        question = self._active
        if question is None:
            return False, _NO_QUESTION
        self._active = None
        self._answered += 1
        level_name = LEVEL_NAMES.get(question["level"], "")
        if (choice or "").strip() == question["answer"]:
            self._score += 1
            return True, (
                f"✅ Benar! {question['code']} tingkat {question['level']} "
                f"({level_name}) {ARROW} grade {question['grade']}."
            )
        return False, (
            f"❌ Kurang tepat. Jawaban yang benar: {question['level']} "
            f"{ARROW} {question['grade']} ({question['code']}, "
            f"tingkat {level_name})."
        )

    # -- bangun soal --------------------------------------------------- #

    @staticmethod
    def _level_info(cand: tuple[dict, dict | None], level: str) -> dict:
        entry, variant = cand
        return Atlas.levels_of(entry, variant).get(level) or {}

    def _level_grade(self, cand: tuple[dict, dict | None], level: str) -> str | None:
        return self._level_info(cand, level).get("grade")

    def _quiz_levels(self, cand: tuple[dict, dict | None]) -> list[str]:
        """Tingkat yang layak jadi soal: terurut L->M->H->S, grade tunggal."""
        entry, variant = cand
        return [lv for lv in Atlas.ordered_levels(entry, variant)
                if self._level_grade(cand, lv) in QUIZ_GRADES]

    def _build_question(self, cand: tuple[dict, dict | None]) -> dict | None:
        entry, variant = cand
        levels = self._quiz_levels(cand)
        self._rng.shuffle(levels)
        for level in levels:
            options, answer = self._make_options(cand, level)
            if options is None:
                continue
            code = entry.get("code", "")
            title = f"{code} {DASH} {Atlas.display_name(entry)}"
            variant_jenis = variant.get("jenis") if variant else None
            desc = (self._level_info(cand, level).get("desc") or "").strip()
            prompt = f'"{title}": {desc}'
            if variant_jenis:
                prompt += f"\nVarian: {variant_jenis}"
            prompt += "\n\nTingkat & grade apa yang tepat?"
            return {
                "code": code,
                "title": title,
                "variant_jenis": variant_jenis,
                "level": level,
                "grade": self._level_grade(cand, level),
                "prompt": prompt,
                "options": options,
                "answer": answer,
            }
        return None

    def _make_options(self, cand: tuple[dict, dict | None],
                      level: str) -> tuple[list[str] | None, str | None]:
        """1 jawaban benar + 3 pengecoh unik; None bila tak bisa 4 opsi."""
        grade = self._level_grade(cand, level)
        correct = f"{level} {ARROW} {grade}"
        options = [correct]

        # Pengecoh diutamakan dari tingkat lain pada kandidat yang sama.
        others = [lv for lv in self._quiz_levels(cand) if lv != level]
        self._rng.shuffle(others)
        for lv in others:
            options = _add_unique(options, lv, self._level_grade(cand, lv))
            if len(options) == 4:
                break

        # Bila kurang, ambil dari tingkat acak kandidat lain.
        if len(options) < 4:
            foreign = [(lv, self._level_grade(c, lv))
                       for c in self._candidates if c != cand
                       for lv in self._quiz_levels(c)]
            self._rng.shuffle(foreign)
            for lv, grade_lv in foreign:
                options = _add_unique(options, lv, grade_lv)
                if len(options) == 4:
                    break

        if len(options) < 4:
            return None, None
        self._rng.shuffle(options)
        return options, correct


def _add_unique(options: list[str], level: str, grade: str | None) -> list[str]:
    """Tambah opsi 'X → grade' bila belum ada (semua opsi harus unik)."""
    text = f"{level} {ARROW} {grade}"
    if text not in options:
        options.append(text)
    return options
