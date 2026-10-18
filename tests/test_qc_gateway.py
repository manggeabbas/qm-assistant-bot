"""Tests untuk qm_bantuan/gateway.py (alur Bantuan QC end-to-end)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_bantuan.data import Atlas
from qm_bantuan.gateway import (
    BTN_BACK,
    BTN_BAGIAN_LIST,
    BTN_BAGIAN_QUIZ,
    BTN_BAGIAN_SEARCH,
    BTN_BAHAN_BAKU,
    BTN_GUIDE,
    BTN_JALUR_UTAMA,
    BTN_LUAR_JALUR,
    BTN_PHOTO,
    BTN_PROSEDUR,
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

    def test_qc_menampilkan_menu_bagian(self):
        out = self.gw.handle(msg("1", "/qc"))
        self.assertEqual(len(out), 1)
        self.assertEqual(
            out[0].buttons,
            [BTN_BAHAN_BAKU, BTN_JALUR_UTAMA, BTN_LUAR_JALUR,
             BTN_PHOTO, BTN_GUIDE, BTN_PROSEDUR],
        )
        self.assertIn("Bantuan QC", out[0].text)

    def test_masuk_bagian_menampilkan_submenu(self):
        self.gw.handle(msg("1", "/qc"))
        out = self.gw.handle(msg("1", BTN_JALUR_UTAMA))
        self.assertEqual(
            out[0].buttons, [BTN_BAGIAN_SEARCH, BTN_BAGIAN_LIST, BTN_BAGIAN_QUIZ, BTN_BACK]
        )
        self.assertIn("Jalur Utama", out[0].text)

    def test_tombol_kembali_ke_menu(self):
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_JALUR_UTAMA))
        self.gw.handle(msg("1", BTN_BAGIAN_SEARCH))
        out = self.gw.handle(msg("1", BTN_BACK))
        self.assertEqual(
            out[0].buttons,
            [BTN_BAHAN_BAKU, BTN_JALUR_UTAMA, BTN_LUAR_JALUR,
             BTN_PHOTO, BTN_GUIDE, BTN_PROSEDUR],
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
        self.gw.handle(msg("1", BTN_JALUR_UTAMA))
        self.gw.handle(msg("1", BTN_BAGIAN_SEARCH))

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

    def test_cari_tidak_ditemukan_di_bagian(self):
        out = self.gw.handle(msg("1", "zzz-tidak-ada"))
        self.assertIn("Tidak ditemukan", out[0].text)

    def test_cari_terbatas_pada_bagian(self):
        # B22 ada di Jalur Utama (rolling mill); cari di Bahan Baku -> tak ketemu
        gw = QCGateway(atlas=Atlas.bundled())
        gw.handle(msg("2", "/qc"))
        gw.handle(msg("2", BTN_BAHAN_BAKU))
        gw.handle(msg("2", BTN_BAGIAN_SEARCH))
        out = gw.handle(msg("2", "B22"))
        self.assertIn("Tidak ditemukan", out[0].text)


class GatewayListTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_LUAR_JALUR))
        self.gw.handle(msg("1", BTN_BAGIAN_LIST))

    def test_daftar_bagian_menampilkan_halaman(self):
        self.gw.handle(msg("1", BTN_BACK))  # kembali ke menu utama
        self.gw.handle(msg("1", BTN_LUAR_JALUR))
        out = self.gw.handle(msg("1", BTN_BAGIAN_LIST))
        self.assertIn("Luar Jalur", out[0].text)
        self.assertIn("hal. 1/", out[0].text)
        self.assertIn("▶", out[0].buttons)

    def test_navigasi_halaman(self):
        out = self.gw.handle(msg("1", "▶"))
        self.assertIn("hal. 2/", out[0].text)
        self.assertIn("◀", out[0].buttons)

    def test_pilih_kode_menampilkan_kartu(self):
        self.gw.handle(msg("1", BTN_BACK))
        self.gw.handle(msg("1", BTN_LUAR_JALUR))
        out = self.gw.handle(msg("1", BTN_BAGIAN_LIST))
        code_btn = out[0].buttons[0]
        out2 = self.gw.handle(msg("1", code_btn))
        self.assertIn("🔍 *", out2[0].text)

    def test_kartu_varian_r19(self):
        gw = QCGateway(atlas=Atlas.bundled())
        gw.handle(msg("3", "/qc"))
        gw.handle(msg("3", BTN_BAHAN_BAKU))
        gw.handle(msg("3", BTN_BAGIAN_SEARCH))
        out = gw.handle(msg("3", "R19"))
        self.assertIn("Jenis 1", out[0].text)
        self.assertIn("Jenis 2", out[0].text)
        out2 = gw.handle(msg("3", "Jenis 1"))
        self.assertIn("*L* (Ringan)", out2[0].text)

    def test_kartu_tanpa_kriteria(self):
        gw = QCGateway(atlas=Atlas.bundled())
        gw.handle(msg("4", "/qc"))
        gw.handle(msg("4", BTN_BAHAN_BAKU))
        gw.handle(msg("4", BTN_BAGIAN_SEARCH))
        out = gw.handle(msg("4", "D03"))
        self.assertIn("database belum ada", out[0].text)


class GatewayQuizTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))
        self.gw.handle(msg("1", BTN_BAHAN_BAKU))

    def test_kuis_5_soal_selesai_dengan_skor(self):
        out = self.gw.handle(msg("1", BTN_BAGIAN_QUIZ))
        self.assertIn("Latihan kilat", out[0].text)
        self.assertIn("Bahan Baku", out[0].text)
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
        out = self.gw.handle(msg("1", BTN_BAGIAN_QUIZ))
        out2 = self.gw.handle(msg("1", "⏹ Selesai"))
        self.assertIn("Latihan", out2[0].text)


class GatewayProsedurTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.gw.handle(msg("1", "/qc"))

    def test_menu_memuat_tombol_prosedur(self):
        out = self.gw.handle(msg("1", BTN_PROSEDUR))
        self.assertIn("Prosedur Kerja", out[0].text)
        self.assertIn("🔧 Mesin FT", out[0].buttons)

    def test_grup_menampilkan_topik(self):
        self.gw.handle(msg("1", BTN_PROSEDUR))
        out = self.gw.handle(msg("1", "🔧 Mesin FT"))
        self.assertIn("Mesin FT", out[0].text)
        self.assertTrue(any("Inspeksi" in b for b in out[0].buttons))

    def test_topik_bisa_dibuka_dan_pindah(self):
        self.gw.handle(msg("1", BTN_PROSEDUR))
        out = self.gw.handle(msg("1", "🔧 Mesin FT"))
        first = out[0].buttons[0]
        out2 = self.gw.handle(msg("1", first))
        self.assertIn("TTRI-QM-ZY-34-2025", out2[0].text)
        # pindah ke topik lain langsung
        second = [b for b in out2[0].buttons if b != first and b != BTN_BACK][0]
        out3 = self.gw.handle(msg("1", second))
        self.assertNotEqual(out2[0].text, out3[0].text)


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

    def test_foto_error_503_pesan_ramah(self):
        from qm_training.core.errors import AIProviderError

        class FailingVision(FakeVision):
            def analyze_image(self, image_bytes, mime_type="image/jpeg"):
                raise AIProviderError('gemini: HTTP 503: {"status": "UNAVAILABLE"}')

        gw = QCGateway(atlas=Atlas.bundled(), ai_provider=FailingVision())
        with TemporaryDirectory() as td:
            p = Path(td) / "foto.jpg"
            p.write_bytes(b"\xff\xd8fake")
            out = gw.handle(msg("1", "", photo_path=p))
        self.assertIn("sibuk", out[0].text)
        self.assertNotIn("UNAVAILABLE", out[0].text)
        self.assertNotIn('"code"', out[0].text)

    def test_foto_error_non_503_tampil_apa_adanya(self):
        from qm_training.core.errors import AIProviderError

        class FailingVision(FakeVision):
            def analyze_image(self, image_bytes, mime_type="image/jpeg"):
                raise AIProviderError("gemini: kunci API tidak ada")

        gw = QCGateway(atlas=Atlas.bundled(), ai_provider=FailingVision())
        with TemporaryDirectory() as td:
            p = Path(td) / "foto.jpg"
            p.write_bytes(b"\xff\xd8fake")
            out = gw.handle(msg("1", "", photo_path=p))
        self.assertIn("Gagal menganalisis foto", out[0].text)


if __name__ == "__main__":
    unittest.main()
