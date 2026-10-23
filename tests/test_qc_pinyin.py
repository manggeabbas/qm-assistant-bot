"""Tests untuk pinyin pada teks Mandarin yang ditampilkan bot."""

from __future__ import annotations

import unittest

try:
    import pypinyin  # noqa: F401
except ImportError:  # pragma: no cover
    pypinyin = None

from qm_bantuan.cards import _cn_line, defect_card
from qm_bantuan.data import Atlas, Panduan


@unittest.skipUnless(pypinyin is not None, "pypinyin belum terpasang")
class PinyinTest(unittest.TestCase):
    def test_to_pinyin_kata_dan_frasa(self):
        from qm_bantuan.pinyin import to_pinyin

        self.assertEqual(to_pinyin("划伤"), "huà shāng")
        self.assertEqual(to_pinyin("热轧卷重不足"), "rè yà juǎn zhòng bù zú")
        self.assertEqual(to_pinyin(""), "")
        self.assertEqual(to_pinyin(None), "")

    def test_baris_mandarin_memuat_pinyin(self):
        self.assertEqual(_cn_line("划伤"), "🇨🇳 _划伤_ (huà shāng)")
        self.assertEqual(_cn_line(""), "")

    def test_header_kartu_memuat_pinyin_nama(self):
        card = defect_card(Atlas.bundled().get("C11"))
        self.assertIn("划伤 (huà shāng)", card)

    def test_nama_mandarin_di_judul_ikut_berpinyin(self):
        # R61 tidak punya nama Indonesia: nama Mandarin tampil di judul.
        card = defect_card(Atlas.bundled().get("R61"))
        self.assertIn("热轧卷重不足 (rè yà juǎn zhòng bù zú)", card)

    def test_judul_bagan_memuat_pinyin(self):
        isi = Panduan.bundled().get("main_bagan")["isi"]
        self.assertIn("yǒng wàng lěng zhá gāng juǎn jiǎn yàn liú chéng tú", isi)
