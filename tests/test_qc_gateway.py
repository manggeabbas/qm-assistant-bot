"""Tests untuk qm_bantuan/gateway.py (alur Bantuan QC end-to-end, tombol inline)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from qm_training.bot.adapters.base import IncomingMessage, OutgoingMessage

from qm_bantuan.data import Atlas
from qm_bantuan.gateway import (
    BTN_BACK,
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


def cbs(out_msg: OutgoingMessage) -> list[tuple[str, str]]:
    """Semua (teks, callback_data) dari inline buttons sebuah pesan."""
    return [(t, d) for row in (out_msg.inline_buttons or []) for t, d in row]


def cb(out_msg: OutgoingMessage, text: str) -> str:
    for t, d in cbs(out_msg):
        if t == text:
            return d
    raise AssertionError(f"tombol '{text}' tidak ditemukan di {cbs(out_msg)}")


def tap(gw: QCGateway, uid: str, out_msg: OutgoingMessage, text: str):
    return gw.handle(msg(uid, cb(out_msg, text)))


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

    def test_qc_menampilkan_menu_bagian_inline(self):
        out = self.gw.handle(msg("1", "/qc"))
        self.assertEqual(len(out), 1)
        texts = [t for t, _ in cbs(out[0])]
        for want in (BTN_BAHAN_BAKU, BTN_JALUR_UTAMA, BTN_LUAR_JALUR, BTN_PHOTO):
            self.assertIn(want, texts)
        self.assertIn("Kode Cacat", out[0].text)
        # tidak ada reply keyboard — murni inline
        self.assertEqual(out[0].buttons, [])

    def test_masuk_bagian_menampilkan_submenu(self):
        out = self.gw.handle(msg("1", "/qc"))
        out = tap(self.gw, "1", out[0], BTN_JALUR_UTAMA)
        texts = [t for t, _ in cbs(out[0])]
        self.assertEqual(texts, ["🔍 Cari", "📖 Daftar", "🎯 Kuis", BTN_BACK])
        self.assertIn("Jalur Utama", out[0].text)

    def test_tombol_kembali_ke_menu(self):
        out = self.gw.handle(msg("1", "/qc"))
        out = tap(self.gw, "1", out[0], BTN_JALUR_UTAMA)
        out = tap(self.gw, "1", out[0], "🔍 Cari")
        # tombol kembali di sini mengarah ke submenu bagian
        out = tap(self.gw, "1", out[0], "◀ 🏭 Jalur Utama")
        self.assertIn("Jalur Utama", out[0].text)
        self.assertIn("Mau apa?", out[0].text)

    def test_idempotensi_update_duplikat(self):
        m = msg("1", "/qc", update_id=77)
        self.gw.handle(m)
        out = self.gw.handle(msg("1", "/qc", update_id=77))
        self.assertEqual(out, [])

    def test_callback_tak_dikenal_kembali_ke_menu(self):
        out = self.gw.handle(msg("1", "qc:ngawur"))
        self.assertIn("Kode Cacat", out[0].text)


class GatewaySearchTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        out = self.gw.handle(msg("1", "/qc"))
        out = tap(self.gw, "1", out[0], BTN_JALUR_UTAMA)
        self.out = tap(self.gw, "1", out[0], "🔍 Cari")

    def test_cari_kode_persis_langsung_kartu(self):
        out = self.gw.handle(msg("1", "C11"))
        self.assertEqual(len(out), 1)
        self.assertIn("*C11* — Tergores", out[0].text)
        self.assertIn("*L* (Ringan) → *A*", out[0].text)

    def test_cari_kata_kunci_banyak_hasil_inline(self):
        out = self.gw.handle(msg("1", "tergores"))
        self.assertIn("Ditemukan", out[0].text)
        # pilih hasil pertama lewat tombol inline
        first_cb = cbs(out[0])[0][1]
        self.assertTrue(first_cb.startswith("qc:card:"))
        out2 = self.gw.handle(msg("1", first_cb))
        self.assertIn("🔍 *", out2[0].text)

    def test_cari_tidak_ditemukan_di_bagian(self):
        out = self.gw.handle(msg("1", "zzz-tidak-ada"))
        self.assertIn("Tidak ditemukan", out[0].text)

    def test_cari_terbatas_pada_bagian(self):
        # B22 ada di Jalur Utama (rolling mill); cari di Bahan Baku -> tak ketemu
        gw = QCGateway(atlas=Atlas.bundled())
        out = gw.handle(msg("2", "/qc"))
        out = tap(gw, "2", out[0], BTN_BAHAN_BAKU)
        out = tap(gw, "2", out[0], "🔍 Cari")
        out = gw.handle(msg("2", "B22"))
        self.assertIn("Tidak ditemukan", out[0].text)


class GatewayListTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        out = self.gw.handle(msg("1", "/qc"))
        out = tap(self.gw, "1", out[0], BTN_LUAR_JALUR)
        self.out = tap(self.gw, "1", out[0], "📖 Daftar")

    def test_daftar_bagian_menampilkan_halaman(self):
        self.assertIn("Luar Jalur", self.out[0].text)
        self.assertIn("hal. 1/", self.out[0].text)
        texts = [t for t, _ in cbs(self.out[0])]
        self.assertIn("▶", texts)

    def test_navigasi_halaman(self):
        out = tap(self.gw, "1", self.out[0], "▶")
        self.assertIn("hal. 2/", out[0].text)
        texts = [t for t, _ in cbs(out[0])]
        self.assertIn("◀", texts)

    def test_pilih_kode_menampilkan_kartu(self):
        first_cb = cbs(self.out[0])[0][1]
        self.assertTrue(first_cb.startswith("qc:card:"))
        out2 = self.gw.handle(msg("1", first_cb))
        self.assertIn("🔍 *", out2[0].text)

    def test_kartu_varian_r19(self):
        gw = QCGateway(atlas=Atlas.bundled())
        out = gw.handle(msg("3", "/qc"))
        out = tap(gw, "3", out[0], BTN_BAHAN_BAKU)
        out = tap(gw, "3", out[0], "🔍 Cari")
        out = gw.handle(msg("3", "R19"))
        texts = [t for t, _ in cbs(out[0])]
        self.assertIn("Jenis 1", texts)
        self.assertIn("Jenis 2", texts)
        out2 = tap(gw, "3", out[0], "Jenis 1")
        self.assertIn("*L* (Ringan)", out2[0].text)

    def test_kartu_tanpa_kriteria(self):
        gw = QCGateway(atlas=Atlas.bundled())
        out = gw.handle(msg("4", "/qc"))
        out = tap(gw, "4", out[0], BTN_BAHAN_BAKU)
        out = tap(gw, "4", out[0], "🔍 Cari")
        out = gw.handle(msg("4", "D03"))
        self.assertIn("database belum ada", out[0].text)


class GatewayQuizTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        out = self.gw.handle(msg("1", "/qc"))
        out = tap(self.gw, "1", out[0], BTN_BAHAN_BAKU)
        self.out = tap(self.gw, "1", out[0], "🎯 Kuis")

    def test_kuis_5_soal_selesai_dengan_skor(self):
        out = self.out
        self.assertIn("Latihan kilat", out[0].text)
        self.assertIn("Bahan Baku", out[0].text)
        self.assertIn("soal 1/5", out[0].text)
        for _ in range(5):
            # jawab dengan opsi inline pertama (benar/salah tak penting)
            first_cb = cbs(out[0])[0][1]
            self.assertTrue(first_cb.startswith("qc:jawab:"))
            out = self.gw.handle(msg("1", first_cb))
            if "Skor" in out[-1].text and "Latihan kilat" not in out[-1].text:
                break
            out = [out[-1]]
        self.assertTrue(any("Skor" in m.text for m in out))

    def test_kuis_stop_di_tengah(self):
        out2 = tap(self.gw, "1", self.out[0], "⏹ Selesai")
        self.assertIn("Latihan", out2[0].text)


class GatewayProsedurTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())
        self.out = self.gw.handle(msg("1", "/qc"))

    def test_menu_memuat_tombol_prosedur(self):
        out = self.gw.handle(msg("1", "qc:prosedur"))
        self.assertIn("Prosedur Kerja", out[0].text)
        texts = [t for t, _ in cbs(out[0])]
        self.assertIn("🔧 Mesin FT", texts)

    def test_grup_menampilkan_topik(self):
        out = self.gw.handle(msg("1", "qc:prosedur"))
        out = tap(self.gw, "1", out[0], "🔧 Mesin FT")
        self.assertIn("Mesin FT", out[0].text)
        self.assertTrue(any("Inspeksi" in t for t, _ in cbs(out[0])))

    def test_topik_bisa_dibuka_dan_pindah(self):
        out = self.gw.handle(msg("1", "qc:prosedur"))
        out = tap(self.gw, "1", out[0], "🔧 Mesin FT")
        first = cbs(out[0])[0]
        out2 = self.gw.handle(msg("1", first[1]))
        self.assertIn("TTRI-QM-ZY-34-2025", out2[0].text)
        # pindah ke topik lain langsung
        others = [d for t, d in cbs(out2[0]) if d != first[1] and "ptopik" in d]
        out3 = self.gw.handle(msg("1", others[0]))
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


class GatewayPaginationEditTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())

    def _masuk_daftar(self, uid="9"):
        out = self.gw.handle(msg(uid, "/qc"))
        out = tap(self.gw, uid, out[0], BTN_LUAR_JALUR)
        return tap(self.gw, uid, out[0], "📖 Daftar")

    def test_halaman_pertama_pesan_baru(self):
        out = self._masuk_daftar()
        self.assertIsNone(out[0].edit_message_id)

    def test_tap_next_mengedit_pesan_yang_sama(self):
        out = self._masuk_daftar()
        # simulasikan tap ▶ pada pesan daftar (message_id 555)
        m = msg("9", "qc:page:+1", is_callback=True, callback_message_id=555)
        out2 = self.gw.handle(m)
        self.assertEqual(len(out2), 1)
        self.assertEqual(out2[0].edit_message_id, 555)
        self.assertIn("hal. 2/", out2[0].text)

    def test_tap_prev_kembali_mengedit(self):
        self._masuk_daftar()
        m = msg("9", "qc:page:+1", is_callback=True, callback_message_id=555)
        out2 = self.gw.handle(m)
        m2 = msg("9", "qc:page:-1", is_callback=True, callback_message_id=555)
        out3 = self.gw.handle(m2)
        self.assertEqual(out3[0].edit_message_id, 555)
        self.assertIn("hal. 1/", out3[0].text)

    def test_tap_kode_dari_daftar_tetap_pesan_baru(self):
        out = self._masuk_daftar()
        first_cb = cbs(out[0])[0][1]
        m = msg("9", first_cb, is_callback=True, callback_message_id=555)
        out2 = self.gw.handle(m)
        self.assertIsNone(out2[0].edit_message_id)
        self.assertIn("🔍 *", out2[0].text)


if __name__ == "__main__":
    unittest.main()


class GatewayQuickSearchTest(unittest.TestCase):
    """Ketik kata kunci di menu -> pencarian kilat lintas konten."""

    def setUp(self):
        self.gw = QCGateway(atlas=Atlas.bundled())

    def test_kode_persis_langsung_kartu(self):
        out = self.gw.handle(msg("1", "/qc_kode"))
        out = self.gw.handle(msg("1", "C11"))
        self.assertIn("*C11* — Tergores", out[0].text)

    def test_kata_kunci_banyak_hasil_dikelompokkan(self):
        out = self.gw.handle(msg("1", "/qc_kode"))
        out = self.gw.handle(msg("1", "korosi"))
        self.assertIn("Hasil untuk", out[0].text)
        self.assertIn("Cacat", out[0].text)
        # tombol-tombol inline tersedia
        self.assertTrue(len(cbs(out[0])) > 1)

    def test_cari_topik_panduan(self):
        out = self.gw.handle(msg("1", "/qc_kode"))
        out = self.gw.handle(msg("1", "kualitas"))
        text = out[0].text
        self.assertTrue("Panduan" in text or "Cacat" in text)

    def test_tidak_ditemukan(self):
        out = self.gw.handle(msg("1", "/qc_kode"))
        out = self.gw.handle(msg("1", "zzz-tidak-ada-xyz"))
        self.assertIn("Tidak ditemukan", out[0].text)

    def test_dari_submenu_bagian_cari_terbatas(self):
        out = self.gw.handle(msg("1", "/qc_kode"))
        out = tap(self.gw, "1", out[0], BTN_BAHAN_BAKU)
        # ketik langsung di submenu bagian -> cari di bagian itu
        out = self.gw.handle(msg("1", "R19"))
        self.assertIn("Jenis 1", [t for t, _ in cbs(out[0])])

    def test_entry_qc_panduan(self):
        out = self.gw.handle(msg("1", "/qc_panduan"))
        self.assertIn("Panduan Kerja", out[0].text)

    def test_entry_qc_ft(self):
        out = self.gw.handle(msg("1", "/qc_ft"))
        self.assertIn("Mesin FT", out[0].text)


if __name__ == "__main__":
    unittest.main()
