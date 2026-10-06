"""Port dari test/form.test.js (qm-ywi-telegram-bot)."""

from __future__ import annotations

import unittest

from qm_coil.form import (
    format_full_preview,
    format_numbering_preview,
    generate_workplace_mandarin_output,
)


def _sample_state() -> dict:
    return {
        "machine": "FT",
        "sourceCoil": "QH2608K2531HA10",
        "materialCode": "K",
        "material": "S30403",
        "specification": "1.24*1524",
        "count": 3,
        "startDigit": 1,
        "generatedCoils": [
            "QH2608K2531HA11",
            "QH2608K2531HA12",
            "QH2608K2531HA13",
        ],
        "inspections": [
            {
                "coilNumber": "QH2608K2531HA11",
                "grade": "A1",
                "mainDefect": "B22",
                "remark": "-",
                "diameter": 610,
                "changeDiameter": "Tidak Perlu",
                "length": 955,
            },
            {
                "coilNumber": "QH2608K2531HA12",
                "grade": "A1",
                "mainDefect": "B22",
                "remark": "-",
                "diameter": 610,
                "changeDiameter": "Tidak Perlu",
                "length": 955,
            },
            {
                "coilNumber": "QH2608K2531HA13",
                "grade": "S",
                "mainDefect": "C13",
                "remark": "-",
                "diameter": 610,
                "changeDiameter": "Tidak Perlu",
                "length": 15,
            },
        ],
    }


class FormTest(unittest.TestCase):
    def test_workplace_mandarin_output_sesuai_prd(self):
        expected = (
            "机组：FT\n"
            "QH2608K2531HA10\n"
            "要生成新卷号\n"
            "\n"
            "QH2608K2531HA11\n"
            "S30403\n"
            "1.24*1524\n"
            "等级: A1\n"
            "主缺陷: B22\n"
            "备注: -\n"
            "目前内径: 610\n"
            "是否需改内径: Tidak Perlu\n"
            "长度: 955米\n"
            "\n"
            "QH2608K2531HA12\n"
            "S30403\n"
            "1.24*1524\n"
            "等级: A1\n"
            "主缺陷: B22\n"
            "备注: -\n"
            "目前内径: 610\n"
            "是否需改内径: Tidak Perlu\n"
            "长度: 955米\n"
            "\n"
            "QH2608K2531HA13\n"
            "S30403\n"
            "1.24*1524\n"
            "等级: S\n"
            "主缺陷: C13\n"
            "备注: -\n"
            "目前内径: 610\n"
            "是否需改内径: Tidak Perlu\n"
            "长度: 15米"
        )
        self.assertEqual(generate_workplace_mandarin_output(_sample_state()), expected)

    def test_remark_kosong_jadi_strip(self):
        state = _sample_state()
        state["inspections"][0]["remark"] = "   "
        output = generate_workplace_mandarin_output(state)
        self.assertIn("备注: -\n", output)

    def test_numbering_preview_sesuai_prd(self):
        coils = ["QH2608K2531HA11", "QH2608K2531HA12", "QH2608K2531HA13"]
        preview = format_numbering_preview(coils, "S30403")
        self.assertIn("Nomor gulungan yang akan dibuat:", preview)
        self.assertIn("1. QH2608K2531HA11", preview)
        self.assertIn("2. QH2608K2531HA12", preview)
        self.assertIn("3. QH2608K2531HA13", preview)
        self.assertIn("Material: S30403", preview)

    def test_full_preview_memuat_semua_data(self):
        preview = format_full_preview(_sample_state())
        self.assertIn("PREVIEW DATA INSPEKSI QM-YWI", preview)
        self.assertIn("QH2608K2531HA10", preview)
        self.assertIn("S30403 (K)", preview)
        self.assertIn("3 coil", preview)
        self.assertIn("Coil 1", preview)
        self.assertIn("Coil 3", preview)
        self.assertIn("Apakah data sudah benar?", preview)


if __name__ == "__main__":
    unittest.main()
