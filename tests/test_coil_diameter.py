"""Port dari test/diameter.test.js (qm-ywi-telegram-bot)."""

from __future__ import annotations

import unittest

from qm_coil.diameter import (
    DIAMETER_CONSTANTS,
    get_diameter_prompt,
    resolve_diameter,
)


class DiameterTest(unittest.TestCase):
    def test_ft_default_610_dan_pilihan_ubah_508(self):
        prompt = get_diameter_prompt("FT")
        self.assertEqual(prompt.machine, "FT")
        self.assertIn("目前内径: 610", prompt.question)
        self.assertIn("Apakah perlu ubah diameter menjadi 508", prompt.question)
        # newline asli (bukan literal backslash-n)
        self.assertIn("610\n\nApakah", prompt.question)

        res_no = resolve_diameter("FT", "Tidak Perlu")
        self.assertEqual(res_no.diameter, 610)
        self.assertEqual(res_no.change_diameter, "Tidak Perlu")

        res_yes = resolve_diameter("FT", DIAMETER_CONSTANTS["FT_CHANGE_YES"])
        self.assertEqual(res_yes.diameter, 610)
        self.assertEqual(res_yes.change_diameter, "Perlu Ubah Diameter 508")

    def test_ft_deteksi_508_dari_teks_bebas(self):
        res = resolve_diameter("FT", "ya, 508 saja")
        self.assertEqual(res.change_diameter, "Perlu Ubah Diameter 508")

    def test_fj_pilihan_610_atau_508(self):
        prompt = get_diameter_prompt("FJ")
        self.assertEqual(prompt.machine, "FJ")
        self.assertEqual([o.value for o in prompt.options], [610, 508])

        res610 = resolve_diameter("FJ", 610)
        self.assertEqual(res610.diameter, 610)
        self.assertEqual(res610.change_diameter, "Tidak Perlu")

        res508 = resolve_diameter("FJ", 508)
        self.assertEqual(res508.diameter, 508)
        self.assertEqual(res508.change_diameter, "Tidak Perlu")

    def test_fj_input_string_angka(self):
        res = resolve_diameter("FJ", "508")
        self.assertEqual(res.diameter, 508)

    def test_mesin_tidak_dikenal(self):
        with self.assertRaises(ValueError):
            get_diameter_prompt("XX")
        with self.assertRaises(ValueError):
            resolve_diameter("XX", 610)


if __name__ == "__main__":
    unittest.main()
