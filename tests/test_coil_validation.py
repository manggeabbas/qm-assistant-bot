"""Port dari test/validation.test.js (qm-ywi-telegram-bot)."""

from __future__ import annotations

import unittest

from qm_coil.validation import (
    VALID_GRADES,
    validate_count,
    validate_grade,
    validate_length,
    validate_machine,
    validate_main_defect,
    validate_name,
    validate_nik,
    validate_remark,
    validate_source_coil,
    validate_specification,
    validate_start_digit,
)


class ValidationTest(unittest.TestCase):
    def test_mesin_ft_fj(self):
        self.assertTrue(validate_machine("FT").valid)
        self.assertTrue(validate_machine("fj").valid)
        self.assertEqual(validate_machine("fj").value, "FJ")
        self.assertFalse(validate_machine("XX").valid)
        self.assertFalse(validate_machine("").valid)

    def test_source_coil_dan_material(self):
        valid = validate_source_coil("QH2608K2531HA10")
        self.assertTrue(valid.valid)
        self.assertEqual(valid.material_code, "K")
        self.assertEqual(valid.material, "S30403")
        self.assertEqual(valid.value, "QH2608K2531HA10")

        invalid = validate_source_coil("QH2608X2531HA10")
        self.assertFalse(invalid.valid)

    def test_spesifikasi(self):
        self.assertTrue(validate_specification("1.24*1524").valid)
        self.assertFalse(validate_specification("").valid)
        self.assertFalse(validate_specification("1").valid)

    def test_count_dan_start_digit(self):
        self.assertTrue(validate_count(3).valid)
        self.assertEqual(validate_count("3").value, 3)
        self.assertFalse(validate_count(0).valid)
        self.assertFalse(validate_count(-1).valid)
        self.assertFalse(validate_count("abc").valid)

        self.assertTrue(validate_start_digit(1, 3).valid)
        self.assertFalse(validate_start_digit(8, 3).valid)  # 8+3-1=10 > 9

    def test_grade(self):
        for grade in VALID_GRADES:
            self.assertTrue(validate_grade(grade).valid)
            self.assertTrue(validate_grade(grade.lower()).valid)
        self.assertFalse(validate_grade("C").valid)
        self.assertFalse(validate_grade("A").valid)
        self.assertFalse(validate_grade("").valid)

    def test_main_defect(self):
        self.assertTrue(validate_main_defect("B22").valid)
        self.assertEqual(validate_main_defect("r20").value, "R20")
        self.assertFalse(validate_main_defect("").valid)

    def test_remark_default_strip(self):
        self.assertEqual(validate_remark("").value, "-")
        self.assertEqual(validate_remark("-").value, "-")
        self.assertEqual(validate_remark("Ada cacat tepi").value, "Ada cacat tepi")

    def test_length_meter(self):
        self.assertTrue(validate_length("955").valid)
        self.assertEqual(validate_length(955).value, 955)
        self.assertFalse(validate_length(0).valid)
        self.assertFalse(validate_length(-10).valid)
        self.assertFalse(validate_length("abc").valid)

    def test_registrasi_nama_dan_nik(self):
        self.assertTrue(validate_name("Budi Santoso").valid)
        self.assertEqual(validate_name("  Budi   Santoso ").value, "Budi Santoso")
        self.assertFalse(validate_name("A").valid)
        self.assertFalse(validate_name("").valid)

        self.assertTrue(validate_nik("12345678").valid)
        self.assertEqual(validate_nik(" 12345678 ").value, "12345678")
        for bad in ["1234567", "123456789", "1234 678", "1234567A",
                    "3273010101900001", ""]:
            with self.subTest(nik=bad):
                self.assertFalse(validate_nik(bad).valid)


if __name__ == "__main__":
    unittest.main()
