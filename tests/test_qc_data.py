"""Tests untuk qm_bantuan/data.py (akses atlas cacat, data-driven)."""

from __future__ import annotations

import unittest

from qm_bantuan.data import (
    GRADE_NAMES,
    LEVEL_NAMES,
    LEVEL_ORDER,
    SECTION_NAMES,
    Atlas,
)


class AtlasLoadTest(unittest.TestCase):
    def test_bundled_memuat_182_entri_tanpa_duplikat(self):
        atlas = Atlas.bundled()
        self.assertEqual(len(atlas), 182)
        codes = atlas.codes()
        self.assertEqual(len(set(codes)), len(codes))

    def test_section_lengkap(self):
        atlas = Atlas.bundled()
        for section in ("bahan_baku", "asam_panas", "rolling_mill", "asam_dingin", "penyelesaian"):
            self.assertGreater(len(atlas.by_section(section)), 0, section)
        self.assertEqual(set(SECTION_NAMES), {s for s, _ in
                          [("bahan_baku", ""), ("asam_panas", ""), ("rolling_mill", ""),
                           ("asam_dingin", ""), ("penyelesaian", "")]})


class AtlasLookupTest(unittest.TestCase):
    def setUp(self):
        self.atlas = Atlas.bundled()

    def test_get_case_insensitive(self):
        self.assertEqual(self.atlas.get("c11")["code"], "C11")
        self.assertEqual(self.atlas.get(" C11 ")["code"], "C11")
        self.assertIsNone(self.atlas.get("ZZZ"))

    def test_search_kode_persis_pertama(self):
        hits = self.atlas.search("C11")
        self.assertGreaterEqual(len(hits), 1)
        self.assertEqual(hits[0]["code"], "C11")

    def test_search_kata_kunci_nama(self):
        hits = self.atlas.search("tergores")
        codes = {e["code"] for e in hits}
        self.assertIn("C11", codes)

    def test_search_kosong(self):
        self.assertEqual(self.atlas.search(""), [])
        self.assertEqual(self.atlas.search("   "), [])
        self.assertEqual(self.atlas.search("xyz-tidak-ada"), [])

    def test_search_limit(self):
        hits = self.atlas.search("a", limit=5)
        self.assertLessEqual(len(hits), 5)


class AtlasShapeTest(unittest.TestCase):
    def setUp(self):
        self.atlas = Atlas.bundled()

    def test_urutan_level_selalu_L_M_H_S(self):
        self.assertEqual(LEVEL_ORDER, ["L", "M", "H", "S"])
        self.assertEqual(set(LEVEL_NAMES), {"L", "M", "H", "S"})
        for e in self.atlas.entries:
            self.assertEqual(
                Atlas.ordered_levels(e),
                [lv for lv in LEVEL_ORDER if lv in Atlas.levels_of(e)],
                e["code"],
            )

    def test_entri_tanpa_kriteria_terdeteksi(self):
        # D03/D21/D38/F16/C56: tanpa levels dan tanpa rule.
        for code in ("D03", "D21", "D38", "F16", "C56"):
            e = self.atlas.get(code)
            self.assertFalse(Atlas.has_criteria(e), code)
            self.assertFalse(Atlas.has_rule(e), code)

    def test_entri_aturan_tanpa_tingkat(self):
        # C49: ada rule, tanpa levels -> kartu aturan, kriteria "database belum ada".
        e = self.atlas.get("C49")
        self.assertTrue(Atlas.has_rule(e))
        self.assertFalse(Atlas.has_criteria(e))

    def test_varian_r19(self):
        e = self.atlas.get("R19")
        variants = Atlas.variants(e)
        self.assertEqual(len(variants), 2)
        self.assertTrue(Atlas.has_criteria(e))
        for v in variants:
            self.assertEqual(
                Atlas.ordered_levels(e, v),
                [lv for lv in LEVEL_ORDER if lv in Atlas.levels_of(e, v)],
            )

    def test_display_name_fallback_mandarin(self):
        # R61: name_id null -> pakai Mandarin (jangan karang nama).
        e = self.atlas.get("R61")
        self.assertIsNone(e.get("name_id"))
        self.assertEqual(Atlas.display_name(e), e["name_cn"])

    def test_grade_names_lengkap(self):
        for g in ("A", "A1", "B", "B1", "C", "R", "F", "S"):
            self.assertIn(g, GRADE_NAMES)


if __name__ == "__main__":
    unittest.main()
