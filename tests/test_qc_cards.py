"""Tests untuk qm_bantuan/cards.py (format kartu jawaban)."""

from __future__ import annotations

import unittest

from qm_bantuan.cards import defect_card, grade_label, search_line, variant_summary
from qm_bantuan.data import Atlas


class CardTest(unittest.TestCase):
    def setUp(self):
        self.atlas = Atlas.bundled()

    def test_kartu_keputusan_di_depan_dan_urut_L_M_H_S(self):
        card = defect_card(self.atlas.get("C11"))
        self.assertIn("*C11* — Tergores", card)
        self.assertIn("划伤", card)
        i_l = card.index("*L* (Ringan)")
        i_m = card.index("*M* (Sedang)")
        i_h = card.index("*H* (Parah)")
        i_s = card.index("*S* (Serius)")
        self.assertTrue(i_l < i_m < i_h < i_s)
        # grade di baris yang sama dengan tingkat
        self.assertIn("*L* (Ringan) → *A*", card)
        self.assertIn("*S* (Serius) → *B1*", card)

    def test_kartu_memuat_legenda_grade(self):
        card = defect_card(self.atlas.get("C11"))
        self.assertIn("C = Giling Ulang", card)
        self.assertIn("S = Pembuangan", card)

    def test_kartu_tanpa_kriteria_tanpa_rule(self):
        # D03: pengertian saja + "database belum ada", tanpa karangan.
        card = defect_card(self.atlas.get("D03"))
        self.assertIn("*D03*", card)
        self.assertIn("database belum ada", card)
        self.assertNotIn("→ *A*", card)

    def test_kartu_aturan_tanpa_tingkat(self):
        # R61: tampilkan aturan + "database belum ada" untuk kriteria.
        card = defect_card(self.atlas.get("R61"))
        self.assertIn("Konfirmasi ke pihak perencanaan", card)
        self.assertIn("database belum ada", card)

    def test_kartu_varian(self):
        e = self.atlas.get("R19")
        v = Atlas.variants(e)[0]
        card = defect_card(e, v)
        self.assertIn("R19", card)
        self.assertIn("Jenis 1", card)
        self.assertIn("*L* (Ringan)", card)

    def test_ringkasan_varian(self):
        summary = variant_summary(self.atlas.get("R19"))
        self.assertIn("R19", summary)
        self.assertIn("Jenis 1", summary)
        self.assertIn("Jenis 2", summary)
        self.assertIn("L→A", summary)

    def test_superseded_note_muncul(self):
        # C39 punya superseded_note ambang scrap <3T.
        card = defect_card(self.atlas.get("C39"))
        self.assertIn("<3T", card)

    def test_search_line(self):
        line = search_line(self.atlas.get("C11"))
        self.assertIn("C11", line)
        self.assertIn("Tergores", line)


class GradeLabelTest(unittest.TestCase):
    def test_grade_khusus_dijelaskan(self):
        self.assertEqual(grade_label("C"), "C (Giling Ulang)")
        self.assertEqual(grade_label("R"), "R (Digulung Ulang)")
        self.assertEqual(grade_label("F"), "F (Diiris Samping)")
        self.assertEqual(grade_label("S"), "S (Pembuangan)")

    def test_grade_lolos_tetap_singkat(self):
        self.assertEqual(grade_label("A1"), "A1")
        self.assertEqual(grade_label("B1"), "B1")


if __name__ == "__main__":
    unittest.main()
