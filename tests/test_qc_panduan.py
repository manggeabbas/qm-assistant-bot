"""Tests untuk fitur 📘 Panduan Kerja (qm_bantuan/data/panduan.json + gateway)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from qm_training.bot.adapters.base import IncomingMessage

from qm_bantuan.data import Panduan
from qm_bantuan.gateway import BTN_GUIDE, QCGateway

DATA_DIR = Path(__file__).resolve().parent.parent / "qm_bantuan" / "data"

_EXPECTED_IDS = ["grade", "prinsip", "batch", "kode"]


def _msg(user_id="7", text="", update_id=0):
    return IncomingMessage(
        user_id=str(user_id),
        text=text,
        update_id=update_id,
    )


class PanduanDataTest(unittest.TestCase):
    def test_json_valid_dan_lengkap(self):
        raw = json.loads((DATA_DIR / "panduan.json").read_text(encoding="utf-8"))
        self.assertIn("topics", raw)
        self.assertEqual(len(raw["topics"]), 4)

    def test_semua_topik_wajib_ada_dan_berisi(self):
        p = Panduan.bundled()
        ids = [t["id"] for t in p.topics()]
        for want in _EXPECTED_IDS:
            self.assertIn(want, ids, f"topik '{want}' hilang")
        for t in p.topics():
            for key in ("id", "emoji", "judul", "isi"):
                self.assertTrue(str(t.get(key, "")).strip(), f"{t.get('id')}: '{key}' kosong")

    def test_konten_tidak_kosong_dan_menyebut_acuan(self):
        p = Panduan.bundled()
        grade = p.get("grade")
        self.assertIn("A1", grade["isi"])
        self.assertIn("<3T", grade["isi"])
        batch = p.get("batch")
        self.assertIn("16", batch["isi"])
        kode = p.get("kode")
        self.assertIn("R13TD07900800H", kode["isi"])

    def test_get_unknown_kembali_none(self):
        self.assertIsNone(Panduan.bundled().get("tidak_ada"))


class PanduanGatewayTest(unittest.TestCase):
    def setUp(self):
        self.gw = QCGateway()
        self.uid = 42
        self._n = 0

    def _send(self, text):
        self._n += 1
        return self.gw.handle(_msg(user_id=self.uid, text=text, update_id=self._n))

    def _buttons(self, replies):
        out = []
        for r in replies:
            out.extend(getattr(r, "buttons", []) or [])
        return out

    def test_menu_memuat_tombol_panduan(self):
        replies = self._send("/qc")
        self.assertIn(BTN_GUIDE, self._buttons(replies))

    def test_masuk_panduan_menampilkan_daftar_topik(self):
        self._send("/qc")
        replies = self._send(BTN_GUIDE)
        buttons = self._buttons(replies)
        for t in Panduan.bundled().topics():
            self.assertIn(Panduan.label(t), buttons)

    def test_setiap_topik_bisa_dibuka(self):
        self._send("/qc")
        self._send(BTN_GUIDE)
        for t in Panduan.bundled().topics():
            replies = self._send(Panduan.label(t))
            text = "\n".join(r.text for r in replies)
            self.assertIn(t["judul"], text)
            # isi topik tampil (cek potongan awal isi)
            self.assertIn(t["isi"][:40].strip().split("\n")[0][:20], text)

    def test_dari_topik_bisa_pindah_topik_langsung(self):
        self._send("/qc")
        self._send(BTN_GUIDE)
        topics = Panduan.bundled().topics()
        self._send(Panduan.label(topics[0]))
        replies = self._send(Panduan.label(topics[1]))
        text = "\n".join(r.text for r in replies)
        self.assertIn(topics[1]["judul"], text)

    def test_tombol_panduan_berlaku_dari_substate_lain(self):
        # dari dalam pencarian, tombol 📘 tetap bisa dipakai
        self._send("/qc")
        self._send("🔍 Cari cacat")
        replies = self._send(BTN_GUIDE)
        text = "\n".join(r.text for r in replies)
        self.assertIn("Panduan Kerja", text)

    def test_kembali_ke_menu_dari_panduan(self):
        self._send("/qc")
        self._send(BTN_GUIDE)
        replies = self._send("◀ Kembali")
        text = "\n".join(r.text for r in replies)
        self.assertIn("Bantuan QC", text)


if __name__ == "__main__":
    unittest.main()
