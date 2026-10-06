"""Port dari test/numbering.test.js (qm-ywi-telegram-bot)."""

from __future__ import annotations

import unittest

from qm_coil.numbering import (
    generate_coil_numbers,
    parse_source_coil_suffix,
    validate_numbering_params,
)


class NumberingTest(unittest.TestCase):
    def test_suffix_parsing_grup_ha(self):
        parsed10 = parse_source_coil_suffix("QH2608K2531HA10")
        self.assertTrue(parsed10.valid)
        self.assertEqual(parsed10.base_prefix, "QH2608K2531HA1")
        self.assertEqual(parsed10.group_prefix, "HA1")
        self.assertEqual(parsed10.last_digit, 0)

        parsed20 = parse_source_coil_suffix("QH2608K2531HA20")
        self.assertTrue(parsed20.valid)
        self.assertEqual(parsed20.base_prefix, "QH2608K2531HA2")
        self.assertEqual(parsed20.group_prefix, "HA2")
        self.assertEqual(parsed20.last_digit, 0)

        parsed35 = parse_source_coil_suffix("QH2608K2531HA35")
        self.assertTrue(parsed35.valid)
        self.assertEqual(parsed35.base_prefix, "QH2608K2531HA3")
        self.assertEqual(parsed35.group_prefix, "HA3")
        self.assertEqual(parsed35.last_digit, 5)

    def test_generate_contoh_prd(self):
        # Source: QH2608K2531HA10, count 3, start 1
        result = generate_coil_numbers("QH2608K2531HA10", 3, 1)
        self.assertTrue(result.valid)
        self.assertEqual(
            result.coils,
            ["QH2608K2531HA11", "QH2608K2531HA12", "QH2608K2531HA13"],
        )

    def test_generate_hanya_digit_terakhir_berubah(self):
        result = generate_coil_numbers("QH2608K2531HA20", 5, 0)
        self.assertTrue(result.valid)
        self.assertEqual(
            result.coils,
            [
                "QH2608K2531HA20",
                "QH2608K2531HA21",
                "QH2608K2531HA22",
                "QH2608K2531HA23",
                "QH2608K2531HA24",
            ],
        )

    def test_tolak_start_plus_count_lebih_dari_9(self):
        # start 1, count 10 -> 1 + 10 - 1 = 10 > 9
        res1 = generate_coil_numbers("QH2608K2531HA10", 10, 1)
        self.assertFalse(res1.valid)
        self.assertIn("Penomoran ditolak", res1.error)
        self.assertIn("HA110", res1.error)
        # newline asli (bukan literal backslash-n)
        self.assertIn("(> 9).\nDigit terakhir", res1.error)
        self.assertNotIn("\\n", res1.error)

        # start 8, count 3 -> 8 + 3 - 1 = 10 > 9
        res2 = generate_coil_numbers("QH2608K2531HA10", 3, 8)
        self.assertFalse(res2.valid)
        self.assertIn("Penomoran ditolak", res2.error)

    def test_validasi_batas_parameter(self):
        self.assertFalse(validate_numbering_params(3, -1).valid)
        self.assertFalse(validate_numbering_params(1, 10).valid)
        self.assertFalse(validate_numbering_params(0, 1).valid)
        self.assertFalse(validate_numbering_params(-2, 1).valid)
        self.assertFalse(validate_numbering_params(2.5, 1).valid)

    def test_parse_tanpa_suffix_ha(self):
        result = parse_source_coil_suffix("QH2608K2531")
        self.assertFalse(result.valid)

    def test_parse_kosong(self):
        self.assertFalse(parse_source_coil_suffix("").valid)
        self.assertFalse(parse_source_coil_suffix(None).valid)


if __name__ == "__main__":
    unittest.main()
