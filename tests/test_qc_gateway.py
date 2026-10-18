"""Tests untuk qm_bantuan/gateway.py (alur Bantuan QC end-to-end)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_bantuan.data import Atlas
from qm_bantuan.gateway import (
    BTN_BACK,
    BTN_GUIDE,
    BTN_LIST,
    BTN_PHOTO,
    BTN_QUIZ,
    BTN_SEARCH,
    QCGateway,
)


def msg(user_id: str, text: str, **kw) -> IncomingMessage:
    return IncomingMessage(user_id=user_id, text=text, **kw)


class FakeVision:
    """Provider AI palsu dengan analyze_image."""

    def __init__(self, reply: str = "kandidat: C11 (Tinggi)") -> None:
        self.reply = reply
        self.calls: list[tuple[bytes, str]] = []

    def analyze_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        self.calls.append((image_bytes, mime_type))
        return self.reply


class GatewayMenuTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())

    def test_qc_menampilkan_menu(self):
        out = self.gw.handle(msg("1", "/qc"))
        self.assertEqual(len(out), 1)
        self.assertEqual(
            out[0].buttons, [BTN_SEARCH, BTN_LIST, BTN_QUIZ, BTN_PHOTO, BTN_GUIDE]
        )
        self.assertIn("Bantuan QC", out[0].text)

    def test_tombol_kembali_ke_menu(self):
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_SEARCH))
        out = self.gw.handle(msg("1", BTN_BACK))
        self.assertEqual(
            out[0].buttons, [BTN_SEARCH, BTN_LIST, BTN_QUIZ, BTN_PHOTO, BTN_GUIDE]
        )

    def test_idempotensi_update_duplikat(self):
        m = msg("1", "/qc", update_id=77)
        self.gw.handle(m)
        out = self.gw.handle(msg("1", "/qc", update_id=77))
        self.assertEqual(out, [])


class GatewaySearchTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_SEARCH))

    def test_cari_kode_persis_langsung_kartu(self):
        out = self.gw.handle(msg("1", "C11"))
        self.assertEqual(len(out), 1)
        self.assertIn("*C11* — Tergores", out[0].text)
        self.assertIn("*L* (Ringan) → *A*", out[0].text)

    def test_cari_kata_kunci_banyak_hasil(self):
        out = self.gw.handle(msg("1", "tergores"))
        self.assertIn("Ditemukan", out[0].text)
        # pilih hasil pertama lewat tombol
        first_btn = out[0].buttons[0]
        out2 = self.gw.handle(msg("1", first_btn))
        self.assertIn("🔍 *", out2[0].text)

    def test_cari_tidak_ditemukan(self):
        out = self.gw.handle(msg("1", "zzz-tidak-ada"))
        self.assertIn("Tidak ditemukan", out[0].text)

    def test_kartu_tanpa_kriteria(self):
        out = self.gw.handle(msg("1", "D03"))
        self.assertIn("database belum ada", out[0].text)


class GatewayListTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_LIST))

    def test_pilih_tahap_menampilkan_halaman(self):
        out = self.gw.handle(msg("1", "Asam Dingin"))
        self.assertIn("Asam Dingin", out[0].text)
        self.assertIn("hal. 1/", out[0].text)
        self.assertIn("▶", out[0].buttons)

    def test_navigasi_halaman(self):
        out = self.gw.handle(msg("1", "Asam Dingin"))
        out2 = self.gw.handle(msg("1", "▶"))
        self.assertIn("hal. 2/", out2[0].text)
        self.assertIn("◀", out2[0].buttons)

    def test_pilih_kode_menampilkan_kartu(self):
        out = self.gw.handle(msg("1", "Bahan Baku"))
        code_btn = out[0].buttons[0]
        out2 = self.gw.handle(msg("1", code_btn))
        self.assertIn("🔍 *", out2[0].text)

    def test_kartu_varian_r19(self):
        self.gw.handle(msg("1", BTN_SEARCH))
        out = self.gw.handle(msg("1", "R19"))
        self.assertIn("Jenis 1", out[0].text)
        self.assertIn("Jenis 2", out[0].text)
        out2 = self.gw.handle(msg("1", "Jenis 1"))
        self.assertIn("*L* (Ringan)", out2[0].text)


class GatewayQuizTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))

    def test_kuis_5_soal_selesai_dengan_skor(self):
        out = self.gw.handle(msg("1", BTN_QUIZ))
        self.assertIn("Latihan kilat", out[0].text)
        self.assertIn("soal 1/5", out[0].text)
        answered = 0
        for _ in range(5):
            # jawab asal dengan opsi pertama (benar/salah tak penting)
            opt = out[0].buttons[0]
            out = self.gw.handle(msg("1", opt))
            answered += 1
            if "Skor" in out[-1].text and "Latihan kilat" not in out[-1].text:
                break
            out = [out[-1]]
        self.assertTrue(any("Skor" in m.text for m in out))

    def test_kuis_stop_di_tengah(self):
        out = self.gw.handle(msg("1", BTN_QUIZ))
        out2 = self.gw.handle(msg("1", "⏹ Selesai"))
        self.assertIn("Latihan", out2[0].text)


class GatewayPhotoTest(unittest.TestCase):
    def test_foto_tanpa_provider(self):
        gw = QCGateway(atlas=Atlas.bundled(), ai_provider=None)
        with TemporaryDirectory() as td:
            p = Path(td) / "foto.jpg"
            p.write_bytes(b"\xff\xd8fake")
            out = gw.handle(msg("1", "", photo_path=p))
        self.assertIn("belum tersedia", out[0].text)

    def test_foto_dianalisis_dan_disclaimer(self):
        vision = FakeVision()
        gw = QCGateway(atlas=Atlas.bundled(), ai_provider=vision)
        with TemporaryDirectory() as td:
            p = Path(td) / "foto.jpg"
            p.write_bytes(b"\xff\xd8fake")
            out = gw.handle(msg("1", "", photo_path=p))
        self.assertEqual(len(vision.calls), 1)
        self.assertEqual(vision.calls[0][1], "image/jpeg")
        self.assertIn("Hasil Analisis Foto", out[0].text)
        self.assertIn("opini kedua", out[0].text)

    def test_foto_tidak_diproses_dua_kali(self):
        vision = FakeVision()
        gw = QCGateway(atlas=Atlas.bundled(), ai_provider=vision)
        with TemporaryDirectory() as td:
            p = Path(td) / "foto.jpg"
            p.write_bytes(b"\xff\xd8fake")
            m = msg("1", "", photo_path=p, update_id=99)
            gw.handle(m)
            out = gw.handle(msg("1", "", photo_path=p, update_id=99))
        self.assertEqual(out, [])
        self.assertEqual(len(vision.calls), 1)


if __name__ == "__main__":
    unittest.main()
