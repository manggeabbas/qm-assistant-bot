"""Port dari test/material.test.js (qm-ywi-telegram-bot)."""

from __future__ import annotations

import unittest

from qm_coil.material import (
    UNKNOWN_MATERIAL_MESSAGE,
    detect_material,
    get_material_name,
)


class MaterialTest(unittest.TestCase):
    def test_mapping_z_k_g(self):
        self.assertEqual(get_material_name("Z"), "S30400")
        self.assertEqual(get_material_name("K"), "S30403")
        self.assertEqual(get_material_name("G"), "S31603")
        # case-insensitive, seperti aslinya
        self.assertEqual(get_material_name("z"), "S30400")
        self.assertEqual(get_material_name("k"), "S30403")
        self.assertEqual(get_material_name("g"), "S31603")

    def test_mapping_tidak_dikenal_tidak_menebak(self):
        self.assertIsNone(get_material_name("X"))
        self.assertIsNone(get_material_name(""))
        self.assertIsNone(get_material_name(None))

    def test_detect_kode_valid(self):
        for coil, code, material in [
            ("QH2608K1234HA10", "K", "S30403"),
            ("QH2608Z1234HA10", "Z", "S30400"),
            ("QH2608G1234HA10", "G", "S31603"),
            ("qh2608k2531ha10", "K", "S30403"),  # case-insensitive
        ]:
            with self.subTest(coil=coil):
                result = detect_material(coil)
                self.assertTrue(result.valid)
                self.assertEqual(result.material_code, code)
                self.assertEqual(result.material, material)

    def test_detect_kode_tidak_dikenal_ditolak(self):
        result = detect_material("QH2608X1234HA10")
        self.assertFalse(result.valid)
        self.assertEqual(result.material_code, "X")
        self.assertEqual(result.error, UNKNOWN_MATERIAL_MESSAGE)
        self.assertIn("Kode jenis/material tidak dikenali", result.error)
        self.assertIn("Z = S30400", result.error)
        self.assertIn("K = S30403", result.error)
        self.assertIn("G = S31603", result.error)

    def test_detect_format_tidak_valid(self):
        no_ha = detect_material("QH2608K1234")
        self.assertFalse(no_ha.valid)
        self.assertIn("suffix HA", no_ha.error)

        empty = detect_material("")
        self.assertFalse(empty.valid)

        none_input = detect_material(None)
        self.assertFalse(none_input.valid)


if __name__ == "__main__":
    unittest.main()
