"""Test qm_coil/wizard.py — simulasi alur percakapan end-to-end."""

from __future__ import annotations

import unittest

from qm_coil.state import CoilSessionStore
from qm_coil.wizard import (
    STEPS,
    CoilWizard,
    cancel_wizard,
    handle_callback,
    handle_text_input,
    start_new_wizard,
)

SOURCE_COIL = "QH2608K2531HA10"  # material K -> S30403


def tap(store, user_id, data):
    """Simulasikan tap tombol (callback)."""
    return handle_callback(user_id, data, store)


def type_text(store, user_id, text):
    return handle_text_input(user_id, text, store)


def labels(reply):
    return [b[0] for row in reply.buttons for b in row]


class WizardFlowTest(unittest.TestCase):
    def setUp(self):
        self.store = CoilSessionStore()
        self.uid = "42"

    def _sampai_preview_nomor(self):
        start_new_wizard(self.uid, self.store)
        tap(self.store, self.uid, "machine:FT")
        replies = type_text(self.store, self.uid, SOURCE_COIL)
        self.assertIn("S30403", replies[0].text)
        tap(self.store, self.uid, "action:confirm_material")
        type_text(self.store, self.uid, "1.24*1524")
        type_text(self.store, self.uid, "2")
        replies = type_text(self.store, self.uid, "1")
        self.assertIn("Nomor gulungan yang akan dibuat", replies[0].text)
        return replies

    def _isi_satu_coil(self, grade="A1", defect="B22", length="955",
                       diameter="Tidak Perlu"):
        tap(self.store, self.uid, f"grade:{grade}")
        type_text(self.store, self.uid, defect)
        tap(self.store, self.uid, "remark:default")
        replies = type_text(self.store, self.uid, length)
        # prompt diameter FT
        self.assertIn("Apakah perlu ubah diameter", replies[0].text)
        return tap(self.store, self.uid, f"diameter:{diameter}")

    def test_mulai_dan_pilih_mesin(self):
        replies = start_new_wizard(self.uid, self.store)
        self.assertEqual(self.store.get(self.uid)["step"], STEPS.SELECT_MACHINE)
        self.assertIn("Silakan pilih mesin", replies[0].text)
        self.assertEqual(labels(replies[0]), ["FT", "FJ", "Batal"])

    def test_mesin_tidak_valid(self):
        start_new_wizard(self.uid, self.store)
        replies = tap(self.store, self.uid, "machine:XX")
        self.assertIn("Mesin", replies[0].text)
        self.assertEqual(self.store.get(self.uid)["step"], STEPS.SELECT_MACHINE)

    def test_alur_nomor_sampai_preview(self):
        self._sampai_preview_nomor()
        session = self.store.get(self.uid)
        self.assertEqual(session["step"], STEPS.PREVIEW_NUMBERING)
        self.assertEqual(len(session["generatedCoils"]), 2)
        # HA10 + start digit 1, count 2 -> HA11, HA12
        self.assertTrue(session["generatedCoils"][0].endswith("HA11"))
        self.assertTrue(session["generatedCoils"][1].endswith("HA12"))

    def test_alur_penuh_sampai_output_final(self):
        self._sampai_preview_nomor()
        tap(self.store, self.uid, "action:confirm_numbering")
        replies = self._isi_satu_coil()
        # lanjut ke coil 2
        self.assertIn("Coil 1 selesai", replies[0].text)
        self.assertIn("pilih Grade", replies[0].text)
        replies = self._isi_satu_coil(grade="B", defect="R20", length="900")
        # preview full form
        self.assertIn("PREVIEW DATA INSPEKSI", replies[0].text)
        self.assertEqual(
            self.store.get(self.uid)["step"], STEPS.PREVIEW_FULL_FORM
        )
        replies = tap(self.store, self.uid, "action:generate_final")
        self.assertEqual(len(replies), 2)
        self.assertIn("FORM BERHASIL DIGENERATE", replies[0].text)
        self.assertIn("```text", replies[1].text)
        self.assertIn("机组", replies[1].text)  # output Mandarin
        # sesi di-reset
        self.assertFalse(self.store.has(self.uid))

    def test_edit_spesifikasi(self):
        self._sampai_preview_nomor()
        tap(self.store, self.uid, "action:confirm_numbering")
        self._isi_satu_coil()
        self._isi_satu_coil()
        tap(self.store, self.uid, "edit:specification")
        replies = type_text(self.store, self.uid, "1.50*1524")
        self.assertIn("diperbarui", replies[0].text)
        self.assertIn("PREVIEW DATA INSPEKSI", replies[1].text)
        self.assertIn("1.50*1524", replies[1].text)

    def test_edit_data_coil_panjang(self):
        self._sampai_preview_nomor()
        tap(self.store, self.uid, "action:confirm_numbering")
        self._isi_satu_coil()
        self._isi_satu_coil()
        tap(self.store, self.uid, "edit:select_coil")
        replies = tap(self.store, self.uid, "edit_coil:0")
        self.assertIn("Edit data untuk", replies[0].text)
        tap(self.store, self.uid, "edit_field:length")
        replies = type_text(self.store, self.uid, "1000")
        self.assertIn("diperbarui", replies[0].text)
        self.assertIn("1000", replies[1].text)

    def test_edit_nomor_gulungan(self):
        start_new_wizard(self.uid, self.store)
        tap(self.store, self.uid, "machine:FJ")
        type_text(self.store, self.uid, SOURCE_COIL)
        # ubah nomor via tombol
        replies = tap(self.store, self.uid, "action:edit_source_coil")
        self.assertIn("masukkan kembali nomor gulungan", replies[0].text)
        self.assertEqual(
            self.store.get(self.uid)["step"], STEPS.INPUT_SOURCE_COIL
        )

    def test_cancel(self):
        start_new_wizard(self.uid, self.store)
        replies = cancel_wizard(self.uid, self.store)
        self.assertIn("dibatalkan", replies[0].text)
        self.assertFalse(self.store.has(self.uid))

    def test_callback_tanpa_sesi(self):
        replies = tap(self.store, self.uid, "grade:A1")
        self.assertIn("Sesi tidak aktif", replies[0].text)

    def test_cmd_material_dan_help(self):
        replies = tap(self.store, self.uid, "cmd:material")
        self.assertIn("TABEL REFERENSI MATERIAL", replies[0].text)
        self.assertTrue(replies[0].markdown)
        replies = tap(self.store, self.uid, "cmd:help")
        self.assertIn("/new", replies[0].text)

    def test_input_tidak_dikenali(self):
        start_new_wizard(self.uid, self.store)
        # paksa ke langkah yang tidak ada di switch
        self.store.set(self.uid, {"step": "LANGKAH_ASING"})
        replies = type_text(self.store, self.uid, "halo")
        self.assertIn("tidak dikenali", replies[0].text)


class CoilWizardAdapterTest(unittest.TestCase):
    """CoilWizard.handle: mapping label tombol -> callback + OutgoingMessage."""

    def test_handle_lewat_label_tombol(self):
        from qm_training.bot.adapters.base import IncomingMessage

        wizard = CoilWizard(CoilSessionStore())
        out = wizard.handle(IncomingMessage(user_id="7", text="/new"))
        self.assertTrue(out)
        self.assertIn("Silakan pilih mesin", out[0].text)
        self.assertIn("FT", out[0].buttons)

        # tap via label (seperti reply keyboard Telegram)
        out = wizard.handle(IncomingMessage(user_id="7", text="FT"))
        self.assertIn("Mesin terpilih", out[0].text)
        self.assertTrue(out[0].markdown)

        out = wizard.handle(IncomingMessage(user_id="7", text=SOURCE_COIL))
        self.assertIn("S30403", out[0].text)

        out = wizard.handle(IncomingMessage(user_id="7", text="Lanjut"))
        self.assertIn("spesifikasi", out[0].text)


if __name__ == "__main__":
    unittest.main()
