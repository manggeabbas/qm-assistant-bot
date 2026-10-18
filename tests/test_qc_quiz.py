"""Tests untuk latihan kilat Bantuan QC (qm_bantuan/quiz.py).

Kuis bersifat acak, jadi semua test memakai seed tetap (random.Random(42))
agar deterministik, mengikuti konvensi unittest repo.
"""

from __future__ import annotations

import random
import unittest

from qm_bantuan.data import Atlas, LEVEL_NAMES
from qm_bantuan.quiz import ARROW, QUIZ_GRADES, Quiz


def make_quiz(n_questions: int = 5, seed: int = 42) -> Quiz:
    return Quiz(Atlas.bundled(), n_questions=n_questions,
                rng=random.Random(seed))


class QuizQuestionTest(unittest.TestCase):
    def test_opsi_empat_unik_dan_jawaban_ada_di_opsi(self):
        quiz = make_quiz()
        q = quiz.next_question()
        self.assertIsNotNone(q)
        self.assertEqual(len(q["options"]), 4)
        self.assertEqual(len(set(q["options"])), 4)  # semua unik
        self.assertIn(q["answer"], q["options"])

    def test_format_opsi_level_panah_grade(self):
        quiz = make_quiz()
        q = quiz.next_question()
        for opt in q["options"]:
            level, sep, grade = opt.partition(f" {ARROW} ")
            self.assertEqual(sep, f" {ARROW} ")
            self.assertIn(level, LEVEL_NAMES)
            self.assertIn(grade, QUIZ_GRADES)

    def test_struktur_dict_soal(self):
        quiz = make_quiz()
        q = quiz.next_question()
        self.assertTrue(q["code"])
        self.assertIn(" — ", q["title"])  # "C11 — Tergores"
        self.assertIn(q["code"], q["title"])
        self.assertIn("Tingkat & grade apa yang tepat?", q["prompt"])
        self.assertIn(q["level"], ("L", "M", "H", "S"))
        self.assertIn(q["grade"], QUIZ_GRADES)

    def test_jawaban_benar_skor_bertambah(self):
        quiz = make_quiz()
        q = quiz.next_question()
        ok, feedback = quiz.answer(q["answer"])
        self.assertTrue(ok)
        self.assertEqual(quiz.score, 1)
        self.assertEqual(quiz.answered, 1)
        self.assertIn("✅", feedback)
        self.assertIn(q["code"], feedback)

    def test_jawaban_salah_skor_tetap(self):
        quiz = make_quiz()
        q = quiz.next_question()
        wrong = next(o for o in q["options"] if o != q["answer"])
        ok, feedback = quiz.answer(wrong)
        self.assertFalse(ok)
        self.assertEqual(quiz.score, 0)
        self.assertEqual(quiz.answered, 1)  # tetap dihitung menjawab
        self.assertIn("❌", feedback)
        self.assertIn(q["answer"], feedback)  # kunci jawaban ditampilkan

    def test_jawab_tanpa_soal_aktif_netral(self):
        quiz = make_quiz()
        ok, feedback = quiz.answer(f"L {ARROW} A")
        self.assertFalse(ok)
        self.assertNotIn("❌", feedback)
        self.assertEqual(quiz.answered, 0)
        self.assertEqual(quiz.score, 0)

    def test_done_setelah_n_questions(self):
        quiz = make_quiz(n_questions=3)
        for _ in range(3):
            q = quiz.next_question()
            self.assertIsNotNone(q)
            quiz.answer(q["answer"])
        self.assertTrue(quiz.done)
        self.assertEqual(quiz.answered, 3)
        self.assertEqual(quiz.score, 3)
        self.assertIsNone(quiz.next_question())  # None saat done

    def test_tidak_ada_kode_berulang_dalam_satu_sesi(self):
        quiz = make_quiz(n_questions=20)
        codes = []
        for _ in range(20):
            q = quiz.next_question()
            self.assertIsNotNone(q)
            codes.append(q["code"])
            quiz.answer(q["answer"])
        self.assertEqual(len(set(codes)), len(codes))

    def test_grade_di_opsi_selalu_kode_tunggal(self):
        # Sapu banyak soal: opsi tak boleh mengandung grade kondisional
        # seperti "A1 (bila hilang diamplas) / B (...)".
        quiz = make_quiz(n_questions=60)
        count = 0
        while not quiz.done:
            q = quiz.next_question()
            self.assertIsNotNone(q)
            for opt in q["options"]:
                grade = opt.split(f" {ARROW} ", 1)[1]
                self.assertNotIn("(", grade)
                self.assertNotIn("/", grade)
                self.assertIn(grade, QUIZ_GRADES)
            quiz.answer(q["answer"])
            count += 1
        self.assertGreater(count, 10)  # benar-benar menyapu banyak soal

    def test_deterministik_dengan_seed_sama(self):
        run1 = [self._snapshot(make_quiz(seed=42)) for _ in range(5)]
        run2 = [self._snapshot(make_quiz(seed=42)) for _ in range(5)]
        self.assertEqual(run1, run2)

    @staticmethod
    def _snapshot(quiz: Quiz) -> tuple:
        q = quiz.next_question()
        quiz.answer(q["answer"])
        return (q["code"], q["level"], tuple(q["options"]), q["answer"])


if __name__ == "__main__":
    unittest.main()
